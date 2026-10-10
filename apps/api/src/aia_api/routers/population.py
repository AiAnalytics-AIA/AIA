"""The population registry, read-only (plan ``population-operations.md`` P2).

``GET /population`` -- the Czech dataset's registered versions (where each stands,
derived from the populations and their history, never stored), its STATIC and LIVE
populations, and every promotion with who made it and why. Any member of the
organization may read it: it is metadata about the shared layer every study is
computed over, and it carries no panel row, no field value and no client's data.

Nothing here writes. Import, establish and promote are a configured operator's, through
``python -m aia_executors.population_ops``; a member who sees LIVE here cannot move it.
"""

from __future__ import annotations

from datetime import datetime

from aia_core.domain.population import PopulationKind, VersionStatus
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17
from aia_core.domain.population.versions import version_status
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from ..dependencies import OrganizationDep, SessionDep
from ..schemas.projects import ErrorResponse

router = APIRouter(
    prefix="/population",
    tags=["population"],
    responses={401: {"model": ErrorResponse, "description": "Not authenticated"}},
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PopulationVersionEntry(_Model):
    version_id: str
    label: str
    content_sha256: str
    row_count: int
    column_count: int
    parent_version_id: str | None
    status: VersionStatus
    #: A runtime-eligible status: a run may be resolved against this version.
    runtime_eligible: bool
    companions_attached: bool
    imported_at: datetime
    imported_by: str
    provenance: str


class PopulationEntry(_Model):
    population_id: str
    kind: PopulationKind
    current_version_id: str
    established_at: datetime
    established_by: str


class PromotionEntry(_Model):
    population_id: str
    from_version_id: str | None
    to_version_id: str
    actor_id: str
    reason: str
    promoted_at: datetime


class PopulationRegistry(_Model):
    dataset_id: str
    contract_id: str
    versions: list[PopulationVersionEntry]
    populations: list[PopulationEntry]
    history: list[PromotionEntry]


@router.get("", response_model=PopulationRegistry, summary="The population registry")
def population_registry(member: OrganizationDep, session: SessionDep) -> PopulationRegistry:
    """Versions, populations and promotion history of the dataset studies run over."""
    del member  # membership is the access (ADR 0019); the registry is no client's
    contract = CZ_SYNTHETIC_V17
    dataset = contract.dataset_id
    registry = PopulationRegistryRepository(session)
    populations = registry.populations(dataset)
    promotions = registry.promotions(dataset)
    versions = sorted(registry.versions(dataset).values(), key=lambda v: v.imported_at)
    entries = []
    for v in versions:
        status = version_status(v.version_id, populations, promotions)
        entries.append(
            PopulationVersionEntry(
                version_id=v.version_id,
                label=v.label,
                content_sha256=v.content_sha256,
                row_count=v.row_count,
                column_count=v.column_count,
                parent_version_id=v.parent_version_id,
                status=status,
                runtime_eligible=status.runtime_eligible,
                companions_attached=registry.companion_set(v.version_id) is not None,
                imported_at=v.imported_at,
                imported_by=v.imported_by,
                provenance=v.provenance,
            )
        )
    return PopulationRegistry(
        dataset_id=dataset,
        contract_id=contract.contract_id,
        versions=entries,
        populations=[
            PopulationEntry(
                population_id=p.population_id,
                kind=p.kind,
                current_version_id=p.current_version_id,
                established_at=p.established_at,
                established_by=p.established_by,
            )
            for p in populations
        ],
        history=[
            PromotionEntry(
                population_id=r.population_id,
                from_version_id=r.from_version_id,
                to_version_id=r.to_version_id,
                actor_id=r.actor_id,
                reason=r.reason,
                promoted_at=r.promoted_at,
            )
            for r in promotions
        ],
    )
