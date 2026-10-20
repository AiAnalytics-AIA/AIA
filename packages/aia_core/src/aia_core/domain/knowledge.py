"""Client Knowledge: what AIA knows about one client, and how it may change.

ADR 0015 decision 7. Three layers, kept apart in the model, the interface and
retrieval:

* **AIA shared intelligence** -- platform data any study may use where policy
  permits: the population registry, shared methodological definitions, general
  societal evidence. No client columns (``population/``).
* **Client Knowledge** -- private to one client: its sources and documents, its
  datasets, approved facts and findings, terminology and entities, dimensions,
  audiences and artifacts. This module.
* **Study context** -- what one study consumes: the shared layer plus the
  approved knowledge of its own client, resolved from the study's scope.

What a **person** writes in the client workspace is knowledge at once (ADR 0019
decision 3): it is recorded as an already-approved proposal, so the revision keeps
its lineage and its author. A study never mutates client knowledge. It **proposes**;
a person holding the approval permission decides -- the proposer too, unless
self-approval is turned off at that scope, exactly as for gates -- and an approval
appends an item revision and advances the client's knowledge revision. Where
self-approval is off, a person's own addition is held as a proposal as well.
Revisions are append-only and carry their provenance.

**Folders and labels** organize a client's items for the people who work with
them (client-workspace plan, D2-D4). They are per client; an item sits in at
most one folder and carries any number of labels. They are organization, not
knowledge: no model sees them, and moving or labelling an item writes no
revision and leaves the client's knowledge revision where it was.

A **file** reaches knowledge by reference (client-workspace C7a). A SOURCE, DOCUMENT or
DATASET item may name one of its client's sources as ``content["source_id"]``; the
original and its reading stay the client's source (lifecycle K2), so the item says what
the file is and the source keeps what it holds. :func:`source_ref` is the shape's rule;
that the source is the item's own client's is the caller's check, against the source
store.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Final
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "KNOWLEDGE_SECTIONS",
    "ORGANIZER_NAME_MAX",
    "PROVENANCE_DATASETS",
    "SOURCE_BACKED_KINDS",
    "SOURCE_REF",
    "STALE_AFTER",
    "KnowledgeFolder",
    "KnowledgeHealth",
    "KnowledgeItem",
    "KnowledgeKind",
    "KnowledgeLabel",
    "KnowledgeLayer",
    "KnowledgeProposal",
    "KnowledgeRevision",
    "KnowledgeSummary",
    "LabelColour",
    "OrganizerNameTaken",
    "ProposalDraft",
    "ProposalOrigin",
    "ProposalStatus",
    "StaleKnowledgeProposal",
    "new_knowledge_folder_id",
    "new_knowledge_item_id",
    "new_knowledge_label_id",
    "new_knowledge_proposal_id",
    "organizer_key",
    "organizer_name",
    "recorded_datasets",
    "source_ref",
]


def new_knowledge_item_id() -> str:
    """``KNW-`` followed by 14 hex characters, like every AIA id."""
    return f"KNW-{uuid4().hex[:14]}"


def new_knowledge_proposal_id() -> str:
    """``KNP-`` followed by 14 hex characters."""
    return f"KNP-{uuid4().hex[:14]}"


def new_knowledge_folder_id() -> str:
    """``KNF-`` followed by 14 hex characters."""
    return f"KNF-{uuid4().hex[:14]}"


def new_knowledge_label_id() -> str:
    """``KNL-`` followed by 14 hex characters."""
    return f"KNL-{uuid4().hex[:14]}"


ORGANIZER_NAME_MAX: Final = 80


def organizer_name(name: str) -> str:
    """A folder's or label's name as stored: trimmed, inner whitespace collapsed.

    Raises ``ValueError`` when nothing is left or it is longer than
    ``ORGANIZER_NAME_MAX`` characters.
    """
    cleaned = " ".join(name.split())
    if not cleaned:
        raise ValueError("a name cannot be empty")
    if len(cleaned) > ORGANIZER_NAME_MAX:
        raise ValueError(f"a name has at most {ORGANIZER_NAME_MAX} characters")
    return cleaned


def organizer_key(name: str) -> str:
    """What makes two names the same within one client: case and spacing do not count.

    "Trh a konkurence" and " trh  A KONKURENCE" are one folder. Accents do count:
    in Czech they change the word.
    """
    return organizer_name(name).casefold()


class OrganizerNameTaken(ValueError):
    """The client already has a folder (or a label) by that name."""


class StaleKnowledgeProposal(Exception):
    """A revision was written from an item revision that is no longer the current one.

    Approving it would replace the newer text with the older one's edit (F-K1). The
    reviewer may read the current revision and accept against it by naming it; nothing
    else lets a stale edit through. ``base_revision`` is ``None`` for a proposal filed
    before its base was recorded: unknown, so it is treated as stale, never as current.
    """

    reason = "stale_proposal"

    def __init__(self, *, item_id: str, base_revision: int | None, current_revision: int) -> None:
        super().__init__(
            f"knowledge item {item_id} is at revision {current_revision}; "
            f"this edit was written from revision {base_revision}"
        )
        self.item_id = item_id
        self.base_revision = base_revision
        self.current_revision = current_revision


class LabelColour(StrEnum):
    """The closed set of label colours: the design system's wayfinding hues.

    Never a status colour, so a label never reads as "failed" or "waiting".
    """

    BLUE = "BLUE"
    TEAL = "TEAL"
    GREEN = "GREEN"
    ORANGE = "ORANGE"
    VIOLET = "VIOLET"
    SLATE = "SLATE"


class KnowledgeLayer(StrEnum):
    """Where a piece of knowledge lives. Inheritance runs one way: shared → client → study."""

    SHARED = "SHARED"
    CLIENT = "CLIENT"
    STUDY = "STUDY"


class KnowledgeKind(StrEnum):
    """The kinds of client knowledge. Matches ``tables.KNOWLEDGE_KINDS``."""

    SOURCE = "SOURCE"
    DOCUMENT = "DOCUMENT"
    DATASET = "DATASET"
    FACT = "FACT"
    FINDING = "FINDING"
    TERM = "TERM"
    ENTITY = "ENTITY"
    DIMENSION = "DIMENSION"
    AUDIENCE = "AUDIENCE"
    ARTIFACT = "ARTIFACT"


# How the client workspace groups the kinds (Znalosti · Data).
KNOWLEDGE_SECTIONS: Final[dict[str, tuple[KnowledgeKind, ...]]] = {
    "sources": (KnowledgeKind.SOURCE, KnowledgeKind.DOCUMENT),
    "knowledge": (
        KnowledgeKind.FACT,
        KnowledgeKind.FINDING,
        KnowledgeKind.TERM,
        KnowledgeKind.ENTITY,
    ),
    "dimensions": (KnowledgeKind.DIMENSION,),
    "audiences": (KnowledgeKind.AUDIENCE,),
    "data": (KnowledgeKind.DATASET, KnowledgeKind.ARTIFACT),
}


#: The key under which an item's content names its client's source (C7a).
SOURCE_REF: Final = "source_id"
#: The kinds that may carry a source: the material itself, never a fact drawn from it.
SOURCE_BACKED_KINDS: Final = frozenset(
    {KnowledgeKind.SOURCE, KnowledgeKind.DOCUMENT, KnowledgeKind.DATASET}
)
# A source's id as the source store mints it (``client_sources.new_source_id``).
_SOURCE_ID: Final = re.compile(r"^SRC-[0-9a-f]{16}$")


#: The key under which a revision's provenance records the datasets its material derives
#: from (CR-4): the item's licence lineage. Written by code only (the develop seed today);
#: no route takes provenance from a request. Read by :func:`recorded_datasets`.
PROVENANCE_DATASETS: Final = "datasets"


def recorded_datasets(provenance: dict[str, Any]) -> tuple[str, ...] | None:
    """The datasets a revision's provenance records, sorted; ``None`` when it records none.

    ``None`` is "nobody recorded which datasets this came from", never "derived from no
    dataset": an empty list, a value that is not a list of nonempty strings, or no key at all
    is unrecorded, so the licence gate goes on refusing it by name (never a guess, §8).
    """
    value = provenance.get(PROVENANCE_DATASETS)
    if not isinstance(value, list) or not value:
        return None
    if any(not isinstance(d, str) or not d.strip() for d in value):
        return None
    return tuple(sorted(set(value)))


def source_ref(kind: KnowledgeKind, content: dict[str, Any]) -> str | None:
    """The source an item's content names, or ``None``; ``ValueError`` for a wrong shape.

    Only a SOURCE, DOCUMENT or DATASET item names one, and only as a source's id.
    """
    if SOURCE_REF not in content:
        return None
    ref = content[SOURCE_REF]
    if kind not in SOURCE_BACKED_KINDS:
        raise ValueError(f"a {kind.value} item does not carry a source")
    if not isinstance(ref, str) or not _SOURCE_ID.fullmatch(ref):
        raise ValueError("source_id is not a source's id")
    return ref


class ProposalStatus(StrEnum):
    """A proposal waits for a person; nothing changes until it is approved."""

    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProposalOrigin(StrEnum):
    """Where a proposal came from: a study's finding, or the client workspace itself."""

    STUDY = "STUDY"
    CLIENT = "CLIENT"


