"""Settings → AI běh: each activity's last answered call (settings-redesign F14, OI-75 (a)).

``GET /settings/ai-activity``: for every native AI activity the settings document lists, when it
last answered, on which model and by which build, from the usage ledger's newest ``SUCCEEDED``
call of it across the organization; ``last_answered: null`` where none is recorded, which says
nothing about whether it would answer now. No client, study, person, text or cost.

OWNER and ADMIN only, refused 403 ``insufficient_role``. Read-only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aia_core.application.ai_activity import last_answered_by_activity
from aia_core.domain.ai_activity import RuntimeActivity
from aia_core.domain.scope import ScopeDenied
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import OrganizationDep, SessionDep
from ..schemas.projects import ErrorResponse

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "Not an organization OWNER or ADMIN"},
    404: {"model": ErrorResponse, "description": "Not a member of the organization"},
}

router = APIRouter(prefix="/settings", tags=["settings"], responses=_RESPONSES)


class LastAnsweredOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at: datetime
    #: The model that served the call where the provider said, else the one asked.
    model: str
    #: The worker's build that made it; ``null``: it recorded none, never a guess.
    build: str | None


class ActivityAnsweredOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: RuntimeActivity
    #: ``null``: no answered call recorded, which is not "working" and not "broken".
    last_answered: LastAnsweredOut | None


class AiActivityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activities: list[ActivityAnsweredOut]


@router.get(
    "/ai-activity",
    response_model=AiActivityResponse,
    summary="Each AI activity's last answered call",
)
def get_ai_activity(scope: OrganizationDep, session: SessionDep) -> AiActivityResponse:
    try:
        answered = last_answered_by_activity(session, scope)
    except ScopeDenied as exc:
        if exc.reason != "insufficient_role":
            raise
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "insufficient_role",
                "message": "Each activity's last answered call is read by an OWNER or ADMIN.",
                "details": {"reason": exc.reason},
            },
        ) from exc
    return AiActivityResponse(
        activities=[
            ActivityAnsweredOut(
                key=activity,
                last_answered=None
                if (last := answered.get(activity)) is None
                else LastAnsweredOut(at=last.at, model=last.model, build=last.build),
            )
            for activity in RuntimeActivity
        ]
    )
