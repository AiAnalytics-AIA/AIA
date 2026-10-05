"""The experimental AIA H-Model candidate (register AIA-H9), on its own terms.

None of these tests is evidence that the candidate is SOMECS's method. They check what
``docs/architecture/sociomapping-hmodel.md`` § 4 asks of an experimental candidate:

* perfect fit **only** where a planted construction guarantees one under this evaluator;
* never below the classical MDS baseline it starts from;
* many independent matrices -- symmetric and asymmetric, tied, signed, with undefined pairs
  -- rather than one screenshot;
* determinism, order independence, and refusals that name their reason.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pytest

from aia_core.domain.sociomap.declared import (
    DeclaredRelations,
    RelationScale,
    declared_from_correlations,
    declared_from_fuzzy,
)
from aia_core.domain.sociomap.fuzzy import (
    FuzzyMatrix,
    FuzzyMatrixError,
    FuzzySource,
    rts_object_correlations,
    rts_people_matrix,
    rts_scale_answers,
)
from aia_core.domain.sociomap.hmodel import EVALUATOR_VERSION, hmodel_accuracy
from aia_core.domain.sociomap.hmodel_candidate import (
    CANDIDATE_METHOD,
    CANDIDATE_STATUS,
    CandidateParameters,
    fit_hmodel_candidate,
)
from aia_core.domain.sociomap.models import RatingsMatrix

FAST = CandidateParameters(random_starts=1)
FIG22 = json.loads(
    (Path(__file__).parent / "fixtures/sociomapping_sources/somecs_input_fig22.json").read_text()
)
TEAM = ("Anna", "Tomas", "Karel", "Marie", "Bara", "David", "Honza")
TAB_1 = (  # certification material p. 9: 1-5 ratings, many ties
    (None, 2, 3, 3, 4, 4, 4),
    (2, None, 4, 1, 2, 4, 4),
    (1, 3, None, 2, 1, 2, 3),
    (3, 2, 2, None, 3, 4, 3),
    (5, 2, 1, 4, None, 4, 2),
    (2, 3, 2, 4, 2, None, 4),
    (3, 3, 4, 4, 2, 4, None),
)


def _planted(n: int, seed: int) -> tuple[FuzzyMatrix, list[tuple[float, float]]]:
    """Symmetric relations, one strictly decreasing function of planted distances."""
    rng = random.Random(seed)
    points = [(rng.random(), rng.random()) for _ in range(n)]
    rows = [
        [None if r == s else math.exp(-3 * math.dist(points[r], points[s])) for s in range(n)]
        for r in range(n)
    ]
    ids = [f"p{i}" for i in range(n)]
    return FuzzyMatrix.from_square(ids, rows, FuzzySource.ENTERED, ("QED-F1",)), points


def _objects(seed: int, constant: bool = False) -> DeclaredRelations:
    """Signed object correlations from fictional 1-10 answers: two opposed groups."""
    rng = random.Random(seed)
    rows = []
    for _ in range(40):
        u = rng.gauss(0, 1)
        row = [
            max(1, min(10, round(5.5 + 2 * (u if j < 3 else -u) + rng.gauss(0, 1.5))))
            for j in range(5)
        ]
        rows.append((*row, 7) if constant else tuple(row))
    ids = ("A", "B", "C", "D", "E", "F") if constant else ("A", "B", "C", "D", "E")
    answers = RatingsMatrix(
        respondent_ids=tuple(f"r{i}" for i in range(40)), object_ids=ids, values=tuple(rows)
    )
    return declared_from_correlations(rts_object_correlations(rts_scale_answers(answers, (1, 10))))


@pytest.mark.parametrize(("n", "seed"), [(5, 0), (5, 1), (8, 0), (8, 1), (8, 2), (10, 3)])
def test_planted_symmetric_relations_are_recovered_exactly(n: int, seed: int) -> None:
    matrix, points = _planted(n, seed)
    assert hmodel_accuracy(matrix, points).accuracy == 1.0  # the construction guarantees it
    layout = fit_hmodel_candidate(declared_from_fuzzy(matrix), FAST)
    assert layout.accuracy.accuracy == 1.0
    assert layout.accuracy.per_point == (1.0,) * n


def test_asymmetric_planted_relations_expose_pooled_versus_per_point() -> None:
    # Each row a different decreasing function of the planted distances: the planted layout
    # has every per-point fit 1 (QED-H2), but a pooled correlation over all rows (SOMECS-H3)
    # rewards another layout. The candidate maximises the pooled accuracy, as specified; the
    # conflict is recorded for the method owner (plan M2), not hidden here.
    rng = random.Random(100)
    n = 6
    points = [(rng.random(), rng.random()) for _ in range(n)]
    a = [rng.uniform(1, 5) for _ in range(n)]
    b = [rng.uniform(0, 0.3) for _ in range(n)]
    rows = [
        [
            None
            if r == s
            else b[r] + (1 - b[r]) * math.exp(-a[r] * math.dist(points[r], points[s]))
            for s in range(n)
        ]
        for r in range(n)
    ]
    matrix = FuzzyMatrix.from_square(
        [f"p{i}" for i in range(n)], rows, FuzzySource.ENTERED, ("QED-F1",)
    )
    planted = hmodel_accuracy(matrix, points)
    assert planted.per_point == (1.0,) * n
    layout = fit_hmodel_candidate(declared_from_fuzzy(matrix), FAST)
    assert layout.accuracy.accuracy is not None and planted.accuracy is not None
    assert layout.accuracy.accuracy > planted.accuracy  # pooled: the optimiser is doing its job
    assert min(p for p in layout.accuracy.per_point if p is not None) < 1.0  # ...per point: not


@pytest.mark.parametrize("seed", range(6))
def test_random_matrices_never_end_below_the_classical_mds_baseline(seed: int) -> None:
    rng = random.Random(1000 + seed)
    n = rng.choice([5, 7, 9])
    symmetric = seed % 2 == 0
    rows = [[0.0] * n for _ in range(n)]
    for r in range(n):
        for s in range(n):
            if r != s and (not symmetric or s > r):
                rows[r][s] = rng.random()
                if symmetric:
                    rows[s][r] = rows[r][s]
    matrix = FuzzyMatrix.from_square(
        [f"e{i}" for i in range(n)], rows, FuzzySource.ENTERED, ("QED-F1",)
    )
    layout = fit_hmodel_candidate(declared_from_fuzzy(matrix), FAST)
    assert layout.baseline_classical_mds is not None and layout.accuracy.accuracy is not None
    assert layout.accuracy.accuracy >= layout.baseline_classical_mds - 1e-12
    assert all(r.final_accuracy is not None for r in layout.starts)


def test_tied_ratings_lay_out_and_report_per_point_fit() -> None:
    layout = fit_hmodel_candidate(declared_from_fuzzy(rts_people_matrix(TEAM, TAB_1, (1, 5))), FAST)
    assert layout.accuracy.accuracy is not None
    assert layout.accuracy.accuracy >= (layout.baseline_classical_mds or 0.0)
    assert layout.accuracy.defined_points == 7
    assert layout.accuracy.ordered_pairs == 42 and layout.accuracy.undefined_pairs == 0


def test_signed_correlations_need_no_conversion_any_monotone_one_gives_the_same_map() -> None:
    relations = _objects(7)
    assert relations.negative_pairs()  # the fixture's two groups correlate negatively
    layout = fit_hmodel_candidate(relations, FAST)
    for transform, scale in [
        (lambda v: (v + 1) / 2, RelationScale.FUZZY_0_1),
        (lambda v: v**3, RelationScale.SIGNED_CORRELATION),
    ]:
        other = DeclaredRelations(
            element_ids=relations.element_ids,
            values=tuple(
                tuple(None if v is None else transform(v) for v in row) for row in relations.values
            ),
            scale=scale,
            undefined=relations.undefined,
            source_fingerprint=relations.source_fingerprint,
            rules=relations.rules,
        )
        assert fit_hmodel_candidate(other, FAST).positions == layout.positions


def test_a_constant_object_is_listed_unplaced_with_its_reason() -> None:
    relations = _objects(7, constant=True)
    layout = fit_hmodel_candidate(relations, FAST)
    assert layout.element_ids == ("A", "B", "C", "D", "E")
    [unplaced] = layout.unplaced
    assert unplaced.element_id == "F" and "every answer equal for F" in unplaced.reason
    assert layout.accuracy.undefined_pairs == 0  # F's pairs are not observations of the rest


def test_reordered_objects_give_the_same_map_reported_in_the_callers_order() -> None:
    relations = _objects(7, constant=True)
    layout = fit_hmodel_candidate(relations, FAST)
    reordered = fit_hmodel_candidate(relations.permuted([4, 2, 0, 5, 1, 3]), FAST)
    assert reordered.element_ids == ("E", "C", "A", "B", "D")
    assert dict(zip(reordered.element_ids, reordered.positions, strict=True)) == dict(
        zip(layout.element_ids, layout.positions, strict=True)
    )
    assert reordered.accuracy.accuracy == layout.accuracy.accuracy


def test_the_result_is_deterministic_framed_and_says_what_it_is() -> None:
    relations = _objects(11)
    layout = fit_hmodel_candidate(relations, FAST)
    assert fit_hmodel_candidate(relations, FAST) == layout
    assert layout.method == CANDIDATE_METHOD == "aia_hmodel_candidate_v1"
    assert layout.status == CANDIDATE_STATUS == "EXPERIMENTAL_AIA"
    assert layout.evaluator == EVALUATOR_VERSION
    assert layout.relations_fingerprint == relations.fingerprint()
    assert layout.relation_scale == "signed_correlation"
    assert layout.rules[: len(relations.rules)] == relations.rules
    assert {"SOMECS-H3", "AIA-H4", "AIA-H8", "AIA-H9"} <= set(layout.rules)
    xs = [c for p in layout.positions for c in p]
    assert min(xs) >= 0.05 - 1e-12 and max(xs) <= 0.95 + 1e-12
    assert len(layout.starts) == 1 + FAST.random_starts and 0 <= layout.chosen_start < 2
    # The frame changes nothing the accuracy sees.
    assert hmodel_accuracy(relations, layout.positions).accuracy == layout.accuracy.accuracy


def test_fig22_a_provisional_comparison_not_a_target() -> None:
    # Regression pin of AIA's own output beside SOMECS's displayed layout (0.786, rounding
    # band 0.783-0.793). Higher is not "better than SOMECS": the candidate optimises this
    # evaluator directly, SOMECS's objective is unknown (AIA-H8).
    matrix = FuzzyMatrix.from_square(
        [f"e{i}" for i in range(10)], FIG22["matrix"], FuzzySource.ENTERED, ("QED-F1",)
    )
    layout = fit_hmodel_candidate(declared_from_fuzzy(matrix))
    assert layout.accuracy.accuracy == pytest.approx(0.8594, abs=5e-5)
    assert layout.baseline_classical_mds == pytest.approx(0.6266, abs=5e-5)


def test_refusals_name_their_reason() -> None:
    with pytest.raises(FuzzyMatrixError, match="at least three elements"):
        fit_hmodel_candidate(
            DeclaredRelations(
                element_ids=("A", "B", "C"),
                values=((None, 0.5, None), (0.5, None, None), (None, None, None)),
                scale=RelationScale.FUZZY_0_1,
                undefined=(("A", "C", "x"), ("C", "A", "x"), ("B", "C", "x"), ("C", "B", "x")),
                source_fingerprint="f",
                rules=("QED-F1",),
            ),
            FAST,
        )
    equal = FuzzyMatrix.from_square(
        "ABC", [[0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]], FuzzySource.ENTERED, ("QED-F1",)
    )
    with pytest.raises(FuzzyMatrixError, match="no order"):
        fit_hmodel_candidate(declared_from_fuzzy(equal), FAST)
    with pytest.raises(FuzzyMatrixError, match="directions"):
        fit_hmodel_candidate(_objects(1), CandidateParameters(directions=2))
