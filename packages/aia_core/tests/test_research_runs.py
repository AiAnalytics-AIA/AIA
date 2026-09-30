"""Research runs (ADR 0016 decision 2): a Study's run over one Design Revision.

What is pinned here: the template is the reference's graph; a run is found only
through its own Study's design; starting is idempotent per revision; a retry is a
new run linked to the one it retries; and a fieldwork step with no AI runtime
parks, visibly, in a state no timer clears.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from aia_core.application.research import (
    ResearchAgentJobs,
    ResearchRunNotFound,
    ResearchRunNotRetryable,
    ResearchRuns,
)
from aia_core.application.workflows import start_workflow
from aia_core.domain.design import DESIGN_PROJECT_OWNER
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.pipeline import ProjectType
from aia_core.domain.research import ResearchPhase, phase_of, retryable
from aia_core.domain.research_agents import ResearchAction
from aia_core.domain.scope import ScopeDenied
from aia_core.domain.workflow import (
    RUNTIME_UNAVAILABLE_REASON,
    FailureClass,
    RecoveryAction,
    StepRunStatus,
    WorkflowRunStatus,
    decide_recovery,
    resume_due,
    validate_dag,
)
from aia_core.domain.workflow_templates import (
    DEVELOP_SNAPSHOT,
    RESEARCH,
    RESEARCH_KINDS,
    UnknownWorkflowType,
    steps_for_workflow,
)
from aia_core.infrastructure.repositories import ProjectNotFound, ProjectRepository
from aia_core.infrastructure.study_design_repository import (
    DesignRevisionNotFound,
    StudyDesignRepository,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository

DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 450,
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
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}
AI = FieldworkSource.AI_RUNTIME


@pytest.fixture
def runs(session: Any, scoped: Any) -> Any:
    """``runs(user=…, study=…)``: the research runs of a user's scope on a study."""
    return lambda **kw: ResearchRuns(session, scoped.scope(**kw))


@pytest.fixture
def design(session: Any, scoped: Any) -> Any:
    """``design(content, study=…)``: submit a design as the lead, return its revision id."""

    def submit(content: dict[str, Any] = DESIGN, *, study: str = "primary") -> str:
        user = "other_lead" if study == "other_client" else "lead"
        repo = StudyDesignRepository(session, scoped.scope(user=user, study=study))
        revision, _ = repo.submit(content=content, source_stage="run")
        return revision.revision_id

    return submit


# --------------------------------------------------------------------------- #
# The template
# --------------------------------------------------------------------------- #


def test_the_research_template_is_the_reference_graph() -> None:
    steps = steps_for_workflow(RESEARCH, project_type=ProjectType.RESEARCH)
    validate_dag(steps)
    graph = {s.node_key: (s.kind, s.stage_type, s.depends_on) for s in steps}
    assert graph == {
        "compile": ("research_compile", "BRIEF", ()),
        "preflight": ("research_preflight", "SAMPLE_PLAN", ("compile",)),
        "run": ("research_fieldwork", "FIELDWORK", ("preflight",)),
        "aggregate": ("research_aggregate", "AGGREGATION", ("run",)),
        "sociomap": ("research_sociomap", "ANALYSIS", ("run",)),
    }
    assert {s.kind for s in steps} == set(RESEARCH_KINDS.values())
    assert all(s.artifact_target == f"research_{s.node_key}" for s in steps)


def test_a_simulation_project_has_no_research_workflow() -> None:
    with pytest.raises(UnknownWorkflowType):
        steps_for_workflow(RESEARCH, project_type=ProjectType.SIMULATION)


# --------------------------------------------------------------------------- #
# The runtime park
# --------------------------------------------------------------------------- #


def test_no_runtime_parks_the_step_without_consuming_an_attempt() -> None:
    decision = decide_recovery(
        failure=FailureClass.RUNTIME_UNAVAILABLE,
        attempt_number=3,
        max_attempts=3,
        paid_call_dispatched=False,
        paid_call_outcome_known=True,
    )
    assert decision.action is RecoveryAction.PARK_PROVIDER
    assert decision.step_status is StepRunStatus.WAITING_PROVIDER
    assert decision.reason == RUNTIME_UNAVAILABLE_REASON
    assert decision.consumes_attempt is False
    assert decision.retry_after is None


