"""Sitemaps as AIA reads them: the sitemaps.org protocol, parsed defensively.

A sitemap is a document a third party wrote, read by a crawler that must not be
made to do anything but read it. So the reader is narrow and fails closed:

* **no DTD, no entity**: a document type declaration, an entity declaration or
  an external entity reference refuses the whole sitemap (``sitemap_dtd``) --
  the parser is stdlib ``expat`` with parameter entities off and a handler that
  raises on the first declaration, so neither "billion laughs" nor an external
  fetch can start; an undefined entity is a parse error (``sitemap_invalid``);
* **bounded**: at most :data:`MAX_SITEMAP_BYTES` of XML, after decompression; a
  gzip sitemap is inflated by a bounded decompressor that stops one byte past the
  cap (``sitemap_too_large``) whatever the declared or apparent ratio, so a gzip
  bomb costs at most the cap; one gzip layer only; element nesting at most
  :data:`MAX_SITEMAP_DEPTH`; at most :data:`MAX_SITEMAP_ENTRIES` entries kept
  (the protocol's own limit), the rest counted;
* **shape**: the root is ``urlset`` (pages) or ``sitemapindex`` (more sitemaps),
  matched by local name in any namespace; anything else is ``sitemap_invalid``.
  The protocol's plain-text form (one URL per line) is read too;
* **entries**: a ``loc`` that is not a URL the fetcher may request
  (``check_url``), or is longer than :data:`MAX_LINK_URL_CHARS`, is dropped and
  counted; ``lastmod`` is kept as a date when it is a W3C date, otherwise None
  (never guessed).

Whether an entry is on the right host is the crawler's question, not the
reader's. Nothing here opens a URL.

Pure: stdlib only.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final, NoReturn
from xml.parsers import expat

from .web import MAX_LINK_URL_CHARS, FetchRefused, check_url

__all__ = [
    "MAX_SITEMAP_BYTES",
    "MAX_SITEMAP_DEPTH",
    "MAX_SITEMAP_ENTRIES",
    "SITEMAP_MEDIA_TYPES",
    "Sitemap",
    "SitemapEntry",
    "SitemapKind",
    "SitemapRefused",
    "read_sitemap",
]

#: XML (or text) read from one sitemap, after decompression (the protocol's 50 MB
#: is more than a crawl budget can use; a larger file is refused, never cut).
MAX_SITEMAP_BYTES: Final = 10_000_000
#: The protocol's own limit on entries in one file; beyond it they are counted.
MAX_SITEMAP_ENTRIES: Final = 50_000
#: Element nesting: urlset > url > loc is three; anything deeper is not a sitemap.
MAX_SITEMAP_DEPTH: Final = 8
#: Characters of text read inside one ``loc`` or ``lastmod``.
_MAX_FIELD_CHARS: Final = MAX_LINK_URL_CHARS + 64
#: What a sitemap may be served as. A gzip body is recognised by its magic bytes.
SITEMAP_MEDIA_TYPES: Final = frozenset(
    {
        "application/xml",
        "text/xml",
        "text/plain",
        "application/gzip",
        "application/x-gzip",
        "application/octet-stream",
    }
)
_GZIP_MAGIC: Final = b"\x1f\x8b"
_W3C_DATE: Final = re.compile(r"^\s*(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?")


class SitemapRefused(Exception):
    """A sitemap AIA will not read. ``reason`` is stable."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class SitemapKind(StrEnum):
    #: ``<urlset>`` or a text sitemap: its entries are pages.
    URLSET = "urlset"
    #: ``<sitemapindex>``: its entries are more sitemaps.
    INDEX = "sitemapindex"


@dataclass(frozen=True, slots=True)
class SitemapEntry:
    url: str
    #: The page's declared last modification, or None (absent or not a W3C date).
    lastmod: date | None


@dataclass(frozen=True, slots=True)
class Sitemap:
    kind: SitemapKind
    entries: tuple[SitemapEntry, ...]
    #: Entries dropped: not a fetchable URL, or too long.
    dropped: int
    #: Entries beyond :data:`MAX_SITEMAP_ENTRIES`, not kept.
    overflow: int
    #: The body was gzip, inflated here.
    compressed: bool


def _lastmod(text: str) -> date | None:
    match = _W3C_DATE.match(text)
    if match is None:
        return None
    try:
        return date(int(match[1]), int(match[2] or 1), int(match[3] or 1))
    except ValueError:
        return None


def _inflate(body: bytes) -> bytes:
    """One gzip member inflated, at most :data:`MAX_SITEMAP_BYTES`; a bomb stops at the cap."""
    inflater = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    try:
        out = inflater.decompress(body, MAX_SITEMAP_BYTES + 1)
    except zlib.error as exc:
        raise SitemapRefused("the gzip sitemap is corrupt", reason="sitemap_invalid") from exc
    if len(out) > MAX_SITEMAP_BYTES or inflater.unconsumed_tail:
        raise SitemapRefused(
            f"the sitemap inflates past {MAX_SITEMAP_BYTES} bytes", reason="sitemap_too_large"
        )
    if not inflater.eof:
        raise SitemapRefused("the gzip sitemap is truncated", reason="sitemap_invalid")
    if out.startswith(_GZIP_MAGIC):
        raise SitemapRefused("a sitemap is gzip once, not twice", reason="sitemap_invalid")
    return out


