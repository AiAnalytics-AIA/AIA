"""The DOCX -> PDF converter and its switch (complete-study-report B3).

The converter is exercised over a stand-in ``soffice``: a script that behaves as LibreOffice
does at its command line (``--version``; ``--convert-to pdf --outdir <dir> <file>`` writing
``<dir>/<stem>.pdf``), so every outcome runs everywhere without LibreOffice installed.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from aia_core.infrastructure.report_pdf import (
    LibreOfficePdf,
    PdfConversionFailed,
    report_pdf_from_env,
)

_SCRIPT = """#!/usr/bin/env python3
import sys, pathlib, time
args = sys.argv[1:]
if args == ["--version"]:
    print("LibreOffice 99.1 stand-in")
    sys.exit(0)
mode = {mode!r}
if mode == "fail":
    sys.exit(1)
if mode == "slow":
    time.sleep(5)
out = pathlib.Path(args[args.index("--outdir") + 1])
source = pathlib.Path(args[-1])
assert any(a.startswith("-env:UserInstallation=file://") for a in args)
if mode == "ok":
    (out / (source.stem + ".pdf")).write_bytes(b"%PDF-1.7 " + source.read_bytes())
elif mode == "garbage":
    (out / (source.stem + ".pdf")).write_bytes(b"not a pdf")
"""


def _soffice(tmp_path: Path, mode: str) -> str:
    script = tmp_path / f"soffice-{mode}"
    script.write_text(_SCRIPT.format(mode=mode))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_a_conversion_returns_the_pdf_the_converter_wrote_and_names_its_version(
    tmp_path: Path,
) -> None:
    converter = LibreOfficePdf(_soffice(tmp_path, "ok"))
    assert converter.version == "LibreOffice 99.1 stand-in"
    assert converter.convert(b"PK docx bytes") == b"%PDF-1.7 PK docx bytes"


@pytest.mark.parametrize("mode", ["fail", "none", "garbage"])
def test_a_converter_that_writes_no_pdf_fails_by_name(tmp_path: Path, mode: str) -> None:
    with pytest.raises(PdfConversionFailed):
        LibreOfficePdf(_soffice(tmp_path, mode)).convert(b"PK")


def test_a_conversion_that_hangs_is_stopped_at_its_timeout(tmp_path: Path) -> None:
    converter = LibreOfficePdf(_soffice(tmp_path, "slow"), timeout_s=0.5)
    with pytest.raises(PdfConversionFailed, match="timed out"):
        converter.convert(b"PK")


def test_the_switch_is_off_unless_said_and_on_needs_soffice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert report_pdf_from_env({}) is None
    assert report_pdf_from_env({"AIA_REPORT_PDF_ENABLED": "false"}) is None
    with pytest.raises(ValueError, match="not true or false"):
        report_pdf_from_env({"AIA_REPORT_PDF_ENABLED": "maybe"})
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ValueError, match="soffice is not installed"):
        report_pdf_from_env({"AIA_REPORT_PDF_ENABLED": "true"})
    (tmp_path / "soffice").write_text(_SCRIPT.format(mode="ok"))
    (tmp_path / "soffice").chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    converter = report_pdf_from_env({"AIA_REPORT_PDF_ENABLED": "on"})
    assert converter is not None and converter.version == "LibreOffice 99.1 stand-in"
