"""Anthropic Messages API adapter (the metered "Claude API" provider).

Request shape: ``POST /v1/messages``. Structured output uses a single forced tool
whose ``input_schema`` is the output contract -- the same approach as the
reference router's "forced tool/schema" path -- so the answer arrives as a
provider-native object and still goes through AIA's deterministic validator.

Classification, from documented status codes and error types:

=====================  =========================  ================
status / error type    kind                       note
=====================  =========================  ================
401 authentication     AUTHENTICATION
403 permission         PERMISSION
404 not_found          MODEL                      unknown model id
429 rate_limit         QUOTA                      reset from headers
400 "credit balance"   QUOTA                      the WAITING_CREDITS case; no reset
402 billing            QUOTA                      no reset
529 overloaded         CAPACITY
500 api_error, 502-504 TRANSPORT                  provider answered; not billed
other 4xx              OTHER                      permanent, never retried
=====================  =========================  ================

A ``200`` whose body cannot be read is classified ``OTHER`` with delivery
``UNKNOWN``: the provider processed *something* and may have billed it, so the
call is carried as uncertain rather than as a free failure.
"""

from __future__ import annotations

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
)
from aia_core.domain.providers import Provider

from .transport import (
    CredentialSource,
    HttpRequest,
    HttpResponse,
    HttpTransport,
    TransportFailure,
    parse_duration_seconds,
    plausible_instant,
    plausible_wait,
    resolve_secret,
    token_count,
)

__all__ = ["ANTHROPIC_API_VERSION", "AnthropicMessagesAdapter"]

#: The Messages API version header this adapter was written against.
ANTHROPIC_API_VERSION: Final = "2023-06-01"

_STOP_REASONS: Final[dict[str, FinishReason]] = {
    "end_turn": FinishReason.COMPLETED,
    "stop_sequence": FinishReason.COMPLETED,
    "tool_use": FinishReason.COMPLETED,
    "max_tokens": FinishReason.TRUNCATED,
    "refusal": FinishReason.REFUSED,
}

