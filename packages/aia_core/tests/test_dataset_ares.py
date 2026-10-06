"""ARES: one legal entity's public facts as a table; nothing of a person is stored.

The fixtures are FICTIONAL (invented IČOs, names and addresses). The legal-entity
fields follow the ARES field names recorded, unverified, in ``docs/architecture/
deep-research-connectors.md``; the person fields are planted in invented shapes to
prove the allowlist. No network: the transport is a double.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aia_core.application.web_retrieval import DatasetAccess, RetrievalGate, WebRetrieval
from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.contracts import QueryDecision, RetrievalMode
from aia_core.domain.deep_research.datasets import DatasetQuery
from aia_core.domain.deep_research.grounding import ground_cell
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
)
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.dataset_ares import (
    ARES_CONNECTOR_ID,
    LEGAL_ENTITY_FORMS,
    AresConnector,
    valid_ico,
)
from aia_core.infrastructure.dataset_connectors import dataset_snapshot
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedResolver,
    SearchResponse,
    ToolCallFailed,
    WebFetcher,
)

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
PUBLIC = "93.184.215.14"
FIXTURES = Path(__file__).parent / "fixtures" / "dataset_connectors"
BODY = (FIXTURES / "ares_subject_fictional.json").read_bytes()
SOLE_TRADER = (FIXTURES / "ares_sole_trader_fictional.json").read_bytes()
ICO = "99999013"

#: Everything of a person the fictional answer carries. None of it may be stored.
PERSON_TEXT = (
    "Kvido",
    "Smyšlenka",
    "Radmila",
    "Vymyšlená",
    "Bohumil",
    "Fiktivního",
    "1971-05-02",
    "1969-11-20",
    "Snová 12",
    "Vymyšlená 7",
    "C 99999/FIKT",
)


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
        "provider_request_id": "ares-req-1",
    }
    fields.update(over)
    return FetchedResponse(**fields)


def _connector(response: FetchedResponse | None = None) -> tuple[AresConnector, _Transport]:
    transport = _Transport(response or _answer())
    return (
        AresConnector(
            transport=transport,
            resolver=RecordedResolver(hosts={"ares.gov.cz": [PUBLIC]}),
            clock=lambda: NOW,
        ),
        transport,
    )


def _query(**over: Any) -> DatasetQuery:
    return DatasetQuery.model_validate(
        {"connector_id": ARES_CONNECTOR_ID, "dataset_id": ICO, **over}
    )


def _body(**over: Any) -> bytes:
    doc = json.loads(BODY)
    doc.update(over)
    return json.dumps(doc).encode()


# ------------------------------------------------------------------- the request


def test_one_get_by_ico_to_the_registers_one_host() -> None:
    connector, transport = _connector()
    connector.query(_query())
    assert transport.calls == [
        ("https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/99999013", PUBLIC)
    ]


def test_an_ico_is_eight_digits_with_its_check_digit() -> None:
    assert valid_ico("99999013") and valid_ico("27345670")
    assert not valid_ico("99999014")  # wrong check digit
    assert not valid_ico("9999901") and not valid_ico("9999901x")


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"dataset_id": "99999014"}, "dataset_id_invalid"),
        ({"dataset_id": "Fiktivni-Mlekarna"}, "dataset_id_invalid"),
        ({"dataset_id": "../../admin"}, "dataset_id_invalid"),
        ({"filters": [{"dimension": "x", "values": ["y"]}]}, "filters_unsupported"),
        ({"period": "2024"}, "filters_unsupported"),
        ({"connector_id": "nkod-sparql-1"}, "connector_mismatch"),
    ],
)
def test_a_query_this_connector_cannot_put_is_never_sent(over: dict[str, Any], reason: str) -> None:
    connector, transport = _connector()
    with pytest.raises(ToolCallFailed) as failed:
        connector.query(_query(**over))
    assert failed.value.reason == reason and failed.value.delivery is Delivery.NOT_SENT
    assert transport.calls == []


# ------------------------------------------------------------------- the table


def test_a_legal_entity_becomes_one_row_of_its_allowlisted_fields() -> None:
    result = _connector()[0].query(_query()).result
    assert result.licence is None  # the register's terms are not stamped
    assert result.title == "Ekonomický subjekt Fiktivní Mlékárna Alfa s.r.o."
    [row] = result.rows
    assert (row.key, row.label) == ("subjekt", "IČO 99999013")
    assert dict(zip((c.key for c in result.columns), row.values, strict=True)) == {
        "ico": "99999013",
        "obchodni_jmeno": "Fiktivní Mlékárna Alfa s.r.o.",
        "pravni_forma": "112",
        "datum_vzniku": "2011-03-14",
        "datum_zaniku": None,
        "datum_aktualizace": "2026-09-30",
        "dic": "CZ99999013",
        "cz_nace": "10510, 46330",
        "sidlo_adresa": "Smyšlená 101, 999 01 Fiktivov",
        "sidlo_obec": "Fiktivov",
        "sidlo_psc": "99901",
        "sidlo_kraj": "Fiktivní kraj",
        "sidlo_stat": "CZ",
        "stav_vr": "AKTIVNI",
        "stav_res": "AKTIVNI",
        "stav_dph": "AKTIVNI",
    }
    assert result.notes == ("Právní forma 112: Společnost s ručením omezeným (právnická osoba).",)


def test_a_recorded_response_full_of_person_fields_stores_no_personal_name() -> None:
    response = _connector()[0].query(_query())
    snapshot = dataset_snapshot(response, retrieval_mode=RetrievalMode.LIVE)
    stored = snapshot.model_dump_json()
    # The fixture does carry them: the test would be empty otherwise.
    assert all(text in BODY.decode() for text in PERSON_TEXT)
    for text in PERSON_TEXT:
        assert text not in stored, text
        assert text not in snapshot.text, text
    # The raw answer is recorded by its hash and length, and its body is not stored.
    assert snapshot.raw_sha256 == hashlib.sha256(BODY).hexdigest()
    assert snapshot.raw_bytes == len(BODY)
    assert "statutarniOrgany" not in stored and "adresaDorucovaci" not in stored
    assert BODY.decode() not in stored


def test_a_fact_grounds_to_its_cell_with_the_ico_in_its_quote() -> None:
    snapshot = dataset_snapshot(_connector()[0].query(_query()), retrieval_mode=RetrievalMode.LIVE)
    verdict = ground_cell(
        snapshot=snapshot,
        locator=f"{ICO}!subjekt/datum_vzniku",
        quote="IČO 99999013 | Datum vzniku = 2011-03-14",
    )
    assert verdict.grounded
    assert not ground_cell(
        snapshot=snapshot,
        locator=f"{ICO}!subjekt/datum_aktualizace",
        quote="IČO 99999013 | Datum vzniku = 2011-03-14",
    ).grounded


# ------------------------------------------------------------------- a person


def test_a_sole_trader_is_refused_whole_and_its_name_goes_nowhere() -> None:
    connector, _ = _connector(_answer(SOLE_TRADER))
    with pytest.raises(ToolCallFailed) as failed:
        connector.query(_query(dataset_id="99999021"))
    assert failed.value.reason == "not_a_legal_entity"
    assert failed.value.delivery is Delivery.RESPONDED  # it was asked: journaled as answered
    assert "Vendelín" not in str(failed.value) and "Smyšlený" not in str(failed.value)


@pytest.mark.parametrize("form", ["100", "101", "105", "107", "424", "999", "", None])
def test_any_form_not_recorded_as_a_legal_person_is_refused(form: str | None) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(_answer(_body(pravniForma=form)))[0].query(_query())
    reason = "response_contract" if form == "" else "not_a_legal_entity"
    assert failed.value.reason == reason


def test_the_legal_form_allowlist_holds_legal_persons_only() -> None:
    # No natural person's form (the 1xx codes below 111, the foreign-person 4xx codes).
    assert not any(code < "111" or code.startswith("4") for code in LEGAL_ENTITY_FORMS)


# ------------------------------------------------------------------- fail closed


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b"not json", "response_contract"),
        (b"[]", "response_contract"),
        (_body(ico="27345670"), "response_contract"),  # another subject
        (_body(ico=None), "response_contract"),
        (_body(obchodniJmeno=None), "response_contract"),
        (_body(obchodniJmeno={"jmeno": "x"}), "response_contract"),
        (_body(datumVzniku="14. 3. 2011"), "response_contract"),
        (_body(czNace="10510"), "response_contract"),
        (_body(czNace=["10510", {"kod": 1}]), "response_contract"),
        (_body(sidlo="Smyšlená 101"), "response_contract"),
        (_body(sidlo={"psc": "99901"}), "response_contract"),
        (_body(seznamRegistraci=["AKTIVNI"]), "response_contract"),
    ],
)
def test_an_answer_in_another_shape_is_refused(body: bytes, reason: str) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(_answer(body))[0].query(_query())
    assert failed.value.reason == reason and failed.value.delivery is Delivery.RESPONDED


def test_an_unknown_subject_is_the_registers_404() -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(_answer(b'{"kod": "NENALEZENO"}', status=404))[0].query(_query())
    assert failed.value.reason == "http_404"


def test_an_answer_of_another_type_is_refused() -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(_answer(headers={"content-type": "text/html"}))[0].query(_query())
    assert failed.value.reason == "content_type"


# ------------------------------------------------------------------- the gate


class _LiveSearch:
    adapter_id = "live-search-test"

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def search(self, query: str, *, max_results: int) -> SearchResponse:
        raise AssertionError("not searched here")


def _route(tool: ToolKind, adapter_id: str) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"{tool.value}-test",
            provider="test",
            zone=ResidencyZone.EU,
            eu_processing_approved=True,
            excluded_from_training=True,
            retention_days=0,
            approved_for=frozenset(DataClass),
        ),
        tool=tool,
        adapter_id=adapter_id,
        retrieval_mode=RetrievalMode.LIVE,
        price_usd_per_call=0.0,
    )


def _gate(scope: Any, connector: AresConnector) -> tuple[RetrievalGate, InMemoryToolLedger]:
    ledger = InMemoryToolLedger(budget_usd=1.0)
    page = _Transport(_answer())
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH, _LiveSearch.adapter_id),
            fetch_route=_route(ToolKind.WEB_FETCH, "live-fetch-test"),
            search=_LiveSearch(),
            fetcher=WebFetcher(
                transport=page, resolver=RecordedResolver(hosts={}), adapter_id="live-fetch-test"
            ),
        ),
        scope=scope,
        meter=ledger,
        client_terms=(),
        class_a_texts=(),
        clock=lambda: NOW,
        datasets=(
            DatasetAccess(
                route=_route(ToolKind.DATASET_QUERY, ARES_CONNECTOR_ID), connector=connector
            ),
        ),
    )
    return gate, ledger


def test_through_the_gate_a_subject_is_journaled_and_a_sole_trader_is_a_known_failure(
    scoped: Any,
) -> None:
    connector, _ = _connector()
    gate, ledger = _gate(scoped.scope(), connector)
    outcome = gate.dataset(_query(), context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.record.decision is QueryDecision.SENT and outcome.snapshot is not None
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.DISPATCHED, ToolOutcome.SUCCEEDED]
    assert "Smyšlenka" not in outcome.snapshot.model_dump_json()

    person, _ = _connector(_answer(SOLE_TRADER))
    gate, ledger = _gate(scoped.scope(), person)
    refused = gate.dataset(
        _query(dataset_id="99999021"), context_class=DataClass.CLASS_C_INTERNAL, track_id="T"
    )
    assert refused.snapshot is None and refused.record.failure == "not_a_legal_entity"
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.DISPATCHED, ToolOutcome.FAILED]
    assert "Vendelín" not in repr(ledger.events()) and "Vendelín" not in repr(refused)


def test_a_client_derived_query_never_reaches_the_register(scoped: Any) -> None:
    connector, transport = _connector()
    gate, _ = _gate(scoped.scope(), connector)
    outcome = gate.dataset(_query(), context_class=DataClass.CLASS_B_DERIVED_CLIENT, track_id="T")
    assert outcome.record.refusal == "dataset_class_c_only" and transport.calls == []
