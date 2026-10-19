"""``compute_object_map``: the audit's object map, ``aia-sociomap-2`` (spec contract 3).

Plan ``sociomap-formula-corrections`` § 8.2, S2. One pure function from
:class:`~.models_v3.ObjectMapInputs` and a :class:`~.specification.SociomapSpecV3` to one
:class:`~.models_v3.SociomapArtifactV3`, in the audit's order::

    require_supported(spec)                               fail closed before any number
    F1   each rating on its item's declared 0-1 scale     (every item of the universe)
    F2   each person's min-max over every item rated      no spread -> NOT PLACED (F11)
    F3   each mapped pair's weighted r~, n, interval and status at n_min
    F4   |r~| beside the signed r~
    F6   sqrt(2 (1 - r~)) over the RELIABLE and WEAK pairs; UNKNOWN weighs 0
    F7   SMACOF from a Torgerson start; Stress-1 and its band; never rescaled
    F8   PRIMARY alignment and connectedness, UNKNOWN left out; the mean rating as height
    F9   K100 with its respondent-bootstrap interval, when the caller asks for it
    F12  the envelope terrain over the PRIMARY hills, when the spec declares one (4b); the
         framed envelope over their relative heights under ``aia-sociomap-5``
         the split-half check and the uncertainty radius of a mapped ``aia-sociomap-5`` map

Every step is a function another chunk already landed and tested (2a ``person_minmax``,
1a ``derive_pair_relations``, 2b ``fit_smacof_objects``, 2c ``stress_quality``, 1b
``primary_scores``, 4a ``connectedness_100``); this module composes them and records what
it composed. Respondent placement (chunk 3) is not computed and the artifact says so; so is
the terrain where the spec declares none (``aia-sociomap-2``) or the family is not mapped.
A family the data cannot map is :data:`~.models_v3.MapOutcome.NOT_MAPPABLE` with its reason,
never an exception and never a picture.

``connectedness_interval`` is the deployment's kill switch for F9's bootstrap
(``AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED``, about 90 s per 1,500 x 22 family at
B = 500), passed by name: off, the artifact records that it was not computed.

Pure: no I/O, no clock; the only randomness is the bootstrap's seeded generator.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from .layout import (
    UnfoldingDesignError,
    correlation_distances,
    fit_smacof_objects,
    stress_terms,
)
from .metrics import ObjectRole, connectedness_100, primary_scores, rank_with_ties
from .models_v3 import (
    OBJECT_MAP_IMPLEMENTATION,
    OBJECT_MAP_IMPLEMENTATION_VERSION,
    CredibilityRule,
    MapCredibility,
    MapOutcome,
    NotComputed,
    NotMappable,
    NotMappableReason,
    ObjectHeights,
    ObjectMapInputs,
    ObjectMapLayout,
    ObjectMapProvenance,
    ObjectMapSupport,
    SociomapArtifactV3,
    SparseDesign,
)
from .pairs import PairRelations, derive_pair_relations
from .relations import PairStatus, person_minmax
from .signed_off_credibility import map_uncertainty, split_half_agreement
from .signed_off_inputs import PreparedInputs, prepare
from .signed_off_layout import (
    SMACOF_ITMAX,
    PositionMethod,
    choose_method,
    interval_mds,
    soft_rank_spearman,
    to_ruler,
)
from .slots import (
    DISTANCE,
    EFFECT_FLOOR,
    EFFECTIVE_N,
    HEIGHT,
    INTERVAL_HIGH,
    INTERVAL_LOW,
    K100,
    NO_SLOTS,
    PERSON,
    SCALE,
    STRESS_1,
    SUPPORT_EFFECTIVE_N,
    Slots,
)
from .specification import (
    LEGACY_MIN_OBJECTS,
    ObjectHeightMetric,
    PairEvidenceBasis,
    RelationEstimator,
    SociomapSpecV3,
    TerrainMethod,
    UnsupportedMethodology,
    require_supported,
)
from .terrain import (
    EnvelopeHill,
    EnvelopeParameters,
    EnvelopeTerrain,
    fit_frame,
    object_envelope,
)
from .view import stress_quality

__all__ = [
    "CONNECTEDNESS_OFF",
    "NOT_PLACED_NO_SPREAD",
    "RESPONDENTS_NOT_COMPUTED",
    "TERRAIN_NOT_COMPUTED",
    "TERRAIN_NOT_MAPPED",
    "WEIGHTING",
    "WEIGHTING_KISH",
    "compute_object_map",
]

#: Why a respondent is not placed (F11): their rated items share one value, or they rated
#: fewer than two -- there is no preference to rescale.
NOT_PLACED_NO_SPREAD: Final = (
    "no spread over the rating items: every item rated with one value, or fewer than two "
    "rated (audit F2, F11)"
)
RESPONDENTS_NOT_COMPUTED: Final = NotComputed(
    status="not_computed",
    reason=(
        "respondent placement is chunk 3 (ideal points against this object map, audit F10); "
        "its misfit threshold is open (plan sociomap-formula-corrections § 4a, 0b)"
    ),
)
TERRAIN_NOT_COMPUTED: Final = NotComputed(
    status="not_computed",
    reason=(
        "the envelope terrain is chunk 4b (audit F12, F13); its kernel width on the fixed "
        "ruler is open (0b)"
    ),
)
#: Why a declared terrain was not computed: nothing to stand the hills on.
TERRAIN_NOT_MAPPED: Final = NotComputed(
    status="not_computed",
    reason="the objects are not mappable, so there is no layout to stand the hills on",
)
#: How the weights enter the map, recorded on every artifact (plan § 8.2, I3).
WEIGHTING: Final = (
    "each pair's correlation is weighted by the respondents' weights as given (the research "
    "step normalises them to sum to N, the unit's vaha); a pair's status reads n, the count of "
    "respondents who rated both, not the weight, so its interval is somewhat optimistic under "
    "unequal weights (Kish's n per pair is chunk 1d's, pending Q6); a K100 resample multiplies "
    "each weight by how many times its respondent was drawn; the heights are weighted means; "
    "nothing here is clustered on donors"
)
#: The same under the evidence policy's Kish basis (Q6, chunk 1d): what a pair's status reads
#: is then each pair's Kish effective n, so the interval no longer overstates the evidence.
WEIGHTING_KISH: Final = (
    "each pair's correlation is weighted by the respondents' weights as given (the research "
    "step normalises them to sum to N, the unit's vaha); a pair's status and interval read "
    "the Kish effective n of the weights of the respondents who rated both, (sum w)^2 / "
    "sum w^2, not their count (AIA's Q6 decision); a K100 resample multiplies each weight by "
    "how many times its respondent was drawn, and its Kish n reads the weights of the "
    "distinct respondents drawn; the heights are weighted means; nothing here is clustered "
    "on donors"
)
#: The same under the baseline-corrected relation (``aia-sociomap-5``), which is unweighted.
WEIGHTING_UNWEIGHTED: Final = (
    "the relations are unweighted: each pair's baseline-corrected r~, its n and its status read "
    "every respondent who rated both objects once, whatever their weight; the heights are "
    "weighted means on the declared 0-1 scale; nothing here is clustered on donors"
)
#: Why a respondent is not placed under the baseline-corrected relation: it centres each
#: person's ratings of the mapped objects only.
NOT_PLACED_NO_SPREAD_OBJECTS: Final = (
    "no spread over the mapped objects: every object rated with one value, or fewer than two rated"
)
#: The connectedness score's bootstrap resamples the weighted Pearson relation; the
#: baseline-corrected one has none.
CONNECTEDNESS_NOT_IN_METHOD: Final = {
    "status": "not_computed",
    "reason": (
        "the respondent bootstrap of the connectedness score resamples the weighted Pearson "
        "relation; the baseline-corrected relation of this method has no such interval"
    ),
}
#: The formulas a version may replace that the baseline-corrected relation and its signed-off
#: layout never read: a replacement would be stored and silently do nothing, so it is refused.
_UNREAD_BY_BASELINE_CORRECTED: Final = (
    PERSON,
    EFFECTIVE_N,
    INTERVAL_LOW,
    INTERVAL_HIGH,
    EFFECT_FLOOR,
    K100,
    DISTANCE,
    STRESS_1,
)
CONNECTEDNESS_OFF: Final = {
    "status": "not_computed",
    "reason": (
        "the respondent bootstrap (audit F9) is off in this deployment: about 90 s per "
        "1,500 x 22 family at B = 500; AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED turns it on"
    ),
}


def _scaled(inputs: ObjectMapInputs, slots: Slots = NO_SLOTS) -> list[list[float | None]]:
    """F1: every rating on its item's declared 0-1 scale; a value off its scale is refused.
    ``slots`` may replace the transform (``f1.scale``); the refusal stays."""
    replaced = slots.get(SCALE)
    rows: list[list[float | None]] = []
    for k, row in enumerate(inputs.values):
        out: list[float | None] = []
        for item, value in zip(inputs.items, row, strict=True):
            if value is None:
                out.append(None)
                continue
            if not item.scale_min <= value <= item.scale_max:
                raise ValueError(
                    f"respondent {inputs.respondent_ids[k]!r} rated {item.item_id!r} {value}, "
                    f"outside its declared scale [{item.scale_min}, {item.scale_max}]"
                )
            out.append(
                (value - item.scale_min) / (item.scale_max - item.scale_min)
                if replaced is None
                else float(replaced(a=value, lo=item.scale_min, hi=item.scale_max))
            )
        rows.append(out)
    return rows


def _unreached(known: Sequence[Sequence[bool]]) -> list[int]:
    """The objects with no chain of known pairs to object 0."""
    m = len(known)
    reached, frontier = {0}, [0]
    while frontier:
        i = frontier.pop()
        for j in range(m):
            if known[i][j] and j not in reached:
                reached.add(j)
                frontier.append(j)
    return sorted(set(range(m)) - reached)


def _heights(
    scaled: Sequence[Sequence[float | None]],
    weights: Sequence[float],
    columns: Sequence[int],
    slots: Slots = NO_SLOTS,
) -> ObjectHeights:
    """F8's height: each object's weighted mean rating on the declared 0-1 scale, over
    everyone who rated it (a person not placed rated it too). ``slots`` may replace the
    mean (``f8.height``) over the same raters."""
    replaced = slots.get(HEIGHT)
    values: list[float | None] = []
    support: list[int] = []
    for c in columns:
        rated = [(row[c], w) for row, w in zip(scaled, weights, strict=True) if row[c] is not None]
        total = math.fsum(w for _, w in rated)
        if rated and replaced is not None:
            values.append(
                float(
                    replaced(
                        a=tuple(v for v, _ in rated if v is not None),
                        w=tuple(w for _, w in rated),
                    )
                )
            )
            support.append(len(rated))
            continue
        values.append(
            math.fsum(v * w for v, w in rated if v is not None) / total if rated else None
        )
        support.append(len(rated))
    return ObjectHeights(
        metric=ObjectHeightMetric.MEAN_RATING_0_1.value,
        values=tuple(values),
        support_n=tuple(support),
    )


#: Every hill's relative height when the objects' heights do not differ: the signed-off
#: methodology stands them all at the middle.
EQUAL_RELATIVE_HEIGHT: Final = 0.5
#: Below this spread the heights do not differ (the methodology's own tie threshold).
_EQUAL_HEIGHTS: Final = 1e-15


def _relative_heights(
    values: Sequence[float | None], primary: Sequence[bool], floor: float
) -> tuple[float | None, ...]:
    """The framed envelope's hill heights: each PRIMARY object's height min-max scaled over
    the PRIMARY objects onto ``[floor, 1]``. An object nobody rated stands at the lowest rated
    height, and with none rated every object at 0; heights that do not differ all stand at
    :data:`EQUAL_RELATIVE_HEIGHT`. A SECONDARY object raises no hill and has none."""
    own = [v for v, p in zip(values, primary, strict=True) if p]
    rated = [v for v in own if v is not None]
    lowest = min(rated) if rated else 0.0
    filled = [lowest if v is None else v for v in own]
    lo, hi = (min(filled), max(filled)) if filled else (0.0, 0.0)
    out: list[float | None] = []
    for v, p in zip(values, primary, strict=True):
        if not p:
            out.append(None)
            continue
        h = lowest if v is None else v
        out.append(
            EQUAL_RELATIVE_HEIGHT
            if hi - lo < _EQUAL_HEIGHTS
            else floor + (1.0 - floor) * (h - lo) / (hi - lo)
        )
    return tuple(out)


def _terrain(
    spec: SociomapSpecV3,
    layout: ObjectMapLayout | None,
    heights: ObjectHeights,
    inputs: ObjectMapInputs,
    slots: Slots = NO_SLOTS,
) -> NotComputed | EnvelopeTerrain:
    """F12's envelope over the PRIMARY objects' hills, each exactly its F8 height.

    A SECONDARY object raises no hill (F8: context objects never enter terrain), and an
    object nobody rated has no height and so no hill -- not a hill of 0.

    The framed envelope stands each PRIMARY object's hill at its relative height (an object
    nobody rated at the lowest) on a grid framed on every placed object, so every object drawn
    stands on the grid, and lets every hill reach every cell.
    """
    declared = spec.terrain
    if declared is None:
        return TERRAIN_NOT_COMPUTED
    if layout is None:
        return TERRAIN_NOT_MAPPED
    if declared.method == TerrainMethod.FRAMED_RELATIVE_ENVELOPE:
        if declared.frame_fill is None or heights.relative is None:
            raise ValueError("the framed envelope is declared whole (require_supported)")
        centre, half = fit_frame(layout.points, declared.frame_fill)
        return object_envelope(
            [
                EnvelopeHill(entity_id=oid, x=point[0], y=point[1], height=t)
                for oid, point, t in zip(
                    inputs.object_ids, layout.points, heights.relative, strict=True
                )
                if t is not None
            ],
            EnvelopeParameters(
                grid_resolution=declared.grid_resolution,
                half_extent=half,
                sigma=declared.sigma,
                centre=centre,
            ),
            slots=slots,
            method="framed_relative_envelope",
        )
    if declared.half_extent is None or declared.kernel_cutoff is None:
        raise ValueError("the envelope is declared whole (require_supported)")
    hills = [
        EnvelopeHill(entity_id=oid, x=point[0], y=point[1], height=h)
        for oid, point, h in zip(inputs.object_ids, layout.points, heights.values, strict=True)
        if h is not None and inputs.roles[oid] == ObjectRole.PRIMARY.value
    ]
    return object_envelope(
        hills,
        EnvelopeParameters(
            grid_resolution=declared.grid_resolution,
            half_extent=declared.half_extent,
            sigma=declared.sigma,
            kernel_cutoff=declared.kernel_cutoff,
        ),
        slots=slots,
    )


def _support(
    inputs: ObjectMapInputs,
    not_placed: dict[str, str],
    weighting: str,
    slots: Slots = NO_SLOTS,
) -> ObjectMapSupport:
    placed = [k for k, rid in enumerate(inputs.respondent_ids) if rid not in not_placed]
    w = [inputs.weights[k] for k in placed]
    squares = math.fsum(x * x for x in w)
    replaced = slots.get(SUPPORT_EFFECTIVE_N)
    effective_n = math.fsum(w) ** 2 / squares if squares > 0 else None
    if effective_n is not None and replaced is not None:
        effective_n = float(replaced(w=tuple(w)))
    return ObjectMapSupport(
        respondents=len(inputs.respondent_ids),
        placed=len(placed),
        not_placed=len(not_placed),
        effective_n=effective_n,
        donors=len({inputs.donor_ids[k] for k in placed}),
        weighting=weighting,
    )


def _evidence_policy(spec: SociomapSpecV3) -> dict[str, Any]:
    """The pair evidence policy the spec declares (Q6, chunk 1d), as the pair keywords.

    A spec that declares neither Kish's n nor an effect floor is a spec pinned before the
    policy existed (``aia-sociomap-2``): its relations are computed and recorded exactly
    as they were, with nothing of the policy in them, so a stored map recomputes to the
    same body.
    """
    rel = spec.relation
    if rel.basis == PairEvidenceBasis.RESPONDENT_COUNT and rel.effect_floor is None:
        return {}
    return {"basis": rel.basis, "effect_floor": rel.effect_floor}


def _ratings(family: Sequence[Sequence[float | None]], m: int) -> NDArray[np.float64]:
    """The family's raw ratings as the methodology reads them: NaN where not rated."""
    return np.array(
        [[math.nan if v is None else v for v in row] for row in family], dtype=float
    ).reshape(len(family), m)


