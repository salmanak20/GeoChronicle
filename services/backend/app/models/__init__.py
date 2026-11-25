from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'in_progress', 'completed', 'archived')",
            name="ck_projects_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(String(500), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    target_duration_seconds: Mapped[int | None] = mapped_column(nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(8), nullable=False, default="16:9", server_default="16:9")
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="en", server_default="en")
    visual_style: Mapped[str] = mapped_column(String(32), nullable=False, default="hybrid", server_default="hybrid")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), server_default=func.now())
    research_sessions: Mapped[list["ResearchSession"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    scripts: Mapped[list["ScriptDocument"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ResearchSession(Base):
    __tablename__ = "research_sessions"
    __table_args__ = (CheckConstraint("status IN ('pending','running','completed','failed')", name="ck_research_sessions_status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    progress: Mapped[str | None] = mapped_column(String(300))
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    project: Mapped[Project] = relationship(back_populates="research_sessions")
    sources: Mapped[list["ResearchSource"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    claims: Mapped[list["Claim"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ResearchSource(Base):
    __tablename__ = "research_sources"
    __table_args__ = (UniqueConstraint("session_id", "url", name="uq_research_sources_session_url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(300))
    author: Mapped[str | None] = mapped_column(String(300))
    publication_date: Mapped[str | None] = mapped_column(String(40))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    content: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    reliability_assessment: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    session: Mapped[ResearchSession] = relationship(back_populates="sources")
    claim_links: Mapped[list["ClaimSource"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint("category IN ('fact','interpretation','estimate','opinion')", name="ck_claims_category"),
        CheckConstraint("verification_status IN ('unverified','supported','partially_supported','disputed','contradicted','insufficient_evidence')", name="ck_claims_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("research_sessions.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False, default="fact")
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified", index=True)
    confidence: Mapped[float | None] = mapped_column(Float(), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    session: Mapped[ResearchSession] = relationship(back_populates="claims")
    source_links: Mapped[list["ClaimSource"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    fact_checks: Mapped[list["FactCheckResult"]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class ClaimSource(Base):
    __tablename__ = "claim_sources"
    __table_args__ = (UniqueConstraint("claim_id", "source_id", name="uq_claim_source"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("research_sources.id", ondelete="CASCADE"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(24), nullable=False, default="relevant")
    evidence: Mapped[str | None] = mapped_column(Text)
    claim: Mapped[Claim] = relationship(back_populates="source_links")
    source: Mapped[ResearchSource] = relationship(back_populates="claim_links")


class FactCheckResult(Base):
    __tablename__ = "fact_check_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float(), nullable=True)
    supporting_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    contradicting_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    claim: Mapped[Claim] = relationship(back_populates="fact_checks")


class ScriptDocument(Base):
    __tablename__ = "script_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    research_session_id: Mapped[int | None] = mapped_column(ForeignKey("research_sessions.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="Video script")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    project: Mapped[Project] = relationship(back_populates="scripts")
    sections: Mapped[list["ScriptSection"]] = relationship(back_populates="script", cascade="all, delete-orphan")
    versions: Mapped[list["ScriptVersion"]] = relationship(back_populates="script", cascade="all, delete-orphan")
    storyboards: Mapped[list["Storyboard"]] = relationship(back_populates="script", cascade="all, delete-orphan")


class ScriptSection(Base):
    __tablename__ = "script_sections"
    __table_args__ = (UniqueConstraint("script_id", "section_key", name="uq_script_section"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("script_documents.id", ondelete="CASCADE"), index=True)
    section_key: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    script: Mapped[ScriptDocument] = relationship(back_populates="sections")


class ScriptVersion(Base):
    __tablename__ = "script_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("script_documents.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(nullable=False)
    sections_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    change_note: Mapped[str] = mapped_column(String(300), nullable=False, default="Saved changes")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    script: Mapped[ScriptDocument] = relationship(back_populates="versions")


class Storyboard(Base):
    __tablename__ = "storyboards"
    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("script_documents.id", ondelete="CASCADE"), index=True)
    schema_version: Mapped[str] = mapped_column(String(12), nullable=False, default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    script: Mapped[ScriptDocument] = relationship(back_populates="storyboards")
    scenes: Mapped[list["StoryboardScene"]] = relationship(back_populates="storyboard", cascade="all, delete-orphan", order_by="StoryboardScene.scene_number")


class StoryboardScene(Base):
    __tablename__ = "storyboard_scenes"
    id: Mapped[int] = mapped_column(primary_key=True)
    storyboard_id: Mapped[int] = mapped_column(ForeignKey("storyboards.id", ondelete="CASCADE"), index=True)
    scene_number: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    script_section_key: Mapped[str | None] = mapped_column(String(40))
    narration_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_seconds: Mapped[int] = mapped_column(nullable=False, default=20)
    visual_direction: Mapped[str] = mapped_column(Text, nullable=False, default="")
    historical_events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    geographic_references: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    claim_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    transition_suggestion: Mapped[str | None] = mapped_column(String(300))
    storyboard: Mapped[Storyboard] = relationship(back_populates="scenes")
    narration_segments: Mapped[list["NarrationSegment"]] = relationship(back_populates="scene", cascade="all, delete-orphan")


class NarrationSegment(Base):
    __tablename__ = "narration_segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("storyboard_scenes.id", ondelete="CASCADE"), index=True)
    segment_number: Mapped[int] = mapped_column(nullable=False)
    paragraph_number: Mapped[int] = mapped_column(nullable=False, default=1)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_duration_seconds: Mapped[float] = mapped_column(Float(), nullable=False)
    scene: Mapped[StoryboardScene] = relationship(back_populates="narration_segments")


class ApplicationSettings(Base):
    __tablename__ = "application_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    setting_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    setting_value: Mapped[object] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProviderConfiguration(Base):
    __tablename__ = "provider_configurations"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model_name: Mapped[str | None] = mapped_column(String(200))
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
