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
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.research import research_artifacts
from aia_core.domain.ai_contracts import canonical_json
from aia_core.domain.deep_research.brief import BRIEF_VERSION, ResearchBrief, uncited_numbers
from aia_core.domain.deep_research.confidence import (
    CONFIDENCE_WEIGHTS_V1,
    ConflictState,
    Provenance,
    Recency,
)
from aia_core.domain.deep_research.contracts import (
    Channel,
    QuarantineReason,
    QueryDecision,
    StopReason,
    SubjectKind,
    TrackStatus,
    subject_key,
)
from aia_core.domain.deep_research.gaps import AcquisitionReason, GapKind
from aia_core.domain.deep_research.investigator import INVESTIGATOR_VERSION
from aia_core.domain.deep_research.quarantine import design_input
from aia_core.domain.deep_research.reputation import (
    REPUTATION_REGISTER_V1,
    Publisher,
    RegisterStatus,
    ReputationRegister,
)
from aia_core.domain.deep_research.sources import SourceClass, SourceTier
from aia_core.domain.deep_research.synthesis import SynthesisStatus
from aia_core.domain.deep_research.tooling import ToolOutcome
from aia_core.domain.deep_research.triangulation import ConflictStatus
from aia_core.domain.deep_research.verification import VERIFICATION_RULES_VERSION
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import (
    ClientKnowledgeItemRow,
    ClientKnowledgeProposalRow,
    ClientKnowledgeRevisionRow,
)
from aia_core.infrastructure.web_retrieval import RecordedSearch
from aia_core.infrastructure.workflow_repository import WorkQueue
from aia_executors import deep_research as deep_research_package
from aia_executors.ai_runtime import AIRuntimeConfigError, build_gateway
from aia_executors.deep_research import DeepResearchConfig, DeepResearchRuntime
from aia_executors.deep_research import agent_directed as agent_directed_module
from aia_executors.deep_research_recorded import recorded_runtime
from aia_executors.deep_research_runtime import deep_research_runtime
from sqlalchemy import func, select
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
    approve_knowledge,
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


def faithful_brief(payload: dict[str, Any]) -> dict[str, Any]:
    """A brief that keeps every rule: each subject's first claim, citing its finding."""
    first: dict[str, dict[str, Any]] = {}
    for f in payload["findings"]:
        first.setdefault(f["subject_key"], f)
    return {
        "summary": next(iter(first.values()))["claim"] if first else "Bez zjištění.",
        "answers": [
            {"subject_key": k, "text": f["claim"], "evidence_ids": [f["evidence_id"]]}
            for k, f in first.items()
        ],
        "conflict_notes": [
            {"conflict_id": c["conflict_id"], "text": "Hodnoty se liší; zdroje uvádějí obě."}
            for c in payload["conflicts"]
        ],
        "limitations": ["Zjištění jsou z veřejných zdrojů, ne z panelu."],
    }


