"""A model's identity and its invocation target in the worker's composition (5a).

``develop-spend-attribution`` chunk 1 will create application inference profiles tagged
``Environment=develop``; before any is configured, the worker must accept one as what a model's
calls are *sent through* while the model's identity -- its ``eu.`` id, its prices, its policy
binding, its ledger rows -- stays the ``eu.`` id it validates as before. Unset, nothing changes.

Every id, ARN and price here is fictional. No network: a scripted transport stands in for AWS,
and botocore is used only offline, to serialise the URL it would send.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aia_core.domain.ai_contracts import AgentDefinition, Message, ModelRequest
from aia_core.domain.ai_execution import ExecutionContext, ReservationView
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.licence import DataLineage
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal
from aia_core.infrastructure.model_adapters import BedrockConverseAdapter
from aia_core.infrastructure.model_adapters.transport import HttpRequest, HttpResponse
from aia_executors.ai_runtime import (
    AIRuntimeConfigError,
    AIRuntimeSettings,
    LightModelSettings,
    build_gateway,
)
from pydantic import BaseModel, ConfigDict

ROUTE_MODEL = "eu.test.route-model:1"
LEAD_MODEL = "eu.test.lead-model:1"
LIGHT_MODEL = "eu.test.light-model:1"
ACCOUNT = "123456789012"


def _profile(name: str, region: str = "eu-central-1") -> str:
    return f"arn:aws:bedrock:{region}:{ACCOUNT}:application-inference-profile/{name}"


ROUTE_PROFILE = _profile("route0profile")
LEAD_PROFILE = _profile("lead0profile")

ENV = {
    "AIA_ENV": "test",
    "AIA_AI_RUNTIME_ENABLED": "true",
    "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
    "AIA_BEDROCK_REGION": "eu-central-1",
    "AIA_BEDROCK_MODEL_ID": ROUTE_MODEL,
    "AIA_AI_POLICY_VERSION": "test-invocation-target-v1",
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

LEAD = {
    "AIA_AI_RESEARCH_LEAD_MODEL_ID": LEAD_MODEL,
    "AIA_AI_RESEARCH_LEAD_INPUT_USD_PER_MTOK": "7",
    "AIA_AI_RESEARCH_LEAD_OUTPUT_USD_PER_MTOK": "11",
    "AIA_AI_RESEARCH_LEAD_MODEL_MAX_OUTPUT_TOKENS": "64000",
    "AIA_AI_RESEARCH_LEAD_CONTEXT_WINDOW_TOKENS": "1000000",
    "AIA_AI_RESEARCH_LEAD_STRUCTURED_OUTPUT": "auto_tool",
    "AIA_AI_RESEARCH_LEAD_THINKING": "adaptive",
}


def _settings(**overrides: str) -> AIRuntimeSettings:
    settings = AIRuntimeSettings.from_env({**ENV, **overrides})
    assert settings is not None
    return settings


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
        content = [{"toolUse": {"toolUseId": "t", "name": tool, "input": {"verdict": "ok"}}}]
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": f"req-{len(self.requests)}"},
            body={
                "output": {"message": {"role": "assistant", "content": content}},
                "stopReason": "tool_use",
                "usage": {"inputTokens": 10, "outputTokens": 2},
            },
        )


def _request(capability: ModelCapability) -> ModelRequest:
    return ModelRequest(
        agent=AgentDefinition(
            agent_id="aia.test.invocation-target",
            version="1",
            capability=capability,
            prompt_id="aia.test.invocation-target",
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


def _encoded(target: str) -> str:
    return target.replace(":", "%3A").replace("/", "%2F")


# --------------------------------------------------------------------------- settings


def test_unset_every_model_is_called_by_its_own_id_as_before() -> None:
    settings = _settings(**LEAD)
    assert settings.invocation_target is None
    assert {i: m.target for i, m in settings.invocations().items()} == {
        ROUTE_MODEL: ROUTE_MODEL,
        LEAD_MODEL: LEAD_MODEL,
    }


def test_each_target_is_read_beside_its_models_id() -> None:
    settings = _settings(
        **LEAD,
        AIA_BEDROCK_INVOCATION_TARGET=ROUTE_PROFILE,
        AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET=LEAD_PROFILE,
    )
    # The identity is unchanged: still the eu. id, everywhere AIA prices and binds a model.
    assert settings.model_id == ROUTE_MODEL
    assert settings.lead_model is not None and settings.lead_model.model_id == LEAD_MODEL
    document = settings.model_document()
    assert [m["model"] for m in document["models"]] == [ROUTE_MODEL, LEAD_MODEL]
    assert ROUTE_PROFILE not in str(document) and LEAD_PROFILE not in str(document)
    called = settings.invocations()
    assert (called[ROUTE_MODEL].target, called[LEAD_MODEL].target) == (ROUTE_PROFILE, LEAD_PROFILE)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        # The identity is never loosened: an ARN is not a model id.
        ({"AIA_BEDROCK_MODEL_ID": ROUTE_PROFILE}, "AIA_BEDROCK_MODEL_ID"),
        ({"AIA_BEDROCK_INVOCATION_TARGET": "eu.test.other:1"}, "AIA_BEDROCK_INVOCATION_TARGET"),
        (
            {"AIA_BEDROCK_INVOCATION_TARGET": _profile("route0profile", "us-east-1")},
            "AIA_BEDROCK_INVOCATION_TARGET.*not the route's EU region",
        ),
        (
            {"AIA_BEDROCK_INVOCATION_TARGET": _profile("route0profile", "eu-west-1")},
            "not the route's EU region",
        ),
        (
            {**LEAD, "AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET": "arn:aws:bedrock:x"},
            "AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET",
        ),
        (
            {
                **LEAD,
                "AIA_BEDROCK_INVOCATION_TARGET": ROUTE_PROFILE,
                "AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET": ROUTE_PROFILE,
            },
            "same invocation target",
        ),
    ],
)
def test_a_wrong_target_stops_the_worker_by_name(overrides: dict[str, str], match: str) -> None:
    with pytest.raises(AIRuntimeConfigError, match=match):
        AIRuntimeSettings.from_env({**ENV, **overrides})


def test_the_lead_models_target_is_checked_while_the_lead_is_off() -> None:
    with pytest.raises(AIRuntimeConfigError, match="AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET"):
        _settings(
            **LEAD,
            AIA_AI_RESEARCH_LEAD_ENABLED="false",
            AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET="eu.test.lead-model:1",
        )


# --------------------------------------------------------------------------- the gateway


def test_calls_go_through_each_profile_and_are_priced_and_recorded_as_the_model(
    world: Any,
) -> None:
    settings = _settings(
        **LEAD,
        AIA_BEDROCK_INVOCATION_TARGET=ROUTE_PROFILE,
        AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET=LEAD_PROFILE,
    )
    transport = Transport()
    gateway = build_gateway(settings, transport=transport, signer=Signer())
    context = _context(world)
    design = asyncio.run(gateway.invoke(_request(ModelCapability.RESEARCH_REASONING), context))
    lead = asyncio.run(gateway.invoke(_request(ModelCapability.STUDY_LEAD), context))

    to_route, to_lead = transport.requests
    assert to_route.url.endswith(f"/model/{_encoded(ROUTE_PROFILE)}/converse")
    assert to_lead.url.endswith(f"/model/{_encoded(LEAD_PROFILE)}/converse")
    # What the ledger and the price see is the model's identity, never the ARN.
    assert (design.resolved_model, lead.resolved_model) == (ROUTE_MODEL, LEAD_MODEL)
    assert design.actual_cost_usd == pytest.approx((10 * 3.0 + 2 * 15.0) / 1_000_000)
    assert lead.actual_cost_usd == pytest.approx((10 * 7.0 + 2 * 11.0) / 1_000_000)


def test_the_light_model_takes_a_target_of_its_own(world: Any) -> None:
    light = LightModelSettings(
        model_id=LIGHT_MODEL,
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=2.0,
        max_output_tokens=4096,
        context_window_tokens=200000,
        invocation_target=_profile("light0profile"),
    )
    transport = Transport()
    gateway = build_gateway(_settings(), light=light, transport=transport, signer=Signer())
    result = asyncio.run(gateway.invoke(_request(ModelCapability.RESEARCH_TRIAGE), _context(world)))
    assert result.resolved_model == LIGHT_MODEL
    assert transport.requests[0].url.endswith(
        f"/model/{_encoded(_profile('light0profile'))}/converse"
    )
    wrong = LightModelSettings(
        model_id=LIGHT_MODEL,
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=2.0,
        max_output_tokens=4096,
        context_window_tokens=200000,
        invocation_target=ROUTE_MODEL,
    )
    with pytest.raises(AIRuntimeConfigError, match="light model"):
        build_gateway(_settings(), light=wrong, transport=Transport(), signer=Signer())


def test_the_url_is_the_one_botocore_serialises_for_the_same_arn() -> None:
    """Offline: botocore builds the Converse request for an ARN modelId and is stopped before
    sending; its path is the adapter's, byte for byte, so signing and routing agree."""
    botocore_session = pytest.importorskip("botocore.session")

    class Stopped(Exception):
        """Raised before botocore sends anything."""

    session = botocore_session.get_session()
    session.set_credentials("AKIDTEST", "secret-test")
    client = session.create_client("bedrock-runtime", region_name="eu-central-1")
    seen: list[str] = []

    def stop(request: Any, **_: Any) -> None:
        seen.append(request.url)
        raise Stopped

    client.meta.events.register("before-send.bedrock-runtime.Converse", stop)
    with pytest.raises(Stopped):
        client.converse(modelId=ROUTE_PROFILE, messages=[{"role": "user", "content": []}])
    adapter = BedrockConverseAdapter(
        transport=Transport(),
        signer=Signer(),
        region="eu-central-1",
        model_id=ROUTE_MODEL,
        invocation_target=ROUTE_PROFILE,
    )
    assert seen == [adapter.url()]
