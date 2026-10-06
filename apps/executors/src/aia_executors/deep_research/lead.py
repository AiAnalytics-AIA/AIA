"""A lead-planned run: the lead's plan at the plan step, its waves and re-plans at investigate.

Plan ``deep-research-web-search.md`` chunk 11; the mode is the composition's
(``DeepResearchConfig.lead``, which needs ``agent_directed``) and recorded on the plan.

**The plan** (:class:`LeadPlanning`, from the ``plan`` step). The web subjects the run
researches -- at most the preset's task limit of them, the rest recorded as beyond it --
go to the lead (``AgentRole.LEAD``, capability ``RESEARCH_LEAD``) in one request whose
contract is bound to the run's limits (``lead.bound_plan_contract``): a plan that breaks
an effort cap, overlaps two tasks, misses a subject or exceeds the run's ceiling fails
validation with every reason named and takes the gateway's one repair. Refused again,
the run's web tracks are **blocked** (``plan_incomplete``, ``lead_plan_refused``, the
reasons in the detail): explicit, and never planned some other way behind the lead's
back. The answer -- or the refusal -- is stored at once as the run's
:class:`~aia_core.domain.deep_research.steps.LeadPlanRecord`, keyed by the run and the
request's hash: the memory a long run and a retried step keep.

**The waves** (:class:`LeadWaves`, from the ``investigate`` step). The plan's tasks run
wave by wave, each task as one agent-directed track whose brief is the task's
(``LeadState.assignment``) and whose allowance is its budget; tracks within a wave run one
after another -- or, with fan-out (chunk 21), each in a step of its own: the wave's
unstored tracks are handed out (:class:`WaveHandedOut`), the step waits for them, and the
next attempt replays the waves before it from what they stored. After a wave, while the
preset allows, the lead re-plans (``AgentRole.LEAD_REPLAN``) over what the wave found; its
contract is bound to the run's state, so a re-plan that overdraws a task, overlaps a
pending task, exceeds the ceiling or the task limit is refused like the plan. A refused
re-plan counts toward the limit and changes nothing: the remaining waves run as planned.
Each re-plan is stored (:class:`~aia_core.domain.deep_research.steps.ReplanRecord`) and a
retried step applies it again without a call; every task's track is stored like any track,
so a retry buys nothing twice.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aia_core.application.web_retrieval import RetrievalGate
from aia_core.domain.analysis.harness import request_sha256
from aia_core.domain.deep_research.agents import AgentRole
from aia_core.domain.deep_research.contracts import (
    Channel,
    DeepResearchRequest,
    ResearchTrack,
    StopReason,
    digest,
)
from aia_core.domain.deep_research.investigator import Allowance, Transcript
from aia_core.domain.deep_research.lead import (
    EFFORT_CAPS,
    LEAD_VERSION,
    MAX_TASKS_PER_WAVE,
    MIN_TASKS_PER_WAVE,
    Allotment,
    Complexity,
    LeadLimits,
    LeadState,
    Replan,
    ResearchPlan,
    SubagentTask,
    bound_plan_contract,
    bound_replan_contract,
    lead_limits,
    lead_track,
)
from aia_core.domain.deep_research.planning import DepthPreset, track_fingerprint
from aia_core.domain.deep_research.steps import (
    BlockedTrack,
    CallRecord,
    Gate,
    LeadPlanRecord,
    LeadRunRecord,
    PlannedTrack,
    PlanRecord,
    ReplanRecord,
    TrackEntry,
    TrackResult,
    run_scoped,
)
from aia_core.domain.licence import DataLineage
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import FailureClass
from aia_worker.executor import StepContext, StepFailed, StepInput

from ..ai_step import StepModelCaller
from ._shared import _Answer, _detail, _Step
from .runtime import DeepResearchRuntime, StepToolMeter

if TYPE_CHECKING:
    from .investigate import InvestigateExecutor

__all__ = ["LeadPlanned", "LeadPlanning", "LeadTask", "LeadWaves", "WaveHandedOut"]

#: Why a lead-planned run's web tracks are blocked when the lead's plan is refused.
LEAD_PLAN_REFUSED = "lead_plan_refused"


def _refusal(exc: StepFailed) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """(the reasons, the calls) of an answer refused after the gateway's one repair.

    None for any other failure: a lost answer, a provider error or a budget stop is
    the worker's to decide, and propagates.
    """
    if exc.failure is not FailureClass.SCHEMA_VIOLATION:
        return None
    violations = tuple(str(v) for v in exc.error.get("violations") or ()) or (str(exc),)
    call_ids = tuple(str(c) for c in exc.error.get("call_ids") or ())
    return violations, call_ids


def _gate_stop(gate: Gate) -> StopReason:
    if gate is Gate.CONTEXT_WINDOW:
        return StopReason.CONTEXT_TOO_LARGE
    return StopReason.MODEL_ROUTE_REFUSED


# --------------------------------------------------------------------------- #
# The plan step: the lead's plan
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class LeadPlanned:
    """What the plan step records of the lead: its plan's artifact, call and refusals."""

    #: The stored ``LeadPlanRecord``; None when no request could be sent at all.
    artifact_id: str | None
    call: CallRecord | None
    #: Web tracks the lead planned (they run as its tasks' tracks instead).
    planned: frozenset[str]
    #: Web tracks blocked: beyond the task limit, or every one when the lead was refused.
    blocked: tuple[BlockedTrack, ...]
    tasks: int


