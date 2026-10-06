"""Web search and fetch: the adapters under the retrieval gate, and their recorded doubles.

Everything here sits *under* ``aia_core.application.web_retrieval.RetrievalGate``,
which decides whether a query or a URL may leave at all, reserves and journals it.
Like the model adapters, the pieces here translate and enforce, and never decide
to retry, reroute or substitute:

* :class:`SearchAdapter` -- one search, one answer. The separately enabled live
  Wikipedia adapter is in :mod:`web_retrieval_live`; recorded search replays tests.
* :class:`WebFetcher` -- one page, fetched through a :class:`FetchTransport` after
  the address checks of ``domain.deep_research.web`` pass for the URL and for every
  address its host resolves to, **on every redirect hop**; then the type and that
  type's size cap; then HTML to text, normalised, and a content-addressed
  :class:`~aia_core.domain.deep_research.contracts.SourceSnapshot` that keeps the
  page's outbound and ``alternate`` links as data (never followed here). A PDF,
  XLSX or CSV is read by ``document_text.read_web_document`` into the same kind
  of snapshot, with the layout that maps its text back to pages or cells. A live
  transport must connect to the address that was checked (DNS rebinding).

Recorded doubles are test doubles (the model adapters keep theirs beside the
protocols too). They are never a production fallback: every adapter and transport
states its own :class:`~aia_core.domain.deep_research.contracts.RetrievalMode`, a
recorded one cannot say anything but ``RECORDED``, a route refuses an adapter of
the other mode, and ``make layer_check`` keeps the doubles out of every
composition but the local recorded one.
"""

from __future__ import annotations

import codecs
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Final, Protocol, runtime_checkable
from urllib.parse import urldefrag, urljoin

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import (
    ArchivedCapture,
    DocumentLayout,
    RetrievalMode,
    SnapshotLink,
    SourceSnapshot,
)
from ..domain.deep_research.documents import CapturedDocument, DocumentRefused
from ..domain.deep_research.grounding import detect_instructions, normalise_text
from ..domain.deep_research.legacy import canonical_url
from ..domain.deep_research.web import (
    DOCUMENT_MEDIA_TYPES,
    HOST_OUT_OF_SCOPE,
    MAX_ALTERNATE_LINKS,
    MAX_FETCH_BYTES,
    MAX_LINK_TEXT_CHARS,
    MAX_LINK_URL_CHARS,
    MAX_REDIRECTS,
    MAX_SNAPSHOT_LINKS,
    MAX_TEXT_CHARS,
    REDIRECT_OUT_OF_SCOPE,
    FetchRefused,
    SearchHit,
    check_content_type,
    check_resolution,
    check_url,
    max_body_bytes,
)
from .document_text import read_web_document

__all__ = [
    "FetchTransport",
    "FetchedPage",
    "FetchedResource",
    "FetchedResponse",
    "HostFilter",
    "PoliteTransport",
    "RecordedFetchTransport",
    "RecordedResolver",
    "RecordedSearch",
    "RecordedWeb",
    "Resolver",
    "SearchAdapter",
    "SearchResponse",
    "ToolCallFailed",
    "WebFetcher",
    "extract_links",
    "extract_page",
    "load_recorded_web",
    "page_snapshot",
]


class ToolCallFailed(Exception):
    """A search or fetch failed. ``delivery`` says whether it may have been served.

    ``NOT_SENT`` and ``RESPONDED`` are known outcomes; ``UNKNOWN`` is the lost
    answer that must never be treated as a free call.
    """

    def __init__(self, message: str, *, reason: str, delivery: Delivery) -> None:
        super().__init__(message)
        self.reason = reason
        self.delivery = delivery


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SearchResponse:
    hits: tuple[SearchHit, ...]
    provider_request_id: str | None
    #: The provider's own unit of charge for this call (a search credit).
    credits: int
    #: Results the provider returned that failed the URL policy and were dropped
    #: before they became hits. A journal can count them; they are never fetched.
    dropped: int = 0


