"""Settings → Stav systému (settings-backends SB4): the deployment's latest smoke run and
GlitchTip's view of AIA's errors, for an organization OWNER or ADMIN.

The smoke results are what ``bin/smoke.sh`` printed on the host after the deploy, kept by
``aia_executors.smoke_record``. GlitchTip is read only with a read-only token; without one the
answer says it is not configured, and a GlitchTip that cannot be read says why without
failing the page.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from sqlalchemy.orm import Session

from ..domain.scope import OrganizationContext, ScopeDenied
from ..infrastructure.deploy_smoke_repository import (
    DeploySmokeRepository,
    SmokeRun,
    tenant_count,
)
from ..infrastructure.glitchtip_status import (
    ErrorTrackingStatus,
    dsn_project_id,
    read_glitchtip,
)
from .develop_seed import SMOKE_ORGANIZATION_SLUG

__all__ = ["ErrorTracking", "error_tracking", "latest_smoke_run"]

#: The develop seed's synthetic smoke organization: the deployment's own, no tenant
#: (``application/develop_seed.py`` SMOKE_ORGANIZATION_SLUG).
_NO_TENANT: Final = frozenset({SMOKE_ORGANIZATION_SLUG})


def _single_tenant(session: Session, admin: OrganizationContext) -> None:
    """Both reads are the deployment's, not the organization's: the smoke proves every
    tenant's deployment and GlitchTip holds every tenant's errors. An organization's OWNER or
    ADMIN reads them only while the deployment holds that organization alone; with more, it
    takes an operator's gate, which does not exist yet (ScopeDenied ``deployment_shared``)."""
    admin.require_administer()
    if tenant_count(session, excluding_slugs=_NO_TENANT) > 1:
        raise ScopeDenied(
            "the deployment holds more than one organization", reason="deployment_shared"
        )


def latest_smoke_run(session: Session, admin: OrganizationContext) -> SmokeRun | None:
    """The newest smoke run kept, or ``None``. OWNER or ADMIN of the deployment's one
    organization."""
    _single_tenant(session, admin)
    return DeploySmokeRepository(session, admin).latest()


@dataclass(frozen=True, slots=True)
class ErrorTracking:
    configured: bool
    dashboard_url: str | None
    status: ErrorTrackingStatus


def error_tracking(
    session: Session,
    admin: OrganizationContext,
    *,
    token: str,
    api_url: str,
    dashboard_url: str,
    dsn: str,
    now: datetime | None = None,
) -> ErrorTracking:
    """GlitchTip's issues, alerts and uptime as the read-only token reads them; not configured
    without a token (nothing is asked). OWNER or ADMIN of the deployment's one organization."""
    _single_tenant(session, admin)
    dashboard = dashboard_url.strip() or None
    if not token.strip():
        return ErrorTracking(False, dashboard, ErrorTrackingStatus())
    return ErrorTracking(
        True,
        dashboard,
        read_glitchtip(
            token=token.strip(),
            api_url=api_url,
            dashboard_url=dashboard,
            project_id=dsn_project_id(dsn),
            now=now or datetime.now(UTC),
        ),
    )
