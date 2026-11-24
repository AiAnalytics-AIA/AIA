"""Sociomapa systémů, the minimum rows of each map input (decision SM13, answers Q-MINROWS).

An input's minimum is the smallest row count at which its planted-answer test meets the rates
declared for it in advance: planted groups found, false pairs in a no-relation world, stability
of the layout. Below the minimum the input is shown as a table, never a map, and the refusal names
the input and its minimum; the minimum is printed on every map. Until an input's test has run,
the starting minimums below hold.

Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

__all__ = [
    "STARTING_MINIMUM",
    "DeclaredRates",
    "PlantedRun",
    "RowsCheck",
    "check_rows",
    "minimum_rows",
]

STARTING_MINIMUM: dict[str, int] = {"months": 36, "experts": 12}
"""Until each input's planted-answer test has run (SM12, Aram's question 13)."""


@dataclass(frozen=True)
class DeclaredRates:
    """Stated before the planted-answer test is run (Aram's question 7)."""

    min_groups_found: float
    max_false_pair_rate: float
    min_stability: float


@dataclass(frozen=True)
class PlantedRun:
    """One planted-answer replicate at ``rows`` rows."""

    rows: int
    groups_found: float
    false_pair_rate: float
    stability: float

    def passes(self, rates: DeclaredRates) -> bool:
        return (
            self.groups_found >= rates.min_groups_found
            and self.false_pair_rate <= rates.max_false_pair_rate
            and self.stability >= rates.min_stability
        )


def minimum_rows(runs: Iterable[PlantedRun], rates: DeclaredRates) -> int | None:
    """The smallest tested row count from which every tested count passes (every replicate at
    that count and at every larger one); None when the largest tested count does not pass."""
    by_rows: dict[int, list[PlantedRun]] = {}
    for run in runs:
        by_rows.setdefault(run.rows, []).append(run)
    minimum = None
    for rows in sorted(by_rows, reverse=True):
        if all(run.passes(rates) for run in by_rows[rows]):
            minimum = rows
        else:
            break
    return minimum


@dataclass(frozen=True)
class RowsCheck:
    input_name: str
    rows: int
    minimum: int
    drawable: bool
    message: str
    """Printed on the map, or as the named refusal above the table."""


def check_rows(input_name: str, rows: int, minimum: int) -> RowsCheck:
    if rows >= minimum:
        return RowsCheck(
            input_name, rows, minimum, True, f"{input_name}: {rows} rows (minimum {minimum})"
        )
    return RowsCheck(
        input_name,
        rows,
        minimum,
        False,
        f"{input_name}: {rows} rows, below its minimum of {minimum}; shown as a table, not a map",
    )