class SearchAdapter(Protocol):
    """One search provider, over one route. Translates; never retries or reroutes."""

    @property
    def adapter_id(self) -> str: ...

    @property
    def retrieval_mode(self) -> RetrievalMode:
        """``RECORDED`` for a replay, ``LIVE`` for a provider. Fixed by the adapter."""
        ...

    def search(self, query: str, *, max_results: int) -> SearchResponse:
        """Run one query, or raise :class:`ToolCallFailed`."""
        ...


# --------------------------------------------------------------------------- #
# Fetch
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class FetchedResponse:
    """One HTTP answer, as a transport read it: no redirect followed."""

    status: int
    headers: Mapping[str, str]
    body: bytes
    #: The transport stopped reading at the byte cap.
    truncated: bool
    provider_request_id: str | None = None


class FetchTransport(Protocol):
    @property
    def retrieval_mode(self) -> RetrievalMode:
        """``RECORDED`` for a replay, ``LIVE`` for the network. Fixed by the transport."""
        ...

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        """GET ``url`` from ``address`` (already checked), at most ``max_bytes``, no redirects."""
        ...


@runtime_checkable
class PoliteTransport(Protocol):
    """A transport that obeys a host's robots.txt and can say so before it sends."""

    def known_refusal(self, url: str) -> str | None:
        """Why ``url`` would be refused by what the transport already knows; sends nothing."""
        ...

    def known_sitemaps(self, host: str) -> tuple[str, ...] | None:
        """The ``Sitemap:`` lines of a robots.txt already held for ``host``; sends nothing."""
        ...


class Resolver(Protocol):
    def resolve(self, host: str) -> tuple[str, ...]:
        """Every address ``host`` resolves to; empty when it does not resolve."""
        ...


_SKIP: Final = frozenset({"script", "style", "noscript", "template", "svg", "iframe", "object"})
_BLOCK: Final = frozenset(
    {
        "p", "div", "section", "article", "header", "footer", "main", "aside", "nav",
        "li", "ul", "ol", "table", "tr", "td", "th", "br", "hr", "blockquote", "pre",
        "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt", "figcaption",
    }
)  # fmt: skip
_DATE_META: Final = (
    "article:published_time",
    "og:published_time",
    "datepublished",
    "date",
    "dc.date",
    "dc.date.issued",
    "citation_publication_date",
    "pubdate",
)
_ISO_DATE: Final = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


