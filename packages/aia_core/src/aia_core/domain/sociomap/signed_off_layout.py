"""The signed-off AIA Sociomapa methodology's object positions (``aia-sociomap-5``).

Ported as written from the methodology folder's ``srs_coulomb_bb1.py``, ``bb1_reference.py``,
``interval_mds.py``, ``layout.py`` and ``sociomap_3d.to_ruler`` (the owner's code, kept outside
this repository; ``tests/test_sociomap_signed_off_layout.py``). From the input stage's layout
pairs (:func:`~.signed_off_inputs.prepare`):

* the fixed object-count rule (:func:`choose_method`): soft-rank Spearman with Coulomb
  repulsion for a declared range of object counts, Interval MDS below and above it;
* soft-rank Spearman with Coulomb repulsion (:func:`soft_rank_spearman`): each object's row of
  relations and its row of map distances are compared by a weighted Pearson of their soft
  ranks over its layout partners, plus a repulsion term that keeps unrelated objects apart;
  optimised per object by Barzilai-Borwein steps with exact backtracking (BB1), from a
  classical start and seeded random starts in the unit square, run in parallel; the restart
  kept is the one with the best hard-rank Spearman;
* Interval MDS (:func:`interval_mds`): weighted SMACOF on the layout targets with an interval
  transformation, a one-sided floor for the pairs below the layout floor, from a classical
  start and seeded random starts, the lowest normalised stress kept;
* one uniform least-squares scale to ruler units (:func:`to_ruler`).

Same operation order, constants, generator draws and compiled kernels (numba, the same
decorator flags) as the original, so on the same machine and library versions the maps are the
original's bit for bit. Across machines the compiled soft-rank kernel's last bits can differ,
and the criterion is chaotic: a full soft-rank run is reproducible on one machine, not across
them. Only what the methodology's layout reads is ported: no reference map for ``to_ruler``,
only the interval transformation of SMACOF.

Pure: no I/O; the only randomness is numpy's seeded generators.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

import numpy as np
from numba import njit, prange
from numpy.typing import NDArray
from scipy.stats import rankdata

from .signed_off_inputs import PreparedInputs

__all__ = [
    "FEW_OBJECTS",
    "SMACOF_ITMAX",
    "PositionMethod",
    "SoftRankSpearmanResult",
    "choose_method",
    "classical_start",
    "interval_mds",
    "prep_a",
    "rescale_unit",
    "soft_rank_spearman",
    "to_ruler",
    "za_rows",
]

Floats = NDArray[np.float64]
Flags = NDArray[np.bool_]


class PositionMethod(StrEnum):
    """Which of the two methods placed the objects, recorded on every map."""

    SOFT_RANK_SPEARMAN_COULOMB = "soft_rank_spearman_coulomb"
    INTERVAL_MDS = "interval_mds"


def choose_method(objects: int, min_objects: int, max_objects: int) -> PositionMethod:
    """The fixed object-count rule: soft-rank Spearman with Coulomb repulsion from
    ``min_objects`` to ``max_objects`` objects, Interval MDS otherwise."""
    if min_objects <= objects <= max_objects:
        return PositionMethod.SOFT_RANK_SPEARMAN_COULOMB
    return PositionMethod.INTERVAL_MDS


# --------------------------------------------------------------------------- the original's
# bb1_reference helpers the soft-rank layout reads

#: How far the relations are kept from 0 and 1 after the row min-max.
EPS: Final = 1e-6


def sig(z: Any) -> Any:
    return 0.5 * (np.tanh(z / 2) + 1)


def prep_a(relation: Floats) -> Floats:
    """Relation matrix (higher = closer) -> row min-max (no diagonal) -> [eps, 1-eps];
    diagonal 1-eps."""
    size = len(relation)
    a = np.array(relation, float)
    off = ~np.eye(size, dtype=bool)
    for i in range(size):
        v = a[i, off[i]]
        lo, hi = v.min(), v.max()
        a[i, off[i]] = (v - lo) / (hi - lo) if hi - lo > 0 else 0.5
    a = EPS + (1 - 2 * EPS) * a
    np.fill_diagonal(a, 1 - EPS)
    return a


def _z(vals: Floats, off: Flags) -> tuple[Floats, Floats]:
    m = off.sum(1, keepdims=True)
    mu = np.where(off, vals, 0).sum(1, keepdims=True) / m
    sd = np.sqrt(np.where(off, (vals - mu) ** 2, 0).sum(1, keepdims=True) / m)
    sd = np.where(sd < 1e-12, 1.0, sd)
    return np.where(off, (vals - mu) / sd, 0.0), sd[:, 0]


def soft_rank_rows(vals: Floats, tau: float, off: Flags) -> Floats:
    """``SR(v)_j = sum_{k != j} sigma((v_j - v_k) / tau)`` per row over off-diagonal entries."""
    size = len(vals)
    t = sig((vals[:, :, None] - vals[:, None, :]) / tau)
    mask = off[:, :, None] & off[:, None, :] & ~np.eye(size, dtype=bool)[None]
    out: Floats = np.where(off, (t * mask).sum(2), 0.0)
    return out


def rescale_unit(xy: Floats) -> Floats:
    """Into the unit square by one scale, centred along the shorter side."""
    xy = xy - xy.min(0)
    span = xy.max(0)
    s = span.max() or 1.0
    xy = xy / s
    out: Floats = xy + (1 - xy.max(0)) / 2 * (np.arange(2) == np.argmin(span))
    return out


def classical_start(a: Floats) -> Floats:
    """Classical scaling of ``(1 - a)^2``, rescaled into the unit square."""
    size = len(a)
    b = (1 - a) ** 2
    np.fill_diagonal(b, 0)
    j = np.eye(size) - 1 / size
    b = -0.5 * j @ b @ j
    b = (b + b.T) / 2
    w, vecs = np.linalg.eigh(b)
    idx = np.argsort(w)[::-1][:2]
    xy = vecs[:, idx] * np.sqrt(np.maximum(w[idx], 0))
    return rescale_unit(xy)


# --------------------------------------------------------------------------- the compiled
# soft-rank Spearman + Coulomb kernels (srs_coulomb_bb1), statement for statement

#: The sigmoid is exactly 0 or 1 beyond this many temperatures.
SAT: Final = 40.0


@njit(cache=True, inline="always")
def _sig(z: float) -> float:
    if z >= SAT:
        return 1.0
    if z <= -SAT:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


@njit(cache=True, inline="always")
def _dsig(z: float) -> float:
    if z >= SAT or z <= -SAT:
        return 0.0
    e = math.exp(-abs(z))
    return e / ((1.0 + e) * (1.0 + e))


@njit(cache=True)
def _dist(xy: Floats, dist: Floats) -> None:
    size = xy.shape[0]
    for i in range(size):
        dist[i, i] = 0.0
        for j in range(i + 1, size):
            a = xy[i, 0] - xy[j, 0]
            b = xy[i, 1] - xy[j, 1]
            d = math.sqrt(a * a + b * b)
            dist[i, j] = d
            dist[j, i] = d


@njit(cache=True)
def _sorted_row(v: Floats, i: int, ranked: Flags, idx: Any, w: Floats) -> int:
    size = v.shape[0]
    n = 0
    for j in range(size):
        if ranked[i, j]:
            idx[n] = j
            n += 1
    o = np.argsort(v[idx[:n]], kind="mergesort")
    tmp = idx[:n].copy()
    for q in range(n):
        idx[q] = tmp[o[q]]
        w[q] = v[idx[q]]
    return n


@njit(cache=True)
def _stats(vals: Floats, za: Floats, ws: Floats, s1: Floats, s2: Floats, sa: Floats) -> None:
    size = vals.shape[0]
    for i in range(size):
        a = 0.0
        b = 0.0
        c = 0.0
        for j in range(size):
            w = ws[i, j]
            if w > 0:
                x = vals[i, j]
                a += w * x
                b += w * x * x
                c += w * za[i, j] * x
        s1[i] = a
        s2[i] = b
        sa[i] = c


@njit(cache=True, inline="always")
def _r(s1: float, s2: float, sa: float, zs: float, m: float) -> float:
    mu = s1 / m
    var = s2 / m - mu * mu
    sd = math.sqrt(var) if var > 0 else 0.0
    if sd < 1e-12:
        sd = 1.0
    return (sa - mu * zs) / (sd * m)


@njit(cache=True)
def _coul_sums(dist: Floats, charge: Floats) -> tuple[float, float]:
    size = dist.shape[0]
    s2 = 0.0
    total = 0.0
    for i in range(size):
        for j in range(i + 1, size):
            d = max(dist[i, j], 1e-12)
            s2 += d * d
            total += charge[i, j] / d
    return s2, total


@njit(cache=True)
def _f_from(
    s1: Floats,
    s2: Floats,
    sa: Floats,
    zs: Floats,
    ms: Floats,
    act: Flags,
    n_act: int,
    lam: float,
    cs2: float,
    ct: float,
    n_pairs: int,
) -> float:
    size = s1.shape[0]
    f = 0.0
    for i in range(size):
        if act[i]:
            f += 1.0 + _r(s1[i], s2[i], sa[i], zs[i], ms[i])
    f /= 2.0 * max(n_act, 1)
    if lam > 0:
        f += lam * math.sqrt(cs2 / n_pairs) * ct / n_pairs
    return f


@njit(cache=True)
def _grad_k(
    k: int,
    xy: Floats,
    dist: Floats,
    grad: Floats,
    charge: Floats,
    lam: float,
    cs2: float,
    ct: float,
    n_pairs: int,
    n_act: int,
    g: Floats,
) -> None:
    size = xy.shape[0]
    gx = 0.0
    gy = 0.0
    for j in range(size):
        if j == k:
            continue
        dk = max(dist[k, j], 1e-12)
        c = (grad[k, j] + grad[j, k]) / dk
        gx += c * (xy[k, 0] - xy[j, 0])
        gy += c * (xy[k, 1] - xy[j, 1])
    gx /= 2.0 * max(n_act, 1)
    gy /= 2.0 * max(n_act, 1)
    rho = math.sqrt(cs2 / n_pairs)
    sx = 0.0
    sy = 0.0
    for j in range(size):
        if j == k:
            continue
        sx += xy[k, 0] - xy[j, 0]
        sy += xy[k, 1] - xy[j, 1]
    if lam > 0:
        tx = 0.0
        ty = 0.0
        for j in range(size):
            if j == k:
                continue
            dx = xy[k, 0] - xy[j, 0]
            dy = xy[k, 1] - xy[j, 1]
            dd = max(dist[k, j], 1e-12)
            q = charge[k, j] / dd**3
            tx -= q * dx
            ty -= q * dy
        gx += lam * (ct * sx / (n_pairs * rho) + rho * tx) / n_pairs
        gy += lam * (ct * sy / (n_pairs * rho) + rho * ty) / n_pairs
    g[0] = gx
    g[1] = gy


@njit(cache=True, inline="always")
def _bsl(v: Floats, n: int, x: float) -> int:
    lo = 0
    hi = n
    while lo < hi:
        mid = (lo + hi) >> 1
        if v[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo


@njit(cache=True, inline="always")
def _bsr(v: Floats, n: int, x: float) -> int:
    lo = 0
    hi = n
    while lo < hi:
        mid = (lo + hi) >> 1
        if v[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo


@njit(cache=True)
def _resort(dist: Floats, o_idx: Any, o_val: Floats, mr: Any) -> None:
    size = dist.shape[0]
    for i in range(size):
        n = mr[i]
        for q in range(n):
            o_val[i, q] = dist[i, o_idx[i, q]]
        for q in range(1, n):
            v = o_val[i, q]
            j = o_idx[i, q]
            p = q - 1
            while p >= 0 and o_val[i, p] > v:
                o_val[i, p + 1] = o_val[i, p]
                o_idx[i, p + 1] = o_idx[i, p]
                p -= 1
            o_val[i, p + 1] = v
            o_idx[i, p + 1] = j


@njit(cache=True)
def _sr_sorted(idx: Any, w: Floats, n: int, it: float, out: Floats, acc: Floats) -> None:
    for p in range(n):
        acc[p] = 0.0
    a = 0
    b = 0
    for p in range(n):
        while a < n and (w[p] - w[a]) * it >= SAT:
            a += 1
        acc[p] += a
        if b < p + 1:
            b = p + 1
        while b < n and (w[p] - w[b]) * it > -SAT:
            b += 1
        for q in range(p + 1, b):
            sg = _sig((w[p] - w[q]) * it)
            acc[p] += sg
            acc[q] += 1.0 - sg
    for p in range(n):
        out[idx[p]] = acc[p]


@njit(cache=True)
def _grad_sorted(
    vals: Floats,
    za: Floats,
    zs: Floats,
    ws: Floats,
    ms: Floats,
    act: Flags,
    mr: Any,
    it: float,
    s1: Floats,
    s2: Floats,
    sa: Floats,
    grad: Floats,
    o_idx: Any,
    o_val: Floats,
    pv: Floats,
) -> None:
    size = vals.shape[0]
    for i in range(size):
        for j in range(size):
            grad[i, j] = 0.0
        if not act[i]:
            continue
        m = ms[i]
        mu = s1[i] / m
        var = s2[i] / m - mu * mu
        sd = math.sqrt(var) if var > 0 else 0.0
        if sd < 1e-12:
            sd = 1.0
        r = (sa[i] - mu * zs[i]) / (sd * m)
        n = mr[i]
        for q in range(n):
            j = o_idx[i, q]
            w = ws[i, j]
            pv[q] = w * (za[i, j] - r * (vals[i, j] - mu) / sd) / (sd * m) if w > 0 else 0.0
        b = 0
        for p in range(n):
            if b < p + 1:
                b = p + 1
            while b < n and (o_val[i, p] - o_val[i, b]) * it > -SAT:
                b += 1
            for q in range(p + 1, b):
                s = _dsig((o_val[i, p] - o_val[i, q]) * it) * it
                grad[i, o_idx[i, p]] += s * (pv[p] - pv[q])
                grad[i, o_idx[i, q]] += s * (pv[q] - pv[p])


@njit(cache=True)
def _trial_f(
    k: int,
    xy: Floats,
    xn: Floats,
    dist: Floats,
    sr: Floats,
    za: Floats,
    zs: Floats,
    charge: Floats,
    lam: float,
    ranked: Flags,
    ws: Floats,
    mr: Any,
    ms: Floats,
    act: Flags,
    n_act: int,
    it: float,
    s1: Floats,
    s2: Floats,
    sa: Floats,
    cs2: float,
    ct: float,
    n_pairs: int,
    dk: Floats,
    rowk: Floats,
    k_idx: Any,
    k_val: Floats,
    o_idx: Any,
    o_val: Floats,
    nb: Floats,
    colk: Floats,
    cb: Floats,
    acc: Floats,
) -> float:
    size = xy.shape[0]
    tau = 1.0 / it
    mg = 41.0 * tau
    for j in range(size):
        if j == k:
            dk[j] = 0.0
        else:
            a = xy[j, 0] - xn[0]
            b = xy[j, 1] - xn[1]
            dk[j] = math.sqrt(a * a + b * b)
    ncs2 = cs2
    nct = ct
    for j in range(size):
        if j == k:
            continue
        do = max(dist[k, j], 1e-12)
        dn = max(dk[j], 1e-12)
        ncs2 += dn * dn - do * do
        if lam > 0:
            nct += charge[k, j] * (1.0 / dn - 1.0 / do)
    cb[0] = ncs2
    cb[1] = nct
    mk = mr[k]
    for j in range(size):
        rowk[j] = 0.0
    for q in range(mk):
        k_idx[q] = o_idx[k, q]
        k_val[q] = dk[k_idx[q]]
    for q in range(1, mk):
        v0 = k_val[q]
        j0 = k_idx[q]
        p = q - 1
        while p >= 0 and k_val[p] > v0:
            k_val[p + 1] = k_val[p]
            k_idx[p + 1] = k_idx[p]
            p -= 1
        k_val[p + 1] = v0
        k_idx[p + 1] = j0
    _sr_sorted(k_idx, k_val, mk, it, rowk, acc)
    a1 = 0.0
    a2 = 0.0
    a3 = 0.0
    for j in range(size):
        w = ws[k, j]
        if w > 0:
            x = rowk[j]
            a1 += w * x
            a2 += w * x * x
            a3 += w * za[k, j] * x
    nb[k, 0] = a1
    nb[k, 1] = a2
    nb[k, 2] = a3
    f = 0.0
    if act[k]:
        f += 1.0 + _r(a1, a2, a3, zs[k], ms[k])
    for i in range(size):
        if i == k:
            continue
        b1 = s1[i]
        b2 = s2[i]
        b3 = sa[i]
        if ranked[i, k]:
            m = mr[i]
            dn = dk[i]
            do = dist[i, k]
            v = o_val[i]
            ix = o_idx[i]
            lo = min(dn, do) - mg
            hi = max(dn, do) + mg
            p0 = _bsl(v, m, lo)
            p1 = _bsr(v, m, hi)
            for q in range(p0, p1):
                j = ix[q]
                if j == k:
                    continue
                dij = v[q]
                zn = (dij - dn) * it
                zo = (dij - do) * it
                if not ((zn >= SAT and zo >= SAT) or (zn <= -SAT and zo <= -SAT)):
                    dl = _sig(zn) - _sig(zo)
                    w = ws[i, j]
                    if dl != 0.0 and w > 0:
                        x = sr[i, j]
                        y = x + dl
                        b1 += w * dl
                        b2 += w * (y * y - x * x)
                        b3 += w * za[i, j] * dl
            thr = dn - mg
            c0 = _bsl(v, m, thr)
            c1 = _bsr(v, m, dn + mg)
            col = float(c0 - (1 if do < thr else 0))
            for q in range(c0, c1):
                j = ix[q]
                if j == k:
                    continue
                col += _sig(-((v[q] - dn) * it))
            colk[i] = col
            w = ws[i, k]
            if w > 0:
                x = sr[i, k]
                b1 += w * (col - x)
                b2 += w * (col * col - x * x)
                b3 += w * za[i, k] * (col - x)
        nb[i, 0] = b1
        nb[i, 1] = b2
        nb[i, 2] = b3
        if act[i]:
            f += 1.0 + _r(b1, b2, b3, zs[i], ms[i])
    f /= 2.0 * max(n_act, 1)
    if lam > 0:
        f += lam * math.sqrt(ncs2 / n_pairs) * nct / n_pairs
    return f


@njit(cache=True)
def _accept(
    k: int,
    dk: Floats,
    rowk: Floats,
    k_idx: Any,
    k_val: Floats,
    dist: Floats,
    sr: Floats,
    ranked: Flags,
    mr: Any,
    it: float,
    o_idx: Any,
    o_val: Floats,
    nb: Floats,
    colk: Floats,
    s1: Floats,
    s2: Floats,
    sa: Floats,
) -> None:
    size = dist.shape[0]
    tau = 1.0 / it
    mg = 41.0 * tau
    for i in range(size):
        if i == k or not ranked[i, k]:
            continue
        m = mr[i]
        dn = dk[i]
        do = dist[i, k]
        v = o_val[i]
        ix = o_idx[i]
        lo = min(dn, do) - mg
        hi = max(dn, do) + mg
        p0 = _bsl(v, m, lo)
        p1 = _bsr(v, m, hi)
        for q in range(p0, p1):
            j = ix[q]
            if j == k:
                continue
            dij = v[q]
            zn = (dij - dn) * it
            zo = (dij - do) * it
            if not ((zn >= SAT and zo >= SAT) or (zn <= -SAT and zo <= -SAT)):
                sr[i, j] += _sig(zn) - _sig(zo)
        sr[i, k] = colk[i]
        pk = 0
        while ix[pk] != k:
            pk += 1
        for q in range(pk, m - 1):
            v[q] = v[q + 1]
            ix[q] = ix[q + 1]
        p = _bsl(v, m - 1, dn)
        for q in range(m - 1, p, -1):
            v[q] = v[q - 1]
            ix[q] = ix[q - 1]
        v[p] = dn
        ix[p] = k
    for j in range(size):
        sr[k, j] = rowk[j]
    for q in range(mr[k]):
        o_idx[k, q] = k_idx[q]
        o_val[k, q] = k_val[q]
    for j in range(size):
        dist[k, j] = dk[j]
        dist[j, k] = dk[j]
    for i in range(size):
        s1[i] = nb[i, 0]
        s2[i] = nb[i, 1]
        sa[i] = nb[i, 2]


@njit(cache=True)
def _full_soft_ranks(
    dist: Floats, mr: Any, it: float, sr: Floats, o_idx: Any, o_val: Floats, acc: Floats
) -> None:
    size = dist.shape[0]
    for i in range(size):
        for j in range(size):
            sr[i, j] = 0.0
        _sr_sorted(o_idx[i], o_val[i], mr[i], it, sr[i], acc)


@njit(cache=True)
def _run_restart(
    xy0: Floats,
    za: Floats,
    charge: Floats,
    lam: float,
    ranked: Flags,
    ws: Floats,
    act: Flags,
    tau: float,
    max_passes: int,
) -> tuple[Floats, float, int]:
    size = xy0.shape[0]
    it = 1.0 / tau
    n_pairs = size * (size - 1) // 2
    xy = xy0.copy()
    mr = np.zeros(size, np.int64)
    ms = np.zeros(size)
    n_act = 0
    for i in range(size):
        for j in range(size):
            if ranked[i, j]:
                mr[i] += 1
            ms[i] += ws[i, j]
        if act[i]:
            n_act += 1
    dist = np.zeros((size, size))
    sr = np.zeros((size, size))
    grad = np.zeros((size, size))
    s1 = np.zeros(size)
    s2 = np.zeros(size)
    sa = np.zeros(size)
    zs = np.zeros(size)
    for i in range(size):
        for j in range(size):
            zs[i] += ws[i, j] * za[i, j]
    o_idx = np.zeros((size, size), np.int64)
    o_val = np.zeros((size, size))
    k_idx = np.zeros(size, np.int64)
    k_val = np.zeros(size)
    pv = np.zeros(size)
    dk = np.zeros(size)
    rowk = np.zeros(size)
    g = np.zeros(2)
    xn = np.zeros(2)
    nb = np.zeros((size, 3))
    colk = np.zeros(size)
    cb = np.zeros(2)
    acc = np.zeros(size)
    _dist(xy, dist)
    for i in range(size):
        n = _sorted_row(dist[i], i, ranked, k_idx, k_val)
        for q in range(n):
            o_idx[i, q] = k_idx[q]
            o_val[i, q] = k_val[q]
    _full_soft_ranks(dist, mr, it, sr, o_idx, o_val, acc)
    _stats(sr, za, ws, s1, s2, sa)
    cs2, ct = _coul_sums(dist, charge)
    f_cur = _f_from(s1, s2, sa, zs, ms, act, n_act, lam, cs2, ct, n_pairs)
    hist = np.empty(max_passes + 1)
    hist[0] = f_cur
    nh = 1
    prev_x = np.zeros((size, 2))
    prev_g = np.zeros((size, 2))
    has = np.zeros(size, np.bool_)
    a_prev = np.full(size, 0.02)
    c = np.ones(size)
    passes = 0
    for ps in range(1, max_passes + 1):
        passes = ps
        f_pass = f_cur
        _grad_sorted(sr, za, zs, ws, ms, act, mr, it, s1, s2, sa, grad, o_idx, o_val, pv)
        moved = False
        for k in range(size):
            _grad_k(k, xy, dist, grad, charge, lam, cs2, ct, n_pairs, n_act, g)
            gn = math.sqrt(g[0] * g[0] + g[1] * g[1])
            if gn < 1e-12:
                continue
            ux = -g[0] / gn
            uy = -g[1] / gn
            if has[k]:
                q0 = xy[k, 0] - prev_x[k, 0]
                q1 = xy[k, 1] - prev_x[k, 1]
                y0 = g[0] - prev_g[k, 0]
                y1 = g[1] - prev_g[k, 1]
                sy = q0 * y0 + q1 * y1
                ss = q0 * q0 + q1 * q1
                a_bb = ss / sy if (sy > 1e-12 and ss > 0) else a_prev[k]
            else:
                a_bb = 0.02
            a = min(max(a_bb * c[k], 1e-6), 1.0)
            nbt = 0
            accepted = False
            fn = 0.0
            for _ in range(8):
                xn[0] = min(max(xy[k, 0] + a * ux, 0.0), 1.0)
                xn[1] = min(max(xy[k, 1] + a * uy, 0.0), 1.0)
                fn = _trial_f(
                    k,
                    xy,
                    xn,
                    dist,
                    sr,
                    za,
                    zs,
                    charge,
                    lam,
                    ranked,
                    ws,
                    mr,
                    ms,
                    act,
                    n_act,
                    it,
                    s1,
                    s2,
                    sa,
                    cs2,
                    ct,
                    n_pairs,
                    dk,
                    rowk,
                    k_idx,
                    k_val,
                    o_idx,
                    o_val,
                    nb,
                    colk,
                    cb,
                    acc,
                )
                if fn <= f_pass - 1e-4 * a * gn:
                    accepted = True
                    break
                nbt += 1  # noqa: SIM113 - set to 8 below when no step is accepted
                den = 2.0 * (fn - f_cur + gn * a)
                if den > 1e-300:  # noqa: SIM108 - the original's statements, kept
                    a = min(max(gn * a * a / den, 0.1 * a), 0.5 * a)
                else:
                    a = 0.5 * a
            if not accepted:
                nbt = 8
            if nbt >= 4:
                c[k] = 0.5 * c[k]
            elif nbt <= 1:
                c[k] = 1.1 * c[k]
            c[k] = min(max(c[k], 0.25), 2.0)
            if accepted:
                prev_x[k, 0] = xy[k, 0]
                prev_x[k, 1] = xy[k, 1]
                prev_g[k, 0] = g[0]
                prev_g[k, 1] = g[1]
                a_prev[k] = a
                has[k] = True
                if (xn[0] - xy[k, 0]) ** 2 + (xn[1] - xy[k, 1]) ** 2 > 1e-24:
                    _accept(
                        k,
                        dk,
                        rowk,
                        k_idx,
                        k_val,
                        dist,
                        sr,
                        ranked,
                        mr,
                        it,
                        o_idx,
                        o_val,
                        nb,
                        colk,
                        s1,
                        s2,
                        sa,
                    )
                    xy[k, 0] = xn[0]
                    xy[k, 1] = xn[1]
                    cs2 = cb[0]
                    ct = cb[1]
                    f_cur = fn
                    moved = True
        _dist(xy, dist)
        _resort(dist, o_idx, o_val, mr)
        _full_soft_ranks(dist, mr, it, sr, o_idx, o_val, acc)
        _stats(sr, za, ws, s1, s2, sa)
        cs2, ct = _coul_sums(dist, charge)
        f_cur = _f_from(s1, s2, sa, zs, ms, act, n_act, lam, cs2, ct, n_pairs)
        hist[nh] = f_cur
        nh += 1
        if not moved:
            break
        if ps > 30 and (hist[nh - 31] - hist[nh - 1]) / max(abs(hist[nh - 31]), 1e-12) < 3e-4:
            break
    return xy, f_cur, passes


@njit(cache=True, parallel=True)
def _run_all(
    starts: Floats,
    za: Floats,
    charge: Floats,
    lam: float,
    ranked: Flags,
    ws: Floats,
    act: Flags,
    tau: float,
    max_passes: int,
) -> tuple[Floats, Floats, Any]:
    n_restarts, size = starts.shape[0], starts.shape[1]
    xys = np.zeros((n_restarts, size, 2))
    fs = np.zeros(n_restarts)
    ps = np.zeros(n_restarts, np.int64)
    for q in prange(n_restarts):
        xy, f, p = _run_restart(starts[q], za, charge, lam, ranked, ws, act, tau, max_passes)
        xys[q] = xy
        fs[q] = f
        ps[q] = p
    return xys, fs, ps


# --------------------------------------------------------------------------- python side


def za_rows(a: Floats, ranked: Flags, ws: Floats, tau: float) -> Floats:
    """Soft ranks of each input row over its rank set, z-scored (weighted) over the scored
    entries."""
    size = len(a)
    off = ~np.eye(size, dtype=bool)
    if (ranked == off).all() and (ws == off).all():
        # Complete case: the original routine, bit for bit.
        return _z(soft_rank_rows(a, tau, off), off)[0]
    z = np.zeros((size, size))
    for i in range(size):
        r = np.where(ranked[i])[0]
        if len(r) == 0:
            continue
        v = a[i, r]
        sr = sig((v[:, None] - v[None, :]) / tau)
        np.fill_diagonal(sr, 0)
        sr = sr.sum(1)
        full = np.zeros(size)
        full[r] = sr
        w = ws[i]
        s = w > 0
        if s.sum() == 0:
            continue
        if np.all(w[s] == 1.0):
            mu = full[s].mean()
            sd = full[s].std()
        else:
            mu = (w[s] * full[s]).sum() / w[s].sum()
            sd = np.sqrt((w[s] * (full[s] - mu) ** 2).sum() / w[s].sum())
        sd = 1.0 if sd < 1e-12 else sd
        z[i, s] = (full[s] - mu) / sd
    return z


def hard_rank_spearman_m(a: Floats, dist: Floats, scored: Flags, act: Flags) -> float:
    """Restart selection: mean per-row hard-rank Spearman over the scored entries of the
    active rows."""
    vals: list[float] = []
    for i in range(len(a)):
        if not act[i]:
            continue
        s = scored[i]
        ai = a[i, s]
        di = dist[i, s]
        if np.ptp(ai) < 1e-12:
            continue
        ra, rd = rankdata(ai), rankdata(di)
        if np.ptp(rd) < 1e-12:
            vals.append(0.0)
            continue
        vals.append(-np.corrcoef(ra, rd)[0, 1])
    return float(np.mean(vals)) if vals else 0.0


@dataclass(frozen=True, slots=True)
class SoftRankSpearmanResult:
    """The kept restart's map in the unit square, its criterion ``f``, hard-rank Spearman
    ``hrs`` and passes; and every restart's ``f``, ``hrs`` and passes."""

    points: Floats
    f: float
    hrs: float
    passes: int
    all_f: list[float]
    all_hrs: list[float]
    all_passes: list[int]