class LeadPlanning:
    """The lead's plan for one run's web tracks, asked once and stored at once."""

    def __init__(
        self,
        executor: _Step,
        *,
        step: StepInput,
        context: StepContext,
        runtime: DeepResearchRuntime,
        caller: StepModelCaller,
        request: DeepResearchRequest,
        depth: DepthPreset,
        data_class: DataClass,
        plan_key: str,
    ) -> None:
        self._executor = executor
        self._step, self._context, self._runtime, self._caller = step, context, runtime, caller
        self._request, self._depth, self._class, self._key = request, depth, data_class, plan_key

    def limits(self, web: Sequence[ResearchTrack]) -> LeadLimits:
        depth = self._depth
        return lead_limits(
            depth.name,
            subjects=[t.subject.key for t in web],
            max_turns=depth.max_turns,
            max_searches=depth.max_searches,
            max_opens=depth.max_opens,
            max_search_calls=depth.max_search_calls,
            max_fetches=depth.max_fetches,
        )

    def plan(self, web: Sequence[ResearchTrack]) -> LeadPlanned:
        """The lead's plan over ``web``'s subjects (in order, up to the task limit)."""
        everything = self.limits(web)
        shown, beyond = list(web[: everything.max_tasks]), list(web[everything.max_tasks :])
        limits = self.limits(shown)
        blocked = [
            BlockedTrack(
                track_id=t.track_id,
                stop_reason=StopReason.TRACK_LIMIT,
                gate=Gate.TRACK_LIMIT,
                reason="lead_task_limit",
                detail=_detail(
                    Gate.TRACK_LIMIT,
                    "lead_task_limit",
                    f"the lead plans at most {limits.max_tasks} subjects' tasks "
                    f"({self._depth.name})",
                ),
            )
            for t in beyond
        ]
        runtime = self._runtime
        request = self._executor._request(
            runtime,
            AgentRole.LEAD,
            payload=self._payload(shown, limits),
            data_class=self._class,
            lineage=DataLineage.none(),
            contract=bound_plan_contract(limits),
        )
        sha = request_sha256(request)
        key = run_scoped(self._step.run_id, digest(["lead_plan", self._key, sha]))

        def refused_all(stop: StopReason, gate: Gate, reason: str, message: str) -> None:
            blocked.extend(
                BlockedTrack(
                    track_id=t.track_id,
                    stop_reason=stop,
                    gate=gate,
                    reason=reason,
                    detail=_detail(gate, reason, message),
                )
                for t in shown
            )

        stored = self._stored(key)
        if stored is None:
            answer: _Answer | None = None
            refusal: tuple[tuple[str, ...], tuple[str, ...]] | None = None
            try:
                answer = self._executor._send(
                    self._caller, runtime, AgentRole.LEAD, request, data_class=self._class
                )
            except StepFailed as exc:
                refusal = _refusal(exc)
                if refusal is None:
                    raise
            if answer is not None and answer.gate is not None:
                # Nothing was sent: no record, and the gate is named on every track.
                refused_all(_gate_stop(answer.gate), answer.gate, answer.reason, answer.detail)
                return LeadPlanned(None, None, frozenset(), tuple(blocked), 0)
            if answer is not None:
                assert isinstance(answer.output, ResearchPlan) and answer.call is not None
                plan: ResearchPlan | None = ResearchPlan.model_validate(
                    answer.output.model_dump(mode="json")
                )
                record = self._record(sha, limits, plan, (), answer.call, ())
            else:
                assert refusal is not None
                record = self._record(sha, limits, None, refusal[0], None, refusal[1])
            artifact_id = self._put(key, record)
        else:
            artifact_id, record = stored
        if record.plan is None:
            refused_all(
                StopReason.PLAN_INCOMPLETE,
                Gate.PLAN,
                LEAD_PLAN_REFUSED,
                "; ".join(record.refused),
            )
            return LeadPlanned(artifact_id, None, frozenset(), tuple(blocked), 0)
        return LeadPlanned(
            artifact_id,
            record.call,
            frozenset(t.track_id for t in shown),
            tuple(blocked),
            len(record.plan.tasks()),
        )

    def _payload(self, shown: Sequence[ResearchTrack], limits: LeadLimits) -> dict[str, Any]:
        return {
            "brief": self._request.brief.model_dump(mode="json"),
            "subjects": [
                {"subject_key": t.subject.key, "kind": t.subject.kind.value, "text": t.subject.text}
                for t in shown
            ],
            "limits": {
                "max_tasks": limits.max_tasks,
                "replans": limits.replans,
                "per_task": limits.per_task.model_dump(),
                "ceiling": limits.ceiling.model_dump(),
                "wave": {"min": MIN_TASKS_PER_WAVE, "max": MAX_TASKS_PER_WAVE},
                "complexity": {
                    c.value: {
                        "tasks": [EFFORT_CAPS[c].min_tasks, EFFORT_CAPS[c].max_tasks],
                        "budget": limits.cap(c).model_dump(),
                    }
                    for c in Complexity
                },
            },
        }

    def _record(
        self,
        sha: str,
        limits: LeadLimits,
        plan: ResearchPlan | None,
        refused: tuple[str, ...],
        call: CallRecord | None,
        call_ids: tuple[str, ...],
    ) -> LeadPlanRecord:
        return LeadPlanRecord(
            kind="deep_research_lead_plan",
            run_id=self._step.run_id,
            version=LEAD_VERSION,
            request_sha256=sha,
            limits=limits,
            plan=plan,
            refused=tuple(r[:2000] for r in refused),
            call=call,
            call_ids=call_ids,
        )

    def _stored(self, key: str) -> tuple[str, LeadPlanRecord] | None:
        with self._context.transaction() as (session, _workflow):
            repo = self._executor._repo(session, self._context)
            found = self._executor._find(repo, self._step, "lead_plan", key)
            if found is None:
                return None
            return found.artifact_id, self._executor._read(repo, found.artifact_id, LeadPlanRecord)

    def _put(self, key: str, record: LeadPlanRecord) -> str:
        with self._context.transaction() as (session, _workflow):
            artifact, _created = self._executor._put(
                self._executor._repo(session, self._context),
                self._step,
                payload=record,
                kind="lead_plan",
                key=key,
            )
        return artifact.artifact_id


