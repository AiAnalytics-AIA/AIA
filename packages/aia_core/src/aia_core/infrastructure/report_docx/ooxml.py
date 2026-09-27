"""Small WordprocessingML helpers python-docx does not provide.

Fields (TOC, PAGE, STYLEREF, SEQ, PAGEREF), bookmarks, internal hyperlinks and
the schema-ordered insertion Word insists on. Everything here writes plain
elements; nothing decides content.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Final

from docx.opc.constants import RELATIONSHIP_TYPE as RT
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


#: ``CT_Settings`` children in schema order (ECMA-376 Part 1, §17.15.1.78), by
#: local name. Word refuses a ``settings.xml`` whose children are out of it.
SETTINGS_ORDER: Final = (
    "writeProtection", "view", "zoom", "removePersonalInformation", "removeDateAndTime",
    "doNotDisplayPageBoundaries", "displayBackgroundShape", "printPostScriptOverText",
    "printFractionalCharacterWidth", "printFormsData", "embedTrueTypeFonts",
    "embedSystemFonts", "saveSubsetFonts", "saveFormsData", "mirrorMargins",
    "alignBordersAndEdges", "bordersDoNotSurroundHeader", "bordersDoNotSurroundFooter",
    "gutterAtTop", "hideSpellingErrors", "hideGrammaticalErrors", "activeWritingStyle",
    "proofState", "formsDesign", "attachedTemplate", "linkStyles",
    "stylePaneFormatFilter", "stylePaneSortMethod", "documentType", "mailMerge",
    "revisionView", "trackRevisions", "doNotTrackMoves", "doNotTrackFormatting",
    "documentProtection", "autoFormatOverride", "styleLockTheme", "styleLockQFSet",
    "defaultTabStop", "autoHyphenation", "consecutiveHyphenLimit", "hyphenationZone",
    "doNotHyphenateCaps", "showEnvelope", "summaryLength", "clickAndTypeStyle",
    "defaultTableStyle", "evenAndOddHeaders", "bookFoldRevPrinting", "bookFoldPrinting",
    "bookFoldPrintingSheets", "drawingGridHorizontalSpacing", "drawingGridVerticalSpacing",
    "displayHorizontalDrawingGridEvery", "displayVerticalDrawingGridEvery",
    "doNotUseMarginsForDrawingGridOrigin", "drawingGridHorizontalOrigin",
    "drawingGridVerticalOrigin", "doNotShadeFormData", "noPunctuationKerning",
    "characterSpacingControl", "printTwoOnOne", "strictFirstAndLastChars",
    "noLineBreaksAfter", "noLineBreaksBefore", "savePreviewPicture",
    "doNotValidateAgainstSchema", "saveInvalidXml", "ignoreMixedContent",
    "alwaysShowPlaceholderText", "doNotDemarcateInvalidXml", "saveXmlDataOnly",
    "useXSLTWhenSaving", "saveThroughXslt", "showXMLTags", "alwaysMergeEmptyNamespace",
    "updateFields", "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars",
    "rsids", "mathPr", "attachedSchema", "themeFontLang", "clrSchemeMapping",
    "doNotIncludeSubdocsInStats", "doNotAutoCompressPictures", "forceUpgrade", "captions",
    "readModeInkLockDown", "smartTagType", "schemaLibrary", "shapeDefaults",
    "doNotEmbedSmartTags", "decimalSymbol", "listSeparator",
)  # fmt: skip

#: ``CT_SectPr`` children in schema order (§17.6.17).
SECTPR_ORDER: Final = (
    "headerReference", "footerReference", "footnotePr", "endnotePr", "type", "pgSz",
    "pgMar", "paperSrc", "pgBorders", "lnNumType", "pgNumType", "cols", "formProt",
    "vAlign", "noEndnote", "titlePg", "textDirection", "bidi", "rtlGutter", "docGrid",
    "printerSettings", "sectPrChange",
)  # fmt: skip


def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def insert_ordered(parent: etree._Element, child: etree._Element, order: tuple[str, ...]) -> None:
    """Insert ``child`` where ``order`` (local names, schema order) puts it.

    An existing child of the same name is replaced, so the call is idempotent.
    """
    name = _local(child.tag)
    rank = order.index(name)
    for existing in list(parent):
        if _local(existing.tag) == name:
            parent.remove(existing)
    for i, existing in enumerate(parent):
        local = _local(existing.tag)
        if local in order and order.index(local) > rank:
            parent.insert(i, child)
            return
    parent.append(child)


def in_schema_order(parent: etree._Element, order: tuple[str, ...]) -> bool:
    """Whether ``parent``'s children that ``order`` names appear in its order."""
    ranks = [order.index(_local(c.tag)) for c in parent if _local(c.tag) in order]
    return ranks == sorted(ranks)


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