#: Below this many objects the soft-rank layout takes its larger number of restarts.
FEW_OBJECTS: Final = 10


def soft_rank_spearman(
    prepared: PreparedInputs,
    *,
    repulsion_weight: float,
    seed: int,
    restarts_below_ten_objects: int,
    restarts: int,
    max_passes: int,
    min_partners: int,
) -> SoftRankSpearmanResult:
    """Soft-rank Spearman with Coulomb repulsion (the original's ``srs_coulomb_bb1``):
    ``R_layout`` and ``W_layout`` for the order term, ``Q`` for the repulsion; a row with
    fewer than ``min_partners`` layout partners leaves the order term (all rows stay when
    every pair has full weight). The first restart starts from classical scaling, the others
    from ``seed``'s generator."""
    a = prep_a(prepared.relation_layout)
    size = len(a)
    tau = 1.0 / min(size, 50) ** 2
    off = ~np.eye(size, dtype=bool)
    ws = np.asarray(prepared.layout_weight, float) * off
    ranked = ws > 0
    act = ranked.sum(1) >= min_partners
    if (ws == off).all():
        act = np.ones(size, bool)
    za = za_rows(a, ranked, ws, tau)
    charge = np.asarray(prepared.charge, float)
    lam = float(repulsion_weight)
    n_restarts = restarts_below_ten_objects if size < FEW_OBJECTS else restarts
    rng = np.random.default_rng(seed)
    starts = np.array(
        [
            classical_start(a) if r == 0 else rescale_unit(rng.random((size, 2)))
            for r in range(n_restarts)
        ]
    )
    xys, fs, ps = _run_all(
        np.ascontiguousarray(starts),
        np.ascontiguousarray(za),
        np.ascontiguousarray(charge),
        lam,
        np.ascontiguousarray(ranked),
        np.ascontiguousarray(ws),
        np.ascontiguousarray(act),
        tau,
        max_passes,
    )
    hrs = [
        hard_rank_spearman_m(a, np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1)), ranked, act)
        for xy in xys
    ]
    b = int(np.argmax(hrs))
    return SoftRankSpearmanResult(
        points=xys[b],
        f=float(fs[b]),
        hrs=hrs[b],
        passes=int(ps[b]),
        all_f=[float(f) for f in fs],
        all_hrs=hrs,
        all_passes=[int(p) for p in ps],
    )


