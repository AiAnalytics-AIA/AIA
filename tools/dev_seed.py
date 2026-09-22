"""Provision a small development world so the web client can run on the real API.

    make services && make migrate && make dev-seed

The migrations need PostgreSQL (several use ALTER of constraints, which SQLite
lacks). Run it once against an empty database: organization slugs are unique, so
a second run fails rather than duplicating the world.

This is a **development fixture**, not a migration and not a back door. It goes
through the same repositories and the same :class:`ScopeResolver` that production
provisioning uses -- the CI startup smoke test does the same thing inline -- so
every row it writes is one the API would accept. It refuses to run outside a
local or test environment.

What it creates, and why each piece is there:

* organization ``aia`` with owner ``lead@aia.dev`` (the default development
  subject in ``apps/web``);
* two clients, each with one study and a budget, so the portfolio has more than
  one row and the scope chrome has two accents to tell apart;
* a LEAD grant on the first client and a VIEWER grant on the second, so the slice
  shows a budget the viewer may see beside one it may not;
* one research project and one simulation project, created through
  :class:`ProjectRepository` -- their stages are whatever the domain initialises,
  never a hand-set status.

Nothing here invents run state. A stage is NOT_STARTED until a workflow runs it.
"""

from __future__ import annotations

import json
import os
import sys

from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.project import ProjectType
from aia_core.domain.scope import ScopeRole
from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.scope_repository import ScopeRepository

ALLOWED_ENVS = {"local", "test"}
OWNER = "lead@aia.dev"


def main() -> int:
    env = os.environ.get("AIA_ENV", "local").lower()
    if env not in ALLOWED_ENVS:
        print(f"dev_seed refuses to run with AIA_ENV={env!r}", file=sys.stderr)
        return 2
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2

    engine = create_app_engine(url)
    with create_session_factory(engine)() as s:
        repo, resolver = ScopeRepository(s), ScopeResolver(s)
        org, owner = repo.create_organization(
            slug="aia", name="AIA (development)", owner_email=OWNER, owner_name="Dev Lead"
        )
        principal = AuthenticatedPrincipal(
            user_id=owner.user_id, organization_id=org.organization_id
        )
        admin = resolver.organization_context(principal)

        first = repo.create_client(admin, slug="dev-horizont", name="Dev Banka Horizont")
        second = repo.create_client(admin, slug="dev-morava", name="Dev Energie Morava")
        study_a = repo.create_study(
            admin,
            client_id=first.client_id,
            slug="dev-retail",
            name="Dev Retail segmentation",
            budget_usd=250.0,
        )
        study_b = repo.create_study(
            admin,
            client_id=second.client_id,
            slug="dev-tariff",
            name="Dev Tariff simulation",
            budget_usd=120.0,
        )
        resolver.grant_client_access(
            admin,
            client_id=first.client_id,
            user_id=owner.user_id,
            role=ScopeRole.LEAD,
            reason="development seed",
        )
        resolver.grant_client_access(
            admin,
            client_id=second.client_id,
            user_id=owner.user_id,
            role=ScopeRole.VIEWER,
            reason="development seed",
        )

        research = ProjectRepository(
            s, resolver.study_context(principal, study_id=study_a.study_id)
        )
        research.create(
            title="Dev research project",
            project_type=ProjectType.RESEARCH,
            content={"goal": "development seed"},
            created_by=owner.user_id,
        )
        research.create(
            title="Dev simulation project",
            project_type=ProjectType.SIMULATION,
            content={"goal": "development seed"},
            created_by=owner.user_id,
        )
        s.commit()

        print(
            json.dumps(
                {
                    "organization": org.slug,
                    "subject": OWNER,
                    "studies": [study_a.study_id, study_b.study_id],
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
