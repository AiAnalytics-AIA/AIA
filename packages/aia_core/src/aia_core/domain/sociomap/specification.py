"""Versioned Sociomapping methodology: the ``SociomapSpec`` contract (2) and contract 3.

Contract 3 (:class:`SociomapSpecV3`, presets :data:`AIA_SOCIOMAP_V2` and
:data:`AIA_SOCIOMAP_V3`) is the audit's object map and is described where it is defined,
below; everything in this docstring up to there is contract 2's, unchanged. A stored spec
names its contract (:func:`spec_payload`) and is read under it (:func:`read_spec`).

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

from pydantic import (
    BaseModel,
    ConfigDict,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

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
    "AIA_OBJECT_ENVELOPE",
    "AIA_SOCIOMAP_V1",
    "AIA_SOCIOMAP_V2",
    "AIA_SOCIOMAP_V3",
    "AIA_SOCIOMAP_V4",
    "AIA_SOCIOMAP_V5",
    "EFFECT_FLOOR_AIA_Q6",
    "FIXED_RULER_EXTENT",
    "LEGACY_CONNECTEDNESS_QUANTILES",
    "LEGACY_MIN_OBJECTS",
    "LEGACY_STRESS_BANDS",
    "PROVISIONAL_ENVELOPE_SIGMA",
    "SPEC_CONTRACTS",
    "SPEC_CONTRACT_V3",
    "SPEC_CONTRACT_VERSION",
    "ConnectednessSpec",
    "DissimilarityTarget",
    "IntervalMdsSpec",
    "KernelWidthBasis",
    "LayoutSpec",
    "MapCredibilitySpec",
    "MapFrameMethod",
    "MapFrameSpec",
    "MetricsSpec",
    "NoiseRuleSpec",
    "ObjectHeightMetric",
    "ObjectLayoutSpec",
    "ObjectScoresSpec",
    "ObjectTerrainSpec",
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
    "RespondentMapSpec",
    "ScaleNormalization",
    "SociomapSpec",
    "SociomapSpecV3",
    "SoftRankSpearmanSpec",
    "TasteSegmentsSpec",
    "TerrainMethod",
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


def _no_boolean_inside(v: object) -> object:
    """:func:`_not_boolean` for each entry of a list or tuple of numbers: ``[0.05, 0.1,
    true]`` would otherwise be stored as ``(0.05, 0.1, 1.0)``."""
    if isinstance(v, list | tuple):
        for entry in v:
            _not_boolean(entry)
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
# (F9). Respondent placement (chunk 3, F10's threshold open) has no member yet: a spec
# declares it ``None`` and an artifact says it was not computed. The envelope terrain
# (chunk 4b) is declared with its kernel width and the width's basis, or ``None`` (as
# ``aia-sociomap-2`` was pinned). Every field is required.


class ScaleNormalization(StrEnum):
    """How a rating reaches a common scale before anything else (audit F1, eq. 3)."""

    DECLARED_ENDS_0_1 = "declared_ends_0_1"


class PersonNormalization(StrEnum):
    """How each person's own use of the scale is removed (audit F2, eq. 5)."""

    #: Lowest rating 0, highest 1, over every rating item the person rated; a person with
    #: no spread is not placed (F11).
    PERSON_MINMAX_ALL_RATED = "person_minmax_all_rated"
    #: Each person's raw ratings of the mapped objects minus their own mean; fewer than two
    #: ratings or no spread is not placed. The signed-off methodology's (``aia-sociomap-5``).
    PERSON_MEAN_CENTRING = "person_mean_centring"


class RelationEstimator(StrEnum):
    """How a pair's relation is estimated from the person-scaled ratings."""

    #: The unit's weighted Pearson correlation (the weighting is AIA's reading where the
    #: audit is silent, register AUDIT-F2), signed, never mapped onto 1-10.
    WEIGHTED_PEARSON = "weighted_pearson"
    #: The signed-off methodology's (``aia-sociomap-5``): the unweighted pairwise Pearson of
    #: the centred ratings, corrected for the unrelated baseline ``r0`` centring alone gives,
    #: ``r~ = (r - r0) / (1 - r0)``; a pair is reliable by Benjamini-Hochberg on Fisher's p
    #: against ``r0`` and, when declared, the noise rule.
    BASELINE_CORRECTED_PEARSON = "baseline_corrected_pearson"


class PairEvidenceBasis(StrEnum):
    """What ``n`` a pair's status and interval read (audit F3; Q6, chunk 1d)."""

    #: The respondents who rated both objects (the audit's N_ij).
    RESPONDENT_COUNT = "respondent_count"
    #: Kish's effective n of those respondents' weights, ``(sum w)^2 / sum w^2``: under a
    #: weighted design the count overstates the evidence. AIA's Q6 decision (2026-10-09).
    KISH_EFFECTIVE_N = "kish_effective_n"


class ObjectHeightMetric(StrEnum):
    """What an object's height is under contract 3 (audit F8: the mean rating)."""

    #: The weighted mean of the object's ratings on the declared 0-1 scale (F1).
    MEAN_RATING_0_1 = "mean_rating_0_1"


class RatingsSpecV3(_Frozen):
    scale_normalization: str
    person_normalization: str


class NoiseRuleSpec(_Frozen):
    """The noise rule of the signed-off methodology: a pair BH keeps stays reliable only when
    its ``|r~|`` exceeds the 95th percentile of ``|r~|`` with one object shuffled, from
    ``permutations`` shuffles per object (half of them on incomplete data) drawn from
    ``seed``. ``enabled`` false declares the rule off."""

    enabled: bool
    permutations: int
    seed: int

    @field_validator("permutations", "seed", mode="before")
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)


