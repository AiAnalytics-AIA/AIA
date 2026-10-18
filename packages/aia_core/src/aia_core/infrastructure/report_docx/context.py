"""The state one render carries: the Word document, the report, and its tallies.

One :class:`RenderContext` per :meth:`DocxRenderer.render` call. Everything a
block renderer needs is here, so a block renderer is a plain function of
``(ctx, container, block)`` and can be tested alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from docx.document import Document
from docx.text.paragraph import Paragraph

from aia_core.domain.report.evidence import EvidenceLedger
from aia_core.domain.report.model import ReportDocument
from aia_core.domain.report.outline import Outline
from aia_core.domain.report.validation import CLIENT_KINDS
from aia_core.infrastructure.report_docx.footnotes import Footnotes
from aia_core.infrastructure.report_docx.images import SvgParts
from aia_core.infrastructure.report_docx.marks import Marks
from aia_core.infrastructure.report_docx.numbering import Numbering
from aia_core.infrastructure.report_docx.ooxml import Bookmarks


class Container(Protocol):
    """Anything python-docx lets a paragraph or table be added to: body or cell."""

    def add_paragraph(self, text: str = "", style: str | None = None) -> Paragraph: ...


@dataclass(slots=True)
class RenderContext:
    document: Document
    report: ReportDocument
    outline: Outline
    bookmarks: Bookmarks
    footnotes: Footnotes
    numbering: Numbering
    svgs: SvgParts
    marks: Marks
    #: The section index and block index being rendered: the outline's key.
    position: tuple[int, int] = (0, 0)

    @property
    def ledger(self) -> EvidenceLedger:
        return self.report.ledger

    @property
    def client(self) -> bool:
        """A client deliverable: no internals, ever."""
        return self.report.meta.kind in CLIENT_KINDS
