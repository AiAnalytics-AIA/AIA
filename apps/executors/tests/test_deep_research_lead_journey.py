"""The lead researcher end to end, recorded: worker, gateway, gate, executors (chunk 11).

The production path of ``test_deep_research_investigator_journey.py`` with the
composition's ``lead`` on: the lead plans the agent-directed web research, its tasks run
as investigator tracks wave by wave, and it re-plans after a wave. The web is
``investigator_web.json`` (fictional ``*-dr.example`` hosts); the lead's plans and the
investigators' turns are scripted here, by task. Nothing leaves the process.

The scripted run (the fictional client's design, web channel, STANDARD: one re-plan):

* the lead sizes Q1 complex (three tasks), Q2 simple (one), oats a comparison (two) and
  almond simple (one): seven tasks in waves of three, three and one;
* T1 is chunk 9's Q1 track -- searches, the news, the table it links, a finding with its
  measures -- and the other tasks finish at once, naming a gap;
* after the first wave the lead re-plans: a gap task for Q1 (T8) that runs next, two
  turns and a search moved from T6 to T5, and a note from T1 routed to T5;
* the re-plan limit reached, the remaining waves run as planned.
"""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.domain.ai_models import ModelCapability, parse_model_config
from aia_core.domain.deep_research.contracts import (
    Channel,
    StopReason,
    SubjectKind,
    TrackStatus,
    subject_key,
)
from aia_core.domain.deep_research.lead import (
    LEAD_VERSION,
    Allotment,
    lead_track_id,
)
from aia_core.domain.deep_research.request_limits import ModelPrices
from aia_core.domain.deep_research.steps import (
    InvestigationRecord,
    LeadPlanRecord,
    PlanRecord,
    ReplanRecord,
)
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.workflow_repository import WorkQueue
from aia_executors.ai_runtime import AIRuntimeConfigError, build_gateway
from aia_executors.deep_research import DeepResearchConfig, DeepResearchRuntime
from aia_executors.deep_research import agent_directed as agent_directed_module
from aia_executors.deep_research_recorded import recorded_runtime
from aia_executors.deep_research_runtime import deep_research_runtime
from deep_research_fixtures import (
    ALMOND,
    ANSWERS,
    DESIGN,
    OATS,
    Q1,
    Q2,
    TEST_ROUTE,
    RecordedAgents,
    Signer,
    ai_settings,
)
from test_deep_research_investigator_journey import (  # type: ignore[import-not-found]
    TURNS,
    WEB,
    ScriptedInvestigator,
    start_web,
    stored,
)
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ResearchWorld,
    _take_the_lease,
    drain,
    read,
    research,  # noqa: F401  (a fixture)
    worker,
)

QS, OS = SubjectKind.QUESTION, SubjectKind.OBJECT
KQ1, KQ2 = subject_key(QS, Q1), subject_key(QS, Q2)
KOATS, KALMOND = subject_key(OS, OATS), subject_key(OS, ALMOND)

_FINISH: dict[str, Any] = {
    "evidence": [],
    "summary": "Nic dalšího se nenašlo.",
    "leads": [],
    "next": [
        {
            "kind": "finish",
            "gaps": [{"need": "novější údaj", "why": "zdroj ho neuvádí", "tried": "nic"}],
        }
    ],
}


