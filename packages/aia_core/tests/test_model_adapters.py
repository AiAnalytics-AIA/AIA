"""Provider adapters against recorded exchanges: every field, every error class.

Each fixture under ``fixtures/model_adapters/<provider>/`` is one exchange and the
normalised result it must produce. They are **hand-authored from the providers'
published API references, not live captures** -- each file says so -- because no
route is approved to send anything yet (ADR 0008) and CI holds no credentials.
What they pin is the adapter's side of the contract: that a 529 is capacity and
not quota, that an out-of-credit 400 parks instead of failing, that a garbled
200 is uncertain rather than free, and that the provider's request id survives
on success and failure alike.

No network. No credentials. No provider SDK.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.domain.ai_contracts import (
    AdapterRequest,
    AdapterResponse,
    AgentDefinition,
    Delivery,
    Message,
    ModelRequest,
    ProviderAdapter,
    ProviderError,
    ProviderErrorKind,
    output_schema,
)
from aia_core.domain.ai_execution import ExecutionContext, ReservationView
from aia_core.domain.ai_models import ModelCapability, ModelRegistry
from aia_core.domain.licence import DataLineage
from aia_core.domain.licence_determinations import recorded_policy
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass, EgressPolicy, ProviderRoute, ResidencyZone
from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal
from aia_core.infrastructure.model_adapters import (
    AnthropicMessagesAdapter,
    ClaudeCodeCliAdapter,
    CliResult,
    OpenAIChatAdapter,
    RecordedCliRunner,
    RecordedTransport,
    StaticCredentials,
)
from aia_core.infrastructure.model_adapters.claude_code import SCRUBBED_ENV
from aia_core.infrastructure.model_adapters.transport import (
    parse_duration_seconds,
    plausible_wait,
    token_count,
)

FIXTURES = Path(__file__).parent / "fixtures" / "model_adapters"
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
SECRET = "test-secret-not-a-real-key"
CREDENTIALS = StaticCredentials({"provider-key": SECRET})

LICENCE = recorded_policy()


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str
    score: int


class LooseVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str
    note: str | None = None


def _adapter_request(*, structured: bool, strict: bool = False, model: str = "m") -> AdapterRequest:
    return AdapterRequest(
        call_id="CALL-test",
        provider=Provider.ANTHROPIC,
        model=model,
        system="Jsi pečlivý analytik.",
        messages=(Message(role="user", content="Shrň to."),),
        max_output_tokens=256,
        output_schema=output_schema(Verdict) if structured else None,
        schema_name="test_agent" if structured else "",
        strict_schema=strict,
    )


def _anthropic(fixture: dict[str, Any]) -> tuple[ProviderAdapter, Any]:
    transport = RecordedTransport.from_fixture(fixture)
    adapter = AnthropicMessagesAdapter(
        transport=transport,
        credentials=CREDENTIALS,
        credential_ref="provider-key",
        base_url="https://anthropic.test/",
        clock=lambda: NOW,
    )
    return adapter, transport


def _openai(fixture: dict[str, Any]) -> tuple[ProviderAdapter, Any]:
    transport = RecordedTransport.from_fixture(fixture)
    adapter = OpenAIChatAdapter(
        transport=transport,
        credentials=CREDENTIALS,
        credential_ref="provider-key",
        base_url="https://openai.test",
        clock=lambda: NOW,
    )
    return adapter, transport


def _claude_code(fixture: dict[str, Any]) -> tuple[ProviderAdapter, Any]:
    runner = RecordedCliRunner.from_fixture(fixture)
    return ClaudeCodeCliAdapter(runner=runner, clock=lambda: NOW), runner


ADAPTERS: dict[str, Callable[[dict[str, Any]], tuple[ProviderAdapter, Any]]] = {
    "anthropic": _anthropic,
    "openai": _openai,
    "claude_code": _claude_code,
}


def _fixtures() -> list[Any]:
    cases = []
    for path in sorted(FIXTURES.glob("*/*.json")):
        cases.append(pytest.param(path, id=f"{path.parent.name}/{path.stem}"))
    return cases


def test_every_provider_has_at_least_three_success_fixtures() -> None:
    """ARCHITECTURE.md §7: >= 3 fixtures per parser, asserting every field."""
    for provider in ADAPTERS:
        successes = [
            p
            for p in (FIXTURES / provider).glob("*.json")
            if "ok" in json.loads(p.read_text(encoding="utf-8"))["expect"]
        ]
        assert len(successes) >= 3, provider


def test_every_fixture_declares_that_it_is_not_a_live_capture() -> None:
    for path in FIXTURES.glob("*/*.json"):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        assert "not captured from a live call" in fixture["provenance"], path


def test_fixtures_cover_every_error_kind_an_adapter_can_emit() -> None:
    """Every class in the taxonomy is produced by at least one recorded exchange."""
    seen = set()
    for path in FIXTURES.glob("*/*.json"):
        expect = json.loads(path.read_text(encoding="utf-8"))["expect"]
        if "error" in expect:
            seen.add(expect["error"]["kind"])
    assert seen == {k.value for k in ProviderErrorKind}


@pytest.mark.parametrize("path", _fixtures())
def test_recorded_exchange(path: Path) -> None:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    adapter, _ = ADAPTERS[path.parent.name](fixture)
    request = _adapter_request(structured=bool(fixture.get("structured")))
    expect = fixture["expect"]

    if "ok" in expect:
        response = asyncio.run(adapter.send(request))
        assert isinstance(response, AdapterResponse)
        want = expect["ok"]
        assert response.text == want["text"]
        assert (dict(response.structured) if response.structured is not None else None) == want[
            "structured"
        ]
        assert response.finish_reason.value == want["finish_reason"]
        assert {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_input_tokens": response.usage.cache_read_input_tokens,
            "cache_write_input_tokens": response.usage.cache_write_input_tokens,
        } == want["usage"]
        assert response.provider_request_id == want["provider_request_id"]
        assert response.served_model == want["served_model"]
        assert response.reported_cost_usd == want["reported_cost_usd"]
        return

    with pytest.raises(ProviderError) as exc:
        asyncio.run(adapter.send(request))
    want = expect["error"]
    error = exc.value
    assert error.kind.value == want["kind"]
    assert error.delivery.value == want["delivery"]
    assert error.provider_request_id == want["provider_request_id"]
    assert (error.retry_after.isoformat() if error.retry_after else None) == want["retry_after"]
    assert error.http_status == want["http_status"]
    if "provider_error_type" in want:
        assert error.provider_error_type == want["provider_error_type"]


# --------------------------------------------------------------------------- #
# Request shapes
# --------------------------------------------------------------------------- #


def _success(provider: str) -> dict[str, Any]:
    name = {
        "anthropic": "success_forced_tool",
        "openai": "success_json_schema",
        "claude_code": "success_json_contract",
    }[provider]
    return json.loads((FIXTURES / provider / f"{name}.json").read_text(encoding="utf-8"))


def test_anthropic_structured_request_forces_the_contract_tool() -> None:
    adapter, transport = _anthropic(_success("anthropic"))
    asyncio.run(adapter.send(_adapter_request(structured=True)))
    sent = transport.requests[0]
    assert sent.url == "https://anthropic.test/v1/messages"
    assert sent.headers["x-api-key"] == SECRET
    assert sent.headers["anthropic-version"] == "2023-06-01"
    assert sent.body["tool_choice"] == {"type": "tool", "name": "test_agent"}
    assert sent.body["tools"][0]["input_schema"] == output_schema(Verdict)
    assert sent.body["system"] == "Jsi pečlivý analytik."
    assert sent.body["max_tokens"] == 256
    assert sent.redacted_headers()["x-api-key"] == "<redacted>"


def test_openai_strict_request_is_strictified_and_carries_the_call_id() -> None:
    adapter, transport = _openai(_success("openai"))
    asyncio.run(adapter.send(_adapter_request(structured=True, strict=True)))
    sent = transport.requests[0]
    assert sent.headers["authorization"] == f"Bearer {SECRET}"
    # AIA's id, recorded before sending, is the handle for an uncertain call.
    assert sent.headers["x-client-request-id"] == "CALL-test"
    fmt = sent.body["response_format"]["json_schema"]
    assert fmt["strict"] is True
    assert fmt["schema"]["additionalProperties"] is False
    assert sent.body["messages"][0] == {"role": "system", "content": "Jsi pečlivý analytik."}
    assert sent.redacted_headers()["authorization"] == "<redacted>"


def test_openai_non_strict_request_sends_the_contract_unchanged() -> None:
    adapter, transport = _openai(_success("openai"))
    request = AdapterRequest(
        call_id="CALL-loose",
        provider=Provider.OPENAI,
        model="m",
        system="s",
        messages=(Message(role="user", content="u"),),
        max_output_tokens=16,
        output_schema=output_schema(LooseVerdict),
        schema_name="loose",
        strict_schema=False,
    )
    asyncio.run(adapter.send(request))
    fmt = transport.requests[0].body["response_format"]["json_schema"]
    assert fmt["strict"] is False
    assert fmt["schema"] == output_schema(LooseVerdict)


def test_claude_code_invocation_scrubs_every_credential_override() -> None:
    """An API key in the CLI's environment moves the call off the subscription."""
    adapter, runner = _claude_code(_success("claude_code"))
    asyncio.run(adapter.send(_adapter_request(structured=True, model="subscription-default")))
    invocation = runner.invocations[0]
    assert set(invocation["unset_env"]) == set(SCRUBBED_ENV)
    assert "ANTHROPIC_API_KEY" in invocation["unset_env"]
    argv = invocation["argv"]
    assert argv[:4] == ["claude", "-p", "--output-format", "json"]
    assert argv[argv.index("--model") + 1] == "subscription-default"
    system = argv[argv.index("--system-prompt") + 1]
    assert system.startswith("Jsi pečlivý analytik.")
    assert '"additionalProperties":false' in system
    assert invocation["stdin"] == "Shrň to."


