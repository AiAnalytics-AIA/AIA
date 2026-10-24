"""A report's per-question tables as rows to export (report-delivery RD12, D-41), pure.

The rows come from a stored report document (``document_model.document_payload``): its question
tables, the ones ``application/report_tables.question_tables`` composed (anchors
``tab-question-<n>``), and each number as the ledger prints it. Nothing is computed or
re-rounded: a cell is a ref the report admitted for its surface, printed as the report prints
it, so the export of the internal draft is internal and the export of the client report is the
client's. A row the report removed for want of support is not a number here either; the export
says how many each table left out, as the report does.

Every text cell is guarded against spreadsheet formulas: one that a spreadsheet would read as a
formula (``=``, ``+``, ``-``, ``@``, a tab or a carriage return first) is kept as text with a
leading apostrophe. Numbers print their minus as U+2212, so no number is touched.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any, Final

from aia_core.domain.fieldwork import MODELLED_DISCLOSURE
from aia_core.domain.report.copy import t

#: The header every export carries.
HEADER: Final = ("Otázka", "Ukazatel", "Hodnota", "95% interval", "Základ", "Evidence", "Původ")
#: Each column's width in an XLSX sheet.
WIDTHS: Final = (52, 36, 14, 22, 14, 18, 40)
_TABLE_ANCHOR: Final = "tab-question-"
_FORMULA_FIRST: Final = ("=", "+", "-", "@", "\t", "\r")


def _guard(text: str) -> str:
    return f"'{text}" if text.startswith(_FORMULA_FIRST) else text


def _grade(entry: Mapping[str, Any]) -> str:
    grade = str(entry.get("grade") or "unknown")
    return t(f"grade_{grade.replace('-', '_')}")


def question_rows(document: Mapping[str, Any]) -> list[tuple[str, ...]]:
    """Every per-question table of ``document`` as rows under :data:`HEADER`: one per printed
    number, and one per table that left numbers out, saying how many. Empty of rows (the header
    alone) when the document has no question table."""
    refs: Mapping[str, Mapping[str, Any]] = document["ledger"]["refs"]
    rows: list[tuple[str, ...]] = [HEADER]
    for section in document["sections"]:
        for block in section["blocks"]:
            if block["type"] != "table" or not str(block.get("anchor") or "").startswith(
                _TABLE_ANCHOR
            ):
                continue
            title = _guard(str(block["title"]))
            for row in block["rows"]:
                label = " ".join(str(c["text"]) for c in row["cells"] if c["type"] == "text")
                for cell in row["cells"]:
                    if cell["type"] != "number":
                        continue
                    entry = refs[cell["ref"]]
                    if entry["suppressed"]:  # pragma: no cover - the stored table drops them
                        continue
                    rows.append(
                        (
                            title,
                            _guard(label),
                            str(entry["value_text"]),
                            str(entry["interval_text"] or "") if cell.get("with_interval") else "",
                            str(entry["base_text"] or ""),
                            _grade(entry),
                            MODELLED_DISCLOSURE if entry.get("modelled_panel") else "",
                        )
                    )
            removed = int(block.get("suppressed_rows") or 0)
            if removed:
                rows.append(
                    (
                        title,
                        f"vynecháno pro nedostatečnou oporu: {removed}",
                        "",
                        "",
                        "",
                        "",
                        "",
                    )
                )
    return rows


def to_csv(rows: list[tuple[str, ...]]) -> bytes:
    """``rows`` as CSV for a Czech spreadsheet: UTF-8 with its mark, ``;`` between cells (the
    decimal mark is a comma), every cell quoted where it must be."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")
