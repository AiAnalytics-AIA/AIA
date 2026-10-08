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
   preset's. Beside them, connectedness on 0-100 with a respondent-bootstrap
   interval and the order those intervals allow (audit F9, chunk 4a);
4. **the map** -- AIA's deterministic engine, ``compute_sociomap``, under the
   spec the run pinned when it was started (:class:`SociomapMethod`), with only the
   rating scale taken from the battery (a property of the data, recorded on the
   artifact). The module's preset is what a *new* run pins; a run executes the spec
   it pinned, whatever the preset has become since, and a run stored before methods
   were pinned is read as ``aia-sociomap-1`` (:data:`LEGACY_METHODS`), the method that
   computed it (plan ``sociomap-formula-corrections`` § 8.2, I0 and I4).

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

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .fieldwork import FieldworkDataset
from .pipeline import fingerprint
from .research_design import ResearchSpecification, SpecBattery
from .sociomap import (
    AIA_SOCIOMAP_V1,
    SociomapSpec,
    compute_sociomap,
    read_spec,
    require_supported,
    spec_payload,
)
from .sociomap.metrics import ObjectRole, connectedness_100, primary_scores, rank_with_ties
from .sociomap.models import RatingsMatrix, RelationMatrix, SociomapInputs
from .sociomap.relations import (
    AUDIT_PROVISIONAL_N_MIN,
    PairStatus,
    fisher_interval,
    pair_status,
    person_minmax,
)

__all__ = [
    "CONNECTEDNESS_NOT_COMPUTED",
    "CONNECTEDNESS_RESAMPLES",
    "CONNECTEDNESS_SEED",
    "D6_OPEN",
    "LEGACY_METHODS",
    "PAIR_CONFIDENCE",
    "RELATION_SOURCE",
    "RESCALE_RULE",
    "SOCIOMAP_VERSION",
    "MethodologyStatus",
    "PairRelations",
    "SociomapMethod",
    "SociomapMethodsInvalid",
    "SociomapNotApproved",
    "battery_sociomap",
    "default_methods",
    "derive_pair_relations",
    "derive_relation_matrix",
    "methods_fingerprint",
    "read_methods",
    "require_client_facing",
    "rescaled_battery_ratings",
    "research_sociomaps",
]

#: The version of this module's artifact body. ``2``: the relation block carries
#: every pair's signed correlation, rater count, interval and status (chunk 1a);
#: the executor fingerprints its input with it, so a run computed under ``1`` is
#: not reused as if it had them. ``3``: each set carries ``object_scores``, the
#: audit's alignment and connectedness (chunk 1b), so a body stored under ``2``
#: (without them) is not reused as if it had them. ``4``: each set carries
#: ``relation_rescaled``, every pair over each person's own 0-1 scale (audit F2,
#: chunk 2a), and ``object_scores`` read it instead of the raw correlation.
#: ``5``: each set carries ``connectedness_100``, the audit's F9 score with its
#: bootstrap interval and the ranking with ties (chunk 4a), so a body stored under
#: ``4`` (without them) is not reused as if it had them. ``6``: the body names the
#: methods the run pinned (``methods``) and each set's map is computed under the
#: pinned spec, not the module's preset (plan § 8.2, S1). Not the engine preset
#: (``aia-sociomap-<n>``).
SOCIOMAP_VERSION: Final = "aia-research-sociomap-6"
#: How ``relation_rescaled`` was made, recorded on every body.
RESCALE_RULE: Final = (
    "audit F2: each rating on its item's declared 0-1 scale (audit F1, eq. 3), then each "
    "respondent's own min-max over every declared rating item of the specification they "
    "rated, straight-liners excluded, then the weighted Pearson correlation as the unit "
    "computes it; the weighting is AIA's reading where the audit is silent (register AUDIT-F2)"
)
RELATION_SOURCE: Final = "DERIVED_FROM_COMMON_RESPONDENT_RATINGS"
#: The audit's interval (F3): a 95 % Fisher-z interval decides RELIABLE.
PAIR_CONFIDENCE: Final = 0.95
#: Audit F9's B ("e.g. 500"): respondent bootstraps behind each K100 interval.
#: Declared here by name and recorded on every body; never shrunk silently.
CONNECTEDNESS_RESAMPLES: Final = 500
#: The bootstrap's seed (OI-62's generator), recorded on every body: the same
#: dataset gives the same intervals on any host.
CONNECTEDNESS_SEED: Final = 20261007

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


