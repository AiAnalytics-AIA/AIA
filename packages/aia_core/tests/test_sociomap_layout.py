"""Declared layout algorithms: fail-closed legacy ids and ``aia_rowcond_unfolding_v1``.

``aia_rowcond_unfolding_v1`` makes no parity claim, so these tests pin what an
unfolding must do regardless of whose it is: recover a geometry that generated
the data, never increase stress, give the same bits twice, absorb per-row scale
use (the "row-conditional" in its name), and fix its gauge. Its golden fixture on
F4's input lives with the artifact tests.
"""

from __future__ import annotations

import itertools
import math
import random
from typing import Any

import pytest

from aia_core.domain.sociomap.layout import (
    LAYOUT_ALGORITHMS,
    AlgorithmStatus,
    LayoutAlgorithm,
    LayoutUnavailable,
    UnfoldingDesignError,
    UnfoldingParameters,
    fit_rowcond_unfolding,
    procrustes_align,
    require_layout_algorithm,
    scale_top_dissimilarity,
    stress_1,
)

TIGHT = UnfoldingParameters(dimensions=2, max_iterations=5000, convergence_tolerance=1e-13)


def _planted(n: int, m: int, seed: int, *, row_scales: bool, missing: bool) -> dict[str, Any]:
    rnd = random.Random(seed)
    objects = [(rnd.uniform(-3, 3), rnd.uniform(-3, 3)) for _ in range(m)]
    people = [(rnd.uniform(-3, 3), rnd.uniform(-3, 3)) for _ in range(n)]
    delta: list[list[float | None]] = []
    for p in people:
        s = rnd.uniform(0.4, 2.5) if row_scales else 1.0
        delta.append([s * math.hypot(p[0] - o[0], p[1] - o[1]) for o in objects])
    if missing:
        for row in delta:
            row[rnd.randrange(m)] = None
    return {"objects": objects, "people": people, "delta": delta}


# --------------------------------------------------------------- registry --


def test_the_implemented_algorithms_are_the_unfolding_and_the_object_map() -> None:
    # aia_smacof_objects_v1 is contract 3's object layout; contract 2 refuses it by name
    # (test_sociomap_object_map.py::test_contract_2_refuses_contract_3s_members).
    implemented = [
        a for a, i in LAYOUT_ALGORITHMS.items() if i.status is AlgorithmStatus.IMPLEMENTED
    ]
    assert implemented == [
        LayoutAlgorithm.AIA_ROWCOND_UNFOLDING_V1,
        LayoutAlgorithm.AIA_SMACOF_OBJECTS_V1,
    ]
    assert set(LAYOUT_ALGORITHMS) == set(LayoutAlgorithm)


@pytest.mark.parametrize(
    ("algorithm", "cause"),
    [
        ("python_weighted_unfolding", "REF-WITHHELD-REFERENCE-ARCHIVE"),
        ("r_smacof_unfolding", "REF-GAP-SOCIO-R-SMACOF"),
    ],
)
def test_legacy_algorithms_fail_closed_and_say_why(algorithm: str, cause: str) -> None:
    with pytest.raises(LayoutUnavailable, match=cause) as caught:
        require_layout_algorithm(algorithm)
    assert "no other algorithm is substituted" in str(caught.value)


@pytest.mark.parametrize("algorithm", ["auto", "", "python", "smacof"])
def test_there_is_no_auto_or_alias(algorithm: str) -> None:
    # The reference's method="auto" picked R or Python by probing the host.
    with pytest.raises(LayoutUnavailable, match="unknown algorithm"):
        require_layout_algorithm(algorithm)


def test_the_aia_algorithm_resolves() -> None:
    assert require_layout_algorithm("aia_rowcond_unfolding_v1") is (
        LayoutAlgorithm.AIA_ROWCOND_UNFOLDING_V1
    )


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("dimensions", 3),
        ("max_iterations", 0),
        ("max_iterations", True),
        ("convergence_tolerance", 0.0),
        ("convergence_tolerance", True),
        ("convergence_tolerance", math.nan),
    ],
)
def test_unfolding_parameters_reject_implausible_values(field: str, bad: Any) -> None:
    with pytest.raises(ValueError):
        UnfoldingParameters(**{**TIGHT.model_dump(), field: bad})


