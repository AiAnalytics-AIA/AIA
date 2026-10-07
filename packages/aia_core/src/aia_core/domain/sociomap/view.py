"""Presentation and exploration layers over an immutable Sociomap artifact.

Two product rules are implemented here as types rather than as discipline:

* **Manual drag is a view override** (fixture F9). ``PRODUCT_POLICY.json`` in the
  reference states ``manual_drag: visual_override_only_never_mutates_raw_results``,
  and ``manualPerson66`` returns the dragged coordinate without touching the
  underlying point. A :class:`ViewOverrides` is bound to one artifact by
  fingerprint and produces a :class:`DisplayedMap`; the artifact is never
  written. As in the reference -- where manual state is part of the terrain
  cache key -- a dragged map may redraw its terrain: :func:`view_terrain`
  computes it over the *displayed* positions and returns it as a view product.
  It is never stored on, or mistaken for, the artifact's terrain.
* **What-if is a scenario layer over immutable originals.** The reference's
  ``effectiveMatrix66`` returns the original matrix unless the source mode is
  ``scenario`` *and* edits exist, in which case ``edits["i:j"]`` overrides cell
  ``(i, j)`` with the diagonal held at ``0``. :func:`apply_scenario` does exactly
  that to the artifact's coerced relation matrix, recomputes what depends on it
  -- relation metrics and, when the height metric is relation-derived, the
  object terrain -- and returns a :class:`ScenarioResult` naming its base.
  Positions come from the ratings unfolding, which a relation edit does not
  touch, so a scenario moves no point.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..pipeline import fingerprint
from .engine import object_terrain, respondent_terrain
from .metrics import NormalizationMode, ObjectMetric, object_metric
from .models import MetricValues, RelationMatrix, SociomapArtifact
from .terrain import TerrainField

__all__ = [
    "STRESS_QUALITY_BANDS",
    "STRESS_QUALITY_TEXT",
    "AlignedObjects",
    "DisplayedMap",
    "Position",
    "RelationEdit",
    "ScenarioLayer",
    "ScenarioResult",
    "StressQuality",
    "ViewOverrideMismatch",
    "ViewOverrides",
    "align_to_reference",
    "apply_scenario",
    "apply_view_overrides",
    "stress_quality",
    "view_terrain",
]

Point = tuple[float, float]


class ViewOverrideMismatch(ValueError):
    """An override or scenario does not belong to the artifact it was applied to."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Position(_Frozen):
    """A displayed 2-D position, in map-frame units."""

    x: float
    y: float

    @field_validator("x", "y", mode="before")
    @classmethod
    def _not_boolean(cls, v: object) -> object:
        if isinstance(v, bool):
            raise ValueError("positions must be numbers, not booleans")
        return v

    @field_validator("x", "y")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("positions must be finite")
        return float(v)


