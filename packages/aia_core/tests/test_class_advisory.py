"""Advisory data class gates (plan ``develop-class-advisory``; the product owner, 2026-10-21).

``AIA_DATA_CLASS_GATES=advisory`` -- develop only -- turns every refusal made solely because of
a data class into a recorded pass. These tests hold each gate in both modes: enforce refuses
exactly as before (the existing suites are unchanged), advisory passes and records what enforce
would have refused, and EU residency, licences, budgets and scope refuse in both.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.application.web_retrieval import RetrievalGate, RunSnapshotCache, WebRetrieval
from aia_core.domain.ai_contracts import (
    AdapterRequest,
    AdapterResponse,
    AgentDefinition,
    FinishReason,
    Message,
    ModelCallFailed,
    ModelRequest,
    ModelUsage,
)
from aia_core.domain.ai_execution import ExecutionContext, ReservationView
from aia_core.domain.ai_models import ModelCapability, ModelRegistry
from aia_core.domain.deep_research.contracts import ClientTerm, QueryDecision, RetrievalMode
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
)
from aia_core.domain.deployment import (
    DataClassGates,
    DeploymentEnvironment,
    data_class_gates_problem,
    parse_data_class_gates,
)
from aia_core.domain.licence import DataLineage
from aia_core.domain.licence_determinations import recorded_policy
from aia_core.domain.providers import Provider
from aia_core.domain.residency import (
    ClassAdvisory,
    DataClass,
    EgressDenied,
    EgressPolicy,
    ProviderRoute,
    ResidencyZone,
    evaluate_egress,
)
from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedFetchTransport,
    RecordedResolver,
    RecordedSearch,
    WebFetcher,
)

# --------------------------------------------------------------------------- helpers
#
# Kept here rather than imported from another test module: both test directories are called
# ``tests`` and are not packages, so an import between test modules resolves by whichever root
# pytest picks (AGENTS.md § pytest). Shaped as test_model_gateway.py's and test_web_retrieval.py's.

POLICY = "policy-test-v1"
LICENCE = recorded_policy()
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
PUBLIC = "93.184.215.14"
PAGE = """<!doctype html><html><head><title>Spotřeba nápojů 2025</title></head>
<body><h1>Trh</h1><p>Spotřeba rostlinných nápojů vzrostla o 12,5 %.</p></body></html>"""
HITS: dict[str, Any] = {
    "spotřeba rostlinných nápojů česko": {
        "hits": [{"url": "https://stats.example/a"}],
        "credits": 1,
    }
}


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str
    score: int


class ScriptedAdapter:
    """Answers from a script; records what it was sent."""

    def __init__(self, provider: Provider, script: list[AdapterResponse]) -> None:
        self._provider = provider
        self._script = list(script)
        self.requests: list[AdapterRequest] = []

    @property
    def provider(self) -> Provider:
        return self._provider

    async def send(self, request: AdapterRequest) -> AdapterResponse:
        self.requests.append(request)
        return self._script.pop(0)


def _ok() -> AdapterResponse:
    return AdapterResponse(
        text='{"verdict": "fine", "score": 7}',
        finish_reason=FinishReason.COMPLETED,
        usage=ModelUsage(input_tokens=1000, output_tokens=200),
        provider_request_id="req_ok",
        served_model="served-id",
    )


def _request(**overrides: Any) -> ModelRequest:
    base: dict[str, Any] = {
        "agent": AgentDefinition(
            agent_id="critic-agent",
            version="3",
            capability=ModelCapability.CRITIC,
            prompt_id="critic",
            prompt_version="2",
            output_contract=Answer,
            max_output_tokens=1000,
        ),
        "policy_version": POLICY,
        "data_classification": DataClass.CLASS_C_INTERNAL,
        "data_lineage": DataLineage.none(),
        "system": "Review the argument.",
        "messages": (Message(role="user", content="The argument."),),
    }
    return ModelRequest(**{**base, **overrides})


def _fetcher(pages: dict[str, dict[str, Any]]) -> tuple[WebFetcher, RecordedFetchTransport]:
    transport = RecordedFetchTransport(pages=pages)
    resolver = RecordedResolver(hosts={"stats.example": [PUBLIC]})
    return (
        WebFetcher(
            transport=transport,
            resolver=resolver,
            adapter_id="recorded-fetch-v1",
            clock=lambda: NOW,
        ),
        transport,
    )


class _LiveTransport:
    """A fetch transport presented as live, never asked: a live route's shape."""

    retrieval_mode = RetrievalMode.LIVE

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        raise AssertionError("nothing is fetched in this test")


