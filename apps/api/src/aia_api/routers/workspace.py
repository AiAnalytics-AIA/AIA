"""The client workspace: clients, their studies, a study's working content, client knowledge.

ADR 0015, ADR 0018. Everything here resolves scope first -- a ``ClientContext`` for
the client's own surfaces, a ``StudyContext`` for one study -- and every denial of
scope is a 404, as elsewhere. Inside a client the caller demonstrably has, a
missing permission is a 403: acknowledging the client leaks nothing.

A research study's working content -- what its stages edit -- is loaded and saved
here, in AIA (``/studies/{study_id}/workspace/content``), and so are the files its
brief carries (``/studies/{study_id}/workspace/attachments``). No route takes a
project id or an 18.6.6 unit project id to find a study.
"""

from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

from aia_core.application.design_reuse import ReuseRefused, reuse_design
from aia_core.application.project_memory import (
    MIN_QUERY_LENGTH,
    search_client_studies,
)
from aia_core.domain.attachments import ATTACHMENT_MAX_BYTES, AttachmentRejected
from aia_core.domain.client_profile import ClientContact, ClientProfile, ContactDraft
from aia_core.domain.design import DesignRejected
from aia_core.domain.knowledge import (
    KNOWLEDGE_SECTIONS,
    KnowledgeFolder,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeLabel,
    KnowledgeProposal,
    LabelColour,
    OrganizerNameTaken,
    ProposalStatus,
    StaleKnowledgeProposal,
    source_ref,
)
from aia_core.domain.questionnaire_import import QuestionnaireImportRejected
from aia_core.domain.research_template import research_template
from aia_core.domain.scope import (
    ClientContext,
    ClientPermission,
    Permission,
    ScopeDenied,
    SeparationOfDutiesViolation,
    Study,
    StudyKind,
    StudyStatus,
)
from aia_core.domain.workspace import (
    ContentState,
    StudyWorkspace,
    WorkingContent,
    WorkspaceRejected,
)
from aia_core.infrastructure.artifact_repository import ArtifactNotFound, ArtifactRepository
from aia_core.infrastructure.client_knowledge_repository import (
    KEEP_FOLDER,
    ClientKnowledgeRepository,
)
from aia_core.infrastructure.client_profile_repository import ClientProfileRepository
from aia_core.infrastructure.client_source_repository import ClientSourceRepository
from aia_core.infrastructure.questionnaire_file import (
    TEMPLATE_FILENAME,
    import_questionnaire,
    template_xlsx,
)
from aia_core.infrastructure.storage import IntegrityError, ObjectNotFound
from aia_core.infrastructure.study_design_repository import DesignRevisionNotFound
from aia_core.infrastructure.study_workspace_repository import (
    StudyWorkspaceRepository,
    WorkspaceConflict,
)
from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
from .research import (
    DesignRevisionResponse,
    DesignSourceResponse,
    design_revision_response,
    design_source_response,
)
from .runs import artifact_corrupt

router = APIRouter(
    tags=["workspace"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Insufficient role"},
        404: {"model": ErrorResponse, "description": "Not found, or not accessible"},
    },
)

