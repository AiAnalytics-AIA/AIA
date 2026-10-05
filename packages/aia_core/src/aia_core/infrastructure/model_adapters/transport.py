"""Transport protocols under the adapters, their recorded doubles, and shared parsing.

The protocols are the seam a live transport will implement. The recorded doubles
replay a captured exchange, so an adapter's request building and response
classification are tested end to end with no network. Parsing helpers here are
shared because the same plausibility rules (anti-pattern A7) apply to every
provider's headers.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final, Protocol

from aia_core.domain.ai_contracts import (
    Delivery,
    Message,
    ProviderError,
    ProviderErrorKind,
)

__all__ = [
    "CliResult",
    "CliRunner",
    "CredentialSource",
    "HttpRequest",
    "HttpResponse",
    "HttpTransport",
    "RecordedCliRunner",
    "RecordedTransport",
    "StaticCredentials",
    "TransportFailure",
    "parse_duration_seconds",
    "plausible_instant",
    "plausible_wait",
    "render_transcript",
    "resolve_secret",
    "token_count",
]

#: The longest wait a provider header may impose before it is treated as noise.
#: A header claiming "retry in 40 days" is far more likely to be a parse error
#: than an instruction, and a quota park on it would strand a study silently.
MAX_PLAUSIBLE_WAIT: Final = timedelta(days=7)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class HttpRequest:
    """One outbound HTTP request, fully built. Headers may contain a secret.

    ``raw_body`` is the exact bytes to send, when an adapter signed them: a
    signature is over bytes, and a transport that re-serialised ``body`` could send
    different ones (key order, spacing) and be refused. ``body`` stays the readable
    form, for recorded exchanges and tests.
    """

    method: str
    url: str
    headers: Mapping[str, str]
    body: Mapping[str, Any]
    raw_body: bytes | None = None

    def redacted_headers(self) -> dict[str, str]:
        """Headers safe to log: credentials replaced."""
        hidden = {"authorization", "x-api-key", "api-key", "x-amz-security-token"}
        return {k: ("<redacted>" if k.lower() in hidden else v) for k, v in self.headers.items()}


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """One HTTP response. Header names are lower-cased by the transport."""

    status: int
    headers: Mapping[str, str]
    body: Any

    def header(self, name: str) -> str | None:
        """Case-insensitive header lookup."""
        return self.headers.get(name.lower())


class TransportFailure(Exception):
    """The transport could not complete an exchange.

    ``delivery`` is the transport's statement about whether the request left:
    a refused connection is ``NOT_SENT``, a read timeout is ``UNKNOWN``. A
    transport that cannot tell must say ``UNKNOWN``.
    """

    def __init__(
        self,
        message: str,
        *,
        delivery: Delivery,
        kind: ProviderErrorKind = ProviderErrorKind.TRANSPORT,
    ) -> None:
        super().__init__(message)
        self.delivery = delivery
        self.kind = kind


class HttpTransport(Protocol):
    """Sends one request and returns the response. Never retries."""

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse: ...


@dataclass
class RecordedTransport:
    """Replays one recorded response (or failure) and keeps what was sent."""

    response: HttpResponse | None = None
    failure: TransportFailure | None = None
    requests: list[HttpRequest] = field(default_factory=list)

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        if self.response is None:
            raise AssertionError("recorded transport has nothing to replay")
        return self.response

    @classmethod
    def from_fixture(cls, fixture: Mapping[str, Any]) -> RecordedTransport:
        """Build from a fixture's ``response`` or ``transport_failure`` block."""
        if "transport_failure" in fixture:
            spec = fixture["transport_failure"]
            return cls(
                failure=TransportFailure(
                    spec.get("message", "recorded transport failure"),
                    delivery=Delivery(spec["delivery"]),
                    kind=ProviderErrorKind(spec.get("kind", "TRANSPORT")),
                )
            )
        spec = fixture["response"]
        return cls(
            response=HttpResponse(
                status=int(spec["status"]),
                headers={k.lower(): str(v) for k, v in spec.get("headers", {}).items()},
                body=spec.get("body"),
            )
        )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CliResult:
    """What a finished CLI process produced."""

    exit_code: int
    stdout: str
    stderr: str


class CliRunner(Protocol):
    """Runs one CLI invocation. Never retries.

    ``unset_env`` names variables that must be removed from the child's
    environment. For the subscription runtime this is not hygiene, it is the
    billing boundary: an ``ANTHROPIC_API_KEY`` in the environment makes the CLI
    bill the metered API instead of the subscription -- a silent provider switch.
    """

    async def run(
        self,
        argv: Sequence[str],
        *,
        stdin: str,
        timeout_s: float,
        unset_env: Sequence[str],
    ) -> CliResult: ...


