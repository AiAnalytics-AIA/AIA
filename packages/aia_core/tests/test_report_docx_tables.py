"""Data tables in DOCX: caption with SEQ and base n, repeating header, suppression.

A suppressed row is removed and counted in the source line; the caption's n is
the base row's effective n; units live in the header, not in every cell.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

from lxml import etree
from test_report_docx_render import _meta

from aia_core.domain.report.model import (
    Align,
    Callout,
    CalloutKind,
    Column,
    CrossRef,
    EmptyCell,
    NumberCell,
    Paragraph,
    ReportDocument,
    Section,
    Table,
    TableRow,
    Text,
    TextCell,
)
from aia_core.infrastructure.report_docx.lint import lint_docx
from aia_core.infrastructure.report_docx.renderer import DocxRenderer

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NB = "\u00a0"


def region_table(landscape: bool = False) -> Table:
    pct = Column("Důvěra", Align.RIGHT, unit="%")
    return Table(
        "tab-regions",
        "Důvěra v banky podle regionu",
        (Column("Region"), pct),
        (
            TableRow((TextCell("Praha"), NumberCell("trust_praha"))),
            TableRow((TextCell("Brno"), NumberCell("trust_brno"))),
            TableRow((TextCell("Ostrava"), NumberCell("trust_ostrava"))),
            TableRow((TextCell("Zlín"), NumberCell("trust_zlin"))),  # suppressed
            TableRow((TextCell("Jihlava"), EmptyCell())),
            TableRow((TextCell("Celkem"), NumberCell("trust_total")), emphasis=True),
        ),
        "AIA, syntetický panel 2026",
        base_ref="trust_total",
        notes=("Váženo na populaci ČR 18+.",),
        landscape=landscape,
    )


def table_document(ledger: Any, landscape: bool = False) -> ReportDocument:
    return ReportDocument(
        _meta(),
        (
            Section(
                "Výsledky",
                (
                    Callout(CalloutKind.METHOD, ()),
                    Paragraph((Text("Viz "), CrossRef("tab-regions"), Text("."))),
                    region_table(landscape),
                    Paragraph((Text("Další text."),)),
                ),
            ),
        ),
        ledger,
    )


def _render(doc: ReportDocument) -> etree._Element:
    data = DocxRenderer().render(doc)
    assert lint_docx(data) == []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return etree.fromstring(z.read("word/document.xml"))


def _t(el: etree._Element) -> str:
    return "".join(t.text or "" for t in el.iter(f"{W}t"))


def _data_table(root: etree._Element) -> etree._Element:
    for tbl in root.iter(f"{W}tbl"):
        if "Region" in _t(tbl):
            return tbl
    raise AssertionError("no data table")


def test_the_caption_numbers_titles_and_states_the_base(report_ledger: Any) -> None:
    root = _render(table_document(report_ledger()))
    caption = next(
        p
        for p in root.iter(f"{W}p")
        if "Důvěra v banky podle regionu" in _t(p)
        and p.find(f"{W}pPr/{W}pStyle").get(f"{W}val") == "Caption"
    )
    instr = [(i.text or "").strip() for i in caption.iter(f"{W}instrText")]
    assert instr == ["SEQ Tabulka \\* ARABIC"]
    assert _t(caption) == f"Tabulka 1 — Důvěra v banky podle regionu (n{NB}={NB}480; měřeno)"
    assert "viz tabulka 1" in _t(root).lower()
    assert 'TOC \\h \\z \\c "Tabulka"' in [
        (i.text or "").strip() for i in root.iter(f"{W}instrText")
    ]


def test_a_suppressed_row_is_removed_and_counted(report_ledger: Any) -> None:
    root = _render(table_document(report_ledger()))
    tbl = _data_table(root)
    rows = tbl.findall(f"{W}tr")
    firsts = [_t(r.findall(f"{W}tc")[0]) for r in rows]
    assert firsts == ["Region", "Praha", "Brno", "Ostrava", "Jihlava", "Celkem"]
    assert "Zlín" not in _t(tbl) and "51,0" not in _t(root)
    source = next(p for p in root.iter(f"{W}p") if _t(p).startswith("Zdroj:"))
    assert _t(source).endswith("Potlačeno pro nedostatečnou efektivní velikost vzorku: 1.")
    assert any(_t(p) == "Poznámka: Váženo na populaci ČR 18+." for p in root.iter(f"{W}p"))


def test_units_in_the_header_numbers_right_aligned_header_repeats(report_ledger: Any) -> None:
    tbl = _data_table(_render(table_document(report_ledger())))
    rows = tbl.findall(f"{W}tr")
    head = rows[0]
    assert head.find(f"{W}trPr/{W}tblHeader") is not None
    assert [_t(c) for c in head.findall(f"{W}tc")] == ["Region", "Důvěra (%)"]
    praha = rows[1].findall(f"{W}tc")[1]
    styles = [p.find(f"{W}pPr/{W}pStyle").get(f"{W}val") for p in praha.iter(f"{W}p")]
    assert styles == ["AIATableNumber", "AIATableNumber"]
    # the value without its unit (the header has it), the interval beneath
    assert [_t(p) for p in praha.iter(f"{W}p")] == ["48,2", f"(41,0\u201355,4{NB}%)"]
    ostrava = rows[3].findall(f"{W}tc")[1]
    assert _t(ostrava).startswith("36,1\u2020")  # indicative, explained under the table
    assert _t(rows[4].findall(f"{W}tc")[1]) == "chybí"  # missing is not zero
    total = rows[5].findall(f"{W}tc")[0]
    assert total.find(f".//{W}rStyle").get(f"{W}val") == "Strong"


def test_a_landscape_table_gets_its_own_section(report_ledger: Any) -> None:
    root = _render(table_document(report_ledger(), landscape=True))
    sections = list(root.iter(f"{W}sectPr"))
    orients = [s.find(f"{W}pgSz").get(f"{W}orient") for s in sections]
    assert orients[-2] == "landscape" and orients[-1] in (None, "portrait")
    wide = sections[-2].find(f"{W}pgSz")
    assert int(wide.get(f"{W}w")) > int(wide.get(f"{W}h"))
    assert all(s.find(f"{W}pgNumType").get(f"{W}start") is None for s in sections[3:])


def test_a_landscape_page_has_running_heads_at_its_own_width(report_ledger: Any) -> None:
    data = DocxRenderer().render(table_document(report_ledger(), landscape=True))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        styles = {
            p.find(f"{W}pPr/{W}pStyle").get(f"{W}val")
            for n in z.namelist()
            if n.startswith(("word/header", "word/footer"))
            for p in etree.fromstring(z.read(n)).iter(f"{W}p")
        }
    assert {"AIAHeaderLandscape", "AIAFooterLandscape", "Header", "Footer"} <= styles
