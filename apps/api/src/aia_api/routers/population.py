"""The population registry, read-only (plan ``population-operations.md`` P2).

``GET /population`` -- the Czech dataset's registered versions (where each stands,
derived from the populations and their history, never stored), its STATIC and LIVE
populations, and every promotion with who made it and why. Any member of the
organization may read it: it is metadata about the shared layer every study is
computed over, and it carries no panel row, no field value and no client's data.

``GET /population/versions/{version_id}/characteristics`` -- what one version is made of
(P7c): the contract's weights, the field blocks, every field with its dictionary facts and
what its policy permits for each use, and the 18 built-in subpanels checked against it.
Read from the dictionary the version keeps, by ``aia_core``; no respondent row.

Nothing here writes. Import, establish and promote are a configured operator's, through
``python -m aia_executors.population_ops``; a member who sees LIVE here cannot move it.
"""

from __future__ import annotations

from datetime import datetime

from aia_core.application.population_characteristics import version_characteristics
from aia_core.domain.population import (
    PopulationKind,
    UnknownDatasetVersion,
    VersionIntegrityError,
    VersionStatus,
)
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17
from aia_core.domain.population.subpanels import (
    MEASURED_ON,
    MEASURED_UNDER_WEIGHT,
    SUBPANEL_NOTE,
)
from aia_core.domain.population.versions import version_status
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from fastapi import APIRouter, HTTPException, status
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


class UseAnswerEntry(_Model):
    use: str
    allowed: bool
    reason: str
    obligations: list[str]


class FieldEntry(_Model):
    field: str
    block: str
    source: str
    evidence_status: str
    provenance_class: str
    production_grade: str
    recommended_use: str
    description: str
    persona_eligible: bool
    is_weight: bool
    derived: bool
    uses: list[UseAnswerEntry]


class WeightEntry(_Model):
    role: str
    column: str
    is_default: bool
    expected_total: float | None
    tolerance: float | None


class BlockEntry(_Model):
    block: str
    fields: int


class SubpanelFilterEntry(_Model):
    field: str
    minimum: int | None
    maximum: int | None
    equals: int | None


class SubpanelMeasuredEntry(_Model):
    """18.6.6's own counts, on ``measured_on``; never AIA's measurement."""

    rows: int
    weighted_population: float
    unique_core_donors: int
    effective_core_donors: float
    max_core_reuse: int


class SubpanelEntry(_Model):
    key: str
    name: str
    description: str
    filter: SubpanelFilterEntry
    focus_domains: list[str]
    status: str
    support_tier: str
    measured_by_18_6_6: SubpanelMeasuredEntry
    #: ``null`` while the version's dictionary is not kept: unknown, never usable.
    usable: bool | None
    reason: str | None


class VersionCharacteristicsResponse(_Model):
    version_id: str
    label: str
    dictionary_sha256: str
    dictionary_kept: bool
    weights: list[WeightEntry]
    blocks: list[BlockEntry]
    fields: list[FieldEntry]
    subpanels: list[SubpanelEntry]
    #: The version and weight 18.6.6 measured every subpanel's counts on.
    subpanels_measured_on: str
    subpanels_measured_under_weight: str
    subpanel_note: str


@router.get(
    "/versions/{version_id}/characteristics",
    response_model=VersionCharacteristicsResponse,
    summary="What a population version is made of",
    responses={404: {"model": ErrorResponse, "description": "No such version"}},
)
def population_characteristics(
    version_id: str, member: OrganizationDep, session: SessionDep
) -> VersionCharacteristicsResponse:
    """Weights, blocks, every field's evidence and permitted uses, and the subpanels."""
    del member  # membership is the access (ADR 0019); the population is no client's
    try:
        found = version_characteristics(session, contract=CZ_SYNTHETIC_V17, version_id=version_id)
    except UnknownDatasetVersion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "No such resource."},
        ) from None
    except VersionIntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "population_dictionary_mismatch",
                "message": "The dictionary kept for this version does not match its pin.",
            },
        ) from None
    return VersionCharacteristicsResponse(
        version_id=found.version_id,
        label=found.label,
        dictionary_sha256=found.dictionary_sha256,
        dictionary_kept=found.dictionary_kept,
        weights=[
            WeightEntry(
                role=w.role,
                column=w.column,
                is_default=w.is_default,
                expected_total=w.expected_total,
                tolerance=w.tolerance,
            )
            for w in found.weights
        ],
        blocks=[BlockEntry(block=b, fields=n) for b, n in found.blocks],
        fields=[
            FieldEntry(
                field=f.field,
                block=f.block,
                source=f.source,
                evidence_status=f.evidence_status,
                provenance_class=f.provenance_class,
                production_grade=f.production_grade,
                recommended_use=f.recommended_use,
                description=f.description,
                persona_eligible=f.persona_eligible,
                is_weight=f.is_weight,
                derived=f.derived,
                uses=[
                    UseAnswerEntry(
                        use=u.use.value,
                        allowed=u.allowed,
                        reason=u.reason,
                        obligations=list(u.obligations),
                    )
                    for u in f.uses
                ],
            )
            for f in found.fields
        ],
        subpanels=[
            SubpanelEntry(
                key=sp.subpanel.key,
                name=sp.subpanel.name,
                description=sp.subpanel.description,
                filter=SubpanelFilterEntry(
                    field=sp.subpanel.filter.field,
                    minimum=sp.subpanel.filter.minimum,
                    maximum=sp.subpanel.filter.maximum,
                    equals=sp.subpanel.filter.equals,
                ),
                focus_domains=list(sp.subpanel.focus_domains),
                status=sp.subpanel.status,
                support_tier=sp.subpanel.support_tier,
                measured_by_18_6_6=SubpanelMeasuredEntry(
                    rows=sp.subpanel.measured.rows,
                    weighted_population=sp.subpanel.measured.weighted_population,
                    unique_core_donors=sp.subpanel.measured.unique_core_donors,
                    effective_core_donors=sp.subpanel.measured.effective_core_donors,
                    max_core_reuse=sp.subpanel.measured.max_core_reuse,
                ),
                usable=sp.usable,
                reason=sp.reason,
            )
            for sp in found.subpanels
        ],
        subpanels_measured_on=MEASURED_ON,
        subpanels_measured_under_weight=MEASURED_UNDER_WEIGHT,
        subpanel_note=SUBPANEL_NOTE,
    )
