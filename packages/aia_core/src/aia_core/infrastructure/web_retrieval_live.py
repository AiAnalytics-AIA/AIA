"""Live public retrieval: checked-IP HTTPS transports, and the Czech Wikipedia search.

Every request connects to the exact globally routable IP that ``WebFetcher``
checked, while TLS verifies the original host (DNS rebinding cannot move it). No
transport here follows a redirect (``WebFetcher`` follows them by hand, checking
every hop), retries, uses a proxy, keeps or sends a cookie, or sends a credential.
Pages are untrusted evidence candidates, never instructions.

* :class:`PinnedHttpsTransport` -- the Wikipedia route's transport: Czech
  Wikipedia only, every other host refused.
* :class:`PublicHttpsTransport` -- any public host (plan chunk 5), politely:
  the host's ``robots.txt`` read once and obeyed (``domain.deep_research.robots``),
  its crawl delay kept, one request at a time per host, and an identifying user
  agent with the operator's contact address.
* :class:`UrllibWire` -- the one HTTPS request both make, over urllib3.
"""

from __future__ import annotations

import json
import re
import socket
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Any, Final, Protocol
from urllib.parse import quote, urlencode, urljoin, urlsplit

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.robots import (
    AGENT_TOKEN,
    MAX_ROBOTS_BYTES,
    RobotsPolicy,
    policy_for_response,
)
from ..domain.deep_research.web import (
    CSV_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
    FetchRefused,
    SearchHit,
    check_address,
    check_resolution,
    check_url,
)
from .model_adapters.live_transport import _certificate_refused
from .web_retrieval import (
    FetchedResponse,
    FetchTransport,
    Resolver,
    SearchResponse,
    ToolCallFailed,
    extract_page,
)

__all__ = [
    "HttpsWire",
    "PinnedHttpsTransport",
    "PublicHttpsTransport",
    "SystemResolver",
    "UrllibWire",
    "WikipediaSearch",
    "public_user_agent",
]

SEARCH_ID: Final = "wikipedia-cs-search-1"
SEARCH_HOST: Final = "cs.wikipedia.org"
SEARCH_ENDPOINT: Final = f"https://{SEARCH_HOST}/w/api.php"
USER_AGENT: Final = "AIAResearch/0.1 (https://aia-develop.art-chain.io/)"
MAX_SEARCH_BYTES: Final = 128_000
#: What a public fetch asks for: a page first, then the documents it keeps.
PAGE_ACCEPT: Final = (
    "text/html, application/xhtml+xml, text/plain;q=0.9, "
    f"{PDF_MEDIA_TYPE};q=0.8, {XLSX_MEDIA_TYPE};q=0.8, {CSV_MEDIA_TYPE};q=0.8"
)


class SystemResolver:
    """Resolve every address; the caller rejects a mixed public/private answer."""

    def resolve(self, host: str) -> tuple[str, ...]:
        try:
            answers = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except OSError:
            return ()
        return tuple(dict.fromkeys(str(answer[4][0]) for answer in answers))


class HttpsWire(Protocol):
    """One HTTPS GET to ``address`` with ``host`` as TLS authority. No redirect, no retry."""

    def get(
        self, *, address: str, host: str, target: str, headers: Mapping[str, str], max_bytes: int
    ) -> FetchedResponse:
        """Read at most ``max_bytes`` of the answer, or raise :class:`ToolCallFailed`."""
        ...


def _target(url: str) -> str:
    parts = urlsplit(url)
    return (parts.path or "/") + (f"?{parts.query}" if parts.query else "")


