from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config,pool
from app.core.config import settings
from app.db.base import Base
from app import models
a=config=context.config

target_metadata=Base.metadata
def run_migrations_offline():
 context.configure(url=settings.resolved_database_url(),target_metadata=target_metadata,literal_binds=True,compare_type=True)
 with context.begin_transaction():context.run_migrations()
def run_migrations_online():
 cfg=a.get_section(a.config_ini_section);cfg['sqlalchemy.url']=settings.resolved_database_url()
 connectable=engine_from_config(cfg,prefix='sqlalchemy.',poolclass=pool.NullPool)
 with connectable.connect() as connection:
  context.configure(connection=connection,target_metadata=target_metadata,compare_type=True)
  with context.begin_transaction():context.run_migrations()
run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
