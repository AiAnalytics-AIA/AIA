"""The agent-directed investigator's track, as code keeps it: refs, actions, turn input.

Plan ``deep-research-web-search.md`` § 6, chunk 9. In the agent-directed mode a web
track is a loop of :class:`~.agents.InvestigatorTurn`\\ s. The model proposes; this
module is what code holds between its proposals and decides about them:

* **Refs** (:class:`TrackRefs`). Every search result is ``R<n>``, every captured
  source ``S<n>``, every link a captured page carries ``L<n>``, numbered in the
  order code met them and never renumbered, so a ref means the same thing in every
  turn of the track and in its transcript. The model never writes a URL: an
  ``open`` names a ref, and :meth:`TrackRefs.url_for` resolves only refs code
  created. A result or link whose page the track already captured is *held*; a
  result whose title and snippet are an exact or near duplicate of an earlier one
  (``filters``: content key, then word-shingle Jaccard) says which.
* **Actions** (:func:`plan_actions`). Before anything reaches the retrieval gate,
  code refuses what it can refuse alone -- an unknown ref, a ref of the wrong kind,
  a part that does not exist, a malformed site or phrase, an operator written into
  the query, a search the track already made, an action beyond the allowance -- and
  serves a ``read`` from the capture itself (nothing is sent). A ``finish`` ends
  the track; anything proposed beside it is skipped. What is left goes to the gate,
  which classifies, authorises, reserves and journals each call.
* **Feedback** (:func:`search_feedback`). Why a search was weak, by code: no hits,
  all held, all low tier (T5 or excluded). An out-of-date-range verdict needs hit
  dates, which no search adapter reports yet; it is not computed rather than
  guessed.
* **Turn input** (:func:`turn_input`). Deterministic JSON: the task, the allowance
  and stop-rule state, results, sources and links (bounded, newest first), the
  newest captured text (untrusted, each part with its ``detect_instructions``
  flags, at most :data:`TURN_TEXT_CHARS` a turn), the grounded findings so far,
  and what code decided about every action of the last turn. The same state gives
  the same bytes, so a retried step finds its answered turns by the request's hash.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any, Final, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from ..residency import DataClass
from .agents import (
    INVESTIGATOR_CONTRACT_VERSION,
    INVESTIGATOR_PROMPT_VERSION,
    MAX_ACTIONS_PER_TURN,
    FinishAction,
    InvestigatorTurn,
    OpenAction,
    ReadAction,
    SearchAction,
)
from .contracts import BriefDigest, ResearchTrack, SourceSnapshot
from .filters import FilterCandidate, exact_duplicate_clusters, near_duplicate_clusters
from .grounding import detect_instructions
from .legacy import canonical_url
from .measures import STATED_MEASURES_VERSION
from .sources import SourceTable, SourceTier, web_tier
from .steps import CallRecord
from .web import FetchRefused, check_url

__all__ = [
    "INVESTIGATOR_VERSION",
    "PART_CHARS",
    "REFUSAL_LIMIT",
    "RESULTS_PER_SEARCH",
    "SHOWN_LINKS",
    "SHOWN_RESULTS",
    "SKIP_EARLIER_ATTEMPT",
    "SKIP_FINISH",
    "TURN_TEXT_CHARS",
    "ActionDecision",
    "ActionOutcome",
    "ActionRecord",
    "Allowance",
    "HitRecord",
    "LinkRef",
    "PlannedAction",
    "Reading",
    "Refusal",
    "ResultRef",
    "SearchFeedback",
    "SourceRef",
    "TrackRefs",
    "TrackState",
    "TurnAnswer",
    "TurnRecord",
    "parse_ref",
    "part_count",
    "part_text",
    "plan_actions",
    "render_search",
    "search_feedback",
    "turn_input",
    "turns_without_new_evidence",
]

#: What an agent-directed track's result depends on beyond the planned mode's
#: rules: the loop, its contract, its prompt, and the stated-measure check.
INVESTIGATOR_VERSION: Final = (
    f"aia-investigator-1/{INVESTIGATOR_CONTRACT_VERSION}/prompt-{INVESTIGATOR_PROMPT_VERSION}"
    f"/{STATED_MEASURES_VERSION}"
)

#: A captured source is read in parts of this many characters (``read`` names one).
PART_CHARS: Final = 6_000
#: The newest captured text one turn is shown, at most; the rest waits for a ``read``.
TURN_TEXT_CHARS: Final = 18_000
#: Results a search asks for: the investigator chooses among them; code fetches none unasked.
RESULTS_PER_SEARCH: Final = 8
#: Results and links shown a turn: the newest. Every ref stays resolvable.
SHOWN_RESULTS: Final = 40
SHOWN_LINKS: Final = 60
#: The same refusal reason this many times ends the track (``STOP_REFUSALS``).
REFUSAL_LIMIT: Final = 3


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- #
# Refs
# --------------------------------------------------------------------------- #

_REF: Final = re.compile(r"^([RSL])([1-9][0-9]{0,5})$")


def parse_ref(text: str) -> tuple[str, int] | None:
    """``("R", 3)`` for ``"R3"``; None for anything else. Case and spaces are kept strict."""
    match = _REF.match(text)
    return (match[1], int(match[2])) if match else None


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _key(url: str) -> str:
    return canonical_url(url) or url


class ResultRef(_Closed):
    """``R<n>``: one search result, as the provider returned it the first time."""

    ref: str
    url: str
    title: str
    snippet: str
    host: str
    tier: SourceTier
    #: The track's search (1-based, in order) that first returned it.
    search: int = Field(ge=1)
    rank: int = Field(ge=0)


class SourceRef(_Closed):
    """``S<n>``: one source the track captured, and where its snapshot is stored."""

    ref: str
    snapshot_id: str
    artifact_id: str
    url: str
    title: str
    host: str
    tier: SourceTier
    published: date | None
    parts: int = Field(ge=1)
    instructions_detected: tuple[str, ...]


class LinkRef(_Closed):
    """``L<n>``: one link a captured page carries; never followed unless opened."""

    ref: str
    url: str
    text: str
    host: str
    tier: SourceTier
    kind: Literal["anchor", "alternate"]
    #: The ``S<n>`` whose page carries it (the first, when several do).
    source: str


class TrackRefs:
    """Every ref of one track, in the order code met each thing. Never renumbered."""

    def __init__(self, table: SourceTable) -> None:
        self._table = table
        self.results: list[ResultRef] = []
        self.sources: list[SourceRef] = []
        self.links: list[LinkRef] = []
        self._result_by_url: dict[str, str] = {}
        self._source_by_snapshot: dict[str, str] = {}
        self._source_by_url: dict[str, str] = {}
        self._link_by_url: dict[str, str] = {}

    # -- adding ----------------------------------------------------------------

    def add_hits(self, hits: Sequence[HitRecord], *, search: int) -> tuple[str, ...]:
        """The ``R<n>`` of each hit, in hit order; a URL already a result keeps its ref."""
        refs: list[str] = []
        for hit in hits:
            key = _key(hit.url)
            ref = self._result_by_url.get(key)
            if ref is None:
                ref = f"R{len(self.results) + 1}"
                self._result_by_url[key] = ref
                self.results.append(
                    ResultRef(
                        ref=ref,
                        url=hit.url,
                        title=hit.title[:500],
                        snippet=hit.snippet[:1000],
                        host=_host(hit.url),
                        tier=web_tier(hit.url, self._table),
                        search=search,
                        rank=hit.rank,
                    )
                )
            if ref not in refs:
                refs.append(ref)
        return tuple(refs)

    def add_source(
        self, snapshot: SourceSnapshot, *, artifact_id: str, published: date | None
    ) -> tuple[str, bool]:
        """The ``S<n>`` of a captured snapshot, and whether it is new to the track.

        A new source brings its links as ``L<n>``, deduplicated by canonical URL
        across the track and never pointing back at the page itself.
        """
        known = self._source_by_snapshot.get(snapshot.snapshot_id)
        if known is not None:
            return known, False
        ref = f"S{len(self.sources) + 1}"
        self._source_by_snapshot[snapshot.snapshot_id] = ref
        for url in (snapshot.url, snapshot.final_url, snapshot.canonical_url):
            self._source_by_url.setdefault(_key(url), ref)
        self.sources.append(
            SourceRef(
                ref=ref,
                snapshot_id=snapshot.snapshot_id,
                artifact_id=artifact_id,
                url=snapshot.final_url,
                title=snapshot.title,
                host=_host(snapshot.final_url),
                tier=web_tier(snapshot.final_url, self._table),
                published=published,
                parts=part_count(snapshot.text),
                instructions_detected=snapshot.instructions_detected,
            )
        )
        own = _key(snapshot.final_url)
        for link in snapshot.links:
            key = _key(link.url)
            if key == own or key in self._link_by_url:
                continue
            lref = f"L{len(self.links) + 1}"
            self._link_by_url[key] = lref
            self.links.append(
                LinkRef(
                    ref=lref,
                    url=link.url,
                    text=link.text or (link.media_type or ""),
                    host=_host(link.url),
                    tier=web_tier(link.url, self._table),
                    kind=link.kind,
                    source=ref,
                )
            )
        return ref, True

    # -- reading ---------------------------------------------------------------

    @staticmethod
    def _index(ref: str, kind: str, table: Sequence[Any]) -> Any | None:
        parsed = parse_ref(ref)
        if parsed is None or parsed[0] != kind or parsed[1] > len(table):
            return None
        return table[parsed[1] - 1]

    def result(self, ref: str) -> ResultRef | None:
        found: ResultRef | None = self._index(ref, "R", self.results)
        return found

    def source(self, ref: str) -> SourceRef | None:
        found: SourceRef | None = self._index(ref, "S", self.sources)
        return found

    def link(self, ref: str) -> LinkRef | None:
        found: LinkRef | None = self._index(ref, "L", self.links)
        return found

    def source_for_snapshot(self, snapshot_id: str) -> str | None:
        return self._source_by_snapshot.get(snapshot_id)

    def url_for(self, ref: str) -> str | None:
        """The URL code stored for an ``R<n>`` or ``L<n>``; None for anything else."""
        result = self.result(ref)
        if result is not None:
            return result.url
        link = self.link(ref)
        return link.url if link is not None else None

    def held(self, url: str) -> str | None:
        """The ``S<n>`` the track captured at ``url``, if it did."""
        return self._source_by_url.get(_key(url))

    def duplicates(self) -> dict[str, str]:
        """Each ``R<n>`` whose title and snippet repeat an earlier result's -> that result.

        Exact duplicates by content key and near duplicates by shingle Jaccard
        (``filters``, default threshold); within a group every later result points
        at the earliest.
        """
        candidates = [FilterCandidate(r.ref, f"{r.title} {r.snippet}") for r in self.results]
        groups = [
            *exact_duplicate_clusters(candidates),
            *near_duplicate_clusters(candidates),
        ]
        number = {r.ref: i for i, r in enumerate(self.results)}
        out: dict[str, str] = {}
        for group in groups:
            members = sorted(group.members, key=number.__getitem__)
            for later in members[1:]:
                out.setdefault(later, members[0])
        return out


# --------------------------------------------------------------------------- #
# Parts of a captured source
# --------------------------------------------------------------------------- #


def part_count(text: str) -> int:
    """How many :data:`PART_CHARS` parts a text has (an empty text has one)."""
    return max(1, math.ceil(len(text) / PART_CHARS))


def part_text(text: str, part: int) -> str:
    return text[(part - 1) * PART_CHARS : part * PART_CHARS]


def _parse_part(part: str, parts: int) -> int | None:
    value = part.strip()
    if not value.isdigit():
        return None
    number = int(value)
    return number if 1 <= number <= parts else None


# --------------------------------------------------------------------------- #
# Actions: what code decided about each
# --------------------------------------------------------------------------- #


class ActionDecision(StrEnum):
    """What code did with one proposed action."""

    #: Left through the retrieval gate; ``outcome`` says how it ended.
    SENT = "sent"
    #: Answered from the run's snapshot cache: nothing sent, nothing charged.
    CACHED = "cached"
    #: A ``read`` of a capture: nothing sent.
    SERVED_LOCALLY = "served_locally"
    #: Not sent: code or the gate refused it (``reason``).
    REFUSED = "refused"
    #: Not attempted: beside a ``finish``, or already sent by an earlier attempt.
    SKIPPED = "skipped"
    #: A ``finish``: the track ends.
    FINISHED = "finished"


class ActionOutcome(StrEnum):
    """How a sent action ended."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    #: It may have been served and no answer is on record: never sent again.
    UNCERTAIN = "uncertain"


