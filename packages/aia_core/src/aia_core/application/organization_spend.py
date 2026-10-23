"""The organization's spend, as Settings → Studie a rozpočty shows it at the top
(``develop-spend-attribution`` 6, settings-backends SB3): what the organization spent over a
period, model calls and tools apart, what is held open now, the calls whose bill is not known,
and the open studies whose budget is nearly used (the product owner, 2026-10-22: 90 %).

An organization OWNER or ADMIN reads it; nobody else. The rows are the content-free ones
per-researcher spend reads (``ResearcherSpendRepository``), folded by the same rules
(``domain/spend_attribution.py``), so the two never disagree on a figure. Read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..domain.scope import OrganizationContext
from ..domain.spend_attribution import (
    ActivitySpend,
    SpendActivity,
    SpendPeriod,
    near_limit_share,
    organization_spend,
    period_bounds,
)
from ..infrastructure.researcher_spend_repository import ResearcherSpendRepository, StudyBudget

__all__ = ["NearLimit", "OrganizationSpendReport", "organization_spend_report"]


@dataclass(frozen=True, slots=True)
class NearLimit:
    """An open study whose budget is at least 90 % spent or held: ``used_usd`` is both."""

    study: StudyBudget
    used_usd: float
    share: float


@dataclass(frozen=True, slots=True)
class OrganizationSpendReport:
    period: SpendPeriod
    start: datetime
    end: datetime
    total: ActivitySpend
    by_activity: dict[SpendActivity, ActivitySpend]
    near_limit: list[NearLimit]


def organization_spend_report(
    session: Session,
    scope: OrganizationContext,
    period: SpendPeriod,
    *,
    now: datetime | None = None,
) -> OrganizationSpendReport:
    """The organization's spend over ``period`` and its studies near their budget. OWNER or
    ADMIN only (``ScopeDenied`` ``insufficient_role`` otherwise), checked before any row is
    read."""
    scope.require_administer()
    start, end = period_bounds(period, now or datetime.now(UTC))
    repo = ResearcherSpendRepository(session, scope)
    total, by_activity = organization_spend(
        repo.usage(since=start), repo.holds(since=start), start=start, end=end
    )
    near: list[NearLimit] = []
    for study in repo.study_budgets():
        share = near_limit_share(study.budget_usd, study.spent_usd, study.held_usd)
        if share is not None:
            near.append(NearLimit(study, study.spent_usd + study.held_usd, share))
    # The fullest first; a tie by name.
    near.sort(key=lambda n: (-n.share, n.study.study_name, n.study.study_id))
    return OrganizationSpendReport(
        period=period,
        start=start,
        end=end,
        total=total,
        by_activity=by_activity,
        near_limit=near,
    )
