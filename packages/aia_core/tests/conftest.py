"""Test fixtures, including access to the legacy prototype for parity testing.

The legacy NPC Panel prototype is deliberately *not* vendored into this
repository. Parity tests import it from the path in ``AIA_LEGACY_REFERENCE`` and
skip cleanly when it is absent, so a normal clone and CI run stay green while a
migration engineer with the reference checkout gets the extra verification.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

_DEFAULT_REFERENCE_PATHS = (
    Path(__file__).resolve().parents[4] / "npc-panel-reference",
    Path.home() / "Downloads" / "AIA" / "npc-panel-reference",
)


def _legacy_root() -> Path | None:
    """Return the legacy prototype root, or None when it is unavailable."""
    configured = os.environ.get("AIA_LEGACY_REFERENCE")
    candidates = [Path(configured)] if configured else list(_DEFAULT_REFERENCE_PATHS)
    for candidate in candidates:
        if (candidate / "project_pipeline.py").is_file():
            return candidate
    return None


@pytest.fixture(scope="session")
def legacy_root() -> Path:
    """Return the legacy prototype root, skipping when it is unavailable."""
    root = _legacy_root()
    if root is None:
        pytest.skip(
            "legacy prototype not available; set AIA_LEGACY_REFERENCE to the "
            "npc-panel-reference checkout to enable parity tests"
        )
    return root


@pytest.fixture(scope="session")
def legacy_pipeline() -> Iterator[Any]:
    """Import the legacy ``project_pipeline`` module for parity comparison."""
    root = _legacy_root()
    if root is None:
        pytest.skip(
            "legacy prototype not available; set AIA_LEGACY_REFERENCE to the "
            "npc-panel-reference checkout to enable parity tests"
        )
    sys.path.insert(0, str(root))
    try:
        import project_pipeline

        yield project_pipeline
    finally:
        sys.path.remove(str(root))


@pytest.fixture(scope="session")
def legacy_provider_runtime() -> Iterator[Any]:
    """Import the legacy ``provider_runtime`` module for parity comparison."""
    root = _legacy_root()
    if root is None:
        pytest.skip("legacy prototype not available; set AIA_LEGACY_REFERENCE")
    sys.path.insert(0, str(root))
    try:
        import provider_runtime

        yield provider_runtime
    finally:
        sys.path.remove(str(root))


@pytest.fixture
def research_project() -> dict[str, Any]:
    """A representative research project payload touching every stage's inputs."""
    return {
        "schema_version": 2,
        "title": "Test výzkum",
        "goal": "Zjistit postoj k nové nabídce",
        "decision_use": "Rozhodnutí o spuštění produktu",
        "briefing": "Klient zvažuje vstup na trh.",
        "study_type": "brand_positioning",
        "research_plan": {"research_questions": ["Jaký je zájem?", "Kdo je cílová skupina?"]},
        "tracked_objects": ["Značka A", "Značka B", "Značka C"],
        "sections": [{"id": "s1", "questions": [{"id": "q1", "text": "Znáte značku A?"}]}],
        "instrument_library": {"version": "17.1.2-instruments-v1.1"},
        "questionnaire_policy": {"max_questions": 25},
        "audience": {"mode": "population", "filters": {"vek": {"min": 18, "max": 65}}},
        "persona_mode": "calibrated",
        "persona_dimensions": ["hodnoty", "media", "nakupni_chovani"],
        "n": 300,
        "panel_mode": "STATIC",
        "model": "sonnet",
        "population_snapshot": {"panel_version": "v17_4_0"},
        "aggregation_policy": {"weighting": "vaha_strukturalni_2025"},
        "weighting": "vaha_strukturalni_2025",
        "validation_policy": {"require_benchmarks": True},
        "benchmarks": {"source": "CENSUS_2021"},
        "analysis_instructions": "Zaměřit se na segmenty.",
        "analysis_style": "consulting",
        "report_style": "client",
        "report_branding": {"logo": "brand/logo.png"},
        "report_language": "cs",
        "delivery": {"format": "docx"},
        "attachment_refs": ["ATT-1"],
        "data_context": {"has_client_data": False},
        "provider": "claude_code_subscription",
        "preferred_provider": "claude_code_subscription",
        "provider_policy": "CLAUDE_CODE_ONLY",
    }


@pytest.fixture
def simulation_project() -> dict[str, Any]:
    """A representative simulation project payload."""
    return {
        "schema_version": "simulation-project-v1",
        "title": "Test simulace",
        "goal": "Odhadnout dopad cenové změny",
        "scenario_contract": {"change": "cena -10 %", "horizon": "12m"},
        "analysis_instructions": "Porovnat varianty.",
        "report_style": "client",
        "report_branding": {"logo": "brand/logo.png"},
        "delivery": {"format": "docx"},
        "attachment_refs": [],
        "data_context": {},
        "simulation": {
            "context": "Trh reaguje na cenové změny se zpožděním.",
            "brief": "Cenová elasticita",
            "baseline": {"share": 0.21},
            "audience": {"mode": "population"},
            "dimensions": ["cenova_citlivost"],
            "change": "cena -10 %",
            "variants": [{"id": "v1", "change": "-5 %"}, {"id": "v2", "change": "-10 %"}],
            "worlds": [{"id": "w1", "seed": 1}, {"id": "w2", "seed": 2}],
            "n": 500,
            "model": "sonnet",
            "comparison_policy": {"primary_output": "delta"},
            "population_snapshot": {"panel_version": "v17_4_0"},
        },
    }


