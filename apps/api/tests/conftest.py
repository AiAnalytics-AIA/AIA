"""API test fixtures.

Each test gets an app with its own database and a provisioned organization,
clients, studies and users at every role, so tests exercise the same
authentication and authorisation path production does.

Authentication uses ``TestIdentityProvider`` with opaque tokens: the Cognito JWT
contract is verified separately in ``test_identity.py`` against real signed
tokens, so tests that merely need *an* authenticated caller do not each pay for
crypto.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.audience_preview import AudiencePreviewer
from aia_core.application.population import PopulationRuntime
from aia_core.application.population_authority import (
    PopulationAuthority,
    PopulationOperatorConfig,
)
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.population import (
    CompanionKind,
    CompanionSpec,
    KnownVersion,
    PopulationImportContract,
    PopulationKind,
    WeightScheme,
    content_sha256,
    field_names_fingerprint,
)
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.population_source import InMemoryPopulationSource
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import Base, ProjectArtifactRow
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_api.config import Environment, Settings
from aia_api.main import create_app

API = "/api/v1"


@pytest.fixture
def settings() -> Settings:
    """Test settings: an isolated database and the deterministic identity provider."""
    return Settings(
        env=Environment.TEST,
        database_url=os.environ.get("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        identity_provider="test",
        log_level="WARNING",
        log_format="console",
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    """An application with a freshly created schema."""
    application = create_app(settings)
    with TestClient(application):
        Base.metadata.create_all(application.state.engine)
        try:
            yield application
        finally:
            Base.metadata.drop_all(application.state.engine)


@dataclass(frozen=True)
class World:
    """A provisioned organization, two clients, three studies and users at every role.

    Two clients exist deliberately: the isolation tests that matter are the ones
    crossing a client boundary, and a single-client fixture cannot express them.
    """

    organization_id: str
    clients: dict[str, Any]
    studies: dict[str, Any]
    users: dict[str, str]
    tokens: dict[str, str]

    def study_id(self, name: str = "primary") -> str:
        return self.studies[name].study_id

    def client_id(self, name: str = "primary") -> str:
        return self.clients[name].client_id


@pytest.fixture
def world(app: FastAPI) -> World:
    """Provision the scope graph and register a token per user."""
    factory = create_session_factory(app.state.engine)
    provider = app.state.identity_provider

    with factory() as session:
        scope_repo = ScopeRepository(session)
        resolver = ScopeResolver(session)

        org, owner = scope_repo.create_organization(
            slug="aia",
            name="AI Analytics",
            owner_email="owner@art-chain.io",
            owner_name="Owner",
        )
        admin = resolver.organization_context(
            AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
        )

        primary = scope_repo.create_client(admin, slug="acme", name="Acme Corp")
        other = scope_repo.create_client(admin, slug="globex", name="Globex Inc")

        studies = {
            "primary": scope_repo.create_study(
                admin,
                client_id=primary.client_id,
                slug="brand-2026",
                name="Acme brand",
                budget_usd=500.0,
            ),
            "sibling": scope_repo.create_study(
                admin,
                client_id=primary.client_id,
                slug="pricing-2026",
                name="Acme pricing",
                budget_usd=200.0,
            ),
            "other_client": scope_repo.create_study(
                admin,
                client_id=other.client_id,
                slug="brand-2026",
                name="Globex brand",
                budget_usd=300.0,
            ),
        }

        # ADR 0019: one role. The labels are kept so the tests that name one still
        # read; every one holds the same Researcher grant. They collapse with the grants.
        users = {"owner": owner.user_id}
        for label in ("lead", "researcher", "reviewer", "viewer"):
            member = scope_repo.add_member(admin, email=f"{label}@art-chain.io")
            users[label] = member.user_id

        other_lead = scope_repo.add_member(admin, email="other-lead@art-chain.io")
        users["other_lead"] = other_lead.user_id

        # A member of the organization holding no client grant at all.
        outsider = scope_repo.add_member(admin, email="outsider@art-chain.io")
        users["outsider"] = outsider.user_id

        session.commit()

        # Bind a token per user. The subject matches the email, which is what the
        # provisioned user record was keyed on.
        tokens: dict[str, str] = {}
        for label in users:
            email = (
                "owner@art-chain.io"
                if label == "owner"
                else f"{label.replace('_', '-')}@art-chain.io"
            )
            token = f"token-{label}"
            provider.register(token, subject=email, email=email, display_name=label)
            tokens[label] = token

        return World(
            organization_id=org.organization_id,
            clients={"primary": primary, "other": other},
            studies=studies,
            users=users,
            tokens=tokens,
        )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """An unauthenticated client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def as_user(app: FastAPI, world: World):
    """Return a factory for clients authenticated as a provisioned user."""

    def build(label: str) -> TestClient:
        c = TestClient(app)
        c.headers.update({"Authorization": f"Bearer {world.tokens[label]}"})
        return c

    return build


@pytest.fixture
def lead(as_user: Any) -> TestClient:
    """A client authenticated as a LEAD on the primary client."""
    return as_user("lead")


