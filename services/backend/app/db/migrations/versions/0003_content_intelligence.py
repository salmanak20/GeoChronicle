"""Phase 4 research and content preparation."""
from alembic import op
import sqlalchemy as sa

revision = "0003_content_intelligence"
down_revision = "0002_project_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("research_sessions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(500), nullable=False), sa.Column("configuration", sa.JSON(), nullable=False), sa.Column("results", sa.JSON(), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("progress", sa.String(300)), sa.Column("error", sa.String(500)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('pending','running','completed','failed')", name="ck_research_sessions_status"))
    op.create_index("ix_research_sessions_project_id", "research_sessions", ["project_id"])
    op.create_index("ix_research_sessions_status", "research_sessions", ["status"])
    op.create_table("research_sources",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False), sa.Column("url", sa.String(2048), nullable=False), sa.Column("publisher", sa.String(300)), sa.Column("author", sa.String(300)),
        sa.Column("publication_date", sa.String(40)), sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("content", sa.Text()), sa.Column("summary", sa.Text()), sa.Column("reliability_assessment", sa.Text()), sa.Column("provenance", sa.JSON(), nullable=False),
        sa.UniqueConstraint("session_id", "url", name="uq_research_sources_session_url"))
    op.create_index("ix_research_sources_session_id", "research_sources", ["session_id"])
    op.create_table("claims",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False), sa.Column("category", sa.String(24), nullable=False), sa.Column("verification_status", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float()), sa.Column("reviewer_notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("category IN ('fact','interpretation','estimate','opinion')", name="ck_claims_category"),
        sa.CheckConstraint("verification_status IN ('unverified','supported','partially_supported','disputed','contradicted','insufficient_evidence')", name="ck_claims_status"))
    op.create_index("ix_claims_session_id", "claims", ["session_id"])
    op.create_index("ix_claims_verification_status", "claims", ["verification_status"])
    op.create_table("claim_sources", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False), sa.Column("relationship_type", sa.String(24), nullable=False), sa.Column("evidence", sa.Text()),
        sa.UniqueConstraint("claim_id", "source_id", name="uq_claim_source"))
    op.create_index("ix_claim_sources_claim_id", "claim_sources", ["claim_id"])
    op.create_index("ix_claim_sources_source_id", "claim_sources", ["source_id"])
    op.create_table("fact_check_results", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("confidence", sa.Float()), sa.Column("supporting_evidence", sa.JSON(), nullable=False), sa.Column("contradicting_evidence", sa.JSON(), nullable=False),
        sa.Column("method", sa.String(80), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_fact_check_results_claim_id", "fact_check_results", ["claim_id"])
    op.create_table("script_documents", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("research_session_id", sa.Integer(), sa.ForeignKey("research_sessions.id", ondelete="SET NULL")), sa.Column("title", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_script_documents_project_id", "script_documents", ["project_id"])
    op.create_table("script_sections", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("script_id", sa.Integer(), sa.ForeignKey("script_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_key", sa.String(40), nullable=False), sa.Column("title", sa.String(160), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("script_id", "section_key", name="uq_script_section"))
    op.create_index("ix_script_sections_script_id", "script_sections", ["script_id"])
    op.create_table("script_versions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("script_id", sa.Integer(), sa.ForeignKey("script_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False), sa.Column("sections_snapshot", sa.JSON(), nullable=False), sa.Column("change_note", sa.String(300), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_script_versions_script_id", "script_versions", ["script_id"])
    op.create_table("storyboards", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("script_id", sa.Integer(), sa.ForeignKey("script_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_version", sa.String(12), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_storyboards_script_id", "storyboards", ["script_id"])
    op.create_table("storyboard_scenes", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("storyboard_id", sa.Integer(), sa.ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("script_section_key", sa.String(40)), sa.Column("narration_text", sa.Text(), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False), sa.Column("visual_direction", sa.Text(), nullable=False), sa.Column("historical_events", sa.JSON(), nullable=False), sa.Column("geographic_references", sa.JSON(), nullable=False),
        sa.Column("claim_ids", sa.JSON(), nullable=False), sa.Column("source_ids", sa.JSON(), nullable=False), sa.Column("transition_suggestion", sa.String(300)))
    op.create_index("ix_storyboard_scenes_storyboard_id", "storyboard_scenes", ["storyboard_id"])
    op.create_table("narration_segments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("scene_id", sa.Integer(), sa.ForeignKey("storyboard_scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("segment_number", sa.Integer(), nullable=False), sa.Column("paragraph_number", sa.Integer(), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("estimated_duration_seconds", sa.Float(), nullable=False))
    op.create_index("ix_narration_segments_scene_id", "narration_segments", ["scene_id"])


def downgrade() -> None:
    for table in ("narration_segments", "storyboard_scenes", "storyboards", "script_versions", "script_sections", "script_documents", "fact_check_results", "claim_sources", "claims", "research_sources", "research_sessions"):
        op.drop_table(table)
