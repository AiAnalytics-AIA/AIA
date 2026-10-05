"""The H-Model's reported accuracy (register SOMECS-H3, AIA-H4, QED-H2).

One source fixture: SOMECS Input tutorial p. 21, fig. 22 -- a generated 10 x 10 matrix, the
2-D coordinates SOMECS fitted to it, and a list of SOMECS's Spearman accuracies, transcribed
from the screenshot (``fixtures/sociomapping_sources/somecs_input_fig22.json``). The other
tests check invariances the definition must satisfy; they test AIA's implementation only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from aia_core.domain.sociomap.fuzzy import FuzzyMatrix, FuzzyMatrixError, FuzzySource
from aia_core.domain.sociomap.hmodel import average_ranks, hmodel_accuracy, spearman

FIG22 = json.loads(
    (Path(__file__).parent / "fixtures/sociomapping_sources/somecs_input_fig22.json").read_text()
)


def entered(ids: str, rows: list[list[float | None]]) -> FuzzyMatrix:
    return FuzzyMatrix.from_square(ids, rows, FuzzySource.ENTERED, ("QED-F1",))


def fig22() -> tuple[FuzzyMatrix, list[tuple[float, float]]]:
    ids = [f"e{i}" for i in range(10)]
    m = FuzzyMatrix.from_square(ids, FIG22["matrix"], FuzzySource.ENTERED, ("QED-F1",))
    return m, [tuple(p) for p in FIG22["coordinates"]]  # type: ignore[misc]


ASYM = entered(
    "ABCD",
    [
        [None, 0.9, 0.4, 0.1],
        [0.2, None, 0.8, 0.3],
        [0.5, 0.6, None, 0.7],
        [0.1, 0.3, 0.95, None],
    ],
)
LAYOUT = [(0.0, 0.0), (1.0, 0.2), (1.6, 1.1), (2.4, 1.0)]


def test_somecs_fig22_layout_scores_as_somecs_lists_it() -> None:
    m, layout = fig22()
    fit = hmodel_accuracy(m, layout)
    assert m.is_symmetric()
    assert fit.accuracy == pytest.approx(0.7858, abs=5e-4)
    assert fit.ordered_pairs == 90
    # SOMECS lists 0.785 among its accuracies; the coordinates' 3-decimal rounding alone
    # moves this figure within 0.783-0.793 (tools/somecs_estimation_experiment.py).
    assert any(abs(listed - fit.accuracy) < 0.002 for listed in FIG22["listed_accuracies"])
    # The alternative reading -- the mean of per-row values -- lands below every listed value.
    assert fit.mean_per_point == pytest.approx(0.7233, abs=5e-4)
    assert fit.mean_per_point < min(FIG22["listed_accuracies"])


def test_symmetric_matrix_ordered_equals_unordered_pairs() -> None:
    m, layout = fig22()
    unordered_v = [m.relation(r, s) for r in range(10) for s in range(r + 1, 10)]
    unordered_d = [-math.dist(layout[r], layout[s]) for r in range(10) for s in range(r + 1, 10)]
    assert hmodel_accuracy(m, layout).accuracy == pytest.approx(
        spearman(unordered_v, unordered_d), abs=1e-12
    )


def test_accuracy_ignores_rotation_translation_reflection_and_scale() -> None:
    base = hmodel_accuracy(ASYM, LAYOUT)
    angle = 0.7
    moved = [
        (
            3.0 * (x * math.cos(angle) - y * math.sin(angle)) + 5.0,
            -3.0 * (x * math.sin(angle) + y * math.cos(angle)) - 2.0,  # reflected
        )
        for x, y in LAYOUT
    ]
    other = hmodel_accuracy(ASYM, moved)
    assert other.accuracy == pytest.approx(base.accuracy, abs=1e-12)
    assert other.per_point == pytest.approx(base.per_point, abs=1e-12)


def test_accuracy_ignores_relabelling() -> None:
    order = [2, 0, 3, 1]
    base = hmodel_accuracy(ASYM, LAYOUT)
    relabelled = hmodel_accuracy(ASYM.permuted(order), [LAYOUT[i] for i in order])
    assert relabelled.accuracy == pytest.approx(base.accuracy, abs=1e-12)
    assert relabelled.per_point == pytest.approx([base.per_point[i] for i in order], abs=1e-12)


def test_accuracy_ignores_monotone_transforms_of_relations() -> None:
    squared = entered(
        "ABCD",
        [[None if v is None else v**2 for v in row] for row in ASYM.values],
    )
    assert hmodel_accuracy(squared, LAYOUT).accuracy == pytest.approx(
        hmodel_accuracy(ASYM, LAYOUT).accuracy, abs=1e-12
    )


def test_a_perfect_layout_scores_one() -> None:
    xs = [0.0, 1.0, 3.0, 6.0]
    m = entered(
        "ABCD",
        [[None if r == s else 1 - abs(xs[r] - xs[s]) / 6 for s in range(4)] for r in range(4)],
    )
    fit = hmodel_accuracy(m, [(x, 0.0) for x in xs])
    assert fit.accuracy == pytest.approx(1.0)
    assert fit.per_point == pytest.approx((1.0, 1.0, 1.0, 1.0))
    reversed_layout = hmodel_accuracy(m, [(6.0 - x, 0.0) for x in xs])
    assert reversed_layout.accuracy == pytest.approx(1.0)  # a reflection, not a worse fit


def test_ties_take_average_ranks() -> None:
    assert average_ranks([0.3, 0.1, 0.3, 0.2]) == [3.5, 1.0, 3.5, 2.0]
    # Hand computation: ranks x = [1, 2.5, 2.5, 4], y = [1, 2, 3, 4];
    # mean 2.5; sxy = 2.25+0+0+2.25 = 4.5; sxx = 2.25+0+0+2.25 = 4.5; syy = 5; rho = 4.5/sqrt(22.5)
    assert spearman([1, 2, 2, 3], [10, 20, 30, 40]) == pytest.approx(4.5 / math.sqrt(22.5))
    assert spearman([1, 1, 1], [1, 2, 3]) is None
    assert spearman([1], [1]) is None
    with pytest.raises(ValueError, match="paired"):
        spearman([1, 2], [1])


def test_constant_row_has_no_per_point_fit() -> None:
    m = entered(
        "ABCD",
        [
            [None, 0.9, 0.4, 0.1],
            [0.5, None, 0.5, 0.5],  # B rated everyone the same
            [0.5, 0.6, None, 0.7],
            [0.1, 0.3, 0.95, None],
        ],
    )
    fit = hmodel_accuracy(m, LAYOUT)
    assert fit.per_point[1] is None and fit.per_point_undefined[1] == "every relation is equal"
    assert fit.defined_points == 3 and fit.accuracy is not None
    defined = [v for v in fit.per_point if v is not None]
    assert fit.mean_per_point == pytest.approx(sum(defined) / 3)


def test_asymmetric_relations_enter_as_separate_observations() -> None:
    fit = hmodel_accuracy(ASYM, LAYOUT)
    v = [ASYM.relation(r, s) for r in range(4) for s in range(4) if r != s]
    d = [-math.dist(LAYOUT[r], LAYOUT[s]) for r in range(4) for s in range(4) if r != s]
    assert fit.ordered_pairs == 12
    assert fit.accuracy == pytest.approx(spearman(v, d), abs=1e-12)
    symmetrised_v = [
        (ASYM.relation(r, s) + ASYM.relation(s, r)) / 2 for r in range(4) for s in range(r + 1, 4)
    ]
    symmetrised_d = [-math.dist(LAYOUT[r], LAYOUT[s]) for r in range(4) for s in range(r + 1, 4)]
    assert fit.accuracy != pytest.approx(spearman(symmetrised_v, symmetrised_d), abs=1e-6)


def test_degenerate_layouts_are_undefined_not_zero() -> None:
    fit = hmodel_accuracy(ASYM, [(1.0, 1.0)] * 4)
    assert fit.accuracy is None and fit.accuracy_undefined == "every distance is equal"
    assert fit.per_point == (None, None, None, None) and fit.mean_per_point is None
    equal = entered("ABC", [[None, 0.5, 0.5], [0.5, None, 0.5], [0.5, 0.5, None]])
    assert hmodel_accuracy(equal, LAYOUT[:3]).accuracy_undefined == "every relation is equal"


def test_positions_contract() -> None:
    for layout, why in [
        (LAYOUT[:3], "3 positions for 4"),
        ([(0.0, 0.0), (1.0, float("nan")), (2.0, 0.0), (3.0, 0.0)], "finite"),
        ([(0.0,), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)], r"\(x, y\)"),
    ]:
        with pytest.raises(FuzzyMatrixError, match=why):
            hmodel_accuracy(ASYM, layout)  # type: ignore[arg-type]
