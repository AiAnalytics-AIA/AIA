"""Extended thinking on the Bedrock route: structured output without a forced tool.

Claude refuses a forced tool choice while thinking is on, so a thinking request is
offered its one output tool with ``toolChoice.auto`` and told to answer through it.
These tests drive the real gateway over the real Bedrock adapter, with a scripted
transport in place of AWS: what is sent, what is kept of the answer, how an answer
in text is repaired, and that the reservation covers the thinking. A request without
a budget must send the bytes it sent before the setting existed (pinned below from
``origin/develop`` @ ``757154e``'s gateway and adapter). No network.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from aia_core.application.model_gateway import (
    REPAIR_TOOL_PROMPT_VERSION,
    TEXT_INSTEAD_OF_TOOL,
    TOOL_ANSWER_PROMPT_VERSION,
    GovernedModelGateway,
    input_token_bound,
)
from aia_core.domain.ai_contracts import (
    AdapterRequest,
    AgentDefinition,
    CallPurpose,
    CostBasis,
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
from aia_core.domain.ai_models import ModelCapability, ModelRegistry, parse_model_config
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

PROFILE = "eu.example.test-model-v1:0"  # a test id, not a real profile
ROUTE = "bedrock-eu-test"
POLICY = "policy-thinking-v1"
TOOL = "aia_test_thinking"
#: $3 in, $15 out per Mtok: the test route's prices.
IN_PRICE, OUT_PRICE = 3.0, 15.0

#: What origin/develop @ 757154e sent for :func:`_request` with no budget: the exact
#: Converse body, and the input fingerprint recorded on its ledger rows.
GOLDEN_BODY = (
    '{"messages":[{"role":"user","content":[{"text":"Tvrzení: trh roste."}]}],'
    '"inferenceConfig":{"maxTokens":4096},"system":[{"text":"Posuď tvrzení."}],'
    '"toolConfig":{"tools":[{"toolSpec":{"name":"aia_test_thinking",'
    '"description":"Return the answer as this object.","inputSchema":{"json":'
    '{"additionalProperties":false,"properties":{"verdict":{"title":"Verdict",'
    '"type":"string"},"score":{"title":"Score","type":"integer"}},'
    '"required":["verdict","score"],"title":"Verdict","type":"object"}}}}],'
    '"toolChoice":{"tool":{"name":"aia_test_thinking"}}}}'
)
GOLDEN_FINGERPRINT = "sha256:afb19df3aff321cd8a6d9ddad7e647d43fcc428d2481f97eae2502bbf66bce6d"

REASONING = "TAJNÁ ÚVAHA, která nesmí nikam"


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


def _converse(
    *blocks: dict[str, Any],
    stop: str = "tool_use",
    input_tokens: int = 1000,
    output_tokens: int = 300,
) -> dict[str, Any]:
    return {
        "output": {"message": {"role": "assistant", "content": list(blocks)}},
        "stopReason": stop,
        "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens},
    }


def _reasoning() -> dict[str, Any]:
    return {"reasoningContent": {"reasoningText": {"text": REASONING, "signature": "c2lnbmF0dXJl"}}}


def _tool(answer: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "toolUse": {
            "toolUseId": "tooluse_1",
            "name": TOOL,
            "input": answer if answer is not None else {"verdict": "podloženo", "score": 4},
        }
    }


def _text(text: str = '{"verdict": "podloženo", "score": 4}') -> dict[str, Any]:
    return {"text": text}


def _registry() -> ModelRegistry:
    binding = {"provider": Provider.AWS_BEDROCK.value, "model": PROFILE, "route_id": ROUTE}
    return parse_model_config(
        {
            "models": [
                {
                    "provider": Provider.AWS_BEDROCK.value,
                    "model": PROFILE,
                    "capabilities": [ModelCapability.CRITIC.value],
                    "max_output_tokens": 8192,
                    "context_window_tokens": 200000,
                    "pricing": {"input_usd_per_mtok": IN_PRICE, "output_usd_per_mtok": OUT_PRICE},
                    "supports_strict_schema": False,
                }
            ],
            "policies": [
                {
                    "version": POLICY,
                    "allowed_providers": [Provider.AWS_BEDROCK.value],
                    "bindings": {ModelCapability.CRITIC.value: binding},
                }
            ],
        }
    )


def _gateway(transport: ScriptedTransport) -> GovernedModelGateway:
    route = ProviderRoute(
        route_id=ROUTE,
        provider=Provider.AWS_BEDROCK.value,
        zone=ResidencyZone.EU,
        eu_processing_approved=True,
        excluded_from_training=True,
        approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
    )
    adapter = BedrockConverseAdapter(
        transport=transport, signer=Signer(), region="eu-central-1", model_id=PROFILE
    )
    return GovernedModelGateway(
        registry=_registry(),
        egress=EgressPolicy(routes=(route,)),
        licence=recorded_policy(),
        adapters={ROUTE: adapter},
    )


def _agent(**overrides: Any) -> AgentDefinition:
    base: dict[str, Any] = {
        "agent_id": "aia.test.thinking",
        "version": "1",
        "capability": ModelCapability.CRITIC,
        "prompt_id": "aia.test.thinking",
        "prompt_version": "1",
        "output_contract": Verdict,
        "max_output_tokens": 4096,
    }
    return AgentDefinition(**{**base, **overrides})


def _request(**overrides: Any) -> ModelRequest:
    base: dict[str, Any] = {
        "agent": _agent(),
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


def _context(scope: Any, journal: InMemoryCallJournal, amount_usd: float = 5.0) -> ExecutionContext:
    return ExecutionContext(
        scope=scope,
        runtime_version="runtime-test",
        journal=journal,
        run_id="RUN-1",
        step_id="STP-1",
        attempt_id="ATT-1",
        reservation=ReservationView(reservation_id="RSV-1", amount_usd=amount_usd),
    )


def _invoke(transport: ScriptedTransport, request: ModelRequest, context: ExecutionContext) -> Any:
    return asyncio.run(_gateway(transport).invoke(request, context))


def _fail(transport: ScriptedTransport, request: ModelRequest, context: ExecutionContext) -> Any:
    with pytest.raises(ModelCallFailed) as failed:
        _invoke(transport, request, context)
    return failed.value


# --------------------------------------------------------------------------- #
# No budget: nothing changes
# --------------------------------------------------------------------------- #


def test_without_a_budget_the_request_is_the_bytes_it_was_before(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport([_converse(_tool())])
    result = _invoke(transport, _request(), _context(scope, journal))
    sent = transport.requests[0]
    assert sent.raw_body is not None
    assert sent.raw_body.decode("utf-8") == GOLDEN_BODY
    assert "additionalModelRequestFields" not in sent.body
    assert {e.input_fingerprint for e in result.usage_events} == {GOLDEN_FINGERPRINT}
    assert result.provenance.input_fingerprint == GOLDEN_FINGERPRINT
    assert {e.note for e in result.usage_events} == {""}


def test_the_fingerprint_names_the_budget_only_when_there_is_one() -> None:
    def outbound(budget: int | None) -> AdapterRequest:
        return AdapterRequest(
            call_id="c",
            provider=Provider.AWS_BEDROCK,
            model=PROFILE,
            system="s",
            messages=(Message(role="user", content="m"),),
            max_output_tokens=4096,
            thinking_budget_tokens=budget,
        )

    assert input_fingerprint(outbound(None)) != input_fingerprint(outbound(2048))
    assert input_fingerprint(outbound(2048)) != input_fingerprint(outbound(3000))


# --------------------------------------------------------------------------- #
# The request contract
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"thinking_budget_tokens": 1023}, "at least 1024"),
        ({"thinking_budget_tokens": 4096}, "below the output limit of 4096"),
        ({"thinking_budget_tokens": 2048, "max_output_tokens": 2048}, "below the output limit"),
        ({"thinking_budget_tokens": 2048, "temperature": 0.0}, "takes no temperature"),
    ],
)
def test_a_budget_is_refused_where_the_call_could_not_carry_it(
    overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _request(**overrides)


def test_the_smallest_budget_and_one_below_the_limit_are_accepted() -> None:
    assert _request(thinking_budget_tokens=1024).thinking_budget_tokens == 1024
    assert _request(thinking_budget_tokens=4095).thinking_budget_tokens == 4095
    assert _request().thinking_budget_tokens is None


# --------------------------------------------------------------------------- #
# With a budget: what is sent, what is kept
# --------------------------------------------------------------------------- #


def test_a_thinking_request_offers_the_tool_and_sends_no_sampling_setting(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport([_converse(_reasoning(), _tool())])
    result = _invoke(transport, _request(thinking_budget_tokens=2048), _context(scope, journal))
    body = transport.requests[0].body
    assert body["additionalModelRequestFields"] == {
        "thinking": {"type": "enabled", "budget_tokens": 2048}
    }
    # The whole output, thinking included, and nothing that samples.
    assert body["inferenceConfig"] == {"maxTokens": 4096}
    tools = body["toolConfig"]
    assert tools["toolChoice"] == {"auto": {}}
    assert [t["toolSpec"]["name"] for t in tools["tools"]] == [TOOL]
    assert tools["tools"][0]["toolSpec"]["inputSchema"] == {"json": output_schema(Verdict)}
    # The agent's prompt, then the instruction to answer through the tool.
    [system] = body["system"]
    assert system["text"].startswith("Posuď tvrzení.\n\n")
    assert f"calling the tool {TOOL} exactly once" in system["text"]
    assert "Do not answer in text." in system["text"]
    # The ledger names the instruction's version, and keeps the prompt's own hash.
    assert {e.note for e in result.usage_events} == {f"answer_prompt={TOOL_ANSWER_PROMPT_VERSION}"}
    assert result.usage_events[0].input_fingerprint != GOLDEN_FINGERPRINT


def test_schema_valid_output_with_thinking_on_and_the_reasoning_is_not_kept(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport([_converse(_reasoning(), _tool(), output_tokens=2500)])
    result = _invoke(transport, _request(thinking_budget_tokens=2048), _context(scope, journal))
    assert result.output == Verdict(verdict="podloženo", score=4)
    assert json.loads(result.text) == {"verdict": "podloženo", "score": 4}
    # Thinking is billed as output: 1000 in, 2500 out (reasoning and answer together).
    assert result.cost_basis is CostBasis.METERED
    assert result.actual_cost_usd == pytest.approx((1000 * IN_PRICE + 2500 * OUT_PRICE) / 1e6)
    # Nothing of the reasoning survives: not the result, not the ledger.
    kept = repr(result) + repr(journal.dispatched) + repr(journal.outcomes)
    assert REASONING not in kept and "c2lnbmF0dXJl" not in kept


def test_an_answer_in_text_is_one_counted_repair_through_the_tool(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    # Valid JSON, but in text: off-contract, because it had to come through the tool.
    transport = ScriptedTransport(
        [_converse(_reasoning(), _text(), stop="end_turn"), _converse(_reasoning(), _tool())]
    )
    result = _invoke(transport, _request(thinking_budget_tokens=2048), _context(scope, journal))
    assert result.output == Verdict(verdict="podloženo", score=4)

    terminal = [e for e in result.usage_events if e.outcome.is_terminal]
    assert [(e.outcome, e.purpose, e.error_kind) for e in terminal] == [
        (UsageOutcome.FAILED, CallPurpose.PRIMARY, ProviderErrorKind.SCHEMA),
        (UsageOutcome.SUCCEEDED, CallPurpose.SCHEMA_REPAIR, None),
    ]
    assert terminal[1].note == (
        f"answer_prompt={TOOL_ANSWER_PROMPT_VERSION} repair_prompt={REPAIR_TOOL_PROMPT_VERSION}"
    )
    # Both calls were billed, so both count against the one reservation.
    assert result.total_cost_usd == pytest.approx(2 * result.actual_cost_usd)

    repair = transport.requests[1].body
    assert repair["additionalModelRequestFields"]["thinking"]["budget_tokens"] == 2048
    assert repair["toolConfig"]["toolChoice"] == {"auto": {}}
    answer, ask = repair["messages"][-2:]
    assert answer == {"role": "assistant", "content": [{"text": _text()["text"]}]}
    assert TEXT_INSTEAD_OF_TOOL in ask["content"][0]["text"]
    assert f"Call the tool {TOOL} exactly once" in ask["content"][0]["text"]


def test_an_answer_in_text_twice_fails_like_any_schema_violation(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport(
        [_converse(_text(), stop="end_turn"), _converse(_text(), stop="end_turn")]
    )
    failure = _fail(transport, _request(thinking_budget_tokens=2048), _context(scope, journal))
    assert failure.failure is FailureClass.SCHEMA_VIOLATION
    assert failure.reason == "structured_output_invalid"
    assert failure.violations == (TEXT_INSTEAD_OF_TOOL,)
    assert failure.outcome_known
    assert len(transport.requests) == 2


def test_a_reply_of_reasoning_alone_is_repaired_with_a_turn_that_is_not_empty(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport(
        [_converse(_reasoning(), stop="end_turn"), _converse(_reasoning(), _tool())]
    )
    result = _invoke(transport, _request(thinking_budget_tokens=2048), _context(scope, journal))
    assert result.output is not None
    answer = transport.requests[1].body["messages"][-2]
    assert answer == {"role": "assistant", "content": [{"text": "(no answer)"}]}
    assert REASONING not in json.dumps(transport.requests[1].body, ensure_ascii=False)


def test_an_off_schema_tool_answer_is_repaired_as_before(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    transport = ScriptedTransport(
        [_converse(_tool({"verdict": "podloženo", "score": "4"})), _converse(_tool())]
    )
    result = _invoke(transport, _request(thinking_budget_tokens=2048), _context(scope, journal))
    assert result.output == Verdict(verdict="podloženo", score=4)
    ask = transport.requests[1].body["messages"][-1]["content"][0]["text"]
    assert "score: Input should be a valid integer" in ask


# --------------------------------------------------------------------------- #
# Money: the ceiling covers the thinking
# --------------------------------------------------------------------------- #


def test_the_ceiling_prices_the_whole_output_thinking_included(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    # The worst case: the whole budget thought, the rest of the limit answered (and a
    # short prompt's real input count, which the byte bound is far above).
    transport = ScriptedTransport(
        [_converse(_reasoning(), _tool(), input_tokens=150, output_tokens=4096)]
    )
    request = _request(thinking_budget_tokens=3000)
    result = _invoke(transport, request, _context(scope, journal))
    dispatched = journal.dispatched[0]
    outbound = AdapterRequest(
        call_id="probe",
        provider=Provider.AWS_BEDROCK,
        model=PROFILE,
        system=transport.requests[0].body["system"][0]["text"],
        messages=request.messages,
        max_output_tokens=4096,
        output_schema=request.agent.schema,
        thinking_budget_tokens=3000,
    )
    ceiling = (input_token_bound(outbound) * IN_PRICE + 4096 * OUT_PRICE) / 1e6
    assert dispatched.ceiling_usd == pytest.approx(ceiling)
    # The output limit sent is the one priced, and the budget lies inside it.
    assert transport.requests[0].body["inferenceConfig"]["maxTokens"] == 4096 > 3000
    assert result.actual_cost_usd <= dispatched.ceiling_usd


def test_a_reservation_that_cannot_cover_the_thinking_sends_nothing(
    scope: Any, journal: InMemoryCallJournal
) -> None:
    # Enough for the budget's tokens alone, not for the whole output limit.
    transport = ScriptedTransport([_converse(_tool())])
    context = _context(scope, journal, amount_usd=3000 * OUT_PRICE / 1e6)
    failure = _fail(transport, _request(thinking_budget_tokens=3000), context)
    assert failure.failure is FailureClass.BUDGET_EXCEEDED
    assert failure.reason == "reservation_exhausted"
    assert transport.requests == [] and journal.dispatched == []


# --------------------------------------------------------------------------- #
# Adapters: Bedrock refuses what Claude would, the others refuse thinking
# --------------------------------------------------------------------------- #


def _adapter_request(**overrides: Any) -> AdapterRequest:
    base: dict[str, Any] = {
        "call_id": "CALL-thinking",
        "provider": Provider.AWS_BEDROCK,
        "model": PROFILE,
        "system": "s",
        "messages": (Message(role="user", content="m"),),
        "max_output_tokens": 4096,
        "output_schema": output_schema(Verdict),
        "schema_name": TOOL,
        "thinking_budget_tokens": 2048,
    }
    return AdapterRequest(**{**base, **overrides})


@pytest.mark.parametrize(
    "overrides",
    [{"temperature": 0.0}, {"thinking_budget_tokens": 4096}],
    ids=["temperature", "budget-not-below-limit"],
)
def test_bedrock_refuses_a_thinking_request_claude_would_reject_unsent(
    overrides: dict[str, Any],
) -> None:
    transport = ScriptedTransport([])
    signer = Signer()
    adapter = BedrockConverseAdapter(
        transport=transport, signer=signer, region="eu-central-1", model_id=PROFILE
    )
    with pytest.raises(ProviderError) as refused:
        asyncio.run(adapter.send(_adapter_request(**overrides)))
    assert refused.value.kind is ProviderErrorKind.OTHER
    assert refused.value.delivery is Delivery.NOT_SENT
    assert transport.requests == []


def test_bedrock_sends_thinking_without_a_schema_and_offers_no_tool() -> None:
    transport = ScriptedTransport([_converse(_reasoning(), _text("Hotovo."), stop="end_turn")])
    adapter = BedrockConverseAdapter(
        transport=transport, signer=Signer(), region="eu-central-1", model_id=PROFILE
    )
    response = asyncio.run(adapter.send(_adapter_request(output_schema=None, schema_name="")))
    body = transport.requests[0].body
    assert "toolConfig" not in body
    assert body["additionalModelRequestFields"]["thinking"]["budget_tokens"] == 2048
    assert response.text == "Hotovo." and response.structured is None


@pytest.mark.parametrize("name", ["anthropic", "openai", "claude_code"])
def test_adapters_that_do_not_send_thinking_refuse_it_unsent(name: str) -> None:
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
    assert refused.value.kind is ProviderErrorKind.OTHER
    assert refused.value.delivery is Delivery.NOT_SENT
    assert "does not send extended thinking" in str(refused.value)
    assert transport.requests == [] and runner.invocations == []
