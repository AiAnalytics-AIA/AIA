"""Authorization and isolation tests for the Organization/Client/Study model.

These are the tests that matter most in the whole suite. AIA holds confidential
research for competing clients, and the product rule is that Client and Study are
hard boundaries. A regression here is a client-confidentiality incident, not a
bug.

Two properties are asserted repeatedly and deliberately:

* **Denial is indistinguishable from absence.** Every failure raises
  ``ScopeDenied`` and the API renders 404, because a 403 would confirm that
  another client's engagement exists.
* **Scope cannot come from an argument.** A ``StudyContext`` can only be issued
  by the authorization layer from a verified principal, so an AI tool, a job
  payload or an HTTP body cannot widen its own scope.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.scope import (
    ClientStatus,
    OrganizationContext,
    OrganizationRole,
    Permission,
    ScopeDenied,
    ScopeGrant,
    ScopeRole,
    StudyContext,
    StudyStatus,
    effective_role,
    permissions_for,
)
from aia_core.infrastructure.repositories import ProjectNotFound, ProjectRepository
from aia_core.infrastructure.scope_repository import ScopeRepository


@pytest.fixture
def scope_repo(session: Session) -> ScopeRepository:
    return ScopeRepository(session)


@pytest.fixture
def resolver(session: Session) -> ScopeResolver:
    return ScopeResolver(session)


@pytest.fixture
def world(scope_repo: ScopeRepository, resolver: ScopeResolver) -> dict[str, Any]:
    """A realistic two-client world.

    Deliberately models the dangerous case: one organization, two clients who may
    be competitors, and researchers who must not see across the boundary.
    """
    org, owner = scope_repo.create_organization(
        slug="aia", name="AI Analytics", owner_email="owner@art-chain.io", owner_name="Owner"
    )
    admin_principal = AuthenticatedPrincipal(
        user_id=owner.user_id, organization_id=org.organization_id, request_id="req-setup"
    )
    admin = resolver.organization_context(admin_principal)

    acme = scope_repo.create_client(admin, slug="acme", name="Acme Corp")
    globex = scope_repo.create_client(admin, slug="globex", name="Globex Inc")

    acme_study = scope_repo.create_study(
        admin,
        client_id=acme.client_id,
        slug="brand-2026",
        name="Acme brand study",
        budget_usd=500.0,
    )
    globex_study = scope_repo.create_study(
        admin,
        client_id=globex.client_id,
        slug="pricing-2026",
        name="Globex pricing",
        budget_usd=300.0,
    )

    researcher = scope_repo.add_member(admin, email="researcher@art-chain.io")
    reviewer = scope_repo.add_member(admin, email="reviewer@art-chain.io")
    outsider = scope_repo.add_member(admin, email="outsider@art-chain.io")

    # The researcher works for Acme only. The reviewer reviews Acme only.
    resolver.grant_client_access(
        admin,
        client_id=acme.client_id,
        user_id=researcher.user_id,
        role=ScopeRole.RESEARCHER,
    )
    resolver.grant_client_access(
        admin,
        client_id=acme.client_id,
        user_id=reviewer.user_id,
        role=ScopeRole.REVIEWER,
    )

    def principal(user_id: str, req: str = "req-1") -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            user_id=user_id, organization_id=org.organization_id, request_id=req
        )

    return {
        "org": org,
        "admin": admin,
        "admin_principal": admin_principal,
        "owner_id": owner.user_id,
        "acme": acme,
        "globex": globex,
        "acme_study": acme_study,
        "globex_study": globex_study,
        "researcher": researcher.user_id,
        "reviewer": reviewer.user_id,
        "outsider": outsider.user_id,
        "principal": principal,
    }


# --------------------------------------------------------------------------- #
# Scope cannot be forged
# --------------------------------------------------------------------------- #


def test_study_context_cannot_be_constructed_directly() -> None:
    """A StudyContext requires a grant only the authorization layer can issue.

    This is the structural guarantee behind "no AI-generated argument may
    determine client or study scope": even with every field known, a caller
    cannot manufacture a context.
    """
    with pytest.raises(ScopeDenied) as exc:
        StudyContext(
            organization_id="ORG-x",
            client_id="CLI-x",
            study_id="STU-x",
            actor_id="USR-x",
            role=ScopeRole.LEAD,
            permissions=permissions_for(ScopeRole.LEAD),
            organization_role=OrganizationRole.OWNER,
            grant=object(),  # type: ignore[arg-type]
        )
    assert exc.value.reason == "forged_scope"


def test_scope_grant_cannot_be_forged() -> None:
    """ScopeGrant rejects any issuer that is not the private sentinel."""
    for bogus in (None, object(), "issuer", 1, {"issuer": True}):
        with pytest.raises(ScopeDenied) as exc:
            ScopeGrant(_issuer=bogus)
        assert exc.value.reason == "forged_scope"


def test_organization_context_cannot_be_forged() -> None:
    """The administrative context is equally unforgeable."""
    with pytest.raises(ScopeDenied):
        OrganizationContext(
            organization_id="ORG-x",
            actor_id="USR-x",
            organization_role=OrganizationRole.OWNER,
            grant=object(),  # type: ignore[arg-type]
        )


def test_study_context_rejects_incomplete_scope(world: dict[str, Any]) -> None:
    """Every scope field is required; a blank client id is not a wildcard."""
    grant = ScopeGrant._issue()
    with pytest.raises(ScopeDenied) as exc:
        StudyContext(
            organization_id="ORG-x",
            client_id="",
            study_id="STU-x",
            actor_id="USR-x",
            role=ScopeRole.LEAD,
            permissions=permissions_for(ScopeRole.LEAD),
            organization_role=OrganizationRole.OWNER,
            grant=grant,
        )
    assert exc.value.reason == "incomplete"


def test_project_repository_refuses_anything_but_a_study_context(
    session: Session,
) -> None:
    """The repository cannot be built from a plain dict or an id.

    A model-supplied payload shaped like a scope is rejected by type, not parsed.
    """
    for bogus in (
        None,
        "ORG-x",
        {"organization_id": "ORG-x", "client_id": "CLI-x", "study_id": "STU-x"},
    ):
        with pytest.raises(TypeError, match="requires a StudyContext"):
            ProjectRepository(session, bogus)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Client isolation
# --------------------------------------------------------------------------- #


def test_researcher_cannot_reach_another_clients_study(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """The central confidentiality guarantee.

    An Acme researcher resolving Globex's study must be denied, and the denial
    must be indistinguishable from the study not existing.
    """
    principal = world["principal"](world["researcher"])

    # Acme resolves.
    scope = resolver.study_context(principal, study_id=world["acme_study"].study_id)
    assert scope.client_id == world["acme"].client_id
    assert scope.role is ScopeRole.RESEARCHER

    # Globex does not.
    with pytest.raises(ScopeDenied) as exc:
        resolver.study_context(principal, study_id=world["globex_study"].study_id)
    assert exc.value.reason == "no_grant"
    assert "not found" in str(exc.value)


def test_organization_member_without_a_grant_sees_nothing(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """Organization membership alone grants no access to client data."""
    principal = world["principal"](world["outsider"])

    for study in (world["acme_study"], world["globex_study"]):
        with pytest.raises(ScopeDenied) as exc:
            resolver.study_context(principal, study_id=study.study_id)
        assert exc.value.reason == "no_grant"

    assert resolver.accessible_studies(principal) == []


def test_organization_admin_has_no_implicit_client_data_access(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """An administrator can create clients but cannot read their research.

    Separating "may administer" from "may read client data" is what makes the
    client boundary meaningful on a team where everyone is effectively an admin.
    """
    admin_principal = world["admin_principal"]

    with pytest.raises(ScopeDenied) as exc:
        resolver.study_context(admin_principal, study_id=world["acme_study"].study_id)
    assert exc.value.reason == "no_grant"


def test_admin_self_grant_works_and_is_audited(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """Break-glass access is possible but visible.

    Someone has to be able to start work on a new client. The self-grant is
    recorded under its own action so it is distinguishable from ordinary
    provisioning when the log is reviewed.
    """
    admin = world["admin"]
    resolver.grant_client_access(
        admin,
        client_id=world["acme"].client_id,
        user_id=world["owner_id"],
        role=ScopeRole.LEAD,
    )

    scope = resolver.study_context(world["admin_principal"], study_id=world["acme_study"].study_id)
    assert scope.role is ScopeRole.LEAD

    actions = [e["action"] for e in resolver.audit_trail(admin)]
    assert "CLIENT_SELF_GRANT" in actions
    assert "CLIENT_GRANT" in actions  # the researcher grant from setup


def test_archived_client_denies_access(
    resolver: ScopeResolver, scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """Archiving a client closes access to its studies immediately."""
    principal = world["principal"](world["researcher"])
    resolver.study_context(principal, study_id=world["acme_study"].study_id)

    scope_repo.set_client_status(
        world["admin"], client_id=world["acme"].client_id, status=ClientStatus.ARCHIVED
    )

    with pytest.raises(ScopeDenied) as exc:
        resolver.study_context(principal, study_id=world["acme_study"].study_id)
    assert exc.value.reason == "client_archived"


def test_deactivated_user_loses_access_immediately(
    resolver: ScopeResolver, scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """Deactivation takes effect now, not at token expiry.

    Checked on every resolution precisely so that a valid token still in
    circulation cannot be used after an account is disabled.
    """
    principal = world["principal"](world["researcher"])
    resolver.study_context(principal, study_id=world["acme_study"].study_id)

    scope_repo.deactivate_user(world["admin"], user_id=world["researcher"])

    with pytest.raises(ScopeDenied) as exc:
        resolver.study_context(principal, study_id=world["acme_study"].study_id)
    assert exc.value.reason == "user_deactivated"


def test_principal_from_another_organization_is_denied(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """A study is only resolvable within its own organization."""
    foreign = AuthenticatedPrincipal(
        user_id=world["researcher"], organization_id="ORG-someone-else"
    )
    with pytest.raises(ScopeDenied) as exc:
        resolver.study_context(foreign, study_id=world["acme_study"].study_id)
    assert exc.value.reason == "not_a_member"


def test_unknown_study_is_denied_without_an_audit_entry(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """A nonexistent id is noise, and must not let a prober fill the audit log."""
    principal = world["principal"](world["researcher"])
    before = len(resolver.audit_trail(world["admin"]))

    for _ in range(5):
        with pytest.raises(ScopeDenied) as exc:
            resolver.study_context(principal, study_id="STU-does-not-exist")
        assert exc.value.reason == "unknown_study"

    assert len(resolver.audit_trail(world["admin"])) == before


def test_denied_grant_attempt_is_audited(resolver: ScopeResolver, world: dict[str, Any]) -> None:
    """A member reaching for a study they hold no grant on is worth recording."""
    principal = world["principal"](world["outsider"])

    with pytest.raises(ScopeDenied):
        resolver.study_context(principal, study_id=world["acme_study"].study_id)

    entries = resolver.audit_trail(world["admin"])
    denials = [e for e in entries if e["action"] == "ACCESS_DENIED"]
    assert denials
    assert denials[0]["study_id"] == world["acme_study"].study_id
    assert denials[0]["actor_id"] == world["outsider"]


# --------------------------------------------------------------------------- #
# Role resolution
# --------------------------------------------------------------------------- #


def test_study_grant_overrides_client_grant_in_both_directions() -> None:
    """A study grant is authoritative, even when narrower.

    That is the point: a client LEAD can be deliberately restricted to VIEWER on
    one sensitive study.
    """
    assert effective_role(client_role=ScopeRole.VIEWER, study_role=ScopeRole.LEAD) is ScopeRole.LEAD
    assert (
        effective_role(client_role=ScopeRole.LEAD, study_role=ScopeRole.VIEWER) is ScopeRole.VIEWER
    )
    assert effective_role(client_role=ScopeRole.RESEARCHER, study_role=None) is (
        ScopeRole.RESEARCHER
    )
    assert effective_role(client_role=None, study_role=None) is None


def test_study_grant_narrows_an_existing_client_grant(
    resolver: ScopeResolver, session: Session, world: dict[str, Any]
) -> None:
    """The narrowing case, end to end against the database."""
    principal = world["principal"](world["researcher"])
    assert (
        resolver.study_context(principal, study_id=world["acme_study"].study_id).role
        is ScopeRole.RESEARCHER
    )

    # A LEAD on the study restricts the researcher to VIEWER on it.
    lead_scope = resolver.study_context(
        world["principal"](world["researcher"]), study_id=world["acme_study"].study_id
    )
    resolver.grant_client_access(
        world["admin"],
        client_id=world["acme"].client_id,
        user_id=world["owner_id"],
        role=ScopeRole.LEAD,
    )
    owner_scope = resolver.study_context(
        world["admin_principal"], study_id=world["acme_study"].study_id
    )
    resolver.grant_study_access(owner_scope, user_id=world["researcher"], role=ScopeRole.VIEWER)

    narrowed = resolver.study_context(principal, study_id=world["acme_study"].study_id)
    assert narrowed.role is ScopeRole.VIEWER
    assert not narrowed.has(Permission.EDIT_STUDY)
    assert lead_scope.role is ScopeRole.RESEARCHER  # the old context is unchanged


def test_study_grant_widens_access_for_a_single_study(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """Someone with no client grant can be brought in for one study only."""
    principal = world["principal"](world["outsider"])

    resolver.grant_client_access(
        world["admin"],
        client_id=world["globex"].client_id,
        user_id=world["owner_id"],
        role=ScopeRole.LEAD,
    )
    owner_scope = resolver.study_context(
        world["admin_principal"], study_id=world["globex_study"].study_id
    )
    resolver.grant_study_access(owner_scope, user_id=world["outsider"], role=ScopeRole.RESEARCHER)

    # They can reach that one study...
    scope = resolver.study_context(principal, study_id=world["globex_study"].study_id)
    assert scope.role is ScopeRole.RESEARCHER
    # ...and nothing else.
    assert resolver.accessible_studies(principal) == [world["globex_study"].study_id]
    with pytest.raises(ScopeDenied):
        resolver.study_context(principal, study_id=world["acme_study"].study_id)


def test_reviewer_can_approve_but_not_edit(resolver: ScopeResolver, world: dict[str, Any]) -> None:
    """Review independence: a reviewer must not be able to edit what they approve."""
    scope = resolver.study_context(
        world["principal"](world["reviewer"]), study_id=world["acme_study"].study_id
    )

    assert scope.has(Permission.APPROVE_GATE)
    assert scope.has(Permission.SIGN_OFF_DELIVERABLE)
    assert not scope.has(Permission.EDIT_STUDY)
    assert not scope.has(Permission.RUN_WORKFLOW)

    with pytest.raises(ScopeDenied) as exc:
        scope.require(Permission.EDIT_STUDY)
    assert exc.value.reason == "insufficient_role"


def test_researcher_can_work_but_not_approve_own_work(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """A researcher cannot sign off their own deliverable."""
    scope = resolver.study_context(
        world["principal"](world["researcher"]), study_id=world["acme_study"].study_id
    )

    assert scope.has(Permission.EDIT_STUDY)
    assert scope.has(Permission.RUN_WORKFLOW)
    assert not scope.has(Permission.SIGN_OFF_DELIVERABLE)
    assert not scope.has(Permission.APPROVE_GATE)
    assert not scope.has(Permission.MANAGE_STUDY_BUDGET)


def test_required_permission_is_checked_at_resolution(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """Resolution can demand a permission up front, and audits the refusal."""
    principal = world["principal"](world["reviewer"])

    resolver.study_context(
        principal, study_id=world["acme_study"].study_id, require=Permission.APPROVE_GATE
    )

    with pytest.raises(ScopeDenied):
        resolver.study_context(
            principal,
            study_id=world["acme_study"].study_id,
            require=Permission.EDIT_STUDY,
        )

    actions = [e["action"] for e in resolver.audit_trail(world["admin"])]
    assert "PERMISSION_DENIED" in actions


def test_permission_sets_are_monotonic_by_capability() -> None:
    """Higher roles must not lose a capability a lower role has.

    Except review authority, which is deliberately not granted to RESEARCHER.
    """
    viewer = permissions_for(ScopeRole.VIEWER)
    researcher = permissions_for(ScopeRole.RESEARCHER)
    lead = permissions_for(ScopeRole.LEAD)

    assert viewer < researcher < lead
    assert permissions_for(ScopeRole.REVIEWER) < lead


# --------------------------------------------------------------------------- #
# Projects are scoped to a study
# --------------------------------------------------------------------------- #


def test_projects_are_invisible_across_clients(
    resolver: ScopeResolver, session: Session, world: dict[str, Any]
) -> None:
    """A project created under one client is unreachable from another.

    Both by id and by listing -- the two ways a leak would actually happen.
    """
    acme_scope = resolver.study_context(
        world["principal"](world["researcher"]), study_id=world["acme_study"].study_id
    )
    acme_repo = ProjectRepository(session, acme_scope)
    project, _ = acme_repo.create(title="Acme confidential", content={"goal": "secret"})

    # Give the owner access to Globex only, and try to reach the Acme project.
    resolver.grant_client_access(
        world["admin"],
        client_id=world["globex"].client_id,
        user_id=world["owner_id"],
        role=ScopeRole.LEAD,
    )
    globex_scope = resolver.study_context(
        world["admin_principal"], study_id=world["globex_study"].study_id
    )
    globex_repo = ProjectRepository(session, globex_scope)

    with pytest.raises(ProjectNotFound):
        globex_repo.get(project.project_id)
    with pytest.raises(ProjectNotFound):
        globex_repo.content(project.project_id)
    with pytest.raises(ProjectNotFound):
        globex_repo.save(project.project_id, content={"goal": "hijacked"})

    assert globex_repo.list_projects().total == 0
    assert acme_repo.list_projects().total == 1
    assert acme_repo.get(project.project_id).title == "Acme confidential"


def test_projects_are_invisible_across_studies_of_one_client(
    resolver: ScopeResolver,
    scope_repo: ScopeRepository,
    session: Session,
    world: dict[str, Any],
) -> None:
    """Study is a boundary too, not only client.

    Two engagements for the same client must not see each other's projects.
    """
    second = scope_repo.create_study(
        world["admin"],
        client_id=world["acme"].client_id,
        slug="pricing-2026",
        name="Acme pricing",
    )

    principal = world["principal"](world["researcher"])
    first_scope = resolver.study_context(principal, study_id=world["acme_study"].study_id)
    second_scope = resolver.study_context(principal, study_id=second.study_id)

    project, _ = ProjectRepository(session, first_scope).create(title="Study one work")

    assert ProjectRepository(session, second_scope).list_projects().total == 0
    with pytest.raises(ProjectNotFound):
        ProjectRepository(session, second_scope).get(project.project_id)


def test_project_rows_carry_client_and_study(
    resolver: ScopeResolver, session: Session, world: dict[str, Any]
) -> None:
    """Every client-derived object resolves to client and study scope."""
    from aia_core.infrastructure.tables import ProjectRow

    scope = resolver.study_context(
        world["principal"](world["researcher"]), study_id=world["acme_study"].study_id
    )
    project, _ = ProjectRepository(session, scope).create(title="Scoped")

    row = session.get(ProjectRow, project.project_id)
    assert row is not None
    assert row.organization_id == scope.organization_id
    assert row.client_id == world["acme"].client_id
    assert row.study_id == world["acme_study"].study_id


def test_viewer_cannot_create_or_edit_a_project(
    resolver: ScopeResolver, session: Session, world: dict[str, Any]
) -> None:
    """Write permission is enforced in the repository, not only in the API."""
    reviewer_scope = resolver.study_context(
        world["principal"](world["reviewer"]), study_id=world["acme_study"].study_id
    )
    repo = ProjectRepository(session, reviewer_scope)

    with pytest.raises(ScopeDenied) as exc:
        repo.create(title="Should not exist")
    assert exc.value.reason == "insufficient_role"


def test_reviewer_can_read_projects_they_cannot_edit(
    resolver: ScopeResolver, session: Session, world: dict[str, Any]
) -> None:
    """Read access is unaffected by lacking write access."""
    researcher_scope = resolver.study_context(
        world["principal"](world["researcher"]), study_id=world["acme_study"].study_id
    )
    project, _ = ProjectRepository(session, researcher_scope).create(title="Readable")

    reviewer_scope = resolver.study_context(
        world["principal"](world["reviewer"]), study_id=world["acme_study"].study_id
    )
    reviewer_repo = ProjectRepository(session, reviewer_scope)

    assert reviewer_repo.get(project.project_id).title == "Readable"
    assert reviewer_repo.list_projects().total == 1
    with pytest.raises(ScopeDenied):
        reviewer_repo.save(project.project_id, content={"x": 1})


def test_closed_study_accepts_no_new_work(
    resolver: ScopeResolver,
    scope_repo: ScopeRepository,
    session: Session,
    world: dict[str, Any],
) -> None:
    """A delivered study is frozen: new work would alter what a client was shown."""
    resolver.grant_client_access(
        world["admin"],
        client_id=world["acme"].client_id,
        user_id=world["owner_id"],
        role=ScopeRole.LEAD,
    )
    lead_scope = resolver.study_context(
        world["admin_principal"], study_id=world["acme_study"].study_id
    )
    scope_repo.set_study_status(lead_scope, StudyStatus.DELIVERED)

    fresh = resolver.study_context(world["admin_principal"], study_id=world["acme_study"].study_id)
    assert fresh.study_status is StudyStatus.DELIVERED

    with pytest.raises(ScopeDenied) as exc:
        ProjectRepository(session, fresh).create(title="Late addition")
    assert exc.value.reason == "study_closed"


# --------------------------------------------------------------------------- #
# Study administration
# --------------------------------------------------------------------------- #


def test_only_admins_can_create_clients_and_studies(
    resolver: ScopeResolver, scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """A plain member cannot provision clients."""
    member_ctx = resolver.organization_context(world["principal"](world["researcher"]))
    assert member_ctx.organization_role is OrganizationRole.MEMBER

    with pytest.raises(ScopeDenied) as exc:
        scope_repo.create_client(member_ctx, slug="rogue", name="Rogue")
    assert exc.value.reason == "insufficient_role"

    with pytest.raises(ScopeDenied):
        scope_repo.create_study(member_ctx, client_id=world["acme"].client_id, slug="x", name="X")


def test_study_lead_can_staff_their_own_study(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """MANAGE_STUDY_ACCESS lets a lead add people without org administration."""
    resolver.grant_client_access(
        world["admin"],
        client_id=world["acme"].client_id,
        user_id=world["owner_id"],
        role=ScopeRole.LEAD,
    )
    lead = resolver.study_context(world["admin_principal"], study_id=world["acme_study"].study_id)

    resolver.grant_study_access(lead, user_id=world["outsider"], role=ScopeRole.VIEWER)

    outsider_scope = resolver.study_context(
        world["principal"](world["outsider"]), study_id=world["acme_study"].study_id
    )
    assert outsider_scope.role is ScopeRole.VIEWER


def test_researcher_cannot_staff_a_study(resolver: ScopeResolver, world: dict[str, Any]) -> None:
    """Granting access needs lead authority, not merely edit rights."""
    scope = resolver.study_context(
        world["principal"](world["researcher"]), study_id=world["acme_study"].study_id
    )
    with pytest.raises(ScopeDenied):
        resolver.grant_study_access(scope, user_id=world["outsider"], role=ScopeRole.LEAD)


def test_budget_changes_require_authority_and_are_audited(
    resolver: ScopeResolver, scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """A study budget is money; changing it is privileged and recorded."""
    researcher_scope = resolver.study_context(
        world["principal"](world["researcher"]), study_id=world["acme_study"].study_id
    )
    with pytest.raises(ScopeDenied):
        scope_repo.set_study_budget(researcher_scope, 9999.0)

    resolver.grant_client_access(
        world["admin"],
        client_id=world["acme"].client_id,
        user_id=world["owner_id"],
        role=ScopeRole.LEAD,
    )
    lead = resolver.study_context(world["admin_principal"], study_id=world["acme_study"].study_id)
    updated = scope_repo.set_study_budget(lead, 750.0)
    assert updated.budget_usd == 750.0

    entries = [
        e for e in resolver.audit_trail(world["admin"]) if e["action"] == "STUDY_BUDGET_CHANGED"
    ]
    assert entries and "750.0" in entries[0]["reason"]


def test_study_listing_is_restricted_to_accessible_ids(
    resolver: ScopeResolver, scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """A portfolio listing is built from accessible ids, never from the table."""
    principal = world["principal"](world["researcher"])
    accessible = resolver.accessible_studies(principal)
    assert accessible == [world["acme_study"].study_id]

    studies = scope_repo.list_studies(world["admin"], study_ids=accessible)
    assert [s.study_id for s in studies] == [world["acme_study"].study_id]


def test_empty_accessible_list_returns_nothing_not_everything(
    scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """The failure mode of a forgotten filter must be an empty list, not a leak."""
    assert scope_repo.list_studies(world["admin"], study_ids=[]) == []


def test_study_slug_is_unique_per_client_not_globally(
    scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """Two clients may each have a study with the same slug."""
    a = scope_repo.create_study(
        world["admin"], client_id=world["acme"].client_id, slug="shared-slug", name="A"
    )
    b = scope_repo.create_study(
        world["admin"], client_id=world["globex"].client_id, slug="shared-slug", name="B"
    )
    assert a.study_id != b.study_id


def test_cannot_create_a_study_for_an_archived_client(
    scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """An archived relationship accepts no new engagements."""
    scope_repo.set_client_status(
        world["admin"], client_id=world["acme"].client_id, status=ClientStatus.ARCHIVED
    )
    with pytest.raises(ScopeDenied) as exc:
        scope_repo.create_study(
            world["admin"], client_id=world["acme"].client_id, slug="new", name="New"
        )
    assert exc.value.reason == "client_archived"


# --------------------------------------------------------------------------- #
# Users and identity binding
# --------------------------------------------------------------------------- #


def test_user_is_matched_by_identity_subject_before_email(
    scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """A user who changes email keeps their identity and their work.

    Matching on the provider's immutable subject claim first is what prevents a
    rename from silently creating a second account.
    """
    first = scope_repo.upsert_user(
        email="person@art-chain.io", display_name="Person", external_subject="cognito-sub-1"
    )
    renamed = scope_repo.upsert_user(
        email="new.address@art-chain.io", display_name="Person", external_subject="cognito-sub-1"
    )
    assert renamed["user_id"] == first["user_id"]


def test_preprovisioned_user_binds_subject_on_first_signin(
    scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """A user added by email before signing in keeps the same record afterwards."""
    invited = scope_repo.add_member(world["admin"], email="invited@art-chain.io")

    bound = scope_repo.upsert_user(email="invited@art-chain.io", external_subject="cognito-sub-42")
    assert bound["user_id"] == invited.user_id
    assert bound["external_subject"] == "cognito-sub-42"


@pytest.mark.parametrize(
    "bad",
    [
        "../etc",  # traversal
        "a/b",  # path separator
        "Has Spaces",
        "under_score",
        "trailing-",
        "-leading",
        "double--hyphen",
        "kli\u010dov\u00fd",  # non-ASCII: legal in a URL, not in every S3 key
        "a" * 65,
        "",
        "   ",
    ],
)
def test_slug_validation_rejects_unsafe_values(bad: str) -> None:
    """Slugs reach URLs and object storage keys, so unsafe values are refused.

    Rejected rather than sanitised: silently stripping characters would let two
    distinct client names collapse onto one slug.
    """
    from pydantic import ValidationError

    from aia_core.domain.scope import Client

    with pytest.raises(ValidationError):
        Client(organization_id="ORG-1", slug=bad, name="x")


def test_slug_normalises_case_and_whitespace() -> None:
    """ "Acme-Corp" and "acme-corp" name the same client, so case is normalised."""
    from aia_core.domain.scope import Client, Study

    assert Client(organization_id="ORG-1", slug="  Acme-Corp  ", name="x").slug == ("acme-corp")
    assert (
        Study(organization_id="ORG-1", client_id="CLI-1", slug="BRAND-2026", name="x").slug
        == "brand-2026"
    )


# --------------------------------------------------------------------------- #
# Permanent regression tests
#
# These encode two invariants that must never be relaxed. Both are cheap to
# break by "simplifying" and expensive to discover afterwards.
# --------------------------------------------------------------------------- #


def test_regression_explicit_study_restriction_beats_broader_client_privilege(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """**Specificity precedence. Never collapse this into max(role).**

        study grant
           overrides client grant
              overrides no access

    An explicit study-level *restriction* wins over a broader client-level
    privilege. A client LEAD restricted to VIEWER on one sensitive study must
    lose edit rights there and keep them elsewhere.

    Taking the maximum of the two grants would make a restriction impossible to
    express, and a restriction is precisely what a confidentiality boundary is
    for. This test exists forever.
    """
    admin = world["admin"]
    acme = world["acme"]
    researcher = world["researcher"]

    # The researcher is promoted to LEAD across the whole client.
    resolver.grant_client_access(
        admin, client_id=acme.client_id, user_id=researcher, role=ScopeRole.LEAD
    )
    principal = world["principal"](researcher)

    broad = resolver.study_context(principal, study_id=world["acme_study"].study_id)
    assert broad.role is ScopeRole.LEAD
    assert broad.has(Permission.EDIT_STUDY)

    # An owner with LEAD on the client narrows the researcher on ONE study.
    resolver.grant_client_access(
        admin, client_id=acme.client_id, user_id=world["owner_id"], role=ScopeRole.LEAD
    )
    owner_scope = resolver.study_context(
        world["admin_principal"], study_id=world["acme_study"].study_id
    )
    resolver.grant_study_access(owner_scope, user_id=researcher, role=ScopeRole.VIEWER)

    restricted = resolver.study_context(principal, study_id=world["acme_study"].study_id)

    assert restricted.role is ScopeRole.VIEWER, (
        "an explicit study restriction must beat the broader client grant; "
        "max(role) would wrongly yield LEAD"
    )
    assert not restricted.has(Permission.EDIT_STUDY)
    assert not restricted.has(Permission.SIGN_OFF_DELIVERABLE)
    assert not restricted.has(Permission.MANAGE_STUDY_ACCESS)


def test_regression_study_grant_also_widens_for_a_single_study(
    resolver: ScopeResolver, scope_repo: ScopeRepository, world: dict[str, Any]
) -> None:
    """Precedence runs both ways: a study grant can widen as well as restrict.

    The same rule that lets a lead be restricted lets an outsider be brought in
    for exactly one study and nothing else.
    """
    second = scope_repo.create_study(
        world["admin"],
        client_id=world["acme"].client_id,
        slug="second-study",
        name="Acme second",
    )
    resolver.grant_client_access(
        world["admin"],
        client_id=world["acme"].client_id,
        user_id=world["owner_id"],
        role=ScopeRole.LEAD,
    )
    lead = resolver.study_context(world["admin_principal"], study_id=second.study_id)
    resolver.grant_study_access(lead, user_id=world["outsider"], role=ScopeRole.RESEARCHER)

    principal = world["principal"](world["outsider"])
    assert resolver.study_context(principal, study_id=second.study_id).role is (
        ScopeRole.RESEARCHER
    )
    assert resolver.accessible_studies(principal) == [second.study_id]
    with pytest.raises(ScopeDenied):
        resolver.study_context(principal, study_id=world["acme_study"].study_id)


def test_self_grant_records_previous_and_new_access(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """A self-grant carries a full before/after record.

    This is the one case where administrative authority and confidential research
    access meet in the same person, so the audit entry must answer what was
    taken, by whom, from what, and why -- readable years later without
    reconstructing the roles of the day.
    """
    admin = world["admin"]
    resolver.grant_client_access(
        admin,
        client_id=world["acme"].client_id,
        user_id=world["owner_id"],
        role=ScopeRole.RESEARCHER,
        reason="starting engagement kickoff",
    )
    # Escalate their own access, which is the interesting case.
    resolver.grant_client_access(
        admin,
        client_id=world["acme"].client_id,
        user_id=world["owner_id"],
        role=ScopeRole.LEAD,
        reason="taking over as study lead",
    )

    entries = [e for e in resolver.audit_trail(admin) if e["action"] == "CLIENT_SELF_GRANT"]
    assert len(entries) == 2

    escalation = entries[0]
    payload = escalation["payload"]
    assert payload["actor_user_id"] == world["owner_id"]
    assert payload["subject_user_id"] == world["owner_id"]
    assert payload["client_id"] == world["acme"].client_id
    assert payload["previous_access"] == "RESEARCHER"
    assert payload["new_access"] == "LEAD"
    assert payload["self_grant"] is True
    assert payload["reason"] == "taking over as study lead"
    assert escalation["created_at"] is not None


def test_granting_someone_else_is_not_recorded_as_a_self_grant(
    resolver: ScopeResolver, world: dict[str, Any]
) -> None:
    """Ordinary provisioning must stay distinguishable from break-glass access."""
    resolver.grant_client_access(
        world["admin"],
        client_id=world["acme"].client_id,
        user_id=world["outsider"],
        role=ScopeRole.VIEWER,
    )
    actions = [e["action"] for e in resolver.audit_trail(world["admin"])]
    assert "CLIENT_GRANT" in actions
    self_grants = [
        e for e in resolver.audit_trail(world["admin"]) if e["action"] == "CLIENT_SELF_GRANT"
    ]
    assert self_grants == []
