"""Per-researcher spend, read (``develop-spend-attribution`` 7, Q40).

The content-free rows a person's spend is made of: usage-ledger rows and budget holds, each with
the person it is booked to (``charged_to_user_id``) and the run and step it was for, so the
domain can say which activity it was (``domain/spend_attribution.py``). Nothing here reads a
prompt, an answer or a document.

**The scope is in the query.** An organization OWNER or ADMIN reads every row of the
organization, the unattributed ones included; anyone else reads only the rows booked to
themself (``charged_to_user_id = actor``), so another person's spend is never loaded, not
loaded and filtered afterwards. The organization is in every query: a usage row by its own
column, a hold by its client's.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, exists, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from ..domain.scope import OrganizationContext, StudyStatus
from ..domain.spend_attribution import HoldFact, UsageFact, activity_of
from ..domain.workflow import ReservationStatus
from .tables import (
    AIUsageEventRow,
    BudgetReservationRow,
    ClientRow,
    OrganizationMemberRow,
    StepRunRow,
    StudyRow,
    UserRow,
    WorkflowRunRow,
    as_utc,
)

__all__ = [
    "Person",
    "ResearcherSpendRepository",
    "StudyBudget",
    "StudyName",
    "hold_facts",
    "run_spend_facts",
    "usage_facts",
]


@dataclass(frozen=True, slots=True)
class Person:
    """Who a row of spend names, as Settings shows them."""

    user_id: str
    email: str
    display_name: str
    is_member: bool


@dataclass(frozen=True, slots=True)
class StudyName:
    study_id: str
    name: str
    client_id: str


@dataclass(frozen=True, slots=True)
class StudyBudget:
    """A study's budget position now: its budget, what it has spent and what is held open."""

    study_id: str
    study_name: str
    client_id: str
    client_name: str
    budget_usd: float
    spent_usd: float
    held_usd: float


class ResearcherSpendRepository:
    """Read-only. Every query is in the organization, and for a non-administrator, the caller's
    own rows only."""

    def __init__(self, session: Session, scope: OrganizationContext) -> None:
        if not isinstance(scope, OrganizationContext):
            raise TypeError("ResearcherSpendRepository requires an issued OrganizationContext")
        self._session = session
        self._scope = scope

    @property
    def everyone(self) -> bool:
        """True when the caller reads every person's spend (OWNER or ADMIN, Q40)."""
        return self._scope.may_administer

    def _booked(self, column: InstrumentedAttribute[str | None]) -> tuple[ColumnElement[bool], ...]:
        return () if self.everyone else (column == self._scope.actor_id,)

    def usage(self, *, since: datetime) -> list[UsageFact]:
        """Every usage row of the organization that occurred at or after ``since``: the later
        rows of a call dispatched in a period too, so its uncertainty is judged on all of
        them."""
        return usage_facts(
            self._session,
            AIUsageEventRow.organization_id == self._scope.organization_id,
            AIUsageEventRow.occurred_at >= since,
            *self._booked(AIUsageEventRow.charged_to_user_id),
        )

    def holds(self, *, since: datetime) -> list[HoldFact]:
        """The organization's holds open now, and those settled at or after ``since``."""
        return hold_facts(
            self._session,
            ClientRow.organization_id == self._scope.organization_id,
            or_(
                BudgetReservationRow.status == ReservationStatus.RESERVED.value,
                BudgetReservationRow.settled_at >= since,
            ),
            *self._booked(BudgetReservationRow.charged_to_user_id),
        )

    def people(self, booked: Collection[str]) -> list[Person]:
        """Who is listed: for an administrator every member of the organization and anyone
        else ``booked`` names (a person who has since left); for anyone else themself."""
        members = set(
            self._session.scalars(
                select(OrganizationMemberRow.user_id).where(
                    OrganizationMemberRow.organization_id == self._scope.organization_id
                )
            )
        )
        wanted = (members | set(booked)) if self.everyone else {self._scope.actor_id}
        rows = self._session.execute(
            select(UserRow.user_id, UserRow.email, UserRow.display_name).where(
                UserRow.user_id.in_(sorted(wanted))
            )
        ).all()
        known = {str(u): (str(e), str(n or "")) for u, e, n in rows}
        return [
            Person(
                user_id=user,
                email=known.get(user, ("", ""))[0],
                display_name=known.get(user, ("", ""))[1],
                is_member=user in members,
            )
            for user in sorted(wanted)
        ]

    def study_budgets(self) -> list[StudyBudget]:
        """Every open study of the organization with a budget set, its spend and its open
        holds; an OWNER or ADMIN only (a budget near its limit is the organization's view).
        A delivered, archived or cancelled study takes no new work, so it is not listed."""
        self._scope.require_administer()
        open_statuses = [s.value for s in StudyStatus if s.accepts_work]
        held = (
            select(
                BudgetReservationRow.study_id.label("study_id"),
                func.sum(BudgetReservationRow.amount_usd).label("held"),
            )
            .where(BudgetReservationRow.status == ReservationStatus.RESERVED.value)
            .group_by(BudgetReservationRow.study_id)
            .subquery()
        )
        rows = self._session.execute(
            select(
                StudyRow.study_id,
                StudyRow.name,
                StudyRow.client_id,
                ClientRow.name,
                StudyRow.budget_usd,
                StudyRow.spent_usd,
                held.c.held,
            )
            .join(ClientRow, ClientRow.client_id == StudyRow.client_id)
            .outerjoin(held, held.c.study_id == StudyRow.study_id)
            .where(
                StudyRow.organization_id == self._scope.organization_id,
                ClientRow.organization_id == self._scope.organization_id,
                StudyRow.status.in_(open_statuses),
                StudyRow.budget_usd > 0,
            )
        ).all()
        budgets: list[StudyBudget] = []
        for row in rows:
            m = row._mapping
            budgets.append(
                StudyBudget(
                    study_id=str(m[StudyRow.study_id]),
                    study_name=str(m[StudyRow.name]),
                    client_id=str(m[StudyRow.client_id]),
                    client_name=str(m[ClientRow.name]),
                    budget_usd=float(m[StudyRow.budget_usd]),
                    spent_usd=float(m[StudyRow.spent_usd]),
                    held_usd=float(m["held"] or 0.0),
                )
            )
        return budgets

    def study_names(self, study_ids: Collection[str]) -> dict[str, StudyName]:
        """The organization's studies among ``study_ids``, by id."""
        if not study_ids:
            return {}
        rows = self._session.execute(
            select(StudyRow.study_id, StudyRow.name, StudyRow.client_id).where(
                StudyRow.organization_id == self._scope.organization_id,
                StudyRow.study_id.in_(sorted(study_ids)),
            )
        ).all()
        return {str(s): StudyName(str(s), str(n), str(c)) for s, n, c in rows}

    def client_names(self, client_ids: Collection[str]) -> dict[str, str]:
        """The organization's clients among ``client_ids``, by id."""
        if not client_ids:
            return {}
        rows = self._session.execute(
            select(ClientRow.client_id, ClientRow.name).where(
                ClientRow.organization_id == self._scope.organization_id,
                ClientRow.client_id.in_(sorted(client_ids)),
            )
        ).all()
        return {str(c): str(n) for c, n in rows}