def _task(
    task_id: str,
    subject: str,
    measure: str,
    budget: tuple[int, int, int],
    *,
    kind: str = "research",
    addresses: list[str] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    turns, searches, opens = budget
    return {
        "task_id": task_id,
        "kind": kind,
        "subject_key": subject,
        "measure": measure,
        "objective": f"Zjistit: {measure}.",
        "wanted_output": "Každé číslo s jednotkou, obdobím, územím a populací.",
        "prefer_sources": ["statistický úřad"],
        "boundaries": ["jiný subjekt"],
        "budget": {"turns": turns, "searches": searches, "opens": opens},
        "addresses": addresses or [],
        "reason": reason,
    }


def _subject(key: str, complexity: str, effort: int) -> dict[str, Any]:
    return {
        "subject_key": key,
        "questions": [f"Otázka k {key}"],
        "complexity": complexity,
        "effort": effort,
        "rationale": "",
    }


T1 = _task("T1", KQ1, "spotřeba rostlinných nápojů, CZ, 2025", (10, 6, 10))
T2 = _task("T2", KQ1, "tržby rostlinných nápojů, CZ, 2025", (6, 4, 6))
T3 = _task("T3", KQ1, "podíl domácností kupujících, CZ, 2025", (6, 4, 6))
T4 = _task("T4", KQ2, "důvody přechodu na rostlinné nápoje, CZ", (6, 4, 6))
T5 = _task("T5", KOATS, "cena ovesného nápoje, CZ, 2025", (6, 3, 6))
T6 = _task("T6", KOATS, "dostupnost ovesného nápoje, CZ, 2025", (8, 5, 8))
T7 = _task("T7", KALMOND, "cena mandlového nápoje, CZ, 2025", (4, 2, 4))

PLAN: dict[str, Any] = {
    "subjects": [
        _subject(KQ1, "complex", 3),
        _subject(KQ2, "simple", 1),
        _subject(KOATS, "comparison", 2),
        _subject(KALMOND, "simple", 1),
    ],
    "waves": [{"tasks": [T1, T2, T3]}, {"tasks": [T4, T5, T6]}, {"tasks": [T7]}],
    "notes": "",
}
#: The plan with two tasks of one subject measuring the same thing.
OVERLAPPING: dict[str, Any] = json.loads(json.dumps(PLAN))
OVERLAPPING["waves"][0]["tasks"][1]["measure"] = T1["measure"].upper()
#: Q1 at its widest, every task at its full budget: over the run's ceiling (120 turns).
OVER_CEILING: dict[str, Any] = {
    "subjects": [
        _subject(KQ1, "complex", 8),
        _subject(KQ2, "simple", 1),
        _subject(KOATS, "comparison", 2),
        _subject(KALMOND, "simple", 1),
    ],
    "waves": [
        {"tasks": [_task(f"T{i}", KQ1, f"ukazatel {i}", (15, 5, 12)) for i in range(1, 6)]},
        {
            "tasks": [
                *[_task(f"T{i}", KQ1, f"ukazatel {i}", (15, 5, 12)) for i in range(6, 9)],
                _task("T9", KQ2, "důvody", (6, 4, 6)),
            ]
        },
        {
            "tasks": [
                _task("T10", KOATS, "cena", (10, 6, 9)),
                _task("T11", KOATS, "obal", (10, 6, 9)),
                _task("T12", KALMOND, "cena", (6, 4, 6)),
            ]
        },
    ],
    "notes": "",
}
T8 = _task(
    "T8",
    KQ1,
    "spotřeba rostlinných nápojů, CZ, 2024",
    (2, 1, 1),
    kind="gap",
    addresses=["T1"],
    reason="tabulka uvádí jen rok 2025",
)
NOTE = "Úřad uvádí spotřebu za rok 2025 (předběžně); hledej cenu v téže publikaci."
REPLAN: dict[str, Any] = {
    "next_wave": [T8],
    "moves": [{"from_task": "T6", "to_task": "T5", "turns": 2, "searches": 1, "opens": 0}],
    "routed": [{"from_task": "T1", "to_task": "T5", "note": NOTE}],
    "notes": "",
}
#: A re-plan moving budget out of a task that already ran.
BAD_REPLAN: dict[str, Any] = {
    **REPLAN,
    "moves": [{"from_task": "T1", "to_task": "T5", "turns": 2, "searches": 0, "opens": 0}],
}


@dataclass
class ScriptedLead(ScriptedInvestigator):
    """The recorded agents, a lead answering from its scripts, investigators by task."""

    plans: list[dict[str, Any]] = field(default_factory=lambda: [PLAN])
    replans: list[dict[str, Any]] = field(default_factory=lambda: [REPLAN])
    tasks: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: {"T1": TURNS[Q1]})
    #: Every lead payload, in order: (role, payload).
    lead_shown: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    by_task: list[tuple[str, int, dict[str, Any]]] = field(default_factory=list)

    def _lead(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.lead_shown.append(("lead", payload))
        # The last scripted plan answers every later request (a repair included).
        return self.plans[min(len(self._asked("lead")) - 1, len(self.plans) - 1)]

    def _lead_replan(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.lead_shown.append(("lead_replan", payload))
        return self.replans[min(len(self._asked("lead_replan")) - 1, len(self.replans) - 1)]

    def _asked(self, role: str) -> list[dict[str, Any]]:
        return [p for r, p in self.lead_shown if r == role]

    def _investigator(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_id, turn = payload["task"]["assignment"]["task_id"], payload["turn"]
        self.by_task.append((task_id, turn, payload))
        script = self.tasks.get(task_id, [_FINISH])
        saved, self.turns = self.turns, {payload["task"]["subject"]["text"]: script}
        try:
            return super()._investigator(payload)
        finally:
            self.turns = saved

    def turns_of_task(self, task_id: str) -> list[int]:
        return [t for k, t, _ in self.by_task if k == task_id]

    def task_payload(self, task_id: str, turn: int = 1) -> dict[str, Any]:
        return next(p for k, t, p in self.by_task if k == task_id and t == turn)


def led(world: ResearchWorld, agents: RecordedAgents) -> DeepResearchRuntime:
    settings = dataclasses.replace(
        ai_settings(world.client_id, approved_for=TEST_ROUTE), research_lead_enabled=True
    )
    return recorded_runtime(
        gateway=build_gateway(settings, transport=agents, signer=Signer()),
        config=DeepResearchConfig(
            policy_version=settings.policy_version,
            max_output_tokens=settings.research_max_output_tokens,
            context_window_tokens=settings.context_window_tokens,
            prices=settings.model_prices(),
            fictional_client_ids=settings.fictional_client_ids,
            material_approvals=settings.material_approvals,
            agent_directed=True,
            lead=True,
        ),
        fixture=WEB,
        env={"AIA_ENV": "test"},
    )


def output(run: dict[str, Any], node: int) -> str:
    return str(run["steps"][node]["output"]["artifact_id"])


@dataclass(frozen=True)
class Led:
    world: ResearchWorld
    agents: ScriptedLead
    runtime: DeepResearchRuntime
    run_id: str
    store: InMemoryArtifactStore

    def records(self) -> tuple[PlanRecord, InvestigationRecord]:
        run, _bundle = read(self.world, self.run_id, self.store)
        plan = PlanRecord.model_validate(stored(self.world, self.store, output(run, 0)))
        investigation = InvestigationRecord.model_validate(
            stored(self.world, self.store, output(run, 1))
        )
        return plan, investigation

    def get(self, artifact_id: str, model: type[Any]) -> Any:
        return model.model_validate(stored(self.world, self.store, artifact_id))


def run_led(
    world: ResearchWorld,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    agents: ScriptedLead,
) -> Led:
    runtime = led(world, agents)
    run_id = start_web(world)
    assert drain(worker(world, database_url, store, build, runtime)) == 6
    return Led(world=world, agents=agents, runtime=runtime, run_id=run_id, store=store)


@pytest.fixture
def led_run(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> Led:
    return run_led(research, database_url, store, build, ScriptedLead(ANSWERS))


def tid(subject: str, task: str) -> str:
    return lead_track_id(subject, task)


# --------------------------------------------------------------------------- #
# The run
# --------------------------------------------------------------------------- #


def test_a_simple_subject_gets_one_track_and_a_complex_one_many(led_run: Led) -> None:
    run, bundle = read(led_run.world, led_run.run_id, led_run.store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    per_subject = Counter(t.subject_key for t in bundle.tracks)
    assert per_subject == {KQ1: 4, KQ2: 1, KOATS: 2, KALMOND: 1}  # Q1: three and its gap
    assert {t.track_id for t in bundle.tracks} == {
        tid(KQ1, "T1"),
        tid(KQ1, "T2"),
        tid(KQ1, "T3"),
        tid(KQ1, "T8"),
        tid(KQ2, "T4"),
        tid(KOATS, "T5"),
        tid(KOATS, "T6"),
        tid(KALMOND, "T7"),
    }
    tracks = {t.track_id: t for t in bundle.tracks}
    assert (tracks[tid(KQ1, "T1")].status, tracks[tid(KQ1, "T1")].stop_reason) == (
        TrackStatus.COMPLETED,
        StopReason.AGENT_FINISHED,
    )
    # T1 is chunk 9's Q1 track under the lead: its finding is accepted.
    assert [a.evidence.track_id for a in bundle.accepted] == [tid(KQ1, "T1")]
    roles = led_run.agents.roles()
    assert (roles["lead"], roles["lead_replan"], roles["planner"]) == (1, 1, 0)
    assert roles["investigator"] == 5 + 7 and roles["web_investigator"] == 0
    assert bundle.counts["model_requests"] == len(led_run.agents.requests)


def test_the_plan_is_a_run_artifact_and_the_waves_run_in_order(led_run: Led) -> None:
    plan, investigation = led_run.records()
    assert plan.versions["lead"] == LEAD_VERSION
    assert plan.planner is not None and plan.planner.agent_id == "aia.deep_research.lead"
    assert plan.planned == () and plan.allowances == {}
    # The subjects' own web tracks are not run: the lead's tasks are the web tracks.
    assert all(t.channel is not Channel.WEB for t in plan.tracks)
    assert plan.lead_plan_artifact_id is not None
    lead_plan = led_run.get(plan.lead_plan_artifact_id, LeadPlanRecord)
    assert lead_plan.refused == () and lead_plan.plan is not None
    assert lead_plan.plan.model_dump(mode="json") == PLAN
    assert lead_plan.limits.subjects == (KQ1, KQ2, KOATS, KALMOND)
    assert investigation.lead is not None
    assert investigation.lead.waves == (
        (tid(KQ1, "T1"), tid(KQ1, "T2"), tid(KQ1, "T3")),
        (tid(KQ1, "T8"),),  # the re-plan's gap task runs next
        (tid(KQ2, "T4"), tid(KOATS, "T5"), tid(KOATS, "T6")),
        (tid(KALMOND, "T7"),),
    )


def test_an_investigator_s_brief_is_its_task_and_its_allowance_the_task_s_budget(
    led_run: Led,
) -> None:
    first = led_run.agents.task_payload("T1")
    assignment = first["task"]["assignment"]
    assert assignment["objective"] == T1["objective"]
    assert assignment["wanted_output"] == T1["wanted_output"]
    assert assignment["prefer_sources"] == ["statistický úřad"]
    assert assignment["boundaries"] == ["jiný subjekt"]
    assert "suggested_queries" not in first["task"]
    assert first["task"]["sub_questions"] == [f"Otázka k {KQ1}"]
    assert first["allowance"]["turns_left"] == 10
    assert (first["allowance"]["searches_left"], first["allowance"]["opens_left"]) == (6, 10)
    assert led_run.agents.turns_of_task("T1") == [1, 2, 3, 4, 5]


def test_after_a_wave_the_lead_re_plans_and_budget_moves_with_the_total_unchanged(
    led_run: Led,
) -> None:
    _role, shown = led_run.agents.lead_shown[1]
    assert [f["task_id"] for f in shown["finished"]] == ["T1", "T2", "T3"]
    t1 = shown["finished"][0]
    assert t1["summaries"][0] == "Hledám zdroje o trhu."
    assert t1["findings"][0]["measures"][0] == {
        "value": 12.5,
        "unit": "%",
        "scale": 1,
        "period": "Y2025",
        "geography": "CZ",
    }
    assert t1["used"] == {"turns": 5, "searches": 4, "opens": 2}
    assert shown["run"]["replans_left"] == 1
    _plan, investigation = led_run.records()
    assert investigation.lead is not None
    [replan_id] = investigation.lead.replan_artifact_ids
    record = led_run.get(replan_id, ReplanRecord)
    assert record.refused == () and record.replan is not None
    assert (
        record.pending_before == record.pending_after == Allotment(turns=24, searches=14, opens=24)
    )
    assert record.committed_after.within(record.ceiling)
    # T5 got T6's two turns and a search, and T1's note.
    t5 = led_run.agents.task_payload("T5")
    assert (t5["allowance"]["turns_left"], t5["allowance"]["searches_left"]) == (8, 4)
    assert t5["task"]["assignment"]["from_lead"] == [{"from": "T1", "note": NOTE}]
    t6 = led_run.agents.task_payload("T6")
    assert (t6["allowance"]["turns_left"], t6["allowance"]["searches_left"]) == (6, 4)
    gap = led_run.agents.task_payload("T8")["task"]["assignment"]
    assert (gap["kind"], gap["reason"]) == ("gap", "tabulka uvádí jen rok 2025")


def test_the_re_plan_limit_holds(led_run: Led) -> None:
    # Four waves ran; STANDARD allows one re-plan, so the lead was asked once.
    assert [r for r, _p in led_run.agents.lead_shown] == ["lead", "lead_replan"]


def _one_task_each(payload: dict[str, Any]) -> dict[str, Any]:
    """A plan sizing every subject it is shown simple: one task each, in waves of five."""
    keys = [s["subject_key"] for s in payload["subjects"]]
    tasks = [_task(f"T{i}", k, f"ukazatel {k}", (2, 1, 1)) for i, k in enumerate(keys, start=1)]
    return {
        "subjects": [_subject(k, "simple", 1) for k in keys],
        "waves": [{"tasks": tasks[i : i + 5]} for i in range(0, len(tasks), 5)],
        "notes": "",
    }


@dataclass
class SizingLead(ScriptedLead):
    def _lead(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.lead_shown.append(("lead", payload))
        return _one_task_each(payload)


EMPTY_REPLAN: dict[str, Any] = {"next_wave": [], "moves": [], "routed": [], "notes": ""}


def test_a_deep_run_plans_its_crosses_and_re_plans_within_its_limit(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    agents = SizingLead(ANSWERS, replans=[EMPTY_REPLAN], tasks={})  # every task finishes
    runtime = led(research, agents)
    with research.sessions() as session:
        scope = research.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=DESIGN, source_stage="brief"
        )
        run_id = (
            DeepResearchRuns(session, scope)
            .start(
                design_revision_id=revision.revision_id, preset_name="DEEP", channels=(Channel.WEB,)
            )
            .run_id
        )
        session.commit()
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    run, bundle = read(research, run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED and bundle.verify()
    # Two questions, two objects and their four crosses: eight subjects, one task each.
    [(_role, shown)] = [(r, p) for r, p in agents.lead_shown if r == "lead"]
    kinds = Counter(s["kind"] for s in shown["subjects"])
    assert kinds == {"QUESTION": 2, "OBJECT": 2, "CROSS": 4}
    assert shown["limits"]["replans"] == 3 and shown["limits"]["max_tasks"] == 20
    crosses = {s["subject_key"] for s in shown["subjects"] if s["kind"] == "CROSS"}
    assert crosses <= {s.key for s in bundle.subjects}
    assert Counter(t.subject_key for t in bundle.tracks) == {
        s["subject_key"]: 1 for s in shown["subjects"]
    }
    # Two waves (five and three tasks), a re-plan after each: two of the three allowed.
    assert [r for r, _p in agents.lead_shown].count("lead_replan") == 2
    assert agents.roles()["investigator"] == 8


# --------------------------------------------------------------------------- #
# Refusals: one repair through the gateway, then explicit
# --------------------------------------------------------------------------- #


def _repair_text(agents: RecordedAgents, role: str) -> str:
    [_first, repair] = [r for r in agents.requests if RecordedAgents._role(r) == role]
    return str(repair.body["messages"][-1]["content"][0]["text"])


def test_overlapping_tasks_are_refused_and_repaired_once(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    agents = ScriptedLead(ANSWERS, plans=[OVERLAPPING, PLAN])
    done = run_led(research, database_url, store, build, agents)
    assert agents.roles()["lead"] == 2
    assert "overlapping_tasks: T2 and T1" in _repair_text(agents, "lead")
    plan, _investigation = done.records()
    assert plan.lead_plan_artifact_id is not None
    stored_plan = done.get(plan.lead_plan_artifact_id, LeadPlanRecord).plan
    assert stored_plan is not None and stored_plan.model_dump(mode="json") == PLAN


def test_a_plan_over_the_run_s_ceiling_is_refused_and_repaired_once(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    agents = ScriptedLead(ANSWERS, plans=[OVER_CEILING, PLAN])
    run_led(research, database_url, store, build, agents)
    text = _repair_text(agents, "lead")
    assert "ceiling_exceeded: the plan's budgets 152/60/126 over 120/64/160" in text


def test_a_plan_refused_twice_blocks_the_web_tracks_and_plans_nothing_else(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    agents = ScriptedLead(ANSWERS, plans=[OVERLAPPING])
    done = run_led(research, database_url, store, build, agents)
    run, bundle = read(research, done.run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    assert {t.subject_key for t in bundle.tracks} == {KQ1, KQ2, KOATS, KALMOND}
    for track in bundle.tracks:
        assert (track.status, track.stop_reason) == (
            TrackStatus.BLOCKED,
            StopReason.PLAN_INCOMPLETE,
        )
        assert "lead_plan_refused" in track.detail and "overlapping_tasks" in track.detail
    roles = agents.roles()
    assert (roles["lead"], roles["planner"], roles["investigator"]) == (2, 0, 0)
    plan, investigation = done.records()
    assert plan.lead_plan_artifact_id is not None and investigation.lead is None
    refused = done.get(plan.lead_plan_artifact_id, LeadPlanRecord)
    assert refused.plan is None and refused.call is None and len(refused.call_ids) == 2
    assert any("overlapping_tasks" in r for r in refused.refused)


def test_a_refused_re_plan_counts_and_the_plan_runs_as_it_stood(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    agents = ScriptedLead(ANSWERS, replans=[BAD_REPLAN])
    done = run_led(research, database_url, store, build, agents)
    assert agents.roles()["lead_replan"] == 2
    assert "move_not_pending: T1 -> T5" in _repair_text(agents, "lead_replan")
    _plan, investigation = done.records()
    assert investigation.lead is not None
    assert [len(w) for w in investigation.lead.waves] == [3, 3, 1]
    [replan_id] = investigation.lead.replan_artifact_ids
    record = done.get(replan_id, ReplanRecord)
    assert record.replan is None and record.call is None
    assert any("move_not_pending" in r for r in record.refused)
    assert record.pending_before == record.pending_after
    t5 = agents.task_payload("T5")
    assert t5["allowance"]["turns_left"] == 6 and t5["task"]["assignment"]["from_lead"] == []
    run, _bundle = read(research, done.run_id, store)
    assert run["status"] is WorkflowRunStatus.COMPLETED


# --------------------------------------------------------------------------- #
# A retry: the stored plan and re-plan, no new lead call
# --------------------------------------------------------------------------- #


def test_a_retry_reuses_the_stored_plan_and_re_plan_without_a_new_lead_call(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents = ScriptedLead(ANSWERS)
    runtime = led(research, agents)
    w = worker(research, database_url, store, build, runtime)
    run_id = start_web(research)
    built = agent_directed_module.turn_input
    lost: list[str] = []

    def turn_input(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = built(*args, **kwargs)
        if payload["task"]["assignment"]["task_id"] == "T5" and not lost:
            lost.append("T5")
            _take_the_lease(research)  # in the third wave: the next request is never sent
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
    # The plan and the re-plan were bought once; every task's turns once each.
    roles = agents.roles()
    assert (roles["lead"], roles["lead_replan"]) == (1, 1)
    assert agents.turns_of_task("T1") == [1, 2, 3, 4, 5]
    assert all(agents.turns_of_task(t) == [1] for t in ("T2", "T3", "T4", "T5", "T6", "T7", "T8"))
    assert bundle.counts["model_requests"] == len(agents.requests)
    with research.sessions() as session:
        events = DeepResearchRuns(session, research.lead_scope(session)).events(run_id, limit=2000)
    assert [e["payload"]["applied"] for e in events if e["message"] == "deep_research_replan"] == [
        True
    ]


# --------------------------------------------------------------------------- #
# The switch and the lead's policy entry
# --------------------------------------------------------------------------- #


def test_the_lead_s_model_is_its_own_policy_entry_bound_only_when_on(
    research: ResearchWorld,  # noqa: F811
) -> None:
    settings = ai_settings(research.client_id, approved_for=TEST_ROUTE)
    version = settings.policy_version
    off = parse_model_config(settings.model_document())
    on = parse_model_config(
        dataclasses.replace(settings, research_lead_enabled=True).model_document()
    )
    assert on.coverage(version) - off.coverage(version) == {ModelCapability.RESEARCH_LEAD}
    resolved = on.resolve(capability=ModelCapability.RESEARCH_LEAD, policy_version=version)
    assert (resolved.model, resolved.route_id) == (settings.model_id, settings.route_id)


@pytest.mark.parametrize("value", ["maybe", "2"])
def test_the_lead_switch_is_read_strictly_and_needs_the_agent_directed_mode(
    research: ResearchWorld,  # noqa: F811
    value: str,
) -> None:
    settings = ai_settings(research.client_id, approved_for=TEST_ROUTE)
    on = {"AIA_DEEP_RESEARCH_ENABLED": "true", "AIA_DEEP_RESEARCH_AGENT_DIRECTED": "true"}
    with pytest.raises(AIRuntimeConfigError, match="AIA_DEEP_RESEARCH_LEAD"):
        deep_research_runtime(settings, env={**on, "AIA_DEEP_RESEARCH_LEAD": value})
    with pytest.raises(AIRuntimeConfigError, match="needs AIA_DEEP_RESEARCH_AGENT_DIRECTED"):
        deep_research_runtime(
            settings, env={"AIA_DEEP_RESEARCH_ENABLED": "true", "AIA_DEEP_RESEARCH_LEAD": "true"}
        )
    with pytest.raises(AIRuntimeConfigError, match="needs AIA_DEEP_RESEARCH_ENABLED"):
        deep_research_runtime(
            None,
            env={"AIA_DEEP_RESEARCH_AGENT_DIRECTED": "true", "AIA_DEEP_RESEARCH_LEAD": "true"},
        )


def test_the_lead_switch_is_off_unless_set_and_on_records_the_mode(
    research: ResearchWorld,  # noqa: F811
) -> None:
    settings = ai_settings(research.client_id, approved_for=TEST_ROUTE)
    directed = {"AIA_DEEP_RESEARCH_ENABLED": "true", "AIA_DEEP_RESEARCH_AGENT_DIRECTED": "true"}

    def runtime(env: dict[str, str]) -> DeepResearchRuntime:
        built = deep_research_runtime(
            settings,
            env={**directed, **env},
            transport=ScriptedLead(ANSWERS),
            signer=Signer(),
        )
        assert built is not None
        return built

    for env in ({}, {"AIA_DEEP_RESEARCH_LEAD": ""}, {"AIA_DEEP_RESEARCH_LEAD": "false"}):
        off = runtime(env)
        assert off.config.lead is False and "lead" not in off.versions()
        registry = off.gateway._registry
        assert ModelCapability.RESEARCH_LEAD not in registry.coverage(settings.policy_version)
    on = runtime({"AIA_DEEP_RESEARCH_LEAD": "true"})
    assert on.config.lead is True and on.versions()["lead"] == LEAD_VERSION
    registry = on.gateway._registry
    assert ModelCapability.RESEARCH_LEAD in registry.coverage(settings.policy_version)
    assert on.retrieval is None  # the switch adds no retrieval
    with pytest.raises(ValueError, match="agent-directed"):
        DeepResearchConfig(
            policy_version="p",
            max_output_tokens=1,
            context_window_tokens=1,
            prices=ModelPrices(3.0, 15.0),
            fictional_client_ids=frozenset(),
            lead=True,
        )
