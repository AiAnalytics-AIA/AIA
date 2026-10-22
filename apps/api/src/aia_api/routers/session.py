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

The report editor, ONLYOFFICE Docs, is served at an origin of its own, ``docs.<hostname>``
(plan report-editor-hosting), which AIA's session cookie -- the id token itself, host-only, and
deployed ``__Host-aia_session``, which no other host can set (F1) -- never reaches. It has a
gate of its own, over a docs-only cookie (:mod:`aia_api.docs_pass`):

* ``POST /session/docs-ticket``: a signed ticket, 60 s, for an active member calling the API
  with their own token; the pane loads ``<editor>/__aia/session?ticket=…&next=…`` with it.
* ``GET /session/docs``: Caddy sends that URL here, on the editor's origin only. The ticket is
  spent once, the person admitted again and audited, and the ``aia_docs`` cookie set (8 h,
  host-only on the editor's origin) before a redirect to ``next``, a path there.
* ``GET /session/docs-gate``: Caddy's ``forward_auth`` target on the editor's origin, for
  every request: 204 for a valid cookie of a person still an active member; 401 otherwise,
  never a redirect. The editor takes uploads and saves, so POST passes as well as GET and HEAD.

All three answer 404 while the editor is not configured (``AIA_ONLYOFFICE_URL`` and
``AIA_ONLYOFFICE_JWT_SECRET``).

No setting turns it off and no legacy setting touches it: whether AIA can be
reached never depends on the 18.6.6 unit, which the product no longer serves at
all (ADR 0018 decision 5; the panel's own gate went with it).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import quote, urlencode, urlparse

from aia_core.application.docs_session import DocsTicketSpent, open_docs_session
from aia_core.application.scope import AuthenticatedPrincipal
from aia_core.domain.scope import ScopeDenied
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
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
from ..docs_pass import COOKIE_LIFETIME, DocsPasses
from ..identity import IdentityProvider

router = APIRouter(prefix="/session", tags=["session"])

SESSION_COOKIE = "aia_session"
# Deployed, the cookie carries the __Host- prefix: the browser takes it only Secure, Path=/ and
# without a Domain, so a script on docs.<hostname> cannot plant a twin AIA's gate would read
# (report-editor-hosting F1). Local and test serve plain http, where the prefix cannot be set.
HOST_SESSION_COOKIE = "__Host-aia_session"
PAGE_METHODS = frozenset({"GET", "HEAD"})
LOGIN_PATH = "/login"
DOCS_COOKIE = "aia_docs"
# The editor loads its script, then its pages, fonts and documents, uploads images and saves
# copies; a WebSocket upgrade reaches the gate as the GET Caddy turns it into.
DOCS_METHODS = frozenset({"GET", "HEAD", "POST"})
DOCS_SESSION_PATH = "/__aia/session"

ProviderDep = Annotated[IdentityProvider, Depends(get_identity_provider)]


def _forbidden(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail={"code": code, "message": message}
    )


def _not_a_member() -> HTTPException:
    return _forbidden("not_a_member", "AIA is open to active members of an organization.")


def _docs_passes(settings: Settings) -> DocsPasses:
    """The editor's passes, or 404 while the editor is not configured."""
    if not settings.docs_editor_on:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return DocsPasses(settings.onlyoffice_jwt_secret.get_secret_value())


def _docs_unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "docs_unauthenticated", "message": "Open the editor from AIA again."},
    )


def _local_path(uri: str | None) -> str:
    """The forwarded URI if it is a path on this origin, else ``/`` (no open redirect)."""
    if not uri or not uri.startswith("/") or uri.startswith("//") or "\\" in uri:
        return "/"
    # A browser drops tab, CR and LF while it parses a URL ("/<tab>/evil.example" is
    # //evil.example), and no control character belongs in a path the gate sends on.
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in uri):
        return "/"
    return uri


def session_cookie(settings: Settings) -> str:
    """The session cookie's name in this environment: prefixed wherever it is deployed."""
    return HOST_SESSION_COOKIE if settings.is_production else SESSION_COOKIE


def _cookie_attributes(settings: Settings) -> dict[str, Any]:
    """What the session cookie is set and cleared with, once for both: a browser clears only
    the cookie it set, and takes a __Host- cookie only Secure, at Path=/, with no Domain."""
    return {"httponly": True, "secure": settings.is_production, "samesite": "lax", "path": "/"}


def _session_credential(request: Request, settings: Settings) -> str | None:
    """The session cookie's value, or ``None`` when it is absent or sent more than once.

    A planted twin arrives under the same name (a nameless cookie is sent as its value alone),
    and Starlette keeps whichever came last, so a repeated name is no session at all."""
    name = session_cookie(settings)
    sent = [
        chunk
        for chunk in request.headers.get("cookie", "").split(";")
        if chunk.strip().split("=", 1)[0] == name
    ]
    return request.cookies.get(name) if len(sent) == 1 else None


