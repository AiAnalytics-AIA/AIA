"""A Design Research run's proposal, and a person's accept of it into a new Design Revision.

ADR 0021 decision 1 with ADR 0019 gate 1 (``deep-research-web-search.md`` chunk 29). A
``DESIGN_RESEARCH`` run is advisory: :meth:`DesignResearchProposals.proposal` reads what it
proposes from its own sealed bundle (built by code,
:func:`~aia_core.domain.deep_research.design_proposals.design_research_proposal`), and only a
person's :meth:`~DesignResearchProposals.accept` writes a revision -- the baseline design with
the items they took added under ``design_research``, nothing else changed.

This is the one place Deep Research meets a design writer, and it is deliberately outside
``application/deep_research.py``, which ``layer_check`` keeps from naming one: the run is read
through :class:`~aia_core.application.deep_research.DeepResearchRuns` (found only through the
Study, its bundle verified against its seal, its lineage re-resolved), and the revision is
written through :meth:`StudyDesignRepository.submit_if_current`, as an agent job's accept is.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..domain.deep_research.design_proposals import (
    DesignProposalRefused,
    DesignResearchProposal,
    apply_to_design,
    design_research_proposal,
    selection_id,
)
from ..domain.design import DesignRejected, DesignRevision
from ..domain.scope import Permission, StudyContext
from ..domain.workflow import WorkflowRunStatus
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.workflow_repository import WorkflowRepository
from .deep_research import DeepResearchRuns, LineageChanged

__all__ = ["DesignResearchProposals"]

#: The stage a Design Research accept is recorded as having come from: the research plan,
#: whose context it informs (``DESIGN_SOURCE_STAGES``).
SOURCE_STAGE = "plan"


@dataclass(frozen=True, slots=True)
class DesignResearchProposals:
    """Design Research proposals of the Study in scope. The caller owns the transaction."""

    session: Session
    scope: StudyContext

    def proposal(self, run_id: str, *, store: ArtifactStore) -> DesignResearchProposal:
        """What a completed, governed Design Research run of this Study proposes.

        Refusals are :class:`~aia_core.domain.design.DesignRejected` with a reason:
        ``proposal_not_ready`` (not completed), ``not_design_research`` (a legacy or an
        interpretation run), ``bundle_mismatch``. A run of another Study is not found.
        """
        self.scope.require(Permission.VIEW_RESULTS)
        runs = DeepResearchRuns(self.session, self.scope)
        run = runs.get(run_id)
        if run["status"] is not WorkflowRunStatus.COMPLETED:
            raise DesignRejected(
                "the Deep Research run has not completed", reason="proposal_not_ready"
            )
        if run["metadata"].get("purpose") != "DESIGN_RESEARCH":
            raise DesignRejected(
                "only a governed Design Research run proposes a design change",
                reason="not_design_research",
            )
        provenance = runs.provenance(run_id, store=store)
        try:
            return design_research_proposal(provenance, runs.bundle(run_id, store=store))
        except DesignProposalRefused as exc:
            raise DesignRejected(str(exc), reason=exc.reason) from exc

    def accept(
        self,
        run_id: str,
        *,
        item_ids: Sequence[str],
        expected_revision_id: str,
        store: ArtifactStore,
    ) -> tuple[DesignRevision, bool, dict[str, Any]]:
        """A person takes the items they chose: a new Design Revision, and its record.

        Needs ``EDIT_STUDY`` and ``APPROVE_GATE`` on an open Study; the worker's scope holds
        no ``APPROVE_GATE`` (ADR 0019 decision 6). The run's lineage must still resolve and
        ``expected_revision_id`` must be both the revision the run researched and the
        Study's newest (``stale_proposal``). Returns the revision, whether it is new, and its
        content, for the client's working copy. An accept that changes nothing writes no
        revision and no ledger row.
        """
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.APPROVE_GATE)
        self.scope.require_open_study()
        proposal = self.proposal(run_id, store=store)
        if expected_revision_id != proposal.design_revision_id:
            raise DesignRejected(
                "the proposal was researched from another Design Revision",
                reason="stale_proposal",
            )
        try:
            DeepResearchRuns(self.session, self.scope).resolve_lineage(run_id, store=store)
        except LineageChanged as exc:
            raise DesignRejected(str(exc), reason="stale_proposal") from exc
        designs = StudyDesignRepository(self.session, self.scope)
        baseline = designs.content(proposal.design_revision_id)
        try:
            content = apply_to_design(baseline, proposal, item_ids)
        except DesignProposalRefused as exc:
            raise DesignRejected(str(exc), reason=exc.reason) from exc
        revision, created = designs.submit_if_current(
            content=content, source_stage=SOURCE_STAGE, expected_revision_id=expected_revision_id
        )
        if created:
            project_id = designs.project_id()
            assert project_id is not None  # submit_if_current has just written to it
            WorkflowRepository(self.session, self.scope).record_design_research_acceptance(
                run_id,
                selection_id=selection_id(run_id, item_ids),
                item_ids=sorted(set(item_ids)),
                revision_id=revision.revision_id,
                project_id=project_id,
                project_revision=revision.revision,
                artifact_id=proposal.evidence_bundle_artifact_id,
            )
        return revision, created, content
