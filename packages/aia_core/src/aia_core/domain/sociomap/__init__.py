"""Deterministic Sociomapping: research mathematics, methodology and view state.

Boundary this package enforces (see ``docs/architecture/sociomapa-deterministic-engine.md``):

* **A -- deterministic research truth** is :func:`compute_sociomap`, which turns
  :class:`SociomapInputs` and a :class:`SociomapSpec` into one immutable,
  fingerprinted :class:`SociomapArtifact`: relation transforms (:mod:`.relations`),
  the declared layout (:mod:`.layout`), object metrics and normalisation
  (:mod:`.metrics`) and both terrain fields (:mod:`.terrain`). Pure Python,
  bit-identical on every host.
* **B -- versioned methodology** is a :class:`SociomapSpec`, fingerprinted, with
  no hidden defaults, and refused by :func:`require_supported` when it names
  anything the engine cannot compute. The layout algorithm is declared, never
  detected.
* **C -- LLM reasoning** consumes artifacts and proposes specs and scenarios.
  Nothing here accepts model prose as a number.
* **Presentation** is :mod:`.view`: drag overrides, view terrain and scenario
  layers that read an artifact and never write it.

Every function ported from the reference is tested against its golden fixture
(F1-F9); what could not be ported, and why, is in the module that would own it.
"""

from .engine import SociomapInputError, compute_sociomap
from .engine_v2 import compute_object_map
from .layout import (
    LAYOUT_ALGORITHMS,
    LayoutAlgorithm,
    LayoutUnavailable,
    UnfoldingDesignError,
    UnfoldingParameters,
)
from .metrics import NormalizationMode, ObjectMetric
from .models import (
    ARTIFACT_CONTRACT_VERSION,
    ENGINE_IMPLEMENTATION,
    ENGINE_IMPLEMENTATION_VERSION,
    ArtifactIntegrityError,
    LayoutResult,
    MetricValues,
    Provenance,
    RatingsMatrix,
    RelationDerivation,
    RelationMatrix,
    SociomapArtifact,
    SociomapInputs,
)
from .models_v3 import (
    ARTIFACT_CONTRACT_V3,
    MapOutcome,
    NotMappableReason,
    ObjectMapInputs,
    RatingItem,
    SociomapArtifactV3,
    read_artifact,
)
from .specification import (
    AIA_OBJECT_ENVELOPE,
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V2,
    AIA_SOCIOMAP_V3,
    EFFECT_FLOOR_AIA_Q6,
    PROVISIONAL_ENVELOPE_SIGMA,
    SPEC_CONTRACT_V3,
    SPEC_CONTRACT_VERSION,
    LayoutSpec,
    MapFrameSpec,
    MetricsSpec,
    RatingsSpec,
    RelationSpec,
    SociomapSpec,
    SociomapSpecV3,
    TerrainSpec,
    UnknownSpecContract,
    UnsupportedMethodology,
    read_spec,
    require_supported,
    spec_payload,
)
from .terrain import (
    TERRAIN66_OBJECT,
    TERRAIN66_RESPONDENT,
    TerrainField,
    TerrainMode,
    TerrainParameters,
)
from .view import (
    DisplayedMap,
    Position,
    RelationEdit,
    ScenarioLayer,
    ScenarioResult,
    ViewOverrideMismatch,
    ViewOverrides,
    apply_scenario,
    apply_view_overrides,
    view_terrain,
)

__all__ = [
    "AIA_OBJECT_ENVELOPE",
    "AIA_SOCIOMAP_V1",
    "AIA_SOCIOMAP_V2",
    "AIA_SOCIOMAP_V3",
    "ARTIFACT_CONTRACT_V3",
    "ARTIFACT_CONTRACT_VERSION",
    "EFFECT_FLOOR_AIA_Q6",
    "ENGINE_IMPLEMENTATION",
    "ENGINE_IMPLEMENTATION_VERSION",
    "LAYOUT_ALGORITHMS",
    "PROVISIONAL_ENVELOPE_SIGMA",
    "SPEC_CONTRACT_V3",
    "SPEC_CONTRACT_VERSION",
    "TERRAIN66_OBJECT",
    "TERRAIN66_RESPONDENT",
    "ArtifactIntegrityError",
    "DisplayedMap",
    "LayoutAlgorithm",
    "LayoutResult",
    "LayoutSpec",
    "LayoutUnavailable",
    "MapFrameSpec",
    "MapOutcome",
    "MetricValues",
    "MetricsSpec",
    "NormalizationMode",
    "NotMappableReason",
    "ObjectMapInputs",
    "ObjectMetric",
    "Position",
    "Provenance",
    "RatingItem",
    "RatingsMatrix",
    "RatingsSpec",
    "RelationDerivation",
    "RelationEdit",
    "RelationMatrix",
    "RelationSpec",
    "ScenarioLayer",
    "ScenarioResult",
    "SociomapArtifact",
    "SociomapArtifactV3",
    "SociomapInputError",
    "SociomapInputs",
    "SociomapSpec",
    "SociomapSpecV3",
    "TerrainField",
    "TerrainMode",
    "TerrainParameters",
    "TerrainSpec",
    "UnfoldingDesignError",
    "UnfoldingParameters",
    "UnknownSpecContract",
    "UnsupportedMethodology",
    "ViewOverrideMismatch",
    "ViewOverrides",
    "apply_scenario",
    "apply_view_overrides",
    "compute_object_map",
    "compute_sociomap",
    "read_artifact",
    "read_spec",
    "require_supported",
    "spec_payload",
    "view_terrain",
]
