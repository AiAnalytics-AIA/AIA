"""Object metrics and height normalisation, moved out of the browser.

In the reference these are frontend functions in ``ui_app.html``:
``objectMetricArray66`` (fixture F6) and ``normalizer66`` (fixture F5). They are
research computation -- the default object height is a classic T-score, and the
normaliser decides what "high" means on the map -- so they live here, where they
can be tested, and the client renders what they return.

Two deliberate departures from the reference, both fail-closed:

* **An unknown metric id is refused.** ``objectMetricArray66`` silently returns
  the T-score for any id it does not recognise, so a typo renders a plausible
  map of the wrong quantity. Here the T-score has its own id,
  :attr:`ObjectMetric.RELATION_CLASSIC_TSCORE`, and anything else is an error.
* **An unknown normalisation mode is refused.** ``normalizer66`` falls through
  to ``range``; here the mode is a :class:`NormalizationMode`.

Standard deviations use the **population** divisor (``/ n``), as the reference
does in both functions.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "METRIC_BOUNDS",
    "NORMALIZATION_LABELS_CS",
    "TSCORE_ZERO_VARIANCE",
    "ZERO_VARIANCE_EPSILON",
    "NormalizationMode",
    "Normalizer",
    "ObjectMetric",
    "UnknownMetricBounds",
    "bounds_for",
    "build_normalizer",
    "object_metric",
    "object_rating_summaries",
    "population_mean_sd",
    "relation_classic",
    "tscore",
]

# Below this standard deviation the reference treats a distribution as constant
# (T-score 50, sigma-normalised 0.5).
ZERO_VARIANCE_EPSILON = 1e-9
TSCORE_ZERO_VARIANCE = 50.0


class ObjectMetric(StrEnum):
    """Per-object quantities that can drive object-map height or colour."""

    MEAN_RATING = "mean_rating"
    SUPPORT_N = "support_n"
    RELATION_CLASSIC = "relation_classic"
    RELATION_CLASSIC_TSCORE = "relation_classic_tscore"


class NormalizationMode(StrEnum):
    """The four ``normalizer66`` modes."""

    RANGE = "range"
    ABSOLUTE = "absolute"
    SIGMA = "sigma"
    PERCENTILE = "percentile"


# Display labels the reference attaches to each mode. Presentation only; kept
# here so the client and the parity test read one definition.
NORMALIZATION_LABELS_CS: Mapping[str, str] = {
    NormalizationMode.RANGE: "rozsah",
    NormalizationMode.ABSOLUTE: "absolutní",
    NormalizationMode.SIGMA: "odchylka \u03c3",  # Greek sigma, escaped for RUF001
    NormalizationMode.PERCENTILE: "percentil",
    "empty": "bez dat",
}

# Metric bounds as recovered from the reference's ``metricDef66``. A metric
# mapped to ``None`` was recovered as *having no bounds*; a metric absent from
# this map has bounds that were **not recovered**, and absolute normalisation of
# it is refused rather than run against guessed bounds.
#   density      -> None      F7 height_def.bounds
#   mean_rating  -> (1, 10)   F8 height_def.bounds
METRIC_BOUNDS: Mapping[str, tuple[float, float] | None] = {
    "density": None,
    ObjectMetric.MEAN_RATING: (1.0, 10.0),
}


class UnknownMetricBounds(ValueError):
    """Absolute normalisation was requested for a metric whose bounds are unrecovered."""


def population_mean_sd(values: Sequence[float]) -> tuple[float, float]:
    """Mean and population standard deviation (divisor ``n``) of a non-empty sequence."""
    if not values:
        raise ValueError("mean and standard deviation need at least one value")
    n = len(values)
    mean = math.fsum(values) / n
    variance = math.fsum((v - mean) ** 2 for v in values) / n
    return mean, math.sqrt(variance)


@dataclass(frozen=True, slots=True)
class Normalizer:
    """A fitted ``normalizer66``: maps a raw value to ``[0, 1]`` display height.

    ``lo`` / ``hi`` are the range the reference *reports* for the legend, which
    is not always the range the transform uses (``sigma`` reports mean +- 2.5 sd,
    ``percentile`` reports 0-100). ``empty`` is true when there were no values;
    the transform is then the constant 0.
    """

    mode: NormalizationMode
    lo: float
    hi: float
    empty: bool
    _transform: Callable[[float], float]

    def __call__(self, value: float) -> float:
        """Normalised height of ``value``."""
        return self._transform(value)

    @property
    def label_cs(self) -> str:
        """The reference's legend label for this normaliser."""
        return NORMALIZATION_LABELS_CS["empty" if self.empty else self.mode]


def _clamp01(v: float) -> float:
    return min(max(v, 0.0), 1.0)


