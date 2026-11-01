"""The native agent boundary enqueues only: no model work in HTTP."""

from pathlib import Path
from typing import Any

import pytest
from aia_core.application.research import research_artifacts
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aia_api.config import Settings


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    """A file-backed SQLite database: one test here starts a worker (AGENTS.md § SQLite)."""
    if settings.database_url and ":memory:" not in settings.database_url:
        return settings
    return settings.model_copy(update={"database_url": f"sqlite+pysqlite:///{tmp_path / 'api.db'}"})


def base(world: Any, study: str = "primary") -> str:
    return f"/api/v1/studies/{world.study_id(study)}/research/agent-jobs"


def revision(client: TestClient, world: Any) -> str:
    response = world.design(
        client, {"title": "Fictional", "goal": "Test concept"}, source_stage="brief"
    )
    assert response.status_code == 201
    return str(response.json()["revision_id"])


def test_native_job_start_is_idempotent_and_returns_only_public_state(
    researcher: TestClient,
    viewer: TestClient,
    outsider: TestClient,
    world: Any,
) -> None:
    """ADR 0019: the "viewer" label holds the Researcher role, so it may start the same job.

    So does a member who was never granted the study. The boundary that remains is the
    study the path names: the job is not found under another study's path.
    """
    rid = revision(researcher, world)
    body = {"design_revision_id": rid, "action": "analyze_brief"}
    started = researcher.post(base(world), json=body)
    assert started.status_code == 201, started.text
    job = started.json()
    assert job["status"] == "RUNNING" and job["context_sha256"]
    assert "snapshot" not in job and "metadata" not in job
    repeated = researcher.post(base(world), json=body)
    assert repeated.status_code == 200 and repeated.json()["run_id"] == job["run_id"]
    assert viewer.post(base(world), json=body).status_code == 200
    assert outsider.post(base(world), json=body).status_code == 200  # idempotent: the same job
    assert outsider.get(f"{base(world)}/{job['run_id']}").json()["run_id"] == job["run_id"]
    read = viewer.get(f"{base(world)}/{job['run_id']}")
    # ADR 0019: costs are no longer hidden from the "viewer" label; it reads what a
    # researcher reads (nothing is spent yet).
    assert read.status_code == 200 and read.json()["actual_cost_usd"] == 0
    assert researcher.get(f"{base(world)}/{job['run_id']}").json()["actual_cost_usd"] == 0
    assert researcher.get(base(world)).json()[0]["run_id"] == job["run_id"]
    assert researcher.get(f"{base(world, 'sibling')}/{job['run_id']}").status_code == 404
    assert researcher.get(f"{base(world)}/{job['run_id']}/result").status_code == 409


def test_agent_api_rejects_authority_and_unimplemented_actions(
    researcher: TestClient,
    world: Any,
) -> None:
    rid = revision(researcher, world)
    for extra in ({"provider": "anthropic"}, {"client_id": "different"}, {"model": "unreviewed"}):
        r = researcher.post(
            base(world), json={"design_revision_id": rid, "action": "analyze_brief", **extra}
        )
        assert r.status_code == 422
    assert (
        researcher.post(
            base(world), json={"design_revision_id": rid, "action": "web_research"}
        ).status_code
        == 422
    )


def test_cancel_is_scoped_to_its_study_and_any_member_may_cancel(
    researcher: TestClient,
    viewer: TestClient,
    outsider: TestClient,
    other_client_lead: TestClient,
    world: Any,
) -> None:
    """ADR 0019: the "viewer" label holds every permission, cancel included."""
    rid = revision(researcher, world)
    job = researcher.post(
        base(world), json={"design_revision_id": rid, "action": "analyze_brief"}
    ).json()
    url = f"{base(world)}/{job['run_id']}/cancel"
    # Under another study's path the job is not there to cancel, whoever asks (ADR 0019).
    for member in (outsider, other_client_lead):
        for study in ("sibling", "other_client"):
            wrong = f"{base(world, study)}/{job['run_id']}/cancel"
            assert member.post(wrong).status_code == 404, (study, wrong)
    assert researcher.get(f"{base(world)}/{job['run_id']}").json()["status"] == "RUNNING"
    cancelled = viewer.post(url)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    assert researcher.get(f"{base(world)}/{job['run_id']}").json()["status"] == "CANCELLED"


