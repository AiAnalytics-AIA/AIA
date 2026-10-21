"""A study's selected client knowledge, frozen into an immutable context (lifecycle K4).

"Use in this study" is a person's decision about exact revisions. They choose one item at its
current revision for one study (a **selection**), and the choice stays at that revision until
they choose again. Knowledge accepted later does not enter a study on its own.

What consumes a study's knowledge reads it **frozen** (:class:`FrozenKnowledgeContext`): every
selected item at the revision chosen, with its words, author, evidence and SHA-256. Each entry
carries the state it was in when frozen:

* ``CURRENT``: the chosen revision is the item's current one;
* ``SUPERSEDED``: the item has moved on since it was chosen. The context still holds the chosen
  revision's text, never the newer one, and says so, so a person can choose again.

An item that is no longer active is **omitted** and named with its reason (``RETIRED``), and so
is a selection that cannot be read in the study's scope (``UNAVAILABLE``); none is dropped
silently. The context's identity is :func:`context_sha256` over what a consumer reads -- each
entry's item, revision and the revision's SHA-256 -- so a consumer that records it names
exactly the text it read, and the identity does not move when only an item's state since does
(a newer revision elsewhere is not text this context holds).

Formal eligibility for a computational use stays with the population and evidence rules. A
selection is a person's statement that the text is context for this study, nothing more.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .knowledge import KnowledgeAuthor, KnowledgeKind, RevisionEvidence

__all__ = [
    "CONTEXT_VERSION",
    "ContextEntryState",
    "FrozenKnowledgeContext",
    "FrozenKnowledgeEntry",
    "KnowledgeSelection",
    "OmittedKnowledge",
    "OmittedReason",
    "StaleKnowledgeSelection",
    "context_sha256",
]

#: The frozen context's shape; part of its hash, so a change of shape is a new identity.
CONTEXT_VERSION = "knowledge-context-v1"


class StaleKnowledgeSelection(Exception):
    """A selection named a revision that is not the item's current one.

    The person chose from a screen that no longer shows the item as it stands. Nothing is
    selected; they read the current revision and choose it.
    """

    reason = "stale_selection"

    def __init__(self, *, item_id: str, revision: int, current_revision: int) -> None:
        super().__init__(
            f"knowledge item {item_id} is at revision {current_revision}; "
            f"revision {revision} was chosen"
        )
        self.item_id = item_id
        self.revision = revision
        self.current_revision = current_revision


class KnowledgeSelection(BaseModel):
    """One item chosen for one study at one revision, and who chose it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    study_id: str
    item_id: str
    revision: int
    selected_by: str
    selected_at: datetime | None = None


class ContextEntryState(StrEnum):
    """Where a selected revision stood when the context was frozen."""

    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"


class OmittedReason(StrEnum):
    """Why a selected item is not in the frozen context."""

    RETIRED = "RETIRED"
    #: The selection's item or revision cannot be read in the study's scope.
    UNAVAILABLE = "UNAVAILABLE"


class FrozenKnowledgeEntry(BaseModel):
    """One selected item at the revision chosen, as a consumer reads it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    revision: int
    kind: KnowledgeKind
    title: str
    summary: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    author: KnowledgeAuthor
    evidence: RevisionEvidence | None = None
    #: ``revision_sha256`` of the chosen revision's title, summary and content.
    sha256: str
    state: ContextEntryState
    #: The item's revision when frozen: equal to ``revision`` unless ``SUPERSEDED``.
    current_revision: int


class OmittedKnowledge(BaseModel):
    """A selected item left out of the frozen context, named with its reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    revision: int
    reason: OmittedReason


class FrozenKnowledgeContext(BaseModel):
    """A study's selected client knowledge, immutable: what a consumer read, exactly."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = CONTEXT_VERSION
    study_id: str
    client_id: str
    #: Sorted by item id.
    entries: tuple[FrozenKnowledgeEntry, ...] = ()
    omitted: tuple[OmittedKnowledge, ...] = ()
    #: :func:`context_sha256` of what is read: the version, study, client and each entry's
    #: item, revision and SHA-256. State and omissions are reported beside it, not hashed.
    sha256: str

    @classmethod
    def freeze(
        cls,
        *,
        study_id: str,
        client_id: str,
        entries: Sequence[FrozenKnowledgeEntry],
        omitted: Sequence[OmittedKnowledge],
    ) -> FrozenKnowledgeContext:
        """The context, ordered by item id, with its hash."""
        ordered = tuple(sorted(entries, key=lambda e: e.item_id))
        left_out = tuple(sorted(omitted, key=lambda o: o.item_id))
        return cls(
            study_id=study_id,
            client_id=client_id,
            entries=ordered,
            omitted=left_out,
            sha256=context_sha256(study_id=study_id, client_id=client_id, entries=ordered),
        )

    def verify(self) -> bool:
        """Whether the hash still names what the context holds (a stored one, read back)."""
        return self.sha256 == context_sha256(
            study_id=self.study_id,
            client_id=self.client_id,
            entries=self.entries,
            version=self.version,
        )


def context_sha256(
    *,
    study_id: str,
    client_id: str,
    entries: Sequence[FrozenKnowledgeEntry],
    version: str = CONTEXT_VERSION,
) -> str:
    """The SHA-256 of what a frozen context gives its reader: its version, study, client and
    each entry's item id, revision and revision SHA-256, in item order, canonical JSON (sorted
    keys, no spaces, UTF-8). An entry's words are covered through its revision's SHA-256; its
    state (``SUPERSEDED``) and the omissions are not what is read, so they are not hashed."""
    payload = json.dumps(
        {
            "version": version,
            "study_id": study_id,
            "client_id": client_id,
            "entries": [
                {"item_id": e.item_id, "revision": e.revision, "sha256": e.sha256}
                for e in sorted(entries, key=lambda e: e.item_id)
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
