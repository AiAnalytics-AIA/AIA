"""Research execution over HTTP (ADR 0016): Design Revisions, then the runs that execute them.

Every route is under the Study and resolves it first. The browser supplies the
design's content and nothing else: a revision or run of another Study, or of
another client, is a 404; a member without a grant on the client is a 404. Since
ADR 0019 every grant holds the one Researcher role, so there is no 403 left for a
missing permission inside a visible Study.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from aia_core.application.client_report import CLIENT_REPORT_ARTIFACT_TYPE
from aia_core.application.report import (
    INTERNAL_REPORT_ARTIFACT_TYPE,
    INTERNAL_REPORT_MEDIA_TYPE,
    INTERNAL_REPORT_PDF_ARTIFACT_TYPE,
)
from aia_core.application.report_export import REVIEW_STAMP_RECORD
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.application.sociomapping_report import SOCIOMAPPING_REPORT_ARTIFACT_TYPE
from aia_core.domain.evidence import ClaimSurface
from aia_core.domain.evidence.validation import METHOD_STATUS_PENDING
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.report.evidence import EvidenceLedger
from aia_core.domain.report.model import (
    Callout,
    CalloutKind,
    Classification,
    Paragraph,
    ReportDocument,
    ReportKind,
    ReportMeta,
    Section,
    text,
)
from aia_core.domain.respondent_behavior import AIA_RESPONSE_V1
from aia_core.domain.scope import StudyStatus
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import (
    ApprovalDecisionRow,
    ProjectArtifactRow,
    ProjectRow,
    StudyRow,
    WorkflowRunRow,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update

from aia_api.config import Settings
from aia_api.routers import research as research_router

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
    # Each step names the id its events carry, so a reader can tell which step said what.
    step_ids = {s["step_id"] for s in run["steps"]}
    assert len(step_ids) == len(run["steps"])
    named = {e["step_id"] for e in events if e["step_id"]}
    assert named <= step_ids


def test_a_listed_run_carries_its_steps_and_no_cost_it_cannot_know(
    researcher: TestClient, world: Any
) -> None:
    revision_id = submit(researcher, world).json()["revision_id"]
    run = start(researcher, world, revision_id).json()
    (listed,) = researcher.get(_runs(world)).json()["items"]
    # The screens read a run's state from its steps, so the listing carries them...
    assert [(s["node_key"], s["status"]) for s in listed["steps"]] == [
        (s["node_key"], s["status"]) for s in run["steps"]
    ]
    assert [s["step_id"] for s in listed["steps"]] == [s["step_id"] for s in run["steps"]]
    # ...without their attempt history: what it holds is absent, never made up.
    assert all(s["started_at"] is None and s["error_message"] is None for s in listed["steps"])
    full = researcher.get(f"{_runs(world)}/{run['run_id']}").json()
    assert full["actual_cost_usd"] is not None
    assert listed["actual_cost_usd"] is None


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
    # No module has read an aggregate yet, so none is said to depart from 18.6.6 (G3c).
    assert internal.json()["aggregation_deviation"] is None
    # ADR 0019: the "viewer" label holds the Researcher role and reads it too.
    assert viewer.get(url).status_code == 200
    # So do a member with no grant and another client's lead (ADR 0019); what bounds it is the
    # study the path names.
    assert outsider.get(url).status_code == 200
    assert other_client_lead.get(url).status_code == 200
    wrong = f"{_runs(world, 'other_client')}/{run['run_id']}/analysis"
    assert other_client_lead.get(wrong).status_code == 404


def _store_internal_report(
    app: FastAPI,
    world: Any,
    run_id: str,
    document: bytes,
    *,
    pdf: bytes | None = None,
    pdf_of: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Drive the run's steps to the end, the report step storing ``document`` as the
    researcher's internal report (and ``pdf`` as its rendering, of ``pdf_of`` when given),
    with ``metadata`` beside what it records; return its artifact id."""
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
                    input_fingerprint=f"report-route-test-{run_id}",
                    produced_by_job_id=work.attempt_id,
                    metadata={
                        "run_id": run_id,
                        "report_kind": "internal",
                        "review_state": "DRAFT_UNAPPROVED",
                        "synthetic": True,
                        **(metadata or {}),
                    },
                )
                report_id = artifact.artifact_id
                output = {"artifact_id": report_id}
                if pdf is not None:
                    rendering, _ = research_artifacts(session, scope, app.state.artifact_store).put(
                        project_id=work.project_id,
                        revision=work.project_revision,
                        stage_type="REPORT",
                        artifact_type=INTERNAL_REPORT_PDF_ARTIFACT_TYPE,
                        data=pdf,
                        content_type="application/pdf",
                        input_fingerprint=f"report-pdf-route-test-{run_id}",
                        metadata={"run_id": run_id, "rendering_of": pdf_of or report_id},
                        depends_on=[report_id],
                    )
                    output["pdf"] = {"state": "READY", "artifact_id": rendering.artifact_id}
            workflow.complete_attempt(work.attempt_id, worker_id="report-fixture", output=output)
        session.commit()
    assert report_id is not None
    return report_id


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
    report_id = _store_internal_report(app, world, run_id, document)

    listed = viewer.get(url)
    assert listed.status_code == 200, listed.text
    assert listed.json()["artifact_id"] == report_id
    assert listed.json()["review_state"] == "DRAFT_UNAPPROVED"
    # Stored without the record of the footer layout: once approved, served unstamped (D2).
    assert listed.json()["approved_on"] is None and listed.json()["stamped"] is False
    assert listed.json()["synthetic"] is True
    # Written before reports recorded data_origin: synthetic alone reads as simulated.
    assert listed.json()["data_origin_kind"] == "SIMULATED"
    assert listed.json()["modelled"] is False
    downloaded = researcher.get(f"{url}/download")
    assert downloaded.status_code == 200 and downloaded.content == document
    assert downloaded.headers["content-type"] == INTERNAL_REPORT_MEDIA_TYPE
    # Was "AIA-<study>-internal-draft.docx": the name now names the version and its review (D2).
    assert downloaded.headers["content-disposition"] == (
        f'attachment; filename="AIA-{world.study_id()}-{run_id}-zakladni-{report_id}-koncept.docx"'
    )
    assert downloaded.headers["cache-control"] == "no-store"
    # The draft these bytes are, so the page approves the one it downloaded.
    assert downloaded.headers["X-AIA-Artifact-Id"] == report_id
    assert downloaded.headers["X-AIA-Artifact-Sha256"] == hashlib.sha256(document).hexdigest()
    assert downloaded.headers["X-AIA-Review-State"] == "DRAFT_UNAPPROVED"
    assert outsider.get(url).status_code == 200  # ADR 0019: a member with no grant reads it too
    assert outsider.get(f"{url}/download").status_code == 200
    other_url = f"{_runs(world, 'other_client')}/{run_id}/report"
    assert other_client_lead.get(other_url).status_code == 404
    assert other_client_lead.get(f"{other_url}/download").status_code == 404
    damage_artifact(report_id, "tampered")
    damaged = researcher.get(f"{url}/download")
    assert damaged.status_code == 409 and damaged.json()["code"] == "artifact_corrupt"
    assert artifact_status(report_id) == "CORRUPT"