def test_claude_code_multi_turn_is_rendered_as_one_transcript() -> None:
    runner = RecordedCliRunner(result=CliResult(exit_code=0, stdout='{"result":"x"}', stderr=""))
    adapter = ClaudeCodeCliAdapter(runner=runner)
    request = AdapterRequest(
        call_id="c",
        provider=Provider.CLAUDE_CODE,
        model="m",
        system="s",
        messages=(
            Message(role="user", content="first"),
            Message(role="assistant", content="answer"),
            Message(role="user", content="fix it"),
        ),
        max_output_tokens=16,
    )
    asyncio.run(adapter.send(request))
    assert (
        runner.invocations[0]["stdin"] == "[user]\nfirst\n\n[assistant]\nanswer\n\n[user]\nfix it"
    )


def test_claude_code_rejects_a_turn_limit_below_one() -> None:
    with pytest.raises(ValueError):
        ClaudeCodeCliAdapter(runner=RecordedCliRunner(), max_turns=0)


@pytest.mark.parametrize("factory", [_anthropic, _openai])
def test_missing_credential_is_missing_and_nothing_is_sent(
    factory: Callable[[dict[str, Any]], tuple[ProviderAdapter, Any]],
) -> None:
    adapter, transport = factory(_success("openai"))
    adapter._credentials = StaticCredentials({})  # type: ignore[attr-defined]
    with pytest.raises(ProviderError) as exc:
        asyncio.run(adapter.send(_adapter_request(structured=False)))
    assert exc.value.kind is ProviderErrorKind.MISSING
    assert exc.value.delivery is Delivery.NOT_SENT
    assert transport.requests == []


