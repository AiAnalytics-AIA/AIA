"""Persistence for organizations, users, clients, studies and grants.

Administrative reads and writes take an :class:`OrganizationContext`; anything
that touches a specific study takes a :class:`StudyContext`. Neither can be
forged, so there is no code path here that operates without an authorisation
decision having already been made.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.scope import (
    Client,
    ClientStatus,
    Organization,
    OrganizationContext,
    OrganizationMembership,
    OrganizationRole,
    Permission,
    ScopeDenied,
    Study,
    StudyContext,
    StudyStatus,
    new_client_id,
    new_organization_id,
    new_study_id,
    new_user_id,
)
from .tables import (
    AccessAuditRow,
    ClientRow,
    OrganizationMemberRow,
    OrganizationRow,
    StudyRow,
    UserRow,
    utcnow,
)

__all__ = ["ScopeRepository"]


def _client_to_domain(row: ClientRow) -> Client:
    return Client(
        client_id=row.client_id,
        organization_id=row.organization_id,
        slug=row.slug,
        name=row.name,
        status=ClientStatus(row.status),
        reference=row.reference,
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
        status=StudyStatus(row.status),
        budget_usd=row.budget_usd,
        spent_usd=row.spent_usd,
        created_at=row.created_at,
        modified_at=row.modified_at,
        delivered_at=row.delivered_at,
    )


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

    def memberships_for_user(self, user_id: str) -> list[str]:
        """Return the organization ids a user belongs to.

        Used during authentication to decide which organization a request is for.
        Returning a list rather than a single id keeps the door open for a
        consultant who works across two AIA organizations without special-casing
        it later.
        """
        return sorted(
            self._session.scalars(
                select(OrganizationMemberRow.organization_id).where(
                    OrganizationMemberRow.user_id == user_id
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
        """Add a user to the organization."""
        admin.require_administer()
        user = self.upsert_user(email=email, display_name=display_name)

        existing = self._session.scalar(
            select(OrganizationMemberRow).where(
                OrganizationMemberRow.organization_id == admin.organization_id,
                OrganizationMemberRow.user_id == user["user_id"],
            )
        )
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
                request_id=admin.request_id,
            )
        )
        self._session.flush()
        return OrganizationMembership(
            organization_id=admin.organization_id, user_id=user["user_id"], role=role
        )

    def deactivate_user(self, admin: OrganizationContext, *, user_id: str) -> None:
        """Deactivate an account.

        Deactivation is checked on every scope resolution, so it takes effect
        immediately even while a valid token is still in circulation.
        """
        admin.require_administer()
        row = self._session.scalar(select(UserRow).where(UserRow.user_id == user_id))
        if row is None:
            raise ScopeDenied("not found", reason="unknown_user")
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

    # ------------------------------------------------------------------ clients

    def create_client(
        self, admin: OrganizationContext, *, slug: str, name: str, reference: str = ""
    ) -> Client:
        """Create a client."""
        admin.require_administer()
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
        stmt = select(ClientRow).where(ClientRow.organization_id == admin.organization_id)
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
        if row is None:
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

    # ------------------------------------------------------------------ studies

    def create_study(
        self,
        admin: OrganizationContext,
        *,
        client_id: str,
        slug: str,
        name: str,
        budget_usd: float = 0.0,
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
            budget_usd=budget_usd,
        )
        self._session.add(
            StudyRow(
                study_id=study.study_id,
                organization_id=study.organization_id,
                client_id=study.client_id,
                slug=study.slug,
                name=study.name,
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

    def get_study(self, scope: StudyContext) -> Study:
        """Return the study in scope.

        No id parameter: the study is whichever one the context authorised, which
        removes any chance of reading a different study under this authorisation.
        """
        row = self._session.scalar(select(StudyRow).where(StudyRow.study_id == scope.study_id))
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
                "is_active": user.is_active,
                "organization_role": member.role,
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
