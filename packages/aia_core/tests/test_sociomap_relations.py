"""Relation transforms against golden fixtures F1-F3, plus their error paths, and the
audit's pair status (F3), checked against the chance band the audit prints.

Fixture values are serialised to ten decimals by the reference's fixture
builder, so "EXACT" (F1) means the branch decision is exact and each value
agrees to that serialisation; the NUMERICAL fixtures use their recorded
tolerance.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from aia_core.domain.sociomap.relations import (
    AmbiguousCoercion,
    CoercionBranch,
    PairStatus,
    RelationScaleError,
    coerce_relation_scale_1_10,
    coercion_branch,
    fisher_interval,
    ipsatize,
    mutual_relation_for_position,
    null_band,
    pair_status,
)

SERIALISATION = 1e-9  # the fixture builder rounds to 10 decimals


def _close(actual: Any, expected: Any, tol: float) -> None:
    assert len(actual) == len(expected)
    for a_row, e_row in zip(actual, expected, strict=True):
        for a, e in zip(a_row, e_row, strict=True):
            assert abs(a - e) <= tol, (a, e)


# --------------------------------------------------------------------- F1 --

F1_BRANCHES = {
    "already_1_10": CoercionBranch.CLIP_1_10,
    "correlation_pm1": CoercionBranch.CORRELATION_PM1,
    "out_of_range_clip": CoercionBranch.CLIP_1_10,
    "sentinels": CoercionBranch.CLIP_1_10,
    "similarity_0_1": CoercionBranch.SIMILARITY_0_1,
}


@pytest.mark.parametrize("case", sorted(F1_BRANCHES))
def test_f1_coercion_matches_the_reference(sociomap_fixture: Any, case: str) -> None:
    fixture = sociomap_fixture("F1")
    matrix = fixture["input"][case]
    assert coercion_branch(matrix) is F1_BRANCHES[case]
    _close(coerce_relation_scale_1_10(matrix), fixture["expected_output"][case], SERIALISATION)


def test_f1_covers_every_branch() -> None:
    assert set(F1_BRANCHES.values()) == set(CoercionBranch)


def test_coercion_preserves_direction() -> None:
    coerced = coerce_relation_scale_1_10([[0, 2, 9], [7, 0, 3], [4, 5, 0]])
    assert coerced[0][1] == 2.0 and coerced[1][0] == 7.0


def test_coercion_forces_the_diagonal_to_zero() -> None:
    coerced = coerce_relation_scale_1_10([[9, 2, 3], [4, 8, 5], [6, 7, 10]])
    assert [coerced[i][i] for i in range(3)] == [0.0, 0.0, 0.0]


def test_diagonal_does_not_decide_the_branch() -> None:
    # A diagonal of 7 would push a similarity matrix into the clip branch if it
    # were counted; the reference decides on off-diagonal cells only.
    assert coercion_branch([[7, 0.2, 0.3], [0.4, 7, 0.5], [0.6, 0.7, 7]]) is (
        CoercionBranch.SIMILARITY_0_1
    )


@pytest.mark.parametrize(
    "matrix",
    [[[0, 1], [1, 0]], [[0, 1, 2], [1, 0, 2]], [[0, 1, 2], [1, 0], [2, 1, 0]], []],
)
def test_coercion_refuses_small_or_non_square_matrices(matrix: Any) -> None:
    with pytest.raises(RelationScaleError):
        coerce_relation_scale_1_10(matrix)


def test_coercion_refuses_the_unrecovered_sentinel_order() -> None:
    # Finite cells say "similarity"; the substituted NaN (5.5) says "clip". The
    # two plausible orders give 2.8 or 1.0 for the 0.2 cell -- refuse, not guess.
    with pytest.raises(AmbiguousCoercion):
        coerce_relation_scale_1_10([[0, 0.2, math.nan], [0.3, 0, 0.5], [0.8, 0.4, 0]])


def test_all_non_finite_off_diagonal_is_not_ambiguous() -> None:
    nan, inf = math.nan, math.inf
    coerced = coerce_relation_scale_1_10([[0, nan, inf], [-inf, 0, nan], [inf, nan, 0]])
    assert coerced[0][1] == 5.5 and coerced[0][2] == 10.0 and coerced[1][0] == 1.0


def test_correlation_extremes_map_to_the_scale_ends() -> None:
    coerced = coerce_relation_scale_1_10([[0, -1, 1], [0.5, 0, -0.5], [0, 0, 0]])
    assert coerced[0][1] == 1.0 and coerced[0][2] == 10.0


# --------------------------------------------------------------------- F2 --


def test_f2_mutual_relation_matches_the_reference(sociomap_fixture: Any) -> None:
    fixture = sociomap_fixture("F2")
    _close(
        mutual_relation_for_position(fixture["input"]),
        fixture["expected_output"],
        max(fixture["tolerance"], SERIALISATION),
    )


def test_mutual_relation_is_symmetric_and_bounded() -> None:
    n = mutual_relation_for_position([[0, 1, 10], [10, 0, 4], [3, 8, 0]])
    for i in range(3):
        assert n[i][i] == 0.0
        for j in range(3):
            assert n[i][j] == n[j][i]
            assert 0.0 <= n[i][j] <= 1.0


def test_mutual_relation_uses_the_arithmetic_mean() -> None:
    # 1 -> 10 and 10 -> 1: mean 5.5, so (5.5 - 1) / 9 = 0.5 -- not a max, min or
    # geometric mean, each of which would give a different number.
    n = mutual_relation_for_position([[0, 1, 5], [10, 0, 5], [5, 5, 0]])
    assert n[0][1] == pytest.approx(0.5, abs=1e-15)


# --------------------------------------------------------------------- F3 --


def test_f3_ipsatization_matches_the_reference(sociomap_fixture: Any) -> None:
    fixture = sociomap_fixture("F3")
    columns = fixture["expected_output"]["columns"]
    # Column selection is the study contract's job; the fixture's objects are
    # the obj_ columns and dem_age is excluded.
    assert columns == sorted(c for c in fixture["input"] if c.startswith("obj_"))
    rows = list(zip(*(fixture["input"][c] for c in columns), strict=True))
    expected = list(zip(*(fixture["expected_output"]["values"][c] for c in columns), strict=True))
    _close(ipsatize(rows), expected, max(fixture["tolerance"], SERIALISATION))


def test_ipsatized_rows_sum_to_zero() -> None:
    for row in ipsatize([[1, 2, 9], [4, 4, 4], [10, 1, 3]]):
        assert abs(math.fsum(v for v in row if v is not None)) < 1e-12


def test_ipsatize_keeps_missing_cells_missing_and_excludes_them_from_the_mean() -> None:
    assert ipsatize([[2, None, 6]]) == ((-2.0, None, 2.0),)


def test_ipsatize_leaves_an_unobserved_row_unobserved() -> None:
    assert ipsatize([[None, None]]) == ((None, None),)


# ------------------------------------------------------- pair status (F3) --
#
# The audit "NPC Sociomapa: faulty formulas in the code", F3: a pair with too few
# raters is UNKNOWN, never a medium relation. Its printed chance band is the
# check: +-0.88 at N = 5, +-0.36 at N = 30.


def test_the_chance_band_is_the_audits() -> None:
    assert null_band(5, 0.95) == pytest.approx(0.88, abs=0.005)
    assert null_band(30, 0.95) == pytest.approx(0.36, abs=0.005)
    assert null_band(3, 0.95) is None  # no standard error below four raters


def test_the_fisher_interval_is_symmetric_on_the_z_scale() -> None:
    low, high = fisher_interval(0.5, 30, 0.95) or (math.nan, math.nan)
    assert low < 0.5 < high
    assert math.atanh(0.5) - math.atanh(low) == pytest.approx(math.atanh(high) - math.atanh(0.5))
    assert math.atanh(high) - math.atanh(0.5) == pytest.approx(1.959964 / math.sqrt(27), rel=1e-6)


def test_a_perfect_correlation_is_its_own_interval() -> None:
    assert fisher_interval(1.0, 10, 0.95) == (1.0, 1.0)
    assert fisher_interval(-1.0, 10, 0.95) == (-1.0, -1.0)
    assert pair_status(-1.0, 30, 30, 0.95) is PairStatus.RELIABLE


def test_the_fisher_interval_needs_four_raters() -> None:
    assert fisher_interval(0.9, 3, 0.95) is None
    assert fisher_interval(0.9, 4, 0.95) is not None


def test_below_n_min_a_pair_is_unknown_whatever_its_number_says() -> None:
    assert pair_status(0.99, 29, 30, 0.95) is PairStatus.UNKNOWN
    assert pair_status(0.0, 4, 30, 0.95) is PairStatus.UNKNOWN


def test_a_pair_without_a_correlation_is_unknown() -> None:
    assert pair_status(None, 500, 30, 0.95) is PairStatus.UNKNOWN


@pytest.mark.parametrize(
    ("r", "n", "expected"),
    [
        (0.5, 30, PairStatus.RELIABLE),  # band at 30 is 0.36
        (-0.5, 30, PairStatus.RELIABLE),  # the sign does not matter
        (0.3, 30, PairStatus.WEAK),
        (0.3, 100, PairStatus.RELIABLE),  # more raters, narrower band
        (0.0, 1000, PairStatus.WEAK),
    ],
)
def test_reliable_means_the_interval_excludes_zero(r: float, n: int, expected: PairStatus) -> None:
    assert pair_status(r, n, 30, 0.95) is expected
    band = null_band(n, 0.95)
    assert band is not None and (abs(r) > band) is (expected is PairStatus.RELIABLE)


@pytest.mark.parametrize("n_min", [0, 3, True])
def test_n_min_must_leave_room_for_a_standard_error(n_min: Any) -> None:
    with pytest.raises(ValueError, match="n_min"):
        pair_status(0.5, 50, n_min, 0.95)


@pytest.mark.parametrize("confidence", [0.0, 1.0, -0.5, 1.5, True])
def test_confidence_must_be_a_probability(confidence: Any) -> None:
    with pytest.raises(ValueError, match="confidence"):
        pair_status(0.5, 50, 30, confidence)
    with pytest.raises(ValueError, match="confidence"):
        null_band(50, confidence)


@pytest.mark.parametrize("r", [1.5, -1.01, math.nan, math.inf, True])
def test_a_correlation_outside_minus_one_to_one_is_refused(r: Any) -> None:
    with pytest.raises(ValueError, match="correlation"):
        pair_status(r, 50, 30, 0.95)


@pytest.mark.parametrize("n", [-1, True])
def test_a_rater_count_is_a_count(n: Any) -> None:
    with pytest.raises(ValueError, match="raters"):
        pair_status(0.5, n, 30, 0.95)
