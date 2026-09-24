"""The client workspace: clients, their studies, the unit bridge and client knowledge.

ADR 0015. Everything here resolves scope first -- a ``ClientContext`` for the
client's own surfaces, a ``StudyContext`` for one study -- and every denial of
scope is a 404, as elsewhere. Inside a client the caller demonstrably has, a
missing permission is a 403: acknowledging the client leaks nothing.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

from aia_core.domain.knowledge import (
    KNOWLEDGE_SECTIONS,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeProposal,
    ProposalStatus,
)
from aia_core.domain.scope import (
    ClientContext,
    ClientPermission,
    Permission,
    ScopeDenied,
    ScopeRole,
    SeparationOfDutiesViolation,
    Study,
    StudyKind,
    StudyStatus,
)
from aia_core.domain.workspace import StudyWorkspace
from aia_core.infrastructure.artifact_repository import ArtifactRepository
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.study_workspace_repository import (
    StudyWorkspaceRepository,
    WorkspaceConflict,
)
from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import (
    ArtifactStoreDep,
    OrganizationDep,
    PrincipalDep,
    ResolverDep,
    ScopeRepositoryDep,
    SessionDep,
    StudyScopeDep,
)
from ..schemas.projects import ErrorResponse

router = APIRouter(
    tags=["workspace"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Insufficient role"},
        404: {"model": ErrorResponse, "description": "Not found, or not accessible"},
    },
)

ClientIdPath = Annotated[str, Path(max_length=64, pattern=r"^CLI-[0-9a-f]{1,32}$")]
OPEN_STATUSES = (StudyStatus.DRAFT, StudyStatus.ACTIVE, StudyStatus.IN_REVIEW)


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class WorkspaceStudy(BaseModel):
    """A research or a simulation, as the client workspace lists it."""

    model_config = ConfigDict(extra="forbid")

    study_id: str
    client_id: str
    name: str
    slug: str
    kind: Literal["RESEARCH", "SIMULATION"]
    status: str
    accepts_work: bool
    last_stage: str | None = None
    has_working_content: bool = False
    created_at: datetime | None = None
    modified_at: datetime | None = None


class ClientCard(BaseModel):
    """One client in the directory."""

    model_config = ConfigDict(extra="forbid")

    client_id: str
    name: str
    slug: str
    your_role: str | None
    active_count: int
    study_count: int
    recent: list[WorkspaceStudy]
    modified_at: datetime | None = None


class ClientWorkspace(BaseModel):
    """The client a workspace is about, and what the caller may do in it."""

    model_config = ConfigDict(extra="forbid")

    client_id: str
    name: str
    slug: str
    status: str
    your_role: str | None
    permissions: list[str]


class OutputItem(BaseModel):
    """A recent output of one of the client's studies."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    artifact_type: str
    stage_type: str
    status: str
    study_id: str
    study_name: str
    created_at: datetime | None = None


class KnowledgeItemResponse(BaseModel):
    """An approved piece of client knowledge."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    kind: str
    title: str
    summary: str
    content: dict[str, Any]
    revision: int
    modified_at: datetime | None = None


class KnowledgeRevisionResponse(BaseModel):
    """One approved revision of an item."""

    model_config = ConfigDict(extra="forbid")

    revision: int
    context_revision: int
    title: str
    summary: str
    provenance: dict[str, Any]
    approved_by: str
    approved_at: datetime | None = None


class ProposalResponse(BaseModel):
    """A proposed knowledge update."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    origin: str
    study_id: str | None
    study_name: str | None = None
    item_id: str | None
    kind: str
    title: str
    summary: str
    status: str
    proposed_by: str
    proposed_at: datetime | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_note: str = ""
    revision: int | None = None
    yours: bool = False


class KnowledgeSummaryResponse(BaseModel):
    """The state of the client's knowledge."""

    model_config = ConfigDict(extra="forbid")

    context_revision: int
    items_by_kind: dict[str, int]
    pending_proposals: int
    last_approved_at: datetime | None = None


