"""Project, revision and stage domain model.

The durable graph is ``Project -> immutable Revision -> Stage -> Artifact``. The
project is the source of truth; workflows and jobs only orchestrate work against
it. This module holds the pure decision logic for saving a revision -- what
deduplicates, what creates a new revision, and which completed stages carry
forward -- with no database or transport dependency.

Ported from the prototype's ``project_store._save_normalized``. The persistence
mechanics live in ``aia_core.infrastructure.repositories``; the rules live here so
they can be tested without a database and reused by the worker.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .pipeline import (
    ImpactPreview,
    ProjectType,
    StageStatus,
    changed_fields,
    fingerprint,
    impact_preview,
    stage_ids,
    stage_labels,
)
from .providers import (
    DEFAULT_MAX_API_COST_USD,
    Provider,
    ProviderPolicy,
    normalize_policy,
    normalize_provider,
    policy_for_provider,
)

__all__ = [
    "Project",
    "ProjectRevision",
    "ProjectStatus",
    "SaveOutcome",
    "StageState",
    "carry_forward_stages",
    "initial_stages",
    "new_project_id",
    "new_revision_id",
    "plan_save",
]


class ProjectStatus(StrEnum):
    """Lifecycle status of a project as a whole."""

    DRAFT = "DRAFT"
    READY_TO_CONTINUE = "READY_TO_CONTINUE"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"
    TRASHED = "TRASHED"


def new_project_id() -> str:
    """Return a new project id.

    The ``PRJ-`` prefix and 14 hex characters match the prototype's format so that
    ids remain recognisable to operators and comparable against legacy exports.
    """
    return "PRJ-" + uuid4().hex[:14]


def new_revision_id() -> str:
    """Return a new opaque revision id (distinct from the per-project counter)."""
    return "REV-" + uuid4().hex[:16]


class StageState(BaseModel):
    """One stage within one immutable project revision.

    ``input_fingerprint`` is what makes artifact reuse safe: a stage's artifacts may
    be reused only when the fingerprint of the current inputs matches the one
    recorded when those artifacts were produced.
    """

    model_config = ConfigDict(extra="forbid")

    stage_type: str
    ordinal: int
    status: StageStatus = StageStatus.NOT_STARTED
    label: str = ""
    input_fingerprint: str = ""
    provider: Provider | None = None
    model: str = ""
    current_job_id: str | None = None
    last_checkpoint: str | None = None
    waiting_reason: str | None = None
    quota_reset_at: datetime | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        """True when this stage's artifacts may be carried into a new revision."""
        return self.status.is_complete

    def carried_forward(self) -> Self:
        """Return a copy for a new revision, preserving completed work.

        Live execution pointers are deliberately dropped: ``current_job_id`` belongs
        to the revision that ran it, and a waiting reason from the old revision must
        not make the new revision look parked.
        """
        return self.model_copy(
            update={
                "current_job_id": None,
                "waiting_reason": None,
                "quota_reset_at": None,
            }
        )


class ProjectRevision(BaseModel):
    """An immutable snapshot of project content.

    ``content_sha256`` is the deduplication key: an autosave whose normalised
    content hashes to the current revision's hash creates no new revision.
    """

    model_config = ConfigDict(extra="forbid")

    revision: int
    revision_id: str = Field(default_factory=new_revision_id)
    parent_revision: int | None = None
    content_sha256: str
    content: dict[str, Any]
    reason: str = "autosave"
    created_at: datetime | None = None
    changed_fields: list[str] = Field(default_factory=list)
    panel_version: str = ""
    model: str = ""

    @field_validator("revision")
    @classmethod
    def _revision_is_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("revision numbering starts at 1")
        return v


class Project(BaseModel):
    """A durable research or simulation workspace."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(default_factory=new_project_id)
    title: str
    project_type: ProjectType = ProjectType.RESEARCH
    status: ProjectStatus = ProjectStatus.DRAFT
    current_revision: int = 0
    current_stage: str = ""
    last_completed_stage: str | None = None
    parent_project_id: str | None = None
    preferred_provider: Provider = Provider.CLAUDE_CODE
    provider_policy: ProviderPolicy = ProviderPolicy.CLAUDE_CODE_ONLY
    max_api_cost_usd: float = DEFAULT_MAX_API_COST_USD
    runtime_version: str = ""
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    archived: bool = False
    created_at: datetime | None = None
    modified_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        title = (v or "").strip()
        if not title:
            raise ValueError("project title must not be empty")
        return title

    @field_validator("max_api_cost_usd")
    @classmethod
    def _budget_not_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("max_api_cost_usd must not be negative")
        return float(v)

    @property
    def stage_ids(self) -> list[str]:
        """Ordered stage ids for this project's pipeline."""
        return stage_ids(self.project_type)

    def default_title(self) -> str:
        """Czech default title matching the prototype's wording."""
        return "Nová simulace" if self.project_type is ProjectType.SIMULATION else "Nový výzkum"


def initial_stages(project_type: Any) -> list[StageState]:
    """Return the full NOT_STARTED stage list for a new revision."""
    labels = stage_labels(project_type)
    return [
        StageState(stage_type=sid, ordinal=i, label=labels[sid], status=StageStatus.NOT_STARTED)
        for i, sid in enumerate(stage_ids(project_type))
    ]


