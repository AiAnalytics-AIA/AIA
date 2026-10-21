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

**Typed revisions and decisions** (lifecycle K3). Every proposal says who wrote it
(:class:`KnowledgeAuthor`: a person, a study, the AI) and, once decided, what was decided
(:class:`KnowledgeDecision`): a person's own write in effect at once, an accept at the
revision the edit was written from, an accept over a newer revision the reviewer named, or a
rejection. :func:`reviewed_decision` is the one rule an approval passes under the item's
lock (F-K1): the reviewer's view and the edit's base are both checked against the item's
current revision. A revision reads back typed: its author, its decision, the base and
reviewed revisions, the evidence an AI proposal rested on (:class:`RevisionEvidence`) and the
SHA-256 of what it says (:func:`revision_sha256`). A record from before these were kept reads
``UNKNOWN`` or ``None``, never a guess.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Final
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "KNOWLEDGE_SECTIONS",
    "ORGANIZER_NAME_MAX",
    "SOURCE_BACKED_KINDS",
    "SOURCE_REF",
    "STALE_AFTER",
    "KnowledgeAuthor",
    "KnowledgeDecision",
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
    "NoRevisionToReview",
    "OrganizerNameTaken",
    "ProposalDraft",
    "ProposalOrigin",
    "ProposalStatus",
    "RevisionEvidence",
    "StaleKnowledgeProposal",
    "author_of",
    "evidence_of",
    "new_knowledge_folder_id",
    "new_knowledge_item_id",
    "new_knowledge_label_id",
    "new_knowledge_proposal_id",
    "organizer_key",
    "organizer_name",
    "reviewed_decision",
    "revision_sha256",
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

    def __init__(
        self,
        *,
        item_id: str,
        base_revision: int | None,
        current_revision: int,
        reviewed_revision: int | None = None,
    ) -> None:
        super().__init__(
            f"knowledge item {item_id} is at revision {current_revision}; "
            f"this edit was written from revision {base_revision}"
            + (
                f" and reviewed at revision {reviewed_revision}"
                if reviewed_revision is not None
                else ""
            )
        )
        self.item_id = item_id
        self.base_revision = base_revision
        self.current_revision = current_revision
        #: The revision the reviewer said they read, when they named one (K3).
        self.reviewed_revision = reviewed_revision


class NoRevisionToReview(ValueError):
    """A reviewed revision was named for a proposal that adds a new item: there is none."""


class KnowledgeAuthor(StrEnum):
    """Who wrote a proposal (lifecycle K3). ``UNKNOWN``: a record that never said."""

    PERSON = "PERSON"
    STUDY = "STUDY"
    AI = "AI"
    UNKNOWN = "UNKNOWN"


class KnowledgeDecision(StrEnum):
    """What a person decided on a proposal (lifecycle K3).

    ``AUTHORED``: a person's own write, in effect at once (ADR 0019 decision 3).
    ``ACCEPTED``: accepted at the revision it was written from (or a new item accepted).
    ``ACCEPTED_OVER``: an edit accepted over a newer revision the reviewer named (F-K1).
    ``REJECTED``: nothing changed.
    """

    AUTHORED = "AUTHORED"
    ACCEPTED = "ACCEPTED"
    ACCEPTED_OVER = "ACCEPTED_OVER"
    REJECTED = "REJECTED"


def reviewed_decision(
    *,
    item_id: str | None,
    base_revision: int | None,
    reviewed_revision: int | None,
    current_revision: int | None,
) -> KnowledgeDecision:
    """The decision an approval records, or the refusal it meets (lifecycle K3, F-K1).

    A new item (``item_id`` ``None``) has no revision to review: naming one raises
    :class:`NoRevisionToReview`. For an edit of an item now at ``current_revision``:

    * a named ``reviewed_revision`` that is not the current one is stale -- the reviewer read
      an older item than the one the accept would change, whatever the edit's base;
    * an edit written from the current revision is ``ACCEPTED``;
    * an edit written from another revision, or from an unknown one (``None``, never
      current), is ``ACCEPTED_OVER`` when the reviewer named the current revision, and
      stale otherwise.

    The caller holds the item's lock across this check and the write.
    """
    if item_id is None:
        if reviewed_revision is not None:
            raise NoRevisionToReview("a new item has no revision to review")
        return KnowledgeDecision.ACCEPTED
    if current_revision is None:
        raise ValueError("an edit is decided against the item's current revision")
    if reviewed_revision is not None and reviewed_revision != current_revision:
        raise StaleKnowledgeProposal(
            item_id=item_id,
            base_revision=base_revision,
            current_revision=current_revision,
            reviewed_revision=reviewed_revision,
        )
    if base_revision == current_revision:
        return KnowledgeDecision.ACCEPTED
    if reviewed_revision == current_revision:
        return KnowledgeDecision.ACCEPTED_OVER
    raise StaleKnowledgeProposal(
        item_id=item_id, base_revision=base_revision, current_revision=current_revision
    )