ClientIdPath = Annotated[str, Path(max_length=64, pattern=r"^CLI-[0-9a-f]{1,32}$")]
AttachmentIdPath = Annotated[str, Path(max_length=64, pattern=r"^ART-[0-9a-f]{1,32}$")]
# The base64 of the largest attachment the domain accepts; a longer body is refused
# before it is decoded.
_ATTACHMENT_B64_MAX = -(-ATTACHMENT_MAX_BYTES // 3) * 4
OPEN_STATUSES = (StudyStatus.DRAFT, StudyStatus.ACTIVE, StudyStatus.IN_REVIEW)


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class StudyKnowledgeCounts(BaseModel):
    """What one study proposed to the client's knowledge: accepted, waiting, turned down."""

    model_config = ConfigDict(extra="forbid")

    approved: int = 0
    proposed: int = 0
    rejected: int = 0


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
    #: Where the study's working content stands (``ContentState``), by name.
    content_state: str = ContentState.EMPTY.value
    created_at: datetime | None = None
    modified_at: datetime | None = None
    #: Only on the studies list, and only for a caller who may read the client's knowledge.
    knowledge: StudyKnowledgeCounts | None = None


class MemoryFieldMatch(BaseModel):
    """A field of a past study that holds the searched words, and the texts that do."""

    field: str
    texts: list[str]


class MemoryHitResponse(BaseModel):
    """A past study of the client that says what was searched for (project memory M1)."""

    study_id: str
    name: str
    kind: str
    status: str
    modified_at: datetime | None
    #: ``design``: its latest Design Revision; ``draft``: its working content, the study has
    #: no Design Revision; ``name``: its name alone.
    source: Literal["design", "draft", "name"]
    design_revision: int | None
    matches: list[MemoryFieldMatch]


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


class ClientCounts(BaseModel):
    """What the client's tabs count: open studies, and knowledge waiting or held.

    Archived studies are not counted. The knowledge counts are null for a caller
    who may not read the client's knowledge: unknown, never zero.
    """

    model_config = ConfigDict(extra="forbid")

    research: int
    simulations: int
    pending_proposals: int | None
    datasets: int | None


class ClientWorkspace(BaseModel):
    """The client a workspace is about, and what the caller may do in it."""

    model_config = ConfigDict(extra="forbid")

    client_id: str
    name: str
    slug: str
    status: str
    your_role: str | None
    permissions: list[str]
    counts: ClientCounts | None = None
    #: Whether a proposer may accept their own knowledge proposal here, and which level
    #: decided it (default, organization, client). Set from Settings or the profile.
    self_approval_allowed: bool | None = None
    self_approval_source: str | None = None


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
    #: Where people filed it (client-workspace C3); not part of the knowledge itself.
    folder_id: str | None = None
    label_ids: list[str] = Field(default_factory=list)


class KnowledgeFolderResponse(BaseModel):
    """A folder of the client's knowledge and how many active items it holds."""

    model_config = ConfigDict(extra="forbid")

    folder_id: str
    name: str
    item_count: int


class KnowledgeLabelResponse(BaseModel):
    """A label of the client's knowledge and how many active items carry it."""

    model_config = ConfigDict(extra="forbid")

    label_id: str
    name: str
    colour: LabelColour
    item_count: int


class FolderWrite(BaseModel):
    """A folder's name: trimmed, at most 80 characters, unique within the client."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)


class LabelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    colour: LabelColour


class LabelChange(BaseModel):
    """Rename, recolour, or both; at least one."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    colour: LabelColour | None = None


_ITEM_ID = r"^KNW-[0-9a-f]{1,32}$"
_FOLDER_ID = r"^KNF-[0-9a-f]{1,32}$"
_LABEL_ID = r"^KNL-[0-9a-f]{1,32}$"


class Placement(BaseModel):
    """File items: into a folder, out of every folder, labels on and off.

    ``folder_id`` left out keeps each item's folder; ``null`` takes the items out
    of any folder. All or nothing.
    """

    model_config = ConfigDict(extra="forbid")

    item_ids: list[Annotated[str, Field(max_length=64, pattern=_ITEM_ID)]] = Field(
        min_length=1, max_length=200
    )
    folder_id: Annotated[str, Field(max_length=64, pattern=_FOLDER_ID)] | None = None
    add_labels: list[Annotated[str, Field(max_length=64, pattern=_LABEL_ID)]] = Field(
        default_factory=list, max_length=50
    )
    remove_labels: list[Annotated[str, Field(max_length=64, pattern=_LABEL_ID)]] = Field(
        default_factory=list, max_length=50
    )


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
    #: The item revision an edit was written from (null for a new item, or unknown).
    base_revision: int | None = None
    yours: bool = False
    #: The client's source the proposed item names (C7a), so a reviewer sees the file.
    source_id: str | None = None


class KnowledgeSummaryResponse(BaseModel):
    """The state of the client's knowledge."""

    model_config = ConfigDict(extra="forbid")

    context_revision: int
    items_by_kind: dict[str, int]
    pending_proposals: int
    last_approved_at: datetime | None = None
    #: Active items unchanged for over a year, and active items in no folder.
    stale_items: int = 0
    unfiled_items: int = 0


class KnowledgeChangeResponse(BaseModel):
    """One recent revision of the client's knowledge, for Přehled's feed."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    title: str
    revision: int
    #: STUDY: a study's finding accepted; PERSON: written by a person; PROPOSAL: a person's
    #: proposal decided by someone else.
    origin: Literal["STUDY", "PERSON", "PROPOSAL"]
    at: datetime | None = None


class ClientOverview(BaseModel):
    """Přehled: what the researcher needs to continue their work for this client."""

    model_config = ConfigDict(extra="forbid")

    client: ClientWorkspace
    active: list[WorkspaceStudy]
    previous_count: int
    recent_outputs: list[OutputItem]
    knowledge: KnowledgeSummaryResponse | None
    pending: list[ProposalResponse]
    recent_changes: list[KnowledgeChangeResponse] = Field(default_factory=list)


class StudyCreate(BaseModel):
    """Start a research or a simulation for the client."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    kind: Literal["RESEARCH", "SIMULATION"]


class StudyWorkspaceResponse(BaseModel):
    """One study as its frame needs it: the study, its client, the caller's rights."""

    model_config = ConfigDict(extra="forbid")

    study: WorkspaceStudy
    client_name: str
    your_role: str
    can_edit: bool
    content_state: str


class WorkingContentResponse(BaseModel):
    """A research study's working content, as its stages load it (ADR 0018)."""

    model_config = ConfigDict(extra="forbid")

    study_id: str
    #: ``ContentState``: EMPTY, NATIVE, MIGRATED, RECOVERED, UNRECOVERABLE or AWAITING_MIGRATION.
    state: str
    #: The revision the content is at; a save names it as its ``base_revision``.
    revision: int | None
    revision_id: str | None
    content: dict[str, Any] | None
    analysis: dict[str, Any] | None
    #: The document a new study starts from and every stored one is completed with.
    template: dict[str, Any]
    saved_at: datetime | None
    saved_by: str | None
    can_edit: bool
    #: Where migrated content came from; empty for content made in AIA.
    lineage: dict[str, Any]


class WorkingContentSave(BaseModel):
    """Save the study's working content as its newest revision."""

    model_config = ConfigDict(extra="forbid")

    content: dict[str, Any]
    analysis: dict[str, Any] | None = None
    #: The revision the content was edited from; null only for a study with no content yet.
    base_revision: int | None = Field(default=None, ge=1)
    reason: str = Field(default="autosave", max_length=64, pattern=r"^[a-z0-9_:.-]{1,64}$")


class WorkingContentSaved(BaseModel):
    """What one save did."""

    model_config = ConfigDict(extra="forbid")

    study_id: str
    state: str
    revision: int
    revision_id: str
    deduplicated: bool


class WorkingRevisionResponse(BaseModel):
    """One saved revision of a study's working content."""

    model_config = ConfigDict(extra="forbid")

    revision: int
    revision_id: str
    parent_revision: int | None
    reason: str
    content_sha256: str
    created_at: datetime
    created_by: str | None


class WorkingRevisionList(BaseModel):
    """A study's working-content history, newest first."""

    model_config = ConfigDict(extra="forbid")

    items: list[WorkingRevisionResponse]


class AttachmentUpload(BaseModel):
    """One file for the brief, base64-encoded as the classic interface sent it."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    data_b64: str = Field(min_length=1, max_length=_ATTACHMENT_B64_MAX)


class AttachmentResponse(BaseModel):
    """What the brief keeps of an attached file: its record, never a storage location."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["file"]
    attachment_id: str
    filename: str
    extension: str
    content_type: str
    size_bytes: int
    sha256: str
    text_extracted: bool
    context_excerpt: str


class QuestionnaireUpload(BaseModel):
    """A filled-in questionnaire template, base64-encoded as the classic interface sent it."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    data_b64: str = Field(min_length=1, max_length=_ATTACHMENT_B64_MAX)


class ImportSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_count: int
    tracked_sets: int
    sections: int


class QuestionnaireImportResponse(BaseModel):
    """The sections the file holds, normalized as 18.6.6 normalized them, and its summary."""

    model_config = ConfigDict(extra="forbid")

    sections: list[dict[str, Any]]
    summary: ImportSummaryResponse
    filename: str


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
    #: The item revision this edit was made from; an edit of an older one is refused (409).
    base_revision: int | None = Field(default=None, ge=1)


class DecisionRequest(BaseModel):
    """Approve or reject a proposal."""

    model_config = ConfigDict(extra="forbid")

    approve: bool
    note: str = Field(default="", max_length=2_000)
    #: The item's current revision, which the reviewer read: approves an edit written from
    #: an older one over it. Without it such an approval is refused (409).
    reviewed_revision: int | None = Field(default=None, ge=1)


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
    state = workspace.state if workspace else ContentState.EMPTY
    return WorkspaceStudy(
        study_id=study.study_id,
        client_id=study.client_id,
        name=study.name,
        slug=study.slug,
        kind=study.kind.value,
        status=study.status.value,
        accepts_work=study.status.accepts_work,
        last_stage=workspace.last_stage if workspace else None,
        has_working_content=state.has_content or state is ContentState.AWAITING_MIGRATION,
        content_state=state.value,
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
        self_approval_allowed=scope.self_approval.allowed,
        self_approval_source=scope.self_approval.source.value,
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
        folder_id=i.folder_id,
        label_ids=list(i.label_ids),
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
        base_revision=p.base_revision,
        yours=p.proposed_by == actor,
        source_id=_named_source(p),
    )


def _named_source(p: KnowledgeProposal) -> str | None:
    """The source a proposal names; one filed before the rule was kept (C7a) names none."""
    try:
        return source_ref(p.kind, p.content)
    except ValueError:
        return None


def _stale(exc: StaleKnowledgeProposal) -> HTTPException:
    """409: the item moved on since the edit was written; nothing was changed."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "knowledge_proposal_stale",
            "message": "The item has a newer revision than the one this edit was written from.",
            "details": {
                "item_id": exc.item_id,
                "base_revision": exc.base_revision,
                "current_revision": exc.current_revision,
            },
        },
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
    """A new client, as a researcher starts one from the directory."""

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
    """Create a client and open its workspace.

    Any member of the organization may, as for ``POST /clients`` (ADR 0019). Membership is
    the access, so the creator, like every member, can open it at once.
    """
    client = repo.create_client(admin, slug=_slug(body.name), name=body.name.strip())
    return _workspace(_client_scope(principal, resolver, client.client_id), repo)


