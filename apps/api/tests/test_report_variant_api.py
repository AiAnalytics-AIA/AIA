"""The report with a chosen review over HTTP: one draft, read only (research-integrity-report 3).

Preparing composes and stores the variant and asks the worker for its PDF; every GET reads what
was prepared and changes nothing, so a closed study still downloads and the status, the DOCX, the
PDF and the approval name one draft. The draft here is fictional bytes stored in-process the way
the prepare stores it; composing a real one needs a completed run and review, which the executor
journey covers (test_analysis_executor.py).
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from aia_core.application.contextual_report import (
    CONTEXT_REPORT_ARTIFACT_TYPE,
    CONTEXT_REPORT_CONTRACT,
    _store_document,
)
from aia_core.application.report import INTERNAL_REPORT_PDF_ARTIFACT_TYPE
from aia_core.application.report_export import REVIEW_STAMP_RECORD, export_docx
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
from aia_core.domain.report.review import REVIEW_STAMP_CONTRACT, ReviewMark, ReviewState
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
    made = world.design(researcher, DESIGN)
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


def _document() -> ReportDocument:
    """A fictional report with literature, as composed."""
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
    section = Section("Literatura", (Paragraph(text("Fiktivní rešerše.")),), id="ch-literature")
    return ReportDocument(meta, (section,), ledger)


def _rendered() -> bytes:
    """A real report with literature as the renderer lays it out, rendered once."""
    if not _RENDERED:
        _RENDERED.append(DocxRenderer().render(_document()))
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


def test_the_document_is_the_prepared_drafts_and_says_when_none_was_stored(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """The pane reads the variant's document beside the DOCX it would approve (RPT3a): before it
    is prepared, before its document was stored, and once it is, all by name; another client's
    study finds nothing. Composes nothing and makes no job."""
    run_id, artifact_id = _prepared(app, researcher, world)
    url = f"{_study(world)}/research/runs/{run_id}/report/context/document"
    params = {"deep_research_run_id": REVIEW}
    before = _jobs(app)
    unstored = researcher.get(url, params=params)
    assert unstored.status_code == 409 and unstored.json()["code"] == "report_document_not_stored"
    other = researcher.get(url, params={"deep_research_run_id": "RUN-abcabc"})
    assert other.status_code == 409 and other.json()["code"] == "context_report_not_prepared"
    with create_session_factory(app.state.engine)() as session:
        scope = _scope(session, world)
        repo = research_artifacts(session, scope, app.state.artifact_store)
        _store_document(repo, run_id, REVIEW, repo.get(artifact_id), _document(), "")
        session.commit()
    read = researcher.get(url, params=params)
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["report_artifact_id"] == artifact_id and body["run_id"] == run_id
    assert body["review_state"] == "DRAFT_UNAPPROVED" and body["approval"] is None
    assert [section["id"] for section in body["document"]["sections"]] == ["ch-literature"]
    # A newer draft of the same pair has no document of its own yet: never the older one's.
    _store_draft(app, world, run_id, b"PK newer draft", CONTEXT_REPORT_CONTRACT)
    newer = researcher.get(url, params=params)
    assert newer.status_code == 409 and newer.json()["code"] == "report_document_not_stored"
    foreign = researcher.get(
        f"{_study(world, 'other_client')}/research/runs/{run_id}/report/context/document",
        params=params,
    )
    assert foreign.status_code == 404
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
    # The report with literature is approved as its own kind, internal (RD3, G66).
    assert approved.json()["report_kind"] == "with_review"
    assert approved.json()["internal_only"] is True
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
    # Rendered, the approved PDF is served, and both formats are named for what they state.
    _render_pdfs(app, world)
    params = {"deep_research_run_id": REVIEW}
    assert researcher.get(base, params=params).json()["pdf"]["state"] == "READY"
    for route, ext in (("download", "docx"), ("pdf/download", "pdf")):
        got = researcher.get(f"{base}/{route}", params=params)
        assert got.status_code == 200, got.text
        assert got.headers["content-disposition"].endswith(
            f'-{REVIEW}-{artifact_id}-schvaleno.{ext}"'
        ), route


def test_a_draft_whose_body_states_its_status_is_approved_as_stored_never_stamped(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Integration review of the cross-review fixes: PR #478 stored literature drafts under
    aia-contextual-report-5, recorded as stampable, whose chapter ended "Tato kapitola je
    součástí interního neschváleného návrhu zprávy.". The stamp reads only the renderer's own
    status marks, so approving one exported SCHVÁLENO in every footer over that sentence.
    Such a draft reads as an earlier composition, and approved it is exported as stored --
    its file says draft throughout -- named for what it states, and no approved PDF is
    asked."""
    run_id, artifact_id = _prepared(
        app, researcher, world, contract="aia-contextual-report-5", stampable=True
    )
    _render_pdfs(app, world)
    base = f"{_study(world)}/research/runs/{run_id}/report/context"
    params = {"deep_research_run_id": REVIEW}
    drafted = researcher.get(base, params=params).json()
    assert drafted["artifact_id"] == artifact_id and drafted["contract_current"] is False
    # Exported as stored once approved, it keeps the PDF its draft already has.
    assert drafted["approval_renders_pdf"] is True
    approved = researcher.post(
        f"{_study(world)}/research/runs/{run_id}/report/approve",
        json={"artifact_id": artifact_id, "note": ""},
    )
    assert approved.status_code == 200 and approved.json()["stamped"] is False
    with create_session_factory(app.state.engine)() as session:
        scope = _scope(session, world)
        docx = research_artifacts(session, scope, app.state.artifact_store).get(artifact_id)
        asked = WorkflowRepository(session, scope).list_runs(
            project_id=docx.project_id,
            workflow_type=REPORT_PDF,
            key_prefix=report_pdf_key(run_id, REVIEW, artifact_id, approved=True),
            limit=10,
        )
    assert asked == []
    got = researcher.get(f"{base}/download", params=params)
    assert got.status_code == 200 and got.headers["X-AIA-Review-State"] == "APPROVED_INTERNAL"
    assert got.content == _rendered()  # as stored: its footers still say KONCEPT
    assert got.headers["content-disposition"].endswith(
        f'-{REVIEW}-{artifact_id}-schvaleno-v-aia.docx"'
    )
    # Its draft's PDF renders those same bytes: it is the approved version's PDF.
    pdf = researcher.get(f"{base}/pdf/download", params=params)
    assert pdf.status_code == 200 and pdf.headers["content-disposition"].endswith(
        f'-{REVIEW}-{artifact_id}-schvaleno-v-aia.pdf"'
    )


