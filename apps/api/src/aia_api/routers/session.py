"""AIA's own session and the gate in front of its pages (ADR 0018 decision 3, OI-59).

The pages under ``/app`` hold no data: they read ``/api/v1`` with the person's own
bearer token, and every client and study is authorized there, per call, by
``ScopeResolver``. What the gate adds is that a signed-out visitor gets the sign-in
page instead of an empty shell, and that nobody who is not an active member of an
organization is served AIA's pages at all. Caddy asks it before every request to
``/app``:

* ``POST /session`` turns the Cognito id token the web client holds into an
  HttpOnly, SameSite=Lax cookie, after the same verification every API call gets
  and the admission decision ``ScopeResolver.authorize_session`` takes: any active
  member of the organization. Opening one is recorded in the access audit.
* ``GET /session/gate`` is Caddy's ``forward_auth`` target. 204 lets the request
  through; a browser navigation without a valid session is sent to ``/login``;
  anything else is refused. The pages take no writes -- the API is ``/api/v1`` --
  so the gate refuses every method but GET and HEAD.
* ``DELETE /session`` clears the cookie.

No setting turns it off and no legacy setting touches it: whether AIA can be
reached never depends on the 18.6.6 unit, which the product no longer serves at
all (ADR 0018 decision 5; the panel's own gate went with it).
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

router = APIRouter(prefix="/session", tags=["session"])

SESSION_COOKIE = "aia_session"
PAGE_METHODS = frozenset({"GET", "HEAD"})
LOGIN_PATH = "/login"

ProviderDep = Annotated[IdentityProvider, Depends(get_identity_provider)]


def _forbidden(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail={"code": code, "message": message}
    )


def _not_a_member() -> HTTPException:
    return _forbidden("not_a_member", "AIA is open to active members of an organization.")


def _local_path(uri: str | None) -> str:
    """The forwarded URI if it is a path on this origin, else ``/`` (no open redirect)."""
    if not uri or not uri.startswith("/") or uri.startswith("//") or "\\" in uri:
        return "/"
    return uri


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


@router.post(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Open an AIA session from the caller's id token",
)
def open_session(
    settings: SettingsDep,
    session: SessionDep,
    principal: PrincipalDep,
    resolver: ResolverDep,
    authorization: Annotated[str | None, Header()] = None,
    x_aia_subject: Annotated[str | None, Header(alias="X-AIA-Subject")] = None,
) -> Response:
    """Admit the caller to AIA's pages and set the session cookie.

    Refused with 403 for someone who is not an active member of the organization;
    the decision, either way, goes to the access audit.
    """
    try:
        resolver.authorize_session(principal, audit=True)
    except ScopeDenied as exc:
        # The request session rolls back on any error, which would take the
        # refusal's audit row with it; the refusal is the record worth keeping.
        session.commit()
        raise _not_a_member() from exc
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


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Close the AIA session")
def close_session(settings: SettingsDep) -> Response:
    """Clear the session cookie. Needs no credential: clearing one's own cookie is harmless."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, secure=settings.is_production, samesite="lax", path="/"
    )
    return response


@router.get(
    "/gate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="forward_auth decision for one request to AIA's pages",
    responses={302: {"description": "Not signed in: go to /login"}},
)
def gate(
    session: SessionDep,
    provider: ProviderDep,
    resolver: ResolverDep,
    aia_session: Annotated[str | None, Cookie()] = None,
    x_forwarded_method: Annotated[str | None, Header()] = None,
    x_forwarded_uri: Annotated[str | None, Header()] = None,
    accept: Annotated[str | None, Header()] = None,
) -> Response:
    """Decide whether Caddy may serve the page request it describes.

    Order matters: a method a page never takes is refused before any credential is
    looked at, so a forged request learns nothing about the session.
    """
    method = (x_forwarded_method or "GET").upper()
    if method not in PAGE_METHODS:
        raise _forbidden("method_not_allowed", "AIA's pages take no writes; the API is /api/v1.")

    navigation = method == "GET" and "text/html" in (accept or "")
    try:
        if not aia_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "unauthenticated", "message": "Sign in to use AIA."},
            )
        principal = principal_from_credential(aia_session, session=session, provider=provider)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED and navigation:
            target = quote(_local_path(x_forwarded_uri), safe="")
            return RedirectResponse(f"{LOGIN_PATH}?next={target}", status_code=302)
        raise

    try:
        resolver.authorize_session(principal, audit=False)
    except ScopeDenied as exc:
        raise _not_a_member() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
