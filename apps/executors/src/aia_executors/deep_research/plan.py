"""The ``plan`` step: tracks, reuse, and the planner's queries for the web tracks left.

In a lead-planned run (``DeepResearchConfig.lead``) the lead researcher plans the web
tracks instead of the planner (``lead.LeadPlanning``): its plan is stored as the run's
own artifact and the web subjects it planned run as its tasks' tracks at investigate.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from aia_core.application.web_retrieval import RetrievalGate
from aia_core.domain.ai_material import classify_material
from aia_core.domain.deep_research.agents import AgentRole, PlanProposal
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    Channel,
    DeepResearchRequest,
    ResearchTrack,
    StopReason,
    digest,
)
from aia_core.domain.deep_research.planning import (
    DepthPreset,
    UnknownPreset,
    allocate,
    build_tracks,
    check_plan_coverage,
    preset,
)
from aia_core.domain.deep_research.settings import SettingsPinCorrupt, read_pin
from aia_core.domain.deep_research.steps import (
    AllowanceRecord,
    BlockedTrack,
    CallRecord,
    Gate,
    PlannedTrack,
    PlanRecord,
    PlanViolationRecord,
    run_scoped,
)
from aia_core.domain.licence import DataLineage
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.study_design_repository import (
    DesignRevisionNotFound,
    StudyDesignRepository,
)
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome
from pydantic import ValidationError

from ._shared import _class_a_texts, _detail, _invalid, _produced, _Step, _subjects, _unconfigured
from .lead import LeadPlanned, LeadPlanning
from .runtime import StepToolMeter

__all__ = ["PlanExecutor"]

# --------------------------------------------------------------------------- #
# plan
# --------------------------------------------------------------------------- #


class PlanExecutor(_Step):
    """Tracks, their fingerprints and reuse; the planner's queries for the web tracks left.

    The planner is asked only when a web track needs research, retrieval exists,
    and a query written from the design's class could leave at all: a Class A
    design's queries never do (``class_a_query``), so no model is paid to write them.
    """

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        runtime = self._runtime
        if runtime is None:
            return _unconfigured()
        try:
            request = DeepResearchRequest.model_validate(step.payload["request"])
        except (KeyError, ValidationError) as exc:
            return _invalid("request_invalid", f"the run's request does not validate: {exc}")
        if request.fingerprint() != step.input_fingerprint:
            return _invalid("request_altered", "the request is not the one the run was created for")
        pinned = step.payload.get("settings")
        if pinned is not None:
            # ADR 0022 decision 4: the run runs under the settings it pinned at enqueue, and
            # a pin that does not prove itself is not run (a run enqueued before pins carries
            # none and is read as it always was).
            try:
                settings = read_pin(pinned)
            except SettingsPinCorrupt as exc:
                return _invalid(f"settings_{exc.reason}", str(exc))
            if settings.approved_method() != request.settings_method:
                # The request's method identity must be the pin's: anything else would key
                # this run's work under settings it does not run under.
                return _invalid(
                    "settings_mismatch",
                    "the request's method settings are not the ones the run pinned",
                )
        if request.harness_version != HARNESS_VERSION:
            # Frozen for an earlier method: executed now it would run under another
            # one and be labelled with the first. It stays readable; it is not run.
            return _invalid(
                "harness_changed",
                f"the run was frozen for {request.harness_version}, not {HARNESS_VERSION}; "
                "start a new run",
            )
        try:
            depth = preset(request.preset)
        except UnknownPreset as exc:
            return _invalid("unknown_preset", str(exc))
        with context.transaction() as (session, _workflow):
            designs = StudyDesignRepository(session, context.scope)
            try:
                revision = designs.get(request.design_revision_id)
            except DesignRevisionNotFound:
                return _invalid(
                    "design_not_in_scope", "the run's Design Revision is not this Study's"
                )
            if (
                revision.revision != step.project_revision
                or designs.project_id() != step.project_id
            ):
                return _invalid("design_not_in_scope", "the run's design does not match its scope")
            decision = classify_material(
                designs.content(request.design_revision_id), runtime.config.material_approvals
            )
        dclass = decision.data_class
        if dclass is None:
            return Failed(
                FailureClass.RUNTIME_UNAVAILABLE,
                error={
                    "reason": "egress_unclassified_material",
                    "message": "Zadání nemá klasifikaci vstupních dat. Nic nebylo odesláno.",
                },
            )
        fictional = any(
            approval.sha256 == decision.sha256 and approval.synthetic
            for approval in runtime.config.material_approvals
        )
        inputs = runtime.inputs()
        tracks, beyond = build_tracks(request, depth, inputs=inputs)
        versions = runtime.versions()
        key = run_scoped(
            step.run_id,
            digest(
                {
                    "kind": "plan",
                    "request": request.fingerprint(),
                    "retrieval": inputs.web_retrieval,
                    "versions": versions,
                }
            ),
        )
        reusable: dict[str, str] = {}
        lead_mode = runtime.config.lead
        with context.transaction() as (session, _workflow):
            designs = StudyDesignRepository(session, context.scope)
            try:
                revision = designs.get(request.design_revision_id)
            except DesignRevisionNotFound:
                return _invalid(
                    "design_not_in_scope", "the run's Design Revision is not this Study's"
                )
            if (
                revision.revision != step.project_revision
                or designs.project_id() != step.project_id
            ):
                return _invalid("design_not_in_scope", "the run's design does not match its scope")
            repo = self._repo(session, context)
            existing = self._find(repo, step, "plan", key)
            if existing is not None:
                repo.read(existing.artifact_id)  # verify the bytes, not only the row
                return _produced(existing, reused=True)
            for track in tracks:
                if lead_mode and track.channel is Channel.WEB:
                    # The lead's tasks are the web tracks; a subject's own is never run.
                    continue
                found = self._find(repo, step, "track", track.fingerprint)
                if found is not None:
                    reusable[track.track_id] = found.artifact_id

        web = [t for t in tracks if t.channel is Channel.WEB and t.track_id not in reusable]
        planned: list[PlannedTrack] = []
        blocked: list[BlockedTrack] = []
        violations: list[PlanViolationRecord] = []
        planner: CallRecord | None = None
        lead: LeadPlanned | None = None

        def block(stop: StopReason, gate: Gate, reason: str, message: str) -> None:
            blocked.extend(
                BlockedTrack(
                    track_id=t.track_id,
                    stop_reason=stop,
                    gate=gate,
                    reason=reason,
                    detail=_detail(gate, reason, message),
                )
                for t in web
                if not any(b.track_id == t.track_id for b in blocked)
            )

        if web and runtime.retrieval is None:
            block(
                StopReason.WEB_RETRIEVAL_UNAVAILABLE,
                Gate.WEB_RETRIEVAL,
                "no_retrieval",
                "no search provider, route or terms are approved (DR-2); nothing was searched",
            )
        elif web and runtime.retrieval is not None:
            gate = RetrievalGate(
                retrieval=runtime.retrieval,
                scope=context.scope,
                meter=StepToolMeter(context),
                client_terms=request.client_terms,
                class_a_texts=_class_a_texts(request),
                clock=runtime.clock,
                archive=runtime.archive,
                datasets=runtime.datasets,
                archives=runtime.archives,
            )
            refusal = gate.refusal_for_class(dclass)
            if refusal is not None:
                block(
                    StopReason.SEARCH_ROUTE_REFUSED,
                    Gate.SEARCH_ROUTE,
                    refusal,
                    f"a query written from {dclass.value} material may not leave",
                )
            elif lead_mode:
                lead = LeadPlanning(
                    self,
                    step=step,
                    context=context,
                    runtime=runtime,
                    caller=self._caller(context, runtime),
                    request=request,
                    depth=depth,
                    data_class=dclass,
                    plan_key=key,
                ).plan(web)
                planner = lead.call
                blocked.extend(lead.blocked)
            else:
                answer = self._ask(
                    self._caller(context, runtime),
                    runtime,
                    AgentRole.PLANNER,
                    payload={
                        "brief": request.brief.model_dump(mode="json"),
                        "limits": {
                            "queries_per_track": depth.queries_per_web_track,
                            "sub_questions_per_track": 5,
                        },
                        "tracks": [
                            {
                                "track_id": t.track_id,
                                "kind": t.subject.kind.value,
                                "subject": t.subject.text,
                            }
                            for t in web
                        ],
                    },
                    data_class=dclass,
                    lineage=DataLineage.none(),
                )
                if answer.gate is not None:
                    block(
                        StopReason.CONTEXT_TOO_LARGE
                        if answer.gate is Gate.CONTEXT_WINDOW
                        else StopReason.MODEL_ROUTE_REFUSED,
                        answer.gate,
                        answer.reason,
                        answer.detail,
                    )
                else:
                    assert isinstance(answer.output, PlanProposal)
                    planner = answer.call
                    planned, plan_blocked, violations = _accept_plan(answer.output, web, depth)
                    blocked.extend(plan_blocked)

        # Every subject a track opened, the lead's planned ones (crosses) included.
        subjects = _subjects(request, (*tracks, *beyond))
        if lead is not None:
            # The web tracks the lead planned run as its tasks' tracks (investigate).
            tracks = tuple(t for t in tracks if t.track_id not in lead.planned)
        web_ids = [t.track_id for t in tracks if t.channel is Channel.WEB]
        record = PlanRecord(
            kind="deep_research_plan",
            request=request,
            request_fingerprint=request.fingerprint(),
            depth=depth,
            versions=versions,
            design_class=dclass,
            fictional_client=fictional,
            web_retrieval=dict(inputs.web_retrieval) if inputs.web_retrieval is not None else None,
            subjects=subjects,
            tracks=tracks,
            beyond=beyond,
            reusable=reusable,
            planned=tuple(planned),
            blocked=tuple(blocked),
            violations=tuple(violations),
            allowances={}
            if lead_mode
            else {
                t: AllowanceRecord(search_calls=a.search_calls, fetches=a.fetches)
                for t, a in allocate(
                    web_ids, depth, agent_directed=runtime.config.agent_directed
                ).items()
            },
            planner=planner,
            lead_plan_artifact_id=lead.artifact_id if lead is not None else None,
        )
        with context.transaction() as (session, _workflow):
            artifact, created = self._put(
                self._repo(session, context), step, payload=record, kind="plan", key=key
            )
        context.progress(
            "deep_research_plan",
            tracks=len(tracks),
            reusable=len(reusable),
            planned=len(planned),
            blocked=len(blocked),
            beyond_limit=len(beyond),
            model_requests=0 if planner is None else 1,
            **({"lead_tasks": lead.tasks} if lead is not None else {}),
        )
        return _produced(artifact, reused=not created)


def _accept_plan(
    proposal: PlanProposal, web: Sequence[ResearchTrack], depth: DepthPreset
) -> tuple[list[PlannedTrack], list[BlockedTrack], list[PlanViolationRecord]]:
    """Take what the planner proposed for the tracks it was asked about, and nothing else.

    A track planned twice keeps its first plan; an invented track is ignored; a
    track the planner skipped or gave no query is blocked (``plan_incomplete``),
    each with the violation recorded. Queries are cut to the preset's number, in the
    planner's order, and duplicates dropped.
    """
    first: dict[str, Any] = {}
    duplicates = []
    for tp in proposal.tracks:
        if tp.track_id in first:
            duplicates.append(tp.track_id)
        else:
            first[tp.track_id] = tp
    requested = [t.track_id for t in web]
    found = check_plan_coverage(requested, {k: v.queries for k, v in first.items()})
    violations = [PlanViolationRecord(track_id=v.track_id, problem=v.problem) for v in found]
    violations += [
        PlanViolationRecord(track_id=t, problem="the plan names this track more than once")
        for t in duplicates
    ]
    refused = {v.track_id for v in found if v.track_id in set(requested)}
    planned, blocked = [], []
    for track_id in requested:
        if track_id in refused:
            problem = next(v.problem for v in found if v.track_id == track_id)
            blocked.append(
                BlockedTrack(
                    track_id=track_id,
                    stop_reason=StopReason.PLAN_INCOMPLETE,
                    gate=Gate.PLAN,
                    reason="plan_incomplete",
                    detail=_detail(Gate.PLAN, "plan_incomplete", problem),
                )
            )
            continue
        tp = first[track_id]
        queries = list(dict.fromkeys(" ".join(q.split()) for q in tp.queries if q.strip()))
        planned.append(
            PlannedTrack(
                track_id=track_id,
                sub_questions=tuple(tp.sub_questions),
                queries=tuple(queries[: depth.queries_per_web_track]),
            )
        )
    return planned, blocked, violations