class UrllibWire:
    """The HTTPS request over urllib3: a one-connection pool per request, no proxy.

    The pool connects to the checked address; ``server_hostname`` (SNI) and
    ``assert_hostname`` make TLS verify the URL's host. A pool keeps no cookies,
    reads no proxy from the environment and, with ``retries=False`` and
    ``redirect=False``, neither retries nor follows. A compressed answer is refused.
    """

    def __init__(self, *, connect_timeout_s: float = 8.0, read_timeout_s: float = 20.0) -> None:
        import urllib3

        self._urllib3 = urllib3
        self._connect_timeout_s = connect_timeout_s
        self._read_timeout_s = read_timeout_s

    def get(
        self, *, address: str, host: str, target: str, headers: Mapping[str, str], max_bytes: int
    ) -> FetchedResponse:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        u = self._urllib3
        pool = u.HTTPSConnectionPool(
            address,
            port=443,
            server_hostname=host,
            assert_hostname=host,
            cert_reqs="CERT_REQUIRED",
            retries=False,
            maxsize=1,
            block=True,
        )
        response: Any = None
        try:
            response = pool.request(
                "GET",
                target,
                headers=dict(headers),
                timeout=u.Timeout(connect=self._connect_timeout_s, read=self._read_timeout_s),
                retries=False,
                redirect=False,
                preload_content=False,
            )
            answered: Mapping[str, str] = {
                key.lower(): str(value) for key, value in response.headers.items()
            }
            if answered.get("content-encoding", "identity").lower() != "identity":
                raise ToolCallFailed(
                    "compressed response refused",
                    reason="content_encoding",
                    delivery=Delivery.RESPONDED,
                )
            body = bytearray()
            while len(body) <= max_bytes:
                chunk = response.read(min(65_536, max_bytes + 1 - len(body)), decode_content=False)
                if not chunk:
                    break
                body.extend(chunk)
            return FetchedResponse(
                status=int(response.status),
                headers=answered,
                body=bytes(body[:max_bytes]),
                truncated=len(body) > max_bytes,
                provider_request_id=answered.get("x-request-id"),
            )
        except ToolCallFailed:
            raise
        except (u.exceptions.ConnectTimeoutError, u.exceptions.NewConnectionError) as exc:
            raise ToolCallFailed(
                str(exc), reason="connect_failed", delivery=Delivery.NOT_SENT
            ) from exc
        except u.exceptions.SSLError as exc:
            delivery = Delivery.NOT_SENT if _certificate_refused(exc) else Delivery.UNKNOWN
            raise ToolCallFailed(str(exc), reason="tls_failed", delivery=delivery) from exc
        except u.exceptions.HTTPError as exc:
            raise ToolCallFailed(
                str(exc), reason="transport_failed", delivery=Delivery.UNKNOWN
            ) from exc
        finally:
            if response is not None:
                response.release_conn()
            pool.close()


class PinnedHttpsTransport:
    """One HTTPS request to the checked IP, with the URL host as TLS authority."""

    def __init__(
        self,
        *,
        connect_timeout_s: float = 8.0,
        read_timeout_s: float = 20.0,
        wire: HttpsWire | None = None,
    ) -> None:
        self._wire = wire or UrllibWire(
            connect_timeout_s=connect_timeout_s, read_timeout_s=read_timeout_s
        )

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        host = check_url(url)
        if host != SEARCH_HOST:
            raise FetchRefused(
                "this public route only fetches Czech Wikipedia", reason="host_scope"
            )
        check_address(address)
        parts = urlsplit(url)
        if parts.scheme != "https":
            raise FetchRefused("live retrieval requires HTTPS", reason="https_only")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        return self._wire.get(
            address=address,
            host=host,
            target=_target(url),
            headers={
                "Host": host,
                "User-Agent": USER_AGENT,
                "Accept": "text/html, text/plain, application/json",
                "Accept-Encoding": "identity",
            },
            max_bytes=max_bytes,
        )


# --------------------------------------------------------------------------- #
# Any public host, politely
# --------------------------------------------------------------------------- #

_CONTACT: Final = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
#: RFC 9309 § 2.3.1.2: a crawler should follow at least five redirects for robots.txt.
MAX_ROBOTS_REDIRECTS: Final = 5


