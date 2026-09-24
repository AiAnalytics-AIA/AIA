"""Clients, studies, membership and access grants.

Two distinct authorisation levels are in play here and the split is deliberate:

* **Administrative** routes take an ``OrganizationContext``. They manage clients,
  studies and grants. They never return research content.
* **Study** routes take a ``StudyContext``, which requires a grant.

Listing clients needs only organization membership, because a client list is
names and slugs -- administrative metadata, not research. Listing a client's
*studies* is restricted to the studies the caller actually holds a grant on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from aia_core.domain.scope import (
    OrganizationRole,
    Permission,
    ScopeDenied,
    ScopeRole,
    StudyStatus,
)
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import (
    OrganizationDep,
    PrincipalDep,
    ResolverDep,
    ScopeRepositoryDep,
    StudyScopeDep,
    require_permission,
)
from ..schemas.projects import ErrorResponse

router = APIRouter(
    tags=["scope"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Insufficient role"},
        404: {"model": ErrorResponse, "description": "Not found, or not accessible"},
    },
)


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class ClientCreateRequest(BaseModel):
    """Create a client."""

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(max_length=64, description="URL-safe identifier, lowercased.")
    name: str = Field(min_length=1, max_length=255)
    reference: str = Field(default="", max_length=128, description="Internal reference.")


class ClientResponse(BaseModel):
    """A client."""

    model_config = ConfigDict(extra="forbid")

    client_id: str
    slug: str
    name: str
    status: str
    reference: str = ""
    study_count: int = 0
    created_at: datetime | None = None


class StudyCreateRequest(BaseModel):
    """Create a study under a client."""

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(max_length=64)
    slug: str = Field(max_length=64)
    name: str = Field(min_length=1, max_length=255)
    budget_usd: float = Field(default=0.0, ge=0, le=1_000_000)


class StudyResponse(BaseModel):
    """A study.

    Budget figures are included only when the caller may view costs; otherwise
    they are omitted rather than zeroed, so a client cannot be told a study has
    no budget when it has one they may not see.
    """

    model_config = ConfigDict(extra="forbid")

    study_id: str
    client_id: str
    slug: str
    name: str
    kind: Literal["RESEARCH", "SIMULATION"] = "RESEARCH"
    status: str
    accepts_work: bool
    your_role: str | None = None
    budget_usd: float | None = None
    spent_usd: float | None = None
    remaining_usd: float | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    delivered_at: datetime | None = None


class StudyStatusRequest(BaseModel):
    """Change a study's lifecycle status."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["DRAFT", "ACTIVE", "IN_REVIEW", "DELIVERED", "ARCHIVED", "CANCELLED"]


class StudyBudgetRequest(BaseModel):
    """Set a study's budget ceiling."""

    model_config = ConfigDict(extra="forbid")

    budget_usd: float = Field(ge=0, le=1_000_000)


class GrantRequest(BaseModel):
    """Grant a user a role."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(max_length=64)
    role: Literal["VIEWER", "REVIEWER", "RESEARCHER", "LEAD"]


class MemberRequest(BaseModel):
    """Add a user to the organization."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=320)
    role: Literal["OWNER", "ADMIN", "MEMBER"] = "MEMBER"
    display_name: str = Field(default="", max_length=255)


