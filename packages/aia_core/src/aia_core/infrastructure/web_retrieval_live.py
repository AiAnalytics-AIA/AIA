"""Bounded public Wikipedia retrieval with a checked-IP HTTPS transport.

:class:`HostPinnedHttpsTransport` is the transport, scoped to one host; the dataset
connectors (``dataset_connectors``) use it for their own hosts.
Search is fixed to Czech Wikipedia's public article namespace. Fetches connect to
the exact globally routable IP checked by ``WebFetcher`` while TLS verifies the
original host. Neither path follows redirects, retries, uses a proxy, or sends
credentials. Pages are still untrusted evidence candidates, never instructions.
"""

from __future__ import annotations

import json
import socket
from collections.abc import Mapping
from typing import Any, Final
from urllib.parse import quote, urlencode, urlsplit

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.web import (
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

__all__ = ["HostPinnedHttpsTransport", "PinnedHttpsTransport", "SystemResolver", "WikipediaSearch"]

SEARCH_ID: Final = "wikipedia-cs-search-1"
SEARCH_HOST: Final = "cs.wikipedia.org"
SEARCH_ENDPOINT: Final = f"https://{SEARCH_HOST}/w/api.php"
USER_AGENT: Final = "AIAResearch/0.1 (https://aia-develop.art-chain.io/)"
MAX_SEARCH_BYTES: Final = 128_000


class SystemResolver:
    """Resolve every address; the caller rejects a mixed public/private answer."""

    def resolve(self, host: str) -> tuple[str, ...]:
        try:
            answers = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except OSError:
            return ()
        return tuple(dict.fromkeys(str(answer[4][0]) for answer in answers))


class HostPinnedHttpsTransport:
    """One HTTPS request to the checked IP of one allowed host, the host as TLS authority.

    Scoped to a single host fixed at construction: a URL on any other host is refused
    before a connection is opened. No proxy (the pool connects to the address itself),
    no redirect followed, no retry, no cookie or credential, an identity encoding only,
    and the body read to ``max_bytes`` and no further. Error messages are fixed text:
    a provider's or a library's message can carry the request URL, and the URL
    carries the query.
    """

    def __init__(
        self,
        *,
        host: str,
        accept: str,
        connect_timeout_s: float = 8.0,
        read_timeout_s: float = 20.0,
    ) -> None:
        import urllib3

        if check_url(f"https://{host}/") != host:
            raise ValueError("a pinned transport is scoped to one plain host name")
        self._urllib3 = urllib3
        self._host = host
        self._accept = accept
        self._connect_timeout_s = connect_timeout_s
        self._read_timeout_s = read_timeout_s

    @property
    def host(self) -> str:
        return self._host

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        host = check_url(url)
        if host != self._host:
            raise FetchRefused(f"this route only fetches {self._host}", reason="host_scope")
        check_address(address)
        parts = urlsplit(url)
        if parts.scheme != "https":
            raise FetchRefused("live retrieval requires HTTPS", reason="https_only")
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
                (parts.path or "/") + (f"?{parts.query}" if parts.query else ""),
                headers={
                    "Host": host,
                    "User-Agent": USER_AGENT,
                    "Accept": self._accept,
                    "Accept-Encoding": "identity",
                },
                timeout=u.Timeout(connect=self._connect_timeout_s, read=self._read_timeout_s),
                retries=False,
                redirect=False,
                preload_content=False,
            )
            headers: Mapping[str, str] = {
                key.lower(): str(value) for key, value in response.headers.items()
            }
            if headers.get("content-encoding", "identity").lower() != "identity":
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
                headers=headers,
                body=bytes(body[:max_bytes]),
                truncated=len(body) > max_bytes,
                provider_request_id=headers.get("x-request-id"),
            )
        except ToolCallFailed:
            raise
        except (u.exceptions.ConnectTimeoutError, u.exceptions.NewConnectionError) as exc:
            raise ToolCallFailed(
                "the connection was not established",
                reason="connect_failed",
                delivery=Delivery.NOT_SENT,
            ) from exc
        except u.exceptions.SSLError as exc:
            delivery = Delivery.NOT_SENT if _certificate_refused(exc) else Delivery.UNKNOWN
            raise ToolCallFailed(
                "the TLS session failed", reason="tls_failed", delivery=delivery
            ) from exc
        except u.exceptions.HTTPError as exc:
            raise ToolCallFailed(
                "the request failed after it was sent",
                reason="transport_failed",
                delivery=Delivery.UNKNOWN,
            ) from exc
        finally:
            if response is not None:
                response.release_conn()
            pool.close()


class PinnedHttpsTransport(HostPinnedHttpsTransport):
    """The pinned transport scoped to Czech Wikipedia, the public route's one host."""

    def __init__(self, *, connect_timeout_s: float = 8.0, read_timeout_s: float = 20.0) -> None:
        super().__init__(
            host=SEARCH_HOST,
            accept="text/html, text/plain, application/json",
            connect_timeout_s=connect_timeout_s,
            read_timeout_s=read_timeout_s,
        )


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
        host = check_url(SEARCH_ENDPOINT)
        addresses = self._resolver.resolve(host)
        check_resolution(host, addresses)
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
        response = self._transport.get(
            f"{SEARCH_ENDPOINT}?{params}", address=addresses[0], max_bytes=MAX_SEARCH_BYTES
        )
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