def author_of(stored: str | None, provenance: Mapping[str, Any]) -> KnowledgeAuthor:
    """A proposal's author: as stored, else what its provenance says outright, else unknown.

    A record filed before the author was stored names it only by the markers the writers
    kept: ``authored`` ``"ai"`` or ``"person"``, or the ``study_id`` a study's proposal
    carries. Anything else is ``UNKNOWN`` -- never presumed a person's.
    """
    if stored is not None:
        return KnowledgeAuthor(stored)
    authored = provenance.get("authored")
    if authored == "ai":
        return KnowledgeAuthor.AI
    if authored == "person":
        return KnowledgeAuthor.PERSON
    study_id = provenance.get("study_id")
    if isinstance(study_id, str) and study_id:
        return KnowledgeAuthor.STUDY
    return KnowledgeAuthor.UNKNOWN


class RevisionEvidence(BaseModel):
    """What an AI proposal from a client's document rested on (lifecycle K2d, K3): the
    document, the words, checked by code to be in it, and where they stand."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    quote: str
    #: Where the quote stands in the original, as the reader placed it (page, line ...).
    locator: dict[str, Any]
    source_sha256: str | None = None
    reading_sha256: str | None = None
    segment: int | None = None
    run_id: str | None = None


def _text_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def evidence_of(
    author: KnowledgeAuthor, provenance: Mapping[str, Any], content: Mapping[str, Any]
) -> RevisionEvidence | None:
    """The evidence an AI-written record rests on, or ``None``.

    Only an ``AI`` record whose provenance names its source and whose content holds the quote
    and locator the extraction step writes has evidence; any other shape has none, rather
    than a part of one.
    """
    if author is not KnowledgeAuthor.AI:
        return None
    source_id = _text_or_none(provenance.get("source_id"))
    quote, locator = content.get("quote"), content.get("locator")
    if source_id is None or not isinstance(quote, str) or not isinstance(locator, dict):
        return None
    segment = provenance.get("segment")
    return RevisionEvidence(
        source_id=source_id,
        quote=quote,
        locator=dict(locator),
        source_sha256=_text_or_none(provenance.get("source_sha256")),
        reading_sha256=_text_or_none(provenance.get("reading_sha256")),
        segment=segment if isinstance(segment, int) and not isinstance(segment, bool) else None,
        run_id=_text_or_none(provenance.get("run_id")),
    )


def revision_sha256(title: str, summary: str, content: Mapping[str, Any]) -> str:
    """The SHA-256 of what a revision says: its title, summary and content, canonical JSON.

    Keys sorted, no insignificant whitespace, UTF-8 as written. The same words give the same
    hash on every store, so a frozen context (K4) can name the exact text it read.
    """
    payload = json.dumps(
        {"title": title, "summary": summary, "content": content},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    #: Typed (lifecycle K3): who wrote it, what was decided, the revision it was written
    #: from and the one the reviewer named, the evidence an AI proposal rested on, and the
    #: SHA-256 of its title, summary and content. ``UNKNOWN`` / ``None`` where never recorded.
    author: KnowledgeAuthor = KnowledgeAuthor.UNKNOWN
    decision: KnowledgeDecision | None = None
    base_revision: int | None = None
    reviewed_revision: int | None = None
    evidence: RevisionEvidence | None = None
    sha256: str = ""


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
    #: Typed (lifecycle K3): who wrote it; once decided, what was decided and the item
    #: revision the reviewer named (``None`` when they named none).
    author: KnowledgeAuthor = KnowledgeAuthor.UNKNOWN
    decision: KnowledgeDecision | None = None
    reviewed_revision: int | None = None


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