class MemberResponse(BaseModel):
    """An organization member."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: str
    display_name: str
    is_active: bool
    organization_role: str


class AuditEntryResponse(BaseModel):
    """One access-audit entry."""

    model_config = ConfigDict(extra="forbid")

    event_id: int
    action: str
    client_id: str | None = None
    study_id: str | None = None
    subject_user_id: str | None = None
    actor_id: str | None = None
    role: str | None = None
    reason: str = ""
    created_at: datetime | None = None


def _forbidden(exc: ScopeDenied) -> HTTPException:
    """Render an insufficient-role denial as 403.

    Distinct from a scope denial, which is 404: here the caller demonstrably has
    access to the study, so acknowledging the resource leaks nothing. Telling
    them they lack the role is actionable and not a disclosure.
    """
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "insufficient_role",
            "message": "Your role on this study does not permit that action.",
            "details": {"reason": exc.reason},
        },
    )


def _study_response(study: Any, *, role: str | None, include_costs: bool) -> StudyResponse:
    """Map a study to its public representation."""
    return StudyResponse(
        study_id=study.study_id,
        client_id=study.client_id,
        slug=study.slug,
        name=study.name,
        kind=study.kind.value,
        status=study.status.value,
        accepts_work=study.status.accepts_work,
        your_role=role,
        budget_usd=study.budget_usd if include_costs else None,
        spent_usd=study.spent_usd if include_costs else None,
        remaining_usd=study.remaining_usd if include_costs else None,
        created_at=study.created_at,
        modified_at=study.modified_at,
        delivered_at=study.delivered_at,
    )


# --------------------------------------------------------------------------- #
# Clients
# --------------------------------------------------------------------------- #


@router.get("/clients", response_model=list[ClientResponse], summary="List clients")
def list_clients(
    admin: OrganizationDep,
    repo: ScopeRepositoryDep,
    include_archived: bool = False,
) -> list[ClientResponse]:
    """List clients in the organization.

    Names and slugs only. Reading a client's studies still requires a grant.
    """
    counts = repo.client_study_counts(admin)
    return [
        ClientResponse(
            client_id=c.client_id,
            slug=c.slug,
            name=c.name,
            status=c.status.value,
            reference=c.reference,
            study_count=counts.get(c.client_id, 0),
            created_at=c.created_at,
        )
        for c in repo.list_clients(admin, include_archived=include_archived)
    ]


@router.post(
    "/clients",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a client",
)
def create_client(
    body: ClientCreateRequest,
    admin: OrganizationDep,
    repo: ScopeRepositoryDep,
    response: Response,
) -> ClientResponse:
    """Create a client. Requires organization administration."""
    try:
        client = repo.create_client(admin, slug=body.slug, name=body.name, reference=body.reference)
    except ScopeDenied as exc:
        raise _forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_client", "message": str(exc)}
        ) from exc

    response.headers["Location"] = f"/api/v1/clients/{client.client_id}"
    return ClientResponse(
        client_id=client.client_id,
        slug=client.slug,
        name=client.name,
        status=client.status.value,
        reference=client.reference,
        created_at=client.created_at,
    )


@router.post(
    "/clients/{client_id}/grants",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Grant a user access to a client",
)
def grant_client_access(
    client_id: Annotated[str, Path(max_length=64, pattern=r"^CLI-[0-9a-f]{1,32}$")],
    body: GrantRequest,
    admin: OrganizationDep,
    resolver: ResolverDep,
) -> Response:
    """Grant a client-level role, applying to all that client's studies.

    An administrator granting themselves access is recorded under a distinct
    audit action, so break-glass access is visible afterwards.
    """
    try:
        resolver.grant_client_access(
            admin, client_id=client_id, user_id=body.user_id, role=ScopeRole(body.role)
        )
    except ScopeDenied as exc:
        if exc.reason == "insufficient_role":
            raise _forbidden(exc) from exc
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "No such client."}
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Studies
# --------------------------------------------------------------------------- #


@router.get("/studies", response_model=list[StudyResponse], summary="List studies")
def list_studies(
    principal: PrincipalDep,
    admin: OrganizationDep,
    repo: ScopeRepositoryDep,
    resolver: ResolverDep,
    client_id: Annotated[str | None, Query(max_length=64)] = None,
    include_archived: bool = False,
) -> list[StudyResponse]:
    """List the studies the caller may access.

    Built from the caller's grants rather than filtered from the table, so a
    forgotten predicate yields an empty list rather than another client's work.
    """
    accessible = resolver.accessible_studies(principal, client_id=client_id)
    studies = repo.list_studies(
        admin,
        study_ids=accessible,
        client_id=client_id,
        include_archived=include_archived,
    )
    return [_study_response(s, role=None, include_costs=False) for s in studies]


@router.post(
    "/studies",
    response_model=StudyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a study",
)
def create_study(
    body: StudyCreateRequest,
    admin: OrganizationDep,
    repo: ScopeRepositoryDep,
    response: Response,
) -> StudyResponse:
    """Create a study under a client. Requires organization administration."""
    try:
        study = repo.create_study(
            admin,
            client_id=body.client_id,
            slug=body.slug,
            name=body.name,
            budget_usd=body.budget_usd,
        )
    except ScopeDenied as exc:
        if exc.reason == "insufficient_role":
            raise _forbidden(exc) from exc
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "No such client."}
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_study", "message": str(exc)}
        ) from exc

    response.headers["Location"] = f"/api/v1/studies/{study.study_id}"
    return _study_response(study, role="LEAD", include_costs=True)


@router.get("/studies/{study_id}", response_model=StudyResponse, summary="Get a study")
def get_study(scope: StudyScopeDep, repo: ScopeRepositoryDep) -> StudyResponse:
    """Return the study in scope, with the caller's effective role."""
    study = repo.get_study(scope)
    return _study_response(
        study,
        role=scope.role.value,
        include_costs=scope.has(Permission.VIEW_COSTS),
    )


