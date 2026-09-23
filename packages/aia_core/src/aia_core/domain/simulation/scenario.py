"""Scenario contracts, approval and variants.

The reference rule (``scenario_compiler``): *the free-text story is never the
final simulation object.* A scenario is compiled -- by a model, later -- into an
explicit contract of measured-variable shifts that a person reviews before it can
be simulated. This module is the deterministic half of that: the contract's
shape, its approval, and applying an approved contract to a population.

Three rules are structural:

* **Only an approved contract can be applied.** :func:`apply_scenario` takes an
  :class:`ApprovedScenario`, which cannot be built for a contract other than the
  one that was approved: approval is bound to the contract's ``sha256``.
* **Change first.** A shift is a *delta* on a measured field, never an absolute
  value; a scenario is a difference from the baseline, and the output is read
  that way.
* **Unknown stays unknown.** Shifting a missing value leaves it missing. Adding
  a delta to an imputed value would invent a measurement.

Shifted values are not clipped to any field range: the population contract does
not carry field ranges yet, and a silent clip here would be exactly the kind of
correction the world-model validator refuses.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..pipeline import fingerprint
from .inoculation import PopulationRow, SimulationPopulation
from .world_model import PanelSchema

__all__ = [
    "MAX_SHIFTS",
    "ApprovedScenario",
    "ScenarioApproval",
    "ScenarioContract",
    "ScenarioRejected",
    "VariableShift",
    "Variant",
    "VariantSet",
    "apply_scenario",
    "approve_scenario",
    "check_contract_against_schema",
]

# The reference compiler tests ``len(clean) > 12`` (scenario_compiler.py:146 in the
# reference archive). What it then does with a longer list is not recorded;
# production refuses.
MAX_SHIFTS = 12


class ScenarioRejected(ValueError):
    """A scenario contract that cannot be applied to this population."""


class VariableShift(BaseModel):
    """Add ``delta`` to a measured numeric field, for every row that has it."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    field: str = Field(min_length=1)
    delta: float
    rationale: str = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def _is_a_change(self) -> Self:
        if self.delta == 0.0:
            raise ValueError(f"a shift of 0 on {self.field!r} is not a scenario")
        return self


class ScenarioContract(BaseModel):
    """A reviewable, content-addressed statement of what a scenario changes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    title: str = Field(min_length=1, max_length=200)
    narrative: str = Field(max_length=4000)
    shifts: tuple[VariableShift, ...] = Field(min_length=1, max_length=MAX_SHIFTS)

    @model_validator(mode="after")
    def _one_shift_per_field(self) -> Self:
        fields = [s.field for s in self.shifts]
        if len(set(fields)) != len(fields):
            raise ValueError("a scenario shifts each field at most once")
        return self

    @property
    def sha256(self) -> str:
        return fingerprint(self.model_dump(mode="json"))


def check_contract_against_schema(contract: ScenarioContract, schema: PanelSchema) -> None:
    """Refuse a contract that shifts a field the population cannot shift."""
    for shift in contract.shifts:
        if shift.field in schema.categorical_fields:
            raise ScenarioRejected(f"{shift.field!r} is categorical; a delta has no meaning")
        if shift.field not in schema.numeric_fields:
            raise ScenarioRejected(f"{shift.field!r} is not a population field")


class ScenarioApproval(BaseModel):
    """A person's approval of one exact contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_by: str = Field(min_length=1)
    approved_at: datetime

    @model_validator(mode="after")
    def _aware(self) -> Self:
        if self.approved_at.tzinfo is None:
            raise ValueError("approved_at must be timezone-aware")
        return self


class ApprovedScenario(BaseModel):
    """A contract together with the approval of *that* contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract: ScenarioContract
    approval: ScenarioApproval

    @model_validator(mode="after")
    def _bound(self) -> Self:
        if self.approval.contract_sha256 != self.contract.sha256:
            raise ValueError("the approval is for a different contract")
        return self


def approve_scenario(
    contract: ScenarioContract, *, approved_by: str, approved_at: datetime
) -> ApprovedScenario:
    return ApprovedScenario(
        contract=contract,
        approval=ScenarioApproval(
            contract_sha256=contract.sha256, approved_by=approved_by, approved_at=approved_at
        ),
    )


def apply_scenario(
    population: SimulationPopulation, scenario: ApprovedScenario, schema: PanelSchema
) -> SimulationPopulation:
    """A new population with the approved shifts applied. The input is untouched."""
    if schema.dataset_version != population.dataset_version:
        raise ScenarioRejected(
            f"schema is {schema.dataset_version!r}, population is {population.dataset_version!r}"
        )
    check_contract_against_schema(scenario.contract, schema)
    deltas = {s.field: s.delta for s in scenario.contract.shifts}
    absent = sorted(set(deltas) - population.fields())
    if absent:
        raise ScenarioRejected(f"population carries no field(s) {absent}")
    rows = []
    for row in population.rows:
        values = dict(row.values)
        for name, delta in deltas.items():
            current = values.get(name)
            if current is not None:
                shifted = current + delta
                if not math.isfinite(shifted):
                    raise ScenarioRejected(f"{row.row_id}.{name} overflows under the shift")
                values[name] = shifted
        rows.append(PopulationRow(row_id=row.row_id, weight=row.weight, values=values))
    return SimulationPopulation(
        dataset_version=population.dataset_version,
        weight_basis=population.weight_basis,
        rows=tuple(rows),
    )


class Variant(BaseModel):
    """One arm of a simulation: the baseline (no scenario) or an approved scenario."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    variant_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=200)
    scenario: ApprovedScenario | None

    @property
    def is_baseline(self) -> bool:
        return self.scenario is None

    @property
    def scenario_sha256(self) -> str | None:
        return None if self.scenario is None else self.scenario.contract.sha256


class VariantSet(BaseModel):
    """Exactly one baseline and at least one scenario variant, uniquely named.

    Every variant is simulated on its own; none is ever derived from the others
    (``LINEAR_INTERPOLATION_ALLOWED`` is ``False``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    variants: tuple[Variant, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _shape(self) -> Self:
        ids = [v.variant_id for v in self.variants]
        if len(set(ids)) != len(ids):
            raise ValueError("variant ids must be unique")
        baselines = [v for v in self.variants if v.is_baseline]
        if len(baselines) != 1:
            raise ValueError(f"a variant set has exactly one baseline; got {len(baselines)}")
        contracts = [v.scenario_sha256 for v in self.variants if not v.is_baseline]
        if len(set(contracts)) != len(contracts):
            raise ValueError("two variants apply the same scenario contract")
        return self

    @property
    def baseline(self) -> Variant:
        return next(v for v in self.variants if v.is_baseline)

    @property
    def alternatives(self) -> tuple[Variant, ...]:
        return tuple(v for v in self.variants if not v.is_baseline)
