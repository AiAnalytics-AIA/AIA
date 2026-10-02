"""Research execution over HTTP (ADR 0016): Design Revisions, then the runs that execute them.

Every route is under the Study and resolves it first. The browser supplies the
design's content and nothing else: a revision or run of another Study, or of
another client, is a 404; a member without a grant on the client is a 404. Since
ADR 0019 every grant holds the one Researcher role, so there is no 403 left for a
missing permission inside a visible Study.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from aia_core.application.report import (
    INTERNAL_REPORT_ARTIFACT_TYPE,
    INTERNAL_REPORT_MEDIA_TYPE,
)
from aia_core.application.research import research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import ProjectRow, StudyRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Settings

API = "/api/v1"


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    """A file-backed SQLite database: these tests start a worker (AGENTS.md § SQLite).

    Its heartbeat thread would otherwise share in-memory SQLite's one connection
    and roll back a step's uncommitted artifact row mid-transaction.
    """
    if settings.database_url and ":memory:" not in settings.database_url:
        return settings
    return settings.model_copy(update={"database_url": f"sqlite+pysqlite:///{tmp_path / 'api.db'}"})


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


def submit(c: TestClient, world: Any, content: Any = None, study: str = "primary") -> Any:
    return c.post(
        f"{API}/studies/{world.study_id(study)}/design/revisions",
        json={"content": DESIGN if content is None else content, "source_stage": "run"},
    )


# --------------------------------------------------------------------------- #
# Design Revisions
# --------------------------------------------------------------------------- #


def test_a_design_becomes_an_immutable_revision_and_resubmitting_it_changes_nothing(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    first = submit(researcher, world)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["created"] is True and body["revision"] == 1
    assert body["study_id"] == world.study_id() and body["revision_id"].startswith("REV-")
    same = submit(researcher, world)
    assert same.status_code == 200 and same.json()["revision_id"] == body["revision_id"]
    edited = submit(researcher, world, {**DESIGN, "n": 500})
    assert edited.status_code == 201 and edited.json()["parent_revision"] == 1
    # Anyone who can see the Study reads its revisions; the content is exactly what ran.
    got = viewer.get(f"{API}/studies/{world.study_id()}/design/revisions/{body['revision_id']}")
    assert got.status_code == 200 and got.json()["content"] == DESIGN
    listed = viewer.get(f"{API}/studies/{world.study_id()}/design/revisions").json()["items"]
    assert [r["revision"] for r in listed] == [2, 1]


def test_every_member_may_submit_a_design_with_or_without_a_grant_and_bad_ones_422(
    viewer: TestClient,
    reviewer: TestClient,
    lead: TestClient,
    outsider: TestClient,
    world: Any,
) -> None:
    """ADR 0019: "viewer" and "reviewer" hold the Researcher role, so they may submit.

    So does a member who was never granted the Study; a design that carries scope is
    still refused.
    """
    for c in (viewer, reviewer, outsider):
        accepted = submit(c, world)
        assert accepted.status_code in (200, 201), accepted.text
    bad = submit(lead, world, {**DESIGN, "client_id": world.client_id("other")})
    assert bad.status_code == 422 and bad.json()["code"] == "design_carries_scope"
    assert submit(lead, world, []).status_code == 422
    extra = lead.post(
        f"{API}/studies/{world.study_id()}/design/revisions",
        json={"content": DESIGN, "source_stage": "run", "client_id": world.client_id()},
    )
    assert extra.status_code == 422


def test_a_design_never_crosses_studies(
    lead: TestClient, other_client_lead: TestClient, outsider: TestClient, world: Any
) -> None:
    acme = submit(lead, world).json()["revision_id"]
    # Each study has a design of its own, so only the Study filter can refuse Acme's id.
    assert submit(other_client_lead, world, study="other_client").status_code == 201
    assert submit(lead, world, {**DESIGN, "n": 21}, study="sibling").status_code == 201
    # Another client's lead may open Acme's study (ADR 0019), but Acme's revision id means
    # nothing in theirs.
    assert submit(other_client_lead, world).status_code in (200, 201)
    assert (
        other_client_lead.get(f"{API}/studies/{world.study_id()}/design/revisions").status_code
        == 200
    )
    assert (
        other_client_lead.get(
            f"{API}/studies/{world.study_id('other_client')}/design/revisions/{acme}"
        ).status_code
        == 404
    )
    # The sibling study of the same client does not have it either.
    assert (
        lead.get(f"{API}/studies/{world.study_id('sibling')}/design/revisions/{acme}").status_code
        == 404
    )
    assert outsider.get(f"{API}/studies/{world.study_id()}/design/revisions").status_code == 200
    # A malformed id is refused before any lookup.
    assert lead.get(f"{API}/studies/{world.study_id()}/design/revisions/PRJ-1").status_code == 422


def test_the_generic_project_routes_cannot_see_or_write_a_design(
    app: FastAPI, researcher: TestClient, lead: TestClient, world: Any, projects_url: Any
) -> None:
    """Regression (ADR 0016 decision 1): the design project was an ordinary project to /projects.

    A researcher could list it, PUT content that skipped validate_design (a
    ``client_id`` key became revision 2), and trash it while runs still started.
    """
    revision_id = submit(researcher, world).json()["revision_id"]
    assert researcher.get(projects_url()).json()["items"] == []
    listed = researcher.get(f"{API}/studies/{world.study_id()}/design/revisions").json()["items"]
    assert [r["revision_id"] for r in listed] == [revision_id]
    # The design project's id is never exposed; read it from the database, as an attacker
    # who guessed it would hold it, and try every write the generic routes offer.
    with create_session_factory(app.state.engine)() as session:
        design_project = session.scalars(select(ProjectRow.project_id)).one()
    base = f"{projects_url()}/{design_project}"
    assert researcher.get(base).status_code == 404
    put = researcher.put(f"{base}/content", json={"content": {**DESIGN, "client_id": "CLI-x"}})
    assert put.status_code == 404
    assert researcher.patch(base, json={"title": "renamed"}).status_code == 404
    assert lead.post(f"{base}/trash").status_code == 404
    runs = lead.post(f"{base}/runs", json={"workflow_type": "develop_snapshot"})
    assert runs.status_code == 404
    listed = researcher.get(f"{API}/studies/{world.study_id()}/design/revisions").json()["items"]
    assert [r["revision_id"] for r in listed] == [revision_id]


# --------------------------------------------------------------------------- #
# Research runs
# --------------------------------------------------------------------------- #


class _Stub:
    """Stands in for chunk 4's executors: succeed, or fail with one class."""

    def __init__(self, failure: FailureClass | None = None) -> None:
        self.failure = failure

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        if self.failure is None:
            return Succeeded()
        return Failed(self.failure, error={"message": "The AI runtime is not deployed."})


