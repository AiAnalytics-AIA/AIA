"""Document furniture: pages, sections, running heads, the cover and front matter.

A report has three kinds of section, each a Word section of its own:

* the **cover**, with no running heads (a draft's cover still carries the draft
  notice in its footer: every footer of an unapproved report says so);
* the **front matter** (document control, contents, lists), paged in lower-case
  roman numerals from i;
* the **body**, paged in arabic numerals from 1, with the report title and the
  client in the header and the classification and page
  in the footer. Appendices and landscape pages are further sections of the body
  that continue its numbering.

Word stores a section's properties in the ``w:sectPr`` of the paragraph that
*ends* it, and the last section's in the body. :func:`end_section` therefore
moves the current body ``sectPr`` into the section's last paragraph and resets
the body one for the section that follows, without adding the empty paragraph
python-docx's ``add_section`` would.
"""

from __future__ import annotations

import copy
import re
from io import BytesIO
from pathlib import Path
from typing import Final, Literal

from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.oxml.ns import qn
from docx.section import Section
from docx.shared import Mm
from docx.text.paragraph import Paragraph
from lxml import etree

from aia_core.domain.report import numbers
from aia_core.domain.report.copy import method_status_text, t
from aia_core.domain.report.model import Classification, ReportKind
from aia_core.domain.report.outline import OutlineEntry
from aia_core.domain.report.print_tokens import PAGE
from aia_core.infrastructure.report_docx.context import RenderContext
from aia_core.infrastructure.report_docx.ooxml import (
    SECTPR_ORDER,
    add_field,
    add_tab,
    add_toc_entry,
    begin_field,
    el,
    end_field,
    insert_ordered,
)
from aia_core.infrastructure.report_docx.styles import S

PageFormat = Literal["lowerRoman", "decimal"]

#: The TOC fields. ``\u`` picks up paragraph outline levels (the appendix
#: heading style has one), ``\c`` collects the captions' SEQ fields by name.
TOC_CONTENTS: Final = 'TOC \\o "1-3" \\h \\z \\u'
TOC_FIGURES: Final = 'TOC \\h \\z \\c "Graf"'
TOC_TABLES: Final = 'TOC \\h \\z \\c "Tabulka"'


# ---------------------------------------------------------------------- pages


def page_setup(section: Section, *, landscape: bool = False) -> None:
    """A4 from the print tokens; inside/outside margins mirror (settings)."""
    width, height = Mm(PAGE.width_mm), Mm(PAGE.height_mm)
    section.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    section.page_width, section.page_height = (height, width) if landscape else (width, height)
    section.top_margin = Mm(PAGE.margin_top_mm)
    section.bottom_margin = Mm(PAGE.margin_bottom_mm)
    section.left_margin = Mm(PAGE.margin_inside_mm)
    section.right_margin = Mm(PAGE.margin_outside_mm)
    section.header_distance = Mm(PAGE.header_mm)
    section.footer_distance = Mm(PAGE.footer_mm)
    section.gutter = Mm(0)


def page_numbers(section: Section, fmt: PageFormat, *, restart: bool) -> None:
    sect_pr: etree._Element = section._sectPr
    pg = el("w:pgNumType", fmt=fmt)
    if restart:
        pg.set(qn("w:start"), "1")
    insert_ordered(sect_pr, pg, SECTPR_ORDER)


def end_section(ctx: RenderContext, last: Paragraph, *, landscape: bool = False) -> Section:
    """End the current section at ``last``; return the section that follows it.

    The new section starts on a new page, inherits the running heads (a caller
    that wants its own unlinks them) and continues the page numbering.
    """
    body: etree._Element = ctx.document.element.body
    body_sect = body.find(qn("w:sectPr"))
    assert body_sect is not None
    ppr: etree._Element = last._p.get_or_add_pPr()
    for existing in ppr.findall(qn("w:sectPr")):
        ppr.remove(existing)
    ppr.append(copy.deepcopy(body_sect))  # sectPr is the last child of pPr but rPr/pPrChange

    for ref in body_sect.findall(qn("w:headerReference")) + body_sect.findall(
        qn("w:footerReference")
    ):
        body_sect.remove(ref)
    insert_ordered(body_sect, el("w:type", val="nextPage"), SECTPR_ORDER)
    pg = body_sect.find(qn("w:pgNumType"))
    if pg is not None:
        pg.attrib.pop(qn("w:start"), None)
    section = ctx.document.sections[-1]
    page_setup(section, landscape=landscape)
    return section


