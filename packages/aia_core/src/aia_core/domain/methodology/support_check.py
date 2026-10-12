"""What an edited support rule does, before it is put in force (ADR 0023 decision 10, plan G1d).

The draft and the support rules in force decide the same fixed fictional cells side by side,
through the functions a run decides with: Results' status through
``research_aggregate.donor_support`` under each specification's ``results`` rule, and
analysis' through ``analysis.native.reassess_support`` under its ``analysis`` rule (the
stricter of the two wins, as in a run). Every cell is listed with both statuses on both
surfaces, and every cell a draft newly reports (it was suppressed, now a number shows) or
newly suppresses (a number showed, now it does not) is named.

The cells are generated here from fixed seeds (``random.Random``): four fictional panels of
different size, donor pool and weighting, each asked four questions answered by a different
share of respondents, so the check spans thin to ample support and is the same every time it
is asked. They are AIA's own invention and say so; no client's data is read.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from ..analysis.native import reassess_support
from ..evidence.support import SupportSpec, SupportStatus
from ..research_aggregate import donor_support
from .pins import support_spec_for

__all__ = [
    "SUPPORT_CHECK_CELLS",
    "CellComparison",
    "CheckCell",
    "SupportComparison",
    "compare_support",
    "compare_support_with_in_force",
]

_SUPPRESS: Final = SupportStatus.SUPPRESS.value


@dataclass(frozen=True, slots=True)
class CheckCell:
    """One fictional cell: who was asked, from how many donors, how weighted, how many answered."""

    id: str
    label_cs: str
    seed: int
    respondents: int
    donors: int
    weights: tuple[float, float] | None  # None: equal weights
    answered: float

    def sample(self) -> tuple[list[str], list[float]]:
        """The donors and weights of those who answered, drawn by the cell's seed."""
        rng = random.Random(self.seed)
        donors: list[str] = []
        weights: list[float] = []
        for _ in range(self.respondents):
            donor = f"d{rng.randrange(self.donors)}"
            weight = 1.0 if self.weights is None else rng.uniform(*self.weights)
            if rng.random() < self.answered:
                donors.append(donor)
                weights.append(weight)
        return donors, weights


_PANELS: Final = (
    ("maly", "Malý panel", 60, 24, None),
    ("stredni", "Střední panel", 150, 45, (0.6, 1.6)),
    ("velky", "Velký panel", 400, 120, (0.4, 2.5)),
    ("nevyvazeny", "Nevyvážený panel", 250, 80, (0.1, 4.0)),
)
_ANSWERED: Final = (
    (1.0, "odpověděli všichni"),
    (0.7, "odpovědělo 70 %"),
    (0.4, "odpovědělo 40 %"),
    (0.15, "odpovědělo 15 %"),
)

#: The fixed fictional cells every draft is checked on, in the order they are listed.
SUPPORT_CHECK_CELLS: Final = tuple(
    CheckCell(
        id=f"{panel}.q{q + 1}",
        label_cs=f"{label} (fiktivní) · otázka {q + 1}: {said}",
        seed=20261012 + 10 * p + q,
        respondents=respondents,
        donors=donors,
        weights=weights,
        answered=share,
    )
    for p, (panel, label, respondents, donors, weights) in enumerate(_PANELS)
    for q, (share, said) in enumerate(_ANSWERED)
)


@dataclass(frozen=True, slots=True)
class CellComparison:
    """One cell under the rules in force and under the draft, on both surfaces."""

    cell: str
    label_cs: str
    n: int
    effective_n: float
    donors: int
    results: tuple[str, str]  # (in force, draft)
    analysis: tuple[str, str]  # (in force, draft)

    def changes(self) -> dict[str, str]:
        """Each surface whose status moved: ``reported`` (a number now shows where none did),
        ``suppressed`` (a number no longer shows) or ``changed`` (shown either way, its
        status moved between INDIKATIVNÍ and REPORTOVATELNÉ)."""
        out: dict[str, str] = {}
        for surface, (before, after) in (("results", self.results), ("analysis", self.analysis)):
            if before == after:
                continue
            if before == _SUPPRESS:
                out[surface] = "reported"
            elif after == _SUPPRESS:
                out[surface] = "suppressed"
            else:
                out[surface] = "changed"
        return out


@dataclass(frozen=True, slots=True)
class SupportComparison:
    """A draft beside the rules in force, cell by cell."""

    in_force: str
    draft: str
    cells: tuple[CellComparison, ...]

    def moved(self, change: str) -> tuple[tuple[str, str], ...]:
        """Every ``(cell, surface)`` whose status moved by ``change``, in the cells' order."""
        return tuple(
            (c.cell, surface)
            for c in self.cells
            for surface, how in c.changes().items()
            if how == change
        )


def _decide(cell: CheckCell, spec: SupportSpec) -> tuple[dict[str, Any], str]:
    """The cell's aggregate support under ``spec.results`` and its analysis status under
    ``spec.analysis``, as a run decides them."""
    donors, weights = cell.sample()
    unit = donor_support(donors, weights, rule=spec.results)
    result = {
        "support_status": unit["support_status"],
        "n_platnych": unit["n"],
        "effective_n": unit["effective_n_combined"],
        "n_unique_layer_donors": unit["n_unique_layer_donors"],
    }
    return unit, reassess_support(result, spec.analysis).status.value


def compare_support(
    in_force: SupportSpec,
    draft: SupportSpec,
    cells: tuple[CheckCell, ...] = SUPPORT_CHECK_CELLS,
) -> SupportComparison:
    """``draft`` beside ``in_force`` on every cell: n, effective n and donors (which no rule
    changes) and each surface's status under each."""
    rows: list[CellComparison] = []
    for cell in cells:
        before, analysis_before = _decide(cell, in_force)
        after, analysis_after = _decide(cell, draft)
        rows.append(
            CellComparison(
                cell=cell.id,
                label_cs=cell.label_cs,
                n=int(before["n"]),
                effective_n=float(before["effective_n_combined"]),
                donors=int(before["n_unique_layer_donors"]),
                results=(str(before["support_status"]), str(after["support_status"])),
                analysis=(analysis_before, analysis_after),
            )
        )
    return SupportComparison(
        in_force=in_force.methodology_version,
        draft=draft.methodology_version,
        cells=tuple(rows),
    )


def compare_support_with_in_force(
    stored: Mapping[str, Any] | None, draft: Mapping[str, Any]
) -> SupportComparison:
    """A draft version payload beside what a run started now would pin: ``stored`` is the
    version in force's payload, ``None`` when the code's preset is in force."""
    return compare_support(support_spec_for(stored), support_spec_for(draft))
