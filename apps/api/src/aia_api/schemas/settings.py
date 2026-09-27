"""Response models for the settings document.

The settings page renders these. Every item states **how** it is controlled, so
the client never offers a form for a value that cannot be changed from the
browser, and never has to guess which values are deployment variables.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

__all__ = [
    "LabelledValue",
    "ProviderEntry",
    "RolePermissions",
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

    #: An administrative action over an existing API route.
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


class ProviderEntry(BaseModel):
    """A provider, its user-facing name, and whether it bills per token."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    paid: bool


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
    providers: list[ProviderEntry]
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
    vocabularies: Vocabularies
