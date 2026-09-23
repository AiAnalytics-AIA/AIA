"""OpenAI Chat Completions adapter.

Request shape: ``POST /v1/chat/completions``. Structured output uses
``response_format: json_schema``, with ``strict: true`` only when the gateway
says the contract is strict-compatible *unchanged* -- otherwise the schema is
sent non-strict rather than rewritten, and AIA's validator is the gate either
way. AIA's ``call_id`` is sent as ``X-Client-Request-Id`` so an uncertain call
can be looked up provider-side by an id AIA recorded before sending.

Classification, from documented status codes and error codes:

=========================  ==============  =====================================
status / error code        kind            note
=========================  ==============  =====================================
401                        AUTHENTICATION
403                        PERMISSION      includes unsupported region
404 model_not_found        MODEL
429 insufficient_quota     QUOTA           out of credits; no reset is invented
429 rate limit             QUOTA           reset from headers
400 on ``response_format`` SCHEMA          the provider refused the contract
503                        CAPACITY
500, 502, 504              TRANSPORT       provider answered; not billed
other                      OTHER           permanent, never retried
=========================  ==============  =====================================
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
    strictify,
)
from aia_core.domain.providers import Provider

from .transport import (
    CredentialSource,
    HttpRequest,
    HttpResponse,
    HttpTransport,
    TransportFailure,
    parse_duration_seconds,
    plausible_wait,
    resolve_secret,
    token_count,
)

__all__ = ["OpenAIChatAdapter"]

_FINISH_REASONS: Final[dict[str, FinishReason]] = {
    "stop": FinishReason.COMPLETED,
    "length": FinishReason.TRUNCATED,
    "content_filter": FinishReason.REFUSED,
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


class OpenAIChatAdapter:
    """:class:`~aia_core.domain.ai_contracts.ProviderAdapter` for Chat Completions."""

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
        return Provider.OPENAI

    def build_request(self, request: AdapterRequest, *, secret: str) -> HttpRequest:
        """The exact HTTP request for one call."""
        body: dict[str, Any] = {
            "model": request.model,
            "max_completion_tokens": request.max_output_tokens,
            "messages": [
                {"role": "system", "content": request.system},
                *({"role": m.role, "content": m.content} for m in request.messages),
            ],
        }
        if request.output_schema is not None:
            schema = (
                strictify(request.output_schema)
                if request.strict_schema
                else dict(request.output_schema)
            )
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name or "structured_output",
                    "schema": schema,
                    "strict": request.strict_schema,
                },
            }
        return HttpRequest(
            method="POST",
            url=f"{self._base_url}/v1/chat/completions",
            headers={
                "authorization": f"Bearer {secret}",
                "content-type": "application/json",
                "x-client-request-id": request.call_id,
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
        return self._parse(response)

    # ----------------------------------------------------------- responses --

    def _parse(self, response: HttpResponse) -> AdapterResponse:
        body = response.body
        request_id = response.header("x-request-id")
        choices = body.get("choices") if isinstance(body, Mapping) else None
        first = choices[0] if isinstance(choices, list) and choices else None
        message = first.get("message") if isinstance(first, Mapping) else None
        if not isinstance(body, Mapping) or not isinstance(message, Mapping):
            raise ProviderError(
                "unreadable 200 response from Chat Completions",
                kind=ProviderErrorKind.OTHER,
                delivery=Delivery.UNKNOWN,
                provider_request_id=request_id,
                http_status=response.status,
            )
        assert isinstance(first, Mapping)

        finish = _FINISH_REASONS.get(str(first.get("finish_reason")), FinishReason.UNKNOWN)
        if message.get("refusal"):
            finish = FinishReason.REFUSED
        content = message.get("content")

        usage = body.get("usage") if isinstance(body.get("usage"), Mapping) else {}
        assert isinstance(usage, Mapping)
        details = usage.get("prompt_tokens_details")
        cached = token_count(details.get("cached_tokens")) if isinstance(details, Mapping) else None
        prompt = token_count(usage.get("prompt_tokens"))
        # prompt_tokens *includes* the cached tokens; AIA prices the uncached
        # remainder at the input rate and the cached part at the cache rate.
        uncached = prompt - cached if prompt is not None and cached is not None else prompt
        return AdapterResponse(
            text=content if isinstance(content, str) else "",
            finish_reason=finish,
            usage=ModelUsage(
                input_tokens=uncached,
                output_tokens=token_count(usage.get("completion_tokens")),
                cache_read_input_tokens=cached,
                cache_write_input_tokens=None,
            ),
            provider_request_id=request_id or (str(body["id"]) if body.get("id") else None),
            served_model=str(body.get("model") or ""),
        )

    def _retry_after(self, response: HttpResponse) -> datetime | None:
        now = self._clock()
        for name in ("retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
            waited = plausible_wait(now, parse_duration_seconds(response.header(name)))
            if waited is not None:
                return waited
        return None

    def _classify(self, response: HttpResponse) -> ProviderError:
        body = response.body if isinstance(response.body, Mapping) else {}
        error = body.get("error") if isinstance(body.get("error"), Mapping) else {}
        assert isinstance(error, Mapping)
        code = str(error.get("code") or "")
        error_type = str(error.get("type") or "")
        param = str(error.get("param") or "")
        message = str(error.get("message") or f"HTTP {response.status}")
        status = response.status
        retry_after: datetime | None = None

        if status == 401:
            kind = ProviderErrorKind.AUTHENTICATION
        elif status == 403:
            kind = ProviderErrorKind.PERMISSION
        elif status == 404 and (code == "model_not_found" or "model" in message.lower()):
            kind = ProviderErrorKind.MODEL
        elif status == 429 and (code == "insufficient_quota" or error_type == "insufficient_quota"):
            kind = ProviderErrorKind.QUOTA
        elif status == 429:
            kind = ProviderErrorKind.QUOTA
            retry_after = self._retry_after(response)
        elif status == 400 and param.startswith("response_format"):
            kind = ProviderErrorKind.SCHEMA
        elif status == 503:
            kind = ProviderErrorKind.CAPACITY
        elif status >= 500:
            kind = ProviderErrorKind.TRANSPORT
        else:
            kind = ProviderErrorKind.OTHER

        return ProviderError(
            message,
            kind=kind,
            delivery=Delivery.RESPONDED,
            provider_request_id=response.header("x-request-id"),
            retry_after=retry_after,
            http_status=status,
            provider_error_type=code or error_type,
        )