def _set_cookie(response: Response, token: str, settings: Settings) -> None:
    # A browser-session cookie: no Max-Age. The id token inside expires within an
    # hour and is re-verified on every gate call, so an expired session is sent
    # back through /login, where the web client refreshes it.
    response.set_cookie(session_cookie(settings), token, **_cookie_attributes(settings))


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
    response.delete_cookie(session_cookie(settings), **_cookie_attributes(settings))
    if settings.is_production:
        # The unprefixed cookie a browser kept from before the prefix: an id token too.
        response.delete_cookie(SESSION_COOKIE, **_cookie_attributes(settings))
    return response


@router.get(
    "/gate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="forward_auth decision for one request to AIA's pages",
    responses={302: {"description": "Not signed in: go to /login"}},
)
def gate(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    provider: ProviderDep,
    resolver: ResolverDep,
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
    # By its name in this environment alone: deployed, an unprefixed aia_session is not AIA's.
    aia_session = _session_credential(request, settings)
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


@router.post(
    "/docs-ticket",
    summary="A one-time ticket into the report editor's origin",
    responses={404: {"description": "The report editor is not configured"}},
)
def docs_ticket(
    settings: SettingsDep, principal: PrincipalDep, resolver: ResolverDep
) -> dict[str, str]:
    """Sign a 60-second ticket for the caller, an active member, to open the editor with.

    The ticket is spent at ``session_url`` (with ``&next=<path on the editor's origin>``),
    which sets the docs cookie there; it is good once.
    """
    passes = _docs_passes(settings)
    try:
        resolver.authorize_session(principal, audit=False)
    except ScopeDenied as exc:
        raise _not_a_member() from exc
    token, ticket = passes.ticket(
        user_id=principal.user_id,
        organization_id=principal.organization_id,
        now=datetime.now(UTC),
    )
    query = urlencode({"ticket": token})
    return {
        "session_url": f"{settings.onlyoffice_url}{DOCS_SESSION_PATH}?{query}",
        "expires_at": ticket.expires_at.isoformat(),
    }


@router.get(
    "/docs",
    status_code=status.HTTP_302_FOUND,
    summary="Spend a ticket for the docs cookie, on the report editor's origin",
    responses={
        401: {"description": "No valid ticket, or one already spent"},
        404: {"description": "Not the editor's origin, or the editor is not configured"},
    },
)
def docs_session(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    ticket: str | None = None,
    next: str | None = None,  # noqa: A002 -- the query parameter's name
) -> Response:
    """Admit the ticket's person to the editor's origin, once, and send them on to ``next``.

    Served only on that origin (Caddy's ``/__aia/session``): a cookie set from AIA's own
    hostname would be on the wrong host, so any other host is 404 and spends nothing.
    """
    passes = _docs_passes(settings)
    if request.headers.get("host", "").lower() != urlparse(settings.onlyoffice_url).netloc.lower():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    now = datetime.now(UTC)
    claims = passes.read(ticket, kind="ticket", now=now)
    if claims is None or claims.ticket_id is None:
        raise _docs_unauthenticated()
    try:
        open_docs_session(
            session,
            user_id=claims.user_id,
            organization_id=claims.organization_id,
            ticket_id=claims.ticket_id,
            expires_at=claims.expires_at,
            now=now,
        )
    except DocsTicketSpent as exc:
        raise _docs_unauthenticated() from exc
    except ScopeDenied as exc:
        # As at AIA's own sign-in: the refusal's audit row is the record worth keeping.
        session.commit()
        raise _not_a_member() from exc
    cookie, _ = passes.cookie(
        user_id=claims.user_id, organization_id=claims.organization_id, now=now
    )
    response = RedirectResponse(_local_path(next), status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        DOCS_COOKIE,
        cookie,
        max_age=int(COOKIE_LIFETIME.total_seconds()),
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
    return response


@router.get(
    "/docs-gate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="forward_auth decision for one request to the report editor's origin",
    responses={
        401: {"description": "No valid docs cookie"},
        404: {"description": "The report editor is not configured"},
    },
)
def docs_gate(
    settings: SettingsDep,
    resolver: ResolverDep,
    aia_docs: Annotated[str | None, Cookie()] = None,
    x_forwarded_method: Annotated[str | None, Header()] = None,
) -> Response:
    """Decide whether Caddy may pass one request to the Document Server.

    The method first, as AIA's own gate does; then the cookie, then the person, who must
    still be an active member of the organization the cookie names.
    """
    passes = _docs_passes(settings)
    if (x_forwarded_method or "GET").upper() not in DOCS_METHODS:
        raise _forbidden("method_not_allowed", "The report editor takes GET, HEAD and POST.")
    claims = passes.read(aia_docs, kind="cookie", now=datetime.now(UTC))
    if claims is None:
        raise _docs_unauthenticated()
    principal = AuthenticatedPrincipal(
        user_id=claims.user_id, organization_id=claims.organization_id
    )
    try:
        resolver.authorize_session(principal, audit=False)
    except ScopeDenied as exc:
        raise _not_a_member() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
