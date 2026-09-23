"""World model contract: reference constants, rejection of invalid model output.

The reference sanitiser *clips* invalid LLM output; production *rejects* it. Every
case below is one field the reference would have silently corrected, and each one
asserts both halves: that production refuses it, and that the refusal is the
recorded intentional difference in ``FIELD_POLICY``.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.simulation import (
    BOUNDS,
    DEFAULT_SPEC_SEED,
    FACTOR_EPISTEMIC_STATUS,
    FIELD_POLICY,
    FS_EPISTEMIC_STATUS,
    LINEAR_INTERPOLATION_ALLOWED,
    SIMULATION_CONSTANTS_VERSION,
    WORLD_SEED_STRIDE,
    LegacyMechanism,
    Objective,
    PanelSchema,
    ProductionHandling,
    ViolationCode,
    WorldModel,
    WorldModelRejected,
    ablation_seed,
    validate_world_model,
    world_id,
    world_seed,
)
from aia_core.domain.simulation.reference import REFERENCE_ARCHIVE_SHA256, policy_for

V = ViolationCode
L = LegacyMechanism


def _validate(fixture: dict[str, Any], raw: dict[str, Any], **kw: Any) -> WorldModel:
    return validate_world_model(
        raw,
        schema=PanelSchema.model_validate(fixture["schema"]),
        objective=kw.get("objective", Objective(fixture["objective"])),
        research_sha256=fixture["research_sha256"],
    )


# --- Reference constants: EXACT ------------------------------------------------------


def test_reference_constants_are_the_recovered_values() -> None:
    assert SIMULATION_CONSTANTS_VERSION == "sim-constants-1"
    assert DEFAULT_SPEC_SEED == 20260816
    assert WORLD_SEED_STRIDE == 104729
    assert FACTOR_EPISTEMIC_STATUS == "HYPOTHESIZED_JOINT"
    assert FS_EPISTEMIC_STATUS == "EXPERIMENTAL_HYPOTHESIZED_JOINT"
    assert LINEAR_INTERPOLATION_ALLOWED is False
    assert REFERENCE_ARCHIVE_SHA256.startswith("86b70bfb")
    assert {o.value for o in Objective} == {"blind_forecast", "scenario_nowcast"}


def test_bounds_are_pinned_to_the_constants_version() -> None:
    """Changing a bound without bumping SIMULATION_CONSTANTS_VERSION fails here."""
    assert (BOUNDS.min_factors, BOUNDS.max_factors) == (6, 12)
    assert BOUNDS.target_mean_10 == (1.2, 9.8)
    assert BOUNDS.target_sd_10 == (0.6, 3.2)
    assert BOUNDS.confidence == (0.05, 0.95)
    assert (BOUNDS.min_drivers, BOUNDS.max_drivers) == (1, 6)
    assert BOUNDS.effect == (-1.0, 1.0)
    assert BOUNDS.min_abs_effect == 0.02
    assert BOUNDS.rho == (-0.65, 0.65)
    assert BOUNDS.max_correlations == 30
    assert (BOUNDS.max_label_chars, BOUNDS.max_description_chars, BOUNDS.max_summary_chars) == (
        120,
        600,
        1800,
    )


@pytest.mark.parametrize(
    ("index", "expected"),
    [(0, 20260816 + 104729), (1, 20260816 + 2 * 104729), (9, 20260816 + 10 * 104729)],
)
def test_world_seed_is_seed_plus_stride_times_index_plus_one(index: int, expected: int) -> None:
    assert world_seed(DEFAULT_SPEC_SEED, index) == expected


def test_world_id_and_seed_refuse_a_negative_index() -> None:
    assert world_id(0) == "world_001"
    assert world_id(41) == "world_042"
    with pytest.raises(ValueError):
        world_id(-1)
    with pytest.raises(ValueError):
        world_seed(DEFAULT_SPEC_SEED, -1)


def test_ablation_seed_truncates_temperature_like_the_reference() -> None:
    base = DEFAULT_SPEC_SEED + 88000
    assert ablation_seed(DEFAULT_SPEC_SEED, 0, 0, 0.0) == base
    assert ablation_seed(DEFAULT_SPEC_SEED, 2, 3, 0.7) == base + 2000 + 300 + 7
    # int() truncates: 0.75 * 10 = 7.5 -> 7, and 0.29 * 10 = 2.9 -> 2
    assert ablation_seed(DEFAULT_SPEC_SEED, 0, 0, 0.75) == base + 7
    assert ablation_seed(DEFAULT_SPEC_SEED, 0, 0, 0.29) == base + 2


# --- The frozen fixture ------------------------------------------------------------


def test_fixture_validates_to_exactly_the_frozen_world_model(
    sim_fixture: dict[str, Any], sim_world_model: WorldModel
) -> None:
    fresh = _validate(sim_fixture, sim_fixture["raw_model_output"])
    assert fresh == sim_world_model
    assert fresh.sha256 == sim_fixture["frozen_world_model"]["sha256"]
    assert fresh.sha256 == fresh.content_sha256()


def test_frozen_model_carries_markers_and_bindings(
    sim_fixture: dict[str, Any], sim_world_model: WorldModel, sim_schema: PanelSchema
) -> None:
    wm = sim_world_model
    assert wm.constants_version == SIMULATION_CONSTANTS_VERSION
    assert wm.research_sha256 == sim_fixture["research_sha256"]
    assert wm.panel_schema_sha256 == sim_schema.fingerprint()
    assert all(f.epistemic_status == FACTOR_EPISTEMIC_STATUS for f in wm.factors)
    assert all(c.epistemic_status == FACTOR_EPISTEMIC_STATUS for c in wm.correlations)
    assert wm.objective is Objective.BLIND_FORECAST
    assert wm.contaminated_for_predictive_benchmark is False


def test_frozen_model_round_trips_through_json(sim_world_model: WorldModel) -> None:
    assert WorldModel.model_validate_json(sim_world_model.model_dump_json()) == sim_world_model


def test_reload_refuses_a_hand_edited_model(sim_fixture: dict[str, Any]) -> None:
    edited = copy.deepcopy(sim_fixture["frozen_world_model"])
    edited["factors"][0]["target_mean_10"] = 6.2
    with pytest.raises(ValidationError, match="sha256 does not match"):
        WorldModel.model_validate(edited)


def test_reload_holds_a_model_to_the_same_bounds(sim_fixture: dict[str, Any]) -> None:
    """A8: the reload path cannot be a way around the validator's bounds."""
    edited = copy.deepcopy(sim_fixture["frozen_world_model"])
    edited["factors"][0]["target_mean_10"] = 9.9
    with pytest.raises(ValidationError, match=r"less than or equal to 9\.8"):
        WorldModel.model_validate(edited)