def _prepare(
    ratings: NDArray[np.float64], spec: SociomapSpecV3, *, noise_rule: bool = True
) -> PreparedInputs:
    """:func:`~.signed_off_inputs.prepare` under the spec; ``noise_rule`` false leaves the
    noise rule out whatever the spec declares, as the methodology's credibility maps do."""
    rel, layout = spec.relation, spec.layout
    noise = rel.noise_rule
    if (
        rel.false_discovery_rate is None
        or noise is None
        or layout.layout_floor is None
        or layout.sparse_share is None
        or layout.min_layout_partners is None
        or layout.layout_weight_full_at is None
        or layout.precision_weight_cap is None
    ):
        raise ValueError("the baseline-corrected relation is declared whole (require_supported)")
    return prepare(
        ratings,
        n_min=rel.n_min,
        layout_floor=layout.layout_floor,
        layout_weight_full_at=layout.layout_weight_full_at,
        false_discovery_rate=rel.false_discovery_rate,
        noise_rule=noise_rule and noise.enabled,
        noise_permutations=noise.permutations,
        noise_seed=noise.seed,
        precision_weight_cap=layout.precision_weight_cap,
        sparse_share=layout.sparse_share,
        min_layout_partners=layout.min_layout_partners,
    )


def _baseline_corrected(
    family: Sequence[Sequence[float | None]], ids: Sequence[str], spec: SociomapSpecV3
) -> tuple[PairRelations, list[int], SparseDesign, PreparedInputs]:
    """The signed-off methodology's relations (:func:`~.signed_off_inputs.prepare`) on the
    family's raw ratings, as the artifact records them: each known pair's ``r~`` and every
    pair's support ``n``; RELIABLE (Benjamini-Hochberg and the noise rule), WEAK (known, not
    reliable) or UNKNOWN (below the status floor or a column without spread: no ``r~``); no
    interval. Also the respondents centring leaves out, the sparse-design note and the layout
    inputs."""
    m = len(ids)
    prepared = _prepare(_ratings(family, m), spec)
    # Each pair read from its upper half: the methodology computes r~[i, j] and r~[j, i]
    # separately, so they can differ in the last bit, and the artifact holds one value a pair.
    upper = np.triu(np.ones((m, m), dtype=bool), 1)
    known = np.where(upper, prepared.known, prepared.known.T)
    reliable = np.where(upper, prepared.reliable, prepared.reliable.T)
    rt = np.where(upper, prepared.rt, prepared.rt.T)
    status = tuple(
        tuple(
            None
            if i == j
            else PairStatus.RELIABLE
            if reliable[i, j]
            else PairStatus.WEAK
            if known[i, j]
            else PairStatus.UNKNOWN
            for j in range(m)
        )
        for i in range(m)
    )
    pairs = PairRelations(
        r=tuple(
            tuple(float(rt[i, j]) if known[i, j] else None for j in range(m)) for i in range(m)
        ),
        n=tuple(
            tuple(None if i == j else int(prepared.n[i, j]) for j in range(m)) for i in range(m)
        ),
        interval=tuple(tuple(None for _ in range(m)) for _ in range(m)),
        status=status,
        n_min=spec.relation.n_min,
        confidence=spec.relation.confidence,
    )
    excluded = [k for k in range(len(family)) if not prepared.placed[k]]
    sparse = SparseDesign(
        flag=prepared.sparse.flag,
        share_below_layout_floor=prepared.sparse.share_below_layout_floor,
        weakly_connected=tuple(ids[k] for k in prepared.sparse.weakly_connected),
    )
    return pairs, excluded, sparse, prepared


