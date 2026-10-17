"""The report with a chosen review over HTTP: one draft, read only (research-integrity-report 3).

Preparing composes and stores the variant and asks the worker for its PDF; every GET reads what
was prepared and changes nothing, so a closed study still downloads and the status, the DOCX, the
PDF and the approval name one draft. The draft here is fictional bytes stored in-process the way
the prepare stores it; composing a real one needs a completed run and review, which the executor
journey covers (test_analysis_executor.py).
"""

from __future__ import annotations

from typing import Any

from aia_core.application.contextual_report import (
    CONTEXT_REPORT_ARTIFACT_TYPE,
    CONTEXT_REPORT_CONTRACT,
)
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.scope import StudyStatus
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import WorkflowRunRow
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

API = "/api/v1"
REVIEW = "RUN-feedfeed"
DESIGN = {
    "title": "Fiktivní studie",
    "n": 50,
    "sections": [
        {
            "type": "questions",
            "questions": [{"id": "q1", "text": "Jak často?", "typ": "skala", "skala": [1, 5]}],
        }
    ],
}


def _study(world: Any, name: str = "primary") -> str:
    return f"{API}/studies/{world.study_id(name)}"


def _scope(session: Any, world: Any) -> Any:
    return ScopeResolver(session).study_context(
        AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        ),
        study_id=world.study_id(),
    )


def _prepared(
    app: FastAPI,
    researcher: TestClient,
    world: Any,
    *,
    ask_pdf: bool = True,
    contract: str = CONTEXT_REPORT_CONTRACT,
) -> tuple[str, str]:
    """A run, and the variant's draft stored and (``ask_pdf``) its PDF asked for, as the
    prepare does; without it, as a draft whose PDF nobody asked for yet. ``contract``: the
    composition contract the draft was stored under."""
    made = researcher.post(
        f"{_study(world)}/design/revisions", json={"content": DESIGN, "source_stage": "run"}
    )
    assert made.status_code in (200, 201), made.text
    started = researcher.post(
        f"{_study(world)}/research/runs", json={"design_revision_id": made.json()["revision_id"]}
    )
    assert started.status_code == 201, started.text
    run_id = started.json()["run_id"]
    with create_session_factory(app.state.engine)() as session:
        scope = _scope(session, world)
        runs = ResearchRuns(session, scope)
        project_id = runs.design_project_id()
        assert project_id is not None
        docx, _ = research_artifacts(session, scope, app.state.artifact_store).put(
            project_id=project_id,
            revision=made.json()["revision"],
            stage_type="REPORT",
            artifact_type=CONTEXT_REPORT_ARTIFACT_TYPE,
            data=b"PK fictional draft with literature",
            input_fingerprint="fictional",
            metadata={
                "run_id": run_id,
                "deep_research_run_id": REVIEW,
                "report_kind": "internal",
                "report_contract": contract,
            },
        )
        if ask_pdf:
            runs.request_report_pdf(docx=docx, run_id=run_id, deep_research_run_id=REVIEW)
        session.commit()
    return run_id, docx.artifact_id


def _jobs(app: FastAPI) -> int:
    with create_session_factory(app.state.engine)() as session:
        return int(session.scalar(select(func.count()).select_from(WorkflowRunRow)) or 0)


