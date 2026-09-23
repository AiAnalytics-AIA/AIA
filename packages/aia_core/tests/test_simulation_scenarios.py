"""Scenario contracts, approval binding, applying shifts, and variant sets."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.simulation import (
    ApprovedScenario,
    PanelSchema,
    ScenarioApproval,
    ScenarioContract,
    ScenarioRejected,
    SimulationPopulation,
    VariableShift,
    Variant,
    VariantSet,
    apply_scenario,
    approve_scenario,
)
from aia_core.domain.simulation.scenario import MAX_SHIFTS

AT = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


def _contract(**kw: Any) -> ScenarioContract:
    base: dict[str, Any] = {
        "scenario_id": "trust_campaign",
        "title": "City runs a data-protection campaign",
        "narrative": "Residents are told plainly how their data is handled.",
        "shifts": (VariableShift(field="institutional_trust_10", delta=1.5, rationale="campaign"),),
    }
    return ScenarioContract(**{**base, **kw})


def test_contract_is_content_addressed() -> None:
    a, b = _contract(), _contract()
    assert a.sha256 == b.sha256
    assert _contract(title="Other").sha256 != a.sha256


@pytest.mark.parametrize(
    "kw",
    [
        {"shifts": ()},
        {
            "shifts": tuple(
                VariableShift(field=f"f{i}", delta=1.0, rationale="r")
                for i in range(MAX_SHIFTS + 1)
            )
        },
        {
            "shifts": (
                VariableShift(field="age", delta=1.0, rationale="r"),
                VariableShift(field="age", delta=2.0, rationale="r"),
            )
        },
        {"scenario_id": "Not A Slug"},
    ],
)
def test_contract_shape_is_enforced(kw: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _contract(**kw)


def test_a_zero_shift_is_not_a_scenario() -> None:
    with pytest.raises(ValidationError, match="not a scenario"):
        VariableShift(field="age", delta=0.0, rationale="r")
    with pytest.raises(ValidationError):
        VariableShift(field="age", delta=float("inf"), rationale="r")


def test_approval_is_bound_to_the_exact_contract() -> None:
    approved = approve_scenario(_contract(), approved_by="lead", approved_at=AT)
    assert approved.approval.contract_sha256 == _contract().sha256
    other = _contract(title="Edited after approval")
    with pytest.raises(ValidationError, match="different contract"):
        ApprovedScenario(contract=other, approval=approved.approval)


def test_approval_needs_an_aware_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        ScenarioApproval(
            contract_sha256=_contract().sha256, approved_by="lead", approved_at=datetime(2026, 1, 1)
        )


def test_apply_shifts_present_values_and_leaves_missing_ones_missing(
    sim_population: SimulationPopulation, sim_schema: PanelSchema
) -> None:
    shifts = (
        VariableShift(field="institutional_trust_10", delta=1.5, rationale="campaign"),
        VariableShift(field="income_index", delta=-0.1, rationale="fees"),
    )
    approved = approve_scenario(_contract(shifts=shifts), approved_by="lead", approved_at=AT)
    before = sim_population.model_dump()
    shifted = apply_scenario(sim_population, approved, sim_schema)
    assert sim_population.model_dump() == before, "the base population must not change"
    assert shifted.fingerprint() != sim_population.fingerprint()
    for old, new in zip(sim_population.rows, shifted.rows, strict=True):
        assert new.row_id == old.row_id and new.weight == old.weight
        trust = old.values["institutional_trust_10"]
        assert trust is not None
        assert new.values["institutional_trust_10"] == pytest.approx(trust + 1.5)
        income = old.values["income_index"]
        if income is None:
            assert new.values["income_index"] is None
        else:
            assert new.values["income_index"] == pytest.approx(income - 0.1)
        assert new.values["age"] == old.values["age"]


@pytest.mark.parametrize(
    ("field", "message"),
    [("region", "categorical"), ("shoe_size", "not a population field")],
)
def test_apply_refuses_fields_the_schema_cannot_shift(
    sim_population: SimulationPopulation, sim_schema: PanelSchema, field: str, message: str
) -> None:
    contract = _contract(shifts=(VariableShift(field=field, delta=1.0, rationale="r"),))
    approved = approve_scenario(contract, approved_by="lead", approved_at=AT)
    with pytest.raises(ScenarioRejected, match=message):
        apply_scenario(sim_population, approved, sim_schema)


def test_apply_refuses_a_schema_for_another_dataset(
    sim_population: SimulationPopulation, sim_schema: PanelSchema
) -> None:
    other = sim_schema.model_copy(update={"dataset_version": "other"})
    approved = approve_scenario(_contract(), approved_by="lead", approved_at=AT)
    with pytest.raises(ScenarioRejected, match="schema is"):
        apply_scenario(sim_population, approved, other)


def test_apply_refuses_a_field_the_rows_do_not_carry(sim_schema: PanelSchema) -> None:
    from aia_core.domain.simulation import PopulationRow

    empty = SimulationPopulation(
        dataset_version=sim_schema.dataset_version,
        weight_basis="w",
        rows=(PopulationRow(row_id="a", weight=1.0, values={"age": 30.0}),),
    )
    approved = approve_scenario(_contract(), approved_by="lead", approved_at=AT)
    with pytest.raises(ScenarioRejected, match="carries no field"):
        apply_scenario(empty, approved, sim_schema)


def _variant(vid: str, contract: ScenarioContract | None) -> Variant:
    scenario = (
        None if contract is None else approve_scenario(contract, approved_by="lead", approved_at=AT)
    )
    return Variant(variant_id=vid, label=vid, scenario=scenario)


def test_variant_set_has_one_baseline_and_distinct_alternatives() -> None:
    vs = VariantSet(
        variants=(
            _variant("baseline", None),
            _variant("trust", _contract()),
            _variant("trust_big", _contract(scenario_id="trust_big", title="Bigger")),
        )
    )
    assert vs.baseline.variant_id == "baseline"
    assert [v.variant_id for v in vs.alternatives] == ["trust", "trust_big"]
    assert vs.baseline.scenario_sha256 is None


@pytest.mark.parametrize(
    ("variants", "message"),
    [
        ((("baseline", None),), "at least 2"),
        ((("a", None), ("b", None)), "exactly one baseline"),
        ((("a", "c"), ("b", "c")), "exactly one baseline"),
        ((("baseline", None), ("a", "c"), ("b", "c")), "same scenario contract"),
        ((("baseline", None), ("baseline", "c")), "unique"),
    ],
)
def test_variant_set_shape_is_enforced(
    variants: tuple[tuple[str, str | None], ...], message: str
) -> None:
    built = tuple(_variant(v, None if c is None else _contract()) for v, c in variants)
    with pytest.raises(ValidationError, match=message):
        VariantSet(variants=built)
