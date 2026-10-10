"""Brave Web Search: the live, metered search adapter for Class C Deep Research.

One adapter, one route, one host. :class:`BraveSearch` turns a query into one
HTTPS ``GET`` to ``api.search.brave.com/res/v1/web/search`` and the answer into
:class:`~aia_core.domain.deep_research.web.SearchHit` pointers. Like every adapter
under ``aia_core.application.web_retrieval.RetrievalGate`` it translates and never
decides: no retry, no fallback, no second request. The gate has already
classified, authorised, reserved and journaled the call before :meth:`search`
runs, so every failure is a :class:`ToolCallFailed` stating its
:class:`~aia_core.domain.ai_contracts.Delivery`:

* ``NOT_SENT`` -- nothing left: bounds refused, no credential, the host did not
  resolve to public addresses, the connection was never made.
* ``RESPONDED`` -- Brave answered and refused or the answer is unusable: a bad
  key (401/403), bad parameters (400/422), a rate limit (429), a body that is not
  the documented JSON. The outcome is known.
* ``UNKNOWN`` -- the request may have been processed and no usable answer came: a
  read timeout, a reset, a 5xx. Closed uncertain by the gate, never resent.

The subscription key is held as a *credential reference*
(:class:`~aia_core.infrastructure.model_adapters.transport.CredentialSource`),
by default :data:`BRAVE_CREDENTIAL_REF`, which ``EnvironmentCredentials`` reads
from ``AIA_DEEP_RESEARCH_BRAVE_API_KEY``. It is resolved for each request, before
anything is looked up or sent, and placed only in the ``X-Subscription-Token``
header handed to the transport. No message, repr or exception this module raises
carries it: every failure message is a fixed sentence, never the text of an
underlying exception.

The transport, :class:`BraveHttpsTransport`, follows the pinned-IP pattern of
``web_retrieval_live.PinnedHttpsTransport``: it connects to the checked address,
verifies TLS against the API host, sends no proxy, follows no redirect, and caps
the body. It is scoped to ``api.search.brave.com`` alone.

``filetype:`` is not offered: Brave's support for it is not established (plan
chunk 3), and a query carrying it is refused before anything is sent.

Not registered by any composition: the route, its settings and its key's
deployment are plan chunk 23.
"""

from __future__ import annotations

import json
import re
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Final, Protocol
from urllib.parse import urlencode, urlsplit

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
from .model_adapters.transport import CredentialSource
from .web_retrieval import FetchedResponse, Resolver, SearchResponse, ToolCallFailed, extract_page

__all__ = [
    "BRAVE_API_HOST",
    "BRAVE_CREDENTIAL_REF",
    "BRAVE_ENDPOINT",
    "BRAVE_SEARCH_ID",
    "MAX_BRAVE_COUNT",
    "BraveHttpsTransport",
    "BraveQuery",
    "BraveSearch",
    "BraveTransport",
    "check_freshness",
]

BRAVE_SEARCH_ID: Final = "brave-web-search-2"
#: Where a deployment keeps the subscription key: the reference, never the key.
BRAVE_CREDENTIAL_REF: Final = "env:AIA_DEEP_RESEARCH_BRAVE_API_KEY"
BRAVE_API_HOST: Final = "api.search.brave.com"
BRAVE_ENDPOINT: Final = f"https://{BRAVE_API_HOST}/res/v1/web/search"
#: Brave's largest ``count`` for web results.
MAX_BRAVE_COUNT: Final = 20
#: Brave's documented query bounds (characters, words).
MAX_QUERY_CHARS: Final = 400
MAX_QUERY_WORDS: Final = 50
MAX_RESPONSE_BYTES: Final = 512_000
MAX_TITLE_CHARS: Final = 500
MAX_SNIPPET_CHARS: Final = 1000
LANGUAGES: Final = frozenset({"cs", "en"})
# Brave does not list CZ among its supported search regions. Global coverage
# retains Czech/English language filtering without sending an invalid country.
# https://api-dashboard.search.brave.com/api-reference/web/search/get
COUNTRY: Final = "ALL"
USER_AGENT: Final = "AIAResearch/0.1 (https://aia-develop.art-chain.io/)"

_FRESHNESS_WORD: Final = frozenset({"pd", "pw", "pm", "py"})
_FRESHNESS_RANGE: Final = re.compile(r"(\d{4}-\d{2}-\d{2})to(\d{4}-\d{2}-\d{2})")
#: A bare DNS host: labels of letters, digits and hyphens, at least one dot.
_HOST: Final = re.compile(
    r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?"
)
#: Operators not offered: support unverified (``filetype:``, ``ext:``).
_UNOFFERED_OPERATOR: Final = re.compile(r"(?:^|\s|-)(?:filetype|ext):", re.IGNORECASE)


