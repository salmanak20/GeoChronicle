from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.exc import ArgumentError

from app.core.config import Settings, settings
from app.db.session import configure_database
from app.main import migrate_database
from app.schemas.project import ProjectCreate


def test_invalid_database_configuration_is_rejected():
    try:
        configure_database("not-a-database-url")
        assert False, "invalid database URL should fail"
    except ArgumentError:
        pass


def test_project_input_validation():
    assert ProjectCreate(name="A story").aspect_ratio == "16:9"
    for invalid in ({"name": ""}, {"name": "x" * 201}, {"name": "ok", "extra": True}):
        try:
            ProjectCreate(**invalid)
            assert False, "invalid project input should fail"
        except ValidationError:
            pass


def test_settings_unique_key_and_provider_persistence(tmp_path):
    engine = configure_database(f"sqlite:///{tmp_path / 'models.db'}")
    from app.db.base import Base
    from app.models import ApplicationSettings, ProviderConfiguration, Project
    from sqlalchemy.orm import Session
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Project(name="Persistence", topic="History"),
            ProviderConfiguration(provider_name="future", configuration={"region": "local"}),
            ApplicationSettings(setting_key="theme", setting_value="dark"),
        ])
        session.commit()
    with Session(engine) as session:
        assert session.query(Project).one().topic == "History"
        assert session.query(ProviderConfiguration).one().configuration == {"region": "local"}
        assert session.query(ApplicationSettings).one().setting_value == "dark"


def test_migration_empty_downgrade_and_upgrade(client, tmp_path):
    config = Config("alembic.ini")
    url = settings.resolved_database_url()
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.downgrade(config, "base")
    assert "projects" not in inspect(configure_database(url)).get_table_names()
    command.upgrade(config, "head")
    assert {"projects", "application_settings", "provider_configurations", "alembic_version"}.issubset(
        inspect(configure_database(url)).get_table_names()
    )


def test_test_database_urls_are_configurable():
    configured = Settings(database_url="sqlite:///custom.db")
    assert configured.resolved_database_url() == "sqlite:///custom.db"


def test_existing_phase2_tables_are_adopted_without_recreation(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    engine = configure_database(url)
    config = Config("alembic.ini")
    command.upgrade(config, "0001_initial")
    with engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM alembic_version")
    migrate_database(engine)
    inspector = inspect(engine)
    assert "alembic_version" in inspector.get_table_names()
    assert {"projects", "application_settings", "provider_configurations"}.issubset(inspector.get_table_names())


def test_database_content_survives_engine_reconfiguration(tmp_path):
    url = f"sqlite:///{tmp_path / 'restart.db'}"
    engine = configure_database(url)
    from app.db.base import Base
    from app.models import Project
    from sqlalchemy.orm import Session
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Project(name="Survives reconnect"))
        session.commit()
    engine.dispose()
    restarted_engine = configure_database(url)
    with Session(restarted_engine) as session:
        assert session.query(Project).one().name == "Survives reconnect"
