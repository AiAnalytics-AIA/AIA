"""Request-scoped dependencies: database sessions and the authenticated principal.

Authentication is deliberately pluggable and currently **unfinished**: the AIA
repository has no SSO or identity provider wired up yet, so this module exposes a
single seam (:func:`get_principal`) with a development-only header-based
implementation that refuses to run in production.

Replacing that one function with a real token verifier is the whole of the
authentication integration; nothing else in the codebase reads identity from
anywhere else. See ``docs/architecture/security.md``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.repositories import ProjectRepository
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller.

    ``organization_id`` is the tenant boundary. Every repository is constructed
    with it, so a handler cannot read across tenants even by mistake.
    """

    user_id: str
    organization_id: str
    email: str | None = None
    roles: frozenset[str] = frozenset()

    def has_role(self, role: str) -> bool:
        """True when the principal holds ``role``."""
        return role in self.roles


def get_engine(request: Request):
    """Return the process-wide engine created during application startup."""
    engine = getattr(request.app.state, "engine", None)
    if engine is None:  # pragma: no cover - startup guarantees this
        raise RuntimeError("database engine is not initialised")
    return engine


def get_session(request: Request) -> Iterator[Session]:
    """Yield a request-scoped session, committing on success.

    One transaction per request means a handler that writes a revision, an event
    and a job record either persists all three or none of them.
    """
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:  # pragma: no cover - startup guarantees this
        raise RuntimeError("session factory is not initialised")

    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_principal(
    settings: Annotated[Settings, Depends(get_settings)],
    x_aia_user: Annotated[str | None, Header(alias="X-AIA-User")] = None,
    x_aia_org: Annotated[str | None, Header(alias="X-AIA-Org")] = None,
) -> Principal:
    """Resolve the authenticated principal.

    **Development seam.** Outside production this trusts ``X-AIA-User`` and
    ``X-AIA-Org`` headers so the API is usable before an identity provider is
    connected. In production it refuses every request, because trusting a
    client-supplied identity header would make tenant isolation meaningless.

    The replacement implementation must verify a signed token and derive both ids
    from its verified claims.
    """
    if settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "code": "auth_not_configured",
                "message": (
                    "No identity provider is configured. Production refuses "
                    "header-based identity; wire get_principal to the real verifier."
                ),
            },
        )

    if not x_aia_user or not x_aia_org:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "unauthenticated",
                "message": "X-AIA-User and X-AIA-Org headers are required in development.",
            },
        )

    return Principal(
        user_id=x_aia_user,
        organization_id=x_aia_org,
        roles=frozenset({"member"}),
    )


def get_project_repository(
    principal: Annotated[Principal, Depends(get_principal)],
    session: Annotated[Session, Depends(get_session)],
) -> ProjectRepository:
    """Return a repository already scoped to the caller's organization.

    ``principal`` is declared before ``session`` deliberately: FastAPI resolves
    sub-dependencies in parameter order, so an unauthenticated request is rejected
    before a database connection is checked out of the pool. Reversing these two
    parameters would let unauthenticated traffic exhaust the connection pool and
    would make the 401 path depend on the database being reachable.
    """
    return ProjectRepository(session, organization_id=principal.organization_id)


SessionDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
ProjectRepositoryDep = Annotated[ProjectRepository, Depends(get_project_repository)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def init_app_state(app, settings: Settings) -> None:
    """Create the engine and session factory once per application.

    Idempotent: a second call reuses the existing engine. Startup can run more than
    once for one app object -- nested test clients do it, and so does an ASGI server
    that re-enters lifespan on reload. Creating a second engine would open a second
    connection pool, and for in-memory SQLite it would silently swap in an empty
    database.
    """
    if getattr(app.state, "engine", None) is not None:
        return

    engine = create_app_engine(settings.database_url or None)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