class Refusal(StrEnum):
    """Why code refused an action before the gate saw it."""

    UNKNOWN_REF = "unknown_ref"
    NOT_OPENABLE = "not_openable"
    NOT_READABLE = "not_readable"
    UNKNOWN_PART = "unknown_part"
    INVALID_SITE = "invalid_site"
    INVALID_PHRASE = "invalid_phrase"
    SEARCH_OPERATOR = "search_operator"
    DUPLICATE_SEARCH = "duplicate_search"
    ALLOWANCE_SPENT = "allowance_spent"


#: Refusals that say nothing about the agent going wrong: never counted to the limit.
_UNCOUNTED: Final = frozenset({Refusal.ALLOWANCE_SPENT.value})

#: Skips, by reason.
SKIP_FINISH: Final = "finish"
SKIP_EARLIER_ATTEMPT: Final = "sent_by_an_earlier_attempt"


class SearchFeedback(StrEnum):
    """Why a search was weak, computed by code. Empty: it was not weak."""

    NO_HITS = "no_hits"
    #: Every hit was already a result of the track or a page it captured.
    ALL_HELD = "all_held"
    #: Every hit's host is T5 or excluded.
    ALL_LOW_TIER = "all_low_tier"


class HitRecord(_Closed):
    """One search hit as the provider returned it."""

    url: str
    title: str
    snippet: str
    rank: int = Field(ge=0)


