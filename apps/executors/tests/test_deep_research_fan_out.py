"""Deep Research fan-out in process: tracks in steps of their own find what one step finds.

Plan ``deep-research-web-search.md`` chunk 21; ``docs/architecture/deep-research-fan-out.md``.
The three recorded journeys -- the planned mode (``test_deep_research_journey.py``), the
agent-directed investigator (chunk 9) and the lead researcher (chunk 11) -- run twice in
one world: once with the switch off, once on, over a design whose title differs (so no
track of the first run is reused by the second) and with fresh recorded agents. With the
switch on the ``investigate`` step hands every track that would make a call to a step of
its own and joins them (a lead-planned run wave by wave); the bundle -- every track's
status, stop, counts and queries, every accepted and quarantined finding, the spend --
must be the first run's, and no agent may be asked once more.

Contention across real processes, the limits under load and a worker killed mid-track are
``test_deep_research_fan_out_processes.py``'s (PostgreSQL).
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.contracts import Channel, StopReason, SubjectKind, TrackStatus
from aia_core.domain.deep_research.steps import InvestigationRecord, PlanRecord
from aia_core.domain.deep_research.tooling import TOOL_EVENT_KINDS, ToolOutcome
from aia_core.domain.deep_research.workflow import INVESTIGATE_TRACK_KIND, track_step_key
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import AttemptStatus, StepRunStatus, WorkflowRunStatus
from aia_core.infrastructure.fan_out_coordination import ModelSlots, ModelSlotsBusy
from aia_core.infrastructure.host_pacing import PacedTransport
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.tables import StepRunRow
from aia_core.infrastructure.web_retrieval import RecordedSearch
from aia_core.infrastructure.workflow_repository import WorkQueue
from aia_executors.ai_runtime import AIRuntimeConfigError, AIRuntimeSettings, build_gateway
from aia_executors.ai_step import MODEL_CONCURRENCY_WAIT
from aia_executors.deep_research import DeepResearchConfig, DeepResearchRuntime
from aia_executors.deep_research_recorded import recorded_runtime
from aia_executors.deep_research_runtime import deep_research_runtime
from aia_worker.worker import Worker
from deep_research_fixtures import (
    ANSWERS,
    DESIGN,
    OATS,
    TEST_ROUTE,
    WEB,
    RecordedAgents,
    Signer,
    ai_settings,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from test_deep_research_investigator_journey import (  # type: ignore[import-not-found]
    REGISTER,
    ScriptedInvestigator,
    start_web,
)
from test_deep_research_investigator_journey import WEB as DIRECTED_WEB
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ResearchWorld,
    _take_the_lease,
    approve_knowledge,
    read,
    research,  # noqa: F401  (a fixture)
    start,
    tid,
    tool_events,
    worker,
)
from test_deep_research_lead_journey import ScriptedLead  # type: ignore[import-not-found]

#: The same design under another title: every track fingerprint differs, so nothing the
#: first run stored is reused by the second, and every agent is asked the same things.
FANNED = {**DESIGN, "title": DESIGN["title"] + " (v paralelních krocích)"}


def _settings(world: ResearchWorld, *, lead: bool = False) -> AIRuntimeSettings:
    base = ai_settings(world.client_id, approved_for=TEST_ROUTE)
    fanned = MaterialApproval(
        sha256=material_sha256(FANNED),
        data_class=DataClass.CLASS_C_INTERNAL,
        provenance="generated wholly by this test; class explicitly set",
        synthetic=True,
    )
    return dataclasses.replace(
        base,
        material_approvals=(*base.material_approvals, fanned),
        research_lead_enabled=lead,
    )


def composition(
    world: ResearchWorld,
    agents: RecordedAgents,
    *,
    mode: str,
    fan_out: bool,
    sessions: sessionmaker[Session],
    slots: Any | None = None,
) -> DeepResearchRuntime:
    """A journey's composition (``planned``, ``directed`` or ``lead``), fanned out or not."""
    settings = _settings(world, lead=mode == "lead")
    runtime = recorded_runtime(
        gateway=build_gateway(settings, transport=agents, signer=Signer()),
        config=DeepResearchConfig(
            policy_version=settings.policy_version,
            max_output_tokens=settings.research_max_output_tokens,
            context_window_tokens=settings.context_window_tokens,
            prices=settings.model_prices(),
            fictional_client_ids=settings.fictional_client_ids,
            material_approvals=settings.material_approvals,
            agent_directed=mode != "planned",
            lead=mode == "lead",
            fan_out=fan_out,
        ),
        fixture=WEB if mode == "planned" else DIRECTED_WEB,
        env={"AIA_ENV": "test"},
        register=REGISTER if mode == "directed" else None,
    )
    if fan_out:
        runtime = dataclasses.replace(
            runtime,
            model_slots=slots or ModelSlots(sessions, pool="bedrock:journey", limit=2),
        )
    return runtime