class ClientOverview(BaseModel):
    """Přehled: what the researcher needs to continue their work for this client."""

    model_config = ConfigDict(extra="forbid")

    client: ClientWorkspace
    active: list[WorkspaceStudy]
    previous_count: int
    recent_outputs: list[OutputItem]
    knowledge: KnowledgeSummaryResponse | None
    pending: list[ProposalResponse]


class StudyCreate(BaseModel):
    """Start a research or a simulation for the client."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    kind: Literal["RESEARCH", "SIMULATION"]


class StudyWorkspaceResponse(BaseModel):
    """One study as its frame needs it: the study, its client, and the bridge."""

    model_config = ConfigDict(extra="forbid")

    study: WorkspaceStudy
    client_name: str
    your_role: str
    can_edit: bool
    unit_project_id: str | None


class BindRequest(BaseModel):
    """Bind the study to the unit project holding its working content (OI-58)."""

    model_config = ConfigDict(extra="forbid")

    unit_project_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_-]{1,160}$")


class StageRequest(BaseModel):
    """The stage the study was opened on."""

    model_config = ConfigDict(extra="forbid")

    stage: str = Field(max_length=32)


class ProposalCreate(BaseModel):
    """Propose an addition to, or a revision of, the client's knowledge."""

    model_config = ConfigDict(extra="forbid")

    kind: KnowledgeKind
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(default="", max_length=10_000)
    content: dict[str, Any] = Field(default_factory=dict)
    item_id: str | None = Field(default=None, max_length=64)


class DecisionRequest(BaseModel):
    """Approve or reject a proposal."""

    model_config = ConfigDict(extra="forbid")

    approve: bool
    note: str = Field(default="", max_length=2_000)


class StudyContextResponse(BaseModel):
    """What a study consumes, by layer (ADR 0015 decision 7)."""

    model_config = ConfigDict(extra="forbid")

    client_id: str
    shared: dict[str, Any]
    client: list[KnowledgeItemResponse]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": "No such resource."},
    )


def _forbidden(reason: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "insufficient_role", "message": message, "details": {"reason": reason}},
    )


def _client_scope(principal: Any, resolver: Any, client_id: str) -> ClientContext:
    try:
        scope: ClientContext = resolver.client_context(principal, client_id=client_id)
    except ScopeDenied as exc:
        raise _not_found() from exc
    return scope


def _study(study: Study, workspace: StudyWorkspace | None) -> WorkspaceStudy:
    return WorkspaceStudy(
        study_id=study.study_id,
        client_id=study.client_id,
        name=study.name,
        slug=study.slug,
        kind=study.kind.value,
        status=study.status.value,
        accepts_work=study.status.accepts_work,
        last_stage=workspace.last_stage if workspace else None,
        has_working_content=workspace is not None,
        created_at=study.created_at,
        modified_at=study.modified_at,
    )


def _workspace(scope: ClientContext, repo: Any) -> ClientWorkspace:
    client = repo.get_client_in_scope(scope)
    return ClientWorkspace(
        client_id=client.client_id,
        name=client.name,
        slug=client.slug,
        status=client.status.value,
        your_role=scope.client_role.value if scope.client_role else None,
        permissions=sorted(p.value for p in scope.permissions),
    )


def _item(i: KnowledgeItem) -> KnowledgeItemResponse:
    return KnowledgeItemResponse(
        item_id=i.item_id,
        kind=i.kind.value,
        title=i.title,
        summary=i.summary,
        content=i.content,
        revision=i.revision,
        modified_at=i.modified_at,
    )


def _proposal(p: KnowledgeProposal, *, actor: str, names: dict[str, str]) -> ProposalResponse:
    return ProposalResponse(
        proposal_id=p.proposal_id,
        origin=p.origin.value,
        study_id=p.study_id,
        study_name=names.get(p.study_id) if p.study_id else None,
        item_id=p.item_id,
        kind=p.kind.value,
        title=p.title,
        summary=p.summary,
        status=p.status.value,
        proposed_by=p.proposed_by,
        proposed_at=p.proposed_at,
        decided_by=p.decided_by,
        decided_at=p.decided_at,
        decision_note=p.decision_note,
        revision=p.revision,
        yours=p.proposed_by == actor,
    )


