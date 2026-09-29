"""Reading a questionnaire file, and writing the template it is filled in from (ADR 0018).

:func:`import_questionnaire` is the unit's ``import_questionnaire_payload`` up to the
rows -- the file name, the format by extension, ``utf-8-sig`` CSV through ``csv.reader``,
and the unit's own dependency-free XLSX reader ``_xlsx_rows`` (``ui_server.py:562-597``),
ported line for line -- and then :func:`aia_core.domain.questionnaire_import.import_rows`.

Two things differ, both at the edge. A file that cannot be read at all -- not UTF-8, not
a ZIP, a workbook missing a part -- is refused as ``unreadable`` in AIA's words, where the
unit answered with the Python exception's text. And a ZIP whose members declare more
than ``ZIP_MAX_UNCOMPRESSED`` bytes is not opened: the unit inflated whatever it got.

:func:`template_xlsx` writes the template AIA offers for download. 18.6.6 served a file
from its tree; AIA writes its own, with the same two sheets and example rows, so the
template is part of AIA, not a copy of the unit's bytes. It says one thing the unit's
did not: a tracked set is rated on 1-10 whatever its ``skala_min`` / ``skala_max``,
because normalization drops a tracked set's scale (``research_project.py:340-360``), in
18.6.6 and here -- the unit's note claimed otherwise.
"""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath
from typing import Final
from xml.sax.saxutils import escape

from ..domain.questionnaire_import import (
    ImportedQuestionnaire,
    QuestionnaireImportRejected,
    import_rows,
)

__all__ = [
    "TEMPLATE_FILENAME",
    "ZIP_MAX_UNCOMPRESSED",
    "import_questionnaire",
    "read_rows",
    "template_xlsx",
]

ZIP_MAX_UNCOMPRESSED: Final = 64 * 1024 * 1024
ZIP_MAX_MEMBERS: Final = 5000
TEMPLATE_FILENAME: Final = "AIA_dotaznik_sablona.xlsx"

_NS: Final = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_UNREADABLE_XLSX: Final = "Soubor se nepodařilo přečíst jako sešit XLSX."


def _xlsx_rows(raw: bytes) -> list[list[str]]:
    """``ui_server._xlsx_rows``: the DOTAZNIK sheet (else the first), every cell as text."""
    ns = _NS
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.findall(".//m:t", ns)))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        relmap = {x.attrib["Id"]: x.attrib["Target"] for x in rels}
        sheets = wb.find("m:sheets", ns)
        target = None
        for sh in list(sheets) if sheets is not None else []:
            rid = sh.attrib.get("{{{}}}id".format(ns["r"]))
            name = str(sh.attrib.get("name") or "")
            if target is None or name.strip().upper() == "DOTAZNIK":
                target = relmap.get(rid) if rid is not None else None
            if name.strip().upper() == "DOTAZNIK":
                break
        if not target:
            raise QuestionnaireImportRejected(
                "XLSX neobsahuje list DOTAZNIK ani čitelný první list.", reason="no_sheet"
            )
        target = str(target).replace("\\", "/").lstrip("/")
        while target.startswith("../"):
            target = target[3:]
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ET.fromstring(z.read(target))
        rows: list[list[str]] = []
        for row in root.findall(".//m:sheetData/m:row", ns):
            vals: dict[int, str] = {}
            maxc = -1
            for c in row.findall("m:c", ns):
                ref = c.attrib.get("r", "A1")
                letters = re.match(r"[A-Z]+", ref)
                if letters is None:
                    raise ValueError(f"not a cell reference: {ref}")
                ci = 0
                for ch in letters.group(0):
                    ci = ci * 26 + (ord(ch) - 64)
                ci -= 1
                maxc = max(maxc, ci)
                typ = c.attrib.get("t")
                val: str | None = ""
                if typ == "inlineStr":
                    val = "".join(t.text or "" for t in c.findall(".//m:t", ns))
                else:
                    v = c.find("m:v", ns)
                    rawv = v.text if v is not None else ""
                    if typ == "s" and str(rawv).isdigit():
                        val = shared[int(str(rawv))] if int(str(rawv)) < len(shared) else ""
                    elif typ == "b":
                        val = "TRUE" if rawv == "1" else "FALSE"
                    else:
                        val = rawv or ""
                vals[ci] = str(val).strip()
            if maxc >= 0:
                rows.append([vals.get(i, "") for i in range(maxc + 1)])
        return rows


