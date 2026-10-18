"""A person approves a run's stored report (complete-study-report B2).

The approval is the artifact repository's own: ``SIGN_OFF_DELIVERABLE``, the
independence the scope's self-approval policy requires, and a row in the approval ledger.
This module decides only *which* artifacts are a run's reports: the internal report its
REPORT step stored, the report with literature or the client report stored for it, each
found through the Study's run and checked to name that run. Approval is a person's sign-off
on the stored document; what the client report may contain was decided when it was composed.

Approving a version (research-integrity-report D2) also freezes it -- it can no longer be
deleted or superseded in place -- and, for a report the worker renders, asks for the PDF of its
approved export in the same transaction. A Study that starts no work asks for nothing; its PDF
state says why (``study_closed``), and its DOCX is still downloaded stamped, which needs no job.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from aia_core.application.client_report import CLIENT_REPORT_ARTIFACT_TYPE
from aia_core.application.contextual_report import CONTEXT_REPORT_ARTIFACT_TYPE
from aia_core.application.report import INTERNAL_REPORT_ARTIFACT_TYPE
from aia_core.application.report_variants import approval_asks_pdf, request_pdf
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
    """Approve ``artifact_id`` as ``run_id``'s report, freeze it and ask for its approved PDF.
    A report already approved is returned as it is: one decision per report, never a second
    ledger row, and nothing asked again (a person asks for a PDF on the report itself)."""
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
        return artifact
    artifacts.approve(artifact_id, note=note)
    approved = artifacts.freeze(artifact_id)
    if approval_asks_pdf(scope, approved):
        request_pdf(
            session,
            scope,
            store,
            docx=approved,
            run_id=run_id,
            deep_research_run_id=approved.metadata.get("deep_research_run_id"),
        )
    return approved
