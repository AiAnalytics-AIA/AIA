"""Presets, budgets and a Deep Research run's cost ceiling (plan deep-research-web-search.md 22).

What is pinned here: the preset table (§ 9) and its version; how many calls of each kind a
run can make, and why each is a bound; the ceiling as those counts priced, with an unknown
price never read as zero and a route that is off costing nothing; and that moving budget
between a lead's tasks never raises the ceiling.
"""

from __future__ import annotations

import math
import random
from typing import Any

import pytest

from aia_core.domain.deep_research.agents import ExtractionProposal, InvestigatorTurn
from aia_core.domain.deep_research.budgets import (
    EVIDENCE_PER_ANSWER,
    MODEL_KINDS,
    ROUTE_ALLOWANCES,
    CallBounds,
    CallKind,
    ResearchMode,
    TrackCounts,
    call_bounds,
    lead_state_bounds,
    track_counts,
)
from aia_core.domain.deep_research.common_crawl import AthenaPricing
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    BriefDigest,
    Channel,
    DeepResearchRequest,
    FrozenKnowledge,
    ResearchSubject,
    SubjectKind,
    subject_key,
)
from aia_core.domain.deep_research.lead import (
    EFFORT_CAPS,
    LEAD_LIMITS,
    Allotment,
    BudgetMove,
    Complexity,
    LeadLimits,
    LeadState,
    Replan,
    ResearchPlan,
    SubagentTask,
    TaskBudget,
    TaskKind,
    Wave,
    lead_limits,
)
from aia_core.domain.deep_research.planning import (
    PRESET_STATUS,
    PRESET_TABLE_VERSION,
    PRESETS,
    TrackInputs,
    build_tracks,
)
from aia_core.domain.run_cost import (
    CeilingUnknown,
    DeepResearchPrices,
    RoutePrice,
    deep_research_cost_ceiling,
    price_bounds,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

#: Illustrative prices for these tests only -- never configuration.
RESERVE = 0.5
SEARCH = 0.005


def prices(**overrides: RoutePrice) -> DeepResearchPrices:
    """Every model kind at RESERVE, search at SEARCH, everything else free; overrides win."""
    base = {k: RoutePrice.per_call(RESERVE) for k in MODEL_KINDS}
    base.update({k: RoutePrice.per_call(0.0) for k in CallKind if k not in MODEL_KINDS})
    base[CallKind.SEARCH] = RoutePrice.per_call(SEARCH)
    base.update({CallKind(k): v for k, v in overrides.items()})
    return DeepResearchPrices(base)


def subject(kind: SubjectKind, text: str) -> ResearchSubject:
    return ResearchSubject(key=subject_key(kind, text), kind=kind, text=text, origin="test")


def request(
    questions: int, objects: int, *, preset: str = "STANDARD", channels: tuple[Channel, ...]
) -> DeepResearchRequest:
    subjects = tuple(
        subject(SubjectKind.QUESTION, f"Otázka {i}?") for i in range(questions)
    ) + tuple(subject(SubjectKind.OBJECT, f"Objekt {i}") for i in range(objects))
    return DeepResearchRequest(
        harness_version=HARNESS_VERSION,
        design_revision_id="REV-1",
        design_revision=1,
        preset=preset,
        channels=channels,
        brief=BriefDigest(title="t", goal="g", decision_use="", briefing=""),
        subjects=subjects,
        questionnaire=(),
        knowledge=FrozenKnowledge(items=(), omitted_ids=(), retrieval_limit=1),
        client_terms=(),
    )


# --------------------------------------------------------------------------- #
# The preset table
# --------------------------------------------------------------------------- #


def test_the_preset_table_is_versioned_and_proposed_with_every_table_for_every_preset() -> None:
    assert PRESET_TABLE_VERSION == "aia-presets-2-proposed" and PRESET_STATUS == "PROPOSED_DR5"
    assert set(PRESETS) == set(LEAD_LIMITS) == set(ROUTE_ALLOWANCES)
    assert set(PRESETS) == {"QUICK", "STANDARD", "DEEP", "EXHAUSTIVE"}


def test_standard_deep_and_exhaustive_are_section_9_s() -> None:
    standard, deep, exhaustive = (PRESETS[n] for n in ("STANDARD", "DEEP", "EXHAUSTIVE"))
    # Standard: 1 lead; <= 12 tracks; per track 8 searches, 20 opens, 15 turns.
    assert (standard.max_searches, standard.max_opens, standard.max_turns) == (8, 20, 15)
    assert (LEAD_LIMITS["STANDARD"].max_tasks, LEAD_LIMITS["STANDARD"].replans) == (12, 1)
    # Deep: 3 re-plans; <= 20 tracks; per track 15 searches, 40 opens, 30 turns.
    assert (deep.max_searches, deep.max_opens, deep.max_turns) == (15, 40, 30)
    assert (LEAD_LIMITS["DEEP"].max_tasks, LEAD_LIMITS["DEEP"].replans) == (20, 3)
    # Exhaustive: 20-50 investigators, and the widest of the three on every axis.
    assert 20 <= LEAD_LIMITS["EXHAUSTIVE"].max_tasks <= 50
    for field in ("max_turns", "max_searches", "max_opens", "max_tracks", "evidence_target"):
        assert getattr(exhaustive, field) >= getattr(deep, field) >= getattr(standard, field)
    assert all(
        e >= d
        for e, d in zip(LEAD_LIMITS["EXHAUSTIVE"].ceiling, LEAD_LIMITS["DEEP"].ceiling, strict=True)
    )
    # Triage, crawl and Common Crawl: Exhaustive only.
    for name in ("QUICK", "STANDARD", "DEEP"):
        routes = ROUTE_ALLOWANCES[name]
        assert (routes.triage_reads, routes.crawl_pages, routes.index_queries) == (0, 0, 0)
        assert routes.archive_fetches == 0
    routes = ROUTE_ALLOWANCES["EXHAUSTIVE"]
    assert min(routes.triage_reads, routes.crawl_pages, routes.index_queries) > 0


def test_an_exhaustive_lead_ceiling_binds_below_its_tasks_at_the_largest_effort() -> None:
    lead = LEAD_LIMITS["EXHAUSTIVE"]
    largest = max(EFFORT_CAPS.values(), key=lambda c: c.turns)
    turns, searches, opens = lead.ceiling
    assert turns < lead.max_tasks * largest.turns
    assert searches < lead.max_tasks * largest.searches
    assert opens < lead.max_tasks * largest.opens


def test_exhaustive_changes_no_fingerprint_of_the_other_presets() -> None:
    """A new row in the table: the earlier presets' tracks fingerprint as they did."""
    inputs = TrackInputs(policy_version="p", prompt_versions={}, web_retrieval=None)
    req = request(2, 2, channels=(Channel.INTERNAL, Channel.WEB))
    tracks, _ = build_tracks(req, PRESETS["STANDARD"], inputs=inputs)
    exhaustive, _ = build_tracks(req, PRESETS["EXHAUSTIVE"], inputs=inputs)
    assert {t.fingerprint for t in tracks}.isdisjoint({t.fingerprint for t in exhaustive})


# --------------------------------------------------------------------------- #
# Call bounds
# --------------------------------------------------------------------------- #


def test_one_answer_s_evidence_is_read_from_both_investigator_contracts() -> None:
    for contract in (ExtractionProposal, InvestigatorTurn):
        schema = contract.model_json_schema()
        assert schema["properties"]["evidence"]["maxItems"] <= EVIDENCE_PER_ANSWER
    assert EVIDENCE_PER_ANSWER == 12


@pytest.mark.parametrize("name", sorted(PRESETS))
@pytest.mark.parametrize("shape", [(1, 0), (2, 3), (12, 40)])
def test_track_counts_are_what_build_tracks_opens(name: str, shape: tuple[int, int]) -> None:
    req = request(*shape, preset=name, channels=(Channel.INTERNAL, Channel.WEB))
    depth = PRESETS[name]
    tracks, _ = build_tracks(
        req, depth, inputs=TrackInputs(policy_version="p", prompt_versions={}, web_retrieval=None)
    )
    counts = track_counts(req, depth)
    assert counts.web == sum(1 for t in tracks if t.channel is Channel.WEB)
    assert counts.internal == sum(1 for t in tracks if t.channel is Channel.INTERNAL)


def test_a_planned_track_asks_once_per_search_and_the_bounds_name_every_kind() -> None:
    depth = PRESETS["STANDARD"]
    bounds = call_bounds(depth, TrackCounts(web=3, internal=2), ResearchMode.PLANNED)
    assert set(bounds.counts) == set(CallKind)
    assert bounds[CallKind.SEARCH] == 3 * depth.queries_per_web_track
    assert bounds[CallKind.INVESTIGATOR] == bounds[CallKind.SEARCH]
    assert bounds[CallKind.FETCH] == 3 * depth.queries_per_web_track * depth.pages_per_query
    assert (bounds[CallKind.PLANNER], bounds[CallKind.LEAD]) == (1, 0)
    assert bounds[CallKind.INTERNAL_INVESTIGATOR] == 2
    assert bounds[CallKind.SYNTHESIZER] == 1
    # Candidates per web track: min(4 requests x 12, 8 - 1 + 12) = 19 -> 2 batches of 12;
    # an internal track's one answer is one batch.
    assert bounds[CallKind.VERIFIER] == 3 * 2 + 2 * 1


def test_an_agent_directed_track_asks_once_per_turn_and_a_lead_within_its_ceiling() -> None:
    depth = PRESETS["DEEP"]
    tracks = TrackCounts(web=30, internal=0)
    directed = call_bounds(depth, tracks, ResearchMode.AGENT_DIRECTED)
    assert directed[CallKind.INVESTIGATOR] == 30 * depth.max_turns
    lead = call_bounds(depth, tracks, ResearchMode.LEAD)
    turns, searches, opens = LEAD_LIMITS["DEEP"].ceiling
    assert lead[CallKind.INVESTIGATOR] == turns
    assert (lead[CallKind.SEARCH], lead[CallKind.FETCH]) == (searches, opens)
    assert lead[CallKind.LEAD] == 1 + LEAD_LIMITS["DEEP"].replans
    assert lead[CallKind.PLANNER] == 0
    # Only tasks are verified: at most max_tasks tracks, each its evidence target's worth.
    per_track = math.ceil((depth.evidence_target - 1 + EVIDENCE_PER_ANSWER) / depth.verify_batch)
    assert lead[CallKind.VERIFIER] == LEAD_LIMITS["DEEP"].max_tasks * per_track


def test_a_run_with_nothing_to_research_calls_nothing_but_its_route_allowances() -> None:
    bounds = call_bounds(PRESETS["STANDARD"], TrackCounts(web=0, internal=0), ResearchMode.LEAD)
    assert all(n == 0 for k, n in bounds.counts.items() if k is not CallKind.CONNECTOR), (
        bounds.counts
    )


def test_call_bounds_state_every_kind_and_refuse_a_preset_without_a_budget() -> None:
    with pytest.raises(ValueError, match="missing"):
        CallBounds({CallKind.SEARCH: 1})
    odd = PRESETS["STANDARD"].model_copy(update={"name": "NOT_IN_THE_TABLE"})
    with pytest.raises(LookupError):
        call_bounds(odd, TrackCounts(web=1, internal=0), ResearchMode.PLANNED)


# --------------------------------------------------------------------------- #
# Prices and the ceiling
# --------------------------------------------------------------------------- #


def test_every_kind_states_its_price_and_a_model_reservation_is_above_zero() -> None:
    with pytest.raises(ValueError, match="missing"):
        DeepResearchPrices({CallKind.SEARCH: RoutePrice.per_call(0.0)})
    with pytest.raises(ValueError, match="above zero"):
        prices(verifier=RoutePrice.per_call(0.0))
    with pytest.raises(ValueError):
        RoutePrice.per_call(float("nan"))
    with pytest.raises(ValueError):
        RoutePrice("off", 1.0)
    assert RoutePrice.of(None) == RoutePrice.unknown()


def test_the_ceiling_is_each_kind_s_calls_times_its_price() -> None:
    depth = PRESETS["STANDARD"]
    tracks = TrackCounts(web=3, internal=2)
    bounds = call_bounds(depth, tracks, ResearchMode.PLANNED)
    ceiling = deep_research_cost_ceiling(depth, tracks, prices(), modes=(ResearchMode.PLANNED,))
    model = sum(bounds[k] for k in MODEL_KINDS)
    assert ceiling.total_usd == pytest.approx(model * RESERVE + bounds[CallKind.SEARCH] * SEARCH)
    assert ceiling.preset == "STANDARD" and ceiling.preset_table == PRESET_TABLE_VERSION
    assert ceiling.unknown is None and ceiling.unknown_kinds == ()


def test_an_unknown_price_the_run_needs_makes_the_ceiling_unknown_not_cheaper() -> None:
    depth = PRESETS["STANDARD"]
    tracks = TrackCounts(web=3, internal=0)
    ceiling = deep_research_cost_ceiling(
        depth, tracks, prices(search=RoutePrice.unknown()), modes=(ResearchMode.PLANNED,)
    )
    assert ceiling.total_usd is None
    assert ceiling.unknown is CeilingUnknown.DEEP_RESEARCH_PRICE_MISSING
    assert ceiling.unknown_kinds == (CallKind.SEARCH,)
    # A kind the run does not call needs no price: an internal-only run never searches.
    internal = deep_research_cost_ceiling(
        depth,
        TrackCounts(web=0, internal=3),
        prices(search=RoutePrice.unknown()),
        modes=(ResearchMode.PLANNED,),
    )
    assert internal.total_usd is not None


def test_a_route_that_is_off_sends_nothing_and_costs_nothing() -> None:
    depth = PRESETS["EXHAUSTIVE"]
    tracks = TrackCounts(web=10, internal=0)
    on = deep_research_cost_ceiling(
        depth, tracks, prices(triage=RoutePrice.per_call(0.01)), modes=(ResearchMode.LEAD,)
    )
    off = deep_research_cost_ceiling(
        depth, tracks, prices(triage=RoutePrice.off()), modes=(ResearchMode.LEAD,)
    )
    assert on.total_usd is not None and off.total_usd is not None
    triage = ROUTE_ALLOWANCES["EXHAUSTIVE"].triage_reads
    assert on.total_usd - off.total_usd == pytest.approx(triage * 0.01)
    # Off, but unknown when on: Exhaustive with an unpriced triage route is unknown.
    unknown = deep_research_cost_ceiling(
        depth, tracks, prices(triage=RoutePrice.unknown()), modes=(ResearchMode.LEAD,)
    )
    assert unknown.unknown_kinds == (CallKind.TRIAGE,)


def test_athena_is_priced_at_its_scan_cutoff_billed() -> None:
    pricing = AthenaPricing(
        usd_per_tb_scanned=5.0, minimum_billed_bytes=10_000_000, billing_increment_bytes=1_000_000
    )
    price = RoutePrice.athena(pricing, 200_000_000_000)  # a 200 GB cutoff
    assert price.usd == pytest.approx(1.0)
    depth = PRESETS["EXHAUSTIVE"]
    tracks = TrackCounts(web=10, internal=0)
    with_index = deep_research_cost_ceiling(
        depth, tracks, prices(url_index_query=price), modes=(ResearchMode.LEAD,)
    )
    without = deep_research_cost_ceiling(
        depth, tracks, prices(url_index_query=RoutePrice.off()), modes=(ResearchMode.LEAD,)
    )
    assert with_index.total_usd is not None and without.total_usd is not None
    queries = ROUTE_ALLOWANCES["EXHAUSTIVE"].index_queries
    assert with_index.total_usd - without.total_usd == pytest.approx(queries * 1.0)


def test_over_every_mode_the_ceiling_is_the_highest_and_unknown_anywhere_is_unknown() -> None:
    depth = PRESETS["DEEP"]
    tracks = TrackCounts(web=8, internal=4)
    each = {
        m: deep_research_cost_ceiling(depth, tracks, prices(), modes=(m,)).total_usd
        for m in ResearchMode
    }
    every = deep_research_cost_ceiling(depth, tracks, prices(), modes=tuple(ResearchMode))
    assert every.total_usd == max(v for v in each.values() if v is not None)
    assert each[every.mode] == every.total_usd
    # The lead is the only mode that asks the lead: an unpriced lead is unknown over all.
    unknown = deep_research_cost_ceiling(
        depth, tracks, prices(lead=RoutePrice.unknown()), modes=tuple(ResearchMode)
    )
    assert unknown.total_usd is None and unknown.unknown_kinds == (CallKind.LEAD,)
    with pytest.raises(ValueError):
        deep_research_cost_ceiling(depth, tracks, prices(), modes=())


@pytest.mark.parametrize("name", ["STANDARD", "DEEP", "EXHAUSTIVE"])
def test_a_deeper_preset_never_has_a_lower_ceiling(name: str) -> None:
    order = ["QUICK", "STANDARD", "DEEP", "EXHAUSTIVE"]
    lower = order[order.index(name) - 1]
    tracks = TrackCounts(web=12, internal=12)
    for mode in ResearchMode:
        high = deep_research_cost_ceiling(PRESETS[name], tracks, prices(), modes=(mode,))
        low = deep_research_cost_ceiling(PRESETS[lower], tracks, prices(), modes=(mode,))
        assert (high.total_usd or 0) >= (low.total_usd or 0), mode


# --------------------------------------------------------------------------- #
# Moving budget never raises the ceiling (property, over seeded random re-plans)
# --------------------------------------------------------------------------- #


def _subjects(n: int) -> tuple[str, ...]:
    return tuple(subject_key(SubjectKind.QUESTION, f"Otázka {i}?") for i in range(n))


def _limits(name: str, subjects: tuple[str, ...]) -> LeadLimits:
    depth = PRESETS[name]
    return lead_limits(
        name,
        subjects=subjects,
        max_turns=depth.max_turns,
        max_searches=depth.max_searches,
        max_opens=depth.max_opens,
        max_search_calls=depth.max_search_calls,
        max_fetches=depth.max_fetches,
    )


def _task(
    task_id: str, subject: str, measure: str, budget: tuple[int, int, int], **kw: Any
) -> SubagentTask:
    turns, searches, opens = budget
    return SubagentTask(
        task_id=task_id,
        kind=kw.get("kind", TaskKind.RESEARCH),
        subject_key=subject,
        measure=measure,
        objective="Zjistit.",
        wanted_output="Číslo.",
        prefer_sources=[],
        boundaries=[],
        budget=TaskBudget(turns=turns, searches=searches, opens=opens),
        addresses=list(kw.get("addresses", [])),
        reason=kw.get("reason"),
    )


def _random_plan(rng: random.Random, limits: LeadLimits) -> ResearchPlan:
    """Every subject complex, three tasks each, budgets drawn within the caps and ceiling."""
    cap = limits.cap(Complexity.COMPLEX)
    per_task = len(limits.subjects) * 3
    share = (
        limits.ceiling.turns // per_task,
        limits.ceiling.searches // per_task,
        limits.ceiling.opens // per_task,
    )
    tasks = []
    for i, key in enumerate(limits.subjects):
        for j in range(3):
            budget = (
                rng.randint(1, max(1, min(cap.turns, share[0]))),
                rng.randint(0, min(cap.searches, share[1])),
                rng.randint(0, min(cap.opens, share[2])),
            )
            tasks.append(_task(f"T{3 * i + j + 1}", key, f"míra {i}-{j}", budget))
    waves = [tasks[k : k + 5] for k in range(0, len(tasks), 5)]
    return ResearchPlan.model_validate(
        {
            "subjects": [
                {
                    "subject_key": key,
                    "questions": [],
                    "complexity": Complexity.COMPLEX,
                    "effort": 3,
                    "rationale": "",
                }
                for key in limits.subjects
            ],
            "waves": [Wave(tasks=w) for w in waves],
            "notes": "",
        }
    )


def move_allotment(move: BudgetMove) -> Allotment:
    return Allotment(turns=move.turns, searches=move.searches, opens=move.opens)


def _random_replan(rng: random.Random, state: LeadState, next_id: int) -> Replan:
    pending = state.pending_ids()
    budgets = {t: state.tasks[t].budget.allotment() for t in pending}
    moves = []
    for _ in range(rng.randint(0, 4)):
        if len(pending) < 2:
            break
        a, b = rng.sample(pending, 2)
        cap = state.limits.cap(state.complexity[state.tasks[b].subject_key])
        source, target = budgets[a], budgets[b]
        # Mostly a move code accepts (within the source and the target's cap); now and
        # then one it refuses, which must change nothing.
        slack = 0 if rng.random() < 0.85 else 2
        move = BudgetMove(
            from_task=a,
            to_task=b,
            turns=rng.randint(0, max(0, min(source.turns - 1, cap.turns - target.turns) + slack)),
            searches=rng.randint(0, max(0, min(source.searches, cap.searches - target.searches))),
            opens=rng.randint(0, max(0, min(source.opens, cap.opens - target.opens))),
        )
        moves.append(move)
        budgets[a] = source.model_copy(
            update={
                "turns": max(0, source.turns - move.turns),
                "searches": source.searches - move.searches,
                "opens": source.opens - move.opens,
            }
        )
        budgets[b] = target + move_allotment(move)
    wave = []
    if state.used and rng.random() < 0.5:
        finished = sorted(state.used)
        source = state.tasks[rng.choice(finished)]
        wave.append(
            _task(
                f"T{next_id}",
                source.subject_key,
                f"mezera {next_id}",
                (rng.randint(1, 6), rng.randint(0, 4), rng.randint(0, 6)),
                kind=TaskKind.GAP,
                addresses=[source.task_id],
                reason="Chybí údaj.",
            )
        )
    return Replan(next_wave=wave, moves=moves, routed=[], notes="")


@pytest.mark.parametrize("name", ["STANDARD", "DEEP", "EXHAUSTIVE"])
def test_moving_budget_never_raises_the_ceiling(name: str) -> None:
    pricing = prices()
    moved = 0
    for seed in range(100):
        rng = random.Random(seed)
        subjects = _subjects(rng.randint(1, LEAD_LIMITS[name].max_tasks // 3))
        limits = _limits(name, subjects)
        depth = PRESETS[name]
        start = call_bounds(depth, TrackCounts(web=len(subjects), internal=0), ResearchMode.LEAD)
        ceiling = price_bounds(start, pricing, preset=name, mode=ResearchMode.LEAD).total_usd
        assert ceiling is not None
        state = LeadState.start(_random_plan(rng, limits), limits)
        next_id = len(state.tasks) + 1

        def bound(state: LeadState = state, start: CallBounds = start) -> float:
            committed = state.committed()
            priced = price_bounds(
                lead_state_bounds(
                    start,
                    committed=(committed.turns, committed.searches, committed.opens),
                    replans_allowed=state.limits.replans,
                ),
                pricing,
                preset=name,
                mode=ResearchMode.LEAD,
            ).total_usd
            assert priced is not None
            return priced

        assert bound() <= ceiling + 1e-9
        while True:
            wave = state.next_wave()
            if not wave:
                break
            state.finish(
                {
                    t.task_id: t.budget.allotment().model_copy(
                        update={"turns": rng.randint(0, t.budget.turns)}
                    )
                    for t in wave
                }
            )
            while state.may_replan and rng.random() < 0.8:
                before = bound()
                replan = _random_replan(rng, state, next_id)
                if state.check_replan(replan):
                    state.refused()
                    assert bound() == before
                    continue
                state.apply(replan)
                next_id += len(replan.next_wave)
                after = bound()
                assert after <= ceiling + 1e-9, (seed, after, ceiling)
                moved += bool(replan.moves)
                if not replan.next_wave:
                    # Moves alone: what is committed, so the bound, is unchanged.
                    assert after == pytest.approx(before)
                break
    # Not vacuous: accepted re-plans moved budget in this run of the property.
    assert moved >= 10


def test_the_lead_state_bounds_of_a_fresh_plan_are_within_the_start_s() -> None:
    limits = _limits("STANDARD", _subjects(2))
    start = call_bounds(PRESETS["STANDARD"], TrackCounts(web=2, internal=0), ResearchMode.LEAD)
    state = LeadState.start(_random_plan(random.Random(7), limits), limits)
    committed = state.committed()
    after = lead_state_bounds(
        start,
        committed=(committed.turns, committed.searches, committed.opens),
        replans_allowed=limits.replans,
    )
    for kind in CallKind:
        assert after[kind] <= start[kind], kind


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (ResearchMode.PLANNED, 1),
        (ResearchMode.AGENT_DIRECTED, 2),
        (ResearchMode.LEAD, 2),
    ],
)
def test_a_brief_and_its_one_repair_are_both_counted(mode: ResearchMode, expected: int) -> None:
    """The agent-directed brief is asked again once to repair its numbers (chunk 13); that
    second request is paid, so the ceiling counts it."""
    bounds = call_bounds(PRESETS["STANDARD"], TrackCounts(web=1, internal=0), mode)
    assert bounds[CallKind.SYNTHESIZER] == expected
