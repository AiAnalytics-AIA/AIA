"""A person's review of a run's key findings (artifact-analysis ANL11, research build spec szz/A7).

:func:`review_finding` writes one decision on one key finding to the approval ledger, after
checking the finding is one the module's re-checked outcome holds and, for an edit, that every
number in the new wording is backed by a claim the finding cites (``domain/analysis/review.py``).
:func:`finding_reviews` reads each finding's decision in force. A decision is bound to the module
outcome it was made on, so it holds on an analysis retry that reuses the outcome and on nothing
else. Both are found only through the study's own run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from aia_core.application.analysis import ModuleOutcomeKind
from aia_core.application.analysis_results import (
    ReconstructionRefused,
    module_outcomes,
    reconstruct_module,
)
from aia_core.domain.analysis.review import (
    FindingDecision,
    FindingKey,
    FindingReview,
    review_comment,
    reviews_of,
    wording_problem,
)
from aia_core.domain.approval_ledger import ApprovalSubject
from aia_core.domain.scope import Permission, StudyContext
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.workflow_repository import WorkflowRepository

__all__ = ["FindingReviewRefused", "finding_reviews", "review_finding"]

_SUBJECT = [ApprovalSubject.ANALYSIS_FINDING]


@dataclass
class FindingReviewRefused(Exception):
    """A decision this finding cannot take, by name: ``finding_not_found`` (the module's outcome
    holds no such completed finding), ``wording_empty``, ``wording_too_long`` or
    ``wording_numbers`` (``numbers``: the ones no cited claim backs)."""

    reason: str
    numbers: tuple[float, ...] = field(default_factory=tuple)

    def __str__(self) -> str:
        return self.reason


def review_finding(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    key: FindingKey,
    decision: FindingDecision,
    wording: str | None = None,
) -> FindingReview | None:
    """Record ``decision`` on the finding ``key`` names and return its decision in force
    (``None`` after an undo). Refused (:class:`FindingReviewRefused`) before anything is written;
    an undo of a finding with no decision in force writes nothing."""
    scope.require(Permission.APPROVE_GATE)
    try:
        module = reconstruct_module(session, scope, store, run_id=run_id, module_id=key.module)
    except ReconstructionRefused as exc:
        if exc.reason in ("not_in_run", "no_outcome"):
            raise FindingReviewRefused("finding_not_found") from exc
        raise
    if (
        module.outcome is not ModuleOutcomeKind.COMPLETED
        or module.result is None
        or key.index >= len(module.result.key_findings)
    ):
        raise FindingReviewRefused("finding_not_found")
    text = None
    if decision is FindingDecision.EDITED:
        finding = module.result.key_findings[key.index]
        cited = [c for c in module.result.claims if c.claim_id in finding.claim_ids]
        problem = wording_problem(
            wording or "",
            cited_values=[c.value for c in cited],
            names=[*(c.row.cell for c in cited), finding.text],
        )
        if problem == "empty":
            raise FindingReviewRefused("wording_empty")
        if problem == "too_long":
            raise FindingReviewRefused("wording_too_long")
        if isinstance(problem, tuple):
            raise FindingReviewRefused("wording_numbers", problem)
        text = (wording or "").strip()
    repo = WorkflowRepository(session, scope)
    outcomes = {key.module: module.artifact_id}
    before = repo.ledger(_SUBJECT)
    if decision is FindingDecision.UNDONE and key not in reviews_of(before, outcomes):
        return None
    entry = repo.record_finding_review(
        run_id,
        subject_id=key.subject_id(run_id),
        decision=decision.value,
        comment=review_comment(module.artifact_id, text),
    )
    return reviews_of([*before, entry], outcomes).get(key)


def finding_reviews(
    session: Session, scope: StudyContext, *, run_id: str
) -> dict[FindingKey, FindingReview]:
    """Each of the run's findings' decision in force; a finding no one decided is absent."""
    scope.require(Permission.EDIT_STUDY)
    outcomes = module_outcomes(session, scope, run_id=run_id)
    return reviews_of(WorkflowRepository(session, scope).ledger(_SUBJECT), outcomes)