def test_reload_refuses_a_forged_contamination_flag(sim_fixture: dict[str, Any]) -> None:
    edited = copy.deepcopy(sim_fixture["frozen_world_model"])
    edited["objective"] = "scenario_nowcast"
    with pytest.raises(ValidationError, match="contaminated_for_predictive_benchmark"):
        WorldModel.model_validate(edited)


def test_rho_lookup_is_symmetric_and_unlisted_pairs_are_zero(sim_world_model: WorldModel) -> None:
    assert sim_world_model.rho("novelty_seeking", "digital_confidence") == 0.6
    assert sim_world_model.rho("digital_confidence", "novelty_seeking") == 0.6
    assert sim_world_model.rho("digital_confidence", "civic_engagement") == 0.0
    assert sim_world_model.rho("civic_engagement", "civic_engagement") == 1.0


# --- Rejection, one case per recorded difference ------------------------------------

Mutation = Callable[[dict[str, Any]], None]


def _factor(i: int, **changes: Any) -> Mutation:
    def apply(raw: dict[str, Any]) -> None:
        raw["factors"][i].update(changes)

    return apply


def _drop_factor_key(i: int, key: str) -> Mutation:
    def apply(raw: dict[str, Any]) -> None:
        del raw["factors"][i][key]

    return apply


def _driver(i: int, j: int, **changes: Any) -> Mutation:
    def apply(raw: dict[str, Any]) -> None:
        raw["factors"][i]["drivers"][j].update(changes)

    return apply


def _correlation(k: int, **changes: Any) -> Mutation:
    def apply(raw: dict[str, Any]) -> None:
        raw["correlations"][k].update(changes)

    return apply


def _too_many_factors(raw: dict[str, Any]) -> None:
    for n in range(7):
        extra = copy.deepcopy(raw["factors"][0])
        extra["id"] = f"extra_{n}"
        raw["factors"].append(extra)


def _too_few_factors(raw: dict[str, Any]) -> None:
    del raw["factors"][4:]