# --------------------------------------------------------------------------- Interval MDS
# (interval_mds.py): weighted SMACOF, interval transformation, one-sided floor


def _dist_matrix(xy: Floats) -> Floats:
    out: Floats = np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1))
    return out


def classical(delta: Floats, w: Floats) -> tuple[Floats, Floats]:
    """Torgerson on the targets (an unfitted pair takes the mean fitted target), with a
    deterministic sign convention."""
    m = len(delta)
    known = w > 0
    np.fill_diagonal(known, True)
    mean = delta[known & ~np.eye(m, dtype=bool)].mean()
    d0 = np.where(known, np.nan_to_num(delta), mean)
    np.fill_diagonal(d0, 0)
    j = np.eye(m) - 1 / m
    b = -0.5 * j @ (d0**2) @ j
    vals, vecs = np.linalg.eigh(b)
    idx = np.argsort(vals)[::-1][:2]
    xy = vecs[:, idx] * np.sqrt(np.maximum(vals[idx], 0))
    for axis in range(2):
        if (xy[:, axis] ** 3).sum() < 0:
            xy[:, axis] *= -1
    return xy, vals[np.argsort(vals)[::-1]]


def _line(
    dist: Floats, delta: Floats, w: Floats, iu: tuple[Any, ...]
) -> tuple[Floats, tuple[float, float, float, float]]:
    """The interval transformation ``dhat(t) = c max(md + b (t - mt), 0)``."""
    wu = w[iu]
    t = delta[iu]
    d = dist[iu]
    sw = wu.sum()
    mt = (wu * t).sum() / sw
    md = (wu * d).sum() / sw
    b = (wu * (t - mt) * (d - md)).sum() / max((wu * (t - mt) ** 2).sum(), 1e-15)
    dh = np.maximum(md + b * (t - mt), 0.0)
    if b <= 0:
        # Degenerate guard.
        dh = np.full_like(t, md)
        b = 0.0
    npair = (wu > 0).sum()
    c = math.sqrt(npair / max((wu * dh * dh).sum(), 1e-15))
    return dh * c, (c, md, b, mt)


