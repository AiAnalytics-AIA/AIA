"""The engine reads the run's settings where it read the code's tables (chunk 43c).

ADR 0022: an approved route allowance bounds a run's calls and so its cost ceiling, and an
approved request limit sizes every request of its kind and its reservation. With nothing
approved, both are the code's tables value for value, so a run under defaults is what it was.
A cap is lower-only: a pinned value above the code's never raises it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from aia_core.application.deep_research import DeepResearchRuns
from aia_core.domain.deep_research.budgets import (
    ROUTE_ALLOWANCES,
    CallKind,
    ResearchMode,
    TrackCounts,
    call_bounds,
)
from aia_core.domain.deep_research.planning import PRESETS
from aia_core.domain.deep_research.request_limits import (
    REQUEST_LIMITS,
    ModelPrices,
    RequestLimits,
    kind_budgets,
)
from aia_core.domain.deep_research.settings import (
    ApprovedValue,
    EffectiveSettings,
    Origin,
    effective,
    request_limits,
    route_allowances,
)
from aia_core.domain.run_cost import DeepResearchPrices, RoutePrice, deep_research_cost_ceiling

CRAWL = "budgets.allowance.exhaustive.crawl_pages"
VERIFIER_ANSWER = "limits.verifier.answer_tokens"

#: Illustrative prices for these tests only -- never configuration.
PRICES = ModelPrices(input_usd_per_mtok=3.0, output_usd_per_mtok=15.0)


def _approved(**values: Any) -> EffectiveSettings:
    at = datetime(2026, 10, 9, tzinfo=UTC)
    return effective(
        {
            key.replace("__", "."): ApprovedValue(
                value=v, version=1, approved_by="a", approved_at=at
            )
            for key, v in values.items()
        }
    )


def _with(key: str, value: int) -> EffectiveSettings:
    return _approved(**{key.replace(".", "__"): value})


def _priced(crawl_usd: float) -> DeepResearchPrices:
    every = {k: RoutePrice.per_call(0.5) for k in CallKind}
    every[CallKind.CRAWL_FETCH] = RoutePrice.per_call(crawl_usd)
    return DeepResearchPrices(every)


# ------------------------------------------------------------------ defaults


def test_with_nothing_approved_the_engine_reads_the_code_s_tables() -> None:
    settings = effective({})
    assert route_allowances(settings) == dict(ROUTE_ALLOWANCES)
    assert request_limits(settings) == dict(REQUEST_LIMITS)


# ------------------------------------------------------------------ allowances


def test_an_approved_allowance_bounds_the_run_and_lowers_its_ceiling() -> None:
    depth = PRESETS["EXHAUSTIVE"]
    tracks = TrackCounts(web=4, internal=1)
    lowered = route_allowances(_with(CRAWL, 300))
    assert lowered["EXHAUSTIVE"].crawl_pages == 300
    assert lowered["EXHAUSTIVE"].triage_reads == ROUTE_ALLOWANCES["EXHAUSTIVE"].triage_reads
    assert {p: a for p, a in lowered.items() if p != "EXHAUSTIVE"} == {
        p: a for p, a in ROUTE_ALLOWANCES.items() if p != "EXHAUSTIVE"
    }
    bounds = call_bounds(depth, tracks, ResearchMode.PLANNED, allowances=lowered)
    assert bounds[CallKind.CRAWL_FETCH] == 300
    modes = (ResearchMode.PLANNED,)
    code = deep_research_cost_ceiling(depth, tracks, _priced(0.01), modes=modes)
    pinned = deep_research_cost_ceiling(
        depth, tracks, _priced(0.01), modes=modes, allowances=lowered
    )
    assert code.total_usd is not None and pinned.total_usd is not None
    assert code.total_usd - pinned.total_usd == pytest.approx((1000 - 300) * 0.01)


def test_the_application_ceiling_reads_the_settings_it_is_given() -> None:
    from aia_core.domain.deep_research.contracts import (
        HARNESS_VERSION,
        BriefDigest,
        Channel,
        DeepResearchRequest,
        FrozenKnowledge,
        ResearchSubject,
        SubjectKind,
        subject_key,
    )

    text = "Jak roste trh rostlinných nápojů?"
    request = DeepResearchRequest(
        harness_version=HARNESS_VERSION,
        design_revision_id="rev",
        design_revision=1,
        preset="EXHAUSTIVE",
        channels=(Channel.WEB,),
        brief=BriefDigest(title="t", goal="g", decision_use="", briefing=""),
        subjects=(
            ResearchSubject(
                key=subject_key(SubjectKind.QUESTION, text),
                kind=SubjectKind.QUESTION,
                text=text,
                origin="test",
            ),
        ),
        questionnaire=(),
        knowledge=FrozenKnowledge(items=(), omitted_ids=(), retrieval_limit=1),
        client_terms=(),
    )
    prices = _priced(0.01)
    code = DeepResearchRuns.cost_ceiling(request, prices=prices)
    defaults = DeepResearchRuns.cost_ceiling(request, prices=prices, settings=effective({}))
    lowered = DeepResearchRuns.cost_ceiling(request, prices=prices, settings=_with(CRAWL, 300))
    assert defaults == code
    assert lowered.calls[CallKind.CRAWL_FETCH] == 300
    assert lowered.total_usd is not None and code.total_usd is not None
    assert lowered.total_usd < code.total_usd


# ------------------------------------------------------------------ request limits


def test_an_approved_request_limit_sizes_its_kind_and_reserves_less() -> None:
    limits = request_limits(_with(VERIFIER_ANSWER, 2048))
    assert limits[CallKind.VERIFIER] == RequestLimits(window_tokens=112_000, answer_tokens=2048)
    assert {k: v for k, v in limits.items() if k is not CallKind.VERIFIER} == {
        k: v for k, v in REQUEST_LIMITS.items() if k is not CallKind.VERIFIER
    }
    args: dict[str, Any] = {"context_window_tokens": 200_000, "max_output_tokens": 8192}
    code = kind_budgets(PRICES, **args)
    pinned = kind_budgets(PRICES, **args, limits=limits)
    assert pinned[CallKind.VERIFIER].output_tokens == 2048
    assert pinned[CallKind.VERIFIER].reservation_usd < code[CallKind.VERIFIER].reservation_usd
    assert {k: b for k, b in pinned.items() if k is not CallKind.VERIFIER} == {
        k: b for k, b in code.items() if k is not CallKind.VERIFIER
    }


def test_a_window_the_code_leaves_to_the_model_can_be_approved_and_still_fits_the_model() -> None:
    limits = request_limits(_with("limits.planner.window_tokens", 50_000))
    assert limits[CallKind.PLANNER].window_tokens == 50_000
    budgets = kind_budgets(
        PRICES, context_window_tokens=40_000, max_output_tokens=8192, limits=limits
    )
    assert budgets[CallKind.PLANNER].window_tokens == 40_000  # never beyond the model's


# ------------------------------------------------------------------ caps


def _forced(key: str, value: int) -> EffectiveSettings:
    """A value above the code's cap, as no approval could store (the store refuses it)."""
    settings = effective({})
    return EffectiveSettings(
        tuple(
            replace(e, value=value, origin=Origin.APPROVED) if e.key == key else e
            for e in settings.values
        )
    )


def test_a_value_above_the_code_s_cap_never_raises_it() -> None:
    assert route_allowances(_forced(CRAWL, 5000))["EXHAUSTIVE"].crawl_pages == 1000
    assert request_limits(_forced(VERIFIER_ANSWER, 64_000))[CallKind.VERIFIER].answer_tokens == (
        4096
    )


def test_the_store_refuses_raising_a_cap_in_the_first_place() -> None:
    from aia_core.domain.deep_research.settings import SettingInvalid

    with pytest.raises(SettingInvalid, match="may only lower"):
        _with(CRAWL, 1001)
