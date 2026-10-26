"""The route model's request profile (sonnet-5-5-switch): what ADR 0010's model is sent.

The product owner decided on 2026-10-25 (AUD-7) to ready develop's route for Claude Sonnet
5.5, whose Bedrock id carries no ``:N`` and which refuses a forced tool, a thinking budget and
a sampling temperature. The route model's profile is configured, never inferred from its id:
``AIA_BEDROCK_STRUCTURED_OUTPUT``, ``_THINKING`` and ``_ACCEPTS_SAMPLING`` together, with an
optional effort for the route and for two capabilities. Unset, the route is sent exactly what
it was sent before -- pinned below byte for byte.

The ids and prices are fake but for the Sonnet 5.5 shape, whose prices and limits are the ones
the infra session read from develop's Bedrock account on 2026-10-25. No network: a scripted
transport stands in for AWS.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

import pytest
from aia_core.domain.ai_contracts import AgentDefinition, Message, ModelRequest
from aia_core.domain.ai_execution import ExecutionContext, ReservationView
from aia_core.domain.ai_models import (
    DEFAULT_REQUEST_PROFILE,
    Effort,
    ModelCapability,
    RequestProfile,
    StructuredOutput,
    ThinkingMode,
)
from aia_core.domain.licence import DataLineage
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal
from aia_core.infrastructure.model_adapters.transport import HttpRequest, HttpResponse
from aia_executors.ai_runtime import AIRuntimeConfigError, AIRuntimeSettings, build_gateway
from pydantic import BaseModel, ConfigDict

LEGACY_MODEL = "eu.test.route-model:1"
SONNET_5_5 = "eu.anthropic.claude-sonnet-5-5"

ENV = {
    "AIA_ENV": "test",
    "AIA_AI_RUNTIME_ENABLED": "true",
    "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
    "AIA_BEDROCK_REGION": "eu-central-1",
    "AIA_BEDROCK_MODEL_ID": LEGACY_MODEL,
    "AIA_AI_POLICY_VERSION": "test-route-profile-v1",
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
    "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "4096",
    "AIA_AI_RESEARCH_RESERVATION_USD": "20",
}

#: Claude Sonnet 5.5 on develop's route, as the infra session read it on 2026-10-25: the EU
#: profile ACTIVE with no ":N"; eu-central-1 Standard geo prices per Mtok; a 1M window and a
#: 128K output ceiling; a forced tool, a thinking budget and sampling refused.
SONNET_5_5_ENV = {
    "AIA_BEDROCK_MODEL_ID": SONNET_5_5,
    "AIA_BEDROCK_INPUT_USD_PER_MTOK": "2.20",
    "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "11.00",
    "AIA_BEDROCK_CACHE_READ_USD_PER_MTOK": "0.11",
    "AIA_BEDROCK_CACHE_WRITE_USD_PER_MTOK": "2.75",
    "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "128000",
    "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "1000000",
    "AIA_BEDROCK_STRUCTURED_OUTPUT": "auto_tool",
    "AIA_BEDROCK_THINKING": "adaptive",
    "AIA_BEDROCK_ACCEPTS_SAMPLING": "false",
}


def _settings(**overrides: str) -> AIRuntimeSettings:
    settings = AIRuntimeSettings.from_env({**ENV, **overrides})
    assert settings is not None
    return settings


def _sonnet(**overrides: str) -> AIRuntimeSettings:
    return _settings(**{**SONNET_5_5_ENV, **overrides})


# --------------------------------------------------------------------------- settings


def test_without_the_keys_the_route_models_profile_is_the_default() -> None:
    settings = _settings()
    assert settings.request_profile == DEFAULT_REQUEST_PROFILE
    assert settings.capability_efforts == {}
    [entry] = settings.model_document()["models"]
    assert not {"structured_output", "thinking", "accepts_sampling", "effort"} & set(entry)
    assert "efforts" not in settings.model_document()["policies"][0]


def test_the_sonnet_5_5_profile_id_is_accepted_as_bedrock_lists_it() -> None:
    settings = _sonnet()
    assert settings.model_id == SONNET_5_5
    assert settings.request_profile == RequestProfile(
        structured_output=StructuredOutput.AUTO_TOOL,
        thinking=ThinkingMode.ADAPTIVE,
        accepts_sampling=False,
    )
    [entry] = settings.model_document()["models"]
    assert entry["structured_output"] == "auto_tool" and entry["thinking"] == "adaptive"
    assert entry["accepts_sampling"] is False and "effort" not in entry
    assert entry["pricing"] == {
        "input_usd_per_mtok": 2.2,
        "output_usd_per_mtok": 11.0,
        "cache_read_usd_per_mtok": 0.11,
        "cache_write_usd_per_mtok": 2.75,
    }


@pytest.mark.parametrize(
    "model_id", ["eu.anthropic.claude-sonnet-latest", "anthropic.claude-sonnet-5-5", "eu."]
)
def test_an_alias_or_a_non_eu_route_model_is_still_refused(model_id: str) -> None:
    with pytest.raises(AIRuntimeConfigError, match="AIA_BEDROCK_MODEL_ID"):
        _settings(AIA_BEDROCK_MODEL_ID=model_id)


def test_the_route_and_each_capability_take_their_own_effort() -> None:
    settings = _sonnet(
        AIA_BEDROCK_EFFORT="medium", AIA_AI_FIELDWORK_EFFORT="low", AIA_AI_RESEARCH_EFFORT="high"
    )
    assert settings.request_profile.effort is Effort.MEDIUM
    policy = settings.model_document()["policies"][0]
    assert policy["efforts"] == {
        "SIMULATION": "low",
        "RESEARCH_REASONING": "high",
        "CRITIC": "high",
    }
    # Deep Research's lead researcher, once its composition binds it, takes the research effort.
    lead = dataclasses.replace(settings, research_lead_enabled=True)
    assert lead.model_document()["policies"][0]["efforts"]["RESEARCH_LEAD"] == "high"


def test_a_capability_effort_for_nothing_bound_is_left_out() -> None:
    # Research agents and analysis off: RESEARCH_REASONING and CRITIC are bound to nothing.
    settings = _sonnet(AIA_AI_RESEARCH_AGENTS_ENABLED="false", AIA_AI_RESEARCH_EFFORT="high")
    assert "efforts" not in settings.model_document()["policies"][0]


@pytest.mark.parametrize(
    ("overrides", "names"),
    [
        ({"AIA_BEDROCK_THINKING": ""}, "AIA_BEDROCK_THINKING is required"),
        ({"AIA_BEDROCK_STRUCTURED_OUTPUT": ""}, "AIA_BEDROCK_STRUCTURED_OUTPUT is required"),
        ({"AIA_BEDROCK_ACCEPTS_SAMPLING": ""}, "AIA_BEDROCK_ACCEPTS_SAMPLING is required"),
        ({"AIA_BEDROCK_THINKING": "enabled"}, "AIA_BEDROCK_THINKING='enabled'"),
        ({"AIA_BEDROCK_STRUCTURED_OUTPUT": "json"}, "AIA_BEDROCK_STRUCTURED_OUTPUT='json'"),
        ({"AIA_BEDROCK_ACCEPTS_SAMPLING": "maybe"}, "AIA_BEDROCK_ACCEPTS_SAMPLING='maybe'"),
        ({"AIA_BEDROCK_EFFORT": "huge"}, "AIA_BEDROCK_EFFORT='huge'"),
        ({"AIA_BEDROCK_THINKING": "budget", "AIA_BEDROCK_EFFORT": "low"}, "AIA_BEDROCK_EFFORT"),
        ({"AIA_AI_FIELDWORK_EFFORT": "tiny"}, "AIA_AI_FIELDWORK_EFFORT='tiny'"),
        (
            {"AIA_BEDROCK_THINKING": "budget", "AIA_AI_FIELDWORK_EFFORT": "low"},
            "AIA_AI_FIELDWORK_EFFORT is set",
        ),
        (
            {"AIA_BEDROCK_THINKING": "budget", "AIA_AI_RESEARCH_EFFORT": "low"},
            "AIA_AI_RESEARCH_EFFORT is set",
        ),
    ],
)
def test_a_wrong_profile_key_stops_the_worker_and_names_it(
    overrides: dict[str, str], names: str
) -> None:
    with pytest.raises(AIRuntimeConfigError, match=names.replace("(", r"\(")):
        _sonnet(**overrides)


def test_any_one_profile_key_alone_declares_the_profile_and_needs_the_rest() -> None:
    with pytest.raises(AIRuntimeConfigError, match="AIA_BEDROCK_ACCEPTS_SAMPLING is required"):
        _settings(AIA_BEDROCK_EFFORT="low")
    with pytest.raises(AIRuntimeConfigError, match="AIA_BEDROCK_STRUCTURED_OUTPUT is required"):
        _settings(AIA_BEDROCK_ACCEPTS_SAMPLING="true")


def test_an_effort_for_a_capability_without_an_adaptive_route_is_refused_without_a_profile() -> (
    None
):
    with pytest.raises(AIRuntimeConfigError, match="AIA_AI_FIELDWORK_EFFORT is set"):
        _settings(AIA_AI_FIELDWORK_EFFORT="low")


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
                "usage": {
                    "inputTokens": 1000,
                    "outputTokens": 100,
                    "cacheReadInputTokens": 0,
                    "cacheWriteInputTokens": 1000,
                },
            },
        )


def _request(
    capability: ModelCapability,
    *,
    temperature: float | None = None,
    thinking_budget_tokens: int | None = None,
    max_output_tokens: int = 1024,
) -> ModelRequest:
    return ModelRequest(
        agent=AgentDefinition(
            agent_id="aia.test.route-profile",
            version="1",
            capability=capability,
            prompt_id="aia.test.route-profile",
            prompt_version="1",
            output_contract=Verdict,
            max_output_tokens=max_output_tokens,
        ),
        policy_version=ENV["AIA_AI_POLICY_VERSION"],
        data_classification=DataClass.CLASS_C_INTERNAL,
        data_lineage=DataLineage.none(),
        system="Jsi respondent.",
        messages=(Message(role="user", content="OTÁZKA 1/1"),),
        temperature=temperature,
        thinking_budget_tokens=thinking_budget_tokens,
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


def _send(world: Any, settings: AIRuntimeSettings, request: ModelRequest) -> HttpRequest:
    transport = Transport()
    gateway = build_gateway(settings, transport=transport, signer=Signer())
    asyncio.run(gateway.invoke(request, _context(world)))
    [sent] = transport.requests
    return sent


#: A respondent-shaped request to the route model with no profile keys, as the code before
#: sonnet-5-5-switch sent it (captured at f7762d72): every byte, signed body included.
LEGACY_BODY = (
    '{"messages":[{"role":"user","content":[{"text":"OTÁZKA 1/1"}]}],'
    '"inferenceConfig":{"maxTokens":1024,"temperature":0.0},'
    '"system":[{"text":"Jsi respondent."}],'
    '"toolConfig":{"tools":[{"toolSpec":{"name":"aia_test_route_profile",'
    '"description":"Return the answer as this object.","inputSchema":{"json":'
    '{"additionalProperties":false,"properties":{"verdict":{"title":"Verdict","type":"string"}},'
    '"required":["verdict"],"title":"Verdict","type":"object"}}}}],'
    '"toolChoice":{"tool":{"name":"aia_test_route_profile"}}}}'
)


def test_without_the_keys_the_route_model_is_sent_the_same_bytes_as_before(world: Any) -> None:
    sent = _send(world, _settings(), _request(ModelCapability.SIMULATION, temperature=0.0))
    assert sent.raw_body == LEGACY_BODY.encode("utf-8")
    assert "/model/eu.test.route-model%3A1/converse" in sent.url


def test_sonnet_5_5_is_offered_the_tool_with_no_temperature_and_its_capabilitys_effort(
    world: Any,
) -> None:
    settings = _sonnet(AIA_AI_FIELDWORK_EFFORT="low")
    sent = _send(world, settings, _request(ModelCapability.SIMULATION))
    assert "/model/eu.anthropic.claude-sonnet-5-5/converse" in sent.url
    assert sent.body["inferenceConfig"] == {"maxTokens": 1024}
    assert sent.body["toolConfig"]["toolChoice"] == {"auto": {}}
    assert sent.body["additionalModelRequestFields"] == {"output_config": {"effort": "low"}}
    assert "Answer only by calling the tool" in sent.body["system"][0]["text"]
    # Another capability on the same model takes the route's effort: here none.
    research = _send(world, settings, _request(ModelCapability.RESEARCH_REASONING))
    assert "additionalModelRequestFields" not in research.body


def test_a_temperature_or_a_budget_sent_to_sonnet_5_5_is_refused_unsent(world: Any) -> None:
    from aia_core.domain.ai_contracts import ModelCallFailed

    for request in (
        _request(ModelCapability.SIMULATION, temperature=0.0),
        _request(
            ModelCapability.RESEARCH_REASONING, thinking_budget_tokens=2048, max_output_tokens=4096
        ),
    ):
        transport = Transport()
        gateway = build_gateway(_sonnet(), transport=transport, signer=Signer())
        with pytest.raises(ModelCallFailed):
            asyncio.run(gateway.invoke(request, _context(world)))
        assert transport.requests == []


def test_a_cache_write_is_charged_at_its_own_price(world: Any) -> None:
    transport = Transport()
    gateway = build_gateway(_sonnet(), transport=transport, signer=Signer())
    result = asyncio.run(gateway.invoke(_request(ModelCapability.SIMULATION), _context(world)))
    # 1000 uncached in at 2.20, 100 out at 11.00, 1000 written to the cache at 2.75.
    assert result.actual_cost_usd == pytest.approx((1000 * 2.20 + 100 * 11.0 + 1000 * 2.75) / 1e6)
