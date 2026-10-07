"""Each Deep Research request is sent under its kind's window, output limit and reservation.

The journeys (``test_deep_research_ceiling_journey.py``) hold every recorded request to its
kind's reservation; here the edges are driven directly: a request larger than its kind's
window but within the model's is refused before anything is reserved or sent, the same
request of a kind with the model's window goes out, and the caller reserves exactly what
it is told for one request.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from aia_core.domain.deep_research.agents import AgentRole
from aia_core.domain.deep_research.budgets import CallKind
from aia_core.domain.deep_research.request_limits import ModelPrices, kind_of
from aia_core.domain.deep_research.steps import Gate
from aia_core.domain.licence import DataLineage
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass
from aia_executors.ai_step import StepModelCaller
from aia_executors.deep_research import DeepResearchConfig, DeepResearchRuntime
from aia_executors.deep_research._shared import _Step

CONFIG = DeepResearchConfig(
    policy_version="p",
    max_output_tokens=8_192,
    context_window_tokens=200_000,
    prices=ModelPrices(3.0, 15.0),
    fictional_client_ids=frozenset(),
)
RUNTIME = cast(DeepResearchRuntime, SimpleNamespace(config=CONFIG))


class _Sent(Exception):
    """What a request carried when it reached the caller (nothing is really sent)."""

    def __init__(self, reservation_usd: float | None) -> None:
        self.reservation_usd = reservation_usd


class _Caller:
    def __init__(self) -> None:
        self.preflights = 0

    def preflight(self, request: Any) -> None:
        self.preflights += 1

    def invoke(self, request: Any, *, reservation_usd: float | None = None) -> None:
        raise _Sent(reservation_usd)


def _request(role: AgentRole, text_bytes: int) -> Any:
    return _Step._request(
        RUNTIME,
        role,
        payload={"text": "a" * text_bytes},
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage.none(),
    )


def _send(caller: _Caller, role: AgentRole, request: Any) -> Any:
    return _Step._send(
        cast(StepModelCaller, caller),
        RUNTIME,
        role,
        request,
        data_class=DataClass.CLASS_C_INTERNAL,
    )


def test_a_request_beyond_its_kinds_window_is_refused_before_anything_is_reserved() -> None:
    # 120 KB of text: beyond the investigator's window with its repair, within the model's.
    caller = _Caller()
    answer = _send(caller, AgentRole.INVESTIGATOR, _request(AgentRole.INVESTIGATOR, 120_000))
    assert answer.gate is Gate.CONTEXT_WINDOW and answer.reason == "context_too_large"
    assert "investigator window of 144000 tokens" in answer.detail
    assert caller.preflights == 0


def test_the_same_request_of_a_whole_window_kind_goes_out_at_its_reservation() -> None:
    caller = _Caller()
    with pytest.raises(_Sent) as sent:
        _send(caller, AgentRole.SYNTHESIZER, _request(AgentRole.SYNTHESIZER, 120_000))
    assert caller.preflights == 1
    assert sent.value.reservation_usd == CONFIG.budget(CallKind.SYNTHESIZER).reservation_usd


@pytest.mark.parametrize("role", list(AgentRole))
def test_every_role_asks_for_its_kinds_output_and_reserves_its_kinds_amount(
    role: AgentRole,
) -> None:
    budget = CONFIG.budget(kind_of(role))
    request = _request(role, 10)
    assert request.output_token_limit == budget.output_tokens
    with pytest.raises(_Sent) as sent:
        _send(_Caller(), role, request)
    assert sent.value.reservation_usd == budget.reservation_usd


def test_a_caller_reserves_what_one_request_names() -> None:
    held: list[float] = []

    class _Context:
        step = SimpleNamespace(run_id="R", step_id="S", attempt_id="A")

        def reserve(self, *, amount_usd: float, provider: Provider, reason: str) -> Any:
            held.append(amount_usd)
            raise _Sent(amount_usd)

    caller = StepModelCaller(
        gateway=cast(Any, None),
        context=cast(Any, _Context()),
        runtime_version="t",
        provider=Provider.AWS_BEDROCK,
        reservation_usd=2.0,
    )
    request = _request(AgentRole.VERIFIER, 10)
    with pytest.raises(_Sent):
        caller.invoke(request, reservation_usd=0.75)
    with pytest.raises(_Sent):
        caller.invoke(request)
    assert held == [0.75, 2.0]
    with pytest.raises(ValueError, match="positive reservation"):
        caller.invoke(request, reservation_usd=0.0)
    assert held == [0.75, 2.0], "a refused amount reserves nothing"
