"""Deterministic numerical primitives for the simulation core. Pure Python.

The domain layer is stdlib + Pydantic only, so there is no numpy here. The
matrices involved are at most 12 x 12 (one row and column per factor), for which
a cyclic Jacobi eigensolver is exact enough and fast enough.

**Reproducibility.** Every operation here is built from IEEE-754 arithmetic,
``math.sqrt`` (correctly rounded) and, for the normal quantile and the logistic
transform, ``math.log``/``math.exp``. The first two are bit-reproducible across
platforms; the last two are reproducible to well inside the 1e-9 tolerance the
parity plan sets for ``simulation.engine``.

**Randomness** is counter-based: a draw is a SHA-256 of ``(seed, *keys)`` mapped
to a uniform and then through the normal quantile. There is no generator state,
so a respondent's draws depend on the world seed and the respondent's id -- not
on how many rows came before it, not on row order, and not on whether the
population was subset. The reference used ``numpy.random.default_rng``; the
difference is recorded in ``docs/architecture/simulation-deterministic-engine.md``.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Final

__all__ = [
    "NEAREST_CORRELATION_ALGORITHM",
    "RNG_ALGORITHM",
    "SD_DEGENERATE_THRESHOLD",
    "CorrelationFactor",
    "Matrix",
    "NearestCorrelation",
    "NotPositiveDefinite",
    "clip",
    "correlation_factor",
    "logit",
    "nearest_correlation",
    "sigmoid",
    "standard_normal",
    "symmetric_eigen",
    "uniform_open",
    "weighted_correlation",
    "weighted_mean",
    "weighted_sd",
]

Matrix = tuple[tuple[float, ...], ...]

RNG_ALGORITHM: Final = "sha256-counter-inv-normal-v1"
NEAREST_CORRELATION_ALGORITHM: Final = "higham2002-dykstra-v1"

# The reference treats a standard deviation at or below this as zero
# (full_simulation.py:111 in the reference archive, via methodology-candidates).
SD_DEGENERATE_THRESHOLD: Final = 1e-9

_STANDARD_NORMAL = NormalDist(0.0, 1.0)
_TWO_POW_53 = float(2**53)


class NotPositiveDefinite(ValueError):
    """Raised when a matrix cannot be made a valid correlation matrix."""


def clip(x: float, lo: float, hi: float) -> float:
    if lo > hi:
        raise ValueError(f"clip bounds are inverted: {lo} > {hi}")
    return lo if x < lo else hi if x > hi else x


def logit(p: float) -> float:
    """``log(p / (1 - p))`` for ``0 < p < 1``. Out-of-range raises; it never clips."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"logit is defined on (0, 1); got {p}")
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    """Numerically stable logistic function."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


# --- Weighted statistics ------------------------------------------------------


def _check_weights(values: Sequence[float], weights: Sequence[float]) -> float:
    if len(values) != len(weights):
        raise ValueError(f"{len(values)} values but {len(weights)} weights")
    total = math.fsum(weights)
    if not total > 0.0:
        # Never divide by a zero total and call the result a mean: there is none.
        raise ValueError("weights must sum to a positive total")
    return total


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    total = _check_weights(values, weights)
    return math.fsum(v * w for v, w in zip(values, weights, strict=True)) / total


def weighted_sd(values: Sequence[float], weights: Sequence[float]) -> float:
    """Population (ddof = 0) weighted standard deviation."""
    total = _check_weights(values, weights)
    mean = math.fsum(v * w for v, w in zip(values, weights, strict=True)) / total
    var = math.fsum(w * (v - mean) ** 2 for v, w in zip(values, weights, strict=True)) / total
    return math.sqrt(max(var, 0.0))


def weighted_correlation(
    x: Sequence[float], y: Sequence[float], weights: Sequence[float]
) -> float | None:
    """Weighted Pearson correlation, or ``None`` when either side has no variance.

    ``None`` rather than 0: a constant column has no correlation, and reporting 0
    would claim the two are measured to be unrelated.
    """
    mx, my = weighted_mean(x, weights), weighted_mean(y, weights)
    total = math.fsum(weights)
    cov = math.fsum(w * (a - mx) * (b - my) for a, b, w in zip(x, y, weights, strict=True))
    sx = weighted_sd(x, weights)
    sy = weighted_sd(y, weights)
    if sx <= SD_DEGENERATE_THRESHOLD or sy <= SD_DEGENERATE_THRESHOLD:
        return None
    return clip(cov / total / (sx * sy), -1.0, 1.0)


# --- Linear algebra -------------------------------------------------------------


def _check_square_symmetric(m: Sequence[Sequence[float]], tol: float = 1e-12) -> int:
    n = len(m)
    if n == 0:
        raise ValueError("matrix is empty")
    for i, row in enumerate(m):
        if len(row) != n:
            raise ValueError(f"matrix is not square: row {i} has {len(row)} of {n}")
        for x in row:
            if not math.isfinite(x):
                raise ValueError(f"matrix entries must be finite; got {x!r}")
    for i in range(n):
        for j in range(i + 1, n):
            if abs(m[i][j] - m[j][i]) > tol:
                raise ValueError(f"matrix is not symmetric at ({i}, {j})")
    return n


def symmetric_eigen(
    m: Sequence[Sequence[float]], *, tol: float = 1e-15, max_sweeps: int = 100
) -> tuple[tuple[float, ...], Matrix]:
    """Eigen-decompose a real symmetric matrix by cyclic Jacobi rotations.

    Returns ``(eigenvalues, vectors)`` with eigenvalues ascending and
    ``vectors[i]`` the unit eigenvector for ``eigenvalues[i]``. Each vector's sign
    is fixed so that its largest-magnitude component is positive, which makes the
    output a function of the input rather than of rotation order.

    Uses only ``+ - * /`` and ``sqrt``, so it is bit-reproducible on any IEEE-754
    platform.
    """
    n = _check_square_symmetric(m)
    a = [list(map(float, row)) for row in m]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    scale = max(1.0, max(abs(x) for row in a for x in row))
    for _ in range(max_sweeps):
        off = math.fsum(a[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off <= (tol * scale) ** 2:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                apq = a[p][q]
                if apq == 0.0:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * apq)
                t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    else:
        raise ArithmeticError(f"Jacobi did not converge in {max_sweeps} sweeps")

    pairs = []
    for i in range(n):
        vec = [v[k][i] for k in range(n)]
        pivot = max(range(n), key=lambda k: (abs(vec[k]), -k))
        if vec[pivot] < 0:
            vec = [-x for x in vec]
        pairs.append((a[i][i], tuple(vec)))
    pairs.sort(key=lambda pair: pair[0])
    return tuple(p[0] for p in pairs), tuple(p[1] for p in pairs)


def _recompose(values: Sequence[float], vectors: Matrix) -> list[list[float]]:
    n = len(values)
    return [
        [math.fsum(values[k] * vectors[k][i] * vectors[k][j] for k in range(n)) for j in range(n)]
        for i in range(n)
    ]


def _project_psd(m: Sequence[Sequence[float]]) -> list[list[float]]:
    values, vectors = symmetric_eigen(_symmetrise(m))
    return _recompose([max(x, 0.0) for x in values], vectors)


def _symmetrise(m: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(m)
    return [[(m[i][j] + m[j][i]) / 2.0 for j in range(n)] for i in range(n)]


@dataclass(frozen=True)
class NearestCorrelation:
    matrix: Matrix
    iterations: int
    # Frobenius distance from the proposed matrix: how much the projection moved it.
    adjustment: float


def nearest_correlation(
    proposed: Sequence[Sequence[float]], *, tol: float = 1e-12, max_iter: int = 500
) -> NearestCorrelation:
    """Nearest correlation matrix in the Frobenius norm (Higham 2002, with Dykstra).

    An LLM-proposed set of pairwise correlations need not be jointly feasible.
    This finds the closest matrix that is: symmetric, unit diagonal, positive
    semi-definite. A proposal that is already valid comes back unchanged (to
    within ``tol``), and ``adjustment`` says how far an invalid one was moved --
    the projection is methodology, so its size is reported rather than hidden.

    Fails closed: non-convergence raises instead of returning an approximation.
    """
    n = _check_square_symmetric(proposed)
    for i in range(n):
        if proposed[i][i] != 1.0:
            raise ValueError(f"a correlation proposal has a unit diagonal; [{i}][{i}] is not 1")
    a = [list(map(float, row)) for row in proposed]
    y = [row[:] for row in a]
    ds = [[0.0] * n for _ in range(n)]
    iterations = 0
    for _ in range(max_iter):
        iterations += 1
        r = [[y[i][j] - ds[i][j] for j in range(n)] for i in range(n)]
        x = _project_psd(r)
        ds = [[x[i][j] - r[i][j] for j in range(n)] for i in range(n)]
        y_next = [[1.0 if i == j else x[i][j] for j in range(n)] for i in range(n)]
        change = math.sqrt(
            math.fsum((y_next[i][j] - y[i][j]) ** 2 for i in range(n) for j in range(n))
        )
        norm = math.sqrt(math.fsum(y_next[i][j] ** 2 for i in range(n) for j in range(n)))
        y = y_next
        if change <= tol * max(norm, 1.0):
            break
    else:
        raise NotPositiveDefinite(f"nearest correlation did not converge in {max_iter} iterations")
    y = _symmetrise(y)
    adjustment = math.sqrt(math.fsum((y[i][j] - a[i][j]) ** 2 for i in range(n) for j in range(n)))
    return NearestCorrelation(tuple(tuple(row) for row in y), iterations, adjustment)


@dataclass(frozen=True)
class CorrelationFactor:
    """A correlation matrix together with a factor ``F`` such that ``F Fᵀ`` is it.

    ``factor`` rows are unit vectors, so the implied matrix has an exact unit
    diagonal and is positive semi-definite by construction -- which is what
    correlated sampling needs, and what a Cholesky decomposition would refuse on a
    singular matrix.
    """

    proposed: Matrix
    matrix: Matrix
    factor: Matrix
    iterations: int
    adjustment: float
    min_eigenvalue: float
    algorithm: str = NEAREST_CORRELATION_ALGORITHM


def correlation_factor(proposed: Sequence[Sequence[float]]) -> CorrelationFactor:
    """Project ``proposed`` to the nearest correlation matrix and factor it."""
    nearest = nearest_correlation(proposed)
    values, vectors = symmetric_eigen(nearest.matrix)
    n = len(values)
    clipped = [max(x, 0.0) for x in values]
    rows = [[vectors[k][i] * math.sqrt(clipped[k]) for k in range(n)] for i in range(n)]
    for i, row in enumerate(rows):
        norm = math.sqrt(math.fsum(x * x for x in row))
        if norm <= 0.0:
            raise NotPositiveDefinite(f"factor {i} has no variance after projection")
        rows[i] = [x / norm for x in row]
    implied = tuple(
        tuple(
            1.0 if i == j else math.fsum(rows[i][k] * rows[j][k] for k in range(n))
            for j in range(n)
        )
        for i in range(n)
    )
    return CorrelationFactor(
        proposed=tuple(tuple(map(float, row)) for row in proposed),
        matrix=implied,
        factor=tuple(tuple(row) for row in rows),
        iterations=nearest.iterations,
        adjustment=nearest.adjustment,
        min_eigenvalue=values[0],
    )


# --- Counter-based randomness ------------------------------------------------------


def uniform_open(seed: int, *keys: str | int) -> float:
    """A deterministic uniform draw on the open interval (0, 1).

    SHA-256 over ``RNG_ALGORITHM|seed|key...``; the top 53 bits give the mantissa,
    offset by half a step so neither 0 nor 1 can occur (the normal quantile is
    infinite at both).
    """
    payload = "|".join([RNG_ALGORITHM, str(int(seed)), *(str(k) for k in keys)])
    word = int.from_bytes(hashlib.sha256(payload.encode("utf-8")).digest()[:8], "big")
    return ((word >> 11) + 0.5) / _TWO_POW_53


def standard_normal(seed: int, *keys: str | int) -> float:
    """A deterministic standard normal draw for ``(seed, *keys)``."""
    return _STANDARD_NORMAL.inv_cdf(uniform_open(seed, *keys))