def _primary_only(inputs: ObjectMapInputs) -> ObjectMapInputs:
    """``inputs`` with the context (SECONDARY) objects left out of the mapped objects."""
    keep = [
        k
        for k, oid in enumerate(inputs.object_ids)
        if inputs.roles[oid] == ObjectRole.PRIMARY.value
    ]
    if len(keep) == len(inputs.object_ids):
        return inputs
    ids = tuple(inputs.object_ids[k] for k in keep)
    return ObjectMapInputs.model_validate(
        inputs.model_dump()
        | {
            "object_ids": ids,
            "object_items": tuple(inputs.object_items[k] for k in keep),
            "roles": dict.fromkeys(ids, ObjectRole.PRIMARY.value),
        }
    )


def _signed_off_layout(
    prepared: PreparedInputs, ids: Sequence[str], spec: SociomapSpecV3
) -> ObjectMapLayout | NotMappable:
    """The signed-off methodology's positions: the fixed object-count rule picks soft-rank
    Spearman with Coulomb repulsion or Interval MDS on the layout pairs, and one uniform scale
    puts the map in ruler units. Stress-1 is not computed: it is SMACOF's measure, and the
    methodology judges a map by its split-half check. ``converged`` is whether the kept run
    stopped by its own rule before its cap. With no layout pair nothing places the objects:
    not mappable."""
    layout = spec.layout
    srs, imds, partners = layout.soft_rank_spearman, layout.interval_mds, layout.min_layout_partners
    if srs is None or imds is None or partners is None:
        raise ValueError("the signed-off layout is declared whole (require_supported)")
    m = len(ids)
    fitted = ~prepared.unknown_layout & ~np.eye(m, dtype=bool)
    if not fitted.any():
        return NotMappable(
            reason=NotMappableReason.NO_KNOWN_PAIR.value,
            message=(
                f"no pair reached the layout floor {layout.layout_floor}: every pair is masked, "
                "so nothing places the objects"
            ),
            objects=tuple(ids),
        )
    method = choose_method(m, srs.min_objects, srs.max_objects)
    if method is PositionMethod.SOFT_RANK_SPEARMAN_COULOMB:
        run = soft_rank_spearman(
            prepared,
            repulsion_weight=srs.repulsion_weight,
            seed=srs.seed,
            restarts_below_ten_objects=srs.restarts_below_ten_objects,
            restarts=srs.restarts,
            max_passes=srs.max_passes,
            min_partners=partners,
        )
        xy, iterations, converged = run.points, run.passes, run.passes < srs.max_passes
    else:
        xy, iterations = interval_mds(
            prepared, starts=imds.random_starts, kappa=imds.floor_fraction
        )
        converged = iterations < SMACOF_ITMAX
    ruler = to_ruler(xy, prepared.delta_layout, fitted)
    return ObjectMapLayout(
        points=tuple((float(x), float(y)) for x, y in ruler),
        extent=layout.map_frame.extent,
        known_pairs=int(fitted.sum()) // 2,
        iterations=iterations,
        converged=converged,
        start_fill=None,
        method=method.value,
    )


