"""Settings → Stav systému (settings-backends SB4, MP6).

``GET /settings/system-status``: the deployment's latest smoke run, the checks not ready first
(FAIL, NOT_RUNNABLE), then the passes; ``latest: null`` when no run has been kept.
``GET /settings/error-tracking``: GlitchTip's open issues of the last seven days, its alert
rules and uptime monitors, read with a read-only token; ``configured: false`` without one, and
a GlitchTip that cannot be read answers ``error``, never a 500. The token is never returned.

OWNER and ADMIN only, refused 403 ``insufficient_role``. Read-only.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from aia_core.application.system_status import error_tracking, latest_smoke_run
from aia_core.domain.deploy_smoke import SmokeStatus
from aia_core.domain.scope import ScopeDenied
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import OrganizationDep, SessionDep, SettingsDep
from ..schemas.projects import ErrorResponse

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "Not an organization OWNER or ADMIN"},
    404: {"model": ErrorResponse, "description": "Not a member of the organization"},
}

router = APIRouter(prefix="/settings", tags=["settings"], responses=_RESPONSES)


def _admin_only[T](read: Callable[[], T]) -> T:
    try:
        return read()
    except ScopeDenied as exc:
        if exc.reason != "insufficient_role":
            raise
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "insufficient_role",
                "message": "The system's state is read by an OWNER or ADMIN.",
                "details": {"reason": exc.reason},
            },
        ) from exc


class SmokeCheckOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: str
    status: SmokeStatus


class SmokeRunOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    build_sha: str
    ran_at: datetime
    #: True only when every check passed; a NOT_RUNNABLE check is not a pass.
    all_ok: bool
    failed: int
    not_runnable: int
    checks: list[SmokeCheckOut]


class SystemStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latest: SmokeRunOut | None


@router.get(
    "/system-status",
    response_model=SystemStatusResponse,
    summary="The deployment's latest smoke run",
)
def get_system_status(scope: OrganizationDep, session: SessionDep) -> SystemStatusResponse:
    run = _admin_only(lambda: latest_smoke_run(session, scope))
    if run is None:
        return SystemStatusResponse(latest=None)
    failed = sum(1 for c in run.checks if c.status is SmokeStatus.FAIL)
    not_runnable = sum(1 for c in run.checks if c.status is SmokeStatus.NOT_RUNNABLE)
    return SystemStatusResponse(
        latest=SmokeRunOut(
            run_id=run.run_id,
            build_sha=run.build_sha,
            ran_at=run.ran_at,
            all_ok=failed == 0 and not_runnable == 0,
            failed=failed,
            not_runnable=not_runnable,
            checks=[SmokeCheckOut(check=c.label, status=c.status) for c in run.checks],
        )
    )


class IssueOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    culprit: str | None
    count: int | None
    last_seen: datetime | None
    url: str | None


class AlertOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    quantity: int | None
    timespan_minutes: int | None
    recipients: int


class MonitorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    #: ``None``: GlitchTip did not say; never read as up.
    is_up: bool | None
    last_change: datetime | None


class ErrorTrackingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    dashboard_url: str | None
    project: str | None
    project_url: str | None
    alerts: list[AlertOut]
    uptime: list[MonitorOut]
    issues_7d: list[IssueOut]
    #: What could not be read, by code (``glitchtip_unreachable``, ``glitchtip_refused_token``,
    #: ``glitchtip_http_<n>``, ``glitchtip_no_project``, ``glitchtip_unexpected_answer``).
    error: str | None


@router.get(
    "/error-tracking",
    response_model=ErrorTrackingResponse,
    summary="GlitchTip: issues, alerts and uptime",
)
def get_error_tracking(scope: OrganizationDep, settings: SettingsDep) -> ErrorTrackingResponse:
    read = _admin_only(
        lambda: error_tracking(
            scope,
            token=settings.glitchtip_api_token.get_secret_value(),
            api_url=settings.glitchtip_api_url,
            dashboard_url=settings.glitchtip_dashboard_url,
            dsn=settings.error_tracking_dsn,
        )
    )
    s = read.status
    return ErrorTrackingResponse(
        configured=read.configured,
        dashboard_url=read.dashboard_url,
        project=s.project,
        project_url=s.project_url,
        alerts=[
            AlertOut(
                name=a.name,
                quantity=a.quantity,
                timespan_minutes=a.timespan_minutes,
                recipients=a.recipients,
            )
            for a in s.alerts
        ],
        uptime=[
            MonitorOut(name=m.name, is_up=m.is_up, last_change=m.last_change) for m in s.uptime
        ],
        issues_7d=[
            IssueOut(
                title=i.title, culprit=i.culprit, count=i.count, last_seen=i.last_seen, url=i.url
            )
            for i in s.issues_7d
        ],
        error=s.error,
    )