def test_no_timer_resumes_a_step_waiting_for_the_runtime() -> None:
    long_ago = datetime.now(UTC) - timedelta(days=365)
    parked = {"runnable_after": long_ago, "parked_at": long_ago, "capacity_backoff_seconds": 0}
    assert not resume_due(
        StepRunStatus.WAITING_PROVIDER, waiting_reason=RUNTIME_UNAVAILABLE_REASON, **parked
    )
    # The same park for a quota does resume: only the reason differs.
    assert resume_due(
        StepRunStatus.WAITING_PROVIDER, waiting_reason="provider_quota_exhausted", **parked
    )


@pytest.mark.parametrize("status", list(WorkflowRunStatus))
def test_every_status_reads_as_exactly_one_phase(status: WorkflowRunStatus) -> None:
    phase = phase_of(status, attempted=True)
    expected = {
        WorkflowRunStatus.PENDING: ResearchPhase.RUNNING,
        WorkflowRunStatus.RUNNING: ResearchPhase.RUNNING,
        WorkflowRunStatus.COMPLETED: ResearchPhase.COMPLETED,
        WorkflowRunStatus.FAILED: ResearchPhase.FAILED,
        WorkflowRunStatus.CANCELLED: ResearchPhase.CANCELLED,
    }.get(status, ResearchPhase.WAITING)
    assert phase is expected
    assert retryable(status) is (phase in (ResearchPhase.FAILED, ResearchPhase.CANCELLED))


def test_a_run_no_worker_has_started_is_queued() -> None:
    for status in (WorkflowRunStatus.PENDING, WorkflowRunStatus.RUNNING):
        assert phase_of(status, attempted=False) is ResearchPhase.QUEUED


# --------------------------------------------------------------------------- #
# Starting, reading, cancelling, retrying
# --------------------------------------------------------------------------- #


def test_a_run_is_pinned_to_its_design_revision_and_starting_it_twice_is_one_run(
    runs: Any, design: Any
) -> None:
    first_revision = design()
    started = runs().start(design_revision_id=first_revision, fieldwork_source=AI)
    assert started.created
    again = runs().start(design_revision_id=first_revision, fieldwork_source=AI)
    assert not again.created and again.run_id == started.run_id

    run = runs().get(started.run_id)
    assert run["workflow_type"] == RESEARCH and run["project_revision"] == 1
    assert run["metadata"]["design_revision_id"] == first_revision
    assert run["metadata"]["fieldwork_source"] == "ai_runtime"
    assert run["phase"] is ResearchPhase.QUEUED and run["retryable"] is False
    by_node = {s["node_key"]: s for s in run["steps"]}
    assert by_node["compile"]["status"] is StepRunStatus.RUNNABLE
    assert by_node["run"]["status"] is StepRunStatus.BLOCKED

    # Editing the design is a new revision and a new run; the first run's revision is unchanged.
    second_revision = design({**DESIGN, "n": 500})
    second = runs().start(design_revision_id=second_revision, fieldwork_source=AI)
    assert second.created and runs().get(second.run_id)["project_revision"] == 2
    assert runs().get(started.run_id)["project_revision"] == 1
    assert [r["run_id"] for r in runs().runs()] == [second.run_id, started.run_id]


