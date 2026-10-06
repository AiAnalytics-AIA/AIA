"""Claude Code CLI adapter (the subscription runtime).

Runs ``claude -p --output-format json`` and reads the single JSON result object
it prints. The subscription has no marginal API cost, so this provider is never
budget-checked -- which makes one thing critical: the child process must not see
an API key. With ``ANTHROPIC_API_KEY`` in its environment the CLI bills the
metered API instead of the subscription, which is precisely a silent switch from
a flat-rate runtime to a metered one. :data:`SCRUBBED_ENV` is removed from every
invocation, and the reference's diagnostic trap (machine-level
``ANTHROPIC_AUTH_TOKEN`` / ``ANTHROPIC_BASE_URL`` overriding the intended
credential) is closed the same way.

The CLI takes one prompt, so structured output is a *JSON contract* appended to
the system prompt -- the reference router's second rung -- and the answer is
still validated by AIA, never trusted.

Classification, from the result object and the process:

===================================  ==============  =========================
signal                               kind            note
===================================  ==============  =========================
``subtype: error_max_turns``         MAX_TURNS
"usage limit reached|<epoch>"        QUOTA           reset from the epoch
"rate limit"                         QUOTA
"invalid api key", "/login", oauth   AUTHENTICATION
"overloaded", "529"                  CAPACITY
unknown option / flag (stderr)       SDK_OUTDATED    the installed CLI is too old
binary not found (runner)            MISSING
timeout (runner)                     TRANSPORT       delivery unknown
anything else                        OTHER
===================================  ==============  =========================
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Final

from aia_core.domain.ai_contracts import (
    AdapterRequest,
    AdapterResponse,
    Delivery,
    FinishReason,
    ModelUsage,
    ProviderError,
    ProviderErrorKind,
    canonical_json,
)
from aia_core.domain.providers import Provider

from .transport import (
    CliResult,
    CliRunner,
    TransportFailure,
    plausible_instant,
    refuse_thinking,
    render_transcript,
    token_count,
)

__all__ = ["JSON_CONTRACT_PROMPT_VERSION", "SCRUBBED_ENV", "ClaudeCodeCliAdapter"]

#: Removed from the CLI's environment on every call. Each one can move the call
#: off the subscription or onto a credential nobody chose.
SCRUBBED_ENV: Final = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_PROFILE",
)

#: The appended JSON-contract instruction is a prompt, so it has an identity.
JSON_CONTRACT_PROMPT_VERSION: Final = "cli-json-contract-v1"

_USAGE_LIMIT: Final = re.compile(r"usage limit reached\|(\d{9,11})", re.IGNORECASE)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _json_contract(schema: Mapping[str, Any]) -> str:
    return (
        "\n\nRespond with exactly one JSON object that satisfies this JSON Schema, "
        "and nothing else:\n" + canonical_json(schema)
    )


class ClaudeCodeCliAdapter:
    """:class:`~aia_core.domain.ai_contracts.ProviderAdapter` for the subscription CLI."""

    def __init__(
        self,
        *,
        runner: CliRunner,
        executable: str = "claude",
        max_turns: int = 1,
        timeout_s: float = 900.0,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self._runner = runner
        self._executable = executable
        self._max_turns = max_turns
        self._timeout_s = timeout_s
        self._clock = clock

    @property
    def provider(self) -> Provider:
        return Provider.CLAUDE_CODE

    def build_invocation(self, request: AdapterRequest) -> tuple[list[str], str]:
        """The argv and stdin for one call."""
        system = request.system
        if request.output_schema is not None:
            system += _json_contract(request.output_schema)
        argv = [
            self._executable,
            "-p",
            "--output-format",
            "json",
            "--model",
            request.model,
            "--max-turns",
            str(self._max_turns),
            "--system-prompt",
            system,
        ]
        return argv, render_transcript(request.messages)

    async def send(self, request: AdapterRequest) -> AdapterResponse:
        if request.thinking_budget_tokens is not None:
            raise refuse_thinking("Claude Code CLI")
        argv, stdin = self.build_invocation(request)
        try:
            result = await self._runner.run(
                argv, stdin=stdin, timeout_s=self._timeout_s, unset_env=SCRUBBED_ENV
            )
        except TransportFailure as exc:
            raise ProviderError(str(exc), kind=exc.kind, delivery=exc.delivery) from exc
        return self._parse(result)

    def _parse(self, result: CliResult) -> AdapterResponse:
        try:
            payload: Any = json.loads(result.stdout) if result.stdout.strip() else None
        except ValueError:
            payload = None

        if not isinstance(payload, Mapping):
            raise self._process_error(result)

        session_id = str(payload["session_id"]) if payload.get("session_id") else None
        subtype = str(payload.get("subtype") or "")
        text = payload.get("result") if isinstance(payload.get("result"), str) else ""
        assert isinstance(text, str)

        if subtype == "error_max_turns":
            raise ProviderError(
                "the CLI stopped at its turn limit",
                kind=ProviderErrorKind.MAX_TURNS,
                delivery=Delivery.RESPONDED,
                provider_request_id=session_id,
                provider_error_type=subtype,
            )
        if payload.get("is_error") is True or (subtype and subtype != "success"):
            raise self._result_error(text, session_id, subtype)

        usage = payload.get("usage") if isinstance(payload.get("usage"), Mapping) else {}
        assert isinstance(usage, Mapping)
        reported = payload.get("total_cost_usd")
        return AdapterResponse(
            text=text,
            finish_reason=FinishReason.COMPLETED,
            usage=ModelUsage(
                input_tokens=token_count(usage.get("input_tokens")),
                output_tokens=token_count(usage.get("output_tokens")),
                cache_read_input_tokens=token_count(usage.get("cache_read_input_tokens")),
                cache_write_input_tokens=token_count(usage.get("cache_creation_input_tokens")),
            ),
            provider_request_id=session_id,
            # Notional: what the same work would have cost on the API. Kept for
            # provenance only; the subscription's marginal cost is zero.
            reported_cost_usd=float(reported)
            if isinstance(reported, int | float) and not isinstance(reported, bool)
            else None,
        )

    def _result_error(self, text: str, session_id: str | None, subtype: str) -> ProviderError:
        lowered = text.lower()
        retry_after: datetime | None = None
        limit = _USAGE_LIMIT.search(text)
        if limit:
            kind = ProviderErrorKind.QUOTA
            retry_after = plausible_instant(
                self._clock(), datetime.fromtimestamp(int(limit.group(1)), tz=UTC)
            )
        elif "rate limit" in lowered or "usage limit" in lowered:
            kind = ProviderErrorKind.QUOTA
        elif "invalid api key" in lowered or "/login" in lowered or "oauth" in lowered:
            kind = ProviderErrorKind.AUTHENTICATION
        elif "overloaded" in lowered or "529" in lowered:
            kind = ProviderErrorKind.CAPACITY
        else:
            kind = ProviderErrorKind.OTHER
        return ProviderError(
            text or "the CLI reported an error",
            kind=kind,
            delivery=Delivery.RESPONDED,
            provider_request_id=session_id,
            retry_after=retry_after,
            provider_error_type=subtype,
        )

    @staticmethod
    def _process_error(result: CliResult) -> ProviderError:
        stderr = result.stderr.lower()
        if "unknown option" in stderr or "unknown argument" in stderr or "unrecognized" in stderr:
            kind = ProviderErrorKind.SDK_OUTDATED
        elif "invalid api key" in stderr or "/login" in stderr:
            kind = ProviderErrorKind.AUTHENTICATION
        else:
            kind = ProviderErrorKind.OTHER
        return ProviderError(
            f"the CLI exited {result.exit_code} without a result object",
            kind=kind,
            delivery=Delivery.RESPONDED,
        )
