"""A Deep Research run asks first when its cost ceiling reaches the study's limit (ADR 0019 gate 2).

Plan ``deep-research-web-search.md`` chunk 22, as a research run's start does it
(``test_research_runs.py``): the server works the ceiling out from the frozen request, its
preset and the prices the deployment states; at or above the study's limit it needs the
person's confirmation covering it, recorded once in the approval ledger with the run; a
ceiling it cannot work out is not let by; a retry asks again.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.research import CostCeilingUnknown, CostConfirmationRequired
from aia_core.domain.deep_research.budgets import MODEL_KINDS, CallKind, ResearchMode
from aia_core.domain.deep_research.planning import PRESET_TABLE_VERSION
from aia_core.domain.run_cost import CeilingUnknown, DeepResearchPrices, RoutePrice
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import ApprovalDecisionRow

DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje",
    "goal": "Zjistit, kdo v Česku pije rostlinné nápoje a proč.",
    "research_plan": {
        "research_questions": [
            "Jak roste trh rostlinných nápojů v Česku?",
            "Proč lidé přecházejí na rostlinné nápoje?",
        ]
    },
    "sections": [
        {
            "type": "object_battery",
            "objects": ["Ovesný nápoj", "Mandlový nápoj"],
            "object_question": "Jak hodnotíte {object}?",
        }
    ],
}

#: Illustrative prices for these tests: every agent reserves 0.5 a request, search and fetch
#: free (the public route), nothing else composed.
PRICES = DeepResearchPrices(
    {
        **{k: RoutePrice.per_call(0.5) for k in MODEL_KINDS},
        CallKind.SEARCH: RoutePrice.per_call(0.0),
        CallKind.FETCH: RoutePrice.per_call(0.0),
        CallKind.TRIAGE: RoutePrice.off(),
        CallKind.CRAWL_FETCH: RoutePrice.off(),
        CallKind.CONNECTOR: RoutePrice.off(),
        CallKind.URL_INDEX_QUERY: RoutePrice.off(),
        CallKind.ARCHIVE_FETCH: RoutePrice.off(),
    }
)
LEAD = (ResearchMode.LEAD,)


@pytest.fixture
def runs(session: Any, scoped: Any) -> Any:
    return lambda **kw: DeepResearchRuns(session, scoped.scope(**kw))


@pytest.fixture
def revision(session: Any, scoped: Any) -> str:
    repo = StudyDesignRepository(session, scoped.scope(user="lead"))
    made, _ = repo.submit(content=DESIGN, source_stage="brief")
    return made.revision_id


def _limit(scoped: Any, usd: float | None) -> None:
    scoped.scope_repo.set_study_spend_confirm(scoped.scope(), usd)


def _spend_rows(session: Any) -> list[Any]:
    return list(
        session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_type == "spend")
        ).all()
    )


def _ceiling(runs: Any, revision: str, preset: str) -> float:
    request = runs(user="researcher").freeze(design_revision_id=revision, preset_name=preset)
    total = DeepResearchRuns.cost_ceiling(request, prices=PRICES, modes=LEAD).total_usd
    assert total is not None
    return float(total)


def _start(runs: Any, revision: str, preset: str = "EXHAUSTIVE", **kw: Any) -> Any:
    args: dict[str, Any] = {
        "design_revision_id": revision,
        "preset_name": preset,
        "prices": PRICES,
        "modes": LEAD,
    }
    args.update(kw)
    return runs(user="researcher").start(**args)


def test_an_exhaustive_run_over_the_limit_asks_first_and_creates_nothing(
    session: Any, scoped: Any, runs: Any, revision: str
) -> None:
    ceiling = _ceiling(runs, revision, "EXHAUSTIVE")
    _limit(scoped, ceiling - 1.0)
    with pytest.raises(CostConfirmationRequired) as asked:
        _start(runs, revision)
    assert (asked.value.ceiling_usd, asked.value.limit_usd) == (ceiling, ceiling - 1.0)
    assert runs(user="researcher").runs() == []  # asking is not starting
    # A confirmation below the ceiling is not one: the server holds it to its own figure.
    with pytest.raises(CostConfirmationRequired):
        _start(runs, revision, confirm_cost_usd=ceiling - 0.01)
    assert _spend_rows(session) == []


def test_reaching_the_limit_exactly_asks_too(scoped: Any, runs: Any, revision: str) -> None:
    _limit(scoped, _ceiling(runs, revision, "EXHAUSTIVE"))
    with pytest.raises(CostConfirmationRequired):
        _start(runs, revision)


def test_the_same_run_under_the_limit_does_not_ask(
    session: Any, scoped: Any, runs: Any, revision: str
) -> None:
    ceiling = _ceiling(runs, revision, "EXHAUSTIVE")
    _limit(scoped, ceiling + 1.0)
    started = _start(runs, revision)
    assert started.created
    assert _spend_rows(session) == []
    meta = runs(user="researcher").get(started.run_id)["metadata"]
    assert meta["preset_table"] == PRESET_TABLE_VERSION
    assert (meta["cost_ceiling_usd"], meta["cost_ceiling_mode"]) == (ceiling, "lead")


def test_a_deeper_preset_asks_where_a_shallower_one_does_not(
    scoped: Any, runs: Any, revision: str
) -> None:
    standard = _ceiling(runs, revision, "STANDARD")
    exhaustive = _ceiling(runs, revision, "EXHAUSTIVE")
    assert standard < exhaustive
    _limit(scoped, (standard + exhaustive) / 2)
    assert _start(runs, revision, preset="STANDARD").created
    with pytest.raises(CostConfirmationRequired):
        _start(runs, revision)


def test_a_confirmation_covering_the_ceiling_starts_the_run_and_is_recorded_once(
    session: Any, scoped: Any, runs: Any, revision: str
) -> None:
    ceiling = _ceiling(runs, revision, "EXHAUSTIVE")
    _limit(scoped, 10.0)
    started = _start(runs, revision, confirm_cost_usd=ceiling)
    assert started.created
    [row] = _spend_rows(session)
    assert (row.decision, row.run_id, row.subject_id) == ("confirm", started.run_id, started.run_id)
    assert row.approver_user_id == scoped.users["researcher"]
    assert json.loads(row.comment) == {
        "ceiling_usd": ceiling,
        "limit_usd": 10.0,
        "confirmed_usd": ceiling,
    }
    # The same request again gets the run that exists: it spends nothing, asks nothing,
    # and records nothing more.
    again = _start(runs, revision)
    assert (again.created, again.run_id) == (False, started.run_id)
    assert len(_spend_rows(session)) == 1


def test_a_retry_is_a_new_run_and_asks_again(
    session: Any, scoped: Any, runs: Any, revision: str
) -> None:
    ceiling = _ceiling(runs, revision, "EXHAUSTIVE")
    _limit(scoped, 10.0)
    first = _start(runs, revision, confirm_cost_usd=ceiling)
    runs(user="researcher").cancel(first.run_id)
    with pytest.raises(CostConfirmationRequired):
        runs(user="researcher").retry(first.run_id, prices=PRICES, modes=LEAD)
    retried = runs(user="researcher").retry(
        first.run_id, prices=PRICES, modes=LEAD, confirm_cost_usd=ceiling
    )
    assert retried.created and retried.run_id != first.run_id
    assert len(_spend_rows(session)) == 2


def test_an_unknown_ceiling_refuses_a_start_that_has_a_limit_and_not_one_without(
    scoped: Any, runs: Any, revision: str
) -> None:
    """A missing price is not a cheap run: with a limit set, the start does not slip by."""
    unpriced = DeepResearchPrices({**PRICES.prices, CallKind.TRIAGE: RoutePrice.unknown()})
    _limit(scoped, 1000.0)
    with pytest.raises(CostCeilingUnknown) as unknown:
        _start(runs, revision, prices=unpriced)
    assert unknown.value.reason is CeilingUnknown.DEEP_RESEARCH_PRICE_MISSING
    assert unknown.value.kinds == ("triage",)
    # No prices at all: unknown too.
    with pytest.raises(CostCeilingUnknown):
        _start(runs, revision, prices=None)
    # Standard has no triage: the unpriced route is one it never calls.
    assert _start(runs, revision, preset="STANDARD", prices=unpriced, confirm_cost_usd=1e5).created
    _limit(scoped, None)
    assert _start(runs, revision, prices=None).created


def test_every_mode_is_asked_against_when_the_caller_does_not_know_the_switches(
    scoped: Any, runs: Any, revision: str
) -> None:
    request = runs(user="researcher").freeze(design_revision_id=revision, preset_name="DEEP")
    every = DeepResearchRuns.cost_ceiling(request, prices=PRICES)
    each = [
        DeepResearchRuns.cost_ceiling(request, prices=PRICES, modes=(m,)).total_usd
        for m in ResearchMode
    ]
    assert every.total_usd == max(t for t in each if t is not None)
