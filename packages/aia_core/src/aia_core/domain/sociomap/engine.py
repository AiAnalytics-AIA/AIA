"""``compute_sociomap``: inputs + spec -> one deterministic :class:`SociomapArtifact`.

The single entry point for Sociomapping research computation. Order of work::

    require_supported(spec)                        fail closed before any number
    ratings   -> range check -> placeable rows -> dissimilarities
              -> declared layout -> gauge-fixed coordinates -> map frame
    relation  -> missing policy -> coerce 1-10 (directed) -> mutual projection
    metrics   -> mean_rating, support_n [, relation_classic, T-score]
    terrain   -> respondent density   over placed respondents
              -> object weighted mean over objects, for the spec's height metric

Pure: no I/O, no clock, no randomness, no environment lookup. Identical inputs
and spec give an identical artifact, bit for bit, on any host.

Two things the engine will not do, because each would stamp a guess:

* **place a respondent it has no position information for.** A respondent with
  fewer than two ratings, or who put every object at the top of the scale, is
  listed in ``excluded_respondents`` with the reason and left off the map. They
  still count towards ``mean_rating`` and ``support_n`` -- their ratings are real.
* **fill a missing relation cell** unless the spec explicitly declares the
  reference's midpoint sentinel.
"""

from __future__ import annotations

import math

from .layout import (
    LayoutAlgorithm,
    UnfoldingParameters,
    fit_rowcond_unfolding,
    require_layout_algorithm,
    scale_top_dissimilarity,
)
from .metrics import (
    NormalizationMode,
    ObjectMetric,
    bounds_for,
    object_metric,
    object_rating_summaries,
)
from .models import (
    LayoutResult,
    MetricValues,
    Provenance,
    RatingsMatrix,
    RelationDerivation,
    RelationMatrix,
    SociomapArtifact,
    SociomapInputs,
)
from .relations import coerce_relation_scale_1_10, coercion_branch, mutual_relation_for_position
from .specification import RelationMissingPolicy, SociomapSpec, require_supported
from .terrain import TerrainField, TerrainMode, TerrainParameters, TerrainSource, compute_terrain

__all__ = [
    "SociomapInputError",
    "compute_sociomap",
    "object_terrain",
    "respondent_terrain",
]

RESPONDENT_DENSITY_METRIC = "density"


class SociomapInputError(ValueError):
    """The inputs do not satisfy the spec (a rating off the scale, a missing relation cell)."""


def _placeability(ratings: RatingsMatrix, scale_top: float) -> dict[str, str]:
    excluded: dict[str, str] = {}
    for rid, row in zip(ratings.respondent_ids, ratings.values, strict=True):
        observed = [v for v in row if v is not None]
        if len(observed) < 2:
            excluded[rid] = f"rated {len(observed)} object(s); a position needs at least 2"
        elif all(v == scale_top for v in observed):
            excluded[rid] = (
                "rated every object at the top of the scale; no object is nearer than "
                "another, so there is no position to recover"
            )
    return excluded


def _check_scale(ratings: RatingsMatrix, lo: float, hi: float) -> None:
    for rid, row in zip(ratings.respondent_ids, ratings.values, strict=True):
        for oid, v in zip(ratings.object_ids, row, strict=True):
            if v is not None and not lo <= v <= hi:
                raise SociomapInputError(
                    f"rating {rid!r} -> {oid!r} = {v!r} is outside the declared scale "
                    f"[{lo}, {hi}]; it is refused, not clipped"
                )


