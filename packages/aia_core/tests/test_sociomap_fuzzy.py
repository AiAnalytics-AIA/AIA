"""The fuzzy-matrix rules, each against what its source says (evidence register ids in brackets).

Source examples reproduced here (quoted by page, not vendored):

* RTS designs doc p. 19: four people rate three objects; correl(X, Y) = 0.96,
  correl(X, Z) = 0.44, correl(Y, Z) = 0.23 [RTS-O1, RTS-O2].
* Certification material p. 9, Tab. 1: seven people rate each other on 1-5; Anna gave Karel 3,
  Karel gave Anna 1; David and Honza gave each other 4 [RTS-P1].
* SOMECS help p. 22: a subject who rated every object the same gets 0.5 everywhere [SOMECS-D2];
  p. 14: an empty field becomes 0 [SOMECS-D1].

Everything else here tests AIA's implementation and is not evidence about the original method.
"""

from __future__ import annotations

import pytest

from aia_core.domain.sociomap.fuzzy import (
    FuzzyMatrix,
    FuzzyMatrixError,
    FuzzySource,
    MethodologyUndetermined,
    NormalisedStorm,
    ObjectCorrelations,
    Product,
    StormMissingPolicy,
    StormTransform,
    legacy_fuzzy_from_relation_1_10,
    rts_fuzzy_from_correlations,
    rts_object_correlations,
    rts_people_matrix,
    rts_scale_answers,
    somecs_transform_storm,
    weighted_mean_fuzzy,
)
from aia_core.domain.sociomap.models import RatingsMatrix
from aia_core.domain.sociomap.relations import coerce_relation_scale_1_10

TEAM = ("Anna", "Tomáš", "Karel", "Marie", "Bára", "David", "Honza")
TAB_1 = (
    (None, 2, 3, 3, 4, 4, 4),
    (2, None, 4, 1, 2, 4, 4),
    (1, 3, None, 2, 1, 2, 3),
    (3, 2, 2, None, 3, 4, 3),
    (5, 2, 1, 4, None, 4, 2),
    (2, 3, 2, 4, 2, None, 4),
    (3, 3, 4, 4, 2, 4, None),
)
# RTS designs doc p. 19, already normalised to 0..1 by RTS.
RTS_EXAMPLE = ((0.8, 0.9, 0.8), (0.5, 0.7, 0.3), (0.5, 0.6, 0.9), (0.2, 0.5, 0.5))


def ratings(rows: object, objects: tuple[str, ...] = ("X", "Y", "Z")) -> RatingsMatrix:
    values = tuple(tuple(r) for r in rows)  # type: ignore[attr-defined]
    return RatingsMatrix(
        respondent_ids=tuple(f"p{i}" for i in range(len(values))),
        object_ids=objects,
        values=values,
    )


def entered(ids: str, rows: list[list[float | None]]) -> FuzzyMatrix:
    return FuzzyMatrix.from_square(ids, rows, FuzzySource.ENTERED, ("QED-F1",))


# ------------------------------------------------------------------ QED-F1 --


def test_a_fuzzy_matrix_is_square_complete_and_on_zero_one() -> None:
    good = FuzzyMatrix.from_square("AB", [[1, 0.25], [0.75, 1]], FuzzySource.ENTERED, ("QED-F1",))
    assert good.values == ((None, 0.25), (0.75, None))
    assert good.relation(0, 1) == 0.25 and good.relation(1, 0) == 0.75
    assert not good.is_symmetric()
    with pytest.raises(FuzzyMatrixError, match="diagonal"):
        good.relation(0, 0)
    for bad, why in [
        (((0.1, 0.2), (0.3, None)), "diagonal"),
        (((None, None), (0.3, None)), "missing"),
        (((None, 1.5), (0.3, None)), "outside"),
        (((None, float("nan")), (0.3, None)), "finite"),
        (((None, True), (0.3, None)), "boolean"),
        (((None, 0.2),), "rows"),
    ]:
        with pytest.raises(ValueError, match=why):
            FuzzyMatrix(
                element_ids=("A", "B"), values=bad, source=FuzzySource.ENTERED, rules=("QED-F1",)
            )
    for ids, rules, why in [
        (("A",), ("QED-F1",), "at least 2"),
        (("A", "A"), ("QED-F1",), "duplicate"),
    ]:
        with pytest.raises(ValueError, match=why):
            FuzzyMatrix(
                element_ids=ids,
                values=((None,),) if len(ids) == 1 else ((None, 0.1), (0.1, None)),
                source=FuzzySource.ENTERED,
                rules=rules,
            )
    with pytest.raises(ValueError, match="rule id"):
        FuzzyMatrix(
            element_ids=("A", "B"),
            values=((None, 0.1), (0.1, None)),
            source=FuzzySource.ENTERED,
            rules=(),
        )


