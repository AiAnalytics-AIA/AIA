"""Deterministic Sociomapping data contracts: inputs, results and the artifact (v2).

:class:`SociomapInputs` is what a computation reads: a respondents x objects
:class:`RatingsMatrix` and, optionally, an objects x objects
:class:`RelationMatrix`. :class:`SociomapArtifact` is what it produces -- the
canonical, immutable research truth a renderer draws and an auditor reads:
respondent and object coordinates with their stress, the relation matrix as
coerced and as projected for position, every object metric, both terrain
fields, and the provenance that binds them to the spec and inputs.

What the contracts enforce:

* **Validity.** Unique non-blank ids, finite numbers, aligned shapes. An invalid
  input fails at construction, not three stages later.
* **Immutability.** Every model is frozen. A drag or a what-if cannot mutate
  research truth because there is no mutating operation.
* **Traceability.** An artifact carries its spec, its input fingerprints and the
  implementation version, and fingerprints itself over all of them.

Missing values are ``None`` and are *preserved*; how one is treated is a spec
decision executed by the engine, never a default of the data model.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..pipeline import fingerprint
from .specification import SociomapSpec
from .terrain import TerrainField

__all__ = [
    "ARTIFACT_CONTRACT_VERSION",
    "ENGINE_IMPLEMENTATION",
    "ENGINE_IMPLEMENTATION_VERSION",
    "ArtifactIntegrityError",
    "LayoutResult",
    "MetricValues",
    "Provenance",
    "RatingsMatrix",
    "RelationDerivation",
    "RelationMatrix",
    "SociomapArtifact",
    "SociomapInputs",
]

ARTIFACT_CONTRACT_VERSION: Literal["2"] = "2"

# Identity of the deterministic implementation recorded into every artifact.
# Bump it whenever any computation changes its output: the version is part of
# the fingerprint, so artifacts from different engine behaviour never collide.
ENGINE_IMPLEMENTATION = "aia_core.domain.sociomap"
ENGINE_IMPLEMENTATION_VERSION = "1.1.0"

Point = tuple[float, float]


def _check_ids(ids: Iterable[str], *, minimum: int, what: str) -> tuple[str, ...]:
    ordered = tuple(ids)
    if len(ordered) < minimum:
        raise ValueError(f"{what} needs at least {minimum} ids; got {len(ordered)}")
    seen: set[str] = set()
    for entity in ordered:
        if not isinstance(entity, str) or not entity.strip():
            raise ValueError(f"{what} ids must be non-blank strings; got {entity!r}")
        if entity in seen:
            raise ValueError(f"duplicate {what} id {entity!r}; identifiers must be unique")
        seen.add(entity)
    return ordered


def _reject_booleans(value: Any, where: str) -> Any:
    """Refuse ``True``/``False`` where a number is expected.

    Runs before pydantic's coercion, which would otherwise turn a boolean into
    ``1.0`` silently.
    """
    if isinstance(value, bool):
        raise ValueError(f"{where} must be a number or None, not a boolean")
    if isinstance(value, list | tuple):
        for i, item in enumerate(value):
            _reject_booleans(item, f"{where}[{i}]")
    return value


def _check_finite(value: float | None, where: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{where} must be finite; got {number!r}")
    return number


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ----------------------------------------------------------------- inputs --


class RelationMatrix(_Frozen):
    """A square matrix of relation values between entities.

    ``values[i][j]`` is the relation *from* ``entity_ids[i]`` *to*
    ``entity_ids[j]``. Directionality is preserved as given: the model does not
    symmetrise. :meth:`is_symmetric` and :meth:`max_asymmetry` are descriptive
    only. ``None`` marks a missing cell; the diagonal is stored as supplied.
    """

    entity_ids: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]

    @field_validator("entity_ids")
    @classmethod
    def _ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(v) < 2:
            raise ValueError("a Sociomapa needs at least two entities; a relation requires a pair")
        return _check_ids(v, minimum=2, what="entity")

    @field_validator("values", mode="before")
    @classmethod
    def _no_booleans(cls, v: Any) -> Any:
        return _reject_booleans(v, "values")

    @model_validator(mode="after")
    def _square_and_finite(self) -> Self:
        n = len(self.entity_ids)
        if len(self.values) != n:
            raise ValueError(f"matrix has {len(self.values)} rows for {n} entities; must be square")
        checked: list[tuple[float | None, ...]] = []
        for i, row in enumerate(self.values):
            if len(row) != n:
                raise ValueError(f"row {i} has {len(row)} columns for {n} entities; must be square")
            checked.append(tuple(_check_finite(v, f"values[{i}][{j}]") for j, v in enumerate(row)))
        object.__setattr__(self, "values", tuple(checked))
        return self

    @property
    def n(self) -> int:
        """Number of entities."""
        return len(self.entity_ids)

    def index_of(self, entity_id: str) -> int:
        """Position of an entity, raising ``KeyError`` for an unknown id."""
        try:
            return self.entity_ids.index(entity_id)
        except ValueError:
            raise KeyError(entity_id) from None

    def cell(self, source: str, target: str) -> float | None:
        """Relation from ``source`` to ``target``."""
        return self.values[self.index_of(source)][self.index_of(target)]

    @property
    def missing_count(self) -> int:
        """Number of ``None`` cells, diagonal included."""
        return sum(1 for row in self.values for v in row if v is None)

    @property
    def is_complete(self) -> bool:
        """True when no cell is missing."""
        return self.missing_count == 0

    def max_asymmetry(self) -> float | None:
        """Largest ``|a_ij - a_ji|`` over fully present off-diagonal pairs, else ``None``."""
        largest: float | None = None
        for i in range(self.n):
            for j in range(i + 1, self.n):
                a, b = self.values[i][j], self.values[j][i]
                if a is None or b is None:
                    continue
                gap = abs(a - b)
                largest = gap if largest is None else max(largest, gap)
        return largest

    def is_symmetric(self, *, abs_tol: float = 0.0) -> bool:
        """True when every present off-diagonal pair agrees within ``abs_tol``.

        A pair with one side missing counts as asymmetric.
        """
        for i in range(self.n):
            for j in range(i + 1, self.n):
                a, b = self.values[i][j], self.values[j][i]
                if (a is None) != (b is None):
                    return False
                if a is not None and b is not None and abs(a - b) > abs_tol:
                    return False
        return True

    def reordered(self, entity_ids: Iterable[str]) -> RelationMatrix:
        """The same relation with rows and columns in a new entity order."""
        order = tuple(entity_ids)
        if sorted(order) != sorted(self.entity_ids):
            raise ValueError("reordered() requires a permutation of the existing entity ids")
        idx = [self.index_of(e) for e in order]
        return RelationMatrix(
            entity_ids=order,
            values=tuple(tuple(self.values[i][j] for j in idx) for i in idx),
        )

    def with_cells(self, overrides: Mapping[tuple[str, str], float | None]) -> RelationMatrix:
        """A new matrix with the given ``(source, target)`` cells replaced."""
        rows = [list(row) for row in self.values]
        for (source, target), value in overrides.items():
            rows[self.index_of(source)][self.index_of(target)] = value
        return RelationMatrix(entity_ids=self.entity_ids, values=tuple(tuple(r) for r in rows))

    def fingerprint(self) -> str:
        """Stable SHA256 of the entity order and every cell."""
        return fingerprint(self.model_dump(mode="json"))


class RatingsMatrix(_Frozen):
    """Respondents x objects ratings. ``values[i][j]``: respondent ``i`` rates object ``j``.

    ``None`` is an unrated cell. Values are raw, on the scale the spec declares;
    the engine checks them against it.
    """

    respondent_ids: tuple[str, ...]
    object_ids: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]

    @field_validator("respondent_ids")
    @classmethod
    def _respondents(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _check_ids(v, minimum=1, what="respondent")

    @field_validator("object_ids")
    @classmethod
    def _objects(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _check_ids(v, minimum=3, what="object")

    @field_validator("values", mode="before")
    @classmethod
    def _no_booleans(cls, v: Any) -> Any:
        return _reject_booleans(v, "values")

    @model_validator(mode="after")
    def _shape(self) -> Self:
        n, m = len(self.respondent_ids), len(self.object_ids)
        if len(self.values) != n:
            raise ValueError(f"ratings have {len(self.values)} rows for {n} respondents")
        checked: list[tuple[float | None, ...]] = []
        for i, row in enumerate(self.values):
            if len(row) != m:
                raise ValueError(f"ratings row {i} has {len(row)} cells for {m} objects")
            checked.append(tuple(_check_finite(v, f"values[{i}][{j}]") for j, v in enumerate(row)))
        object.__setattr__(self, "values", tuple(checked))
        return self

    def fingerprint(self) -> str:
        """Stable SHA256 of both id orders and every cell."""
        return fingerprint(self.model_dump(mode="json"))


class SociomapInputs(_Frozen):
    """Everything a Sociomap computation reads.

    ``object_relation``, when given, must name exactly the ratings' objects in
    the same order -- positional coincidence is not alignment.
    """

    ratings: RatingsMatrix
    object_relation: RelationMatrix | None

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        if (
            self.object_relation is not None
            and self.object_relation.entity_ids != self.ratings.object_ids
        ):
            raise ValueError(
                "object_relation must list the ratings' object ids in the same order; "
                "reorder the matrix rather than relying on positional coincidence"
            )
        return self

    def fingerprints(self) -> dict[str, str]:
        """Input fingerprints, as recorded in provenance."""
        out = {"ratings": self.ratings.fingerprint()}
        if self.object_relation is not None:
            out["object_relation"] = self.object_relation.fingerprint()
        return out


# ---------------------------------------------------------------- results --


class MetricValues(_Frozen):
    """One per-object metric, aligned with the artifact's ``object_ids``."""

    metric_id: str
    values: tuple[float | None, ...]

    @field_validator("metric_id")
    @classmethod
    def _named(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("metric_id must not be blank")
        return v

    @field_validator("values", mode="before")
    @classmethod
    def _no_booleans(cls, v: Any) -> Any:
        return _reject_booleans(v, "values")

    @field_validator("values")
    @classmethod
    def _finite(cls, v: tuple[float | None, ...]) -> tuple[float | None, ...]:
        return tuple(_check_finite(x, f"values[{i}]") for i, x in enumerate(v))


def _finite_points(points: tuple[Point, ...], where: str) -> tuple[Point, ...]:
    for i, (x, y) in enumerate(points):
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError(f"{where}[{i}] must be finite")
    return points


class LayoutResult(_Frozen):
    """Canonical coordinates from the declared layout algorithm, in map-frame units.

    ``respondent_ids`` are the *placed* respondents, in input order; respondents
    that could not be placed are listed, with the reason, on the artifact.
    ``layout_to_map_scale`` is the factor applied to the algorithm's own units by
    the spec's map frame, recorded so either unit system can be recovered.
    """

    algorithm: str
    gauge_fixed: bool
    respondent_ids: tuple[str, ...]
    respondent_xy: tuple[Point, ...]
    object_xy: tuple[Point, ...]
    layout_to_map_scale: float
    stress_1: float
    normalized_stress: float
    iterations: int
    converged: bool
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("respondent_xy", "object_xy")
    @classmethod
    def _finite(cls, v: tuple[Point, ...], info: Any) -> tuple[Point, ...]:
        return _finite_points(v, str(info.field_name))

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        if len(self.respondent_ids) != len(self.respondent_xy):
            raise ValueError("respondent_xy must align with respondent_ids")
        if not (math.isfinite(self.layout_to_map_scale) and self.layout_to_map_scale > 0):
            raise ValueError("layout_to_map_scale must be positive and finite")
        return self


class RelationDerivation(_Frozen):
    """The object relation matrix as the engine used it.

    ``coerced`` is the directed matrix on the 1-10 scale (diagonal ``0``) -- what
    relation metrics and scenarios read. ``position_input`` is the symmetric
    ``[0, 1]`` projection that collapses direction for 2-D placement. Both are
    kept: direction stays visible even where position ignores it.
    """

    coercion_branch: str
    coerced: RelationMatrix
    position_input: RelationMatrix
    substituted_cells: tuple[tuple[str, str], ...] = ()


class Provenance(_Frozen):
    """Where an artifact came from, sufficient to reproduce or refuse it.

    No timestamp and no host detail: the artifact repository row records
    ``created_at``, and anything host-specific inside the fingerprinted body
    would make identical computations on two machines look different -- the
    very defect the declared-algorithm rule removes.
    """

    implementation: str = ENGINE_IMPLEMENTATION
    implementation_version: str = ENGINE_IMPLEMENTATION_VERSION
    input_fingerprints: dict[str, str]
    source_artifact_ids: tuple[str, ...] = ()
    layout_algorithm: str
    seed: int | None

    @field_validator("input_fingerprints")
    @classmethod
    def _string_map(cls, v: dict[str, str]) -> dict[str, str]:
        if "ratings" not in v:
            raise ValueError("provenance must record the ratings fingerprint")
        for key, value in v.items():
            if not key.strip() or not value.strip():
                raise ValueError("provenance maps must have non-blank keys and values")
        return dict(v)


class ArtifactIntegrityError(ValueError):
    """A serialised artifact's recorded fingerprints do not match its content."""


class SociomapArtifact(_Frozen):
    """The canonical, immutable result of one Sociomapping computation.

    Nothing presentational: no pixels, no palette, no drag state. The chain
    ``inputs -> spec -> dissimilarities -> layout -> metrics -> terrain`` is all
    here and fingerprinted, so a rendered map can always be traced to numbers.
    """

    kind: Literal["sociomap"] = "sociomap"
    contract_version: Literal["2"] = ARTIFACT_CONTRACT_VERSION
    spec: SociomapSpec
    respondent_ids: tuple[str, ...]
    object_ids: tuple[str, ...]
    excluded_respondents: dict[str, str]
    layout: LayoutResult
    relation: RelationDerivation | None
    object_metrics: dict[str, MetricValues]
    respondent_terrain: TerrainField
    object_terrain: TerrainField
    provenance: Provenance
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        m = len(self.object_ids)
        if len(self.layout.object_xy) != m:
            raise ValueError(
                f"layout places {len(self.layout.object_xy)} objects; artifact has {m}"
            )
        placed = set(self.layout.respondent_ids)
        excluded = set(self.excluded_respondents)
        if placed & excluded:
            raise ValueError("a respondent cannot be both placed and excluded")
        if placed | excluded != set(self.respondent_ids):
            raise ValueError("every respondent must be either placed or excluded, with a reason")
        order = [r for r in self.respondent_ids if r in placed]
        if tuple(order) != self.layout.respondent_ids:
            raise ValueError("placed respondents must keep the input order")
        for metric_id, metric in self.object_metrics.items():
            if metric.metric_id != metric_id or len(metric.values) != m:
                raise ValueError(f"object metric {metric_id!r} must align with object_ids")
        if self.relation is not None and self.relation.coerced.entity_ids != self.object_ids:
            raise ValueError("relation derivation must use the artifact's object order")
        return self

    # --------------------------------------------------------------- identity --

    @property
    def spec_fingerprint(self) -> str:
        """Fingerprint of the methodology that produced this artifact."""
        return self.spec.fingerprint()

    def fingerprint(self) -> str:
        """Stable SHA256 over the entire canonical body."""
        return fingerprint(self.model_dump(mode="json"))

    def respondent_position(self, respondent_id: str) -> Point:
        """Canonical map position of a placed respondent (``KeyError`` otherwise)."""
        try:
            return self.layout.respondent_xy[self.layout.respondent_ids.index(respondent_id)]
        except ValueError:
            raise KeyError(respondent_id) from None

    def object_position(self, object_id: str) -> Point:
        """Canonical map position of an object (``KeyError`` otherwise)."""
        try:
            return self.layout.object_xy[self.object_ids.index(object_id)]
        except ValueError:
            raise KeyError(object_id) from None

    # ---------------------------------------------------------- serialisation --

    def to_payload(self) -> dict[str, Any]:
        """JSON-ready payload carrying the body plus its recorded fingerprints.

        :meth:`from_payload` recomputes and compares them, so a payload edited in
        storage or in transit is refused rather than served as a finding.
        """
        return {
            "artifact": self.model_dump(mode="json"),
            "artifact_fingerprint": self.fingerprint(),
            "spec_fingerprint": self.spec_fingerprint,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> SociomapArtifact:
        """Rebuild an artifact from :meth:`to_payload` output, verifying integrity."""
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
