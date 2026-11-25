from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    topic: str | None = Field(default=None, max_length=500)
    target_duration_seconds: int | None = Field(default=None, ge=30, le=7200)
    aspect_ratio: str = Field(default="16:9", pattern=r"^(16:9|9:16|1:1|4:3)$")
    language: str = Field(default="en", min_length=2, max_length=12, pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    visual_style: str = Field(default="hybrid", pattern=r"^(hybrid|cinematic|animated_maps)$")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name cannot be blank")
        return normalized

    @field_validator("description", "topic")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ProjectCreate(ProjectFields):
    pass


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    topic: str | None = Field(default=None, max_length=500)
    status: ProjectStatus | None = None
    target_duration_seconds: int | None = Field(default=None, ge=30, le=7200)
    aspect_ratio: str | None = Field(default=None, pattern=r"^(16:9|9:16|1:1|4:3)$")
    language: str | None = Field(default=None, min_length=2, max_length=12, pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    visual_style: str | None = Field(default=None, pattern=r"^(hybrid|cinematic|animated_maps)$")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name cannot be blank")
        return normalized

    @field_validator("description", "topic")
    @classmethod
    def normalize_patch_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one project field must be provided")
        return self


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    topic: str | None
    status: ProjectStatus
    target_duration_seconds: int | None
    aspect_ratio: str
    language: str
    visual_style: str
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def timestamps_are_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @field_serializer("created_at", "updated_at")
    def serialize_timestamps(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ProjectStats(BaseModel):
    total: int
    draft: int
    in_progress: int
    completed: int
    recently_updated: list[ProjectResponse]
