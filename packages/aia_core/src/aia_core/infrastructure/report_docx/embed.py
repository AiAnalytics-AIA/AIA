"""Embed the report fonts in a DOCX package (ECMA-376 Part 1, §17.8.1).

A report must look like the design system on a machine that has none of its fonts
installed, so the faces travel inside the file. Word embeds a TrueType font as an
*obfuscated* part: the first 32 bytes are XORed with a key (a GUID) recorded next
to the reference in ``fontTable.xml``. This is packaging, not protection — the
standard's own term — and the licences allow it (OFL, ``fsType = 0``).

Two properties the rest of the report relies on:

* **Deterministic.** Each face's key is derived from the file's own SHA-256, so
  the same document content always produces the same bytes. A report's content
  fingerprint depends on that.
* **Schema order.** Word, unlike LibreOffice, refuses a ``settings.xml`` whose
  children are out of the schema's order, so insertion follows it.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Final, Literal

from docx.document import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

FONT_DIR: Final = Path(__file__).parent / "fonts"

Slot = Literal["Regular", "Bold", "Italic", "BoldItalic"]

#: Word font name → the vendored file for each style slot. The names are the
#: fonts' own family names (``name`` table ID 1), which is how Word and
#: LibreOffice match an embedded face to the text that asks for it.
FACES: Final[dict[str, dict[Slot, str]]] = {
    "Source Serif 4": {
        "Regular": "SourceSerif4-Regular.ttf",
        "Bold": "SourceSerif4-Bold.ttf",
        "Italic": "SourceSerif4-It.ttf",
        "BoldItalic": "SourceSerif4-BoldIt.ttf",
    },
    "Source Serif 4 Semibold": {"Regular": "SourceSerif4-Semibold.ttf"},
    "Source Serif 4 Display Semibold": {"Regular": "SourceSerif4Display-Semibold.ttf"},
    "IBM Plex Sans": {
        "Regular": "IBMPlexSans-Regular.ttf",
        "Bold": "IBMPlexSans-Bold.ttf",
        "Italic": "IBMPlexSans-Italic.ttf",
        "BoldItalic": "IBMPlexSans-BoldItalic.ttf",
    },
    "IBM Plex Sans SmBld": {"Regular": "IBMPlexSans-SemiBold.ttf"},
    "IBM Plex Mono": {"Regular": "IBMPlexMono-Regular.ttf"},
}

#: ``w:family`` per face, for a reader that must substitute.
_GENERIC: Final[dict[str, str]] = {
    "Source Serif 4": "roman",
    "Source Serif 4 Semibold": "roman",
    "Source Serif 4 Display Semibold": "roman",
    "IBM Plex Sans": "swiss",
    "IBM Plex Sans SmBld": "swiss",
    "IBM Plex Mono": "modern",
}

OBFUSCATED_FONT: Final = "application/vnd.openxmlformats-officedocument.obfuscatedFont"
_FONT_REL: Final = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"
_KEY_NAMESPACE: Final = uuid.UUID("5d0e6f2e-6a5b-4c1e-9d0a-7a1a0c0f0a71")

# ``CT_Settings`` children that come after ``w:embedTrueTypeFonts`` in schema
# order (ECMA-376 Part 1, §17.15.1.78). The element is inserted before the first
# of these that is present.
_AFTER_EMBED_TRUETYPE: Final = (
    "embedSystemFonts",
    "saveSubsetFonts",
    "saveFormsData",
    "mirrorMargins",
    "alignBordersAndEdges",
    "bordersDoNotSurroundHeader",
    "bordersDoNotSurroundFooter",
    "gutterAtTop",
    "hideSpellingErrors",
    "hideGrammaticalErrors",
    "activeWritingStyle",
    "proofState",
    "formsDesign",
    "attachedTemplate",
    "linkStyles",
    "stylePaneFormatFilter",
    "stylePaneSortMethod",
    "documentType",
    "mailMerge",
    "revisionView",
    "trackRevisions",
    "doNotTrackMoves",
    "doNotTrackFormatting",
    "documentProtection",
    "autoFormatOverride",
    "styleLockTheme",
    "styleLockQFSet",
    "defaultTabStop",
)


def font_key(data: bytes) -> str:
    """The obfuscation key for one face: a GUID derived from its bytes."""
    digest = hashlib.sha256(data).hexdigest()
    return "{" + str(uuid.uuid5(_KEY_NAMESPACE, digest)).upper() + "}"


def obfuscate(data: bytes, key: str) -> bytes:
    """XOR the first 32 bytes with the key, per §17.8.1. Its own inverse.

    The key's 16 bytes are taken from the GUID's hex digits read right to left,
    which is what the standard's "reverse order" means for the string form.
    """
    raw = bytes.fromhex(key.strip("{}").replace("-", ""))[::-1]
    if len(raw) != 16:
        raise ValueError(f"not a GUID: {key!r}")
    out = bytearray(data)
    for i in range(min(32, len(out))):
        out[i] ^= raw[i % 16]
    return bytes(out)


def _insert_in_order(parent: etree._Element, child: etree._Element, later: Iterable[str]) -> None:
    """Insert ``child`` before the first existing sibling named in ``later``."""
    tags = {qn(f"w:{name}") for name in later}
    for i, existing in enumerate(parent):
        if existing.tag in tags:
            parent.insert(i, child)
            return
    parent.append(child)


def _font_table_part(document: Document) -> Part:
    for rel in document.part.rels.values():
        if rel.reltype == RT.FONT_TABLE:
            part: Part = rel.target_part
            return part
    raise ValueError("the document has no font table part")


def embed_fonts(document: Document, names: Iterable[str]) -> list[str]:
    """Embed every face of each named font; return the part names written.

    A name that is not vendored is an error, not a silent fallback: a report that
    asks for a face it cannot carry would render in a substitute on the client's
    machine.
    """
    wanted = list(dict.fromkeys(names))
    unknown = [n for n in wanted if n not in FACES]
    if unknown:
        raise KeyError(f"no vendored face for: {', '.join(unknown)}")

    table_part = _font_table_part(document)
    table = etree.fromstring(table_part.blob)
    package = document.part.package
    written: list[str] = []
    index = sum(1 for _ in package.iter_parts())

    for name in wanted:
        font = next((f for f in table.iterfind(qn("w:font")) if f.get(qn("w:name")) == name), None)
        if font is None:
            font = etree.SubElement(table, qn("w:font"), {qn("w:name"): name})
            etree.SubElement(font, qn("w:family"), {qn("w:val"): _GENERIC[name]})
            pitch = "fixed" if name == "IBM Plex Mono" else "variable"
            etree.SubElement(font, qn("w:pitch"), {qn("w:val"): pitch})
        for slot, filename in FACES[name].items():
            data = (FONT_DIR / filename).read_bytes()
            key = font_key(data)
            index += 1
            partname = PackURI(f"/word/fonts/font{index}.odttf")
            part = Part(partname, OBFUSCATED_FONT, obfuscate(data, key), package)
            rid = table_part.relate_to(part, _FONT_REL)
            etree.SubElement(font, qn(f"w:embed{slot}"), {qn("r:id"): rid, qn("w:fontKey"): key})
            written.append(str(partname))

    # The font table has no python-docx part class, so it is a plain Part whose
    # blob is the serialised XML; replace it wholesale (there is no public setter).
    table_part._blob = etree.tostring(
        table, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    settings = document.settings.element
    if settings.find(qn("w:embedTrueTypeFonts")) is None:
        _insert_in_order(settings, OxmlElement("w:embedTrueTypeFonts"), _AFTER_EMBED_TRUETYPE)
    return written
