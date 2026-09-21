"""Request and response models for the projects API.

These are the public API contract. They are deliberately separate from the domain
models so that a domain refactor does not silently change the wire format, and so
that internal fields (storage keys, organization ids, filesystem paths) can never
leak into a response by default.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreateRequest(BaseModel):
    """Create a research or simulation project."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        max_length=500,
        description="Project title. Defaults to a Czech placeholder per project type.",
    )
    project_type: Literal["research", "simulation"] = "research"
    content: dict[str, Any] = Field(
        default_factory=dict, description="Initial project content for revision 1."
    )
    preferred_provider: Literal["claude_code_subscription", "anthropic", "openai"] | None = None
    provider_policy: (
        Literal["CLAUDE_CODE_ONLY", "CLAUDE_API_ONLY", "OPENAI_ONLY", "CLAUDE_CODE_THEN_API"] | None
    ) = None
    max_api_cost_usd: float | None = Field(default=None, ge=0, le=100_000)
    parent_project_id: str | None = Field(default=None, max_length=64)


class ProjectSaveRequest(BaseModel):
    """Save project content, creating a revision only if it materially changed."""

    model_config = ConfigDict(extra="forbid")

    content: dict[str, Any]
    reason: str = Field(default="autosave", max_length=64)
    force_new_revision: bool = Field(
        default=False,
        description="Create a revision even when content is unchanged (branch/restore).",
    )
    explicit_stage: str | None = Field(
        default=None,
        max_length=64,
        description="Force a rerun from this stage regardless of what changed.",
    )


class ProjectSettingsRequest(BaseModel):
    """Update project header settings."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=500)
    tags: list[str] | None = Field(default=None, max_length=50)
    pinned: bool | None = None
    preferred_provider: Literal["claude_code_subscription", "anthropic", "openai"] | None = None
    provider_policy: (
        Literal["CLAUDE_CODE_ONLY", "CLAUDE_API_ONLY", "OPENAI_ONLY", "CLAUDE_CODE_THEN_API"] | None
    ) = None
    max_api_cost_usd: float | None = Field(default=None, ge=0, le=100_000)


class StageResponse(BaseModel):
    """One stage's public state.

    ``input_fingerprint`` is exposed as a short prefix only: the full value is an
    internal reuse key and publishing it invites clients to reason about cache
    behaviour we may change.
    """

    model_config = ConfigDict(extra="forbid")

    stage_type: str
    ordinal: int
    status: str
    label: str
    provider: str | None = None
    provider_label: str | None = None
    model: str = ""
    artifact_count: int = 0
    waiting_reason: str | None = None
    quota_reset_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    fingerprint_prefix: str = ""
    is_complete: bool = False


class ImpactResponse(BaseModel):
    """Which stages an edit would invalidate."""

    model_config = ConfigDict(extra="forbid")

    root_stage: str | None = None
    invalidate: list[str] = Field(default_factory=list)
    preserve: list[str] = Field(default_factory=list)
    presentation_only: bool = False


class ProjectResponse(BaseModel):
    """A project header."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    title: str
    project_type: str
    status: str
    current_revision: int
    current_stage: str
    last_completed_stage: str | None = None
    parent_project_id: str | None = None
    preferred_provider: str
    provider_label: str
    provider_policy: str
    max_api_cost_usd: float
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    archived: bool = False
    created_at: datetime | None = None
    modified_at: datetime | None = None


class ProjectDetailResponse(ProjectResponse):
    """A project with its current stages and content."""

    stages: list[StageResponse] = Field(default_factory=list)
    content: dict[str, Any] = Field(default_factory=dict)


class SaveResponse(BaseModel):
    """Outcome of a save.

    ``deduplicated`` true means no revision was created because the content was
    unchanged -- the normal result of an idle autosave.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str
    revision: int
    revision_id: str | None = None
    deduplicated: bool
    content_sha256: str
    changed_fields: list[str] = Field(default_factory=list)
    impact: ImpactResponse = Field(default_factory=ImpactResponse)
    current_stage: str = ""
    status: str = ""


class RevisionResponse(BaseModel):
    """One entry of revision history."""

    model_config = ConfigDict(extra="forbid")

    revision: int
    revision_id: str
    parent_revision: int | None = None
    content_sha256: str
    reason: str
    changed_fields: list[str] = Field(default_factory=list)
    impact: ImpactResponse = Field(default_factory=ImpactResponse)
    created_at: datetime | None = None


class EventResponse(BaseModel):
    """One entry of project history."""

    model_config = ConfigDict(extra="forbid")

    event_id: int
    event_type: str
    level: str
    message: str
    revision: int | None = None
    stage_type: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class PageMeta(BaseModel):
    """Pagination metadata, identical on every list endpoint."""

    model_config = ConfigDict(extra="forbid")

    total: int
    limit: int
    offset: int
    has_more: bool


class ProjectListResponse(BaseModel):
    """A page of projects."""

    model_config = ConfigDict(extra="forbid")

    items: list[ProjectResponse]
    page: PageMeta


class ErrorResponse(BaseModel):
    """The single error shape every endpoint returns.

    ``code`` is a stable machine-readable string clients may branch on; ``message``
    is human-readable and may change. ``request_id`` ties the response to the
    server logs for support.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
