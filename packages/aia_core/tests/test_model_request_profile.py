"""A model's request profile: the request shape declared in its catalog entry.

A newer model family on Bedrock refuses, with a 400, the two ways the adapter asked
for structured output before profiles existed -- a forced tool choice, and a thinking
budget beside an offered tool -- and any non-default sampling value. It thinks
adaptively when nothing is said about thinking. So the shape a model is sent is a
declared property of its catalog entry, never guessed from its id.

These tests drive the real gateway over the real Bedrock adapter, with a scripted
transport in place of AWS: what each profile sends, that the default profile sends
the bytes it sent before profiles existed, that an answer in text is the one repair,
and that a request a profile cannot carry is refused unsent and by name. The model
ids are obviously fake; no model name or price of a real model appears here. No
network.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from aia_core.application.model_gateway import (
    REPAIR_TOOL_PROMPT_VERSION,
    TEXT_INSTEAD_OF_TOOL,
    TOOL_ANSWER_PROMPT_VERSION,
    GovernedModelGateway,
)
from aia_core.domain.ai_contracts import (
    AdapterRequest,
    AgentDefinition,
    CallPurpose,
    Delivery,
    Message,
    ModelCallFailed,
    ModelRequest,
    ProviderError,
    ProviderErrorKind,
    UsageOutcome,
    input_fingerprint,
    output_schema,
)
from aia_core.domain.ai_execution import ExecutionContext, ReservationView
from aia_core.domain.ai_models import (
    DEFAULT_REQUEST_PROFILE,
    Effort,
    ModelCapability,
    ModelConfigError,
    ModelRegistry,
    RequestProfile,
    StructuredOutput,
    ThinkingMode,
    parse_model_config,
)
from aia_core.domain.licence import DataLineage
from aia_core.domain.licence_determinations import recorded_policy
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass, EgressPolicy, ProviderRoute, ResidencyZone
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal
from aia_core.infrastructure.model_adapters import (
    AnthropicMessagesAdapter,
    BedrockConverseAdapter,
    ClaudeCodeCliAdapter,
    OpenAIChatAdapter,
    RecordedCliRunner,
    RecordedTransport,
    StaticCredentials,
)
from aia_core.infrastructure.model_adapters.transport import HttpRequest, HttpResponse

MODEL = "eu.test.profile-model:1"  # a test id, not a real profile
ROUTE = "bedrock-eu-test"
POLICY = "policy-profile-v1"
TOOL = "aia_test_profile"

#: The profile a model family declares when it refuses a forced tool, a thinking
#: budget and sampling.
ADAPTIVE = RequestProfile(
    structured_output=StructuredOutput.AUTO_TOOL,
    thinking=ThinkingMode.ADAPTIVE,
    accepts_sampling=False,
)


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str
    score: int


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


class ScriptedTransport:
    """Bedrock's side: one scripted Converse answer per request, every request kept."""

    def __init__(self, answers: Sequence[dict[str, Any]]) -> None:
        self._answers = list(answers)
        self.requests: list[HttpRequest] = []

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        self.requests.append(request)
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": f"req-{len(self.requests)}"},
            body=self._answers.pop(0),
        )


def _converse(*blocks: dict[str, Any], stop: str = "tool_use") -> dict[str, Any]:
    return {
        "output": {"message": {"role": "assistant", "content": list(blocks)}},
        "stopReason": stop,
        "usage": {"inputTokens": 1000, "outputTokens": 300},
    }


def _tool() -> dict[str, Any]:
    return {
        "toolUse": {
            "toolUseId": "tooluse_1",
            "name": TOOL,
            "input": {"verdict": "podloženo", "score": 4},
        }
    }


def _text(text: str = '{"verdict": "podloženo", "score": 4}') -> dict[str, Any]:
    return {"text": text}


def _entry(**profile: Any) -> dict[str, Any]:
    return {
        "provider": Provider.AWS_BEDROCK.value,
        "model": MODEL,
        "capabilities": [ModelCapability.CRITIC.value],
        "max_output_tokens": 8192,
        "context_window_tokens": 200000,
        "pricing": {"input_usd_per_mtok": 1.0, "output_usd_per_mtok": 2.0},
        "supports_strict_schema": False,
        **profile,
    }


def _registry(**profile: Any) -> ModelRegistry:
    binding = {"provider": Provider.AWS_BEDROCK.value, "model": MODEL, "route_id": ROUTE}
    return parse_model_config(
        {
            "models": [_entry(**profile)],
            "policies": [
                {
                    "version": POLICY,
                    "allowed_providers": [Provider.AWS_BEDROCK.value],
                    "bindings": {ModelCapability.CRITIC.value: binding},
                }
            ],
        }
    )


