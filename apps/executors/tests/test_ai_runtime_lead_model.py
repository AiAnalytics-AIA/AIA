"""The Research Lead's own model: ``STUDY_LEAD`` on ADR 0010's route (ADR 0026 amendment).

The product owner decided on 2026-10-19 that the study's Research Lead runs on a model of
its own while every other capability stays on the route's model. That model is configured,
never written in code: its pinned EU profile, its prices, its limits and its request profile
come from ``AIA_AI_RESEARCH_LEAD_MODEL_*`` keys, read only when the id is set, with no
default for any of them. Unset, the Lead's turns run on the route's model as before.

The ids and prices here are obviously fake. No network: a scripted transport stands in for
AWS.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aia_core.domain.ai_contracts import AgentDefinition, Message, ModelRequest
from aia_core.domain.ai_execution import ExecutionContext, ReservationView
from aia_core.domain.ai_models import (
    Effort,
    ModelCapability,
    RequestProfile,
    StructuredOutput,
    ThinkingMode,
    parse_model_config,
)
from aia_core.domain.deep_research.request_limits import ModelPrices, reservation_usd
from aia_core.domain.licence import DataLineage
from aia_core.domain.providers import Provider
from aia_core.domain.research_lead import lead_request_window_tokens
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal
from aia_core.infrastructure.model_adapters.transport import HttpRequest, HttpResponse
from aia_executors.ai_runtime import (
    AIRuntimeConfigError,
    AIRuntimeSettings,
    LeadModelSettings,
    LightModelSettings,
    build_gateway,
)
from pydantic import BaseModel, ConfigDict

ROUTE_MODEL = "eu.test.route-model:1"
LEAD_MODEL = "eu.test.lead-model:1"
LIGHT_MODEL = "eu.test.light-model:1"

ENV = {
    "AIA_ENV": "test",
    "AIA_AI_RUNTIME_ENABLED": "true",
    "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
    "AIA_BEDROCK_REGION": "eu-central-1",
    "AIA_BEDROCK_MODEL_ID": ROUTE_MODEL,
    "AIA_AI_POLICY_VERSION": "test-lead-model-v1",
    "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
    "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
    "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
    "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
    "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
    "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
    "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL",
    "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
    "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
    "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
    "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
    "AIA_AI_RESEARCH_RESERVATION_USD": "2",
    "AIA_AI_RESEARCH_LEAD_ENABLED": "true",
    "AIA_AI_RESEARCH_LEAD_MAX_OUTPUT_TOKENS": "1500",
    "AIA_AI_RESEARCH_LEAD_RESERVATION_USD": "5",
}

#: The Lead's own model, every key set: fake id, fake prices.
LEAD = {
    "AIA_AI_RESEARCH_LEAD_MODEL_ID": LEAD_MODEL,
    "AIA_AI_RESEARCH_LEAD_INPUT_USD_PER_MTOK": "7",
    "AIA_AI_RESEARCH_LEAD_OUTPUT_USD_PER_MTOK": "11",
    "AIA_AI_RESEARCH_LEAD_CACHE_READ_USD_PER_MTOK": "0.7",
    "AIA_AI_RESEARCH_LEAD_CACHE_WRITE_USD_PER_MTOK": "8.75",
    "AIA_AI_RESEARCH_LEAD_MODEL_MAX_OUTPUT_TOKENS": "64000",
    "AIA_AI_RESEARCH_LEAD_CONTEXT_WINDOW_TOKENS": "1000000",
    "AIA_AI_RESEARCH_LEAD_STRUCTURED_OUTPUT": "auto_tool",
    "AIA_AI_RESEARCH_LEAD_THINKING": "adaptive",
    "AIA_AI_RESEARCH_LEAD_EFFORT": "medium",
}

REQUIRED = [
    "AIA_AI_RESEARCH_LEAD_INPUT_USD_PER_MTOK",
    "AIA_AI_RESEARCH_LEAD_OUTPUT_USD_PER_MTOK",
    "AIA_AI_RESEARCH_LEAD_MODEL_MAX_OUTPUT_TOKENS",
    "AIA_AI_RESEARCH_LEAD_CONTEXT_WINDOW_TOKENS",
    "AIA_AI_RESEARCH_LEAD_STRUCTURED_OUTPUT",
    "AIA_AI_RESEARCH_LEAD_THINKING",
]


def _settings(**overrides: str) -> AIRuntimeSettings:
    settings = AIRuntimeSettings.from_env({**ENV, **overrides})
    assert settings is not None
    return settings


def _with_lead(**overrides: str) -> AIRuntimeSettings:
    return _settings(**{**LEAD, **overrides})


def _bindings(settings: AIRuntimeSettings, light: LightModelSettings | None = None) -> Any:
    return settings.model_document(light)["policies"][0]["bindings"]


# --------------------------------------------------------------------------- settings


def test_without_its_id_no_lead_model_is_read_and_the_lead_runs_on_the_route_model() -> None:
    # The other keys alone do nothing: the id is what turns the Lead's own model on.
    rest = {k: v for k, v in LEAD.items() if k != "AIA_AI_RESEARCH_LEAD_MODEL_ID"}
    settings = _settings(**rest)
    assert settings.lead_model is None and settings.study_lead_model is None
    assert settings.study_lead_context_window_tokens == settings.context_window_tokens
    assert _bindings(settings)[ModelCapability.STUDY_LEAD.value]["model"] == ROUTE_MODEL
    assert [m["model"] for m in settings.model_document()["models"]] == [ROUTE_MODEL]


def test_every_key_is_read_as_written() -> None:
    lead = _with_lead().lead_model
    assert lead == LeadModelSettings(
        model_id=LEAD_MODEL,
        input_usd_per_mtok=7.0,
        output_usd_per_mtok=11.0,
        cache_read_usd_per_mtok=0.7,
        cache_write_usd_per_mtok=8.75,
        max_output_tokens=64000,
        context_window_tokens=1000000,
        structured_output=StructuredOutput.AUTO_TOOL,
        thinking=ThinkingMode.ADAPTIVE,
        effort=Effort.MEDIUM,
    )
    without_effort = _with_lead(AIA_AI_RESEARCH_LEAD_EFFORT="").lead_model
    assert without_effort is not None and without_effort.effort is None
    cache_free = {
        k: v
        for k, v in LEAD.items()
        if k
        not in (
            "AIA_AI_RESEARCH_LEAD_CACHE_READ_USD_PER_MTOK",
            "AIA_AI_RESEARCH_LEAD_CACHE_WRITE_USD_PER_MTOK",
        )
    }
    optional = _settings(**cache_free).lead_model
    assert optional is not None
    assert (optional.cache_read_usd_per_mtok, optional.cache_write_usd_per_mtok) == (None, None)


@pytest.mark.parametrize("key", REQUIRED)
def test_a_missing_key_stops_the_worker_and_names_it(key: str) -> None:
    env = {**ENV, **{k: v for k, v in LEAD.items() if k != key}}
    with pytest.raises(AIRuntimeConfigError, match=key):
        AIRuntimeSettings.from_env(env)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"AIA_AI_RESEARCH_LEAD_MODEL_ID": "us.test.lead-model:1"}, "EU inference profile"),
        ({"AIA_AI_RESEARCH_LEAD_MODEL_ID": "eu."}, "EU inference profile"),
        ({"AIA_AI_RESEARCH_LEAD_MODEL_ID": "eu.test.lead-model:latest"}, "floating alias"),
        ({"AIA_AI_RESEARCH_LEAD_MODEL_ID": ROUTE_MODEL}, "route's own model"),
        ({"AIA_AI_RESEARCH_LEAD_INPUT_USD_PER_MTOK": "-1"}, "INPUT_USD_PER_MTOK"),
        ({"AIA_AI_RESEARCH_LEAD_OUTPUT_USD_PER_MTOK": "cheap"}, "OUTPUT_USD_PER_MTOK"),
        ({"AIA_AI_RESEARCH_LEAD_CACHE_READ_USD_PER_MTOK": "inf"}, "CACHE_READ_USD_PER_MTOK"),
        ({"AIA_AI_RESEARCH_LEAD_MODEL_MAX_OUTPUT_TOKENS": "0"}, "MODEL_MAX_OUTPUT_TOKENS"),
        ({"AIA_AI_RESEARCH_LEAD_CONTEXT_WINDOW_TOKENS": "lots"}, "CONTEXT_WINDOW_TOKENS"),
        ({"AIA_AI_RESEARCH_LEAD_STRUCTURED_OUTPUT": "json"}, "forced_tool, auto_tool"),
        ({"AIA_AI_RESEARCH_LEAD_THINKING": "enabled"}, "budget, adaptive"),
        ({"AIA_AI_RESEARCH_LEAD_EFFORT": "extreme"}, "low, medium, high, xhigh, max"),
        ({"AIA_AI_RESEARCH_LEAD_THINKING": "budget"}, "AIA_AI_RESEARCH_LEAD_EFFORT"),
    ],
)
def test_an_invalid_key_stops_the_worker_and_names_it(
    overrides: dict[str, str], match: str
) -> None:
    with pytest.raises(AIRuntimeConfigError, match=match):
        _with_lead(**overrides)


def test_an_id_without_a_version_suffix_is_accepted_as_bedrock_lists_it() -> None:
    """The current model family's Bedrock ids have no ``:N`` (``eu.anthropic.<model>``)."""
    unsuffixed = "eu.test.lead-model-unsuffixed"
    settings = _settings(**{**LEAD, "AIA_AI_RESEARCH_LEAD_MODEL_ID": unsuffixed})
    assert settings.lead_model is not None
    assert settings.lead_model.model_id == unsuffixed


