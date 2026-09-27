"""The report's Word style sheet, generated from the print register.

Every paragraph and run in a report has a named style, and every style here is
built from ``domain/report/print_tokens.py``, itself generated from
``tokens.json``. The renderer never sets a font, size or colour directly. That
makes "restyle the report" a token change, and makes a stray hand-formatted run
a lint failure (``test_report_docx_structure.py``).

Word recognises its built-in styles (headings, captions, TOC levels, footnotes,
header and footer) by their internal, lower-case names. The TOC and list-of-
figures fields, the navigation pane and screen readers rely on them, so those
styles keep the built-in names and are restyled rather than replaced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from docx.document import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from docx.styles.style import BaseStyle, CharacterStyle, ParagraphStyle
from lxml import etree

from aia_core.domain.report.print_tokens import COLORS, STYLES, PrintStyle
from aia_core.infrastructure.report_docx.ooxml import el, insert_in_order

# ---------------------------------------------------------------------- names


class S:
    """Style names the renderer uses. One place, so a rename cannot drift."""

    BODY = "Normal"
    TITLE = "Title"
    SUBTITLE = "Subtitle"
    KICKER = "AIA Kicker"
    META = "AIA Meta"
    H1 = "Heading 1"
    H2 = "Heading 2"
    H3 = "Heading 3"
    APPENDIX = "AIA Appendix Heading"
    FRONT_HEADING = "AIA Front Heading"
    LEDE = "AIA Lede"
    CAPTION = "Caption"
    SOURCE = "AIA Source"
    FOOTNOTE = "footnote text"
    HEADER = "Header"
    FOOTER = "Footer"
    TABLE = "AIA Table"
    TABLE_NUMBER = "AIA Table Number"
    TABLE_HEAD = "AIA Table Head"
    TABLE_HEAD_NUMBER = "AIA Table Head Number"
    KPI_VALUE = "AIA KPI"
    KPI_LABEL = "AIA KPI Label"
    QUOTE = "Quote"
    QUOTE_BY = "AIA Quote Attribution"
    MONO = "AIA Mono"
    BULLET = "List Bullet"
    BULLET_2 = "List Bullet 2"
    NUMBER = "List Number"
    NUMBER_2 = "List Number 2"
    TOC_1 = "toc 1"
    TOC_2 = "toc 2"
    TOC_3 = "toc 3"
    TOF = "table of figures"
    CALLOUT_TITLE = "AIA Callout Title"
    CALLOUT = "AIA Callout"
    FIGURE = "AIA Figure"
    FINDING_TITLE = "AIA Finding Title"
    FINDING_LABEL = "AIA Finding Label"
    COVER_RULE = "AIA Cover Rule"
    # character styles
    EMPHASIS = "Emphasis"
    STRONG = "Strong"
    FOOTNOTE_REF = "footnote reference"
    LINK = "Hyperlink"
    NUMERAL = "AIA Numeral"
    GRADE = "AIA Grade"
    # table style
    DATA_TABLE = "AIA Data Table"


#: The ones Word knows by these internal names. They keep them.
_BUILTIN: Final = frozenset(
    {
        S.BODY,
        S.TITLE,
        S.SUBTITLE,
        S.H1,
        S.H2,
        S.H3,
        S.CAPTION,
        S.FOOTNOTE,
        S.HEADER,
        S.FOOTER,
        S.QUOTE,
        S.BULLET,
        S.BULLET_2,
        S.NUMBER,
        S.NUMBER_2,
        S.TOC_1,
        S.TOC_2,
        S.TOC_3,
        S.TOF,
        S.EMPHASIS,
        S.STRONG,
        S.FOOTNOTE_REF,
        S.LINK,
    }
)


def hex_rgb(token: str) -> RGBColor:
    return RGBColor.from_string(COLORS[token].lstrip("#").upper())


def color_val(token: str) -> str:
    return COLORS[token].lstrip("#").upper()


# ---------------------------------------------------------------------- building


@dataclass(frozen=True, slots=True)
class Para:
    """How one Word paragraph style is set, beyond its print style."""

    token: str
    color: str = "doc-ink"
    align: WD_ALIGN_PARAGRAPH | None = None
    keep_next: bool = False
    page_break_before: bool = False
    outline: int | None = None  # 0 = level 1, for the TOC and the navigation pane
    indent_mm: float = 0.0
    hanging_mm: float = 0.0
    space_before_pt: float | None = None
    space_after_pt: float | None = None
    tabs_right_mm: float | None = None  # a right tab with dot leader (TOC entries)
    base: str | None = None


_TEXT_WIDTH_MM: Final = 210 - 24 - 20  # page width minus inside and outside margins

PARAGRAPHS: Final[dict[str, Para]] = {
    S.BODY: Para("doc-body"),
    S.TITLE: Para("doc-title", space_after_pt=10),
    S.SUBTITLE: Para("doc-subtitle", color="doc-muted"),
    S.KICKER: Para("doc-kicker", color="doc-accent", keep_next=True),
    S.META: Para("doc-meta", color="doc-muted"),
    S.H1: Para("doc-h1", keep_next=True, page_break_before=True, outline=0),
    S.H2: Para("doc-h2", keep_next=True, outline=1),
    S.H3: Para("doc-h3", keep_next=True, outline=2),
    S.APPENDIX: Para("doc-h1", keep_next=True, page_break_before=True, outline=0),
    S.FRONT_HEADING: Para("doc-h1", keep_next=True, page_break_before=False),
    S.LEDE: Para("doc-lede"),
    S.CAPTION: Para("doc-caption", keep_next=True, space_before_pt=10, space_after_pt=4),
    S.SOURCE: Para("doc-caption", color="doc-muted", space_before_pt=3, space_after_pt=12),
    S.FOOTNOTE: Para("doc-footnote", color="doc-muted", indent_mm=4, hanging_mm=4),
    S.HEADER: Para("doc-running", color="doc-muted"),
    S.FOOTER: Para("doc-running", color="doc-muted"),
    S.TABLE: Para("doc-table"),
    S.TABLE_NUMBER: Para("doc-table", align=WD_ALIGN_PARAGRAPH.RIGHT),
    S.TABLE_HEAD: Para("doc-table-head"),
    S.TABLE_HEAD_NUMBER: Para("doc-table-head", align=WD_ALIGN_PARAGRAPH.RIGHT),
    S.KPI_VALUE: Para("doc-kpi"),
    S.KPI_LABEL: Para("doc-caption", color="doc-muted", space_before_pt=0, space_after_pt=0),
    S.QUOTE: Para("doc-quote", indent_mm=8),
    S.QUOTE_BY: Para("doc-caption", color="doc-muted", indent_mm=8, space_before_pt=0),
    S.MONO: Para("doc-mono"),
    S.BULLET: Para("doc-body", indent_mm=6, hanging_mm=4, space_after_pt=3),
    S.BULLET_2: Para("doc-body", indent_mm=12, hanging_mm=4, space_after_pt=3),
    S.NUMBER: Para("doc-body", indent_mm=7, hanging_mm=5, space_after_pt=3),
    S.NUMBER_2: Para("doc-body", indent_mm=13, hanging_mm=5, space_after_pt=3),
    S.TOC_1: Para(
        "doc-meta",
        color="doc-ink",
        space_before_pt=6,
        space_after_pt=2,
        tabs_right_mm=_TEXT_WIDTH_MM,
    ),
    S.TOC_2: Para("doc-meta", indent_mm=8, tabs_right_mm=_TEXT_WIDTH_MM),
    S.TOC_3: Para("doc-meta", indent_mm=16, tabs_right_mm=_TEXT_WIDTH_MM),
    S.TOF: Para("doc-meta", tabs_right_mm=_TEXT_WIDTH_MM),
    S.CALLOUT_TITLE: Para("doc-table-head", color="doc-accent", keep_next=True, space_before_pt=4),
    S.CALLOUT: Para("doc-body", space_after_pt=4),
    S.FIGURE: Para("doc-body", keep_next=True, space_before_pt=2, space_after_pt=0),
    S.FINDING_TITLE: Para("doc-h3", keep_next=True, space_before_pt=14),
    S.FINDING_LABEL: Para("doc-table-head", color="doc-muted", keep_next=True, space_before_pt=4),
    S.COVER_RULE: Para("doc-meta", space_before_pt=0, space_after_pt=0),
}


@dataclass(frozen=True, slots=True)
class Char:
    token: str | None = None  # a print style for the face; None keeps the paragraph's
    color: str | None = None
    italic: bool | None = None
    bold: bool | None = None
    superscript: bool = False
    underline: bool = False


CHARACTERS: Final[dict[str, Char]] = {
    S.EMPHASIS: Char(italic=True),
    S.STRONG: Char(bold=True),  # Source Serif 4 has a real Bold face, embedded
    S.FOOTNOTE_REF: Char(superscript=True, color="doc-accent"),
    S.LINK: Char(color="doc-accent", underline=False),
    S.NUMERAL: Char(token="doc-table"),  # tabular Plex Sans numbers inside prose
    S.GRADE: Char(token="doc-caption", color="doc-muted"),
}


def _strip_theme_fonts(rpr: etree._Element) -> etree._Element:
    """Remove theme font attributes: they silently override an explicit font.

    Found by the report prototype: every heading fell back to the theme font
    while the body embedded correctly (``AGENTS.md``, DOCX).
    """
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = el("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        rfonts.attrib.pop(qn(attr), None)
    return rfonts


def _set_face(style: BaseStyle, ps: PrintStyle) -> None:
    rpr = style.element.get_or_add_rPr()
    rfonts = _strip_theme_fonts(rpr)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), ps.font)
    font = style.font  # type: ignore[attr-defined]
    font.size = Pt(ps.size_pt)
    font.bold = ps.bold
    font.italic = ps.italic
    font.all_caps = ps.caps
    if ps.tracking_pt:
        spacing = rpr.find(qn("w:spacing"))
        if spacing is None:
            spacing = el("w:spacing")
            rpr.append(spacing)
        spacing.set(qn("w:val"), str(round(ps.tracking_pt * 20)))


def _paragraph_style(document: Document, name: str) -> ParagraphStyle:
    styles = document.styles
    if name in [s.name for s in styles]:
        style = styles[name]
    else:
        style = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        if name in _BUILTIN:
            style.element.name_val = name  # keep Word's internal name exactly
    assert isinstance(style, ParagraphStyle)
    return style


def _character_style(document: Document, name: str) -> CharacterStyle:
    styles = document.styles
    if name in [s.name for s in styles]:
        style = styles[name]
    else:
        style = styles.add_style(name, WD_STYLE_TYPE.CHARACTER)
        if name in _BUILTIN:
            style.element.name_val = name
    assert isinstance(style, CharacterStyle)
    return style


def _apply_paragraph(style: ParagraphStyle, spec: Para) -> None:
    ps = STYLES[spec.token]
    if spec.base is None and style.name != S.BODY:
        style.base_style = None
    _set_face(style, ps)
    style.font.color.rgb = hex_rgb(spec.color)
    pf = style.paragraph_format
    pf.space_before = Pt(ps.before_pt if spec.space_before_pt is None else spec.space_before_pt)
    pf.space_after = Pt(ps.after_pt if spec.space_after_pt is None else spec.space_after_pt)
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.line_spacing = Pt(ps.leading_pt)
    pf.widow_control = True
    pf.keep_with_next = spec.keep_next
    pf.page_break_before = spec.page_break_before
    pf.alignment = spec.align if spec.align is not None else WD_ALIGN_PARAGRAPH.LEFT
    pf.left_indent = Mm(spec.indent_mm) if spec.indent_mm else None
    pf.first_line_indent = Mm(-spec.hanging_mm) if spec.hanging_mm else None
    ppr = style.element.get_or_add_pPr()
    for existing in ppr.findall(qn("w:outlineLvl")):
        ppr.remove(existing)
    for existing in ppr.findall(qn("w:numPr")):
        ppr.remove(existing)
    if spec.outline is not None:
        ppr.append(el("w:outlineLvl", val=str(spec.outline)))
    if spec.tabs_right_mm is not None:
        pf.tab_stops.clear_all()
        from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER

        pf.tab_stops.add_tab_stop(
            Mm(spec.tabs_right_mm), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS
        )
    style.quick_style = True


def _apply_character(style: CharacterStyle, spec: Char) -> None:
    if spec.token is not None:
        _set_face(style, STYLES[spec.token])
    font = style.font
    if spec.color is not None:
        font.color.rgb = hex_rgb(spec.color)
    if spec.italic is not None:
        font.italic = spec.italic
    if spec.bold is not None:
        font.bold = spec.bold
    font.superscript = spec.superscript or None
    font.underline = spec.underline or None


def _defaults(document: Document) -> None:
    """Document defaults: body face, Czech, no theme fonts, no space by default."""
    styles_el = document.styles.element
    doc_defaults = styles_el.find(qn("w:docDefaults"))
    if doc_defaults is None:
        doc_defaults = el("w:docDefaults")
        styles_el.insert(0, doc_defaults)
    rpr_default = doc_defaults.find(qn("w:rPrDefault"))
    if rpr_default is None:
        rpr_default = el("w:rPrDefault")
        doc_defaults.insert(0, rpr_default)
    rpr = rpr_default.find(qn("w:rPr"))
    if rpr is None:
        rpr = el("w:rPr")
        rpr_default.append(rpr)
    rfonts = _strip_theme_fonts(rpr)
    body = STYLES["doc-body"]
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), body.font)
    for existing in rpr.findall(qn("w:lang")):
        rpr.remove(existing)
    rpr.append(el("w:lang", val="cs-CZ", eastAsia="cs-CZ", bidi="ar-SA"))
    for existing in rpr.findall(qn("w:color")):
        rpr.remove(existing)
    rpr.append(el("w:color", val=color_val("doc-ink")))


def _data_table_style(document: Document) -> None:
    """Rules, not boxes: a heavy rule under the header, hairlines between rows."""
    styles = document.styles
    if S.DATA_TABLE in [s.name for s in styles]:
        return
    style = styles.add_style(S.DATA_TABLE, WD_STYLE_TYPE.TABLE)
    tbl_pr = style.element.find(qn("w:tblPr"))
    if tbl_pr is None:
        tbl_pr = el("w:tblPr")
        style.element.append(tbl_pr)
    borders = el("w:tblBorders")
    for side, size, color in (
        ("top", "8", "doc-ink"),
        ("bottom", "8", "doc-ink"),
        ("insideH", "4", "doc-rule"),
    ):
        borders.append(el(f"w:{side}", val="single", sz=size, space="0", color=color_val(color)))
    for side in ("left", "right", "insideV"):
        borders.append(el(f"w:{side}", val="nil"))
    tbl_pr.append(borders)
    margins = el("w:tblCellMar")
    for side, twips in (("top", "40"), ("bottom", "40"), ("left", "80"), ("right", "80")):
        margins.append(el(f"w:{side}", w=twips, type="dxa"))
    tbl_pr.append(margins)
    # The header row: a heavier rule under it.
    header = el("w:tblStylePr", type="firstRow")
    tc_pr = el("w:tcPr")
    tc_borders = el("w:tcBorders")
    tc_borders.append(el("w:bottom", val="single", sz="8", space="0", color=color_val("doc-ink")))
    tc_pr.append(tc_borders)
    header.append(tc_pr)
    style.element.append(header)


def install_styles(document: Document) -> None:
    """Build the whole style sheet into ``document``. Idempotent."""
    _defaults(document)
    for name, pspec in PARAGRAPHS.items():
        _apply_paragraph(_paragraph_style(document, name), pspec)
    for name, cspec in CHARACTERS.items():
        _apply_character(_character_style(document, name), cspec)
    _data_table_style(document)
    # Styles the report does not restyle (Heading 4-9, the template's character
    # twins) still carry theme fonts; strip them everywhere so nothing falls back.
    for rfonts in document.styles.element.iter(qn("w:rFonts")):
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
            rfonts.attrib.pop(qn(attr), None)


#: CT_PPrBase children after ``w:numPr`` (for list numbering inserted per paragraph).
PPR_AFTER_NUMPR: Final = (
    "suppressLineNumbers",
    "pBdr",
    "shd",
    "tabs",
    "suppressAutoHyphens",
    "kinsoku",
    "wordWrap",
    "overflowPunct",
    "topLinePunct",
    "autoSpaceDE",
    "autoSpaceDN",
    "bidi",
    "adjustRightInd",
    "snapToGrid",
    "spacing",
    "ind",
    "contextualSpacing",
    "mirrorIndents",
    "suppressOverlap",
    "jc",
    "textDirection",
    "textAlignment",
    "textboxTightWrap",
    "outlineLvl",
    "divId",
    "cnfStyle",
    "rPr",
    "sectPr",
    "pPrChange",
)

__all__ = [
    "PARAGRAPHS",
    "PPR_AFTER_NUMPR",
    "S",
    "color_val",
    "hex_rgb",
    "insert_in_order",
    "install_styles",
]