def _gateway(transport: ScriptedTransport, **profile: Any) -> GovernedModelGateway:
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
        registry=_registry(**profile),
        egress=EgressPolicy(routes=(route,)),
        licence=recorded_policy(),
        adapters={ROUTE: adapter},
    )


def _request(**overrides: Any) -> ModelRequest:
    base: dict[str, Any] = {
        "agent": AgentDefinition(
            agent_id="aia.test.profile",
            version="1",
            capability=ModelCapability.CRITIC,
            prompt_id="aia.test.profile",
            prompt_version="1",
            output_contract=Verdict,
            max_output_tokens=4096,
        ),
        "policy_version": POLICY,
        "data_classification": DataClass.CLASS_C_INTERNAL,
        "data_lineage": DataLineage.none(),
        "system": "Posuď tvrzení.",
        "messages": (Message(role="user", content="Tvrzení: trh roste."),),
    }
    return ModelRequest(**{**base, **overrides})


@pytest.fixture
def journal() -> InMemoryCallJournal:
    return InMemoryCallJournal()


@pytest.fixture
def scope(scoped: Any) -> Any:
    return scoped.scope(user="researcher", study="primary")


def _context(scope: Any, journal: InMemoryCallJournal) -> ExecutionContext:
    return ExecutionContext(
        scope=scope,
        runtime_version="runtime-test",
        journal=journal,
        run_id="RUN-1",
        step_id="STP-1",
        attempt_id="ATT-1",
        reservation=ReservationView(reservation_id="RSV-1", amount_usd=5.0),
    )


def _invoke(
    transport: ScriptedTransport,
    request: ModelRequest,
    context: ExecutionContext,
    **profile: Any,
) -> Any:
    return asyncio.run(_gateway(transport, **profile).invoke(request, context))


_ADAPTIVE_ENTRY: dict[str, Any] = {
    "structured_output": "auto_tool",
    "thinking": "adaptive",
    "accepts_sampling": False,
}


# --------------------------------------------------------------------------- #
# The catalog entry declares it
# --------------------------------------------------------------------------- #


def test_an_entry_that_declares_no_profile_has_the_shape_it_always_had() -> None:
    descriptor = _registry().descriptor(Provider.AWS_BEDROCK, MODEL)
    assert descriptor is not None
    assert descriptor.request_profile == DEFAULT_REQUEST_PROFILE
    assert descriptor.request_profile.is_default
    assert (
        RequestProfile(
            structured_output=StructuredOutput.FORCED_TOOL,
            thinking=ThinkingMode.BUDGET,
            accepts_sampling=True,
            effort=None,
        )
        == DEFAULT_REQUEST_PROFILE
    )


def test_an_entry_declares_its_profile_and_its_effort() -> None:
    descriptor = _registry(**_ADAPTIVE_ENTRY, effort="high").descriptor(Provider.AWS_BEDROCK, MODEL)
    assert descriptor is not None
    assert descriptor.request_profile == RequestProfile(
        structured_output=StructuredOutput.AUTO_TOOL,
        thinking=ThinkingMode.ADAPTIVE,
        accepts_sampling=False,
        effort=Effort.HIGH,
    )
    assert not descriptor.request_profile.is_default


@pytest.mark.parametrize(
    "profile",
    [
        {"structured_output": "json_mode"},
        {"thinking": "enabled"},
        {"accepts_sampling": "no"},
        {"thinking": "adaptive", "effort": "extreme"},
        # An effort means nothing to a model that thinks on a budget.
        {"effort": "high"},
    ],
    ids=["structured-output", "thinking", "sampling", "effort-value", "effort-on-budget"],
)
def test_a_profile_the_entry_cannot_have_is_refused_at_load(profile: dict[str, Any]) -> None:
    with pytest.raises(ModelConfigError):
        _registry(**profile)


# --------------------------------------------------------------------------- #
# What each profile sends
# --------------------------------------------------------------------------- #


