from datetime import datetime
from typing import Literal
from pydantic import field_validator, model_validator

from pydantic import BaseModel, ConfigDict, Field


class ResearchStart(BaseModel):
    topic: str | None = Field(default=None, max_length=500)
    source_limit: int = Field(default=8, ge=1, le=10)
    include_primary_sources: bool = True
    region: str | None = Field(default=None, max_length=120)
    date_range: str | None = Field(default=None, max_length=120)


class ResearchStatus(BaseModel):
    id: int
    project_id: int
    topic: str
    configuration: dict
    status: str
    progress: str | None
    error: str | None
    overview: str | None = None
    perspectives: list[str] = Field(default_factory=list)
    created_at: str
    completed_at: str | None


class SourceOut(BaseModel):
    id: int
    title: str
    url: str
    publisher: str | None
    author: str | None
    publication_date: str | None
    retrieved_at: datetime
    source_type: str
    content: str | None
    summary: str | None
    reliability_assessment: str | None
    provenance: dict

    model_config = ConfigDict(from_attributes=True)


class ClaimOut(BaseModel):
    id: int
    session_id: int
    text: str
    category: str
    verification_status: str
    confidence: float | None
    reviewer_notes: str | None
    sources: list[dict]


class ClaimReview(BaseModel):
    verification_status: Literal["unverified", "supported", "partially_supported", "disputed", "contradicted", "insufficient_evidence"] | None = None
    reviewer_notes: str | None = Field(default=None, max_length=4000)


class ScriptGenerate(BaseModel):
    research_session_id: int | None = None
    audience: str = Field(default="general audience", max_length=300)
    narrative_structure: str = Field(default="documentary", max_length=120)


class SectionUpdate(BaseModel):
    content: str = Field(max_length=12000)
    change_note: str = Field(default="Edited section", max_length=300)


class SectionApproval(BaseModel):
    approved: bool


class SceneUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    script_section_key: str | None = Field(default=None, max_length=40)
    narration_text: str = Field(default="", max_length=12000)
    description: str = Field(default="", max_length=8000)
    duration_seconds: int = Field(ge=1, le=600)
    visual_direction: str = Field(default="", max_length=8000)
    historical_events: list[str] = Field(default_factory=list, max_length=20)
    geographic_references: list[str] = Field(default_factory=list, max_length=20)
    claim_ids: list[int] = Field(default_factory=list, max_length=50)
    source_ids: list[int] = Field(default_factory=list, max_length=50)
    transition_suggestion: str | None = Field(default=None, max_length=300)


class NarrationConfig(BaseModel):
    words_per_minute: int = Field(default=145, ge=80, le=250)


class NarrationSegmentUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    words_per_minute: int = Field(default=145, ge=80, le=250)


class ProviderConfigurationUpdate(BaseModel):
    search_provider: Literal["none", "tavily"] | None = None
    search_endpoint: str | None = Field(default=None, max_length=500)
    ai_provider: Literal["none", "openai_compatible"] | None = None
    ai_endpoint: str | None = Field(default=None, max_length=500)
    ai_model: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("search_endpoint", "ai_endpoint")
    @classmethod
    def safe_endpoint(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not (value.startswith("https://") or value.startswith(("http://127.0.0.1:", "http://localhost:"))):
            raise ValueError("Provider endpoints must use HTTPS, or loopback HTTP for local development")
        return value

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one provider setting must be provided")
        return self
