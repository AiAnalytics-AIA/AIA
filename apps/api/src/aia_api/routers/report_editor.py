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
origin, its secret and AIA's public origin, ``AIA_ONLYOFFICE_CALLBACK_BASE``).
``POST …/report/editor/callback`` is the Document Server telling AIA of a session: in use (1),
saved (6, the timed autosave or a person's save; 2, everyone left), left unchanged (4), or a save
it failed (3, 7). A save is fetched from the editor's own origin and stored as the line's next
version (``report_editor_saves``). It answers ``{"error": 0}`` once done and ``{"error": 1}``
otherwise, so the Document Server tries again; what was not stored is kept on the session for the
pane to say.
"""

from __future__ import annotations

import json
import logging
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
from aia_core.application.report_editor_saves import (
    SaveNotStored,
    VersionNotFound,
    store_save,
    version_changes,
)
from aia_core.application.research import research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal
from aia_core.domain.report.editor import CallbackAction, callback_action
from aia_core.domain.report.saved_changes import changes_payload
from aia_core.domain.scope import Permission, ScopeDenied, StudyContext
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import (
    ArtifactStoreDep,
    EditorFetcherDep,
    ResolverDep,
    SessionDep,
    SettingsDep,
    StudyIdPath,
    StudyScopeDep,
)
from ..editor_tokens import EditorTokens, TokenRefused, bearer
from ..schemas.projects import ErrorResponse
from .research import (
    RunIdPath,
    _approval_fields,
    _export,
    _mark,
    _not_found,
    _refused,
    _report_filename,
    _report_for_run,
    _review_fields,
    _review_headers,
    _variant,
)
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
        #: Why the session's newest save was not stored, for the pane to say; null when none.
        "problem": opened.session.last_problem,
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
    found: EditorSession | None, resolver: Any, *, as_user: str | None = None
) -> tuple[EditorSession, StudyContext]:
    """The session a Document Server request names, and the scope of ``as_user`` (one of the
    people a config was signed for; else the person who opened it), in the session's own study;
    404 for a key no session has, or a person no longer a member."""
    if found is None:
        raise _not_found("editor_session")
    user = as_user if as_user in found.users else found.opened_by
    principal = AuthenticatedPrincipal(
        user_id=user, organization_id=found.organization_id, request_id="onlyoffice"
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


#: Why a callback's save was not stored, logged without the URL (it carries the file link).
log = logging.getLogger("aia.report_editor")


async def _callback_body(request: Request) -> dict[str, Any]:
    """The callback's JSON object, or ``{}`` for anything else: read in the route, so a body it
    cannot parse is refused as unsigned (403, or 404 while the editor is off), never 422. Caddy
    bounds its size."""
    try:
        parsed = json.loads(await request.body())
    except (ValueError, RecursionError):  # a UnicodeDecodeError is a ValueError
        return {}
    return parsed if isinstance(parsed, dict) else {}


CallbackBody = Annotated[dict[str, Any], Depends(_callback_body)]


@document_server.post(
    "/callback",
    summary="The Document Server's callback for an editing session",
    responses={403: {"model": ErrorResponse}},
)
def report_editor_callback(
    session: SessionDep,
    store: ArtifactStoreDep,
    settings: SettingsDep,
    resolver: ResolverDep,
    fetcher: EditorFetcherDep,
    body: CallbackBody,
    token: TokenQuery = None,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    """A session's news, as ONLYOFFICE posts it: its JWT (in the body or the header), the URL
    token naming this session, and the signed key the token's. Only signed fields are read."""
    tokens = _tokens(settings)
    now = _now()
    try:
        if token is None or len(token) > MAX_TOKEN:
            raise TokenRefused("no token, or not one")
        payload = tokens.read_callback(body.get("token"), bearer(authorization))
        claim = tokens.read_url(token, "callback", now=now)
    except TokenRefused as exc:
        raise HTTPException(403, detail={"code": "editor_token_refused"}) from exc
    if payload.get("key") != claim.document_key:
        raise HTTPException(403, detail={"code": "editor_token_refused"})
    try:
        action = callback_action(int(payload.get("status", -1)))
    except (TypeError, ValueError):
        return {"error": 1}
    users = payload.get("users")
    first = users[0] if isinstance(users, list) and users and isinstance(users[0], str) else None
    # A version is stored as its first author's, when a config was signed for them.
    found, scope = _session_scope(
        session_by_key(session, claim.document_key), resolver, as_user=first
    )
    if found.closed_at is not None:
        # A session ends once (status 2 or 4, or idle): a late or replayed callback for it
        # changes nothing, and a save it carries is not stored over a newer session's.
        if action in (CallbackAction.STORE, CallbackAction.STORE_AND_CLOSE):
            log.warning("report editor save not stored", extra={"reason": "session_closed"})
            return {"error": 1}
        return {"error": 0}
    editor = ReportEditor(session, scope)
    if action is CallbackAction.OPEN:
        editor.keep_open(found, now=now)
    elif action is CallbackAction.CLOSE:
        editor.close(found, now=now, reason="unchanged")
    elif action is CallbackAction.LOG:
        editor.note_problem(found, now=now, problem="document_server_save_failed")
        log.warning("report editor save failed", extra={"status": payload.get("status")})
    else:
        url = payload.get("url")
        if not isinstance(users, list) or not isinstance(url, str):
            return {"error": 1}
        try:
            store_save(
                session,
                scope,
                store,
                found,
                url=url,
                origin=settings.onlyoffice_url,
                fetcher=fetcher,
                authors=[str(u) for u in users],
                now=now,
            )
        except SaveNotStored as refused:
            session.commit()  # the problem is kept for the pane
            log.warning("report editor save not stored", extra={"reason": refused.reason})
            return {"error": 1}
        if action is CallbackAction.STORE_AND_CLOSE:
            editor.close(found, now=now, reason="saved")
    session.commit()
    return {"error": 0}


ArtifactIdPath = Annotated[str, Path(max_length=64, pattern=r"^ART-[0-9a-f]{1,32}$")]


def _version(
    run_id: str, artifact_id: str, scope: StudyContext, session: Any, store: Any
) -> tuple[Any, Any, Any]:
    try:
        return version_changes(session, scope, store, run_id=run_id, artifact_id=artifact_id)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except VersionNotFound as exc:
        raise _not_found("editor_version") from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc


#: The variant a version's file names: the internal report's, or its Deep Research run's.
def _file_variant(version: Any) -> str:
    return "zakladni" if version.variant == "internal" else str(version.deep_research_run_id)


@router.get(
    "/research/runs/{run_id}/report/editor/versions/{artifact_id}",
    summary="A saved version of a run's report: its provenance, review and what it changed",
)
def report_editor_version(
    run_id: RunIdPath,
    artifact_id: ArtifactIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> dict[str, Any]:
    """A version of one of the run's report lines, for the doc bar and the approval dialog
    (RPT8d): who saved it and from which version, its review and approval as the run's report
    status says them, and what it changed in the numbers code wrote, as stored beside it (each
    control changed, removed or added, each number typed outside one). ``changes`` null for
    koncept 1, the composer's own; ``uncomparable`` when there was nothing to compare it with,
    never an empty list read as no change. Served whether or not the editor is on: an approved
    version stays readable."""
    version, artifact, changes = _version(run_id, artifact_id, scope, session, store)
    mark = _mark(artifact, scope, session, store)
    return {
        "run_id": run_id,
        "version_artifact_id": version.artifact_id,
        "artifact_type": artifact.artifact_type,
        "sha256": version.sha256,
        "line_id": version.line_id,
        "koncept": version.koncept,
        "edited_from": artifact.metadata.get("edited_from"),
        "authors": list(version.authors),
        "saved_at": version.saved_at.isoformat(),
        **_review_fields(artifact, mark),
        **_approval_fields(artifact, scope, session, store),
        "changes": changes_payload(changes) if changes is not None else None,
    }


@router.get(
    "/research/runs/{run_id}/report/editor/versions/{artifact_id}/download",
    response_class=Response,
    summary="Download a saved version of a run's report",
)
def download_report_editor_version(
    run_id: RunIdPath,
    artifact_id: ArtifactIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> Response:
    """Exactly that version's DOCX, with the run's report download's headers (its id, SHA-256
    and review), so the version a person approves is the one they downloaded. An edited version
    is not stamped: approved, its file keeps the draft footer, and its name says so
    (``schvaleno-v-aia``)."""
    try:
        scope.require(Permission.EXPORT_DELIVERABLE)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    version, artifact, _changes = _version(run_id, artifact_id, scope, session, store)
    exported = _export(artifact, scope, session, store)
    return Response(
        content=exported.data,
        media_type=INTERNAL_REPORT_MEDIA_TYPE,
        headers=_review_headers(
            exported.mark,
            _report_filename(
                scope.study_id,
                run_id,
                _file_variant(version),
                exported.mark,
                "docx",
                stamped=exported.stamped,
            ),
        ),
    )