@router.get(
    "/workspace/clients", response_model=list[ClientCard], summary="The clients you work for"
)
def my_clients(
    principal: PrincipalDep, resolver: ResolverDep, repo: ScopeRepositoryDep
) -> list[ClientCard]:
    """The organization's clients the caller may open: every one that is not archived (ADR 0019)."""
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
    session: SessionDep,
) -> ClientWorkspace:
    """The client, the caller's role in it, what they may do, and what its tabs count.

    404 outside their scope.
    """
    scope = _client_scope(principal, resolver, client_id)
    studies = repo.studies_in_client(scope, include_archived=False)
    pending: int | None = None
    datasets: int | None = None
    if scope.has(ClientPermission.VIEW_CLIENT_KNOWLEDGE):
        summary = ClientKnowledgeRepository(session).summary(scope)
        pending = summary.pending_proposals
        datasets = summary.items_by_kind.get(KnowledgeKind.DATASET, 0)
    counts = ClientCounts(
        research=sum(1 for s in studies if s.kind is StudyKind.RESEARCH),
        simulations=sum(1 for s in studies if s.kind is StudyKind.SIMULATION),
        pending_proposals=pending,
        datasets=datasets,
    )
    return _workspace(scope, repo).model_copy(update={"counts": counts})


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
    """The studies of this client the caller may open, newest change first.

    Each says what it brought into the client's knowledge when the caller may read it:
    zeros for a study that proposed nothing, null when the caller may not know.
    """
    scope = _client_scope(principal, resolver, client_id)
    studies = repo.studies_in_client(
        scope, kind=StudyKind(kind) if kind else None, include_archived=include_archived
    )
    bound = StudyWorkspaceRepository(session).in_client(scope)
    listed = [_study(s, bound.get(s.study_id)) for s in studies]
    if not scope.has(ClientPermission.VIEW_CLIENT_KNOWLEDGE):
        return listed
    counts = ClientKnowledgeRepository(session).proposal_counts_by_study(scope)

    def brought(study_id: str) -> StudyKnowledgeCounts:
        c = counts.get(study_id, {})
        return StudyKnowledgeCounts(
            approved=c.get(ProposalStatus.APPROVED, 0),
            proposed=c.get(ProposalStatus.PROPOSED, 0),
            rejected=c.get(ProposalStatus.REJECTED, 0),
        )

    return [s.model_copy(update={"knowledge": brought(s.study_id)}) for s in listed]


