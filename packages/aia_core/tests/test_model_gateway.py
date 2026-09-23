"""The governed model gateway: every rule a convenient gateway would give up.

Each test drives :class:`GovernedModelGateway` with a scripted adapter and the
in-memory journal, so the assertions are about *order and refusal*: what was
checked before anything was sent, what was recorded before the adapter saw the
request, and what the failure tells the recovery decision. No network, no
credentials.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from aia_core.application.model_gateway import (
    REPAIR_PROMPT_VERSION,
    GovernedModelGateway,
    input_token_bound,
)
from aia_core.domain.ai_contracts import (
    AdapterRequest,
    AdapterResponse,
    AgentDefinition,
    CallPurpose,
    CostBasis,
    Delivery,
    FallbackPolicy,
    FinishReason,
    Message,
    ModelCallFailed,
    ModelRequest,
    ModelResult,
    ModelUsage,
    ProviderError,
    ProviderErrorKind,
    UsageOutcome,
)
from aia_core.domain.ai_execution import ExecutionContext, ReservationView, recovery_inputs
from aia_core.domain.ai_models import ModelBinding, ModelCapability, ModelRegistry
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass, EgressPolicy, ProviderRoute, ResidencyZone
from aia_core.domain.workflow import (
    FailureClass,
    RecoveryAction,
    StepRunStatus,
    decide_recovery,
)
from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal

POLICY = "policy-test-v1"


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str
    score: int


class LooseAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str
    note: str | None = None


def _route(route_id: str, provider: str) -> ProviderRoute:
    # Internal-only, non-EU: the honest description of a direct provider API.
    return ProviderRoute(
        route_id=route_id,
        provider=provider,
        zone=ResidencyZone.NON_EU,
        approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
    )


EGRESS = EgressPolicy(
    routes=(
        _route("anthropic-direct", "anthropic"),
        _route("openai-direct", "openai"),
        _route("claude-code-cli", "claude_code_subscription"),
    )
)


class ScriptedAdapter:
    """Answers from a script, and checks the dispatch was journaled first."""

    def __init__(
        self,
        provider: Provider,
        script: Sequence[AdapterResponse | BaseException],
        journal: InMemoryCallJournal | None = None,
    ) -> None:
        self._provider = provider
        self._script = list(script)
        self._journal = journal
        self.requests: list[AdapterRequest] = []

    @property
    def provider(self) -> Provider:
        return self._provider

    async def send(self, request: AdapterRequest) -> AdapterResponse:
        if self._journal is not None:
            # The whole point of DISPATCHED: it exists before the call does.
            assert request.call_id in {e.call_id for e in self._journal.dispatched}
        self.requests.append(request)
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _ok(text: str = '{"verdict": "fine", "score": 7}', **kwargs: Any) -> AdapterResponse:
    base: dict[str, Any] = {
        "text": text,
        "finish_reason": FinishReason.COMPLETED,
        "usage": ModelUsage(input_tokens=1000, output_tokens=200),
        "provider_request_id": "req_ok",
        "served_model": "served-id",
    }
    return AdapterResponse(**{**base, **kwargs})


def _agent(**overrides: Any) -> AgentDefinition:
    base: dict[str, Any] = {
        "agent_id": "critic-agent",
        "version": "3",
        "capability": ModelCapability.CRITIC,
        "prompt_id": "critic",
        "prompt_version": "2",
        "output_contract": Answer,
        "max_output_tokens": 1000,
    }
    return AgentDefinition(**{**base, **overrides})


def _request(**overrides: Any) -> ModelRequest:
    base: dict[str, Any] = {
        "agent": _agent(),
        "policy_version": POLICY,
        "data_classification": DataClass.CLASS_C_INTERNAL,
        "system": "Review the argument.",
        "messages": (Message(role="user", content="The argument."),),
    }
    return ModelRequest(**{**base, **overrides})


@pytest.fixture
def scope(scoped: Any) -> Any:
    return scoped.scope(user="researcher", study="primary")


@pytest.fixture
def journal() -> InMemoryCallJournal:
    return InMemoryCallJournal()


@pytest.fixture
def context(scope: Any, journal: InMemoryCallJournal) -> ExecutionContext:
    return ExecutionContext(
        scope=scope,
        runtime_version="runtime-test",
        journal=journal,
        run_id="RUN-1",
        step_id="STP-1",
        attempt_id="ATT-1",
        reservation=ReservationView(reservation_id="RSV-1", amount_usd=5.0),
    )


# The route each test adapter is bound to. Adapters are keyed by route, not by
# provider: a route is the unit of residency approval.
ROUTE_FOR: dict[Provider, str] = {
    Provider.ANTHROPIC: "anthropic-direct",
    Provider.OPENAI: "openai-direct",
    Provider.CLAUDE_CODE: "claude-code-cli",
}


def _gateway(registry: ModelRegistry, *adapters: ScriptedAdapter) -> GovernedModelGateway:
    return GovernedModelGateway(
        registry=registry,
        egress=EGRESS,
        adapters={ROUTE_FOR[a.provider]: a for a in adapters},
    )


def _run(gateway: GovernedModelGateway, request: ModelRequest, ctx: ExecutionContext) -> Any:
    return asyncio.run(gateway.invoke(request, ctx))


def _fail(gateway: GovernedModelGateway, request: ModelRequest, ctx: ExecutionContext) -> Any:
    with pytest.raises(ModelCallFailed) as exc:
        asyncio.run(gateway.invoke(request, ctx))
    return exc.value


# --------------------------------------------------------------------------- #
# The happy path, and everything it records
# --------------------------------------------------------------------------- #


def test_structured_call_on_a_metered_route(
    model_registry: ModelRegistry, context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    openai = ScriptedAdapter(Provider.OPENAI, [_ok()], journal)
    result: ModelResult = _run(_gateway(model_registry, openai), _request(), context)

    assert isinstance(result.output, Answer)
    assert result.output.score == 7
    assert result.resolved_provider is Provider.OPENAI
    assert result.resolved_model == "extraction-small"
    assert result.served_model == "served-id"
    assert result.provider_request_id == "req_ok"
    assert result.finish_reason is FinishReason.COMPLETED
    # 1000 in at $0.15/M + 200 out at $0.60/M
    assert result.actual_cost_usd == pytest.approx(0.00027)
    assert result.cost_basis is CostBasis.METERED
    assert result.total_cost_usd == pytest.approx(0.00027)

    prov = result.provenance
    assert (prov.agent_id, prov.agent_version) == ("critic-agent", "3")
    assert (prov.prompt_id, prov.prompt_version) == ("critic", "2")
    assert prov.policy_version == POLICY
    assert prov.runtime_version == "runtime-test"
    assert prov.route_id == "openai-direct"
    assert prov.data_class is DataClass.CLASS_C_INTERNAL
    assert prov.schema_fingerprint is not None
    assert prov.substituted_from is None
    assert prov.fallback_from is None

    assert [e.outcome for e in result.usage_events] == [
        UsageOutcome.DISPATCHED,
        UsageOutcome.SUCCEEDED,
    ]
    assert journal.dispatched[0].ceiling_usd > result.actual_cost_usd
    assert journal.committed_usd() == pytest.approx(0.00027)


def test_ledger_attribution_comes_from_the_issued_scope(
    model_registry: ModelRegistry, context: ExecutionContext, scope: Any
) -> None:
    result = _run(
        _gateway(model_registry, ScriptedAdapter(Provider.OPENAI, [_ok()])), _request(), context
    )
    for event in result.usage_events:
        assert (event.organization_id, event.client_id, event.study_id, event.actor_id) == (
            scope.organization_id,
            scope.client_id,
            scope.study_id,
            scope.actor_id,
        )
        assert (event.run_id, event.step_id, event.attempt_id) == ("RUN-1", "STP-1", "ATT-1")
        assert event.reservation_id == "RSV-1"


def test_strict_mode_is_used_only_when_the_schema_supports_it_unchanged(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    strict = ScriptedAdapter(Provider.OPENAI, [_ok()])
    _run(_gateway(model_registry, strict), _request(), context)
    assert strict.requests[0].strict_schema is True
    assert strict.requests[0].output_schema is not None

    loose = ScriptedAdapter(Provider.OPENAI, [_ok('{"verdict": "fine"}')])
    _run(
        _gateway(model_registry, loose),
        _request(agent=_agent(output_contract=LooseAnswer)),
        context,
    )
    assert loose.requests[0].strict_schema is False


def test_subscription_call_needs_no_reservation_and_invents_no_usage(
    model_registry: ModelRegistry, scope: Any, journal: InMemoryCallJournal
) -> None:
    context = ExecutionContext(scope=scope, runtime_version="rv", journal=journal)
    subscription = ScriptedAdapter(
        Provider.CLAUDE_CODE,
        [_ok("plain prose", usage=ModelUsage(), provider_request_id="session-1")],
    )
    result = _run(
        _gateway(model_registry, subscription),
        _request(
            agent=_agent(capability=ModelCapability.RESEARCH_REASONING, output_contract=None),
            requested_provider=Provider.CLAUDE_CODE,
        ),
        context,
    )
    assert result.text == "plain prose"
    assert result.output is None
    assert result.actual_cost_usd == 0.0
    assert result.cost_basis is CostBasis.SUBSCRIPTION
    # Not reported is not zero.
    assert result.usage.input_tokens is None
    assert result.provenance.explicit_choice is True


def test_metered_call_with_unreported_usage_is_carried_at_its_ceiling(
    model_registry: ModelRegistry, context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    result = _run(
        _gateway(model_registry, ScriptedAdapter(Provider.OPENAI, [_ok(usage=ModelUsage())])),
        _request(),
        context,
    )
    assert result.cost_basis is CostBasis.CEILING
    assert result.actual_cost_usd == pytest.approx(journal.dispatched[0].ceiling_usd)


def test_retired_pin_is_recorded_on_every_entry(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    anthropic = ScriptedAdapter(Provider.ANTHROPIC, [_ok()])
    result = _run(
        _gateway(model_registry, anthropic),
        _request(
            agent=_agent(capability=ModelCapability.RESEARCH_REASONING),
            requested_model="reasoning-large",
        ),
        context,
    )
    assert anthropic.requests[0].model == "reasoning-large-v2"
    assert result.provenance.substituted_from == "reasoning-large"
    assert all(e.substituted_from == "reasoning-large" for e in result.usage_events)


# --------------------------------------------------------------------------- #
# Refused before anything is sent
# --------------------------------------------------------------------------- #


def _nothing_sent(adapter: ScriptedAdapter, journal: InMemoryCallJournal) -> None:
    assert adapter.requests == []
    assert journal.dispatched == []


def test_unconfigured_capability_fails_closed(
    model_registry: ModelRegistry, context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    failure = _fail(
        _gateway(model_registry, adapter),
        _request(agent=_agent(capability=ModelCapability.SIMULATION)),
        context,
    )
    assert failure.failure is FailureClass.MISSING_CONFIGURATION
    assert failure.reason == "model_resolution_capability_not_configured"
    _nothing_sent(adapter, journal)


@pytest.mark.parametrize(
    ("data_class", "reason"),
    [
        (None, "egress_unclassified_material"),
        (DataClass.CLASS_A_CLIENT_CONFIDENTIAL, "egress_route_not_approved_for_class"),
        (DataClass.CLASS_B_DERIVED_CLIENT, "egress_route_not_approved_for_class"),
    ],
)
def test_egress_is_refused_before_dispatch(
    model_registry: ModelRegistry,
    context: ExecutionContext,
    journal: InMemoryCallJournal,
    data_class: DataClass | None,
    reason: str,
) -> None:
    """Client material over a non-EU direct route, or unclassified material at
    all, never reaches the adapter -- and nothing is offered instead."""
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    failure = _fail(
        _gateway(model_registry, adapter), _request(data_classification=data_class), context
    )
    assert failure.failure is FailureClass.PERMISSION
    assert failure.reason == reason
    _nothing_sent(adapter, journal)


def test_route_approved_for_another_provider_is_refused(
    model_registry: ModelRegistry, context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    gateway = GovernedModelGateway(
        registry=model_registry,
        egress=EgressPolicy(routes=(_route("openai-direct", "someone_else"),)),
        # No adapter can even be bound to this route (the constructor refuses a
        # mismatch), so the egress check is what stops the call.
        adapters={},
    )
    failure = _fail(gateway, _request(), context)
    assert failure.reason == "egress_route_provider_mismatch"
    _nothing_sent(adapter, journal)


def test_metered_call_without_a_reservation_is_refused(
    model_registry: ModelRegistry, scope: Any, journal: InMemoryCallJournal
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    context = ExecutionContext(scope=scope, runtime_version="rv", journal=journal)
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.failure is FailureClass.MISSING_CONFIGURATION
    assert failure.reason == "paid_call_without_reservation"
    _nothing_sent(adapter, journal)


def test_request_naming_another_reservation_is_refused(
    model_registry: ModelRegistry, context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    failure = _fail(
        _gateway(model_registry, adapter), _request(budget_reservation_id="RSV-other"), context
    )
    assert failure.reason == "reservation_mismatch"
    _nothing_sent(adapter, journal)


def test_budget_preflight_refuses_a_call_the_reservation_cannot_cover(
    model_registry: ModelRegistry, scope: Any, journal: InMemoryCallJournal
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    context = ExecutionContext(
        scope=scope,
        runtime_version="rv",
        journal=journal,
        reservation=ReservationView(reservation_id="RSV-1", amount_usd=0.0001),
    )
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.failure is FailureClass.BUDGET_EXCEEDED
    assert failure.reason == "reservation_exhausted"
    _nothing_sent(adapter, journal)
    # Budget parks and asks; it is not a failed attempt.
    decision = decide_recovery(
        failure=failure.failure,
        attempt_number=1,
        paid_call_dispatched=False,
        paid_call_outcome_known=True,
    )
    assert decision.step_status is StepRunStatus.AWAITING_BUDGET


def test_output_limit_above_the_model_is_refused_not_capped(
    model_registry: ModelRegistry, context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    failure = _fail(_gateway(model_registry, adapter), _request(max_output_tokens=100_000), context)
    assert failure.reason == "output_limit_exceeds_model"
    _nothing_sent(adapter, journal)


def test_missing_adapter_fails_closed(
    model_registry: ModelRegistry, context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    failure = _fail(_gateway(model_registry), _request(), context)
    assert failure.reason == "no_adapter_for_route"
    assert journal.dispatched == []


def test_cancellation_is_honoured_before_dispatch(
    model_registry: ModelRegistry, scope: Any, journal: InMemoryCallJournal
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    context = ExecutionContext(
        scope=scope,
        runtime_version="rv",
        journal=journal,
        reservation=ReservationView(reservation_id="RSV-1", amount_usd=5.0),
        is_cancelled=lambda: True,
    )
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.failure is FailureClass.CANCELLED
    _nothing_sent(adapter, journal)


def test_invoke_requires_an_execution_context(model_registry: ModelRegistry) -> None:
    gateway = _gateway(model_registry)
    with pytest.raises(TypeError):
        asyncio.run(gateway.invoke(_request(), {"study_id": "STU-x"}))  # type: ignore[arg-type]


def test_adapter_bound_to_an_unknown_or_mismatched_route_is_refused(
    model_registry: ModelRegistry,
) -> None:
    with pytest.raises(ValueError, match="unknown route"):
        GovernedModelGateway(
            registry=model_registry,
            egress=EGRESS,
            adapters={"nowhere": ScriptedAdapter(Provider.OPENAI, [])},
        )
    with pytest.raises(ValueError, match="carries anthropic"):
        GovernedModelGateway(
            registry=model_registry,
            egress=EGRESS,
            adapters={"anthropic-direct": ScriptedAdapter(Provider.OPENAI, [])},
        )


def _two_openai_routes(document: dict[str, Any]) -> tuple[ModelRegistry, EgressPolicy]:
    """A policy whose CRITIC binding uses a second OpenAI route."""
    from aia_core.domain.ai_models import parse_model_config

    document["policies"][0]["bindings"]["CRITIC"]["route_id"] = "openai-eu"
    egress = EgressPolicy(
        routes=(*EGRESS.routes, _route("openai-eu", "openai")),
    )
    return parse_model_config(document), egress


def test_each_route_uses_its_own_adapter(
    model_config_document: dict[str, Any], context: ExecutionContext
) -> None:
    """Codex P1 on #28: the same provider over two routes is two residency
    answers. The call authorised for one route must leave over that route's
    adapter, not over whichever adapter happens to speak the same provider."""
    registry, egress = _two_openai_routes(model_config_document)
    direct = ScriptedAdapter(Provider.OPENAI, [_ok()])
    eu = ScriptedAdapter(Provider.OPENAI, [_ok()])
    gateway = GovernedModelGateway(
        registry=registry, egress=egress, adapters={"openai-direct": direct, "openai-eu": eu}
    )
    result = _run(gateway, _request(), context)
    assert result.provenance.route_id == "openai-eu"
    assert len(eu.requests) == 1
    assert direct.requests == []


def test_unbound_route_does_not_borrow_another_routes_adapter(
    model_config_document: dict[str, Any], context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    registry, egress = _two_openai_routes(model_config_document)
    direct = ScriptedAdapter(Provider.OPENAI, [_ok()])
    gateway = GovernedModelGateway(
        registry=registry, egress=egress, adapters={"openai-direct": direct}
    )
    failure = _fail(gateway, _request(), context)
    assert failure.reason == "no_adapter_for_route"
    _nothing_sent(direct, journal)


# --------------------------------------------------------------------------- #
# Provider failures: classified, recorded, never routed around
# --------------------------------------------------------------------------- #


def _provider_error(kind: ProviderErrorKind, delivery: Delivery, **kwargs: Any) -> ProviderError:
    return ProviderError(f"{kind.value} happened", kind=kind, delivery=delivery, **kwargs)


def test_quota_parks_in_waiting_provider_with_its_reset_and_request_id(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    """The reference's WAITING_CREDITS. Not a failed attempt; a scheduled resume."""
    reset = datetime(2026, 9, 23, 3, 0, tzinfo=UTC)
    adapter = ScriptedAdapter(
        Provider.OPENAI,
        [
            _provider_error(
                ProviderErrorKind.QUOTA,
                Delivery.RESPONDED,
                provider_request_id="req_quota",
                retry_after=reset,
            )
        ],
    )
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.failure is FailureClass.QUOTA
    assert failure.error_kind is ProviderErrorKind.QUOTA
    assert failure.provider_request_id == "req_quota"
    assert failure.outcome_known is True
    assert [e.outcome for e in failure.usage_events] == [
        UsageOutcome.DISPATCHED,
        UsageOutcome.FAILED,
    ]
    assert failure.usage_events[-1].provider_request_id == "req_quota"

    inputs = recovery_inputs(failure)
    decision = decide_recovery(
        failure=inputs.failure,
        attempt_number=1,
        paid_call_dispatched=True,
        paid_call_outcome_known=True,
        quota_reset_at=inputs.quota_reset_at,
    )
    assert decision.action is RecoveryAction.PARK_PROVIDER
    assert decision.step_status is StepRunStatus.WAITING_PROVIDER
    assert decision.retry_after == reset
    assert decision.consumes_attempt is False


