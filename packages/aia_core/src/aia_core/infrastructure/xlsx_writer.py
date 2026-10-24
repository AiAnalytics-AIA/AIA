"""A workbook of text and whole-number sheets, written with the standard library.

AIA's own XLSX files (the questionnaire template, report-delivery RD12's question tables) are
small sheets of strings and integers. This writes them without a spreadsheet library: inline
strings, a bold header row, frozen under it, set column widths, and fixed timestamps, so the same
rows give the same bytes. A string is always written as text (``inlineStr``), never as a formula,
whatever it starts with; a character XML 1.0 cannot carry is left out of it.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Sequence
from typing import Final
from xml.sax.saxutils import escape

Cell = str | int | bool | None
#: One sheet: its name, its rows (the first is the header) and each column's width.
Sheet = tuple[str, Sequence[tuple[Cell, ...]], Sequence[int]]

_XML: Final = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_MAIN: Final = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OFFICE_REL: Final = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE: Final = "http://schemas.openxmlformats.org/package/2006"
_SHEETML: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml"
#: What the workbook's files are dated: a fixed time, so the bytes depend on the rows alone.
_DATED: Final = (2026, 1, 1, 0, 0, 0)

MEDIA_TYPE: Final = f"{_SHEETML}.sheet"
#: What XML 1.0 cannot carry in text: a cell holding one would be a workbook no reader opens.
_NOT_XML: Final = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _column(i: int) -> str:
    name = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        name = chr(65 + rem) + name
    return name


def _cell(ref: str, value: Cell, *, bold: bool) -> str:
    style = ' s="1"' if bold else ""
    if value is None:
        return ""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"{style}><v>{int(value)}</v></c>'
    if isinstance(value, int):
        return f'<c r="{ref}"{style}><v>{value}</v></c>'
    text = escape(_NOT_XML.sub("", value))
    return f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{text}</t></is></c>'


def _sheet(rows: Sequence[tuple[Cell, ...]], widths: Sequence[int]) -> str:
    last = f"{_column(max(len(r) for r in rows) - 1)}{len(rows)}"
    cols = "".join(
        f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>'
        for i, w in enumerate(widths)
    )
    body = "".join(
        f'<row r="{n}">'
        + "".join(_cell(f"{_column(i)}{n}", v, bold=n == 1) for i, v in enumerate(row))
        + "</row>"
        for n, row in enumerate(rows, start=1)
    )
    return (
        f'{_XML}<worksheet xmlns="{_MAIN}"><dimension ref="A1:{last}"/>'
        f'<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        f'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f"<cols>{cols}</cols><sheetData>{body}</sheetData></worksheet>"
    )


def workbook(sheets: Sequence[Sheet]) -> bytes:
    """``sheets`` as one workbook, in order. Deterministic bytes."""
    numbered = list(enumerate(sheets, start=1))
    parts = {
        "[Content_Types].xml": (
            f'{_XML}<Types xmlns="{_PACKAGE}/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/xl/workbook.xml" ContentType="{_SHEETML}.sheet.main+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{n}.xml" '
                f'ContentType="{_SHEETML}.worksheet+xml"/>'
                for n, _ in numbered
            )
            + f'<Override PartName="/xl/styles.xml" ContentType="{_SHEETML}.styles+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            f'{_XML}<Relationships xmlns="{_PACKAGE}/relationships">'
            f'<Relationship Id="rId1" Type="{_OFFICE_REL}/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            f'{_XML}<workbook xmlns="{_MAIN}" xmlns:r="{_OFFICE_REL}"><sheets>'
            + "".join(
                f'<sheet name="{escape(name)}" sheetId="{n}" r:id="rId{n}"/>'
                for n, (name, _rows, _widths) in numbered
            )
            + "</sheets></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            f'{_XML}<Relationships xmlns="{_PACKAGE}/relationships">'
            + "".join(
                f'<Relationship Id="rId{n}" Type="{_OFFICE_REL}/worksheet" '
                f'Target="worksheets/sheet{n}.xml"/>'
                for n, _ in numbered
            )
            + f'<Relationship Id="rId{len(numbered) + 1}" Type="{_OFFICE_REL}/styles" '
            'Target="styles.xml"/>'
            "</Relationships>"
        ),
        "xl/styles.xml": (
            f'{_XML}<styleSheet xmlns="{_MAIN}">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
            '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border>'
            "</borders>"
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
            "</cellStyleXfs>"
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
            "</cellXfs>"
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            "</styleSheet>"
        ),
        **{
            f"xl/worksheets/sheet{n}.xml": _sheet(rows, widths)
            for n, (_name, rows, widths) in numbered
        },
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in parts.items():
            info = zipfile.ZipInfo(name, date_time=_DATED)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, body.encode("utf-8"))
    return buf.getvalue()
