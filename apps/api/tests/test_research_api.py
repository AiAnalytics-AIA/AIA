"""Research execution over HTTP (ADR 0016): Design Revisions, then the runs that execute them.

Every route is under the Study and resolves it first. The browser supplies the
design's content and nothing else: a revision or run of another Study, or of
another client, is a 404; a missing permission inside a visible Study is a 403.
"""

from __future__ import annotations

from typing import Any

from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import ProjectRow
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

API = "/api/v1"

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


def test_submitting_needs_edit_rights_and_says_why_it_refuses(
    viewer: TestClient, reviewer: TestClient, lead: TestClient, world: Any
) -> None:
    for c in (viewer, reviewer):
        refused = submit(c, world)
        assert refused.status_code == 403 and refused.json()["code"] == "insufficient_role"
    bad = submit(lead, world, {**DESIGN, "client_id": world.client_id("other")})
    assert bad.status_code == 422 and bad.json()["code"] == "design_carries_scope"
    assert submit(lead, world, []).status_code == 422
    extra = lead.post(
        f"{API}/studies/{world.study_id()}/design/revisions",
        json={"content": DESIGN, "source_stage": "run", "client_id": world.client_id()},
    )
    assert extra.status_code == 422


def test_a_design_never_crosses_studies_or_clients(
    lead: TestClient, other_client_lead: TestClient, outsider: TestClient, world: Any
) -> None:
    acme = submit(lead, world).json()["revision_id"]
    # Each study has a design of its own, so only the Study filter can refuse Acme's id.
    assert submit(other_client_lead, world, study="other_client").status_code == 201
    assert submit(lead, world, {**DESIGN, "n": 21}, study="sibling").status_code == 201
    # Another client's lead: Acme's study is invisible; Acme's revision id means nothing in theirs.
    assert submit(other_client_lead, world).status_code == 404
    assert (
        other_client_lead.get(f"{API}/studies/{world.study_id()}/design/revisions").status_code
        == 404
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
    assert outsider.get(f"{API}/studies/{world.study_id()}/design/revisions").status_code == 404
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


def test_starting_needs_run_rights_and_a_revision_of_this_study(
    researcher: TestClient,
    viewer: TestClient,
    reviewer: TestClient,
    other_client_lead: TestClient,
    world: Any,
) -> None:
    revision_id = submit(researcher, world).json()["revision_id"]
    for c in (viewer, reviewer):
        refused = start(c, world, revision_id)
        assert refused.status_code == 403 and refused.json()["code"] == "insufficient_role"
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
    assert start(other_client_lead, world, revision_id).status_code == 404


def test_a_run_never_crosses_studies_or_clients(
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
    assert other_client_lead.get(f"{_runs(world)}/{acme}").status_code == 404
    assert outsider.get(_runs(world)).status_code == 404
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
    app: FastAPI, researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    worker = _worker(app, FailureClass.PERMISSION)
    while worker.run_once() is not None:
        pass
    failed = researcher.get(f"{_runs(world)}/{run_id}").json()
    assert failed["phase"] == "FAILED" and failed["retryable"] is True
    assert viewer.post(f"{_runs(world)}/{run_id}/retry").status_code == 403

    retry = researcher.post(f"{_runs(world)}/{run_id}/retry")
    assert retry.status_code == 201, retry.text
    body = retry.json()
    assert body["run_id"] != run_id and body["retry_of"] == run_id
    assert body["design_revision_id"] == failed["design_revision_id"]
    again = researcher.post(f"{_runs(world)}/{run_id}/retry")
    assert again.status_code == 200 and again.json()["run_id"] == body["run_id"]


def test_cancelling_needs_cancel_rights_and_ends_the_run(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    refused = viewer.post(f"{_runs(world)}/{run_id}/cancel")
    assert refused.status_code == 403 and refused.json()["code"] == "insufficient_role"
    cancelled = researcher.post(f"{_runs(world)}/{run_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["phase"] == "CANCELLED" and cancelled.json()["retryable"] is True


def test_cost_is_shown_only_to_those_who_may_see_costs(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    assert researcher.get(f"{_runs(world)}/{run_id}").json()["actual_cost_usd"] == 0.0
    assert viewer.get(f"{_runs(world)}/{run_id}").json()["actual_cost_usd"] is None
    assert all(r["actual_cost_usd"] is None for r in viewer.get(_runs(world)).json()["items"])


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
    # Another client's lead cannot read this Study's readiness, nor ask about its revision.
    assert other_client_lead.get(url, params={"design_revision_id": revision_id}).status_code == 404
    other = f"{API}/studies/{world.study_id('other_client')}/research/readiness"
    submit(other_client_lead, world, study="other_client")
    assert (
        other_client_lead.get(other, params={"design_revision_id": revision_id}).status_code == 404
    )


def test_research_artifacts_are_read_only_through_the_run_that_produced_them(
    app: FastAPI, researcher: TestClient, world: Any, projects_url: Any
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

    with create_session_factory(app.state.engine)() as session:
        design_project = session.scalars(select(ProjectRow.project_id)).one()
    for artifact_id in (spec_id, dataset_id):
        generic = researcher.get(f"{projects_url()}/{design_project}/artifacts/{artifact_id}")
        assert generic.status_code == 404
