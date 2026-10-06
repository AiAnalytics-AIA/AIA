"""The shapes Deep Research passes between its phases, and what it publishes.

ADR 0017, ``.planning/plans/deep-research.md``. Every shape is closed (unknown
fields are refused) and frozen: a finding is data produced once and read many
times, and an artifact that a later reader could reinterpret is not provenance.

The rule the shapes carry: **a finding exists only as an evidence item grounded
in a captured source.** A web source is a :class:`SourceSnapshot` -- the bytes a
fetch returned, normalised to text, hashed and stored -- never a URL and never a
model's recollection. A Client Knowledge source is a :class:`KnowledgeSource`,
one approved item at one revision, frozen when the run was enqueued. An
:class:`EvidenceItem` quotes one of them verbatim and says where.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import hashlib
import unicodedata
from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
)

from ..ai_contracts import canonical_json
from ..residency import DataClass

__all__ = [
    "DOCUMENT_LAYOUT_VERSION",
    "HARNESS_VERSION",
    "BriefDigest",
    "Channel",
    "ClientTerm",
    "CoverageCell",
    "DeepResearchRequest",
    "DocumentBookmark",
    "DocumentLayout",
    "DocumentPage",
    "DocumentSheet",
    "EvidenceItem",
    "EvidenceOrigin",
    "EvidenceType",
    "FrozenKnowledge",
    "GridCell",
    "KnowledgeSource",
    "Measure",
    "MeasureBasis",
    "QualityStatus",
    "QuarantineReason",
    "QuarantinedEvidence",
    "QueryDecision",
    "QueryRecord",
    "RecommendedUse",
    "ResearchSubject",
    "ResearchTrack",
    "RetrievalMode",
    "ScreenQuestion",
    "SnapshotLink",
    "SourceKind",
    "SourceSnapshot",
    "StopReason",
    "SubjectKind",
    "TrackStatus",
    "digest",
    "evidence_id",
    "normalise_label",
    "subject_key",
    "track_id",
]

#: The Deep Research harness. Part of every fingerprint: a harness change is a
#: method change, and nothing produced under the old one is reused under the new.
HARNESS_VERSION: Final = "aia-deep-research-harness-1"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def digest(value: Any) -> str:
    """Hex SHA256 of a JSON value's canonical form (sorted keys, no whitespace)."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalise_label(text: str) -> str:
    """The comparison form of a label: NFKC, case-folded, single spaces."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


# --------------------------------------------------------------------------- #
# Subjects and tracks
# --------------------------------------------------------------------------- #


class Channel(StrEnum):
    """Where a track looks. Each has its own access contract (ADR 0017 decision 3)."""

    #: Approved Client Knowledge, frozen at enqueue. No egress, no web tools.
    INTERNAL = "INTERNAL"
    #: AIA-owned search and fetch. Never reads Client Knowledge.
    WEB = "WEB"


class SubjectKind(StrEnum):
    """What a track researches (DR-1: research questions *and* tracked objects)."""

    QUESTION = "QUESTION"
    OBJECT = "OBJECT"
    #: One question about one object; opened only by presets that allow crosses.
    CROSS = "CROSS"


_SUBJECT_PREFIX: Final = {
    SubjectKind.QUESTION: "q",
    SubjectKind.OBJECT: "o",
    SubjectKind.CROSS: "x",
}


def subject_key(kind: SubjectKind, text: str) -> str:
    """A subject's identity: its kind and its normalised text, never its position."""
    return f"{_SUBJECT_PREFIX[kind]}-{digest([kind.value, normalise_label(text)])[:12]}"


class ResearchSubject(_Closed):
    """One research question, tracked object, or question x object cross."""

    key: str = Field(pattern=r"^[qox]-[0-9a-f]{12}$")
    kind: SubjectKind
    text: str = Field(min_length=1, max_length=1500)
    #: Where the subject came from, for provenance ("research_plan.research_questions[0]").
    origin: str = Field(min_length=1, max_length=300)
    question_key: str | None = None
    object_key: str | None = None


def track_id(subject: str, channel: Channel) -> str:
    """A track's stable name: one subject on one channel, the same in every pass."""
    return f"DRT-{channel.value[0]}-{subject}"


class ResearchTrack(_Closed):
    """One subject on one channel, and the fingerprint of everything its result depends on.

    ``fingerprint`` is the reuse key: a later pass whose track has the same
    fingerprint takes the stored result instead of researching again.
    """

    track_id: str
    subject: ResearchSubject
    channel: Channel
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