# --------------------------------------------------------------------------- #
# Scope helpers
#
# Every repository that touches client data needs a StudyContext, and only the
# authorization layer can issue one. These helpers build a real organization /
# client / study / grant graph so tests exercise the same authorisation path
# production does, rather than a stub that would hide a scoping bug.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ScopeFixture:
    """A fully provisioned scope for tests."""

    organization_id: str
    admin_context: Any
    admin_principal: Any
    owner_id: str
    clients: dict[str, Any]
    studies: dict[str, Any]
    users: dict[str, str]
    resolver: Any
    scope_repo: Any

    def principal(self, user_id: str, *, request_id: str = "req-test") -> Any:
        """Build an authenticated principal for a provisioned user."""
        from aia_core.application.scope import AuthenticatedPrincipal

        return AuthenticatedPrincipal(
            user_id=user_id, organization_id=self.organization_id, request_id=request_id
        )

    def scope(self, *, user: str = "lead", study: str = "primary") -> Any:
        """Resolve a StudyContext for a provisioned user and study."""
        return self.resolver.study_context(
            self.principal(self.users[user]), study_id=self.studies[study].study_id
        )


def build_scope_fixture(session: Any) -> ScopeFixture:
    """Provision a two-client, two-study world with users at every role.

    Two clients are created deliberately: the interesting isolation tests are the
    ones that cross a client boundary, and a single-client fixture cannot express
    them.
    """
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.domain.scope import ScopeRole
    from aia_core.infrastructure.scope_repository import ScopeRepository

    scope_repo = ScopeRepository(session)
    resolver = ScopeResolver(session)

    org, owner = scope_repo.create_organization(
        slug="aia",
        name="AI Analytics",
        owner_email="owner@art-chain.io",
        owner_name="Owner",
    )
    admin_principal = AuthenticatedPrincipal(
        user_id=owner.user_id, organization_id=org.organization_id, request_id="req-setup"
    )
    admin = resolver.organization_context(admin_principal)

    primary_client = scope_repo.create_client(admin, slug="acme", name="Acme Corp")
    other_client = scope_repo.create_client(admin, slug="globex", name="Globex Inc")

    studies = {
        "primary": scope_repo.create_study(
            admin,
            client_id=primary_client.client_id,
            slug="brand-2026",
            name="Acme brand",
            budget_usd=500.0,
        ),
        "sibling": scope_repo.create_study(
            admin,
            client_id=primary_client.client_id,
            slug="pricing-2026",
            name="Acme pricing",
            budget_usd=200.0,
        ),
        "other_client": scope_repo.create_study(
            admin,
            client_id=other_client.client_id,
            slug="brand-2026",
            name="Globex brand",
            budget_usd=300.0,
        ),
    }

    users: dict[str, str] = {"owner": owner.user_id}
    for label, role in (
        ("lead", ScopeRole.LEAD),
        ("researcher", ScopeRole.RESEARCHER),
        ("reviewer", ScopeRole.REVIEWER),
        ("viewer", ScopeRole.VIEWER),
    ):
        member = scope_repo.add_member(admin, email=f"{label}@art-chain.io")
        users[label] = member.user_id
        resolver.grant_client_access(
            admin, client_id=primary_client.client_id, user_id=member.user_id, role=role
        )

    # A lead on the other client, so cross-client tests have a real counterpart
    # rather than an unauthorised one.
    other_lead = scope_repo.add_member(admin, email="other-lead@art-chain.io")
    users["other_lead"] = other_lead.user_id
    resolver.grant_client_access(
        admin,
        client_id=other_client.client_id,
        user_id=other_lead.user_id,
        role=ScopeRole.LEAD,
    )

    # Someone in the organization with no client grant at all.
    outsider = scope_repo.add_member(admin, email="outsider@art-chain.io")
    users["outsider"] = outsider.user_id

    session.flush()
    return ScopeFixture(
        organization_id=org.organization_id,
        admin_context=admin,
        admin_principal=admin_principal,
        owner_id=owner.user_id,
        clients={"primary": primary_client, "other": other_client},
        studies=studies,
        users=users,
        resolver=resolver,
        scope_repo=scope_repo,
    )


@pytest.fixture(scope="session")
def engine() -> Iterator[Any]:
    """A real database engine: PostgreSQL when DATABASE_URL is set, else SQLite.

    Session-scoped so the schema is built once. CI runs the whole suite twice,
    against PostgreSQL and against SQLite, because the two disagree about things
    that matter -- JSONB, timezone-aware timestamps and cascade deletes.
    """
    from aia_core.infrastructure.db import create_app_engine
    from aia_core.infrastructure.tables import Base

    eng = create_app_engine(os.environ.get("DATABASE_URL"))
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def session(engine: Any) -> Iterator[Any]:
    """A session whose tables are emptied afterwards, so tests stay independent."""
    from aia_core.infrastructure.db import create_session_factory
    from aia_core.infrastructure.tables import Base

    factory = create_session_factory(engine)
    with factory() as s:
        yield s
        s.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            s.execute(table.delete())
        s.commit()


@pytest.fixture
def scoped(session: Any) -> ScopeFixture:
    """A provisioned organization / client / study world with users at every role."""
    return build_scope_fixture(session)
