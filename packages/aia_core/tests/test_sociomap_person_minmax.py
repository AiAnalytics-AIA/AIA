"""Audit F2 and F5: each person on their own scale; a matrix's type declared, not guessed.

Plan ``sociomap-formula-corrections`` chunk 2a. F2: Pearson on raw ratings measures rating
habits (a generous rater rates everything high) as well as relations; each respondent's
ratings are put on their own 0-1 scale over every item they rated first. F5: a supplied
matrix's scale was guessed from its values; it is declared instead.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Any

import pytest

from aia_core.domain.research_design import SpecBattery, SpecObject
from aia_core.domain.research_sociomap import derive_pair_relations, rescaled_battery_ratings
from aia_core.domain.sociomap import AIA_SOCIOMAP_V1, compute_sociomap
from aia_core.domain.sociomap.engine import SociomapInputError
from aia_core.domain.sociomap.models import RatingsMatrix, RelationMatrix, SociomapInputs
from aia_core.domain.sociomap.relations import (
    DeclaredRelationType,
    DeclaredTypeUnspecified,
    RelationScaleError,
    coerce_declared_1_10,
    coerce_relation_scale_1_10,
    person_minmax,
)
from aia_core.domain.sociomap.specification import (
    RelationMissingPolicy,
    RelationScaleCoercion,
    UnsupportedMethodology,
    require_supported,
)

# --------------------------------------------------------------------- F2: person_minmax


def test_each_rating_is_placed_between_the_persons_own_lowest_and_highest() -> None:
    scaled = person_minmax([[2.0, 4.0, None, 10.0], [7.0, 9.0, 8.0, None]])
    assert scaled.values == ((0.0, 0.25, None, 1.0), (0.0, 1.0, 0.5, None))
    assert scaled.excluded == ()


def test_a_generous_and_a_strict_rater_who_like_the_same_things_look_the_same() -> None:
    # The audit's own sentence (F2, p. 4): the habit disappears, the preference stays.
    generous, strict = [8.0, 9.0, 10.0], [2.0, 3.0, 4.0]
    scaled = person_minmax([generous, strict])
    assert scaled.values[0] == scaled.values[1] == (0.0, 0.5, 1.0)


@pytest.mark.parametrize(
    "row", [[6.0, 6.0, 6.0], [10.0, None, 10.0], [3.0, None, None], [None, None, None], []]
)
def test_a_row_with_no_spread_is_excluded_never_divided_by_zero(row: list[float | None]) -> None:
    scaled = person_minmax([[1.0, 5.0, 9.0], row])
    assert scaled.excluded == (1,)
    assert scaled.values[1] == tuple(None for _ in row)
    assert scaled.values[0] == (0.0, 0.5, 1.0)


def test_a_non_finite_rating_is_refused() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        person_minmax([[1.0, math.nan, 3.0]])


def _habit_panel(seed: int, n: int = 3000, m: int = 6) -> list[list[float | None]]:
    """``a = 5.5 + g_k + t_ki`` on an integer 1-10 scale: a personal generosity g (sd 1.2)
    and a true taste t (sd 1.5) independent across objects -- the audit's setting."""
    rng = random.Random(seed)
    rows: list[list[float | None]] = []
    for _ in range(n):
        g = rng.gauss(0.0, 1.2)
        rows.append(
            [float(min(10, max(1, round(5.5 + g + rng.gauss(0.0, 1.5))))) for _ in range(m)]
        )
    return rows


def _mean_r(rows: Any) -> float:
    pairs = derive_pair_relations(rows, [1.0] * len(rows), n_min=30, confidence=0.95)
    m = len(pairs.r)
    values = [pairs.r[i][j] for i in range(m) for j in range(i + 1, m)]
    assert all(v is not None for v in values)
    return statistics.fmean(v for v in values if v is not None)


def test_the_rating_habit_inflates_raw_r_and_the_rescaling_removes_it() -> None:
    """Audit F2 [C1]: six independent objects, sd_g = 1.2, sd_t = 1.5. Raw r tends to
    1.44 / 3.69 = 0.39 (the audit's run: +0.394); after per-person min-max, the small
    negative baseline the audit states (-0.09). Measured here on 3,000 respondents,
    seed 1: +0.394 and -0.090."""
    rows = _habit_panel(seed=1)
    assert _mean_r(rows) == pytest.approx(0.394, abs=0.01)
    assert _mean_r(person_minmax(rows).values) == pytest.approx(-0.09, abs=0.01)


