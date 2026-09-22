"""Presentation and exploration layers over an immutable Sociomapa.

Two product rules are implemented here as types rather than as discipline:

* **Manual drag is view state.** ``PRODUCT_POLICY.json`` in the legacy system
  states ``manual_drag: visual_override_only_never_mutates_raw_results``. A
  :class:`ViewOverrides` is bound to one artifact by fingerprint and produces a
  :class:`DisplayedLayout`; the artifact it reads is never written.
* **What-if is a layer.** A :class:`WhatIfLayer` names its base artifact and
  the edits applied to the base *inputs*; :func:`derive_what_if_relation` builds
  a new relation matrix from an untouched original. The derived artifact must
  record the base under :data:`WHAT_IF_BASE_KEY` in its provenance so lineage is
  a lookup, not an inference.

The edit vocabulary of the what-if layer (cell overrides on the relation
matrix) is the minimal deterministic mechanism. The legacy what-if mode's exact
semantics have not been read from the reference implementation yet; when they
are, they extend this vocabulary rather than replace the layering invariant.
"""

from __future__ import annotations

import math
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import RelationMatrix, SociomapArtifact

__all__ = [
    "WHAT_IF_BASE_KEY",
    "DisplayedLayout",
    "Position",
    "RelationEdit",
    "ViewOverrideMismatch",
    "ViewOverrides",
    "WhatIfLayer",
    "apply_view_overrides",
    "derive_what_if_relation",
]

# Provenance key under which a what-if artifact records its base artifact's
# fingerprint (``Provenance.input_fingerprints[WHAT_IF_BASE_KEY]``).
WHAT_IF_BASE_KEY = "what_if_base_artifact"


class ViewOverrideMismatch(ValueError):
    """The overrides do not belong to the artifact they were applied to."""


class Position(BaseModel):
    """A displayed 2-D position."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x: float
    y: float

    @field_validator("x", "y")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("positions must be finite")
        return float(v)


class ViewOverrides(BaseModel):
    """Per-entity display positions a user dragged to, bound to one artifact.

    Binding by ``artifact_fingerprint`` is what stops an override recorded
    against one computation being silently shown over another: if the
    methodology, inputs or implementation change, the artifact fingerprint
    changes and the stale overrides are refused.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_fingerprint: str
    positions: dict[str, Position] = Field(default_factory=dict)

    @field_validator("artifact_fingerprint")
    @classmethod
    def _bound(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("overrides must be bound to an artifact fingerprint")
        return v

    def with_position(self, entity_id: str, x: float, y: float) -> ViewOverrides:
        """Return overrides with one entity moved; the receiver is unchanged."""
        positions = dict(self.positions)
        positions[entity_id] = Position(x=x, y=y)
        return self.model_copy(update={"positions": positions})

    def without(self, entity_id: str) -> ViewOverrides:
        """Return overrides with one entity reset to its canonical position."""
        positions = {k: v for k, v in self.positions.items() if k != entity_id}
        return self.model_copy(update={"positions": positions})


class DisplayedLayout(BaseModel):
    """What a renderer draws: canonical coordinates with overrides applied.

    Carries the artifact fingerprint so the display can always be traced to the
    research truth it departs from, and lists which entities were moved so the
    departure is visible rather than silent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_fingerprint: str
    entity_ids: tuple[str, ...]
    x: tuple[float, ...]
    y: tuple[float, ...]
    overridden: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        n = len(self.entity_ids)
        if len(self.x) != n or len(self.y) != n:
            raise ValueError("displayed coordinates must align with entity_ids")
        return self


def apply_view_overrides(artifact: SociomapArtifact, overrides: ViewOverrides) -> DisplayedLayout:
    """Layer dragged positions over an artifact's canonical layout.

    Pure: returns a new :class:`DisplayedLayout` and touches nothing else. Raises
    :class:`ViewOverrideMismatch` when the overrides are bound to a different
    artifact or name an entity the artifact does not contain.
    """
    fp = artifact.fingerprint()
    if overrides.artifact_fingerprint != fp:
        raise ViewOverrideMismatch(
            "view overrides are bound to a different artifact; canonical results "
            "changed, so the stale drag state is refused rather than shown"
        )
    unknown = sorted(set(overrides.positions) - set(artifact.entity_ids))
    if unknown:
        raise ViewOverrideMismatch(f"overrides name entities not in the artifact: {unknown}")

    xs = list(artifact.layout.x)
    ys = list(artifact.layout.y)
    moved: list[str] = []
    for i, entity in enumerate(artifact.entity_ids):
        position = overrides.positions.get(entity)
        if position is not None:
            xs[i], ys[i] = position.x, position.y
            moved.append(entity)
    return DisplayedLayout(
        artifact_fingerprint=fp,
        entity_ids=artifact.entity_ids,
        x=tuple(xs),
        y=tuple(ys),
        overridden=tuple(moved),
    )


class RelationEdit(BaseModel):
    """One hypothetical change to a relation cell: ``source -> target`` becomes ``value``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    target: str
    value: float | None

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(v):
            raise ValueError("a what-if value must be finite or None")
        return v


class WhatIfLayer(BaseModel):
    """A hypothesis expressed as edits to an immutable base artifact's inputs.

    ``label`` is for people. ``edits`` are the deterministic content. The layer
    never holds a result: results are separate artifacts whose provenance names
    this layer's base.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_artifact_fingerprint: str
    edits: tuple[RelationEdit, ...]
    label: str = ""

    @field_validator("base_artifact_fingerprint")
    @classmethod
    def _bound(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("a what-if layer must name its base artifact")
        return v

    @field_validator("edits")
    @classmethod
    def _non_empty(cls, v: tuple[RelationEdit, ...]) -> tuple[RelationEdit, ...]:
        if not v:
            raise ValueError("a what-if layer with no edits is the base itself")
        return v

    def provenance_inputs(self) -> dict[str, str]:
        """The provenance entries a derived artifact must carry."""
        return {WHAT_IF_BASE_KEY: self.base_artifact_fingerprint}


def derive_what_if_relation(base: SociomapArtifact, layer: WhatIfLayer) -> RelationMatrix:
    """Build the alternative relation matrix a what-if layer describes.

    Refuses a layer bound to a different artifact. The base artifact and its
    matrix are read only; the result is a new :class:`RelationMatrix` ready to be
    fed to the engine under the base artifact's spec (or a deliberately different
    one, recorded as such).
    """
    if layer.base_artifact_fingerprint != base.fingerprint():
        raise ViewOverrideMismatch("what-if layer is bound to a different base artifact")
    overrides: dict[tuple[str, str], float | None] = {
        (edit.source, edit.target): edit.value for edit in layer.edits
    }
    try:
        return base.relation.with_cells(overrides)
    except KeyError as exc:
        raise ViewOverrideMismatch(
            f"what-if edit names an unknown entity {exc.args[0]!r}"
        ) from None


def what_if_inputs(base: SociomapArtifact, layer: WhatIfLayer) -> dict[str, Any]:
    """Convenience: the inputs an engine call for this what-if would receive."""
    return {
        "relation": derive_what_if_relation(base, layer),
        "spec": base.spec,
        "provenance_inputs": layer.provenance_inputs(),
    }
