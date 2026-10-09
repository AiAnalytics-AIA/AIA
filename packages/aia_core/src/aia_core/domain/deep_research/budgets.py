"""What a Deep Research run may call, at most, by kind: the counts its cost ceiling prices.

Plan ``deep-research-web-search.md`` § 9 and chunk 22. A run's cost ceiling
(``aia_core.domain.run_cost.deep_research_cost_ceiling``) is these counts, each priced
at what one call of its kind may cost. This module says how many calls of each kind a
run can make, from its frozen request and its preset alone -- before anything is sent,
with no composition at hand -- and why each count is a bound:

* **Model requests.** The planner asks once; the lead once, plus every re-plan its
  preset allows (a refused one counts too). A planned web track asks one investigator
  request per search it may send (one per round, and a round needs a sent search); an
  agent-directed track one per turn; a lead-planned run at most its ceiling's turns. An
  internal track asks once. The verifier asks once per batch of a track's candidates,
  and a track's candidates are bounded twice: by its requests times what one answer may
  hold (:data:`EVIDENCE_PER_ANSWER`, read from the contracts), and by its evidence
  target, since the stop rule is checked before every request (the last request may
  add a full answer to ``evidence_target - 1``). The planned synthesizer asks once; an
  agent-directed or lead-planned run's brief synthesizer asks once and may be asked
  once more to repair its numbers (chunk 13), so twice.
* **Tool calls.** Searches and pages opened are each track's allowance
  (``planning.allocate``), or a lead-planned run's ceiling.
* **Routes beyond search and fetch** -- triage reads on the light model, a focused
  crawl's pages, dataset connectors (and the archive lookup), Common Crawl index
  queries and archive records -- are each preset's :data:`ROUTE_ALLOWANCES`.
  No step reads those yet (chunk 23 wires the routes): until the step that sends them
  holds itself to them, a composition that offers one of these routes must price it,
  and the chunk that wires it makes the allowance the step's own limit. They live
  here, not on :class:`~.planning.DepthPreset`, so that no stored plan and no track
  fingerprint changes before a step reads them.

Each repair is inside its request: a research agent's reservation covers the primary
call and its one schema repair, at its own kind's window and output limit
(:mod:`.request_limits`), and a triage read's likewise. Reuse is not subtracted: a
reused track costs nothing, and the bound holds.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Final

from annotated_types import MaxLen
from pydantic import BaseModel

from .agents import ExtractionProposal, InvestigatorTurn
from .contracts import Channel, DeepResearchRequest
from .lead import LEAD_LIMITS, lead_limits
from .planning import DepthPreset, allocate, track_slots

__all__ = [
    "EVIDENCE_PER_ANSWER",
    "MODEL_KINDS",
    "ROUTE_ALLOWANCES",
    "CallBounds",
    "CallKind",
    "ResearchMode",
    "RouteAllowance",
    "TrackCounts",
    "call_bounds",
    "lead_state_bounds",
    "track_counts",
]


class CallKind(StrEnum):
    """One kind of paid call a run can make, priced on its own."""

    PLANNER = "planner"
    #: The lead's plan and each re-plan.
    LEAD = "lead"
    INTERNAL_INVESTIGATOR = "internal_investigator"
    #: A planned web track's investigator request, or an agent-directed turn.
    INVESTIGATOR = "investigator"
    VERIFIER = "verifier"
    SYNTHESIZER = "synthesizer"
    #: A triage reader's request on the light model (chunk 20).
    TRIAGE = "triage"
    SEARCH = "search"
    FETCH = "fetch"
    #: A page a focused crawl fetches (chunk 17), on its own switch.
    CRAWL_FETCH = "crawl_fetch"
    #: A dataset connector's query, or an archive lookup (chunks 14-16).
    CONNECTOR = "connector"
    #: A Common Crawl URL index query through Athena (chunk 18).
    URL_INDEX_QUERY = "url_index_query"
    #: An archived record read by byte range (chunk 18).
    ARCHIVE_FETCH = "archive_fetch"


#: The kinds that are model requests: each priced at a per-request reservation.
MODEL_KINDS: Final = frozenset(
    {
        CallKind.PLANNER,
        CallKind.LEAD,
        CallKind.INTERNAL_INVESTIGATOR,
        CallKind.INVESTIGATOR,
        CallKind.VERIFIER,
        CallKind.SYNTHESIZER,
        CallKind.TRIAGE,
    }
)


class ResearchMode(StrEnum):
    """How a run's web tracks are researched: the composition's switches."""

    PLANNED = "planned"
    AGENT_DIRECTED = "agent_directed"
    LEAD = "lead"


def _max_items(model: type[BaseModel], field: str) -> int:
    for meta in model.model_fields[field].metadata:
        if isinstance(meta, MaxLen):
            return int(meta.max_length)
    raise AssertionError(f"{model.__name__}.{field} has no maximum length")


#: The most evidence one investigator answer may hold, in either mode: what one request
#: can add to a track's candidates.
EVIDENCE_PER_ANSWER: Final = max(
    _max_items(ExtractionProposal, "evidence"), _max_items(InvestigatorTurn, "evidence")
)


@dataclass(frozen=True, slots=True)
class RouteAllowance:
    """One run's calls on the routes beyond search and fetch. Proposed (DR-5)."""

    triage_reads: int
    crawl_pages: int
    connector_calls: int
    index_queries: int
    archive_fetches: int

    def __post_init__(self) -> None:
        if any(getattr(self, f.name) < 0 for f in fields(self)):
            raise ValueError("a route allowance is not negative")


