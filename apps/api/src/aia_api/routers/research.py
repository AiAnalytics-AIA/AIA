"""Research execution under the Study: Design Revisions, and the runs that execute them.

ADR 0016. Every route resolves the Study through ``ScopeResolver`` first
(``StudyScopeDep``): a Study outside the caller's scope is a 404, and so is a
revision or run that is not the Study's own. Inside a Study the caller can see,
a missing permission is a 403. No route takes a client, organization or unit
project id: the browser supplies content, never authority.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from aia_core.domain.design import DesignRejected, DesignRevision
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.study_design_repository import (
    DesignRevisionNotFound,
    StudyDesignRepository,
)
from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import SessionDep, StudyScopeDep
from ..schemas.projects import ErrorResponse

router = APIRouter(
    prefix="/studies/{study_id}",
    tags=["research"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Insufficient role, or the study is closed"},
        404: {"model": ErrorResponse, "description": "Not found, or not accessible"},
    },
)

RevisionIdPath = Annotated[str, Path(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")]


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class DesignSubmission(BaseModel):
    """The design the browser holds. Content only: identity comes from the Study."""

    model_config = ConfigDict(extra="forbid")

    content: dict[str, Any]
    source_stage: str = Field(max_length=32)


class DesignRevisionResponse(BaseModel):
    """One immutable Design Revision of the Study."""

    model_config = ConfigDict(extra="forbid")

    revision_id: str
    study_id: str
    revision: int
    content_sha256: str
    parent_revision: int | None
    source_stage: str
    created_by: str | None
    created_at: datetime
    created: bool | None = None
    content: dict[str, Any] | None = None


class DesignRevisionList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DesignRevisionResponse]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _not_found(what: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": f"{what}_not_found", "message": "No such resource."},
    )


def _refused(exc: ScopeDenied) -> HTTPException:
    """A permission or lifecycle refusal inside a Study the caller can see: 403."""
    code = "study_closed" if exc.reason == "study_closed" else "insufficient_role"
    message = (
        "The study no longer accepts changes."
        if code == "study_closed"
        else "Your role on this study does not permit that."
    )
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": code, "message": message, "details": {"reason": exc.reason}},
    )


def _revision(
    r: DesignRevision, *, created: bool | None = None, content: dict[str, Any] | None = None
) -> DesignRevisionResponse:
    return DesignRevisionResponse(
        revision_id=r.revision_id,
        study_id=r.study_id,
        revision=r.revision,
        content_sha256=r.content_sha256,
        parent_revision=r.parent_revision,
        source_stage=r.source_stage,
        created_by=r.created_by,
        created_at=r.created_at,
        created=created,
        content=content,
    )


# --------------------------------------------------------------------------- #
# Design Revisions
# --------------------------------------------------------------------------- #


@router.post(
    "/design/revisions",
    response_model=DesignRevisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit the research design as a new Design Revision",
    responses={200: {"description": "Identical to the newest revision: nothing new"}},
)
def submit_design(
    body: DesignSubmission, scope: StudyScopeDep, session: SessionDep, response: Response
) -> DesignRevisionResponse:
    """Store the design as an immutable, Study-scoped revision (ADR 0016 decision 1).

    Needs ``EDIT_STUDY`` on an open research Study. Content identical to the
    newest revision answers 200 with that revision; anything else is a new one.
    """
    try:
        revision, created = StudyDesignRepository(session, scope).submit(
            content=body.content, source_stage=body.source_stage
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except DesignRejected as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.reason, "message": str(exc)},
        ) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return _revision(revision, created=created)


@router.get(
    "/design/revisions",
    response_model=DesignRevisionList,
    summary="The Study's Design Revisions, newest first",
)
def list_designs(
    scope: StudyScopeDep, session: SessionDep, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> DesignRevisionList:
    items = StudyDesignRepository(session, scope).revisions(limit=limit)
    return DesignRevisionList(items=[_revision(r) for r in items])


@router.get(
    "/design/revisions/{revision_id}",
    response_model=DesignRevisionResponse,
    summary="One Design Revision, with its content",
)
def get_design(
    revision_id: RevisionIdPath, scope: StudyScopeDep, session: SessionDep
) -> DesignRevisionResponse:
    """A revision of this Study only; another Study's revision id is a 404."""
    repo = StudyDesignRepository(session, scope)
    try:
        return _revision(repo.get(revision_id), content=repo.content(revision_id))
    except DesignRevisionNotFound as exc:
        raise _not_found("design_revision") from exc
