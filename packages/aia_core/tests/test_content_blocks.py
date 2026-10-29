"""Content blocks beyond text on a model message (ADR 0026 Amendment 2026-10-28, G1).

A Lead turn becomes a tool conversation: the model answers with tool calls and reasoning,
AIA sends back tool results and the reasoning unchanged. These are the contracts that
carry it. A text message stays exactly what it was (its bytes are pinned by
``test_model_request_golden.py``); a message of blocks is closed by role, is
fingerprinted and bounded by its blocks, and never reaches a text-only path or adapter.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from aia_core.application.model_gateway import input_token_bound
from aia_core.domain.ai_contracts import (
    AdapterRequest,
    AdapterResponse,
    CallPurpose,
    Delivery,
    FinishReason,
    Message,
    ModelUsage,
    ProviderError,
    ProviderErrorKind,
    ReasoningBlock,
    TextBlock,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
    canonical_json,
    input_fingerprint,
)
from aia_core.domain.providers import Provider
from aia_core.infrastructure.model_adapters import (
    AnthropicMessagesAdapter,
    ClaudeCodeCliAdapter,
    OpenAIChatAdapter,
    RecordedCliRunner,
    RecordedTransport,
    StaticCredentials,
)
from aia_core.infrastructure.model_adapters.transport import render_transcript

#: A reasoning block as Converse returns it (shape from the provider's documentation;
#: a hand-written example, not a recording).
REASONING = {
    "reasoningContent": {"reasoningText": {"text": "Nejdřív výsledky.", "signature": "c2ln"}}
}
REDACTED = {"reasoningContent": {"redactedContent": "b3BhcXVl"}}


def _assistant() -> Message:
    return Message(
        role="assistant",
        content=(
            ReasoningBlock.of(Provider.AWS_BEDROCK, REASONING),
            TextBlock("Přečtu výsledky."),
            ToolUseBlock.of("tu_1", "run_results", {"run_id": "run-1"}),
            ToolUseBlock.of("tu_2", "readiness", {}),
        ),
    )


def _results() -> Message:
    return Message(
        role="user",
        content=(
            ToolResultBlock("tu_1", '{"rows":[]}'),
            ToolResultBlock("tu_2", '{"code":"not_in_context"}', is_error=True),
        ),
    )


# --------------------------------------------------------------------------- #
# The blocks and the message
# --------------------------------------------------------------------------- #


def test_a_tool_conversation_is_carried_as_blocks() -> None:
    assistant, results = _assistant(), _results()
    assert assistant.has_blocks and results.has_blocks
    assert [b.name for b in assistant.blocks if isinstance(b, ToolUseBlock)] == [
        "run_results",
        "readiness",
    ]
    tool_use = assistant.blocks[2]
    assert isinstance(tool_use, ToolUseBlock)
    assert tool_use.input == {"run_id": "run-1"}


def test_a_text_message_is_what_it_was() -> None:
    message = Message(role="user", content="Ahoj")
    assert message.content == "Ahoj"
    assert message.text == "Ahoj"
    assert not message.has_blocks
    assert message.blocks == (TextBlock("Ahoj"),)


def test_a_message_of_blocks_has_no_text_to_guess() -> None:
    with pytest.raises(ValueError, match="content blocks"):
        _ = _assistant().text


def test_a_reasoning_block_keeps_the_providers_block_as_it_came() -> None:
    block = ReasoningBlock.of(Provider.AWS_BEDROCK, REASONING)
    assert block.provider_block == REASONING
    assert not block.redacted
    redacted = ReasoningBlock.of(Provider.AWS_BEDROCK, REDACTED, redacted=True)
    assert redacted.redacted
    assert redacted.provider_block == REDACTED


@pytest.mark.parametrize(
    ("role", "blocks", "words"),
    [
        ("user", (ToolUseBlock.of("t", "x", {}),), "assistant"),
        ("user", (ReasoningBlock.of(Provider.AWS_BEDROCK, REASONING),), "assistant"),
        ("assistant", (ToolResultBlock("t", "{}"),), "user"),
        ("user", (), "at least one"),
    ],
    ids=["tool-use-from-user", "reasoning-from-user", "result-from-assistant", "empty"],
)
def test_a_block_the_role_cannot_hold_is_refused(
    role: Any, blocks: tuple[Any, ...], words: str
) -> None:
    with pytest.raises(ValueError, match=words):
        Message(role=role, content=blocks)


def test_a_block_with_a_blank_id_or_name_is_refused() -> None:
    with pytest.raises(ValueError):
        ToolUseBlock.of(" ", "x", {})
    with pytest.raises(ValueError):
        ToolUseBlock.of("t", "", {})
    with pytest.raises(ValueError):
        ToolResultBlock("", "{}")


def test_a_tool_input_must_be_a_json_object() -> None:
    with pytest.raises(ValueError, match="object"):
        ToolUseBlock("t", "x", "[1, 2]")
    with pytest.raises(ValueError):
        ToolUseBlock("t", "x", "not json")


def test_a_reasoning_block_is_a_json_object() -> None:
    with pytest.raises(ValueError, match="reasoning"):
        ReasoningBlock(Provider.AWS_BEDROCK, "[1]")
    with pytest.raises(ValueError, match="reasoning"):
        ReasoningBlock(Provider.AWS_BEDROCK, "{}")


# --------------------------------------------------------------------------- #
# Fingerprint and bound
# --------------------------------------------------------------------------- #


def _outbound(*messages: Message) -> AdapterRequest:
    return AdapterRequest(
        call_id="c",
        provider=Provider.AWS_BEDROCK,
        model="m",
        system="s",
        messages=messages,
        max_output_tokens=1024,
    )


def test_the_fingerprint_is_of_every_block_sent() -> None:
    ask = Message(role="user", content="Co běh zjistil?")
    base = input_fingerprint(_outbound(ask, _assistant(), _results()))
    other_reasoning = Message(
        role="assistant",
        content=(
            ReasoningBlock.of(
                Provider.AWS_BEDROCK,
                {"reasoningContent": {"reasoningText": {"text": "Jinak.", "signature": "c2ln"}}},
            ),
            *_assistant().blocks[1:],
        ),
    )
    other_result = Message(role="user", content=(ToolResultBlock("tu_1", '{"rows":[1]}'),))
    assert input_fingerprint(_outbound(ask, other_reasoning, _results())) != base
    assert input_fingerprint(_outbound(ask, _assistant(), other_result)) != base
    assert input_fingerprint(_outbound(ask, _assistant(), _results())) == base


def test_the_bound_counts_every_block() -> None:
    ask = Message(role="user", content="Co běh zjistil?")
    plain = input_token_bound(_outbound(ask))
    with_blocks = input_token_bound(_outbound(ask, _assistant(), _results()))
    blocks_bytes = sum(
        len(canonical_json(b.wire()).encode("utf-8"))
        for m in (_assistant(), _results())
        for b in m.blocks
    )
    assert with_blocks - plain >= blocks_bytes


# --------------------------------------------------------------------------- #
# The purpose and the response
# --------------------------------------------------------------------------- #


def test_a_tool_round_is_a_purpose_the_ledger_can_hold() -> None:
    assert CallPurpose("TOOL_ROUND") is CallPurpose.TOOL_ROUND
    # ai_usage_events.purpose is String(32).
    assert all(len(p.value) <= 32 for p in CallPurpose)


def test_a_response_carries_its_blocks_in_order() -> None:
    blocks = _assistant().blocks
    response = AdapterResponse(
        text="Přečtu výsledky.",
        finish_reason=FinishReason.COMPLETED,
        usage=ModelUsage(input_tokens=1, output_tokens=1),
        provider_request_id=None,
        blocks=blocks,
    )
    assert [b.tool_use_id for b in response.tool_calls] == ["tu_1", "tu_2"]
    assert response.reasoning == (blocks[0],)


def test_a_response_without_blocks_is_todays_response() -> None:
    response = AdapterResponse(
        text="x", finish_reason=FinishReason.COMPLETED, usage=ModelUsage(), provider_request_id=None
    )
    assert response.blocks == ()
    assert response.tool_calls == ()


def test_a_response_holds_no_block_a_user_sends() -> None:
    with pytest.raises(ValueError, match="assistant"):
        AdapterResponse(
            text="",
            finish_reason=FinishReason.COMPLETED,
            usage=ModelUsage(),
            provider_request_id=None,
            blocks=(ToolResultBlock("t", "{}"),),
        )


# --------------------------------------------------------------------------- #
# The adapters that carry no blocks or tools refuse them
# --------------------------------------------------------------------------- #


def _adapters() -> dict[str, Any]:
    credentials = StaticCredentials({"k": "secret"})
    return {
        "anthropic": AnthropicMessagesAdapter(
            transport=RecordedTransport(),
            credentials=credentials,
            credential_ref="k",
            base_url="https://anthropic.test",
        ),
        "openai": OpenAIChatAdapter(
            transport=RecordedTransport(),
            credentials=credentials,
            credential_ref="k",
            base_url="https://openai.test",
        ),
        "claude_code": ClaudeCodeCliAdapter(runner=RecordedCliRunner()),
    }


# Bedrock carries both from G2 (test_bedrock_tool_use.py).
@pytest.mark.parametrize("name", ["anthropic", "openai", "claude_code"])
def test_an_adapter_refuses_a_message_of_blocks_unsent(name: str) -> None:
    adapter = _adapters()[name]
    request = AdapterRequest(
        call_id="c",
        provider=adapter.provider,
        model="m",
        system="s",
        messages=(Message(role="user", content="Ahoj"), _assistant(), _results()),
        max_output_tokens=1024,
    )
    with pytest.raises(ProviderError) as refused:
        asyncio.run(adapter.send(request))
    assert refused.value.delivery is Delivery.NOT_SENT
    assert refused.value.kind is ProviderErrorKind.OTHER
    assert "content blocks" in str(refused.value)


def test_a_transcript_refuses_a_message_of_blocks() -> None:
    with pytest.raises(ValueError, match="content blocks"):
        render_transcript((Message(role="user", content="Ahoj"), _assistant()))


def test_a_model_result_carries_the_answering_responses_blocks() -> None:
    from dataclasses import fields

    from aia_core.domain.ai_contracts import ModelResult

    [blocks] = [f for f in fields(ModelResult) if f.name == "blocks"]
    assert blocks.default == ()


def test_content_is_text_or_a_tuple_of_blocks() -> None:
    with pytest.raises(ValueError, match="text or a tuple"):
        Message(role="user", content=[ToolResultBlock("t", "{}")])  # type: ignore[arg-type]


def test_an_unknown_role_is_refused_as_a_value() -> None:
    with pytest.raises(ValueError, match="role"):
        Message(role="system", content=(TextBlock("x"),))  # type: ignore[arg-type]


def test_the_same_call_is_the_same_block_however_its_json_was_spaced() -> None:
    assert ToolUseBlock("t", "x", '{ "b": 1, "a": 2 }') == ToolUseBlock.of(
        "t", "x", {"a": 2, "b": 1}
    )
    spaced = '{ "reasoningContent": {"redactedContent": "b3BhcXVl"} }'
    assert ReasoningBlock(Provider.AWS_BEDROCK, spaced) == ReasoningBlock.of(
        Provider.AWS_BEDROCK, REDACTED
    )


def test_the_gateway_hands_on_the_answering_responses_blocks(scoped: Any) -> None:
    from pydantic import BaseModel, ConfigDict

    from aia_core.application.model_gateway import GovernedModelGateway
    from aia_core.domain.ai_contracts import AgentDefinition, ModelRequest
    from aia_core.domain.ai_execution import ExecutionContext, ReservationView
    from aia_core.domain.ai_models import ModelCapability, parse_model_config
    from aia_core.domain.licence import DataLineage
    from aia_core.domain.licence_determinations import recorded_policy
    from aia_core.domain.residency import DataClass, EgressPolicy, ProviderRoute, ResidencyZone
    from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal

    class Answer(BaseModel):
        model_config = ConfigDict(extra="forbid")
        ok: bool

    blocks = (
        ReasoningBlock.of(Provider.AWS_BEDROCK, REASONING),
        ToolUseBlock.of("tu_1", "answer", {"ok": True}),
    )

    class Adapter:
        provider = Provider.AWS_BEDROCK

        async def send(self, request: AdapterRequest) -> AdapterResponse:
            return AdapterResponse(
                text="",
                finish_reason=FinishReason.COMPLETED,
                usage=ModelUsage(input_tokens=10, output_tokens=5),
                provider_request_id="r",
                structured={"ok": True},
                blocks=blocks,
            )

    model, route = "eu.test.blocks:1", "bedrock-eu-blocks"
    registry = parse_model_config(
        {
            "models": [
                {
                    "provider": Provider.AWS_BEDROCK.value,
                    "model": model,
                    "capabilities": [ModelCapability.CRITIC.value],
                    "max_output_tokens": 4096,
                    "context_window_tokens": 200000,
                    "pricing": {"input_usd_per_mtok": 1.0, "output_usd_per_mtok": 2.0},
                    "supports_strict_schema": False,
                }
            ],
            "policies": [
                {
                    "version": "p1",
                    "allowed_providers": [Provider.AWS_BEDROCK.value],
                    "bindings": {
                        ModelCapability.CRITIC.value: {
                            "provider": Provider.AWS_BEDROCK.value,
                            "model": model,
                            "route_id": route,
                        }
                    },
                }
            ],
        }
    )
    gateway = GovernedModelGateway(
        registry=registry,
        egress=EgressPolicy(
            routes=(
                ProviderRoute(
                    route_id=route,
                    provider=Provider.AWS_BEDROCK.value,
                    zone=ResidencyZone.EU,
                    eu_processing_approved=True,
                    excluded_from_training=True,
                    approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
                ),
            )
        ),
        licence=recorded_policy(),
        adapters={route: Adapter()},
    )
    request = ModelRequest(
        agent=AgentDefinition(
            agent_id="aia.test.blocks",
            version="1",
            capability=ModelCapability.CRITIC,
            prompt_id="aia.test.blocks",
            prompt_version="1",
            output_contract=Answer,
        ),
        policy_version="p1",
        data_classification=DataClass.CLASS_C_INTERNAL,
        data_lineage=DataLineage.none(),
        system="s",
        messages=(Message(role="user", content="m"),),
    )
    context = ExecutionContext(
        scope=scoped.scope(user="researcher", study="primary"),
        runtime_version="r",
        journal=InMemoryCallJournal(),
        run_id="RUN-1",
        step_id="STP-1",
        attempt_id="ATT-1",
        reservation=ReservationView(reservation_id="RSV-1", amount_usd=5.0),
    )
    result = asyncio.run(gateway.invoke(request, context))
    assert result.blocks == blocks
    assert [c.tool_use_id for c in result.tool_calls] == ["tu_1"]


# --------------------------------------------------------------------------- #
# Tools offered beside the output contract (G2)
# --------------------------------------------------------------------------- #

READ = ToolSpec.of(
    "run_results",
    "Admitted results of one run.",
    {"type": "object", "properties": {"run_id": {"type": "string"}}, "required": ["run_id"]},
)


def test_a_tool_spec_is_a_named_object_schema() -> None:
    assert READ.schema["type"] == "object"
    with pytest.raises(ValueError, match="name"):
        ToolSpec.of("run results", "x", {"type": "object"})
    with pytest.raises(ValueError, match="says what"):
        ToolSpec.of("x", " ", {"type": "object"})
    with pytest.raises(ValueError, match="object"):
        ToolSpec.of("x", "y", {"type": "string"})
    assert ToolSpec("x", "y", '{ "type": "object" }') == ToolSpec.of("x", "y", {"type": "object"})


def test_an_offered_tool_is_named_once_and_never_as_the_output() -> None:
    with pytest.raises(ValueError, match="once"):
        AdapterRequest(
            call_id="c",
            provider=Provider.AWS_BEDROCK,
            model="m",
            system="s",
            messages=(Message(role="user", content="m"),),
            max_output_tokens=1024,
            tools=(READ, READ),
        )
    with pytest.raises(ValueError, match="output contract"):
        AdapterRequest(
            call_id="c",
            provider=Provider.AWS_BEDROCK,
            model="m",
            system="s",
            messages=(Message(role="user", content="m"),),
            max_output_tokens=1024,
            output_schema={"type": "object"},
            schema_name="run_results",
            tools=(READ,),
        )


def _offering(*tools: ToolSpec) -> AdapterRequest:
    return AdapterRequest(
        call_id="c",
        provider=Provider.AWS_BEDROCK,
        model="m",
        system="s",
        messages=(Message(role="user", content="Co běh zjistil?"),),
        max_output_tokens=1024,
        tools=tools,
    )


def test_the_fingerprint_and_the_bound_count_the_offered_tools() -> None:
    assert input_fingerprint(_offering(READ)) != input_fingerprint(_offering())
    grown = input_token_bound(_offering(READ)) - input_token_bound(_offering())
    assert grown >= len(canonical_json(READ.wire()).encode("utf-8"))


# Bedrock carries both from G2 (test_bedrock_tool_use.py).
@pytest.mark.parametrize("name", ["anthropic", "openai", "claude_code"])
def test_an_adapter_refuses_an_offered_tool_unsent(name: str) -> None:
    adapter = _adapters()[name]
    request = AdapterRequest(
        call_id="c",
        provider=adapter.provider,
        model="m",
        system="s",
        messages=(Message(role="user", content="Ahoj"),),
        max_output_tokens=1024,
        tools=(READ,),
    )
    with pytest.raises(ProviderError) as refused:
        asyncio.run(adapter.send(request))
    assert refused.value.delivery is Delivery.NOT_SENT
    assert "tools" in str(refused.value)


def test_a_tool_result_says_something() -> None:
    # Converse refuses a blank text block; an empty read answers with a JSON value, never "".
    with pytest.raises(ValueError, match="result"):
        ToolResultBlock("t", " ")