def run_all(w: Worker, *, limit: int = 200) -> list[str]:
    """Run the worker until nothing is claimable: how each attempt ended, in order."""
    endings = []
    for _ in range(limit):
        result = w.run_once()
        if result is None:
            return endings
        endings.append(result.ending)
    raise AssertionError("the worker kept finding work")


def signature(bundle: EvidenceBundle) -> dict[str, Any]:
    """What a run found and spent, without what names the run (ids, fingerprints)."""
    return {
        "tracks": [
            (
                t.track_id,
                t.channel,
                t.status,
                t.stop_reason,
                t.detail,
                t.reused,
                t.model_requests,
                t.search_calls,
                t.fetches,
                t.credits,
                len(t.snapshot_ids),
                len(t.evidence_ids),
                len(t.quarantined_ids),
                [(q.text, q.decision, q.refusal, q.failure) for q in t.queries],
            )
            for t in bundle.tracks
        ],
        "accepted": sorted(a.evidence.claim for a in bundle.accepted),
        "quarantined": sorted((q.claim, q.reason) for q in bundle.quarantined),
        "snapshots": sorted(s.snapshot_id for s in bundle.snapshots),
        "counts": bundle.counts,
        "spend": bundle.spend_usd,
        "quality": bundle.quality_status,
        "synthesis": bundle.synthesis is not None,
    }


def steps(world: ResearchWorld, run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["node_key"]: s for s in run["steps"]}


@dataclasses.dataclass(frozen=True)
class Pair:
    """The same journey with the switch off, then on, in one world."""

    off: tuple[dict[str, Any], EvidenceBundle, RecordedAgents]
    on: tuple[dict[str, Any], EvidenceBundle, RecordedAgents]
    endings: list[str]


def pair(
    world: ResearchWorld,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    sessions: sessionmaker[Session],
    *,
    mode: str,
    agents: Any,
) -> Pair:
    def journey(fan_out: bool, content: dict[str, Any]) -> tuple[Any, ...]:
        recorded_agents = agents()
        runtime = composition(world, recorded_agents, mode=mode, fan_out=fan_out, sessions=sessions)
        run_id = start(world, content) if mode == "planned" else start_web(world, content)
        endings = run_all(worker(world, database_url, store, build, runtime))
        run, bundle = read(world, run_id, store)
        return run, bundle, recorded_agents, endings

    off_run, off_bundle, off_agents, off_endings = journey(False, DESIGN)
    assert off_endings == ["completed"] * 6
    on_run, on_bundle, on_agents, on_endings = journey(True, FANNED)
    return Pair(
        off=(off_run, off_bundle, off_agents),
        on=(on_run, on_bundle, on_agents),
        endings=on_endings,
    )


def _investigation(store: InMemoryArtifactStore, world: ResearchWorld, run: dict[str, Any]) -> Any:
    from aia_core.application.research import research_artifacts

    artifact_id = steps(world, run)["investigate"]["output"]["artifact_id"]
    with world.sessions() as session:
        payload = research_artifacts(session, world.lead_scope(session), store).read_json(
            artifact_id
        )
    return InvestigationRecord.model_validate(payload)


def _plan(store: InMemoryArtifactStore, world: ResearchWorld, run: dict[str, Any]) -> PlanRecord:
    from aia_core.application.research import research_artifacts

    artifact_id = steps(world, run)["plan"]["output"]["artifact_id"]
    with world.sessions() as session:
        payload = research_artifacts(session, world.lead_scope(session), store).read_json(
            artifact_id
        )
    return PlanRecord.model_validate(payload)


# --------------------------------------------------------------------------- #
# The same bundle, in steps of their own
# --------------------------------------------------------------------------- #


