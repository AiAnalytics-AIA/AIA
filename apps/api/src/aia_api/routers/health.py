"""Health, readiness and version endpoints.

Liveness and readiness are deliberately different: liveness answers "is this
process functioning", readiness answers "should this instance receive traffic".
A database outage must not make the orchestrator restart healthy API pods, so
only readiness touches the database.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from ..config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def health() -> dict[str, str]:
    """Return OK when the process is running. Never touches a dependency."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
        "env": settings.env.value,
    }


@router.get("/ready", summary="Readiness probe")
def ready(request: Request, response: Response) -> dict[str, object]:
    """Return 200 only when every dependency needed to serve traffic is reachable."""
    from ..main import check_database

    database_ok = check_database(request.app)
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if database_ok else "not_ready",
        "checks": {"database": "ok" if database_ok else "unavailable"},
    }
