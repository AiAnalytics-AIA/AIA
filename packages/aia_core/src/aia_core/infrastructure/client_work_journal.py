"""The answered model requests of the client's own work (lifecycle K2d).

A document's proposals are asked batch by batch, and a step can stop between batches:
parked when the client's budget cannot hold the next call, or released by its worker.
Each answer is kept here the moment it returns, keyed by the client and a fingerprint
of exactly what was sent, and read before anything is asked. A resumed step -- or a new
run over the same reading -- replays what was answered and pays only for what was not.

Only the worker's scope of that client's own work reads or writes here
(``RUN_WORKFLOW``); another client's entries are never found. An entry is written once:
a second write of the same key keeps the first, which answered the same request.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.scope import ClientWorkContext, Permission, ScopeDenied
from .tables import ClientWorkJournalRow

__all__ = ["ClientWorkJournal", "erase_client_work_journal"]


class ClientWorkJournal:
    def __init__(self, session: Session, scope: ClientWorkContext) -> None:
        if not isinstance(scope, ClientWorkContext):
            raise ScopeDenied("client work requires a client work context", reason="forged_scope")
        scope.require(Permission.RUN_WORKFLOW)
        self._session = session
        self._scope = scope

    def get(self, request_key: str) -> dict[str, Any] | None:
        """The answer kept for ``request_key``, or ``None`` when it was never answered."""
        row = self._row(request_key)
        return None if row is None else dict(row.payload)

    def put(self, request_key: str, *, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Keep an answer once; returns what is kept (the first, if one was already)."""
        found = self._row(request_key)
        if found is not None:
            return dict(found.payload)
        try:
            with self._session.begin_nested():
                self._session.add(
                    ClientWorkJournalRow(
                        journal_id=f"CWJ-{uuid4().hex[:14]}",
                        organization_id=self._scope.organization_id,
                        client_id=self._scope.client_id,
                        request_key=request_key,
                        run_id=run_id,
                        payload=payload,
                    )
                )
        except IntegrityError:
            raced = self._row(request_key)
            if raced is None:
                raise
            return dict(raced.payload)
        return payload

    def _row(self, request_key: str) -> ClientWorkJournalRow | None:
        return self._session.scalar(
            select(ClientWorkJournalRow).where(
                ClientWorkJournalRow.organization_id == self._scope.organization_id,
                ClientWorkJournalRow.client_id == self._scope.client_id,
                ClientWorkJournalRow.request_key == request_key,
            )
        )


def erase_client_work_journal(session: Session, *, client_id: str) -> None:
    """Delete a deleted client's work journal: what its paid requests answered (SB5)."""
    session.execute(delete(ClientWorkJournalRow).where(ClientWorkJournalRow.client_id == client_id))
    session.flush()
