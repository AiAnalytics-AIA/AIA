"""A research run's Sociomap: integrated, computed, and not exposed (ADR 0016 decision 6).

PR C chunk 6. For each tracked object set of the specification:

1. **the relation matrix** -- ported from the unit, ``sociomap.py``
   ``derive_relation_matrix``: object x object weighted Pearson correlation of the
   respondents' ratings, mapped onto 1-10 (``corr = -1 -> 1``, ``0 -> 5.5``,
   ``+1 -> 10``), fewer than five common ratings -> 5.5, diagonal 0; and each
   object's weighted mean rating. Weighted by ``_analysis_weight`` normalised to
   sum N, as the unit's ``project_engine._battery_dataset`` builds ``vaha``;
2. **each pair's status** -- the audit *NPC Sociomapa: faulty formulas in the
   code* (F3): the same correlation signed, the number of respondents who rated
   both objects, the Fisher-z interval and what the pair can be said to be
   (``UNKNOWN`` below ``n_min``, ``RELIABLE``, ``WEAK``). The unit's 5.5 stamp
   stays in step 1 only, because ``aia-sociomap-1`` is the unit's formula kept
   as a named comparison alternative; the status says where that matrix must
   not be read (plan ``sociomap-formula-corrections``, chunk 1a);
3. **each object's alignment and connectedness** -- the audit's replacement
   of the classic score (F8), over the PRIMARY objects with UNKNOWN pairs left
   out; every object of a tracked set is PRIMARY until AIA has an object
   manager (chunk 1b). Stored beside the map; the map's height is still the
   preset's;
4. **the map** -- AIA's deterministic engine, ``compute_sociomap``, under the
   preset ``AIA_SOCIOMAP_V1`` adopted by name, with only the rating scale taken
   from the battery (a property of the data, recorded on the artifact).

**Integration is not exposure.** The preset carries four AIA methodology
declarations that PROGRESS D6 has not approved, so every Sociomap this module
builds is ``INTERNAL_ONLY``: the Study's researchers may inspect it; no
client-facing surface, export or report may render it. :func:`require_client_facing`
is the one check such a surface calls, and it refuses while D6 is open.

Pure: no I/O.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, model_validator

from .fieldwork import FieldworkDataset
from .research_design import ResearchSpecification, SpecBattery
from .sociomap import AIA_SOCIOMAP_V1, compute_sociomap
from .sociomap.metrics import ObjectRole, primary_scores
from .sociomap.models import RatingsMatrix, RelationMatrix, SociomapInputs
from .sociomap.relations import AUDIT_PROVISIONAL_N_MIN, PairStatus, fisher_interval, pair_status

__all__ = [
    "D6_OPEN",
    "PAIR_CONFIDENCE",
    "RELATION_SOURCE",
    "SOCIOMAP_VERSION",
    "MethodologyStatus",
    "PairRelations",
    "SociomapNotApproved",
    "battery_sociomap",
    "derive_pair_relations",
    "derive_relation_matrix",
    "require_client_facing",
    "research_sociomaps",
]

#: The version of this module's artifact body. ``2``: the relation block carries
#: every pair's signed correlation, rater count, interval and status (chunk 1a);
#: the executor fingerprints its input with it, so a run computed under ``1`` is
#: not reused as if it had them. ``3``: each set carries ``object_scores``, the
#: audit's alignment and connectedness (chunk 1b), so a body stored under ``2``
#: (without them) is not reused as if it had them. Not the engine preset
#: (``aia-sociomap-<n>``).
SOCIOMAP_VERSION: Final = "aia-research-sociomap-3"
RELATION_SOURCE: Final = "DERIVED_FROM_COMMON_RESPONDENT_RATINGS"
#: The audit's interval (F3): a 95 % Fisher-z interval decides RELIABLE.
PAIR_CONFIDENCE: Final = 0.95

#: PROGRESS D6: the four AIA Sociomap declarations await the methodology owner.
#: Flipping this is a methodology decision recorded in PROGRESS, never a fix.
D6_OPEN: Final = True


class MethodologyStatus(StrEnum):
    #: The Study's researchers may look at it; nobody else, nowhere else.
    INTERNAL_ONLY = "INTERNAL_ONLY"
    #: D6 approved: a client-facing surface may render it.
    CLIENT_FACING = "CLIENT_FACING"


class SociomapNotApproved(PermissionError):
    """A Sociomap reached a client-facing surface while its methodology is not approved."""


def require_client_facing(sociomap: dict[str, Any]) -> None:
    """The check every client-facing surface, export and report makes. Fails closed."""
    if sociomap.get("methodology_status") != MethodologyStatus.CLIENT_FACING.value:
        raise SociomapNotApproved(
            "this Sociomap is INTERNAL_ONLY: its methodology (PROGRESS D6) is not approved "
            "for client use"
        )


def _methodology_status() -> MethodologyStatus:
    return MethodologyStatus.INTERNAL_ONLY if D6_OPEN else MethodologyStatus.CLIENT_FACING


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


def battery_sociomap(battery: SpecBattery, dataset: FieldworkDataset) -> dict[str, Any]:
    """One tracked set's relation matrix and its Sociomap, as an internal artifact body."""
    object_ids = [o.id for o in battery.objects]
    qids = [battery.question_id(o) for o in battery.objects]
    raw = [r.weight for r in dataset.respondents]
    total = sum(raw) or 1.0
    weights = [w * (len(raw) / total) for w in raw]  # project_engine.py:34-35, "vaha"
    ratings: list[list[float | None]] = []
    for r in dataset.respondents:
        row: list[float | None] = []
        for q in qids:
            value = r.answers.get(q)
            row.append(
                float(value) if isinstance(value, int) and not isinstance(value, bool) else None
            )
        ratings.append(row)
    relation, scores = derive_relation_matrix(ratings, weights)
    pairs = derive_pair_relations(
        ratings, weights, n_min=AUDIT_PROVISIONAL_N_MIN, confidence=PAIR_CONFIDENCE
    )
    # Every object of a tracked set is PRIMARY: AIA has no object manager, so no
    # set has context objects yet. Declared here, by name, not defaulted.
    object_scores = primary_scores(
        object_ids, pairs.r, pairs.status, dict.fromkeys(object_ids, ObjectRole.PRIMARY)
    )

    low, high = battery.scale
    spec = AIA_SOCIOMAP_V1.model_copy(
        update={
            "ratings": AIA_SOCIOMAP_V1.ratings.model_copy(
                update={"rating_scale_min": float(low), "rating_scale_max": float(high)}
            )
        }
    )
    inputs = SociomapInputs(
        ratings=RatingsMatrix(
            respondent_ids=tuple(r.respondent_id for r in dataset.respondents),
            object_ids=tuple(object_ids),
            values=tuple(tuple(row) for row in ratings),
        ),
        object_relation=RelationMatrix(
            entity_ids=tuple(object_ids), values=tuple(tuple(row) for row in relation)
        ),
    )
    artifact = compute_sociomap(inputs, spec)
    return {
        "battery_id": battery.id,
        "title": battery.title,
        "family": battery.family,
        "objects": [{"id": o.id, "label": o.label} for o in battery.objects],
        "methodology_status": _methodology_status().value,
        "methodology_decision": "PROGRESS D6: the four AIA Sociomap declarations, open",
        "preset": AIA_SOCIOMAP_V1.methodology_version,
        "rating_scale": [low, high],
        "relation": {
            "source": RELATION_SOURCE,
            "ported_from": "legacy/npc-panel-18.6.6/app/sociomap.py derive_relation_matrix",
            "matrix": relation,
            "matrix_caveat": (
                "the unit's 1-10 strength, kept for aia-sociomap-1: a pair below five raters "
                "is stamped 5.5 and r = 0 reads as a medium relation (audit F3, F4); read "
                "status before matrix"
            ),
            "scores": scores,
            **pairs.model_dump(mode="json"),
            "status_counts": pairs.counts(),
            "status_rule": (
                "audit F3: UNKNOWN below n_min common raters or without a correlation; "
                "RELIABLE when the Fisher-z interval at confidence excludes 0; WEAK otherwise. "
                "n_min is the audit's provisional value, pending its Q6"
            ),
        },
        "object_scores": object_scores.to_payload(),
        "sociomap": artifact.model_dump(mode="json"),
    }


def research_sociomaps(spec: ResearchSpecification, dataset: FieldworkDataset) -> dict[str, Any]:
    """Every tracked set's Sociomap. A specification without one has none, and says so."""
    return {
        "sociomap_version": SOCIOMAP_VERSION,
        "methodology_status": _methodology_status().value,
        "data_origin": dataset.origin.value if dataset.origin else None,
        "batteries": [battery_sociomap(b, dataset) for b in spec.batteries],
        "note": None if spec.batteries else "Návrh nemá sledovanou sadu; Sociomapa nevznikla.",
    }