def test_planned_tracks_in_steps_of_their_own_find_what_one_step_finds(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    sessions: sessionmaker[Session],
) -> None:
    approve_knowledge(research)
    result = pair(
        research,
        database_url,
        store,
        build,
        sessions,
        mode="planned",
        agents=lambda: RecordedAgents(ANSWERS),
    )
    (off_run, off_bundle, off_agents), (on_run, on_bundle, on_agents) = result.off, result.on

    assert on_run["status"] is WorkflowRunStatus.COMPLETED and on_bundle.verify()
    assert signature(on_bundle) == signature(off_bundle)
    assert on_agents.roles() == off_agents.roles(), "no agent asked once more, or less"

    # Every track the plan did not block is handed out -- Q2's internal one too: only the
    # gateway, asked by the track, refuses it -- each to a step of its own, and the join
    # ran twice: handed out, then joined.
    on_steps = steps(research, on_run)
    children = {k: s for k, s in on_steps.items() if s["kind"] == INVESTIGATE_TRACK_KIND}
    assert set(children) == {track_step_key(t.track_id) for t in on_bundle.tracks}
    assert all(s["status"] is StepRunStatus.SUCCEEDED for s in children.values())
    assert all(len(s["attempts"]) == 1 for s in children.values())
    assert [a["status"] for a in on_steps["investigate"]["attempts"]] == [
        AttemptStatus.DEFERRED,
        AttemptStatus.SUCCEEDED,
    ]
    assert on_steps["investigate"]["attempts_consumed"] == 1
    assert result.endings == ["completed", "deferred", *["completed"] * (len(children) + 5)]
    # The same plan, the same versions: the switch is recorded nowhere.
    assert _plan(store, research, on_run).versions == _plan(store, research, off_run).versions
    on_record = _investigation(store, research, on_run)
    off_record = _investigation(store, research, off_run)
    assert [e.track_id for e in on_record.tracks] == [e.track_id for e in off_record.tracks]
    assert not any(e.reused for e in on_record.tracks)


def test_agent_directed_tracks_in_steps_of_their_own_find_what_one_step_finds(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    sessions: sessionmaker[Session],
) -> None:
    result = pair(
        research,
        database_url,
        store,
        build,
        sessions,
        mode="directed",
        agents=lambda: ScriptedInvestigator(ANSWERS),
    )
    (_off_run, off_bundle, off_agents), (on_run, on_bundle, on_agents) = result.off, result.on

    assert on_run["status"] is WorkflowRunStatus.COMPLETED and on_bundle.verify()
    assert signature(on_bundle) == signature(off_bundle)
    assert on_agents.roles() == off_agents.roles()
    assert [(s, t) for s, t, _ in on_agents.shown] == [(s, t) for s, t, _ in off_agents.shown]
    assert result.endings.count("deferred") == 1


def test_a_lead_planned_run_hands_out_wave_by_wave_and_asks_the_lead_nothing_twice(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    sessions: sessionmaker[Session],
) -> None:
    result = pair(
        research,
        database_url,
        store,
        build,
        sessions,
        mode="lead",
        agents=lambda: ScriptedLead(ANSWERS),
    )
    (off_run, off_bundle, off_agents), (on_run, on_bundle, on_agents) = result.off, result.on

    assert on_run["status"] is WorkflowRunStatus.COMPLETED and on_bundle.verify()
    assert signature(on_bundle) == signature(off_bundle)
    # The re-plan after a wave is stored and replayed on every later attempt of the
    # join: the lead is asked exactly as often as when one step ran every wave.
    assert on_agents.roles() == off_agents.roles()
    assert on_agents.roles()["lead_replan"] == 1
    off_lead = _investigation(store, research, off_run).lead
    on_lead = _investigation(store, research, on_run).lead
    assert off_lead is not None and on_lead is not None
    assert on_lead.waves == off_lead.waves
    on_steps = steps(research, on_run)
    joins = [a["status"] for a in on_steps["investigate"]["attempts"]]
    assert joins == [AttemptStatus.DEFERRED] * len(on_lead.waves) + [AttemptStatus.SUCCEEDED]
    assert on_steps["investigate"]["attempts_consumed"] == 1, "waiting per wave is not failing"
    tasks = {k for k, s in on_steps.items() if s["kind"] == INVESTIGATE_TRACK_KIND}
    assert tasks == {track_step_key(t) for wave in on_lead.waves for t in wave}