@dataclass
class ScriptedInvestigator(RecordedAgents):
    """The recorded agents, and an investigator answering from its script by subject and turn."""

    turns: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: TURNS)
    #: Every investigator payload it was sent, by (subject, turn), in order.
    shown: list[tuple[str, int, dict[str, Any]]] = field(default_factory=list)
    #: The independent verifier's answers by claim, over "supported" (chunk 12).
    judged: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Every item the independent verifier was shown, in order.
    verified: list[dict[str, Any]] = field(default_factory=list)
    #: The brief synthesizer's answers in order (chunk 13), each built from its payload;
    #: past the end of the list, :func:`faithful_brief`.
    briefs: list[Callable[[dict[str, Any]], dict[str, Any]]] = field(default_factory=list)
    #: Every payload the brief synthesizer was sent, in order.
    brief_payloads: list[dict[str, Any]] = field(default_factory=list)

    def _brief_synthesizer(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.brief_payloads.append(payload)
        n = len(self.brief_payloads)
        return (self.briefs[n - 1] if n <= len(self.briefs) else faithful_brief)(payload)

    def _independent_verifier(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.verified.extend(payload["items"])
        return {
            "judgements": [
                {
                    "evidence_id": i["evidence_id"],
                    "verdict": "supported",
                    "attacks": [],
                    "superseded_by": None,
                    "search": None,
                    "reason": "posouzeno podle citace a měr",
                    **self.judged.get(i["claim"], {}),
                }
                for i in payload["items"]
            ]
        }

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


#: The fictional publishers of the recorded web, as a register names them.
REGISTER = ReputationRegister(
    version="test-register-dr-1",
    status=RegisterStatus.PROPOSED,
    publishers=(
        Publisher(
            "Statistický úřad DR",
            ("SÚDR",),
            ("stat-dr.example",),
            SourceClass.OFFICIAL_STATISTICS,
            SourceTier.T1,
            ("datastat",),
        ),
    ),
)


def directed(
    world: ResearchWorld,
    agents: RecordedAgents,
    *,
    agent_directed: bool = True,
    fixture: Path = WEB,
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
        fixture=fixture,
        env={"AIA_ENV": "test"},
        register=REGISTER if agent_directed else None,
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


def test_a_turn_that_proposes_nothing_ends_its_track(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    quiet = {**TURNS, ALMOND: [{"evidence": [], "summary": "", "leads": [], "next": []}]}
    agents = ScriptedInvestigator(ANSWERS, turns=quiet)
    run_id = start_web(research)
    assert drain(worker(research, database_url, store, build, directed(research, agents))) == 6
    _run, bundle = read(research, run_id, store)
    almond = {t.track_id: t for t in bundle.tracks}[tid(OS, ALMOND, W)]
    assert (almond.status, almond.stop_reason) == (
        TrackStatus.COMPLETED,
        StopReason.AGENT_FINISHED,
    )
    assert almond.detail == "the turn proposed no action"
    assert agents.turns_of(ALMOND) == [1]


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
        "ladders": 0,
        "acquired": 0,
        "acquisition_gaps": 0,
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


# --------------------------------------------------------------------------- #
# Verification (chunk 12): the independent verifier, decided by code
# --------------------------------------------------------------------------- #

TABLE_CLAIM = (
    "Spotřeba rostlinných nápojů v Česku vzrostla v roce 2025 o 12,5 % na 41 milionů litrů."
)


def verify_record(store: InMemoryArtifactStore) -> dict[str, Any]:
    """The run's verify record, as stored."""
    records = [
        record
        for key in store.keys
        if isinstance(record := json.loads(store.get(key).decode("utf-8")), dict)
        and record.get("kind") == "deep_research_verify"
    ]
    assert len(records) == 1
    return records[0]


def test_the_independent_verifier_reviews_each_candidate_with_its_measures_and_source(
    directed_run: Directed, store: InMemoryArtifactStore
) -> None:
    agents = directed_run.agents
    roles = agents.roles()
    assert roles["independent_verifier"] == 1 and roles["verifier"] == 0
    [shown] = agents.verified
    assert shown["claim"] == TABLE_CLAIM
    # What it is shown: the measures code normalised and the source's trace, never the
    # investigator's reasoning or its opinion of its source.
    assert [(m["value"], m.get("unit"), m.get("period")) for m in shown["measures"]] == [
        (12.5, "%", "Y2025"),
        (41.0, "l", "Y2025"),
    ]
    assert shown["source"]["publisher"] == "Statistický úřad DR"
    assert shown["source"]["primary"] == "primary"
    assert "source_quality" not in json.dumps(shown) and "summary" not in shown
    review = verify_record(store)["review"]
    assert review["rules_version"] == VERIFICATION_RULES_VERSION
    assert review["register_version"] == "test-register-dr-1"
    [trace] = review["traces"]
    assert (trace["status"], trace["publisher_name"]) == ("primary", "Statistický úřad DR")
    assert review["conflicts"] == [] and review["resolve_requests"] == []
    assert review["supersessions"] == [] and review["primary_leads"] == []
    _run, bundle = read(directed_run.world, directed_run.run_id, store)
    [accepted] = [a for a in bundle.accepted if a.evidence.claim == TABLE_CLAIM]
    assert accepted.confirmations == ()
    assert bundle.versions["verification"] == VERIFICATION_RULES_VERSION
    assert bundle.versions["register"] == "test-register-dr-1"


@pytest.mark.parametrize(
    ("judgement", "reason", "detail"),
    [
        (
            {"verdict": "overstated", "attacks": ["overstated_generalisation"]},
            QuarantineReason.OVERSTATED_BY_VERIFIER,
            "overstated_generalisation",
        ),
        (
            # A newer figure named that the run never captured: code does not accept it.
            {"verdict": "superseded", "superseded_by": "EV-0000000000000000"},
            QuarantineReason.UNVERIFIED,
            "cannot accept",
        ),
    ],
)
def test_the_verifier_s_verdict_is_applied_by_code(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    judgement: dict[str, Any],
    reason: QuarantineReason,
    detail: str,
) -> None:
    agents = ScriptedInvestigator(ANSWERS, judged={TABLE_CLAIM: judgement})
    runtime = directed(research, agents)
    run_id = start_web(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    assert not [a for a in bundle.accepted if a.evidence.claim == TABLE_CLAIM]
    [q] = [q for q in bundle.quarantined if q.claim == TABLE_CLAIM]
    assert q.reason is reason and detail in q.detail


def test_a_proposed_search_is_recorded_as_a_lead_and_nothing_is_sent(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    search = {"query": "spotřeba rostlinných nápojů 2026", "publisher": "SÚDR", "why": "novější"}
    agents = ScriptedInvestigator(ANSWERS, judged={TABLE_CLAIM: {"search": search}})
    runtime = directed(research, agents)
    start_web(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    searched = len(directed_run_search(runtime).calls)
    [lead] = verify_record(store)["review"]["verifier_leads"]
    assert (lead["query"], lead["publisher"]) == (search["query"], "Statistický úřad DR")
    assert search["query"] not in directed_run_search(runtime).calls
    assert searched == 7  # the investigators' searches only


def test_the_planned_mode_never_asks_the_independent_verifier(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    assert pass_one.agents.roles()["independent_verifier"] == 0
    assert pass_one.agents.roles()["verifier"] > 0
    assert "verification" not in pass_one.runtime.versions()
    assert pass_one.runtime.register is None
    blobs = [store.get(key).decode("utf-8") for key in store.keys]
    assert not any('"judgements"' in b or "deep_research_verification_review" in b for b in blobs)


def test_the_composition_gives_the_register_to_the_agent_directed_mode_only(
    research: ResearchWorld,  # noqa: F811
) -> None:
    settings = ai_settings(research.client_id, approved_for=TEST_ROUTE)

    def runtime(directed_value: str) -> DeepResearchRuntime:
        built = deep_research_runtime(
            settings,
            env={
                "AIA_DEEP_RESEARCH_ENABLED": "true",
                "AIA_DEEP_RESEARCH_AGENT_DIRECTED": directed_value,
            },
            transport=ScriptedInvestigator(ANSWERS),
            signer=Signer(),
        )
        assert built is not None
        return built

    off, on = runtime("false"), runtime("true")
    assert off.register is None and "register" not in off.versions()
    assert on.register is REPUTATION_REGISTER_V1
    assert on.versions()["register"] == REPUTATION_REGISTER_V1.version
    assert on.versions()["verification"] == VERIFICATION_RULES_VERSION


# --------------------------------------------------------------------------- #
# Confidence, gaps and the brief (chunk 13)
# --------------------------------------------------------------------------- #

SVAZ = "https://svaz-dr.example/spotreba"
PAYWALL = "https://placeny-dr.example/studie"
SVAZ_QUOTE = "Spotřeba rostlinných nápojů v Česku činila v roce 2025 podle svazu 38 milionů litrů."


def brief_of(world: ResearchWorld, run_id: str, store: InMemoryArtifactStore) -> ResearchBrief:
    _run, bundle = read(world, run_id, store)
    assert bundle.synthesis is not None and bundle.synthesis.brief is not None
    return bundle.synthesis.brief


def synthesis_record(store: InMemoryArtifactStore) -> dict[str, Any]:
    [record] = [
        r
        for key in store.keys
        if isinstance(r := json.loads(store.get(key).decode("utf-8")), dict)
        and r.get("kind") == "deep_research_synthesis"
    ]
    return record


def wider_web(tmp: Path) -> Path:
    """The recorded web, and a trade association's figure and a paywalled study."""
    data = json.loads(WEB.read_text(encoding="utf-8"))
    data["source_classes"]["svaz-dr.example"] = "INDUSTRY_RESEARCH"
    data["hosts"]["svaz-dr.example"] = ["93.184.215.14"]
    data["hosts"]["placeny-dr.example"] = ["93.184.215.14"]
    data["search"]["spotřeba rostlinných nápojů svaz"] = {
        "hits": [
            {"url": SVAZ, "title": "Spotřeba podle svazu", "snippet": "Svaz výrobců."},
            {"url": PAYWALL, "title": "Studie trhu nápojů", "snippet": "Placená studie."},
        ],
        "request_id": "rec-s-svaz",
    }
    data["pages"][SVAZ] = {
        "body": "<html><head><title>Spotřeba podle svazu</title></head><body><p>"
        + SVAZ_QUOTE
        + "</p></body></html>"
    }
    data["pages"][PAYWALL] = {"status": 402, "body": ""}
    path = tmp / "investigator_web_wider.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


#: The almond track, finding the association's figure (an open conflict with the
#: official table's 41) and meeting a paywall.
ALMOND_WIDER: list[dict[str, Any]] = [
    {
        "evidence": [],
        "summary": "",
        "leads": [],
        "next": [
            {
                "kind": "search",
                "query": "spotřeba rostlinných nápojů svaz",
                "site": None,
                "phrase": None,
                "lang": "cs",
                "purpose": "najít zdroje",
            }
        ],
    },
    {
        "evidence": [],
        "summary": "",
        "leads": [],
        "next": [
            {"kind": "open", "ref": "R1", "purpose": "údaj svazu"},
            {"kind": "open", "ref": "R2", "purpose": "studie trhu"},
        ],
    },
    {
        "evidence": [
            {
                "source_id": "S1",
                "quote": SVAZ_QUOTE,
                "claim": SVAZ_QUOTE,
                "evidence_type": "industry_report",
                "measures": [
                    {
                        "value": 38,
                        "scale": 1000000,
                        "unit": "litrů",
                        "period": "2025",
                        "geography": "Česko",
                        "measure_name": "spotřeba rostlinných nápojů",
                    }
                ],
            }
        ],
        "summary": "Svaz uvádí jiný údaj.",
        "leads": [],
        "next": [
            {
                "kind": "finish",
                "gaps": [
                    {"need": "cena mandlového nápoje", "why": "studie je placená", "tried": "R2"}
                ],
            }
        ],
    },
]


def wider_run(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    tmp_path: Path,
    **agent_fields: Any,
) -> tuple[ScriptedInvestigator, str]:
    turns = {**TURNS, ALMOND: ALMOND_WIDER}
    agents = ScriptedInvestigator(ANSWERS, turns=turns, **agent_fields)
    runtime = directed(research, agents, fixture=wider_web(tmp_path))
    run_id = start_web(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    return agents, run_id


def test_the_brief_carries_findings_with_confidence_by_code_and_its_gaps(
    directed_run: Directed, store: InMemoryArtifactStore
) -> None:
    world, agents = directed_run.world, directed_run.agents
    run, bundle = read(world, directed_run.run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    brief = brief_of(world, directed_run.run_id, store)
    # The brief synthesizer wrote it, once; the planned synthesizer was never asked.
    roles = agents.roles()
    assert roles["brief_synthesizer"] == 1 and roles["synthesizer"] == 0
    assert bundle.counts["model_requests"] == len(agents.requests)
    assert bundle.versions["brief"] == BRIEF_VERSION
    assert bundle.versions["confidence_weights"] == CONFIDENCE_WEIGHTS_V1.version
    assert brief.status is SynthesisStatus.COMPLETE and brief.repair is None
    # Each finding with its measures, source, tier, provenance and code's confidence.
    [finding] = brief.findings
    assert finding.claim == TABLE_CLAIM
    assert finding.tier is SourceTier.T1 and finding.provenance is Provenance.PRIMARY
    assert finding.publisher == "Statistický úřad DR"
    assert finding.measures_text == ("12,5 % Y2025 CZ", "41 mil. l Y2025 CZ")
    record = finding.confidence
    assert record.weights_version == CONFIDENCE_WEIGHTS_V1.version
    assert record.inputs.recency is Recency.CURRENT
    assert record.value == round(sum(record.terms.values()), 3)
    # The synthesizer saw the band only, and no agent's rating.
    [payload] = agents.brief_payloads
    assert payload["findings"][0]["confidence"] == record.band.value
    assert "source_quality" not in json.dumps(payload)
    # Gaps: Q1's stated gap, Q2 and the oats unanswered (with why), the almond's stated one.
    gaps = {(g.kind, g.subject_key): g for g in brief.gaps}
    q1, q2 = subject_key(QS, Q1), subject_key(QS, Q2)
    oats, almond = subject_key(OS, OATS), subject_key(OS, ALMOND)
    assert gaps[(GapKind.STATED, q1)].need == "údaj za rok 2024 pro srovnání"
    assert gaps[(GapKind.STATED, q1)].tried == "tabulka úřadu, metodika"
    assert "repeated_refusals" in gaps[(GapKind.UNANSWERED, q2)].reason
    assert "tool_outcome_uncertain" in gaps[(GapKind.UNANSWERED, oats)].reason
    assert gaps[(GapKind.STATED, almond)].need == "cena mandlového nápoje"
    # Q1's lead to the office's table named no registered publisher: recorded, unpursued.
    [lead] = brief.acquisition_gaps
    assert lead.title == "Tabulka spotřeby za rok 2025" and lead.raised_by == "investigator_lead"
    assert lead.reason is AcquisitionReason.NOT_PURSUED and lead.ladder_version is None
    assert uncited_numbers(brief, bundle.subjects) == ()


def test_a_conflict_and_a_paywalled_source_reach_the_brief(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    tmp_path: Path,
) -> None:
    _agents, run_id = wider_run(research, database_url, store, build, tmp_path)
    brief = brief_of(research, run_id, store)
    # Both sides of the conflict, its cause, a note citing only their numbers.
    [shown] = brief.conflicts
    assert sorted(s.measure.value for s in shown.conflict.sides) == [38.0, 41.0]
    assert shown.conflict.cause.value == "unexplained"
    assert shown.conflict.status is ConflictStatus.OPEN
    assert shown.note is not None and shown.note_refused is None
    [gap] = [g for g in brief.gaps if g.kind is GapKind.CONFLICT]
    assert gap.conflict_id == shown.conflict.conflict_id
    # Standing in an open conflict lowers both findings' confidence by code.
    assert {f.confidence.inputs.conflict for f in brief.findings} == {ConflictState.OPEN}
    svaz = next(f for f in brief.findings if f.source_url == SVAZ)
    table = next(f for f in brief.findings if f.claim == TABLE_CLAIM)
    assert svaz.tier is SourceTier.T3 and table.confidence.value > svaz.confidence.value
    # The paywalled study: an acquisition gap with its reason and the attempt.
    [paid] = [g for g in brief.acquisition_gaps if g.raised_by == "refused_open"]
    assert paid.reason is AcquisitionReason.PAYWALL and paid.url == PAYWALL
    assert paid.title == "Studie trhu nápojů" and paid.publisher == "placeny-dr.example"
    assert [r.outcome for r in paid.rungs_tried] == ["http_402"]
    assert "platební bránou" in paid.how_to_obtain
    _run, bundle = read(research, run_id, store)
    assert uncited_numbers(brief, bundle.subjects) == ()


def _corrupt(payload: dict[str, Any]) -> dict[str, Any]:
    """Every answer states a number no cited finding carries."""
    answer = faithful_brief(payload)
    answer["answers"] = [
        {**a, "text": a["text"] + " Do roku 2030 trh vzroste o 99 %."} for a in answer["answers"]
    ]
    return answer


def test_a_draft_with_an_uncited_number_is_repaired_once(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    agents = ScriptedInvestigator(ANSWERS, briefs=[_corrupt])
    runtime = directed(research, agents)
    run_id = start_web(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    brief = brief_of(research, run_id, store)
    assert agents.roles()["brief_synthesizer"] == 2
    first, again = agents.brief_payloads
    assert "problems" not in first
    assert again["problems"][0]["reason"] == "number_not_in_cited_evidence"
    assert "99" in again["problems"][0]["detail"]
    assert again["previous"]["answers"][0]["text"].endswith("o 99 %.")
    assert brief.status is SynthesisStatus.COMPLETE and brief.excluded == ()
    assert brief.repair is not None and brief.repair.refused is None
    # The answer, and the summary that used the numbers only that answer cited.
    assert [p.reason for p in brief.repair.problems] == [
        "number_not_in_cited_evidence",
        "summary_withheld",
    ]
    # Both requests are metered and counted.
    assert synthesis_record(store)["repair_call"]["role"] == "brief_synthesizer"
    _run, bundle = read(research, run_id, store)
    assert bundle.counts["model_requests"] == len(agents.requests)


def test_a_draft_still_wrong_after_its_repair_is_refused_explicitly(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    agents = ScriptedInvestigator(ANSWERS, briefs=[_corrupt, _corrupt, _corrupt])
    runtime = directed(research, agents)
    run_id = start_web(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    brief = brief_of(research, run_id, store)
    assert agents.roles()["brief_synthesizer"] == 2  # one repair, never a third draft
    assert brief.status is SynthesisStatus.BLOCKED and brief.answers == ()
    assert [e.reason for e in brief.excluded] == ["number_not_in_cited_evidence"]
    assert "99" in brief.excluded[0].detail
    # Nothing uncited is published; code's parts stand.
    assert uncited_numbers(brief, bundle.subjects) == ()
    assert [f.claim for f in brief.findings] == [TABLE_CLAIM]
    assert bundle.synthesis is not None
    assert bundle.synthesis.check.status is SynthesisStatus.BLOCKED


#: The official table's confidence by code, term by term, under the proposed weights:
#: T1, primary, no other independent group, supported, no conflict, a 2025 period read
#: in 2026, the least final basis unstated, the least complete measure 3 of 7 stated.
TABLE_TERMS = {
    "tier": 0.45,
    "provenance": 0.15,
    "confirmations": 0.0,
    "verdict": 0.12,
    "superseded": 0.0,
    "conflict": 0.0,
    "recency": 0.08,
    "basis": -0.02,
    "completeness": round(0.05 * 3 / 7, 6),
}


@pytest.mark.parametrize("quality", [0.0, 0.5, 1.0])
def test_the_investigator_s_own_source_quality_changes_no_confidence(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    quality: float,
) -> None:
    turns = json.loads(json.dumps(TURNS))
    for subject in turns.values():
        for turn in subject:
            for e in turn["evidence"]:
                e["source_quality"] = quality
    agents = ScriptedInvestigator(ANSWERS, turns=turns)
    runtime = directed(research, agents)
    run_id = start_web(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    _run, bundle = read(research, run_id, store)
    # Recorded as the agent said it, and nothing more: the same confidence for every rating.
    assert [a.evidence.agent_source_quality for a in bundle.accepted] == [quality]
    [finding] = brief_of(research, run_id, store).findings
    assert finding.confidence.terms == TABLE_TERMS
    assert finding.confidence.value == 0.801


def _knowledge_rows(world: ResearchWorld) -> tuple[int, int, int]:
    with world.sessions() as session:
        return (
            session.scalar(select(func.count()).select_from(ClientKnowledgeItemRow)) or 0,
            session.scalar(select(func.count()).select_from(ClientKnowledgeRevisionRow)) or 0,
            session.scalar(select(func.count()).select_from(ClientKnowledgeProposalRow)) or 0,
        )


def test_client_knowledge_and_the_accepted_sources_are_unchanged_by_the_brief(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    tmp_path: Path,
) -> None:
    approve_knowledge(research)
    before = _knowledge_rows(research)
    _agents, run_id = wider_run(
        research, database_url, store, build, tmp_path, briefs=[_corrupt, _corrupt]
    )
    # The brief proposes and writes nothing to Client Knowledge, even when it is blocked.
    assert _knowledge_rows(research) == before
    # Confidence is an annotation, never a gate: the bundle's accepted sources are the
    # verify step's, item for item, whatever the brief's status or the confidence.
    _run, bundle = read(research, run_id, store)
    brief = brief_of(research, run_id, store)
    assert brief.status is SynthesisStatus.BLOCKED
    verified = verify_record(store)["accepted"]
    assert [a.model_dump(mode="json") for a in bundle.accepted] == verified
    assert {f.evidence_id for f in brief.findings} == {
        a["evidence"]["evidence_id"] for a in verified
    }
    assert any(f.confidence.band.value != "high" for f in brief.findings)
    design = design_input(bundle)
    assert sorted(f.evidence_id for fs in design.findings.values() for f in fs) == sorted(
        a.evidence.evidence_id for a in bundle.accepted
    )
