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
import json
import zipfile
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from aia_core.application import client_report
from aia_core.application.client_report import (
    CLIENT_REPORT_ARTIFACT_TYPE,
    CLIENT_REPORT_DOCUMENT_ARTIFACT_TYPE,
)
from aia_core.application.report import (
    INTERNAL_REPORT_ARTIFACT_TYPE,
    INTERNAL_REPORT_DOCUMENT_ARTIFACT_TYPE,
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
from aia_core.domain.report.document_model import DOCUMENT_MODEL_CONTRACT, document_bytes
from aia_core.domain.report.evidence import EvidenceLedger
from aia_core.domain.report.model import (
    Callout,
    CalloutKind,
    Classification,
    Paragraph,
    Quote,
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
    return world.design(c, DESIGN if content is None else content, study=study)


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


def test_a_design_names_the_working_revision_it_is_and_is_refused_otherwise(
    researcher: TestClient, world: Any
) -> None:
    """ADR 0026 decision 5: the submit names its working revision, which the server checks by
    hash and records; without one, or with one whose content differs, it is refused."""
    url = f"{API}/studies/{world.study_id()}"
    made = submit(researcher, world)
    assert made.status_code == 201, made.text
    working = researcher.get(f"{url}/workspace/content").json()["revision"]
    assert made.json()["workspace_revision"] == working
    got = researcher.get(f"{url}/design/revisions/{made.json()['revision_id']}").json()
    assert got["workspace_revision"] == working
    for body in (
        {"content": DESIGN, "source_stage": "run"},
        {"content": DESIGN, "source_stage": "run", "workspace_revision": 0},
    ):
        assert researcher.post(f"{url}/design/revisions", json=body).status_code == 422
    for content, number in (({**DESIGN, "n": 7}, working), (DESIGN, working + 5)):
        refused = researcher.post(
            f"{url}/design/revisions",
            json={"content": content, "source_stage": "run", "workspace_revision": number},
        )
        assert refused.status_code == 422, refused.text
        assert refused.json()["code"] == "design_not_from_workspace"


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
        # The working copy is owned too (study_workspace); the other owned project is the design.
        design_project = session.scalars(
            select(ProjectRow.project_id).where(ProjectRow.owner != "study_workspace")
        ).one()
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
        return Failed(
            self.failure,
            error={
                "message": "The AI runtime is not deployed.",
                "reason": "egress_route_not_approved_for_class",
            },
        )


def _worker(app: FastAPI, fieldwork: FailureClass | None) -> Worker:
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


def test_finding_reviews_are_read_and_refused_through_the_study_the_path_names(
    app: FastAPI, researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """artifact-analysis ANL11: a run's finding reviews are found only through its study, a
    finding the analysis does not hold is 404, and only an edit carries a wording."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run = start(researcher, world, revision).json()
    base = f"{_runs(world)}/{run['run_id']}/analysis/findings"

    listed = researcher.get(base)
    assert listed.status_code == 200, listed.text
    assert listed.json() == {"run_id": run["run_id"], "reviews": []}

    # No module has an outcome yet: there is no finding to decide on.
    refused = researcher.put(f"{base}/executive/0", json={"decision": "accepted"})
    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "finding_not_found"
    mismatch = researcher.put(
        f"{base}/executive/0", json={"decision": "accepted", "wording": "Čaj vede."}
    )
    assert (mismatch.status_code, mismatch.json()["code"]) == (422, "wording_mismatch")
    assert researcher.put(f"{base}/nonsense/0", json={"decision": "accepted"}).status_code == 422
    assert researcher.put(f"{base}/executive/0", json={"decision": "kept"}).status_code == 422

    # Another client's study does not hold this run.
    wrong = f"{_runs(world, 'other_client')}/{run['run_id']}/analysis/findings"
    assert other_client_lead.get(wrong).status_code == 404
    assert (
        other_client_lead.put(f"{wrong}/executive/0", json={"decision": "accepted"}).status_code
        == 404
    )


def _store_internal_report(
    app: FastAPI,
    world: Any,
    run_id: str,
    document: bytes,
    *,
    pdf: bytes | None = None,
    pdf_of: str | None = None,
    metadata: dict[str, Any] | None = None,
    model: bytes | None = None,
    model_metadata: dict[str, Any] | None = None,
) -> str:
    """Drive the run's steps to the end, the report step storing ``document`` as the
    researcher's internal report (and ``pdf`` as its rendering, of ``pdf_of`` when given;
    ``model`` as its document model, with ``model_metadata`` over what it records), with
    ``metadata`` beside what it records; return its artifact id."""
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
                if model is not None:
                    stored, _ = research_artifacts(session, scope, app.state.artifact_store).put(
                        project_id=work.project_id,
                        revision=work.project_revision,
                        stage_type="REPORT",
                        artifact_type=INTERNAL_REPORT_DOCUMENT_ARTIFACT_TYPE,
                        data=model,
                        content_type="application/json",
                        input_fingerprint=f"report-route-test-{run_id}",
                        metadata={
                            "run_id": run_id,
                            "report_kind": "internal",
                            "docx_artifact_id": report_id,
                            "docx_sha256": artifact.sha256,
                            **(model_metadata or {}),
                        },
                        depends_on=[report_id],
                    )
                    output["document"] = {
                        "artifact_id": stored.artifact_id,
                        "sha256": stored.sha256,
                    }
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


def _document_model(title: str = "Úvod a rámec studie") -> bytes:
    """A stored document model of the current contract, fictional."""
    return json.dumps(
        {
            "contract": DOCUMENT_MODEL_CONTRACT,
            "meta": {"kind": "internal", "title": "Interní analytická zpráva"},
            "sections": [
                {
                    "id": "intro",
                    "title": title,
                    "appendix": False,
                    "blocks": [
                        {
                            "id": "intro.1",
                            "type": "paragraph",
                            "role": "body",
                            "content": [{"type": "text", "text": "Fiktivní.", "emphasis": "none"}],
                            "marks": [],
                            "refs": [],
                        }
                    ],
                    "refs": [],
                }
            ],
            "ledger": {"surface": "internal", "refs": {}},
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _question_table_model() -> bytes:
    """A stored internal document with one per-question table, as the composer anchors it."""
    model = json.loads(_document_model())
    model["sections"].append(
        {
            "id": "ch-tables",
            "title": "Výsledky jednotlivých otázek",
            "appendix": False,
            "refs": ["q1.pct.1", "q1.n"],
            "blocks": [
                {
                    "id": "ch-tables.1",
                    "type": "table",
                    "anchor": "tab-question-1",
                    "title": "@Jak často nakupujete?",
                    "columns": [{"label": "Ukazatel", "align": "left", "unit": None}],
                    "rows": [
                        {
                            "cells": [
                                {"type": "text", "text": "Denně", "control": None},
                                {"type": "number", "ref": "q1.pct.1", "with_interval": True},
                            ],
                            "emphasis": False,
                        },
                        {
                            "cells": [
                                {"type": "text", "text": "platné odpovědi", "control": None},
                                {"type": "number", "ref": "q1.n", "with_interval": False},
                            ],
                            "emphasis": False,
                        },
                    ],
                    "suppressed_rows": 1,
                    "source": "Fiktivní",
                    "base_ref": "q1.n",
                    "notes": [],
                    "notes_control": None,
                    "refs": ["q1.pct.1", "q1.n"],
                }
            ],
        }
    )
    entry = {"suppressed": False, "grade": "measured", "modelled_panel": False}
    model["ledger"]["refs"] = {
        "q1.pct.1": {
            **entry,
            "value_text": "42,5 %",
            "interval_text": "38,1 až 46,9 %",
            "base_text": "n = 480",
        },
        "q1.n": {**entry, "value_text": "480", "interval_text": None, "base_text": None},
    }
    return json.dumps(model, sort_keys=True, separators=(",", ":")).encode()


def test_a_runs_question_tables_export_as_the_report_prints_them(
    app: FastAPI,
    researcher: TestClient,
    other_client_lead: TestClient,
    world: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RD12 (D-41): the per-question tables of the stored internal draft as CSV and XLSX, each
    number the text the report prints; the client report's alone with document=client."""
    import csv
    import io

    import openpyxl

    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    url = f"{_runs(world)}/{run_id}/report/tables"
    assert researcher.get(f"{url}/csv").status_code == 404  # no report yet
    report_id = _store_internal_report(
        app, world, run_id, b"PK\x03\x04draft", model=_question_table_model()
    )

    got = researcher.get(f"{url}/csv")
    assert got.status_code == 200, got.text
    assert got.headers["content-type"].startswith("text/csv")
    assert got.headers["x-aia-artifact-id"] == report_id
    assert (
        got.headers["x-aia-artifact-sha256"]
        == researcher.get(f"{_runs(world)}/{run_id}/report/document").json()["report_sha256"]
    )
    assert got.headers["x-aia-review-state"] == "DRAFT_UNAPPROVED"
    assert f"-tabulky-zakladni-{report_id}-koncept.csv" in got.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(got.content.decode("utf-8-sig")), delimiter=";"))
    title = "'@Jak často nakupujete?"  # a formula's first character, kept as text
    assert rows == [
        ["Otázka", "Ukazatel", "Hodnota", "95% interval", "Základ", "Evidence", "Původ"],
        [title, "Denně", "42,5 %", "38,1 až 46,9 %", "n = 480", "Měřeno", ""],
        [title, "platné odpovědi", "480", "", "", "Měřeno", ""],
        [title, "vynecháno pro nedostatečnou oporu: 1", "", "", "", "", ""],
    ]

    book = researcher.get(f"{url}/xlsx")
    assert book.status_code == 200, book.text
    sheet = openpyxl.load_workbook(io.BytesIO(book.content)).active
    cells = [[c if c is not None else "" for c in r] for r in sheet.iter_rows(values_only=True)]
    # A workbook cell is text, never a formula: it carries the title as written, unguarded.
    assert cells == [[c.removeprefix("'") for c in row] for row in rows]

    # The client report's export is its own: this one has no question table, said by name.
    monkeypatch.setattr(
        client_report, "compose_client_report", _composing(_client_report_document())
    )
    assert researcher.get(f"{_runs(world)}/{run_id}/report/client/download").status_code == 200
    none = researcher.get(f"{url}/csv", params={"document": "client"})
    assert none.status_code == 409 and none.json()["code"] == "no_question_tables"
    assert researcher.get(f"{url}/pdf").status_code == 422
    foreign = f"{_runs(world, 'other_client')}/{run_id}/report/tables/csv"
    assert other_client_lead.get(foreign).status_code == 404


