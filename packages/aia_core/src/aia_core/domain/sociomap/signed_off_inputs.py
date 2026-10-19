"""The signed-off AIA Sociomapa methodology's input stage (``aia-sociomap-5``).

Ported as written from the methodology folder's ``aia_inputs.py`` (the owner's code, kept
outside this repository), so it is checked number for number against that code
(``tests/test_sociomap_signed_off_inputs.py``). From a ratings matrix (respondents x
objects, NaN where not rated, the raw ratings on their own scale, unweighted):

* each respondent's ratings centred on their own mean; fewer than two ratings or no spread
  leaves the respondent out (:func:`centre`);
* each pair's pairwise-complete Pearson ``r``, the unrelated baseline ``r0`` it would have by
  centring alone, the baseline-corrected ``r~ = (r - r0) / (1 - r0)``, its support ``n`` and
  Fisher's p against ``r0`` (:func:`pair_stats`); below the status floor a pair is unknown;
* reliable pairs by Benjamini-Hochberg (:func:`bh`) and the noise rule
  (:func:`noise_q95_fast`): ``|r~|`` above the 95th percentile of ``|r~|`` with one object
  shuffled;
* the layout inputs: the same ``r~`` at the lower layout floor, each pair's layout weight
  (:func:`layout_weights`), precision weights (:func:`precision_weights`) and the
  sparse-design note (:func:`sparse_design`).

The constants of the original are the specification's (``relation`` and ``layout`` of
``aia-sociomap-5``) and are passed in; nothing here has a default. Same operation order,
same clipping constants and the same generator draws as the original, so the results agree
to rounding.

Pure: no I/O; the only randomness is the noise rule's seeded generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.stats import norm

__all__ = [
    "PreparedInputs",
    "SparseDesignNote",
    "bh",
    "centre",
    "layout_weights",
    "noise_q95",
    "noise_q95_fast",
    "pair_stats",
    "precision_weights",
    "prepare",
    "sparse_design",
]

Floats = NDArray[np.float64]
Flags = NDArray[np.bool_]


def centre(ratings: Floats) -> Floats:
    """Each respondent's ratings minus their own mean; a respondent with fewer than two
    ratings or no spread is left out (a row of NaN), as is every rating not given."""
    rated = np.isfinite(ratings)
    count = rated.sum(1)
    mean = np.where(rated, ratings, 0).sum(1) / np.maximum(count, 1)
    centred: Floats = ratings - mean[:, None]
    spread = np.where(rated, np.abs(centred), 0).max(1)
    placed = (count >= 2) & (spread > 1e-12)
    centred[~placed] = np.nan
    centred[~rated] = np.nan
    return centred


def pair_stats(centred: Floats, n_min: int) -> tuple[Floats, Floats, Floats, Flags]:
    """Each pair's baseline-corrected ``r~``, support ``n``, Fisher p against the unrelated
    baseline ``r0``, and whether it is known (``n >= n_min`` and both columns vary).

    Unweighted, pairwise complete. ``r0`` is the correlation two unrelated objects get from
    centring alone: minus the mean over the pair's co-raters of ``1 / (L - 1)``, ``L`` the
    number of objects each rated. An unknown pair has no ``r~`` and no p (NaN).
    """
    rated = np.isfinite(centred).astype(float)
    values = np.where(rated > 0, centred, 0.0)
    n: Floats = rated.T @ rated
    per_person = rated.sum(1)
    inverse = np.where(per_person > 1, 1 / np.maximum(per_person - 1, 1), 0)
    r0 = -(rated.T @ (rated * inverse[:, None])) / np.maximum(n, 1)
    sum_x = values.T @ rated
    sum_xx = (values**2).T @ rated
    sum_xy = values.T @ values
    mean_i = sum_x / np.maximum(n, 1)
    mean_j = mean_i.T
    cov = sum_xy / np.maximum(n, 1) - mean_i * mean_j
    var_i = sum_xx / np.maximum(n, 1) - mean_i**2
    var_j = var_i.T
    with np.errstate(invalid="ignore", divide="ignore"):
        r = cov / np.sqrt(var_i * var_j)
    r = np.clip(r, -0.999999, 0.999999)
    known: Flags = (n >= n_min) & (var_i > 1e-12) & (var_j > 1e-12)
    np.fill_diagonal(known, False)
    rt: Floats = np.where(known, (r - r0) / (1 - r0), np.nan)
    z = (np.arctanh(r) - np.arctanh(np.clip(r0, -0.999, 0.999))) * np.sqrt(np.maximum(n - 3, 1e-9))
    p: Floats = np.where(known, 2 * norm.sf(np.abs(z)), np.nan)
    np.fill_diagonal(rt, 0)
    return rt, n, p, known


def bh(p: Floats, known: Flags, q: float) -> Flags:
    """Benjamini-Hochberg at false-discovery rate ``q`` over the known pairs (each once)."""
    objects = len(p)
    upper = np.triu_indices(objects, 1)
    pv = p[upper]
    ok = known[upper]
    idx = np.where(ok)[0]
    tested = len(idx)
    keep = np.zeros(len(pv), bool)
    if tested:
        order = idx[np.argsort(pv[idx])]
        thresholds = q * np.arange(1, tested + 1) / tested
        passed = np.where(pv[order] <= thresholds)[0]
        if len(passed):
            keep[order[: passed.max() + 1]] = True
    reliable = np.zeros((objects, objects), bool)
    reliable[upper] = keep
    out: Flags = reliable | reliable.T
    return out


def noise_q95(ratings: Floats, perms: int, seed: int, n_min: int) -> Floats:
    """The noise rule's threshold, any data: the 95th percentile of ``|r~|`` with one object
    shuffled across respondents and the set re-centred, ``perms`` shuffles per object."""
    rng = np.random.default_rng(seed)
    _, objects = ratings.shape
    null = np.full((objects, objects, perms), np.nan)
    for b in range(objects):
        for t in range(perms):
            shuffled = ratings.copy()
            shuffled[:, b] = rng.permutation(shuffled[:, b])
            rt, _, _, _ = pair_stats(centre(shuffled), n_min)
            null[b, :, t] = np.abs(rt[b])
    out = np.full((objects, objects), np.nan)
    for a in range(objects):
        for b in range(a + 1, objects):
            v = np.concatenate([null[b, a], null[a, b]])
            v = v[np.isfinite(v)]
            if len(v) >= perms:
                out[a, b] = out[b, a] = np.quantile(v, 0.95)
    return out


def noise_q95_fast(ratings: Floats, perms: int, seed: int, n_min: int) -> Floats:
    """The same statistic on complete data in ``O(NM)`` per shuffle: shuffling column ``b``
    moves only the respondent means. Incomplete data takes :func:`noise_q95` with half the
    shuffles, as the original does."""
    if not np.isfinite(ratings).all():
        return noise_q95(ratings, perms=perms // 2, seed=seed, n_min=n_min)
    rng = np.random.default_rng(seed)
    _, objects = ratings.shape
    r0 = -1 / (objects - 1)
    null = np.full((objects, objects, perms), np.nan)
    for b in range(objects):
        for t in range(perms):
            bp = rng.permutation(ratings[:, b])
            m = (ratings.sum(1) - ratings[:, b] + bp) / objects
            centred = ratings - m[:, None]
            cb = bp - m
            # Respondents without spread are not left out here: complete simulated data has
            # none (the original's own approximation, kept).
            cc = centred - centred.mean(0)
            cbc = cb - cb.mean()
            r = (cc * cbc[:, None]).sum(0) / np.sqrt((cc**2).sum(0) * (cbc**2).sum())
            null[b, :, t] = np.abs((r - r0) / (1 - r0))
    out = np.full((objects, objects), np.nan)
    for a in range(objects):
        for b in range(a + 1, objects):
            v = np.concatenate([null[b, a], null[a, b]])
            v = v[np.isfinite(v)]
            # No minimum count here, unlike the general path (the original's own difference).
            out[a, b] = out[b, a] = np.quantile(v, 0.95)
    return out


def precision_weights(rt: Floats, n: Floats, known: Flags, cap: float) -> Floats:
    """Each known pair's precision ``2 n / ((1 - r~)(1 + r~)^2)`` (``r~`` clipped to
    +-0.95), floored at the largest over ``cap`` and scaled to mean 1; 0 elsewhere."""
    r = np.clip(np.nan_to_num(rt), -0.95, 0.95)
    w = np.where(known, 2 * n / ((1 - r) * (1 + r) ** 2), 0.0)
    pos = w[w > 0]
    if len(pos):
        w = np.where(w > 0, np.clip(w, pos.max() / cap, None), 0)
    out: Floats = w / (w[w > 0].mean() if len(pos) else 1)
    return out


def layout_weights(n: Floats, known_layout: Flags, full_at: int) -> Floats:
    """Each layout pair's weight ``min(1, (n - 3) / (full_at - 3))``; 0 (masked) below the
    layout floor."""
    w: Floats = np.where(known_layout, np.clip((n - 3) / (full_at - 3), 0, 1), 0.0)
    np.fill_diagonal(w, 0)
    return w


@dataclass(frozen=True, slots=True)
class SparseDesignNote:
    """The sparse-design note: set when more than the declared share of pairs is below the
    layout floor, or some object has fewer layout partners than the declared minimum."""

    flag: bool
    share_below_layout_floor: float
    weakly_connected: list[int]
    layout_partners: NDArray[np.int64]


def sparse_design(w_layout: Floats, share: float, min_partners: int) -> SparseDesignNote:
    objects = len(w_layout)
    upper = np.triu_indices(objects, 1)
    below = float((w_layout[upper] <= 0).mean()) if objects > 1 else 0.0
    partners = (w_layout > 0).sum(1)
    weak = np.where(partners < min_partners)[0]
    return SparseDesignNote(
        flag=bool(below > share or len(weak) > 0),
        share_below_layout_floor=below,
        weakly_connected=[int(k) for k in weak],
        layout_partners=partners,
    )


@dataclass(frozen=True, slots=True)
class PreparedInputs:
    """Everything the input stage gives the later stages, named as in the original:
    ``rt``, ``n``, ``p``, ``known``, ``reliable``, ``delta``, ``W`` (``precision``), ``R``
    (``relation``), ``Q`` (``charge``), ``R_layout``, ``W_layout``, ``delta_layout``,
    ``W_mds_layout`` (``precision_layout``), ``unknown_layout``, ``sparse``,
    ``mean_rating``. ``placed`` marks the respondents :func:`centre` kept."""

    rt: Floats
    n: Floats
    p: Floats
    known: Flags
    reliable: Flags
    delta: Floats
    precision: Floats
    relation: Floats
    charge: Floats
    relation_layout: Floats
    layout_weight: Floats
    delta_layout: Floats
    precision_layout: Floats
    unknown_layout: Flags
    sparse: SparseDesignNote
    mean_rating: Floats
    placed: Flags


def prepare(
    ratings: Any,
    *,
    n_min: int,
    layout_floor: int,
    layout_weight_full_at: int,
    false_discovery_rate: float,
    noise_rule: bool,
    noise_permutations: int,
    noise_seed: int,
    precision_weight_cap: float,
    sparse_share: float,
    min_layout_partners: int,
) -> PreparedInputs:
    """The whole input stage in one call (the original's ``prepare``)."""
    a: Floats = np.asarray(ratings, float)
    centred = centre(a)
    rt, n, p, known = pair_stats(centred, n_min)
    rel = bh(p, known, false_discovery_rate)
    # The noise rule only ever removes pairs BH kept, so with none kept the result is the
    # same without it (and a family with no pair, where its shuffles have nothing to read).
    if noise_rule and rel.any():
        q = noise_q95_fast(a, perms=noise_permutations, seed=noise_seed, n_min=n_min)
        rel = rel & (np.abs(np.nan_to_num(rt)) > np.nan_to_num(q, nan=np.inf))
    delta = np.where(known, np.sqrt(np.clip(2 * (1 - np.nan_to_num(rt)), 0, None)), np.nan)
    np.fill_diagonal(delta, 0)
    w = precision_weights(rt, n, known, precision_weight_cap)
    np.fill_diagonal(w, 0)
    relation = np.nan_to_num(rt)
    np.fill_diagonal(relation, 1.0)
    charge = ((1 - np.clip(relation, -1, 1)) / 2) ** 2
    rt_layout, _, _, known_layout = pair_stats(centred, layout_floor)
    relation_layout = np.nan_to_num(rt_layout)
    np.fill_diagonal(relation_layout, 1.0)
    w_layout = layout_weights(n, known_layout, layout_weight_full_at)
    delta_layout = np.where(
        known_layout, np.sqrt(np.clip(2 * (1 - np.nan_to_num(rt_layout)), 0, None)), np.nan
    )
    np.fill_diagonal(delta_layout, 0)
    w_mds_layout = precision_weights(rt_layout, n, known_layout, precision_weight_cap)
    np.fill_diagonal(w_mds_layout, 0)
    unknown_layout = ~known_layout & ~np.eye(a.shape[1], dtype=bool)
    return PreparedInputs(
        rt=rt,
        n=n,
        p=p,
        known=known,
        reliable=rel,
        delta=delta,
        precision=w,
        relation=relation,
        charge=charge,
        relation_layout=relation_layout,
        layout_weight=w_layout,
        delta_layout=delta_layout,
        precision_layout=w_mds_layout,
        unknown_layout=unknown_layout,
        sparse=sparse_design(w_layout, sparse_share, min_layout_partners),
        mean_rating=np.nanmean(a, 0),
        placed=np.isfinite(centred).any(1),
    )