class _Extractor(HTMLParser):
    """Visible text, the title, the page's own publication date and its links, from HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.dates: list[str] = []
        #: (href, anchor text parts) per ``<a href>``, in document order.
        self.anchors: list[tuple[str, list[str]]] = []
        #: (href, declared type, title) per ``<link rel="alternate">``.
        self.alternates: list[tuple[str, str, str]] = []
        self.base_href: str | None = None
        self._skip = 0
        self._in_title = False
        self._anchor: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k.lower(): (v or "") for k, v in attrs}
        if tag in _SKIP:
            self._skip += 1
        elif self._skip:
            pass
        elif tag == "a" and values.get("href"):
            self._anchor = []
            self.anchors.append((values["href"], self._anchor))
        elif tag == "base" and values.get("href") and self.base_href is None:
            self.base_href = values["href"]
        elif tag == "link" and values.get("href"):
            rel = set(values.get("rel", "").lower().split())
            if "alternate" in rel and "stylesheet" not in rel:
                self.alternates.append(
                    (values["href"], values.get("type", ""), values.get("title", ""))
                )
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = values.get("property") or values.get("name") or values.get("itemprop") or ""
            if name.lower() in _DATE_META and values.get("content"):
                self.dates.append(values["content"])
        elif tag == "time" and values.get("datetime"):
            self.dates.append(values["datetime"])
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "a":
            self._anchor = None
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title_parts.append(data)
        else:
            self.parts.append(data)
            if self._anchor is not None:
                self._anchor.append(data)


def _first_date(candidates: Sequence[str]) -> date | None:
    for raw in candidates:
        match = _ISO_DATE.search(raw)
        if match:
            try:
                return date(int(match[1]), int(match[2]), int(match[3]))
            except ValueError:
                continue
    return None


def _parse(body: str) -> _Extractor:
    parser = _Extractor()
    parser.feed(body)
    parser.close()
    return parser


def extract_page(body: str, media_type: str) -> tuple[str, str, date | None]:
    """(title, normalised visible text, the page's own publication date or None)."""
    if media_type == "text/plain":
        return "", normalise_text(body), None
    parser = _parse(body)
    title = normalise_text("".join(parser.title_parts))
    return title, normalise_text("".join(parser.parts)), _first_date(parser.dates)


_HREF_NOISE: Final = re.compile(r"[\t\n\r]")


def _absolute(base: str, href: str) -> str | None:
    """``href`` made absolute against ``base``, without its fragment, or None if unusable."""
    # Browsers strip whitespace around an href and drop tabs and newlines inside it.
    href = _HREF_NOISE.sub("", href.strip())
    if not href or href.startswith("#"):
        return None
    try:
        url = urldefrag(urljoin(base, href)).url
        check_url(url)
    except (ValueError, FetchRefused):
        return None
    return url if len(url) <= MAX_LINK_URL_CHARS else None


def _links(parser: _Extractor, page_url: str) -> tuple[SnapshotLink, ...]:
    base = page_url
    if parser.base_href is not None:
        declared = _absolute(page_url, parser.base_href)
        if declared is not None:
            base = declared
    anchors: dict[str, str] = {}
    for href, parts in parser.anchors:
        url = _absolute(base, href)
        if url is None:
            continue
        text = normalise_text("".join(parts))[:MAX_LINK_TEXT_CHARS]
        if url in anchors:
            # The first anchor with words names the link; an image link says nothing.
            anchors[url] = anchors[url] or text
        elif len(anchors) < MAX_SNAPSHOT_LINKS:
            anchors[url] = text
    alternates: dict[str, tuple[str, str]] = {}
    for href, media_type, title in parser.alternates:
        url = _absolute(base, href)
        if url is None or url in alternates or len(alternates) >= MAX_ALTERNATE_LINKS:
            continue
        alternates[url] = (
            normalise_text(media_type).lower()[:100],
            normalise_text(title)[:MAX_LINK_TEXT_CHARS],
        )
    kept = [SnapshotLink(kind="anchor", url=u, text=t) for u, t in anchors.items()]
    kept.extend(
        SnapshotLink(kind="alternate", url=u, text=t, media_type=m or None)
        for u, (m, t) in alternates.items()
    )
    return tuple(kept)


def extract_links(body: str, page_url: str) -> tuple[SnapshotLink, ...]:
    """An HTML page's links: absolute, fetchable, no fragment, deduplicated and capped.

    ``<a href>`` targets (at most :data:`MAX_SNAPSHOT_LINKS`, with their anchor
    text) then ``<link rel="alternate">`` targets (at most
    :data:`MAX_ALTERNATE_LINKS`, with their declared type), resolved against the
    page's ``<base href>`` when it declares a usable one. A link that fails
    ``check_url`` (another scheme, a port, credentials, an internal name, a private
    address) is dropped, as is one longer than :data:`MAX_LINK_URL_CHARS`. Nothing
    here opens a link.
    """
    return _links(_parse(body), page_url)


def _charset(content_type: str) -> str:
    match = re.search(r"charset=([\w.-]+)", content_type, re.I)
    return match[1] if match else "utf-8"


def _read_document(body: bytes, media: str, content_type: str) -> CapturedDocument:
    """A document's snapshot text and layout, or :class:`FetchRefused` with the reason."""
    try:
        return read_web_document(body, media, charset=_charset(content_type))
    except DocumentRefused as exc:
        raise FetchRefused(str(exc), reason=exc.reason) from exc


@dataclass(frozen=True, slots=True)
class FetchedPage:
    """A snapshot, and what scoring needs that the snapshot does not hold."""

    snapshot: SourceSnapshot
    published: date | None


#: Which hosts a fetch may reach, by host name: the caller's confinement (a crawl's host).
HostFilter = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class FetchedResource:
    """A bounded document fetched for what it lists, not for what it says: never evidence."""

    url: str
    final_url: str
    redirects: tuple[str, ...]
    media_type: str
    body: bytes
    raw_sha256: str
    request_id: str | None


def page_snapshot(
    *,
    url: str,
    final_url: str,
    redirects: tuple[str, ...],
    http_status: int,
    content_type: str,
    body: bytes,
    request_id: str | None,
    adapter_id: str,
    retrieval_mode: RetrievalMode,
    retrieved_at: datetime,
    archive: ArchivedCapture | None = None,
) -> FetchedPage:
    """A captured body as a snapshot: the one path every captured page takes.

    ``content_type`` is the declared header (its media type must be one
    ``check_content_type`` keeps, its charset decodes the body). A live fetch and
    an archived record both come through here, so their text, title, date and
    links are read by the same rules. A PDF, XLSX or CSV body is read as a
    document: its text and the layout that maps it back to pages or cells. An
    ``archive`` capture is stamped on the snapshot, and its id is derived from
    the record as well as the text: an archived copy is never the same snapshot
    as a live page with the same words.
    """
    media = check_content_type(content_type)
    links: tuple[SnapshotLink, ...] = ()
    layout: DocumentLayout | None = None
    published: date | None = None
    if media in DOCUMENT_MEDIA_TYPES:
        document = _read_document(body, media, content_type)
        title, kept, layout = document.title, document.text, document.layout
        truncated = document.truncated
    else:
        charset = _charset(content_type)
        try:
            codecs.lookup(charset)
        except LookupError as exc:
            # errors="replace" covers bad bytes, not an unknown codec: decoding with a
            # guessed charset would store text the page never said.
            raise FetchRefused(
                f"the declared charset {charset[:40]!r} is not one AIA can read",
                reason="charset_unknown",
            ) from exc
        decoded = body.decode(charset, errors="replace")
        if media == "text/plain":
            title, text, published = extract_page(decoded, media)
        else:
            parser = _parse(decoded)
            title = normalise_text("".join(parser.title_parts))
            text = normalise_text("".join(parser.parts))
            published = _first_date(parser.dates)
            links = _links(parser, final_url)
        kept = text[:MAX_TEXT_CHARS]
        truncated = len(text) > MAX_TEXT_CHARS
    text_sha = hashlib.sha256(kept.encode("utf-8")).hexdigest()
    address = text_sha
    if archive is not None:
        address = hashlib.sha256(
            "\n".join(
                (
                    "archive",
                    archive.archive,
                    archive.warc_filename,
                    str(archive.warc_record_offset),
                    str(archive.warc_record_length),
                    text_sha,
                )
            ).encode("utf-8")
        ).hexdigest()
    snapshot = SourceSnapshot(
        snapshot_id="SNP-" + address[:24],
        url=url,
        canonical_url=canonical_url(final_url) or final_url,
        final_url=final_url,
        redirects=redirects,
        title=title[:500],
        retrieved_at=retrieved_at,
        http_status=http_status,
        content_type=media,
        raw_sha256=hashlib.sha256(body).hexdigest(),
        raw_bytes=len(body),
        text=kept,
        text_sha256=text_sha,
        truncated=truncated,
        adapter=adapter_id,
        request_id=request_id,
        retrieval_mode=retrieval_mode,
        instructions_detected=detect_instructions(kept),
        links=links,
        document=layout,
        archive=archive,
    )
    return FetchedPage(snapshot=snapshot, published=published)


class WebFetcher:
    """Fetch one page under the address policy, following redirects by hand."""

    def __init__(
        self,
        *,
        transport: FetchTransport,
        resolver: Resolver,
        adapter_id: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transport = transport
        self._resolver = resolver
        self.adapter_id = adapter_id
        self._clock = clock

    @property
    def retrieval_mode(self) -> RetrievalMode:
        """The transport's mode, stamped on every snapshot this fetcher takes."""
        return self._transport.retrieval_mode

    def known_refusal(self, url: str) -> str | None:
        """Why ``url`` would be refused before any request, if the transport already knows.

        A transport that obeys robots.txt (:class:`PoliteTransport`) answers from
        the policies it holds; any other answers None. Sends nothing.
        """
        if isinstance(self._transport, PoliteTransport):
            return self._transport.known_refusal(url)
        return None

    def known_sitemaps(self, host: str) -> tuple[str, ...] | None:
        """The ``Sitemap:`` lines of ``host``'s robots.txt, if the transport already holds it.

        None when it is not known (not read yet, or a transport that reads no
        robots.txt). Sends nothing.
        """
        if isinstance(self._transport, PoliteTransport):
            return self._transport.known_sitemaps(host)
        return None

    def _follow(
        self, url: str, *, max_bytes: int, host_allowed: HostFilter | None
    ) -> tuple[str, list[str], FetchedResponse]:
        """GET ``url``, following redirects by hand: (final URL, hops, the 2xx answer).

        Every hop's URL and addresses are checked before it is requested, and, with
        ``host_allowed``, its host too: the first URL refused as
        ``host_out_of_scope``, a later hop as ``redirect_out_of_scope`` -- in both
        cases before anything is sent to that host.
        """
        redirects: list[str] = []
        current = url
        while True:
            host = check_url(current)
            if host_allowed is not None and not host_allowed(host):
                raise FetchRefused(
                    f"{host} is outside the hosts this fetch is confined to",
                    reason=REDIRECT_OUT_OF_SCOPE if redirects else HOST_OUT_OF_SCOPE,
                )
            addresses = self._resolver.resolve(host)
            check_resolution(host, addresses)
            response = self._transport.get(current, address=addresses[0], max_bytes=max_bytes)
            if response.status in (301, 302, 303, 307, 308):
                location = {k.lower(): v for k, v in response.headers.items()}.get("location")
                if not location:
                    raise FetchRefused("a redirect without a location", reason="redirect_invalid")
                if len(redirects) >= MAX_REDIRECTS:
                    raise FetchRefused(
                        f"more than {MAX_REDIRECTS} redirects", reason="too_many_redirects"
                    )
                redirects.append(current)
                current = urljoin(current, location)
                continue
            break
        if not 200 <= response.status < 300:
            raise ToolCallFailed(
                f"HTTP {response.status} for {current}",
                reason=f"http_{response.status}",
                delivery=Delivery.RESPONDED,
            )
        return current, redirects, response

    def fetch_resource(
        self,
        url: str,
        *,
        media_types: frozenset[str],
        max_bytes: int,
        host_allowed: HostFilter | None = None,
    ) -> FetchedResource:
        """A bounded document that is not evidence (a sitemap), as bytes. No snapshot.

        The same address, redirect and host checks as :meth:`fetch`; the declared
        media type must be one of ``media_types`` (``content_type``) and the body
        at most ``max_bytes`` (``body_too_large``, never cut). Raises FetchRefused
        or ToolCallFailed.
        """
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        current, redirects, response = self._follow(
            url, max_bytes=max_bytes, host_allowed=host_allowed
        )
        headers = {k.lower(): v for k, v in response.headers.items()}
        media = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media not in media_types:
            raise FetchRefused(
                f"content type {media or '(none)'!r} is not kept", reason="content_type"
            )
        if response.truncated:
            raise FetchRefused(
                f"the document is larger than {max_bytes} bytes", reason="body_too_large"
            )
        return FetchedResource(
            url=url,
            final_url=current,
            redirects=tuple(redirects),
            media_type=media,
            body=response.body,
            raw_sha256=hashlib.sha256(response.body).hexdigest(),
            request_id=response.provider_request_id,
        )

    def fetch(self, url: str, *, host_allowed: HostFilter | None = None) -> FetchedPage:
        """The page at ``url`` as a snapshot. Raises FetchRefused or ToolCallFailed.

        With ``host_allowed``, the URL and every redirect hop must be on a host it
        allows (:meth:`_follow`).
        """
        current, redirects, response = self._follow(
            url, max_bytes=MAX_FETCH_BYTES, host_allowed=host_allowed
        )
        headers = {k.lower(): v for k, v in response.headers.items()}
        content_type = headers.get("content-type", "")
        media = check_content_type(content_type)
        cap = max_body_bytes(media)
        if response.truncated or len(response.body) > cap:
            raise FetchRefused(
                f"the {media} body is larger than its cap of {cap} bytes", reason="body_too_large"
            )
        return page_snapshot(
            url=url,
            final_url=current,
            redirects=tuple(redirects),
            http_status=response.status,
            content_type=content_type,
            body=response.body,
            request_id=response.provider_request_id,
            adapter_id=self.adapter_id,
            retrieval_mode=self.retrieval_mode,
            retrieved_at=self._clock(),
        )


# --------------------------------------------------------------------------- #
# Recorded doubles
# --------------------------------------------------------------------------- #


def _query_key(query: str) -> str:
    return " ".join(query.casefold().split())


@dataclass(slots=True)
class RecordedSearch:
    """Replays captured search exchanges by query; an unrecorded query has no results.

    An exchange may record a failure: ``{"fail": "known" | "uncertain"}``.
    """

    adapter_id: str
    exchanges: Mapping[str, Mapping[str, Any]]
    calls: list[str] = field(default_factory=list)

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.RECORDED

    def search(self, query: str, *, max_results: int) -> SearchResponse:
        self.calls.append(query)
        exchange = self.exchanges.get(_query_key(query), {"hits": []})
        failure = exchange.get("fail")
        if failure == "uncertain":
            raise ToolCallFailed("recorded: no answer", reason="lost", delivery=Delivery.UNKNOWN)
        if failure == "known":
            raise ToolCallFailed(
                "recorded: provider error", reason="provider_error", delivery=Delivery.RESPONDED
            )
        hits = tuple(
            SearchHit(url=h["url"], title=h.get("title", ""), snippet=h.get("snippet", ""), rank=i)
            for i, h in enumerate(exchange.get("hits", []), 1)
        )
        return SearchResponse(
            hits=hits[:max_results],
            provider_request_id=exchange.get("request_id"),
            credits=int(exchange.get("credits", 1)),
        )


@dataclass(slots=True)
class RecordedFetchTransport:
    """Replays captured pages by URL; an unrecorded URL is a 404."""

    pages: Mapping[str, Mapping[str, Any]]
    calls: list[str] = field(default_factory=list)

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.RECORDED

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        self.calls.append(url)
        page = self.pages.get(url)
        if page is None:
            return FetchedResponse(status=404, headers={}, body=b"", truncated=False)
        if page.get("fail") == "uncertain":
            raise ToolCallFailed("recorded: reset", reason="reset", delivery=Delivery.UNKNOWN)
        body = str(page.get("body", "")).encode("utf-8")
        return FetchedResponse(
            status=int(page.get("status", 200)),
            headers=dict(page.get("headers", {"content-type": "text/html; charset=utf-8"})),
            body=body[:max_bytes],
            truncated=len(body) > max_bytes,
            provider_request_id=page.get("request_id"),
        )


@dataclass(slots=True)
class RecordedResolver:
    hosts: Mapping[str, Sequence[str]]

    def resolve(self, host: str) -> tuple[str, ...]:
        return tuple(self.hosts.get(host, ()))


@dataclass(slots=True)
class RecordedWeb:
    """One recorded exchange set: search, fetch and the resolver that goes with them."""

    search: RecordedSearch
    transport: RecordedFetchTransport
    resolver: RecordedResolver


def load_recorded_web(path: Path, *, adapter_id: str = "recorded-search-v1") -> RecordedWeb:
    """Load ``{"search": {query: exchange}, "pages": {url: page}, "hosts": {host: [ip]}}``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return RecordedWeb(
        search=RecordedSearch(
            adapter_id=adapter_id,
            exchanges={_query_key(q): e for q, e in data.get("search", {}).items()},
        ),
        transport=RecordedFetchTransport(pages=data.get("pages", {})),
        resolver=RecordedResolver(hosts=data.get("hosts", {})),
    )