class ViewOverrides(_Frozen):
    """Dragged display positions, bound to one artifact.

    Mirrors the reference's ``st.manual = {respondents: {...}, objects: {...}}``.
    Binding by ``artifact_fingerprint`` stops an override recorded against one
    computation being shown over another: if anything upstream changes, the
    fingerprint changes and the stale drag state is refused.
    """

    artifact_fingerprint: str
    respondents: dict[str, Position] = Field(default_factory=dict)
    objects: dict[str, Position] = Field(default_factory=dict)

    @field_validator("artifact_fingerprint")
    @classmethod
    def _bound(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("overrides must be bound to an artifact fingerprint")
        return v

    def moving_respondent(self, respondent_id: str, x: float, y: float) -> ViewOverrides:
        """Overrides with one respondent dragged; the receiver is unchanged."""
        return self.model_copy(
            update={"respondents": {**self.respondents, respondent_id: Position(x=x, y=y)}}
        )

    def moving_object(self, object_id: str, x: float, y: float) -> ViewOverrides:
        """Overrides with one object dragged; the receiver is unchanged."""
        return self.model_copy(update={"objects": {**self.objects, object_id: Position(x=x, y=y)}})

    def reset(self, entity_id: str) -> ViewOverrides:
        """Overrides with one entity returned to its canonical position."""
        return self.model_copy(
            update={
                "respondents": {k: v for k, v in self.respondents.items() if k != entity_id},
                "objects": {k: v for k, v in self.objects.items() if k != entity_id},
            }
        )

    def key(self) -> str:
        """Fingerprint of the view state; part of :meth:`DisplayedMap.view_key`."""
        return fingerprint(self.model_dump(mode="json"))


class DisplayedMap(_Frozen):
    """What a renderer draws: canonical positions with overrides applied.

    Carries the artifact fingerprint so the display can always be traced to the
    research truth it departs from, and lists what was moved so the departure is
    visible rather than silent.
    """

    artifact_fingerprint: str
    overrides_key: str
    respondent_ids: tuple[str, ...]
    respondent_xy: tuple[Point, ...]
    object_ids: tuple[str, ...]
    object_xy: tuple[Point, ...]
    moved_respondents: tuple[str, ...]
    moved_objects: tuple[str, ...]

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        if len(self.respondent_xy) != len(self.respondent_ids) or len(self.object_xy) != len(
            self.object_ids
        ):
            raise ValueError("displayed positions must align with their ids")
        return self

    def view_key(self) -> str:
        """The invalidation key for anything drawn from this view.

        The backend counterpart of the reference's terrain cache key: it changes
        when the artifact or the manual state changes, and on nothing else.
        """
        return fingerprint({"artifact": self.artifact_fingerprint, "view": self.overrides_key})


def apply_view_overrides(artifact: SociomapArtifact, overrides: ViewOverrides) -> DisplayedMap:
    """Layer dragged positions over the canonical layout (``personPos66``, F9).

    Pure: returns a new :class:`DisplayedMap`. Raises :class:`ViewOverrideMismatch`
    when the overrides are bound to another artifact or name an unknown or
    unplaced entity.
    """
    fp = artifact.fingerprint()
    if overrides.artifact_fingerprint != fp:
        raise ViewOverrideMismatch(
            "view overrides are bound to a different artifact; canonical results "
            "changed, so the stale drag state is refused rather than shown"
        )
    placed = artifact.layout.respondent_ids
    unknown = sorted(set(overrides.respondents) - set(placed)) + sorted(
        set(overrides.objects) - set(artifact.object_ids)
    )
    if unknown:
        raise ViewOverrideMismatch(f"overrides name entities not placed on this map: {unknown}")

    def place(
        ids: tuple[str, ...], base: tuple[Point, ...], moved: dict[str, Position]
    ) -> tuple[tuple[Point, ...], tuple[str, ...]]:
        xy = tuple(
            (moved[i].x, moved[i].y) if i in moved else p for i, p in zip(ids, base, strict=True)
        )
        return xy, tuple(i for i in ids if i in moved)

    r_xy, r_moved = place(placed, artifact.layout.respondent_xy, overrides.respondents)
    o_xy, o_moved = place(artifact.object_ids, artifact.layout.object_xy, overrides.objects)
    return DisplayedMap(
        artifact_fingerprint=fp,
        overrides_key=overrides.key(),
        respondent_ids=placed,
        respondent_xy=r_xy,
        object_ids=artifact.object_ids,
        object_xy=o_xy,
        moved_respondents=r_moved,
        moved_objects=o_moved,
    )


def view_terrain(
    artifact: SociomapArtifact,
    displayed: DisplayedMap,
    *,
    mode: str,
    respondent_subset: tuple[str, ...] | None = None,
    height_metric: str | None = None,
) -> TerrainField:
    """Terrain over the *displayed* positions -- a view product, never research truth.

    ``mode`` is ``respondent_density`` or ``object_metric``. ``respondent_subset``
    is the reference's ``terrainScope == 'filter'``: density over a subset only.
    ``height_metric`` redraws the object terrain for another metric without
    moving a point. Parameters and normaliser are the artifact spec's.
    """
    if displayed.artifact_fingerprint != artifact.fingerprint():
        raise ViewOverrideMismatch("displayed map belongs to a different artifact")
    spec = artifact.spec
    normalization = NormalizationMode(spec.terrain.normalization)
    if mode == "respondent_density":
        chosen = displayed.respondent_ids
        if respondent_subset is not None:
            unknown = sorted(set(respondent_subset) - set(chosen))
            if unknown:
                raise ViewOverrideMismatch(f"subset names respondents not on this map: {unknown}")
            keep = set(respondent_subset)
            chosen = tuple(r for r in chosen if r in keep)
        index = {r: i for i, r in enumerate(displayed.respondent_ids)}
        return respondent_terrain(
            chosen,
            tuple(displayed.respondent_xy[index[r]] for r in chosen),
            spec.terrain.respondent,
            normalization,
        )
    if mode == "object_metric":
        # Redrawing for another metric colours by that metric too; otherwise the
        # spec's height and colour metrics apply.
        height = height_metric or spec.metrics.object_height_metric
        colour = height_metric or spec.metrics.object_colour_metric
        for metric in (height, colour):
            if metric not in artifact.object_metrics:
                raise ViewOverrideMismatch(f"metric {metric!r} is not available on this artifact")
        return object_terrain(
            displayed.object_ids,
            displayed.object_xy,
            artifact.object_metrics[height],
            artifact.object_metrics[colour],
            spec.terrain.object,
            normalization,
            rating_scale=(spec.ratings.rating_scale_min, spec.ratings.rating_scale_max),
        )
    raise ValueError(f"unknown terrain mode {mode!r}")


# ------------------------------------------------------------ scenarios --


class RelationEdit(_Frozen):
    """One hypothetical relation, ``source -> target = value`` on the coerced 1-10 scale."""

    source: str
    target: str
    value: float

    @field_validator("value", mode="before")
    @classmethod
    def _not_boolean(cls, v: object) -> object:
        if isinstance(v, bool):
            raise ValueError("a scenario relation must be a number, not a boolean")
        return v

    @field_validator("value")
    @classmethod
    def _on_scale(cls, v: float) -> float:
        if not (math.isfinite(v) and 1.0 <= v <= 10.0):
            raise ValueError("a scenario relation must be on the coerced 1-10 scale")
        return float(v)

    @model_validator(mode="after")
    def _off_diagonal(self) -> Self:
        if self.source == self.target:
            raise ValueError(
                "the diagonal is held at 0 in a scenario; an edit to it would be silently "
                "ignored, so it is refused"
            )
        return self


class ScenarioLayer(_Frozen):
    """A hypothesis: edits to an immutable base artifact's relation matrix."""

    base_artifact_fingerprint: str
    edits: tuple[RelationEdit, ...]
    label: str = ""

    @field_validator("base_artifact_fingerprint")
    @classmethod
    def _bound(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("a scenario must name its base artifact")
        return v

    @field_validator("edits")
    @classmethod
    def _non_empty(cls, v: tuple[RelationEdit, ...]) -> tuple[RelationEdit, ...]:
        if not v:
            raise ValueError("a scenario with no edits is the base itself")
        pairs = [(e.source, e.target) for e in v]
        if len(set(pairs)) != len(pairs):
            raise ValueError("a scenario may edit each relation cell once")
        return v


class ScenarioResult(_Frozen):
    """What a scenario changes: the effective matrix, relation metrics, object terrain.

    ``base_artifact_fingerprint`` is the lineage. Positions are not here because a
    relation edit does not move any: they are the base artifact's.
    """

    base_artifact_fingerprint: str
    layer: ScenarioLayer
    effective_relation: RelationMatrix
    object_metrics: dict[str, MetricValues]
    object_terrain: TerrainField

    def fingerprint(self) -> str:
        """Stable SHA256 of the scenario result."""
        return fingerprint(self.model_dump(mode="json"))


def apply_scenario(artifact: SociomapArtifact, layer: ScenarioLayer) -> ScenarioResult:
    """``effectiveMatrix66`` in scenario mode, and everything that reads it.

    The base artifact is read only.
    """
    if layer.base_artifact_fingerprint != artifact.fingerprint():
        raise ViewOverrideMismatch("scenario is bound to a different base artifact")
    if artifact.relation is None:
        raise ViewOverrideMismatch("this artifact has no relation matrix to build a scenario on")
    base = artifact.relation.coerced
    try:
        effective = base.with_cells({(e.source, e.target): e.value for e in layer.edits})
    except KeyError as exc:
        raise ViewOverrideMismatch(
            f"scenario edit names an unknown object {exc.args[0]!r}"
        ) from None

    matrix = [[v if v is not None else 0.0 for v in row] for row in effective.values]
    metrics = dict(artifact.object_metrics)
    for metric in (ObjectMetric.RELATION_CLASSIC, ObjectMetric.RELATION_CLASSIC_TSCORE):
        metrics[metric.value] = MetricValues(
            metric_id=metric.value, values=object_metric(metric, relation=matrix)
        )
    spec = artifact.spec
    terrain = object_terrain(
        artifact.object_ids,
        artifact.layout.object_xy,
        metrics[spec.metrics.object_height_metric],
        metrics[spec.metrics.object_colour_metric],
        spec.terrain.object,
        NormalizationMode(spec.terrain.normalization),
        rating_scale=(spec.ratings.rating_scale_min, spec.ratings.rating_scale_max),
    )
    return ScenarioResult(
        base_artifact_fingerprint=layer.base_artifact_fingerprint,
        layer=layer,
        effective_relation=effective,
        object_metrics=metrics,
        object_terrain=terrain,
    )


# ------------------------------------------- one layout, aligned, labelled (F7) --
#
# Audit F7 (p. 9, § 12 p. 24): the unit computed the layout four times with
# different settings, so the same data gave different maps (opening the scenario
# view turned the map a quarter and enlarged it), and no map said how far to trust
# it. The replacement: one layout (layout.fit_smacof_objects), each new map aligned
# to the one the reader was looking at by an orthogonal rotation or reflection --
# no scaling -- as a view layer, and every map labelled by its Stress-1.


class StressQuality(StrEnum):
    """The audit's plain label for a map's Stress-1 (F7, eq. 16 note)."""

    GOOD = "good"
    FAIR = "fair"
    WEAK = "weak"
    #: "2D picture unreliable".
    UNRELIABLE = "unreliable"


#: The audit's thresholds: < 0.05 good, < 0.10 fair, < 0.20 weak, >= 0.20 unreliable.
STRESS_QUALITY_BANDS: tuple[tuple[float, StressQuality], ...] = (
    (0.05, StressQuality.GOOD),
    (0.10, StressQuality.FAIR),
    (0.20, StressQuality.WEAK),
)

#: The audit's words for each label, as a reader sees them.
STRESS_QUALITY_TEXT: dict[StressQuality, str] = {
    StressQuality.GOOD: "good",
    StressQuality.FAIR: "fair",
    StressQuality.WEAK: "weak",
    StressQuality.UNRELIABLE: "2D picture unreliable",
}


def stress_quality(stress_1: float) -> StressQuality:
    """The label every map shows beside its Stress-1. A non-finite or negative value is
    not a fit and is refused rather than labelled."""
    if not math.isfinite(stress_1) or stress_1 < 0:
        raise ValueError(f"Stress-1 is a finite non-negative number; got {stress_1!r}")
    for bound, label in STRESS_QUALITY_BANDS:
        if stress_1 < bound:
            return label
    return StressQuality.UNRELIABLE


@dataclass(frozen=True, slots=True)
class AlignedObjects:
    """A map turned onto a reference map: a view of it, never a new layout (F7, eq. 16).

    ``points`` are the input points rotated (and, if ``reflected``, mirrored) about the
    origin by the angle that best matches the reference on the ``common`` objects; no
    scaling and no translation, so distances -- and the Stress-1 -- are those of the
    layout. ``rmsd`` is the remaining disagreement on the common objects, in map units.
    ``base`` and ``reference`` fingerprint the two inputs, so a view names what it turned.
    """

    points: dict[str, Point]
    common: tuple[str, ...]
    angle: float
    reflected: bool
    rmsd: float
    base: str
    reference: str


def align_to_reference(
    points: Mapping[str, Point], reference: Mapping[str, Point]
) -> AlignedObjects:
    """``P_shown = argmin_{Q in rot/refl} ||P* Q - P_previous||_F`` over the common objects.

    Both maps come from the layout's gauge (centred on their objects), and the audit's Q
    is a rotation or reflection only, so nothing is translated or scaled. Objects in only
    one map are turned with the rest and do not enter the fit. Fewer than two common
    objects cannot fix a rotation and are refused.
    """
    common = tuple(sorted(set(points) & set(reference)))
    if len(common) < 2:
        raise ViewOverrideMismatch(
            f"aligning needs at least two objects in both maps; they share {len(common)}"
        )
    best: AlignedObjects | None = None
    for reflected in (False, True):
        src = {k: ((x, -y) if reflected else (x, y)) for k, (x, y) in points.items()}
        num = math.fsum(src[k][0] * reference[k][1] - src[k][1] * reference[k][0] for k in common)
        dot = math.fsum(src[k][0] * reference[k][0] + src[k][1] * reference[k][1] for k in common)
        theta = math.atan2(num, dot)
        c, s = math.cos(theta), math.sin(theta)
        turned = {k: (c * x - s * y, s * x + c * y) for k, (x, y) in src.items()}
        rmsd = math.sqrt(
            math.fsum(
                (turned[k][0] - reference[k][0]) ** 2 + (turned[k][1] - reference[k][1]) ** 2
                for k in common
            )
            / len(common)
        )
        if best is None or rmsd < best.rmsd - 1e-15:
            best = AlignedObjects(
                points=turned,
                common=common,
                angle=theta,
                reflected=reflected,
                rmsd=rmsd,
                base=fingerprint({k: list(v) for k, v in sorted(points.items())}),
                reference=fingerprint({k: list(v) for k, v in sorted(reference.items())}),
            )
    assert best is not None
    return best