def _disparities(dist: Floats, delta: Floats, w: Floats, iu: tuple[Any, ...]) -> Floats:
    """Weighted disparities normalised so ``sum_{i<j} w dhat^2`` is the number of pairs."""
    dh, _ = _line(dist, delta, w, iu)
    h = np.zeros_like(dist)
    h[iu] = dh
    out: Floats = h + h.T
    return out


def _floor_value(
    dist: Floats, delta: Floats, w: Floats, iu: tuple[Any, ...], kappa: float
) -> float:
    _, (c, md, b, mt) = _line(dist, delta, w, iu)
    return kappa * c * max(md + b * (math.sqrt(2) - mt), 0.0)


def stress_n(
    xy: Floats, delta: Floats, w: Floats, u: Flags, kappa: float, wu: float = 1.0
) -> float:
    """Normalised stress at the optimal disparities, comparable across starts; with ``u``
    the unfitted pairs' floor violations are added with weight ``wu``."""
    m = len(xy)
    iu = np.triu_indices(m, 1)
    dist = _dist_matrix(xy)
    h_mat = _disparities(dist, delta, w, iu)
    wv, h, d = w[iu], h_mat[iu], dist[iu]
    a = (wv * h * d).sum() / max((wv * d * d).sum(), 1e-15)
    for _ in range(3):
        h_mat = _disparities(a * dist, delta, w, iu)
        h = h_mat[iu]
        a = (wv * h * d).sum() / max((wv * d * d).sum(), 1e-15)
    num = (wv * (h - a * d) ** 2).sum()
    den = (wv * h * h).sum()
    if u.any():
        f = _floor_value(a * dist, delta, w, iu, kappa)
        uv = u[iu]
        v = np.maximum(f - a * d, 0.0) * uv
        num += wu * (v**2).sum()
    return float(num / den)


