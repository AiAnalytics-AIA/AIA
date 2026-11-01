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
  resolved against the caller's membership. A body field -- or an AI tool argument --
  can never widen scope, because scope is not read from either.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Annotated, Final, cast

from aia_core.application.audience_preview import AudiencePreviewer, PanelSampler
from aia_core.application.population_double import PopulationDouble, population_double
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.population import CZ_LIVE, PopulationImportContract
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17
from aia_core.domain.population.enrichment import AudienceDimensionsEnricher
from aia_core.domain.scope import (
    OrganizationContext,
    Permission,
    ScopeDenied,
    StudyContext,
)
from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.editor_fetch import LiveSaveFetcher, SaveFetcher
from aia_core.infrastructure.population_source import FilesystemPopulationSource
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.scope_repository import ScopeRepository, SubjectMismatch
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
    # LOCAL AND TEST ONLY: the population double, before the previewer below (RQC10).
    if settings.population_double:
        install_population_double(app, settings)
    # A previewer already installed is kept: the UI workbench installs its fictional one
    # before the server's startup runs this again (panel-grounded-respondents 6f).
    if getattr(app.state, "audience_previewer", None) is None:
        app.state.audience_previewer = build_audience_previewer(settings)
    logger.info(
        "identity provider configured",
        extra={"context": {"provider": app.state.identity_provider.name}},
    )
    logger.info(
        "artifact store configured",
        extra={"context": {"backend": settings.storage_backend}},
    )


@dataclass(frozen=True, slots=True)
class AudiencePopulation:
    """The population the audience routes describe: its import contract and population id.

    The Czech LIVE in every deployment; nothing in configuration changes it. The UI workbench
    (``tools/ui_workbench/api_standin.py``) replaces it on ``app.state`` with a fictional one,
    because fictional rows cannot meet the v17 contract's pins.
    """

    contract: PopulationImportContract
    population_id: str


CZECH_AUDIENCE: Final = AudiencePopulation(contract=CZ_SYNTHETIC_V17, population_id=CZ_LIVE)


def install_population_double(app: FastAPI, settings: Settings) -> None:
    """LOCAL AND TEST ONLY: compose the fictional population double (plan
    ``run-qc-and-checkpoint`` RQC10).

    A new research run then records the double's LIVE (``app.state.run_population``, read by the
    run start), and the audience catalogue and preview read it too, so a run started over HTTP
    has respondents the worker's composition ``aia_executors.population_double`` can draw. The
    double refuses any ``AIA_ENV`` but local and test, and ``validate_for_production`` refuses the
    switch before that, so a deployment never reaches here.

    Nothing is read from the database at startup (the schema may not exist yet); the double is
    established in the transaction of the first request that needs it
    (:func:`ensure_population_double`), idempotently, so a restarted API keeps what it established.
    """
    # AIA_ENV must be named, as the worker's composition requires: the settings default an
    # unset AIA_ENV to local, and an unset environment must refuse the double, never admit it.
    named = settings.env if "env" in settings.model_fields_set else None
    double = population_double(named)
    population = AudiencePopulation(contract=double.contract, population_id=double.population_id)
    app.state.population_double = double
    app.state.run_population = population
    app.state.audience_population = population
    app.state.audience_previewer = double.previewer()
    logging.getLogger("aia.population").warning(
        "population double composed: fictional respondents, local and test only",
        extra={"context": {"population_id": double.population_id}},
    )


def ensure_population_double(request: Request, session: Session) -> None:
    """Establish the population double in this request's transaction when it is composed.

    Concurrent first requests (the audience step reads its catalogue and its preview at once)
    may both find nothing: :meth:`PopulationDouble.establish` writes in a savepoint and reads
    back what the other wrote first, so neither fails; the request commits it with the rest of
    its work."""
    double: PopulationDouble | None = getattr(request.app.state, "population_double", None)
    if double is not None:
        double.establish(session)


def get_run_population(request: Request, session: SessionDep) -> AudiencePopulation:
    """The population a new research run records: the Czech LIVE in every deployment; the
    population double's LIVE only where :func:`install_population_double` composed it."""
    ensure_population_double(request, session)
    found: AudiencePopulation = getattr(request.app.state, "run_population", CZECH_AUDIENCE)
    return found


def get_audience_population(request: Request, session: SessionDep) -> AudiencePopulation:
    """The population the audience catalogue and preview read (the Czech LIVE; the population
    double where it is composed)."""
    ensure_population_double(request, session)
    found: AudiencePopulation = getattr(request.app.state, "audience_population", CZECH_AUDIENCE)
    return found


def build_audience_previewer(settings: Settings) -> AudiencePreviewer | None:
    """The audience preview over LIVE, or ``None`` when no asset root is configured.

    Builds nothing that reads: the population is loaded on the first preview.
    """
    if not settings.population_asset_root:
        return None
    return AudiencePreviewer(
        contract=CZECH_AUDIENCE.contract,
        source=FilesystemPopulationSource(settings.population_asset_root),
        enricher=AudienceDimensionsEnricher(),
        population_id=CZECH_AUDIENCE.population_id,
    )