@pytest.fixture
def researcher(as_user: Any) -> TestClient:
    """A client authenticated as a RESEARCHER on the primary client."""
    return as_user("researcher")


@pytest.fixture
def reviewer(as_user: Any) -> TestClient:
    """The person once labelled REVIEWER; a Researcher like everyone else (ADR 0019)."""
    return as_user("reviewer")


@pytest.fixture
def viewer(as_user: Any) -> TestClient:
    """The person once labelled VIEWER; a Researcher like everyone else (ADR 0019)."""
    return as_user("viewer")


@pytest.fixture
def other_client_lead(as_user: Any) -> TestClient:
    """A LEAD on a *different* client, for cross-client isolation tests."""
    return as_user("other_lead")


@pytest.fixture
def outsider(as_user: Any) -> TestClient:
    """An organization member with no client grant."""
    return as_user("outsider")


@pytest.fixture
def owner(as_user: Any) -> TestClient:
    """The organization OWNER: may administer, but holds no client grant."""
    return as_user("owner")


@pytest.fixture
def damage_artifact(app: FastAPI) -> Callable[[str, str], None]:
    """Damage an artifact's stored object behind the database's back.

    ``"tampered"`` replaces the bytes, so they no longer match the recorded
    SHA-256; ``"missing"`` deletes the object. The key comes from the artifact's
    row, so this works on whichever store the app was built with.
    """

    def damage(artifact_id: str, how: str) -> None:
        with create_session_factory(app.state.engine)() as session:
            key = session.scalars(
                select(ProjectArtifactRow.storage_key).where(
                    ProjectArtifactRow.artifact_id == artifact_id
                )
            ).one()
        if how == "tampered":
            app.state.artifact_store.put(key, b'{"tampered": true}')
        elif how == "missing":
            app.state.artifact_store.delete(key)
        else:  # pragma: no cover - a typo in a test
            raise ValueError(f"unknown damage {how!r}")

    return damage


@pytest.fixture
def artifact_status(app: FastAPI) -> Callable[[str], str]:
    """The status the database holds for an artifact, read in a session of its own.

    Not through the API: a response can say CORRUPT while the row it came from is
    rolled back, which is exactly what the durable-mark tests are about.
    """

    def read(artifact_id: str) -> str:
        with create_session_factory(app.state.engine)() as session:
            status: str = session.scalars(
                select(ProjectArtifactRow.status).where(
                    ProjectArtifactRow.artifact_id == artifact_id
                )
            ).one()
        return status

    return read


@pytest.fixture
def api_prefix() -> str:
    """The versioned API prefix."""
    return API


@pytest.fixture
def projects_url(world: World):
    """Return a function building the projects URL for a named study.

    Exposed as a fixture rather than an importable helper because the two test
    packages in this repository are both called ``tests``, so relative imports
    between them collide under a single pytest invocation.
    """

    def build(study: str = "primary") -> str:
        return f"{API}/studies/{world.study_id(study)}/projects"

    return build


# --------------------------------------------------------------------------- #
# A fictional LIVE population, for the audience preview (panel-grounded 6c)
# --------------------------------------------------------------------------- #
# The sampler's fictional rows (packages/aia_core/tests/fixtures/representative_draw/rows.csv:
# 3,000 rows on 400 donors, every quota field) with the joint certificate, imported and
# established LIVE through PopulationRuntime as an operator would; the previewer over it is
# what the API composes -- the production one reads the v17 contract, which these rows cannot meet.

ROOT = Path(__file__).resolve().parents[3]
CORE_FIXTURES = ROOT / "packages" / "aia_core" / "tests" / "fixtures"
WEIGHT = "vaha_strukturalni_2025"
LIVE = "GROUNDED_LIVE"
_POLICY_HEADER = (
    "field",
    "block",
    "source",
    "evidence_status",
    "production_grade",
    "recommended_use",
    "description",
    "persona_eligible",
)
_DEFAULT = ("core", "POPULATION_ANCHOR", "A", "PERSONA_OR_ANALYSIS_WITH_SCOPE", "yes")
_AUDIT = {
    "panel_row_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
    "core_donor_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
    WEIGHT: ("weight", "NEW_WEIGHT", "T", "AUDIT_ONLY", "no"),
}


