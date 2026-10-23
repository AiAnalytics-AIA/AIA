"""The organization's spend and the near-limit rule (settings-backends SB3, pure).

The organization's total is every person's spend by the same fold, the unattributed rows
included, so it never disagrees with per-researcher spend; a study is near its limit from 90 %
of a set budget spent or held, and a study with no budget is never near one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from aia_core.domain.spend_attribution import (
    NEAR_LIMIT_SHARE,
    HoldFact,
    SpendActivity,
    UsageFact,
    near_limit_share,
    organization_spend,
    researcher_spend,
)

_T0 = datetime(2026, 10, 1, tzinfo=UTC)
_T1 = datetime(2026, 11, 1, tzinfo=UTC)


def _u(call: str, outcome: str, cost: float, who: str | None, **kw: Any) -> UsageFact:
    base: dict[str, Any] = {
        "call_id": call,
        "outcome": outcome,
        "cost_usd": cost,
        "charged_to": who,
        "client_id": "CLI-1",
        "study_id": "STU-1",
        "activity": SpendActivity.FIELDWORK,
        "occurred_at": _T0 + timedelta(days=3),
    }
    return UsageFact(**{**base, **kw})


def _h(rid: str, status: str, amount: float, settled: float, who: str | None) -> HoldFact:
    return HoldFact(
        reservation_id=rid,
        status=status,
        amount_usd=amount,
        settled_amount_usd=settled,
        charged_to=who,
        client_id="CLI-1",
        study_id="STU-1",
        activity=SpendActivity.DEEP_RESEARCH,
        in_ledger=False,
        settled_at=_T0 + timedelta(days=4) if status != "RESERVED" else None,
    )


def test_the_organization_is_every_person_and_nobody_by_the_same_fold() -> None:
    usage = [
        _u("c1", "SUCCEEDED", 0.5, "A"),
        _u("c2", "SUCCEEDED", 0.25, None, activity=SpendActivity.LEAD),
        _u("c3", "DISPATCHED", 0.0, "B"),  # no outcome: uncertain, never a zero
    ]
    holds = [
        _h("r1", "SETTLED", 0.4, 0.3, "B"),
        _h("r2", "RESERVED", 0.2, 0.0, None),
        _h("r3", "SETTLED_UNCERTAIN", 0.1, 0.1, "A"),
    ]
    total, by = organization_spend(usage, holds, start=_T0, end=_T1)
    people = researcher_spend(usage, holds, start=_T0, end=_T1).values()
    assert total.model_usd == pytest.approx(sum(p.model_usd for p in people)) == 0.75
    assert total.outside_ledger_usd == pytest.approx(0.4)
    assert total.reserved_usd == pytest.approx(0.2)
    assert total.uncertain_calls == 2
    assert by[SpendActivity.LEAD].model_usd == 0.25
    assert by[SpendActivity.DEEP_RESEARCH].outside_ledger_usd == pytest.approx(0.4)


def test_nothing_spent_is_a_known_zero() -> None:
    total, by = organization_spend([], [], start=_T0, end=_T1)
    assert (total.total_usd, total.reserved_usd, total.uncertain_calls, by) == (0.0, 0.0, 0, {})


@pytest.mark.parametrize(
    ("budget", "spent", "held", "share"),
    [
        (100.0, 90.0, 0.0, 0.9),  # at the line
        (100.0, 60.0, 35.0, 0.95),  # held counts: the budget can no longer give it
        (100.0, 120.0, 0.0, 1.2),  # an overrun stays visible above 1
        (100.0, 89.0, 0.0, None),
        (0.0, 5.0, 0.0, None),  # no budget set: never near a limit, no share invented
    ],
)
def test_a_study_is_near_its_limit_from_ninety_percent_spent_or_held(
    budget: float, spent: float, held: float, share: float | None
) -> None:
    assert NEAR_LIMIT_SHARE == 0.9
    got = near_limit_share(budget, spent, held)
    assert got == (pytest.approx(share) if share is not None else None)