ADVISORY = DataClassGates.ADVISORY
ENFORCE = DataClassGates.ENFORCE

# --------------------------------------------------------------------------- the switch


@pytest.mark.parametrize(
    ("raw", "gates"),
    [(None, ENFORCE), ("", ENFORCE), ("  ", ENFORCE), ("enforce", ENFORCE), ("Advisory", ADVISORY)],
)
def test_the_switch_is_enforce_unless_it_says_advisory(raw: str | None, gates: Any) -> None:
    assert parse_data_class_gates(raw) is gates


def test_a_value_that_is_not_a_mode_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="AIA_DATA_CLASS_GATES='lenient' is not one of"):
        parse_data_class_gates("lenient")


@pytest.mark.parametrize(
    "environment",
    [DeploymentEnvironment.LOCAL, DeploymentEnvironment.TEST, DeploymentEnvironment.DEVELOP],
)
def test_advisory_is_allowed_in_local_test_and_develop(environment: Any) -> None:
    assert data_class_gates_problem(environment, ADVISORY) is None


@pytest.mark.parametrize(
    "environment", [DeploymentEnvironment.STAGING, DeploymentEnvironment.PRODUCTION, None]
)
def test_advisory_is_refused_in_staging_production_and_an_unknown_environment(
    environment: Any,
) -> None:
    problem = data_class_gates_problem(environment, ADVISORY)
    assert problem is not None and "AIA_DATA_CLASS_GATES=advisory is refused" in problem
    assert data_class_gates_problem(environment, ENFORCE) is None


def test_an_advisory_says_its_gate_rule_and_class() -> None:
    advisory = ClassAdvisory(
        "egress", "route_not_approved_for_class", DataClass.CLASS_B_DERIVED_CLIENT
    )
    assert advisory.note() == (
        "class_advisory gate=egress rule=route_not_approved_for_class "
        "class=CLASS_B_DERIVED_CLIENT advisory=true"
    )
    assert ClassAdvisory("egress", "unclassified_material", None).record() == {
        "gate": "egress",
        "rule": "unclassified_material",
        "data_class": None,
        "advisory": True,
    }


# --------------------------------------------------------------------------- egress


def _route(**overrides: Any) -> ProviderRoute:
    base: dict[str, Any] = {
        "route_id": "eu-internal-only",
        "provider": "openai",
        "zone": ResidencyZone.EU,
        "eu_processing_approved": True,
        "excluded_from_training": True,
        "retention_days": 0,
        "approved_for": frozenset({DataClass.CLASS_C_INTERNAL}),
    }
    return ProviderRoute(**{**base, **overrides})


@pytest.fixture
def scope(scoped: Any) -> Any:
    return scoped.scope(user="researcher", study="primary")


@pytest.mark.parametrize(
    ("data_class", "reason"),
    [
        (None, "unclassified_material"),
        (DataClass.CLASS_B_DERIVED_CLIENT, "route_not_approved_for_class"),
        (DataClass.CLASS_A_CLIENT_CONFIDENTIAL, "route_not_approved_for_class"),
    ],
)
def test_enforce_refuses_a_class_only_egress_as_it_always_has(
    scope: Any, data_class: DataClass | None, reason: str
) -> None:
    with pytest.raises(EgressDenied) as denied:
        evaluate_egress(scope=scope, data_class=data_class, route=_route())
    assert denied.value.reason == reason
    with pytest.raises(EgressDenied):
        evaluate_egress(scope=scope, data_class=data_class, route=_route(), class_gates=ENFORCE)


