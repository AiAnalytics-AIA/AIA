"""Sociomapa systémů, futures against the real world (decision SM11, answers Q-FUTSCALE).

Each future the model computes for a quantity (a diesel price, a rent, a wage) is placed against
what really happened to the same quantity: its percentile among realised changes over the same
horizon in EU countries since 2000. Without history, against a range a named person declares.
Without either, by the futures' own spread, flagged. When the futures are much narrower or wider
than history, a warning is printed: the model then under- or over-states the risk.

Pure: no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = ["DeclaredRange", "ScaledFutures", "scale_futures"]

Floats = NDArray[np.float64]

WIDTH_WARNING = (0.5, 2.0)
"""The futures' 5-95 % width over history's: outside this band the warning is printed."""


@dataclass(frozen=True)
class DeclaredRange:
    low: float
    high: float
    author: str


@dataclass(frozen=True)
class ScaledFutures:
    positions: Floats
    """Each future on 0-1: its percentile in history, its place in the declared range, or its
    place in the futures' own spread."""
    method: str
    """``history``, ``declared`` or ``own spread (flagged)``."""
    source: str
    warning: str | None


def scale_futures(
    futures: Floats,
    *,
    history: Floats | None = None,
    history_source: str = "",
    declared: DeclaredRange | None = None,
) -> ScaledFutures:
    f = np.asarray(futures, float)
    if history is not None and np.asarray(history).size > 0:
        h = np.sort(np.asarray(history, float))
        positions = np.searchsorted(h, f, side="right") / h.size
        width_f = np.subtract(*np.quantile(f, [0.95, 0.05]))
        width_h = np.subtract(*np.quantile(h, [0.95, 0.05]))
        warning = None
        if width_h > 0:
            ratio = width_f / width_h
            if ratio < WIDTH_WARNING[0]:
                warning = f"the futures are {ratio:.2f} times as wide as history: risk understated"
            elif ratio > WIDTH_WARNING[1]:
                warning = f"the futures are {ratio:.2f} times as wide as history: risk overstated"
        return ScaledFutures(positions, "history", history_source, warning)
    if declared is not None:
        if declared.high <= declared.low:
            raise ValueError("a declared range needs high above low")
        positions = np.clip((f - declared.low) / (declared.high - declared.low), 0.0, 1.0)
        return ScaledFutures(positions, "declared", declared.author, None)
    span = f.max() - f.min()
    positions = (f - f.min()) / span if span > 0 else np.full(f.size, 0.5)
    return ScaledFutures(
        positions,
        "own spread (flagged)",
        "the futures themselves",
        "no real-world scale: own spread only",
    )
