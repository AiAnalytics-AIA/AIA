"""Footnotes. python-docx has no footnotes part, so the report adds its own.

A footnotes part holds the two separator notes Word requires (ids -1 and 0) and
then one note per reference. ``settings.xml`` names the separators in
``w:footnotePr``, before ``w:compat`` (schema order).
"""

from __future__ import annotations

from typing import Final

from docx.document import Document
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml.ns import nsdecls, qn
from docx.text.paragraph import Paragraph
from lxml import etree

from aia_core.infrastructure.report_docx.ooxml import el, insert_in_order
from aia_core.infrastructure.report_docx.styles import S

FOOTNOTES_CT: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
FOOTNOTES_REL: Final = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"
)

_SETTINGS_AFTER_FOOTNOTEPR: Final = (
    "endnotePr",
    "compat",
    "docVars",
    "rsids",
    "m:mathPr",
    "attachedSchema",
    "themeFontLang",
    "clrSchemeMapping",
    "doNotIncludeSubdocsInStats",
    "doNotAutoCompressPictures",
    "forceUpgrade",
    "captions",
    "readModeInkLockDown",
    "smartTagType",
    "sl:schemaLibrary",
    "shapeDefaults",
    "doNotEmbedSmartTags",
    "decimalSymbol",
    "listSeparator",
)


def _separator(kind: str, note_id: str, tag: str) -> str:
    return (
        f'<w:footnote w:type="{kind}" w:id="{note_id}"><w:p><w:pPr>'
        f'<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
        f"<w:r><w:{tag}/></w:r></w:p></w:footnote>"
    )


class Footnotes:
    """Adds footnotes to one document; the part is written on :meth:`finish`."""

    def __init__(self, document: Document) -> None:
        self._document = document
        self._root: etree._Element = etree.fromstring(
            f"<w:footnotes {nsdecls('w', 'r')}>"
            + _separator("separator", "-1", "separator")
            + _separator("continuationSeparator", "0", "continuationSeparator")
            + "</w:footnotes>"
        )
        self._next = 1

    def add(self, paragraph: Paragraph, text: str) -> int:
        """Place a reference in ``paragraph`` and write the note's text."""
        note_id = self._next
        self._next += 1
        ref_run: etree._Element = paragraph.add_run(style=S.FOOTNOTE_REF)._r
        ref_run.append(el("w:footnoteReference", id=str(note_id)))

        note = el("w:footnote", id=str(note_id))
        p = el("w:p")
        ppr = el("w:pPr")
        ppr.append(el("w:pStyle", val=_style_id(self._document, S.FOOTNOTE)))
        p.append(ppr)
        mark = el("w:r")
        mark_rpr = el("w:rPr")
        mark_rpr.append(el("w:rStyle", val=_style_id(self._document, S.FOOTNOTE_REF)))
        mark.append(mark_rpr)
        mark.append(el("w:footnoteRef"))
        p.append(mark)
        body = el("w:r")
        t = el("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = f"\u00a0{text}"
        body.append(t)
        p.append(body)
        note.append(p)
        self._root.append(note)
        return note_id

    @property
    def count(self) -> int:
        return self._next - 1

    def finish(self) -> None:
        """Attach the part (only if any note was written) and declare the separators."""
        if self.count == 0:
            return
        blob = etree.tostring(self._root, xml_declaration=True, encoding="UTF-8", standalone=True)
        part = Part(PackURI("/word/footnotes.xml"), FOOTNOTES_CT, blob, self._document.part.package)
        self._document.part.relate_to(part, FOOTNOTES_REL)
        settings = self._document.settings.element
        if settings.find(qn("w:footnotePr")) is None:
            pr = el("w:footnotePr")
            pr.append(el("w:footnote", id="-1"))
            pr.append(el("w:footnote", id="0"))
            insert_in_order(settings, pr, _SETTINGS_AFTER_FOOTNOTEPR)


def _style_id(document: Document, name: str) -> str:
    style_id: str = document.styles[name].style_id
    return style_id