def test_permuted_matrix_is_a_relabelling() -> None:
    m = entered("ABC", [[None, 0.1, 0.2], [0.3, None, 0.4], [0.5, 0.6, None]])
    p = m.permuted([2, 0, 1])
    assert p.element_ids == ("C", "A", "B")
    assert p.relation(0, 1) == m.relation(2, 0)  # C -> A
    assert p.permuted([1, 2, 0]).values == m.values
    with pytest.raises(FuzzyMatrixError, match="permutation"):
        m.permuted([0, 0, 1])


# ------------------------------------------------------------ RTS-P1, N1 --


def test_rts_people_matrix_keeps_the_certification_tables_orientation() -> None:
    m = rts_people_matrix(TEAM, TAB_1, (1, 5))
    anna, karel, david, honza = 0, 2, 5, 6
    assert m.relation(anna, karel) == 0.5  # Anna gave Karel 3
    assert m.relation(karel, anna) == 0.0  # Karel gave Anna 1
    assert m.relation(david, honza) == m.relation(honza, david) == 0.75  # 4 both ways
    assert m.source is FuzzySource.RTS_PEOPLE and m.rules == ("RTS-P1", "RTS-N1")


def test_rts_people_matrix_refuses_what_rts_would_not_collect() -> None:
    off = [list(row) for row in TAB_1]
    off[0][1] = 6
    with pytest.raises(FuzzyMatrixError, match="outside the scale"):
        rts_people_matrix(TEAM, off, (1, 5))
    gap = [list(row) for row in TAB_1]
    gap[0][1] = None
    with pytest.raises(FuzzyMatrixError, match="missing"):
        rts_people_matrix(TEAM, gap, (1, 5))
    for scale in [(5, 1), (1, float("inf")), (True, 5)]:
        with pytest.raises(FuzzyMatrixError, match="lower to a higher"):
            rts_people_matrix(TEAM, TAB_1, scale)  # type: ignore[arg-type]


def test_rts_scale_is_the_scale_not_the_data_range() -> None:
    out = rts_scale_answers(ratings(((1, 4, 7), (4, 4, None))), (1, 7))
    assert out.values == ((0.0, 0.5, 1.0), (0.5, 0.5, None))
    assert out.transform is StormTransform.RTS_SCALE and out.product is Product.RTS
    assert out.scale == (1, 7) and out.rules == ("RTS-N1",) and not out.is_complete()
    narrow = rts_scale_answers(ratings(((3, 4, 5),)), (1, 7))
    assert narrow.values == ((1 / 3, 0.5, 2 / 3),)  # not stretched to the data's 3..5
    with pytest.raises(FuzzyMatrixError, match="outside the scale"):
        rts_scale_answers(ratings(((1, 4, 8),)), (1, 7))


# ------------------------------------------------------- NormalisedStorm --


def _storm(**changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "subject_ids": ("p0", "p1"),
        "object_ids": ("X", "Y"),
        "values": ((0.0, 1.0), (0.5, None)),
        "transform": StormTransform.RTS_SCALE,
        "missing_policy": StormMissingPolicy.KEEP_EMPTY,
        "scale": (1.0, 5.0),
        "product": Product.RTS,
        "rules": ("RTS-N1",),
        "ratings_fingerprint": "f",
    }
    base.update(changes)
    return base


def test_normalised_storm_contract() -> None:
    NormalisedStorm(**_storm())  # type: ignore[arg-type]
    for changes, why in [
        ({"subject_ids": ()}, "at least 1"),
        ({"subject_ids": ("p0", "p0")}, "duplicate"),
        ({"object_ids": ("X",), "values": ((0.0,), (0.5,))}, "at least 2"),
        ({"values": ((0.0, 1.0),)}, "rows"),
        ({"values": ((0.0, 1.0), (0.5,))}, "cells"),
        ({"values": ((0.0, 1.2), (0.5, None))}, "outside"),
        ({"values": ((0.0, float("inf")), (0.5, None))}, "finite"),
        ({"values": ((0.0, True), (0.5, None))}, "boolean"),
        ({"scale": None}, "scale"),
        ({"scale": (5.0, 1.0)}, "lower to a higher"),
        ({"product": Product.SOMECS}, "belongs to"),
        ({"rules": ()}, "rule id"),
        (
            {
                "transform": StormTransform.SOMECS_WITHIN_ROW,
                "scale": None,
                "product": Product.SOMECS,
                "missing_policy": StormMissingPolicy.SOMECS_ZERO,
            },
            "empty",
        ),
        (
            {"missing_policy": StormMissingPolicy.SOMECS_ZERO, "values": ((0.0, 1.0), (0.5, 0.5))},
            "SOMECS zero",
        ),
    ]:
        with pytest.raises((ValueError, FuzzyMatrixError), match=why):
            NormalisedStorm(**_storm(**changes))  # type: ignore[arg-type]


