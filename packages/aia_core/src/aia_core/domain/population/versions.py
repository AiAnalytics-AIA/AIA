"""Dataset versions, populations, lineage and promotion.

The semantics preserved here are product contract, recovered from the reference's
``population_context.py`` (``population-subsystem.md`` §7 in AIA-reference). The
reference kept them in a SQLite registry; the schema was an implementation detail,
the behaviours are not:

* **A version is its content.** Identity is derived from the SHA256 of the bytes as
  delivered, so the same bytes always name the same version and a label can never
  be re-pointed at different bytes.
* **Two named populations with different rules.** ``STATIC`` is an immutable
  reproducibility anchor, established once and never moved. ``LIVE`` is the default
  runtime population and changes only by explicit promotion.
* **Lineage is recorded, not inferred.** ``parent_version_id`` links each version
  to the one it was built from, and a LIVE version must descend from the static
  reference.
* **Import never promotes.** Nothing here is reachable from the import path; a
  promotion needs an actor, a reason and the version the actor believes is current.

Nothing here performs I/O. The functions take a snapshot of the registry and
return what should change, so every rule is testable without a database -- the
same split as ``domain.project.plan_save``.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import uuid4

from .errors import (
    LineageError,
    PopulationNotEstablished,
    PromotionConflict,
    PromotionRefused,
    StaticReferenceImmutable,
    UnknownDatasetVersion,
    VersionNotRuntimeEligible,
)

__all__ = [
    "VERSION_ID_HASH_CHARS",
    "DatasetVersion",
    "Population",
    "PopulationKind",
    "PromotionRecord",
    "VersionStatus",
    "ancestry",
    "content_sha256",
    "dataset_version_id",
    "descends_from",
    "is_sha256",
    "new_promotion_id",
    "plan_establish",
    "plan_promotion",
    "require_runtime_eligible",
    "version_status",
]

#: Hex characters of the content hash carried in a version id. The full hash is
#: stored alongside and is the unique key; the id only has to be readable and
#: collision-free in practice (64 bits).
VERSION_ID_HASH_CHARS: Final = 16

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def content_sha256(data: bytes) -> str:
    """Return the lowercase hex SHA256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def is_sha256(value: str) -> bool:
    """True when ``value`` is a lowercase 64-character hex digest."""
    return bool(_SHA256.match(value))


def dataset_version_id(dataset_id: str, sha256: str) -> str:
    """Return the content-derived id of a dataset version.

    Deterministic by construction: importing the same bytes twice names the same
    version, which is what makes import idempotent and a second copy impossible.
    """
    if not dataset_id:
        raise ValueError("dataset_id is required")
    if not is_sha256(sha256):
        raise ValueError(f"not a lowercase sha256 digest: {sha256!r}")
    return f"{dataset_id}@sha256:{sha256[:VERSION_ID_HASH_CHARS]}"


def new_promotion_id() -> str:
    """Return a new promotion record id."""
    return "PRM-" + uuid4().hex[:16]


class PopulationKind(StrEnum):
    """The two population roles. Distinct product concepts, not two copies."""

    #: Immutable reproducibility anchor (``CZ_STATIC_REFERENCE`` -> ``v17_1_2``).
    STATIC = "STATIC"
    #: The default runtime population (``CZ_LIVE`` -> ``v17_4_0``).
    LIVE = "LIVE"


