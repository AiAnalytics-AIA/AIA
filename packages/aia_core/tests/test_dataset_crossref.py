"""The Crossref connector: a work's update notices, read as its standing (chunk 46).

Fictional answers in the shape Crossref documents (unverified here; see the module).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest

from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.datasets import DatasetQuery
from aia_core.domain.deep_research.works import WorkStatus, resolve_status
from aia_core.infrastructure.dataset_crossref import (
    CROSSREF_CONNECTOR_ID,
    CrossrefConnector,
    crossref_notices,
)
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedResolver,
    ToolCallFailed,
)

NOW = datetime(2026, 10, 8, 9, 0, tzinfo=UTC)
PUBLIC = "93.184.215.14"
DOI = "10.99999/fikce.2024.001"
CONTACT = "provoz@aia.example"


def _work(*updates: dict[str, Any], doi: str = DOI.upper()) -> bytes:
    message: dict[str, Any] = {"DOI": doi, "title": ["Fiktivní studie spotřeby"], "type": "x"}
    if updates:
        message["updated-by"] = list(updates)
    return json.dumps({"status": "ok", "message-type": "work", "message": message}).encode()


def _update(kind: str, **over: Any) -> dict[str, Any]:
    return {
        "type": kind,
        "DOI": "10.99999/notice.7",
        "source": "retraction-watch",
        "updated": {"date-parts": [[2025, 3, 14]]},
        **over,
    }


class _Transport:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls: list[tuple[str, str]] = []

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        self.calls.append((url, address))
        return FetchedResponse(
            status=200,
            headers={"content-type": "application/json"},
            body=self.body,
            truncated=False,
        )


def _connector(body: bytes, *, mailto: str | None = CONTACT) -> tuple[Any, _Transport]:
    transport = _Transport(body)
    connector = CrossrefConnector(
        transport=transport,
        resolver=RecordedResolver(hosts={"api.crossref.org": [PUBLIC]}),
        mailto=mailto,
        clock=lambda: NOW,
    )
    return connector, transport


def _query(dataset_id: str = f"doi:{DOI}", **over: Any) -> DatasetQuery:
    return DatasetQuery.model_validate(
        {"connector_id": CROSSREF_CONNECTOR_ID, "dataset_id": dataset_id, **over}
    )


def test_a_doi_is_one_get_to_crossref_with_the_contact_kept_out_of_the_record() -> None:
    connector, transport = _connector(_work())
    response = connector.query(_query())
    [(url, address)] = transport.calls
    parts = urlsplit(url)
    assert (parts.netloc, parts.path, address) == ("api.crossref.org", f"/works/{DOI}", PUBLIC)
    assert parse_qsl(parts.query) == [("mailto", CONTACT)]
    assert CONTACT not in response.result.source_url
    assert response.result.rows == ()
    assert crossref_notices(response.result) == ()


def test_a_retraction_and_a_correction_become_notices_and_the_retraction_stands() -> None:
    connector, _ = _connector(
        _work(_update("retraction"), _update("correction", source="publisher", DOI="10.99999/c.1"))
    )
    notices = crossref_notices(connector.query(_query()).result)
    assert [(n.status, n.notice_doi, n.source, n.issued) for n in notices] == [
        (WorkStatus.RETRACTED, "10.99999/notice.7", "retraction-watch", date(2025, 3, 14)),
        (WorkStatus.CORRECTED, "10.99999/c.1", "publisher", date(2025, 3, 14)),
    ]
    record = resolve_status(DOI, {CROSSREF_CONNECTOR_ID: notices}, checked_at=NOW)
    assert record.status is WorkStatus.RETRACTED and record.quarantines


def test_an_update_type_nobody_mapped_is_unknown_never_guessed() -> None:
    connector, _ = _connector(_work(_update("new_kind_of_notice")))
    (notice,) = crossref_notices(connector.query(_query()).result)
    assert notice.status is WorkStatus.UNKNOWN


def test_a_partial_retraction_is_a_concern_not_a_retraction_of_every_finding() -> None:
    connector, _ = _connector(_work(_update("partial_retraction")))
    (notice,) = crossref_notices(connector.query(_query()).result)
    assert notice.status is WorkStatus.EXPRESSION_OF_CONCERN


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        json.dumps({"status": "ok", "message": []}).encode(),
        _work(doi="10.99999/another.work"),
        json.dumps({"message": {"DOI": DOI, "updated-by": {"type": "retraction"}}}).encode(),
    ],
)
def test_an_answer_that_is_not_this_work_is_refused(body: bytes) -> None:
    connector, _ = _connector(body)
    with pytest.raises(ToolCallFailed):
        connector.query(_query())


@pytest.mark.parametrize(
    "query",
    [
        _query("works"),
        _query("doi:not-a-doi"),
        _query(filters=[{"dimension": "x", "values": ["y"]}]),
    ],
)
def test_a_query_crossref_cannot_answer_is_refused_before_it_is_sent(query: DatasetQuery) -> None:
    connector, transport = _connector(_work())
    with pytest.raises(ToolCallFailed):
        connector.query(query)
    assert transport.calls == []


def test_the_contact_is_one_plain_address() -> None:
    with pytest.raises(ValueError):
        _connector(_work(), mailto="not an address")
