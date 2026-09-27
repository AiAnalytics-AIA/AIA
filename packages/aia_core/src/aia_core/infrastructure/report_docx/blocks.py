"""One renderer per block of the document model.

Each function takes the render context, the container it writes into (the body,
or a table cell) and one block, and writes paragraphs that carry a named style
and nothing else: no run or paragraph here sets a font, a size, a colour or an
indent. How a block looks is the style sheet's (``styles.py``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from docx.enum.text import WD_BREAK
from docx.text.paragraph import Paragraph as DocxParagraph

from aia_core.domain.report import numbers
from aia_core.domain.report.copy import method_status_text, t
from aia_core.domain.report.evidence import PrintGrade
from aia_core.domain.report.model import (
    AuditBlock,
    Block,
    BulletList,
    Callout,
    CalloutKind,
    CrossRef,
    EvidenceAppendix,
    EvidenceKey,
    Footnote,
    Heading,
    Inline,
    KeyFinding,
    KpiRow,
    Link,
    ListItem,
    PageBreak,
    Paragraph,
    ParagraphRole,
    Quote,
    Recommendation,
    Section,
    Text,
    Value,
)
from aia_core.domain.report.outline import OutlineEntry
from aia_core.domain.report.validation import cited_refs
from aia_core.infrastructure.report_docx.context import Container, RenderContext
from aia_core.infrastructure.report_docx.layout import heading_label
from aia_core.infrastructure.report_docx.marks import UNKNOWN_GLYPH, grade_label
from aia_core.infrastructure.report_docx.numbering import Numbering
from aia_core.infrastructure.report_docx.ooxml import (
    add_external_link,
    add_internal_link,
    full_width,
    header_row,
)
from aia_core.infrastructure.report_docx.styles import S

# ---------------------------------------------------------------------- inline

_EMPHASIS = {"none": None, "em": S.EMPHASIS, "strong": S.STRONG}


def write_inlines(ctx: RenderContext, p: DocxParagraph, content: tuple[Inline, ...]) -> None:
    for inline in content:
        if isinstance(inline, Text):
            p.add_run(inline.text, style=_EMPHASIS[inline.emphasis])
        elif isinstance(inline, Value):
            write_value(ctx, p, inline.ref, with_interval=inline.with_interval)
        elif isinstance(inline, Footnote):
            ctx.footnotes.add(p, inline.text)
        elif isinstance(inline, CrossRef):
            add_internal_link(
                p,
                ctx.outline.labels[inline.target],
                ctx.bookmarks.name(inline.target),
                style=S.LINK,
            )
        elif isinstance(inline, Link):
            add_external_link(p, inline.text, inline.url, style=S.LINK)


def value_text(ctx: RenderContext, ref: str, *, with_interval: bool, unit: bool = True) -> str:
    """How one evidenced value prints: exactly as the evidence rounded it.

    In a client report an estimate always carries its interval, whatever the
    block asked for (validation guarantees there is one).
    """
    row = ctx.ledger.row(ref)
    out = (
        numbers.with_unit(row.value, row.decimals, row.unit)
        if unit
        else numbers.number(row.value, row.decimals)
    )
    if row.interval is not None and (with_interval or (ctx.client and row.is_estimate)):
        out += f"{numbers.NBSP}{numbers.interval(row.interval, row.decimals, row.unit)}"
    return out


def base_text(ctx: RenderContext, ref: str) -> str:
    """``n = 1 204``: the row's effective n, rounded down. Absent → ``?``, never a guess."""
    effective = ctx.ledger.row(ref).support.effective_n
    if effective is None:
        return f"n{numbers.NBSP}={numbers.NBSP}{UNKNOWN_GLYPH}"
    return numbers.base_n(effective)


