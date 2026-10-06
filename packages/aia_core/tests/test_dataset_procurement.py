"""Public procurement: a notice's forms as a table, grounded by its evidence number.

The fixture is FICTIONAL (invented numbers, authorities, persons and contacts), in the
record shape recorded, unverified, in ``docs/architecture/deep-research-connectors.md``.
Contact and supplier fields are planted to prove the allowlist. No network.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aia_core.application.web_retrieval import DatasetAccess, RetrievalGate, WebRetrieval
from aia_core.domain.ai_contracts import Delivery, canonical_json
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
from aia_core.infrastructure.dataset_connectors import dataset_snapshot
from aia_core.infrastructure.dataset_procurement import (
    NOTICE_FIELDS,
    PROCUREMENT_CONNECTOR_ID,
    REDACTED,
    ProcurementNoticeConnector,
    RecordedNoticeSource,
    valid_notice_id,
)
from aia_core.infrastructure.web_retrieval import (
    RecordedFetchTransport,
    RecordedResolver,
    RecordedSearch,
    ToolCallFailed,
    WebFetcher,
)

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
NOTICE = "Z2025-999001"
FIXTURE = json.loads(
    (
        Path(__file__).parent
        / "fixtures"
        / "dataset_connectors"
        / "procurement_notice_fictional.json"
    ).read_text(encoding="utf-8")
)
NOTICES: dict[str, Any] = {k: v for k, v in FIXTURE.items() if not k.startswith("_")}

#: Every person, contact or supplier detail the fictional records carry.
PERSONAL = (
    "Ludmila",
    "Smyšlená",
    "Smyšlené",
    "ludmila.smyslena@alfa.example",
    "podatelna@alfa.example",
    "999 123 456",
    "999 765 432",
    "Bořivoj",
    "Vendelín",
    "Domácí 3",
    "99999021",
)


def _connector(notices: dict[str, Any] | None = None) -> ProcurementNoticeConnector:
    return ProcurementNoticeConnector(
        source=RecordedNoticeSource(notices=NOTICES if notices is None else notices),
        clock=lambda: NOW,
    )


def _query(**over: Any) -> DatasetQuery:
    return DatasetQuery.model_validate(
        {"connector_id": PROCUREMENT_CONNECTOR_ID, "dataset_id": NOTICE, **over}
    )


def _with(**over: Any) -> dict[str, Any]:
    """The fixture's notice with its first record changed."""
    notice = json.loads(json.dumps(NOTICES[NOTICE]))
    notice["records"][0].update(over)
    return {NOTICE: notice}


def _cells() -> dict[str, dict[str, str | None]]:
    result = _connector().query(_query()).result
    keys = [c.key for c in result.columns]
    return {r.key: dict(zip(keys, r.values, strict=True)) for r in result.rows}


# ------------------------------------------------------------------- the table


def test_a_notice_becomes_one_row_per_form_keyed_by_its_number() -> None:
    result = _connector().query(_query()).result
    assert result.title == f"Veřejná zakázka {NOTICE}" and result.licence is None
    assert [(r.key, r.label) for r in result.rows] == [
        ("F2025-999101", f"{NOTICE} formulář F2025-999101"),
        ("F2025-999202", f"{NOTICE} formulář F2025-999202"),
    ]
    cells = _cells()
    assert cells["F2025-999101"] == {
        "notice_id": NOTICE,
        "form_type": "F02",
        "valid_form": "1",
        "published": "2025-03-04",
        "authority": "Fiktivní město Alfa",
        "authority_ico": "99999030",
        "subject": "Dodávka mléčných výrobků pro fiktivní školní jídelny",
        "contract_type": "Dodávky",
        "procedure": "Otevřené řízení",
        "cpv_main": "15500000-3",
        "estimated_value": "4 500 000,00",
        "estimated_currency": "CZK",
        "final_value": None,
        "final_currency": None,
        "tender_deadline": "2025-04-15T10:00:00",
    }
    assert cells["F2025-999202"]["final_value"] == "4 120 500,00"


