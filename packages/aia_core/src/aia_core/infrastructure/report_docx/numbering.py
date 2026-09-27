"""List numbering: bullets, and numbered lists that restart per list.

Word numbers a list through ``numbering.xml``: an abstract definition (the
levels' look) and a numbering instance per list. Bullets share one instance; each
ordered list gets its own, so the second list in a chapter starts at 1 again.
"""

from __future__ import annotations

from typing import Final

from docx.document import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from lxml import etree

from aia_core.infrastructure.report_docx.ooxml import el, insert_in_order
from aia_core.infrastructure.report_docx.styles import PPR_AFTER_NUMPR

_BULLET_ABSTRACT: Final = 9001
_DECIMAL_ABSTRACT: Final = 9002
_BULLETS: Final = ("\u2022", "\u2013")  # bullet, en dash
_INDENT_MM: Final = ((6.0, 4.0), (12.0, 4.0))


def _twips(mm: float) -> str:
    return str(round(mm / 25.4 * 1440))


def _level(ilvl: int, fmt: str, text: str, font: str | None) -> etree._Element:
    lvl = el("w:lvl", ilvl=str(ilvl))
    lvl.append(el("w:start", val="1"))
    lvl.append(el("w:numFmt", val=fmt))
    lvl.append(el("w:lvlText", val=text))
    lvl.append(el("w:lvlJc", val="left"))
    ppr = el("w:pPr")
    left, hanging = _INDENT_MM[ilvl]
    ppr.append(el("w:ind", left=_twips(left), hanging=_twips(hanging)))
    lvl.append(ppr)
    if font:
        rpr = el("w:rPr")
        rpr.append(el("w:rFonts", ascii=font, hAnsi=font, cs=font))
        lvl.append(rpr)
    return lvl


class Numbering:
    """The report's numbering definitions, installed once per document."""

    def __init__(self, document: Document) -> None:
        self._root: etree._Element = document.part.numbering_part.element
        self._next_num = 9000
        bullet = el("w:abstractNum", abstractNumId=str(_BULLET_ABSTRACT))
        bullet.append(el("w:multiLevelType", val="hybridMultilevel"))
        for i, glyph in enumerate(_BULLETS):
            bullet.append(_level(i, "bullet", glyph, "IBM Plex Sans"))
        decimal = el("w:abstractNum", abstractNumId=str(_DECIMAL_ABSTRACT))
        decimal.append(el("w:multiLevelType", val="hybridMultilevel"))
        decimal.append(_level(0, "decimal", "%1.", None))
        decimal.append(_level(1, "lowerLetter", "%2)", None))
        # abstractNum elements precede every num element (CT_Numbering order).
        insert_in_order(self._root, bullet, ["num", "numIdMacAtCleanup"])
        insert_in_order(self._root, decimal, ["num", "numIdMacAtCleanup"])
        self.bullets = self._instance(_BULLET_ABSTRACT)

    def _instance(self, abstract: int, restart: bool = False) -> int:
        self._next_num += 1
        num = el("w:num", numId=str(self._next_num))
        num.append(el("w:abstractNumId", val=str(abstract)))
        if restart:
            override = el("w:lvlOverride", ilvl="0")
            override.append(el("w:startOverride", val="1"))
            num.append(override)
        insert_in_order(self._root, num, ["numIdMacAtCleanup"])
        return self._next_num

    def new_ordered_list(self) -> int:
        return self._instance(_DECIMAL_ABSTRACT, restart=True)

    @staticmethod
    def apply(paragraph: Paragraph, num_id: int, level: int) -> None:
        ppr = paragraph._p.get_or_add_pPr()
        for existing in ppr.findall(qn("w:numPr")):
            ppr.remove(existing)
        num_pr = el("w:numPr")
        num_pr.append(el("w:ilvl", val=str(level)))
        num_pr.append(el("w:numId", val=str(num_id)))
        insert_in_order(ppr, num_pr, PPR_AFTER_NUMPR)