def last_paragraph(ctx: RenderContext) -> Paragraph:
    """The body's last paragraph, adding an empty one after a trailing table."""
    body: etree._Element = ctx.document.element.body
    children = [c for c in body if c.tag != qn("w:sectPr")]
    if children and children[-1].tag == qn("w:p"):
        return ctx.document.paragraphs[-1]
    return ctx.document.add_paragraph(style=S.BODY)


# ---------------------------------------------------------------------- running heads


def _classification(ctx: RenderContext) -> str:
    if ctx.report.meta.classification is Classification.INTERNAL:
        return t("classification_internal")
    return t("classification_client")


def _draft(ctx: RenderContext) -> bool:
    return not ctx.report.meta.approvals


def running(ctx: RenderContext, section: Section, *, wide: bool = False) -> None:
    """The running heads of ``section``, from ``ctx.running``.

    A landscape page has its own (``wide``) Header/Footer styles, whose right tab
    sits at the landscape text width, so a section after it sets them again.
    """
    running_head(section, ctx.report.meta.study_name, ctx.report.meta.client_name, wide=wide)
    running_foot(ctx, section, page=True, wide=wide)


def running_head(
    section: Section,
    title: str,
    client: str,
    *,
    wide: bool = False,
) -> None:
    """The supplied template's AIA/study identity and client, over a fine rule."""
    header = section.header
    header.is_linked_to_previous = False
    p = header.paragraphs[0]
    p.style = S.HEADER_WIDE if wide else S.HEADER
    p.add_run(f"AIA · {title}")
    add_tab(p)
    p.add_run(client)


def running_foot(ctx: RenderContext, section: Section, *, page: bool, wide: bool = False) -> None:
    """Classification and the page; a draft's footer says it is a draft, first."""
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.style = S.FOOTER_WIDE if wide else S.FOOTER
    if _draft(ctx):
        p.add_run(t("draft"), style=S.DRAFT)
        p.add_run(t("separator"))
    p.add_run(_classification(ctx))
    if page:
        add_tab(p)
        add_field(p, "PAGE", "1")


# ---------------------------------------------------------------------- cover