class VersionStatus(StrEnum):
    """Where a registered version stands. Derived from the registry, never stored.

    Storing it would create a second answer to "which version is live" that could
    disagree with the population's pointer -- R4 again, one level down.
    """

    #: Validated and registered, never bound to a population. A build input
    #: (``v17_0_BASE``) or a candidate awaiting promotion. Not runtime-resolvable.
    REGISTERED = "REGISTERED"
    #: The version a STATIC population is pinned to.
    STATIC_REFERENCE = "STATIC_REFERENCE"
    #: The version a LIVE population currently points at.
    LIVE_CURRENT = "LIVE_CURRENT"
    #: Was LIVE, replaced by an explicit promotion. Still resolvable by pin, so a
    #: past run can be reproduced against exactly what it used.
    SUPERSEDED = "SUPERSEDED"

    @property
    def runtime_eligible(self) -> bool:
        """True when a run may be resolved against a version in this status."""
        return self is not VersionStatus.REGISTERED


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    """One immutable, content-addressed snapshot of a dataset.

    Every field is fixed at import. There is no method that changes one, and the
    repository offers no update -- a corrected dataset is a new version with this
    one as its parent.
    """

    version_id: str
    dataset_id: str
    label: str
    content_sha256: str
    byte_size: int
    row_count: int
    column_count: int
    contract_id: str
    dictionary_sha256: str
    field_names_sha256: str
    parent_version_id: str | None
    storage_location: str
    dictionary_location: str
    provenance: str
    imported_at: datetime
    imported_by: str

    def __post_init__(self) -> None:
        for name in ("content_sha256", "dictionary_sha256", "field_names_sha256"):
            if not is_sha256(getattr(self, name)):
                raise ValueError(f"{name} must be a lowercase sha256 digest")
        if self.version_id != dataset_version_id(self.dataset_id, self.content_sha256):
            raise ValueError("version_id must be derived from dataset_id and content_sha256")
        for name in (
            "label",
            "contract_id",
            "storage_location",
            "dictionary_location",
            "imported_by",
        ):
            if not getattr(self, name):
                raise ValueError(f"{name} is required on a dataset version")
        for name in ("byte_size", "row_count", "column_count"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.parent_version_id == self.version_id:
            raise ValueError("a version cannot be its own parent")
        if self.imported_at.tzinfo is None:
            raise ValueError("imported_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Population:
    """A named population and the version it currently resolves to."""

    population_id: str
    dataset_id: str
    kind: PopulationKind
    current_version_id: str
    established_at: datetime
    established_by: str


@dataclass(frozen=True, slots=True)
class PromotionRecord:
    """One append-only entry in a population's history.

    ``from_version_id`` is ``None`` for the establishing entry. For a STATIC
    population that entry is the only one there will ever be.
    """

    promotion_id: str
    population_id: str
    from_version_id: str | None
    to_version_id: str
    actor_id: str
    reason: str
    promoted_at: datetime


# --------------------------------------------------------------------------- #
# Lineage
# --------------------------------------------------------------------------- #


def ancestry(version_id: str, versions: Mapping[str, DatasetVersion]) -> tuple[str, ...]:
    """Return ``version_id`` followed by each ancestor up to its root.

    Raises :class:`UnknownDatasetVersion` for an unregistered start, and
    :class:`LineageError` for a dangling parent or a cycle -- a lineage that cannot
    be walked to a root is not a lineage.
    """
    if version_id not in versions:
        raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
    chain: list[str] = []
    seen: set[str] = set()
    current: str | None = version_id
    while current is not None:
        if current in seen:
            raise LineageError(f"lineage cycle through {current}")
        version = versions.get(current)
        if version is None:
            raise LineageError(f"{chain[-1]} names parent {current}, which is not registered")
        seen.add(current)
        chain.append(current)
        current = version.parent_version_id
    return tuple(chain)


def descends_from(
    version_id: str, ancestor_id: str, versions: Mapping[str, DatasetVersion]
) -> bool:
    """True when ``ancestor_id`` is a strict ancestor of ``version_id``."""
    return ancestor_id in ancestry(version_id, versions)[1:]


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #


def version_status(
    version_id: str,
    populations: Sequence[Population],
    promotions: Sequence[PromotionRecord],
) -> VersionStatus:
    """Derive where ``version_id`` stands from the populations and their history."""
    for population in populations:
        if population.current_version_id == version_id:
            if population.kind is PopulationKind.STATIC:
                return VersionStatus.STATIC_REFERENCE
            return VersionStatus.LIVE_CURRENT
    if any(p.to_version_id == version_id for p in promotions):
        return VersionStatus.SUPERSEDED
    return VersionStatus.REGISTERED


def require_runtime_eligible(version_id: str, status: VersionStatus) -> None:
    """Raise unless a run may be resolved against ``version_id``."""
    if not status.runtime_eligible:
        raise VersionNotRuntimeEligible(
            f"{version_id} has never been bound to a population; it is a build input "
            "or an unpromoted candidate and cannot back a run"
        )


# --------------------------------------------------------------------------- #
# Establish and promote
# --------------------------------------------------------------------------- #


def _require_explicit(actor_id: str, reason: str) -> None:
    if not actor_id:
        raise PromotionRefused("a population change requires an actor")
    if not reason.strip():
        raise PromotionRefused("a population change requires a stated reason")


def _static_for(dataset_id: str, populations: Sequence[Population]) -> Population | None:
    for population in populations:
        if population.dataset_id == dataset_id and population.kind is PopulationKind.STATIC:
            return population
    return None


def plan_establish(
    *,
    population_id: str,
    kind: PopulationKind,
    version: DatasetVersion,
    versions: Mapping[str, DatasetVersion],
    populations: Sequence[Population],
    static_label: str,
    actor_id: str,
    reason: str,
    at: datetime,
) -> tuple[Population, PromotionRecord]:
    """Return the population to create and its establishing history entry.

    * A population id is established once.
    * One STATIC and one LIVE per dataset.
    * STATIC may only be established with the version whose label the import
      contract declares as the static reference -- the choice of reproducibility
      anchor is methodology, not an operator's call.
    * LIVE requires the STATIC population to exist, and its version must strictly
      descend from the static reference.
    """
    _require_explicit(actor_id, reason)
    if not population_id:
        raise PromotionRefused("population_id is required")
    if any(p.population_id == population_id for p in populations):
        raise PromotionRefused(f"population {population_id} is already established")
    if version.version_id not in versions:
        raise UnknownDatasetVersion(f"unknown dataset version {version.version_id}")
    ancestry(version.version_id, versions)  # a broken lineage is refused here too

    same_kind = [p for p in populations if p.dataset_id == version.dataset_id and p.kind is kind]
    if same_kind:
        raise PromotionRefused(
            f"dataset {version.dataset_id} already has a {kind.value} population "
            f"({same_kind[0].population_id})"
        )

    if kind is PopulationKind.STATIC:
        if version.label != static_label:
            raise StaticReferenceImmutable(
                f"the static reference for {version.dataset_id} is {static_label!r}; "
                f"{version.label!r} cannot be established as STATIC"
            )
    else:
        static = _static_for(version.dataset_id, populations)
        if static is None:
            raise PopulationNotEstablished(
                f"establish the STATIC population for {version.dataset_id} before LIVE"
            )
        _require_live_descent(version.version_id, static, versions)

    population = Population(
        population_id=population_id,
        dataset_id=version.dataset_id,
        kind=kind,
        current_version_id=version.version_id,
        established_at=at,
        established_by=actor_id,
    )
    record = PromotionRecord(
        promotion_id=new_promotion_id(),
        population_id=population_id,
        from_version_id=None,
        to_version_id=version.version_id,
        actor_id=actor_id,
        reason=reason,
        promoted_at=at,
    )
    return population, record


def _require_live_descent(
    target_id: str, static: Population, versions: Mapping[str, DatasetVersion]
) -> None:
    if target_id == static.current_version_id:
        raise StaticReferenceImmutable(
            "LIVE may not point at the static reference itself; the static snapshot "
            "stays a separate anchor"
        )
    if not descends_from(target_id, static.current_version_id, versions):
        raise LineageError(
            f"{target_id} does not descend from the static reference "
            f"{static.current_version_id}; a LIVE version must"
        )


def plan_promotion(
    *,
    population: Population,
    target_version_id: str,
    expected_current_version_id: str,
    versions: Mapping[str, DatasetVersion],
    populations: Sequence[Population],
    actor_id: str,
    reason: str,
    at: datetime,
) -> tuple[Population, PromotionRecord]:
    """Return the updated LIVE population and the history entry recording the move.

    Refused for a STATIC population outright, for a stale ``expected_current``, for
    a no-op, for a target of another dataset, for the static reference itself and
    for any target that does not descend from it. The previous version becomes
    SUPERSEDED by virtue of the history entry; nothing about it is rewritten.
    """
    _require_explicit(actor_id, reason)
    if population.kind is PopulationKind.STATIC:
        raise StaticReferenceImmutable(
            f"{population.population_id} is STATIC; it has no promotion path"
        )
    if expected_current_version_id != population.current_version_id:
        raise PromotionConflict(
            f"{population.population_id} is at {population.current_version_id}, "
            f"not {expected_current_version_id}"
        )
    if target_version_id == population.current_version_id:
        raise PromotionRefused(f"{target_version_id} is already current")
    target = versions.get(target_version_id)
    if target is None:
        raise UnknownDatasetVersion(f"unknown dataset version {target_version_id}")
    if target.dataset_id != population.dataset_id:
        raise PromotionRefused(
            f"{target_version_id} belongs to {target.dataset_id}, not {population.dataset_id}"
        )
    static = _static_for(population.dataset_id, populations)
    if static is None:
        raise PopulationNotEstablished(
            f"no STATIC population for {population.dataset_id}; LIVE descent cannot be checked"
        )
    _require_live_descent(target_version_id, static, versions)

    promoted = Population(
        population_id=population.population_id,
        dataset_id=population.dataset_id,
        kind=population.kind,
        current_version_id=target_version_id,
        established_at=population.established_at,
        established_by=population.established_by,
    )
    record = PromotionRecord(
        promotion_id=new_promotion_id(),
        population_id=population.population_id,
        from_version_id=population.current_version_id,
        to_version_id=target_version_id,
        actor_id=actor_id,
        reason=reason,
        promoted_at=at,
    )
    return promoted, record