def _slug(name: str) -> str:
    """A URL-safe slug from a Czech name, unique enough to never collide in practice."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:48].strip("-") or "study"
    return f"{base}-{uuid4().hex[:6]}"


# --------------------------------------------------------------------------- #
# The directory and one client
# --------------------------------------------------------------------------- #


class Me(BaseModel):
    """Who the caller is in this organization."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: str | None
    organization_role: str
    may_administer: bool


class ClientStart(BaseModel):
    """A new client, as an administrator starts one from the directory."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


@router.get("/workspace/me", response_model=Me, summary="Who you are here")
def me(principal: PrincipalDep, admin: OrganizationDep) -> Me:
    """The caller's user id, e-mail and organization role; no client data."""
    return Me(
        user_id=principal.user_id,
        email=principal.email,
        organization_role=admin.organization_role.value,
        may_administer=admin.may_administer,
    )


@router.post(
    "/workspace/clients",
    response_model=ClientWorkspace,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new client",
)
def start_client(
    body: ClientStart,
    principal: PrincipalDep,
    admin: OrganizationDep,
    resolver: ResolverDep,
    repo: ScopeRepositoryDep,
) -> ClientWorkspace:
    """Create a client and grant its creator LEAD on it, in one transaction.

    Organization administration is required, as for ``POST /clients``. The grant
    is the ordinary self-grant ADR 0004 allows and audits as ``CLIENT_SELF_GRANT``:
    without it the creator could not open the client they just made.
    """
    try:
        client = repo.create_client(admin, slug=_slug(body.name), name=body.name.strip())
        resolver.grant_client_access(
            admin,
            client_id=client.client_id,
            user_id=principal.user_id,
            role=ScopeRole.LEAD,
            reason="created the client from the directory",
        )
    except ScopeDenied as exc:
        raise _forbidden(
            exc.reason, "Starting a client needs an organization owner or admin."
        ) from exc
    return _workspace(_client_scope(principal, resolver, client.client_id), repo)


@router.get(
    "/workspace/clients", response_model=list[ClientCard], summary="The clients you work for"
)
def my_clients(
    principal: PrincipalDep, resolver: ResolverDep, repo: ScopeRepositoryDep
) -> list[ClientCard]:
    """The clients the caller holds a grant in: a client grant, or a study grant within it.

    Organization owners and admins are not silently included (ADR 0004); an
    administrator who needs a client grants themselves access, and that is audited.
    """
    cards: list[ClientCard] = []
    for client_id in resolver.accessible_clients(principal):
        scope = _client_scope(principal, resolver, client_id)
        client = repo.get_client_in_scope(scope)
        studies = repo.studies_in_client(scope, include_archived=False)
        active = [s for s in studies if s.status in OPEN_STATUSES]
        cards.append(
            ClientCard(
                client_id=client.client_id,
                name=client.name,
                slug=client.slug,
                your_role=scope.client_role.value if scope.client_role else None,
                active_count=len(active),
                study_count=len(studies),
                recent=[_study(s, None) for s in active[:2]],
                modified_at=max(
                    (s.modified_at for s in studies if s.modified_at), default=client.modified_at
                ),
            )
        )
    return sorted(cards, key=lambda c: c.name.lower())


@router.get(
    "/clients/{client_id}", response_model=ClientWorkspace, summary="One client's workspace"
)
def client_workspace(
    client_id: ClientIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    repo: ScopeRepositoryDep,
) -> ClientWorkspace:
    """The client, the caller's role in it and what they may do. 404 outside their scope."""
    return _workspace(_client_scope(principal, resolver, client_id), repo)


@router.get(
    "/clients/{client_id}/studies",
    response_model=list[WorkspaceStudy],
    summary="The client's research and simulations",
)
def client_studies(
    client_id: ClientIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    repo: ScopeRepositoryDep,
    session: SessionDep,
    kind: Annotated[Literal["RESEARCH", "SIMULATION"] | None, Query()] = None,
    include_archived: bool = True,
) -> list[WorkspaceStudy]:
    """The studies of this client the caller may open, newest change first."""
    scope = _client_scope(principal, resolver, client_id)
    studies = repo.studies_in_client(
        scope, kind=StudyKind(kind) if kind else None, include_archived=include_archived
    )
    bound = StudyWorkspaceRepository(session).in_client(scope)
    return [_study(s, bound.get(s.study_id)) for s in studies]


