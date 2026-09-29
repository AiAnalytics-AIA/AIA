"""A research Study's working content: what its stages edit, kept in AIA.

ADR 0018, open item OI-58. The research stages edit one document per Study -- the
brief, the plan, the questionnaire, the audience, the dimensions -- and save it
every few seconds. Until ADR 0018 that document lived in the 18.6.6 unit's
single-tenant project store, reached through an AIA-owned binding. It now lives in
AIA: the Study's *working project* (``projects.owner = study_workspace``), whose
immutable revisions are the saves, found only through the Study's
``study_workspaces`` row.

The working copy is not what a run executes. A run executes a Design Revision the
browser submits from it (ADR 0016); the working project only keeps the edits, their
history and, for a Study whose content came from 18.6.6, where it came from.

A Study's content is always in exactly one :class:`ContentState`, and the state says
so by name. In particular a Study bound to an 18.6.6 project that has not been
migrated is ``AWAITING_MIGRATION`` -- not empty, and not editable, because a fresh
edit would fork what the migration will bring -- and a Study whose 18.6.6 project is
gone with nothing recoverable is ``UNRECOVERABLE``, never an empty stand-in.

Pure: no I/O.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

__all__ = [
    "LEGACY_SOURCE",
    "SAVE_REASON",
    "STAGE_KEYS",
    "UNIT_PROJECT_ID",
    "WORKING_CONTENT_MAX_BYTES",
    "WORKSPACE_PROJECT_OWNER",
    "ContentState",
    "StudyWorkspace",
    "UnitProjectId",
    "WorkingContent",
    "WorkingRevision",
    "WorkingSave",
    "WorkspaceRejected",
    "validate_working_content",
]

#: ``projects.owner`` of a Study's working project. As with the design project
#: (``study_design``), a project with an owner is invisible to every repository that
#: does not name it, so no generic project route can read or write a Study's
#: working content around the Study's scope.
WORKSPACE_PROJECT_OWNER: Final = "study_workspace"

#: What migrated content came from. Recorded in lineage, never compared with
#: anything a caller sends.
LEGACY_SOURCE: Final = "npc-panel-18.6.6"

#: The 18.6.6 unit's project ids (``PRJ-…`` and the like). Kept only as lineage:
#: the id a Study's content was migrated from, never a way to find a Study.
UNIT_PROJECT_ID: Final = re.compile(r"^[A-Za-z0-9_-]{1,160}$")

#: A save's reason, as the stages give it (``autosave``, ``brief_attachments``,
#: ``ai_analysis_1780`` …): provenance of one revision, short and plain.
SAVE_REASON: Final = re.compile(r"^[a-z0-9_:.-]{1,64}$")

#: The whole saved document -- content and analysis together -- is capped at the
#: API's ordinary request ceiling. Attachment bytes are stored separately; only
#: their records and text excerpts travel with the content.
WORKING_CONTENT_MAX_BYTES: Final = 2 * 1024 * 1024

# The research stages the client-first frame knows (apps/web/src/research/steps.ts).
STAGE_KEYS: Final = frozenset(
    {
        "brief",
        "plan",
        "questionnaire",
        "audience",
        "persona",
        "run",
        "progress",
        "results",
        "verify",
        "next",
    }
)

# Top-level keys that would let saved content pose as identity or scope, refused
# exactly as a Design Revision refuses them (``design.validate_design``). The
# 18.6.6 document's own ``id``/``project_id`` are harmless data.
_SCOPE_KEYS: Final = frozenset(
    {"organization_id", "client_id", "study_id", "tenant_id", "actor_id", "design_revision_id"}
)


class ContentState(StrEnum):
    """Where a Study's working content stands. One per Study, always named."""

    #: Nothing saved yet: a new Study. The stages start from the research template.
    EMPTY = "EMPTY"
    #: Saved in AIA.
    NATIVE = "NATIVE"
    #: Brought from the 18.6.6 unit's project store by the migration, with lineage.
    MIGRATED = "MIGRATED"
    #: The bound 18.6.6 project no longer existed; the content was recovered from
    #: the newest Design Revision the Study had submitted, with lineage.
    RECOVERED = "RECOVERED"
    #: The bound 18.6.6 project no longer existed and nothing recoverable did.
    #: Starting again is an explicit act of a person who may edit the Study.
    UNRECOVERABLE = "UNRECOVERABLE"
    #: Bound to an 18.6.6 project that has not been migrated yet. Not editable:
    #: an edit now would fork the content the migration brings.
    AWAITING_MIGRATION = "AWAITING_MIGRATION"

    @property
    def has_content(self) -> bool:
        """True when a working project holds the Study's content."""
        return self in (ContentState.NATIVE, ContentState.MIGRATED, ContentState.RECOVERED)

    @property
    def editable(self) -> bool:
        """True when a save may be accepted (subject to the caller's permission)."""
        return self is not ContentState.AWAITING_MIGRATION


