from sqlalchemy.exc import IntegrityError
from app.db.session import configure_database,get_session
from app.models import Project,ApplicationSettings,ProviderConfiguration

def test_project_and_provider_persist(tmp_path):
 engine=configure_database(f"sqlite:///{tmp_path/'persist.db'}")
 from app.db.base import Base
 Base.metadata.create_all(engine)
 from sqlalchemy.orm import Session
 with Session(engine) as s:
  s.add(Project(name="Test story",topic="History"));s.add(ProviderConfiguration(provider_name="future",enabled=False,configuration={"region":"local"}));s.commit()
 with Session(engine) as s:
  assert s.query(Project).one().name=="Test story"
  assert s.query(ProviderConfiguration).one().configuration=={"region":"local"}

def test_setting_key_is_unique(tmp_path):
 engine=configure_database(f"sqlite:///{tmp_path/'unique.db'}")
 from app.db.base import Base
 Base.metadata.create_all(engine)
 from sqlalchemy.orm import Session
 with Session(engine) as s:
  s.add_all([ApplicationSettings(setting_key="theme",setting_value="dark"),ApplicationSettings(setting_key="theme",setting_value="light")])
  try:s.commit();assert False,"duplicate key should fail"
  except IntegrityError:s.rollback()