class SoftRankSpearmanSpec(_Frozen):
    """The signed-off layout's soft-rank Spearman with Coulomb repulsion: it places maps of
    ``min_objects`` to ``max_objects`` objects (Interval MDS the others), with repulsion weight
    ``repulsion_weight``, ``restarts_below_ten_objects`` restarts below ten objects and
    ``restarts`` from ten on, random starts from ``seed``, at most ``max_passes`` passes each."""

    min_objects: int
    max_objects: int
    repulsion_weight: float
    restarts_below_ten_objects: int
    restarts: int
    seed: int
    max_passes: int

    @field_validator(
        "min_objects",
        "max_objects",
        "repulsion_weight",
        "restarts_below_ten_objects",
        "restarts",
        "seed",
        "max_passes",
        mode="before",
    )
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)


class IntervalMdsSpec(_Frozen):
    """The signed-off layout's Interval MDS: the classical start and ``random_starts`` random
    starts; a pair below the layout floor is pushed apart only when drawn closer than
    ``floor_fraction`` of the fitted distance of two unrelated objects."""

    random_starts: int
    floor_fraction: float

    @field_validator("random_starts", "floor_fraction", mode="before")
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)


class PairEvidenceSpec(_Frozen):
    """How a pair's relation is estimated and what it can be said to be (F3)."""

    estimator: str
    basis: str
    n_min: int
    confidence: float
    #: The practical floor on ``|r|`` (Q6's second gate, chunk 1d), recorded per pair as
    #: ``meets_effect_floor`` beside the status, never folded into it. ``None`` declares no
    #: such gate, which is what ``aia-sociomap-2`` was pinned with before the gate existed:
    #: the key is then left out of the stored form, so that pin and its fingerprint read
    #: unchanged.
    effect_floor: float | None = None
    #: The baseline-corrected relation's reliability (``aia-sociomap-5``): Benjamini-Hochberg's
    #: false-discovery rate over the known pairs, and the noise rule. ``None`` under every
    #: other estimator, left out of the stored form so earlier pins read unchanged.
    false_discovery_rate: float | None = None
    noise_rule: NoiseRuleSpec | None = None
    #: The ``|r~|`` from which the map's relation detail calls a relation clear ("zřetelný")
    #: rather than slight ("slabý"); wording only (``aia-sociomap-5``). ``None`` under every
    #: other estimator, left out of the stored form.
    clear_effect: float | None = None

    @field_validator(
        "n_min", "confidence", "effect_floor", "false_discovery_rate", "clear_effect", mode="before"
    )
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)

    @model_serializer(mode="wrap")
    def _without_absent_gate(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        for key in ("effect_floor", "false_discovery_rate", "noise_rule", "clear_effect"):
            if body.get(key) is None:
                body.pop(key, None)
        return body


class ObjectLayoutSpec(_Frozen):
    """The objects' map (F6, F7): its algorithm, its targets, its stopping rule, its frame.

    ``min_objects`` (how many objects a map needs) and ``stress_bands`` (the upper bounds of
    Stress-1's good, fair and weak bands; above the last is unreliable) were constants of the
    code until ``aia-sociomap-4`` declared them (plan ``methodology-tab`` S2a). ``None`` is a
    pin made before then: it computes with the value its code fixed, 3 and (0.05, 0.10, 0.20),
    and the key is left out of the stored form so that pin and its fingerprint read unchanged.
    """

    algorithm: str
    dissimilarity: str
    max_iterations: int
    tolerance: float
    map_frame: MapFrameSpec
    min_objects: int | None = None
    stress_bands: tuple[float, float, float] | None = None
    #: The signed-off methodology's layout pairs (``aia-sociomap-5``): pairs with at least
    #: ``layout_floor`` co-raters enter the layout; the sparse-design note is set when more
    #: than ``sparse_share`` of the pairs is below the layout floor or an object has fewer
    #: than ``min_layout_partners`` layout partners. ``None`` under every other estimator,
    #: left out of the stored form.
    layout_floor: int | None = None
    sparse_share: float | None = None
    min_layout_partners: int | None = None
    #: The signed-off layout (``aia-sociomap-5``): a layout pair's weight reaches 1 at
    #: ``layout_weight_full_at`` co-raters; the precision weights are floored at the largest
    #: over ``precision_weight_cap``; and its two methods. ``None`` under every other
    #: algorithm, left out of the stored form.
    layout_weight_full_at: int | None = None
    precision_weight_cap: float | None = None
    soft_rank_spearman: SoftRankSpearmanSpec | None = None
    interval_mds: IntervalMdsSpec | None = None

    @field_validator(
        "max_iterations",
        "tolerance",
        "min_objects",
        "layout_floor",
        "sparse_share",
        "min_layout_partners",
        "layout_weight_full_at",
        "precision_weight_cap",
        mode="before",
    )
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)

    @field_validator("stress_bands", mode="before")
    @classmethod
    def _no_bool_inside(cls, v: object) -> object:
        return _no_boolean_inside(v)

    @model_serializer(mode="wrap")
    def _without_undeclared(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        for key in ("min_objects", "stress_bands", *_LAYOUT_PAIR_FIELDS):
            if body.get(key) is None:
                body.pop(key, None)
        return body


#: :class:`ObjectLayoutSpec`'s layout-pair and signed-off layout fields, declared exactly
#: under the baseline-corrected estimator, which only the signed-off layout lays out.
_LAYOUT_PAIR_FIELDS: Final = (
    "layout_floor",
    "sparse_share",
    "min_layout_partners",
    "layout_weight_full_at",
    "precision_weight_cap",
    "soft_rank_spearman",
    "interval_mds",
)


class TerrainMethod(StrEnum):
    """How the object terrain is computed under contract 3 (audit F12, F13)."""

    #: ``z(q) = max_j h_j exp(-||q - y_j||^2 / 2 sigma^2)`` over the PRIMARY objects.
    OBJECT_ENVELOPE = "object_envelope"
    #: The signed-off methodology's (``aia-sociomap-5``): the same envelope over the PRIMARY
    #: objects' relative heights (min-max onto [floor, 1]; an object nobody rated is not
    #: placed), on a grid framed on the objects with a known pair, and with no cutoff, so
    #: every cell has a height.
    FRAMED_RELATIVE_ENVELOPE = "framed_relative_envelope"


class KernelWidthBasis(StrEnum):
    """Where a terrain's kernel width comes from: the audit leaves it to its author (A5)."""

    #: AIA's provisional width (2026-10-09), pending the audit's author: a hill falls below
    #: 5 % of its height at the correlation distance of r = 0.8, sqrt(2 (1 - 0.8)), so two
    #: objects less related than that never visibly raise each other's position.
    AIA_PROVISIONAL_R08_5PCT = "aia_provisional_r08_5pct"
    #: The signed-off methodology's own hill width: 6.75 frame units at 27 frame units to the
    #: ruler unit, so 0.25 on the ruler; the methodology states it without a derivation.
    SIGNED_OFF_METHODOLOGY = "signed_off_methodology"


class ObjectTerrainSpec(_Frozen):
    """The object terrain (chunk 4b): the envelope, its kernel and grid on the fixed ruler.

    The framed envelope (``aia-sociomap-5``) fits its grid to the map rather than declaring
    ``half_extent``, and has no ``kernel_cutoff``: both ``None``. It declares instead the share
    of the grid's half-width the objects fill, ``frame_fill``, and the lowest relative height
    of a hill, ``relative_height_floor``, which every other method leaves ``None``. A ``None``
    is left out of the stored form, so earlier pins read unchanged.
    """

    method: str
    sigma: float
    sigma_basis: str
    grid_resolution: int
    half_extent: float | None = None
    kernel_cutoff: float | None = None
    frame_fill: float | None = None
    relative_height_floor: float | None = None

    @field_validator(
        "sigma",
        "grid_resolution",
        "half_extent",
        "kernel_cutoff",
        "frame_fill",
        "relative_height_floor",
        mode="before",
    )
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)

    @model_serializer(mode="wrap")
    def _without_undeclared(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        for key in ("half_extent", "kernel_cutoff", "frame_fill", "relative_height_floor"):
            if body.get(key) is None:
                body.pop(key, None)
        return body


class ObjectScoresSpec(_Frozen):
    height: str


class ConnectednessSpec(_Frozen):
    """K100's respondent bootstrap (F9): how many resamples, from which seed, and the
    interval's quantiles. ``quantiles`` ``None`` is a pin made before ``aia-sociomap-4``
    declared them: it computes with (0.025, 0.975), and the key is left out of its stored
    form (see :class:`ObjectLayoutSpec`)."""

    resamples: int
    seed: int
    quantiles: tuple[float, float] | None = None

    @field_validator("resamples", "seed", mode="before")
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)

    @field_validator("quantiles", mode="before")
    @classmethod
    def _no_bool_inside(cls, v: object) -> object:
        return _no_boolean_inside(v)

    @model_serializer(mode="wrap")
    def _without_undeclared(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        if body.get("quantiles") is None:
            body.pop("quantiles", None)
        return body


class MapCredibilitySpec(_Frozen):
    """The signed-off methodology's map credibility (``aia-sociomap-5``): the split-half check
    over ``split_half_splits`` random halvings of the respondents drawn from
    ``split_half_seed``, the map weakly determined below ``split_half_threshold``; and the
    uncertainty radius from ``bootstrap_resamples`` respondent bootstraps drawn from
    ``bootstrap_seed``, ``safety_factor`` times the median object spread."""

    split_half_threshold: float
    split_half_splits: int
    split_half_seed: int
    bootstrap_resamples: int
    bootstrap_seed: int
    safety_factor: float

    @field_validator(
        "split_half_threshold",
        "split_half_splits",
        "split_half_seed",
        "bootstrap_resamples",
        "bootstrap_seed",
        "safety_factor",
        mode="before",
    )
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)


