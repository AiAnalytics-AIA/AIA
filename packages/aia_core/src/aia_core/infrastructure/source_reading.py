"""Read a client's source into segments with locators (lifecycle K2a).

:func:`read_source` turns one original's bytes into a
:class:`~aia_core.domain.client_sources.SourceReading`: every readable part with the
place it stands in the original, and an outcome that never claims more than happened.
It is a pure function of the bytes and the name, so where it runs (the API at upload
today, a worker later) changes no contract.

The libraries are the ``documents`` extra the brief's attachments already use (pypdf,
pdfplumber, python-docx), imported only when a file of their kind is read. A PDF is read
with :func:`document_text.read_pdf`, the Deep Research reader: its 400-page refusal, its
password and malformed-file refusals and its bounded table extraction. An Office file is
checked against :func:`document_text.check_zip_bounds` before anything in it is inflated.

A reader not in AIA yet reads as ``UNSUPPORTED`` (``reader_pending``), an image or a
video as ``UNREADABLE``: both are kept, and neither poses as read.
"""

from __future__ import annotations

import io
from typing import Final

from ..domain.attachments import extension_of
from ..domain.client_sources import (
    Locator,
    ReadingNote,
    ReadingOutcome,
    Segment,
    SourceFamily,
    SourceReading,
    family_of,
    reading_of_segments,
)
from ..domain.deep_research.documents import DocumentRefused
from .document_text import check_zip_bounds, read_pdf

__all__ = ["READERS", "read_source"]

#: The reader each readable format goes through, and its version. A new version is a
#: new name: a reading records which reader made it.
READERS: Final[dict[str, str]] = {
    ".pdf": "pdf/1",
    ".docx": "docx/1",
    ".txt": "text/1",
    ".md": "text/1",
}


def _cells(values: tuple[str, ...] | list[str]) -> str:
    return " | ".join(v.strip() for v in values)


def _pdf(data: bytes) -> tuple[list[Segment], list[ReadingNote]]:
    content = read_pdf(data)
    segments = [
        Segment(locator=Locator(page=number), text=text)
        for number, text in enumerate(content.pages, start=1)
    ]
    notes: list[ReadingNote] = []
    # A page without text is said only when others have it: a PDF with none at all is
    # a scan, and the reading says that once (``no_text``), not once a page.
    if any(text.strip() for text in content.pages):
        notes.extend(
            ReadingNote(code="page_without_text", at=Locator(page=number))
            for number, text in enumerate(content.pages, start=1)
            if not text.strip()
        )
    for index, table in enumerate(content.tables, start=1):
        segments.extend(
            Segment(
                locator=Locator(page=table.page, table=index, row=row.number),
                text=_cells(row.values),
            )
            for row in table.rows
        )
    if content.tables_truncated:
        notes.append(ReadingNote(code="tables_bound", count=len(content.tables)))
    return segments, notes


def _docx(data: bytes) -> tuple[list[Segment], list[ReadingNote]]:
    check_zip_bounds(data, "DOCX")
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise DocumentRefused(
            f"the DOCX cannot be read ({type(exc).__name__})", reason="document_malformed"
        ) from exc
    segments: list[Segment] = []
    paragraph = table = 0
    # The body in its own order: a paragraph, then a table, as a reader meets them.
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph += 1
            text = Paragraph(child, document).text
            segments.append(Segment(locator=Locator(paragraph=paragraph), text=text))
        elif tag == "tbl":
            table += 1
            for number, row in enumerate(Table(child, document).rows, start=1):
                segments.append(
                    Segment(
                        locator=Locator(table=table, row=number),
                        text=_cells([cell.text for cell in row.cells]),
                    )
                )
    return segments, []


def _text(data: bytes) -> tuple[list[Segment], list[ReadingNote]]:
    notes: list[ReadingNote] = []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("utf-8-sig", errors="replace")
        notes.append(ReadingNote(code="not_utf8"))
    # A paragraph is a run of lines; its locator is the line it starts on.
    segments: list[Segment] = []
    start: int | None = None
    lines: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if start is None:
                start = number
            lines.append(line)
        elif start is not None:
            segments.append(Segment(locator=Locator(line=start), text="\n".join(lines)))
            start, lines = None, []
    if start is not None:
        segments.append(Segment(locator=Locator(line=start), text="\n".join(lines)))
    return segments, notes


_READ = {".pdf": _pdf, ".docx": _docx, ".txt": _text, ".md": _text}


def read_source(data: bytes, filename: str) -> SourceReading:
    """What reading these bytes under this name produces; never raises on a bad file.

    A missing reader library is not a file AIA cannot read: the ``documents`` extra is
    part of the deployment, and its absence raises ``ImportError``.
    """
    suffix = extension_of(filename)
    family = family_of(filename)
    if family in (SourceFamily.IMAGE, SourceFamily.VIDEO):
        return SourceReading(outcome=ReadingOutcome.UNREADABLE, reason="not_text_media")
    read = _READ.get(suffix)
    if read is None:
        return SourceReading(outcome=ReadingOutcome.UNSUPPORTED, reason="reader_pending")
    try:
        segments, notes = read(data)
    except ImportError:
        raise
    except DocumentRefused as exc:
        return SourceReading(outcome=ReadingOutcome.REFUSED, reason=exc.reason)
    except Exception:  # a hostile or broken file is refused, never half-read
        return SourceReading(outcome=ReadingOutcome.REFUSED, reason="document_malformed")
    return reading_of_segments(READERS[suffix], segments, notes=notes)
