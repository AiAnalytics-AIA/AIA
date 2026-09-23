"""Relation-matrix and ratings transforms that feed Sociomapping positions.

Ported from the reference backend (``sociomap.py``, ``study_validation.py``)
against golden fixtures F1-F3. Pure Python on purpose: the arithmetic is a fixed
sequence of IEEE-754 operations, so it gives the same bits on every host, which
is the property the reference's environment-dependent layout lacked.

The three steps and where each sits in the reference pipeline::

    ratings (respondents x objects)
      -> ipsatize()                          within-person centring          F3
    relation matrix (objects x objects, directed, any legacy scale)
      -> coerce_relation_scale_1_10()        scale harmonisation, directed   F1
      -> mutual_relation_for_position()      direction collapsed for 2-D     F2

Direction is preserved by coercion and collapsed only by the position
projection: the directed matrix stays visible for metrics and display.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum

__all__ = [
    "MIN_RELATION_OBJECTS",
    "AmbiguousCoercion",
    "CoercionBranch",
    "RelationScaleError",
    "coerce_relation_scale_1_10",
    "coercion_branch",
    "ipsatize",
    "mutual_relation_for_position",
]

# ``_coerce_relation_scale_1_10`` refuses fewer than three objects.
MIN_RELATION_OBJECTS = 3

# Sentinel substitutions recovered from the reference (F1). NaN is mapped to the
# scale midpoint -- which scores *unknown* as *neutral* (ARCHITECTURE.md A4). It
# is kept only for parity on raw legacy matrices; production inputs carry missing
# cells as ``None`` and the spec's missing-data policy decides, see engine.py.
_NAN_SENTINEL = 5.5
_POS_INF_SENTINEL = 10.0
_NEG_INF_SENTINEL = 1.0

Matrix = tuple[tuple[float, ...], ...]


class RelationScaleError(ValueError):
    """The matrix violates a precondition of scale coercion (shape or size)."""


class AmbiguousCoercion(RelationScaleError):
    """The reference's behaviour for this input was not recovered.

    The contract lists the sentinel substitutions and the scale branches but not
    their order. On every fixture both orders agree; on a matrix whose *finite*
    off-diagonal cells select one branch while the substituted sentinels select
    another, they do not. Rather than guess which the reference did, refuse.
    """


class CoercionBranch(StrEnum):
    """Which scale the off-diagonal cells were recognised as."""

    SIMILARITY_0_1 = "similarity_0_1"
    CORRELATION_PM1 = "correlation_pm1"
    CLIP_1_10 = "clip_1_10"


def _square(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    rows = [[float(v) for v in row] for row in matrix]
    n = len(rows)
    if any(len(row) != n for row in rows):
        raise RelationScaleError("relation matrix must be square")
    if n < MIN_RELATION_OBJECTS:
        raise RelationScaleError(
            f"relation matrix needs at least {MIN_RELATION_OBJECTS} objects; got {n}"
        )
    return rows


def _substitute(value: float) -> float:
    if math.isnan(value):
        return _NAN_SENTINEL
    if value == math.inf:
        return _POS_INF_SENTINEL
    if value == -math.inf:
        return _NEG_INF_SENTINEL
    return value


def _branch(values: Sequence[float]) -> CoercionBranch:
    if all(0.0 <= v <= 1.0 for v in values):
        return CoercionBranch.SIMILARITY_0_1
    if all(-1.0 <= v <= 1.0 for v in values):
        return CoercionBranch.CORRELATION_PM1
    return CoercionBranch.CLIP_1_10


def _off_diagonal(rows: Sequence[Sequence[float]]) -> list[float]:
    return [v for i, row in enumerate(rows) for j, v in enumerate(row) if i != j]


def coercion_branch(matrix: Sequence[Sequence[float]]) -> CoercionBranch:
    """Return the scale branch :func:`coerce_relation_scale_1_10` will apply.

    Exposed so the branch can be recorded in provenance: the same numbers mean
    different things on a similarity, a correlation and a 1-10 scale.
    """
    rows = _square(matrix)
    raw = _off_diagonal(rows)
    substituted = [_substitute(v) for v in raw]
    after = _branch(substituted)
    if any(not math.isfinite(v) for v in raw):
        finite = [v for v in raw if math.isfinite(v)]
        if finite and _branch(finite) is not after:
            raise AmbiguousCoercion(
                "non-finite cells in a matrix whose finite cells look like a "
                f"{_branch(finite).value} scale: the reference's sentinel/branch order "
                "is unrecovered for this case, so it is refused rather than guessed"
            )
    return after


def coerce_relation_scale_1_10(matrix: Sequence[Sequence[float]]) -> Matrix:
    """Harmonise a relation matrix onto the 1-10 scale, keeping direction (F1).

    Rules, from ``sociomap._coerce_relation_scale_1_10``:

    ============================  =====================================
    NaN / +inf / -inf             5.5 / 10.0 / 1.0
    all off-diagonal in [0, 1]    similarity:  ``1 + 9x``
    all off-diagonal in [-1, 1]   correlation: ``1 + 9 * (x + 1) / 2``
    otherwise                     ``clip(x, 1, 10)``
    diagonal                      forced to ``0.0``
    ============================  =====================================

    Raises :class:`RelationScaleError` for a non-square matrix or fewer than
    three objects, and :class:`AmbiguousCoercion` where the reference's order of
    operations was not recovered.
    """
    branch = coercion_branch(matrix)
    rows = [[_substitute(v) for v in row] for row in _square(matrix)]
    out: list[tuple[float, ...]] = []
    for i, row in enumerate(rows):
        coerced: list[float] = []
        for j, v in enumerate(row):
            if i == j:
                coerced.append(0.0)
            elif branch is CoercionBranch.SIMILARITY_0_1:
                coerced.append(1.0 + 9.0 * v)
            elif branch is CoercionBranch.CORRELATION_PM1:
                coerced.append(1.0 + 9.0 * ((v + 1.0) / 2.0))
            else:
                coerced.append(min(max(v, 1.0), 10.0))
        out.append(tuple(coerced))
    return tuple(out)


def mutual_relation_for_position(matrix: Sequence[Sequence[float]]) -> Matrix:
    """Collapse direction for 2-D placement and rescale to ``[0, 1]`` (F2).

    ``raw = coerce(M)``; ``mutual = (raw + rawT) / 2``; off-diagonal
    ``clip((mutual - 1) / 9, 0, 1)``; diagonal ``0``. The arithmetic mean is the
    reference's deliberate choice -- its docstring calls it "the simplest
    auditable projection rule" -- and direction remains visible in the coerced
    matrix, which is kept alongside this one.
    """
    raw = coerce_relation_scale_1_10(matrix)
    n = len(raw)
    out: list[tuple[float, ...]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            if i == j:
                row.append(0.0)
                continue
            mutual = (raw[i][j] + raw[j][i]) / 2.0
            row.append(min(max((mutual - 1.0) / 9.0, 0.0), 1.0))
        out.append(tuple(row))
    return tuple(out)


def ipsatize(
    values: Sequence[Sequence[float | None]],
) -> tuple[tuple[float | None, ...], ...]:
    """Within-person centring: subtract each row's mean over its observed cells (F3).

    Rows are respondents and columns the object ratings only; selecting which
    columns are objects is the study contract's job, not this function's.
    Missing cells (``None``) stay missing and do not enter the mean -- the
    reference's pandas ``mean`` skips NaN the same way. A row with no observed
    cell stays entirely missing: there is no mean to centre on, and inventing
    one would stamp a guess.
    """
    out: list[tuple[float | None, ...]] = []
    for row in values:
        observed = [float(v) for v in row if v is not None]
        if not observed:
            out.append(tuple(None for _ in row))
            continue
        mean = math.fsum(observed) / len(observed)
        out.append(tuple(None if v is None else float(v) - mean for v in row))
    return tuple(out)
