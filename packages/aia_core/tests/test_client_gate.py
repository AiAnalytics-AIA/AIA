"""The client deliverable's gate (report-delivery RD0, MVPQ-09), over the stored document model:
drill-down content or an unadmitted number is each a warning naming its block (warnings since
2026-10-22, never a refusal)."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Any

from report_samples import build

from aia_core.domain.evidence.claims import ClaimLevel, ClaimSurface
from aia_core.domain.report.client_gate import GateCode, client_gate
from aia_core.domain.report.document_model import document_payload
from aia_core.domain.report.model import Paragraph, Quote, ReportDocument, Section, Value


def _without_quotes(document: ReportDocument) -> ReportDocument:
    sections = tuple(
        replace(s, blocks=tuple(b for b in s.blocks if not isinstance(b, Quote)))
        for s in document.sections
    )
    return replace(document, sections=sections)


def test_a_client_report_of_admitted_aggregate_numbers_passes(report_ledger: Any) -> None:
    assert client_gate(document_payload(_without_quotes(build("client", report_ledger)))) == ()


def test_a_respondents_own_words_are_drill_down_named_by_their_block(report_ledger: Any) -> None:
    document = build("client", report_ledger)
    payload = document_payload(document)
    quote = next(b["id"] for s in payload["sections"] for b in s["blocks"] if b["type"] == "quote")
    assert [r.to_json() for r in client_gate(payload)] == [
        {
            "code": "drill_down_content",
            "where": quote,
            "message": "doslovná odpověď jednoho respondenta",
        }
    ]


def test_a_number_read_from_one_respondent_is_drill_down(report_ledger: Any) -> None:
    document = _without_quotes(build("client", report_ledger))
    ref = next(iter(document.ledger.rows))
    rows = dict(document.ledger.rows)
    rows[ref] = replace(rows[ref], level=ClaimLevel.INDIVIDUAL)
    ledger = replace(document.ledger, rows=MappingProxyType(rows))
    refusals = client_gate(document_payload(replace(document, ledger=ledger)))
    assert refusals and {r.code for r in refusals} == {GateCode.DRILL_DOWN}
    assert all(ref in r.message for r in refusals)


def test_a_ref_the_stored_ledger_does_not_hold_is_unadmitted(report_ledger: Any) -> None:
    payload = document_payload(_without_quotes(build("client", report_ledger)))
    payload["sections"][0]["blocks"][0]["refs"].append("no-such-ref")
    refusals = client_gate(payload)
    assert [(r.code, r.where) for r in refusals] == [
        (GateCode.UNADMITTED_NUMBER, payload["sections"][0]["blocks"][0]["id"])
    ]


def test_a_document_on_another_surface_is_said_and_its_blocks_still_checked(
    report_ledger: Any,
) -> None:
    document = build("client", report_ledger)
    internal = replace(document.ledger, surface=ClaimSurface.INTERNAL)
    payload = document_payload(replace(document, ledger=internal))
    quote = next(b["id"] for s in payload["sections"] for b in s["blocks"] if b["type"] == "quote")
    findings = client_gate(payload)
    # The whole-document warning first, and the block's own after it, never instead of it.
    assert [(f.code, f.where) for f in findings] == [
        (GateCode.LEDGER_NOT_CLIENT_FACING, "evidence"),
        (GateCode.DRILL_DOWN, quote),
    ]


def test_every_refusal_is_reported_not_only_the_first(report_ledger: Any) -> None:
    document = build("client", report_ledger)
    ref = next(iter(document.ledger.rows))
    rows = dict(document.ledger.rows)
    rows[ref] = replace(rows[ref], level=ClaimLevel.INDIVIDUAL)
    extra = Section("X", (Paragraph((Value(ref),)),), id="x")
    ledger = replace(document.ledger, rows=MappingProxyType(rows))
    payload = document_payload(
        replace(document, ledger=ledger, sections=(*document.sections, extra))
    )
    payload["sections"][-1]["blocks"][0]["refs"].append("no-such-ref")
    assert {r.code for r in client_gate(payload)} == {
        GateCode.DRILL_DOWN,
        GateCode.UNADMITTED_NUMBER,
    }


def test_a_document_of_an_older_contract_is_not_judged_so_not_passed(report_ledger: Any) -> None:
    payload = document_payload(_without_quotes(build("client", report_ledger)))
    payload["contract"] = "aia-report-document-2"
    assert [(r.code, r.where) for r in client_gate(payload)] == [(GateCode.UNRECORDED, "report")]