# --------------------------------------------------------- RTS-O1, RTS-O2 --


def _rts(
    rows: tuple[tuple[float, ...], ...], objects: tuple[str, ...] = ("X", "Y", "Z")
) -> NormalisedStorm:
    return rts_scale_answers(ratings(rows, objects), (0.0, 1.0))


def test_object_correlations_reproduce_the_rts_example() -> None:
    signed = rts_object_correlations(_rts(RTS_EXAMPLE))
    assert signed.support == 4 and signed.undefined == ()
    assert round(signed.r[0][1], 2) == 0.96  # type: ignore[arg-type]  # correl(X, Y)
    assert round(signed.r[0][2], 2) == 0.44  # type: ignore[arg-type]  # correl(X, Z)
    assert round(signed.r[1][2], 2) == 0.23  # type: ignore[arg-type]  # correl(Y, Z)
    # Spearman, the other common "correlation", does not reproduce the example.
    x, y, z = zip(*RTS_EXAMPLE, strict=True)
    assert [round(_spearman(a, b), 2) for a, b in ((x, y), (x, z), (y, z))] == [
        0.95,
        0.32,
        0.0,
    ]
    m = rts_fuzzy_from_correlations(signed)
    assert m.source is FuzzySource.RTS_OBJECT_CORRELATION
    assert m.rules == ("RTS-N1", "RTS-O1", "RTS-O2")
    assert m.relation(0, 1) == signed.r[0][1] and m.is_symmetric()


def test_scaling_columns_keeps_r_but_row_normalisation_changes_it() -> None:
    raw = ((2, 9, 4), (5, 7, 1), (5, 6, 10), (1, 5, 5), (8, 2, 6))
    on_scale = rts_object_correlations(rts_scale_answers(ratings(raw), (1, 10)))
    as_is = rts_object_correlations(rts_scale_answers(ratings(raw), (0, 10)))
    for a in range(3):
        for b in range(3):
            if a != b:
                assert on_scale.r[a][b] == pytest.approx(as_is.r[a][b], abs=1e-12)
    rows = somecs_transform_storm(
        ratings(raw), StormTransform.SOMECS_WITHIN_ROW, StormMissingPolicy.KEEP_EMPTY
    )
    columns = list(zip(*rows.values, strict=True))
    row_normalised_r = _pearson(columns[0], columns[1])  # type: ignore[arg-type]
    assert row_normalised_r == pytest.approx(-0.4260, abs=1e-4)
    assert on_scale.r[0][1] == pytest.approx(-0.6196, abs=1e-4)  # a different number
    with pytest.raises(MethodologyUndetermined, match="not a documented pipeline"):
        rts_object_correlations(rows)


