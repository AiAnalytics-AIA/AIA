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


_DEFAULT_REFERENCE_REPO_PATHS = (
    Path(__file__).resolve().parents[4] / "aia-reference",
    Path(__file__).resolve().parents[4] / "AIA-reference",
)


def _reference_repo() -> Path | None:
    """Return the AIA-reference checkout, or None when it is unavailable.

    Distinct from the legacy prototype: this is ``AiAnalytics-AIA/AIA-reference``,
    the private repository holding the contracts and golden fixtures -- no archive
    and no licensed data. Identified by its golden-fixture manifest.
    """
    configured = os.environ.get("AIA_REFERENCE_REPO")
    candidates = [Path(configured)] if configured else list(_DEFAULT_REFERENCE_REPO_PATHS)
    for candidate in candidates:
        if (candidate / "golden-fixtures" / "manifest.json").is_file() and (
            candidate / "field-policy.json"
        ).is_file():
            return candidate
    return None


@pytest.fixture(scope="session")
def reference_repo() -> Path:
    """Return the AIA-reference checkout, skipping when it is unavailable."""
    root = _reference_repo()
    if root is None:
        pytest.skip(
            "AIA-reference not available; set AIA_REFERENCE_REPO to a checkout of "
            "AiAnalytics-AIA/AIA-reference to enable population and evidence parity tests"
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


@pytest.fixture
def scope_builder() -> Any:
    """Return :func:`build_scope_fixture` for tests managing their own sessions.

    Exposed as a fixture rather than imported because both test directories in
    this repository are named ``tests``, so they cannot be packages and relative
    imports between their modules collide.
    """
    return build_scope_fixture


# --- Evidence governance ------------------------------------------------------
#
# The real field dictionary is reference material and is not vendored (see
# .planning/plans/done/evidence-governance-foundation.md). Unit tests use this small
# synthetic dictionary, one row per policy shape the gates must distinguish. The
# parity suite reads the real export from the private reference repository
# through the shared ``reference_repo`` fixture above.

SYNTHETIC_DICTIONARY_SHA256 = "0" * 63 + "1"

SYNTHETIC_DICTIONARY_ROWS: tuple[dict[str, str], ...] = (
    {
        "field": "vek",
        "block": "population_anchor",
        "source": "Census 2021",
        "evidence_status": "POPULATION_ANCHOR",
        "production_grade": "A",
        "recommended_use": "PERSONA_OR_ANALYSIS_WITH_SCOPE",
        "persona_eligible": "yes",
    },
    {
        "field": "vzdelani",
        "block": "core",
        "source": "matching/core",
        "evidence_status": "CANONICAL_CORE",
        "production_grade": "A",
        "recommended_use": "PERSONA_OR_ANALYSIS_WITH_SCOPE",
        "persona_eligible": "yes",
    },
    {
        "field": "numeracy_score",
        "block": "piaac_core",
        "source": "PIAAC",
        "evidence_status": "MEASURED_CORE_PIAAC",
        "production_grade": "B",
        "recommended_use": "PERSONA_OR_ANALYSIS_WITH_SCOPE",
        "persona_eligible": "yes",
    },
    {
        "field": "wellbeing_index",
        "block": "mental_health",
        "source": "donor",
        "evidence_status": "MATCHED_WHOLE_BLOCK",
        "production_grade": "B",
        "recommended_use": "PERSONA_OR_ANALYSIS_WITH_SCOPE",
        "persona_eligible": "yes",
    },
    {
        "field": "trust_courts",
        "block": "rule_of_law",
        "source": "donor",
        "evidence_status": "MATCHED_WHOLE_BLOCK",
        "production_grade": "B",
        "recommended_use": "PERSONA_OR_ANALYSIS_WITH_SCOPE",
        "persona_eligible": "yes",
    },
    {
        "field": "vote_2021",
        "block": "politics",
        "source": "donor",
        "evidence_status": "MATCHED_POLITICS_CANONICAL",
        "production_grade": "C",
        "recommended_use": "HISTORICAL_OR_EXPLORATORY",
        "persona_eligible": "yes",
    },
    {
        "field": "religious_affiliation",
        "block": "RELIGION",
        "source": "donor",
        "evidence_status": "MATCHED_WHOLE_BLOCK_CANONICAL",
        "production_grade": "B",
        "recommended_use": "persona/context with provenance",
        "persona_eligible": "yes",
    },
    {
        "field": "deal_seeking_1_10",
        "block": "marketing_behavior",
        "source": "latent",
        "evidence_status": "MODELED_MARKETING_PRIOR",
        "production_grade": "D",
        "recommended_use": "behavioral prior / simulation modifier, never measured fact",
        "persona_eligible": "yes",
    },
    {
        "field": "value_security",
        "block": "VALUES",
        "source": "proxy",
        "evidence_status": "MODELED_VALUE_PROXY",
        "production_grade": "C",
        "recommended_use": "simulation prior; never claim direct Schwartz measurement",
        "persona_eligible": "yes",
    },
    {
        "field": "has_savings",
        "block": "FINANCIAL_CAPABILITY",
        "source": "calibrated",
        "evidence_status": "CALIBRATED_MODELED_BINARY",
        "production_grade": "C",
        "recommended_use": "segmentation/aggregate; individual value modeled",
        "persona_eligible": "yes",
    },
    {
        "field": "tv_daily_minutes",
        "block": "media",
        "source": "benchmark",
        "evidence_status": "CALIBRATED_BENCHMARK",
        "production_grade": "B",
        "recommended_use": (
            "aggregate planning and persona background with modeled-value disclosure"
        ),
        "persona_eligible": "yes",
    },
    {
        "field": "life_stage",
        "block": "derived",
        "source": "derived",
        "evidence_status": "DERIVED_TRANSPARENT",
        "production_grade": "B",
        "recommended_use": "PERSONA_OR_ANALYSIS_WITH_SCOPE",
        "persona_eligible": "yes",
    },
    {
        "field": "is_procurement_buyer_current",
        "block": "SPECIAL_PANEL_FLAG",
        "source": "derived",
        "evidence_status": "DERIVED_TRANSPARENT",
        "production_grade": "C",
        "recommended_use": "audience selection; use vaha_strukturalni_2025",
        "persona_eligible": "yes",
    },
    {
        "field": "panel_row_id",
        "block": "provenance",
        "source": "matching/core",
        "evidence_status": "POPULATION_ANCHOR",
        "production_grade": "T",
        "recommended_use": "AUDIT_ONLY",
        "persona_eligible": "no",
    },
    {
        "field": "vaha_strukturalni_2025",
        "block": "weight",
        "source": "raking",
        "evidence_status": "NEW_WEIGHT",
        "production_grade": "T",
        "recommended_use": "AUDIT_ONLY",
        "persona_eligible": "no",
    },
    {
        "field": "donor_id_mental_health",
        "block": "provenance",
        "source": "matching",
        "evidence_status": "PROVENANCE_OR_CORE",
        "production_grade": "T",
        "recommended_use": "technical/provenance only",
        "persona_eligible": "no",
    },
)

SYNTHETIC_RUNTIME_ONLY_COLUMNS = ("life_stage_derived", "_analysis_weight")


@pytest.fixture
def dictionary_rows() -> list[dict[str, str]]:
    return [dict(row, description=f"synthetic {row['field']}") for row in SYNTHETIC_DICTIONARY_ROWS]


@pytest.fixture
def field_book(dictionary_rows: list[dict[str, str]]) -> Any:
    from aia_core.domain.evidence import FieldPolicyBook

    return FieldPolicyBook.from_dictionary_rows(
        dictionary_rows,
        source_sha256=SYNTHETIC_DICTIONARY_SHA256,
        runtime_columns=[r["field"] for r in dictionary_rows]
        + list(SYNTHETIC_RUNTIME_ONLY_COLUMNS),
    )


SYNTHETIC_PANEL_SHA256 = "b" * 64

# Shaped like the reference certificate (population-subsystem.md §10), with a
# synthetic panel name and hash.
SYNTHETIC_JOINT_CERTIFICATE: dict[str, Any] = {
    "production_panel": "synthetic_panel.csv.gz",
    "panel_sha256": SYNTHETIC_PANEL_SHA256,
    "structure_status": "QC_PASSED",
    "prediction_validation_status": "EXTERNAL_HOLDOUT_PENDING",
    "matched_blocks": [
        "mental_health",
        "social_network",
        "institutions",
        "rule_of_law",
        "politics",
        "family_health",
    ],
    "core_same_person_joint": True,
    "cross_block_same_person_joint": False,
    "client_joint_outputs_allowed": False,
    "descriptive_core_outputs_allowed": True,
    "matched_block_outputs_allowed": True,
    "cross_block_joint_claims_allowed": False,
    "runtime_identity_contract": (
        "single authoritative core; specialist donor demographics and party identity are audit-only"
    ),
}


@pytest.fixture
def certificate_bytes() -> Any:
    """Build certificate bytes from the synthetic certificate plus overrides."""
    import json

    def build(**overrides: Any) -> bytes:
        return json.dumps({**SYNTHETIC_JOINT_CERTIFICATE, **overrides}).encode("utf-8")

    return build


@pytest.fixture
def joint_status(certificate_bytes: Any) -> Any:
    """The certified status: the synthetic certificate bound to the synthetic panel."""
    from aia_core.domain.evidence import load_joint_status

    return load_joint_status(certificate_bytes(), measured_panel_sha256=SYNTHETIC_PANEL_SHA256)


@pytest.fixture
def degraded_joint_status() -> Any:
    from aia_core.domain.evidence import load_joint_status

    return load_joint_status(None, measured_panel_sha256=SYNTHETIC_PANEL_SHA256)


@pytest.fixture
def evidence_row() -> Any:
    """Build an EvidenceRow with sensible, fully supported defaults plus overrides."""
    from aia_core.domain.evidence import (
        ClaimBasis,
        ClaimLevel,
        Disclosure,
        EvidenceRow,
        Interval,
        SupportEvidence,
        assess_support,
        parse_metric,
    )

    def build(ref: str = "E1", **overrides: Any) -> Any:
        metric = overrides.pop("metric", "top2box_pct")
        args: dict[str, Any] = {
            "evidence_ref": ref,
            "metric": parse_metric(metric) if isinstance(metric, str) else metric,
            "value": 42.5,
            "decimals": 1,
            "support": assess_support(SupportEvidence(n=600, effective_n=480.0)),
            "fields": ("vek",),
            "basis": ClaimBasis.MEASURED,
            "level": ClaimLevel.AGGREGATE,
            "cell": "total",
            "question_id": "q1",
            "interval": Interval(38.1, 46.9, 0.95),
            "disclosures": frozenset({Disclosure.SCOPE}),
        }
        args.update(overrides)
        return EvidenceRow(**args)

    return build


# --------------------------------------------------------------------------- #
# Sociomapping golden fixtures
#
# F1-F9 are synthetic fixtures captured by executing the reference, vendored from
# AiAnalytics-AIA/AIA-reference (see fixtures/sociomap/index.json). Unlike the
# legacy prototype they ARE in this repository, so the tests that use them run in
# every CI job rather than skipping.
# --------------------------------------------------------------------------- #

SOCIOMAP_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sociomap"


@pytest.fixture(scope="session")
def sociomap_fixture() -> Any:
    """Return a loader: ``sociomap_fixture("F1")`` -> the parsed fixture document."""
    import json

    index = json.loads((SOCIOMAP_FIXTURES / "index.json").read_text(encoding="utf-8"))
    by_prefix = {fid.split("_", 1)[0]: entry for fid, entry in index["fixtures"].items()}

    def load(fixture: str) -> dict[str, Any]:
        entry = by_prefix[fixture]
        document: dict[str, Any] = json.loads(
            (SOCIOMAP_FIXTURES / entry["file"]).read_text(encoding="utf-8")
        )
        return document

    return load


# --------------------------------------------------------------------------- #
# Synthetic population bundles
#
# The real panels are licensed-derived data withheld from every repository, so
# population tests run on a small synthetic dataset built here, through exactly the
# code paths the real import uses: gzip-compressed UTF-8 CSV, a field dictionary,
# and a contract pinning both by hash. Three versions with the preserved lineage
# shape -- root, static reference, live -- differing in bytes but not in weights.
# --------------------------------------------------------------------------- #


@dataclass
class SyntheticPopulation:
    """A contract, an in-memory asset source and the bytes of three versions."""

    contract: Any
    source: Any
    fields: tuple[str, ...]
    rows: dict[str, list[dict[str, str]]]
    dictionary_location: str = "dictionary.csv"

    def location(self, label: str) -> str:
        return f"panels/{label}.csv.gz"

    def panel_bytes(self, label: str) -> bytes:
        return bytes(self.source.read(self.location(label)))

    def rebuild(self, label: str, mutate: Any) -> bytes:
        """Return ``label``'s bytes rebuilt with ``mutate`` applied to a copy of its rows."""
        rows = [dict(r) for r in self.rows[label]]
        mutate(rows)
        return gzip_csv(self.fields, rows)


SYNTHETIC_FIELDS = ("row_id", "vek", "occupation_code", "segment", "w_main", "w_alt")
SYNTHETIC_ENRICHMENT = ("life_stage_derived", "dominant_media_derived")


def synthetic_rows(segment_suffix: str) -> list[dict[str, str]]:
    """Six respondents. Leading-zero occupation codes, a quoted comma, Czech text."""
    return [
        {
            "row_id": "R1",
            "vek": "34",
            "occupation_code": "0110",
            "segment": f"a{segment_suffix}",
            "w_main": "1.5",
            "w_alt": "2",
        },
        {
            "row_id": "R2",
            "vek": "71",
            "occupation_code": "0310",
            "segment": f"b{segment_suffix}",
            "w_main": "0.5",
            "w_alt": "1",
        },
        {
            "row_id": "R3",
            "vek": "",
            "occupation_code": "2512",
            "segment": "Praha, střed",
            "w_main": "2.0",
            "w_alt": "1",
        },
        {
            "row_id": "R4",
            "vek": "18",
            "occupation_code": "0010",
            "segment": "NA",
            "w_main": "1.0",
            "w_alt": "3",
        },
        {
            "row_id": "R5",
            "vek": "45",
            "occupation_code": "9629",
            "segment": "",
            "w_main": "3.25",
            "w_alt": "1",
        },
        {
            "row_id": "R6",
            "vek": "100",
            "occupation_code": "0000",
            "segment": "x",
            "w_main": "0.75",
            "w_alt": "2",
        },
    ]


# One policy row per synthetic field: (block, evidence_status, grade, recommended_use,
# persona_eligible). Chosen to cover the interesting policy categories.
SYNTHETIC_POLICY: dict[str, tuple[str, str, str, str, str]] = {
    "row_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
    "vek": ("population_anchor", "POPULATION_ANCHOR", "A", "PERSONA_OR_ANALYSIS_WITH_SCOPE", "yes"),
    "occupation_code": ("core", "CANONICAL_CORE", "C", "HISTORICAL_OR_EXPLORATORY", "yes"),
    "segment": (
        "marketing_behavior",
        "MODELED_MARKETING_PRIOR",
        "B",
        "behavioral prior / simulation modifier, never measured fact",
        "yes",
    ),
    "w_main": ("weight", "NEW_WEIGHT", "T", "AUDIT_ONLY", "no"),
    "w_alt": ("weight", "NEW_WEIGHT", "T", "AUDIT_ONLY", "no"),
}

DEFAULT_POLICY_ROW = ("core", "POPULATION_ANCHOR", "A", "PERSONA_OR_ANALYSIS_WITH_SCOPE", "yes")


def policy_dictionary_csv(
    fields: tuple[str, ...], policy: dict[str, tuple[str, str, str, str, str]] | None = None
) -> bytes:
    """A field dictionary in the reference's column layout, with a policy row per field."""
    import csv
    import io

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "field",
            "block",
            "source",
            "evidence_status",
            "production_grade",
            "recommended_use",
            "description",
            "persona_eligible",
        ]
    )
    for name in fields:
        block, status, grade, use, persona = (policy or {}).get(name, DEFAULT_POLICY_ROW)
        writer.writerow(
            [name, block, "synthetic", status, grade, use, f"{name} (synthetic)", persona]
        )
    return buffer.getvalue().encode("utf-8")


