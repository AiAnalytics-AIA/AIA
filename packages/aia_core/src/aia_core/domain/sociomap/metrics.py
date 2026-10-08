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
``sociomap-formula-corrections``, chunk 1b). Its F9 replaces the normative
score: :func:`connectedness_100` puts connectedness on 0-100 with a respondent-
bootstrap interval, and :func:`rank_with_ties` orders objects only where those
intervals do not overlap (chunk 4a).
"""

from __future__ import annotations

import bisect
import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .relations import PairStatus

__all__ = [
    "AUDIT_PROVISIONAL_DEFAULT_HEIGHT",
    "CONNECTEDNESS_100_RULE",
    "CONNECTEDNESS_BOOTSTRAP_GENERATOR",
    "CONNECTEDNESS_QUANTILES",
    "METRIC_BOUNDS",
    "NORMALIZATION_LABELS_CS",
    "PRIMARY_SCORE_RULE",
    "RANK_WITH_TIES_RULE",
    "TSCORE_ZERO_VARIANCE",
    "ZERO_VARIANCE_EPSILON",
    "Connectedness100",
    "ConnectednessInterval",
    "NormalizationMode",
    "Normalizer",
    "ObjectMetric",
    "ObjectRole",
    "PairCorrelator",
    "PrimaryObjectScore",
    "PrimaryScores",
    "RankRelation",
    "RankedObject",
    "TiedRanking",
    "UnknownMetricBounds",
    "alignment",
    "bounds_for",
    "build_normalizer",
    "connectedness",
    "connectedness_100",
    "linear_quantile",
    "object_metric",
    "object_rating_summaries",
    "population_mean_sd",
    "primary_scores",
    "rank_with_ties",
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


# --------------------------- connectedness 0-100 with its interval (F9) --
#
# Audit F9: the normative score 50 + 10 z always makes winners and losers,
# whatever the data. Its replacement is connectedness on a fixed scale with a
# margin of error, and an order only where the margins say so:
#
#     K100_i = 100 K_i
#     [K_lo_i, K_hi_i] = 2.5 % / 97.5 % quantiles of K100_i over B respondent
#                        bootstraps (clusters = respondents)
#     rank i above j only if their intervals do not overlap; otherwise tied
#
# Readings AIA takes where the audit is silent, recorded on every result and in
# the evidence register's AUDIT-F9:
#
# * **Pair status is fixed from the full sample.** K_i is a mean over i's known
#   PRIMARY pairs (F8); the bootstrap measures how that statistic varies, so the
#   set of pairs it averages is the full sample's in every resample. A pair the
#   full sample calls UNKNOWN stays out; a resample's own count never
#   reclassifies one, and a resample's statuses are not read.
# * **A resample that cannot compute one of i's pairs does not score i.** Where a
#   full-sample known pair has no correlation in a resample (a column constant
#   there, or nobody drawn who rated both), K_i over fewer pairs would be another
#   statistic, and 0 would be unknown scored as a value (CLAUDE.md § 8). That
#   resample is left out of i's interval, and each object records how many
#   resamples scored it.
# * **The generator and the quantile are aggregation's** (OI-62):
#   ``random.Random(seed).random()``, respondent index ``floor(u * n)``, and the
#   linear quantile ``np.quantile`` uses by default (type 7), the rule
#   ``research_aggregate`` applies to its intervals. Every respondent of the
#   sample is a cluster, including one who rated nothing in the family: the
#   resample has the sample's size and composition, so its rater counts vary.

#: The rule :func:`connectedness_100` applies, recorded on every result.
CONNECTEDNESS_100_RULE: Final = "audit-f9-connectedness-100-respondent-bootstrap-v1"
#: OI-62's generator, named as ``research_aggregate.BOOTSTRAP_GENERATOR`` names it.
CONNECTEDNESS_BOOTSTRAP_GENERATOR: Final = "python-random-mt19937:floor(u*m)"
#: The audit's interval: the 2.5 % and 97.5 % quantiles.
CONNECTEDNESS_QUANTILES: Final = (0.025, 0.975)
#: The rule :func:`rank_with_ties` applies, recorded on every ranking.
RANK_WITH_TIES_RULE: Final = "audit-f9-rank-where-intervals-do-not-overlap-v1"

_CONNECTEDNESS_100_RULE_TEXT: Final = (
    "audit F9: K100 = 100 x connectedness (F8, over the PRIMARY objects, UNKNOWN pairs "
    "out); the interval is the 2.5 % / 97.5 % linear (type 7) quantiles of K100 over "
    "`resamples` respondent bootstraps drawn by random.Random(seed).random(), index "
    "floor(u * n) (OI-62). Pair status is fixed from the full sample; a resample in "
    "which one of an object's known pairs has no correlation does not score that object "
    "and is counted out of its interval (`resamples_scored`); an object unscored in the "
    "full sample has no interval"
)
_RANK_WITH_TIES_RULE_TEXT: Final = (
    "audit F9: i is above j only when i's interval lies wholly above j's (low_i > high_j); "
    "intervals that overlap or touch are tied. Overlap is not transitive, so the result "
    "is a relation per pair and a rank range per object (best = 1 + objects surely above "
    "it, worst = ranked objects - objects surely below it), never one rank or one tie group; "
    "an object without an interval is unranked"
)

#: ``correlate(multiplicities)``: each pair's signed correlation and status over the
#: respondents, respondent ``k`` taken ``multiplicities[k]`` times (0: not drawn).
PairCorrelator = Callable[
    [Sequence[int]],
    tuple[Sequence[Sequence[float | None]], Sequence[Sequence[PairStatus | str | None]]],
]


def linear_quantile(sorted_values: Sequence[float], q: float) -> float:
    """The linear quantile of already sorted values: ``np.quantile``'s default (type 7).

    The rule ``research_aggregate`` applies to its bootstrap intervals (a test pins
    the two to each other); written here because the Sociomap package imports
    nothing outside itself.
    """
    if not sorted_values:
        raise ValueError("a quantile needs at least one value")
    h = (len(sorted_values) - 1) * q
    lo = math.floor(h)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (h - lo)


@dataclass(frozen=True, slots=True)
class ConnectednessInterval:
    """One PRIMARY object's ``K100`` and its bootstrap interval (audit F9).

    ``k100`` is ``100 K_i`` of the full sample, ``None`` when the object has no
    known pair (F8: unscored); ``low`` and ``high`` are then ``None`` too.
    ``resamples_scored`` counts the resamples whose quantiles make the interval:
    an interval from fewer than the declared resamples says so here.
    ``known_pairs`` is the full sample's denominator, the set every resample averages.
    """

    object_id: str
    k100: float | None
    low: float | None
    high: float | None
    resamples_scored: int
    known_pairs: int

    @property
    def interval(self) -> tuple[float, float] | None:
        """``(low, high)``, or ``None`` when there is none."""
        if self.low is None or self.high is None:
            return None
        return (self.low, self.high)


@dataclass(frozen=True, slots=True)
class Connectedness100:
    """Every PRIMARY object's ``K100`` with its interval, and how it was drawn (audit F9)."""

    rule: str
    resamples: int
    seed: int
    generator: str
    quantiles: tuple[float, float]
    respondents: int
    scores: tuple[ConnectednessInterval, ...]

    def intervals(self) -> dict[str, tuple[float, float] | None]:
        """Each object's interval by id; ``None`` where it has none."""
        return {s.object_id: s.interval for s in self.scores}

    def to_payload(self) -> dict[str, Any]:
        """A JSON-ready body: the scores, their intervals, the draw and the rule."""
        return {
            "rule": self.rule,
            "rule_text": _CONNECTEDNESS_100_RULE_TEXT,
            "resamples": self.resamples,
            "seed": self.seed,
            "generator": self.generator,
            "quantiles": list(self.quantiles),
            "respondents": self.respondents,
            "objects": [
                {
                    "id": s.object_id,
                    "k100": s.k100,
                    "low": s.low,
                    "high": s.high,
                    "resamples_scored": s.resamples_scored,
                    "known_pairs": s.known_pairs,
                }
                for s in self.scores
            ],
        }


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer; got {value!r}")
    return value