class ActionRecord(_Closed):
    """One proposed action and everything code decided and did about it."""

    index: int = Field(ge=0)
    kind: Literal["search", "open", "read", "finish"]
    purpose: str
    ref: str | None = None
    part: str | None = None
    #: A search's text as sent (query, then "phrase", then site:host), and its language.
    query: str | None = None
    lang: str | None = None
    #: An open's URL, resolved from its ref by code.
    url: str | None = None
    decision: ActionDecision
    reason: str | None = None
    outcome: ActionOutcome | None = None
    data_class: DataClass | None = None
    class_reasons: tuple[str, ...] = ()
    call_id: str | None = None
    #: SHA256 of what the gate journaled as sent (never the text itself in the journal).
    request_fingerprint: str | None = None
    hits: tuple[HitRecord, ...] = ()
    #: The ``R<n>`` the hits are, and why the search was weak.
    results: tuple[str, ...] = ()
    feedback: tuple[SearchFeedback, ...] = ()
    #: The ``S<n>`` an open captured or a read was served from.
    source: str | None = None
    snapshot_id: str | None = None
    snapshot_artifact_id: str | None = None

    @property
    def counted_refusal(self) -> str | None:
        """The refusal reason that counts toward :data:`REFUSAL_LIMIT`, if any."""
        if self.decision is ActionDecision.REFUSED and self.reason not in _UNCOUNTED:
            return self.reason
        return None


