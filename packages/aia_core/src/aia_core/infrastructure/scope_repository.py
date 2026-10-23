"""Persistence for organizations, users, clients, studies and grants.

Administrative reads and writes take an :class:`OrganizationContext`; anything
that touches a specific study takes a :class:`StudyContext`. Neither can be
forged, so there is no code path here that operates without an authorisation
decision having already been made.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.content_free import content_free, rename
from ..domain.scope import (
    Client,
    ClientBudget,
    ClientContext,
    ClientPermission,
    ClientStatus,
    Organization,
    OrganizationContext,
    OrganizationMembership,
    OrganizationRole,
    Permission,
    ScopeDenied,
    SelfApprovalPolicy,
    Study,
    StudyContext,
    StudyKind,
    StudyStatus,
    new_client_id,
    new_organization_id,
    new_study_id,
    new_user_id,
    resolve_self_approval_policy,
)
from ..domain.workflow import ReservationStatus
from .tables import (
    AccessAuditRow,
    BudgetReservationRow,
    ClientDeletionObjectRow,
    ClientDeletionTicketRow,
    ClientRow,
    OrganizationMemberRow,
    OrganizationRow,
    StudyRow,
    UserRow,
    as_utc,
    utcnow,
)

__all__ = ["ScopeRepository", "SubjectMismatch"]


def _client_to_domain(row: ClientRow) -> Client:
    return Client(
        client_id=row.client_id,
        organization_id=row.organization_id,
        slug=row.slug,
        name=row.name,
        status=ClientStatus(row.status),
        reference=row.reference,
        allow_self_approval=row.allow_self_approval,
        short_code=row.short_code,
        industry=row.industry,
        market=row.market,
        description=row.description,
        created_at=row.created_at,
        modified_at=row.modified_at,
    )


def _study_to_domain(row: StudyRow) -> Study:
    return Study(
        study_id=row.study_id,
        organization_id=row.organization_id,
        client_id=row.client_id,
        slug=row.slug,
        name=row.name,
        kind=StudyKind(row.kind),
        status=StudyStatus(row.status),
        budget_usd=row.budget_usd,
        spent_usd=row.spent_usd,
        spend_confirm_usd=row.spend_confirm_usd,
        allow_self_approval=row.allow_self_approval,
        created_at=row.created_at,
        modified_at=row.modified_at,
        delivered_at=row.delivered_at,
    )


class SubjectMismatch(Exception):
    """A sign-in's subject differs from the one the e-mail's record is bound to."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"user {user_id} is bound to another identity-provider subject")
        self.user_id = user_id


