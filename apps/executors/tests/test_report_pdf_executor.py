"""The report_pdf job: a stored report DOCX rendered as PDF (research-integrity-report 3).

The report with a chosen literature review is composed in the API, which holds no converter; the
worker renders the draft the API stored, by artifact id and SHA-256, so one variant's DOCX and PDF
carry the same report. These tests drive the real worker over the one step kind, with a fake
converter at the protocol boundary.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import pytest
from aia_core.application.report import INTERNAL_REPORT_ARTIFACT_TYPE
from aia_core.application.report_approval import approve_report
from aia_core.application.report_export import (
    REVIEW_STAMP_RECORD,
    Export,
    ReviewUnrecorded,
    export_docx,
    review_mark,
)
from aia_core.application.report_variants import (
    PdfState,
    approval_renders_pdf,
    request_pdf,
    variant_pdf,
)
from aia_core.application.research import ResearchRuns, report_pdf_key, research_artifacts
from aia_core.domain.evidence import ClaimSurface
from aia_core.domain.evidence.validation import METHOD_STATUS_PENDING
from aia_core.domain.fieldwork import FieldworkSource
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
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.domain.workflow_templates import REPORT_PDF, REPORT_PDF_STEP_KIND
from aia_core.infrastructure import error_tracking
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.report_pdf import PdfConversionFailed
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import (
    ApprovalDecisionRow,
    ProjectArtifactRow,
    StepRunRow,
    WorkflowRunRow,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors.report import ReportPdfExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import func, select, update

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
DOCX = b"PK fictional report draft"


class _FakePdf:
    version = "fake-pdf 1"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def convert(self, docx: bytes) -> bytes:
        self.calls += 1
        if self.fail:
            raise PdfConversionFailed("exited 1")
        return b"%PDF-1.7 rendering of " + hashlib.sha256(docx).hexdigest().encode()


def _worker(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity, pdf: Any
) -> Worker:
    return Worker(
        session_factory=world.sessions,
        executors={REPORT_PDF_STEP_KIND: ReportPdfExecutor(store=store, build=build, pdf=pdf)},
        settings=WorkerSettings(
            database_url=database_url,
            executors="aia_executors.registry:build_registry",
            worker_id="pdf-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _drain(worker: Worker) -> list[str]:
    endings: list[str] = []
    while (result := worker.run_once()) is not None:
        endings.append(result.ending)
    return endings


def _report(
    world: Any,
    store: InMemoryArtifactStore,
    data: bytes = DOCX,
    *,
    metadata: dict[str, Any] | None = None,
) -> tuple[str, Any]:
    """A research run of the study and a stored report DOCX of it (fictional bytes), with
    ``metadata`` beside what every report records."""
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        runs = ResearchRuns(session, scope)
        started = runs.start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
        )
        project_id = runs.design_project_id()
        assert project_id is not None
        docx, _ = research_artifacts(session, scope, store).put(
            project_id=project_id,
            revision=revision.revision,
            stage_type="REPORT",
            artifact_type=INTERNAL_REPORT_ARTIFACT_TYPE,
            data=data,
            input_fingerprint=hashlib.sha256(data).hexdigest(),
            metadata={"run_id": started.run_id, "report_kind": "internal", **(metadata or {})},
        )
        session.commit()
        return started.run_id, docx


def _ask(world: Any, run_id: str, docx: Any, mark: ReviewMark | None = None) -> Any:
    """A person asking for ``docx``'s PDF, having read it as ``mark`` (a draft by default)."""
    with world.sessions() as session:
        started = ResearchRuns(session, world.lead_scope(session)).request_report_pdf(
            docx=docx,
            run_id=run_id,
            deep_research_run_id=None,
            mark=mark or ReviewMark(ReviewState.DRAFT, docx.artifact_id, docx.sha256),
        )
        session.commit()
        return started


def _forge(world: Any, job_run_id: str, payload: dict[str, Any]) -> None:
    """The job's stored step input replaced, as a corrupted or forged row would read: the
    executor must check what it is told against the draft, never trust the payload."""
    with world.sessions() as session:
        session.execute(
            update(StepRunRow).where(StepRunRow.run_id == job_run_id).values(input_json=payload)
        )
        session.commit()