def build_normalizer(
    values: Sequence[float | None],
    mode: NormalizationMode,
    bounds: tuple[float, float] | None,
) -> Normalizer:
    """Fit ``normalizer66(values, mode, bounds)`` (F5).

    ``values`` are the raw heights the normaliser is fitted to; missing entries
    are ignored. ``bounds`` is used by ``absolute`` mode only, and must be the
    metric's recovered bounds -- see :data:`METRIC_BOUNDS`.
    """
    mode = NormalizationMode(mode)
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return Normalizer(mode, 0.0, 1.0, True, lambda _x: 0.0)
    lo, hi = min(xs), max(xs)

    if mode is NormalizationMode.ABSOLUTE:
        if bounds is not None:
            a, b = float(bounds[0]), float(bounds[1])
            if not b > a:
                raise ValueError(f"absolute bounds must satisfy lo < hi; got {bounds!r}")
            return Normalizer(mode, a, b, False, lambda x: _clamp01((x - a) / (b - a)))
        top = max(abs(lo), abs(hi), 1.0)
        return Normalizer(mode, 0.0, top, False, lambda x: _clamp01(x / top))

    if mode is NormalizationMode.SIGMA:
        mean, sd = population_mean_sd(xs)
        if sd < ZERO_VARIANCE_EPSILON:
            return Normalizer(mode, mean - 2.5 * sd, mean + 2.5 * sd, False, lambda _x: 0.5)
        return Normalizer(
            mode,
            mean - 2.5 * sd,
            mean + 2.5 * sd,
            False,
            lambda x: _clamp01(0.5 + ((x - mean) / sd) / 5.0),
        )

    if mode is NormalizationMode.PERCENTILE:
        ordered = sorted(xs)
        n = len(ordered)
        # Upper-bound rank: the share of values <= x (F5: 1 -> 1/8, 21 -> 8/8).
        return Normalizer(mode, 0.0, 100.0, False, lambda x: bisect.bisect_right(ordered, x) / n)

    if hi == lo:
        return Normalizer(mode, lo, hi, False, lambda _x: 0.5)
    return Normalizer(mode, lo, hi, False, lambda x: _clamp01((x - lo) / (hi - lo)))


def bounds_for(metric_id: str, mode: NormalizationMode) -> tuple[float, float] | None:
    """The bounds ``build_normalizer`` should use for ``metric_id`` under ``mode``.

    Only ``absolute`` mode consults bounds. For it, a metric whose bounds were not
    recovered raises :class:`UnknownMetricBounds`.
    """
    if NormalizationMode(mode) is not NormalizationMode.ABSOLUTE:
        return None
    if metric_id not in METRIC_BOUNDS:
        raise UnknownMetricBounds(
            f"bounds for metric {metric_id!r} were not recovered from the reference; "
            "absolute normalisation of it is refused rather than run on guessed bounds"
        )
    return METRIC_BOUNDS[metric_id]


def relation_classic(matrix: Sequence[Sequence[float]]) -> tuple[float, ...]:
    """``relation_classic[i] = sum_j (M[i][j] + M[j][i])`` -- symmetric relation strength (F6).

    Summed over every ``j`` including ``i``; the diagonal is zero after coercion.
    """
    n = len(matrix)
    if any(len(row) != n for row in matrix):
        raise ValueError("relation matrix must be square")
    return tuple(
        math.fsum(float(matrix[i][j]) + float(matrix[j][i]) for j in range(n)) for i in range(n)
    )


def tscore(values: Sequence[float]) -> tuple[float, ...]:
    """Classic T-score ``50 + 10 (v - mean) / sd``, population sd; all 50 when constant (F6)."""
    mean, sd = population_mean_sd(list(values))
    if sd < ZERO_VARIANCE_EPSILON:
        return tuple(TSCORE_ZERO_VARIANCE for _ in values)
    return tuple(50.0 + 10.0 * (v - mean) / sd for v in values)


def object_rating_summaries(
    ratings: Sequence[Sequence[float | None]],
) -> tuple[tuple[float | None, ...], tuple[float, ...]]:
    """Per-object ``(mean_rating, support_n)`` from a respondents x objects matrix.

    ``mean_rating`` is the arithmetic mean of the observed raw ratings, ``None``
    when nobody rated the object; ``support_n`` is the number of observed
    ratings. The reference's frontend receives both precomputed (F6); this is
    the backend derivation, stated here because it is an AIA declaration rather
    than a recovered function.
    """
    if not ratings:
        raise ValueError("ratings must have at least one respondent")
    m = len(ratings[0])
    if any(len(row) != m for row in ratings):
        raise ValueError("every respondent row must rate the same objects")
    means: list[float | None] = []
    support: list[float] = []
    for j in range(m):
        observed = [float(v) for v in (row[j] for row in ratings) if v is not None]
        support.append(float(len(observed)))
        means.append(math.fsum(observed) / len(observed) if observed else None)
    return tuple(means), tuple(support)


def object_metric(
    metric: ObjectMetric | str,
    *,
    mean_rating: Sequence[float | None] | None = None,
    support_n: Sequence[float] | None = None,
    relation: Sequence[Sequence[float]] | None = None,
) -> tuple[float | None, ...]:
    """``objectMetricArray66(id)``, with unknown ids refused (F6).

    Raises ``ValueError`` for an unrecognised id -- the reference's silent
    T-score fall-through -- and when the input the metric needs was not given.
    """
    try:
        chosen = ObjectMetric(metric)
    except ValueError:
        raise ValueError(
            f"unknown object metric {metric!r}; the reference silently rendered the "
            "T-score for unknown ids, which production refuses"
        ) from None
    if chosen is ObjectMetric.MEAN_RATING:
        if mean_rating is None:
            raise ValueError("mean_rating needs per-object mean ratings")
        return tuple(None if v is None else float(v) for v in mean_rating)
    if chosen is ObjectMetric.SUPPORT_N:
        if support_n is None:
            raise ValueError("support_n needs per-object support counts")
        return tuple(float(v) for v in support_n)
    if relation is None:
        raise ValueError(f"{chosen.value} needs the object relation matrix")
    classic = relation_classic(relation)
    if chosen is ObjectMetric.RELATION_CLASSIC:
        return classic
    return tscore(classic)