def test_the_status_names_the_prepared_draft_and_its_pdf_and_composes_nothing(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    run_id, artifact_id = _prepared(app, researcher, world)
    before = _jobs(app)
    url = f"{_study(world)}/research/runs/{run_id}/report/context"
    status_ = researcher.get(url, params={"deep_research_run_id": REVIEW})
    assert status_.status_code == 200, status_.text
    body = status_.json()
    assert body["state"] == "READY" and body["artifact_id"] == artifact_id
    assert body["review_state"] == "DRAFT_UNAPPROVED"
    assert body["pdf"]["state"] == "RENDERING" and body["pdf"]["artifact_id"] is None
    other = researcher.get(url, params={"deep_research_run_id": "RUN-abcabc"})
    assert other.json()["state"] == "NOT_PREPARED" and other.json()["pdf"] is None
    assert _jobs(app) == before


def test_a_draft_of_an_older_composition_contract_is_prepared_again_never_served(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Review 2: drafts stored under aia-contextual-report-3 (the Fio run's, 2026-10-16) read
    READY for ever, and the page, which prepares only a variant NOT_PREPARED, never composed one
    under the current contract."""
    run_id, _ = _prepared(app, researcher, world, contract="aia-contextual-report-3")
    base = f"{_study(world)}/research/runs/{run_id}/report/context"
    body = researcher.get(base, params={"deep_research_run_id": REVIEW}).json()
    assert body["state"] == "NOT_PREPARED" and body["artifact_id"] is None
    download = researcher.get(f"{base}/download", params={"deep_research_run_id": REVIEW})
    assert download.status_code == 409
    assert download.json()["code"] == "context_report_not_prepared"


def test_the_docx_download_is_the_prepared_draft_and_the_pdf_waits_for_its_rendering(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    run_id, artifact_id = _prepared(app, researcher, world)
    base = f"{_study(world)}/research/runs/{run_id}/report/context"
    docx = researcher.get(f"{base}/download", params={"deep_research_run_id": REVIEW})
    assert docx.status_code == 200, docx.text
    assert docx.content == b"PK fictional draft with literature"
    assert docx.headers["X-AIA-Artifact-Id"] == artifact_id
    assert docx.headers["X-AIA-Review-State"] == "DRAFT_UNAPPROVED"
    assert f"{run_id}-{REVIEW}.docx" in docx.headers["Content-Disposition"]
    pdf = researcher.get(f"{base}/pdf/download", params={"deep_research_run_id": REVIEW})
    assert pdf.status_code == 404  # asked for, not rendered yet: never another file instead


def test_a_closed_study_still_downloads_and_no_job_is_made(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    run_id, artifact_id = _prepared(app, researcher, world)
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).set_study_status(_scope(session, world), StudyStatus.DELIVERED)
        session.commit()
    before = _jobs(app)
    url = f"{_study(world)}/research/runs/{run_id}/report/context/download"
    got = researcher.get(url, params={"deep_research_run_id": REVIEW})
    assert got.status_code == 200, got.text
    assert got.headers["X-AIA-Artifact-Id"] == artifact_id
    assert _jobs(app) == before


def test_another_clients_study_finds_no_variant(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    run_id, _ = _prepared(app, researcher, world)
    foreign = f"{_study(world, 'other_client')}/research/runs/{run_id}/report/context"
    params = {"deep_research_run_id": REVIEW}
    assert researcher.get(foreign, params=params).status_code == 404
    assert researcher.get(f"{foreign}/download", params=params).status_code == 404
    assert researcher.get(f"{foreign}/pdf/download", params=params).status_code == 404


def test_a_closed_study_finds_its_draft_and_says_why_its_pdf_waits(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Review, 2026-10-16: the draft was found only through its PDF job, and a delivered study
    starts no job, so its report with literature could be had in no format. The draft is found
    as itself; its PDF says why nothing was asked, and asking makes nothing."""
    run_id, artifact_id = _prepared(app, researcher, world, ask_pdf=False)
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).set_study_status(_scope(session, world), StudyStatus.DELIVERED)
        session.commit()
    before = _jobs(app)
    base = f"{_study(world)}/research/runs/{run_id}/report/context"
    params = {"deep_research_run_id": REVIEW}
    body = researcher.get(base, params=params).json()
    assert body["state"] == "READY" and body["artifact_id"] == artifact_id
    assert body["pdf"] == {
        "state": "NOT_REQUESTED",
        "artifact_id": None,
        "sha256": None,
        "size_bytes": None,
        "reason": "study_closed",
        "askable": False,
    }
    asked = researcher.post(f"{base}/pdf", params=params)
    assert asked.status_code == 200, asked.text
    assert asked.json()["pdf"]["reason"] == "study_closed"
    assert _jobs(app) == before
    docx = researcher.get(f"{base}/download", params=params)
    assert docx.status_code == 200 and docx.headers["X-AIA-Artifact-Id"] == artifact_id


def test_preparing_answers_the_stored_draft_and_asks_for_its_pdf_once(
    app: FastAPI, researcher: TestClient, world: Any, monkeypatch: Any
) -> None:
    """The prepare route's own path (review 2: only its refusals were tested): the draft it
    stores is the one it answers with, its PDF is asked for in the same request, and preparing
    again starts nothing new. Composition is the executor journey's; here it returns the draft
    stored the way it stores one."""
    from aia_api.routers import research as routes

    run_id, artifact_id = _prepared(app, researcher, world, ask_pdf=False)

    def stored(session: Any, scope: Any, store: Any, **_: Any) -> tuple[Any, bytes]:
        return research_artifacts(session, scope, store).get(artifact_id), b""

    monkeypatch.setattr(routes, "stored_contextual_report", stored)
    url = f"{_study(world)}/research/runs/{run_id}/report/context"
    params = {"deep_research_run_id": REVIEW}
    before = _jobs(app)
    prepared = researcher.post(url, params=params)
    assert prepared.status_code == 200, prepared.text
    body = prepared.json()
    assert body["state"] == "READY" and body["artifact_id"] == artifact_id
    assert body["pdf"]["state"] == "RENDERING" and body["pdf"]["askable"] is False
    assert _jobs(app) == before + 1
    again = researcher.post(url, params=params)
    assert again.status_code == 200 and again.json()["artifact_id"] == artifact_id
    assert _jobs(app) == before + 1
    assert researcher.get(url, params=params).json()["artifact_id"] == artifact_id


def test_asking_again_renders_the_prepared_draft_once_and_never_composes(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Review, 2026-10-16: asking for the PDF again went through the whole composition, which
    a later deploy can refuse though the draft is stored. It asks for the draft itself."""
    run_id, artifact_id = _prepared(app, researcher, world, ask_pdf=False)
    base = f"{_study(world)}/research/runs/{run_id}/report/context"
    params = {"deep_research_run_id": REVIEW}
    assert researcher.get(base, params=params).json()["pdf"]["askable"] is True
    before = _jobs(app)
    asked = researcher.post(f"{base}/pdf", params=params)
    assert asked.status_code == 200, asked.text
    assert asked.json()["artifact_id"] == artifact_id
    assert asked.json()["pdf"]["state"] == "RENDERING" and asked.json()["pdf"]["askable"] is False
    assert _jobs(app) == before + 1
    # Asking while it renders is the same job.
    assert researcher.post(f"{base}/pdf", params=params).json()["pdf"]["state"] == "RENDERING"
    assert _jobs(app) == before + 1


def test_asking_for_a_pdf_before_preparing_is_refused_by_name(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    run_id, _ = _prepared(app, researcher, world)
    url = f"{_study(world)}/research/runs/{run_id}/report/context/pdf"
    refused = researcher.post(url, params={"deep_research_run_id": "RUN-abcabc"})
    assert refused.status_code == 409 and refused.json()["code"] == "context_report_not_prepared"
