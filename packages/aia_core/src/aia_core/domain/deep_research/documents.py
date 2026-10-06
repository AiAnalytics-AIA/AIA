"""Documents as sources: a PDF's pages and an XLSX's or a CSV's grid, as groundable text.

Plan ``deep-research-web-search.md`` chunk 6, §§ 5.3 and 8.2. A document becomes a
:class:`~.contracts.SourceSnapshot` like a page: its text is normalised the way a
page's is (:func:`~.grounding.normalise_text`), so a quote grounds in it, and
``detect_instructions`` screens it, exactly as for HTML. What a page lacks and a
document has is a **layout** (:class:`~.contracts.DocumentLayout`), which maps any
span of that text back to where it came from:

* **PDF** -- each page's text, in page order, one space between pages. A quote's
  span maps to the page or pages it lies on (:func:`locate_span`). The file's own
  outline (bookmarks) is kept as it declares it.
* **XLSX, CSV** -- each sheet a grid of rows. A row renders as
  ``| v1 | v2 | | v4 |`` (an empty cell is an empty slot, so columns stay where
  they are), rows one space apart, an XLSX sheet headed ``## <name>``. A span maps
  to the cells it covers, each with its address (``List1!B3``, ``B3`` in a CSV), its
  row and column labels, and the sheet's caption and notes
  (:class:`~.contracts.DocumentSheet` says how those are found).

PDF table structure (cells, headers, captions inside a PDF) is not extracted:
pypdf yields flat text, and no table extractor is a dependency. A number in a PDF
table grounds to its page.

:func:`read_part` serves a part of a captured document -- pages of a PDF, a sheet
or a range of an XLSX, rows of a CSV -- from the snapshot alone; nothing leaves
the process. Every line it returns is a substring of the snapshot's text, so a
quote copied from a part grounds against the whole. :func:`document_outline`
says what parts there are.

The readers that turn bytes into :class:`PdfContent` and :class:`GridContent`
are in ``infrastructure.document_text``; everything here is pure: stdlib and the
contracts.
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from .contracts import (
    DocumentBookmark,
    DocumentLayout,
    DocumentPage,
    DocumentSheet,
    SourceSnapshot,
)
from .grounding import normalise_text

__all__ = [
    "MAX_BOOKMARKS",
    "MAX_DOCUMENT_TEXT_CHARS",
    "MAX_GRID_CELLS",
    "MAX_GRID_COLUMNS",
    "MAX_GRID_ROWS",
    "MAX_GRID_SHEETS",
    "MAX_LABEL_LINES",
    "MAX_PART_CHARS",
    "PDF_MAX_PAGES",
    "ZIP_MAX_RATIO",
    "CapturedDocument",
    "DocumentOutline",
    "DocumentPart",
    "DocumentRefused",
    "GridContent",
    "GridRow",
    "Locator",
    "PartLine",
    "PartRefused",
    "PdfBookmark",
    "PdfContent",
    "SheetOutline",
    "cell_address",
    "column_letters",
    "document_outline",
    "grid_document",
    "locate_span",
    "pdf_document",
    "read_part",
    "sheet_reference",
]

#: A PDF of more pages is refused: past it, a source is a book, and the ladder
#: looks for its chapter instead (a statistical yearbook is published by chapter).
PDF_MAX_PAGES: Final = 400
#: A document's normalised text kept per snapshot; ten times a page's
#: (``web.MAX_TEXT_CHARS``), because a document is read in parts, never whole.
MAX_DOCUMENT_TEXT_CHARS: Final = 2_000_000
#: Non-empty cells read from one document; past it, the rest is not read.
MAX_GRID_CELLS: Final = 100_000
#: Rows and columns read per sheet, and sheets per workbook; past them, truncated.
MAX_GRID_ROWS: Final = 100_000
MAX_GRID_COLUMNS: Final = 500
MAX_GRID_SHEETS: Final = 50
#: An XLSX whose members declare more than this many times its own size is not
#: opened (beside ``document_text``'s member-count and total-size bounds).
ZIP_MAX_RATIO: Final = 100
#: Bookmarks kept from a PDF's outline.
MAX_BOOKMARKS: Final = 500
#: Caption and note lines kept per sheet, and their length.
MAX_LABEL_LINES: Final = 10
_MAX_LABEL_CHARS: Final = 500
#: The most text one part serves; a longer part says it is truncated.
MAX_PART_CHARS: Final = 20_000


class DocumentRefused(Exception):
    """A document the fetcher will not keep. ``reason`` is stable."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class PartRefused(Exception):
    """A part that cannot be served from a snapshot. ``reason`` is stable."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


# --------------------------------------------------------------------------- #
# What the readers hand over
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PdfBookmark:
    title: str
    level: int
    page: int | None


@dataclass(frozen=True, slots=True)
class PdfContent:
    """A PDF as read: each page's text in order, and what the file says of itself."""

    pages: tuple[str, ...]
    title: str = ""
    bookmarks: tuple[PdfBookmark, ...] = ()


