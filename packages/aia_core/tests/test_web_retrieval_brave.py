"""Brave Web Search: one checked request, mapped hits, named failures, a key that never leaks.

Nothing here touches the network. The adapter runs over a fake transport and
resolver; the real transport runs over a fake urllib3 connection pool.

``DOCUMENTED_SHAPE`` is the *documented* response shape of Brave's
``/res/v1/web/search`` (``{"type": "search", "query": {...}, "web": {"type":
"search", "results": [{"title", "url", "description", ...}]}}``) filled with
fictional content. It is not a live capture: no request has been sent to Brave
(plan chunk 3; a recorded live exchange is chunk 25's).
"""

from __future__ import annotations

import gzip
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.web import FetchRefused
from aia_core.infrastructure.model_adapters.transport import StaticCredentials
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    LanguageSearch,
    SearchAdapter,
    ToolCallFailed,
)
from aia_core.infrastructure.web_retrieval_brave import (
    BRAVE_API_HOST,
    BRAVE_SEARCH_ID,
    MAX_RESPONSE_BYTES,
    BraveHttpsTransport,
    BraveQuery,
    BraveSearch,
    check_freshness,
)

KEY = "BSAfictional-subscription-key-0123456789"
REF = "brave-test-key"
ADDRESS = "93.184.215.14"

DOCUMENTED_SHAPE: dict[str, Any] = {
    "type": "search",
    "query": {"original": "spotřeba kávy domácnosti", "country": "cz"},
    "web": {
        "type": "search",
        "results": [
            {
                "title": "Spotřeba <strong>kávy</strong> v domácnostech &amp; trh",
                "url": "https://statistika.example.cz/kava/2025",
                "description": "Fiktivní <strong>přehled</strong> spotřeby, rok 2025.",
                "is_source_local": False,
                "language": "cs",
                "profile": {"name": "Statistika (fiktivní)"},
            },
            {
                "title": "Interní stránka",
                "url": "http://intranet.local/kava",
                "description": "Neveřejná adresa: nesmí projít.",
            },
            {
                "title": "Ročenka trhu s kávou",
                "url": "https://rocenka.example.org/trh-kava",
                "description": "Fiktivní ročenka.",
            },
            {"title": "Bez adresy", "description": "Výsledek bez URL."},
            {
                "title": "Soubor",
                "url": "ftp://soubory.example.cz/kava.csv",
                "description": "Nepodporované schéma.",
            },
        ],
    },
}


@dataclass
class Resolver:
    addresses: tuple[str, ...] = (ADDRESS,)
    hosts: list[str] = field(default_factory=list)

    def resolve(self, host: str) -> tuple[str, ...]:
        self.hosts.append(host)
        return self.addresses


@dataclass
class Transport:
    response: FetchedResponse | None = None
    failure: Exception | None = None
    #: What the adapter handed over, the key included: kept out of the repr.
    calls: list[dict[str, Any]] = field(default_factory=list, repr=False)
    retrieval_mode: RetrievalMode = RetrievalMode.LIVE

    def get(
        self, url: str, *, address: str, max_bytes: int, headers: Mapping[str, str]
    ) -> FetchedResponse:
        self.calls.append(
            {"url": url, "address": address, "max_bytes": max_bytes, "headers": dict(headers)}
        )
        if self.failure is not None:
            raise self.failure
        assert self.response is not None
        return self.response


def _json(
    payload: Any,
    *,
    status: int = 200,
    content_type: str = "application/json; charset=utf-8",
    request_id: str | None = None,
) -> FetchedResponse:
    return FetchedResponse(
        status=status,
        headers={"content-type": content_type},
        body=json.dumps(payload).encode(),
        truncated=False,
        provider_request_id=request_id,
    )


def _search(
    transport: Transport,
    *,
    resolver: Resolver | None = None,
    secrets: Mapping[str, str] | None = None,
    **kwargs: Any,
) -> BraveSearch:
    return BraveSearch(
        credentials=StaticCredentials({REF: KEY} if secrets is None else secrets),
        credential_ref=REF,
        resolver=resolver or Resolver(),
        transport=transport,
        **kwargs,
    )


def _params(call: dict[str, Any]) -> dict[str, str]:
    parsed = parse_qs(urlsplit(call["url"]).query, keep_blank_values=True)
    assert all(len(v) == 1 for v in parsed.values())
    return {k: v[0] for k, v in parsed.items()}


# ----------------------------------------------------------------- identity --


