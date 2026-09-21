"""FastAPI application factory.

The app is built by a factory rather than created at import time so that tests can
construct an isolated instance with its own settings and database.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import Settings, get_settings
from .dependencies import init_app_state
from .observability import (
    RequestContextMiddleware,
    configure_logging,
    install_exception_handlers,
)
from .routers import health, projects, scope

API_PREFIX = "/api/v1"

DESCRIPTION = """
AIA research and simulation platform API.

**Durability model.** A project is the source of truth. Content changes create
immutable revisions; completed stages upstream of a change are preserved so their
artifacts are reused rather than recomputed. Workflows and jobs orchestrate work
against a project but are never authoritative.

**Scope.** Client and Study are hard isolation boundaries. Every client-derived
object resolves to a client and a study, and scope is injected from authenticated
context -- never from a request body or a model-generated argument. A resource the
caller has no grant on returns 404, not 403.

**Authentication vs authorization.** A token proves identity only. Roles, client
access and study access are AIA's own decision, answered from PostgreSQL, so a
token cannot grant itself access.

**Provider behaviour.** There is no silent provider fallback. A provider or model
change is explicit, audited, and does not invalidate completed work.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application."""
    resolved = settings or get_settings()
    resolved.validate_for_production()
    configure_logging(level=resolved.log_level, fmt=resolved.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Open the database pool on startup and dispose of it on shutdown.

        Only the call that actually created the engine disposes it, so a nested or
        re-entrant lifespan cannot close a pool that is still in use.
        """
        owns_engine = getattr(app.state, "engine", None) is None
        init_app_state(app, resolved)
        logging.getLogger("aia.startup").info(
            "api started",
            extra={"context": {"env": resolved.env.value, "version": resolved.version}},
        )
        try:
            yield
        finally:
            engine = getattr(app.state, "engine", None)
            if owns_engine and engine is not None:
                engine.dispose()
                app.state.engine = None

    app = FastAPI(
        title="AIA API",
        version=resolved.version,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs" if resolved.docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if resolved.docs_enabled else None,
    )
    app.state.settings = resolved

    # Request context wraps everything, so even a rejected request is logged with
    # a correlation id.
    #
    # There is no longer a blanket production auth gate: it has been replaced by
    # two stronger, narrower guarantees. Settings.validate_for_production() refuses
    # to boot a deployed environment that is not configured for Cognito, and
    # DevelopmentIdentityProvider refuses to construct outside local/test. A gate
    # here would additionally have blocked correctly configured Cognito traffic.
    app.add_middleware(RequestContextMiddleware)
    if resolved.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
        )

    install_exception_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(scope.router, prefix=API_PREFIX)
    app.include_router(projects.router, prefix=API_PREFIX)
    return app


def check_database(app: FastAPI) -> bool:
    """Return True when the database answers a trivial query.

    Used by the readiness probe. Liveness deliberately does not check the database:
    a database outage should not cause the orchestrator to kill otherwise healthy
    API pods.
    """
    engine = getattr(app.state, "engine", None)
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logging.getLogger("aia.health").warning("database probe failed", exc_info=True)
        return False


app = create_app()