def test_advisory_passes_a_class_the_route_is_not_approved_for_and_records_it(scope: Any) -> None:
    decision = evaluate_egress(
        scope=scope,
        data_class=DataClass.CLASS_B_DERIVED_CLIENT,
        route=_route(),
        class_gates=ADVISORY,
    )
    assert decision.data_class is DataClass.CLASS_B_DERIVED_CLIENT
    assert decision.advisories == (
        ClassAdvisory("egress", "route_not_approved_for_class", DataClass.CLASS_B_DERIVED_CLIENT),
    )


def test_advisory_judges_unclassified_material_as_class_a_and_records_both_refusals(
    scope: Any,
) -> None:
    decision = evaluate_egress(scope=scope, data_class=None, route=_route(), class_gates=ADVISORY)
    # Unknown is never the permissive answer: judged as A for every residency check.
    assert decision.data_class is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    assert [(a.rule, a.data_class) for a in decision.advisories] == [
        ("unclassified_material", None),
        ("route_not_approved_for_class", None),
    ]
    approved = _route(approved_for=frozenset(DataClass))
    only = evaluate_egress(scope=scope, data_class=None, route=approved, class_gates=ADVISORY)
    assert [a.rule for a in only.advisories] == ["unclassified_material"]


def test_advisory_records_nothing_for_a_call_enforce_allows(scope: Any) -> None:
    decision = evaluate_egress(
        scope=scope, data_class=DataClass.CLASS_C_INTERNAL, route=_route(), class_gates=ADVISORY
    )
    assert decision.advisories == ()


@pytest.mark.parametrize(
    ("route", "data_class", "reason"),
    [
        (
            _route(zone=ResidencyZone.NON_EU),
            DataClass.CLASS_B_DERIVED_CLIENT,
            "residency_violation",
        ),
        (_route(zone=ResidencyZone.NON_EU), None, "residency_violation"),
        (_route(eu_processing_approved=False), None, "residency_violation"),
        (
            _route(excluded_from_training=False),
            DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            "training_exclusion_missing",
        ),
        (_route(retention_days=None), DataClass.CLASS_B_DERIVED_CLIENT, "retention_unspecified"),
        (None, DataClass.CLASS_B_DERIVED_CLIENT, "no_approved_route"),
    ],
)
def test_advisory_still_enforces_eu_residency_and_needs_a_route(
    scope: Any, route: ProviderRoute | None, data_class: DataClass | None, reason: str
) -> None:
    with pytest.raises(EgressDenied) as denied:
        evaluate_egress(scope=scope, data_class=data_class, route=route, class_gates=ADVISORY)
    assert denied.value.reason == reason


def test_advisory_still_needs_an_issued_scope() -> None:
    with pytest.raises(EgressDenied) as denied:
        evaluate_egress(scope=object(), data_class=None, route=_route(), class_gates=ADVISORY)  # type: ignore[arg-type]
    assert denied.value.reason == "unauthorised_scope"


def test_the_policy_passes_its_mode_through(scope: Any) -> None:
    policy = EgressPolicy(routes=(_route(),))
    with pytest.raises(EgressDenied):
        policy.authorise(scope=scope, data_class=None, route_id="eu-internal-only")
    decision = policy.authorise(
        scope=scope, data_class=None, route_id="eu-internal-only", class_gates=ADVISORY
    )
    assert decision.advisories


# --------------------------------------------------------------------------- the gateway


def _gateway(
    registry: ModelRegistry,
    adapter: ScriptedAdapter,
    *,
    gates: DataClassGates,
    route: ProviderRoute,
) -> GovernedModelGateway:
    return GovernedModelGateway(
        registry=registry,
        egress=EgressPolicy(routes=(route,)),
        licence=LICENCE,
        adapters={route.route_id: adapter},
        class_gates=gates,
    )


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


#: The registry's OpenAI binding rides this route id; here an EU route approved for C alone.
EU_C_ONLY = _route(route_id="openai-direct", provider="openai")


