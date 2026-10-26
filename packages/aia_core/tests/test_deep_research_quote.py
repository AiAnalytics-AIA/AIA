"""A Deep Research start's price, always computed, and the read-only quote that states it.

Plan ``deep-research-web-search.md`` chunk 55 (DRL-0): every new run stores its ceiling,
whether or not the study has a confirmation threshold (F-DRL-2); ``DeepResearchRuns.quote``
answers what a start would cost and answer, from the same admission the start acts on, and
writes nothing.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select

from aia_core.application.deep_research import (
    DeepResearchRuns,
    LiveNotApproved,
    StartVerdict,
    ceiling_metadata,
)
from aia_core.application.research import CostCeilingUnknown, CostConfirmationRequired
from aia_core.domain.deep_research.budgets import MODEL_KINDS, CallKind, ResearchMode
from aia_core.domain.deep_research.integration import DeepResearchPurpose
from aia_core.domain.deep_research.settings import effective
from aia_core.domain.run_cost import CeilingUnknown, DeepResearchPrices, RoutePrice
from aia_core.domain.scope import ScopeDenied, StudyStatus
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import (
    ApprovalDecisionRow,
    BudgetReservationRow,
    StepRunRow,
    WorkflowRunRow,
)

DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje",
    "goal": "Zjistit, kdo v Česku pije rostlinné nápoje a proč.",
    "research_plan": {"research_questions": ["Jak roste trh rostlinných nápojů v Česku?"]},
    "sections": [],
}
LEAD = (ResearchMode.LEAD,)


def _prices(search: RoutePrice) -> DeepResearchPrices:
    every = {k: RoutePrice.per_call(0.5) for k in MODEL_KINDS}
    every.update({k: RoutePrice.off() for k in CallKind if k not in MODEL_KINDS})
    every[CallKind.SEARCH] = search
    every[CallKind.FETCH] = RoutePrice.per_call(0.0)
    return DeepResearchPrices(every)


FREE = _prices(RoutePrice.per_call(0.0))
PAID = _prices(RoutePrice.per_call(0.005))
UNPRICED = _prices(RoutePrice.unknown())


@pytest.fixture
def runs(session: Any, scoped: Any) -> DeepResearchRuns:
    return DeepResearchRuns(session, scoped.scope(user="researcher"))


@pytest.fixture
def revision(session: Any, scoped: Any) -> str:
    repo = StudyDesignRepository(session, scoped.scope(user="lead"))
    made, _ = repo.submit_as_working_copy(content=DESIGN, source_stage="brief")
    return made.revision_id


def _limit(scoped: Any, usd: float | None) -> None:
    scoped.scope_repo.set_study_spend_confirm(scoped.scope(), usd)


def _quote(runs: DeepResearchRuns, revision: str, prices: Any, preset: str = "STANDARD") -> Any:
    spec = runs.freeze_design(design_revision_id=revision, preset_name=preset)
    return runs.quote(spec, prices=prices, modes=LEAD)


def _start(runs: DeepResearchRuns, revision: str, prices: Any, **kw: Any) -> Any:
    return runs.start(
        design_revision_id=revision, preset_name="STANDARD", prices=prices, modes=LEAD, **kw
    )


def _counts(session: Any) -> tuple[int, ...]:
    return tuple(
        int(session.scalar(select(func.count()).select_from(table)) or 0)
        for table in (WorkflowRunRow, StepRunRow, ApprovalDecisionRow, BudgetReservationRow)
    )


def test_a_study_with_no_threshold_still_stores_the_ceiling_the_quote_states(
    runs: DeepResearchRuns, revision: str
) -> None:
    """F-DRL-2: the ceiling was worked out only under a threshold; now always."""
    quoted = _quote(runs, revision, FREE)
    assert quoted.threshold_usd is None
    assert quoted.verdict is StartVerdict.START
    assert quoted.ceiling is not None and quoted.ceiling.total_usd is not None
    assert quoted.ceiling.total_usd > 0
    started = _start(runs, revision, FREE)
    meta = runs.get(started.run_id)["metadata"]
    assert meta["cost_ceiling_usd"] == quoted.ceiling.total_usd
    assert meta["cost_ceiling_mode"] == "lead"
    assert "cost_ceiling_unknown" not in meta


def test_a_quote_writes_nothing(session: Any, runs: DeepResearchRuns, revision: str) -> None:
    before = _counts(session)
    for prices in (FREE, PAID, UNPRICED, None):
        _quote(runs, revision, prices)
    session.flush()
    assert _counts(session) == before
    assert runs.runs() == []


def test_the_quote_and_the_start_agree_under_a_threshold(
    session: Any, scoped: Any, runs: DeepResearchRuns, revision: str
) -> None:
    ceiling = _quote(runs, revision, FREE).ceiling.total_usd
    _limit(scoped, ceiling - 1.0)
    quoted = _quote(runs, revision, FREE)
    assert quoted.verdict is StartVerdict.CONFIRM
    assert quoted.threshold_usd == ceiling - 1.0
    with pytest.raises(CostConfirmationRequired) as asked:
        _start(runs, revision, FREE)
    assert asked.value.ceiling_usd == quoted.ceiling.total_usd
    started = _start(runs, revision, FREE, confirm_cost_usd=quoted.ceiling.total_usd)
    assert started.created
    again = _quote(runs, revision, FREE)
    assert again.verdict is StartVerdict.EXISTS and again.existing_run_id == started.run_id


def test_under_the_threshold_the_quote_says_start(
    scoped: Any, runs: DeepResearchRuns, revision: str
) -> None:
    ceiling = _quote(runs, revision, FREE).ceiling.total_usd
    _limit(scoped, ceiling + 1.0)
    assert _quote(runs, revision, FREE).verdict is StartVerdict.START
    assert _start(runs, revision, FREE).created


def test_an_unknown_price_is_null_with_its_kinds_never_zero(
    scoped: Any, runs: DeepResearchRuns, revision: str
) -> None:
    quoted = _quote(runs, revision, UNPRICED)
    assert quoted.ceiling is not None and quoted.ceiling.total_usd is None
    assert quoted.ceiling.unknown_kinds == (CallKind.SEARCH,)
    assert CallKind.SEARCH not in quoted.ceiling.usd
    # No threshold: the run starts, and stores what it does not know as unknown.
    started = _start(runs, revision, UNPRICED)
    meta = runs.get(started.run_id)["metadata"]
    assert meta["cost_ceiling_usd"] is None
    assert meta["cost_ceiling_unknown"] == CeilingUnknown.DEEP_RESEARCH_PRICE_MISSING.value
    assert meta["cost_ceiling_unknown_kinds"] == ["search"]
    # A threshold: the quote and the start both refuse the unknown ceiling.
    _limit(scoped, 5.0)
    other = runs.freeze_design(design_revision_id=revision, preset_name="QUICK")
    assert runs.quote(other, prices=UNPRICED, modes=LEAD).verdict is StartVerdict.CEILING_UNKNOWN
    with pytest.raises(CostCeilingUnknown):
        runs.start(design_revision_id=revision, preset_name="QUICK", prices=UNPRICED, modes=LEAD)


def test_no_prices_stated_is_unknown_and_refused_only_under_a_threshold(
    scoped: Any, runs: DeepResearchRuns, revision: str
) -> None:
    quoted = _quote(runs, revision, None)
    assert quoted.ceiling is None and quoted.verdict is StartVerdict.START
    started = _start(runs, revision, None)
    assert runs.get(started.run_id)["metadata"]["cost_ceiling_usd"] is None
    _limit(scoped, 5.0)
    assert _quote(runs, revision, None, preset="QUICK").verdict is StartVerdict.CEILING_UNKNOWN


def test_a_priced_route_names_the_live_settings_the_start_refuses_without(
    runs: DeepResearchRuns, revision: str
) -> None:
    quoted = _quote(runs, revision, PAID)
    assert quoted.paid_routes == (CallKind.SEARCH,)
    assert quoted.live_missing == effective({}).missing_for_live()
    assert quoted.verdict is StartVerdict.LIVE_SETTINGS_UNAPPROVED
    with pytest.raises(LiveNotApproved) as refused:
        _start(runs, revision, PAID)
    assert refused.value.missing == quoted.live_missing
    assert _quote(runs, revision, FREE).live_missing == ()


def test_the_quote_carries_purpose_preset_settings_and_budget(
    runs: DeepResearchRuns, revision: str
) -> None:
    quoted = _quote(runs, revision, FREE, preset="QUICK")
    assert quoted.purpose is DeepResearchPurpose.DESIGN_RESEARCH
    assert quoted.preset == "QUICK"
    assert len(quoted.settings_digest) == 64
    assert quoted.budget is not None and set(quoted.budget) >= {"budget_usd", "available_usd"}
    standard = _quote(runs, revision, FREE)
    assert standard.ceiling.total_usd > quoted.ceiling.total_usd


def test_a_quote_needs_an_open_study(
    scoped: Any, runs: DeepResearchRuns, revision: str, session: Any
) -> None:
    spec = runs.freeze_design(design_revision_id=revision, preset_name="QUICK")
    scoped.scope_repo.set_study_status(scoped.scope(), StudyStatus.ARCHIVED)
    session.flush()
    closed = DeepResearchRuns(session, scoped.scope(user="researcher"))
    with pytest.raises(ScopeDenied):
        closed.quote(spec, prices=FREE, modes=LEAD)


def test_ceiling_metadata_never_writes_zero_for_unknown() -> None:
    assert ceiling_metadata(None) == {
        "cost_ceiling_usd": None,
        "cost_ceiling_unknown": "deep_research_price_missing",
    }


# --------------------------------------------------------------------------- a focused run

#: Two research questions and a tracked set: the whole design researches all three kinds.
FOCUS_DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje",
    "goal": "Zjistit, kdo v Česku pije rostlinné nápoje a proč.",
    "research_plan": {
        "research_questions": [
            "Jak roste trh rostlinných nápojů v Česku?",
            "Proč lidé rostlinné nápoje nekupují?",
        ],
        "tracked_sets": [{"objects": ["Alpro", "Oatly"]}],
    },
    "sections": [],
}


def _focus_revision(session: Any, scoped: Any) -> tuple[str, list[str]]:
    from aia_core.domain.item_ids import list_ids, with_item_ids

    repo = StudyDesignRepository(session, scoped.scope(user="lead"))
    made, _ = repo.submit_as_working_copy(content=FOCUS_DESIGN, source_stage="brief")
    plan = with_item_ids(repo.content(made.revision_id))[0]["research_plan"]
    ids = list_ids(plan, "research_questions", "research_question_ids")
    assert ids is not None and len(ids) == 2
    return made.revision_id, ids


def test_a_focused_quote_equals_the_focused_start_and_both_are_smaller_than_the_design(
    session: Any, scoped: Any, runs: DeepResearchRuns
) -> None:
    """LO5a.1 (Q45; Codex on #553): a focused card used to quote and run the whole design."""
    revision, ids = _focus_revision(session, scoped)
    whole = runs.quote(
        runs.freeze_design(design_revision_id=revision, preset_name="STANDARD"),
        prices=FREE,
        modes=LEAD,
    )
    spec = runs.freeze_design(design_revision_id=revision, preset_name="STANDARD", focus=[ids[1]])
    focused = runs.quote(spec, prices=FREE, modes=LEAD)
    assert focused.ceiling.total_usd < whole.ceiling.total_usd
    started = _start(runs, revision, FREE, focus=[ids[1]])
    meta = runs.get(started.run_id)["metadata"]
    assert meta["cost_ceiling_usd"] == focused.ceiling.total_usd
    assert meta["subjects"] == 1
    # Its own request and spec: the whole design's start is a run of its own, never this one.
    assert meta["run_spec_fingerprint"] == spec.fingerprint()
    assert _start(runs, revision, FREE).run_id != started.run_id


def test_a_focused_request_holds_only_the_selected_research_questions(
    session: Any, scoped: Any, runs: DeepResearchRuns
) -> None:
    from aia_core.domain.deep_research.contracts import SubjectKind

    revision, ids = _focus_revision(session, scoped)
    whole = runs.freeze(design_revision_id=revision, preset_name="QUICK")
    assert {s.kind for s in whole.subjects} == {SubjectKind.QUESTION, SubjectKind.OBJECT}
    focused = runs.freeze(design_revision_id=revision, preset_name="QUICK", focus=[ids[1]])
    assert [(s.kind, s.text) for s in focused.subjects] == [
        (SubjectKind.QUESTION, "Proč lidé rostlinné nápoje nekupují?")
    ]
    # The subject is the whole design's own, so its tracks reuse what was researched before.
    assert focused.subjects[0] in whole.subjects
    both = runs.freeze(design_revision_id=revision, preset_name="QUICK", focus=[ids[1], ids[0]])
    assert len(both.subjects) == 2


def test_an_unknown_focus_is_refused_by_name_before_anything_is_priced(
    session: Any, scoped: Any, runs: DeepResearchRuns
) -> None:
    from aia_core.application.deep_research import FocusUnknown

    revision, ids = _focus_revision(session, scoped)
    before = _counts(session)
    with pytest.raises(FocusUnknown) as refused:
        runs.freeze_design(
            design_revision_id=revision, preset_name="STANDARD", focus=[ids[0], "rq_nope"]
        )
    assert refused.value.unknown == ("rq_nope",) and refused.value.reason == "focus_unknown"
    with pytest.raises(FocusUnknown):
        _start(runs, revision, FREE, focus=["rq_nope"])
    session.flush()
    assert _counts(session) == before
