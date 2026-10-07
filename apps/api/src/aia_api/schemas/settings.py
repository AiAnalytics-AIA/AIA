"""Response models for the settings document.

The settings page renders these. Every item states **how** it is controlled, so
the client never offers a form for a value that cannot be changed from the
browser, and never has to guess which values are deployment variables.

What powers AIA's model calls is :class:`NativeRuntime`: facts from code, never a
connection or health claim. Whether a switch is on lives in the worker's
environment; the web's ``/config`` displays it.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

__all__ = [
    "LabelledValue",
    "NamedValue",
    "NativeActivity",
    "NativeRuntime",
    "ProviderEntry",
    "ProviderUse",
    "RolePermissions",
    "RuntimeCredential",
    "SettingControl",
    "SettingGroup",
    "SettingItem",
    "SettingsResponse",
    "Vocabularies",
]

#: A setting's value. ``None`` means *not configured*, never zero or false.
SettingValue = str | int | float | bool | list[str] | None


class SettingControl(StrEnum):
    """How a setting is changed."""

    #: A live, audited action over an existing API route; who may is a permission.
    API = "API"
    #: An environment variable, read and validated at process start.
    DEPLOYMENT = "DEPLOYMENT"
    #: A versioned constant in code; changing it is a reviewed change.
    CODE = "CODE"
    #: A product refusal (ARCHITECTURE.md §10). Not configurable at all.
    INVARIANT = "INVARIANT"


class SettingItem(BaseModel):
    """One setting and where it comes from."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: SettingValue
    control: SettingControl
    #: The environment variable, ``module:CONSTANT``, route or document that owns it.
    source: str
    unit: str | None = None


class SettingGroup(BaseModel):
    """A titled group of settings. Titles are the client's; this is the key."""

    model_config = ConfigDict(extra="forbid")

    key: str
    items: list[SettingItem]


class LabelledValue(BaseModel):
    """An enum member with the label the domain gives it, when it gives one."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str | None = None


class ProviderUse(StrEnum):
    """Whether AIA calls a provider, or only reads its identifier from records."""

    #: AIA's own runtime calls it (``aia_core.domain.providers:NATIVE_PROVIDERS``).
    NATIVE = "NATIVE"
    #: The prototype's: read from persisted projects, provenance and the usage
    #: ledger, never offered, and nothing native is sent to it.
    HISTORICAL = "HISTORICAL"


class ProviderEntry(BaseModel):
    """A provider, its user-facing name, whether it bills per token, and its use."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    paid: bool
    use: ProviderUse


class RuntimeCredential(StrEnum):
    """How the worker proves itself to the provider."""

    #: The host's instance or container role (SigV4). There is no key and no login.
    INSTANCE_ROLE = "INSTANCE_ROLE"


class NamedValue(BaseModel):
    """A named identifier, as it is recorded on what it produced."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: str


class NativeActivity(BaseModel):
    """One thing AIA's runtime does with a model, as the code defines it."""

    model_config = ConfigDict(extra="forbid")

    key: str
    #: The workflow step kind that runs it. The worker makes its calls, never a request.
    step_kind: str
    #: What it asks the gateway for (``ModelCapability``); the model policy picks the model.
    capabilities: list[str]
    #: The harness, agent and prompt versions recorded on its outputs.
    versions: list[NamedValue]
    #: Worker environment variables that must all be on for it to run, in order.
    switches: list[str]
    #: The closed actions a person can start, when it offers any.
    actions: list[str]


class NativeRuntime(BaseModel):
    """What powers AIA's model calls, from code.

    A description, not a state: it says what the runtime would call and how, never
    that it is configured, reachable or verified. Those are the worker's to know;
    ``/config`` shows the switches and nothing probes the route.
    """

    model_config = ConfigDict(extra="forbid")

    #: The providers the worker may call (``NATIVE_PROVIDERS``): Amazon Bedrock today.
    providers: list[ProviderEntry]
    credential: RuntimeCredential
    #: The switch the worker reads first. Off, it reads nothing else and builds no AI
    #: runtime; on, a value it refuses in any activity's switch stops the worker.
    switch: str
    #: Switches the worker reads even with ``switch`` off (Deep Research's). Each needs every
    #: switch named before it by an activity that lists it: on without them, or holding a
    #: value the worker refuses, it stops the worker, as a refused switch does.
    strict_switches: list[str]
    activities: list[NativeActivity]
    #: Capabilities no native step asks for yet.
    unused_capabilities: list[str]


class RolePermissions(BaseModel):
    """A study role and the permissions it confers."""

    model_config = ConfigDict(extra="forbid")

    role: str
    permissions: list[str]


class Vocabularies(BaseModel):
    """The domain enums the settings page renders, so it never hard-codes them."""

    model_config = ConfigDict(extra="forbid")

    organization_roles: list[str]
    scope_roles: list[RolePermissions]
    permissions: list[str]
    client_statuses: list[str]
    study_statuses: list[str]
    #: Every provider id a record can carry, each marked ``NATIVE`` or ``HISTORICAL``.
    providers: list[ProviderEntry]
    #: Every one historical: the prototype's per-project rule, kept to read persisted
    #: projects. A native run never consults one.
    provider_policies: list[str]
    model_capabilities: list[str]
    data_classes: list[str]
    research_stages: list[LabelledValue]
    simulation_stages: list[LabelledValue]


class SettingsResponse(BaseModel):
    """The effective settings, as the caller may see them.

    The ``deployment`` group is present only for organization administrators: it
    describes the deployment's security posture, which a member has no need for.
    Secrets are never included, only whether they are configured.
    """

    model_config = ConfigDict(extra="forbid")

    organization_id: str
    your_role: str
    may_administer: bool
    groups: list[SettingGroup]
    ai_runtime: NativeRuntime
    vocabularies: Vocabularies
