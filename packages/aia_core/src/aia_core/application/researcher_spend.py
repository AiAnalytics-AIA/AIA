"""Per-researcher spend, as Settings → Studie a rozpočty shows it (``develop-spend-attribution``
7, Q40: OWNER and ADMIN see everyone, a researcher only themself).

The repository reads the content-free rows in scope; ``domain/spend_attribution.py`` folds them
into each person's spend by activity and by study; this module names the people, studies and
clients and orders the result. Read-only: nothing here writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..domain.scope import OrganizationContext
from ..domain.spend_attribution import (
    PersonSpend,
    SpendPeriod,
    period_bounds,
    researcher_spend,
)
from ..infrastructure.researcher_spend_repository import (
    Person,
    ResearcherSpendRepository,
    StudyName,
)

__all__ = ["NamedPersonSpend", "ResearcherSpendReport", "researcher_spend_report"]


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
