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

from ..domain.questionnaire_import import (
    ImportedQuestionnaire,
    QuestionnaireImportRejected,
    import_rows,
)
from .document_text import refuse_dtd
from .xlsx_writer import Cell, workbook

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
# A row is materialized up to its last named cell, so a cell reference alone decides
# its size: one <c r="ZZZZZZ1"/> is 321 million strings. Excel's last column is XFD,
# and a questionnaire is a few hundred rows of ten columns; past either bound the
# file is not one.
XLSX_MAX_COLUMN: Final = 16_383  # XFD, 0-based
XLSX_MAX_CELLS: Final = 1_000_000

_NS: Final = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_UNREADABLE_XLSX: Final = "Soubor se nepodařilo přečíst jako sešit XLSX."


def _xml(data: bytes) -> ET.Element:
    """One part, parsed; a part declaring a DTD is refused before its entities expand."""
    refuse_dtd(data)
    return ET.fromstring(data)


def _xlsx_rows(raw: bytes) -> list[list[str]]:
    """``ui_server._xlsx_rows``: the DOTAZNIK sheet (else the first), every cell as text."""
    ns = _NS
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = _xml(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.findall(".//m:t", ns)))
        wb = _xml(z.read("xl/workbook.xml"))
        rels = _xml(z.read("xl/_rels/workbook.xml.rels"))
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
        root = _xml(z.read(target))
        rows: list[list[str]] = []
        cells = 0
        for row in root.findall(".//m:sheetData/m:row", ns):
            vals: dict[int, str] = {}
            maxc = -1
            for c in row.findall("m:c", ns):
                ref = c.attrib.get("r", "A1")
                letters = re.match(r"[A-Z]+", ref)
                if letters is None:
                    raise ValueError(f"not a cell reference: {ref}")
                # XFD is three letters; a longer run is refused before it is counted,
                # since counting it is quadratic in its length.
                if len(letters.group(0)) > 3:
                    raise ValueError("a cell past the last column")
                ci = 0
                for ch in letters.group(0):
                    ci = ci * 26 + (ord(ch) - 64)
                ci -= 1
                if ci > XLSX_MAX_COLUMN:
                    raise ValueError(f"a cell past the last column: {ref}")
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
                cells += maxc + 1
                if cells > XLSX_MAX_CELLS:
                    raise ValueError("more cells than a questionnaire holds")
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


def template_xlsx() -> bytes:
    """AIA's questionnaire template: sheets DOTAZNIK and NAVOD. Deterministic bytes."""
    return workbook(
        [
            (
                "DOTAZNIK",
                [TEMPLATE_HEADER, *TEMPLATE_EXAMPLES],
                [12, 52, 16, 40, 10, 10, 18, 18, 14, 48],
            ),
            ("NAVOD", list(TEMPLATE_GUIDE), [24, 90]),
        ]
    )
