"""The client-level scope (ADR 0015 decision 6) and a study's kind (decision 2).

A ClientContext is issued only by ScopeResolver.client_context, for an active member of
the client's organization (ADR 0019: membership is the access; there are no grants to
consult). It is how the client workspace -- its studies and its knowledge -- is reached;
a client of another organization, an unknown one and an archived one fail closed.
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
            client_role=ScopeRole.RESEARCHER,
            permissions=frozenset(ClientPermission),
            organization_role=OrganizationRole.MEMBER,
            grant=object(),  # type: ignore[arg-type]
        )
    assert denied.value.reason == "forged_scope"


def test_a_retired_stored_role_reads_as_a_researcher() -> None:
    # ADR 0019: grants written before it may carry VIEWER, REVIEWER or LEAD.
    for stored in ("VIEWER", "REVIEWER", "LEAD", "RESEARCHER"):
        assert ScopeRole.from_stored(stored) is ScopeRole.RESEARCHER
    with pytest.raises(ValueError):
        ScopeRole.from_stored("ADMIN")


def test_a_member_opens_the_client_with_all_its_studies(scoped: Any) -> None:
    ctx = client_scope(scoped, "lead")
    assert ctx.client_role is ScopeRole.RESEARCHER
    assert ctx.study_ids == {scoped.studies["primary"].study_id, scoped.studies["sibling"].study_id}
    assert ctx.has(ClientPermission.APPROVE_CLIENT_KNOWLEDGE)


def test_another_clients_lead_opens_the_client_too(scoped: Any) -> None:
    """ADR 0019 decision 2: the lead of one client is a Researcher on every client."""
    ctx = client_scope(scoped, "other_lead", "primary")
    assert ctx.client_role is ScopeRole.RESEARCHER
    assert ctx.study_ids == {scoped.studies["primary"].study_id, scoped.studies["sibling"].study_id}
    assert ctx.permissions == frozenset(ClientPermission)


def test_an_organization_owner_is_a_researcher_on_every_client(scoped: Any) -> None:
    # ADR 0019 retired ADR 0004's "administration is not data access".
    ctx = client_scope(scoped, "owner")
    assert ctx.client_role is ScopeRole.RESEARCHER
    assert ctx.permissions == frozenset(ClientPermission)


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
    # The archived client drops out of the list; the other client is still there.
    assert scoped.resolver.accessible_clients(scoped.principal(scoped.users["lead"])) == [
        scoped.clients["other"].client_id
    ]


def test_a_member_with_no_grant_opens_the_client_with_its_studies_and_knowledge(
    scoped: Any,
) -> None:
    member = scoped.scope_repo.add_member(scoped.admin_context, email="guest@art-chain.io")
    ctx = scoped.resolver.client_context(
        scoped.principal(member.user_id), client_id=scoped.clients["primary"].client_id
    )
    assert ctx.client_role is ScopeRole.RESEARCHER
    assert ctx.study_ids == {scoped.studies["primary"].study_id, scoped.studies["sibling"].study_id}
    assert ctx.permissions == frozenset(ClientPermission)
    ctx.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
    listed = scoped.scope_repo.studies_in_client(ctx)
    assert {s.study_id for s in listed} == {
        scoped.studies["primary"].study_id,
        scoped.studies["sibling"].study_id,
    }


def test_every_member_sees_every_unarchived_client(scoped: Any) -> None:
    everything = sorted(c.client_id for c in scoped.clients.values())
    for user in ("lead", "other_lead", "outsider", "owner"):
        assert (
            scoped.resolver.accessible_clients(scoped.principal(scoped.users[user])) == everything
        )


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


def test_every_person_with_the_client_starts_work_for_it_and_it_is_audited(
    scoped: Any, session: Any
) -> None:
    """ADR 0019: one role, so no one with the client needs a second grant to start a study.

    Each label below held a different power before ADR 0019 (the viewer and the reviewer could
    not start work); they hold the same Researcher grant now, and each one's study is audited.
    """
    studies = {}
    for user in ("viewer", "reviewer", "researcher", "lead"):
        ctx = client_scope(scoped, user)
        assert ctx.has(ClientPermission.CREATE_STUDY)
        studies[user] = scoped.scope_repo.create_study_in_client(
            ctx, slug=f"by-{user}", name="Brand 2027", kind=StudyKind.RESEARCH
        )
        assert studies[user].client_id == scoped.clients["primary"].client_id
    for user, study in studies.items():
        audit = session.scalars(
            select(AccessAuditRow).where(
                AccessAuditRow.study_id == study.study_id,
                AccessAuditRow.action == "STUDY_CREATED",
            )
        ).all()
        assert [a.payload for a in audit] == [{"kind": "RESEARCH", "via": "client_workspace"}], user


def test_a_person_with_no_grant_starts_work_for_the_client_too(scoped: Any, session: Any) -> None:
    # ADR 0019: membership is the access, so a member who was never granted the client
    # may start work for it, and the study is audited like any other.
    ctx = client_scope(scoped, "outsider")
    assert ctx.has(ClientPermission.CREATE_STUDY)
    study = scoped.scope_repo.create_study_in_client(
        ctx, slug="by-outsider", name="Brand 2027", kind=StudyKind.RESEARCH
    )
    assert study.client_id == scoped.clients["primary"].client_id
    audit = session.scalars(
        select(AccessAuditRow).where(
            AccessAuditRow.study_id == study.study_id, AccessAuditRow.action == "STUDY_CREATED"
        )
    ).all()
    assert [a.actor_id for a in audit] == [scoped.users["outsider"]]


def test_a_new_member_may_do_everything_for_the_client(
    scoped: Any,
) -> None:
    """ADR 0019: a member added a moment ago needs nothing granted to work for a client."""
    member = scoped.scope_repo.add_member(scoped.admin_context, email="guest2@art-chain.io")
    ctx = scoped.resolver.client_context(
        scoped.principal(member.user_id), client_id=scoped.clients["primary"].client_id
    )
    assert ctx.permissions == frozenset(ClientPermission)
    study = scoped.scope_repo.create_study_in_client(
        ctx, slug="x", name="x", kind=StudyKind.RESEARCH
    )
    assert study.client_id == scoped.clients["primary"].client_id
