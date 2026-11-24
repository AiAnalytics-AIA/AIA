"""Sociomapa systémů, how much an indicator matters (decision SM10, answers Q-IMPORT).

On maps whose points are indicators (Jednotky, Čas), height is how much the indicator matters for
the question (SM2). Where a tested model covers the question, it is the drop in the model's score
when the indicator is shuffled on test years the model never saw, with an interval: grade
doloženo. Where no tested model covers the question, it is a weight we declare, printed as odhad
with its author. Never the indicator's correlation with the outcome on the data the map is drawn
from: that is circular.

Pure: no I/O; the only randomness is numpy's seeded generators. The caller passes the frozen
model's predict function and the score (AUC, red-flag precision, ...) the question uses.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = ["IndicatorHeight", "declared_importance", "permutation_importance"]

Floats = NDArray[np.float64]


@dataclass(frozen=True)
class IndicatorHeight:
    indicator: str
    value: float
    interval: tuple[float, float] | None
    grade: str
    """``doloženo`` from a tested model on unseen years, ``odhad`` when declared."""
    source: str
    """The model and its test years, or the person who declared the weight."""


def permutation_importance(
    names: Sequence[str],
    x_test: Floats,
    y_test: Floats,
    predict: Callable[[Floats], Floats],
    score: Callable[[Floats, Floats], float],
    *,
    model: str,
    repeats: int = 200,
    seed: int,
    level: float = 0.95,
) -> tuple[IndicatorHeight, ...]:
    """The score drop per indicator over ``repeats`` shuffles, each on a bootstrap of the unseen
    test rows; ``model`` names the frozen model and its test years for the printed source."""
    x = np.asarray(x_test, float)
    y = np.asarray(y_test)
    if x.shape[1] != len(names):
        raise ValueError("one name per column of x_test")
    rng = np.random.default_rng(seed)
    drops = np.empty((len(names), repeats))
    for r in range(repeats):
        rows = rng.integers(0, x.shape[0], x.shape[0])
        base_x, base_y = x[rows], y[rows]
        base = score(base_y, predict(base_x))
        for column in range(len(names)):
            shuffled = base_x.copy()
            shuffled[:, column] = rng.permutation(shuffled[:, column])
            drops[column, r] = base - score(base_y, predict(shuffled))
    tails = [(1 - level) / 2, (1 + level) / 2]
    return tuple(
        IndicatorHeight(
            name,
            float(np.mean(drops[i])),
            (float(np.quantile(drops[i], tails[0])), float(np.quantile(drops[i], tails[1]))),
            "doloženo",
            model,
        )
        for i, name in enumerate(names)
    )


def declared_importance(
    weights: Mapping[str, float], *, author: str
) -> tuple[IndicatorHeight, ...]:
    """Heights from weights a named person declared, for questions no tested model covers."""
    if not author.strip():
        raise ValueError("a declared weight needs its author")
    if any(w < 0 for w in weights.values()):
        raise ValueError("weights must not be negative")
    return tuple(
        IndicatorHeight(name, float(w), None, "odhad", author) for name, w in weights.items()
    )
