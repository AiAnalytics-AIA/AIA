"""A client's sources: material a person adds, kept as it came (lifecycle K2a).

``POST /clients/{client_id}/sources`` -- keep a file for the client. The same bytes
added again are the same source with another occurrence (200 instead of 201). What
reading it produced comes back at once: ``READ``, ``PARTIAL``, ``UNREADABLE``,
``UNSUPPORTED`` or ``REFUSED``, each with its reason.

``GET /clients/{client_id}/sources`` -- the client's sources, the most recently added
first. ``GET …/{source_id}`` -- one source with its reading, every segment with where it
stands in the original, and a dataset's columns. ``GET …/{source_id}/original`` -- the
bytes, as ``application/octet-stream``, never rendered in AIA's origin.
``POST …/{source_id}/reading`` -- read a source again with its format's current reader,
when a newer one has come (OI-110).

``POST …/{source_id}/proposals`` -- ask AI for knowledge proposals from a document, as the
client's own work paid by its budget, one run per reading (lifecycle K2d4); ``GET`` the
newest such run and why it waits or stopped.

A source is not knowledge: adding one accepts nothing, and no study reads it. Found only
within its client; another client's source is a 404.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Annotated, Any
from urllib.parse import quote

from aia_core.application.source_proposals import (
    ProposalsRun,
    latest_source_proposals,
    start_source_proposals,
)
from aia_core.domain.client_sources import (
    SOURCE_MAX_BYTES,
    SourceReading,
    SourceRecord,
    SourceRejected,
)
from aia_core.domain.scope import ClientContext, ClientWorkContext, ScopeDenied
from aia_core.domain.source_proposals import NotExtractable
from aia_core.infrastructure.client_source_repository import ClientSourceRepository
from aia_core.infrastructure.storage import IntegrityError, ObjectNotFound
from fastapi import APIRouter, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import ArtifactStoreDep, PrincipalDep, ResolverDep, SessionDep
from ..schemas.projects import ErrorResponse

router = APIRouter(
    prefix="/clients/{client_id}/sources",
    tags=["client sources"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Insufficient role"},
        404: {"model": ErrorResponse, "description": "Not found, or not accessible"},
    },
)

ClientIdPath = Annotated[str, Path(max_length=64, pattern=r"^CLI-[0-9a-f]{1,32}$")]
SourceIdPath = Annotated[str, Path(max_length=64, pattern=r"^SRC-[0-9a-f]{16}$")]
# The base64 of the largest source the domain keeps; a longer body is refused before it
# is decoded.
_B64_MAX = -(-SOURCE_MAX_BYTES // 3) * 4


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceUpload(_Model):
    filename: str = Field(min_length=1, max_length=400)
    data_b64: str = Field(min_length=1, max_length=_B64_MAX)


class OccurrenceResponse(_Model):
    occurrence_id: str
    filename: str
    origin: str
    added_by: str | None
    added_at: datetime | None


class SourceResponse(_Model):
    """A source as listed: what it is and what reading it produced."""

    source_id: str
    sha256: str
    size_bytes: int
    media_type: str
    family: str
    filename: str
    outcome: str
    reason: str | None
    reader: str | None
    characters: int
    segments: int
    occurrences: list[OccurrenceResponse]
    created_at: datetime | None


class SourceAddedResponse(SourceResponse):
    #: False when the same bytes were already the client's: another occurrence.
    created: bool


class LocatorResponse(_Model):
    page: int | None = None
    paragraph: int | None = None
    slide: int | None = None
    table: int | None = None
    sheet: str | None = None
    row: int | None = None
    line: int | None = None


class SegmentResponse(_Model):
    locator: LocatorResponse
    text: str


class NoteResponse(_Model):
    code: str
    at: LocatorResponse | None = None
    count: int | None = None


class ColumnResponse(_Model):
    index: int
    letter: str
    header: str | None
    kind: str
    filled: int
    distinct: int
    distinct_capped: bool
    #: Why the column is treated as personal data; its samples are then masked.
    personal: str | None
    sample: list[str]


class SheetResponse(_Model):
    name: str | None
    header_row: int | None
    rows: int
    columns: list[ColumnResponse]
    truncated: bool


class DatasetResponse(_Model):
    sheets: list[SheetResponse]
    more_sheets: bool


class ReadingResponse(_Model):
    outcome: str
    reader: str | None
    reason: str | None
    segments: list[SegmentResponse]
    notes: list[NoteResponse]
    #: A dataset's columns as read (a CSV, XLSX, XLS or ODS); null for anything else.
    dataset: DatasetResponse | None = None


class SourceDetailResponse(SourceResponse):
    reading: ReadingResponse


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": "No such resource."},
    )


def _scope(principal: Any, resolver: Any, client_id: str) -> ClientContext:
    try:
        scope: ClientContext = resolver.client_context(principal, client_id=client_id)
    except ScopeDenied as exc:
        raise _not_found() from exc
    return scope


def _denied(exc: ScopeDenied) -> HTTPException:
    if exc.reason in ("unknown_source", "forged_scope"):
        return _not_found()
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "insufficient_role",
            "message": "Your role on this client does not permit that.",
            "details": {"reason": exc.reason},
        },
    )


def _corrupt() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "source_corrupt",
            "message": "The stored bytes are missing or no longer match their hash.",
        },
    )


def _source(record: SourceRecord) -> dict[str, Any]:
    return {
        **record.model_dump(mode="json", exclude={"client_id", "occurrences", "family", "outcome"}),
        "family": record.family.value,
        "outcome": record.outcome.value,
        "occurrences": [
            OccurrenceResponse(
                occurrence_id=o.occurrence_id,
                filename=o.filename,
                origin=o.origin.value,
                added_by=o.added_by,
                added_at=o.added_at,
            )
            for o in record.occurrences
        ],
    }


def _reading(reading: SourceReading) -> ReadingResponse:
    return ReadingResponse.model_validate(reading.model_dump(mode="json"))


@router.post(
    "",
    response_model=SourceAddedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Keep a file as the client's source",
    responses={
        200: {"model": SourceAddedResponse, "description": "The same bytes were already kept"},
        422: {
            "model": ErrorResponse,
            "description": "Empty, too large, not base64, or a format AIA does not take",
        },
    },
)
def add_source(
    client_id: ClientIdPath,
    body: SourceUpload,
    response: Response,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> SourceAddedResponse:
    """Needs ``PROPOSE_CLIENT_KNOWLEDGE``. Adding a source accepts nothing."""
    scope = _scope(principal, resolver, client_id)
    try:
        data = base64.b64decode(body.data_b64, validate=True)
    except binascii.Error as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "not_base64", "message": "The file is not valid base64."},
        ) from exc
    try:
        record, created = ClientSourceRepository(session, store).add(
            scope, filename=body.filename, data=data
        )
    except ScopeDenied as exc:
        raise _denied(exc) from exc
    except SourceRejected as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return SourceAddedResponse(**_source(record), created=created)


@router.get("", response_model=list[SourceResponse], summary="The client's sources")
def list_sources(
    client_id: ClientIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> list[SourceResponse]:
    """Needs ``VIEW_CLIENT_KNOWLEDGE``. The most recently added first."""
    scope = _scope(principal, resolver, client_id)
    try:
        records = ClientSourceRepository(session, store).sources(scope)
    except ScopeDenied as exc:
        raise _denied(exc) from exc
    return [SourceResponse(**_source(r)) for r in records]


@router.get(
    "/{source_id}",
    response_model=SourceDetailResponse,
    summary="One source and what reading it produced",
    responses={409: {"model": ErrorResponse, "description": "The stored reading is altered"}},
)
def get_source(
    client_id: ClientIdPath,
    source_id: SourceIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> SourceDetailResponse:
    scope = _scope(principal, resolver, client_id)
    repo = ClientSourceRepository(session, store)
    try:
        record = repo.source(scope, source_id)
        reading = repo.reading(scope, source_id)
    except ScopeDenied as exc:
        raise _denied(exc) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise _corrupt() from exc
    return SourceDetailResponse(**_source(record), reading=_reading(reading))


@router.get(
    "/{source_id}/original",
    response_class=Response,
    summary="Download a source's original",
    responses={
        200: {"content": {"application/octet-stream": {}}, "description": "The file"},
        409: {"model": ErrorResponse, "description": "The stored bytes are missing or altered"},
    },
)
def download_source(
    client_id: ClientIdPath,
    source_id: SourceIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> Response:
    """Always ``application/octet-stream`` and ``attachment``, whatever the file claims."""
    scope = _scope(principal, resolver, client_id)
    try:
        filename, data = ClientSourceRepository(session, store).original(scope, source_id)
    except ScopeDenied as exc:
        raise _denied(exc) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise _corrupt() from exc
    # A header is Latin-1: an ASCII fallback, and the name as written (RFC 6266 / 5987).
    fallback = filename.encode("ascii", "replace").decode().replace("?", "_").replace('"', "_")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post(
    "/{source_id}/reading",
    response_model=SourceDetailResponse,
    summary="Read a source again with its format's current reader",
    responses={409: {"model": ErrorResponse, "description": "The stored bytes are altered"}},
)
def reread_source(
    client_id: ClientIdPath,
    source_id: SourceIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> SourceDetailResponse:
    """Needs ``PROPOSE_CLIENT_KNOWLEDGE``. The original never changes; a source already
    read by its format's current reader is answered as it is (OI-110)."""
    scope = _scope(principal, resolver, client_id)
    repo = ClientSourceRepository(session, store)
    try:
        repo.reread(scope, source_id)
        record = repo.source(scope, source_id)
        reading = repo.reading(scope, source_id)
    except ScopeDenied as exc:
        raise _denied(exc) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise _corrupt() from exc
    return SourceDetailResponse(**_source(record), reading=_reading(reading))