def test_the_reports_pdf_is_read_only_as_the_rendering_of_its_stored_docx(
    app: FastAPI, researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """Complete-study-report B3: the status says whether a PDF exists; the download serves it
    only through the run, and only as the rendering of that run's report."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    _store_internal_report(app, world, run_id, b"PK\x03\x04docx", pdf=b"%PDF-1.7 test")
    url = f"{_runs(world)}/{run_id}/report"
    status = researcher.get(url).json()
    assert status["pdf"]["state"] == "READY" and status["pdf"]["size_bytes"] == 13
    downloaded = researcher.get(f"{url}/pdf/download")
    assert downloaded.status_code == 200 and downloaded.content == b"%PDF-1.7 test"
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.headers["content-disposition"].endswith('-koncept.pdf"')
    foreign = f"{_runs(world, 'other_client')}/{run_id}/report/pdf/download"
    assert other_client_lead.get(foreign).status_code == 404


def test_a_report_without_a_pdf_says_it_can_be_asked_for_and_another_documents_is_refused(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    _store_internal_report(app, world, run_id, b"PK\x03\x04docx")
    url = f"{_runs(world)}/{run_id}/report"
    # The step rendered none (the converter was off): never asked for, and a person may ask.
    assert researcher.get(url).json()["pdf"] == {
        "state": "NOT_REQUESTED",
        "reason": None,
        "askable": True,
    }
    assert researcher.get(f"{url}/pdf/download").status_code == 404

    other_revision = submit(researcher, world, {**DESIGN, "title": "Jiná"}).json()["revision_id"]
    other_run = start(researcher, world, other_revision).json()["run_id"]
    _store_internal_report(
        app, world, other_run, b"PK\x03\x04other", pdf=b"%PDF x", pdf_of="ART-0000000000000000"
    )
    other_url = f"{_runs(world)}/{other_run}/report"
    # The report still reads; only its PDF is said to be unusable, and why, and it can be
    # rendered again from the report itself.
    assert researcher.get(other_url).json()["pdf"] == {
        "state": "INVALID",
        "reason": "pdf_not_this_report",
        "askable": True,
    }
    refused = researcher.get(f"{other_url}/pdf/download")
    assert refused.status_code == 409 and refused.json()["code"] == "report_artifact_invalid"


def test_a_step_pdf_gone_bad_or_missing_is_said_as_what_it_is(
    app: FastAPI, researcher: TestClient, world: Any, damage_artifact: Any
) -> None:
    """Review 2: a corrupt or deleted PDF the report step made read as "not this report's
    rendering", a different document, which told the reader the wrong cause."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    _store_internal_report(app, world, run_id, b"PK\x03\x04docx", pdf=b"%PDF-1.7 test")
    url = f"{_runs(world)}/{run_id}/report"
    pdf_id = researcher.get(url).json()["pdf"]["artifact_id"]
    damage_artifact(pdf_id, "tampered")
    assert researcher.get(f"{url}/pdf/download").status_code == 409  # the read marks it CORRUPT
    assert researcher.get(url).json()["pdf"] == {
        "state": "INVALID",
        "reason": "pdf_corrupt",
        "askable": True,
    }
    with create_session_factory(app.state.engine)() as session:
        session.execute(delete(ProjectArtifactRow).where(ProjectArtifactRow.artifact_id == pdf_id))
        session.commit()
    assert researcher.get(url).json()["pdf"]["reason"] == "pdf_missing"


def test_the_runs_own_report_gets_its_pdf_when_a_person_asks(
    app: FastAPI, researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """Review, 2026-10-16: a report whose step rendered no PDF (the converter was off) could
    never get one. Asking renders exactly its stored DOCX; a ready PDF is left as it is."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    docx_id = _store_internal_report(app, world, run_id, b"PK\x03\x04docx")
    url = f"{_runs(world)}/{run_id}/report"
    asked = researcher.post(f"{url}/pdf")
    assert asked.status_code == 200, asked.text
    assert asked.json()["pdf"]["state"] == "RENDERING"
    assert asked.json()["pdf"]["askable"] is False
    assert researcher.get(f"{url}/pdf/download").status_code == 404  # not rendered yet
    foreign = f"{_runs(world, 'other_client')}/{run_id}/report/pdf"
    assert other_client_lead.post(foreign).status_code == 404

    # The job renders it, as the worker's report_pdf step stores one: the status and the
    # download then read that rendering (review 2: nothing checked the fallback past RENDERING).
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        principal = AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        )
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        workflow = WorkflowRepository(session, scope)
        work = workflow.claim_next(worker_id="pdf-fixture")
        assert work is not None and work.node_key == "pdf"
        pdf, _ = research_artifacts(session, scope, app.state.artifact_store).put(
            project_id=work.project_id,
            revision=work.project_revision,
            stage_type="REPORT",
            artifact_type=INTERNAL_REPORT_PDF_ARTIFACT_TYPE,
            data=b"%PDF-1.7 asked",
            content_type="application/pdf",
            input_fingerprint=f"report-pdf-asked-{run_id}",
            metadata={"run_id": run_id, "rendering_of": docx_id},
            depends_on=[docx_id],
        )
        workflow.complete_attempt(
            work.attempt_id, worker_id="pdf-fixture", output={"artifact_id": pdf.artifact_id}
        )
        session.commit()
    ready = researcher.get(url).json()["pdf"]
    assert ready["state"] == "READY" and ready["artifact_id"] == pdf.artifact_id
    downloaded = researcher.get(f"{url}/pdf/download")
    assert downloaded.status_code == 200 and downloaded.content == b"%PDF-1.7 asked"
    assert downloaded.headers["X-AIA-Artifact-Id"] == docx_id
    # A ready PDF is left as it is: asking again starts nothing.
    with factory() as session:
        jobs = session.scalar(select(func.count()).select_from(WorkflowRunRow))
    assert researcher.post(f"{url}/pdf").json()["pdf"]["state"] == "READY"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(WorkflowRunRow)) == jobs


def test_a_run_without_modelled_data_has_no_client_report_and_says_why(
    app: FastAPI, researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """Complete-study-report B5c: the client report is refused by name (409), never printed
    with a caveat, and another client's study cannot reach the run at all."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    _store_internal_report(app, world, run_id, b"PK\x03\x04docx")
    url = f"{_runs(world)}/{run_id}/report/client/download"
    refused = researcher.get(url)
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "client_report_refused"
    foreign = f"{_runs(world, 'other_client')}/{run_id}/report/client/download"
    assert other_client_lead.get(foreign).status_code == 404


def test_the_sociomap_register_is_read_through_a_study(researcher: TestClient, world: Any) -> None:
    url = f"{API}/studies/{world.study_id()}/research/sociomap-register"
    (entry,) = researcher.get(url).json()["entries"]
    assert entry["method_id"] == "aia-sociomap-3" and entry["status"] == "CLIENT_FACING"
    assert entry["decided_on"] == "2026-10-13" and len(entry["spec_fingerprint"]) == 64


def test_a_person_approves_a_runs_stored_report_once_and_only_that(
    app: FastAPI,
    owner: TestClient,
    researcher: TestClient,
    outsider: TestClient,
    other_client_lead: TestClient,
    world: Any,
) -> None:
    """Complete-study-report B2: the approval is the ledger's, of a report of this run."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    report_id = _store_internal_report(app, world, run_id, b"PK\x03\x04approve-test")
    url = f"{_runs(world)}/{run_id}/report"
    approve = f"{url}/approve"

    # No such report in the study, and another client's study cannot see the run.
    unknown = researcher.post(approve, json={"artifact_id": "ART-0000000000000000"})
    assert unknown.status_code == 404
    foreign = f"{_runs(world, 'other_client')}/{run_id}/report/approve"
    assert other_client_lead.post(foreign, json={"artifact_id": report_id}).status_code == 404

    # Independent review turned on for this client: the producer may not clear it.
    forbid = owner.put(
        f"{API}/self-approval", json={"allowed": False, "client_id": world.client_id()}
    )
    assert forbid.status_code == 200, forbid.text
    own = researcher.post(approve, json={"artifact_id": report_id})
    assert own.status_code == 403 and own.json()["code"] == "separation_of_duties"
    assert researcher.get(url).json()["review_state"] == "DRAFT_UNAPPROVED"

    before = _prague_today()
    approved = outsider.post(approve, json={"artifact_id": report_id, "note": "Přečteno."})
    assert approved.status_code == 200, approved.text
    assert approved.json()["review_state"] == "APPROVED_INTERNAL"
    assert approved.json()["internal_only"] is True
    status_ = researcher.get(url).json()
    assert status_["review_state"] == "APPROVED_INTERNAL"
    assert status_["approved_on"] in {before, _prague_today()}
    # D2: approving asks for the approved version's PDF; its fictional bytes take no stamp.
    assert status_["pdf"]["state"] == "RENDERING" and status_["stamped"] is False
    again = outsider.post(approve, json={"artifact_id": report_id})
    assert again.status_code == 200

    factory = create_session_factory(app.state.engine)
    with factory() as session:
        decisions = session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_id == report_id)
        ).all()
    assert [(d.decision, d.comment) for d in decisions] == [("APPROVED", "Přečteno.")]


def _prague_today() -> str:
    return datetime.now(ZoneInfo("Europe/Prague")).date().isoformat()


_RENDERED: list[bytes] = []


def _rendered_report() -> bytes:
    """A real internal report as the renderer lays it out (its status in its footers only),
    rendered once: a stamp needs that layout, which fictional bytes do not have."""
    if not _RENDERED:
        meta = ReportMeta(
            ReportKind.INTERNAL,
            "Interní analytická zpráva",
            "Fiktivní data",
            "Fiktivní klient",
            "Fiktivní studie",
            "STU-1",
            date(2026, 10, 18),
            1,
            METHOD_STATUS_PENDING,
            classification=Classification.INTERNAL,
        )
        ledger = EvidenceLedger.from_claims([], surface=ClaimSurface.INTERNAL)
        section = Section("Shrnutí", (Paragraph(text("Fiktivní zpráva.")),))
        _RENDERED.append(DocxRenderer().render(ReportDocument(meta, (section,), ledger)))
    return _RENDERED[0]


def _footers(docx: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        return {n: z.read(n) for n in z.namelist() if n.startswith("word/footer")}


def _says_approved(footers: dict[str, bytes], status: str, version: str) -> bool:
    """Every footer says the version is approved and none that it is a draft: the cover, in its
    narrower status column, as two lines (the version id whole), every other one on one line."""
    one = f"{status} \u00b7 {version}".encode()
    two = f"{status}</w:t><w:br/><w:t>{version}".encode()
    return (
        sum(two in f for f in footers.values()) == 1
        and all(one in f or two in f for f in footers.values())
        and all(b"KONCEPT" not in f for f in footers.values())
    )


def _part(docx: bytes, name: str) -> bytes:
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        return z.read(name)


def test_a_draft_download_is_the_stored_bytes_and_names_their_sha(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    document = _rendered_report()
    report_id = _store_internal_report(
        app, world, run_id, document, metadata=dict(REVIEW_STAMP_RECORD)
    )
    url = f"{_runs(world)}/{run_id}/report"
    status_ = researcher.get(url).json()
    assert status_["review_state"] == "DRAFT_UNAPPROVED" and status_["approved_on"] is None
    assert status_["stamped"] is True  # once approved, its file will say so
    downloaded = researcher.get(f"{url}/download")
    assert downloaded.status_code == 200 and downloaded.content == document
    assert downloaded.headers["X-AIA-Artifact-Id"] == report_id
    assert downloaded.headers["X-AIA-Artifact-Sha256"] == hashlib.sha256(document).hexdigest()
    assert downloaded.headers["X-AIA-Review-State"] == "DRAFT_UNAPPROVED"
    assert all(b"KONCEPT" in f for f in _footers(downloaded.content).values())


def test_an_approved_versions_docx_says_approved_and_names_the_version(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    """Before D2, every download of an approved report printed "KONCEPT — NESCHVÁLENO" in
    every footer and on its cover under an APPROVED_INTERNAL header and a "draft" file name.
    The approved version's DOCX is its stored bytes with only the footers' status replaced."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    document = _rendered_report()
    report_id = _store_internal_report(
        app, world, run_id, document, metadata=dict(REVIEW_STAMP_RECORD)
    )
    url = f"{_runs(world)}/{run_id}/report"
    approved = outsider.post(f"{url}/approve", json={"artifact_id": report_id})
    assert approved.status_code == 200, approved.text
    approved_on = approved.json()["approved_on"]
    assert approved.json()["stamped"] is True
    downloaded = researcher.get(f"{url}/download")
    assert downloaded.status_code == 200
    # The stored version it is (its id and SHA-256), approved, in its name too.
    assert downloaded.headers["X-AIA-Artifact-Id"] == report_id
    assert downloaded.headers["X-AIA-Artifact-Sha256"] == hashlib.sha256(document).hexdigest()
    assert downloaded.headers["X-AIA-Review-State"] == "APPROVED_INTERNAL"
    assert downloaded.headers["content-disposition"].endswith(f'-{report_id}-schvaleno.docx"')
    year, month, day = (int(x) for x in approved_on.split("-"))
    status = f"SCHVÁLENO {day}.\u00a0{month}.\u00a0{year}"
    assert _says_approved(_footers(downloaded.content), status, f"verze {report_id}")
    # Everything else is the version a person approved, byte for byte.
    assert _part(downloaded.content, "word/document.xml") == _part(document, "word/document.xml")
    assert downloaded.content != document


def test_an_approved_version_never_serves_its_draft_pdf(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    report_id = _store_internal_report(
        app,
        world,
        run_id,
        _rendered_report(),
        pdf=b"%PDF-1.7 draft rendering",
        metadata=dict(REVIEW_STAMP_RECORD),
    )
    url = f"{_runs(world)}/{run_id}/report"
    assert researcher.get(f"{url}/pdf/download").content == b"%PDF-1.7 draft rendering"
    assert researcher.post(f"{url}/approve", json={"artifact_id": report_id}).status_code == 200
    # The step's PDF renders the draft: approved, the version's PDF is its approved rendering,
    # asked for by the approval and not made yet -- never the draft's instead.
    status_ = researcher.get(url).json()
    assert status_["pdf"]["state"] == "RENDERING"
    assert researcher.get(f"{url}/pdf/download").status_code == 404


def _close_study(app: FastAPI, world: Any) -> None:
    with create_session_factory(app.state.engine)() as session:
        scope = ScopeResolver(session).study_context(
            AuthenticatedPrincipal(
                user_id=world.users["researcher"], organization_id=world.organization_id
            ),
            study_id=world.study_id(),
        )
        ScopeRepository(session).set_study_status(scope, StudyStatus.DELIVERED)
        session.commit()


def test_a_draft_promises_an_approved_pdf_only_where_approving_makes_one(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    """Review 4 of D2: the card promised "DOCX i PDF" after approval from the PDF's reason
    alone, which a closed study's READY draft PDF and a deployment that rendered none do not
    give. The status says it: approving asks for a PDF, and this draft's own PDF was rendered
    here. Anything less is no promise."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    report_id = _store_internal_report(
        app,
        world,
        run_id,
        _rendered_report(),
        pdf=b"%PDF-1.7 draft rendering",
        metadata=dict(REVIEW_STAMP_RECORD),
    )
    url = f"{_runs(world)}/{run_id}/report"
    status_ = researcher.get(url).json()
    assert status_["pdf"]["state"] == "READY" and status_["approval_renders_pdf"] is True
    _close_study(app, world)
    status_ = researcher.get(url).json()
    # The draft's PDF is still READY, and no reason is given; a closed study asks for nothing.
    assert status_["pdf"]["state"] == "READY" and status_["pdf"].get("reason") is None
    assert status_["approval_renders_pdf"] is False
    assert outsider.post(f"{url}/approve", json={"artifact_id": report_id}).status_code == 200
    status_ = researcher.get(url).json()
    assert status_["pdf"]["state"] == "NOT_REQUESTED" and status_["pdf"]["reason"] == "study_closed"
    assert status_["approval_renders_pdf"] is False


def test_a_draft_whose_step_rendered_no_pdf_promises_none(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """A deployment without PDF (the code default): the step made none, nobody asked, and
    whether approving would make one is not known. Unknown is never a promise."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    _store_internal_report(
        app, world, run_id, _rendered_report(), metadata=dict(REVIEW_STAMP_RECORD)
    )
    status_ = researcher.get(f"{_runs(world)}/{run_id}/report").json()
    assert status_["pdf"] == {"state": "NOT_REQUESTED", "reason": None, "askable": True}
    assert status_["approval_renders_pdf"] is False


def test_the_approved_client_report_downloads_stamped_and_is_read_once(
    app: FastAPI,
    researcher: TestClient,
    outsider: TestClient,
    world: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review 4 of D2: the client report's approved download had no test of its own, and every
    download read the stored DOCX twice -- once to find it, again to export it. Its composition
    needs a population-grounded run (test_ai_fieldwork covers it); here the stored draft it finds
    is a real client report, stored the way it stores one."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    meta = ReportMeta(
        ReportKind.CLIENT,
        "Výzkumná zpráva",
        "Fiktivní data",
        "Fiktivní klient",
        "Fiktivní studie",
        "STU-1",
        date(2026, 10, 18),
        1,
        METHOD_STATUS_PENDING,
        classification=Classification.CLIENT_CONFIDENTIAL,
    )
    ledger = EvidenceLedger.from_claims([], surface=ClaimSurface.CLIENT_FACING)
    method = Callout(CalloutKind.METHOD, text("Fiktivní data."), title="Jak číst tuto zprávu")
    section = Section("Shrnutí", (method, Paragraph(text("Fiktivní zpráva pro klienta."))))
    document = DocxRenderer().render(ReportDocument(meta, (section,), ledger))
    principal = AuthenticatedPrincipal(
        user_id=world.users["researcher"], organization_id=world.organization_id
    )
    with create_session_factory(app.state.engine)() as session:
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        run = ResearchRuns(session, scope).get(run_id)
        stored, _ = research_artifacts(session, scope, app.state.artifact_store).put(
            project_id=run["project_id"],
            revision=int(run["project_revision"]),
            stage_type="REPORT",
            artifact_type=CLIENT_REPORT_ARTIFACT_TYPE,
            data=document,
            content_type=INTERNAL_REPORT_MEDIA_TYPE,
            input_fingerprint="fictional-client-report",
            metadata={
                "run_id": run_id,
                "report_kind": "client",
                "review_state": "DRAFT_UNAPPROVED",
                **REVIEW_STAMP_RECORD,
            },
        )
        session.commit()

    def found(session: Any, scope: Any, store: Any, *, run_id: str, build: str = "") -> Any:
        # stored_client_report's own path for a draft it finds: the artifact and its bytes, read.
        artifacts = research_artifacts(session, scope, store)
        return artifacts.get(stored.artifact_id), artifacts.read(stored.artifact_id)

    monkeypatch.setattr(research_router, "stored_client_report", found)
    reads: list[str] = []
    real_get = app.state.artifact_store.get

    def counted(key: str, **kw: Any) -> bytes:
        reads.append(key)
        return bytes(real_get(key, **kw))

    monkeypatch.setattr(app.state.artifact_store, "get", counted)
    url = f"{_runs(world)}/{run_id}/report"
    draft = researcher.get(f"{url}/client/download")
    assert draft.status_code == 200, draft.text
    assert draft.content == document and len(reads) == 1
    assert draft.headers["content-disposition"] == (
        f'attachment; filename="AIA-{world.study_id()}-{run_id}-klient-{stored.artifact_id}'
        '-koncept.docx"'
    )
    approved = outsider.post(f"{url}/approve", json={"artifact_id": stored.artifact_id})
    assert approved.status_code == 200, approved.text
    assert approved.json()["stamped"] is True
    reads.clear()
    downloaded = researcher.get(f"{url}/client/download")
    assert downloaded.status_code == 200 and len(reads) == 1
    assert downloaded.headers["X-AIA-Review-State"] == "APPROVED_INTERNAL"
    assert downloaded.headers["X-AIA-Artifact-Sha256"] == stored.sha256
    assert downloaded.headers["content-disposition"].endswith(
        f'-klient-{stored.artifact_id}-schvaleno.docx"'
    )
    year, month, day = (int(x) for x in approved.json()["approved_on"].split("-"))
    status = f"SCHVÁLENO {day}.\u00a0{month}.\u00a0{year}"
    assert _says_approved(_footers(downloaded.content), status, f"verze {stored.artifact_id}")
    assert _part(downloaded.content, "word/document.xml") == _part(document, "word/document.xml")


def test_an_older_version_approved_is_served_unstamped_and_says_so(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """A version stored before this layout (no record of it) is approved as it is: its DOCX is
    the stored bytes, never partly stamped, and the status says it is not stamped."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    document = _rendered_report()
    report_id = _store_internal_report(app, world, run_id, document)
    url = f"{_runs(world)}/{run_id}/report"
    assert researcher.post(f"{url}/approve", json={"artifact_id": report_id}).status_code == 200
    status_ = researcher.get(url).json()
    assert status_["review_state"] == "APPROVED_INTERNAL" and status_["stamped"] is False
    downloaded = researcher.get(f"{url}/download")
    assert downloaded.status_code == 200 and downloaded.content == document
    assert downloaded.headers["X-AIA-Review-State"] == "APPROVED_INTERNAL"


def test_an_approval_without_its_ledger_row_is_refused_by_name(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    report_id = _store_internal_report(
        app, world, run_id, _rendered_report(), metadata=dict(REVIEW_STAMP_RECORD)
    )
    with create_session_factory(app.state.engine)() as session:
        session.execute(
            update(ProjectArtifactRow)
            .where(ProjectArtifactRow.artifact_id == report_id)
            .values(is_approved=True)
        )
        session.commit()
    url = f"{_runs(world)}/{run_id}/report"
    for got in (researcher.get(url), researcher.get(f"{url}/download")):
        assert got.status_code == 409 and got.json()["code"] == "report_review_unrecorded"


def test_experimental_sociomapping_is_read_and_downloaded_only_through_its_run(
    app: FastAPI,
    researcher: TestClient,
    outsider: TestClient,
    other_client_lead: TestClient,
    world: Any,
) -> None:
    """Plan sociomapping-engine I3: the switch adds two steps; the result and its draft are
    read through the run, researchers only, and an artifact that does not say it is
    experimental is refused rather than served."""
    revision = submit(researcher, world).json()["revision_id"]
    plain = start(researcher, world, revision).json()
    assert [s["node_key"] for s in plain["steps"]][-1] == "sociomap"
    assert (
        researcher.get(f"{_runs(world)}/{plain['run_id']}/sociomapping/report").json()["state"]
        == "NOT_IN_RUN"
    )

    app.state.settings = app.state.settings.model_copy(
        update={"sociomapping_experimental_enabled": True}
    )
    run = start(researcher, world, revision).json()
    run_id = run["run_id"]
    assert run_id != plain["run_id"]  # a different graph is a different run
    assert [s["node_key"] for s in run["steps"]][-2:] == ["sociomapping", "sociomapping_report"]
    url = f"{_runs(world)}/{run_id}/sociomapping/report"
    status = researcher.get(url).json()
    assert status["method_status"] == "EXPERIMENTAL_AIA" and status["internal_only"] is True
    assert researcher.get(f"{url}/download").status_code == 404

    document = b"PK\x03\x04sociomapping-draft-test"
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        principal = AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        )
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        workflow = WorkflowRepository(session, scope)
        research = research_artifacts(session, scope, app.state.artifact_store)
        ids: dict[str, str] = {}
        while (work := workflow.claim_next(worker_id="sociomapping-fixture")) is not None:
            output: dict[str, Any] = {}
            if work.node_key == "sociomapping":
                artifact, _ = research.put_json(
                    payload={"kind": "research_sociomapping", "sociomapping": {"batteries": []}},
                    project_id=work.project_id,
                    revision=work.project_revision,
                    stage_type="ANALYSIS",
                    artifact_type="research_sociomapping",
                    input_fingerprint="sociomapping-route-test",
                    produced_by_job_id=work.attempt_id,
                    metadata={"run_id": run_id, "method_status": "EXPERIMENTAL_AIA"},
                )
                ids["result"] = artifact.artifact_id
                output = {"artifact_id": artifact.artifact_id}
            if work.node_key == "sociomapping_report":
                artifact, _ = research.put(
                    project_id=work.project_id,
                    revision=work.project_revision,
                    stage_type="REPORT",
                    artifact_type=SOCIOMAPPING_REPORT_ARTIFACT_TYPE,
                    data=document,
                    content_type=INTERNAL_REPORT_MEDIA_TYPE,
                    input_fingerprint="sociomapping-report-route-test",
                    produced_by_job_id=work.attempt_id,
                    metadata={
                        "run_id": run_id,
                        "report_kind": "internal",
                        "review_state": "DRAFT_UNAPPROVED",
                        "method_status": "EXPERIMENTAL_AIA",
                        "client_facing": False,
                        "synthetic": True,
                    },
                )
                ids["report"] = artifact.artifact_id
                output = {"artifact_id": artifact.artifact_id}
            workflow.complete_attempt(
                work.attempt_id, worker_id="sociomapping-fixture", output=output
            )
        session.commit()

    result = researcher.get(f"{_runs(world)}/{run_id}/artifacts/{ids['result']}")
    assert result.status_code == 200, result.text
    assert result.json()["payload"]["kind"] == "research_sociomapping"
    listed = researcher.get(url).json()
    assert listed["state"] == "READY" and listed["artifact_id"] == ids["report"]
    assert listed["review_state"] == "DRAFT_UNAPPROVED" and listed["synthetic"] is True
    downloaded = researcher.get(f"{url}/download")
    assert downloaded.status_code == 200 and downloaded.content == document
    assert downloaded.headers["content-type"] == INTERNAL_REPORT_MEDIA_TYPE
    assert "sociomapping-experimental-draft.docx" in downloaded.headers["content-disposition"]
    assert outsider.get(f"{url}/download").status_code == 200  # ADR 0019: any member
    other = f"{_runs(world, 'other_client')}/{run_id}/sociomapping/report"
    assert other_client_lead.get(f"{other}/download").status_code == 404

    # A draft whose metadata stopped saying it is experimental is not served.
    with factory() as session:
        row = session.get(ProjectArtifactRow, ids["report"])
        assert row is not None
        row.artifact_metadata = {**row.artifact_metadata, "client_facing": True}
        session.commit()
    refused = researcher.get(f"{url}/download")
    assert refused.status_code == 409 and refused.json()["code"] == "report_artifact_invalid"


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


def test_a_selected_population_that_is_not_the_clients_child_is_404_and_nothing_starts(
    researcher: TestClient, world: Any
) -> None:
    """P4e2: a run may name its client's child; any other id reads as not there."""
    revision_id = submit(researcher, world).json()["revision_id"]
    refused = researcher.post(
        _runs(world),
        json={"design_revision_id": revision_id, "population_version_id": "no-such-version"},
    )
    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "population_version_not_found"
    assert researcher.get(_runs(world)).json()["items"] == []


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


def test_retrying_analysis_says_why_a_run_has_nothing_to_ask_again(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """The route's refusals; the retry itself runs end to end in the executor suite
    (test_retrying_failed_modules_asks_only_them_over_the_same_data)."""
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    early = researcher.post(f"{_runs(world)}/{run_id}/analysis/retry")
    assert early.status_code == 409, early.text
    assert early.json()["code"] == "analysis_not_retryable"
    assert early.json()["details"]["reason"] == "run_not_finished"
    worker = _worker(app, FailureClass.PERMISSION)
    while worker.run_once() is not None:
        pass
    none = researcher.post(f"{_runs(world)}/{run_id}/analysis/retry")
    assert none.status_code == 409
    assert none.json()["details"]["reason"] == "analysis_not_in_run"
    assert "AI analýzu" in none.json()["message"]
    missing = researcher.post(f"{_runs(world)}/RUN-0000000000000000/analysis/retry")
    assert missing.status_code == 404
    retryable = researcher.get(f"{_runs(world)}/{run_id}/analysis/retryable")
    assert retryable.status_code == 200, retryable.text
    assert retryable.json() == {"run_id": run_id, "modules": []}
    assert (
        researcher.get(f"{_runs(world)}/RUN-0000000000000000/analysis/retryable").status_code == 404
    )


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


def test_readiness_forecasts_whether_a_runs_numbers_will_be_shown(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    """Plan run-recovery-and-truth 2a: 50 fictional respondents pass every structural check
    and still show nothing; readiness says so, as a warning, before anything is paid."""
    url = f"{API}/studies/{world.study_id()}/research/readiness"

    def forecast(n: int) -> Any:
        revision_id = submit(researcher, world, {**DESIGN, "n": n}).json()["revision_id"]
        body = viewer.get(url, params={"design_revision_id": revision_id}).json()
        return body, next(c for c in body["checks"] if c["id"] == "support_forecast")

    small, check = forecast(50)
    assert small["ready"] is True, "a forecast warns, it never refuses"
    assert check["status"] == "WARN" and "nevzniknou" in check["message"]
    _, enough = forecast(450)
    assert enough["status"] == "PASS"


def test_readiness_lists_every_question_with_whether_the_run_will_answer_it(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    """Plan run-recovery-and-truth 2b: each item, as the respondent reads it, with its
    verdict and the reasons; the support forecast decides the verdict of every one."""
    url = f"{API}/studies/{world.study_id()}/research/readiness"

    def outlook(n: int) -> list[dict[str, Any]]:
        revision_id = submit(researcher, world, {**DESIGN, "n": n}).json()["revision_id"]
        body = viewer.get(url, params={"design_revision_id": revision_id}).json()
        items: list[dict[str, Any]] = body["question_outlook"]
        assert len(items) == body["questions"] + body["objects"]
        return items

    small = outlook(50)
    assert {i["verdict"] for i in small} == {"UNANSWERABLE"}
    assert all("support_suppressed" in i["reasons"] for i in small)
    assert all(i["text"] for i in small)
    enough = outlook(450)
    assert "support_suppressed" not in {r for i in enough for r in i["reasons"]}
    assert any(i["verdict"] == "ANSWERABLE" for i in enough)
    assert any(i["battery_id"] is not None for i in enough)


def test_readiness_traces_each_research_question_to_the_questions_that_measure_it(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    """Plan run-recovery-and-truth 3a: a research question nothing measures is named before
    anything is paid for; a design that declares no link is unknown, never covered."""
    url = f"{API}/studies/{world.study_id()}/research/readiness"

    def readiness(content: dict[str, Any]) -> Any:
        revision_id = submit(researcher, world, content).json()["revision_id"]
        return viewer.get(url, params={"design_revision_id": revision_id}).json()

    plain = readiness(DESIGN)
    assert plain["research_trace"]["linked"] is False
    assert [q["verdict"] for q in plain["research_trace"]["questions"]] == ["UNKNOWN"]

    habit, other = "Jak často lidé pijí kávu?", "Co lidé snídají?"
    sections = [dict(s) for s in DESIGN["sections"]]
    sections[0] = {
        **sections[0],
        "questions": [
            {**sections[0]["questions"][0], "research_questions": [habit]},
            sections[0]["questions"][1],
        ],
    }
    linked = readiness(
        {**DESIGN, "research_plan": {"research_questions": [habit, other]}, "sections": sections}
    )
    trace = {q["text"]: q for q in linked["research_trace"]["questions"]}
    assert trace[habit]["measures"] == ["q1"] and trace[habit]["verdict"] == "ANSWERABLE"
    assert trace[other]["verdict"] == "UNANSWERABLE" and trace[other]["reasons"] == ["unmeasured"]
    check = next(c for c in linked["checks"] if c["id"] == "research_question_coverage")
    assert check["status"] == "WARN" and other in check["message"]
    assert linked["ready"] is True, "a trace warns, it never refuses"
    # Runnable is not answerable (research-integrity-report 1): said beside it, and with the
    # deployment's gate off no acknowledgement is asked for -- the switch reaches the page.
    assert linked["answerability"]["capable"] is False
    assert linked["answerability"]["acknowledgement_required"] is False
    assert [g["research_question"] for g in linked["answerability"]["gaps"]] == [other]

    # 3c: the comparison the plan declares is checked against what measures it.
    ranked = readiness(
        {
            **DESIGN,
            "research_plan": {
                "research_questions": [habit, other],
                "research_question_comparisons": {habit: "rank_objects"},
            },
            "sections": sections,
        }
    )
    trace = {q["text"]: q for q in ranked["research_trace"]["questions"]}
    assert trace[habit]["comparison"] == "rank_objects"
    assert trace[habit]["verdict"] == "UNANSWERABLE"
    assert trace[habit]["reasons"] == ["comparison_needs_tracked_set"]
    assert trace[other]["comparison"] is None


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
    assert steps["run"]["data_origin_kind"] == "SIMULATED"
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


def test_a_run_says_which_population_it_recorded_and_that_fieldwork_did_not_read_it(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Population-operations P3: no LIVE, no population; a recorded one is a record only."""
    revision_id = submit(researcher, world).json()["revision_id"]
    run = start(researcher, world, revision_id).json()
    assert run["population"] is None  # no LIVE when it started: it recorded none

    note = {
        "population_id": "CZ_LIVE",
        "version_id": "DSV-fictional",
        "version_label": "v17_4_0",
        "read_by_fieldwork": False,
    }
    with create_session_factory(app.state.engine)() as session:
        row = session.get(WorkflowRunRow, run["run_id"])
        assert row is not None
        row.metadata_json = {**row.metadata_json, "population": note}
        session.commit()
    read = researcher.get(f"{_runs(world)}/{run['run_id']}").json()
    assert read["population"] == note


def test_a_run_names_the_methods_it_computed_under(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Methodology-tab Z1, R1d: Results say which Sociomap, support, aggregation and response
    process a run pinned, and whether its response process is 18.6.6's."""
    revision_id = submit(researcher, world).json()["revision_id"]
    run = start(researcher, world, revision_id).json()
    assert run["methodology"] == {
        "sociomap": {"name": "aia-sociomap-3", "stored": False},
        "support": {"name": "aia-support-1", "stored": False},
        "aggregation": {"name": "aia-aggregate-1", "stored": False},
        "response": {"name": "aia-response-1", "stored": False},
        "response_deviates": False,
    }

    def version(module: str, name: str) -> dict[str, Any]:
        return {"module": module, "version": 1, "name": name, "payload_sha256": "0" * 64}

    with create_session_factory(app.state.engine)() as session:
        row = session.get(WorkflowRunRow, run["run_id"])
        assert row is not None
        row.metadata_json = {
            **row.metadata_json,
            "methodology": version("sociomap", "aia-sociomap-3+e1"),
            "support_methodology": version("support", "aia-support-1+e2"),
            "aggregation_methodology": version("aggregation", "aia-aggregate-1+e1"),
            "response": {
                **AIA_RESPONSE_V1.model_dump(mode="json"),
                "methodology_version": "aia-response-1+e1",
                "extremity": 0.5,
            },
            "response_methodology": version("response", "aia-response-1+e1"),
        }
        session.commit()
    read = researcher.get(f"{_runs(world)}/{run['run_id']}").json()
    assert read["methodology"] == {
        "sociomap": {"name": "aia-sociomap-3+e1", "stored": True},
        "support": {"name": "aia-support-1+e2", "stored": True},
        "aggregation": {"name": "aia-aggregate-1+e1", "stored": True},
        "response": {"name": "aia-response-1+e1", "stored": True},
        "response_deviates": True,
    }
    listed = researcher.get(_runs(world)).json()["items"]
    assert listed[0]["methodology"] == read["methodology"]


def test_a_run_from_before_the_pins_reads_as_the_presets_it_was_computed_under() -> None:
    from aia_api.routers.research import _methodology

    assert _methodology({}).model_dump() == {
        "sociomap": {"name": "aia-sociomap-1", "stored": False},
        "support": {"name": "aia-support-1", "stored": False},
        "aggregation": {"name": "aia-aggregate-1", "stored": False},
        "response": {"name": "aia-response-1", "stored": False},
        "response_deviates": False,
    }
    unreadable = _methodology({"response": {"extremity": "much"}}).model_dump()
    assert unreadable["response"] == {"name": None, "stored": False}
    assert unreadable["response_deviates"] is None  # never a guess


def test_a_report_artifact_reads_its_origin_kind_and_an_unknown_one_is_never_real() -> None:
    from aia_core.domain.fieldwork import OriginKind

    from aia_api.routers.research import _artifact_origin_kind, _origin_flags

    assert _artifact_origin_kind({"data_origin": "MODELLED_AI_PANEL"}) is OriginKind.MODELLED
    assert _artifact_origin_kind({"synthetic": True}) is OriginKind.SIMULATED
    assert _artifact_origin_kind({"synthetic": False}) is OriginKind.UNKNOWN
    assert _artifact_origin_kind({"data_origin": "PANEL"}) is OriginKind.UNKNOWN
    assert _origin_flags({OriginKind.MODELLED}) == {
        "modelled": True,
        "data_origin_kind": "MODELLED",
    }
    assert _origin_flags({OriginKind.MODELLED, OriginKind.SIMULATED})["data_origin_kind"] == (
        "UNKNOWN"
    )
    assert _origin_flags(set()) == {"modelled": False, "data_origin_kind": None}


def test_a_run_says_who_its_respondents_are_and_a_panel_start_needs_a_population(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Plan panel-grounded-respondents 5c: the switch decides what a new run pins; with it on
    and no population established, nothing starts -- never a fictional run instead."""
    revision_id = submit(researcher, world).json()["revision_id"]
    roster = start(researcher, world, revision_id).json()
    assert roster["persona_source"] == "fictional_roster"

    app.state.settings = app.state.settings.model_copy(
        update={"ai_population_personas_enabled": True}
    )
    refused = researcher.post(f"{_runs(world)}", json={"design_revision_id": revision_id})
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "population_not_established"
    # The fictional run is untouched and still reads as what it pinned.
    read = researcher.get(f"{_runs(world)}/{roster['run_id']}").json()
    assert read["persona_source"] == "fictional_roster"


def test_readiness_says_the_filters_apply_only_where_a_new_run_would_draw_from_the_population(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Plan panel-grounded-respondents 6d: readiness reads the pin a start would make now."""
    filtered = {
        **DESIGN,
        "audience": {"source_mode": "population", "filters": {"vek": {"min": 30, "max": 59}}},
    }
    revision_id = submit(researcher, world, filtered).json()["revision_id"]
    url = f"{API}/studies/{world.study_id()}/research/readiness"

    def audience() -> dict[str, Any]:
        body = researcher.get(url, params={"design_revision_id": revision_id}).json()
        return next(c for c in body["checks"] if c["id"] == "audience")

    assert audience()["status"] == "WARN"
    app.state.settings = app.state.settings.model_copy(
        update={"ai_population_personas_enabled": True}
    )
    assert audience() == {
        "id": "audience",
        "status": "PASS",
        "message": "Filtry se uplatní při výběru respondentů z populace.",
    }


def test_a_run_stored_before_the_pin_reads_as_the_fictional_roster(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    revision_id = submit(researcher, world).json()["revision_id"]
    run = start(researcher, world, revision_id).json()
    with create_session_factory(app.state.engine)() as session:
        row = session.get(WorkflowRunRow, run["run_id"])
        assert row is not None
        row.metadata_json = {k: v for k, v in row.metadata_json.items() if k != "persona_source"}
        session.commit()
    assert researcher.get(f"{_runs(world)}/{run['run_id']}").json()["persona_source"] == (
        "fictional_roster"
    )


def test_a_person_chooses_who_answers_among_the_sources_the_deployment_offers(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Plan run-recovery-and-truth 5a: the switch says what is offered and what is the
    default; a person chooses per run, and an unoffered source is refused, never swapped."""
    filtered = {
        **DESIGN,
        "audience": {"source_mode": "population", "filters": {"vek": {"min": 30, "max": 59}}},
    }
    revision_id = submit(researcher, world, filtered).json()["revision_id"]
    url = f"{API}/studies/{world.study_id()}/research/readiness"

    def readiness(**params: str) -> Any:
        return researcher.get(url, params={"design_revision_id": revision_id, **params})

    off = readiness().json()
    assert off["persona_source"] == "fictional_roster"
    assert off["persona_sources"] == [
        {"source": "fictional_roster", "offered": True, "reason": None, "default": True},
        {
            "source": "panel",
            "offered": False,
            "reason": "panel_personas_disabled",
            "default": False,
        },
    ]
    asked = readiness(persona_source="panel")
    assert asked.status_code == 409, asked.text
    assert (asked.json()["code"], asked.json()["details"]["reason"]) == (
        "persona_source_unavailable",
        "panel_personas_disabled",
    )
    refused = researcher.post(
        _runs(world), json={"design_revision_id": revision_id, "persona_source": "panel"}
    )
    assert refused.status_code == 409 and refused.json()["code"] == "persona_source_unavailable"
    assert researcher.get(_runs(world)).json()["items"] == []  # nothing started

    app.state.settings = app.state.settings.model_copy(
        update={"ai_population_personas_enabled": True}
    )
    on = readiness().json()
    assert on["persona_source"] == "panel"
    assert [(o["source"], o["offered"], o["default"]) for o in on["persona_sources"]] == [
        ("fictional_roster", True, False),
        ("panel", True, True),
    ]
    # Readiness under the roster, chosen with the panel on: the filters are not applied.
    roster = readiness(persona_source="fictional_roster").json()
    assert roster["persona_source"] == "fictional_roster"
    audience = next(c for c in roster["checks"] if c["id"] == "audience")
    assert audience["status"] == "WARN"
    # The roster can be chosen with the panel on: the switch no longer decides every run.
    run = researcher.post(
        _runs(world),
        json={"design_revision_id": revision_id, "persona_source": "fictional_roster"},
    )
    assert run.status_code == 201, run.text
    assert run.json()["persona_source"] == "fictional_roster"


def test_a_run_records_what_its_design_selected_and_what_reached_its_respondents(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Plan run-recovery-and-truth 5b, 5c: dimensions and filters apply only to a draw from the
    population, so a roster run says so; a run from before 5b recorded nothing and says so."""
    selected = {
        **DESIGN,
        "persona_dimensions": {"approved": ["vek_skupina", "region"]},
        "audience": {"source_mode": "population", "filters": {"vek": {"min": 30, "max": 59}}},
    }
    revision_id = submit(researcher, world, selected).json()["revision_id"]
    run = start(researcher, world, revision_id).json()
    assert run["selection"] == {
        "dimensions": ["vek_skupina", "region"],
        "dimensions_unmatched": ["vek_skupina", "region"],
        "dimensions_applied": False,
        "dimensions_reason": "dimensions_need_population_draw",
        "audience_filters": {"vek": {"max": 59, "min": 30}},
        "filters_applied": False,
        "filters_reason": "filters_need_population_draw",
    }
    with create_session_factory(app.state.engine)() as session:
        row = session.get(WorkflowRunRow, run["run_id"])
        assert row is not None
        row.metadata_json = {k: v for k, v in row.metadata_json.items() if k != "selection"}
        session.commit()
    assert researcher.get(f"{_runs(world)}/{run['run_id']}").json()["selection"] is None


def test_a_panel_runs_filters_are_applied_only_once_its_draw_succeeded() -> None:
    """Review (Codex on #439): a start records the filters as awaiting the draw; only a
    fieldwork step that succeeded with population-drawn data applies them, and a run that
    ended without one says no respondent was drawn."""
    from aia_api.routers.research import ResearchStepResponse, _selection

    meta = {
        "selection": {
            "dimensions": ["media"],
            "dimensions_applied": False,
            "dimensions_reason": "dimensions_await_population_draw",
            "audience_filters": {"vek": {"min": 30}},
            "filters_applied": False,
            "filters_reason": "filters_await_population_draw",
        }
    }

    def fieldwork(status: str, origin: str | None) -> list[ResearchStepResponse]:
        return [
            ResearchStepResponse.model_construct(node_key="run", status=status, data_origin=origin)
        ]

    waiting = _selection(meta, fieldwork("RUNNING", None), terminal=False)
    assert waiting is not None
    assert (waiting.filters_applied, waiting.filters_reason) == (
        False,
        "filters_await_population_draw",
    )
    drawn = _selection(meta, fieldwork("SUCCEEDED", "MODELLED_AI_PANEL"), terminal=True)
    assert drawn is not None and (drawn.filters_applied, drawn.filters_reason) == (True, None)
    # 5c: the dimensions are the drawn personas' topic allowlist, settled by the same step.
    assert (drawn.dimensions_applied, drawn.dimensions_reason) == (True, None)
    failed = _selection(meta, fieldwork("FAILED", None), terminal=True)
    assert failed is not None
    assert (failed.filters_applied, failed.filters_reason) == (
        False,
        "population_draw_not_completed",
    )
    assert failed.dimensions_reason == "population_draw_not_completed"
    # Data that is not the population's never counts as the draw.
    roster = _selection(meta, fieldwork("SUCCEEDED", "SYNTHETIC_AI_FICTIONAL"), terminal=True)
    assert roster is not None and roster.filters_applied is False
    # Codex on #447: a drawn run whose every dimension is no persona topic applied none of them.
    none_topics = {
        "selection": {
            **meta["selection"],
            "dimensions": ["region"],
            "dimensions_unmatched": ["region"],
        }
    }
    unmatched = _selection(none_topics, fieldwork("SUCCEEDED", "MODELLED_AI_PANEL"), terminal=True)
    assert unmatched is not None
    assert (unmatched.dimensions_applied, unmatched.dimensions_reason) == (
        False,
        "dimensions_not_persona_topics",
    )
    assert unmatched.filters_applied is True
