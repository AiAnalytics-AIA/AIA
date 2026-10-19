"""Persistence for Client Knowledge (ADR 0015 decision 7).

The only module that touches the knowledge tables (`make layer_check`). Every
read and write takes an issued scope -- a ``ClientContext`` for the client's
own workspace, a ``StudyContext`` for what a study consumes or proposes -- and
the scope is in the query itself. There is no unscoped search to filter
afterwards: retrieval resolves the client first.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal, cast

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ..domain.knowledge import (
    STALE_AFTER,
    KnowledgeFolder,
    KnowledgeHealth,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeLabel,
    KnowledgeProposal,
    KnowledgeRevision,
    KnowledgeSummary,
    LabelColour,
    OrganizerNameTaken,
    ProposalDraft,
    ProposalOrigin,
    ProposalStatus,
    StaleKnowledgeProposal,
    new_knowledge_folder_id,
    new_knowledge_item_id,
    new_knowledge_label_id,
    new_knowledge_proposal_id,
    organizer_key,
    organizer_name,
    source_ref,
)
from ..domain.scope import (
    ClientContext,
    ClientPermission,
    ClientWorkContext,
    Permission,
    ScopeDenied,
    SeparationOfDutiesViolation,
    StudyContext,
)
from .tables import (
    AccessAuditRow,
    ClientKnowledgeFolderRow,
    ClientKnowledgeItemFolderRow,
    ClientKnowledgeItemLabelRow,
    ClientKnowledgeItemRow,
    ClientKnowledgeLabelRow,
    ClientKnowledgeProposalRow,
    ClientKnowledgeRevisionRow,
    ClientRow,
    as_utc,
    utcnow,
)

__all__ = ["KEEP_FOLDER", "ClientKnowledgeRepository", "SourceAdded"]

_MAX_RESULTS = 200
#: The most items one placement may move or label at once.
_MAX_PLACED = 200


class _KeepFolder:
    """The placement leaves each item's folder as it is."""

    def __repr__(self) -> str:
        return "KEEP_FOLDER"


KEEP_FOLDER: Final = _KeepFolder()


