"""The report with a chosen review over HTTP: one draft, read only (research-integrity-report 3).

Preparing composes and stores the variant and asks the worker for its PDF; every GET reads what
was prepared and changes nothing, so a closed study still downloads and the status, the DOCX, the
PDF and the approval name one draft. The draft here is fictional bytes stored in-process the way
the prepare stores it; composing a real one needs a completed run and review, which the executor
journey covers (test_analysis_executor.py).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from aia_core.application.contextual_report import (
    CONTEXT_REPORT_ARTIFACT_TYPE,
    CONTEXT_REPORT_CONTRACT,
)
from aia_core.application.report import INTERNAL_REPORT_PDF_ARTIFACT_TYPE
from aia_core.application.report_export import REVIEW_STAMP_RECORD
from aia_core.application.research import ResearchRuns, report_pdf_key, research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.evidence import ClaimSurface
from aia_core.domain.evidence.validation import METHOD_STATUS_PENDING
from aia_core.domain.report.evidence import EvidenceLedger
from aia_core.domain.report.model import (
    Classification,
    Paragraph,
    ReportDocument,
    ReportKind,
    ReportMeta,
    Section,
    text,
)
from aia_core.domain.report.review import ReviewMark, ReviewState
from aia_core.domain.scope import StudyStatus
from aia_core.domain.workflow_templates import REPORT_PDF, REPORT_PDF_STEP_KIND
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import WorkflowRunRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
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
    stampable: bool = False,
) -> tuple[str, str]:
    """A run, and the variant's draft stored and (``ask_pdf``) its PDF asked for, as the
    prepare does; without it, as a draft whose PDF nobody asked for yet. ``contract``: the
    composition contract the draft was stored under. ``stampable``: a real report laid out
    with its status in its footers, recorded so (D2); else fictional bytes, which a version
    stored before that layout stands for."""
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
            data=_rendered() if stampable else b"PK fictional draft with literature",
            input_fingerprint="fictional",
            metadata={
                "run_id": run_id,
                "deep_research_run_id": REVIEW,
                "report_kind": "internal",
                "report_contract": contract,
                **(REVIEW_STAMP_RECORD if stampable else {}),
            },
        )
        if ask_pdf:
            runs.request_report_pdf(
                docx=docx,
                run_id=run_id,
                deep_research_run_id=REVIEW,
                mark=ReviewMark(ReviewState.DRAFT, docx.artifact_id, docx.sha256),
            )
        session.commit()
    return run_id, docx.artifact_id


_RENDERED: list[bytes] = []


def _rendered() -> bytes:
    """A real report with literature as the renderer lays it out, rendered once."""
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
        section = Section("Literatura", (Paragraph(text("Fiktivní rešerše.")),))
        _RENDERED.append(DocxRenderer().render(ReportDocument(meta, (section,), ledger)))
    return _RENDERED[0]


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
    # Fictional bytes without the record of the footer layout: never stamped (D2).
    assert body["approved_on"] is None and body["stamped"] is False
    assert body["pdf"]["state"] == "RENDERING" and body["pdf"]["artifact_id"] is None
    # Its PDF not made yet: whether approving gives the approved version one is not known.
    assert body["approval_renders_pdf"] is False
    other = researcher.get(url, params={"deep_research_run_id": "RUN-abcabc"})
    assert other.json()["state"] == "NOT_PREPARED" and other.json()["pdf"] is None
    assert _jobs(app) == before


def _store_draft(app: FastAPI, world: Any, run_id: str, data: bytes, contract: str) -> str:
    """Another draft of the variant, stored the way the prepare stores one."""
    with create_session_factory(app.state.engine)() as session:
        scope = _scope(session, world)
        project_id = ResearchRuns(session, scope).design_project_id()
        assert project_id is not None
        draft, _ = research_artifacts(session, scope, app.state.artifact_store).put(
            project_id=project_id,
            revision=1,
            stage_type="REPORT",
            artifact_type=CONTEXT_REPORT_ARTIFACT_TYPE,
            data=data,
            input_fingerprint=f"fictional-{contract}",
            metadata={
                "run_id": run_id,
                "deep_research_run_id": REVIEW,
                "report_kind": "internal",
                "report_contract": contract,
            },
        )
        session.commit()
    return draft.artifact_id


def test_a_draft_of_an_earlier_contract_stays_the_report_and_says_it_is_earlier(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Review 2: drafts stored under aia-contextual-report-3 (the Fio run's, 2026-10-16) read as
    current for ever, and the page never composed one under today's contract. Review 3: hiding
    them instead lost a prepared, possibly approved, report whenever composing it again is
    refused. An earlier draft stays the report, downloadable and approvable, and says it is
    earlier, so the page offers to prepare it anew.

    Changed on purpose (cross-review interactions#5): this test used to end with a draft of
    today's contract, prepared after the earlier one was approved, becoming the report. That
    left the approved version downloadable in neither format. The approved version now stays
    the report; a draft displaces only a draft (the next test)."""
    run_id, artifact_id = _prepared(app, researcher, world, contract="aia-contextual-report-3")
    base = f"{_study(world)}/research/runs/{run_id}/report/context"
    params = {"deep_research_run_id": REVIEW}
    body = researcher.get(base, params=params).json()
    assert body["state"] == "READY" and body["artifact_id"] == artifact_id
    assert body["contract"] == "aia-contextual-report-3" and body["contract_current"] is False
    download = researcher.get(f"{base}/download", params=params)
    assert download.status_code == 200 and download.headers["X-AIA-Artifact-Id"] == artifact_id
    approved = researcher.post(
        f"{_study(world)}/research/runs/{run_id}/report/approve",
        json={"artifact_id": artifact_id, "note": ""},
    )
    assert approved.status_code == 200, approved.text
    again = researcher.get(base, params=params).json()
    assert again["artifact_id"] == artifact_id and again["review_state"] == "APPROVED_INTERNAL"

    # A draft of today's contract stored since does not displace the approved version.
    _store_draft(app, world, run_id, b"PK today's draft", CONTEXT_REPORT_CONTRACT)
    now = researcher.get(base, params=params).json()
    assert now["artifact_id"] == artifact_id and now["review_state"] == "APPROVED_INTERNAL"
    assert now["contract_current"] is False
    docx = researcher.get(f"{base}/download", params=params)
    assert docx.status_code == 200 and docx.headers["X-AIA-Artifact-Id"] == artifact_id
    assert docx.headers["X-AIA-Review-State"] == "APPROVED_INTERNAL"
    # Its PDF is still being made: never the newer draft's instead.
    assert researcher.get(f"{base}/pdf/download", params=params).status_code == 404


