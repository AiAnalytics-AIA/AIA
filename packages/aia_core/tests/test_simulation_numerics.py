"""Numerical primitives: transforms, weighted statistics, eigen, nearest correlation, RNG."""

from __future__ import annotations

import math
import statistics

import pytest

from aia_core.domain.simulation.numerics import (
    NEAREST_CORRELATION_ALGORITHM,
    RNG_ALGORITHM,
    NotPositiveDefinite,
    clip,
    correlation_factor,
    logit,
    nearest_correlation,
    sigmoid,
    standard_normal,
    symmetric_eigen,
    uniform_open,
    weighted_correlation,
    weighted_mean,
    weighted_sd,
)


def _matmul_t(f: tuple[tuple[float, ...], ...]) -> list[list[float]]:
    n = len(f)
    return [[math.fsum(f[i][k] * f[j][k] for k in range(n)) for j in range(n)] for i in range(n)]


# --- Transforms -------------------------------------------------------------------------


def test_clip_and_its_inverted_bounds() -> None:
    assert clip(5.0, 1.0, 3.0) == 3.0
    assert clip(-1.0, 1.0, 3.0) == 1.0
    assert clip(2.0, 1.0, 3.0) == 2.0
    with pytest.raises(ValueError):
        clip(1.0, 3.0, 1.0)


@pytest.mark.parametrize("p", [0.001, 0.2, 0.5, 0.8, 0.999])
def test_logit_inverts_sigmoid(p: float) -> None:
    assert sigmoid(logit(p)) == pytest.approx(p, abs=1e-15)


@pytest.mark.parametrize("p", [0.0, 1.0, -0.1, 1.1])
def test_logit_refuses_rather_than_clips(p: float) -> None:
    with pytest.raises(ValueError):
        logit(p)


def test_sigmoid_is_stable_at_extremes() -> None:
    assert sigmoid(0.0) == 0.5
    assert sigmoid(800.0) == 1.0
    assert sigmoid(-800.0) == 0.0
    assert sigmoid(-30.0) == pytest.approx(math.exp(-30.0), rel=1e-12)


# --- Weighted statistics ------------------------------------------------------------------


def test_weighted_mean_and_sd_match_an_expanded_sample() -> None:
    values = [1.0, 2.0, 4.0]
    weights = [1.0, 2.0, 3.0]
    expanded = [1.0, 2.0, 2.0, 4.0, 4.0, 4.0]
    assert weighted_mean(values, weights) == pytest.approx(statistics.fmean(expanded))
    assert weighted_sd(values, weights) == pytest.approx(statistics.pstdev(expanded))


def test_weighted_statistics_refuse_a_zero_total() -> None:
    with pytest.raises(ValueError, match="positive total"):
        weighted_mean([1.0, 2.0], [0.0, 0.0])
    with pytest.raises(ValueError):
        weighted_mean([1.0], [1.0, 2.0])


def test_weighted_correlation_is_none_for_a_constant_column() -> None:
    w = [1.0, 1.0, 1.0]
    assert weighted_correlation([1.0, 2.0, 3.0], [2.0, 4.0, 6.0], w) == pytest.approx(1.0)
    assert weighted_correlation([1.0, 2.0, 3.0], [3.0, 2.0, 1.0], w) == pytest.approx(-1.0)
    assert weighted_correlation([1.0, 2.0, 3.0], [5.0, 5.0, 5.0], w) is None


# --- Eigen ----------------------------------------------------------------------------------


def test_symmetric_eigen_reconstructs_the_matrix() -> None:
    m = [[4.0, 1.0, 0.5], [1.0, 3.0, 0.2], [0.5, 0.2, 2.0]]
    values, vectors = symmetric_eigen(m)
    assert list(values) == sorted(values)
    for i in range(3):
        for j in range(3):
            recon = math.fsum(values[k] * vectors[k][i] * vectors[k][j] for k in range(3))
            assert recon == pytest.approx(m[i][j], abs=1e-12)
    for k in range(3):
        assert math.fsum(x * x for x in vectors[k]) == pytest.approx(1.0, abs=1e-12)
        assert max(vectors[k], key=abs) > 0  # sign convention


def test_symmetric_eigen_known_values() -> None:
    values, _ = symmetric_eigen([[2.0, 1.0], [1.0, 2.0]])
    assert values == pytest.approx((1.0, 3.0), abs=1e-14)