def test_analysis_graph_is_selected_by_composition_and_preserved_on_retry(
    runs: Any, design: Any, session: Any, scoped: Any
) -> None:
    revision = design()
    basic = runs().start(design_revision_id=revision, fieldwork_source=AI)
    analysed = runs().start(design_revision_id=revision, fieldwork_source=AI, analysis_enabled=True)
    assert analysed.created and analysed.run_id != basic.run_id
    assert (
        WorkflowRepository(session, scoped.scope()).find_run_by_idempotency_key(
            f"{RESEARCH}:{revision}"
        )
        is not None
    )
    assert [s["node_key"] for s in basic.run["steps"]] == [
        "compile",
        "preflight",
        "run",
        "aggregate",
        "sociomap",
    ]
    assert len(analysed.run["steps"]) == 13
    assert analysed.run["metadata"]["analysis_enabled"] is True
    WorkflowRepository(session, scoped.scope()).request_cancel(analysed.run_id, reason="test")
    retry = runs().retry(analysed.run_id, fieldwork_source=AI)
    assert retry.created and len(retry.run["steps"]) == 13
    assert retry.run["metadata"]["analysis_enabled"] is True


def test_starting_needs_run_rights_on_an_open_study(runs: Any, design: Any) -> None:
    revision = design()
    for user in ("viewer", "reviewer"):
        with pytest.raises(ScopeDenied) as denied:
            runs(user=user).start(design_revision_id=revision, fieldwork_source=AI)
        assert denied.value.reason == "insufficient_role"
    assert runs(user="researcher").start(design_revision_id=revision, fieldwork_source=AI).created


def test_a_run_and_its_revision_are_reachable_only_through_their_own_study(
    runs: Any, design: Any
) -> None:
    acme_revision = design()
    acme = runs().start(design_revision_id=acme_revision, fieldwork_source=AI).run_id
    # Each study has a design and a run of its own, so only the Study can refuse Acme's ids.
    sibling_revision = design({**DESIGN, "n": 21}, study="sibling")
    runs(study="sibling").start(design_revision_id=sibling_revision, fieldwork_source=AI)
    globex_revision = design(study="other_client")
    globex = runs(user="other_lead", study="other_client")
    globex.start(design_revision_id=globex_revision, fieldwork_source=AI)

    for other in (runs(study="sibling"), globex):
        with pytest.raises(ResearchRunNotFound):
            other.get(acme)
        with pytest.raises(ResearchRunNotFound):
            other.events(acme)
        with pytest.raises(ResearchRunNotFound):
            other.cancel(acme)
        with pytest.raises(DesignRevisionNotFound):
            other.start(design_revision_id=acme_revision, fieldwork_source=AI)
        assert acme not in [r["run_id"] for r in other.runs()]


def test_a_non_research_run_on_the_design_project_is_not_a_research_run(
    session: Any, scoped: Any, runs: Any, design: Any
) -> None:
    design()
    project_id = StudyDesignRepository(session, scoped.scope()).project_id()
    assert project_id is not None
    # An ordinary caller cannot run anything on the design project at all ...
    with pytest.raises(ProjectNotFound):
        start_workflow(
            session, scoped.scope(), project_id=project_id, workflow_type=DEVELOP_SNAPSHOT
        )
    # ... and a snapshot run on it by its owner is still not a research run.
    snapshot = start_workflow(
        session,
        scoped.scope(),
        project_id=project_id,
        workflow_type=DEVELOP_SNAPSHOT,
        owner=DESIGN_PROJECT_OWNER,
    )
    # A research workflow over some other project of the same Study is not the Study's research.
    stray, _ = ProjectRepository(session, scoped.scope()).create(
        title="Stray", project_type=ProjectType.RESEARCH, content=DESIGN
    )
    other = start_workflow(
        session, scoped.scope(), project_id=stray.project_id, workflow_type=RESEARCH
    )
    for run_id in (snapshot.run_id, other.run_id):
        with pytest.raises(ResearchRunNotFound):
            runs().get(run_id)
    assert runs().runs() == []


def test_a_study_with_no_design_has_no_runs(runs: Any) -> None:
    assert runs().runs() == []
    with pytest.raises(ResearchRunNotFound):
        runs().get("RUN-0")
    with pytest.raises(DesignRevisionNotFound):
        runs().start(design_revision_id="REV-0", fieldwork_source=AI)


