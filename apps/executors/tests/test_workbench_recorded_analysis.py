"""The UI workbench reaches an internal draft report on recorded answers (artifact-chain CHN7).

Before this, the workbench composition had no gateway: a run's analysis parked
(``analysis_unconfigured``) and, without ``AIA_AI_ANALYSIS_ENABLED`` in the API, the template added
no report node, so nothing after Sociomapy could be seen on this machine. Here a fictional run on
the workbench registry is walked over HTTP, as the browser starts it, to its stored draft: the
eight modules answered by :class:`RecordedModels` behind the real gateway, reservations and
ledger, every call priced at zero and naming its recording.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from aia_api.config import Environment, Settings
from aia_api.main import create_app
from aia_core.domain.ai_contracts import UsageOutcome
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.infrastructure.ai_usage_repository import AIUsageRepository
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_executors import workbench
from aia_executors.workbench import recorded_analysis, workbench_registry_for
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi.testclient import TestClient

API = "/api/v1"
RQ = "Jak často lidé ráno pijí kávu?"
DESIGN: dict[str, Any] = {
    "title": "Fiktivní ranní nápoj",
    "goal": "Zjistit, co fiktivní lidé ráno pijí.",
    "n": 200,
    "research_plan": {"research_questions": [RQ]},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Jak často pijete kávu?",
                    "typ": "skala",
                    "skala": [1, 5],
                    "research_questions": [RQ],
                },
                {"id": "q2", "text": "Co si ráno koupíte?", "typ": "vyber",
                 "kategorie": ["Kávu", "Čaj", "Nic"]},
            ],
        }
    ],
}  # fmt: skip


@pytest.fixture
def api(world: Any, database_url: str, store: InMemoryArtifactStore) -> Iterator[TestClient]:
    """The API as the UI workbench starts it (tools/ui_workbench/api_standin.py): fictional
    fieldwork, analysis switched on."""
    app = create_app(
        Settings(
            env=Environment.TEST,
            database_url=database_url,
            identity_provider="test",
            log_level="WARNING",
            log_format="console",
            research_fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE.value,
            ai_analysis_enabled=True,
            ai_analysis_reservation_usd=0.01,
        )
    )
    with TestClient(app) as client:
        app.state.artifact_store = store
        app.state.identity_provider.register(
            "token-lead",
            subject="lead@art-chain.io",
            email="lead@art-chain.io",
            display_name="Lead",
        )
        client.headers["Authorization"] = "Bearer token-lead"
        yield client


def _worker(sessions: Any, database_url: str, executors: dict[str, Any]) -> Worker:
    return Worker(
        session_factory=sessions,
        executors=executors,
        settings=WorkerSettings(
            database_url=database_url,
            executors="aia_executors.workbench:build_registry",
            worker_id="workbench-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _start(api: TestClient, world: Any) -> str:
    study = f"{API}/studies/{world.study_id}"
    now = api.get(f"{study}/workspace/content").json()
    saved = api.put(
        f"{study}/workspace/content", json={"content": DESIGN, "base_revision": now.get("revision")}
    )
    assert saved.status_code == 200, saved.text
    made = api.post(
        f"{study}/design/revisions",
        json={
            "content": DESIGN,
            "source_stage": "run",
            "workspace_revision": saved.json()["revision"],
        },
    )
    assert made.status_code in (200, 201), made.text
    started = api.post(
        f"{study}/research/runs", json={"design_revision_id": made.json()["revision_id"]}
    )
    assert started.status_code in (200, 201), started.text
    return str(started.json()["run_id"])


def test_a_fictional_run_reaches_its_internal_draft_on_recorded_answers_at_zero_cost(
    api: TestClient,
    world: Any,
    sessions: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
) -> None:
    run_id = _start(api, world)
    worker = _worker(
        sessions,
        database_url,
        workbench_registry_for(
            store=store, build=build, analysis=recorded_analysis(store=store, build=build)
        ),
    )
    endings = []
    while (result := worker.run_once()) is not None:
        endings.append(result.ending)
    assert endings and set(endings) == {"completed"}, endings

    run = f"{API}/studies/{world.study_id}/research/runs/{run_id}"
    assert api.get(run).json()["status"] == "COMPLETED"
    report = api.get(f"{run}/report")
    assert report.status_code == 200, report.text
    assert report.json()["state"] == "READY"
    assert report.json()["review_state"] == "DRAFT_UNAPPROVED"
    download = api.get(f"{run}/report/download")
    assert download.status_code == 200 and download.content[:2] == b"PK"

    with sessions() as session:
        ledger = AIUsageRepository(session, world.lead_scope(session)).events(run_id=run_id)
    answered = [e for e in ledger if e.outcome is UsageOutcome.SUCCEEDED]
    # One recorded answer per module; nothing priced, every answer naming its recording.
    assert len(answered) == len(AnalysisModuleId)
    assert all(e.cost_usd == 0 for e in ledger)
    assert all((e.provider_request_id or "").startswith("recorded-") for e in answered)


def test_build_registry_answers_analysis_from_recordings_only_when_asked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setenv("AIA_ENV", "local")
    monkeypatch.setenv("AIA_STORAGE_BACKEND", "filesystem")
    monkeypatch.setenv("AIA_STORAGE_ROOT", str(tmp_path))
    # A developer's live runtime keys are never read: the recorded runtime is the composition's own.
    monkeypatch.setenv("AIA_BEDROCK_MODEL_ID", "eu.anthropic.a-live-model")
    monkeypatch.delenv("AIA_AI_ANALYSIS_ENABLED", raising=False)
    parked = workbench.build_registry()["research_analysis"]
    monkeypatch.setenv("AIA_AI_ANALYSIS_ENABLED", "true")
    recorded = workbench.build_registry()["research_analysis"]
    assert type(parked) is type(recorded)
    assert getattr(parked, "_gateway", None) is None
    assert getattr(recorded, "_gateway", None) is not None
    assert workbench.RECORDED_RUNTIME["AIA_BEDROCK_INPUT_USD_PER_MTOK"] == "0"
    assert workbench.RECORDED_RUNTIME["AIA_BEDROCK_OUTPUT_USD_PER_MTOK"] == "0"