def test_brave_is_a_live_search_adapter_with_its_own_id() -> None:
    adapter: SearchAdapter = _search(Transport(_json(DOCUMENTED_SHAPE)))
    assert adapter.adapter_id == BRAVE_SEARCH_ID == "brave-web-search-1"
    assert adapter.retrieval_mode is RetrievalMode.LIVE


def test_a_recorded_transport_is_refused() -> None:
    with pytest.raises(ValueError, match="live transport"):
        _search(Transport(retrieval_mode=RetrievalMode.RECORDED))


# ------------------------------------------------------------------ request --


def test_one_get_to_the_checked_address_with_the_documented_parameters() -> None:
    transport = Transport(_json(DOCUMENTED_SHAPE))
    resolver = Resolver()
    _search(transport, resolver=resolver).search("  spotřeba   kávy ", max_results=5)
    assert resolver.hosts == [BRAVE_API_HOST]
    (call,) = transport.calls
    parts = urlsplit(call["url"])
    assert (parts.scheme, parts.hostname, parts.path) == (
        "https",
        "api.search.brave.com",
        "/res/v1/web/search",
    )
    assert call["address"] == ADDRESS and call["max_bytes"] == MAX_RESPONSE_BYTES
    assert call["headers"] == {"Accept": "application/json", "X-Subscription-Token": KEY}
    assert _params(call) == {
        "q": "spotřeba kávy",
        "country": "CZ",
        "search_lang": "cs",
        "count": "5",
        "safesearch": "strict",
        "result_filter": "web",
    }


@pytest.mark.parametrize(("asked", "sent"), [(1, "1"), (20, "20"), (21, "20"), (500, "20")])
def test_count_never_exceeds_twenty_or_the_callers_limit(asked: int, sent: str) -> None:
    transport = Transport(_json({"web": {"results": []}}))
    _search(transport).search("káva", max_results=asked)
    assert _params(transport.calls[0])["count"] == sent


def test_the_adapter_language_and_freshness_apply_to_plain_queries() -> None:
    transport = Transport(_json({"web": {"results": []}}))
    _search(transport, lang="en", freshness="pm").search("coffee", max_results=3)
    params = _params(transport.calls[0])
    assert params["search_lang"] == "en" and params["freshness"] == "pm"


def test_a_typed_query_carries_its_operators_language_and_freshness() -> None:
    transport = Transport(_json({"web": {"results": []}}))
    query = BraveQuery(
        "spotřeba kávy",
        site="csu.gov.cz",
        phrase="domácnosti celkem",
        lang="cs",
        freshness="2024-01-01to2025-06-30",
    )
    assert query.q == 'spotřeba kávy "domácnosti celkem" site:csu.gov.cz'
    _search(transport, lang="en").search_query(query, max_results=10)
    params = _params(transport.calls[0])
    assert params["q"] == query.q
    assert params["search_lang"] == "cs"
    assert params["freshness"] == "2024-01-01to2025-06-30"


def test_a_language_search_asks_its_own_language_and_refuses_another() -> None:
    transport = Transport(_json({"web": {"results": []}}))
    adapter = _search(transport, lang="cs", freshness="py")
    assert isinstance(adapter, LanguageSearch)
    adapter.search_in('plant drinks "per capita" site:csu.gov.cz', lang="en", max_results=4)
    params = _params(transport.calls[0])
    assert params["q"] == 'plant drinks "per capita" site:csu.gov.cz'
    assert (params["search_lang"], params["freshness"], params["count"]) == ("en", "py", "4")
    for query, lang in (("káva", "de"), ("káva filetype:pdf", "cs")):
        with pytest.raises(ToolCallFailed) as refused:
            adapter.search_in(query, lang=lang, max_results=4)
        assert refused.value.delivery is Delivery.NOT_SENT
    assert len(transport.calls) == 1


def test_a_phrase_alone_is_a_query() -> None:
    assert BraveQuery("", phrase="tržní podíl").q == '"tržní podíl"'


@pytest.mark.parametrize("value", ["pd", "pw", "pm", "py", "2025-01-01to2025-01-01"])
def test_freshness_values_brave_documents_are_accepted(value: str) -> None:
    assert check_freshness(value) == value


@pytest.mark.parametrize(
    "value",
    ["", "p1", "PD", "2025-1-1to2025-02-01", "2025-02-30to2025-03-01", "2025-03-01to2025-01-01",
     "2025-01-01..2025-02-01", "pd "],
)  # fmt: skip
def test_bad_freshness_is_refused(value: str) -> None:
    with pytest.raises(ValueError):
        check_freshness(value)
    with pytest.raises(ValueError):
        BraveQuery("káva", freshness=value)