def resolve_provider_defaults(
    *, preferred_provider: Any, provider_policy: Any
) -> tuple[Provider, ProviderPolicy]:
    """Return a coherent (provider, policy) pair for a new project.

    When the caller picks a non-default provider but leaves the policy at its
    default, the policy is widened to match the provider -- otherwise the project
    would be pinned to a runtime the user did not choose. Matches the prototype's
    ``create_project``.
    """
    provider = normalize_provider(preferred_provider)
    raw_policy = str(provider_policy or "").strip().upper()

    if raw_policy in ("", ProviderPolicy.CLAUDE_CODE_ONLY) and provider is not Provider.CLAUDE_CODE:
        return provider, policy_for_provider(provider)

    return provider, normalize_policy(provider_policy)


def carry_forward_stages(
    *,
    previous: list[StageState],
    project_type: Any,
    impact: ImpactPreview,
) -> list[StageState]:
    """Build the new revision's stages, reusing completed upstream work.

    This is the core cross-revision no-recompute rule. A stage is carried forward
    only when both conditions hold:

    * the impact analysis places it upstream of the change (``impact.preserve``);
    * it actually completed in the previous revision (DONE / DONE_WITH_WARNINGS).

    The root stage becomes READY so the pipeline resumes exactly there, and
    everything downstream of it starts NOT_STARTED.
    """
    labels = stage_labels(project_type)
    prior = {s.stage_type: s for s in previous}
    preserve = set(impact.preserve)
    fresh = initial_stages(project_type)

    stages: list[StageState] = []
    for stage in fresh:
        sid = stage.stage_type
        old = prior.get(sid)

        if sid in preserve and old is not None and old.is_complete:
            carried = old.carried_forward()
            # Ordinal and label follow the current pipeline definition, not the
            # stored copy, so a pipeline reordering cannot corrupt a new revision.
            stages.append(
                carried.model_copy(update={"ordinal": stage.ordinal, "label": labels[sid]})
            )
        elif sid == impact.root_stage:
            stages.append(stage.model_copy(update={"status": StageStatus.READY}))
        else:
            stages.append(stage)

    return stages


class SaveOutcome(BaseModel):
    """Result of planning a project save.

    When ``deduplicated`` is true the content was byte-identical to the current
    revision: no revision was created and ``revision`` still points at the existing
    one. Callers should touch ``modified_at`` and stop.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    project_id: str
    revision: int
    revision_id: str | None = None
    deduplicated: bool = False
    content_sha256: str
    changed_fields: list[str] = Field(default_factory=list)
    impact: dict[str, Any] = Field(default_factory=dict)
    stages: list[StageState] = Field(default_factory=list)
    root_stage: str | None = None
    project_status: ProjectStatus = ProjectStatus.DRAFT
    current_stage: str = ""
    last_completed_stage: str | None = None


def plan_save(
    *,
    project: Project,
    content: dict[str, Any],
    previous_content: dict[str, Any] | None,
    previous_stages: list[StageState] | None,
    reason: str = "autosave",
    force_new_revision: bool = False,
    explicit_stage: str | None = None,
) -> SaveOutcome:
    """Decide what a save does, without performing any I/O.

    The rules, in order:

    1. Content identical to the current revision and no force flag -> deduplicate.
    2. Otherwise a new immutable revision is created at ``current_revision + 1``.
    3. Changed top-level fields determine the impact root.
    4. Completed stages upstream of the root carry forward; the root becomes READY.
    5. With no material change (e.g. a provider switch), every completed stage is
       preserved and the project points at the last completed stage.

    ``explicit_stage`` lets a user force a rerun from a chosen stage even when the
    content did not change there.
    """
    content = content or {}
    content_hash = fingerprint(content)
    is_first = project.current_revision < 1 or previous_content is None

    if (
        not is_first
        and not force_new_revision
        and explicit_stage is None
        and content_hash == fingerprint(previous_content)
    ):
        return SaveOutcome(
            project_id=project.project_id,
            revision=project.current_revision,
            deduplicated=True,
            content_sha256=content_hash,
            project_status=project.status,
            current_stage=project.current_stage,
            last_completed_stage=project.last_completed_stage,
        )

    ids = stage_ids(project.project_type)
    revision = project.current_revision + 1 if not is_first else 1

    if is_first:
        return SaveOutcome(
            project_id=project.project_id,
            revision=revision,
            revision_id=new_revision_id(),
            deduplicated=False,
            content_sha256=content_hash,
            changed_fields=[],
            impact=ImpactPreview(
                root_stage=None, invalidate=[], preserve=list(ids), presentation_only=False
            ).as_dict(),
            stages=initial_stages(project.project_type),
            root_stage=None,
            project_status=ProjectStatus.DRAFT,
            current_stage=ids[0],
            last_completed_stage=None,
        )

    changed = changed_fields(previous_content, content)
    impact = impact_preview(project.project_type, changed, explicit_stage=explicit_stage)
    stages = carry_forward_stages(
        previous=previous_stages or [],
        project_type=project.project_type,
        impact=impact,
    )

    completed = [s.stage_type for s in stages if s.is_complete]
    last_completed = completed[-1] if completed else None

    if impact.root_stage:
        current_stage = impact.root_stage
        status = ProjectStatus.READY_TO_CONTINUE
    elif last_completed:
        # A metadata / provider / report-preference edit with no data impact keeps
        # every completed stage and leaves the project where it already stood.
        current_stage = last_completed
        status = ProjectStatus.READY_TO_CONTINUE
    else:
        current_stage = ids[0]
        status = project.status

    return SaveOutcome(
        project_id=project.project_id,
        revision=revision,
        revision_id=new_revision_id(),
        deduplicated=False,
        content_sha256=content_hash,
        changed_fields=changed,
        impact=impact.as_dict(),
        stages=stages,
        root_stage=impact.root_stage,
        project_status=status,
        current_stage=current_stage,
        last_completed_stage=last_completed,
    )