@pytest.mark.parametrize(
    ("data_class", "reason"),
    [
        (None, "egress_unclassified_material"),
        (DataClass.CLASS_B_DERIVED_CLIENT, "egress_route_not_approved_for_class"),
    ],
)
def test_the_gateway_under_enforce_refuses_and_sends_nothing(
    model_registry: ModelRegistry,
    context: ExecutionContext,
    journal: InMemoryCallJournal,
    data_class: DataClass | None,
    reason: str,
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    gateway = _gateway(model_registry, adapter, gates=ENFORCE, route=EU_C_ONLY)
    assert gateway.class_gates is ENFORCE
    for call in (gateway.preflight, gateway.invoke):
        with pytest.raises(ModelCallFailed) as failed:
            outcome = call(_request(data_classification=data_class), context)
            if asyncio.iscoroutine(outcome):
                asyncio.run(outcome)
        assert failed.value.reason == reason
    assert adapter.requests == [] and journal.dispatched == []


def test_the_gateway_under_advisory_sends_unclassified_material_and_writes_it_on_every_row(
    model_registry: ModelRegistry, context: ExecutionContext, journal: InMemoryCallJournal
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    gateway = _gateway(model_registry, adapter, gates=ADVISORY, route=EU_C_ONLY)
    request = _request(data_classification=None)
    gateway.preflight(request, context)  # the preflight passes as invoke will
    result = asyncio.run(gateway.invoke(request, context))
    assert len(adapter.requests) == 1
    expected = (
        "class_advisory gate=egress rule=unclassified_material class=unclassified advisory=true",
        "class_advisory gate=egress rule=route_not_approved_for_class class=unclassified "
        "advisory=true",
    )
    assert result.provenance.class_advisories == expected
    assert result.provenance.data_class is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    assert len(result.usage_events) == 2
    for event in result.usage_events:
        assert event.data_class is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
        assert all(note in event.note for note in expected)


def test_the_gateway_under_advisory_records_a_class_the_route_does_not_carry(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    gateway = _gateway(model_registry, adapter, gates=ADVISORY, route=EU_C_ONLY)
    result = asyncio.run(
        gateway.invoke(_request(data_classification=DataClass.CLASS_B_DERIVED_CLIENT), context)
    )
    assert result.provenance.data_class is DataClass.CLASS_B_DERIVED_CLIENT
    assert result.provenance.class_advisories == (
        "class_advisory gate=egress rule=route_not_approved_for_class "
        "class=CLASS_B_DERIVED_CLIENT advisory=true",
    )


def test_the_gateway_under_advisory_records_nothing_for_an_approved_class(
    model_registry: ModelRegistry, context: ExecutionContext
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    gateway = _gateway(model_registry, adapter, gates=ADVISORY, route=EU_C_ONLY)
    result = asyncio.run(gateway.invoke(_request(), context))
    assert result.provenance.class_advisories == ()
    assert all("class_advisory" not in e.note for e in result.usage_events)


@pytest.mark.parametrize(
    ("route", "overrides", "reason"),
    [
        # EU residency: client material, or unclassified (judged A), never leaves the EU.
        (
            _route(route_id="openai-direct", zone=ResidencyZone.NON_EU),
            {"data_classification": None},
            "egress_residency_violation",
        ),
        (
            _route(route_id="openai-direct", zone=ResidencyZone.NON_EU),
            {"data_classification": DataClass.CLASS_B_DERIVED_CLIENT},
            "egress_residency_violation",
        ),
        # The licence gate is not a class gate.
        (
            EU_C_ONLY,
            {"data_classification": None, "data_lineage": None},
            "licence_lineage_undeclared",
        ),
        (
            EU_C_ONLY,
            {"data_lineage": DataLineage.of("czech_population_panel")},
            "licence_not_approved_for_route",
        ),
    ],
)
def test_the_gateway_under_advisory_still_enforces_residency_and_licence(
    model_registry: ModelRegistry,
    context: ExecutionContext,
    journal: InMemoryCallJournal,
    route: ProviderRoute,
    overrides: dict[str, Any],
    reason: str,
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    gateway = _gateway(model_registry, adapter, gates=ADVISORY, route=route)
    with pytest.raises(ModelCallFailed) as failed:
        asyncio.run(gateway.invoke(_request(**overrides), context))
    assert failed.value.reason == reason
    assert adapter.requests == [] and journal.dispatched == []


def test_the_gateway_under_advisory_still_needs_a_reservation_for_a_metered_call(
    model_registry: ModelRegistry, scope: Any
) -> None:
    adapter = ScriptedAdapter(Provider.OPENAI, [_ok()])
    gateway = _gateway(model_registry, adapter, gates=ADVISORY, route=EU_C_ONLY)
    unreserved = ExecutionContext(
        scope=scope, runtime_version="runtime-test", journal=InMemoryCallJournal()
    )
    with pytest.raises(ModelCallFailed) as failed:
        asyncio.run(gateway.invoke(_request(data_classification=None), unreserved))
    assert failed.value.reason == "paid_call_without_reservation"
    assert adapter.requests == []


# --------------------------------------------------------------------------- the retrieval gate


def _tool_route(
    tool: ToolKind,
    *,
    zone: ResidencyZone = ResidencyZone.EU,
    approved: bool = True,
    any_class: bool = False,
    price: float = 0.0,
    mode: RetrievalMode = RetrievalMode.RECORDED,
) -> ToolRoute:
    recorded = mode is RetrievalMode.RECORDED
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"{tool.value}-{zone.value.lower()}",
            provider="recorded" if recorded else "live",
            zone=zone,
            eu_processing_approved=approved,
            excluded_from_training=approved,
            retention_days=0 if approved else None,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
        tool=tool,
        adapter_id=f"{'recorded' if recorded else 'live'}-{tool.value.split('_')[1]}-v1",
        retrieval_mode=mode,
        price_usd_per_call=price,
        any_class_when_advisory=any_class,
    )


def _gate(
    scope: Any,
    *,
    gates: DataClassGates,
    search_route: ToolRoute | None = None,
    meter: Any = None,
) -> tuple[RetrievalGate, Any, RecordedSearch]:
    search = RecordedSearch(adapter_id="recorded-search-v1", exchanges=dict(HITS))
    fetcher, _ = _fetcher({"https://stats.example/a": {"body": PAGE}})
    ledger = meter if meter is not None else InMemoryToolLedger(budget_usd=1.0)
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=search_route or _tool_route(ToolKind.WEB_SEARCH),
            fetch_route=_tool_route(ToolKind.WEB_FETCH),
            search=search,
            fetcher=fetcher,
        ),
        scope=scope,
        meter=ledger,
        client_terms=(ClientTerm(term="Acme Corp", source="client.name"),),
        class_a_texts=("klient plánuje zvýšit ceny prémiové řady o dvanáct procent",),
        clock=lambda: NOW,
        class_gates=gates,
    )
    return gate, ledger, search


QUERY = "spotřeba rostlinných nápojů česko"
CASES = [
    (DataClass.CLASS_B_DERIVED_CLIENT, "egress_route_not_approved_for_class"),
    (DataClass.CLASS_A_CLIENT_CONFIDENTIAL, "class_a_query"),
]


@pytest.mark.parametrize(("context_class", "reason"), CASES)
def test_the_retrieval_gate_under_enforce_refuses_a_class_only_query(
    scope: Any, context_class: DataClass, reason: str
) -> None:
    gate, ledger, search = _gate(scope, gates=ENFORCE)
    outcome = gate.search(QUERY, context_class=context_class, track_id="T", max_results=3)
    assert outcome.record.decision is QueryDecision.REFUSED and outcome.record.refusal == reason
    assert search.calls == [] and [e.outcome for e in ledger.events()] == [ToolOutcome.REFUSED]
    assert gate.refusal_for_class(context_class) == reason


@pytest.mark.parametrize(("context_class", "reason"), CASES)
def test_the_retrieval_gate_under_advisory_sends_it_and_records_the_refusal_it_lifted(
    scope: Any, context_class: DataClass, reason: str
) -> None:
    gate, ledger, search = _gate(scope, gates=ADVISORY)
    assert gate.refusal_for_class(context_class) is None
    outcome = gate.search(QUERY, context_class=context_class, track_id="T", max_results=3)
    assert outcome.record.decision is QueryDecision.SENT and search.calls == [QUERY]
    assert outcome.record.data_class is context_class  # the class is still computed and kept
    dispatched, succeeded = ledger.events()
    assert dispatched.outcome is ToolOutcome.DISPATCHED
    assert dispatched.note == ClassAdvisory("retrieval", reason, context_class).note()
    assert succeeded.outcome is ToolOutcome.SUCCEEDED and "class_advisory" not in succeeded.note


def test_the_retrieval_gate_under_advisory_records_nothing_for_a_public_query(scope: Any) -> None:
    gate, ledger, _ = _gate(scope, gates=ADVISORY)
    gate.search(QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T", max_results=3)
    assert [e.note for e in ledger.events()] == ["", ""]


def test_the_retrieval_gate_under_advisory_still_enforces_residency_off_the_brave_route(
    scope: Any,
) -> None:
    """A search route outside the EU that does not declare the exception (Wikipedia's) still
    refuses client material, now by the reason that holds: residency."""
    outside = _tool_route(ToolKind.WEB_SEARCH, zone=ResidencyZone.UNKNOWN, approved=False)
    gate, ledger, search = _gate(scope, gates=ADVISORY, search_route=outside)
    outcome = gate.search(
        QUERY, context_class=DataClass.CLASS_B_DERIVED_CLIENT, track_id="T", max_results=3
    )
    assert outcome.record.refusal == "egress_residency_violation"
    assert gate.refusal_for_class(DataClass.CLASS_B_DERIVED_CLIENT) == "egress_residency_violation"
    assert gate.refusal_for_class(DataClass.CLASS_A_CLIENT_CONFIDENTIAL) == (
        "egress_residency_violation"
    )
    assert search.calls == [] and [e.outcome for e in ledger.events()] == [ToolOutcome.REFUSED]


def _brave(**overrides: Any) -> ToolRoute:
    """Shaped as ``deep_research_live.brave_retrieval``'s search route: outside the EU, Class C
    only, nothing about its processing approved, the owner's exception declared."""
    return _tool_route(
        ToolKind.WEB_SEARCH,
        zone=ResidencyZone.NON_EU,
        approved=False,
        any_class=True,
        **overrides,
    )


@pytest.mark.parametrize(
    ("context_class", "query", "reason"),
    [
        (DataClass.CLASS_B_DERIVED_CLIENT, QUERY, "egress_route_not_approved_for_class"),
        (DataClass.CLASS_A_CLIENT_CONFIDENTIAL, QUERY, "class_a_query"),
        # A client term raises a public context's query to B; Class A overlap to A.
        (
            DataClass.CLASS_C_INTERNAL,
            "Acme Corp tržní podíl",
            "egress_route_not_approved_for_class",
        ),
    ],
)
def test_brave_under_enforce_refuses_any_class_but_c(
    scope: Any, context_class: DataClass, query: str, reason: str
) -> None:
    gate, ledger, search = _gate(scope, gates=ENFORCE, search_route=_brave())
    outcome = gate.search(query, context_class=context_class, track_id="T", max_results=3)
    assert outcome.record.refusal == reason and search.calls == []
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.REFUSED]


@pytest.mark.parametrize(
    ("context_class", "query", "data_class", "reason"),
    [
        (
            DataClass.CLASS_B_DERIVED_CLIENT,
            QUERY,
            DataClass.CLASS_B_DERIVED_CLIENT,
            "egress_route_not_approved_for_class",
        ),
        (
            DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            QUERY,
            DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            "class_a_query",
        ),
        (
            DataClass.CLASS_C_INTERNAL,
            "zvýšit ceny prémiové řady o dvanáct procent",
            DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            "class_a_query",
        ),
    ],
)
def test_brave_under_advisory_takes_a_query_of_any_class_and_records_it(
    scope: Any, context_class: DataClass, query: str, data_class: DataClass, reason: str
) -> None:
    gate, ledger, search = _gate(scope, gates=ADVISORY, search_route=_brave())
    assert gate.refusal_for_class(context_class) is None
    outcome = gate.search(query, context_class=context_class, track_id="T", max_results=3)
    assert outcome.record.decision is QueryDecision.SENT and search.calls == [query]
    assert outcome.record.data_class is data_class
    dispatched = ledger.events()[0]
    assert dispatched.outcome is ToolOutcome.DISPATCHED and dispatched.data_class is data_class
    assert dispatched.note == (
        f"class_advisory gate=retrieval rule={reason} class={data_class.value} advisory=true"
    )


def test_brave_under_advisory_is_still_metered_against_the_study(scope: Any) -> None:
    """Advisory lifts the class, never the price: a priced route whose meter cannot hold the
    study's budget is refused as before."""
    priced = _brave(price=0.005, mode=RetrievalMode.LIVE)
    search = RecordedSearch(adapter_id="recorded-search-v1", exchanges=dict(HITS))
    assert priced.needs_sign_off
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=priced,
            fetch_route=_tool_route(ToolKind.WEB_FETCH, price=0.0, mode=RetrievalMode.LIVE),
            search=_LiveSearch(search),
            fetcher=_live_fetcher(),
        ),
        scope=scope,
        meter=InMemoryToolLedger(budget_usd=1.0),  # holds a ceiling, charges no study
        client_terms=(),
        class_a_texts=(),
        class_gates=ADVISORY,
    )
    outcome = gate.search(
        QUERY, context_class=DataClass.CLASS_B_DERIVED_CLIENT, track_id="T", max_results=3
    )
    assert outcome.record.refusal == "tool_metering_unavailable"
    assert search.calls == []


