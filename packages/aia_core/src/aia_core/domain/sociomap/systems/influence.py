"""Sociomapa systémů, Vlivy: rated influences between factors (decision SM17, answers Q-VLIVY).

Named raters score how strongly each factor affects each other factor on a declared ordinal scale,
independently, before any discussion. The map needs at least :data:`MIN_RATERS` raters (the
planted-driver test sets the final minimum, SM13); fewer raters give a table, not a map. The cells
are combined by their median. Agreement is Krippendorff's alpha (ordinal), printed; a cell whose
raters spread wider than a declared width is disputed and gets no line or arrow. A factor's height
is its total influence (direct and indirect) on the question's outcome factor; without an outcome
factor in the matrix, its driving power. The grade is always odhad, and where indicator data exist
the influences are checked against the month test (SM12).

Total influence follows DEMATEL: the direct matrix N, scaled by the larger of its greatest row and
column sum, gives T = N (I - N)^-1, the sum of all paths of every length.

Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "GRADE",
    "MIN_RATERS",
    "InfluenceMap",
    "TooFewRaters",
    "influence_map",
    "krippendorff_alpha",
    "total_influence",
]

Floats = NDArray[np.float64]
Metric = Literal["nominal", "ordinal", "interval"]

MIN_RATERS = 5
GRADE = "odhad"


class TooFewRaters(ValueError):
    """Fewer than the minimum raters: show the ratings as a table, not a map."""


def krippendorff_alpha(data: Floats, metric: Metric = "ordinal") -> float:
    """Krippendorff's alpha for ``data`` = raters x units, NaN where a rater gave no value.

    Units with fewer than two values are not pairable and are left out (Krippendorff 2011,
    "Computing Krippendorff's alpha-reliability")."""
    d = np.asarray(data, float)
    values = np.unique(d[~np.isnan(d)])
    index = {v: i for i, v in enumerate(values)}
    k = values.size
    coincidence = np.zeros((k, k))
    for unit in d.T:
        present = unit[~np.isnan(unit)]
        m = present.size
        if m < 2:
            continue
        counts = np.zeros(k)
        for v in present:
            counts[index[v]] += 1
        coincidence += (np.outer(counts, counts) - np.diag(counts)) / (m - 1)
    totals = coincidence.sum(1)
    n = totals.sum()
    if n == 0:
        return float("nan")
    delta = _distances(values, totals, metric)
    observed = (coincidence * delta).sum()
    expected = (np.outer(totals, totals) * delta).sum() / (n - 1)
    return float(1 - observed / expected) if expected > 0 else 1.0


def _distances(values: Floats, totals: Floats, metric: Metric) -> Floats:
    k = values.size
    if metric == "nominal":
        return 1.0 - np.eye(k)
    if metric == "interval":
        return np.asarray((values[:, None] - values[None, :]) ** 2, float)
    if metric == "ordinal":
        delta = np.zeros((k, k))
        for c in range(k):
            for e in range(k):
                low, high = min(c, e), max(c, e)
                delta[c, e] = (totals[low : high + 1].sum() - (totals[c] + totals[e]) / 2) ** 2
        return delta
    raise ValueError(f"unknown metric {metric!r}")


def total_influence(direct: Floats) -> Floats:
    """DEMATEL's total relation matrix T = N (I - N)^-1 of the direct matrix (zero diagonal)."""
    a = np.asarray(direct, float).copy()
    np.fill_diagonal(a, 0.0)
    scale = max(a.sum(1).max(), a.sum(0).max())
    if scale <= 0:
        return np.zeros_like(a)
    n = a / scale
    total: Floats = n @ np.linalg.inv(np.eye(a.shape[0]) - n)
    return total


@dataclass(frozen=True)
class InfluenceMap:
    combined: Floats
    """The median rating per cell (factors x factors, ``[i, j]`` = influence of i on j)."""
    alpha: float
    disputed: NDArray[np.bool_]
    """Cells whose raters spread wider than the declared width: no line, no arrow."""
    heights: Floats
    height_rule: str
    raters: int
    grade: str = GRADE


def influence_map(
    ratings: Floats,
    *,
    disputed_width: float,
    outcome: int | None,
    spread: Callable[[Floats], Floats] | None = None,
) -> InfluenceMap:
    """``ratings`` is raters x factors x factors. ``disputed_width`` is declared before the
    ratings are seen; ``spread`` measures the raters' spread per cell (default: interquartile
    range). ``outcome`` is the question's outcome factor, or None."""
    r = np.asarray(ratings, float)
    if r.ndim != 3 or r.shape[1] != r.shape[2]:
        raise ValueError("ratings must be raters x factors x factors")
    raters, factors = r.shape[0], r.shape[1]
    if raters < MIN_RATERS:
        raise TooFewRaters(f"{raters} raters; a Vlivy map needs at least {MIN_RATERS}")
    combined = np.nanmedian(r, axis=0)
    np.fill_diagonal(combined, 0.0)
    off = ~np.eye(factors, dtype=bool)
    alpha = krippendorff_alpha(r[:, off], "ordinal")
    if spread is None:
        q1, q3 = np.nanquantile(r, [0.25, 0.75], axis=0)
        cell_spread = q3 - q1
    else:
        cell_spread = spread(r)
    disputed = (cell_spread > disputed_width) & off
    total = total_influence(combined)
    if outcome is None:
        heights, rule = total.sum(1), "driving power: total influence on every factor"
    else:
        if not 0 <= outcome < factors:
            raise ValueError("outcome must name a factor")
        heights = total[:, outcome].copy()
        heights[outcome] = np.nan
        rule = "total influence on the question's outcome factor"
    return InfluenceMap(combined, alpha, disputed, heights, rule, raters)
