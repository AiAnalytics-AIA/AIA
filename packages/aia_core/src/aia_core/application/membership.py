"""Deactivating and reactivating a member, and the seal on their Lead (D-27, ADR 0030).

Plan settings-backends SB2. An organization OWNER or ADMIN deactivates a member of their own
organization (security-audit S15: never a user found elsewhere); the membership resolves no
scope from the next request, and the member's Research Lead is sealed in the same
transaction: unreadable by anyone, the member included. A reactivation within
:data:`~aia_core.infrastructure.researcher_lead_repository.SEAL_DAYS` unseals it for that
member; after that the retention sweep (:func:`erase_sealed_leads`) erases it, with every
conversation, frozen context and answer the Lead's turns kept.

The caller owns the transaction, except :func:`erase_sealed_leads`, which commits each Lead
on its own and deletes the stored objects after its commit.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from ..domain.scope import OrganizationContext
from ..infrastructure.artifact_repository import erase_artifacts_of_attempts
from ..infrastructure.researcher_lead_repository import ErasedLead, LeadSeal, LeadSeals
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.storage import ArtifactStore, ObjectNotFound
from ..infrastructure.study_lead_repository import erase_member_turns
from ..infrastructure.workflow_repository import erase_lead_run_payloads

__all__ = [
    "Deactivation",
    "Reactivation",
    "deactivate_member",
    "erase_sealed_leads",
    "reactivate_member",
]

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Deactivation:
    """What a deactivation did: whether it changed anything, and the Lead's seal if any."""

    changed: bool
    seal: LeadSeal | None


@dataclass(frozen=True, slots=True)
class Reactivation:
    """What a reactivation did: whether it changed anything, and whether the Lead came back."""

    changed: bool
    lead_unsealed: bool


def deactivate_member(
    session: Session, admin: OrganizationContext, *, user_id: str, now: datetime
) -> Deactivation:
    """Deactivate the member in the admin's own organization and seal their Lead."""
    changed = ScopeRepository(session).deactivate_member(admin, user_id=user_id, now=now)
    return Deactivation(changed, LeadSeals(session, admin).seal(user_id, now=now))


def reactivate_member(
    session: Session, admin: OrganizationContext, *, user_id: str
) -> Reactivation:
    """Reactivate the member; their Lead is unsealed when it has not been erased yet."""
    changed = ScopeRepository(session).reactivate_member(admin, user_id=user_id)
    return Reactivation(changed, LeadSeals(session, admin).unseal(user_id) if changed else False)


def lead_seals(session: Session, admin: OrganizationContext) -> dict[str, LeadSeal]:
    """Every sealed Lead of the admin's organization, by member: when, and when erased."""
    return LeadSeals(session, admin).seals()


def erase_sealed_leads(
    sessions: Callable[[], Session], store: ArtifactStore, *, now: datetime
) -> list[ErasedLead]:
    """Erase every sealed Lead past its date: the Lead's files, history and notes, its
    researcher's Lead turns in every Study, what those turns' steps sent and got back, and
    the artifacts they stored. One Lead per transaction; a Lead unsealed meanwhile is left.

    What stays: the turns' runs and steps as rows (status, costs), so the usage ledger, the
    approval ledger and the audit trail still resolve; they hold no Lead content.
    """
    with sessions() as session:
        due = LeadSeals.due(session, now=now)
    erased: list[ErasedLead] = []
    for organization_id, user_id, lead_id in due:
        with sessions() as session:
            done = LeadSeals.erase(session, lead_id=lead_id)
            if done is None:
                session.rollback()
                continue
            run_ids = erase_member_turns(session, organization_id=organization_id, user_id=user_id)
            attempts = erase_lead_run_payloads(
                session, organization_id=organization_id, user_id=user_id, run_ids=run_ids
            )
            keys = erase_artifacts_of_attempts(session, attempts)
            session.commit()
        for key in keys:
            try:
                store.delete(key)
            except ObjectNotFound:
                pass
            except Exception:  # an orphaned object harms nothing; a later sweep is not needed
                log.exception("a sealed Lead's object could not be deleted")
        erased.append(done)
    return erased
