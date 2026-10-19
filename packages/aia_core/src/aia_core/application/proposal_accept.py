"""Accept a design proposal into the working copy and the design, in one transaction (ADR 0026).

An AI proposal -- an agent job's (``ResearchAgentJobs.accept``) or a Design Research run's
(``DesignResearchProposals.accept``) -- was made on one Design Revision, which names the working
revision it came from (decision 5). Accepting it, under the Study row lock every design and
working-copy writer takes:

1. refuses it as stale (:class:`StaleProposal`) when the head Design Revision moved
   (``design_moved``), when its baseline is not known (``unknown_baseline``: a revision written
   before every writer named its working revision), or when an item it changes also changed in
   the working copy since that baseline (``items_changed``, the items named);
2. merges it into the working copy *now*, item by item: what it touches takes its value,
   everything else keeps the person's (:func:`~aia_core.domain.design_items.merge_items`);
3. saves the merged working copy, based on the revision the person had
   (``expected_workspace_revision``; another is ``stale_revision``);
4. submits the merged content as the new Design Revision, naming that working revision.

The caller writes its ledger row in the same transaction and commits; nothing here commits, so a
failure at any step writes none of them (decision 6). The browser then reloads the working copy;
it no longer writes the proposal back itself.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..domain.design import DesignRejected, DesignRevision
from ..domain.design_items import Documents, ItemKey, design_items, merge_items
from ..domain.scope import Permission, StudyContext
from ..domain.workspace import WorkingSave
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.study_workspace_repository import (
    StudyWorkspaceRepository,
    WorkspaceConflict,
)

__all__ = [
    "AcceptedProposal",
    "StaleProposal",
    "accept_into_working_copy",
    "proposal_baseline",
]


class StaleProposal(DesignRejected):
    """The proposal cannot be accepted as it stands: rebuild it on the current design.

    ``why`` is ``design_moved``, ``unknown_baseline`` or ``items_changed``; ``conflicting_items``
    names, for the last, each item the proposal changes that the working copy changed too.
    """

    def __init__(
        self, message: str, *, why: str, conflicting_items: Iterable[ItemKey] = ()
    ) -> None:
        super().__init__(message, reason="stale_proposal")
        self.why = why
        self.conflicting_items = tuple(sorted(conflicting_items))

    def details(self) -> dict[str, object]:
        """The refusal's details, as the API answers them."""
        return {
            "reason": self.why,
            "conflicting_items": [str(k) for k in self.conflicting_items],
        }


@dataclass(frozen=True, slots=True)
class AcceptedProposal:
    """What an accept wrote: the Design Revision and the working copy, the same design."""

    revision: DesignRevision
    created: bool
    working: WorkingSave
    merged: Documents


def proposal_baseline(
    session: Session, scope: StudyContext, design: DesignRevision
) -> Documents | None:
    """The working copy a proposal on ``design`` was made from, or ``None`` when unknown."""
    if design.workspace_revision is None:
        return None
    stored = StudyWorkspaceRepository(session).at_revision(scope, design.workspace_revision)
    if stored is None:
        return None
    return Documents(content=dict(stored.content or {}), analysis=stored.analysis)


def accept_into_working_copy(
    session: Session,
    scope: StudyContext,
    *,
    design_revision_id: str,
    proposed: Documents,
    expected_workspace_revision: int,
    source_stage: str,
    reason: str,
    touched: Iterable[ItemKey] | None = None,
) -> AcceptedProposal:
    """Check, merge and write a proposal made on ``design_revision_id`` (the module's steps 1-4).

    ``proposed`` is the design the proposal would make of its baseline; ``touched`` the items it
    changes, as the worker recorded them, else computed here from the baseline. Needs
    ``EDIT_STUDY`` and ``APPROVE_GATE`` on an open Study: only a person accepts (ADR 0019 gate 1).
    """
    scope.require(Permission.EDIT_STUDY)
    scope.require(Permission.APPROVE_GATE)
    scope.require_open_study()
    designs = StudyDesignRepository(session, scope)
    workspaces = StudyWorkspaceRepository(session)
    designs.lock()
    design = designs.get(design_revision_id)
    latest = designs.latest()
    if latest is None or latest.revision_id != design_revision_id:
        raise StaleProposal("a newer Design Revision was submitted since", why="design_moved")
    baseline = proposal_baseline(session, scope, design)
    if baseline is None:
        raise StaleProposal(
            "the proposal's design names no working revision to check it against",
            why="unknown_baseline",
        )
    now = workspaces.content(scope)
    if now.revision != expected_workspace_revision:
        raise WorkspaceConflict(
            "the working content changed since it was loaded",
            reason="stale_revision",
            current_revision=now.revision,
        )
    current = Documents(content=dict(now.content or {}), analysis=now.analysis)
    touched_set = frozenset(touched) if touched is not None else design_items(baseline, proposed)
    conflicts = touched_set & design_items(baseline, current)
    if conflicts:
        raise StaleProposal(
            "the working copy changed an item the proposal changes",
            why="items_changed",
            conflicting_items=conflicts,
        )
    merged = merge_items(proposed, current, touched_set)
    saved = workspaces.save(
        scope,
        content=merged.content,
        analysis=merged.analysis,
        base_revision=now.revision,
        reason=reason,
    )
    stored = workspaces.at_revision(scope, saved.revision)
    assert stored is not None  # save has just written or found it
    revision, created = designs.submit_if_current(
        content=stored.content,
        source_stage=source_stage,
        expected_revision_id=design_revision_id,
        workspace_revision=saved.revision,
    )
    return AcceptedProposal(revision=revision, created=created, working=saved, merged=merged)
