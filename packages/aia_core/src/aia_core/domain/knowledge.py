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

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Final
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "KNOWLEDGE_SECTIONS",
    "KnowledgeItem",
    "KnowledgeKind",
    "KnowledgeLayer",
    "KnowledgeProposal",
    "KnowledgeRevision",
    "KnowledgeSummary",
    "ProposalOrigin",
    "ProposalStatus",
    "new_knowledge_item_id",
    "new_knowledge_proposal_id",
]


def new_knowledge_item_id() -> str:
    """``KNW-`` followed by 14 hex characters, like every AIA id."""
    return f"KNW-{uuid4().hex[:14]}"


def new_knowledge_proposal_id() -> str:
    """``KNP-`` followed by 14 hex characters."""
    return f"KNP-{uuid4().hex[:14]}"


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


class KnowledgeSummary(BaseModel):
    """The state of a client's knowledge at a glance (Přehled)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    context_revision: int
    items_by_kind: dict[KnowledgeKind, int]
    pending_proposals: int
    last_approved_at: datetime | None = None
