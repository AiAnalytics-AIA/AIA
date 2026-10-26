"""A researcher's conversation with their Research Lead in one Study (ADR 0026 decision 8).

The only reader and writer of ``study_lead_turns`` (``make layer_check``). Every method takes
the issued :class:`~aia_core.domain.scope.StudyContext` it was built with and filters by all
three scope columns **and the calling researcher** (``scope.actor_id``): a conversation is
one researcher's, so nobody reads another's turns, even on the same Study (the product
owner, 2026-10-19). The table is append-only; a turn is never rewritten.

The caller owns the transaction. The one exception to "never rewritten" is
:func:`erase_member_turns`: the retention sweep erases a sealed Lead's conversations
(ADR 0030, settings-backends SB2).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..domain.research_lead import LeadTurn, new_turn_id
from ..domain.scope import ScopeDenied, StudyContext
from .tables import StudyLeadTurnAnswerRow, StudyLeadTurnRow, StudyRow, as_utc, utcnow

__all__ = [
    "StudyLeadRepository",
    "erase_client_lead_turns",
    "erase_member_turns",
]


def _to_domain(row: StudyLeadTurnRow) -> LeadTurn:
    return LeadTurn(
        turn_id=row.turn_id,
        study_id=row.study_id,
        user_id=row.user_id,
        sequence_no=row.sequence_no,
        actor=row.actor,
        kind=row.kind,
        stage=row.stage,
        text=row.text,
        focus=dict(row.focus) if row.focus else None,
        run_id=row.run_id,
        workspace_revision=row.workspace_revision,
        design_revision_id=row.design_revision_id,
        created_by=row.created_by,
        created_at=as_utc(row.created_at),
        command=row.command,
        parent_turn_id=row.parent_turn_id,
    )


class StudyLeadRepository:
    """The calling researcher's Lead turns in the Study in scope."""

    def __init__(self, session: Session, scope: StudyContext) -> None:
        if not isinstance(scope, StudyContext):
            raise TypeError("StudyLeadRepository needs an issued StudyContext")
        self._session = session
        self._scope = scope

    def _mine(self) -> tuple[Any, ...]:
        s = self._scope
        return (
            StudyLeadTurnRow.organization_id == s.organization_id,
            StudyLeadTurnRow.client_id == s.client_id,
            StudyLeadTurnRow.study_id == s.study_id,
            StudyLeadTurnRow.user_id == s.actor_id,
        )

    # -- reads ---------------------------------------------------------------

    def turns(self, *, limit: int = 100) -> list[LeadTurn]:
        """The newest ``limit`` turns of this researcher's conversation, oldest first."""
        rows = self._session.scalars(
            select(StudyLeadTurnRow)
            .where(*self._mine())
            .order_by(StudyLeadTurnRow.sequence_no.desc())
            .limit(max(1, min(int(limit), 500)))
        ).all()
        return [_to_domain(r) for r in reversed(rows)]

    def queued(self) -> list[LeadTurn]:
        """This researcher's messages no Lead turn has been sent and no withdrawal names, in
        queue order (ADR 0041 decision 7): state derived from the rows, never stored."""
        answered = select(StudyLeadTurnAnswerRow.person_turn_id).where(
            StudyLeadTurnAnswerRow.study_id == self._scope.study_id,
            StudyLeadTurnAnswerRow.user_id == self._scope.actor_id,
        )
        withdrawn = select(StudyLeadTurnRow.parent_turn_id).where(
            *self._mine(), StudyLeadTurnRow.kind == "withdrawal"
        )
        rows = self._session.scalars(
            select(StudyLeadTurnRow)
            .where(
                *self._mine(),
                StudyLeadTurnRow.actor == "person",
                StudyLeadTurnRow.kind == "message",
                StudyLeadTurnRow.command.is_(None),
                StudyLeadTurnRow.turn_id.not_in(answered),
                StudyLeadTurnRow.turn_id.not_in(withdrawn),
            )
            .order_by(StudyLeadTurnRow.sequence_no)
        ).all()
        return [_to_domain(r) for r in rows]

    def withdrawn(self, turn_ids: list[str]) -> set[str]:
        """Which of these messages a ``withdrawal`` names."""
        if not turn_ids:
            return set()
        return set(
            self._session.scalars(
                select(StudyLeadTurnRow.parent_turn_id).where(
                    *self._mine(),
                    StudyLeadTurnRow.kind == "withdrawal",
                    StudyLeadTurnRow.parent_turn_id.in_(turn_ids),
                )
            )
        )

    def answers(self, lead_turn_ids: list[str]) -> dict[str, list[str]]:
        """The messages each of these Lead turns was sent, in queue order."""
        if not lead_turn_ids:
            return {}
        rows = self._session.execute(
            select(StudyLeadTurnAnswerRow.lead_turn_id, StudyLeadTurnAnswerRow.person_turn_id)
            .join(
                StudyLeadTurnRow,
                StudyLeadTurnRow.turn_id == StudyLeadTurnAnswerRow.person_turn_id,
            )
            .where(
                *self._mine(),
                StudyLeadTurnAnswerRow.lead_turn_id.in_(lead_turn_ids),
            )
            .order_by(StudyLeadTurnRow.sequence_no)
        ).all()
        out: dict[str, list[str]] = {}
        for lead_turn_id, person_turn_id in rows:
            out.setdefault(lead_turn_id, []).append(person_turn_id)
        return out

    def lead_turn_ids(self) -> list[str]:
        """Every Lead turn of this researcher's conversation in the Study, oldest first: the
        turns whose ledger decisions the decision digest reads (ids only)."""
        return list(
            self._session.scalars(
                select(StudyLeadTurnRow.turn_id)
                .where(*self._mine(), StudyLeadTurnRow.actor == "lead")
                .order_by(StudyLeadTurnRow.sequence_no)
            )
        )

    def get(self, turn_id: str) -> LeadTurn | None:
        """One turn of this researcher's conversation in the Study; ``None`` for any other,
        whoever's it is."""
        row = self._session.scalar(
            select(StudyLeadTurnRow).where(*self._mine(), StudyLeadTurnRow.turn_id == turn_id)
        )
        return _to_domain(row) if row else None

    def latest_lead_turn(self) -> LeadTurn | None:
        """This researcher's newest Lead turn in the Study, or ``None``."""
        row = self._session.scalar(
            select(StudyLeadTurnRow)
            .where(*self._mine(), StudyLeadTurnRow.actor == "lead")
            .order_by(StudyLeadTurnRow.sequence_no.desc())
            .limit(1)
        )
        return _to_domain(row) if row else None

    def has_spoken_before(self) -> bool:
        """Whether this researcher's Lead has answered them anywhere in the organization.

        Only the researcher's own rows are read, across their Studies: the Lead introduces
        itself in its first conversation after hatching, not in every Study.
        """
        s = self._scope
        count = self._session.scalar(
            select(func.count())
            .select_from(StudyLeadTurnRow)
            .where(
                StudyLeadTurnRow.organization_id == s.organization_id,
                StudyLeadTurnRow.user_id == s.actor_id,
                StudyLeadTurnRow.actor == "lead",
            )
        )
        return bool(count)

    # -- writes --------------------------------------------------------------

    def lock(self) -> None:
        """Serialize this Study's Lead turns on the Study row, so two messages sent at once
        cannot both find the conversation idle (a no-op on SQLite's single writer)."""
        s = self._scope
        study = self._session.scalar(
            select(StudyRow.study_id)
            .where(StudyRow.study_id == s.study_id, StudyRow.client_id == s.client_id)
            .with_for_update()
        )
        if study is None:  # pragma: no cover - an issued scope names an existing study
            raise ScopeDenied("not found", reason="unknown_study")

    def append(
        self,
        *,
        actor: str,
        kind: str,
        stage: str,
        text: str | None = None,
        focus: dict[str, str] | None = None,
        run_id: str | None = None,
        workspace_revision: int | None = None,
        design_revision_id: str | None = None,
        turn_id: str | None = None,
        command: str | None = None,
        parent_turn_id: str | None = None,
    ) -> LeadTurn:
        """Append one turn to this researcher's conversation, numbered after the last."""
        s = self._scope
        last = self._session.scalar(
            select(func.max(StudyLeadTurnRow.sequence_no)).where(*self._mine())
        )
        row = StudyLeadTurnRow(
            turn_id=turn_id or new_turn_id(),
            organization_id=s.organization_id,
            client_id=s.client_id,
            study_id=s.study_id,
            user_id=s.actor_id,
            sequence_no=int(last or 0) + 1,
            actor=actor,
            kind=kind,
            stage=stage,
            text=text,
            focus=focus,
            run_id=run_id,
            workspace_revision=workspace_revision,
            design_revision_id=design_revision_id,
            command=command,
            parent_turn_id=parent_turn_id,
            created_by=s.actor_id,
            created_at=utcnow(),
        )
        self._session.add(row)
        self._session.flush()
        return _to_domain(row)

    def record_answers(self, lead_turn_id: str, person_turn_ids: list[str]) -> None:
        """Record that ``lead_turn_id`` was sent these messages: one append-only row each, in
        the transaction that stores the Lead turn."""
        s = self._scope
        now = utcnow()
        self._session.add_all(
            StudyLeadTurnAnswerRow(
                lead_turn_id=lead_turn_id,
                person_turn_id=person_turn_id,
                organization_id=s.organization_id,
                study_id=s.study_id,
                user_id=s.actor_id,
                created_at=now,
            )
            for person_turn_id in person_turn_ids
        )
        self._session.flush()


