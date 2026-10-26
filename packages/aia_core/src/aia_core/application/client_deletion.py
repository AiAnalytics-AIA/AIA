"""Deleting a client (settings-backends SB5; study-data-lifecycle SDL3, client part).

The product owner, 2026-10-22: **content gone, ledgers kept.** The client's studies' content,
working copies, knowledge, sources, files and run artifacts are deleted; the money ledger (usage
rows and budget holds), the approval ledger and the audit trail are kept, the client's and its
studies' names replaced by their ids. The client and study rows stay as tombstones (archived,
named by id, ``deleted_at``), so every kept row still resolves and no scope can be issued for
them again.

:func:`deletion_preview` counts both sides and issues a one-time confirmation, valid ten
minutes, to the person who asked. :func:`delete_client` spends it and deletes every row in the
caller's transaction; the caller commits, then deletes the stored objects
(:func:`finish_deletion`), so no row ever points at a deleted object. A second call answers
``already_deleted``. Irreversible; within 30 days backups and object versions still hold the
content (MVPQ-07), which the restore runbook's journal covers (SDL5).
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from sqlalchemy.orm import Session

from ..domain.scope import OrganizationContext
from ..infrastructure.ai_usage_repository import client_usage_rows, organization_usage_rows
from ..infrastructure.client_knowledge_repository import (
    count_client_knowledge,
    erase_client_knowledge,
)
from ..infrastructure.client_profile_repository import erase_client_profile
from ..infrastructure.client_source_repository import count_client_sources, erase_client_sources
from ..infrastructure.client_work_journal import erase_client_work_journal
from ..infrastructure.deep_research_settings_repository import erase_client_test_policies
from ..infrastructure.fieldwork_journal import erase_study_fieldwork_journals
from ..infrastructure.holdout_repository import erase_client_holdouts
from ..infrastructure.population_repository import client_population_children
from ..infrastructure.repositories import (
    active_client_runs,
    client_projects,
    erase_client_projects,
)
from ..infrastructure.researcher_lead_repository import erase_client_notes
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.storage import ArtifactStore, ObjectNotFound
from ..infrastructure.study_design_repository import erase_client_designs
from ..infrastructure.study_lead_repository import erase_client_lead_turns
from ..infrastructure.study_workspace_repository import erase_client_workspaces
from ..infrastructure.workflow_repository import (
    client_approval_rows,
    organization_approval_rows,
    scrub_client_approvals,
)
from ..infrastructure.workspace_edit_repository import erase_client_edit_ops

__all__ = [
    "CONFIRMATION_MINUTES",
    "ClientDeletion",
    "ClientHasActiveWork",
    "DeletionPreview",
    "KeptRecord",
    "delete_client",
    "deletion_preview",
    "finish_deletion",
    "kept_records",
]

log = logging.getLogger(__name__)

CONFIRMATION_MINUTES: Final = 10


@dataclass(frozen=True, slots=True)
class DeletionPreview:
    client_id: str
    name: str
    status: str
    #: studies, working_revisions, knowledge_items, sources, files, runs, artifacts
    deleted: dict[str, int]
    #: usage_rows (usage ledger and budget holds), approval_rows, audit_rows
    kept: dict[str, int]
    #: What is not deleted yet, though it should be, until the stores can delete it
    #: (study-data-lifecycle SDL2): ``population_children`` (materialized for the client) and
    #: ``replaced_source_readings`` (an older reading of a reread source; ``None``: not counted,
    #: its key is not kept). Nothing here is shown as deleted.
    remains_until_sdl2: dict[str, int | None]
    #: The client's runs that have not ended, by id (the ones :class:`ClientHasActiveWork`
    #: would name), so the person sees before confirming that the deletion waits for them
    #: (settings-redesign F22). Read when the preview is made; the deletion checks again.
    active_run_ids: list[str]
    confirm_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ClientDeletion:
    already_deleted: bool
    deleted: dict[str, int]


class ClientHasActiveWork(Exception):
    """The client has runs that have not ended: a leased step would go on paying and writing
    under a deleted client. The person cancels them first (the runs' own cancel)."""

    def __init__(self, run_ids: Sequence[str]) -> None:
        super().__init__(f"{len(run_ids)} run(s) of the client have not ended")
        self.run_ids = list(run_ids)


def _counts(
    session: Session, scope: ScopeRepository, admin: OrganizationContext, client_id: str
) -> tuple[dict[str, int], dict[str, int]]:
    projects = client_projects(session, client_id=client_id)
    sources = count_client_sources(session, client_id=client_id)
    deleted = {
        "studies": len(scope.client_study_ids(admin, client_id)),
        "working_revisions": projects.revisions,
        "knowledge_items": count_client_knowledge(session, client_id=client_id),
        "sources": sources,
        "files": projects.artifacts + sources,
        "runs": projects.runs,
        "artifacts": projects.artifacts,
    }
    kept = {
        "usage_rows": client_usage_rows(session, client_id=client_id),
        "approval_rows": client_approval_rows(session, client_id=client_id),
        "audit_rows": scope.client_audit_rows(admin, client_id),
    }
    return deleted, kept


def deletion_preview(
    session: Session, admin: OrganizationContext, client_id: str, *, now: datetime
) -> DeletionPreview | None:
    """What deleting the client removes and keeps, and a confirmation for this person, valid
    :data:`CONFIRMATION_MINUTES`. OWNER or ADMIN of the client's organization; ``None`` when
    the client is already deleted. The caller commits (the confirmation is kept)."""
    scope = ScopeRepository(session)
    client = scope.client_for_deletion(admin, client_id)
    if client is None:
        return None
    deleted, kept = _counts(session, scope, admin, client_id)
    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=CONFIRMATION_MINUTES)
    scope.issue_deletion_ticket(admin, client_id, token=token, expires_at=expires_at)
    return DeletionPreview(
        client_id=client.client_id,
        name=client.name,
        status=client.status.value,
        deleted=deleted,
        kept=kept,
        remains_until_sdl2={
            "population_children": client_population_children(session, client_id=client_id),
            "replaced_source_readings": None,
        },
        active_run_ids=active_client_runs(session, client_id=client_id),
        confirm_token=token,
        expires_at=expires_at,
    )


