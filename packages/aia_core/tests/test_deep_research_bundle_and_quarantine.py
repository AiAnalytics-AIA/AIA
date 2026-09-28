"""The sealed bundle, and what leaves it for respondents, the design and analysis."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.deep_research.bundle import TrackRecord, seal_bundle
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    BriefDigest,
    Channel,
    DeepResearchRequest,
    EvidenceItem,
    EvidenceOrigin,
    EvidenceType,
    FrozenKnowledge,
    QualityStatus,
    QuarantineReason,
    RecommendedUse,
    ResearchSubject,
    RetrievalMode,
    ScreenQuestion,
    SourceKind,
    StopReason,
    SubjectKind,
    TrackStatus,
    subject_key,
)
from aia_core.domain.deep_research.merge import AcceptedEvidence, RespondentUse, ScoreRecord
from aia_core.domain.deep_research.quarantine import (
    EXTERNAL_CONTEXT,
    RecordedEvidenceRefused,
    analysis_context,
    design_input,
    require_live_evidence,
    respondent_context,
)
from aia_core.domain.residency import DataClass

QUESTION = ResearchSubject(
    key=subject_key(SubjectKind.QUESTION, "Proč lidé kupují rostlinné nápoje?"),
    kind=SubjectKind.QUESTION,
    text="Proč lidé kupují rostlinné nápoje?",
    origin="research_plan.research_questions[0]",
)
OBJECT = ResearchSubject(
    key=subject_key(SubjectKind.OBJECT, "Aroma"),
    kind=SubjectKind.OBJECT,
    text="Aroma",
    origin="tracked_objects[0]",
)
WEB_Q = "DRT-W-" + QUESTION.key
WEB_O = "DRT-W-" + OBJECT.key


def _request() -> DeepResearchRequest:
    return DeepResearchRequest(
        harness_version=HARNESS_VERSION,
        design_revision_id="REV-1",
        design_revision=1,
        preset="QUICK",
        channels=(Channel.WEB,),
        brief=BriefDigest(title="t", goal="g", decision_use="d", briefing=""),
        subjects=(QUESTION, OBJECT),
        questionnaire=(),
        knowledge=FrozenKnowledge(items=(), omitted_ids=(), retrieval_limit=200),
        client_terms=(),
    )


def _track(track: str, subject: ResearchSubject, **fields: Any) -> TrackRecord:
    values: dict[str, Any] = {
        "track_id": track,
        "subject_key": subject.key,
        "channel": Channel.WEB,
        "fingerprint": "a" * 64,
        "status": TrackStatus.COMPLETED,
        "stop_reason": StopReason.SATURATED,
        "detail": "",
        "reused": False,
        "artifact_id": "ART-1",
        "retrieval_mode": RetrievalMode.RECORDED,
        "queries": (),
        "snapshot_ids": (),
        "evidence_ids": (),
        "quarantined_ids": (),
        "model_requests": 1,
        "search_calls": 1,
        "fetches": 2,
        "credits": 3,
        "model_cost_usd": 0.01,
        "tool_cost_usd": 0.0,
        **fields,
    }
    return TrackRecord.model_validate(values)


def _accepted(n: int, claim: str, *, track: str = WEB_Q, **fields: Any) -> AcceptedEvidence:
    use = fields.pop("respondent_use", RespondentUse.ELIGIBLE)
    exclusion = fields.pop("respondent_exclusion", None)
    confidence = fields.pop("confidence", 0.9)
    values: dict[str, Any] = {
        "evidence_id": f"EV-{n:016x}",
        "track_id": track,
        "subject_key": QUESTION.key if track == WEB_Q else OBJECT.key,
        "channel": Channel.WEB,
        "source_kind": SourceKind.WEB_PAGE,
        "source_ref": "SNP-" + str(n).zfill(24),
        "source_url": f"https://www.czso.cz/{n}",
        "source_title": "t",
        "claim": claim,
        "quote": claim,
        "quote_span": (0, len(claim)),
        "evidence_type": EvidenceType.OFFICIAL_REPORT,
        "source_date": "2025-01-01",
        "geography": "CZ",
        "population": "",
        "topics": ("trh",),
        "data_class": DataClass.CLASS_C_INTERNAL,
        "agent_outcome_overlap": False,
        "agent_recommended_use": RecommendedUse.CONTEXT_ONLY,
        "agent_source_quality": 0.9,
        **fields,
    }
    return AcceptedEvidence(
        evidence=EvidenceItem.model_validate(values),
        score=ScoreRecord(
            source_class="OFFICIAL_STATISTICS",
            base=0.95,
            age="recent",
            age_adjustment=0.0,
            score=0.95,
            geography="CZ",
            table_version="aia-source-table-1",
        ),
        respondent_use=use,
        respondent_exclusion=exclusion,
        merged_ids=(),
        confirmations=(),
        confidence=confidence,
        verifier_reason="ok",
    )


def _bundle(
    *accepted: AcceptedEvidence,
    tracks: tuple[TrackRecord, ...] | None = None,
    fictional: bool = False,
) -> Any:
    return seal_bundle(
        request=_request(),
        subjects=(QUESTION, OBJECT),
        versions={"harness": HARNESS_VERSION},
        tracks=tracks or (_track(WEB_Q, QUESTION), _track(WEB_O, OBJECT)),
        accepted=accepted,
        quarantined=(),
        snapshots=(),
        synthesis=None,
        fictional_client=fictional,
        counts={"model_requests": 2},
        spend_usd={"model": 0.02, "tools": 0.0},
    )


# --------------------------------------------------------------------------- the bundle


def test_a_sealed_bundle_verifies_and_a_changed_one_does_not() -> None:
    bundle = _bundle(_accepted(1, "Regulace obalů se mění od roku 2026."))
    assert bundle.verify() and len(bundle.sha256) == 64
    assert bundle.client_facing is False
    tampered = bundle.model_copy(update={"fictional_client": True})
    assert not tampered.verify()


def test_quality_status_and_origins_follow_the_tracks() -> None:
    grounded = _bundle(_accepted(1, "Regulace obalů se mění od roku 2026."))
    assert grounded.quality_status is QualityStatus.GROUNDED
    assert grounded.origins == (EvidenceOrigin.RECORDED_FIXTURE,)
    assert _bundle().quality_status is QualityStatus.NO_EVIDENCE
    blocked = (
        _track(WEB_Q, QUESTION),
        _track(
            WEB_O,
            OBJECT,
            status=TrackStatus.BLOCKED,
            stop_reason=StopReason.SEARCH_ROUTE_REFUSED,
            detail="no search route approved for CLASS_A_CLIENT_CONFIDENTIAL",
            artifact_id=None,
        ),
    )
    partial = _bundle(_accepted(1, "Regulace obalů se mění od roku 2026."), tracks=blocked)
    assert partial.quality_status is QualityStatus.PARTIAL
    cells = {c.track_id: c for c in partial.coverage}
    assert cells[WEB_Q].accepted == 1 and cells[WEB_O].status is TrackStatus.BLOCKED
    (cell,) = partial.grid
    assert not cell.covered  # the object's track was blocked


# --------------------------------------------------------------------------- respondents


FINAL = (
    ScreenQuestion(id="q9", text="Kolik lidí kupuje ovesné nápoje týdně?", kategorie=("Týdně",)),
)


def test_recorded_evidence_never_reaches_respondents_unless_a_test_says_so() -> None:
    bundle = _bundle(_accepted(1, "Regulace obalů se mění od roku 2026."))
    with pytest.raises(RecordedEvidenceRefused):
        respondent_context(bundle, FINAL)
    assert respondent_context(bundle, FINAL, allow_recorded=True).blocks


def test_leakage_introduced_by_the_final_questionnaire_is_caught_at_compile() -> None:
    # Accepted at pass 1, when no survey question asked about weekly purchases.
    leaky = _accepted(1, "Ovesné nápoje kupuje týdně 38 % lidí, ukazuje průzkum.")
    safe = _accepted(2, "Regulace obalů se mění od roku 2026.")
    context = respondent_context(_bundle(leaky, safe), FINAL, allow_recorded=True)
    assert [b.evidence_id for b in context.blocks] == [safe.evidence.evidence_id]
    (excluded,) = context.excluded
    assert excluded.evidence_id == leaky.evidence.evidence_id
    assert excluded.reason is QuarantineReason.QUESTIONNAIRE_LEAKAGE
    # Before that question existed, the same finding was eligible.
    earlier = respondent_context(_bundle(leaky, safe), (), allow_recorded=True)
    assert len(earlier.blocks) == 2


def test_alignment_evidence_never_becomes_a_hint_whatever_the_questionnaire() -> None:
    target = _accepted(
        3,
        "Značku Aroma zná 61 % dotázaných.",
        respondent_use=RespondentUse.EXCLUDED,
        respondent_exclusion=QuarantineReason.TARGET_OUTCOME_OVERLAP,
    )
    context = respondent_context(_bundle(target), (), allow_recorded=True)
    assert context.blocks == ()
    assert context.excluded[0].reason is QuarantineReason.TARGET_OUTCOME_OVERLAP


def test_blocks_keep_the_units_shape_and_order_by_confidence() -> None:
    items = [
        _accepted(10 + i, f"Tvrzení o regulaci číslo {i} platí.", confidence=0.6 + i / 100)
        for i in range(10)
    ]
    context = respondent_context(_bundle(*items), (), allow_recorded=True)
    assert len(context.blocks) == 8 and len(context.beyond_limit) == 2
    first = context.blocks[0]
    assert first.id.startswith("research_01_") and len(first.id) == len("research_01_") + 8
    assert first.role == EXTERNAL_CONTEXT and first.jistota == pytest.approx(0.69)
    assert first.zdroj.startswith("https://www.czso.cz/") and first.datum == "2025-01-01"


# --------------------------------------------------------------------------- design, analysis


def test_the_design_sees_every_finding_by_subject_and_the_gaps() -> None:
    target = _accepted(
        4,
        "Značku Aroma zná 61 % dotázaných.",
        track=WEB_O,
        respondent_use=RespondentUse.EXCLUDED,
        respondent_exclusion=QuarantineReason.TARGET_OUTCOME_OVERLAP,
    )
    view = design_input(_bundle(target))
    assert view.role == EXTERNAL_CONTEXT
    assert view.gaps == (QUESTION.key,)
    (finding,) = view.findings[OBJECT.key]
    assert finding.respondent_use is RespondentUse.EXCLUDED and finding.quote == finding.claim


def test_analysis_gets_context_that_is_never_a_panel_claim() -> None:
    context = analysis_context(_bundle(_accepted(5, "Regulace obalů se mění od roku 2026.")))
    assert all(
        i.admissible_as_panel_claim is False and i.role == EXTERNAL_CONTEXT for i in context.items
    )


def test_client_facing_use_refuses_fixtures_and_fiction() -> None:
    with pytest.raises(RecordedEvidenceRefused, match="recorded"):
        require_live_evidence(_bundle(_accepted(6, "Regulace obalů se mění od roku 2026.")))
    live = (
        _track(WEB_Q, QUESTION, retrieval_mode=RetrievalMode.LIVE),
        _track(WEB_O, OBJECT, retrieval_mode=RetrievalMode.LIVE),
    )
    require_live_evidence(_bundle(tracks=live))
    with pytest.raises(RecordedEvidenceRefused, match="fictional"):
        require_live_evidence(_bundle(tracks=live, fictional=True))
