"""The population registry, read-only (plan ``population-operations.md`` P2).

``GET /population`` -- the Czech dataset's registered versions (where each stands,
derived from the populations and their history, never stored), its STATIC and LIVE
populations, and every promotion with who made it and why. Any member of the
organization may read it: it is metadata about the shared layer every study is
computed over, and it carries no panel row, no field value and no client's data.

An owned child -- a dimension materialized for one of the organization's clients
(population-operations P4c) -- is listed, and its characteristics read, only within
that organization; to anyone else it does not exist (404, like any scope miss).

``GET /population/versions/{version_id}/characteristics`` -- what one version is made of
(P7c): the contract's weights, the field blocks, every field with its dictionary facts and
what its policy permits for each use, and the 18 built-in subpanels checked against it.
Read from the dictionary the version keeps, by ``aia_core``; no respondent row.

``GET /population/audience-catalogue`` -- what a study's audience may be filtered by
(panel-grounded-respondents 6b): LIVE's current version, the factor catalogue kept for it
(``population_ops record-catalogue``; the research-only factors reduced to their count) and
the 18 built-in subpanels as filters, each checked against it. No respondent row is read.

``POST /population/audience-preview`` -- how many rows a study's audience filters select in
LIVE and whether a run could draw ``n`` from them (6c): counted in this process over LIVE
loaded once per version, through the run's own functions; counts and the sampler's verdict,
never a row. 503 when this deployment has no asset root to load from.

Nothing here writes. Import, establish and promote are a configured operator's, through
``python -m aia_executors.population_ops``; a member who sees LIVE here cannot move it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aia_core.application.audience_catalogue import live_audience_catalogue
from aia_core.application.materialize import child_outcome
from aia_core.application.population_characteristics import version_characteristics
from aia_core.domain.population import (
    MaterializedKind,
    PopulationError,
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
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..dependencies import (
    AudiencePopulationDep,
    AudiencePreviewerDep,
    OrganizationDep,
    SessionDep,
)
from ..schemas.projects import ErrorResponse

router = APIRouter(
    prefix="/population",
    tags=["population"],
    responses={401: {"model": ErrorResponse, "description": "Not authenticated"}},
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MaterializedEntry(_Model):
    """What an owned child adds, and the target beside what its derivation achieved."""

    dimension_id: str
    kind: MaterializedKind
    definition_sha256: str
    method: str
    target: float
    achieved: float
    #: Within the kind's tolerance; a target the derivation left unmet is ``false``.
    target_met: bool
    usable_predictors: list[str]


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
    #: ``null`` on a shared version; on an owned child, the client it was made for.
    owner_client_id: str | None
    #: ``null`` on a shared version; on an owned child, the hash of what it adds.
    extension_sha256: str | None
    #: ``null`` on a shared version; on an owned child, its dimension and outcome.
    materialized: MaterializedEntry | None = None


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
    # Membership is the access (ADR 0019): every shared version, and this
    # organization's own children only.
    contract = CZ_SYNTHETIC_V17
    dataset = contract.dataset_id
    registry = PopulationRegistryRepository(session)
    populations = registry.populations(dataset)
    promotions = registry.promotions(dataset)
    versions = sorted(
        registry.versions(dataset, organization_id=member.organization_id).values(),
        key=lambda v: v.imported_at,
    )
    entries = []
    for v in versions:
        status = version_status(v.version_id, populations, promotions)
        outcome = child_outcome(session, v)
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
                owner_client_id=v.owner.client_id if v.owner is not None else None,
                extension_sha256=v.extension_sha256,
                materialized=(
                    MaterializedEntry(
                        dimension_id=outcome.dimension_id,
                        kind=outcome.kind,
                        definition_sha256=outcome.definition_sha256,
                        method=outcome.method,
                        target=outcome.target,
                        achieved=outcome.achieved,
                        target_met=outcome.target_met,
                        usable_predictors=list(outcome.usable_predictors),
                    )
                    if outcome is not None
                    else None
                ),
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
    #: A field an owned child adds: modelled values, its uses fixed.
    materialized: bool


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
    owner_client_id: str | None
    extension_sha256: str | None


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
    try:
        found = version_characteristics(
            session,
            contract=CZ_SYNTHETIC_V17,
            version_id=version_id,
            organization_id=member.organization_id,
        )
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
                "message": "What is kept for this version does not match its pins.",
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
                materialized=f.materialized,
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
        owner_client_id=found.owner_client_id,
        extension_sha256=found.extension_sha256,
    )


# --------------------------------------------------------------------------- #
# The audience catalogue (panel-grounded-respondents 6b)
# --------------------------------------------------------------------------- #


class CatalogueValue(_Model):
    value: str
    #: Rows holding it, unweighted, as 18.6.6 counted.
    count: int


class CatalogueFactor(_Model):
    id: str
    column: str
    label: str
    category: str
    category_label: str
    kind: str
    status: str
    filterable: bool
    sensitive: bool
    source: str
    non_null: int
    min: float | None = None
    max: float | None = None
    p10: float | None = None
    p90: float | None = None
    scale_hint: str | None = None
    #: A non-numeric factor's 60 most frequent values; absent on a numeric one.
    values: list[CatalogueValue] | None = None
    #: The version's field policy for AUDIENCE_FILTERING; a refused factor is not a filter.
    policy_allowed: bool
    policy_reason: str


class CatalogueCategory(_Model):
    id: str
    label: str
    description: str
    count: int
    filterable_count: int


class AudienceSubpanelEntry(_Model):
    key: str
    name: str
    description: str
    #: The subpanel as the audience filter takes it.
    filters: dict[str, Any]
    status: str
    support_tier: str
    measured_by_18_6_6: SubpanelMeasuredEntry
    usable: bool | None
    reason: str | None


class AudienceCatalogueResponse(_Model):
    version_id: str
    version_label: str
    catalogue_version: str
    categories: list[CatalogueCategory]
    factors: list[CatalogueFactor]
    filterable_count: int
    #: Every factor the catalogue holds, the research-only ones not sent included.
    factor_count: int
    logic: str
    subpanels: list[AudienceSubpanelEntry]
    subpanels_measured_on: str
    subpanel_note: str


@router.get(
    "/audience-catalogue",
    response_model=AudienceCatalogueResponse,
    summary="What a study's audience may be filtered by",
    responses={404: {"model": ErrorResponse, "description": "No LIVE population or catalogue"}},
)
def audience_catalogue(
    member: OrganizationDep, session: SessionDep, audience: AudiencePopulationDep
) -> AudienceCatalogueResponse:
    """LIVE's factor catalogue, kept per version, and the built-in subpanels as filters."""
    try:
        found = live_audience_catalogue(
            session,
            contract=audience.contract,
            population_id=audience.population_id,
            organization_id=member.organization_id,
        )
    except VersionIntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "audience_catalogue_mismatch",
                "message": "What is kept for this version does not match its pins.",
            },
        ) from None
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "population_not_established",
                "message": "No LIVE population is established; there is nothing to filter.",
            },
        )
    if found.catalogue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "audience_catalogue_missing",
                "message": (
                    f"No audience catalogue is kept for {found.version_label}; "
                    "population_ops record-catalogue keeps it."
                ),
            },
        )
    catalogue = found.catalogue
    return AudienceCatalogueResponse(
        version_id=found.version_id,
        version_label=found.version_label,
        catalogue_version=catalogue["catalogue_version"],
        categories=[CatalogueCategory(**c) for c in catalogue["categories"]],
        factors=[CatalogueFactor(**f) for f in catalogue["factors"]],
        filterable_count=catalogue["filterable_count"],
        factor_count=catalogue["factor_count"],
        logic=catalogue["logic"],
        subpanels=[
            AudienceSubpanelEntry(
                key=sp.subpanel.key,
                name=sp.subpanel.name,
                description=sp.subpanel.description,
                filters=found.subpanel_filters[sp.subpanel.key],
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
        subpanel_note=SUBPANEL_NOTE,
    )


# --------------------------------------------------------------------------- #
# The audience preview (panel-grounded-respondents 6c)
# --------------------------------------------------------------------------- #


class AudiencePreviewRequest(_Model):
    #: The audience filters in the filter's language (AND across, OR within a dimension).
    filters: dict[str, Any] = Field(default_factory=dict)
    #: The study's planned n; omitted, only the audience is counted.
    n: int | None = Field(default=None, ge=1, le=100_000)

    @field_validator("n", mode="before")
    @classmethod
    def _not_a_boolean(cls, value: Any) -> Any:
        # Lax mode would read true as 1 before any after-validator sees it (AGENTS.md).
        if isinstance(value, bool):
            raise ValueError("n is a number of respondents, not a boolean")
        return value


class PreviewVerdict(_Model):
    ok: bool
    reason: str | None = None
    message: str | None = None
    reasons: list[str] | None = None
    #: A drawable sample's audit status (PASS / PASS_WEIGHTED), its donors and effective n.
    status: str | None = None
    sample_donors: int | None = None
    effective_n: float | None = None


class AudiencePreviewResponse(_Model):
    version_id: str
    version_label: str
    population_rows: int
    selected_rows: int | None
    selected_donors: int | None
    filters_applied: dict[str, Any] | None
    audience: PreviewVerdict
    n: int | None
    sample: PreviewVerdict | None
    #: The seed the preview's draw used; a run draws with its own.
    seed: int


@router.post(
    "/audience-preview",
    response_model=AudiencePreviewResponse,
    response_model_exclude_none=False,
    summary="How many an audience selects, and whether a run could sample it",
    responses={
        404: {"model": ErrorResponse, "description": "No LIVE population"},
        503: {"model": ErrorResponse, "description": "No preview in this deployment"},
    },
)
def audience_preview(
    body: AudiencePreviewRequest,
    member: OrganizationDep,
    session: SessionDep,
    previewer: AudiencePreviewerDep,
) -> AudiencePreviewResponse:
    """Counts and the sampler's verdict over LIVE; never a row."""
    if previewer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "audience_preview_unavailable",
                "message": "This deployment cannot count an audience: no population is mounted.",
            },
        )
    try:
        answer = previewer.preview(session, body.filters, body.n)
    except PopulationError as exc:
        # The population would not load (a file missing, a hash that does not match): the
        # preview cannot count, and says so; a run would park on the same refusal.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "population_unavailable",
                "message": f"LIVE could not be loaded to count: {type(exc).__name__}.",
            },
        ) from None
    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "population_not_established",
                "message": "No LIVE population is established; there is nothing to count.",
            },
        )
    return AudiencePreviewResponse(**answer)
