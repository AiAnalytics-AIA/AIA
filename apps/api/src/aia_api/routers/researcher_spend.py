"""Per-researcher spend, Settings → Studie a rozpočty, "Útrata podle výzkumníka"
(``develop-spend-attribution`` 7, Q40).

``GET /settings/researcher-spend?period=this_month|last_month|year_to_date``: each person's
spend over the period, by activity (Lead, fieldwork, analysis and report, Deep Research, other)
and by study, with the holds open now and the calls whose bill is not known. An organization
OWNER or ADMIN reads every member and what is booked to nobody; anyone else reads only
themself, enforced in the query (``ResearcherSpendRepository``). Read-only; months are UTC.

Every figure is from the content-free rows: model spend from the usage ledger, spend outside it
(tool calls) from the settled holds no ledger row names. ``uncertain_calls`` above zero means a
total is not known to the cent; it is never folded into a zero.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from aia_core.application.researcher_spend import (
    NamedPersonSpend,
    ResearcherSpendReport,
    researcher_spend_report,
)
from aia_core.domain.spend_attribution import ActivitySpend, SpendActivity, SpendPeriod
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from ..dependencies import OrganizationDep, SessionDep
from ..schemas.projects import ErrorResponse

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    404: {"model": ErrorResponse, "description": "Not a member of the organization"},
}

router = APIRouter(prefix="/settings", tags=["settings"], responses=_RESPONSES)


class ActivitySpendOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity: SpendActivity
    model_usd: float
    outside_ledger_usd: float
    total_usd: float
    reserved_usd: float
    uncertain_calls: int


class StudySpendOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: None: the client's own work, which is no study.
    study_id: str | None
    study_name: str | None
    client_id: str
    client_name: str | None
    model_usd: float
    outside_ledger_usd: float
    total_usd: float
    reserved_usd: float
    uncertain_calls: int
    by_activity: list[ActivitySpendOut]


class PersonSpendOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: None: what is booked to nobody ("nepřiřazeno"); listed for OWNER and ADMIN only.
    user_id: str | None
    email: str | None
    display_name: str | None
    #: False: a person booked spend who is no longer a member; None for the unattributed row.
    is_member: bool | None
    model_usd: float
    outside_ledger_usd: float
    total_usd: float
    reserved_usd: float
    uncertain_calls: int
    study_count: int
    by_activity: list[ActivitySpendOut]
    studies: list[StudySpendOut]


class ResearcherSpendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: SpendPeriod
    start: datetime
    end: datetime
    #: True: the caller reads everyone (OWNER or ADMIN); False: themself only.
    everyone: bool
    currency: str = "USD"
    people: list[PersonSpendOut]


def _activities(by: dict[SpendActivity, ActivitySpend]) -> list[ActivitySpendOut]:
    """Every activity, in one order, a missing one at a known zero (no row: nothing spent)."""
    out = []
    for activity in SpendActivity:
        a = by.get(activity, ActivitySpend())
        out.append(
            ActivitySpendOut(
                activity=activity,
                model_usd=a.model_usd,
                outside_ledger_usd=a.outside_ledger_usd,
                total_usd=a.total_usd,
                reserved_usd=a.reserved_usd,
                uncertain_calls=a.uncertain_calls,
            )
        )
    return out


def _person(named: NamedPersonSpend, report: ResearcherSpendReport) -> PersonSpendOut:
    spend = named.spend
    studies = [
        StudySpendOut(
            study_id=s.study_id,
            study_name=report.studies[s.study_id].name if s.study_id in report.studies else None,
            client_id=s.client_id,
            client_name=report.clients.get(s.client_id),
            model_usd=s.model_usd,
            outside_ledger_usd=s.outside_ledger_usd,
            total_usd=s.total_usd,
            reserved_usd=s.reserved_usd,
            uncertain_calls=s.uncertain_calls,
            by_activity=_activities(s.by_activity),
        )
        for s in sorted(spend.studies.values(), key=lambda s: (-s.total_usd, s.study_id or ""))
    ]
    person = named.person
    return PersonSpendOut(
        user_id=person.user_id if person else None,
        email=person.email if person else None,
        display_name=person.display_name if person else None,
        is_member=person.is_member if person else None,
        model_usd=spend.model_usd,
        outside_ledger_usd=spend.outside_ledger_usd,
        total_usd=spend.total_usd,
        reserved_usd=spend.reserved_usd,
        uncertain_calls=spend.uncertain_calls,
        study_count=spend.study_count,
        by_activity=_activities(spend.by_activity),
        studies=studies,
    )


@router.get(
    "/researcher-spend",
    response_model=ResearcherSpendResponse,
    summary="Spend per researcher (Q40)",
)
def get_researcher_spend(
    scope: OrganizationDep,
    session: SessionDep,
    period: Annotated[SpendPeriod, Query()] = SpendPeriod.THIS_MONTH,
) -> ResearcherSpendResponse:
    """Each person's spend over ``period``: everyone's for an OWNER or ADMIN, the caller's own
    for anyone else (in the query, never a full list filtered here)."""
    report = researcher_spend_report(session, scope, period)
    return ResearcherSpendResponse(
        period=report.period,
        start=report.start,
        end=report.end,
        everyone=report.everyone,
        people=[_person(n, report) for n in report.people],
    )