@njit(cache=True, nogil=True)
def _smacof_interval_kernel(
    delta: Floats,
    w_fit: Floats,
    w_all: Floats,
    u: Flags,
    use_u: bool,
    vp: Floats,
    xy: Floats,
    itmax: int,
    eps: float,
    check: int,
    kappa: float,
) -> tuple[Floats, int]:
    m = xy.shape[0]
    dist = np.empty((m, m))
    h_mat = np.zeros((m, m))
    bm = np.empty((m, m))
    last = -1.0
    it_out = 0
    npair = 0
    for i in range(m):
        for j in range(i + 1, m):
            if w_fit[i, j] > 0:
                npair += 1
    for it in range(itmax):
        it_out = it
        for i in range(m):
            dist[i, i] = 0.0
            for j in range(i + 1, m):
                d = math.sqrt((xy[i, 0] - xy[j, 0]) ** 2 + (xy[i, 1] - xy[j, 1]) ** 2)
                dist[i, j] = d
                dist[j, i] = d
        # The disparity line: weighted regression of d on delta over i < j.
        sw = 0.0
        st = 0.0
        sd = 0.0
        for i in range(m):
            for j in range(i + 1, m):
                w = w_fit[i, j]
                sw += w
                st += w * delta[i, j]
                sd += w * dist[i, j]
        mt = st / sw
        md = sd / sw
        num = 0.0
        den = 0.0
        for i in range(m):
            for j in range(i + 1, m):
                w = w_fit[i, j]
                num += w * (delta[i, j] - mt) * (dist[i, j] - md)
                den += w * (delta[i, j] - mt) ** 2
        b = num / max(den, 1e-15)
        degen = b <= 0
        if degen:
            b = 0.0
        swh = 0.0
        for i in range(m):
            for j in range(i + 1, m):
                dh = md if degen else max(md + b * (delta[i, j] - mt), 0.0)
                h_mat[i, j] = dh
                swh += w_fit[i, j] * dh * dh
        c = math.sqrt(npair / max(swh, 1e-15))
        f = kappa * c * max(md + b * (math.sqrt(2.0) - mt), 0.0)
        for i in range(m):
            for j in range(i + 1, m):
                h = h_mat[i, j] * c
                if use_u and u[i, j]:
                    h = max(dist[i, j], f)
                h_mat[i, j] = h
                h_mat[j, i] = h
        for i in range(m):
            s = 0.0
            for j in range(m):
                if i != j and dist[i, j] > 1e-12:
                    v = -w_all[i, j] * h_mat[i, j] / dist[i, j]
                else:
                    v = 0.0
                bm[i, j] = v
                s += v
            bm[i, i] = -s + bm[i, i]
        xy = vp @ (bm @ xy)
        if it % check == 0:
            num = 0.0
            den = 0.0
            for i in range(m):
                for j in range(i + 1, m):
                    d = math.sqrt((xy[i, 0] - xy[j, 0]) ** 2 + (xy[i, 1] - xy[j, 1]) ** 2)
                    w = w_all[i, j]
                    h = h_mat[i, j]
                    num += w * (h - d) ** 2
                    den += w * h * h
            s = num / den
            if last >= 0 and last - s < eps * max(last, 1e-12):
                break
            last = s
    return xy, it_out + 1