def usage_facts(session: Session, *where: ColumnElement[bool]) -> list[UsageFact]:
    """The usage-ledger rows ``where`` selects, each with its run's activity."""
    rows = session.execute(
        select(
            AIUsageEventRow.call_id,
            AIUsageEventRow.outcome,
            AIUsageEventRow.cost_usd,
            AIUsageEventRow.charged_to_user_id,
            AIUsageEventRow.client_id,
            AIUsageEventRow.study_id,
            AIUsageEventRow.occurred_at,
            WorkflowRunRow.workflow_type,
            StepRunRow.stage_type,
        )
        .outerjoin(WorkflowRunRow, WorkflowRunRow.run_id == AIUsageEventRow.run_id)
        .outerjoin(StepRunRow, StepRunRow.step_id == AIUsageEventRow.step_id)
        .where(*where)
    ).all()
    facts: list[UsageFact] = []
    for call, outcome, cost, person, client, study, at, workflow, stage in rows:
        occurred = as_utc(at)
        assert occurred is not None  # non-nullable column
        facts.append(
            UsageFact(
                call_id=str(call),
                outcome=str(outcome),
                cost_usd=float(cost),
                charged_to=person,
                client_id=str(client),
                study_id=study,
                activity=activity_of(workflow, stage),
                occurred_at=occurred,
            )
        )
    return facts


def hold_facts(session: Session, *where: ColumnElement[bool]) -> list[HoldFact]:
    """The budget holds ``where`` selects (their client joined), each with whether a ledger row
    names it and its run's activity."""
    in_ledger = exists().where(
        AIUsageEventRow.reservation_id == BudgetReservationRow.reservation_id
    )
    rows = session.execute(
        select(
            BudgetReservationRow.reservation_id,
            BudgetReservationRow.status,
            BudgetReservationRow.amount_usd,
            BudgetReservationRow.settled_amount_usd,
            BudgetReservationRow.charged_to_user_id,
            BudgetReservationRow.client_id,
            BudgetReservationRow.study_id,
            BudgetReservationRow.settled_at,
            in_ledger.label("in_ledger"),
            WorkflowRunRow.workflow_type,
            StepRunRow.stage_type,
        )
        .join(ClientRow, ClientRow.client_id == BudgetReservationRow.client_id)
        .outerjoin(WorkflowRunRow, WorkflowRunRow.run_id == BudgetReservationRow.run_id)
        .outerjoin(StepRunRow, StepRunRow.step_id == BudgetReservationRow.step_id)
        .where(*where)
    ).all()
    facts: list[HoldFact] = []
    for row in rows:
        m = row._mapping
        settled_at = m[BudgetReservationRow.settled_at]
        facts.append(
            HoldFact(
                reservation_id=str(m[BudgetReservationRow.reservation_id]),
                status=str(m[BudgetReservationRow.status]),
                amount_usd=float(m[BudgetReservationRow.amount_usd]),
                settled_amount_usd=float(m[BudgetReservationRow.settled_amount_usd] or 0.0),
                charged_to=m[BudgetReservationRow.charged_to_user_id],
                client_id=str(m[BudgetReservationRow.client_id]),
                study_id=m[BudgetReservationRow.study_id],
                activity=activity_of(m[WorkflowRunRow.workflow_type], m[StepRunRow.stage_type]),
                in_ledger=bool(m["in_ledger"]),
                settled_at=as_utc(settled_at) if settled_at is not None else None,
            )
        )
    return facts


def run_spend_facts(
    session: Session, *, organization_id: str, study_id: str, run_id: str
) -> tuple[list[UsageFact], list[HoldFact]]:
    """Every usage row and hold of one run, whoever it is booked to: a run's spend is the
    study's, which every member who can open the study reads (ADR 0019). The caller has found
    the run through the study; the organization and study are in the query as well."""
    return (
        usage_facts(
            session,
            AIUsageEventRow.organization_id == organization_id,
            AIUsageEventRow.study_id == study_id,
            AIUsageEventRow.run_id == run_id,
        ),
        hold_facts(
            session,
            ClientRow.organization_id == organization_id,
            BudgetReservationRow.study_id == study_id,
            BudgetReservationRow.run_id == run_id,
        ),
    )
