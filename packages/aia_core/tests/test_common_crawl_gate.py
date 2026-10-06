"""Common Crawl through the retrieval gate: classified, residency-checked, metered, grounded.

The URL index is in ``us-east-1``: only a Class C statement may leave, and the
statement is written by code. A query is reserved at its scan cutoff and charged
the bytes it scanned. An archived record becomes a snapshot that says it is one,
is grounded like any other, and never answers a live fetch.

No network: recorded doubles, and the live Athena adapter over a scripted wire.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from aia_core.application.web_retrieval import (
    ArchiveRetrieval,
    RetrievalGate,
    RunSnapshotCache,
    WebRetrieval,
)
from aia_core.domain.deep_research.common_crawl import (
    INDEX_COLUMNS,
    AthenaPricing,
    IndexTable,
    IndexTarget,
    UrlIndexQuery,
    build_index_sql,
)
from aia_core.domain.deep_research.contracts import (
    ClientTerm,
    QuarantineReason,
    RetrievalMode,
)
from aia_core.domain.deep_research.grounding import GroundableSource, ground
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
)
from aia_core.domain.deep_research.warc import MAX_RECORD_INFLATED_BYTES
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.common_crawl import (
    ArchiveFetcher,
    AthenaUrlIndex,
    PostResponse,
    RecordedArchiveTransport,
    RecordedUrlIndex,
)
from aia_core.infrastructure.web_retrieval import (
    RecordedFetchTransport,
    RecordedResolver,
    RecordedSearch,
    WebFetcher,
)

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
TABLE = IndexTable(database="ccindex", table="ccindex")
CRAWL = "CC-MAIN-2024-10"
FILE = f"crawl-data/{CRAWL}/segments/1700000000000.10/warc/CC-MAIN-20240101-00001.warc.gz"
FILE_URL = f"https://data.commoncrawl.org/{FILE}"
PAGE_URL = "https://stats.example/zprava/2023"
PAGE = (
    "<html><head><title>Zpráva 2023</title></head><body>"
    "<p>Fiktivní statistický úřad uvádí, že rostlinné nápoje kupuje 45 % domácností.</p>"
    "</body></html>"
).encode()
LIVE_PAGE = "<html><head><title>Dnes</title></head><body><p>Živá verze.</p></body></html>"
PRICING = AthenaPricing(
    usd_per_tb_scanned=5.0, minimum_billed_bytes=10_000_000, billing_increment_bytes=1_000_000
)
CUTOFF = 20_000_000_000
CEILING = PRICING.cost_usd(CUTOFF)  # $0.10


def warc_member(body: bytes = PAGE, *, target: str = PAGE_URL) -> bytes:
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


MEMBER = warc_member()


def _row(offset: int = 0, length: int = len(MEMBER)) -> list[str | None]:
    return [
        PAGE_URL,
        "2024-02-21 10:11:12.000",
        "200",
        "text/html",
        None,
        FILE,
        str(offset),
        str(length),
        CRAWL,
    ]


QUERY = UrlIndexQuery(target=IndexTarget.URL, value=PAGE_URL, crawls=(CRAWL,), limit=3)


def _provider(route_id: str, *, approved: frozenset[DataClass]) -> ProviderRoute:
    # us-east-1: where Common Crawl's bucket is. Approved for Class C only.
    return ProviderRoute(
        route_id=route_id,
        provider="common-crawl",
        zone=ResidencyZone.NON_EU,
        approved_for=approved,
    )


def _route(
    tool: ToolKind,
    adapter_id: str,
    mode: RetrievalMode,
    price: float = 0.0,
    approved: frozenset[DataClass] = frozenset({DataClass.CLASS_C_INTERNAL}),
) -> ToolRoute:
    return ToolRoute(
        route=_provider(f"{tool.value}-{mode.value.lower()}", approved=approved),
        tool=tool,
        adapter_id=adapter_id,
        retrieval_mode=mode,
        price_usd_per_call=price,
    )


def _web_route(tool: ToolKind) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"{tool.value}-recorded",
            provider="recorded",
            zone=ResidencyZone.EU,
            eu_processing_approved=True,
            excluded_from_training=True,
            retention_days=0,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
        tool=tool,
        adapter_id=f"recorded-{tool.value.split('_')[1]}-v1",
        retrieval_mode=RetrievalMode.RECORDED,
        price_usd_per_call=0.0,
    )


@dataclass(slots=True)
class _StudyLedger(InMemoryToolLedger):
    """A meter that holds tool spend against the study (the generalized ledger's stand-in)."""

    @property
    def charges_study_budget(self) -> bool:
        return True


@dataclass
class _Harness:
    gate: RetrievalGate
    ledger: InMemoryToolLedger
    archive: RecordedArchiveTransport
    live: RecordedFetchTransport
    index: Any


def _archive_fetcher(transport: RecordedArchiveTransport) -> ArchiveFetcher:
    return ArchiveFetcher(
        transport=transport,
        resolver=RecordedResolver(hosts={"data.commoncrawl.org": ["18.160.0.10"]}),
        adapter_id="recorded-archive-v1",
        clock=lambda: NOW,
    )


def _harness(
    scope: Any,
    *,
    index: Any = None,
    files: Mapping[str, bytes] | None = None,
    ledger: InMemoryToolLedger | None = None,
    archive_retrieval: ArchiveRetrieval | None = None,
    client_terms: tuple[ClientTerm, ...] = (),
    index_approved: frozenset[DataClass] = frozenset({DataClass.CLASS_C_INTERNAL}),
    cache: RunSnapshotCache | None = None,
) -> _Harness:
    archive = RecordedArchiveTransport(files=files if files is not None else {FILE_URL: MEMBER})
    if index is None:
        index = RecordedUrlIndex(
            table=TABLE,
            exchanges={
                build_index_sql(QUERY, TABLE): {
                    "columns": list(INDEX_COLUMNS),
                    "rows": [_row()],
                    "scanned": 1_234_567,
                    "execution_id": "q-rec",
                }
            },
        )
    if archive_retrieval is None:
        archive_retrieval = ArchiveRetrieval(
            index_route=_route(
                ToolKind.URL_INDEX_QUERY,
                index.adapter_id,
                RetrievalMode.RECORDED,
                approved=index_approved,
            ),
            archive_route=_route(
                ToolKind.ARCHIVE_FETCH, "recorded-archive-v1", RetrievalMode.RECORDED
            ),
            index=index,
            fetcher=_archive_fetcher(archive),
        )
    live = RecordedFetchTransport(pages={PAGE_URL: {"body": LIVE_PAGE}})
    ledger = ledger if ledger is not None else InMemoryToolLedger(budget_usd=1.0)
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_web_route(ToolKind.WEB_SEARCH),
            fetch_route=_web_route(ToolKind.WEB_FETCH),
            search=RecordedSearch(adapter_id="recorded-search-v1", exchanges={}),
            fetcher=WebFetcher(
                transport=live,
                resolver=RecordedResolver(hosts={"stats.example": ["93.184.215.14"]}),
                adapter_id="recorded-fetch-v1",
                clock=lambda: NOW,
            ),
        ),
        scope=scope,
        meter=ledger,
        client_terms=client_terms,
        class_a_texts=("Interní cenová strategie značky Kotelna na rok 2027",),
        clock=lambda: NOW,
        cache=cache,
        archive=archive_retrieval,
    )
    return _Harness(gate, ledger, archive, live, index)


