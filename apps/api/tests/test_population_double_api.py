"""The population double over HTTP (plan run-qc-and-checkpoint RQC10).

With ``AIA_POPULATION_DOUBLE`` on, a local or test API establishes the fictional double on the
first request that needs it, a new panel run records the double's LIVE, and the audience step
reads it; every deployed environment refuses the switch at start.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from aia_core.application.population_double import DOUBLE_NAMES, PopulationDoubleRefused
from aia_core.infrastructure.tables import Base
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aia_api.config import Environment, Settings
from aia_api.dependencies import ensure_population_double, install_population_double
from aia_api.main import create_app

API = "/api/v1"
PRODUCTION_OK = {
    "database_url": "postgresql+psycopg://u:p@db/aia",
    "build_sha": "0" * 40,
    "storage_backend": "s3",
    "storage_bucket": "aia-artifacts",
    "storage_region": "eu-central-1",
    "identity_provider": "cognito",
    "cognito_region": "eu-central-1",
    "cognito_user_pool_id": "eu-central-1_pool",
    "cognito_client_id": "client",
    "ai_research_lead_enabled": False,
}
DESIGN = {
    "title": "Fiktivní ranní nápoj",
    "goal": "Zjistit, co fiktivní lidé ráno pijí.",
    "n": 200,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]}
            ],
        }
    ],
}


@pytest.mark.parametrize("env", [Environment.DEVELOP, Environment.STAGING, Environment.PRODUCTION])
def test_every_deployed_environment_refuses_the_switch(env: Environment) -> None:
    settings = Settings(**{**PRODUCTION_OK, "env": env, "population_double": True})
    with pytest.raises(RuntimeError, match="AIA_POPULATION_DOUBLE is refused"):
        settings.validate_for_production()
    # Off, the same deployment starts: the refusal is the switch's alone.
    Settings(**{**PRODUCTION_OK, "env": env}).validate_for_production()


def test_an_unset_aia_env_refuses_the_double(monkeypatch: pytest.MonkeyPatch) -> None:
    """The settings read an unset AIA_ENV as local; the double needs it named, as the worker's
    composition does, so an unset environment never composes it."""
    monkeypatch.delenv("AIA_ENV", raising=False)
    unset = Settings(population_double=True, database_url="sqlite+pysqlite:///:memory:")
    assert unset.env is Environment.LOCAL and "env" not in unset.model_fields_set
    with pytest.raises(PopulationDoubleRefused, match="unset or unknown"):
        install_population_double(FastAPI(), unset)
    named = Settings(env=Environment.LOCAL, population_double=True)
    app = FastAPI()
    install_population_double(app, named)
    assert app.state.run_population.population_id == DOUBLE_NAMES.live


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={"population_double": True, "ai_population_personas_enabled": True}
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    """The API with the double composed; the schema is created after startup, as in every test,
    so the double cannot be established before its first request."""
    application = create_app(settings)
    with TestClient(application):
        Base.metadata.create_all(application.state.engine)
        try:
            yield application
        finally:
            Base.metadata.drop_all(application.state.engine)


def test_a_panel_run_started_over_http_records_the_doubles_live(
    researcher: TestClient, world: Any
) -> None:
    made = world.design(researcher, DESIGN)
    assert made.status_code in (200, 201), made.text
    started = researcher.post(
        f"{API}/studies/{world.study_id()}/research/runs",
        json={"design_revision_id": made.json()["revision_id"], "persona_source": "panel"},
    )
    assert started.status_code == 201, started.text
    population = started.json()["population"]
    assert population["population_id"] == DOUBLE_NAMES.live
    assert population["read_by_fieldwork"] is True  # a panel run: its respondents come from it


def test_the_audience_step_reads_the_double(researcher: TestClient) -> None:
    catalogue = researcher.get(f"{API}/population/audience-catalogue")
    assert catalogue.status_code == 200, catalogue.text
    assert catalogue.json()["version_label"] == "v1_4"
    preview = researcher.post(f"{API}/population/audience-preview", json={"filters": {}, "n": 200})
    assert preview.status_code == 200, preview.text


def test_concurrent_first_requests_establish_the_double_once(app: FastAPI) -> None:
    """The audience step's two first reads arrive together, each in its own request
    transaction; both find the double established and nothing is imported twice.

    PostgreSQL only (``DATABASE_URL``): SQLite admits one writer, so two transactions that both
    read before writing deadlock there; the core suite holds the same race at the double."""
    import threading
    from types import SimpleNamespace

    from aia_core.infrastructure.db import create_session_factory
    from aia_core.infrastructure.population_repository import PopulationRegistryRepository

    if app.state.engine.dialect.name == "sqlite":
        pytest.skip("SQLite admits one writer; the race is PostgreSQL's (DATABASE_URL)")
    factory = create_session_factory(app.state.engine)
    request: Any = SimpleNamespace(app=app)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def first_request() -> None:
        try:
            with factory() as session:
                barrier.wait(timeout=10)
                ensure_population_double(request, session)
                session.commit()  # as the request's own transaction does at its end
        except BaseException as exc:  # the test reports it
            errors.append(exc)

    threads = [threading.Thread(target=first_request) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert errors == []
    with factory() as session:
        registry = PopulationRegistryRepository(session)
        assert registry.population(DOUBLE_NAMES.live) is not None
        assert len(registry.versions(DOUBLE_NAMES.dataset_id)) == 3
