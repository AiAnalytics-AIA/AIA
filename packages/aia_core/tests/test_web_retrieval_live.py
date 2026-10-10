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
    expected_host: str = "cs.wikipedia.org"

    def resolve(self, host: str) -> tuple[str, ...]:
        assert host == self.expected_host
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


def test_english_search_uses_the_english_index_and_its_pinned_transport() -> None:
    cs = Transport(_response({"query": {"search": []}}))
    en = Transport(_response({"query": {"search": [{"title": "Library", "snippet": "Services"}]}}))
    search = WikipediaSearch(
        resolver=Resolver(expected_host="en.wikipedia.org"), transport=cs, english_transport=en
    )
    response = search.search_in("Library", lang="en", max_results=2)
    assert response.hits[0].url == "https://en.wikipedia.org/wiki/Library"
    assert len(en.calls) == 1 and en.calls[0][0].startswith("https://en.wikipedia.org/w/api.php?")
    assert cs.calls == []


def test_an_unconfigured_language_never_silently_searches_another_index() -> None:
    transport = Transport(_response({"query": {"search": []}}))
    search = WikipediaSearch(resolver=Resolver(), transport=transport)
    for language in ("en", "fr", "en.wikipedia.org.evil.test"):
        with pytest.raises(ToolCallFailed) as error:
            search.search_in("Library", lang=language, max_results=2)
        assert error.value.reason == "search_language"
        assert error.value.delivery is Delivery.NOT_SENT
    assert not transport.calls


def test_search_refuses_mixed_resolution_and_oversized_query_before_egress() -> None:
    transport = Transport(_response({"query": {"search": []}}))
    for addresses, reason in (
        (("93.184.215.14", "10.0.0.5"), "address_not_public"),
        ((), "address_unresolved"),
    ):
        with pytest.raises(ToolCallFailed) as unsent:
            WikipediaSearch(resolver=Resolver(addresses), transport=transport).search(
                "Praha", max_results=1
            )
        assert unsent.value.delivery is Delivery.NOT_SENT and unsent.value.reason == reason
    with pytest.raises(ToolCallFailed) as refused:
        WikipediaSearch(resolver=Resolver(), transport=transport).search("x" * 513, max_results=1)
    assert refused.value.delivery is Delivery.NOT_SENT
    assert transport.calls == []


@dataclass
class RefusingTransport:
    retrieval_mode: RetrievalMode = RetrievalMode.LIVE

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        raise FetchRefused("refused before connecting", reason="https_only")


def test_a_transport_refusal_is_a_failure_that_sent_nothing() -> None:
    with pytest.raises(ToolCallFailed) as unsent:
        WikipediaSearch(resolver=Resolver(), transport=RefusingTransport()).search(
            "Praha", max_results=1
        )
    assert unsent.value.delivery is Delivery.NOT_SENT and unsent.value.reason == "https_only"


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
