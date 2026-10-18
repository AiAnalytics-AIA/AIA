"""A report version's review mark and the words its approved export prints (D2)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from aia_core.domain.report.review import (
    REVIEW_TIMEZONE,
    ReviewMark,
    ReviewState,
    approval_date,
    approved_words,
)

NB = "\u00a0"
SHA = "a" * 64


def test_the_states_keep_the_wire_values_the_api_has_always_sent() -> None:
    assert ReviewState.DRAFT.value == "DRAFT_UNAPPROVED"
    assert ReviewState.APPROVED.value == "APPROVED_INTERNAL"


def test_an_approved_mark_has_its_date_and_a_draft_none() -> None:
    ReviewMark(ReviewState.DRAFT, "ART-0123456789abcdef", SHA)
    ReviewMark(ReviewState.APPROVED, "ART-0123456789abcdef", SHA, date(2026, 10, 18))
    with pytest.raises(ValueError, match="its date"):
        ReviewMark(ReviewState.APPROVED, "ART-0123456789abcdef", SHA)
    with pytest.raises(ValueError, match="its date"):
        ReviewMark(ReviewState.DRAFT, "ART-0123456789abcdef", SHA, date(2026, 10, 18))


def test_the_approved_words_name_the_date_and_the_version_on_one_line() -> None:
    mark = ReviewMark(ReviewState.APPROVED, "ART-0123456789abcdef", SHA, date(2026, 10, 8))
    words = approved_words(mark)
    assert words == f"SCHVÁLENO 8.{NB}10.{NB}2026 \u00b7 verze ART-0123456789abcdef"
    assert "\n" not in words and len(words) < 60
    with pytest.raises(ValueError, match="only an approved"):
        approved_words(ReviewMark(ReviewState.DRAFT, "ART-0123456789abcdef", SHA))


def test_an_approval_is_dated_on_the_prague_calendar() -> None:
    # Pinned: the ledger's UTC moment, read in Prague. 22:30 UTC on 17 October 2026 is
    # 00:30 on the 18th in Prague (summer time, UTC+2), and the 18th is printed.
    assert REVIEW_TIMEZONE == "Europe/Prague"
    assert approval_date(datetime(2026, 10, 17, 22, 30, tzinfo=UTC)) == date(2026, 10, 18)
    assert approval_date(datetime(2026, 10, 17, 21, 59, tzinfo=UTC)) == date(2026, 10, 17)
    # Winter time (UTC+1): 23:30 UTC on 31 December is New Year's Day in Prague.
    assert approval_date(datetime(2026, 12, 31, 23, 30, tzinfo=UTC)) == date(2027, 1, 1)
    # Any aware moment reads the same; a naive one names no moment and is refused.
    elsewhere = datetime(2026, 10, 17, 18, 30, tzinfo=timezone(timedelta(hours=-4)))
    assert approval_date(elsewhere) == date(2026, 10, 18)
    with pytest.raises(ValueError, match="timezone-aware"):
        approval_date(datetime(2026, 10, 17, 22, 30))
