"""Regression golden: the simulation core's own outputs on the frozen fixture, pinned.

This is **not** reference parity. It pins what *this* implementation produces
(``fs-inoculation-v1`` under ``sim-constants-1``), so that an accidental change to
any number in the chain fails loudly instead of shifting every future result.

Floats are compared at 1e-9, the parity plan's tolerance for ``simulation.engine``,
rather than bit-for-bit: the chain passes through ``math.exp``/``math.log``, whose
last bits may differ between platforms' libm. Hashes of content that contains no
such floats (the population, the world model) are compared exactly.

A deliberate change regenerates the golden **and** bumps the version it names;
``test_golden_names_the_versions_it_pins`` refuses the one without the other.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.simulation import (
    DEFAULT_SPEC_SEED,
    INOCULATION_ALGORITHM,
    NEAREST_CORRELATION_ALGORITHM,
    RNG_ALGORITHM,
    SIMULATION_CONSTANTS_VERSION,
    PanelSchema,
    ScenarioContract,
    SimulationPopulation,
    VariableShift,
    Variant,
    WorldModel,
    approve_scenario,
    compare_variants,
    inoculate_population,
    run_variant,
)

GOLDEN = Path(__file__).parent / "fixtures" / "simulation" / "golden_outputs_v1.json"
TOL = 1e-9


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return loaded


def test_golden_names_the_versions_it_pins(golden: dict[str, Any]) -> None:
    assert golden["versions"] == {
        "constants": SIMULATION_CONSTANTS_VERSION,
        "algorithm": INOCULATION_ALGORITHM,
        "rng": RNG_ALGORITHM,
        "nearest_correlation": NEAREST_CORRELATION_ALGORITHM,
    }
    assert golden["tolerance"] == TOL
    assert golden["spec_seed"] == DEFAULT_SPEC_SEED


def test_inputs_are_the_ones_the_golden_was_made_from(
    golden: dict[str, Any], sim_population: SimulationPopulation, sim_world_model: WorldModel
) -> None:
    assert golden["population"]["rows"] == len(sim_population.rows)
    assert golden["population"]["sha256"] == sim_population.fingerprint()
    assert golden["world_model_sha256"] == sim_world_model.sha256


def test_first_world_matches_the_golden(
    golden: dict[str, Any], sim_population: SimulationPopulation, sim_world_model: WorldModel
) -> None:
    world = inoculate_population(
        sim_population, sim_world_model, world_index=0, spec_seed=DEFAULT_SPEC_SEED
    )
    expected = golden["world_001"]
    assert world.world_seed == expected["world_seed"]

    for i, row in enumerate(golden["correlation_matrix"]):
        assert list(world.correlation.matrix[i]) == pytest.approx(row, abs=TOL)
    assert world.correlation.adjustment == pytest.approx(golden["correlation_adjustment"], abs=TOL)

    for stats in world.factor_stats:
        pinned = expected["factor_stats"][stats.factor_id]
        for key, value in pinned.items():
            assert getattr(stats, key) == pytest.approx(value, abs=TOL), (stats.factor_id, key)

    by_id = dict(zip(world.row_ids, world.values, strict=True))
    for row_id, values in expected["first_rows"].items():
        got = dict(zip(world.factor_ids, by_id[row_id], strict=True))
        assert got == pytest.approx(values, abs=TOL), row_id
    assert list(world.profiles[:5]) == expected["first_profiles"]


def test_variant_chain_matches_the_golden(
    golden: dict[str, Any],
    sim_population: SimulationPopulation,
    sim_world_model: WorldModel,
    sim_schema: PanelSchema,
) -> None:
    at = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    contract = ScenarioContract(
        scenario_id="trust_campaign",
        title="Data-protection campaign",
        narrative="",
        shifts=(VariableShift(field="institutional_trust_10", delta=2.0, rationale="campaign"),),
    )
    baseline = run_variant(
        sim_world_model,
        sim_population,
        sim_schema,
        Variant(variant_id="baseline", label="Baseline", scenario=None),
        spec_seed=DEFAULT_SPEC_SEED,
        n_worlds=3,
    )
    trust = run_variant(
        sim_world_model,
        sim_population,
        sim_schema,
        Variant(
            variant_id="trust",
            label="Trust campaign",
            scenario=approve_scenario(contract, approved_by="lead", approved_at=at),
        ),
        spec_seed=DEFAULT_SPEC_SEED,
        n_worlds=3,
    )
    assert dict(baseline.ensemble.means) == pytest.approx(
        golden["baseline_ensemble_means"], abs=TOL
    )
    deltas = {q: d.delta for q, d in compare_variants(baseline, trust).mean_deltas.items()}
    assert deltas == pytest.approx(golden["trust_mean_deltas"], abs=TOL)
