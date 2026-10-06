"""An agent-directed web track: the investigator's turns, each action through the gate.

Plan ``deep-research-web-search.md`` § 6, chunk 9; the mode is the composition's
(``DeepResearchConfig.agent_directed``) and recorded on the plan. A track is a loop:

1. **The stop rule**, before every turn (``planning.investigator_stop_reason``).
2. **One governed request** (``AgentRole.INVESTIGATOR``) over a deterministic turn
   input (``investigator.turn_input``), through ``StepModelCaller`` with the
   composition's thinking budget. Its answer is stored at once
   (:class:`~aia_core.domain.deep_research.investigator.TurnAnswer`), keyed by the
   run, the track, the turn and the request's hash: a retried step that rebuilds
   the same request finds it and never pays for it again.
3. **Grounding** of the turn's evidence against the track's own captures, with the
   measures it states (check 5); a citation is an ``S<n>`` the track holds.
4. **The actions.** Code's own refusals first (``investigator.plan_actions``); then
   every sendable search and open is *begun* through the ``RetrievalGate`` --
   classified (an open's whole URL, path and query included), egress-checked,
   reserved and journaled ``DISPATCHED`` -- before any of them is sent; then up to
   five are sent concurrently, the adapter calls alone on worker threads; then each
   outcome is journaled on the step's thread, in action order. A ``read`` is served
   from the capture; a URL the run already captured is a cache hit that sends
   nothing. A search or fetch an earlier attempt dispatched for a turn it never
   recorded is not sent again (its answer is unknown): it counts against the
   allowance and is reported.
5. **The record** (:class:`~aia_core.domain.deep_research.investigator.TurnRecord`):
   the answer, every action with code's decision, what was grounded. A retry
   replays recorded turns -- no model call, no tool call -- into the same state.

A finish, an uncertain delivery (the track ends ``INCOMPLETE``; nothing more is
sent, not even the next turn) and the same refusal three times
(``repeated_refusals``) end the track after the turn that caused them.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import TYPE_CHECKING, Any

from aia_core.application.web_retrieval import (
    FetchOutcome,
    PendingFetch,
    PendingSearch,
    RetrievalGate,
    SearchOutcome,
    request_fingerprint,
    sent_search,
)
from aia_core.domain.analysis.harness import request_sha256
from aia_core.domain.deep_research.agents import (
    MAX_ACTIONS_PER_TURN,
    AgentRole,
    FinishAction,
    InvestigatorTurn,
    TurnEvidence,
)
from aia_core.domain.deep_research.bundle import SnapshotRef
from aia_core.domain.deep_research.contracts import (
    QueryDecision,
    QueryRecord,
    ResearchTrack,
    SourceKind,
    SourceSnapshot,
    StopReason,
    TrackStatus,
    digest,
)
from aia_core.domain.deep_research.grounding import GroundableSource
from aia_core.domain.deep_research.investigator import (
    RESULTS_PER_SEARCH,
    SKIP_EARLIER_ATTEMPT,
    ActionDecision,
    ActionOutcome,
    ActionRecord,
    Allowance,
    HitRecord,
    PlannedAction,
    TrackRefs,
    TrackState,
    TurnAnswer,
    TurnRecord,
    plan_actions,
    transcript,
    turn_input,
    turns_without_new_evidence,
)
from aia_core.domain.deep_research.planning import investigator_stop_reason
from aia_core.domain.deep_research.steps import (
    AllowanceRecord,
    CallRecord,
    Gate,
    PlannedTrack,
    PlanRecord,
    SnapshotArtifact,
    SourceFactsRecord,
    TrackResult,
    run_scoped,
)
from aia_core.domain.licence import DataLineage
from aia_core.infrastructure.web_retrieval import FetchedPage
from aia_worker.executor import StepContext, StepInput

from ..ai_step import StepModelCaller
from ._findings import _Findings
from ._shared import _detail
from .runtime import DeepResearchRuntime, StepToolMeter

if TYPE_CHECKING:
    from .investigate import InvestigateExecutor

__all__ = ["AgentDirectedTrack"]


def _turn_key(run_id: str, track: ResearchTrack, turn: int, sha: str) -> str:
    return run_scoped(run_id, digest(["investigator_turn", track.fingerprint, turn, sha]))


class AgentDirectedTrack:
    """One agent-directed web track, run (or replayed) to its stop."""

    def __init__(
        self,
        executor: InvestigateExecutor,
        *,
        step: StepInput,
        context: StepContext,
        runtime: DeepResearchRuntime,
        plan: PlanRecord,
        track: ResearchTrack,
        planned: PlannedTrack,
        gate: RetrievalGate,
        meter: StepToolMeter,
        caller: StepModelCaller,
    ) -> None:
        self._executor = executor
        self._step, self._context, self._runtime = step, context, runtime
        self._plan, self._track, self._planned = plan, track, planned
        self._gate, self._meter, self._caller = gate, meter, caller
        allowance = plan.allowances.get(track.track_id) or AllowanceRecord(
            search_calls=0, fetches=0
        )
        self._allowance = Allowance(
            turns=plan.depth.max_turns,
            searches=allowance.search_calls,
            opens=allowance.fetches,
        )
        self._state = TrackState(refs=TrackRefs(runtime.source_table))
        self._findings = _Findings(
            track=track, data_class=plan.design_class, evidence=[], quarantined=[]
        )
        self._calls: list[CallRecord] = []
        self._records: list[TurnRecord] = []
        self._snapshots: dict[str, SnapshotRef] = {}
        self._stored: dict[str, SnapshotArtifact] = {}
        self._by_artifact: dict[str, SnapshotArtifact] = {}
        #: Dispatches earlier attempts journaled that no recorded turn accounts for.
        self._unaccounted = meter.dispatched_earlier(track.track_id)

    # ------------------------------------------------------------------ run --

    def run(self) -> TrackResult:
        status, stop, detail = TrackStatus.COMPLETED, None, ""
        turn = 0
        while True:
            if self._meter.uncertain(self._track.track_id):
                status, stop = TrackStatus.INCOMPLETE, StopReason.TOOL_OUTCOME_UNCERTAIN
                detail = (
                    "a call sent for this track may have been served with no answer on "
                    "record; nothing more is sent"
                )
                break
            stop = investigator_stop_reason(
                grounded=len(self._findings.evidence),
                new_by_turn=self._state.new_by_turn,
                turns_used=turn,
                searches_left=self._allowance.searches - self._state.searches_used,
                opens_left=self._allowance.opens - self._state.opens_used,
                unread=bool(self._state.reading),
                depth=self._plan.depth,
            )
            if stop is not None:
                break
            turn += 1
            self._context.checkpoint()
            refused = self._turn(turn)
            if refused is not None:
                status, stop, detail = TrackStatus.INCOMPLETE, refused[0], refused[1]
                break
            last = self._records[-1].actions
            if any(a.outcome is ActionOutcome.UNCERTAIN for a in last):
                status, stop = TrackStatus.INCOMPLETE, StopReason.TOOL_OUTCOME_UNCERTAIN
                lost = next(a for a in last if a.outcome is ActionOutcome.UNCERTAIN)
                detail = (
                    f"the {lost.kind} of action {lost.index} in turn {turn} may have been "
                    "served; nothing more is sent"
                )
                break
            if self._state.finished:
                stop = StopReason.AGENT_FINISHED
                break
            if not last:
                # Nothing proposed and nothing new to read: the next turn would be
                # asked the same thing again. The agent is done, without saying so.
                stop, detail = StopReason.AGENT_FINISHED, "the turn proposed no action"
                break
            reason = self._state.repeated_refusal()
            if reason is not None:
                stop = StopReason.STOP_REFUSALS
                detail = _detail(Gate.SEARCH_ROUTE, "repeated_refusals", reason)
                if not any(
                    a.decision in (ActionDecision.SENT, ActionDecision.CACHED)
                    for r in self._records
                    for a in r.actions
                ):
                    # Nothing ever left: a refused track is not a result to reuse.
                    status = TrackStatus.BLOCKED
                break
        return self._result(status, stop, detail)

    # ----------------------------------------------------------------- turn --

    def _turn(self, turn: int) -> tuple[StopReason, str] | None:
        """One turn, replayed or asked; the stop and detail when a gate refused the ask."""
        plan, track, step = self._plan, self._track, self._step
        reading, waiting, fresh = self._state.take_reading()
        payload = turn_input(
            self._state,
            track=track,
            brief=plan.request.brief,
            sub_questions=self._planned.sub_questions,
            suggested_queries=self._planned.queries,
            turn=turn,
            allowance=self._allowance,
            stop={
                "evidence_target": plan.depth.evidence_target,
                "grounded": len(self._findings.evidence),
                "saturation_window": plan.depth.saturation_window,
                "turns_without_new_evidence": turns_without_new_evidence(self._state.new_by_turn),
            },
            findings=[
                (self._state.refs.source_for_snapshot(e.source_ref) or e.source_ref, e.claim)
                for e in self._findings.evidence
            ],
            reading=reading,
            waiting=waiting,
        )
        request = self._executor._request(
            self._runtime,
            AgentRole.INVESTIGATOR,
            payload=payload,
            data_class=plan.design_class,
            lineage=DataLineage.none(),
        )
        sha = request_sha256(request)
        key = _turn_key(step.run_id, track, turn, sha)

        recorded = self._stored_turn("turn", key, TurnRecord)
        if recorded is not None:
            self._replay(recorded, fresh)
            return None

        answered = self._stored_turn("turn_answer", key, TurnAnswer)
        if answered is not None:
            output, call, replayed = answered.output, answered.call, True
        else:
            answer = self._executor._send(
                self._caller,
                self._runtime,
                AgentRole.INVESTIGATOR,
                request,
                data_class=plan.design_class,
            )
            if answer.gate is not None:
                stop = (
                    StopReason.CONTEXT_TOO_LARGE
                    if answer.gate is Gate.CONTEXT_WINDOW
                    else StopReason.MODEL_ROUTE_REFUSED
                )
                return stop, _detail(answer.gate, answer.reason, answer.detail)
            assert isinstance(answer.output, InvestigatorTurn) and answer.call is not None
            output, call, replayed = answer.output, answer.call, False
            self._put(
                "turn_answer",
                key,
                TurnAnswer(
                    kind="deep_research_turn_answer",
                    track_id=track.track_id,
                    turn=turn,
                    request_sha256=sha,
                    output=output,
                    call=call,
                ),
            )
        self._calls.append(call)
        grounded, quarantined = self._ground(output)
        if fresh:
            self._state.new_by_turn.append(len(grounded))
        records = self._execute(plan_actions(output, self._state, self._allowance))
        kept = self._state.apply(records, self._snapshot_map(records))
        record = TurnRecord(
            kind="deep_research_turn",
            track_id=track.track_id,
            turn=turn,
            request_sha256=sha,
            call=call,
            answer_replayed=replayed,
            output=output,
            actions=kept,
            grounded=tuple(grounded),
            quarantined=tuple(quarantined),
            fresh=fresh,
        )
        self._put("turn", key, record)
        self._records.append(record)
        self._context.progress(
            "deep_research_turn",
            track_id=track.track_id,
            turn=turn,
            replayed=False,
            answer_replayed=replayed,
            actions=len(kept),
            sent=sum(1 for a in kept if a.decision is ActionDecision.SENT),
            refused=sum(1 for a in kept if a.decision is ActionDecision.REFUSED),
            grounded=len(grounded),
        )
        return None

    def _replay(self, record: TurnRecord, fresh: bool) -> None:
        """A recorded turn into the state: no model call, no tool call."""
        if record.fresh != fresh or record.turn != len(self._records) + 1:
            raise RuntimeError("a recorded turn does not answer the state it is replayed into")
        self._calls.append(record.call)
        grounded, _quarantined = self._ground(record.output)
        if fresh:
            self._state.new_by_turn.append(len(grounded))
        for action in record.actions:
            if action.request_fingerprint is not None and action.decision is ActionDecision.SENT:
                self._unaccounted[action.request_fingerprint] -= 1
        self._state.apply(record.actions, self._snapshot_map(record.actions))
        self._records.append(record)
        self._context.progress(
            "deep_research_turn",
            track_id=self._track.track_id,
            turn=record.turn,
            replayed=True,
            answer_replayed=record.answer_replayed,
            actions=len(record.actions),
            sent=0,
            refused=0,
            grounded=len(grounded),
        )

    # ------------------------------------------------------------- grounding --

    def _ground(self, output: InvestigatorTurn) -> tuple[list[str], list[str]]:
        """The turn's evidence, cited by ``S<n>``, grounded in the track's captures."""
        refs = self._state.refs
        proposals: list[TurnEvidence] = []
        for p in output.evidence:
            source = refs.source(p.source_id)
            snapshot_id = source.snapshot_id if source is not None else p.source_id
            proposals.append(p.model_copy(update={"source_id": snapshot_id}))
        snaps = {k: v.snapshot for k, v in self._stored.items()}
        return self._findings.add(
            proposals,
            sources={
                k: GroundableSource(k, s.text, s.instructions_detected) for k, s in snaps.items()
            },
            kind=SourceKind.WEB_PAGE,
            urls={k: s.final_url for k, s in snaps.items()},
            titles={k: s.title for k, s in snaps.items()},
        )

    # --------------------------------------------------------------- actions --

    def _execute(self, planned: Sequence[PlannedAction]) -> list[ActionRecord]:
        """Every planned action's record, in order: begun, sent together, finished."""
        track_id = self._track.track_id
        done: dict[int, ActionRecord] = {}
        pending: list[tuple[PlannedAction, PendingSearch | PendingFetch]] = []
        for p in planned:
            if p.record is not None:
                done[p.index] = p.record
                continue
            if p.search is not None:
                text, lang = p.search
                fingerprint = request_fingerprint(sent_search(text, lang))
                if self._unaccounted[fingerprint] > 0:
                    self._unaccounted[fingerprint] -= 1
                    done[p.index] = self._earlier(p, query=text, lang=lang)
                    continue
                begun_search = self._gate.begin_search(
                    text,
                    context_class=self._plan.design_class,
                    track_id=track_id,
                    max_results=RESULTS_PER_SEARCH,
                    lang=lang,
                )
                if isinstance(begun_search, SearchOutcome):
                    done[p.index] = self._search_record(p, begun_search, text, lang)
                else:
                    pending.append((p, begun_search))
            else:
                assert p.url is not None
                if self._unaccounted[request_fingerprint(p.url)] > 0:
                    self._unaccounted[request_fingerprint(p.url)] -= 1
                    done[p.index] = self._earlier(p, ref=p.ref, url=p.url)
                    continue
                begun_fetch = self._gate.begin_fetch(p.url, track_id=track_id)
                if isinstance(begun_fetch, FetchOutcome):
                    done[p.index] = self._fetch_record(p, begun_fetch)
                else:
                    pending.append((p, begun_fetch))
        # Every dispatch is on record; now they leave together.
        if pending:
            workers = min(MAX_ACTIONS_PER_TURN, len(pending))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(lambda item: item[1].send(), pending))
        error: BaseException | None = None
        for p, sent in pending:
            try:
                if isinstance(sent, PendingSearch):
                    done[p.index] = self._search_record(
                        p, self._gate.finish_search(sent), sent.query, sent.lang
                    )
                else:
                    done[p.index] = self._fetch_record(p, self._gate.finish_fetch(sent))
            except Exception as exc:  # every other outcome is journaled first
                error = error or exc
        if error is not None:
            raise error
        return [done[i] for i in sorted(done)]

    @staticmethod
    def _earlier(p: PlannedAction, **fields: Any) -> ActionRecord:
        return ActionRecord(
            index=p.index,
            kind=p.kind,
            purpose=p.purpose,
            decision=ActionDecision.SKIPPED,
            reason=SKIP_EARLIER_ATTEMPT,
            **fields,
        )

    @staticmethod
    def _search_record(
        p: PlannedAction, outcome: SearchOutcome, text: str, lang: str | None
    ) -> ActionRecord:
        record = outcome.record
        fields: dict[str, Any] = {
            "index": p.index,
            "kind": "search",
            "purpose": p.purpose,
            "query": text,
            "lang": lang,
            "data_class": record.data_class,
            "class_reasons": record.class_reasons,
            "call_id": record.call_id,
            "request_fingerprint": outcome.request_fingerprint,
        }
        if record.decision is QueryDecision.REFUSED:
            return ActionRecord(decision=ActionDecision.REFUSED, reason=record.refusal, **fields)
        if outcome.uncertain:
            result = ActionOutcome.UNCERTAIN
        elif record.failure is not None:
            result = ActionOutcome.FAILED
        else:
            result = ActionOutcome.SUCCEEDED
        return ActionRecord(
            decision=ActionDecision.SENT,
            reason=record.failure,
            outcome=result,
            hits=tuple(
                HitRecord(url=h.url, title=h.title, snippet=h.snippet, rank=h.rank)
                for h in outcome.hits
            ),
            **fields,
        )

    def _fetch_record(self, p: PlannedAction, outcome: FetchOutcome) -> ActionRecord:
        fields: dict[str, Any] = {
            "index": p.index,
            "kind": "open",
            "purpose": p.purpose,
            "ref": p.ref,
            "url": p.url,
            "data_class": outcome.data_class,
            "call_id": outcome.call_id,
            "request_fingerprint": outcome.request_fingerprint,
        }
        if outcome.page is not None:
            ref = self._keep(outcome.page)
            return ActionRecord(
                decision=ActionDecision.CACHED if outcome.cached else ActionDecision.SENT,
                outcome=None if outcome.cached else ActionOutcome.SUCCEEDED,
                snapshot_id=ref.snapshot_id,
                snapshot_artifact_id=ref.artifact_id,
                **fields,
            )
        if outcome.call_id is None:
            return ActionRecord(decision=ActionDecision.REFUSED, reason=outcome.reason, **fields)
        return ActionRecord(
            decision=ActionDecision.SENT,
            reason=outcome.reason,
            outcome=ActionOutcome.UNCERTAIN if outcome.uncertain else ActionOutcome.FAILED,
            **fields,
        )

    # ------------------------------------------------------------ snapshots --

    def _keep(self, page: FetchedPage) -> SnapshotRef:
        ref, stored = self._executor._snapshot(self._context, self._step, page)
        self._hold(ref, stored)
        return ref

    def _hold(self, ref: SnapshotRef, stored: SnapshotArtifact) -> None:
        self._snapshots.setdefault(ref.snapshot_id, ref)
        self._stored.setdefault(ref.snapshot_id, stored)
        self._by_artifact.setdefault(ref.artifact_id, stored)

    def _snapshot_map(
        self, records: Sequence[ActionRecord]
    ) -> dict[str, tuple[SourceSnapshot, date | None]]:
        """Each record's captured snapshot by artifact id; read back from the store on replay."""
        out: dict[str, tuple[SourceSnapshot, date | None]] = {}
        for record in records:
            artifact_id = record.snapshot_artifact_id
            if artifact_id is None:
                continue
            stored = self._by_artifact.get(artifact_id)
            if stored is None:
                # A replayed turn's capture: read back, and held in the run's cache
                # as the interrupted attempt held it.
                stored = self._executor._read_snapshot(self._context, artifact_id)
                self._hold(self._executor._snapshot_ref(artifact_id, stored), stored)
                if record.url is not None:
                    self._gate.remember(
                        record.url,
                        FetchedPage(snapshot=stored.snapshot, published=stored.published),
                    )
            out[artifact_id] = (stored.snapshot, stored.published)
        return out

    # ---------------------------------------------------------------- store --

    def _stored_turn(self, kind: str, key: str, model: type[Any]) -> Any | None:
        with self._context.transaction() as (session, _workflow):
            repo = self._executor._repo(session, self._context)
            found = self._executor._find(repo, self._step, kind, key)
            if found is None:
                return None
            return self._executor._read(repo, found.artifact_id, model)

    def _put(self, kind: str, key: str, payload: TurnAnswer | TurnRecord) -> None:
        with self._context.transaction() as (session, _workflow):
            self._executor._put(
                self._executor._repo(session, self._context),
                self._step,
                payload=payload,
                kind=kind,
                key=key,
            )

    # --------------------------------------------------------------- result --

    def _result(self, status: TrackStatus, stop: StopReason, detail: str) -> TrackResult:
        track_id = self._track.track_id
        searches, fetches, charged, tool_cost = self._meter.track_usage(track_id)
        actions = [a for r in self._records for a in r.actions]
        # The searches the gate judged, as the planned mode records its queries.
        queries: list[QueryRecord] = []
        for a in actions:
            if a.kind != "search" or a.data_class is None:
                continue
            sent = a.decision is ActionDecision.SENT
            queries.append(
                QueryRecord(
                    text=a.query or "",
                    data_class=a.data_class,
                    class_reasons=a.class_reasons,
                    decision=QueryDecision.SENT if sent else QueryDecision.REFUSED,
                    refusal=None if sent else a.reason,
                    call_id=a.call_id,
                    hits=len(a.hits),
                    failure=a.reason if sent else None,
                )
            )
        finish = next(
            (
                action
                for r in self._records
                for action in r.output.next
                if isinstance(action, FinishAction)
            ),
            None,
        )
        gaps = tuple(
            f"{g.need} -- {g.why} (zkoušeno: {g.tried})"
            for g in (finish.gaps if finish is not None else ())
        )
        assert self._runtime.retrieval is not None
        record = transcript(
            run_id=self._step.run_id,
            track_id=track_id,
            status=status,
            stop_reason=stop,
            detail=detail,
            turns=self._records,
            refs=self._state.refs,
            tool_cost_usd=tool_cost,
        )
        # Keyed like the track's result: reusable with it when it completed, else this
        # run's own. A reused track brings the transcript of the run that researched it.
        material = digest(["investigator_transcript", self._track.fingerprint])
        key = (
            material if status is TrackStatus.COMPLETED else run_scoped(self._step.run_id, material)
        )
        with self._context.transaction() as (session, _workflow):
            artifact, _created = self._executor._put(
                self._executor._repo(session, self._context),
                self._step,
                payload=record,
                kind="transcript",
                key=key,
                depends_on=[s.artifact_id for s in self._state.refs.sources],
            )
        return TrackResult(
            kind="deep_research_track",
            run_id=self._step.run_id,
            track=self._track,
            status=status,
            stop_reason=stop,
            detail=detail[:2000],
            retrieval_mode=self._runtime.retrieval.retrieval_mode,
            sub_questions=self._planned.sub_questions,
            queries=tuple(queries),
            snapshots=tuple(self._snapshots[s.snapshot_id] for s in self._state.refs.sources),
            knowledge_refs=(),
            sources=tuple(
                SourceFactsRecord(
                    ref=s.snapshot_id,
                    kind=SourceKind.WEB_PAGE,
                    url=self._stored[s.snapshot_id].snapshot.final_url,
                    published=self._stored[s.snapshot_id].published,
                    retrieved=self._stored[s.snapshot_id].snapshot.retrieved_at.date(),
                )
                for s in self._state.refs.sources
            ),
            evidence=tuple(self._findings.evidence),
            quarantined=tuple(self._findings.quarantined),
            gaps=gaps,
            calls=tuple(self._calls),
            search_calls=searches,
            fetches=fetches,
            credits=charged,
            model_cost_usd=sum(c.cost_usd for c in self._calls),
            tool_cost_usd=tool_cost,
            transcript_artifact_id=artifact.artifact_id,
        )
