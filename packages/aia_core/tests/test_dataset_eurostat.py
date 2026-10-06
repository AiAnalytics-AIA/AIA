"""Eurostat: one dataset, filtered by code, answers as a table cited by cell.

The fixture is FICTIONAL (invented codes, labels and values) in the shape of JSON-stat
2.0 without roles, as Eurostat's API Statistics is recorded to answer
(``docs/architecture/deep-research-connectors.md``; unverified). No network: the
transport is a double.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest

from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.datasets import DatasetQuery
from aia_core.domain.deep_research.grounding import ground_cell
from aia_core.infrastructure.dataset_connectors import dataset_snapshot
from aia_core.infrastructure.dataset_eurostat import EUROSTAT_CONNECTOR_ID, EurostatConnector
from aia_core.infrastructure.jsonstat import jsonstat_table
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedFetchTransport,
    RecordedResolver,
    ToolCallFailed,
)

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
PUBLIC = "93.184.215.14"
FIXTURE = Path(__file__).parent / "fixtures" / "dataset_connectors"
BODY = (FIXTURE / "eurostat_dataset_fictional.json").read_bytes()
BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/fikt_hh01"


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
        "headers": {"content-type": "application/json"},
        "body": body,
        "truncated": False,
    }
    fields.update(over)
    return FetchedResponse(**fields)


def _connector(response: FetchedResponse | None = None) -> tuple[EurostatConnector, _Transport]:
    transport = _Transport(response or _answer())
    return (
        EurostatConnector(
            transport=transport,
            resolver=RecordedResolver(hosts={"ec.europa.eu": [PUBLIC]}),
            clock=lambda: NOW,
        ),
        transport,
    )


def _query(**over: Any) -> DatasetQuery:
    return DatasetQuery.model_validate(
        {"connector_id": EUROSTAT_CONNECTOR_ID, "dataset_id": "fikt_hh01", **over}
    )


def test_one_get_to_the_dataset_with_its_filters_in_a_fixed_order() -> None:
    connector, transport = _connector()
    query = _query(
        filters=[
            {"dimension": "geo", "values": ["XA", "XB"]},
            {"dimension": "freq", "values": ["A"]},
        ],
        period="2024",
    )
    response = connector.query(query)
    [(url, address)] = transport.calls
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == BASE and address == PUBLIC
    # Filters by dimension, each value its own parameter, then the period.
    assert parse_qsl(parts.query) == [
        ("format", "JSON"),
        ("lang", "EN"),
        ("freq", "A"),
        ("geo", "XA"),
        ("geo", "XB"),
        ("time", "2024"),
    ]
    assert response.result.source_url == url and response.result.publisher == "Eurostat"
    assert response.result.licence is None  # unverified terms are not stamped
    assert connector.query(query).result == response.result  # deterministic


def test_the_cube_without_roles_becomes_rows_by_country_and_columns_by_year() -> None:
    result = _connector()[0].query(_query()).result
    assert result.title == "Fictional share of households with a fictional good"
    # "time" is the time dimension although the document declares no role.
    assert [(c.key, c.period) for c in result.columns] == [("2023", "2023"), ("2024", "2024")]
    assert [(r.key, r.label) for r in result.rows] == [
        ("A.PC_HH.XA", "Fictional country Alpha"),
        ("A.PC_HH.XB", "Fictional country Beta"),
    ]
    # The unit is a dimension, so it is a note -- never a guessed unit on a cell.
    assert "Unit of measure: Percentage of households" in result.notes
    assert all(r.unit is None for r in result.rows) and result.unit is None
    assert result.rows[0].values == ("41.50", "43.2")  # as published, not re-rounded
    assert result.rows[0].statuses == (None, "p")
    assert result.rows[1].values == ("37.0", None) and result.rows[1].statuses == (None, ":")


def test_a_number_grounds_to_its_cell_with_its_period_and_status() -> None:
    snapshot = dataset_snapshot(_connector()[0].query(_query()), retrieval_mode=RetrievalMode.LIVE)
    verdict = ground_cell(
        snapshot=snapshot,
        locator="fikt_hh01!A.PC_HH.XA/2024",
        quote="Fictional country Alpha | 2024 | period 2024 = 43.2 | status p",
    )
    assert verdict.grounded and verdict.cell is not None and verdict.cell.period == "2024"
    assert not ground_cell(
        snapshot=snapshot,
        locator="fikt_hh01!A.PC_HH.XB/2024",
        quote="Fictional country Beta | 2024 | period 2024 = 43.2",
    ).grounded


def test_a_category_the_answer_lacks_is_a_known_failure_never_a_wider_table() -> None:
    connector, transport = _connector()
    with pytest.raises(ToolCallFailed) as failed:
        connector.query(_query(filters=[{"dimension": "geo", "values": ["XC"]}]))
    assert failed.value.reason == "filter_category_unknown"
    assert failed.value.delivery is Delivery.RESPONDED and len(transport.calls) == 1


def test_a_declared_time_role_wins_over_the_providers_name() -> None:
    doc = json.loads(BODY)
    doc["role"] = {"time": ["geo"]}
    result = jsonstat_table(json.dumps(doc).encode(), query=_query(), time_dimension="time")
    assert [c.get("period") for c in result["columns"]] == [
        "Fictional country Alpha",
        "Fictional country Beta",
    ]


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"dataset_id": "fikt.hh01"}, "dataset_id_invalid"),
        ({"dataset_id": "x" * 65}, "dataset_id_invalid"),
        ({"filters": [{"dimension": "lang", "values": ["CS"]}]}, "filter_invalid"),
        ({"filters": [{"dimension": "time", "values": ["2024"]}]}, "filter_invalid"),
        ({"filters": [{"dimension": "geo.x", "values": ["XA"]}]}, "filter_invalid"),
        ({"filters": [{"dimension": "geo", "values": ["X:A"]}]}, "filter_invalid"),
        ({"connector_id": "csu-datastat-1"}, "connector_mismatch"),
    ],
)
def test_a_query_this_connector_cannot_put_is_never_sent(over: dict[str, Any], reason: str) -> None:
    connector, transport = _connector()
    with pytest.raises(ToolCallFailed) as failed:
        connector.query(_query(**over))
    assert failed.value.reason == reason and failed.value.delivery is Delivery.NOT_SENT
    assert transport.calls == []


def _variant(**change: Any) -> bytes:
    doc = json.loads(BODY)
    doc.update(change)
    return json.dumps(doc).encode()


def _without_time() -> bytes:
    doc = json.loads(BODY)
    doc["id"] = ["freq", "unit", "geo", "period"]
    doc["dimension"]["period"] = doc["dimension"].pop("time")
    return json.dumps(doc).encode()


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (
            _answer(
                json.dumps(
                    {"warning": {"status": 413, "label": "ASYNCHRONOUS_RESPONSE. Fictional."}}
                ).encode()
            ),
            "dataset_asynchronous",
        ),
        (_answer(b'{"error": {"status": 400, "label": "x"}}'), "response_contract"),
        (_answer(b"<html>not json</html>"), "response_contract"),
        (_answer(_variant(version="1.0")), "response_contract"),
        (_answer(_without_time()), "response_contract"),
        (_answer(headers={"content-type": "text/csv"}), "content_type"),
        (_answer(status=404), "http_404"),
        (_answer(status=302, headers={"location": "https://ec.europa.eu/x"}), "redirect_refused"),
        (_answer(truncated=True), "body_too_large"),
    ],
)  # fmt: skip
def test_an_answer_outside_the_format_is_refused(response: FetchedResponse, reason: str) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(response)[0].query(_query())
    assert failed.value.reason == reason and failed.value.delivery is Delivery.RESPONDED


def test_the_connector_requires_a_live_transport() -> None:
    with pytest.raises(ValueError):
        EurostatConnector(
            transport=RecordedFetchTransport(pages={}), resolver=RecordedResolver(hosts={})
        )
