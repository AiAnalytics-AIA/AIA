"""A person approves a run's stored report (complete-study-report B2).

The approval is the artifact repository's own: ``SIGN_OFF_DELIVERABLE``, the
independence the scope's self-approval policy requires, and a row in the approval ledger.
This module decides only *which* artifacts are a run's reports: the internal report its
REPORT step stored, the report with literature or the client report stored for it, each
found through the Study's run and checked to name that run. Approval is a person's sign-off
on the stored document; what the client report may contain was decided when it was composed, and
the client deliverable's gate (RD0) is read before the client report's approval.

Approving a version (research-integrity-report D2) also freezes it -- it can no longer be
deleted or superseded in place -- and, for a report the worker renders whose approved export is
stamped, asks for that export's PDF in the same transaction, where this deployment has shown it
converts: the draft's own PDF is ready (``report_variants.approval_asks_pdf``). A Study that
starts no work asks for nothing; its PDF state says why (``study_closed``), and its DOCX is
still downloaded stamped, which needs no job. Where no draft PDF was made, nothing is asked: a
person asks for the approved PDF on the report itself -- unless the draft's own job failed for
want of a converter, a reason the approved version's PDF state keeps (``pdf_disabled``, not
offered: ``report_variants.variant_pdf``).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from aia_core.application.client_report import CLIENT_REPORT_ARTIFACT_TYPE, require_client_gate
from aia_core.application.contextual_report import CONTEXT_REPORT_ARTIFACT_TYPE
from aia_core.application.report import INTERNAL_REPORT_ARTIFACT_TYPE
from aia_core.application.report_variants import approval_asks_pdf, draft_pdf_ready, request_pdf
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.scope import Permission, StudyContext
from aia_core.infrastructure.artifact_repository import Artifact, ArtifactStatus
from aia_core.infrastructure.storage import ArtifactStore

REPORT_ARTIFACT_TYPES = frozenset(
    {INTERNAL_REPORT_ARTIFACT_TYPE, CONTEXT_REPORT_ARTIFACT_TYPE, CLIENT_REPORT_ARTIFACT_TYPE}
)


class ReportNotApprovable(Exception):
    """The artifact is not a valid stored report of this run."""


def approve_report(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    artifact_id: str,
    note: str = "",
) -> Artifact:
    """Approve ``artifact_id`` as ``run_id``'s report, freeze it and, where its draft's own PDF
    is ready, ask for its approved PDF. A report already approved records no second decision
    and asks for nothing again (a person asks for a PDF on the report itself); one approved
    before approving froze is frozen now, so no approved version stays deletable."""
    scope.require(Permission.SIGN_OFF_DELIVERABLE)
    ResearchRuns(session, scope).get(run_id)
    artifacts = research_artifacts(session, scope, store)
    artifact = artifacts.get(artifact_id)
    if (
        artifact.artifact_type not in REPORT_ARTIFACT_TYPES
        or artifact.status is not ArtifactStatus.VALID
        or artifact.metadata.get("run_id") != run_id
    ):
        raise ReportNotApprovable(artifact_id)
    if artifact.is_approved:
        # Approved before this release, which froze nothing: invalidate_stage and delete spare
        # only a frozen artifact. Freezing is no decision, so the ledger keeps its one row.
        return artifact if artifact.is_frozen else artifacts.freeze(artifact_id)
    if artifact.artifact_type == CLIENT_REPORT_ARTIFACT_TYPE:
        # The client deliverable's gate (RD0, MVPQ-09): it blocks, never a flag a reviewer
        # approves past.
        require_client_gate(artifacts, artifact)
    # Read while it is still a draft: its own PDF, under the draft's key.
    ready = draft_pdf_ready(session, scope, store, docx=artifact, run_id=run_id)
    artifacts.approve(artifact_id, note=note)
    approved = artifacts.freeze(artifact_id)
    if approval_asks_pdf(scope, approved, pdf_ready=ready):
        request_pdf(
            session,
            scope,
            store,
            docx=approved,
            run_id=run_id,
            deep_research_run_id=approved.metadata.get("deep_research_run_id"),
        )
    return approved
