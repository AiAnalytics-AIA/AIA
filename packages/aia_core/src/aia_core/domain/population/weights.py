"""Canonical analysis-weight resolution. No default column, no fallback, ever.

The reference had four independent weight paths and each degraded differently
(``methodology-ledger.md`` M01, fixture F11):

1. ``data_contract.weight()`` returned ``vaha_kalibrovana`` -- the Census 2021
   scheme -- for any unknown role or a missing weights map;
2. ``Panel.__init__`` fell back to ``vaha_kalibrovana`` when the declared column
   was absent, silently moving every result onto a different population basis;
3. ``Panel.__init__`` set every weight to ``1.0`` when that was absent too, making
   the population unweighted;
4. ``full_simulation.py`` and ``study_dataset.py`` each carried their own chain.

Here there is one path. A role resolves to exactly the column the contract
declares for it, or the resolution fails; a column resolves to exactly its values,
or the load fails. The reference's ``fillna(0).clip(lower=0)`` is **not** carried
forward: a null or negative weight in the chosen scheme is a defect in the data,
and zeroing it would quietly drop that respondent from every weighted estimate.
That is an INTENTIONAL_DIFFERENCE, recorded as such by the parity tier.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, model_validator

from .contract import PopulationImportContract
from .errors import WeightResolutionError

__all__ = [
    "SchemeSpec",
    "WeightResolution",
    "WeightingSpec",
    "analysis_weights",
    "parse_weight",
    "resolve_weight_scheme",
    "weighting_spec",
]

# A plain decimal, optionally signed, optionally with an exponent. Deliberately
# narrower than ``float()``, which also accepts "nan", "inf", "infinity",
# underscores ("1_000") and surrounding whitespace -- none of which is a weight.
_DECIMAL = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


@dataclass(frozen=True, slots=True)
class WeightResolution:
    """Which declared scheme backs the analysis weight, under which contract."""

    role: str
    column: str
    contract_id: str


def resolve_weight_scheme(
    contract: PopulationImportContract, role: str | None = None
) -> WeightResolution:
    """Resolve ``role`` -- or the contract's declared default -- to its column.

    ``None`` means "the contract's declared default", which is itself a declared
    fact of the contract and is recorded on every binding; it is not a fallback.
    An undeclared role raises. Nothing is guessed.
    """
    chosen = contract.default_weight_role if role is None else role
    scheme = contract.weight_scheme(chosen)
    return WeightResolution(
        role=scheme.role, column=scheme.column, contract_id=contract.contract_id
    )


def parse_weight(text: str) -> float:
    """Parse one weight cell exactly, or raise :class:`ValueError`.

    Finite, non-negative plain decimals only.
    """
    if not _DECIMAL.match(text):
        raise ValueError(f"not a plain decimal: {text!r}")
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"not finite: {text!r}")
    if value < 0:
        raise ValueError(f"negative: {text!r}")
    return value


def analysis_weights(
    cells: Sequence[str | None], resolution: WeightResolution
) -> tuple[float, ...]:
    """Return the analysis weight for every row, from the resolved column only.

    Refuses the whole column when any cell is null, malformed, non-finite or
    negative, or when the weights sum to zero. The error counts every defect so
    that one failure tells an operator the size of the problem.
    """
    values: list[float] = []
    nulls = 0
    bad: list[str] = []
    for cell in cells:
        if cell is None:
            nulls += 1
            continue
        try:
            values.append(parse_weight(cell))
        except ValueError:
            bad.append(cell)
    if nulls or bad:
        sample = ", ".join(repr(b) for b in bad[:3])
        raise WeightResolutionError(
            f"weight column {resolution.column} ({resolution.role}) is unusable: "
            f"{nulls} null and {len(bad)} malformed of {len(cells)} rows"
            + (f" (e.g. {sample})" if sample else ""),
            reason="unusable_weight",
        )
    if not values or math.fsum(values) <= 0:
        raise WeightResolutionError(
            f"weight column {resolution.column} ({resolution.role}) sums to zero",
            reason="unusable_weight",
        )
    return tuple(values)


# --------------------------------------------------------------------------- declared
#
# Plan ``methodology-tab.md`` W1a, ADR 0023 decision 2: what weighting rests on, declared in
# one specification the Metodika tab shows. Its preset is built from the import contract, so
# the schemes, the default role and the totals are the contract's own, never a copy that can
# drift from it.


class _Declared(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SchemeSpec(_Declared):
    """One scheme's column, and the population total an import must meet, where declared."""

    column: str
    expected_total: float | None
    tolerance: float | None

    @model_validator(mode="after")
    def _total_and_tolerance_together(self) -> SchemeSpec:
        if not self.column:
            raise ValueError("a scheme names its column")
        if (self.expected_total is None) != (self.tolerance is None):
            raise ValueError("an expected total and its tolerance go together")
        if self.expected_total is not None and not (
            math.isfinite(self.expected_total) and self.expected_total > 0
        ):
            raise ValueError("an expected total is a positive finite number")
        if self.tolerance is not None and not (
            math.isfinite(self.tolerance) and self.tolerance >= 0
        ):
            raise ValueError("a tolerance is a finite number, not negative")
        return self


class WeightingSpec(_Declared):
    """How AIA weights (plan ``methodology-tab.md`` W1a).

    ``schemes`` are keyed by role, in the contract's order; ``default_role`` is the scheme a
    binding records when none is chosen. The population's weights are the panel's own
    columns; what a run's sample does with them (the floor, raking to the audience's
    targets, the audit) is the sampler's, shown on the Metodika tab beside this
    (``methodology/weighting.py``, plan W1b).
    """

    methodology_version: str
    contract_id: str
    default_role: str
    schemes: dict[str, SchemeSpec]

    @model_validator(mode="after")
    def _the_default_is_declared(self) -> WeightingSpec:
        if not self.schemes:
            raise ValueError("a weighting declares at least one scheme")
        if self.default_role not in self.schemes:
            raise ValueError(
                f"the default role {self.default_role!r} is not a declared scheme; "
                f"declared: {sorted(self.schemes)}"
            )
        columns = [s.column for s in self.schemes.values()]
        if len(set(columns)) != len(columns):
            raise ValueError("two schemes name the same column")
        return self


def weighting_spec(
    contract: PopulationImportContract,
    *,
    methodology_version: str,
) -> WeightingSpec:
    """The weighting ``contract`` declares, as a specification: its schemes in its order,
    its default role, its totals and tolerances, exactly."""
    return WeightingSpec(
        methodology_version=methodology_version,
        contract_id=contract.contract_id,
        default_role=contract.default_weight_role,
        schemes={
            s.role: SchemeSpec(
                column=s.column, expected_total=s.expected_total, tolerance=s.tolerance
            )
            for s in contract.weight_schemes
        },
    )