def test_the_internal_draft_is_read_as_its_document_beside_its_docx(
    app: FastAPI,
    researcher: TestClient,
    other_client_lead: TestClient,
    world: Any,
    damage_artifact: Any,
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    url = f"{_runs(world)}/{run_id}/report/document"
    assert researcher.get(url).status_code == 404  # no report yet

    model = _document_model()
    report_id = _store_internal_report(app, world, run_id, b"PK\x03\x04draft", model=model)
    read = researcher.get(url)
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["report_artifact_id"] == report_id
    assert body["sha256"] == hashlib.sha256(model).hexdigest()
    assert body["review_state"] == "DRAFT_UNAPPROVED" and body["approved_on"] is None
    assert body["document"] == json.loads(model)
    assert [b["id"] for b in body["document"]["sections"][0]["blocks"]] == ["intro.1"]
    other_url = f"{_runs(world, 'other_client')}/{run_id}/report/document"
    assert other_client_lead.get(other_url).status_code == 404

    damage_artifact(body["artifact_id"], "tampered")
    damaged = researcher.get(url)
    assert damaged.status_code == 409 and damaged.json()["code"] == "artifact_corrupt"


def test_a_report_without_its_document_or_beside_another_docx_says_so(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]

    before = start(researcher, world, revision).json()["run_id"]
    _store_internal_report(app, world, before, b"PK\x03\x04before-rd5a")
    refused = researcher.get(f"{_runs(world)}/{before}/report/document")
    assert refused.status_code == 409
    assert refused.json()["code"] == "report_document_not_stored"
    # Its DOCX still downloads.
    assert researcher.get(f"{_runs(world)}/{before}/report/download").status_code == 200


@pytest.mark.parametrize(
    "model_metadata",
    [
        pytest.param({"docx_artifact_id": "ART-0000000000000000"}, id="another-docx"),
        pytest.param({"docx_sha256": "0" * 64}, id="another-docx-bytes"),
        pytest.param({"run_id": "RUN-another"}, id="another-run"),
    ],
)
def test_a_document_not_beside_this_runs_docx_is_refused(
    app: FastAPI, researcher: TestClient, world: Any, model_metadata: dict[str, Any]
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    _store_internal_report(
        app,
        world,
        run_id,
        b"PK\x03\x04draft",
        model=_document_model(),
        model_metadata=model_metadata,
    )
    refused = researcher.get(f"{_runs(world)}/{run_id}/report/document")
    assert refused.status_code == 409
    assert refused.json()["code"] == "report_artifact_invalid"


def test_a_stored_document_of_another_contract_is_refused(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    _store_internal_report(
        app, world, run_id, b"PK\x03\x04draft", model=b'{"contract":"aia-report-document-0"}'
    )
    refused = researcher.get(f"{_runs(world)}/{run_id}/report/document")
    assert refused.status_code == 409
    assert refused.json()["code"] == "report_artifact_invalid"


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
    entry, signed_off = researcher.get(url).json()["entries"]
    assert entry["method_id"] == "aia-sociomap-3" and entry["status"] == "CLIENT_FACING"
    assert entry["decided_on"] == "2026-10-13" and len(entry["spec_fingerprint"]) == 64
    assert signed_off["method_id"] == "aia-sociomap-5" and signed_off["status"] == "CLIENT_FACING"
    assert signed_off["decided_on"] == "2026-10-21"


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
    report_id = _store_internal_report(
        app, world, run_id, b"PK\x03\x04approve-test", model=_document_model()
    )
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
    assert researcher.get(url).json()["approval"] is None  # a draft names no approver (RD2)

    before = _prague_today()
    approved = outsider.post(approve, json={"artifact_id": report_id, "note": "Přečteno."})
    assert approved.status_code == 200, approved.text
    assert approved.json()["review_state"] == "APPROVED_INTERNAL"
    assert approved.json()["internal_only"] is True
    assert approved.json()["report_kind"] == "internal"  # RD3, G66
    status_ = researcher.get(url).json()
    assert status_["review_state"] == "APPROVED_INTERNAL"
    assert status_["approved_on"] in {before, _prague_today()}
    # RD2: by whom, under which rule, from the ledger row; "you" is the asker.
    approval = status_["approval"]
    assert approval["approver_name"] and approval["by_you"] is False
    assert approval["self_approved"] is False and approval["self_approval_allowed"] is False
    assert approval["self_approval_source"] == "client" and approval["note"] == "Přečteno."
    assert outsider.get(url).json()["approval"]["by_you"] is True
    assert approved.json()["approval"]["by_you"] is True
    # The document route Zpráva reads carries the same approval.
    document = researcher.get(f"{url}/document")
    assert document.status_code == 200, document.text
    assert document.json()["approval"] == approval
    # D2: its fictional bytes take no stamp, so its approved export is its stored bytes and
    # approving asks for no new PDF (cross-review interactions#4); a person may ask for one.
    assert status_["stamped"] is False
    assert status_["pdf"] == {"state": "NOT_REQUESTED", "reason": None, "askable": True}
    again = outsider.post(approve, json={"artifact_id": report_id})
    assert again.status_code == 200

    factory = create_session_factory(app.state.engine)
    with factory() as session:
        decisions = session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_id == report_id)
        ).all()
    assert [(d.decision, d.comment) for d in decisions] == [("APPROVED", "Přečteno.")]
    # Its document was checked (RD7) and nothing found: an empty list, never NULL, which says
    # nothing was checked (the next test).
    assert decisions[0].warnings == []


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


def test_a_version_approved_before_the_stamp_layout_keeps_its_pdf_on_a_closed_study(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    """Cross-review interactions#4 / web#3: an approved version's PDF was looked up only under
    the approved key, so a report approved before this release -- stored without the stamp
    layout, its step PDF ready -- read NOT_REQUESTED, study_closed, and its PDF download was a
    404 for good on a delivered study. Its export is its stored bytes, which the step's PDF
    renders exactly: that PDF is the approved version's, and approving asks for nothing."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    report_id = _store_internal_report(
        app, world, run_id, _rendered_report(), pdf=b"%PDF-1.7 draft rendering"
    )
    url = f"{_runs(world)}/{run_id}/report"
    before = _jobs_count(app)
    approved = outsider.post(f"{url}/approve", json={"artifact_id": report_id})
    assert approved.status_code == 200 and approved.json()["stamped"] is False
    assert _jobs_count(app) == before  # nothing new to render
    _close_study(app, world)
    status_ = researcher.get(url).json()
    assert status_["review_state"] == "APPROVED_INTERNAL"
    assert status_["pdf"]["state"] == "READY" and status_["pdf"]["askable"] is False
    pdf = researcher.get(f"{url}/pdf/download")
    assert pdf.status_code == 200, pdf.text
    assert pdf.content == b"%PDF-1.7 draft rendering"
    assert pdf.headers["X-AIA-Artifact-Id"] == report_id
    assert pdf.headers["X-AIA-Review-State"] == "APPROVED_INTERNAL"
    # Its pages keep the draft footer it was stored with: named approved in AIA, not stamped.
    assert pdf.headers["content-disposition"].endswith(f'-{report_id}-schvaleno-v-aia.pdf"')
    docx = researcher.get(f"{url}/download")
    assert docx.status_code == 200 and docx.content == _rendered_report()


def test_a_draft_whose_step_rendered_no_pdf_promises_none(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """A deployment without PDF (the code default): the step made none, nobody asked, and
    whether approving would make one is not known. Unknown is never a promise."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    report_id = _store_internal_report(
        app, world, run_id, _rendered_report(), metadata=dict(REVIEW_STAMP_RECORD)
    )
    url = f"{_runs(world)}/{run_id}/report"
    status_ = researcher.get(url).json()
    assert status_["pdf"] == {"state": "NOT_REQUESTED", "reason": None, "askable": True}
    assert status_["approval_renders_pdf"] is False
    # Cross-review web#2: approving asks for no PDF here either -- a job would only fail
    # pdf_disabled where none is rendered. A person may ask for one on the report.
    before = _jobs_count(app)
    approved = researcher.post(f"{url}/approve", json={"artifact_id": report_id})
    assert approved.status_code == 200, approved.text
    assert _jobs_count(app) == before
    status_ = researcher.get(url).json()
    assert status_["review_state"] == "APPROVED_INTERNAL"
    assert status_["pdf"]["state"] == "NOT_REQUESTED" and status_["pdf"]["askable"] is True


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
        # stored_client_report stores the document beside the draft it stores (RD5a), which the
        # client gate reads at approval (RD0).
        client_report._store_document(
            research_artifacts(session, scope, app.state.artifact_store),
            run_id,
            stored,
            ReportDocument(meta, (section,), ledger),
            "",
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
    # The client report is the deliverable that leaves: never said to be internal (RD3, G66).
    assert approved.json()["report_kind"] == "client"
    assert approved.json()["internal_only"] is False
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


def _client_report_document() -> ReportDocument:
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
    return ReportDocument(meta, (section,), ledger)


def test_an_approved_client_report_stays_the_client_report_after_its_contract_changes(
    app: FastAPI,
    researcher: TestClient,
    outsider: TestClient,
    world: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-review interactions#1: the client download keyed its stored draft on the
    fingerprint of what composing gives today, which carries the composition contract. A
    contract bump (aia-client-report-2 -> -3 on this branch) composed and served a new draft
    instead of the approved version, which no route served any more; composing refused under
    the new rules, the download was a 409. The approved version is the client report (D2).

    The real stored_client_report; composing is stubbed the way it reads the contract (at call
    time), since a real composition needs a population-grounded run (test_ai_fieldwork)."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    composed: list[str] = []

    def compose(session: Any, scope: Any, store: Any, *, run_id: str) -> Any:
        composed.append(client_report.CLIENT_REPORT_CONTRACT)
        return client_report.ComposedClientReport(
            document=_client_report_document(),
            sources={"contract": client_report.CLIENT_REPORT_CONTRACT, "run_id": run_id},
            depends_on=(),
        )

    monkeypatch.setattr(client_report, "compose_client_report", compose)
    monkeypatch.setattr(client_report, "CLIENT_REPORT_CONTRACT", "aia-client-report-2")
    url = f"{_runs(world)}/{run_id}/report"
    draft = researcher.get(f"{url}/client/download")
    assert draft.status_code == 200, draft.text
    version = draft.headers["X-AIA-Artifact-Id"]
    assert draft.headers["X-AIA-Review-State"] == "DRAFT_UNAPPROVED"
    approved = outsider.post(f"{url}/approve", json={"artifact_id": version})
    assert approved.status_code == 200 and approved.json()["stamped"] is True

    # The deploy: the contract moves on. The approved version is served, nothing composed.
    monkeypatch.setattr(client_report, "CLIENT_REPORT_CONTRACT", "aia-client-report-3")
    composed.clear()
    after = researcher.get(f"{url}/client/download")
    assert after.status_code == 200, after.text
    assert after.headers["X-AIA-Artifact-Id"] == version
    assert after.headers["X-AIA-Artifact-Sha256"] == draft.headers["X-AIA-Artifact-Sha256"]
    assert after.headers["X-AIA-Review-State"] == "APPROVED_INTERNAL"
    assert after.headers["content-disposition"].endswith(f'-klient-{version}-schvaleno.docx"')
    year, month, day = (int(x) for x in approved.json()["approved_on"].split("-"))
    status = f"SCHVÁLENO {day}.\u00a0{month}.\u00a0{year}"
    assert _says_approved(_footers(after.content), status, f"verze {version}")
    assert composed == []

    # Composing refused under today's rules refuses nothing a person approved.
    def refused(*_a: Any, **_kw: Any) -> Any:
        raise client_report.ClientReportRefused("not_modelled", "fiktivní odmítnutí")

    monkeypatch.setattr(client_report, "compose_client_report", refused)
    again = researcher.get(f"{url}/client/download")
    assert again.status_code == 200 and again.headers["X-AIA-Artifact-Id"] == version
    with create_session_factory(app.state.engine)() as session:
        stored = session.scalars(
            select(ProjectArtifactRow.artifact_id).where(
                ProjectArtifactRow.artifact_type == CLIENT_REPORT_ARTIFACT_TYPE
            )
        ).all()
    assert stored == [version]


def test_the_client_report_is_read_as_its_document_beside_its_docx(
    app: FastAPI,
    researcher: TestClient,
    outsider: TestClient,
    world: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RD5a part 2: the client report's download stores the document it renders beside the DOCX
    and the document route reads it, composing nothing; an approved version keeps its
    document. Composing is stubbed as in the contract test above (a real composition needs a
    population-grounded run, test_ai_fieldwork)."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    composed: list[str] = []

    def compose(session: Any, scope: Any, store: Any, *, run_id: str) -> Any:
        composed.append(run_id)
        return client_report.ComposedClientReport(
            document=_client_report_document(),
            sources={"contract": client_report.CLIENT_REPORT_CONTRACT, "run_id": run_id},
            depends_on=(),
        )

    monkeypatch.setattr(client_report, "compose_client_report", compose)
    url = f"{_runs(world)}/{run_id}/report/client"
    assert researcher.get(f"{url}/document").status_code == 404  # none stored yet
    assert composed == []  # reading the document never composes

    draft = researcher.get(f"{url}/download")
    assert draft.status_code == 200, draft.text
    version = draft.headers["X-AIA-Artifact-Id"]
    read = researcher.get(f"{url}/document")
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["report_artifact_id"] == version
    assert body["report_sha256"] == draft.headers["X-AIA-Artifact-Sha256"]
    assert body["review_state"] == "DRAFT_UNAPPROVED"
    assert body["document"] == json.loads(document_bytes(_client_report_document()))
    assert body["document"]["meta"]["kind"] == "client"
    assert body["document"]["meta"]["identifiers"] == []

    # Downloaded again: the same draft, the same document, nothing stored twice.
    assert researcher.get(f"{url}/download").headers["X-AIA-Artifact-Id"] == version
    assert researcher.get(f"{url}/document").json()["artifact_id"] == body["artifact_id"]
    approved = outsider.post(
        f"{_runs(world)}/{run_id}/report/approve", json={"artifact_id": version}
    )
    assert approved.status_code == 200, approved.text
    after = researcher.get(f"{url}/document").json()
    assert after["artifact_id"] == body["artifact_id"]
    assert after["review_state"] == "APPROVED_INTERNAL"
    assert after["approval"]["by_you"] is False and after["approval"]["approver_name"]
    with create_session_factory(app.state.engine)() as session:
        models = session.scalars(
            select(ProjectArtifactRow.artifact_id).where(
                ProjectArtifactRow.artifact_type == CLIENT_REPORT_DOCUMENT_ARTIFACT_TYPE
            )
        ).all()
    assert models == [body["artifact_id"]]


def test_a_client_report_stored_again_gets_a_document_of_its_own(
    app: FastAPI,
    researcher: TestClient,
    world: Any,
    damage_artifact: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review of #584: the document was reused by fingerprint alone. A draft that turned
    CORRUPT is stored again under the same fingerprint; its document must be its own, not the
    first draft's, which the route would refuse on every read."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]

    def compose(session: Any, scope: Any, store: Any, *, run_id: str) -> Any:
        return client_report.ComposedClientReport(
            document=_client_report_document(),
            sources={"contract": client_report.CLIENT_REPORT_CONTRACT, "run_id": run_id},
            depends_on=(),
        )

    monkeypatch.setattr(client_report, "compose_client_report", compose)
    url = f"{_runs(world)}/{run_id}/report/client"
    first = researcher.get(f"{url}/download").headers["X-AIA-Artifact-Id"]
    first_model = researcher.get(f"{url}/document").json()["artifact_id"]
    damage_artifact(first, "tampered")
    assert researcher.get(f"{url}/download").status_code == 409  # the damage is found
    again = researcher.get(f"{url}/download")
    assert again.status_code == 200, again.text
    second = again.headers["X-AIA-Artifact-Id"]
    assert second != first
    read = researcher.get(f"{url}/document")
    assert read.status_code == 200, read.text
    assert read.json()["report_artifact_id"] == second
    assert read.json()["artifact_id"] != first_model
    # Found again, not stored a third time.
    researcher.get(f"{url}/download")
    assert researcher.get(f"{url}/document").json()["artifact_id"] == read.json()["artifact_id"]


def _composing(document: ReportDocument) -> Any:
    def compose(session: Any, scope: Any, store: Any, *, run_id: str) -> Any:
        return client_report.ComposedClientReport(
            document=document,
            sources={"contract": client_report.CLIENT_REPORT_CONTRACT, "run_id": run_id},
            depends_on=(),
        )

    return compose


def test_the_client_report_is_the_runs_work_not_its_first_downloaders(
    app: FastAPI,
    owner: TestClient,
    researcher: TestClient,
    outsider: TestClient,
    world: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RD8: the client report is stored on whoever's read first asks for it, but code composed
    it from the run. With independent review on, the person who downloaded it first may approve
    it; the person who started the run may not, as for the run's internal report."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    # Every run names its starter: no run reaches a client report without a producer.
    with create_session_factory(app.state.engine)() as session:
        principal = AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        )
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        run = WorkflowRepository(session, scope).get_run(run_id)
    assert run["triggered_by"] == world.users["researcher"]
    monkeypatch.setattr(
        client_report, "compose_client_report", _composing(_client_report_document())
    )
    forbid = owner.put(
        f"{API}/self-approval", json={"allowed": False, "client_id": world.client_id()}
    )
    assert forbid.status_code == 200, forbid.text
    url = f"{_runs(world)}/{run_id}/report"
    # The reviewer reads it first: that read stores the draft.
    version = outsider.get(f"{url}/client/download").headers["X-AIA-Artifact-Id"]
    own = researcher.post(f"{url}/approve", json={"artifact_id": version})
    assert own.status_code == 403 and own.json()["code"] == "separation_of_duties"
    approved = outsider.post(f"{url}/approve", json={"artifact_id": version})
    assert approved.status_code == 200, approved.text
    assert approved.json()["report_kind"] == "client"
    assert approved.json()["approval"]["self_approved"] is False


def _held_after(real: Any, applies: Any) -> tuple[Any, Any]:
    """``real`` held after it ran: the first call that ``applies`` to waits, its write not yet
    committed, until a second has written too (no lock), or for 10 s (the second waits on the
    lock). Answers the replacement and the event the first call sets."""
    import threading

    first_in, second_done = threading.Event(), threading.Event()

    def held(self: Any, *args: Any, **kw: Any) -> Any:
        done = real(self, *args, **kw)
        if not applies(*args, **kw):
            return done
        if not first_in.is_set():
            first_in.set()
            second_done.wait(10)
        else:
            second_done.set()
        return done

    return held, first_in


def _at_once(app: FastAPI, world: Any, first_in: Any, calls: list[tuple[str, Any]]) -> None:
    """Each of ``calls`` (a user, then what it does in its own session and scope) in a thread of
    its own, the second started once the first holds; every error raised here."""
    import threading

    factory = create_session_factory(app.state.engine)
    errors: list[BaseException] = []

    def run(user: str, act: Any) -> None:
        try:
            with factory() as own:
                principal = AuthenticatedPrincipal(
                    user_id=world.users[user], organization_id=world.organization_id
                )
                act(own, ScopeResolver(own).study_context(principal, study_id=world.study_id()))
                own.commit()
        except BaseException as exc:  # reported below, never swallowed
            errors.append(exc)

    threads = [threading.Thread(target=run, args=call) for call in calls]
    threads[0].start()
    assert first_in.wait(30)
    threads[1].start()
    for thread in threads:
        thread.join(30)
    assert not errors, errors


def test_two_first_reads_of_the_client_report_store_one_draft(
    app: FastAPI, researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two first reads at once (two people opening Zpráva) store one draft: the second waits on
    the run's lock and finds the first's, so the version one approves is the one the other read.
    PostgreSQL only: the guard is a row lock, which SQLite does not take (it serialises writers
    instead)."""
    from aia_core.infrastructure.artifact_repository import ArtifactRepository

    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    monkeypatch.setattr(
        client_report, "compose_client_report", _composing(_client_report_document())
    )
    held, first_in = _held_after(
        ArtifactRepository.put,
        lambda **kw: kw.get("artifact_type") == CLIENT_REPORT_ARTIFACT_TYPE,
    )
    monkeypatch.setattr(ArtifactRepository, "put", held)
    ids: list[str] = []

    def read(session: Any, scope: Any) -> None:
        found, _data = client_report.stored_client_report(
            session, scope, app.state.artifact_store, run_id=run_id
        )
        ids.append(found.artifact_id)

    _at_once(app, world, first_in, [("researcher", read), ("lead", read)])
    assert len(ids) == 2 and ids[0] == ids[1]
    with create_session_factory(app.state.engine)() as session:
        stored = session.scalar(
            select(func.count())
            .select_from(ProjectArtifactRow)
            .where(ProjectArtifactRow.artifact_type == CLIENT_REPORT_ARTIFACT_TYPE)
        )
    assert stored == 1


def test_two_approvals_of_one_report_at_once_record_one_decision(
    app: FastAPI,
    researcher: TestClient,
    outsider: TestClient,
    world: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Approve once: the second approval waits on the run's lock, then reads the report
    approved and records nothing. PostgreSQL only, as the store race above."""
    from aia_core.application.report_approval import approve_report
    from aia_core.infrastructure.artifact_repository import ArtifactRepository

    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    monkeypatch.setattr(
        client_report, "compose_client_report", _composing(_client_report_document())
    )
    report = f"{_runs(world)}/{run_id}/report/client/download"
    version = outsider.get(report).headers["X-AIA-Artifact-Id"]
    held, first_in = _held_after(ArtifactRepository.approve, lambda *a, **kw: True)
    monkeypatch.setattr(ArtifactRepository, "approve", held)

    def approve(session: Any, scope: Any) -> None:
        approve_report(session, scope, app.state.artifact_store, run_id=run_id, artifact_id=version)

    _at_once(app, world, first_in, [("outsider", approve), ("lead", approve)])
    with create_session_factory(app.state.engine)() as session:
        decisions = session.scalar(
            select(func.count())
            .select_from(ApprovalDecisionRow)
            .where(ApprovalDecisionRow.subject_id == version)
        )
    assert decisions == 1


def test_a_client_report_carrying_drill_down_content_is_approved_with_its_warning_on_record(
    app: FastAPI,
    researcher: TestClient,
    outsider: TestClient,
    world: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RD0 (MVPQ-09), warnings since 2026-10-22 (the product owner: "Warnings for all of it"):
    the check names what it found before the approval and never refuses it; the approval records
    the warning it went past, on its ledger row."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    base = _client_report_document()
    quoted = replace(
        base,
        sections=(
            *base.sections,
            Section(
                "Hlasy", (Quote("Fiktivní citace.", "fiktivní respondent", synthetic=True),), id="v"
            ),
        ),
    )
    monkeypatch.setattr(client_report, "compose_client_report", _composing(quoted))
    url = f"{_runs(world)}/{run_id}/report"
    version = researcher.get(f"{url}/client/download").headers["X-AIA-Artifact-Id"]
    warning = {
        "code": "drill_down_content",
        "where": "v.1",
        "message": "doslovná odpověď jednoho respondenta",
    }
    before = researcher.get(f"{url}/client/document").json()
    assert before["warnings"] == [warning] and before["approval"] is None
    approved = outsider.post(f"{url}/approve", json={"artifact_id": version})
    assert approved.status_code == 200, approved.text
    assert approved.json()["approval"]["warnings"] == [warning]
    after = researcher.get(f"{url}/client/document").json()
    assert after["review_state"] == "APPROVED_INTERNAL"
    assert after["approval"]["warnings"] == [warning]
    with create_session_factory(app.state.engine)() as session:
        row = session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_id == version)
        ).one()
        assert row.warnings == [warning]


def test_a_sentence_comparing_in_words_alone_is_marked_and_approved_on_record(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    """RD7 (MVPQ-09), marking since 2026-10-22: the internal draft's document names a
    sentence of the analysis prose that compares with no number from the ledger; approving
    goes through and records it, as RD0's warnings are recorded."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    model = json.loads(_document_model())
    model["sections"][0]["sources"] = [
        {"kind": "artifact", "artifact_type": "research_analysis_module"}
    ]
    model["sections"][0]["blocks"][0]["content"] = [
        {"type": "text", "text": "Fiktivní. Nejvíc důvěřují lidé v Praze.", "emphasis": "none"}
    ]
    report_id = _store_internal_report(
        app, world, run_id, b"PK\x03\x04draft", model=json.dumps(model).encode()
    )
    url = f"{_runs(world)}/{run_id}/report"
    marked = {
        "code": "unsupported_comparison",
        "where": "intro.1",
        "message": "srovnání bez doloženého čísla: „Nejvíc důvěřují lidé v Praze.“",
        "sentence": 1,
        "text": "Nejvíc důvěřují lidé v Praze.",
    }
    assert researcher.get(f"{url}/document").json()["warnings"] == [marked]
    approved = outsider.post(f"{url}/approve", json={"artifact_id": report_id})
    assert approved.status_code == 200, approved.text
    assert approved.json()["approval"]["warnings"] == [marked]
    with create_session_factory(app.state.engine)() as session:
        row = session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_id == report_id)
        ).one()
        assert row.warnings == [marked]


def test_a_version_with_no_stored_document_is_approved_unchecked(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    """A version with no stored document is not checked: SQL NULL, never JSON null (RD0), so
    the migration's downgrade counts only the rows that recorded warnings."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    report_id = _store_internal_report(app, world, run_id, b"PK\x03\x04before-rd5a")
    approve = f"{_runs(world)}/{run_id}/report/approve"
    assert outsider.post(approve, json={"artifact_id": report_id}).status_code == 200
    with create_session_factory(app.state.engine)() as session:
        unchecked = session.scalar(
            select(func.count())
            .select_from(ApprovalDecisionRow)
            .where(
                ApprovalDecisionRow.subject_id == report_id,
                ApprovalDecisionRow.warnings.is_(None),
            )
        )
    assert unchecked == 1


def test_the_client_report_is_prepared_to_be_read_without_a_download(
    app: FastAPI,
    researcher: TestClient,
    outsider: TestClient,
    world: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RD3: a person reads the client draft in AIA, then approves it; no file leaves to do so.
    Prepare stores it as the download would, once; a run with no client report is refused by
    name, and nothing is stored."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    url = f"{_runs(world)}/{run_id}/report"
    refused = researcher.post(f"{url}/client/prepare")
    assert refused.status_code == 409 and refused.json()["code"] == "client_report_refused"
    assert researcher.get(f"{url}/client/document").status_code == 404

    monkeypatch.setattr(
        client_report, "compose_client_report", _composing(_client_report_document())
    )
    assert researcher.get(f"{url}/client/document").status_code == 404
    prepared = researcher.post(f"{url}/client/prepare")
    assert prepared.status_code == 200, prepared.text
    body = prepared.json()
    assert body["review_state"] == "DRAFT_UNAPPROVED" and body["approval"] is None
    assert body["document"]["meta"]["kind"] == "client"
    # When the version was stored, with its offset: the approval question names it by it (RPT3d).
    assert datetime.fromisoformat(body["stored_at"]).utcoffset() is not None
    assert researcher.get(f"{url}/client/document").json() == body
    again = researcher.post(f"{url}/client/prepare").json()
    assert again["report_artifact_id"] == body["report_artifact_id"]  # stored once
    # The version read is the version the download hands over and the approval names.
    handed = researcher.get(f"{url}/client/download").headers["X-AIA-Artifact-Id"]
    assert handed == body["report_artifact_id"]
    version = body["report_artifact_id"]
    approved = outsider.post(f"{url}/approve", json={"artifact_id": version})
    assert approved.status_code == 200, approved.text
    after = researcher.post(f"{url}/client/prepare").json()
    assert after["report_artifact_id"] == version and after["review_state"] == "APPROVED_INTERNAL"


def test_a_client_document_of_an_older_contract_is_stored_again_on_download(
    app: FastAPI,
    researcher: TestClient,
    outsider: TestClient,
    world: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A document stored under an older contract names no claim's level, so the gate cannot
    judge it (gate_unrecorded); the next download stores one of today's beside the same DOCX."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    monkeypatch.setattr(
        client_report, "compose_client_report", _composing(_client_report_document())
    )
    url = f"{_runs(world)}/{run_id}/report"
    version = researcher.get(f"{url}/client/download").headers["X-AIA-Artifact-Id"]
    first = researcher.get(f"{url}/client/document").json()["artifact_id"]
    with create_session_factory(app.state.engine)() as session:
        row = session.get(ProjectArtifactRow, first)
        assert row is not None
        row.artifact_metadata = {
            **row.artifact_metadata,
            "document_contract": "aia-report-document-2",
        }
        session.commit()
    assert researcher.get(f"{url}/client/download").headers["X-AIA-Artifact-Id"] == version
    second = researcher.get(f"{url}/client/document").json()["artifact_id"]
    assert second != first
    assert outsider.post(f"{url}/approve", json={"artifact_id": version}).status_code == 200


def test_a_client_draft_with_no_stored_document_is_approved_as_unverifiable(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    """A draft stored before its document (RD5a) cannot be checked: unknown, never passed, and
    said as a warning the approval records ("nelze ověřit"), never a refusal (RD0, 2026-10-22)."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
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
            data=DocxRenderer().render(_client_report_document()),
            content_type=INTERNAL_REPORT_MEDIA_TYPE,
            input_fingerprint="client-before-rd0",
            metadata={"run_id": run_id, "report_kind": "client", **REVIEW_STAMP_RECORD},
        )
        session.commit()
    approved = outsider.post(
        f"{_runs(world)}/{run_id}/report/approve", json={"artifact_id": stored.artifact_id}
    )
    assert approved.status_code == 200, approved.text
    (warning,) = approved.json()["approval"]["warnings"]
    assert warning["code"] == "gate_unrecorded" and "nelze ji ověřit" in warning["message"]


def test_a_client_report_stored_before_its_document_says_so(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    principal = AuthenticatedPrincipal(
        user_id=world.users["researcher"], organization_id=world.organization_id
    )
    with create_session_factory(app.state.engine)() as session:
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        run = ResearchRuns(session, scope).get(run_id)
        research_artifacts(session, scope, app.state.artifact_store).put(
            project_id=run["project_id"],
            revision=int(run["project_revision"]),
            stage_type="REPORT",
            artifact_type=CLIENT_REPORT_ARTIFACT_TYPE,
            data=b"PK\x03\x04client-before-rd5a",
            content_type=INTERNAL_REPORT_MEDIA_TYPE,
            input_fingerprint="client-before-rd5a",
            metadata={"run_id": run_id, "report_kind": "client"},
        )
        session.commit()
    refused = researcher.get(f"{_runs(world)}/{run_id}/report/client/document")
    assert refused.status_code == 409
    assert refused.json()["code"] == "report_document_not_stored"


def test_a_client_report_the_stamp_refuses_says_so_in_its_status_and_name(
    app: FastAPI,
    researcher: TestClient,
    outsider: TestClient,
    world: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-review web#14: the writer recorded that a version takes the stamp whatever its
    bytes, and the status's ``stamped`` read only that record, so an approved file the stamp
    refuses was said to state SCHVÁLENO while it was served as stored. The writer now tries
    the stamp first: a body that states the draft status is recorded unstampable, and the
    approval's answer, the file and its name agree."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    stated = _client_report_document()
    body = Section("Poznámka", (Paragraph(text("KONCEPT \u2014 NESCHVÁLENO")),))
    document = ReportDocument(stated.meta, (*stated.sections, body), stated.ledger)

    def compose(session: Any, scope: Any, store: Any, *, run_id: str) -> Any:
        return client_report.ComposedClientReport(
            document=document,
            sources={"contract": client_report.CLIENT_REPORT_CONTRACT, "run_id": run_id},
            depends_on=(),
        )

    monkeypatch.setattr(client_report, "compose_client_report", compose)
    url = f"{_runs(world)}/{run_id}/report"
    draft = researcher.get(f"{url}/client/download")
    assert draft.status_code == 200, draft.text
    version = draft.headers["X-AIA-Artifact-Id"]
    approved = outsider.post(f"{url}/approve", json={"artifact_id": version})
    assert approved.status_code == 200 and approved.json()["stamped"] is False
    after = researcher.get(f"{url}/client/download")
    assert after.content == draft.content  # as stored, never partly stamped
    assert after.headers["X-AIA-Review-State"] == "APPROVED_INTERNAL"
    assert after.headers["content-disposition"].endswith(f'-klient-{version}-schvaleno-v-aia.docx"')


def test_an_older_version_approved_is_served_unstamped_and_says_so(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """A version stored before this layout (no record of it) is approved as it is: its DOCX is
    the stored bytes, never partly stamped, and the status says it is not stamped. Its file
    name says so too (cross-review interactions#9: it was named "-schvaleno" while every
    footer said KONCEPT)."""
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
    assert downloaded.headers["content-disposition"].endswith(
        f'-zakladni-{report_id}-schvaleno-v-aia.docx"'
    )


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


def test_an_experimental_sociomapping_report_is_never_approved(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    """The experimental Sociomapping's draft is never client-facing, so it is never approved:
    no ledger row, never frozen, never stamped. Its composer's own guard went with
    ``ReportMeta.approvals`` (cb62426), leaving the approval route's type check untested while
    approving came to freeze a version and ask for its PDF."""
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    principal = AuthenticatedPrincipal(
        user_id=world.users["researcher"], organization_id=world.organization_id
    )
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        run = ResearchRuns(session, scope).get(run_id)
        stored, _ = research_artifacts(session, scope, app.state.artifact_store).put(
            project_id=run["project_id"],
            revision=int(run["project_revision"]),
            stage_type="REPORT",
            artifact_type=SOCIOMAPPING_REPORT_ARTIFACT_TYPE,
            data=_rendered_report(),
            content_type=INTERNAL_REPORT_MEDIA_TYPE,
            input_fingerprint="sociomapping-approval-test",
            metadata={
                "run_id": run_id,
                "report_kind": "internal",
                "review_state": "DRAFT_UNAPPROVED",
                "method_status": "EXPERIMENTAL_AIA",
                "client_facing": False,
                **REVIEW_STAMP_RECORD,
            },
        )
        session.commit()
    before = _jobs_count(app)
    for person in (researcher, outsider):
        refused = person.post(
            f"{_runs(world)}/{run_id}/report/approve", json={"artifact_id": stored.artifact_id}
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "report_not_approvable"
    with factory() as session:
        row = session.get(ProjectArtifactRow, stored.artifact_id)
        assert row is not None and not row.is_approved and not row.is_frozen
        decisions = session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_id == stored.artifact_id)
        ).all()
    assert decisions == []
    assert _jobs_count(app) == before  # nothing asked for its PDF either


def _jobs_count(app: FastAPI) -> int:
    with create_session_factory(app.state.engine)() as session:
        return int(session.scalar(select(func.count()).select_from(WorkflowRunRow)) or 0)


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
    # The gate's own code, which the web words as who fixes it (lead-orchestration LO12a).
    assert steps["run"]["error_reason"] == "egress_route_not_approved_for_class"
    assert steps["compile"]["error_reason"] is None
    assert steps["aggregate"]["status"] == steps["sociomap"]["status"] == "BLOCKED"
    assert run["artifact_ids"] == []
    # Waiting is not failure: it cannot be retried into a second run that waits for the same thing.
    refused = researcher.post(f"{_runs(world)}/{run_id}/retry")
    assert refused.status_code == 409 and refused.json()["code"] == "run_not_retryable"


def _close_study(app: FastAPI, world: Any) -> None:
    from aia_core.domain.scope import StudyStatus
    from aia_core.infrastructure.scope_repository import ScopeRepository

    with create_session_factory(app.state.engine)() as session:
        principal = AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        )
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        ScopeRepository(session).set_study_status(scope, StudyStatus.DELIVERED)
        session.commit()


def test_a_run_parked_for_the_runtime_goes_on_when_a_person_resumes_it(
    app: FastAPI, researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """PC4: no timer resumes a runtime park and a retry refuses a waiting run, so the run
    waited for ever once the runtime was on. A person lets the same run go on."""
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    off = _worker(app, FailureClass.RUNTIME_UNAVAILABLE)
    while off.run_once() is not None:
        pass
    url = f"{_runs(world)}/{run_id}/resume"
    # Under another study's path the run is not there to resume, whoever asks.
    elsewhere = other_client_lead.post(f"{_runs(world, 'other_client')}/{run_id}/resume")
    assert elsewhere.status_code == 404

    resumed = researcher.post(url)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["run_id"] == run_id and resumed.json()["phase"] != "WAITING"
    fieldwork = next(s for s in resumed.json()["steps"] if s["node_key"] == "run")
    assert (fieldwork["status"], fieldwork["waiting_reason"]) == ("RUNNABLE", None)
    # Nothing waits for the runtime any more: a second press is refused by name.
    again = researcher.post(url)
    assert again.status_code == 409 and again.json()["code"] == "runtime_park_not_resumable"

    # Still off: the step parks again, without spending an attempt, and can be resumed again.
    while off.run_once() is not None:
        pass
    parked = researcher.get(f"{_runs(world)}/{run_id}").json()
    fieldwork = next(s for s in parked["steps"] if s["node_key"] == "run")
    assert fieldwork["waiting_reason"] == "ai_runtime_unavailable"
    assert researcher.post(url).status_code == 200

    # On: the same run goes on from fieldwork; nothing before it ran twice, no second run.
    on = _worker(app, None)
    assert on.run_once() is not None
    steps = {s["node_key"]: s for s in researcher.get(f"{_runs(world)}/{run_id}").json()["steps"]}
    assert steps["run"]["status"] == "SUCCEEDED"
    assert steps["compile"]["attempts_recorded"] == steps["preflight"]["attempts_recorded"] == 1
    assert [r["run_id"] for r in researcher.get(_runs(world)).json()["items"]] == [run_id]


def test_resuming_a_run_refuses_one_that_waits_for_nothing_and_a_closed_study(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    url = f"{_runs(world)}/{run_id}/resume"
    queued = researcher.post(url)
    assert queued.status_code == 409 and queued.json()["code"] == "runtime_park_not_resumable"

    off = _worker(app, FailureClass.RUNTIME_UNAVAILABLE)
    while off.run_once() is not None:
        pass
    _close_study(app, world)
    closed = researcher.post(url)
    assert closed.status_code == 403 and closed.json()["code"] == "study_closed"
    fieldwork = next(
        s
        for s in researcher.get(f"{_runs(world)}/{run_id}").json()["steps"]
        if s["node_key"] == "run"
    )
    assert fieldwork["status"] == "WAITING_PROVIDER"


def _stop_for_recovery(app: FastAPI, run_id: str, node_key: str, *, uncertain: bool) -> None:
    """A step stopped for recovery, as the engine leaves it; ``uncertain``: its attempt sent a
    paid call whose outcome is unknown."""
    from aia_core.domain.workflow import StepRunStatus
    from aia_core.infrastructure.tables import StepAttemptRow, StepRunRow

    with create_session_factory(app.state.engine)() as session:
        step = session.scalars(
            select(StepRunRow).where(StepRunRow.run_id == run_id, StepRunRow.node_key == node_key)
        ).one()
        step.status = StepRunStatus.RECOVERY_REQUIRED.value
        step.attempts_recorded = 1
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


def test_a_step_stopped_for_recovery_says_why_where_its_attempts_are_read(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """PC14: RECOVERY_REQUIRED keeps no waiting reason, so Průběh said nothing about why a step
    stopped and nothing repeated it. The run says it from its attempts; a listing, which reads
    none, says nothing rather than guess."""
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    _stop_for_recovery(app, run_id, "compile", uncertain=True)
    step = next(
        s
        for s in researcher.get(f"{_runs(world)}/{run_id}").json()["steps"]
        if s["node_key"] == "compile"
    )
    assert (step["status"], step["recovery_reason"]) == ("RECOVERY_REQUIRED", "paid_call_uncertain")
    others = researcher.get(f"{_runs(world)}/{run_id}").json()["steps"]
    assert all(s["recovery_reason"] is None for s in others if s["node_key"] != "compile")
    listed = researcher.get(f"{_runs(world)}?steps=true").json()["items"]
    assert all(s.get("recovery_reason") is None for r in listed for s in r.get("steps") or [])


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


def test_a_retry_of_an_old_method_run_is_refused_with_a_new_run_link_and_starts_nothing(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    from aia_core.domain.research_sociomap import SociomapMethod
    from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V1, AIA_SOCIOMAP_V3

    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    old = [SociomapMethod.of(s).model_dump(mode="json") for s in (AIA_SOCIOMAP_V1, AIA_SOCIOMAP_V3)]
    with create_session_factory(app.state.engine)() as session:
        # What a run stored under the old default holds: aia-sociomap-1 beside -3, and the
        # bare key every start that took a default had.
        row = session.get(WorkflowRunRow, run_id)
        assert row is not None
        row.metadata_json = {**row.metadata_json, "sociomap_methods": old}
        row.idempotency_key = f"research:{revision}"
        session.commit()
    worker = _worker(app, FailureClass.PERMISSION)
    while worker.run_once() is not None:
        pass
    assert researcher.get(f"{_runs(world)}/{run_id}").json()["retryable"] is True
    before = researcher.get(_runs(world)).json()["items"]
    refused = researcher.post(f"{_runs(world)}/{run_id}/retry")
    assert refused.status_code == 409, refused.text
    body = refused.json()
    assert body["code"] == "run_on_retired_method"
    details = body["details"]
    assert details["methods"] == ["aia-sociomap-1", "aia-sociomap-3"]
    assert details["new_run"] == {
        "method": "POST",
        "href": f"/api/v1/studies/{world.study_id('primary')}/research/runs",
        # The refused run's respondents, so the new run starts as it did.
        "body": {"design_revision_id": revision, "persona_source": "fictional_roster"},
    }
    assert researcher.get(_runs(world)).json()["items"] == before  # nothing started
    # The link starts a new run over the same revision, on aia-sociomap-5.
    new = researcher.post(details["new_run"]["href"], json=details["new_run"]["body"])
    assert new.status_code == 201, new.text
    assert new.json()["run_id"] != run_id
    assert new.json()["design_revision_id"] == revision


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
    # No analysis reservation is configured here, so the ceiling (LO23) is unknown: null, not 0.
    assert retryable.json() == {"run_id": run_id, "modules": [], "stale": [], "ceiling_usd": None}
    assert (
        researcher.get(f"{_runs(world)}/RUN-0000000000000000/analysis/retryable").status_code == 404
    )


def test_an_analysis_retry_refused_for_an_old_method_names_the_new_run(
    researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The route's answer when the application refuses (test_research_runs holds when it does:
    an old-default run whose map is not stored)."""
    from aia_core.application.research import ResearchRunOnRetiredMethod

    from aia_api.routers import research as research_router

    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    old = {
        "run_id": run_id,
        "metadata": {"design_revision_id": revision, "persona_source": "fictional_roster"},
    }

    def _refuse(*_: object, **__: object) -> object:
        raise ResearchRunOnRetiredMethod(old, ["aia-sociomap-1", "aia-sociomap-3"])

    monkeypatch.setattr(research_router, "retry_failed_modules", _refuse)
    refused = researcher.post(f"{_runs(world)}/{run_id}/analysis/retry")
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "run_on_retired_method"
    assert refused.json()["details"]["new_run"] == {
        "method": "POST",
        "href": f"/api/v1/studies/{world.study_id('primary')}/research/runs",
        "body": {"design_revision_id": revision, "persona_source": "fictional_roster"},
    }


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


def test_the_routing_switch_passes_a_valid_condition_and_pins_it_on_the_run(
    app: FastAPI, researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    """AIA_ROUTING_ENABLED (working-copy-edit-ops WCE13 (d)): off by default, a conditional
    question stops a run as before; on, a valid one passes and the run pins it."""
    assert Settings.model_fields["routing_enabled"].default is False
    filtered = {**DESIGN, "sections": [dict(DESIGN["sections"][0]), DESIGN["sections"][1]]}
    filtered["sections"][0]["questions"] = [
        *DESIGN["sections"][0]["questions"],
        {
            "id": "q3",
            "text": "Proč?",
            "typ": "otevrena",
            "filtr": {"question_id": "q2", "options": ["Nic"]},
        },
    ]
    revision = submit(researcher, world, filtered).json()["revision_id"]
    url = f"{API}/studies/{world.study_id()}/research/readiness"

    def conditional() -> dict[str, Any]:
        body = viewer.get(url, params={"design_revision_id": revision}).json()
        return next(c for c in body["checks"] if c["id"] == "conditional_questions")

    assert conditional()["status"] == "FAIL"
    assert start(researcher, world, revision).json()["code"] == "design_not_ready"
    app.state.settings = app.state.settings.model_copy(update={"routing_enabled": True})
    assert conditional()["status"] == "PASS"
    run = start(researcher, world, revision)
    assert run.status_code in (200, 201), run.text
    with create_session_factory(app.state.engine)() as session:
        row = session.get(WorkflowRunRow, run.json()["run_id"])
        assert row is not None and row.metadata_json["routing"] is True


def test_readiness_reads_a_working_revision_without_submitting_a_design(
    researcher: TestClient, viewer: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """Plan working-copy-edit-ops WCE7: a stage reads readiness on the working revision it
    shows. The answer is the one a submit of that revision reads, and nothing is written."""
    base = f"{API}/studies/{world.study_id()}"
    now = researcher.get(f"{base}/workspace/content").json().get("revision")
    saved = researcher.put(
        f"{base}/workspace/content", json={"content": DESIGN, "base_revision": now}
    )
    assert saved.status_code == 200, saved.text
    number = saved.json()["revision"]
    url = f"{base}/research/readiness/working"

    working = viewer.get(url, params={"working_revision": number})
    assert working.status_code == 200, working.text
    body = working.json()
    assert body["working_revision"] == number and "design_revision_id" not in body
    assert viewer.get(f"{base}/design/revisions").json()["items"] == [], "nothing was submitted"

    # The same answer a submit of that revision reads, but for the revision it names.
    revision_id = submit(researcher, world).json()["revision_id"]
    design = viewer.get(f"{base}/research/readiness", params={"design_revision_id": revision_id})
    same = {**design.json()}
    same.pop("design_revision_id")
    mine = {k: v for k, v in body.items() if k != "working_revision"}
    # Its acknowledgement digest names no Design Revision, so it never stands for a start's.
    assert mine["answerability"]["digest"] != same["answerability"]["digest"]
    mine["answerability"].pop("digest")
    same["answerability"].pop("digest")
    assert mine == same

    # A revision the Study never saved, or another study's, is not found.
    missing = viewer.get(url, params={"working_revision": number + 50})
    assert missing.status_code == 404 and missing.json()["code"] == "working_revision_not_found"
    assert viewer.get(url, params={"working_revision": 0}).status_code == 422
    other = f"{API}/studies/{world.study_id('other_client')}/research/readiness/working"
    assert other_client_lead.get(other, params={"working_revision": number}).status_code == 404


def test_impact_reads_each_stage_of_a_design_against_the_working_copy(
    researcher: TestClient, viewer: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """Plan working-copy-edit-ops WCE7, AC-07: a questionnaire edited after a design was
    submitted; its stage reads CHANGED, the stages after it RECHECK, those before CURRENT, and the
    Design Revision named is older than the working copy. Nothing is written."""
    base = f"{API}/studies/{world.study_id()}"
    url = f"{base}/research/impact"
    assert viewer.get(url, params={"working_revision": 1}).status_code == 404  # nothing saved
    made = submit(researcher, world).json()
    same = viewer.get(url, params={"working_revision": made["workspace_revision"]})
    assert same.status_code == 200, same.text
    assert {s["impact"] for s in same.json()["stages"]} == {"CURRENT"}
    assert same.json()["changed"] == []

    edited = {**DESIGN, "sections": [dict(DESIGN["sections"][0]), DESIGN["sections"][1]]}
    edited["sections"][0]["questions"] = [
        {**DESIGN["sections"][0]["questions"][0], "text": "Upravená otázka?"},
        *DESIGN["sections"][0]["questions"][1:],
    ]
    saved = researcher.put(
        f"{base}/workspace/content",
        json={"content": edited, "base_revision": made["workspace_revision"]},
    )
    assert saved.status_code == 200, saved.text
    body = viewer.get(url, params={"working_revision": saved.json()["revision"]}).json()
    assert body["design_revision_id"] == made["revision_id"]
    assert body["design_revision"] == made["revision"] and body["changed"] == ["sections"]
    impact = {s["stage"]: s["impact"] for s in body["stages"]}
    assert impact["BRIEF"] == "CURRENT" and impact["RESEARCH_DESIGN"] == "CURRENT"
    assert impact["QUESTIONNAIRE"] == "CHANGED" and impact["FIELDWORK"] == "CHANGED"
    assert impact["ANALYSIS"] == "RECHECK" and impact["REPORT"] == "RECHECK"
    assert len(viewer.get(f"{base}/design/revisions").json()["items"]) == 1, "nothing submitted"

    # A named revision of this Study; another study's, or an unknown one, is not found.
    named = viewer.get(
        url,
        params={
            "working_revision": saved.json()["revision"],
            "design_revision_id": made["revision_id"],
        },
    )
    assert named.json() == body
    missing = viewer.get(
        url, params={"working_revision": saved.json()["revision"], "design_revision_id": "REV-0"}
    )
    assert missing.status_code == 404 and missing.json()["code"] == "design_revision_not_found"
    other = f"{API}/studies/{world.study_id('other_client')}/research/impact"
    assert other_client_lead.get(other, params={"working_revision": 1}).status_code == 404


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

    # The full fictional chain completed: aggregate, and a Sociomap under aia-sociomap-5,
    # which the register approves for reports.
    assert run["status"] == "COMPLETED" and run["phase"] == "COMPLETED"
    aggregate_id, sociomap_id = steps["aggregate"]["artifact_id"], steps["sociomap"]["artifact_id"]
    aggregate = viewer.get(f"{_runs(world)}/{run_id}/artifacts/{aggregate_id}")
    assert aggregate.status_code == 200
    assert aggregate.json()["payload"]["aggregate"]["data_origin"] == "SYNTHETIC_FIXTURE"
    sociomap = researcher.get(f"{_runs(world)}/{run_id}/artifacts/{sociomap_id}")
    assert sociomap.status_code == 200
    assert sociomap.json()["payload"]["sociomap"]["methodology_status"] == "CLIENT_FACING"
    # ADR 0019: every member is a Researcher and reads it, a member who was never granted the
    # study included; respondent rows are still never inlined for anyone.
    internal = viewer.get(f"{_runs(world)}/{run_id}/artifacts/{sociomap_id}")
    assert internal.status_code == 200
    assert internal.json()["payload"]["sociomap"]["methodology_status"] == "CLIENT_FACING"
    for artifact_id in (spec_id, dataset_id, aggregate_id, sociomap_id):
        read = outsider.get(f"{_runs(world)}/{run_id}/artifacts/{artifact_id}")
        assert read.status_code == 200
        if artifact_id == dataset_id:
            assert read.json()["payload"] is None

    with create_session_factory(app.state.engine)() as session:
        # The working copy is owned too (study_workspace); the other owned project is the design.
        design_project = session.scalars(
            select(ProjectRow.project_id).where(ProjectRow.owner != "study_workspace")
        ).one()
    for artifact_id in (spec_id, dataset_id, aggregate_id, sociomap_id):
        generic = researcher.get(f"{projects_url()}/{design_project}/artifacts/{artifact_id}")
        assert generic.status_code == 404


def _finished_fictional_run(app: FastAPI, c: TestClient, world: Any, n: int) -> str:
    """A run of DESIGN at ``n`` respondents, on fictional fieldwork, to its end."""
    app.state.settings = app.state.settings.model_copy(
        update={"research_fieldwork_source": FieldworkSource.SYNTHETIC_FIXTURE}
    )
    run_id = str(
        start(c, world, submit(c, world, {**DESIGN, "n": n}).json()["revision_id"]).json()["run_id"]
    )
    worker = _real_worker(app, workbench=True)
    while worker.run_once() is not None:
        pass
    assert c.get(f"{_runs(world)}/{run_id}").json()["status"] == "COMPLETED"
    return run_id


def test_results_serve_admitted_rows_and_a_suppressed_number_never_leaves_the_api(
    app: FastAPI, researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    """evidence-integrity 6: Results decided suppression in the browser, over the raw aggregate,
    so a suppressed number reached the page. Here it is absent from the response."""
    small = _finished_fictional_run(app, researcher, world, n=60)
    answer = viewer.get(f"{_runs(world)}/{small}/results")
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["run_id"] == small and body["internal_only"] is True
    assert body["data_origin"] == "SYNTHETIC_FIXTURE"
    # Every question the specification asked, in its order: the two questions, then each object.
    ids = [q["question_id"] for q in body["questions"]]
    assert ids[:2] == ["q1", "q2"] and len(ids) == 2 + 5
    q2 = next(q for q in body["questions"] if q["question_id"] == "q2")
    assert [r["answer"] for r in q2["rows"] if r["metric"] == "pct"] == ["Kávu", "Čaj", "Nic"]
    q1 = body["questions"][0]
    assert [r["metric"] for r in q1["rows"]] == ["mean", "top2box_pct", "n", "effective_n"]
    # 60 fictional respondents fall below the effective-n guard: every row says why, none a number,
    # though the aggregate stored each.
    steps = {s["node_key"]: s for s in researcher.get(f"{_runs(world)}/{small}").json()["steps"]}
    aggregate = researcher.get(
        f"{_runs(world)}/{small}/artifacts/{steps['aggregate']['artifact_id']}"
    ).json()["payload"]["aggregate"]
    assert aggregate["questions"]["q2"]["celkem_pct"]["Kávu"] is not None
    for row in (r for q in body["questions"] for r in q["rows"]):
        assert row["support"] == "SUPPRESS" and row["value"] is None
        assert row["interval"] is None and row["effective_n"] is None
        # Why, as codes: the reasons' words name the effective n withheld.
        assert "below_effective_n" in row["reasons"]
        assert not any(ch.isdigit() for code in row["reasons"] for ch in code)

    large = _finished_fictional_run(app, researcher, world, n=450)
    rows = [
        r
        for q in viewer.get(f"{_runs(world)}/{large}/results").json()["questions"]
        for r in q["rows"]
    ]
    admitted = [r for r in rows if r["support"] in ("REPORTABLE", "INDICATIVE")]
    assert admitted
    for row in admitted:
        assert row["value"] is not None and not row["reasons"]
        if row["metric"] not in ("n", "effective_n"):
            low, high = row["interval"]
            assert low <= row["value"] <= high
    for row in rows:
        assert (row["value"] is None) == (row["support"] == "SUPPRESS")


def test_results_wait_for_the_aggregate_and_stay_in_their_study(
    researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    waiting = researcher.get(f"{_runs(world)}/{run_id}/results")
    assert waiting.status_code == 409
    assert waiting.json()["code"] == "results_unavailable"
    assert waiting.json()["details"]["reason"] == "missing_upstream"
    # Another study's path never finds this study's run.
    elsewhere = other_client_lead.get(f"{_runs(world, 'other_client')}/{run_id}/results")
    assert elsewhere.status_code == 404
    assert researcher.get(f"{_runs(world)}/RUN-0123abcd/results").status_code == 404


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


def test_results_over_a_corrupt_aggregate_keep_it_marked_corrupt(
    app: FastAPI,
    researcher: TestClient,
    world: Any,
    damage_artifact: Any,
    artifact_status: Any,
) -> None:
    """The results' read of a damaged source answers 409 and keeps its CORRUPT mark."""
    run_id = _finished_fictional_run(app, researcher, world, n=60)
    steps = {s["node_key"]: s for s in researcher.get(f"{_runs(world)}/{run_id}").json()["steps"]}
    aggregate_id = steps["aggregate"]["artifact_id"]
    damage_artifact(aggregate_id, "tampered")
    refused = researcher.get(f"{_runs(world)}/{run_id}/results")
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "artifact_corrupt"
    assert artifact_status(aggregate_id) == "CORRUPT"


# --------------------------------------------------------------------------- #
# Lifting a budget wait (plan 5b.1)
# --------------------------------------------------------------------------- #


def _park_first_step_on_budget(
    app: FastAPI, world: Any, who: str = "researcher", error: dict[str, Any] | None = None
) -> str:
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
            claimed.attempt_id,
            worker_id="budget-fixture",
            failure=FailureClass.BUDGET_EXCEEDED,
            error=error,
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


def test_the_runs_budget_lift_releases_the_run_and_is_refused_when_nothing_waits(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """CR-3: Progress lifts the run, not one step at a time."""
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    node = _park_first_step_on_budget(app, world)
    before = _study_budget(app, world)
    url = f"{_runs(world)}/{run_id}/budget"

    lower = researcher.post(url, json={"budget_usd": before - 1.0})
    assert lower.status_code == 422 and lower.json()["code"] == "budget_not_raised"
    lifted = researcher.post(url, json={"budget_usd": before + 20.0, "note": "běh"})
    assert lifted.status_code == 200, lifted.text
    assert next(s for s in lifted.json()["steps"] if s["node_key"] == node)["status"] == "RUNNABLE"
    again = researcher.post(url, json={"budget_usd": before + 40.0})
    assert again.status_code == 409 and again.json()["code"] == "not_waiting_for_budget"
    assert _study_budget(app, world) == before + 20.0
    assert (
        researcher.post(
            f"{_runs(world)}/RUN-0a1b2c/budget", json={"budget_usd": before + 1.0}
        ).status_code
        == 404
    )


def test_a_step_waiting_for_budget_says_what_it_needs_and_unknown_is_never_zero(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """FLD10: the worker records the refused hold (worker.py's BudgetExceeded); the run's read
    serves it, so the park note can say what the step needs. A stop with no price is unknown."""
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    node = _park_first_step_on_budget(
        app, world, error={"requested_usd": 1.25, "remaining_usd": 0.4, "budget_usd": 5.0}
    )
    read = researcher.get(f"{_runs(world)}/{run_id}").json()
    step = next(s for s in read["steps"] if s["node_key"] == node)
    assert step["status"] == "AWAITING_BUDGET"
    assert step["budget_need"] == {"requested_usd": 1.25, "remaining_usd": 0.4}
    # A listing reads no attempts: unknown there, never a guess.
    listed = researcher.get(_runs(world)).json()
    listed_run = next(r for r in listed["items"] if r["run_id"] == run_id)
    assert all(s["budget_need"] is None for s in listed_run["steps"])
    # Every other step needs nothing.
    assert all(s["budget_need"] is None for s in read["steps"] if s["node_key"] != node)


@pytest.mark.parametrize(
    "error",
    [
        {},  # a park that recorded only that it stopped (the gateway's reservation_exhausted)
        {"requested_usd": 0.0, "remaining_usd": 0.0},
        {"requested_usd": 1.0},
        {"requested_usd": 1.0, "remaining_usd": -0.5},
        {"requested_usd": "1.0", "remaining_usd": 0.0},
        {"requested_usd": True, "remaining_usd": 0.0},
    ],
)
def test_a_budget_stop_that_names_no_price_reads_unknown(
    app: FastAPI, researcher: TestClient, world: Any, error: dict[str, Any]
) -> None:
    run_id = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()[
        "run_id"
    ]
    node = _park_first_step_on_budget(app, world, error=error)
    step = next(
        s
        for s in researcher.get(f"{_runs(world)}/{run_id}").json()["steps"]
        if s["node_key"] == node
    )
    assert step["status"] == "AWAITING_BUDGET"
    assert step["budget_need"] is None


def test_a_recorded_amount_that_is_not_a_finite_number_reads_unknown() -> None:
    """What JSONB cannot hold (inf, NaN) never reaches the read from PostgreSQL; the rule still
    holds for any store that keeps them."""
    for value in (float("inf"), float("-inf"), float("nan"), True, "1.0", None, -0.01):
        assert research_router._usd(value) is None, value
    assert research_router._usd(0) == 0.0 and research_router._usd(1.5) == 1.5


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
    """Methodology-tab Z1, R1d, V1a: Results say which Sociomap, support, aggregation, response
    process and readiness limits a run pinned, and whether its response process is 18.6.6's."""
    revision_id = submit(researcher, world).json()["revision_id"]
    run = start(researcher, world, revision_id).json()
    assert run["methodology"] == {
        "sociomap": {"name": "aia-sociomap-5", "stored": False},
        "support": {"name": "aia-support-1", "stored": False},
        "aggregation": {"name": "aia-aggregate-1", "stored": False},
        "response": {"name": "aia-response-1", "stored": False},
        "readiness": {"name": "aia-readiness-1", "stored": False},
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
            "readiness_methodology": version("readiness", "aia-readiness-1+e2"),
        }
        session.commit()
    read = researcher.get(f"{_runs(world)}/{run['run_id']}").json()
    assert read["methodology"] == {
        "sociomap": {"name": "aia-sociomap-3+e1", "stored": True},
        "support": {"name": "aia-support-1+e2", "stored": True},
        "aggregation": {"name": "aia-aggregate-1+e1", "stored": True},
        "response": {"name": "aia-response-1+e1", "stored": True},
        "readiness": {"name": "aia-readiness-1+e2", "stored": True},
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
        "readiness": {"name": "aia-readiness-1", "stored": False},
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


def test_persona_topics_answer_each_dimension_before_any_run(
    researcher: TestClient, world: Any
) -> None:
    """artifact-dimensions DIM2: Dimenze's chip, from the mapping a run's receipt reads."""
    url = f"{API}/studies/{world.study_id()}/research/persona-topics"
    got = researcher.get(url, params=[("dimension", "ekologie"), ("dimension", "barva_obalu")])
    assert got.status_code == 200
    assert got.json()["items"] == [
        {"dimension": "ekologie", "topic": "eko"},
        {"dimension": "barva_obalu", "topic": None},
    ]
    assert researcher.get(url).json() == {"items": []}
    too_many = researcher.get(url, params=[("dimension", f"d{i}") for i in range(65)])
    assert too_many.status_code == 422
    assert researcher.get(url, params={"dimension": "x" * 81}).status_code == 422


def test_a_step_passes_on_a_stored_code_never_free_text() -> None:
    from aia_api.routers.research import _code

    assert _code("egress_route_not_approved_for_class") == "egress_route_not_approved_for_class"
    assert _code("Trasa není schválená.") is None
    assert _code(None) is None
    assert _code(3) is None


def test_a_report_a_module_holds_is_refused_naming_the_modules(
    researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Evidence-integrity 9b: the report with literature, asked for directly while a module states
    no supported finding, is refused with its reason and the modules in its details, so the
    screen says it in words (approvalRefusal) instead of the composer's English."""
    from aia_core.application.report import ReportCompositionRefused

    def held(*_a: Any, **_kw: Any) -> Any:
        raise ReportCompositionRefused(
            "waiting on: executive", reason="analysis_holds_report", modules=("executive",)
        )

    monkeypatch.setattr(research_router, "prepared_context_report", lambda *_a, **_kw: None)
    monkeypatch.setattr(research_router, "stored_contextual_report", held)
    refused = researcher.post(
        f"{_runs(world)}/RUN-000000/report/context",
        params={"deep_research_run_id": "RUN-000001"},
    )
    assert refused.status_code == 409, refused.text
    body = refused.json()
    assert body["code"] == "context_report_refused"
    assert body["details"] == {"reason": "analysis_holds_report", "modules": ["executive"]}


# --------------------------------------------------- map snapshots (report-delivery RD4)


def _fictional_map() -> dict[str, Any]:
    """A stored Sociomap result with one contract-3 object map, computed by the engine on
    fictional ratings, as the sociomap step stores it."""
    import random

    from aia_core.domain.sociomap import (
        AIA_SOCIOMAP_V3,
        ObjectMapInputs,
        RatingItem,
        compute_object_map,
    )

    rng = random.Random(92)
    objects = ("a", "b", "c", "d")
    inputs = ObjectMapInputs(
        respondent_ids=tuple(f"FIC-{i}" for i in range(40)),
        donor_ids=tuple(f"DONOR-{i // 2}" for i in range(40)),
        items=tuple(RatingItem(item_id=o, scale_min=1, scale_max=10) for o in objects),
        values=tuple(tuple(float(rng.randint(1, 10)) for _ in objects) for _ in range(40)),
        weights=(1.0,) * 40,
        object_ids=objects,
        object_items=objects,
        roles=dict.fromkeys(objects, "primary"),
    )
    artifact = compute_object_map(inputs, AIA_SOCIOMAP_V3, connectedness_interval=False)
    return {
        "batteries": [
            {
                "battery_id": "fictional",
                "title": "Fiktivní nabídky",
                "objects": [{"id": o, "label": f"Objekt {o}"} for o in objects],
                "maps": {AIA_SOCIOMAP_V3.methodology_version: artifact.to_payload()},
            }
        ],
        # As a run records its pinned methods: the register's approved -3, at its exact spec.
        "methods": [
            {
                "method_id": AIA_SOCIOMAP_V3.methodology_version,
                "spec_fingerprint": artifact.spec_fingerprint,
            }
        ],
    }


def _store_map(
    app: FastAPI, world: Any, run_id: str, body: dict[str, Any], *, reused: str | None = None
) -> str:
    """Drive the run's steps to the end, its sociomap step storing ``body``, or naming the map
    ``reused`` another run stored (as a retry reuses it); the map's id."""
    with create_session_factory(app.state.engine)() as session:
        principal = AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        )
        scope = ScopeResolver(session).study_context(principal, study_id=world.study_id())
        workflow = WorkflowRepository(session, scope)
        map_id = None
        while (work := workflow.claim_next(worker_id="map-fixture")) is not None:
            output: dict[str, Any] = {}
            if work.node_key == "sociomap" and reused:
                map_id = output["artifact_id"] = reused
            elif work.node_key == "sociomap":
                stored, _ = research_artifacts(session, scope, app.state.artifact_store).put_json(
                    project_id=work.project_id,
                    revision=work.project_revision,
                    stage_type="SOCIOMAP",
                    artifact_type="research_sociomap",
                    payload={"kind": "research_sociomap", "sociomap": body},
                    input_fingerprint=f"map-route-test-{run_id}",
                    produced_by_job_id=work.attempt_id,
                    metadata={"run_id": run_id},
                )
                map_id = output["artifact_id"] = stored.artifact_id
            workflow.complete_attempt(work.attempt_id, worker_id="map-fixture", output=output)
        session.commit()
    assert map_id is not None
    return map_id


def test_a_map_snapshot_is_drawn_on_the_server_from_the_stored_map_and_approved_once(
    app: FastAPI,
    researcher: TestClient,
    outsider: TestClient,
    other_client_lead: TestClient,
    world: Any,
) -> None:
    """RD4: the snapshot is the stored map drawn by the report's figure function, never the
    browser's bytes; stored once per map and view; its status is the register's for the map's
    method, read now; approved as any deliverable is, the run's starter its producer."""
    from aia_core.application.map_snapshots import MAP_SNAPSHOT_ARTIFACT_TYPE

    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    url = f"{_runs(world)}/{run_id}/map-snapshots"
    asked = {"battery_id": "fictional", "method": "aia-sociomap-3", "view": "top"}
    early = researcher.post(url, json=asked)
    assert early.status_code == 409 and early.json()["details"]["reason"] == "no_map"
    map_id = _store_map(app, world, run_id, _fictional_map())

    drawn = researcher.post(url, json=asked)
    assert drawn.status_code == 201, drawn.text
    snapshot = drawn.json()
    assert snapshot["status"] == "CLIENT_FACING"  # aia-sociomap-3 at its registered spec
    assert snapshot["camera"] is None and snapshot["view"] == "top"
    assert snapshot["review_state"] == "DRAFT_UNAPPROVED" and snapshot["approval"] is None
    again = researcher.post(url, json=asked)
    assert again.status_code == 200 and again.json()["artifact_id"] == snapshot["artifact_id"]
    side = researcher.post(url, json={**asked, "view": "3d"})
    assert side.status_code == 201 and side.json()["artifact_id"] != snapshot["artifact_id"]
    for wrong, reason in (
        ({**asked, "battery_id": "nowhere"}, "no_battery"),
        ({**asked, "method": "aia-sociomap-1"}, "no_method"),
    ):
        refused = researcher.post(url, json=wrong)
        assert refused.status_code == 409 and refused.json()["details"]["reason"] == reason

    one = f"{url}/{snapshot['artifact_id']}"
    png = researcher.get(f"{one}/download")
    assert png.status_code == 200 and png.content.startswith(b"\x89PNG")
    assert png.headers["content-type"] == "image/png"
    assert png.headers["x-aia-artifact-id"] == snapshot["artifact_id"]
    assert png.headers["content-disposition"].endswith(
        f'-mapa-fictional-top-klient-{snapshot["artifact_id"]}-koncept.png"'
    )
    # The same map and view draw the same bytes: the figure function fits nothing.
    from aia_core.domain.sociomap import read_object_maps
    from aia_core.infrastructure.report_docx.object_map_figure import object_map_snapshot

    battery = _fictional_map()["batteries"][0]
    ((_, artifact),) = read_object_maps(battery)
    labels = {o["id"]: o["label"] for o in battery["objects"]}
    assert png.content == object_map_snapshot(artifact, labels, "top")
    with create_session_factory(app.state.engine)() as session:
        stored = session.scalars(
            select(ProjectArtifactRow).where(
                ProjectArtifactRow.artifact_id == snapshot["artifact_id"]
            )
        ).one()
        assert stored.artifact_type == MAP_SNAPSHOT_ARTIFACT_TYPE
        assert stored.artifact_metadata["map_artifact_id"] == map_id
        assert stored.produced_by_user_id is None  # code drew it; no person is its producer

    foreign = f"{_runs(world, 'other_client')}/{run_id}/map-snapshots/{snapshot['artifact_id']}"
    assert other_client_lead.get(foreign).status_code == 404
    # The run is found before its row is locked: a run outside the study is 404, never 500.
    assert other_client_lead.post(f"{foreign}/approve", json={}).status_code == 404
    # A member of another organization finds neither the study nor its snapshot.
    from aia_core.infrastructure.scope_repository import ScopeRepository

    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).create_organization(
            slug="elsewhere", name="Elsewhere", owner_email="o@elsewhere.example"
        )
        session.commit()
    app.state.identity_provider.register(
        "token-elsewhere", subject="o@elsewhere.example", email="o@elsewhere.example"
    )
    stranger = TestClient(app)
    stranger.headers.update({"Authorization": "Bearer token-elsewhere"})
    for path in ("", "/download"):
        assert stranger.get(f"{url}/{snapshot['artifact_id']}{path}").status_code == 404
    assert stranger.post(url, json=asked).status_code == 404
    approved = outsider.post(f"{one}/approve", json={"note": "Zkontrolováno."})
    assert approved.status_code == 200, approved.text
    assert approved.json()["review_state"] == "APPROVED_INTERNAL"
    assert approved.json()["approval"]["note"] == "Zkontrolováno."
    with create_session_factory(app.state.engine)() as session:
        rows = session.scalars(
            select(ApprovalDecisionRow).where(
                ApprovalDecisionRow.subject_id == snapshot["artifact_id"]
            )
        ).all()
    assert [r.subject_type for r in rows] == ["artifact"]  # one ledger shape
    assert outsider.post(f"{one}/approve", json={}).status_code == 200  # once: nothing new
    with create_session_factory(app.state.engine)() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ApprovalDecisionRow)
                .where(ApprovalDecisionRow.subject_id == snapshot["artifact_id"])
            )
            == 1
        )


def test_the_run_starter_may_not_approve_a_map_snapshot_under_independent_review(
    app: FastAPI, owner: TestClient, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    _store_map(app, world, run_id, _fictional_map())
    url = f"{_runs(world)}/{run_id}/map-snapshots"
    # The reviewer asks for it: the run's work all the same, not theirs.
    snapshot = outsider.post(
        url, json={"battery_id": "fictional", "method": "aia-sociomap-3", "view": "top"}
    ).json()
    forbid = owner.put(
        f"{API}/self-approval", json={"allowed": False, "client_id": world.client_id()}
    )
    assert forbid.status_code == 200, forbid.text
    own = researcher.post(f"{url}/{snapshot['artifact_id']}/approve", json={})
    assert own.status_code == 403 and own.json()["code"] == "separation_of_duties"
    assert outsider.post(f"{url}/{snapshot['artifact_id']}/approve", json={}).status_code == 200


def test_a_snapshot_of_a_method_the_register_does_not_approve_is_internal() -> None:
    """The register's status, read at every read: -3 at another specification is no method it
    approved, so its snapshot is internal whatever its review."""
    from aia_core.application.map_snapshots import _status
    from aia_core.domain.sociomap_register import MethodologyStatus

    body = _fictional_map()
    assert _status(body, "aia-sociomap-3") is MethodologyStatus.CLIENT_FACING
    body["methods"][0]["spec_fingerprint"] = "0" * 64
    assert _status(body, "aia-sociomap-3") is MethodologyStatus.INTERNAL_ONLY
    assert _status({}, "aia-sociomap-3") is MethodologyStatus.INTERNAL_ONLY
    # A stored methodology edit is another method, whatever its base: never the register's.
    edited = _fictional_map()
    edited["methods"][0]["formulas"] = {"relation": "fiktivní"}
    assert _status(edited, "aia-sociomap-3") is MethodologyStatus.INTERNAL_ONLY


@pytest.mark.parametrize("unapproved", ["another_spec", "stored_edit"])
def test_a_map_the_register_does_not_approve_is_internal_through_every_route_and_its_approval(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any, unapproved: str
) -> None:
    """The snapshot's status is the register's for the map's method, read at every read: a
    method at a specification the register never approved, or a stored methodology edit of an
    approved one, is INTERNAL_ONLY when drawn, read and downloaded, and approving the snapshot
    does not make it the client's."""
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    body = _fictional_map()
    if unapproved == "another_spec":
        body["methods"][0]["spec_fingerprint"] = "0" * 64
    else:
        body["methods"][0]["formulas"] = {"relation": "fiktivní"}
    _store_map(app, world, run_id, body)
    url = f"{_runs(world)}/{run_id}/map-snapshots"
    drawn = researcher.post(
        url, json={"battery_id": "fictional", "method": "aia-sociomap-3", "view": "top"}
    )
    assert drawn.status_code == 201 and drawn.json()["status"] == "INTERNAL_ONLY"
    one = f"{url}/{drawn.json()['artifact_id']}"
    assert researcher.get(one).json()["status"] == "INTERNAL_ONLY"
    name = researcher.get(f"{one}/download").headers["content-disposition"]
    assert name.endswith(f'-interni-{drawn.json()["artifact_id"]}-koncept.png"')
    approved = outsider.post(f"{one}/approve", json={})
    assert approved.status_code == 200 and approved.json()["status"] == "INTERNAL_ONLY"
    name = researcher.get(f"{one}/download").headers["content-disposition"]
    assert name.endswith(f'-interni-{drawn.json()["artifact_id"]}-schvaleno.png"')


def test_two_first_asks_of_one_snapshot_store_one(
    app: FastAPI, researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A double click: the second ask waits on the run's lock and answers the first's
    snapshot, never a second one under the same key. PostgreSQL only: the guard is a row lock,
    which SQLite does not take (it serialises writers instead)."""
    import threading

    from aia_core.application import map_snapshots
    from aia_core.infrastructure.artifact_repository import ArtifactRepository

    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    _store_map(app, world, run_id, _fictional_map())
    first_in, second_stored = threading.Event(), threading.Event()
    real = ArtifactRepository.put

    def held(self: ArtifactRepository, **kw: Any) -> Any:
        stored = real(self, **kw)
        if kw.get("artifact_type") != "research_map_snapshot":
            return stored
        if not first_in.is_set():
            # The first ask: its snapshot stored, not yet committed. Held until the second
            # has stored one too (no lock), or for 10 s (the second waits on the lock).
            first_in.set()
            second_stored.wait(10)
        else:
            second_stored.set()
        return stored

    monkeypatch.setattr(ArtifactRepository, "put", held)
    factory = create_session_factory(app.state.engine)
    ids: list[str] = []
    errors: list[BaseException] = []

    def ask() -> None:
        try:
            with factory() as own:
                principal = AuthenticatedPrincipal(
                    user_id=world.users["researcher"], organization_id=world.organization_id
                )
                scope = ScopeResolver(own).study_context(principal, study_id=world.study_id())
                found, _created = map_snapshots.map_snapshot(
                    own,
                    scope,
                    app.state.artifact_store,
                    run_id=run_id,
                    battery_id="fictional",
                    method="aia-sociomap-3",
                    view="top",
                )
                own.commit()
                ids.append(found.artifact.artifact_id)
        except BaseException as exc:  # reported below, never swallowed
            errors.append(exc)

    a = threading.Thread(target=ask)
    a.start()
    assert first_in.wait(30)
    b = threading.Thread(target=ask)
    b.start()
    a.join(30)
    b.join(30)
    assert not errors, errors
    assert len(ids) == 2 and ids[0] == ids[1]
    with create_session_factory(app.state.engine)() as session:
        stored = session.scalar(
            select(func.count())
            .select_from(ProjectArtifactRow)
            .where(ProjectArtifactRow.artifact_type == "research_map_snapshot")
        )
    assert stored == 1


def test_a_run_that_reuses_another_runs_map_gets_a_snapshot_of_its_own(
    app: FastAPI, researcher: TestClient, outsider: TestClient, world: Any
) -> None:
    """A run whose sociomap step reuses the map another run stored (a retry does) is drawn its
    own snapshot: found through it, read, downloaded and approved under it, never the other
    run's, which it could not read."""
    import copy

    first = start(researcher, world, submit(researcher, world).json()["revision_id"]).json()
    map_id = _store_map(app, world, first["run_id"], _fictional_map())
    other = copy.deepcopy(DESIGN)
    other["title"] = "Fiktivní studie, druhá revize"
    second = start(researcher, world, submit(researcher, world, other).json()["revision_id"]).json()
    assert first["run_id"] != second["run_id"]
    _store_map(app, world, second["run_id"], {}, reused=map_id)
    asked = {"battery_id": "fictional", "method": "aia-sociomap-3", "view": "top"}
    ids = []
    for run in (first, second):
        url = f"{_runs(world)}/{run['run_id']}/map-snapshots"
        drawn = researcher.post(url, json=asked)
        assert drawn.status_code == 201, drawn.text
        one = f"{url}/{drawn.json()['artifact_id']}"
        assert researcher.get(one).status_code == 200
        assert researcher.get(f"{one}/download").status_code == 200
        assert outsider.post(f"{one}/approve", json={}).status_code == 200
        ids.append(drawn.json()["artifact_id"])
    assert ids[0] != ids[1]


def test_two_approvals_of_one_snapshot_at_once_record_one_decision(
    app: FastAPI, researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Approve once: the second approval waits on the run's lock, then reads the snapshot
    approved and records nothing. PostgreSQL only, as the store race above."""
    import threading

    from aia_core.application import map_snapshots
    from aia_core.infrastructure.artifact_repository import ArtifactRepository

    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    revision = submit(researcher, world).json()["revision_id"]
    run_id = start(researcher, world, revision).json()["run_id"]
    _store_map(app, world, run_id, _fictional_map())
    snapshot = researcher.post(
        f"{_runs(world)}/{run_id}/map-snapshots",
        json={"battery_id": "fictional", "method": "aia-sociomap-3", "view": "top"},
    ).json()["artifact_id"]
    first_in, second_in = threading.Event(), threading.Event()
    real = ArtifactRepository.approve

    def held(self: ArtifactRepository, artifact_id: str, **kw: Any) -> Any:
        approved = real(self, artifact_id, **kw)
        if not first_in.is_set():
            # The first approval: recorded, not yet committed. Held until the second has
            # recorded one too (no lock), or for 10 s (the second waits on the lock).
            first_in.set()
            second_in.wait(10)
        else:
            second_in.set()
        return approved

    monkeypatch.setattr(ArtifactRepository, "approve", held)
    factory = create_session_factory(app.state.engine)
    errors: list[BaseException] = []

    def approve(user: str) -> None:
        try:
            with factory() as own:
                principal = AuthenticatedPrincipal(
                    user_id=world.users[user], organization_id=world.organization_id
                )
                scope = ScopeResolver(own).study_context(principal, study_id=world.study_id())
                map_snapshots.approve_map_snapshot(
                    own, scope, app.state.artifact_store, run_id=run_id, artifact_id=snapshot
                )
                own.commit()
        except BaseException as exc:  # reported below, never swallowed
            errors.append(exc)

    a = threading.Thread(target=approve, args=("outsider",))
    a.start()
    assert first_in.wait(30)
    b = threading.Thread(target=approve, args=("lead",))
    b.start()
    a.join(30)
    b.join(30)
    assert not errors, errors
    with create_session_factory(app.state.engine)() as session:
        decisions = session.scalar(
            select(func.count())
            .select_from(ApprovalDecisionRow)
            .where(ApprovalDecisionRow.subject_id == snapshot)
        )
    assert decisions == 1
