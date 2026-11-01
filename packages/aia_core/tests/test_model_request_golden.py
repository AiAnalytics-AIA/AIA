"""The bytes every existing caller sends, pinned (ADR 0026 Amendment 2026-10-28, G1).

G1-G3 widen the one model call path for the Lead's tool conversation: content blocks on
a message, a tool round, several tools. Every other caller must keep sending exactly
what it sent before, so this file pins it: for each request shape a caller sends today,
the Converse body as the real gateway hands it to the real Bedrock adapter (primary and
repair), the ledger's input fingerprint, system-prompt hash and ceiling, and the
Messages, Chat Completions and transcript bodies the other adapters build from the same
messages.

The pins in ``fixtures/model_adapters/golden_requests.json`` were captured on ``develop``
@ ``963a0d9a``, before G1 changed anything, by ``_capture``. Never regenerate them to make a
test pass: a difference is a caller's bytes changing. A new shape is captured on the code
before the change that needs it. No network.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.domain.ai_contracts import AdapterRequest, AgentDefinition, Message, ModelRequest
from aia_core.domain.ai_execution import ExecutionContext, ReservationView
from aia_core.domain.ai_models import ModelCapability, parse_model_config
from aia_core.domain.licence import DataLineage
from aia_core.domain.licence_determinations import recorded_policy
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass, EgressPolicy, ProviderRoute, ResidencyZone
from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal
from aia_core.infrastructure.model_adapters import (
    AnthropicMessagesAdapter,
    BedrockConverseAdapter,
    OpenAIChatAdapter,
    RecordedTransport,
    StaticCredentials,
)
from aia_core.infrastructure.model_adapters.transport import (
    HttpRequest,
    HttpResponse,
    render_transcript,
)

GOLDEN = Path(__file__).parent / "fixtures" / "model_adapters" / "golden_requests.json"

MODEL = "eu.test.golden-model:1"  # a test id, not a real profile
ROUTE = "bedrock-eu-golden"
POLICY = "policy-golden-v1"
AGENT = "aia.test.golden"
TOOL = "aia_test_golden"


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str
    score: int


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


class ScriptedTransport:
    def __init__(self, answers: Sequence[dict[str, Any]]) -> None:
        self._answers = list(answers)
        self.requests: list[HttpRequest] = []

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        self.requests.append(request)
        return HttpResponse(
            status=200, headers={"x-amzn-requestid": "r"}, body=self._answers.pop(0)
        )


def _converse(block: dict[str, Any], stop: str) -> dict[str, Any]:
    return {
        "output": {"message": {"role": "assistant", "content": [block]}},
        "stopReason": stop,
        "usage": {"inputTokens": 1000, "outputTokens": 300},
    }


TOOL_ANSWER = _converse(
    {"toolUse": {"toolUseId": "t1", "name": TOOL, "input": {"verdict": "ano", "score": 4}}},
    "tool_use",
)
TEXT_ANSWER = _converse({"text": "Odpověď je ano."}, "end_turn")
OFF_CONTRACT = _converse({"text": '{"verdict": "ano"}'}, "end_turn")

ADAPTIVE = {"structured_output": "auto_tool", "thinking": "adaptive", "accepts_sampling": False}

CONVERSATION = (
    Message(role="user", content="Shrň zadání: „spotřebitelé 18–35, Praha“."),  # noqa: RUF001
    Message(role="assistant", content="Zadání: mladí spotřebitelé v Praze."),
    Message(role="user", content="Navrhni tři výzkumné otázky.\nKaždou na řádek."),
)

#: Each request shape an existing caller sends today: (agent output, request fields,
#: catalog profile, the provider's scripted answers).
SHAPES: dict[str, tuple[bool, dict[str, Any], dict[str, Any], list[dict[str, Any]]]] = {
    # A text agent (no output contract).
    "text": (False, {}, {}, [TEXT_ANSWER]),
    # A structured agent on the default profile: research agents, analysis, extraction.
    "structured": (True, {}, {}, [TOOL_ANSWER]),
    # The AI respondent: temperature 0.0.
    "respondent_temperature": (True, {"temperature": 0.0}, {}, [TOOL_ANSWER]),
    # A schema violation and its one repair.
    "structured_repair": (True, {}, {}, [OFF_CONTRACT, TOOL_ANSWER]),
    # Deep Research's agents with a thinking budget.
    "thinking_budget": (True, {"thinking_budget_tokens": 2048}, {}, [TOOL_ANSWER]),
    # The study Lead on an adaptive model with an effort, and its repair.
    "adaptive_effort": (True, {}, {**ADAPTIVE, "effort": "high"}, [TOOL_ANSWER]),
    "adaptive_repair": (True, {}, ADAPTIVE, [TEXT_ANSWER, TOOL_ANSWER]),
    # Several turns, Czech and a line break in the content.
    "conversation": (True, {"messages": CONVERSATION}, {}, [TOOL_ANSWER]),
}


def _gateway(transport: ScriptedTransport, profile: dict[str, Any]) -> GovernedModelGateway:
    entry = {
        "provider": Provider.AWS_BEDROCK.value,
        "model": MODEL,
        "capabilities": [ModelCapability.CRITIC.value],
        "max_output_tokens": 8192,
        "context_window_tokens": 200000,
        "pricing": {"input_usd_per_mtok": 1.0, "output_usd_per_mtok": 2.0},
        "supports_strict_schema": False,
        **profile,
    }
    binding = {"provider": Provider.AWS_BEDROCK.value, "model": MODEL, "route_id": ROUTE}
    registry = parse_model_config(
        {
            "models": [entry],
            "policies": [
                {
                    "version": POLICY,
                    "allowed_providers": [Provider.AWS_BEDROCK.value],
                    "bindings": {ModelCapability.CRITIC.value: binding},
                }
            ],
        }
    )
    route = ProviderRoute(
        route_id=ROUTE,
        provider=Provider.AWS_BEDROCK.value,
        zone=ResidencyZone.EU,
        eu_processing_approved=True,
        excluded_from_training=True,
        approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
    )
    adapter = BedrockConverseAdapter(
        transport=transport, signer=Signer(), region="eu-central-1", model_id=MODEL
    )
    return GovernedModelGateway(
        registry=registry,
        egress=EgressPolicy(routes=(route,)),
        licence=recorded_policy(),
        adapters={ROUTE: adapter},
    )


def _request(structured: bool, fields: dict[str, Any]) -> ModelRequest:
    base: dict[str, Any] = {
        "agent": AgentDefinition(
            agent_id=AGENT,
            version="1",
            capability=ModelCapability.CRITIC,
            prompt_id=AGENT,
            prompt_version="1",
            output_contract=Verdict if structured else None,
            max_output_tokens=4096,
        ),
        "policy_version": POLICY,
        "data_classification": DataClass.CLASS_C_INTERNAL,
        "data_lineage": DataLineage.none(),
        "system": "Jsi pečlivý analytik. Odpovídej česky.",
        "messages": (Message(role="user", content="Tvrzení: trh roste o 5 %."),),
    }
    return ModelRequest(**{**base, **fields})


def _capture_shape(scope: Any, name: str) -> dict[str, Any]:
    structured, fields, profile, answers = SHAPES[name]
    transport = ScriptedTransport(answers)
    journal = InMemoryCallJournal()
    context = ExecutionContext(
        scope=scope,
        runtime_version="runtime-golden",
        journal=journal,
        run_id="RUN-1",
        step_id="STP-1",
        attempt_id="ATT-1",
        reservation=ReservationView(reservation_id="RSV-1", amount_usd=5.0),
    )
    result = asyncio.run(_gateway(transport, profile).invoke(_request(structured, fields), context))
    dispatched = [e for e in result.usage_events if not e.outcome.is_terminal]
    calls = []
    for sent, event in zip(transport.requests, dispatched, strict=True):
        assert sent.raw_body is not None
        calls.append(
            {
                "purpose": event.purpose.value,
                "bedrock_body": sent.raw_body.decode("utf-8"),
                "input_fingerprint": event.input_fingerprint,
                "system_prompt_sha256": event.system_prompt_sha256,
                "ceiling_usd": event.ceiling_usd,
            }
        )
    return {"calls": calls}


def _other_adapters(name: str) -> dict[str, Any]:
    """What the Messages, Chat Completions and transcript adapters build from the shape."""
    structured, fields, _, _ = SHAPES[name]
    request = _request(structured, fields)
    outbound = AdapterRequest(
        call_id="call-golden",
        provider=Provider.ANTHROPIC,
        model="test-model",
        system=request.system,
        messages=request.messages,
        max_output_tokens=4096,
        output_schema=request.agent.schema,
        schema_name=TOOL if structured else "",
        temperature=request.temperature,
    )
    recorded = RecordedTransport()
    anthropic = AnthropicMessagesAdapter(
        transport=recorded,
        credentials=StaticCredentials({"k": "secret"}),
        credential_ref="k",
        base_url="https://anthropic.test",
    )
    openai = OpenAIChatAdapter(
        transport=recorded,
        credentials=StaticCredentials({"k": "secret"}),
        credential_ref="k",
        base_url="https://openai.test",
    )
    return {
        "anthropic_body": _canonical(anthropic.build_request(outbound, secret="s").body),
        "openai_body": _canonical(openai.build_request(outbound, secret="s").body),
        "transcript": render_transcript(request.messages),
    }


def _canonical(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _capture(scope: Any) -> dict[str, Any]:
    return {name: {**_capture_shape(scope, name), **_other_adapters(name)} for name in SHAPES}


@pytest.fixture
def scope(scoped: Any) -> Any:
    return scoped.scope(user="researcher", study="primary")


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    pinned: dict[str, Any] = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return pinned


def test_every_shape_is_pinned(golden: dict[str, Any]) -> None:
    assert sorted(golden) == sorted(SHAPES)


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_the_gateway_sends_bedrock_the_bytes_it_sent_before(
    golden: dict[str, Any], scope: Any, name: str
) -> None:
    assert _capture_shape(scope, name) == {"calls": golden[name]["calls"]}


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_the_other_adapters_build_the_bodies_they_built_before(
    golden: dict[str, Any], name: str
) -> None:
    pinned = {k: golden[name][k] for k in ("anthropic_body", "openai_body", "transcript")}
    assert _other_adapters(name) == pinned
