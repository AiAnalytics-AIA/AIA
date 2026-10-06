"""NKOD: a catalogue record, asked by one fixed SELECT, becomes a table of distributions.

The fixture is FICTIONAL (invented IRIs, titles and URLs) in the shape of W3C SPARQL
1.1 Query Results JSON over DCAT terms (``docs/architecture/
deep-research-connectors.md``). No network: the transport is a double.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.datasets import DatasetQuery
from aia_core.domain.deep_research.grounding import ground_cell
from aia_core.infrastructure.dataset_connectors import dataset_snapshot
from aia_core.infrastructure.dataset_nkod import NKOD_CONNECTOR_ID, NkodConnector, nkod_query
from aia_core.infrastructure.web_retrieval import FetchedResponse, RecordedResolver, ToolCallFailed

NOW = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
PUBLIC = "93.184.215.14"
BODY = (
    Path(__file__).parent / "fixtures" / "dataset_connectors" / "nkod_dataset_fictional.json"
).read_bytes()
IRI = "https://lkod.example/datové-sady/navstevnici"


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
        "headers": {"content-type": "application/sparql-results+json; charset=utf-8"},
        "body": body,
        "truncated": False,
    }
    fields.update(over)
    return FetchedResponse(**fields)


def _connector(response: FetchedResponse | None = None) -> tuple[NkodConnector, _Transport]:
    transport = _Transport(response or _answer())
    return (
        NkodConnector(
            transport=transport,
            resolver=RecordedResolver(hosts={"data.gov.cz": [PUBLIC]}),
            clock=lambda: NOW,
        ),
        transport,
    )


def _query(**over: Any) -> DatasetQuery:
    return DatasetQuery.model_validate(
        {"connector_id": NKOD_CONNECTOR_ID, "dataset_id": IRI, **over}
    )


def test_one_fixed_select_to_the_catalogues_endpoint() -> None:
    connector, transport = _connector()
    connector.query(_query())
    [(url, address)] = transport.calls
    parts = urlsplit(url)
    assert (parts.scheme, parts.netloc, parts.path, address) == (
        "https",
        "data.gov.cz",
        "/sparql",
        PUBLIC,
    )
    assert parse_qs(parts.query) == {"query": [nkod_query(IRI)]}
    assert f"<{IRI}> a dcat:Dataset" in nkod_query(IRI)


def test_the_record_becomes_one_row_per_distribution() -> None:
    result = _connector()[0].query(_query()).result
    assert result.title == "Fiktivní počty návštěvníků"  # the Czech title first
    assert result.licence is None  # the catalogue's own terms are not stamped
    assert [r.label for r in result.rows] == [
        "https://lkod.example/distribuce/1",
        "https://lkod.example/distribuce/2",
    ]
    first, second = result.rows
    # Two bindings (two title languages) for one distribution are one row.
    assert first.values[2] == "https://lkod.example/soubory/navstevnici.csv"
    assert first.values[4] is None and second.values[1] is None
    assert second.values[4] == "https://creativecommons.org/licenses/by/4.0/"
    assert "Poskytovatel (dct:publisher): https://rpp.example/ovm/00000001" in result.notes
    assert "Název datové sady: Fictional visitor counts" in result.notes


def test_a_distributions_licence_grounds_to_its_cell() -> None:
    snapshot = dataset_snapshot(_connector()[0].query(_query()), retrieval_mode=RetrievalMode.LIVE)
    verdict = ground_cell(
        snapshot=snapshot,
        locator=f"{IRI}!d2/license",
        quote="https://lkod.example/distribuce/2 | Licence (dct:license) = "
        "https://creativecommons.org/licenses/by/4.0/",
    )
    assert verdict.grounded
    assert not ground_cell(
        snapshot=snapshot,
        locator=f"{IRI}!d1/license",
        quote="https://lkod.example/distribuce/2 | Licence (dct:license) = "
        "https://creativecommons.org/licenses/by/4.0/",
    ).grounded


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"filters": [{"dimension": "x", "values": ["y"]}]}, "filters_unsupported"),
        ({"period": "2024"}, "filters_unsupported"),
        ({"dataset_id": "http://lkod.example/plain"}, "dataset_id_invalid"),
        ({"dataset_id": "https://localhost/internal"}, "dataset_id_invalid"),
        ({"dataset_id": "urn:uuid:1234"}, "dataset_id_invalid"),
        ({"connector_id": "csu-datastat-1"}, "connector_mismatch"),
    ],
)
def test_a_query_this_connector_cannot_put_is_never_sent(over: dict[str, Any], reason: str) -> None:
    connector, transport = _connector()
    with pytest.raises(ToolCallFailed) as failed:
        connector.query(_query(**over))
    assert failed.value.reason == reason and failed.value.delivery is Delivery.NOT_SENT
    assert transport.calls == []


def test_an_iri_cannot_close_the_query() -> None:
    # Every character that could end the IRIREF is refused by the query contract.
    for bad in (
        "https://x.example/a>b",
        "https://x.example/a b",
        'https://x.example/"',
        "https://x.example/{",
    ):
        with pytest.raises(ValueError):
            _query(dataset_id=bad)


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b"not json", "response_contract"),
        (json.dumps({"results": []}).encode(), "response_contract"),
        (json.dumps({"results": {"bindings": [{"title": "bare"}]}}).encode(), "response_contract"),
        (json.dumps({"results": {"bindings": []}}).encode(), "dataset_not_found"),
        (
            json.dumps(
                {"results": {"bindings": [{"distribution": {"type": "uri", "value": "x"}}] * 400}}
            ).encode(),
            "dataset_too_large",
        ),
    ],
)
def test_an_answer_outside_the_results_format_is_refused(body: bytes, reason: str) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(_answer(body))[0].query(_query())
    assert failed.value.reason == reason and failed.value.delivery is Delivery.RESPONDED


def test_an_answer_of_another_type_is_refused() -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(_answer(headers={"content-type": "text/html"}))[0].query(_query())
    assert failed.value.reason == "content_type"
