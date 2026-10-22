"""The working copy's operation log as values: one row per ``(item, field)`` a write touched (M1).

ADR 0029 decision 3: every write of a study's working copy is logged, insert-once, in
``workspace_edit_ops``. This module is what a row says, built by code from the write; the table and
its one repository are infrastructure's, and ``apply_edit_ops`` (application) is the one writer.

* A **whole-copy write** (the PUT and the web autosave, a reuse, a server-authored copy, an accept,
  the 18.6.6 migration) logs one row per ``(item, field)`` that differs between the copy it
  replaced and the copy it wrote (:func:`.design_fields.changed_fields`), so the change feed and
  the field-level conflict rule (WCE5) see it as they see an operation. A write whose every change
  is one :mod:`.design_fields` does not count (a list entry re-spaced, an id list alone) still made
  a revision, and logs one row for the copy as a whole (:data:`WHOLE_COPY`), so no write skips the
  log.
* A **vocabulary operation** logs one row per field it touched (``edit_ops.touches``), the
  operation itself as the row's ``op``.

Rows of one write share a ``batch_id``. Who wrote it is a person, or the Lead of a named
researcher; only a revision migrated from 18.6.6, whose author it did not record, names nobody.
Keys and fields come from stored content, so one longer than its column is kept as a prefix and
a digest of the whole: deterministic, so two writes of the same field still compare equal.
Pure: no I/O.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .design_fields import Touch, changed_fields
from .design_items import Documents, ItemKey
from .edit_ops import new_op_id

__all__ = [
    "FIELD_MAX",
    "ITEM_KEY_MAX",
    "WHOLE_COPY",
    "ActorKind",
    "EditLogRow",
    "OpSource",
    "WriteBy",
    "op_rows",
    "whole_copy_op",
    "whole_copy_rows",
    "whole_copy_touches",
]

#: The columns' widths (``workspace_edit_ops.item_key``, ``.field``).
ITEM_KEY_MAX: Final = 160
FIELD_MAX: Final = 48

#: The row a whole-copy write logs when nothing :mod:`.design_fields` counts changed.
WHOLE_COPY: Final[Touch] = (ItemKey("content", "copy"), "value")


class ActorKind(StrEnum):
    """Who made a write: a person, or the Lead of the researcher it names."""

    PERSON = "person"
    LEAD = "lead"


class OpSource(StrEnum):
    """Where a write came from (ADR 0029 decision 3, and the whole-copy writers WCE2 records)."""

    UI = "ui"
    LEAD_TURN = "lead_turn"
    PROPOSAL_ACCEPT = "proposal_accept"
    DESIGN_RESEARCH_ACCEPT = "design_research_accept"
    UNDO = "undo"
    REUSE = "reuse"
    AUTHORED = "authored"
    MIGRATION = "migration"


@dataclass(frozen=True, slots=True)
class WriteBy:
    """Who made one write and why, shared by every row it logs.

    ``actor_user_id`` is the person, or the researcher whose Lead made it. It is ``None`` only
    for a revision migrated from 18.6.6, whose author the unit did not record: a person's write
    (18.6.6 had no Lead) with the source ``migration``. Any other write without one is refused
    here, so a person's write is never logged as nobody's. Which code may name that source is
    held by ``make layer_check`` (the 18.6.6 migration alone), so the label is not a caller's to
    pick.
    """

    actor_kind: ActorKind
    actor_user_id: str | None
    source: OpSource
    source_ref: str | None = None

    def __post_init__(self) -> None:
        migrated = self.source is OpSource.MIGRATION and self.actor_kind is ActorKind.PERSON
        if self.actor_user_id is None and not migrated:
            raise ValueError("only a revision migrated from 18.6.6 is logged without its author")
        if self.actor_user_id is not None and not self.actor_user_id:
            raise ValueError("an author is a user id, never empty")


@dataclass(frozen=True, slots=True)
class EditLogRow:
    """One ``workspace_edit_ops`` row, before it is stored."""

    op_id: str
    batch_id: str
    base_revision: int | None
    result_revision: int
    by: WriteBy
    item_key: str
    field: str | None
    op: dict[str, Any]
    #: The operation that undoes this one, computed by code (WCE9); none yet.
    inverse: dict[str, Any] | None = None


def _bounded(text: str, limit: int) -> str:
    """``text``, or, when longer than ``limit``, its prefix and a digest of the whole."""
    if len(text) <= limit:
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{text[: limit - len(digest) - 1]}#{digest}"


def whole_copy_op(reason: str) -> dict[str, Any]:
    """The ``op`` a whole-copy write logs: what kind of write it was, never the copy (the revision
    holds that)."""
    return {"op": "whole_copy", "reason": reason}


def whole_copy_touches(
    before: Documents | Mapping[str, Any] | None, after: Documents | Mapping[str, Any]
) -> frozenset[Touch]:
    """Every ``(item, field)`` a whole-copy write changed; :data:`WHOLE_COPY` alone when it changed
    none :mod:`.design_fields` counts. ``before`` ``None``: the study had no copy, so every field
    the new one holds is written."""
    base = Documents(content={}) if before is None else before
    touched = changed_fields(base, after)
    return touched or frozenset({WHOLE_COPY})


def op_rows(
    touched: Iterable[Touch],
    *,
    op: Mapping[str, Any],
    by: WriteBy,
    batch_id: str,
    base_revision: int | None,
    result_revision: int,
) -> tuple[EditLogRow, ...]:
    """One row per ``(item, field)`` in ``touched``, in key order, each with a fresh id."""
    if result_revision < 1:
        raise ValueError("a write results in a working revision")
    return tuple(
        EditLogRow(
            op_id=new_op_id(),
            batch_id=batch_id,
            base_revision=base_revision,
            result_revision=result_revision,
            by=by,
            item_key=_bounded(str(key), ITEM_KEY_MAX),
            field=_bounded(field, FIELD_MAX),
            op=dict(op),
        )
        for key, field in sorted(touched, key=lambda t: (str(t[0]), t[1]))
    )


def whole_copy_rows(
    before: Documents | Mapping[str, Any] | None,
    after: Documents | Mapping[str, Any],
    *,
    reason: str,
    by: WriteBy,
    batch_id: str,
    base_revision: int | None,
    result_revision: int,
) -> tuple[EditLogRow, ...]:
    """The rows a whole-copy write logs: one per field it changed, at least one."""
    return op_rows(
        whole_copy_touches(before, after),
        op=whole_copy_op(reason),
        by=by,
        batch_id=batch_id,
        base_revision=base_revision,
        result_revision=result_revision,
    )
