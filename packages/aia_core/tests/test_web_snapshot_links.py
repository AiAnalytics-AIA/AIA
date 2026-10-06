"""A snapshot keeps its page's links as data, and a snapshot without links is unchanged.

No network: the fetcher runs over a recorded transport and resolver.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from aia_core.domain.deep_research.contracts import SnapshotLink, SourceSnapshot, digest
from aia_core.domain.deep_research.steps import SnapshotArtifact
from aia_core.domain.deep_research.web import (
    MAX_ALTERNATE_LINKS,
    MAX_LINK_TEXT_CHARS,
    MAX_SNAPSHOT_LINKS,
)
from aia_core.infrastructure.web_retrieval import (
    RecordedFetchTransport,
    RecordedResolver,
    WebFetcher,
    extract_links,
)

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
PUBLIC = "93.184.215.14"


def _fetch(url: str, page: dict[str, object]) -> SourceSnapshot:
    fetcher = WebFetcher(
        transport=RecordedFetchTransport(pages={url: page}),
        resolver=RecordedResolver(hosts={"stats.example": [PUBLIC]}),
        adapter_id="recorded-fetch-v1",
        clock=lambda: NOW,
    )
    return fetcher.fetch(url).snapshot


LINKED = """<html><head><title>Trh</title>
<link rel="alternate" type="application/RSS+xml" title="Novinky" href="/feed.xml">
<link rel="alternate" hreflang="en" href="https://stats.example/en/trh">
<link rel="alternate stylesheet" href="/dark.css">
<link rel="stylesheet" href="/main.css">
</head><body>
<p>Spotřeba vzrostla o 12,5 %.</p>
<a href="/tabulka#radek-3">Tabulka   <b>3</b></a>
<a href="/tabulka">druhý odkaz na tabulku</a>
<a href="https://other.example/zprava?rok=2025">Zpráva</a>
<a href="#nahoru">nahoru</a>
<a href="mailto:info@stats.example">napište nám</a>
<a href="javascript:void(0)">menu</a>
<a href="http://10.0.0.8/admin">vnitřní</a>
<a href="http://169.254.169.254/latest/meta-data/">metadata</a>
<a href="https://stats.example:8443/port">port</a>
<a href="https://user:pw@stats.example/">heslo</a>
<a href="http://intranet.local/">intranet</a>
<a href=" /x/&#10;y ">mezery</a>
<script><a href="/ve-skriptu">ne</a></script>
<a href="/obrazek"><img src="/i.png"></a><a href="/obrazek">Obrázek s popisem</a>
</body></html>"""


def test_links_are_absolute_fetchable_deduplicated_and_kept_with_anchor_text() -> None:
    snap = _fetch("https://stats.example/trh", {"body": LINKED})
    anchors = [(link.url, link.text) for link in snap.links if link.kind == "anchor"]
    assert anchors == [
        ("https://stats.example/tabulka", "Tabulka 3"),
        ("https://other.example/zprava?rok=2025", "Zpráva"),
        ("https://stats.example/x/y", "mezery"),
        ("https://stats.example/obrazek", "Obrázek s popisem"),
    ]
    alternates = [link for link in snap.links if link.kind == "alternate"]
    assert alternates == [
        SnapshotLink(
            kind="alternate",
            url="https://stats.example/feed.xml",
            text="Novinky",
            media_type="application/rss+xml",
        ),
        SnapshotLink(kind="alternate", url="https://stats.example/en/trh"),
    ]
    # The links are data: the snapshot's content address is its text alone.
    plain = _fetch(
        "https://stats.example/trh",
        {"body": LINKED.replace("<a ", "<span ").replace("</a>", "</span>")},
    )
    assert plain.snapshot_id == snap.snapshot_id
    assert [link.kind for link in plain.links] == ["alternate", "alternate"]


def test_links_resolve_against_the_final_url_and_a_declared_base() -> None:
    redirected = WebFetcher(
        transport=RecordedFetchTransport(
            pages={
                "https://stats.example/a": {
                    "status": 301,
                    "headers": {"location": "https://stats.example/dir/b"},
                },
                "https://stats.example/dir/b": {"body": '<a href="c">c</a>'},
            }
        ),
        resolver=RecordedResolver(hosts={"stats.example": [PUBLIC]}),
        adapter_id="recorded-fetch-v1",
        clock=lambda: NOW,
    ).fetch("https://stats.example/a")
    assert [link.url for link in redirected.snapshot.links] == ["https://stats.example/dir/c"]
    based = extract_links(
        '<base href="https://mirror.example/data/"><a href="t.html">t</a>',
        "https://stats.example/a",
    )
    assert [link.url for link in based] == ["https://mirror.example/data/t.html"]
    # A base that could not be fetched itself is ignored.
    unsafe = extract_links(
        '<base href="http://127.0.0.1/"><a href="t.html">t</a>', "https://stats.example/a/"
    )
    assert [link.url for link in unsafe] == ["https://stats.example/a/t.html"]


def test_links_are_capped_and_anchor_text_is_truncated() -> None:
    many = "".join(
        f'<a href="/p/{i}">{"slovo " * 80}{i}</a>' for i in range(MAX_SNAPSHOT_LINKS + 50)
    )
    many += "".join(
        f'<link rel="alternate" href="/alt/{i}">' for i in range(MAX_ALTERNATE_LINKS + 5)
    )
    links = extract_links(many, "https://stats.example/")
    anchors = [link for link in links if link.kind == "anchor"]
    assert len(anchors) == MAX_SNAPSHOT_LINKS
    assert anchors[-1].url == f"https://stats.example/p/{MAX_SNAPSHOT_LINKS - 1}"
    assert all(len(link.text) == MAX_LINK_TEXT_CHARS for link in anchors)
    assert len([link for link in links if link.kind == "alternate"]) == MAX_ALTERNATE_LINKS
    too_long = extract_links(f'<a href="/{"x" * 3000}">x</a>', "https://stats.example/")
    assert too_long == ()


def test_a_plain_text_page_has_no_links() -> None:
    snap = _fetch(
        "https://stats.example/t.txt",
        {"body": '<a href="/x">x</a>', "headers": {"content-type": "text/plain"}},
    )
    assert snap.links == ()


# Measured on develop @ 757154e, before snapshots carried links: the same page,
# fetched by the same recorded fetcher at the same instant.
_UNLINKED_PAGE = (
    "<html><head><title>Trh</title></head><body><p>Spotřeba vzrostla o 12,5 %.</p></body></html>"
)
_UNLINKED_SNAPSHOT_DIGEST = "c94b6d8b005c35a5cec6363d49dab1af3671e2c8559902112782174425f92dc4"
_UNLINKED_ARTIFACT_DIGEST = "bd0af647eae116c3321a2c645f3302e1f453087eb1afe92d021b8f24e12a4603"
# A snapshot stored before the field existed (its page had a link it did not keep).
_STORED_BEFORE = json.loads(
    '{"snapshot_id":"SNP-82327c2bfea8fc31046e03a9","url":"https://stats.example/a",'
    '"canonical_url":"https://stats.example/a","final_url":"https://stats.example/a",'
    '"redirects":[],"title":"Trh","retrieved_at":"2026-09-27T12:00:00Z","http_status":200,'
    '"content_type":"text/html","raw_sha256":'
    '"9641f960a95a4543ae798f6f0134dd0f68f63530e635f50ae91136535310c5e2","raw_bytes":113,'
    '"text":"Spotřeba vzrostla o 12,5 %. dál","text_sha256":'
    '"82327c2bfea8fc31046e03a94a8852a84b9fc03f0a7427a8a34a84b2bbd8ee49","truncated":false,'
    '"adapter":"recorded-fetch-v1","request_id":null,"retrieval_mode":"RECORDED",'
    '"instructions_detected":[]}'
)


def test_a_snapshot_without_links_keeps_its_old_serialisation_and_hash() -> None:
    snap = _fetch("https://stats.example/a", {"body": _UNLINKED_PAGE})
    assert snap.links == ()
    dumped = snap.model_dump(mode="json")
    assert "links" not in dumped
    assert digest(dumped) == _UNLINKED_SNAPSHOT_DIGEST
    artifact = SnapshotArtifact(kind="deep_research_source_snapshot", snapshot=snap, published=None)
    assert digest(artifact.model_dump(mode="json")) == _UNLINKED_ARTIFACT_DIGEST
    assert "links" not in json.loads(snap.model_dump_json())
    # A stored snapshot reads back and re-serialises byte for byte.
    stored = SourceSnapshot.model_validate(_STORED_BEFORE)
    assert stored.links == ()
    assert stored.model_dump(mode="json") == _STORED_BEFORE
    # With links, the key is present and round-trips.
    linked = stored.model_copy(
        update={"links": (SnapshotLink(kind="anchor", url="https://stats.example/b", text="dál"),)}
    )
    again = SourceSnapshot.model_validate(linked.model_dump(mode="json"))
    assert again == linked and again.model_dump(mode="json")["links"][0]["text"] == "dál"