class KnowledgeItem(BaseModel):
    """One approved piece of a client's knowledge, at its current revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    client_id: str
    kind: KnowledgeKind
    title: str
    summary: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    revision: int
    modified_at: datetime | None = None
    #: Organization, not knowledge: where people filed it. Changing these writes no revision.
    folder_id: str | None = None
    label_ids: tuple[str, ...] = ()
    #: The datasets its current revision's provenance records (:func:`recorded_datasets`);
    #: ``None``: unrecorded. Read only for what a study inherits (``for_study``).
    datasets: tuple[str, ...] | None = None


class KnowledgeFolder(BaseModel):
    """A folder of one client's knowledge. An item sits in at most one."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    folder_id: str
    client_id: str
    name: str
    #: The client's active items in it.
    item_count: int = 0


class KnowledgeLabel(BaseModel):
    """A label of one client's knowledge. An item carries any number."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label_id: str
    client_id: str
    name: str
    colour: LabelColour
    #: The client's active items carrying it.
    item_count: int = 0


class KnowledgeRevision(BaseModel):
    """An approved revision: append-only, with where it came from and who approved it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    revision: int
    context_revision: int
    title: str
    summary: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    proposal_id: str | None = None
    approved_by: str
    approved_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProposalDraft:
    """One proposal a run of the client's own work offers (lifecycle K2d2), before it is
    filed: what it is, and where it came from. Filed as a proposal, never as knowledge."""

    kind: KnowledgeKind
    title: str
    summary: str
    content: dict[str, Any]
    provenance: dict[str, Any]


class KnowledgeProposal(BaseModel):
    """A proposed addition or change, and its decision once made."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str
    client_id: str
    origin: ProposalOrigin
    study_id: str | None = None
    item_id: str | None = None
    kind: KnowledgeKind
    title: str
    summary: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    status: ProposalStatus
    proposed_by: str
    proposed_at: datetime | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_note: str = ""
    revision: int | None = None
    #: The item revision a revising proposal was written from; ``None`` for a new item, or
    #: for a revision filed before the base was recorded (unknown, never current).
    base_revision: int | None = None


#: How long an item may go unchanged before Přehled asks a person to look at it again.
STALE_AFTER: Final = timedelta(days=365)


class KnowledgeHealth(BaseModel):
    """What in a client's knowledge wants a person's attention (Přehled).

    ``stale``: active items unchanged for longer than ``STALE_AFTER``.
    ``unfiled``: active items in no folder.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    stale: int
    unfiled: int


class KnowledgeSummary(BaseModel):
    """The state of a client's knowledge at a glance (Přehled)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    context_revision: int
    items_by_kind: dict[KnowledgeKind, int]
    pending_proposals: int
    last_approved_at: datetime | None = None
