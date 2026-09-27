"""The settings document: every control the system has, and how each is set.

Read-only. It serialises the effective deployment settings and the domain's own
constants and vocabularies, so the settings page shows the values the code
actually uses rather than a copy that drifts (ARCHITECTURE.md A6). Changing a
value happens elsewhere: an ``API`` item names its route, a ``DEPLOYMENT`` item
its environment variable, a ``CODE`` item its constant. An ``INVARIANT`` item is
a refusal, and there is nothing to change.

Secrets are reduced to *configured / not configured*. The database URL is
reported only as its backend, never as a string that could carry a password.
"""

from __future__ import annotations

from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.evidence import REFERENCE_THRESHOLDS, TIER_PERMITS
from aia_core.domain.pipeline import RESEARCH_STAGES, SIMULATION_STAGES
from aia_core.domain.population import CZ_DATASET_ID, CZ_LIVE, CZ_STATIC_REFERENCE
from aia_core.domain.population.policy import FIELD_POLICY_VERSION
from aia_core.domain.providers import (
    DEFAULT_MAX_API_COST_USD,
    DEFAULT_POLICY,
    DEFAULT_PROVIDER,
    Provider,
    ProviderPolicy,
    is_paid,
    ui_label,
)
from aia_core.domain.residency import DataClass
from aia_core.domain.scope import (
    DEFAULT_SELF_APPROVAL_ALLOWED,
    ROLE_PERMISSIONS,
    ClientStatus,
    OrganizationRole,
    Permission,
    StudyStatus,
)
from aia_core.domain.simulation import DEFAULT_SPEC_SEED, SIMULATION_CONSTANTS_VERSION
from aia_core.domain.workflow import (
    DEFAULT_CAPACITY_BACKOFF_SECONDS,
    DEFAULT_LEASE_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_QUOTA_FALLBACK_SECONDS,
)
from fastapi import APIRouter, Request

from ..config import Settings
from ..dependencies import OrganizationDep
from ..schemas.projects import ErrorResponse
from ..schemas.settings import (
    LabelledValue,
    ProviderEntry,
    RolePermissions,
    SettingControl,
    SettingGroup,
    SettingItem,
    SettingsResponse,
    Vocabularies,
)

router = APIRouter(
    tags=["settings"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Not a member of an organization"},
    },
)

_API = SettingControl.API
_DEPLOYMENT = SettingControl.DEPLOYMENT
_CODE = SettingControl.CODE
_INVARIANT = SettingControl.INVARIANT


def _item(
    key: str,
    value: object,
    control: SettingControl,
    source: str,
    unit: str | None = None,
) -> SettingItem:
    return SettingItem.model_validate(
        {"key": key, "value": value, "control": control, "source": source, "unit": unit}
    )


def _database_backend(url: str) -> str | None:
    """The backend name only. ``None`` when unset -- never a guessed default."""
    if not url.strip():
        return None
    scheme = url.split(":", 1)[0].split("+", 1)[0].lower()
    return "postgresql" if scheme in ("postgresql", "postgres") else scheme


def _deployment(settings: Settings) -> SettingGroup:
    cognito_configured = all(
        (settings.cognito_region, settings.cognito_user_pool_id, settings.cognito_client_id)
    )
    return SettingGroup(
        key="deployment",
        items=[
            _item("env", settings.env.value, _DEPLOYMENT, "AIA_ENV"),
            _item("version", settings.version, _DEPLOYMENT, "AIA_VERSION"),
            _item("debug", settings.debug, _DEPLOYMENT, "AIA_DEBUG"),
            _item(
                "database_backend",
                _database_backend(settings.database_url),
                _DEPLOYMENT,
                "DATABASE_URL",
            ),
            _item(
                "identity_provider",
                settings.identity_provider,
                _DEPLOYMENT,
                "AIA_IDENTITY_PROVIDER",
            ),
            _item(
                "cognito_configured",
                cognito_configured,
                _DEPLOYMENT,
                "AIA_COGNITO_REGION, AIA_COGNITO_USER_POOL_ID, AIA_COGNITO_CLIENT_ID",
            ),
            _item(
                "cognito_token_use",
                settings.cognito_token_use,
                _DEPLOYMENT,
                "AIA_COGNITO_TOKEN_USE",
            ),
            _item("cors_origins", list(settings.cors_origins), _DEPLOYMENT, "AIA_CORS_ORIGINS"),
            _item(
                "max_request_bytes",
                settings.max_request_bytes,
                _DEPLOYMENT,
                "AIA_MAX_REQUEST_BYTES",
                "bytes",
            ),
            _item("log_level", settings.log_level, _DEPLOYMENT, "AIA_LOG_LEVEL"),
            _item("log_format", settings.log_format, _DEPLOYMENT, "AIA_LOG_FORMAT"),
            _item("docs_enabled", settings.docs_enabled, _DEPLOYMENT, "AIA_ENV"),
        ],
    )


