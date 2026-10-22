"""The working copy's writer of vocabulary operations (ADR 0029 decision 3; WCE2d).

``apply_edit_ops`` applies a batch of the vocabulary's operations (``domain/edit_ops.py``) to the
working copy as it was loaded, in order, and saves the result once through
:meth:`StudyWorkspaceRepository.save`, the one persistence point, which logs each operation under
its own ``op`` (``domain/edit_log.py`` ``write_rows``) in the same transaction. An operation that
writes a locked Sociomap input (decision 8), or that the copy cannot take, is refused with its word
and the rest still apply. A copy whose ids the web's store keeps (``item_ids.stores_item_ids``) is
settled as the store settles it, so a reworded research question keeps its links (F-WCE1-1).

The caller holds the Study's lock, has checked the copy is the one the batch was decided on, and
owns the transaction.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..domain.design_fields import Touch
from ..domain.edit_log import WriteBy
from ..domain.edit_ops import IdKind, Refused, apply_edit, lock_refusal, new_item_id, touches
from ..domain.item_ids import settle_item_ids, stores_item_ids
from ..domain.research_design import SampleSizeLimits
from ..domain.research_template import research_template
from ..domain.scope import StudyContext
from ..domain.workspace import WorkingContent, WorkingSave
from ..infrastructure.study_workspace_repository import StudyWorkspaceRepository

__all__ = ["AppliedOps", "apply_edit_ops"]


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
) -> AppliedOps:
    """Apply ``edits`` to ``current``, in order, and save the copy once, logged as ``by``.

    ``sample_size``: the readiness limits a ``set_n`` is held to. The save names ``current``'s
    revision, so a copy that moved meanwhile is refused as stale by the repository."""
    content: dict[str, Any] = (
        dict(current.content) if current.content is not None else research_template()
    )
    analysis = current.analysis
    loaded = (content, analysis)
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
        content, analysis = applied
    if not ops:
        return AppliedOps(refused=refused, saved=None)
    if stores_item_ids(*loaded):
        content, analysis = settle_item_ids(loaded, (content, analysis))
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