# --------------------------------------------------------------------------- #
# The investigate step: waves and re-plans
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class LeadTask:
    """What a lead task's track runs with instead of the planner's: brief and budget."""

    planned: PlannedTrack
    allowance: Allowance
    assignment: dict[str, Any]


class WaveHandedOut(Exception):
    """A wave's unstored tracks go to steps of their own; the investigate step waits.

    Raised by :meth:`LeadWaves.run` with fan-out on, before anything of the wave is
    researched here. The next attempt replays every earlier wave and re-plan from what
    was stored, finds this wave stored too, and carries on.
    """

    def __init__(self, tracks: Sequence[tuple[ResearchTrack, LeadTask]]) -> None:
        super().__init__(f"{len(tracks)} track(s) handed out")
        self.tracks: tuple[tuple[ResearchTrack, LeadTask | None], ...] = tuple(tracks)


class LeadWaves:
    """A lead-planned run's tasks, wave by wave, with a re-plan after each while allowed."""

    def __init__(
        self,
        executor: InvestigateExecutor,
        *,
        step: StepInput,
        context: StepContext,
        runtime: DeepResearchRuntime,
        plan: PlanRecord,
        lead_plan_id: str,
        gate: RetrievalGate | None,
        meter: StepToolMeter,
        caller: StepModelCaller,
        fan_out: bool = False,
    ) -> None:
        self._executor = executor
        self._step, self._context, self._runtime, self._plan = step, context, runtime, plan
        self._lead_plan_id = lead_plan_id
        self._gate, self._meter, self._caller = gate, meter, caller
        self._fan_out = fan_out

    def run(self) -> tuple[list[TrackEntry], LeadRunRecord | None]:
        """Every task's track entry, in the order run, and how the waves went.

        ``(no entries, None)`` when the lead's plan was refused: the plan step blocked
        the web tracks, and they are the plan's own.
        """
        with self._context.transaction() as (session, _workflow):
            record = self._executor._read(
                self._executor._repo(session, self._context), self._lead_plan_id, LeadPlanRecord
            )
        if record.plan is None:
            return [], None
        state = LeadState.start(record.plan, record.limits)
        subjects = {s.key: s for s in self._plan.subjects}
        inputs = self._runtime.inputs()
        entries: list[TrackEntry] = []
        waves: list[tuple[str, ...]] = []
        replans: list[str] = []
        calls: list[CallRecord] = []
        wave = 0
        while True:
            tasks = state.next_wave()
            if not tasks:
                break
            wave += 1
            ran: list[tuple[SubagentTask, TrackResult]] = []
            used: dict[str, Allotment] = {}
            planned_wave: list[tuple[SubagentTask, ResearchTrack, LeadTask]] = []
            for task in tasks:
                subject = subjects[task.subject_key]
                track = lead_track(
                    task,
                    subject,
                    base_fingerprint=track_fingerprint(
                        subject,
                        Channel.WEB,
                        request=self._plan.request,
                        depth=self._plan.depth,
                        inputs=inputs,
                    ),
                    state=state,
                )
                planned_wave.append(
                    (
                        task,
                        track,
                        LeadTask(
                            planned=PlannedTrack(
                                track_id=track.track_id,
                                sub_questions=state.questions[task.subject_key],
                                queries=(),
                            ),
                            allowance=Allowance(
                                turns=task.budget.turns,
                                searches=task.budget.searches,
                                opens=task.budget.opens,
                            ),
                            assignment=state.assignment(task),
                        ),
                    )
                )
            if self._fan_out:
                out = [
                    (track, lead)
                    for _task, track, lead in planned_wave
                    if self._executor.researches(self._plan, track, self._gate, lead=True)
                    and not self._executor.stored_track(self._step, self._context, track)
                ]
                if out:
                    raise WaveHandedOut(out)
            for task, track, lead in planned_wave:
                self._context.checkpoint()
                entry = self._executor._track(
                    self._step,
                    self._context,
                    self._runtime,
                    self._plan,
                    track,
                    self._gate,
                    self._meter,
                    self._caller,
                    lead=lead,
                )
                result = self._read(entry.artifact_id, TrackResult)
                entries.append(entry)
                ran.append((task, result))
                # A track an earlier run researched cost this run nothing.
                used[task.task_id] = (
                    Allotment(turns=0, searches=0, opens=0)
                    if entry.reused
                    else Allotment(
                        turns=len(result.calls), searches=result.search_calls, opens=result.fetches
                    )
                )
            state.finish(used)
            waves.append(tuple(r.track.track_id for _t, r in ran))
            if state.may_replan:
                artifact_id, replan = self._replan(state, wave, ran)
                replans.append(artifact_id)
                if replan.call is not None:
                    calls.append(replan.call)
        return entries, LeadRunRecord(
            lead_plan_artifact_id=self._lead_plan_id,
            waves=tuple(waves),
            replan_artifact_ids=tuple(replans),
            calls=tuple(calls),
        )

    # -- re-plans --------------------------------------------------------------

    def _replan(
        self, state: LeadState, wave: int, ran: Sequence[tuple[SubagentTask, TrackResult]]
    ) -> tuple[str, ReplanRecord]:
        """Ask for (or replay) the re-plan after ``wave``, and apply it to ``state``."""
        this_wave = {t.task_id for t, _r in ran}
        payload = {
            "wave": wave,
            "finished": [self._finished(task, result, state) for task, result in ran],
            "earlier": [
                {
                    "task_id": t,
                    "subject_key": state.tasks[t].subject_key,
                    "measure": state.tasks[t].measure,
                }
                for t in state.used
                if t not in this_wave
            ],
            "run": state.view(),
        }
        runtime, plan = self._runtime, self._plan
        request = self._executor._request(
            runtime,
            AgentRole.LEAD_REPLAN,
            payload=payload,
            data_class=plan.design_class,
            lineage=DataLineage.none(),
            contract=bound_replan_contract(state),
        )
        sha = request_sha256(request)
        key = run_scoped(self._step.run_id, digest(["lead_replan", self._lead_plan_id, wave, sha]))
        with self._context.transaction() as (session, _workflow):
            repo = self._executor._repo(session, self._context)
            found = self._executor._find(repo, self._step, "replan", key)
            if found is not None:
                stored = self._executor._read(repo, found.artifact_id, ReplanRecord)
                self._apply(state, stored.replan)
                return found.artifact_id, stored

        replan: Replan | None = None
        refused: tuple[str, ...] = ()
        call: CallRecord | None = None
        call_ids: tuple[str, ...] = ()
        try:
            answer = self._executor._send(
                self._caller,
                runtime,
                AgentRole.LEAD_REPLAN,
                request,
                data_class=plan.design_class,
            )
        except StepFailed as exc:
            refusal = _refusal(exc)
            if refusal is None:
                raise
            refused, call_ids = refusal
        else:
            if answer.gate is not None:
                refused = (_detail(answer.gate, answer.reason, answer.detail),)
            else:
                assert isinstance(answer.output, Replan) and answer.call is not None
                replan = Replan.model_validate(answer.output.model_dump(mode="json"))
                call = answer.call
        before, after = self._apply(state, replan)
        record = ReplanRecord(
            kind="deep_research_lead_replan",
            run_id=self._step.run_id,
            wave=wave,
            request_sha256=sha,
            replan=replan,
            refused=tuple(r[:2000] for r in refused),
            call=call,
            call_ids=call_ids,
            pending_before=before,
            pending_after=after,
            committed_after=state.committed(),
            ceiling=state.limits.ceiling,
        )
        with self._context.transaction() as (session, _workflow):
            artifact, _created = self._executor._put(
                self._executor._repo(session, self._context),
                self._step,
                payload=record,
                kind="replan",
                key=key,
            )
        self._context.progress(
            "deep_research_replan",
            wave=wave,
            applied=replan is not None,
            new_tasks=len(replan.next_wave) if replan is not None else 0,
            moves=len(replan.moves) if replan is not None else 0,
        )
        return artifact.artifact_id, record

    @staticmethod
    def _apply(state: LeadState, replan: Replan | None) -> tuple[Allotment, Allotment]:
        if replan is None:
            state.refused()
            pending = state.pending_total()
            return pending, pending
        return state.apply(replan)

    def _finished(
        self, task: SubagentTask, result: TrackResult, state: LeadState
    ) -> dict[str, Any]:
        """One finished task as the re-plan request shows it (deterministic)."""
        summaries: list[str] = []
        leads: list[dict[str, Any]] = []
        if result.transcript_artifact_id is not None:
            transcript = self._read(result.transcript_artifact_id, Transcript)
            summaries = [t.output.summary for t in transcript.turns if t.output.summary][-5:]
            leads = [
                lead.model_dump(mode="json") for t in transcript.turns for lead in t.output.leads
            ][-5:]
        used = state.used[task.task_id]
        return {
            "task_id": task.task_id,
            "kind": task.kind.value,
            "subject_key": task.subject_key,
            "measure": task.measure,
            "status": result.status.value,
            "stop_reason": result.stop_reason.value,
            "findings": [
                {
                    "claim": e.claim,
                    "measures": [m.model_dump(mode="json", exclude_none=True) for m in e.measures],
                }
                for e in result.evidence
            ][:12],
            "quarantined": len(result.quarantined),
            "gaps": list(result.gaps),
            "leads": leads,
            "summaries": summaries,
            "used": used.model_dump(),
        }

    def _read(self, artifact_id: str, model: type[Any]) -> Any:
        with self._context.transaction() as (session, _workflow):
            return self._executor._read(
                self._executor._repo(session, self._context), artifact_id, model
            )
