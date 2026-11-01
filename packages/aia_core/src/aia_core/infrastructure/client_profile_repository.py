"""Persistence for a client's profile and contacts (client-workspace C5).

The only module that reads or writes ``client_contacts`` and the profile columns of
``clients`` (`make layer_check`). Every call takes an issued ``ClientContext`` and the
client is in the query itself. Reading needs ``VIEW_CLIENT``; changing needs
``EDIT_CLIENT_PROFILE``. Every change writes an ``access_audit`` row, which is also what
the profile's history reads back. No study context and no model request reads anything
here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..domain.client_profile import ClientContact, ClientProfile, ContactDraft, new_contact_id
from ..domain.scope import ClientContext, ClientPermission, ScopeDenied
from .scope_repository import member_display_names
from .tables import AccessAuditRow, ClientContactRow, ClientRow, as_utc, utcnow

__all__ = [
    "PROFILE_ACTIONS",
    "ClientProfileRepository",
    "ProfileChange",
    "RuleChange",
    "erase_client_profile",
]

#: The audit actions that make up a profile's history: the profile and its contacts, and
#: the client's budget and rules (client-pages-redesign CPR3).
PROFILE_ACTIONS: Final = (
    "CLIENT_PROFILE_CHANGED",
    "CLIENT_CONTACT_ADDED",
    "CLIENT_CONTACT_CHANGED",
    "CLIENT_CONTACT_REMOVED",
    "CLIENT_BUDGET_CHANGED",
    "CLIENT_RULES_CHANGED",
    "SELF_APPROVAL_CONFIGURED",
)
#: The budget's changes are read only by a caller who may read the budget. The rules (data
#: posture and wallet ceiling) are read by any member (client_rules), so their changes are too.
_COST_ACTIONS: Final = frozenset({"CLIENT_BUDGET_CHANGED"})
_MAX_CONTACTS: Final = 100


RuleValue = str | float | bool | None


class RuleChange(BaseModel):
    """One field of the client's budget or rules, from what to what, as the audit kept it.

    ``before_known`` is false where the audit did not record the earlier value (a
    self-approval change keeps only the new one): unknown, never a guessed ``before``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    before: RuleValue = None
    after: RuleValue = None
    before_known: bool = True


def _value(raw: object) -> tuple[RuleValue, bool]:
    """A stored value as a history may carry it, and whether it could be read at all."""
    if raw is None or isinstance(raw, str | bool):
        return raw, True
    if isinstance(raw, int | float):
        return float(raw), True
    return None, False


def _amount(raw: str) -> tuple[float | None, bool]:
    """One side of a budget change's ``"<before> -> <after>"`` reason, as ``str()`` wrote it."""
    if raw == "None":
        return None, True
    try:
        return float(raw), True
    except ValueError:
        return None, False