def _not_sent(message: str, reason: str) -> ToolCallFailed:
    return ToolCallFailed(message, reason=reason, delivery=Delivery.NOT_SENT)


def check_freshness(value: str) -> str:
    """``pd``/``pw``/``pm``/``py`` or ``YYYY-MM-DDtoYYYY-MM-DD`` (start <= end), else ValueError."""
    if value in _FRESHNESS_WORD:
        return value
    match = _FRESHNESS_RANGE.fullmatch(value)
    if match is None:
        raise ValueError("freshness must be pd, pw, pm, py or YYYY-MM-DDtoYYYY-MM-DD")
    start, end = date.fromisoformat(match[1]), date.fromisoformat(match[2])
    if start > end:
        raise ValueError("a freshness range must not end before it starts")
    return value


def _check_text(text: str) -> None:
    if _UNOFFERED_OPERATOR.search(text):
        raise ValueError("the filetype: operator is not offered")
    if any(ch in text for ch in "\r\n\t\x00"):
        raise ValueError("a query is one line of text")


@dataclass(frozen=True, slots=True)
class BraveQuery:
    """One search, built from typed parts.

    ``site`` and ``phrase`` become Brave's query operators (``site:host``,
    ``"exact phrase"``) inside ``q``; ``lang`` and ``freshness`` are request
    parameters. Everything is validated here, before a gate sees the text.
    """

    text: str
    site: str | None = None
    phrase: str | None = None
    lang: str = "cs"
    freshness: str | None = None

    def __post_init__(self) -> None:
        _check_text(self.text)
        if self.site is not None:
            site = self.site
            if site != site.strip().lower() or not _HOST.fullmatch(site):
                raise ValueError("site must be a bare lower-case host, without scheme or path")
            try:
                check_url(f"https://{site}/")
            except FetchRefused as exc:
                raise ValueError("site must name a public host") from exc
        if self.phrase is not None:
            if not self.phrase.strip() or '"' in self.phrase:
                raise ValueError("a phrase is non-empty text without double quotes")
            _check_text(self.phrase)
        if self.lang not in LANGUAGES:
            raise ValueError(f"lang must be one of {sorted(LANGUAGES)}")
        if self.freshness is not None:
            check_freshness(self.freshness)
        if not self.q:
            raise ValueError("a query needs text or a phrase")

    @property
    def q(self) -> str:
        """The ``q`` parameter: the text, then the phrase, then the site operator."""
        parts = [" ".join(self.text.split())]
        if self.phrase is not None:
            parts.append(f'"{" ".join(self.phrase.split())}"')
        if self.site is not None:
            parts.append(f"site:{self.site}")
        return " ".join(p for p in parts if p)


class BraveTransport(Protocol):
    """One GET to the Brave API host from a checked address, with the given headers."""

    @property
    def retrieval_mode(self) -> RetrievalMode: ...

    def get(
        self, url: str, *, address: str, max_bytes: int, headers: Mapping[str, str]
    ) -> FetchedResponse:
        """GET ``url`` from ``address``; no redirects; at most ``max_bytes``. Or ToolCallFailed."""
        ...


