"""Audit F6: objects placed alone on a fixed ruler, sqrt(2 (1 - r)), by weighted SMACOF.

Plan ``sociomap-formula-corrections`` chunk 2b. The unit measured every target against the
family's strongest pair and stretched the map to a fixed radius, so a barely related family
looked as structured as a strong one. Here one map unit is one unit of correlation distance
everywhere, an UNKNOWN pair pulls nothing, and the map says how well it fits (Stress-1).
"""

from __future__ import annotations

import itertools
import math
import random

import pytest

from aia_core.domain.sociomap.layout import (
    CORRELATION_DISTANCE_MAX,
    UnfoldingDesignError,
    correlation_distance,
    correlation_distances,
    fit_smacof_objects,
)

FIT = {"max_iterations": 5000, "tolerance": 1e-12}


def _dist(p: tuple[float, float], q: tuple[float, float]) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _planted(m: int, seed: int) -> list[tuple[float, float]]:
    rng = random.Random(seed)
    return [(rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0)) for _ in range(m)]


def _correlations(m: int, low: float, high: float, seed: int) -> list[list[float | None]]:
    rng = random.Random(seed)
    r: list[list[float | None]] = [[1.0 if i == j else None for j in range(m)] for i in range(m)]
    for i in range(m):
        for j in range(i + 1, m):
            r[i][j] = r[j][i] = rng.uniform(low, high)
    return r


def _all_known(m: int) -> list[list[bool]]:
    return [[i != j for j in range(m)] for i in range(m)]


def test_the_ruler_is_the_distance_between_standardised_variables() -> None:
    """Audit F6 (p. 8): 0 identical, sqrt 2 = 1.41 unrelated, 2 opposite."""
    assert correlation_distance(1.0) == 0.0
    assert correlation_distance(0.0) == pytest.approx(math.sqrt(2.0))
    assert correlation_distance(-1.0) == CORRELATION_DISTANCE_MAX == 2.0
    for bad in (1.2, -1.01, math.nan):
        with pytest.raises(ValueError):
            correlation_distance(bad)


def test_a_planted_configuration_is_recovered_exactly() -> None:
    points = _planted(8, seed=5)
    delta = [[_dist(p, q) for q in points] for p in points]
    layout = fit_smacof_objects(delta, **FIT)
    assert layout.stress_1 < 1e-4 and layout.converged
    for i in range(8):
        for j in range(8):
            assert _dist(layout.points[i], layout.points[j]) == pytest.approx(delta[i][j], abs=1e-6)


def test_the_map_is_never_stretched_to_a_radius() -> None:
    """Objects whose correlations are cos(a - b) are chords of the unit circle: the fixed
    ruler puts them on radius 1 exactly, where the unit would have stretched to 38."""
    m = 12
    angles = [2.0 * math.pi * k / m for k in range(m)]
    r = [[max(-1.0, min(1.0, math.cos(a - b))) for b in angles] for a in angles]
    layout = fit_smacof_objects(correlation_distances(r, _all_known(m)), **FIT)
    assert layout.stress_1 < 1e-6
    assert [math.hypot(*p) for p in layout.points] == pytest.approx([1.0] * m, abs=1e-6)


def test_a_family_without_structure_keeps_its_size_and_says_so() -> None:
    """Audit F6 [C4/P4]: a weak family's targets crowd near sqrt 2 and cannot be drawn in 2D
    (the audit's run: Stress-1 0.307). Here twelve objects with r in [-0.09, 0.08]: the
    stress is in the audit's "2D picture unreliable" band, every target is near 1.41, and
    the map is not stretched to look like a strong family."""
    m = 12
    weak = fit_smacof_objects(
        correlation_distances(_correlations(m, -0.09, 0.08, 3), _all_known(m)), **FIT
    )
    strong_r = _correlations(m, -0.82, 0.59, 3)
    strong = fit_smacof_objects(correlation_distances(strong_r, _all_known(m)), **FIT)
    assert weak.stress_1 >= 0.20
    weak_targets = [
        correlation_distance(v)
        for i, row in enumerate(_correlations(m, -0.09, 0.08, 3))
        for j, v in enumerate(row)
        if i < j and v is not None
    ]
    assert min(weak_targets) > 1.34 and max(weak_targets) < 1.48
    # The fixed ruler keeps the two families' sizes apart; a stretch would make them equal.
    weak_radius = max(math.hypot(*p) for p in weak.points)
    strong_radius = max(math.hypot(*p) for p in strong.points)
    assert weak_radius < strong_radius


def test_an_unknown_pair_pulls_nothing() -> None:
    """Audit F3 + F6: w = 0 for an UNKNOWN pair. Whatever its correlation reads, the map is
    the same, and the stress is computed over the known pairs only."""
    m = 6
    r = _correlations(m, -0.6, 0.7, 11)
    known = _all_known(m)
    known[0][3] = known[3][0] = False
    first = fit_smacof_objects(correlation_distances(r, known), **FIT)
    r[0][3] = r[3][0] = -0.99  # what an UNKNOWN pair's number says changes nothing
    second = fit_smacof_objects(correlation_distances(r, known), **FIT)
    assert first.points == second.points and first.stress_1 == second.stress_1
    assert first.known_pairs == m * (m - 1) // 2 - 1
    assert first.start_fill is not None


def test_each_iteration_never_raises_the_stress() -> None:
    m = 9
    delta = correlation_distances(_correlations(m, -0.7, 0.8, 21), _all_known(m))
    raws = [
        fit_smacof_objects(delta, max_iterations=k, tolerance=1e-15).raw_stress
        for k in (1, 2, 4, 8, 16, 32)
    ]
    assert all(b <= a + 1e-12 for a, b in itertools.pairwise(raws))


def test_the_same_input_gives_the_same_bits() -> None:
    delta = correlation_distances(_correlations(10, -0.5, 0.9, 8), _all_known(10))
    assert fit_smacof_objects(delta, **FIT) == fit_smacof_objects(delta, **FIT)


def test_objects_with_no_chain_of_known_pairs_are_refused() -> None:
    m = 5
    r = _correlations(m, -0.5, 0.5, 2)
    known = _all_known(m)
    for j in range(m):
        if j != 4:
            known[4][j] = known[j][4] = False
    with pytest.raises(UnfoldingDesignError, match=r"\[4\]"):
        fit_smacof_objects(correlation_distances(r, known), **FIT)


@pytest.mark.parametrize(
    "delta",
    [
        [[0.0, 1.0], [1.0, 0.0]],  # two objects
        [[0.0, 1.0, 1.0], [2.0, 0.0, 1.0], [1.0, 1.0, 0.0]],  # asymmetric
        [[0.0, -1.0, 1.0], [-1.0, 0.0, 1.0], [1.0, 1.0, 0.0]],  # negative
    ],
)
def test_a_target_matrix_that_is_not_one_is_refused(delta: list[list[float | None]]) -> None:
    with pytest.raises((ValueError, UnfoldingDesignError)):
        fit_smacof_objects(delta, **FIT)


def test_a_known_pair_without_a_correlation_is_refused() -> None:
    r: list[list[float | None]] = [[1.0, None, 0.2], [None, 1.0, 0.3], [0.2, 0.3, 1.0]]
    with pytest.raises(ValueError, match="no correlation"):
        correlation_distances(r, _all_known(3))