def test_design_jobs_do_not_hide_fieldwork_when_the_list_is_limited(
    session: Any, scoped: Any, runs: Any, design: Any
) -> None:
    revision_id = design()
    fieldwork = runs().start(design_revision_id=revision_id, fieldwork_source=AI)
    jobs = ResearchAgentJobs(session, scoped.scope())
    first = jobs.start(design_revision_id=revision_id, action=ResearchAction.ANALYZE)
    second = jobs.start(design_revision_id=revision_id, action=ResearchAction.CRITIQUE)
    session.flush()

    assert [r["run_id"] for r in runs().runs(limit=1)] == [fieldwork.run_id]
    listed = jobs.jobs(limit=1)
    assert len(listed) == 1
    assert listed[0]["run_id"] in {first.run_id, second.run_id}


def test_only_a_failed_or_cancelled_run_is_retried_and_a_retry_is_a_linked_run(
    runs: Any, design: Any
) -> None:
    original = runs().start(design_revision_id=design(), fieldwork_source=AI).run_id
    with pytest.raises(ResearchRunNotRetryable) as refused:
        runs().retry(original, fieldwork_source=AI)
    assert refused.value.status is WorkflowRunStatus.RUNNING

    with pytest.raises(ScopeDenied):
        runs(user="viewer").cancel(original)
    assert runs().cancel(original) is WorkflowRunStatus.CANCELLED
    cancelled = runs().get(original)
    assert cancelled["phase"] is ResearchPhase.CANCELLED and cancelled["retryable"] is True

    retry = runs().retry(original, fieldwork_source=AI)
    assert retry.created and retry.run_id != original
    again = runs().retry(original, fieldwork_source=AI)
    assert not again.created and again.run_id == retry.run_id
    linked = runs().get(retry.run_id)
    assert linked["metadata"]["retry_of"] == original
    assert linked["metadata"]["design_revision_id"] == cancelled["metadata"]["design_revision_id"]


def test_fieldwork_without_a_runtime_parks_the_run_and_nothing_downstream_runs(
    session: Any, scoped: Any, runs: Any, design: Any
) -> None:
    """D1: a real run progresses honestly to fieldwork, then waits for the AI runtime."""
    run_id = runs().start(design_revision_id=design(), fieldwork_source=AI).run_id
    engine = WorkflowRepository(session, scoped.scope())
    assert [r["phase"] for r in runs().runs()] == [ResearchPhase.QUEUED]
    for kind in ("research_compile", "research_preflight"):
        work = engine.claim_next(worker_id="w", kinds={kind})
        assert work is not None and work.run_id == run_id
        engine.complete_attempt(work.attempt_id, worker_id="w", output={})
    assert runs().get(run_id)["phase"] is ResearchPhase.RUNNING
    assert [r["phase"] for r in runs().runs()] == [ResearchPhase.RUNNING]
    fieldwork = engine.claim_next(worker_id="w", kinds={"research_fieldwork"})
    assert fieldwork is not None and fieldwork.payload == {"fieldwork_source": "ai_runtime"}
    engine.fail_attempt(
        fieldwork.attempt_id,
        worker_id="w",
        failure=FailureClass.RUNTIME_UNAVAILABLE,
        error={"message": "The AI runtime is not deployed."},
    )

    run = runs().get(run_id)
    assert run["status"] is WorkflowRunStatus.WAITING_PROVIDER
    assert run["phase"] is ResearchPhase.WAITING and run["retryable"] is False
    by_node = {s["node_key"]: s for s in run["steps"]}
    assert by_node["run"]["status"] is StepRunStatus.WAITING_PROVIDER
    assert by_node["run"]["waiting_reason"] == RUNTIME_UNAVAILABLE_REASON
    assert by_node["run"]["attempts_consumed"] == 0
    for downstream in ("aggregate", "sociomap"):
        assert by_node[downstream]["status"] is StepRunStatus.BLOCKED
    # No sweep, however late, resumes it; and nothing is claimable.
    far = datetime.now(UTC) + timedelta(days=365)
    assert engine.resume_waiting_steps(now=far, capacity_backoff_seconds=0) == []
    assert engine.claim_next(worker_id="w") is None
