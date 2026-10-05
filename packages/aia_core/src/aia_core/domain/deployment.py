"""Where a process runs, and what that place allows. Pure: no I/O.

Every rule that depends on the deployment environment is stated here once, so the
API and the worker cannot hold two copies of the same rule with different conditions
(the develop outage of 2026-10-02: the API refused ``AIA_AI_FICTIONAL_CLIENT_IDS``
under ``staging``, the worker only under ``production``).

``develop`` is a deployed environment that always hosts fictional data: it keeps every
deployed-environment guard and is the only deployed environment where fictional
material is allowed. ``staging`` rehearses production and allows what production allows.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

__all__ = [
    "DeploymentEnvironment",
    "fictional_material_problem",
    "parse_environment",
]


class DeploymentEnvironment(StrEnum):
    """The value of ``AIA_ENV``."""

    LOCAL = "local"
    TEST = "test"
    DEVELOP = "develop"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_deployed(self) -> bool:
        """A shared host: deployed-environment guards apply (PostgreSQL, S3, Cognito, …)."""
        return self in (
            DeploymentEnvironment.DEVELOP,
            DeploymentEnvironment.STAGING,
            DeploymentEnvironment.PRODUCTION,
        )

    @property
    def allows_fictional_material(self) -> bool:
        """Whether fictional clients may be named here (``AIA_AI_FICTIONAL_CLIENT_IDS``)."""
        return self in (
            DeploymentEnvironment.LOCAL,
            DeploymentEnvironment.TEST,
            DeploymentEnvironment.DEVELOP,
        )


def parse_environment(raw: str | None) -> DeploymentEnvironment | None:
    """``AIA_ENV`` as an environment; ``None`` when unset or not one of the values."""
    value = (raw or "").strip().lower()
    try:
        return DeploymentEnvironment(value)
    except ValueError:
        return None


def fictional_material_problem(
    environment: DeploymentEnvironment | None, fictional_client_ids: Iterable[str]
) -> str | None:
    """Why these fictional clients may not be named here, or ``None`` when they may.

    An unknown environment refuses: fictional material is allowed only where an
    environment says so, never by default.
    """
    if not any(c.strip() for c in fictional_client_ids):
        return None
    if environment is not None and environment.allows_fictional_material:
        return None
    where = environment.value if environment is not None else "an unknown environment"
    return (
        f"AIA_AI_FICTIONAL_CLIENT_IDS is refused in {where}: fictional material belongs "
        "only in local, test and develop"
    )
