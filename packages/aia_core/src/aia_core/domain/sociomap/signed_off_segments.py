"""The signed-off AIA Sociomapa methodology's taste segments (``aia-sociomap-5``).

Ported as written from the methodology folder's ``respondents.py`` (``respondent_slopes``,
``_xd_em`` with its compiled EM loop, ``find_segments``, ``_segments_from_fit``,
``consensus_maps``, ``_consensus_state``, ``find_segments_consensus``, ``segment_profiles``),
the owner's code, kept outside this repository (``tests/test_sociomap_signed_off_segments.py``).
With the mapped objects fixed at their ruler positions:

* each respondent's vector-model slope and its noise covariance (:func:`respondent_slopes`),
  from at least the declared number of ratings that are not all equal: the slope is linear in
  the respondent's taste, so a set without segments is one Gaussian cloud;
* a Gaussian mixture of 1 to ``max_segments`` segments in which each slope keeps its own noise
  (extreme deconvolution: k-means++ starts, an EM loop compiled by numba), the number of
  segments chosen by ``-2 log L + penalty_factor * p * ln n``, ``p = 6k - 1``; nothing is
  looked for below ``min_respondents`` respondents with a slope;
* the shuffle guard: the same fit on copies of the ratings with each respondent's ratings
  permuted among the objects they rated; segments only when the real gain beats every
  shuffled gain. Shuffles are drawn in order from one generator and fitted
  :data:`SHUFFLE_BATCH` at a time; the loop stops after the first batch in which a shuffle
  matches the real gain;
* the step-down against over-splitting (the last segment's share of the gain, the smallest
  segment, the two closest segments), each tested on the fit with that many segments;
* the decision on the shown map and on maps of the ratings jittered at the rounding level
  (:func:`consensus_state`): segments, none, or borderline, when the penalised margins
  averaged over the maps lie within the declared band;
* each segment's labels (largest first), membership, shares, separation, and the colour mask:
  membership at least the declared level and the respondent clearly placed;
* the profiles (:func:`segment_profiles`): each segment's mean respondent-centred raw rating
  of every object against everyone else's, weighted by membership, with a normal test and
  Benjamini-Hochberg over all segments and objects.

Unweighted: survey weights do not enter. The slopes read the ratings on the declared 0-1
scale, the profiles the raw ratings, as the methodology does.

Pure: no I/O; the only randomness is numpy's seeded generators. The shuffles run in threads
(the EM loop releases the GIL); each is fitted from its own copy of the ratings, so the threads
change when a result is ready, never what it is.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Final

import numpy as np
from numba import njit
from numpy.typing import NDArray
from scipy.stats import norm

from .specification import TasteSegmentsSpec

__all__ = [
    "BORDERLINE",
    "NONE",
    "NOT_ABOVE_SHUFFLED",
    "NOT_STABLE",
    "NO_CLEAR_SEGMENTS",
    "SEGMENTS",
    "SHUFFLE_BATCH",
    "TOO_FEW_RESPONDENTS",
    "MapDecision",
    "Profiles",
    "Segments",
    "Slopes",
    "Split",
    "consensus_state",
    "jittered_ratings",
    "map_decision",
    "respondent_slopes",
    "segment_profiles",
    "taste_segments",
]

Floats = NDArray[np.float64]
Flags = NDArray[np.bool_]
Labels = NDArray[np.int64]

#: The decision.
SEGMENTS: Final = "SEGMENTS"
NONE: Final = "NONE"
BORDERLINE: Final = "BORDERLINE"
#: Why there are no segments.
TOO_FEW_RESPONDENTS: Final = "TOO_FEW_RESPONDENTS"
NO_CLEAR_SEGMENTS: Final = "NO_CLEAR_SEGMENTS"
NOT_ABOVE_SHUFFLED: Final = "NOT_ABOVE_SHUFFLED"
NOT_STABLE: Final = "NOT_STABLE"

#: The vector model's parameters per respondent: an intercept and two slopes.
_PARAMETERS: Final = 3
#: At or below this sum of squares a respondent's ratings have no spread.
_NO_SPREAD: Final = 1e-12
#: The mixture's fixed settings (the methodology's): k-means++ starts per number of segments
#: above one, the EM loop's iteration cap and relative tolerance, and the floor of a
#: covariance's eigenvalues relative to its largest.
EM_STARTS: Final = 3
EM_ITERATIONS: Final = 200
EM_TOLERANCE: Final = 1e-6
EIGENVALUE_FLOOR: Final = 1e-6
_KMEANS_ITERATIONS: Final = 50
#: The generators' offsets from the declared seed: the shuffles' stream, and each jittered
#: map's (times its number, from 1).
SHUFFLE_STREAM: Final = 7919
JITTER_STREAM: Final = 104729
#: Shuffles fitted at a time. Fixed, never the machine's core count: the guard stops after the
#: first batch with a shuffle as strong as the real data, so the largest shuffled gain it
#: records depends on the batch size.
SHUFFLE_BATCH: Final = 4


@dataclass(frozen=True, slots=True)
class Slopes:
    """Each respondent's slope (N x 2), its noise covariance (N x 2 x 2) and whether the
    respondent has one (enough ratings, not all equal)."""

    slope: Floats
    noise: Floats
    eligible: Flags


def respondent_slopes(points: Floats, ratings: Floats, *, min_ratings: int) -> Slopes:
    """The vector model's slopes: ``points`` the objects' ruler positions (M x 2), ``ratings``
    each respondent's ratings of them on the declared 0-1 scale (N x M, NaN where not rated)."""
    y = np.asarray(points, float)
    a = np.asarray(ratings, float)
    n, m = a.shape
    rated = np.isfinite(a)
    a0 = np.where(rated, a, 0.0)
    nr = rated.sum(1)
    z = np.c_[np.ones(m), y]
    gram = (rated.astype(float) @ (z[:, :, None] * z[:, None, :]).reshape(m, 9)).reshape(n, 3, 3)
    b = a0 @ z
    mean = a0.sum(1) / np.maximum(nr, 1)
    sst = (rated * (a0 - mean[:, None]) ** 2).sum(1)
    ok = (nr >= min_ratings) & (sst > _NO_SPREAD)
    inverse = np.zeros((n, 3, 3))
    inverse[ok] = np.linalg.pinv(gram[ok])
    beta = np.einsum("kij,kj->ki", inverse, b)
    ssr = (rated * (a0 - beta @ z.T) ** 2).sum(1)
    s2 = np.where(ok, ssr / np.maximum(nr - _PARAMETERS, 1), 0.0)
    return Slopes(slope=beta[:, 1:], noise=inverse[:, 1:, 1:] * s2[:, None, None], eligible=ok)