@pytest.mark.parametrize(
    "bad",
    [[], [[1.0, 2.0]], [[1.0, 2.0], [3.0, 1.0]], [[float("nan"), 0.0], [0.0, 1.0]]],
)
def test_symmetric_eigen_refuses_bad_input(bad: list[list[float]]) -> None:
    with pytest.raises(ValueError):
        symmetric_eigen(bad)


# --- Nearest correlation ---------------------------------------------------------------------


def test_valid_correlation_matrix_is_left_unchanged() -> None:
    m = [[1.0, 0.3, -0.2], [0.3, 1.0, 0.1], [-0.2, 0.1, 1.0]]
    result = nearest_correlation(m)
    assert result.adjustment == pytest.approx(0.0, abs=1e-10)
    for i in range(3):
        for j in range(3):
            assert result.matrix[i][j] == pytest.approx(m[i][j], abs=1e-10)


def test_infeasible_proposal_is_projected_to_a_valid_matrix() -> None:
    """Pairwise-plausible, jointly impossible: +.65, +.65 and -.65 around a triangle."""
    m = [[1.0, 0.65, 0.65], [0.65, 1.0, -0.65], [0.65, -0.65, 1.0]]
    assert symmetric_eigen(m)[0][0] < 0  # the proposal is not PSD
    result = nearest_correlation(m)
    values, _ = symmetric_eigen(result.matrix)
    assert values[0] >= -1e-10
    assert all(result.matrix[i][i] == 1.0 for i in range(3))
    assert result.adjustment > 0.01


def test_correlation_factor_reproduces_its_matrix_exactly_on_the_diagonal() -> None:
    m = [[1.0, 0.65, 0.65], [0.65, 1.0, -0.65], [0.65, -0.65, 1.0]]
    cf = correlation_factor(m)
    assert cf.algorithm == NEAREST_CORRELATION_ALGORITHM
    implied = _matmul_t(cf.factor)
    for i in range(3):
        assert implied[i][i] == pytest.approx(1.0, abs=1e-15)
        for j in range(3):
            assert implied[i][j] == pytest.approx(cf.matrix[i][j], abs=1e-12)
    assert cf.proposed == tuple(tuple(r) for r in m)
    assert cf.min_eigenvalue >= -1e-10


def test_nearest_correlation_refuses_a_non_unit_diagonal() -> None:
    with pytest.raises(ValueError, match="unit diagonal"):
        nearest_correlation([[2.0, 0.0], [0.0, 1.0]])


def test_nearest_correlation_fails_closed_when_it_cannot_converge() -> None:
    m = [[1.0, 0.65, 0.65], [0.65, 1.0, -0.65], [0.65, -0.65, 1.0]]
    with pytest.raises(NotPositiveDefinite):
        nearest_correlation(m, max_iter=1)


def test_projection_is_deterministic() -> None:
    m = [[1.0, 0.6, -0.6], [0.6, 1.0, 0.65], [-0.6, 0.65, 1.0]]
    assert correlation_factor(m) == correlation_factor(m)


# --- Counter-based RNG ------------------------------------------------------------------------


def test_uniform_is_open_and_deterministic() -> None:
    draws = [uniform_open(20260816, "r1", k) for k in range(2000)]
    assert all(0.0 < u < 1.0 for u in draws)
    assert draws == [uniform_open(20260816, "r1", k) for k in range(2000)]
    assert statistics.fmean(draws) == pytest.approx(0.5, abs=0.03)


def test_draw_depends_on_every_key() -> None:
    base = standard_normal(1, "row", 0)
    assert standard_normal(2, "row", 0) != base
    assert standard_normal(1, "other", 0) != base
    assert standard_normal(1, "row", 1) != base


def test_standard_normal_is_roughly_standard() -> None:
    xs = [standard_normal(7, "row", i) for i in range(4000)]
    assert statistics.fmean(xs) == pytest.approx(0.0, abs=0.06)
    assert statistics.pstdev(xs) == pytest.approx(1.0, abs=0.05)


def test_rng_output_is_pinned() -> None:
    """Changing the RNG must change RNG_ALGORITHM; this pins version 1's output exactly.

    SHA-256 and integer arithmetic make the uniform bit-exact on every platform.
    The normal quantile goes through ``math.log``, so it is pinned to 1e-15.
    """
    assert RNG_ALGORITHM == "sha256-counter-inv-normal-v1"
    assert uniform_open(20260816, "r00000", 0) == 0.8229246875237048
    assert standard_normal(20260816, "r00000", 0) == pytest.approx(0.9265684831262635, abs=1e-15)
