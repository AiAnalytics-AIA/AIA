"""What a report writer records about the stamp, and so what a version's status says.

Cross-review web#14: the record that a version takes the stamp was written whatever its bytes,
and the status's ``stamped`` read only that record, so the status could say an approved file
states SCHVÁLENO while the export, refused by the stamp, served it unstamped. The writer now
records it only for bytes the stamp takes.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import date
from typing import Any

import pytest
import report_samples

from aia_core.application.report_export import REVIEW_STAMP_RECORD, review_stamp_record
from aia_core.domain.report.review import ReviewMark, ReviewState, approved_words
from aia_core.infrastructure.report_docx.embed import reembed_fonts
from aia_core.infrastructure.report_docx.renderer import DocxRenderer, write_package
from aia_core.infrastructure.report_docx.review_stamp import stamp_review

DRAFT = "KONCEPT — NESCHVÁLENO"

_RENDERED: dict[str, bytes] = {}


@pytest.fixture
def samples(report_ledger: Any) -> dict[str, bytes]:
    if not _RENDERED:
        for kind in ("internal", "client"):
            _RENDERED[kind] = DocxRenderer().render(report_samples.build(kind, report_ledger))
    return _RENDERED


def _with_body(data: bytes, edit: Any) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        parts = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    return write_package((n, edit(b) if n == "word/document.xml" else b) for n, b in parts)


@pytest.mark.parametrize("kind", ["internal", "client"])
def test_a_report_laid_out_for_the_stamp_records_it(samples: dict[str, bytes], kind: str) -> None:
    assert review_stamp_record(samples[kind]) == REVIEW_STAMP_RECORD


def test_bytes_the_stamp_refuses_record_nothing(samples: dict[str, bytes]) -> None:
    # A body that states the draft status, as every version stored before the layout did.
    stated = _with_body(
        samples["client"],
        lambda b: b.replace("Stav této verze uvádí zápatí".encode(), DRAFT.encode()),
    )
    assert stated != samples["client"]
    assert dict(review_stamp_record(stated)) == {}
    # Not a package at all.
    assert dict(review_stamp_record(b"PK fictional bytes")) == {}


def test_an_approved_editor_saved_version_exports_stamped_with_its_fonts_back(
    samples: dict[str, bytes],
) -> None:
    """RPT15 (spec szz T7), in the order ``export_docx`` takes: the stamp on the stored bytes,
    then the fonts. The stamp still applies, every face the renderer embeds is back, and the
    body is the stored version's, byte for byte."""
    stored = report_samples.without_embedded_fonts(samples["internal"])
    mark = ReviewMark(
        ReviewState.APPROVED,
        "ART-0000000000000001",
        hashlib.sha256(stored).hexdigest(),
        date(2026, 10, 26),
    )
    stamped = stamp_review(stored, mark)
    exported = reembed_fonts(stamped)
    assert exported is not None
    with zipfile.ZipFile(io.BytesIO(exported)) as z, zipfile.ZipFile(io.BytesIO(stamped)) as before:
        footers = b"".join(z.read(n) for n in z.namelist() if n.startswith("word/footer"))
        assert approved_words(mark).encode() in footers
        assert any(n.startswith("word/fonts/") for n in z.namelist())
        assert z.read("word/document.xml") == before.read("word/document.xml")