@router.get(
    "/clients/{client_id}/memory/search",
    response_model=list[MemoryHitResponse],
    summary="Search this client's past studies on their designs",
    responses={404: {"model": ErrorResponse, "description": "No such client"}},
)
def client_memory_search(
    client_id: ClientIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    q: Annotated[str, Query(min_length=MIN_QUERY_LENGTH, max_length=200)],
) -> list[MemoryHitResponse]:
    """The client's studies whose name or design holds every word of ``q``, and where.

    Only this client's studies are searched (project memory M1, owner 2026-10-10); a study
    with no Design Revision is searched on its working draft and says so.
    """
    _client_scope(principal, resolver, client_id)  # 404 before anything is searched
    try:
        hits = search_client_studies(session, resolver, principal, client_id=client_id, query=q)
    except ScopeDenied as exc:  # pragma: no cover - resolved just above
        raise _not_found() from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "query_too_short", "message": str(exc)},
        ) from None
    return [
        MemoryHitResponse(
            study_id=h.study_id,
            name=h.name,
            kind=h.kind.value,
            status=h.status.value,
            modified_at=h.modified_at,
            source=h.source.value,
            design_revision=h.design_revision,
            matches=[MemoryFieldMatch(field=m.field, texts=list(m.texts)) for m in h.matches],
        )
        for h in hits
    ]


class MemoryReuse(BaseModel):
    """Start a study from a past study's Design Revision: a new one, or an empty one."""

    model_config = ConfigDict(extra="forbid")

    source_study_id: str = Field(min_length=1, max_length=64)
    source_revision_id: str = Field(min_length=1, max_length=64)
    #: An existing, empty research study of the client; or ``new_study_name`` for a new one.
    target_study_id: str | None = Field(default=None, min_length=1, max_length=64)
    new_study_name: str | None = Field(default=None, min_length=1, max_length=255)


class MemoryReuseResponse(BaseModel):
    """The study the design now starts, its first Design Revision and its citation."""

    model_config = ConfigDict(extra="forbid")

    study_id: str
    created_study: bool
    revision: DesignRevisionResponse
    source: DesignSourceResponse


@router.post(
    "/clients/{client_id}/memory/reuse",
    response_model=MemoryReuseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new or empty study from a past study's design",
    responses={
        404: {"model": ErrorResponse, "description": "Outside the client"},
        409: {"model": ErrorResponse, "description": "The target is not an empty research study"},
    },
)
def client_memory_reuse(
    client_id: ClientIdPath,
    body: MemoryReuse,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> MemoryReuseResponse:
    """Reuse a past research design of this client (project memory M3, owner 2026-10-12).

    Into a new research study, or one with no working content and no Design Revision: nothing
    anyone wrote is replaced. The target's design cites its source with the labels every run of
    the source revision carries. Anything outside the client is a 404, like an unknown study.
    """
    if (body.target_study_id is None) == (body.new_study_name is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "target_required",
                "message": "Name either target_study_id or new_study_name.",
            },
        )
    _client_scope(principal, resolver, client_id)  # 404 before anything is read
    name = body.new_study_name.strip() if body.new_study_name else None
    try:
        reused = reuse_design(
            session,
            resolver,
            principal,
            store,
            client_id=client_id,
            source_study_id=body.source_study_id,
            source_revision_id=body.source_revision_id,
            target_study_id=body.target_study_id,
            new_study=(_slug(name), name) if name else None,
        )
    except (ScopeDenied, DesignRevisionNotFound) as exc:
        raise _not_found() from exc
    except (ReuseRefused, DesignRejected) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.reason, "message": str(exc)},
        ) from None
    return MemoryReuseResponse(
        study_id=reused.study_id,
        created_study=reused.created_study,
        revision=design_revision_response(reused.revision),
        source=design_source_response(reused.source),
    )


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
    """Any member of the organization (``CREATE_STUDY``; ADR 0019)."""
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

    Each study's outputs are read under that study's own scope, never under the
    client's alone.
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
    changes: list[KnowledgeChangeResponse] = []
    if scope.has(ClientPermission.VIEW_CLIENT_KNOWLEDGE):
        kr = ClientKnowledgeRepository(session)
        summary = kr.summary(scope)
        health = kr.health(scope, now=datetime.now(UTC))
        knowledge = KnowledgeSummaryResponse(
            context_revision=summary.context_revision,
            items_by_kind={k.value: n for k, n in summary.items_by_kind.items()},
            pending_proposals=summary.pending_proposals,
            last_approved_at=summary.last_approved_at,
            stale_items=health.stale,
            unfiled_items=health.unfiled,
        )
        pending = [
            _proposal(p, actor=scope.actor_id, names=names)
            for p in kr.proposals(scope, status=ProposalStatus.PROPOSED)[:5]
        ]
        changes = [
            KnowledgeChangeResponse(
                item_id=r.item_id,
                title=r.title,
                revision=r.revision,
                origin=(
                    "STUDY"
                    if r.provenance.get("origin") == "STUDY"
                    else "PERSON"
                    if r.provenance.get("authored") == "person"
                    else "PROPOSAL"
                ),
                at=r.approved_at,
            )
            for r in kr.recent_revisions(scope, limit=6)
        ]
    return ClientOverview(
        client=_workspace(scope, repo),
        active=[_study(s, bound.get(s.study_id)) for s in active[:8]],
        previous_count=len(studies) - len(active),
        recent_outputs=outputs[:6],
        knowledge=knowledge,
        pending=pending,
        recent_changes=changes,
    )


# --------------------------------------------------------------------------- #
# The client's profile and contacts (client-workspace C5)
# --------------------------------------------------------------------------- #