def test_a_draft_of_todays_contract_displaces_an_earlier_draft(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    run_id, artifact_id = _prepared(app, researcher, world, contract="aia-contextual-report-3")
    base = f"{_study(world)}/research/runs/{run_id}/report/context"
    params = {"deep_research_run_id": REVIEW}
    current = _store_draft(app, world, run_id, b"PK today's draft", CONTEXT_REPORT_CONTRACT)
    now = researcher.get(base, params=params).json()
    assert now["artifact_id"] == current and now["contract_current"] is True
    assert now["review_state"] == "DRAFT_UNAPPROVED"
    download = researcher.get(f"{base}/download", params=params)
    assert download.headers["X-AIA-Artifact-Id"] == current != artifact_id


def test_preparing_an_approved_variant_again_composes_nothing_over_it(
    app: FastAPI, researcher: TestClient, world: Any, monkeypatch: Any
) -> None:
    """Cross-review interactions#5 / web#6: preparing anew an approved variant of an earlier
    contract stored a new draft that became the report, and the approved version was then
    downloadable in neither format. Preparing now composes nothing over an approved version."""
    from aia_api.routers import research as routes

    run_id, artifact_id = _prepared(app, researcher, world, contract="aia-contextual-report-3")
    approved = researcher.post(
        f"{_study(world)}/research/runs/{run_id}/report/approve",
        json={"artifact_id": artifact_id, "note": ""},
    )
    assert approved.status_code == 200, approved.text
    composed: list[str] = []

    def compose(*_a: Any, **_kw: Any) -> Any:
        composed.append("composed")
        raise AssertionError("an approved variant is never composed over")

    monkeypatch.setattr(routes, "stored_contextual_report", compose)
    url = f"{_study(world)}/research/runs/{run_id}/report/context"
    prepared = researcher.post(url, params={"deep_research_run_id": REVIEW})
    assert prepared.status_code == 200, prepared.text
    body = prepared.json()
    assert body["artifact_id"] == artifact_id and body["review_state"] == "APPROVED_INTERNAL"
    assert composed == []


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
    # The file names the run, the review, the version and its review state (D2).
    assert f"{run_id}-{REVIEW}-{artifact_id}-koncept.docx" in docx.headers["Content-Disposition"]
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
    assert body["approval_renders_pdf"] is False
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


def test_approving_a_prepared_variant_asks_for_its_approved_pdf_under_its_review(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Review 4 of D2: approving a variant asks for its approved PDF under the review's own key
    (the variant's ``deep_research_run_id``); asked under the base report's key, the variant's
    status would read NOT_REQUESTED for ever, and no test said so. A version whose approved
    export is stamped: one that exports its stored bytes asks for nothing new (the next test)."""
    run_id, artifact_id = _prepared(app, researcher, world, stampable=True)
    # Its draft's own PDF rendered here: evidence this deployment converts (cross-review web#2).
    _render_pdfs(app, world)
    base = f"{_study(world)}/research/runs/{run_id}/report/context"
    drafted = researcher.get(base, params={"deep_research_run_id": REVIEW}).json()
    assert drafted["pdf"]["state"] == "READY" and drafted["approval_renders_pdf"] is True
    approved = researcher.post(
        f"{_study(world)}/research/runs/{run_id}/report/approve",
        json={"artifact_id": artifact_id, "note": ""},
    )
    assert approved.status_code == 200, approved.text
    body = researcher.get(
        f"{_study(world)}/research/runs/{run_id}/report/context",
        params={"deep_research_run_id": REVIEW},
    ).json()
    assert body["review_state"] == "APPROVED_INTERNAL" and body["approved_on"] is not None
    assert body["pdf"]["state"] == "RENDERING" and body["approval_renders_pdf"] is False
    with create_session_factory(app.state.engine)() as session:
        scope = _scope(session, world)
        docx = research_artifacts(session, scope, app.state.artifact_store).get(artifact_id)
        workflows = WorkflowRepository(session, scope)

        def jobs(review: str | None) -> list[dict[str, Any]]:
            return workflows.list_runs(
                project_id=docx.project_id,
                workflow_type=REPORT_PDF,
                key_prefix=report_pdf_key(run_id, review, artifact_id, approved=True),
                limit=10,
            )

        asked = jobs(REVIEW)
        assert jobs(None) == []
    assert len(asked) == 1
    assert asked[0]["metadata"]["deep_research_run_id"] == REVIEW
    assert asked[0]["metadata"]["review_state"] == "APPROVED_INTERNAL"


def _render_pdfs(app: FastAPI, world: Any) -> list[str]:
    """The worker's part, stood in for: every waiting PDF job renders the DOCX its payload
    names and stores the rendering the way the report_pdf step stores one; returns the PDFs."""
    made: list[str] = []
    with create_session_factory(app.state.engine)() as session:
        scope = _scope(session, world)
        workflow = WorkflowRepository(session, scope)
        repo = research_artifacts(session, scope, app.state.artifact_store)
        while work := workflow.claim_next(worker_id="pdf-fixture", kinds={REPORT_PDF_STEP_KIND}):
            docx = repo.get(str(work.payload["docx_artifact_id"]))
            pdf, _ = repo.put(
                project_id=work.project_id,
                revision=work.project_revision,
                stage_type="REPORT",
                artifact_type=INTERNAL_REPORT_PDF_ARTIFACT_TYPE,
                data=b"%PDF-1.7 rendering of " + docx.sha256.encode(),
                content_type="application/pdf",
                input_fingerprint=f"pdf-fixture-{work.attempt_id}",
                metadata={
                    "run_id": work.payload["run_id"],
                    "deep_research_run_id": work.payload["deep_research_run_id"],
                    "rendering_of": docx.artifact_id,
                },
                depends_on=[docx.artifact_id],
            )
            workflow.complete_attempt(
                work.attempt_id,
                worker_id="pdf-fixture",
                output={"state": "READY", "artifact_id": pdf.artifact_id},
            )
            made.append(pdf.artifact_id)
        session.commit()
    return made


def test_an_older_variant_approved_keeps_its_drafts_pdf_on_a_closed_study(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Cross-review interactions#4 / web#3: a variant stored before the stamp layout exports
    its stored bytes once approved, so the PDF rendered from them while it was a draft is its
    approved PDF -- served on a closed study too, and never asked for again."""
    run_id, artifact_id = _prepared(app, researcher, world)
    (pdf_id,) = _render_pdfs(app, world)
    approved = researcher.post(
        f"{_study(world)}/research/runs/{run_id}/report/approve",
        json={"artifact_id": artifact_id, "note": ""},
    )
    assert approved.status_code == 200 and approved.json()["stamped"] is False
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).set_study_status(_scope(session, world), StudyStatus.DELIVERED)
        session.commit()
    before = _jobs(app)
    base = f"{_study(world)}/research/runs/{run_id}/report/context"
    params = {"deep_research_run_id": REVIEW}
    body = researcher.get(base, params=params).json()
    assert body["review_state"] == "APPROVED_INTERNAL" and body["stamped"] is False
    assert body["pdf"]["state"] == "READY" and body["pdf"]["artifact_id"] == pdf_id
    pdf = researcher.get(f"{base}/pdf/download", params=params)
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["X-AIA-Artifact-Id"] == artifact_id
    assert pdf.headers["X-AIA-Review-State"] == "APPROVED_INTERNAL"
    assert _jobs(app) == before


def test_approving_a_variant_whose_pdf_is_not_rendered_yet_asks_for_none(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Cross-review web#2: approving asked for the approved PDF whatever the draft's own PDF
    was, so a deployment that renders none failed the job (pdf_disabled) and the card offered
    to ask again. Without a ready draft PDF nothing is asked; the status says the approved
    PDF was not asked for, and a person may ask."""
    run_id, artifact_id = _prepared(app, researcher, world, stampable=True)
    before = _jobs(app)
    approved = researcher.post(
        f"{_study(world)}/research/runs/{run_id}/report/approve",
        json={"artifact_id": artifact_id, "note": ""},
    )
    assert approved.status_code == 200, approved.text
    assert _jobs(app) == before
    body = researcher.get(
        f"{_study(world)}/research/runs/{run_id}/report/context",
        params={"deep_research_run_id": REVIEW},
    ).json()
    assert body["review_state"] == "APPROVED_INTERNAL"
    assert body["pdf"]["state"] == "NOT_REQUESTED" and body["pdf"]["askable"] is True