def _groups() -> list[SettingGroup]:
    """Everything that is the same for every caller."""
    thresholds = REFERENCE_THRESHOLDS
    return [
        SettingGroup(
            key="access",
            items=[
                _item("members", None, _API, "POST /api/v1/members"),
                _item("client_grants", None, _API, "POST /api/v1/clients/{client_id}/grants"),
                _item("study_grants", None, _API, "POST /api/v1/studies/{study_id}/grants"),
                _item(
                    "membership_grants_no_data",
                    True,
                    _INVARIANT,
                    "docs/architecture/scope-and-authorization.md",
                ),
            ],
        ),
        SettingGroup(
            key="budgets",
            items=[
                _item("study_budget", None, _API, "PUT /api/v1/studies/{study_id}/budget", "USD"),
                _item(
                    "default_project_max_api_cost",
                    DEFAULT_MAX_API_COST_USD,
                    _CODE,
                    "aia_core.domain.providers:DEFAULT_MAX_API_COST_USD",
                    "USD",
                ),
                _item(
                    "project_max_api_cost",
                    None,
                    _API,
                    "PATCH /api/v1/studies/{study_id}/projects/{project_id}",
                    "USD",
                ),
                _item("no_spend_past_budget", True, _INVARIANT, "ARCHITECTURE.md §10"),
            ],
        ),
        SettingGroup(
            key="approvals",
            items=[
                _item(
                    "default_self_approval",
                    DEFAULT_SELF_APPROVAL_ALLOWED,
                    _CODE,
                    "aia_core.domain.scope:DEFAULT_SELF_APPROVAL_ALLOWED",
                ),
            ],
        ),
        SettingGroup(
            key="ai",
            items=[
                _item(
                    "default_provider",
                    DEFAULT_PROVIDER.value,
                    _CODE,
                    "aia_core.domain.providers:DEFAULT_PROVIDER",
                ),
                _item(
                    "default_provider_policy",
                    DEFAULT_POLICY.value,
                    _CODE,
                    "aia_core.domain.providers:DEFAULT_POLICY",
                ),
                _item(
                    "project_provider_policy",
                    None,
                    _API,
                    "PATCH /api/v1/studies/{study_id}/projects/{project_id}",
                ),
                _item(
                    "single_model_call_path",
                    True,
                    _INVARIANT,
                    "docs/architecture/adr/0005-llm-gateway.md",
                ),
                _item("no_silent_provider_fallback", True, _INVARIANT, "ARCHITECTURE.md §10"),
            ],
        ),
        SettingGroup(
            key="residency",
            items=[
                _item(
                    "eu_residency",
                    True,
                    _INVARIANT,
                    "docs/architecture/adr/0008-eu-data-residency.md",
                ),
                _item("egress_fails_closed", True, _INVARIANT, "aia_core.domain.residency"),
            ],
        ),
        SettingGroup(
            key="workflow",
            items=[
                _item(
                    "lease_seconds",
                    DEFAULT_LEASE_SECONDS,
                    _DEPLOYMENT,
                    "AIA_WORKER_LEASE_SECONDS",
                    "s",
                ),
                _item(
                    "capacity_backoff_seconds",
                    DEFAULT_CAPACITY_BACKOFF_SECONDS,
                    _DEPLOYMENT,
                    "AIA_WORKER_CAPACITY_BACKOFF_SECONDS",
                    "s",
                ),
                _item(
                    "quota_fallback_seconds",
                    DEFAULT_QUOTA_FALLBACK_SECONDS,
                    _DEPLOYMENT,
                    "AIA_WORKER_QUOTA_FALLBACK_SECONDS",
                    "s",
                ),
                _item(
                    "max_attempts",
                    DEFAULT_MAX_ATTEMPTS,
                    _CODE,
                    "aia_core.domain.workflow:DEFAULT_MAX_ATTEMPTS",
                ),
                _item("no_fake_progress", True, _INVARIANT, "ARCHITECTURE.md §10"),
            ],
        ),
        SettingGroup(
            key="population",
            items=[
                _item(
                    "dataset_id", CZ_DATASET_ID, _CODE, "aia_core.domain.population:CZ_DATASET_ID"
                ),
                _item(
                    "static_reference",
                    CZ_STATIC_REFERENCE,
                    _CODE,
                    "aia_core.domain.population:CZ_STATIC_REFERENCE",
                ),
                _item("live_population", CZ_LIVE, _CODE, "aia_core.domain.population:CZ_LIVE"),
                _item(
                    "field_policy_version",
                    FIELD_POLICY_VERSION,
                    _CODE,
                    "aia_core.domain.population.policy:FIELD_POLICY_VERSION",
                ),
                _item(
                    "population_bound_once_per_run",
                    True,
                    _INVARIANT,
                    "docs/architecture/population.md",
                ),
            ],
        ),
        SettingGroup(
            key="evidence",
            items=[
                _item(
                    "min_cell",
                    thresholds.min_cell,
                    _CODE,
                    "aia_core.domain.evidence:REFERENCE_THRESHOLDS",
                    "n",
                ),
                _item(
                    "n_guard",
                    thresholds.n_guard,
                    _CODE,
                    "aia_core.domain.evidence:REFERENCE_THRESHOLDS",
                    "n_eff",
                ),
                _item(
                    "indicative",
                    thresholds.indicative,
                    _CODE,
                    "aia_core.domain.evidence:REFERENCE_THRESHOLDS",
                    "n_eff",
                ),
                _item(
                    "min_layer_donors",
                    thresholds.min_layer_donors,
                    _CODE,
                    "aia_core.domain.evidence:REFERENCE_THRESHOLDS",
                    "n",
                ),
                _item(
                    "indicative_layer_donors",
                    thresholds.indicative_layer_donors,
                    _CODE,
                    "aia_core.domain.evidence:REFERENCE_THRESHOLDS",
                    "n",
                ),
                *(
                    _item(
                        f"tier_{tier.value}_permits",
                        sorted(use.value for use in uses),
                        _CODE,
                        "aia_core.domain.evidence:TIER_PERMITS",
                    )
                    for tier, uses in sorted(TIER_PERMITS.items())
                ),
                _item("no_invented_certainty", True, _INVARIANT, "ARCHITECTURE.md §10"),
            ],
        ),
        SettingGroup(
            key="simulation",
            items=[
                _item(
                    "constants_version",
                    SIMULATION_CONSTANTS_VERSION,
                    _CODE,
                    "aia_core.domain.simulation:SIMULATION_CONSTANTS_VERSION",
                ),
                _item(
                    "default_spec_seed",
                    DEFAULT_SPEC_SEED,
                    _CODE,
                    "aia_core.domain.simulation:DEFAULT_SPEC_SEED",
                ),
                _item("no_visualisation_mutation", True, _INVARIANT, "ARCHITECTURE.md §10"),
            ],
        ),
    ]


