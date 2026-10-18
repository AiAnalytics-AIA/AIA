"""A stored report version's review status, as its file states it (pure).

A **version** is one stored report DOCX: its artifact id and the SHA-256 it was stored with.
It is a draft until a person approves it (``ArtifactRepository.approve``, a row in the
approval ledger), and approval never changes the stored bytes. What a file says about its
status therefore lives in one place only, the footers (research-integrity-report D2): the
stored draft says "KONCEPT — NESCHVÁLENO" there, and the approved version's export is the
same bytes with only those footer words replaced by :func:`approved_words` -- the date and
the version, never who approved (the ledger keeps that).

The mark is decided once, from the ledger (``application.report_export.review_mark``): an
approval without its ledger row is refused, never stamped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Final
from zoneinfo import ZoneInfo

from aia_core.domain.report import numbers
from aia_core.domain.report.copy import t

__all__ = [
    "REVIEW_STAMP_CONTRACT",
    "REVIEW_TIMEZONE",
    "ReviewMark",
    "ReviewState",
    "approval_date",
    "approved_words",
]

#: What an approved export prints, and where: the footers' status runs replaced by
#: :func:`approved_words`. A change of either is a new contract, and a new approved PDF.
REVIEW_STAMP_CONTRACT: Final = "aia-review-stamp-1"

#: The date an approval prints is its ledger row's, on the calendar of the people who read it.
REVIEW_TIMEZONE: Final = "Europe/Prague"


class ReviewState(StrEnum):
    """A stored report's review, in the wire values the API has always sent."""

    DRAFT = "DRAFT_UNAPPROVED"
    APPROVED = "APPROVED_INTERNAL"


@dataclass(frozen=True, slots=True)
class ReviewMark:
    """What one stored report version is: a draft, or approved on ``approved_on``.

    ``approved_on`` is set exactly when the version is approved: an approval without a date
    is not one this code can print, and a draft has none.
    """

    state: ReviewState
    artifact_id: str
    sha256: str
    approved_on: date | None = None

    def __post_init__(self) -> None:
        if (self.state is ReviewState.APPROVED) != (self.approved_on is not None):
            raise ValueError("an approved version has its date, and a draft none")


def approval_date(decided_at: datetime) -> date:
    """The calendar day an approval recorded at ``decided_at`` was made, in Prague.

    A naive timestamp is refused: it names no moment, and a guessed zone can print the
    wrong day around midnight.
    """
    if decided_at.tzinfo is None:
        raise ValueError("an approval's time must be timezone-aware")
    return decided_at.astimezone(ZoneInfo(REVIEW_TIMEZONE)).date()


def approved_words(mark: ReviewMark) -> str:
    """The footer words of an approved version: ``SCHVÁLENO 18. 10. 2026 · verze ART-…``.

    One short line, beside the classification and the page number.
    """
    if mark.state is not ReviewState.APPROVED or mark.approved_on is None:
        raise ValueError("only an approved version is stamped")
    return (
        f"{t('approved')} {numbers.czech_short_date(mark.approved_on)}"
        f"{t('separator')}{t('version')} {mark.artifact_id}"
    )
