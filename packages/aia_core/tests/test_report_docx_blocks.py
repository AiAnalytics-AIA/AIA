"""The report components in DOCX: values, marks, lists, findings, KPIs, evidence.

Every value is printed exactly as the evidence rounded it, with its grade mark;
the unknown grade prints ``?``; a client estimate always shows its interval; and
nothing is formatted outside a named style.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import replace
from typing import Any

from lxml import etree
from test_report_docx_render import _meta

from aia_core.domain.evidence.claims import ClaimSurface
from aia_core.domain.report.model import (
    AuditBlock,
    BulletList,
    Callout,
    CalloutKind,
    Classification,
    EvidenceAppendix,
    EvidenceKey,
    KeyFinding,
    Kpi,
    KpiRow,
    ListItem,
    Paragraph,
    Quote,
    Recommendation,
    ReportDocument,
    ReportKind,
    Section,
    Text,
    Value,
    text,
)
from aia_core.infrastructure.report_docx.lint import lint_docx
from aia_core.infrastructure.report_docx.renderer import DocxRenderer

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
NB = "\u00a0"


def components(ledger: Any, **meta: Any) -> ReportDocument:
    blocks = (
        Callout(CalloutKind.METHOD, ()),
        Paragraph(
            (
                Text("Bankám důvěřuje "),
                Value("trust_total"),
                Text(", v Ostravě "),
                Value("trust_ostrava"),
                Text("; modelovaně přejde "),
                Value("switch_modelled"),
                Text("."),
            )
        ),
        Callout(CalloutKind.DECISION, text("Soustřeďte se na Prahu."), refs=("trust_praha",)),
        BulletList(
            (
                ListItem(text("první"), (ListItem(text("vnořená")),)),
                ListItem(text("druhá")),
            )
        ),
        BulletList((ListItem(text("jedna")), ListItem(text("dvě"))), ordered=True),
        BulletList((ListItem(text("znovu jedna")),), ordered=True),
        Quote("Banku měním, když mě naštve.", "žena, 34 let, Brno", synthetic=True),
        KeyFinding(
            "Praha důvěřuje víc",
            "Důvěra je v Praze nejvyšší.",
            "Srovnání regionů.",
            "Kampaň začněte v Praze.",
            "střední",
            refs=("trust_praha",),
        ),
        Recommendation("Začněte v Praze", "Nejvyšší důvěra.", "vysoká", refs=("trust_praha",)),
        KpiRow((Kpi("Důvěra celkem", "trust_total"), Kpi("Respondenti", "n_total"))),
        EvidenceKey(),
    )
    return ReportDocument(
        _meta(**meta),
        (
            Section("Shrnutí", blocks),
            Section("Evidence", (EvidenceAppendix(),), appendix=True),
        ),
        ledger,
    )


def _render(doc: ReportDocument) -> dict[str, bytes]:
    data = DocxRenderer().render(doc)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def _body(parts: dict[str, bytes]) -> etree._Element:
    return etree.fromstring(parts["word/document.xml"])


def _paragraphs(root: etree._Element) -> list[str]:
    return ["".join(t.text or "" for t in p.iter(f"{W}t")) for p in root.iter(f"{W}p")]


def test_values_print_as_the_evidence_rounded_them_with_intervals(report_ledger: Any) -> None:
    lines = _paragraphs(_body(_render(components(report_ledger()))))
    prose = next(p for p in lines if p.startswith("Bankám"))
    # a client estimate carries its interval although the block did not ask for it
    assert f"42,5{NB}%{NB}(38,1\u201346,9{NB}%)" in prose
    assert f"36,1{NB}%{NB}(27,9\u201344,3{NB}%){NB} (orientační)" in prose
    assert f"18,4{NB}%{NB}(14,9\u201321,9{NB}%)" in prose


def test_every_value_carries_its_grade_mark_with_alt_text(report_ledger: Any) -> None:
    parts = _render(components(report_ledger()))
    descr = [d.get("descr") for d in _body(parts).iter(f"{WP}docPr")]
    assert "Měřeno" in descr and "Modelováno" in descr
    # one SVG per distinct grade, shared by every occurrence
    grades: dict[str, set[str]] = {}
    svg_ns = "{http://schemas.microsoft.com/office/drawing/2016/SVG/main}"
    r_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    for inline in _body(parts).iter(f"{WP}inline"):
        label = inline.find(f"{WP}docPr").get("descr")
        if not label:
            continue  # the cover accent has no scientific grade
        vector = next(inline.iter(svg_ns + "svgBlip"))
        grades.setdefault(label, set()).add(vector.get(r_ns + "embed"))
    assert set(grades) == {d for d in descr if d}
    assert all(len(rids) == 1 for rids in grades.values())
    assert len(set().union(*grades.values())) == len(grades)
    blips = parts["word/document.xml"].decode()
    assert "svgBlip" in blips and "{96DAC541-7B7A-43D3-8B79-37D633B846F1}" in blips


def test_an_ungraded_field_prints_a_question_mark_not_a_mark(report_ledger: Any) -> None:
    root = _body(_render(components(report_ledger(field_grades={}))))
    para = next(p for p in root.iter(f"{W}p") if _paragraphs(p)[0].startswith("Bankám"))
    assert f"42,5{NB}%{NB}(38,1\u201346,9{NB}%){NB}?" in _paragraphs(para)[0]
    descr = {d.get("descr") for d in para.iter(f"{WP}docPr")}
    assert descr == {"Modelováno"}  # never the strongest grade by default


def test_lists_number_and_restart_per_list(report_ledger: Any) -> None:
    root = _body(_render(components(report_ledger())))
    nums: dict[str, list[str]] = {}
    for p in root.iter(f"{W}p"):
        num = p.find(f"{W}pPr/{W}numPr/{W}numId")
        if num is not None:
            style = p.find(f"{W}pPr/{W}pStyle")
            assert style is not None
            nums.setdefault(num.get(f"{W}val"), []).append(style.get(f"{W}val"))
    assert len(nums) == 3  # the bullets, and one instance per ordered list
    assert sorted(len(v) for v in nums.values()) == [1, 2, 3]
    assert any("ListBullet2" in v for v in nums.values())


def test_quote_finding_recommendation_and_kpis(report_ledger: Any) -> None:
    root = _body(_render(components(report_ledger())))
    lines = _paragraphs(root)
    assert "\u201eBanku měním, když mě naštve.\u201c" in lines
    assert "\u2014 žena, 34 let, Brno, syntetický respondent" in lines
    for label in ("Evidence", "Co to znamená", "Jistota", "Proč", "Priorita"):
        assert label in lines
    assert f"n{NB}={NB}480" in lines  # the KPI's base: the row's effective n
    assert f"1{NB}204" in "".join(lines)
    styles = {s.get(f"{W}val") for s in root.iter(f"{W}tblStyle")}
    assert "AIAKPITable" in styles


def test_the_evidence_key_and_appendix(report_ledger: Any) -> None:
    root = _body(_render(components(report_ledger())))
    lines = _paragraphs(root)
    for grade in ("Měřeno", "Kalibrované jádro", "Modelováno", "Validace čeká", "Role neznámá"):
        assert any(grade in line for line in lines), grade
    assert any(line.startswith("? Role neznámá") for line in lines)  # no glyph: "?"
    cited = {"trust_total", "trust_ostrava", "switch_modelled", "trust_praha", "n_total"}
    assert cited <= set(lines)
    assert "trust_zlin" not in lines  # suppressed: never cited
    assert "modelováno" in lines and "orientační" in lines


def test_an_internal_report_prints_the_audit_block(report_ledger: Any) -> None:
    doc = components(
        report_ledger(ClaimSurface.INTERNAL),
        kind=ReportKind.INTERNAL,
        classification=Classification.INTERNAL,
    )
    section = replace(doc.sections[0], blocks=(AuditBlock((("model", "m-1"),)),))
    lines = _paragraphs(_body(_render(replace(doc, sections=(section,)))))
    assert "Audit" in lines and "m-1" in lines


def test_components_are_styled_only_by_name_and_render_identically(report_ledger: Any) -> None:
    doc = components(report_ledger())
    first = DocxRenderer().render(doc)
    assert first == DocxRenderer().render(doc)
    assert lint_docx(first) == []
