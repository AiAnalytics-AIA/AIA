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

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Final
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "KNOWLEDGE_SECTIONS",
    "ORGANIZER_NAME_MAX",
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
    "ProposalOrigin",
    "ProposalStatus",
    "new_knowledge_folder_id",
    "new_knowledge_item_id",
    "new_knowledge_label_id",
    "new_knowledge_proposal_id",
    "organizer_key",
    "organizer_name",
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