@router.put(
    "/studies/{study_id}/status",
    response_model=StudyResponse,
    summary="Change a study's status",
)
def set_study_status(
    body: StudyStatusRequest,
    scope: StudyScopeDep,
    repo: ScopeRepositoryDep,
) -> StudyResponse:
    """Change the lifecycle status.

    Marking a study DELIVERED requires sign-off authority, because delivery is
    the point at which work becomes client-visible and is frozen.
    """
    try:
        study = repo.set_study_status(scope, StudyStatus(body.status))
    except ScopeDenied as exc:
        raise _forbidden(exc) from exc
    return _study_response(
        study, role=scope.role.value, include_costs=scope.has(Permission.VIEW_COSTS)
    )


@router.put(
    "/studies/{study_id}/budget",
    response_model=StudyResponse,
    summary="Set a study's budget",
)
def set_study_budget(
    body: StudyBudgetRequest,
    scope: Annotated[Any, Depends(require_permission(Permission.MANAGE_STUDY_BUDGET))],
    repo: ScopeRepositoryDep,
) -> StudyResponse:
    """Set the budget ceiling enforced before every paid provider call."""
    try:
        study = repo.set_study_budget(scope, body.budget_usd)
    except ScopeDenied as exc:
        raise _forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_budget", "message": str(exc)}
        ) from exc
    return _study_response(study, role=scope.role.value, include_costs=True)


@router.post(
    "/studies/{study_id}/grants",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Grant a user access to a study",
)
def grant_study_access(
    body: GrantRequest,
    scope: Annotated[Any, Depends(require_permission(Permission.MANAGE_STUDY_ACCESS))],
    resolver: ResolverDep,
) -> Response:
    """Grant a study-level role.

    A study grant is authoritative over a client grant in both directions: it can
    bring someone in for a single study, or restrict a client lead on a sensitive
    one.
    """
    try:
        resolver.grant_study_access(scope, user_id=body.user_id, role=ScopeRole(body.role))
    except ScopeDenied as exc:
        raise _forbidden(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Members and audit
# --------------------------------------------------------------------------- #


@router.get("/members", response_model=list[MemberResponse], summary="List members")
def list_members(admin: OrganizationDep, repo: ScopeRepositoryDep) -> list[MemberResponse]:
    """List organization members and their administrative roles."""
    return [MemberResponse(**m) for m in repo.members(admin)]


@router.post(
    "/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member",
)
def add_member(
    body: MemberRequest, admin: OrganizationDep, repo: ScopeRepositoryDep
) -> MemberResponse:
    """Add a user to the organization.

    Membership alone grants no access to client data; a grant is still required.
    """
    try:
        repo.add_member(
            admin,
            email=body.email,
            role=OrganizationRole(body.role),
            display_name=body.display_name,
        )
    except ScopeDenied as exc:
        raise _forbidden(exc) from exc

    for member in repo.members(admin):
        if member["email"] == body.email.strip().lower():
            return MemberResponse(**member)
    raise HTTPException(  # pragma: no cover - the member was just written
        status_code=500, detail={"code": "internal_error", "message": "Member not found."}
    )


@router.get(
    "/access-audit",
    response_model=list[AuditEntryResponse],
    summary="Access audit trail",
)
def access_audit(
    admin: OrganizationDep,
    resolver: ResolverDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[AuditEntryResponse]:
    """Return recent grants, revocations and denials.

    Security-relevant: an administrator granting themselves access to a client is
    legitimate but must be reviewable afterwards.
    """
    try:
        return [AuditEntryResponse(**e) for e in resolver.audit_trail(admin, limit=limit)]
    except ScopeDenied as exc:
        raise _forbidden(exc) from exc