@pytest.mark.parametrize(
    "site",
    ["https://csu.gov.cz", "csu.gov.cz/data", "csu gov.cz", "CSU.gov.cz", "csu.gov.cz:443",
     "localhost", "intranet.local", "10.0.0.1", "", "-csu.gov.cz", "csu", "a..cz"],
)  # fmt: skip
def test_site_must_be_a_bare_public_host(site: str) -> None:
    with pytest.raises(ValueError):
        BraveQuery("káva", site=site)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": "káva", "phrase": 'with "quote"'},
        {"text": "káva", "phrase": "   "},
        {"text": "káva", "lang": "de"},
        {"text": "káva filetype:pdf"},
        {"text": "káva", "phrase": "ext:xlsx"},
        {"text": "první\ndruhý"},
        {"text": "   "},
    ],
)
def test_bad_parts_are_refused(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        BraveQuery(**kwargs)


def test_the_adapter_refuses_an_unknown_language_or_freshness() -> None:
    with pytest.raises(ValueError):
        _search(Transport(), lang="de")
    with pytest.raises(ValueError):
        _search(Transport(), freshness="yesterday")


@pytest.mark.parametrize(
    ("query", "max_results", "reason"),
    [
        ("", 5, "search_bounds"),
        ("   ", 5, "search_bounds"),
        ("káva", 0, "search_bounds"),
        ("x" * 401, 5, "search_bounds"),
        (" ".join(["slovo"] * 51), 5, "search_bounds"),
        ("káva filetype:pdf", 5, "search_operator"),
        ("káva -FileType:xls", 5, "search_operator"),
        ("káva\r\nHost: evil", 5, "search_operator"),
    ],
)
def test_out_of_bounds_queries_send_nothing(query: str, max_results: int, reason: str) -> None:
    transport = Transport(_json({}))
    resolver = Resolver()
    with pytest.raises(ToolCallFailed) as failed:
        _search(transport, resolver=resolver).search(query, max_results=max_results)
    assert failed.value.delivery is Delivery.NOT_SENT and failed.value.reason == reason
    assert transport.calls == [] and resolver.hosts == []


def test_a_mixed_or_empty_resolution_sends_nothing() -> None:
    for addresses in ((), (ADDRESS, "10.0.0.5"), ("169.254.169.254",)):
        transport = Transport(_json({}))
        with pytest.raises(ToolCallFailed) as failed:
            _search(transport, resolver=Resolver(addresses)).search("káva", max_results=3)
        assert failed.value.delivery is Delivery.NOT_SENT
        assert failed.value.reason in {"address_unresolved", "address_not_public"}
        assert transport.calls == []


# ----------------------------------------------------------------- response --


def test_hits_are_mapped_in_order_with_html_stripped_and_bad_urls_dropped_and_counted() -> None:
    transport = Transport(_json(DOCUMENTED_SHAPE, request_id="req-7"))
    answer = _search(transport).search("spotřeba kávy domácnosti", max_results=10)
    assert [(h.rank, h.url) for h in answer.hits] == [
        (1, "https://statistika.example.cz/kava/2025"),
        (3, "https://rocenka.example.org/trh-kava"),
    ]
    first = answer.hits[0]
    assert first.title == "Spotřeba kávy v domácnostech & trh"
    assert first.snippet == "Fiktivní přehled spotřeby, rok 2025."
    assert answer.dropped == 3
    assert answer.credits == 1
    assert answer.provider_request_id == "req-7"


def test_no_request_id_is_none_never_a_guess() -> None:
    answer = _search(Transport(_json(DOCUMENTED_SHAPE))).search("káva", max_results=3)
    assert answer.provider_request_id is None


def test_only_the_asked_number_of_results_is_read() -> None:
    answer = _search(Transport(_json(DOCUMENTED_SHAPE))).search("káva", max_results=1)
    assert len(answer.hits) == 1 and answer.dropped == 0


@pytest.mark.parametrize("payload", [{}, {"web": {}}, {"type": "search"}])
def test_no_web_results_is_an_empty_answer(payload: dict[str, Any]) -> None:
    answer = _search(Transport(_json(payload))).search("káva", max_results=3)
    assert answer.hits == () and answer.dropped == 0 and answer.credits == 1


# ----------------------------------------------------------------- failures --


@pytest.mark.parametrize(
    ("status", "reason", "delivery"),
    [
        (401, "bad_credential", Delivery.RESPONDED),
        (403, "bad_credential", Delivery.RESPONDED),
        (400, "bad_request", Delivery.RESPONDED),
        (422, "bad_request", Delivery.RESPONDED),
        (429, "rate_limited", Delivery.RESPONDED),
        (404, "http_404", Delivery.RESPONDED),
        (500, "provider_error", Delivery.UNKNOWN),
        (502, "provider_error", Delivery.UNKNOWN),
        (503, "provider_error", Delivery.UNKNOWN),
    ],
)
def test_http_failures_name_their_reason_and_delivery(
    status: int, reason: str, delivery: Delivery
) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _search(Transport(_json({"error": "x"}, status=status))).search("káva", max_results=3)
    assert (failed.value.reason, failed.value.delivery) == (reason, delivery)


@pytest.mark.parametrize(
    "response",
    [
        FetchedResponse(200, {"content-type": "application/json"}, b"{not json", False),
        FetchedResponse(200, {"content-type": "application/json"}, b"\xff\xfe", False),
        FetchedResponse(200, {"content-type": "application/json"}, b"[1, 2]", False),
        FetchedResponse(200, {"content-type": "text/html"}, b"<html></html>", False),
        FetchedResponse(200, {}, b"{}", False),
        _json({"web": {"results": "many"}}),
        _json({"web": ["results"]}),
        _json({"web": {"results": [{"url": "https://a.example.cz/", "title": 7}]}}),
    ],
)
def test_malformed_answers_are_provider_errors_that_responded(response: FetchedResponse) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _search(Transport(response)).search("káva", max_results=3)
    assert failed.value.reason == "provider_error"
    assert failed.value.delivery is Delivery.RESPONDED


def test_an_oversized_answer_is_refused() -> None:
    response = FetchedResponse(200, {"content-type": "application/json"}, b"{}", True)
    with pytest.raises(ToolCallFailed) as failed:
        _search(Transport(response)).search("káva", max_results=3)
    assert failed.value.reason == "response_too_large"


def test_a_transport_failure_passes_through_unchanged_and_is_not_retried() -> None:
    lost = ToolCallFailed("lost", reason="timeout", delivery=Delivery.UNKNOWN)
    transport = Transport(failure=lost)
    with pytest.raises(ToolCallFailed) as failed:
        _search(transport).search("káva", max_results=3)
    assert failed.value is lost and len(transport.calls) == 1


@pytest.mark.parametrize("secrets", [{}, {REF: ""}, {REF: "   "}])
def test_a_missing_credential_sends_nothing(secrets: dict[str, str]) -> None:
    transport = Transport(_json(DOCUMENTED_SHAPE))
    resolver = Resolver()
    with pytest.raises(ToolCallFailed) as failed:
        _search(transport, resolver=resolver, secrets=secrets).search("káva", max_results=3)
    assert failed.value.reason == "missing_credential"
    assert failed.value.delivery is Delivery.NOT_SENT
    assert REF in str(failed.value)
    assert transport.calls == [] and resolver.hosts == []


# --------------------------------------------------------------- transport --


@dataclass
class _Response:
    status: int
    headers: dict[str, str]
    body: bytes
    fail_on_read: Exception | None = None
    released: bool = False
    _offset: int = 0

    def read(self, amount: int, *, decode_content: bool) -> bytes:
        assert decode_content is False
        if self.fail_on_read is not None:
            raise self.fail_on_read
        chunk = self.body[self._offset : self._offset + amount]
        self._offset += len(chunk)
        return chunk

    def release_conn(self) -> None:
        self.released = True


@dataclass
class _Pool:
    """Stands in for urllib3.HTTPSConnectionPool: records what would have been sent."""

    outcome: _Response | Exception
    created: list[dict[str, Any]] = field(default_factory=list)
    requests: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False

    def __call__(self, host: str, **kwargs: Any) -> _Pool:
        self.created.append({"host": host, **kwargs})
        return self

    def request(self, method: str, path: str, **kwargs: Any) -> _Response:
        self.requests.append({"method": method, "path": path, **kwargs})
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    def close(self) -> None:
        self.closed = True


def _real_transport(monkeypatch: pytest.MonkeyPatch, pool: _Pool) -> BraveHttpsTransport:
    import urllib3

    monkeypatch.setattr(urllib3, "HTTPSConnectionPool", pool)
    return BraveHttpsTransport()


def _get(transport: BraveHttpsTransport, url: str | None = None) -> FetchedResponse:
    return transport.get(
        url or f"https://{BRAVE_API_HOST}/res/v1/web/search?q=k%C3%A1va",
        address=ADDRESS,
        max_bytes=MAX_RESPONSE_BYTES,
        headers={"Accept": "application/json", "X-Subscription-Token": KEY},
    )


def test_the_transport_pins_the_checked_ip_verifies_the_host_and_follows_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = json.dumps(DOCUMENTED_SHAPE).encode()
    pool = _Pool(_Response(200, {"Content-Type": "application/json", "X-Request-Id": "r-1"}, body))
    answer = _get(_real_transport(monkeypatch, pool))
    (created,) = pool.created
    assert created["host"] == ADDRESS and created["port"] == 443
    assert created["server_hostname"] == created["assert_hostname"] == BRAVE_API_HOST
    assert created["cert_reqs"] == "CERT_REQUIRED" and created["retries"] is False
    (sent,) = pool.requests
    assert sent["method"] == "GET" and sent["path"] == "/res/v1/web/search?q=k%C3%A1va"
    assert sent["redirect"] is False and sent["retries"] is False
    assert sent["headers"]["Host"] == BRAVE_API_HOST
    assert sent["headers"]["X-Subscription-Token"] == KEY
    assert sent["headers"]["Accept-Encoding"] == "identity"
    assert answer.status == 200 and answer.body == body and not answer.truncated
    assert answer.provider_request_id == "r-1"
    assert pool.closed and isinstance(pool.outcome, _Response) and pool.outcome.released


def test_a_redirect_is_returned_not_followed(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _Pool(_Response(302, {"Location": "https://evil.example.com/"}, b""))
    transport = _real_transport(monkeypatch, pool)
    with pytest.raises(ToolCallFailed) as failed:
        _search(Transport(_get(transport))).search("káva", max_results=1)
    assert failed.value.reason == "http_302" and len(pool.requests) == 1


def test_the_body_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _Pool(_Response(200, {}, b"x" * (MAX_RESPONSE_BYTES + 10)))
    answer = _get(_real_transport(monkeypatch, pool))
    assert answer.truncated and len(answer.body) == MAX_RESPONSE_BYTES


def test_a_gzipped_body_is_inflated_within_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps(DOCUMENTED_SHAPE).encode()
    pool = _Pool(_Response(200, {"Content-Encoding": "gzip"}, gzip.compress(body)))
    answer = _get(_real_transport(monkeypatch, pool))
    assert answer.body == body and not answer.truncated
    bomb = _Pool(_Response(200, {"Content-Encoding": "gzip"}, gzip.compress(b"0" * 3_000_000)))
    assert _get(_real_transport(monkeypatch, bomb)).truncated


@pytest.mark.parametrize(
    ("encoding", "body", "reason"),
    [("br", b"..", "content_encoding"), ("gzip", b"not gzip", "provider_error")],
)
def test_an_unreadable_encoding_is_refused(
    monkeypatch: pytest.MonkeyPatch, encoding: str, body: bytes, reason: str
) -> None:
    pool = _Pool(_Response(200, {"Content-Encoding": encoding}, body))
    with pytest.raises(ToolCallFailed) as failed:
        _get(_real_transport(monkeypatch, pool))
    assert failed.value.reason == reason and failed.value.delivery is Delivery.RESPONDED


@pytest.mark.parametrize(
    "url",
    [
        "https://api.search.brave.com.evil.example/res/v1/web/search",
        "https://search.brave.com/search?q=x",
        "https://example.com/res/v1/web/search",
        "http://api.search.brave.com/res/v1/web/search",
        "https://api.search.brave.com:8443/res/v1/web/search",
    ],
)
def test_the_transport_reaches_no_other_host(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    pool = _Pool(_Response(200, {}, b"{}"))
    with pytest.raises(FetchRefused):
        _get(_real_transport(monkeypatch, pool), url)
    assert pool.created == [] and pool.requests == []


def test_the_transport_refuses_a_non_public_address(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _Pool(_Response(200, {}, b"{}"))
    transport = _real_transport(monkeypatch, pool)
    for address in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "::1"):
        with pytest.raises(FetchRefused):
            transport.get(
                f"https://{BRAVE_API_HOST}/res/v1/web/search",
                address=address,
                max_bytes=10,
                headers={},
            )
    assert pool.created == []


def _urllib3_failures() -> list[tuple[Exception, str, Delivery]]:
    import ssl

    from urllib3.exceptions import (
        ConnectTimeoutError,
        NewConnectionError,
        ProtocolError,
        ReadTimeoutError,
        SSLError,
    )
    from urllib3.exceptions import TimeoutError as Urllib3Timeout

    cert = SSLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))
    return [
        (ConnectTimeoutError(None, "connect timed out"), "connect_failed", Delivery.NOT_SENT),
        (NewConnectionError(None, "refused"), "connect_failed", Delivery.NOT_SENT),  # type: ignore[arg-type]
        (ReadTimeoutError(None, "/", "read timed out"), "timeout", Delivery.UNKNOWN),  # type: ignore[arg-type]
        (ProtocolError("Connection aborted.", ConnectionResetError(104, "reset")), "reset",
         Delivery.UNKNOWN),
        (cert, "tls_failed", Delivery.NOT_SENT),
        (SSLError("EOF in violation of protocol"), "tls_failed", Delivery.UNKNOWN),
        (Urllib3Timeout("other"), "transport_failed", Delivery.UNKNOWN),
    ]  # fmt: skip


@pytest.mark.parametrize("on_read", [False, True])
def test_transport_failures_name_their_delivery(
    monkeypatch: pytest.MonkeyPatch, on_read: bool
) -> None:
    for error, reason, delivery in _urllib3_failures():
        if on_read and reason == "connect_failed":
            continue
        outcome: _Response | Exception = (
            _Response(200, {}, b"", fail_on_read=error) if on_read else error
        )
        pool = _Pool(outcome)
        with pytest.raises(ToolCallFailed) as failed:
            _get(_real_transport(monkeypatch, pool))
        assert (failed.value.reason, failed.value.delivery) == (reason, delivery), error
        assert pool.closed


# ----------------------------------------------------------- the key leaks --


def _chain(exc: BaseException) -> list[BaseException]:
    seen: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in seen:
        seen.append(current)
        current = current.__cause__ or current.__context__
    return seen


def _assert_no_key(exc: BaseException) -> None:
    for link in _chain(exc):
        for text in (
            str(link),
            repr(link),
            repr(link.args),
            repr(vars(link)) if hasattr(link, "__dict__") else "",
        ):
            assert KEY not in text, f"key leaked through {type(link).__name__}"


def test_the_key_never_appears_in_any_failure_repr_or_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    failures: list[BaseException] = []
    # Every adapter-level failure, the key resolved and in hand.
    responses = [_json({}, status=s) for s in (400, 401, 403, 404, 422, 429, 500, 503)]
    responses += [
        FetchedResponse(200, {"content-type": "application/json"}, b"{bad", False),
        FetchedResponse(200, {"content-type": "application/json"}, b"{}", True),
    ]
    for response in responses:
        with pytest.raises(ToolCallFailed) as failed:
            _search(Transport(response)).search("káva", max_results=3)
        failures.append(failed.value)
    for query in ("", "káva filetype:pdf"):
        with pytest.raises(ToolCallFailed) as failed:
            _search(Transport()).search(query, max_results=3)
        failures.append(failed.value)
    with pytest.raises(ToolCallFailed) as failed:
        _search(Transport(), resolver=Resolver(("10.0.0.1",))).search("káva", max_results=3)
    failures.append(failed.value)
    # Every transport-level failure, the key in the headers it was asked to send.
    for error, _, _ in _urllib3_failures():
        for outcome in (error, _Response(200, {}, b"", fail_on_read=error)):
            with pytest.raises(ToolCallFailed) as failed:
                _get(_real_transport(monkeypatch, _Pool(outcome)))
            failures.append(failed.value)
    for encoding, body in (("br", b".."), ("gzip", b"no")):
        with pytest.raises(ToolCallFailed) as failed:
            _get(
                _real_transport(
                    monkeypatch, _Pool(_Response(200, {"Content-Encoding": encoding}, body))
                )
            )
        failures.append(failed.value)
    assert len(failures) > 25
    for exc in failures:
        _assert_no_key(exc)
    adapter = _search(Transport(_json(DOCUMENTED_SHAPE)))
    answer = adapter.search("káva", max_results=3)
    for text in (
        repr(adapter),
        str(adapter),
        repr(vars(adapter)),
        repr(answer),
        repr(BraveHttpsTransport()),
    ):
        assert KEY not in text
    assert KEY not in caplog.text
