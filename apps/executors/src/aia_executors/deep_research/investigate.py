"""The ``investigate`` step: every track, reused or researched, grounded in what it captured.

With ``DeepResearchConfig.fan_out`` (chunk 21, ``docs/architecture/deep-research-fan-out.md``)
the step is a join: every track that would make a call is handed out as a step of its own
(:class:`InvestigateTrackExecutor`, any worker), the step waits, and it runs again to take
what they stored. A lead-planned run's waves are handed out the same way, one wave at a
time. Off, every track is researched here, one after another, as before.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from aia_core.application.web_retrieval import (
    FetchOutcome,
    RetrievalGate,
    RunSnapshotCache,
    SearchOutcome,
)
from aia_core.domain.analysis.harness import request_sha256
from aia_core.domain.deep_research.agents import (
    SOURCE_TEXT_CHARS,
    AgentRole,
    ExtractionProposal,
    request_class,
)
from aia_core.domain.deep_research.bundle import SnapshotRef
from aia_core.domain.deep_research.contracts import (
    Channel,
    QueryDecision,
    QueryRecord,
    ResearchTrack,
    SourceKind,
    SourceSnapshot,
    StopReason,
    TrackStatus,
    digest,
)
from aia_core.domain.deep_research.grounding import GroundableSource, detect_instructions
from aia_core.domain.deep_research.knowledge_access import retrieve
from aia_core.domain.deep_research.legacy import canonical_url
from aia_core.domain.deep_research.planning import stop_reason
from aia_core.domain.deep_research.steps import (
    AllowanceRecord,
    CallRecord,
    Gate,
    InvestigationRecord,
    PlannedFetch,
    PlannedHit,
    PlannedRound,
    PlannedRoundAnswer,
    PlannedSearch,
    PlannedTrack,
    PlanRecord,
    SnapshotArtifact,
    SourceFactsRecord,
    TrackEntry,
    TrackResult,
    run_scoped,
)
from aia_core.domain.deep_research.workflow import track_step_key
from aia_core.domain.licence import DataLineage
from aia_core.infrastructure.artifact_repository import Artifact, ArtifactRepository
from aia_core.infrastructure.web_retrieval import FetchedPage
from aia_worker.executor import ChildStep, Deferred, Failed, StepContext, StepInput, StepOutcome
from pydantic import BaseModel, ValidationError

from ..ai_step import StepModelCaller
from ._findings import _blocked_result, _Findings
from ._shared import (
    _agent_directed,
    _Answer,
    _class_a_texts,
    _composition_changed,
    _detail,
    _invalid,
    _lineage,
    _produced,
    _Step,
    _unconfigured,
)
from .agent_directed import AgentDirectedTrack
from .fan_out import StoredRunSnapshotCache, TrackStepPayload, track_child
from .lead import LeadTask, LeadWaves, WaveHandedOut
from .runtime import DeepResearchRuntime, StepToolMeter

__all__ = ["InvestigateExecutor", "InvestigateTrackExecutor"]

_R = TypeVar("_R", bound=BaseModel)

# --------------------------------------------------------------------------- #
# investigate
# --------------------------------------------------------------------------- #


class InvestigateExecutor(_Step):
    """Every planned track: reused when its fingerprint is stored, else researched.

    Each track's result is stored as it finishes, so a step that runs again after
    a crash takes what it already did, and a later pass takes every COMPLETED track
    whose fingerprint is unchanged. A track a gate refused, or one an uncertain
    tool call cut short, is stored for this run alone.
    """

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        runtime = self._runtime
        if runtime is None:
            return _unconfigured()
        loaded = self._plan(context, step)
        if isinstance(loaded, Failed):
            return loaded
        plan_id, plan = loaded
        changed = _changed(runtime, plan)
        if changed is not None:
            return changed
        key = run_scoped(step.run_id, digest({"kind": "investigation", "plan": plan_id}))
        with context.transaction() as (session, _workflow):
            repo = self._repo(session, context)
            existing = self._find(repo, step, "investigation", key)
            if existing is not None:
                repo.read(existing.artifact_id)
                return _produced(existing, reused=True)

        meter = StepToolMeter.resuming(context, clock=runtime.clock)
        # Agent-directed tracks share the run's captures: a URL any track of this
        # attempt captured is answered from them and sends nothing. The planned mode
        # has no cache, as before.
        gate = self._gate(
            context,
            runtime,
            plan,
            meter,
            cache=RunSnapshotCache() if _agent_directed(plan) else None,
        )
        if runtime.config.fan_out:
            pending = self._unstored(step, context, plan, gate)
            if pending:
                return _hand_out(step, [(t, None) for t in pending])
        caller = self._caller(context, runtime)
        entries: list[TrackEntry] = []
        for track in plan.tracks:
            context.checkpoint()
            entries.append(self._track(step, context, runtime, plan, track, gate, meter, caller))
        lead = None
        if plan.lead_plan_artifact_id is not None:
            # A lead-planned run: its tasks' tracks, wave by wave, after the plan's own.
            try:
                lead_entries, lead = LeadWaves(
                    self,
                    step=step,
                    context=context,
                    runtime=runtime,
                    plan=plan,
                    lead_plan_id=plan.lead_plan_artifact_id,
                    gate=gate,
                    meter=meter,
                    caller=caller,
                    fan_out=runtime.config.fan_out,
                ).run()
            except WaveHandedOut as wave:
                # A wave's tracks are out in steps of their own: wait for them.
                return _hand_out(step, wave.tracks)
            entries += lead_entries
        record = InvestigationRecord(
            kind="deep_research_investigation",
            plan_artifact_id=plan_id,
            tracks=tuple(entries),
            lead=lead,
        )
        with context.transaction() as (session, _workflow):
            artifact, created = self._put(
                self._repo(session, context),
                step,
                payload=record,
                kind="investigation",
                key=key,
                depends_on=[plan_id, *(e.artifact_id for e in entries)],
            )
        context.progress(
            "deep_research_investigated",
            tracks=len(entries),
            reused=sum(1 for e in entries if e.reused),
        )
        return _produced(artifact, reused=not created)

    def _track(
        self,
        step: StepInput,
        context: StepContext,
        runtime: DeepResearchRuntime,
        plan: PlanRecord,
        track: ResearchTrack,
        gate: RetrievalGate | None,
        meter: StepToolMeter,
        caller: StepModelCaller,
        lead: LeadTask | None = None,
    ) -> TrackEntry:
        """One track's entry: found stored, or researched and stored.

        ``lead`` is a lead-planned task's brief and budget: its track runs agent-directed
        with them instead of the planner's queries and the plan's allowance.
        """
        mine = run_scoped(step.run_id, track.fingerprint)
        with context.transaction() as (session, _workflow):
            repo = self._repo(session, context)
            found = self._stored(repo, step, track)
            if found is not None:
                repo.read(found.artifact_id)
                return TrackEntry(
                    track_id=track.track_id,
                    artifact_id=found.artifact_id,
                    reused=self._reused(found, step),
                )

        blocked = plan.blocked_for(track.track_id)
        mode = runtime.retrieval.retrieval_mode if runtime.retrieval is not None else None
        result: TrackResult
        if blocked is not None:
            result = _blocked_result(step, track, blocked.stop_reason, blocked.detail, mode)
        elif track.channel is Channel.INTERNAL:
            result = self._internal(step, runtime, plan, track, caller)
        else:
            planned = lead.planned if lead is not None else plan.planned_for(track.track_id)
            if gate is None or planned is None:
                result = _blocked_result(
                    step,
                    track,
                    StopReason.PLAN_INCOMPLETE,
                    _detail(Gate.PLAN, "plan_incomplete", "no plan for this track"),
                    mode,
                )
            elif _agent_directed(plan):
                result = AgentDirectedTrack(
                    self,
                    step=step,
                    context=context,
                    runtime=runtime,
                    plan=plan,
                    track=track,
                    planned=planned,
                    gate=gate,
                    meter=meter,
                    caller=caller,
                    allowance=lead.allowance if lead is not None else None,
                    assignment=lead.assignment if lead is not None else None,
                ).run()
            else:
                result = self._web(
                    step, context, runtime, plan, track, planned, gate, meter, caller
                )

        key = track.fingerprint if result.status is TrackStatus.COMPLETED else mine
        with context.transaction() as (session, _workflow):
            artifact, _created = self._put(
                self._repo(session, context),
                step,
                payload=result,
                kind="track",
                key=key,
                depends_on=[
                    *(s.artifact_id for s in result.snapshots),
                    *([result.transcript_artifact_id] if result.transcript_artifact_id else []),
                ],
            )
        context.progress(
            "deep_research_track",
            track_id=track.track_id,
            channel=track.channel.value,
            status=result.status.value,
            stop_reason=result.stop_reason.value,
            model_requests=len(result.calls),
            search_calls=result.search_calls,
            fetches=result.fetches,
            evidence=len(result.evidence),
            quarantined=len(result.quarantined),
        )
        return TrackEntry(track_id=track.track_id, artifact_id=artifact.artifact_id, reused=False)

    # -- fan-out ----------------------------------------------------------------

    def _gate(
        self,
        context: StepContext,
        runtime: DeepResearchRuntime,
        plan: PlanRecord,
        meter: StepToolMeter,
        *,
        cache: RunSnapshotCache | None,
    ) -> RetrievalGate | None:
        """The step's gate over the composition's retrieval; None when it has none."""
        if runtime.retrieval is None:
            return None
        return RetrievalGate(
            retrieval=runtime.retrieval,
            scope=context.scope,
            meter=meter,
            client_terms=plan.request.client_terms,
            class_a_texts=_class_a_texts(plan.request),
            clock=runtime.clock,
            cache=cache,
            archive=runtime.archive,
            datasets=runtime.datasets,
            archives=runtime.archives,
        )

    def _stored(
        self, repo: ArtifactRepository, step: StepInput, track: ResearchTrack
    ) -> Artifact | None:
        """The track's stored result: by fingerprint (any run), else this run's own."""
        return self._find(repo, step, "track", track.fingerprint) or self._find(
            repo, step, "track", run_scoped(step.run_id, track.fingerprint)
        )

    def stored_track(self, step: StepInput, context: StepContext, track: ResearchTrack) -> bool:
        """True when the track's result is stored (a reused, done or handed-out track)."""
        with context.transaction() as (session, _workflow):
            return self._stored(self._repo(session, context), step, track) is not None

    @staticmethod
    def researches(
        plan: PlanRecord, track: ResearchTrack, gate: RetrievalGate | None, *, lead: bool = False
    ) -> bool:
        """Whether :meth:`_track` would research the track (and so may send something).

        Exactly its branches: a blocked track, and a web track with no retrieval or no
        plan, are recorded without a call -- inline, never handed out.
        """
        if lead:
            return gate is not None
        if plan.blocked_for(track.track_id) is not None:
            return False
        if track.channel is Channel.INTERNAL:
            return True
        return gate is not None and plan.planned_for(track.track_id) is not None

    def _unstored(
        self,
        step: StepInput,
        context: StepContext,
        plan: PlanRecord,
        gate: RetrievalGate | None,
    ) -> list[ResearchTrack]:
        """The plan's tracks that would be researched and are not stored yet, in plan order."""
        with context.transaction() as (session, _workflow):
            repo = self._repo(session, context)
            return [
                t
                for t in plan.tracks
                if self.researches(plan, t, gate) and self._stored(repo, step, t) is None
            ]

    # -- internal ---------------------------------------------------------------

    def _internal(
        self,
        step: StepInput,
        runtime: DeepResearchRuntime,
        plan: PlanRecord,
        track: ResearchTrack,
        caller: StepModelCaller,
    ) -> TrackResult:
        """Approved knowledge the subject names, read by code; one investigator request."""
        request = plan.request
        items = retrieve(
            request.knowledge, [track.subject.text], limit=plan.depth.knowledge_items_per_track
        )
        base = _blocked_result(step, track, StopReason.NO_KNOWLEDGE_MATCHED, "", None)
        if not items:
            return base.model_copy(update={"status": TrackStatus.COMPLETED})
        refs = tuple(i.ref for i in items)
        dclass = request_class(design=plan.design_class, sources=[i.data_class for i in items])
        answer = self._ask(
            caller,
            runtime,
            AgentRole.INTERNAL_INVESTIGATOR,
            payload={
                "track_id": track.track_id,
                "subject": {"kind": track.subject.kind.value, "text": track.subject.text},
                "brief": {"title": request.brief.title, "goal": request.brief.goal},
                "sources": [
                    {
                        "source_id": i.ref,
                        "kind": i.kind,
                        "title": i.title,
                        "text": i.text[:SOURCE_TEXT_CHARS],
                        "text_truncated": i.truncated or len(i.text) > SOURCE_TEXT_CHARS,
                    }
                    for i in items
                ],
            },
            data_class=dclass,
            lineage=_lineage(items),
        )
        if answer.gate is not None:
            stop = (
                StopReason.CONTEXT_TOO_LARGE
                if answer.gate is Gate.CONTEXT_WINDOW
                else StopReason.MODEL_ROUTE_REFUSED
            )
            return base.model_copy(
                update={
                    "stop_reason": stop,
                    "detail": _detail(answer.gate, answer.reason, answer.detail),
                    "knowledge_refs": refs,
                }
            )
        assert isinstance(answer.output, ExtractionProposal) and answer.call is not None
        findings = _Findings(track=track, data_class=dclass, evidence=[], quarantined=[])
        findings.add(
            answer.output.evidence,
            sources={
                i.ref: GroundableSource(i.ref, i.text, detect_instructions(i.text)) for i in items
            },
            kind=SourceKind.CLIENT_KNOWLEDGE,
            urls={},
            titles={i.ref: i.title for i in items},
        )
        return base.model_copy(
            update={
                "status": TrackStatus.COMPLETED,
                "stop_reason": StopReason.SINGLE_PASS,
                "knowledge_refs": refs,
                "sources": tuple(
                    SourceFactsRecord(
                        ref=i.ref,
                        kind=SourceKind.CLIENT_KNOWLEDGE,
                        url=None,
                        published=None,
                        retrieved=None,
                    )
                    for i in items
                ),
                "evidence": tuple(findings.evidence),
                "quarantined": tuple(findings.quarantined),
                "gaps": tuple(answer.output.gaps),
                "calls": (answer.call,),
                "model_cost_usd": answer.call.cost_usd,
            }
        )

    # -- web --------------------------------------------------------------------

    def _snapshot(
        self, context: StepContext, step: StepInput, page: FetchedPage
    ) -> tuple[SnapshotRef, SnapshotArtifact]:
        """Store a page once per content address; what is stored is what the track cites."""
        stored = SnapshotArtifact(
            kind="deep_research_source_snapshot", snapshot=page.snapshot, published=page.published
        )
        with context.transaction() as (session, _workflow):
            repo = self._repo(session, context)
            artifact, created = self._put(
                repo, step, payload=stored, kind="snapshot", key=page.snapshot.snapshot_id
            )
            if not created:
                stored = self._read(repo, artifact.artifact_id, SnapshotArtifact)
        return self._snapshot_ref(artifact.artifact_id, stored), stored

    @staticmethod
    def _snapshot_ref(artifact_id: str, stored: SnapshotArtifact) -> SnapshotRef:
        s = stored.snapshot
        return SnapshotRef(
            snapshot_id=s.snapshot_id,
            artifact_id=artifact_id,
            url=s.url,
            final_url=s.final_url,
            title=s.title,
            retrieved_at=s.retrieved_at,
            text_sha256=s.text_sha256,
            retrieval_mode=s.retrieval_mode,
            instructions_detected=s.instructions_detected,
        )

    def _read_snapshot(self, context: StepContext, artifact_id: str) -> SnapshotArtifact:
        """A snapshot this run stored, read back (and verified) for a replayed turn."""
        with context.transaction() as (session, _workflow):
            return self._read(self._repo(session, context), artifact_id, SnapshotArtifact)

    def _web(
        self,
        step: StepInput,
        context: StepContext,
        runtime: DeepResearchRuntime,
        plan: PlanRecord,
        track: ResearchTrack,
        planned: PlannedTrack,
        gate: RetrievalGate,
        meter: StepToolMeter,
        caller: StepModelCaller,
    ) -> TrackResult:
        """Search, fetch, snapshot and ask, round by round, until a stop rule ends the track.

        One round is one query: its results fetched (within the track's allowance,
        each URL once), each page snapshotted, then one investigator request over the
        round's new pages. The stop rule is checked before every round.

        Every external outcome is durable before the next call leaves
        (:class:`_PlannedLog`): the search with its hits in order, each fetch with the
        page it captured, the round once its fetches resolved, the investigator's
        answer before it is grounded. A step that runs again walks the same sequence,
        reads each record in place of the call it stands for, and goes live at the
        first one missing -- unless an earlier attempt dispatched a call no record
        accounts for: what came back is not known, so the track ends
        ``TOOL_OUTCOME_UNCERTAIN`` and nothing more is sent.
        """
        depth = plan.depth
        allowance = plan.allowances.get(track.track_id) or AllowanceRecord(
            search_calls=0, fetches=0
        )
        assert runtime.retrieval is not None
        mode = runtime.retrieval.retrieval_mode
        queries = list(planned.queries)
        log = _PlannedLog(self, step, context, track, meter)
        records: list[QueryRecord] = []
        refs: dict[str, SnapshotRef] = {}
        stored: dict[str, SnapshotArtifact] = {}
        fetched_urls: set[str] = set()
        findings = _Findings(track=track, data_class=plan.design_class, evidence=[], quarantined=[])
        calls: list[CallRecord] = []
        new_by_round: list[int] = []
        # What this track dispatched, counted along the walk: a replayed record counts
        # as the dispatch it records, so the allowance is the one the track spent
        # (the resumed meter already holds every earlier attempt's dispatches).
        searches_used = fetches_used = 0
        status, stop, detail = TrackStatus.COMPLETED, None, ""

        for i, query in enumerate(queries):
            stop = stop_reason(
                grounded=len(findings.evidence),
                new_by_round=new_by_round,
                queries_left=len(queries) - i,
                searches_left=allowance.search_calls - searches_used,
                depth=depth,
            )
            if stop is not None:
                break
            search = log.search(i, query)
            if search is None:
                if log.unaccounted():
                    status, stop, detail = _uncertain_earlier()
                    break
                context.checkpoint()
                outcome = gate.search(
                    query,
                    context_class=plan.design_class,
                    track_id=track.track_id,
                    max_results=depth.pages_per_query,
                )
                search = log.searched(i, query, outcome)
            records.append(search.record)
            if search.request_fingerprint is not None:
                searches_used += 1
            if search.record.decision is QueryDecision.REFUSED:
                continue
            if search.uncertain:
                status, stop = TrackStatus.INCOMPLETE, StopReason.TOOL_OUTCOME_UNCERTAIN
                detail = f"the search for {query!r} may have been served; nothing more is sent"
                break
            if search.record.failure is not None:
                # A known failure returned nothing: it says nothing about saturation.
                continue
            done = log.round(i)
            fetches: list[PlannedFetch] = []
            pages: list[SnapshotArtifact] = []
            for position, hit in enumerate(search.hits):
                if fetches_used >= allowance.fetches:
                    break
                url_key = canonical_url(hit.url) or hit.url
                if url_key in fetched_urls:
                    continue
                fetched_urls.add(url_key)
                fetch: PlannedFetch | None
                if done is not None:
                    fetch = done.fetches[len(fetches)]
                    assert fetch.position == position, "a round replays the fetches it made"
                    log.replayed(fetch.request_fingerprint)
                else:
                    fetch = log.fetch(i, position)
                if fetch is None:
                    if log.unaccounted():
                        status, stop, detail = _uncertain_earlier()
                        break
                    got = gate.fetch(hit.url, track_id=track.track_id)
                    captured = None
                    if got.page is not None and not got.uncertain:
                        captured = self._snapshot(context, step, got.page)
                    fetch = log.fetched(i, position, got, captured)
                    snap = captured[1] if captured is not None else None
                else:
                    snap = (
                        self._read_snapshot(context, fetch.snapshot_artifact_id)
                        if fetch.snapshot_artifact_id is not None
                        else None
                    )
                fetches.append(fetch)
                if fetch.request_fingerprint is not None:
                    fetches_used += 1
                if fetch.uncertain:
                    status, stop = TrackStatus.INCOMPLETE, StopReason.TOOL_OUTCOME_UNCERTAIN
                    detail = f"the fetch of {hit.url} may have been served; nothing more is sent"
                    break
                if snap is None:
                    continue
                assert fetch.snapshot_artifact_id is not None
                ref = self._snapshot_ref(fetch.snapshot_artifact_id, snap)
                if ref.snapshot_id not in refs:
                    refs[ref.snapshot_id] = ref
                    stored[ref.snapshot_id] = snap
                    pages.append(snap)
            if status is TrackStatus.INCOMPLETE:
                # The round's last fetch may have been served: nothing more is sent, not
                # even the investigator request over the pages it did capture.
                break
            if done is None:
                log.rounded(i, query, fetches)
            if pages:
                new = self._investigate_pages(
                    caller,
                    runtime,
                    plan,
                    track,
                    planned,
                    pages,
                    stored,
                    findings,
                    calls,
                    log=log,
                    round_index=i,
                )
                if isinstance(new, _Answer):
                    stop = (
                        StopReason.CONTEXT_TOO_LARGE
                        if new.gate is Gate.CONTEXT_WINDOW
                        else StopReason.MODEL_ROUTE_REFUSED
                    )
                    status = TrackStatus.INCOMPLETE
                    assert new.gate is not None
                    detail = _detail(new.gate, new.reason, new.detail)
                    break
                new_by_round.append(new)
            else:
                new_by_round.append(0)

        searches, fetched, charged, tool_cost = meter.track_usage(track.track_id)
        sent = [r for r in records if r.decision is QueryDecision.SENT]
        if status is TrackStatus.COMPLETED:
            if records and not sent:
                status, stop = TrackStatus.BLOCKED, StopReason.ALL_QUERIES_REFUSED
                reasons = sorted({r.refusal or "" for r in records})
                detail = _detail(Gate.SEARCH_ROUTE, "all_queries_refused", ", ".join(reasons))
            elif not records and not queries:
                status, stop = TrackStatus.BLOCKED, StopReason.PLAN_INCOMPLETE
                detail = _detail(Gate.PLAN, "plan_incomplete", "the plan gave no query")
            elif stop is None:
                stop = (
                    stop_reason(
                        grounded=len(findings.evidence),
                        new_by_round=new_by_round,
                        queries_left=0,
                        searches_left=allowance.search_calls - searches,
                        depth=depth,
                    )
                    or StopReason.QUERIES_EXHAUSTED
                )
        assert stop is not None
        return TrackResult(
            kind="deep_research_track",
            run_id=step.run_id,
            track=track,
            status=status,
            stop_reason=stop,
            detail=detail[:2000],
            retrieval_mode=mode,
            sub_questions=planned.sub_questions,
            queries=tuple(records),
            snapshots=tuple(refs.values()),
            knowledge_refs=(),
            sources=tuple(
                SourceFactsRecord(
                    ref=s.snapshot.snapshot_id,
                    kind=SourceKind.WEB_PAGE,
                    url=s.snapshot.final_url,
                    published=s.published,
                    retrieved=s.snapshot.retrieved_at.date(),
                    doi=s.snapshot.doi,
                )
                for s in stored.values()
            ),
            evidence=tuple(findings.evidence),
            quarantined=tuple(findings.quarantined),
            gaps=(),
            calls=tuple(calls),
            search_calls=searches,
            fetches=fetched,
            credits=charged,
            model_cost_usd=sum(c.cost_usd for c in calls),
            tool_cost_usd=tool_cost,
        )

    def _investigate_pages(
        self,
        caller: StepModelCaller,
        runtime: DeepResearchRuntime,
        plan: PlanRecord,
        track: ResearchTrack,
        planned: PlannedTrack,
        pages: Sequence[SnapshotArtifact],
        stored: dict[str, SnapshotArtifact],
        findings: _Findings,
        calls: list[CallRecord],
        *,
        log: _PlannedLog,
        round_index: int,
    ) -> int | _Answer:
        """One investigator request over a round's new pages; the count newly grounded.

        The answer is stored the moment it returns, before it is grounded; a step that
        runs again grounds the stored answer and asks nothing.
        """
        data_class = plan.design_class
        request = self._request(
            runtime,
            AgentRole.WEB_INVESTIGATOR,
            payload={
                "track_id": track.track_id,
                "subject": {"kind": track.subject.kind.value, "text": track.subject.text},
                "sub_questions": list(planned.sub_questions),
                "brief": {"title": plan.request.brief.title, "goal": plan.request.brief.goal},
                "sources": [
                    {
                        "source_id": p.snapshot.snapshot_id,
                        "url": p.snapshot.final_url,
                        "title": p.snapshot.title,
                        "published": p.published.isoformat() if p.published else None,
                        "text": p.snapshot.text[:SOURCE_TEXT_CHARS],
                        "text_truncated": len(p.snapshot.text) > SOURCE_TEXT_CHARS,
                    }
                    for p in pages
                ],
            },
            data_class=data_class,
            lineage=DataLineage.none(),
        )
        sha = request_sha256(request)
        answered = log.answer(round_index, sha)
        if answered is not None:
            output, call = answered.output, answered.call
        else:
            answer = self._send(
                caller, runtime, AgentRole.WEB_INVESTIGATOR, request, data_class=data_class
            )
            if answer.gate is not None:
                return answer
            assert isinstance(answer.output, ExtractionProposal) and answer.call is not None
            output, call = answer.output, answer.call
            log.answered(round_index, sha, output, call)
        calls.append(call)
        snaps: dict[str, SourceSnapshot] = {k: v.snapshot for k, v in stored.items()}
        grounded, _quarantined = findings.add(
            output.evidence,
            sources={
                k: GroundableSource(k, s.text, s.instructions_detected) for k, s in snaps.items()
            },
            kind=SourceKind.WEB_PAGE,
            urls={k: s.final_url for k, s in snaps.items()},
            titles={k: s.title for k, s in snaps.items()},
        )
        return len(grounded)