# --------------------------------------------------------------------------- #
# The index: classified and residency-checked before anything leaves
# --------------------------------------------------------------------------- #


def test_a_recorded_index_query_sends_the_statement_code_wrote_and_reads_its_rows(
    scoped: Any,
) -> None:
    h = _harness(scoped.scope())
    outcome = h.gate.query_url_index(QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.reason is None and not outcome.uncertain
    assert outcome.statement == build_index_sql(QUERY, TABLE)
    assert h.index.calls == [outcome.statement]
    assert outcome.data_class is DataClass.CLASS_C_INTERNAL
    (row,) = outcome.rows
    assert (row.url, row.crawl, row.warc_record_offset) == (PAGE_URL, CRAWL, 0)
    events = h.ledger.events()
    assert [(e.tool, e.outcome) for e in events] == [
        (ToolKind.URL_INDEX_QUERY, ToolOutcome.DISPATCHED),
        (ToolKind.URL_INDEX_QUERY, ToolOutcome.SUCCEEDED),
    ]
    assert events[-1].credits == 1_234_567 and events[-1].cost_usd == 0
    assert events[-1].provider_request_id == "q-rec"
    assert outcome.data_scanned_bytes == 1_234_567 and outcome.cost_usd == 0


@pytest.mark.parametrize(
    ("context_class", "approved", "reason"),
    [
        (
            DataClass.CLASS_B_DERIVED_CLIENT,
            frozenset({DataClass.CLASS_C_INTERNAL}),
            "egress_route_not_approved_for_class",
        ),
        # Even a route someone approved for Class B is refused: it is not in the EU.
        (
            DataClass.CLASS_B_DERIVED_CLIENT,
            frozenset({DataClass.CLASS_B_DERIVED_CLIENT, DataClass.CLASS_C_INTERNAL}),
            "egress_residency_violation",
        ),
        (DataClass.CLASS_A_CLIENT_CONFIDENTIAL, frozenset(DataClass), "class_a_query"),
    ],
)
def test_a_statement_written_from_client_material_never_leaves_the_eu(
    scoped: Any, context_class: DataClass, approved: frozenset[DataClass], reason: str
) -> None:
    h = _harness(scoped.scope(), index_approved=approved)
    outcome = h.gate.query_url_index(QUERY, context_class=context_class, track_id="T")
    assert outcome.reason == reason and outcome.rows == ()
    assert h.index.calls == []
    (event,) = h.ledger.events()
    assert event.outcome is ToolOutcome.REFUSED and event.note == reason


def test_a_client_s_name_in_the_host_raises_the_statement_and_it_is_refused(scoped: Any) -> None:
    h = _harness(
        scoped.scope(),
        client_terms=(ClientTerm(term="Pivovar Kotelna", source="client.name"),),
    )
    query = UrlIndexQuery(
        target=IndexTarget.HOST, value="www.pivovar-kotelna.example", crawls=(CRAWL,), limit=10
    )
    outcome = h.gate.query_url_index(query, context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.data_class is DataClass.CLASS_B_DERIVED_CLIENT
    assert outcome.reason == "egress_route_not_approved_for_class"
    assert h.index.calls == []


def test_rows_of_another_shape_are_refused_whole(scoped: Any) -> None:
    bad = _row()
    bad[INDEX_COLUMNS.index("warc_filename")] = "crawl-data/../../etc/passwd.warc.gz"
    index = RecordedUrlIndex(
        table=TABLE,
        exchanges={
            build_index_sql(QUERY, TABLE): {
                "columns": list(INDEX_COLUMNS),
                "rows": [_row(), bad],
                "scanned": 99,
            }
        },
    )
    h = _harness(scoped.scope(), index=index)
    outcome = h.gate.query_url_index(QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.reason == "index_rows_invalid" and outcome.rows == ()
    assert h.ledger.events()[-1].outcome is ToolOutcome.FAILED


# --------------------------------------------------------------------------- #
# Cost: reserved at the cutoff, settled on the bytes scanned
# --------------------------------------------------------------------------- #


class _LiveArchive(RecordedArchiveTransport):
    """Ranges served in-process, standing behind a live route (the live adapter's tests)."""

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE


@dataclass
class _AthenaWire:
    answers: dict[str, Any]
    sent: list[str] = field(default_factory=list)

    def post(
        self, url: str, *, headers: Mapping[str, str], body: bytes, max_bytes: int
    ) -> PostResponse:
        action = headers["x-amz-target"].split(".", 1)[1]
        self.sent.append(action)
        status, payload = self.answers.get(action, (200, {}))
        return PostResponse(
            status=status, headers={}, body=json.dumps(payload).encode(), truncated=False
        )


class _Signer:
    def sign(
        self, *, method: str, url: str, headers: Mapping[str, str], body: bytes
    ) -> dict[str, str]:
        return dict(headers)


def _execution(state: str, scanned: int | None) -> dict[str, Any]:
    execution: dict[str, Any] = {"QueryExecutionId": "q-1", "Status": {"State": state}}
    if scanned is not None:
        execution["Statistics"] = {"DataScannedInBytes": scanned}
    return {"QueryExecution": execution}


def _results() -> dict[str, Any]:
    return {
        "ResultSet": {
            "ResultSetMetadata": {
                "ColumnInfo": [{"Name": c, "Type": "varchar"} for c in INDEX_COLUMNS]
            },
            "Rows": [
                {"Data": [{"VarCharValue": c} for c in INDEX_COLUMNS]},
                {"Data": [{} if v is None else {"VarCharValue": v} for v in _row()]},
            ],
        }
    }


def _live(
    scope: Any, wire: _AthenaWire, ledger: InMemoryToolLedger
) -> tuple[_Harness, AthenaUrlIndex]:
    index = AthenaUrlIndex(
        workgroup="aia-ccindex",
        table=TABLE,
        signer=_Signer(),
        wire=wire,
        monotonic=lambda: 0.0,
        sleep=lambda _: None,
    )

    retrieval = ArchiveRetrieval(
        index_route=_route(
            ToolKind.URL_INDEX_QUERY, index.adapter_id, RetrievalMode.LIVE, price=CEILING
        ),
        archive_route=_route(ToolKind.ARCHIVE_FETCH, "recorded-archive-v1", RetrievalMode.LIVE),
        index=index,
        fetcher=_archive_fetcher(_LiveArchive(files={FILE_URL: MEMBER})),
        pricing=PRICING,
        scan_cutoff_bytes=CUTOFF,
    )
    return _harness(scope, index=index, ledger=ledger, archive_retrieval=retrieval), index


def test_a_query_is_reserved_at_its_cutoff_and_charged_the_bytes_it_scanned(scoped: Any) -> None:
    wire = _AthenaWire(
        answers={
            "StartQueryExecution": (200, {"QueryExecutionId": "q-1"}),
            "GetQueryExecution": (200, _execution("SUCCEEDED", 2_500_000_000)),
            "GetQueryResults": (200, _results()),
        }
    )
    ledger = _StudyLedger(budget_usd=1.0)
    h, _ = _live(scoped.scope(), wire, ledger)
    outcome = h.gate.query_url_index(QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.reason is None and len(outcome.rows) == 1
    dispatched, settled = ledger.events()
    assert dispatched.ceiling_usd == pytest.approx(CEILING) == pytest.approx(0.1)
    assert settled.outcome is ToolOutcome.SUCCEEDED
    assert settled.credits == 2_500_000_000
    assert settled.cost_usd == pytest.approx(0.0125) == pytest.approx(outcome.cost_usd)
    assert ledger.committed_usd() == pytest.approx(0.0125)
    assert "scanned 2500000000 bytes" in settled.note


def test_a_failed_query_is_charged_what_it_scanned_and_an_unknown_scan_its_ceiling(
    scoped: Any,
) -> None:
    failed = _AthenaWire(
        answers={
            "StartQueryExecution": (200, {"QueryExecutionId": "q-1"}),
            "GetQueryExecution": (200, _execution("FAILED", 3_000_000)),
        }
    )
    ledger = _StudyLedger(budget_usd=1.0)
    h, _ = _live(scoped.scope(), failed, ledger)
    outcome = h.gate.query_url_index(QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.reason == "athena_failed" and not outcome.uncertain
    # Below the 10 MB minimum: billed the minimum.
    assert ledger.committed_usd() == pytest.approx(PRICING.cost_usd(10_000_000))

    lost = _AthenaWire(
        answers={"StartQueryExecution": (503, {"__type": "InternalServerException"})}
    )
    ledger = _StudyLedger(budget_usd=1.0)
    h, _ = _live(scoped.scope(), lost, ledger)
    outcome = h.gate.query_url_index(QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.uncertain and outcome.data_scanned_bytes is None
    assert ledger.events()[-1].outcome is ToolOutcome.UNCERTAIN
    assert ledger.committed_usd() == pytest.approx(CEILING)


def test_a_paid_index_is_refused_while_tool_spend_cannot_be_charged_to_the_study(
    scoped: Any,
) -> None:
    wire = _AthenaWire(answers={})
    h, _ = _live(scoped.scope(), wire, InMemoryToolLedger(budget_usd=1.0))
    outcome = h.gate.query_url_index(QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.reason == "tool_metering_unavailable"
    assert wire.sent == []


def test_a_live_index_route_must_be_priced_at_its_cutoff_and_both_routes_share_a_mode() -> None:
    index = AthenaUrlIndex(
        workgroup="aia-ccindex", table=TABLE, signer=_Signer(), wire=_AthenaWire({})
    )

    def retrieval(price: float, archive_mode: RetrievalMode) -> ArchiveRetrieval:
        transport = (
            _LiveArchive(files={})
            if archive_mode is RetrievalMode.LIVE
            else RecordedArchiveTransport(files={})
        )
        return ArchiveRetrieval(
            index_route=_route(
                ToolKind.URL_INDEX_QUERY, index.adapter_id, RetrievalMode.LIVE, price
            ),
            archive_route=_route(ToolKind.ARCHIVE_FETCH, "recorded-archive-v1", archive_mode),
            index=index,
            fetcher=_archive_fetcher(transport),
            pricing=PRICING,
            scan_cutoff_bytes=CUTOFF,
        )

    assert retrieval(CEILING, RetrievalMode.LIVE).scan_cost_usd(None) == pytest.approx(CEILING)
    with pytest.raises(ValueError, match="scan cutoff"):
        retrieval(0.01, RetrievalMode.LIVE)
    with pytest.raises(ValueError, match="both be recorded or both be live"):
        retrieval(CEILING, RetrievalMode.RECORDED)


# --------------------------------------------------------------------------- #
# Archived records: extracted, grounded, never the live page
# --------------------------------------------------------------------------- #


def test_an_archived_record_is_extracted_grounded_and_kept_apart_from_live_fetches(
    scoped: Any,
) -> None:
    cache = RunSnapshotCache()
    h = _harness(scoped.scope(), cache=cache)
    (row,) = h.gate.query_url_index(
        QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T"
    ).rows
    archived = h.gate.fetch_archived(row, track_id="T")
    assert archived.reason is None and archived.page is not None
    snapshot = archived.page.snapshot
    assert snapshot.archive is not None and snapshot.archive.crawl == CRAWL
    assert snapshot.archive.captured_at == datetime(2024, 2, 21, 10, 11, 12, tzinfo=UTC)
    assert h.archive.calls == [(FILE_URL, 0, len(MEMBER))]

    sources = {
        "S1": GroundableSource(
            ref="S1", text=snapshot.text, instructions_detected=snapshot.instructions_detected
        )
    }
    grounded = ground(
        source_ref="S1",
        quote="rostlinné nápoje kupuje 45 % domácností",
        claim="Rostlinné nápoje kupuje 45 % domácností.",
        sources=sources,
    )
    assert grounded.grounded
    added = ground(
        source_ref="S1",
        quote="rostlinné nápoje kupuje 45 % domácností",
        claim="Rostlinné nápoje kupuje 54 % domácností.",
        sources=sources,
    )
    assert added.failure is QuarantineReason.NUMBER_NOT_IN_QUOTE

    # The run cache holds live captures only: the same URL fetched live is fetched.
    assert len(cache) == 0
    live = h.gate.fetch(PAGE_URL, track_id="T")
    assert not live.cached and live.page is not None and live.page.snapshot.archive is None
    assert live.page.snapshot.snapshot_id != snapshot.snapshot_id
    assert h.live.calls == [PAGE_URL]

    fetch_events = [e for e in h.ledger.events() if e.tool is ToolKind.ARCHIVE_FETCH]
    assert [e.outcome for e in fetch_events] == [ToolOutcome.DISPATCHED, ToolOutcome.SUCCEEDED]
    assert fetch_events[-1].note == f"archived {CRAWL} 2024-02-21"


def _fetch_row(h: _Harness) -> Any:
    return h.gate.query_url_index(
        QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T"
    ).rows[0]


def test_a_truncated_member_is_refused_and_the_call_closed(scoped: Any) -> None:
    h = _harness(scoped.scope(), files={FILE_URL: MEMBER[:-9]})
    row = _fetch_row(h)
    # The file ends before the record does: the archive answers a shorter range.
    outcome = h.gate.fetch_archived(row, track_id="T")
    assert outcome.page is None and outcome.reason == "range_mismatch"
    assert h.ledger.events()[-1].outcome is ToolOutcome.FAILED

    short = _row(length=len(MEMBER) - 9)
    index = RecordedUrlIndex(
        table=TABLE,
        exchanges={
            build_index_sql(QUERY, TABLE): {"columns": list(INDEX_COLUMNS), "rows": [short]}
        },
    )
    h = _harness(scoped.scope(), index=index)
    outcome = h.gate.fetch_archived(_fetch_row(h), track_id="T")
    assert outcome.reason == "archive_record_truncated"


def test_a_member_that_inflates_past_its_bound_is_refused(scoped: Any) -> None:
    bomb = warc_member(b"<p>" + b"0" * MAX_RECORD_INFLATED_BYTES + b"</p>")
    assert len(bomb) < 50_000
    index = RecordedUrlIndex(
        table=TABLE,
        exchanges={
            build_index_sql(QUERY, TABLE): {
                "columns": list(INDEX_COLUMNS),
                "rows": [_row(length=len(bomb))],
            }
        },
    )
    h = _harness(scoped.scope(), index=index, files={FILE_URL: bomb})
    outcome = h.gate.fetch_archived(_fetch_row(h), track_id="T")
    assert outcome.page is None and outcome.reason == "archive_record_too_large"


def test_an_archived_fetch_is_refused_for_a_client_term_in_its_url(scoped: Any) -> None:
    h = _harness(
        scoped.scope(), client_terms=(ClientTerm(term="Pivovar Kotelna", source="client.name"),)
    )
    row = _fetch_row(h)
    kotelna = row.__class__(
        **{
            **{f: getattr(row, f) for f in row.__dataclass_fields__},
            "warc_filename": f"crawl-data/{CRAWL}/segments/pivovar-kotelna/warc/a.warc.gz",
        }
    )
    outcome = h.gate.fetch_archived(kotelna, track_id="T")
    assert outcome.reason == "egress_route_not_approved_for_class"
    assert h.archive.calls == []