# --------------------------------------------- F2 in the research step: every item rated


def _battery(bid: str, n: int, scale: tuple[int, int]) -> SpecBattery:
    return SpecBattery(
        id=bid,
        title=bid,
        family="f",
        question_template="{object}",
        scale=scale,
        scale_labels=("low", "high"),
        objects=tuple(SpecObject(id=f"{bid}{i}", label=f"{bid}{i}") for i in range(n)),
        familiarity_required=False,
        output_type="sociomap",
    )


class _Respondent:
    def __init__(self, rid: str, answers: dict[str, int]) -> None:
        self.respondent_id, self.answers, self.weight = rid, answers, 1.0


class _Dataset:
    def __init__(self, respondents: list[_Respondent]) -> None:
        self.respondents = respondents


def _answers(battery: SpecBattery, values: list[int]) -> dict[str, int]:
    return {battery.question_id(o): v for o, v in zip(battery.objects, values, strict=True)}


def test_a_persons_scale_spans_every_item_they_rated_not_only_the_family_mapped() -> None:
    a, b = _battery("a", 2, (1, 10)), _battery("b", 2, (1, 5))
    # 5 and 5 in family a would be a straight-liner alone; family b spans the scale.
    # On the declared 0-1 scale a's 5 is 4/9 and b's ends are 0 and 1, so a's ratings sit
    # at 4/9 of this person's own range.
    person = _Respondent("R1", {**_answers(a, [5, 5]), **_answers(b, [1, 5])})
    flat = _Respondent("R2", {**_answers(a, [7, 7]), **_answers(b, [4, 4])})
    rows, excluded = rescaled_battery_ratings(a, _Dataset([person, flat]), (a, b))  # type: ignore[arg-type]
    assert rows[0] == [pytest.approx(4 / 9), pytest.approx(4 / 9)]
    # 7 on 1-10 is 2/3 and 4 on 1-5 is 3/4: different, so R2 is not a straight-liner
    # over everything they rated, though they are within each family.
    assert excluded == []
    only_a, excluded_a = rescaled_battery_ratings(a, _Dataset([person, flat]), (a,))  # type: ignore[arg-type]
    assert excluded_a == ["R1", "R2"] and only_a == [[None, None], [None, None]]


def test_the_set_mapped_must_be_one_of_the_sets_it_is_rated_with() -> None:
    a, b = _battery("a", 2, (1, 10)), _battery("b", 2, (1, 10))
    with pytest.raises(ValueError, match="not among"):
        rescaled_battery_ratings(a, _Dataset([]), (b,))  # type: ignore[arg-type]


# ---------------------------------------------------------- F5: declared matrix types


def _matrix(x: float, other: float) -> list[list[float]]:
    return [[0.0, x, other], [x, 0.0, other], [other, other, 0.0]]


def test_the_same_correlation_means_the_same_strength_whatever_the_other_cells() -> None:
    """Audit F5 [C7]: detection reads r = 0.30 as 3.70 when no cell is negative and as 6.85
    when one is -0.1; declared as a correlation it is 6.85 both times."""
    guessed = [coerce_relation_scale_1_10(_matrix(0.3, o))[0][1] for o in (0.2, -0.1)]
    assert guessed == [pytest.approx(3.7), pytest.approx(6.85)]
    declared = [
        coerce_declared_1_10(_matrix(0.3, o), DeclaredRelationType.CORRELATION)[0][1]
        for o in (0.2, -0.1)
    ]
    assert declared == [pytest.approx(6.85), pytest.approx(6.85)]


@pytest.mark.parametrize(
    ("declared", "x", "expected"),
    [
        (DeclaredRelationType.CORRELATION, -1.0, 1.0),
        (DeclaredRelationType.CORRELATION, 1.0, 10.0),
        (DeclaredRelationType.SIMILARITY_0_1, 0.5, 5.5),
    ],
)
def test_each_declared_type_has_its_own_conversion(
    declared: DeclaredRelationType, x: float, expected: float
) -> None:
    out = coerce_declared_1_10(_matrix(x, x), declared)
    assert out[0][1] == pytest.approx(expected) and out[0][0] == 0.0


