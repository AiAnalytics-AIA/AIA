"""Which bank items a population can hold out (panel-grounded-respondents 7a, "Eligible").

An item is eligible only when the population's answers to it are a survey's measured
responses, every stored answer is one of the item's options, and enough of them exist:

1. **measured, never modelled** -- the field's provenance is observed or donor-matched
   (:attr:`~..population.policy.ProvenanceClass.is_measured`); a calibrated or modelled field
   is a model, and a model scored against a model proves nothing;
2. **closed** -- the bank already refuses an item outside 2-11 options; here every stored
   value must be one of its codes (``value_not_an_option``), never coerced;
3. **answered** -- at least :data:`MIN_COVERAGE` of the weighted rows the survey asked hold an
   answer;
4. **supported** -- at least :data:`MIN_EFFECTIVE_DONORS` effective donors (Kish, over the
   donor behind the answer: ``core_donor_id`` for a core field, ``_donor_<block>_id`` for a
   matched block's) among the rows that answered;
5. **not given** -- not a field the respondent is told: the sampler's quota fields and the
   exact age, a fact the factual layer answers by code, or an audience dimension.

Each assessment lists every rule an item fails, not only the first, so the bank's compiler
sees what to fix. Near-duplicates (rule 6) are a property of a pair, and are settled when the
pool is drawn.

Pure: stdlib only.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol, TypeGuard

from ..evidence.joint_status import CORE_BLOCKS
from ..panel_persona import FACT_COLUMNS
from ..population.audience import DERIVED_COLUMNS
from ..population.policy import FieldPolicy
from ..population.runtime import Cell
from ..population.sampling import DONOR_FIELD, QUOTA_FIELDS
from .bank import HoldoutItem, ItemBank

__all__ = [
    "AGE_FIELD",
    "GIVEN_FIELDS",
    "MIN_COVERAGE",
    "MIN_EFFECTIVE_DONORS",
    "HoldoutPopulation",
    "ItemAssessment",
    "assess_bank",
    "assess_item",
    "donor_field",
    "scored_rows",
]

#: At least 80 % of the weighted rows the survey asked hold an answer (7a, eligibility 3).
MIN_COVERAGE: Final = 0.80
#: 18.6.6's ``human_n >= 300`` (``validation_gate.py:28-46``), counted in donors (4e4).
MIN_EFFECTIVE_DONORS: Final = 300.0
#: The exact age: the persona's base line, and how a core item's measured range is read.
AGE_FIELD: Final = "vek"
#: What every respondent is told, so predicting it proves nothing (7a, eligibility 5).
GIVEN_FIELDS: Final = frozenset((*QUOTA_FIELDS, AGE_FIELD, *FACT_COLUMNS, *DERIVED_COLUMNS))
_NA_TOKENS: Final = frozenset({"", "NA", "NaN", "nan", "N/A", "<NA>", "None", "null"})


class HoldoutPopulation(Protocol):
    """What the holdout reads of a population; a loaded ``RuntimePopulation`` is one."""

    @property
    def fields(self) -> tuple[str, ...]: ...

    @property
    def field_policy(self) -> FieldPolicy: ...

    @property
    def analysis_weight(self) -> tuple[float, ...]: ...

    def column(self, name: str) -> tuple[Cell, ...]: ...


@dataclass(frozen=True, slots=True)
class ItemAssessment:
    """One item against one population: eligible, or every reason it is not."""

    field: str
    reasons: tuple[str, ...]
    #: The weighted share of the asked rows that hold an answer; ``None`` when not computable.
    coverage: float | None
    #: Effective donors behind the answers; ``None`` when not computable.
    effective_donors: float | None
    #: The donor column the support was counted over.
    donor_field: str | None

    @property
    def eligible(self) -> bool:
        """True when no rule failed."""
        return not self.reasons


def _present(cell: Cell) -> TypeGuard[str]:
    """A cell that holds an answer: present and not a not-answered token."""
    return cell is not None and cell.strip() not in _NA_TOKENS


def donor_field(population: HoldoutPopulation, field: str) -> str | None:
    """The column naming the donor whose answer ``field`` holds, or ``None`` if the
    population's dictionary does not place the field in a block."""
    entry = population.field_policy.entry(field)
    if entry is None or not entry.block:
        return None
    return DONOR_FIELD if entry.block in CORE_BLOCKS else f"_donor_{entry.block}_id"


def _age(cell: Cell) -> float | None:
    if not _present(cell):
        return None
    try:
        age = float(cell)
    except ValueError:
        return None
    return age if math.isfinite(age) else None


def scored_rows(population: HoldoutPopulation, item: HoldoutItem) -> tuple[int, ...]:
    """The rows whose answer to ``item`` is real: every row for a matched block, the rows in
    the measured age range for a core item. A row whose age is unknown is never in a range."""
    if item.measured_ages is None:
        return tuple(range(len(population.analysis_weight)))
    low, high = item.measured_ages
    ages = population.column(AGE_FIELD)
    return tuple(
        i for i, cell in enumerate(ages) if (a := _age(cell)) is not None and low <= a <= high
    )


def _kish(weights: Sequence[float]) -> float:
    total = math.fsum(weights)
    squares = math.fsum(w * w for w in weights)
    return total * total / squares if squares > 0 else 0.0


def assess_item(population: HoldoutPopulation, item: HoldoutItem) -> ItemAssessment:
    """Assess one item. Never raises for a population that lacks what the item needs: that is
    a reason, listed."""
    reasons: list[str] = []
    name = item.field
    if name in GIVEN_FIELDS:
        reasons.append("given_to_respondent")
    if name not in population.fields:
        return ItemAssessment(name, (*reasons, "not_in_population"), None, None, None)
    entry = population.field_policy.entry(name)
    if entry is None or not entry.provenance_class.is_measured:
        reasons.append("not_measured")
    if item.measured_ages is not None and AGE_FIELD not in population.fields:
        return ItemAssessment(name, (*reasons, "age_unknown"), None, None, None)

    cells = population.column(name)
    weights = population.analysis_weight
    rows = scored_rows(population, item)
    codes = frozenset(item.codes)
    answered: list[int] = []
    off_option = False
    for i in rows:
        cell = cells[i]
        if _present(cell):
            answered.append(i)
            off_option = off_option or cell.strip() not in codes
    if off_option:
        reasons.append("value_not_an_option")

    asked_weight = math.fsum(weights[i] for i in rows)
    coverage = math.fsum(weights[i] for i in answered) / asked_weight if asked_weight > 0 else None
    if coverage is None or coverage < MIN_COVERAGE:
        reasons.append("low_coverage")

    donors = donor_field(population, name)
    effective: float | None = None
    if donors is None or donors not in population.fields:
        reasons.append("donor_unknown")
    else:
        donor_cells = population.column(donors)
        per_donor: dict[str, float] = {}
        unknown = False
        for i in answered:
            donor = donor_cells[i]
            if not _present(donor):
                unknown = True
                break
            per_donor[donor] = per_donor.get(donor, 0.0) + weights[i]
        if unknown:
            reasons.append("donor_unknown")
        else:
            effective = _kish(list(per_donor.values()))
            if effective < MIN_EFFECTIVE_DONORS:
                reasons.append("low_support")
    return ItemAssessment(name, tuple(reasons), coverage, effective, donors)


def assess_bank(population: HoldoutPopulation, bank: ItemBank) -> tuple[ItemAssessment, ...]:
    """Every item of ``bank`` against ``population``, in bank order."""
    return tuple(assess_item(population, item) for item in bank.items)