class ScopeRepository:
    """Reads and writes the scope graph.

    The caller owns the transaction; this class flushes but never commits.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------- bootstrap / provisioning

    def create_organization(
        self, *, slug: str, name: str, owner_email: str, owner_name: str = ""
    ) -> tuple[Organization, OrganizationMembership]:
        """Create an organization and its first OWNER.

        This is the only unauthenticated write in the codebase, because it is the
        bootstrap that creates the first principal. It is not exposed over HTTP;
        it runs from a provisioning command.
        """
        org = Organization(organization_id=new_organization_id(), slug=slug, name=name)
        self._session.add(
            OrganizationRow(organization_id=org.organization_id, slug=org.slug, name=org.name)
        )

        user = self.upsert_user(email=owner_email, display_name=owner_name)
        self._session.add(
            OrganizationMemberRow(
                organization_id=org.organization_id,
                user_id=user["user_id"],
                role=OrganizationRole.OWNER.value,
            )
        )
        self._session.add(
            AccessAuditRow(
                organization_id=org.organization_id,
                subject_user_id=user["user_id"],
                actor_id=user["user_id"],
                action="ORGANIZATION_CREATED",
                role=OrganizationRole.OWNER.value,
            )
        )
        self._session.flush()
        return org, OrganizationMembership(
            organization_id=org.organization_id,
            user_id=user["user_id"],
            role=OrganizationRole.OWNER,
        )

    def upsert_user(
        self,
        *,
        email: str,
        display_name: str = "",
        external_subject: str | None = None,
    ) -> dict[str, Any]:
        """Find or create a user by identity-provider subject, else by email.

        Matching on ``external_subject`` first matters: it is the identity
        provider's immutable claim, so a user who changes their email address
        keeps their identity and their work rather than acquiring a second
        account. Email is the fallback for a user provisioned before their first
        sign-in.
        """
        row: UserRow | None = None
        if external_subject:
            row = self._session.scalar(
                select(UserRow).where(UserRow.external_subject == external_subject)
            )
        if row is None:
            row = self._session.scalar(
                select(UserRow).where(UserRow.email == email.strip().lower())
            )
            # The e-mail fallback binds a subject once. A record already bound to
            # another subject belongs to that subject: an address reassigned in the
            # directory, or a second provider asserting it, is someone else.
            if (
                row is not None
                and external_subject
                and row.external_subject
                and row.external_subject != external_subject
            ):
                raise SubjectMismatch(row.user_id)

        if row is None:
            row = UserRow(
                user_id=new_user_id(),
                email=email.strip().lower(),
                display_name=display_name or email.split("@")[0],
                external_subject=external_subject,
            )
            self._session.add(row)
        else:
            # Bind the subject on first federated sign-in of a pre-provisioned
            # user, and keep the display name fresh from the directory.
            if external_subject and not row.external_subject:
                row.external_subject = external_subject
            if display_name:
                row.display_name = display_name
            row.last_seen_at = utcnow()

        self._session.flush()
        return {
            "user_id": row.user_id,
            "email": row.email,
            "display_name": row.display_name,
            "external_subject": row.external_subject,
            "is_active": row.is_active,
        }

    def record_subject_mismatch(self, *, user_id: str, request_id: str | None = None) -> None:
        """Audit a refused sign-in as ``user_id`` (``SubjectMismatch``), in each organization.

        The presented subject is not recorded: it is another person's identifier.
        """
        for organization_id in self.memberships_for_user(user_id, include_deactivated=True):
            self._session.add(
                AccessAuditRow(
                    organization_id=organization_id,
                    subject_user_id=user_id,
                    actor_id=None,
                    action="AIA_SESSION_DENIED",
                    reason="identity_mismatch",
                    request_id=request_id,
                )
            )
        self._session.flush()

    def clear_subject(self, admin: OrganizationContext, *, user_id: str) -> None:
        """Unbind a member's identity-provider subject, so their next sign-in binds by e-mail.

        For a person whose subject genuinely changed (a Cognito user re-created, an
        account re-federated), refused ``identity_mismatch`` until an administrator who
        has confirmed it is the same person clears it. Only a member of the
        administrator's own organization; audited.
        """
        admin.require_administer()
        if admin.organization_id not in self.memberships_for_user(
            user_id, include_deactivated=True
        ):
            raise ScopeDenied("not a member of this organization", reason="unknown_user")
        row = self._session.scalar(select(UserRow).where(UserRow.user_id == user_id))
        if row is None:  # pragma: no cover - a membership names an existing user
            raise ScopeDenied("not found", reason="unknown_user")
        row.external_subject = None
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                subject_user_id=user_id,
                actor_id=admin.actor_id,
                action="IDENTITY_SUBJECT_CLEARED",
                request_id=admin.request_id,
            )
        )
        self._session.flush()

    def memberships_for_user(self, user_id: str, *, include_deactivated: bool = False) -> list[str]:
        """Return the organization ids a user belongs to: those they may sign in to, a
        membership deactivated there left out (D-27), unless ``include_deactivated``.

        Used during authentication to decide which organization a request is for.
        Returning a list rather than a single id keeps the door open for a
        consultant who works across two AIA organizations without special-casing
        it later.
        """
        return sorted(
            self._session.scalars(
                select(OrganizationMemberRow.organization_id).where(
                    OrganizationMemberRow.user_id == user_id,
                    *(
                        ()
                        if include_deactivated
                        else (OrganizationMemberRow.deactivated_at.is_(None),)
                    ),
                )
            ).all()
        )

    def add_member(
        self,
        admin: OrganizationContext,
        *,
        email: str,
        role: OrganizationRole = OrganizationRole.MEMBER,
        display_name: str = "",
    ) -> OrganizationMembership:
        """Add a user to the organization, or change a member's role.

        Only an OWNER grants or removes OWNER, and the last OWNER is never demoted (the
        product owner's decision, security-audit-2026-10 S14).
        """
        admin.require_administer()
        user = self.upsert_user(email=email, display_name=display_name)

        existing = self._session.scalar(
            select(OrganizationMemberRow).where(
                OrganizationMemberRow.organization_id == admin.organization_id,
                OrganizationMemberRow.user_id == user["user_id"],
            )
        )
        previous = existing.role if existing is not None else None
        self._guard_owner(admin, previous=previous, role=role.value)
        if existing is not None:
            existing.role = role.value
        else:
            self._session.add(
                OrganizationMemberRow(
                    organization_id=admin.organization_id,
                    user_id=user["user_id"],
                    role=role.value,
                )
            )

        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                subject_user_id=user["user_id"],
                actor_id=admin.actor_id,
                action="MEMBER_ADDED",
                role=role.value,
                payload={"from": previous, "to": role.value},
                request_id=admin.request_id,
            )
        )
        self._session.flush()
        return OrganizationMembership(
            organization_id=admin.organization_id, user_id=user["user_id"], role=role
        )

    def record_role_denied(
        self,
        admin: OrganizationContext,
        *,
        email: str = "",
        user_id: str | None = None,
        role: str,
        reason: str,
        change: str | None = None,
    ) -> None:
        """Audit a refused role change (``owner_only`` / ``last_owner``): the attempt is the
        security-relevant event. The caller commits it after rolling the refused change back,
        so a refused grant to a new address leaves no user behind. The person is the row's
        subject when known (``user_id``, else found by ``email``); the address is not recorded
        (as ``record_subject_mismatch``). ``change`` names a refused deactivation or
        reactivation (``deactivate`` / ``reactivate``) of an OWNER, kept in the payload."""
        subject = user_id
        if subject is None:
            address = email.strip().lower()
            subject = self._session.scalar(select(UserRow.user_id).where(UserRow.email == address))
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                subject_user_id=subject,
                actor_id=admin.actor_id,
                action="MEMBER_ROLE_DENIED",
                role=role,
                reason=reason,
                payload={"change": change} if change else {},
                request_id=admin.request_id,
            )
        )
        self._session.flush()

    def _guard_owner(
        self, admin: OrganizationContext, *, previous: str | None, role: str | None
    ) -> None:
        """Refuse a change that grants or removes OWNER unless an OWNER makes it, and any
        that would leave the organization with no OWNER. ``role`` None: removed."""
        owner = OrganizationRole.OWNER.value
        if (previous == owner) == (role == owner):
            return  # OWNER neither granted nor removed
        if admin.organization_role is not OrganizationRole.OWNER:
            raise ScopeDenied("only an OWNER grants or removes OWNER", reason="owner_only")
        if previous == owner:
            # The organization row is locked first: two owners demoting each other under READ
            # COMMITTED would otherwise each count the other and both commit, leaving none.
            # The second waits here, then counts what the first committed.
            self._session.execute(
                select(OrganizationRow.organization_id)
                .where(OrganizationRow.organization_id == admin.organization_id)
                .with_for_update()
            )
            # Active owners only: a deactivated OWNER cannot sign in to administer.
            owners = self._session.scalar(
                select(func.count())
                .select_from(OrganizationMemberRow)
                .join(UserRow, UserRow.user_id == OrganizationMemberRow.user_id)
                .where(
                    OrganizationMemberRow.organization_id == admin.organization_id,
                    OrganizationMemberRow.role == owner,
                    OrganizationMemberRow.deactivated_at.is_(None),
                    UserRow.is_active.is_(True),
                )
            )
            if (owners or 0) <= 1:
                raise ScopeDenied("the organization's last OWNER", reason="last_owner")

    def deactivate_user(self, admin: OrganizationContext, *, user_id: str) -> None:
        """Deactivate an account.

        Deactivation is checked on every scope resolution, so it takes effect
        immediately even while a valid token is still in circulation.
        """
        admin.require_administer()
        # The target is resolved through the acting admin's own organization (S15): a user
        # who is not a member here is not found, whatever other organization they are in.
        membership = self._session.scalar(
            select(OrganizationMemberRow.role).where(
                OrganizationMemberRow.organization_id == admin.organization_id,
                OrganizationMemberRow.user_id == user_id,
            )
        )
        if membership is None:
            raise ScopeDenied("not found", reason="not_a_member")
        row = self._session.scalar(select(UserRow).where(UserRow.user_id == user_id))
        if row is None:
            raise ScopeDenied("not found", reason="unknown_user")
        self._guard_owner(admin, previous=membership, role=None)
        row.is_active = False
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                subject_user_id=user_id,
                actor_id=admin.actor_id,
                action="USER_DEACTIVATED",
                request_id=admin.request_id,
            )
        )
        self._session.flush()

    def _member_row(self, admin: OrganizationContext, user_id: str) -> OrganizationMemberRow:
        """A member of the admin's own organization, locked, or ``not_a_member`` (S15).

        The organization row is locked first, in the order ``add_member`` takes them through
        ``_guard_owner``: a deactivation and a role change of the same OWNER, the other way
        round, would each hold the lock the other waits for.
        """
        self._session.execute(
            select(OrganizationRow.organization_id)
            .where(OrganizationRow.organization_id == admin.organization_id)
            .with_for_update()
        )
        row = self._session.scalar(
            select(OrganizationMemberRow)
            .where(
                OrganizationMemberRow.organization_id == admin.organization_id,
                OrganizationMemberRow.user_id == user_id,
            )
            .with_for_update()
        )
        if row is None:
            raise ScopeDenied("not found", reason="not_a_member")
        return row

    def deactivate_member(self, admin: OrganizationContext, *, user_id: str, now: datetime) -> bool:
        """Deactivate a member in the admin's own organization (D-27).

        Only this membership: the account and any other organization are untouched. The
        member resolves no scope here from the next request, whatever token they hold. The
        OWNER rule and the last active OWNER hold (security-audit S14). Returns whether it
        changed anything; deactivating a deactivated member changes nothing.
        """
        admin.require_administer()
        row = self._member_row(admin, user_id)
        if row.deactivated_at is not None:
            return False
        self._guard_owner(admin, previous=row.role, role=None)
        row.deactivated_at, row.deactivated_by = now, admin.actor_id
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                subject_user_id=user_id,
                actor_id=admin.actor_id,
                action="MEMBER_DEACTIVATED",
                role=row.role,
                request_id=admin.request_id,
            )
        )
        self._session.flush()
        return True

    def reactivate_member(self, admin: OrganizationContext, *, user_id: str) -> bool:
        """Reactivate a member deactivated in the admin's own organization. Granting an OWNER
        back is the OWNER rule's (only an OWNER restores an OWNER). Returns whether it changed
        anything."""
        admin.require_administer()
        row = self._member_row(admin, user_id)
        if row.deactivated_at is None:
            return False
        if row.role == OrganizationRole.OWNER.value and (
            admin.organization_role is not OrganizationRole.OWNER
        ):
            raise ScopeDenied("only an OWNER grants or removes OWNER", reason="owner_only")
        row.deactivated_at, row.deactivated_by = None, None
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                subject_user_id=user_id,
                actor_id=admin.actor_id,
                action="MEMBER_REACTIVATED",
                role=row.role,
                request_id=admin.request_id,
            )
        )
        self._session.flush()
        return True

    # ------------------------------------------------------------------ clients

    def create_client(
        self, admin: OrganizationContext, *, slug: str, name: str, reference: str = ""
    ) -> Client:
        """Create a client: any member of the organization may (ADR 0019).

        A client is research work, not system administration, so it needs no OWNER or
        ADMIN role (the owner's decision, 2026-10-05). The context exists only for an
        active member of the organization; the creation is audited with its actor.
        Changing a client's status stays with administration (:meth:`set_client_status`).
        """
        client = Client(
            client_id=new_client_id(),
            organization_id=admin.organization_id,
            slug=slug,
            name=name,
            reference=reference,
        )
        self._session.add(
            ClientRow(
                client_id=client.client_id,
                organization_id=client.organization_id,
                slug=client.slug,
                name=client.name,
                status=client.status.value,
                reference=client.reference,
            )
        )
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                client_id=client.client_id,
                actor_id=admin.actor_id,
                action="CLIENT_CREATED",
                request_id=admin.request_id,
            )
        )
        self._session.flush()
        return client

    def get_client(self, admin: OrganizationContext, client_id: str) -> Client:
        """Return a client within the administrator's organization."""
        row = self._session.scalar(
            select(ClientRow).where(
                ClientRow.client_id == client_id,
                ClientRow.organization_id == admin.organization_id,
            )
        )
        if row is None:
            raise ScopeDenied("not found", reason="unknown_client")
        return _client_to_domain(row)

    def list_clients(
        self, admin: OrganizationContext, *, include_archived: bool = False
    ) -> list[Client]:
        """List clients in the organization.

        This is administrative metadata -- names and slugs, no research content --
        so organization membership is sufficient. Reading a client's *studies*
        still requires a grant.
        """
        stmt = select(ClientRow).where(
            ClientRow.organization_id == admin.organization_id,
            ClientRow.deleted_at.is_(None),  # a deleted client is a tombstone, never listed
        )
        if not include_archived:
            stmt = stmt.where(ClientRow.status != ClientStatus.ARCHIVED.value)
        rows = self._session.scalars(stmt.order_by(ClientRow.name)).all()
        return [_client_to_domain(r) for r in rows]

    def set_client_status(
        self, admin: OrganizationContext, *, client_id: str, status: ClientStatus
    ) -> Client:
        """Change a client's lifecycle status."""
        admin.require_administer()
        row = self._session.scalar(
            select(ClientRow).where(
                ClientRow.client_id == client_id,
                ClientRow.organization_id == admin.organization_id,
            )
        )
        if row is None or row.deleted_at is not None:
            # A deleted client is not reopened: its content is gone (settings-backends SB5).
            raise ScopeDenied("not found", reason="unknown_client")
        row.status = status.value
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                client_id=client_id,
                actor_id=admin.actor_id,
                action="CLIENT_STATUS_CHANGED",
                reason=status.value,
                request_id=admin.request_id,
            )
        )
        self._session.flush()
        return _client_to_domain(row)

    # ------------------------------------------------------- client deletion (SB5) --

    def _deletable(self, admin: OrganizationContext, client_id: str) -> ClientRow:
        admin.require_administer()
        row = self._session.scalar(
            select(ClientRow).where(
                ClientRow.client_id == client_id,
                ClientRow.organization_id == admin.organization_id,
            )
        )
        if row is None:
            raise ScopeDenied("not found", reason="unknown_client")
        return row

    def client_for_deletion(self, admin: OrganizationContext, client_id: str) -> Client | None:
        """The client an OWNER or ADMIN may delete, in their own organization (else
        ``unknown_client``); ``None`` when it is already deleted."""
        row = self._deletable(admin, client_id)
        return None if row.deleted_at is not None else _client_to_domain(row)

    def client_study_ids(self, admin: OrganizationContext, client_id: str) -> list[str]:
        self._deletable(admin, client_id)
        return sorted(
            self._session.scalars(select(StudyRow.study_id).where(StudyRow.client_id == client_id))
        )

    def client_audit_rows(self, admin: OrganizationContext, client_id: str) -> int:
        """How many audit rows name the client: what a deletion keeps."""
        self._deletable(admin, client_id)
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(AccessAuditRow)
                .where(
                    AccessAuditRow.organization_id == admin.organization_id,
                    AccessAuditRow.client_id == client_id,
                )
            )
            or 0
        )

    def issue_deletion_ticket(
        self, admin: OrganizationContext, client_id: str, *, token: str, expires_at: datetime
    ) -> None:
        """Keep a one-time confirmation of this client's deletion, for this person, by the
        token's SHA-256 only."""
        self._deletable(admin, client_id)
        self._session.add(
            ClientDeletionTicketRow(
                token_sha256=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                organization_id=admin.organization_id,
                client_id=client_id,
                actor_id=admin.actor_id,
                expires_at=expires_at,
            )
        )
        self._session.flush()

    def spend_deletion_ticket(
        self, admin: OrganizationContext, client_id: str, *, token: str, now: datetime
    ) -> None:
        """Spend the confirmation: the same client, the same person, unspent and in time, or
        ``ScopeDenied`` ``confirmation_invalid`` / ``confirmation_expired``."""
        self._deletable(admin, client_id)
        query = select(ClientDeletionTicketRow).where(
            ClientDeletionTicketRow.token_sha256
            == hashlib.sha256(token.encode("utf-8")).hexdigest()
        )
        if self._session.get_bind().dialect.name == "postgresql":
            query = query.with_for_update()
        ticket = self._session.scalar(query)
        if (
            ticket is None
            or ticket.spent_at is not None
            or (ticket.organization_id, ticket.client_id, ticket.actor_id)
            != (admin.organization_id, client_id, admin.actor_id)
        ):
            raise ScopeDenied("confirmation does not match", reason="confirmation_invalid")
        if as_utc(ticket.expires_at) <= now:
            raise ScopeDenied("confirmation expired", reason="confirmation_expired")
        ticket.spent_at = now
        self._session.flush()

    def lock_client(self, admin: OrganizationContext, client_id: str) -> None:
        """Lock the client row for its deletion (FOR UPDATE on PostgreSQL): a status change, a
        budget lift or a second deletion of the same client waits for this one."""
        query = select(ClientRow.client_id).where(
            ClientRow.client_id == client_id,
            ClientRow.organization_id == admin.organization_id,
        )
        if self._session.get_bind().dialect.name == "postgresql":
            query = query.with_for_update()
        self._session.execute(query)

    def client_names(self, admin: OrganizationContext, client_id: str) -> dict[str, str]:
        """The client's and its studies' names, each to its id: what a deletion replaces."""
        row = self._deletable(admin, client_id)
        studies = self._session.execute(
            select(StudyRow.name, StudyRow.study_id).where(StudyRow.client_id == client_id)
        ).all()
        names = {row.name: row.client_id} | {str(n): str(i) for n, i in studies}
        return {k: v for k, v in names.items() if k and k != v}

    def keep_pending_objects(
        self, admin: OrganizationContext, client_id: str, keys: Sequence[str]
    ) -> None:
        """List a deleted client's stored objects still to delete, in the deletion's
        transaction, so a delete interrupted after its commit is retried."""
        for key in sorted(set(keys)):
            self._session.merge(
                ClientDeletionObjectRow(
                    client_id=client_id, storage_key=key, organization_id=admin.organization_id
                )
            )
        self._session.flush()

    def pending_objects(self, admin: OrganizationContext, client_id: str) -> list[str]:
        self._deletable(admin, client_id)
        return sorted(
            self._session.scalars(
                select(ClientDeletionObjectRow.storage_key).where(
                    ClientDeletionObjectRow.client_id == client_id,
                    ClientDeletionObjectRow.organization_id == admin.organization_id,
                )
            )
        )

    def clear_pending_object(self, admin: OrganizationContext, client_id: str, key: str) -> None:
        row = self._session.get(ClientDeletionObjectRow, (client_id, key))
        if row is not None and row.organization_id == admin.organization_id:
            self._session.delete(row)
            self._session.flush()

    def record_object_deletion(
        self, admin: OrganizationContext, client_id: str, *, deleted: int, failed: int
    ) -> None:
        """Audit how many of a deleted client's objects were deleted and how many are left."""
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                client_id=client_id,
                actor_id=admin.actor_id,
                action="CLIENT_DELETION_OBJECTS",
                role=admin.organization_role.value,
                payload={"deleted": deleted, "failed": failed},
                request_id=admin.request_id,
            )
        )
        self._session.flush()

    def tombstone_client(
        self,
        admin: OrganizationContext,
        client_id: str,
        *,
        now: datetime,
        counts: dict[str, int],
    ) -> None:
        """What stays of a deleted client: its row and its studies' rows, archived and named by
        their ids, so the kept ledgers still resolve; every kept audit row of the organization
        with the client's or a study's name in it reads the id instead. Audited CLIENT_DELETED
        with the counts, never a name."""
        row = self._deletable(admin, client_id)
        studies = self._session.scalars(
            select(StudyRow).where(StudyRow.client_id == client_id)
        ).all()
        names = {row.name: row.client_id} | {s.name: s.study_id for s in studies}
        names = {k: v for k, v in names.items() if k}
        for study in studies:
            study.name = study.study_id
            study.status = StudyStatus.ARCHIVED.value
        row.name = row.client_id
        row.status = ClientStatus.ARCHIVED.value
        row.deleted_at, row.deleted_by = now, admin.actor_id
        audit = self._session.scalars(
            select(AccessAuditRow).where(AccessAuditRow.organization_id == admin.organization_id)
        ).all()
        own = {client_id, *(s.study_id for s in studies)}
        for entry in audit:
            renamed = rename(entry.payload, names)
            if entry.client_id in own or entry.study_id in own:
                # The client's own rows are kept content-free (MVPQ-07): ids, codes, numbers
                # and times stay; any other text (a file name, a title) is erased.
                renamed = content_free(renamed)
            if renamed != entry.payload:
                entry.payload = renamed
            if entry.reason:
                entry.reason = rename(entry.reason, names)
            if entry.reason and (entry.client_id in own or entry.study_id in own):
                entry.reason = content_free(entry.reason)
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                client_id=client_id,
                actor_id=admin.actor_id,
                action="CLIENT_DELETED",
                role=admin.organization_role.value,
                payload=dict(counts),
                request_id=admin.request_id,
            )
        )
        self._session.flush()

    def kept_after_deletion(self, admin: OrganizationContext) -> tuple[int, int]:
        """The organization's audit rows and deleted clients' tombstones, OWNER or ADMIN."""
        admin.require_administer()
        audit = self._session.scalar(
            select(func.count())
            .select_from(AccessAuditRow)
            .where(AccessAuditRow.organization_id == admin.organization_id)
        )
        tombstones = self._session.scalar(
            select(func.count())
            .select_from(ClientRow)
            .where(
                ClientRow.organization_id == admin.organization_id,
                ClientRow.deleted_at.is_not(None),
            )
        )
        return int(audit or 0), int(tombstones or 0)

    # ------------------------------------------------------------------ studies

    def create_study(
        self,
        admin: OrganizationContext,
        *,
        client_id: str,
        slug: str,
        name: str,
        budget_usd: float = 0.0,
        kind: StudyKind = StudyKind.RESEARCH,
    ) -> Study:
        """Create a study under a client."""
        admin.require_administer()

        client = self._session.scalar(
            select(ClientRow).where(
                ClientRow.client_id == client_id,
                ClientRow.organization_id == admin.organization_id,
            )
        )
        if client is None:
            raise ScopeDenied("not found", reason="unknown_client")
        if client.status == ClientStatus.ARCHIVED.value:
            raise ScopeDenied(
                "cannot create a study for an archived client", reason="client_archived"
            )

        study = Study(
            study_id=new_study_id(),
            organization_id=admin.organization_id,
            client_id=client_id,
            slug=slug,
            name=name,
            kind=kind,
            budget_usd=budget_usd,
        )
        self._session.add(
            StudyRow(
                study_id=study.study_id,
                organization_id=study.organization_id,
                client_id=study.client_id,
                slug=study.slug,
                name=study.name,
                kind=study.kind.value,
                status=study.status.value,
                budget_usd=study.budget_usd,
            )
        )
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                client_id=client_id,
                study_id=study.study_id,
                actor_id=admin.actor_id,
                action="STUDY_CREATED",
                request_id=admin.request_id,
            )
        )
        self._session.flush()
        return study

    # ------------------------------------------------------- client workspace

    def get_client_in_scope(self, scope: ClientContext) -> Client:
        """The client a :class:`ClientContext` authorised; no id parameter to get wrong."""
        row = self._session.scalar(
            select(ClientRow).where(
                ClientRow.client_id == scope.client_id,
                ClientRow.organization_id == scope.organization_id,
            )
        )
        if row is None:
            raise ScopeDenied("not found", reason="unknown_client")
        return _client_to_domain(row)

    def _client_row(self, scope: ClientContext, *, for_update: bool = False) -> ClientRow:
        """The client in scope; ``for_update`` locks it and re-reads what is committed.

        A row already in this session would otherwise keep the value it was read with,
        so a change made meanwhile by another request would be compared and audited
        against a stale predecessor.
        """
        query = select(ClientRow).where(
            ClientRow.client_id == scope.client_id,
            ClientRow.organization_id == scope.organization_id,
        )
        if for_update:
            # Blocking FOR UPDATE on PostgreSQL (SQLite has none and serialises writers).
            query = query.with_for_update().execution_options(populate_existing=True)
        row = self._session.scalar(query)
        if row is None:
            raise ScopeDenied("not found", reason="unknown_client")
        return row

    def client_budget(self, scope: ClientContext, *, for_update: bool = False) -> ClientBudget:
        """What the client's own AI work may cost and where it stands (client-budget CB1).

        ``reserved_usd`` is what the client's own work holds now: its runs' open holds, which
        name no study. Never the studies' budgets or holds: those are theirs. ``for_update``
        locks the client row and reads it as committed, for a change decided on this value.
        """
        scope.require(ClientPermission.VIEW_CLIENT_COSTS)
        row = self._client_row(scope, for_update=for_update)
        held = self._session.scalar(
            select(func.coalesce(func.sum(BudgetReservationRow.amount_usd), 0.0)).where(
                BudgetReservationRow.client_id == scope.client_id,
                BudgetReservationRow.study_id.is_(None),
                BudgetReservationRow.status == ReservationStatus.RESERVED.value,
            )
        )
        return ClientBudget(
            budget_usd=row.budget_usd, spent_usd=row.spent_usd, reserved_usd=float(held or 0.0)
        )

    def set_client_budget(self, scope: ClientContext, budget_usd: float) -> ClientBudget:
        """Set what the client's own AI work may cost; audited with the old and new value.

        Lowering it below what is spent is allowed: nothing new may then be held until it
        is raised again, and nothing spent is undone.
        """
        scope.require(ClientPermission.MANAGE_CLIENT_BUDGET)
        if budget_usd < 0:
            raise ValueError("budget_usd must not be negative")
        # Locked and freshly read: two concurrent changes are applied one after the
        # other, each audited against the value the other committed.
        row = self._client_row(scope, for_update=True)
        previous = row.budget_usd
        if previous != float(budget_usd):
            row.budget_usd = float(budget_usd)
            self._session.add(
                AccessAuditRow(
                    **scope.audit_fields(),
                    action="CLIENT_BUDGET_CHANGED",
                    reason=f"{previous} -> {float(budget_usd)}",
                )
            )
            self._session.flush()
        return self.client_budget(scope)

    def client_of_study(self, scope: StudyContext) -> Client:
        """The client of the study in scope: from the context, never from an argument."""
        row = self._session.scalar(
            select(ClientRow).where(
                ClientRow.client_id == scope.client_id,
                ClientRow.organization_id == scope.organization_id,
            )
        )
        if row is None:
            raise ScopeDenied("not found", reason="unknown_client")
        return _client_to_domain(row)

    def studies_in_client(
        self,
        scope: ClientContext,
        *,
        kind: StudyKind | None = None,
        include_archived: bool = True,
    ) -> list[Study]:
        """The studies of the client in scope that the actor may open, newest change first.

        Restricted to ``scope.study_ids`` in the query itself: a study-only
        grantee sees their studies and nothing else of the client's work.
        """
        if not scope.study_ids:
            return []
        stmt = select(StudyRow).where(
            StudyRow.organization_id == scope.organization_id,
            StudyRow.client_id == scope.client_id,
            StudyRow.study_id.in_(sorted(scope.study_ids)),
        )
        if kind is not None:
            stmt = stmt.where(StudyRow.kind == kind.value)
        if not include_archived:
            stmt = stmt.where(StudyRow.status != StudyStatus.ARCHIVED.value)
        rows = self._session.scalars(stmt.order_by(StudyRow.modified_at.desc())).all()
        return [_study_to_domain(r) for r in rows]

    def create_study_in_client(
        self,
        scope: ClientContext,
        *,
        slug: str,
        name: str,
        kind: StudyKind,
    ) -> Study:
        """Start a research or a simulation for the client in scope (ADR 0015).

        Needs ``CREATE_STUDY`` on the client (a client-level RESEARCHER or LEAD):
        the person working for the client starts the work, and their client grant
        is what lets them open it. The budget starts at zero; raising it needs
        ``MANAGE_STUDY_BUDGET`` on the study, as before.
        """
        scope.require(ClientPermission.CREATE_STUDY)
        study = Study(
            study_id=new_study_id(),
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            slug=slug,
            name=name,
            kind=kind,
        )
        self._session.add(
            StudyRow(
                study_id=study.study_id,
                organization_id=study.organization_id,
                client_id=study.client_id,
                slug=study.slug,
                name=study.name,
                kind=study.kind.value,
                status=study.status.value,
                budget_usd=0.0,
            )
        )
        self._session.add(
            AccessAuditRow(
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                study_id=study.study_id,
                actor_id=scope.actor_id,
                action="STUDY_CREATED",
                payload={"kind": kind.value, "via": "client_workspace"},
                request_id=scope.request_id,
            )
        )
        self._session.flush()
        return study

    def get_study(self, scope: StudyContext, *, for_update: bool = False) -> Study:
        """Return the study in scope.

        No id parameter: the study is whichever one the context authorised, which
        removes any chance of reading a different study under this authorisation.
        ``for_update`` locks the row and re-reads what is committed, for a caller that
        compares a value (the budget) before changing it.
        """
        query = select(StudyRow).where(StudyRow.study_id == scope.study_id)
        if for_update:
            # Blocking FOR UPDATE on PostgreSQL (SQLite has none and serialises writers).
            query = query.with_for_update().execution_options(populate_existing=True)
        row = self._session.scalar(query)
        if row is None:
            raise ScopeDenied("not found", reason="unknown_study")
        return _study_to_domain(row)

    def list_studies(
        self,
        admin: OrganizationContext,
        *,
        study_ids: Sequence[str],
        client_id: str | None = None,
        include_archived: bool = False,
    ) -> list[Study]:
        """List studies, restricted to ``study_ids``.

        ``study_ids`` comes from ``ScopeResolver.accessible_studies``. Passing an
        empty sequence returns nothing rather than everything -- the failure mode
        of a forgotten filter is an empty list, not a data leak.
        """
        if not study_ids:
            return []

        stmt = select(StudyRow).where(
            StudyRow.organization_id == admin.organization_id,
            StudyRow.study_id.in_(list(study_ids)),
        )
        if client_id is not None:
            stmt = stmt.where(StudyRow.client_id == client_id)
        if not include_archived:
            stmt = stmt.where(StudyRow.status != StudyStatus.ARCHIVED.value)

        rows = self._session.scalars(stmt.order_by(StudyRow.modified_at.desc())).all()
        return [_study_to_domain(r) for r in rows]

    def set_study_status(self, scope: StudyContext, status: StudyStatus) -> Study:
        """Change the study's lifecycle status.

        Marking a study DELIVERED requires sign-off authority, because delivery is
        the point at which work becomes client-visible and is frozen.
        """
        if status is StudyStatus.DELIVERED:
            scope.require(Permission.SIGN_OFF_DELIVERABLE)
        else:
            scope.require(Permission.EDIT_STUDY)

        row = self._session.scalar(select(StudyRow).where(StudyRow.study_id == scope.study_id))
        if row is None:
            raise ScopeDenied("not found", reason="unknown_study")

        row.status = status.value
        if status is StudyStatus.DELIVERED:
            row.delivered_at = utcnow()

        self._session.add(
            AccessAuditRow(
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                study_id=scope.study_id,
                actor_id=scope.actor_id,
                action="STUDY_STATUS_CHANGED",
                role=scope.role.value,
                reason=status.value,
                request_id=scope.request_id,
            )
        )
        self._session.flush()
        return _study_to_domain(row)

    def set_study_budget(self, scope: StudyContext, budget_usd: float) -> Study:
        """Set the study's budget ceiling."""
        scope.require(Permission.MANAGE_STUDY_BUDGET)
        if budget_usd < 0:
            raise ValueError("budget_usd must not be negative")

        row = self._session.scalar(select(StudyRow).where(StudyRow.study_id == scope.study_id))
        if row is None:
            raise ScopeDenied("not found", reason="unknown_study")

        previous = row.budget_usd
        row.budget_usd = float(budget_usd)
        self._session.add(
            AccessAuditRow(
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                study_id=scope.study_id,
                actor_id=scope.actor_id,
                action="STUDY_BUDGET_CHANGED",
                role=scope.role.value,
                reason=f"{previous} -> {budget_usd}",
                request_id=scope.request_id,
            )
        )
        self._session.flush()
        return _study_to_domain(row)

    def set_study_spend_confirm(self, scope: StudyContext, limit_usd: float | None) -> Study:
        """Set the cost ceiling at which a run's start asks for confirmation; ``None`` clears it."""
        scope.require(Permission.MANAGE_STUDY_BUDGET)
        if limit_usd is not None and limit_usd < 0:
            raise ValueError("limit_usd must not be negative")

        row = self._session.scalar(select(StudyRow).where(StudyRow.study_id == scope.study_id))
        if row is None:
            raise ScopeDenied("not found", reason="unknown_study")

        previous = row.spend_confirm_usd
        row.spend_confirm_usd = None if limit_usd is None else float(limit_usd)
        self._session.add(
            AccessAuditRow(
                organization_id=scope.organization_id,
                client_id=scope.client_id,
                study_id=scope.study_id,
                actor_id=scope.actor_id,
                action="STUDY_SPEND_CONFIRM_CHANGED",
                role=scope.role.value,
                reason=f"{previous} -> {row.spend_confirm_usd}",
                request_id=scope.request_id,
            )
        )
        self._session.flush()
        return _study_to_domain(row)

    def set_self_approval(
        self,
        admin: OrganizationContext,
        *,
        allowed: bool | None,
        client_id: str | None = None,
        study_id: str | None = None,
    ) -> SelfApprovalPolicy:
        """Configure self-approval at the organization, client or study level.

        This is the **only** way the policy is set, and it requires organization
        administration. That is deliberate: self-approval weakens a control, so
        turning it on must be an administrative act against persisted state, not
        something a study LEAD can arrange for their own study, and certainly not
        something a request payload or an agent can assert.

        ``allowed=None`` clears the level so it inherits its parent again, which
        is distinct from setting it to ``False``. Passing ``study_id`` configures
        that study, ``client_id`` that client, and neither configures the
        organization.

        Returns the policy that now resolves for the level that was changed, so a
        caller can show the effect rather than the setting.
        """
        admin.require_administer()
        if client_id and study_id:
            raise ValueError("configure a client or a study, not both")

        organization = self._session.scalar(
            select(OrganizationRow).where(OrganizationRow.organization_id == admin.organization_id)
        )
        if organization is None:
            raise ScopeDenied("not found", reason="unknown_organization")

        client_row: ClientRow | None = None
        study_row: StudyRow | None = None
        level = "organization"

        if study_id:
            study_row = self._session.scalar(
                select(StudyRow).where(
                    StudyRow.study_id == study_id,
                    StudyRow.organization_id == admin.organization_id,
                )
            )
            if study_row is None:
                raise ScopeDenied("not found", reason="unknown_study")
            study_row.allow_self_approval = allowed
            client_id = study_row.client_id
            level = "study"
        elif client_id:
            client_row = self._session.scalar(
                select(ClientRow).where(
                    ClientRow.client_id == client_id,
                    ClientRow.organization_id == admin.organization_id,
                )
            )
            if client_row is None:
                raise ScopeDenied("not found", reason="unknown_client")
            client_row.allow_self_approval = allowed
            level = "client"
        else:
            organization.allow_self_approval = allowed

        if client_row is None and client_id:
            client_row = self._session.scalar(
                select(ClientRow).where(ClientRow.client_id == client_id)
            )

        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                client_id=client_id,
                study_id=study_id,
                actor_id=admin.actor_id,
                action="SELF_APPROVAL_CONFIGURED",
                reason=f"{level}={'inherit' if allowed is None else str(allowed).lower()}",
                payload={"level": level, "allow_self_approval": allowed},
                request_id=admin.request_id,
            )
        )
        self._session.flush()
        return resolve_self_approval_policy(
            organization=organization.allow_self_approval,
            client=client_row.allow_self_approval if client_row is not None else None,
            study=study_row.allow_self_approval if study_row is not None else None,
        )

    def self_approval_levels(self, admin: OrganizationContext) -> dict[str, Any]:
        """Return every configured self-approval level, as stored.

        ``organization`` is the base value (``None`` = not configured, which
        resolves to the default). ``clients`` and ``studies`` list only the levels
        that are set: an absent entry inherits. The raw values are returned, not
        resolved ones, because an administrator changing the policy needs to see
        which level decided it, and a resolved ``False`` does not say.

        Requires organization administration, like the write: which parts of the
        organization have weakened review is itself security-relevant.
        """
        admin.require_administer()
        organization = self._session.scalar(
            select(OrganizationRow.allow_self_approval).where(
                OrganizationRow.organization_id == admin.organization_id
            )
        )
        clients = self._session.execute(
            select(ClientRow.client_id, ClientRow.allow_self_approval)
            .where(
                ClientRow.organization_id == admin.organization_id,
                ClientRow.allow_self_approval.is_not(None),
            )
            .order_by(ClientRow.client_id)
        ).all()
        studies = self._session.execute(
            select(StudyRow.study_id, StudyRow.client_id, StudyRow.allow_self_approval)
            .where(
                StudyRow.organization_id == admin.organization_id,
                StudyRow.allow_self_approval.is_not(None),
            )
            .order_by(StudyRow.study_id)
        ).all()
        return {
            "organization": organization,
            "clients": [{"client_id": c, "allowed": bool(a)} for c, a in clients],
            "studies": [{"study_id": s, "client_id": c, "allowed": bool(a)} for s, c, a in studies],
        }

    def study_spend(self, scope: StudyContext) -> dict[str, float]:
        """Return the study's budget position."""
        scope.require(Permission.VIEW_COSTS)
        row = self._session.scalar(select(StudyRow).where(StudyRow.study_id == scope.study_id))
        if row is None:
            raise ScopeDenied("not found", reason="unknown_study")
        return {
            "budget_usd": row.budget_usd,
            "spent_usd": row.spent_usd,
            "remaining_usd": max(0.0, row.budget_usd - row.spent_usd),
        }

    def members(self, admin: OrganizationContext) -> list[dict[str, Any]]:
        """List organization members with their roles."""
        rows = self._session.execute(
            select(OrganizationMemberRow, UserRow)
            .join(UserRow, UserRow.user_id == OrganizationMemberRow.user_id)
            .where(OrganizationMemberRow.organization_id == admin.organization_id)
            .order_by(UserRow.email)
        ).all()
        return [
            {
                "user_id": user.user_id,
                "email": user.email,
                "display_name": user.display_name,
                "is_active": user.is_active and member.deactivated_at is None,
                "organization_role": member.role,
                "deactivated_at": member.deactivated_at,
            }
            for member, user in rows
        ]

    def client_study_counts(self, admin: OrganizationContext) -> dict[str, int]:
        """Return study counts per client, for an administrative overview."""
        rows = self._session.execute(
            select(StudyRow.client_id, func.count())
            .where(StudyRow.organization_id == admin.organization_id)
            .group_by(StudyRow.client_id)
        ).all()
        return {client_id: int(count) for client_id, count in rows}
