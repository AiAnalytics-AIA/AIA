"""ČSÚ DataStat: a selection's JSON-stat answer becomes a table cited by cell.

The fixture is FICTIONAL (invented labels and values) in the shape of JSON-stat 2.0,
the format DataStat is recorded to answer in (``docs/architecture/
deep-research-connectors.md``; unverified). No network: the transport is a double.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.datasets import DatasetQuery
from aia_core.domain.deep_research.grounding import ground_cell
from aia_core.infrastructure.dataset_connectors import dataset_snapshot
from aia_core.infrastructure.dataset_datastat import DATASTAT_CONNECTOR_ID, DataStatConnector
from aia_core.infrastructure.jsonstat import jsonstat_table
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedFetchTransport,
    RecordedResolver,
    ToolCallFailed,
)

NOW = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
PUBLIC = "93.184.215.14"
FIXTURE = Path(__file__).parent / "fixtures" / "dataset_connectors"
BODY = (FIXTURE / "datastat_selection_fictional.json").read_bytes()
URL = "https://data.csu.gov.cz/api/dotaz/v1/data/vybery/FIKT01"


class _Transport:
    def __init__(self, response: FetchedResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        self.calls.append((url, address))
        return self.response


def _answer(body: bytes = BODY, **over: Any) -> FetchedResponse:
    fields: dict[str, Any] = {
        "status": 200,
        "headers": {"content-type": "application/json;charset=UTF-8"},
        "body": body,
        "truncated": False,
        "provider_request_id": "req-1",
    }
    fields.update(over)
    return FetchedResponse(**fields)


def _connector(response: FetchedResponse | None = None) -> tuple[DataStatConnector, _Transport]:
    transport = _Transport(response or _answer())
    return (
        DataStatConnector(
            transport=transport,
            resolver=RecordedResolver(hosts={"data.csu.gov.cz": [PUBLIC]}),
            clock=lambda: NOW,
        ),
        transport,
    )


def _query(**over: Any) -> DatasetQuery:
    return DatasetQuery.model_validate(
        {"connector_id": DATASTAT_CONNECTOR_ID, "dataset_id": "FIKT01", **over}
    )


def test_one_get_to_the_selection_on_the_one_host() -> None:
    connector, transport = _connector()
    response = connector.query(_query())
    assert transport.calls == [(URL, PUBLIC)]
    result = response.result
    assert result.source_url == URL and result.publisher == "Český statistický úřad"
    assert result.licence is None  # unverified terms are not stamped
    assert response.provider_request_id == "req-1" and response.raw_bytes == len(BODY)
    assert connector.retrieval_mode is RetrievalMode.LIVE


def test_the_cube_becomes_rows_by_territory_and_columns_by_year() -> None:
    result = _connector()[0].query(_query()).result
    assert result.title == "Fiktivní podíl domácností podle území"
    assert [(c.key, c.period) for c in result.columns] == [("2023", "2023"), ("2024", "2024")]
    assert [(r.key, r.label, r.unit) for r in result.rows] == [
        ("FIK01.CZ010", "Fiktivní kraj Alfa", "%"),
        ("FIK01.CZ020", "Fiktivní kraj Beta", "%"),
    ]
    assert "Ukazatel: Fiktivní podíl domácností" in result.notes
    # The number's JSON text, verbatim: 13.10 is not re-rounded to 13.1.
    assert result.rows[0].values == ("12.4", "13.10")
    assert result.rows[0].statuses == (None, "p")
    assert result.rows[1].values == ("9.8", None)


def test_a_number_grounds_to_its_dataset_cell_with_its_period() -> None:
    connector, _ = _connector()
    snapshot = dataset_snapshot(connector.query(_query()), retrieval_mode=RetrievalMode.LIVE)
    locator = "FIKT01!FIK01.CZ010/2024"
    verdict = ground_cell(
        snapshot=snapshot,
        locator=locator,
        quote="Fiktivní kraj Alfa | 2024 | period 2024 | unit % = 13.10 | status p",
    )
    assert verdict.grounded and verdict.cell is not None
    assert (verdict.cell.period, verdict.cell.unit, verdict.cell.status) == ("2024", "%", "p")
    wrong_year = ground_cell(
        snapshot=snapshot,
        locator="FIKT01!FIK01.CZ010/2023",
        quote="Fiktivní kraj Alfa | 2023 | period 2023 | unit % = 13.10",
    )
    assert not wrong_year.grounded


def test_filters_and_the_period_are_applied_to_the_answer_by_code() -> None:
    connector, transport = _connector()
    query = _query(filters=[{"dimension": "UZEMI", "values": ["CZ020"]}], period="2023")
    result = connector.query(query).result
    assert transport.calls == [(URL, PUBLIC)]  # the request is the selection, unchanged
    assert [c.key for c in result.columns] == ["2023"]
    # Nothing varies any more, so the one row is labelled by every category it fixes.
    assert [(r.label, r.values) for r in result.rows] == [
        ("Fiktivní podíl domácností / Fiktivní kraj Beta", ("9.8",))
    ]
    assert "Území: Fiktivní kraj Beta" in result.notes
    assert result.query == query


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"filters": [{"dimension": "VEK", "values": ["1"]}]}, "filter_dimension_unknown"),
        ({"filters": [{"dimension": "UZEMI", "values": ["CZ099"]}]}, "filter_category_unknown"),
        ({"period": "2019"}, "period_unknown"),
    ],
)
def test_a_filter_the_data_lacks_is_a_known_failure(over: dict[str, Any], reason: str) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector()[0].query(_query(**over))
    assert failed.value.reason == reason and failed.value.delivery is Delivery.RESPONDED


@pytest.mark.parametrize("dataset_id", ["a/b", "x" * 65, "FIKT%2F01", "FIKT.01"])
def test_a_selection_code_outside_the_path_rule_is_never_sent(dataset_id: str) -> None:
    connector, transport = _connector()
    with pytest.raises(ToolCallFailed) as failed:
        connector.query(_query(dataset_id=dataset_id))
    assert failed.value.delivery is Delivery.NOT_SENT and transport.calls == []


def test_a_query_for_another_connector_is_never_sent() -> None:
    connector, transport = _connector()
    with pytest.raises(ToolCallFailed) as failed:
        connector.query(DatasetQuery(connector_id="nkod-1", dataset_id="FIKT01"))
    assert failed.value.reason == "connector_mismatch" and transport.calls == []


def _variant(**change: Any) -> bytes:
    doc = json.loads(BODY)
    doc.update(change)
    return json.dumps(doc).encode()


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (_answer(b"<html>not json</html>"), "response_contract"),
        (_answer(_variant(version="1.0")), "response_contract"),
        (_answer(_variant(**{"class": "collection"})), "response_contract"),
        (_answer(_variant(size=[1, 2, 3])), "response_contract"),
        (_answer(_variant(value=[1, 2, 3])), "response_contract"),
        (_answer(_variant(value=[True, 2, 3, 4])), "response_contract"),
        (_answer(_variant(size=[1, 2, 2], id=["UKAZATEL", "UZEMI", "UZEMI"])), "response_contract"),
        (_answer(_variant(value=12.4)), "response_contract"),
        (_answer(_variant(role={"time": "CASR"})), "response_contract"),
        (_answer(headers={"content-type": "text/csv"}), "content_type"),
        (_answer(status=429), "http_429"),
        (_answer(status=301, headers={"location": "https://x.example/"}), "redirect_refused"),
        (_answer(truncated=True), "body_too_large"),
    ],
)  # fmt: skip
def test_an_answer_this_connector_does_not_hold_to_the_format_is_refused(
    response: FetchedResponse, reason: str
) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(response)[0].query(_query())
    assert failed.value.reason == reason and failed.value.delivery is Delivery.RESPONDED


def test_a_cube_beyond_the_cell_cap_is_refused() -> None:
    with pytest.raises(ToolCallFailed) as failed:
        jsonstat_table(BODY, query=_query(), max_cells=3)
    assert failed.value.reason == "dataset_too_large"


def test_the_connector_requires_a_live_transport() -> None:
    with pytest.raises(ValueError):
        DataStatConnector(
            transport=RecordedFetchTransport(pages={}), resolver=RecordedResolver(hosts={})
        )
