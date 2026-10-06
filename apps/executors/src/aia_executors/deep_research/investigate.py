"""The ``investigate`` step: every track, reused or researched, grounded in what it captured."""

from __future__ import annotations

from collections.abc import Sequence

from aia_core.application.web_retrieval import RetrievalGate, RunSnapshotCache
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
    PlannedTrack,
    PlanRecord,
    SnapshotArtifact,
    SourceFactsRecord,
    TrackEntry,
    TrackResult,
    run_scoped,
)
from aia_core.domain.licence import DataLineage
from aia_core.infrastructure.web_retrieval import FetchedPage
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome

from ..ai_step import StepModelCaller
from ._findings import _blocked_result, _Findings
from ._shared import (
    _Answer,
    _class_a_texts,
    _composition_changed,
    _detail,
    _lineage,
    _produced,
    _Step,
    _unconfigured,
)
from .agent_directed import AgentDirectedTrack
from .runtime import DeepResearchRuntime, StepToolMeter

__all__ = ["InvestigateExecutor"]

# --------------------------------------------------------------------------- #
# investigate
# --------------------------------------------------------------------------- #


def _agent_directed(plan: PlanRecord) -> bool:
    """Whether the run was planned with agent-directed web tracks (recorded on the plan)."""
    return "investigator" in plan.versions


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
        inputs = runtime.inputs()
        if (
            runtime.versions() != plan.versions
            or (dict(inputs.web_retrieval) if inputs.web_retrieval is not None else None)
            != plan.web_retrieval
        ):
            return _composition_changed("the composition's rules, policy or retrieval")
        key = run_scoped(step.run_id, digest({"kind": "investigation", "plan": plan_id}))
        with context.transaction() as (session, _workflow):
            repo = self._repo(session, context)
            existing = self._find(repo, step, "investigation", key)
            if existing is not None:
                repo.read(existing.artifact_id)
                return _produced(existing, reused=True)

        meter = StepToolMeter.resuming(context, clock=runtime.clock)
        gate = (
            RetrievalGate(
                retrieval=runtime.retrieval,
                scope=context.scope,
                meter=meter,
                client_terms=plan.request.client_terms,
                class_a_texts=_class_a_texts(plan.request),
                clock=runtime.clock,
                # Agent-directed tracks share the run's captures: a URL any track of
                # this attempt captured is answered from them and sends nothing. The
                # planned mode has no cache, as before.
                cache=RunSnapshotCache() if _agent_directed(plan) else None,
            )
            if runtime.retrieval is not None
            else None
        )
        caller = self._caller(context, runtime)
        entries: list[TrackEntry] = []
        for track in plan.tracks:
            context.checkpoint()
            entries.append(self._track(step, context, runtime, plan, track, gate, meter, caller))
        record = InvestigationRecord(
            kind="deep_research_investigation", plan_artifact_id=plan_id, tracks=tuple(entries)
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
    ) -> TrackEntry:
        mine = run_scoped(step.run_id, track.fingerprint)
        with context.transaction() as (session, _workflow):
            repo = self._repo(session, context)
            found = self._find(repo, step, "track", track.fingerprint) or self._find(
                repo, step, "track", mine
            )
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
            planned = plan.planned_for(track.track_id)
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
                depends_on=[s.artifact_id for s in result.snapshots],
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
        """
        depth = plan.depth
        allowance = plan.allowances.get(track.track_id) or AllowanceRecord(
            search_calls=0, fetches=0
        )
        assert runtime.retrieval is not None
        mode = runtime.retrieval.retrieval_mode
        queries = list(planned.queries)
        records: list[QueryRecord] = []
        refs: dict[str, SnapshotRef] = {}
        stored: dict[str, SnapshotArtifact] = {}
        fetched_urls: set[str] = set()
        findings = _Findings(track=track, data_class=plan.design_class, evidence=[], quarantined=[])
        calls: list[CallRecord] = []
        new_by_round: list[int] = []
        status, stop, detail = TrackStatus.COMPLETED, None, ""

        for i, query in enumerate(queries):
            if meter.uncertain(track.track_id):
                # An earlier attempt of this step sent a call for this track and stopped
                # before its outcome was on record: resuming closed it as uncertain.
                status, stop = TrackStatus.INCOMPLETE, StopReason.TOOL_OUTCOME_UNCERTAIN
                detail = (
                    "a call an earlier attempt sent for this track may have been served; "
                    "nothing more is sent"
                )
                break
            searches, fetches, _credits, _cost = meter.track_usage(track.track_id)
            stop = stop_reason(
                grounded=len(findings.evidence),
                new_by_round=new_by_round,
                queries_left=len(queries) - i,
                searches_left=allowance.search_calls - searches,
                depth=depth,
            )
            if stop is not None:
                break
            context.checkpoint()
            outcome = gate.search(
                query,
                context_class=plan.design_class,
                track_id=track.track_id,
                max_results=depth.pages_per_query,
            )
            records.append(outcome.record)
            if outcome.record.decision is QueryDecision.REFUSED:
                continue
            if outcome.uncertain:
                status, stop = TrackStatus.INCOMPLETE, StopReason.TOOL_OUTCOME_UNCERTAIN
                detail = f"the search for {query!r} may have been served; nothing more is sent"
                break
            if outcome.record.failure is not None:
                # A known failure returned nothing: it says nothing about saturation.
                continue
            pages: list[SnapshotArtifact] = []
            for hit in outcome.hits:
                if meter.track_usage(track.track_id)[1] >= allowance.fetches:
                    break
                url_key = canonical_url(hit.url) or hit.url
                if url_key in fetched_urls:
                    continue
                fetched_urls.add(url_key)
                got = gate.fetch(hit.url, track_id=track.track_id)
                if got.uncertain:
                    status, stop = TrackStatus.INCOMPLETE, StopReason.TOOL_OUTCOME_UNCERTAIN
                    detail = f"the fetch of {hit.url} may have been served; nothing more is sent"
                    break
                if got.page is None:
                    continue
                ref, snap = self._snapshot(context, step, got.page)
                if ref.snapshot_id not in refs:
                    refs[ref.snapshot_id] = ref
                    stored[ref.snapshot_id] = snap
                    pages.append(snap)
            if status is TrackStatus.INCOMPLETE:
                # The round's last fetch may have been served: nothing more is sent, not
                # even the investigator request over the pages it did capture.
                break
            if pages:
                new = self._investigate_pages(
                    caller, runtime, plan, track, planned, pages, stored, findings, calls
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

        searches, fetches, charged, tool_cost = meter.track_usage(track.track_id)
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
                )
                for s in stored.values()
            ),
            evidence=tuple(findings.evidence),
            quarantined=tuple(findings.quarantined),
            gaps=(),
            calls=tuple(calls),
            search_calls=searches,
            fetches=fetches,
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
    ) -> int | _Answer:
        """One investigator request over a round's new pages; the count newly grounded."""
        answer = self._ask(
            caller,
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
            data_class=plan.design_class,
            lineage=DataLineage.none(),
        )
        if answer.gate is not None:
            return answer
        assert isinstance(answer.output, ExtractionProposal) and answer.call is not None
        calls.append(answer.call)
        snaps: dict[str, SourceSnapshot] = {k: v.snapshot for k, v in stored.items()}
        grounded, _quarantined = findings.add(
            answer.output.evidence,
            sources={
                k: GroundableSource(k, s.text, s.instructions_detected) for k, s in snaps.items()
            },
            kind=SourceKind.WEB_PAGE,
            urls={k: s.final_url for k, s in snaps.items()},
            titles={k: s.title for k, s in snaps.items()},
        )
        return len(grounded)