class RespondentMapSpec(_Frozen):
    """The signed-off methodology's respondent map (``aia-sociomap-5``): each respondent with
    at least ``min_ratings`` ratings of the mapped objects placed by the vector model, PLACED
    when the chance test's p-value is at most ``chance_level`` and FADED otherwise; the map
    informative from ``informative_min_objects`` objects; the density of the PLACED
    respondents with a kernel ``density_sigma`` ruler units wide."""

    chance_level: float
    min_ratings: int
    informative_min_objects: int
    density_sigma: float

    @field_validator(
        "chance_level", "min_ratings", "informative_min_objects", "density_sigma", mode="before"
    )
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)


class TasteSegmentsSpec(_Frozen):
    """The signed-off methodology's taste segments (``aia-sociomap-5``): a mixture of 1 to
    ``max_segments`` segments on the vector-model slopes of the respondents with at least
    ``min_ratings`` ratings, chosen by the likelihood penalised ``penalty_factor`` times BIC,
    looked for from ``min_respondents`` such respondents; shown only when the gain beats
    ``shuffles`` within-respondent shuffles (0 switches the guard off); stepped down while the
    last segment adds less than ``min_gain_share`` of the gain, a segment holds less than
    ``min_segment_share`` of the respondents or two segments are less than ``min_separation``
    apart. A respondent is coloured from membership ``colour_membership`` and clearly placed;
    segments are distinct from separation ``distinct_separation``. Profiles: Benjamini-Hochberg
    at ``profile_false_discovery_rate``, ``profile_top`` objects named. The decision is taken
    on ``consensus_maps`` maps (the shown one and maps of ratings jittered by ``jitter``) when
    the set has at least ``consensus_min_objects`` objects, borderline within
    ``borderline_margin`` of a zero mean margin. ``seed`` starts every generator."""

    max_segments: int
    penalty_factor: float
    shuffles: int
    min_respondents: int
    min_ratings: int
    min_gain_share: float
    min_segment_share: float
    min_separation: float
    colour_membership: float
    distinct_separation: float
    profile_false_discovery_rate: float
    profile_top: int
    consensus_maps: int
    consensus_min_objects: int
    borderline_margin: float
    jitter: float
    seed: int

    @field_validator("*", mode="before")
    @classmethod
    def _no_bool(cls, v: object) -> object:
        return _not_boolean(v)


