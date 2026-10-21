"""The contract-3 Sociomap: the audit's object map, its inputs and its artifact.

Plan ``sociomap-formula-corrections`` § 8.2, S2. :class:`ObjectMapInputs` is what
:func:`~.engine_v2.compute_object_map` reads: every rating item of the study with its
declared scale (the *rating universe*), every respondent's raw ratings of them, the
respondents' weights, and the family being mapped with each object's role.
:class:`SociomapArtifactV3` is what it produces: the canonical, immutable object map.

Beside the contract-2 artifact (:class:`~.models.SociomapArtifact`), never instead of it:
a stored contract-2 payload is read exactly as before, and :func:`read_artifact` reads each
payload under the contract it names. What contract 3 does not compute -- respondent
placement (chunk 3) outside a mapped ``aia-sociomap-5`` map, and the terrain where the spec
declares none or nothing is mapped -- is a :class:`NotComputed` block with its reason, never
an empty list a reader could take for "nobody" or "flat".

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from ..pipeline import fingerprint
from .metrics import ObjectRole
from .models import ArtifactIntegrityError, SociomapArtifact
from .pairs import PairRelations
from .specification import SociomapSpecV3
from .terrain import EnvelopeParameters, EnvelopeTerrain

__all__ = [
    "ARTIFACT_CONTRACT_V3",
    "OBJECT_MAP_IMPLEMENTATION",
    "OBJECT_MAP_IMPLEMENTATION_VERSION",
    "CredibilityRule",
    "MapCredibility",
    "MapOutcome",
    "NoSegmentsReason",
    "NotComputed",
    "NotMappable",
    "NotMappableReason",
    "ObjectHeights",
    "ObjectMapInputs",
    "ObjectMapLayout",
    "ObjectMapProvenance",
    "ObjectMapSupport",
    "RatingItem",
    "RespondentDensity",
    "RespondentMap",
    "RespondentStatus",
    "SegmentDecision",
    "SegmentHint",
    "SegmentProfile",
    "SociomapArtifactV3",
    "SparseDesign",
    "TasteSegments",
    "read_artifact",
    "read_object_maps",
]

ARTIFACT_CONTRACT_V3: Literal["3"] = "3"

#: The object map's implementation, recorded on every contract-3 artifact. Its own version,
#: not the contract-2 engine's: a change to one never invalidates the other's maps.
OBJECT_MAP_IMPLEMENTATION: Final = "aia_core.domain.sociomap.engine_v2"
OBJECT_MAP_IMPLEMENTATION_VERSION: Final = "1.0.0"

Point = tuple[float, float]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _no_bool(value: Any, where: str) -> Any:
    if isinstance(value, bool):
        raise ValueError(f"{where}: expected a number, not a boolean")
    if isinstance(value, list | tuple):
        for item in value:
            _no_bool(item, where)
    return value


def _unique(ids: tuple[str, ...], what: str) -> tuple[str, ...]:
    if any(not i.strip() for i in ids):
        raise ValueError(f"{what} must be non-blank")
    if len(set(ids)) != len(ids):
        raise ValueError(f"{what} must be unique")
    return ids


class RatingItem(_Frozen):
    """One rating item of the study: its id and the ends of its declared scale (audit F1)."""

    item_id: str
    scale_min: float
    scale_max: float

    @field_validator("scale_min", "scale_max", mode="before")
    @classmethod
    def _numbers(cls, v: Any) -> Any:
        return _no_bool(v, "scale")

    @model_validator(mode="after")
    def _scale(self) -> Self:
        if not (math.isfinite(self.scale_min) and math.isfinite(self.scale_max)):
            raise ValueError(f"{self.item_id}: the scale's ends must be finite")
        if not self.scale_max > self.scale_min:
            raise ValueError(f"{self.item_id}: scale_max must exceed scale_min")
        return self


class ObjectMapInputs(_Frozen):
    """What one object map reads: the whole rating universe, and the family mapped.

    ``values[k][i]`` is respondent ``k``'s raw rating of item ``i`` on that item's declared
    scale, ``None`` unrated. Every item of the universe enters each person's min-max (F2);
    only the ``object_ids`` are mapped, each read from its item in ``object_items`` (an
    object id belongs to its family, an item id to the study, so the same object rated in
    two families is two items). ``roles`` declares every mapped object PRIMARY or
    SECONDARY: nothing defaults.
    """

    respondent_ids: tuple[str, ...]
    #: The panel person each respondent was built from (``FieldworkRespondent.donor_id``):
    #: recorded on the map's support, never read by a formula here.
    donor_ids: tuple[str, ...]
    items: tuple[RatingItem, ...]
    values: tuple[tuple[float | None, ...], ...]
    weights: tuple[float, ...]
    object_ids: tuple[str, ...]
    object_items: tuple[str, ...]
    roles: dict[str, str]

    @field_validator("respondent_ids")
    @classmethod
    def _respondents(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(v, "respondent ids")

    @field_validator("object_ids")
    @classmethod
    def _objects(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(v, "object ids")

    @field_validator("values", "weights", mode="before")
    @classmethod
    def _numbers(cls, v: Any) -> Any:
        return _no_bool(v, "values and weights")

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        n, p = len(self.respondent_ids), len(self.items)
        _unique(tuple(i.item_id for i in self.items), "item ids")
        if len(self.values) != n or any(len(row) != p for row in self.values):
            raise ValueError(f"values must be {n} respondents x {p} items")
        for k, row in enumerate(self.values):
            if any(v is not None and not math.isfinite(v) for v in row):
                raise ValueError(f"respondent row {k} holds a non-finite rating")
        if len(self.weights) != n:
            raise ValueError("weights must align with the respondents")
        if len(self.donor_ids) != n:
            raise ValueError("donor_ids must align with the respondents")
        if any(not (math.isfinite(w) and w > 0) for w in self.weights):
            raise ValueError("every weight must be positive and finite")
        if len(self.object_items) != len(self.object_ids):
            raise ValueError("object_items must name one item for each mapped object")
        _unique(self.object_items, "the mapped objects' items")
        known = {i.item_id for i in self.items}
        missing = [i for i in self.object_items if i not in known]
        if missing:
            raise ValueError(f"mapped objects name items outside the universe: {missing}")
        if set(self.roles) != set(self.object_ids):
            raise ValueError("roles must declare every mapped object, and only those")
        for obj, role in self.roles.items():
            if role not in {r.value for r in ObjectRole}:
                raise ValueError(f"object {obj!r} has an unknown role {role!r}")
        return self

    def object_columns(self) -> tuple[int, ...]:
        """Each mapped object's item column, in ``object_ids`` order."""
        index = {i.item_id: c for c, i in enumerate(self.items)}
        return tuple(index[i] for i in self.object_items)

    def fingerprints(self) -> dict[str, str]:
        """What the map was computed from, part by part."""
        return {
            "ratings": fingerprint(
                {
                    "respondents": list(self.respondent_ids),
                    "items": [i.model_dump(mode="json") for i in self.items],
                    "values": [list(r) for r in self.values],
                }
            ),
            "weights": fingerprint(list(self.weights)),
            "donors": fingerprint(list(self.donor_ids)),
            "family": fingerprint(
                {
                    "objects": list(self.object_ids),
                    "items": list(self.object_items),
                    "roles": self.roles,
                }
            ),
        }