def delete_client(
    session: Session,
    admin: OrganizationContext,
    client_id: str,
    *,
    confirm_token: str,
    now: datetime,
) -> ClientDeletion:
    """Delete the client's content in the caller's transaction and leave its tombstone.

    The client row is locked first. ``ScopeDenied`` ``confirmation_invalid`` /
    ``confirmation_expired`` when the confirmation is not this person's for this client, or is
    old; :class:`ClientHasActiveWork` while any of its runs has not ended. The objects to delete
    are listed with the rows, in the same transaction; the caller commits, then
    :func:`finish_deletion` deletes them. On a tombstone this answers ``already_deleted`` and
    asks nothing: :func:`finish_deletion` retries what is left."""
    scope = ScopeRepository(session)
    scope.lock_client(admin, client_id)
    if scope.client_for_deletion(admin, client_id) is None:
        return ClientDeletion(already_deleted=True, deleted={})
    scope.spend_deletion_ticket(admin, client_id, token=confirm_token, now=now)
    running = active_client_runs(session, client_id=client_id)
    if running:
        raise ClientHasActiveWork(running)
    deleted, kept = _counts(session, scope, admin, client_id)
    study_ids = scope.client_study_ids(admin, client_id)
    names = scope.client_names(admin, client_id)

    erase_client_knowledge(session, client_id=client_id)
    _, source_keys = erase_client_sources(session, client_id=client_id)
    erase_client_profile(session, client_id=client_id)
    erase_client_notes(session, client_id=client_id)
    erase_client_edit_ops(session, client_id=client_id)
    erase_client_holdouts(session, client_id=client_id)
    erase_client_test_policies(session, client_id=client_id)
    erase_client_work_journal(session, client_id=client_id)
    erase_study_fieldwork_journals(session, study_ids=study_ids)
    # A person's own Lead message has no run: no cascade from the runs reaches it.
    erase_client_lead_turns(session, client_id=client_id)
    # The rows that hold a project (RESTRICT) before the projects themselves.
    erase_client_designs(session, client_id=client_id)
    erase_client_workspaces(session, client_id=client_id)
    _, artifact_keys = erase_client_projects(session, client_id=client_id)
    # The kept approval ledger, content-free (MVPQ-07): names to ids, other text erased.
    scrub_client_approvals(session, client_id=client_id, names=names)

    scope.keep_pending_objects(admin, client_id, [*artifact_keys, *source_keys])
    scope.tombstone_client(admin, client_id, now=now, counts={**deleted, **kept})
    return ClientDeletion(already_deleted=False, deleted=deleted)


def finish_deletion(
    session: Session, admin: OrganizationContext, client_id: str, store: ArtifactStore
) -> tuple[int, int]:
    """Delete a deleted client's stored objects still listed, after the rows' deletion
    committed: each cleared, and committed, as it goes, so an interruption leaves only what is
    left to the next try. Audited with what was deleted and what failed. Returns
    ``(deleted, failed)``."""
    scope = ScopeRepository(session)
    keys = scope.pending_objects(admin, client_id)
    if not keys:
        return 0, 0
    deleted = failed = 0
    for key in keys:
        try:
            store.delete(key)
        except ObjectNotFound:
            pass
        except Exception:
            failed += 1
            log.exception("a deleted client's object could not be deleted; it stays listed")
            continue
        scope.clear_pending_object(admin, client_id, key)
        session.commit()
        deleted += 1
    scope.record_object_deletion(admin, client_id, deleted=deleted, failed=failed)
    session.commit()
    return deleted, failed


@dataclass(frozen=True, slots=True)
class KeptRecord:
    """A kind of record a deletion keeps: how many the organization holds, for how long, why."""

    record: str
    count: int
    #: ``indefinite``: kept with no horizon (the product owner, MVPQ-07, 2026-10-20).
    kept_for: str
    why: str


def kept_records(session: Session, admin: OrganizationContext) -> list[KeptRecord]:
    """What a client's deletion keeps, organization-wide; OWNER or ADMIN (MVPQ-07: content-free
    usage and audit rows are kept, readable by an OWNER or ADMIN only)."""
    audit, tombstones = ScopeRepository(session).kept_after_deletion(admin)
    usage, holds = organization_usage_rows(session, organization_id=admin.organization_id)
    approvals = organization_approval_rows(session, organization_id=admin.organization_id)
    return [
        KeptRecord(
            "usage_rows",
            usage,
            "indefinite",
            "each model call's tokens and cost, no text: spend reconciles",
        ),
        KeptRecord(
            "budget_holds", holds, "indefinite", "what was held and settled against a budget"
        ),
        KeptRecord(
            "approval_rows", approvals, "indefinite", "who approved which paid work or change"
        ),
        KeptRecord(
            "audit_rows", audit, "indefinite", "who changed what and when; names replaced by ids"
        ),
        KeptRecord(
            "deleted_clients",
            tombstones,
            "indefinite",
            "a deleted client's id, so the kept rows resolve",
        ),
    ]