def _zip_within_bounds(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
    except Exception:
        return True  # not a ZIP: the reader says so
    return len(members) <= ZIP_MAX_MEMBERS and (
        sum(m.file_size for m in members) <= ZIP_MAX_UNCOMPRESSED
    )


def read_rows(data: bytes, filename: str) -> list[list[str]]:
    """The file's rows as text, by its extension; the unit's formats only."""
    lower = filename.lower()
    if lower.endswith(".csv"):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise QuestionnaireImportRejected(
                "CSV není text v kódování UTF-8. Uložte ho jako CSV UTF-8.", reason="unreadable"
            ) from exc
        try:
            return list(csv.reader(io.StringIO(text)))
        except csv.Error as exc:
            raise QuestionnaireImportRejected(
                "Soubor se nepodařilo přečíst jako CSV.", reason="unreadable"
            ) from exc
    if lower.endswith(".xlsx"):
        if not _zip_within_bounds(data):
            raise QuestionnaireImportRejected(_UNREADABLE_XLSX, reason="unreadable")
        try:
            return _xlsx_rows(data)
        except QuestionnaireImportRejected:
            raise
        except Exception as exc:
            # Not a ZIP, a missing part, broken XML, an impossible cell: the unit
            # answered with the exception's own text; AIA says what it means.
            raise QuestionnaireImportRejected(_UNREADABLE_XLSX, reason="unreadable") from exc
    raise QuestionnaireImportRejected(
        "Podporovaný formát je .xlsx nebo .csv.", reason="unsupported_format"
    )


def import_questionnaire(data: bytes, filename: str) -> ImportedQuestionnaire:
    """A filled-in template, imported as the unit imported it."""
    if not data:
        raise QuestionnaireImportRejected("Nahrajte XLSX nebo CSV dotazník.", reason="no_file")
    name = PurePosixPath(str(filename or "dotaznik.xlsx")).name
    return import_rows(read_rows(data, name), filename=name)


# --------------------------------------------------------------------------- #
# The template
# --------------------------------------------------------------------------- #

Cell = str | int | bool | None

TEMPLATE_HEADER: Final[tuple[str, ...]] = (
    "id",
    "otazka",
    "typ",
    "moznosti",
    "skala_min",
    "skala_max",
    "blok",
    "sledovana_sada",
    "povolit_nevim",
    "poznamka",
)
#: The unit's three example rows (``NPC_QUESTIONNAIRE_TEMPLATE_v17_6_0.xlsx``, sheet DOTAZNIK).
TEMPLATE_EXAMPLES: Final[tuple[tuple[Cell, ...], ...]] = (
    (
        "Q1",
        "Jak pravděpodobné je, že byste produkt koupil/a?",
        "skala",
        None,
        1,
        10,
        "Nákupní záměr",
        None,
        False,
        "Příklad \u2013 nahraďte vlastní otázkou.",
    ),
    (
        "Q2",
        "Který z následujících důvodů je pro vás nejdůležitější?",
        "vyber",
        "Cena | Kvalita | Dostupnost | Značka",
        None,
        None,
        "Bariéry",
        None,
        True,
        "Možnosti oddělujte znakem |.",
    ),
    (
        "OBJ_MEDIA",
        "Jak relevantní je pro vás {object}?",
        "objektova_sada",
        "TV | Online video | Sociální sítě | Rádio",
        1,
        10,
        "Média",
        "Média",
        False,
        "U objektové sady uvádějte 4\u201315 srovnatelných položek.",
    ),
)
#: The guide (sheet NAVOD): the unit's, where it was true of the import.
TEMPLATE_GUIDE: Final[tuple[tuple[str, str], ...]] = (
    ("POLE", "JAK HO VYPLNIT"),
    ("id", "Unikátní krátké ID bez mezer, např. Q1, Q_PRICE, OBJ_MEDIA."),
    ("otazka", "Přesné znění otázky. U objektové sady použijte {object}."),
    ("typ", "vyber / multi / skala / otevrena / objektova_sada."),
    ("moznosti", "U vyber/multi odpovědi, u objektové sady objekty. Oddělte znakem |."),
    (
        "skala_min / skala_max",
        "Vyplňte u skály. Objektová sada se hodnotí na škále 1\u201310, ať je zde uvedeno cokoli.",
    ),
    ("blok", "Logický blok dotazníku, např. Screening, Produkt, Cena."),
    ("sledovana_sada", "Název tracked setu; jinak nechte prázdné."),
    ("povolit_nevim", "TRUE/FALSE."),
    ("poznamka", "Metodická poznámka pro import nebo AI."),
    ("Objektové sady", "Doporučeně 4\u201315 položek stejného typu a stejné škály."),
    ("AI workflow", "Soubor lze připravit i v jiné AI: předejte jí oba listy této šablony."),
    ("Import", "AIA validuje strukturu a načte ji do stejného editoru jako ruční/AI cestu."),
)

_XML: Final = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_MAIN: Final = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OFFICE_REL: Final = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE: Final = "http://schemas.openxmlformats.org/package/2006"
_SHEETML: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml"


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
    text = escape(value)
    return f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{text}</t></is></c>'


def _sheet(rows: list[tuple[Cell, ...]], widths: list[int]) -> str:
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


def template_xlsx() -> bytes:
    """AIA's questionnaire template: sheets DOTAZNIK and NAVOD. Deterministic bytes."""
    parts = {
        "[Content_Types].xml": (
            f'{_XML}<Types xmlns="{_PACKAGE}/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/xl/workbook.xml" ContentType="{_SHEETML}.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            f'ContentType="{_SHEETML}.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" '
            f'ContentType="{_SHEETML}.worksheet+xml"/>'
            f'<Override PartName="/xl/styles.xml" ContentType="{_SHEETML}.styles+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            f'{_XML}<Relationships xmlns="{_PACKAGE}/relationships">'
            f'<Relationship Id="rId1" Type="{_OFFICE_REL}/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            f'{_XML}<workbook xmlns="{_MAIN}" xmlns:r="{_OFFICE_REL}"><sheets>'
            '<sheet name="DOTAZNIK" sheetId="1" r:id="rId1"/>'
            '<sheet name="NAVOD" sheetId="2" r:id="rId2"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            f'{_XML}<Relationships xmlns="{_PACKAGE}/relationships">'
            f'<Relationship Id="rId1" Type="{_OFFICE_REL}/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId2" Type="{_OFFICE_REL}/worksheet" '
            'Target="worksheets/sheet2.xml"/>'
            f'<Relationship Id="rId3" Type="{_OFFICE_REL}/styles" Target="styles.xml"/>'
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
        "xl/worksheets/sheet1.xml": _sheet(
            [TEMPLATE_HEADER, *TEMPLATE_EXAMPLES], [12, 52, 16, 40, 10, 10, 18, 18, 14, 48]
        ),
        "xl/worksheets/sheet2.xml": _sheet(list(TEMPLATE_GUIDE), [24, 90]),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in parts.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, body.encode("utf-8"))
    return buf.getvalue()