# --------------------------------------------------------------------------- #
# Frozen inputs
# --------------------------------------------------------------------------- #


class BriefDigest(_Closed):
    """The part of the brief every track's research depends on."""

    title: str = Field(max_length=500)
    goal: str = Field(max_length=4000)
    decision_use: str = Field(max_length=4000)
    briefing: str = Field(max_length=16000)

    def fingerprint(self) -> str:
        return digest(self.model_dump(mode="json"))


class KnowledgeSource(_Closed):
    """One approved Client Knowledge item at one revision, as the run froze it.

    ``text`` is what an internal quote must occur in: the title, the summary and a
    textual ``content.text``, normalised. ``truncated`` says the frozen text stops
    short of the item -- a quote beyond it is not in the source the run holds.
    """

    ref: str = Field(pattern=r"^KNW-[0-9a-f]+@[1-9][0-9]*$")
    item_id: str
    revision: int = Field(ge=1)
    kind: str
    title: str
    text: str
    data_class: DataClass
    #: Datasets the item derives from; empty for none. Unknown lineage is named, never empty.
    lineage: tuple[str, ...]
    truncated: bool
    #: The approver marked an ENTITY/TERM public; only then is its name not a client term.
    public: bool


class FrozenKnowledge(_Closed):
    """The approved, Study-visible knowledge a run holds, bounded, with what it left out."""

    items: tuple[KnowledgeSource, ...]
    omitted_ids: tuple[str, ...]
    retrieval_limit: int = Field(ge=1)

    def fingerprint(self) -> str:
        """Identity of the knowledge as held: which items, at which revisions, with which text."""
        return digest([[k.ref, digest(k.text)] for k in self.items])

    def source(self, ref: str) -> KnowledgeSource | None:
        return next((k for k in self.items if k.ref == ref), None)


class ClientTerm(_Closed):
    """A term whose presence makes material client-identifying (at least Class B)."""

    term: str = Field(min_length=2, max_length=300)
    source: str = Field(min_length=1, max_length=300)


class ScreenQuestion(_Closed):
    """A survey question as the leakage screen reads it: its text and its categories."""

    id: str
    text: str
    kategorie: tuple[str, ...] = ()


class DeepResearchRequest(_Closed):
    """Everything a run is pinned to, frozen at enqueue (plan decision I-8).

    Nothing here is authority: scope comes from the lease the worker holds, and
    the design revision is re-read under that scope. ``fingerprint`` is the
    request's identity, for idempotent enqueueing.
    """

    harness_version: Literal["aia-deep-research-harness-1"]
    design_revision_id: str = Field(min_length=1)
    design_revision: int = Field(ge=1)
    preset: str
    channels: tuple[Channel, ...] = Field(min_length=1)
    brief: BriefDigest
    subjects: tuple[ResearchSubject, ...]
    questionnaire: tuple[ScreenQuestion, ...]
    knowledge: FrozenKnowledge
    client_terms: tuple[ClientTerm, ...]

    @field_validator("channels")
    @classmethod
    def _distinct(cls, value: tuple[Channel, ...]) -> tuple[Channel, ...]:
        if len(set(value)) != len(value):
            raise ValueError("each channel at most once")
        return value

    def fingerprint(self) -> str:
        return digest(self.model_dump(mode="json"))


# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #


class SourceKind(StrEnum):
    WEB_PAGE = "WEB_PAGE"
    CLIENT_KNOWLEDGE = "CLIENT_KNOWLEDGE"


class RetrievalMode(StrEnum):
    """How a web source was obtained. A recorded source is never client evidence."""

    #: Replayed from a recorded exchange (tests, the local composition).
    RECORDED = "RECORDED"
    #: Retrieved over an approved live route.
    LIVE = "LIVE"


class SnapshotLink(_Closed):
    """One link a captured HTML page carries: data for a later ``L<n>`` ref, never followed.

    ``kind`` is ``anchor`` for an ``<a href>`` (``text`` is its anchor text,
    normalised and truncated) or ``alternate`` for a ``<link rel="alternate">``
    (``media_type`` is its declared ``type``, when it has one). ``url`` is absolute,
    without a fragment, and passed ``check_url`` when the page was captured; it is
    checked again, with its resolution, if anything ever opens it.
    """

    kind: Literal["anchor", "alternate"]
    url: str = Field(min_length=1, max_length=2048)
    text: str = Field(default="", max_length=200)
    media_type: str | None = Field(default=None, max_length=100)


