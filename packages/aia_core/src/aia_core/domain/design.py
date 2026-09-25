"""The Design Revision: the research design a run executes (ADR 0016 decision 1).

A research Study's design is written by the researcher in the rebuilt stages and,
until OI-58, edited in the unit's store. What *runs* is never that working copy:
the browser submits the design it holds, AIA checks it against the authenticated
Study and stores it as an immutable revision of the Study's own design project.
A run then names one revision by id and executes exactly that content.

The browser supplies content, never authority. Nothing in a design can widen
scope: identity comes from the issued ``StudyContext``, and a design that carries
scope-looking keys at its top level is refused rather than trusted or stripped.
Pure: no I/O.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Final

from pydantic import BaseModel, ConfigDict

__all__ = [
    "DESIGN_MAX_BYTES",
    "DESIGN_PROJECT_OWNER",
    "DESIGN_SOURCE_STAGES",
    "DesignRejected",
    "DesignRevision",
    "validate_design",
]

#: ``projects.owner`` of a Study's design project. A project with an owner is
#: invisible to a repository that does not name it, so only the design repository
#: can write the content a run executes (ADR 0016 decision 1).
DESIGN_PROJECT_OWNER: Final = "study_design"

#: A design is a questionnaire, an audience and choices: kilobytes, not megabytes.
#: The cap is generous and exists so that a submission cannot become a dump of
#: working state (attachments, AI transcripts) into an immutable table.
DESIGN_MAX_BYTES: Final = 2 * 1024 * 1024

#: The stage a design was submitted from, for provenance. The rebuilt stage keys
#: (``apps/web/src/unit/research/steps.ts``); ``run`` is where a run starts.
DESIGN_SOURCE_STAGES: Final = frozenset(
    {"brief", "plan", "questionnaire", "audience", "persona", "run"}
)

# Top-level keys that would let submitted content pose as identity or scope. The
# design's own ``id``/``project_id`` from the unit's store are harmless data, but
# a key naming AIA scope is refused: content must never look like authority.
_SCOPE_KEYS: Final = frozenset(
    {"organization_id", "client_id", "study_id", "tenant_id", "actor_id", "design_revision_id"}
)


class DesignRejected(ValueError):
    """The submitted content cannot become a Design Revision."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def validate_design(content: Any) -> dict[str, Any]:
    """Return the design as a plain object, or raise :class:`DesignRejected`.

    Checks what AIA can know without interpreting methodology: the shape (a JSON
    object), the size, and that no top-level key poses as scope. Readiness --
    whether the design is complete enough to run -- is the preflight step's
    question, not the ingestion's: an incomplete design is still a design.
    """
    if not isinstance(content, dict):
        raise DesignRejected("a design is a JSON object", reason="design_not_object")
    if not content:
        raise DesignRejected("the design is empty", reason="design_empty")
    posing = sorted(k for k in content if str(k).lower() in _SCOPE_KEYS)
    if posing:
        raise DesignRejected(
            f"a design may not carry scope keys: {', '.join(posing)}",
            reason="design_carries_scope",
        )
    try:
        text = json.dumps(
            content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        size = len(text.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise DesignRejected("the design is not plain JSON", reason="design_not_json") from exc
    if size > DESIGN_MAX_BYTES:
        raise DesignRejected(
            f"the design is {size} bytes; the limit is {DESIGN_MAX_BYTES}",
            reason="design_too_large",
        )
    return dict(content)


class DesignRevision(BaseModel):
    """One immutable revision of a Study's research design."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The Design Revision ID a run names (``REV-…``, the project revision's id).
    revision_id: str
    study_id: str
    #: 1, 2, 3 … within the Study's design; the order edits were submitted in.
    revision: int
    content_sha256: str
    #: The revision this one was edited from, or ``None`` for the first.
    parent_revision: int | None
    #: Provenance: the stage the design was submitted from, who, and when.
    source_stage: str
    created_by: str | None
    created_at: datetime
