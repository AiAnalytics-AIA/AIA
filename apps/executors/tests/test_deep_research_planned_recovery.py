"""A planned web track recovered at every external boundary (chunk 21's finding).

The planned mode stores every external outcome before the next call leaves: the
search with its hits in order, each fetch with the page it captured, the round once
its fetches resolved, the investigator's answer before it is grounded. A worker asked
to stop (a deploy's ``SIGTERM``) releases the step at its next checkpoint; another
worker runs it again. Each test releases the step at one boundary and compares the
recovered run with an uninterrupted reference run of the same journey, in a fresh
database:

* every search, fetch and investigator request is sent exactly as often as in the
  reference -- never twice;
* the research is the same: tracks, queries, snapshots, evidence, stop reasons,
  counts and allowance accounting, and the payload of every artifact that names no
  run-scoped identity;
* no artifact row is duplicated within the resumed run.

Run-scoped identities (``ART-…`` row ids, the ``run_id`` a track carries, a call's id)
legitimately differ between two independent runs and are left out of the comparison.
A dispatch an earlier attempt journaled with no record of its outcome is the one case
that cannot continue: the track ends ``TOOL_OUTCOME_UNCERTAIN`` and nothing more is sent.
"""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from aia_core.domain.deep_research.contracts import StopReason, TrackStatus
from aia_core.domain.deep_research.tooling import TOOL_EVENT_KINDS, ToolOutcome
from aia_core.domain.deep_research.workflow import ARTIFACT_TYPES
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.tables import ProjectArtifactRow
from aia_core.infrastructure.web_retrieval import RecordedFetchTransport, RecordedSearch
from aia_executors.deep_research import DeepResearchRuntime
from aia_worker.worker import Worker
from conftest import _truncate  # type: ignore[import-not-found]
from deep_research_fixtures import (
    ANSWERS,
    RecordedAgents,
    recorded,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ResearchWorld,
    approve_knowledge,
    drain,
    make_research_world,
    read,
    start,
    tool_events,
    worker,
)

#: The planned journey's first web query: its round fetches two pages, and its track
#: has a second round.
QUERY = "trh rostlinných nápojů česko"
#: The investigator role of a planned web round, as the recorded agents count it.
WEB_INVESTIGATOR = "web_investigator"


@dataclass
class Journey:
    world: ResearchWorld
    agents: RecordedAgents
    runtime: DeepResearchRuntime
    store: InMemoryArtifactStore
    run_id: str

    @property
    def search(self) -> RecordedSearch:
        retrieval = self.runtime.retrieval
        assert retrieval is not None and isinstance(retrieval.search, RecordedSearch)
        return retrieval.search

    @property
    def transport(self) -> RecordedFetchTransport:
        retrieval = self.runtime.retrieval
        assert retrieval is not None
        transport = retrieval.fetcher._transport
        assert isinstance(transport, RecordedFetchTransport)
        return transport

    def dispatches(self) -> dict[str, Counter[str]]:
        """What reached the recorded web and model, by request."""
        return {
            "search": Counter(self.search.calls),
            "fetch": Counter(self.transport.calls),
            "model": self.agents.roles(),
        }


def _runtime(world: ResearchWorld, agents: RecordedAgents, *, fan_out: bool) -> DeepResearchRuntime:
    runtime = recorded(world, agents)
    if fan_out:
        runtime = dataclasses.replace(
            runtime, config=dataclasses.replace(runtime.config, fan_out=True)
        )
    return runtime


@pytest.fixture
def journeys(
    sessions: sessionmaker[Session], database_url: str, build: Any
) -> Iterator[Callable[..., Journey]]:
    """``journeys(fan_out=..., release=...)``: the reference run, then the database
    emptied and the same journey run with the step released where ``release`` says."""

    def run(*, fan_out: bool, release: Callable[[Journey, Worker], None] | None) -> Journey:
        world = make_research_world(sessions)
        approve_knowledge(world)
        agents = RecordedAgents(ANSWERS)
        runtime = _runtime(world, agents, fan_out=fan_out)
        store = InMemoryArtifactStore()
        journey = Journey(world, agents, runtime, store, start(world))
        first = worker(world, database_url, store, build, runtime)
        if release is not None:
            release(journey, first)
        drain(first, limit=200)
        if release is not None:
            assert first.stopping, "the release never happened: the boundary was not reached"
            drain(worker(world, database_url, store, build, runtime), limit=200)
        return journey

    yield run