def _duplicate_factor(raw: dict[str, Any]) -> None:
    raw["factors"][1]["id"] = raw["factors"][0]["id"]


def _too_many_drivers(raw: dict[str, Any]) -> None:
    raw["factors"][0]["drivers"] = [
        {"field": f, "effect": 0.1}
        for f in [
            "age",
            "education_years",
            "income_index",
            "institutional_trust_10",
            "digital_use_share",
            "household_size",
        ]
    ] + [{"field": "age", "effect": 0.2}]


def _no_drivers(raw: dict[str, Any]) -> None:
    raw["factors"][1]["drivers"] = []


def _duplicate_driver_field(raw: dict[str, Any]) -> None:
    raw["factors"][1]["drivers"].append({"field": "institutional_trust_10", "effect": 0.1})


def _too_many_correlations(raw: dict[str, Any]) -> None:
    # 6 factors give only 15 distinct pairs; widen to 12 factors (66 pairs) to exceed 30.
    for n in range(6):
        f = copy.deepcopy(raw["factors"][0])
        f["id"] = f"extra_{n}"
        raw["factors"].append(f)
    ids = [f["id"] for f in raw["factors"]]
    pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1 :]]
    raw["correlations"] = [{"a": a, "b": b, "rho": 0.01} for a, b in pairs[:31]]


def _duplicate_correlation(raw: dict[str, Any]) -> None:
    first = raw["correlations"][0]
    raw["correlations"].append({"a": first["b"], "b": first["a"], "rho": 0.1})


def _overlap_refs(raw: dict[str, Any]) -> None:
    raw["target_overlap_refs"] = ["research_item_17"]


def _long_summary(raw: dict[str, Any]) -> None:
    raw["summary"] = "x" * 1801


CASES: list[tuple[str, Mutation, str, ViolationCode, LegacyMechanism]] = [
    ("factors capped at 12", _too_many_factors, "factors", V.TOO_MANY, L.CAP),
    ("fewer than 6 factors", _too_few_factors, "factors", V.TOO_FEW, L.TOP_UP_FROM_FALLBACK),
    ("duplicate factor id", _duplicate_factor, "factors[].id", V.DUPLICATE, L.DEDUPLICATE),
    (
        "non-slug factor id",
        _factor(0, id="Digital Confidence"),
        "factors[].id",
        V.INVALID_IDENTIFIER,
        L.NORMALISE,
    ),
    ("label > 120", _factor(0, label="x" * 121), "factors[].label", V.TOO_LONG, L.TRUNCATE),
    (
        "description > 600",
        _factor(0, description="x" * 601),
        "factors[].description",
        V.TOO_LONG,
        L.TRUNCATE,
    ),
    (
        "mean above 9.8",
        _factor(0, target_mean_10=9.81),
        "factors[].target_mean_10",
        V.OUT_OF_RANGE,
        L.CLIP,
    ),
    (
        "mean below 1.2",
        _factor(0, target_mean_10=1.0),
        "factors[].target_mean_10",
        V.OUT_OF_RANGE,
        L.CLIP,
    ),
    (
        "mean missing",
        _drop_factor_key(0, "target_mean_10"),
        "factors[].target_mean_10",
        V.MISSING,
        L.DEFAULT,
    ),
    (
        "sd above 3.2",
        _factor(0, target_sd_10=3.3),
        "factors[].target_sd_10",
        V.OUT_OF_RANGE,
        L.CLIP,
    ),
    (
        "sd below 0.6",
        _factor(0, target_sd_10=0.5),
        "factors[].target_sd_10",
        V.OUT_OF_RANGE,
        L.CLIP,
    ),
    (
        "sd missing",
        _drop_factor_key(0, "target_sd_10"),
        "factors[].target_sd_10",
        V.MISSING,
        L.DEFAULT,
    ),
    (
        "confidence above .95",
        _factor(0, confidence=0.99),
        "factors[].confidence",
        V.OUT_OF_RANGE,
        L.CLIP,
    ),
    (
        "confidence missing",
        _drop_factor_key(0, "confidence"),
        "factors[].confidence",
        V.MISSING,
        L.DEFAULT,
    ),
    (
        "factor claims measured status",
        _factor(0, epistemic_status="MEASURED"),
        "factors[].epistemic_status",
        V.WRONG_EPISTEMIC_STATUS,
        L.STAMP,
    ),
    ("more than 6 drivers", _too_many_drivers, "factors[].drivers", V.TOO_MANY, L.TRUNCATE),
    ("no drivers", _no_drivers, "factors[].drivers", V.TOO_FEW, L.NOT_ENFORCED),
    (
        "effect above 1",
        _driver(0, 0, effect=1.2),
        "factors[].drivers[].effect",
        V.OUT_OF_RANGE,
        L.CLIP,
    ),
    (
        "negligible effect",
        _driver(0, 0, effect=0.019),
        "factors[].drivers[].effect",
        V.NEGLIGIBLE_EFFECT,
        L.DROP,
    ),
    (
        "driver field not in population",
        _driver(0, 0, field="shoe_size"),
        "factors[].drivers[].field",
        V.UNKNOWN_FIELD,
        L.DROP,
    ),
    (
        "categorical driver field",
        _driver(0, 0, field="region"),
        "factors[].drivers[].field",
        V.NON_NUMERIC_FIELD,
        L.SCORE_AS_CATEGORY,
    ),
    (
        "driver field twice",
        _duplicate_driver_field,
        "factors[].drivers[].field",
        V.DUPLICATE,
        L.NOT_RECORDED,
    ),
    ("more than 30 correlations", _too_many_correlations, "correlations", V.TOO_MANY, L.CAP),
    (
        "rho above .65",
        _correlation(0, rho=0.66),
        "correlations[].rho",
        V.OUT_OF_RANGE,
        L.CLIP,
    ),
    (
        "rho below -.65",
        _correlation(1, rho=-0.9),
        "correlations[].rho",
        V.OUT_OF_RANGE,
        L.CLIP,
    ),
    (
        "correlation with unknown factor",
        _correlation(0, b="ghost"),
        "correlations[]",
        V.UNKNOWN_FACTOR,
        L.NOT_RECORDED,
    ),
    (
        "self correlation",
        _correlation(0, b="digital_confidence"),
        "correlations[]",
        V.SELF_CORRELATION,
        L.NOT_RECORDED,
    ),
    ("pair given twice", _duplicate_correlation, "correlations[]", V.DUPLICATE, L.NOT_RECORDED),
    (
        "correlation claims measured status",
        _correlation(0, epistemic_status="MEASURED"),
        "correlations[].epistemic_status",
        V.WRONG_EPISTEMIC_STATUS,
        L.STAMP,
    ),
    ("summary > 1800", _long_summary, "summary", V.TOO_LONG, L.TRUNCATE),
    (
        "blind run uses target overlap",
        _overlap_refs,
        "target_overlap_refs",
        V.BLIND_TARGET_OVERLAP,
        L.STRIP,
    ),
]


