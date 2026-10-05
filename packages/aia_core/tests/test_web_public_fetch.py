"""Public-web fetch: any public host, its robots.txt obeyed, its pace kept, nothing leaked.

No network: the transport runs over a scripted wire, a scripted resolver and a
fake clock; one test replaces urllib3's pool to see what the real wire would send.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar

import pytest

from aia_core.application.web_retrieval import RetrievalGate, WebRetrieval
from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
)
from aia_core.domain.deep_research.web import FetchRefused
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure import web_retrieval_live
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    ToolCallFailed,
    WebFetcher,
)
from aia_core.infrastructure.web_retrieval_live import (
    PinnedHttpsTransport,
    PublicHttpsTransport,
    UrllibWire,
    public_user_agent,
)

CONTACT = "research-desk@aia.example"
PUBLIC = "93.184.215.14"
OTHER = "93.184.215.15"
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
PAGE = "<html><head><title>Trh</title></head><body><p>Spotřeba vzrostla.</p></body></html>"
HTML = {"content-type": "text/html; charset=utf-8"}


@dataclass
class Clock:
    now: float = 1000.0
    slept: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@dataclass
class Sent:
    at: float
    address: str
    host: str
    target: str
    headers: dict[str, str]
    max_bytes: int


@dataclass
class Wire:
    """Answers by (host, target); every request it is asked to send is recorded."""

    clock: Clock
    answers: dict[tuple[str, str], FetchedResponse | Exception]
    sent: list[Sent] = field(default_factory=list)

    def get(
        self, *, address: str, host: str, target: str, headers: Mapping[str, str], max_bytes: int
    ) -> FetchedResponse:
        self.sent.append(Sent(self.clock.now, address, host, target, dict(headers), max_bytes))
        answer = self.answers.get(
            (host, target), FetchedResponse(status=404, headers={}, body=b"", truncated=False)
        )
        if isinstance(answer, Exception):
            raise answer
        return answer

    def targets(self) -> list[str]:
        return [f"{s.host}{s.target}" for s in self.sent]


@dataclass
class Resolver:
    hosts: dict[str, tuple[str, ...]]

    def resolve(self, host: str) -> tuple[str, ...]:
        return self.hosts.get(host, ())


def _ok(body: str, headers: dict[str, str] | None = None, status: int = 200) -> FetchedResponse:
    return FetchedResponse(
        status=status, headers=headers or HTML, body=body.encode(), truncated=False
    )


def _robots(body: str) -> FetchedResponse:
    return _ok(body, {"content-type": "text/plain"})


def _redirect(location: str, status: int = 302) -> FetchedResponse:
    return FetchedResponse(status=status, headers={"Location": location}, body=b"", truncated=False)


def _setup(
    answers: dict[tuple[str, str], FetchedResponse | Exception],
    *,
    hosts: dict[str, tuple[str, ...]] | None = None,
    **options: Any,
) -> tuple[WebFetcher, PublicHttpsTransport, Wire, Clock]:
    clock = Clock()
    wire = Wire(clock, answers)
    resolver = Resolver(
        hosts
        or {"stats.example": (PUBLIC,), "www.stats.example": (OTHER,), "news.example": (OTHER,)}
    )
    transport = PublicHttpsTransport(
        contact=CONTACT,
        resolver=resolver,
        wire=wire,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        **options,
    )
    fetcher = WebFetcher(
        transport=transport, resolver=resolver, adapter_id="public-https-1", clock=lambda: NOW
    )
    return fetcher, transport, wire, clock


# --------------------------------------------------------------------------- any host


def test_any_public_host_is_fetched_from_the_checked_address_after_its_robots_txt() -> None:
    fetcher, transport, wire, _ = _setup(
        {
            ("stats.example", "/robots.txt"): _robots("User-agent: *\nDisallow: /private\n"),
            ("stats.example", "/data?year=2025"): _ok(PAGE),
            ("news.example", "/a"): _ok(PAGE),
        }
    )
    page = fetcher.fetch("https://stats.example/data?year=2025")
    assert page.snapshot.title == "Trh" and page.snapshot.retrieval_mode is RetrievalMode.LIVE
    assert fetcher.fetch("https://news.example/a").snapshot.text
    assert wire.targets() == [
        "stats.example/robots.txt",
        "stats.example/data?year=2025",
        "news.example/robots.txt",  # a 404: no file, everything allowed
        "news.example/a",
    ]
    assert [s.address for s in wire.sent] == [PUBLIC, PUBLIC, OTHER, OTHER]
    assert transport.retrieval_mode is RetrievalMode.LIVE


def test_every_request_identifies_aia_with_its_contact_and_carries_nothing_else() -> None:
    fetcher, transport, wire, _ = _setup({("stats.example", "/a"): _ok(PAGE)})
    fetcher.fetch("https://stats.example/a")
    agent = f"AIA-research/1 (+mailto:{CONTACT})"
    assert transport.user_agent == agent == public_user_agent(CONTACT)
    for sent in wire.sent:
        names = {name.lower() for name in sent.headers}
        assert sent.headers["User-Agent"] == agent
        assert sent.headers["Host"] == "stats.example"
        assert sent.headers["Accept-Encoding"] == "identity"
        assert names.isdisjoint({"cookie", "authorization", "proxy-authorization", "referer"})
    assert wire.sent[0].max_bytes == 512_000  # robots.txt has its own cap
    assert wire.sent[1].max_bytes == 2_000_000


@pytest.mark.parametrize(
    "contact", ["", "nobody", "a@b", "x@y.example (me)", "two@a.example,three@b.example"]
)
def test_a_contact_address_is_required_and_must_be_one_address(contact: str) -> None:
    with pytest.raises(ValueError):
        PublicHttpsTransport(contact=contact, resolver=Resolver({}))


def test_plain_http_internal_and_non_public_addresses_are_refused_before_sending() -> None:
    _, transport, wire, _ = _setup({})
    for url, address, reason in [
        ("http://stats.example/a", PUBLIC, "https_only"),
        ("https://stats.example/a", "10.0.0.8", "address_not_public"),
        ("https://stats.example/a", "169.254.169.254", "address_not_public"),
        ("https://stats.example/a", "127.0.0.1", "address_not_public"),
        ("https://metadata.google.internal/", PUBLIC, "url_internal_host"),
        ("https://stats.example:8443/a", PUBLIC, "url_port"),
    ]:
        with pytest.raises(FetchRefused) as refused:
            transport.get(url, address=address, max_bytes=1000)
        assert refused.value.reason == reason
    assert wire.sent == []


def test_a_private_address_on_a_redirect_hop_is_refused() -> None:
    fetcher, _, wire, _ = _setup(
        {
            ("stats.example", "/a"): _redirect("https://evil.example/x"),
            ("evil.example", "/x"): _ok(PAGE),
        },
        hosts={"stats.example": (PUBLIC,), "evil.example": (PUBLIC, "10.0.0.8")},
    )
    with pytest.raises(FetchRefused) as refused:
        fetcher.fetch("https://stats.example/a")
    assert refused.value.reason == "address_not_public"
    assert wire.targets() == ["stats.example/robots.txt", "stats.example/a"]


def test_the_metadata_service_on_a_redirect_hop_is_never_reached() -> None:
    fetcher, _, wire, _ = _setup(
        {("stats.example", "/a"): _redirect("http://169.254.169.254/latest/meta-data/")}
    )
    with pytest.raises(FetchRefused) as refused:
        fetcher.fetch("https://stats.example/a")
    assert refused.value.reason == "address_not_public"
    assert all(s.address == PUBLIC for s in wire.sent)


def test_a_redirect_to_another_public_host_reads_that_hosts_robots_too() -> None:
    fetcher, _, wire, _ = _setup(
        {
            ("stats.example", "/a"): _redirect("https://www.stats.example/a"),
            ("www.stats.example", "/robots.txt"): _robots("User-agent: *\nDisallow: /a\n"),
        }
    )
    with pytest.raises(FetchRefused) as refused:
        fetcher.fetch("https://stats.example/a")
    assert refused.value.reason == "robots_disallowed"
    assert wire.targets() == [
        "stats.example/robots.txt",
        "stats.example/a",
        "www.stats.example/robots.txt",
    ]


# --------------------------------------------------------------------------- robots.txt


def test_a_disallowed_url_is_refused_before_any_request_for_it() -> None:
    fetcher, transport, wire, _ = _setup(
        {
            ("stats.example", "/robots.txt"): _robots(
                "User-agent: AIA-research\nDisallow: /soukrome/\n"
            ),
            ("stats.example", "/verejne"): _ok(PAGE),
        }
    )
    with pytest.raises(FetchRefused) as refused:
        fetcher.fetch("https://stats.example/soukrome/x")
    assert refused.value.reason == "robots_disallowed"
    assert wire.targets() == ["stats.example/robots.txt"]
    # Now known: refused without sending anything, and robots.txt is not read again.
    assert transport.known_refusal("https://stats.example/soukrome/y") == "robots_disallowed"
    assert fetcher.known_refusal("https://stats.example/verejne") is None
    fetcher.fetch("https://stats.example/verejne")
    assert wire.targets() == ["stats.example/robots.txt", "stats.example/verejne"]
    # A host whose robots.txt was never read is not known yet.
    assert transport.known_refusal("https://news.example/a") is None


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        (FetchedResponse(status=404, headers={}, body=b"", truncated=False), None),
        (FetchedResponse(status=410, headers={}, body=b"", truncated=False), None),
        (FetchedResponse(status=401, headers={}, body=b"", truncated=False), "robots_disallowed"),
        (FetchedResponse(status=403, headers={}, body=b"", truncated=False), "robots_disallowed"),
        (FetchedResponse(status=429, headers={}, body=b"", truncated=False), "robots_unavailable"),
        (FetchedResponse(status=500, headers={}, body=b"", truncated=False), "robots_unavailable"),
        (FetchedResponse(status=503, headers={}, body=b"", truncated=False), "robots_unavailable"),
        (
            ToolCallFailed("read timed out", reason="transport_failed", delivery=Delivery.UNKNOWN),
            "robots_unavailable",
        ),
        (
            ToolCallFailed("refused", reason="connect_failed", delivery=Delivery.NOT_SENT),
            "robots_unavailable",
        ),
        (_redirect("https://10.0.0.8/robots.txt"), "robots_unavailable"),
        (_redirect("http://stats.example/robots.txt"), "robots_unavailable"),
    ],
)
def test_robots_txt_that_is_not_a_file_sets_the_conservative_policy(
    answer: FetchedResponse | Exception, reason: str | None
) -> None:
    fetcher, _, wire, _ = _setup(
        {("stats.example", "/robots.txt"): answer, ("stats.example", "/a"): _ok(PAGE)}
    )
    if reason is None:
        fetcher.fetch("https://stats.example/a")
        assert wire.targets()[-1] == "stats.example/a"
    else:
        with pytest.raises(FetchRefused) as refused:
            fetcher.fetch("https://stats.example/a")
        assert refused.value.reason == reason
        assert "stats.example/a" not in wire.targets()


def test_robots_redirects_are_followed_a_bounded_number_of_times() -> None:
    hops = {
        ("stats.example", "/robots.txt" if i == 0 else f"/r{i}"): _redirect(f"/r{i + 1}")
        for i in range(6)
    }
    fetcher, _, wire, _ = _setup({**hops, ("stats.example", "/a"): _ok(PAGE)})
    with pytest.raises(FetchRefused) as refused:
        fetcher.fetch("https://stats.example/a")
    assert refused.value.reason == "robots_unavailable"
    assert len(wire.sent) == 6  # the file and five redirects; the page never
    followed, _, wire, _ = _setup(
        {
            ("stats.example", "/robots.txt"): _redirect("https://www.stats.example/robots.txt"),
            ("www.stats.example", "/robots.txt"): _robots("User-agent: *\nDisallow: /a\n"),
        }
    )
    with pytest.raises(FetchRefused):
        followed.fetch("https://stats.example/a")
    assert [s.address for s in wire.sent] == [PUBLIC, OTHER]


def test_robots_txt_is_read_once_per_host_and_again_after_it_expires() -> None:
    fetcher, _, wire, clock = _setup(
        {("stats.example", f"/{i}"): _ok(PAGE) for i in range(3)}, robots_ttl_s=3600.0
    )
    fetcher.fetch("https://stats.example/0")
    fetcher.fetch("https://stats.example/1")
    assert wire.targets().count("stats.example/robots.txt") == 1
    clock.now += 3600.0
    fetcher.fetch("https://stats.example/2")
    assert wire.targets().count("stats.example/robots.txt") == 2


# --------------------------------------------------------------------------- pace


def test_crawl_delay_spaces_every_request_to_a_host() -> None:
    fetcher, _, wire, clock = _setup(
        {
            ("stats.example", "/robots.txt"): _robots("User-agent: *\nCrawl-delay: 5\n"),
            **{("stats.example", f"/{i}"): _ok(PAGE) for i in range(3)},
            ("news.example", "/a"): _ok(PAGE),
        }
    )
    for i in range(3):
        fetcher.fetch(f"https://stats.example/{i}")
    fetcher.fetch("https://news.example/a")
    times = [s.at for s in wire.sent if s.host == "stats.example"]
    assert times == [1000.0, 1005.0, 1010.0, 1015.0]
    # Another host keeps its own pace: its robots.txt needs no wait, its page the minimum.
    news = [s.at for s in wire.sent if s.host == "news.example"]
    assert news == [1015.0, 1016.0]
    assert clock.slept == [5.0, 5.0, 5.0, 1.0]


def test_without_a_crawl_delay_the_minimum_interval_holds() -> None:
    fetcher, _, wire, clock = _setup(
        {("stats.example", f"/{i}"): _ok(PAGE) for i in range(2)}, min_interval_s=2.0
    )
    clock.now = 0.0
    fetcher.fetch("https://stats.example/0")
    clock.now += 0.5  # time passed elsewhere counts
    fetcher.fetch("https://stats.example/1")
    assert [s.at for s in wire.sent] == [0.0, 2.0, 4.0]


def test_a_crawl_delay_longer_than_the_run_can_wait_refuses_the_host() -> None:
    fetcher, transport, wire, _ = _setup(
        {("stats.example", "/robots.txt"): _robots("User-agent: *\nCrawl-delay: 3600\n")},
        max_crawl_delay_s=30.0,
    )
    with pytest.raises(FetchRefused) as refused:
        fetcher.fetch("https://stats.example/a")
    assert refused.value.reason == "robots_crawl_delay"
    assert transport.known_refusal("https://stats.example/b") == "robots_crawl_delay"
    assert wire.targets() == ["stats.example/robots.txt"]


# --------------------------------------------------------------------------- the gate


def _route(tool: ToolKind) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"public-{tool.value}",
            provider="public-web",
            zone=ResidencyZone.EU,
            eu_processing_approved=True,
            excluded_from_training=True,
            retention_days=0,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
        tool=tool,
        adapter_id="live-search-v1" if tool is ToolKind.WEB_SEARCH else "public-https-1",
        retrieval_mode=RetrievalMode.LIVE,
        price_usd_per_call=0.0,
    )


@dataclass
class _LiveSearch:
    adapter_id: str = "live-search-v1"
    retrieval_mode: RetrievalMode = RetrievalMode.LIVE

    def search(self, query: str, *, max_results: int) -> Any:
        raise AssertionError("no search in these tests")


def test_the_gate_journals_a_robots_refusal_and_refuses_a_known_one_before_dispatch(
    scoped: Any,
) -> None:
    fetcher, _, wire, _ = _setup(
        {("stats.example", "/robots.txt"): _robots("User-agent: *\nDisallow: /x\n")}
    )
    ledger = InMemoryToolLedger(budget_usd=0.0)
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH),
            fetch_route=_route(ToolKind.WEB_FETCH),
            search=_LiveSearch(),
            fetcher=fetcher,
        ),
        scope=scoped.scope(),
        meter=ledger,
        client_terms=(),
        class_a_texts=(),
        clock=lambda: NOW,
    )
    first = gate.fetch("https://stats.example/x/1", track_id="T")
    assert first.page is None and first.reason == "robots_disallowed"
    second = gate.fetch("https://stats.example/x/2", track_id="T")
    assert second.reason == "robots_disallowed"
    events = ledger.events()
    assert [e.outcome for e in events] == [
        ToolOutcome.DISPATCHED,  # robots.txt had to be read: that left
        ToolOutcome.FAILED,
        ToolOutcome.REFUSED,  # known: nothing was sent
    ]
    assert [e.note for e in events[1:]] == ["robots_disallowed", "robots_disallowed"]
    assert wire.targets() == ["stats.example/robots.txt"]


# --------------------------------------------------------------------------- the wire


class _FakePool:
    created: ClassVar[list[tuple[str, dict[str, Any]]]] = []
    requests: ClassVar[list[tuple[str, str, dict[str, Any]]]] = []

    def __init__(self, address: str, **kwargs: Any) -> None:
        _FakePool.created.append((address, kwargs))

    def request(self, method: str, target: str, **kwargs: Any) -> Any:
        _FakePool.requests.append((method, target, kwargs))
        return _FakeResponse()

    def close(self) -> None:
        pass


class _FakeResponse:
    status = 200
    headers: ClassVar[dict[str, str]] = {"Content-Type": "text/html", "Set-Cookie": "session=1"}

    def __init__(self) -> None:
        self._body = [PAGE.encode(), b""]

    def read(self, amount: int, decode_content: bool) -> bytes:
        assert decode_content is False
        return self._body.pop(0)

    def release_conn(self) -> None:
        pass


def test_the_wire_pins_the_address_verifies_the_host_and_never_follows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import urllib3

    _FakePool.created.clear()
    _FakePool.requests.clear()
    monkeypatch.setattr(urllib3, "HTTPSConnectionPool", _FakePool)
    wire = UrllibWire()
    answer = wire.get(
        address=PUBLIC,
        host="stats.example",
        target="/a?b=1",
        headers={"Host": "stats.example", "User-Agent": public_user_agent(CONTACT)},
        max_bytes=10_000,
    )
    assert answer.status == 200 and answer.body == PAGE.encode() and not answer.truncated
    address, pool = _FakePool.created[0]
    assert address == PUBLIC and pool["port"] == 443
    assert pool["server_hostname"] == pool["assert_hostname"] == "stats.example"
    assert pool["cert_reqs"] == "CERT_REQUIRED" and pool["retries"] is False
    method, target, request = _FakePool.requests[0]
    assert (method, target) == ("GET", "/a?b=1")
    assert request["redirect"] is False and request["retries"] is False
    assert set(request["headers"]) == {"Host", "User-Agent"}
    # A second request does not carry the cookie the first answer set.
    wire.get(address=PUBLIC, host="stats.example", target="/b", headers={}, max_bytes=10)
    assert _FakePool.requests[1][2]["headers"] == {}
    assert len(_FakePool.created) == 2  # a fresh pool per request: no state carried


def test_the_wikipedia_transport_still_refuses_every_other_host() -> None:
    clock = Clock()
    wire = Wire(clock, {("cs.wikipedia.org", "/wiki/Praha"): _ok(PAGE)})
    transport = PinnedHttpsTransport(wire=wire)
    with pytest.raises(FetchRefused) as refused:
        transport.get("https://stats.example/a", address=PUBLIC, max_bytes=1000)
    assert refused.value.reason == "host_scope"
    transport.get("https://cs.wikipedia.org/wiki/Praha", address=PUBLIC, max_bytes=1000)
    assert wire.targets() == ["cs.wikipedia.org/wiki/Praha"]  # no robots.txt on this route
    assert wire.sent[0].headers["User-Agent"] == web_retrieval_live.USER_AGENT


def test_the_sitemaps_robots_txt_declares_are_known_once_it_was_read(scoped: Any) -> None:
    fetcher, transport, wire, _ = _setup(
        {
            ("stats.example", "/robots.txt"): _robots(
                "User-agent: *\nDisallow: /x\nSitemap: https://stats.example/sitemap.xml\n"
            ),
            ("stats.example", "/a"): _ok(PAGE),
        }
    )
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH),
            fetch_route=_route(ToolKind.WEB_FETCH),
            search=_LiveSearch(),
            fetcher=fetcher,
        ),
        scope=scoped.scope(),
        meter=InMemoryToolLedger(budget_usd=0.0),
        client_terms=(),
        class_a_texts=(),
        clock=lambda: NOW,
    )
    # Not read yet: unknown, and asking sends nothing.
    assert gate.known_sitemaps("stats.example") is None
    assert wire.sent == []
    gate.fetch("https://stats.example/a", track_id="T")
    assert gate.known_sitemaps("stats.example") == ("https://stats.example/sitemap.xml",)
    assert transport.known_sitemaps("STATS.example.") == ("https://stats.example/sitemap.xml",)
    assert gate.known_sitemaps("news.example") is None
    assert wire.targets() == ["stats.example/robots.txt", "stats.example/a"]
