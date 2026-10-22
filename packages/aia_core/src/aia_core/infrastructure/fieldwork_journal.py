"""The answered respondent blocks of a research run's fieldwork (run-qc-and-checkpoint RQC0).

Fieldwork asks the model one respondent block at a time, and a step can stop between blocks:
released by its worker, its lease lost, or its run retried. Each answer is kept here the moment
it returns, keyed by the run's lineage (the run a retry chain began with) and a fingerprint of
exactly what was sent, and read before anything is asked; a resumed attempt or a retried run
replays what was answered and pays only for what was not.

Only a scope of the run's own study with ``RUN_WORKFLOW`` reads or writes here; another study's
entries are never found. An entry is written once: a second write of the same key keeps the
first, which answered the same request.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.scope import Permission, ScopeDenied, StudyContext
from .tables import FieldworkJournalRow

__all__ = ["FieldworkJournal"]


class FieldworkJournal:
    def __init__(self, session: Session, scope: StudyContext, *, lineage_run_id: str) -> None:
        if not isinstance(scope, StudyContext):
            raise ScopeDenied("fieldwork requires a study context", reason="forged_scope")
        scope.require(Permission.RUN_WORKFLOW)
        self._session = session
        self._scope = scope
        self._lineage = lineage_run_id

    def get(self, request_key: str) -> dict[str, Any] | None:
        """The answer kept for ``request_key`` in this lineage, or ``None`` if never answered."""
        row = self._row(request_key)
        return None if row is None else dict(row.payload)

    def kept(self) -> dict[str, dict[str, Any]]:
        """Every answer kept in this lineage, by request key: one read before fieldwork asks."""
        rows = self._session.scalars(
            select(FieldworkJournalRow).where(
                FieldworkJournalRow.organization_id == self._scope.organization_id,
                FieldworkJournalRow.study_id == self._scope.study_id,
                FieldworkJournalRow.lineage_run_id == self._lineage,
            )
        )
        return {row.request_key: dict(row.payload) for row in rows}

    def put(self, request_key: str, *, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Keep an answer once; returns what is kept (the first, if one was already)."""
        found = self._row(request_key)
        if found is not None:
            return dict(found.payload)
        try:
            with self._session.begin_nested():
                self._session.add(
                    FieldworkJournalRow(
                        journal_id=f"FWJ-{uuid4().hex[:14]}",
                        organization_id=self._scope.organization_id,
                        study_id=self._scope.study_id,
                        lineage_run_id=self._lineage,
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

    def _row(self, request_key: str) -> FieldworkJournalRow | None:
        return self._session.scalar(
            select(FieldworkJournalRow).where(
                FieldworkJournalRow.organization_id == self._scope.organization_id,
                FieldworkJournalRow.study_id == self._scope.study_id,
                FieldworkJournalRow.lineage_run_id == self._lineage,
                FieldworkJournalRow.request_key == request_key,
            )
        )
