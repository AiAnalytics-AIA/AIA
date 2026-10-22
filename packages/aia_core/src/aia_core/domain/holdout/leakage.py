"""What a respondent is not given while a block of holdout items is asked (7a, "Leakage").

For each item, the persona of every arm leaves out:

1. the item itself;
2. for an item in a **matched block**, every field of that block: the block is one donor's
   answers, so a sibling carries the answer;
3. every persona field whose weighted association with the item, on the rows the item is
   scored on, reaches :data:`ASSOCIATION_THRESHOLD` -- |r| for two numeric fields when the
   item is ordinal, Cramér's V otherwise. An association that cannot be computed (no shared
   answered rows, or a field with one value there) is not read as "none": the field is left
   out, so the test is never easier for what AIA could not measure;
4. every catalog signal whose column is left out, or whose concept is an item's.

Items are asked in blocks, so a block's exclusion is the union over its items. The result
records, for every field left out, why, and the association that put it there: the
preregistration pins it, and nobody chooses an exclusion by hand.

Leaving out correlated fields makes the test harder than production, never easier.

Pure: stdlib only.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, TypeGuard

from ..evidence.joint_status import CORE_BLOCKS
from ..population.runtime import Cell
from .bank import HoldoutItem
from .eligibility import HoldoutPopulation, scored_rows

__all__ = [
    "ASSOCIATION_THRESHOLD",
    "BlockExclusion",
    "CatalogSignal",
    "ExcludedField",
    "ExclusionReason",
    "ParsedColumns",
    "association",
    "block_exclusion",
]

#: 7a: |r| or Cramér's V at or above this leaves a persona field out.
ASSOCIATION_THRESHOLD: Final = 0.30
_NA_TOKENS: Final = frozenset({"", "NA", "NaN", "nan", "N/A", "<NA>", "None", "null"})


class ExclusionReason(StrEnum):
    """Why a field is left out of a persona."""

    ITEM = "ITEM"
    MATCHED_BLOCK = "MATCHED_BLOCK"
    ASSOCIATED = "ASSOCIATED"
    ASSOCIATION_UNKNOWN = "ASSOCIATION_UNKNOWN"
    SIGNAL_CONCEPT = "SIGNAL_CONCEPT"


@dataclass(frozen=True, slots=True)
class CatalogSignal:
    """What the leakage rule reads of a persona catalog signal: its column and concept."""

    column: str
    concept: str


@dataclass(frozen=True, slots=True)
class ExcludedField:
    """One field left out, the item that put it out, and why."""

    field: str
    item: str
    reason: ExclusionReason
    #: The association that put it out (``ASSOCIATED`` only), rounded for the record.
    association: float | None = None


@dataclass(frozen=True, slots=True)
class BlockExclusion:
    """A block of items and everything its respondents are not given."""

    items: tuple[str, ...]
    excluded: tuple[ExcludedField, ...]
    #: The catalog signals' columns left out (their column excluded, or their concept an item's).
    signals: tuple[str, ...]

    @property
    def fields(self) -> frozenset[str]:
        """Every field left out, items included."""
        return frozenset(e.field for e in self.excluded) | frozenset(self.signals)


def _present(cell: Cell) -> TypeGuard[str]:
    """A cell that holds an answer: present and not a not-answered token."""
    return cell is not None and cell.strip() not in _NA_TOKENS


def _number(cell: Cell) -> float | None:
    if not _present(cell):
        return None
    try:
        value = float(cell)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _pearson(xs: Sequence[float], ys: Sequence[float], ws: Sequence[float]) -> float | None:
    # Two passes over centred values; plain sums are exact enough for a 0.30 / 0.70 threshold.
    total = sum(ws)
    if total <= 0:
        return None
    mx = sum([w * x for w, x in zip(ws, xs, strict=True)]) / total
    my = sum([w * y for w, y in zip(ws, ys, strict=True)]) / total
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    sxy = sum([w * a * b for w, a, b in zip(ws, dx, dy, strict=True)])
    sxx = sum([w * a * a for w, a in zip(ws, dx, strict=True)])
    syy = sum([w * b * b for w, b in zip(ws, dy, strict=True)])
    if sxx <= 0 or syy <= 0:
        return None
    return abs(sxy / math.sqrt(sxx * syy))


def _cramers_v(xs: Sequence[str], ys: Sequence[str], ws: Sequence[float]) -> float | None:
    total = math.fsum(ws)
    if total <= 0:
        return None
    joint: dict[tuple[str, str], float] = {}
    row: dict[str, float] = {}
    col: dict[str, float] = {}
    for x, y, w in zip(xs, ys, ws, strict=True):
        joint[(x, y)] = joint.get((x, y), 0.0) + w
        row[x] = row.get(x, 0.0) + w
        col[y] = col.get(y, 0.0) + w
    k = min(len(row), len(col))
    if k < 2:
        return None
    # phi^2 = sum p_ij^2 / (p_i p_j) - 1; invariant to the weights' scale.
    phi2 = (
        math.fsum(
            (p / total) ** 2 / ((row[x] / total) * (col[y] / total)) for (x, y), p in joint.items()
        )
        - 1.0
    )
    return math.sqrt(max(phi2, 0.0) / (k - 1))


@dataclass(frozen=True, slots=True)
class _Parsed:
    #: The stripped answer, ``None`` where missing.
    text: tuple[str | None, ...]
    #: The answer as a finite number, ``None`` where missing or not a number.
    number: tuple[float | None, ...]


class ParsedColumns:
    """Each column parsed once per computation: an association reads two columns, and a pool
    of items against a persona's fields reads the same ones thousands of times."""

    def __init__(self, population: HoldoutPopulation) -> None:
        self._population = population
        self._memo: dict[str, _Parsed] = {}

    @property
    def weights(self) -> tuple[float, ...]:
        """The population's analysis weight."""
        return self._population.analysis_weight

    def get(self, name: str) -> _Parsed:
        """``name``'s cells, parsed."""
        parsed = self._memo.get(name)
        if parsed is None:
            cells = self._population.column(name)
            text = tuple(c.strip() if _present(c) else None for c in cells)
            parsed = _Parsed(text=text, number=tuple(_number(t) for t in text))
            self._memo[name] = parsed
        return parsed