@pytest.mark.parametrize(
    ("mutate", "field", "code", "legacy"),
    [pytest.param(m, f, c, lg, id=name) for name, m, f, c, lg in CASES],
)
def test_production_rejects_what_the_reference_corrected(
    sim_fixture: dict[str, Any],
    mutate: Mutation,
    field: str,
    code: ViolationCode,
    legacy: LegacyMechanism,
) -> None:
    raw = copy.deepcopy(sim_fixture["raw_model_output"])
    mutate(raw)
    with pytest.raises(WorldModelRejected) as caught:
        _validate(sim_fixture, raw)
    assert (field, code) in caught.value.codes()
    policy = policy_for(field, code)
    assert policy is not None, f"({field}, {code}) is rejected but not recorded in FIELD_POLICY"
    assert policy.legacy is legacy
    assert policy.production is ProductionHandling.REJECT


def test_every_recorded_difference_is_exercised() -> None:
    """Producer/consumer drift (A6): a policy entry with no test is an unverified claim."""
    exercised = {(f, c) for _, _, f, c, _ in CASES}
    recorded = {(p.field, p.code) for p in FIELD_POLICY}
    assert recorded == exercised


def test_policy_table_is_reject_only_and_unambiguous() -> None:
    keys = [(p.field, p.code) for p in FIELD_POLICY]
    assert len(keys) == len(set(keys))
    assert {p.production for p in FIELD_POLICY} == {ProductionHandling.REJECT}
    assert {p.parity for p in FIELD_POLICY} == {"INTENTIONAL_DIFFERENCE"}


