"""The report_pdf job: a stored report DOCX rendered as PDF (research-integrity-report 3).

The report with a chosen literature review is composed in the API, which holds no converter; the
worker renders the draft the API stored, by artifact id and SHA-256, so one variant's DOCX and PDF
carry the same report. These tests drive the real worker over the one step kind, with a fake
converter at the protocol boundary.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from aia_core.application.report import INTERNAL_REPORT_ARTIFACT_TYPE
from aia_core.application.report_variants import PdfState, request_pdf, variant_pdf
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.scope import StudyStatus
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.domain.workflow_templates import REPORT_PDF, REPORT_PDF_STEP_KIND
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.report_pdf import PdfConversionFailed
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import ProjectArtifactRow, StepRunRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors.report import ReportPdfExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import update

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


def _report(world: Any, store: InMemoryArtifactStore, data: bytes = DOCX) -> tuple[str, Any]:
    """A research run of the study and a stored report DOCX of it (fictional bytes)."""
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
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
            metadata={"run_id": started.run_id, "report_kind": "internal"},
        )
        session.commit()
        return started.run_id, docx


def _ask(world: Any, run_id: str, docx: Any) -> Any:
    with world.sessions() as session:
        started = ResearchRuns(session, world.lead_scope(session)).request_report_pdf(
            docx=docx, run_id=run_id, deep_research_run_id=None
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
    with world.sessions() as session:
        return variant_pdf(
            session,
            world.lead_scope(session),
            store,
            docx=docx,
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
    # The converter is turned on; the person prepares again: a new job, not the failed one.
    again = _ask(world, run_id, docx)
    assert again.created
    assert _drain(_worker(world, database_url, store, build, _FakePdf())) == ["completed"]
    assert _pdf_state(world, store, run_id, docx).state is PdfState.READY


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
        assert runs.request_report_pdf(docx=docx, run_id=run_id, deep_research_run_id=None) is None
    found = _ask_again(world, store, run_id, docx)
    assert found.state is PdfState.NOT_REQUESTED
    assert found.reason == "study_closed" and not found.askable
