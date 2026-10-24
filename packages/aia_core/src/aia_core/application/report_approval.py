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

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from sqlalchemy.orm import Session

from aia_core.application.client_report import CLIENT_REPORT_ARTIFACT_TYPE, require_client_gate
from aia_core.application.contextual_report import CONTEXT_REPORT_ARTIFACT_TYPE
from aia_core.application.report import INTERNAL_REPORT_ARTIFACT_TYPE
from aia_core.application.report_editor_saves import coverage
from aia_core.application.report_variants import approval_asks_pdf, draft_pdf_ready, request_pdf
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.report.editor import (
    EDIT_ARTIFACT_TYPES,
    SeenEdit,
    UnsavedEdits,
    unsaved_edits,
)
from aia_core.domain.scope import Permission, StudyContext
from aia_core.infrastructure.artifact_repository import Artifact, ArtifactRepository, ArtifactStatus
from aia_core.infrastructure.report_editor_repository import ReportEditorRepository
from aia_core.infrastructure.storage import ArtifactStore

#: Each approvable report by its stored type, as the approval names it (report-delivery RD3, G66):
#: the client report is the one deliverable that leaves the organization.
REPORT_KINDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        INTERNAL_REPORT_ARTIFACT_TYPE: "internal",
        CONTEXT_REPORT_ARTIFACT_TYPE: "with_review",
        CLIENT_REPORT_ARTIFACT_TYPE: "client",
    }
)
#: A version a researcher saved in the editor (artifact-report RPT8c), by kind: approved as
#: exactly that version, of whichever line, and frozen as any approved report is. The client
#: report is never edited.
EDITED_REPORT_KINDS: Final[Mapping[str, str]] = MappingProxyType(
    {EDIT_ARTIFACT_TYPES["internal"]: "internal", EDIT_ARTIFACT_TYPES["context"]: "with_review"}
)
#: Every report a person approves, composed or edited.
APPROVABLE_KINDS: Final[Mapping[str, str]] = MappingProxyType(
    {**REPORT_KINDS, **EDITED_REPORT_KINDS}
)
#: The kinds a client receives: never internal_only.
CLIENT_REPORT_KINDS: Final = frozenset({"client"})
REPORT_ARTIFACT_TYPES = frozenset(REPORT_KINDS)


class ReportNotApprovable(Exception):
    """The artifact is not a valid stored report of this run."""


class ReportVersionStale(Exception):
    """A version asked to be approved as its line's newest is no longer the newest: a save
    stored the next koncept while the person read the question (artifact-report RPT8d)."""

    def __init__(self, artifact_id: str, newest_artifact_id: str, koncept: int) -> None:
        super().__init__(f"{artifact_id} is not its line's newest version ({newest_artifact_id})")
        self.newest_artifact_id = newest_artifact_id
        self.koncept = koncept


class ReportEditsUnsaved(Exception):
    """An edited version asked to be approved as its line's newest does not hold an edit made in
    the editor (artifact-report RPT8f): the approving page's edit has not reached AIA, or an edit
    AIA received is later than the version's last change. The server decides, under the line's
    lock, so no edit made before the approval left is approved without being in the version."""

    def __init__(self, artifact_id: str, reason: UnsavedEdits) -> None:
        super().__init__(f"{artifact_id} does not hold every edit made ({reason.value})")
        self.reason = reason


