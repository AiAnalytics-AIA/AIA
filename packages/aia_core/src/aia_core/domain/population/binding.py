"""Resolution: which exact version, weight and view a run uses -- decided once.

The reference answered "which population is in use" in four places, each able to
disagree (R4), and one of them swallowed its own failure (R2). Here there is one
function, :func:`resolve_binding`, and one result, :class:`PopulationBinding`,
which a run records at creation and every later read of population data goes
through. Nothing re-resolves mid-run, so a promotion that lands while a run is in
flight cannot change what that run is computed over.

A selector asks for a *population* (``CZ_LIVE``, ``CZ_STATIC_REFERENCE``) or pins
an exact *version*. Neither has a fallback: a population with no version, a
version that is not runtime-eligible, a version imported under another contract
and an undeclared weight role are all refusals.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .contract import PopulationImportContract
from .errors import PopulationError, PopulationNotEstablished, UnknownDatasetVersion
from .versions import (
    DatasetVersion,
    Population,
    PopulationKind,
    PromotionRecord,
    is_sha256,
    require_runtime_eligible,
    version_status,
)
from .weights import resolve_weight_scheme

__all__ = [
    "PopulationBinding",
    "PopulationSelector",
    "PopulationView",
    "ResolutionMode",
    "resolve_binding",
]


class ResolutionMode(StrEnum):
    """How a binding's version was chosen. Recorded, so a reader knows why."""

    LIVE_CURRENT = "LIVE_CURRENT"
    STATIC_REFERENCE = "STATIC_REFERENCE"
    PINNED = "PINNED"


class PopulationView(StrEnum):
    """Which runtime shape a consumer gets. One loader, named views.

    F10 showed the reference's two loaders returning 407 and 408 columns from the
    same bytes. Here the difference is a named view recorded on the binding, not a
    second loader.
    """

    #: The source fields only, exactly as imported. Audit and import checks.
    BASE = "BASE"
    #: Source fields + the enrichment fields + the canonical analysis weight.
    ANALYSIS = "ANALYSIS"


@dataclass(frozen=True, slots=True)
class PopulationSelector:
    """What a caller asks for: a population by id, or an exact version by pin."""

    population_id: str | None = None
    version_id: str | None = None

    def __post_init__(self) -> None:
        if (self.population_id is None) == (self.version_id is None):
            raise ValueError("select a population or pin a version, exactly one")

    @classmethod
    def population(cls, population_id: str) -> PopulationSelector:
        """Select whatever ``population_id`` currently resolves to."""
        return cls(population_id=population_id)

    @classmethod
    def pinned(cls, version_id: str) -> PopulationSelector:
        """Select exactly ``version_id``. For reproducing a recorded run."""
        return cls(version_id=version_id)


@dataclass(frozen=True, slots=True)
class PopulationBinding:
    """The resolved population identity a run is computed over.

    Recorded once per run and never updated. It is a record, not a capability:
    the loader re-verifies every field against the registry and the bytes before
    handing out data, so a binding assembled by hand cannot load anything the
    registry would not have resolved.
    """

    dataset_id: str
    version_id: str
    version_label: str
    content_sha256: str
    contract_id: str
    population_id: str | None
    resolution: ResolutionMode
    weight_role: str
    weight_column: str
    view: PopulationView
    resolved_at: datetime

    def __post_init__(self) -> None:
        if not is_sha256(self.content_sha256):
            raise PopulationError("a binding needs the full content sha256", reason="binding")
        for name in ("dataset_id", "version_id", "version_label", "contract_id"):
            if not getattr(self, name):
                raise PopulationError(f"a binding needs {name}", reason="binding")
        if not self.weight_role or not self.weight_column:
            raise PopulationError("a binding needs a resolved weight", reason="binding")
        if (self.resolution is ResolutionMode.PINNED) != (self.population_id is None):
            raise PopulationError(
                "a pinned binding names no population; a population binding names one",
                reason="binding",
            )
        if self.resolved_at.tzinfo is None:
            raise PopulationError("resolved_at must be timezone-aware", reason="binding")

    def as_record(self) -> dict[str, str | None]:
        """Provenance form, for run metadata, artifacts and reports."""
        return {
            "dataset_id": self.dataset_id,
            "version_id": self.version_id,
            "version_label": self.version_label,
            "content_sha256": self.content_sha256,
            "contract_id": self.contract_id,
            "population_id": self.population_id,
            "resolution": self.resolution.value,
            "weight_role": self.weight_role,
            "weight_column": self.weight_column,
            "view": self.view.value,
            "resolved_at": self.resolved_at.isoformat(),
        }


def resolve_binding(
    selector: PopulationSelector,
    *,
    contract: PopulationImportContract,
    versions: Mapping[str, DatasetVersion],
    populations: Sequence[Population],
    promotions: Sequence[PromotionRecord],
    view: PopulationView,
    weight_role: str | None,
    at: datetime,
) -> PopulationBinding:
    """Resolve ``selector`` to exactly one version, weight and view, or refuse."""
    population: Population | None = None
    if selector.population_id is not None:
        population = next(
            (p for p in populations if p.population_id == selector.population_id), None
        )
        if population is None:
            raise PopulationNotEstablished(
                f"population {selector.population_id} has not been established"
            )
        version_id = population.current_version_id
        mode = (
            ResolutionMode.STATIC_REFERENCE
            if population.kind is PopulationKind.STATIC
            else ResolutionMode.LIVE_CURRENT
        )
    elif selector.version_id is not None:
        version_id = selector.version_id
        mode = ResolutionMode.PINNED
    else:  # pragma: no cover - the selector refuses to be built this way
        raise ValueError("select a population or pin a version, exactly one")

    version = versions.get(version_id)
    if version is None:
        raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
    if version.dataset_id != contract.dataset_id or version.contract_id != contract.contract_id:
        raise PopulationError(
            f"{version_id} was imported under {version.contract_id}, not {contract.contract_id}; "
            "its semantics are not this contract's",
            reason="contract_mismatch",
        )
    require_runtime_eligible(version_id, version_status(version_id, populations, promotions))
    weight = resolve_weight_scheme(contract, weight_role)

    return PopulationBinding(
        dataset_id=version.dataset_id,
        version_id=version.version_id,
        version_label=version.label,
        content_sha256=version.content_sha256,
        contract_id=contract.contract_id,
        population_id=population.population_id if population else None,
        resolution=mode,
        weight_role=weight.role,
        weight_column=weight.column,
        view=view,
        resolved_at=at,
    )