def _worker(app: FastAPI, fieldwork: FailureClass) -> Worker:
    settings = app.state.settings
    return Worker(
        session_factory=create_session_factory(app.state.engine),
        executors={
            "research_compile": _Stub(),
            "research_preflight": _Stub(),
            "research_fieldwork": _Stub(fieldwork),
        },
        settings=WorkerSettings(
            database_url=settings.database_url or "sqlite+pysqlite:///:memory:",
            executors="aia_executors.registry:build_registry",
            worker_id="research-test-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
        ),
    )


def _runs(world: Any, study: str = "primary") -> str:
    return f"{API}/studies/{world.study_id(study)}/research/runs"


def start(c: TestClient, world: Any, revision_id: str, study: str = "primary") -> Any:
    return c.post(_runs(world, study), json={"design_revision_id": revision_id})


def test_a_run_starts_once_per_design_revision_and_is_read_by_its_study(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    revision_id = submit(researcher, world).json()["revision_id"]
    first = start(researcher, world, revision_id)
    assert first.status_code == 201, first.text
    run = first.json()
    assert first.headers["Location"] == f"{_runs(world)}/{run['run_id']}"
    assert run["study_id"] == world.study_id() and run["design_revision_id"] == revision_id
    assert run["design_revision"] == 1 and run["created"] is True
    assert run["phase"] == "QUEUED" and run["fieldwork_source"] == "ai_runtime"
    assert [s["node_key"] for s in run["steps"]] == [
        "compile",
        "preflight",
        "run",
        "aggregate",
        "sociomap",
    ]
    # The product surface names the Study and its design; never a project of any store.
    assert "project_id" not in run and all("project_id" not in s for s in run["steps"])
    again = start(researcher, world, revision_id)
    assert again.status_code == 200 and again.json()["run_id"] == run["run_id"]

    assert viewer.get(f"{_runs(world)}/{run['run_id']}").status_code == 200
    listed = viewer.get(_runs(world)).json()["items"]
    assert [r["run_id"] for r in listed] == [run["run_id"]]
    events = viewer.get(f"{_runs(world)}/{run['run_id']}/events").json()
    assert events[0]["event_type"] == "RUN_CREATED"


def test_analysis_results_are_study_scoped_and_internal(
    app: FastAPI,
    researcher: TestClient,
    viewer: TestClient,
    outsider: TestClient,
    other_client_lead: TestClient,
    world: Any,
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    response = start(researcher, world, revision)
    assert response.status_code == 201, response.text
    run = response.json()
    assert len(run["steps"]) == 14
    assert run["steps"][-1]["node_key"] == "report"
    url = f"{_runs(world)}/{run['run_id']}/analysis"
    internal = researcher.get(url)
    assert internal.status_code == 200, internal.text
    assert internal.json()["internal_only"] is True
    assert len(internal.json()["pending"]) == 8
    assert internal.json()["modules"] == {}
    # ADR 0019: the "viewer" label holds the Researcher role and reads it too.
    assert viewer.get(url).status_code == 200
    # So do a member with no grant and another client's lead (ADR 0019); what bounds it is the
    # study the path names.
    assert outsider.get(url).status_code == 200
    assert other_client_lead.get(url).status_code == 200
    wrong = f"{_runs(world, 'other_client')}/{run['run_id']}/analysis"
    assert other_client_lead.get(wrong).status_code == 404


def test_internal_report_is_listed_and_downloaded_only_through_its_study_run(
    app: FastAPI,
    researcher: TestClient,
    viewer: TestClient,
    outsider: TestClient,
    other_client_lead: TestClient,
    world: Any,
    damage_artifact: Any,
    artifact_status: Any,
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    url = f"{_runs(world)}/{run_id}/report"
    assert researcher.get(url).json()["state"] == "BLOCKED"
    assert researcher.get(f"{url}/download").status_code == 404

    document = b"PK\x03\x04internal-draft-test"
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        principal = AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        )
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        workflow = WorkflowRepository(session, scope)
        report_id = None
        for _ in range(14):
            work = workflow.claim_next(worker_id="report-fixture")
            assert work is not None
            output = {}
            if work.node_key == "report":
                artifact, _ = research_artifacts(session, scope, app.state.artifact_store).put(
                    project_id=work.project_id,
                    revision=work.project_revision,
                    stage_type="REPORT",
                    artifact_type=INTERNAL_REPORT_ARTIFACT_TYPE,
                    data=document,
                    content_type=INTERNAL_REPORT_MEDIA_TYPE,
                    input_fingerprint="report-route-test",
                    produced_by_job_id=work.attempt_id,
                    metadata={
                        "run_id": run_id,
                        "report_kind": "internal",
                        "review_state": "DRAFT_UNAPPROVED",
                        "synthetic": True,
                    },
                )
                report_id = artifact.artifact_id
                output = {"artifact_id": report_id}
            workflow.complete_attempt(work.attempt_id, worker_id="report-fixture", output=output)
        session.commit()
    assert report_id is not None

    listed = viewer.get(url)
    assert listed.status_code == 200, listed.text
    assert listed.json()["artifact_id"] == report_id
    assert listed.json()["review_state"] == "DRAFT_UNAPPROVED"
    assert listed.json()["synthetic"] is True
    downloaded = researcher.get(f"{url}/download")
    assert downloaded.status_code == 200 and downloaded.content == document
    assert downloaded.headers["content-type"] == INTERNAL_REPORT_MEDIA_TYPE
    assert "internal-draft.docx" in downloaded.headers["content-disposition"]
    assert downloaded.headers["cache-control"] == "no-store"
    assert outsider.get(url).status_code == 200  # ADR 0019: a member with no grant reads it too
    assert outsider.get(f"{url}/download").status_code == 200
    other_url = f"{_runs(world, 'other_client')}/{run_id}/report"
    assert other_client_lead.get(other_url).status_code == 404
    assert other_client_lead.get(f"{other_url}/download").status_code == 404
    damage_artifact(report_id, "tampered")
    damaged = researcher.get(f"{url}/download")
    assert damaged.status_code == 409 and damaged.json()["code"] == "artifact_corrupt"
    assert artifact_status(report_id) == "CORRUPT"


def test_starting_needs_a_revision_of_this_study_not_a_grant(
    researcher: TestClient,
    viewer: TestClient,
    reviewer: TestClient,
    outsider: TestClient,
    other_client_lead: TestClient,
    world: Any,
) -> None:
    """ADR 0019: every member may start; the boundary is the Study the revision belongs to."""
    revision_id = submit(researcher, world).json()["revision_id"]
    for c in (outsider, viewer, reviewer):
        started = start(c, world, revision_id)
        assert started.status_code in (200, 201), started.text
    # The browser cannot choose how fieldwork is done.
    extra = researcher.post(
        _runs(world),
        json={"design_revision_id": revision_id, "fieldwork_source": "synthetic_fixture"},
    )
    assert extra.status_code == 422
    assert start(researcher, world, "REV-0").status_code == 404
    assert start(researcher, world, "PRJ-1").status_code == 422
    # Another client's lead, in their own study, cannot run Acme's revision.
    submit(other_client_lead, world, study="other_client")
    assert start(other_client_lead, world, revision_id, study="other_client").status_code == 404
    # Through Acme's own study they may run Acme's revision (ADR 0019); the same run, so 200.
    assert start(other_client_lead, world, revision_id).status_code in (200, 201)


def test_a_run_never_crosses_studies(
    lead: TestClient, other_client_lead: TestClient, outsider: TestClient, world: Any
) -> None:
    acme = start(lead, world, submit(lead, world).json()["revision_id"]).json()["run_id"]
    sibling_rev = submit(lead, world, {**DESIGN, "n": 21}, study="sibling").json()["revision_id"]
    assert start(lead, world, sibling_rev, study="sibling").status_code == 201
    globex_rev = submit(other_client_lead, world, study="other_client").json()["revision_id"]
    assert start(other_client_lead, world, globex_rev, study="other_client").status_code == 201

    for c, study in ((lead, "sibling"), (other_client_lead, "other_client")):
        base = _runs(world, study)
        for path in ("", "/events"):
            assert c.get(f"{base}/{acme}{path}").status_code == 404
        for action in ("cancel", "retry"):
            assert c.post(f"{base}/{acme}/{action}").status_code == 404
        assert acme not in [r["run_id"] for r in c.get(base).json()["items"]]
    # Through its own study's path any member reads the run (ADR 0019).
    assert other_client_lead.get(f"{_runs(world)}/{acme}").status_code == 200
    assert outsider.get(_runs(world)).status_code == 200
    assert lead.get(f"{_runs(world)}/PRJ-1").status_code == 422


def test_fieldwork_without_the_ai_runtime_waits_visibly_and_nothing_downstream_runs(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """D1: a real run progresses honestly to fieldwork, then parks; no result is shown."""
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    worker = _worker(app, FailureClass.RUNTIME_UNAVAILABLE)
    endings = [worker.run_once() for _ in range(4)]
    assert [e.ending if e else None for e in endings] == ["completed", "completed", "failed", None]

    run = researcher.get(f"{_runs(world)}/{run_id}").json()
    assert run["status"] == "WAITING_PROVIDER" and run["phase"] == "WAITING"
    assert run["needs_attention"] is False and run["retryable"] is False
    steps = {s["node_key"]: s for s in run["steps"]}
    assert steps["compile"]["status"] == steps["preflight"]["status"] == "SUCCEEDED"
    assert steps["run"]["status"] == "WAITING_PROVIDER"
    assert steps["run"]["waiting_reason"] == "ai_runtime_unavailable"
    assert steps["run"]["failure_class"] == "RUNTIME_UNAVAILABLE"
    assert steps["aggregate"]["status"] == steps["sociomap"]["status"] == "BLOCKED"
    assert run["artifact_ids"] == []
    # Waiting is not failure: it cannot be retried into a second run that waits for the same thing.
    refused = researcher.post(f"{_runs(world)}/{run_id}/retry")
    assert refused.status_code == 409 and refused.json()["code"] == "run_not_retryable"


def test_a_failed_run_is_retried_as_a_new_run_linked_to_it(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    worker = _worker(app, FailureClass.PERMISSION)
    while worker.run_once() is not None:
        pass
    failed = researcher.get(f"{_runs(world)}/{run_id}").json()
    assert failed["phase"] == "FAILED" and failed["retryable"] is True
    # ADR 0019: any member may retry, one who was never granted the study included. The retry is
    # one new run, so whoever retries first gets 201 and the next gets the same run back.
    retry = outsider.post(f"{_runs(world)}/{run_id}/retry")
    assert retry.status_code == 201, retry.text
    body = retry.json()
    assert body["run_id"] != run_id and body["retry_of"] == run_id
    assert body["design_revision_id"] == failed["design_revision_id"]
    again = researcher.post(f"{_runs(world)}/{run_id}/retry")
    assert again.status_code == 200 and again.json()["run_id"] == body["run_id"]


def test_any_member_may_cancel_a_run_with_or_without_a_grant(
    researcher: TestClient, viewer: TestClient, outsider: TestClient, world: Any
) -> None:
    """ADR 0019: cancelling is no longer withheld from the "viewer" label."""
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    # Under another study's path the run is not there to cancel, whoever asks.
    wrong = f"{_runs(world, 'sibling')}/{run_id}/cancel"
    assert outsider.post(wrong).status_code == 404
    assert researcher.get(f"{_runs(world)}/{run_id}").json()["phase"] != "CANCELLED"
    cancelled = outsider.post(f"{_runs(world)}/{run_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["phase"] == "CANCELLED" and cancelled.json()["retryable"] is True
    assert viewer.post(f"{_runs(world)}/{run_id}/cancel").status_code == 200  # already cancelled


def test_cost_is_shown_to_every_member(
    researcher: TestClient, viewer: TestClient, outsider: TestClient, world: Any
) -> None:
    """ADR 0019: the Researcher role holds VIEW_COSTS, so the "viewer" label sees cost too."""
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    assert researcher.get(f"{_runs(world)}/{run_id}").json()["actual_cost_usd"] == 0.0
    assert viewer.get(f"{_runs(world)}/{run_id}").json()["actual_cost_usd"] == 0.0
    # The list summaries carry no steps, so no cost for anyone (routers/research.py:355);
    # what changed is only that the viewer label no longer differs from the researcher.
    listed = viewer.get(_runs(world)).json()["items"]
    assert listed and [r["actual_cost_usd"] for r in listed] == [
        r["actual_cost_usd"] for r in researcher.get(_runs(world)).json()["items"]
    ]
    assert outsider.get(f"{_runs(world)}/{run_id}").json()["actual_cost_usd"] == 0.0
    assert outsider.get(_runs(world)).status_code == 200


def test_a_run_serves_only_the_artifacts_it_produced(researcher: TestClient, world: Any) -> None:
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    base = f"{_runs(world)}/{run_id}/artifacts"
    assert researcher.get(f"{base}/ART-0000000000abcd").status_code == 404
    assert researcher.get(f"{_runs(world)}/RUN-0000000000abcd/artifacts/ART-1").status_code == 404
    assert researcher.get(f"{base}/REV-1").status_code == 422


# --------------------------------------------------------------------------- #
# Readiness, and artifacts read only through their run (chunk 4)
# --------------------------------------------------------------------------- #


def _real_worker(app: FastAPI, *, workbench: bool) -> Worker:
    """A worker over the app's database and store, running the real research executors."""
    from aia_core.infrastructure.build_identity import BuildIdentity
    from aia_executors import workbench as wb
    from aia_executors.registry import registry_for

    build = BuildIdentity(sha="a15be650937aacaa")
    store = app.state.artifact_store
    executors = (
        wb.workbench_registry_for(store=store, build=build)
        if workbench
        else registry_for(store=store, build=build)
    )
    settings = app.state.settings
    return Worker(
        session_factory=create_session_factory(app.state.engine),
        executors=executors,
        settings=WorkerSettings(
            database_url=settings.database_url or "sqlite+pysqlite:///:memory:",
            executors="aia_executors.registry:build_registry",
            worker_id="research-api-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
        ),
    )


def test_readiness_says_what_would_stop_a_run_before_anything_starts(
    researcher: TestClient, viewer: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    revision_id = submit(researcher, world).json()["revision_id"]
    url = f"{API}/studies/{world.study_id()}/research/readiness"
    ready = viewer.get(url, params={"design_revision_id": revision_id})
    assert ready.status_code == 200, ready.text
    body = ready.json()
    assert body["ready"] is True and body["rules"] == "aia-structural-readiness-1"
    assert (body["questions"], body["batteries"], body["objects"], body["n"]) == (2, 1, 5, 450)
    assert body["fieldwork_source"] == "ai_runtime"

    filtered = {**DESIGN, "sections": [dict(DESIGN["sections"][0]), DESIGN["sections"][1]]}
    filtered["sections"][0]["questions"] = [
        *DESIGN["sections"][0]["questions"],
        {"id": "q3", "text": "Proč?", "typ": "otevrena", "filtr": "q2 == 'Nic'"},
    ]
    not_ready = submit(researcher, world, filtered).json()["revision_id"]
    body = viewer.get(url, params={"design_revision_id": not_ready}).json()
    assert body["ready"] is False
    assert any(c["id"] == "conditional_questions" and c["status"] == "FAIL" for c in body["checks"])
    refused = start(researcher, world, not_ready)
    assert refused.status_code == 409 and refused.json()["code"] == "design_not_ready"
    assert refused.json()["details"]["failed"][0]["id"] == "conditional_questions"
    # Another client's lead may read this Study's readiness (ADR 0019), but cannot ask about its
    # revision through their own study.
    assert other_client_lead.get(url, params={"design_revision_id": revision_id}).status_code == 200
    other = f"{API}/studies/{world.study_id('other_client')}/research/readiness"
    submit(other_client_lead, world, study="other_client")
    assert (
        other_client_lead.get(other, params={"design_revision_id": revision_id}).status_code == 404
    )


def test_research_artifacts_are_read_only_through_the_run_that_produced_them(
    app: FastAPI,
    researcher: TestClient,
    viewer: TestClient,
    outsider: TestClient,
    world: Any,
    projects_url: Any,
) -> None:
    """Regression (ADR 0016 chunk 4): the generic artifact route served them.

    It checked only that the artifact's project was the Study's, so the design
    project's id and a research artifact id reached any artifact of the research,
    past the run it belonged to and past the rule that keeps respondent rows out
    of the browser.
    """
    # The test/workbench composition: this API records the fictional source on its runs.
    app.state.settings = app.state.settings.model_copy(
        update={"research_fieldwork_source": FieldworkSource.SYNTHETIC_FIXTURE}
    )
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    worker = _real_worker(app, workbench=True)
    while worker.run_once() is not None:
        pass
    run = researcher.get(f"{_runs(world)}/{run_id}").json()
    steps = {s["node_key"]: s for s in run["steps"]}
    assert steps["run"]["data_origin"] == "SYNTHETIC_FIXTURE"
    spec_id, dataset_id = steps["compile"]["artifact_id"], steps["run"]["artifact_id"]

    spec = researcher.get(f"{_runs(world)}/{run_id}/artifacts/{spec_id}")
    assert spec.status_code == 200 and spec.json()["payload"]["specification"]["n"] == 450
    dataset = researcher.get(f"{_runs(world)}/{run_id}/artifacts/{dataset_id}")
    assert dataset.status_code == 200
    assert dataset.json()["payload"] is None, "respondent rows are never inlined"

    # The full fictional chain completed: aggregate, and an INTERNAL_ONLY Sociomap.
    assert run["status"] == "COMPLETED" and run["phase"] == "COMPLETED"
    aggregate_id, sociomap_id = steps["aggregate"]["artifact_id"], steps["sociomap"]["artifact_id"]
    aggregate = viewer.get(f"{_runs(world)}/{run_id}/artifacts/{aggregate_id}")
    assert aggregate.status_code == 200
    assert aggregate.json()["payload"]["aggregate"]["data_origin"] == "SYNTHETIC_FIXTURE"
    sociomap = researcher.get(f"{_runs(world)}/{run_id}/artifacts/{sociomap_id}")
    assert sociomap.status_code == 200
    assert sociomap.json()["payload"]["sociomap"]["methodology_status"] == "INTERNAL_ONLY"
    # INTERNAL_ONLY while D6 is open. ADR 0019: every member is a Researcher and reads it
    # (the payload above still says INTERNAL_ONLY), a member who was never granted the study
    # included; respondent rows are still never inlined for anyone.
    internal = viewer.get(f"{_runs(world)}/{run_id}/artifacts/{sociomap_id}")
    assert internal.status_code == 200
    assert internal.json()["payload"]["sociomap"]["methodology_status"] == "INTERNAL_ONLY"
    for artifact_id in (spec_id, dataset_id, aggregate_id, sociomap_id):
        read = outsider.get(f"{_runs(world)}/{run_id}/artifacts/{artifact_id}")
        assert read.status_code == 200
        if artifact_id == dataset_id:
            assert read.json()["payload"] is None

    with create_session_factory(app.state.engine)() as session:
        design_project = session.scalars(select(ProjectRow.project_id)).one()
    for artifact_id in (spec_id, dataset_id, aggregate_id, sociomap_id):
        generic = researcher.get(f"{projects_url()}/{design_project}/artifacts/{artifact_id}")
        assert generic.status_code == 404


@pytest.mark.parametrize("damage", ["tampered", "missing"])
def test_a_corrupt_research_artifact_stays_marked_corrupt_after_the_409(
    app: FastAPI,
    researcher: TestClient,
    world: Any,
    damage_artifact: Any,
    artifact_status: Any,
    damage: str,
) -> None:
    """Regression, the research twin: the 409's rollback took the CORRUPT mark with it."""
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    compiled = _real_worker(app, workbench=False).run_once()
    assert compiled is not None and compiled.ending == "completed"
    steps = {s["node_key"]: s for s in researcher.get(f"{_runs(world)}/{run_id}").json()["steps"]}
    spec_id = steps["compile"]["artifact_id"]
    damage_artifact(spec_id, damage)

    url = f"{_runs(world)}/{run_id}/artifacts/{spec_id}"
    refused = researcher.get(url)
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "artifact_corrupt"
    assert artifact_status(spec_id) == "CORRUPT"
    assert researcher.get(url).status_code == 409


# --------------------------------------------------------------------------- #
# Lifting a budget wait (plan 5b.1)
# --------------------------------------------------------------------------- #


def _park_first_step_on_budget(app: FastAPI, world: Any, who: str = "researcher") -> str:
    """Claim the run's first step as a worker would, and stop it at the budget cap."""
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        principal = AuthenticatedPrincipal(
            user_id=world.users[who], organization_id=world.organization_id
        )
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        workflow = WorkflowRepository(session, scope)
        claimed = workflow.claim_next(worker_id="budget-fixture")
        assert claimed is not None
        workflow.fail_attempt(
            claimed.attempt_id, worker_id="budget-fixture", failure=FailureClass.BUDGET_EXCEEDED
        )
        session.commit()
        return str(claimed.node_key)


def _study_budget(app: FastAPI, world: Any) -> float:
    with create_session_factory(app.state.engine)() as session:
        return float(
            session.scalar(select(StudyRow.budget_usd).where(StudyRow.study_id == world.study_id()))
        )


def test_a_budget_wait_is_lifted_through_its_study_run_and_the_run_goes_on(
    app: FastAPI, researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    """The dead end: the Progress page explained the wait and offered no way out."""
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    node = _park_first_step_on_budget(app, world)
    before = _study_budget(app, world)
    waiting = researcher.get(f"{_runs(world)}/{run_id}").json()
    assert waiting["phase"] == "WAITING"
    assert next(s for s in waiting["steps"] if s["node_key"] == node)["status"] == "AWAITING_BUDGET"

    url = f"{_runs(world)}/{run_id}/steps/{node}/budget"
    lifted = viewer.post(url, json={"budget_usd": before + 250.0, "note": "Klient souhlasil"})
    assert lifted.status_code == 200, lifted.text
    body = lifted.json()
    assert body["phase"] != "WAITING"
    assert next(s for s in body["steps"] if s["node_key"] == node)["status"] == "RUNNABLE"
    assert _study_budget(app, world) == before + 250.0

    # A second lift finds nothing waiting; it neither errors the run nor moves the budget.
    again = researcher.post(url, json={"budget_usd": before + 900.0})
    assert again.status_code == 409 and again.json()["code"] == "not_waiting_for_budget"
    assert _study_budget(app, world) == before + 250.0


def test_a_budget_lift_that_is_refused_changes_nothing(
    app: FastAPI, researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    node = _park_first_step_on_budget(app, world)
    before = _study_budget(app, world)
    url = f"{_runs(world)}/{run_id}/steps/{node}/budget"

    lower = researcher.post(url, json={"budget_usd": before - 1.0})
    assert lower.status_code == 422 and lower.json()["code"] == "budget_not_raised"
    unknown = researcher.post(
        f"{_runs(world)}/{run_id}/steps/nope/budget", json={"budget_usd": before + 1.0}
    )
    assert unknown.status_code == 404
    # Under another study's path the run is not there to lift, whoever asks.
    elsewhere = other_client_lead.post(
        f"{_runs(world, 'other_client')}/{run_id}/steps/{node}/budget",
        json={"budget_usd": before + 1.0},
    )
    assert elsewhere.status_code == 404
    for body in ({}, {"budget_usd": -5.0}, {"budget_usd": 10.0, "extra": 1}):
        assert researcher.post(url, json=body).status_code == 422
    assert _study_budget(app, world) == before
    step = next(
        s
        for s in researcher.get(f"{_runs(world)}/{run_id}").json()["steps"]
        if s["node_key"] == node
    )
    assert step["status"] == "AWAITING_BUDGET"


def test_lifting_a_budget_wait_needs_a_signed_in_member(client: TestClient, world: Any) -> None:
    url = f"{_runs(world)}/RUN-0a1b2c/steps/run/budget"
    assert client.post(url, json={"budget_usd": 10.0}).status_code == 401
