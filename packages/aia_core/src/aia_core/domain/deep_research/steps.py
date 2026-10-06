"""What each step of a Deep Research run stores, and how a run's spend is counted.

The six steps of ``deep_research`` (:mod:`.workflow`) each record one artifact as
their output, and some record more: one per track, per source snapshot, per
verification batch. These are their shapes -- closed and frozen, like everything a
later reader must not be able to reinterpret -- published for whoever reads a run
beyond its bundle (a review screen, the integrator's API).

Two kinds of artifact, told apart by their fingerprint (plan decision I-4):

* **Reusable across runs**, keyed by what their content depends on: a COMPLETED
  track (its track fingerprint), a source snapshot (its content address), a
  verification batch and a synthesis (what their model was shown). A later pass
  finds them and buys nothing again.
* **This run's own**, keyed by :func:`run_scoped`: the plan, the investigation, the
  merge and verify records, and every track that did not complete. A crashed step
  that runs again finds them; no other run can. A track a gate refused is never
  reusable: the gate may open, and the next pass must look again.

A lead-planned run (chunk 11) adds two of this run's own: the lead's plan
(:class:`LeadPlanRecord`) -- the memory a long run and a retried step keep -- and one
:class:`ReplanRecord` per re-plan asked after a wave. A task's track is keyed like any
track, by a fingerprint that includes its brief and budget.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer

from ..residency import DataClass
from .agents import AgentRole
from .brief import ResearchBrief
from .bundle import SnapshotRef
from .contracts import (
    DeepResearchRequest,
    EvidenceItem,
    QuarantinedEvidence,
    QueryDecision,
    QueryRecord,
    ResearchSubject,
    ResearchTrack,
    RetrievalMode,
    SourceKind,
    SourceSnapshot,
    StopReason,
    TrackStatus,
    digest,
)
from .lead import Allotment, LeadLimits, Replan, ResearchPlan
from .merge import AcceptedEvidence, Candidate, SourceFacts
from .planning import DepthPreset
from .synthesis import SynthesisCheck
from .verification import VerificationReview
from .verifier import ClaimJudgement

__all__ = [
    "AllowanceRecord",
    "BatchEntry",
    "BlockedTrack",
    "CallRecord",
    "Gate",
    "InvestigationRecord",
    "LeadPlanRecord",
    "LeadRunRecord",
    "MergeRecord",
    "PlanRecord",
    "PlanViolationRecord",
    "PlannedTrack",
    "ReplanRecord",
    "SnapshotArtifact",
    "SourceFactsRecord",
    "SynthesisArtifact",
    "TrackEntry",
    "TrackResult",
    "UrlCaptureRecord",
    "VerificationBatch",
    "VerifyRecord",
    "run_scoped",
    "tally",
]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def run_scoped(run_id: str, fingerprint: str) -> str:
    """The key of an artifact only its own run may find again (a resumed step)."""
    return digest(["run", run_id, fingerprint])


class Gate(StrEnum):
    """What refused a track, a batch or a synthesis before anything was sent."""

    #: No retrieval exists in this composition (no provider is approved, DR-2).
    WEB_RETRIEVAL = "web_retrieval"
    #: The search or fetch route may not carry the class, or its spend is unmetered.
    SEARCH_ROUTE = "search_route"
    #: The gateway's preflight: route and class, licence, capability.
    MODEL_ROUTE = "model_route"
    #: The request would not fit the model's context window; nothing is trimmed.
    CONTEXT_WINDOW = "context_window"
    #: The planner skipped the track, or gave it no query.
    PLAN = "plan"
    #: The preset's track limit.
    TRACK_LIMIT = "track_limit"


class CallRecord(_Closed):
    """One logical model request as it ran: its identity and cost, never its text."""

    role: AgentRole
    agent_id: str
    prompt_version: str
    call_id: str
    provider_request_id: str | None
    model: str
    route_id: str
    policy_version: str
    data_class: DataClass
    cost_usd: float = Field(ge=0.0)


class AllowanceRecord(_Closed):
    search_calls: int = Field(ge=0)
    fetches: int = Field(ge=0)


class PlannedTrack(_Closed):
    """What the planner proposed for one web track, as code accepted it."""

    track_id: str
    sub_questions: tuple[str, ...]
    queries: tuple[str, ...]


class BlockedTrack(_Closed):
    """A track refused at planning time: the gate, its reason, in words."""

    track_id: str
    stop_reason: StopReason
    gate: Gate
    reason: str
    detail: str = Field(max_length=2000)


class PlanViolationRecord(_Closed):
    track_id: str
    problem: str


class PlanRecord(_Closed):
    """The ``plan`` step: what the run researches, how far, and on what."""

    kind: Literal["deep_research_plan"]
    request: DeepResearchRequest
    request_fingerprint: str
    depth: DepthPreset
    versions: dict[str, str]
    #: The class of the design every agent is shown (Class C only for a fictional client).
    design_class: DataClass
    fictional_client: bool
    #: The retrieval a web track runs on (``WebRetrieval.identity``), or None.
    web_retrieval: dict[str, Any] | None
    #: The request's subjects and the crosses the preset opened.
    subjects: tuple[ResearchSubject, ...]
    tracks: tuple[ResearchTrack, ...]
    #: Tracks beyond the preset's limit: recorded as skipped, never dropped.
    beyond: tuple[ResearchTrack, ...]
    #: Track id -> the stored COMPLETED result found for its fingerprint at planning.
    reusable: dict[str, str]
    planned: tuple[PlannedTrack, ...]
    blocked: tuple[BlockedTrack, ...]
    violations: tuple[PlanViolationRecord, ...]
    allowances: dict[str, AllowanceRecord]
    #: The planner's request, or in a lead-planned run the lead's plan request.
    planner: CallRecord | None
    #: A lead-planned run's :class:`LeadPlanRecord`. None otherwise, and then left out
    #: of the stored form, so a plan stored before the lead existed reads and hashes
    #: exactly as it did.
    lead_plan_artifact_id: str | None = None

    @model_serializer(mode="wrap")
    def _omit_no_lead(self, handler: SerializerFunctionWrapHandler) -> Any:
        data = handler(self)
        if self.lead_plan_artifact_id is None and isinstance(data, dict):
            data.pop("lead_plan_artifact_id", None)
        return data

    def planned_for(self, track_id: str) -> PlannedTrack | None:
        return next((p for p in self.planned if p.track_id == track_id), None)

    def blocked_for(self, track_id: str) -> BlockedTrack | None:
        return next((b for b in self.blocked if b.track_id == track_id), None)


class SnapshotArtifact(_Closed):
    """One captured source, stored once per content address."""

    kind: Literal["deep_research_source_snapshot"]
    snapshot: SourceSnapshot
    #: The page's own publication date, when it states one; scoring reads it.
    published: date | None


class UrlCaptureRecord(_Closed):
    """A URL this run captured, and the content address of what it returned (chunk 21).

    Stored run-scoped by the URL's canonical form, so a track step of the same run asking
    for the URL is answered from the snapshot and sends nothing (the run's snapshot
    cache, held in the store when tracks run in steps of their own).
    """

    kind: Literal["deep_research_url_capture"]
    url: str
    snapshot_id: str


class SourceFactsRecord(_Closed):
    """What source scoring needs about one source a track holds."""

    ref: str
    kind: SourceKind
    url: str | None
    published: date | None
    retrieved: date | None

    def facts(self) -> SourceFacts:
        return SourceFacts(
            ref=self.ref,
            kind=self.kind,
            url=self.url,
            published=self.published,
            retrieved=self.retrieved,
        )


class TrackResult(_Closed):
    """One track as it ran: every query, source, finding, refusal and cost.

    ``run_id`` is the run that researched it; a later pass that reuses it says so.
    """

    kind: Literal["deep_research_track"]
    run_id: str
    track: ResearchTrack
    status: TrackStatus
    stop_reason: StopReason
    detail: str = Field(max_length=2000)
    retrieval_mode: RetrievalMode | None
    sub_questions: tuple[str, ...]
    queries: tuple[QueryRecord, ...]
    snapshots: tuple[SnapshotRef, ...]
    knowledge_refs: tuple[str, ...]
    sources: tuple[SourceFactsRecord, ...]
    evidence: tuple[EvidenceItem, ...]
    quarantined: tuple[QuarantinedEvidence, ...]
    gaps: tuple[str, ...]
    calls: tuple[CallRecord, ...]
    search_calls: int = Field(ge=0)
    fetches: int = Field(ge=0)
    credits: int = Field(ge=0)
    model_cost_usd: float = Field(ge=0.0)
    tool_cost_usd: float = Field(ge=0.0)
    #: An agent-directed track's transcript artifact (``deep_research_transcript``):
    #: every turn, action and decision. None for a planned-mode track, and then left
    #: out of the stored form, so a track stored before it existed reads, dumps and
    #: hashes exactly as it did.
    transcript_artifact_id: str | None = None

    @model_serializer(mode="wrap")
    def _omit_no_transcript(self, handler: SerializerFunctionWrapHandler) -> Any:
        data = handler(self)
        if self.transcript_artifact_id is None and isinstance(data, dict):
            data.pop("transcript_artifact_id", None)
        return data


class TrackEntry(_Closed):
    track_id: str
    artifact_id: str
    #: Researched by an earlier run and taken as stored (a later pass, an unchanged track).
    reused: bool


class LeadPlanRecord(_Closed):
    """The lead's plan for one run, or why there is none. This run's own.

    Stored the moment the answer is known, keyed by the run and the request's hash,
    so a plan step that runs again finds it and asks nothing. ``plan`` is None when
    the lead's answer was refused after the gateway's one repair (``refused`` names
    every reason, ``call_ids`` the calls it cost); the run's web tracks are then
    blocked (``plan_incomplete``, ``lead_plan_refused``), never planned some other way.
    """

    kind: Literal["deep_research_lead_plan"]
    run_id: str
    version: str
    request_sha256: str
    limits: LeadLimits
    plan: ResearchPlan | None
    refused: tuple[str, ...]
    call: CallRecord | None
    call_ids: tuple[str, ...]


class ReplanRecord(_Closed):
    """One re-plan after a wave, as asked and as decided. This run's own.

    Keyed by the run, the lead's plan, the wave and the request's hash: a retried
    step that rebuilds the same request finds it and applies it again without a call.
    ``pending_before`` and ``pending_after`` are the budgets of the tasks still to run
    either side of its moves -- equal, by construction and by check -- and
    ``committed_after`` what the run is committed to after it, within ``ceiling``.
    """

    kind: Literal["deep_research_lead_replan"]
    run_id: str
    wave: int = Field(ge=1)
    request_sha256: str
    replan: Replan | None
    #: Why it was not applied: the gate that refused the request, or every reason the
    #: lead's answer was refused for after the gateway's one repair.
    refused: tuple[str, ...]
    call: CallRecord | None
    call_ids: tuple[str, ...]
    pending_before: Allotment
    pending_after: Allotment
    committed_after: Allotment
    ceiling: Allotment


class LeadRunRecord(_Closed):
    """How a lead-planned run's waves ran: their tracks, its re-plans, the lead's calls."""

    lead_plan_artifact_id: str
    #: Each wave's track ids, in the order the waves ran.
    waves: tuple[tuple[str, ...], ...]
    replan_artifact_ids: tuple[str, ...]
    #: The re-plans' calls (the plan's is ``PlanRecord.planner``).
    calls: tuple[CallRecord, ...]


class InvestigationRecord(_Closed):
    """The ``investigate`` step: every planned track, and where its result is."""

    kind: Literal["deep_research_investigation"]
    plan_artifact_id: str
    tracks: tuple[TrackEntry, ...]
    #: A lead-planned run's waves and re-plans; None otherwise, and then left out of
    #: the stored form (a record stored before the lead existed is unchanged).
    lead: LeadRunRecord | None = None

    @model_serializer(mode="wrap")
    def _omit_no_lead(self, handler: SerializerFunctionWrapHandler) -> Any:
        data = handler(self)
        if self.lead is None and isinstance(data, dict):
            data.pop("lead", None)
        return data


class MergeRecord(_Closed):
    """The ``merge`` step: candidates for the verifier, and what was quarantined."""

    kind: Literal["deep_research_merge"]
    investigation_artifact_id: str
    source_table_version: str
    merge_rules_version: str
    candidates: tuple[Candidate, ...]
    #: Every finding a track or the merge quarantined, with its one reason.
    quarantined: tuple[QuarantinedEvidence, ...]


class VerificationBatch(_Closed):
    """One verifier request over one batch: reusable when the batch is unchanged."""

    kind: Literal["deep_research_verification"]
    evidence_ids: tuple[str, ...]
    #: evidence id -> [verdict, reason], for the ids of this batch only.
    verdicts: dict[str, tuple[str, str]]
    call: CallRecord
    #: The independent verifier's whole judgements (agent-directed mode, chunk 12). Empty
    #: for the planned mode's verifier, and then left out of the stored form, so a batch
    #: stored before it existed reads, dumps and hashes exactly as it did.
    judgements: tuple[ClaimJudgement, ...] = ()

    @model_serializer(mode="wrap")
    def _omit_no_judgements(self, handler: SerializerFunctionWrapHandler) -> Any:
        data = handler(self)
        if not self.judgements and isinstance(data, dict):
            data.pop("judgements", None)
        return data


class BatchEntry(_Closed):
    fingerprint: str
    evidence_ids: tuple[str, ...]
    artifact_id: str | None
    reused: bool
    #: Why the batch was not sent, as ``gate:reason``; its candidates stay unverified.
    refused: str | None


class VerifyRecord(_Closed):
    """The ``verify`` step: accepted evidence, and every quarantined finding."""

    kind: Literal["deep_research_verify"]
    merge_artifact_id: str
    batches: tuple[BatchEntry, ...]
    accepted: tuple[AcceptedEvidence, ...]
    quarantined: tuple[QuarantinedEvidence, ...]
    #: An agent-directed run's review (chunk 12): independence, primary tracing, leads,
    #: supersessions, conflicts and resolve-track requests. None in the planned mode,
    #: and then left out of the stored form, which is unchanged.
    review: VerificationReview | None = None

    @model_serializer(mode="wrap")
    def _omit_no_review(self, handler: SerializerFunctionWrapHandler) -> Any:
        data = handler(self)
        if self.review is None and isinstance(data, dict):
            data.pop("review", None)
        return data


class SynthesisArtifact(_Closed):
    """The ``synthesize`` step: the checked brief, and the request that wrote it."""

    kind: Literal["deep_research_synthesis"]
    check: SynthesisCheck
    call: CallRecord | None
    #: Why no request was sent (``gate:reason``), when none was.
    refused: str | None
    #: The agent-directed brief (chunk 13): findings with confidence by code, conflicts,
    #: gaps, acquisition gaps; ``check`` is its planned-mode shape. None in the planned
    #: mode, and then left out of the stored form, which is unchanged.
    brief: ResearchBrief | None = None
    #: The one repair request a failed agent-directed draft got, when it got one. Left
    #: out of the stored form when None.
    repair_call: CallRecord | None = None

    @model_serializer(mode="wrap")
    def _omit_no_brief(self, handler: SerializerFunctionWrapHandler) -> Any:
        data = handler(self)
        if isinstance(data, dict):
            if self.brief is None:
                data.pop("brief", None)
            if self.repair_call is None:
                data.pop("repair_call", None)
        return data


def _cost(calls: Iterable[CallRecord]) -> float:
    return sum(c.cost_usd for c in calls)


def tally(
    *,
    plan: PlanRecord,
    results: Sequence[tuple[TrackResult, bool]],
    batches: Sequence[BatchEntry],
    batch_calls: Mapping[str, CallRecord],
    synthesis: SynthesisArtifact,
    synthesis_reused: bool,
    accepted: int,
    quarantined: int,
    lead_calls: Sequence[CallRecord] = (),
) -> tuple[dict[str, int], dict[str, float]]:
    """What this run did and spent, counted from its records. A reused unit costs nothing.

    ``results`` pairs each track's result with whether it was reused; ``batch_calls``
    maps a batch fingerprint to the call this run made for it; ``lead_calls`` are a
    lead-planned run's re-plan requests.
    """
    fresh = [r for r, reused in results if not reused]
    calls = [c for r in fresh for c in r.calls]
    if plan.planner is not None:
        calls.append(plan.planner)
    calls += lead_calls
    calls += [batch_calls[b.fingerprint] for b in batches if b.fingerprint in batch_calls]
    if synthesis.call is not None and not synthesis_reused:
        calls.append(synthesis.call)
        if synthesis.repair_call is not None:
            calls.append(synthesis.repair_call)
    snapshots = {s.snapshot_id for r, _ in results for s in r.snapshots}
    counts = {
        "tracks": len(results) + len(plan.beyond),
        "tracks_researched": len(fresh),
        "tracks_reused": len(results) - len(fresh),
        "tracks_blocked": sum(1 for r, _ in results if r.status is TrackStatus.BLOCKED)
        + len(plan.beyond),
        "tracks_incomplete": sum(1 for r, _ in results if r.status is TrackStatus.INCOMPLETE),
        "tracks_beyond_limit": len(plan.beyond),
        "model_requests": len(calls),
        "search_calls": sum(r.search_calls for r in fresh),
        "fetches": sum(r.fetches for r in fresh),
        "queries_refused": sum(
            1 for r in fresh for q in r.queries if q.decision is QueryDecision.REFUSED
        ),
        "snapshots": len(snapshots),
        "verification_batches": len(batches),
        "verification_batches_reused": sum(1 for b in batches if b.reused),
        "accepted": accepted,
        "quarantined": quarantined,
    }
    spend = {
        "model_usd": round(_cost(calls), 6),
        "tool_usd": round(sum(r.tool_cost_usd for r in fresh), 6),
    }
    return counts, spend
