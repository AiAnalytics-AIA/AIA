"""Sitemaps as AIA reads them: the protocol's two forms, and nothing a hostile file makes of it."""

from __future__ import annotations

import gzip
from datetime import date

import pytest

from aia_core.domain.deep_research import sitemaps
from aia_core.domain.deep_research.sitemaps import (
    MAX_SITEMAP_BYTES,
    SitemapKind,
    SitemapRefused,
    read_sitemap,
)

NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


def _urlset(*entries: str) -> bytes:
    body = "".join(f"<url>{entry}</url>" for entry in entries)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset {NS}>{body}</urlset>'.encode()


def _refused(body: bytes, media_type: str = "application/xml") -> str:
    with pytest.raises(SitemapRefused) as refused:
        read_sitemap(body, media_type=media_type)
    return refused.value.reason


def test_a_urlset_yields_its_pages_with_their_dates() -> None:
    sitemap = read_sitemap(
        _urlset(
            "<loc>https://stats.example/a</loc><lastmod>2026-09-30T10:00:00+02:00</lastmod>",
            "<loc> https://stats.example/b?x=1&amp;y=2 </loc><lastmod>2025-07</lastmod>",
            "<loc>https://stats.example/c</loc><lastmod>yesterday</lastmod>",
            "<loc>https://stats.example/a</loc>",  # listed twice: kept once
            "<loc>javascript:alert(1)</loc>",
            "<loc>https://10.0.0.8/internal</loc>",
            "<loc>https://stats.example/" + "x" * 3000 + "</loc>",
            "<loc></loc>",
        ),
        media_type="text/xml; charset=utf-8",
    )
    assert sitemap.kind is SitemapKind.URLSET and not sitemap.compressed
    assert [(e.url, e.lastmod) for e in sitemap.entries] == [
        ("https://stats.example/a", date(2026, 9, 30)),
        ("https://stats.example/b?x=1&y=2", date(2025, 7, 1)),
        ("https://stats.example/c", None),  # not a W3C date: unknown, never guessed
    ]
    assert sitemap.dropped == 4 and sitemap.overflow == 0


def test_an_index_yields_sitemaps_and_extensions_are_ignored() -> None:
    body = (
        f'<sitemapindex {NS} xmlns:x="urn:x">'
        "<sitemap><loc>https://stats.example/s1.xml</loc><lastmod>2026-01-02</lastmod></sitemap>"
        "<sitemap><loc>https://stats.example/s2.xml.gz</loc><x:note>n</x:note></sitemap>"
        "</sitemapindex>"
    ).encode()
    sitemap = read_sitemap(body, media_type="application/xml")
    assert sitemap.kind is SitemapKind.INDEX
    assert [e.url for e in sitemap.entries] == [
        "https://stats.example/s1.xml",
        "https://stats.example/s2.xml.gz",
    ]
    images = _urlset(
        '<loc>https://stats.example/p</loc><image:image xmlns:image="urn:i">'
        "<image:loc>https://img.example/1.png</image:loc></image:image>"
    )
    assert [e.url for e in read_sitemap(images, media_type="text/xml").entries] == [
        "https://stats.example/p"
    ]


def test_a_doctype_or_an_entity_refuses_the_whole_sitemap() -> None:
    laughs = (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]>'
        b"<urlset><url><loc>https://stats.example/&lol2;</loc></url></urlset>"
    )
    assert _refused(laughs) == "sitemap_dtd"
    external = (
        b'<?xml version="1.0"?><!DOCTYPE urlset [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b"<urlset><url><loc>&xxe;</loc></url></urlset>"
    )
    assert _refused(external) == "sitemap_dtd"
    public_dtd = b'<!DOCTYPE urlset SYSTEM "https://evil.example/s.dtd"><urlset/>'
    assert _refused(public_dtd) == "sitemap_dtd"
    # Without a declaration, an entity is undefined: not XML.
    assert _refused(_urlset("<loc>https://stats.example/&undefined;</loc>")) == "sitemap_invalid"


def test_gzip_is_inflated_once_and_a_bomb_stops_at_the_cap() -> None:
    plain = _urlset("<loc>https://stats.example/a</loc>")
    sitemap = read_sitemap(gzip.compress(plain), media_type="application/x-gzip")
    assert sitemap.compressed and [e.url for e in sitemap.entries] == ["https://stats.example/a"]
    # Served as XML, recognised by its bytes.
    assert read_sitemap(gzip.compress(plain), media_type="application/xml").compressed
    bomb = gzip.compress(b" " * (MAX_SITEMAP_BYTES + 10), compresslevel=9)
    assert len(bomb) < MAX_SITEMAP_BYTES // 100  # a small file that inflates past the cap
    assert _refused(bomb, "application/gzip") == "sitemap_too_large"
    assert _refused(gzip.compress(gzip.compress(plain)), "application/gzip") == "sitemap_invalid"
    assert _refused(gzip.compress(plain)[:-12], "application/gzip") == "sitemap_invalid"
    assert _refused(plain, "application/gzip") == "sitemap_invalid"  # declared, but is not
    assert _refused(b"\x1f\x8bnot really", "application/gzip") == "sitemap_invalid"


def test_bounds_on_size_nesting_and_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _refused(b" " * (MAX_SITEMAP_BYTES + 1)) == "sitemap_too_large"
    deep = b"<urlset>" + b"<a>" * 10 + b"</a>" * 10 + b"</urlset>"
    assert _refused(deep) == "sitemap_invalid"
    monkeypatch.setattr(sitemaps, "MAX_SITEMAP_ENTRIES", 2)
    sitemap = read_sitemap(
        _urlset(*(f"<loc>https://stats.example/{i}</loc>" for i in range(5))),
        media_type="application/xml",
    )
    assert len(sitemap.entries) == 2 and sitemap.overflow == 3


def test_what_is_not_a_sitemap_is_refused() -> None:
    assert _refused(b"<html><body>hi</body></html>") == "sitemap_invalid"
    assert _refused(b"<urlset><url><loc>https://a.example/</loc></url>") == "sitemap_invalid"
    assert _refused(b"") == "sitemap_invalid"
    assert _refused(b"https://stats.example/a", "application/xml") == "sitemap_invalid"
    assert _refused(_urlset(), "text/html") == "content_type"


def test_the_text_form_is_one_url_per_line() -> None:
    body = b"\xef\xbb\xbfhttps://stats.example/a\n\nhttps://stats.example/b\r\nnot a url\n"
    sitemap = read_sitemap(body, media_type="text/plain")
    assert [e.url for e in sitemap.entries] == [
        "https://stats.example/a",
        "https://stats.example/b",
    ]
    assert sitemap.kind is SitemapKind.URLSET and sitemap.dropped == 1