def test_only_a_search_route_may_declare_the_exception() -> None:
    with pytest.raises(ValueError, match="only a web search route"):
        _tool_route(ToolKind.WEB_FETCH, any_class=True)


class _LiveSearch:
    """A recorded search presented as live, for a live route's shape (nothing is sent)."""

    adapter_id = "live-search-v1"
    retrieval_mode = RetrievalMode.LIVE

    def __init__(self, inner: RecordedSearch) -> None:
        self._inner = inner

    def search(self, query: str, *, max_results: int) -> Any:
        return self._inner.search(query, max_results=max_results)


def _live_fetcher() -> Any:
    return WebFetcher(
        transport=_LiveTransport(), resolver=RecordedResolver(hosts={}), adapter_id="live-fetch-v1"
    )


def _cached_gate(scope: Any, gates: DataClassGates) -> tuple[RetrievalGate, Any, Any]:
    fetcher, transport = _fetcher({"https://stats.example/acme-corp-results": {"body": PAGE}})
    ledger = InMemoryToolLedger(budget_usd=1.0)
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_tool_route(ToolKind.WEB_SEARCH),
            fetch_route=_tool_route(ToolKind.WEB_FETCH),
            search=RecordedSearch(adapter_id="recorded-search-v1", exchanges={}),
            fetcher=fetcher,
        ),
        scope=scope,
        meter=ledger,
        client_terms=(ClientTerm(term="Acme Corp", source="client.name"),),
        class_a_texts=(),
        clock=lambda: NOW,
        cache=RunSnapshotCache(),
        class_gates=gates,
    )
    return gate, ledger, transport


