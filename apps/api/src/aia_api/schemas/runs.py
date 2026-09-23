"""Request and response models for workflow runs and artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RunCreateRequest(BaseModel):
    """Start a workflow against a project's current revision."""

    model_config = ConfigDict(extra="forbid")

    workflow_type: Literal["develop_snapshot"] = Field(
        description="A workflow template name. Closed set; the domain owns the graph."
    )


class AttemptResponse(BaseModel):
    """One execution attempt of a step. Append-only history."""

    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    attempt_number: int
    status: str
    worker_id: str | None = None
    failure_class: str | None = None
    error: dict[str, Any] = Field(default_factory=dict)
    provider: str | None = None
    model: str | None = None
    estimated_cost_usd: float | None = None
    actual_cost_usd: float | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class StepRunResponse(BaseModel):
    """One node of the run."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    node_key: str
    kind: str
    status: str
    stage_type: str
    attempts_recorded: int
    attempts_consumed: int
    max_attempts: int
    waiting_reason: str | None = None
    runnable_after: datetime | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    attempts: list[AttemptResponse] = Field(default_factory=list)


class RunSummaryResponse(BaseModel):
    """A run without its steps, for listings."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: str
    needs_attention: bool
    is_terminal: bool
    workflow_type: str
    project_id: str
    project_revision: int
    cancel_requested: bool = False
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunResponse(RunSummaryResponse):
    """A run with its steps and their attempt history."""

    created: bool | None = Field(
        default=None,
        description="On creation only: False when an existing run satisfied the request.",
    )
    steps: list[StepRunResponse] = Field(default_factory=list)


class RunListResponse(BaseModel):
    """A project's runs, newest first."""

    model_config = ConfigDict(extra="forbid")

    items: list[RunSummaryResponse]


class RunEventResponse(BaseModel):
    """One entry of a run's event feed."""

    model_config = ConfigDict(extra="forbid")

    event_id: int
    step_id: str | None = None
    attempt_id: str | None = None
    event_type: str
    level: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class ArtifactResponse(BaseModel):
    """Artifact metadata and, for a small JSON artifact, its decoded payload.

    Never the storage key: clients receive content or a short-lived URL, not a
    path into the bucket.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    project_id: str
    revision: int
    stage_type: str
    artifact_type: str
    content_type: str
    sha256: str
    size_bytes: int
    status: str
    input_fingerprint_prefix: str = ""
    provider: str | None = None
    model: str = ""
    runtime_version: str = ""
    produced_by_job_id: str | None = None
    created_at: datetime | None = None
    payload: dict[str, Any] | list[Any] | None = Field(
        default=None, description="Decoded content when it is JSON under 1 MiB; else null."
    )