#: What the signed-off Interval MDS raises on too little data: ``ZeroDivisionError`` when no
#: pair reaches the layout floor, ``LinAlgError`` when the classical start of a near-empty
#: design does not converge. Any other error is a defect and propagates.
_TOO_LITTLE_DATA: Final = (ZeroDivisionError, np.linalg.LinAlgError)


def _credibility(
    family: Sequence[Sequence[float | None]], prepared: PreparedInputs, spec: SociomapSpecV3
) -> MapCredibility:
    """The signed-off methodology's map credibility, with the AIA panel's fallbacks. The
    split-half check decides whether the map is weakly determined; when it has no score (a
    half cannot be mapped, or two objects have no triplet) the map is weakly determined
    exactly when no pair is RELIABLE. The uncertainty radius is ``None`` when a bootstrap map
    cannot be computed. Every map here is Interval MDS of the input stage without the noise
    rule, on the family's raw ratings, as the methodology computes them."""
    cred, imds = spec.credibility, spec.layout.interval_mds
    if cred is None or imds is None:
        raise ValueError("the map credibility is declared whole (require_supported)")
    m = len(prepared.n)
    ratings = _ratings(family, m)

    def map_of(part: NDArray[np.float64]) -> NDArray[np.float64]:
        xy, _ = interval_mds(
            _prepare(part, spec, noise_rule=False),
            starts=imds.random_starts,
            kappa=imds.floor_fraction,
        )
        return xy

    try:
        score = split_half_agreement(
            ratings, splits=cred.split_half_splits, seed=cred.split_half_seed, map_of=map_of
        )
    except _TOO_LITTLE_DATA:
        score = math.nan
    reliable = int(prepared.reliable[np.triu_indices(m, 1)].sum())
    try:
        radius: float | None = map_uncertainty(
            ratings,
            resamples=cred.bootstrap_resamples,
            seed=cred.bootstrap_seed,
            safety=cred.safety_factor,
            map_of=map_of,
        ).radius
    except _TOO_LITTLE_DATA:
        radius = None
    finite = math.isfinite(score)
    return MapCredibility(
        rule=(CredibilityRule.SPLIT_HALF if finite else CredibilityRule.NO_RELIABLE_PAIR).value,
        split_half=score if finite else None,
        threshold=cred.split_half_threshold,
        weakly_determined=score < cred.split_half_threshold if finite else reliable == 0,
        reliable_pairs=reliable,
        # A reference map with every object on one point has no distance to measure by.
        uncertainty_radius=radius if radius is not None and math.isfinite(radius) else None,
    )


