"""A stored report version as the file a person downloads (research-integrity-report D2).

A version is one stored report DOCX: its artifact id and SHA-256. Its review is decided here
once, from the ledger (:func:`review_mark`), and every download -- DOCX or PDF, the run's own
report, the report with a review, the client report -- states that one mark: in the
``X-AIA-Review-State`` the API sends and in the file itself.

* A **draft** exports its stored bytes, verified: its footers say "KONCEPT — NESCHVÁLENO".
* An **approved** version exports the same bytes with only the footers' status runs saying
  "SCHVÁLENO <date> · verze <id>" (``review_stamp.stamp_review``): every other byte is the
  version a person approved.
* An approved version stored before that layout (every report from before this release) is
  served as stored, unstamped, and says so: ``stamped`` false in its status, and its file
  named ``…-schvaleno-v-aia`` rather than ``…-schvaleno``. Never partly stamped, never a
  refusal of a file a person approved.

Whether a version takes the stamp is decided once, when it is stored: its writer records
:data:`REVIEW_STAMP_RECORD` only for bytes the stamp takes (:func:`review_stamp_record`), so
:func:`stampable`, read from that record alone, is what :func:`export_docx` does once the
version is approved -- the status says what the download is.

An artifact marked approved without its ledger row is refused by name
(:class:`ReviewUnrecorded`): the date it would print is not known, and is never guessed.
Routers reach the stamp only through here (the import ratchet in ``pyproject.toml``).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from types import MappingProxyType
from typing import Final

from ..domain.report.review import (
    REVIEW_STAMP_CONTRACT,
    ReviewMark,
    ReviewState,
    approval_date,
)
from ..infrastructure.artifact_repository import Artifact, ArtifactRepository
from ..infrastructure.report_docx.embed import reembed_fonts as embed_missing_fonts
from ..infrastructure.report_docx.review_stamp import NotStampable, stamp_review

__all__ = [
    "REVIEW_STAMP_RECORD",
    "Export",
    "ReviewUnrecorded",
    "export_docx",
    "exports_stamped",
    "review_mark",
    "review_stamp_record",
    "stampable",
]

_log = logging.getLogger("aia.report_export")

#: What a report writer records in a stored version's metadata: its renderer states the status
#: in the footers alone, one run each, the layout this stamp contract takes.
REVIEW_STAMP_RECORD: Final[Mapping[str, str]] = MappingProxyType(
    {"review_stamp": REVIEW_STAMP_CONTRACT}
)


class ReviewUnrecorded(Exception):
    """The artifact says it is approved and the approval ledger has no row for it."""

    def __init__(self, artifact_id: str) -> None:
        super().__init__(f"{artifact_id} is marked approved without its ledger row")
        self.artifact_id = artifact_id


@dataclass(frozen=True, slots=True)
class Export:
    """What a download of one version is: its bytes, its mark, and whether the bytes state an
    approval (only an approved version's stamped export does)."""

    data: bytes
    mark: ReviewMark
    stamped: bool
    #: The brand fonts were embedded again in these bytes (RPT15): they differ from the stored
    #: version's, which ``mark`` still names.
    fonts_reembedded: bool = False


#: A mark of no stored version, approved: what :func:`review_stamp_record` tries the stamp with.
_PROBE_VERSION: Final = "ART-0000000000000000"
_PROBE_DAY: Final = date(2000, 1, 1)


def review_stamp_record(docx: bytes) -> Mapping[str, str]:
    """What a report writer records beside the DOCX it stores: :data:`REVIEW_STAMP_RECORD`
    when the stamp takes these bytes -- tried once, here, as if they were approved -- else
    nothing. One more pass over the package per stored version, never per read: 170-200 ms
    (median of 5) on the executor journey's 2.07 MB reports, with and without literature
    (cross-review web#14: the record was written whatever the bytes, so a status could say
    "stamped" over a file the export served unstamped)."""
    probe = ReviewMark(
        ReviewState.APPROVED, _PROBE_VERSION, hashlib.sha256(docx).hexdigest(), _PROBE_DAY
    )
    try:
        stamp_review(docx, probe)
    except Exception as exc:  # a probe of a stranger's bytes (an editor save, RPT8c):
        # any failure -- NotStampable, a part lxml cannot parse, a member zipfile cannot
        # inflate -- means "not stampable", never a lost save. Its answer is only yes or no.
        # Logged by kind alone: nothing of the document is in the record.
        _log.info("review stamp probe refused the bytes", extra={"reason": type(exc).__name__})
        return MappingProxyType({})
    return REVIEW_STAMP_RECORD


#: Compositions whose body states the report's status although their writer recorded the
#: stamp: aia-contextual-report-5's literature chapter ended "Tato kapitola je součástí
#: interního neschváleného návrhu zprávy." (contextual_report.py:610 @ f58bfb8), which the
#: stamp, reading only the renderer's own status marks, does not see. A version of one is
#: exported as stored, like one from before the stamp layout -- never SCHVÁLENO in its footers
#: over that sentence (integration review of the cross-review fixes).
STATUS_IN_BODY: Final = frozenset({"aia-contextual-report-5"})


def stampable(artifact: Artifact) -> bool:
    """Whether the version states its status in its footers alone, as its writer recorded
    after trying the stamp on its bytes (:func:`review_stamp_record`): once approved, its
    export says so there. False for every report stored before, and for a composition whose
    body states its status (:data:`STATUS_IN_BODY`)."""
    return artifact.metadata.get("report_contract") not in STATUS_IN_BODY and all(
        artifact.metadata.get(k) == v for k, v in REVIEW_STAMP_RECORD.items()
    )


def exports_stamped(artifact: Artifact, mark: ReviewMark) -> bool:
    """Whether a download of the version is other bytes than it was stored as: approved, with
    a layout that takes the stamp. Otherwise -- a draft, or an approved version stored before
    the layout -- its export is its stored bytes, and the PDF rendered from those bytes renders
    its export, whatever its review was when it was rendered."""
    return mark.state is ReviewState.APPROVED and stampable(artifact)


def review_mark(artifacts: ArtifactRepository, artifact: Artifact) -> ReviewMark:
    """The one reading of a version's review: approved only when the artifact is and its
    ledger row exists (dated by that row, in Prague); otherwise a draft. Raises
    :class:`ReviewUnrecorded` for an approval without its row."""
    if not artifact.is_approved:
        return ReviewMark(ReviewState.DRAFT, artifact.artifact_id, artifact.sha256)
    decided = artifacts.approval_of(artifact.artifact_id)
    if decided is None:
        raise ReviewUnrecorded(artifact.artifact_id)
    return ReviewMark(
        ReviewState.APPROVED, artifact.artifact_id, artifact.sha256, approval_date(decided)
    )


def export_docx(
    artifacts: ArtifactRepository,
    artifact: Artifact,
    *,
    data: bytes | None = None,
    reembed_fonts: bool = False,
) -> Export:
    """The file a download of ``artifact`` is. Reads the stored bytes verified (a corrupt
    version raises the store's error, as any read does) and stamps an approved version whose
    layout takes it; anything else is the stored bytes.

    ``data``: the version's bytes a caller has just read or stored (the client report, composed
    and stored on download), used instead of reading them again only when they are its bytes
    -- their SHA-256 is the version's. Any other bytes are not this version: the store is read.

    ``reembed_fonts``: an editor-saved version, whose editor dropped the embedded brand fonts,
    downloads with them embedded again (artifact-report RPT15; the owner's B6 (b), 2026-10-26):
    the stored version, its SHA-256 and its approval are untouched, and ``fonts_reembedded``
    says the bytes differ from it. A package the fonts cannot be put back in is served as
    stored, and says nothing was re-embedded."""
    exported = _export_docx(artifacts, artifact, data)
    if not reembed_fonts:
        return exported
    try:
        carried = embed_missing_fonts(exported.data)
    except ValueError as exc:
        _log.warning("fonts not re-embedded in %s: %s", artifact.artifact_id, exc)
        return exported
    return exported if carried is None else replace(exported, data=carried, fonts_reembedded=True)


def _export_docx(artifacts: ArtifactRepository, artifact: Artifact, data: bytes | None) -> Export:
    mark = review_mark(artifacts, artifact)
    if data is None or hashlib.sha256(data).hexdigest() != artifact.sha256:
        data = artifacts.read(artifact.artifact_id)
    if mark.state is ReviewState.APPROVED and stampable(artifact):
        try:
            return Export(stamp_review(data, mark), mark, stamped=True)
        except NotStampable:
            # Recorded as stampable, laid out otherwise: a record its writer did not try
            # (review_stamp_record tries every one it writes). Served as stored, never partly
            # stamped; the download's name says it is not stamped (``stamped`` false), though a
            # status reading the record alone would not.
            pass
    return Export(data, mark, stamped=False)
