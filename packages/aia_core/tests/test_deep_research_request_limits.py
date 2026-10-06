"""Each kind of Deep Research request: its window, its output limit, its reservation."""

from __future__ import annotations

import pytest

from aia_core.domain.deep_research.agents import AgentRole
from aia_core.domain.deep_research.budgets import MODEL_KINDS, CallKind
from aia_core.domain.deep_research.request_limits import (
    REQUEST_LIMITS,
    RESEARCH_KINDS,
    KindBudget,
    ModelPrices,
    RequestLimits,
    kind_budgets,
    kind_of,
    reservation_usd,
    window_fits,
)

PRICES = ModelPrices(input_usd_per_mtok=3.0, output_usd_per_mtok=15.0)
WINDOW = 200_000
OUTPUT = 8_192


def budgets() -> dict[CallKind, KindBudget]:
    return kind_budgets(PRICES, context_window_tokens=WINDOW, max_output_tokens=OUTPUT)


def test_every_research_kind_is_stated_and_triage_is_not() -> None:
    assert set(REQUEST_LIMITS) == RESEARCH_KINDS == MODEL_KINDS - {CallKind.TRIAGE}


def test_every_agent_role_is_a_research_kind() -> None:
    assert {kind_of(role) for role in AgentRole} == RESEARCH_KINDS


def test_the_whole_window_kinds_reserve_what_the_worker_always_required() -> None:
    whole = 2 * (WINDOW * 3.0 + OUTPUT * 15.0) / 1_000_000
    for kind in (CallKind.PLANNER, CallKind.LEAD, CallKind.SYNTHESIZER):
        budget = kind_budgets(PRICES, context_window_tokens=WINDOW, max_output_tokens=OUTPUT)[kind]
        assert (budget.window_tokens, budget.output_tokens) == (WINDOW, OUTPUT)
        assert budget.reservation_usd == pytest.approx(whole)


def test_the_frequent_kinds_reserve_less_than_the_whole_window() -> None:
    every = kind_budgets(PRICES, context_window_tokens=WINDOW, max_output_tokens=OUTPUT)
    whole = every[CallKind.SYNTHESIZER].reservation_usd
    investigator = every[CallKind.INVESTIGATOR]
    assert (investigator.window_tokens, investigator.output_tokens) == (144_000, 6_144)
    assert investigator.reservation_usd == pytest.approx(
        2 * (144_000 * 3.0 + 6_144 * 15.0) / 1_000_000
    )
    for kind in (CallKind.INVESTIGATOR, CallKind.INTERNAL_INVESTIGATOR, CallKind.VERIFIER):
        assert every[kind].reservation_usd < whole


def test_thinking_is_added_to_the_answer_and_never_beyond_the_research_limit() -> None:
    every = kind_budgets(
        PRICES, context_window_tokens=WINDOW, max_output_tokens=OUTPUT, thinking_budget_tokens=1024
    )
    assert every[CallKind.INVESTIGATOR].output_tokens == 6_144 + 1024
    assert every[CallKind.VERIFIER].output_tokens == 4_096 + 1024
    capped = kind_budgets(
        PRICES, context_window_tokens=WINDOW, max_output_tokens=OUTPUT, thinking_budget_tokens=4096
    )
    assert capped[CallKind.INVESTIGATOR].output_tokens == OUTPUT
    assert capped[CallKind.VERIFIER].output_tokens == OUTPUT


def test_no_kind_exceeds_a_smaller_model() -> None:
    small = kind_budgets(PRICES, context_window_tokens=50_000, max_output_tokens=2_000)
    assert all(b.window_tokens == 50_000 and b.output_tokens == 2_000 for b in small.values())


def test_the_dearest_input_path_prices_the_window() -> None:
    cached = ModelPrices(3.0, 15.0, cache_read_usd_per_mtok=0.3, cache_write_usd_per_mtok=3.75)
    assert reservation_usd(cached, window_tokens=1_000_000, output_tokens=0) == pytest.approx(7.5)


def test_the_window_keeps_room_for_the_repair() -> None:
    # The request, five bytes per output token for the answer sent back, and the framing.
    assert window_fits(100, window_tokens=100 + 5 * 10 + 2048, output_tokens=10)
    assert not window_fits(101, window_tokens=100 + 5 * 10 + 2048, output_tokens=10)


def test_the_repair_fits_what_the_primary_left() -> None:
    """The invariant behind the reservation: a request that fits its window, sent at its
    worst (every byte a token, the whole output), leaves enough for the repair at its worst
    (the original, the answer back at five bytes a token, the framing)."""
    for kind, budget in budgets().items():
        largest = budget.window_tokens - 5 * budget.output_tokens - 2048
        assert window_fits(
            largest,
            window_tokens=budget.window_tokens,
            output_tokens=budget.output_tokens,
        ), kind
        primary = (largest * 3.0 + budget.output_tokens * 15.0) / 1e6
        repair_input = largest + 5 * budget.output_tokens + 2048
        repair = (repair_input * 3.0 + budget.output_tokens * 15.0) / 1e6
        assert primary + repair <= budget.reservation_usd + 1e-12, kind


@pytest.mark.parametrize("value", [0, -1])
def test_a_limit_is_positive(value: int) -> None:
    with pytest.raises(ValueError):
        RequestLimits(window_tokens=value, answer_tokens=None)
    with pytest.raises(ValueError):
        RequestLimits(window_tokens=None, answer_tokens=value)


def test_a_table_missing_a_kind_is_refused() -> None:
    partial: dict[CallKind, RequestLimits] = {
        k: v for k, v in REQUEST_LIMITS.items() if k is not CallKind.VERIFIER
    }
    with pytest.raises(ValueError, match="verifier"):
        kind_budgets(PRICES, context_window_tokens=WINDOW, max_output_tokens=OUTPUT, limits=partial)


def test_a_price_is_finite_and_not_negative() -> None:
    with pytest.raises(ValueError):
        ModelPrices(-1.0, 15.0)
    with pytest.raises(ValueError):
        ModelPrices(3.0, float("inf"))
