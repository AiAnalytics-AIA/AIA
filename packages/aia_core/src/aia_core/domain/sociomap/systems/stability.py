"""Sociomapa systémů, how far each point moves when the rows are drawn again (decision SM14,
answers Q-LINES).

The rows are redrawn by a moving-block bootstrap (block length declared, so months keep their
order), each redrawn map is aligned onto the reference map by Procrustes (rotation, reflection,
translation, one scale), and each object's displacement is measured in units of the reference
map's root-mean-square inter-object distance. A point's uncertainty circle has the radius within
which 90 % of its displacements fall; the circles are a switch in Nastavení mapy, off by default
(:data:`SHOW_CIRCLES_BY_DEFAULT`). One stability number, the median displacement over objects and
draws, is always printed.

Pure: no I/O; the only randomness is numpy's seeded generators.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = ["SHOW_CIRCLES_BY_DEFAULT", "MapStability", "align", "map_stability"]

Floats = NDArray[np.float64]

SHOW_CIRCLES_BY_DEFAULT = False


def align(moved: Floats, reference: Floats) -> Floats:
    """``moved`` aligned onto ``reference`` by rotation, reflection, translation and one scale."""
    yc = moved - moved.mean(0)
    xc = reference - reference.mean(0)
    u, s, vt = np.linalg.svd(yc.T @ xc)
    aligned: Floats = (s.sum() / (yc**2).sum()) * yc @ (u @ vt) + reference.mean(0)
    return aligned


def _block_rows(rows: int, block_length: int, rng: np.random.Generator) -> NDArray[np.intp]:
    starts = rng.integers(0, rows - block_length + 1, size=-(-rows // block_length))
    return np.concatenate([np.arange(s, s + block_length) for s in starts])[:rows]


@dataclass(frozen=True)
class MapStability:
    radii: Floats
    """Per object: the radius holding ``share`` of its displacements, in reference RMS units."""
    stability: float
    """The median displacement over objects and draws, in reference RMS units; always printed."""
    block_length: int
    draws: int
    share: float


def map_stability(
    rows: Floats,
    map_of: Callable[[Floats], Floats],
    *,
    block_length: int,
    draws: int,
    seed: int,
    share: float = 0.9,
) -> MapStability:
    """``rows`` is rows x columns; ``map_of`` maps rows to object positions (objects x 2)."""
    data = np.asarray(rows, float)
    if not 1 <= block_length <= data.shape[0]:
        raise ValueError("block_length must be between 1 and the number of rows")
    reference = map_of(data)
    iu = np.triu_indices(reference.shape[0], 1)
    rms = float(np.sqrt((((reference[:, None] - reference[None]) ** 2).sum(-1)[iu]).mean()))
    rng = np.random.default_rng(seed)
    moves = np.empty((draws, reference.shape[0]))
    for draw in range(draws):
        positions = align(map_of(data[_block_rows(data.shape[0], block_length, rng)]), reference)
        moves[draw] = np.sqrt(((positions - reference) ** 2).sum(-1)) / rms
    return MapStability(
        radii=np.quantile(moves, share, axis=0),
        stability=float(np.median(moves)),
        block_length=block_length,
        draws=draws,
        share=share,
    )
