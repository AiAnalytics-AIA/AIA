"""``DocxRenderer``: a validated :class:`ReportDocument` in, DOCX bytes out.

The one entry point of the report's infrastructure. It trusts nothing it is
handed: the document is validated (``require_valid``) before a byte exists, and
the outline — every printed number of the furniture — is computed once, first.
Then the sections are written in order (cover, front matter, body, appendices),
and the package is finished: footnotes, core properties, embedded fonts, and
``w:updateFields`` so Word refreshes the contents on open.

**The output is deterministic.** The same document renders to the same bytes:
the zip is rewritten with fixed timestamps and the core properties are dated by
the report's issue date, so a report's content fingerprint is stable.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from typing import Final

import docx
from docx.oxml.ns import qn

from aia_core.domain.report.model import EvidenceAppendix, ReportDocument
from aia_core.domain.report.outline import build_outline
from aia_core.domain.report.print_tokens import FONTS
from aia_core.domain.report.validation import require_valid
from aia_core.infrastructure.report_docx import layout
from aia_core.infrastructure.report_docx.blocks import chapter_heading
from aia_core.infrastructure.report_docx.context import RenderContext
from aia_core.infrastructure.report_docx.dispatch import render_block
from aia_core.infrastructure.report_docx.embed import embed_fonts
from aia_core.infrastructure.report_docx.footnotes import Footnotes
from aia_core.infrastructure.report_docx.images import SvgParts
from aia_core.infrastructure.report_docx.marks import Marks
from aia_core.infrastructure.report_docx.numbering import Numbering
from aia_core.infrastructure.report_docx.ooxml import SETTINGS_ORDER, Bookmarks, el, insert_ordered
from aia_core.infrastructure.report_docx.styles import S, install_styles

#: The zip timestamp every part carries: the earliest the format allows.
_ZIP_EPOCH: Final = (1980, 1, 1, 0, 0, 0)


class DocxRenderer:
    """Renders a report to DOCX. Implements ``domain.report.ReportRenderer``."""

    media_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def render(self, doc: ReportDocument) -> bytes:
        require_valid(doc)
        document = docx.Document()
        install_styles(document)
        svgs = SvgParts(document)
        ctx = RenderContext(
            document=document,
            report=doc,
            outline=build_outline(doc),
            bookmarks=Bookmarks(),
            footnotes=Footnotes(document),
            numbering=Numbering(document),
            svgs=svgs,
            marks=Marks(svgs),
        )
        _write(ctx)
        _finish(ctx)
        out = io.BytesIO()
        document.save(out)
        return _normalise_zip(out.getvalue())


def _write(ctx: RenderContext) -> None:
    first_chapter = ctx.outline.headings[0].number
    first_title = f"{first_chapter} {ctx.report.sections[0].title}"

    layout.page_setup(ctx.document.sections[0])
    layout.render_cover(ctx)

    front = layout.end_section(ctx, layout.last_paragraph(ctx))
    layout.page_numbers(front, "lowerRoman", restart=True)
    layout.running(ctx, front)
    layout.render_document_control(ctx)
    layout.render_contents(ctx)

    body = layout.end_section(ctx, layout.last_paragraph(ctx))
    layout.page_numbers(body, "decimal", restart=True)
    ctx.running = (S.H1, first_title)
    layout.running(ctx, body)

    in_appendix = False
    wide = False
    for si, section in enumerate(ctx.report.sections):
        needs_wide = section.appendix and any(
            isinstance(b, EvidenceAppendix) for b in section.blocks
        )
        if (section.appendix and not in_appendix) or needs_wide != wide:
            in_appendix = section.appendix
            wide = needs_wide
            if si > 0:
                appendix = layout.end_section(ctx, layout.last_paragraph(ctx), landscape=wide)
                label = layout.heading_label(
                    [e for e in ctx.outline.headings if e.level == 1][si],
                    appendix=section.appendix,
                )
                ctx.running = (S.APPENDIX if section.appendix else S.H1, f"{label} {section.title}")
                layout.running(ctx, appendix, wide=wide)
        chapter_heading(ctx, si, section)
        for bi, block in enumerate(section.blocks):
            ctx.position = (si, bi)
            render_block(ctx, ctx.document, block)


def _finish(ctx: RenderContext) -> None:
    meta = ctx.report.meta
    document = ctx.document
    ctx.footnotes.finish()

    issued = datetime(meta.issued_on.year, meta.issued_on.month, meta.issued_on.day, tzinfo=UTC)
    props = document.core_properties
    props.title = meta.title
    props.subject = meta.subtitle or meta.study_name
    props.author = meta.prepared_by
    props.last_modified_by = meta.prepared_by
    props.language = "cs-CZ"
    props.revision = meta.revision
    props.created = issued
    props.modified = issued
    props.last_printed = issued
    props.comments = ""
    props.keywords = ""
    props.category = meta.kind.value

    embed_fonts(document, FONTS)
    settings = document.settings.element
    insert_ordered(settings, el("w:mirrorMargins"), SETTINGS_ORDER)
    insert_ordered(settings, el("w:updateFields", val="true"), SETTINGS_ORDER)
    # The template's rsid table records python-docx's own editing session; it is
    # noise that differs from nothing, but it is not ours to ship.
    for rsids in settings.findall(qn("w:rsids")):
        settings.remove(rsids)


def _normalise_zip(data: bytes) -> bytes:
    """Rewrite the package with fixed timestamps, so equal content is equal bytes."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            fixed = zipfile.ZipInfo(info.filename, date_time=_ZIP_EPOCH)
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = 0o644 << 16
            dst.writestr(fixed, src.read(info.filename))
    return out.getvalue()