def test_every_violation_is_reported_at_once(sim_fixture: dict[str, Any]) -> None:
    raw = copy.deepcopy(sim_fixture["raw_model_output"])
    raw["factors"][0]["target_mean_10"] = 11
    raw["factors"][1]["confidence"] = 0.0
    raw["correlations"][0]["rho"] = 0.9
    with pytest.raises(WorldModelRejected) as caught:
        _validate(sim_fixture, raw)
    paths = {v.path for v in caught.value.violations}
    assert {
        "factors[0].target_mean_10",
        "factors[1].confidence",
        "correlations[0].rho",
    } <= paths


def test_validator_never_returns_a_corrected_value(sim_fixture: dict[str, Any]) -> None:
    """The one behaviour this contract exists to prevent: a clip that looks like success."""
    raw = copy.deepcopy(sim_fixture["raw_model_output"])
    raw["factors"][0]["target_mean_10"] = 12.0
    with pytest.raises(WorldModelRejected):
        _validate(sim_fixture, raw)


# --- Contract errors with no reference counterpart ---------------------------------------


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (_factor(0, target_mean_10="6.1"), V.WRONG_TYPE),
        (_factor(0, target_mean_10=True), V.WRONG_TYPE),
        (_factor(0, target_mean_10=float("nan")), V.NOT_FINITE),
        (_factor(0, label="   "), V.BLANK),
        (_factor(0, notes="extra"), V.UNKNOWN_KEY),
    ],
)
def test_contract_errors_are_rejected_without_a_policy_entry(
    sim_fixture: dict[str, Any], mutate: Mutation, code: ViolationCode
) -> None:
    raw = copy.deepcopy(sim_fixture["raw_model_output"])
    mutate(raw)
    with pytest.raises(WorldModelRejected) as caught:
        _validate(sim_fixture, raw)
    assert any(v.code is code and v.policy is None for v in caught.value.violations)


def test_model_cannot_declare_its_own_objective(sim_fixture: dict[str, Any]) -> None:
    raw = copy.deepcopy(sim_fixture["raw_model_output"])
    raw["objective"] = "blind_forecast"
    with pytest.raises(WorldModelRejected) as caught:
        _validate(sim_fixture, raw)
    assert ("", V.UNKNOWN_KEY) in caught.value.codes()


def test_non_object_output_is_rejected(sim_fixture: dict[str, Any]) -> None:
    with pytest.raises(WorldModelRejected):
        _validate(sim_fixture, ["not", "an", "object"])  # type: ignore[arg-type]


def test_research_binding_must_be_a_sha256(sim_fixture: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="research_sha256"):
        validate_world_model(
            sim_fixture["raw_model_output"],
            schema=PanelSchema.model_validate(sim_fixture["schema"]),
            objective=Objective.BLIND_FORECAST,
            research_sha256="not-a-hash",
        )


def test_epistemic_status_may_be_omitted_and_is_stamped(sim_fixture: dict[str, Any]) -> None:
    raw = copy.deepcopy(sim_fixture["raw_model_output"])
    assert "epistemic_status" not in json.dumps(raw)
    wm = _validate(sim_fixture, raw)
    assert all(f.epistemic_status == FACTOR_EPISTEMIC_STATUS for f in wm.factors)


# --- Objective and contamination -----------------------------------------------------------


def test_scenario_run_may_use_target_overlap_and_is_contaminated(
    sim_fixture: dict[str, Any],
) -> None:
    raw = copy.deepcopy(sim_fixture["raw_model_output"])
    _overlap_refs(raw)
    wm = _validate(sim_fixture, raw, objective=Objective.SCENARIO_NOWCAST)
    assert wm.target_overlap_refs == ("research_item_17",)
    assert wm.contaminated_for_predictive_benchmark is True


def test_scenario_run_is_contaminated_even_without_overlap(sim_fixture: dict[str, Any]) -> None:
    wm = _validate(
        sim_fixture, sim_fixture["raw_model_output"], objective=Objective.SCENARIO_NOWCAST
    )
    assert wm.target_overlap_refs == ()
    assert wm.contaminated_for_predictive_benchmark is True


def test_different_objective_or_research_changes_the_address(
    sim_fixture: dict[str, Any], sim_world_model: WorldModel
) -> None:
    scenario = _validate(
        sim_fixture, sim_fixture["raw_model_output"], objective=Objective.SCENARIO_NOWCAST
    )
    assert scenario.sha256 != sim_world_model.sha256


def test_schema_refuses_a_field_that_is_both_kinds() -> None:
    with pytest.raises(ValidationError):
        PanelSchema(
            dataset_version="x",
            numeric_fields=frozenset({"a"}),
            categorical_fields=frozenset({"a"}),
        )