def public_user_agent(contact: str) -> str:
    """``AIA-research/1 (+mailto:<contact>)``: who is asking, and how to reach them."""
    if not _CONTACT.match(contact) or len(contact) > 254:
        raise ValueError("the public-web contact must be one plain e-mail address")
    return f"{AGENT_TOKEN}/1 (+mailto:{contact})"


@dataclass(frozen=True, slots=True)
class _KnownRobots:
    policy: RobotsPolicy
    #: ``monotonic()`` when it was read; it is asked again after the TTL.
    read_at: float


class PublicHttpsTransport:
    """GET any public host's page, after its robots.txt, at its pace, from the checked IP.

    For each request, in order: the URL must pass ``check_url`` and be ``https``;
    the address must be public (``WebFetcher`` resolved and checked it, and checks
    every redirect hop the same way); then, holding the host's lock (one request at
    a time per host), the host's robots.txt is read if this transport does not hold
    a fresh copy, the URL is refused if it forbids it (``robots_disallowed``, or
    ``robots_unavailable`` when it could not be read) or if its crawl delay exceeds
    ``max_crawl_delay_s`` (``robots_crawl_delay``), and the request waits until the
    host's interval -- the larger of ``min_interval_s`` and the crawl delay -- has
    passed since the last request to it. The robots.txt request is a request too:
    it is paced the same way and capped at ``MAX_ROBOTS_BYTES``.

    robots.txt is read once per host for as long as this transport holds it
    (``robots_ttl_s``, 24 hours by default, RFC 9309 § 2.4). A composition builds
    one transport per run, so it is read once per host per run.

    ``contact`` is required: it is the address a site operator writes to, carried
    in every request's user agent. The clock and the sleep are injectable.
    """

    def __init__(
        self,
        *,
        contact: str,
        resolver: Resolver,
        wire: HttpsWire | None = None,
        connect_timeout_s: float = 8.0,
        read_timeout_s: float = 20.0,
        min_interval_s: float = 1.0,
        max_crawl_delay_s: float = 30.0,
        robots_ttl_s: float = 86_400.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 0 <= min_interval_s <= max_crawl_delay_s:
            raise ValueError("the minimum interval is between zero and the longest crawl delay")
        if robots_ttl_s <= 0:
            raise ValueError("a robots.txt is held for a positive time")
        self.user_agent = public_user_agent(contact)
        self._resolver = resolver
        self._wire = wire or UrllibWire(
            connect_timeout_s=connect_timeout_s, read_timeout_s=read_timeout_s
        )
        self._min_interval_s = min_interval_s
        self._max_crawl_delay_s = max_crawl_delay_s
        self._robots_ttl_s = robots_ttl_s
        self._monotonic = monotonic
        self._sleep = sleep
        self._guard = threading.Lock()
        self._host_locks: dict[str, threading.Lock] = {}
        self._robots: dict[str, _KnownRobots] = {}
        self._last_request: dict[str, float] = {}

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    # ------------------------------------------------------------------ policy --

    def _held(self, host: str) -> RobotsPolicy | None:
        with self._guard:
            known = self._robots.get(host)
        if known is None or self._monotonic() - known.read_at >= self._robots_ttl_s:
            return None
        return known.policy

    def _refusal(self, policy: RobotsPolicy, url: str) -> str | None:
        reason = policy.refusal(url)
        if reason is None and (policy.crawl_delay_s or 0.0) > self._max_crawl_delay_s:
            reason = "robots_crawl_delay"
        return reason

    def known_refusal(self, url: str) -> str | None:
        """Why ``url`` would be refused by a robots.txt already held; None if not known.

        Sends nothing. The gate asks first, so a URL refused by a policy it has
        already read is journaled as refused before any dispatch.
        """
        try:
            host = check_url(url)
        except FetchRefused as exc:
            return exc.reason
        policy = self._held(host)
        return None if policy is None else self._refusal(policy, url)

    def known_sitemaps(self, host: str) -> tuple[str, ...] | None:
        """The ``Sitemap:`` URLs of ``host``'s robots.txt, if this transport holds it.

        None when it has not been read (or is stale); sends nothing. A host whose
        robots.txt could not be read or forbids everything declares none.
        """
        policy = self._held(host.lower().rstrip("."))
        return None if policy is None else policy.sitemaps

    def _host_lock(self, host: str) -> threading.Lock:
        with self._guard:
            return self._host_locks.setdefault(host, threading.Lock())

    def _paced(
        self, host: str, interval_s: float, send: Callable[[], FetchedResponse]
    ) -> FetchedResponse:
        """Send once ``interval_s`` has passed since the host's last request (lock held)."""
        last = self._last_request.get(host)
        if last is not None:
            wait = last + interval_s - self._monotonic()
            if wait > 0:
                self._sleep(wait)
        try:
            return send()
        finally:
            self._last_request[host] = self._monotonic()

    def _send(
        self, url: str, *, host: str, address: str, max_bytes: int, accept: str
    ) -> FetchedResponse:
        return self._wire.get(
            address=address,
            host=host,
            target=_target(url),
            headers={
                "Host": host,
                "User-Agent": self.user_agent,
                "Accept": accept,
                "Accept-Encoding": "identity",
            },
            max_bytes=max_bytes,
        )

    def _read_robots(self, host: str, address: str) -> RobotsPolicy:
        """The host's robots.txt as a policy; an answer that cannot be read disallows all.

        Called with the host's lock held. Redirects are followed (at most
        :data:`MAX_ROBOTS_REDIRECTS`, https only, every hop's host resolved and
        checked like a page's); the rules found apply to ``host``.
        """
        url = f"https://{host}/robots.txt"
        hop_host, hop_address = host, address
        try:
            for _hop in range(MAX_ROBOTS_REDIRECTS + 1):
                response = self._paced(
                    hop_host,
                    self._min_interval_s,
                    partial(
                        self._send,
                        url,
                        host=hop_host,
                        address=hop_address,
                        max_bytes=MAX_ROBOTS_BYTES,
                        accept="text/plain",
                    ),
                )
                location = {k.lower(): v for k, v in response.headers.items()}.get("location")
                if response.status not in (301, 302, 303, 307, 308):
                    return policy_for_response(response.status, response.body)
                if not location:
                    return RobotsPolicy.unavailable("redirect_invalid")
                url = urljoin(url, location)
                if urlsplit(url).scheme != "https":
                    return RobotsPolicy.unavailable("https_only")
                next_host = check_url(url)
                if next_host != hop_host:
                    addresses = self._resolver.resolve(next_host)
                    check_resolution(next_host, addresses)
                    hop_host, hop_address = next_host, addresses[0]
            return RobotsPolicy.unavailable("too_many_redirects")
        except (ToolCallFailed, FetchRefused) as exc:
            # Unreachable (RFC 9309 2.3.1.4): nothing on the host is requested.
            return RobotsPolicy.unavailable(exc.reason)

    def _policy(self, host: str, address: str) -> RobotsPolicy:
        policy = self._held(host)
        if policy is None:
            policy = self._read_robots(host, address)
            with self._guard:
                self._robots[host] = _KnownRobots(policy, self._monotonic())
        return policy

    # ----------------------------------------------------------------- request --

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        host = check_url(url)
        if urlsplit(url).scheme != "https":
            raise FetchRefused("live retrieval requires HTTPS", reason="https_only")
        check_address(address)
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        with self._host_lock(host):
            policy = self._policy(host, address)
            reason = self._refusal(policy, url)
            if reason is not None:
                raise FetchRefused(
                    f"{host}'s robots.txt does not let {AGENT_TOKEN} request this URL"
                    f" ({policy.state.value}: {policy.detail})",
                    reason=reason,
                )
            interval = max(self._min_interval_s, policy.crawl_delay_s or 0.0)
            response: FetchedResponse = self._paced(
                host,
                interval,
                lambda: self._send(
                    url,
                    host=host,
                    address=address,
                    max_bytes=max_bytes,
                    accept=PAGE_ACCEPT,
                ),
            )
            return response


class WikipediaSearch:
    """One bounded MediaWiki search in Czech Wikipedia's article namespace."""

    adapter_id: Final = SEARCH_ID

    def __init__(self, *, resolver: Resolver, transport: FetchTransport) -> None:
        if transport.retrieval_mode is not RetrievalMode.LIVE:
            raise ValueError("live Wikipedia search requires a live transport")
        self._resolver = resolver
        self._transport = transport

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def search(self, query: str, *, max_results: int) -> SearchResponse:
        if not 1 <= max_results <= 8 or not query.strip() or len(query.encode()) > 512:
            raise ToolCallFailed(
                "search query or result limit is outside the public route",
                reason="search_bounds",
                delivery=Delivery.NOT_SENT,
            )
        # The adapter contract is ToolCallFailed: the gate has already journaled this
        # call as dispatched, and a FetchRefused would escape it with the call open
        # and its reservation held. Every refusal here happens before a byte is sent.
        try:
            host = check_url(SEARCH_ENDPOINT)
            addresses = self._resolver.resolve(host)
            check_resolution(host, addresses)
        except FetchRefused as exc:
            raise ToolCallFailed(
                "the Wikipedia search host was refused before sending",
                reason=exc.reason,
                delivery=Delivery.NOT_SENT,
            ) from exc
        params = urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srnamespace": "0",
                "srlimit": str(max_results),
                "format": "json",
                "formatversion": "2",
                "utf8": "1",
                "maxlag": "5",
            }
        )
        try:
            response = self._transport.get(
                f"{SEARCH_ENDPOINT}?{params}", address=addresses[0], max_bytes=MAX_SEARCH_BYTES
            )
        except FetchRefused as exc:
            # The transport refuses a URL or address only before it connects.
            raise ToolCallFailed(
                "the Wikipedia search request was refused before sending",
                reason=exc.reason,
                delivery=Delivery.NOT_SENT,
            ) from exc
        if response.truncated:
            raise ToolCallFailed(
                "search response too large", reason="search_body", delivery=Delivery.RESPONDED
            )
        if response.status != 200:
            raise ToolCallFailed(
                f"Wikipedia HTTP {response.status}",
                reason=f"search_http_{response.status}",
                delivery=Delivery.RESPONDED,
            )
        media = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if media != "application/json":
            raise ToolCallFailed(
                "search response is not JSON", reason="search_type", delivery=Delivery.RESPONDED
            )
        try:
            payload = json.loads(response.body)
            if "error" in payload:
                raise ValueError("MediaWiki reported an error")
            entries = payload["query"]["search"]
            if not isinstance(entries, list):
                raise ValueError("search is not a list")
            hits: list[SearchHit] = []
            for entry in entries[:max_results]:
                title = entry["title"]
                if not isinstance(title, str) or not title.strip() or len(title) > 500:
                    raise ValueError("invalid title")
                snippet = entry.get("snippet", "")
                if not isinstance(snippet, str):
                    raise ValueError("invalid snippet")
                url = f"https://{SEARCH_HOST}/wiki/{quote(title.replace(' ', '_'), safe='()')}"
                hits.append(
                    SearchHit(
                        url=url,
                        title=title,
                        snippet=extract_page(snippet[:2000], "text/html")[1][:1000],
                        rank=len(hits) + 1,
                    )
                )
        except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
            raise ToolCallFailed(
                "invalid Wikipedia search response",
                reason="search_contract",
                delivery=Delivery.RESPONDED,
            ) from exc
        return SearchResponse(tuple(hits), response.provider_request_id, credits=0)
