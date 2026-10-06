"""The acquisition ladder over the retrieval gate: each rung, the cap, the boundaries.

Each rung test builds a FICTIONAL world in which every earlier rung is tried and fails,
and only that rung reaches the source. The boundary tests show that a paywalled live
page is never asked of an archive (Wayback or Common Crawl), that robots.txt and the
cap end a lead as a gap, and that every call is the gate's (classified, journaled).

Every host is a reserved ``.example`` host or an archive's; every page, table and DOI
is invented. No network: recorded doubles throughout.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from aia_core.application.acquisition_ladder import (
    Climb,
    LadderConfig,
    LadderLimits,
    LadderResult,
    LadderStop,
    ladder,
    rung_direct_link,
    rung_other_formats,
)
from aia_core.application.web_retrieval import (
    ArchiveRetrieval,
    DatasetAccess,
    RetrievalGate,
    WebRetrieval,
    request_fingerprint,
)
from aia_core.domain.deep_research.acquisition import (
    AcquisitionLead,
    DatasetRef,
    GapReason,
    LeadOrigin,
    Match,
    Rung,
    TitleVariant,
)
from aia_core.domain.deep_research.archive import ArchiveBasis
from aia_core.domain.deep_research.common_crawl import (
    INDEX_COLUMNS,
    IndexTable,
    IndexTarget,
    UrlIndexQuery,
    build_index_sql,
)
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.reputation import (
    Publisher,
    RegisterStatus,
    ReputationRegister,
)
from aia_core.domain.deep_research.sources import SourceClass, SourceTier
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
)
from aia_core.domain.deep_research.web import FetchRefused
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.common_crawl import (
    ArchiveFetcher,
    RecordedArchiveTransport,
    RecordedUrlIndex,
)
from aia_core.infrastructure.dataset_connectors import RecordedDatasetConnector
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedFetchTransport,
    RecordedResolver,
    RecordedSearch,
    WebFetcher,
    page_snapshot,
)

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
IP = "93.184.215.14"
PHRASE = "Tabulka 7: Spotřeba rostlinných nápojů"
TITLE = "Ročenka spotřeby potravin 2025"
FILLER = " ".join(["Metodická poznámka k fiktivní ročence a jejím tabulkám."] * 40)
DEAD = "https://stat.example/stara-adresa.html"
CRAWL = "CC-MAIN-2024-10"
TABLE = IndexTable(database="ccindex", table="ccindex")
WARC_FILE = f"crawl-data/{CRAWL}/segments/1700000000000.10/warc/CC-MAIN-20240101-00001.warc.gz"
DATASTAT = "csu-datastat-1"
EUROSTAT = "eurostat-statistics-1"
OPENALEX = "openalex-works-1"
WAYBACK = "wayback-cdx-1"

HOSTS = (
    "stat.example",
    "zpravy.example",
    "noviny.example",
    "journal.example",
    "repozitar.example",
    "jinde.example",
    "web.archive.org",
    "ec.europa.eu",
    "eur-lex.europa.eu",
    "oecd.org",
    "data.gov.cz",
)

REGISTER = ReputationRegister(
    version="fictional-register-1",
    status=RegisterStatus.PROPOSED,
    publishers=(
        Publisher(
            "Fiktivní statistický úřad",
            ("FSÚ",),
            ("stat.example",),
            SourceClass.OFFICIAL_STATISTICS,
            SourceTier.T1,
            ("datastat",),
        ),
    ),
)


def html(
    *,
    title: str = "Fiktivní stránka",
    body: str = FILLER,
    links: tuple[tuple[str, str], ...] = (),
) -> dict[str, Any]:
    anchors = "".join(f'<p><a href="{h}">{text}</a></p>' for h, text in links)
    return {
        "body": f"<html><head><title>{title}</title></head>"
        f"<body><p>{body}</p>{anchors}</body></html>"
    }


def holding(phrase: str = PHRASE, *, title: str = TITLE) -> dict[str, Any]:
    """A page that is the source: it holds the phrase (and the title)."""
    return html(title=title, body=f"{FILLER} {phrase} -- údaje v tis. litrů.")


def lead(**over: Any) -> AcquisitionLead:
    fields: dict[str, Any] = {
        "need": "Tabulka spotřeby rostlinných nápojů za rok 2025",
        "publisher": "Fiktivní statistický úřad",
        "title": TITLE,
        "phrases": (PHRASE,),
        "urls": (DEAD,),
        "origin": LeadOrigin.INVESTIGATOR,
    }
    fields.update(over)
    return AcquisitionLead(**fields)


def q(text: str) -> str:
    return " ".join(text.casefold().split())


def _route(tool: ToolKind, adapter_id: str, *, zone: ResidencyZone = ResidencyZone.EU) -> ToolRoute:
    eu = zone is ResidencyZone.EU
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"{tool.value}-{adapter_id}",
            provider="recorded",
            zone=zone,
            eu_processing_approved=eu,
            excluded_from_training=eu,
            retention_days=0 if eu else None,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
        tool=tool,
        adapter_id=adapter_id,
        retrieval_mode=RetrievalMode.RECORDED,
        price_usd_per_call=0.0,
    )


def warc_member(body: bytes, *, target: str) -> bytes:
    block = b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n" + body
    digest = base64.b32encode(hashlib.sha1(body).digest()).decode()
    head = (
        "WARC/1.0\r\n"
        "WARC-Type: response\r\n"
        "WARC-Date: 2024-02-21T10:11:12Z\r\n"
        "WARC-Record-ID: <urn:uuid:00000000-0000-4000-8000-000000000003>\r\n"
        f"WARC-Target-URI: {target}\r\n"
        "Content-Type: application/http; msgtype=response\r\n"
        f"WARC-Payload-Digest: sha1:{digest}\r\n"
        f"Content-Length: {len(block)}\r\n\r\n"
    ).encode()
    return gzip.compress(head + block + b"\r\n\r\n", mtime=0)


def table(title: str, columns: list[str], rows: list[tuple[str, list[str | None]]]) -> Any:
    return {
        "result": {
            "title": title,
            "publisher": "Fiktivní vydavatel",
            "source_url": "https://data.example/api",
            "columns": [{"key": c, "label": c} for c in columns],
            "rows": [{"key": k, "label": f"řádek {k}", "values": v} for k, v in rows],
        },
        "raw": "{}",
    }


def wayback_table(url: str, timestamp: str = "20240301000000") -> Any:
    return table(
        f"Captures of {url}",
        ["timestamp", "original", "mimetype", "statuscode", "digest", "length", "archived_url"],
        [
            (
                "c1",
                [
                    timestamp,
                    url,
                    "text/html",
                    "200",
                    "FIKTIVNIAAAAAAAAAAAAAAAAAAAAAAAA",
                    "5120",
                    f"https://web.archive.org/web/{timestamp}/{url}",
                ],
            )
        ],
    )


@dataclass
class RobotsTransport:
    """A transport that keeps a robots.txt: known before sending, or found on sending."""

    inner: RecordedFetchTransport
    known: tuple[str, ...] = ()
    found: tuple[str, ...] = ()
    calls: list[str] = field(default_factory=list)

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.RECORDED

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        self.calls.append(url)
        if url.startswith(self.found + self.known):
            raise FetchRefused("robots.txt disallows it", reason="robots_disallowed")
        return self.inner.get(url, address=address, max_bytes=max_bytes)

    def known_refusal(self, url: str) -> str | None:
        return "robots_disallowed" if url.startswith(self.known) else None

    def known_sitemaps(self, host: str) -> tuple[str, ...] | None:
        return None


@dataclass
class World:
    gate: RetrievalGate
    ledger: InMemoryToolLedger
    search: RecordedSearch
    transport: Any
    connectors: dict[str, RecordedDatasetConnector]
    index: RecordedUrlIndex
    archive: RecordedArchiveTransport

    def run(self, the_lead: AcquisitionLead, **kwargs: Any) -> LadderResult:
        kwargs.setdefault("config", LadderConfig(register=REGISTER, crawls=(CRAWL,)))
        kwargs.setdefault("context_class", DataClass.CLASS_C_INTERNAL)
        return ladder(the_lead, gate=self.gate, track_id="T1", **kwargs)

    def fetched(self) -> list[str]:
        calls: list[str] = self.transport.calls
        return calls


def world(
    scope: Any,
    *,
    pages: Mapping[str, Mapping[str, Any]] | None = None,
    searches: Mapping[str, list[dict[str, str]]] | None = None,
    datasets: Mapping[str, Mapping[str, Any]] | None = None,
    wayback: Mapping[str, Any] | None = None,
    index: Mapping[str, Any] | None = None,
    files: Mapping[str, bytes] | None = None,
    robots: tuple[tuple[str, ...], tuple[str, ...]] | None = None,
) -> World:
    recorded = RecordedFetchTransport(pages=dict(pages or {}))
    transport: Any = recorded
    if robots is not None:
        transport = RobotsTransport(inner=recorded, known=robots[0], found=robots[1])
    search = RecordedSearch(
        adapter_id="recorded-search-v1",
        exchanges={q(k): {"hits": v} for k, v in (searches or {}).items()},
    )
    connectors = {
        cid: RecordedDatasetConnector(connector_id=cid, exchanges=ex, clock=lambda: NOW)
        for cid, ex in (datasets or {}).items()
    }
    archives = []
    if wayback is not None:
        connectors[WAYBACK] = RecordedDatasetConnector(
            connector_id=WAYBACK,
            exchanges=wayback,
            clock=lambda: NOW,
            tool_kind=ToolKind.ARCHIVE_LOOKUP,
        )
        archives.append(
            DatasetAccess(
                route=_route(ToolKind.ARCHIVE_LOOKUP, WAYBACK), connector=connectors[WAYBACK]
            )
        )
    url_index = RecordedUrlIndex(table=TABLE, exchanges=dict(index or {}))
    archive_transport = RecordedArchiveTransport(files=dict(files or {}))
    ledger = InMemoryToolLedger(budget_usd=1.0)
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH, "recorded-search-v1"),
            fetch_route=_route(ToolKind.WEB_FETCH, "recorded-fetch-v1"),
            search=search,
            fetcher=WebFetcher(
                transport=transport,
                resolver=RecordedResolver(hosts={h: [IP] for h in HOSTS}),
                adapter_id="recorded-fetch-v1",
                clock=lambda: NOW,
            ),
        ),
        scope=scope,
        meter=ledger,
        client_terms=(),
        class_a_texts=(),
        clock=lambda: NOW,
        datasets=tuple(
            DatasetAccess(route=_route(ToolKind.DATASET_QUERY, cid), connector=c)
            for cid, c in connectors.items()
            if cid != WAYBACK
        ),
        archives=tuple(archives),
        archive=ArchiveRetrieval(
            index_route=_route(
                ToolKind.URL_INDEX_QUERY, url_index.adapter_id, zone=ResidencyZone.NON_EU
            ),
            archive_route=_route(
                ToolKind.ARCHIVE_FETCH, "recorded-archive-v1", zone=ResidencyZone.NON_EU
            ),
            index=url_index,
            fetcher=ArchiveFetcher(
                transport=archive_transport,
                resolver=RecordedResolver(hosts={"data.commoncrawl.org": ["18.160.0.10"]}),
                adapter_id="recorded-archive-v1",
                clock=lambda: NOW,
            ),
        ),
    )
    return World(gate, ledger, search, transport, connectors, url_index, archive_transport)


def acquired(result: LadderResult, rung: Rung) -> None:
    record = result.record
    assert record.stop is LadderStop.ACQUIRED, record.gap
    assert record.acquisition is not None and record.acquisition.rung is rung
    assert record.gap is None and result.capture is not None
    assert result.capture[0].snapshot_id == record.acquisition.snapshot_id


def every_call_journaled(w: World) -> None:
    """Each dispatch is on record before its outcome, and nothing left otherwise."""
    events = w.ledger.events()
    dispatched = [e.call_id for e in events if e.outcome is ToolOutcome.DISPATCHED]
    closed = [e.call_id for e in events if e.outcome.is_terminal and e.reservation_id]
    assert sorted(dispatched) == sorted(closed)


# --------------------------------------------------------------------------- rung by rung


def test_rung_1_opens_the_url_the_lead_names(scoped: Any) -> None:
    source = "https://stat.example/t7.html"
    w = world(scoped.scope(), pages={source: holding()})
    result = w.run(lead(urls=(source,)))
    acquired(result, Rung.DIRECT_LINK)
    assert result.record.acquisition is not None
    assert result.record.acquisition.match is Match.PHRASE
    assert result.record.acquisition.on_publisher_host
    assert result.record.rungs_tried == (Rung.DIRECT_LINK,) and result.record.requests == 1
    every_call_journaled(w)


def test_rung_1_follows_a_link_of_the_citing_page_that_names_the_source(scoped: Any) -> None:
    source = "https://stat.example/publikace/rocenka-spotreby-potravin-2025"
    w = world(scoped.scope(), pages={source: holding()})
    # The citing page: a capture the track already holds.
    page = page_snapshot(
        url="https://zpravy.example/clanek",
        final_url="https://zpravy.example/clanek",
        redirects=(),
        http_status=200,
        content_type="text/html; charset=utf-8",
        body=(
            f'<html><body><p>{FILLER}</p><a href="{source}">zdroj</a>'
            '<a href="https://archive.ph/abc">Ročenka spotřeby potravin 2025</a></body></html>'
        ).encode(),
        request_id=None,
        adapter_id="recorded-fetch-v1",
        retrieval_mode=RetrievalMode.RECORDED,
        retrieved_at=NOW,
    ).snapshot
    result = w.run(lead(urls=()), citing=page)
    acquired(result, Rung.DIRECT_LINK)
    # The archive.ph link names the title too: it is never a candidate.
    assert w.fetched() == [source]


def test_rung_2_reaches_the_csv_twin_of_an_html_release(scoped: Any) -> None:
    release = "https://stat.example/rocenka.html"
    twin = "https://stat.example/data/t7.csv"
    w = world(
        scoped.scope(),
        pages={
            release: html(title=TITLE, links=((twin, "Data ke stažení"),)),
            twin: {
                "body": f"{PHRASE};2025\nPraha;12\n",
                "headers": {"content-type": "text/csv; charset=utf-8"},
            },
        },
    )
    result = w.run(lead(urls=(release,)))
    acquired(result, Rung.OTHER_FORMATS)
    assert result.record.rungs_tried == (Rung.DIRECT_LINK, Rung.OTHER_FORMATS)
    assert w.fetched() == [release, twin]


def test_rung_3_finds_the_source_on_the_publisher_s_own_site(scoped: Any) -> None:
    source = "https://stat.example/publikace/t7"
    w = world(
        scoped.scope(),
        pages={source: holding()},
        searches={
            f'"{PHRASE}" site:stat.example': [
                {"url": "https://jinde.example/kopie", "title": "kopie"},
                {"url": source, "title": PHRASE},
            ]
        },
    )
    result = w.run(lead())
    acquired(result, Rung.PUBLISHER_INDEX)
    # Only the publisher's own host is opened from a site: search.
    assert w.fetched() == [DEAD, source]
    assert result.record.rungs_tried == (Rung.DIRECT_LINK, Rung.PUBLISHER_INDEX)


def test_rung_4_asks_the_publisher_s_own_data_interface(scoped: Any) -> None:
    w = world(
        scoped.scope(),
        datasets={
            DATASTAT: {
                "FIKT07 period=2025": table(
                    "Spotřeba rostlinných nápojů", ["2025"], [("R1", ["12,4"])]
                )
            }
        },
    )
    the_lead = lead(datasets=(DatasetRef(connector_id=DATASTAT, dataset_id="FIKT07"),))
    the_lead = the_lead.model_copy(update={"period": "2025"})
    result = w.run(the_lead)
    acquired(result, Rung.DATA_INTERFACE)
    assert result.record.acquisition is not None
    assert result.record.acquisition.match is Match.DATASET
    assert w.connectors[DATASTAT].calls == ["FIKT07 period=2025"]
    # Rung 3 was tried first: its site: search and its sitemap found nothing.
    assert result.record.rungs_tried == (
        Rung.DIRECT_LINK,
        Rung.PUBLISHER_INDEX,
        Rung.DATA_INTERFACE,
    )
    assert "https://stat.example/sitemap.xml" in w.fetched()


def test_rung_5_finds_the_exact_phrase_anywhere_public(scoped: Any) -> None:
    source = "https://jinde.example/kopie-tabulky"
    w = world(
        scoped.scope(),
        pages={source: holding()},
        searches={
            f'"{PHRASE}"': [
                {
                    "url": "https://web.archive.org/web/2024/https://stat.example/t7",
                    "title": PHRASE,
                },
                {"url": source, "title": PHRASE},
            ]
        },
    )
    result = w.run(lead(publisher=None))
    acquired(result, Rung.EXACT_PHRASE)
    assert result.record.acquisition is not None
    assert not result.record.acquisition.on_publisher_host
    # The archive's copy among the hits is never opened.
    assert w.fetched() == [DEAD, source]


def test_rung_6_reaches_the_english_edition(scoped: Any) -> None:
    source = "https://jinde.example/en/yearbook"
    variant = TitleVariant(title="Food Consumption Yearbook 2025", lang="en", period="2025")
    w = world(
        scoped.scope(),
        pages={source: holding("Table 7", title="Food Consumption Yearbook 2025")},
        searches={'"Food Consumption Yearbook 2025"': [{"url": source, "title": "Yearbook"}]},
    )
    result = w.run(lead(publisher=None, variants=(variant,)))
    acquired(result, Rung.LANGUAGE_EDITION)
    assert result.record.acquisition is not None
    assert result.record.acquisition.edition_period == "2025"
    assert w.search.languages[-1] == "en"
    assert result.record.rungs_tried == (
        Rung.DIRECT_LINK,
        Rung.EXACT_PHRASE,
        Rung.LANGUAGE_EDITION,
    )


OA_COLUMNS = [
    "is_oa",
    "version",
    "license",
    "landing_page_url",
    "pdf_url",
    "source",
    "source_type",
    "best_oa",
]
PAPER = "Rostlinné nápoje v české domácnosti"
JOURNAL = "https://journal.example/clanek/7"
REPO = "https://repozitar.example/7"


def _oa_world(scope: Any, **datasets: Any) -> World:
    return world(
        scope,
        pages={
            JOURNAL: html(
                title=PAPER, body=f"{PAPER}. Subscribe to continue reading this article."
            ),
            REPO: html(title=PAPER, body=f"{FILLER} {PAPER}: plný text (accepted version)."),
        },
        datasets={
            OPENALEX: {
                "doi:10.5555/fikt.2025.7": table(
                    PAPER,
                    OA_COLUMNS,
                    [
                        (
                            "loc1",
                            ["false", "publishedVersion", None, JOURNAL, None, "J", "j", "no"],
                        ),
                        ("loc2", ["true", "acceptedVersion", "cc-by", REPO, None, "R", "r", "yes"]),
                    ],
                ),
                **datasets,
            }
        },
        wayback={},
    )


def test_rung_7_finds_an_open_access_copy_of_a_paywalled_doi(scoped: Any) -> None:
    w = _oa_world(scoped.scope())
    the_lead = lead(
        publisher=None, phrases=(), title=PAPER, doi="10.5555/fikt.2025.7", urls=(JOURNAL,)
    )
    result = w.run(the_lead)
    acquired(result, Rung.SCHOLARLY_IDENTITY)
    assert result.record.acquisition is not None and result.record.acquisition.url == REPO
    # The paywalled publisher page was met, read as a paywall, and nothing more.
    assert w.fetched() == [JOURNAL, REPO]
    assert w.connectors[WAYBACK].calls == []


def test_rung_7_finds_the_doi_from_the_title(scoped: Any) -> None:
    search = table(
        "OpenAlex works search",
        ["openalex_id", "doi", "title", "publication_year", "is_oa", "oa_status", "oa_url"],
        [
            (
                "w1",
                ["W1", "https://doi.org/10.5555/fikt.2025.7", PAPER, "2025", "true", "green", REPO],
            )
        ],
    )
    w = _oa_world(scoped.scope(), **{"works search=rostlinne,napoje,ceske,domacnosti": search})
    result = w.run(lead(publisher=None, phrases=(), title=PAPER, urls=(JOURNAL,)))
    acquired(result, Rung.SCHOLARLY_IDENTITY)
    assert w.connectors[OPENALEX].calls == [
        "works search=rostlinne,napoje,ceske,domacnosti",
        "doi:10.5555/fikt.2025.7",
    ]


def test_rung_8_reaches_an_aggregator_republishing_the_figure(scoped: Any) -> None:
    w = world(
        scoped.scope(),
        datasets={
            EUROSTAT: {"fikt_tab": table("Plant-based drinks", ["2025"], [("CZ", ["12.4"])])}
        },
    )
    the_lead = lead(datasets=(DatasetRef(connector_id=EUROSTAT, dataset_id="fikt_tab"),))
    result = w.run(the_lead)
    acquired(result, Rung.AGGREGATOR)
    assert result.record.rungs_tried == (
        Rung.DIRECT_LINK,
        Rung.PUBLISHER_INDEX,
        Rung.EXACT_PHRASE,
        Rung.AGGREGATOR,
    )


def test_rung_9_reads_a_dead_page_from_wayback_nearest_the_cited_date(scoped: Any) -> None:
    replay = f"https://web.archive.org/web/20240301000000/{DEAD}"
    w = world(
        scoped.scope(),
        pages={replay: holding()},
        wayback={f"{DEAD} period=2024": wayback_table(DEAD)},
    )
    result = w.run(lead(publisher=None, cited_date="2024"))
    acquired(result, Rung.ARCHIVED_COPY)
    acquisition = result.record.acquisition
    assert acquisition is not None and acquisition.archived is not None
    assert acquisition.archived.archive == "wayback"
    assert acquisition.archived.basis is ArchiveBasis.DEAD
    assert acquisition.archived.captured == "20240301000000"
    assert acquisition.url == DEAD
    assert w.fetched() == [DEAD, replay]
    permit = [a for a in result.record.attempts if a.tool == "archive_permit"]
    assert [(a.target, a.reason) for a in permit] == [(DEAD, "dead")]


def test_rung_9_reads_a_dead_page_from_common_crawl(scoped: Any) -> None:
    body = (
        f"<html><head><title>{TITLE}</title></head><body><p>{FILLER} {PHRASE}</p></body></html>"
    ).encode()
    member = warc_member(body, target=DEAD)
    statement = build_index_sql(
        UrlIndexQuery(target=IndexTarget.URL, value=DEAD, crawls=(CRAWL,), limit=20), TABLE
    )
    row = [DEAD, "2024-02-21 10:11:12.000", "200", "text/html", None, WARC_FILE]
    w = world(
        scoped.scope(),
        index={
            statement: {
                "columns": list(INDEX_COLUMNS),
                "rows": [[*row, "0", str(len(member)), CRAWL]],
                "scanned": 1000,
            }
        },
        files={f"https://data.commoncrawl.org/{WARC_FILE}": member},
    )
    result = w.run(lead(publisher=None))
    acquired(result, Rung.ARCHIVED_COPY)
    acquisition = result.record.acquisition
    assert acquisition is not None and acquisition.archived is not None
    assert acquisition.archived.archive == "common_crawl"
    assert result.capture is not None and result.capture[0].archive is not None
    assert w.index.calls == [statement]


def test_rung_10_finds_a_moved_document_on_its_own_host(scoped: Any) -> None:
    gone = "https://stat.example/publikace/2025/rocenka.pdf"
    listing = "https://stat.example/publikace/2025/"
    moved = "https://stat.example/publikace/2025/rocenka-spotreby-potravin-2025.html"
    w = world(
        scoped.scope(),
        pages={
            listing: html(links=((moved, TITLE), ("https://jinde.example/x", TITLE))),
            moved: holding(),
        },
    )
    result = w.run(lead(publisher=None, urls=(gone,)))
    acquired(result, Rung.PATH_DISCOVERY)
    assert w.fetched() == [gone, listing, moved]
    # The archive was asked (the page is dead: a permit) and held no capture.
    assert len(w.index.calls) == 1
    assert result.record.rungs_tried == (
        Rung.DIRECT_LINK,
        Rung.EXACT_PHRASE,
        Rung.AGGREGATOR,
        Rung.ARCHIVED_COPY,
        Rung.PATH_DISCOVERY,
    )


def test_a_rung_can_be_climbed_alone(scoped: Any) -> None:
    release = "https://stat.example/rocenka.html"
    twin = "https://stat.example/data/t7.csv"
    w = world(
        scoped.scope(),
        pages={
            release: html(title=TITLE, links=((twin, "CSV"),)),
            twin: {"body": f"{PHRASE};1\n", "headers": {"content-type": "text/csv"}},
        },
    )
    climb = Climb(
        lead(urls=(release,)),
        gate=w.gate,
        track_id="T1",
        context_class=DataClass.CLASS_C_INTERNAL,
        config=LadderConfig(),
        limits=LadderLimits(),
    )
    rung_direct_link(climb)  # captures the release; it does not answer
    assert [p.final_url for p in climb.pages] == [release]
    with pytest.raises(Exception, match="2_other_formats"):
        climb.rung = Rung.OTHER_FORMATS
        rung_other_formats(climb)


# --------------------------------------------------------------------------- boundaries

PAYWALLED = "https://noviny.example/placeny-clanek"


def _paywall_world(scope: Any, page: Mapping[str, Any]) -> World:
    """A live page and both archives holding a copy of it: the archives must stay unasked."""
    body = f"<html><body><p>{FILLER} {PHRASE}</p></body></html>".encode()
    member = warc_member(body, target=PAYWALLED)
    statement = build_index_sql(
        UrlIndexQuery(target=IndexTarget.URL, value=PAYWALLED, crawls=(CRAWL,), limit=20), TABLE
    )
    row = [PAYWALLED, "2024-02-21 10:11:12.000", "200", "text/html", None, WARC_FILE]
    replay = f"https://web.archive.org/web/20240301000000/{PAYWALLED}"
    return world(
        scope,
        pages={PAYWALLED: page, replay: holding()},
        wayback={PAYWALLED: wayback_table(PAYWALLED)},
        index={
            statement: {
                "columns": list(INDEX_COLUMNS),
                "rows": [[*row, "0", str(len(member)), CRAWL]],
                "scanned": 1000,
            }
        },
        files={f"https://data.commoncrawl.org/{WARC_FILE}": member},
    )


@pytest.mark.parametrize(
    ("page", "reason"),
    [
        # Live, answered 200, and a paywall in the way.
        (
            html(body=f"{FILLER} Obsah je dostupný jen pro předplatitele."),
            GapReason.PAYWALL,
        ),
        (html(body=f"{FILLER} Please sign in to continue reading."), GapReason.LOGIN),
        # The publisher says so by status.
        ({"status": 402, "body": ""}, GapReason.PAYWALL),
        ({"status": 403, "body": ""}, GapReason.NOT_PUBLIC),
        # A short page nobody can tell is open: unknown is never scored as open.
        (html(body="Krátká stránka."), GapReason.NOT_FOUND),
    ],
)
def test_a_paywalled_live_page_is_never_fetched_from_an_archive(
    scoped: Any, page: Mapping[str, Any], reason: GapReason
) -> None:
    w = _paywall_world(scoped.scope(), page)
    result = w.run(lead(publisher=None, urls=(PAYWALLED,)))
    record = result.record
    assert record.stop is LadderStop.GAP and record.gap is not None
    assert record.gap.reason is reason
    # Neither archive was asked, by lookup, index or record; no replay was fetched.
    assert w.connectors[WAYBACK].calls == []
    assert w.index.calls == [] and w.archive.calls == []
    assert not any("web.archive.org" in url for url in w.fetched())
    permit = [a for a in record.attempts if a.tool == "archive_permit"]
    assert [(a.target, a.reason) for a in permit] == [(PAYWALLED, "live_access_restricted")]
    every_call_journaled(w)


def test_the_same_page_dead_is_read_from_the_archive(scoped: Any) -> None:
    # The control for the test above: the same world, the live page gone.
    w = _paywall_world(scoped.scope(), {"status": 410, "body": ""})
    result = w.run(lead(publisher=None, urls=(PAYWALLED,)))
    acquired(result, Rung.ARCHIVED_COPY)
    assert w.connectors[WAYBACK].calls == [PAYWALLED]


@pytest.mark.parametrize("when", ["known", "found"])
def test_a_robots_refusal_is_a_gap_and_is_never_worked_round(scoped: Any, when: str) -> None:
    private = "https://stat.example/interni/t7.html"
    prefixes = (("https://stat.example/interni/",), ())
    w = world(
        scoped.scope(),
        pages={private: holding()},
        wayback={private: wayback_table(private)},
        robots=prefixes if when == "known" else prefixes[::-1],
    )
    result = w.run(lead(publisher=None, urls=(private,)))
    record = result.record
    assert record.stop is LadderStop.GAP and record.gap is not None
    assert record.gap.reason is GapReason.ROBOTS
    assert "robots.txt" in record.gap.how_to_obtain
    # A robots refusal is no reason to ask an archive.
    assert w.connectors[WAYBACK].calls == []
    first = record.attempts[0]
    if when == "known":
        assert first.decision.value == "refused" and first.call_id is None
        assert w.fetched() == []
    else:
        assert first.decision.value == "sent" and first.outcome == "failed"


def test_the_cap_ends_an_unreachable_lead(scoped: Any) -> None:
    urls = tuple(f"https://stat.example/neexistuje/{i}.html" for i in range(10))
    w = world(
        scoped.scope(),
        searches={
            f'"{PHRASE}" site:stat.example': [
                {"url": f"https://stat.example/jine/{i}", "title": PHRASE} for i in range(5)
            ]
        },
    )
    result = w.run(lead(urls=urls))
    record = result.record
    assert record.stop is LadderStop.GAP and record.gap is not None
    assert record.gap.reason is GapReason.CAP_REACHED
    assert record.requests == 12
    dispatched = [e for e in w.ledger.events() if e.outcome is ToolOutcome.DISPATCHED]
    assert len(dispatched) == 12
    assert len(w.fetched()) + len(w.search.calls) == 12
    every_call_journaled(w)


def test_a_smaller_cap_ends_sooner(scoped: Any) -> None:
    w = world(scoped.scope())
    result = w.run(lead(), limits=LadderLimits(requests=2))
    assert result.record.requests == 2 and result.record.gap is not None
    assert result.record.gap.reason is GapReason.CAP_REACHED


def test_the_gap_names_publisher_title_and_reason(scoped: Any) -> None:
    w = world(scoped.scope())
    result = w.run(lead())
    gap = result.record.gap
    assert result.record.stop is LadderStop.GAP and gap is not None
    assert gap.publisher == "Fiktivní statistický úřad"
    assert gap.title == TITLE and gap.url == DEAD
    assert gap.reason is GapReason.NOT_FOUND
    assert gap.rungs_tried == (*result.record.rungs_tried, Rung.GAP)
    assert gap.rungs_tried[0] is Rung.DIRECT_LINK and gap.how_to_obtain


def test_an_uncertain_call_ends_the_ladder_and_nothing_more_is_sent(scoped: Any) -> None:
    lost = "https://stat.example/ztraceno.html"
    w = world(scoped.scope(), pages={lost: {"fail": "uncertain"}})
    result = w.run(lead(urls=(lost, DEAD)))
    assert result.record.stop is LadderStop.UNCERTAIN
    assert result.record.gap is not None and result.record.gap.reason is GapReason.UNCERTAIN
    assert w.fetched() == [lost] and w.search.calls == []


def test_a_call_an_earlier_attempt_dispatched_is_not_sent_again(scoped: Any) -> None:
    w = world(scoped.scope())
    sent_before = {request_fingerprint(DEAD)}
    result = w.run(lead(), may_send=lambda sent: request_fingerprint(sent) not in sent_before)
    assert result.record.stop is LadderStop.EARLIER_ATTEMPT
    assert result.record.gap is None and w.fetched() == []
    assert result.record.attempts[-1].reason == "sent_by_an_earlier_attempt"


def test_searches_written_from_client_material_are_refused_by_the_gate(scoped: Any) -> None:
    w = world(scoped.scope())
    result = w.run(lead(), context_class=DataClass.CLASS_B_DERIVED_CLIENT)
    assert result.record.gap is not None
    assert result.record.gap.reason is GapReason.POLICY_REFUSED
    assert w.search.calls == []
    refused = [a for a in result.record.attempts if a.tool == "search"]
    assert refused and all(a.decision.value == "refused" for a in refused)


def test_the_track_s_allowance_bounds_the_ladder(scoped: Any) -> None:
    w = world(scoped.scope())
    result = w.run(lead(), limits=LadderLimits(searches=0, fetches=1))
    assert w.search.calls == [] and w.fetched() == [DEAD]
    assert result.record.searches == 0 and result.record.fetches == 1


def test_a_failed_dataset_call_is_recorded_not_raised(scoped: Any) -> None:
    w = world(scoped.scope(), datasets={DATASTAT: {"FIKT07": {"fail": "known"}}})
    result = w.run(lead(datasets=(DatasetRef(connector_id=DATASTAT, dataset_id="FIKT07"),)))
    assert result.record.stop is LadderStop.GAP
    failed = [a for a in result.record.attempts if a.tool == "dataset"]
    assert [(a.outcome, a.reason) for a in failed] == [("failed", "provider_error")]