def test_capacity_parks_in_waiting_capacity(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    adapter = ScriptedAdapter(
        Provider.OPENAI, [_provider_error(ProviderErrorKind.CAPACITY, Delivery.RESPONDED)]
    )
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    decision = decide_recovery(
        failure=failure.failure,
        attempt_number=1,
        paid_call_dispatched=True,
        paid_call_outcome_known=failure.outcome_known,
    )
    assert decision.step_status is StepRunStatus.WAITING_CAPACITY
    # Exactly one call: no hidden in-call retry (ADR 0005 condition 1).
    assert len(adapter.requests) == 1


@pytest.mark.parametrize(
    "kind",
    [ProviderErrorKind.AUTHENTICATION, ProviderErrorKind.PERMISSION, ProviderErrorKind.MISSING],
)
def test_misconfiguration_is_terminal(
    model_registry: ModelRegistry, context: ExecutionContext, kind: ProviderErrorKind
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_provider_error(kind, Delivery.RESPONDED)])
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.failure.is_permanent


def test_unknown_delivery_on_a_paid_call_is_uncertain_and_carried_at_ceiling(
    model_registry: ModelRegistry, context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    """The worker-killed case, survived: the request left, no answer came back."""
    adapter = ScriptedAdapter(
        Provider.OPENAI, [_provider_error(ProviderErrorKind.TRANSPORT, Delivery.UNKNOWN)]
    )
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.outcome_known is False
    assert failure.paid_call_dispatched is True
    terminal = failure.usage_events[-1]
    assert terminal.outcome is UsageOutcome.UNCERTAIN
    assert terminal.cost_basis is CostBasis.CEILING
    assert terminal.cost_usd == pytest.approx(journal.dispatched[0].ceiling_usd)
    # Money that may be gone is not headroom.
    assert journal.committed_usd() == pytest.approx(terminal.cost_usd)

    decision = decide_recovery(
        failure=failure.failure,
        attempt_number=1,
        paid_call_dispatched=True,
        paid_call_outcome_known=False,
    )
    assert decision.action is RecoveryAction.RECOVERY_REQUIRED
    assert decision.settle_reservation_as_uncertain is True


def test_adapter_defect_after_dispatch_is_uncertain_not_retryable(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [RuntimeError("boom")])
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.failure is FailureClass.UNKNOWN
    assert failure.reason == "adapter_error"
    assert failure.outcome_known is False
    assert failure.usage_events[-1].outcome is UsageOutcome.UNCERTAIN


def test_known_transport_failure_before_send_costs_nothing(
    model_registry: ModelRegistry, context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    adapter = ScriptedAdapter(
        Provider.OPENAI, [_provider_error(ProviderErrorKind.TRANSPORT, Delivery.NOT_SENT)]
    )
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.outcome_known is True
    assert failure.failure is FailureClass.TRANSPORT
    assert journal.committed_usd() == 0.0


# --------------------------------------------------------------------------- #
# Fallback: explicit or not at all
# --------------------------------------------------------------------------- #


ANTHROPIC_CRITIC = ModelBinding(
    provider=Provider.ANTHROPIC, model="reasoning-large-v2", route_id="anthropic-direct"
)


def test_no_fallback_without_an_explicit_policy(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    """The governing rule. Capacity on the primary parks; the permitted
    alternative is not tried because nobody authorised it."""
    primary = ScriptedAdapter(
        Provider.OPENAI, [_provider_error(ProviderErrorKind.CAPACITY, Delivery.RESPONDED)]
    )
    alternative = ScriptedAdapter(Provider.ANTHROPIC, [_ok()])
    failure = _fail(_gateway(model_registry, primary, alternative), _request(), context)
    assert failure.failure is FailureClass.PROVIDER_CAPACITY
    assert alternative.requests == []


def test_explicit_fallback_runs_and_is_recorded(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    primary = ScriptedAdapter(
        Provider.OPENAI,
        [
            _provider_error(
                ProviderErrorKind.CAPACITY, Delivery.RESPONDED, provider_request_id="req_busy"
            )
        ],
    )
    alternative = ScriptedAdapter(Provider.ANTHROPIC, [_ok(provider_request_id="req_alt")])
    result = _run(
        _gateway(model_registry, primary, alternative),
        _request(
            fallback_policy=FallbackPolicy(
                alternates=(ANTHROPIC_CRITIC,),
                on=frozenset({ProviderErrorKind.CAPACITY}),
                authorised_by="user-lead",
            )
        ),
        context,
    )
    assert result.resolved_provider is Provider.ANTHROPIC
    assert result.provider_request_id == "req_alt"
    assert result.provenance.fallback_from == "openai:extraction-small@openai-direct"
    assert result.provenance.fallback_authorised_by == "user-lead"
    outcomes = [(e.provider, e.outcome, e.purpose) for e in result.usage_events]
    assert outcomes == [
        (Provider.OPENAI, UsageOutcome.DISPATCHED, CallPurpose.PRIMARY),
        (Provider.OPENAI, UsageOutcome.FAILED, CallPurpose.PRIMARY),
        (Provider.ANTHROPIC, UsageOutcome.DISPATCHED, CallPurpose.FALLBACK),
        (Provider.ANTHROPIC, UsageOutcome.SUCCEEDED, CallPurpose.FALLBACK),
    ]
    # The failed primary's request id survives in the ledger.
    assert result.usage_events[1].provider_request_id == "req_busy"


def test_fallback_does_not_cover_kinds_it_does_not_name(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    primary = ScriptedAdapter(
        Provider.OPENAI, [_provider_error(ProviderErrorKind.QUOTA, Delivery.RESPONDED)]
    )
    alternative = ScriptedAdapter(Provider.ANTHROPIC, [_ok()])
    failure = _fail(
        _gateway(model_registry, primary, alternative),
        _request(
            fallback_policy=FallbackPolicy(
                alternates=(ANTHROPIC_CRITIC,),
                on=frozenset({ProviderErrorKind.CAPACITY}),
                authorised_by="user-lead",
            )
        ),
        context,
    )
    assert failure.failure is FailureClass.QUOTA
    assert alternative.requests == []


def test_no_fallback_while_the_failed_call_may_have_been_billed(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    """Even an authorised fallback waits for a person when the first call's
    outcome is unknown: it may already have done -- and charged for -- the work."""
    primary = ScriptedAdapter(
        Provider.OPENAI, [_provider_error(ProviderErrorKind.TRANSPORT, Delivery.UNKNOWN)]
    )
    alternative = ScriptedAdapter(Provider.ANTHROPIC, [_ok()])
    failure = _fail(
        _gateway(model_registry, primary, alternative),
        _request(
            fallback_policy=FallbackPolicy(
                alternates=(ANTHROPIC_CRITIC,),
                on=frozenset({ProviderErrorKind.TRANSPORT}),
                authorised_by="user-lead",
            )
        ),
        context,
    )
    assert failure.outcome_known is False
    assert alternative.requests == []


def test_fallback_to_a_binding_the_policy_does_not_permit_is_refused(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    primary = ScriptedAdapter(
        Provider.OPENAI, [_provider_error(ProviderErrorKind.CAPACITY, Delivery.RESPONDED)]
    )
    alternative = ScriptedAdapter(Provider.CLAUDE_CODE, [_ok()])
    failure = _fail(
        _gateway(model_registry, primary, alternative),
        _request(
            fallback_policy=FallbackPolicy(
                alternates=(
                    ModelBinding(
                        provider=Provider.CLAUDE_CODE,
                        model="subscription-default",
                        route_id="claude-code-cli",
                    ),
                ),
                on=frozenset({ProviderErrorKind.CAPACITY}),
                authorised_by="user-lead",
            )
        ),
        context,
    )
    assert failure.reason == "fallback_resolution_model_not_permitted"
    assert alternative.requests == []
    # The primary's ledger entries are still on the failure.
    assert len(failure.usage_events) == 2


# --------------------------------------------------------------------------- #
# Structured output: one repair, then fail
# --------------------------------------------------------------------------- #


def test_one_same_model_repair_is_made_and_recorded(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    adapter = ScriptedAdapter(
        Provider.OPENAI,
        [_ok('{"verdict": "fine", "score": "7"}'), _ok('{"verdict": "fine", "score": 7}')],
    )
    result = _run(_gateway(model_registry, adapter), _request(), context)
    assert isinstance(result.output, Answer)
    assert [r.model for r in adapter.requests] == ["extraction-small", "extraction-small"]

    repair = adapter.requests[1]
    assert repair.messages[-2].role == "assistant"
    assert "score: Input should be a valid integer" in repair.messages[-1].content

    terminal = [e for e in result.usage_events if e.outcome.is_terminal]
    assert [(e.outcome, e.purpose) for e in terminal] == [
        (UsageOutcome.FAILED, CallPurpose.PRIMARY),
        (UsageOutcome.SUCCEEDED, CallPurpose.SCHEMA_REPAIR),
    ]
    assert terminal[0].error_kind is ProviderErrorKind.SCHEMA
    assert terminal[1].note == f"repair_prompt={REPAIR_PROMPT_VERSION}"
    # Both calls were billed, so both are counted.
    assert result.total_cost_usd == pytest.approx(2 * result.actual_cost_usd)


def test_second_violation_fails_with_the_violations(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok("nope"), _ok('{"verdict": 1}')])
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.failure is FailureClass.SCHEMA_VIOLATION
    assert failure.error_kind is ProviderErrorKind.SCHEMA
    assert failure.violations
    assert len(adapter.requests) == 2


def test_agent_without_repair_fails_on_the_first_violation(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok("nope"), _ok()])
    failure = _fail(
        _gateway(model_registry, adapter),
        _request(agent=_agent(schema_repair_attempts=0)),
        context,
    )
    assert failure.failure is FailureClass.SCHEMA_VIOLATION
    assert len(adapter.requests) == 1


def test_truncated_structured_output_is_a_violation(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    adapter = ScriptedAdapter(
        Provider.OPENAI,
        [
            _ok(finish_reason=FinishReason.TRUNCATED),
            _ok(finish_reason=FinishReason.TRUNCATED),
        ],
    )
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.violations == ("output truncated at the output token limit",)


def test_repair_is_budget_checked_like_any_call(
    model_registry: ModelRegistry, scope: Any, journal: InMemoryCallJournal
) -> None:
    """The reservation covers one call at its ceiling but not a second."""
    probe = AdapterRequest(
        call_id="probe",
        provider=Provider.OPENAI,
        model="extraction-small",
        system=_request().system,
        messages=_request().messages,
        max_output_tokens=1000,
        output_schema=_agent().schema,
    )
    one_ceiling = (0.15 * input_token_bound(probe) + 0.6 * 1000) / 1_000_000
    context = ExecutionContext(
        scope=scope,
        runtime_version="rv",
        journal=journal,
        reservation=ReservationView(reservation_id="RSV-1", amount_usd=one_ceiling * 1.5),
    )
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok("nope", usage=ModelUsage()), _ok()])
    failure = _fail(_gateway(model_registry, adapter), _request(), context)
    assert failure.failure is FailureClass.BUDGET_EXCEEDED
    assert len(adapter.requests) == 1


# --------------------------------------------------------------------------- #
# The input bound
# --------------------------------------------------------------------------- #


def test_input_bound_is_never_below_the_content_bytes() -> None:
    request = AdapterRequest(
        call_id="c",
        provider=Provider.OPENAI,
        model="m",
        system="Příliš žluťoučký kůň",
        messages=(Message(role="user", content="úpěl ďábelské ódy" * 50),),
        max_output_tokens=10,
    )
    content = len(request.system.encode()) + len(request.messages[0].content.encode())
    assert input_token_bound(request) > content


def test_clock_drives_ledger_timestamps_and_latency(
    model_registry: ModelRegistry, scope: Any, journal: InMemoryCallJournal
) -> None:
    ticks = iter(datetime(2026, 9, 22, 12, 0, tzinfo=UTC) + timedelta(seconds=i) for i in range(10))
    context = ExecutionContext(
        scope=scope,
        runtime_version="rv",
        journal=journal,
        reservation=ReservationView(reservation_id="RSV-1", amount_usd=5.0),
        clock=lambda: next(ticks),
    )
    result = _run(
        _gateway(model_registry, ScriptedAdapter(Provider.OPENAI, [_ok()])), _request(), context
    )
    assert result.latency_ms == 1000
    assert result.usage_events[0].occurred_at < result.usage_events[1].occurred_at


def test_schema_name_is_provider_safe(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    _run(
        _gateway(model_registry, adapter),
        _request(agent=_agent(agent_id="critic.agent/v2 ü" + "x" * 80)),
        context,
    )
    name = adapter.requests[0].schema_name
    assert len(name) == 64
    assert all(c.isascii() and (c.isalnum() or c == "_") for c in name)


def test_every_call_records_the_fingerprint_of_its_own_inputs(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    """Codex P2 on #28: a primary call and its repair send different messages,
    so they must be distinguishable in the ledger by what they sent."""
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok('{"verdict": "fine", "score": "7"}'), _ok()])
    result = _run(_gateway(model_registry, adapter), _request(), context)
    primary, repair = (
        [e for e in result.usage_events if e.call_id == call]
        for call in dict.fromkeys(e.call_id for e in result.usage_events)
    )
    assert {e.input_fingerprint for e in primary} == {primary[0].input_fingerprint}
    assert {e.input_fingerprint for e in repair} == {repair[0].input_fingerprint}
    assert primary[0].input_fingerprint != repair[0].input_fingerprint
    assert primary[0].input_fingerprint.startswith("sha256:")
    assert result.provenance.input_fingerprint == repair[0].input_fingerprint

    again = ScriptedAdapter(Provider.OPENAI, [_ok()])
    same = _run(_gateway(model_registry, again), _request(), context)
    assert same.provenance.input_fingerprint == primary[0].input_fingerprint
