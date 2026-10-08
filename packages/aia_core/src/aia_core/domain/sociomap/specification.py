"""Versioned Sociomapping methodology: the ``SociomapSpec`` contract, version 2.

A Sociomapa is only reproducible if every methodology choice that shaped it is
written down. This module makes each of them an explicit, fingerprinted field:

=====================  =====================================================
``ratings``            how respondents x objects ratings become dissimilarities
``relation``           how an objects x objects relation matrix is harmonised
                       and projected for position (or ``None``: the study has
                       no relation matrix)
``layout``             the declared algorithm, its parameters, its seed, and
                       the frame that maps layout units onto the terrain grid
``metrics``            which object metric drives object height and colour
``terrain``            every terrain constant, per mode, and the normaliser
=====================  =====================================================

Two rules are enforced here rather than documented:

* **No hidden defaults.** Every field is required. :data:`AIA_SOCIOMAP_V1` is a
  named preset a study adopts *explicitly*; nothing reads it implicitly.
* **Fail closed.** :func:`require_supported` refuses a spec naming anything the
  engine cannot compute -- an unknown method, the reference's unavailable layout
  algorithms, a combination that does not mean anything -- and says what. Nothing
  silently becomes a different method.

Version 1 of this contract described one square entity set and carried free
method names against an empty registry, because nothing had been ported. The
reference pipeline is rectangular -- respondents *and* objects are placed by one
unfolding -- so version 2 replaces it; no version-1 spec was ever executable.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..pipeline import fingerprint
from .layout import (
    LayoutAlgorithm,
    LayoutUnavailable,
    UnfoldingParameters,
    require_layout_algorithm,
)
from .metrics import NormalizationMode, ObjectMetric, UnknownMetricBounds, bounds_for
from .terrain import TERRAIN66_OBJECT, TERRAIN66_RESPONDENT, TerrainParameters

__all__ = [
    "AIA_SOCIOMAP_V1",
    "SPEC_CONTRACTS",
    "SPEC_CONTRACT_VERSION",
    "DissimilarityTarget",
    "LayoutSpec",
    "MapFrameMethod",
    "MapFrameSpec",
    "MetricsSpec",
    "PositionProjection",
    "RatingsMissingPolicy",
    "RatingsSpec",
    "RelationMissingPolicy",
    "RelationScaleCoercion",
    "RelationSpec",
    "SociomapSpec",
    "TerrainSpec",
    "UnknownSpecContract",
    "UnsupportedMethodology",
    "read_spec",
    "require_supported",
    "spec_payload",
]

# Version of this *contract* (the shape of a spec), distinct from
# ``SociomapSpec.methodology_version`` (which methodology the spec describes).
SPEC_CONTRACT_VERSION = "2"
#: Every spec contract this engine reads. A stored spec names its contract
#: (:func:`spec_payload`) and is read under that one (:func:`read_spec`), never under
#: the newest: a later contract is a new model beside this one, so a spec stored under
#: an earlier contract keeps its fields and its fingerprint byte for byte.
SPEC_CONTRACTS: Final = (SPEC_CONTRACT_VERSION,)


class DissimilarityTarget(StrEnum):
    """How a rating becomes a dissimilarity for unfolding."""

    SCALE_TOP_MINUS_RATING = "scale_top_minus_rating"


class RatingsMissingPolicy(StrEnum):
    """How unrated cells enter the layout."""

    OBSERVED_CELLS_ONLY = "observed_cells_only"


class RelationScaleCoercion(StrEnum):
    """How a relation matrix is harmonised onto one scale."""

    #: The reference's: the scale guessed from the values (audit F5), kept for
    #: ``aia-sociomap-1``'s parity with fixture F1.
    REFERENCE_COERCE_1_10 = "reference_coerce_1_10"
    #: Audit F5: the matrix's type is declared, never detected; each maps onto the
    #: 1-10 scale by its own conversion, and a cell outside its range is refused.
    DECLARED_CORRELATION = "declared_correlation"
    DECLARED_SIMILARITY_0_1 = "declared_similarity_0_1"
    #: Named and refused by ``require_supported``: its transform is not written out
    #: (register AUDIT-F5, SPECIFICATION_REQUIRED).
    DECLARED_STRENGTH_1_10 = "declared_strength_1_10"


class PositionProjection(StrEnum):
    """How a directed relation is collapsed for 2-D position."""

    MUTUAL_ARITHMETIC_MEAN = "mutual_arithmetic_mean"


class RelationMissingPolicy(StrEnum):
    """How a missing relation cell is treated.

    ``refuse`` is the fail-closed choice. ``reference_midpoint_sentinel``
    reproduces the reference, which substitutes 5.5 -- the scale midpoint -- for
    an unknown relation, scoring *unknown* as *neutral* (ARCHITECTURE.md A4). It
    exists so a study can declare that it wants the reference's behaviour; it is
    never chosen for anyone.
    """

    REFUSE = "refuse"
    REFERENCE_MIDPOINT_SENTINEL = "reference_midpoint_sentinel"


class MapFrameMethod(StrEnum):
    """How layout units are mapped onto terrain-grid units."""

    MAX_ABS_TO_EXTENT = "max_abs_to_extent"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _not_boolean(v: object) -> object:
    """Refuse a boolean where a number is expected.

    pydantic coerces ``True`` to ``1`` / ``1.0`` before an after-validator runs,
    so ``"extent": true`` would otherwise become a map compressed to extent 1.
    """
    if isinstance(v, bool):
        raise ValueError("expected a number, not a boolean")
    return v


def _finite(v: float, what: str) -> float:
    if not math.isfinite(v):
        raise ValueError(f"{what} must be finite")
    return float(v)


class RatingsSpec(_Frozen):
    """Respondents x objects ratings -> unfolding dissimilarities."""

    ipsatize: bool
    dissimilarity: str
    rating_scale_min: float
    rating_scale_max: float
    missing_data_policy: str

    @field_validator("rating_scale_min", "rating_scale_max", mode="before")
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)

    @model_validator(mode="after")
    def _scale(self) -> RatingsSpec:
        _finite(self.rating_scale_min, "rating_scale_min")
        _finite(self.rating_scale_max, "rating_scale_max")
        if not self.rating_scale_max > self.rating_scale_min:
            raise ValueError("rating_scale_max must exceed rating_scale_min")
        return self


class RelationSpec(_Frozen):
    """Objects x objects relation matrix -> harmonised, directed + position input."""

    scale_coercion: str
    position_projection: str
    missing_data_policy: str


class MapFrameSpec(_Frozen):
    """Layout units -> terrain-grid units.

    The reference renders terrain on a +-62 grid with kernels of width 9.5 and 12,
    so coordinates must be in those units before a kernel is meaningful. The
    reference's own layout-to-screen scaling was not recovered; this is declared.
    """

    method: str
    extent: float

    @field_validator("extent", mode="before")
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)

    @field_validator("extent")
    @classmethod
    def _extent(cls, v: float) -> float:
        if not (math.isfinite(v) and v > 0):
            raise ValueError("map frame extent must be positive and finite")
        return float(v)


class LayoutSpec(_Frozen):
    """The declared layout algorithm. There is no ``auto``."""

    algorithm: str
    parameters: dict[str, Any]
    seed: int | None
    map_frame: MapFrameSpec

    @field_validator("seed", mode="before")
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)

    @field_validator("parameters")
    @classmethod
    def _parameters_are_json(cls, v: dict[str, Any]) -> dict[str, Any]:
        # The fingerprint is a JSON hash; a parameter that cannot be serialised
        # would be stringified silently and two different objects could collide.
        _assert_json_scalar_tree(v, "layout.parameters")
        return v


class MetricsSpec(_Frozen):
    """Which object metric drives object-map height, and which drives colour."""

    object_height_metric: str
    object_colour_metric: str


class TerrainSpec(_Frozen):
    """Terrain constants per mode, and the height normaliser."""

    respondent: TerrainParameters
    object: TerrainParameters
    normalization: str


class SociomapSpec(_Frozen):
    """Every methodology decision behind one Sociomapa, as data.

    ``relation`` is ``None`` for a study with no objects x objects relation
    matrix; relation-derived metrics are then unavailable and refused.
    """

    methodology_version: str
    ratings: RatingsSpec
    relation: RelationSpec | None
    layout: LayoutSpec
    metrics: MetricsSpec
    terrain: TerrainSpec

    @field_validator("methodology_version")
    @classmethod
    def _named(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("methodology_version must be stated; blank is not a default")
        return v

    def fingerprint(self) -> str:
        """Stable SHA256 over the whole methodology, independent of key order.

        Any change to any field -- one terrain constant, one layout parameter,
        the seed -- changes it, so an artifact produced under one methodology can
        never be mistaken for one produced under another.
        """
        return fingerprint(
            {"contract_version": SPEC_CONTRACT_VERSION, **self.model_dump(mode="json")}
        )


class UnknownSpecContract(ValueError):
    """A stored spec names a contract this engine does not read, or names none."""


def spec_payload(spec: SociomapSpec) -> dict[str, Any]:
    """A spec as it is stored: its contract named beside its body.

    The contract is stated, not inferred from the fields present, so a reader can never
    take a spec of one contract for another's.
    """
    return {"contract_version": SPEC_CONTRACT_VERSION, "spec": spec.model_dump(mode="json")}


def read_spec(payload: Mapping[str, Any]) -> SociomapSpec:
    """The spec :func:`spec_payload` stored, read under the contract it names.

    Raises :class:`UnknownSpecContract` for a contract this engine does not read (or a
    payload naming none) and pydantic's ``ValidationError`` for a body that does not
    validate under its own contract.
    """
    contract = payload.get("contract_version")
    if contract not in SPEC_CONTRACTS:
        raise UnknownSpecContract(
            f"no Sociomap spec contract {contract!r}; this engine reads {list(SPEC_CONTRACTS)}"
        )
    return SociomapSpec.model_validate(payload.get("spec"))


def _assert_json_scalar_tree(value: Any, path: str) -> None:
    """Reject anything json.dumps would stringify via ``default=str``."""
    if value is None or isinstance(value, bool | int | str):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be finite; got {value!r}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings; got {key!r}")
            _assert_json_scalar_tree(item, f"{path}.{key}")
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _assert_json_scalar_tree(item, f"{path}[{index}]")
        return
    raise ValueError(f"{path} must be JSON data (str, int, float, bool, None, list, dict)")


class UnsupportedMethodology(ValueError):
    """The spec names something this engine cannot compute. Nothing substitutes.

    ``unsupported`` maps each offending field path to the reason, so the caller
    -- or the agent that proposed the spec -- can see exactly what is missing.
    """

    def __init__(self, unsupported: dict[str, str]) -> None:
        self.unsupported = dict(unsupported)
        detail = "; ".join(f"{field}: {why}" for field, why in sorted(unsupported.items()))
        super().__init__(
            "Sociomapping methodology not supported by this engine, and no fallback is "
            f"permitted: {detail}"
        )


_RELATION_METRICS = frozenset({ObjectMetric.RELATION_CLASSIC, ObjectMetric.RELATION_CLASSIC_TSCORE})


def _member(enum: type[StrEnum], value: str) -> bool:
    return value in {m.value for m in enum}


def require_supported(spec: SociomapSpec) -> None:
    """Raise :class:`UnsupportedMethodology` unless the engine can compute ``spec``.

    Call before any computation. Every problem is reported at once.
    """
    problems: dict[str, str] = {}

    r = spec.ratings
    if not _member(DissimilarityTarget, r.dissimilarity):
        problems["ratings.dissimilarity"] = f"unknown target {r.dissimilarity!r}"
    elif r.ipsatize:
        # scale_top_minus_rating reads a rating's position on the declared scale;
        # an ipsatized value is a deviation from the respondent's mean and has no
        # position on that scale.
        problems["ratings.ipsatize"] = (
            f"{r.dissimilarity!r} needs ratings on the declared scale; ipsatized values "
            "are not, and no implemented target accepts them"
        )
    if not _member(RatingsMissingPolicy, r.missing_data_policy):
        problems["ratings.missing_data_policy"] = f"unknown policy {r.missing_data_policy!r}"

    if spec.relation is not None:
        rel = spec.relation
        if not _member(RelationScaleCoercion, rel.scale_coercion):
            problems["relation.scale_coercion"] = f"unknown coercion {rel.scale_coercion!r}"
        elif rel.scale_coercion == RelationScaleCoercion.DECLARED_STRENGTH_1_10:
            problems["relation.scale_coercion"] = (
                "declared_strength_1_10 has no specified transform (audit F5, register AUDIT-F5: "
                "SPECIFICATION_REQUIRED); it is refused until the audit's author writes it out"
            )
        if not _member(PositionProjection, rel.position_projection):
            problems["relation.position_projection"] = (
                f"unknown projection {rel.position_projection!r}"
            )
        if not _member(RelationMissingPolicy, rel.missing_data_policy):
            problems["relation.missing_data_policy"] = f"unknown policy {rel.missing_data_policy!r}"
        elif (
            rel.scale_coercion != RelationScaleCoercion.REFERENCE_COERCE_1_10
            and rel.missing_data_policy == RelationMissingPolicy.REFERENCE_MIDPOINT_SENTINEL
        ):
            # Audit F5: under a declared type a missing cell is unknown, never 5.5.
            problems["relation.missing_data_policy"] = (
                "a declared relation type takes no midpoint sentinel: a missing cell is "
                "unknown (audit F5); declare 'refuse'"
            )

    layout = spec.layout
    try:
        algorithm = require_layout_algorithm(layout.algorithm)
    except LayoutUnavailable as exc:
        problems["layout.algorithm"] = exc.reason
    else:
        if algorithm is LayoutAlgorithm.AIA_ROWCOND_UNFOLDING_V1:
            try:
                UnfoldingParameters.model_validate(layout.parameters)
            except ValueError as exc:
                problems["layout.parameters"] = str(exc).splitlines()[0]
            if layout.seed is not None:
                problems["layout.seed"] = (
                    f"{algorithm.value} uses no randomness; a seed would be recorded as if it "
                    "mattered. Declare null"
                )
    if not _member(MapFrameMethod, layout.map_frame.method):
        problems["layout.map_frame.method"] = f"unknown method {layout.map_frame.method!r}"

    normalization: NormalizationMode | None = None
    if _member(NormalizationMode, spec.terrain.normalization):
        normalization = NormalizationMode(spec.terrain.normalization)
    else:
        problems["terrain.normalization"] = f"unknown mode {spec.terrain.normalization!r}"

    for field in ("object_height_metric", "object_colour_metric"):
        metric = getattr(spec.metrics, field)
        if not _member(ObjectMetric, metric):
            problems[f"metrics.{field}"] = (
                f"unknown metric {metric!r}; the reference rendered the T-score for unknown "
                "ids, which production refuses"
            )
        elif ObjectMetric(metric) in _RELATION_METRICS and spec.relation is None:
            problems[f"metrics.{field}"] = f"{metric!r} needs a relation spec and matrix"
    height = spec.metrics.object_height_metric
    if normalization is not None and _member(ObjectMetric, height):
        try:
            bounds_for(
                height,
                normalization,
                rating_scale=(spec.ratings.rating_scale_min, spec.ratings.rating_scale_max),
            )
        except UnknownMetricBounds as exc:
            problems["terrain.normalization"] = str(exc)

    if problems:
        raise UnsupportedMethodology(problems)


# The preset this engine version proposes. A study adopts it by naming it; the
# engine never falls back to it. Every value is either recovered from the
# reference (cited) or an AIA declaration (marked) -- see
# docs/architecture/sociomapa-deterministic-engine.md §5.
AIA_SOCIOMAP_V1 = SociomapSpec(
    methodology_version="aia-sociomap-1",
    ratings=RatingsSpec(
        ipsatize=False,  # AIA: the implemented target reads the rating scale
        dissimilarity=DissimilarityTarget.SCALE_TOP_MINUS_RATING,  # AIA declaration
        rating_scale_min=1.0,  # reference 1-10 scale (F1, F8 bounds)
        rating_scale_max=10.0,
        missing_data_policy=RatingsMissingPolicy.OBSERVED_CELLS_ONLY,  # reference (F4)
    ),
    relation=RelationSpec(
        scale_coercion=RelationScaleCoercion.REFERENCE_COERCE_1_10,  # reference (F1)
        position_projection=PositionProjection.MUTUAL_ARITHMETIC_MEAN,  # reference (F2)
        missing_data_policy=RelationMissingPolicy.REFUSE,  # AIA: fail closed
    ),
    layout=LayoutSpec(
        algorithm=LayoutAlgorithm.AIA_ROWCOND_UNFOLDING_V1,  # AIA declaration
        parameters={"dimensions": 2, "max_iterations": 2000, "convergence_tolerance": 1e-7},
        seed=None,  # deterministic: no RNG
        map_frame=MapFrameSpec(method=MapFrameMethod.MAX_ABS_TO_EXTENT, extent=45.0),  # AIA
    ),
    metrics=MetricsSpec(
        object_height_metric=ObjectMetric.RELATION_CLASSIC_TSCORE,  # reference default (F6)
        object_colour_metric=ObjectMetric.RELATION_CLASSIC_TSCORE,
    ),
    terrain=TerrainSpec(
        respondent=TERRAIN66_RESPONDENT,  # reference (F7)
        object=TERRAIN66_OBJECT,  # reference (F8)
        normalization=NormalizationMode.RANGE,  # reference default (F7, F8)
    ),
)
