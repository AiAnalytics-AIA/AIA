"""The validation's code baselines, L0 and L1 (7a, "The arms"; 7d).

Neither calls a model. Both read the item's own column, which no client question has, so they
do not decide the verdict: they say how much of what the panel already knows the model
recovers.

- **L0** predicts, for everyone, the population's weighted distribution of the item on the rows
  it is scored on.
- **L1** predicts, for each respondent, the weighted distribution of the item among the
  population's rows in the respondent's sex x age group x education x region cell, with every
  row of the respondent's own donor left out (so a respondent never predicts themselves). A cell
  with fewer than :data:`MIN_CELL_DONORS` other donors backs off a level: region, then
  education, then age group, then sex, then the whole population.

A baseline's prediction is a probability vector per respondent. Its metrics are taken from the
expected marginal (the weighted mean of those vectors), not a draw: code has no sampling noise
to show.

Pure: stdlib only.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from typing import Final

from ..population.runtime import Cell
from ..population.sampling import DONOR_FIELD
from .bank import HoldoutItem
from .eligibility import HoldoutPopulation, donor_field, scored_rows
from .scoring import MIN_CELL_DONORS as MIN_SUBGROUP_DONORS
from .scoring import ItemMetrics, ItemTruth, Respondent

__all__ = [
    "CELL_FIELDS",
    "MIN_CELL_DONORS",
    "Predictions",
    "baseline_metrics",
    "l0_predictions",
    "l1_predictions",
]

#: The L1 cell, finest first; each backoff drops the last field.
CELL_FIELDS: Final = ("pohlavi", "vek_skupina", "vzdelani", "kraj")
#: 7a: a cell with fewer other donors than this backs off a level.
MIN_CELL_DONORS: Final = 30
_NA_TOKENS: Final = frozenset({"", "NA", "NaN", "nan", "N/A", "<NA>", "None", "null"})

#: ``(item, respondent) -> probabilities in the item's code order``.
Predictions = Mapping[tuple[str, str], tuple[float, ...]]


def _value(cell: Cell) -> str | None:
    if cell is None:
        return None
    text = cell.strip()
    return None if text in _NA_TOKENS else text


def _normalised(counts: Mapping[str, float], codes: Sequence[str]) -> tuple[float, ...] | None:
    total = math.fsum(counts.get(c, 0.0) for c in codes)
    if total <= 0:
        return None
    return tuple(counts.get(c, 0.0) / total for c in codes)


def l0_predictions(
    population: HoldoutPopulation,
    items: Sequence[HoldoutItem],
    sample_rows: Mapping[str, int],
) -> dict[tuple[str, str], tuple[float, ...]]:
    """Everyone's L0 prediction: the item's weighted population distribution."""
    weights = population.analysis_weight
    out: dict[tuple[str, str], tuple[float, ...]] = {}
    for item in items:
        column = population.column(item.field)
        counts: dict[str, float] = {}
        for i in scored_rows(population, item):
            v = _value(column[i])
            if v is not None:
                counts[v] = counts.get(v, 0.0) + weights[i]
        marginal = _normalised(counts, item.codes)
        if marginal is None:
            raise ValueError(f"{item.field} has no answer in the population")
        for respondent in sample_rows:
            out[(item.field, respondent)] = marginal
    return out


def l1_predictions(
    population: HoldoutPopulation,
    items: Sequence[HoldoutItem],
    sample_rows: Mapping[str, int],
) -> dict[tuple[str, str], tuple[float, ...]]:
    """Each respondent's L1 prediction: their cell's distribution without their own donor."""
    weights = population.analysis_weight
    cells = {name: population.column(name) for name in CELL_FIELDS if name in population.fields}
    levels = [CELL_FIELDS[:k] for k in range(len(CELL_FIELDS), -1, -1)]

    def key(row: int, fields: Sequence[str]) -> tuple[str | None, ...]:
        return tuple(_value(cells[f][row]) if f in cells else None for f in fields)

    out: dict[tuple[str, str], tuple[float, ...]] = {}
    for item in items:
        column = population.column(item.field)
        donors_name = donor_field(population, item.field) or DONOR_FIELD
        donors = population.column(donors_name)
        rows = [i for i in scored_rows(population, item) if _value(column[i]) is not None]
        # Per level: key -> code -> weight, and key -> donor -> code -> weight (to leave one out).
        totals: list[dict[tuple[str | None, ...], dict[str, float]]] = []
        by_donor: list[dict[tuple[str | None, ...], dict[str, dict[str, float]]]] = []
        for fields in levels:
            t: dict[tuple[str | None, ...], dict[str, float]] = {}
            b: dict[tuple[str | None, ...], dict[str, dict[str, float]]] = {}
            for i in rows:
                k = key(i, fields)
                code = _value(column[i])
                donor = _value(donors[i]) or f"row-{i}"
                assert code is not None
                t.setdefault(k, {})[code] = t.setdefault(k, {}).get(code, 0.0) + weights[i]
                per = b.setdefault(k, {}).setdefault(donor, {})
                per[code] = per.get(code, 0.0) + weights[i]
            totals.append(t)
            by_donor.append(b)
        for respondent, row in sample_rows.items():
            own = _value(donors[row]) or f"row-{row}"
            prediction: tuple[float, ...] | None = None
            for level, fields in enumerate(levels):
                k = key(row, fields)
                donors_here = by_donor[level].get(k, {})
                others = len(donors_here) - (1 if own in donors_here else 0)
                if others < MIN_CELL_DONORS and level < len(levels) - 1:
                    continue
                counts = dict(totals[level].get(k, {}))
                for code, w in donors_here.get(own, {}).items():
                    counts[code] = counts.get(code, 0.0) - w
                prediction = _normalised(counts, item.codes)
                if prediction is not None:
                    break
            if prediction is None:
                raise ValueError(f"{item.field} has no answer outside {respondent}'s own donor")
            out[(item.field, respondent)] = prediction
    return out


def _expected(
    truth: ItemTruth, predictions: Predictions, members: Sequence[Respondent]
) -> dict[str, float]:
    total = math.fsum(r.weight for r in members)
    out = dict.fromkeys(truth.codes, 0.0)
    for r in members:
        for code, p in zip(truth.codes, predictions[(truth.item, r.respondent_id)], strict=True):
            out[code] += r.weight * p / total
    return out


def _true(truth: ItemTruth, members: Sequence[Respondent]) -> dict[str, float]:
    total = math.fsum(r.weight for r in members)
    out = dict.fromkeys(truth.codes, 0.0)
    for r in members:
        out[truth.answers[r.respondent_id]] += r.weight / total
    return out


def _tvd(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    return 50.0 * math.fsum(abs(a[c] - b[c]) for c in a)


def _entropy(p: Mapping[str, float]) -> float:
    return -math.fsum(v * math.log2(v) for v in p.values() if v > 0)


def baseline_metrics(
    truths: Sequence[ItemTruth], respondents: Sequence[Respondent], predictions: Predictions
) -> tuple[ItemMetrics, ...]:
    """A code baseline's metrics per item, from its expected marginal."""
    out = []
    for truth in truths:
        scored = [r for r in respondents if r.respondent_id in truth.answers]
        true = _true(truth, scored)
        expected = _expected(truth, predictions, scored)
        cells: dict[str, list[Respondent]] = {}
        for r in scored:
            if r.cell is not None:
                cells.setdefault(r.cell, []).append(r)
        cell_tvds = [
            _tvd(_expected(truth, predictions, m), _true(truth, m))
            for m in cells.values()
            if len({r.donor_id for r in m}) >= MIN_SUBGROUP_DONORS
        ]
        brier = None
        if truth.person_level:
            total = math.fsum(r.weight for r in scored)
            brier = (
                math.fsum(
                    r.weight
                    * math.fsum(
                        (p - (1.0 if c == truth.answers[r.respondent_id] else 0.0)) ** 2
                        for c, p in zip(
                            truth.codes, predictions[(truth.item, r.respondent_id)], strict=True
                        )
                    )
                    for r in scored
                )
                / total
            )
        out.append(
            ItemMetrics(
                item=truth.item,
                domain=truth.domain,
                tvd=_tvd(expected, true),
                subgroup_tvd=statistics.fmean(cell_tvds) if cell_tvds else None,
                brier=brier,
                entropy_gap=_entropy(expected) - _entropy(true),
            )
        )
    return tuple(out)
