"""Deterministic Sociomapping data contracts: inputs, results and the artifact.

These types describe the *shape* of Sociomapping research truth -- a relation
matrix, a layout, per-entity metrics, and the artifact that binds them to the
methodology and inputs that produced them. They deliberately contain no
methodology: nothing here derives a relation, transforms a matrix or places a
point. Those operations belong to the (not yet ported) deterministic engine and
are gated by :func:`aia_core.domain.sociomap.specification.require_supported`.

What the contracts do enforce:

* **Validity.** Square matrices, unique non-blank entity identifiers, finite
  numbers, per-entity vectors that match the entity list exactly. An invalid
  input fails at construction, not three stages later.
* **Immutability.** Every model is frozen. A rendered map, a drag or a what-if
  cannot mutate research truth because there is no mutating operation.
* **Traceability.** An artifact carries its spec, its input fingerprints, the
  implementation version and the seed, and fingerprints itself over all of them.
  "Why is this point here" is answerable from the artifact alone.

Missing values are represented as ``None`` and are *preserved*, never imputed:
how a missing cell is treated is a methodology decision recorded in the spec's
``missing_data_policy`` and executed by the engine, not a default of the data
model.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..pipeline import fingerprint
from .specification import SociomapSpec

__all__ = [
    "ARTIFACT_CONTRACT_VERSION",
    "ENGINE_IMPLEMENTATION",
    "ENGINE_IMPLEMENTATION_VERSION",
    "ArtifactIntegrityError",
    "LayoutResult",
    "MetricValues",
    "Provenance",
    "RelationMatrix",
    "SociomapArtifact",
]

ARTIFACT_CONTRACT_VERSION: Literal["1"] = "1"

# Identity of the deterministic implementation recorded into every artifact.
# ``0.0.0-contracts`` states plainly that no Sociomapping mathematics has been
# ported yet: contracts exist, computation does not.
ENGINE_IMPLEMENTATION = "aia_core.domain.sociomap"
ENGINE_IMPLEMENTATION_VERSION = "0.0.0-contracts"


def _check_entity_ids(ids: Iterable[str]) -> tuple[str, ...]:
    ordered = tuple(ids)
    if len(ordered) < 2:
        raise ValueError("a Sociomapa needs at least two entities; a relation requires a pair")
    seen: set[str] = set()
    for entity in ordered:
        if not isinstance(entity, str) or not entity.strip():
            raise ValueError(f"entity ids must be non-blank strings; got {entity!r}")
        if entity in seen:
            raise ValueError(f"duplicate entity id {entity!r}; identifiers must be unique")
        seen.add(entity)
    return ordered


def _reject_booleans(value: Any, where: str) -> Any:
    """Refuse ``True``/``False`` where a number is expected.

    Runs before pydantic's coercion, which would otherwise turn a boolean into
    ``1.0`` silently. A yes/no relation is a legitimate input, but the caller must
    encode it as numbers deliberately rather than have the contract guess.
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


