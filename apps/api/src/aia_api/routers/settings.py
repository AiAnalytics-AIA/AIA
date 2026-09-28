"""The settings document: every control the system has, and how each is set.

Read-only. It serialises the effective deployment settings and the domain's own
constants and vocabularies, so the settings page shows the values the code
actually uses rather than a copy that drifts (ARCHITECTURE.md A6). Changing a
value happens elsewhere: an ``API`` item names its route, a ``DEPLOYMENT`` item
its environment variable, a ``CODE`` item its constant. An ``INVARIANT`` item is
a refusal, and there is nothing to change.

Secrets are reduced to *configured / not configured*. The database URL is
reported only as its backend, never as a string that could carry a password.

What powers AIA's model calls is ``ai_runtime``: the one native provider, how the
worker authenticates, and each native AI activity with its capabilities, versions
and switches -- all from code. It never says a switch is on (the API cannot see the
worker's environment; the web's ``/config`` shows it) and never that a route is
connected or verified: nothing here calls a model. The prototype's provider fields
and defaults are in ``ai_history``, so older records stay readable without being
offered as a choice.
"""

from __future__ import annotations

from aia_core.domain import ai_respondent
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.evidence import REFERENCE_THRESHOLDS, TIER_PERMITS
from aia_core.domain.pipeline import RESEARCH_STAGES, SIMULATION_STAGES
from aia_core.domain.population import CZ_DATASET_ID, CZ_LIVE, CZ_STATIC_REFERENCE
from aia_core.domain.population.policy import FIELD_POLICY_VERSION
from aia_core.domain.providers import (
    DEFAULT_MAX_API_COST_USD,
    DEFAULT_POLICY,
    DEFAULT_PROVIDER,
    NATIVE_PROVIDERS,
    Provider,
    ProviderPolicy,
    is_paid,
    ui_label,
)
from aia_core.domain.research_agents import HARNESS_VERSION, ResearchAction
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
from aia_core.domain.workflow_templates import RESEARCH_AGENT, RESEARCH_KINDS
from fastapi import APIRouter