@pytest.mark.parametrize(
    ("declared", "x"),
    [
        (DeclaredRelationType.CORRELATION, 1.2),
        (DeclaredRelationType.SIMILARITY_0_1, -0.1),
        (DeclaredRelationType.SIMILARITY_0_1, math.nan),
        (DeclaredRelationType.CORRELATION, math.inf),
    ],
)
def test_a_cell_the_declared_type_cannot_hold_is_refused_not_clipped(
    declared: DeclaredRelationType, x: float
) -> None:
    with pytest.raises(RelationScaleError, match="refused"):
        coerce_declared_1_10(_matrix(0.5, x), declared)


def _inputs(relation: list[list[float | None]]) -> SociomapInputs:
    ids = ("o1", "o2", "o3")
    return SociomapInputs(
        ratings=RatingsMatrix(
            respondent_ids=("r1", "r2", "r3"),
            object_ids=ids,
            values=((1.0, 5.0, 10.0), (10.0, 4.0, 2.0), (3.0, 9.0, 6.0)),
        ),
        object_relation=RelationMatrix(entity_ids=ids, values=tuple(map(tuple, relation))),
    )


def _declared_spec(coercion: str, policy: str = RelationMissingPolicy.REFUSE) -> Any:
    assert AIA_SOCIOMAP_V1.relation is not None
    return AIA_SOCIOMAP_V1.model_copy(
        update={
            "relation": AIA_SOCIOMAP_V1.relation.model_copy(
                update={"scale_coercion": coercion, "missing_data_policy": policy}
            )
        }
    )


def test_the_engine_converts_by_the_declared_type_and_records_it() -> None:
    relation: list[list[float | None]] = [[0.0, 0.3, 0.2], [0.3, 0.0, 0.2], [0.2, 0.2, 0.0]]
    spec = _declared_spec(RelationScaleCoercion.DECLARED_CORRELATION)
    artifact = compute_sociomap(_inputs(relation), spec)
    derived = artifact.relation
    assert derived is not None
    assert derived.coercion_branch == "declared_correlation"
    assert derived.coerced.values[0][1] == pytest.approx(6.85)
    # The reference preset still guesses, for fixture F1's parity: 3.70 here.
    reference = compute_sociomap(_inputs(relation), AIA_SOCIOMAP_V1).relation
    assert reference is not None and reference.coerced.values[0][1] == pytest.approx(3.7)


def test_the_engine_refuses_a_cell_its_declared_type_cannot_hold() -> None:
    relation: list[list[float | None]] = [[0.0, 3.0, 2.0], [3.0, 0.0, 2.0], [2.0, 2.0, 0.0]]
    with pytest.raises(SociomapInputError, match="not a correlation value"):
        compute_sociomap(
            _inputs(relation), _declared_spec(RelationScaleCoercion.DECLARED_CORRELATION)
        )


def test_a_declared_type_takes_no_midpoint_sentinel() -> None:
    spec = _declared_spec(
        RelationScaleCoercion.DECLARED_SIMILARITY_0_1,
        RelationMissingPolicy.REFERENCE_MIDPOINT_SENTINEL,
    )
    with pytest.raises(UnsupportedMethodology) as refused:
        require_supported(spec)
    assert "relation.missing_data_policy" in str(refused.value)


def test_a_declared_strength_is_refused_by_name_until_its_transform_is_written() -> None:
    """Register AUDIT-F5 is SPECIFICATION_REQUIRED: the audit names a 'strength 1-10' matrix
    type and does not write out its transform into F6's distance, so converting it would be
    invented methodology. It is refused by name in the conversion and in the spec check."""
    with pytest.raises(DeclaredTypeUnspecified, match="AUDIT-F5"):
        coerce_declared_1_10(_matrix(5.0, 5.0), DeclaredRelationType.STRENGTH_1_10)
    with pytest.raises(UnsupportedMethodology) as refused:
        require_supported(_declared_spec(RelationScaleCoercion.DECLARED_STRENGTH_1_10))
    assert "relation.scale_coercion" in str(refused.value)
    assert "SPECIFICATION_REQUIRED" in str(refused.value)
