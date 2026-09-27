"""Which renderer draws which block: the one table of the report's components."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aia_core.domain.report import model
from aia_core.infrastructure.report_docx import blocks, tables
from aia_core.infrastructure.report_docx.context import Container, RenderContext

_RENDERERS: dict[type[Any], Callable[[RenderContext, Container, Any], None]] = {
    model.Heading: blocks.render_heading,
    model.Paragraph: blocks.render_paragraph,
    model.PageBreak: blocks.render_page_break,
    model.Callout: blocks.render_callout,
    model.BulletList: blocks.render_list,
    model.Quote: blocks.render_quote,
    model.KeyFinding: blocks.render_key_finding,
    model.Recommendation: blocks.render_recommendation,
    model.KpiRow: blocks.render_kpi_row,
    model.EvidenceKey: blocks.render_evidence_key,
    model.EvidenceAppendix: blocks.render_evidence_appendix,
    model.AuditBlock: blocks.render_audit,
    model.Table: tables.render_table,
}


def render_block(ctx: RenderContext, container: Container, block: model.Block) -> None:
    renderer = _RENDERERS.get(type(block))
    if renderer is None:
        raise NotImplementedError(f"no renderer for {type(block).__name__} yet")
    renderer(ctx, container, block)