def _render_pdfs(app: FastAPI, world: Any) -> list[str]:
    """The worker's part, stood in for: every waiting PDF job renders the DOCX its payload
    names -- an approved version's export -- and stores the rendering with what the
    report_pdf step records beside it; returns the PDFs."""
    made: list[str] = []
    with create_session_factory(app.state.engine)() as session:
        scope = _scope(session, world)
        workflow = WorkflowRepository(session, scope)
        repo = research_artifacts(session, scope, app.state.artifact_store)
        while work := workflow.claim_next(worker_id="pdf-fixture", kinds={REPORT_PDF_STEP_KIND}):
            docx = repo.get(str(work.payload["docx_artifact_id"]))
            exported = export_docx(repo, docx)
            mark = exported.mark
            review = (
                {
                    "review_state": mark.state.value,
                    "approved_on": mark.approved_on.isoformat(),
                    "review_stamp": REVIEW_STAMP_CONTRACT,
                    "stamped": exported.stamped,
                    "docx_sha256": mark.sha256,
                }
                if mark.approved_on is not None
                else {}
            )
            pdf, _ = repo.put(
                project_id=work.project_id,
                revision=work.project_revision,
                stage_type="REPORT",
                artifact_type=INTERNAL_REPORT_PDF_ARTIFACT_TYPE,
                data=b"%PDF-1.7 rendering of " + hashlib.sha256(exported.data).hexdigest().encode(),
                content_type="application/pdf",
                input_fingerprint=f"pdf-fixture-{work.attempt_id}",
                metadata={
                    "run_id": work.payload["run_id"],
                    "deep_research_run_id": work.payload["deep_research_run_id"],
                    "rendering_of": docx.artifact_id,
                    **review,
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


def _edit(
    app: FastAPI,
    world: Any,
    run_id: str,
    draft: str,
    *,
    by: str = "researcher",
    data: bytes | None = None,
) -> str:
    """The prepared draft opened in the editor and a save of it stored as ``by``'s (RPT8c):
    the edited version's artifact id. ``data``: the saved DOCX, else a small one with no
    footer."""
    import io
    import zipfile
    from datetime import UTC, datetime

    from aia_core.application.report_editor import ReportEditor
    from aia_core.application.report_editor_saves import store_save

    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(
            zipfile.ZipInfo("word/document.xml", (2026, 10, 23, 0, 0, 0)),
            f'<w:document xmlns:w="{w}"><w:body><w:p><w:r><w:t>Upraveno</w:t></w:r></w:p>'
            "</w:body></w:document>",
        )
    url = "https://docs.aia.example.test/cache/files/x.docx"
    now = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)
    with create_session_factory(app.state.engine)() as session:
        scope = ScopeResolver(session).study_context(
            AuthenticatedPrincipal(user_id=world.users[by], organization_id=world.organization_id),
            study_id=world.study_id(),
        )
        store = app.state.artifact_store
        docx = research_artifacts(session, scope, store).get(draft)
        opened = ReportEditor(session, scope).open(
            docx, run_id=run_id, variant="context", deep_research_run_id=REVIEW, now=now
        )
        edited = store_save(
            session,
            scope,
            store,
            opened.session,
            url=url,
            origin="https://docs.aia.example.test",
            fetcher={url: out.getvalue() if data is None else data}.__getitem__,
            authors=[scope.actor_id],
            now=now,
        ).version.artifact_id
        session.commit()
    return edited


def test_an_approved_edit_of_the_report_with_literature_is_named_beside_its_draft(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """A version of this report saved in the editor and approved (RPT8c) leaves the prepared
    draft a draft: the variant's status names the approved edit beside it."""
    run_id, draft = _prepared(app, researcher, world)
    edited = _edit(app, world, run_id, draft)
    runs = f"{_study(world)}/research/runs/{run_id}"
    approved = researcher.post(f"{runs}/report/approve", json={"artifact_id": edited})
    assert approved.status_code == 200, approved.text
    assert approved.json()["report_kind"] == "with_review"
    body = researcher.get(f"{runs}/report/context", params={"deep_research_run_id": REVIEW}).json()
    assert body["artifact_id"] == draft and body["review_state"] == "DRAFT_UNAPPROVED"
    (named,) = body["approved_edits"]
    assert named["artifact_id"] == edited and named["koncept"] == 2
    assert named["review_state"] == "APPROVED_INTERNAL"
    # The internal report's status is another report's: it names no edit of this one.
    assert researcher.get(f"{runs}/report").json().get("approved_edits", []) == []


def test_who_prepared_the_report_does_not_approve_its_edit_where_self_approval_is_off(
    app: FastAPI,
    researcher: TestClient,
    lead: TestClient,
    owner: TestClient,
    outsider: TestClient,
    world: Any,
) -> None:
    """Koncept 1 of the report with literature names no author, but a person prepared it: an
    edit someone else saved is still their work, so where independent review is on they may
    not approve it, and neither may the editor."""
    forbid = owner.put(
        f"{API}/self-approval", json={"allowed": False, "client_id": world.client_id()}
    )
    assert forbid.status_code == 200, forbid.text
    run_id, draft = _prepared(app, researcher, world)  # prepared as the researcher's
    edited = _edit(app, world, run_id, draft, by="lead")
    approve = f"{_study(world)}/research/runs/{run_id}/report/approve"
    for person in (researcher, lead):
        refused = person.post(approve, json={"artifact_id": edited})
        assert refused.status_code == 403 and refused.json()["code"] == "separation_of_duties"
    assert outsider.post(approve, json={"artifact_id": edited}).status_code == 200


def test_an_edited_version_renders_its_pdf_and_approved_says_so_in_its_footers(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """A version saved in the editor (RPT8c) is a report like any other: its PDF is asked for
    and rendered from exactly it, and, where the editor kept the composer's footer layout
    (checked when it was saved), approving it stamps SCHVÁLENO there and renders the approved
    PDF; a save whose footers are gone is served as saved."""
    run_id, draft = _prepared(app, researcher, world, ask_pdf=False)
    edited = _edit(app, world, run_id, draft, data=_rendered())
    plain = _edit(app, world, run_id, draft)
    with create_session_factory(app.state.engine)() as session:
        repo = research_artifacts(session, _scope(session, world), app.state.artifact_store)
        assert repo.get(edited).metadata["review_stamp"] == REVIEW_STAMP_CONTRACT
        assert repo.get(edited).metadata["report_contract"] == CONTEXT_REPORT_CONTRACT
        assert "review_stamp" not in repo.get(plain).metadata
    versions = f"{_study(world)}/research/runs/{run_id}/report/editor/versions"
    before = researcher.get(f"{versions}/{edited}").json()
    assert before["stamped"] is True and before["pdf"]["state"] == "NOT_REQUESTED"
    assert researcher.get(f"{versions}/{edited}/pdf/download").status_code == 404

    asked = researcher.post(f"{versions}/{edited}/pdf")
    assert asked.status_code == 200 and asked.json()["pdf"]["state"] == "RENDERING", asked.text
    (pdf_id,) = _render_pdfs(app, world)
    ready = researcher.get(f"{versions}/{edited}").json()["pdf"]
    assert ready["state"] == "READY" and ready["artifact_id"] == pdf_id
    got = researcher.get(f"{versions}/{edited}/pdf/download")
    assert got.status_code == 200 and got.headers["X-AIA-Artifact-Id"] == edited
    assert got.headers["X-AIA-Review-State"] == "DRAFT_UNAPPROVED"
    assert got.headers["content-disposition"].endswith(f'-{REVIEW}-{edited}-koncept.pdf"')

    # Approved: its footers say so, and its approved PDF is asked for and rendered.
    approve = f"{_study(world)}/research/runs/{run_id}/report/approve"
    assert researcher.post(approve, json={"artifact_id": edited}).status_code == 200
    (approved_pdf,) = _render_pdfs(app, world)
    docx = researcher.get(f"{versions}/{edited}/download")
    assert docx.status_code == 200 and docx.content != _rendered()
    assert docx.headers["content-disposition"].endswith(f'-{REVIEW}-{edited}-schvaleno.docx"')
    pdf = researcher.get(f"{versions}/{edited}/pdf/download")
    assert pdf.status_code == 200 and pdf.headers["X-AIA-Review-State"] == "APPROVED_INTERNAL"
    assert researcher.get(f"{versions}/{edited}").json()["pdf"]["artifact_id"] == approved_pdf
    assert pdf.headers["content-disposition"].endswith(f'-{REVIEW}-{edited}-schvaleno.pdf"')