def _pdf_state(world: Any, store: InMemoryArtifactStore, run_id: str, docx: Any) -> Any:
    """The PDF state of ``docx`` as stored now (approved since, it reads as approved)."""
    with world.sessions() as session:
        scope = world.lead_scope(session)
        return variant_pdf(
            session,
            scope,
            store,
            docx=research_artifacts(session, scope, store).get(docx.artifact_id),
            run_id=run_id,
            deep_research_run_id=None,
        )


def test_the_job_renders_exactly_the_stored_draft_and_asking_again_is_the_same_job(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    run_id, docx = _report(world, store)
    first = _ask(world, run_id, docx)
    assert first.created and first.workflow_type == REPORT_PDF
    assert _pdf_state(world, store, run_id, docx).state is PdfState.RENDERING
    pdf = _FakePdf()
    assert _drain(_worker(world, database_url, store, build, pdf)) == ["completed"]
    found = _pdf_state(world, store, run_id, docx)
    assert found.state is PdfState.READY and found.artifact is not None
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        data = repo.read(found.artifact.artifact_id)
        assert [d.artifact_id for d in repo.dependencies(found.artifact.artifact_id)] == [
            docx.artifact_id
        ]
    assert data == b"%PDF-1.7 rendering of " + hashlib.sha256(DOCX).hexdigest().encode()
    assert found.artifact.metadata["rendering_of"] == docx.artifact_id
    assert found.artifact.metadata["run_id"] == run_id
    assert "deep_research_run_id" not in found.artifact.metadata
    # Asking again for a rendered draft is the same job: nothing renders twice.
    again = _ask(world, run_id, docx)
    assert not again.created and again.run_id == first.run_id
    assert pdf.calls == 1


def test_a_pdf_that_failed_for_want_of_a_converter_is_rendered_once_a_person_asks_again(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    run_id, docx = _report(world, store)
    _ask(world, run_id, docx)
    assert _drain(_worker(world, database_url, store, build, None)) == ["failed"]
    failed = _pdf_state(world, store, run_id, docx)
    assert failed.state is PdfState.FAILED and failed.reason == "pdf_disabled"
    # Cross-review web#2: the card does not offer it again -- in this deployment asking only
    # fails again, each failure an error-tracking issue.
    assert not failed.askable
    # The converter is turned on; the person prepares again: a new job, not the failed one.
    again = _ask(world, run_id, docx)
    assert again.created
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    assert _pdf_state(world, store, run_id, docx).state is PdfState.READY


def test_asking_again_after_a_hundred_failed_jobs_still_starts_a_new_one(
    world: Any, store: InMemoryArtifactStore
) -> None:
    """Review 2: the next round was the count of a listing capped at 100, so the 102nd ask
    named an existing key and returned the failed job while the card still offered to ask."""
    run_id, docx = _report(world, store)
    for _ in range(102):
        started = _ask(world, run_id, docx)
        assert started.created
        with world.sessions() as session:
            session.execute(
                update(WorkflowRunRow)
                .where(WorkflowRunRow.run_id == started.run_id)
                .values(status=WorkflowRunStatus.FAILED.value)
            )
            session.commit()
    with world.sessions() as session:
        jobs = WorkflowRepository(session, world.lead_scope(session)).list_runs(
            project_id=docx.project_id, workflow_type=REPORT_PDF, limit=200
        )
    assert len(jobs) == 102 and jobs[0]["metadata"]["round"] == 101


def test_a_conversion_that_fails_both_attempts_is_said_so_and_can_be_asked_again(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    """A conversion can time out under load: TRANSIENT, so the worker tries once more (max 2);
    after both it stops for recovery, the card says the PDF failed and why, and a person
    preparing again starts a new job."""
    run_id, docx = _report(world, store)
    _ask(world, run_id, docx)
    pdf = _FakePdf(fail=True)
    assert _drain(_worker(world, database_url, store, build, pdf)) == ["failed", "failed"]
    assert pdf.calls == 2
    found = _pdf_state(world, store, run_id, docx)
    assert found.state is PdfState.FAILED and found.reason == "pdf_conversion_failed"
    assert _ask(world, run_id, docx).created
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    assert _pdf_state(world, store, run_id, docx).state is PdfState.READY


@pytest.mark.parametrize("tamper", ["sha", "run", "review"])
def test_a_job_naming_a_different_draft_renders_nothing(
    world: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
    tamper: str,
) -> None:
    run_id, docx = _report(world, store)
    job = _ask(world, run_id, docx)
    _forge(
        world,
        job.run_id,
        {
            "docx_artifact_id": docx.artifact_id,
            "docx_sha256": "0" * 64 if tamper == "sha" else docx.sha256,
            "run_id": "RUN-0000" if tamper == "run" else run_id,
            "deep_research_run_id": "RUN-dddd" if tamper == "review" else None,
        },
    )
    pdf = _FakePdf()
    assert _drain(_worker(world, database_url, store, build, pdf)) == ["failed"]
    assert pdf.calls == 0
    found = _pdf_state(world, store, run_id, docx)
    assert found.state is PdfState.FAILED and found.reason == "report_docx_mismatch"


def test_a_job_whose_draft_is_gone_fails_by_name(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    run_id, docx = _report(world, store)
    started = _ask(world, run_id, docx)
    _forge(world, started.run_id, {"docx_artifact_id": "ART-missing", "run_id": run_id})
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["failed"]
    with world.sessions() as session:
        run = WorkflowRepository(session, world.lead_scope(session)).get_run(started.run_id)
    assert run["status"] is WorkflowRunStatus.FAILED
    (step,) = run["steps"]
    assert step["status"] is StepRunStatus.FAILED
    assert step["attempts"][-1]["error"]["reason"] == "report_docx_missing"


def test_two_drafts_with_the_same_bytes_each_get_their_own_rendering(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    run_id, docx = _report(world, store)
    with world.sessions() as session:
        scope = world.lead_scope(session)
        twin, created = research_artifacts(session, scope, store).put(
            project_id=docx.project_id,
            revision=docx.revision,
            stage_type="REPORT",
            artifact_type=INTERNAL_REPORT_ARTIFACT_TYPE,
            data=DOCX,
            input_fingerprint="another composition",
            metadata={"run_id": run_id, "report_kind": "internal"},
            reuse=False,
        )
        session.commit()
    assert created and twin.artifact_id != docx.artifact_id
    _ask(world, run_id, docx)
    _ask(world, run_id, twin)
    _drain(_worker(world, database_url, store, build, _FakePdf()))
    first = _pdf_state(world, store, run_id, docx)
    second = _pdf_state(world, store, run_id, twin)
    assert first.state is PdfState.READY and second.state is PdfState.READY
    assert first.artifact is not None and second.artifact is not None
    assert first.artifact.metadata["rendering_of"] == docx.artifact_id
    assert second.artifact.metadata["rendering_of"] == twin.artifact_id


def _ask_again(world: Any, store: InMemoryArtifactStore, run_id: str, docx: Any) -> Any:
    with world.sessions() as session:
        found = request_pdf(
            session,
            world.lead_scope(session),
            store,
            docx=docx,
            run_id=run_id,
            deep_research_run_id=None,
        )
        session.commit()
        return found


def test_a_pdf_whose_bytes_went_bad_is_rendered_again_when_a_person_asks(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    """Review, 2026-10-16: a rendered PDF marked corrupt by a failed read was INVALID for good:
    its job had succeeded, so asking again found the same finished job."""
    run_id, docx = _report(world, store)
    _ask(world, run_id, docx)
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    ready = _pdf_state(world, store, run_id, docx)
    assert ready.state is PdfState.READY and ready.artifact is not None
    assert not ready.askable  # a ready PDF is left as it is
    with world.sessions() as session:
        session.execute(
            update(ProjectArtifactRow)
            .where(ProjectArtifactRow.artifact_id == ready.artifact.artifact_id)
            .values(status="CORRUPT")
        )
        session.commit()
    bad = _pdf_state(world, store, run_id, docx)
    assert bad.state is PdfState.INVALID and bad.reason == "pdf_corrupt" and bad.askable
    assert _ask_again(world, store, run_id, docx).state is PdfState.RENDERING
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    again = _pdf_state(world, store, run_id, docx)
    assert again.state is PdfState.READY and again.artifact is not None
    assert again.artifact.artifact_id != ready.artifact.artifact_id


def test_a_closed_study_asks_for_no_pdf_and_says_why(
    world: Any, store: InMemoryArtifactStore
) -> None:
    """A delivered study starts no work: its stored DOCX stays the report, and its PDF says
    why none was asked for instead of the request failing."""
    run_id, docx = _report(world, store)
    with world.sessions() as session:
        ScopeRepository(session).set_study_status(world.lead_scope(session), StudyStatus.DELIVERED)
        session.commit()
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        draft = ReviewMark(ReviewState.DRAFT, docx.artifact_id, docx.sha256)
        assert (
            runs.request_report_pdf(docx=docx, run_id=run_id, deep_research_run_id=None, mark=draft)
            is None
        )
    found = _ask_again(world, store, run_id, docx)
    assert found.state is PdfState.NOT_REQUESTED
    assert found.reason == "study_closed" and not found.askable


# --- an approved version's PDF (research-integrity-report D2) ---------------------------------

_RENDERED: list[bytes] = []


def _rendered() -> bytes:
    """A real report as the renderer lays it out (its status in its footers), rendered once."""
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


def _approve(world: Any, store: InMemoryArtifactStore, run_id: str, docx: Any) -> Any:
    with world.sessions() as session:
        approved = approve_report(
            session, world.lead_scope(session), store, run_id=run_id, artifact_id=docx.artifact_id
        )
        session.commit()
        return approved


def _export(world: Any, store: InMemoryArtifactStore, docx: Any) -> Export:
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        return export_docx(repo, repo.get(docx.artifact_id))


def _jobs(world: Any, docx: Any, prefix: str) -> list[dict[str, Any]]:
    with world.sessions() as session:
        return WorkflowRepository(session, world.lead_scope(session)).list_runs(
            project_id=docx.project_id, workflow_type=REPORT_PDF, key_prefix=prefix, limit=50
        )


def _rendering_of(data: bytes) -> bytes:
    return b"%PDF-1.7 rendering of " + hashlib.sha256(data).hexdigest().encode()


def test_the_approved_pdf_key_never_matches_a_draft_prefix(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    """The job lookup is a literal ``startswith``: an approved key that extended a draft key
    would be found, and served, as the draft's PDF -- and the other way round."""
    for review in (None, "RUN-feedfeed"):
        draft = report_pdf_key("RUN-ab12", review, "ART-0123456789abcdef")
        approved = report_pdf_key("RUN-ab12", review, "ART-0123456789abcdef", approved=True)
        assert draft == f"report_pdf:RUN-ab12:{review or 'base'}:ART-0123456789abcdef"
        assert approved.startswith("report_pdf:approved:")
        assert not approved.startswith(draft) and not draft.startswith(approved)
        assert not f"{draft}:again-1".startswith(approved)
    run_id, docx = _report(world, store, _rendered(), metadata=dict(REVIEW_STAMP_RECORD))
    _ask(world, run_id, docx)
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    _approve(world, store, run_id, docx)
    draft_jobs = _jobs(world, docx, report_pdf_key(run_id, None, docx.artifact_id))
    approved_jobs = _jobs(
        world, docx, report_pdf_key(run_id, None, docx.artifact_id, approved=True)
    )
    assert [j["metadata"]["review_state"] for j in draft_jobs] == ["DRAFT_UNAPPROVED"]
    assert [j["metadata"]["review_state"] for j in approved_jobs] == ["APPROVED_INTERNAL"]


def test_approving_freezes_the_version_and_asks_for_its_approved_pdf_once(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    """Approving asks for the approved version's PDF where its draft's own PDF was rendered
    here (cross-review web#2: asking where none is rendered only fails)."""
    run_id, docx = _report(world, store, _rendered(), metadata=dict(REVIEW_STAMP_RECORD))
    _ask(world, run_id, docx)
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    approved = _approve(world, store, run_id, docx)
    assert approved.is_approved and approved.is_frozen
    prefix = report_pdf_key(run_id, None, docx.artifact_id, approved=True)
    assert len(_jobs(world, docx, prefix)) == 1
    assert _pdf_state(world, store, run_id, docx).state is PdfState.RENDERING
    # One decision per report: approving again records nothing and asks for nothing.
    assert _approve(world, store, run_id, docx).is_approved
    assert len(_jobs(world, docx, prefix)) == 1
    pdf = _FakePdf()
    assert _drain(_worker(world, database_url, store, build, pdf)) == ["completed"]
    found = _pdf_state(world, store, run_id, docx)
    assert found.state is PdfState.READY and found.artifact is not None
    exported = _export(world, store, docx)
    assert exported.stamped and exported.data != _rendered()
    with world.sessions() as session:
        data = research_artifacts(session, world.lead_scope(session), store).read(
            found.artifact.artifact_id
        )
    # The PDF renders the stamped export, the file a DOCX download of the version is.
    assert data == _rendering_of(exported.data)
    assert {k: found.artifact.metadata[k] for k in ("review_state", "stamped", "docx_sha256")} == {
        "review_state": "APPROVED_INTERNAL",
        "stamped": True,
        "docx_sha256": docx.sha256,
    }
    assert found.artifact.metadata["rendering_of"] == docx.artifact_id


def test_the_approved_pdf_renders_the_stamped_version_and_refuses_a_changed_review(
    world: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A draft's job asked before the approval, run after it, renders nothing: the version it
    was asked for is no longer a draft. That is a person approving while the draft's PDF
    waited, not a broken run: the job ends superseded, reported to nobody (it failed
    SCHEMA_VIOLATION, one error-tracking issue with every real integrity fault of the step).
    The approved job renders the stamped export; one whose payload names another approval is
    refused, by name.

    Changed on purpose (cross-review web#2): the approval asked for the approved PDF itself.
    Its draft's PDF was not ready yet -- no evidence this deployment converts -- so it now asks
    for nothing, and a person asks for the approved PDF on the report."""
    reported: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        error_tracking,
        "report_failure",
        lambda title, *, fingerprint, **_kw: reported.append((title, fingerprint)),
    )
    run_id, docx = _report(world, store, _rendered(), metadata=dict(REVIEW_STAMP_RECORD))
    draft_job = _ask(world, run_id, docx)
    _approve(world, store, run_id, docx)
    pdf = _FakePdf()
    assert _drain(_worker(world, database_url, store, build, pdf)) == ["completed"]
    assert pdf.calls == 0
    asked = _pdf_state(world, store, run_id, docx)
    assert asked.state is PdfState.NOT_REQUESTED and asked.askable
    assert _ask(world, run_id, docx, mark=_export(world, store, docx).mark).created
    assert _drain(_worker(world, database_url, store, build, pdf)) == ["completed"]
    assert pdf.calls == 1
    assert reported == []
    with world.sessions() as session:
        (step,) = WorkflowRepository(session, world.lead_scope(session)).get_run(draft_job.run_id)[
            "steps"
        ]
    assert step["status"] is StepRunStatus.SUCCEEDED
    assert step["output"] == {"state": "SUPERSEDED", "reason": "report_review_changed"}
    with world.sessions() as session:
        renderings = [
            a
            for a in research_artifacts(session, world.lead_scope(session), store).list_for_stage(
                project_id=docx.project_id, revision=docx.revision, stage_type="REPORT"
            )
            if a.metadata.get("rendering_of") == docx.artifact_id
        ]
    assert [a.metadata["review_state"] for a in renderings] == ["APPROVED_INTERNAL"]
    found = _pdf_state(world, store, run_id, docx)
    assert found.state is PdfState.READY
    assert found.artifact is not None and found.artifact.metadata["stamped"] is True

    again = _ask(world, run_id, docx, mark=_export(world, store, docx).mark)
    assert not again.created  # the approved rendering is ready: the same job
    with world.sessions() as session:
        exported = export_docx(
            research_artifacts(session, world.lead_scope(session), store),
            research_artifacts(session, world.lead_scope(session), store).get(docx.artifact_id),
        )
        forged = ResearchRuns(session, world.lead_scope(session)).request_report_pdf(
            docx=docx,
            run_id=run_id,
            deep_research_run_id=None,
            mark=exported.mark,
            again=True,
        )
        session.commit()
    assert forged is not None
    _forge(
        world,
        forged.run_id,
        {
            "docx_artifact_id": docx.artifact_id,
            "docx_sha256": docx.sha256,
            "run_id": run_id,
            "deep_research_run_id": None,
            "review_state": "APPROVED_INTERNAL",
            "approved_on": "2001-01-01",
        },
    )
    assert _drain(_worker(world, database_url, store, build, pdf)) == ["failed"]
    assert pdf.calls == 1
    with world.sessions() as session:
        (step,) = WorkflowRepository(session, world.lead_scope(session)).get_run(forged.run_id)[
            "steps"
        ]
    assert step["attempts"][-1]["error"]["reason"] == "report_review_changed"
    # A review that moved any other way is an integrity fault, an issue of its own.
    assert reported == [
        (
            f"{REPORT_PDF_STEP_KIND} failed: SCHEMA_VIOLATION (report_review_changed)",
            ["step-failed", REPORT_PDF_STEP_KIND, "SCHEMA_VIOLATION", "report_review_changed"],
        )
    ]


def test_approving_promises_a_pdf_only_once_the_drafts_own_was_rendered_here(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    """Review 4 of D2: a PDF is promised for the approved version only where approving asks
    for one and this draft's own PDF was rendered here -- never while it is being made, and
    never on a Study that starts no work."""
    run_id, docx = _report(world, store, _rendered(), metadata=dict(REVIEW_STAMP_RECORD))

    def promised() -> bool:
        with world.sessions() as session:
            scope = world.lead_scope(session)
            repo = research_artifacts(session, scope, store)
            artifact = repo.get(docx.artifact_id)
            pdf = _pdf_state(world, store, run_id, docx)
            return approval_renders_pdf(
                scope, artifact, review_mark(repo, artifact), pdf_ready=pdf.state is PdfState.READY
            )

    assert not promised()  # never asked: no deployment has shown it converts
    _ask(world, run_id, docx)
    assert not promised()  # being made: not known yet
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    assert promised()
    with world.sessions() as session:
        ScopeRepository(session).set_study_status(world.lead_scope(session), StudyStatus.DELIVERED)
        session.commit()
    assert not promised()  # its PDF is still READY; approving would ask for nothing


def test_an_export_takes_bytes_already_read_only_when_they_are_the_version(
    world: Any, store: InMemoryArtifactStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller that has just read a version (the client report's download) hands its bytes
    over instead of a second read; bytes that are not the version's are never exported as it."""
    run_id, docx = _report(world, store, _rendered(), metadata=dict(REVIEW_STAMP_RECORD))
    reads: list[str] = []
    real_get = store.get

    def counted(key: str, **kw: Any) -> bytes:
        reads.append(key)
        return real_get(key, **kw)

    monkeypatch.setattr(store, "get", counted)
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        artifact = repo.get(docx.artifact_id)
        assert export_docx(repo, artifact, data=_rendered()).data == _rendered()
        assert reads == []
        assert export_docx(repo, artifact, data=b"PK another document").data == _rendered()
        assert len(reads) == 1
    _approve(world, store, run_id, docx)
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        exported = export_docx(repo, repo.get(docx.artifact_id), data=_rendered())
    assert exported.stamped and exported.data == _export(world, store, docx).data


def test_an_older_approved_version_renders_as_stored_and_says_so(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    """A version stored before the stamp layout has no record of it: approved, its DOCX and
    PDF are its stored bytes, never partly stamped, and they say they are not stamped.

    Changed on purpose (cross-review interactions#4): approving it asked for a new rendering
    under the approved key. Its export is its stored bytes, so there is nothing new to render:
    approving asks for nothing, and a person asking renders the stored bytes under the draft's
    key, where a rendering made while it was a draft already is its PDF."""
    run_id, docx = _report(world, store, _rendered())
    _approve(world, store, run_id, docx)
    exported = _export(world, store, docx)
    assert exported.data == _rendered() and not exported.stamped
    assert exported.mark.state is ReviewState.APPROVED
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == []
    asked = _pdf_state(world, store, run_id, docx)
    assert asked.state is PdfState.NOT_REQUESTED and asked.askable
    with world.sessions() as session:
        scope = world.lead_scope(session)
        request_pdf(
            session,
            scope,
            store,
            docx=research_artifacts(session, scope, store).get(docx.artifact_id),
            run_id=run_id,
            deep_research_run_id=None,
        )
        session.commit()
    assert _jobs(world, docx, report_pdf_key(run_id, None, docx.artifact_id, approved=True)) == []
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    found = _pdf_state(world, store, run_id, docx)
    assert found.state is PdfState.READY and found.artifact is not None
    assert found.artifact.metadata["stamped"] is False
    with world.sessions() as session:
        data = research_artifacts(session, world.lead_scope(session), store).read(
            found.artifact.artifact_id
        )
    assert data == _rendering_of(_rendered())


def test_an_older_version_keeps_the_pdf_its_draft_had_once_approved(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    """Cross-review interactions#4 / web#3: every report approved before this release lost its
    PDF -- for good on a closed Study, which asks for nothing -- although the PDF its draft had
    renders exactly the file its approved export is. It stays its PDF, and nothing is asked."""
    run_id, docx = _report(world, store, _rendered())
    _ask(world, run_id, docx)
    pdf = _FakePdf()
    assert _drain(_worker(world, database_url, store, build, pdf)) == ["completed"]
    drafted = _pdf_state(world, store, run_id, docx)
    assert drafted.state is PdfState.READY and drafted.artifact is not None
    _approve(world, store, run_id, docx)
    with world.sessions() as session:
        ScopeRepository(session).set_study_status(world.lead_scope(session), StudyStatus.DELIVERED)
        session.commit()
    found = _pdf_state(world, store, run_id, docx)
    assert found.state is PdfState.READY and found.artifact is not None
    assert found.artifact.artifact_id == drafted.artifact.artifact_id
    assert _drain(_worker(world, database_url, store, build, pdf)) == [] and pdf.calls == 1


def test_an_older_version_approved_while_its_draft_pdf_waited_still_gets_it(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    """The draft's job of a version stored before the stamp layout, run after the version was
    approved, renders it: its approved export is those bytes. Ending it superseded, as a
    stamped version's is, would leave the version without a PDF and nothing asking for one."""
    run_id, docx = _report(world, store, _rendered())
    job = _ask(world, run_id, docx)
    _approve(world, store, run_id, docx)
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    with world.sessions() as session:
        (step,) = WorkflowRepository(session, world.lead_scope(session)).get_run(job.run_id)[
            "steps"
        ]
    assert step["output"]["state"] == "READY"
    found = _pdf_state(world, store, run_id, docx)
    assert found.state is PdfState.READY and found.artifact is not None
    assert found.artifact.metadata["stamped"] is False
    with world.sessions() as session:
        data = research_artifacts(session, world.lead_scope(session), store).read(
            found.artifact.artifact_id
        )
    assert data == _rendering_of(_rendered())


def test_an_approval_without_its_ledger_row_is_never_exported_as_approved(
    world: Any, store: InMemoryArtifactStore
) -> None:
    run_id, docx = _report(world, store, _rendered(), metadata=dict(REVIEW_STAMP_RECORD))
    with world.sessions() as session:
        session.execute(
            update(ProjectArtifactRow)
            .where(ProjectArtifactRow.artifact_id == docx.artifact_id)
            .values(is_approved=True)
        )
        session.commit()
    with world.sessions() as session, pytest.raises(ReviewUnrecorded):
        repo = research_artifacts(session, world.lead_scope(session), store)
        review_mark(repo, repo.get(docx.artifact_id))
    with pytest.raises(ReviewUnrecorded):
        _export(world, store, docx)
    with pytest.raises(ReviewUnrecorded):
        _pdf_state(world, store, run_id, docx)


def test_a_closed_study_approves_and_stamps_the_docx_and_says_why_no_pdf(
    world: Any, store: InMemoryArtifactStore
) -> None:
    run_id, docx = _report(world, store, _rendered(), metadata=dict(REVIEW_STAMP_RECORD))
    with world.sessions() as session:
        ScopeRepository(session).set_study_status(world.lead_scope(session), StudyStatus.DELIVERED)
        session.commit()
    approved = _approve(world, store, run_id, docx)
    assert approved.is_approved and approved.is_frozen
    prefix = report_pdf_key(run_id, None, docx.artifact_id, approved=True)
    assert _jobs(world, docx, prefix) == []
    found = _pdf_state(world, store, run_id, docx)
    assert found.state is PdfState.NOT_REQUESTED and found.reason == "study_closed"
    assert _export(world, store, docx).stamped


def test_a_version_approved_before_approving_froze_is_frozen_without_a_second_decision(
    world: Any, store: InMemoryArtifactStore
) -> None:
    """Codex review of PR #478: a version approved by the previous release is approved but not
    frozen, and approving it again returned it as it was, so invalidate_stage and delete, which
    spare only a frozen artifact, could still remove a signed version. Approving it now freezes
    it; freezing is no decision, so the ledger keeps its one row and nothing is asked."""
    run_id, docx = _report(world, store, _rendered(), metadata=dict(REVIEW_STAMP_RECORD))
    with world.sessions() as session:
        # What the previous release did: the ledger row and the flag, no freeze.
        before = research_artifacts(session, world.lead_scope(session), store).approve(
            docx.artifact_id
        )
        session.commit()
    assert before.is_approved and not before.is_frozen

    def decisions() -> int:
        with world.sessions() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(ApprovalDecisionRow)
                    .where(
                        ApprovalDecisionRow.subject_type == "artifact",
                        ApprovalDecisionRow.subject_id == docx.artifact_id,
                    )
                )
                or 0
            )

    assert decisions() == 1
    approved = _approve(world, store, run_id, docx)
    assert approved.is_approved and approved.is_frozen
    assert decisions() == 1
    assert _jobs(world, docx, report_pdf_key(run_id, None, docx.artifact_id, approved=True)) == []
    with world.sessions() as session:
        stored = research_artifacts(session, world.lead_scope(session), store).get(docx.artifact_id)
    assert stored.is_frozen


def test_approving_where_no_pdf_is_rendered_asks_for_none(
    world: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-review web#2: approving asked for an approved PDF where this deployment renders
    none (AIA_REPORT_PDF_ENABLED off, the default outside develop): the job failed pdf_disabled,
    raised an error-tracking issue, and the card offered "Vytvořit PDF znovu", which could only
    fail again. Approving asks only where the draft's own PDF was rendered; a pdf_disabled
    failure is not offered again -- nor, once the version is approved, is the approved PDF the
    draft's failure showed would fail too (it read NOT_REQUESTED, askable: the card offered
    "Vytvořit PDF" for a job that failed pdf_disabled again)."""
    reported: list[str] = []
    monkeypatch.setattr(
        error_tracking, "report_failure", lambda title, **_kw: reported.append(title)
    )
    run_id, docx = _report(world, store, _rendered(), metadata=dict(REVIEW_STAMP_RECORD))
    _ask(world, run_id, docx)
    assert _drain(_worker(world, database_url, store, build, None)) == ["failed"]
    reported.clear()
    failed = _pdf_state(world, store, run_id, docx)
    assert failed.state is PdfState.FAILED and failed.reason == "pdf_disabled"
    assert not failed.askable
    _approve(world, store, run_id, docx)
    prefix = report_pdf_key(run_id, None, docx.artifact_id, approved=True)
    assert _jobs(world, docx, prefix) == []
    assert _drain(_worker(world, database_url, store, build, None)) == []
    assert reported == []
    # Approved: nothing was asked for its PDF, and the reason its draft's failed is kept.
    approved = _pdf_state(world, store, run_id, docx)
    assert approved.state is PdfState.NOT_REQUESTED and approved.reason == "pdf_disabled"
    assert not approved.askable
    # On a Study that starts no work, the closure is why nothing is asked.
    for status, reason in ((StudyStatus.DELIVERED, "study_closed"), (StudyStatus.ACTIVE, None)):
        with world.sessions() as session:
            ScopeRepository(session).set_study_status(world.lead_scope(session), status)
            session.commit()
        if reason is not None:
            closed = _pdf_state(world, store, run_id, docx)
            assert closed.reason == reason and not closed.askable
    assert _pdf_state(world, store, run_id, docx).reason == "pdf_disabled"
    # The converter turned on, the operator's ask (POST …/report/pdf) still renders the
    # approved export, under the approved key.
    with world.sessions() as session:
        scope = world.lead_scope(session)
        request_pdf(
            session,
            scope,
            store,
            docx=research_artifacts(session, scope, store).get(docx.artifact_id),
            run_id=run_id,
            deep_research_run_id=None,
        )
        session.commit()
    assert len(_jobs(world, docx, prefix)) == 1
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    rendered = _pdf_state(world, store, run_id, docx)
    assert rendered.state is PdfState.READY and rendered.artifact is not None
    assert rendered.artifact.metadata["stamped"] is True
    assert reported == []
