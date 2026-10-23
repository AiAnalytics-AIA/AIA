"""Zpráva in the report editor: the signed config and the version's DOCX (artifact-report RPT8c).

``POST …/report/editor`` signs, for the person asking, the config ONLYOFFICE's ``api.js`` opens
the editor with: the line's session key (a second researcher joins the same co-editing session),
the version's document URL, the callback URL, the person's id and display name (never an
e-mail). ``GET /report-editor/document`` is the Document Server fetching that version: no
person's session reaches it, so it is outside the study tree and let in by two signatures,
ONLYOFFICE's JWT (the request is from *that* Document Server) and AIA's URL token (it was handed
this URL for this version); the scope is the one the token's session names, resolved through
ScopeResolver for the person who opened it.

Both answer 404 until the editor is configured (``Settings.report_editor_on``: the editor's
origin, its secret and AIA's public origin, ``AIA_ONLYOFFICE_CALLBACK_BASE``). The callback, which
stores a save, is the next chunk's.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from aia_core.application.errors import IntegrityError, ObjectNotFound
from aia_core.application.report import INTERNAL_REPORT_MEDIA_TYPE
from aia_core.application.report_editor import (
    EditorSession,
    LineNotFound,
    NotEditable,
    OpenedLine,
    ReportEditor,
    session_by_key,
)
from aia_core.application.research import research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal
from aia_core.domain.scope import ScopeDenied, StudyContext
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import (
    ArtifactStoreDep,
    ResolverDep,
    SessionDep,
    SettingsDep,
    StudyIdPath,
    StudyScopeDep,
)
from ..editor_tokens import EditorTokens, TokenRefused, bearer
from ..schemas.projects import ErrorResponse
from .research import RunIdPath, _not_found, _refused, _report_for_run, _variant
from .runs import artifact_corrupt

router = APIRouter(
    prefix="/studies/{study_id}",
    tags=["report-editor"],
    responses={404: {"model": ErrorResponse, "description": "Not found, or the editor is off"}},
)

#: The API's prefix as main.py mounts it (``API_PREFIX``); a URL the Document Server fetches
#: is built whole.
API_PREFIX = "/api/v1"
#: Optional and unbounded here, so a request without one, or with one too long, is refused by the
#: route (404 while the editor is off, else 403), never answered 422 before the editor's state is
#: read; the route bounds it (:data:`MAX_TOKEN`).
TokenQuery = Annotated[str | None, Query()]
MAX_TOKEN = 2048


class EditorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: ``client`` is named so it is refused by name, never read as another variant.
    variant: Literal["internal", "context", "client"] = "internal"
    deep_research_run_id: str | None = Field(
        default=None, max_length=64, pattern=r"^RUN-[0-9a-f]{1,32}$"
    )
    line: str | None = Field(default=None, max_length=64, pattern=r"^ART-[0-9a-f]{1,32}$")
    #: ``view`` below 768 px (RPT8d): the same session, read only.
    mode: Literal["edit", "view"] = "edit"


def _tokens(settings: Any) -> EditorTokens:
    if not settings.report_editor_on:
        raise HTTPException(404, detail={"code": "not_found", "message": "No such resource."})
    return EditorTokens(settings.onlyoffice_jwt_secret.get_secret_value())


def _now() -> datetime:
    return datetime.now(UTC)


def _composed(
    body: EditorRequest, run_id: str, scope: StudyContext, session: Any, store: Any
) -> Any:
    """The run's current draft of the variant asked for, as the report routes find it."""
    if body.variant == "client":
        raise HTTPException(409, detail={"code": "client_report_not_editable"})
    if body.variant == "internal":
        _step, report = _report_for_run(run_id, scope, session, store)
        if report is None:
            raise HTTPException(409, detail={"code": "report_not_ready"})
        return report
    if body.deep_research_run_id is None:
        raise HTTPException(422, detail={"code": "deep_research_run_id_required"})
    found = _variant(run_id, body.deep_research_run_id, scope, session, store)
    if found.docx is None:
        raise HTTPException(409, detail={"code": "context_report_not_prepared"})
    return found.docx


def _config(
    opened: OpenedLine,
    *,
    scope: StudyContext,
    name: str,
    mode: str,
    settings: Any,
    tokens: EditorTokens,
    now: datetime,
) -> dict[str, Any]:
    # The Document Server's own routes: not under the study, which the token's session names.
    base = f"{settings.onlyoffice_callback_base}{API_PREFIX}/report-editor"
    key = opened.session.document_key
    document = tokens.url_token(
        "document", document_key=key, artifact_id=opened.version.artifact_id, now=now
    )
    callback = tokens.url_token("callback", document_key=key, now=now)
    edit = mode == "edit"
    config: dict[str, Any] = {
        "documentType": "word",
        "document": {
            "fileType": "docx",
            "key": key,
            "title": f"Zpráva, koncept {opened.version.koncept}.docx",
            "url": f"{base}/document?token={document}",
            "permissions": {"edit": edit, "download": True, "print": True, "comment": edit},
        },
        "editorConfig": {
            "callbackUrl": f"{base}/callback?token={callback}",
            "lang": "cs",
            "mode": mode,
            "user": {"id": scope.actor_id, "name": name or "Člen týmu"},
            "customization": {"forcesave": True},
            "coEditing": {"mode": "fast", "change": False},
        },
    }
    return {**config, "token": tokens.sign_config(config, now=now)}


