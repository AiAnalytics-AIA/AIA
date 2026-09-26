"""Amazon Bedrock Runtime ``Converse`` adapter, bound to one route and one model (ADR 0010).

Request: ``POST https://bedrock-runtime.{region}.amazonaws.com/model/{modelId}/converse``,
SigV4-signed for service ``bedrock`` with the instance (or task) role -- there is no
static credential. ``modelId`` is the pinned EU inference profile id, percent-encoded
as one path segment (``:`` → ``%3A``), which is how botocore serialises it
(``bedrock-runtime`` service model, ``modelId`` is a non-greedy label).

**Route-bound.** The adapter is constructed with the one model id its route may carry
and refuses, before anything is signed or sent, a request naming any other: the IAM
grant names one profile, and an adapter that sent whatever it was asked would turn a
policy mistake into a 403 from AWS instead of a refusal here.

Structured output is a single forced tool (``toolChoice.tool``) whose ``inputSchema``
is the output contract -- the same approach as the Messages adapter -- so the answer
arrives as ``toolUse.input`` and still goes through AIA's deterministic validator.
Bedrock's newer ``outputConfig.textFormat`` is not used: its model support is
narrower, and the forced tool is the shape every Anthropic model on Bedrock accepts.

Classification, from the service model's error shapes (``x-amzn-errortype`` header,
else the body's ``__type`` / ``code``):

===================================  ======  ===============  ==========================
error                                status  kind             note
===================================  ======  ===============  ==========================
UnrecognizedClient / ExpiredToken    403     AUTHENTICATION   the role's credentials
AccessDeniedException                403     PERMISSION       IAM, or model access off
ResourceNotFoundException            404     MODEL            unknown profile id
ThrottlingException                  429     QUOTA            reset from ``retry-after``
ServiceQuotaExceededException        400     QUOTA            no reset
ModelNotReadyException               429     CAPACITY
ServiceUnavailableException          503     CAPACITY
ModelTimeoutException                408     TRANSPORT        provider answered
InternalServerException, other 5xx   5xx     TRANSPORT        provider answered
ValidationException, other 4xx       4xx     OTHER            permanent, never retried
ModelErrorException                  424     OTHER            permanent
===================================  ======  ===============  ==========================

A ``200`` whose body cannot be read is ``OTHER`` with delivery ``UNKNOWN``: Bedrock
processed something and may have billed it.

This adapter never retries, falls back or substitutes (ADR 0005 A).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Final, Protocol
from urllib.parse import quote

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
    HttpRequest,
    HttpResponse,
    HttpTransport,
    TransportFailure,
    parse_duration_seconds,
    plausible_wait,
    token_count,
)

__all__ = [
    "BEDROCK_SIGNING_SERVICE",
    "BedrockConverseAdapter",
    "BedrockSigner",
    "SigningUnavailable",
    "bedrock_runtime_host",
]

#: The SigV4 service name for Bedrock Runtime (service model ``signingName``).
BEDROCK_SIGNING_SERVICE: Final = "bedrock"

_STOP_REASONS: Final[dict[str, FinishReason]] = {
    "end_turn": FinishReason.COMPLETED,
    "stop_sequence": FinishReason.COMPLETED,
    "tool_use": FinishReason.COMPLETED,
    "max_tokens": FinishReason.TRUNCATED,
    "model_context_window_exceeded": FinishReason.TRUNCATED,
    "guardrail_intervened": FinishReason.REFUSED,
    "content_filtered": FinishReason.REFUSED,
}

_AUTHENTICATION_ERRORS: Final = frozenset(
    {
        "UnrecognizedClientException",
        "ExpiredTokenException",
        "InvalidSignatureException",
        "IncompleteSignatureException",
        "MissingAuthenticationTokenException",
    }
)


def bedrock_runtime_host(region: str) -> str:
    """``bedrock-runtime.{region}.amazonaws.com``: the endpoint rule set's standard host."""
    return f"bedrock-runtime.{region}.amazonaws.com"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SigningUnavailable(Exception):
    """No acceptable credential could sign the request. Nothing was sent."""