def erase_member_turns(session: Session, *, organization_id: str, user_id: str) -> list[str]:
    """Erase every Lead turn of one member in one organization, every Study; returns the
    runs those turns started, so their steps and artifacts can be erased too. The retention
    sweep's alone, after the member's Lead was sealed for its full period."""
    where = (
        StudyLeadTurnRow.organization_id == organization_id,
        StudyLeadTurnRow.user_id == user_id,
    )
    run_ids = sorted(
        {r for r in session.scalars(select(StudyLeadTurnRow.run_id).where(*where)) if r is not None}
    )
    # The answer rows name these turns; deleted explicitly, never left to the FK's cascade.
    session.execute(
        delete(StudyLeadTurnAnswerRow).where(
            StudyLeadTurnAnswerRow.organization_id == organization_id,
            StudyLeadTurnAnswerRow.user_id == user_id,
        )
    )
    session.execute(delete(StudyLeadTurnRow).where(*where))
    return run_ids


def erase_client_lead_turns(session: Session, *, client_id: str) -> int:
    """Delete every Lead turn in a deleted client's studies (settings-backends SB5): a
    person's own message has no run, so no cascade reaches it. Returns the turns deleted."""
    turns = int(
        session.scalar(
            select(func.count())
            .select_from(StudyLeadTurnRow)
            .where(StudyLeadTurnRow.client_id == client_id)
        )
        or 0
    )
    # The answer rows name these turns; deleted explicitly, never left to the FK's cascade.
    client_turns = select(StudyLeadTurnRow.turn_id).where(StudyLeadTurnRow.client_id == client_id)
    session.execute(
        delete(StudyLeadTurnAnswerRow).where(StudyLeadTurnAnswerRow.lead_turn_id.in_(client_turns))
    )
    session.execute(delete(StudyLeadTurnRow).where(StudyLeadTurnRow.client_id == client_id))
    session.flush()
    return turns
