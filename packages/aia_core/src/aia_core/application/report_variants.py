"""One report variant, the same content in DOCX and PDF (plan research-integrity-report chunk 3).

The fictional Fio run on develop (``RUN-9b6e0f5e6e0e4345``, 2026-10-16) gave two different
documents: the report with its completed literature review was a 40-page DOCX, composed on
request in the API, while the PDF button gave the 33-page base report. The worker renders a
PDF only for the report its own step stores, and the API has no converter, so the report with
literature had no PDF at all, and the card offering PDF never knew a review was selected.

A researcher now chooses a variant: the run's own report, or the report with one completed
interpretation review. Preparing the variant stores its DOCX once
(``stored_contextual_report``) and asks the worker to render *that stored artifact*
(``ResearchRuns.request_report_pdf``). Everything else reads: :func:`variant_status` resolves a
variant's draft and PDF in one place, composing nothing and changing no state, so the status, the
DOCX download, the PDF download and the approval all name the same draft.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from ..domain.scope import StudyContext
from ..domain.workflow import StepRunStatus
from ..domain.workflow_templates import REPORT_PDF
from ..infrastructure.artifact_repository import Artifact, ArtifactNotFound, ArtifactStatus
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.workflow_repository import WorkflowRepository
from .contextual_report import CONTEXT_REPORT_ARTIFACT_TYPE
from .report import INTERNAL_REPORT_PDF_ARTIFACT_TYPE
from .research import ResearchRuns, report_pdf_key, research_artifacts

__all__ = [
    "PdfState",
    "VariantPdf",
    "VariantState",
    "VariantStatus",
    "prepared_context_report",
    "variant_pdf",
    "variant_status",
]


class VariantState(StrEnum):
    #: Nothing stored for this run and review yet: a person prepares it.
    NOT_PREPARED = "NOT_PREPARED"
    #: The draft below is stored.
    READY = "READY"


class PdfState(StrEnum):
    """Where a variant's PDF stands. Closed: the web matches exactly these."""

    #: No job asked for this draft.
    NOT_REQUESTED = "NOT_REQUESTED"
    #: A job is queued, waiting or running.
    RENDERING = "RENDERING"
    READY = "READY"
    #: The job failed or was cancelled; ``reason`` says why (``pdf_disabled`` and so on).
    FAILED = "FAILED"
    #: The job says it rendered, but what it stored is not this draft's rendering.
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class VariantPdf:
    state: PdfState
    artifact: Artifact | None = None
    reason: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "artifact_id": self.artifact.artifact_id if self.artifact else None,
            "sha256": self.artifact.sha256 if self.artifact else None,
            "size_bytes": self.artifact.size_bytes if self.artifact else None,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class VariantStatus:
    """A run's report with one review: its stored draft (``None``: not prepared) and its PDF."""

    state: VariantState
    docx: Artifact | None
    pdf: VariantPdf | None


def variant_pdf(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    docx: Artifact,
    run_id: str,
    deep_research_run_id: str | None,
) -> VariantPdf:
    """The PDF rendered from exactly ``docx`` by its newest job, verified as its rendering."""
    workflows = WorkflowRepository(session, scope)
    jobs = workflows.list_runs(
        project_id=docx.project_id,
        workflow_type=REPORT_PDF,
        key_prefix=report_pdf_key(run_id, deep_research_run_id, docx.artifact_id),
        limit=1,
    )
    if not jobs:
        return VariantPdf(PdfState.NOT_REQUESTED)
    (step,) = workflows.get_run(str(jobs[0]["run_id"]))["steps"]
    status = step["status"]
    if status is StepRunStatus.SUCCEEDED:
        output = step.get("output") or {}
        try:
            pdf = research_artifacts(session, scope, store).get(str(output.get("artifact_id")))
        except ArtifactNotFound:
            return VariantPdf(PdfState.INVALID, reason="pdf_missing")
        if (
            pdf.artifact_type != INTERNAL_REPORT_PDF_ARTIFACT_TYPE
            or pdf.status is not ArtifactStatus.VALID
            or pdf.metadata.get("rendering_of") != docx.artifact_id
        ):
            return VariantPdf(PdfState.INVALID, reason="pdf_not_this_report")
        return VariantPdf(PdfState.READY, artifact=pdf)
    # A conversion that failed every attempt stops for recovery: for a PDF that needs nobody
    # but a person asking again (ResearchRuns.request_report_pdf starts a new job).
    if status in (
        StepRunStatus.FAILED,
        StepRunStatus.CANCELLED,
        StepRunStatus.SKIPPED,
        StepRunStatus.RECOVERY_REQUIRED,
    ):
        attempts = step.get("attempts") or []
        error = (attempts[-1].get("error") or {}) if attempts else {}
        return VariantPdf(PdfState.FAILED, reason=str(error.get("reason") or "pdf_failed"))
    return VariantPdf(PdfState.RENDERING)


def prepared_context_report(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    deep_research_run_id: str,
) -> Artifact | None:
    """The report with this review as last prepared (its newest PDF job names its draft), read
    without composing anything; ``None`` when it was never prepared or is no longer valid."""
    project_id = ResearchRuns(session, scope).design_project_id()
    if project_id is None:
        return None
    jobs = WorkflowRepository(session, scope).list_runs(
        project_id=project_id,
        workflow_type=REPORT_PDF,
        key_prefix=f"{REPORT_PDF}:{run_id}:{deep_research_run_id}:",
        limit=1,
    )
    if not jobs:
        return None
    try:
        docx = research_artifacts(session, scope, store).get(
            str((jobs[0].get("metadata") or {}).get("docx_artifact_id"))
        )
    except ArtifactNotFound:
        return None
    if (
        docx.artifact_type != CONTEXT_REPORT_ARTIFACT_TYPE
        or docx.status is not ArtifactStatus.VALID
        or docx.metadata.get("run_id") != run_id
        or docx.metadata.get("deep_research_run_id") != deep_research_run_id
    ):
        return None
    return docx


def variant_status(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    deep_research_run_id: str,
) -> VariantStatus:
    """The one reading of a variant: its prepared draft and that draft's PDF. Found only through
    the Study's run (``ResearchRunNotFound`` otherwise); composes and changes nothing."""
    ResearchRuns(session, scope).get(run_id)
    docx = prepared_context_report(
        session, scope, store, run_id=run_id, deep_research_run_id=deep_research_run_id
    )
    if docx is None:
        return VariantStatus(VariantState.NOT_PREPARED, None, None)
    pdf = variant_pdf(
        session,
        scope,
        store,
        docx=docx,
        run_id=run_id,
        deep_research_run_id=deep_research_run_id,
    )
    return VariantStatus(VariantState.READY, docx, pdf)