def _derive_relation(matrix: RelationMatrix, policy: RelationMissingPolicy) -> RelationDerivation:
    raw: list[list[float]] = []
    substituted: list[tuple[str, str]] = []
    ids = matrix.entity_ids
    for i, row in enumerate(matrix.values):
        cells: list[float] = []
        for j, v in enumerate(row):
            if v is not None:
                cells.append(v)
            elif i == j:
                cells.append(0.0)  # forced to 0 by coercion either way
            elif policy is RelationMissingPolicy.REFERENCE_MIDPOINT_SENTINEL:
                cells.append(math.nan)  # coerced to the reference's 5.5 sentinel
                substituted.append((ids[i], ids[j]))
            else:
                raise SociomapInputError(
                    f"relation {ids[i]!r} -> {ids[j]!r} is missing and the spec's policy is "
                    "'refuse'; declare 'reference_midpoint_sentinel' to use the reference's "
                    "5.5 substitution instead"
                )
        raw.append(cells)
    return RelationDerivation(
        coercion_branch=coercion_branch(raw).value,
        coerced=RelationMatrix(entity_ids=ids, values=coerce_relation_scale_1_10(raw)),
        position_input=RelationMatrix(entity_ids=ids, values=mutual_relation_for_position(raw)),
        substituted_cells=tuple(substituted),
    )


def _object_metrics(
    ratings: RatingsMatrix, relation: RelationDerivation | None
) -> dict[str, MetricValues]:
    means, support = object_rating_summaries(ratings.values)
    coerced = None
    if relation is not None:
        coerced = [[v if v is not None else 0.0 for v in row] for row in relation.coerced.values]
    out: dict[str, MetricValues] = {}
    for metric in ObjectMetric:
        if coerced is None and metric in (
            ObjectMetric.RELATION_CLASSIC,
            ObjectMetric.RELATION_CLASSIC_TSCORE,
        ):
            continue
        values = object_metric(metric, mean_rating=means, support_n=support, relation=coerced)
        out[metric.value] = MetricValues(metric_id=metric.value, values=values)
    return out


def respondent_terrain(
    respondent_ids: tuple[str, ...],
    positions: tuple[tuple[float, float], ...],
    params: TerrainParameters,
    normalization: NormalizationMode,
) -> TerrainField:
    """Respondent density terrain: every placed respondent contributes ``h = c = 1``."""
    sources = [
        TerrainSource(entity_id=rid, x=x, y=y, height=1.0, colour=1.0)
        for rid, (x, y) in zip(respondent_ids, positions, strict=True)
    ]
    return compute_terrain(
        TerrainMode.RESPONDENT_DENSITY,
        sources,
        params,
        metric_id=RESPONDENT_DENSITY_METRIC,
        normalization=normalization,
        bounds=bounds_for(RESPONDENT_DENSITY_METRIC, normalization),
    )


def object_terrain(
    object_ids: tuple[str, ...],
    positions: tuple[tuple[float, float], ...],
    height: MetricValues,
    colour: MetricValues,
    params: TerrainParameters,
    normalization: NormalizationMode,
    *,
    rating_scale: tuple[float, float],
) -> TerrainField:
    """Object metric terrain: kernel-weighted mean of the height metric.

    An object whose height or colour value is missing contributes nothing -- an
    unknown value cannot be averaged -- and is absent from ``source_ids``.
    ``rating_scale`` is the spec's declared scale; it bounds ``mean_rating``
    under absolute normalisation.
    """
    sources = [
        TerrainSource(entity_id=oid, x=x, y=y, height=h, colour=c)
        for oid, (x, y), h, c in zip(
            object_ids, positions, height.values, colour.values, strict=True
        )
        if h is not None and c is not None
    ]
    return compute_terrain(
        TerrainMode.OBJECT_METRIC,
        sources,
        params,
        metric_id=height.metric_id,
        normalization=normalization,
        bounds=bounds_for(height.metric_id, normalization, rating_scale=rating_scale),
    )


