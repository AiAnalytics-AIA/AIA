"""Weighting on the Metodika tab (plan ``methodology-tab.md`` W1a).

What every registered module must be (complete, pinned, its tests present) is held by
``test_methodology.py``; this file pins what is particular to this one: its preset is the
import contract's declaration exactly, the aggregate's cleaning is declared as the unit's, and
finding D1 is reproduced -- three cleaning rules for the same weight, and Kish's n computed in
three places that agree only on positive finite weights.
"""

from __future__ import annotations

import math
import random

import pytest
from pydantic import ValidationError

from aia_core.domain import research_aggregate
from aia_core.domain.evidence import support
from aia_core.domain.methodology import MODULES, describe, module_problems
from aia_core.domain.methodology.weighting import AIA_WEIGHTING_V1, WEIGHTING
from aia_core.domain.population import (
    WeightResolutionError,
    analysis_weights,
    resolve_weight_scheme,
)
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17
from aia_core.domain.population.weights import (
    SchemeSpec,
    WeightCleaning,
    WeightingSpec,
    weighting_spec,
)
from aia_core.domain.sociomap import relations

_KISH = (
    research_aggregate.kish_effective_n,
    support.kish_effective_n,
    relations.kish_effective_n,
)


def _values() -> dict[str, object]:
    return {v.reference: v.value for s in describe(WEIGHTING).steps for v in s.values}


def test_it_is_registered_after_aggregation_and_is_complete() -> None:
    assert [m.id for m in MODULES][-3:] == ["support", "aggregation", "weighting"]
    assert module_problems(WEIGHTING) == {}


def test_the_preset_is_the_contracts_declaration_exactly() -> None:
    spec = AIA_WEIGHTING_V1
    assert spec.methodology_version == "aia-weighting-1"
    assert spec.contract_id == CZ_SYNTHETIC_V17.contract_id
    assert spec.default_role == CZ_SYNTHETIC_V17.default_weight_role == "default_current"
    assert [
        (role, s.column, s.expected_total, s.tolerance) for role, s in spec.schemes.items()
    ] == [
        (s.role, s.column, s.expected_total, s.tolerance) for s in CZ_SYNTHETIC_V17.weight_schemes
    ]
    # The default role resolves, through the loader's own path, to the column declared here.
    resolved = resolve_weight_scheme(CZ_SYNTHETIC_V17)
    assert resolved.column == spec.schemes[spec.default_role].column == "vaha_strukturalni_2025"
    # Two totals are declared and none is invented for the other two schemes.
    declared = {r: s.expected_total for r, s in spec.schemes.items() if s.expected_total}
    assert declared == {"default_current": 8_956_290.3618, "census_2021": 8_533_116.0}


def test_every_value_is_shown_from_the_specification() -> None:
    values = _values()
    assert values["default_role"] == "default_current"
    assert values["schemes.census_2021.tolerance"] == 1e-3
    assert values["schemes.party_2021_aggregate.expected_total"] is None  # said, not zero
    assert values["aggregate_cleaning"] is WeightCleaning.MEDIAN


def test_it_is_declared_in_force_and_not_editable_yet() -> None:
    assert [p.name for p in WEIGHTING.presets] == ["aia-weighting-1"]
    assert WEIGHTING.in_force == "aia-weighting-1"
    assert WEIGHTING.editable is False  # W1c
    assert WEIGHTING.formulas == ()


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"default_role": "unknown"}, "not a declared scheme"),
        ({"schemes": {}}, "at least one scheme"),
    ],
)
def test_a_weighting_that_cannot_be_read_is_refused(change: dict[str, object], says: str) -> None:
    payload = {**AIA_WEIGHTING_V1.model_dump(mode="json"), **change}
    with pytest.raises(ValidationError, match=says):
        WeightingSpec.model_validate(payload)


@pytest.mark.parametrize(
    ("scheme", "says"),
    [
        ({"column": "w", "expected_total": 10.0, "tolerance": None}, "go together"),
        ({"column": "w", "expected_total": -1.0, "tolerance": 1.0}, "positive finite"),
        ({"column": "w", "expected_total": 10.0, "tolerance": -1.0}, "not negative"),
        ({"column": "", "expected_total": None, "tolerance": None}, "names its column"),
    ],
)
def test_a_scheme_that_cannot_be_checked_is_refused(scheme: dict[str, object], says: str) -> None:
    with pytest.raises(ValidationError, match=says):
        SchemeSpec.model_validate(scheme)


def test_two_schemes_on_one_column_are_refused() -> None:
    payload = AIA_WEIGHTING_V1.model_dump(mode="json")
    payload["schemes"]["census_2021"]["column"] = "vaha_strukturalni_2025"
    with pytest.raises(ValidationError, match="same column"):
        WeightingSpec.model_validate(payload)


def test_the_spec_follows_whatever_contract_it_is_built_from() -> None:
    spec = weighting_spec(
        CZ_SYNTHETIC_V17, methodology_version="x", aggregate_cleaning=WeightCleaning.REFUSE
    )
    assert spec.aggregate_cleaning is WeightCleaning.REFUSE
    assert spec.schemes == AIA_WEIGHTING_V1.schemes


# ------------------------------------------------------------------------------- D1


def test_three_cleaning_rules_impute_or_refuse_the_same_weight() -> None:
    """D1, reproduced: one invalid weight among valid ones. The aggregate (the unit's port)
    replaces it by the median of the valid ones; the evidence gate and the population loader
    refuse it."""
    weights = [1.0, math.nan, 3.0, 5.0]
    assert research_aggregate.clean_weights(weights) == [1.0, 3.0, 3.0, 5.0]
    assert research_aggregate.clean_weights([math.nan, -1.0]) == [1.0, 1.0]  # none valid: 1
    with pytest.raises(ValueError, match="finite non-negative"):
        support.kish_effective_n(weights)
    with pytest.raises(WeightResolutionError, match="unusable"):
        analysis_weights(["1", None, "3", "5"], resolve_weight_scheme(CZ_SYNTHETIC_V17))
    with pytest.raises(WeightResolutionError, match="unusable"):
        analysis_weights(["1", "-2", "3", "5"], resolve_weight_scheme(CZ_SYNTHETIC_V17))


def test_kish_is_computed_three_times_and_agrees_only_on_valid_weights() -> None:
    """D1, reproduced: three implementations of the same formula. On positive finite weights
    they give the same float; on a zero, a negative or a NaN each does something else."""
    rng = random.Random(20261012)
    for _ in range(200):
        w = [rng.uniform(0.05, 6.0) for _ in range(rng.randint(1, 80))]
        first, *rest = (kish(w) for kish in _KISH)
        assert all(other == first for other in rest), w

    with_zero = [1.0, 0.0, 2.0]
    assert research_aggregate.kish_effective_n(with_zero) == support.kish_effective_n(with_zero)
    with pytest.raises(ValueError):
        relations.kish_effective_n(with_zero)  # the Sociomap's pair refuses a zero

    negative = [1.0, -1.0, 2.0]
    assert research_aggregate.kish_effective_n(negative) == pytest.approx(1.8)  # dropped
    for refusing in (support.kish_effective_n, relations.kish_effective_n):
        with pytest.raises(ValueError):
            refusing(negative)