#: The layout's version: how a document's text is rendered and where its parts lie.
#: A change to the rendering changes the text, and so every snapshot id it yields.
DOCUMENT_LAYOUT_VERSION: Final = "aia-document-layout-1"


class DocumentPage(_Closed):
    """One PDF page: where its text lies in the snapshot's text, ``[start, end)``."""

    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class DocumentBookmark(_Closed):
    """One entry of a PDF's own outline (its bookmarks), as the file declares it."""

    title: str = Field(max_length=500)
    level: int = Field(ge=0)
    #: The page it points to, when the file says so in a form that can be read.
    page: int | None = Field(default=None, ge=1)


class DocumentSheet(_Closed):
    """One grid -- an XLSX sheet, or a CSV file -- as captured.

    ``cells`` holds every non-empty cell as ``(row, column, start, end)``: its
    1-based row and column in the sheet and where its value lies in the
    snapshot's text, in text order. ``header_row`` is the first row with two or
    more values (the column labels), ``label_column`` the leftmost column with
    values below it (the row labels); ``caption`` the rows above the header,
    ``notes`` the one-value rows below the table's last row of two or more.
    These are rules over the grid as read, never a guess at what a person meant;
    ``None`` where the rule finds nothing.
    """

    name: str = Field(max_length=200)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    header_row: int | None = Field(default=None, ge=1)
    label_column: int | None = Field(default=None, ge=1)
    caption: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    cells: tuple[tuple[int, int, int, int], ...] = ()
    #: Rows or cells past a bound were not read.
    truncated: bool = False


class DocumentLayout(_Closed):
    """Where a captured document's pages or cells lie in its snapshot's text.

    The text itself is the snapshot's ``text`` -- normalised like a page's, so a
    quote grounds in it exactly as in HTML; the layout maps a span of it back to
    a page (PDF) or a cell (XLSX, CSV). Built by ``domain.deep_research.documents``.
    """

    version: Literal["aia-document-layout-1"] = DOCUMENT_LAYOUT_VERSION
    kind: Literal["pdf", "xlsx", "csv"]
    #: Pages in the file (PDF); ``pages`` holds those whose text was kept.
    page_count: int | None = Field(default=None, ge=0)
    pages: tuple[DocumentPage, ...] = ()
    bookmarks: tuple[DocumentBookmark, ...] = ()
    sheets: tuple[DocumentSheet, ...] = ()


class SourceSnapshot(_Closed):
    """A fetched page as stored: content-addressed, with how it was retrieved.

    ``snapshot_id`` is derived from the normalised text, so the same content is
    one snapshot however often it is fetched, and a changed page is a new one.
    ``instructions_detected`` names every prompt-injection pattern the text
    contains; such a page is kept for provenance and quarantined as a source.

    ``links`` are the outbound and ``alternate`` links of an HTML page. They are
    not part of the content address, and a snapshot without links serialises
    exactly as one stored before the field existed (the key is omitted), so its
    stored JSON, and every hash taken of it, is unchanged.

    ``document`` is the layout of a PDF, XLSX or CSV source (where each page or
    cell lies in ``text``); ``None`` for a page, and then omitted the same way.
    """

    snapshot_id: str = Field(pattern=r"^SNP-[0-9a-f]{24}$")
    url: str
    canonical_url: str
    final_url: str
    redirects: tuple[str, ...]
    title: str
    retrieved_at: datetime
    http_status: int
    content_type: str
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_bytes: int = Field(ge=0)
    text: str
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    truncated: bool
    adapter: str
    request_id: str | None
    retrieval_mode: RetrievalMode
    instructions_detected: tuple[str, ...]
    links: tuple[SnapshotLink, ...] = ()
    document: DocumentLayout | None = None

    @model_serializer(mode="wrap")
    def _omit_absent(self, handler: SerializerFunctionWrapHandler) -> Any:
        data = handler(self)
        if isinstance(data, dict):
            if not self.links:
                data.pop("links", None)
            if self.document is None:
                data.pop("document", None)
        return data


# --------------------------------------------------------------------------- #
# Evidence
# --------------------------------------------------------------------------- #


class EvidenceType(StrEnum):
    """What kind of source a finding comes from. The legacy four, and AIA's own."""

    PRIMARY_SOURCE = "primary_source"
    PEER_REVIEWED = "peer_reviewed"
    OFFICIAL_REPORT = "official_report"
    INDUSTRY_REPORT = "industry_report"
    MEDIA = "media"
    CLIENT_KNOWLEDGE = "client_knowledge"
    OTHER = "other"