class BedrockSigner(Protocol):
    """Signs one request with SigV4. Returns the headers to send, auth included.

    Raises :class:`SigningUnavailable` when no acceptable credential exists -- for
    the live signer, when the credential is not an instance or container role.
    """

    def sign(
        self, *, method: str, url: str, headers: Mapping[str, str], body: bytes
    ) -> dict[str, str]: ...


def _error_type(response: HttpResponse) -> str:
    """The AWS error code: header first, then the body, cleaned as botocore does."""
    raw = response.header("x-amzn-errortype") or ""
    if not raw and isinstance(response.body, Mapping):
        raw = str(response.body.get("__type") or response.body.get("code") or "")
    return raw.split(":", 1)[0].rsplit("#", 1)[-1]


def _message(response: HttpResponse) -> str:
    body = response.body if isinstance(response.body, Mapping) else {}
    return str(body.get("message") or body.get("Message") or f"HTTP {response.status}")


class BedrockConverseAdapter:
    """:class:`~aia_core.domain.ai_contracts.ProviderAdapter` for one Bedrock route."""

    def __init__(
        self,
        *,
        transport: HttpTransport,
        signer: BedrockSigner,
        region: str,
        model_id: str,
        timeout_s: float = 300.0,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        if not region.strip() or not model_id.strip():
            raise ValueError("a Bedrock adapter is bound to a region and one model id")
        self._transport = transport
        self._signer = signer
        self._region = region
        self._model_id = model_id
        self._timeout_s = timeout_s
        self._clock = clock

    @property
    def provider(self) -> Provider:
        return Provider.AWS_BEDROCK

    @property
    def model_id(self) -> str:
        """The one model id this adapter's route carries."""
        return self._model_id

    # ------------------------------------------------------------ requests --

    def url(self) -> str:
        """The Converse URL for the bound model; the id is one encoded path segment."""
        return (
            f"https://{bedrock_runtime_host(self._region)}/model/"
            f"{quote(self._model_id, safe='-._~')}/converse"
        )

    def build_body(self, request: AdapterRequest) -> dict[str, Any]:
        """The Converse request body for one call."""
        inference: dict[str, Any] = {"maxTokens": request.max_output_tokens}
        if request.temperature is not None:
            inference["temperature"] = request.temperature
        body: dict[str, Any] = {
            "messages": [
                {"role": m.role, "content": [{"text": m.content}]} for m in request.messages
            ],
            "inferenceConfig": inference,
        }
        if request.system:
            body["system"] = [{"text": request.system}]
        if request.output_schema is not None:
            name = request.schema_name or "structured_output"
            body["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": name,
                            "description": "Return the answer as this object.",
                            "inputSchema": {"json": dict(request.output_schema)},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": name}},
            }
        return body

    def build_request(self, request: AdapterRequest) -> HttpRequest:
        """The exact, signed HTTP request for one call."""
        body = self.build_body(request)
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        url = self.url()
        headers = {"content-type": "application/json", "accept": "application/json"}
        signed = self._signer.sign(method="POST", url=url, headers=headers, body=raw)
        return HttpRequest(method="POST", url=url, headers=signed, body=body, raw_body=raw)

    async def send(self, request: AdapterRequest) -> AdapterResponse:
        if request.model != self._model_id:
            # A binding for another model reached this route's adapter: refuse it
            # here, unsigned and unsent, rather than let AWS answer 403.
            raise ProviderError(
                f"this Bedrock route carries {self._model_id}, not {request.model}",
                kind=ProviderErrorKind.MODEL,
                delivery=Delivery.NOT_SENT,
            )
        try:
            http_request = self.build_request(request)
        except SigningUnavailable as exc:
            raise ProviderError(
                str(exc), kind=ProviderErrorKind.AUTHENTICATION, delivery=Delivery.NOT_SENT
            ) from exc
        try:
            response = await self._transport.send(http_request, timeout_s=self._timeout_s)
        except TransportFailure as exc:
            raise ProviderError(str(exc), kind=exc.kind, delivery=exc.delivery) from exc

        if response.status != 200:
            raise self._classify(response)
        return self._parse(request, response)

    # ----------------------------------------------------------- responses --

    @staticmethod
    def _request_id(response: HttpResponse) -> str | None:
        return response.header("x-amzn-requestid") or response.header("x-amz-request-id")

    def _parse(self, request: AdapterRequest, response: HttpResponse) -> AdapterResponse:
        body = response.body
        request_id = self._request_id(response)
        output = body.get("output") if isinstance(body, Mapping) else None
        message = output.get("message") if isinstance(output, Mapping) else None
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(body, Mapping) or not isinstance(content, list):
            raise ProviderError(
                "unreadable 200 response from Bedrock Converse",
                kind=ProviderErrorKind.OTHER,
                delivery=Delivery.UNKNOWN,
                provider_request_id=request_id,
                http_status=response.status,
            )

        texts: list[str] = []
        structured: Mapping[str, Any] | None = None
        wanted_tool = request.schema_name or "structured_output"
        for block in content:
            if not isinstance(block, Mapping):
                continue
            if isinstance(block.get("text"), str):
                texts.append(block["text"])
            tool_use = block.get("toolUse")
            if (
                request.output_schema is not None
                and isinstance(tool_use, Mapping)
                and tool_use.get("name") == wanted_tool
                and isinstance(tool_use.get("input"), Mapping)
            ):
                structured = tool_use["input"]

        usage = body.get("usage") if isinstance(body.get("usage"), Mapping) else {}
        assert isinstance(usage, Mapping)
        return AdapterResponse(
            text="".join(texts),
            finish_reason=_STOP_REASONS.get(str(body.get("stopReason")), FinishReason.UNKNOWN),
            usage=ModelUsage(
                input_tokens=token_count(usage.get("inputTokens")),
                output_tokens=token_count(usage.get("outputTokens")),
                cache_read_input_tokens=token_count(usage.get("cacheReadInputTokens")),
                cache_write_input_tokens=token_count(usage.get("cacheWriteInputTokens")),
            ),
            provider_request_id=request_id,
            # Converse does not name the serving model; the profile is what ran.
            served_model=self._model_id,
            structured=structured,
        )

    def _classify(self, response: HttpResponse) -> ProviderError:
        error_type = _error_type(response)
        status = response.status
        retry_after: datetime | None = None

        if error_type in _AUTHENTICATION_ERRORS or status == 401:
            kind = ProviderErrorKind.AUTHENTICATION
        elif error_type == "AccessDeniedException" or status == 403:
            kind = ProviderErrorKind.PERMISSION
        elif error_type == "ResourceNotFoundException" or status == 404:
            kind = ProviderErrorKind.MODEL
        elif error_type == "ModelNotReadyException":
            kind = ProviderErrorKind.CAPACITY
        elif error_type == "ThrottlingException" or status == 429:
            kind = ProviderErrorKind.QUOTA
            retry_after = plausible_wait(
                self._clock(), parse_duration_seconds(response.header("retry-after"))
            )
        elif error_type == "ServiceQuotaExceededException":
            kind = ProviderErrorKind.QUOTA
        elif error_type == "ServiceUnavailableException" or status == 503:
            kind = ProviderErrorKind.CAPACITY
        elif error_type == "ModelErrorException" or status == 424:
            kind = ProviderErrorKind.OTHER
        elif error_type == "ModelTimeoutException" or status == 408 or status >= 500:
            kind = ProviderErrorKind.TRANSPORT
        else:
            kind = ProviderErrorKind.OTHER

        return ProviderError(
            _message(response),
            kind=kind,
            delivery=Delivery.RESPONDED,
            provider_request_id=self._request_id(response),
            retry_after=retry_after,
            http_status=status,
            provider_error_type=error_type,
        )
