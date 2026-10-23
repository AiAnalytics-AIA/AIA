"""Each researcher's own Research Lead: its files and its notes (product owner, 2026-10-19).

The only reader and writer of ``researcher_leads``, ``researcher_lead_revisions`` and
``researcher_lead_memories`` (``make layer_check``). It takes an issued scope and always works
on the **calling researcher's** Lead -- ``(organization_id, actor_id)`` from the scope, never
an argument -- so nobody reads or changes another researcher's Lead.

Two rules are kept in the queries, not in a prompt:

* **Client isolation.** A ``client`` note is loaded only into a turn of that client's Study
  (:meth:`ResearcherLeadRepository.notes_for_study`, by ``client_id``); ``personal`` notes
  load everywhere. A forget can reach only a note the same query would have loaded.
* **The researcher changes the files only through chat.** Over HTTP a Lead can be hatched and
  read; its files and notes change only by :meth:`ResearcherLeadRepository.apply_self_update`,
  which a Lead turn's step calls under the researcher's own run scope, keeping each replaced
  text in ``researcher_lead_revisions``.

The caller owns the transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.research_lead import (
    DEFAULT_LEAD_NAME,
    DEFAULT_SOUL,
    DEFAULT_USER,
    NOTES_IN_CONTEXT,
    LeadNote,
    ResearcherLead,
    SelfUpdate,
    SelfUpdateApplied,
    new_lead_id,
    new_lead_revision_id,
    new_memory_id,
)
from ..domain.scope import OrganizationContext, Permission, ScopeDenied, StudyContext
from .tables import (
    AccessAuditRow,
    ClientRow,
    ResearcherLeadMemoryRow,
    ResearcherLeadRevisionRow,
    ResearcherLeadRow,
    as_utc,
    utcnow,
)

__all__ = [
    "SEAL_DAYS",
    "ErasedLead",
    "LeadAlreadyHatched",
    "LeadNotHatched",
    "LeadSeal",
    "LeadSeals",
    "ResearcherLeadRepository",
    "erase_client_notes",
]

_FIELD_ORDER = {"name": 0, "soul": 1, "user": 2}


class LeadAlreadyHatched(Exception):
    """The researcher already has a Lead in this organization."""

    reason = "lead_already_hatched"


class LeadNotHatched(Exception):
    """The researcher has not hatched a Lead yet."""

    reason = "lead_not_hatched"


def _lead(row: ResearcherLeadRow) -> ResearcherLead:
    return ResearcherLead(
        lead_id=row.lead_id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        name=row.name,
        soul=row.soul,
        user=row.user_profile,
        hatched_at=as_utc(row.hatched_at),
        updated_at=as_utc(row.updated_at),
        auto_accept_text_edits=bool(row.auto_accept_text_edits),
    )


def _note(row: ResearcherLeadMemoryRow, client_name: str | None = None) -> LeadNote:
    return LeadNote(
        memory_id=row.memory_id,
        scope=row.scope,
        client_id=row.client_id,
        client_name=client_name,
        text=row.text,
        source_turn_id=row.source_turn_id,
        created_by=row.created_by,
        created_at=as_utc(row.created_at),
    )


class ResearcherLeadRepository:
    """The calling researcher's Lead, its file history and its notes."""

    def __init__(self, session: Session, scope: OrganizationContext | StudyContext) -> None:
        if not isinstance(scope, OrganizationContext | StudyContext):
            raise TypeError("ResearcherLeadRepository needs an issued organization or study scope")
        self._session = session
        self._scope = scope

    def _owner(self) -> tuple[Any, ...]:
        s = self._scope
        return (
            ResearcherLeadRow.organization_id == s.organization_id,
            ResearcherLeadRow.user_id == s.actor_id,
            # A sealed Lead (ADR 0030) is read by no one, its researcher included.
            ResearcherLeadRow.sealed_at.is_(None),
        )

    def is_sealed(self) -> bool:
        """Whether the calling researcher's Lead is sealed (their membership deactivated):
        a turn queued before the deactivation must not run."""
        s = self._scope
        return (
            self._session.scalar(
                select(ResearcherLeadRow.lead_id).where(
                    ResearcherLeadRow.organization_id == s.organization_id,
                    ResearcherLeadRow.user_id == s.actor_id,
                    ResearcherLeadRow.sealed_at.is_not(None),
                )
            )
            is not None
        )

    def _row(self, *, for_update: bool = False) -> ResearcherLeadRow | None:
        stmt = select(ResearcherLeadRow).where(*self._owner())
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return self._session.scalar(stmt)

    # -- reads ---------------------------------------------------------------

    def get(self) -> ResearcherLead | None:
        """The calling researcher's Lead, or ``None`` before it is hatched."""
        row = self._row()
        return _lead(row) if row else None

    def lock(self) -> ResearcherLead | None:
        """The calling researcher's Lead, its row locked to the end of the transaction.

        Every Lead turn the researcher posts takes it first, so two tabs posting at once are
        decided one after the other: the greeting window and the busy check read what the
        other wrote. ``None`` before the Lead is hatched (a no-op lock on SQLite)."""
        row = self._row(for_update=True)
        return _lead(row) if row else None

    def notes_for_study(self, *, limit: int = NOTES_IN_CONTEXT) -> list[LeadNote]:
        """The active notes a turn of this Study may be shown, newest first: every personal
        note, and the client notes of **this Study's client** only (by ``client_id``)."""
        scope = self._scope
        if not isinstance(scope, StudyContext):
            raise TypeError("notes for a study need a StudyContext")
        lead = self._row()
        if lead is None:
            return []
        rows = self._session.scalars(
            select(ResearcherLeadMemoryRow)
            .where(*self._note_filter(lead, scope))
            .order_by(ResearcherLeadMemoryRow.created_at.desc(), ResearcherLeadMemoryRow.memory_id)
            .limit(max(1, int(limit)))
        ).all()
        return [_note(r) for r in rows]

    def _note_filter(self, lead: ResearcherLeadRow, scope: StudyContext) -> tuple[Any, ...]:
        return (
            ResearcherLeadMemoryRow.lead_id == lead.lead_id,
            ResearcherLeadMemoryRow.organization_id == scope.organization_id,
            ResearcherLeadMemoryRow.user_id == scope.actor_id,
            ResearcherLeadMemoryRow.forgotten_at.is_(None),
            or_(
                ResearcherLeadMemoryRow.scope == "personal",
                (ResearcherLeadMemoryRow.scope == "client")
                & (ResearcherLeadMemoryRow.client_id == scope.client_id),
            ),
        )

    def active_notes(self) -> list[LeadNote]:
        """Every active note of the calling researcher's Lead, newest first, a client note
        with its client's name: what the researcher reads of their own Lead's memory."""
        lead = self._row()
        if lead is None:
            return []
        rows = self._session.execute(
            select(ResearcherLeadMemoryRow, ClientRow.name)
            .outerjoin(
                ClientRow,
                (ClientRow.client_id == ResearcherLeadMemoryRow.client_id)
                & (ClientRow.organization_id == ResearcherLeadMemoryRow.organization_id),
            )
            .where(
                ResearcherLeadMemoryRow.lead_id == lead.lead_id,
                ResearcherLeadMemoryRow.user_id == self._scope.actor_id,
                ResearcherLeadMemoryRow.forgotten_at.is_(None),
            )
            .order_by(ResearcherLeadMemoryRow.created_at.desc(), ResearcherLeadMemoryRow.memory_id)
        ).all()
        return [_note(row, name) for row, name in rows]

    def revisions(self) -> list[dict[str, Any]]:
        """Every change to the Lead's files, oldest first, with the text it replaced."""
        lead = self._row()
        if lead is None:
            return []
        rows = self._session.scalars(
            select(ResearcherLeadRevisionRow).where(
                ResearcherLeadRevisionRow.lead_id == lead.lead_id,
                ResearcherLeadRevisionRow.user_id == self._scope.actor_id,
            )
        ).all()
        # One update writes its fields in this order, at one timestamp.
        rows = sorted(rows, key=lambda r: (as_utc(r.created_at), _FIELD_ORDER[r.field]))
        return [
            {
                "revision_id": r.revision_id,
                "field": r.field,
                "previous": r.previous,
                "value": r.value,
                "source_turn_id": r.source_turn_id,
                "created_at": as_utc(r.created_at),
            }
            for r in rows
        ]

    # -- writes --------------------------------------------------------------

    def hatch(self) -> ResearcherLead:
        """Hatch the calling researcher's Lead with the defaults, once.

        A person's act: a run's scope, whose actor may be a worker, cannot hatch. A second
        hatch -- concurrent or not -- is :class:`LeadAlreadyHatched`.
        """
        s = self._scope
        if s.actor_id.startswith("worker:"):
            raise ScopeDenied("only a person hatches their Lead", reason="insufficient_role")
        if self._row() is not None:
            raise LeadAlreadyHatched("the Lead is already hatched")
        now = utcnow()
        row = ResearcherLeadRow(
            lead_id=new_lead_id(),
            organization_id=s.organization_id,
            user_id=s.actor_id,
            name=DEFAULT_LEAD_NAME,
            soul=DEFAULT_SOUL,
            user_profile=DEFAULT_USER,
            hatched_at=now,
            updated_at=now,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            raise LeadAlreadyHatched("the Lead is already hatched") from exc
        return _lead(row)

    def set_preferences(self, *, auto_accept_text_edits: bool) -> ResearcherLead:
        """The calling researcher sets their own Lead's preferences; audited.

        A person's act on their own row: a run's scope, whose actor may be a worker, cannot.
        ``auto_accept_text_edits`` is their standing choice to have the Lead's text edits
        accepted without a click (plan inline-decisions chunk 2). An unchanged value writes
        nothing. Without a Lead, :class:`LeadNotHatched`.
        """
        s = self._scope
        if s.actor_id.startswith("worker:"):
            raise ScopeDenied(
                "only a person sets their Lead's preferences", reason="insufficient_role"
            )
        row = self._row(for_update=True)
        if row is None:
            raise LeadNotHatched("the researcher has no Lead")
        if bool(row.auto_accept_text_edits) != auto_accept_text_edits:
            previous = bool(row.auto_accept_text_edits)
            row.auto_accept_text_edits = auto_accept_text_edits
            row.updated_at = utcnow()
            self._session.add(
                AccessAuditRow(
                    organization_id=s.organization_id,
                    client_id=s.client_id if isinstance(s, StudyContext) else None,
                    study_id=s.study_id if isinstance(s, StudyContext) else None,
                    actor_id=s.actor_id,
                    action="RESEARCH_LEAD_PREFERENCES_SET",
                    reason="",
                    payload={
                        "lead_id": row.lead_id,
                        "auto_accept_text_edits": auto_accept_text_edits,
                        "previous": previous,
                    },
                    request_id=s.request_id,
                )
            )
            self._session.flush()
        return _lead(row)

    def apply_self_update(self, update_: SelfUpdate, *, source_turn_id: str) -> SelfUpdateApplied:
        """Apply a Lead turn's change to its own files, under that turn's Study scope.

        The researcher asked for it in chat, so it is their edit: it needs ``EDIT_STUDY`` on
        the Study the turn ran in (the worker's scope holds it, acting for the run's
        researcher). ``name``, ``soul`` and ``user`` replace the file, each replaced text kept
        in a revision row; an unchanged value writes nothing. ``remember`` adds notes (a
        client note bound to this Study's client); ``forget`` reaches only active notes this
        Study's turns may be shown. Without a Lead nothing is applied.
        """
        scope = self._scope
        if not isinstance(scope, StudyContext):
            raise TypeError("a Lead's self-update runs under a StudyContext")
        scope.require(Permission.EDIT_STUDY)
        lead = self._row(for_update=True)
        if lead is None:
            raise LeadNotHatched("the researcher has no Lead")
        now = utcnow()
        applied: dict[str, Any] = {"remembered": [], "forgotten": []}
        files = (("name", "name", update_.name), ("soul", "soul", update_.soul))
        for field, column, value in (*files, ("user", "user_profile", update_.user)):
            if value is None or value == getattr(lead, column):
                continue
            self._session.add(
                ResearcherLeadRevisionRow(
                    revision_id=new_lead_revision_id(),
                    lead_id=lead.lead_id,
                    organization_id=lead.organization_id,
                    user_id=lead.user_id,
                    field=field,
                    previous=getattr(lead, column),
                    value=value,
                    source_turn_id=source_turn_id,
                    created_at=now,
                )
            )
            setattr(lead, column, value)
            applied[field] = True
        for note in update_.remember:
            memory_id = new_memory_id()
            self._session.add(
                ResearcherLeadMemoryRow(
                    memory_id=memory_id,
                    lead_id=lead.lead_id,
                    organization_id=lead.organization_id,
                    user_id=lead.user_id,
                    scope=note.scope,
                    client_id=scope.client_id if note.scope == "client" else None,
                    text=note.text,
                    source_turn_id=source_turn_id,
                    created_by="lead",
                    created_at=now,
                )
            )
            applied["remembered"].append(memory_id)
        if update_.forget:
            reachable = set(
                self._session.scalars(
                    select(ResearcherLeadMemoryRow.memory_id).where(
                        *self._note_filter(lead, scope),
                        ResearcherLeadMemoryRow.memory_id.in_(list(update_.forget)),
                    )
                ).all()
            )
            if reachable:
                self._session.execute(
                    update(ResearcherLeadMemoryRow)
                    .where(
                        ResearcherLeadMemoryRow.memory_id.in_(sorted(reachable)),
                        ResearcherLeadMemoryRow.forgotten_at.is_(None),
                    )
                    .values(forgotten_at=now)
                )
            applied["forgotten"] = [m for m in update_.forget if m in reachable]
        if (
            any(applied.get(f) for f in ("name", "soul", "user"))
            or applied["remembered"]
            or (applied["forgotten"])
        ):
            lead.updated_at = now
        self._session.flush()
        return SelfUpdateApplied(**applied)


#: How long a sealed Lead is kept before it is erased (the product owner, 2026-10-22).
SEAL_DAYS = 30


@dataclass(frozen=True, slots=True)
class LeadSeal:
    """A member's sealed Lead: when it was sealed and when it is erased."""

    user_id: str
    sealed_at: datetime
    erase_after: datetime


@dataclass(frozen=True, slots=True)
class ErasedLead:
    """What the retention sweep erased of one sealed Lead: counts, never content."""

    organization_id: str
    user_id: str
    lead_id: str
    revisions: int
    notes: int


class LeadSeals:
    """Sealing a deactivated member's Lead, and erasing it after :data:`SEAL_DAYS`
    (ADR 0030, settings-backends SB2).

    Sealing and unsealing are an organization OWNER's or ADMIN's, on a member of their own
    organization; they read and change only the seal, never the Lead's content. Erasure is
    the retention sweep's, an operator command with no request behind it.
    """

    def __init__(self, session: Session, admin: OrganizationContext) -> None:
        admin.require_administer()
        self._session, self._admin = session, admin

    def _row(self, user_id: str) -> ResearcherLeadRow | None:
        return self._session.scalar(
            select(ResearcherLeadRow)
            .where(
                ResearcherLeadRow.organization_id == self._admin.organization_id,
                ResearcherLeadRow.user_id == user_id,
            )
            .with_for_update()
        )

    def _audit(self, action: str, user_id: str, **payload: Any) -> None:
        self._session.add(
            AccessAuditRow(
                organization_id=self._admin.organization_id,
                subject_user_id=user_id,
                actor_id=self._admin.actor_id,
                action=action,
                payload=dict(payload),
                request_id=self._admin.request_id,
            )
        )

    def seal(self, user_id: str, *, now: datetime) -> LeadSeal | None:
        """Seal the member's Lead, if they hatched one; a sealed one keeps its dates."""
        row = self._row(user_id)
        if row is None:
            return None
        if row.sealed_at is None:
            row.sealed_at, row.erase_after = now, now + timedelta(days=SEAL_DAYS)
            self._audit("LEAD_SEALED", user_id, erase_after=row.erase_after.isoformat())
            self._session.flush()
        assert row.erase_after is not None
        return LeadSeal(user_id, as_utc(row.sealed_at), as_utc(row.erase_after))

    def unseal(self, user_id: str, *, now: datetime) -> bool:
        """Unseal the member's Lead on their reactivation; ``False`` when there is none to
        unseal (never hatched, or already erased) and when it is past its date: a Lead due for
        erasure never comes back, whether or not the sweep has reached it."""
        row = self._row(user_id)
        if row is None or row.sealed_at is None:
            return False
        if row.erase_after is not None and as_utc(row.erase_after) <= now:
            return False
        row.sealed_at, row.erase_after = None, None
        self._audit("LEAD_UNSEALED", user_id)
        self._session.flush()
        return True

    def seals(self) -> dict[str, LeadSeal]:
        """Every sealed Lead of the organization, by member."""
        rows = self._session.scalars(
            select(ResearcherLeadRow).where(
                ResearcherLeadRow.organization_id == self._admin.organization_id,
                ResearcherLeadRow.sealed_at.is_not(None),
            )
        ).all()
        return {
            r.user_id: LeadSeal(r.user_id, as_utc(r.sealed_at), as_utc(r.erase_after))
            for r in rows
            if r.sealed_at is not None and r.erase_after is not None
        }

    @staticmethod
    def due(session: Session, *, now: datetime) -> list[tuple[str, str, str]]:
        """The sealed Leads past their date, as ``(organization_id, user_id, lead_id)``."""
        rows = session.execute(
            select(
                ResearcherLeadRow.organization_id,
                ResearcherLeadRow.user_id,
                ResearcherLeadRow.lead_id,
            ).where(
                ResearcherLeadRow.sealed_at.is_not(None),
                ResearcherLeadRow.erase_after <= now,
            )
        ).all()
        return [(o, u, lead) for o, u, lead in rows]

    @staticmethod
    def erase(session: Session, *, lead_id: str) -> ErasedLead | None:
        """Erase one sealed Lead: its files, their history and its notes. Audited with
        counts only. A Lead unsealed meanwhile is left alone (``None``)."""
        row = session.scalar(
            select(ResearcherLeadRow)
            .where(ResearcherLeadRow.lead_id == lead_id, ResearcherLeadRow.sealed_at.is_not(None))
            .with_for_update()
        )
        if row is None:
            return None
        revisions = session.scalar(
            select(func.count()).where(ResearcherLeadRevisionRow.lead_id == lead_id)
        )
        notes = session.scalar(
            select(func.count()).where(ResearcherLeadMemoryRow.lead_id == lead_id)
        )
        session.execute(
            delete(ResearcherLeadRevisionRow).where(ResearcherLeadRevisionRow.lead_id == lead_id)
        )
        session.execute(
            delete(ResearcherLeadMemoryRow).where(ResearcherLeadMemoryRow.lead_id == lead_id)
        )
        erased = ErasedLead(row.organization_id, row.user_id, lead_id, revisions or 0, notes or 0)
        session.delete(row)
        session.add(
            AccessAuditRow(
                organization_id=erased.organization_id,
                subject_user_id=erased.user_id,
                actor_id="system:lead-retention",
                action="LEAD_ERASED",
                payload={"revisions": erased.revisions, "notes": erased.notes},
            )
        )
        session.flush()
        return erased


def erase_client_notes(session: Session, *, client_id: str) -> int:
    """Delete every researcher's Lead note kept for a deleted client (settings-backends SB5).
    The caller owns the transaction. Returns the notes deleted."""
    result = session.execute(
        delete(ResearcherLeadMemoryRow).where(ResearcherLeadMemoryRow.client_id == client_id)
    )
    session.flush()
    return int(getattr(result, "rowcount", 0) or 0)