def write_value(ctx: RenderContext, p: DocxParagraph, ref: str, *, with_interval: bool) -> None:
    """``42,5 % (38,1-46,9 %)`` in the numeral face, its grade mark, "orientační"."""
    p.add_run(value_text(ctx, ref, with_interval=with_interval), style=S.NUMERAL)
    p.add_run(numbers.NBSP)
    write_mark(ctx, p, ref)
    if ctx.ledger.is_indicative(ref):
        p.add_run(f" ({t('indicative')})", style=S.GRADE)


def write_mark(ctx: RenderContext, p: DocxParagraph, ref: str) -> None:
    ctx.marks.add(p, ctx.ledger.grade(ref))


def write_marks(ctx: RenderContext, p: DocxParagraph, refs: tuple[str, ...]) -> None:
    for ref in refs:
        p.add_run(numbers.NBSP)
        write_mark(ctx, p, ref)


# ---------------------------------------------------------------------- headings


def chapter_heading(ctx: RenderContext, index: int, section: Section) -> DocxParagraph:
    """``Heading 1`` (or the appendix style): the number, then the title; bookmarked."""
    entry = _chapter_entry(ctx, index)
    style = S.APPENDIX if section.appendix else S.H1
    p = ctx.document.add_paragraph(style=style)
    p.add_run(heading_label(entry, appendix=section.appendix), style=S.HEADING_NUMBER)
    p.add_run(f" {section.title}")
    ctx.bookmarks.wrap(p, entry.anchor)
    return p


def _chapter_entry(ctx: RenderContext, index: int) -> OutlineEntry:
    return [e for e in ctx.outline.headings if e.level == 1][index]


def render_heading(ctx: RenderContext, container: Container, block: Heading) -> None:
    number = ctx.outline.heading_numbers[ctx.position]
    anchor = next(
        e.anchor for e in ctx.outline.headings if e.number == number and e.level == block.level
    )
    p = container.add_paragraph(style=S.H2 if block.level == 2 else S.H3)
    p.add_run(number, style=S.HEADING_NUMBER)
    p.add_run(f" {block.text}")
    ctx.bookmarks.wrap(p, anchor)


# ---------------------------------------------------------------------- text


def render_paragraph(ctx: RenderContext, container: Container, block: Paragraph) -> None:
    style = S.LEDE if block.role is ParagraphRole.LEDE else S.BODY
    write_inlines(ctx, container.add_paragraph(style=style), block.content)


def render_page_break(ctx: RenderContext, container: Container, block: PageBreak) -> None:
    container.add_paragraph(style=S.BODY).add_run().add_break(WD_BREAK.PAGE)


# ---------------------------------------------------------------------- callouts

_CALLOUT_TITLES = {
    CalloutKind.DECISION: "decision_answer",
    CalloutKind.METHOD: "method_status",
    CalloutKind.LIMITATION: "limitation",
    CalloutKind.PROVISIONAL: "provisional",
    CalloutKind.NOTE: "note",
}


def render_callout(ctx: RenderContext, container: Container, block: Callout) -> None:
    """A boxed statement: title (with the grades of its refs), then its text.

    The method callout always prints the document's method status in the words
    code chose (``copy.method_status_text``) before anything the template adds.
    """
    title = container.add_paragraph(style=S.CALLOUT_TITLE)
    title.add_run(block.title or t(_CALLOUT_TITLES[block.kind]))
    write_marks(ctx, title, block.refs)
    if block.kind is CalloutKind.METHOD:
        container.add_paragraph(method_status_text(ctx.report.meta.method_status), style=S.CALLOUT)
    if block.content:
        write_inlines(ctx, container.add_paragraph(style=S.CALLOUT), block.content)


# ---------------------------------------------------------------------- lists and quotes


def render_list(ctx: RenderContext, container: Container, block: BulletList) -> None:
    num_id = ctx.numbering.new_ordered_list() if block.ordered else ctx.numbering.bullets
    styles = (S.NUMBER, S.NUMBER_2) if block.ordered else (S.BULLET, S.BULLET_2)
    for item in block.items:
        _list_item(ctx, container, item, num_id, styles, 0)


