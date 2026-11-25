from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from app.api.router import router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import configure_database


def migrate_database(engine=None) -> None:
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.resolved_database_url().replace("%", "%%"))
    engine = engine or configure_database()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    legacy_tables = {"projects", "application_settings", "provider_configurations"}
    has_migration_marker = False
    if "alembic_version" in tables:
        with engine.connect() as connection:
            has_migration_marker = connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version LIMIT 1"
            ).first() is not None
    if legacy_tables.issubset(tables) and not has_migration_marker:
        expected_columns = {
            "projects": {"id", "name", "description", "topic", "status", "created_at", "updated_at"},
            "application_settings": {"id", "setting_key", "setting_value", "updated_at"},
            "provider_configurations": {"id", "provider_name", "enabled", "model_name", "configuration", "created_at", "updated_at"},
        }
        matches_initial_schema = all(
            {column["name"] for column in inspector.get_columns(table)} == columns
            for table, columns in expected_columns.items()
        )
        if matches_initial_schema:
            command.stamp(config, "0001_initial")
    command.upgrade(config, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = configure_database()
    migrate_database(engine)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": {"code": "internal_error", "message": "An unexpected error occurred"}})


configure_logging()

\n