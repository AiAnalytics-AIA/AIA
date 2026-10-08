"""Versioned Sociomapping methodology: the ``SociomapSpec`` contract (2) and contract 3.

Contract 3 (:class:`SociomapSpecV3`, preset :data:`AIA_SOCIOMAP_V2`) is the audit's object
map and is described where it is defined, below; everything in this docstring up to there is
contract 2's, unchanged. A stored spec names its contract (:func:`spec_payload`) and is read
under it (:func:`read_spec`).

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
from .relations import AUDIT_PROVISIONAL_N_MIN
from .terrain import TERRAIN66_OBJECT, TERRAIN66_RESPONDENT, TerrainParameters

__all__ = [
    "AIA_SOCIOMAP_V1",
    "AIA_SOCIOMAP_V2",
    "FIXED_RULER_EXTENT",
    "SPEC_CONTRACTS",
    "SPEC_CONTRACT_V3",
    "SPEC_CONTRACT_VERSION",
    "ConnectednessSpec",
    "DissimilarityTarget",
    "LayoutSpec",
    "MapFrameMethod",
    "MapFrameSpec",
    "MetricsSpec",
    "ObjectHeightMetric",
    "ObjectLayoutSpec",
    "ObjectScoresSpec",
    "PairEvidenceBasis",
    "PairEvidenceSpec",
    "PersonNormalization",
    "PositionProjection",
    "RatingsMissingPolicy",
    "RatingsSpec",
    "RatingsSpecV3",
    "RelationEstimator",
    "RelationMissingPolicy",
    "RelationScaleCoercion",
    "RelationSpec",
    "ScaleNormalization",
    "SociomapSpec",
    "SociomapSpecV3",
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
SPEC_CONTRACTS: Final = (SPEC_CONTRACT_VERSION, "3")
#: Contract 3: the audit's object map (plan ``sociomap-formula-corrections`` § 8.2, S2).
SPEC_CONTRACT_V3: Final = "3"


class DissimilarityTarget(StrEnum):
    """How a rating becomes a dissimilarity for unfolding."""

    SCALE_TOP_MINUS_RATING = "scale_top_minus_rating"
    #: Audit F6: two objects' distance is ``sqrt(2 (1 - r~))`` of their correlation over
    #: each person's own scale. Contract 3's object layout; contract 2 refuses it.
    CORRELATION_DISTANCE = "correlation_distance"


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
    #: Audit F6: no rescale. One map unit is one unit of correlation distance, so the
    #: extent is the ruler's own maximum (2.0, two opposite objects). Contract 3 only.
    FIXED_RULER = "fixed_ruler"


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


# --------------------------------------------------------------------------- #
# Contract 3: the audit's object map (aia-sociomap-2)
# --------------------------------------------------------------------------- #
#
# The audit "NPC Sociomapa: faulty formulas in the code" (canonical, plan
# ``sociomap-formula-corrections``) fixes a chain contract 2 cannot express: each rating
# on its item's declared 0-1 scale (F1), each person's min-max over every rating item
# (F2), the weighted correlation of what remains with its status (F3, F4), the objects
# alone by SMACOF on the correlation distance on a fixed ruler (F6, F7), the PRIMARY
# scores with UNKNOWN left out and the mean rating as height (F8), K100 with its interval
# (F9). Respondent placement (chunk 3, F10's threshold open) and the envelope terrain
# (chunk 4b, its kernel width open) have no member yet: a spec declares them ``None`` and
# an artifact says they were not computed. Every field is required.


class ScaleNormalization(StrEnum):
    """How a rating reaches a common scale before anything else (audit F1, eq. 3)."""

    DECLARED_ENDS_0_1 = "declared_ends_0_1"


class PersonNormalization(StrEnum):
    """How each person's own use of the scale is removed (audit F2, eq. 5)."""

    #: Lowest rating 0, highest 1, over every rating item the person rated; a person with
    #: no spread is not placed (F11).
    PERSON_MINMAX_ALL_RATED = "person_minmax_all_rated"


class RelationEstimator(StrEnum):
    """How a pair's relation is estimated from the person-scaled ratings."""

    #: The unit's weighted Pearson correlation (the weighting is AIA's reading where the
    #: audit is silent, register AUDIT-F2), signed, never mapped onto 1-10.
    WEIGHTED_PEARSON = "weighted_pearson"


class PairEvidenceBasis(StrEnum):
    """What ``n`` a pair's status reads (chunk 1d adds the Kish effective n)."""

    RESPONDENT_COUNT = "respondent_count"


class ObjectHeightMetric(StrEnum):
    """What an object's height is under contract 3 (audit F8: the mean rating)."""

    #: The weighted mean of the object's ratings on the declared 0-1 scale (F1).
    MEAN_RATING_0_1 = "mean_rating_0_1"


class RatingsSpecV3(_Frozen):
    scale_normalization: str
    person_normalization: str