def approve_report(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    artifact_id: str,
    note: str = "",
    newest_of_line: bool = False,
    seen_edit: SeenEdit | None = None,
) -> Artifact:
    """Approve ``artifact_id`` as ``run_id``'s report, freeze it and, where its draft's own PDF
    is ready, ask for its approved PDF. A report already approved records no second decision
    and asks for nothing again (a person asks for a PDF on the report itself); one approved
    before approving froze is frozen now, so no approved version stays deletable.

    ``newest_of_line``: approve a version of a report-editor line only while it is that line's
    newest (the editor shows the newest), under the line's lock a save also takes, so a save
    and this approval take their turn; :class:`ReportVersionStale` otherwise. Under the same lock,
    and for every edited version whatever the caller asks (RPT8f: the server decides),
    :class:`ReportEditsUnsaved` while an edit of the line's open session, or ``seen_edit`` (the
    approving page's last edit start), is not held by it (``unsaved_edits``)."""
    scope.require(Permission.SIGN_OFF_DELIVERABLE)
    ResearchRuns(session, scope).get(run_id)
    artifacts = research_artifacts(session, scope, store)
    artifact = artifacts.get(artifact_id)
    if (
        artifact.artifact_type not in APPROVABLE_KINDS
        or artifact.status is not ArtifactStatus.VALID
        or artifact.metadata.get("run_id") != run_id
    ):
        raise ReportNotApprovable(artifact_id)
    if newest_of_line or (
        artifact.artifact_type in EDITED_REPORT_KINDS and not artifact.is_approved
    ):
        _check_line(session, scope, artifact, seen_edit, newest=newest_of_line)
    if artifact.is_approved:
        # Approved before this release, which froze nothing: invalidate_stage and delete spare
        # only a frozen artifact. Freezing is no decision, so the ledger keeps its one row.
        return artifact if artifact.is_frozen else artifacts.freeze(artifact_id)
    if artifact.artifact_type == CLIENT_REPORT_ARTIFACT_TYPE:
        # The client deliverable's gate (RD0, MVPQ-09): it blocks, never a flag a reviewer
        # approves past.
        require_client_gate(artifacts, artifact)
    authors = (
        _line_authors(session, scope, artifacts, artifact)
        if artifact.artifact_type in EDITED_REPORT_KINDS
        else frozenset()
    )
    # Read while it is still a draft: its own PDF, under the draft's key.
    ready = draft_pdf_ready(session, scope, store, docx=artifact, run_id=run_id)
    artifacts.approve(artifact_id, note=note, co_producers=authors)
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


def _check_line(
    session: Session,
    scope: StudyContext,
    artifact: Artifact,
    seen: SeenEdit | None,
    *,
    newest: bool,
) -> None:
    """Under the line's lock: with ``newest``, the version is its line's newest, else
    :class:`ReportVersionStale`; and it holds every edit the line's open session reported, else
    :class:`ReportEditsUnsaved`."""
    repo = ReportEditorRepository(session, scope)
    version = repo.version(artifact.artifact_id)
    if version is None:
        raise ReportNotApprovable(artifact.artifact_id)
    repo.lock_line(version.line_id)  # as store_save does, before the versions are read
    last = repo.versions(version.line_id)[-1]
    if newest and last.artifact_id != artifact.artifact_id:
        raise ReportVersionStale(artifact.artifact_id, last.artifact_id, last.koncept)
    marks = repo.edit_marks(version.line_id, also=seen.document_key if seen else None)
    reason = unsaved_edits(coverage(version, artifact), marks, seen)
    if reason is not None:
        raise ReportEditsUnsaved(artifact.artifact_id, reason)


def _line_authors(
    session: Session, scope: StudyContext, artifacts: ArtifactRepository, artifact: Artifact
) -> frozenset[str]:
    """Everyone whose work an edited version is: the person who produced its line's composed
    report (koncept 1, which names no author: a report with literature is prepared by a
    person) and everyone who saved the line up to it, not only the one person its artifact
    records as producer (a save's first author). Where self-approval is off, none of them may
    approve it; where it is on, one who does is recorded as self-approving."""
    repo = ReportEditorRepository(session, scope)
    version = repo.version(artifact.artifact_id)
    if version is None:
        raise ReportNotApprovable(artifact.artifact_id)
    composed = artifacts.get(version.line_id).produced_by_user_id
    saved = {
        author
        for earlier in repo.versions(version.line_id)
        if earlier.koncept <= version.koncept
        for author in earlier.authors
    }
    return frozenset(saved | ({composed} if composed else set()))