def search_feedback(
    results: Sequence[str], refs: TrackRefs, *, earlier: frozenset[str]
) -> tuple[SearchFeedback, ...]:
    """Why a search whose hits are ``results`` was weak; ``earlier`` = results before it."""
    if not results:
        return (SearchFeedback.NO_HITS,)
    found: list[SearchFeedback] = []
    rows = [refs.result(r) for r in results]
    if all(r is not None and (r.ref in earlier or refs.held(r.url)) for r in rows):
        found.append(SearchFeedback.ALL_HELD)
    if all(r is not None and r.tier in (SourceTier.T5, SourceTier.EXCLUDED) for r in rows):
        found.append(SearchFeedback.ALL_LOW_TIER)
    return tuple(found)


# --------------------------------------------------------------------------- #
# Searches as written
# --------------------------------------------------------------------------- #

_SITE: Final = re.compile(
    r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?"
)
_OPERATOR: Final = re.compile(
    r"(?:^|[\s\-(])(?:site|filetype|ext|inurl|intitle|intext|cache|related):", re.IGNORECASE
)
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f]")


def render_search(action: SearchAction) -> tuple[str, None] | tuple[None, Refusal]:
    """The text a search sends -- query, "phrase", site:host -- or why it may not.

    Operators are code's to write: a query carrying one (``site:``, ``filetype:``...)
    is refused, as is a site that is not a bare public host or a phrase with a
    double quote. ``filetype:`` is not offered at all (its support is unverified).
    """
    if _CONTROL.search(action.query) or _OPERATOR.search(action.query):
        return None, Refusal.SEARCH_OPERATOR
    parts = [" ".join(action.query.split())]
    if action.phrase is not None:
        if not action.phrase.strip() or '"' in action.phrase or _CONTROL.search(action.phrase):
            return None, Refusal.INVALID_PHRASE
        if _OPERATOR.search(action.phrase):
            return None, Refusal.SEARCH_OPERATOR
        parts.append(f'"{" ".join(action.phrase.split())}"')
    if action.site is not None:
        site = action.site
        if site != site.strip().lower() or not _SITE.fullmatch(site):
            return None, Refusal.INVALID_SITE
        try:
            check_url(f"https://{site}/")
        except FetchRefused:
            return None, Refusal.INVALID_SITE
        parts.append(f"site:{site}")
    return " ".join(p for p in parts if p), None