def test_unfolding_parameters_have_no_defaults() -> None:
    with pytest.raises(ValueError):
        UnfoldingParameters(dimensions=2, max_iterations=10)  # type: ignore[call-arg]


# ------------------------------------------------------------- targets --


def test_scale_top_dissimilarity() -> None:
    assert scale_top_dissimilarity([[10, 1, None]], 10.0) == ((0.0, 9.0, None),)


def test_ratings_above_the_declared_scale_are_refused_not_clipped() -> None:
    with pytest.raises(UnfoldingDesignError, match="above the declared scale top"):
        scale_top_dissimilarity([[11, 3]], 10.0)


# ------------------------------------------------------------ recovery --


@pytest.mark.parametrize(("n", "m", "seed", "missing"), [(30, 6, 7, False), (60, 9, 11, True)])
def test_recovers_the_geometry_that_generated_the_data(
    n: int, m: int, seed: int, missing: bool
) -> None:
    planted = _planted(n, m, seed, row_scales=True, missing=missing)
    result = fit_rowcond_unfolding(planted["delta"], TIGHT)
    assert result.converged
    assert result.stress_1 < 1e-4
    fit = procrustes_align(planted["objects"], list(result.object_xy), allow_scale=True)
    assert fit.rmsd < 1e-3
    people = procrustes_align(planted["people"], list(result.respondent_xy), allow_scale=True)
    assert people.rmsd < 1e-3


def test_row_scales_absorb_how_each_respondent_uses_the_scale() -> None:
    plain = _planted(30, 6, 3, row_scales=False, missing=False)
    scaled = [
        [None if v is None else v * (1 + i % 5) for v in row]
        for i, row in enumerate(plain["delta"])
    ]
    a = fit_rowcond_unfolding(plain["delta"], TIGHT)
    b = fit_rowcond_unfolding(scaled, TIGHT)
    fit = procrustes_align(list(a.object_xy), list(b.object_xy), allow_scale=True)
    assert fit.rmsd < 1e-3


def test_stress_never_increases_with_more_iterations() -> None:
    delta = _planted(25, 6, 5, row_scales=True, missing=True)["delta"]
    stresses = [
        fit_rowcond_unfolding(
            delta,
            UnfoldingParameters(dimensions=2, max_iterations=k, convergence_tolerance=1e-15),
        ).normalized_stress
        for k in (1, 2, 5, 10, 40, 160)
    ]
    assert all(later <= earlier + 1e-15 for earlier, later in itertools.pairwise(stresses))


def test_stops_at_max_iterations_and_says_it_did_not_converge() -> None:
    delta = _planted(25, 6, 5, row_scales=True, missing=False)["delta"]
    result = fit_rowcond_unfolding(
        delta, UnfoldingParameters(dimensions=2, max_iterations=3, convergence_tolerance=1e-15)
    )
    assert result.iterations == 3 and not result.converged


# --------------------------------------------------------- determinism --


def test_identical_input_gives_identical_bits() -> None:
    delta = _planted(40, 7, 9, row_scales=True, missing=True)["delta"]
    assert fit_rowcond_unfolding(delta, TIGHT) == fit_rowcond_unfolding(delta, TIGHT)


def test_gauge_is_fixed() -> None:
    result = fit_rowcond_unfolding(
        _planted(40, 7, 9, row_scales=True, missing=False)["delta"], TIGHT
    )
    ys = result.object_xy
    assert abs(math.fsum(x for x, _ in ys)) < 1e-9 and abs(math.fsum(y for _, y in ys)) < 1e-9
    assert abs(math.fsum(x * y for x, y in ys)) < 1e-9  # principal axes
    assert math.fsum(x**3 for x, _ in ys) > 0 and math.fsum(y**3 for _, y in ys) > 0
    var_x = math.fsum(x * x for x, _ in ys)
    var_y = math.fsum(y * y for _, y in ys)
    assert var_x >= var_y