class BraveSearch:
    """Brave Web Search, ``country=ALL``, strict safe search, web results only."""

    adapter_id: Final = BRAVE_SEARCH_ID

    def __init__(
        self,
        *,
        credentials: CredentialSource,
        credential_ref: str = BRAVE_CREDENTIAL_REF,
        resolver: Resolver,
        transport: BraveTransport,
        lang: str = "cs",
        freshness: str | None = None,
    ) -> None:
        if transport.retrieval_mode is not RetrievalMode.LIVE:
            raise ValueError("live Brave search requires a live transport")
        if lang not in LANGUAGES:
            raise ValueError(f"lang must be one of {sorted(LANGUAGES)}")
        if freshness is not None:
            check_freshness(freshness)
        self._credentials = credentials
        self.credential_ref = credential_ref
        self._resolver = resolver
        self._transport = transport
        self._lang = lang
        self._freshness = freshness

    def __repr__(self) -> str:
        return f"BraveSearch(credential_ref={self.credential_ref!r}, lang={self._lang!r})"

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def search(self, query: str, *, max_results: int) -> SearchResponse:
        """The protocol's call: ``query`` is ``q``; language and freshness are this adapter's."""
        try:
            _check_text(query)
        except ValueError as exc:
            raise _not_sent(str(exc), "search_operator") from exc
        return self._send(
            " ".join(query.split()),
            lang=self._lang,
            freshness=self._freshness,
            max_results=max_results,
        )

    def search_in(self, query: str, *, lang: str, max_results: int) -> SearchResponse:
        """``LanguageSearch``: ``query`` is ``q`` (site and phrase already in it), in ``lang``."""
        try:
            _check_text(query)
            if lang not in LANGUAGES:
                raise ValueError(f"lang must be one of {sorted(LANGUAGES)}")
        except ValueError as exc:
            raise _not_sent(str(exc), "search_operator") from exc
        return self._send(
            " ".join(query.split()), lang=lang, freshness=self._freshness, max_results=max_results
        )

    def search_query(self, query: BraveQuery, *, max_results: int) -> SearchResponse:
        """A typed query, with its own language and freshness."""
        return self._send(
            query.q, lang=query.lang, freshness=query.freshness, max_results=max_results
        )

    # ------------------------------------------------------------------ call --

    def _send(
        self, q: str, *, lang: str, freshness: str | None, max_results: int
    ) -> SearchResponse:
        if max_results < 1 or not q or len(q) > MAX_QUERY_CHARS or len(q.split()) > MAX_QUERY_WORDS:
            raise _not_sent("search query or result limit is outside the route", "search_bounds")
        count = min(max_results, MAX_BRAVE_COUNT)
        params: dict[str, str] = {
            "q": q,
            "country": COUNTRY,
            "search_lang": lang,
            "count": str(count),
            "safesearch": "strict",
            "result_filter": "web",
        }
        if freshness is not None:
            params["freshness"] = freshness
        # The key: resolved per call, fail closed before any address is looked up.
        try:
            key = self._credentials.secret(self.credential_ref)
        except KeyError:
            key = ""
        if not key.strip():
            raise _not_sent(
                f"no credential configured for {self.credential_ref!r}", "missing_credential"
            )
        try:
            host = check_url(BRAVE_ENDPOINT)
            addresses = self._resolver.resolve(host)
            check_resolution(host, addresses)
        except FetchRefused as exc:
            raise _not_sent(
                "the Brave API host did not resolve to public addresses", exc.reason
            ) from exc
        response = self._transport.get(
            f"{BRAVE_ENDPOINT}?{urlencode(params)}",
            address=addresses[0],
            max_bytes=MAX_RESPONSE_BYTES,
            headers={"Accept": "application/json", "X-Subscription-Token": key},
        )
        return _parse(response, count=count)


def _answered(message: str, reason: str) -> ToolCallFailed:
    return ToolCallFailed(message, reason=reason, delivery=Delivery.RESPONDED)


def _status_failure(status: int) -> ToolCallFailed:
    if status in (401, 403):
        return _answered(f"Brave refused the credential (HTTP {status})", "bad_credential")
    if status == 429:
        return _answered("Brave rate limit reached (HTTP 429)", "rate_limited")
    if status in (400, 422):
        return _answered(f"Brave refused the parameters (HTTP {status})", "bad_request")
    if 500 <= status < 600:
        return ToolCallFailed(
            f"Brave server error (HTTP {status})",
            reason="provider_error",
            delivery=Delivery.UNKNOWN,
        )
    return _answered(f"Brave answered HTTP {status}", f"http_{status}")


