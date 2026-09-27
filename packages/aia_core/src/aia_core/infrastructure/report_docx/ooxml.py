"""Small WordprocessingML helpers python-docx does not provide.

Fields (TOC, PAGE, STYLEREF, SEQ, PAGEREF), bookmarks, internal hyperlinks and
the schema-ordered insertion Word insists on. Everything here writes plain
elements; nothing decides content.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from lxml import etree

W_NS: Final = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def el(tag: str, **attrs: str) -> etree._Element:
    """``el("w:jc", val="right")`` → ``<w:jc w:val="right"/>``."""
    e = OxmlElement(tag)
    for name, value in attrs.items():
        e.set(qn(f"w:{name}"), value)
    return e


def insert_in_order(parent: etree._Element, child: etree._Element, later: Iterable[str]) -> None:
    """Insert ``child`` before the first existing sibling whose tag is in ``later``.

    Word refuses a document whose property children are out of schema order.
    """
    tags = {qn(t) if ":" in t else qn(f"w:{t}") for t in later}
    for i, existing in enumerate(parent):
        if existing.tag in tags:
            parent.insert(i, child)
            return
    parent.append(child)


def _run(paragraph: Paragraph, style: str | None = None) -> etree._Element:
    r = paragraph.add_run(style=style)._r
    return r


def add_field(
    paragraph: Paragraph, instruction: str, cached: str, *, style: str | None = None
) -> None:
    """A complex field with a cached result, so it reads correctly before an update.

    Word recomputes the result when fields update; a reader that never updates
    fields (a previewer, a converter) shows ``cached``.
    """
    begin = _run(paragraph, style)
    begin.append(el("w:fldChar", fldCharType="begin"))
    instr = _run(paragraph, style)
    t = OxmlElement("w:instrText")
    t.set(qn("xml:space"), "preserve")
    t.text = f" {instruction} "
    instr.append(t)
    sep = _run(paragraph, style)
    sep.append(el("w:fldChar", fldCharType="separate"))
    paragraph.add_run(cached, style=style)
    end = _run(paragraph, style)
    end.append(el("w:fldChar", fldCharType="end"))


def begin_field(paragraph: Paragraph, instruction: str) -> None:
    """Open a field whose result spans the following paragraphs (the TOC)."""
    begin = _run(paragraph)
    begin.append(el("w:fldChar", fldCharType="begin"))
    instr = _run(paragraph)
    t = OxmlElement("w:instrText")
    t.set(qn("xml:space"), "preserve")
    t.text = f" {instruction} "
    instr.append(t)
    sep = _run(paragraph)
    sep.append(el("w:fldChar", fldCharType="separate"))


def end_field(paragraph: Paragraph) -> None:
    end = _run(paragraph)
    end.append(el("w:fldChar", fldCharType="end"))


class Bookmarks:
    """Allocates bookmark ids; names are the report's own ids, made Word-safe."""

    def __init__(self) -> None:
        self._next = 0

    @staticmethod
    def name(ident: str) -> str:
        # Word bookmark names: letters, digits, underscore; start with a letter; <= 40.
        safe = "".join(ch if ch.isalnum() else "_" for ch in ident)
        return ("r_" + safe)[:40]

    def wrap(self, paragraph: Paragraph, ident: str) -> str:
        """Bookmark the whole paragraph; return the bookmark name."""
        name = self.name(ident)
        bid = str(self._next)
        self._next += 1
        p: etree._Element = paragraph._p
        start = el("w:bookmarkStart", id=bid, name=name)
        end = el("w:bookmarkEnd", id=bid)
        ppr = p.find(qn("w:pPr"))
        p.insert(0 if ppr is None else 1, start)
        p.append(end)
        return name


def add_internal_link(paragraph: Paragraph, text: str, bookmark: str, *, style: str | None) -> None:
    """A hyperlink to a bookmark inside the document ("viz graf 3")."""
    link = OxmlElement("w:hyperlink")
    link.set(qn("w:anchor"), bookmark)
    link.set(qn("w:history"), "1")
    run = OxmlElement("w:r")
    if style:
        rpr = OxmlElement("w:rPr")
        rpr.append(el("w:rStyle", val=style))
        run.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    run.append(t)
    link.append(run)
    p: etree._Element = paragraph._p
    p.append(link)


def add_tab(paragraph: Paragraph, style: str | None = None) -> None:
    r = _run(paragraph, style)
    r.append(OxmlElement("w:tab"))