from ..config import Settings
from ..dependencies import OrganizationDep, SettingsDep
from ..schemas.projects import ErrorResponse
from ..schemas.settings import (
    LabelledValue,
    NamedValue,
    NativeActivity,
    NativeRuntime,
    ProviderEntry,
    ProviderUse,
    RolePermissions,
    RuntimeCredential,
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

_PROJECT_PATCH = "PATCH /api/v1/studies/{study_id}/projects/{project_id}"

# The worker's switches (apps/executors/src/aia_executors/ai_runtime.py). Named, not
# read: the API's environment does not carry them. test_settings_presentation.py
# holds each name to the variable the worker reads and Compose passes.
_RUNTIME_SWITCH = "AIA_AI_RUNTIME_ENABLED"
_DESIGN_SWITCH = "AIA_AI_RESEARCH_AGENTS_ENABLED"


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
                _item("clients", None, _API, "POST /api/v1/clients"),
                _item("client_status", None, _API, "PUT /api/v1/clients/{client_id}/status"),
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
            key="studies",
            items=[
                _item("studies", None, _API, "POST /api/v1/studies"),
                _item("study_status", None, _API, "PUT /api/v1/studies/{study_id}/status"),
                _item("study_budget", None, _API, "PUT /api/v1/studies/{study_id}/budget", "USD"),
                _item("no_spend_past_budget", True, _INVARIANT, "ARCHITECTURE.md §10"),
            ],
        ),
        SettingGroup(
            key="approvals",
            items=[
                _item("self_approval", None, _API, "PUT /api/v1/self-approval"),
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
                    "single_model_call_path",
                    True,
                    _INVARIANT,
                    "docs/architecture/adr/0005-llm-gateway.md",
                ),
                _item("no_silent_provider_fallback", True, _INVARIANT, "ARCHITECTURE.md §10"),
                _item("configuration_is_not_verification", True, _INVARIANT, "ARCHITECTURE.md §2"),
            ],
        ),
        # The generic project model's provider fields, carried from the prototype.
        # Still stored and still readable; no native run reads any of them.
        SettingGroup(
            key="ai_history",
            items=[
                _item(
                    "project_default_provider",
                    DEFAULT_PROVIDER.value,
                    _CODE,
                    "aia_core.domain.providers:DEFAULT_PROVIDER",
                ),
                _item(
                    "project_default_provider_policy",
                    DEFAULT_POLICY.value,
                    _CODE,
                    "aia_core.domain.providers:DEFAULT_POLICY",
                ),
                _item(
                    "project_provider_policy",
                    None,
                    _API,
                    _PROJECT_PATCH,
                ),
                _item(
                    "default_project_max_api_cost",
                    DEFAULT_MAX_API_COST_USD,
                    _CODE,
                    "aia_core.domain.providers:DEFAULT_MAX_API_COST_USD",
                    "USD",
                ),
                _item("project_max_api_cost", None, _API, _PROJECT_PATCH, "USD"),
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


def _provider(provider: Provider) -> ProviderEntry:
    return ProviderEntry(
        id=provider.value,
        label=ui_label(provider),
        paid=is_paid(provider),
        use=ProviderUse.NATIVE if provider in NATIVE_PROVIDERS else ProviderUse.HISTORICAL,
    )


def _native_runtime() -> NativeRuntime:
    """What AIA's runtime calls, how, and for what: code facts only.

    Each activity's capabilities are the ones its agent definition asks for
    (``ai_respondent.respondent_agent``, ``research_agents.agent_request``) and the
    worker's composition binds (``apps/executors/src/aia_executors/ai_runtime.py``);
    the tests hold all three to each other, so a new binding cannot reach the worker
    unlisted here.
    """
    fieldwork = NativeActivity(
        key="respondent_fieldwork",
        step_kind=RESEARCH_KINDS["run"],
        capabilities=[ModelCapability.SIMULATION.value],
        versions=[
            NamedValue(name="generator", value=ai_respondent.GENERATOR),
            NamedValue(
                name="agent", value=f"{ai_respondent.AGENT_ID}@{ai_respondent.AGENT_VERSION}"
            ),
            NamedValue(
                name="prompt", value=f"{ai_respondent.PROMPT_ID}@{ai_respondent.PROMPT_VERSION}"
            ),
            NamedValue(name="contract", value=ai_respondent.CONTRACT_VERSION),
            NamedValue(name="roster", value=ai_respondent.ROSTER_VERSION),
        ],
        switches=[_RUNTIME_SWITCH],
        actions=[],
    )
    design = NativeActivity(
        key="design_agents",
        step_kind=RESEARCH_AGENT,
        capabilities=[ModelCapability.RESEARCH_REASONING.value, ModelCapability.CRITIC.value],
        versions=[NamedValue(name="harness", value=HARNESS_VERSION)],
        switches=[_RUNTIME_SWITCH, _DESIGN_SWITCH],
        actions=[a.value for a in ResearchAction],
    )
    activities = [fieldwork, design]
    used = {c for activity in activities for c in activity.capabilities}
    return NativeRuntime(
        providers=[_provider(p) for p in Provider if p in NATIVE_PROVIDERS],
        credential=RuntimeCredential.INSTANCE_ROLE,
        switch=_RUNTIME_SWITCH,
        activities=activities,
        unused_capabilities=[c.value for c in ModelCapability if c.value not in used],
    )


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
        providers=[_provider(p) for p in Provider],
        provider_policies=[p.value for p in ProviderPolicy],
        model_capabilities=[c.value for c in ModelCapability],
        data_classes=[c.value for c in DataClass],
        research_stages=[LabelledValue(id=i, label=label) for i, label in RESEARCH_STAGES],
        simulation_stages=[LabelledValue(id=i, label=label) for i, label in SIMULATION_STAGES],
    )


@router.get("/settings", response_model=SettingsResponse, summary="Effective settings")
def get_settings_document(admin: OrganizationDep, settings: SettingsDep) -> SettingsResponse:
    """Return every control the system has, its value, and how it is changed.

    Any organization member may read it. The deployment group, which describes the
    deployment's security posture, is included only for OWNER and ADMIN. Its values
    are the ones this application was built with (``SettingsDep`` reads
    ``app.state.settings``), not a fresh read of the environment. ``ai_runtime``
    holds no secret, route id, price or client: every member may read it.
    """
    groups = _groups()
    if admin.may_administer:
        groups.insert(0, _deployment(settings))
    return SettingsResponse(
        organization_id=admin.organization_id,
        your_role=admin.organization_role.value,
        may_administer=admin.may_administer,
        groups=groups,
        ai_runtime=_native_runtime(),
        vocabularies=_vocabularies(),
    )
