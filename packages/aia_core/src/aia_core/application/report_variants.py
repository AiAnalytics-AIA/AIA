"""One report variant, the same content in DOCX and PDF (plan research-integrity-report chunk 3).

The fictional Fio run on develop (``RUN-9b6e0f5e6e0e4345``, 2026-10-16) gave two different
documents: the report with its completed literature review was a 40-page DOCX, composed on
request in the API, while the PDF button gave the 33-page base report. The worker renders a
PDF only for the report its own step stores, and the API has no converter, so the report with
literature had no PDF at all, and the card offering PDF never knew a review was selected.

A researcher now chooses a variant: the run's own report, or the report with one completed
interpretation review. Preparing the variant stores its DOCX once
(``stored_contextual_report``) and asks the worker to render *that stored artifact*
(:func:`request_pdf`). Everything else reads: :func:`variant_status` resolves a variant's draft
and PDF in one place, composing nothing and changing no state, so the status, the DOCX download,
the PDF download and the approval all name the same draft. The draft is found as itself (its
stage, type, run and review), never through a PDF job, so a delivered study, which starts no job,
still prepares and downloads its DOCX.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from ..domain.scope import Permission, StudyContext
from ..domain.workflow import StepRunStatus
from ..domain.workflow_templates import REPORT_PDF
from ..infrastructure.artifact_repository import Artifact, ArtifactNotFound, ArtifactStatus
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.workflow_repository import WorkflowRepository
from .contextual_report import prepared_drafts
from .report import INTERNAL_REPORT_PDF_ARTIFACT_TYPE
from .research import ResearchRuns, report_pdf_key, research_artifacts

__all__ = [
    "PdfState",
    "VariantPdf",
    "VariantState",
    "VariantStatus",
    "prepared_context_report",
    "request_pdf",
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


#: Where a person asking for the PDF starts a new rendering of the same draft.
_ASKABLE = frozenset({PdfState.NOT_REQUESTED, PdfState.FAILED, PdfState.INVALID})


@dataclass(frozen=True, slots=True)
class VariantPdf:
    state: PdfState
    artifact: Artifact | None = None
    reason: str | None = None
    #: Whether a person asking now starts a rendering (:func:`request_pdf`): never asked, failed
    #: or invalid, on a Study that still starts work, by someone who may run one. The page
    #: offers it exactly then.
    askable: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "artifact_id": self.artifact.artifact_id if self.artifact else None,
            "sha256": self.artifact.sha256 if self.artifact else None,
            "size_bytes": self.artifact.size_bytes if self.artifact else None,
            "reason": self.reason,
            "askable": self.askable,
        }


def _judged(scope: StudyContext, state: PdfState, **kw: Any) -> VariantPdf:
    """A PDF state with whether asking now would start a rendering, and, on a Study that starts
    no work, why nothing was asked for."""
    open_ = scope.study_status.accepts_work
    if state is PdfState.NOT_REQUESTED and not open_:
        kw.setdefault("reason", "study_closed")
    askable = state in _ASKABLE and open_ and scope.has(Permission.RUN_WORKFLOW)
    return VariantPdf(state, askable=askable, **kw)


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
        return _judged(scope, PdfState.NOT_REQUESTED)
    (step,) = workflows.get_run(str(jobs[0]["run_id"]))["steps"]
    status = step["status"]
    if status is StepRunStatus.SUCCEEDED:
        output = step.get("output") or {}
        try:
            pdf = research_artifacts(session, scope, store).get(str(output.get("artifact_id")))
        except ArtifactNotFound:
            return _judged(scope, PdfState.INVALID, reason="pdf_missing")
        if (
            pdf.artifact_type != INTERNAL_REPORT_PDF_ARTIFACT_TYPE
            or pdf.metadata.get("rendering_of") != docx.artifact_id
        ):
            return _judged(scope, PdfState.INVALID, reason="pdf_not_this_report")
        if pdf.status is not ArtifactStatus.VALID:
            # Its stored bytes failed a read: rendered again on request, never served.
            return _judged(scope, PdfState.INVALID, reason="pdf_corrupt")
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
        return _judged(scope, PdfState.FAILED, reason=str(error.get("reason") or "pdf_failed"))
    return VariantPdf(PdfState.RENDERING)


def request_pdf(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    docx: Artifact,
    run_id: str,
    deep_research_run_id: str | None,
) -> VariantPdf:
    """Ask for the PDF of a stored report DOCX (the run's own, or a variant's), by one rule: a
    rendering that is ready or under way is left as it is; one never asked for, failed or
    invalid is asked again as a new job of exactly that DOCX. Composes nothing, so a draft
    stored before a later deploy changed what composition accepts still gets its PDF. On a
    Study that starts no work nothing is asked and the state says so (``study_closed``)."""
    current = variant_pdf(
        session, scope, store, docx=docx, run_id=run_id, deep_research_run_id=deep_research_run_id
    )
    if current.state not in _ASKABLE or not scope.study_status.accepts_work:
        return current
    ResearchRuns(session, scope).request_report_pdf(
        docx=docx,
        run_id=run_id,
        deep_research_run_id=deep_research_run_id,
        again=current.state is PdfState.INVALID,
    )
    return variant_pdf(
        session, scope, store, docx=docx, run_id=run_id, deep_research_run_id=deep_research_run_id
    )


def prepared_context_report(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    deep_research_run_id: str,
) -> Artifact | None:
    """The report with this review as last prepared: the newest valid draft stored for this run
    and review under the current composition contract (``prepared_drafts``), read without
    composing anything; ``None`` when it was never prepared, none is valid any more, or every
    draft predates the contract (the page then prepares it again). Found as itself, never
    through a PDF job, which a closed Study never has."""
    run = ResearchRuns(session, scope).get(run_id)
    drafts = prepared_drafts(
        research_artifacts(session, scope, store),
        run,
        run_id=run_id,
        deep_research_run_id=deep_research_run_id,
    )
    return drafts[-1] if drafts else None


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
