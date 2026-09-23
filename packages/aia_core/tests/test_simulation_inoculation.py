"""Population inoculation from a frozen world model: FS_* columns, seeds, invariants."""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from typing import Any

import pytest

from aia_core.domain.simulation import (
    DEFAULT_SPEC_SEED,
    FS_EPISTEMIC_STATUS,
    INOCULATION_ALGORITHM,
    RNG_ALGORITHM,
    SIMULATION_CONSTANTS_VERSION,
    Driver,
    DriverFieldMissing,
    InoculatedWorld,
    PopulationRow,
    SimulationPopulation,
    WorldModel,
    apply_world,
    calibrate_intercept,
    calibrate_world,
    driver_vector,
    fs_column,
    inoculate_population,
    world_correlation,
    world_seed,
)
from aia_core.domain.simulation.numerics import (
    symmetric_eigen,
    weighted_correlation,
    weighted_mean,
)


@pytest.fixture(scope="module")
def world(sim_population: SimulationPopulation, sim_world_model: WorldModel) -> InoculatedWorld:
    return inoculate_population(
        sim_population, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED
    )


def _field(population: SimulationPopulation, name: str) -> list[float | None]:
    return [r.values.get(name) for r in population.rows]


# --- Identity and markers -------------------------------------------------------------------


def test_world_records_seed_identity_and_versions(
    world: InoculatedWorld, sim_world_model: WorldModel, sim_population: SimulationPopulation
) -> None:
    assert world.world_id == "world_001"
    assert world.world_seed == world_seed(DEFAULT_SPEC_SEED, 0) == 20260816 + 104729
    assert world.world_model_sha256 == sim_world_model.sha256
    assert world.population_sha256 == sim_population.fingerprint()
    assert world.epistemic_status == FS_EPISTEMIC_STATUS
    assert world.algorithm == INOCULATION_ALGORITHM
    assert world.rng_algorithm == RNG_ALGORITHM
    assert world.constants_version == SIMULATION_CONSTANTS_VERSION
    assert world.weight_basis == "synthetic_weight"
    world.verify()


def test_fs_columns_are_exactly_the_reference_set(
    world: InoculatedWorld, sim_world_model: WorldModel
) -> None:
    columns = world.fs_columns()
    expected = {fs_column(f) for f in sim_world_model.factor_ids} | {
        "FS_SIMULATION_PROFILE",
        "FS_WORLD_ID",
        "FS_WORLD_SEED",
        "FS_WORLD_MODEL_SHA256",
        "FS_EPISTEMIC_STATUS",
    }
    assert set(columns) == expected
    assert all(name.startswith("FS_") for name in columns)
    n = len(world.row_ids)
    assert all(len(col) == n for col in columns.values())
    assert set(columns["FS_WORLD_ID"]) == {"world_001"}
    assert set(columns["FS_EPISTEMIC_STATUS"]) == {"EXPERIMENTAL_HYPOTHESIZED_JOINT"}
    assert set(columns["FS_WORLD_MODEL_SHA256"]) == {sim_world_model.sha256}
    assert set(columns["FS_SIMULATION_PROFILE"]) <= set(sim_world_model.factor_ids)


def test_base_population_is_unchanged(
    sim_population_builder: Callable[..., SimulationPopulation], sim_world_model: WorldModel
) -> None:
    """Reference rule, kept exactly: only FS_* fields are added; rows and weights stay."""
    population = sim_population_builder()
    before = population.model_dump()
    fingerprint = population.fingerprint()
    inoculate_population(population, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED)
    assert population.model_dump() == before
    assert population.fingerprint() == fingerprint
    assert not any(k.startswith("FS_") for r in population.rows for k in r.values)


# --- The numbers --------------------------------------------------------------------------


def test_values_stay_on_the_scale_and_hit_the_target_mean(
    world: InoculatedWorld, sim_world_model: WorldModel
) -> None:
    for factor, stats in zip(sim_world_model.factors, world.factor_stats, strict=True):
        column = world.column(factor.id)
        assert all(1.0 < v < 10.0 for v in column)
        assert weighted_mean(column, world.weights) == pytest.approx(
            factor.target_mean_10, abs=1e-9
        )
        assert stats.weighted_mean == pytest.approx(factor.target_mean_10, abs=1e-9)
        # The SD is the design value to first order, never forced; it is reported.
        assert stats.weighted_sd == pytest.approx(factor.target_sd_10, rel=0.35)
        assert stats.minimum == min(column) and stats.maximum == max(column)


def test_driver_signs_carry_through(
    world: InoculatedWorld, sim_population: SimulationPopulation
) -> None:
    w = world.weights
    use = [x or 0.0 for x in _field(sim_population, "digital_use_share")]
    trust = [x or 0.0 for x in _field(sim_population, "institutional_trust_10")]
    positive = weighted_correlation(use, list(world.column("digital_confidence")), w)
    trusting = weighted_correlation(trust, list(world.column("institutional_trust")), w)
    assert positive is not None and positive > 0.3
    assert trusting is not None and trusting > 0.5