def test_a_notices_facts_ground_to_its_cells_and_every_quote_names_the_notice() -> None:
    snapshot = dataset_snapshot(_connector().query(_query()), retrieval_mode=RetrievalMode.RECORDED)
    the_id = ground_cell(
        snapshot=snapshot,
        locator=f"{NOTICE}!F2025-999101/notice_id",
        quote=f"{NOTICE} formulář F2025-999101 | Evidenční číslo zakázky ve VVZ = {NOTICE}",
    )
    assert the_id.grounded
    value = ground_cell(
        snapshot=snapshot,
        locator=f"{NOTICE}!F2025-999202/final_value",
        quote=f"{NOTICE} formulář F2025-999202 | Celková konečná hodnota = 4 120 500,00",
    )
    assert value.grounded and value.cell is not None and NOTICE in value.cell.text()
    # The award's value is not the notice's estimate: another cell does not ground.
    assert not ground_cell(
        snapshot=snapshot,
        locator=f"{NOTICE}!F2025-999101/estimated_value",
        quote=f"{NOTICE} formulář F2025-999202 | Celková konečná hodnota = 4 120 500,00",
    ).grounded


def test_no_contact_person_email_phone_or_supplier_is_stored() -> None:
    response = _connector().query(_query())
    snapshot = dataset_snapshot(response, retrieval_mode=RetrievalMode.RECORDED)
    stored = snapshot.model_dump_json()
    planted = json.dumps(NOTICES, ensure_ascii=False)
    assert all(text in planted for text in PERSONAL)  # the test is not empty
    for text in PERSONAL:
        assert text not in stored, text
    # The contact details inside the title are replaced, and the note says so.
    assert _cells()["F2025-999202"]["subject"] == (
        f"Dodávka mléčných výrobků pro fiktivní školní jídelny (info: {REDACTED}, {REDACTED})"
    )
    assert any(REDACTED in note for note in response.result.notes)
    # The records are kept by their hash and length only.
    raw = canonical_json(NOTICES[NOTICE]["records"]).encode("utf-8")
    assert (snapshot.raw_sha256, snapshot.raw_bytes) == (hashlib.sha256(raw).hexdigest(), len(raw))


def test_no_read_field_is_a_contact_or_supplier_field() -> None:
    read = {name for _, _, name, _ in NOTICE_FIELDS}
    assert not any(
        word in name for name in read for word in ("Kontakt", "Email", "Telefon", "Dodavatel")
    )
    assert "StrucnyPopisVZ" not in read and "OteviraniNabidekOpravneneOsobyDalsiInfo" not in read


# ------------------------------------------------------------------- the query


def test_a_notice_is_asked_for_by_its_evidence_number() -> None:
    assert valid_notice_id("Z2025-999001")
    for bad in ("Z25-999001", "Z2025-99901", "N006/24/V00012345", "z2025-999001", "Z2025-999001 "):
        assert not valid_notice_id(bad)


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"dataset_id": "N006/24/V00012345"}, "dataset_id_invalid"),
        ({"dataset_id": "Fiktivni-mesto"}, "dataset_id_invalid"),
        ({"filters": [{"dimension": "x", "values": ["y"]}]}, "filters_unsupported"),
        ({"period": "2025"}, "filters_unsupported"),
        ({"connector_id": "ares-subject-1"}, "connector_mismatch"),
    ],
)
def test_a_query_this_connector_cannot_put_is_never_sent(over: dict[str, Any], reason: str) -> None:
    source = RecordedNoticeSource(notices=NOTICES)
    connector = ProcurementNoticeConnector(source=source, clock=lambda: NOW)
    with pytest.raises(ToolCallFailed) as failed:
        connector.query(_query(**over))
    assert failed.value.reason == reason and failed.value.delivery is Delivery.NOT_SENT
    assert source.calls == []


# ------------------------------------------------------------------- fail closed


