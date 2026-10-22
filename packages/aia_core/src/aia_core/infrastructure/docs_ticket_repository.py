"""Spent tickets to the report editor's origin (plan report-editor-hosting, chunk 3).

A ticket is signed and expires on its own (``aia_api.docs_pass``); what makes it single
use, across every API process, is this table's primary key. A spend is made in the
organization scope ``ScopeResolver`` issued for the ticket's person once it found them
still an active member, and records that person. Their rows a day past expiry are
deleted on their next spend: nothing reads a spent ticket after it expired.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.scope import OrganizationContext, ScopeDenied
from .tables import DocsTicketSpendRow

__all__ = ["DocsTicketRepository"]

KEEP_AFTER_EXPIRY = timedelta(days=1)


class DocsTicketRepository:
    def __init__(self, session: Session, scope: OrganizationContext) -> None:
        if not isinstance(scope, OrganizationContext):
            raise ScopeDenied("a docs ticket needs an organization context", reason="forged_scope")
        self._session = session
        self._scope = scope

    def spend(self, ticket_id: str, *, expires_at: datetime, now: datetime) -> bool:
        """Record the ticket spent; False when it already was."""
        self._session.execute(
            delete(DocsTicketSpendRow).where(
                DocsTicketSpendRow.user_id == self._scope.actor_id,
                DocsTicketSpendRow.expires_at < now - KEEP_AFTER_EXPIRY,
            )
        )
        try:
            with self._session.begin_nested():
                self._session.add(
                    DocsTicketSpendRow(
                        ticket_id=ticket_id,
                        user_id=self._scope.actor_id,
                        expires_at=expires_at,
                        spent_at=now,
                    )
                )
        except IntegrityError:
            return False
        return True