def _uncertain_earlier() -> tuple[TrackStatus, StopReason, str]:
    """An earlier attempt dispatched a call for this track that no record accounts for."""
    return (
        TrackStatus.INCOMPLETE,
        StopReason.TOOL_OUTCOME_UNCERTAIN,
        "a call an earlier attempt sent for this track may have been served; nothing more is sent",
    )


class _PlannedLog:
    """A planned web track's durable record of every external outcome, for this run alone.

    Each record is keyed by the track's fingerprint, the round and what the call was
    (``run_scoped``), and written the moment its outcome is known. Reading one back
    consumes the dispatch it records from what the earlier attempts journaled, so
    :meth:`unaccounted` is true exactly when an earlier attempt sent a call whose
    outcome no record holds -- the only case a recovered track cannot continue.
    """

    def __init__(
        self,
        executor: InvestigateExecutor,
        step: StepInput,
        context: StepContext,
        track: ResearchTrack,
        meter: StepToolMeter,
    ) -> None:
        self._executor, self._step, self._context, self._track = executor, step, context, track
        self._meter = meter
        self._earlier = meter.dispatched_earlier(track.track_id)

    def _key(self, kind: str, *parts: object) -> str:
        return run_scoped(
            self._step.run_id, digest([f"planned_{kind}", self._track.fingerprint, *parts])
        )

    def _find(self, kind: str, key: str, model: type[_R]) -> _R | None:
        with self._context.transaction() as (session, _workflow):
            repo = self._executor._repo(session, self._context)
            found = self._executor._find(repo, self._step, kind, key)
            if found is None:
                return None
            return self._executor._read(repo, found.artifact_id, model)

    def _put(self, kind: str, key: str, payload: BaseModel) -> None:
        with self._context.transaction() as (session, _workflow):
            self._executor._put(
                self._executor._repo(session, self._context),
                self._step,
                payload=payload,
                kind=kind,
                key=key,
            )

    def replayed(self, fingerprint: str | None) -> None:
        """A recorded call stands for one dispatch an earlier attempt journaled."""
        if fingerprint is not None and self._earlier[fingerprint] > 0:
            self._earlier[fingerprint] -= 1

    def unaccounted(self) -> bool:
        """True when a call may have been served with no record of what came back."""
        return self._meter.uncertain(self._track.track_id) or any(
            n > 0 for n in self._earlier.values()
        )

    # -- search ------------------------------------------------------------------

    def search(self, round_index: int, query: str) -> PlannedSearch | None:
        found = self._find("planned_search", self._key("search", round_index, query), PlannedSearch)
        if found is not None:
            self.replayed(found.request_fingerprint)
        return found

    def searched(self, round_index: int, query: str, outcome: SearchOutcome) -> PlannedSearch:
        record = PlannedSearch(
            kind="deep_research_planned_search",
            track_id=self._track.track_id,
            round=round_index,
            query=query,
            record=outcome.record,
            hits=tuple(
                PlannedHit(url=h.url, title=h.title, snippet=h.snippet, rank=h.rank)
                for h in outcome.hits
            ),
            uncertain=outcome.uncertain,
            request_fingerprint=outcome.request_fingerprint,
        )
        self._put("planned_search", self._key("search", round_index, query), record)
        return record

    # -- fetch -------------------------------------------------------------------

    def fetch(self, round_index: int, position: int) -> PlannedFetch | None:
        found = self._find("planned_fetch", self._key("fetch", round_index, position), PlannedFetch)
        if found is not None:
            self.replayed(found.request_fingerprint)
        return found

    def fetched(
        self,
        round_index: int,
        position: int,
        outcome: FetchOutcome,
        captured: tuple[SnapshotRef, SnapshotArtifact] | None,
    ) -> PlannedFetch:
        record = PlannedFetch(
            kind="deep_research_planned_fetch",
            track_id=self._track.track_id,
            round=round_index,
            position=position,
            url=outcome.url,
            request_fingerprint=outcome.request_fingerprint,
            reason=outcome.reason,
            uncertain=outcome.uncertain,
            snapshot_artifact_id=captured[0].artifact_id if captured is not None else None,
        )
        self._put("planned_fetch", self._key("fetch", round_index, position), record)
        return record

    # -- round -------------------------------------------------------------------

    def round(self, round_index: int) -> PlannedRound | None:
        return self._find("planned_round", self._key("round", round_index), PlannedRound)

    def rounded(self, round_index: int, query: str, fetches: Sequence[PlannedFetch]) -> None:
        self._put(
            "planned_round",
            self._key("round", round_index),
            PlannedRound(
                kind="deep_research_planned_round",
                track_id=self._track.track_id,
                round=round_index,
                query=query,
                fetches=tuple(fetches),
            ),
        )

    # -- answer ------------------------------------------------------------------

    def answer(self, round_index: int, sha: str) -> PlannedRoundAnswer | None:
        return self._find(
            "planned_round_answer", self._key("answer", round_index, sha), PlannedRoundAnswer
        )

    def answered(
        self, round_index: int, sha: str, output: ExtractionProposal, call: CallRecord
    ) -> None:
        self._put(
            "planned_round_answer",
            self._key("answer", round_index, sha),
            PlannedRoundAnswer(
                kind="deep_research_planned_round_answer",
                track_id=self._track.track_id,
                round=round_index,
                request_sha256=sha,
                output=output,
                call=call,
            ),
        )


