"""Who may use the vendored 18.6.6 interface on the product hostname (ADR 0012).

The unit is single-tenant, so study scope cannot be applied to it; admission is
an organization-level decision, taken only by ``ScopeResolver`` like every other
scope decision, and only owners and admins pass.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.scope import LEGACY_PANEL_ROLES, OrganizationRole, ScopeDenied
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import AccessAuditRow


def test_only_owners_and_admins_may_use_the_panel() -> None:
    assert frozenset({OrganizationRole.OWNER, OrganizationRole.ADMIN}) == LEGACY_PANEL_ROLES
    assert OrganizationRole.MEMBER not in LEGACY_PANEL_ROLES


def _world(session: Any) -> tuple[str, dict[str, str]]:
    repo = ScopeRepository(session)
    org, owner = repo.create_organization(
        slug="aia", name="AI Analytics", owner_email="owner@example.test", owner_name="Owner"
    )
    admin_ctx = ScopeResolver(session).organization_context(
        AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
    )
    admin = repo.add_member(admin_ctx, email="admin@example.test", role=OrganizationRole.ADMIN)
    member = repo.add_member(admin_ctx, email="member@example.test")
    session.flush()
    return org.organization_id, {
        "owner": owner.user_id,
        "admin": admin.user_id,
        "member": member.user_id,
    }


def _audit(session: Any, action: str) -> list[AccessAuditRow]:
    return list(session.scalars(select(AccessAuditRow).where(AccessAuditRow.action == action)))


@pytest.mark.parametrize("label", ["owner", "admin"])
def test_an_administrator_is_admitted_and_the_session_is_audited(session: Any, label: str) -> None:
    org_id, users = _world(session)
    principal = AuthenticatedPrincipal(user_id=users[label], organization_id=org_id)
    context = ScopeResolver(session).authorize_legacy_panel(principal, audit=True)
    assert context.organization_id == org_id
    assert context.actor_id == users[label]
    session.flush()
    rows = _audit(session, "LEGACY_PANEL_SESSION")
    assert [r.actor_id for r in rows] == [users[label]]


def test_a_plain_member_is_refused_and_the_refusal_is_audited(session: Any) -> None:
    org_id, users = _world(session)
    principal = AuthenticatedPrincipal(user_id=users["member"], organization_id=org_id)
    with pytest.raises(ScopeDenied) as denied:
        ScopeResolver(session).authorize_legacy_panel(principal, audit=True)
    assert denied.value.reason == "legacy_panel_role"
    session.flush()
    assert [r.role for r in _audit(session, "LEGACY_PANEL_DENIED")] == ["MEMBER"]
    assert _audit(session, "LEGACY_PANEL_SESSION") == []


def test_the_per_request_gate_writes_no_audit(session: Any) -> None:
    org_id, users = _world(session)
    resolver = ScopeResolver(session)
    resolver.authorize_legacy_panel(
        AuthenticatedPrincipal(user_id=users["owner"], organization_id=org_id), audit=False
    )
    with pytest.raises(ScopeDenied):
        resolver.authorize_legacy_panel(
            AuthenticatedPrincipal(user_id=users["member"], organization_id=org_id), audit=False
        )
    session.flush()
    assert _audit(session, "LEGACY_PANEL_SESSION") == []
    assert _audit(session, "LEGACY_PANEL_DENIED") == []


def test_a_non_member_is_refused(session: Any) -> None:
    org_id, _ = _world(session)
    stranger = ScopeRepository(session).upsert_user(email="stranger@example.test")
    with pytest.raises(ScopeDenied) as denied:
        ScopeResolver(session).authorize_legacy_panel(
            AuthenticatedPrincipal(user_id=stranger["user_id"], organization_id=org_id),
            audit=False,
        )
    assert denied.value.reason == "not_a_member"


def test_a_deactivated_administrator_is_refused(session: Any) -> None:
    org_id, users = _world(session)
    from aia_core.infrastructure.tables import UserRow

    row = session.scalar(select(UserRow).where(UserRow.user_id == users["admin"]))
    row.is_active = False
    session.flush()
    with pytest.raises(ScopeDenied) as denied:
        ScopeResolver(session).authorize_legacy_panel(
            AuthenticatedPrincipal(user_id=users["admin"], organization_id=org_id), audit=False
        )
    assert denied.value.reason == "user_deactivated"
