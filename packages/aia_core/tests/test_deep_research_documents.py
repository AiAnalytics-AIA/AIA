"""A document's text, its layout, where a quote lies, its outline and its parts.

Pure: the documents are built here from what a reader would hand over; the
readers themselves are tested in ``test_web_documents.py``. All content fictional.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from aia_core.domain.deep_research import documents
from aia_core.domain.deep_research.contracts import RetrievalMode, SourceSnapshot
from aia_core.domain.deep_research.documents import (
    CapturedDocument,
    DocumentRefused,
    GridContent,
    GridRow,
    PartRefused,
    PdfBookmark,
    PdfContent,
    column_letters,
    document_outline,
    grid_document,
    locate_span,
    pdf_document,
    read_part,
    sheet_reference,
)
from aia_core.domain.deep_research.grounding import (
    GroundableSource,
    detect_instructions,
    ground,
    normalise_text,
)

NOW = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)


def _snapshot(doc: CapturedDocument, media: str) -> SourceSnapshot:
    sha = hashlib.sha256(doc.text.encode()).hexdigest()
    return SourceSnapshot(
        snapshot_id="SNP-" + sha[:24],
        url="https://stats.example/doc",
        canonical_url="https://stats.example/doc",
        final_url="https://stats.example/doc",
        redirects=(),
        title=doc.title,
        retrieved_at=NOW,
        http_status=200,
        content_type=media,
        raw_sha256="0" * 64,
        raw_bytes=1,
        text=doc.text,
        text_sha256=sha,
        truncated=doc.truncated,
        adapter="recorded-fetch-v1",
        request_id=None,
        retrieval_mode=RetrievalMode.RECORDED,
        instructions_detected=detect_instructions(doc.text),
        document=doc.layout,
    )


def _span(snap: SourceSnapshot, quote: str, claim: str) -> tuple[int, int]:
    verdict = ground(
        source_ref="S1",
        quote=quote,
        claim=claim,
        sources={"S1": GroundableSource("S1", snap.text, snap.instructions_detected)},
    )
    assert verdict.grounded, verdict.detail
    assert verdict.span is not None
    return verdict.span


PAGES = (
    "Výroční zpráva 2025\nFiktivní statistický úřad",
    "Obsah\n1. Úvod\n2. Spotřeba",
    "Tabulka 3: Spotřeba nápojů\nPraha    12,5 l na osobu\nBrno 9,4 l na osobu",
    "",
    "Závěr: spotřeba roste\u00a0rychleji, než se čekalo.",
)


def _pdf() -> SourceSnapshot:
    content = PdfContent(
        pages=PAGES,
        title="Výroční zpráva",
        bookmarks=(
            PdfBookmark("Úvod", 0, 2),
            PdfBookmark("Spotřeba", 0, 3),
            PdfBookmark("Tabulky", 1, 3),
            PdfBookmark("Mimo", 0, 99),
        ),
    )
    return _snapshot(pdf_document(content), "application/pdf")


def test_a_pdf_is_its_pages_normalised_in_order() -> None:
    snap = _pdf()
    assert normalise_text(snap.text) == snap.text
    assert snap.text.startswith("Výroční zpráva 2025 Fiktivní statistický úřad Obsah")
    assert snap.title == "Výroční zpráva"
    layout = snap.document
    assert layout is not None and layout.kind == "pdf" and layout.page_count == 5
    # The empty page 4 has nothing to point at; every other page its own text.
    assert [p.page for p in layout.pages] == [1, 2, 3, 5]
    for page, raw in zip(layout.pages, (PAGES[0], PAGES[1], PAGES[2], PAGES[4]), strict=True):
        assert snap.text[page.start : page.end] == normalise_text(raw)


def test_a_quote_on_page_three_is_located_on_page_three() -> None:
    snap = _pdf()
    span = _span(snap, "Praha 12,5 l na osobu", "V Praze se vypije 12,5 l na osobu.")
    assert [loc.ref for loc in locate_span(snap, span)] == ["p. 3"]
    across = _span(snap, "Brno 9,4 l na osobu Závěr: spotřeba roste", "Spotřeba roste.")
    assert [loc.page for loc in locate_span(snap, across)] == [3, 5]


def test_a_pdf_keeps_its_bookmarks_and_drops_a_page_it_does_not_have() -> None:
    layout = _pdf().document
    assert layout is not None
    assert [(b.title, b.level, b.page) for b in layout.bookmarks] == [
        ("Úvod", 0, 2),
        ("Spotřeba", 0, 3),
        ("Tabulky", 1, 3),
        ("Mimo", 0, None),
    ]


def test_a_pdf_over_the_page_bound_or_without_text_is_refused() -> None:
    with pytest.raises(DocumentRefused) as many:
        pdf_document(PdfContent(pages=("x",) * (documents.PDF_MAX_PAGES + 1)))
    assert many.value.reason == "document_too_many_pages"
    with pytest.raises(DocumentRefused) as scanned:
        pdf_document(PdfContent(pages=("", "  \n ")))
    assert scanned.value.reason == "document_no_text"


def test_a_pdf_past_the_text_cap_is_cut_at_a_page_and_says_so() -> None:
    doc = pdf_document(PdfContent(pages=("a" * 30, "b" * 30, "c" * 30)), max_chars=45)
    assert doc.truncated and len(doc.text) == 45
    assert [(p.page, p.start, p.end) for p in doc.layout.pages] == [(1, 0, 30), (2, 31, 45)]


# --------------------------------------------------------------------------- #
# Grids
# --------------------------------------------------------------------------- #


def _row(number: int, *values: str) -> GridRow:
    return GridRow(number=number, values=values)


KRAJE = GridContent(
    name="Kraje 2024",
    rows=(
        _row(1, "Tabulka 1: Spotřeba nápojů podle krajů (l na osobu)"),
        _row(3, "Kraj", "2023", "2024"),
        _row(4, "Hlavní město Praha", "11.8", "12.5"),
        _row(5, "Jihomoravský kraj", "", "9.4"),
        _row(7, "Pozn.: údaje za rok 2024 jsou předběžné."),
    ),
)
SOUHRN = GridContent(name="Souhrn", rows=(_row(2, "", "Celkem", "21.9"),))


def _xlsx() -> SourceSnapshot:
    doc = grid_document("xlsx", (KRAJE, SOUHRN), title="Spotřeba")
    return _snapshot(doc, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def test_a_sheet_renders_as_rows_with_empty_slots_kept() -> None:
    snap = _xlsx()
    assert normalise_text(snap.text) == snap.text
    assert snap.text == (
        "## Kraje 2024 | Tabulka 1: Spotřeba nápojů podle krajů (l na osobu) |"
        " | Kraj | 2023 | 2024 | | Hlavní město Praha | 11.8 | 12.5 |"
        " | Jihomoravský kraj | | 9.4 | | Pozn.: údaje za rok 2024 jsou předběžné. |"
        " ## Souhrn | Celkem | 21.9 |"
    )
    layout = snap.document
    assert layout is not None
    kraje, souhrn = layout.sheets
    assert (kraje.header_row, kraje.label_column) == (3, 1)
    assert kraje.caption == ("Tabulka 1: Spotřeba nápojů podle krajů (l na osobu)",)
    assert kraje.notes == ("Pozn.: údaje za rok 2024 jsou předběžné.",)
    # Every cell's span is its value.
    values = {(r, c): snap.text[s:e] for r, c, s, e in kraje.cells}
    assert values[(4, 3)] == "12.5" and values[(5, 3)] == "9.4" and (5, 2) not in values
    # A sheet starting in column B starts its rows there.
    assert [(r, c) for r, c, *_ in souhrn.cells] == [(2, 2), (2, 3)]


def test_a_number_grounds_to_its_cell_with_its_labels_and_notes() -> None:
    snap = _xlsx()
    span = _span(snap, "Hlavní město Praha | 11.8 | 12.5", "Praha: 12.5 l na osobu.")
    found = locate_span(snap, span)
    assert [loc.ref for loc in found] == ["'Kraje 2024'!A4", "'Kraje 2024'!B4", "'Kraje 2024'!C4"]
    cell = found[-1]
    assert (cell.sheet, cell.address, cell.row, cell.column) == ("Kraje 2024", "C4", 4, 3)
    assert (cell.row_label, cell.column_label) == ("Hlavní město Praha", "2024")
    assert cell.notes == ("Pozn.: údaje za rok 2024 jsou předběžné.",)
    assert cell.caption == ("Tabulka 1: Spotřeba nápojů podle krajů (l na osobu)",)
    # The row label is a label itself: it has a column label and no row label.
    assert (found[0].row_label, found[0].column_label) == (None, "Kraj")


def test_a_header_cell_has_no_labels() -> None:
    snap = _xlsx()
    span = _span(snap, "| Kraj | 2023 | 2024 |", "Sloupce jsou kraje a roky.")
    header = locate_span(snap, span)
    assert [loc.address for loc in header] == ["A3", "B3", "C3"]
    assert all(loc.row_label is None and loc.column_label is None for loc in header)


def test_a_csv_is_one_grid_with_its_first_row_as_headers() -> None:
    csv = GridContent(
        name="",
        rows=(
            _row(1, "obec", "obyvatel", "podíl"),
            _row(2, "Horní Lhota", "1204", "0.31"),
            _row(3, "Dolní Lhota", "877", "0.22"),
        ),
    )
    snap = _snapshot(grid_document("csv", (csv,)), "text/csv")
    assert snap.text == (
        "| obec | obyvatel | podíl | | Horní Lhota | 1204 | 0.31 | | Dolní Lhota | 877 | 0.22 |"
    )
    span = _span(snap, "Dolní Lhota | 877 | 0.22", "Dolní Lhota má 877 obyvatel.")
    cell = locate_span(snap, span)[1]
    assert (cell.ref, cell.sheet, cell.row_label, cell.column_label) == (
        "B3",
        None,
        "Dolní Lhota",
        "obyvatel",
    )
    with pytest.raises(ValueError):
        grid_document("csv", (csv, csv))


def test_a_grid_without_values_is_refused() -> None:
    with pytest.raises(DocumentRefused) as empty:
        grid_document("csv", (GridContent(name="", rows=(_row(1, "", " "),)),))
    assert empty.value.reason == "document_no_text"


def test_a_grid_past_the_text_cap_keeps_only_whole_cells() -> None:
    rows = tuple(_row(n, f"radek {n}", str(n * 10)) for n in range(1, 40))
    doc = grid_document("csv", (GridContent(name="", rows=rows),), max_chars=100)
    assert doc.truncated and len(doc.text) <= 100
    sheet = doc.layout.sheets[0]
    assert sheet.truncated and all(e <= len(doc.text) for *_, e in sheet.cells)
    assert sheet.cells and sheet.cells[-1][3] <= 100


def test_addresses_and_sheet_references() -> None:
    assert [column_letters(n) for n in (1, 26, 27, 52, 703)] == ["A", "Z", "AA", "AZ", "AAA"]
    assert sheet_reference("List1") == "List1"
    assert sheet_reference("Obyvatelé") == "Obyvatelé"
    assert sheet_reference("Kraje 2024") == "'Kraje 2024'"
    assert sheet_reference("Jan's") == "'Jan''s'"
    with pytest.raises(ValueError):
        column_letters(0)


# --------------------------------------------------------------------------- #
# Outline and parts
# --------------------------------------------------------------------------- #


def test_the_outline_of_each_kind() -> None:
    pdf = document_outline(_pdf())
    assert (pdf.kind, pdf.page_count, pdf.pages_kept, len(pdf.bookmarks)) == ("pdf", 5, 4, 4)
    xlsx = document_outline(_xlsx())
    kraje, souhrn = xlsx.sheets
    assert (kraje.name, kraje.used_range, kraje.rows, kraje.columns) == (
        "Kraje 2024",
        "A1:C7",
        5,
        3,
    )
    assert kraje.header_row == 3
    assert kraje.column_labels == (("A", "Kraj"), ("B", "2023"), ("C", "2024"))
    assert kraje.notes == ("Pozn.: údaje za rok 2024 jsou předběžné.",)
    assert (souhrn.used_range, souhrn.header_row) == ("B2:C2", 2)


def test_a_pdf_part_is_its_pages_and_each_line_grounds() -> None:
    snap = _pdf()
    part = read_part(snap, "p. 2-3")
    assert part.ref == "p. 2-3" and not part.truncated
    assert [line.label for line in part.lines] == ["p. 2", "p. 3"]
    assert all(line.text in snap.text for line in part.lines)
    assert read_part(snap, "strany 3\u20135").ref == "p. 3-5"
    assert [line.label for line in read_part(snap, "pages 3-9").lines] == ["p. 3", "p. 5"]
    assert read_part(snap, "p. 4").lines == ()
    for bad, reason in (
        ("p. 9", "part_out_of_range"),
        ("p. 3-2", "part_invalid"),
        ("A1", "part_invalid"),
    ):
        with pytest.raises(PartRefused) as refused:
            read_part(snap, bad)
        assert refused.value.reason == reason


def test_a_sheet_a_range_and_rows_of_a_workbook() -> None:
    snap = _xlsx()
    whole = read_part(snap, "'Kraje 2024'")
    assert whole.ref == "'Kraje 2024'!A1:C7" and len(whole.lines) == 5
    assert read_part(snap, "Kraje 2024").ref == whole.ref
    ranged = read_part(snap, "'Kraje 2024'!B3:C5")
    assert ranged.ref == "'Kraje 2024'!B3:C5"
    assert [(line.label, line.text) for line in ranged.lines] == [
        ("3", "2023 | 2024"),
        ("4", "11.8 | 12.5"),
        ("5", "9.4"),
    ]
    assert ranged.column_labels == (("B", "2023"), ("C", "2024"))
    rows = read_part(snap, "'Kraje 2024'!4:5")
    assert [line.text for line in rows.lines] == [
        "Hlavní město Praha | 11.8 | 12.5",
        "Jihomoravský kraj | | 9.4",
    ]
    assert all(line.text in snap.text for part in (whole, ranged, rows) for line in part.lines)
    with pytest.raises(PartRefused) as unknown:
        read_part(snap, "Okresy!A1:B2")
    assert unknown.value.reason == "part_unknown_sheet"
    with pytest.raises(PartRefused) as bare:
        read_part(snap, "A1:B2")  # two sheets: a bare range names none
    assert bare.value.reason == "part_unknown_sheet"


def test_rows_of_a_csv_and_a_part_cut_at_its_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = tuple(_row(n, f"obec {n}", str(n)) for n in range(1, 30))
    snap = _snapshot(grid_document("csv", (GridContent(name="", rows=rows),)), "text/csv")
    part = read_part(snap, "rows 2-4")
    assert part.ref == "A2:B4" and [line.label for line in part.lines] == ["2", "3", "4"]
    assert read_part(snap, "B10:B11").lines[0].text == "10"
    monkeypatch.setattr(documents, "MAX_PART_CHARS", 30)
    cut = read_part(snap, "2:29")
    assert cut.truncated and cut.ref == "A2:B4"
    assert sum(len(line.text) for line in cut.lines) <= 30


def test_a_page_has_no_parts() -> None:
    page = _pdf().model_copy(update={"document": None})
    with pytest.raises(PartRefused) as refused:
        read_part(page, "p. 1")
    assert refused.value.reason == "not_a_document"
    with pytest.raises(PartRefused):
        document_outline(page)


def test_a_document_snapshot_round_trips_and_a_page_omits_the_key() -> None:
    snap = _xlsx()
    dumped = snap.model_dump(mode="json")
    assert dumped["document"]["kind"] == "xlsx"
    assert SourceSnapshot.model_validate(dumped) == snap
    page = snap.model_copy(update={"document": None})
    assert "document" not in page.model_dump(mode="json")