@dataclass
class RecordedCliRunner:
    """Replays one recorded CLI result (or failure) and keeps the invocations."""

    result: CliResult | None = None
    failure: TransportFailure | None = None
    invocations: list[dict[str, Any]] = field(default_factory=list)

    async def run(
        self,
        argv: Sequence[str],
        *,
        stdin: str,
        timeout_s: float,
        unset_env: Sequence[str],
    ) -> CliResult:
        self.invocations.append(
            {
                "argv": list(argv),
                "stdin": stdin,
                "timeout_s": timeout_s,
                "unset_env": list(unset_env),
            }
        )
        if self.failure is not None:
            raise self.failure
        if self.result is None:
            raise AssertionError("recorded runner has nothing to replay")
        return self.result

    @classmethod
    def from_fixture(cls, fixture: Mapping[str, Any]) -> RecordedCliRunner:
        """Build from a fixture's ``cli`` or ``transport_failure`` block."""
        if "transport_failure" in fixture:
            spec = fixture["transport_failure"]
            return cls(
                failure=TransportFailure(
                    spec.get("message", "recorded runner failure"),
                    delivery=Delivery(spec["delivery"]),
                    kind=ProviderErrorKind(spec.get("kind", "TRANSPORT")),
                )
            )
        spec = fixture["cli"]
        return cls(
            result=CliResult(
                exit_code=int(spec["exit_code"]),
                stdout=str(spec.get("stdout", "")),
                stderr=str(spec.get("stderr", "")),
            )
        )


# --------------------------------------------------------------------------- #
# Credentials
# --------------------------------------------------------------------------- #


class CredentialSource(Protocol):
    """Resolves a credential reference to its secret. Raises ``KeyError`` if absent.

    The adapter holds a *reference*, never the secret, so configuration and logs
    can name which credential a route uses without containing it.
    """

    def secret(self, reference: str) -> str: ...


@dataclass(frozen=True, slots=True)
class StaticCredentials:
    """A fixed mapping of references to secrets. For tests and local runs.

    The secrets stay out of the repr, so an adapter holding this can be printed.
    """

    secrets: Mapping[str, str] = field(repr=False)

    def secret(self, reference: str) -> str:
        return self.secrets[reference]


def resolve_secret(credentials: CredentialSource, reference: str) -> str:
    """Return the secret, or raise a ``MISSING`` provider error. Nothing is sent."""
    try:
        value = credentials.secret(reference)
    except KeyError:
        value = ""
    if not value.strip():
        raise ProviderError(
            f"no credential configured for {reference!r}",
            kind=ProviderErrorKind.MISSING,
            delivery=Delivery.NOT_SENT,
        )
    return value


# --------------------------------------------------------------------------- #
# Shared parsing
# --------------------------------------------------------------------------- #


_DURATION_PART: Final = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def parse_duration_seconds(value: str | None) -> float | None:
    """Parse ``"30"``, ``"1.5"``, ``"20ms"``, ``"1s"`` or ``"6m0s"`` into seconds.

    Returns None for anything else. The whole string must be consumed: a parser
    that picks the first number it finds out of ``"soon, maybe 5s"`` produces a
    precise-looking answer from noise.
    """
    if value is None:
        return None
    text = value.strip().lower()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        pass
    else:
        # "inf", "nan" and "1e400" all parse as floats; none is a wait.
        return number if math.isfinite(number) else None
    total, position = 0.0, 0
    for match in _DURATION_PART.finditer(text):
        if match.start() != position:
            return None
        number, unit = float(match.group(1)), match.group(2)
        total += {"ms": number / 1000, "s": number, "m": number * 60, "h": number * 3600}[unit]
        position = match.end()
    return total if position == len(text) and position else None


def plausible_wait(now: datetime, seconds: float | None) -> datetime | None:
    """``now + seconds`` when that is a plausible wait, else None.

    A negative wait, or one longer than :data:`MAX_PLAUSIBLE_WAIT`
    is discarded rather than trusted. ``None`` then means "no reset known",
    which parks without a scheduled resume -- a person sees it -- rather than
    scheduling a resume from a number nobody should believe.
    """
    if seconds is None or seconds < 0:
        return None
    wait = timedelta(seconds=seconds)
    if wait > MAX_PLAUSIBLE_WAIT:
        return None
    return now + wait


def plausible_instant(now: datetime, instant: datetime | None) -> datetime | None:
    """An absolute reset instant, if it is in the plausible future window."""
    if instant is None:
        return None
    if instant < now - timedelta(minutes=5) or instant - now > MAX_PLAUSIBLE_WAIT:
        return None
    return max(instant, now)


def token_count(value: Any) -> int | None:
    """A provider-reported token count, or None when absent or implausible.

    A bool, a float, a string or a negative is not a count. ``None`` is kept
    distinct from zero all the way to the ledger: not reported is not "none used".
    """
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return int(value)
    return None


def render_transcript(messages: Sequence[Message]) -> str:
    """Render a conversation as one prompt, for transports that take one string."""
    if len(messages) == 1 and messages[0].role == "user":
        return messages[0].content
    return "\n\n".join(f"[{m.role}]\n{m.content}" for m in messages)