@pytest.mark.parametrize(
    ("notices", "reason"),
    [
        ({}, "notice_not_found"),
        (_with(EvidencniCisloVZnaVVZ="Z2025-999002"), "response_contract"),
        (_with(EvidencniCisloVZnaVVZ=None), "response_contract"),
        (_with(CisloFormulareNaVVZ="F 1/2"), "response_contract"),
        (_with(CisloFormulareNaVVZ=None), "response_contract"),
        (_with(OdhadovanaHodnotaVZbezDPH=4500000.5), "response_contract"),
        (_with(OdhadovanaHodnotaVZbezDPH="cca 4,5 mil."), "response_contract"),
        (_with(DatumUverejneni="březen 2025"), "response_contract"),
        (_with(ZadavatelICO="CZ99999030"), "response_contract"),
        (_with(NazevVZ={"cs": "x"}), "response_contract"),
        (_with(PlatnyFormular=True), "response_contract"),
        (
            {NOTICE: {**NOTICES[NOTICE], "records": [NOTICES[NOTICE]["records"][0]] * 2}},
            "response_contract",  # one form twice
        ),
        (
            {NOTICE: {**NOTICES[NOTICE], "records": [NOTICES[NOTICE]["records"][0]] * 51}},
            "notice_too_large",
        ),
        ({NOTICE: {**NOTICES[NOTICE], "source_url": "http://isvz.example/"}}, "response_contract"),
    ],
)
def test_an_answer_in_another_shape_is_refused(notices: dict[str, Any], reason: str) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(notices).query(_query())
    assert failed.value.reason == reason and failed.value.delivery is Delivery.RESPONDED


# ------------------------------------------------------------------- the gate


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


def _gate(scope: Any, notices: dict[str, Any]) -> tuple[RetrievalGate, InMemoryToolLedger]:
    ledger = InMemoryToolLedger(budget_usd=1.0)
    connector = ProcurementNoticeConnector(
        source=RecordedNoticeSource(notices=notices), clock=lambda: NOW
    )
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
        client_terms=(),
        class_a_texts=(),
        clock=lambda: NOW,
        datasets=(
            DatasetAccess(
                route=_route(ToolKind.DATASET_QUERY, PROCUREMENT_CONNECTOR_ID),
                connector=connector,
            ),
        ),
    )
    return gate, ledger


def test_through_the_gate_a_notice_is_journaled_and_returned_as_a_table(scoped: Any) -> None:
    gate, ledger = _gate(scoped.scope(), NOTICES)
    outcome = gate.dataset(_query(), context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.record.decision is QueryDecision.SENT and outcome.record.hits == 2
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.DISPATCHED, ToolOutcome.SUCCEEDED]
    assert ledger.events()[1].provider_request_id == "isvz-fikt-1"
    assert outcome.snapshot is not None and outcome.snapshot.dataset is not None
    assert outcome.snapshot.dataset.dataset_id == NOTICE


@pytest.mark.parametrize(
    ("fail", "outcome_kind", "uncertain"),
    [("uncertain", ToolOutcome.UNCERTAIN, True), ("known", ToolOutcome.FAILED, False)],
)
def test_a_failed_notice_is_journaled_with_its_delivery(
    scoped: Any, fail: str, outcome_kind: ToolOutcome, uncertain: bool
) -> None:
    gate, ledger = _gate(scoped.scope(), {NOTICE: {"fail": fail}})
    outcome = gate.dataset(_query(), context_class=DataClass.CLASS_C_INTERNAL, track_id="T")
    assert outcome.snapshot is None and outcome.uncertain is uncertain
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.DISPATCHED, outcome_kind]


def test_a_client_derived_notice_query_is_refused_before_the_source(scoped: Any) -> None:
    gate, ledger = _gate(scoped.scope(), NOTICES)
    outcome = gate.dataset(_query(), context_class=DataClass.CLASS_B_DERIVED_CLIENT, track_id="T")
    assert outcome.record.refusal == "dataset_class_c_only"
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.REFUSED]
