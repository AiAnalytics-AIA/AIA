"""Per-researcher spend, as Settings → Studie a rozpočty shows it (``develop-spend-attribution``
7, Q40: OWNER and ADMIN see everyone, a researcher only themself).

The repository reads the content-free rows in scope; ``domain/spend_attribution.py`` folds them
into each person's spend by activity and by study; this module names the people, studies and
clients and orders the result. Read-only: nothing here writes.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..domain.scope import OrganizationContext, Permission, StudyContext
from ..domain.spend_attribution import (
    ActivitySpend,
    PersonSpend,
    SpendPeriod,
    period_bounds,
    researcher_spend,
    runs_spend,
)
from ..infrastructure.researcher_spend_repository import (
    Person,
    ResearcherSpendRepository,
    StudyName,
    run_spend_facts,
)

__all__ = [
    "NamedPersonSpend",
    "ResearcherSpendReport",
    "researcher_spend_report",
    "run_spend_of",
    "run_spends",
]


def run_spends(
    session: Session, scope: StudyContext, run_ids: Collection[str]
) -> dict[str, ActivitySpend]:
    """What each run of this Study (a research run, an agent job, a Deep Research run) has spent,
    holds open and could not settle, from the usage ledger and its holds, by the rules a person's
    spend is read (``artifact-fieldwork`` FLD4), in one read for all of them. The caller found the
    runs through this Study; the query is in the Study and organization too."""
    scope.require(Permission.VIEW_COSTS)
    usage, holds = run_spend_facts(
        session,
        organization_id=scope.organization_id,
        study_id=scope.study_id,
        run_ids=run_ids,
    )
    return runs_spend(run_ids, usage, holds)


def run_spend_of(session: Session, scope: StudyContext, run_id: str) -> ActivitySpend:
    """One run's spend, as :func:`run_spends` reads it."""
    return run_spends(session, scope, [run_id])[run_id]


@dataclass(frozen=True, slots=True)
class NamedPersonSpend:
    """One person's spend with who they are; ``person`` ``None`` is the unattributed row."""

    person: Person | None
    spend: PersonSpend


@dataclass(frozen=True, slots=True)
class ResearcherSpendReport:
    period: SpendPeriod
    start: datetime
    end: datetime
    everyone: bool
    people: list[NamedPersonSpend]
    studies: dict[str, StudyName]
    clients: dict[str, str]


def researcher_spend_report(
    session: Session,
    scope: OrganizationContext,
    period: SpendPeriod,
    *,
    now: datetime | None = None,
) -> ResearcherSpendReport:
    """The spend of every person the caller may see over ``period``: everyone's for an OWNER or
    ADMIN (and what is booked to nobody), the caller's own otherwise."""
    start, end = period_bounds(period, now or datetime.now(UTC))
    repo = ResearcherSpendRepository(session, scope)
    usage = repo.usage(since=start)
    holds = repo.holds(since=start)
    booked = {f.charged_to for f in usage if f.charged_to} | {
        h.charged_to for h in holds if h.charged_to
    }
    people = repo.people(booked)
    folded = researcher_spend(
        usage, holds, start=start, end=end, people=[p.user_id for p in people]
    )
    if not repo.everyone:
        # The query loaded only the caller's rows; this keeps the shape honest if it ever did
        # not, rather than show another person's figures.
        folded = {k: v for k, v in folded.items() if k == scope.actor_id}
    by_id = {p.user_id: p for p in people}
    listed = [
        NamedPersonSpend(person=by_id.get(user) if user else None, spend=spend)
        for user, spend in folded.items()
        if user is None or user in by_id
    ]
    # The largest spender first, the unattributed row last; a tie by name.
    listed.sort(
        key=lambda n: (
            n.person is None,
            -n.spend.total_usd,
            (n.person.display_name or n.person.email) if n.person else "",
        )
    )
    study_ids = {s for n in listed for (_, s) in n.spend.studies if s is not None}
    client_ids = {c for n in listed for (c, _) in n.spend.studies}
    return ResearcherSpendReport(
        period=period,
        start=start,
        end=end,
        everyone=repo.everyone,
        people=listed,
        studies=repo.study_names(study_ids),
        clients=repo.client_names(client_ids),
    )