def association(
    population: HoldoutPopulation,
    item: HoldoutItem,
    field: str,
    rows: Sequence[int],
    *,
    columns: ParsedColumns | None = None,
) -> float | None:
    """The weighted association between ``item`` and ``field`` on ``rows``, both answered:
    |r| when the item is ordinal and both are numeric there, Cramér's V otherwise. ``None``
    when it cannot be computed. ``columns`` shares parsing across calls."""
    parsed = columns or ParsedColumns(population)
    a = parsed.get(item.field)
    b = parsed.get(field)
    weights = parsed.weights
    pairs = [i for i in rows if a.text[i] is not None and b.text[i] is not None]
    if not pairs:
        return None
    ws = [weights[i] for i in pairs]
    if item.ordinal:
        xs: list[float] = []
        ys: list[float] = []
        for i in pairs:
            x, y = a.number[i], b.number[i]
            if x is None or y is None:
                break
            xs.append(x)
            ys.append(y)
        else:
            return _pearson(xs, ys, ws)
    xt: list[str] = []
    yt: list[str] = []
    for i in pairs:
        s, t = a.text[i], b.text[i]
        if s is not None and t is not None:
            xt.append(s)
            yt.append(t)
    return _cramers_v(xt, yt, ws)


def block_exclusion(
    population: HoldoutPopulation,
    items: Sequence[HoldoutItem],
    persona_fields: Sequence[str],
    signals: Sequence[CatalogSignal] = (),
    *,
    columns: ParsedColumns | None = None,
) -> BlockExclusion:
    """Everything a block's respondents are not given.

    ``persona_fields`` are the columns a persona would read (the profile's and the catalog
    signals'); a field the population lacks is skipped, as the persona builder skips it.
    """
    policy = population.field_policy
    parsed = columns or ParsedColumns(population)
    item_names = {item.field for item in items}
    excluded: dict[str, ExcludedField] = {}

    def leave_out(entry: ExcludedField) -> None:
        excluded.setdefault(entry.field, entry)

    for item in items:
        leave_out(ExcludedField(item.field, item.field, ExclusionReason.ITEM))
    present = [f for f in dict.fromkeys(persona_fields) if f in population.fields]
    for item in items:
        entry = policy.entry(item.field)
        block = entry.block if entry is not None else ""
        rows = scored_rows(population, item)
        for name in present:
            if name in item_names or name in excluded:
                continue
            other = policy.entry(name)
            if block and block not in CORE_BLOCKS and other is not None and other.block == block:
                leave_out(ExcludedField(name, item.field, ExclusionReason.MATCHED_BLOCK))
                continue
            value = association(population, item, name, rows, columns=parsed)
            if value is None:
                leave_out(ExcludedField(name, item.field, ExclusionReason.ASSOCIATION_UNKNOWN))
            elif value >= ASSOCIATION_THRESHOLD:
                leave_out(
                    ExcludedField(name, item.field, ExclusionReason.ASSOCIATED, round(value, 6))
                )
    out = set(excluded)
    item_concepts = {s.concept for s in signals if s.column in item_names}
    dropped = []
    for signal in signals:
        if signal.column in out or signal.concept in item_concepts:
            dropped.append(signal.column)
            if signal.column not in out:
                source = next(
                    s.column
                    for s in signals
                    if s.concept == signal.concept and s.column in item_names
                )
                leave_out(ExcludedField(signal.column, source, ExclusionReason.SIGNAL_CONCEPT))
    ordered = tuple(sorted(excluded.values(), key=lambda e: (e.field, e.item)))
    return BlockExclusion(
        items=tuple(item.field for item in items),
        excluded=ordered,
        signals=tuple(sorted(set(dropped))),
    )