def connectedness_100(
    object_ids: Sequence[str],
    roles: Mapping[str, ObjectRole | str],
    correlate: PairCorrelator,
    *,
    respondents: int,
    resamples: int,
    seed: int,
) -> Connectedness100:
    """``K100_i = 100 K_i`` with its respondent-bootstrap interval (audit F9).

    ``correlate`` returns each pair's signed correlation and status over the
    ``respondents``, each taken as many times as the multiplicities it is given.
    The full sample is ``correlate([1] * respondents)``. The caller passes the
    correlator that made the stored relation (``research_sociomap`` passes
    ``derive_pair_relations`` over the per-person-rescaled rows, weight times
    multiplicity), so every resample is computed exactly as the full sample is.
    ``K_i`` is :func:`primary_scores`' connectedness.

    ``resamples`` (the audit's B) and ``seed`` have no default and are recorded.
    Each resample draws ``respondents`` indices with replacement. The section's
    notes give the pair-status reading and what a resample that cannot compute
    a pair does.
    """
    n = _positive_int(respondents, "respondents")
    b = _positive_int(resamples, "resamples")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError(f"seed must be an integer; got {seed!r}")
    ids = list(object_ids)
    m = len(ids)
    full_r, full_status = correlate([1] * n)
    full = primary_scores(ids, full_r, full_status, roles)
    denominators = {s.object_id: s.known_pairs for s in full.scores}
    draws: dict[str, list[float]] = {
        s.object_id: [] for s in full.scores if s.connectedness is not None
    }

    rng = random.Random(seed)
    for _ in range(b if draws else 0):
        multiplicities = [0] * n
        for _ in range(n):
            multiplicities[min(int(rng.random() * n), n - 1)] += 1
        r_b, _statuses_not_read = correlate(multiplicities)
        _square_of(r_b, m, "a resample's r")
        # The full sample's statuses; a known pair this resample cannot compute is
        # made UNKNOWN, so primary_scores never reads a missing number, and the
        # object it belongs to is then not scored by this resample (below).
        status_b = [
            [
                PairStatus.UNKNOWN if i != j and r_b[i][j] is None else full_status[i][j]
                for j in range(m)
            ]
            for i in range(m)
        ]
        for s in primary_scores(ids, r_b, status_b, roles).scores:
            if (
                s.object_id in draws
                and s.connectedness is not None
                and s.known_pairs == denominators[s.object_id]
            ):
                draws[s.object_id].append(100.0 * s.connectedness)

    low_q, high_q = CONNECTEDNESS_QUANTILES
    out: list[ConnectednessInterval] = []
    for s in full.scores:
        values = sorted(draws.get(s.object_id, ()))
        out.append(
            ConnectednessInterval(
                object_id=s.object_id,
                k100=None if s.connectedness is None else 100.0 * s.connectedness,
                low=linear_quantile(values, low_q) if values else None,
                high=linear_quantile(values, high_q) if values else None,
                resamples_scored=len(values),
                known_pairs=s.known_pairs,
            )
        )
    return Connectedness100(
        rule=CONNECTEDNESS_100_RULE,
        resamples=b,
        seed=seed,
        generator=CONNECTEDNESS_BOOTSTRAP_GENERATOR,
        quantiles=CONNECTEDNESS_QUANTILES,
        respondents=n,
        scores=tuple(out),
    )


