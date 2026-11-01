"""The Metodik mark (D-14, settings-backends SB1): granted and revoked by an OWNER only, on a
member of the OWNER's own organization, audited; the resolver issues it from the membership."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.domain.scope import OrganizationRole, ScopeDenied
from aia_core.infrastructure.methodology_repository import MethodologyRepository
from aia_core.infrastructure.tables import AccessAuditRow


def _context(scoped: Any, user_id: str, organization_id: str | None = None) -> Any:
    principal = scoped.principal(user_id)
    if organization_id is not None:
        principal = replace(principal, organization_id=organization_id)
    return scoped.resolver.organization_context(principal)


def _actions(session: Any) -> list[tuple[str, str | None]]:
    rows = session.scalars(
        select(AccessAuditRow)
        .where(AccessAuditRow.action.like("METHODOLOGIST_%"))
        .order_by(AccessAuditRow.event_id)
    )
    return [(r.action, r.subject_user_id) for r in rows]


def test_nobody_holds_the_mark_until_an_owner_grants_it(scoped: Any, session: Any) -> None:
    assert scoped.admin_context.methodologist is False
    assert not any(m["methodologist"] for m in scoped.scope_repo.members(scoped.admin_context))


def test_an_owner_grants_and_revokes_it_and_each_change_is_audited(
    scoped: Any, session: Any
) -> None:
    lead = scoped.users["lead"]
    scoped.scope_repo.set_methodologist(scoped.admin_context, user_id=lead, methodologist=True)
    marked = _context(scoped, lead)
    assert marked.methodologist is True
    MethodologyRepository(session, marked)  # admitted
    by_id = {m["user_id"]: m for m in scoped.scope_repo.members(scoped.admin_context)}
    assert by_id[lead]["methodologist"] is True

    # Setting what is set changes nothing and records nothing.
    scoped.scope_repo.set_methodologist(scoped.admin_context, user_id=lead, methodologist=True)
    scoped.scope_repo.set_methodologist(scoped.admin_context, user_id=lead, methodologist=False)
    assert _context(scoped, lead).methodologist is False
    with pytest.raises(ScopeDenied):
        MethodologyRepository(session, _context(scoped, lead))
    assert _actions(session) == [("METHODOLOGIST_GRANTED", lead), ("METHODOLOGIST_REVOKED", lead)]


def test_only_an_owner_grants_it_not_an_admin(scoped: Any, session: Any) -> None:
    admin_user = scoped.scope_repo.add_member(
        scoped.admin_context, email="second-admin@art-chain.io", role=OrganizationRole.ADMIN
    ).user_id
    admin = _context(scoped, admin_user)
    with pytest.raises(ScopeDenied) as denied:
        scoped.scope_repo.set_methodologist(admin, user_id=admin_user, methodologist=True)
    assert denied.value.reason == "owner_only"
    assert _actions(session) == []


def test_an_owner_cannot_mark_someone_outside_their_organization(scoped: Any, session: Any) -> None:
    other_org, other_owner = scoped.scope_repo.create_organization(
        slug="other", name="Other", owner_email="o@example.org", owner_name="O"
    )
    with pytest.raises(ScopeDenied) as denied:
        scoped.scope_repo.set_methodologist(
            scoped.admin_context, user_id=other_owner.user_id, methodologist=True
        )
    assert denied.value.reason == "not_a_member"
    theirs = _context(scoped, other_owner.user_id, other_org.organization_id)
    assert theirs.methodologist is False
