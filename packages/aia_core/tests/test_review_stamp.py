"""The approved export of a stored report version: its footers' status runs, and nothing else.

On real rendered sample reports (``report_samples``): a stamp leaves every part of the package
but the footers byte for byte as stored, changes each footer only where its status run's words
were, is deterministic and passes the lint. A document that states a status anywhere else --
every version stored before this layout -- is not stampable, never partly stamped.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import date
from typing import Any

import pytest
import report_samples
from docx import Document

from aia_core.domain.report.review import ReviewMark, ReviewState, approved_words
from aia_core.infrastructure.report_docx.lint import lint_docx
from aia_core.infrastructure.report_docx.renderer import DocxRenderer, write_package
from aia_core.infrastructure.report_docx.review_stamp import NotStampable, stamp_review

DRAFT = "KONCEPT \u2014 NESCHVÁLENO"
COVER = f"{DRAFT}. Tato verze dosud nebyla schválena. Nepředávejte ji jako finální."


def _mark(data: bytes, *, artifact_id: str = "ART-0123456789abcdef") -> ReviewMark:
    sha = hashlib.sha256(data).hexdigest()
    return ReviewMark(ReviewState.APPROVED, artifact_id, sha, date(2026, 10, 18))


def _infos(data: bytes) -> list[zipfile.ZipInfo]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.infolist()


def _parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def _footer(name: str) -> bool:
    return name.startswith("word/footer") and name.endswith(".xml")


#: The rendered samples, once per module: rendering is deterministic, and the slow part.
_RENDERED: dict[str, bytes] = {}


@pytest.fixture
def samples(report_ledger: Any) -> dict[str, bytes]:
    if not _RENDERED:
        for kind in ("internal", "client"):
            _RENDERED[kind] = DocxRenderer().render(report_samples.build(kind, report_ledger))
    return _RENDERED


@pytest.mark.parametrize("kind", ["internal", "client"])
def test_a_stamp_changes_only_the_status_runs_of_the_footers(
    samples: dict[str, bytes], kind: str
) -> None:
    stored = samples[kind]
    mark = _mark(stored)
    stamped = stamp_review(stored, mark)
    words = approved_words(mark)

    before, after = _infos(stored), _infos(stamped)
    assert [i.filename for i in after] == [i.filename for i in before]  # the stored order
    old, new = _parts(stored), _parts(stamped)
    footers = [n for n in old if _footer(n)]
    assert len(footers) >= 3  # cover, front matter, body
    for b, a in zip(before, after, strict=True):
        assert a.date_time == b.date_time == (1980, 1, 1, 0, 0, 0)
        if _footer(b.filename):
            continue
        # Every other part byte for byte, compressed alike.
        assert new[b.filename] == old[b.filename], b.filename
        assert (a.CRC, a.compress_size) == (b.CRC, b.compress_size), b.filename
    for name in footers:
        # Each footer changed exactly where its one status run's words were.
        said = COVER if COVER.encode() in old[name] else DRAFT
        assert old[name].count(said.encode()) == 1, name
        assert new[name] == old[name].replace(said.encode(), words.encode()), name
        assert DRAFT.encode() not in new[name]

    assert stamp_review(stored, mark) == stamped  # deterministic
    assert lint_docx(stamped) == []
    Document(io.BytesIO(stamped))  # Word's reader opens it


def test_an_approved_footer_reads_its_date_and_version_beside_the_classification(
    samples: dict[str, bytes],
) -> None:
    stored = samples["client"]
    stamped = stamp_review(stored, _mark(stored))
    document = Document(io.BytesIO(stamped))
    texts = [s.footer.paragraphs[0].text for s in document.sections]
    nb = "\u00a0"
    approved = f"SCHVÁLENO 18.{nb}10.{nb}2026 \u00b7 verze ART-0123456789abcdef"
    assert texts[0] == approved  # the cover: the status alone
    assert all(t.startswith(f"{approved} \u00b7 Důvěrné") for t in texts[1:])


def test_only_an_approved_mark_for_exactly_these_bytes_stamps(samples: dict[str, bytes]) -> None:
    stored = samples["client"]
    draft = ReviewMark(ReviewState.DRAFT, "ART-0123456789abcdef", _mark(stored).sha256)
    with pytest.raises(ValueError, match="only an approved"):
        stamp_review(stored, draft)
    with pytest.raises(ValueError, match="not version"):
        stamp_review(stored + b"\0", _mark(stored))


def _rewritten(data: bytes, edit: dict[str, Any]) -> bytes:
    """The package with some parts' bytes rewritten by ``edit[name](bytes)``."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        parts = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    return write_package((n, edit[n](b) if n in edit else b) for n, b in parts)


def test_a_version_stored_before_this_layout_is_not_stampable(samples: dict[str, bytes]) -> None:
    # The layout before research-integrity-report D2: the status style was "AIA Draft", and
    # the cover notice and the document control said draft in the body too.
    stored = samples["client"]
    footers = [n for n in _parts(stored) if _footer(n)]
    legacy = _rewritten(
        stored,
        {
            "word/styles.xml": lambda b: b.replace(b"AIA Status", b"AIA Draft").replace(
                b"AIAStatus", b"AIADraft"
            ),
            **{n: (lambda b: b.replace(b"AIAStatus", b"AIADraft")) for n in footers},
            "word/document.xml": lambda b: b.replace(
                "Stav této verze uvádí zápatí".encode(), DRAFT.encode()
            ),
        },
    )
    with pytest.raises(NotStampable):
        stamp_review(legacy, _mark(legacy))


@pytest.mark.parametrize(
    "edit",
    [
        # The status style is gone: nothing says which runs are the status.
        lambda parts: {"word/styles.xml": lambda b: b.replace(b"AIA Status", b"AIA Other")},
        # The body says draft, as the old cover notice did.
        lambda parts: {
            "word/document.xml": lambda b: b.replace(
                "Stav této verze uvádí zápatí".encode(), DRAFT.encode()
            )
        },
        # A footer with no status run.
        lambda parts: {
            next(n for n in parts if _footer(n)): lambda b: b.replace(b"AIAStatus", b"AIAOther")
        },
        # A footer with two: the stamp would have to choose.
        lambda parts: {
            next(n for n in parts if _footer(n)): lambda b: b.replace(
                b"</w:p>",
                b'<w:r><w:rPr><w:rStyle w:val="AIAStatus"/></w:rPr><w:t>x</w:t></w:r></w:p>',
            )
        },
    ],
    ids=["no-status-style", "status-in-body", "footer-without-status", "footer-with-two"],
)
def test_a_document_that_states_its_status_other_than_once_per_footer_is_not_stampable(
    samples: dict[str, bytes], edit: Any
) -> None:
    stored = samples["client"]
    broken = _rewritten(stored, edit(_parts(stored)))
    with pytest.raises(NotStampable):
        stamp_review(broken, _mark(broken))
