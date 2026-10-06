"""The agent-directed investigator end to end, recorded: worker, gateway, gate, executors.

Plan ``deep-research-web-search.md`` chunk 9. The same production path as
``test_deep_research_journey.py`` -- the worker loop and its leases, the governed
gateway with the Bedrock adapter, the retrieval gate, the executors -- with the
composition's ``agent_directed`` on. The web is ``fixtures/deep_research/
investigator_web.json`` (fictional ``*-dr.example`` hosts); the investigator's turns
are scripted in ``investigator_turns.json`` by subject and turn. Nothing leaves the
process.

The scripted tracks, on the fictional client's design (web channel, STANDARD):

* Q1 -- three searches at once (Czech, English, the publisher's site); the news page
  opened and an unknown ref refused; the link from the news to the official table
  followed (``L1``) while the news, asked again, is a cache hit; on the table one
  finding grounded with its measures, one mis-stated (households as people), one
  without its measure; the methodology note read from the capture; the gap searched;
  finish.
* Q2 -- a page that instructs the agent to search the client's name; it does, three
  times, and code refuses each (Class B on a Class C route): ``repeated_refusals``.
* Ovesný nápoj -- two searches at once, one whose answer is lost: the track ends
  ``INCOMPLETE`` and the lost search is never sent again.
* Mandlový nápoj -- finished at once, naming its gap.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.research import research_artifacts
from aia_core.domain.ai_contracts import canonical_json
from aia_core.domain.deep_research.contracts import (
    Channel,
    QuarantineReason,
    QueryDecision,
    StopReason,
    SubjectKind,
    TrackStatus,
)
from aia_core.domain.deep_research.investigator import INVESTIGATOR_VERSION
from aia_core.domain.deep_research.tooling import ToolOutcome
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.web_retrieval import RecordedSearch
from aia_core.infrastructure.workflow_repository import WorkQueue
from aia_executors import deep_research as deep_research_package
from aia_executors.ai_runtime import AIRuntimeConfigError, build_gateway
from aia_executors.deep_research import DeepResearchConfig, DeepResearchRuntime
from aia_executors.deep_research import agent_directed as agent_directed_module
from aia_executors.deep_research_recorded import recorded_runtime
from aia_executors.deep_research_runtime import deep_research_runtime
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ALMOND,
    ANSWERS,
    DESIGN,
    DESIGN_2,
    OATS,
    Q1,
    Q2,
    SOY,
    TEST_ROUTE,
    Journey,
    RecordedAgents,
    ResearchWorld,
    Signer,
    _take_the_lease,
    ai_settings,
    drain,
    pass_one,  # noqa: F401  (a fixture)
    read,
    research,  # noqa: F401  (a fixture)
    tid,
    tool_events,
    worker,
)

FIXTURES = Path(__file__).parent / "fixtures" / "deep_research"
WEB = FIXTURES / "investigator_web.json"
TURNS: dict[str, list[dict[str, Any]]] = json.loads(
    (FIXTURES / "investigator_turns.json").read_text(encoding="utf-8")
)
W = Channel.WEB
QS, OS = SubjectKind.QUESTION, SubjectKind.OBJECT

_EVIDENCE_DEFAULTS: dict[str, Any] = {
    "evidence_type": "official_report",
    "source_date": None,
    "geography": "CZ",
    "population": "",
    "topics": [],
    "outcome_overlap": False,
    "recommended_use": "context_only",
    "source_quality": 0.9,
    "measures": [],
}
_MEASURE_DEFAULTS: dict[str, Any] = {
    "unit": None,
    "scale": 1,
    "period": None,
    "geography": None,
    "population": None,
    "denominator": None,
    "measure_name": None,
    "basis": None,
}


@dataclass
class ScriptedInvestigator(RecordedAgents):
    """The recorded agents, and an investigator answering from its script by subject and turn."""

    turns: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: TURNS)
    #: Every investigator payload it was sent, by (subject, turn), in order.
    shown: list[tuple[str, int, dict[str, Any]]] = field(default_factory=list)

    def _investigator(self, payload: dict[str, Any]) -> dict[str, Any]:
        subject, turn = payload["task"]["subject"]["text"], payload["turn"]
        self.shown.append((subject, turn, payload))
        answer = json.loads(json.dumps(self.turns[subject][turn - 1]))
        answer["evidence"] = [
            {
                **_EVIDENCE_DEFAULTS,
                **e,
                "measures": [{**_MEASURE_DEFAULTS, **m} for m in e.get("measures", [])],
            }
            for e in answer["evidence"]
        ]
        return dict(answer)

    def turns_of(self, subject: str) -> list[int]:
        return [t for s, t, _ in self.shown if s == subject]

    def payload(self, subject: str, turn: int) -> dict[str, Any]:
        return next(p for s, t, p in self.shown if s == subject and t == turn)


def directed(
    world: ResearchWorld, agents: RecordedAgents, *, agent_directed: bool = True
) -> DeepResearchRuntime:
    settings = ai_settings(world.client_id, approved_for=TEST_ROUTE)
    return recorded_runtime(
        gateway=build_gateway(settings, transport=agents, signer=Signer()),
        config=DeepResearchConfig(
            policy_version=settings.policy_version,
            max_output_tokens=settings.research_max_output_tokens,
            context_window_tokens=settings.context_window_tokens,
            reservation_usd=settings.research_reservation_usd,
            fictional_client_ids=settings.fictional_client_ids,
            material_approvals=settings.material_approvals,
            agent_directed=agent_directed,
        ),
        fixture=WEB,
        env={"AIA_ENV": "test"},
    )


def start_web(world: ResearchWorld, content: dict[str, Any] = DESIGN) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=content, source_stage="brief"
        )
        run = DeepResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id, preset_name="STANDARD", channels=(W,)
        )
        session.commit()
        return run.run_id


def track_events(world: ResearchWorld, run_id: str, track: str) -> list[dict[str, Any]]:
    return [e for e in tool_events(world, run_id) if e["payload"]["track_id"] == track]


def turn_events(world: ResearchWorld, run_id: str) -> list[dict[str, Any]]:
    with world.sessions() as session:
        events = DeepResearchRuns(session, world.lead_scope(session)).events(run_id, limit=2000)
    return [e for e in events if e["message"] == "deep_research_turn"]


@dataclass(frozen=True)
class Directed:
    world: ResearchWorld
    agents: ScriptedInvestigator
    runtime: DeepResearchRuntime
    run_id: str

    @property
    def search(self) -> RecordedSearch:
        retrieval = self.runtime.retrieval
        assert retrieval is not None and isinstance(retrieval.search, RecordedSearch)
        return retrieval.search

    @property
    def fetched(self) -> list[str]:
        retrieval = self.runtime.retrieval
        assert retrieval is not None
        return list(retrieval.fetcher._transport.calls)  # type: ignore[attr-defined]


@pytest.fixture
def directed_run(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> Directed:
    agents = ScriptedInvestigator(ANSWERS)
    runtime = directed(research, agents)
    run_id = start_web(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    return Directed(world=research, agents=agents, runtime=runtime, run_id=run_id)


# --------------------------------------------------------------------------- #
# The run
# --------------------------------------------------------------------------- #


def test_every_track_runs_to_its_own_stop(
    directed_run: Directed, store: InMemoryArtifactStore
) -> None:
    world, agents = directed_run.world, directed_run.agents
    run, bundle = read(world, directed_run.run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    tracks = {t.track_id: t for t in bundle.tracks}
    assert {k: (t.status, t.stop_reason) for k, t in tracks.items()} == {
        tid(QS, Q1, W): (TrackStatus.COMPLETED, StopReason.AGENT_FINISHED),
        tid(QS, Q2, W): (TrackStatus.COMPLETED, StopReason.STOP_REFUSALS),
        tid(OS, OATS, W): (TrackStatus.INCOMPLETE, StopReason.TOOL_OUTCOME_UNCERTAIN),
        tid(OS, ALMOND, W): (TrackStatus.COMPLETED, StopReason.AGENT_FINISHED),
    }
    # One investigator request a turn, and no planned-mode web investigator at all.
    assert agents.turns_of(Q1) == [1, 2, 3, 4, 5]
    assert agents.turns_of(Q2) == [1, 2, 3, 4, 5]
    assert agents.turns_of(OATS) == [1] and agents.turns_of(ALMOND) == [1]
    roles = agents.roles()
    assert roles["investigator"] == 12 and roles["web_investigator"] == 0
    assert roles["planner"] == 1
    assert bundle.counts["model_requests"] == len(agents.requests)
    # Searches: Q1 4, Q2 1 (three refused), oats 2 (one lost). Fetches: news, table,
    # instructions page; the news again was answered from the run's captures.
    assert bundle.counts["search_calls"] == 7 and bundle.counts["fetches"] == 3
    assert bundle.counts["queries_refused"] == 3
    assert directed_run.fetched == [
        "https://zpravy-dr.example/trh-napoju",
        "https://stat-dr.example/tabulka-2025",
        "https://pokyny-dr.example/pokyny",
    ]


def test_a_lead_is_followed_from_the_news_to_the_table_it_links(
    directed_run: Directed, store: InMemoryArtifactStore
) -> None:
    agents = directed_run.agents
    third = agents.payload(Q1, 3)
    # The model sees the link as a ref, its anchor text and host -- never a URL.
    assert third["links"] == [
        {
            "ref": "L1",
            "text": "tabulce spotřeby za rok 2025",
            "host": "stat-dr.example",
            "tier": "T1",
            "from": "S1",
            "held": None,
        }
    ]
    assert "https://" not in json.dumps(third, ensure_ascii=False)
    fourth = agents.payload(Q1, 4)
    assert [s["ref"] for s in fourth["sources"]] == ["S1", "S2"]
    assert fourth["sources"][1]["host"] == "stat-dr.example"
    assert fourth["sources"][1]["tier"] == "T1" and fourth["sources"][1]["parts"] == 2
    # The news, opened again, came from the run's captures.
    [cached] = [a for a in fourth["last_turn"] if a["ref"] == "R1"]
    assert cached["decision"] == "cached" and cached["source"] == "S1"
    _run, bundle = read(directed_run.world, directed_run.run_id, store)
    [accepted] = [a.evidence for a in bundle.accepted if a.evidence.track_id == tid(QS, Q1, W)]
    assert accepted.source_url == "https://stat-dr.example/tabulka-2025"


def test_up_to_five_actions_are_all_journaled_before_any_leaves(directed_run: Directed) -> None:
    events = track_events(directed_run.world, directed_run.run_id, tid(QS, Q1, W))
    outcomes = [e["payload"]["outcome"] for e in events]
    # Turn 1's three searches: three dispatches on record, then three outcomes.
    assert outcomes[:6] == [ToolOutcome.DISPATCHED.value] * 3 + [ToolOutcome.SUCCEEDED.value] * 3
    # Each in its own language; the site search goes as an operator code wrote.
    assert directed_run.search.calls[:3] == [
        "trh rostlinných nápojů",
        "plant-based drinks Czech market",
        "spotřeba rostlinných nápojů site:stat-dr.example",
    ]
    assert directed_run.search.languages[:3] == ["cs", "en", "cs"]
    second = directed_run.agents.payload(Q1, 2)
    feedback = {a["query"]: a["feedback"] for a in second["last_turn"]}
    assert feedback["spotřeba rostlinných nápojů site:stat-dr.example"] == ["no_hits"]
    assert [r["ref"] for r in second["results"]] == ["R1", "R2", "R3"]  # the news once


def test_an_unknown_ref_is_refused_and_a_read_sends_nothing(directed_run: Directed) -> None:
    agents = directed_run.agents
    refused = [a for a in agents.payload(Q1, 3)["last_turn"] if a["ref"] == "R99"]
    assert refused == [
        {"action": 1, "kind": "open", "decision": "refused", "reason": "unknown_ref", "ref": "R99"}
    ]
    fifth = agents.payload(Q1, 5)
    [read_back] = [a for a in fifth["last_turn"] if a["kind"] == "read"]
    assert read_back["decision"] == "served_locally" and read_back["source"] == "S2"
    assert [(r["ref"], r["part"]) for r in fifth["reading"]] == [("S2", 2)]
    assert "Metodická poznámka" in fifth["reading"][0]["text"]
    # Turn 4 sent one search and nothing else; the read is not in the journal.
    events = track_events(directed_run.world, directed_run.run_id, tid(QS, Q1, W))
    assert Counter(e["payload"]["outcome"] for e in events) == Counter(
        {
            ToolOutcome.DISPATCHED.value: 6,  # 4 searches, 2 pages
            ToolOutcome.SUCCEEDED.value: 6,
            ToolOutcome.CACHED.value: 1,
        }
    )


def test_a_gap_is_searched_in_a_later_turn(directed_run: Directed) -> None:
    agents = directed_run.agents
    assert agents.payload(Q1, 3)["last_turn"][0]["source"] == "S1"
    fifth = agents.payload(Q1, 5)
    [gap] = [a for a in fifth["last_turn"] if a["kind"] == "search"]
    assert gap["query"] == "metodika spotřeby rostlinných nápojů" and gap["results"] == ["R4"]
    assert "metodika spotřeby rostlinných nápojů" in directed_run.search.calls


def test_measures_are_required_and_a_misstated_one_is_quarantined(
    directed_run: Directed, store: InMemoryArtifactStore
) -> None:
    _run, bundle = read(directed_run.world, directed_run.run_id, store)
    q1 = tid(QS, Q1, W)
    reasons = {q.claim: q.reason for q in bundle.quarantined if q.track_id == q1}
    assert reasons == {
        "Rostlinné nápoje kupuje 45 % domácností.": QuarantineReason.MEASURE_NOT_IN_SOURCE,
        "Rostlinné nápoje kupuje v Česku 45 % domácností.": QuarantineReason.MEASURE_MISSING,
    }
    [accepted] = [a.evidence for a in bundle.accepted if a.evidence.track_id == q1]
    assert [(m.value, m.unit, m.scale, m.period, m.geography) for m in accepted.measures] == [
        (12.5, "%", 1, "Y2025", "CZ"),
        (41.0, "l", 1_000_000, "Y2025", "CZ"),
    ]
    assert accepted.measures[1].basis is not None and accepted.measures[1].basis.value == (
        "preliminary"
    )


def test_a_page_telling_the_agent_to_search_the_client_is_refused_three_times(
    directed_run: Directed, store: InMemoryArtifactStore
) -> None:
    agents = directed_run.agents
    third = agents.payload(Q2, 3)
    assert third["reading"][0]["instructions_detected"] == ["ignore_instructions"]
    _run, bundle = read(directed_run.world, directed_run.run_id, store)
    q2 = {t.track_id: t for t in bundle.tracks}[tid(QS, Q2, W)]
    refused = [q for q in q2.queries if q.decision is QueryDecision.REFUSED]
    assert [(q.text, q.data_class, q.refusal) for q in refused] == [
        (text, DataClass.CLASS_B_DERIVED_CLIENT, "egress_route_not_approved_for_class")
        for text in ("Acme ovesný nápoj", "Acme nápoje cena", "Acme recenze")
    ]
    assert q2.detail.endswith("egress_route_not_approved_for_class")
    assert not any("Acme" in q for q in directed_run.search.calls)  # nothing left
    # Each refusal was reported to the next turn with its reason.
    fifth = agents.payload(Q2, 5)
    assert fifth["last_turn"][0]["reason"] == "egress_route_not_approved_for_class"


def test_an_uncertain_search_ends_its_track_and_is_never_sent_again(
    directed_run: Directed,
) -> None:
    lost = "ovesný nápoj ztracený"
    assert directed_run.search.calls.count(lost) == 1
    assert directed_run.agents.turns_of(OATS) == [1]  # no turn after the lost answer
    events = track_events(directed_run.world, directed_run.run_id, tid(OS, OATS, W))
    assert Counter(e["payload"]["outcome"] for e in events) == Counter(
        {
            ToolOutcome.DISPATCHED.value: 2,
            ToolOutcome.SUCCEEDED.value: 1,
            ToolOutcome.UNCERTAIN.value: 1,
        }
    )


def test_a_finished_track_names_its_gaps(
    directed_run: Directed, store: InMemoryArtifactStore
) -> None:
    _run, bundle = read(directed_run.world, directed_run.run_id, store)
    almond = {t.track_id: t for t in bundle.tracks}[tid(OS, ALMOND, W)]
    assert almond.search_calls == 0 and almond.fetches == 0
    assert directed_run.agents.turns_of(ALMOND) == [1]


def test_the_mode_is_recorded_and_a_changed_mode_is_refused_mid_run(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    agents = ScriptedInvestigator(ANSWERS)
    runtime = directed(research, agents)
    assert runtime.versions()["investigator"] == INVESTIGATOR_VERSION
    assert runtime.inputs().investigator == INVESTIGATOR_VERSION
    run_id = start_web(research)
    assert worker(research, database_url, store, build, runtime).run_once()
    planned_mode = directed(research, agents, agent_directed=False)
    drain(worker(research, database_url, store, build, planned_mode))
    with research.sessions() as session:
        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    assert run["steps"][1]["attempts"][0]["error"]["reason"] == "composition_changed"
    assert agents.roles() == Counter(planner=1)


# --------------------------------------------------------------------------- #
# A retry replays answered turns and pays for none of them again
# --------------------------------------------------------------------------- #


def test_a_retry_replays_answered_turns_without_paying_twice(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents = ScriptedInvestigator(ANSWERS)
    runtime = directed(research, agents)
    w = worker(research, database_url, store, build, runtime)
    run_id = start_web(research)
    built = agent_directed_module.turn_input
    lost: list[int] = []

    def turn_input(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = built(*args, **kwargs)
        if payload["task"]["subject"]["text"] == Q1 and payload["turn"] == 3 and not lost:
            lost.append(3)
            _take_the_lease(research)  # between turns: the next request is never sent
        return payload

    monkeypatch.setattr(agent_directed_module, "turn_input", turn_input)
    drain(w)
    with research.sessions() as session:
        WorkQueue(session).recover_expired_attempts(now=datetime.now(UTC) + timedelta(hours=1))
        session.commit()
    drain(w)

    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    assert [a["status"].value for a in run["steps"][1]["attempts"]] == ["EXPIRED", "SUCCEEDED"]
    # Every Q1 turn asked exactly once: turns 1 and 2 were replayed, not bought again.
    assert agents.turns_of(Q1) == [1, 2, 3, 4, 5]
    replayed = [
        (e["payload"]["turn"], e["payload"]["replayed"])
        for e in turn_events(research, run_id)
        if e["payload"]["track_id"] == tid(QS, Q1, W)
    ]
    assert replayed == [
        (1, False),
        (2, False),
        (1, True),
        (2, True),
        (3, False),
        (4, False),
        (5, False),
    ]
    # Nothing a replayed turn sent was sent again; the news, opened in turn 2 by the
    # lost attempt, is still a cache hit in turn 3.
    assert directed_run_searches(runtime) == 7
    retrieval = runtime.retrieval
    assert retrieval is not None
    assert (
        retrieval.fetcher._transport.calls.count(  # type: ignore[attr-defined]
            "https://zpravy-dr.example/trh-napoju"
        )
        == 1
    )
    tracks = {t.track_id: t for t in bundle.tracks}
    assert (tracks[tid(QS, Q1, W)].status, tracks[tid(QS, Q1, W)].stop_reason) == (
        TrackStatus.COMPLETED,
        StopReason.AGENT_FINISHED,
    )
    assert bundle.counts["model_requests"] == len(agents.requests)


def test_an_action_sent_before_its_turn_was_recorded_is_not_sent_again(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The window between a turn's answer and its record: the answer is replayed, and
    an action the lost attempt sent is reported, never resent (its result is unknown)."""
    agents = ScriptedInvestigator(ANSWERS)
    runtime = directed(research, agents)
    w = worker(research, database_url, store, build, runtime)
    run_id = start_web(research)
    put = agent_directed_module.AgentDirectedTrack._put
    lost: list[int] = []

    def interrupted(self: Any, kind: str, key: str, payload: Any) -> None:
        mine = kind == "turn" and payload.turn == 2 and payload.track_id == tid(QS, Q1, W)
        if mine and not lost:
            lost.append(2)
            _take_the_lease(research)  # the turn's record is never written
        put(self, kind, key, payload)

    monkeypatch.setattr(agent_directed_module.AgentDirectedTrack, "_put", interrupted)
    drain(w)
    with research.sessions() as session:
        WorkQueue(session).recover_expired_attempts(now=datetime.now(UTC) + timedelta(hours=1))
        session.commit()
    drain(w)

    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    # Turn 2 was answered once and its answer replayed; its open was not sent again.
    assert agents.turns_of(Q1).count(2) == 1
    third = agents.payload(Q1, 3)
    [skipped] = [a for a in third["last_turn"] if a.get("ref") == "R1"]
    assert (skipped["decision"], skipped["reason"]) == ("skipped", "sent_by_an_earlier_attempt")
    events = track_events(research, run_id, tid(QS, Q1, W))
    news = [
        e
        for e in events
        if e["payload"]["outcome"] == ToolOutcome.DISPATCHED.value
        and e["payload"]["tool"] == "web_fetch"
    ]
    # Turn 2's open of the news was dispatched once, by the lost attempt. Its page was
    # never held, so the news has no S ref and its link no L ref: turn 3's open of L1
    # is refused, and its open of R1 -- a new action, chosen again -- fetches it.
    assert [e["payload"]["request_fingerprint"] for e in news] == [
        hashlib.sha256(b"https://zpravy-dr.example/trh-napoju").hexdigest()
    ] * 2
    assert news[0]["attempt_id"] != news[1]["attempt_id"]
    [link] = [a for a in agents.payload(Q1, 4)["last_turn"] if a.get("ref") == "L1"]
    assert link["reason"] == "unknown_ref"
    q1 = {t.track_id: t for t in bundle.tracks}[tid(QS, Q1, W)]
    assert q1.status is TrackStatus.COMPLETED


