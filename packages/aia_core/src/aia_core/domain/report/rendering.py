"""The seam between the report's rules and its bytes (pure).

The application layer renders a report through this protocol; the one
implementation is ``infrastructure.report_docx.DocxRenderer``. A renderer
validates the document itself, so a caller cannot hand it an unchecked one.
"""

from __future__ import annotations

from typing import Protocol

from aia_core.domain.report.model import ReportDocument


class ReportRenderer(Protocol):
    #: The media type of what :meth:`render` returns (DOCX, always, for now).
    media_type: str

    def render(self, doc: ReportDocument) -> bytes:
        """The document as a file. Raises ``ReportInvalid`` before writing anything."""
        ...