class RelationMatrix(BaseModel):
    """A square matrix of relation values between entities.

    ``values[i][j]`` is the relation *from* ``entity_ids[i]`` *to*
    ``entity_ids[j]``. Directionality is preserved as given: the model does not
    symmetrise, and whether the methodology treats the relation as directed is a
    spec decision. :meth:`is_symmetric` and :meth:`max_asymmetry` are descriptive
    only.

    ``None`` marks a missing cell. The diagonal is stored as supplied; what it
    means (self-relation, ignored, forced to a constant) is again methodology.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_ids: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]

    @field_validator("entity_ids")
    @classmethod
    def _ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _check_entity_ids(v)

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

    # ------------------------------------------------------------- inspection --

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
        """Largest ``|a_ij - a_ji|`` over pairs where both cells are present.

        Returns ``None`` when no off-diagonal pair is fully present. Descriptive
        only: it reports how directed the data is, it does not decide anything.
        """
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

        A pair with one side missing counts as asymmetric: symmetry cannot be
        asserted about a value that is not there.
        """
        for i in range(self.n):
            for j in range(i + 1, self.n):
                a, b = self.values[i][j], self.values[j][i]
                if (a is None) != (b is None):
                    return False
                if a is not None and b is not None and abs(a - b) > abs_tol:
                    return False
        return True

    # ------------------------------------------------------------ derivation --

    def reordered(self, entity_ids: Iterable[str]) -> RelationMatrix:
        """Return the same relation with rows and columns in a new entity order.

        The new order must be a permutation of the existing ids. Relation values
        are carried by identity, so ``cell(a, b)`` is invariant under reordering.
        """
        order = tuple(entity_ids)
        if sorted(order) != sorted(self.entity_ids):
            raise ValueError("reordered() requires a permutation of the existing entity ids")
        idx = [self.index_of(e) for e in order]
        return RelationMatrix(
            entity_ids=order,
            values=tuple(tuple(self.values[i][j] for j in idx) for i in idx),
        )

    def with_cells(self, overrides: Mapping[tuple[str, str], float | None]) -> RelationMatrix:
        """Return a new matrix with the given ``(source, target)`` cells replaced.

        The receiver is untouched. This is the data mechanism a what-if layer uses
        to derive an alternative input from an immutable original.
        """
        rows = [list(row) for row in self.values]
        for (source, target), value in overrides.items():
            rows[self.index_of(source)][self.index_of(target)] = value
        return RelationMatrix(entity_ids=self.entity_ids, values=tuple(tuple(r) for r in rows))

    def fingerprint(self) -> str:
        """Stable SHA256 of the entity order and every cell."""
        return fingerprint(self.model_dump(mode="json"))


class MetricValues(BaseModel):
    """One per-entity metric, e.g. the values chosen to drive height or colour.

    ``metric_id`` names the metric as the spec does; ``values`` are aligned with
    the owning artifact's ``entity_ids``. ``None`` is a missing value and is kept
    as such.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

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


class LayoutResult(BaseModel):
    """Canonical 2-D coordinates produced by a layout algorithm.

    ``gauge_fixed`` records whether the algorithm fixes translation, rotation,
    reflection and scale (so two runs are comparable coordinate-by-coordinate)
    or leaves them free (so comparison needs an alignment step). ``None`` means
    the implementation has not declared this; a parity comparison must not
    assume either.

    ``diagnostics`` is for algorithm-specific facts worth auditing -- iteration
    count, final stress, convergence flag -- and is included in the fingerprint.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    algorithm: str
    x: tuple[float, ...]
    y: tuple[float, ...]
    gauge_fixed: bool | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("x", "y", mode="before")
    @classmethod
    def _no_booleans(cls, v: Any, info: Any) -> Any:
        return _reject_booleans(v, str(info.field_name))

    @field_validator("x", "y")
    @classmethod
    def _finite_coords(cls, v: tuple[float, ...], info: Any) -> tuple[float, ...]:
        out: list[float] = []
        for i, value in enumerate(v):
            checked = _check_finite(value, f"{info.field_name}[{i}]")
            if checked is None:
                raise ValueError(f"{info.field_name}[{i}] must not be missing")
            out.append(checked)
        return tuple(out)

    @model_validator(mode="after")
    def _same_length(self) -> Self:
        if len(self.x) != len(self.y):
            raise ValueError(f"x has {len(self.x)} values and y has {len(self.y)}")
        return self

    @property
    def n(self) -> int:
        """Number of placed entities."""
        return len(self.x)