class SociomapMethodsInvalid(ValueError):
    """A run's pinned methods cannot be read, or are not a set this module computes."""


class SociomapMethod(BaseModel):
    """One Sociomap method a run pinned when it was started: its id and its whole spec.

    The spec is stored, not its name: a run executes exactly the methodology it was
    started under, even after the module's preset changes. ``spec_fingerprint`` is the
    spec's own and is re-checked on every read, so an edited pin is refused rather than
    computed. The battery's rating scale is filled in at execution (a property of the
    data, recorded on the artifact), as it always was.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    method_id: str = Field(min_length=1, max_length=100)
    spec: dict[str, Any]
    spec_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def of(cls, spec: SociomapSpec) -> SociomapMethod:
        """The pin for ``spec``: its methodology version, its stored form, its fingerprint."""
        return cls(
            method_id=spec.methodology_version,
            spec=spec_payload(spec),
            spec_fingerprint=spec.fingerprint(),
        )

    def resolve(self) -> SociomapSpec:
        """The pinned spec, verified against its fingerprint and its id, and computable.

        Raises :class:`SociomapMethodsInvalid` for a pin that does not read, does not hash
        to its fingerprint or names another method, and
        :class:`~.sociomap.specification.UnsupportedMethodology` for a spec this engine
        cannot compute: nothing substitutes another method.
        """
        try:
            spec = read_spec(self.spec)
        except (ValueError, ValidationError) as exc:
            raise SociomapMethodsInvalid(
                f"{self.method_id}: the pinned spec does not read: {exc}"
            ) from exc
        if spec.fingerprint() != self.spec_fingerprint:
            raise SociomapMethodsInvalid(
                f"{self.method_id}: the pinned spec does not match its recorded fingerprint"
            )
        if spec.methodology_version != self.method_id:
            raise SociomapMethodsInvalid(
                f"the pin names {self.method_id!r} but holds {spec.methodology_version!r}"
            )
        require_supported(spec)
        return spec


#: How a run stored before methods were pinned is read: ``aia-sociomap-1``, the preset
#: that computed every such run. Never back-filled onto the stored run.
LEGACY_METHODS: Final = (SociomapMethod.of(AIA_SOCIOMAP_V1),)


def default_methods() -> tuple[SociomapMethod, ...]:
    """What a new run pins: today ``aia-sociomap-1`` alone, the shipped picture."""
    return LEGACY_METHODS


def methods_fingerprint(methods: Sequence[SociomapMethod]) -> str:
    """One identity for a pinned set, in its order."""
    return fingerprint([m.model_dump(mode="json") for m in methods])


def read_methods(value: Any) -> tuple[SociomapMethod, ...]:
    """A run's pinned methods from its stored form; ``None`` (a run stored before pins) is
    :data:`LEGACY_METHODS`.

    The set must be one this module computes: at least one method, no id twice, and
    exactly one spec of contract 2, whose map is the set's ``sociomap`` (the picture the
    Results and the report draw until chunk 5). Raises :class:`SociomapMethodsInvalid`.
    """
    if value is None:
        return LEGACY_METHODS
    if not isinstance(value, list | tuple) or not value:
        raise SociomapMethodsInvalid("a run pins at least one Sociomap method")
    try:
        methods = tuple(SociomapMethod.model_validate(v) for v in value)
    except ValidationError as exc:
        raise SociomapMethodsInvalid(f"a pinned method does not read: {exc}") from exc
    ids = [m.method_id for m in methods]
    if len(set(ids)) != len(ids):
        raise SociomapMethodsInvalid(f"a method is pinned twice: {ids}")
    contract_2 = [m for m in methods if m.spec.get("contract_version") == "2"]
    if len(contract_2) != 1:
        raise SociomapMethodsInvalid(
            "exactly one contract-2 method draws a set's map until chunk 5; pinned "
            f"{[m.method_id for m in contract_2]}"
        )
    return methods


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


def _rating(value: Any) -> float | None:
    return float(value) if isinstance(value, int) and not isinstance(value, bool) else None


def rescaled_battery_ratings(
    battery: SpecBattery, dataset: FieldworkDataset, rated_with: Sequence[SpecBattery]
) -> tuple[list[list[float | None]], list[str]]:
    """``battery``'s ratings on each respondent's own 0-1 scale (audit F2), and who has none.

    Every rating of every set in ``rated_with`` -- the specification's declared rating
    items (audit F1) -- is first put on its own declared 0-1 scale, so items with different
    ends compare; each respondent's lowest is then 0 and highest 1 over all of them
    (:func:`~.sociomap.relations.person_minmax`), and ``battery``'s columns are returned.
    A respondent whose rated items all share one value is excluded: their row is all
    ``None`` and their id is listed.
    """
    if not any(b.id == battery.id for b in rated_with):
        raise ValueError(f"battery {battery.id!r} is not among the sets it is rated with")
    columns: list[tuple[str, int, int]] = []
    own: list[int] = []
    for b in rated_with:
        low, high = b.scale
        if not high > low:
            raise ValueError(f"battery {b.id!r} declares an empty scale {b.scale!r}")
        for obj in b.objects:
            if b.id == battery.id:
                own.append(len(columns))
            columns.append((b.question_id(obj), low, high))
    rows: list[list[float | None]] = []
    for r in dataset.respondents:
        row: list[float | None] = []
        for qid, low, high in columns:
            value = _rating(r.answers.get(qid))
            row.append(None if value is None else (value - low) / (high - low))
        rows.append(row)
    scaled = person_minmax(rows)
    ids = [dataset.respondents[k].respondent_id for k in scaled.excluded]
    return [[scaled.values[k][c] for c in own] for k in range(len(rows))], ids


#: What the body says where the bootstrap was not asked for (the worker's kill switch,
#: ``AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED``): not computed, never a 0 or a guess.
CONNECTEDNESS_NOT_COMPUTED: Final = {
    "status": "not_computed",
    "reason": (
        "the respondent bootstrap (audit F9) is off in this deployment: about 90 s per "
        "1,500 x 22 set at B = 500; AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED turns it on"
    ),
}


def battery_sociomap(
    battery: SpecBattery,
    dataset: FieldworkDataset,
    *,
    rated_with: Sequence[SpecBattery],
    connectedness_interval: bool,
    map_spec: SociomapSpec,
) -> dict[str, Any]:
    """One tracked set's relation matrix and its Sociomap, as an internal artifact body.

    ``rated_with`` are every tracked set of the specification: the declared rating items
    each respondent's own scale is read over (audit F2: all the items they rated, not only
    this family). ``map_spec`` is the run's pinned contract-2 spec; only its rating scale
    is replaced, by the battery's.
    """
    object_ids = [o.id for o in battery.objects]
    qids = [battery.question_id(o) for o in battery.objects]
    raw = [r.weight for r in dataset.respondents]
    total = sum(raw) or 1.0
    weights = [w * (len(raw) / total) for w in raw]  # project_engine.py:34-35, "vaha"
    ratings: list[list[float | None]] = [
        [_rating(r.answers.get(q)) for q in qids] for r in dataset.respondents
    ]
    relation, scores = derive_relation_matrix(ratings, weights)
    pairs = derive_pair_relations(
        ratings, weights, n_min=AUDIT_PROVISIONAL_N_MIN, confidence=PAIR_CONFIDENCE
    )
    rescaled, not_rescaled = rescaled_battery_ratings(battery, dataset, rated_with)
    rescaled_pairs = derive_pair_relations(
        rescaled, weights, n_min=AUDIT_PROVISIONAL_N_MIN, confidence=PAIR_CONFIDENCE
    )
    # Every object of a tracked set is PRIMARY: AIA has no object manager, so no
    # set has context objects yet. Declared here, by name, not defaulted. The scores
    # read the relation after the rating habit is removed (audit F8 reads r~, F2).
    object_scores = primary_scores(
        object_ids,
        rescaled_pairs.r,
        rescaled_pairs.status,
        dict.fromkeys(object_ids, ObjectRole.PRIMARY),
    )

    def correlate(
        multiplicities: Sequence[int],
    ) -> tuple[tuple[tuple[float | None, ...], ...], tuple[tuple[PairStatus | None, ...], ...]]:
        # A resample: each respondent's rescaled row taken as many times as drawn,
        # as a weight multiple (the weighted Pearson of duplicated rows). The rows
        # are rescaled once: each person's min-max is their own (F2).
        drawn = derive_pair_relations(
            rescaled,
            [k * w for k, w in zip(multiplicities, weights, strict=True)],
            n_min=AUDIT_PROVISIONAL_N_MIN,
            confidence=PAIR_CONFIDENCE,
        )
        return drawn.r, drawn.status

    connectedness: dict[str, Any] = dict(CONNECTEDNESS_NOT_COMPUTED)
    if connectedness_interval:
        k100 = connectedness_100(
            object_ids,
            dict.fromkeys(object_ids, ObjectRole.PRIMARY),
            correlate,
            respondents=len(rescaled),
            resamples=CONNECTEDNESS_RESAMPLES,
            seed=CONNECTEDNESS_SEED,
        )
        connectedness = {
            "status": "computed",
            **k100.to_payload(),
            "ranking": rank_with_ties(k100.intervals()).to_payload(),
        }

    low, high = battery.scale
    spec = map_spec.model_copy(
        update={
            "ratings": map_spec.ratings.model_copy(
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
        "preset": map_spec.methodology_version,
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
        "relation_rescaled": {
            "rule": RESCALE_RULE,
            "rated_with": [b.id for b in rated_with],
            "excluded_respondents": not_rescaled,
            **rescaled_pairs.model_dump(mode="json"),
            # Audit F4: how strong, whichever its direction, beside the signed r~.
            "abs_r": [[None if v is None else abs(v) for v in row] for row in rescaled_pairs.r],
            "status_counts": rescaled_pairs.counts(),
        },
        "object_scores": object_scores.to_payload(),
        "connectedness_100": connectedness,
        "sociomap": artifact.model_dump(mode="json"),
    }


def research_sociomaps(
    spec: ResearchSpecification,
    dataset: FieldworkDataset,
    *,
    methods: Sequence[SociomapMethod],
    connectedness_interval: bool,
) -> dict[str, Any]:
    """Every tracked set's Sociomap. A specification without one has none, and says so.

    ``methods`` are the run's pinned methods (:func:`read_methods`); each is resolved --
    verified and checked computable -- before any number, so a pin this engine cannot
    compute fails here by name. ``connectedness_interval`` is the worker's kill switch for
    the F9 bootstrap, passed by name: off, each set records
    :data:`CONNECTEDNESS_NOT_COMPUTED` instead.
    """
    pinned = read_methods([m.model_dump(mode="json") for m in methods])
    resolved = [(m, m.resolve()) for m in pinned]
    map_spec = next(s for m, s in resolved if m.spec.get("contract_version") == "2")
    return {
        "sociomap_version": SOCIOMAP_VERSION,
        "methods": [
            {"method_id": m.method_id, "spec_fingerprint": m.spec_fingerprint} for m in pinned
        ],
        "methodology_status": _methodology_status().value,
        "data_origin": dataset.origin.value if dataset.origin else None,
        "batteries": [
            battery_sociomap(
                b,
                dataset,
                rated_with=spec.batteries,
                connectedness_interval=connectedness_interval,
                map_spec=map_spec,
            )
            for b in spec.batteries
        ],
        "note": None if spec.batteries else "Návrh nemá sledovanou sadu; Sociomapa nevznikla.",
    }
