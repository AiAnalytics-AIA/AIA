"""The report's outline numbers and the DOCX style sheet built from print tokens."""

from __future__ import annotations

from datetime import date
from typing import Any

from docx import Document
from docx.oxml.ns import qn

from aia_core.domain.evidence.validation import METHOD_STATUS_PENDING
from aia_core.domain.report.model import (
    Chart,
    ChartKind,
    Figure,
    Heading,
    ReportDocument,
    ReportKind,
    ReportMeta,
    Section,
    Series,
)
from aia_core.domain.report.outline import appendix_letter, build_outline
from aia_core.domain.report.print_tokens import STYLES
from aia_core.infrastructure.report_docx.styles import PARAGRAPHS, S, install_styles


def test_appendix_letters() -> None:
    assert [appendix_letter(i) for i in (0, 25, 26)] == ["A", "Z", "AA"]


def test_outline_numbers_chapters_headings_figures_and_appendices(report_ledger: Any) -> None:
    fig = Figure(
        "fig-1",
        "Důvěra",
        Chart(ChartKind.BAR, ("Praha",), (Series("x", ("trust_praha",)),), "%"),
        "AIA",
        "alt",
    )
    meta = ReportMeta(
        ReportKind.CLIENT, "T", "S", "C", "St", "STU-1", date(2026, 9, 25), 1, METHOD_STATUS_PENDING
    )
    doc = ReportDocument(
        meta,
        (
            Section("Shrnutí", (Heading("A", 2), Heading("B", 3), fig), id="ch-1"),
            Section("Metodika", (Heading("C", 2, id="h-c"),)),
            Section("Dotazník", (), appendix=True),
        ),
        report_ledger(),
    )
    o = build_outline(doc)
    assert o.chapter_numbers == ("1", "2", "A")
    assert [h.number for h in o.headings] == ["1", "1.1", "1.1.1", "2", "2.1", "A"]
    assert o.labels == {"ch-1": "kapitola 1", "fig-1": "graf 1", "h-c": "oddíl 2.1"}


def test_every_paragraph_style_comes_from_a_print_token() -> None:
    assert {spec.token for spec in PARAGRAPHS.values()} <= set(STYLES)


def test_the_style_sheet_installs_with_no_theme_fonts() -> None:
    document = Document()
    install_styles(document)
    names = {s.name for s in document.styles}
    for name in (S.BODY, S.H1, S.CAPTION, S.TOC_1, S.FOOTNOTE, S.DATA_TABLE, S.STRONG):
        assert name in names, name
    xml = document.styles.element.xml
    assert "asciiTheme" not in xml and "hAnsiTheme" not in xml
    h1 = document.styles[S.H1].element
    assert h1.find(qn("w:rPr")).find(qn("w:rFonts")).get(qn("w:ascii")) == STYLES["doc-h1"].font


def test_starter_theme_furniture_cannot_override_the_aia_template() -> None:
    from aia_core.infrastructure.report_docx.ooxml import el

    document = Document()
    props = document.styles["Title"].element.get_or_add_pPr()
    props.append(el("w:pBdr"))
    props.append(el("w:shd", fill="FF0000"))
    props.append(el("w:contextualSpacing"))
    install_styles(document)
    title = document.styles[S.TITLE].element.get_or_add_pPr()
    assert all(title.find(qn(tag)) is None for tag in ("w:pBdr", "w:shd", "w:contextualSpacing"))
    assert PARAGRAPHS[S.FINDING_TITLE].token == "doc-body"