def get_audience_previewer(request: Request, session: SessionDep) -> AudiencePreviewer | None:
    """The process's audience previewer; ``None`` when this deployment has none."""
    ensure_population_double(request, session)
    previewer: AudiencePreviewer | None = getattr(request.app.state, "audience_previewer", None)
    return previewer


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


# ``scope="function"`` (FastAPI 0.121.0): the code after ``yield`` -- the commit -- runs when the
# endpoint returns, before the response is sent. The default scope for a ``yield`` dependency
# has been ``"request"`` since FastAPI 0.118.0: its exit runs *after* the response has gone, so
# a client held a 201 for a row no other connection could see yet, and a commit that failed was
# rolled back after the client had been told it succeeded
# (tests/test_commit_before_response.py). Every user of the session takes it through this one
# alias: the dependency cache is keyed by scope too, and a ``Depends(get_session)`` without it
# would be a second session in the same request. Nothing may read the session after the
# endpoint returns (a streamed body, a background task): it is closed by then.
SessionDep = Annotated[Session, Depends(get_session, scope="function")]


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
    try:
        user = scope_repo.upsert_user(
            email=identity.email or f"{identity.subject}@unknown.invalid",
            display_name=identity.display_name or "",
            external_subject=identity.subject,
            seen=True,
        )
    except SubjectMismatch as exc:
        # An attempt to sign in as someone else's account: the record worth keeping.
        # The request session rolls back on the error below, so the audit row is
        # committed first (as open_session does with a refused admission).
        scope_repo.record_subject_mismatch(user_id=exc.user_id, request_id=request_id_var.get())
        session.commit()
        logger.warning(
            "authentication refused: e-mail bound to another subject; an administrator "
            "who confirms the change clears it with ScopeRepository.clear_subject",
            extra={"context": {"user_id": exc.user_id, "provider": provider.name}},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "identity_mismatch",
                "message": "This sign-in does not match the account its e-mail belongs to.",
            },
        ) from exc
    if not user["is_active"]:
        raise _unauthenticated("account_disabled", "This account is disabled.")

    memberships = scope_repo.memberships_for_user(user["user_id"])
    if not memberships and scope_repo.memberships_for_user(
        user["user_id"], include_deactivated=True
    ):
        # Every membership deactivated (D-27): said as what it is, not as never provisioned.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "member_deactivated",
                "message": "This account is deactivated in its organization.",
            },
        )
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
    session: SessionDep,
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
    session: SessionDep,
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
    session: SessionDep,
) -> ProjectRepository:
    """Return a project repository bound to the authorised study scope."""
    return ProjectRepository(session, scope)


def get_scope_repository(
    session: SessionDep,
) -> ScopeRepository:
    """Return the scope repository."""
    return ScopeRepository(session)


ArtifactStoreDep = Annotated[ArtifactStore, Depends(get_artifact_store)]
PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_principal)]
OrganizationDep = Annotated[OrganizationContext, Depends(get_organization_context)]
StudyScopeDep = Annotated[StudyContext, Depends(get_study_context)]
ProjectRepositoryDep = Annotated[ProjectRepository, Depends(get_project_repository)]
ScopeRepositoryDep = Annotated[ScopeRepository, Depends(get_scope_repository)]
ResolverDep = Annotated[ScopeResolver, Depends(get_scope_resolver)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_editor_fetcher(request: Request) -> SaveFetcher:
    """What fetches a save back from the report editor's Document Server (RPT8c): the one the
    application was given (a test's), else the live one, on the editor's exact origin."""
    given = getattr(request.app.state, "editor_fetcher", None)
    if given is not None:
        return cast(SaveFetcher, given)
    return LiveSaveFetcher(get_app_settings(request).onlyoffice_url)


EditorFetcherDep = Annotated[SaveFetcher, Depends(get_editor_fetcher)]
AudiencePreviewerDep = Annotated[AudiencePreviewer | None, Depends(get_audience_previewer)]
AudiencePopulationDep = Annotated[AudiencePopulation, Depends(get_audience_population)]
RunPopulationDep = Annotated[AudiencePopulation, Depends(get_run_population)]


def get_panel_sampler(
    request: Request, session: SessionDep, population: RunPopulationDep
) -> PanelSampler | None:
    """A panel run's sample as a start would draw it (run-qc-and-checkpoint RQC6b): the
    previewer's draw, bound to this request's session, over the population a new run records;
    ``None`` when the previewer reads another population (the workbench's stand-in audience) or
    there is none (no ``AIA_POPULATION_ASSET_ROOT``), so a panel forecast reads unknown."""
    previewer: AudiencePreviewer | None = getattr(request.app.state, "audience_previewer", None)
    if previewer is None or previewer.population_id != population.population_id:
        return None
    return lambda filters, n, seed: previewer.panel_sample(session, filters, n, seed)


PanelSamplerDep = Annotated[PanelSampler | None, Depends(get_panel_sampler)]