def _list_item(
    ctx: RenderContext,
    container: Container,
    item: ListItem,
    num_id: int,
    styles: tuple[str, str],
    level: int,
) -> None:
    p = container.add_paragraph(style=styles[level])
    Numbering.apply(p, num_id, level)
    write_inlines(ctx, p, item.content)
    for child in item.children:
        _list_item(ctx, container, child, num_id, styles, 1)


def render_quote(ctx: RenderContext, container: Container, block: Quote) -> None:
    """A verbatim quote in Czech quotation marks; a synthetic respondent says so."""
    container.add_paragraph(f"\u201e{block.text}\u201c", style=S.QUOTE)
    by = f"\u2014 {block.attribution}"
    if block.synthetic:
        by += f", {t('synthetic_quote')}"
    container.add_paragraph(by, style=S.QUOTE_BY)


# ---------------------------------------------------------------------- findings


def _labelled(container: Container, label: str, body: str) -> None:
    container.add_paragraph(label, style=S.FINDING_LABEL)
    container.add_paragraph(body, style=S.BODY)


def render_key_finding(ctx: RenderContext, container: Container, block: KeyFinding) -> None:
    """Legacy ``key_findings``: headline, finding, evidence, meaning, confidence."""
    title = container.add_paragraph(block.headline, style=S.FINDING_TITLE)
    write_marks(ctx, title, block.refs)
    container.add_paragraph(block.finding, style=S.BODY)
    _labelled(container, t("finding_evidence"), block.evidence)
    _labelled(container, t("finding_meaning"), block.meaning)
    _labelled(container, t("finding_confidence"), block.confidence)


def render_recommendation(ctx: RenderContext, container: Container, block: Recommendation) -> None:
    """Legacy ``implications``: the action, why, and its priority."""
    title = container.add_paragraph(block.action, style=S.FINDING_TITLE)
    write_marks(ctx, title, block.refs)
    _labelled(container, t("recommendation_why"), block.why)
    _labelled(container, t("recommendation_priority"), block.priority)


def render_kpi_row(ctx: RenderContext, container: Container, block: KpiRow) -> None:
    """Stat tiles in a borderless table: value and mark, label, then base n."""
    table = ctx.document.add_table(rows=1, cols=len(block.items))
    table.style = S.KPI_TABLE
    full_width(table)
    for cell, kpi in zip(table.rows[0].cells, block.items, strict=True):
        value = cell.paragraphs[0]
        value.style = S.KPI_VALUE
        row = ctx.ledger.row(kpi.ref)
        value.add_run(numbers.with_unit(row.value, row.decimals, row.unit))
        value.add_run(numbers.NBSP)
        write_mark(ctx, value, kpi.ref)
        cell.add_paragraph(kpi.label, style=S.KPI_LABEL)
        base = base_text(ctx, kpi.ref)
        if row.interval is not None:  # the tile's interval sits under it, never dropped
            base += f"{t('separator')}{numbers.interval(row.interval, row.decimals, row.unit)}"
        if ctx.ledger.is_indicative(kpi.ref):
            base += f", {t('indicative')}"
        cell.add_paragraph(base, style=S.KPI_LABEL)


# ---------------------------------------------------------------------- evidence


def _grade_text(grade: PrintGrade) -> str:
    return UNKNOWN_GLYPH if grade is PrintGrade.UNKNOWN else grade_label(grade)


def render_evidence_key(ctx: RenderContext, container: Container, block: EvidenceKey) -> None:
    """The key to the marks, every grade, the unknown one included."""
    container.add_paragraph(t("evidence_key"), style=S.CALLOUT_TITLE)
    for grade in PrintGrade:
        p = container.add_paragraph(style=S.CALLOUT)
        ctx.marks.add(p, grade)
        p.add_run(f" {grade_label(grade)}", style=S.STRONG)
        key = grade.value.replace("-", "_")
        p.add_run(f" \u2014 {t(f'grade_{key}_long')}")


