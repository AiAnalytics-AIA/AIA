"""Sociomapa systémů, Konkurence: weighted coverage (decision SM16, answers Q-KONK).

A covers B to the extent that A matches B's strengths on the rows that matter for the question:

    coverage(A, B) = sum_r w_r * min(a_r, b_r) / sum_r w_r * b_r

The rows are scaled to the real world first (SM4/SM5), so a strength means the same on every row;
the weights are the question's (SM10). AIA's past competitor maps used each row's own range and no
weights. Coverage runs one way (A may cover B without B covering A); see :mod:`.one_sided`.

Pure: no I/O.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

__all__ = ["weighted_coverage"]

Floats = NDArray[np.float64]


def weighted_coverage(scores: Floats, weights: Floats) -> Floats:
    """``scores`` is objects x rows, already scaled, non-negative; ``weights`` one per row,
    non-negative. Returns objects x objects with ``[a, b]`` = how much a covers b; 1 on the
    diagonal; NaN where b has no weighted strength to cover."""
    s = np.asarray(scores, float)
    w = np.asarray(weights, float)
    if s.ndim != 2 or w.shape != (s.shape[1],):
        raise ValueError("scores must be objects x rows and weights one per row")
    if (s < 0).any() or (w < 0).any():
        raise ValueError("scaled scores and weights must not be negative")
    shared = (np.minimum(s[:, None, :], s[None, :, :]) * w).sum(-1)
    own = (s * w).sum(-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        coverage: Floats = np.where(own[None, :] > 0, shared / own[None, :], np.nan)
    np.fill_diagonal(coverage, 1.0)
    return coverage