@router.post(
    "/clients/{client_id}/studies",
    response_model=WorkspaceStudy,
    status_code=status.HTTP_201_CREATED,
    summary="Start a research or a simulation for the client",
)
def start_study(
    client_id: ClientIdPath,
    body: StudyCreate,
    principal: PrincipalDep,
    resolver: ResolverDep,
    repo: ScopeRepositoryDep,
) -> WorkspaceStudy:
    """Needs a client-level RESEARCHER or LEAD role (``CREATE_STUDY``)."""
    scope = _client_scope(principal, resolver, client_id)
    try:
        study = repo.create_study_in_client(
            scope, slug=_slug(body.name), name=body.name.strip(), kind=StudyKind(body.kind)
        )
    except ScopeDenied as exc:
        raise _forbidden(
            exc.reason, "Your role for this client does not permit starting work."
        ) from exc
    return _study(study, None)


@router.get("/clients/{client_id}/overview", response_model=ClientOverview, summary="Přehled")
def client_overview(
    client_id: ClientIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    repo: ScopeRepositoryDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> ClientOverview:
    """Active work, recent outputs, the state of the client's knowledge, pending approvals.

    Each study's outputs are read under that study's own scope, so a study grant
    that narrows access narrows what appears here too.
    """
    scope = _client_scope(principal, resolver, client_id)
    studies = repo.studies_in_client(scope, include_archived=True)
    bound = StudyWorkspaceRepository(session).in_client(scope)
    active = [s for s in studies if s.status in OPEN_STATUSES]
    names = {s.study_id: s.name for s in studies}

    outputs: list[OutputItem] = []
    for s in studies[:12]:
        try:
            study_scope = resolver.study_context(principal, study_id=s.study_id)
            recent = ArtifactRepository(session, study_scope, store).recent(limit=3)
        except ScopeDenied:
            continue
        outputs.extend(
            OutputItem(
                artifact_id=a.artifact_id,
                artifact_type=a.artifact_type,
                stage_type=a.stage_type,
                status=a.status.value,
                study_id=s.study_id,
                study_name=s.name,
                created_at=a.created_at,
            )
            for a in recent
        )
    outputs.sort(key=lambda o: o.created_at or datetime.min, reverse=True)

    knowledge: KnowledgeSummaryResponse | None = None
    pending: list[ProposalResponse] = []
    if scope.has(ClientPermission.VIEW_CLIENT_KNOWLEDGE):
        kr = ClientKnowledgeRepository(session)
        summary = kr.summary(scope)
        knowledge = KnowledgeSummaryResponse(
            context_revision=summary.context_revision,
            items_by_kind={k.value: n for k, n in summary.items_by_kind.items()},
            pending_proposals=summary.pending_proposals,
            last_approved_at=summary.last_approved_at,
        )
        pending = [
            _proposal(p, actor=scope.actor_id, names=names)
            for p in kr.proposals(scope, status=ProposalStatus.PROPOSED)[:5]
        ]
    return ClientOverview(
        client=_workspace(scope, repo),
        active=[_study(s, bound.get(s.study_id)) for s in active[:8]],
        previous_count=len(studies) - len(active),
        recent_outputs=outputs[:6],
        knowledge=knowledge,
        pending=pending,
    )


# --------------------------------------------------------------------------- #
# Client knowledge
# --------------------------------------------------------------------------- #


def _knowledge_scope(principal: Any, resolver: Any, client_id: str) -> ClientContext:
    scope = _client_scope(principal, resolver, client_id)
    if not scope.has(ClientPermission.VIEW_CLIENT_KNOWLEDGE):
        raise _forbidden("insufficient_role", "Client knowledge needs a role for the whole client.")
    return scope


@router.get(
    "/clients/{client_id}/knowledge",
    response_model=list[KnowledgeItemResponse],
    summary="The client's knowledge",
)
def client_knowledge(
    client_id: ClientIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    section: Annotated[
        Literal["sources", "knowledge", "dimensions", "audiences", "data"] | None, Query()
    ] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> list[KnowledgeItemResponse]:
    """Approved knowledge of this client only: the client is resolved first and is in the query."""
    scope = _knowledge_scope(principal, resolver, client_id)
    kinds = KNOWLEDGE_SECTIONS[section] if section else None
    return [_item(i) for i in ClientKnowledgeRepository(session).items(scope, kinds=kinds, text=q)]


@router.get(
    "/clients/{client_id}/knowledge/items/{item_id}/revisions",
    response_model=list[KnowledgeRevisionResponse],
    summary="An item's revision history",
)
def knowledge_revisions(
    client_id: ClientIdPath,
    item_id: Annotated[str, Path(max_length=64, pattern=r"^KNW-[0-9a-f]{1,32}$")],
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> list[KnowledgeRevisionResponse]:
    """Oldest first, each with its provenance. 404 when the item is not this client's."""
    scope = _knowledge_scope(principal, resolver, client_id)
    revisions = ClientKnowledgeRepository(session).revisions(scope, item_id=item_id)
    if not revisions:
        raise _not_found()
    return [
        KnowledgeRevisionResponse(
            revision=r.revision,
            context_revision=r.context_revision,
            title=r.title,
            summary=r.summary,
            provenance=r.provenance,
            approved_by=r.approved_by,
            approved_at=r.approved_at,
        )
        for r in revisions
    ]


@router.get(
    "/clients/{client_id}/knowledge/proposals",
    response_model=list[ProposalResponse],
    summary="Pending and decided knowledge updates",
)
def knowledge_proposals(
    client_id: ClientIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    repo: ScopeRepositoryDep,
    session: SessionDep,
    status_: Annotated[
        Literal["PROPOSED", "APPROVED", "REJECTED"] | None, Query(alias="status")
    ] = None,
) -> list[ProposalResponse]:
    """The client's proposals, newest first."""
    scope = _knowledge_scope(principal, resolver, client_id)
    names = {s.study_id: s.name for s in repo.studies_in_client(scope)}
    proposals = ClientKnowledgeRepository(session).proposals(
        scope, status=ProposalStatus(status_) if status_ else None
    )
    return [_proposal(p, actor=scope.actor_id, names=names) for p in proposals]


@router.post(
    "/clients/{client_id}/knowledge/proposals",
    response_model=ProposalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Propose a knowledge update",
)
def propose_knowledge(
    client_id: ClientIdPath,
    body: ProposalCreate,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> ProposalResponse:
    """A proposal changes nothing until a person with the approval permission decides."""
    scope = _knowledge_scope(principal, resolver, client_id)
    try:
        proposal = ClientKnowledgeRepository(session).propose(
            scope,
            kind=body.kind,
            title=body.title,
            summary=body.summary,
            content=body.content,
            item_id=body.item_id,
        )
    except ScopeDenied as exc:
        if exc.reason == "unknown_item":
            raise _not_found() from exc
        raise _forbidden(
            exc.reason, "Your role for this client does not permit proposing knowledge."
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_proposal", "message": str(exc)}
        ) from exc
    return _proposal(proposal, actor=scope.actor_id, names={})


@router.post(
    "/clients/{client_id}/knowledge/proposals/{proposal_id}/decision",
    response_model=ProposalResponse,
    summary="Approve or reject a knowledge update",
)
def decide_knowledge(
    client_id: ClientIdPath,
    proposal_id: Annotated[str, Path(max_length=64, pattern=r"^KNP-[0-9a-f]{1,32}$")],
    body: DecisionRequest,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> ProposalResponse:
    """An approval appends a revision and advances the client's knowledge revision."""
    scope = _knowledge_scope(principal, resolver, client_id)
    try:
        proposal = ClientKnowledgeRepository(session).decide(
            scope, proposal_id=proposal_id, approve=body.approve, note=body.note
        )
    except SeparationOfDutiesViolation as exc:
        raise _forbidden(
            exc.reason, "Someone other than the proposer must decide this update."
        ) from exc
    except ScopeDenied as exc:
        if exc.reason in ("unknown_proposal", "unknown_item"):
            raise _not_found() from exc
        raise _forbidden(
            exc.reason, "Your role for this client does not permit approving knowledge."
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409, detail={"code": "already_decided", "message": str(exc)}
        ) from exc
    return _proposal(proposal, actor=scope.actor_id, names={})


# --------------------------------------------------------------------------- #
# One study: its frame, the unit bridge, what it consumes, what it proposes
# --------------------------------------------------------------------------- #


def _study_workspace(scope: Any, repo: Any, session: Any) -> StudyWorkspaceResponse:
    study = repo.get_study(scope)
    client = repo.client_of_study(scope)
    workspace = StudyWorkspaceRepository(session).get(scope)
    return StudyWorkspaceResponse(
        study=_study(study, workspace),
        client_name=client.name,
        your_role=scope.role.value,
        can_edit=scope.has(Permission.EDIT_STUDY),
        unit_project_id=workspace.unit_project_id if workspace else None,
    )


@router.get(
    "/studies/{study_id}/workspace",
    response_model=StudyWorkspaceResponse,
    summary="One study's frame and bridge",
)
def study_workspace(
    scope: StudyScopeDep, repo: ScopeRepositoryDep, session: SessionDep
) -> StudyWorkspaceResponse:
    """The study, its client's name, the caller's role, and the unit project bound to it (OI-58).

    The unit project id comes out of the study's scope; nothing takes one in to
    find a study.
    """
    return _study_workspace(scope, repo, session)


@router.put(
    "/studies/{study_id}/workspace",
    response_model=StudyWorkspaceResponse,
    summary="Bind the study's working content",
)
def bind_study_workspace(
    body: BindRequest, scope: StudyScopeDep, repo: ScopeRepositoryDep, session: SessionDep
) -> StudyWorkspaceResponse:
    """Once per study, never to a unit project bound elsewhere.

    Needs ``EDIT_STUDY`` on an open study.
    """
    try:
        StudyWorkspaceRepository(session).bind(scope, unit_project_id=body.unit_project_id)
    except ScopeDenied as exc:
        raise _forbidden(exc.reason, "Your role on this study does not permit that.") from exc
    except WorkspaceConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.reason, "message": "The working content is already bound."},
        ) from exc
    return _study_workspace(scope, repo, session)


@router.put(
    "/studies/{study_id}/workspace/stage",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remember the open stage",
)
def record_study_stage(body: StageRequest, scope: StudyScopeDep, session: SessionDep) -> None:
    """For "continue where you left off". A no-op for a role that may not edit."""
    try:
        StudyWorkspaceRepository(session).record_stage(scope, stage=body.stage)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "unknown_stage", "message": str(exc)}
        ) from exc


@router.get(
    "/studies/{study_id}/context",
    response_model=StudyContextResponse,
    summary="What the study consumes",
)
def study_context(scope: StudyScopeDep, session: SessionDep) -> StudyContextResponse:
    """The study's inherited context, by layer.

    Shared intelligence first, then its own client's approved knowledge.
    """
    items = ClientKnowledgeRepository(session).for_study(scope)
    return StudyContextResponse(
        client_id=scope.client_id,
        shared={"population": "the population bound to each run (docs/architecture/population.md)"},
        client=[_item(i) for i in items],
    )


@router.post(
    "/studies/{study_id}/knowledge-proposals",
    response_model=ProposalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Offer a study finding for reuse",
)
def propose_from_study(
    body: ProposalCreate, scope: StudyScopeDep, session: SessionDep
) -> ProposalResponse:
    """The study proposes; it never writes client knowledge. Needs ``EDIT_STUDY``."""
    try:
        proposal = ClientKnowledgeRepository(session).propose_from_study(
            scope,
            kind=body.kind,
            title=body.title,
            summary=body.summary,
            content=body.content,
            item_id=body.item_id,
        )
    except ScopeDenied as exc:
        if exc.reason == "unknown_item":
            raise _not_found() from exc
        raise _forbidden(
            exc.reason, "Your role on this study does not permit proposing knowledge."
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_proposal", "message": str(exc)}
        ) from exc
    return _proposal(proposal, actor=scope.actor_id, names={})
