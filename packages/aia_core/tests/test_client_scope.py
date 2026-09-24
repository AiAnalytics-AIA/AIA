"""The client-level scope (ADR 0015 decision 6) and a study's kind (decision 2).

A ClientContext is issued only by ScopeResolver.client_context, from persisted
grants. It is how the client workspace -- its studies, and later its knowledge --
is reached; everything a client does not authorise fails closed.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from aia_core.domain.scope import (
    ClientContext,
    ClientPermission,
    ClientStatus,
    OrganizationRole,
    ScopeDenied,
    ScopeRole,
    StudyKind,
)
from aia_core.infrastructure.tables import AccessAuditRow


def client_scope(scoped: Any, user: str, client: str = "primary") -> ClientContext:
    return scoped.resolver.client_context(
        scoped.principal(scoped.users[user]), client_id=scoped.clients[client].client_id
    )


def test_a_client_context_cannot_be_constructed_directly() -> None:
    with pytest.raises(ScopeDenied) as denied:
        ClientContext(
            organization_id="ORG-1",
            client_id="CLI-1",
            actor_id="USR-1",
            client_role=ScopeRole.LEAD,
            permissions=frozenset(ClientPermission),
            organization_role=OrganizationRole.MEMBER,
            grant=object(),  # type: ignore[arg-type]
        )
    assert denied.value.reason == "forged_scope"


def test_a_client_grant_opens_the_client_with_all_its_studies(scoped: Any) -> None:
    ctx = client_scope(scoped, "lead")
    assert ctx.client_role is ScopeRole.LEAD
    assert ctx.study_ids == {scoped.studies["primary"].study_id, scoped.studies["sibling"].study_id}
    assert ctx.has(ClientPermission.APPROVE_CLIENT_KNOWLEDGE)


def test_another_clients_lead_cannot_open_the_client(scoped: Any) -> None:
    with pytest.raises(ScopeDenied) as denied:
        client_scope(scoped, "other_lead", "primary")
    assert denied.value.reason == "no_grant"


def test_an_organization_owner_has_no_implicit_client_access(scoped: Any) -> None:
    # ADR 0004: administration is not data access.
    with pytest.raises(ScopeDenied):
        client_scope(scoped, "owner")


def test_an_unknown_or_archived_client_is_not_found(scoped: Any) -> None:
    with pytest.raises(ScopeDenied) as unknown:
        scoped.resolver.client_context(scoped.principal(scoped.users["lead"]), client_id="CLI-0000")
    assert unknown.value.reason == "unknown_client"
    scoped.scope_repo.set_client_status(
        scoped.admin_context,
        client_id=scoped.clients["primary"].client_id,
        status=ClientStatus.ARCHIVED,
    )
    with pytest.raises(ScopeDenied) as archived:
        client_scope(scoped, "lead")
    assert archived.value.reason == "client_archived"
    assert scoped.resolver.accessible_clients(scoped.principal(scoped.users["lead"])) == []


def test_a_study_grant_alone_opens_only_that_study_and_no_knowledge(scoped: Any) -> None:
    member = scoped.scope_repo.add_member(scoped.admin_context, email="guest@art-chain.io")
    lead = scoped.resolver.study_context(
        scoped.principal(scoped.users["lead"]), study_id=scoped.studies["sibling"].study_id
    )
    scoped.resolver.grant_study_access(lead, user_id=member.user_id, role=ScopeRole.RESEARCHER)
    ctx = scoped.resolver.client_context(
        scoped.principal(member.user_id), client_id=scoped.clients["primary"].client_id
    )
    assert ctx.client_role is None
    assert ctx.study_ids == {scoped.studies["sibling"].study_id}
    assert ctx.permissions == {ClientPermission.VIEW_CLIENT}
    with pytest.raises(ScopeDenied):
        ctx.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
    listed = scoped.scope_repo.studies_in_client(ctx)
    assert [s.study_id for s in listed] == [scoped.studies["sibling"].study_id]


def test_accessible_clients_are_the_granted_ones_only(scoped: Any) -> None:
    ids = {name: c.client_id for name, c in scoped.clients.items()}
    assert scoped.resolver.accessible_clients(scoped.principal(scoped.users["lead"])) == [
        ids["primary"]
    ]
    assert scoped.resolver.accessible_clients(scoped.principal(scoped.users["other_lead"])) == [
        ids["other"]
    ]
    assert scoped.resolver.accessible_clients(scoped.principal(scoped.users["outsider"])) == []
    assert scoped.resolver.accessible_clients(scoped.principal(scoped.users["owner"])) == []


def test_a_clients_studies_never_include_another_clients(scoped: Any) -> None:
    listed = scoped.scope_repo.studies_in_client(client_scope(scoped, "lead"))
    assert {s.client_id for s in listed} == {scoped.clients["primary"].client_id}
    assert scoped.studies["other_client"].study_id not in {s.study_id for s in listed}
    other = scoped.scope_repo.studies_in_client(client_scope(scoped, "other_lead", "other"))
    assert [s.study_id for s in other] == [scoped.studies["other_client"].study_id]


def test_research_and_simulation_are_both_studies_told_apart_by_kind(scoped: Any) -> None:
    ctx = client_scope(scoped, "researcher")
    sim = scoped.scope_repo.create_study_in_client(
        ctx, slug="ev-pricing", name="EV pricing", kind=StudyKind.SIMULATION
    )
    assert scoped.studies["primary"].kind is StudyKind.RESEARCH
    fresh = client_scope(scoped, "researcher")
    sims = scoped.scope_repo.studies_in_client(fresh, kind=StudyKind.SIMULATION)
    research = scoped.scope_repo.studies_in_client(fresh, kind=StudyKind.RESEARCH)
    assert [s.study_id for s in sims] == [sim.study_id]
    assert sim.study_id not in {s.study_id for s in research}
    # The same study object either way: scope, lifecycle and permissions resolve as for any study.
    study = scoped.resolver.study_context(
        scoped.principal(scoped.users["researcher"]), study_id=sim.study_id
    )
    assert study.client_id == scoped.clients["primary"].client_id
    assert study.role is ScopeRole.RESEARCHER


def test_starting_work_for_a_client_needs_create_study_and_is_audited(
    scoped: Any, session: Any
) -> None:
    for user in ("viewer", "reviewer"):
        with pytest.raises(ScopeDenied):
            scoped.scope_repo.create_study_in_client(
                client_scope(scoped, user), slug=f"by-{user}", name="x", kind=StudyKind.RESEARCH
            )
    study = scoped.scope_repo.create_study_in_client(
        client_scope(scoped, "lead"), slug="brand-2027", name="Brand 2027", kind=StudyKind.RESEARCH
    )
    assert study.client_id == scoped.clients["primary"].client_id
    audit = session.scalars(
        select(AccessAuditRow).where(
            AccessAuditRow.study_id == study.study_id, AccessAuditRow.action == "STUDY_CREATED"
        )
    ).all()
    assert [a.payload for a in audit] == [{"kind": "RESEARCH", "via": "client_workspace"}]


def test_a_study_only_grantee_cannot_start_work_for_the_client(scoped: Any) -> None:
    member = scoped.scope_repo.add_member(scoped.admin_context, email="guest2@art-chain.io")
    lead = scoped.resolver.study_context(
        scoped.principal(scoped.users["lead"]), study_id=scoped.studies["primary"].study_id
    )
    scoped.resolver.grant_study_access(lead, user_id=member.user_id, role=ScopeRole.LEAD)
    ctx = scoped.resolver.client_context(
        scoped.principal(member.user_id), client_id=scoped.clients["primary"].client_id
    )
    with pytest.raises(ScopeDenied):
        scoped.scope_repo.create_study_in_client(ctx, slug="x", name="x", kind=StudyKind.RESEARCH)