#: Interval SMACOF stops after this many iterations at the latest.
SMACOF_ITMAX: Final = 1500


def smacof(
    delta: Floats,
    w: Floats,
    xy0: Floats,
    *,
    u: Flags,
    kappa: float,
    itmax: int = SMACOF_ITMAX,
    eps: float = 1e-8,
    check: int = 5,
    wu: float = 1.0,
) -> tuple[Floats, int]:
    """Interval SMACOF from ``xy0`` (the compiled loop); ``u`` marks the unfitted pairs with
    the one-sided floor ``kappa dhat(sqrt 2)``, weight ``wu``."""
    m = len(delta)
    use_u = bool(u.any())
    w_all = np.where(u, wu, w) if use_u else w.copy()
    if use_u:
        np.fill_diagonal(w_all, 0)
    v = -w_all.copy()
    np.fill_diagonal(v, 0)
    np.fill_diagonal(v, w_all.sum(1) - np.diag(w_all))
    vp = np.linalg.pinv(v)
    uk = u if use_u else np.zeros((m, m), np.bool_)
    xy, it = _smacof_interval_kernel(
        np.ascontiguousarray(delta, float),
        np.ascontiguousarray(w, float),
        np.ascontiguousarray(w_all, float),
        np.ascontiguousarray(uk),
        use_u,
        np.ascontiguousarray(vp),
        np.ascontiguousarray(xy0, float),
        itmax,
        eps,
        check,
        kappa,
    )
    out: Floats = xy - xy.mean(0)
    return out, int(it)


