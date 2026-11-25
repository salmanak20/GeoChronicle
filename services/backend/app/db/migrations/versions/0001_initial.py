"""initial tables"""
from alembic import op
import sqlalchemy as sa
revision="0001_initial"
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
 op.create_table('projects',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('name',sa.String(200),nullable=False),sa.Column('description',sa.Text()),sa.Column('topic',sa.String(500)),sa.Column('status',sa.String(32),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
 op.create_index('ix_projects_name','projects',['name']);op.create_index('ix_projects_status','projects',['status'])
 op.create_table('application_settings',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('setting_key',sa.String(120),nullable=False,unique=True),sa.Column('setting_value',sa.JSON(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
 op.create_table('provider_configurations',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('provider_name',sa.String(100),nullable=False),sa.Column('enabled',sa.Boolean(),nullable=False),sa.Column('model_name',sa.String(200)),sa.Column('configuration',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
 op.create_index('ix_provider_configurations_provider_name','provider_configurations',['provider_name'])
def downgrade():
 op.drop_table('provider_configurations');op.drop_table('application_settings');op.drop_index('ix_projects_status',table_name='projects');op.drop_index('ix_projects_name',table_name='projects');op.drop_table('projects')
