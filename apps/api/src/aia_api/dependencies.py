"""Request-scoped dependencies: sessions, authentication and authorised scope.

The chain a request goes through:

    Authorization header
      -> IdentityProvider.verify()      authentication: who is this?
      -> user lookup / binding          AIA's own user record
      -> AuthenticatedPrincipal         identity + organization, no privileges
      -> ScopeResolver.study_context()  authorization: what may they touch?
      -> StudyContext                   injected into every repository

Two things this module deliberately does **not** do:

* **Trust token claims for authorization.** A token proves identity. Roles,
  clients and studies come from PostgreSQL, so a misconfigured identity pool
  cannot hand anyone access to a client.
* **Let scope come from a request body.** ``study_id`` is a path parameter
  resolved against the caller's grants. A body field -- or an AI tool argument --
  can never widen scope, because scope is not read from either.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import Annotated

from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.scope import (
    OrganizationContext,
    Permission,
    ScopeDenied,
    StudyContext,
)
from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.storage_settings import build_artifact_store
from fastapi import Depends, FastAPI, Header, HTTPException, Path, Request, status
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .identity import (
    CognitoIdentityProvider,
    CognitoSettings,
    DevelopmentIdentityProvider,
    ExpiredToken,
    IdentityError,
    IdentityProvider,
    IdentityProviderUnavailable,
    TestIdentityProvider,
)
from .observability import request_id_var

logger = logging.getLogger("aia.auth")


# --------------------------------------------------------------------------- #
# Infrastructure
# --------------------------------------------------------------------------- #


def build_identity_provider(settings: Settings) -> IdentityProvider:
    """Construct the configured identity provider.

    Production configuration is validated at startup, so an unexpected value here
    is a programming error rather than a misconfiguration.
    """
    if settings.identity_provider == "cognito":
        return CognitoIdentityProvider(
            CognitoSettings(
                region=settings.cognito_region,
                user_pool_id=settings.cognito_user_pool_id,
                client_id=settings.cognito_client_id,
                token_use=settings.cognito_token_use,
            )
        )
    if settings.identity_provider == "test":
        return TestIdentityProvider()
    # Raises unless the environment grants insecure local identity.
    return DevelopmentIdentityProvider(
        allow_insecure_local_identity=settings.allow_insecure_local_identity
    )


def init_app_state(app: FastAPI, settings: Settings) -> None:
    """Create the engine, session factory, identity provider and artifact store once per app.

    Idempotent: startup can run more than once for one app object -- nested test
    clients do it, and so does a server that re-enters lifespan on reload.
    Creating a second engine would open a second pool, and for in-memory SQLite
    would silently swap in an empty database.
    """
    if getattr(app.state, "engine", None) is not None:
        return

    engine = create_app_engine(settings.database_url or None)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.identity_provider = build_identity_provider(settings)
    # The store's S3 client is created on first use, so building it here costs
    # nothing and needs no credentials until an artifact is actually read.
    app.state.artifact_store = build_artifact_store(settings.storage_settings())
    logger.info(
        "identity provider configured",
        extra={"context": {"provider": app.state.identity_provider.name}},
    )
    logger.info(
        "artifact store configured",
        extra={"context": {"backend": settings.storage_backend}},
    )


def get_session(request: Request) -> Iterator[Session]:
    """Yield a request-scoped session, committing on success.

    One transaction per request, so a handler that writes a revision, an event
    and an audit entry either persists all three or none.
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


def get_artifact_store(request: Request) -> ArtifactStore:
    """Return the process-wide artifact store."""
    store: ArtifactStore | None = getattr(request.app.state, "artifact_store", None)
    if store is None:  # pragma: no cover - startup guarantees this
        raise RuntimeError("artifact store is not initialised")
    return store


