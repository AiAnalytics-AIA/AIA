"""Opening a session on the report editor's origin (plan report-editor-hosting, chunk 3).

A ticket the API signed names a person and their organization. Spending it admits that
person to ``docs.<hostname>`` only if they are still an active member, recorded in the
access audit as any session is, and only once: a second spend of the same ticket is
refused whoever presents it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..domain.scope import OrganizationContext
from ..infrastructure.docs_ticket_repository import DocsTicketRepository
from .scope import AuthenticatedPrincipal, ScopeResolver

__all__ = ["DocsTicketSpent", "open_docs_session"]


class DocsTicketSpent(Exception):
    """The ticket was spent already."""


def open_docs_session(
    session: Session,
    *,
    user_id: str,
    organization_id: str,
    ticket_id: str,
    expires_at: datetime,
    now: datetime,
) -> OrganizationContext:
    """Spend the ticket for its person; raises ScopeDenied or :class:`DocsTicketSpent`."""
    principal = AuthenticatedPrincipal(user_id=user_id, organization_id=organization_id)
    context = ScopeResolver(session).authorize_session(principal, audit=True)
    if not DocsTicketRepository(session, context).spend(ticket_id, expires_at=expires_at, now=now):
        raise DocsTicketSpent(ticket_id)
    return context
