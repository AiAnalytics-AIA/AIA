"""The working copy's writer of vocabulary operations (ADR 0029 decision 3; WCE2d).

``apply_edit_ops`` applies a batch of the vocabulary's operations (``domain/edit_ops.py``) to the
working copy as it was loaded, in order, and saves the result once through
:meth:`StudyWorkspaceRepository.save`, the one persistence point, which logs each operation under
its own ``op`` (``domain/edit_log.py`` ``write_rows``) in the same transaction. An operation that
writes a locked Sociomap input (decision 8), or that the copy cannot take, is refused with its word
and the rest still apply. A copy whose ids the web's store keeps (``item_ids.stores_item_ids``) is
settled as the store settles it, so a reworded research question keeps its links (F-WCE1-1).

The caller has checked the copy is the one the batch was decided on and owns the transaction; the
save takes the Study's lock and refuses a copy that moved meanwhile as stale.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..domain.design_fields import Touch
from ..domain.edit_log import ActorKind, OpSource, WriteBy
from ..domain.edit_ops import IdKind, Refused, apply_edit, lock_refusal, new_item_id, touches
from ..domain.item_ids import settle_item_ids, stores_item_ids
from ..domain.research_design import SampleSizeLimits
from ..domain.research_template import research_template
from ..domain.scope import Permission, StudyContext
from ..domain.workspace import WorkingContent, WorkingSave, edited_from_current
from ..infrastructure.study_workspace_repository import (
    StudyWorkspaceRepository,
    WorkspaceConflict,
)
from .research import readiness_in_force

__all__ = ["AppliedOps", "EditsRefused", "apply_edit_ops", "apply_person_edits"]


@dataclass(frozen=True, slots=True)
class AppliedOps:
    """What a batch did: the positions in it refused, with their words, and the save (``None``
    when nothing applied)."""

    refused: Mapping[int, str]
    saved: WorkingSave | None


def _replaying(ids: list[str]) -> Callable[[IdKind], str]:
    """The ids an operation was applied with, handed out again in order, so what it touched names
    the items it added."""
    replay = iter(ids)
    return lambda _kind: next(replay)


def apply_edit_ops(
    session: Session,
    scope: StudyContext,
    current: WorkingContent,
    edits: Sequence[BaseModel],
    *,
    by: WriteBy,
    reason: str,
    sample_size: SampleSizeLimits | None,
    whole_batch: bool = False,
) -> AppliedOps:
    """Apply ``edits`` to ``current``, in order, and save the copy once, logged as ``by``.

    ``sample_size``: the readiness limits a ``set_n`` is held to. The save names ``current``'s
    revision, so a copy that moved meanwhile is refused as stale by the repository. ``whole_batch``:
    a batch with any refused edit saves nothing (a person's, :func:`apply_person_edits`)."""
    content: dict[str, Any] = (
        dict(current.content) if current.content is not None else research_template()
    )
    analysis = current.analysis
    # Settled after each edit, as the web's store settles each change: over a whole batch, a list
    # going from one item to two reads a reword beside an add as a new item and drops its links.
    settles = stores_item_ids(content, analysis)
    refused: dict[int, str] = {}
    ops: list[tuple[Mapping[str, Any], frozenset[Touch]]] = []
    for position, edit in enumerate(edits):
        locked = lock_refusal(edit, content)
        if locked is not None:
            refused[position] = locked
            continue
        made: list[str] = []

        def new_id(kind: IdKind, made: list[str] = made) -> str:
            made.append(new_item_id(kind))
            return made[-1]

        applied = apply_edit(content, analysis, edit, new_id=new_id, sample_size=sample_size)
        if isinstance(applied, Refused):
            refused[position] = applied.reason
            continue
        touched = touches(edit, content, new_id=_replaying(made))
        ops.append((edit.model_dump(mode="json", exclude={"why"}), touched))
        content, analysis = settle_item_ids((content, analysis), applied) if settles else applied
    if not ops or (whole_batch and refused):
        return AppliedOps(refused=refused, saved=None)
    saved = StudyWorkspaceRepository(session).save(
        scope,
        content=content,
        analysis=analysis,
        base_revision=current.revision,
        reason=reason,
        by=by,
        ops=ops,
    )
    return AppliedOps(refused=refused, saved=saved)


class EditsRefused(Exception):
    """A person's batch the working copy did not take whole: each refused position with its word,
    and the revision it was judged on. Nothing of the batch was saved."""

    def __init__(self, refused: Mapping[int, str], current_revision: int | None) -> None:
        super().__init__("the working copy did not take every edit of the batch")
        self.refused = dict(refused)
        self.current_revision = current_revision


def apply_person_edits(
    session: Session,
    scope: StudyContext,
    edits: Sequence[BaseModel],
    *,
    base_revision: int | None,
    reason: str,
) -> tuple[WorkingSave, WorkingContent]:
    """A person's edits from a stage (``POST …/workspace/ops``, working-copy-edit-ops WCE3a), made
    by the person through the interface, and the copy as saved.

    The batch names the revision it was edited from, and one from any other revision is refused
    (``stale_revision``), as a whole-copy save is: the merge of ADR 0029 decision 4 is WCE5's. The
    batch is all or nothing: the stage applied every edit to its own copy, so a copy that keeps
    some of them is one the person never saw; any refusal raises :class:`EditsRefused` and the
    nothing is saved. A ``set_n`` is held to the readiness limits in force."""
    scope.require(Permission.EDIT_STUDY)
    scope.require_open_study()
    workspace = StudyWorkspaceRepository(session)
    working = workspace.content(scope)
    if not edited_from_current(base_revision, working.revision, working.content, working.analysis):
        raise WorkspaceConflict(
            "the working content changed since it was loaded",
            reason="stale_revision",
            current_revision=working.revision,
        )
    limits, _ = readiness_in_force(session, scope)
    batch = apply_edit_ops(
        session,
        scope,
        working,
        edits,
        by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
        reason=reason,
        sample_size=limits.sample_size,
        whole_batch=True,
    )
    if batch.refused:
        raise EditsRefused(batch.refused, working.revision)
    assert batch.saved is not None  # a batch with nothing refused applied at least one edit
    return batch.saved, workspace.content(scope)