# ---------------------------------------------------------------- AI proposals (K2d4)


class ProposalsRunResponse(_Model):
    """A run asking a model for knowledge proposals from one source, paid by the client."""

    run_id: str
    source_id: str
    reading_sha256: str
    #: The run's state: ``PENDING``, ``RUNNING``, ``COMPLETED``, ``FAILED`` …
    status: str
    #: Its step's: ``QUEUED``, ``RUNNING``, ``AWAITING_BUDGET``, ``SUCCEEDED`` …
    step_status: str
    #: Why the step stopped or waits, by name (``client_source_proposals_unconfigured``,
    #: ``egress_route_not_approved_for_class``, ``reading_changed`` …); null when it has not.
    reason: str | None
    #: Whether the reading this run pinned is still the source's.
    current: bool
    created_at: datetime | None
    finished_at: datetime | None
    #: When it succeeded: ``batches``, ``proposed`` and ``dropped`` by reason.
    output: dict[str, Any]
    #: False when a run for this reading already existed and was returned.
    created: bool
    #: Whether asking again starts a new run: this one ended without a result and left no
    #: paid call of unknown outcome (what it answered is replayed, not paid again).
    restartable: bool


def _proposals_run(run: ProposalsRun) -> ProposalsRunResponse:
    return ProposalsRunResponse(
        run_id=run.run_id,
        source_id=run.source_id,
        reading_sha256=run.reading_sha256,
        status=run.status.value,
        step_status=run.step_status,
        reason=run.reason,
        current=run.current,
        created_at=run.created_at,
        finished_at=run.finished_at,
        output=run.output,
        created=run.created,
        restartable=run.restartable,
    )