def _psd(s: Floats, eps: float = EIGENVALUE_FLOOR) -> Floats:
    w, u = np.linalg.eigh((s + s.T) / 2)
    out: Floats = (u * np.maximum(w, eps * max(w.max(), 1e-9))) @ u.T
    return out


def _kmeans(x: Floats, k: int, rng: np.random.Generator, iters: int = _KMEANS_ITERATIONS) -> Any:
    chosen = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d = np.min(((x[:, None] - np.array(chosen)[None]) ** 2).sum(-1), 1)
        chosen.append(x[rng.choice(len(x), p=d / d.sum())])
    c = np.array(chosen)
    lab = np.zeros(len(x), int)
    for _ in range(iters):
        lab = ((x[:, None] - c[None]) ** 2).sum(-1).argmin(1)
        c = np.array([x[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
    return lab


# --------------------------------------------------------------------------- the compiled
# EM loop (respondents._psd2, _em), statement for statement


@njit(cache=True, nogil=True)
def _psd2(a: float, b: float, c: float, eps: float) -> tuple[float, float, float]:
    """(a b; b c) with eigenvalues floored at eps * max(w_max, 1e-9), as :func:`_psd`."""
    tr = a + c
    df = a - c
    r = np.sqrt(0.25 * df * df + b * b)
    w1 = 0.5 * tr + r
    w0 = 0.5 * tr - r
    fl = eps * max(w1, 1e-9)
    if w0 >= fl:
        return a, b, c
    w0f = max(w0, fl)
    w1f = max(w1, fl)
    if r < 1e-300:
        return w1f, 0.0, w1f
    # The eigenvector of w1: (b, w1 - a) or (w1 - c, b), whichever is longer.
    x, y = (b, w1 - a) if abs(b) + abs(w1 - a) > abs(w1 - c) + abs(b) else (w1 - c, b)
    nrm = np.sqrt(x * x + y * y)
    x /= nrm
    y /= nrm
    return w1f * x * x + w0f * y * y, (w1f - w0f) * x * y, w1f * y * y + w0f * x * x


@njit(cache=True, nogil=True)
def _em(
    x0: Floats,
    x1: Floats,
    v00: Floats,
    v01: Floats,
    v11: Floats,
    al: Floats,
    m: Floats,
    s: Floats,
    iters: int,
    tol: float,
) -> tuple[float, Floats]:
    n = x0.shape[0]
    k = al.shape[0]
    big_l = np.empty((n, k))
    big_r = np.empty((n, k))
    ll_old = -np.inf
    ll = 0.0
    b0 = np.empty((n, k))
    b1 = np.empty((n, k))
    c00 = np.empty((n, k))
    c01 = np.empty((n, k))
    c11 = np.empty((n, k))
    l2p = 2.0 * np.log(2 * np.pi)
    for _ in range(iters):
        ll = 0.0
        for i in range(n):
            mx = -np.inf
            for j in range(k):
                s00 = s[j, 0, 0]
                s01 = s[j, 0, 1]
                s11 = s[j, 1, 1]
                t00 = s00 + v00[i]
                t01 = s01 + v01[i]
                t11 = s11 + v11[i]
                det = t00 * t11 - t01 * t01
                i00 = t11 / det
                i01 = -t01 / det
                i11 = t00 / det
                d0 = x0[i] - m[j, 0]
                d1 = x1[i] - m[j, 1]
                u0 = i00 * d0 + i01 * d1
                u1 = i01 * d0 + i11 * d1
                big_l[i, j] = np.log(max(al[j], 1e-300)) - 0.5 * (
                    d0 * u0 + d1 * u1 + np.log(det) + l2p
                )
                if big_l[i, j] > mx:
                    mx = big_l[i, j]
                b0[i, j] = m[j, 0] + s00 * u0 + s01 * u1
                b1[i, j] = m[j, 1] + s01 * u0 + s11 * u1
                p00 = s00 * i00 + s01 * i01
                p01 = s00 * i01 + s01 * i11
                p10 = s01 * i00 + s11 * i01
                p11 = s01 * i01 + s11 * i11
                c00[i, j] = s00 - (p00 * s00 + p01 * s01)
                c01[i, j] = s01 - (p00 * s01 + p01 * s11)
                c11[i, j] = s11 - (p10 * s01 + p11 * s11)
            sm = 0.0
            for j in range(k):
                big_r[i, j] = np.exp(big_l[i, j] - mx)
                sm += big_r[i, j]
            for j in range(k):
                big_r[i, j] /= sm
            ll += mx + np.log(sm)
        for j in range(k):
            nk = 1e-12
            a0 = 0.0
            a1 = 0.0
            for i in range(n):
                nk += big_r[i, j]
                a0 += big_r[i, j] * b0[i, j]
                a1 += big_r[i, j] * b1[i, j]
            al[j] = nk / n
            m[j, 0] = a0 / nk
            m[j, 1] = a1 / nk
            m00 = 0.0
            m01 = 0.0
            m11 = 0.0
            for i in range(n):
                e0 = m[j, 0] - b0[i, j]
                e1 = m[j, 1] - b1[i, j]
                m00 += big_r[i, j] * (e0 * e0 + c00[i, j])
                m01 += big_r[i, j] * (e0 * e1 + c01[i, j])
                m11 += big_r[i, j] * (e1 * e1 + c11[i, j])
            a, b, c = _psd2(m00 / nk, m01 / nk, m11 / nk, 1e-6)
            s[j, 0, 0] = a
            s[j, 0, 1] = b
            s[j, 1, 0] = b
            s[j, 1, 1] = c
        if ll - ll_old < tol * abs(ll):
            break
        ll_old = ll
    return ll, big_r


@dataclass(frozen=True, slots=True)
class _Fit:
    """The best start's mixture with ``k`` segments: log-likelihood, shares, means,
    covariances and each respondent's membership (n x k)."""

    log_likelihood: float
    shares: Floats
    means: Floats
    covariances: Floats
    membership: Floats


def _xd_em(wd: Floats, v: Floats, k: int, seed: int) -> _Fit:
    """Extreme deconvolution (Bovy, Hogg & Roweis 2011): a Gaussian mixture in which every
    point has its own noise covariance. k = 1 runs one start: its starts would be identical."""
    n = len(wd)
    best: _Fit | None = None
    rng = np.random.default_rng(seed)
    x0, x1 = np.ascontiguousarray(wd[:, 0]), np.ascontiguousarray(wd[:, 1])
    v00, v01, v11 = (np.ascontiguousarray(v[:, a, b]) for a, b in ((0, 0), (0, 1), (1, 1)))
    for _ in range(EM_STARTS if k > 1 else 1):
        lab = _kmeans(wd, k, rng) if k > 1 else np.zeros(n, int)
        vm = v.mean(0)
        al = np.array([(lab == j).mean() for j in range(k)]) + 1e-6
        al /= al.sum()
        m = np.array(
            [wd[lab == j].mean(0) if (lab == j).sum() > 0 else wd.mean(0) for j in range(k)]
        )
        s = np.array(
            [
                _psd((np.cov(wd[lab == j].T) if (lab == j).sum() > 2 else np.cov(wd.T)) - 0.5 * vm)
                for j in range(k)
            ]
        )
        ll, r = _em(x0, x1, v00, v01, v11, al, m, s, EM_ITERATIONS, EM_TOLERANCE)
        if best is None or ll > best.log_likelihood:
            best = _Fit(log_likelihood=ll, shares=al, means=m, covariances=s, membership=r)
    assert best is not None  # at least one start
    return best


@dataclass(frozen=True, slots=True)
class _Fits:
    """The penalised criterion and the fit for k = 1 .. max_segments, who has a slope, and
    how many do."""

    criterion: list[float]
    fits: list[_Fit]
    eligible: Flags
    n: int


def _seg_fit(points: Floats, ratings: Floats, rules: TasteSegmentsSpec) -> _Fits | None:
    """Every fit; ``None`` when fewer than ``min_respondents`` respondents have a slope."""
    slopes = respondent_slopes(points, ratings, min_ratings=rules.min_ratings)
    ok = slopes.eligible
    wd, vk = slopes.slope[ok], slopes.noise[ok]
    n = len(wd)
    if n < rules.min_respondents:
        return None
    criterion: list[float] = []
    fits: list[_Fit] = []
    for j in range(1, rules.max_segments + 1):
        f = _xd_em(wd, vk, j, rules.seed)
        fits.append(f)
        p = (j - 1) + 2 * j + 3 * j
        criterion.append(float(-2 * f.log_likelihood + rules.penalty_factor * p * np.log(n)))
    return _Fits(criterion=criterion, fits=fits, eligible=ok, n=n)


def _shuffle_within(ratings: Floats, rng: np.random.Generator) -> Floats:
    """Each respondent's ratings permuted among the objects they rated: it keeps rating
    habits and the missing pattern and removes the shared taste."""
    a = np.array(ratings, float, copy=True)
    for i in range(len(a)):
        r = np.where(np.isfinite(a[i]))[0]
        a[i, r] = a[i, rng.permutation(r)]
    return a


def _min_sep(mu: Floats, sg: Floats) -> float:
    """The smallest separation ``sqrt(dm' [(S_a + S_b) / 2]^-1 dm)`` between segment means."""
    k = len(mu)
    return min(
        float(np.sqrt((mu[a] - mu[b]) @ np.linalg.solve((sg[a] + sg[b]) / 2, mu[a] - mu[b])))
        for a in range(k)
        for b in range(a + 1, k)
    )


@dataclass(frozen=True, slots=True)
class MapDecision:
    """The decision on one map: the number of segments shown (0 for none), why none, the gain
    of the segment model, the largest shuffled gain (``None`` when the guard did not run), the
    penalised margin (NaN with too few respondents), the fit's own number before the
    step-down (``None`` unless the step-down ran), and the fits."""

    k: int
    reason: str | None
    gain: float
    null_gain_max: float | None
    margin: float
    k_fit: int | None
    fitted: _Fits | None


def map_decision(points: Floats, ratings: Floats, rules: TasteSegmentsSpec) -> MapDecision:
    """The methodology's ``find_segments`` decision on one map."""
    fitted = _seg_fit(points, ratings, rules)
    if fitted is None:
        return MapDecision(0, TOO_FEW_RESPONDENTS, 0.0, None, np.nan, None, None)
    crit, fits = fitted.criterion, fitted.fits
    k = int(np.argmin(crit)) + 1
    gain = float(crit[0] - min(crit))
    # Below 0 the best mixture with segments beats one segment.
    margin = float(min(crit[1:]) - crit[0])
    if k == 1:
        return MapDecision(0, NO_CLEAR_SEGMENTS, gain, None, margin, None, fitted)
    null_max = None
    if rules.shuffles:
        null_max = _largest_shuffled_gain(points, ratings, rules, gain)
        if gain <= null_max:
            return MapDecision(0, NOT_ABOVE_SHUFFLED, gain, null_max, margin, None, fitted)
    k_fit = k
    ll = [f.log_likelihood for f in fits]
    while k >= 3 and (ll[k - 1] - ll[k - 2]) < rules.min_gain_share * (ll[k - 1] - ll[0]):
        k -= 1
    while k >= 2 and fits[k - 1].shares.min() < rules.min_segment_share:
        k -= 1
    while k >= 2 and _min_sep(fits[k - 1].means, fits[k - 1].covariances) < rules.min_separation:
        k -= 1
    if k < 2:
        return MapDecision(0, NO_CLEAR_SEGMENTS, gain, null_max, margin, k_fit, fitted)
    return MapDecision(k, None, gain, null_max, margin, k_fit, fitted)


def _largest_shuffled_gain(
    points: Floats, ratings: Floats, rules: TasteSegmentsSpec, gain: float
) -> float:
    """The shuffle guard: shuffles drawn in order from one stream, fitted
    :data:`SHUFFLE_BATCH` at a time, stopping after the first batch with a shuffle as strong
    as the real data (the decision is then the same whatever the rest would give)."""
    rng = np.random.default_rng(rules.seed + SHUFFLE_STREAM)
    gains: list[float] = []

    def shuffled_gain(shuffled: Floats) -> float:
        fitted = _seg_fit(points, shuffled, rules)
        if fitted is None:
            return 0.0
        return float(fitted.criterion[0] - min(fitted.criterion))

    with ThreadPoolExecutor(SHUFFLE_BATCH) as pool:
        while len(gains) < rules.shuffles:
            batch = [
                _shuffle_within(ratings, rng)
                for _ in range(min(SHUFFLE_BATCH, rules.shuffles - len(gains)))
            ]
            gains += list(pool.map(shuffled_gain, batch))
            if max(gains) >= gain:
                break
    return float(max(gains))


@dataclass(frozen=True, slots=True)
class Split:
    """The segments of the fit with ``k`` segments on the shown map, relabelled largest
    first: each respondent's label (-1 without a slope), membership of each segment (N x k,
    NaN without a slope) and largest membership, the shares, the means and covariances, the
    smallest separation, whether the segments are distinct, and who is coloured."""

    k: int
    labels: Labels
    post: Floats
    membership: Floats
    shares: list[float]
    means: Floats
    covariances: Floats
    separation: float
    distinct: bool
    coloured: Flags


def _segments_from_fit(fitted: _Fits, k: int, placed: Flags, rules: TasteSegmentsSpec) -> Split:
    ok = fitted.eligible
    n = len(ok)
    lab = np.full(n, -1)
    fit = fitted.fits[k - 1]
    r = fit.membership
    lab[ok] = r.argmax(1)
    mu_, sg_ = fit.means, fit.covariances
    order = np.argsort([-(lab == j).sum() for j in range(k)])
    relab = np.full(k, 0)
    relab[order] = np.arange(k)
    lab[ok] = relab[lab[ok]]
    post = np.full((n, k), np.nan)
    post[np.ix_(ok, relab)] = r
    share = [float((lab == j).sum() / ok.sum()) for j in range(k)]
    inv = np.argsort(relab)
    mu_, sg_ = mu_[inv], sg_[inv]
    sep = np.full((k, k), np.inf)
    for a in range(k):
        for b in range(k):
            if a != b:
                dm = mu_[a] - mu_[b]
                sep[a, b] = float(np.sqrt(dm @ np.linalg.solve((sg_[a] + sg_[b]) / 2, dm)))
    separation = float(sep[np.isfinite(sep)].min())
    # The largest membership of each respondent with a slope; the others have none (NaN).
    prob = np.full(n, np.nan)
    prob[ok] = post[ok].max(1)
    return Split(
        k=k,
        labels=lab,
        post=post,
        membership=prob,
        shares=share,
        means=mu_,
        covariances=sg_,
        separation=separation,
        distinct=bool(separation >= rules.distinct_separation),
        coloured=(np.nan_to_num(prob) >= rules.colour_membership) & (lab >= 0) & placed,
    )


def consensus_state(margins: Floats, ks: Sequence[int], band: float) -> str:
    """Segments, none or borderline from the maps' penalised margins (below 0 favours
    segments) and numbers of segments shown: segments when the mean margin is below ``-band``
    and at least half the maps show segments; none when it is above ``band``, or no map shows
    segments and it is above 0; borderline otherwise."""
    m = float(np.nanmean(margins)) if np.isfinite(margins).any() else np.inf
    v = float(np.mean([int(k) >= 2 for k in ks]))
    if m < -band and v >= 0.5:
        return SEGMENTS
    if m > band or (v == 0 and m > 0):
        return NONE
    return BORDERLINE


@dataclass(frozen=True, slots=True)
class Segments:
    """The decision (:data:`SEGMENTS`, :data:`NONE` or :data:`BORDERLINE`) and why none; the
    shown map's gain, largest shuffled gain and fit's own number before the step-down; each
    map's margin rounded to two decimals as the methodology records it (``None`` for a map
    with too few respondents), their mean, the maps showing segments and the maps (all
    ``None`` without jittered maps); the segments (:data:`SEGMENTS` only) or the likely split
    (:data:`BORDERLINE` only)."""

    decision: str
    reason: str | None
    gain: float
    null_gain_max: float | None
    k_fit: int | None
    margins: tuple[float | None, ...] | None
    mean_margin: float | None
    votes: int | None
    maps: int | None
    split: Split | None
    hint: Split | None


def _mode(ks: list[int]) -> int:
    """The most common number of segments, the smaller on a tie."""
    return min(set(ks), key=lambda k: (-ks.count(k), k))


def taste_segments(
    points: Floats,
    other_maps: Sequence[Floats],
    ratings: Floats,
    placed: Flags,
    rules: TasteSegmentsSpec,
) -> Segments:
    """The methodology's ``find_segments_consensus`` on the shown map ``points`` and the
    jittered maps ``other_maps`` (ruler units), from each respondent's ratings on the declared
    0-1 scale (N x M, NaN where not rated); ``placed`` marks the clearly placed respondents.
    Without other maps the shown map's decision stands alone."""
    main = map_decision(points, ratings, rules)

    def shown(decision: MapDecision, **consensus: Any) -> Segments:
        split = (
            None
            if decision.fitted is None or decision.k < 2
            else _segments_from_fit(decision.fitted, decision.k, placed, rules)
        )
        return Segments(
            decision=SEGMENTS if split is not None else NONE,
            reason=decision.reason,
            gain=decision.gain,
            null_gain_max=decision.null_gain_max,
            k_fit=decision.k_fit,
            margins=consensus.get("margins"),
            mean_margin=consensus.get("mean_margin"),
            votes=consensus.get("votes"),
            maps=consensus.get("maps"),
            split=split,
            hint=None,
        )

    if not len(other_maps):
        return shown(main)
    others = [map_decision(other, ratings, rules) for other in other_maps]
    ks = [main.k] + [o.k for o in others]
    margins = np.array([main.margin] + [o.margin for o in others], float)
    state = consensus_state(margins, ks, rules.borderline_margin)
    yes_ks = [k for k in ks if k >= 2]
    finite = bool(np.isfinite(margins).any())
    info: dict[str, Any] = {
        "margins": tuple(round(float(x), 2) if np.isfinite(x) else None for x in margins.tolist()),
        "mean_margin": float(np.nanmean(margins)) if finite else None,
        "votes": len(yes_ks),
        "maps": len(ks),
    }
    if state == SEGMENTS:
        if main.k >= 2:
            return shown(main, **info)
        # The shown map alone showed none: its fit with the other maps' most common number.
        assert main.fitted is not None  # a mean margin below -band is finite
        k_mode = _mode(yes_ks)
        return Segments(
            decision=SEGMENTS,
            reason=None,
            gain=main.gain,
            null_gain_max=main.null_gain_max,
            k_fit=k_mode,
            split=_segments_from_fit(main.fitted, k_mode, placed, rules),
            hint=None,
            **info,
        )
    if state == NONE:
        if main.k < 2:
            return shown(main, **info)
        return Segments(
            decision=NONE,
            reason=NOT_STABLE,
            gain=main.gain,
            null_gain_max=main.null_gain_max,
            k_fit=None,
            split=None,
            hint=None,
            **info,
        )
    if main.fitted is None:
        return shown(main, **info)
    k_hint = _mode(yes_ks) if yes_ks else int(np.argmin(main.fitted.criterion[1:])) + 2
    return Segments(
        decision=BORDERLINE,
        reason=None,
        gain=main.gain,
        null_gain_max=main.null_gain_max,
        k_fit=None,
        split=None,
        hint=_segments_from_fit(main.fitted, k_hint, placed, rules),
        **info,
    )


def jittered_ratings(ratings: Floats, *, copies: int, jitter: float, seed: int) -> list[Floats]:
    """The raw ratings with a jitter at the rounding level, one copy per jittered map: enough
    to send the soft-rank layout to another, equally good map. Each copy is laid out exactly
    as the shown map; only their segment decisions are used."""
    a = np.ascontiguousarray(ratings, dtype=float)
    return [
        a + np.random.default_rng(seed + JITTER_STREAM * (j + 1)).normal(size=a.shape) * jitter
        for j in range(copies)
    ]


@dataclass(frozen=True, slots=True)
class Profiles:
    """What each segment rates above or below everyone else (k x M): the difference of
    respondent-centred raw ratings, its standard error and two-sided p-value, whether it is
    distinctive (Benjamini-Hochberg over all segments and objects), and per segment up to
    ``top`` distinctive objects rated higher (largest first) and lower (lowest first), as
    column indices."""

    difference: Floats
    standard_error: Floats
    p_value: Floats
    distinctive: Flags
    likes: list[list[int]]
    dislikes: list[list[int]]


def segment_profiles(
    raw: Floats, split: Split, *, false_discovery_rate: float, top: int
) -> Profiles:
    """The methodology's ``segment_profiles`` of ``split`` from the raw ratings (N x M, NaN
    where not rated), so the differences are in rating units."""
    a = np.asarray(raw, float)
    k, m = split.k, a.shape[1]
    rated = np.isfinite(a)
    count = rated.sum(1, keepdims=True)
    # The row mean of the rated objects; a respondent who rated nothing has none (and no slope).
    total = np.where(rated, a, 0.0).sum(1, keepdims=True)
    mean = np.divide(total, count, out=np.full(total.shape, np.nan), where=count > 0)
    c = a - mean
    ok = split.labels >= 0
    f = np.isfinite(c) & ok[:, None]
    x = np.where(f, c, 0.0)

    def wm(w: Floats) -> tuple[Floats, Floats]:
        weights = f * w[:, None]
        sw = weights.sum(0)
        mm = (weights * x).sum(0) / np.maximum(sw, 1e-12)
        v = (weights * (x - mm) ** 2).sum(0) / np.maximum(sw, 1e-12)
        neff = sw**2 / np.maximum((weights**2).sum(0), 1e-12)
        return mm, v / np.maximum(neff, 1)

    d = np.zeros((k, m))
    se = np.zeros((k, m))
    for g in range(k):
        r = np.nan_to_num(split.post[:, g])
        m1, v1 = wm(r)
        m0, v0 = wm(np.where(ok, 1 - r, 0.0))
        d[g] = m1 - m0
        se[g] = np.sqrt(v1 + v0)
    pv = 2 * norm.sf(np.abs(d / np.maximum(se, 1e-12)))
    p = pv.ravel()
    o = np.argsort(p)
    size = len(p)
    passed = np.where(p[o] <= false_discovery_rate * np.arange(1, size + 1) / size)[0]
    flat = np.zeros(size, bool)
    if len(passed):
        flat[o[: passed.max() + 1]] = True
    flag = flat.reshape(k, m)
    likes = [
        [int(j) for j in np.argsort(-d[g]) if flag[g, j] and d[g, j] > 0][:top] for g in range(k)
    ]
    dislikes = [
        [int(j) for j in np.argsort(d[g]) if flag[g, j] and d[g, j] < 0][:top] for g in range(k)
    ]
    return Profiles(
        difference=d,
        standard_error=se,
        p_value=pv,
        distinctive=flag,
        likes=likes,
        dislikes=dislikes,
    )