class SociomapSpecV3(_Frozen):
    """Every methodology decision behind one contract-3 Sociomap (the audit's object map).

    ``respondent_placement`` is declared ``None``: no member is built (chunk 3 waits on a
    decision the audit leaves to its author), and a value is refused by
    :func:`require_supported` rather than ignored. ``terrain`` is the object envelope
    (chunk 4b) or ``None``, which computes no terrain. ``credibility``, ``respondent_map`` and
    ``segments`` are declared exactly under the baseline-corrected relation
    (``aia-sociomap-5``); ``None`` is left out of the stored form, so earlier pins read
    unchanged.
    """

    methodology_version: str
    ratings: RatingsSpecV3
    relation: PairEvidenceSpec
    layout: ObjectLayoutSpec
    scores: ObjectScoresSpec
    connectedness: ConnectednessSpec
    respondent_placement: str | None
    terrain: ObjectTerrainSpec | None
    credibility: MapCredibilitySpec | None = None
    respondent_map: RespondentMapSpec | None = None
    segments: TasteSegmentsSpec | None = None

    @field_validator("methodology_version")
    @classmethod
    def _named(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("methodology_version must be stated; blank is not a default")
        return v

    @model_serializer(mode="wrap")
    def _without_undeclared(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        for key in ("credibility", "respondent_map", "segments"):
            if body.get(key) is None:
                body.pop(key, None)
        return body

    def fingerprint(self) -> str:
        """Stable SHA256 over the whole methodology, its contract included."""
        return fingerprint({"contract_version": SPEC_CONTRACT_V3, **self.model_dump(mode="json")})


#: The fixed ruler's extent: the largest correlation distance, two opposite objects.
FIXED_RULER_EXTENT: Final = 2.0
#: The smallest ``n_min`` a status can mean anything at: the Fisher interval needs four.
_V3_N_MIN_FLOOR: Final = 4
#: What a map needs before ``aia-sociomap-4`` declared it: three objects. Two points have no
#: shape, and the layout refuses fewer (``layout.fit_smacof_objects``).
LEGACY_MIN_OBJECTS: Final = 3
#: Stress-1's band bounds before ``aia-sociomap-4`` declared them: the audit's < 0.05 good,
#: < 0.10 fair, < 0.20 weak, above unreliable (``view.STRESS_QUALITY_BANDS``).
LEGACY_STRESS_BANDS: Final = (0.05, 0.10, 0.20)
#: K100's interval quantiles before ``aia-sociomap-4`` declared them
#: (``metrics.CONNECTEDNESS_QUANTILES``).
LEGACY_CONNECTEDNESS_QUANTILES: Final = (0.025, 0.975)


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
        problems["relation.basis"] = f"unknown basis {rel.basis!r}"
    if rel.effect_floor is not None and not (
        math.isfinite(rel.effect_floor) and 0.0 < rel.effect_floor < 1.0
    ):
        problems["relation.effect_floor"] = (
            f"an effect floor lies strictly between 0 and 1; got {rel.effect_floor!r}"
        )
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
        if algorithm not in _OBJECT_LAYOUTS:
            problems["layout.algorithm"] = (
                f"{algorithm.value} places respondents and objects together (contract 2); "
                "contract 3 maps the objects alone"
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
    least = (
        _SIGNED_OFF_MIN_OBJECTS
        if layout.algorithm == LayoutAlgorithm.SOFT_RANK_SPEARMAN_OR_INTERVAL_MDS
        else LEGACY_MIN_OBJECTS
    )
    if layout.min_objects is not None and layout.min_objects < least:
        problems["layout.min_objects"] = (
            f"a map needs at least {least} objects: SMACOF needs three, the signed-off layout "
            f"draws two at their target distance and one has no map; got {layout.min_objects}"
        )
    if layout.stress_bands is not None:
        bands = layout.stress_bands
        if not all(math.isfinite(b) and b > 0 for b in bands) or not (
            bands[0] < bands[1] < bands[2]
        ):
            problems["layout.stress_bands"] = (
                f"three positive bounds, each above the last (good < fair < weak); got "
                f"{list(bands)}"
            )
    if spec.connectedness.resamples < 1:
        problems["connectedness.resamples"] = "resamples must be at least 1"
    quantiles = spec.connectedness.quantiles
    if quantiles is not None and not (
        all(math.isfinite(q) for q in quantiles) and 0.0 < quantiles[0] < quantiles[1] < 1.0
    ):
        problems["connectedness.quantiles"] = (
            f"two quantiles strictly between 0 and 1, the lower first; got {list(quantiles)}"
        )
    if spec.respondent_placement is not None:
        problems["respondent_placement"] = (
            "respondent placement is chunk 3's (ideal points, F10) and is not built: its "
            "misfit threshold is open (plan § 4a, 0b); declare null"
        )
    if spec.terrain is not None:
        problems.update(_terrain_problems(spec.terrain))
    problems.update(_baseline_corrected_problems(spec))
    if problems:
        raise UnsupportedMethodology(problems)


#: The layouts contract 3 maps the objects alone by.
_OBJECT_LAYOUTS: Final = (
    LayoutAlgorithm.AIA_SMACOF_OBJECTS_V1,
    LayoutAlgorithm.SOFT_RANK_SPEARMAN_OR_INTERVAL_MDS,
)
#: The fewest objects the signed-off layout maps: Interval MDS draws two at their distance.
_SIGNED_OFF_MIN_OBJECTS: Final = 2

#: ``relation.confidence`` under the baseline-corrected relation: required by the shape, read
#: by nothing, so held at ``aia-sociomap-4``'s value.
_UNREAD_CONFIDENCE: Final = 0.95
#: SMACOF's ``layout.max_iterations`` and ``layout.tolerance`` under the signed-off layout:
#: required by the shape, read by nothing, so held at ``aia-sociomap-4``'s values.
_UNREAD_MAX_ITERATIONS: Final = 5000
_UNREAD_TOLERANCE: Final = 1e-12


def _baseline_corrected_problems(spec: SociomapSpecV3) -> dict[str, str]:
    """The signed-off methodology's relation comes whole: mean-centred ratings, its own
    reliability and layout-pair fields, all declared together and never under another
    estimator."""
    problems: dict[str, str] = {}
    rel, layout = spec.relation, spec.layout
    corrected = rel.estimator == RelationEstimator.BASELINE_CORRECTED_PEARSON
    if corrected != (layout.algorithm == LayoutAlgorithm.SOFT_RANK_SPEARMAN_OR_INTERVAL_MDS):
        problems["layout.algorithm"] = (
            "the signed-off layout reads the baseline-corrected relation's layout pairs, and "
            "that relation is laid out by nothing else: declare "
            "aia_soft_rank_spearman_or_interval_mds_v1 with baseline_corrected_pearson, never "
            "one without the other"
        )
    if corrected != (spec.ratings.person_normalization == PersonNormalization.PERSON_MEAN_CENTRING):
        problems["ratings.person_normalization"] = (
            "the baseline-corrected relation reads each person's mean-centred ratings and "
            "nothing else does: declare person_mean_centring with baseline_corrected_pearson, "
            "never one without the other"
        )
    declared: dict[str, object] = {
        "relation.false_discovery_rate": rel.false_discovery_rate,
        "relation.noise_rule": rel.noise_rule,
        **{f"layout.{key}": getattr(layout, key) for key in _LAYOUT_PAIR_FIELDS},
        "credibility": spec.credibility,
        "respondent_map": spec.respondent_map,
        "segments": spec.segments,
    }
    # The clear relation's wording may be left out (a version saved before it), never misplaced.
    clear = rel.clear_effect
    if clear is not None and not corrected:
        problems["relation.clear_effect"] = (
            "only the baseline-corrected relation reads it; declare null"
        )
    elif clear is not None and not (math.isfinite(clear) and 0.0 < clear < 1.0):
        problems["relation.clear_effect"] = (
            f"a clear relation's |r~| lies strictly between 0 and 1; got {clear!r}"
        )
    if not corrected:
        for path, value in declared.items():
            if value is not None:
                problems[path] = "only the baseline-corrected relation reads it; declare null"
        return problems
    for path, value in declared.items():
        if value is None:
            problems[path] = "the baseline-corrected relation reads it; declare it"
    if rel.basis != PairEvidenceBasis.RESPONDENT_COUNT:
        problems["relation.basis"] = (
            "the baseline-corrected relation is unweighted: its n is the count of respondents "
            "who rated both objects"
        )
    if rel.effect_floor is not None:
        problems["relation.effect_floor"] = (
            "the baseline-corrected relation has no effect floor; declare null"
        )
    rate = rel.false_discovery_rate
    if rate is not None and not (math.isfinite(rate) and 0.0 < rate < 1.0):
        problems["relation.false_discovery_rate"] = (
            f"a false-discovery rate lies strictly between 0 and 1; got {rate!r}"
        )
    if rel.confidence != _UNREAD_CONFIDENCE:
        problems["relation.confidence"] = (
            f"the baseline-corrected relation reads no interval; keep {_UNREAD_CONFIDENCE} so "
            "the unread value is never taken for an edit"
        )
    if rel.noise_rule is not None and rel.noise_rule.permutations < 2:
        problems["relation.noise_rule.permutations"] = (
            "at least 2 shuffles per object: incomplete data takes half of them"
        )
    if rel.noise_rule is not None and rel.noise_rule.seed < 0:
        problems["relation.noise_rule.seed"] = (
            f"the generator's seed is a non-negative integer; got {rel.noise_rule.seed}"
        )
    floor = layout.layout_floor
    if floor is not None and not 1 <= floor <= rel.n_min:
        problems["layout.layout_floor"] = (
            f"the layout floor lies between 1 and the status floor n_min {rel.n_min}; got {floor}"
        )
    share = layout.sparse_share
    if share is not None and not (math.isfinite(share) and 0.0 <= share < 1.0):
        problems["layout.sparse_share"] = f"a share lies in [0, 1); got {share!r}"
    partners = layout.min_layout_partners
    if partners is not None and partners < 0:
        problems["layout.min_layout_partners"] = f"a count of partners; got {partners}"
    if layout.stress_bands is not None:
        problems["layout.stress_bands"] = (
            "the signed-off layout computes no Stress-1, so it has no bands; declare null"
        )
    if layout.max_iterations != _UNREAD_MAX_ITERATIONS:
        problems["layout.max_iterations"] = (
            f"the signed-off layout reads no SMACOF iterations; keep {_UNREAD_MAX_ITERATIONS} so "
            "the unread value is never taken for an edit"
        )
    if layout.tolerance != _UNREAD_TOLERANCE:
        problems["layout.tolerance"] = (
            f"the signed-off layout reads no SMACOF tolerance; keep {_UNREAD_TOLERANCE} so the "
            "unread value is never taken for an edit"
        )
    full_at = layout.layout_weight_full_at
    if full_at is not None and full_at <= 3:
        problems["layout.layout_weight_full_at"] = (
            f"a layout weight is (n - 3) / (n_full - 3): n_full lies above 3; got {full_at}"
        )
    cap = layout.precision_weight_cap
    if cap is not None and not (math.isfinite(cap) and cap >= 1.0):
        problems["layout.precision_weight_cap"] = f"a cap is at least 1; got {cap!r}"
    problems.update(_soft_rank_spearman_problems(layout.soft_rank_spearman))
    problems.update(_credibility_problems(spec.credibility))
    problems.update(_respondent_map_problems(spec))
    problems.update(_segments_problems(spec.segments))
    imds = layout.interval_mds
    if imds is not None and imds.random_starts < 0:
        problems["layout.interval_mds.random_starts"] = (
            f"a count of random starts; got {imds.random_starts}"
        )
    fraction = None if imds is None else imds.floor_fraction
    if fraction is not None and not (math.isfinite(fraction) and 0 <= fraction <= 1):
        problems["layout.interval_mds.floor_fraction"] = (
            f"a fraction of the unrelated distance lies in [0, 1]; got {fraction!r}"
        )
    return problems


def _soft_rank_spearman_problems(srs: SoftRankSpearmanSpec | None) -> dict[str, str]:
    problems: dict[str, str] = {}
    if srs is None:
        return problems
    path = "layout.soft_rank_spearman"
    if not _SIGNED_OFF_MIN_OBJECTS <= srs.min_objects <= srs.max_objects:
        problems[f"{path}.min_objects"] = (
            f"{_SIGNED_OFF_MIN_OBJECTS} <= min_objects <= max_objects; got {srs.min_objects} and "
            f"{srs.max_objects}"
        )
    if not (math.isfinite(srs.repulsion_weight) and srs.repulsion_weight >= 0):
        problems[f"{path}.repulsion_weight"] = (
            f"a repulsion weight is non-negative; got {srs.repulsion_weight!r}"
        )
    for key in ("restarts_below_ten_objects", "restarts", "max_passes"):
        if getattr(srs, key) < 1:
            problems[f"{path}.{key}"] = f"at least 1; got {getattr(srs, key)}"
    if srs.seed < 0:
        problems[f"{path}.seed"] = f"the generator's seed is a non-negative integer; got {srs.seed}"
    return problems


def _credibility_problems(credibility: MapCredibilitySpec | None) -> dict[str, str]:
    problems: dict[str, str] = {}
    if credibility is None:
        return problems
    threshold = credibility.split_half_threshold
    if not (math.isfinite(threshold) and 0.0 <= threshold <= 1.0):
        problems["credibility.split_half_threshold"] = (
            f"a share of triplets lies in [0, 1]; got {threshold!r}"
        )
    if credibility.split_half_splits < 1:
        problems["credibility.split_half_splits"] = (
            f"at least 1; got {credibility.split_half_splits}"
        )
    if credibility.bootstrap_resamples < 2:
        problems["credibility.bootstrap_resamples"] = (
            f"at least 2: one bootstrap map has no spread; got {credibility.bootstrap_resamples}"
        )
    for key in ("split_half_seed", "bootstrap_seed"):
        if getattr(credibility, key) < 0:
            problems[f"credibility.{key}"] = (
                f"the generator's seed is a non-negative integer; got {getattr(credibility, key)}"
            )
    safety = credibility.safety_factor
    if not (math.isfinite(safety) and safety > 0.0):
        problems["credibility.safety_factor"] = f"a safety factor is positive; got {safety!r}"
    return problems


#: The vector model's parameters per respondent (an intercept and two slopes): fewer ratings
#: than this cannot be fitted, and exactly this many fit any ratings.
_VECTOR_MODEL_PARAMETERS: Final = 3


def _respondent_map_problems(spec: SociomapSpecV3) -> dict[str, str]:
    problems: dict[str, str] = {}
    declared = spec.respondent_map
    if declared is None:
        return problems
    if spec.terrain is None or spec.terrain.method != TerrainMethod.FRAMED_RELATIVE_ENVELOPE:
        problems["respondent_map"] = (
            "the respondent density is drawn on the framed terrain's grid: declare the terrain "
            "framed_relative_envelope"
        )
    level = declared.chance_level
    if not (math.isfinite(level) and 0.0 < level < 1.0):
        problems["respondent_map.chance_level"] = (
            f"a chance-test level lies strictly between 0 and 1; got {level!r}"
        )
    if declared.min_ratings < _VECTOR_MODEL_PARAMETERS:
        problems["respondent_map.min_ratings"] = (
            f"at least {_VECTOR_MODEL_PARAMETERS}: the vector model fits an intercept and two "
            f"slopes; got {declared.min_ratings}"
        )
    if declared.informative_min_objects < 1:
        problems["respondent_map.informative_min_objects"] = (
            f"a count of objects, at least 1; got {declared.informative_min_objects}"
        )
    sigma = declared.density_sigma
    if not (math.isfinite(sigma) and sigma > 0.0):
        problems["respondent_map.density_sigma"] = (
            f"a kernel width is positive and finite; got {sigma!r}"
        )
    return problems


def _segments_problems(segments: TasteSegmentsSpec | None) -> dict[str, str]:
    problems: dict[str, str] = {}
    if segments is None:
        return problems
    path = "segments"
    if segments.max_segments < 2:
        problems[f"{path}.max_segments"] = (
            f"at least 2: one segment is no segmentation; got {segments.max_segments}"
        )
    elif segments.min_respondents < segments.max_segments:
        problems[f"{path}.min_respondents"] = (
            f"at least max_segments {segments.max_segments}: each start draws one respondent "
            f"per segment; got {segments.min_respondents}"
        )
    if segments.min_ratings <= _VECTOR_MODEL_PARAMETERS:
        problems[f"{path}.min_ratings"] = (
            f"more than {_VECTOR_MODEL_PARAMETERS}: a slope's noise is estimated from the "
            f"ratings beyond the vector model's intercept and two slopes; got "
            f"{segments.min_ratings}"
        )
    for key in ("penalty_factor", "jitter"):
        value = getattr(segments, key)
        if not (math.isfinite(value) and value > 0.0):
            problems[f"{path}.{key}"] = f"positive and finite; got {value!r}"
    for key in ("min_separation", "distinct_separation", "borderline_margin"):
        value = getattr(segments, key)
        if not (math.isfinite(value) and value >= 0.0):
            problems[f"{path}.{key}"] = f"non-negative and finite; got {value!r}"
    for key in ("min_gain_share", "min_segment_share"):
        value = getattr(segments, key)
        if not (math.isfinite(value) and 0.0 <= value <= 1.0):
            problems[f"{path}.{key}"] = f"a share lies in [0, 1]; got {value!r}"
    membership = segments.colour_membership
    if not (math.isfinite(membership) and 0.0 < membership <= 1.0):
        problems[f"{path}.colour_membership"] = (
            f"a membership probability lies in (0, 1]; got {membership!r}"
        )
    rate = segments.profile_false_discovery_rate
    if not (math.isfinite(rate) and 0.0 < rate < 1.0):
        problems[f"{path}.profile_false_discovery_rate"] = (
            f"a false-discovery rate lies strictly between 0 and 1; got {rate!r}"
        )
    for key in ("profile_top", "consensus_maps", "consensus_min_objects"):
        if getattr(segments, key) < 1:
            problems[f"{path}.{key}"] = f"at least 1; got {getattr(segments, key)}"
    if segments.shuffles < 0:
        problems[f"{path}.shuffles"] = (
            f"a count of shuffles, 0 to switch the guard off; got {segments.shuffles}"
        )
    if segments.seed < 0:
        problems[f"{path}.seed"] = (
            f"the generator's seed is a non-negative integer; got {segments.seed}"
        )
    return problems


#: The largest grid a terrain may declare: (N + 1)^2 cells are stored in the artifact.
_MAX_TERRAIN_GRID: Final = 256


def _terrain_problems(terrain: ObjectTerrainSpec) -> dict[str, str]:
    problems: dict[str, str] = {}
    if not _member(TerrainMethod, terrain.method):
        problems["terrain.method"] = f"unknown terrain method {terrain.method!r}"
    if not _member(KernelWidthBasis, terrain.sigma_basis):
        problems["terrain.sigma_basis"] = f"unknown kernel width basis {terrain.sigma_basis!r}"
    if not (math.isfinite(terrain.sigma) and terrain.sigma > 0.0):
        problems["terrain.sigma"] = f"sigma must be positive and finite; got {terrain.sigma!r}"
    if not 1 <= terrain.grid_resolution <= _MAX_TERRAIN_GRID:
        problems["terrain.grid_resolution"] = (
            f"grid_resolution must lie in 1..{_MAX_TERRAIN_GRID}; got {terrain.grid_resolution}"
        )
    if terrain.method == TerrainMethod.FRAMED_RELATIVE_ENVELOPE:
        for key in ("half_extent", "kernel_cutoff"):
            if getattr(terrain, key) is not None:
                problems[f"terrain.{key}"] = (
                    "the framed envelope fits its grid to the map and lets every hill reach "
                    "every cell; declare null"
                )
        fill, floor = terrain.frame_fill, terrain.relative_height_floor
        if fill is None or not (math.isfinite(fill) and 0.0 < fill <= 1.0):
            problems["terrain.frame_fill"] = (
                f"the share of the grid the objects fill lies in (0, 1]; got {fill!r}"
            )
        if floor is None or not (math.isfinite(floor) and 0.0 <= floor < 1.0):
            problems["terrain.relative_height_floor"] = (
                f"the lowest relative height lies in [0, 1); got {floor!r}"
            )
        return problems
    for key in ("frame_fill", "relative_height_floor"):
        if getattr(terrain, key) is not None:
            problems[f"terrain.{key}"] = "only the framed envelope reads it; declare null"
    half, cutoff = terrain.half_extent, terrain.kernel_cutoff
    if half is None or not (math.isfinite(half) and half >= FIXED_RULER_EXTENT):
        problems["terrain.half_extent"] = (
            f"the terrain must cover the fixed ruler, half_extent >= {FIXED_RULER_EXTENT}; "
            f"got {half!r}"
        )
    if cutoff is None or not (math.isfinite(cutoff) and 0.0 < cutoff < 1.0):
        problems["terrain.kernel_cutoff"] = (
            f"kernel_cutoff must lie strictly between 0 and 1; got {cutoff!r}"
        )
    return problems


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
        if algorithm in _OBJECT_LAYOUTS:
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


#: The provisional kernel width of :data:`KernelWidthBasis.AIA_PROVISIONAL_R08_5PCT`:
#: ``sqrt(0.4) / sqrt(2 ln 20)`` is 0.258, rounded down to 0.25 so the 5 % is kept.
PROVISIONAL_ENVELOPE_SIGMA: Final = 0.25

#: The object terrain of ``aia-sociomap-3``: the envelope on a 65 x 65 grid covering the
#: fixed ruler and three kernel widths beyond it, with the unit's cutoff (``terrain66``).
AIA_OBJECT_ENVELOPE = ObjectTerrainSpec(
    method=TerrainMethod.OBJECT_ENVELOPE,  # audit F12, F13
    sigma=PROVISIONAL_ENVELOPE_SIGMA,  # AIA provisional (A5 open)
    sigma_basis=KernelWidthBasis.AIA_PROVISIONAL_R08_5PCT,
    grid_resolution=64,  # AIA declaration
    half_extent=FIXED_RULER_EXTENT + 3 * PROVISIONAL_ENVELOPE_SIGMA,  # AIA declaration
    kernel_cutoff=0.0005,  # the unit's terrain66 cutoff
)

#: Q6's practical floor on ``|r|``, AIA's decision of 2026-10-09 (the audit leaves it open;
#: its author may replace it). Below it a RELIABLE relation is precisely small, not strong.
EFFECT_FLOOR_AIA_Q6: Final = 0.10

# The audit's object map under AIA's Q5-Q7 decisions of 2026-10-09 (plan
# ``sociomap-formula-corrections`` § 4a): positions from co-movement with level shown apart
# (Q5 (c)); the pair evidence policy's two gates on Kish's n (Q6 (b) + (c)); mean rating as
# the default height (Q7 (d) with (a)). Everything else is ``aia-sociomap-2``'s, unchanged.
AIA_SOCIOMAP_V3 = AIA_SOCIOMAP_V2.model_copy(
    update={
        "methodology_version": "aia-sociomap-3",
        "relation": AIA_SOCIOMAP_V2.relation.model_copy(
            update={
                "basis": PairEvidenceBasis.KISH_EFFECTIVE_N,  # AIA Q6 (c)
                "effect_floor": EFFECT_FLOOR_AIA_Q6,  # AIA Q6 (b)
            }
        ),
        "terrain": AIA_OBJECT_ENVELOPE,  # chunk 4b, audit F12 with AIA's provisional sigma
    }
)

# ``aia-sociomap-3`` with every value its code fixed declared in the specification (plan
# ``methodology-tab`` S2a): the same numbers, so the same maps, now the methodologist's to edit.
# A run pins it from S2a on; a run that pinned -3 keeps -3 and computes exactly as it did.
AIA_SOCIOMAP_V4 = AIA_SOCIOMAP_V3.model_copy(
    update={
        "methodology_version": "aia-sociomap-4",
        "layout": AIA_SOCIOMAP_V3.layout.model_copy(
            update={"min_objects": LEGACY_MIN_OBJECTS, "stress_bands": LEGACY_STRESS_BANDS}
        ),
        "connectedness": AIA_SOCIOMAP_V3.connectedness.model_copy(
            update={"quantiles": LEGACY_CONNECTEDNESS_QUANTILES}
        ),
    }
)

# The signed-off AIA Sociomapa methodology (plan ``signed-off-sociomap-method``): each person's
# raw ratings mean-centred, the unweighted baseline-corrected relation with its status floor,
# Benjamini-Hochberg with the noise rule, the layout pairs and the sparse-design note; the
# objects placed by soft-rank Spearman with Coulomb repulsion or, by the fixed object-count
# rule, Interval MDS; no Stress-1; the survey-weighted mean rating as height, and the envelope of
# relative heights on a grid framed on the map; the split-half check and the uncertainty radius;
# the respondents placed by the vector model with the chance test, and their density on the
# map's frame; taste segments on the respondents' slopes; every value the methodology's own. What
# every new run pins, alone; approved for reports in the Sociomap register at its fingerprint.
AIA_SOCIOMAP_V5 = AIA_SOCIOMAP_V4.model_copy(
    update={
        "methodology_version": "aia-sociomap-5",
        "ratings": AIA_SOCIOMAP_V4.ratings.model_copy(
            update={"person_normalization": PersonNormalization.PERSON_MEAN_CENTRING}
        ),
        "relation": AIA_SOCIOMAP_V4.relation.model_copy(
            update={
                "estimator": RelationEstimator.BASELINE_CORRECTED_PEARSON,
                "basis": PairEvidenceBasis.RESPONDENT_COUNT,
                "n_min": 10,
                "effect_floor": None,
                "false_discovery_rate": 0.05,
                "noise_rule": NoiseRuleSpec(enabled=True, permutations=100, seed=0),
                "clear_effect": 0.3,
            }
        ),
        "layout": AIA_SOCIOMAP_V4.layout.model_copy(
            update={
                "algorithm": LayoutAlgorithm.SOFT_RANK_SPEARMAN_OR_INTERVAL_MDS,
                "min_objects": _SIGNED_OFF_MIN_OBJECTS,
                "stress_bands": None,
                "layout_floor": 5,
                "sparse_share": 0.30,
                "min_layout_partners": 3,
                "layout_weight_full_at": 20,
                "precision_weight_cap": 20.0,
                "soft_rank_spearman": SoftRankSpearmanSpec(
                    min_objects=4,
                    max_objects=163,
                    repulsion_weight=0.15,
                    restarts_below_ten_objects=15,
                    restarts=10,
                    seed=1,
                    max_passes=500,
                ),
                "interval_mds": IntervalMdsSpec(random_starts=2, floor_fraction=0.5),
            }
        ),
        "credibility": MapCredibilitySpec(
            split_half_threshold=0.59,
            split_half_splits=2,
            split_half_seed=0,
            bootstrap_resamples=20,
            bootstrap_seed=0,
            safety_factor=1.2,
        ),
        "respondent_map": RespondentMapSpec(
            chance_level=0.10, min_ratings=3, informative_min_objects=6, density_sigma=0.35
        ),
        "segments": TasteSegmentsSpec(
            max_segments=4,
            penalty_factor=0.5,
            shuffles=20,
            min_respondents=30,
            min_ratings=5,
            min_gain_share=0.10,
            min_segment_share=0.05,
            min_separation=1.8,
            colour_membership=0.8,
            distinct_separation=3.5,
            profile_false_discovery_rate=0.05,
            profile_top=3,
            consensus_maps=5,
            consensus_min_objects=5,
            borderline_margin=4.0,
            jitter=1e-9,
            seed=0,
        ),
        "terrain": ObjectTerrainSpec(
            method=TerrainMethod.FRAMED_RELATIVE_ENVELOPE,
            sigma=0.25,
            sigma_basis=KernelWidthBasis.SIGNED_OFF_METHODOLOGY,
            grid_resolution=84,
            frame_fill=0.70,
            relative_height_floor=0.15,
        ),
    }
)