def render_cover(ctx: RenderContext) -> None:
    from aia_core.infrastructure.report_docx.cover import add_cover_field, add_cover_logo
    from aia_core.infrastructure.report_docx.images import add_vector_image

    meta = ctx.report.meta
    d = ctx.document
    cover = d.sections[0]
    cover.top_margin = Mm(22)
    cover.bottom_margin = Mm(20)
    cover.header_distance = Mm(0)
    # Header artwork stays on the cover, with relationships owned by that part.
    header = cover.header
    header.is_linked_to_previous = False
    field = header.paragraphs[0]
    field.style = S.COVER_RULE
    add_cover_field(ctx, field)
    logo = header.add_paragraph(style=S.COVER_RULE)
    add_cover_logo(ctx, logo)

    placement = d.add_table(rows=1, cols=1)
    placement.style = S.COVER_TABLE
    placement.autofit = False
    placement.columns[0].width = Mm(120)
    placement.rows[0].height = Mm(250)
    placement.rows[0].height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    cell = placement.cell(0, 0)
    cell.width = Mm(120)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.BOTTOM
    placement.rows[0]._tr.get_or_add_trPr().append(el("w:cantSplit"))
    if meta.branding.client_logo_png is not None:
        p = cell.paragraphs[0]
        p.style = S.META
        p.add_run().add_picture(BytesIO(meta.branding.client_logo_png), height=Mm(14))
        kicker = cell.add_paragraph(style=S.KICKER)
    else:
        kicker = cell.paragraphs[0]
        kicker.style = S.KICKER
    kind = meta.title if meta.kind is ReportKind.INTERNAL else t(f"kind_{meta.kind.value}")
    kicker.add_run(kind)
    cover_title = meta.study_name if meta.kind is ReportKind.INTERNAL else meta.title
    cover_title = re.sub(
        r"\d{4}-\d{2}-\d{2}", lambda m: m.group().replace("-", "\u2011"), cover_title
    )
    cell.add_paragraph(cover_title, style=S.TITLE)
    if meta.subtitle:
        cell.add_paragraph(meta.subtitle, style=S.SUBTITLE)
    # A literal 42pt by 2.25pt accent rule, from the supplied design.
    accent = cell.add_paragraph(style=S.COVER_ACCENT)
    add_vector_image(
        accent,
        ctx.svgs,
        svg=(
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 3">'
            b'<rect width="56" height="3" fill="#0d5279"/></svg>'
        ),
        png=(Path(__file__).parent / "assets" / "report-cover-accent.png").read_bytes(),
        width_mm=14.8167,
        height_mm=0.79375,
        alt="",
        name="AIA cover accent",
    )
    grid = cell.add_table(rows=0, cols=2)
    grid.style = S.COVER_META_TABLE
    grid.autofit = False
    grid.columns[0].width = Mm(22)
    grid.columns[1].width = Mm(98)
    signature = meta.approvals[-1].reviewer if meta.approvals else "čeká na podpis"
    rows = [
        ("Klient", meta.client_name, S.META),
        ("Datum", numbers.czech_date(meta.issued_on), S.META),
        ("Autoři", meta.prepared_by, S.META),
        ("Revize", str(meta.revision), S.MONO),
        ("Schválení", signature, S.META),
    ]
    for label, value, style in rows:
        cells = grid.add_row().cells
        cells[0].width, cells[1].width = Mm(22), Mm(98)
        cells[0].paragraphs[0].style = S.META
        cells[0].paragraphs[0].add_run(label)
        cells[1].paragraphs[0].style = style
        cells[1].paragraphs[0].add_run(value)
    cell.paragraphs[-1].style = S.COVER_RULE
    notice = cell.add_paragraph(_classification(ctx), style=S.COVER_NOTICE)
    if _draft(ctx):
        notice.add_run(" · " + t("draft"), style=S.DRAFT)
        notice.add_run(". " + t("draft_long"))
        footer = cover.footer
        footer.is_linked_to_previous = False
        fp = footer.paragraphs[0]
        fp.style = S.FOOTER
        fp.add_run(t("draft"), style=S.DRAFT)
    d.add_paragraph(style=S.COVER_RULE)


# ---------------------------------------------------------------------- front matter


def _key_value_table(ctx: RenderContext, rows: list[tuple[str, str]]) -> None:
    table = ctx.document.add_table(rows=0, cols=2)
    table.style = S.DATA_TABLE
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].paragraphs[0].style = S.TABLE_HEAD
        cells[0].paragraphs[0].add_run(label)
        cells[1].paragraphs[0].style = S.TABLE
        cells[1].paragraphs[0].add_run(value)


