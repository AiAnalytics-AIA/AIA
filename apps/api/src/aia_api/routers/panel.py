"""The gate in front of AIA's pages and the vendored 18.6.6 unit on the product hostname.

The develop site is AIA's client-first application (ADR 0015); the 18.6.6
interface is an explicit hand-off at ``/classic`` and the unit still serves its
own paths, while AIA rebuilds each feature (ADR 0012). The unit has no identity
model (reference R14), so every request Caddy forwards to ``/app``, ``/classic``
or a unit path first asks this router:

* ``POST /panel/session`` turns the Cognito id token the web client holds into an
  HttpOnly, SameSite=Lax cookie, after the same verification every API call gets
  and an admission decision taken by ``ScopeResolver`` (organization owners and
  admins only).
* ``GET /panel/gate`` is Caddy's ``forward_auth`` target. 204 lets the request
  through to the unit; a browser navigation without a valid session is sent to
  ``/login``; anything else is refused. A state-changing request must name the
  product origin in ``Origin``, because the unit's own origin check is neutralised
  by its relay.
* ``DELETE /panel/session`` clears the cookie.

Transport only: the admission rule is ``ScopeResolver.authorize_legacy_panel`` and
the credential check is ``principal_from_credential``, shared with every other
route. ``AIA_LEGACY_PANEL_ENABLED`` off makes all three answer 404.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from aia_core.domain.scope import ScopeDenied
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from ..config import Settings
from ..dependencies import (
    PrincipalDep,
    ResolverDep,
    SessionDep,
    SettingsDep,
    bearer_credential,
    get_identity_provider,
    principal_from_credential,
)
from ..identity import IdentityProvider

router = APIRouter(prefix="/panel", tags=["legacy panel"])

SESSION_COOKIE = "aia_panel"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
LOGIN_PATH = "/login"


def _require_enabled(settings: SettingsDep) -> Settings:
    if not settings.legacy_panel_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "No such resource."},
        )
    return settings


EnabledSettings = Annotated[Settings, Depends(_require_enabled)]
ProviderDep = Annotated[IdentityProvider, Depends(get_identity_provider)]


def _forbidden(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail={"code": code, "message": message}
    )


def _set_cookie(response: Response, token: str, settings: Settings) -> None:
    # A browser-session cookie: no Max-Age. The id token inside expires within an
    # hour and is re-verified on every gate call, so an expired session is sent
    # back through /login, where the web client refreshes it.
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )


def _local_path(uri: str | None) -> str:
    """The forwarded URI if it is a path on this origin, else ``/`` (no open redirect)."""
    if not uri or not uri.startswith("/") or uri.startswith("//") or "\\" in uri:
        return "/"
    return uri


@router.post(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Open a legacy-panel session from the caller's id token",
)
def open_session(
    settings: EnabledSettings,
    session: SessionDep,
    principal: PrincipalDep,
    resolver: ResolverDep,
    authorization: Annotated[str | None, Header()] = None,
    x_aia_subject: Annotated[str | None, Header(alias="X-AIA-Subject")] = None,
) -> Response:
    """Admit the caller to the 18.6.6 interface and set its session cookie.

    Refused with 403 for a member who is not an organization owner or admin; the
    decision, either way, goes to the access audit.
    """
    try:
        resolver.authorize_legacy_panel(principal, audit=True)
    except ScopeDenied as exc:
        # The request session rolls back on any error, which would take the
        # refusal's audit row with it; the refusal is the record worth keeping.
        session.commit()
        raise _forbidden(
            "legacy_panel_denied",
            "The 18.6.6 interface is open to organization owners and admins only.",
        ) from exc
    # The credential get_principal has just verified: the bearer token, or in
    # local development only, the header identity it accepted instead.
    credential = bearer_credential(authorization)
    if credential is None and settings.allow_insecure_local_identity:
        credential = x_aia_subject
    if not credential:  # pragma: no cover - get_principal refused it already
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_cookie(response, credential, settings)
    return response


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Close the legacy-panel session",
)
def close_session(settings: EnabledSettings) -> Response:
    """Clear the session cookie. Needs no credential: clearing one's own cookie is harmless."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, secure=settings.is_production, samesite="lax", path="/"
    )
    return response


@router.get(
    "/gate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="forward_auth decision for one request to the 18.6.6 unit",
    responses={302: {"description": "Not signed in: go to /login"}},
)
def gate(
    settings: EnabledSettings,
    session: SessionDep,
    provider: ProviderDep,
    resolver: ResolverDep,
    aia_panel: Annotated[str | None, Cookie()] = None,
    x_forwarded_method: Annotated[str | None, Header()] = None,
    x_forwarded_uri: Annotated[str | None, Header()] = None,
    origin: Annotated[str | None, Header()] = None,
    accept: Annotated[str | None, Header()] = None,
) -> Response:
    """Decide whether Caddy may forward the request it describes to the unit.

    Order matters: a cross-origin write is refused before any credential is
    looked at, so a forged request learns nothing about the session.
    """
    method = (x_forwarded_method or "GET").upper()
    if method not in SAFE_METHODS and (
        not settings.legacy_panel_origin or origin != settings.legacy_panel_origin
    ):
        raise _forbidden(
            "cross_origin",
            "State-changing requests to the 18.6.6 interface must come from its own pages.",
        )

    navigation = method == "GET" and "text/html" in (accept or "")
    try:
        if not aia_panel:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "unauthenticated", "message": "Sign in to use the panel."},
            )
        principal = principal_from_credential(aia_panel, session=session, provider=provider)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED and navigation:
            target = quote(_local_path(x_forwarded_uri), safe="")
            return RedirectResponse(f"{LOGIN_PATH}?next={target}", status_code=302)
        raise

    try:
        resolver.authorize_legacy_panel(principal, audit=False)
    except ScopeDenied as exc:
        raise _forbidden(
            "legacy_panel_denied",
            "The 18.6.6 interface is open to organization owners and admins only.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
