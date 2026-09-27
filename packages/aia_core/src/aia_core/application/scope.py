"""Scope resolution: turning an authenticated principal into an authorised scope.

This module is the **only** place that issues a :class:`StudyContext` or an
:class:`OrganizationContext`. Every repository touching client data demands one,
and the private issuer sentinel in ``aia_core.domain.scope`` means nothing else
can forge one.

That is what makes the product rule enforceable:

> Scope is injected from authenticated application context. No AI- or
> model-generated argument may determine client or study scope.

An AI tool can pass whatever ``client_id`` it likes; it will not resolve unless
the *authenticated human* behind the request holds a grant on it. The worst a
confused or compromised agent can do is fail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.scope import (
    LEGACY_PANEL_ROLES,
    ClientContext,
    ClientGrant,
    ClientPermission,
    ClientStatus,
    OrganizationContext,
    OrganizationRole,
    Permission,
    ScopeDenied,
    ScopeGrant,
    ScopeRole,
    StudyContext,
    StudyGrant,
    StudyStatus,
    client_permissions_for,
    effective_role,
    permissions_for,
    resolve_self_approval_policy,
)
from ..domain.workflow import AttemptStatus
from ..infrastructure.tables import (
    AccessAuditRow,
    ClientGrantRow,
    ClientRow,
    OrganizationMemberRow,
    OrganizationRow,
    StepAttemptRow,
    StepRunRow,
    StudyGrantRow,
    StudyRow,
    UserRow,
    WorkflowRunRow,
)

__all__ = ["EXECUTION_ROLE", "AuthenticatedPrincipal", "ScopeResolver"]

# The role a worker executes under: doing the work, never approving it. RESEARCHER
# confers RUN_WORKFLOW, EDIT_STUDY and UPLOAD_DATA and withholds APPROVE_GATE,
# APPROVE_BUDGET and every MANAGE_* permission -- so neither the worker nor any
# executor or AI tool running inside it can sign off its own gate or raise the
# budget it is spending.
EXECUTION_ROLE = ScopeRole.RESEARCHER


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """A caller whose identity has been verified by the identity provider.

    This carries only what the token proved. It deliberately carries **no roles
    and no client or study ids**: authorization is AIA's job and is answered from
    PostgreSQL, not from token claims. A token cannot grant itself access to a
    client.
    """

    user_id: str
    organization_id: str
    email: str | None = None
    external_subject: str | None = None
    request_id: str | None = None


class ScopeResolver:
    """Resolves and authorises scope for one request or one job.

    Construct per unit of work. The resolver reads grants, decides, records the
    decision when it matters, and issues a context.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------- internals --

    def _membership_role(self, principal: AuthenticatedPrincipal) -> OrganizationRole:
        """Return the principal's organization role, or deny."""
        row = self._session.scalar(
            select(OrganizationMemberRow).where(
                OrganizationMemberRow.organization_id == principal.organization_id,
                OrganizationMemberRow.user_id == principal.user_id,
            )
        )
        if row is None:
            raise ScopeDenied("not found", reason="not_a_member")
        return OrganizationRole(row.role)

    def _active_user(self, principal: AuthenticatedPrincipal) -> UserRow:
        """Return the user row, denying a deactivated account.

        Deactivation must take effect immediately even if a valid token is still
        in circulation, so it is checked on every resolution rather than trusted
        to token expiry.
        """
        row = self._session.scalar(select(UserRow).where(UserRow.user_id == principal.user_id))
        if row is None:
            raise ScopeDenied("not found", reason="unknown_user")
        if not row.is_active:
            raise ScopeDenied("not found", reason="user_deactivated")
        return row

    def _record(
        self,
        principal: AuthenticatedPrincipal,
        *,
        action: str,
        client_id: str | None = None,
        study_id: str | None = None,
        subject_user_id: str | None = None,
        role: str | None = None,
        reason: str = "",
    ) -> None:
        """Append an access audit entry."""
        self._session.add(
            AccessAuditRow(
                organization_id=principal.organization_id,
                client_id=client_id,
                study_id=study_id,
                subject_user_id=subject_user_id,
                actor_id=principal.user_id,
                action=action,
                role=role,
                reason=reason,
                request_id=principal.request_id,
            )
        )

    # ---------------------------------------------------------------- public --

    def organization_context(self, principal: AuthenticatedPrincipal) -> OrganizationContext:
        """Authorise organization-level scope, for administration only.

        The returned context carries no client or study id, so it cannot be used
        to read client research data.
        """
        self._active_user(principal)
        role = self._membership_role(principal)
        return OrganizationContext(
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            organization_role=role,
            grant=ScopeGrant._issue(),
            request_id=principal.request_id,
        )

    def authorize_legacy_panel(
        self, principal: AuthenticatedPrincipal, *, audit: bool
    ) -> OrganizationContext:
        """Admit a principal to the vendored 18.6.6 interface, or deny (ADR 0012).

        Only an active member whose organization role is in
        :data:`LEGACY_PANEL_ROLES` is admitted. ``audit`` records the decision in
        the access audit; the session is opened with it on, and the per-request
        gate re-checks with it off, because a record per asset and API call of one
        page would drown every other entry.
        """
        context = self.organization_context(principal)
        if context.organization_role not in LEGACY_PANEL_ROLES:
            if audit:
                self._record(
                    principal,
                    action="LEGACY_PANEL_DENIED",
                    role=context.organization_role.value,
                    reason="organization_role",
                )
            raise ScopeDenied("not found", reason="legacy_panel_role")
        if audit:
            self._record(
                principal,
                action="LEGACY_PANEL_SESSION",
                role=context.organization_role.value,
            )
        return context

    def study_context(
        self,
        principal: AuthenticatedPrincipal,
        *,
        study_id: str,
        require: Permission | None = None,
    ) -> StudyContext:
        """Authorise scope for one study, or raise :class:`ScopeDenied`.

        The client id is derived from the **study row**, never from the caller.
        Accepting a caller-supplied client id would let a mismatched pair be used
        to read one client's study under another client's authorisation.

        Resolution order:

        1. the user exists and is active;
        2. the user is a member of the organization;
        3. the study exists **within that organization**;
        4. the client is not archived;
        5. the user holds a client grant or a study grant, with the study grant
           authoritative;
        6. the effective role confers ``require``, when given.

        The self-approval policy is resolved here, from the organization, client
        and study rows, and travels on the issued context. Resolving it at this
        point rather than at the approval call is the security property: a
        ``StudyContext`` can only be issued from persisted AIA state, so no model
        output, tool argument or request body can assert that self-approval is
        permitted.

        Every failure raises the same exception with a distinguishing ``reason``
        for the audit log, and callers must surface all of them as 404.
        """
        self._active_user(principal)
        organization_role = self._membership_role(principal)

        study = self._session.scalar(
            select(StudyRow).where(
                StudyRow.study_id == study_id,
                StudyRow.organization_id == principal.organization_id,
            )
        )
        if study is None:
            # Not recorded: an id that does not exist in this organization is
            # noise, and recording it would let a prober fill the audit log.
            raise ScopeDenied("not found", reason="unknown_study")

        client = self._session.scalar(
            select(ClientRow).where(ClientRow.client_id == study.client_id)
        )
        if client is None:
            raise ScopeDenied("not found", reason="unknown_client")
        if client.status == ClientStatus.ARCHIVED.value:
            raise ScopeDenied("not found", reason="client_archived")

        client_grant = self._session.scalar(
            select(ClientGrantRow).where(
                ClientGrantRow.client_id == study.client_id,
                ClientGrantRow.user_id == principal.user_id,
            )
        )
        study_grant = self._session.scalar(
            select(StudyGrantRow).where(
                StudyGrantRow.study_id == study_id,
                StudyGrantRow.user_id == principal.user_id,
            )
        )

        role = effective_role(
            client_role=ScopeRole(client_grant.role) if client_grant else None,
            study_role=ScopeRole(study_grant.role) if study_grant else None,
        )

        if role is None:
            # This one *is* recorded: a member of the organization reaching for a
            # study they hold no grant on is worth seeing.
            self._record(
                principal,
                action="ACCESS_DENIED",
                client_id=study.client_id,
                study_id=study_id,
                reason="no_grant",
            )
            raise ScopeDenied("not found", reason="no_grant")

        organization = self._session.scalar(
            select(OrganizationRow).where(
                OrganizationRow.organization_id == principal.organization_id
            )
        )

        context = StudyContext(
            organization_id=principal.organization_id,
            client_id=study.client_id,
            study_id=study_id,
            actor_id=principal.user_id,
            role=role,
            permissions=permissions_for(role),
            organization_role=organization_role,
            grant=ScopeGrant._issue(),
            study_status=StudyStatus(study.status),
            self_approval=resolve_self_approval_policy(
                organization=organization.allow_self_approval if organization else None,
                client=client.allow_self_approval,
                study=study.allow_self_approval,
            ),
            request_id=principal.request_id,
        )

        if require is not None:
            try:
                context.require(require)
            except ScopeDenied:
                self._record(
                    principal,
                    action="PERMISSION_DENIED",
                    client_id=study.client_id,
                    study_id=study_id,
                    role=role.value,
                    reason=require.value,
                )
                raise

        return context

    def execution_context(self, *, attempt_id: str, worker_id: str) -> StudyContext:
        """Issue the scope a worker executes one claimed attempt under.

        **The capability is the lease.** The context is issued only while
        ``worker_id`` holds ``attempt_id`` -- status ``CLAIMED`` or ``EXECUTING``,
        owner recorded on the row -- and its organization, client and study come
        from the persisted attempt → step → run → study chain, never from the
        caller. Nothing in a worker process can obtain a context for a study it has
        not claimed work in, and a claim payload or a model-generated argument
        cannot name one.

        Three properties, each deliberate:

        * **Role** is :data:`EXECUTION_ROLE`: the worker can do the work and
          cannot approve it.
        * **Actor** is the run's ``triggered_by`` -- the human on whose behalf the
          work runs -- so a gate the worker opens records that person as the
          producer, and the separation-of-duties check compares against them.
          A run with no recorded trigger is attributed to ``worker:<id>``.
        * **Fail closed** on an archived client: its work stops, whatever was in
          flight. (Whether a revoked or deactivated *triggering user* should also
          stop their runs is an open policy question -- ``open-items.md`` OI-22 --
          and is not decided here.)

        Denials raise :class:`ScopeDenied` with a reason, like every other
        resolution.
        """
        row = self._session.execute(
            select(StepAttemptRow, WorkflowRunRow, StudyRow, ClientRow)
            .join(StepRunRow, StepRunRow.step_id == StepAttemptRow.step_id)
            .join(WorkflowRunRow, WorkflowRunRow.run_id == StepRunRow.run_id)
            .join(StudyRow, StudyRow.study_id == WorkflowRunRow.study_id)
            .join(ClientRow, ClientRow.client_id == StudyRow.client_id)
            .where(StepAttemptRow.attempt_id == attempt_id)
        ).first()
        if row is None:
            raise ScopeDenied("not found", reason="unknown_attempt")
        attempt, run, study, client = row

        if attempt.worker_id != worker_id or not AttemptStatus(attempt.status).holds_lease:
            raise ScopeDenied("not found", reason="lease_not_held")
        if (run.organization_id, run.client_id) != (study.organization_id, study.client_id):
            # The run row carries its own copy of the scope. If it disagrees with
            # the study it names, one of them is wrong, and guessing which would be
            # choosing a client's data at random.
            raise ScopeDenied("not found", reason="scope_mismatch")
        if client.status == ClientStatus.ARCHIVED.value:
            raise ScopeDenied("not found", reason="client_archived")

        organization = self._session.scalar(
            select(OrganizationRow).where(OrganizationRow.organization_id == run.organization_id)
        )
        return StudyContext(
            organization_id=run.organization_id,
            client_id=study.client_id,
            study_id=study.study_id,
            actor_id=run.triggered_by or f"worker:{worker_id}",
            role=EXECUTION_ROLE,
            permissions=permissions_for(EXECUTION_ROLE),
            organization_role=OrganizationRole.MEMBER,
            grant=ScopeGrant._issue(),
            study_status=StudyStatus(study.status),
            self_approval=resolve_self_approval_policy(
                organization=organization.allow_self_approval if organization else None,
                client=client.allow_self_approval,
                study=study.allow_self_approval,
            ),
            request_id=f"{run.run_id}/{attempt.attempt_id}",
        )

    def client_context(
        self,
        principal: AuthenticatedPrincipal,
        *,
        client_id: str,
        require: ClientPermission | None = None,
    ) -> ClientContext:
        """Authorise scope for one client, or raise :class:`ScopeDenied` (ADR 0015).

        Resolution order: the user is active; a member of the organization; the
        client exists **within that organization** and is not archived; the user
        holds a client-level grant, or at least one study grant on a study of this
        client (study-only access). The studies the actor may open are resolved
        here and travel on the context. Every failure must surface as 404.
        """
        self._active_user(principal)
        organization_role = self._membership_role(principal)

        client = self._session.scalar(
            select(ClientRow).where(
                ClientRow.client_id == client_id,
                ClientRow.organization_id == principal.organization_id,
            )
        )
        if client is None:
            raise ScopeDenied("not found", reason="unknown_client")
        if client.status == ClientStatus.ARCHIVED.value:
            raise ScopeDenied("not found", reason="client_archived")

        client_grant = self._session.scalar(
            select(ClientGrantRow).where(
                ClientGrantRow.client_id == client_id,
                ClientGrantRow.user_id == principal.user_id,
            )
        )
        study_ids = frozenset(self.accessible_studies(principal, client_id=client_id))
        if client_grant is None and not study_ids:
            self._record(
                principal,
                action="ACCESS_DENIED",
                client_id=client_id,
                study_id=None,
                reason="no_grant",
            )
            raise ScopeDenied("not found", reason="no_grant")

        client_role = ScopeRole(client_grant.role) if client_grant else None
        organization = self._session.scalar(
            select(OrganizationRow).where(
                OrganizationRow.organization_id == principal.organization_id
            )
        )
        context = ClientContext(
            organization_id=principal.organization_id,
            client_id=client_id,
            actor_id=principal.user_id,
            client_role=client_role,
            permissions=client_permissions_for(client_role),
            organization_role=organization_role,
            grant=ScopeGrant._issue(),
            study_ids=study_ids,
            self_approval=resolve_self_approval_policy(
                organization=organization.allow_self_approval if organization else None,
                client=client.allow_self_approval,
            ),
            request_id=principal.request_id,
        )
        if require is not None:
            try:
                context.require(require)
            except ScopeDenied:
                self._record(
                    principal,
                    action="PERMISSION_DENIED",
                    client_id=client_id,
                    study_id=None,
                    role=client_role.value if client_role else None,
                    reason=require.value,
                )
                raise
        return context

    def accessible_clients(self, principal: AuthenticatedPrincipal) -> list[str]:
        """The clients this principal may open: a client grant, or a study grant within it.

        Archived clients are excluded, as :meth:`client_context` refuses them.
        Organization administrators are not silently included (ADR 0004).
        """
        self._active_user(principal)
        self._membership_role(principal)
        via_client = (
            select(ClientRow.client_id)
            .join(ClientGrantRow, ClientGrantRow.client_id == ClientRow.client_id)
            .where(
                ClientRow.organization_id == principal.organization_id,
                ClientRow.status != ClientStatus.ARCHIVED.value,
                ClientGrantRow.user_id == principal.user_id,
            )
        )
        via_study = (
            select(ClientRow.client_id)
            .join(StudyRow, StudyRow.client_id == ClientRow.client_id)
            .join(StudyGrantRow, StudyGrantRow.study_id == StudyRow.study_id)
            .where(
                ClientRow.organization_id == principal.organization_id,
                ClientRow.status != ClientStatus.ARCHIVED.value,
                StudyGrantRow.user_id == principal.user_id,
            )
        )
        ids = set(self._session.scalars(via_client).all())
        ids.update(self._session.scalars(via_study).all())
        return sorted(ids)

    def accessible_studies(
        self, principal: AuthenticatedPrincipal, *, client_id: str | None = None
    ) -> list[str]:
        """Return the study ids this principal may access.

        Used to scope a portfolio listing. A study reachable through either a
        client grant or a study grant is included; nothing else is, and
        organization administrators are not silently included.
        """
        self._active_user(principal)
        self._membership_role(principal)

        via_client = (
            select(StudyRow.study_id)
            .join(ClientGrantRow, ClientGrantRow.client_id == StudyRow.client_id)
            .where(
                StudyRow.organization_id == principal.organization_id,
                ClientGrantRow.user_id == principal.user_id,
            )
        )
        via_study = (
            select(StudyRow.study_id)
            .join(StudyGrantRow, StudyGrantRow.study_id == StudyRow.study_id)
            .where(
                StudyRow.organization_id == principal.organization_id,
                StudyGrantRow.user_id == principal.user_id,
            )
        )
        if client_id is not None:
            via_client = via_client.where(StudyRow.client_id == client_id)
            via_study = via_study.where(StudyRow.client_id == client_id)

        ids = set(self._session.scalars(via_client).all())
        ids.update(self._session.scalars(via_study).all())
        return sorted(ids)

    # ------------------------------------------------------------- mutations --

    def grant_client_access(
        self,
        admin: OrganizationContext,
        *,
        client_id: str,
        user_id: str,
        role: ScopeRole,
        reason: str = "",
    ) -> ClientGrant:
        """Grant a user a role on a client. Requires organization administration.

        An administrator granting **themselves** access is legitimate -- someone
        has to be able to start work on a new client -- but it is recorded with a
        distinct action so the break-glass case is visible in the audit log rather
        than indistinguishable from ordinary provisioning.
        """
        admin.require_administer()

        client = self._session.scalar(
            select(ClientRow).where(
                ClientRow.client_id == client_id,
                ClientRow.organization_id == admin.organization_id,
            )
        )
        if client is None:
            raise ScopeDenied("not found", reason="unknown_client")

        existing = self._session.scalar(
            select(ClientGrantRow).where(
                ClientGrantRow.client_id == client_id,
                ClientGrantRow.user_id == user_id,
            )
        )
        previous_access = existing.role if existing is not None else None

        if existing is not None:
            existing.role = role.value
            existing.granted_by = admin.actor_id
        else:
            self._session.add(
                ClientGrantRow(
                    client_id=client_id,
                    user_id=user_id,
                    role=role.value,
                    granted_by=admin.actor_id,
                )
            )

        # A self-grant is legitimate -- someone has to be able to start work on a
        # new client -- but it is the one case where administrative authority and
        # confidential research access meet in the same person. It gets its own
        # action and a full before/after record so a reviewer can see exactly what
        # was taken, by whom, and why.
        is_self_grant = user_id == admin.actor_id
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                client_id=client_id,
                subject_user_id=user_id,
                actor_id=admin.actor_id,
                action="CLIENT_SELF_GRANT" if is_self_grant else "CLIENT_GRANT",
                role=role.value,
                reason=reason or ("self_grant" if is_self_grant else "granted_by_admin"),
                request_id=admin.request_id,
                payload={
                    "actor_user_id": admin.actor_id,
                    "client_id": client_id,
                    "subject_user_id": user_id,
                    "previous_access": previous_access,
                    "new_access": role.value,
                    "self_grant": is_self_grant,
                    "reason": reason or None,
                    "request_id": admin.request_id,
                },
            )
        )
        self._session.flush()
        return ClientGrant(client_id=client_id, user_id=user_id, role=role)

    def grant_study_access(
        self,
        granter: StudyContext,
        *,
        user_id: str,
        role: ScopeRole,
        reason: str = "",
    ) -> StudyGrant:
        """Grant a user a role on the study in scope.

        Requires ``MANAGE_STUDY_ACCESS``, so a study LEAD can staff their own
        study without organization administration.
        """
        granter.require(Permission.MANAGE_STUDY_ACCESS)

        existing = self._session.scalar(
            select(StudyGrantRow).where(
                StudyGrantRow.study_id == granter.study_id,
                StudyGrantRow.user_id == user_id,
            )
        )
        previous_access = existing.role if existing is not None else None

        if existing is not None:
            existing.role = role.value
            existing.granted_by = granter.actor_id
        else:
            self._session.add(
                StudyGrantRow(
                    study_id=granter.study_id,
                    user_id=user_id,
                    role=role.value,
                    granted_by=granter.actor_id,
                )
            )

        self._session.add(
            AccessAuditRow(
                organization_id=granter.organization_id,
                client_id=granter.client_id,
                study_id=granter.study_id,
                subject_user_id=user_id,
                actor_id=granter.actor_id,
                action="STUDY_GRANT",
                role=role.value,
                reason=reason or "granted_by_study_lead",
                request_id=granter.request_id,
                payload={
                    "actor_user_id": granter.actor_id,
                    "client_id": granter.client_id,
                    "study_id": granter.study_id,
                    "subject_user_id": user_id,
                    "previous_access": previous_access,
                    "new_access": role.value,
                    "restricts_client_grant": True,
                    "reason": reason or None,
                    "request_id": granter.request_id,
                },
            )
        )
        self._session.flush()
        return StudyGrant(study_id=granter.study_id, user_id=user_id, role=role)

    def revoke_client_access(
        self, admin: OrganizationContext, *, client_id: str, user_id: str
    ) -> None:
        """Remove a user's client grant."""
        admin.require_administer()
        row = self._session.scalar(
            select(ClientGrantRow).where(
                ClientGrantRow.client_id == client_id,
                ClientGrantRow.user_id == user_id,
            )
        )
        if row is not None:
            self._session.delete(row)
        self._session.add(
            AccessAuditRow(
                organization_id=admin.organization_id,
                client_id=client_id,
                subject_user_id=user_id,
                actor_id=admin.actor_id,
                action="CLIENT_REVOKE",
                request_id=admin.request_id,
            )
        )
        self._session.flush()

    def audit_trail(self, admin: OrganizationContext, *, limit: int = 200) -> list[dict[str, Any]]:
        """Return recent access audit entries for the organization."""
        admin.require_administer()
        rows = self._session.scalars(
            select(AccessAuditRow)
            .where(AccessAuditRow.organization_id == admin.organization_id)
            .order_by(AccessAuditRow.event_id.desc())
            .limit(max(1, min(int(limit), 1000)))
        ).all()
        return [
            {
                "event_id": r.event_id,
                "action": r.action,
                "client_id": r.client_id,
                "study_id": r.study_id,
                "subject_user_id": r.subject_user_id,
                "actor_id": r.actor_id,
                "role": r.role,
                "reason": r.reason,
                "payload": dict(r.payload or {}),
                "created_at": r.created_at,
            }
            for r in rows
        ]