def test_the_lead_models_entry_declares_its_profile_and_no_sampling() -> None:
    lead = _with_lead().lead_model
    assert lead is not None
    assert lead.request_profile() == RequestProfile(
        structured_output=StructuredOutput.AUTO_TOOL,
        thinking=ThinkingMode.ADAPTIVE,
        accepts_sampling=False,
        effort=Effort.MEDIUM,
    )
    registry = parse_model_config(_with_lead().model_document())
    descriptor = registry.descriptor(Provider.AWS_BEDROCK, LEAD_MODEL)
    assert descriptor is not None
    assert descriptor.request_profile == lead.request_profile()
    assert descriptor.capabilities == frozenset({ModelCapability.STUDY_LEAD})


# --------------------------------------------------------------------------- binding


def test_with_the_lead_model_study_lead_alone_runs_on_it_on_the_same_route() -> None:
    settings = _with_lead()
    registry = parse_model_config(settings.model_document())
    lead = registry.resolve(
        capability=ModelCapability.STUDY_LEAD, policy_version=settings.policy_version
    )
    assert lead.model == LEAD_MODEL and lead.route_id == settings.route_id
    pricing = lead.descriptor.pricing
    assert pricing is not None
    assert (pricing.input_usd_per_mtok, pricing.output_usd_per_mtok) == (7.0, 11.0)
    assert (lead.descriptor.max_output_tokens, lead.descriptor.context_window_tokens) == (
        64000,
        1000000,
    )
    for capability in (
        ModelCapability.SIMULATION,
        ModelCapability.RESEARCH_REASONING,
        ModelCapability.CRITIC,
    ):
        other = registry.resolve(capability=capability, policy_version=settings.policy_version)
        assert other.model == ROUTE_MODEL
        assert other.descriptor.request_profile.is_default
    # The route's model is not offered STUDY_LEAD, nor the Lead's model anything else.
    route = registry.descriptor(Provider.AWS_BEDROCK, ROUTE_MODEL)
    assert route is not None and ModelCapability.STUDY_LEAD not in route.capabilities


