from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
_engine=None
SessionLocal=None
def configure_database(url=None):
 global _engine,SessionLocal
 url=url or settings.resolved_database_url()
 _engine=create_engine(url,connect_args={"check_same_thread":False} if url.startswith("sqlite") else {})
 if _engine.dialect.name=="sqlite":
  @event.listens_for(_engine,"connect")
  def fk(conn,_):conn.execute("PRAGMA foreign_keys=ON")
 SessionLocal=sessionmaker(bind=_engine,expire_on_commit=False)
 return _engine
def get_engine():return _engine or configure_database()
def init_db():
 from app import models
 from app.db.base import Base
 Base.metadata.create_all(get_engine())
def get_session():
 s=(SessionLocal or sessionmaker(bind=get_engine(),expire_on_commit=False))()
 try:yield s
 finally:s.close()
