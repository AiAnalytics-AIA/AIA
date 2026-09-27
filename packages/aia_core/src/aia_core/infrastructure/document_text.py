"""The text of a brief attachment, read as 18.6.6 read it (ADR 0018).

A port of the unit's ``data_library._extract_text`` (``data_library.py:146-169``) that
uses the libraries the unit used -- pypdf, python-docx and openpyxl, the ``documents``
extra, imported here only and only when a file of that kind is read -- so the text an
analysis reads of an attachment is the text 18.6.6 read. ``test_document_text.py``
compares it with the unit's own function on fictional documents
(``tests/fixtures/attachment_text``, captured by ``tools/attachment_text_capture.py``).

The unit's contract is kept: a file AIA cannot read yields ``""`` (the unit's failure
marker, which its attachment code turned into ``""``), so its record says
``text_extracted = False`` and never poses as read. That includes the unit's own
limits -- the first 80 PDF pages, the top-level paragraphs of a Word document (not its
tables), the first 12 sheets, 300 rows and 30 columns of a workbook, and no text from a
sheet that does not declare its size.

One thing is added. An Office file is a ZIP, and the unit decompressed whatever it was
given inside the request; here a ZIP whose members declare more than
``ZIP_MAX_UNCOMPRESSED`` bytes, or more than ``ZIP_MAX_MEMBERS`` members, is not
opened, and keeps no text. ``zipfile`` never inflates a member past its declared size,
so the declaration bounds the work.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from typing import Final

from ..domain.attachments import TEXT_MAX_CHARS, extension_of

__all__ = [
    "PDF_MAX_PAGES",
    "TEXT_SUFFIXES",
    "ZIP_MAX_MEMBERS",
    "ZIP_MAX_UNCOMPRESSED",
    "extract_text",
]

#: Read as UTF-8 text, undecodable bytes replaced (the unit's list).
TEXT_SUFFIXES: Final = frozenset({".txt", ".md", ".csv", ".json", ".tsv"})
PDF_MAX_PAGES: Final = 80
XLSX_MAX_SHEETS: Final = 12
XLSX_MAX_ROWS: Final = 300
XLSX_MAX_COLUMNS: Final = 30
ZIP_MAX_UNCOMPRESSED: Final = 200 * 1024 * 1024
ZIP_MAX_MEMBERS: Final = 5000
_ZIP_SUFFIXES: Final = frozenset({".docx", ".xlsx", ".xlsm"})


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages[:PDF_MAX_PAGES]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # the unit skips a page it cannot read
            continue
    return "\n".join(parts)


def _docx(data: bytes) -> str:
    from docx import Document

    return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)


def _xlsx(data: bytes) -> str:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        out: list[str] = []
        for sheet in workbook.worksheets[:XLSX_MAX_SHEETS]:
            out.append(f"### {sheet.title}")
            # A sheet that declares no size has max_row None; min() raises, and the
            # workbook keeps no text -- as in the unit.
            rows = sheet.iter_rows(
                min_row=1, max_row=min(sheet.max_row, XLSX_MAX_ROWS), values_only=True
            )
            for row in rows:
                out.append(" | ".join("" if v is None else str(v) for v in row[:XLSX_MAX_COLUMNS]))
        return "\n".join(out)
    finally:
        workbook.close()


_READERS: Final[dict[str, Callable[[bytes], str]]] = {
    ".pdf": _pdf,
    ".docx": _docx,
    ".xlsx": _xlsx,
    ".xlsm": _xlsx,
}


def _zip_within_bounds(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
    except Exception:  # not a ZIP at all: nothing to read
        return False
    return len(members) <= ZIP_MAX_MEMBERS and (
        sum(m.file_size for m in members) <= ZIP_MAX_UNCOMPRESSED
    )


def extract_text(data: bytes, filename: str) -> str:
    """The text of an attached file, at most ``TEXT_MAX_CHARS`` characters; ``""`` if none.

    The kind of file is its extension, as in the unit. A kind with no reader (an
    image, a video) and a file its reader cannot parse both yield ``""``. A missing
    reader library is not a file AIA cannot read: the ``documents`` extra is part of
    the deployment, and its absence raises.
    """
    suffix = extension_of(filename)
    if suffix in TEXT_SUFFIXES:
        return data.decode("utf-8", errors="replace")[:TEXT_MAX_CHARS]
    reader = _READERS.get(suffix)
    if reader is None:
        return ""
    if suffix in _ZIP_SUFFIXES and not _zip_within_bounds(data):
        return ""
    try:
        text = reader(data)
    except ImportError:
        raise
    except Exception:
        # A malformed or hostile document: kept, with no text (the unit's contract).
        return ""
    return text[:TEXT_MAX_CHARS]