def _pearson(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den


def _ranks(values: tuple[float, ...]) -> tuple[float, ...]:
    # Average ranks: a tied value gets the mean of the positions it spans.
    return tuple(sum(w < v for w in values) + (sum(w == v for w in values) + 1) / 2 for v in values)


def _spearman(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return _pearson(_ranks(a), _ranks(b))


def test_negative_correlations_are_kept_signed_and_refused_by_name() -> None:
    signed = rts_object_correlations(_rts(((0.1, 0.9, 0.2), (0.5, 0.5, 0.6), (0.9, 0.1, 0.7))))
    negatives = signed.negative_pairs()
    assert [(a, b) for a, b, _ in negatives] == [("X", "Y"), ("Y", "Z")]
    assert all(r < 0 for _, _, r in negatives)
    with pytest.raises(MethodologyUndetermined, match="M12") as refused:
        rts_fuzzy_from_correlations(signed)
    assert "X/Y" in str(refused.value) and refused.value.question == "M12"
    assert signed.r[0][1] == negatives[0][2]  # still there, unchanged


def test_constant_object_has_no_correlation_and_is_named() -> None:
    signed = rts_object_correlations(_rts(((0.5, 0.1, 0.4), (0.5, 0.9, 0.6), (0.5, 0.4, 0.9))))
    assert signed.r[0][1] is None and signed.r[0][2] is None and signed.r[1][2] is not None
    assert signed.undefined == (
        ("X", "Y", "every answer equal for X"),
        ("X", "Z", "every answer equal for X"),
    )
    with pytest.raises(FuzzyMatrixError, match="no correlation"):
        rts_fuzzy_from_correlations(signed)


@pytest.mark.parametrize(
    ("value", "scale", "respondents"),
    [
        (2, (1, 10), 10),  # 1/9 ten times: the float mean is not 1/9; r came out 1.0
        (2, (1, 11), 6),  # 1/10 six times: r came out exactly 1.0
        (2, (1, 6), 3),
        (5, (1, 7), 13),
        (3, (0, 10), 7),
    ],
)
def test_repeated_fractions_are_constant_not_perfectly_correlated(
    value: int, scale: tuple[int, int], respondents: int
) -> None:
    constant = rts_scale_answers(ratings([(value, value, value)] * respondents), scale)
    assert constant.values[0][0] not in {0.0, 0.5, 1.0}  # a fraction with no exact binary form
    signed = rts_object_correlations(constant)
    assert signed.r == ((None,) * 3,) * 3
    assert [pair for *pair, _ in signed.undefined] == [["X", "Y"], ["X", "Z"], ["Y", "Z"]]
    with pytest.raises(FuzzyMatrixError, match="no correlation"):
        rts_fuzzy_from_correlations(signed)


def test_every_constant_column_is_undefined_on_every_scale_and_size() -> None:
    # Every value of every scale 1-2 .. 1-11, at 2..15 respondents, beside a varying column:
    # the constant column's pairs are undefined and the varying pair is untouched.
    for high in range(2, 12):
        for value in range(1, high + 1):
            for n in range(2, 16):
                rows = [(value, 1 + i % high, 1 + (i * 7) % high) for i in range(n)]
                signed = rts_object_correlations(rts_scale_answers(ratings(rows), (1, high)))
                assert signed.r[0][1] is None and signed.r[0][2] is None, (high, value, n)
                assert [p[:2] for p in signed.undefined][:2] == [("X", "Y"), ("X", "Z")]


def test_correlations_need_rts_scaled_complete_answers() -> None:
    gap = _rts(((0.8, None, 0.8), (0.5, 0.7, 0.3), (0.5, 0.6, 0.9)))  # type: ignore[arg-type]
    with pytest.raises(MethodologyUndetermined, match="M5"):
        rts_object_correlations(gap)
    with pytest.raises(FuzzyMatrixError, match="two respondents"):
        rts_object_correlations(_rts(((0.8, 0.9, 0.8),)))


def test_object_correlations_contract() -> None:
    good = {
        "object_ids": ("X", "Y"),
        "r": ((None, 0.5), (0.5, None)),
        "undefined": (),
        "support": 3,
        "rules": ("RTS-O1",),
        "answers_fingerprint": "f",
    }
    ObjectCorrelations(**good)  # type: ignore[arg-type]
    for changes, why in [
        ({"r": ((None, 0.5), (0.4, None))}, "symmetric"),
        ({"r": ((None, 1.5), (1.5, None))}, "outside"),
        ({"r": ((0.0, 0.5), (0.5, None))}, "diagonal"),
        ({"support": 1}, "two respondents"),
        ({"r": ((None, None), (None, None))}, "named"),
        ({"undefined": (("X", "Y", "why"),)}, "named"),
    ]:
        with pytest.raises(ValueError, match=why):
            ObjectCorrelations(**{**good, **changes})  # type: ignore[arg-type]


# ------------------------------------------------------- SOMECS-D1..D4 --


def test_somecs_within_row_follows_the_help() -> None:
    out = somecs_transform_storm(
        ratings(((2, 4, 6), (5, 5, 5))),
        StormTransform.SOMECS_WITHIN_ROW,
        StormMissingPolicy.KEEP_EMPTY,
    )
    assert out.values == ((0.0, 0.5, 1.0), (0.5, 0.5, 0.5))  # equal row: 0.5 everywhere
    assert out.product is Product.SOMECS and out.rules == ("SOMECS-D2",) and out.scale is None


def test_somecs_zero_fill_and_complete_data() -> None:
    filled = somecs_transform_storm(
        ratings(((None, 4, 8),)), StormTransform.SOMECS_WITHIN_ROW, StormMissingPolicy.SOMECS_ZERO
    )
    assert filled.values == ((0.0, 0.5, 1.0),)
    assert filled.rules == ("SOMECS-D1", "SOMECS-D2")
    with pytest.raises(MethodologyUndetermined, match="complete data"):
        somecs_transform_storm(
            ratings(((None, 4, 8),)),
            StormTransform.SOMECS_WITHIN_ROW,
            StormMissingPolicy.KEEP_EMPTY,
        )


def test_somecs_within_database_and_refusals() -> None:
    out = somecs_transform_storm(
        ratings(((2, 4, 6), (10, 3, 2))),
        StormTransform.SOMECS_WITHIN_DATABASE,
        StormMissingPolicy.KEEP_EMPTY,
    )
    assert out.values == ((0.0, 0.25, 0.5), (1.0, 0.125, 0.0))
    with pytest.raises(MethodologyUndetermined, match="all equal") as constant:
        somecs_transform_storm(ratings(((3, 3, 3),)), "somecs_within_database", "keep_empty")  # type: ignore[arg-type]
    assert constant.value.question == "M1"
    with pytest.raises(MethodologyUndetermined, match="rank"):
        somecs_transform_storm(ratings(((1, 2, 3),)), "somecs_ordinal", "keep_empty")  # type: ignore[arg-type]
    with pytest.raises(FuzzyMatrixError, match="not a SOMECS transform"):
        somecs_transform_storm(ratings(((1, 2, 3),)), "rts_scale", "keep_empty")  # type: ignore[arg-type]


# --------------------------------------------------------- SOMECS-A1, A2 --


def test_weighted_mean_keeps_inputs_weights_and_the_unperformed_check() -> None:
    one = entered("AB", [[None, 0.2], [0.4, None]])
    two = entered("AB", [[None, 0.8], [0.0, None]])
    result = weighted_mean_fuzzy([one, two], [25, 75])  # SOMECS weights are percentages
    assert result.mean.relation(0, 1) == pytest.approx(0.65)
    assert result.mean.relation(1, 0) == pytest.approx(0.1)
    assert result.weights == (25.0, 75.0) and result.normalised_weights == (0.25, 0.75)
    assert result.input_fingerprints == (one.fingerprint(), two.fingerprint())
    assert result.discrepancy_check == "NOT_PERFORMED" and "M11" in result.discrepancy_reason
    assert result.mean.rules == ("QED-F1", "SOMECS-A1")
    assert weighted_mean_fuzzy([one, two], [1, 0]).mean.values == one.values


def test_weighted_mean_refuses_incompatible_or_weightless_inputs() -> None:
    ab = entered("AB", [[None, 0.2], [0.4, None]])
    ba = entered("BA", [[None, 0.2], [0.4, None]])
    for matrices, weights, why in [
        ([ab, ba], [1, 1], "same elements in the same order"),
        ([ab, ab], [0, 0], "every weight is 0"),
        ([ab, ab], [1, -1], "not negative"),
        ([ab, ab], [1, float("nan")], "finite"),
        ([ab, ab], [1], "2 matrices"),
        ([], [], "at least one"),
        ([ab], [True], "boolean"),
    ]:
        with pytest.raises(FuzzyMatrixError, match=why):
            weighted_mean_fuzzy(matrices, weights)


# --------------------------------------------------------------- LEGACY-R1 --


def test_legacy_1_10_bridge_inverts_f1() -> None:
    m = legacy_fuzzy_from_relation_1_10("ABC", [[0, 1, 10], [5.5, 0, 3.25], [10, 1, 0]])
    assert m.values == ((None, 0.0, 1.0), (0.5, None, 0.25), (1.0, 0.0, None))
    assert m.rules == ("LEGACY-R1",)
    similarity = [[0.0, 0.2, 0.9], [0.4, 0.0, 0.6], [1.0, 0.3, 0.0]]
    back = legacy_fuzzy_from_relation_1_10("ABC", coerce_relation_scale_1_10(similarity))
    for r in range(3):
        for s in range(3):
            if r != s:
                assert back.relation(r, s) == pytest.approx(similarity[r][s], abs=1e-12)
    with pytest.raises(FuzzyMatrixError, match="outside the scale"):
        legacy_fuzzy_from_relation_1_10("AB", [[0, 0.5], [3, 0]])