class MapOutcome(StrEnum):
    #: The objects have a map, with its Stress-1 and its band.
    MAPPED = "MAPPED"
    #: The family has no map the data can support; :class:`NotMappable` says why.
    NOT_MAPPABLE = "NOT_MAPPABLE"


class NotMappableReason(StrEnum):
    #: Fewer than three objects: two points have no shape to show.
    TOO_FEW_OBJECTS = "TOO_FEW_OBJECTS"
    #: No pair reached RELIABLE or WEAK: nothing is known to place anything by.
    NO_KNOWN_PAIR = "NO_KNOWN_PAIR"
    #: Some objects have no chain of known pairs to the rest (``objects`` names them).
    DISCONNECTED = "DISCONNECTED"
    #: The known-pair weights leave the configuration undetermined.
    SINGULAR = "SINGULAR"
    #: The objects are rated on different scales: the signed-off methodology reads one scale
    #: per set, in its relations and its respondent map alike.
    MIXED_SCALES = "MIXED_SCALES"


class NotMappable(_Frozen):
    reason: str
    message: str
    objects: tuple[str, ...]


class ObjectMapLayout(_Frozen):
    """The objects on the fixed ruler (audit F6, F7): never rescaled, with how far to trust it."""

    points: tuple[Point, ...]
    extent: float
    #: The SMACOF fit and its band. ``None`` under the signed-off layout (``aia-sociomap-5``),
    #: which does not compute Stress-1, and left out of the stored form.
    stress_1: float | None = None
    raw_stress: float | None = None
    quality: str | None = None
    known_pairs: int
    iterations: int
    converged: bool
    start_fill: float | None
    #: Which method placed the objects under the signed-off layout (``aia-sociomap-5``):
    #: ``soft_rank_spearman_coulomb`` or ``interval_mds``. ``None`` (SMACOF) is left out of
    #: the stored form, so every map stored before it reads, and recomputes, byte for byte.
    method: str | None = None

    @model_serializer(mode="wrap")
    def _without_absent(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        for key in ("stress_1", "raw_stress", "quality", "method"):
            if body.get(key) is None:
                body.pop(key, None)
        return body

    @field_validator("points")
    @classmethod
    def _finite(cls, v: tuple[Point, ...]) -> tuple[Point, ...]:
        for i, (x, y) in enumerate(v):
            if not (math.isfinite(x) and math.isfinite(y)):
                raise ValueError(f"points[{i}] must be finite")
        return v

    @model_validator(mode="after")
    def _stress_exactly_for_smacof(self) -> Self:
        recorded = [v is not None for v in (self.stress_1, self.raw_stress, self.quality)]
        if not (all(recorded) if self.method is None else not any(recorded)):
            raise ValueError(
                "a SMACOF layout records stress_1, raw_stress and quality; the signed-off "
                "layout (a method) records none of them"
            )
        return self


class NotComputed(_Frozen):
    """A part of the method this contract names and does not compute yet, and why."""

    status: Literal["not_computed"]
    reason: str


class ObjectHeights(_Frozen):
    """Each mapped object's height (audit F8: the mean rating), with its support.

    A ``values`` entry is ``None`` exactly when nobody rated the object. ``relative`` is each
    PRIMARY object's hill height under the framed envelope (``aia-sociomap-5``): its height
    min-max scaled over the rated ones onto ``[floor, 1]``; ``None`` for an object nobody
    rated (not placed) and for a SECONDARY object. Under every other terrain ``relative`` is
    ``None`` and left out of the stored form, so every map stored before it reads, and
    recomputes, byte for byte.
    """

    metric: str
    values: tuple[float | None, ...]
    support_n: tuple[int, ...]
    relative: tuple[float | None, ...] | None = None

    @model_serializer(mode="wrap")
    def _without_absent(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        if body.get("relative") is None:
            body.pop("relative", None)
        return body


class ObjectMapSupport(_Frozen):
    """How much the map rests on, and how the weights entered it (plan § 8.2, I3).

    ``placed`` respondents are the ones with a preference to rescale (F2); the others are
    ``not_placed`` and enter no relation. ``effective_n`` is Kish's ``(sum w)^2 / sum w^2``
    over the placed respondents' weights: what the weighted sample is worth, beside the
    count every pair's status reads (``weighting`` says which is used where). ``donors``
    counts the distinct panel persons the placed respondents were built from.
    """

    respondents: int
    placed: int
    not_placed: int
    effective_n: float | None
    donors: int
    weighting: str


class SparseDesign(_Frozen):
    """The sparse-design note of the signed-off methodology (``aia-sociomap-5``): set when
    more than the declared share of pairs is below the layout floor, or some objects have
    fewer layout partners than declared (``weakly_connected``, by object id)."""

    flag: bool
    share_below_layout_floor: float
    weakly_connected: tuple[str, ...]


class CredibilityRule(StrEnum):
    """Which rule decided whether a map is weakly determined (``aia-sociomap-5``)."""

    #: The split-half check: weakly determined below the threshold.
    SPLIT_HALF = "split_half"
    #: Where the split-half check has no score (a half cannot be mapped, or two objects have
    #: no triplet): weakly determined when no pair is RELIABLE.
    NO_RELIABLE_PAIR = "no_reliable_pair"


class MapCredibility(_Frozen):
    """How far the signed-off methodology's map can be read (``aia-sociomap-5``).

    ``split_half`` is the split-half agreement, ``None`` when it has no score; ``rule`` says
    which rule decided ``weakly_determined``; ``reliable_pairs`` counts the RELIABLE pairs.
    ``uncertainty_radius`` is how far an object typically moves if the study were re-run, in
    units of the root-mean-square inter-object distance of the map; ``None`` when the
    bootstrap maps cannot be computed.
    """

    rule: str
    split_half: float | None
    threshold: float
    weakly_determined: bool
    reliable_pairs: int
    uncertainty_radius: float | None

    @model_validator(mode="after")
    def _decided_by_its_rule(self) -> Self:
        if self.rule == CredibilityRule.SPLIT_HALF:
            if self.split_half is None or not math.isfinite(self.split_half):
                raise ValueError("the split-half rule decides on a split-half score")
            if self.weakly_determined != (self.split_half < self.threshold):
                raise ValueError("weakly determined exactly below the split-half threshold")
        elif self.rule == CredibilityRule.NO_RELIABLE_PAIR:
            if self.split_half is not None:
                raise ValueError("the no-reliable-pair rule decides only without a score")
            if self.weakly_determined != (self.reliable_pairs == 0):
                raise ValueError("weakly determined exactly when no pair is RELIABLE")
        else:
            raise ValueError(f"unknown credibility rule {self.rule!r}")
        return self


class RespondentStatus(StrEnum):
    """Where a respondent stands on the respondent map (``aia-sociomap-5``)."""

    #: Their ratings follow a direction beyond chance: drawn, and counted in the density.
    PLACED = "PLACED"
    #: Drawn faintly: the direction could be chance. Not counted in the density.
    FADED = "FADED"
    #: Fewer ratings than the minimum, or all equal: no direction to draw.
    NOT_PLACED = "NOT_PLACED"


class RespondentDensity(_Frozen):
    """The density of the PLACED respondents, divided by its maximum (0 everywhere when
    nobody is PLACED), indexed ``[gy][gx]`` on the object terrain's grid: ``parameters``
    are its ``centre``, ``half_extent`` and ``grid_resolution``, with the density's own
    kernel width ``sigma``. A respondent can stand outside the grid."""

    parameters: EnvelopeParameters
    height: tuple[tuple[float, ...], ...]

    @model_validator(mode="after")
    def _shape(self) -> Self:
        size = self.parameters.grid_resolution + 1
        if len(self.height) != size or any(len(row) != size for row in self.height):
            raise ValueError(f"the density must be a {size} x {size} grid")
        if not all(math.isfinite(h) and 0.0 <= h <= 1.0 for row in self.height for h in row):
            raise ValueError("a density divided by its maximum lies in [0, 1]")
        return self


class SegmentDecision(StrEnum):
    """What the taste segments of a respondent map are (``aia-sociomap-5``)."""

    #: Segments shown: their respondents coloured, their profiles named.
    SEGMENTS = "SEGMENTS"
    #: No segments; the reason says why.
    NONE = "NONE"
    #: A near-tie between the shown and the jittered maps: nobody coloured, the likely split
    #: named.
    BORDERLINE = "BORDERLINE"


class NoSegmentsReason(StrEnum):
    """Why a respondent map shows no taste segments."""

    #: Fewer respondents with a slope than the declared minimum: nothing was looked for.
    TOO_FEW_RESPONDENTS = "TOO_FEW_RESPONDENTS"
    #: Fewer objects than the ratings a slope needs: nobody can have a taste told from chance.
    TOO_FEW_OBJECTS = "TOO_FEW_OBJECTS"
    #: One segment fits best, or the step-down left fewer than two.
    NO_CLEAR_SEGMENTS = "NO_CLEAR_SEGMENTS"
    #: The gain is no larger than in the ratings shuffled within each respondent.
    NOT_ABOVE_SHUFFLED = "NOT_ABOVE_SHUFFLED"
    #: The shown map showed segments, the jittered maps together did not.
    NOT_STABLE = "NOT_STABLE"


class SegmentProfile(_Frozen):
    """What one segment rates above or below everyone else, one entry per mapped object in
    the map's ``object_ids`` order: the difference of respondent-centred raw ratings (rating
    units), its standard error and p-value, and whether it is distinctive; ``likes`` and
    ``dislikes`` are up to the declared number of distinctive objects rated higher (largest
    first) and lower (lowest first)."""

    likes: tuple[str, ...]
    dislikes: tuple[str, ...]
    difference: tuple[float, ...]
    standard_error: tuple[float, ...]
    p_value: tuple[float, ...]
    distinctive: tuple[bool, ...]

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        m = len(self.difference)
        if any(len(c) != m for c in (self.standard_error, self.p_value, self.distinctive)):
            raise ValueError("a profile has one entry per object in every column")
        if not all(math.isfinite(v) for v in (*self.difference, *self.standard_error)):
            raise ValueError("a profile's differences and standard errors are finite")
        if not all(0.0 <= p <= 1.0 for p in self.p_value):
            raise ValueError("a p-value lies in [0, 1]")
        return self


class SegmentHint(_Frozen):
    """The likely split of a borderline decision: its number of segments, their shares
    (largest first) and profiles. Nobody is coloured by it."""

    k: int
    shares: tuple[float, ...]
    profiles: tuple[SegmentProfile, ...]

    @model_validator(mode="after")
    def _sized(self) -> Self:
        if self.k < 2 or len(self.shares) != self.k or len(self.profiles) != self.k:
            raise ValueError("a split has at least two segments, each with a share and profile")
        return self


class TasteSegments(_Frozen):
    """The taste segments of a respondent map (``aia-sociomap-5``).

    ``decision`` and, for NONE, ``reason`` are codes the reader words. ``gain`` is the shown
    map's gain of the segment model over one segment, ``null_gain_max`` the largest gain in
    the shuffled ratings (``None`` when the guard did not run), ``k_fit`` the number the fit
    chose before the step-down (``None`` unless the step-down ran). ``margins`` are the
    penalised margins of the shown and the jittered maps (below 0 favours segments; rounded to
    two decimals, ``None`` for a map with too few respondents), ``mean_margin`` their mean,
    ``votes`` the maps showing segments of ``maps``; all four ``None`` when the set has too
    few objects for jittered maps. Under SEGMENTS: ``k`` segments with their ``shares``
    (largest first), smallest ``separation``, whether ``distinct``, one profile each, and per
    respondent in ``respondent_ids`` order the ``label`` (-1 without a slope), largest
    ``membership`` (``None`` without a slope; five decimals, the colour decided before) and
    whether ``coloured``. Otherwise ``k`` is 0 and the per-respondent columns are ``None``:
    nobody is coloured. Under BORDERLINE, ``hint`` is the likely split.
    """

    decision: str
    reason: str | None
    k: int
    k_fit: int | None
    gain: float
    null_gain_max: float | None
    margins: tuple[float | None, ...] | None
    mean_margin: float | None
    votes: int | None
    maps: int | None
    shares: tuple[float, ...]
    separation: float | None
    distinct: bool | None
    profiles: tuple[SegmentProfile, ...]
    label: tuple[int, ...] | None
    membership: tuple[float | None, ...] | None
    coloured: tuple[bool, ...] | None
    hint: SegmentHint | None

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.decision not in {d.value for d in SegmentDecision}:
            raise ValueError(f"a decision is one of {[d.value for d in SegmentDecision]}")
        none = self.decision == SegmentDecision.NONE
        if (self.reason is not None) != none:
            raise ValueError("a reason is given exactly when there are no segments")
        if self.reason is not None and self.reason not in {r.value for r in NoSegmentsReason}:
            raise ValueError(f"a reason is one of {[r.value for r in NoSegmentsReason]}")
        if (self.hint is not None) != (self.decision == SegmentDecision.BORDERLINE):
            raise ValueError("a likely split is named exactly when the decision is borderline")
        consensus = (self.margins, self.mean_margin, self.votes, self.maps)
        if self.margins is None and any(v is not None for v in consensus):
            raise ValueError("margins, their mean, votes and maps are recorded together")
        if self.margins is not None and (
            self.maps is None or self.votes is None or len(self.margins) != self.maps
        ):
            raise ValueError("one margin per map, and the votes among them")
        shown = self.decision == SegmentDecision.SEGMENTS
        columns = (self.label, self.membership, self.coloured)
        if not shown:
            if self.k != 0 or self.shares or self.profiles or self.separation is not None:
                raise ValueError("without segments there are no shares, profiles or separation")
            if self.distinct is not None or any(c is not None for c in columns):
                raise ValueError("without segments nobody is labelled or coloured")
            return self
        if self.k < 2 or len(self.shares) != self.k or len(self.profiles) != self.k:
            raise ValueError("segments are at least two, each with a share and a profile")
        if self.separation is None or self.distinct is None:
            raise ValueError("segments record their separation and whether they are distinct")
        if self.label is None or self.membership is None or self.coloured is None:
            raise ValueError("segments label every respondent")
        if not len(self.label) == len(self.membership) == len(self.coloured):
            raise ValueError("every per-respondent column has one entry per respondent")
        for label, membership, coloured in zip(
            self.label, self.membership, self.coloured, strict=True
        ):
            if not -1 <= label < self.k:
                raise ValueError(f"a label is -1 or a segment below {self.k}")
            if (membership is None) != (label == -1):
                raise ValueError("a respondent has a membership exactly when labelled")
            if coloured and label == -1:
                raise ValueError("only a labelled respondent is coloured")
        return self


class RespondentMap(_Frozen):
    """The signed-off methodology's respondent map (``aia-sociomap-5``), one entry per
    respondent in the map's ``respondent_ids`` order.

    ``x``, ``y`` are the position on the ruler and ``misfit`` (``1 - R2``) and ``p_value``
    (the chance test) the fit, each rounded to five decimals (the status was decided before);
    each is ``None`` exactly when the respondent is NOT_PLACED.
    ``counts`` counts each status. ``informative`` is false when the map has fewer than
    ``min_objects`` objects: it is still drawn, with a note that it is only indicative.
    """

    status: Literal["computed"] = "computed"
    x: tuple[float | None, ...]
    y: tuple[float | None, ...]
    placement: tuple[str, ...]
    misfit: tuple[float | None, ...]
    p_value: tuple[float | None, ...]
    counts: dict[str, int]
    informative: bool
    min_objects: int
    density: RespondentDensity
    #: The taste segments, where the spec declares them; ``None`` is left out of the stored
    #: form, so a respondent map stored before them reads, and recomputes, byte for byte.
    segments: TasteSegments | None = None

    @model_serializer(mode="wrap")
    def _without_absent(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        if body.get("segments") is None:
            body.pop("segments", None)
        return body

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        n = len(self.placement)
        if any(len(column) != n for column in (self.x, self.y, self.misfit, self.p_value)):
            raise ValueError("every column has one entry per respondent")
        known = {s.value for s in RespondentStatus}
        if set(self.placement) - known:
            raise ValueError(f"a placement is one of {sorted(known)}")
        for status, *values in zip(
            self.placement, self.x, self.y, self.misfit, self.p_value, strict=True
        ):
            placed = status != RespondentStatus.NOT_PLACED
            if any((v is not None) != placed for v in values):
                raise ValueError("a respondent has a position and a fit exactly when placed")
        if self.counts != {s.value: self.placement.count(s) for s in RespondentStatus}:
            raise ValueError("counts must count each placement")
        if self.segments is not None and self.segments.coloured is not None:
            if len(self.segments.coloured) != n:
                raise ValueError("the segments label every respondent of the map")
            if any(
                coloured and status != RespondentStatus.PLACED
                for coloured, status in zip(self.segments.coloured, self.placement, strict=True)
            ):
                raise ValueError("only a clearly placed (PLACED) respondent is coloured")
        return self


class ObjectMapProvenance(_Frozen):
    implementation: str
    implementation_version: str
    input_fingerprints: dict[str, str]
    #: What the worker computed a signed-off map with: its numerical libraries' versions and
    #: its ``NUMBA_CACHE_DIR``, as the worker read them. ``None`` -- every earlier map, and any
    #: map computed without them -- is left out of the stored form, so it reads, and
    #: fingerprints, byte for byte as before.
    runtime: dict[str, str] | None = None

    @model_serializer(mode="wrap")
    def _without_absent_runtime(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        if body.get("runtime") is None:
            body.pop("runtime", None)
        return body


class SociomapArtifactV3(_Frozen):
    """The canonical, immutable contract-3 Sociomap: the audit's object map.

    ``relations`` are every pair over the mapped objects, on each person's own scale (F2):
    signed ``r`` with ``abs_r`` beside it (F4), the rater count, interval and status (F3).
    ``not_placed`` are the respondents with no preference to rescale (F11), each with its
    reason; they never enter a relation, but their ratings still count towards
    ``heights``. ``layout`` is ``None`` exactly when ``outcome`` is ``NOT_MAPPABLE``.
    """

    kind: Literal["sociomap"] = "sociomap"
    contract_version: Literal["3"] = ARTIFACT_CONTRACT_V3
    spec: SociomapSpecV3
    respondent_ids: tuple[str, ...]
    object_ids: tuple[str, ...]
    object_items: tuple[str, ...]
    roles: dict[str, str]
    items: tuple[RatingItem, ...]
    not_placed: dict[str, str]
    relations: PairRelations
    abs_r: tuple[tuple[float | None, ...], ...]
    status_counts: dict[str, int]
    outcome: str
    not_mappable: NotMappable | None
    layout: ObjectMapLayout | None
    scores: dict[str, Any]
    heights: ObjectHeights
    connectedness_100: dict[str, Any]
    support: ObjectMapSupport
    #: The respondent map of a MAPPED ``aia-sociomap-5`` map; :class:`NotComputed` otherwise.
    respondents: NotComputed | RespondentMap
    terrain: NotComputed | EnvelopeTerrain
    provenance: ObjectMapProvenance
    #: Recorded only under the baseline-corrected relation; ``None`` is left out of the
    #: stored form, so every map stored before it reads, and recomputes, byte for byte.
    sparse_design: SparseDesign | None = None
    #: Recorded only on a MAPPED map under the baseline-corrected relation; ``None`` is left
    #: out of the stored form, as ``sparse_design`` is.
    credibility: MapCredibility | None = None
    #: The set's objects the signed-off map (``aia-sociomap-5``) does not place because nobody
    #: rated them: left out of ``object_ids`` and of every computation. Empty is left out of
    #: the stored form, so every map stored before it reads, and recomputes, byte for byte.
    objects_not_placed: tuple[str, ...] = ()

    @model_serializer(mode="wrap")
    def _without_absent_note(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        for key in ("sparse_design", "credibility"):
            if body.get(key) is None:
                body.pop(key, None)
        if not body.get("objects_not_placed"):
            body.pop("objects_not_placed", None)
        return body

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        m = len(self.object_ids)
        if len(self.relations.r) != m:
            raise ValueError("relations must be over the mapped objects")
        expected_abs = tuple(
            tuple(None if v is None else abs(v) for v in row) for row in self.relations.r
        )
        if self.abs_r != expected_abs:
            raise ValueError("abs_r must be |r| of the relations")
        if set(self.not_placed) - set(self.respondent_ids):
            raise ValueError("not_placed names respondents the map does not have")
        if set(self.objects_not_placed) & set(self.object_ids):
            raise ValueError("an object not placed is not a mapped object")
        if self.outcome == MapOutcome.MAPPED:
            if self.layout is None or self.not_mappable is not None:
                raise ValueError("a MAPPED artifact has a layout and no not-mappable reason")
            if len(self.layout.points) != m:
                raise ValueError("the layout must place every mapped object")
        elif self.outcome == MapOutcome.NOT_MAPPABLE:
            if self.layout is not None or self.not_mappable is None:
                raise ValueError("a NOT_MAPPABLE artifact has a reason and no layout")
        else:
            raise ValueError(f"unknown outcome {self.outcome!r}")
        if self.credibility is not None and self.layout is None:
            raise ValueError("credibility judges a map; a NOT_MAPPABLE artifact has none")
        if isinstance(self.respondents, RespondentMap):
            if self.layout is None:
                raise ValueError("respondents stand on a map; a NOT_MAPPABLE artifact has none")
            if len(self.respondents.placement) != len(self.respondent_ids):
                raise ValueError("the respondent map places every respondent of the map")
            if self.respondents.informative != (m >= self.respondents.min_objects):
                raise ValueError("the respondent map is informative from its minimum of objects")
            segments = self.respondents.segments
            if (segments is None) != (self.spec.segments is None):
                raise ValueError("a respondent map has taste segments exactly when declared")
            profiles = () if segments is None else segments.profiles
            if segments is not None and segments.hint is not None:
                profiles += segments.hint.profiles
            for profile in profiles:
                if len(profile.difference) != m:
                    raise ValueError("a segment profile has one entry per mapped object")
                if set(profile.likes + profile.dislikes) - set(self.object_ids):
                    raise ValueError("a segment profile names mapped objects")
        if len(self.heights.values) != m or len(self.heights.support_n) != m:
            raise ValueError("heights must align with the mapped objects")
        if self.heights.relative is not None and len(self.heights.relative) != m:
            raise ValueError("relative heights must align with the mapped objects")
        if isinstance(self.terrain, EnvelopeTerrain):
            if self.layout is None:
                raise ValueError("a terrain stands on a layout; a NOT_MAPPABLE map has none")
            if set(self.terrain.source_ids) - set(self.object_ids):
                raise ValueError("the terrain's hills must be mapped objects")
        if (
            self.support.respondents != len(self.respondent_ids)
            or self.support.not_placed != len(self.not_placed)
            or self.support.placed + self.support.not_placed != self.support.respondents
        ):
            raise ValueError("support must count the map's respondents, placed and not")
        return self

    @property
    def spec_fingerprint(self) -> str:
        return self.spec.fingerprint()

    def fingerprint(self) -> str:
        """Stable SHA256 over the entire canonical body."""
        return fingerprint(self.model_dump(mode="json"))

    def to_payload(self) -> dict[str, Any]:
        """JSON-ready payload carrying the body plus its recorded fingerprints."""
        return {
            "artifact": self.model_dump(mode="json"),
            "artifact_fingerprint": self.fingerprint(),
            "spec_fingerprint": self.spec_fingerprint,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> SociomapArtifactV3:
        """Rebuild from :meth:`to_payload` output, refusing anything edited since."""
        try:
            body = payload["artifact"]
            recorded_artifact = payload["artifact_fingerprint"]
            recorded_spec = payload["spec_fingerprint"]
        except KeyError as exc:
            raise ArtifactIntegrityError(f"payload is missing {exc.args[0]!r}") from None
        artifact = cls.model_validate(body)
        if artifact.fingerprint() != recorded_artifact:
            raise ArtifactIntegrityError("artifact body does not match its recorded fingerprint")
        if artifact.spec_fingerprint != recorded_spec:
            raise ArtifactIntegrityError("spec does not match its recorded fingerprint")
        return artifact


def read_artifact(payload: Mapping[str, Any]) -> SociomapArtifact | SociomapArtifactV3:
    """A stored Sociomap payload, read under the contract its body names.

    A contract-2 payload is read exactly as :meth:`SociomapArtifact.from_payload` always
    read it; a contract-3 one by :meth:`SociomapArtifactV3.from_payload`; anything else is
    an :class:`~.models.ArtifactIntegrityError`. Both verify every recorded fingerprint.
    """
    body = payload.get("artifact")
    contract = body.get("contract_version") if isinstance(body, Mapping) else None
    if contract == "2":
        return SociomapArtifact.from_payload(payload)
    if contract == ARTIFACT_CONTRACT_V3:
        return SociomapArtifactV3.from_payload(payload)
    raise ArtifactIntegrityError(f"no Sociomap artifact contract {contract!r}")


def read_object_maps(battery: Mapping[str, Any]) -> tuple[tuple[str, SociomapArtifactV3], ...]:
    """A stored battery's contract-3 object maps, in stored order, each read and checked.

    The one reader of a battery's ``maps``: every map is read by :func:`read_artifact`
    (every fingerprint verified), must be contract 3, and must have been computed under
    the method it is stored by. Anything else is an :class:`~.models.ArtifactIntegrityError`,
    so no consumer draws or describes a map the run did not compute under that name.
    """
    read: list[tuple[str, SociomapArtifactV3]] = []
    for method, payload in (battery.get("maps") or {}).items():
        artifact = read_artifact(payload)
        if not isinstance(artifact, SociomapArtifactV3):
            raise ArtifactIntegrityError("an object map must use contract 3")
        if artifact.spec.methodology_version != method:
            raise ArtifactIntegrityError("map method differs from its stored key")
        read.append((str(method), artifact))
    return tuple(read)