def test_hypothesised_correlation_direction_is_realised(world: InoculatedWorld) -> None:
    ids = world.factor_ids
    a, b = ids.index("institutional_trust"), ids.index("privacy_concern")
    realised = world.realised_correlation[a][b]
    assert realised is not None and realised < -0.2


def test_missing_driver_values_are_counted_not_hidden(
    world: InoculatedWorld, sim_population: SimulationPopulation
) -> None:
    missing = sum(1 for x in _field(sim_population, "income_index") if x is None)
    assert missing > 0
    stats = {s.factor_id: s for s in world.factor_stats}
    assert stats["price_sensitivity"].missing_driver_values == missing
    assert stats["institutional_trust"].missing_driver_values == 0


def test_world_correlation_is_a_valid_correlation_matrix(
    world: InoculatedWorld, sim_world_model: WorldModel
) -> None:
    corr = world_correlation(sim_world_model)
    assert corr == world.correlation
    n = len(sim_world_model.factors)
    assert all(corr.matrix[i][i] == 1.0 for i in range(n))
    assert symmetric_eigen(corr.matrix)[0][0] >= -1e-10
    # The fixture's hypothesised correlations are jointly infeasible; the size of
    # the projection is reported rather than hidden.
    assert symmetric_eigen(corr.proposed)[0][0] < 0
    assert corr.adjustment > 0


# --- Determinism ------------------------------------------------------------------------------


def test_same_inputs_give_the_same_world(
    world: InoculatedWorld, sim_population: SimulationPopulation, sim_world_model: WorldModel
) -> None:
    again = inoculate_population(
        sim_population, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED
    )
    assert again == world
    assert again.sha256 == world.sha256


def test_another_world_or_seed_gives_a_different_world(
    world: InoculatedWorld, sim_population: SimulationPopulation, sim_world_model: WorldModel
) -> None:
    second = inoculate_population(
        sim_population, sim_world_model, world_index=1, spec_seed=DEFAULT_SPEC_SEED
    )
    reseeded = inoculate_population(
        sim_population, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED + 1
    )
    assert second.world_id == "world_002"
    assert second.sha256 != world.sha256
    assert reseeded.sha256 != world.sha256


def test_row_order_does_not_change_any_row(
    world: InoculatedWorld, sim_population: SimulationPopulation, sim_world_model: WorldModel
) -> None:
    """Counter-based draws are keyed on row id, and every sum is an exact fsum."""
    reversed_population = sim_population.model_copy(
        update={"rows": tuple(reversed(sim_population.rows))}
    )
    flipped = inoculate_population(
        reversed_population, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED
    )
    by_id = dict(zip(flipped.row_ids, flipped.values, strict=True))
    for row_id, values in zip(world.row_ids, world.values, strict=True):
        assert by_id[row_id] == pytest.approx(values, abs=1e-12)


def test_tampered_world_fails_verification(world: InoculatedWorld) -> None:
    forged = dataclasses.replace(world, profiles=("digital_confidence",) * len(world.profiles))
    with pytest.raises(ValueError, match="does not match sha256"):
        forged.verify()


# --- Fail closed ----------------------------------------------------------------------------


def test_driver_field_absent_from_the_population_is_refused(
    sim_population: SimulationPopulation, sim_world_model: WorldModel
) -> None:
    rows = tuple(
        PopulationRow(
            row_id=r.row_id,
            weight=r.weight,
            values={k: v for k, v in r.values.items() if k != "household_size"},
        )
        for r in sim_population.rows
    )
    thin = sim_population.model_copy(update={"rows": rows})
    with pytest.raises(DriverFieldMissing, match="household_size"):
        inoculate_population(thin, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED)


def test_population_of_a_different_dataset_is_refused(
    sim_population: SimulationPopulation, sim_world_model: WorldModel
) -> None:
    other = sim_population.model_copy(update={"dataset_version": "another-dataset"})
    with pytest.raises(DriverFieldMissing, match="validated against"):
        inoculate_population(other, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED)


def test_constant_driver_is_reported_as_degenerate(
    sim_population: SimulationPopulation, sim_world_model: WorldModel
) -> None:
    rows = tuple(
        PopulationRow(row_id=r.row_id, weight=r.weight, values={**r.values, "household_size": 3.0})
        for r in sim_population.rows
    )
    flat = sim_population.model_copy(update={"rows": rows})
    world = inoculate_population(flat, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED)
    stats = {s.factor_id: s for s in world.factor_stats}
    assert stats["price_sensitivity"].degenerate_drivers == ("household_size",)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"rows": ()}, "at least 1"),
        ({"weight_basis": ""}, "at least 1"),
    ],
)
def test_population_contract(kwargs: dict[str, Any], message: str) -> None:
    base: dict[str, Any] = {
        "dataset_version": "d",
        "weight_basis": "w",
        "rows": (PopulationRow(row_id="a", weight=1.0, values={}),),
    }
    with pytest.raises(ValueError, match=message):
        SimulationPopulation(**{**base, **kwargs})