def compute_object_map(
    inputs: ObjectMapInputs,
    spec: SociomapSpecV3,
    *,
    connectedness_interval: bool,
    slots: Slots = NO_SLOTS,
) -> SociomapArtifactV3:
    """The audit's object map of ``inputs.object_ids`` under ``spec``. See the module.

    ``slots`` are the formulas a methodology version replaces (ADR 0023, ``slots.py``),
    each computed where the code's formula would be; with none, the code computes every
    one, bit for bit as before.
    """
    require_supported(spec)
    if spec.relation.estimator == RelationEstimator.BASELINE_CORRECTED_PEARSON:
        # The signed-off methodology maps a set's PRIMARY objects only, as the AIA panel
        # shows them; how context objects join its map is an open question.
        inputs = _primary_only(inputs)
    scaled = _scaled(inputs, slots)
    columns = inputs.object_columns()
    weights = list(inputs.weights)
    evidence = spec.relation
    ids = list(inputs.object_ids)
    m = len(ids)
    sparse: SparseDesign | None = None
    prepared: PreparedInputs | None = None
    corrected = evidence.estimator == RelationEstimator.BASELINE_CORRECTED_PEARSON
    if corrected and (unread := [s for s in _UNREAD_BY_BASELINE_CORRECTED if s in slots]):
        raise UnsupportedMethodology(
            dict.fromkeys(
                unread,
                "the baseline-corrected relation and its layout do not read this formula; "
                "remove it",
            )
        )
    if corrected:
        # The signed-off methodology reads the raw ratings of the mapped objects, unweighted.
        family = [[row[c] for c in columns] for row in inputs.values]
        policy: dict[str, Any] = {}
        pairs, excluded, sparse, prepared = _baseline_corrected(family, ids, spec)
        not_placed = {inputs.respondent_ids[k]: NOT_PLACED_NO_SPREAD_OBJECTS for k in excluded}
    else:
        person = person_minmax(scaled, slots=slots)
        not_placed = {inputs.respondent_ids[k]: NOT_PLACED_NO_SPREAD for k in person.excluded}
        family = [[row[c] for c in columns] for row in person.values]
        policy = _evidence_policy(spec)
        pairs = derive_pair_relations(
            family,
            weights,
            n_min=evidence.n_min,
            confidence=evidence.confidence,
            slots=slots,
            **policy,
        )
    known = [
        [i != j and pairs.status[i][j] in (PairStatus.RELIABLE, PairStatus.WEAK) for j in range(m)]
        for i in range(m)
    ]

    not_mappable: NotMappable | None = None
    layout: ObjectMapLayout | None = None
    credibility: MapCredibility | None = None
    declared = spec.layout.min_objects
    min_objects = LEGACY_MIN_OBJECTS if declared is None else declared
    if m < min_objects:
        needed = "three" if min_objects == LEGACY_MIN_OBJECTS else str(min_objects)
        not_mappable = NotMappable(
            reason=NotMappableReason.TOO_FEW_OBJECTS.value,
            message=f"an object map needs at least {needed} objects; the family has {m}",
            objects=tuple(ids),
        )
    elif prepared is not None:
        # The signed-off layout places every object, related or not: no known-pair check.
        placed = _signed_off_layout(prepared, ids, spec)
        if isinstance(placed, NotMappable):
            not_mappable = placed
        else:
            layout = placed
            credibility = _credibility(family, prepared, spec)
    elif not any(any(row) for row in known):
        not_mappable = NotMappable(
            reason=NotMappableReason.NO_KNOWN_PAIR.value,
            message=(
                f"no pair reached RELIABLE or WEAK at n_min {evidence.n_min}: every pair is "
                "UNKNOWN, so nothing places the objects"
            ),
            objects=tuple(ids),
        )
    elif unreached := _unreached(known):
        not_mappable = NotMappable(
            reason=NotMappableReason.DISCONNECTED.value,
            message=(
                "these objects have no chain of RELIABLE or WEAK pairs to the rest and "
                "cannot be placed on the same map"
            ),
            objects=tuple(ids[k] for k in unreached),
        )
    else:
        delta = correlation_distances(pairs.r, known, slots=slots)
        try:
            fit = fit_smacof_objects(
                delta,
                max_iterations=spec.layout.max_iterations,
                tolerance=spec.layout.tolerance,
            )
        except UnfoldingDesignError as exc:
            not_mappable = NotMappable(
                reason=NotMappableReason.SINGULAR.value, message=str(exc), objects=tuple(ids)
            )
        else:
            stress_1 = fit.stress_1
            if (replaced_stress := slots.get(STRESS_1)) is not None:
                d, t = stress_terms(fit.points, delta)
                stress_1 = float(replaced_stress(d=d, delta=t))
            layout = ObjectMapLayout(
                points=fit.points,
                extent=spec.layout.map_frame.extent,
                stress_1=stress_1,
                raw_stress=fit.raw_stress,
                quality=stress_quality(stress_1, spec.layout.stress_bands).value,
                known_pairs=fit.known_pairs,
                iterations=fit.iterations,
                converged=fit.converged,
                start_fill=fit.start_fill,
            )

    scores = primary_scores(ids, pairs.r, pairs.status, inputs.roles, slots=slots)
    heights = _heights(scaled, weights, columns, slots)
    terrain = spec.terrain
    if layout is not None and terrain is not None and terrain.relative_height_floor is not None:
        heights = heights.model_copy(
            update={
                "relative": _relative_heights(
                    heights.values,
                    [inputs.roles[oid] == ObjectRole.PRIMARY.value for oid in ids],
                    terrain.relative_height_floor,
                )
            }
        )

    connectedness: dict[str, Any] = dict(
        CONNECTEDNESS_NOT_IN_METHOD if corrected else CONNECTEDNESS_OFF
    )
    if connectedness_interval and not corrected:

        def correlate(
            multiplicities: Sequence[int],
        ) -> tuple[tuple[tuple[float | None, ...], ...], tuple[tuple[PairStatus | None, ...], ...]]:
            # A resample: each person's scaled row taken as many times as drawn, as a weight
            # multiple. Rows are scaled once: each person's min-max is their own (F2).
            # Kish's n reads the design weights of the distinct people drawn, never the
            # multiplicities: a duplicated row is the same person, not less evidence.
            drawn = derive_pair_relations(
                family,
                [k * w for k, w in zip(multiplicities, weights, strict=True)],
                n_min=evidence.n_min,
                confidence=evidence.confidence,
                design_weights=weights,
                slots=slots,
                **policy,
            )
            return drawn.r, drawn.status

        k100 = connectedness_100(
            ids,
            inputs.roles,
            correlate,
            respondents=len(family),
            resamples=spec.connectedness.resamples,
            seed=spec.connectedness.seed,
            slots=slots,
            **(
                {}
                if spec.connectedness.quantiles is None
                else {"quantiles": spec.connectedness.quantiles}
            ),
        )
        connectedness = {
            "status": "computed",
            **k100.to_payload(),
            "ranking": rank_with_ties(k100.intervals()).to_payload(),
        }

    return SociomapArtifactV3(
        spec=spec,
        respondent_ids=inputs.respondent_ids,
        object_ids=inputs.object_ids,
        object_items=inputs.object_items,
        roles=dict(inputs.roles),
        items=inputs.items,
        not_placed=not_placed,
        relations=pairs,
        abs_r=tuple(tuple(None if v is None else abs(v) for v in row) for row in pairs.r),
        status_counts=pairs.counts(),
        outcome=(MapOutcome.MAPPED if layout is not None else MapOutcome.NOT_MAPPABLE).value,
        not_mappable=not_mappable,
        layout=layout,
        scores=scores.to_payload(),
        heights=heights,
        connectedness_100=connectedness,
        support=_support(
            inputs,
            not_placed,
            WEIGHTING_UNWEIGHTED
            if corrected
            else WEIGHTING_KISH
            if evidence.basis == PairEvidenceBasis.KISH_EFFECTIVE_N
            else WEIGHTING,
            slots,
        ),
        respondents=RESPONDENTS_NOT_COMPUTED,
        terrain=_terrain(spec, layout, heights, inputs, slots),
        provenance=ObjectMapProvenance(
            implementation=OBJECT_MAP_IMPLEMENTATION,
            implementation_version=OBJECT_MAP_IMPLEMENTATION_VERSION,
            input_fingerprints=inputs.fingerprints(),
        ),
        sparse_design=sparse,
        credibility=credibility,
    )