def _link_run(text: str, style: str | None) -> etree._Element:
    run = OxmlElement("w:r")
    if style:
        rpr = OxmlElement("w:rPr")
        rpr.append(el("w:rStyle", val=style))
        run.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    run.append(t)
    return run


def add_external_link(paragraph: Paragraph, text: str, url: str, *, style: str | None) -> None:
    """A hyperlink to a URL, through an external relationship of the part."""
    rid = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rid)
    link.set(qn("w:history"), "1")
    link.append(_link_run(text, style))
    p: etree._Element = paragraph._p
    p.append(link)


def _field_runs(instruction: str, cached: str) -> list[etree._Element]:
    """The runs of a complex field with a cached result, as bare elements."""
    begin = OxmlElement("w:r")
    begin.append(el("w:fldChar", fldCharType="begin"))
    instr = OxmlElement("w:r")
    t = OxmlElement("w:instrText")
    t.set(qn("xml:space"), "preserve")
    t.text = f" {instruction} "
    instr.append(t)
    sep = OxmlElement("w:r")
    sep.append(el("w:fldChar", fldCharType="separate"))
    result = _link_run(cached, None)
    end = OxmlElement("w:r")
    end.append(el("w:fldChar", fldCharType="end"))
    return [begin, instr, sep, result, end]


def add_toc_entry(paragraph: Paragraph, text: str, bookmark: str, cached_page: str) -> None:
    """One entry of a TOC field's cached result, shaped as Word writes its own.

    A hyperlink to the heading's bookmark holding the text, a tab (the style's
    right tab with its leader) and a ``PAGEREF`` field, so a reader that
    computes fields finds the page and a reader that does not still links.
    """
    link = OxmlElement("w:hyperlink")
    link.set(qn("w:anchor"), bookmark)
    link.set(qn("w:history"), "1")
    link.append(_link_run(text, None))
    tab = OxmlElement("w:r")
    tab.append(OxmlElement("w:tab"))
    link.append(tab)
    for run in _field_runs(f"PAGEREF {bookmark} \\h", cached_page):
        link.append(run)
    p: etree._Element = paragraph._p
    p.append(link)


def add_tab(paragraph: Paragraph, style: str | None = None) -> None:
    r = _run(paragraph, style)
    r.append(OxmlElement("w:tab"))


def full_width(table: Any) -> None:
    """The table spans the text width (``tblW`` 100 %), whatever the page."""
    tbl_pr: etree._Element = table._tbl.tblPr
    for existing in tbl_pr.findall(qn("w:tblW")):
        tbl_pr.remove(existing)
    insert_in_order(
        tbl_pr,
        el("w:tblW", w="5000", type="pct"),
        ("jc", "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar",
         "tblLook", "tblCaption", "tblDescription"),
    )  # fmt: skip


def keep_row(row: Any) -> None:
    """Never split this row across pages (a value and its interval stay together)."""
    tr_pr: etree._Element = row._tr.get_or_add_trPr()
    if tr_pr.find(qn("w:cantSplit")) is None:
        tr_pr.append(el("w:cantSplit"))


def header_row(row: Any) -> None:
    """Repeat this row at the top of every page the table runs onto; never split it."""
    tr_pr: etree._Element = row._tr.get_or_add_trPr()
    tr_pr.append(el("w:cantSplit"))
    tr_pr.append(el("w:tblHeader"))
