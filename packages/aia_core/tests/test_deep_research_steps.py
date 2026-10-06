"""What each step stores, and how a run's spend is counted: a reused unit costs nothing."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.deep_research.agents import AgentRole
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    BriefDigest,
    Channel,
    DeepResearchRequest,
    FrozenKnowledge,
    QueryDecision,
    QueryRecord,
    ResearchSubject,
    ResearchTrack,
    SourceKind,
    StopReason,
    SubjectKind,
    TrackStatus,
    subject_key,
    track_id,
)
from aia_core.domain.deep_research.planning import PRESETS
from aia_core.domain.deep_research.steps import (
    BatchEntry,
    BlockedTrack,
    CallRecord,
    Gate,
    PlannedTrack,
    PlanRecord,
    SourceFactsRecord,
    SynthesisArtifact,
    TrackResult,
    run_scoped,
    tally,
)
from aia_core.domain.deep_research.synthesis import SynthesisCheck, SynthesisStatus
from aia_core.domain.residency import DataClass

SUBJECT = ResearchSubject(
    key=subject_key(SubjectKind.QUESTION, "Jak roste trh?"),
    kind=SubjectKind.QUESTION,
    text="Jak roste trh?",
    origin="research_plan.research_questions[0]",
)
TRACKS = {
    c: ResearchTrack(
        track_id=track_id(SUBJECT.key, c), subject=SUBJECT, channel=c, fingerprint=f * 64
    )
    for c, f in ((Channel.INTERNAL, "a"), (Channel.WEB, "b"))
}


def _call(role: AgentRole, cost: float) -> CallRecord:
    return CallRecord(
        role=role,
        agent_id=f"aia.deep_research.{role.value}",
        prompt_version="1",
        call_id=f"call-{role.value}",
        provider_request_id=None,
        model="m",
        route_id="r",
        policy_version="p",
        data_class=DataClass.CLASS_C_INTERNAL,
        cost_usd=cost,
    )


def _plan(**overrides: Any) -> PlanRecord:
    request = DeepResearchRequest(
        harness_version=HARNESS_VERSION,
        design_revision_id="DREV-1",
        design_revision=1,
        preset="QUICK",
        channels=(Channel.INTERNAL, Channel.WEB),
        brief=BriefDigest(title="t", goal="g", decision_use="", briefing=""),
        subjects=(SUBJECT,),
        questionnaire=(),
        knowledge=FrozenKnowledge(items=(), omitted_ids=(), retrieval_limit=200),
        client_terms=(),
    )
    fields: dict[str, Any] = {
        "kind": "deep_research_plan",
        "request": request,
        "request_fingerprint": request.fingerprint(),
        "depth": PRESETS["QUICK"],
        "versions": {"harness": HARNESS_VERSION},
        "design_class": DataClass.CLASS_C_INTERNAL,
        "fictional_client": True,
        "web_retrieval": None,
        "subjects": (SUBJECT,),
        "tracks": tuple(TRACKS.values()),
        "beyond": (),
        "reusable": {},
        "planned": (
            PlannedTrack(track_id=TRACKS[Channel.WEB].track_id, sub_questions=(), queries=("q",)),
        ),
        "blocked": (),
        "violations": (),
        "allowances": {},
        "planner": _call(AgentRole.PLANNER, 0.01),
        **overrides,
    }
    return PlanRecord(**fields)


def _result(channel: Channel, *, calls: tuple[CallRecord, ...], searches: int = 0) -> TrackResult:
    return TrackResult(
        kind="deep_research_track",
        run_id="RUN-1",
        track=TRACKS[channel],
        status=TrackStatus.COMPLETED,
        stop_reason=StopReason.SINGLE_PASS,
        detail="",
        retrieval_mode=None,
        sub_questions=(),
        queries=(
            QueryRecord(
                text="q",
                data_class=DataClass.CLASS_C_INTERNAL,
                class_reasons=(),
                decision=QueryDecision.REFUSED,
                refusal="class_a_query",
                call_id=None,
                hits=0,
            ),
        )
        if channel is Channel.WEB
        else (),
        snapshots=(),
        knowledge_refs=(),
        sources=(),
        evidence=(),
        quarantined=(),
        gaps=(),
        calls=calls,
        search_calls=searches,
        fetches=0,
        credits=0,
        model_cost_usd=sum(c.cost_usd for c in calls),
        tool_cost_usd=0.0,
    )


def _synthesis(call: CallRecord | None) -> SynthesisArtifact:
    return SynthesisArtifact(
        kind="deep_research_synthesis",
        check=SynthesisCheck(
            status=SynthesisStatus.EMPTY,
            summary=None,
            summary_withheld=None,
            findings=(),
            excluded=(),
            gaps=(),
            limitations=(),
        ),
        call=call,
        refused=None,
    )


def test_a_run_scoped_key_is_found_by_its_own_run_only() -> None:
    assert run_scoped("RUN-1", "f") == run_scoped("RUN-1", "f")
    assert run_scoped("RUN-1", "f") != run_scoped("RUN-2", "f") != "f"


def test_a_run_counts_what_it_bought_and_nothing_it_reused() -> None:
    internal = _result(Channel.INTERNAL, calls=(_call(AgentRole.INTERNAL_INVESTIGATOR, 0.02),))
    web = _result(Channel.WEB, calls=(_call(AgentRole.WEB_INVESTIGATOR, 0.03),), searches=2)
    batches = (
        BatchEntry(
            fingerprint="b1", evidence_ids=("EV-1",), artifact_id="A1", reused=True, refused=None
        ),
        BatchEntry(
            fingerprint="b2", evidence_ids=("EV-2",), artifact_id="A2", reused=False, refused=None
        ),
        BatchEntry(
            fingerprint="b3",
            evidence_ids=("EV-3",),
            artifact_id=None,
            reused=False,
            refused="model_route:x",
        ),
    )
    counts, spend = tally(
        plan=_plan(),
        results=[(internal, True), (web, False)],
        batches=batches,
        batch_calls={"b2": _call(AgentRole.VERIFIER, 0.04)},
        synthesis=_synthesis(_call(AgentRole.SYNTHESIZER, 0.05)),
        synthesis_reused=False,
        accepted=1,
        quarantined=2,
    )
    # planner + the web investigator + one verifier batch + the synthesizer; the reused
    # internal track and the reused batch cost this run nothing.
    assert counts["model_requests"] == 4
    assert spend == {"model_usd": pytest.approx(0.13), "tool_usd": 0.0}
    assert counts["tracks_reused"] == 1 and counts["tracks_researched"] == 1
    assert counts["search_calls"] == 2 and counts["queries_refused"] == 1
    assert counts["verification_batches"] == 3 and counts["verification_batches_reused"] == 1

    counts, spend = tally(
        plan=_plan(planner=None),
        results=[(internal, True), (web, True)],
        batches=batches[:1],
        batch_calls={},
        synthesis=_synthesis(_call(AgentRole.SYNTHESIZER, 0.05)),
        synthesis_reused=True,
        accepted=1,
        quarantined=0,
    )
    assert counts["model_requests"] == 0 and spend["model_usd"] == 0.0


def test_beyond_the_limit_counts_as_blocked_and_blocked_tracks_are_named() -> None:
    beyond = TRACKS[Channel.WEB].model_copy(update={"track_id": "DRT-W-q-000000000000"})
    plan = _plan(
        beyond=(beyond,),
        blocked=(
            BlockedTrack(
                track_id=TRACKS[Channel.WEB].track_id,
                stop_reason=StopReason.WEB_RETRIEVAL_UNAVAILABLE,
                gate=Gate.WEB_RETRIEVAL,
                reason="no_retrieval",
                detail="web_retrieval: no_retrieval",
            ),
        ),
    )
    counts, _ = tally(
        plan=plan,
        results=[],
        batches=(),
        batch_calls={},
        synthesis=_synthesis(None),
        synthesis_reused=False,
        accepted=0,
        quarantined=0,
    )
    assert counts["tracks"] == 1 and counts["tracks_beyond_limit"] == 1
    assert counts["tracks_blocked"] == 1
    web = TRACKS[Channel.WEB].track_id
    assert plan.blocked_for(web) is not None and plan.planned_for(web) is not None
    assert plan.blocked_for("DRT-W-q-ffffffffffff") is None


def test_the_step_records_are_closed_and_source_facts_round_trip() -> None:
    facts = SourceFactsRecord(
        ref="SNP-" + "0" * 24,
        kind=SourceKind.WEB_PAGE,
        url="https://stat.example/a",
        published=date(2025, 6, 30),
        retrieved=date(2026, 9, 1),
    ).facts()
    assert (facts.url, facts.published, facts.retrieved) == (
        "https://stat.example/a",
        date(2025, 6, 30),
        date(2026, 9, 1),
    )
    with pytest.raises(ValidationError):
        PlanRecord.model_validate({**_plan().model_dump(mode="json"), "unexpected": 1})
    assert PlanRecord.model_validate(_plan().model_dump(mode="json")) == _plan()


def test_a_track_without_a_transcript_stores_exactly_as_before() -> None:
    planned = _result(Channel.WEB, calls=())
    assert "transcript_artifact_id" not in planned.model_dump(mode="json")
    directed = planned.model_copy(update={"transcript_artifact_id": "ART-1"})
    dumped = directed.model_dump(mode="json")
    assert dumped["transcript_artifact_id"] == "ART-1"
    assert TrackResult.model_validate(dumped) == directed
    assert TrackResult.model_validate(planned.model_dump(mode="json")) == planned