def test_a_url_enforce_refuses_is_never_fetched_nor_answered_from_the_cache(scope: Any) -> None:
    gate, ledger, transport = _cached_gate(scope, ENFORCE)
    for _ in range(2):
        refused = gate.fetch("https://stats.example/acme-corp-results", track_id="T")
        assert refused.reason == "egress_route_not_approved_for_class"
    assert transport.calls == []
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.REFUSED, ToolOutcome.REFUSED]


def test_a_page_served_from_the_cache_under_advisory_records_the_refusal_it_lifted(
    scope: Any,
) -> None:
    """Codex P2 on #594: the cached answer passed the same class gate as the dispatch, so it
    carries the same advisory; nothing advisory lets through goes unrecorded."""
    gate, ledger, transport = _cached_gate(scope, ADVISORY)
    url = "https://stats.example/acme-corp-results"
    first = gate.fetch(url, track_id="T")
    again = gate.fetch(url, track_id="T")
    assert first.page is not None and not first.cached
    assert again.page is not None and again.cached
    assert transport.calls == [url]  # the second was answered from the run's cache
    advisory = ClassAdvisory(
        "retrieval", "egress_route_not_approved_for_class", DataClass.CLASS_B_DERIVED_CLIENT
    ).note()
    events = ledger.events()
    assert [e.outcome for e in events] == [
        ToolOutcome.DISPATCHED,
        ToolOutcome.SUCCEEDED,
        ToolOutcome.CACHED,
    ]
    assert events[0].note == advisory
    assert events[2].note.startswith("run_snapshot_cache SNP-")
    assert events[2].note.endswith(advisory)