def directed_run_searches(runtime: DeepResearchRuntime) -> int:
    retrieval = runtime.retrieval
    assert retrieval is not None and isinstance(retrieval.search, RecordedSearch)
    return len(retrieval.search.calls)


# --------------------------------------------------------------------------- #
# The transcript, and a later pass
# --------------------------------------------------------------------------- #


def stored(world: ResearchWorld, store: InMemoryArtifactStore, artifact_id: str) -> Any:
    with world.sessions() as session:
        return research_artifacts(session, world.lead_scope(session), store).read_json(artifact_id)


def track_result(
    world: ResearchWorld, store: InMemoryArtifactStore, run_id: str, track: str
) -> dict[str, Any]:
    _run, bundle = read(world, run_id, store)
    entry = {t.track_id: t for t in bundle.tracks}[track]
    result: dict[str, Any] = stored(world, store, entry.artifact_id)
    return result


def test_every_turn_action_and_decision_is_in_the_track_s_transcript(
    directed_run: Directed, store: InMemoryArtifactStore
) -> None:
    world, run_id = directed_run.world, directed_run.run_id
    result = track_result(world, store, run_id, tid(QS, Q1, W))
    transcript = stored(world, store, result["transcript_artifact_id"])
    assert transcript["kind"] == "deep_research_transcript"
    assert transcript["version"] == INVESTIGATOR_VERSION
    assert (transcript["status"], transcript["stop_reason"]) == ("COMPLETED", "agent_finished")
    assert [t["turn"] for t in transcript["turns"]] == [1, 2, 3, 4, 5]
    decisions = [
        [(a["kind"], a["decision"], a.get("reason")) for a in t["actions"]]
        for t in transcript["turns"]
    ]
    assert decisions == [
        [("search", "sent", None)] * 3,
        [("open", "sent", None), ("open", "refused", "unknown_ref")],
        [("open", "sent", None), ("open", "cached", None)],
        [("read", "served_locally", None), ("search", "sent", None)],
        [("finish", "finished", None)],
    ]
    purposes = [a["purpose"] for a in transcript["turns"][2]["actions"]]
    assert purposes == ["tabulka, ze které číslo pochází", "znovu zpráva"]
    assert [r["ref"] for r in transcript["results"]] == ["R1", "R2", "R3", "R4"]
    assert [(s["ref"], s["host"], s["tier"]) for s in transcript["sources"]] == [
        ("S1", "zpravy-dr.example", "T4"),
        ("S2", "stat-dr.example", "T1"),
    ]
    assert [link["ref"] for link in transcript["links"]] == ["L1"]
    assert transcript["counts"] == {
        "turns": 5,
        "turns_replayed_answer": 0,
        "actions": 10,
        "sent": 6,
        "cached": 1,
        "served_locally": 1,
        "refused": 1,
        "skipped": 0,
        "finished": 1,
        "searches": 4,
        "opens": 4,
        "reads": 1,
        "grounded": 1,
        "quarantined": 2,
    }
    assert transcript["turns"][3]["grounded"] == [e["evidence_id"] for e in result["evidence"]]