def multistart(
    delta: Floats,
    w: Floats,
    starts: int,
    *,
    u: Flags,
    kappa: float,
    seed0: int = 1,
    wu: float = 1.0,
) -> tuple[Floats, float, int]:
    """The Torgerson start (jittered from generator 0) and ``starts`` random starts
    (generators ``1000 + s``); the lowest normalised stress kept, with its iterations."""
    m = len(delta)
    t, _ = classical(np.where(w > 0, delta, np.nan), w)
    cands = [t + 1e-6 * np.random.default_rng(0).normal(size=t.shape)]
    scale = math.sqrt((t**2).sum() / m) or 1.0
    for s in range(seed0, seed0 + starts):
        cands.append(np.random.default_rng(1000 + s).normal(size=(m, 2)) * scale)
    best: Floats | None = None
    bf: float | None = None
    kept = 0
    for xy0 in cands:
        xy, it = smacof(delta, w, xy0, u=u, kappa=kappa, wu=wu)
        f = stress_n(xy, delta, w, u, kappa, wu)
        if bf is None or f < bf - 1e-12:
            best, bf, kept = xy, f, it
    assert best is not None and bf is not None
    return best, bf, kept


def interval_mds(prepared: PreparedInputs, *, starts: int, kappa: float) -> tuple[Floats, int]:
    """Interval MDS on the layout pairs (the original's ``interval_mds``): targets
    ``delta_layout``, precision weights ``W_mds_layout``; the pairs below the layout floor get
    the one-sided floor. Centred, in arbitrary units (see :func:`to_ruler`); with the kept
    start's iterations."""
    d = np.nan_to_num(prepared.delta_layout)
    w = prepared.precision_layout
    u = prepared.unknown_layout
    xy, _, it = multistart(d, w, starts, u=u, kappa=kappa)
    return xy, it


def to_ruler(xy: Any, delta: Floats, known: Flags) -> Floats:
    """One uniform least-squares scale of a centred layout to ruler (``delta``) units over the
    known pairs; with none, the root-mean-square distance becomes that of unrelated objects,
    ``sqrt 2``."""
    xy = np.asarray(xy, float)
    xy = xy - xy.mean(0)
    iu = np.triu_indices(len(xy), 1)
    d = np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1))[iu]
    dl = np.nan_to_num(delta)[iu]
    k = known[iu]
    if k.sum() == 0 or (d[k] @ d[k]) <= 0:
        out: Floats = xy * math.sqrt(2) / max(math.sqrt((d**2).mean()), 1e-12)
        return out
    scaled: Floats = xy * (d[k] @ dl[k]) / (d[k] @ d[k])
    return scaled