class PairEvidenceSpec(_Frozen):
    """How a pair's relation is estimated and what it can be said to be (F3)."""

    estimator: str
    basis: str
    n_min: int
    confidence: float

    @field_validator("n_min", "confidence", mode="before")
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)


class ObjectLayoutSpec(_Frozen):
    """The objects' map (F6, F7): its algorithm, its targets, its stopping rule, its frame."""

    algorithm: str
    dissimilarity: str
    max_iterations: int
    tolerance: float
    map_frame: MapFrameSpec

    @field_validator("max_iterations", "tolerance", mode="before")
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)


class ObjectScoresSpec(_Frozen):
    height: str


class ConnectednessSpec(_Frozen):
    """K100's respondent bootstrap (F9): how many resamples, from which seed."""

    resamples: int
    seed: int

    @field_validator("resamples", "seed", mode="before")
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)


class SociomapSpecV3(_Frozen):
    """Every methodology decision behind one contract-3 Sociomap (the audit's object map).

    ``respondent_placement`` and ``terrain`` are declared ``None``: no member is built
    (chunks 3 and 4b wait on decisions the audit leaves to its author), and a value is
    refused by :func:`require_supported` rather than ignored.
    """

    methodology_version: str
    ratings: RatingsSpecV3
    relation: PairEvidenceSpec
    layout: ObjectLayoutSpec
    scores: ObjectScoresSpec
    connectedness: ConnectednessSpec
    respondent_placement: str | None
    terrain: str | None

    @field_validator("methodology_version")
    @classmethod
    def _named(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("methodology_version must be stated; blank is not a default")
        return v

    def fingerprint(self) -> str:
        """Stable SHA256 over the whole methodology, its contract included."""
        return fingerprint({"contract_version": SPEC_CONTRACT_V3, **self.model_dump(mode="json")})


#: The fixed ruler's extent: the largest correlation distance, two opposite objects.
FIXED_RULER_EXTENT: Final = 2.0
#: The smallest ``n_min`` a status can mean anything at: the Fisher interval needs four.
_V3_N_MIN_FLOOR: Final = 4


def _require_supported_v3(spec: SociomapSpecV3) -> None:
    problems: dict[str, str] = {}
    if not _member(ScaleNormalization, spec.ratings.scale_normalization):
        problems["ratings.scale_normalization"] = (
            f"unknown normalization {spec.ratings.scale_normalization!r}"
        )
    if not _member(PersonNormalization, spec.ratings.person_normalization):
        problems["ratings.person_normalization"] = (
            f"unknown normalization {spec.ratings.person_normalization!r}"
        )
    rel = spec.relation
    if not _member(RelationEstimator, rel.estimator):
        problems["relation.estimator"] = f"unknown estimator {rel.estimator!r}"
    if not _member(PairEvidenceBasis, rel.basis):
        problems["relation.basis"] = f"unknown basis {rel.basis!r} (the Kish n is chunk 1d's)"
    if rel.n_min < _V3_N_MIN_FLOOR:
        problems["relation.n_min"] = (
            f"n_min {rel.n_min} is below {_V3_N_MIN_FLOOR}: the Fisher interval needs four raters"
        )
    if not (math.isfinite(rel.confidence) and 0.0 < rel.confidence < 1.0):
        problems["relation.confidence"] = f"confidence must lie in (0, 1); got {rel.confidence!r}"
    layout = spec.layout
    try:
        algorithm = require_layout_algorithm(layout.algorithm)
    except LayoutUnavailable as exc:
        problems["layout.algorithm"] = exc.reason
    else:
        if algorithm is not LayoutAlgorithm.AIA_SMACOF_OBJECTS_V1:
            problems["layout.algorithm"] = (
                f"{algorithm.value} places respondents and objects together (contract 2); "
                "contract 3 maps the objects alone by aia_smacof_objects_v1"
            )
    if layout.dissimilarity != DissimilarityTarget.CORRELATION_DISTANCE:
        problems["layout.dissimilarity"] = (
            f"contract 3's objects are placed on the correlation distance; got "
            f"{layout.dissimilarity!r}"
        )
    if layout.max_iterations < 1:
        problems["layout.max_iterations"] = "max_iterations must be at least 1"
    if not (math.isfinite(layout.tolerance) and layout.tolerance > 0):
        problems["layout.tolerance"] = "tolerance must be positive and finite"
    if layout.map_frame.method != MapFrameMethod.FIXED_RULER:
        problems["layout.map_frame.method"] = (
            "contract 3 keeps the fixed ruler (audit F6): no rescale to a radius"
        )
    elif layout.map_frame.extent != FIXED_RULER_EXTENT:
        problems["layout.map_frame.extent"] = (
            f"the fixed ruler's extent is the correlation distance's maximum, "
            f"{FIXED_RULER_EXTENT}; got {layout.map_frame.extent}"
        )
    if not _member(ObjectHeightMetric, spec.scores.height):
        problems["scores.height"] = f"unknown height {spec.scores.height!r}"
    if spec.connectedness.resamples < 1:
        problems["connectedness.resamples"] = "resamples must be at least 1"
    if spec.respondent_placement is not None:
        problems["respondent_placement"] = (
            "respondent placement is chunk 3's (ideal points, F10) and is not built: its "
            "misfit threshold is open (plan § 4a, 0b); declare null"
        )
    if spec.terrain is not None:
        problems["terrain"] = (
            "the envelope terrain is chunk 4b's (F12, F13) and is not built: its kernel width "
            "on the fixed ruler is open (0b); declare null"
        )
    if problems:
        raise UnsupportedMethodology(problems)


class UnknownSpecContract(ValueError):
    """A stored spec names a contract this engine does not read, or names none."""


def spec_payload(spec: SociomapSpec | SociomapSpecV3) -> dict[str, Any]:
    """A spec as it is stored: its contract named beside its body.

    The contract is stated, not inferred from the fields present, so a reader can never
    take a spec of one contract for another's.
    """
    contract = SPEC_CONTRACT_V3 if isinstance(spec, SociomapSpecV3) else SPEC_CONTRACT_VERSION
    return {"contract_version": contract, "spec": spec.model_dump(mode="json")}


def read_spec(payload: Mapping[str, Any]) -> SociomapSpec | SociomapSpecV3:
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
    if contract == SPEC_CONTRACT_V3:
        return SociomapSpecV3.model_validate(payload.get("spec"))
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
_CONTRACT_3_ONLY: Final = (
    "the audit's object map (aia-sociomap-2) is spec contract 3; a contract-2 spec places "
    "respondents and objects together and cannot compute it"
)


def _member(enum: type[StrEnum], value: str) -> bool:
    return value in {m.value for m in enum}


def require_supported(spec: SociomapSpec | SociomapSpecV3) -> None:
    """Raise :class:`UnsupportedMethodology` unless the engine can compute ``spec``.

    Call before any computation. Every problem is reported at once. Each contract is
    checked by its own rules: a contract-2 spec never borrows contract 3's members.
    """
    if isinstance(spec, SociomapSpecV3):
        _require_supported_v3(spec)
        return
    problems: dict[str, str] = {}

    r = spec.ratings
    if not _member(DissimilarityTarget, r.dissimilarity):
        problems["ratings.dissimilarity"] = f"unknown target {r.dissimilarity!r}"
    elif r.dissimilarity == DissimilarityTarget.CORRELATION_DISTANCE:
        problems["ratings.dissimilarity"] = _CONTRACT_3_ONLY
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
        if algorithm is LayoutAlgorithm.AIA_SMACOF_OBJECTS_V1:
            problems["layout.algorithm"] = _CONTRACT_3_ONLY
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
    elif layout.map_frame.method == MapFrameMethod.FIXED_RULER:
        problems["layout.map_frame.method"] = _CONTRACT_3_ONLY

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


# The audit's object map. Every value is the audit's (cited) or an AIA declaration
# (marked); plan ``sociomap-formula-corrections`` § 8.2, S2.
AIA_SOCIOMAP_V2 = SociomapSpecV3(
    methodology_version="aia-sociomap-2",
    ratings=RatingsSpecV3(
        scale_normalization=ScaleNormalization.DECLARED_ENDS_0_1,  # audit F1, eq. 3
        person_normalization=PersonNormalization.PERSON_MINMAX_ALL_RATED,  # audit F2, eq. 5
    ),
    relation=PairEvidenceSpec(
        estimator=RelationEstimator.WEIGHTED_PEARSON,  # the unit's; weighting AIA (AUDIT-F2)
        basis=PairEvidenceBasis.RESPONDENT_COUNT,  # audit F3; Kish is chunk 1d's (Q6)
        n_min=AUDIT_PROVISIONAL_N_MIN,  # audit F3's provisional working minimum, pending Q6
        confidence=0.95,  # audit F3
    ),
    layout=ObjectLayoutSpec(
        algorithm=LayoutAlgorithm.AIA_SMACOF_OBJECTS_V1,  # audit F6, F7
        dissimilarity=DissimilarityTarget.CORRELATION_DISTANCE,  # audit F6, eq. 13
        max_iterations=5000,  # AIA declaration
        tolerance=1e-12,  # AIA declaration: relative raw-stress improvement
        map_frame=MapFrameSpec(method=MapFrameMethod.FIXED_RULER, extent=FIXED_RULER_EXTENT),
    ),
    scores=ObjectScoresSpec(height=ObjectHeightMetric.MEAN_RATING_0_1),  # audit F8
    connectedness=ConnectednessSpec(resamples=500, seed=20261007),  # audit F9's B; OI-62 seed
    respondent_placement=None,  # chunk 3
    terrain=None,  # chunk 4b
)