def test_the_default_profile_forces_the_tool_and_adds_nothing(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport([_converse(_tool())])
    result = _invoke(transport, _request(temperature=0.0), _context(scope, journal))
    body = transport.requests[0].body
    assert body["toolConfig"]["toolChoice"] == {"tool": {"name": TOOL}}
    assert body["inferenceConfig"] == {"maxTokens": 4096, "temperature": 0.0}
    assert body["system"] == [{"text": "Posuď tvrzení."}]
    assert "additionalModelRequestFields" not in body
    assert {e.note for e in result.usage_events} == {""}


def test_an_auto_tool_adaptive_model_is_offered_the_tool_and_told_to_use_it(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport([_converse(_tool())])
    result = _invoke(transport, _request(), _context(scope, journal), **_ADAPTIVE_ENTRY)
    assert result.output == Verdict(verdict="podloženo", score=4)
    body = transport.requests[0].body
    tools = body["toolConfig"]
    # Never forced: the model family answers a forced tool choice with a 400.
    assert tools["toolChoice"] == {"auto": {}}
    assert [t["toolSpec"]["name"] for t in tools["tools"]] == [TOOL]
    assert tools["tools"][0]["toolSpec"]["inputSchema"] == {"json": output_schema(Verdict)}
    # Nothing about thinking (adaptive when omitted), no budget, nothing that samples.
    assert "additionalModelRequestFields" not in body
    assert body["inferenceConfig"] == {"maxTokens": 4096}
    # The agent's prompt, then the instruction to answer through the tool.
    [system] = body["system"]
    assert system["text"].startswith("Posuď tvrzení.\n\n")
    assert f"calling the tool {TOOL} exactly once" in system["text"]
    assert {e.note for e in result.usage_events} == {f"answer_prompt={TOOL_ANSWER_PROMPT_VERSION}"}


@pytest.mark.parametrize("effort", list(Effort))
def test_a_configured_effort_is_the_only_field_beside_the_request(
    scope: Any, journal: InMemoryCallJournal, effort: Effort
) -> None:
    transport = ScriptedTransport([_converse(_tool())])
    _invoke(
        transport,
        _request(),
        _context(scope, journal),
        **_ADAPTIVE_ENTRY,
        effort=effort.value,
    )
    body = transport.requests[0].body
    assert body["additionalModelRequestFields"] == {"output_config": {"effort": effort.value}}
    assert "thinking" not in body["additionalModelRequestFields"]
    assert body["toolConfig"]["toolChoice"] == {"auto": {}}


def test_an_auto_tool_model_without_adaptive_thinking_takes_its_temperature(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport([_converse(_tool())])
    _invoke(
        transport,
        _request(temperature=0.2),
        _context(scope, journal),
        structured_output="auto_tool",
    )
    body = transport.requests[0].body
    assert body["toolConfig"]["toolChoice"] == {"auto": {}}
    assert body["inferenceConfig"] == {"maxTokens": 4096, "temperature": 0.2}
    assert "additionalModelRequestFields" not in body


def test_an_answer_in_text_is_the_one_repair_through_the_tool(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport([_converse(_text(), stop="end_turn"), _converse(_tool())])
    result = _invoke(transport, _request(), _context(scope, journal), **_ADAPTIVE_ENTRY)
    assert result.output == Verdict(verdict="podloženo", score=4)
    terminal = [e for e in result.usage_events if e.outcome.is_terminal]
    assert [(e.outcome, e.purpose, e.error_kind) for e in terminal] == [
        (UsageOutcome.FAILED, CallPurpose.PRIMARY, ProviderErrorKind.SCHEMA),
        (UsageOutcome.SUCCEEDED, CallPurpose.SCHEMA_REPAIR, None),
    ]
    assert terminal[1].note == (
        f"answer_prompt={TOOL_ANSWER_PROMPT_VERSION} repair_prompt={REPAIR_TOOL_PROMPT_VERSION}"
    )
    repair = transport.requests[1].body
    assert repair["toolConfig"]["toolChoice"] == {"auto": {}}
    assert "additionalModelRequestFields" not in repair
    ask = repair["messages"][-1]["content"][0]["text"]
    assert TEXT_INSTEAD_OF_TOOL in ask and f"Call the tool {TOOL} exactly once" in ask


def test_an_answer_in_text_twice_fails_like_any_schema_violation(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport(
        [_converse(_text(), stop="end_turn"), _converse(_text(), stop="end_turn")]
    )
    with pytest.raises(ModelCallFailed) as failed:
        _invoke(transport, _request(), _context(scope, journal), **_ADAPTIVE_ENTRY)
    assert failed.value.failure is FailureClass.SCHEMA_VIOLATION
    assert failed.value.violations == (TEXT_INSTEAD_OF_TOOL,)
    assert len(transport.requests) == 2


def test_the_profile_is_the_models_and_leaves_the_content_fingerprint_alone() -> None:
    def outbound(profile: RequestProfile) -> AdapterRequest:
        return AdapterRequest(
            call_id="c",
            provider=Provider.AWS_BEDROCK,
            model=MODEL,
            system="s",
            messages=(Message(role="user", content="m"),),
            max_output_tokens=4096,
            request_profile=profile,
        )

    assert input_fingerprint(outbound(DEFAULT_REQUEST_PROFILE)) == input_fingerprint(
        outbound(ADAPTIVE)
    )


# --------------------------------------------------------------------------- #
# What a profile cannot carry is refused unsent, by name
# --------------------------------------------------------------------------- #


def test_a_thinking_budget_to_an_adaptive_model_is_refused_unsent(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport([])
    with pytest.raises(ModelCallFailed) as failed:
        _invoke(
            transport,
            _request(thinking_budget_tokens=2048),
            _context(scope, journal),
            **_ADAPTIVE_ENTRY,
        )
    assert failed.value.reason == "provider_other"
    assert "thinks adaptively and takes no thinking budget" in str(failed.value)
    assert failed.value.outcome_known
    assert transport.requests == []


def test_a_temperature_to_a_model_that_takes_no_sampling_is_refused_unsent(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport([])
    with pytest.raises(ModelCallFailed) as failed:
        _invoke(transport, _request(temperature=0.0), _context(scope, journal), **_ADAPTIVE_ENTRY)
    assert "takes no sampling setting" in str(failed.value)
    assert transport.requests == []


def _adapter_request(**overrides: Any) -> AdapterRequest:
    base: dict[str, Any] = {
        "call_id": "CALL-profile",
        "provider": Provider.AWS_BEDROCK,
        "model": MODEL,
        "system": "s",
        "messages": (Message(role="user", content="m"),),
        "max_output_tokens": 4096,
        "output_schema": output_schema(Verdict),
        "schema_name": TOOL,
        "request_profile": ADAPTIVE,
    }
    return AdapterRequest(**{**base, **overrides})


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"thinking_budget_tokens": 2048}, "takes no thinking budget"),
        ({"temperature": 0.0}, "takes no sampling setting"),
    ],
    ids=["budget", "temperature"],
)
def test_bedrock_refuses_what_the_profile_cannot_carry_before_signing(
    overrides: dict[str, Any], message: str
) -> None:
    transport = ScriptedTransport([])
    adapter = BedrockConverseAdapter(
        transport=transport, signer=Signer(), region="eu-central-1", model_id=MODEL
    )
    with pytest.raises(ProviderError, match=message) as refused:
        asyncio.run(adapter.send(_adapter_request(**overrides)))
    assert refused.value.kind is ProviderErrorKind.OTHER
    assert refused.value.delivery is Delivery.NOT_SENT
    assert transport.requests == []


def test_bedrock_sends_an_adaptive_model_text_without_a_tool() -> None:
    transport = ScriptedTransport([_converse(_text("Hotovo."), stop="end_turn")])
    adapter = BedrockConverseAdapter(
        transport=transport, signer=Signer(), region="eu-central-1", model_id=MODEL
    )
    response = asyncio.run(adapter.send(_adapter_request(output_schema=None, schema_name="")))
    body = transport.requests[0].body
    assert "toolConfig" not in body and "additionalModelRequestFields" not in body
    assert response.text == "Hotovo."


@pytest.mark.parametrize("name", ["anthropic", "openai", "claude_code"])
def test_adapters_that_send_only_the_default_shape_refuse_another_profile(name: str) -> None:
    transport = RecordedTransport()
    runner = RecordedCliRunner()
    credentials = StaticCredentials({"provider-key": "secret"})
    adapter: Any = {
        "anthropic": lambda: AnthropicMessagesAdapter(
            transport=transport,
            credentials=credentials,
            credential_ref="provider-key",
            base_url="https://anthropic.test/",
        ),
        "openai": lambda: OpenAIChatAdapter(
            transport=transport,
            credentials=credentials,
            credential_ref="provider-key",
            base_url="https://openai.test",
        ),
        "claude_code": lambda: ClaudeCodeCliAdapter(runner=runner),
    }[name]()
    with pytest.raises(ProviderError) as refused:
        asyncio.run(adapter.send(_adapter_request(provider=adapter.provider, model="m")))
    assert refused.value.delivery is Delivery.NOT_SENT
    assert "sends only the default request profile" in str(refused.value)
    assert transport.requests == [] and runner.invocations == []