def test_a_later_pass_reuses_completed_tracks_with_their_transcripts_at_no_cost(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    agents = ScriptedInvestigator(ANSWERS)
    runtime = directed(research, agents)
    w = worker(research, database_url, store, build, runtime)
    first = start_web(research)
    assert drain(w) == 6
    before = len(agents.requests)
    searched = len(directed_run_search(runtime).calls)
    second = start_web(research, DESIGN_2)
    assert drain(w) == 6
    _run, bundle = read(research, second, store)
    tracks = {t.track_id: t for t in bundle.tracks}
    assert {k for k, t in tracks.items() if t.reused} == {
        tid(QS, Q1, W),
        tid(QS, Q2, W),
        tid(OS, ALMOND, W),
    }
    # The same stored result and the same transcript, bought by the first run.
    for track in (tid(QS, Q1, W), tid(QS, Q2, W)):
        assert (
            track_result(research, store, second, track)["transcript_artifact_id"]
            == track_result(research, store, first, track)["transcript_artifact_id"]
        )
    # Bought now: the plan, the new object's one turn and the oats track again (it was
    # INCOMPLETE, never reused), and the review of what is new.
    bought = Counter(RecordedAgents._role(r) for r in agents.requests[before:])
    assert bought["investigator"] == 2 and bought["planner"] == 1
    assert agents.turns_of(SOY) == [1]
    assert len(directed_run_search(runtime).calls) == searched + 2  # the oats track's two
    assert bundle.counts["tracks_reused"] == 3


def directed_run_search(runtime: DeepResearchRuntime) -> RecordedSearch:
    retrieval = runtime.retrieval
    assert retrieval is not None and isinstance(retrieval.search, RecordedSearch)
    return retrieval.search


# --------------------------------------------------------------------------- #
# The switch
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", ["maybe", "2", "yes please"])
def test_the_switch_is_read_strictly_and_needs_deep_research(
    research: ResearchWorld,  # noqa: F811
    value: str,
) -> None:
    settings = ai_settings(research.client_id, approved_for=TEST_ROUTE)
    with pytest.raises(AIRuntimeConfigError, match="AIA_DEEP_RESEARCH_AGENT_DIRECTED"):
        deep_research_runtime(
            settings,
            env={"AIA_DEEP_RESEARCH_ENABLED": "true", "AIA_DEEP_RESEARCH_AGENT_DIRECTED": value},
            transport=ScriptedInvestigator(ANSWERS),
            signer=Signer(),
        )
    with pytest.raises(AIRuntimeConfigError, match="needs AIA_DEEP_RESEARCH_ENABLED"):
        deep_research_runtime(None, env={"AIA_DEEP_RESEARCH_AGENT_DIRECTED": "true"})


def test_the_switch_is_off_unless_set_and_on_records_the_mode(
    research: ResearchWorld,  # noqa: F811
) -> None:
    settings = ai_settings(research.client_id, approved_for=TEST_ROUTE)

    def runtime(env: dict[str, str]) -> DeepResearchRuntime:
        built = deep_research_runtime(
            settings,
            env={"AIA_DEEP_RESEARCH_ENABLED": "true", **env},
            transport=ScriptedInvestigator(ANSWERS),
            signer=Signer(),
        )
        assert built is not None
        return built

    for env in (
        {},
        {"AIA_DEEP_RESEARCH_AGENT_DIRECTED": ""},
        {"AIA_DEEP_RESEARCH_AGENT_DIRECTED": "false"},
    ):
        off = runtime(env)
        assert off.config.agent_directed is False and "investigator" not in off.versions()
    on = runtime({"AIA_DEEP_RESEARCH_AGENT_DIRECTED": "true"})
    assert on.config.agent_directed is True
    assert on.versions()["investigator"] == INVESTIGATOR_VERSION
    # The switch adds no retrieval: what may leave is the composition's, unchanged.
    assert on.retrieval is None
    assert deep_research_runtime(None, env={}) is None


# --------------------------------------------------------------------------- #
# Mode off: the planned journey, byte for byte
# --------------------------------------------------------------------------- #

#: Pass one of ``test_deep_research_journey.py`` as feature/dr-agents-base @ a6338c3
#: sent it, before the agent-directed mode existed: the planner's and the web
#: investigators' request bodies exactly; every request with the random knowledge
#: item ids and the evidence ids taken from them masked; and the tool journal as
#: (tool, outcome, request fingerprint). Computed on that commit by this file's
#: digests; the mode off must reproduce them.
PLANNED_WEB_REQUESTS = "1017ad3dc20c686bd75ef42060f29c88bcd2b2e480cf684617600890e5c37bf1"
PLANNED_ALL_REQUESTS = "513c447086654ec5bc2982bbf1111fb290c54f588d5cffc2f453a18cfb3d5fc9"
PLANNED_TOOL_JOURNAL = "6ee0ced884929d5e127b81601bcedfcd64f439813477bb780242845a39aac605"


def test_with_the_mode_off_the_planned_journey_is_byte_for_byte_unchanged(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    requests = pass_one.agents.requests
    web = [r.body for r in requests if RecordedAgents._role(r) in {"planner", "web_investigator"}]
    assert len(web) == 5
    assert hashlib.sha256(canonical_json(web).encode()).hexdigest() == PLANNED_WEB_REQUESTS
    masked = re.sub(
        r"(KNW-[0-9a-f]+@|EV-[0-9a-f]{16})", "ID", canonical_json([r.body for r in requests])
    )
    assert hashlib.sha256(masked.encode()).hexdigest() == PLANNED_ALL_REQUESTS
    journal = [
        (e["payload"]["tool"], e["payload"]["outcome"], e["payload"]["request_fingerprint"])
        for e in tool_events(pass_one.world, pass_one.run_id)
    ]
    assert len(journal) == 30
    assert hashlib.sha256(json.dumps(journal).encode()).hexdigest() == PLANNED_TOOL_JOURNAL
    assert "investigator" not in pass_one.runtime.versions()
    assert pass_one.runtime.inputs().investigator is None
    assert pass_one.agents.roles()["investigator"] == 0
    # No planned track has a transcript, nor a key for one in its stored form.
    blobs = [store.get(key).decode("utf-8") for key in store.keys]
    assert not any('"transcript_artifact_id"' in b or "deep_research_turn" in b for b in blobs)
    assert (
        deep_research_package.DeepResearchConfig.__dataclass_fields__["agent_directed"].default
        is False
    )