def test_reported_stress_matches_the_returned_configuration() -> None:
    delta = _planted(20, 5, 2, row_scales=False, missing=False)["delta"]
    result = fit_rowcond_unfolding(delta, TIGHT)
    dhat = [[b * v for v in row] for row, b in zip(delta, result.row_scales, strict=True)]
    assert stress_1(dhat, result.respondent_xy, result.object_xy) == pytest.approx(result.stress_1)


# ---------------------------------------------------------- design errors --


@pytest.mark.parametrize(
    ("delta", "match"),
    [
        ([], "at least one"),
        ([[1.0, 2.0]], "at least 3 objects"),
        ([[1.0, 2.0, 3.0], [1.0, 2.0]], "at least 3 objects"),
        ([[1.0, None, None]], "not placeable"),
        ([[0.0, 0.0, 0.0]], "not placeable"),
        ([[1.0, -2.0, 3.0]], "not placeable"),
        ([[1.0, 2.0, None], [2.0, 1.0, None]], "rated by no placeable"),
        ([[1.0, 2.0, None, None], [None, None, 1.0, 2.0]], "disconnected"),
    ],
)
def test_unplaceable_designs_are_refused(delta: Any, match: str) -> None:
    with pytest.raises(UnfoldingDesignError, match=match):
        fit_rowcond_unfolding(delta, TIGHT)


def test_a_connected_sparse_design_is_placeable() -> None:
    # A and C are never rated by the same respondent, but B links them.
    delta = [
        [1.0, 3.0, None],
        [2.0, 0.5, None],
        [None, 1.0, 2.5],
        [None, 2.0, 0.5],
    ]
    result = fit_rowcond_unfolding(delta, TIGHT)
    assert len(result.object_xy) == 3 and len(result.respondent_xy) == 4


def test_a_connected_sparse_design_recovers_planted_geometry() -> None:
    planted = _planted(60, 8, 13, row_scales=True, missing=False)
    # Two rating blocks sharing objects 2-5: pairs (0|1, 6|7) are never co-rated.
    for i, row in enumerate(planted["delta"]):
        for j in (6, 7) if i % 2 == 0 else (0, 1):
            row[j] = None
    result = fit_rowcond_unfolding(planted["delta"], TIGHT)
    fit = procrustes_align(planted["objects"], list(result.object_xy), allow_scale=True)
    # Measured: stress-1 0.0097, RMSD 0.018 on a configuration spanning +-3. A
    # shortest-path start for the missing pairs reached RMSD 1.47 -- a reflected
    # block -- at similar stress, which is what this test exists to catch.
    assert result.stress_1 < 0.02
    assert fit.rmsd < 0.05


def test_a_respondent_indifferent_between_objects_is_placeable() -> None:
    delta = [[3.0, 3.0, 3.0], [0.0, 4.0, 8.0], [8.0, 4.0, 0.0], [4.0, 0.0, 4.0]]
    result = fit_rowcond_unfolding(delta, TIGHT)
    assert len(result.respondent_xy) == 4
    assert all(math.isfinite(c) for p in result.respondent_xy for c in p)


# ------------------------------------------------------------- procrustes --


def test_procrustes_recovers_a_rotated_reflected_scaled_copy() -> None:
    ref = [(0.0, 0.0), (1.0, 0.0), (0.0, 2.0), (-1.5, 0.5)]
    c, s = math.cos(0.7), math.sin(0.7)
    moved = [(3 * (c * x - s * -y) + 5, 3 * (s * x + c * -y) - 2) for x, y in ref]
    fit = procrustes_align(ref, moved, allow_scale=True)
    assert fit.rmsd < 1e-12 and fit.reflected and fit.scale == pytest.approx(1 / 3)
    assert procrustes_align(ref, moved, allow_scale=False).rmsd > 0.1


def test_procrustes_refuses_mismatched_configurations() -> None:
    with pytest.raises(ValueError):
        procrustes_align([(0.0, 0.0)], [], allow_scale=False)
