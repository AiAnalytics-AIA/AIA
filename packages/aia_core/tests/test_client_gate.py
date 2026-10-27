"""The client deliverable's gate (report-delivery RD0, MVPQ-09), over the stored document model:
drill-down content or an unadmitted number is each a warning naming its block (warnings since
2026-10-22, never a refusal)."""

from __future__ import annotations

import copy
import io
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import Any

from lxml import etree
from report_samples import build

from aia_core.domain.evidence.claims import ClaimLevel, ClaimSurface
from aia_core.domain.report.client_gate import GateCode, client_gate, edited_client_gate
from aia_core.domain.report.document_model import document_payload
from aia_core.domain.report.model import Paragraph, Quote, ReportDocument, Section, Text, Value
from aia_core.domain.report.saved_changes import (
    ChangeKind,
    SavedChange,
    SavedChanges,
    Uncomparable,
    compare,
    written_texts,
)
from aia_core.infrastructure.report_docx.census import census
from aia_core.infrastructure.report_docx.renderer import DocxRenderer


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


# -- a saved editor version of a client report (artifact-report RPT13) ------------------------


#: What code wrote under each tag in the line's composed draft, for the hand-built cases.
_WRITTEN: Mapping[str, frozenset[str]] = {"trust_total": frozenset({"42,5 %"})}


def _edited(
    *changes: SavedChange,
    uncomparable: Uncomparable | None = None,
    written: Mapping[str, frozenset[str]] | None = _WRITTEN,
) -> list[Any]:
    return [f.to_json() for f in edited_client_gate(SavedChanges(changes, uncomparable), written)]


_TEXT = {
    "code": "gate_unrecorded",
    "where": "text",
    "message": "text upravený v editoru AIA neověří; zkontrolujte, že necituje jednoho respondenta",
}


def test_a_retyped_or_typed_number_is_unadmitted_and_the_text_is_never_passed() -> None:
    assert _edited(
        SavedChange(ChangeKind.CHANGED, "trust_total", "42,5 %", "50 %"),
        SavedChange(ChangeKind.TYPED, now="73 %", paragraph="Téměř tři čtvrtiny, 73 %, souhlasí."),
    ) == [
        {
            "code": "unadmitted_number",
            "where": "trust_total",
            "message": "číslo přepsané ručně: 42,5 % → 50 %",
        },
        {
            "code": "unadmitted_number",
            "where": "text",
            "message": "číslo 73 % napsané ručně mimo připuštěná čísla"
            " („Téměř tři čtvrtiny, 73 %, souhlasí.“)",
        },
        _TEXT,
    ]


def test_a_typed_numbers_paragraph_is_marked_cut_only_where_it_was() -> None:
    long = "Téměř tři čtvrtiny lidí, celkem 73 %, souhlasí s tím, že banka jedná férově a otevřeně."
    (typed, _text) = _edited(SavedChange(ChangeKind.TYPED, now="73 %", paragraph=long))
    assert typed["message"].endswith(f"(„{long[:60]}…“)")


def test_a_removed_number_or_a_copy_of_what_code_wrote_under_its_tag_prints_nothing_new() -> None:
    assert _edited(SavedChange(ChangeKind.REMOVED, "trust_total", was="42,5 %")) == [_TEXT]
    assert _edited(SavedChange(ChangeKind.ADDED, "trust_total", now="42,5 %")) == [_TEXT]


def test_a_control_copied_and_retyped_is_unadmitted() -> None:
    """Review of #1017 (P1): ``added`` is any surplus text under a tag, not only a copy."""
    retyped = {
        "code": "unadmitted_number",
        "where": "trust_total",
        "message": "číslo přidané ručně: 99 %",
    }
    assert _edited(SavedChange(ChangeKind.ADDED, "trust_total", now="99 %")) == [retyped, _TEXT]
    # A tag code never wrote holds nothing admitted to copy.
    assert _edited(SavedChange(ChangeKind.ADDED, "trust_praha", now="42,5 %"))[0] == {
        "code": "unadmitted_number",
        "where": "trust_praha",
        "message": "číslo přidané ručně: 42,5 %",
    }
    # What code wrote unknown, no added text is a copy: unknown is never passed.
    assert _edited(SavedChange(ChangeKind.ADDED, "trust_total", now="42,5 %"), written=None) == [
        {**retyped, "message": "číslo přidané ručně: 42,5 %"},
        _TEXT,
    ]


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _saved(docx: bytes, edit: Callable[[etree._Element], None]) -> bytes:
    """``docx`` as an editor would save it after ``edit`` to its body."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(docx)) as source, zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "word/document.xml":
                root = etree.fromstring(data)
                edit(root)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            target.writestr(info, data)
    return out.getvalue()


def _copy_control(tag: str, text: str | None) -> Callable[[etree._Element], None]:
    """The control ``tag`` copied beside itself, its copy retyped to ``text`` (``None``: kept)."""

    def edit(root: etree._Element) -> None:
        (sdt,) = (
            s
            for s in root.iter(f"{_W}sdt")
            if any(t.get(f"{_W}val") == tag for t in s.iter(f"{_W}tag"))
        )
        twin = copy.deepcopy(sdt)
        if text is not None:
            first, *rest = twin.iter(f"{_W}t")
            first.text = text
            for t in rest:
                t.text = ""
        sdt.addnext(twin)

    return edit


def test_a_copied_control_retyped_is_unadmitted_through_the_census(report_doc: Any) -> None:
    """The real path a save takes (``census``, ``compare``) and the baseline the approval reads:
    a locked number copied and then retyped prints a number no admitted claim holds, while a
    plain copy prints the admitted one again."""
    draft = DocxRenderer().render(
        report_doc(Paragraph((Text("Bance důvěřuje "), Value("trust_total"), Text(" lidí."))))
    )
    baseline = census(draft)
    written = written_texts(baseline)

    def numbers(edit: Callable[[etree._Element], None]) -> list[tuple[str, str]]:
        changes = compare(baseline, census(_saved(draft, edit)))
        return [
            (f.code.value, f.where)
            for f in edited_client_gate(changes, written)
            if f.code is GateCode.UNADMITTED_NUMBER
        ]

    assert numbers(_copy_control("trust_total", "99 %")) == [("unadmitted_number", "trust_total")]
    assert numbers(_copy_control("trust_total", None)) == []


def test_a_save_with_nothing_to_compare_is_unknown_never_passed() -> None:
    # A clean save is still not a passed one: the text a person wrote is never judged.
    assert _edited() == [_TEXT]
    assert _edited(uncomparable=Uncomparable.NO_CONTROLS) == [
        {
            "code": "gate_unrecorded",
            "where": "numbers",
            "message": "čísla verze nelze porovnat s tím, co napsal kód; nelze je ověřit",
        },
        _TEXT,
    ]
