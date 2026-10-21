"""The UI workbench runs a design worker on recorded answers (research-lead-workbench 26e).

Without a gateway the workbench's design jobs parked, so a job's card in the Lead's conversation,
its proposal and the stale refusal of an accept could not be met on this machine. Here a job is
started over HTTP as the Lead's card starts it, answered by :class:`RecordedModels` behind the real
gateway, reservations and ledger at zero price, and its proposal is refused once the working copy
moved under it, as the browser meets it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from aia_api.config import Environment, Settings
from aia_api.main import create_app
from aia_core.domain.ai_contracts import UsageOutcome
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.knowledge import KnowledgeKind
from aia_core.infrastructure.ai_usage_repository import AIUsageRepository
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_executors import workbench
from aia_executors.workbench import recorded_research_agent, workbench_registry_for
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi.testclient import TestClient

API = "/api/v1"
DESIGN: dict[str, Any] = {
    "title": "Fiktivní ranní nápoj",
    "goal": "Zjistit, co fiktivní lidé ráno pijí.",
    "n": 200,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
            ],
        }
    ],
}


@pytest.fixture
def api(world: Any, database_url: str, store: InMemoryArtifactStore) -> Iterator[TestClient]:
    """The API as the UI workbench starts it, with the design job's nominal reservation."""
    app = create_app(
        Settings(
            env=Environment.TEST,
            database_url=database_url,
            identity_provider="test",
            log_level="WARNING",
            log_format="console",
            ai_research_reservation_usd=0.01,
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


def _save(api: TestClient, study: str, content: dict[str, Any]) -> int:
    now = api.get(f"{study}/workspace/content").json()
    saved = api.put(
        f"{study}/workspace/content",
        json={"content": content, "base_revision": now.get("revision")},
    )
    assert saved.status_code == 200, saved.text
    return int(saved.json()["revision"])


def test_a_design_job_answers_from_its_recording_at_zero_cost_and_goes_stale_under_an_edit(
    api: TestClient,
    world: Any,
    sessions: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
) -> None:
    # The workbench's seeded clients carry approved knowledge, which makes a job's request
    # Class A by rule (Codex on #597): the recorded route must take it, as the EU route does.
    with sessions() as session:
        ctx = ScopeResolver(session).client_context(
            AuthenticatedPrincipal(user_id=world.lead_id, organization_id=world.organization_id),
            client_id=world.client_id,
        )
        ClientKnowledgeRepository(session).add(
            ctx, kind=KnowledgeKind.FACT, title="Fiktivní fakt", summary="Ráno se pije káva."
        )
        session.commit()
    study = f"{API}/studies/{world.study_id}"
    revision = _save(api, study, DESIGN)
    made = api.post(
        f"{study}/design/revisions",
        json={"content": DESIGN, "source_stage": "questionnaire", "workspace_revision": revision},
    )
    assert made.status_code in (200, 201), made.text
    base = made.json()["revision_id"]
    started = api.post(
        f"{study}/research/agent-jobs",
        json={"design_revision_id": base, "action": "optimize_questionnaire"},
    )
    assert started.status_code == 201, started.text
    run_id = started.json()["run_id"]

    worker = _worker(
        sessions,
        database_url,
        workbench_registry_for(
            store=store,
            build=build,
            research_agent=recorded_research_agent(store=store, build=build),
        ),
    )
    while worker.run_once() is not None:
        pass
    job = api.get(f"{study}/research/agent-jobs/{run_id}").json()
    assert job["status"] == "COMPLETED", job
    result = api.get(f"{study}/research/agent-jobs/{run_id}/result").json()
    assert result["result"]["proposal"]["sections"], result

    with sessions() as session:
        ledger = AIUsageRepository(session, world.lead_scope(session)).events(run_id=run_id)
    answered = [e for e in ledger if e.outcome is UsageOutcome.SUCCEEDED]
    assert len(answered) == 1
    assert all(e.cost_usd == 0 for e in ledger)
    assert (answered[0].provider_request_id or "").startswith("recorded-")

    # The person rewrites the question the proposal also rewrites: its accept is refused by
    # name, never merged over the person's wording.
    question = {**DESIGN["sections"][0]["questions"][0], "text": "Kolik káv denně vypijete?"}
    moved = {**DESIGN, "sections": [{**DESIGN["sections"][0], "questions": [question]}]}
    now = _save(api, study, moved)
    refused = api.post(
        f"{study}/research/agent-jobs/{run_id}/accept",
        json={"expected_revision_id": base, "expected_workspace_revision": now},
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "stale_proposal"


def test_build_registry_answers_design_jobs_from_recordings_only_when_asked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setenv("AIA_ENV", "local")
    monkeypatch.setenv("AIA_STORAGE_BACKEND", "filesystem")
    monkeypatch.setenv("AIA_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("AIA_BEDROCK_MODEL_ID", "eu.anthropic.a-live-model")
    monkeypatch.delenv("AIA_AI_RESEARCH_AGENTS_ENABLED", raising=False)
    parked = workbench.build_registry()["research_agent"]
    monkeypatch.setenv("AIA_AI_RESEARCH_AGENTS_ENABLED", "true")
    recorded = workbench.build_registry()["research_agent"]
    assert getattr(parked, "_gateway", None) is None
    assert getattr(recorded, "_gateway", None) is not None
    assert workbench.RECORDED_RUNTIME["AIA_AI_RESEARCH_RESERVATION_USD"] == "0.01"
