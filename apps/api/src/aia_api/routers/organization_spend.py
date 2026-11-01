"""The organization's spend, Settings → Studie a rozpočty (``develop-spend-attribution`` 6,
settings-backends SB3).

``GET /settings/organization-spend?period=this_month|last_month|year_to_date``: what the
organization spent over the period (model calls and tools apart), what is held open now, the
calls whose bill is not known, and the open studies whose budget is at least 90 % spent or held.
OWNER and ADMIN only, refused 403 ``insufficient_role`` before any row is read. Read-only;
months are UTC.

The figures are folded by the same rules as per-researcher spend, so a person's rows and the
organization's total never disagree. ``uncertain_calls`` above zero means the total is not known
to the cent; it is never folded into a zero.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from aia_core.application.organization_spend import organization_spend_report
from aia_core.domain.scope import ScopeDenied
from aia_core.domain.spend_attribution import (
    NEAR_LIMIT_SHARE,
    ActivitySpend,
    SpendActivity,
    SpendPeriod,
)
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import OrganizationDep, SessionDep
from ..schemas.projects import ErrorResponse

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "Not an organization OWNER or ADMIN"},
    404: {"model": ErrorResponse, "description": "Not a member of the organization"},
}

router = APIRouter(prefix="/settings", tags=["settings"], responses=_RESPONSES)


class ActivityTotalOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity: SpendActivity
    model_usd: float
    tools_usd: float
    spent_usd: float
    reserved_usd: float
    uncertain_calls: int


class NearLimitOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str
    study_name: str
    client_id: str
    client_name: str
    budget_usd: float
    #: Spent plus held open now: what the budget can no longer give.
    used_usd: float
    spent_usd: float
    held_usd: float
    #: ``used_usd / budget_usd``; at least 0.9, above 1 when an overrun was booked.
    share: float


class OrganizationSpendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: SpendPeriod
    start: datetime
    end: datetime
    currency: str = "USD"
    #: Model calls (the usage ledger) plus tools (holds settled outside it), in the period.
    spent_usd: float
    model_usd: float
    tools_usd: float
    #: Held open now, whatever the period: not spent yet.
    reserved_usd: float
    uncertain_calls: int
    by_activity: list[ActivityTotalOut]
    near_limit: list[NearLimitOut]
    #: The share from which a study is listed (the product owner, 2026-10-22).
    near_limit_share: float = NEAR_LIMIT_SHARE


def _activities(by: dict[SpendActivity, ActivitySpend]) -> list[ActivityTotalOut]:
    """Every activity, in one order, a missing one at a known zero (no row: nothing spent)."""
    out = []
    for activity in SpendActivity:
        a = by.get(activity, ActivitySpend())
        out.append(
            ActivityTotalOut(
                activity=activity,
                model_usd=a.model_usd,
                tools_usd=a.outside_ledger_usd,
                spent_usd=a.total_usd,
                reserved_usd=a.reserved_usd,
                uncertain_calls=a.uncertain_calls,
            )
        )
    return out


@router.get(
    "/organization-spend",
    response_model=OrganizationSpendResponse,
    summary="The organization's spend and the studies near their budget",
)
def get_organization_spend(
    scope: OrganizationDep,
    session: SessionDep,
    period: Annotated[SpendPeriod, Query()] = SpendPeriod.THIS_MONTH,
) -> OrganizationSpendResponse:
    """The organization's spend over ``period`` and its open studies at 90 % of their budget
    or more. OWNER or ADMIN."""
    try:
        report = organization_spend_report(session, scope, period)
    except ScopeDenied as exc:
        if exc.reason != "insufficient_role":
            raise
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "insufficient_role",
                "message": "The organization's spend is read by an OWNER or ADMIN.",
                "details": {"reason": exc.reason},
            },
        ) from exc
    total = report.total
    return OrganizationSpendResponse(
        period=report.period,
        start=report.start,
        end=report.end,
        spent_usd=total.total_usd,
        model_usd=total.model_usd,
        tools_usd=total.outside_ledger_usd,
        reserved_usd=total.reserved_usd,
        uncertain_calls=total.uncertain_calls,
        by_activity=_activities(report.by_activity),
        near_limit=[
            NearLimitOut(
                study_id=n.study.study_id,
                study_name=n.study.study_name,
                client_id=n.study.client_id,
                client_name=n.study.client_name,
                budget_usd=n.study.budget_usd,
                used_usd=n.used_usd,
                spent_usd=n.study.spent_usd,
                held_usd=n.study.held_usd,
                share=n.share,
            )
            for n in report.near_limit
        ],
    )