class WorkspaceRejected(ValueError):
    """The content cannot be saved as a Study's working content."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def _json_size(value: Any) -> int:
    try:
        text = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise WorkspaceRejected("the content is not plain JSON", reason="content_not_json") from exc
    return len(text.encode("utf-8"))


def validate_working_content(
    content: Any, analysis: Any = None
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return the content and the analysis as plain objects, or raise :class:`WorkspaceRejected`.

    What AIA can check without interpreting methodology: a JSON object that is not
    empty, no top-level key posing as scope, an analysis that is an object or
    nothing, and a size under :data:`WORKING_CONTENT_MAX_BYTES`. Whether the design
    is complete enough to run is readiness's question (``research_design``), not
    the save's: a half-written brief is still working content.
    """
    if not isinstance(content, dict):
        raise WorkspaceRejected("working content is a JSON object", reason="content_not_object")
    if not content:
        raise WorkspaceRejected("the working content is empty", reason="content_empty")
    posing = sorted(k for k in content if str(k).lower() in _SCOPE_KEYS)
    if posing:
        raise WorkspaceRejected(
            f"working content may not carry scope keys: {', '.join(posing)}",
            reason="content_carries_scope",
        )
    if analysis is not None and not isinstance(analysis, dict):
        raise WorkspaceRejected("an analysis is a JSON object", reason="analysis_not_object")
    size = _json_size(content) + (_json_size(analysis) if analysis is not None else 0)
    if size > WORKING_CONTENT_MAX_BYTES:
        raise WorkspaceRejected(
            f"the working content is {size} bytes; the limit is {WORKING_CONTENT_MAX_BYTES}",
            reason="content_too_large",
        )
    return dict(content), (dict(analysis) if analysis is not None else None)


def _unit_project_id(value: str) -> str:
    if not UNIT_PROJECT_ID.fullmatch(value):
        raise ValueError("not a unit project id")
    return value


UnitProjectId = Annotated[str, AfterValidator(_unit_project_id)]


class StudyWorkspace(BaseModel):
    """One Study's workspace row: its content state, its working project, its lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    study_id: str
    state: ContentState
    #: The AIA working project, once the Study has content in AIA.
    project_id: str | None = None
    #: Lineage only: the 18.6.6 project the content was (or is to be) migrated from.
    unit_project_id: UnitProjectId | None = None
    #: Migration provenance, as recorded when the content was brought over.
    lineage: dict[str, Any] = Field(default_factory=dict)
    last_stage: str | None = None
    bound_at: datetime | None = None
    modified_at: datetime | None = None


class WorkingContent(BaseModel):
    """What a stage loads: the Study's state and, when it has one, its current revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    study_id: str
    state: ContentState
    revision: int | None = None
    revision_id: str | None = None
    content: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    saved_at: datetime | None = None
    saved_by: str | None = None
    lineage: dict[str, Any] = Field(default_factory=dict)


class WorkingSave(BaseModel):
    """The outcome of one save."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    study_id: str
    state: ContentState
    revision: int
    revision_id: str
    #: True when nothing changed and no revision was written.
    deduplicated: bool


class WorkingRevision(BaseModel):
    """One saved revision of a Study's working content, for its history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    revision: int
    revision_id: str
    parent_revision: int | None
    reason: str
    content_sha256: str
    created_at: datetime
    created_by: str | None