_NONE: Final = RouteAllowance(0, 0, 0, 0, 0)

#: Per preset (``planning.PRESET_TABLE_VERSION``; proposed, plan § 9): STANDARD and DEEP
#: have no triage, crawl or Common Crawl; EXHAUSTIVE has all three. Connectors -- public
#: data interfaces, today without a charge -- are allowed from STANDARD up.
ROUTE_ALLOWANCES: Final[Mapping[str, RouteAllowance]] = {
    "QUICK": _NONE,
    "STANDARD": RouteAllowance(
        triage_reads=0, crawl_pages=0, connector_calls=24, index_queries=0, archive_fetches=0
    ),
    "DEEP": RouteAllowance(
        triage_reads=0, crawl_pages=0, connector_calls=60, index_queries=0, archive_fetches=0
    ),
    "EXHAUSTIVE": RouteAllowance(
        triage_reads=2000,
        crawl_pages=1000,
        connector_calls=200,
        index_queries=40,
        archive_fetches=400,
    ),
}


@dataclass(frozen=True, slots=True)
class TrackCounts:
    """The tracks a run opens within its preset's limit, by channel."""

    web: int
    internal: int


def track_counts(request: DeepResearchRequest, depth: DepthPreset) -> TrackCounts:
    """What :func:`~.planning.build_tracks` would open for ``request``, counted."""
    opened = track_slots(request, depth)[: depth.max_tracks]
    web = sum(1 for _subject, channel in opened if channel is Channel.WEB)
    return TrackCounts(web=web, internal=len(opened) - web)


@dataclass(frozen=True, slots=True)
class CallBounds:
    """The most calls of each kind a run can make. Every kind is stated, zero included."""

    counts: Mapping[CallKind, int]

    def __post_init__(self) -> None:
        missing = set(CallKind) - set(self.counts)
        if missing:
            raise ValueError(f"call bounds state every kind; missing {sorted(missing)}")
        if any(n < 0 for n in self.counts.values()):
            raise ValueError("a call bound is not negative")

    def __getitem__(self, kind: CallKind) -> int:
        return self.counts[kind]


