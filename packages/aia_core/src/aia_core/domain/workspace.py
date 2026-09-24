"""The study workspace bridge: which unit project holds a study's working content.

ADR 0015 decision 5, open item OI-58. **Temporary migration debt.** The research
stages rebuilt in React still keep their working content in the 18.6.6 unit's
single-tenant project store. A :class:`StudyWorkspace` is the AIA-owned binding
from a study -- canonical for scope, identity, lifecycle, permissions, costs,
approvals, provenance and artifacts -- to that unit project. It is read and
written only under an issued ``StudyContext``; a unit project id is never a way
into a study. It goes when stage state moves into AIA's own study-scoped
storage, and nothing may treat the unit store as the target data model.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict

__all__ = ["STAGE_KEYS", "UNIT_PROJECT_ID", "StudyWorkspace", "UnitProjectId"]

# The unit's project ids (PRJ-… and the like): the pattern the web client's
# hand-off already accepts, so nothing longer or stranger is ever stored.
UNIT_PROJECT_ID: Final = re.compile(r"^[A-Za-z0-9_-]{1,160}$")

# The research stages the client-first frame knows (apps/web/src/unit/research/steps.ts).
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


def _unit_project_id(value: str) -> str:
    if not UNIT_PROJECT_ID.fullmatch(value):
        raise ValueError("not a unit project id")
    return value


UnitProjectId = Annotated[str, AfterValidator(_unit_project_id)]


class StudyWorkspace(BaseModel):
    """The unit project bound to a study, and the stage it was last opened on."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    study_id: str
    unit_project_id: UnitProjectId
    last_stage: str | None = None
    bound_at: datetime | None = None
    modified_at: datetime | None = None
