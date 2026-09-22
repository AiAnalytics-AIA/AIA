"""Deterministic Sociomapping: contracts for research truth, methodology and view state.

Boundary this package enforces (see ``docs/architecture/sociomapa-deterministic-engine.md``):

* **A -- deterministic research truth** lives in tested code that produces a
  :class:`SociomapArtifact`. None of it has been ported yet: the legacy
  ``sociomap.py`` reference was unavailable when these contracts were written,
  and no Sociomapping mathematics is invented here in its absence.
* **B -- versioned methodology** is a :class:`SociomapSpec`, fingerprinted, with
  no hidden defaults, and refused by :func:`require_supported` when it names a
  method the engine has not implemented.
* **C -- LLM reasoning** consumes artifacts and proposes specs, layers and
  hypotheses. Nothing in this package accepts model prose as a number.
* **Presentation** is :mod:`.view`: drag overrides and what-if layers that read
  an immutable artifact and never write it.
"""

from .models import (
    ARTIFACT_CONTRACT_VERSION,
    ENGINE_IMPLEMENTATION,
    ENGINE_IMPLEMENTATION_VERSION,
    ArtifactIntegrityError,
    LayoutResult,
    MetricValues,
    Provenance,
    RelationMatrix,
    SociomapArtifact,
)
from .specification import (
    IMPLEMENTED,
    SPEC_CONTRACT_VERSION,
    ImplementedMethods,
    MapKind,
    SociomapSpec,
    UnsupportedMethodology,
    require_supported,
)
from .view import (
    WHAT_IF_BASE_KEY,
    DisplayedLayout,
    Position,
    RelationEdit,
    ViewOverrideMismatch,
    ViewOverrides,
    WhatIfLayer,
    apply_view_overrides,
    derive_what_if_relation,
    what_if_inputs,
)

__all__ = [
    "ARTIFACT_CONTRACT_VERSION",
    "ENGINE_IMPLEMENTATION",
    "ENGINE_IMPLEMENTATION_VERSION",
    "IMPLEMENTED",
    "SPEC_CONTRACT_VERSION",
    "WHAT_IF_BASE_KEY",
    "ArtifactIntegrityError",
    "DisplayedLayout",
    "ImplementedMethods",
    "LayoutResult",
    "MapKind",
    "MetricValues",
    "Position",
    "Provenance",
    "RelationEdit",
    "RelationMatrix",
    "SociomapArtifact",
    "SociomapSpec",
    "UnsupportedMethodology",
    "ViewOverrideMismatch",
    "ViewOverrides",
    "WhatIfLayer",
    "apply_view_overrides",
    "derive_what_if_relation",
    "require_supported",
    "what_if_inputs",
]