def _verifier_requests(tracks: int, requests_per_track: int, depth: DepthPreset) -> int:
    """Verifier batches over ``tracks`` tracks, each asking up to ``requests_per_track``."""
    if tracks == 0 or requests_per_track == 0:
        return 0
    candidates = min(
        requests_per_track * EVIDENCE_PER_ANSWER,
        depth.evidence_target - 1 + EVIDENCE_PER_ANSWER,
    )
    return tracks * -(-candidates // depth.verify_batch)


def _bounds(
    depth: DepthPreset, tracks: TrackCounts, mode: ResearchMode, routes: RouteAllowance
) -> dict[CallKind, int]:
    counts = dict.fromkeys(CallKind, 0)
    web_ids = [str(i) for i in range(tracks.web)]
    verifier = _verifier_requests(tracks.internal, 1, depth)
    if mode is ResearchMode.LEAD:
        lead = LEAD_LIMITS[depth.name]
        limits = lead_limits(
            depth.name,
            subjects=web_ids[: lead.max_tasks],
            max_turns=depth.max_turns,
            max_searches=depth.max_searches,
            max_opens=depth.max_opens,
            max_search_calls=depth.max_search_calls,
            max_fetches=depth.max_fetches,
        )
        has_web = tracks.web > 0
        counts[CallKind.LEAD] = (1 + limits.replans) if has_web else 0
        counts[CallKind.INVESTIGATOR] = limits.ceiling.turns if has_web else 0
        counts[CallKind.SEARCH] = limits.ceiling.searches if has_web else 0
        counts[CallKind.FETCH] = limits.ceiling.opens if has_web else 0
        # Every task is a track of at most the per-task turns, and there are at most
        # max_tasks of them.
        verifier += _verifier_requests(
            limits.max_tasks if has_web else 0, limits.per_task.turns, depth
        )
    else:
        directed = mode is ResearchMode.AGENT_DIRECTED
        allowances = allocate(web_ids, depth, agent_directed=directed).values()
        counts[CallKind.PLANNER] = 1 if tracks.web else 0
        counts[CallKind.SEARCH] = sum(a.search_calls for a in allowances)
        counts[CallKind.FETCH] = sum(a.fetches for a in allowances)
        if directed:
            counts[CallKind.INVESTIGATOR] = tracks.web * depth.max_turns
            verifier += _verifier_requests(tracks.web, depth.max_turns, depth)
        else:
            # One request per round, and a round needs a sent search.
            counts[CallKind.INVESTIGATOR] = counts[CallKind.SEARCH]
            for a in allowances:
                verifier += _verifier_requests(1, a.search_calls, depth)
    counts[CallKind.INTERNAL_INVESTIGATOR] = tracks.internal
    counts[CallKind.VERIFIER] = verifier
    # The brief is repaired once with every problem (chunk 13): a second request.
    briefs = 1 if mode is ResearchMode.PLANNED else 2
    counts[CallKind.SYNTHESIZER] = briefs if tracks.web or tracks.internal else 0
    counts[CallKind.TRIAGE] = routes.triage_reads
    counts[CallKind.CRAWL_FETCH] = routes.crawl_pages
    counts[CallKind.CONNECTOR] = routes.connector_calls
    counts[CallKind.URL_INDEX_QUERY] = routes.index_queries
    counts[CallKind.ARCHIVE_FETCH] = routes.archive_fetches
    return counts


def call_bounds(
    depth: DepthPreset,
    tracks: TrackCounts,
    mode: ResearchMode,
    *,
    allowances: Mapping[str, RouteAllowance] = ROUTE_ALLOWANCES,
) -> CallBounds:
    """The most calls of each kind a run of ``depth`` over ``tracks`` makes in ``mode``.

    ``allowances`` are the route allowances in force: the run's settings
    (``settings.route_allowances``, chunk 43c), or the code's table.
    """
    if depth.name not in allowances or depth.name not in LEAD_LIMITS:
        raise LookupError(f"the preset table has no budget for {depth.name!r}")
    return CallBounds(_bounds(depth, tracks, mode, allowances[depth.name]))


def lead_state_bounds(
    bounds: CallBounds, *, committed: tuple[int, int, int], replans_allowed: int
) -> CallBounds:
    """A lead-planned run's bounds once its plan is in: what is committed, not the ceiling.

    ``committed`` is ``LeadState.committed()`` as (turns, searches, opens): what finished
    tasks used plus every running and pending task's budget. Code keeps it within the
    run's ceiling at every re-plan, and a budget move leaves it as it was, so these
    bounds never exceed the start's.
    """
    turns, searches, opens = committed
    counts = dict(bounds.counts)
    counts[CallKind.INVESTIGATOR] = turns
    counts[CallKind.SEARCH] = searches
    counts[CallKind.FETCH] = opens
    counts[CallKind.LEAD] = 1 + replans_allowed
    return CallBounds(counts)
