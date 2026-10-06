"""The light model's policy entry: ``RESEARCH_TRIAGE`` on ADR 0010's route, proposed.

Plan ``deep-research-web-search.md`` chunk 20. The light model is a second catalog
entry and a second binding on the same route, held to the route model's rules (an
EU inference profile pinned to a version, prices stated, no defaults). Without it
nothing binds ``RESEARCH_TRIAGE`` and the registry refuses it; with it, a triage
request leaves through the light model's own pinned adapter and the research
agents' requests are unchanged. No network: a scripted transport stands in for AWS.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

import pytest
from aia_core.domain.ai_contracts import AgentDefinition, Message, ModelCallFailed, ModelRequest
from aia_core.domain.ai_execution import ExecutionContext, ReservationView
from aia_core.domain.ai_models import ModelCapability, ResolutionError, parse_model_config
from aia_core.domain.licence import DataLineage
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal
from aia_core.infrastructure.model_adapters.transport import HttpRequest, HttpResponse
from aia_executors.ai_runtime import (
    AIRuntimeConfigError,
    AIRuntimeSettings,
    LightModelSettings,
    build_gateway,
)

ENV = {
    "AIA_ENV": "test",
    "AIA_AI_RUNTIME_ENABLED": "true",
    "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
    "AIA_BEDROCK_REGION": "eu-central-1",
    "AIA_BEDROCK_MODEL_ID": "eu.example.research-test-v1:0",
    "AIA_AI_POLICY_VERSION": "test-light-v1",
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
}

#: The proposed entry (plan chunk 20; chunk 1 signs it off). Its prices are the
#: EU geography rate this repository expects -- the US list price plus the 10 %
#: the verified research-model EU rate carries (ADR 0010) -- and are UNVERIFIED
#: until the Bedrock pricing page is read and dated. Configuration, not a default.
PROPOSED = LightModelSettings(
    model_id="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
    input_usd_per_mtok=1.10,
    output_usd_per_mtok=5.50,
    cache_read_usd_per_mtok=0.11,
    cache_write_usd_per_mtok=1.375,
    max_output_tokens=64000,
    context_window_tokens=200000,
)


def _settings() -> AIRuntimeSettings:
    settings = AIRuntimeSettings.from_env(ENV)
    assert settings is not None
    return settings


def test_without_the_light_model_nothing_binds_triage() -> None:
    settings = _settings()
    registry = parse_model_config(settings.model_document())
    with pytest.raises(ResolutionError) as refused:
        registry.resolve(
            capability=ModelCapability.RESEARCH_TRIAGE, policy_version=settings.policy_version
        )
    assert refused.value.reason == "capability_not_configured"
    assert settings.model_document() == settings.model_document(None)


def test_the_light_model_binds_triage_alone_on_the_same_route() -> None:
    settings = _settings()
    registry = parse_model_config(settings.model_document(PROPOSED))
    triage = registry.resolve(
        capability=ModelCapability.RESEARCH_TRIAGE, policy_version=settings.policy_version
    )
    assert triage.model == PROPOSED.model_id
    assert triage.route_id == settings.route_id
    assert triage.descriptor.capabilities == frozenset({ModelCapability.RESEARCH_TRIAGE})
    pricing = triage.descriptor.pricing
    assert pricing is not None
    assert (pricing.input_usd_per_mtok, pricing.output_usd_per_mtok) == (1.10, 5.50)
    assert (pricing.cache_read_usd_per_mtok, pricing.cache_write_usd_per_mtok) == (0.11, 1.375)
    for capability in (ModelCapability.RESEARCH_REASONING, ModelCapability.CRITIC):
        other = registry.resolve(capability=capability, policy_version=settings.policy_version)
        assert other.model == settings.model_id
    # The research model cannot be asked for triage, nor the light model for research.
    with pytest.raises(ResolutionError):
        registry.resolve(
            capability=ModelCapability.RESEARCH_TRIAGE,
            policy_version=settings.policy_version,
            requested_model=settings.model_id,
        )


@pytest.mark.parametrize(
    "model_id",
    [
        "anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "eu.anthropic.claude-haiku-latest",
        "eu.anthropic.claude-haiku-4-5",
    ],
)
def test_the_light_model_is_a_pinned_eu_profile(model_id: str) -> None:
    with pytest.raises(AIRuntimeConfigError, match="EU inference profile"):
        replace(PROPOSED, model_id=model_id)


@pytest.mark.parametrize(
    "change",
    [
        {"input_usd_per_mtok": -1.0},
        {"output_usd_per_mtok": float("inf")},
        {"cache_read_usd_per_mtok": float("nan")},
        {"max_output_tokens": 0},
        {"context_window_tokens": -5},
    ],
)
def test_the_light_model_states_real_prices_and_limits(change: dict[str, Any]) -> None:
    with pytest.raises(AIRuntimeConfigError):
        replace(PROPOSED, **change)


def test_the_light_model_is_not_the_route_model() -> None:
    settings = _settings()
    with pytest.raises(AIRuntimeConfigError, match="different profile"):
        settings.model_document(replace(PROPOSED, model_id=settings.model_id))


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


class Transport:
    def __init__(self) -> None:
        self.urls: list[str] = []

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        self.urls.append(request.url)
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": f"req-{len(self.urls)}"},
            body={
                "output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}},
                "stopReason": "end_turn",
                "usage": {"inputTokens": 10, "outputTokens": 2},
            },
        )


def _scope(world: Any) -> Any:
    with world.sessions() as session:
        return world.lead_scope(session)


def _request(capability: ModelCapability) -> ModelRequest:
    return ModelRequest(
        agent=AgentDefinition(
            agent_id="aia.test.light",
            version="1",
            capability=capability,
            prompt_id="aia.test.light",
            prompt_version="1",
            max_output_tokens=64,
        ),
        policy_version=ENV["AIA_AI_POLICY_VERSION"],
        data_classification=DataClass.CLASS_C_INTERNAL,
        data_lineage=DataLineage.none(),
        system="s",
        messages=(Message(role="user", content="m"),),
    )


def test_the_gateway_sends_each_capability_through_its_own_model(world: Any) -> None:
    settings = _settings()
    transport = Transport()
    gateway = build_gateway(settings, light=PROPOSED, transport=transport, signer=Signer())
    context = ExecutionContext(
        scope=_scope(world),
        runtime_version="runtime-test",
        journal=InMemoryCallJournal(),
        reservation=ReservationView("RSV-1", 1.0),
    )
    triage = asyncio.run(gateway.invoke(_request(ModelCapability.RESEARCH_TRIAGE), context))
    research = asyncio.run(gateway.invoke(_request(ModelCapability.RESEARCH_REASONING), context))
    assert triage.resolved_model == PROPOSED.model_id
    assert research.resolved_model == settings.model_id
    assert "/model/eu.anthropic.claude-haiku-4-5-20251001-v1%3A0/converse" in transport.urls[0]
    assert "/model/eu.example.research-test-v1%3A0/converse" in transport.urls[1]
    # Priced at the light model's own rates: 10 in, 2 out.
    assert triage.actual_cost_usd == pytest.approx((10 * 1.10 + 2 * 5.50) / 1_000_000)


def test_without_the_light_model_the_gateway_refuses_triage_and_sends_nothing(
    world: Any,
) -> None:
    transport = Transport()
    gateway = build_gateway(_settings(), transport=transport, signer=Signer())
    context = ExecutionContext(
        scope=_scope(world),
        runtime_version="runtime-test",
        journal=InMemoryCallJournal(),
        reservation=ReservationView("RSV-1", 1.0),
    )

    with pytest.raises(ModelCallFailed) as refused:
        asyncio.run(gateway.invoke(_request(ModelCapability.RESEARCH_TRIAGE), context))
    assert refused.value.reason == "model_resolution_capability_not_configured"
    assert transport.urls == []