class RankRelation(StrEnum):
    """What two intervals let a ranking say about their objects (audit F9)."""

    #: The first object's interval lies wholly above the second's.
    ABOVE = "above"
    #: The first object's interval lies wholly below the second's.
    BELOW = "below"
    #: The intervals overlap or touch: no order is claimed.
    TIED = "tied"


@dataclass(frozen=True, slots=True)
class RankedObject:
    """One object's place in a ranking with ties (audit F9).

    ``outranks`` are the objects whose interval lies wholly below this one's,
    ``outranked_by`` those wholly above, ``tied_with`` the rest of the ranked
    objects. ``rank_best`` and ``rank_worst`` bound the rank the intervals allow:
    ``1 + len(outranked_by)`` and ``ranked - len(outranks)``. Equal bounds mean
    the rank is settled.
    """

    object_id: str
    interval: tuple[float, float]
    outranks: tuple[str, ...]
    outranked_by: tuple[str, ...]
    tied_with: tuple[str, ...]
    rank_best: int
    rank_worst: int


@dataclass(frozen=True, slots=True)
class TiedRanking:
    """An order only where the intervals do not overlap (audit F9).

    ``objects`` keeps the input's order (no order is implied by it); ``unranked``
    are the objects that had no interval. Overlap is not transitive -- A can be
    tied with B and B with C while A is above C -- so there are no tie groups:
    read :meth:`relation` for a pair, ``rank_best`` / ``rank_worst`` for an object.
    """

    rule: str
    objects: tuple[RankedObject, ...]
    unranked: tuple[str, ...]

    def relation(self, a: str, b: str) -> RankRelation:
        """What the ranking says about ``a`` against ``b``; both must be ranked."""
        entry = {o.object_id: o for o in self.objects}
        if a not in entry or b not in entry:
            raise KeyError(f"both objects must be ranked; got {a!r}, {b!r}")
        if a == b:
            raise ValueError("an object is not ranked against itself")
        if b in entry[a].outranks:
            return RankRelation.ABOVE
        if b in entry[a].outranked_by:
            return RankRelation.BELOW
        return RankRelation.TIED

    def to_payload(self) -> dict[str, Any]:
        """A JSON-ready body: each object's relations and rank range, and the rule."""
        return {
            "rule": self.rule,
            "rule_text": _RANK_WITH_TIES_RULE_TEXT,
            "objects": [
                {
                    "id": o.object_id,
                    "interval": list(o.interval),
                    "outranks": list(o.outranks),
                    "outranked_by": list(o.outranked_by),
                    "tied_with": list(o.tied_with),
                    "rank_best": o.rank_best,
                    "rank_worst": o.rank_worst,
                }
                for o in self.objects
            ],
            "unranked": list(self.unranked),
        }