def _rows(journey: Journey) -> list[ProjectArtifactRow]:
    with journey.world.sessions() as session:
        return list(
            session.scalars(
                select(ProjectArtifactRow).where(
                    ProjectArtifactRow.artifact_type.in_(set(ARTIFACT_TYPES.values()))
                )
            )
        )


def _payload(journey: Journey, row: ProjectArtifactRow) -> Any:
    return json.loads(journey.store.get(row.storage_key, expected_sha256=row.sha256))


def _without(item: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in item.items() if k not in keys}


def _track(payload: dict[str, Any]) -> dict[str, Any]:
    """A track's research, without the identities only its own run or world has.

    A web track keeps everything but the run's id, each call's and query's call id and
    each snapshot's artifact row. An internal track is not what this file recovers and
    reads Client Knowledge whose ids each world mints anew (``KNW-…``), so its
    fingerprint, its knowledge refs and its evidence ids differ between two worlds; it
    is compared by what it found and what it cost.
    """
    out = _without(payload, "run_id")
    out["calls"] = [_without(c, "call_id") for c in out["calls"]]
    out["queries"] = [_without(q, "call_id") for q in out["queries"]]
    out["snapshots"] = [_without(s, "artifact_id") for s in out["snapshots"]]
    if out["track"]["channel"] == "INTERNAL":
        out["track"] = _without(out["track"], "fingerprint")
        out["evidence"] = [_without(e, "evidence_id", "source_ref") for e in out["evidence"]]
        for key in ("knowledge_refs", "sources"):
            out[key] = len(out[key])
    return out


#: Artifacts whose payload names no run- or world-scoped identity: equal byte for byte.
_IDENTITY_FREE = {ARTIFACT_TYPES["snapshot"]}


def semantics(journey: Journey) -> dict[str, Any]:
    """What a run researched, for comparing two independent runs."""
    rows = _rows(journey)
    tracks = {}
    for row in rows:
        if row.artifact_type == ARTIFACT_TYPES["track"]:
            payload = _payload(journey, row)
            tracks[payload["track"]["track_id"]] = _track(payload)
    return {
        "tracks": tracks,
        "kinds": Counter(r.artifact_type for r in rows),
        "identity_free": sorted(
            (r.artifact_type, r.input_fingerprint, r.sha256)
            for r in rows
            if r.artifact_type in _IDENTITY_FREE
        ),
        # Every planned search as it came back, in order and with its hits, less the
        # call id its query record carries.
        "planned_searches": sorted(
            json.dumps(
                {**(p := _payload(journey, r)), "record": _without(p["record"], "call_id")},
                sort_keys=True,
                ensure_ascii=False,
            )
            for r in rows
            if r.artifact_type == ARTIFACT_TYPES["planned_search"]
        ),
    }


# --------------------------------------------------------------------------- #
# The releases
# --------------------------------------------------------------------------- #


def after_search(monkeypatch: pytest.MonkeyPatch) -> Callable[[Journey, Worker], None]:
    """Stop as the round's search returns: released before its first fetch."""

    def release(journey: Journey, w: Worker) -> None:
        served = RecordedSearch.search

        def search(self: RecordedSearch, query: str, *, max_results: int) -> Any:
            response = served(self, query, max_results=max_results)
            if query == QUERY:
                w.request_stop()
            return response

        monkeypatch.setattr(RecordedSearch, "search", search)

    return release


def after_first_fetch(monkeypatch: pytest.MonkeyPatch) -> Callable[[Journey, Worker], None]:
    """Stop as the round's first page returns: released before its second fetch."""

    def release(journey: Journey, w: Worker) -> None:
        served = RecordedFetchTransport.get
        searched: list[str] = []
        original = RecordedSearch.search

        def search(self: RecordedSearch, query: str, *, max_results: int) -> Any:
            searched.append(query)
            return original(self, query, max_results=max_results)

        def get(self: RecordedFetchTransport, url: str, *, address: str, max_bytes: int) -> Any:
            response = served(self, url, address=address, max_bytes=max_bytes)
            if searched and searched[-1] == QUERY and not url.endswith("/robots.txt"):
                w.request_stop()
            return response

        monkeypatch.setattr(RecordedSearch, "search", search)
        monkeypatch.setattr(RecordedFetchTransport, "get", get)

    return release


def after_answer(monkeypatch: pytest.MonkeyPatch) -> Callable[[Journey, Worker], None]:
    """Stop as the first planned round's investigator answers: released before the next
    round's search (the reproduction in the finding)."""

    def release(journey: Journey, w: Worker) -> None:
        answer = RecordedAgents._web_investigator

        def web_investigator(self: RecordedAgents, payload: dict[str, Any]) -> dict[str, Any]:
            out = answer(self, payload)
            w.request_stop()
            return out

        monkeypatch.setattr(RecordedAgents, "_web_investigator", web_investigator)

    return release


