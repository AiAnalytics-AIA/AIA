"""The lead researcher: subjects sized by effort, waves of tasks, re-planned after each wave.

Plan ``deep-research-web-search.md`` § 1, § 5.2, § 9, chunk 11. In the agent-directed
mode with the lead switched on, a run's web research is not one track per subject but
what a **lead researcher** plans: for each subject its questions, how complex it is and
how much effort it deserves (how many tasks), and the tasks themselves -- each a
closed brief for one investigator track (objective, wanted output, sources to
prefer, boundaries, budget) -- grouped into **waves** that run one after another.
After a wave the lead **re-plans**: tracks for the gaps it left, *resolve* tracks for
conflicting findings, budget moved between tasks not yet run, and notes routed from
a finished task to a later one.

The lead only proposes. This module is what code decides about a proposal:

* **Effort caps by complexity** (:data:`EFFORT_CAPS`, proposed with the presets,
  DR-5): a simple fact gets one task, a comparison two to four, complex research
  three to eight; each task's budget is capped by its subject's complexity and by
  the preset's per-track allowance.
* **Waves** of :data:`MIN_TASKS_PER_WAVE`--:data:`MAX_TASKS_PER_WAVE` tasks; only the
  plan's last wave may be smaller (a run of one simple subject is one task).
* **No overlap**: no two tasks with the same subject and measure (the measure's
  normalised text). A gap or resolve task may share a finished task's measure --
  that is its point -- but not a task still to run.
* **The run's ceiling** (:class:`LeadLimits`): what finished tasks used plus what
  every task still to run may use never exceeds it, in turns, searches and opens.
  Moving budget never changes the total: a move is a transfer between two tasks not
  yet run, checked so.
* **The re-plan limit**: a preset allows a number of re-plans; a refused one counts.

The checks run inside the gateway's own validation: :func:`bound_plan_contract` and
:func:`bound_replan_contract` give the output contract a validator that knows the
limits (and, for a re-plan, the run's state), so a refused proposal is a schema
violation with every reason named, and takes the gateway's one repair like any other.
The contract's JSON Schema is the unbound contract's, byte for byte: what the model is
shown does not depend on the limits; the limits are in the request.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Any, ClassVar, Final, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import Channel, ResearchSubject, ResearchTrack, digest, normalise_label, track_id

__all__ = [
    "EFFORT_CAPS",
    "EFFORT_CAPS_VERSION",
    "LEAD_CONTRACT_VERSION",
    "LEAD_LIMITS",
    "LEAD_PROMPT_VERSION",
    "LEAD_VERSION",
    "MAX_TASKS_PER_WAVE",
    "MIN_TASKS_PER_WAVE",
    "Allotment",
    "BudgetMove",
    "Complexity",
    "EffortCap",
    "LeadLimits",
    "LeadState",
    "PlanRefusal",
    "Replan",
    "ResearchPlan",
    "RoutedFinding",
    "SubagentTask",
    "SubjectPlan",
    "TaskBudget",
    "TaskKind",
    "Wave",
    "bound_plan_contract",
    "bound_replan_contract",
    "check_plan",
    "lead_limits",
    "lead_track",
    "lead_track_id",
]

#: The contracts :class:`ResearchPlan` and :class:`Replan`. A new field is a new version.
LEAD_CONTRACT_VERSION: Final = "lead-plan-1"
#: The lead's prompts (plan and re-plan change together).
LEAD_PROMPT_VERSION: Final = "1"
#: :data:`EFFORT_CAPS` and :data:`LEAD_LIMITS`: proposed with the presets (DR-5).
EFFORT_CAPS_VERSION: Final = "aia-lead-effort-1-proposed"
#: Everything a lead-planned run depends on beyond the agent-directed mode's rules.
LEAD_VERSION: Final = (
    f"aia-lead-1/{LEAD_CONTRACT_VERSION}/prompt-{LEAD_PROMPT_VERSION}/{EFFORT_CAPS_VERSION}"
)

#: A wave holds at most this many tasks, and every wave but the plan's last at least
#: :data:`MIN_TASKS_PER_WAVE` (plan § 1: waves of 3-5 subagent tasks).
MAX_TASKS_PER_WAVE: Final = 5
MIN_TASKS_PER_WAVE: Final = 3


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_Line = Annotated[str, Field(min_length=1, max_length=300)]
_Text = Annotated[str, Field(min_length=1, max_length=600)]
_Id = Annotated[str, Field(min_length=1, max_length=100)]
_TaskId = Annotated[str, Field(pattern=r"^T[1-9][0-9]{0,2}$")]


# --------------------------------------------------------------------------- #
# Effort by complexity, and each preset's limits (proposed, DR-5)
# --------------------------------------------------------------------------- #


class Complexity(StrEnum):
    """How much research a subject needs (Anthropic's effort-scaling rules, plan § 9)."""

    #: One fact: one task.
    SIMPLE = "simple"
    #: A comparison of a few things: a task per side.
    COMPARISON = "comparison"
    #: Complex research with divided responsibilities.
    COMPLEX = "complex"


class TaskKind(StrEnum):
    """What a task is for. A plan holds only research; a re-plan only gap and resolve."""

    RESEARCH = "research"
    #: Take up what a finished task could not establish.
    GAP = "gap"
    #: Find each conflicting value's primary source and explain the difference.
    RESOLVE = "resolve"


@dataclass(frozen=True, slots=True)
class EffortCap:
    """Tasks a subject of one complexity gets, and what each task may use at most."""

    min_tasks: int
    max_tasks: int
    turns: int
    searches: int
    opens: int


#: Proposed (DR-5), from plan § 9: a simple fact is one track of 3-10 tool calls; a
#: comparison 2-4 tracks of 10-15 calls each; complex research more tracks, each up to
#: the preset's per-track allowance (STANDARD: 15 turns, 8 searches, 20 opens).
EFFORT_CAPS: Final[Mapping[Complexity, EffortCap]] = {
    Complexity.SIMPLE: EffortCap(min_tasks=1, max_tasks=1, turns=6, searches=4, opens=6),
    Complexity.COMPARISON: EffortCap(min_tasks=2, max_tasks=4, turns=10, searches=6, opens=9),
    Complexity.COMPLEX: EffortCap(min_tasks=3, max_tasks=8, turns=15, searches=8, opens=20),
}


class Allotment(_Closed):
    """Turns, searches and opens: a total, a ceiling, or what a task used."""

    turns: int = Field(ge=0)
    searches: int = Field(ge=0)
    opens: int = Field(ge=0)

    def __add__(self, other: Allotment) -> Allotment:
        return Allotment(
            turns=self.turns + other.turns,
            searches=self.searches + other.searches,
            opens=self.opens + other.opens,
        )

    def within(self, ceiling: Allotment) -> bool:
        return (
            self.turns <= ceiling.turns
            and self.searches <= ceiling.searches
            and self.opens <= ceiling.opens
        )


_ZERO: Final = Allotment(turns=0, searches=0, opens=0)


@dataclass(frozen=True, slots=True)
class _PresetLead:
    max_tasks: int
    replans: int
    ceiling: tuple[int, int, int]


#: Per preset (proposed, DR-5; plan § 9): tasks a run may hold in all (the plan's and
#: every re-plan's), re-plans allowed, and the run's ceiling in (turns, searches, opens)
#: -- below tasks x per-track allowance, so the ceiling binds on its own. At about $0.04
#: a turn, STANDARD's 120 turns are about $5 and DEEP's 360 about $14 of investigation.
LEAD_LIMITS: Final[Mapping[str, _PresetLead]] = {
    "QUICK": _PresetLead(max_tasks=4, replans=0, ceiling=(16, 12, 24)),
    "STANDARD": _PresetLead(max_tasks=12, replans=1, ceiling=(120, 64, 160)),
    "DEEP": _PresetLead(max_tasks=20, replans=3, ceiling=(360, 200, 500)),
    # Chunk 22 (``planning.PRESET_TABLE_VERSION``): 20-50 investigators under one lead
    # (the subject leads § 9 names are not built). Below 50 tasks at the effort table's
    # largest task (15/8/20), so the ceiling binds on its own; at about $0.04 a turn its
    # 720 turns are about $29 of investigation.
    "EXHAUSTIVE": _PresetLead(max_tasks=50, replans=6, ceiling=(720, 384, 960)),
}


class LeadLimits(_Closed):
    """What code holds a lead's plan and re-plans to, for one run. Recorded on the plan."""

    #: The subjects the lead plans, in order (``ResearchSubject.key``).
    subjects: tuple[str, ...]
    max_tasks: int = Field(ge=1)
    replans: int = Field(ge=0)
    #: The preset's allowance of one track: no task's budget exceeds it.
    per_task: Allotment
    #: The run's ceiling: finished tasks' use plus every pending budget, never above.
    ceiling: Allotment

    def cap(self, complexity: Complexity) -> Allotment:
        """A task's budget cap: its subject's complexity, within the preset's per track."""
        effort = EFFORT_CAPS[complexity]
        return Allotment(
            turns=min(effort.turns, self.per_task.turns),
            searches=min(effort.searches, self.per_task.searches),
            opens=min(effort.opens, self.per_task.opens),
        )


def lead_limits(
    preset_name: str,
    *,
    subjects: Sequence[str],
    max_turns: int,
    max_searches: int,
    max_opens: int,
    max_search_calls: int,
    max_fetches: int,
) -> LeadLimits:
    """One run's limits from its preset: the lead's table, within the preset's own limits."""
    lead = LEAD_LIMITS[preset_name]
    turns, searches, opens = lead.ceiling
    return LeadLimits(
        subjects=tuple(subjects),
        max_tasks=lead.max_tasks,
        replans=lead.replans,
        per_task=Allotment(turns=max_turns, searches=max_searches, opens=max_opens),
        ceiling=Allotment(
            turns=turns,
            searches=min(searches, max_search_calls),
            opens=min(opens, max_fetches),
        ),
    )


# --------------------------------------------------------------------------- #
# The contracts the lead answers in
# --------------------------------------------------------------------------- #


class TaskBudget(_Closed):
    """What one task's track may use: investigator turns, searches sent, pages opened."""

    turns: int = Field(ge=1, le=60)
    searches: int = Field(ge=0, le=100)
    opens: int = Field(ge=0, le=200)

    def allotment(self) -> Allotment:
        return Allotment(turns=self.turns, searches=self.searches, opens=self.opens)


class SubagentTask(_Closed):
    """One investigator's brief: a closed task contract (plan § 3: no vague delegation)."""

    task_id: _TaskId
    kind: TaskKind
    subject_key: _Id
    #: What the task measures: the indicator, its population, place and period. Two
    #: tasks with the same subject and measure duplicate each other and are refused.
    measure: _Line
    objective: _Text
    wanted_output: _Text
    prefer_sources: list[_Line] = Field(max_length=5)
    boundaries: list[_Line] = Field(max_length=5)
    budget: TaskBudget
    #: For a gap or resolve task: the finished tasks whose gap or conflict it takes up.
    addresses: list[_TaskId] = Field(max_length=5)
    #: For a gap or resolve task: the gap, or the conflict. ``null`` for research.
    reason: str | None = Field(max_length=600)


class Wave(_Closed):
    """Tasks that run together; the next wave starts when this one is done."""

    tasks: list[SubagentTask] = Field(min_length=1, max_length=MAX_TASKS_PER_WAVE)


class SubjectPlan(_Closed):
    """One subject as the lead sizes it: its questions, complexity and effort."""

    subject_key: _Id
    questions: list[_Line] = Field(max_length=5)
    complexity: Complexity
    #: How many tasks the subject gets; within its complexity's range.
    effort: int = Field(ge=1, le=12)
    rationale: str = Field(max_length=600)


#: A check a bound contract runs: the problems, each ``reason: detail``; none passes.
_Check = Callable[[BaseModel], tuple[str, ...]]


class _Checked(_Closed):
    """A contract whose bound form runs a check of code's inside validation."""

    _check: ClassVar[_Check | None] = None

    @model_validator(mode="after")
    def _within_limits(self) -> Self:
        check = type(self)._check
        if check is not None:
            problems = check(self)
            if problems:
                raise ValueError("; ".join(problems))
        return self


class ResearchPlan(_Checked):
    """The lead's plan: every subject sized, every task in a wave."""

    subjects: list[SubjectPlan] = Field(max_length=60)
    waves: list[Wave] = Field(min_length=1, max_length=12)
    notes: str = Field(max_length=2000)

    def tasks(self) -> list[SubagentTask]:
        return [t for wave in self.waves for t in wave.tasks]


class BudgetMove(_Closed):
    """Budget moved from one task not yet run to another; the total does not change."""

    from_task: _TaskId
    to_task: _TaskId
    turns: int = Field(ge=0, le=60)
    searches: int = Field(ge=0, le=100)
    opens: int = Field(ge=0, le=200)


class RoutedFinding(_Closed):
    """What a finished task found that a later task should know (its brief carries it)."""

    from_task: _TaskId
    to_task: _TaskId
    note: _Text


class Replan(_Checked):
    """The lead after a wave: tracks for gaps and conflicts, budget moved, findings routed."""

    next_wave: list[SubagentTask] = Field(max_length=MAX_TASKS_PER_WAVE)
    moves: list[BudgetMove] = Field(max_length=10)
    routed: list[RoutedFinding] = Field(max_length=10)
    notes: str = Field(max_length=2000)


# --------------------------------------------------------------------------- #
# What code checks
# --------------------------------------------------------------------------- #


class PlanRefusal(StrEnum):
    """Why code refuses a plan or a re-plan. Each problem names one."""

    UNKNOWN_SUBJECT = "unknown_subject"
    SUBJECT_NOT_PLANNED = "subject_not_planned"
    SUBJECT_PLANNED_TWICE = "subject_planned_twice"
    EFFORT_OUTSIDE_COMPLEXITY = "effort_outside_complexity"
    TASKS_NOT_EFFORT = "tasks_not_effort"
    DUPLICATE_TASK_ID = "duplicate_task_id"
    OVERLAPPING_TASKS = "overlapping_tasks"
    WAVE_SIZE = "wave_size"
    KIND_NOT_ALLOWED = "kind_not_allowed"
    REASON_MISSING = "reason_missing"
    ADDRESSES_INVALID = "addresses_invalid"
    BUDGET_OVER_CAP = "budget_over_cap"
    TOO_MANY_TASKS = "too_many_tasks"
    CEILING_EXCEEDED = "ceiling_exceeded"
    REPLAN_LIMIT = "replan_limit"
    MOVE_NOT_PENDING = "move_not_pending"
    MOVE_OVERDRAWN = "move_overdrawn"
    ROUTE_INVALID = "route_invalid"


def _problem(reason: PlanRefusal, detail: str) -> str:
    return f"{reason.value}: {detail}"


def _total(budgets: Sequence[Allotment]) -> Allotment:
    total = _ZERO
    for b in budgets:
        total = total + b
    return total


def _over(name: str, value: Allotment, cap: Allotment) -> str | None:
    if value.within(cap):
        return None
    return (
        f"{name} {value.turns}/{value.searches}/{value.opens} "
        f"over {cap.turns}/{cap.searches}/{cap.opens} (turns/searches/opens)"
    )


def _overlaps(tasks: Sequence[SubagentTask], against: Mapping[tuple[str, str], str]) -> list[str]:
    """Each task sharing its subject and measure with another, or with ``against``."""
    seen = dict(against)
    out = []
    for task in tasks:
        key = (task.subject_key, normalise_label(task.measure))
        other = seen.get(key)
        if other is not None:
            out.append(
                _problem(
                    PlanRefusal.OVERLAPPING_TASKS,
                    f"{task.task_id} and {other} share subject {task.subject_key} "
                    f"and measure {task.measure!r}",
                )
            )
        else:
            seen[key] = task.task_id
    return out


def check_plan(plan: ResearchPlan, limits: LeadLimits) -> tuple[str, ...]:
    """Every problem with a plan against a run's limits; empty when it may run."""
    problems: list[str] = []
    known = set(limits.subjects)
    sized: dict[str, SubjectPlan] = {}
    for subject in plan.subjects:
        if subject.subject_key not in known:
            problems.append(_problem(PlanRefusal.UNKNOWN_SUBJECT, subject.subject_key))
        elif subject.subject_key in sized:
            problems.append(_problem(PlanRefusal.SUBJECT_PLANNED_TWICE, subject.subject_key))
        else:
            sized[subject.subject_key] = subject
        cap = EFFORT_CAPS[subject.complexity]
        if not cap.min_tasks <= subject.effort <= cap.max_tasks:
            problems.append(
                _problem(
                    PlanRefusal.EFFORT_OUTSIDE_COMPLEXITY,
                    f"{subject.subject_key} is {subject.complexity.value} with effort "
                    f"{subject.effort}; {subject.complexity.value} is "
                    f"{cap.min_tasks}-{cap.max_tasks} tasks",
                )
            )
    problems += [
        _problem(PlanRefusal.SUBJECT_NOT_PLANNED, key)
        for key in limits.subjects
        if key not in sized
    ]

    tasks = plan.tasks()
    ids = Counter(t.task_id for t in tasks)
    problems += [
        _problem(PlanRefusal.DUPLICATE_TASK_ID, task_id) for task_id, n in ids.items() if n > 1
    ]
    for task in tasks:
        if task.kind is not TaskKind.RESEARCH or task.addresses or task.reason is not None:
            problems.append(
                _problem(
                    PlanRefusal.KIND_NOT_ALLOWED,
                    f"{task.task_id}: a plan holds research tasks only, with no addresses "
                    "and no reason",
                )
            )
        owner = sized.get(task.subject_key)
        if owner is None:
            # A known subject the plan did not size is already "subject_not_planned".
            if task.subject_key not in known:
                problems.append(
                    _problem(PlanRefusal.UNKNOWN_SUBJECT, f"{task.task_id}: {task.subject_key}")
                )
            continue
        over = _over(
            f"{task.task_id} budget", task.budget.allotment(), limits.cap(owner.complexity)
        )
        if over is not None:
            problems.append(_problem(PlanRefusal.BUDGET_OVER_CAP, over))
    per_subject = Counter(t.subject_key for t in tasks)
    problems += [
        _problem(
            PlanRefusal.TASKS_NOT_EFFORT,
            f"{key} has effort {s.effort} and {per_subject.get(key, 0)} tasks",
        )
        for key, s in sized.items()
        if per_subject.get(key, 0) != s.effort
    ]
    problems += _overlaps(tasks, {})
    last = len(plan.waves) - 1
    problems += [
        _problem(
            PlanRefusal.WAVE_SIZE,
            f"wave {i + 1} has {len(w.tasks)} tasks; every wave but the last has "
            f"{MIN_TASKS_PER_WAVE}-{MAX_TASKS_PER_WAVE}",
        )
        for i, w in enumerate(plan.waves)
        if i < last and len(w.tasks) < MIN_TASKS_PER_WAVE
    ]
    if len(tasks) > limits.max_tasks:
        problems.append(
            _problem(
                PlanRefusal.TOO_MANY_TASKS,
                f"{len(tasks)} tasks; the run holds at most {limits.max_tasks}",
            )
        )
    over = _over(
        "the plan's budgets", _total([t.budget.allotment() for t in tasks]), limits.ceiling
    )
    if over is not None:
        problems.append(_problem(PlanRefusal.CEILING_EXCEEDED, over))
    return tuple(problems)


def _bind(contract: type[_Checked], check: _Check) -> type[_Checked]:
    """``contract`` with ``check`` run inside its validation; its JSON Schema unchanged."""
    # The same name, module and docstring: the schema's title and description are the
    # contract's own, so the model is shown exactly what the unbound contract shows.
    namespace: dict[str, Any] = {
        "_check": staticmethod(check),
        "__module__": contract.__module__,
        "__doc__": contract.__doc__,
        "__qualname__": contract.__qualname__,
    }
    return cast(type[_Checked], type(contract.__name__, (contract,), namespace))


def bound_plan_contract(limits: LeadLimits) -> type[ResearchPlan]:
    """:class:`ResearchPlan` refusing, in validation, any plan :func:`check_plan` refuses."""
    return cast(
        type[ResearchPlan],
        _bind(ResearchPlan, lambda plan: check_plan(cast(ResearchPlan, plan), limits)),
    )


def bound_replan_contract(state: LeadState) -> type[Replan]:
    """:class:`Replan` refusing, in validation, any re-plan the run's state refuses."""
    return cast(
        type[Replan],
        _bind(Replan, lambda replan: state.check_replan(cast(Replan, replan))),
    )


# --------------------------------------------------------------------------- #
# The run's state between waves
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class LeadState:
    """A lead-planned run's tasks between waves: built from the plan and its re-plans.

    Applying the same plan and the same re-plans in order gives the same state --
    live, or replayed by a retried step from their stored records.
    """

    limits: LeadLimits
    complexity: dict[str, Complexity]
    questions: dict[str, tuple[str, ...]]
    #: Every task in its current form (a moved budget is its budget now).
    tasks: dict[str, SubagentTask]
    #: Waves not yet started, as task ids, in the order they run.
    pending: list[list[str]]
    #: Tasks of the wave running now.
    running: list[str] = field(default_factory=list)
    #: What each finished task used.
    used: dict[str, Allotment] = field(default_factory=dict)
    #: Notes routed to a task: (from task, note), in the order routed.
    notes: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    replans: int = 0

    @classmethod
    def start(cls, plan: ResearchPlan, limits: LeadLimits) -> LeadState:
        problems = check_plan(plan, limits)
        if problems:
            raise ValueError("; ".join(problems))
        return cls(
            limits=limits,
            complexity={s.subject_key: s.complexity for s in plan.subjects},
            questions={s.subject_key: tuple(s.questions) for s in plan.subjects},
            tasks={t.task_id: t for t in plan.tasks()},
            pending=[[t.task_id for t in w.tasks] for w in plan.waves],
        )

    # -- waves -----------------------------------------------------------------

    def next_wave(self) -> tuple[SubagentTask, ...]:
        """The next wave's tasks (now running); empty when every wave has run."""
        if self.running:
            raise RuntimeError("the running wave has not finished")
        if not self.pending:
            return ()
        self.running = self.pending.pop(0)
        return tuple(self.tasks[t] for t in self.running)

    def finish(self, used: Mapping[str, Allotment]) -> None:
        """The running wave is done; ``used`` says what each of its tasks used."""
        if set(used) != set(self.running):
            raise ValueError("a finished wave reports every task it ran, and no other")
        self.used.update(used)
        self.running = []

    # -- totals ----------------------------------------------------------------

    def pending_ids(self) -> list[str]:
        return [t for wave in self.pending for t in wave]

    def pending_total(self) -> Allotment:
        return _total([self.tasks[t].budget.allotment() for t in self.pending_ids()])

    def committed(self) -> Allotment:
        """What finished tasks used, plus what running and pending tasks may use."""
        return (
            _total(list(self.used.values()))
            + _total([self.tasks[t].budget.allotment() for t in self.running])
            + self.pending_total()
        )

    @property
    def may_replan(self) -> bool:
        return self.replans < self.limits.replans

    # -- re-plans --------------------------------------------------------------

    def check_replan(self, replan: Replan) -> tuple[str, ...]:
        """Every problem with a re-plan in this state; empty when it may be applied."""
        problems: list[str] = []
        if not self.may_replan:
            problems.append(
                _problem(
                    PlanRefusal.REPLAN_LIMIT,
                    f"{self.replans} re-plans made; the run allows {self.limits.replans}",
                )
            )
        if self.running:
            problems.append(
                _problem(PlanRefusal.REPLAN_LIMIT, "a re-plan comes after a wave, not during")
            )
        pending = set(self.pending_ids())
        finished = set(self.used)
        new = {t.task_id for t in replan.next_wave}
        ids = Counter(t.task_id for t in replan.next_wave)
        problems += [
            _problem(PlanRefusal.DUPLICATE_TASK_ID, t)
            for t, n in ids.items()
            if n > 1 or t in self.tasks
        ]
        for task in replan.next_wave:
            if task.kind is TaskKind.RESEARCH:
                problems.append(
                    _problem(
                        PlanRefusal.KIND_NOT_ALLOWED,
                        f"{task.task_id}: a re-plan adds gap and resolve tasks only",
                    )
                )
            if task.reason is None or not task.reason.strip():
                problems.append(_problem(PlanRefusal.REASON_MISSING, task.task_id))
            if not task.addresses or any(a not in finished for a in task.addresses):
                problems.append(
                    _problem(
                        PlanRefusal.ADDRESSES_INVALID,
                        f"{task.task_id} addresses {task.addresses}; it must name finished tasks",
                    )
                )
            complexity = self.complexity.get(task.subject_key)
            if complexity is None:
                problems.append(
                    _problem(PlanRefusal.UNKNOWN_SUBJECT, f"{task.task_id}: {task.subject_key}")
                )
                continue
            over = _over(
                f"{task.task_id} budget", task.budget.allotment(), self.limits.cap(complexity)
            )
            if over is not None:
                problems.append(_problem(PlanRefusal.BUDGET_OVER_CAP, over))
        problems += _overlaps(
            replan.next_wave,
            {
                (self.tasks[t].subject_key, normalise_label(self.tasks[t].measure)): t
                for t in self.pending_ids()
            },
        )
        if len(self.tasks) + len(new) > self.limits.max_tasks:
            problems.append(
                _problem(
                    PlanRefusal.TOO_MANY_TASKS,
                    f"{len(self.tasks) + len(new)} tasks; the run holds at most "
                    f"{self.limits.max_tasks}",
                )
            )
        budgets, move_problems = self._moved(replan.moves, pending)
        problems += move_problems
        for route in replan.routed:
            if route.from_task not in finished or route.to_task not in pending | new:
                problems.append(
                    _problem(
                        PlanRefusal.ROUTE_INVALID,
                        f"{route.from_task} -> {route.to_task}: a note goes from a finished "
                        "task to one still to run",
                    )
                )
        after = (
            _total(list(self.used.values()))
            + _total(list(budgets.values()))
            + _total([t.budget.allotment() for t in replan.next_wave])
        )
        over = _over("finished use and pending budgets", after, self.limits.ceiling)
        if over is not None:
            problems.append(_problem(PlanRefusal.CEILING_EXCEEDED, over))
        return tuple(problems)

    def _moved(
        self, moves: Sequence[BudgetMove], pending: set[str]
    ) -> tuple[dict[str, Allotment], list[str]]:
        """Pending budgets after ``moves``, applied in order, and what was wrong with them."""
        budgets = {t: self.tasks[t].budget.allotment() for t in self.pending_ids()}
        problems: list[str] = []
        for move in moves:
            name = f"{move.from_task} -> {move.to_task}"
            if move.from_task not in pending or move.to_task not in pending:
                problems.append(
                    _problem(
                        PlanRefusal.MOVE_NOT_PENDING,
                        f"{name}: budget moves only between tasks still to run",
                    )
                )
                continue
            if move.from_task == move.to_task:
                problems.append(_problem(PlanRefusal.MOVE_NOT_PENDING, f"{name}: the same task"))
                continue
            source = budgets[move.from_task]
            if (
                move.turns > source.turns - 1
                or move.searches > source.searches
                or move.opens > source.opens
            ):
                problems.append(
                    _problem(
                        PlanRefusal.MOVE_OVERDRAWN,
                        f"{name}: {move.from_task} has {source.turns}/{source.searches}/"
                        f"{source.opens} and keeps at least one turn",
                    )
                )
                continue
            amount = Allotment(turns=move.turns, searches=move.searches, opens=move.opens)
            budgets[move.from_task] = Allotment(
                turns=source.turns - amount.turns,
                searches=source.searches - amount.searches,
                opens=source.opens - amount.opens,
            )
            budgets[move.to_task] = budgets[move.to_task] + amount
        for task_id, budget in budgets.items():
            over = _over(
                f"{task_id} budget after the moves",
                budget,
                self.limits.cap(self.complexity[self.tasks[task_id].subject_key]),
            )
            if over is not None:
                problems.append(_problem(PlanRefusal.BUDGET_OVER_CAP, over))
        return budgets, problems

    def apply(self, replan: Replan) -> tuple[Allotment, Allotment]:
        """Take a re-plan in: its wave runs next, moves and notes land. Refused: raises.

        Returns the budgets of the tasks that were pending, before and after the moves:
        a move changes two pending budgets and never their total (checked here again).
        """
        problems = self.check_replan(replan)
        if problems:
            raise ValueError("; ".join(problems))
        before = self.pending_total()
        budgets, _ = self._moved(replan.moves, set(self.pending_ids()))
        for task_id, budget in budgets.items():
            self.tasks[task_id] = self.tasks[task_id].model_copy(
                update={"budget": TaskBudget(**budget.model_dump())}
            )
        after = self.pending_total()
        if after != before:
            raise AssertionError("a budget move changed the pending total")
        for task in replan.next_wave:
            self.tasks[task.task_id] = task
        if replan.next_wave:
            self.pending.insert(0, [t.task_id for t in replan.next_wave])
        for route in replan.routed:
            self.notes.setdefault(route.to_task, []).append((route.from_task, route.note))
        self.replans += 1
        return before, after

    def refused(self) -> None:
        """A re-plan was asked and refused: it counts toward the limit, nothing changes."""
        self.replans += 1

    # -- a task's brief --------------------------------------------------------

    def assignment(self, task: SubagentTask) -> dict[str, Any]:
        """What an investigator is told of its task, beside the subject and the brief."""
        return {
            "task_id": task.task_id,
            "kind": task.kind.value,
            "measure": task.measure,
            "objective": task.objective,
            "wanted_output": task.wanted_output,
            "prefer_sources": list(task.prefer_sources),
            "boundaries": list(task.boundaries),
            "reason": task.reason,
            "from_lead": [
                {"from": source, "note": note} for source, note in self.notes.get(task.task_id, [])
            ],
        }

    def view(self) -> dict[str, Any]:
        """The run's state as the re-plan request shows it (deterministic)."""
        return {
            "replans_left": self.limits.replans - self.replans,
            "tasks_left": self.limits.max_tasks - len(self.tasks),
            "ceiling": self.limits.ceiling.model_dump(),
            "committed": self.committed().model_dump(),
            "per_task": {c.value: self.limits.cap(c).model_dump() for c in Complexity},
            "pending": [
                {
                    "task_id": t,
                    "subject_key": self.tasks[t].subject_key,
                    "measure": self.tasks[t].measure,
                    "budget": self.tasks[t].budget.model_dump(),
                }
                for t in self.pending_ids()
            ],
        }


# --------------------------------------------------------------------------- #
# A task's track
# --------------------------------------------------------------------------- #


def lead_track_id(subject_key: str, task_id: str) -> str:
    """A task's track: its subject's web track, and the task."""
    return f"{track_id(subject_key, Channel.WEB)}-{task_id}"


def lead_track(
    task: SubagentTask, subject: ResearchSubject, *, base_fingerprint: str, state: LeadState
) -> ResearchTrack:
    """The track one task runs as, fingerprinted by everything its result depends on.

    ``base_fingerprint`` is the subject's agent-directed web track fingerprint (the
    brief, the depth, the policy, the rules, the retrieval); the task's brief -- its
    notes from the lead included -- and its budget add to it, with the lead's version.
    The same task in a later pass is the same track and is reused.
    """
    return ResearchTrack(
        track_id=lead_track_id(subject.key, task.task_id),
        subject=subject,
        channel=Channel.WEB,
        fingerprint=digest(
            {
                "track": base_fingerprint,
                "lead": LEAD_VERSION,
                "assignment": state.assignment(task),
                "budget": task.budget.model_dump(),
            }
        ),
    )