def _changed(runtime: DeepResearchRuntime, plan: PlanRecord) -> Failed | None:
    """Refuse a composition whose rules, policy or retrieval are not the plan's."""
    inputs = runtime.inputs()
    if (
        runtime.versions() != plan.versions
        or (dict(inputs.web_retrieval) if inputs.web_retrieval is not None else None)
        != plan.web_retrieval
    ):
        return _composition_changed("the composition's rules, policy or retrieval")
    return None


def _hand_out(step: StepInput, tracks: Sequence[tuple[ResearchTrack, LeadTask | None]]) -> Deferred:
    """Every track as a step of its own; this step waits for them (``Deferred``)."""
    children: list[ChildStep] = [track_child(step, t, lead) for t, lead in tracks]
    return Deferred(
        children=tuple(children),
        output={"handed_out": [t.track_id for t, _lead in tracks]},
    )


# --------------------------------------------------------------------------- #
# A track's own step
# --------------------------------------------------------------------------- #


class InvestigateTrackExecutor(InvestigateExecutor):
    """One track a fanned-out ``investigate`` handed out, researched in a step of its own.

    The same research as the sequential step -- :meth:`InvestigateExecutor._track`, with
    its own resumed tool meter, gate and model caller -- so the artifact it stores is the
    one the join finds. Its input is re-checked first: the run's plan read through the
    run, the composition the plan's, the track the plan's (or, for a lead task, a web
    track of a subject of a lead-planned run), and the fingerprint and node key the ones
    the track was handed out under. In agent-directed mode the run's snapshot cache is
    the store's (:class:`~aia_executors.deep_research.fan_out.StoredRunSnapshotCache`),
    so a URL another track step captured is not fetched again.
    """

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        runtime = self._runtime
        if runtime is None:
            return _unconfigured()
        loaded = self._plan(context, step)
        if isinstance(loaded, Failed):
            return loaded
        _plan_id, plan = loaded
        changed = _changed(runtime, plan)
        if changed is not None:
            return changed
        try:
            payload = TrackStepPayload.model_validate(step.payload)
        except ValidationError as exc:
            return _invalid("track_payload_invalid", f"the track's input does not validate: {exc}")
        track = payload.track
        if (
            track.fingerprint != step.input_fingerprint
            or track_step_key(track.track_id) != step.node_key
        ):
            return _invalid("request_altered", "the track is not the one this step was handed")
        lead: LeadTask | None = None
        if payload.lead is None:
            if track not in plan.tracks:
                return _invalid("track_not_planned", "the run's plan has no such track")
        else:
            if (
                plan.lead_plan_artifact_id is None
                or track.channel is not Channel.WEB
                or track.subject.key not in {s.key for s in plan.subjects}
                or payload.lead.planned.track_id != track.track_id
            ):
                return _invalid("track_not_planned", "the run's lead planned no such task")
            lead = payload.lead.task()
        meter = StepToolMeter.resuming(context, clock=runtime.clock)
        gate = self._gate(
            context,
            runtime,
            plan,
            meter,
            cache=StoredRunSnapshotCache(self, context, step) if _agent_directed(plan) else None,
        )
        entry = self._track(
            step,
            context,
            runtime,
            plan,
            track,
            gate,
            meter,
            self._caller(context, runtime),
            lead=lead,
        )
        with context.transaction() as (session, _workflow):
            artifact = self._repo(session, context).get(entry.artifact_id)
        return _produced(artifact, reused=entry.reused, track_id=track.track_id)
