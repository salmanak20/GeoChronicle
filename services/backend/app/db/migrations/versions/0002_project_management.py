"""Add project production settings and status validation.

Revision ID: 0002_project_management
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_project_management"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("target_duration_seconds", sa.Integer(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("aspect_ratio", sa.String(length=8), nullable=False, server_default="16:9"),
    )
    op.add_column(
        "projects",
        sa.Column("language", sa.String(length=12), nullable=False, server_default="en"),
    )
    op.add_column(
        "projects",
        sa.Column("visual_style", sa.String(length=32), nullable=False, server_default="hybrid"),
    )
    op.create_index("ix_projects_topic", "projects", ["topic"])
    with op.batch_alter_table("projects") as batch:
        batch.create_check_constraint(
            "ck_projects_status",
            "status IN ('draft', 'in_progress', 'completed', 'archived')",
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("ck_projects_status", type_="check")
        batch.drop_column("visual_style")
        batch.drop_column("language")
        batch.drop_column("aspect_ratio")
        batch.drop_column("target_duration_seconds")
    op.drop_index("ix_projects_topic", table_name="projects")