def test_population_refuses_duplicate_ids_zero_weight_and_bad_values() -> None:
    row = PopulationRow(row_id="a", weight=1.0, values={"x": 1.0})
    with pytest.raises(ValueError, match="unique"):
        SimulationPopulation(dataset_version="d", weight_basis="w", rows=(row, row))
    with pytest.raises(ValueError, match="positive total"):
        SimulationPopulation(
            dataset_version="d",
            weight_basis="w",
            rows=(PopulationRow(row_id="a", weight=0.0, values={}),),
        )
    with pytest.raises(ValueError, match="boolean"):
        PopulationRow(row_id="a", weight=1.0, values={"x": True})
    with pytest.raises(ValueError):
        PopulationRow(row_id="a", weight=1.0, values={"x": math.inf})
    with pytest.raises(ValueError):
        PopulationRow(row_id="a", weight=-1.0, values={})


# --- Building blocks --------------------------------------------------------------------------


def test_driver_vector_is_effect_times_weighted_z() -> None:
    population = SimulationPopulation(
        dataset_version="d",
        weight_basis="w",
        rows=(
            PopulationRow(row_id="a", weight=1.0, values={"x": 0.0}),
            PopulationRow(row_id="b", weight=1.0, values={"x": 2.0}),
            PopulationRow(row_id="c", weight=1.0, values={"x": None}),
        ),
    )
    drive, missing, degenerate = driver_vector(population, [Driver(field="x", effect=0.5)])
    # mean 1, sd 1 over present rows; the missing row sits at the mean (z = 0)
    assert drive == pytest.approx((-0.5, 0.5, 0.0))
    assert missing == 1
    assert degenerate == ()


def test_calibrate_intercept_hits_the_target() -> None:
    latent = [-1.5, -0.5, 0.0, 0.5, 1.5]
    weights = [1.0, 2.0, 1.0, 2.0, 1.0]
    for target in (1.2, 4.0, 5.5, 9.8):
        a = calibrate_intercept(target, 1.3, latent, weights)
        mean = weighted_mean([1 + 9 / (1 + math.exp(-(a + 1.3 * s))) for s in latent], weights)
        assert mean == pytest.approx(target, abs=1e-9)


@pytest.mark.parametrize("target", [1.0, 10.0, 0.5, 11.0])
def test_calibrate_intercept_refuses_an_unreachable_target(target: float) -> None:
    with pytest.raises(ValueError):
        calibrate_intercept(target, 1.0, [0.0, 1.0], [1.0, 1.0])


# --- Calibrate once, evaluate many ------------------------------------------------------------


def test_inoculate_is_calibrate_then_apply_on_the_same_population(
    world: InoculatedWorld, sim_population: SimulationPopulation, sim_world_model: WorldModel
) -> None:
    calibration = calibrate_world(
        sim_population, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED
    )
    assert apply_world(sim_population, sim_world_model, calibration) == world
    assert world.calibration_population_sha256 == world.population_sha256
    assert world.calibration_sha256 == calibration.sha256


def test_a_shifted_population_is_evaluated_in_the_baseline_world(
    world: InoculatedWorld, sim_population: SimulationPopulation, sim_world_model: WorldModel
) -> None:
    calibration = calibrate_world(
        sim_population, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED
    )
    rows = tuple(
        PopulationRow(
            row_id=r.row_id,
            weight=r.weight,
            values={**r.values, "age": (r.values["age"] or 0.0) + 10.0},
        )
        for r in sim_population.rows
    )
    older = sim_population.model_copy(update={"rows": rows})
    shifted = apply_world(older, sim_world_model, calibration)
    assert shifted.calibration_population_sha256 == sim_population.fingerprint()
    assert shifted.population_sha256 == older.fingerprint()
    assert shifted.world_seed == world.world_seed
    means = {s.factor_id: s.weighted_mean for s in shifted.factor_stats}
    base = {s.factor_id: s.weighted_mean for s in world.factor_stats}
    assert means["digital_confidence"] < base["digital_confidence"]  # age effect -0.35
    assert means["privacy_concern"] > base["privacy_concern"]  # age effect +0.25
    assert means["price_sensitivity"] == base["price_sensitivity"]  # no age driver


def test_calibration_for_another_world_model_is_refused(
    sim_fixture: dict[str, Any],
    sim_population: SimulationPopulation,
    sim_world_model: WorldModel,
    sim_schema: Any,
) -> None:
    from aia_core.domain.simulation import Objective, validate_world_model

    other = validate_world_model(
        sim_fixture["raw_model_output"],
        schema=sim_schema,
        objective=Objective.SCENARIO_NOWCAST,
        research_sha256=sim_fixture["research_sha256"],
    )
    calibration = calibrate_world(sim_population, other, world_index=0, spec_seed=1)
    with pytest.raises(ValueError, match="different world model"):
        apply_world(sim_population, sim_world_model, calibration)
    foreign = sim_population.model_copy(update={"dataset_version": "another"})
    with pytest.raises(DriverFieldMissing, match="calibrated on"):
        apply_world(foreign, other, calibration)