def _search_key(query: str, lang: str) -> str:
    return f"{lang}:{' '.join(query.casefold().split())}"


# --------------------------------------------------------------------------- #
# The track's state, and what a turn's actions become
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Allowance:
    """A track's allowance: turns, searches sent, pages opened (fetches dispatched)."""

    turns: int
    searches: int
    opens: int


@dataclass(frozen=True, slots=True)
class Reading:
    """One part of a captured source to show the next turn."""

    source: str
    part: int


@dataclass(slots=True)
class TrackState:
    """Everything code holds about one agent-directed track between turns.

    Built only by applying turns in order -- live, or replayed from their records --
    so the same records always give the same state, and the same next request.
    """

    refs: TrackRefs
    texts: dict[str, str] = field(default_factory=dict)
    turns: list[tuple[ActionRecord, ...]] = field(default_factory=list)
    #: What the next turn reads: parts captured or asked for since the last turn.
    reading: list[Reading] = field(default_factory=list)
    shown: set[tuple[str, int]] = field(default_factory=set)
    searched: set[str] = field(default_factory=set)
    #: Newly grounded findings per turn that read fresh text (saturation's input).
    new_by_turn: list[int] = field(default_factory=list)
    finished: bool = False

    def _actions(self) -> list[ActionRecord]:
        return [a for turn in self.turns for a in turn]

    @property
    def searches_used(self) -> int:
        """Searches dispatched (sent, or sent by an earlier attempt and not resent)."""
        return sum(
            1
            for a in self._actions()
            if a.kind == "search"
            and (
                a.decision is ActionDecision.SENT
                or (a.decision is ActionDecision.SKIPPED and a.reason == SKIP_EARLIER_ATTEMPT)
            )
        )

    @property
    def opens_used(self) -> int:
        """Pages fetched (dispatched); a cached open costs nothing and is not counted."""
        return sum(
            1
            for a in self._actions()
            if a.kind == "open"
            and (
                a.decision is ActionDecision.SENT
                or (a.decision is ActionDecision.SKIPPED and a.reason == SKIP_EARLIER_ATTEMPT)
            )
        )

    def refusals(self) -> Counter[str]:
        """Counted refusal reasons over the whole track."""
        return Counter(r for a in self._actions() if (r := a.counted_refusal) is not None)

    def repeated_refusal(self) -> str | None:
        """A refusal reason given :data:`REFUSAL_LIMIT` times, if one was (the first such)."""
        for reason, count in sorted(self.refusals().items()):
            if count >= REFUSAL_LIMIT:
                return reason
        return None

    def capture(
        self, snapshot: SourceSnapshot, *, artifact_id: str, published: date | None
    ) -> tuple[str, bool]:
        """Hold a captured snapshot as ``S<n>``; its first part is read next turn if unseen."""
        ref, new = self.refs.add_source(snapshot, artifact_id=artifact_id, published=published)
        self.texts.setdefault(ref, snapshot.text)
        self._read(ref, 1)
        return ref, new

    def _read(self, source: str, part: int) -> None:
        reading = Reading(source, part)
        if reading not in self.reading:
            self.reading.append(reading)

    def apply(
        self,
        records: Sequence[ActionRecord],
        snapshots: Mapping[str, tuple[SourceSnapshot, date | None]],
    ) -> tuple[ActionRecord, ...]:
        """Take one turn's records into the state, in action order; the records as kept.

        Refs are given here, never by the caller: a sent search's hits become
        ``R<n>`` (with code's feedback on it), a capture becomes ``S<n>``. The same
        records applied to the same state give the same refs, live or replayed.
        ``snapshots`` maps each ``snapshot_artifact_id`` to its snapshot and
        publication date (read back from the store on a replay).
        """
        self.reading = []
        sent = sum(
            1 for a in self._actions() if a.kind == "search" and a.decision is ActionDecision.SENT
        )
        kept: list[ActionRecord] = []
        for record in records:
            if record.kind == "search" and record.query is not None and record.lang is not None:
                # A search the gate saw (sent, refused by it, or sent by an earlier
                # attempt) is one the track made: asking it again is a duplicate.
                if record.data_class is not None or record.reason == SKIP_EARLIER_ATTEMPT:
                    self.searched.add(_search_key(record.query, record.lang))
                if (
                    record.decision is ActionDecision.SENT
                    and record.outcome is ActionOutcome.SUCCEEDED
                ):
                    earlier = frozenset(r.ref for r in self.refs.results)
                    sent += 1
                    results = self.refs.add_hits(record.hits, search=sent)
                    record = record.model_copy(
                        update={
                            "results": results,
                            "feedback": search_feedback(results, self.refs, earlier=earlier),
                        }
                    )
                elif record.decision is ActionDecision.SENT:
                    sent += 1
            elif record.snapshot_artifact_id is not None:
                snapshot, published = snapshots[record.snapshot_artifact_id]
                ref, _new = self.capture(
                    snapshot, artifact_id=record.snapshot_artifact_id, published=published
                )
                record = record.model_copy(
                    update={"source": ref, "snapshot_id": snapshot.snapshot_id}
                )
            elif record.decision is ActionDecision.SERVED_LOCALLY and record.source is not None:
                assert record.part is not None
                self._read(record.source, int(record.part))
            elif record.decision is ActionDecision.FINISHED:
                self.finished = True
            kept.append(record)
        self.turns.append(tuple(kept))
        return tuple(kept)

    def take_reading(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        """(the parts shown this turn, the parts left for a later read, whether any is new).

        Each shown part is untrusted text with its ``detect_instructions`` flags; at
        most :data:`TURN_TEXT_CHARS` characters in all, in the order code captured
        or was asked for them.
        """
        shown: list[dict[str, Any]] = []
        waiting: list[dict[str, Any]] = []
        budget = TURN_TEXT_CHARS
        fresh = False
        for item in self.reading:
            source = self.refs.source(item.source)
            assert source is not None
            text = part_text(self.texts[item.source], item.part)
            if len(text) > budget:
                waiting.append({"ref": item.source, "part": item.part, "parts": source.parts})
                continue
            budget -= len(text)
            fresh = fresh or (item.source, item.part) not in self.shown
            self.shown.add((item.source, item.part))
            shown.append(
                {
                    "ref": item.source,
                    "part": item.part,
                    "parts": source.parts,
                    "instructions_detected": list(detect_instructions(text)),
                    "text": text,
                }
            )
        return shown, waiting, fresh


@dataclass(frozen=True, slots=True)
class PlannedAction:
    """One proposed action after code's own checks: decided, or for the gate.

    ``record`` is set when code decided alone (refused, skipped, served, finished).
    Otherwise ``search`` (text and language) or ``url`` says what the gate is asked.
    """

    index: int
    kind: Literal["search", "open", "read", "finish"]
    purpose: str
    record: ActionRecord | None = None
    search: tuple[str, str] | None = None
    url: str | None = None
    ref: str | None = None


def _decided(
    index: int,
    kind: Literal["search", "open", "read", "finish"],
    purpose: str,
    decision: ActionDecision,
    reason: str | None = None,
    **fields: Any,
) -> PlannedAction:
    return PlannedAction(
        index,
        kind,
        purpose,
        record=ActionRecord(
            index=index, kind=kind, purpose=purpose, decision=decision, reason=reason, **fields
        ),
    )


def plan_actions(
    turn: InvestigatorTurn, state: TrackState, allowance: Allowance
) -> tuple[PlannedAction, ...]:
    """What code makes of a turn's proposed actions, in their order, before any gate.

    A ``finish`` ends the track: every other action of the turn is skipped. Within
    the allowance, searches and opens go to the gate in order; beyond it they are
    refused (``allowance_spent``, not counted toward the refusal limit).
    """
    actions = turn.next[:MAX_ACTIONS_PER_TURN]
    finish = next((i for i, a in enumerate(actions) if isinstance(a, FinishAction)), None)
    searches_left = allowance.searches - state.searches_used
    opens_left = allowance.opens - state.opens_used
    seen = set(state.searched)
    out: list[PlannedAction] = []
    for i, action in enumerate(actions):
        if isinstance(action, FinishAction):
            if i == finish:
                out.append(_decided(i, "finish", "", ActionDecision.FINISHED))
            else:
                out.append(_decided(i, "finish", "", ActionDecision.SKIPPED, SKIP_FINISH))
            continue
        if finish is not None:
            out.append(
                _decided(i, action.kind, action.purpose, ActionDecision.SKIPPED, SKIP_FINISH)
            )
            continue
        if isinstance(action, SearchAction):
            text, refused = render_search(action)
            fields: dict[str, Any] = {"query": text or action.query, "lang": action.lang}
            if refused is not None:
                out.append(
                    _decided(i, "search", action.purpose, ActionDecision.REFUSED, refused, **fields)
                )
                continue
            assert text is not None
            key = _search_key(text, action.lang)
            if key in seen:
                out.append(
                    _decided(
                        i,
                        "search",
                        action.purpose,
                        ActionDecision.REFUSED,
                        Refusal.DUPLICATE_SEARCH,
                        **fields,
                    )
                )
                continue
            if searches_left <= 0:
                out.append(
                    _decided(
                        i,
                        "search",
                        action.purpose,
                        ActionDecision.REFUSED,
                        Refusal.ALLOWANCE_SPENT,
                        **fields,
                    )
                )
                continue
            seen.add(key)
            searches_left -= 1
            out.append(PlannedAction(i, "search", action.purpose, search=(text, action.lang)))
        elif isinstance(action, OpenAction):
            url = state.refs.url_for(action.ref)
            if url is None:
                reason = (
                    Refusal.NOT_OPENABLE if state.refs.source(action.ref) else Refusal.UNKNOWN_REF
                )
                out.append(
                    _decided(
                        i, "open", action.purpose, ActionDecision.REFUSED, reason, ref=action.ref
                    )
                )
                continue
            if opens_left <= 0:
                out.append(
                    _decided(
                        i,
                        "open",
                        action.purpose,
                        ActionDecision.REFUSED,
                        Refusal.ALLOWANCE_SPENT,
                        ref=action.ref,
                        url=url,
                    )
                )
                continue
            opens_left -= 1
            out.append(PlannedAction(i, "open", action.purpose, url=url, ref=action.ref))
        else:
            assert isinstance(action, ReadAction)
            source = state.refs.source(action.ref)
            fields = {"ref": action.ref, "part": action.part}
            if source is None:
                reason = (
                    Refusal.NOT_READABLE
                    if state.refs.url_for(action.ref) is not None
                    else Refusal.UNKNOWN_REF
                )
                out.append(
                    _decided(i, "read", action.purpose, ActionDecision.REFUSED, reason, **fields)
                )
                continue
            part = _parse_part(action.part, source.parts)
            if part is None:
                out.append(
                    _decided(
                        i,
                        "read",
                        action.purpose,
                        ActionDecision.REFUSED,
                        Refusal.UNKNOWN_PART,
                        **fields,
                    )
                )
                continue
            out.append(
                _decided(
                    i,
                    "read",
                    action.purpose,
                    ActionDecision.SERVED_LOCALLY,
                    ref=action.ref,
                    part=str(part),
                    source=source.ref,
                    snapshot_id=source.snapshot_id,
                )
            )
    return tuple(out)


# --------------------------------------------------------------------------- #
# The turn's input
# --------------------------------------------------------------------------- #


def _action_view(record: ActionRecord) -> dict[str, Any]:
    view: dict[str, Any] = {
        "action": record.index,
        "kind": record.kind,
        "decision": record.decision.value,
    }
    if record.reason is not None:
        view["reason"] = record.reason
    if record.outcome is not None:
        view["outcome"] = record.outcome.value
    if record.kind == "search":
        view["query"] = record.query
        view["lang"] = record.lang
        view["results"] = list(record.results)
        view["feedback"] = [f.value for f in record.feedback]
    if record.ref is not None:
        view["ref"] = record.ref
    if record.part is not None:
        view["part"] = record.part
    if record.source is not None:
        view["source"] = record.source
    return view


def turn_input(
    state: TrackState,
    *,
    track: ResearchTrack,
    brief: BriefDigest,
    sub_questions: Sequence[str],
    suggested_queries: Sequence[str],
    turn: int,
    allowance: Allowance,
    stop: Mapping[str, int],
    findings: Sequence[tuple[str, str]],
    reading: Sequence[Mapping[str, Any]],
    waiting: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The payload of one turn's request: deterministic for the same state.

    ``findings`` are (``S<n>``, claim) of the track's grounded findings so far;
    ``reading`` and ``waiting`` come from :meth:`TrackState.take_reading`.
    """
    refs = state.refs
    duplicates = refs.duplicates()
    return {
        "track_id": track.track_id,
        "turn": turn,
        "task": {
            "subject": {"kind": track.subject.kind.value, "text": track.subject.text},
            "brief": {"title": brief.title, "goal": brief.goal},
            "sub_questions": list(sub_questions),
            "suggested_queries": list(suggested_queries),
        },
        "allowance": {
            "turns_left": max(allowance.turns - turn + 1, 0),
            "searches_left": max(allowance.searches - state.searches_used, 0),
            "opens_left": max(allowance.opens - state.opens_used, 0),
            "actions_per_turn": MAX_ACTIONS_PER_TURN,
        },
        "stop_rule": dict(stop),
        "results": [
            {
                "ref": r.ref,
                "title": r.title,
                "host": r.host,
                "tier": r.tier.value,
                "held": refs.held(r.url),
                "duplicate_of": duplicates.get(r.ref),
            }
            for r in refs.results[-SHOWN_RESULTS:]
        ],
        "sources": [
            {
                "ref": s.ref,
                "title": s.title,
                "host": s.host,
                "tier": s.tier.value,
                "published": s.published.isoformat() if s.published else None,
                "parts": s.parts,
                "instructions_detected": list(s.instructions_detected),
            }
            for s in refs.sources
        ],
        "links": [
            {
                "ref": link.ref,
                "text": link.text,
                "host": link.host,
                "tier": link.tier.value,
                "from": link.source,
                "held": refs.held(link.url),
            }
            for link in refs.links[-SHOWN_LINKS:]
        ],
        "reading": [dict(r) for r in reading],
        "not_shown": [dict(w) for w in waiting],
        "findings": [{"source": s, "claim": c} for s, c in findings],
        "last_turn": [_action_view(a) for a in (state.turns[-1] if state.turns else ())],
    }


def turns_without_new_evidence(new_by_turn: Sequence[int]) -> int:
    """How many of the latest turns that read new text grounded nothing new."""
    count = 0
    for new in reversed(new_by_turn):
        if new:
            break
        count += 1
    return count


# --------------------------------------------------------------------------- #
# What a turn stores (checkpoints; this run's own)
# --------------------------------------------------------------------------- #


class TurnAnswer(_Closed):
    """A turn's answer, stored the moment it is known: a retry never buys it again.

    Keyed by the run, the track, the turn and the request's hash, so it answers only
    the request it was given.
    """

    kind: Literal["deep_research_turn_answer"]
    track_id: str
    turn: int = Field(ge=1)
    request_sha256: str
    output: InvestigatorTurn
    call: CallRecord


class TurnRecord(_Closed):
    """A turn as it ran: its answer, what code did with each action, what it grounded.

    Stored once the turn's actions are done; a retry replays it without a model
    call or a tool call, and arrives at the same state.
    """

    kind: Literal["deep_research_turn"]
    track_id: str
    turn: int = Field(ge=1)
    request_sha256: str
    call: CallRecord
    #: The answer came from a stored :class:`TurnAnswer` (a retry), not a new call.
    answer_replayed: bool
    output: InvestigatorTurn
    actions: tuple[ActionRecord, ...]
    #: Evidence ids this turn grounded, and those it quarantined.
    grounded: tuple[str, ...]
    quarantined: tuple[str, ...]
    #: Whether the turn read text it had not read before (saturation counts only these).
    fresh: bool