def render_evidence_appendix(
    ctx: RenderContext, container: Container, block: EvidenceAppendix
) -> None:
    """One row per cited ref: value, interval, effective n, support, basis, grade."""
    head = (
        t("evidence"),
        t("value"),
        t("interval_head"),
        t("effective_n_head"),
        t("support"),
        t("basis"),
        t("grade"),
        t("disclosures"),
    )
    numeric = {1, 2, 3}
    table = ctx.document.add_table(rows=1, cols=len(head))
    table.style = S.DATA_TABLE
    full_width(table)
    header_row(table.rows[0])
    for i, (cell, label) in enumerate(zip(table.rows[0].cells, head, strict=True)):
        cell.paragraphs[0].style = S.TABLE_HEAD_NUMBER if i in numeric else S.TABLE_HEAD
        cell.paragraphs[0].add_run(label)
    refs = cited_refs(ctx.report)
    for ref in refs:
        row = ctx.ledger.row(ref)
        interval = (
            numbers.interval(row.interval, row.decimals, row.unit)
            if row.interval is not None
            else t("no_value")
        )
        values = (
            ref,
            numbers.with_unit(row.value, row.decimals, row.unit),
            interval,
            UNKNOWN_GLYPH
            if row.support.effective_n is None
            else numbers.effective_n(row.support.effective_n),
            t(f"support_{row.support.status.value}"),
            t(f"basis_{row.basis.value}"),
            _grade_text(ctx.ledger.grade(ref)),
            ", ".join(t(f"disclosure_short_{d.value}") for d in sorted(row.disclosures)),
        )
        cells = table.add_row().cells
        for i, (cell, value) in enumerate(zip(cells, values, strict=True)):
            cell.paragraphs[0].style = (
                S.MONO if i == 0 else S.TABLE_NUMBER if i in numeric else S.TABLE
            )
            cell.paragraphs[0].add_run(value)
    used = sorted({d for ref in refs for d in ctx.ledger.row(ref).disclosures})
    for d in used:
        p = container.add_paragraph(style=S.SOURCE)
        p.add_run(t(f"disclosure_short_{d.value}"), style=S.STRONG)
        p.add_run(f" \u2014 {t(f'disclosure_{d.value}')}")


def render_audit(ctx: RenderContext, container: Container, block: AuditBlock) -> None:
    """Run ids, fingerprints, provider and model. Internal reports only (validated)."""
    container.add_paragraph(t("audit"), style=S.H2_FRONT)
    table = ctx.document.add_table(rows=1, cols=2)
    table.style = S.DATA_TABLE
    full_width(table)
    header_row(table.rows[0])
    for cell, label in zip(table.rows[0].cells, (t("audit_key"), t("value")), strict=True):
        cell.paragraphs[0].style = S.TABLE_HEAD
        cell.paragraphs[0].add_run(label)
    for key, value in block.entries:
        cells = table.add_row().cells
        cells[0].paragraphs[0].style = S.TABLE
        cells[0].paragraphs[0].add_run(key)
        cells[1].paragraphs[0].style = S.MONO
        cells[1].paragraphs[0].add_run(value)


# ---------------------------------------------------------------------- dispatch

_RENDERERS: dict[type[Any], Callable[[RenderContext, Container, Any], None]] = {
    Heading: render_heading,
    Paragraph: render_paragraph,
    PageBreak: render_page_break,
    Callout: render_callout,
    BulletList: render_list,
    Quote: render_quote,
    KeyFinding: render_key_finding,
    Recommendation: render_recommendation,
    KpiRow: render_kpi_row,
    EvidenceKey: render_evidence_key,
    EvidenceAppendix: render_evidence_appendix,
    AuditBlock: render_audit,
}


def render_block(ctx: RenderContext, container: Container, block: Block) -> None:
    renderer = _RENDERERS.get(type(block))
    if renderer is None:
        raise NotImplementedError(f"no renderer for {type(block).__name__} yet")
    renderer(ctx, container, block)
