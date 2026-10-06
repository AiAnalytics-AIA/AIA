"""The archive is used only for a dead or moved page, and only with a permit for that URL.

Plan ``deep-research-web-search.md`` § 4 (never an archive to get round a paywall) and
§ 7 rung 9. The policy is pure; the gate refuses an archive lookup without the permit
the policy issues. Every page and capture here is FICTIONAL. No network.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from aia_core.application.web_retrieval import (
    DatasetAccess,
    FetchOutcome,
    RetrievalGate,
    WebRetrieval,
    live_attempt,
)
from aia_core.domain.deep_research.archive import (
    AccessBarrier,
    ArchiveBasis,
    ArchivePermit,
    LiveAttempt,
    decide_archive_use,
)
from aia_core.domain.deep_research.contracts import (
    ClientTerm,
    QueryDecision,
    RetrievalMode,
    SourceSnapshot,
)
from aia_core.domain.deep_research.datasets import DatasetQuery
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
)
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.dataset_connectors import RecordedDatasetConnector
from aia_core.infrastructure.web_retrieval import (
    FetchedPage,
    RecordedFetchTransport,
    RecordedResolver,
    RecordedSearch,
    WebFetcher,
)

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
PAGE = "https://zpravy.example/fiktivni-zprava-2022"
NEED = "Fiktivní podíl domácností vzrostl na 43,2 %."


def _page(text: str, *, final_url: str = PAGE) -> LiveAttempt:
    return LiveAttempt(
        url=PAGE,
        failure=None,
        uncertain=False,
        final_url=final_url,
        text=text,
        barrier=AccessBarrier.NONE,
    )


def _failed(reason: str, *, uncertain: bool = False) -> LiveAttempt:
    return LiveAttempt(url=PAGE, failure=reason, uncertain=uncertain)


# --------------------------------------------------------------------------- the policy


@pytest.mark.parametrize(
    ("attempt", "basis"),
    [
        (_failed("http_404"), ArchiveBasis.DEAD),
        (_failed("http_410"), ArchiveBasis.DEAD),
        (_failed("address_unresolved"), ArchiveBasis.DEAD),  # the host is gone
        (
            _page("Stránka byla přesunuta.", final_url="https://zpravy.example/archiv"),
            ArchiveBasis.MOVED,
        ),
        (_page("Nový obsah bez původní věty."), ArchiveBasis.CHANGED),
    ],
)
def test_a_dead_moved_or_changed_page_may_be_asked_of_the_archive(
    attempt: LiveAttempt, basis: ArchiveBasis
) -> None:
    decision = decide_archive_use(attempt, needed_quote=NEED)
    assert decision.refusal is None and decision.permit is not None
    assert (decision.permit.url, decision.permit.basis) == (PAGE, basis)


@pytest.mark.parametrize(
    ("attempt", "refusal"),
    [
        # The live page serves the quote: the archive is never a first choice.
        (_page(f"Úvod. {NEED} Závěr."), "live_has_quote"),
        (_page(f"Úvod. {NEED}", final_url="https://zpravy.example/nova-adresa"), "live_has_quote"),
        # A page live behind a barrier is never fetched from an archive.
        (
            LiveAttempt(PAGE, None, False, PAGE, "Předplaťte si článek.", AccessBarrier.PAYWALL),
            "live_access_restricted",
        ),
        (
            LiveAttempt(PAGE, None, False, PAGE, "Přihlaste se.", AccessBarrier.LOGIN),
            "live_access_restricted",
        ),
        (
            LiveAttempt(
                PAGE, None, False, PAGE, "Ověřte, že nejste robot.", AccessBarrier.CHALLENGE
            ),
            "live_access_restricted",
        ),
        # Nobody said whether there was a barrier: unknown is never scored as open.
        (
            LiveAttempt(PAGE, None, False, PAGE, "Text.", AccessBarrier.UNKNOWN),
            "live_access_restricted",
        ),
        (_failed("http_401"), "live_access_restricted"),
        (_failed("http_402"), "live_access_restricted"),
        (_failed("http_403"), "live_access_restricted"),
        (_failed("http_451"), "live_access_restricted"),
        # A later live attempt may get past these.
        (_failed("http_429"), "live_transient"),
        (_failed("http_503"), "live_transient"),
        (_failed("connect_failed"), "live_transient"),
        (_failed("reset", uncertain=True), "live_uncertain"),
        # AIA's own refusal is not routed round by an archive.
        (_failed("url_internal_host"), "live_refused"),
        (_failed("class_a_url"), "live_refused"),
        (_failed("egress_route_not_approved"), "live_refused"),
        # A failure nobody named is not "dead".
        (_failed("http_400"), "live_failure_unrecognised"),
        (_failed("no_page"), "live_failure_unrecognised"),
    ],
)
def test_every_other_live_outcome_refuses_the_archive(attempt: LiveAttempt, refusal: str) -> None:
    decision = decide_archive_use(attempt, needed_quote=NEED)
    assert decision.permit is None and decision.refusal == refusal


def test_a_permit_is_only_issued_by_the_policy() -> None:
    with pytest.raises(ValueError):
        ArchivePermit(url=PAGE, basis=ArchiveBasis.DEAD, _issuer=object())
    with pytest.raises(ValueError):
        decide_archive_use(_failed("http_404"), needed_quote="  ")


def test_an_attempt_is_a_failure_or_a_whole_page() -> None:
    with pytest.raises(ValueError):
        LiveAttempt(PAGE, "http_404", False, PAGE, "text", AccessBarrier.NONE)
    with pytest.raises(ValueError):
        LiveAttempt(PAGE, None, False, PAGE, "text", None)
    with pytest.raises(ValueError):
        LiveAttempt(PAGE, None, True, PAGE, "text", AccessBarrier.NONE)


def _snapshot(text: str, final_url: str) -> SourceSnapshot:
    return SourceSnapshot(
        snapshot_id="SNP-" + "a" * 24,
        url=PAGE,
        canonical_url=final_url,
        final_url=final_url,
        redirects=(PAGE,) if final_url != PAGE else (),
        title="Fiktivní zpráva",
        retrieved_at=NOW,
        http_status=200,
        content_type="text/html",
        raw_sha256="0" * 64,
        raw_bytes=len(text),
        text=text,
        text_sha256="0" * 64,
        truncated=False,
        adapter="recorded-fetch-v1",
        request_id=None,
        retrieval_mode=RetrievalMode.RECORDED,
        instructions_detected=(),
    )


def test_the_gates_fetch_outcome_becomes_the_policys_live_attempt() -> None:
    dead = live_attempt(FetchOutcome(PAGE, None, "http_404", False), barrier=None)
    assert dead == _failed("http_404")
    moved = live_attempt(
        FetchOutcome(
            PAGE,
            FetchedPage(_snapshot("Jiný text.", "https://zpravy.example/nova"), None),
            None,
            False,
        ),
        barrier=AccessBarrier.NONE,
    )
    assert decide_archive_use(moved, needed_quote=NEED).permit is not None
    unstated = live_attempt(
        FetchOutcome(PAGE, FetchedPage(_snapshot("Jiný text.", PAGE), None), None, False),
        barrier=None,
    )
    assert unstated.barrier is AccessBarrier.UNKNOWN
    assert decide_archive_use(unstated, needed_quote=NEED).refusal == "live_access_restricted"


# --------------------------------------------------------------------------- the gate

ARCHIVE = "recorded-archive-v1"
DATASET = "recorded-dataset-v1"
CAPTURES = {
    "result": {
        "title": "Fiktivní záznamy archivu",
        "publisher": "Fiktivní archiv",
        "source_url": "https://archive.example/cdx",
        "columns": [{"key": "statuscode", "label": "HTTP status"}],
        "rows": [{"key": "c1", "label": "1. capture 20221230080000", "values": ["200"]}],
    },
    "raw": "[]",
}


def _route(tool: ToolKind, adapter_id: str) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"{tool.value}-recorded",
            provider="recorded",
            zone=ResidencyZone.EU,
            eu_processing_approved=True,
            excluded_from_training=True,
            retention_days=0,
            approved_for=frozenset(DataClass),
        ),
        tool=tool,
        adapter_id=adapter_id,
        retrieval_mode=RetrievalMode.RECORDED,
        price_usd_per_call=0.0,
    )


def _archive_connector() -> RecordedDatasetConnector:
    return RecordedDatasetConnector(
        connector_id=ARCHIVE,
        exchanges={f"{PAGE} period=2023": CAPTURES},
        clock=lambda: NOW,
        tool_kind=ToolKind.ARCHIVE_LOOKUP,
    )


def _gate(
    scope: Any, archive: RecordedDatasetConnector
) -> tuple[RetrievalGate, InMemoryToolLedger]:
    ledger = InMemoryToolLedger(budget_usd=1.0)
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH, "recorded-search-v1"),
            fetch_route=_route(ToolKind.WEB_FETCH, "recorded-fetch-v1"),
            search=RecordedSearch(adapter_id="recorded-search-v1", exchanges={}),
            fetcher=WebFetcher(
                transport=RecordedFetchTransport(pages={}),
                resolver=RecordedResolver(hosts={}),
                adapter_id="recorded-fetch-v1",
            ),
        ),
        scope=scope,
        meter=ledger,
        client_terms=(ClientTerm(term="Acme Corp", source="client.name"),),
        class_a_texts=(),
        clock=lambda: NOW,
        archives=(
            DatasetAccess(route=_route(ToolKind.ARCHIVE_LOOKUP, ARCHIVE), connector=archive),
        ),
    )
    return gate, ledger


QUERY = DatasetQuery(connector_id=ARCHIVE, dataset_id=PAGE, period="2023")


def test_with_its_permit_an_archive_lookup_is_journaled_and_answered(scoped: Any) -> None:
    connector = _archive_connector()
    gate, ledger = _gate(scoped.scope(), connector)
    permit = decide_archive_use(_failed("http_404"), needed_quote=NEED).permit
    outcome = gate.archive(
        QUERY, permit=permit, context_class=DataClass.CLASS_C_INTERNAL, track_id="T"
    )
    assert outcome.record.decision is QueryDecision.SENT and outcome.snapshot is not None
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.DISPATCHED, ToolOutcome.SUCCEEDED]
    assert {e.tool for e in ledger.events()} == {ToolKind.ARCHIVE_LOOKUP}
    assert connector.calls == [f"{PAGE} period=2023"]


def test_without_a_permit_for_this_url_the_archive_is_never_asked(scoped: Any) -> None:
    connector = _archive_connector()
    gate, ledger = _gate(scoped.scope(), connector)
    other = LiveAttempt(url="https://zpravy.example/jina", failure="http_404", uncertain=False)
    refused_live = decide_archive_use(_page(f"{NEED}"), needed_quote=NEED)
    for permit in (None, decide_archive_use(other, needed_quote=NEED).permit, refused_live.permit):
        outcome = gate.archive(
            QUERY, permit=permit, context_class=DataClass.CLASS_C_INTERNAL, track_id="T"
        )
        assert outcome.record.refusal == "archive_not_permitted" and outcome.snapshot is None
    assert connector.calls == []
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.REFUSED] * 3
    # The dataset path does not reach an archive at all.
    assert (
        gate.dataset(QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T").record.refusal
        == "dataset_connector_unavailable"
    )


def test_a_permitted_lookup_is_still_class_c_only(scoped: Any) -> None:
    connector = _archive_connector()
    gate, _ = _gate(scoped.scope(), connector)
    url = "https://zpravy.example/acme-corp-vysledky"
    permit = decide_archive_use(
        LiveAttempt(url=url, failure="http_410", uncertain=False), needed_quote=NEED
    ).permit
    outcome = gate.archive(
        DatasetQuery(connector_id=ARCHIVE, dataset_id=url),
        permit=permit,
        context_class=DataClass.CLASS_C_INTERNAL,
        track_id="T",
    )
    assert outcome.record.refusal == "dataset_class_c_only" and connector.calls == []


def test_an_archive_is_given_as_an_archive_and_a_dataset_as_a_dataset(scoped: Any) -> None:
    archive = _archive_connector()
    dataset = RecordedDatasetConnector(connector_id=DATASET, exchanges={})
    with pytest.raises(ValueError):  # an archive index on a dataset route
        DatasetAccess(route=_route(ToolKind.DATASET_QUERY, ARCHIVE), connector=archive)
    with pytest.raises(ValueError):  # a dataset connector on an archive route
        DatasetAccess(route=_route(ToolKind.ARCHIVE_LOOKUP, DATASET), connector=dataset)
    with pytest.raises(ValueError):
        RetrievalGate(
            retrieval=WebRetrieval(
                search_route=_route(ToolKind.WEB_SEARCH, "recorded-search-v1"),
                fetch_route=_route(ToolKind.WEB_FETCH, "recorded-fetch-v1"),
                search=RecordedSearch(adapter_id="recorded-search-v1", exchanges={}),
                fetcher=WebFetcher(
                    transport=RecordedFetchTransport(pages={}),
                    resolver=RecordedResolver(hosts={}),
                    adapter_id="recorded-fetch-v1",
                ),
            ),
            scope=scoped.scope(),
            meter=InMemoryToolLedger(budget_usd=1.0),
            client_terms=(),
            class_a_texts=(),
            datasets=(
                DatasetAccess(route=_route(ToolKind.ARCHIVE_LOOKUP, ARCHIVE), connector=archive),
            ),
        )