@pytest.fixture
def policy_dictionary() -> Any:
    """Return :func:`policy_dictionary_csv` for tests that build their own dictionaries."""
    return policy_dictionary_csv


def gzip_csv(fields: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    """Deterministic gzip CSV (mtime=0), so a version's hash is stable."""
    import csv
    import gzip
    import io

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(fields)
    for row in rows:
        writer.writerow([row.get(f, "") for f in fields])
    return gzip.compress(buffer.getvalue().encode("utf-8"), mtime=0)


def build_synthetic_population() -> SyntheticPopulation:
    from aia_core.domain.population import (
        KnownVersion,
        PopulationImportContract,
        WeightScheme,
        content_sha256,
        field_names_fingerprint,
    )
    from aia_core.infrastructure.population_source import InMemoryPopulationSource

    rows = {
        "v1_BASE": synthetic_rows("0"),
        "v1_1": synthetic_rows("1"),
        "v1_4": synthetic_rows("4"),
    }
    panels = {label: gzip_csv(SYNTHETIC_FIELDS, r) for label, r in rows.items()}
    dictionary_bytes = policy_dictionary_csv(SYNTHETIC_FIELDS, SYNTHETIC_POLICY)

    contract = PopulationImportContract(
        contract_id="synthetic_population/v1",
        dataset_id="synthetic_population",
        field_count=len(SYNTHETIC_FIELDS),
        field_names_sha256=field_names_fingerprint(SYNTHETIC_FIELDS),
        dictionary_sha256=content_sha256(dictionary_bytes),
        primary_key="row_id",
        expected_rows=6,
        weight_schemes=(
            WeightScheme("main", "w_main", expected_total=9.0, tolerance=1e-9),
            WeightScheme("alt", "w_alt", expected_total=10.0, tolerance=1e-9),
        ),
        default_weight_role="main",
        known_versions=(
            KnownVersion("v1_BASE", content_sha256(panels["v1_BASE"]), len(panels["v1_BASE"])),
            KnownVersion("v1_1", content_sha256(panels["v1_1"]), len(panels["v1_1"]), "v1_BASE"),
            KnownVersion("v1_4", content_sha256(panels["v1_4"]), len(panels["v1_4"]), "v1_1"),
        ),
        static_reference_label="v1_1",
        enrichment_fields=SYNTHETIC_ENRICHMENT,
        text_fields=frozenset({"occupation_code"}),
        forbidden_prefixes=("D_", "P_"),
    )
    source = InMemoryPopulationSource({"dictionary.csv": dictionary_bytes})
    population = SyntheticPopulation(
        contract=contract, source=source, fields=SYNTHETIC_FIELDS, rows=rows
    )
    for label, data in panels.items():
        source.put(population.location(label), data)
    return population


@pytest.fixture
def synthetic_population() -> SyntheticPopulation:
    """A fresh synthetic population bundle per test."""
    return build_synthetic_population()


@pytest.fixture
def gzip_csv_writer() -> Any:
    """Return :func:`gzip_csv` for tests that build their own panels."""
    return gzip_csv


# --------------------------------------------------------------------------- #
# Synthetic companion sets
# --------------------------------------------------------------------------- #


def joint_certificate_json(certified_sha256: str, /, **overrides: Any) -> bytes:
    """A certificate in the v17 ``CORE_JOINT_STATUS.json`` shape (methodology M03)."""
    import json

    document: dict[str, Any] = {
        "status": "COHERENT_CORE_MATCHED_BLOCKS",
        "structure_status": "QC_PASSED",
        "prediction_validation_status": "EXTERNAL_HOLDOUT_PENDING",
        "panel_sha256": certified_sha256,
        "matched_blocks": ["marketing_behavior"],
        "core_same_person_joint": True,
        "cross_block_same_person_joint": False,
        "client_joint_outputs_allowed": False,
        "descriptive_core_outputs_allowed": True,
        "matched_block_outputs_allowed": True,
        "cross_block_joint_claims_allowed": False,
    }
    document.update(overrides)
    return json.dumps(document, indent=2).encode("utf-8")


def _csv(header: list[str], rows: list[list[str]]) -> bytes:
    import csv
    import io

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


@dataclass
class SyntheticCompanions:
    """A synthetic population whose contract declares a companion set."""

    population: SyntheticPopulation
    assets: dict[str, bytes]

    @property
    def contract(self) -> Any:
        return self.population.contract

    @property
    def source(self) -> Any:
        return self.population.source

    def locations(self, label: str = "v1_4") -> dict[str, str]:
        """Asset id -> location, for ``label``'s set. The certificate differs per label."""
        return {
            asset: f"companions/{label}/{asset}"
            if asset == "CORE_JOINT_STATUS.json"
            else f"companions/{asset}"
            for asset in self.assets
        }


def build_synthetic_companions() -> SyntheticCompanions:
    from dataclasses import replace

    from aia_core.domain.population import CompanionKind, CompanionSpec, content_sha256

    pop = build_synthetic_population()
    fields = list(pop.fields)
    assets = {
        "SCORECARD.csv": _csv(["dimension", "score"], [[f, "0.9"] for f in fields]),
        "PERSONA_CATALOG.csv": _csv(["column", "label"], [["vek", "age"], ["segment", "seg"]]),
        "RESPONDENT_AUDIT.csv": _csv(
            ["panel_row_id", "audit_status"], [[f"R{i}", "PASS"] for i in range(1, 7)]
        ),
        "CORE_JOINT_STATUS.json": joint_certificate_json(content_sha256(pop.panel_bytes("v1_4"))),
    }
    specs = (
        CompanionSpec(
            asset_id="SCORECARD.csv",
            kind=CompanionKind.DIMENSION_SCORECARD,
            sha256=content_sha256(assets["SCORECARD.csv"]),
            byte_size=len(assets["SCORECARD.csv"]),
            fmt="csv",
            rows=len(fields),
            columns=2,
        ),
        CompanionSpec(
            asset_id="PERSONA_CATALOG.csv",
            kind=CompanionKind.PERSONA_SIGNAL_CATALOG,
            sha256=content_sha256(assets["PERSONA_CATALOG.csv"]),
            byte_size=len(assets["PERSONA_CATALOG.csv"]),
            fmt="csv",
            rows=2,
            columns=2,
            panel_column_field="column",
        ),
        CompanionSpec(
            asset_id="RESPONDENT_AUDIT.csv",
            kind=CompanionKind.RESPONDENT_AUDIT,
            sha256=content_sha256(assets["RESPONDENT_AUDIT.csv"]),
            byte_size=len(assets["RESPONDENT_AUDIT.csv"]),
            fmt="csv",
            rows=6,
            columns=2,
            status_column="audit_status",
            forbidden_status="FAIL",
        ),
        CompanionSpec(
            asset_id="CORE_JOINT_STATUS.json",
            kind=CompanionKind.CORE_JOINT_STATUS,
            sha256=content_sha256(assets["CORE_JOINT_STATUS.json"]),
            byte_size=len(assets["CORE_JOINT_STATUS.json"]),
            fmt="json",
        ),
    )
    pop.contract = replace(
        pop.contract, companions=specs, joint_certified_labels=frozenset({"v1_4"})
    )
    companions = SyntheticCompanions(population=pop, assets=assets)
    # Every label ships the same pinned certificate bytes: it certifies v1_4 only.
    for label in ("v1_BASE", "v1_1", "v1_4"):
        for asset, location in companions.locations(label).items():
            pop.source.put(location, assets[asset])
    return companions


@pytest.fixture
def synthetic_companions() -> SyntheticCompanions:
    """A synthetic population whose contract requires a companion set."""
    return build_synthetic_companions()


@pytest.fixture
def certificate_json() -> Any:
    """Return :func:`joint_certificate_json`."""
    return joint_certificate_json