def _grid(ctx: RenderContext, head: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    table = ctx.document.add_table(rows=1, cols=len(head))
    table.style = S.DATA_TABLE
    for cell, label in zip(table.rows[0].cells, head, strict=True):
        cell.paragraphs[0].style = S.TABLE_HEAD
        cell.paragraphs[0].add_run(label)
    for row in rows:
        for cell, value in zip(table.add_row().cells, row, strict=True):
            cell.paragraphs[0].style = S.TABLE
            cell.paragraphs[0].add_run(value)


def render_document_control(ctx: RenderContext) -> None:
    """The meta table, sign-off and revision history; identifiers only internally."""
    meta = ctx.report.meta
    d = ctx.document
    d.add_paragraph(t("document_control"), style=S.FRONT_HEADING)
    rows = [
        (t("client"), meta.client_name),
        (t("study"), meta.study_name),
        (t("date"), numbers.czech_date(meta.issued_on)),
        (t("revision").capitalize(), str(meta.revision)),
        (t("classification"), _classification(ctx)),
        (t("prepared_by"), meta.prepared_by),
        (t("method_status"), method_status_text(meta.method_status)),
    ]
    if not ctx.client:
        rows.insert(2, (t("study_id"), meta.study_id))
    _key_value_table(ctx, rows)

    d.add_paragraph(t("approval"), style=S.H2_FRONT)
    if meta.approvals:
        _grid(
            ctx,
            (t("reviewer"), t("decided_on")),
            [(a.reviewer, numbers.czech_date(a.decided_on)) for a in meta.approvals],
        )
    else:
        p = d.add_paragraph(style=S.BODY)
        p.add_run(t("draft"), style=S.DRAFT)
        p.add_run(" " + t("draft_long"))

    if meta.history:
        d.add_paragraph(t("revision_history"), style=S.H2_FRONT)
        _grid(
            ctx,
            (t("revision").capitalize(), t("date"), t("change")),
            [(str(h.revision), numbers.czech_date(h.on), h.summary) for h in meta.history],
        )

    if not ctx.client and meta.identifiers:
        d.add_paragraph(t("identifiers"), style=S.H2_FRONT)
        table = d.add_table(rows=0, cols=2)
        table.style = S.DATA_TABLE
        for label, value in meta.identifiers:
            cells = table.add_row().cells
            cells[0].paragraphs[0].style = S.TABLE_HEAD
            cells[0].paragraphs[0].add_run(label)
            cells[1].paragraphs[0].style = S.MONO
            cells[1].paragraphs[0].add_run(value)


def heading_label(entry: OutlineEntry, *, appendix: bool) -> str:
    """How a heading's number prints: ``2.1`` or, for an appendix, ``Příloha A``."""
    if appendix and entry.level == 1:
        return f"{t('appendix')} {entry.number}"
    return entry.number


def _toc(
    ctx: RenderContext,
    instruction: str,
    entries: list[tuple[str, str, str]],
) -> None:
    """A TOC field whose cached result is the outline's own entries.

    ``entries`` are ``(style, text, anchor)``. Word refreshes the field on open
    (``w:updateFields``); a reader that never computes fields shows these.
    """
    d = ctx.document
    first: Paragraph | None = None
    last: Paragraph | None = None
    for style, text, anchor in entries:
        p = d.add_paragraph(style=style)
        if first is None:
            first = p
            begin_field(p, instruction)
        add_toc_entry(p, text, ctx.bookmarks.name(anchor), "")
        last = p
    assert first is not None and last is not None
    end_field(last)


def render_contents(ctx: RenderContext) -> None:
    """Obsah, Seznam grafů and Seznam tabulek, each a TOC field."""
    report, outline = ctx.report, ctx.outline
    d = ctx.document
    appendix_anchors = {
        e.anchor
        for e, s in zip([h for h in outline.headings if h.level == 1], report.sections, strict=True)
        if s.appendix
    }
    if report.table_of_contents:
        d.add_paragraph(t("contents"), style=S.FRONT_HEADING_BREAK)
        styles = {1: S.TOC_1, 2: S.TOC_2, 3: S.TOC_3}
        _toc(
            ctx,
            TOC_CONTENTS,
            [
                (
                    styles[e.level],
                    f"{heading_label(e, appendix=e.anchor in appendix_anchors)} {e.title}",
                    e.anchor,
                )
                for e in outline.headings
            ],
        )
    for wanted, entries, heading, word, instruction in (
        (report.list_of_figures, outline.figures, "list_of_figures", "figure", TOC_FIGURES),
        (report.list_of_tables, outline.tables, "list_of_tables", "table", TOC_TABLES),
    ):
        if wanted and entries:
            d.add_paragraph(t(heading), style=S.FRONT_HEADING)
            _toc(
                ctx,
                instruction,
                [(S.TOF, f"{t(word)} {e.number} \u2014 {e.title}", e.anchor) for e in entries],
            )