def _checked_interval(object_id: str, value: Any) -> tuple[float, float]:
    try:
        low, high = value
    except (TypeError, ValueError):
        raise ValueError(f"{object_id!r}: an interval is (low, high); got {value!r}") from None
    for bound in (low, high):
        if isinstance(bound, bool) or not isinstance(bound, int | float):
            raise ValueError(f"{object_id!r}: interval bounds must be numbers; got {value!r}")
        if not math.isfinite(bound):
            raise ValueError(f"{object_id!r}: interval bounds must be finite; got {value!r}")
    if low > high:
        raise ValueError(f"{object_id!r}: interval low exceeds high; got {value!r}")
    return (float(low), float(high))


def rank_with_ties(intervals: Mapping[str, tuple[float, float] | None]) -> TiedRanking:
    """Rank ``i`` above ``j`` only where their intervals do not overlap (audit F9).

    ``intervals`` maps each object to its ``(low, high)`` -- as
    :meth:`Connectedness100.intervals` returns them -- or ``None`` when it has
    none; such an object is unranked, never placed last. Intervals that touch
    (``low_i == high_j``) overlap and are tied: the audit's "do not overlap" is
    read with closed intervals.
    """
    ranked = {
        oid: _checked_interval(oid, value) for oid, value in intervals.items() if value is not None
    }
    ids = list(ranked)
    total = len(ids)
    objects: list[RankedObject] = []
    for a in ids:
        low_a, high_a = ranked[a]
        outranks = tuple(b for b in ids if b != a and low_a > ranked[b][1])
        outranked_by = tuple(b for b in ids if b != a and ranked[b][0] > high_a)
        tied_with = tuple(b for b in ids if b != a and b not in outranks and b not in outranked_by)
        objects.append(
            RankedObject(
                object_id=a,
                interval=ranked[a],
                outranks=outranks,
                outranked_by=outranked_by,
                tied_with=tied_with,
                rank_best=1 + len(outranked_by),
                rank_worst=total - len(outranks),
            )
        )
    return TiedRanking(
        rule=RANK_WITH_TIES_RULE,
        objects=tuple(objects),
        unranked=tuple(oid for oid, value in intervals.items() if value is None),
    )