def test_with_the_lead_switched_off_its_model_is_checked_but_bound_to_nothing() -> None:
    settings = _with_lead(AIA_AI_RESEARCH_LEAD_ENABLED="false")
    assert settings.lead_model is not None and settings.study_lead_model is None
    document = settings.model_document()
    assert [m["model"] for m in document["models"]] == [ROUTE_MODEL]
    assert ModelCapability.STUDY_LEAD.value not in document["policies"][0]["bindings"]
    # Still validated: a wrong key stops the worker even while the Lead is off.
    with pytest.raises(AIRuntimeConfigError, match="EU inference profile"):
        _with_lead(AIA_AI_RESEARCH_LEAD_ENABLED="false", AIA_AI_RESEARCH_LEAD_MODEL_ID="x:1")


def test_the_lead_model_and_the_light_model_are_different_profiles() -> None:
    light = LightModelSettings(
        model_id=LEAD_MODEL,
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=2.0,
        max_output_tokens=4096,
        context_window_tokens=200000,
    )
    with pytest.raises(AIRuntimeConfigError, match="different profile from the light model"):
        _with_lead().model_document(light)


# --------------------------------------------------------------------------- the reservation


def _minimum(input_price: float, output_price: float, tokens: int = 1500) -> float:
    return reservation_usd(
        ModelPrices(input_usd_per_mtok=input_price, output_usd_per_mtok=output_price),
        window_tokens=lead_request_window_tokens(tokens),
        output_tokens=tokens,
    )