def compute_sociomap(inputs: SociomapInputs, spec: SociomapSpec) -> SociomapArtifact:
    """Compute the Sociomap ``spec`` describes over ``inputs``.

    Raises :class:`~.specification.UnsupportedMethodology` for a spec the engine
    cannot run, :class:`SociomapInputError` for inputs the spec rejects, and
    :class:`~.layout.UnfoldingDesignError` for a design that cannot be placed.
    """
    require_supported(spec)
    if spec.relation is not None and inputs.object_relation is None:
        raise SociomapInputError("the spec declares a relation matrix but none was supplied")
    if spec.relation is None and inputs.object_relation is not None:
        raise SociomapInputError(
            "a relation matrix was supplied but the spec declares none; an input the "
            "methodology does not use would be silently ignored"
        )

    ratings = inputs.ratings
    top = spec.ratings.rating_scale_max
    _check_scale(ratings, spec.ratings.rating_scale_min, top)
    excluded = _placeability(ratings, top)
    placed = tuple(r for r in ratings.respondent_ids if r not in excluded)
    placed_rows = [
        row
        for rid, row in zip(ratings.respondent_ids, ratings.values, strict=True)
        if rid not in excluded
    ]

    algorithm = require_layout_algorithm(spec.layout.algorithm)
    if algorithm is not LayoutAlgorithm.AIA_ROWCOND_UNFOLDING_V1:  # pragma: no cover
        raise AssertionError(f"require_supported admitted unimplemented {algorithm}")
    params = UnfoldingParameters.model_validate(spec.layout.parameters)
    fit = fit_rowcond_unfolding(scale_top_dissimilarity(placed_rows, top), params)

    extent = spec.layout.map_frame.extent
    reach = max(abs(c) for p in (*fit.respondent_xy, *fit.object_xy) for c in p)
    if reach == 0:
        raise SociomapInputError("the layout collapsed to a single point; nothing to map")
    scale = extent / reach
    respondent_xy = tuple((scale * x, scale * y) for x, y in fit.respondent_xy)
    object_xy = tuple((scale * x, scale * y) for x, y in fit.object_xy)

    relation = None
    if spec.relation is not None and inputs.object_relation is not None:
        relation = _derive_relation(
            inputs.object_relation, RelationMissingPolicy(spec.relation.missing_data_policy)
        )
    metrics = _object_metrics(ratings, relation)
    normalization = NormalizationMode(spec.terrain.normalization)

    warnings: list[str] = []
    if excluded:
        warnings.append(
            f"{len(excluded)} respondent(s) excluded from the map; see excluded_respondents"
        )
    if not fit.converged:
        warnings.append(
            f"layout stopped at max_iterations={params.max_iterations} before converging"
        )
    if relation is not None and relation.substituted_cells:
        warnings.append(
            f"{len(relation.substituted_cells)} missing relation cell(s) set to the reference's "
            "5.5 midpoint sentinel, as the spec declares"
        )

    obj_terrain = object_terrain(
        ratings.object_ids,
        object_xy,
        metrics[spec.metrics.object_height_metric],
        metrics[spec.metrics.object_colour_metric],
        spec.terrain.object,
        normalization,
        rating_scale=(spec.ratings.rating_scale_min, spec.ratings.rating_scale_max),
    )
    missing_sources = len(ratings.object_ids) - len(obj_terrain.source_ids)
    if missing_sources:
        warnings.append(
            f"{missing_sources} object(s) have no {spec.metrics.object_height_metric} value and "
            "do not shape the object terrain"
        )

    return SociomapArtifact(
        spec=spec,
        respondent_ids=ratings.respondent_ids,
        object_ids=ratings.object_ids,
        excluded_respondents=excluded,
        layout=LayoutResult(
            algorithm=algorithm.value,
            gauge_fixed=True,
            respondent_ids=placed,
            respondent_xy=respondent_xy,
            object_xy=object_xy,
            layout_to_map_scale=scale,
            stress_1=fit.stress_1,
            normalized_stress=fit.normalized_stress,
            iterations=fit.iterations,
            converged=fit.converged,
            diagnostics={
                "principal_axis_gap": fit.principal_axis_gap,
                "row_scales": list(fit.row_scales),
            },
        ),
        relation=relation,
        object_metrics=metrics,
        respondent_terrain=respondent_terrain(
            placed, respondent_xy, spec.terrain.respondent, normalization
        ),
        object_terrain=obj_terrain,
        provenance=Provenance(
            input_fingerprints=inputs.fingerprints(),
            layout_algorithm=algorithm.value,
            seed=spec.layout.seed,
        ),
        warnings=tuple(warnings),
    )