def get_app_settings(request: Request) -> Settings:
    """Return the settings the application was built with.

    Not ``get_settings()``, which re-reads the environment: ``create_app`` takes an
    explicit, validated ``Settings``, and a request must see that one, or a test
    that builds its own settings (and any caller of ``create_app``) is silently
    answered with the process environment's.
    """
    settings: Settings | None = getattr(request.app.state, "settings", None)
    return settings if settings is not None else get_settings()


def get_identity_provider(request: Request) -> IdentityProvider:
    """Return the process-wide identity provider."""
    provider: IdentityProvider | None = getattr(request.app.state, "identity_provider", None)
    if provider is None:  # pragma: no cover - startup guarantees this
        raise RuntimeError("identity provider is not initialised")
    return provider


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #


def _unauthenticated(code: str, message: str) -> HTTPException:
    """Build an authentication failure with a bearer challenge."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def principal_from_credential(
    credential: str,
    *,
    session: Session,
    provider: IdentityProvider,
    organization_hint: str | None = None,
) -> AuthenticatedPrincipal:
    """Verify a credential and bind it to an AIA user record, or raise.

    The one place a raw credential becomes a principal: a bearer token on an API
    call and AIA's session cookie (ADR 0018) take the same path, so a rule added
    here applies to both.

    ``organization_id`` comes from the user's membership, and ``organization_hint``
    (``X-AIA-Org``) only disambiguates when they belong to several. It is never
    taken on trust: :meth:`ScopeResolver.study_context` re-checks membership on
    every resolution.
    """
    try:
        identity = provider.verify(credential)
    except ExpiredToken as exc:
        raise _unauthenticated("expired_token", exc.client_message) from exc
    except IdentityProviderUnavailable as exc:
        logger.error("identity provider unavailable", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "identity_unavailable", "message": exc.client_message},
        ) from exc
    except IdentityError as exc:
        # The specific reason goes to the log, not to the client.
        logger.warning(
            "authentication rejected",
            extra={"context": {"reason": exc.reason, "provider": provider.name}},
        )
        raise _unauthenticated("unauthenticated", exc.client_message) from exc

    scope_repo = ScopeRepository(session)
    user = scope_repo.upsert_user(
        email=identity.email or f"{identity.subject}@unknown.invalid",
        display_name=identity.display_name or "",
        external_subject=identity.subject,
    )
    if not user["is_active"]:
        raise _unauthenticated("account_disabled", "This account is disabled.")

    memberships = scope_repo.memberships_for_user(user["user_id"])
    if not memberships:
        # Authenticated but not provisioned. 403 rather than 401: retrying with a
        # different token will not help; an administrator must add them.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "not_provisioned",
                "message": "This account is not a member of any organization.",
            },
        )

    if len(memberships) == 1:
        organization_id = memberships[0]
    elif organization_hint and organization_hint in memberships:
        organization_id = organization_hint
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "organization_required",
                "message": "Specify which organization this request is for.",
                "details": {"organizations": memberships},
            },
        )

    return AuthenticatedPrincipal(
        user_id=user["user_id"],
        organization_id=organization_id,
        email=user["email"],
        external_subject=identity.subject,
        request_id=request_id_var.get() or None,
    )


def bearer_credential(authorization: str | None) -> str | None:
    """The token of an ``Authorization: Bearer <token>`` header, or None when absent."""
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise _unauthenticated("invalid_authorization_header", "Expected 'Bearer <token>'.")
    return value.strip()


def get_principal(
    settings: Annotated[Settings, Depends(get_app_settings)],
    session: Annotated[Session, Depends(get_session)],
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
    authorization: Annotated[str | None, Header()] = None,
    x_aia_subject: Annotated[str | None, Header(alias="X-AIA-Subject")] = None,
    x_aia_org: Annotated[str | None, Header(alias="X-AIA-Org")] = None,
) -> AuthenticatedPrincipal:
    """Authenticate the caller and bind them to an AIA user record.

    The credential is a bearer token in ``Authorization``. In local development
    only, ``X-AIA-Subject`` is accepted instead; the provider that consumes it
    cannot be constructed outside a local environment, so that branch is
    unreachable in a deployment.
    """
    credential = bearer_credential(authorization)
    if credential is None and x_aia_subject and settings.allow_insecure_local_identity:
        credential = x_aia_subject

    if not credential:
        raise _unauthenticated("unauthenticated", "Authentication is required.")

    return principal_from_credential(
        credential, session=session, provider=provider, organization_hint=x_aia_org
    )


# --------------------------------------------------------------------------- #
# Authorization
# --------------------------------------------------------------------------- #


def _not_found_for(exc: ScopeDenied) -> HTTPException:
    """Render a scope denial as 404.

    Always 404, never 403. A 403 would confirm that the study exists, which
    discloses another client's engagement. The distinguishing ``reason`` goes to
    the access audit, not to the response.
    """
    logger.info("scope denied", extra={"context": {"reason": exc.reason}})
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": "No such resource."},
    )


def get_scope_resolver(
    session: Annotated[Session, Depends(get_session)],
) -> ScopeResolver:
    """Return a scope resolver bound to this request's session."""
    return ScopeResolver(session)


