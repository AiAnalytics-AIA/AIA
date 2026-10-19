"""The signed-off AIA Sociomapa methodology's map credibility (``aia-sociomap-5``).

Ported as written from the methodology folder's ``map_checks.py`` (``split_half_agreement``)
and ``uncertainty.py`` (``map_uncertainty``), the owner's code, kept outside this repository
(``tests/test_sociomap_signed_off_credibility.py``). From a ratings matrix (respondents x
objects, NaN where not rated, the raw ratings, unweighted):

* the split-half check (:func:`split_half_agreement`): the respondents split at random into
  two halves, each half mapped on its own; the share of triplets "i closer to j than to k"
  the two half-maps order alike, averaged over the splits (0.5 is chance, 1 identical);
* the uncertainty radius (:func:`map_uncertainty`): respondent bootstraps, each mapped and
  aligned onto the map of the whole sample by Procrustes (rotation, reflection, translation,
  one scale); each object's spread around its mean bootstrap position, in units of the
  reference map's root-mean-square inter-object distance; the radius is a safety factor
  times the median spread. One radius per map: the methodology found the objects' own
  spreads rank the objects no better than chance, so they are not shown.

Every map here -- the half-maps, the bootstrap maps and the reference map -- is the
methodology's Interval MDS of its input stage without the noise rule (``map_of``, built by
the caller from the specification). On too little data that map raises
``ZeroDivisionError`` (no layout pair) or ``numpy.linalg.LinAlgError`` (the classical start
of a near-empty design), as the original does; the caller decides what follows.

Pure: no I/O; the only randomness is numpy's seeded generators.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = ["MapUncertainty", "map_uncertainty", "split_half_agreement"]

Floats = NDArray[np.float64]


def split_half_agreement(
    ratings: Floats, *, splits: int, seed: int, map_of: Callable[[Floats], Floats]
) -> float:
    """The mean over ``splits`` random halvings (``perm[:N // 2]`` and the rest) of the share
    of triplets the two half-maps order alike; NaN with fewer than three objects, where there
    is no triplet."""
    a = np.asarray(ratings, float)
    n, m = a.shape
    rng = np.random.default_rng(seed)
    out = []
    first, second = np.triu_indices(m - 1, 1)
    for _ in range(splits):
        perm = rng.permutation(n)
        dist = []
        for half in (perm[: n // 2], perm[n // 2 :]):
            xy = map_of(a[half])
            dist.append(np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1)))
        agree = []
        for i in range(m):
            others = np.array([j for j in range(m) if j != i])
            d1, d2 = dist[0][i, others], dist[1][i, others]
            agree.append(np.sign(d1[first] - d1[second]) == np.sign(d2[first] - d2[second]))
        alike = np.concatenate(agree)
        # The original's mean of no triplet is NaN with a warning; the same NaN, silently.
        out.append(float(alike.mean()) if alike.size else math.nan)
    return float(np.mean(out))


def _procrustes(y: Floats, x: Floats) -> Floats:
    xc = x - x.mean(0)
    yc = y - y.mean(0)
    u, s, vt = np.linalg.svd(yc.T @ xc)
    rotation = u @ vt
    aligned: Floats = (s.sum() / (yc**2).sum()) * yc @ rotation + x.mean(0)
    return aligned


def _rho(xy: Floats) -> float:
    iu = np.triu_indices(len(xy), 1)
    return float(np.sqrt((((xy[:, None] - xy[None]) ** 2).sum(-1)[iu]).mean()))


@dataclass(frozen=True, slots=True)
class MapUncertainty:
    """The map-level radius and each object's spread, both in units of the reference map's
    root-mean-square inter-object distance."""

    radius: float
    per_object: Floats


def map_uncertainty(
    ratings: Floats,
    *,
    resamples: int,
    seed: int,
    safety: float,
    map_of: Callable[[Floats], Floats],
) -> MapUncertainty:
    """``resamples`` respondent bootstraps (``rng.integers(0, N, N)``), each mapped from a cold
    start and aligned onto the map of the whole sample; radius = ``safety`` x the median
    object spread."""
    a = np.asarray(ratings, float)
    n = len(a)
    reference = map_of(a)
    rng = np.random.default_rng(seed)
    aligned = []
    for _ in range(resamples):
        aligned.append(_procrustes(map_of(a[rng.integers(0, n, n)]), reference))
    y = np.array(aligned) / _rho(reference)
    per_object: Floats = np.sqrt(((y - y.mean(0)) ** 2).sum(-1).mean(0))
    return MapUncertainty(radius=float(safety * np.median(per_object)), per_object=per_object)
