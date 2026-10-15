"""Every built-in estimator of aggregation gives the aggregate's exact bits (plan G2b).

ADR 0023 decision 4. Each slot's built-in expression replaces the code inside the aggregate
itself, and the result must be equal -- not close: equal. Two ways:

* every aggregate fixture (the cases captured against the unit) aggregated with all five slots
  replaced by their own built-ins is identical to the aggregate the code computes;
* the unrounded estimates -- a bootstrap's point and both bounds, Kish n, the variance -- are
  equal as floats on random inputs, where a different last bit would show.

Then a replaced slot is shown to be what the aggregate computes, so an edit is never silently
ignored. A slot without a built-in, or a built-in without a slot the aggregate reads, fails.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.evidence.support import AIA_SUPPORT_V1
from aia_core.domain.fieldwork import FieldworkDataset
from aia_core.domain.methodology.aggregation import AGGREGATION
from aia_core.domain.methodology.aggregation_formulas import AGGREGATION_FORMULAS
from aia_core.domain.methodology.expressions import compile_formula
from aia_core.domain.research_aggregate import (
    AGGREGATE_SLOTS,
    AIA_AGGREGATE_V1,
    KISH,
    MEAN,
    SHARE,
    TOP_BOX,
    VARIANCE,
    aggregate_dataset,
    bootstrap_weighted_distribution,
    bootstrap_weighted_mean,
    donor_support,
    kish_effective_n,
    weighted_variance,
)
from aia_core.domain.research_design import ResearchSpecification
from aia_core.domain.sociomap.slots import Slots

FIXTURES = Path(__file__).parent / "fixtures" / "research_aggregate"
CASES = sorted(p.stem for p in (FIXTURES / "cases").glob("*.json"))
QUANTILES = AIA_AGGREGATE_V1.bootstrap.quantiles

BUILT_IN: Slots = {f.slot.id: compile_formula(f.slot, f.expression) for f in AGGREGATION_FORMULAS}


def _case(case_id: str) -> tuple[ResearchSpecification, FieldworkDataset]:
    case = json.loads((FIXTURES / "cases" / f"{case_id}.json").read_text(encoding="utf-8"))
    return (
        ResearchSpecification.model_validate(case["spec"]),
        FieldworkDataset.model_validate(case["dataset"]),
    )


def test_every_slot_the_aggregate_reads_has_a_built_in_and_none_other() -> None:
    assert set(BUILT_IN) == AGGREGATE_SLOTS
    assert AGGREGATION.formulas == AGGREGATION_FORMULAS
    steps = {s.id for s in AGGREGATION.steps}
    assert {f.step_id for f in AGGREGATION_FORMULAS} <= steps


@pytest.mark.parametrize("case_id", CASES)
def test_every_fixture_aggregates_identically_through_its_built_in_expressions(
    case_id: str,
) -> None:
    spec, dataset = _case(case_id)
    code = aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1)
    expressions = aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1, slots=BUILT_IN)
    # Every number is identical. The aggregate still says its formulas were replaced (G2c):
    # an edit is an edit, even one that repeats the built-in.
    assert expressions.pop("deviation")["replaced_formulas"] == sorted(AGGREGATE_SLOTS)
    assert expressions == code


def _rows(rng: random.Random) -> tuple[list[float], list[float], list[str]]:
    n = rng.randint(2, 60)
    values = [
        float(rng.randint(1, 10)) if rng.random() < 0.7 else rng.uniform(0, 10) for _ in range(n)
    ]
    weights = [
        rng.choice([1.0, rng.uniform(0.05, 4.0), rng.lognormvariate(0, 1)]) for _ in range(n)
    ]
    donors = [f"d{rng.randrange(max(1, n // rng.randint(1, 4)))}" for _ in range(n)]
    return values, weights, donors


def test_the_mean_is_bit_identical_at_its_point_and_every_replicate() -> None:
    rng = random.Random(20261012)
    for _ in range(150):
        values, weights, donors = _rows(rng)
        args: dict[str, Any] = {"reps": 40, "seed": rng.randrange(10**6), "donors": donors}
        code = bootstrap_weighted_mean(values, weights, quantiles=QUANTILES, **args)
        slot = bootstrap_weighted_mean(
            values, weights, quantiles=QUANTILES, slots={MEAN: BUILT_IN[MEAN]}, **args
        )
        assert slot == code  # the unrounded point and both bounds, as floats


def test_kish_and_the_variance_are_bit_identical() -> None:
    rng = random.Random(7)
    for _ in range(300):
        values, weights, _ = _rows(rng)
        assert kish_effective_n(weights, {KISH: BUILT_IN[KISH]}) == kish_effective_n(weights)
        assert weighted_variance(values, weights, {VARIANCE: BUILT_IN[VARIANCE]}) == (
            weighted_variance(values, weights)
        )


def test_the_share_is_bit_identical_in_the_distribution_bootstrap() -> None:
    rng = random.Random(11)
    categories = ["a", "b", "c", "d"]
    for _ in range(100):
        _, weights, donors = _rows(rng)
        answers = [rng.choice(categories[:3]) for _ in weights]  # "d" is never chosen
        args: dict[str, Any] = {"reps": 30, "seed": rng.randrange(10**6), "donors": donors}
        code = bootstrap_weighted_distribution(
            answers, categories, weights, quantiles=QUANTILES, **args
        )
        slot = bootstrap_weighted_distribution(
            answers,
            categories,
            weights,
            quantiles=QUANTILES,
            slots={SHARE: BUILT_IN[SHARE]},
            **args,
        )
        assert slot == code


def test_the_top_box_rule_is_the_codes_for_every_width() -> None:
    rule = BUILT_IN[TOP_BOX]
    for top in (5, 7, 10):
        for b in (1, 2, 3):
            for x in [*range(0, top + 2), 4.5, math.nan]:
                expected = 1.0 if x >= top - (b - 1) else 0.0
                assert float(rule(x=float(x), top=float(top), b=float(b))) == expected


def test_a_replaced_estimator_is_what_the_aggregate_computes() -> None:
    """An edit is never silently ignored, and reaches everything that estimator computes."""
    spec, dataset = _case(CASES[0])
    scale = next(q.id for q in spec.questions if q.typ == "skala")

    def aggregate(slots: Slots) -> dict[str, Any]:
        return aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1, slots=slots)["questions"][
            scale
        ]

    code = aggregate({})
    one_point = aggregate({TOP_BOX: compile_formula(BUILT_IN[TOP_BOX].slot, "x >= top")})
    assert one_point["top2box_pct"] < code["top2box_pct"]
    assert one_point["prumer"] == code["prumer"]  # only the top box moved

    largest = aggregate({MEAN: compile_formula(BUILT_IN[MEAN].slot, "max(x)")})
    assert largest["prumer"] == round(max(float(k) for k in code["rozlozeni"]), 2)
    # The top box's share is the weighted mean of who is in it, so it follows agg.mean too.
    assert largest["top2box_pct"] == 100.0
    # Who answered and how they were weighted did not move.
    for key in ("n_platnych", "effective_n", "n_unique_layer_donors", "support_status"):
        assert largest[key] == code[key] == one_point[key], key


# --------------------------------------------------------------------------- what stays code
# A slot replaces one estimator, never the aggregate around it (product owner, 2026-10-14: the
# object map's reader took the step's whole formula for the editable part; the same holds here).


@pytest.mark.parametrize("formula", AGGREGATION_FORMULAS, ids=lambda f: f.slot.id)
def test_every_estimator_says_what_the_aggregate_keeps_around_it(formula: Any) -> None:
    assert formula.kept_cs, f"{formula.slot.id} does not say what stays code"
    assert all(line.strip() and line.endswith(".") for line in formula.kept_cs)


def test_a_replaced_kish_n_sees_cleaned_weights_and_stays_capped_by_the_donors() -> None:
    seen: list[tuple[float, ...]] = []

    def huge(w: tuple[float, ...]) -> float:
        seen.append(w)
        return 1000.0

    support = donor_support(
        ["d1", "d1", "d2"], [1.0, -2.0, math.nan], rule=AIA_SUPPORT_V1.results, slots={KISH: huge}
    )
    assert seen == [(1.0, 1.0, 1.0)]  # invalid weights became the median of the valid ones
    assert support["effective_n_kish"] == 1000.0
    assert support["effective_n_combined"] == 2.0  # never above the two donors


def test_a_replaced_variance_never_sees_fewer_than_two_answers() -> None:
    def never(**_: Any) -> float:
        raise AssertionError("called")

    assert weighted_variance([3.0], [1.0], {VARIANCE: never}) is None
    assert weighted_variance([3.0, math.nan], [1.0, 1.0], {VARIANCE: never}) is None