def test_the_reservation_minimum_is_the_lead_models_not_the_routes() -> None:
    on_route, on_lead = _minimum(3.0, 15.0), _minimum(8.75, 11.0)  # cache writes are dearer
    assert on_route < on_lead
    between = f"{(on_route + on_lead) / 2:.4f}"
    # Enough at the route model's prices: accepted when the Lead runs there ...
    assert _settings(AIA_AI_RESEARCH_LEAD_RESERVATION_USD=between).study_lead_configured
    # ... refused at the Lead model's, and the worker states the minimum it needs.
    with pytest.raises(AIRuntimeConfigError) as refused:
        _with_lead(AIA_AI_RESEARCH_LEAD_RESERVATION_USD=between)
    assert "AIA_AI_RESEARCH_LEAD_RESERVATION_USD" in str(refused.value)
    assert "the Lead model's prices" in str(refused.value)
    assert f"at least {on_lead:.4f}" in str(refused.value)
    enough = f"{on_lead + 0.0001:.4f}"
    assert _with_lead(AIA_AI_RESEARCH_LEAD_RESERVATION_USD=enough).study_lead_configured


def test_the_lead_models_own_limits_bound_the_lead() -> None:
    # Above the route model's output ceiling, within the Lead model's: accepted.
    settings = _with_lead(
        AIA_AI_RESEARCH_LEAD_MAX_OUTPUT_TOKENS="9000", AIA_AI_RESEARCH_LEAD_RESERVATION_USD="10"
    )
    assert settings.study_lead_max_output_tokens == 9000
    assert settings.study_lead_context_window_tokens == 1000000
    with pytest.raises(AIRuntimeConfigError, match="AIA_AI_RESEARCH_LEAD_MODEL_MAX_OUTPUT_TOKENS"):
        _with_lead(AIA_AI_RESEARCH_LEAD_MODEL_MAX_OUTPUT_TOKENS="1000")
    # The route's window is wide enough; the Lead model's is not.
    with pytest.raises(AIRuntimeConfigError, match="AIA_AI_RESEARCH_LEAD_CONTEXT_WINDOW_TOKENS"):
        _with_lead(AIA_AI_RESEARCH_LEAD_CONTEXT_WINDOW_TOKENS="100000")


# --------------------------------------------------------------------------- the gateway


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


class Transport:
    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        self.requests.append(request)
        tool = request.body["toolConfig"]["tools"][0]["toolSpec"]["name"]
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": f"req-{len(self.requests)}"},
            body={
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "t",
                                    "name": tool,
                                    "input": {"verdict": "ok"},
                                }
                            }
                        ],
                    }
                },
                "stopReason": "tool_use",
                "usage": {"inputTokens": 10, "outputTokens": 2},
            },
        )


