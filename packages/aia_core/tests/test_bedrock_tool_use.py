"""The Bedrock adapter carries a tool conversation (ADR 0026 Amendment 2026-10-28, G2).

The exchanges under ``fixtures/converse_tool_use/`` are HAND-WRITTEN from
the Converse API reference until the G2 capture from develop's Lead route replaces them
(each file's ``provenance`` says which it is). What they hold the adapter to:

- several tools offered beside the output contract, the output tool first, never forced;
- every ``toolUse`` block kept in order, the output tool's input still the structured
  answer;
- every reasoning block, redacted or not, kept exactly as it came and sent back
  unchanged, signature included;
- tool results sent as ``toolResult`` blocks, an error marked as one;
- an answer in text kept as text (the gateway's violation, not the adapter's);
- another provider's reasoning refused unsent.

A request that offers nothing and holds no block still sends the bytes it always sent
(``test_model_request_golden.py``). No network.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.ai_contracts import (
    AdapterRequest,
    Delivery,
    FinishReason,
    Message,
    ProviderError,
    ReasoningBlock,
    TextBlock,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)
from aia_core.domain.ai_models import RequestProfile, StructuredOutput, ThinkingMode
from aia_core.domain.providers import Provider
from aia_core.infrastructure.model_adapters import BedrockConverseAdapter, RecordedTransport
from aia_core.infrastructure.model_adapters.transport import HttpResponse

FIXTURES = Path(__file__).parent / "fixtures" / "converse_tool_use"
MODEL = "eu.test.tool-model:1"  # a test id, not a real profile
OUTPUT = "aia_research_lead_output"
ADAPTIVE = RequestProfile(
    structured_output=StructuredOutput.AUTO_TOOL,
    thinking=ThinkingMode.ADAPTIVE,
    accepts_sampling=False,
)

RUN_ID = {"type": "object", "properties": {"run_id": {"type": "string"}}, "required": ["run_id"]}
READS = (
    ToolSpec.of("run_results", "Admitted results of one run.", RUN_ID),
    ToolSpec.of("run_status", "Status, steps and spend of one run.", RUN_ID),
    ToolSpec.of("readiness", "Readiness checks on the working revision.", {"type": "object"}),
)
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


def _fixture(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


def _content(name: str) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = _fixture(name)["response"]["body"]["output"]["message"][
        "content"
    ]
    return content


def _adapter(name: str | None = None) -> tuple[BedrockConverseAdapter, RecordedTransport]:
    response = None
    if name is not None:
        recorded = _fixture(name)["response"]
        response = HttpResponse(
            status=recorded["status"], headers=recorded["headers"], body=recorded["body"]
        )
    transport = RecordedTransport(response=response)
    adapter = BedrockConverseAdapter(
        transport=transport, signer=Signer(), region="eu-central-1", model_id=MODEL
    )
    return adapter, transport


def _request(*messages: Message, tools: tuple[ToolSpec, ...] = READS) -> AdapterRequest:
    return AdapterRequest(
        call_id="call-g2",
        provider=Provider.AWS_BEDROCK,
        model=MODEL,
        system="Jsi Vedoucí výzkumu.",
        messages=messages or (Message(role="user", content="Shrň běh run-fict-1."),),
        max_output_tokens=2048,
        output_schema=OUTPUT_SCHEMA,
        schema_name=OUTPUT,
        request_profile=ADAPTIVE,
        tools=tools,
    )


def test_every_fixture_says_whether_it_was_recorded() -> None:
    for path in sorted(FIXTURES.glob("*.json")):
        provenance = json.loads(path.read_text(encoding="utf-8"))["provenance"]
        assert provenance.startswith(("HAND-WRITTEN", "RECORDED")), path.name


# --------------------------------------------------------------------------- #
# What is offered
# --------------------------------------------------------------------------- #


def test_the_reads_are_offered_beside_the_output_tool_never_forced() -> None:
    adapter, _ = _adapter()
    body = adapter.build_body(_request())
    tools = body["toolConfig"]["tools"]
    # The output tool first: what a reader of tools[0] has always found there.
    assert [t["toolSpec"]["name"] for t in tools] == [OUTPUT, *(t.name for t in READS)]
    assert tools[1]["toolSpec"] == {
        "name": "run_results",
        "description": "Admitted results of one run.",
        "inputSchema": {"json": RUN_ID},
    }
    assert body["toolConfig"]["toolChoice"] == {"auto": {}}


def test_reads_without_an_output_contract_are_offered_alone() -> None:
    adapter, _ = _adapter()
    request = AdapterRequest(
        call_id="c",
        provider=Provider.AWS_BEDROCK,
        model=MODEL,
        system="s",
        messages=(Message(role="user", content="m"),),
        max_output_tokens=2048,
        request_profile=ADAPTIVE,
        tools=READS[:1],
    )
    body = adapter.build_body(request)
    assert [t["toolSpec"]["name"] for t in body["toolConfig"]["tools"]] == ["run_results"]
    assert body["toolConfig"]["toolChoice"] == {"auto": {}}


# --------------------------------------------------------------------------- #
# What comes back
# --------------------------------------------------------------------------- #


def test_several_tool_uses_are_kept_in_order_with_the_reasoning() -> None:
    adapter, _ = _adapter("several_tool_uses")
    response = asyncio.run(adapter.send(_request()))
    raw = _content("several_tool_uses")
    assert response.blocks == (
        ReasoningBlock.of(Provider.AWS_BEDROCK, raw[0]),
        TextBlock("Přečtu výsledky a stav běhu."),
        ToolUseBlock.of("tooluse_r1", "run_results", {"run_id": "run-fict-1"}),
        ToolUseBlock.of("tooluse_r2", "run_status", {"run_id": "run-fict-1"}),
    )
    assert [c.name for c in response.tool_calls] == ["run_results", "run_status"]
    assert response.structured is None
    assert response.text == "Přečtu výsledky a stav běhu."
    assert response.finish_reason is FinishReason.COMPLETED


def test_a_redacted_reasoning_block_is_kept_as_it_came() -> None:
    adapter, _ = _adapter("redacted_reasoning")
    response = asyncio.run(adapter.send(_request()))
    [reasoning] = response.reasoning
    assert reasoning.redacted
    assert reasoning.provider_block == _content("redacted_reasoning")[0]
    assert [c.name for c in response.tool_calls] == ["readiness"]


def test_the_output_tool_is_still_the_structured_answer() -> None:
    adapter, _ = _adapter("output_tool")
    response = asyncio.run(adapter.send(_request()))
    assert response.structured == {"reply": "Běh skončil; výsledky jsou připravené."}
    assert [c.name for c in response.tool_calls] == [OUTPUT]
    assert len(response.reasoning) == 1


def test_an_answer_in_text_is_kept_as_text() -> None:
    adapter, _ = _adapter("answer_in_text")
    response = asyncio.run(adapter.send(_request()))
    assert response.text == "Běh skončil a výsledky jsou připravené."
    assert response.tool_calls == ()
    assert response.structured is None


# --------------------------------------------------------------------------- #
# What is sent back
# --------------------------------------------------------------------------- #


def _round_two(name: str) -> tuple[Message, Message, Message]:
    adapter, _ = _adapter(name)
    ask = Message(role="user", content="Shrň běh run-fict-1.")
    answered = asyncio.run(adapter.send(_request(ask)))
    results = Message(
        role="user",
        content=tuple(
            ToolResultBlock(
                c.tool_use_id, '{"code":"not_in_context"}' if i else '{"rows":[]}', is_error=i > 0
            )
            for i, c in enumerate(answered.tool_calls)
        ),
    )
    return ask, Message(role="assistant", content=answered.blocks), results


@pytest.mark.parametrize("name", ["several_tool_uses", "redacted_reasoning"])
def test_the_answer_goes_back_exactly_as_it_came(name: str) -> None:
    adapter, _ = _adapter()
    ask, assistant, results = _round_two(name)
    body = adapter.build_body(_request(ask, assistant, results))
    assert body["messages"][1] == {"role": "assistant", "content": _content(name)}


def test_tool_results_go_back_as_tool_result_blocks() -> None:
    adapter, _ = _adapter()
    ask, assistant, results = _round_two("several_tool_uses")
    body = adapter.build_body(_request(ask, assistant, results))
    assert body["messages"][2] == {
        "role": "user",
        "content": [
            {"toolResult": {"toolUseId": "tooluse_r1", "content": [{"text": '{"rows":[]}'}]}},
            {
                "toolResult": {
                    "toolUseId": "tooluse_r2",
                    "content": [{"text": '{"code":"not_in_context"}'}],
                    "status": "error",
                }
            },
        ],
    }


def test_the_round_is_signed_and_sent_as_built() -> None:
    adapter, transport = _adapter("output_tool")
    ask, assistant, results = _round_two("several_tool_uses")
    asyncio.run(adapter.send(_request(ask, assistant, results)))
    [sent] = transport.requests
    assert sent.raw_body is not None
    assert json.loads(sent.raw_body) == adapter.build_body(_request(ask, assistant, results))


def test_another_providers_reasoning_is_refused_unsent() -> None:
    adapter, transport = _adapter("output_tool")
    foreign = Message(
        role="assistant",
        content=(
            ReasoningBlock.of(Provider.ANTHROPIC, {"type": "thinking", "thinking": "x"}),
            ToolUseBlock.of("t1", "readiness", {}),
        ),
    )
    results = Message(role="user", content=(ToolResultBlock("t1", "{}"),))
    with pytest.raises(ProviderError) as refused:
        asyncio.run(adapter.send(_request(Message(role="user", content="m"), foreign, results)))
    assert refused.value.delivery is Delivery.NOT_SENT
    assert "reasoning" in str(refused.value)
    assert transport.requests == []


def test_a_tool_use_without_its_id_is_an_unreadable_answer() -> None:
    recorded = _fixture("several_tool_uses")["response"]
    recorded["body"]["output"]["message"]["content"][2]["toolUse"]["toolUseId"] = ""
    transport = RecordedTransport(
        response=HttpResponse(status=200, headers=recorded["headers"], body=recorded["body"])
    )
    adapter = BedrockConverseAdapter(
        transport=transport, signer=Signer(), region="eu-central-1", model_id=MODEL
    )
    with pytest.raises(ProviderError) as unreadable:
        asyncio.run(adapter.send(_request()))
    # Bedrock answered and may have billed it: never NOT_SENT.
    assert unreadable.value.delivery is Delivery.UNKNOWN


def test_a_conversation_offering_no_tool_is_refused_unsent() -> None:
    # Converse requires toolConfig whenever the history holds toolUse or toolResult blocks.
    adapter, transport = _adapter("output_tool")
    ask, assistant, results = _round_two("several_tool_uses")
    request = AdapterRequest(
        call_id="c",
        provider=Provider.AWS_BEDROCK,
        model=MODEL,
        system="s",
        messages=(ask, assistant, results),
        max_output_tokens=2048,
        request_profile=ADAPTIVE,
    )
    with pytest.raises(ProviderError) as refused:
        asyncio.run(adapter.send(request))
    assert refused.value.delivery is Delivery.NOT_SENT
    assert "toolConfig" in str(refused.value)
    assert transport.requests == []


def test_a_block_of_a_kind_the_adapter_does_not_know_is_an_unreadable_answer() -> None:
    recorded = _fixture("several_tool_uses")["response"]
    recorded["body"]["output"]["message"]["content"].insert(
        1, {"citationsContent": {"content": [{"text": "x"}]}}
    )
    transport = RecordedTransport(
        response=HttpResponse(status=200, headers=recorded["headers"], body=recorded["body"])
    )
    adapter = BedrockConverseAdapter(
        transport=transport, signer=Signer(), region="eu-central-1", model_id=MODEL
    )
    # Dropping it would send back a different turn than the model wrote.
    with pytest.raises(ProviderError) as unreadable:
        asyncio.run(adapter.send(_request()))
    assert unreadable.value.delivery is Delivery.UNKNOWN
