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

Once a person approves a version (D2), its PDF is the rendering of its approved export -- the
stamped DOCX -- asked for under a job key of its own (``report_pdf_key(approved=True)``); the
draft's PDF is never served for it. A version stored before the stamp layout exports its stored
bytes once approved (``report_export.exports_stamped``), so the PDF rendered from those bytes
while it was a draft -- the report step's, or one a person asked for -- is its approved PDF:
served as it is, and never asked for again (cross-review interactions#4: refusing it lost the
PDF of every report approved before this release, for good on a closed Study).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from ..domain.report.review import REVIEW_STAMP_CONTRACT, ReviewMark, ReviewState
from ..domain.scope import Permission, StudyContext
from ..domain.workflow import StepRunStatus
from ..domain.workflow_templates import REPORT_PDF
from ..infrastructure.artifact_repository import Artifact, ArtifactNotFound, ArtifactStatus
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.workflow_repository import WorkflowRepository
from .contextual_report import (
    CONTEXT_REPORT_ARTIFACT_TYPE,
    CONTEXT_REPORT_CONTRACT,
    prepared_drafts,
)
from .report import INTERNAL_REPORT_ARTIFACT_TYPE, INTERNAL_REPORT_PDF_ARTIFACT_TYPE
from .report_export import exports_stamped, review_mark, stampable
from .research import ResearchRuns, report_pdf_key, research_artifacts

__all__ = [
    "RENDERABLE_REPORTS",
    "PdfState",
    "VariantPdf",
    "VariantState",
    "VariantStatus",
    "approval_asks_pdf",
    "approval_renders_pdf",
    "prepared_context_report",
    "request_pdf",
    "variant_pdf",
    "variant_status",
]


#: The report DOCX types a ``report_pdf`` job renders: the run's own report and the report with
#: a chosen literature review (the client report is DOCX only).
RENDERABLE_REPORTS = frozenset({INTERNAL_REPORT_ARTIFACT_TYPE, CONTEXT_REPORT_ARTIFACT_TYPE})


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


def approval_asks_pdf(scope: StudyContext, docx: Artifact) -> bool:
    """Whether approving ``docx`` asks the worker for its approved version's PDF
    (``report_approval.approve_report``): a report the worker renders whose approved export is
    stamped (one that exports its stored bytes keeps its draft's rendering), on a Study that
    still starts work, approved by someone who may start it."""
    return (
        docx.artifact_type in RENDERABLE_REPORTS
        and stampable(docx)
        and scope.study_status.accepts_work
        and scope.has(Permission.RUN_WORKFLOW)
    )


def approval_renders_pdf(
    scope: StudyContext, docx: Artifact, mark: ReviewMark, *, pdf_ready: bool
) -> bool:
    """Whether approving the draft ``docx`` now gives its approved version a PDF too, as far
    as AIA knows: the approval asks for one (:func:`approval_asks_pdf`) and this draft's own
    PDF is ready (``pdf_ready``), so this deployment converts. A closed Study, a
    deployment that rendered none, a PDF still being made or one that failed is no promise:
    whether a PDF will be made is then unknown, never a yes (D2, review 4). A version whose
    approved export is its stored bytes keeps that ready PDF, closed Study or not. False once
    approved: approving again asks nothing."""
    return (
        mark.state is ReviewState.DRAFT
        and pdf_ready
        and (not stampable(docx) or approval_asks_pdf(scope, docx))
    )


@dataclass(frozen=True, slots=True)
class VariantStatus:
    """A run's report with one review: its stored draft (``None``: not prepared) and its PDF.
    ``contract_current`` is false for a draft composed under an earlier contract: still the
    report a person prepared, downloadable and approvable; while it is a draft, preparing
    composes it anew, and once approved it stays the report (:func:`prepared_context_report`)."""

    state: VariantState
    docx: Artifact | None
    pdf: VariantPdf | None
    contract_current: bool = True
    #: The draft's review (``report_export.review_mark``); ``None`` before it is prepared.
    mark: ReviewMark | None = None
    #: Whether approving the draft now gives its approved version a PDF too
    #: (:func:`approval_renders_pdf`).
    approval_renders_pdf: bool = False


def _approved_rendering(pdf: Artifact, mark: ReviewMark) -> bool:
    """Whether ``pdf`` renders the approved export of the version ``mark`` names, as it is
    stamped today: a rendering of the draft, or of another stamp, is not."""
    return (
        pdf.metadata.get("review_state") == ReviewState.APPROVED.value
        and pdf.metadata.get("docx_sha256") == mark.sha256
        and mark.approved_on is not None
        and pdf.metadata.get("approved_on") == mark.approved_on.isoformat()
        and pdf.metadata.get("review_stamp") == REVIEW_STAMP_CONTRACT
    )


def variant_pdf(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    docx: Artifact,
    run_id: str,
    deep_research_run_id: str | None,
) -> VariantPdf:
    """The PDF rendered from exactly ``docx`` by its newest job, verified as its rendering: of
    its stored bytes while it is a draft, of its approved export once it is approved (never the
    draft's, when the two differ: ``report_export.exports_stamped``). Raises
    ``report_export.ReviewUnrecorded`` for an approval without its ledger row."""
    mark = review_mark(research_artifacts(session, scope, store), docx)
    stamped = exports_stamped(docx, mark)
    workflows = WorkflowRepository(session, scope)
    jobs = workflows.list_runs(
        project_id=docx.project_id,
        workflow_type=REPORT_PDF,
        key_prefix=report_pdf_key(run_id, deep_research_run_id, docx.artifact_id, approved=stamped),
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
            or (stamped and not _approved_rendering(pdf, mark))
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
    invalid is asked again as a new job of exactly that DOCX -- of its approved export once it
    is approved. Composes nothing, so a draft stored before a later deploy changed what
    composition accepts still gets its PDF. On a Study that starts no work nothing is asked and
    the state says so (``study_closed``)."""
    current = variant_pdf(
        session, scope, store, docx=docx, run_id=run_id, deep_research_run_id=deep_research_run_id
    )
    if current.state not in _ASKABLE or not scope.study_status.accepts_work:
        return current
    ResearchRuns(session, scope).request_report_pdf(
        docx=docx,
        run_id=run_id,
        deep_research_run_id=deep_research_run_id,
        mark=review_mark(research_artifacts(session, scope, store), docx),
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
    """The report with this review as last prepared, read without composing anything: the
    newest valid version a person approved, under any composition contract (D2: the approved
    version is the one exported; a newer draft never displaces it); else the newest valid
    draft under the current contract, else the newest of an earlier one, which stays the
    report a person prepared until a current one exists; ``None`` when it was never prepared
    or none is valid any more. Found as itself, never through a PDF job, which a closed Study
    never has."""
    run = ResearchRuns(session, scope).get(run_id)
    drafts = prepared_drafts(
        research_artifacts(session, scope, store),
        run,
        run_id=run_id,
        deep_research_run_id=deep_research_run_id,
        any_contract=True,
    )
    approved = [a for a in drafts if a.is_approved]
    current = [a for a in drafts if a.metadata.get("report_contract") == CONTEXT_REPORT_CONTRACT]
    return (approved or current or drafts)[-1] if drafts else None


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
    mark = review_mark(research_artifacts(session, scope, store), docx)
    return VariantStatus(
        VariantState.READY,
        docx,
        pdf,
        contract_current=docx.metadata.get("report_contract") == CONTEXT_REPORT_CONTRACT,
        mark=mark,
        approval_renders_pdf=approval_renders_pdf(
            scope, docx, mark, pdf_ready=pdf.state is PdfState.READY
        ),
    )