def _work_scope(principal: Any, resolver: Any, client_id: str) -> ClientWorkContext:
    try:
        work: ClientWorkContext = resolver.client_work_context(principal, client_id=client_id)
    except ScopeDenied as exc:
        raise _denied(exc) from exc
    return work


@router.post(
    "/{source_id}/proposals",
    response_model=ProposalsRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ask AI for knowledge proposals from a document, paid by the client",
    responses={
        200: {"model": ProposalsRunResponse, "description": "A run for this reading exists"},
        409: {"model": ErrorResponse, "description": "The stored reading is altered"},
        422: {
            "model": ErrorResponse,
            "description": "A dataset, a file without text, or a document nothing was read from",
        },
    },
)
def start_proposals(
    client_id: ClientIdPath,
    source_id: SourceIdPath,
    response: Response,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> ProposalsRunResponse:
    """Needs ``PROPOSE_CLIENT_KNOWLEDGE`` and ``RUN_CLIENT_WORK``. Queues one run per
    reading of the source; asking again returns it (200) unless it failed or was
    cancelled. What the model proposes is filed as proposals a person decides on."""
    scope = _scope(principal, resolver, client_id)
    work = _work_scope(principal, resolver, client_id)
    try:
        run = start_source_proposals(session, scope, work, store, source_id)
    except ScopeDenied as exc:
        raise _denied(exc) from exc
    except NotExtractable as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": exc.reason,
                "message": "AIA navrhuje znalosti zatím jen z přečteného dokumentu.",
            },
        ) from exc
    if not run.created:
        response.status_code = status.HTTP_200_OK
    return _proposals_run(run)


@router.get(
    "/{source_id}/proposals",
    response_model=ProposalsRunResponse | None,
    summary="The newest proposals run about a source; null when nobody has asked",
)
def get_proposals(
    client_id: ClientIdPath,
    source_id: SourceIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> ProposalsRunResponse | None:
    """Needs ``VIEW_CLIENT_KNOWLEDGE`` and ``RUN_CLIENT_WORK``."""
    scope = _scope(principal, resolver, client_id)
    work = _work_scope(principal, resolver, client_id)
    try:
        run = latest_source_proposals(session, scope, work, store, source_id)
    except ScopeDenied as exc:
        raise _denied(exc) from exc
    return None if run is None else _proposals_run(run)
