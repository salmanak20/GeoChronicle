from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

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