def test_blank_credential_is_missing() -> None:
    adapter, transport = _anthropic(_success("anthropic"))
    adapter._credentials = StaticCredentials({"provider-key": "  "})  # type: ignore[attr-defined]
    with pytest.raises(ProviderError) as exc:
        asyncio.run(adapter.send(_adapter_request(structured=False)))
    assert exc.value.kind is ProviderErrorKind.MISSING
    assert transport.requests == []


# --------------------------------------------------------------------------- #
# Shared parsing guards (A7)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "seconds"),
    [
        ("30", 30.0),
        ("1.5", 1.5),
        ("20ms", 0.02),
        ("1s", 1.0),
        ("6m0s", 360.0),
        ("1h2m3s", 3723.0),
        (None, None),
        ("", None),
        ("soon, maybe 5s", None),
        ("5s later", None),
        ("-", None),
        ("inf", None),
        ("nan", None),
        ("1e400", None),
    ],
)
def test_duration_parsing_consumes_the_whole_value(raw: str | None, seconds: float | None) -> None:
    assert parse_duration_seconds(raw) == seconds


def test_implausible_waits_are_discarded() -> None:
    assert plausible_wait(NOW, parse_duration_seconds("inf")) is None
    assert plausible_wait(NOW, -1) is None
    assert plausible_wait(NOW, 8 * 24 * 3600) is None
    assert plausible_wait(NOW, 0) == NOW


