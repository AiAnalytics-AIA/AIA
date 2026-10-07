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

The audit *NPC Sociomapa: faulty formulas in the code* (F8) replaces the
classic score: :func:`primary_scores` computes **alignment** and
**connectedness** over the PRIMARY objects, from each pair's signed correlation
and its status (F3), with UNKNOWN pairs left out. The classic score and its
T-score stay, by name, for ``aia-sociomap-1`` (plan
``sociomap-formula-corrections``, chunk 1b).
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .relations import PairStatus

__all__ = [
    "AUDIT_PROVISIONAL_DEFAULT_HEIGHT",
    "METRIC_BOUNDS",
    "NORMALIZATION_LABELS_CS",
    "PRIMARY_SCORE_RULE",
    "TSCORE_ZERO_VARIANCE",
    "ZERO_VARIANCE_EPSILON",
    "NormalizationMode",
    "Normalizer",
    "ObjectMetric",
    "ObjectRole",
    "PrimaryObjectScore",
    "PrimaryScores",
    "UnknownMetricBounds",
    "alignment",
    "bounds_for",
    "build_normalizer",
    "connectedness",
    "object_metric",
    "object_rating_summaries",
    "population_mean_sd",
    "primary_scores",
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


def bounds_for(
    metric_id: str,
    mode: NormalizationMode,
    *,
    rating_scale: tuple[float, float] | None = None,
) -> tuple[float, float] | None:
    """The bounds ``build_normalizer`` should use for ``metric_id`` under ``mode``.

    Only ``absolute`` mode consults bounds. ``mean_rating`` is bounded by the
    rating scale the spec declares, when one is given -- the reference's (1, 10)
    is only that scale's default; a 0-5 study normalised against 1-10 would put a
    perfect mean at 4/9. Any other metric whose bounds were not recovered raises
    :class:`UnknownMetricBounds`.
    """
    if NormalizationMode(mode) is not NormalizationMode.ABSOLUTE:
        return None
    if metric_id == ObjectMetric.MEAN_RATING and rating_scale is not None:
        return (float(rating_scale[0]), float(rating_scale[1]))
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


# ------------------------------------------- alignment and connectedness (F8) --
#
# Audit F8: the classic score sum_j (s_ij + s_ji) over the 1-10 strengths is
# mostly the constant 11 (m - 1), opposite relations cancel in it, a pair nobody
# measured counts as a medium one (5.5), and a context object added to the set
# reshuffles the ranking. Its replacement is two scores over the PRIMARY objects
# only, read from the signed correlation and the pair's status (F3):
#
#     A_i = (1 / k_i) sum_{j in P, j != i, known} r_ij        in [-1, 1]
#     K_i = (1 / k_i) sum_{j in P, j != i, known} |r_ij|      in [0, 1]
#
# The audit writes the denominator as m_P - 1 and leaves UNKNOWN pairs out of
# both sums. With a fixed denominator, leaving a pair out of the sum is scoring
# it 0 -- "not connected" -- which is unknown scored as a value (ARCHITECTURE A4,
# CLAUDE.md § 8). AIA's reading, recorded in the evidence register's AUDIT-F8 and
# put to the audit's author with Q7: k_i counts i's *known* PRIMARY pairs
# (m_P - 1 minus i's UNKNOWN ones), and an object with none is unscored (None).


class ObjectRole(StrEnum):
    """An object's part in the scores (audit F8). AIA has no object manager yet.

    The caller declares every object's role; nothing defaults to PRIMARY, so a
    context object can never enter a PRIMARY score by being left undeclared.
    """

    #: A main object of the family: scored, and the only kind that scores others.
    PRIMARY = "primary"
    #: A context object: drawn for orientation, never in a PRIMARY score.
    SECONDARY = "secondary"


#: The default object height the audit proposes (F8: "mean rating, pending Q7").
#: The audit's provisional value, not AIA's decision: spec contract v3 (chunk 2d)
#: declares it; ``aia-sociomap-1`` keeps the classic T-score.
AUDIT_PROVISIONAL_DEFAULT_HEIGHT: Final = ObjectMetric.MEAN_RATING

#: The rule :func:`primary_scores` applies, recorded on every result.
PRIMARY_SCORE_RULE: Final = "audit-f8-known-primary-pairs-v1"

_PRIMARY_SCORE_RULE_TEXT: Final = (
    "audit F8: alignment = mean signed r, connectedness = mean |r|, over i's PRIMARY "
    "partners whose pair is not UNKNOWN (F3); UNKNOWN pairs are out of the sums and "
    "the denominator; an object with no known pair is unscored; SECONDARY objects "
    "never enter a PRIMARY score. The denominator reading is AIA's, put to the "
    "audit's author with Q7"
)


@dataclass(frozen=True, slots=True)
class PrimaryObjectScore:
    """One PRIMARY object's two scores and what they were computed over.

    ``known_pairs`` is the denominator ``k_i``; ``unknown_partners`` are the
    PRIMARY objects whose pair with this one is UNKNOWN and was left out. Both
    scores are ``None`` when ``known_pairs`` is 0: nothing is known, so nothing
    is scored.
    """

    object_id: str
    alignment: float | None
    connectedness: float | None
    known_pairs: int
    unknown_partners: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrimaryScores:
    """Alignment and connectedness of every PRIMARY object (audit F8).

    ``scores`` follows ``primary``'s order; SECONDARY objects have no entry.
    ``excluded_pairs`` are the unordered PRIMARY pairs left out as UNKNOWN.
    """

    rule: str
    primary: tuple[str, ...]
    secondary: tuple[str, ...]
    scores: tuple[PrimaryObjectScore, ...]
    excluded_pairs: tuple[tuple[str, str], ...]

    def alignment(self) -> dict[str, float | None]:
        """``A_i`` by object id."""
        return {s.object_id: s.alignment for s in self.scores}

    def connectedness(self) -> dict[str, float | None]:
        """``K_i`` by object id."""
        return {s.object_id: s.connectedness for s in self.scores}

    def to_payload(self) -> dict[str, Any]:
        """A JSON-ready body: the scores, their denominators and the rule."""
        return {
            "rule": self.rule,
            "rule_text": _PRIMARY_SCORE_RULE_TEXT,
            "primary": list(self.primary),
            "secondary": list(self.secondary),
            "objects": [
                {
                    "id": s.object_id,
                    "alignment": s.alignment,
                    "connectedness": s.connectedness,
                    "known_pairs": s.known_pairs,
                    "unknown_partners": list(s.unknown_partners),
                }
                for s in self.scores
            ],
            "excluded_pairs": [list(p) for p in self.excluded_pairs],
        }


def _roles(object_ids: Sequence[str], roles: Mapping[str, ObjectRole | str]) -> list[ObjectRole]:
    ids = list(object_ids)
    if len(set(ids)) != len(ids):
        raise ValueError("object ids must be unique")
    unknown = sorted(set(roles) - set(ids))
    if unknown:
        raise ValueError(f"roles name objects the matrix does not have: {unknown!r}")
    undeclared = [oid for oid in ids if oid not in roles]
    if undeclared:
        raise ValueError(
            f"every object's role must be declared; nothing defaults to PRIMARY: {undeclared!r}"
        )
    out: list[ObjectRole] = []
    for oid in ids:
        try:
            out.append(ObjectRole(roles[oid]))
        except ValueError:
            raise ValueError(f"object {oid!r} has an unknown role {roles[oid]!r}") from None
    return out


def _square_of(matrix: Sequence[Sequence[Any]], m: int, name: str) -> None:
    if len(matrix) != m or any(len(row) != m for row in matrix):
        raise ValueError(f"{name} must be a {m} x {m} matrix over the object ids")


def _known_r(value: Any, a: str, b: str) -> float:
    if (
        value is None
        or isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or not -1.0 <= value <= 1.0
    ):
        raise ValueError(
            f"pair ({a!r}, {b!r}) is not UNKNOWN, so its correlation must lie in [-1, 1]; "
            f"got {value!r}"
        )
    return float(value)


def _status(value: Any, a: str, b: str) -> PairStatus:
    if value is None:
        raise ValueError(f"pair ({a!r}, {b!r}) has no status")
    try:
        return PairStatus(value)
    except ValueError:
        raise ValueError(f"pair ({a!r}, {b!r}) has an unknown status {value!r}") from None


def primary_scores(
    object_ids: Sequence[str],
    r: Sequence[Sequence[float | None]],
    status: Sequence[Sequence[PairStatus | str | None]],
    roles: Mapping[str, ObjectRole | str],
) -> PrimaryScores:
    """Alignment ``A_i`` and connectedness ``K_i`` of every PRIMARY object (audit F8).

    ``r`` and ``status`` are square over ``object_ids``: each pair's signed
    correlation and its :class:`~.relations.PairStatus`, as
    ``research_sociomap.derive_pair_relations`` returns them. ``roles`` declares
    every object PRIMARY or SECONDARY; an undeclared or unknown id is refused.

    Only PRIMARY x PRIMARY cells are read. An UNKNOWN pair's number is never
    read; a RELIABLE or WEAK pair must carry a correlation in [-1, 1], and the
    two halves of every PRIMARY pair must agree. SECONDARY rows and columns are
    not read at all, so a context object cannot move a PRIMARY score.
    """
    ids = list(object_ids)
    declared = _roles(ids, roles)
    m = len(ids)
    _square_of(r, m, "r")
    _square_of(status, m, "status")
    primary = [k for k in range(m) if declared[k] is ObjectRole.PRIMARY]

    known: dict[tuple[int, int], float] = {}
    excluded: list[tuple[str, str]] = []
    for x, i in enumerate(primary):
        for j in primary[x + 1 :]:
            a, b = ids[i], ids[j]
            pair = _status(status[i][j], a, b)
            if pair is not _status(status[j][i], b, a):
                raise ValueError(f"pair ({a!r}, {b!r}) has two statuses")
            if pair is PairStatus.UNKNOWN:
                excluded.append((a, b))
                continue
            value = _known_r(r[i][j], a, b)
            if _known_r(r[j][i], b, a) != value:
                raise ValueError(f"pair ({a!r}, {b!r}) has two correlations")
            known[(i, j)] = known[(j, i)] = value

    scores: list[PrimaryObjectScore] = []
    for i in primary:
        values = [known[(i, j)] for j in primary if j != i and (i, j) in known]
        k = len(values)
        scores.append(
            PrimaryObjectScore(
                object_id=ids[i],
                alignment=math.fsum(values) / k if k else None,
                connectedness=math.fsum(abs(v) for v in values) / k if k else None,
                known_pairs=k,
                unknown_partners=tuple(ids[j] for j in primary if j != i and (i, j) not in known),
            )
        )
    return PrimaryScores(
        rule=PRIMARY_SCORE_RULE,
        primary=tuple(ids[k] for k in primary),
        secondary=tuple(ids[k] for k in range(m) if declared[k] is ObjectRole.SECONDARY),
        scores=tuple(scores),
        excluded_pairs=tuple(excluded),
    )


def alignment(
    object_ids: Sequence[str],
    r: Sequence[Sequence[float | None]],
    status: Sequence[Sequence[PairStatus | str | None]],
    roles: Mapping[str, ObjectRole | str],
) -> dict[str, float | None]:
    """``A_i`` of every PRIMARY object, ``None`` where it has no known pair (audit F8)."""
    return primary_scores(object_ids, r, status, roles).alignment()


def connectedness(
    object_ids: Sequence[str],
    r: Sequence[Sequence[float | None]],
    status: Sequence[Sequence[PairStatus | str | None]],
    roles: Mapping[str, ObjectRole | str],
) -> dict[str, float | None]:
    """``K_i`` of every PRIMARY object, ``None`` where it has no known pair (audit F8)."""
    return primary_scores(object_ids, r, status, roles).connectedness()