class ProfileChange(BaseModel):
    """One entry of a profile's history: what changed, who changed it, when."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: str
    actor_id: str | None
    #: The actor's display name as a member of the organization, never an e-mail; None
    #: when there is no such name, for the reader to say in words.
    actor_name: str | None = None
    at: datetime | None
    #: The profile fields that changed, or the contact's name.
    fields: tuple[str, ...] = ()
    contact_name: str | None = None
    #: The budget's or a rule's fields, from what to what.
    changes: tuple[RuleChange, ...] = ()


def _rule_changes(row: AccessAuditRow) -> tuple[RuleChange, ...]:
    """What a budget or rules entry changed, read from its audit row as written."""
    payload = row.payload or {}
    if row.action == "CLIENT_RULES_CHANGED":
        changes = []
        for name, moved in payload.items():
            if not isinstance(moved, dict):
                continue
            before, before_ok = _value(moved.get("from"))
            after, after_ok = _value(moved.get("to"))
            if before_ok and after_ok:
                changes.append(RuleChange(field=name, before=before, after=after))
        return tuple(changes)
    if row.action == "SELF_APPROVAL_CONFIGURED":
        allowed = payload.get("allow_self_approval")
        if allowed is not None and not isinstance(allowed, bool):
            return ()
        # None clears the client's own rule: it inherits the organization's, said as such.
        return (
            RuleChange(
                field="allow_self_approval",
                after="inherit" if allowed is None else allowed,
                before_known=False,
            ),
        )
    if row.action == "CLIENT_BUDGET_CHANGED":
        sides = (row.reason or "").split(" -> ")
        if len(sides) != 2:
            return ()
        (before, before_ok), (after, after_ok) = _amount(sides[0]), _amount(sides[1])
        if not (before_ok and after_ok) or after is None:
            return ()
        return (RuleChange(field="budget_usd", before=before, after=after),)
    return ()


def _client(scope: object) -> ClientContext:
    if not isinstance(scope, ClientContext):
        raise ScopeDenied("a client profile requires a client context", reason="forged_scope")
    return scope


def _contact(row: ClientContactRow) -> ClientContact:
    return ClientContact(
        contact_id=row.contact_id,
        client_id=row.client_id,
        name=row.name,
        role=row.role,
        email=row.email,
        receives_reports=row.receives_reports,
    )


class ClientProfileRepository:
    """Reads and changes one client's profile and contacts. The caller owns the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _client_row(self, scope: ClientContext) -> ClientRow:
        row = self._session.scalar(
            select(ClientRow).where(
                ClientRow.client_id == scope.client_id,
                ClientRow.organization_id == scope.organization_id,
            )
        )
        if row is None:
            raise ScopeDenied("not found", reason="unknown_client")
        return row

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

    # ----------------------------------------------------------------- profile

    def profile(self, scope: ClientContext) -> ClientProfile:
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT)
        row = self._client_row(scope)
        return ClientProfile(
            short_code=row.short_code,
            industry=row.industry,
            market=row.market,
            description=row.description,
        )

    def update_profile(self, scope: ClientContext, profile: ClientProfile) -> ClientProfile:
        """Replace the profile. Writes history only when something changed."""
        scope = _client(scope)
        scope.require(ClientPermission.EDIT_CLIENT_PROFILE)
        row = self._client_row(scope)
        changed = [
            name
            for name in ("short_code", "industry", "market", "description")
            if getattr(row, name) != getattr(profile, name)
        ]
        if changed:
            for name in changed:
                setattr(row, name, getattr(profile, name))
            self._audit(scope, "CLIENT_PROFILE_CHANGED", {"fields": changed})
            self._session.flush()
        return self.profile(scope)

    # ---------------------------------------------------------------- contacts

    def contacts(self, scope: ClientContext) -> list[ClientContact]:
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT)
        rows = self._session.scalars(
            select(ClientContactRow).where(
                ClientContactRow.organization_id == scope.organization_id,
                ClientContactRow.client_id == scope.client_id,
            )
        ).all()
        return sorted((_contact(r) for r in rows), key=lambda c: c.name.casefold())

    def _contact_row(self, scope: ClientContext, contact_id: str) -> ClientContactRow:
        row = self._session.scalar(
            select(ClientContactRow).where(
                ClientContactRow.contact_id == contact_id,
                ClientContactRow.organization_id == scope.organization_id,
                ClientContactRow.client_id == scope.client_id,
            )
        )
        if row is None:
            raise ScopeDenied("not found", reason="unknown_contact")
        return row

    def add_contact(self, scope: ClientContext, draft: ContactDraft) -> ClientContact:
        scope = _client(scope)
        scope.require(ClientPermission.EDIT_CLIENT_PROFILE)
        if len(self.contacts(scope)) >= _MAX_CONTACTS:
            raise ValueError(f"a client keeps at most {_MAX_CONTACTS} contacts")
        row = ClientContactRow(
            contact_id=new_contact_id(),
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            name=draft.name,
            role=draft.role,
            email=draft.email,
            receives_reports=draft.receives_reports,
            created_by=scope.actor_id,
            created_at=utcnow(),
        )
        self._session.add(row)
        # The history names the contact, never their e-mail.
        self._audit(
            scope, "CLIENT_CONTACT_ADDED", {"contact_id": row.contact_id, "name": draft.name}
        )
        self._session.flush()
        return _contact(row)

    def update_contact(
        self, scope: ClientContext, *, contact_id: str, draft: ContactDraft
    ) -> ClientContact:
        scope = _client(scope)
        scope.require(ClientPermission.EDIT_CLIENT_PROFILE)
        row = self._contact_row(scope, contact_id)
        row.name, row.role, row.email = draft.name, draft.role, draft.email
        row.receives_reports = draft.receives_reports
        self._audit(scope, "CLIENT_CONTACT_CHANGED", {"contact_id": contact_id, "name": draft.name})
        self._session.flush()
        return _contact(row)

    def remove_contact(self, scope: ClientContext, *, contact_id: str) -> None:
        scope = _client(scope)
        scope.require(ClientPermission.EDIT_CLIENT_PROFILE)
        row = self._contact_row(scope, contact_id)
        self._audit(scope, "CLIENT_CONTACT_REMOVED", {"contact_id": contact_id, "name": row.name})
        self._session.delete(row)
        self._session.flush()

    # ----------------------------------------------------------------- history

    def history(self, scope: ClientContext, *, limit: int = 50) -> list[ProfileChange]:
        """The profile's changes, newest first, from the audit, each naming who made it.

        The client's budget changes are listed only for a caller who may read the budget
        (``VIEW_CLIENT_COSTS``); a self-approval change only when it was set for this client,
        not for one of its studies.
        """
        scope = _client(scope)
        scope.require(ClientPermission.VIEW_CLIENT)
        actions = [
            a
            for a in PROFILE_ACTIONS
            if a not in _COST_ACTIONS or scope.has(ClientPermission.VIEW_CLIENT_COSTS)
        ]
        rows = self._session.scalars(
            select(AccessAuditRow)
            .where(
                AccessAuditRow.organization_id == scope.organization_id,
                AccessAuditRow.client_id == scope.client_id,
                AccessAuditRow.action.in_(actions),
                or_(
                    AccessAuditRow.action != "SELF_APPROVAL_CONFIGURED",
                    AccessAuditRow.study_id.is_(None),
                ),
            )
            .order_by(AccessAuditRow.event_id.desc())
            .limit(max(1, min(limit, 100)))
        ).all()
        names = member_display_names(
            self._session, scope.organization_id, sorted({r.actor_id for r in rows if r.actor_id})
        )
        return [
            ProfileChange(
                action=r.action,
                actor_id=r.actor_id,
                actor_name=names.get(r.actor_id) if r.actor_id else None,
                at=as_utc(r.created_at) if r.created_at else None,
                fields=tuple((r.payload or {}).get("fields", ())),
                contact_name=(r.payload or {}).get("name"),
                changes=_rule_changes(r),
            )
            for r in rows
        ]


def erase_client_profile(session: Session, *, client_id: str) -> int:
    """A deleted client's contacts deleted and its profile emptied (settings-backends SB5).
    The caller owns the transaction. Returns the contacts deleted."""
    contacts = session.scalars(
        select(ClientContactRow).where(ClientContactRow.client_id == client_id)
    ).all()
    for contact in contacts:
        session.delete(contact)
    client = session.get(ClientRow, client_id)
    if client is not None:
        client.short_code = client.industry = client.market = client.description = ""
        client.reference = ""
    session.flush()
    return len(contacts)