# --------------------------------------------------------------------------- #
# An interrupted track recovers in its own step
# --------------------------------------------------------------------------- #


def test_a_track_step_that_lost_its_lease_mid_search_is_resumed_and_sends_nothing_again(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approve_knowledge(research)
    agents = RecordedAgents(ANSWERS)
    runtime = composition(research, agents, mode="planned", fan_out=True, sessions=sessions)
    w = worker(research, database_url, store, build, runtime)
    run_id = start(research, FANNED)
    lost = "ovesný nápoj spotřeba"
    served = RecordedSearch.search

    def search(self: RecordedSearch, query: str, *, max_results: int) -> Any:
        if query == lost and lost not in self.calls:
            _take_the_lease(research)  # the dispatch is on record; its outcome will not be
        return served(self, query, max_results=max_results)

    monkeypatch.setattr(RecordedSearch, "search", search)
    endings = run_all(w)
    assert "lease_lost" in endings
    with research.sessions() as session:  # the reconciler, once the lapsed lease is due
        WorkQueue(session).recover_expired_attempts(now=datetime.now(UTC) + timedelta(hours=1))
        session.commit()
    run_all(w)

    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    oats = tid(SubjectKind.OBJECT, OATS, Channel.WEB)
    track_step = steps(research, run)[track_step_key(oats)]
    assert [a["status"] for a in track_step["attempts"]] == [
        AttemptStatus.EXPIRED,
        AttemptStatus.SUCCEEDED,
    ]
    others = [
        s
        for k, s in steps(research, run).items()
        if s["kind"] == INVESTIGATE_TRACK_KIND and k != track_step_key(oats)
    ]
    assert all(len(s["attempts"]) == 1 for s in others), "no other track ran twice"
    retrieval = runtime.retrieval
    assert retrieval is not None and isinstance(retrieval.search, RecordedSearch)
    assert retrieval.search.calls.count(lost) == 1, "a search that may have been served"
    record = {t.track_id: t for t in bundle.tracks}[oats]
    assert record.status is TrackStatus.INCOMPLETE
    assert record.stop_reason is StopReason.TOOL_OUTCOME_UNCERTAIN
    entries = [e for e in tool_events(research, run_id) if e["payload"]["track_id"] == oats]
    dispatched = [e for e in entries if e["message"] == TOOL_EVENT_KINDS[ToolOutcome.DISPATCHED]]
    closed = [e for e in entries if e["message"] == TOOL_EVENT_KINDS[ToolOutcome.UNCERTAIN]]
    assert len(closed) == 1 and closed[0]["payload"]["call_id"] in {
        e["payload"]["call_id"] for e in dispatched
    }
    assert closed[0]["step_id"] == track_step["step_id"], "closed by the track's own step"
    assert closed[0]["attempt_id"] == track_step["attempts"][1]["attempt_id"]


def test_an_agent_directed_track_step_interrupted_between_turns_replays_and_pays_once(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lost between turns 2 and 3 of Q1: its own step resumes it, buying nothing twice."""
    from aia_executors.deep_research import agent_directed as agent_directed_module
    from deep_research_fixtures import Q1
    from test_deep_research_investigator_journey import (
        turn_events,  # type: ignore[import-not-found]
    )

    agents = ScriptedInvestigator(ANSWERS)
    runtime = composition(research, agents, mode="directed", fan_out=True, sessions=sessions)
    w = worker(research, database_url, store, build, runtime)
    run_id = start_web(research, FANNED)
    built = agent_directed_module.turn_input
    lost: list[int] = []

    def turn_input(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = built(*args, **kwargs)
        if payload["task"]["subject"]["text"] == Q1 and payload["turn"] == 3 and not lost:
            lost.append(3)
            _take_the_lease(research)  # between turns: the next request is never sent
        return payload

    monkeypatch.setattr(agent_directed_module, "turn_input", turn_input)
    run_all(w)
    with research.sessions() as session:
        WorkQueue(session).recover_expired_attempts(now=datetime.now(UTC) + timedelta(hours=1))
        session.commit()
    run_all(w)

    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    q1 = tid(SubjectKind.QUESTION, Q1, Channel.WEB)
    q1_step = steps(research, run)[track_step_key(q1)]
    assert [a["status"] for a in q1_step["attempts"]] == [
        AttemptStatus.EXPIRED,
        AttemptStatus.SUCCEEDED,
    ]
    assert agents.turns_of(Q1) == [1, 2, 3, 4, 5], "turns 1 and 2 replayed, not bought again"
    replayed = [
        (e["payload"]["turn"], e["payload"]["replayed"], e["step_id"])
        for e in turn_events(research, run_id)
        if e["payload"]["track_id"] == q1
    ]
    assert [(t, r) for t, r, _ in replayed] == [
        (1, False),
        (2, False),
        (1, True),
        (2, True),
        (3, False),
        (4, False),
        (5, False),
    ]
    assert {step for _t, _r, step in replayed} == {q1_step["step_id"]}
    others = [
        s
        for k, s in steps(research, run).items()
        if s["kind"] == INVESTIGATE_TRACK_KIND and k != track_step_key(q1)
    ]
    assert all(len(s["attempts"]) == 1 for s in others)
    assert bundle.counts["model_requests"] == len(agents.requests)


def test_a_handed_out_track_whose_input_was_altered_is_refused_before_anything_is_sent(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    sessions: sessionmaker[Session],
) -> None:
    agents = RecordedAgents(ANSWERS)
    runtime = composition(research, agents, mode="planned", fan_out=True, sessions=sessions)
    w = worker(research, database_url, store, build, runtime)
    run_id = start(research, FANNED)
    assert [w.run_once().ending for _ in range(2)] == ["completed", "deferred"]  # type: ignore[union-attr]
    asked = Counter(agents.roles())
    with research.sessions() as session:
        child = session.scalars(
            select(StepRunRow)
            .where(StepRunRow.run_id == run_id, StepRunRow.kind == INVESTIGATE_TRACK_KIND)
            .order_by(StepRunRow.ordinal)
        ).first()
        assert child is not None
        payload = dict(child.input_json)
        payload["track"] = {**payload["track"], "fingerprint": "0" * 64}
        child.input_json = payload
        session.commit()

    result = w.run_once()

    assert result is not None and result.ending == "failed"
    with research.sessions() as session:
        from aia_core.application.deep_research import DeepResearchRuns

        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    failed = next(s for s in run["steps"] if s["status"] is StepRunStatus.FAILED)
    assert failed["attempts"][0]["error"]["reason"] == "request_altered"
    assert run["status"] is WorkflowRunStatus.FAILED
    assert agents.roles() == asked, "nothing was asked for the altered track"


# --------------------------------------------------------------------------- #
# The run's snapshot cache across its track steps
# --------------------------------------------------------------------------- #


class _Context:
    """Just enough of a step's context for the cache: the claimed attempt's scope."""

    def __init__(self, sessions: sessionmaker[Session], scope: Any, step: Any) -> None:
        self._sessions, self.scope, self.step = sessions, scope, step

    @contextmanager
    def transaction(self) -> Iterator[tuple[Session, Any]]:
        from aia_core.infrastructure.workflow_repository import WorkflowRepository

        with self._sessions() as session:
            yield session, WorkflowRepository(session, self.scope)
            session.commit()


def _claimed(world: ResearchWorld, run_id: str, node: str) -> tuple[Any, Any]:
    """A claimed attempt of ``run_id``'s step ``node``, as a worker would hold it."""
    from aia_core.application.scope import ScopeResolver
    from aia_worker.executor import StepInput

    with world.sessions() as session:
        work = WorkQueue(session).claim_next(worker_id="cache-test", kinds={node})
        assert work is not None and work.run_id == run_id
        scope = ScopeResolver(session).execution_context(
            attempt_id=work.attempt_id, worker_id="cache-test"
        )
        session.commit()
    step = StepInput(
        run_id=work.run_id,
        step_id=work.step_id,
        attempt_id=work.attempt_id,
        attempt_number=work.attempt_number,
        node_key=work.node_key,
        kind=work.kind,
        stage_type=work.stage_type,
        artifact_target=work.artifact_target,
        input_fingerprint=work.input_fingerprint,
        interaction_mode=work.interaction_mode,
        payload=dict(work.payload),
        project_id=work.project_id,
        project_revision=work.project_revision,
    )
    return scope, step


def test_a_url_one_track_step_captured_is_answered_to_another_from_the_store(
    research: ResearchWorld,  # noqa: F811
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    from aia_executors.deep_research import InvestigateTrackExecutor
    from aia_executors.deep_research.fan_out import StoredRunSnapshotCache
    from aia_executors.deep_research_recorded import recorded_retrieval

    retrieval, _table = recorded_retrieval(DIRECTED_WEB)
    news = "https://zpravy-dr.example/trh-napoju"
    page = retrieval.fetcher.fetch(news)
    first = start_web(research)
    second = start_web(research, FANNED)
    executor = InvestigateTrackExecutor(store=store, build=build, runtime=None)
    scope, step = _claimed(research, first, "deep_research_plan")
    one = _Context(research.sessions, scope, step)

    assert StoredRunSnapshotCache(executor, one, step).get(news) is None
    executor._snapshot(one, step, page)  # the track stores what it captured ...
    StoredRunSnapshotCache(executor, one, step).put(news, page)  # ... and indexes it

    another = StoredRunSnapshotCache(executor, one, step)  # another step, same run
    hit = another.get(news)
    assert hit is not None and hit.snapshot == page.snapshot and hit.published == page.published
    assert another.get(page.snapshot.final_url) is not None, "under its final URL too"
    assert another.get("https://zpravy-dr.example/jina") is None
    other_scope, other_step = _claimed(research, second, "deep_research_plan")
    other_run = _Context(research.sessions, other_scope, other_step)
    assert StoredRunSnapshotCache(executor, other_run, other_step).get(news) is None, (
        "another run's captures are its own"
    )


# --------------------------------------------------------------------------- #
# The model limit
# --------------------------------------------------------------------------- #


class NoSlot:
    """A pool with no slot free: every request waits out its bound."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    @contextmanager
    def hold(self, *, holder_attempt_id: str, checkpoint: Any) -> Iterator[int]:
        self.asked.append(holder_attempt_id)
        checkpoint()
        raise ModelSlotsBusy("bedrock:journey", 1, 120.0)
        yield 0  # pragma: no cover - never reached


def test_a_request_with_no_slot_parks_for_capacity_reserving_and_sending_nothing(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    sessions: sessionmaker[Session],
) -> None:
    agents = RecordedAgents(ANSWERS)
    slots = NoSlot()
    runtime = composition(
        research, agents, mode="planned", fan_out=True, sessions=sessions, slots=slots
    )
    w = worker(research, database_url, store, build, runtime)
    run_id = start(research, FANNED)

    result = w.run_once()

    assert result is not None and result.step_status is StepRunStatus.WAITING_CAPACITY
    assert len(slots.asked) == 1 and agents.requests == []
    with research.sessions() as session:
        from aia_core.application.deep_research import DeepResearchRuns

        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    plan = run["steps"][0]
    assert plan["attempts_consumed"] == 0, "waiting for capacity is not a failure"
    assert plan["attempts"][0]["error"]["reason"] == MODEL_CONCURRENCY_WAIT
    assert plan["attempts"][0]["paid_call_dispatched"] is False
    assert run["status"] is WorkflowRunStatus.WAITING_CAPACITY


def test_every_agent_request_of_a_fanned_out_run_holds_a_slot_and_returns_it(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    sessions: sessionmaker[Session],
) -> None:
    held: list[int] = []
    pool = ModelSlots(sessions, pool="bedrock:journey", limit=1)

    class Counting:
        @contextmanager
        def hold(self, *, holder_attempt_id: str, checkpoint: Any) -> Iterator[int]:
            with pool.hold(holder_attempt_id=holder_attempt_id, checkpoint=checkpoint) as slot:
                held.append(slot)
                assert pool.in_flight() == 1
                yield slot

    agents = RecordedAgents(ANSWERS)
    runtime = composition(
        research, agents, mode="planned", fan_out=True, sessions=sessions, slots=Counting()
    )
    run_id = start(research, FANNED)
    run_all(worker(research, database_url, store, build, runtime))

    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    assert len(held) == len(agents.requests) == bundle.counts["model_requests"]
    assert set(held) == {0} and pool.in_flight() == 0


# --------------------------------------------------------------------------- #
# The switch
# --------------------------------------------------------------------------- #


ON = {"AIA_DEEP_RESEARCH_ENABLED": "true"}


@pytest.mark.parametrize("value", ["yes please", "2"])
def test_the_switch_is_read_strictly(research: ResearchWorld, value: str) -> None:  # noqa: F811
    settings = ai_settings(research.client_id, approved_for=TEST_ROUTE)
    with pytest.raises(AIRuntimeConfigError, match="AIA_DEEP_RESEARCH_FAN_OUT"):
        deep_research_runtime(settings, env={**ON, "AIA_DEEP_RESEARCH_FAN_OUT": value})


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"AIA_DEEP_RESEARCH_FAN_OUT": "true"}, "needs AIA_DEEP_RESEARCH_ENABLED"),
        ({**ON, "AIA_DEEP_RESEARCH_FAN_OUT": "true"}, "needs AIA_DEEP_RESEARCH_MODEL_CONCURRENCY"),
        ({**ON, "AIA_DEEP_RESEARCH_MODEL_CONCURRENCY": "4"}, "needs AIA_DEEP_RESEARCH_FAN_OUT"),
        (
            {**ON, "AIA_DEEP_RESEARCH_FAN_OUT": "true", "AIA_DEEP_RESEARCH_MODEL_CONCURRENCY": "0"},
            "between 1 and 256",
        ),
        (
            {
                **ON,
                "AIA_DEEP_RESEARCH_FAN_OUT": "true",
                "AIA_DEEP_RESEARCH_MODEL_CONCURRENCY": "4x",
            },
            "not a whole number",
        ),
        (
            {**ON, "AIA_DEEP_RESEARCH_FAN_OUT": "true", "AIA_DEEP_RESEARCH_MODEL_CONCURRENCY": "4"},
            "needs DATABASE_URL",
        ),
        (
            {
                **ON,
                "AIA_DEEP_RESEARCH_FAN_OUT": "true",
                "AIA_DEEP_RESEARCH_MODEL_CONCURRENCY": "4",
                "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            },
            "in-memory",
        ),
    ],
)
def test_the_worker_refuses_to_start_on_an_incomplete_fan_out(
    research: ResearchWorld,  # noqa: F811
    env: dict[str, str],
    message: str,
) -> None:
    settings = ai_settings(research.client_id, approved_for=TEST_ROUTE)
    with pytest.raises(AIRuntimeConfigError, match=message):
        deep_research_runtime(settings, env=env)


def test_off_unless_set_and_on_it_shares_one_pacer_and_one_pool(
    research: ResearchWorld,  # noqa: F811
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    settings = ai_settings(research.client_id, approved_for=TEST_ROUTE)
    for env in ({}, {"AIA_DEEP_RESEARCH_FAN_OUT": ""}, {"AIA_DEEP_RESEARCH_FAN_OUT": "false"}):
        off = deep_research_runtime(settings, env={**ON, **env})
        assert off is not None and off.config.fan_out is False and off.model_slots is None

    on = deep_research_runtime(
        settings,
        env={
            **ON,
            "AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED": "true",
            "AIA_DEEP_RESEARCH_FAN_OUT": "true",
            "AIA_DEEP_RESEARCH_MODEL_CONCURRENCY": "4",
        },
        coordination=sessions,
    )
    assert on is not None and on.config.fan_out is True
    assert isinstance(on.model_slots, ModelSlots)
    assert on.model_slots.limit == 4 and on.model_slots.pool == f"bedrock:{settings.route_id}"
    assert on.retrieval is not None
    assert isinstance(on.retrieval.fetcher._transport, PacedTransport)
    # The switch is recorded nowhere: the versions a plan records are the same.
    off = deep_research_runtime(settings, env={**ON, "AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED": "true"})
    assert off is not None and off.versions() == on.versions()
    assert off.inputs() == on.inputs()

    from_url = deep_research_runtime(
        settings,
        env={
            **ON,
            "AIA_DEEP_RESEARCH_FAN_OUT": "true",
            "AIA_DEEP_RESEARCH_MODEL_CONCURRENCY": "2",
            "DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'coordination.db'}",
        },
    )
    assert from_url is not None and isinstance(from_url.model_slots, ModelSlots)
