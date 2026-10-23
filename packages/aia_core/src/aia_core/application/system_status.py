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

from sqlalchemy.orm import Session

from ..domain.scope import OrganizationContext
from ..infrastructure.deploy_smoke_repository import DeploySmokeRepository, SmokeRun
from ..infrastructure.glitchtip_status import (
    ErrorTrackingStatus,
    dsn_project_id,
    read_glitchtip,
)

__all__ = ["ErrorTracking", "error_tracking", "latest_smoke_run"]


def latest_smoke_run(session: Session, admin: OrganizationContext) -> SmokeRun | None:
    """The newest smoke run kept, or ``None``. OWNER or ADMIN."""
    return DeploySmokeRepository(session, admin).latest()


@dataclass(frozen=True, slots=True)
class ErrorTracking:
    configured: bool
    dashboard_url: str | None
    status: ErrorTrackingStatus


def error_tracking(
    admin: OrganizationContext,
    *,
    token: str,
    api_url: str,
    dashboard_url: str,
    dsn: str,
    now: datetime | None = None,
) -> ErrorTracking:
    """GlitchTip's issues, alerts and uptime as the read-only token reads them; not configured
    without a token (nothing is asked). OWNER or ADMIN."""
    admin.require_administer()
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
