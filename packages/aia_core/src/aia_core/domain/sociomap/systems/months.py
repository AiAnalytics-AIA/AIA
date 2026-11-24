"""Sociomapa systémů, the month map's relation test (decision SM12, answers Q-TIMETEST).

Months follow each other, so they are not independent rows. Every relation between two monthly
series is tested in an order that keeps their autocorrelation:

1. a trend declared before any result is seen is removed (``"none"`` or ``"linear"``);
2. the relation is Pearson's r on the detrended series;
3. its p-value comes from IAAFT surrogates (Schreiber & Schmitz 1996), 1,000 per series by
   default: series with the same spectrum and value distribution as the real one, but no link to
   the other series; each surrogate set is checked to reproduce the series' autocorrelation;
4. the p-values of all pairs are corrected by Benjamini-Yekutieli, which holds under the dependence
   these tests share (Benjamini-Hochberg has no such guarantee);
5. each pair carries its effective number of months (Pyper & Peterman 1998, modified), printed
   beside it, e.g. 34.6 of 36;
6. a series shorter than :data:`MIN_MONTHS` is described, never mapped (:class:`TooFewMonths`);
7. the false-pair rate measured on planted no-link data is declared before use and travels with
   the result, so every month map prints it.

Pure: no I/O; the only randomness is numpy's seeded generators.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "MIN_MONTHS",
    "MonthPair",
    "MonthRelations",
    "TooFewMonths",
    "autocorrelation",
    "benjamini_yekutieli",
    "detrend",
    "effective_months",
    "iaaft",
    "month_relations",
]

Floats = NDArray[np.float64]
Trend = Literal["none", "linear"]

MIN_MONTHS = 36
"""Below this a month series is described, not mapped (Aram's question 4: at 24 months the test
found 1 of 16 planted pairs; at 36 and 60 it found them under low inertia)."""


class TooFewMonths(ValueError):
    """The series is shorter than :data:`MIN_MONTHS`: describe it, draw no map."""


def detrend(series: Floats, trend: Trend) -> Floats:
    """The series with its declared trend removed; ``"none"`` returns it centred."""
    x = np.asarray(series, float)
    if trend == "none":
        return x - x.mean()
    if trend == "linear":
        t = np.arange(x.size, dtype=float)
        slope, intercept = np.polyfit(t, x, 1)
        residual: Floats = x - (slope * t + intercept)
        return residual
    raise ValueError(f"unknown trend {trend!r}")


def autocorrelation(series: Floats, lags: int) -> Floats:
    """Autocorrelation at lags 1..``lags`` (the biased estimator, as Pyper & Peterman use it)."""
    x = np.asarray(series, float) - np.mean(series)
    denominator = float((x**2).sum())
    if denominator == 0:
        return np.zeros(lags)
    return np.array([(x[:-k] * x[k:]).sum() / denominator for k in range(1, lags + 1)])


def iaaft(series: Floats, count: int, *, seed: int, iterations: int = 100) -> Floats:
    """``count`` IAAFT surrogates of ``series`` (rows): each keeps the series' amplitude spectrum
    and its exact value distribution, with the phases randomised."""
    x = np.asarray(series, float)
    sorted_values = np.sort(x)
    amplitudes = np.abs(np.fft.rfft(x))
    rng = np.random.default_rng(seed)
    out = np.empty((count, x.size))
    for row in range(count):
        surrogate = rng.permutation(x)
        for _ in range(iterations):
            phases = np.angle(np.fft.rfft(surrogate))
            spectral = np.fft.irfft(amplitudes * np.exp(1j * phases), n=x.size)
            ranked = np.empty_like(spectral)
            ranked[np.argsort(spectral)] = sorted_values
            if np.array_equal(ranked, surrogate):
                break
            surrogate = ranked
        out[row] = surrogate
    return out


def effective_months(x: Floats, y: Floats) -> float:
    """Pyper & Peterman's (1998) modified effective sample size for the correlation of ``x`` and
    ``y``, capped at N:

        1/N* = 1/N + (2/N) * sum_{j=1}^{N/5} ((N - j) / N) * rho_xx(j) * rho_yy(j)
    """
    n = len(x)
    lags = max(1, n // 5)
    rx, ry = autocorrelation(x, lags), autocorrelation(y, lags)
    weights = (n - np.arange(1, lags + 1)) / n
    inverse = 1 / n + (2 / n) * float((weights * rx * ry).sum())
    return float(min(n, 1 / inverse)) if inverse > 0 else float(n)


def benjamini_yekutieli(p_values: Floats, q: float) -> tuple[NDArray[np.bool_], Floats]:
    """Which hypotheses Benjamini-Yekutieli rejects at false-discovery rate ``q``, and the adjusted
    p-values (the step-up BH adjustment times the harmonic sum c(m) = sum_{i=1}^m 1/i)."""
    p = np.asarray(p_values, float)
    m = p.size
    if m == 0:
        return np.zeros(0, bool), np.zeros(0)
    c = float((1 / np.arange(1, m + 1)).sum())
    order = np.argsort(p)
    ranked = p[order] * m * c / np.arange(1, m + 1)
    adjusted_sorted = np.minimum(1.0, np.minimum.accumulate(ranked[::-1])[::-1])
    adjusted = np.empty(m)
    adjusted[order] = adjusted_sorted
    return adjusted <= q, adjusted


@dataclass(frozen=True)
class MonthPair:
    first: str
    second: str
    r: float
    p_value: float
    adjusted_p: float
    effective_months: float
    months: int
    accepted: bool
    """Passed the test after the correction: only accepted pairs are drawn as lines (SM14)."""


@dataclass(frozen=True)
class MonthRelations:
    pairs: tuple[MonthPair, ...]
    trend: Trend
    q: float
    surrogates_per_series: int
    declared_false_pair_rate: float
    """The false-pair rate measured on planted no-link data before use (SM12); printed."""
    autocorrelation_reproduced: Mapping[str, bool]
    """Per series: did its surrogates reproduce its autocorrelation within the tolerance."""


def _pearson(a: Floats, b: Floats) -> float:
    sa, sb = a.std(), b.std()
    if sa == 0 or sb == 0:
        return 0.0
    return float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))


def month_relations(
    series: Mapping[str, Floats],
    *,
    trend: Trend,
    declared_false_pair_rate: float,
    q: float = 0.05,
    surrogates: int = 1000,
    seed: int,
    autocorrelation_tolerance: float = 0.1,
) -> MonthRelations:
    """Test every pair of monthly series (decision SM12). ``trend`` and
    ``declared_false_pair_rate`` must be stated by the caller before results are seen."""
    names = list(series)
    lengths = {len(series[name]) for name in names}
    if len(lengths) != 1:
        raise ValueError("every series must cover the same months")
    months = lengths.pop()
    if months < MIN_MONTHS:
        raise TooFewMonths(f"{months} months; a month map needs at least {MIN_MONTHS}")
    if not 0 <= declared_false_pair_rate <= 1:
        raise ValueError("declared_false_pair_rate must be a share between 0 and 1")
    clean = {name: detrend(series[name], trend) for name in names}
    nulls, reproduced = {}, {}
    lags = max(1, months // 5)
    for index, name in enumerate(names):
        nulls[name] = iaaft(clean[name], surrogates, seed=seed + index)
        real = autocorrelation(clean[name], lags)
        mean_surrogate = np.mean([autocorrelation(s, lags) for s in nulls[name]], axis=0)
        reproduced[name] = bool(np.max(np.abs(real - mean_surrogate)) <= autocorrelation_tolerance)
    raw = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            r = _pearson(clean[a], clean[b])
            null = np.concatenate(
                [
                    [_pearson(s, clean[b]) for s in nulls[a]],
                    [_pearson(clean[a], s) for s in nulls[b]],
                ]
            )
            p = (1 + int((np.abs(null) >= abs(r)).sum())) / (1 + null.size)
            raw.append((a, b, r, p, effective_months(clean[a], clean[b])))
    accepted, adjusted = benjamini_yekutieli(np.array([row[3] for row in raw]), q)
    pairs = tuple(
        MonthPair(a, b, r, p, float(adj), round(n_eff, 1), months, bool(ok))
        for (a, b, r, p, n_eff), adj, ok in zip(raw, adjusted, accepted, strict=True)
    )
    if any(math.isnan(pair.r) for pair in pairs):
        raise ValueError("a relation is undefined")
    return MonthRelations(pairs, trend, q, surrogates, declared_false_pair_rate, reproduced)