def _csv(header: tuple[str, ...], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _rows() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    text = (CORE_FIXTURES / "representative_draw" / "rows.csv").read_text("utf-8")
    header, *raw = list(csv.reader(io.StringIO(text)))
    return tuple(header), [dict(zip(header, r, strict=True)) for r in raw]


class _NoEnrichment:
    enricher_id = "test-no-enrichment/v1"

    def derive(self, panel: Any) -> dict[str, tuple[str | None, ...]]:
        return {}


def _operator() -> Any:
    config = PopulationOperatorConfig.from_names(
        {"operator": ("POPULATION_ESTABLISH", "POPULATION_PROMOTE")}
    )
    return PopulationAuthority(config).operator_context(
        AuthenticatedPrincipal(user_id="operator", organization_id="platform")
    )


@dataclass(frozen=True, slots=True)
class GroundedPopulation:
    """The population as established, and how a run reaches it."""

    contract: PopulationImportContract
    source: InMemoryPopulationSource
    rows: int
    #: The LIVE population it is established as.
    live_id: str = LIVE

    def runtime(self, session: Session) -> PopulationRuntime:
        return PopulationRuntime(
            session, contract=self.contract, source=self.source, enricher=_NoEnrichment()
        )

    def previewer(self) -> AudiencePreviewer:
        """The API's previewer, over this population's LIVE."""
        return AudiencePreviewer(
            contract=self.contract, source=self.source, enricher=_NoEnrichment(), population_id=LIVE
        )


def _grounded_population(session: Session, *, omit: tuple[str, ...] = ()) -> GroundedPopulation:
    """Import the fictional rows as v1_BASE, v1_1 (STATIC) and v1_4 (LIVE), and commit."""
    header, base = _rows()
    versions = {
        label: [[r[h] if h != "panel_row_id" else f"{r[h]}-{label}" for h in header] for r in base]
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    panels = {label: gzip.compress(_csv(header, rows), mtime=0) for label, rows in versions.items()}
    # The dictionary's column order: field, block, source, evidence_status, grade, use, text,
    # persona.
    dictionary = _csv(
        _POLICY_HEADER,
        [
            [
                name,
                (row := _AUDIT.get(name, _DEFAULT))[0],
                "synthetic",
                row[1],
                row[2],
                row[3],
                f"{name} (synthetic)",
                row[4],
            ]
            for name in header
        ],
    )
    certificate = json.dumps(
        {
            "status": "COHERENT_CORE_MATCHED_BLOCKS",
            "structure_status": "QC_PASSED",
            "prediction_validation_status": "EXTERNAL_HOLDOUT_PENDING",
            "panel_sha256": content_sha256(panels["v1_4"]),
            "matched_blocks": [],
            "core_same_person_joint": True,
            "cross_block_same_person_joint": False,
            "client_joint_outputs_allowed": False,
            "descriptive_core_outputs_allowed": True,
            "matched_block_outputs_allowed": True,
            "cross_block_joint_claims_allowed": False,
        },
        indent=2,
    ).encode("utf-8")
    assets = {
        asset: data
        for asset, data in (("CORE_JOINT_STATUS.json", certificate),)
        if asset not in omit
    }
    total = math.fsum(float(r[WEIGHT] or 0) for r in base)
    contract = PopulationImportContract(
        contract_id="grounded_population/v1",
        dataset_id="grounded_population",
        field_count=len(header),
        field_names_sha256=field_names_fingerprint(header),
        dictionary_sha256=content_sha256(dictionary),
        primary_key="panel_row_id",
        expected_rows=len(base),
        weight_schemes=(
            WeightScheme("default_current", WEIGHT, expected_total=total, tolerance=1e-6),
        ),
        default_weight_role="default_current",
        known_versions=(
            KnownVersion("v1_BASE", content_sha256(panels["v1_BASE"]), len(panels["v1_BASE"])),
            KnownVersion("v1_1", content_sha256(panels["v1_1"]), len(panels["v1_1"]), "v1_BASE"),
            KnownVersion("v1_4", content_sha256(panels["v1_4"]), len(panels["v1_4"]), "v1_1"),
        ),
        static_reference_label="v1_1",
        enrichment_fields=(),
        companions=tuple(
            CompanionSpec(
                asset_id=asset,
                kind=CompanionKind.CORE_JOINT_STATUS
                if asset == "CORE_JOINT_STATUS.json"
                else CompanionKind.INTEGRITY_ONLY,
                sha256=content_sha256(data),
                byte_size=len(data),
                fmt="json" if asset.endswith(".json") else "csv",
            )
            for asset, data in assets.items()
        ),
        joint_certified_labels=frozenset({"v1_4"}),
    )
    source = InMemoryPopulationSource({"dictionary.csv": dictionary})
    for label, data in panels.items():
        source.put(f"panels/{label}.csv.gz", data)
        for asset, blob in assets.items():
            source.put(f"companions/{label}/{asset}", blob)
    world = GroundedPopulation(contract=contract, source=source, rows=len(base))
    runtime = world.runtime(session)

    def load(label: str) -> Any:
        return runtime.import_version(
            label=label,
            panel_location=f"panels/{label}.csv.gz",
            dictionary_location="dictionary.csv",
            provenance="fictional sampling rows",
            imported_by="importer",
            companion_locations={a: f"companions/{label}/{a}" for a in assets},
        )

    load("v1_BASE")
    anchor = load("v1_1")
    operator = _operator()
    runtime.establish(
        population_id="GROUNDED_STATIC",
        kind=PopulationKind.STATIC,
        version_id=anchor.version_id,
        operator=operator,
        reason="the anchor",
    )
    live = load("v1_4")
    runtime.establish(
        population_id=LIVE,
        kind=PopulationKind.LIVE,
        version_id=live.version_id,
        operator=operator,
        reason="the grounded fieldwork test population",
    )
    session.commit()
    return world


@pytest.fixture
def fictional_live(app: FastAPI) -> GroundedPopulation:
    """The fictional LIVE population in this app's database."""
    with create_session_factory(app.state.engine)() as session:
        return _grounded_population(session)