_RESET_HEADERS: Final = (
    "anthropic-ratelimit-requests-reset",
    "anthropic-ratelimit-tokens-reset",
    "anthropic-ratelimit-input-tokens-reset",
    "anthropic-ratelimit-output-tokens-reset",
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AnthropicMessagesAdapter:
    """:class:`~aia_core.domain.ai_contracts.ProviderAdapter` for the Messages API."""

    def __init__(
        self,
        *,
        transport: HttpTransport,
        credentials: CredentialSource,
        credential_ref: str,
        base_url: str,
        timeout_s: float = 600.0,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._transport = transport
        self._credentials = credentials
        self._credential_ref = credential_ref
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._clock = clock

    @property
    def provider(self) -> Provider:
        return Provider.ANTHROPIC

    def build_request(self, request: AdapterRequest, *, secret: str) -> HttpRequest:
        """The exact HTTP request for one call."""
        body: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_output_tokens,
            "system": request.system,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.output_schema is not None:
            name = request.schema_name or "structured_output"
            body["tools"] = [
                {
                    "name": name,
                    "description": "Return the answer as this object.",
                    "input_schema": dict(request.output_schema),
                }
            ]
            body["tool_choice"] = {"type": "tool", "name": name}
        return HttpRequest(
            method="POST",
            url=f"{self._base_url}/v1/messages",
            headers={
                "x-api-key": secret,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
            },
            body=body,
        )

    async def send(self, request: AdapterRequest) -> AdapterResponse:
        secret = resolve_secret(self._credentials, self._credential_ref)
        http_request = self.build_request(request, secret=secret)
        try:
            response = await self._transport.send(http_request, timeout_s=self._timeout_s)
        except TransportFailure as exc:
            raise ProviderError(str(exc), kind=exc.kind, delivery=exc.delivery) from exc

        if response.status != 200:
            raise self._classify(response)
        return self._parse(request, response)

    # ----------------------------------------------------------- responses --

    def _request_id(self, response: HttpResponse) -> str | None:
        header = response.header("request-id")
        if header:
            return header
        body = response.body if isinstance(response.body, Mapping) else {}
        value = body.get("request_id") or body.get("id")
        return str(value) if value else None

    def _parse(self, request: AdapterRequest, response: HttpResponse) -> AdapterResponse:
        body = response.body
        request_id = self._request_id(response)
        if not isinstance(body, Mapping) or not isinstance(body.get("content"), list):
            raise ProviderError(
                "unreadable 200 response from the Messages API",
                kind=ProviderErrorKind.OTHER,
                delivery=Delivery.UNKNOWN,
                provider_request_id=request_id,
                http_status=response.status,
            )

        texts: list[str] = []
        structured: Mapping[str, Any] | None = None
        wanted_tool = request.schema_name or "structured_output"
        for block in body["content"]:
            if not isinstance(block, Mapping):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                texts.append(block["text"])
            elif (
                request.output_schema is not None
                and block.get("type") == "tool_use"
                and block.get("name") == wanted_tool
                and isinstance(block.get("input"), Mapping)
            ):
                structured = block["input"]

        usage = body.get("usage") if isinstance(body.get("usage"), Mapping) else {}
        assert isinstance(usage, Mapping)
        return AdapterResponse(
            text="".join(texts),
            finish_reason=_STOP_REASONS.get(str(body.get("stop_reason")), FinishReason.UNKNOWN),
            usage=ModelUsage(
                input_tokens=token_count(usage.get("input_tokens")),
                output_tokens=token_count(usage.get("output_tokens")),
                cache_read_input_tokens=token_count(usage.get("cache_read_input_tokens")),
                cache_write_input_tokens=token_count(usage.get("cache_creation_input_tokens")),
            ),
            provider_request_id=request_id,
            served_model=str(body.get("model") or ""),
            structured=structured,
        )

    def _retry_after(self, response: HttpResponse) -> datetime | None:
        now = self._clock()
        waited = plausible_wait(now, parse_duration_seconds(response.header("retry-after")))
        if waited is not None:
            return waited
        instants: list[datetime] = []
        for name in _RESET_HEADERS:
            raw = response.header(name)
            if not raw:
                continue
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None:
                continue
            instant = plausible_instant(now, parsed)
            if instant is not None:
                instants.append(instant)
        # The latest reset is the one after which every limit has cleared.
        return max(instants) if instants else None

    def _classify(self, response: HttpResponse) -> ProviderError:
        body = response.body if isinstance(response.body, Mapping) else {}
        error = body.get("error") if isinstance(body.get("error"), Mapping) else {}
        assert isinstance(error, Mapping)
        error_type = str(error.get("type") or "")
        message = str(error.get("message") or f"HTTP {response.status}")
        status = response.status
        retry_after: datetime | None = None

        if status == 401 or error_type == "authentication_error":
            kind = ProviderErrorKind.AUTHENTICATION
        elif status == 403 or error_type == "permission_error":
            kind = ProviderErrorKind.PERMISSION
        elif status == 404 or error_type == "not_found_error":
            kind = ProviderErrorKind.MODEL
        elif status == 429 or error_type == "rate_limit_error":
            kind = ProviderErrorKind.QUOTA
            retry_after = self._retry_after(response)
        elif status == 402 or error_type == "billing_error" or "credit balance" in message.lower():
            # Out of credits: the reference's WAITING_CREDITS. There is no reset
            # instant -- somebody has to add credit -- so none is invented.
            kind = ProviderErrorKind.QUOTA
        elif status == 529 or error_type == "overloaded_error":
            kind = ProviderErrorKind.CAPACITY
        elif status >= 500:
            kind = ProviderErrorKind.TRANSPORT
        else:
            kind = ProviderErrorKind.OTHER

        return ProviderError(
            message,
            kind=kind,
            delivery=Delivery.RESPONDED,
            provider_request_id=self._request_id(response),
            retry_after=retry_after,
            http_status=status,
            provider_error_type=error_type,
        )
