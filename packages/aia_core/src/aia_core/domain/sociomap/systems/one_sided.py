"""Sociomapa systémů, one-sided relations (decision SM15, answers Q-ONEWAY).

On Konkurence (A covers B) and Vlivy (A drives B) a relation can run one way. The layout uses the
mean of both directions, so positions stay readable and stable. The direction is drawn as an arrow
on the line, and only when the asymmetry passes its test: the difference A->B minus B->A, redrawn
over resampled raters or rows, must keep its sign in the central ``level`` share of the redraws.
The arrow runs from the driver to the driven, or from the coverer to the covered.

Pure: no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = ["Arrow", "arrows_that_pass", "symmetric_part"]

Floats = NDArray[np.float64]


def symmetric_part(matrix: Floats) -> Floats:
    """The mean of both directions, the input to the layout."""
    m = np.asarray(matrix, float)
    mean: Floats = (m + m.T) / 2
    return mean


@dataclass(frozen=True)
class Arrow:
    source: int
    target: int
    difference: float
    """Observed source->target minus target->source."""
    interval: tuple[float, float]


def arrows_that_pass(
    observed: Floats, redraws: Floats, *, level: float = 0.95
) -> tuple[Arrow, ...]:
    """Arrows for the pairs whose asymmetry keeps its sign across the redraws.

    ``observed`` is n x n with ``observed[i, j]`` the relation i -> j; ``redraws`` is
    redraws x n x n, the same matrix computed on resampled raters or rows.
    """
    m = np.asarray(observed, float)
    r = np.asarray(redraws, float)
    differences = r - np.transpose(r, (0, 2, 1))
    low, high = np.quantile(differences, [(1 - level) / 2, (1 + level) / 2], axis=0)
    arrows = []
    for i in range(m.shape[0]):
        for j in range(i + 1, m.shape[0]):
            d = float(m[i, j] - m[j, i])
            if low[i, j] > 0:
                arrows.append(Arrow(i, j, d, (float(low[i, j]), float(high[i, j]))))
            elif high[i, j] < 0:
                arrows.append(Arrow(j, i, -d, (float(-high[i, j]), float(-low[i, j]))))
    return tuple(arrows)