def _vocabularies() -> Vocabularies:
    return Vocabularies(
        organization_roles=[r.value for r in OrganizationRole],
        scope_roles=[
            RolePermissions(
                role=role.value,
                permissions=[p.value for p in Permission if p in granted],
            )
            for role, granted in ROLE_PERMISSIONS.items()
        ],
        permissions=[p.value for p in Permission],
        client_statuses=[s.value for s in ClientStatus],
        study_statuses=[s.value for s in StudyStatus],
        providers=[ProviderEntry(id=p.value, label=ui_label(p), paid=is_paid(p)) for p in Provider],
        provider_policies=[p.value for p in ProviderPolicy],
        model_capabilities=[c.value for c in ModelCapability],
        data_classes=[c.value for c in DataClass],
        research_stages=[LabelledValue(id=i, label=label) for i, label in RESEARCH_STAGES],
        simulation_stages=[LabelledValue(id=i, label=label) for i, label in SIMULATION_STAGES],
    )


@router.get("/settings", response_model=SettingsResponse, summary="Effective settings")
def get_settings_document(admin: OrganizationDep, request: Request) -> SettingsResponse:
    """Return every control the system has, its value, and how it is changed.

    Any organization member may read it. The deployment group, which describes the
    deployment's security posture, is included only for OWNER and ADMIN.

    The deployment values are the ones this application was built with
    (``app.state.settings``), not a fresh read of the environment: ``get_settings``
    is process-cached and ignores settings passed to ``create_app``.
    """
    groups = _groups()
    if admin.may_administer:
        settings: Settings = request.app.state.settings
        groups.insert(0, _deployment(settings))
    return SettingsResponse(
        organization_id=admin.organization_id,
        your_role=admin.organization_role.value,
        may_administer=admin.may_administer,
        groups=groups,
        vocabularies=_vocabularies(),
    )
