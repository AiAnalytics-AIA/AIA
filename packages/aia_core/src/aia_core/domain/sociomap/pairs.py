"""Each object pair's correlation, and what it can be said to be (audit F3).

Moved here unchanged from ``research_sociomap`` (plan ``sociomap-formula-corrections``
§ 8.2, S2) so the v2 engine (:mod:`.engine_v2`) can compute pair relations without
importing outside the Sociomap package; ``research_sociomap`` re-exports every name.

:func:`derive_relation_matrix` is the unit's own formula (``sociomap.py``), kept EXACT for
``aia-sociomap-1``; :func:`derive_pair_relations` is the audit's reading of the same
correlation: signed, unmapped, with its rater count, interval and status.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from .relations import PairStatus, fisher_interval, pair_status

__all__ = ["Interval", "PairRelations", "derive_pair_relations", "derive_relation_matrix"]


_Triples = list[tuple[float, float, float]]


def _columns(ratings: Sequence[Sequence[float | None]]) -> list[list[float]]:
    """Object columns, an unrated cell as NaN (the unit's ``pd.to_numeric`` reading)."""
    m = len(ratings[0]) if ratings else 0
    cols: list[list[float]] = [[] for _ in range(m)]
    for row in ratings:
        for j in range(m):
            value = row[j]
            cols[j].append(math.nan if value is None else float(value))
    return cols


def _common(a: Sequence[float], b: Sequence[float], w: Sequence[float]) -> _Triples:
    """The respondents who rated both objects with a positive finite weight."""
    return [
        (x, y, ww)
        for x, y, ww in zip(a, b, w, strict=True)
        if math.isfinite(x) and math.isfinite(y) and math.isfinite(ww) and ww > 0
    ]


def _weighted_moments(ok: _Triples) -> tuple[float, float, float]:
    """Weighted variances of both columns and their covariance, as the unit computes them."""
    sw = sum(ww for _, _, ww in ok) or 1.0
    ma = sum(ww * a for a, _, ww in ok) / sw
    mb = sum(ww * b for _, b, ww in ok) / sw
    va = sum(ww * (a - ma) ** 2 for a, _, ww in ok) / sw
    vb = sum(ww * (b - mb) ** 2 for _, b, ww in ok) / sw
    cov = sum(ww * (a - ma) * (b - mb) for a, b, ww in ok) / sw
    return va, vb, cov


def _clamped_correlation(va: float, vb: float, cov: float) -> float:
    # ``** 0.5``, not ``math.sqrt``: the unit's operation, kept for EXACT parity;
    # typeshed types float ** float as Any, so the result is narrowed here.
    spread: float = (va * vb) ** 0.5
    corr = cov / max(spread, 1e-12)
    return max(-1.0, min(1.0, corr))


def derive_relation_matrix(
    ratings: Sequence[Sequence[float | None]], weights: Sequence[float]
) -> tuple[list[list[float]], list[float | None]]:
    """``sociomap.py`` ``derive_relation_matrix``: relations and scores from ratings.

    ``ratings[r][j]`` is respondent ``r``'s rating of object ``j`` (``None`` unrated).
    Returns the symmetric 1-10 relation matrix with a zero diagonal, and each
    object's weighted mean rating (``None`` where nobody rated it).

    This is the unit's formula, kept EXACT for ``aia-sociomap-1``: fewer than
    five common ratings is stamped 5.5 and a constant column reads as r = 0,
    both drawn as a medium relation (audit F3, F4). Read
    :func:`derive_pair_relations` for what each cell can be said to be.
    """
    cols = _columns(ratings)
    m = len(cols)
    w = [x if math.isfinite(x) else 1.0 for x in weights]

    scores: list[float | None] = []
    for j in range(m):
        pairs = [(x, ww) for x, ww in zip(cols[j], w, strict=True) if math.isfinite(x) and ww > 0]
        scores.append(
            sum(x * ww for x, ww in pairs) / sum(ww for _, ww in pairs) if pairs else None
        )

    relation = [[0.0] * m for _ in range(m)]
    for i in range(m):
        for j in range(i + 1, m):
            ok = _common(cols[i], cols[j], w)
            if len(ok) < 5:
                rel = 5.5
            else:
                corr = _clamped_correlation(*_weighted_moments(ok))
                rel = 1.0 + 9.0 * ((corr + 1.0) / 2.0)
            relation[i][j] = relation[j][i] = float(min(10.0, max(1.0, rel)))
    return relation, scores


Interval = tuple[float, float]


class PairRelations(BaseModel):
    """Every object pair's correlation and what it can be said to be (audit F3).

    Square matrices over the battery's objects, in order. The diagonal is not a
    pair and is ``None`` in every matrix. ``r`` is the signed weighted Pearson
    correlation over the respondents who rated both objects, or ``None`` where
    there is none to compute; ``n`` counts those respondents; ``interval`` is the
    Fisher-z interval at ``confidence`` (``None`` below four raters); ``status``
    is :func:`~.sociomap.relations.pair_status` at ``n_min``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    r: tuple[tuple[float | None, ...], ...]
    n: tuple[tuple[int | None, ...], ...]
    interval: tuple[tuple[Interval | None, ...], ...]
    status: tuple[tuple[PairStatus | None, ...], ...]
    n_min: int
    confidence: float

    @model_validator(mode="after")
    def _square_and_pairwise(self) -> Self:
        m = len(self.r)
        for name in ("r", "n", "interval", "status"):
            matrix = getattr(self, name)
            if len(matrix) != m or any(len(row) != m for row in matrix):
                raise ValueError(f"{name} must be a {m} x {m} matrix like r")
            if any(matrix[i][i] is not None for i in range(m)):
                raise ValueError(f"{name}: the diagonal is not a pair and must be None")
        return self

    def counts(self) -> dict[str, int]:
        """How many unordered pairs carry each status."""
        out = dict.fromkeys((s.value for s in PairStatus), 0)
        m = len(self.status)
        for i in range(m):
            for j in range(i + 1, m):
                status = self.status[i][j]
                if status is not None:
                    out[status.value] += 1
        return out


def derive_pair_relations(
    ratings: Sequence[Sequence[float | None]],
    weights: Sequence[float],
    *,
    n_min: int,
    confidence: float,
) -> PairRelations:
    """Each pair's signed weighted correlation, its rater count, interval and status.

    The audit's reading of the unit's relation matrix (F3, and the data side of
    F4): the same weighted Pearson correlation, signed and unmapped, with the
    number of respondents who rated both objects and the status that number
    gives it. Nothing is stamped: a pair with fewer than two common raters or a
    constant column has no correlation (``None``), and a pair below ``n_min`` is
    ``UNKNOWN`` whatever its number says. The 1-10 mapping and the 5.5 sentinel
    stay in :func:`derive_relation_matrix`, the unit's own formula.

    ``weights`` weight the correlation as the unit's ``vaha`` does; a respondent
    whose weight is not a positive finite number rates no pair here (the unit
    substituted 1.0 for a non-finite weight, a stamp this variant drops). ``n``
    counts respondents, not weight: the interval reads it as the sample size with
    no correction for unequal weights, which makes it somewhat optimistic under a
    weighted design -- recorded for the audit's author with the plan's open
    points. Scaling each person's ratings before the correlation (F2) is chunk
    2a's and is applied to ``ratings`` before this call.
    """
    cols = _columns(ratings)
    m = len(cols)
    w = [float(x) for x in weights]
    r: list[list[float | None]] = [[None] * m for _ in range(m)]
    n: list[list[int | None]] = [[None] * m for _ in range(m)]
    interval: list[list[Interval | None]] = [[None] * m for _ in range(m)]
    status: list[list[PairStatus | None]] = [[None] * m for _ in range(m)]
    for i in range(m):
        for j in range(i + 1, m):
            ok = _common(cols[i], cols[j], w)
            corr: float | None = None
            # Constancy is read from the values, not the variance: weighted
            # arithmetic over equal values can leave a variance of 1e-32, and
            # 0 / 1e-12 would then report "no relation" where there is no data.
            if len({a for a, _, _ in ok}) > 1 and len({b for _, b, _ in ok}) > 1:
                corr = _clamped_correlation(*_weighted_moments(ok))
            r[i][j] = r[j][i] = corr
            n[i][j] = n[j][i] = len(ok)
            interval[i][j] = interval[j][i] = (
                None if corr is None else fisher_interval(corr, len(ok), confidence)
            )
            status[i][j] = status[j][i] = pair_status(corr, len(ok), n_min, confidence)
    return PairRelations(
        r=tuple(tuple(row) for row in r),
        n=tuple(tuple(row) for row in n),
        interval=tuple(tuple(row) for row in interval),
        status=tuple(tuple(row) for row in status),
        n_min=n_min,
        confidence=confidence,
    )
