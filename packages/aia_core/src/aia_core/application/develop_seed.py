"""Synthetic develop data, provisioned through the same paths production uses.

The develop environment holds no client data. This use case creates enough
valid domain state to exercise the application -- an organization with its
owner, a synthetic client and study with a budget, a project, and one example
workflow run -- by calling the repositories and the authorization layer exactly
as the API does. There is no direct insert that skips an invariant, and no
back door: the owner is provisioned as an organization OWNER and granted LEAD on
the client, and everything else is done under contexts issued for them.

**Idempotent.** Every object is found by a stable slug or title before it is
created, so re-running changes nothing and reports the same ids. ``reset``
removes the seeded organization and everything cascading from it, and nothing
else: it refuses any slug but the seed's own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.application.workflows import StartedRun, start_workflow
from aia_core.domain.knowledge import KnowledgeKind
from aia_core.domain.scope import (
    ClientStatus,
    OrganizationRole,
    ScopeRole,
    StudyContext,
    StudyKind,
    StudyStatus,
)
from aia_core.domain.workflow_templates import DEVELOP_SNAPSHOT
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import OrganizationMemberRow, OrganizationRow, StudyRow

__all__ = [
    "SEED_CLIENT_SLUG",
    "SEED_ORGANIZATION_SLUG",
    "SEED_PROJECT_TITLE",
    "SEED_STUDY_SLUG",
    "SEED_WORKSPACES",
    "SeedResult",
    "reset_develop_seed",
    "seed_develop",
    "seeded_study_scope",
]

SEED_ORGANIZATION_SLUG: Final = "aia-develop"
SEED_CLIENT_SLUG: Final = "synthetic-client"
SEED_STUDY_SLUG: Final = "develop-smoke"
SEED_STUDY_BUDGET_USD: Final = 25.0
SEED_PROJECT_TITLE: Final = "Develop smoke project"

#: Synthetic content with no client, brand or person in it. The public-library
#: topic is the one the MVP acceptance test uses for the same reason.
SEED_PROJECT_CONTENT: Final[dict[str, Any]] = {
    "goal": (
        "How do adults aged 18-65 rate five proposed changes to municipal library "
        "services, and which groups would use them?"
    ),
    "audience": {"mode": "population", "age_min": 18, "age_max": 65},
    "objects": ["service_a", "service_b", "service_c", "service_d", "service_e"],
    "synthetic": True,
}


# The client-first world (ADR 0015): two fictional clients -- invented names, no
# real company, brand or person -- each with research, a simulation, approved
# knowledge and one pending update, so every area of the client workspace has
# something true to show on develop. Each tuple is (slug, name, kind, status).
SEED_WORKSPACES: Final[dict[str, dict[str, Any]]] = {
    "horizont-mobility": {
        "name": "Horizont Mobility (fiktivní)",
        "studies": [
            ("vnimani-znacky-2026", "Vnímání značky 2026", StudyKind.RESEARCH, StudyStatus.ACTIVE),
            (
                "segmentace-flotil",
                "Segmentace flotilových zákazníků",
                StudyKind.RESEARCH,
                StudyStatus.DRAFT,
            ),
            (
                "cenove-scenare-ev-2027",
                "Cenové scénáře elektromobilů 2027",
                StudyKind.SIMULATION,
                StudyStatus.ACTIVE,
            ),
            (
                "spokojenost-servisu-2025",
                "Spokojenost se servisem 2025",
                StudyKind.RESEARCH,
                StudyStatus.DELIVERED,
            ),
        ],
        "knowledge": [
            (
                KnowledgeKind.SOURCE,
                "Výroční zpráva 2025",
                "Fiktivní podklad klienta: obchodní síť a produktové řady.",
            ),
            (
                KnowledgeKind.TERM,
                "Flotilový zákazník",
                "Firma s pěti a více vozy na leasing nebo v majetku.",
            ),
            (
                KnowledgeKind.FINDING,
                "Zákazníci do 35 let rozhodují hlavně podle ceny",
                "Z výzkumu Spokojenost se servisem 2025.",
            ),
            (
                KnowledgeKind.DIMENSION,
                "Vztah k elektromobilitě",
                "Klientská dimenze: od odmítání po aktivní zájem.",
            ),
            (
                KnowledgeKind.AUDIENCE,
                "Fleet manažeři středních firem",
                "Firmy s 50 až 249 zaměstnanci, rozhodují o vozovém parku.",
            ),
            (KnowledgeKind.DATASET, "Servisní průzkum 2025", "Fiktivní datová sada, n = 1 200."),
        ],
        "pending": (
            "vnimani-znacky-2026",
            KnowledgeKind.FINDING,
            "Značka působí spolehlivě, ale konzervativně",
            "Navrženo k převzetí do znalostí klienta z běžícího výzkumu.",
        ),
    },
    "lumen-pojistovna": {
        "name": "Lumen pojišťovna (fiktivní)",
        "studies": [
            (
                "duvera-v-digitalnim-pojisteni",
                "Důvěra v digitální pojištění",
                StudyKind.RESEARCH,
                StudyStatus.ACTIVE,
            ),
            (
                "reakce-na-zmenu-pojistneho",
                "Reakce na změnu pojistného",
                StudyKind.SIMULATION,
                StudyStatus.DRAFT,
            ),
        ],
        "knowledge": [
            (
                KnowledgeKind.FACT,
                "Online kanál tvoří 38 % nových smluv",
                "Fiktivní údaj klienta za rok 2025.",
            ),
            (
                KnowledgeKind.TERM,
                "Pojistná událost",
                "Klientova definice pro komunikaci se zákazníky.",
            ),
        ],
        "pending": None,
    },
}
SEED_CURATOR_EMAIL: Final = "curator.seed@aia-develop.invalid"


@dataclass(frozen=True, slots=True)
class SeedResult:
    """Every id the seed provisioned or found."""

    organization_id: str
    owner_user_id: str
    owner_email: str
    client_id: str
    study_id: str
    project_id: str
    run_id: str
    created: dict[str, bool]
    workspaces: dict[str, str]


def _find_organization(session: Session, slug: str) -> OrganizationRow | None:
    return session.scalar(select(OrganizationRow).where(OrganizationRow.slug == slug))


def seed_develop(session: Session, *, owner_email: str) -> SeedResult:
    """Provision the develop world for ``owner_email``, or find it. Commits nothing."""
    email = owner_email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("AIA_SEED_OWNER_EMAIL must be the operator's e-mail address")

    created: dict[str, bool] = {}
    scope_repo = ScopeRepository(session)
    resolver = ScopeResolver(session)

    org_row = _find_organization(session, SEED_ORGANIZATION_SLUG)
    if org_row is None:
        org, owner = scope_repo.create_organization(
            slug=SEED_ORGANIZATION_SLUG, name="AIA develop (synthetic)", owner_email=email
        )
        organization_id, owner_id = org.organization_id, owner.user_id
        created["organization"] = True
    else:
        organization_id = org_row.organization_id
        owner_id = scope_repo.upsert_user(email=email)["user_id"]
        created["organization"] = False

    # A returning operator who is not yet a member (a fresh e-mail against an
    # existing seed) becomes its owner; an existing member keeps their role.
    # This has to happen before the context is resolved: the resolver denies a
    # non-member (`not_a_member`), which is how a changed operator e-mail made
    # every develop smoke fail with a bare "ScopeDenied: not found". The seed
    # is an operator command with the database's credentials, as the creation
    # of the organization above is; it does not widen what a request can do.
    if organization_id not in scope_repo.memberships_for_user(owner_id):
        session.add(
            OrganizationMemberRow(
                organization_id=organization_id,
                user_id=owner_id,
                role=OrganizationRole.OWNER.value,
            )
        )
        session.flush()
    admin = resolver.organization_context(
        AuthenticatedPrincipal(user_id=owner_id, organization_id=organization_id)
    )

    clients = {c.slug: c for c in scope_repo.list_clients(admin, include_archived=True)}
    client = clients.get(SEED_CLIENT_SLUG)
    if client is None:
        client = scope_repo.create_client(
            admin, slug=SEED_CLIENT_SLUG, name="Synthetic client (develop)"
        )
    created["client"] = SEED_CLIENT_SLUG not in clients

    # LEAD on the client covers every study under it, including ones seeded later.
    resolver.grant_client_access(
        admin, client_id=client.client_id, user_id=owner_id, role=ScopeRole.LEAD, reason="seed"
    )

    study_row = session.scalar(
        select(StudyRow).where(
            StudyRow.client_id == client.client_id, StudyRow.slug == SEED_STUDY_SLUG
        )
    )
    if study_row is None:
        study = scope_repo.create_study(
            admin,
            client_id=client.client_id,
            slug=SEED_STUDY_SLUG,
            name="Develop smoke study",
            budget_usd=SEED_STUDY_BUDGET_USD,
        )
        study_id = study.study_id
        created["study"] = True
    else:
        study_id = study_row.study_id
        created["study"] = False

    scope = resolver.study_context(
        AuthenticatedPrincipal(user_id=owner_id, organization_id=organization_id),
        study_id=study_id,
    )
    if scope.study_status is StudyStatus.DRAFT:
        scope_repo.set_study_status(scope, StudyStatus.ACTIVE)
        scope = resolver.study_context(
            AuthenticatedPrincipal(user_id=owner_id, organization_id=organization_id),
            study_id=study_id,
        )

    projects = ProjectRepository(session, scope)
    page = projects.list_projects(search=SEED_PROJECT_TITLE, limit=200)
    match = next((p for p in page.items if p.title == SEED_PROJECT_TITLE), None)
    if match is None:
        project, _ = projects.create(
            title=SEED_PROJECT_TITLE,
            content=dict(SEED_PROJECT_CONTENT),
            created_by=owner_id,
        )
        project_id = project.project_id
        created["project"] = True
    else:
        project_id = match.project_id
        created["project"] = False

    started: StartedRun = start_workflow(
        session, scope, project_id=project_id, workflow_type=DEVELOP_SNAPSHOT
    )
    created["run"] = started.created

    workspaces, created["workspaces"] = _seed_workspaces(
        session,
        scope_repo,
        resolver,
        admin=admin,
        owner_id=owner_id,
        organization_id=organization_id,
    )

    return SeedResult(
        organization_id=organization_id,
        owner_user_id=owner_id,
        owner_email=email,
        client_id=client.client_id,
        study_id=study_id,
        project_id=project_id,
        run_id=started.run_id,
        created=created,
        workspaces=workspaces,
    )


def _seed_workspaces(
    session: Session,
    scope_repo: ScopeRepository,
    resolver: ScopeResolver,
    *,
    admin: Any,
    owner_id: str,
    organization_id: str,
) -> tuple[dict[str, str], bool]:
    """The fictional clients of SEED_WORKSPACES, found by slug or created; idempotent.

    Knowledge goes the governed way: the operator proposes, a synthetic curator
    (a REVIEWER on the client) approves, so every item has a revision and
    provenance like any other. Returns slug -> client id, and whether anything
    was new. A client a person has archived is left as they left it: nothing is
    granted or seeded into it.
    """
    knowledge = ClientKnowledgeRepository(session)
    owner = AuthenticatedPrincipal(user_id=owner_id, organization_id=organization_id)
    members = {m["email"]: m for m in scope_repo.members(admin)}
    curator_id = (
        members[SEED_CURATOR_EMAIL]["user_id"]
        if SEED_CURATOR_EMAIL in members
        else scope_repo.add_member(
            admin, email=SEED_CURATOR_EMAIL, display_name="Kurátor (seed)"
        ).user_id
    )
    curator = AuthenticatedPrincipal(user_id=curator_id, organization_id=organization_id)
    existing = {c.slug: c for c in scope_repo.list_clients(admin, include_archived=True)}
    out: dict[str, str] = {}
    fresh = False
    for slug, spec in SEED_WORKSPACES.items():
        client = existing.get(slug)
        if client is None:
            client = scope_repo.create_client(admin, slug=slug, name=spec["name"])
            fresh = True
        out[slug] = client.client_id
        if client.status is ClientStatus.ARCHIVED:
            # Archiving a showcase client is a person's decision (Settings, PUT
            # /clients/{id}/status). The resolver refuses an archived client, so
            # seeding into it failed every later deploy (OI-80, deploy run 40);
            # leaving it alone is the seed respecting that decision, not undoing it.
            continue
        resolver.grant_client_access(
            admin, client_id=client.client_id, user_id=owner_id, role=ScopeRole.LEAD, reason="seed"
        )
        resolver.grant_client_access(
            admin,
            client_id=client.client_id,
            user_id=curator_id,
            role=ScopeRole.REVIEWER,
            reason="seed",
        )
        ctx = resolver.client_context(owner, client_id=client.client_id)
        studies = {s.slug: s for s in scope_repo.studies_in_client(ctx)}
        for study_slug, name, kind, status in spec["studies"]:
            if study_slug in studies:
                continue
            study = scope_repo.create_study_in_client(ctx, slug=study_slug, name=name, kind=kind)
            studies[study_slug] = study
            fresh = True
            if status is not StudyStatus.DRAFT:
                study_scope = resolver.study_context(owner, study_id=study.study_id)
                scope_repo.set_study_status(study_scope, status)

        ctx = resolver.client_context(owner, client_id=client.client_id)
        have = {i.title for i in knowledge.items(ctx)}
        proposed = {p.title for p in knowledge.proposals(ctx)}
        delivered = studies.get("spokojenost-servisu-2025")
        for kind, title, summary in spec["knowledge"]:
            if title in have or title in proposed:
                continue
            provenance: dict[str, Any] = {"seed": True}
            if kind is KnowledgeKind.FINDING and delivered is not None:
                provenance["study_id"] = delivered.study_id
            p = knowledge.propose(
                ctx, kind=kind, title=title, summary=summary, provenance=provenance
            )
            knowledge.decide(
                resolver.client_context(curator, client_id=client.client_id),
                proposal_id=p.proposal_id,
                approve=True,
                note="seed",
            )
            fresh = True
        pending = spec["pending"]
        if pending is not None and pending[2] not in proposed:
            study_scope = resolver.study_context(owner, study_id=studies[pending[0]].study_id)
            knowledge.propose_from_study(
                study_scope,
                kind=pending[1],
                title=pending[2],
                summary=pending[3],
                provenance={"seed": True},
            )
            fresh = True
    return out, fresh


def seeded_study_scope(session: Session, *, owner_email: str) -> StudyContext:
    """The seeded operator's context on the seeded study, issued by the resolver.

    For the smoke command, which acts as the operator would through the API.
    Raises :class:`LookupError` when the seed has not run.
    """
    org_row = _find_organization(session, SEED_ORGANIZATION_SLUG)
    if org_row is None:
        raise LookupError("the develop seed has not run; nothing to act on")
    scope_repo = ScopeRepository(session)
    user = scope_repo.upsert_user(email=owner_email.strip().lower())
    resolver = ScopeResolver(session)
    study_row = session.scalar(
        select(StudyRow).where(
            StudyRow.organization_id == org_row.organization_id,
            StudyRow.slug == SEED_STUDY_SLUG,
        )
    )
    if study_row is None:
        raise LookupError("the seeded study is missing; re-run the seed")
    return resolver.study_context(
        AuthenticatedPrincipal(user_id=user["user_id"], organization_id=org_row.organization_id),
        study_id=study_row.study_id,
    )


def reset_develop_seed(session: Session) -> bool:
    """Delete the seeded organization and everything under it. Commits nothing.

    Returns True when something was removed. Only the seed's own slug is ever
    deleted; the function has no parameter for any other.
    """
    org_row = _find_organization(session, SEED_ORGANIZATION_SLUG)
    if org_row is None:
        return False
    session.delete(org_row)
    session.flush()
    return True