def _request(capability: ModelCapability) -> ModelRequest:
    return ModelRequest(
        agent=AgentDefinition(
            agent_id="aia.test.lead-model",
            version="1",
            capability=capability,
            prompt_id="aia.test.lead-model",
            prompt_version="1",
            output_contract=Verdict,
            max_output_tokens=1500,
        ),
        policy_version=ENV["AIA_AI_POLICY_VERSION"],
        data_classification=DataClass.CLASS_C_INTERNAL,
        data_lineage=DataLineage.none(),
        system="s",
        messages=(Message(role="user", content="m"),),
    )


def _context(world: Any) -> ExecutionContext:
    with world.sessions() as session:
        scope = world.lead_scope(session)
    return ExecutionContext(
        scope=scope,
        runtime_version="runtime-test",
        journal=InMemoryCallJournal(),
        reservation=ReservationView("RSV-1", 1.0),
    )


def test_the_gateway_pins_both_models_and_sends_each_its_own_shape(world: Any) -> None:
    settings = _with_lead()
    transport = Transport()
    gateway = build_gateway(settings, transport=transport, signer=Signer())
    context = _context(world)
    lead = asyncio.run(gateway.invoke(_request(ModelCapability.STUDY_LEAD), context))
    design = asyncio.run(gateway.invoke(_request(ModelCapability.RESEARCH_REASONING), context))

    assert lead.resolved_model == LEAD_MODEL and design.resolved_model == ROUTE_MODEL
    to_lead, to_route = transport.requests
    assert "/model/eu.test.lead-model%3A1/converse" in to_lead.url
    assert "/model/eu.test.route-model%3A1/converse" in to_route.url
    # The Lead's model: the tool offered and the instruction, its effort, nothing else.
    assert to_lead.body["toolConfig"]["toolChoice"] == {"auto": {}}
    assert to_lead.body["additionalModelRequestFields"] == {"output_config": {"effort": "medium"}}
    assert to_lead.body["inferenceConfig"] == {"maxTokens": 1500}
    assert "exactly once" in to_lead.body["system"][0]["text"]
    # The route's model: exactly the shape it was sent before.
    assert to_route.body["toolConfig"]["toolChoice"] == {"tool": {"name": "aia_test_lead_model"}}
    assert "additionalModelRequestFields" not in to_route.body
    assert to_route.body["system"] == [{"text": "s"}]
    # Each priced at its own model's rates: 10 in, 2 out.
    assert lead.actual_cost_usd == pytest.approx((10 * 7.0 + 2 * 11.0) / 1_000_000)
    assert design.actual_cost_usd == pytest.approx((10 * 3.0 + 2 * 15.0) / 1_000_000)


def test_with_the_light_model_too_the_route_carries_three_pinned_models(world: Any) -> None:
    light = LightModelSettings(
        model_id=LIGHT_MODEL,
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=2.0,
        max_output_tokens=4096,
        context_window_tokens=200000,
    )
    transport = Transport()
    gateway = build_gateway(_with_lead(), light=light, transport=transport, signer=Signer())
    context = _context(world)
    for capability in (
        ModelCapability.RESEARCH_TRIAGE,
        ModelCapability.STUDY_LEAD,
        ModelCapability.RESEARCH_REASONING,
    ):
        asyncio.run(gateway.invoke(_request(capability), context))
    assert [r.url.split("/model/")[1] for r in transport.requests] == [
        "eu.test.light-model%3A1/converse",
        "eu.test.lead-model%3A1/converse",
        "eu.test.route-model%3A1/converse",
    ]


def test_without_the_lead_model_the_lead_is_sent_to_the_route_model_as_before(
    world: Any,
) -> None:
    transport = Transport()
    gateway = build_gateway(_settings(), transport=transport, signer=Signer())
    result = asyncio.run(gateway.invoke(_request(ModelCapability.STUDY_LEAD), _context(world)))
    assert result.resolved_model == ROUTE_MODEL
    [sent] = transport.requests
    assert sent.body["toolConfig"]["toolChoice"] == {"tool": {"name": "aia_test_lead_model"}}
    assert "additionalModelRequestFields" not in sent.body
