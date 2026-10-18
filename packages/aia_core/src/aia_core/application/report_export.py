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
  served as stored, unstamped, and says so (``stamped`` false): never partly stamped, never
  a refusal of a file a person approved.

An artifact marked approved without its ledger row is refused by name
(:class:`ReviewUnrecorded`): the date it would print is not known, and is never guessed.
Routers reach the stamp only through here (the import ratchet in ``pyproject.toml``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from ..domain.report.review import (
    REVIEW_STAMP_CONTRACT,
    ReviewMark,
    ReviewState,
    approval_date,
)
from ..infrastructure.artifact_repository import Artifact, ArtifactRepository
from ..infrastructure.report_docx.review_stamp import NotStampable, stamp_review

__all__ = [
    "REVIEW_STAMP_RECORD",
    "Export",
    "ReviewUnrecorded",
    "export_docx",
    "review_mark",
    "stampable",
]

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


def stampable(artifact: Artifact) -> bool:
    """Whether the version states its status in its footers alone, as its writer recorded:
    once approved, its export says so there. False for every report stored before."""
    return all(artifact.metadata.get(k) == v for k, v in REVIEW_STAMP_RECORD.items())


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
    artifacts: ArtifactRepository, artifact: Artifact, *, data: bytes | None = None
) -> Export:
    """The file a download of ``artifact`` is. Reads the stored bytes verified (a corrupt
    version raises the store's error, as any read does) and stamps an approved version whose
    layout takes it; anything else is the stored bytes.

    ``data``: the version's bytes a caller has just read or stored (the client report, composed
    and stored on download), used instead of reading them again only when they are its bytes
    -- their SHA-256 is the version's. Any other bytes are not this version: the store is read."""
    mark = review_mark(artifacts, artifact)
    if data is None or hashlib.sha256(data).hexdigest() != artifact.sha256:
        data = artifacts.read(artifact.artifact_id)
    if mark.state is ReviewState.APPROVED and stampable(artifact):
        try:
            return Export(stamp_review(data, mark), mark, stamped=True)
        except NotStampable:
            pass  # recorded as stampable, laid out otherwise: served as stored, said so
    return Export(data, mark, stamped=False)
