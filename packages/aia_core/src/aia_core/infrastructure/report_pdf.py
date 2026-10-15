"""A stored DOCX report as PDF, through headless LibreOffice (complete-study-report B3).

The PDF is a rendering of the DOCX the report step stored, never a second composition:
the same bytes in, the same document out, so what a person approves (the DOCX) is what
the PDF shows. LibreOffice runs as a subprocess with a private profile per conversion, so a
stale lock or a concurrent conversion never blocks one, and with a timeout.

It ships behind ``AIA_REPORT_PDF_ENABLED`` (off when unset, CLAUDE.md § 8). Measured on the
four template samples (1.5 MB DOCX each, LibreOffice 24.2, cold profile): 1.8-2.0 s per
conversion, PDFs of 250-360 kB. On, the worker stops at start when ``soffice`` is missing
rather than storing reports that silently never get a PDF.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Protocol

REPORT_PDF_KEY: Final = "AIA_REPORT_PDF_ENABLED"
PDF_MEDIA_TYPE: Final = "application/pdf"
_TRUE: Final = {"1", "true", "yes", "on"}
_FALSE: Final = {"0", "false", "no", "off", ""}


class PdfConversionFailed(Exception):
    """The converter ran and produced no PDF."""


class PdfConverter(Protocol):
    """DOCX bytes -> PDF bytes. ``version`` names the converter in a PDF's fingerprint."""

    @property
    def version(self) -> str: ...

    def convert(self, docx: bytes) -> bytes: ...


class LibreOfficePdf:
    """Headless LibreOffice Writer, one subprocess per conversion."""

    def __init__(self, soffice: str, *, timeout_s: float = 120.0) -> None:
        self._soffice = soffice
        self._timeout_s = timeout_s
        found = subprocess.run(
            [soffice, "--version"], capture_output=True, text=True, timeout=60, check=False
        )
        self._version = found.stdout.strip() or "libreoffice (version not reported)"

    @property
    def version(self) -> str:
        return self._version

    def convert(self, docx: bytes) -> bytes:
        with tempfile.TemporaryDirectory(prefix="aia-pdf-") as work:
            root = Path(work)
            source = root / "report.docx"
            source.write_bytes(docx)
            profile = root / "profile"
            try:
                subprocess.run(
                    [
                        self._soffice,
                        f"-env:UserInstallation={profile.as_uri()}",
                        "--headless",
                        "--norestore",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        str(root),
                        str(source),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=self._timeout_s,
                )
            except subprocess.TimeoutExpired as exc:
                raise PdfConversionFailed(f"timed out after {self._timeout_s:.0f} s") from exc
            except subprocess.CalledProcessError as exc:
                raise PdfConversionFailed(f"exited {exc.returncode}") from exc
            pdf = root / "report.pdf"
            if not pdf.exists() or not pdf.read_bytes().startswith(b"%PDF"):
                raise PdfConversionFailed("no PDF written")
            return pdf.read_bytes()


def report_pdf_from_env(env: Mapping[str, str]) -> LibreOfficePdf | None:
    """The converter when ``AIA_REPORT_PDF_ENABLED`` is on, else None.

    A value that is neither true nor false, or the switch on without ``soffice`` on the
    PATH, stops the worker rather than being read as off.
    """
    raw = env.get(REPORT_PDF_KEY)
    value = (raw or "").strip().lower()
    if value in _FALSE:
        return None
    if value not in _TRUE:
        raise ValueError(f"{REPORT_PDF_KEY}={raw!r} is not true or false")
    soffice = shutil.which("soffice")
    if soffice is None:
        raise ValueError(f"{REPORT_PDF_KEY} is on and soffice is not installed")
    return LibreOfficePdf(soffice)
