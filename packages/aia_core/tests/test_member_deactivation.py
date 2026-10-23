"""Deactivating a member in one organization (D-27, settings-backends SB2), and S15: the
target is resolved through the acting admin's own organization, never found elsewhere."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.application.membership import deactivate_member, reactivate_member
from aia_core.domain.scope import OrganizationRole, ScopeDenied
from aia_core.infrastructure.researcher_lead_repository import (
    SEAL_DAYS,
    LeadSeals,
    ResearcherLeadRepository,
)
from aia_core.infrastructure.tables import AccessAuditRow

NOW = datetime(2026, 10, 22, 23, 0, tzinfo=UTC)


def _other_world(scoped: Any) -> tuple[Any, Any]:
    """A second organization whose OWNER also belongs to it alone, and its admin context."""
    org, owner = scoped.scope_repo.create_organization(
        slug="other", name="Other", owner_email="o@example.org", owner_name="O"
    )
    admin = scoped.resolver.organization_context(
        replace(scoped.principal(owner.user_id), organization_id=org.organization_id)
    )
    return org, admin


def test_an_admin_cannot_deactivate_a_user_of_another_organization(
    scoped: Any, session: Any
) -> None:
    """S15: before, ``deactivate_user`` found the user anywhere and switched the account off,
    so an ADMIN of one organization could lock a member of another out of it."""
    _, theirs = _other_world(scoped)
    researcher = scoped.users["researcher"]  # a member of the fixture's organization only
    with pytest.raises(ScopeDenied) as denied:
        scoped.scope_repo.deactivate_user(theirs, user_id=researcher)
    assert denied.value.reason == "not_a_member"
    with pytest.raises(ScopeDenied) as member:
        deactivate_member(session, theirs, user_id=researcher, now=NOW)
    assert member.value.reason == "not_a_member"
    assert scoped.resolver.organization_context(scoped.principal(researcher))  # still in


def test_a_deactivated_member_resolves_no_scope_here_but_keeps_their_other_membership(
    scoped: Any, session: Any
) -> None:
    other, theirs = _other_world(scoped)
    lead = scoped.users["lead"]
    scoped.scope_repo.add_member(theirs, email="lead@art-chain.io")
    done = deactivate_member(session, scoped.admin_context, user_id=lead, now=NOW)
    assert done.changed is True
    with pytest.raises(ScopeDenied) as denied:
        scoped.resolver.organization_context(scoped.principal(lead))
    assert denied.value.reason == "user_deactivated"
    with pytest.raises(ScopeDenied):
        scoped.scope(user="lead")
    elsewhere = scoped.resolver.organization_context(
        replace(scoped.principal(lead), organization_id=other.organization_id)
    )
    assert elsewhere.organization_id == other.organization_id
    listed = {m["user_id"]: m for m in scoped.scope_repo.members(scoped.admin_context)}
    assert listed[lead]["is_active"] is False and listed[lead]["deactivated_at"] is not None

    again = deactivate_member(session, scoped.admin_context, user_id=lead, now=NOW)
    assert again.changed is False
    back = reactivate_member(session, scoped.admin_context, user_id=lead, now=NOW)
    assert back.changed is True
    assert scoped.resolver.organization_context(scoped.principal(lead))
    actions = [
        r.action
        for r in session.scalars(
            select(AccessAuditRow)
            .where(AccessAuditRow.subject_user_id == lead)
            .order_by(AccessAuditRow.event_id)
        )
        if r.action.startswith("MEMBER_")
    ]
    assert actions[-2:] == ["MEMBER_DEACTIVATED", "MEMBER_REACTIVATED"]


def test_the_last_active_owner_is_never_deactivated_and_only_an_owner_deactivates_one(
    scoped: Any, session: Any
) -> None:
    owner = scoped.admin_context
    with pytest.raises(ScopeDenied) as last:
        deactivate_member(session, owner, user_id=owner.actor_id, now=NOW)
    assert last.value.reason == "last_owner"
    second = scoped.scope_repo.add_member(
        owner, email="second-owner@art-chain.io", role=OrganizationRole.OWNER
    ).user_id
    admin_id = scoped.scope_repo.add_member(
        owner, email="an-admin@art-chain.io", role=OrganizationRole.ADMIN
    ).user_id
    admin = scoped.resolver.organization_context(scoped.principal(admin_id))
    with pytest.raises(ScopeDenied) as owner_only:
        deactivate_member(session, admin, user_id=second, now=NOW)
    assert owner_only.value.reason == "owner_only"
    deactivate_member(session, owner, user_id=second, now=NOW)
    # The deactivated OWNER no longer counts: the first is the last active one again.
    with pytest.raises(ScopeDenied) as again:
        deactivate_member(session, owner, user_id=owner.actor_id, now=NOW)
    assert again.value.reason == "last_owner"


def test_deactivating_seals_the_lead_for_everyone_and_reactivating_unseals_it(
    scoped: Any, session: Any
) -> None:
    lead = scoped.users["lead"]
    own = scoped.resolver.organization_context(scoped.principal(lead))
    ResearcherLeadRepository(session, own).hatch()
    done = deactivate_member(session, scoped.admin_context, user_id=lead, now=NOW)
    assert done.seal is not None
    assert (done.seal.erase_after - done.seal.sealed_at).days == SEAL_DAYS
    # Nobody reads it: the repository answers as if there were none, for its own researcher.
    assert ResearcherLeadRepository(session, own).get() is None
    assert ResearcherLeadRepository(session, own).is_sealed() is True
    assert set(LeadSeals(session, scoped.admin_context).seals()) == {lead}

    back = reactivate_member(session, scoped.admin_context, user_id=lead, now=NOW)
    assert back.lead_unsealed is True
    assert ResearcherLeadRepository(session, own).get() is not None
    assert LeadSeals(session, scoped.admin_context).seals() == {}


def test_a_lead_past_its_date_is_erased_on_reactivation_never_unsealed(
    scoped: Any, session: Any
) -> None:
    """Reactivated on day 31 with no sweep in between (it runs per deploy): the Lead is erased
    then and there, as the sweep would have, and its member hatches a new one."""
    lead = scoped.users["lead"]
    own = scoped.resolver.organization_context(scoped.principal(lead))
    ResearcherLeadRepository(session, own).hatch()
    deactivate_member(session, scoped.admin_context, user_id=lead, now=NOW)
    late = NOW + timedelta(days=SEAL_DAYS + 1)
    assert LeadSeals(session, scoped.admin_context).unseal(lead, now=late) is False

    back = reactivate_member(session, scoped.admin_context, user_id=lead, now=late)
    assert (back.lead_unsealed, back.lead_erased) == (False, True)
    assert LeadSeals(session, scoped.admin_context).seals() == {}
    assert ResearcherLeadRepository(session, own).get() is None
    assert ResearcherLeadRepository(session, own).is_sealed() is False
    ResearcherLeadRepository(session, own).hatch()  # a new Lead, not the old one back
    actions = session.scalars(
        select(AccessAuditRow.action).where(AccessAuditRow.subject_user_id == lead)
    ).all()
    assert "LEAD_ERASED" in actions and "LEAD_UNSEALED" not in actions


def test_only_an_administrator_seals_a_lead(scoped: Any, session: Any) -> None:
    member = scoped.resolver.organization_context(scoped.principal(scoped.users["researcher"]))
    with pytest.raises(ScopeDenied):
        deactivate_member(session, member, user_id=scoped.users["lead"], now=NOW)
    with pytest.raises(ScopeDenied):
        LeadSeals(session, member)
