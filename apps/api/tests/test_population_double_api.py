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


def test_readiness_draws_the_panel_sample_a_start_would_draw(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """RQC6b: a panel design's readiness draws the run's own sample over the population a new run
    records, and forecasts its support from it; drawn once per version and design, then kept."""
    made = world.design(researcher, DESIGN)
    assert made.status_code in (200, 201), made.text
    url = f"{API}/studies/{world.study_id()}/research/readiness"
    params = {"design_revision_id": made.json()["revision_id"], "persona_source": "panel"}
    read = researcher.get(url, params=params)
    assert read.status_code == 200, read.text
    body = read.json()
    composition = body["sample_composition"]
    assert composition["refused"] is None and composition["support_counted"] is True
    assert composition["quota_fields"] and composition["cells"]
    assert sum(c["n"] for c in composition["cells"]) == DESIGN["n"]
    assert all(len(c["values"]) == len(composition["quota_fields"]) for c in composition["cells"])
    check = next(c for c in body["checks"] if c["id"] == "support_forecast")
    # Known, from the sample's own donors: a sample at any other seed would read unknown.
    assert check["message"].startswith(
        f"Běh bude mít {composition['sample_donors']} různých dárců na {DESIGN['n']} respondentů"
    )
    again = researcher.get(url, params=params).json()["sample_composition"]
    assert again == composition
    assert len(app.state.audience_previewer._draws) == 1  # kept, not drawn again

    roster = researcher.get(url, params={**params, "persona_source": "fictional_roster"})
    assert roster.status_code == 200, roster.text
    assert roster.json()["sample_composition"] is None


def test_a_start_draws_the_sample_readiness_drew(
    app: FastAPI, researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gaps a person acknowledges on readiness are the start's: both draw at the same
    filters, n and seed (RQC6b)."""
    previewer = app.state.audience_previewer
    asked: list[tuple[Any, ...]] = []
    draw = previewer.panel_sample

    def spy(session: Any, filters: Any, n: int, seed: int) -> Any:
        asked.append((filters, n, seed))
        return draw(session, filters, n, seed)

    monkeypatch.setattr(previewer, "panel_sample", spy)
    revision = world.design(researcher, DESIGN).json()["revision_id"]
    study = f"{API}/studies/{world.study_id()}/research"
    read = researcher.get(
        f"{study}/readiness", params={"design_revision_id": revision, "persona_source": "panel"}
    )
    assert read.status_code == 200, read.text
    started = researcher.post(
        f"{study}/runs", json={"design_revision_id": revision, "persona_source": "panel"}
    )
    assert started.status_code == 201, started.text
    assert len(asked) == 2 and asked[0] == asked[1]
    assert read.json()["sample_composition"]["seed"] == asked[0][2]


def test_a_population_that_will_not_load_reads_unknown_never_fails_readiness(
    app: FastAPI, researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aia_core.domain.population import PopulationError

    def broken(session: Any) -> Any:
        raise PopulationError("a fictional missing asset")

    monkeypatch.setattr(app.state.audience_previewer, "_population", broken)
    revision = world.design(researcher, DESIGN).json()["revision_id"]
    read = researcher.get(
        f"{API}/studies/{world.study_id()}/research/readiness",
        params={"design_revision_id": revision, "persona_source": "panel"},
    )
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["sample_composition"]["refused"] == "population_unavailable"
    assert body["sample_composition"]["cells"] == []
    # A population that will not load says nothing of the design: no failed check.
    assert all(c["id"] != "panel_sample" for c in body["checks"])
    check = next(c for c in body["checks"] if c["id"] == "support_forecast")
    assert check["status"] == "WARN" and "se ukáže až při výběru" in check["message"]


def test_readiness_for_a_run_over_a_selected_child_draws_nothing(
    researcher: TestClient, world: Any
) -> None:
    """A run over a selected child draws from the child, which the sampler does not read: its
    readiness reads unknown, as its start does, so the two agree (review on #694)."""
    revision = world.design(researcher, DESIGN).json()["revision_id"]
    url = f"{API}/studies/{world.study_id()}/research/readiness"
    params = {"design_revision_id": revision, "persona_source": "panel"}
    over_child = researcher.get(url, params={**params, "population_version_id": "PV-CHILD"})
    assert over_child.status_code == 200, over_child.text
    body = over_child.json()
    assert body["sample_composition"] is None
    check = next(c for c in body["checks"] if c["id"] == "support_forecast")
    assert "se ukáže až při výběru" in check["message"]
    over_live = researcher.get(url, params=params).json()
    assert over_live["sample_composition"] is not None


def test_a_refused_draw_names_what_it_refused(researcher: TestClient, world: Any) -> None:
    """A refusal carries the filters it names, as the audience preview's ``reasons`` do, so
    Vzorek can say which filter (review on #725): the code alone left a fragment."""
    design = {**DESIGN, "audience": {"filters": {"fiktivni_pole": "ano"}}}
    revision = world.design(researcher, design).json()["revision_id"]
    read = researcher.get(
        f"{API}/studies/{world.study_id()}/research/readiness",
        params={"design_revision_id": revision, "persona_source": "panel"},
    )
    assert read.status_code == 200, read.text
    composition = read.json()["sample_composition"]
    assert composition["refused"] == "sampling_filter_invalid"
    assert composition["refused_reasons"] and "fiktivni_pole" in composition["refused_reasons"][0]


def test_a_drawn_sample_whose_forecast_is_unknown_says_it_was_not_counted(
    researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A drawn sample can still leave the forecast unknown (a respondent without a donor,
    ``forecast_support``): the composition says so, so Vzorek never reads the unknown check's
    words as a counted forecast (review on #725)."""
    from aia_core.application import research as application

    real = application.forecast_support
    monkeypatch.setattr(
        application,
        "forecast_support",
        lambda spec, **kw: real(spec, **{**kw, "sample": None}),  # as an undonored sample reads
    )
    revision = world.design(researcher, DESIGN).json()["revision_id"]
    read = researcher.get(
        f"{API}/studies/{world.study_id()}/research/readiness",
        params={"design_revision_id": revision, "persona_source": "panel"},
    )
    assert read.status_code == 200, read.text
    composition = read.json()["sample_composition"]
    assert composition["refused"] is None and composition["cells"]
    assert composition["support_counted"] is False


def test_a_sample_the_sampler_refuses_fails_readiness_and_refuses_the_start(
    researcher: TestClient, world: Any
) -> None:
    """Fieldwork draws the sample readiness drew and would refuse it, so the refusal is a FAIL
    by name and a start is refused before any run (RQC6); the roster run of the same design is
    not held to a sample it never draws."""
    design = {**DESIGN, "audience": {"filters": {"fiktivni_pole": "ano"}}}
    revision = world.design(researcher, design).json()["revision_id"]
    study = f"{API}/studies/{world.study_id()}/research"
    read = researcher.get(
        f"{study}/readiness", params={"design_revision_id": revision, "persona_source": "panel"}
    )
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["ready"] is False
    check = next(c for c in body["checks"] if c["id"] == "panel_sample")
    assert check["status"] == "FAIL" and "fiktivni_pole" in check["message"]

    started = researcher.post(
        f"{study}/runs", json={"design_revision_id": revision, "persona_source": "panel"}
    )
    assert started.status_code == 409, started.text
    assert started.json()["code"] == "design_not_ready"
    assert [c["id"] for c in started.json()["details"]["failed"]] == ["panel_sample"]
    assert researcher.get(f"{study}/runs").json()["items"] == []

    roster = researcher.get(
        f"{study}/readiness",
        params={"design_revision_id": revision, "persona_source": "fictional_roster"},
    ).json()
    assert all(c["id"] != "panel_sample" for c in roster["checks"])