class RecommendedUse(StrEnum):
    """The legacy labels (``research_context.py`` ``SAFE_USE`` / ``EXCLUDE_USE``)."""

    CONTEXT_ONLY = "context_only"
    EXCLUDE_TARGET_LEAKAGE = "exclude_target_leakage"


class MeasureBasis(StrEnum):
    """What kind of figure a number is, as its source says (plan § 8.1)."""

    ACTUAL = "actual"
    ESTIMATE = "estimate"
    FORECAST = "forecast"
    PRELIMINARY = "preliminary"


class Measure(_Closed):
    """What one cited number means: the value and everything that makes it that number.

    ``value`` is the number as written; ``scale`` multiplies it (``450`` with scale
    1000 is "450 tis."). ``unit``, ``period``, ``geography``, ``population`` and
    ``denominator`` hold the normalised keys of
    :mod:`aia_core.domain.deep_research.measures` (``%``, ``CZK``, ``Y2025``,
    ``CZ``, ``HOUSEHOLDS``...). ``None`` is *not stated*, never a default: a
    missing population is unknown, not "everyone".
    """

    value: float = Field(allow_inf_nan=False)
    unit: str | None = Field(default=None, max_length=40)
    scale: int = Field(default=1, ge=1)
    period: str | None = Field(default=None, max_length=40)
    geography: str | None = Field(default=None, max_length=40)
    population: str | None = Field(default=None, max_length=60)
    denominator: str | None = Field(default=None, max_length=60)
    measure_name: str | None = Field(default=None, max_length=200)
    basis: MeasureBasis | None = None


def evidence_id(track_fingerprint: str, source_ref: str, quote: str, claim: str) -> str:
    """A finding's identity: its track instance, its source, its quote and its claim."""
    return "EV-" + digest([track_fingerprint, source_ref, quote, claim])[:16]


class EvidenceItem(_Closed):
    """One grounded finding: a claim, the verbatim quote it rests on, and the source.

    ``quote_span`` is the quote's position in the source's normalised text; with the
    snapshot's hash it makes the citation checkable after the page has changed.
    The ``agent_*`` fields are what the investigating model said about its own
    finding. They are recorded and never decide anything: acceptance comes from
    grounding, the declared source tables, the leakage screen and the verifier.
    """

    evidence_id: str = Field(pattern=r"^EV-[0-9a-f]{16}$")
    track_id: str
    subject_key: str
    channel: Channel
    source_kind: SourceKind
    source_ref: str
    source_url: str | None
    source_title: str
    claim: str = Field(min_length=1, max_length=1200)
    quote: str = Field(min_length=1, max_length=800)
    quote_span: tuple[int, int]
    evidence_type: EvidenceType
    source_date: str | None
    geography: str
    population: str
    topics: tuple[str, ...]
    data_class: DataClass
    agent_outcome_overlap: bool
    agent_recommended_use: RecommendedUse
    agent_source_quality: float = Field(ge=0.0, le=1.0)
    #: The measure of each number the claim cites (plan § 8.1); empty until a later
    #: chunk fills it. Empty is left out of the stored form, so an item stored
    #: before measures existed dumps, digests and seals exactly as it did.
    measures: tuple[Measure, ...] = Field(default=(), max_length=40)

    @model_serializer(mode="wrap")
    def _omit_empty_measures(self, handler: SerializerFunctionWrapHandler) -> Any:
        dumped = handler(self)
        if isinstance(dumped, dict) and not self.measures:
            dumped.pop("measures", None)
        return dumped


class QuarantineReason(StrEnum):
    """Why a finding did not become accepted evidence. One reason per quarantine."""

    # The legacy reasons (research_context.py _merge_agents), kept verbatim.
    TARGET_OUTCOME_OVERLAP = "target_outcome_overlap"
    DETERMINISTIC_TARGET_OVERLAP = "deterministic_target_overlap"
    LOW_SOURCE_QUALITY = "low_source_quality"
    NO_INDEPENDENT_CONFIRMATION = "no_independent_confirmation"
    # AIA's own.
    UNGROUNDED_EXCERPT = "ungrounded_excerpt"
    CITATION_OUTSIDE_TRACK = "citation_outside_track"
    NUMBER_NOT_IN_QUOTE = "number_not_in_quote"
    SOURCE_CONTAINS_INSTRUCTIONS = "source_contains_instructions"
    UNSUPPORTED_BY_VERIFIER = "unsupported_by_verifier"
    OVERSTATED_BY_VERIFIER = "overstated_by_verifier"
    UNVERIFIED = "unverified"
    #: The compile-time re-screen against the final questionnaire.
    QUESTIONNAIRE_LEAKAGE = "questionnaire_leakage"
    #: The claim gives a number a unit, scale, period, population, denominator or
    #: place its quote's context in the source does not (``measures.py``).
    MEASURE_NOT_IN_SOURCE = "measure_not_in_source"