class ClientProfileWrite(BaseModel):
    """The whole profile, as the form sends it; an empty field is not filled in."""

    model_config = ConfigDict(extra="forbid")

    short_code: str = Field(default="", max_length=64)
    industry: str = Field(default="", max_length=400)
    market: str = Field(default="", max_length=400)
    description: str = Field(default="", max_length=8000)


class ContactWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=400)
    role: str = Field(default="", max_length=400)
    email: str = Field(default="", max_length=400)
    receives_reports: bool = False


class ContactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: str
    name: str
    role: str
    email: str
    receives_reports: bool


class ProfileChangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    at: datetime | None
    fields: list[str]
    contact_name: str | None


class ClientProfileResponse(BaseModel):
    """The client's profile, its contacts and what changed in them, newest first."""

    model_config = ConfigDict(extra="forbid")

    short_code: str
    industry: str
    market: str
    description: str
    contacts: list[ContactResponse]
    history: list[ProfileChangeResponse]


ContactIdPath = Annotated[str, Path(max_length=64, pattern=r"^CON-[0-9a-f]{1,32}$")]


def _contact_out(c: ClientContact) -> ContactResponse:
    return ContactResponse(
        contact_id=c.contact_id,
        name=c.name,
        role=c.role,
        email=c.email,
        receives_reports=c.receives_reports,
    )


def _profile_out(scope: ClientContext, repo: ClientProfileRepository) -> ClientProfileResponse:
    p = repo.profile(scope)
    return ClientProfileResponse(
        short_code=p.short_code,
        industry=p.industry,
        market=p.market,
        description=p.description,
        contacts=[_contact_out(c) for c in repo.contacts(scope)],
        history=[
            ProfileChangeResponse(
                action=h.action, at=h.at, fields=list(h.fields), contact_name=h.contact_name
            )
            for h in repo.history(scope)
        ],
    )


def _profile_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ScopeDenied):
        if exc.reason in {"unknown_contact", "unknown_client"}:
            return _not_found()
        return _forbidden(
            exc.reason, "Your role for this client does not permit editing its profile."
        )
    return HTTPException(status_code=422, detail={"code": "invalid_profile", "message": str(exc)})


def _validated(model: Any, data: dict[str, Any]) -> Any:
    try:
        return model(**data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_profile",
                "message": "; ".join(e["msg"] for e in exc.errors()),
            },
        ) from exc


@router.get(
    "/clients/{client_id}/profile",
    response_model=ClientProfileResponse,
    summary="The client's profile and contacts",
)
def client_profile(
    client_id: ClientIdPath, principal: PrincipalDep, resolver: ResolverDep, session: SessionDep
) -> ClientProfileResponse:
    """Any member who may open the client reads it. No model ever reads it."""
    scope = _client_scope(principal, resolver, client_id)
    return _profile_out(scope, ClientProfileRepository(session))