class _Collector:
    """Accumulates entries; shared by the XML and the text readers."""

    def __init__(self) -> None:
        self.entries: list[SitemapEntry] = []
        self.dropped = 0
        self.overflow = 0
        self._seen: set[str] = set()

    def add(self, loc: str, lastmod: str) -> None:
        url = loc.strip()
        try:
            if not url or len(url) > MAX_LINK_URL_CHARS:
                raise FetchRefused("unusable loc", reason="url_invalid")
            check_url(url)
        except FetchRefused:
            self.dropped += 1
            return
        if url in self._seen:
            return
        if len(self.entries) >= MAX_SITEMAP_ENTRIES:
            self.overflow += 1
            return
        self._seen.add(url)
        self.entries.append(SitemapEntry(url=url, lastmod=_lastmod(lastmod)))


def _refuse_dtd(*_: object) -> NoReturn:
    raise SitemapRefused("a sitemap declaring a DTD or an entity is not read", reason="sitemap_dtd")


def _local(name: str) -> str:
    """An element's local name: expat joins namespace and name with a space here."""
    return name.rsplit(" ", 1)[-1]


def _read_xml(body: bytes) -> tuple[SitemapKind, _Collector]:
    collector = _Collector()
    stack: list[str] = []
    fields: dict[str, list[str]] = {}
    state: dict[str, SitemapKind] = {}

    def start(name: str, _attrs: dict[str, str]) -> None:
        local = _local(name)
        if not stack:
            if local == "urlset":
                state["kind"] = SitemapKind.URLSET
            elif local == "sitemapindex":
                state["kind"] = SitemapKind.INDEX
            else:
                raise SitemapRefused(f"<{local}> is not a sitemap", reason="sitemap_invalid")
        stack.append(local)
        if len(stack) > MAX_SITEMAP_DEPTH:
            raise SitemapRefused("the sitemap nests too deeply", reason="sitemap_invalid")
        if len(stack) == 2:
            fields.clear()
        elif len(stack) == 3 and local in ("loc", "lastmod"):
            fields[local] = []

    def end(_name: str) -> None:
        local = stack.pop()
        if len(stack) == 1 and local in ("url", "sitemap"):
            loc = "".join(fields.get("loc", ()))
            collector.add(loc, "".join(fields.get("lastmod", ())))
            fields.clear()

    def data(text: str) -> None:
        if len(stack) == 3 and stack[-1] in fields:
            parts = fields[stack[-1]]
            if sum(map(len, parts)) < _MAX_FIELD_CHARS:
                parts.append(text)

    parser = expat.ParserCreate(namespace_separator=" ")
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.StartDoctypeDeclHandler = _refuse_dtd
    parser.EntityDeclHandler = _refuse_dtd
    parser.UnparsedEntityDeclHandler = _refuse_dtd
    parser.ExternalEntityRefHandler = _refuse_dtd
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = data
    try:
        parser.Parse(body, True)
    except expat.ExpatError as exc:
        raise SitemapRefused(f"the sitemap is not XML: {exc}", reason="sitemap_invalid") from exc
    if "kind" not in state:
        raise SitemapRefused("the sitemap is empty", reason="sitemap_invalid")
    return state["kind"], collector


def _read_text(body: bytes) -> _Collector:
    collector = _Collector()
    text = body.decode("utf-8", errors="replace").removeprefix("﻿")
    for line in text.splitlines():
        if line.strip():
            collector.add(line, "")
    return collector


def read_sitemap(body: bytes, *, media_type: str) -> Sitemap:
    """The entries of one sitemap body, or :class:`SitemapRefused`.

    ``media_type`` is the type the response declared (already one of
    :data:`SITEMAP_MEDIA_TYPES`); a gzip body is recognised by its magic bytes,
    whatever it was declared as. After inflating, a body that starts with ``<``
    is XML; otherwise a ``text/plain`` body is the protocol's text form, and
    anything else is refused.
    """
    media = media_type.split(";", 1)[0].strip().lower()
    if media not in SITEMAP_MEDIA_TYPES:
        raise SitemapRefused(f"{media or '(none)'} is not a sitemap type", reason="content_type")
    if len(body) > MAX_SITEMAP_BYTES:
        raise SitemapRefused(
            f"the sitemap is larger than {MAX_SITEMAP_BYTES} bytes", reason="sitemap_too_large"
        )
    compressed = body.startswith(_GZIP_MAGIC)
    if compressed:
        body = _inflate(body)
    elif media in ("application/gzip", "application/x-gzip"):
        raise SitemapRefused("declared gzip, but is not", reason="sitemap_invalid")
    head = body.lstrip(b"\xef\xbb\xbf \t\r\n")[:1]
    if head == b"<":
        kind, collector = _read_xml(body)
    elif media == "text/plain":
        kind, collector = SitemapKind.URLSET, _read_text(body)
    else:
        raise SitemapRefused("the sitemap is neither XML nor text", reason="sitemap_invalid")
    return Sitemap(
        kind=kind,
        entries=tuple(collector.entries),
        dropped=collector.dropped,
        overflow=collector.overflow,
        compressed=compressed,
    )
