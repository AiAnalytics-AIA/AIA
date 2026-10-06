"""Dataset tables: rendered deterministically, cited by cell, asked through the gate.

Plan ``deep-research-web-search.md`` §§ 5.3, 7 (rung 4) and 8.2. Every table here is
FICTIONAL: invented labels and values in the shape a connector produces. No network.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.application.web_retrieval import DatasetAccess, RetrievalGate, WebRetrieval
from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.contracts import (
    ClientTerm,
    QuarantineReason,
    QueryDecision,
    RetrievalMode,
    SourceSnapshot,
    digest,
)
from aia_core.domain.deep_research.datasets import (
    DATASET_MEDIA_TYPE,
    MAX_DATASET_CELLS,
    NO_VALUE,
    DatasetQuery,
    DatasetResult,
    parse_locator,
)
from aia_core.domain.deep_research.grounding import GroundableSource, ground, ground_cell
from aia_core.domain.deep_research.steps import SnapshotArtifact
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
)
from aia_core.domain.deep_research.web import FetchRefused
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.dataset_connectors import (
    DatasetResponse,
    HostScopedClient,
    RecordedDatasetConnector,
    dataset_snapshot,
)
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedFetchTransport,
    RecordedResolver,
    RecordedSearch,
    ToolCallFailed,
    WebFetcher,
)
from aia_core.infrastructure.web_retrieval_live import HostPinnedHttpsTransport

NOW = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
PUBLIC = "93.184.215.14"
CONNECTOR = "recorded-dataset-v1"
QUERY = DatasetQuery(connector_id=CONNECTOR, dataset_id="FIKT01", period="2024")


def _fields(**over: Any) -> dict[str, Any]:
    """A FICTIONAL two-region, two-year table of an invented indicator."""
    fields: dict[str, Any] = {
        "title": "Fiktivní ukazatel podle krajů",
        "publisher": "Fiktivní statistický úřad",
        "licence": "CC BY 4.0",
        "source_url": "https://data.example/api/FIKT01",
        "unit": "%",
        "columns": [
            {"key": "2023", "label": "2023", "period": "2023"},
            {"key": "2024", "label": "2024", "period": "2024"},
        ],
        "rows": [
            {"key": "R1", "label": "Kraj Alfa", "values": ["3,1", "3,15"], "statuses": [None, "p"]},
            {"key": "R2", "label": "Kraj Beta", "values": ["2,9", None]},
        ],
    }
    fields.update(over)
    return fields


def _result(**over: Any) -> DatasetResult:
    return DatasetResult.model_validate(
        {
            "connector_id": CONNECTOR,
            "dataset_id": "FIKT01",
            "query": QUERY,
            "retrieved_at": NOW,
            **_fields(**over),
        }
    )


def _snapshot(result: DatasetResult | None = None) -> SourceSnapshot:
    response = DatasetResponse(
        result=result or _result(),
        raw_sha256="0" * 64,
        raw_bytes=0,
        http_status=200,
        provider_request_id=None,
    )
    return dataset_snapshot(response, retrieval_mode=RetrievalMode.RECORDED)


# --------------------------------------------------------------------------- the table


def test_the_rendering_is_one_line_per_cell_with_its_headers_and_is_deterministic() -> None:
    text = _result().render()
    assert text.splitlines() == [
        "Dataset FIKT01: Fiktivní ukazatel podle krajů",
        "Publisher: Fiktivní statistický úřad",
        "Licence: CC BY 4.0",
        f"Connector: {CONNECTOR}",
        "Query: FIKT01 period=2024",
        "[FIKT01!R1/2023] Kraj Alfa | 2023 | period 2023 | unit % = 3,1",
        "[FIKT01!R1/2024] Kraj Alfa | 2024 | period 2024 | unit % = 3,15 | status p",
        "[FIKT01!R2/2023] Kraj Beta | 2023 | period 2023 | unit % = 2,9",
        f"[FIKT01!R2/2024] Kraj Beta | 2024 | period 2024 | unit % = {NO_VALUE}",
    ]
    assert _result().render() == text
    # The same table, retrieved another day, is the same snapshot.
    later = _result()
    assert _snapshot(later).snapshot_id == _snapshot().snapshot_id
    assert _snapshot(_result(rows=[_fields()["rows"][0]])).snapshot_id != _snapshot().snapshot_id


def test_a_licence_the_provider_does_not_state_is_said_never_guessed() -> None:
    assert "Licence: not stated by the provider" in _result(licence=None).render()


def test_a_locator_carries_the_cells_labels_unit_and_period() -> None:
    cell = _result().cell("FIKT01!R1/2024")
    assert cell is not None
    assert (cell.row_label, cell.column_label, cell.unit, cell.period, cell.value, cell.status) == (
        "Kraj Alfa",
        "2024",
        "%",
        "2024",
        "3,15",
        "p",
    )
    assert parse_locator(cell.locator) == ("FIKT01", "R1", "2024")
    assert _result().cell("FIKT01!R9/2024") is None
    assert _result().cell("OTHER!R1/2024") is None
    assert parse_locator("no-separator") is None


def test_unit_and_period_come_from_the_row_when_the_row_fixes_them() -> None:
    table = _result(
        unit=None,
        columns=[{"key": "v", "label": "Hodnota", "period": "2024"}],
        rows=[
            {"key": "a", "label": "Podíl", "unit": "%", "values": ["12,5"]},
            {"key": "b", "label": "Počet", "unit": "tis. osob", "values": ["410"]},
        ],
    )
    units = {c.row_key: (c.unit, c.period) for c in table.cells()}
    assert units == {"a": ("%", "2024"), "b": ("tis. osob", "2024")}


@pytest.mark.parametrize(
    "over",
    [
        # A unit set at two levels is ambiguous.
        {"columns": [{"key": "c", "label": "C", "unit": "%"}], "rows": []},
        # Two rows with one label would make two cells read the same.
        {
            "rows": [
                {"key": "a", "label": "Stejný", "values": ["1", "2"]},
                {"key": "b", "label": "Stejný", "values": ["3", "4"]},
            ]
        },
        {"rows": [{"key": "a", "label": "Krátký", "values": ["1"]}]},
        {"rows": [{"key": "a/b", "label": "Lomítko", "values": ["1", "2"]}]},
        {"rows": [{"key": "a", "label": "Dva\nřádky", "values": ["1", "2"]}]},
        {"rows": [{"key": "a", "label": "Hodnota", "values": ["1\n2", "2"]}]},
        {"source_url": "http://data.example/plain"},
    ],
)
def test_a_table_that_cannot_be_cited_cell_by_cell_is_refused(over: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _result(**over)


def test_a_table_beyond_the_cell_cap_is_refused_not_truncated() -> None:
    rows = [{"key": f"r{i}", "label": f"Řádek {i}", "values": ["1", "2"]} for i in range(2501)]
    assert MAX_DATASET_CELLS < 2501 * 2
    with pytest.raises(ValidationError):
        _result(rows=rows)


def test_a_result_answers_its_own_query() -> None:
    with pytest.raises(ValidationError):
        DatasetResult.model_validate(
            {
                "connector_id": CONNECTOR,
                "dataset_id": "JINY01",
                "query": QUERY,
                "retrieved_at": NOW,
                **_fields(),
            }
        )


def test_the_query_text_is_deterministic_and_filters_are_codes() -> None:
    query = DatasetQuery(
        connector_id="csu-datastat-1",
        dataset_id="FIKT01",
        filters=(
            {"dimension": "uzemi", "values": ("CZ010", "CZ020")},
            {"dimension": "pohlavi", "values": ("1",)},
        ),
        period="2024",
    )
    assert query.text() == "FIKT01 pohlavi=1 uzemi=CZ010,CZ020 period=2024"
    with pytest.raises(ValidationError):
        DatasetQuery(connector_id="c-1", dataset_id="x!y")
    with pytest.raises(ValidationError):
        DatasetQuery(
            connector_id="c-1", dataset_id="x", filters=({"dimension": "d", "values": ("a b",)},)
        )


# --------------------------------------------------------------------------- the snapshot


def test_a_page_snapshot_serialises_and_hashes_exactly_as_before_tables() -> None:
    """Pinned on ``origin/develop`` @ 757154e, before ``dataset`` existed."""
    snapshot = SourceSnapshot(
        snapshot_id="SNP-" + "a" * 24,
        url="https://stats.example/a",
        canonical_url="https://stats.example/a",
        final_url="https://stats.example/a",
        redirects=(),
        title="T",
        retrieved_at=datetime(2026, 9, 27, 12, tzinfo=UTC),
        http_status=200,
        content_type="text/html",
        raw_sha256="b" * 64,
        raw_bytes=10,
        text="Spotřeba vzrostla o 12,5 %.",
        text_sha256="c" * 64,
        truncated=False,
        adapter="recorded-fetch-v1",
        request_id=None,
        retrieval_mode=RetrievalMode.RECORDED,
        instructions_detected=(),
    )
    assert "dataset" not in snapshot.model_dump(mode="json")
    assert "dataset" not in snapshot.model_dump_json()
    assert (
        digest(snapshot.model_dump(mode="json"))
        == "068ca763b0877caf5b80ffe4e2951a0c9e42ea2314bcd08187541eb4dd8fc738"
    )
    artifact = SnapshotArtifact(
        kind="deep_research_source_snapshot", snapshot=snapshot, published=None
    )
    assert (
        digest(artifact.model_dump(mode="json"))
        == "21a84308428af26fee713aa3a9c644a5979f9d6bfb39bb93bb82bd356e59d2fa"
    )
    assert SourceSnapshot.model_validate(snapshot.model_dump(mode="json")) == snapshot


def test_a_dataset_snapshot_is_its_rendering_and_round_trips_with_its_table() -> None:
    snapshot = _snapshot()
    assert snapshot.content_type == DATASET_MEDIA_TYPE and snapshot.dataset is not None
    assert snapshot.text == snapshot.dataset.render() and not snapshot.truncated
    stored = SnapshotArtifact(
        kind="deep_research_source_snapshot", snapshot=snapshot, published=None
    ).model_dump(mode="json")
    assert SnapshotArtifact.model_validate(stored).snapshot == snapshot
    tampered = {**snapshot.model_dump(mode="json"), "text": snapshot.text.replace("3,1", "4,1")}
    with pytest.raises(ValidationError):
        SourceSnapshot.model_validate(tampered)
    tableless = {**snapshot.model_dump(mode="json"), "dataset": None}
    with pytest.raises(ValidationError):
        SourceSnapshot.model_validate(tableless)


# --------------------------------------------------------------------------- grounding


def test_a_cell_quote_grounds_to_its_cell_with_its_period() -> None:
    snapshot = _snapshot()
    quote = "Kraj Alfa | 2024 | period 2024 | unit % = 3,15 | status p"
    verdict = ground_cell(snapshot=snapshot, locator="FIKT01!R1/2024", quote=quote)
    assert verdict.grounded and verdict.cell is not None and verdict.span is not None
    assert verdict.cell.period == "2024" and verdict.cell.status == "p"
    with_locator = ground_cell(
        snapshot=snapshot, locator="FIKT01!R1/2024", quote="[FIKT01!R1/2024] " + quote
    )
    assert with_locator.grounded and with_locator.span == verdict.span
    # The quote is in the text, so the generic check grounds it as well.
    generic = ground(
        source_ref=snapshot.snapshot_id,
        quote=quote,
        claim="Ukazatel v kraji Alfa byl v roce 2024 předběžně 3,15 %.",
        sources={
            snapshot.snapshot_id: GroundableSource(
                ref=snapshot.snapshot_id, text=snapshot.text, instructions_detected=()
            )
        },
    )
    assert generic.grounded


@pytest.mark.parametrize(
    ("locator", "quote", "detail"),
    [
        # Another cell's line, cited under this locator.
        (
            "FIKT01!R1/2024",
            "Kraj Beta | 2023 | period 2023 | unit % = 2,9",
            "the quote is the cell FIKT01!R2/2023",
        ),
        # A value cut short: 3,1 is a prefix of 3,15.
        ("FIKT01!R1/2024", "Kraj Alfa | 2024 | period 2024 | unit % = 3,1", "as the table"),
        # The right value under the wrong year.
        ("FIKT01!R1/2023", "Kraj Alfa | 2023 | period 2023 | unit % = 3,15", "as the table"),
        ("FIKT01!R7/2024", "Kraj Alfa | 2024 | period 2024 | unit % = 3,15", "not a cell"),
    ],
)
def test_a_wrong_cell_does_not_ground(locator: str, quote: str, detail: str) -> None:
    verdict = ground_cell(snapshot=_snapshot(), locator=locator, quote=quote)
    assert not verdict.grounded and verdict.failure is QuarantineReason.UNGROUNDED_EXCERPT
    assert detail in verdict.detail


def test_a_page_has_no_cells() -> None:
    fetcher = WebFetcher(
        transport=RecordedFetchTransport(
            pages={"https://stats.example/a": {"body": "<p>Podíl byl 3,1 % v roce 2024.</p>"}}
        ),
        resolver=RecordedResolver(hosts={"stats.example": [PUBLIC]}),
        adapter_id="recorded-fetch-v1",
        clock=lambda: NOW,
    )
    page = fetcher.fetch("https://stats.example/a").snapshot
    verdict = ground_cell(snapshot=page, locator="FIKT01!R1/2024", quote="Podíl byl 3,1 %")
    assert (
        verdict.failure is QuarantineReason.UNGROUNDED_EXCERPT and "not a table" in verdict.detail
    )


# --------------------------------------------------------------------------- connectors


class _Transport:
    def __init__(self, response: FetchedResponse | BaseException) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        self.calls.append((url, address))
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


def _client(
    response: FetchedResponse | BaseException, *, addresses: tuple[str, ...] = (PUBLIC,)
) -> tuple[HostScopedClient, _Transport]:
    transport = _Transport(response)
    return (
        HostScopedClient(
            host="data.example",
            transport=transport,
            resolver=RecordedResolver(hosts={"data.example": list(addresses)}),
            media_types=("application/json",),
            max_bytes=1000,
        ),
        transport,
    )


def _ok(**over: Any) -> FetchedResponse:
    fields: dict[str, Any] = {
        "status": 200,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": b"{}",
        "truncated": False,
    }
    fields.update(over)
    return FetchedResponse(**fields)


def test_the_client_reaches_its_one_host_at_the_checked_address() -> None:
    client, transport = _client(_ok())
    assert client.get("https://data.example/api/x").status == 200
    assert transport.calls == [("https://data.example/api/x", PUBLIC)]


@pytest.mark.parametrize(
    ("url", "response", "addresses", "reason", "delivery"),
    [
        ("https://other.example/x", _ok(), (PUBLIC,), "refused_host_scope", Delivery.NOT_SENT),
        ("http://data.example/x", _ok(), (PUBLIC,), "refused_host_scope", Delivery.NOT_SENT),
        (
            "https://data.example/x",
            _ok(),
            (PUBLIC, "10.0.0.5"),
            "refused_address_not_public",
            Delivery.NOT_SENT,
        ),
        (
            "https://data.example/x",
            FetchRefused("x", reason="host_scope"),
            (PUBLIC,),
            "refused_host_scope",
            Delivery.NOT_SENT,
        ),
        ("https://data.example/x", _ok(status=503), (PUBLIC,), "http_503", Delivery.RESPONDED),
        (
            "https://data.example/x",
            _ok(status=302, headers={"location": "https://evil.example/"}),
            (PUBLIC,),
            "redirect_refused",
            Delivery.RESPONDED,
        ),
        ("https://data.example/x", _ok(truncated=True), (PUBLIC,), "body_too_large",
         Delivery.RESPONDED),
        (
            "https://data.example/x",
            _ok(headers={"content-type": "text/html"}),
            (PUBLIC,),
            "content_type",
            Delivery.RESPONDED,
        ),
        (
            "https://data.example/x",
            ToolCallFailed("reset", reason="transport_failed", delivery=Delivery.UNKNOWN),
            (PUBLIC,),
            "transport_failed",
            Delivery.UNKNOWN,
        ),
        (
            "https://data.example/x",
            RuntimeError("https://data.example/x?secret"),
            (PUBLIC,),
            "transport_error",
            Delivery.UNKNOWN,
        ),
    ],
)  # fmt: skip
def test_every_client_failure_is_a_tool_call_failed_with_its_delivery(
    url: str,
    response: FetchedResponse | BaseException,
    addresses: tuple[str, ...],
    reason: str,
    delivery: Delivery,
) -> None:
    client, transport = _client(response, addresses=addresses)
    with pytest.raises(ToolCallFailed) as failed:
        client.get(url)
    assert failed.value.reason == reason and failed.value.delivery is delivery
    assert "secret" not in str(failed.value)  # fixed text: never the URL or a library's message
    if delivery is Delivery.NOT_SENT and reason != "refused_host_scope":
        assert transport.calls == []


def test_a_live_client_refuses_a_recorded_transport() -> None:
    with pytest.raises(ValueError):
        HostScopedClient(
            host="data.example",
            transport=RecordedFetchTransport(pages={}),
            resolver=RecordedResolver(hosts={}),
            media_types=("application/json",),
            max_bytes=10,
        )


def test_the_pinned_transport_is_scoped_to_its_one_host() -> None:
    transport = HostPinnedHttpsTransport(host="data.example", accept="application/json")
    with pytest.raises(FetchRefused) as refused:
        transport.get("https://other.example/", address=PUBLIC, max_bytes=10)
    assert refused.value.reason == "host_scope"
    with pytest.raises(FetchRefused):
        transport.get("https://data.example/", address="127.0.0.1", max_bytes=10)
    with pytest.raises(ValueError):
        HostPinnedHttpsTransport(host="data.example/path", accept="application/json")


# --------------------------------------------------------------------------- the gate


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


RECORDED = {
    "FIKT01 period=2024": {"result": _fields(), "raw": '{"fiktivni": true}', "request_id": "r-1"},
    "LOST01": {"fail": "uncertain"},
    "BROKEN01": {"fail": "known"},
}


def _gate(scope: Any) -> tuple[RetrievalGate, InMemoryToolLedger, RecordedDatasetConnector]:
    connector = RecordedDatasetConnector(
        connector_id=CONNECTOR, exchanges=RECORDED, clock=lambda: NOW
    )
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
        datasets=(
            DatasetAccess(route=_route(ToolKind.DATASET_QUERY, CONNECTOR), connector=connector),
        ),
    )
    return gate, ledger, connector


def test_a_dataset_query_is_journaled_around_its_call_and_returns_the_table(scoped: Any) -> None:
    gate, ledger, connector = _gate(scoped.scope())
    outcome = gate.dataset(QUERY, context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.record.decision is QueryDecision.SENT and outcome.record.hits == 2
    assert outcome.record.text == "FIKT01 period=2024" and not outcome.uncertain
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.DISPATCHED, ToolOutcome.SUCCEEDED]
    assert {e.tool for e in ledger.events()} == {ToolKind.DATASET_QUERY}
    assert ledger.events()[1].provider_request_id == "r-1"
    assert outcome.snapshot is not None and outcome.snapshot.adapter == CONNECTOR
    assert outcome.snapshot.retrieval_mode is RetrievalMode.RECORDED
    assert ground_cell(
        snapshot=outcome.snapshot,
        locator="FIKT01!R2/2023",
        quote="Kraj Beta | 2023 | period 2023 | unit % = 2,9",
    ).grounded
    assert connector.calls == ["FIKT01 period=2024"]


@pytest.mark.parametrize(
    ("dataset_id", "filters", "context", "reason"),
    [
        # A client term in the dataset id or in a filter raises the query to Class B.
        ("Acme-Corp-sales", (), DataClass.CLASS_C_INTERNAL, "dataset_class_c_only"),
        (
            "FIKT01",
            ({"dimension": "znacka", "values": ("AcmeCorp",)},),
            DataClass.CLASS_C_INTERNAL,
            "dataset_class_c_only",
        ),
        # A query written from client-derived context is never lowered.
        ("FIKT01", (), DataClass.CLASS_B_DERIVED_CLIENT, "dataset_class_c_only"),
        ("FIKT01", (), DataClass.CLASS_A_CLIENT_CONFIDENTIAL, "class_a_query"),
    ],
)
def test_only_a_class_c_dataset_query_leaves(
    scoped: Any, dataset_id: str, filters: tuple[Any, ...], context: DataClass, reason: str
) -> None:
    gate, ledger, connector = _gate(scoped.scope())
    query = DatasetQuery(connector_id=CONNECTOR, dataset_id=dataset_id, filters=filters)
    outcome = gate.dataset(query, context_class=context, track_id="T")
    assert outcome.record.decision is QueryDecision.REFUSED and outcome.record.refusal == reason
    assert outcome.record.data_class is not DataClass.CLASS_C_INTERNAL
    assert connector.calls == [] and outcome.snapshot is None
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.REFUSED]
    assert ledger.events()[0].tool is ToolKind.DATASET_QUERY


def test_an_unknown_connector_is_refused_and_nothing_is_journaled(scoped: Any) -> None:
    gate, ledger, connector = _gate(scoped.scope())
    outcome = gate.dataset(
        DatasetQuery(connector_id="csu-datastat-1", dataset_id="FIKT01"),
        context_class=DataClass.CLASS_C_INTERNAL,
        track_id="T",
    )
    assert outcome.record.refusal == "dataset_connector_unavailable"
    assert ledger.events() == () and connector.calls == []


@pytest.mark.parametrize(
    ("dataset_id", "outcome_kind", "uncertain"),
    [
        ("LOST01", ToolOutcome.UNCERTAIN, True),
        ("BROKEN01", ToolOutcome.FAILED, False),
        ("UNRECORDED01", ToolOutcome.FAILED, False),
    ],
)
def test_a_failed_dataset_call_is_journaled_with_its_delivery(
    scoped: Any, dataset_id: str, outcome_kind: ToolOutcome, uncertain: bool
) -> None:
    gate, ledger, _ = _gate(scoped.scope())
    outcome = gate.dataset(
        DatasetQuery(connector_id=CONNECTOR, dataset_id=dataset_id),
        context_class=DataClass.CLASS_C_INTERNAL,
        track_id="T",
    )
    assert outcome.record.decision is QueryDecision.SENT and outcome.snapshot is None
    assert outcome.uncertain is uncertain and outcome.record.failure is not None
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.DISPATCHED, outcome_kind]


def test_a_dataset_route_must_name_its_connector_and_share_its_mode() -> None:
    connector = RecordedDatasetConnector(connector_id=CONNECTOR, exchanges={})
    with pytest.raises(ValueError):
        DatasetAccess(route=_route(ToolKind.WEB_SEARCH, CONNECTOR), connector=connector)
    with pytest.raises(ValueError):
        DatasetAccess(route=_route(ToolKind.DATASET_QUERY, "other-v1"), connector=connector)
    live = ToolRoute(
        route=_route(ToolKind.DATASET_QUERY, CONNECTOR).route,
        tool=ToolKind.DATASET_QUERY,
        adapter_id=CONNECTOR,
        retrieval_mode=RetrievalMode.LIVE,
        price_usd_per_call=0.0,
    )
    with pytest.raises(ValueError):
        DatasetAccess(route=live, connector=connector)