def get_organization_context(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_principal)],
    resolver: Annotated[ScopeResolver, Depends(get_scope_resolver)],
) -> OrganizationContext:
    """Authorise organization-level scope, for administration only.

    Carries no client or study id, so it cannot read client research data.
    """
    try:
        return resolver.organization_context(principal)
    except ScopeDenied as exc:
        raise _not_found_for(exc) from exc


StudyIdPath = Annotated[
    str,
    Path(
        min_length=4,
        max_length=64,
        pattern=r"^STU-[0-9a-f]{1,32}$",
        description="Study identifier.",
    ),
]


def get_study_context(
    study_id: StudyIdPath,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_principal)],
    resolver: Annotated[ScopeResolver, Depends(get_scope_resolver)],
) -> StudyContext:
    """Authorise scope for the study named in the path.

    The client id is derived from the study row, never from the request, so a
    mismatched client/study pair cannot be used to read one client's study under
    another client's authorisation.
    """
    try:
        return resolver.study_context(principal, study_id=study_id)
    except ScopeDenied as exc:
        raise _not_found_for(exc) from exc


def require_permission(
    permission: Permission,
) -> Callable[..., StudyContext]:
    """Build a dependency that authorises scope and demands one permission.

    Used as ``Depends(require_permission(Permission.EDIT_STUDY))`` so the
    requirement is visible in the route signature rather than buried in a handler
    body.
    """

    def dependency(
        study_id: StudyIdPath,
        principal: Annotated[AuthenticatedPrincipal, Depends(get_principal)],
        resolver: Annotated[ScopeResolver, Depends(get_scope_resolver)],
    ) -> StudyContext:
        try:
            return resolver.study_context(principal, study_id=study_id, require=permission)
        except ScopeDenied as exc:
            raise _not_found_for(exc) from exc

    return dependency


def get_project_repository(
    scope: Annotated[StudyContext, Depends(get_study_context)],
    session: Annotated[Session, Depends(get_session)],
) -> ProjectRepository:
    """Return a project repository bound to the authorised study scope."""
    return ProjectRepository(session, scope)


def get_scope_repository(
    session: Annotated[Session, Depends(get_session)],
) -> ScopeRepository:
    """Return the scope repository."""
    return ScopeRepository(session)


ArtifactStoreDep = Annotated[ArtifactStore, Depends(get_artifact_store)]
SessionDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
OrganizationDep = Annotated[OrganizationContext, Depends(get_organization_context)]
StudyScopeDep = Annotated[StudyContext, Depends(get_study_context)]
ProjectRepositoryDep = Annotated[ProjectRepository, Depends(get_project_repository)]
ScopeRepositoryDep = Annotated[ScopeRepository, Depends(get_scope_repository)]
ResolverDep = Annotated[ScopeResolver, Depends(get_scope_resolver)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