@dataclass(frozen=True, slots=True)
class SourceAdded:
    """What one "add this checked source" did: ``added`` (knowledge now), ``proposed`` (the
    client turned self-approval off) or ``exists`` (the client already holds or awaits a
    source at that URL; nothing was written). ``item_id`` is the item, when there is one."""

    status: Literal["added", "proposed", "exists"]
    item_id: str | None
    proposal_id: str | None


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
        base_revision=row.base_revision,
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
        *,
        conditions: Sequence[Any] = (),
    ) -> list[KnowledgeItem]:
        stmt = select(ClientKnowledgeItemRow).where(
            ClientKnowledgeItemRow.organization_id == organization_id,
            ClientKnowledgeItemRow.client_id == client_id,
            ClientKnowledgeItemRow.status == "ACTIVE",
            *conditions,
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
        folder_id: str | None = None,
        unfiled: bool = False,
        label_id: str | None = None,
    ) -> list[KnowledgeItem]:
        """The client's approved knowledge, with where people filed it. Needs a client-level grant.

        ``folder_id`` keeps the items in that folder, ``unfiled`` those in none,
        ``label_id`` those carrying that label. A folder or label of another
        client matches nothing. Only this workspace read carries the folder and
        labels: what a study reads (:meth:`for_study`) never does.
        """
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        filed = select(ClientKnowledgeItemFolderRow.item_id).where(
            ClientKnowledgeItemFolderRow.client_id == scope.client_id
        )
        conditions: list[Any] = []
        if folder_id is not None:
            conditions.append(
                ClientKnowledgeItemRow.item_id.in_(
                    filed.where(ClientKnowledgeItemFolderRow.folder_id == folder_id)
                )
            )
        if unfiled:
            conditions.append(ClientKnowledgeItemRow.item_id.not_in(filed))
        if label_id is not None:
            conditions.append(
                ClientKnowledgeItemRow.item_id.in_(
                    select(ClientKnowledgeItemLabelRow.item_id).where(
                        ClientKnowledgeItemLabelRow.client_id == scope.client_id,
                        ClientKnowledgeItemLabelRow.label_id == label_id,
                    )
                )
            )
        found = self._approved(
            scope.organization_id, scope.client_id, kinds, text, conditions=conditions
        )
        return self._with_placement(scope, found)

    def _with_placement(
        self, scope: ClientContext, items: list[KnowledgeItem]
    ) -> list[KnowledgeItem]:
        if not items:
            return items
        ids = [i.item_id for i in items]
        folders = dict(
            self._session.execute(
                select(
                    ClientKnowledgeItemFolderRow.item_id, ClientKnowledgeItemFolderRow.folder_id
                ).where(
                    ClientKnowledgeItemFolderRow.client_id == scope.client_id,
                    ClientKnowledgeItemFolderRow.item_id.in_(ids),
                )
            ).all()
        )
        labels: dict[str, list[str]] = {}
        for item_id, label in self._session.execute(
            select(ClientKnowledgeItemLabelRow.item_id, ClientKnowledgeItemLabelRow.label_id)
            .where(
                ClientKnowledgeItemLabelRow.client_id == scope.client_id,
                ClientKnowledgeItemLabelRow.item_id.in_(ids),
            )
            .order_by(ClientKnowledgeItemLabelRow.label_id)
        ).all():
            labels.setdefault(item_id, []).append(label)
        return [
            i.model_copy(
                update={
                    "folder_id": folders.get(i.item_id),
                    "label_ids": tuple(labels.get(i.item_id, ())),
                }
            )
            for i in items
        ]

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

    def proposal_counts_by_study(
        self, scope: ClientContext
    ) -> dict[str, dict[ProposalStatus, int]]:
        """How many proposals each of the client's studies made, by status.

        What a study brought into the client's knowledge, for the studies list.
        A study that proposed nothing is absent, not zero.
        """
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        rows = self._session.execute(
            select(
                ClientKnowledgeProposalRow.study_id,
                ClientKnowledgeProposalRow.status,
                func.count(),
            )
            .where(
                ClientKnowledgeProposalRow.organization_id == scope.organization_id,
                ClientKnowledgeProposalRow.client_id == scope.client_id,
                ClientKnowledgeProposalRow.study_id.is_not(None),
            )
            .group_by(ClientKnowledgeProposalRow.study_id, ClientKnowledgeProposalRow.status)
        ).all()
        counts: dict[str, dict[ProposalStatus, int]] = {}
        for study_id, status, n in rows:
            counts.setdefault(str(study_id), {})[ProposalStatus(status)] = int(n)
        return counts

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

    # ----------------------------------------------------------- organization
    #
    # Folders and labels are the people's way of filing the client's knowledge
    # (client-workspace D4). Whoever may propose knowledge may organize it; no
    # change here writes a revision or moves the client's knowledge revision.
    # Each change is audited.

    def _audit(self, scope: ClientContext, action: str, payload: dict[str, Any]) -> None:
        self._session.add(
            AccessAuditRow(
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                actor_id=scope.actor_id,
                action=action,
                reason="",
                payload=payload,
                request_id=scope.request_id,
            )
        )

    def _active_counts(self, scope: ClientContext, column: Any, link: Any) -> dict[str, int]:
        rows = self._session.execute(
            select(column, func.count())
            .select_from(link)
            .join(ClientKnowledgeItemRow, ClientKnowledgeItemRow.item_id == link.item_id)
            .where(link.client_id == scope.client_id, ClientKnowledgeItemRow.status == "ACTIVE")
            .group_by(column)
        ).all()
        return {str(k): int(cast(int, n)) for k, n in rows}

    def folders(self, scope: ClientContext) -> list[KnowledgeFolder]:
        """The client's folders by name, each with how many of its active items it holds."""
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        rows = self._session.scalars(
            select(ClientKnowledgeFolderRow).where(
                ClientKnowledgeFolderRow.organization_id == scope.organization_id,
                ClientKnowledgeFolderRow.client_id == scope.client_id,
            )
        ).all()
        counts = self._active_counts(
            scope, ClientKnowledgeItemFolderRow.folder_id, ClientKnowledgeItemFolderRow
        )
        return sorted(
            (
                KnowledgeFolder(
                    folder_id=r.folder_id,
                    client_id=r.client_id,
                    name=r.name,
                    item_count=counts.get(r.folder_id, 0),
                )
                for r in rows
            ),
            key=lambda f: f.name.casefold(),
        )

    def _folder_row(self, scope: ClientContext, folder_id: str) -> ClientKnowledgeFolderRow:
        row = self._session.scalar(
            select(ClientKnowledgeFolderRow).where(
                ClientKnowledgeFolderRow.folder_id == folder_id,
                ClientKnowledgeFolderRow.organization_id == scope.organization_id,
                ClientKnowledgeFolderRow.client_id == scope.client_id,
            )
        )
        if row is None:
            raise ScopeDenied("not found", reason="unknown_folder")
        return row

    def _name_free(self, scope: ClientContext, table: Any, key: str, own_id: str | None) -> None:
        id_column = table.folder_id if table is ClientKnowledgeFolderRow else table.label_id
        clash = self._session.scalar(
            select(id_column).where(
                table.client_id == scope.client_id,
                table.name_key == key,
                *([id_column != own_id] if own_id else []),
            )
        )
        if clash is not None:
            raise OrganizerNameTaken(key)

    def create_folder(self, scope: ClientContext, *, name: str) -> KnowledgeFolder:
        """A new, empty folder. ``OrganizerNameTaken`` when the client has one by that name."""
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        cleaned, key = organizer_name(name), organizer_key(name)
        self._name_free(scope, ClientKnowledgeFolderRow, key, None)
        row = ClientKnowledgeFolderRow(
            folder_id=new_knowledge_folder_id(),
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            name=cleaned,
            name_key=key,
            created_by=scope.actor_id,
            created_at=utcnow(),
        )
        self._session.add(row)
        self._audit(
            scope, "CLIENT_KNOWLEDGE_FOLDER_CREATED", {"folder_id": row.folder_id, "name": cleaned}
        )
        self._session.flush()
        return KnowledgeFolder(folder_id=row.folder_id, client_id=row.client_id, name=row.name)

    def rename_folder(self, scope: ClientContext, *, folder_id: str, name: str) -> KnowledgeFolder:
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        row = self._folder_row(scope, folder_id)
        cleaned, key = organizer_name(name), organizer_key(name)
        self._name_free(scope, ClientKnowledgeFolderRow, key, folder_id)
        before = row.name
        row.name, row.name_key = cleaned, key
        self._audit(
            scope,
            "CLIENT_KNOWLEDGE_FOLDER_RENAMED",
            {"folder_id": folder_id, "from": before, "to": cleaned},
        )
        self._session.flush()
        return next(f for f in self.folders(scope) if f.folder_id == folder_id)

    def delete_folder(self, scope: ClientContext, *, folder_id: str) -> None:
        """Delete a folder. Its items stay, in no folder; nothing about them changes."""
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        row = self._folder_row(scope, folder_id)
        self._session.execute(
            delete(ClientKnowledgeItemFolderRow).where(
                ClientKnowledgeItemFolderRow.folder_id == folder_id
            )
        )
        self._audit(
            scope, "CLIENT_KNOWLEDGE_FOLDER_DELETED", {"folder_id": folder_id, "name": row.name}
        )
        self._session.delete(row)
        self._session.flush()

    def labels(self, scope: ClientContext) -> list[KnowledgeLabel]:
        """The client's labels by name, each with how many of its active items carry it."""
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        rows = self._session.scalars(
            select(ClientKnowledgeLabelRow).where(
                ClientKnowledgeLabelRow.organization_id == scope.organization_id,
                ClientKnowledgeLabelRow.client_id == scope.client_id,
            )
        ).all()
        counts = self._active_counts(
            scope, ClientKnowledgeItemLabelRow.label_id, ClientKnowledgeItemLabelRow
        )
        return sorted(
            (
                KnowledgeLabel(
                    label_id=r.label_id,
                    client_id=r.client_id,
                    name=r.name,
                    colour=LabelColour(r.colour),
                    item_count=counts.get(r.label_id, 0),
                )
                for r in rows
            ),
            key=lambda lb: lb.name.casefold(),
        )

    def _label_row(self, scope: ClientContext, label_id: str) -> ClientKnowledgeLabelRow:
        row = self._session.scalar(
            select(ClientKnowledgeLabelRow).where(
                ClientKnowledgeLabelRow.label_id == label_id,
                ClientKnowledgeLabelRow.organization_id == scope.organization_id,
                ClientKnowledgeLabelRow.client_id == scope.client_id,
            )
        )
        if row is None:
            raise ScopeDenied("not found", reason="unknown_label")
        return row

    def create_label(
        self, scope: ClientContext, *, name: str, colour: LabelColour
    ) -> KnowledgeLabel:
        """A new label. ``OrganizerNameTaken`` when the client has one by that name."""
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        cleaned, key = organizer_name(name), organizer_key(name)
        colour = LabelColour(colour)
        self._name_free(scope, ClientKnowledgeLabelRow, key, None)
        row = ClientKnowledgeLabelRow(
            label_id=new_knowledge_label_id(),
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            name=cleaned,
            name_key=key,
            colour=colour.value,
            created_by=scope.actor_id,
            created_at=utcnow(),
        )
        self._session.add(row)
        self._audit(
            scope,
            "CLIENT_KNOWLEDGE_LABEL_CREATED",
            {"label_id": row.label_id, "name": cleaned, "colour": colour.value},
        )
        self._session.flush()
        return KnowledgeLabel(
            label_id=row.label_id, client_id=row.client_id, name=row.name, colour=colour
        )

    def update_label(
        self,
        scope: ClientContext,
        *,
        label_id: str,
        name: str | None = None,
        colour: LabelColour | None = None,
    ) -> KnowledgeLabel:
        """Rename a label, recolour it, or both."""
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        row = self._label_row(scope, label_id)
        before = {"name": row.name, "colour": row.colour}
        if name is not None:
            cleaned, key = organizer_name(name), organizer_key(name)
            self._name_free(scope, ClientKnowledgeLabelRow, key, label_id)
            row.name, row.name_key = cleaned, key
        if colour is not None:
            row.colour = LabelColour(colour).value
        self._audit(
            scope,
            "CLIENT_KNOWLEDGE_LABEL_CHANGED",
            {"label_id": label_id, "from": before, "to": {"name": row.name, "colour": row.colour}},
        )
        self._session.flush()
        return next(lb for lb in self.labels(scope) if lb.label_id == label_id)

    def delete_label(self, scope: ClientContext, *, label_id: str) -> None:
        """Delete a label; it comes off every item that carried it, and nothing else changes."""
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        row = self._label_row(scope, label_id)
        self._session.execute(
            delete(ClientKnowledgeItemLabelRow).where(
                ClientKnowledgeItemLabelRow.label_id == label_id
            )
        )
        self._audit(
            scope, "CLIENT_KNOWLEDGE_LABEL_DELETED", {"label_id": label_id, "name": row.name}
        )
        self._session.delete(row)
        self._session.flush()

    def place(
        self,
        scope: ClientContext,
        *,
        item_ids: Sequence[str],
        folder_id: str | _KeepFolder | None = KEEP_FOLDER,
        add_labels: Sequence[str] = (),
        remove_labels: Sequence[str] = (),
    ) -> list[KnowledgeItem]:
        """File items: into a folder (``None``: out of any), and labels on and off.

        All or nothing: every item, the folder and every label must be this
        client's, or nothing changes (``ScopeDenied``). A label both added and
        removed is refused (``ValueError``). Writes no revision; the items'
        ``modified_at`` does not move. Returns the items as they are filed now.
        """
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        ids = list(dict.fromkeys(item_ids))
        if not ids:
            raise ValueError("name at least one item")
        if len(ids) > _MAX_PLACED:
            raise ValueError(f"at most {_MAX_PLACED} items at once")
        adding, removing = list(dict.fromkeys(add_labels)), list(dict.fromkeys(remove_labels))
        if set(adding) & set(removing):
            raise ValueError("a label cannot be added and removed at once")
        found = set(
            self._session.scalars(
                select(ClientKnowledgeItemRow.item_id).where(
                    ClientKnowledgeItemRow.organization_id == scope.organization_id,
                    ClientKnowledgeItemRow.client_id == scope.client_id,
                    ClientKnowledgeItemRow.item_id.in_(ids),
                )
            ).all()
        )
        if found != set(ids):
            raise ScopeDenied("not found", reason="unknown_item")
        if isinstance(folder_id, str):
            self._folder_row(scope, folder_id)
        for label in [*adding, *removing]:
            self._label_row(scope, label)

        if not isinstance(folder_id, _KeepFolder):
            self._session.execute(
                delete(ClientKnowledgeItemFolderRow).where(
                    ClientKnowledgeItemFolderRow.client_id == scope.client_id,
                    ClientKnowledgeItemFolderRow.item_id.in_(ids),
                )
            )
            if folder_id is not None:
                self._session.add_all(
                    ClientKnowledgeItemFolderRow(
                        item_id=i, folder_id=folder_id, client_id=scope.client_id
                    )
                    for i in ids
                )
        if removing:
            self._session.execute(
                delete(ClientKnowledgeItemLabelRow).where(
                    ClientKnowledgeItemLabelRow.client_id == scope.client_id,
                    ClientKnowledgeItemLabelRow.item_id.in_(ids),
                    ClientKnowledgeItemLabelRow.label_id.in_(removing),
                )
            )
        if adding:
            have = set(
                self._session.execute(
                    select(
                        ClientKnowledgeItemLabelRow.item_id, ClientKnowledgeItemLabelRow.label_id
                    ).where(
                        ClientKnowledgeItemLabelRow.client_id == scope.client_id,
                        ClientKnowledgeItemLabelRow.item_id.in_(ids),
                        ClientKnowledgeItemLabelRow.label_id.in_(adding),
                    )
                ).all()
            )
            self._session.add_all(
                ClientKnowledgeItemLabelRow(item_id=i, label_id=lb, client_id=scope.client_id)
                for i in ids
                for lb in adding
                if (i, lb) not in have
            )
        self._audit(
            scope,
            "CLIENT_KNOWLEDGE_ORGANIZED",
            {
                "item_ids": ids,
                "folder_id": None if isinstance(folder_id, _KeepFolder) else folder_id,
                "folder_changed": not isinstance(folder_id, _KeepFolder),
                "add_labels": adding,
                "remove_labels": removing,
            },
        )
        self._session.flush()
        rows = self._session.scalars(
            select(ClientKnowledgeItemRow).where(ClientKnowledgeItemRow.item_id.in_(ids))
        ).all()
        by_id = {r.item_id: _item(r) for r in rows}
        return self._with_placement(scope, [by_id[i] for i in ids])

    # --------------------------------------------------------------- overview

    def health(self, scope: ClientContext, *, now: datetime) -> KnowledgeHealth:
        """How many active items have gone unchanged for a year, and how many are in no folder."""
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        active = (
            ClientKnowledgeItemRow.organization_id == scope.organization_id,
            ClientKnowledgeItemRow.client_id == scope.client_id,
            ClientKnowledgeItemRow.status == "ACTIVE",
        )
        stale = self._session.scalar(
            select(func.count()).where(
                *active, ClientKnowledgeItemRow.modified_at < now - STALE_AFTER
            )
        )
        unfiled = self._session.scalar(
            select(func.count()).where(
                *active,
                ClientKnowledgeItemRow.item_id.not_in(
                    select(ClientKnowledgeItemFolderRow.item_id).where(
                        ClientKnowledgeItemFolderRow.client_id == scope.client_id
                    )
                ),
            )
        )
        return KnowledgeHealth(stale=int(stale or 0), unfiled=int(unfiled or 0))

    def recent_revisions(self, scope: ClientContext, *, limit: int = 8) -> list[KnowledgeRevision]:
        """The client's latest knowledge revisions, newest first: what changed and how."""
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
        rows = self._session.scalars(
            select(ClientKnowledgeRevisionRow)
            .where(
                ClientKnowledgeRevisionRow.organization_id == scope.organization_id,
                ClientKnowledgeRevisionRow.client_id == scope.client_id,
            )
            .order_by(ClientKnowledgeRevisionRow.context_revision.desc())
            .limit(max(1, min(limit, 50)))
        ).all()
        return [_revision(r) for r in rows]

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
        base_revision: int | None,
        run_id: str | None = None,
    ) -> KnowledgeProposal:
        if not title.strip():
            raise ValueError("a proposal needs a title")
        if item_id is None and base_revision is not None:
            raise ValueError("only a revision of an existing item has a base revision")
        # The shape of a file's reference; that it is this client's source is the caller's
        # check against the source store (C7a).
        source_ref(kind, content)
        if item_id is not None:
            target = self._session.scalar(
                select(ClientKnowledgeItemRow)
                .where(
                    ClientKnowledgeItemRow.item_id == item_id,
                    ClientKnowledgeItemRow.organization_id == organization_id,
                    ClientKnowledgeItemRow.client_id == client_id,
                )
                .with_for_update()
            )
            if target is None:
                raise ScopeDenied("not found", reason="unknown_item")
            if target.kind != kind.value:
                raise ValueError("a revision keeps the item's kind")
            # An edit made from an older screen is stale before it is filed. Without a
            # named base, the proposal is written from the revision current now.
            if base_revision is not None and base_revision != target.current_revision:
                raise StaleKnowledgeProposal(
                    item_id=item_id,
                    base_revision=base_revision,
                    current_revision=target.current_revision,
                )
            base_revision = target.current_revision
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
            base_revision=base_revision,
            run_id=run_id,
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
        base_revision: int | None = None,
    ) -> KnowledgeProposal:
        """A study offers a finding for reuse. Changes nothing until someone approves it.

        A study does not attach a client's file: only a person on the client does (C7a).
        """
        scope = _study(scope)
        scope.require(Permission.EDIT_STUDY)
        if source_ref(kind, content or {}) is not None:
            raise ValueError("a study's proposal does not attach a client's source")
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
            base_revision=base_revision,
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
        base_revision: int | None = None,
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
            base_revision=base_revision,
        )

    def propose_from_client_work(
        self, scope: ClientWorkContext, *, run_id: str, drafts: Sequence[ProposalDraft]
    ) -> list[KnowledgeProposal]:
        """File what a run of the client's own work proposes, once (lifecycle K2d2).

        AI proposals from a client's document: each a proposal and never knowledge, marked
        ``authored: "ai"`` and naming the run, until a person accepts it. ``proposed_by`` is the
        person who started the run. A retried step files nothing twice: when the run has
        filed already, what it filed is returned and nothing is written. Only the worker's
        scope of that client's own work files here (``RUN_WORKFLOW``); no study is named.
        """
        if not isinstance(scope, ClientWorkContext):
            raise ScopeDenied("client work requires a client work context", reason="forged_scope")
        scope.require(Permission.RUN_WORKFLOW)
        filed = self._session.scalars(
            select(ClientKnowledgeProposalRow)
            .where(
                ClientKnowledgeProposalRow.organization_id == scope.organization_id,
                ClientKnowledgeProposalRow.client_id == scope.client_id,
                ClientKnowledgeProposalRow.run_id == run_id,
            )
            .order_by(
                ClientKnowledgeProposalRow.proposed_at, ClientKnowledgeProposalRow.proposal_id
            )
        ).all()
        if filed:
            return [_proposal(r) for r in filed]
        return [
            self._add_proposal(
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                study_id=None,
                actor_id=scope.actor_id,
                kind=draft.kind,
                title=draft.title,
                summary=draft.summary,
                content=draft.content,
                provenance={**draft.provenance, "authored": "ai", "run_id": run_id},
                item_id=None,
                base_revision=None,
                run_id=run_id,
            )
            for draft in drafts
        ]

    # --------------------------------------------------------------- decisions

    def decide(
        self,
        scope: ClientContext,
        *,
        proposal_id: str,
        approve: bool,
        note: str = "",
        reviewed_revision: int | None = None,
    ) -> KnowledgeProposal:
        """Approve or reject a proposal. An approval appends a revision and a knowledge revision.

        Needs ``APPROVE_CLIENT_KNOWLEDGE``; the proposer may not decide their own
        proposal unless self-approval is allowed at the client's scope.

        An edit of an item is approved only against the revision it was written from
        (F-K1). Where the item has moved on, the approval raises
        :class:`StaleKnowledgeProposal` and changes nothing, unless the reviewer names the
        item's current revision as ``reviewed_revision``: they read it and accept the edit
        over it, which the new revision's provenance records. A rejection needs neither.
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
            scope,
            row,
            approve=approve,
            note=note,
            action="CLIENT_KNOWLEDGE_DECIDED",
            reviewed_revision=reviewed_revision,
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
        base_revision: int | None = None,
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
                base_revision=base_revision,
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
            base_revision=base_revision,
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

    def add_source_once(
        self,
        scope: ClientContext,
        *,
        url: str,
        title: str,
        summary: str = "",
        content: dict[str, Any],
        provenance: dict[str, Any],
    ) -> SourceAdded:
        """A person adds a web source they checked, once per client and URL.

        The client's row is locked first, so two clicks at once are decided one after the
        other. An active ``SOURCE`` item, or a pending ``SOURCE`` proposal, that is the same
        address answers ``exists`` and writes nothing: its ``content.url`` or
        ``content.final_url`` (where a redirect led) is ``url`` or ``content["final_url"]``.
        Otherwise the source
        is written through :meth:`add` -- knowledge at once, or a proposal where the client
        turned self-approval off -- with ``content.url`` set to ``url``. Needs what
        :meth:`add` needs.
        """
        scope = _client(scope)
        scope.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
        scope.require(ClientPermission.APPROVE_CLIENT_KNOWLEDGE)
        if not url:
            raise ValueError("a source needs its URL")
        final_url = content.get("final_url")
        addresses = {url, final_url} if isinstance(final_url, str) and final_url else {url}

        def same(held: object) -> bool:
            return isinstance(held, dict) and any(
                isinstance(held.get(key), str) and held.get(key) in addresses
                for key in ("url", "final_url")
            )

        self._session.scalar(
            select(ClientRow.client_id)
            .where(
                ClientRow.client_id == scope.client_id,
                ClientRow.organization_id == scope.organization_id,
            )
            .with_for_update()
        )
        # Filtered in Python, not by a JSON path: the same on SQLite and PostgreSQL, and a
        # client's sources are a short list read only on this click.
        items = self._session.execute(
            select(ClientKnowledgeItemRow.item_id, ClientKnowledgeItemRow.content)
            .where(
                ClientKnowledgeItemRow.organization_id == scope.organization_id,
                ClientKnowledgeItemRow.client_id == scope.client_id,
                ClientKnowledgeItemRow.kind == KnowledgeKind.SOURCE.value,
                ClientKnowledgeItemRow.status == "ACTIVE",
            )
            .order_by(ClientKnowledgeItemRow.created_at)
        ).all()
        for item_id, held in items:
            if same(held):
                return SourceAdded(status="exists", item_id=str(item_id), proposal_id=None)
        pending = self._session.execute(
            select(ClientKnowledgeProposalRow.proposal_id, ClientKnowledgeProposalRow.content)
            .where(
                ClientKnowledgeProposalRow.organization_id == scope.organization_id,
                ClientKnowledgeProposalRow.client_id == scope.client_id,
                ClientKnowledgeProposalRow.kind == KnowledgeKind.SOURCE.value,
                ClientKnowledgeProposalRow.status == ProposalStatus.PROPOSED.value,
                ClientKnowledgeProposalRow.item_id.is_(None),
            )
            .order_by(ClientKnowledgeProposalRow.proposed_at)
        ).all()
        for proposal_id, held in pending:
            if same(held):
                return SourceAdded(status="exists", item_id=None, proposal_id=str(proposal_id))
        written = self.add(
            scope,
            kind=KnowledgeKind.SOURCE,
            title=title,
            summary=summary,
            content={**content, "url": url},
            provenance=provenance,
        )
        return SourceAdded(
            status="added" if written.status is ProposalStatus.APPROVED else "proposed",
            item_id=written.item_id,
            proposal_id=written.proposal_id,
        )

    def _settle(
        self,
        scope: ClientContext,
        row: ClientKnowledgeProposalRow,
        *,
        approve: bool,
        note: str,
        action: str,
        reviewed_revision: int | None = None,
    ) -> KnowledgeProposal:
        """Record the decision on a proposal row and, if approved, apply it."""
        if approve and row.item_id is not None:
            self._require_current_base(scope, row, reviewed_revision)
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

    def _require_current_base(
        self,
        scope: ClientContext,
        row: ClientKnowledgeProposalRow,
        reviewed_revision: int | None,
    ) -> None:
        """Refuse an edit whose base is not the item's current revision (F-K1).

        The item is locked here, so nothing writes a revision between this check and
        :meth:`_apply`. An unknown base (``None``) is stale. A reviewer who names the
        current revision accepts over it; the proposal's provenance then says so.
        """
        assert row.item_id is not None
        item = self._session.scalar(
            select(ClientKnowledgeItemRow)
            .where(
                ClientKnowledgeItemRow.item_id == row.item_id,
                ClientKnowledgeItemRow.client_id == scope.client_id,
            )
            .with_for_update()
        )
        if item is None:
            raise ScopeDenied("not found", reason="unknown_item")
        current = item.current_revision
        if row.base_revision == current:
            return
        if reviewed_revision != current:
            raise StaleKnowledgeProposal(
                item_id=row.item_id, base_revision=row.base_revision, current_revision=current
            )
        row.provenance = {
            **(row.provenance or {}),
            "base_revision": row.base_revision,
            "accepted_over_revision": current,
        }

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