class QuarantinedEvidence(_Closed):
    """A finding kept in the log, with the one reason it may not be used."""

    evidence_id: str
    track_id: str
    reason: QuarantineReason
    detail: str = Field(max_length=2000)
    claim: str
    source_ref: str
    evidence: EvidenceItem | None = None


# --------------------------------------------------------------------------- #
# Tracks as run
# --------------------------------------------------------------------------- #


class QueryDecision(StrEnum):
    SENT = "SENT"
    REFUSED = "REFUSED"


class QueryRecord(_Closed):
    """One proposed query and what code decided about it."""

    text: str
    data_class: DataClass
    #: Why the class is what it is ("context:CLASS_C_INTERNAL", "client_term:...").
    class_reasons: tuple[str, ...]
    decision: QueryDecision
    #: Why it was not sent (a ``REFUSED`` decision): the class, the route, the budget.
    refusal: str | None
    call_id: str | None
    hits: int
    #: Why a sent query brought nothing back: the provider's error, or a lost answer.
    failure: str | None = None


class TrackStatus(StrEnum):
    #: The track ran to a stop rule.
    COMPLETED = "COMPLETED"
    #: A gate refused the track before anything was spent (route, class, licence, channel).
    BLOCKED = "BLOCKED"
    #: The track stopped early on something outside the stop rule (an uncertain tool call).
    INCOMPLETE = "INCOMPLETE"


class StopReason(StrEnum):
    """Why a track stopped. Every track records exactly one."""

    DEPTH_TARGET_MET = "depth_target_met"
    SATURATED = "saturated"
    QUERIES_EXHAUSTED = "queries_exhausted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ALL_QUERIES_REFUSED = "all_queries_refused"
    NO_KNOWLEDGE_MATCHED = "no_knowledge_matched"
    SINGLE_PASS = "single_pass"
    WEB_RETRIEVAL_UNAVAILABLE = "web_retrieval_unavailable"
    SEARCH_ROUTE_REFUSED = "search_route_refused"
    MODEL_ROUTE_REFUSED = "model_route_refused"
    CHANNEL_NOT_REQUESTED = "channel_not_requested"
    TOOL_OUTCOME_UNCERTAIN = "tool_outcome_uncertain"
    #: Beyond the preset's track limit: recorded and skipped, never dropped silently.
    TRACK_LIMIT = "track_limit"
    #: The planner skipped the track or gave it no query; nothing was searched for it.
    PLAN_INCOMPLETE = "plan_incomplete"
    #: The request for this track's model would not fit the model's context window.
    CONTEXT_TOO_LARGE = "context_too_large"


class CoverageCell(_Closed):
    """One subject on one channel: whether it was researched, and what came of it."""

    subject_key: str
    channel: Channel
    track_id: str
    status: TrackStatus
    stop_reason: StopReason
    reused: bool
    accepted: int
    quarantined: int


class GridCell(_Closed):
    """One research question x tracked object cell, and the tracks that cover it."""

    question_key: str
    object_key: str
    cross_track: str | None
    question_tracks: tuple[str, ...]
    object_tracks: tuple[str, ...]
    covered: bool


# --------------------------------------------------------------------------- #
# The bundle's status and origin
# --------------------------------------------------------------------------- #


class QualityStatus(StrEnum):
    """What a bundle can be relied on for. None of them is a client deliverable."""

    #: Every planned track ran to a stop rule; accepted evidence is grounded and verified.
    GROUNDED = "GROUNDED"
    #: Some tracks were blocked or incomplete; the bundle says which and why.
    PARTIAL = "PARTIAL"
    #: The tracks ran and nothing survived the gates.
    NO_EVIDENCE = "NO_EVIDENCE"


class EvidenceOrigin(StrEnum):
    """Where a bundle's evidence came from. Recorded evidence is never a finding."""

    RECORDED_FIXTURE = "RECORDED_FIXTURE"
    LIVE_RETRIEVAL = "LIVE_RETRIEVAL"
    CLIENT_KNOWLEDGE = "CLIENT_KNOWLEDGE"
