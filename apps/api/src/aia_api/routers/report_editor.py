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
    TooManyPages,
    session_by_key,
)
from aia_core.application.report_editor_saves import (
    SaveNotStored,
    VersionNotFound,
    content_held,
    edited_version,
    edits_verdict,
    store_save,
    version_changes,
)
from aia_core.application.report_export import ReviewUnrecorded
from aia_core.application.report_variants import request_pdf, variant_pdf
from aia_core.application.research import research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal
from aia_core.domain.report.editor import CallbackAction, SeenEdit, UnsavedEdits, callback_action
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
    _base_pdf,
    _export,
    _mark,
    _not_found,
    _refused,
    _report_filename,
    _report_for_run,
    _review_fields,
    _review_headers,
    _unrecorded,
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


class EditReport(BaseModel):
    """An edit start a page reports (RPT8f): the page's id and its count from 1."""

    model_config = ConfigDict(extra="forbid")

    page: str = Field(pattern=r"^[0-9A-Za-z_-]{8,64}$")
    seq: int = Field(ge=1, le=2_000_000_000)


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
            # The doc bar is the only way out of the editor (Z5): its downloads name the stored
            # version, its approval and its fonts; the editor's own would name none of them.
            "permissions": {"edit": edit, "download": False, "print": False, "comment": edit},
        },
        "editorConfig": {
            "callbackUrl": f"{base}/callback?token={callback}",
            "lang": "cs",
            "region": "cs-CZ",
            "mode": mode,
            "user": {"id": scope.actor_id, "name": name or "Člen týmu"},
            # The board's editor (Z5, T5). modifyContentControl is left at the server's default:
            # unlocking a control stays allowed (amended ADR 0035).
            "customization": {
                "uiTheme": "theme-aia",
                "compactHeader": True,
                "compactToolbar": True,
                "toolbarHideFileName": True,
                "unit": "cm",
                "zoom": 90,
                "plugins": False,
                "chat": False,
                "help": False,
                "forcesave": True,
            },
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
        # What the page's api.js must hash to (RPT8e); it loads nothing that does not.
        "api_integrity": settings.onlyoffice_api_integrity,
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


@router.post(
    "/research/runs/{run_id}/report/editor/sessions/{document_key}/edits",
    status_code=204,
    response_class=Response,
    summary="An edit start the page reports in an editing session",
    responses={409: {"model": ErrorResponse}},
)
def report_editor_edit(
    run_id: RunIdPath,
    body: EditReport,
    scope: StudyScopeDep,
    session: SessionDep,
    settings: SettingsDep,
    document_key: Annotated[str, Path(pattern=r"^[0-9A-Za-z._=-]{1,128}$")],
) -> Response:
    """The caller's page started edit ``seq`` in the open session ``document_key``: kept with
    AIA's time of receipt, so an approval is refused while no stored version holds it (409
    ``report_edits_unsaved``). 404 for a session that is not the run's, not open, or not one a
    config was signed for the caller in; 409 ``editor_pages_exhausted`` for a new page beyond the
    session's pages."""
    _tokens(settings)
    try:
        ReportEditor(session, scope).record_edit(
            document_key,
            run_id=run_id,
            page=body.page,
            seq=body.seq,
            now=_now(),
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except LineNotFound as exc:
        raise _not_found("editor_session") from exc
    except TooManyPages as exc:
        raise HTTPException(
            409,
            detail={
                "code": "editor_pages_exhausted",
                "message": "This editing session keeps edit reports for no more pages.",
            },
        ) from exc
    session.commit()
    return Response(status_code=204)


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
                content_at=_held_through(_lastsave(payload.get("lastsave")), now),
            )
        except SaveNotStored as refused:
            session.commit()  # the problem is kept for the pane
            log.warning("report editor save not stored", extra={"reason": refused.reason})
            return {"error": 1}
        if action is CallbackAction.STORE_AND_CLOSE:
            editor.close(found, now=now, reason="saved")
    session.commit()
    return {"error": 0}


def _lastsave(value: Any) -> datetime | None:
    """ONLYOFFICE's ``lastsave`` (signed, with the rest of the callback): the time of the last
    change the saved file holds; ``None`` for anything that is not an aware ISO time."""
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _edits(reason: UnsavedEdits | None) -> dict[str, Any]:
    return {"edits": {"saved": reason is None, "reason": reason.value if reason else None}}


def _held_through(lastsave: datetime | None, now: datetime) -> datetime | None:
    """``lastsave`` no later than ``now``, AIA's receipt of the callback that says it (RPT8f): a
    change cannot be later than the save that reports it, so a Document Server clock running ahead
    can only make an edit look later, never held early. Logged when it is ahead."""
    if lastsave is not None and lastsave > now:
        log.warning(
            "report editor lastsave is ahead of AIA's clock",
            extra={"ahead_ms": int((lastsave - now).total_seconds() * 1000)},
        )
        return now
    return lastsave


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


def _edited(
    run_id: str, artifact_id: str, scope: StudyContext, session: Any, store: Any
) -> tuple[Any, Any]:
    """The version and its artifact, reading nothing else (its DOCX is read by the caller)."""
    try:
        return edited_version(session, scope, store, run_id=run_id, artifact_id=artifact_id)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except VersionNotFound as exc:
        raise _not_found("editor_version") from exc


def _version_pdf(
    version: Any, artifact: Any, run_id: str, scope: StudyContext, session: Any, store: Any
) -> tuple[Any, dict[str, Any]]:
    """The version's PDF, ready or not, and its state. Koncept 1 of the run's own internal
    line is the report its report step composed, so its PDF is that report's, the step's
    rendering included (``research._base_pdf``, as ``…/report`` reads it); any other version's
    is its own job's (``report_variants.variant_pdf``)."""
    try:
        if version.koncept == 1 and version.variant == "internal":
            step, report = _report_for_run(run_id, scope, session, store)
            if report is not None and report.artifact_id == artifact.artifact_id:
                mark = _mark(report, scope, session, store)
                pdf, said = _base_pdf(step, report, mark, run_id, scope, session, store)
                return pdf, said or {"state": "NOT_REQUESTED"}
        found = variant_pdf(
            session,
            scope,
            store,
            docx=artifact,
            run_id=run_id,
            deep_research_run_id=version.deep_research_run_id,
        )
    except ReviewUnrecorded as exc:
        raise _unrecorded(exc) from exc
    return found.artifact, found.to_json()


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
    seen_key: Annotated[str | None, Query(pattern=r"^[0-9A-Za-z._=-]{1,128}$")] = None,
    seen_page: Annotated[str | None, Query(pattern=r"^[0-9A-Za-z_-]{8,64}$")] = None,
    seen_seq: Annotated[int | None, Query(ge=1, le=2_000_000_000)] = None,
) -> dict[str, Any]:
    """A version of one of the run's report lines, for the doc bar and the approval dialog
    (RPT8d): who saved it (by display name) and from which version, its review and approval as
    the run's report status says them, its line's newest version, and what it changed in the
    numbers code wrote, as stored beside it (each control changed, removed or added, each number
    typed outside one). ``changes`` null for
    koncept 1, the composer's own; ``uncomparable`` when there was nothing to compare it with,
    never an empty list read as no change. Served whether or not the editor is on: an approved
    version stays readable. ``seen_*``: the asking page's last edit start, all three or none,
    which ``edits`` then counts (RPT8f)."""
    named = (seen_key, seen_page, seen_seq)
    if any(v is not None for v in named) and not all(v is not None for v in named):
        raise HTTPException(
            422, detail={"code": "invalid_request", "message": "seen_* come all three or none."}
        )
    seen = (
        SeenEdit(seen_key, seen_page, seen_seq)
        if seen_key is not None and seen_page is not None and seen_seq is not None
        else None
    )
    version, artifact, changes = _version(run_id, artifact_id, scope, session, store)
    mark = _mark(artifact, scope, session, store)
    editor = ReportEditor(session, scope)
    names = editor.names(version.authors)
    newest = editor.newest(version.line_id)
    return {
        "run_id": run_id,
        "version_artifact_id": version.artifact_id,
        "artifact_type": artifact.artifact_type,
        "sha256": version.sha256,
        "line_id": version.line_id,
        "koncept": version.koncept,
        "edited_from": artifact.metadata.get("edited_from"),
        "authors": list(version.authors),
        # Each author's display name, null for one with none (never an e-mail), in that order.
        "author_names": [names.get(a) for a in version.authors],
        "saved_at": version.saved_at.isoformat(),
        # The last change the file holds, as the Document Server said it (null when it did not,
        # and for koncept 1), and this server's time, so the pane can place an edit it saw
        # before or after it on one clock.
        # Moved on by a later save of the same bytes (RPT8f).
        "content_at": held.isoformat() if (held := content_held(version, artifact)) else None,
        "server_now": _now().isoformat(),
        # The server's own verdict (RPT8f): whether this version holds every edit its line's open
        # session reported and the asking page's, by the rule an approval is refused under, and
        # why not; the pane's hold follows it and guesses nothing.
        **_edits(edits_verdict(session, scope, version, artifact, seen)),
        # The line's newest version: approving this one while a later save exists approves what
        # the editor no longer shows, so the pane asks again (RPT8d).
        "newest_in_line": {"version_artifact_id": newest.artifact_id, "koncept": newest.koncept}
        if newest is not None
        else None,
        **_review_fields(artifact, mark),
        **_approval_fields(artifact, scope, session, store),
        "changes": changes_payload(changes) if changes is not None else None,
        # Its PDF, rendered from exactly this version (of its approved export once approved).
        "pdf": _version_pdf(version, artifact, run_id, scope, session, store)[1],
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
    and review), so the version a person approves is the one they downloaded. Approved, it says
    SCHVÁLENO in its footers where the editor kept the composer's footer layout (checked when it
    was saved); else it keeps the draft footer, and its name says so (``schvaleno-v-aia``)."""
    try:
        scope.require(Permission.EXPORT_DELIVERABLE)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    version, artifact = _edited(run_id, artifact_id, scope, session, store)
    # Only the DOCX is read: what it changed is the version route's, never the download's.
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


@router.post(
    "/research/runs/{run_id}/report/editor/versions/{artifact_id}/pdf",
    summary="Ask for the PDF of a saved version of a run's report",
)
def ask_report_editor_version_pdf(
    run_id: RunIdPath,
    artifact_id: ArtifactIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> dict[str, Any]:
    """A rendering of exactly this version (of its approved export once approved), by the one
    rule every report PDF is asked by (``report_variants.request_pdf``): one ready or under way
    is left as it is; one never asked for, failed or invalid is asked again. Answers the PDF's
    state."""
    version, artifact = _edited(run_id, artifact_id, scope, session, store)
    ready, _said = _version_pdf(version, artifact, run_id, scope, session, store)
    if ready is None:  # a rendering already made, the report step's too, is never made again
        try:
            request_pdf(
                session,
                scope,
                store,
                docx=artifact,
                run_id=run_id,
                deep_research_run_id=version.deep_research_run_id,
            )
        except ScopeDenied as exc:
            raise _refused(exc) from exc
        except ReviewUnrecorded as exc:
            raise _unrecorded(exc) from exc
        session.commit()
    return {
        "run_id": run_id,
        "version_artifact_id": version.artifact_id,
        "pdf": _version_pdf(version, artifact, run_id, scope, session, store)[1],
    }


@router.get(
    "/research/runs/{run_id}/report/editor/versions/{artifact_id}/pdf/download",
    response_class=Response,
    summary="Download the PDF of a saved version of a run's report",
)
def download_report_editor_version_pdf(
    run_id: RunIdPath,
    artifact_id: ArtifactIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> Response:
    """The PDF rendered from exactly this version, with the same review headers as its DOCX;
    404 ``report_pdf_not_found`` until one is ready."""
    try:
        scope.require(Permission.EXPORT_DELIVERABLE)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    version, artifact = _edited(run_id, artifact_id, scope, session, store)
    pdf, _said = _version_pdf(version, artifact, run_id, scope, session, store)
    if pdf is None:
        raise _not_found("report_pdf")
    mark = _mark(artifact, scope, session, store)
    try:
        data = research_artifacts(session, scope, store).read(pdf.artifact_id)
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    return Response(
        content=data,
        media_type=pdf.content_type,  # application/pdf, as the rendering stored it
        headers=_review_headers(
            mark,
            _report_filename(
                scope.study_id,
                run_id,
                _file_variant(version),
                mark,
                "pdf",
                stamped=pdf.metadata.get("stamped") is True,
            ),
        ),
    )