def _text(value: Any, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("a title or description is not text")
    return extract_page(value[: limit * 4], "text/html")[1][:limit]


def _parse(response: FetchedResponse, *, count: int) -> SearchResponse:
    if response.status != 200:
        raise _status_failure(response.status)
    if response.truncated:
        raise _answered("the Brave response is larger than the cap", "response_too_large")
    media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media != "application/json":
        raise _answered("the Brave response is not JSON", "provider_error")
    try:
        payload = json.loads(response.body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("the response is not an object")
        web = payload.get("web")
        results: Any = [] if web is None else web.get("results", [])
        if not isinstance(results, list):
            raise ValueError("web.results is not a list")
        hits: list[SearchHit] = []
        dropped = 0
        for position, entry in enumerate(results[:count], 1):
            url = entry.get("url") if isinstance(entry, dict) else None
            if not isinstance(url, str):
                dropped += 1
                continue
            try:
                check_url(url)
            except FetchRefused:
                dropped += 1
                continue
            hits.append(
                SearchHit(
                    url=url,
                    title=_text(entry.get("title"), MAX_TITLE_CHARS),
                    snippet=_text(entry.get("description"), MAX_SNIPPET_CHARS),
                    rank=position,
                )
            )
    except (UnicodeDecodeError, ValueError, AttributeError, TypeError) as exc:
        raise _answered("invalid Brave search response", "provider_error") from exc
    return SearchResponse(
        hits=tuple(hits),
        provider_request_id=response.provider_request_id,
        credits=1,
        dropped=dropped,
    )


# --------------------------------------------------------------------------- #
# Transport
# --------------------------------------------------------------------------- #


def _decoded(body: bytes, encoding: str, max_bytes: int) -> tuple[bytes, bool]:
    """The body, gunzipped when the server compressed it anyway; capped at ``max_bytes``."""
    if encoding in ("", "identity"):
        return body[:max_bytes], len(body) > max_bytes
    if encoding not in ("gzip", "x-gzip"):
        raise _answered("the Brave response uses an unsupported encoding", "content_encoding")
    try:
        inflater = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
        plain = inflater.decompress(body, max_bytes + 1)
    except zlib.error as exc:
        raise _answered("the Brave response is not valid gzip", "provider_error") from exc
    return plain[:max_bytes], len(plain) > max_bytes or bool(inflater.unconsumed_tail)


class BraveHttpsTransport:
    """One HTTPS request to a checked IP of ``api.search.brave.com``, and nowhere else.

    The connection goes to the address the adapter checked; TLS verifies the API
    host. No proxy, no redirect, no retry; the (compressed) body is read up to the
    cap. Failure messages are fixed sentences: an underlying exception's text is
    never repeated, so nothing the request carried can surface in one.
    """

    def __init__(self, *, connect_timeout_s: float = 5.0, read_timeout_s: float = 15.0) -> None:
        import urllib3

        self._urllib3 = urllib3
        self._connect_timeout_s = connect_timeout_s
        self._read_timeout_s = read_timeout_s

    def __repr__(self) -> str:
        return f"BraveHttpsTransport(host={BRAVE_API_HOST!r})"

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def get(
        self, url: str, *, address: str, max_bytes: int, headers: Mapping[str, str]
    ) -> FetchedResponse:
        host = check_url(url)
        parts = urlsplit(url)
        if host != BRAVE_API_HOST or parts.scheme != "https":
            raise FetchRefused(
                "this route only reaches the Brave Search API over HTTPS", reason="host_scope"
            )
        check_address(address)
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
                    **headers,
                    "Host": host,
                    "User-Agent": USER_AGENT,
                    "Accept-Encoding": "identity",
                },
                timeout=u.Timeout(connect=self._connect_timeout_s, read=self._read_timeout_s),
                retries=False,
                redirect=False,
                preload_content=False,
            )
            answer: Mapping[str, str] = {
                key.lower(): str(value) for key, value in response.headers.items()
            }
            raw = bytearray()
            while len(raw) <= max_bytes:
                chunk = response.read(min(65_536, max_bytes + 1 - len(raw)), decode_content=False)
                if not chunk:
                    break
                raw.extend(chunk)
            body, truncated = _decoded(
                bytes(raw), answer.get("content-encoding", "identity").strip().lower(), max_bytes
            )
            return FetchedResponse(
                status=int(response.status),
                headers=answer,
                body=body,
                truncated=truncated or len(raw) > max_bytes,
                provider_request_id=answer.get("x-request-id") or None,
            )
        except ToolCallFailed:
            raise
        except u.exceptions.ConnectTimeoutError as exc:
            # NewConnectionError included: the connection was never made.
            raise _not_sent("could not connect to the Brave API", "connect_failed") from exc
        except u.exceptions.ReadTimeoutError as exc:
            raise ToolCallFailed(
                "the Brave API did not answer in time", reason="timeout", delivery=Delivery.UNKNOWN
            ) from exc
        except u.exceptions.SSLError as exc:
            delivery = Delivery.NOT_SENT if _certificate_refused(exc) else Delivery.UNKNOWN
            raise ToolCallFailed(
                "TLS with the Brave API failed", reason="tls_failed", delivery=delivery
            ) from exc
        except u.exceptions.ProtocolError as exc:
            raise ToolCallFailed(
                "the connection to the Brave API was reset",
                reason="reset",
                delivery=Delivery.UNKNOWN,
            ) from exc
        except u.exceptions.HTTPError as exc:
            raise ToolCallFailed(
                "the Brave API request failed", reason="transport_failed", delivery=Delivery.UNKNOWN
            ) from exc
        finally:
            if response is not None:
                response.release_conn()
            pool.close()
