"""The population double across both processes (plan run-qc-and-checkpoint RQC10, tier A AC-05).

A panel run is started over HTTP by an API that composed the double; a worker that composed its
own double -- built independently, as a second process would -- draws the run's respondents
from what the run recorded. Nothing is injected into either process: each reads the population
through the canonical loader from the same deterministic bytes. Recorded models answer the
respondents (nothing leaves the process, nothing is paid). And the worker's composition refuses
every environment but local and test before it builds anything.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from aia_api.config import Environment, Settings
from aia_api.main import create_app
from aia_core.application.population_double import (
    DOUBLE_NAMES,
    PopulationDoubleRefused,
    population_double,
)
from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.deployment import DeploymentEnvironment
from aia_core.domain.fieldwork import DataOrigin
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_executors import population_double as composition
from aia_executors.ai_runtime import AIRuntimeSettings, build_ai_fieldwork
from aia_executors.recorded_models import RecordedModels, RecordedSigner, runtime_env
from aia_executors.registry import registry_for
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi.testclient import TestClient

API = "/api/v1"
N = 120
DESIGN: dict[str, Any] = {
    "title": "Fiktivní ranní nápoj",
    "goal": "Zjistit, co fiktivní lidé ráno pijí.",
    "n": N,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
            ],
        }
    ],
}


@pytest.mark.parametrize("env", ["develop", "staging", "production", "", "elsewhere"])
def test_the_workers_composition_refuses_every_environment_but_local_and_test(
    env: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIA_ENV", env)
    with pytest.raises(PopulationDoubleRefused, match="local and test"):
        composition.build_registry()


def test_the_workers_composition_is_the_production_registry_in_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the AI runtime it composes exactly what production composes: fieldwork parks."""
    for key in ("AIA_AI_RUNTIME_ENABLED", "AIA_POPULATION_STORE_BUCKET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AIA_ENV", "test")
    monkeypatch.setenv("AIA_STORAGE_BACKEND", "memory")
    from aia_executors.registry import build_registry

    assert set(composition.build_registry()) == set(build_registry())


@pytest.fixture
def api(world: Any, database_url: str, store: InMemoryArtifactStore) -> Iterator[TestClient]:
    """The API with the double composed (AIA_POPULATION_DOUBLE) and the panel offered."""
    app = create_app(
        Settings(
            env=Environment.TEST,
            database_url=database_url,
            identity_provider="test",
            log_level="WARNING",
            log_format="console",
            population_double=True,
            ai_population_personas_enabled=True,
            ai_fieldwork_reservation_usd=0.25,
        )
    )
    with TestClient(app) as client:
        app.state.artifact_store = store
        app.state.identity_provider.register(
            "token-lead", subject="lead@art-chain.io", email="lead@art-chain.io", display_name="L"
        )
        client.headers["Authorization"] = "Bearer token-lead"
        yield client


def _worker(world: Any, database_url: str, store: Any, build: BuildIdentity, models: Any) -> Worker:
    """The worker's panel path over a double of its own: what the composition passes
    (``aia_executors.population_double``), with the recorded wire in place of Bedrock."""
    env = runtime_env(
        world.client_id,
        [],
        # A panel persona is Class A, and the operator classified the design as such.
        AIA_AI_ROUTE_APPROVED_FOR="CLASS_A_CLIENT_CONFIDENTIAL,CLASS_B_DERIVED_CLIENT,CLASS_C_INTERNAL",
        AIA_AI_POPULATION_PERSONAS_ENABLED="true",
        AIA_POPULATION_ASSET_ROOT="/nonexistent-the-double-replaces-it",
        AIA_AI_MATERIAL_CLASSIFICATIONS="["
        + MaterialApproval(
            sha256=material_sha256(DESIGN),
            data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            provenance="test material explicitly classified as confidential",
        ).model_dump_json()
        + "]",
    )
    settings = AIRuntimeSettings.from_env(env)
    assert settings is not None
    double = population_double(DeploymentEnvironment.TEST)  # the worker's own, built apart
    return Worker(
        session_factory=world.sessions,
        executors=registry_for(
            store=store,
            build=build,
            ai_runtime=build_ai_fieldwork(
                settings,
                build=build,
                transport=models,
                signer=RecordedSigner(),
                population=double.loader(),
            ),
        ),
        settings=WorkerSettings(
            database_url=database_url,
            executors="aia_executors.population_double:build_registry",
            worker_id="double-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def test_a_panel_run_over_http_is_answered_from_the_double_the_worker_composed(
    api: TestClient,
    world: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
) -> None:
    study = f"{API}/studies/{world.study_id}"
    saved = api.put(f"{study}/workspace/content", json={"content": DESIGN, "base_revision": None})
    assert saved.status_code == 200, saved.text
    made = api.post(
        f"{study}/design/revisions",
        json={"content": DESIGN, "source_stage": "run", "workspace_revision": 1},
    )
    assert made.status_code == 201, made.text
    ready = api.get(f"{study}/research/readiness?design_revision_id={made.json()['revision_id']}")
    panel = next(s for s in ready.json()["persona_sources"] if s["source"] == "panel")
    assert panel["offered"] and panel["default"]
    started = api.post(
        f"{study}/research/runs",
        json={"design_revision_id": made.json()["revision_id"], "persona_source": "panel"},
    )
    assert started.status_code == 201, started.text
    run_id = started.json()["run_id"]
    assert started.json()["population"]["population_id"] == DOUBLE_NAMES.live

    models = RecordedModels()
    worker = _worker(world, database_url, store, build, models)
    while worker.run_once() is not None:
        pass

    run = api.get(f"{study}/research/runs/{run_id}").json()
    steps = {s["node_key"]: s for s in run["steps"]}
    assert steps["run"]["status"] == "SUCCEEDED", steps["run"]
    assert steps["run"]["data_origin"] == DataOrigin.MODELLED_AI_PANEL.value
    assert run["population"]["population_id"] == DOUBLE_NAMES.live
    assert run["population"]["read_by_fieldwork"] is True
    assert len(models.requests) > 0 and len(models.requests) % N == 0  # per respondent, block
