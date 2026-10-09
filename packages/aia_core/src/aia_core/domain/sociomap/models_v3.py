"""The contract-3 Sociomap: the audit's object map, its inputs and its artifact.

Plan ``sociomap-formula-corrections`` § 8.2, S2. :class:`ObjectMapInputs` is what
:func:`~.engine_v2.compute_object_map` reads: every rating item of the study with its
declared scale (the *rating universe*), every respondent's raw ratings of them, the
respondents' weights, and the family being mapped with each object's role.
:class:`SociomapArtifactV3` is what it produces: the canonical, immutable object map.

Beside the contract-2 artifact (:class:`~.models.SociomapArtifact`), never instead of it:
a stored contract-2 payload is read exactly as before, and :func:`read_artifact` reads each
payload under the contract it names. What contract 3 does not compute yet -- respondent
placement (chunk 3), and the terrain where the spec declares none or nothing is mapped -- is a
:class:`NotComputed` block with its reason, never an empty list a reader could take for
"nobody" or "flat".

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..pipeline import fingerprint
from .metrics import ObjectRole
from .models import ArtifactIntegrityError, SociomapArtifact
from .pairs import PairRelations
from .specification import SociomapSpecV3
from .terrain import EnvelopeTerrain

__all__ = [
    "ARTIFACT_CONTRACT_V3",
    "OBJECT_MAP_IMPLEMENTATION",
    "OBJECT_MAP_IMPLEMENTATION_VERSION",
    "MapOutcome",
    "NotComputed",
    "NotMappable",
    "NotMappableReason",
    "ObjectHeights",
    "ObjectMapInputs",
    "ObjectMapLayout",
    "ObjectMapProvenance",
    "ObjectMapSupport",
    "RatingItem",
    "SociomapArtifactV3",
    "read_artifact",
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


class NotMappable(_Frozen):
    reason: str
    message: str
    objects: tuple[str, ...]


class ObjectMapLayout(_Frozen):
    """The objects on the fixed ruler (audit F6, F7): never rescaled, with how far to trust it."""

    points: tuple[Point, ...]
    extent: float
    stress_1: float
    raw_stress: float
    quality: str
    known_pairs: int
    iterations: int
    converged: bool
    start_fill: float | None

    @field_validator("points")
    @classmethod
    def _finite(cls, v: tuple[Point, ...]) -> tuple[Point, ...]:
        for i, (x, y) in enumerate(v):
            if not (math.isfinite(x) and math.isfinite(y)):
                raise ValueError(f"points[{i}] must be finite")
        return v


class NotComputed(_Frozen):
    """A part of the method this contract names and does not compute yet, and why."""

    status: Literal["not_computed"]
    reason: str


class ObjectHeights(_Frozen):
    """Each mapped object's height (audit F8: the mean rating), with its support."""

    metric: str
    values: tuple[float | None, ...]
    support_n: tuple[int, ...]


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


class ObjectMapProvenance(_Frozen):
    implementation: str
    implementation_version: str
    input_fingerprints: dict[str, str]


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
    respondents: NotComputed
    terrain: NotComputed | EnvelopeTerrain
    provenance: ObjectMapProvenance

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
        if len(self.heights.values) != m or len(self.heights.support_n) != m:
            raise ValueError("heights must align with the mapped objects")
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
