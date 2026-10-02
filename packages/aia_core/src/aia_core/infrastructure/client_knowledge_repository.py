"""Persistence for Client Knowledge (ADR 0015 decision 7).

The only module that touches the knowledge tables (`make layer_check`). Every
read and write takes an issued scope -- a ``ClientContext`` for the client's
own workspace, a ``StudyContext`` for what a study consumes or proposes -- and
the scope is in the query itself. There is no unscoped search to filter
afterwards: retrieval resolves the client first.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..domain.knowledge import (
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeProposal,
    KnowledgeRevision,
    KnowledgeSummary,
    ProposalOrigin,
    ProposalStatus,
    new_knowledge_item_id,
    new_knowledge_proposal_id,
)
from ..domain.scope import (
    ClientContext,
    ClientPermission,
    Permission,
    ScopeDenied,
    SeparationOfDutiesViolation,
    StudyContext,
)
from .tables import (
    AccessAuditRow,
    ClientKnowledgeItemRow,
    ClientKnowledgeProposalRow,
    ClientKnowledgeRevisionRow,
    as_utc,
    utcnow,
)

__all__ = ["ClientKnowledgeRepository"]

_MAX_RESULTS = 200


def _client(scope: object) -> ClientContext:
    # Defence in depth beyond the annotations: an OrganizationContext, a dict or
    # anything else that is not an issued ClientContext is refused outright.
    if not isinstance(scope, ClientContext):
        raise ScopeDenied("client knowledge requires a client context", reason="forged_scope")
    return scope


def _study(scope: object) -> StudyContext:
    if not isinstance(scope, StudyContext):
        raise ScopeDenied("study knowledge requires a study context", reason="forged_scope")
    return scope


def _item(row: ClientKnowledgeItemRow) -> KnowledgeItem:
    return KnowledgeItem(
        item_id=row.item_id,
        client_id=row.client_id,
        kind=KnowledgeKind(row.kind),
        title=row.title,
        summary=row.summary,
        content=dict(row.content or {}),
        revision=row.current_revision,
        modified_at=as_utc(row.modified_at),
    )


def _proposal(row: ClientKnowledgeProposalRow) -> KnowledgeProposal:
    return KnowledgeProposal(
        proposal_id=row.proposal_id,
        client_id=row.client_id,
        origin=ProposalOrigin.STUDY if row.study_id else ProposalOrigin.CLIENT,
        study_id=row.study_id,
        item_id=row.item_id,
        kind=KnowledgeKind(row.kind),
        title=row.title,
        summary=row.summary,
        content=dict(row.content or {}),
        provenance=dict(row.provenance or {}),
        status=ProposalStatus(row.status),
        proposed_by=row.proposed_by,
        proposed_at=as_utc(row.proposed_at),
        decided_by=row.decided_by,
        decided_at=as_utc(row.decided_at) if row.decided_at else None,
        decision_note=row.decision_note,
        revision=row.revision,
    )


def _revision(row: ClientKnowledgeRevisionRow) -> KnowledgeRevision:
    return KnowledgeRevision(
        item_id=row.item_id,
        revision=row.revision,
        context_revision=row.context_revision,
        title=row.title,
        summary=row.summary,
        content=dict(row.content or {}),
        provenance=dict(row.provenance or {}),
        proposal_id=row.proposal_id,
        approved_by=row.approved_by,
        approved_at=as_utc(row.approved_at),
    )


class ClientKnowledgeRepository:
    """Reads, proposals and decisions over one client's knowledge.

    The caller owns the transaction.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ reads

    def _approved(
        self,
        organization_id: str,
        client_id: str,
        kinds: Iterable[KnowledgeKind] | None,
        text: str | None,
    ) -> list[KnowledgeItem]:
        stmt = select(ClientKnowledgeItemRow).where(
            ClientKnowledgeItemRow.organization_id == organization_id,
            ClientKnowledgeItemRow.client_id == client_id,
            ClientKnowledgeItemRow.status == "ACTIVE",
        )
        kind_values = [k.value for k in kinds] if kinds is not None else None
        if kind_values is not None:
            stmt = stmt.where(ClientKnowledgeItemRow.kind.in_(kind_values))
        if text:
            needle = f"%{text.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(ClientKnowledgeItemRow.title).like(needle),
                    func.lower(ClientKnowledgeItemRow.summary).like(needle),
                )
            )
        rows = self._session.scalars(
            stmt.order_by(ClientKnowledgeItemRow.modified_at.desc()).limit(_MAX_RESULTS)
        ).all()
        return [_item(r) for r in rows]

    def items(
        self,
        scope: ClientContext,
        *,
        kinds: Iterable[KnowledgeKind] | None = None,
        text: str | None = None,
    ) -> list[KnowledgeItem]:
        """The client's approved knowledge. Needs a client-level grant."""
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        return self._approved(scope.organization_id, scope.client_id, kinds, text)

    def for_study(
        self,
        scope: StudyContext,
        *,
        kinds: Iterable[KnowledgeKind] | None = None,
        text: str | None = None,
    ) -> list[KnowledgeItem]:
        """What a study inherits: its own client's approved knowledge, never another's.

        The client comes from the study's scope (the study row), not from any
        argument, so retrieval for a study cannot be pointed at another client.
        """
        scope = _study(scope)
        scope.require(Permission.VIEW_STUDY)
        return self._approved(scope.organization_id, scope.client_id, kinds, text)

    def revisions(self, scope: ClientContext, *, item_id: str) -> list[KnowledgeRevision]:
        """An item's revision history, oldest first; empty when the item is not this client's."""
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        rows = self._session.scalars(
            select(ClientKnowledgeRevisionRow)
            .where(
                ClientKnowledgeRevisionRow.item_id == item_id,
                ClientKnowledgeRevisionRow.organization_id == scope.organization_id,
                ClientKnowledgeRevisionRow.client_id == scope.client_id,
            )
            .order_by(ClientKnowledgeRevisionRow.revision)
        ).all()
        return [_revision(r) for r in rows]

    def proposals(
        self, scope: ClientContext, *, status: ProposalStatus | None = None
    ) -> list[KnowledgeProposal]:
        """The client's proposals, newest first."""
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        stmt = select(ClientKnowledgeProposalRow).where(
            ClientKnowledgeProposalRow.organization_id == scope.organization_id,
            ClientKnowledgeProposalRow.client_id == scope.client_id,
        )
        if status is not None:
            stmt = stmt.where(ClientKnowledgeProposalRow.status == status.value)
        rows = self._session.scalars(
            stmt.order_by(ClientKnowledgeProposalRow.proposed_at.desc()).limit(_MAX_RESULTS)
        ).all()
        return [_proposal(r) for r in rows]

    def summary(self, scope: ClientContext) -> KnowledgeSummary:
        """Counts, pending proposals and the knowledge revision, for the overview."""
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        counts = self._session.execute(
            select(ClientKnowledgeItemRow.kind, func.count())
            .where(
                ClientKnowledgeItemRow.organization_id == scope.organization_id,
                ClientKnowledgeItemRow.client_id == scope.client_id,
                ClientKnowledgeItemRow.status == "ACTIVE",
            )
            .group_by(ClientKnowledgeItemRow.kind)
        ).all()
        pending = self._session.scalar(
            select(func.count()).where(
                ClientKnowledgeProposalRow.organization_id == scope.organization_id,
                ClientKnowledgeProposalRow.client_id == scope.client_id,
                ClientKnowledgeProposalRow.status == ProposalStatus.PROPOSED.value,
            )
        )
        last = self._session.execute(
            select(
                func.max(ClientKnowledgeRevisionRow.context_revision),
                func.max(ClientKnowledgeRevisionRow.approved_at),
            ).where(
                ClientKnowledgeRevisionRow.organization_id == scope.organization_id,
                ClientKnowledgeRevisionRow.client_id == scope.client_id,
            )
        ).one()
        return KnowledgeSummary(
            context_revision=int(last[0] or 0),
            items_by_kind={KnowledgeKind(kind): int(n) for kind, n in counts},
            pending_proposals=int(pending or 0),
            last_approved_at=as_utc(last[1]) if last[1] else None,
        )

    # -------------------------------------------------------------- proposals

    def _add_proposal(
        self,
        *,
        organization_id: str,
        client_id: str,
        study_id: str | None,
        actor_id: str,
        kind: KnowledgeKind,
        title: str,
        summary: str,
        content: dict[str, Any],
        provenance: dict[str, Any],
        item_id: str | None,
    ) -> KnowledgeProposal:
        if not title.strip():
            raise ValueError("a proposal needs a title")
        if item_id is not None:
            target = self._session.scalar(
                select(ClientKnowledgeItemRow).where(
                    ClientKnowledgeItemRow.item_id == item_id,
                    ClientKnowledgeItemRow.organization_id == organization_id,
                    ClientKnowledgeItemRow.client_id == client_id,
                )
            )
            if target is None:
                raise ScopeDenied("not found", reason="unknown_item")
            if target.kind != kind.value:
                raise ValueError("a revision keeps the item's kind")
        row = ClientKnowledgeProposalRow(
            proposal_id=new_knowledge_proposal_id(),
            organization_id=organization_id,
            client_id=client_id,
            study_id=study_id,
            item_id=item_id,
            kind=kind.value,
            title=title.strip(),
            summary=summary,
            content=content,
            provenance=provenance,
            status=ProposalStatus.PROPOSED.value,
            proposed_by=actor_id,
            proposed_at=utcnow(),
        )
        self._session.add(row)
        self._session.flush()
        return _proposal(row)

    def propose_from_study(
        self,
        scope: StudyContext,
        *,
        kind: KnowledgeKind,
        title: str,
        summary: str = "",
        content: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        item_id: str | None = None,
    ) -> KnowledgeProposal:
        """A study offers a finding for reuse. Changes nothing until someone approves it."""
        scope = _study(scope)
        scope.require(Permission.EDIT_STUDY)
        return self._add_proposal(
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            study_id=scope.study_id,
            actor_id=scope.actor_id,
            kind=kind,
            title=title,
            summary=summary,
            content=content or {},
            provenance={**(provenance or {}), "study_id": scope.study_id},
            item_id=item_id,
        )

    def propose(
        self,
        scope: ClientContext,
        *,
        kind: KnowledgeKind,
        title: str,
        summary: str = "",
        content: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        item_id: str | None = None,
    ) -> KnowledgeProposal:
        """A proposal made in the client workspace itself (a source added, a term defined)."""
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        return self._add_proposal(
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            study_id=None,
            actor_id=scope.actor_id,
            kind=kind,
            title=title,
            summary=summary,
            content=content or {},
            provenance=provenance or {},
            item_id=item_id,
        )

    # --------------------------------------------------------------- decisions

    def decide(
        self, scope: ClientContext, *, proposal_id: str, approve: bool, note: str = ""
    ) -> KnowledgeProposal:
        """Approve or reject a proposal. An approval appends a revision and a knowledge revision.

        Needs ``APPROVE_CLIENT_KNOWLEDGE``; the proposer may not decide their own
        proposal unless self-approval is allowed at the client's scope.
        """
        scope = _client(scope)
        scope.require(ClientPermission.APPROVE_CLIENT_KNOWLEDGE)
        row = self._session.scalar(
            select(ClientKnowledgeProposalRow)
            .where(
                ClientKnowledgeProposalRow.proposal_id == proposal_id,
                ClientKnowledgeProposalRow.organization_id == scope.organization_id,
                ClientKnowledgeProposalRow.client_id == scope.client_id,
            )
            .with_for_update()
        )
        if row is None:
            raise ScopeDenied("not found", reason="unknown_proposal")
        if row.status != ProposalStatus.PROPOSED.value:
            raise ValueError("this proposal has already been decided")
        if row.proposed_by == scope.actor_id and not scope.self_approval.allowed:
            raise SeparationOfDutiesViolation(scope.actor_id, what="this proposal")

        return self._settle(
            scope, row, approve=approve, note=note, action="CLIENT_KNOWLEDGE_DECIDED"
        )

    def add(
        self,
        scope: ClientContext,
        *,
        kind: KnowledgeKind,
        title: str,
        summary: str = "",
        content: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        item_id: str | None = None,
    ) -> KnowledgeProposal:
        """A person adds or edits knowledge in the client workspace; it takes effect now.

        ADR 0019 decision 3: no approval between people. Only what an AI produced
        waits for a person's accept, and that comes through :meth:`propose_from_study`.
        The write still goes through a proposal row, already approved, so the
        revision keeps the same lineage and the audit says who wrote it.

        Where the client, study or organization has turned self-approval *off*, the
        owner asked for independent review: this then files an ordinary proposal for
        someone else to decide, as before. Needs both knowledge permissions -- the
        two a person needed to get the same change in before.
        """
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        scope.require(ClientPermission.APPROVE_CLIENT_KNOWLEDGE)
        if not scope.self_approval.allowed:
            return self.propose(
                scope,
                kind=kind,
                title=title,
                summary=summary,
                content=content,
                provenance=provenance,
                item_id=item_id,
            )
        proposal = self._add_proposal(
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            study_id=None,
            actor_id=scope.actor_id,
            kind=kind,
            title=title,
            summary=summary,
            content=content or {},
            provenance={**(provenance or {}), "authored": "person"},
            item_id=item_id,
        )
        row = self._session.scalar(
            select(ClientKnowledgeProposalRow)
            .where(ClientKnowledgeProposalRow.proposal_id == proposal.proposal_id)
            .with_for_update()
        )
        assert row is not None  # flushed by _add_proposal in this transaction
        return self._settle(
            scope,
            row,
            approve=True,
            note="written by a person",
            action="CLIENT_KNOWLEDGE_AUTHORED",
        )

    def _settle(
        self,
        scope: ClientContext,
        row: ClientKnowledgeProposalRow,
        *,
        approve: bool,
        note: str,
        action: str,
    ) -> KnowledgeProposal:
        """Record the decision on a proposal row and, if approved, apply it."""
        now = utcnow()
        row.decided_by = scope.actor_id
        row.decided_at = now
        row.decision_note = note
        if not approve:
            row.status = ProposalStatus.REJECTED.value
        else:
            row.status = ProposalStatus.APPROVED.value
            row.revision = self._apply(scope, row, now)
        self._session.add(
            AccessAuditRow(
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                study_id=row.study_id,
                actor_id=scope.actor_id,
                action=action,
                reason=row.status,
                payload={
                    "proposal_id": row.proposal_id,
                    "item_id": row.item_id,
                    "revision": row.revision,
                },
                request_id=scope.request_id,
            )
        )
        self._session.flush()
        return _proposal(row)

    def _apply(self, scope: ClientContext, proposal: ClientKnowledgeProposalRow, now: Any) -> int:
        context_revision = 1 + int(
            self._session.scalar(
                select(func.max(ClientKnowledgeRevisionRow.context_revision)).where(
                    ClientKnowledgeRevisionRow.client_id == scope.client_id
                )
            )
            or 0
        )
        if proposal.item_id is None:
            item = ClientKnowledgeItemRow(
                item_id=new_knowledge_item_id(),
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                kind=proposal.kind,
                title=proposal.title,
                summary=proposal.summary,
                content=proposal.content,
                current_revision=1,
                created_at=now,
                modified_at=now,
            )
            self._session.add(item)
            self._session.flush()
            proposal.item_id = item.item_id
            revision = 1
        else:
            existing = self._session.scalar(
                select(ClientKnowledgeItemRow)
                .where(
                    ClientKnowledgeItemRow.item_id == proposal.item_id,
                    ClientKnowledgeItemRow.client_id == scope.client_id,
                )
                .with_for_update()
            )
            if existing is None:
                raise ScopeDenied("not found", reason="unknown_item")
            item = existing
            revision = item.current_revision + 1
            item.title = proposal.title
            item.summary = proposal.summary
            item.content = proposal.content
            item.current_revision = revision
            item.modified_at = now
        self._session.add(
            ClientKnowledgeRevisionRow(
                item_id=proposal.item_id,
                revision=revision,
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                context_revision=context_revision,
                title=proposal.title,
                summary=proposal.summary,
                content=proposal.content,
                provenance={
                    **(proposal.provenance or {}),
                    "origin": (
                        ProposalOrigin.STUDY if proposal.study_id else ProposalOrigin.CLIENT
                    ).value,
                    "proposal_id": proposal.proposal_id,
                    "proposed_by": proposal.proposed_by,
                },
                proposal_id=proposal.proposal_id,
                approved_by=scope.actor_id,
                approved_at=now,
            )
        )
        return revision