@router.post(
    "/research/runs/{run_id}/report/editor",
    summary="The signed config the report editor opens a run's report with",
    responses={409: {"model": ErrorResponse}},
)
def open_report_editor(
    study_id: StudyIdPath,
    run_id: RunIdPath,
    body: EditorRequest,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    """The line asked for, or the one with the newest version, and its session's config: the
    open session's key when one is open, so co-editors meet in one document. The client report
    is refused by name (409 ``client_report_not_editable``)."""
    tokens = _tokens(settings)
    composed = _composed(body, run_id, scope, session, store)
    now = _now()
    try:
        editor = ReportEditor(session, scope)
        opened = editor.open(
            composed,
            run_id=run_id,
            variant=body.variant,
            deep_research_run_id=body.deep_research_run_id,
            line_id=body.line,
            now=now,
        )
        lines = editor.lines(
            run_id=run_id, variant=body.variant, deep_research_run_id=body.deep_research_run_id
        )
        name = editor.display_name()
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except LineNotFound as exc:
        raise _not_found("line") from exc
    except NotEditable as exc:
        raise HTTPException(409, detail={"code": "report_not_editable"}) from exc
    session.commit()
    return {
        "document_server": settings.onlyoffice_url,
        "config": _config(
            opened,
            scope=scope,
            name=name,
            mode=body.mode,
            settings=settings,
            tokens=tokens,
            now=now,
        ),
        "line_id": opened.line_id,
        "koncept": opened.version.koncept,
        "version_artifact_id": opened.version.artifact_id,
        "lines": [
            {
                "line_id": h.line_id,
                "koncept": h.koncept,
                "version_artifact_id": h.version_id,
                "saved_at": h.saved_at.isoformat(),
                "current_composition": h.line_id == composed.artifact_id,
            }
            for h in lines
        ],
    }


def _session_scope(
    found: EditorSession | None, resolver: Any
) -> tuple[EditorSession, StudyContext]:
    """The session a Document Server request names, and the scope of the person who opened it,
    in the session's own study; 404 for a key no session has, or a person no longer a member."""
    if found is None:
        raise _not_found("editor_session")
    principal = AuthenticatedPrincipal(
        user_id=found.opened_by, organization_id=found.organization_id, request_id="onlyoffice"
    )
    try:
        return found, resolver.study_context(principal, study_id=found.study_id)
    except ScopeDenied as exc:
        raise _not_found("editor_session") from exc


#: The Document Server's routes. It carries no person's session, so these are not under a
#: study: the URL token names the session, and the session its study and run, which the scope is
#: resolved for. A route under ``/studies/{study_id}`` is a person's, scoped by the path first
#: (MVP-ACCEPT AC01 sweeps them as another organization).
document_server = APIRouter(
    prefix="/report-editor",
    tags=["report-editor"],
    responses={404: {"model": ErrorResponse, "description": "Not found, or the editor is off"}},
)


@document_server.get(
    "/document",
    response_class=Response,
    summary="A version's DOCX, as the Document Server fetches it",
    responses={403: {"model": ErrorResponse}},
)
def report_editor_document(
    request: Request,
    session: SessionDep,
    store: ArtifactStoreDep,
    settings: SettingsDep,
    resolver: ResolverDep,
    token: TokenQuery = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    """The version the URL token names, served only to the Document Server holding the editor's
    secret (its JWT) and only for a URL AIA handed it (the token, short-lived)."""
    tokens = _tokens(settings)
    try:
        if token is None or len(token) > MAX_TOKEN:
            raise TokenRefused("no token, or not one")
        tokens.read_onlyoffice(bearer(authorization), url_path=f"{request.url.path}?token={token}")
        claim = tokens.read_url(token, "document", now=_now())
    except TokenRefused as exc:
        raise HTTPException(403, detail={"code": "editor_token_refused"}) from exc
    found, scope = _session_scope(session_by_key(session, claim.document_key), resolver)
    version = ReportEditor(session, scope).version_of(found, str(claim.artifact_id))
    if version is None:
        raise _not_found("editor_version")
    try:
        data = research_artifacts(session, scope, store).read(version.artifact_id)
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    return Response(
        content=data,
        media_type=INTERNAL_REPORT_MEDIA_TYPE,
        headers={"Cache-Control": "no-store"},
    )