@dataclass(frozen=True, slots=True)
class GridRow:
    """One sheet row as read: its 1-based number, its values from column A on."""

    number: int
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GridContent:
    """One sheet (or a CSV) as read; ``truncated`` when a bound stopped the reader."""

    name: str
    rows: tuple[GridRow, ...]
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class CapturedDocument:
    """A document's snapshot text, its layout, and whether a bound cut either."""

    title: str
    text: str
    layout: DocumentLayout
    truncated: bool


# --------------------------------------------------------------------------- #
# Addresses
# --------------------------------------------------------------------------- #


def column_letters(column: int) -> str:
    """``1`` -> ``A``, ``27`` -> ``AA``: a spreadsheet's column name."""
    if column < 1:
        raise ValueError("columns count from 1")
    letters = ""
    while column:
        column, rest = divmod(column - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def _column_number(letters: str) -> int:
    number = 0
    for char in letters.upper():
        number = number * 26 + ord(char) - ord("A") + 1
    return number


def cell_address(row: int, column: int) -> str:
    return f"{column_letters(column)}{row}"


_PLAIN_SHEET: Final = re.compile(r"^\w+$")


def sheet_reference(name: str) -> str:
    """A sheet's name as a reference prefix: ``List1``, or ``'Kraje 2024'`` quoted."""
    if _PLAIN_SHEET.match(name):
        return name
    return "'" + name.replace("'", "''") + "'"


# --------------------------------------------------------------------------- #
# Building the text
# --------------------------------------------------------------------------- #


class _Text:
    """Normalised text built piece by piece, with every piece's offsets known."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self.length = 0

    def segment(self, value: str) -> tuple[int, int]:
        """Append ``value`` (normalised, non-empty) one space after what is there."""
        if self.length:
            self._parts.append(" ")
            self.length += 1
        return self.glue(value)

    def glue(self, value: str) -> tuple[int, int]:
        """Append ``value`` directly."""
        start = self.length
        self._parts.append(value)
        self.length += len(value)
        return start, self.length

    def text(self) -> str:
        return "".join(self._parts)


def _clip(text: str, max_chars: int) -> tuple[str, int, bool]:
    """``text`` cut to ``max_chars`` (trailing space dropped), its length, and if it was cut."""
    if len(text) <= max_chars:
        return text, len(text), False
    kept = text[:max_chars].rstrip()
    return kept, len(kept), True


def _checked(text: str) -> None:
    # The layout's offsets are offsets in the text grounding searches; they hold only
    # if normalising the text changes nothing (it never does, piece by piece; this
    # guards the joins).
    if normalise_text(text) != text:
        raise DocumentRefused(
            "the document's text does not normalise stably", reason="document_malformed"
        )


def pdf_document(
    content: PdfContent, *, max_chars: int = MAX_DOCUMENT_TEXT_CHARS
) -> CapturedDocument:
    """A PDF's snapshot text (its pages, in order) and the page each span lies on."""
    if len(content.pages) > PDF_MAX_PAGES:
        raise DocumentRefused(
            f"the PDF has {len(content.pages)} pages; at most {PDF_MAX_PAGES} are kept",
            reason="document_too_many_pages",
        )
    built = _Text()
    spans: list[tuple[int, int, int]] = []
    for number, raw in enumerate(content.pages, start=1):
        page = normalise_text(raw)
        start, end = built.segment(page) if page else (built.length, built.length)
        spans.append((number, start, end))
    text, length, truncated = _clip(built.text(), max_chars)
    if not text:
        raise DocumentRefused(
            "the PDF has no text to read (a scanned document needs OCR, which AIA does not do)",
            reason="document_no_text",
        )
    _checked(text)
    # A page with no text, or past the cut, has nothing to point at.
    pages = tuple(
        DocumentPage(page=n, start=s, end=min(e, length))
        for n, s, e in spans
        if s < e and s < length
    )
    bookmarks = tuple(
        DocumentBookmark(
            title=normalise_text(b.title)[:_MAX_LABEL_CHARS],
            level=b.level,
            page=b.page if b.page is not None and 1 <= b.page <= len(content.pages) else None,
        )
        for b in content.bookmarks[:MAX_BOOKMARKS]
    )
    layout = DocumentLayout(
        kind="pdf", page_count=len(content.pages), pages=pages, bookmarks=bookmarks
    )
    return CapturedDocument(
        title=normalise_text(content.title)[:500], text=text, layout=layout, truncated=truncated
    )


@dataclass(frozen=True, slots=True)
class _Table:
    header_row: int | None
    label_column: int | None
    caption: tuple[str, ...]
    notes: tuple[str, ...]


def _table(rows: Sequence[tuple[int, dict[int, str]]]) -> _Table:
    """The header row, the label column, the caption and the notes, by the stated rules."""
    if not rows:
        return _Table(None, None, (), ())
    wide = [i for i, (_, cells) in enumerate(rows) if len(cells) >= 2]
    header_at = wide[0] if wide else 0
    last_at = wide[-1] if wide else len(rows) - 1
    caption = tuple(
        " ".join(cells[c] for c in sorted(cells))[:_MAX_LABEL_CHARS]
        for _, cells in rows[:header_at]
    )[:MAX_LABEL_LINES]
    notes = tuple(
        " ".join(cells[c] for c in sorted(cells))[:_MAX_LABEL_CHARS]
        for _, cells in rows[last_at + 1 :]
        if len(cells) == 1
    )[:MAX_LABEL_LINES]
    body = rows[header_at + 1 : last_at + 1]
    columns = {c for _, cells in rows[header_at : last_at + 1] for c in cells}
    label_column = None
    if len(columns) >= 2:
        below = {c for _, cells in body for c in cells}
        label_column = min(below) if below else None
    return _Table(rows[header_at][0], label_column, caption, notes)


def grid_document(
    kind: Literal["xlsx", "csv"],
    sheets: Sequence[GridContent],
    *,
    title: str = "",
    truncated: bool = False,
    max_chars: int = MAX_DOCUMENT_TEXT_CHARS,
) -> CapturedDocument:
    """An XLSX's or a CSV's snapshot text (its rows, in order) and the cell each span is."""
    if kind == "csv" and len(sheets) != 1:
        raise ValueError("a CSV is one grid")
    built = _Text()
    drafts: list[tuple[str, int, int, _Table, list[tuple[int, int, int, int]], bool]] = []
    for sheet in sheets:
        name = normalise_text(sheet.name)[:200]
        sheet_start = built.length + (1 if built.length else 0)
        if kind == "xlsx":
            built.segment(f"## {name}" if name else "##")
        rows: list[tuple[int, dict[int, str]]] = []
        for row in sheet.rows:
            cells = {
                c: v
                for c, v in ((c, normalise_text(raw)) for c, raw in enumerate(row.values, 1))
                if v
            }
            if cells:
                rows.append((row.number, cells))
        first_column = min((min(cells) for _, cells in rows), default=1)
        spans: list[tuple[int, int, int, int]] = []
        for number, cells in rows:
            built.segment("|")
            for column in range(first_column, max(cells) + 1):
                value = cells.get(column)
                if value:
                    start, end = built.glue(" " + value)
                    spans.append((number, column, start + 1, end))
                built.glue(" |")
        drafts.append(
            (
                name,
                min(sheet_start, built.length),
                built.length,
                _table(rows),
                spans,
                sheet.truncated,
            )
        )
    text, length, cut = _clip(built.text(), max_chars)
    if not text or not any(spans for *_, spans, _ in drafts):
        raise DocumentRefused("the document has no cell with a value", reason="document_no_text")
    _checked(text)
    layout_sheets = tuple(
        DocumentSheet(
            name=name,
            start=start,
            end=min(end, length),
            header_row=table.header_row,
            label_column=table.label_column,
            caption=table.caption,
            notes=table.notes,
            cells=tuple(cell for cell in spans if cell[3] <= length),
            truncated=sheet_truncated or end > length,
        )
        for name, start, end, table, spans, sheet_truncated in drafts
        if start < length or start == 0
    )
    return CapturedDocument(
        title=normalise_text(title)[:500],
        text=text,
        layout=DocumentLayout(kind=kind, sheets=layout_sheets),
        truncated=truncated or cut or any(s.truncated for s in layout_sheets),
    )


# --------------------------------------------------------------------------- #
# Where a span came from
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Locator:
    """Where a span of a document's text lies: a page, or a cell with its labels.

    ``ref`` is the human form (``p. 3``, ``List1!B3``, ``B3``). For a cell,
    ``row_label`` and ``column_label`` are the values the sheet's label column and
    header row hold for it (None where there is none, or the cell is a label
    itself), and the sheet's ``caption`` and ``notes`` travel with it.
    """

    ref: str
    page: int | None = None
    sheet: str | None = None
    address: str | None = None
    row: int | None = None
    column: int | None = None
    row_label: str | None = None
    column_label: str | None = None
    caption: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def _layout(snapshot: SourceSnapshot) -> DocumentLayout:
    if snapshot.document is None:
        raise PartRefused(
            f"{snapshot.snapshot_id} is a page, not a document", reason="not_a_document"
        )
    return snapshot.document


def _value(snapshot: SourceSnapshot, sheet: DocumentSheet, row: int, column: int) -> str | None:
    for r, c, start, end in sheet.cells:
        if r == row and c == column:
            return snapshot.text[start:end]
    return None


def _cell_ref(kind: str, sheet: DocumentSheet, row: int, column: int) -> str:
    address = cell_address(row, column)
    return address if kind == "csv" else f"{sheet_reference(sheet.name)}!{address}"


def _cell_locator(
    snapshot: SourceSnapshot, kind: str, sheet: DocumentSheet, row: int, column: int
) -> Locator:
    header = sheet.header_row
    labelled = header is not None and row > header
    column_label = _value(snapshot, sheet, header, column) if header and row > header else None
    row_label = None
    if labelled and sheet.label_column is not None and column != sheet.label_column:
        row_label = _value(snapshot, sheet, row, sheet.label_column)
    return Locator(
        ref=_cell_ref(kind, sheet, row, column),
        sheet=None if kind == "csv" else sheet.name,
        address=cell_address(row, column),
        row=row,
        column=column,
        row_label=row_label,
        column_label=column_label,
        caption=sheet.caption,
        notes=sheet.notes,
    )


def locate_span(snapshot: SourceSnapshot, span: tuple[int, int]) -> tuple[Locator, ...]:
    """The pages, or the cells, a span of a document snapshot's text overlaps.

    ``span`` is what grounding returns for a quote (``Grounding.span``): offsets
    in the snapshot's text. A span that covers only a separator overlaps nothing.
    Raises :class:`PartRefused` for a page snapshot.
    """
    layout = _layout(snapshot)
    start, end = span
    if layout.kind == "pdf":
        return tuple(
            Locator(ref=f"p. {p.page}", page=p.page)
            for p in layout.pages
            if p.start < end and start < p.end
        )
    found: list[Locator] = []
    for sheet in layout.sheets:
        if sheet.end <= start or end <= sheet.start:
            continue
        starts = [cell[2] for cell in sheet.cells]
        at = max(bisect.bisect_right(starts, start) - 1, 0)
        for row, column, cell_start, cell_end in sheet.cells[at:]:
            if cell_start >= end:
                break
            if cell_end > start:
                found.append(_cell_locator(snapshot, layout.kind, sheet, row, column))
    return tuple(found)


# --------------------------------------------------------------------------- #
# Outline
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SheetOutline:
    """One grid: its used range, its size, its column labels, caption and notes."""

    name: str
    used_range: str
    rows: int
    columns: int
    header_row: int | None
    column_labels: tuple[tuple[str, str], ...]
    caption: tuple[str, ...]
    notes: tuple[str, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class DocumentOutline:
    """What parts a captured document has, for choosing one to read."""

    kind: Literal["pdf", "xlsx", "csv"]
    page_count: int | None
    pages_kept: int
    bookmarks: tuple[DocumentBookmark, ...]
    sheets: tuple[SheetOutline, ...]
    truncated: bool


def _sheet_outline(snapshot: SourceSnapshot, sheet: DocumentSheet) -> SheetOutline:
    if not sheet.cells:
        return SheetOutline(
            sheet.name, "", 0, 0, None, (), sheet.caption, sheet.notes, sheet.truncated
        )
    rows = sorted({r for r, *_ in sheet.cells})
    columns = sorted({c for _, c, *_ in sheet.cells})
    labels: tuple[tuple[str, str], ...] = ()
    if sheet.header_row is not None:
        labels = tuple(
            (column_letters(c), snapshot.text[s:e])
            for r, c, s, e in sheet.cells
            if r == sheet.header_row
        )
    used = f"{cell_address(rows[0], columns[0])}:{cell_address(rows[-1], columns[-1])}"
    return SheetOutline(
        name=sheet.name,
        used_range=used,
        rows=len(rows),
        columns=len(columns),
        header_row=sheet.header_row,
        column_labels=labels,
        caption=sheet.caption,
        notes=sheet.notes,
        truncated=sheet.truncated,
    )


def document_outline(snapshot: SourceSnapshot) -> DocumentOutline:
    """A PDF's page count and bookmarks; each sheet's used range and labels; a CSV's header."""
    layout = _layout(snapshot)
    return DocumentOutline(
        kind=layout.kind,
        page_count=layout.page_count,
        pages_kept=len(layout.pages),
        bookmarks=layout.bookmarks,
        sheets=tuple(_sheet_outline(snapshot, s) for s in layout.sheets),
        truncated=snapshot.truncated,
    )


# --------------------------------------------------------------------------- #
# Parts
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PartLine:
    """One page or one row of a part. ``text`` is a substring of the snapshot's text."""

    label: str
    text: str


@dataclass(frozen=True, slots=True)
class DocumentPart:
    """A part of a captured document, served from the snapshot alone.

    ``ref`` names what was served (``p. 3-5``, ``List1!A2:D40``, ``A2:D40``) --
    when the part is cut at :data:`MAX_PART_CHARS`, only up to where it stops.
    ``column_labels`` are the sheet's header labels of the columns served.
    """

    ref: str
    lines: tuple[PartLine, ...]
    truncated: bool
    column_labels: tuple[tuple[str, str], ...] = ()

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


_DASH: Final = "\\s*[-\\u2013]\\s*"
_PAGES: Final = re.compile(
    rf"^(?:p\.?|pp\.?|pages?|str\.?|strany?|strana)\s*(\d+)(?:{_DASH}(\d+))?$", re.I
)
_ROWS: Final = re.compile(rf"^(?:rows?|řádky?|řádek)\s*(\d+)(?:{_DASH}(\d+))?$", re.I)
_RANGE: Final = re.compile(r"^\$?([A-Za-z]{1,3})\$?(\d+)(?::\$?([A-Za-z]{1,3})\$?(\d+))?$")
_ROW_RANGE: Final = re.compile(r"^(\d+):(\d+)$")
_SHEET_REF: Final = re.compile(r"^(?:'((?:[^']|'')+)'|([^!']+))!(.+)$")


def _bounds(first: str, last: str | None) -> tuple[int, int]:
    low, high = int(first), int(last) if last is not None else int(first)
    if low < 1 or high < low:
        raise PartRefused(f"{low}-{high} is not a range", reason="part_invalid")
    return low, high


def _pdf_part(snapshot: SourceSnapshot, layout: DocumentLayout, spec: str) -> DocumentPart:
    match = _PAGES.match(spec)
    if match is None:
        raise PartRefused(
            f"{spec!r} names no pages (say 'p. 3' or 'p. 3-5')", reason="part_invalid"
        )
    low, high = _bounds(match[1], match[2])
    if layout.page_count is None or low > layout.page_count:
        raise PartRefused(
            f"the document has {layout.page_count or 0} pages", reason="part_out_of_range"
        )
    high = min(high, layout.page_count)
    lines: list[PartLine] = []
    used = 0
    served = low
    truncated = False
    last = high
    for page in layout.pages:
        if not low <= page.page <= high:
            continue
        room = MAX_PART_CHARS - used
        text = snapshot.text[page.start : page.end]
        if len(text) > room:
            truncated = True
            if lines:
                last = served
            else:
                lines.append(PartLine(label=f"p. {page.page}", text=text[:room]))
                last = page.page
            break
        lines.append(PartLine(label=f"p. {page.page}", text=text))
        used += len(text)
        served = page.page
    # A page with no text (or past the snapshot's cut) is served as nothing.
    ref = f"p. {low}" if last <= low else f"p. {low}-{last}"
    return DocumentPart(ref=ref, lines=tuple(lines), truncated=truncated)


def _grid_part(
    snapshot: SourceSnapshot,
    kind: str,
    sheet: DocumentSheet,
    rows: tuple[int, int] | None,
    columns: tuple[int, int] | None,
) -> DocumentPart:
    by_row: dict[int, list[tuple[int, int, int]]] = {}
    for r, c, s, e in sheet.cells:
        if rows is not None and not rows[0] <= r <= rows[1]:
            continue
        if columns is not None and not columns[0] <= c <= columns[1]:
            continue
        by_row.setdefault(r, []).append((c, s, e))
    lines: list[PartLine] = []
    used = 0
    truncated = False
    for r in sorted(by_row):
        cells = by_row[r]
        # From the first cell's value to the last's: the separators between are the
        # snapshot's own, so the line is a substring of its text.
        text = snapshot.text[cells[0][1] : cells[-1][2]]
        if used + len(text) > MAX_PART_CHARS:
            truncated = True
            if not lines:
                lines.append(PartLine(label=str(r), text=text[:MAX_PART_CHARS]))
            break
        lines.append(PartLine(label=str(r), text=text))
        used += len(text)
    all_columns = sorted({c for _, c, *_ in sheet.cells}) or [1]
    all_rows = sorted({r for r, *_ in sheet.cells}) or [1]
    low_col, high_col = columns if columns else (all_columns[0], all_columns[-1])
    low_row, high_row = rows if rows else (all_rows[0], all_rows[-1])
    if truncated:
        high_row = int(lines[-1].label)
    address = f"{cell_address(low_row, low_col)}:{cell_address(high_row, high_col)}"
    ref = address if kind == "csv" else f"{sheet_reference(sheet.name)}!{address}"
    labels: tuple[tuple[str, str], ...] = ()
    if sheet.header_row is not None:
        labels = tuple(
            (column_letters(c), snapshot.text[s:e])
            for r, c, s, e in sheet.cells
            if r == sheet.header_row and low_col <= c <= high_col
        )
    return DocumentPart(ref=ref, lines=tuple(lines), truncated=truncated, column_labels=labels)


def _range(spec: str) -> tuple[tuple[int, int], tuple[int, int] | None]:
    """``B2:D10`` -> rows (2, 10), columns (2, 4); ``2:40`` and ``rows 2-40`` -> rows only."""
    if match := _ROWS.match(spec):
        return _bounds(match[1], match[2]), None
    if match := _ROW_RANGE.match(spec):
        return _bounds(match[1], match[2]), None
    if match := _RANGE.match(spec):
        first_col, first_row = _column_number(match[1]), int(match[2])
        last_col = _column_number(match[3]) if match[3] else first_col
        last_row = int(match[4]) if match[4] else first_row
        if first_row < 1 or last_row < first_row or last_col < first_col:
            raise PartRefused(f"{spec!r} is not a range", reason="part_invalid")
        return (first_row, last_row), (first_col, last_col)
    raise PartRefused(
        f"{spec!r} is not a range (say 'B2:D10', '2:40' or 'rows 2-40')", reason="part_invalid"
    )


def read_part(snapshot: SourceSnapshot, part: str) -> DocumentPart:
    """Serve ``part`` of a captured document: ``read``'s backend; nothing is fetched.

    A PDF takes pages: ``p. 3``, ``p. 3-5`` (``pages``, ``str.``, ``strany`` too).
    An XLSX takes a sheet (``List1``, ``'Kraje 2024'``), or a range of one
    (``List1!B2:D10``, ``List1!2:40``); a workbook of one sheet takes a bare
    range. A CSV takes a range (``B2:D10``, ``2:40``, ``rows 2-40``).
    """
    layout = _layout(snapshot)
    spec = part.strip()
    if not spec:
        raise PartRefused("an empty part", reason="part_invalid")
    if layout.kind == "pdf":
        return _pdf_part(snapshot, layout, spec)
    if layout.kind == "csv":
        rows, columns = _range(spec)
        return _grid_part(snapshot, "csv", layout.sheets[0], rows, columns)
    names = {s.name: s for s in layout.sheets}
    bare = spec[1:-1].replace("''", "'") if spec.startswith("'") and spec.endswith("'") else spec
    if bare in names:
        return _grid_part(snapshot, "xlsx", names[bare], None, None)
    if match := _SHEET_REF.match(spec):
        name = match[1].replace("''", "'") if match[1] is not None else match[2].strip()
        sheet = names.get(name)
        if sheet is None:
            raise PartRefused(f"the workbook has no sheet {name!r}", reason="part_unknown_sheet")
        rows, columns = _range(match[3].strip())
        return _grid_part(snapshot, "xlsx", sheet, rows, columns)
    if len(layout.sheets) == 1:
        try:
            rows, columns = _range(spec)
        except PartRefused:
            pass
        else:
            return _grid_part(snapshot, "xlsx", layout.sheets[0], rows, columns)
    raise PartRefused(f"the workbook has no sheet {spec!r}", reason="part_unknown_sheet")
