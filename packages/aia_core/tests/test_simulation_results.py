"""Outcomes, ensembles, variant deltas, frozen predictions, write-once truth, scoring."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from aia_core.domain.simulation import (
    DEFAULT_SPEC_SEED,
    IncomparableResults,
    Objective,
    PanelSchema,
    ScenarioContract,
    SimulationPopulation,
    TruthAlreadyRecorded,
    TruthPrecedesFreeze,
    VariableShift,
    Variant,
    VariantResult,
    WorldModel,
    approve_scenario,
    compare_variants,
    ensemble_worlds,
    freeze_prediction,
    fs_column,
    inoculate_population,
    record_truth,
    run_variant,
    score_distribution,
    score_prediction,
    validate_world_model,
    world_outcome,
)
from aia_core.domain.simulation.results import SCALE_OPTIONS

AT = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
N_WORLDS = 3
TRUST = fs_column("institutional_trust")
PRIVACY = fs_column("privacy_concern")


def _approved(delta: float = 2.0) -> Any:
    contract = ScenarioContract(
        scenario_id="trust_campaign",
        title="Data-protection campaign",
        narrative="",
        shifts=(VariableShift(field="institutional_trust_10", delta=delta, rationale="campaign"),),
    )
    return approve_scenario(contract, approved_by="lead", approved_at=AT)


BASELINE = Variant(variant_id="baseline", label="Baseline", scenario=None)
TRUST_VARIANT = Variant(variant_id="trust", label="Trust campaign", scenario=_approved())


@pytest.fixture(scope="module")
def baseline(
    sim_world_model: WorldModel, sim_population: SimulationPopulation, sim_schema: PanelSchema
) -> VariantResult:
    return run_variant(
        sim_world_model,
        sim_population,
        sim_schema,
        BASELINE,
        spec_seed=DEFAULT_SPEC_SEED,
        n_worlds=N_WORLDS,
    )


@pytest.fixture(scope="module")
def trust(
    sim_world_model: WorldModel, sim_population: SimulationPopulation, sim_schema: PanelSchema
) -> VariantResult:
    return run_variant(
        sim_world_model,
        sim_population,
        sim_schema,
        TRUST_VARIANT,
        spec_seed=DEFAULT_SPEC_SEED,
        n_worlds=N_WORLDS,
    )


# --- Outcomes and ensembles -----------------------------------------------------------------


def test_world_outcome_is_a_distribution_per_factor(
    sim_world_model: WorldModel, sim_population: SimulationPopulation
) -> None:
    world = inoculate_population(sim_population, sim_world_model, world_index=0, spec_seed=1)
    outcome = world_outcome(world)
    assert set(outcome.distributions) == {fs_column(f) for f in sim_world_model.factor_ids}
    for dist in outcome.distributions.values():
        assert tuple(dist) == SCALE_OPTIONS
        assert sum(dist.values()) == pytest.approx(100.0, abs=1e-9)
    for f in sim_world_model.factors:
        assert outcome.means[fs_column(f.id)] == pytest.approx(f.target_mean_10, abs=1e-9)


def test_ensemble_is_the_mean_with_the_world_range(baseline: VariantResult) -> None:
    e = baseline.ensemble
    assert e.world_ids == ("world_001", "world_002", "world_003")
    for q, dist in e.distributions.items():
        assert sum(dist.values()) == pytest.approx(100.0, abs=1e-9)
        for opt, pct in dist.items():
            lo, hi = e.distribution_range[q][opt]
            assert lo <= pct <= hi
            per_world = [w.distributions[q][opt] for w in baseline.worlds]
            assert pct == pytest.approx(sum(per_world) / N_WORLDS)


def test_ensemble_refuses_nothing_duplicates_and_mismatched_shapes(
    baseline: VariantResult,
) -> None:
    with pytest.raises(ValueError, match="at least one"):
        ensemble_worlds([])
    w = baseline.worlds[0]
    with pytest.raises(ValueError, match="same world twice"):
        ensemble_worlds([w, w])
    odd = dataclasses.replace(
        baseline.worlds[1], distributions={"other": {"1": 100.0}}, means={"other": 1.0}
    )
    with pytest.raises(IncomparableResults):
        ensemble_worlds([w, odd])


def test_run_variant_is_deterministic(
    baseline: VariantResult,
    sim_world_model: WorldModel,
    sim_population: SimulationPopulation,
    sim_schema: PanelSchema,
) -> None:
    again = run_variant(
        sim_world_model,
        sim_population,
        sim_schema,
        BASELINE,
        spec_seed=DEFAULT_SPEC_SEED,
        n_worlds=N_WORLDS,
    )
    assert again.sha256 == baseline.sha256
    assert baseline.interpolated is False


def test_run_variant_refuses_zero_worlds_and_a_foreign_schema(
    sim_world_model: WorldModel, sim_population: SimulationPopulation, sim_schema: PanelSchema
) -> None:
    with pytest.raises(ValueError, match="n_worlds"):
        run_variant(sim_world_model, sim_population, sim_schema, BASELINE, spec_seed=1, n_worlds=0)
    foreign = sim_schema.model_copy(update={"numeric_fields": sim_schema.numeric_fields | {"z"}})
    with pytest.raises(IncomparableResults, match="different schema"):
        run_variant(sim_world_model, sim_population, foreign, BASELINE, spec_seed=1, n_worlds=1)


# --- Comparison -------------------------------------------------------------------------------


def test_trust_scenario_moves_trust_up_and_privacy_down(
    baseline: VariantResult, trust: VariantResult
) -> None:
    """The deltas come from two full runs, not from arithmetic on one."""
    cmp = compare_variants(baseline, trust)
    assert cmp.interpolated is False and cmp.common_random_numbers is True
    assert cmp.scenario_sha256 == TRUST_VARIANT.scenario_sha256
    assert trust.base_population_sha256 == baseline.base_population_sha256
    assert trust.simulated_population_sha256 != baseline.simulated_population_sha256

    # institutional_trust is driven +0.7 by the shifted field, privacy_concern -0.3.
    assert cmp.mean_deltas[TRUST].delta > 0.5
    assert cmp.mean_deltas[TRUST].sign_consistent
    assert cmp.mean_deltas[PRIVACY].delta < 0
    assert cmp.mean_deltas[PRIVACY].sign_consistent
    for q in cmp.distribution_deltas:
        assert sum(d.delta for d in cmp.distribution_deltas[q].values()) == pytest.approx(
            0.0, abs=1e-9
        )
        for opt, d in cmp.distribution_deltas[q].items():
            assert d.delta == pytest.approx(
                trust.ensemble.distributions[q][opt] - baseline.ensemble.distributions[q][opt]
            )
            assert d.world_min <= d.delta <= d.world_max


def test_a_factor_the_scenario_does_not_drive_does_not_move(
    baseline: VariantResult, trust: VariantResult
) -> None:
    """Common random numbers and one calibration per world: an undriven factor is exact."""
    cmp = compare_variants(baseline, trust)
    untouched = fs_column("digital_confidence")
    assert cmp.mean_deltas[untouched].delta == 0.0
    assert cmp.mean_deltas[untouched].world_min == 0.0
    assert cmp.mean_deltas[untouched].world_max == 0.0
    assert all(d.delta == 0.0 for d in cmp.distribution_deltas[untouched].values())


def test_a_bigger_shift_moves_the_factor_further(
    sim_world_model: WorldModel,
    sim_population: SimulationPopulation,
    sim_schema: PanelSchema,
    baseline: VariantResult,
    trust: VariantResult,
) -> None:
    """Each variant is modelled on its own; the response is not assumed linear."""
    bigger = run_variant(
        sim_world_model,
        sim_population,
        sim_schema,
        Variant(variant_id="trust_big", label="Bigger", scenario=_approved(delta=4.0)),
        spec_seed=DEFAULT_SPEC_SEED,
        n_worlds=N_WORLDS,
    )
    small = compare_variants(baseline, trust).mean_deltas[TRUST].delta
    large = compare_variants(baseline, bigger).mean_deltas[TRUST].delta
    assert large > small > 0
    assert large != pytest.approx(2 * small, rel=1e-6)


def test_baseline_compared_with_itself_shows_no_change(baseline: VariantResult) -> None:
    """Common random numbers: identical inputs give exactly zero delta in every world."""
    fake_alt = dataclasses.replace(baseline, variant_id="same", scenario_sha256="0" * 64)
    from aia_core.domain.pipeline import fingerprint

    fake_alt = dataclasses.replace(fake_alt, sha256=fingerprint(fake_alt.content()))
    cmp = compare_variants(baseline, fake_alt)
    for deltas in cmp.distribution_deltas.values():
        for d in deltas.values():
            assert d.delta == 0.0 and d.world_min == 0.0 and d.world_max == 0.0
            assert not d.sign_consistent


@pytest.mark.parametrize(
    "tamper",
    [
        "baseline_not_baseline",
        "alternative_is_baseline",
        "different_seed",
        "different_world_model",
        "forged",
    ],
)
def test_comparison_refuses_incomparable_results(
    baseline: VariantResult, trust: VariantResult, tamper: str
) -> None:
    b, a = baseline, trust
    if tamper == "baseline_not_baseline":
        b = trust
    elif tamper == "alternative_is_baseline":
        a = baseline
    elif tamper == "different_seed":
        a = dataclasses.replace(trust, spec_seed=trust.spec_seed + 1)
    elif tamper == "different_world_model":
        a = dataclasses.replace(trust, world_model_sha256="f" * 64)
    elif tamper == "forged":
        a = dataclasses.replace(trust, variant_id="renamed")
    with pytest.raises(IncomparableResults):
        compare_variants(b, a)


# --- Freezing, truth, scoring -------------------------------------------------------------------


def _truth_from(frozen: Any, q: str, shift: float = 0.0) -> dict[str, dict[str, float]]:
    dist = dict(frozen.distributions[q])
    dist["5"] += shift
    dist["6"] -= shift
    return {q: dist}


def test_blind_uncontaminated_prediction_is_benchmark_eligible(
    sim_world_model: WorldModel, baseline: VariantResult
) -> None:
    frozen = freeze_prediction(sim_world_model, baseline, frozen_at=AT)
    assert frozen.objective is Objective.BLIND_FORECAST
    assert frozen.benchmark_eligible is True
    assert frozen.variant_result_sha256 == baseline.sha256
    assert len(frozen.sha256) == 64


def test_scenario_prediction_is_never_eligible_and_truth_cannot_change_that(
    sim_fixture: dict[str, Any],
    sim_population: SimulationPopulation,
    sim_schema: PanelSchema,
) -> None:
    scenario_model = validate_world_model(
        sim_fixture["raw_model_output"],
        schema=sim_schema,
        objective=Objective.SCENARIO_NOWCAST,
        research_sha256=sim_fixture["research_sha256"],
    )
    result = run_variant(
        scenario_model, sim_population, sim_schema, BASELINE, spec_seed=1, n_worlds=1
    )
    frozen = freeze_prediction(scenario_model, result, frozen_at=AT)
    assert frozen.benchmark_eligible is False
    truth = record_truth(
        frozen,
        _truth_from(frozen, TRUST),
        recorded_by="analyst",
        recorded_at=AT + timedelta(days=1),
        existing=None,
    )
    assert not hasattr(truth, "benchmark_eligible")
    assert score_prediction(frozen, truth).benchmark_eligible is False


def test_truth_is_written_once(sim_world_model: WorldModel, baseline: VariantResult) -> None:
    frozen = freeze_prediction(sim_world_model, baseline, frozen_at=AT)
    first = record_truth(
        frozen,
        _truth_from(frozen, TRUST),
        recorded_by="analyst",
        recorded_at=AT + timedelta(hours=1),
        existing=None,
    )
    with pytest.raises(TruthAlreadyRecorded):
        record_truth(
            frozen,
            _truth_from(frozen, TRUST, shift=1.0),
            recorded_by="analyst",
            recorded_at=AT + timedelta(hours=2),
            existing=first,
        )


def test_truth_before_freeze_is_refused(
    sim_world_model: WorldModel, baseline: VariantResult
) -> None:
    frozen = freeze_prediction(sim_world_model, baseline, frozen_at=AT)
    for at in (AT, AT - timedelta(seconds=1)):
        with pytest.raises(TruthPrecedesFreeze):
            record_truth(
                frozen, _truth_from(frozen, TRUST), recorded_by="a", recorded_at=at, existing=None
            )


def test_rounded_truth_is_normalised_and_the_factor_recorded(
    sim_world_model: WorldModel, baseline: VariantResult
) -> None:
    frozen = freeze_prediction(sim_world_model, baseline, frozen_at=AT)
    entered = {TRUST: dict.fromkeys(SCALE_OPTIONS, 10.0)}
    entered[TRUST]["10"] = 9.7  # sums to 99.7, within the 0.5 pp tolerance
    truth = record_truth(
        frozen, entered, recorded_by="a", recorded_at=AT + timedelta(1), existing=None
    )
    assert sum(truth.distributions[TRUST].values()) == pytest.approx(100.0)
    assert truth.normalisation[TRUST] == pytest.approx(100.0 / 99.7)


@pytest.mark.parametrize(
    ("entered", "error"),
    [
        ({}, ValueError),
        ({"FS_ghost_10": dict.fromkeys(SCALE_OPTIONS, 10.0)}, IncomparableResults),
        ({TRUST: {"1": 100.0}}, IncomparableResults),
        ({TRUST: dict.fromkeys(SCALE_OPTIONS, 11.0)}, ValueError),
        ({TRUST: {**dict.fromkeys(SCALE_OPTIONS, 10.0), "1": -1.0, "2": 21.0}}, ValueError),
    ],
)
def test_malformed_truth_is_refused(
    sim_world_model: WorldModel,
    baseline: VariantResult,
    entered: dict[str, dict[str, float]],
    error: type[Exception],
) -> None:
    frozen = freeze_prediction(sim_world_model, baseline, frozen_at=AT)
    with pytest.raises(error):
        record_truth(frozen, entered, recorded_by="a", recorded_at=AT + timedelta(1), existing=None)


def test_freeze_refuses_naive_time_and_a_foreign_result(
    sim_world_model: WorldModel, baseline: VariantResult
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        freeze_prediction(sim_world_model, baseline, frozen_at=datetime(2026, 1, 1))
    foreign = dataclasses.replace(baseline, world_model_sha256="e" * 64)
    with pytest.raises(IncomparableResults):
        freeze_prediction(sim_world_model, foreign, frozen_at=AT)


def test_scoring_a_perfect_and_a_shifted_prediction(
    sim_world_model: WorldModel, baseline: VariantResult
) -> None:
    frozen = freeze_prediction(sim_world_model, baseline, frozen_at=AT)
    perfect = record_truth(
        frozen,
        {q: dict(d) for q, d in frozen.distributions.items() if q in (TRUST, PRIVACY)},
        recorded_by="a",
        recorded_at=AT + timedelta(1),
        existing=None,
    )
    score = score_prediction(frozen, perfect)
    assert score.benchmark_eligible is True
    assert set(score.per_question) == {TRUST, PRIVACY}
    assert score.per_question[TRUST].mae_pp == pytest.approx(0.0, abs=1e-12)


def test_score_distribution_arithmetic() -> None:
    pred = {"a": 50.0, "b": 30.0, "c": 20.0}
    truth = {"a": 40.0, "b": 40.0, "c": 20.0}
    s = score_distribution(pred, truth)
    assert s.mae_pp == pytest.approx(20.0 / 3)
    assert s.max_abs_error_pp == pytest.approx(10.0)
    assert s.total_variation == pytest.approx(0.1)
    with pytest.raises(IncomparableResults):
        score_distribution(pred, {"a": 100.0})
    with pytest.raises(ValueError, match="sums to"):
        score_distribution({"a": 50.0, "b": 30.0, "c": 10.0}, truth)


def test_truth_for_another_prediction_is_refused(
    sim_world_model: WorldModel, baseline: VariantResult, trust: VariantResult
) -> None:
    one = freeze_prediction(sim_world_model, baseline, frozen_at=AT)
    other = freeze_prediction(sim_world_model, trust, frozen_at=AT)
    truth = record_truth(
        one, _truth_from(one, TRUST), recorded_by="a", recorded_at=AT + timedelta(1), existing=None
    )
    with pytest.raises(IncomparableResults):
        score_prediction(other, truth)
