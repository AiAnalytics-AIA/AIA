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
    F12  the envelope terrain over the PRIMARY hills, when the spec declares one (4b)

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
)
from .pairs import derive_pair_relations
from .relations import PairStatus, person_minmax
from .slots import HEIGHT, NO_SLOTS, SCALE, STRESS_1, SUPPORT_EFFECTIVE_N, Slots
from .specification import (
    LEGACY_MIN_OBJECTS,
    ObjectHeightMetric,
    PairEvidenceBasis,
    SociomapSpecV3,
    require_supported,
)
from .terrain import EnvelopeHill, EnvelopeParameters, EnvelopeTerrain, object_envelope
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
    """
    declared = spec.terrain
    if declared is None:
        return TERRAIN_NOT_COMPUTED
    if layout is None:
        return TERRAIN_NOT_MAPPED
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
    scaled = _scaled(inputs, slots)
    person = person_minmax(scaled, slots=slots)
    not_placed = {inputs.respondent_ids[k]: NOT_PLACED_NO_SPREAD for k in person.excluded}
    columns = inputs.object_columns()
    family = [[row[c] for c in columns] for row in person.values]
    weights = list(inputs.weights)
    evidence = spec.relation
    policy = _evidence_policy(spec)
    pairs = derive_pair_relations(
        family,
        weights,
        n_min=evidence.n_min,
        confidence=evidence.confidence,
        slots=slots,
        **policy,
    )
    ids = list(inputs.object_ids)
    m = len(ids)
    known = [
        [i != j and pairs.status[i][j] in (PairStatus.RELIABLE, PairStatus.WEAK) for j in range(m)]
        for i in range(m)
    ]

    not_mappable: NotMappable | None = None
    layout: ObjectMapLayout | None = None
    declared = spec.layout.min_objects
    min_objects = LEGACY_MIN_OBJECTS if declared is None else declared
    if m < min_objects:
        needed = "three" if min_objects == LEGACY_MIN_OBJECTS else str(min_objects)
        not_mappable = NotMappable(
            reason=NotMappableReason.TOO_FEW_OBJECTS.value,
            message=f"an object map needs at least {needed} objects; the family has {m}",
            objects=tuple(ids),
        )
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

    connectedness: dict[str, Any] = dict(CONNECTEDNESS_OFF)
    if connectedness_interval:

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
            WEIGHTING_KISH if evidence.basis == PairEvidenceBasis.KISH_EFFECTIVE_N else WEIGHTING,
            slots,
        ),
        respondents=RESPONDENTS_NOT_COMPUTED,
        terrain=_terrain(spec, layout, heights, inputs, slots),
        provenance=ObjectMapProvenance(
            implementation=OBJECT_MAP_IMPLEMENTATION,
            implementation_version=OBJECT_MAP_IMPLEMENTATION_VERSION,
            input_fingerprints=inputs.fingerprints(),
        ),
    )
