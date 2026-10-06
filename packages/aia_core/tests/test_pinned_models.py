"""One route, several pinned models: each request goes through its own model's adapter.

``PinnedModels`` lets ADR 0010's route carry the light triage model beside the
research model without either single-model Bedrock adapter learning to send the
other's id. A model the route does not hold is refused unsigned and unsent.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from aia_core.domain.ai_contracts import (
    AdapterRequest,
    Delivery,
    Message,
    ProviderError,
    ProviderErrorKind,
)
from aia_core.domain.providers import Provider
from aia_core.infrastructure.model_adapters import BedrockConverseAdapter, PinnedModels
from aia_core.infrastructure.model_adapters.transport import HttpRequest, HttpResponse

MAIN = "eu.example.main-test-v1:0"
LIGHT = "eu.example.light-test-v1:0"


class Signer:
    def __init__(self) -> None:
        self.signed: list[str] = []

    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        self.signed.append(url)
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


class Transport:
    def __init__(self) -> None:
        self.urls: list[str] = []

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        self.urls.append(request.url)
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": "req-1"},
            body={
                "output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}},
                "stopReason": "end_turn",
                "usage": {"inputTokens": 1, "outputTokens": 1},
            },
        )


def _adapter(model: str, transport: Transport, signer: Signer) -> BedrockConverseAdapter:
    return BedrockConverseAdapter(
        transport=transport, signer=signer, region="eu-central-1", model_id=model
    )


def _request(model: str) -> AdapterRequest:
    return AdapterRequest(
        call_id="c",
        provider=Provider.AWS_BEDROCK,
        model=model,
        system="s",
        messages=(Message(role="user", content="m"),),
        max_output_tokens=16,
    )


def test_each_model_goes_through_its_own_pinned_adapter() -> None:
    transport, signer = Transport(), Signer()
    route = PinnedModels([_adapter(MAIN, transport, signer), _adapter(LIGHT, transport, signer)])
    assert route.provider is Provider.AWS_BEDROCK
    assert route.model_ids == frozenset({MAIN, LIGHT})

    asyncio.run(route.send(_request(LIGHT)))
    asyncio.run(route.send(_request(MAIN)))
    assert [u.split("/model/")[1].split("/")[0] for u in transport.urls] == [
        "eu.example.light-test-v1%3A0",
        "eu.example.main-test-v1%3A0",
    ]


def test_a_model_the_route_does_not_hold_is_refused_unsigned_and_unsent() -> None:
    transport, signer = Transport(), Signer()
    route = PinnedModels([_adapter(MAIN, transport, signer), _adapter(LIGHT, transport, signer)])
    with pytest.raises(ProviderError) as refused:
        asyncio.run(route.send(_request("eu.example.other-v1:0")))
    assert refused.value.kind is ProviderErrorKind.MODEL
    assert refused.value.delivery is Delivery.NOT_SENT
    assert transport.urls == [] and signer.signed == []


def test_a_route_holds_each_model_once_from_one_provider() -> None:
    transport, signer = Transport(), Signer()
    with pytest.raises(ValueError):
        PinnedModels([_adapter(MAIN, transport, signer), _adapter(MAIN, transport, signer)])
    with pytest.raises(ValueError):
        PinnedModels([])

    class Other:
        provider = Provider.ANTHROPIC
        model_id = LIGHT

        async def send(self, request: AdapterRequest) -> Any:  # pragma: no cover
            raise AssertionError

    with pytest.raises(ValueError):
        PinnedModels([_adapter(MAIN, transport, signer), Other()])