@pytest.mark.parametrize("value", [True, -1, 1.5, "12", None])
def test_only_non_negative_integers_are_token_counts(value: Any) -> None:
    assert token_count(value) is None
    assert token_count(12) == 12


# --------------------------------------------------------------------------- #
# End to end: gateway over an adapter over a recorded exchange
# --------------------------------------------------------------------------- #


def test_gateway_over_a_recorded_openai_exchange(
    model_registry: ModelRegistry, scoped: Any
) -> None:
    adapter, transport = _openai(_success("openai"))
    gateway = GovernedModelGateway(
        registry=model_registry,
        licence=LICENCE,
        egress=EgressPolicy(
            routes=(
                ProviderRoute(
                    route_id="openai-direct",
                    provider="openai",
                    zone=ResidencyZone.NON_EU,
                    approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
                ),
            )
        ),
        adapters={"openai-direct": adapter},
    )
    journal = InMemoryCallJournal()
    context = ExecutionContext(
        scope=scoped.scope(user="researcher", study="primary"),
        runtime_version="rv",
        journal=journal,
        reservation=ReservationView(reservation_id="RSV-1", amount_usd=1.0),
    )
    agent = AgentDefinition(
        agent_id="test-agent",
        version="1",
        capability=ModelCapability.FAST_EXTRACTION,
        prompt_id="p",
        prompt_version="1",
        output_contract=Verdict,
        max_output_tokens=256,
    )
    result = asyncio.run(
        gateway.invoke(
            ModelRequest(
                agent=agent,
                policy_version="policy-test-v1",
                data_classification=DataClass.CLASS_C_INTERNAL,
                data_lineage=DataLineage.none(),
                system="s",
                messages=(Message(role="user", content="u"),),
            ),
            context,
        )
    )
    assert isinstance(result.output, Verdict)
    assert result.provider_request_id == "req_openai_ok"
    assert result.served_model == "extraction-small-2026-08-01"
    # 200 uncached at $0.15/M + 1000 cached at $0.075/M + 50 out at $0.60/M
    assert result.actual_cost_usd == pytest.approx((200 * 0.15 + 1000 * 0.075 + 50 * 0.6) / 1e6)
    # The id on the wire is the id in the ledger.
    assert transport.requests[0].headers["x-client-request-id"] == result.call_id
    assert journal.dispatched[0].call_id == result.call_id
