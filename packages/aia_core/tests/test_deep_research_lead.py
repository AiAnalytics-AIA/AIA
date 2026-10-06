"""The lead researcher's rules, as code holds them (plan deep-research-web-search.md chunk 11).

Effort caps by complexity, waves, no overlapping tasks, the run's ceiling, the re-plan
limit, budget moved with the run's total unchanged -- and the bound contracts that run
those checks inside the gateway's validation without changing what the model is shown.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.deep_research.agents import (
    AGENT_IDS,
    AgentRole,
    agent_definition,
    model_request,
    prompt_for,
)
from aia_core.domain.deep_research.contracts import (
    ResearchSubject,
    SubjectKind,
    subject_key,
)
from aia_core.domain.deep_research.lead import (
    EFFORT_CAPS,
    LEAD_LIMITS,
    LEAD_PROMPT_VERSION,
    Allotment,
    BudgetMove,
    Complexity,
    LeadLimits,
    LeadState,
    PlanRefusal,
    Replan,
    ResearchPlan,
    RoutedFinding,
    SubagentTask,
    TaskBudget,
    TaskKind,
    Wave,
    bound_plan_contract,
    bound_replan_contract,
    check_plan,
    lead_limits,
    lead_track,
    lead_track_id,
)
from aia_core.domain.deep_research.planning import PRESETS
from aia_core.domain.licence import DataLineage
from aia_core.domain.residency import DataClass

Q1 = subject_key(SubjectKind.QUESTION, "Jak roste trh rostlinných nápojů v Česku?")
Q2 = subject_key(SubjectKind.QUESTION, "Proč lidé přecházejí na rostlinné nápoje?")
OATS = subject_key(SubjectKind.OBJECT, "Ovesný nápoj")


def standard(subjects: tuple[str, ...] = (Q1, Q2, OATS)) -> LeadLimits:
    depth = PRESETS["STANDARD"]
    return lead_limits(
        "STANDARD",
        subjects=subjects,
        max_turns=depth.max_turns,
        max_searches=depth.max_searches,
        max_opens=depth.max_opens,
        max_search_calls=depth.max_search_calls,
        max_fetches=depth.max_fetches,
    )


def task(
    task_id: str,
    subject: str,
    measure: str,
    *,
    budget: tuple[int, int, int] = (6, 4, 6),
    kind: TaskKind = TaskKind.RESEARCH,
    addresses: tuple[str, ...] = (),
    reason: str | None = None,
) -> SubagentTask:
    turns, searches, opens = budget
    return SubagentTask(
        task_id=task_id,
        kind=kind,
        subject_key=subject,
        measure=measure,
        objective=f"Zjistit {measure}.",
        wanted_output="Číslo s jednotkou, obdobím, územím a populací.",
        prefer_sources=["statistický úřad"],
        boundaries=["jiný ukazatel"],
        budget=TaskBudget(turns=turns, searches=searches, opens=opens),
        addresses=list(addresses),
        reason=reason,
    )


def sized(key: str, complexity: Complexity, effort: int) -> dict[str, Any]:
    return {
        "subject_key": key,
        "questions": ["Jaký je stav?"],
        "complexity": complexity,
        "effort": effort,
        "rationale": "",
    }


def plan(subjects: list[dict[str, Any]], *waves: list[SubagentTask]) -> ResearchPlan:
    return ResearchPlan.model_validate(
        {
            "subjects": subjects,
            "waves": [Wave(tasks=list(w)) for w in waves],
            "notes": "",
        }
    )


#: Q1 complex (three tasks), Q2 simple (one), oats a comparison (two): six tasks, two waves.
def good_plan() -> ResearchPlan:
    return plan(
        [
            sized(Q1, Complexity.COMPLEX, 3),
            sized(Q2, Complexity.SIMPLE, 1),
            sized(OATS, Complexity.COMPARISON, 2),
        ],
        [
            task("T1", Q1, "spotřeba rostlinných nápojů, CZ, 2025", budget=(15, 8, 20)),
            task("T2", Q1, "tržby rostlinných nápojů, CZ, 2025", budget=(10, 6, 10)),
            task("T3", Q1, "podíl domácností kupujících, CZ, 2025", budget=(10, 6, 10)),
        ],
        [
            task("T4", Q2, "důvody přechodu, CZ"),
            task("T5", OATS, "cena ovesného nápoje, CZ, 2025", budget=(10, 6, 9)),
            task("T6", OATS, "cena mandlového nápoje, CZ, 2025", budget=(10, 6, 9)),
        ],
    )


def reasons(problems: tuple[str, ...]) -> set[str]:
    return {p.split(":", 1)[0] for p in problems}


# --------------------------------------------------------------------------- #
# The tables
# --------------------------------------------------------------------------- #


def test_the_effort_table_scales_from_one_task_to_many() -> None:
    simple, comparison, complex_ = (EFFORT_CAPS[c] for c in Complexity)
    assert (simple.min_tasks, simple.max_tasks) == (1, 1)
    assert (comparison.min_tasks, comparison.max_tasks) == (2, 4)
    assert complex_.min_tasks > comparison.min_tasks and complex_.max_tasks > 4
    # Plan section 9: a simple fact is 3-10 tool calls, a comparison 10-15 per track.
    assert simple.searches + simple.opens <= 10
    assert comparison.searches + comparison.opens <= 15
    assert simple.turns < comparison.turns < complex_.turns


def test_every_preset_has_lead_limits_and_its_ceiling_binds_on_its_own() -> None:
    assert set(LEAD_LIMITS) == set(PRESETS)
    for name, limits in LEAD_LIMITS.items():
        depth = PRESETS[name]
        turns, searches, opens = limits.ceiling
        # Below what every task at the preset's full per-track allowance could use.
        assert turns < limits.max_tasks * depth.max_turns
        assert searches < limits.max_tasks * depth.max_searches
        assert opens < limits.max_tasks * depth.max_opens
    assert (LEAD_LIMITS["QUICK"].replans, LEAD_LIMITS["STANDARD"].replans) == (0, 1)
    assert LEAD_LIMITS["DEEP"].replans == 3


def test_a_task_cap_is_its_complexity_within_the_preset_s_track() -> None:
    limits = standard()
    assert limits.cap(Complexity.COMPLEX) == Allotment(turns=15, searches=8, opens=20)
    quick = lead_limits(
        "QUICK",
        subjects=(Q1,),
        max_turns=6,
        max_searches=4,
        max_opens=8,
        max_search_calls=48,
        max_fetches=96,
    )
    assert quick.cap(Complexity.COMPLEX) == Allotment(turns=6, searches=4, opens=8)
    # The run's ceiling never above the preset's own run limits.
    tight = lead_limits(
        "STANDARD",
        subjects=(Q1,),
        max_turns=15,
        max_searches=8,
        max_opens=20,
        max_search_calls=10,
        max_fetches=30,
    )
    assert (tight.ceiling.searches, tight.ceiling.opens) == (10, 30)


# --------------------------------------------------------------------------- #
# The plan
# --------------------------------------------------------------------------- #


def test_a_simple_subject_gets_one_task_and_a_complex_one_many() -> None:
    assert check_plan(good_plan(), standard()) == ()
    two_for_simple = plan(
        [sized(Q2, Complexity.SIMPLE, 2)],
        [task("T1", Q2, "důvody přechodu"), task("T2", Q2, "věk přecházejících")],
    )
    assert reasons(check_plan(two_for_simple, standard((Q2,)))) == {
        PlanRefusal.EFFORT_OUTSIDE_COMPLEXITY.value
    }
    one_for_complex = plan([sized(Q1, Complexity.COMPLEX, 1)], [task("T1", Q1, "spotřeba")])
    assert reasons(check_plan(one_for_complex, standard((Q1,)))) == {
        PlanRefusal.EFFORT_OUTSIDE_COMPLEXITY.value
    }
    # A run of one simple subject is one task in one wave.
    single = plan([sized(Q2, Complexity.SIMPLE, 1)], [task("T1", Q2, "důvody přechodu")])
    assert check_plan(single, standard((Q2,))) == ()


def test_a_subject_has_as_many_tasks_as_its_effort() -> None:
    short = plan(
        [sized(OATS, Complexity.COMPARISON, 3)],
        [task("T1", OATS, "cena"), task("T2", OATS, "obal")],
    )
    problems = check_plan(short, standard((OATS,)))
    assert reasons(problems) == {PlanRefusal.TASKS_NOT_EFFORT.value}
    assert "effort 3 and 2 tasks" in problems[0]


def test_overlapping_tasks_are_refused() -> None:
    overlapping = plan(
        [sized(OATS, Complexity.COMPARISON, 2), sized(Q2, Complexity.SIMPLE, 1)],
        [
            task("T1", OATS, "Cena ovesného nápoje, CZ, 2025"),
            task("T2", OATS, "cena  ovesného nápoje, cz, 2025"),
            # The same measure for another subject is another task.
            task("T3", Q2, "cena ovesného nápoje, CZ, 2025"),
        ],
    )
    problems = check_plan(overlapping, standard((OATS, Q2)))
    assert reasons(problems) == {PlanRefusal.OVERLAPPING_TASKS.value}
    assert "T2 and T1" in problems[0]


def test_every_wave_but_the_last_holds_three_to_five_tasks() -> None:
    subjects = [
        sized(Q1, Complexity.COMPLEX, 3),
        sized(Q2, Complexity.SIMPLE, 1),
        sized(OATS, Complexity.COMPARISON, 2),
    ]
    tasks = good_plan().tasks()
    assert reasons(check_plan(plan(subjects, tasks[:2], tasks[2:]), standard())) == {
        PlanRefusal.WAVE_SIZE.value
    }
    assert check_plan(plan(subjects, tasks[:4], tasks[4:]), standard()) == ()
    with pytest.raises(ValidationError):
        Wave(tasks=tasks)  # six: more than a wave holds


def test_a_task_budget_is_capped_by_its_subject_s_complexity() -> None:
    over = plan([sized(Q2, Complexity.SIMPLE, 1)], [task("T1", Q2, "důvody", budget=(7, 4, 6))])
    problems = check_plan(over, standard((Q2,)))
    assert reasons(problems) == {PlanRefusal.BUDGET_OVER_CAP.value}
    assert "7/4/6 over 6/4/6" in problems[0]


def test_the_plan_must_fit_the_run_s_ceiling() -> None:
    limits = standard().model_copy(update={"ceiling": Allotment(turns=50, searches=64, opens=160)})
    problems = check_plan(good_plan(), limits)
    assert reasons(problems) == {PlanRefusal.CEILING_EXCEEDED.value}
    assert "61/" in problems[0]


def test_every_subject_is_planned_once_and_no_other() -> None:
    p = plan(
        [
            sized(Q2, Complexity.SIMPLE, 1),
            sized(Q2, Complexity.SIMPLE, 1),
            sized("q-000000000000", Complexity.SIMPLE, 1),
        ],
        [task("T1", Q2, "důvody"), task("T1", "q-000000000000", "jiné")],
    )
    assert reasons(check_plan(p, standard((Q2, OATS)))) == {
        PlanRefusal.SUBJECT_PLANNED_TWICE.value,
        PlanRefusal.UNKNOWN_SUBJECT.value,
        PlanRefusal.SUBJECT_NOT_PLANNED.value,
        PlanRefusal.DUPLICATE_TASK_ID.value,
    }


def test_a_plan_holds_research_tasks_only_and_no_more_than_the_run_allows() -> None:
    gap = plan(
        [sized(Q2, Complexity.SIMPLE, 1)],
        [task("T1", Q2, "důvody", kind=TaskKind.GAP, addresses=("T9",), reason="mezera")],
    )
    assert reasons(check_plan(gap, standard((Q2,)))) == {PlanRefusal.KIND_NOT_ALLOWED.value}
    few = standard().model_copy(update={"max_tasks": 5})
    assert reasons(check_plan(good_plan(), few)) == {PlanRefusal.TOO_MANY_TASKS.value}


def test_the_bound_contract_refuses_in_validation_and_shows_the_same_schema() -> None:
    limits = standard()
    bound = bound_plan_contract(limits)
    assert bound.model_json_schema() == ResearchPlan.model_json_schema()
    assert (
        agent_definition(AgentRole.LEAD, max_output_tokens=4096, contract=bound).schema
        == agent_definition(AgentRole.LEAD, max_output_tokens=4096).schema
    )
    good = good_plan().model_dump_json()
    accepted = bound.model_validate_json(good, strict=True)
    assert isinstance(accepted, ResearchPlan)
    bad = good_plan().model_dump(mode="json")
    bad["waves"][0]["tasks"][1]["measure"] = bad["waves"][0]["tasks"][0]["measure"]
    with pytest.raises(ValidationError) as refused:
        bound.model_validate(bad)
    assert "overlapping_tasks: T2 and T1" in str(refused.value)
    # The unbound contract checks shape only: a stored plan reads back as it was.
    assert ResearchPlan.model_validate(bad).waves[0].tasks[1].task_id == "T2"
    with pytest.raises(TypeError):
        agent_definition(AgentRole.LEAD, max_output_tokens=4096, contract=Replan)


# --------------------------------------------------------------------------- #
# Re-plans
# --------------------------------------------------------------------------- #


def after_first_wave(limits: LeadLimits | None = None) -> LeadState:
    state = LeadState.start(good_plan(), limits or standard())
    wave = state.next_wave()
    assert [t.task_id for t in wave] == ["T1", "T2", "T3"]
    state.finish(
        {
            "T1": Allotment(turns=5, searches=4, opens=3),
            "T2": Allotment(turns=10, searches=6, opens=10),
            "T3": Allotment(turns=2, searches=1, opens=0),
        }
    )
    return state


def replan(**fields: Any) -> Replan:
    return Replan.model_validate(
        {"next_wave": [], "moves": [], "routed": [], "notes": "", **fields}
    )


def gap(task_id: str = "T7", **kw: Any) -> SubagentTask:
    defaults: dict[str, Any] = {
        "kind": TaskKind.GAP,
        "addresses": ("T1",),
        "reason": "chybí údaj za rok 2024",
        "budget": (6, 4, 6),
    }
    return task(task_id, Q1, kw.pop("measure", "spotřeba, CZ, 2024"), **{**defaults, **kw})


def test_budget_moved_between_pending_tasks_keeps_the_run_s_total() -> None:
    lean = good_plan().model_dump(mode="json")
    lean["waves"][1]["tasks"][1]["budget"] = {"turns": 6, "searches": 3, "opens": 5}  # T5
    state = LeadState.start(ResearchPlan.model_validate(lean), standard())
    state.next_wave()
    state.finish({t: Allotment(turns=1, searches=0, opens=0) for t in ("T1", "T2", "T3")})
    total_before = state.pending_total()
    committed_before = state.committed()
    # T4 is simple and already at its cap (6/4/6): it can take nothing more.
    into_simple = [BudgetMove(from_task="T6", to_task="T4", turns=1, searches=0, opens=0)]
    assert reasons(state.check_replan(replan(moves=into_simple))) == {
        PlanRefusal.BUDGET_OVER_CAP.value
    }
    moves = [BudgetMove(from_task="T6", to_task="T5", turns=4, searches=3, opens=4)]
    assert state.check_replan(replan(moves=moves)) == ()
    before, after = state.apply(replan(moves=moves))
    assert before == after == total_before
    assert state.pending_total() == total_before
    assert state.committed() == committed_before
    assert state.tasks["T5"].budget == TaskBudget(turns=10, searches=6, opens=9)
    assert state.tasks["T6"].budget == TaskBudget(turns=6, searches=3, opens=5)


def test_a_move_never_overdraws_and_only_between_tasks_still_to_run() -> None:
    state = after_first_wave()
    overdrawn = [BudgetMove(from_task="T4", to_task="T5", turns=6, searches=0, opens=0)]
    assert reasons(state.check_replan(replan(moves=overdrawn))) == {
        PlanRefusal.MOVE_OVERDRAWN.value
    }
    finished = [BudgetMove(from_task="T1", to_task="T5", turns=1, searches=0, opens=0)]
    assert reasons(state.check_replan(replan(moves=finished))) == {
        PlanRefusal.MOVE_NOT_PENDING.value
    }


def test_a_gap_task_runs_next_and_its_brief_carries_the_lead_s_notes() -> None:
    state = after_first_wave()
    routed = [RoutedFinding(from_task="T1", to_task="T4", note="Úřad uvádí spotřebu za 2025.")]
    state.apply(replan(next_wave=[gap()], routed=routed))
    assert [t.task_id for t in state.next_wave()] == ["T7"]
    assert state.assignment(state.tasks["T4"])["from_lead"] == [
        {"from": "T1", "note": "Úřad uvádí spotřebu za 2025."}
    ]
    state.finish({"T7": Allotment(turns=1, searches=0, opens=0)})
    assert [t.task_id for t in state.next_wave()] == ["T4", "T5", "T6"]


def test_a_re_plan_adds_only_gap_and_resolve_tasks_that_name_finished_ones() -> None:
    state = after_first_wave()
    cases = {
        PlanRefusal.KIND_NOT_ALLOWED: gap(kind=TaskKind.RESEARCH),
        PlanRefusal.REASON_MISSING: gap(reason=None),
        PlanRefusal.ADDRESSES_INVALID: gap(addresses=("T4",)),
        PlanRefusal.DUPLICATE_TASK_ID: gap("T2", measure="jiný ukazatel"),
        PlanRefusal.BUDGET_OVER_CAP: gap(budget=(16, 4, 6)),
    }
    for reason, bad in cases.items():
        assert reason.value in reasons(state.check_replan(replan(next_wave=[bad]))), reason
    resolve = gap("T8", kind=TaskKind.RESOLVE, addresses=("T1", "T2"), reason="12,5 % proti 9 %")
    assert state.check_replan(replan(next_wave=[resolve])) == ()


def test_a_gap_may_share_a_finished_task_s_measure_but_not_a_pending_one_s() -> None:
    state = after_first_wave()
    finished_measure = gap(measure="spotřeba rostlinných nápojů, CZ, 2025")
    assert state.check_replan(replan(next_wave=[finished_measure])) == ()
    pending_measure = task(
        "T7",
        OATS,
        "cena ovesného nápoje, CZ, 2025",
        kind=TaskKind.GAP,
        addresses=("T1",),
        reason="mezera",
    )
    assert reasons(state.check_replan(replan(next_wave=[pending_measure]))) == {
        PlanRefusal.OVERLAPPING_TASKS.value
    }


def test_a_re_plan_never_takes_the_run_over_its_ceiling() -> None:
    # A ceiling the plan fills exactly; the first wave used 18/9/27 less than its budgets.
    limits = standard().model_copy(update={"ceiling": Allotment(turns=61, searches=36, opens=64)})
    state = after_first_wave(limits)
    assert state.committed() == Allotment(turns=43, searches=27, opens=37)

    def two(searches: int) -> list[SubagentTask]:
        return [
            gap("T7", budget=(6, searches, 3)),
            gap("T8", measure="tržby, CZ, 2024", budget=(6, searches, 3)),
        ]

    assert state.check_replan(replan(next_wave=two(4))) == ()  # 27 + 8 searches of 36
    problems = state.check_replan(replan(next_wave=two(5)))  # 27 + 10
    assert reasons(problems) == {PlanRefusal.CEILING_EXCEEDED.value}
    assert "55/37/43 over 61/36/64" in problems[0]


def test_the_re_plan_limit_holds_and_a_refused_re_plan_counts() -> None:
    state = after_first_wave()  # STANDARD: one re-plan
    assert state.may_replan
    state.refused()
    assert not state.may_replan
    assert reasons(state.check_replan(replan())) == {PlanRefusal.REPLAN_LIMIT.value}
    with pytest.raises(ValueError, match="replan_limit"):
        state.apply(replan())


def test_the_bound_re_plan_contract_checks_against_the_run_s_state() -> None:
    state = after_first_wave()
    bound = bound_replan_contract(state)
    assert bound.model_json_schema() == Replan.model_json_schema()
    bad = replan(moves=[BudgetMove(from_task="T1", to_task="T5", turns=1, searches=0, opens=0)])
    with pytest.raises(ValidationError, match="move_not_pending"):
        bound.model_validate_json(bad.model_dump_json(), strict=True)
    assert isinstance(bound.model_validate_json(replan().model_dump_json(), strict=True), Replan)


# --------------------------------------------------------------------------- #
# Tracks, agents, prompts
# --------------------------------------------------------------------------- #


def test_a_task_s_track_is_its_subject_s_web_track_and_its_brief() -> None:
    state = after_first_wave()
    subject = ResearchSubject(key=OATS, kind=SubjectKind.OBJECT, text="Ovesný nápoj", origin="t")
    first = lead_track(state.tasks["T5"], subject, base_fingerprint="0" * 64, state=state)
    assert first.track_id == lead_track_id(OATS, "T5") == f"DRT-W-{OATS}-T5"
    again = lead_track(state.tasks["T5"], subject, base_fingerprint="0" * 64, state=state)
    assert again.fingerprint == first.fingerprint
    state.apply(
        replan(routed=[RoutedFinding(from_task="T1", to_task="T5", note="Poznámka vedoucího.")])
    )
    noted = lead_track(state.tasks["T5"], subject, base_fingerprint="0" * 64, state=state)
    assert noted.fingerprint != first.fingerprint
    other_base = lead_track(state.tasks["T5"], subject, base_fingerprint="1" * 64, state=state)
    assert other_base.fingerprint != noted.fingerprint


def test_the_lead_names_its_own_capability_and_answers_in_its_contracts() -> None:
    plan_agent = agent_definition(AgentRole.LEAD, max_output_tokens=4096)
    replan_agent = agent_definition(AgentRole.LEAD_REPLAN, max_output_tokens=4096)
    assert plan_agent.capability is replan_agent.capability is ModelCapability.RESEARCH_LEAD
    assert (plan_agent.output_contract, replan_agent.output_contract) == (ResearchPlan, Replan)
    assert plan_agent.prompt_version == replan_agent.prompt_version == LEAD_PROMPT_VERSION
    assert AGENT_IDS[AgentRole.LEAD] == "aia.deep_research.lead"
    assert plan_agent.allowed_tools == frozenset()
    # Every other agent is as it was.
    assert agent_definition(AgentRole.PLANNER, max_output_tokens=1).capability is (
        ModelCapability.RESEARCH_REASONING
    )
    assert agent_definition(AgentRole.VERIFIER, max_output_tokens=1).capability is (
        ModelCapability.CRITIC
    )
    request = model_request(
        AgentRole.LEAD,
        payload={},
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage.none(),
        policy_version="p",
        max_output_tokens=4096,
        contract=bound_plan_contract(standard()),
    )
    assert request.agent.output_contract is not ResearchPlan
    assert request.agent.schema == plan_agent.schema


def test_the_lead_s_prompts_are_rendered_from_the_effort_table() -> None:
    for role in (AgentRole.LEAD, AgentRole.LEAD_REPLAN):
        prompt = prompt_for(role)
        for complexity, cap in EFFORT_CAPS.items():
            assert f"'{complexity.value}' --" in prompt
            assert f"nejvýše {cap.turns} tahů, {cap.searches} vyhledávání a {cap.opens}" in prompt
        assert all(f"'{k.value}'" in prompt for k in TaskKind)
    assert "3 až 5 úkolů" in prompt_for(AgentRole.LEAD)
    assert "přesně 1 úkol," in prompt_for(AgentRole.LEAD)
