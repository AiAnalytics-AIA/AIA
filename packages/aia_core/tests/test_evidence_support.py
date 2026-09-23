"""Effective-n support, suppression by removal, and numbers that need an interval."""

from __future__ import annotations

import math

import pytest

from aia_core.domain.evidence import (
    REFERENCE_THRESHOLDS,
    Interval,
    ReportableEstimate,
    SupportAssessment,
    SupportEvidence,
    SupportStatus,
    UnsupportedEstimate,
    assess_support,
    kish_effective_n,
    suppress_cells,
    top2box_pct,
    weighted_mean,
    weighted_share_pct,
)


def test_reference_thresholds() -> None:
    t = REFERENCE_THRESHOLDS
    assert (t.min_cell, t.n_guard, t.indicative, t.min_layer_donors) == (50, 25.0, 50.0, 25)


def test_default_assessment_is_suppress() -> None:
    assert SupportAssessment().status is SupportStatus.SUPPRESS
    assert not SupportAssessment().reportable


@pytest.mark.parametrize("status", [SupportStatus.REPORTABLE, SupportStatus.INDICATIVE])
def test_a_reportable_status_cannot_be_written_by_hand(status: SupportStatus) -> None:
    """Only assess_support issues a status that lets a number reach a client."""
    with pytest.raises(UnsupportedEstimate, match="issued only by assess_support"):
        SupportAssessment(status)
    with pytest.raises(UnsupportedEstimate):
        SupportAssessment(status, (), 400.0, _issuer=object())


def test_suppress_may_be_stated_by_anyone() -> None:
    assert SupportAssessment(SupportStatus.SUPPRESS, ("cell removed",)).reasons == ("cell removed",)


@pytest.mark.parametrize(
    ("n", "eff", "status"),
    [
        (None, 80.0, SupportStatus.SUPPRESS),
        (100, None, SupportStatus.SUPPRESS),
        (100, math.nan, SupportStatus.SUPPRESS),
        (100, -1.0, SupportStatus.SUPPRESS),
        (-5, 3.0, SupportStatus.SUPPRESS),
        (49, 49.0, SupportStatus.SUPPRESS),  # below min_cell
        (500, 24.99, SupportStatus.SUPPRESS),  # below n_guard
        (500, 25.0, SupportStatus.INDICATIVE),
        (500, 49.99, SupportStatus.INDICATIVE),
        (50, 50.0, SupportStatus.REPORTABLE),
        (500, 312.5, SupportStatus.REPORTABLE),
        (40, 60.0, SupportStatus.SUPPRESS),  # effective n cannot exceed n
    ],
)
def test_support_decisions(n: int | None, eff: float | None, status: SupportStatus) -> None:
    assert assess_support(SupportEvidence(n=n, effective_n=eff)).status is status


@pytest.mark.parametrize(
    ("donors", "status"),
    [
        (None, SupportStatus.SUPPRESS),
        (24, SupportStatus.SUPPRESS),
        (25, SupportStatus.INDICATIVE),
        (49, SupportStatus.INDICATIVE),
        (50, SupportStatus.REPORTABLE),
    ],
)
def test_donor_layer_support(donors: int | None, status: SupportStatus) -> None:
    evidence = SupportEvidence(
        n=400, effective_n=300.0, requires_donor_support=True, n_unique_layer_donors=donors
    )
    assert assess_support(evidence).status is status


def test_suppression_reasons_are_all_kept() -> None:
    a = assess_support(SupportEvidence(n=10, effective_n=4.0))
    assert a.status is SupportStatus.SUPPRESS and len(a.reasons) == 2


def test_suppressed_cells_are_removed_not_greyed() -> None:
    result = suppress_cells(
        {
            "total": SupportEvidence(n=800, effective_n=610.0),
            "men_18_24": SupportEvidence(n=31, effective_n=22.0),
            "unknown": SupportEvidence(n=None, effective_n=None),
            "women_65_plus": SupportEvidence(n=120, effective_n=41.0),
        }
    )
    assert set(result.kept) == {"total", "women_65_plus"}
    assert set(result.removed) == {"men_18_24", "unknown"}
    assert result.kept["women_65_plus"].status is SupportStatus.INDICATIVE


# --- reportable estimates ------------------------------------------------------------


GOOD = assess_support(SupportEvidence(n=500, effective_n=400.0))


def test_reportable_estimate_needs_its_interval_and_support() -> None:
    est = ReportableEstimate(42.0, Interval(38.0, 46.0, 0.95), GOOD)
    assert est.interval.contains(42.0)
    with pytest.raises(UnsupportedEstimate, match="requires its interval"):
        ReportableEstimate(42.0, None, GOOD)  # type: ignore[arg-type]
    with pytest.raises(UnsupportedEstimate, match="suppressed"):
        ReportableEstimate(42.0, Interval(38.0, 46.0, 0.95), SupportAssessment())
    with pytest.raises(UnsupportedEstimate, match="outside"):
        ReportableEstimate(50.0, Interval(38.0, 46.0, 0.95), GOOD)
    with pytest.raises(UnsupportedEstimate, match="finite"):
        ReportableEstimate(math.inf, Interval(38.0, 46.0, 0.95), GOOD)


@pytest.mark.parametrize(
    ("lower", "upper", "level"),
    [(5.0, 4.0, 0.95), (1.0, 2.0, 1.0), (1.0, 2.0, 0.0), (math.nan, 2.0, 0.9)],
)
def test_invalid_intervals_are_refused(lower: float, upper: float, level: float) -> None:
    with pytest.raises(UnsupportedEstimate):
        Interval(lower, upper, level)


# --- estimators ---------------------------------------------------------------------------


def test_kish_effective_n() -> None:
    assert kish_effective_n([1.0] * 100) == pytest.approx(100.0)
    assert kish_effective_n([1.0, 3.0]) == pytest.approx(16.0 / 10.0)
    assert kish_effective_n([2.0, 0.0, 2.0]) == pytest.approx(2.0)


@pytest.mark.parametrize("weights", [[], [0.0, 0.0], [1.0, -1.0], [1.0, math.nan], [math.inf]])
def test_kish_refuses_weights_it_would_otherwise_have_to_clean(weights: list[float]) -> None:
    with pytest.raises(ValueError):
        kish_effective_n(weights)


def test_weighted_mean_skips_unanswered() -> None:
    assert weighted_mean([1.0, None, 3.0], [1.0, 5.0, 3.0]) == pytest.approx(2.5)
    assert weighted_mean([None, None], [1.0, 1.0]) is None
    assert weighted_mean([1.0], [0.0]) is None
    with pytest.raises(ValueError, match="weights"):
        weighted_mean([1.0], [1.0, 2.0])
    with pytest.raises(ValueError, match="finite"):
        weighted_mean([1.0], [-1.0])


def test_weighted_share_pct() -> None:
    assert weighted_share_pct([True, False, None], [3.0, 1.0, 9.0]) == pytest.approx(75.0)
    assert weighted_share_pct([None], [1.0]) is None


def test_top2box_pct() -> None:
    values: list[float | None] = [5.0, 4.0, 3.0, 1.0, None]
    assert top2box_pct(values, [1.0] * 5, scale_max=5) == pytest.approx(50.0)
    assert top2box_pct([10.0, 9.0, 8.0], [1.0, 1.0, 2.0], scale_max=10) == pytest.approx(50.0)
    with pytest.raises(ValueError, match="outside"):
        top2box_pct([6.0], [1.0], scale_max=5)
    with pytest.raises(ValueError, match="at least 2"):
        top2box_pct([1.0], [1.0], scale_max=1)