class Provenance(BaseModel):
    """Where an artifact came from, sufficient to reproduce or refuse it.

    No timestamp lives here on purpose: the artifact repository row records
    ``created_at``, and a time inside the fingerprinted body would make two
    identical computations look different.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    implementation: str = ENGINE_IMPLEMENTATION
    implementation_version: str = ENGINE_IMPLEMENTATION_VERSION
    input_fingerprints: dict[str, str] = Field(default_factory=dict)
    source_artifact_ids: tuple[str, ...] = ()
    seed: int | None = None
    dependencies: dict[str, str] = Field(default_factory=dict)

    @field_validator("input_fingerprints", "dependencies")
    @classmethod
    def _string_map(cls, v: dict[str, str]) -> dict[str, str]:
        for key, value in v.items():
            if not key.strip() or not value.strip():
                raise ValueError("provenance maps must have non-blank keys and values")
        return dict(v)


class ArtifactIntegrityError(ValueError):
    """A serialised artifact's recorded fingerprints do not match its content."""


class SociomapArtifact(BaseModel):
    """The canonical, immutable result of one Sociomapping computation.

    Everything a renderer needs and everything an auditor needs, with nothing
    presentational in it: no pixel positions, no palette, no drag state. The
    chain ``inputs -> spec -> relation -> layout -> height/colour`` is all here,
    fingerprinted, so a rendered map can always be traced back to numbers.

    Height and colour are independent of the layout and of each other:
    :meth:`with_metrics` swaps either while leaving the coordinates untouched,
    which is the product invariant that position is relationship-derived and
    stays stable when the displayed metric changes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["sociomap"] = "sociomap"
    contract_version: Literal["1"] = ARTIFACT_CONTRACT_VERSION
    spec: SociomapSpec
    entity_ids: tuple[str, ...]
    relation: RelationMatrix
    layout: LayoutResult
    height: MetricValues | None = None
    colour: MetricValues | None = None
    provenance: Provenance = Field(default_factory=Provenance)
    quality: dict[str, Any] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @field_validator("entity_ids")
    @classmethod
    def _ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _check_entity_ids(v)

    @model_validator(mode="after")
    def _aligned(self) -> Self:
        n = len(self.entity_ids)
        if self.relation.entity_ids != self.entity_ids:
            raise ValueError(
                "relation matrix entity order must equal the artifact entity order; "
                "reorder the matrix rather than relying on positional coincidence"
            )
        if self.layout.n != n:
            raise ValueError(f"layout places {self.layout.n} entities; artifact has {n}")
        for name, metric in (("height", self.height), ("colour", self.colour)):
            if metric is not None and len(metric.values) != n:
                raise ValueError(f"{name} metric has {len(metric.values)} values for {n} entities")
        return self

    # --------------------------------------------------------------- identity --

    @property
    def spec_fingerprint(self) -> str:
        """Fingerprint of the methodology that produced this artifact."""
        return self.spec.fingerprint()

    def fingerprint(self) -> str:
        """Stable SHA256 over the entire canonical body.

        Identical inputs, spec, implementation and seed give an identical
        fingerprint. Any difference anywhere -- one coordinate, one warning, one
        provenance entry -- gives a different one.
        """
        return fingerprint(self.model_dump(mode="json"))

    # ------------------------------------------------------------- derivation --

    def with_metrics(
        self,
        *,
        height: MetricValues | Literal[False] | None = False,
        colour: MetricValues | Literal[False] | None = False,
    ) -> SociomapArtifact:
        """Return a copy with height and/or colour replaced; layout is unchanged.

        Pass ``None`` to clear a metric. ``False`` (the default) leaves it as is.
        The relation, layout, spec and provenance are carried by reference, so the
        derived artifact answers "why is this point here" identically.
        """
        update: dict[str, Any] = {}
        if height is not False:
            update["height"] = height
        if colour is not False:
            update["colour"] = colour
        return self.model_copy(update=update)

    # ---------------------------------------------------------- serialisation --

    def to_payload(self) -> dict[str, Any]:
        """JSON-ready payload carrying the body plus its recorded fingerprints.

        The fingerprints are redundant with the body on purpose:
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