class _Proposes:
    """Stands in for the model: stores the proposal artifact the real executor would."""

    def __init__(self, store: ArtifactStore) -> None:
        self._store = store

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        with context.transaction() as (session, _):
            artifact, _created = research_artifacts(session, context.scope, self._store).put_json(
                payload={"result": {"project": {"title": "Proposed"}}, "provenance": {}},
                project_id=step.project_id,
                revision=step.project_revision,
                stage_type=step.stage_type,
                artifact_type="research_agent_proposal",
            )
        return Succeeded(output={"artifact_id": artifact.artifact_id})


def _worker(app: FastAPI, executor: Any = None) -> Worker:
    settings = app.state.settings
    return Worker(
        session_factory=create_session_factory(app.state.engine),
        executors={"research_agent": executor or _Proposes(app.state.artifact_store)},
        settings=WorkerSettings(
            database_url=settings.database_url or "sqlite+pysqlite:///:memory:",
            executors="aia_executors.registry:build_registry",
            worker_id="agent-jobs-test-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
        ),
    )


class _Unavailable:
    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        return Failed(FailureClass.RUNTIME_UNAVAILABLE, error={"message": "runtime is off"})


def test_same_design_can_resume_an_unbilled_runtime_park_after_activation(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    rid = revision(researcher, world)
    url = base(world)
    job_id = researcher.post(
        url, json={"design_revision_id": rid, "action": "analyze_brief"}
    ).json()["run_id"]
    assert _worker(app, _Unavailable()).run_once() is not None
    parked = researcher.get(f"{url}/{job_id}").json()
    assert parked["status"] == "WAITING_PROVIDER"
    assert parked["steps"][0]["waiting_reason"] == "ai_runtime_unavailable"
    assert parked["actual_cost_usd"] == 0
    # ADR 0019: any member may resume, one who was never granted the study included; the job is
    # not found under another study's path.
    assert outsider.post(f"{url}/{job_id}/resume").status_code == 200
    assert researcher.post(f"{base(world, 'sibling')}/{job_id}/resume").status_code == 404

    resumed = researcher.post(f"{url}/{job_id}/resume")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["run_id"] == job_id
    assert resumed.json()["steps"][0]["status"] == "RUNNABLE"
    assert researcher.post(f"{url}/{job_id}/resume").status_code == 200
    assert _worker(app).run_once() is not None
    assert researcher.get(f"{url}/{job_id}").json()["status"] == "COMPLETED"
    assert researcher.post(f"{url}/{job_id}/resume").status_code == 409


class _OverBudget:
    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        return Failed(FailureClass.BUDGET_EXCEEDED, error={"message": "over the study's budget"})


def _budget(app: FastAPI, world: Any) -> float:
    from aia_core.infrastructure.tables import StudyRow
    from sqlalchemy import select

    with create_session_factory(app.state.engine)() as session:
        return float(
            session.scalar(select(StudyRow.budget_usd).where(StudyRow.study_id == world.study_id()))
        )


def test_a_job_stopped_at_the_budget_cap_goes_on_when_a_person_lifts_it(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """PC4: only a research run's step could be lifted. A job stopped at the cap waited until
    cancelled, and asking the same action again returned the same waiting job."""
    rid = revision(researcher, world)
    url = base(world)
    job_id = researcher.post(
        url, json={"design_revision_id": rid, "action": "analyze_brief"}
    ).json()["run_id"]
    assert _worker(app, _OverBudget()).run_once() is not None
    waiting = researcher.get(f"{url}/{job_id}").json()
    assert waiting["steps"][0]["status"] == "AWAITING_BUDGET"
    before = _budget(app, world)

    lower = researcher.post(f"{url}/{job_id}/budget", json={"budget_usd": before - 1.0})
    assert lower.status_code == 422 and lower.json()["code"] == "budget_not_raised"
    elsewhere = researcher.post(
        f"{base(world, 'sibling')}/{job_id}/budget", json={"budget_usd": before + 5.0}
    )
    assert elsewhere.status_code == 404
    assert _budget(app, world) == before

    lifted = researcher.post(
        f"{url}/{job_id}/budget", json={"budget_usd": before + 5.0, "note": "Schváleno"}
    )
    assert lifted.status_code == 200, lifted.text
    assert lifted.json()["run_id"] == job_id
    assert lifted.json()["steps"][0]["status"] == "RUNNABLE"
    assert _budget(app, world) == before + 5.0
    again = researcher.post(f"{url}/{job_id}/budget", json={"budget_usd": before + 9.0})
    assert again.status_code == 409 and again.json()["code"] == "not_waiting_for_budget"

    assert _worker(app).run_once() is not None
    assert researcher.get(f"{url}/{job_id}").json()["status"] == "COMPLETED"


class _Refused:
    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        return Failed(FailureClass.PERMISSION, error={"message": "refused"})


def test_asking_again_after_a_job_ended_without_a_proposal_starts_a_new_round(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """PC13: the same ask on the same design was the same job in any state, so a cancelled or
    failed job answered every later ask and the stage could only repeat its error."""
    rid = revision(researcher, world)
    url = base(world)
    ask = {"design_revision_id": rid, "action": "analyze_brief"}
    first = researcher.post(url, json=ask).json()["run_id"]
    # Still queued: asked again, it is followed, nothing new.
    assert researcher.post(url, json=ask).json()["run_id"] == first

    researcher.post(f"{url}/{first}/cancel")
    assert researcher.get(f"{url}/{first}").json()["status"] == "CANCELLED"
    again = researcher.post(url, json=ask)
    assert again.status_code == 201, again.text
    second = again.json()["run_id"]
    assert second != first
    assert researcher.post(url, json=ask).json()["run_id"] == second

    assert _worker(app, _Refused()).run_once() is not None
    assert researcher.get(f"{url}/{second}").json()["status"] == "FAILED"
    third = researcher.post(url, json=ask)
    assert third.status_code == 201 and third.json()["run_id"] not in (first, second)
    assert _worker(app).run_once() is not None
    assert researcher.get(f"{url}/{third.json()['run_id']}").json()["status"] == "COMPLETED"
    # Done: asked again, the proposal is followed, never paid for twice.
    assert researcher.post(url, json=ask).json()["run_id"] == third.json()["run_id"]


def _recovering(app: FastAPI, run_id: str, *, uncertain: bool) -> None:
    """The job's step stopped for recovery; ``uncertain``: a paid call's outcome unknown."""
    from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
    from aia_core.infrastructure.tables import StepAttemptRow, StepRunRow, WorkflowRunRow
    from sqlalchemy import select

    with create_session_factory(app.state.engine)() as session:
        step = session.scalars(select(StepRunRow).where(StepRunRow.run_id == run_id)).one()
        step.status = StepRunStatus.RECOVERY_REQUIRED.value
        run = session.get(WorkflowRunRow, run_id)
        assert run is not None
        run.status = WorkflowRunStatus.RECOVERY_REQUIRED.value
        session.add(
            StepAttemptRow(
                attempt_id=f"ATT-{run_id[-12:]}",
                step_id=step.step_id,
                attempt_number=1,
                status="FAILED",
                paid_call_dispatched=uncertain,
                paid_call_outcome_known=False,
            )
        )
        session.commit()


def test_a_job_stopped_with_a_paid_call_of_unknown_outcome_is_never_asked_again(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """The OI-121 rule: a call that may have been billed is settled by an operator first."""
    rid = revision(researcher, world)
    url = base(world)
    ask = {"design_revision_id": rid, "action": "critique_design"}
    first = researcher.post(url, json=ask).json()["run_id"]
    _recovering(app, first, uncertain=True)
    assert researcher.post(url, json=ask).json()["run_id"] == first
    other = {"design_revision_id": rid, "action": "analyze_brief"}
    known = researcher.post(url, json=other).json()["run_id"]
    _recovering(app, known, uncertain=False)
    restarted = researcher.post(url, json=other)
    assert restarted.status_code == 201 and restarted.json()["run_id"] != known


class _Reports(_Proposes):
    """Reports progress as the real executor does, then proposes."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.progress("Připravený kontext; AI zpracovává návrh", action="analyze_brief")
        return super().execute(step, context)


def test_the_job_feed_says_what_its_step_reported_after_a_cursor_and_only_under_its_study(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    rid = revision(researcher, world)
    url = base(world)
    job_id = researcher.post(
        url, json={"design_revision_id": rid, "action": "analyze_brief"}
    ).json()["run_id"]
    assert _worker(app, _Reports(app.state.artifact_store)).run_once() is not None

    feed = researcher.get(f"{url}/{job_id}/events")
    assert feed.status_code == 200, feed.text
    events = feed.json()
    progress = [e for e in events if e["event_type"] == "STEP_PROGRESS"]
    assert [(e["message"], e["payload"]) for e in progress] == [
        ("Připravený kontext; AI zpracovává návrh", {"action": "analyze_brief"})
    ]
    assert progress[0]["attempt_id"]
    # The event names the step the job lists, by the id the job's step carries.
    steps = researcher.get(f"{url}/{job_id}").json()["steps"]
    assert progress[0]["step_id"] == steps[0]["step_id"]
    ids = [e["event_id"] for e in events]
    assert ids == sorted(ids)
    # After a cursor, only what came later.
    later = researcher.get(f"{url}/{job_id}/events", params={"since": progress[0]["event_id"]})
    assert [e["event_id"] for e in later.json()] == [i for i in ids if i > progress[0]["event_id"]]
    # Found only under its own study's path; any member may read it there (ADR 0019).
    assert outsider.get(f"{url}/{job_id}/events").status_code == 200
    assert researcher.get(f"{base(world, 'sibling')}/{job_id}/events").status_code == 404
    assert researcher.get(f"{url}/RUN-0000000000000000/events").status_code == 404


@pytest.mark.parametrize("damage", ["tampered", "missing"])
def test_a_corrupt_proposal_is_a_409_and_stays_marked_corrupt(
    app: FastAPI,
    researcher: TestClient,
    world: Any,
    damage_artifact: Any,
    artifact_status: Any,
    damage: str,
) -> None:
    """Regression: a proposal whose bytes failed verification answered 500.

    The storage error escaped the route's error mapping, so the caller got
    ``internal_error`` and ``get_session`` rolled the CORRUPT mark back with it.
    """
    rid = revision(researcher, world)
    job = researcher.post(
        base(world), json={"design_revision_id": rid, "action": "analyze_brief"}
    ).json()
    done = _worker(app).run_once()
    assert done is not None and done.ending == "completed"
    url = f"{base(world)}/{job['run_id']}"
    assert researcher.get(f"{url}/result").status_code == 200
    (step,) = researcher.get(url).json()["steps"]
    damage_artifact(step["artifact_id"], damage)

    refused = researcher.get(f"{url}/result")
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "artifact_corrupt"
    assert artifact_status(step["artifact_id"]) == "CORRUPT"
    accepted = researcher.post(
        f"{url}/accept", json={"expected_revision_id": rid, "expected_workspace_revision": 1}
    )
    assert accepted.status_code == 409 and accepted.json()["code"] == "artifact_corrupt"


# -- dismiss, rebuild and the pending-proposals projection (ADR 0026 decisions 5 and 8) ---------


def _decisions(app: FastAPI, run_id: str) -> list[str]:
    from aia_core.infrastructure.tables import ApprovalDecisionRow
    from sqlalchemy import select

    with create_session_factory(app.state.engine)() as session:
        return list(
            session.scalars(
                select(ApprovalDecisionRow.decision)
                .where(
                    ApprovalDecisionRow.subject_type == "ai_proposal",
                    ApprovalDecisionRow.subject_id == run_id,
                )
                .order_by(ApprovalDecisionRow.decision_id)
            )
        )


def test_a_proposal_is_dismissed_in_the_ledger_and_rebuilt_as_a_new_job(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    rid = revision(researcher, world)
    url = base(world)
    asked = {"design_revision_id": rid, "action": "analyze_brief", "instruction": "Zkrátit"}
    first = researcher.post(url, json=asked).json()["run_id"]
    # Not yet a proposal: nothing to decide, and nothing pending.
    assert researcher.get(f"{url}/{first}").json()["proposal_state"] is None
    refused = researcher.post(f"{url}/{first}/dismiss")
    assert refused.status_code == 409 and refused.json()["code"] == "proposal_not_ready"
    assert _worker(app).run_once() is not None
    assert researcher.get(f"{url}/{first}").json()["proposal_state"] == "pending"
    assert [j["run_id"] for j in researcher.get(url, params={"pending": "true"}).json()] == [first]

    # Dismissed: one ledger row, nothing written to the design, and no longer pending.
    dismissed = researcher.post(f"{url}/{first}/dismiss")
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["proposal_state"] == "dismissed"
    assert researcher.post(f"{url}/{first}/dismiss").status_code == 200  # recorded once
    assert _decisions(app, first) == ["dismiss"]
    designs = researcher.get(f"/api/v1/studies/{world.study_id()}/design/revisions").json()
    assert [r["revision_id"] for r in designs["items"]] == [rid]
    assert researcher.get(url, params={"pending": "true"}).json() == []

    # Rebuilt: the same action and instruction, on the newest design, naming the old job.
    stale = researcher.post(f"{url}/{first}/rebuild", json={"design_revision_id": "REV-0"})
    assert stale.status_code == 409 and stale.json()["code"] == "stale_design"  # not the newest
    second = researcher.post(f"{url}/{first}/rebuild", json={"design_revision_id": rid})
    assert second.status_code == 201, second.text
    rebuilt = second.json()
    assert rebuilt["run_id"] != first and rebuilt["rebuild_of"] == first
    assert rebuilt["action"] == "analyze_brief" and rebuilt["proposal_state"] is None
    assert _worker(app).run_once() is not None
    listed = {j["run_id"]: j["proposal_state"] for j in researcher.get(url).json()}
    # A dismissal stands over the rebuild; the new proposal waits for a person.
    assert listed == {first: "dismissed", rebuilt["run_id"]: "pending"}

    # A third job, rebuilt before anyone decided it, is superseded.
    third = researcher.post(url, json={**asked, "instruction": "Jinak"}).json()["run_id"]
    assert _worker(app).run_once() is not None
    fourth = researcher.post(f"{url}/{third}/rebuild", json={"design_revision_id": rid}).json()
    assert researcher.get(f"{url}/{third}").json()["proposal_state"] == "superseded"
    assert fourth["rebuild_of"] == third

    # A newer design: a rebuild on the old one is refused, never run on a design not current.
    newer = world.design(
        researcher, {"title": "Fictional", "goal": "Changed"}, source_stage="brief"
    )
    assert newer.status_code == 201
    old = researcher.post(f"{url}/{third}/rebuild", json={"design_revision_id": rid})
    assert old.status_code == 409 and old.json()["code"] == "stale_design"


def test_a_pending_proposal_older_than_the_newest_page_is_still_listed_as_pending(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    # The listing's page is the newest 20 jobs; ``pending=true`` must not filter that page.
    rid = revision(researcher, world)
    url = base(world)
    asked = {"design_revision_id": rid, "action": "analyze_brief"}
    oldest = researcher.post(url, json={**asked, "instruction": "První"}).json()["run_id"]
    assert _worker(app).run_once() is not None
    for n in range(20):
        made = researcher.post(url, json={**asked, "instruction": f"Další {n}"})
        assert made.status_code == 201, made.text
    assert oldest not in [j["run_id"] for j in researcher.get(url).json()]
    pending = researcher.get(url, params={"pending": "true"}).json()
    assert [j["run_id"] for j in pending] == [oldest]
    assert pending[0]["proposal_state"] == "pending"


def test_a_questionnaire_job_reads_external_context_only_with_the_analysis_switch_on(
    researcher: TestClient, world: Any, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """QST13: AIA_AI_ANALYSIS_EXTERNAL_CONTEXT gives a job's start the store it reads the newest
    Design Research bundle from; off, no store and no external layer."""
    from aia_core.application.research import ResearchAgentJobs

    given: list[object] = []

    def external(self: ResearchAgentJobs, snapshot: Any, store: object) -> Any:
        given.append(store)
        return snapshot

    monkeypatch.setattr(ResearchAgentJobs, "_with_external", external)
    rid = revision(researcher, world)
    body = {"design_revision_id": rid, "action": "build_questionnaire"}
    assert researcher.post(base(world), json=body).status_code == 201
    assert given == []
    monkeypatch.setattr(
        app.state,
        "settings",
        app.state.settings.model_copy(update={"ai_analysis_external_context": True}),
    )
    assert researcher.post(base(world), json={**body, "instruction": "Kratší"}).status_code == 201
    assert len(given) == 1 and given[0] is not None