@router.put(
    "/clients/{client_id}/profile",
    response_model=ClientProfileResponse,
    summary="Replace the client's profile",
)
def update_client_profile(
    client_id: ClientIdPath,
    body: ClientProfileWrite,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> ClientProfileResponse:
    """The whole profile at once; only a real change enters the history."""
    scope = _client_scope(principal, resolver, client_id)
    repo = ClientProfileRepository(session)
    profile = _validated(ClientProfile, body.model_dump())
    try:
        repo.update_profile(scope, profile)
    except ScopeDenied as exc:
        raise _profile_error(exc) from exc
    return _profile_out(scope, repo)


@router.post(
    "/clients/{client_id}/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a contact at the client",
)
def add_client_contact(
    client_id: ClientIdPath,
    body: ContactWrite,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> ContactResponse:
    scope = _client_scope(principal, resolver, client_id)
    draft = _validated(ContactDraft, body.model_dump())
    try:
        return _contact_out(ClientProfileRepository(session).add_contact(scope, draft))
    except (ScopeDenied, ValueError) as exc:
        raise _profile_error(exc) from exc


@router.put(
    "/clients/{client_id}/contacts/{contact_id}",
    response_model=ContactResponse,
    summary="Change a contact",
)
def update_client_contact(
    client_id: ClientIdPath,
    contact_id: ContactIdPath,
    body: ContactWrite,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> ContactResponse:
    scope = _client_scope(principal, resolver, client_id)
    draft = _validated(ContactDraft, body.model_dump())
    try:
        return _contact_out(
            ClientProfileRepository(session).update_contact(
                scope, contact_id=contact_id, draft=draft
            )
        )
    except ScopeDenied as exc:
        raise _profile_error(exc) from exc


@router.delete(
    "/clients/{client_id}/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a contact",
)
def remove_client_contact(
    client_id: ClientIdPath,
    contact_id: ContactIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> Response:
    scope = _client_scope(principal, resolver, client_id)
    try:
        ClientProfileRepository(session).remove_contact(scope, contact_id=contact_id)
    except ScopeDenied as exc:
        raise _profile_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    folder: Annotated[
        str | None, Query(max_length=64, pattern=r"^(KNF-[0-9a-f]{1,32}|unfiled)$")
    ] = None,
    label: Annotated[str | None, Query(max_length=64, pattern=_LABEL_ID)] = None,
) -> list[KnowledgeItemResponse]:
    """Approved knowledge of this client only: the client is resolved first and is in the query.

    ``folder`` keeps one folder's items (``unfiled``: those in none); ``label`` those
    carrying it. Each item says where it is filed.
    """
    scope = _knowledge_scope(principal, resolver, client_id)
    kinds = KNOWLEDGE_SECTIONS[section] if section else None
    items = ClientKnowledgeRepository(session).items(
        scope,
        kinds=kinds,
        text=q,
        folder_id=folder if folder and folder != "unfiled" else None,
        unfiled=folder == "unfiled",
        label_id=label,
    )
    return [_item(i) for i in items]


# Folders and labels (client-workspace C3): organization, never knowledge. Whoever may
# propose the client's knowledge may file it; nothing here writes a revision.


def _organizer_error(exc: Exception, what: str) -> HTTPException:
    if isinstance(exc, OrganizerNameTaken):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "name_taken",
                "message": f"This client already has a {what} by that name.",
            },
        )
    if isinstance(exc, ScopeDenied):
        if exc.reason in {"unknown_folder", "unknown_label", "unknown_item"}:
            return _not_found()
        return _forbidden(exc.reason, "Your role for this client does not permit filing knowledge.")
    return HTTPException(status_code=422, detail={"code": "invalid_name", "message": str(exc)})


def _folder(f: KnowledgeFolder) -> KnowledgeFolderResponse:
    return KnowledgeFolderResponse(folder_id=f.folder_id, name=f.name, item_count=f.item_count)


def _label(lb: KnowledgeLabel) -> KnowledgeLabelResponse:
    return KnowledgeLabelResponse(
        label_id=lb.label_id, name=lb.name, colour=lb.colour, item_count=lb.item_count
    )


FolderIdPath = Annotated[str, Path(max_length=64, pattern=_FOLDER_ID)]
LabelIdPath = Annotated[str, Path(max_length=64, pattern=_LABEL_ID)]


@router.get(
    "/clients/{client_id}/knowledge/folders",
    response_model=list[KnowledgeFolderResponse],
    summary="The client's knowledge folders",
)
def knowledge_folders(
    client_id: ClientIdPath, principal: PrincipalDep, resolver: ResolverDep, session: SessionDep
) -> list[KnowledgeFolderResponse]:
    scope = _knowledge_scope(principal, resolver, client_id)
    return [_folder(f) for f in ClientKnowledgeRepository(session).folders(scope)]


@router.post(
    "/clients/{client_id}/knowledge/folders",
    response_model=KnowledgeFolderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a knowledge folder",
)
def create_knowledge_folder(
    client_id: ClientIdPath,
    body: FolderWrite,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> KnowledgeFolderResponse:
    """409 when the client has a folder by that name (case and spacing do not count)."""
    scope = _knowledge_scope(principal, resolver, client_id)
    try:
        return _folder(ClientKnowledgeRepository(session).create_folder(scope, name=body.name))
    except (OrganizerNameTaken, ScopeDenied, ValueError) as exc:
        raise _organizer_error(exc, "folder") from exc


@router.put(
    "/clients/{client_id}/knowledge/folders/{folder_id}",
    response_model=KnowledgeFolderResponse,
    summary="Rename a knowledge folder",
)
def rename_knowledge_folder(
    client_id: ClientIdPath,
    folder_id: FolderIdPath,
    body: FolderWrite,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> KnowledgeFolderResponse:
    scope = _knowledge_scope(principal, resolver, client_id)
    try:
        return _folder(
            ClientKnowledgeRepository(session).rename_folder(
                scope, folder_id=folder_id, name=body.name
            )
        )
    except (OrganizerNameTaken, ScopeDenied, ValueError) as exc:
        raise _organizer_error(exc, "folder") from exc


@router.delete(
    "/clients/{client_id}/knowledge/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a knowledge folder; its items stay, in no folder",
)
def delete_knowledge_folder(
    client_id: ClientIdPath,
    folder_id: FolderIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> Response:
    scope = _knowledge_scope(principal, resolver, client_id)
    try:
        ClientKnowledgeRepository(session).delete_folder(scope, folder_id=folder_id)
    except ScopeDenied as exc:
        raise _organizer_error(exc, "folder") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/clients/{client_id}/knowledge/labels",
    response_model=list[KnowledgeLabelResponse],
    summary="The client's knowledge labels",
)
def knowledge_labels(
    client_id: ClientIdPath, principal: PrincipalDep, resolver: ResolverDep, session: SessionDep
) -> list[KnowledgeLabelResponse]:
    scope = _knowledge_scope(principal, resolver, client_id)
    return [_label(lb) for lb in ClientKnowledgeRepository(session).labels(scope)]


@router.post(
    "/clients/{client_id}/knowledge/labels",
    response_model=KnowledgeLabelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a knowledge label",
)
def create_knowledge_label(
    client_id: ClientIdPath,
    body: LabelCreate,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> KnowledgeLabelResponse:
    scope = _knowledge_scope(principal, resolver, client_id)
    try:
        return _label(
            ClientKnowledgeRepository(session).create_label(
                scope, name=body.name, colour=body.colour
            )
        )
    except (OrganizerNameTaken, ScopeDenied, ValueError) as exc:
        raise _organizer_error(exc, "label") from exc


@router.put(
    "/clients/{client_id}/knowledge/labels/{label_id}",
    response_model=KnowledgeLabelResponse,
    summary="Rename or recolour a knowledge label",
)
def change_knowledge_label(
    client_id: ClientIdPath,
    label_id: LabelIdPath,
    body: LabelChange,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> KnowledgeLabelResponse:
    scope = _knowledge_scope(principal, resolver, client_id)
    if body.name is None and body.colour is None:
        raise HTTPException(
            status_code=422, detail={"code": "nothing_to_change", "message": "Name a change."}
        )
    try:
        return _label(
            ClientKnowledgeRepository(session).update_label(
                scope, label_id=label_id, name=body.name, colour=body.colour
            )
        )
    except (OrganizerNameTaken, ScopeDenied, ValueError) as exc:
        raise _organizer_error(exc, "label") from exc


@router.delete(
    "/clients/{client_id}/knowledge/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a knowledge label; it comes off every item",
)
def delete_knowledge_label(
    client_id: ClientIdPath,
    label_id: LabelIdPath,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> Response:
    scope = _knowledge_scope(principal, resolver, client_id)
    try:
        ClientKnowledgeRepository(session).delete_label(scope, label_id=label_id)
    except ScopeDenied as exc:
        raise _organizer_error(exc, "label") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/clients/{client_id}/knowledge/placement",
    response_model=list[KnowledgeItemResponse],
    summary="File knowledge items: folder and labels",
)
def place_knowledge(
    client_id: ClientIdPath,
    body: Placement,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
) -> list[KnowledgeItemResponse]:
    """All or nothing: 404 if any item, the folder or a label is not this client's.

    Writes no knowledge revision; the items come back filed as they are now.
    """
    scope = _knowledge_scope(principal, resolver, client_id)
    folder = body.folder_id if "folder_id" in body.model_fields_set else KEEP_FOLDER
    try:
        placed = ClientKnowledgeRepository(session).place(
            scope,
            item_ids=body.item_ids,
            folder_id=folder,
            add_labels=body.add_labels,
            remove_labels=body.remove_labels,
        )
    except (ScopeDenied, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise HTTPException(
                status_code=422, detail={"code": "invalid_placement", "message": str(exc)}
            ) from exc
        raise _organizer_error(exc, "folder") from exc
    return [_item(i) for i in placed]


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
    summary="Add or edit client knowledge",
)
def propose_knowledge(
    client_id: ClientIdPath,
    body: ProposalCreate,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> ProposalResponse:
    """What a person writes here takes effect now (ADR 0019); the answer is the approved record.

    Only when self-approval is turned off for this client does it come back ``PROPOSED``,
    for someone else to decide. A study's findings are different: they are offered through
    ``/studies/{study_id}/knowledge-proposals`` and always wait for a person.

    A SOURCE, DOCUMENT or DATASET item may name one of this client's sources as
    ``content.source_id`` (C7a); any other source is ``422 unknown_source``.
    """
    scope = _knowledge_scope(principal, resolver, client_id)
    try:
        ref = source_ref(body.kind, body.content)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_proposal", "message": str(exc)}
        ) from exc
    if ref is not None:
        try:
            ClientSourceRepository(session, store).source(scope, ref)
        except ScopeDenied as exc:
            if exc.reason != "unknown_source":
                raise _forbidden(
                    exc.reason, "Your role for this client does not permit adding knowledge."
                ) from exc
            raise HTTPException(
                status_code=422,
                detail={"code": "unknown_source", "message": "No such source for this client."},
            ) from exc
    try:
        proposal = ClientKnowledgeRepository(session).add(
            scope,
            kind=body.kind,
            title=body.title,
            summary=body.summary,
            content=body.content,
            item_id=body.item_id,
            base_revision=body.base_revision,
        )
    except StaleKnowledgeProposal as exc:
        raise _stale(exc) from exc
    except ScopeDenied as exc:
        if exc.reason == "unknown_item":
            raise _not_found() from exc
        raise _forbidden(
            exc.reason, "Your role for this client does not permit adding knowledge."
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
            scope,
            proposal_id=proposal_id,
            approve=body.approve,
            note=body.note,
            reviewed_revision=body.reviewed_revision,
        )
    except StaleKnowledgeProposal as exc:
        raise _stale(exc) from exc
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
# One study: its frame, its working content, what it consumes, what it proposes
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
        content_state=(workspace.state if workspace else ContentState.EMPTY).value,
    )


@router.get(
    "/studies/{study_id}/workspace",
    response_model=StudyWorkspaceResponse,
    summary="One study's frame",
)
def study_workspace(
    scope: StudyScopeDep, repo: ScopeRepositoryDep, session: SessionDep
) -> StudyWorkspaceResponse:
    """The study, its client's name, the caller's role and where its working content stands."""
    return _study_workspace(scope, repo, session)


def _content_response(scope: Any, content: WorkingContent) -> WorkingContentResponse:
    return WorkingContentResponse(
        study_id=content.study_id,
        state=content.state.value,
        revision=content.revision,
        revision_id=content.revision_id,
        content=content.content,
        analysis=content.analysis,
        template=research_template(),
        saved_at=content.saved_at,
        saved_by=content.saved_by,
        can_edit=scope.has(Permission.EDIT_STUDY) and content.state.editable,
        lineage=content.lineage,
    )


@router.get(
    "/studies/{study_id}/workspace/content",
    response_model=WorkingContentResponse,
    summary="The research study's working content",
)
def study_working_content(scope: StudyScopeDep, session: SessionDep) -> WorkingContentResponse:
    """What the stages edit, at its current revision, with the template it is completed with.

    A study with nothing saved is ``EMPTY``; one whose content still waits in 18.6.6
    is ``AWAITING_MIGRATION``; one whose 18.6.6 content was lost is ``UNRECOVERABLE``.
    Each says so, with no content, rather than answering with an empty document.
    """
    return _content_response(scope, StudyWorkspaceRepository(session).content(scope))


@router.put(
    "/studies/{study_id}/workspace/content",
    response_model=WorkingContentSaved,
    summary="Save the research study's working content",
    responses={
        409: {
            "model": ErrorResponse,
            "description": "A newer revision exists, or the content awaits migration",
        }
    },
)
def save_study_working_content(
    body: WorkingContentSave, scope: StudyScopeDep, session: SessionDep
) -> WorkingContentSaved:
    """A new immutable revision, or nothing when nothing changed.

    Needs ``EDIT_STUDY`` on an open research study. ``base_revision`` is the revision
    the content was edited from; a save from an older one is refused with 409
    ``stale_revision`` and the current revision, never applied over it.
    """
    try:
        saved = StudyWorkspaceRepository(session).save(
            scope,
            content=body.content,
            analysis=body.analysis,
            base_revision=body.base_revision,
            reason=body.reason,
        )
    except ScopeDenied as exc:
        raise _forbidden(exc.reason, "Your role on this study does not permit that.") from exc
    except WorkspaceConflict as exc:
        raise _workspace_conflict(exc) from exc
    except WorkspaceRejected as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    return WorkingContentSaved(
        study_id=saved.study_id,
        state=saved.state.value,
        revision=saved.revision,
        revision_id=saved.revision_id,
        deduplicated=saved.deduplicated,
    )


@router.get(
    "/studies/{study_id}/workspace/revisions",
    response_model=WorkingRevisionList,
    summary="The research study's working-content history",
)
def study_working_revisions(
    scope: StudyScopeDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> WorkingRevisionList:
    """Every saved revision, newest first: when, by whom, why, and its content hash."""
    return WorkingRevisionList(
        items=[
            WorkingRevisionResponse(**r.model_dump())
            for r in StudyWorkspaceRepository(session).revisions(scope, limit=limit)
        ]
    )


def _workspace_conflict(exc: WorkspaceConflict) -> HTTPException:
    messages = {
        "awaiting_migration": "The working content awaits migration from 18.6.6.",
        "not_saved": "Save the study's working content before attaching files to it.",
    }
    return HTTPException(
        status_code=409,
        detail={
            "code": exc.reason,
            "message": messages.get(
                exc.reason, "The working content was saved elsewhere since it was loaded."
            ),
            "details": {"current_revision": exc.current_revision},
        },
    )


@router.post(
    "/studies/{study_id}/workspace/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach a file to the research study's brief",
    responses={
        409: {"model": ErrorResponse, "description": "Nothing saved yet, or awaiting migration"},
        422: {"model": ErrorResponse, "description": "Empty, too large, or not base64"},
    },
)
def attach_study_file(
    body: AttachmentUpload, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> AttachmentResponse:
    """Keep the file in AIA's storage and answer with the record the brief keeps.

    Needs ``EDIT_STUDY`` on an open study whose working content has been saved. The
    record's ``context_excerpt`` is the text 18.6.6 would have read of the file;
    ``text_extracted`` is false when none could be read. The brief itself is not
    changed: the stage adds the record and saves.
    """
    try:
        data = base64.b64decode(body.data_b64, validate=True)
    except binascii.Error as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "not_base64", "message": "The file is not valid base64."},
        ) from exc
    try:
        record = StudyWorkspaceRepository(session).attach(
            scope, store, filename=body.filename, data=data
        )
    except ScopeDenied as exc:
        raise _forbidden(exc.reason, "Your role on this study does not permit that.") from exc
    except WorkspaceConflict as exc:
        raise _workspace_conflict(exc) from exc
    except AttachmentRejected as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    return AttachmentResponse(**record.model_dump())


@router.get(
    "/studies/{study_id}/workspace/attachments/{attachment_id}",
    response_class=Response,
    summary="Download a file attached to the research study's brief",
    responses={
        200: {"content": {"application/octet-stream": {}}, "description": "The file"},
        409: {"model": ErrorResponse, "description": "The stored bytes are missing or altered"},
    },
)
def download_study_file(
    attachment_id: AttachmentIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> Response:
    """The file's bytes, for anyone who may read the study; any other id is a 404.

    Always ``application/octet-stream`` and ``attachment``, never rendered in AIA's
    origin, whatever the file claims to be. The bytes are hash-verified on read: a
    mismatch or a missing object marks the file CORRUPT, durably, and answers 409.
    """
    try:
        artifact, data = StudyWorkspaceRepository(session).attachment(scope, store, attachment_id)
    except ArtifactNotFound as exc:
        raise _not_found() from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc
    filename = str(artifact.metadata.get("filename") or "attachment")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post(
    "/studies/{study_id}/workspace/questionnaire-import",
    response_model=QuestionnaireImportResponse,
    summary="Read a filled-in questionnaire template",
    responses={422: {"model": ErrorResponse, "description": "The file does not import"}},
)
def import_study_questionnaire(
    body: QuestionnaireUpload, scope: StudyScopeDep
) -> QuestionnaireImportResponse:
    """The questionnaire in an XLSX or CSV template, as the stage's new sections.

    Nothing is stored: the stage puts the sections on the study's working content and
    saves, as any other edit. Needs ``EDIT_STUDY`` on an open study. A file that breaks
    one of 18.6.6's import rules is refused with its message (422); so is one that
    cannot be read at all (``unreadable``).
    """
    try:
        scope.require(Permission.EDIT_STUDY)
        scope.require_open_study()
    except ScopeDenied as exc:
        raise _forbidden(exc.reason, "Your role on this study does not permit that.") from exc
    try:
        data = base64.b64decode(body.data_b64, validate=True)
    except binascii.Error as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "not_base64", "message": "The file is not valid base64."},
        ) from exc
    try:
        imported = import_questionnaire(data, body.filename)
    except QuestionnaireImportRejected as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    return QuestionnaireImportResponse(
        sections=imported.sections,
        summary=ImportSummaryResponse(**imported.summary.model_dump()),
        filename=imported.filename,
    )


@router.get(
    "/studies/{study_id}/workspace/questionnaire-template",
    response_class=Response,
    summary="The questionnaire template, as an XLSX workbook",
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
            "description": "The template",
        }
    },
)
def study_questionnaire_template(scope: StudyScopeDep) -> Response:
    """AIA's template: sheet DOTAZNIK with three example rows, sheet NAVOD with the guide."""
    return Response(
        content=template_xlsx(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{TEMPLATE_FILENAME}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


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
            base_revision=body.base_revision,
        )
    except StaleKnowledgeProposal as exc:
        raise _stale(exc) from exc
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
