"""OpenAlex: a DOI's open-access locations, and a short works search, as tables.

The fixtures are FICTIONAL (invented ids, DOI, titles, hosts) in the shape OpenAlex's
own documentation gives for a ``Work`` and a list answer (``docs/architecture/
deep-research-connectors.md``). No network: the transport is a double.
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
from aia_core.infrastructure.dataset_openalex import (
    OPENALEX_CONNECTOR_ID,
    OpenAccessCopy,
    OpenAlexConnector,
    open_access_copies,
    openalex_retracted,
)
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedFetchTransport,
    RecordedResolver,
    ToolCallFailed,
)

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
PUBLIC = "93.184.215.14"
FIXTURE = Path(__file__).parent / "fixtures" / "dataset_connectors"
WORK = (FIXTURE / "openalex_work_fictional.json").read_bytes()
SEARCH = (FIXTURE / "openalex_search_fictional.json").read_bytes()
DOI = "10.99999/fikce.2024.001"
CONTACT = "provoz@aia.example"


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


def _answer(body: bytes = WORK, **over: Any) -> FetchedResponse:
    fields: dict[str, Any] = {
        "status": 200,
        "headers": {"content-type": "application/json"},
        "body": body,
        "truncated": False,
    }
    fields.update(over)
    return FetchedResponse(**fields)


def _connector(
    response: FetchedResponse | None = None, *, mailto: str | None = CONTACT
) -> tuple[OpenAlexConnector, _Transport]:
    transport = _Transport(response or _answer())
    return (
        OpenAlexConnector(
            transport=transport,
            resolver=RecordedResolver(hosts={"api.openalex.org": [PUBLIC]}),
            mailto=mailto,
            clock=lambda: NOW,
        ),
        transport,
    )


def _query(**over: Any) -> DatasetQuery:
    return DatasetQuery.model_validate(
        {"connector_id": OPENALEX_CONNECTOR_ID, "dataset_id": f"doi:{DOI}", **over}
    )


def _search(*words: str, year: str | None = None) -> DatasetQuery:
    filters: list[dict[str, Any]] = [{"dimension": "search", "values": list(words)}]
    if year is not None:
        filters.append({"dimension": "publication_year", "values": [year]})
    return _query(dataset_id="works", filters=filters)


def test_a_doi_is_one_singleton_get_asking_only_for_the_fields_it_reads() -> None:
    connector, transport = _connector()
    response = connector.query(_query())
    [(url, address)] = transport.calls
    parts = urlsplit(url)
    assert (parts.netloc, parts.path, address) == ("api.openalex.org", f"/works/doi:{DOI}", PUBLIC)
    assert parse_qsl(parts.query) == [
        (
            "select",
            "id,doi,title,publication_year,type,open_access,best_oa_location,locations,"
            "is_retracted",
        ),
        ("mailto", CONTACT),
    ]
    # No author, affiliation or abstract is asked for.
    assert "authorships" not in url and "abstract" not in url
    # The contact is sent, and kept out of what a snapshot stores.
    assert CONTACT not in response.result.source_url
    assert response.result.source_url == url.removesuffix(f"&mailto={CONTACT.replace('@', '%40')}")
    assert response.credits == 1
    assert response.result.licence == "CC0"


def test_without_a_configured_contact_nothing_is_guessed() -> None:
    connector, transport = _connector(mailto=None)
    connector.query(_query())
    assert "mailto" not in transport.calls[0][0]
    for bad in ("", "nobody", "a@b", "x@y.example&api_key=1", "x y@z.example"):
        with pytest.raises(ValueError):
            _connector(mailto=bad)


def test_the_work_becomes_one_row_per_location() -> None:
    result = _connector()[0].query(_query()).result
    assert result.title == "A fictional study of fictional household goods"
    assert [(r.key, r.label) for r in result.rows] == [
        ("loc1", "1. Journal of Fictional Studies"),
        ("loc2", "2. Fictional University Repository"),
        ("loc3", "3. Fictional Preprint Server"),
    ]
    assert result.rows[0].values == (
        "false",
        "publishedVersion",
        None,
        "https://doi.org/10.99999/fikce.2024.001",
        None,
        "Journal of Fictional Studies",
        "journal",
        "no",
    )
    assert result.rows[1].values[-1] == "yes" and result.rows[2].values[-1] == "no"
    assert "Open-access status (open_access.oa_status): green" in result.notes
    assert "Publication year: 2024" in result.notes


def test_the_ladder_reads_the_lawful_open_copies_best_first() -> None:
    result = _connector()[0].query(_query()).result
    assert open_access_copies(result) == (
        OpenAccessCopy(
            row_key="loc2",
            url="https://repozitar.example/fikce/2024-001.pdf",
            version="acceptedVersion",
            licence="cc-by",
            best=True,
        ),
        OpenAccessCopy(
            row_key="loc3",
            url="https://preprinty.example/abs/0000.00001",
            version="submittedVersion",
            licence=None,
            best=False,
        ),
    )  # the paywalled version of record (loc1) is never offered


def test_a_closed_work_has_no_open_copy() -> None:
    doc = json.loads(WORK)
    doc["best_oa_location"] = None
    for location in doc["locations"]:
        location["is_oa"] = False
    result = _connector(_answer(json.dumps(doc).encode()))[0].query(_query()).result
    assert open_access_copies(result) == ()


def test_a_locations_licence_grounds_to_its_cell() -> None:
    snapshot = dataset_snapshot(_connector()[0].query(_query()), retrieval_mode=RetrievalMode.LIVE)
    assert ground_cell(
        snapshot=snapshot,
        locator=f"doi:{DOI}!loc2/license",
        quote="2. Fictional University Repository | Licence at this location (license) = cc-by",
    ).grounded


def test_a_search_is_one_list_get_of_lower_case_words() -> None:
    connector, transport = _connector(_answer(SEARCH))
    response = connector.query(_search("Household", "GOODS", year="2024"))
    parts = urlsplit(transport.calls[0][0])
    assert parts.path == "/works"
    assert parse_qsl(parts.query) == [
        ("search", "household goods"),  # lower case: no word is a boolean operator
        ("filter", "publication_year:2024"),
        ("select", "id,doi,title,publication_year,open_access"),
        ("per-page", "25"),
        ("mailto", CONTACT),
    ]
    assert response.credits == 10
    result = response.result
    assert [r.label for r in result.rows] == [
        "1. https://openalex.org/W0000000001",
        "2. https://openalex.org/W0000000002",
    ]
    assert result.rows[1].values == (
        "https://openalex.org/W0000000002",
        None,
        "Fictional household goods, revisited",
        "2023",
        "false",
        "closed",
        None,
    )
    assert "Works matching (meta.count): 2" in result.notes
    # An AND written by an agent is a word, not an operator.
    _connector(_answer(SEARCH))[0].query(_search("goods", "AND", "prices"))


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        (_query(dataset_id="doi:11.1234/x"), "dataset_id_invalid"),
        (_query(dataset_id="doi:10.12/x"), "dataset_id_invalid"),
        (_query(dataset_id="doi:10.1234/a,b"), "dataset_id_invalid"),
        (_query(dataset_id="doi:10.1234/a&b"), "dataset_id_invalid"),
        (_query(dataset_id="authors"), "dataset_id_invalid"),
        (_query(period="2024"), "filters_unsupported"),
        (_query(filters=[{"dimension": "search", "values": ["x"]}]), "filters_unsupported"),
        (_query(dataset_id="works"), "filter_invalid"),
        (_search(*[f"w{i}" for i in range(11)]), "filter_invalid"),
        (_search("a.b"), "filter_invalid"),
        (_search("goods", year="24"), "filter_invalid"),
        (
            _query(
                dataset_id="works",
                filters=[
                    {"dimension": "search", "values": ["goods"]},
                    {"dimension": "authorships.author.id", "values": ["A1"]},
                ],
            ),
            "filters_unsupported",
        ),
        (_query(connector_id="eurostat-statistics-1"), "connector_mismatch"),
    ],
)
def test_a_query_this_connector_cannot_put_is_never_sent(query: DatasetQuery, reason: str) -> None:
    connector, transport = _connector()
    with pytest.raises(ToolCallFailed) as failed:
        connector.query(query)
    assert failed.value.reason == reason and failed.value.delivery is Delivery.NOT_SENT
    assert transport.calls == []


def _work(**change: Any) -> bytes:
    doc = json.loads(WORK)
    doc.update(change)
    return json.dumps(doc).encode()


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (_answer(_work(doi="https://doi.org/10.99999/another")), "response_contract"),
        (_answer(_work(doi=None)), "response_contract"),
        (_answer(_work(locations={"0": {}})), "response_contract"),
        (_answer(_work(title={"text": "x"})), "response_contract"),
        (_answer(_work(open_access=[True])), "response_contract"),
        (_answer(b"[]"), "response_contract"),
        (_answer(b"not json"), "response_contract"),
        (_answer(status=404), "http_404"),
        (_answer(status=429), "http_429"),
        # A merged work redirects; redirects are not followed.
        (_answer(status=301, headers={"location": "https://x.example/"}), "redirect_refused"),
        (_answer(headers={"content-type": "text/html"}), "content_type"),
    ],
)  # fmt: skip
def test_an_answer_outside_the_work_contract_is_refused(
    response: FetchedResponse, reason: str
) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(response)[0].query(_query())
    assert failed.value.reason == reason and failed.value.delivery is Delivery.RESPONDED


def test_a_list_answer_outside_its_contract_is_refused() -> None:
    doc = json.loads(SEARCH)
    doc["results"] = doc["results"] * 13  # 26 works for a page of 25
    for body in (json.dumps(doc).encode(), b'{"results": {}}'):
        with pytest.raises(ToolCallFailed) as failed:
            _connector(_answer(body))[0].query(_search("goods"))
        assert failed.value.reason == "response_contract"


def test_the_connector_requires_a_live_transport() -> None:
    with pytest.raises(ValueError):
        OpenAlexConnector(
            transport=RecordedFetchTransport(pages={}),
            resolver=RecordedResolver(hosts={}),
            mailto=None,
        )


@pytest.mark.parametrize(
    ("flag", "read"), [(True, True), (False, False), (None, None), ("yes", None)]
)
def test_a_doi_lookup_says_whether_openalex_holds_the_work_retracted(
    flag: Any, read: bool | None
) -> None:
    """Chunk 46: OpenAlex's is_retracted, read as stated; anything else is not stated."""
    doc = json.loads(WORK)
    if flag is None:
        doc.pop("is_retracted", None)
    else:
        doc["is_retracted"] = flag
    connector, _ = _connector(_answer(json.dumps(doc).encode()))
    assert openalex_retracted(connector.query(_query()).result) is read
