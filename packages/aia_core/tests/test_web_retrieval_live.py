"""Live public retrieval is bounded to Czech Wikipedia and the checked address."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.web import FetchRefused
from aia_core.infrastructure.web_retrieval import FetchedResponse, ToolCallFailed
from aia_core.infrastructure.web_retrieval_live import PinnedHttpsTransport, WikipediaSearch


@dataclass
class Resolver:
    addresses: tuple[str, ...] = ("93.184.215.14",)

    def resolve(self, host: str) -> tuple[str, ...]:
        assert host == "cs.wikipedia.org"
        return self.addresses


@dataclass
class Transport:
    response: FetchedResponse
    calls: list[tuple[str, str, int]] = field(default_factory=list)
    retrieval_mode: RetrievalMode = RetrievalMode.LIVE

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        self.calls.append((url, address, max_bytes))
        return self.response


def _response(payload: Any, *, status: int = 200) -> FetchedResponse:
    return FetchedResponse(
        status=status,
        headers={"content-type": "application/json; charset=utf-8"},
        body=json.dumps(payload).encode(),
        truncated=False,
        provider_request_id=None,
    )


def test_wikipedia_search_uses_one_checked_ip_and_public_article_namespace() -> None:
    transport = Transport(
        _response({"query": {"search": [{"title": "Praha", "snippet": "<b>Hlavní</b> město"}]}})
    )
    search = WikipediaSearch(resolver=Resolver(), transport=transport)
    answer = search.search("Praha", max_results=2)
    assert answer.credits == 0 and len(answer.hits) == 1
    assert answer.hits[0].url == "https://cs.wikipedia.org/wiki/Praha"
    assert answer.hits[0].snippet == "Hlavní město"
    url, address, cap = transport.calls[0]
    assert address == "93.184.215.14" and cap == 128_000
    assert "srnamespace=0" in url and "srlimit=2" in url


def test_search_refuses_mixed_resolution_and_oversized_query_before_egress() -> None:
    transport = Transport(_response({"query": {"search": []}}))
    with pytest.raises(FetchRefused):
        WikipediaSearch(
            resolver=Resolver(("93.184.215.14", "10.0.0.5")), transport=transport
        ).search("Praha", max_results=1)
    with pytest.raises(ToolCallFailed) as refused:
        WikipediaSearch(resolver=Resolver(), transport=transport).search("x" * 513, max_results=1)
    assert refused.value.delivery is Delivery.NOT_SENT
    assert transport.calls == []


def test_search_refuses_unusable_provider_response() -> None:
    for response in (
        _response({"error": {"code": "maxlag"}}),
        _response({"query": {"search": "invalid"}}),
        _response({}, status=503),
    ):
        with pytest.raises(ToolCallFailed):
            WikipediaSearch(resolver=Resolver(), transport=Transport(response)).search(
                "Praha", max_results=1
            )


def test_pinned_transport_refuses_other_hosts_and_non_public_ip() -> None:
    transport = PinnedHttpsTransport()
    with pytest.raises(FetchRefused):
        transport.get("https://example.com/", address="93.184.215.14", max_bytes=1024)
    with pytest.raises(FetchRefused):
        transport.get("https://cs.wikipedia.org/wiki/Praha", address="127.0.0.1", max_bytes=1024)
