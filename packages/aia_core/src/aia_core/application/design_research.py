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
written through :func:`~.proposal_accept.accept_into_working_copy`, as an agent job's accept is:
the working copy takes the items too, in the same transaction, and the Design Revision names the
working revision it wrote (ADR 0026 decisions 5-6).
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
from ..domain.design import DesignRejected
from ..domain.design_items import Documents
from ..domain.edit_log import ActorKind, OpSource, WriteBy
from ..domain.research_agents import context_snapshot
from ..domain.scope import Permission, StudyContext
from ..domain.workflow import WorkflowRunStatus
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from ..infrastructure.storage import ArtifactStore
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.study_workspace_repository import StudyWorkspaceRepository
from ..infrastructure.workflow_repository import WorkflowRepository
from .deep_research import DeepResearchRuns, LineageChanged
from .proposal_accept import (
    AcceptedProposal,
    StaleProposal,
    accept_into_working_copy,
    proposal_baseline,
)

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
        expected_workspace_revision: int,
        store: ArtifactStore,
    ) -> AcceptedProposal:
        """A person takes the items they chose: a new Design Revision, and its record.

        Needs ``EDIT_STUDY`` and ``APPROVE_GATE`` on an open Study; the worker's scope holds
        no ``APPROVE_GATE`` (ADR 0019 decision 6). The run's lineage must still resolve and
        ``expected_revision_id`` must be the revision the run researched (``stale_proposal``,
        ``design_moved``); a newer one alone stales nothing (WCE5), and a run whose items were
        accepted once is spent (``proposal_already_accepted``). The items go into the working
        copy at ``expected_workspace_revision`` too, field by field, in the same transaction, and
        the Design Revision names the working revision written (ADR 0026 decisions 5-6); an edit
        of the person's to a field the items change refuses it (``stale_proposal``,
        ``items_changed``). An accept that changes no design writes no ledger row.
        """
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.APPROVE_GATE)
        self.scope.require_open_study()
        proposal = self.proposal(run_id, store=store)
        if expected_revision_id != proposal.design_revision_id:
            raise StaleProposal(
                "the proposal was researched from another Design Revision", why="design_moved"
            )
        # A newer Design Revision no longer stales a proposal (WCE5): a run whose items are in the
        # design is spent by its accept, read under the Study lock the accept writes under.
        StudyDesignRepository(self.session, self.scope).lock()
        if WorkflowRepository(self.session, self.scope).design_research_accepted(run_id):
            raise DesignRejected(
                "items of this run are already in the design", reason="proposal_already_accepted"
            )
        try:
            DeepResearchRuns(self.session, self.scope).resolve_lineage(run_id, store=store)
        except LineageChanged as exc:
            raise StaleProposal(str(exc), why="lineage_changed") from exc
        designs = StudyDesignRepository(self.session, self.scope)
        design = designs.get(proposal.design_revision_id)
        baseline = proposal_baseline(self.session, self.scope, design)
        if baseline is None:
            raise StaleProposal(
                "the proposal's design names no working revision to check it against",
                why="unknown_baseline",
            )
        try:
            content = apply_to_design(baseline.content, proposal, item_ids)
        except DesignProposalRefused as exc:
            raise DesignRejected(str(exc), reason=exc.reason) from exc
        accepted = accept_into_working_copy(
            self.session,
            self.scope,
            design_revision_id=expected_revision_id,
            proposed=Documents(content=content, analysis=baseline.analysis),
            expected_workspace_revision=expected_workspace_revision,
            source_stage=SOURCE_STAGE,
            reason="design_research_accepted",
            by=WriteBy(
                ActorKind.PERSON, self.scope.actor_id, OpSource.DESIGN_RESEARCH_ACCEPT, run_id
            ),
        )
        # The accept may land on a newer working copy than the run's baseline (WCE5): the copy
        # it merged into, as the person had it, and the merged one a design job will read,
        # checked before anything is committed.
        before = StudyWorkspaceRepository(self.session).at_revision(
            self.scope, expected_workspace_revision
        )
        assert before is not None  # the accept has just merged into it
        self._require_design_jobs_keep_working(dict(before.content or {}), accepted.merged.content)
        revision, created = accepted.revision, accepted.created
        if created:
            project_id = designs.project_id()
            assert project_id is not None  # the accept has just written to it
            WorkflowRepository(self.session, self.scope).record_design_research_acceptance(
                run_id,
                selection_id=selection_id(run_id, item_ids),
                item_ids=sorted(set(item_ids)),
                revision_id=revision.revision_id,
                project_id=project_id,
                project_revision=revision.revision,
                artifact_id=proposal.evidence_bundle_artifact_id,
            )
        return accepted

    def _require_design_jobs_keep_working(
        self, baseline: dict[str, Any], content: dict[str, Any]
    ) -> None:
        """Refuse an accept that would push the design past what a design job can read.

        Every design job starts from :func:`~aia_core.domain.research_agents.context_snapshot`,
        the whole design plus the Study's approved knowledge inside a 64 KB budget. The
        block's own bound cannot see the rest of the design, so the snapshot a job would
        build is built here, before and after. A baseline already over the budget is not
        made worse in kind by evidence beside it, and is not this accept's to refuse.
        """
        knowledge = ClientKnowledgeRepository(self.session).for_study(self.scope)
        try:
            context_snapshot(baseline, knowledge)
        except ValueError:
            return
        try:
            context_snapshot(content, knowledge)
        except ValueError as exc:
            raise DesignRejected(
                "accepting these items would leave the design too large for the design "
                "jobs' context; accept fewer items",
                reason="design_context_too_large",
            ) from exc
