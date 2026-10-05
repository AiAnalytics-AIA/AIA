"""The H-Model's reported fit: how well a 2-D layout represents a fuzzy matrix.

The H-Model ("horizontal model") places a fuzzy matrix's elements in the plane "so that their
distances in the plane correspond to the distances in the fuzzy matrix, keeping the
asymmetry"; its **accuracy is Spearman's rank correlation between the matrix of Euclidean
distances and the fuzzy matrix** (SOMECS help p. 53; evidence register SOMECS-H1, SOMECS-H3).
The certification material states the same criterion from each person's side: "the points
are placed, as far as possible, so that the distances from one point to the others follow the
order of that person's ratings of the others" (p. 12; QED-H2).

This module is the **reported accuracy only**. It is deliberately separate from the fitting
objective (how a layout is searched for), which is not chosen yet: see
``docs/architecture/sociomapping-hmodel.md``. A layout from any source -- SOMECS's own
coordinates, a test, a future optimiser -- is scored the same way.

Definitions (``docs/architecture/sociomapping-hmodel.md`` § 2 gives the reasoning):

* **Direction.** Relations are similarities (higher = closer) and distances are distances,
  so a good layout has a *negative* rank correlation between them. Accuracy is the Spearman
  correlation between the relations ``v_rs`` and the *negated* distances ``-d_rs``: +1 is a
  perfect order, 0 none.
* **Which cells.** Every ordered pair ``r != s``. A directed relation enters as its own
  observation; ``v_rs`` and ``v_sr`` share the one distance ``d_rs``. For a symmetric matrix
  this equals the correlation over unordered pairs (each pair counted once).
* **Ties.** Average ranks; Spearman is Pearson's r of the ranks. A side with every value
  equal has no rank correlation: accuracy is ``None``, with the reason.
* **Per-point fit.** For element ``r``, the same correlation over its own row: its
  relations to the others against its distances to them. ``None`` for a constant row.
* **Overall vs per-point.** The overall accuracy is *not* the mean of the per-point
  values; both are reported, and ``mean_per_point`` is labelled as what it is.

Inferred, not documented (register SOMECS-H3): that "the" Spearman is over all off-diagonal
cells rather than averaged per row; that ties take average ranks. SOMECS's own estimation
screen (SOMECS Input tutorial p. 21) gives one generated matrix with its 2-D coordinates;
the overall definition gives 0.786 on them, inside a list of SOMECS accuracies that holds
0.785, while the mean per-row value is 0.723 (``test_sociomapping_hmodel_accuracy``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Self

from pydantic import model_validator

from .fuzzy import FuzzyMatrix, FuzzyMatrixError
from .models import _Frozen

__all__ = [
    "HModelAccuracy",
    "average_ranks",
    "hmodel_accuracy",
    "spearman",
]

_ACCURACY_RULES = ("SOMECS-H3", "AIA-H4")


class HModelAccuracy(_Frozen):
    """The reported fit of one layout to one fuzzy matrix."""

    element_ids: tuple[str, ...]
    accuracy: float | None
    accuracy_undefined: str | None
    ordered_pairs: int
    per_point: tuple[float | None, ...]
    per_point_undefined: tuple[str | None, ...]
    mean_per_point: float | None
    defined_points: int
    rules: tuple[str, ...]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        n = len(self.element_ids)
        if len(self.per_point) != n or len(self.per_point_undefined) != n:
            raise ValueError("one per-point value and reason per element")
        if (self.accuracy is None) == (self.accuracy_undefined is None):
            raise ValueError("an accuracy is a number or a reason, never both or neither")
        for value, reason in zip(self.per_point, self.per_point_undefined, strict=True):
            if (value is None) == (reason is None):
                raise ValueError("a per-point fit is a number or a reason, never both or neither")
        return self


def average_ranks(values: Sequence[float]) -> list[float]:
    """1-based ranks, ties sharing the mean of the ranks they span."""
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Spearman's rho with average ranks; ``None`` when either side has no variation."""
    if len(x) != len(y):
        raise ValueError("Spearman needs paired values")
    if len(x) < 2 or len(set(x)) == 1 or len(set(y)) == 1:
        return None  # no variation, decided on the values, not on a rounded sum
    rx, ry = average_ranks(x), average_ranks(y)
    mx, my = math.fsum(rx) / len(rx), math.fsum(ry) / len(ry)
    sxx = math.fsum((a - mx) ** 2 for a in rx)
    syy = math.fsum((b - my) ** 2 for b in ry)
    sxy = math.fsum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    return max(-1.0, min(1.0, sxy / math.sqrt(sxx * syy)))


def hmodel_accuracy(
    matrix: FuzzyMatrix, positions: Sequence[tuple[float, float]]
) -> HModelAccuracy:
    """Score a layout against a fuzzy matrix as defined in the module docstring."""
    n = matrix.size
    if len(positions) != n:
        raise FuzzyMatrixError(f"{len(positions)} positions for {n} elements")
    points: list[tuple[float, float]] = []
    for k, point in enumerate(positions):
        if len(point) != 2:
            raise FuzzyMatrixError(f"position {k} must be (x, y)")
        x, y = float(point[0]), float(point[1])
        if not (math.isfinite(x) and math.isfinite(y)):
            raise FuzzyMatrixError(f"position {k} must be finite")
        points.append((x, y))
    distance = [[math.dist(points[r], points[s]) for s in range(n)] for r in range(n)]

    relations: list[float] = []
    closeness: list[float] = []
    for r in range(n):
        for s in range(n):
            if r != s:
                relations.append(matrix.relation(r, s))
                closeness.append(-distance[r][s])
    accuracy = spearman(relations, closeness)
    accuracy_undefined = None
    if accuracy is None:
        accuracy_undefined = _why(relations, closeness)

    per_point: list[float | None] = []
    reasons: list[str | None] = []
    for r in range(n):
        others = [s for s in range(n) if s != r]
        row = [matrix.relation(r, s) for s in others]
        near = [-distance[r][s] for s in others]
        value = spearman(row, near)
        per_point.append(value)
        reasons.append(None if value is not None else _why(row, near))
    defined = [v for v in per_point if v is not None]
    return HModelAccuracy(
        element_ids=matrix.element_ids,
        accuracy=accuracy,
        accuracy_undefined=accuracy_undefined,
        ordered_pairs=len(relations),
        per_point=tuple(per_point),
        per_point_undefined=tuple(reasons),
        mean_per_point=sum(defined) / len(defined) if defined else None,
        defined_points=len(defined),
        rules=(*matrix.rules, *_ACCURACY_RULES),
    )


def _why(relations: Sequence[float], closeness: Sequence[float]) -> str:
    if len(relations) < 2:
        return "fewer than two pairs"
    if len(set(relations)) == 1:
        return "every relation is equal"
    return "every distance is equal"