# --------------------------------------------------------------------------- #
# The tests
# --------------------------------------------------------------------------- #


class _Snapshot:
    """A finished reference, read before its database was emptied."""

    def __init__(self, semantics_: dict[str, Any], dispatches: dict[str, Counter[str]]) -> None:
        self.semantics, self._dispatches = semantics_, dispatches

    def dispatches(self) -> dict[str, Counter[str]]:
        return self._dispatches


def _compare(recovered: Journey, reference: _Snapshot, *, fanned_out: bool) -> None:
    run, bundle = read(recovered.world, recovered.run_id, recovered.store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    released = [
        s["node_key"]
        for s in run["steps"]
        if any(a["status"].value == "ABANDONED" for a in s["attempts"])
    ]
    # Released once, at the boundary, and run again: by the investigation itself, or
    # fanned out, by the track's own step (``investigate/<track id>``).
    assert len(released) == 1
    assert released[0].startswith("investigate/") if fanned_out else released == ["investigate"]
    # Nothing was sent twice: every request exactly as often as in the uninterrupted run.
    assert recovered.dispatches() == reference.dispatches()
    assert set(recovered.dispatches()["search"].values()) == {1}
    # The same research, the same accounting, the same identity-free payloads.
    assert semantics(recovered) == reference.semantics
    # No artifact row was written twice within the resumed run.
    keys = Counter((r.artifact_type, r.input_fingerprint) for r in _rows(recovered))
    assert [k for k, n in keys.items() if n > 1] == []


def _run_reference(
    journeys: Callable[..., Journey], sessions: sessionmaker[Session], *, fan_out: bool
) -> _Snapshot:
    reference = journeys(fan_out=fan_out, release=None)
    snap = _Snapshot(semantics(reference), reference.dispatches())
    _truncate(sessions)
    return snap


@pytest.mark.parametrize(
    ("release", "fan_out"),
    [
        pytest.param(after_search, False, id="after-search-before-fetch"),
        pytest.param(after_first_fetch, False, id="after-a-fetch-before-the-round-ends"),
        pytest.param(after_answer, False, id="after-the-round-answer"),
        pytest.param(after_answer, True, id="after-the-round-answer-fanned-out"),
    ],
)
def test_a_released_planned_track_continues_and_sends_nothing_twice(
    journeys: Callable[..., Journey],
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    release: Callable[[pytest.MonkeyPatch], Callable[[Journey, Worker], None]],
    fan_out: bool,
) -> None:
    reference = _run_reference(journeys, sessions, fan_out=fan_out)
    recovered = journeys(fan_out=fan_out, release=release(monkeypatch))
    _compare(recovered, reference, fanned_out=fan_out)


def test_a_dispatch_with_no_record_of_its_outcome_ends_the_track_and_sends_nothing_more(
    journeys: Callable[..., Journey],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The window a record cannot close: the search's outcome is journaled, the attempt
    dies before its record is written. What came back is not known; nothing is guessed."""
    from aia_executors.deep_research import investigate

    searched = investigate._PlannedLog.searched
    w_box: list[Worker] = []

    def lost(self: Any, round_index: int, query: str, outcome: Any) -> Any:
        if query == QUERY:
            w_box[0].request_stop()
            from aia_worker.executor import ShutdownRequested

            raise ShutdownRequested()
        return searched(self, round_index, query, outcome)

    def release(journey: Journey, w: Worker) -> None:
        w_box.append(w)
        monkeypatch.setattr(investigate._PlannedLog, "searched", lost)

    recovered = journeys(fan_out=False, release=release)
    run, bundle = read(recovered.world, recovered.run_id, recovered.store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    assert recovered.search.calls.count(QUERY) == 1, "a search with no record is not sent again"
    track = next(t for t in bundle.tracks if t.stop_reason is StopReason.TOOL_OUTCOME_UNCERTAIN)
    assert track.status is TrackStatus.INCOMPLETE
    # Nothing more left for that track after the lost search.
    entries = [
        e
        for e in tool_events(recovered.world, recovered.run_id)
        if e["payload"]["track_id"] == track.track_id
        and e["message"] == TOOL_EVENT_KINDS[ToolOutcome.DISPATCHED]
    ]
    assert len(entries) == 1
