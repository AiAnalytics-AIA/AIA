"""The agent-directed brief: code's parts, the prose's numbers, gaps and acquisition gaps.

Plan ``deep-research-web-search.md`` § 8.8 and § 7 (rung 11), chunk 13. Fictional
publishers and hosts (``*-dr.example``), recorded synthesizer answers, nothing sent.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.ai_contracts import schema_supports_strict
from aia_core.domain.deep_research.agents import (
    AGENT_IDS,
    AgentRole,
    TurnGap,
    TurnLead,
    agent_definition,
    prompt_for,
)
from aia_core.domain.deep_research.brief import (
    BRIEF_VERSION,
    BriefMaterial,
    BriefRepair,
    brief_material,
    brief_payload,
    check_brief,
    research_brief,
    synthesis_check,
    uncited_numbers,
)
from aia_core.domain.deep_research.bundle import SynthesisRecord
from aia_core.domain.deep_research.confidence import (
    CONFIDENCE_WEIGHTS_V1,
    ConflictState,
    Provenance,
)
from aia_core.domain.deep_research.contracts import (
    Channel,
    EvidenceItem,
    EvidenceType,
    Measure,
    MeasureBasis,
    QuarantinedEvidence,
    QuarantineReason,
    RecommendedUse,
    ResearchSubject,
    SourceKind,
    StopReason,
    SubjectKind,
    TrackStatus,
    evidence_id,
    subject_key,
)
from aia_core.domain.deep_research.gaps import (
    WITHHELD,
    AcquisitionReason,
    AcquisitionRung,
    GapKind,
    LeadSource,
    OpenAttempt,
    TrackFacts,
    acquisition_gaps,
    acquisition_reason,
    conflict_gaps,
    how_to_obtain,
    only_years,
    research_gaps,
    strip_ids,
    track_facts,
)
from aia_core.domain.deep_research.merge import (
    AcceptedEvidence,
    RespondentUse,
    ScoreRecord,
)
from aia_core.domain.deep_research.reputation import Publisher, RegisterStatus, ReputationRegister
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1, SourceClass, SourceTier
from aia_core.domain.deep_research.steps import SynthesisArtifact
from aia_core.domain.deep_research.synthesis import SynthesisStatus
from aia_core.domain.deep_research.synthesizer import (
    BRIEF_CONTRACT_VERSION,
    BRIEF_PROMPT_VERSION,
    BriefProposal,
)
from aia_core.domain.deep_research.tracing import PrimaryLead, PrimaryStatus, TraceRecord
from aia_core.domain.deep_research.triangulation import (
    ConflictStatus,
    MeasuredFinding,
    detect_conflicts,
)
from aia_core.domain.deep_research.verification import VerificationReview, VerifierLead
from aia_core.domain.residency import DataClass

READ = date(2026, 9, 27)
STAT = "https://stat-dr.example/tabulka-2025"
SVAZ = "https://svaz-dr.example/spotreba"
TABLE = SOURCE_TABLE_V1.extended(
    "test-brief-table",
    {
        "stat-dr.example": SourceClass.OFFICIAL_STATISTICS,
        "svaz-dr.example": SourceClass.INDUSTRY_RESEARCH,
    },
)
REGISTER = ReputationRegister(
    version="test-register-brief",
    status=RegisterStatus.PROPOSED,
    publishers=(
        Publisher(
            "Statistický úřad DR",
            ("SÚDR",),
            ("stat-dr.example",),
            SourceClass.OFFICIAL_STATISTICS,
            SourceTier.T1,
            ("datastat",),
        ),
    ),
)

Q1_TEXT = "Jak roste trh rostlinných nápojů v Česku?"
Q2_TEXT = "Proč lidé přecházejí na rostlinné nápoje?"
Q1 = ResearchSubject(
    key=subject_key(SubjectKind.QUESTION, Q1_TEXT),
    kind=SubjectKind.QUESTION,
    text=Q1_TEXT,
    origin="research_plan.research_questions[0]",
)
Q2 = ResearchSubject(
    key=subject_key(SubjectKind.QUESTION, Q2_TEXT),
    kind=SubjectKind.QUESTION,
    text=Q2_TEXT,
    origin="research_plan.research_questions[1]",
)
AGE = ResearchSubject(
    key=subject_key(SubjectKind.QUESTION, "Kdo pije rostlinné nápoje ve věku 18-29 let?"),
    kind=SubjectKind.QUESTION,
    text="Kdo pije rostlinné nápoje ve věku 18-29 let?",
    origin="research_plan.research_questions[2]",
)
SUBJECTS = (Q1, Q2, AGE)
NAME = "spotřeba rostlinných nápojů"

TABLE_QUOTE = (
    "Spotřeba rostlinných nápojů v Česku vzrostla v roce 2025 o 12,5 % na 41 milionů litrů."
)
SVAZ_QUOTE = "Spotřeba rostlinných nápojů v Česku činila v roce 2025 podle svazu 38 milionů litrů."


def measure(value: float, **fields: Any) -> Measure:
    defaults: dict[str, Any] = {
        "unit": "l",
        "scale": 1_000_000,
        "period": "Y2025",
        "geography": "CZ",
        "measure_name": NAME,
    }
    return Measure(value=value, **{**defaults, **fields})


def evidence(
    url: str | None,
    quote: str,
    *,
    subject: ResearchSubject = Q1,
    measures: Sequence[Measure] = (),
    ref: str = "SNP-1",
    quality: float = 0.5,
    claim: str | None = None,
) -> EvidenceItem:
    claim = claim or quote
    return EvidenceItem.model_validate(
        {
            "evidence_id": evidence_id("f" * 64, ref, quote, claim),
            "track_id": f"DRT-W-{subject.key}",
            "subject_key": subject.key,
            "channel": Channel.WEB,
            "source_kind": SourceKind.WEB_PAGE,
            "source_ref": ref,
            "source_url": url,
            "source_title": "Tabulka",
            "claim": claim,
            "quote": quote,
            "quote_span": (0, len(quote)),
            "evidence_type": EvidenceType.OFFICIAL_REPORT,
            "source_date": None,
            "geography": "CZ",
            "population": "",
            "topics": (),
            "data_class": DataClass.CLASS_C_INTERNAL,
            "agent_outcome_overlap": False,
            "agent_recommended_use": RecommendedUse.CONTEXT_ONLY,
            "agent_source_quality": quality,
            "measures": tuple(measures),
        }
    )


def accept(item: EvidenceItem, cls: str = "OFFICIAL_STATISTICS") -> AcceptedEvidence:
    return AcceptedEvidence(
        evidence=item,
        score=ScoreRecord(
            source_class=cls,
            base=0.95,
            age="recent",
            age_adjustment=0.0,
            score=0.95,
            geography="",
            table_version=TABLE.version,
        ),
        respondent_use=RespondentUse.ELIGIBLE,
        respondent_exclusion=None,
        merged_ids=(),
        confirmations=(),
        confidence=0.95,
        verifier_reason="posouzeno podle citace a měr",
    )


TABLE_ITEM = evidence(
    STAT,
    TABLE_QUOTE,
    measures=[measure(12.5, unit="%", scale=1, measure_name=None), measure(41)],
    ref="SNP-stat",
)
SVAZ_ITEM = evidence(SVAZ, SVAZ_QUOTE, measures=[measure(38)], ref="SNP-svaz")


def trace(item: EvidenceItem, status: PrimaryStatus, publisher: str) -> TraceRecord:
    return TraceRecord(
        evidence_id=item.evidence_id,
        publisher=f"x:{publisher}",
        publisher_name=publisher,
        status=status,
        cited=(),
        traced_to=None,
        lead_id=None,
        detail="",
    )


def review(
    items: Sequence[EvidenceItem] = (TABLE_ITEM, SVAZ_ITEM),
    *,
    primary_leads: Sequence[PrimaryLead] = (),
    verifier_leads: Sequence[VerifierLead] = (),
) -> VerificationReview:
    traces = [
        trace(i, PrimaryStatus.PRIMARY, "Statistický úřad DR")
        if i.source_url == STAT
        else trace(i, PrimaryStatus.UNDETERMINED, "svaz-dr.example")
        for i in items
    ]
    findings = [
        MeasuredFinding(
            evidence_id=i.evidence_id,
            publisher=t.publisher,
            publisher_name=t.publisher_name,
            primary=t.status is PrimaryStatus.PRIMARY,
            source_url=i.source_url,
            measure=m,
        )
        for i, t in zip(items, traces, strict=True)
        for m in i.measures
    ]
    return VerificationReview(
        kind="deep_research_verification_review",
        rules_version="test",
        register_version=REGISTER.version,
        independence=(),
        traces=tuple(traces),
        primary_leads=tuple(primary_leads),
        verifier_leads=tuple(verifier_leads),
        supersessions=(),
        conflicts=detect_conflicts(findings),
        resolve_requests=(),
    )


def facts(subject: ResearchSubject, **fields: Any) -> TrackFacts:
    defaults: dict[str, Any] = {
        "track_id": f"DRT-W-{subject.key}",
        "subject_key": subject.key,
        "status": TrackStatus.COMPLETED,
        "stop_reason": StopReason.AGENT_FINISHED,
        "detail": "",
        "sub_questions": (),
    }
    return TrackFacts(**{**defaults, **fields})


def material(
    accepted: Sequence[AcceptedEvidence] = (accept(TABLE_ITEM), accept(SVAZ_ITEM, "INDUSTRY")),
    *,
    tracks: Sequence[TrackFacts] = (),
    the_review: VerificationReview | None = None,
    quarantined: Sequence[QuarantinedEvidence] = (),
) -> BriefMaterial:
    return brief_material(
        accepted,
        quarantined=quarantined,
        review=the_review if the_review is not None else review(),
        subjects=SUBJECTS,
        tracks=tracks or (facts(Q1), facts(Q2)),
        read={a.evidence.evidence_id: READ for a in accepted},
        table=TABLE,
        register=REGISTER,
        weights=CONFIDENCE_WEIGHTS_V1,
    )


def proposal(**fields: Any) -> BriefProposal:
    defaults: dict[str, Any] = {
        "summary": "Spotřeba v roce 2025 vzrostla na 41 milionů litrů.",
        "answers": [
            {
                "subject_key": Q1.key,
                "text": "Úřad uvádí růst o 12,5 % na 41 milionů litrů za rok 2025; svaz 38.",
                "evidence_ids": [TABLE_ITEM.evidence_id, SVAZ_ITEM.evidence_id],
            }
        ],
        "conflict_notes": [],
        "limitations": ["Údaje jsou z veřejných zdrojů, ne z panelu."],
    }
    return BriefProposal.model_validate({**defaults, **fields})


def subjects() -> dict[str, ResearchSubject]:
    return {s.key: s for s in SUBJECTS}


# --------------------------------------------------------------------------- #
# The contract and the agent
# --------------------------------------------------------------------------- #


def test_the_brief_synthesizer_is_an_agent_of_its_own_with_a_strict_contract() -> None:
    agent = agent_definition(AgentRole.BRIEF_SYNTHESIZER, max_output_tokens=4000)
    assert agent.agent_id == AGENT_IDS[AgentRole.BRIEF_SYNTHESIZER]
    assert agent.agent_id == "aia.deep_research.brief_synthesizer"
    assert agent.prompt_version == BRIEF_PROMPT_VERSION and agent.allowed_tools == frozenset()
    assert agent.output_contract is BriefProposal and agent.schema is not None
    assert schema_supports_strict(agent.schema)
    assert BRIEF_CONTRACT_VERSION in BRIEF_VERSION
    # The planned mode's synthesizer is unchanged.
    assert agent_definition(AgentRole.SYNTHESIZER, max_output_tokens=4000).output_contract is not (
        BriefProposal
    )


def _properties(node: Any) -> set[str]:
    if isinstance(node, dict):
        found = (
            set(node.get("properties", {})) if isinstance(node.get("properties"), dict) else set()
        )
        return found | {p for v in node.values() for p in _properties(v)}
    if isinstance(node, list):
        return {p for v in node for p in _properties(v)}
    return set()


def test_the_model_cannot_rate_its_own_brief() -> None:
    fields = _properties(BriefProposal.model_json_schema())
    assert fields >= {"summary", "answers", "conflict_notes", "limitations", "evidence_ids"}
    for word in ("confidence", "quality", "score", "certainty"):
        assert not [f for f in fields if word in f]
    prompt = prompt_for(AgentRole.BRIEF_SYNTHESIZER)
    assert "Jistotu nikdy nevyjadřuj číslem" in prompt
    assert "neprůměruj" in prompt


def test_a_self_rating_in_the_answer_is_refused_by_the_contract() -> None:
    raw = proposal().model_dump(mode="json")
    raw["answers"][0]["confidence"] = 0.99
    with pytest.raises(ValidationError, match="confidence"):
        BriefProposal.model_validate(raw)


# --------------------------------------------------------------------------- #
# Code's parts: findings with confidence, conflicts, gaps
# --------------------------------------------------------------------------- #


def test_every_finding_carries_its_measures_source_tier_provenance_and_confidence() -> None:
    m = material()
    table, svaz = m.findings
    assert table.evidence_id == TABLE_ITEM.evidence_id
    assert table.tier is SourceTier.T1 and table.provenance is Provenance.PRIMARY
    assert table.publisher == "Statistický úřad DR"
    assert table.measures_text == ("12,5 % Y2025 CZ", "41 mil. l Y2025 CZ")
    assert svaz.tier is SourceTier.T3 and svaz.provenance is Provenance.UNDETERMINED
    # The two disagree on one measure, and both stand in that open conflict.
    assert table.confidence.inputs.conflict is ConflictState.OPEN
    assert table.confidence.value > svaz.confidence.value
    assert table.confidence.weights_version == CONFIDENCE_WEIGHTS_V1.version


def test_the_agent_s_self_rating_changes_no_confidence_in_the_brief() -> None:
    def rated(q: float) -> list[Any]:
        items = [
            TABLE_ITEM.model_copy(update={"agent_source_quality": q}),
            SVAZ_ITEM.model_copy(update={"agent_source_quality": q}),
        ]
        built = material([accept(items[0]), accept(items[1], "INDUSTRY")], the_review=review(items))
        return [f.confidence for f in built.findings]

    assert rated(0.0) == rated(1.0) == rated(0.5)


def test_a_conflict_shows_both_sides_and_its_cause_and_an_open_one_is_a_gap() -> None:
    m = material()
    [conflict] = m.conflicts
    assert {s.evidence_id for s in conflict.sides} == {
        TABLE_ITEM.evidence_id,
        SVAZ_ITEM.evidence_id,
    }
    assert {s.measure.value for s in conflict.sides} == {41.0, 38.0}
    assert conflict.status is ConflictStatus.OPEN and conflict.cause.value == "unexplained"
    [gap] = [g for g in m.gaps if g.kind is GapKind.CONFLICT]
    assert gap.conflict_id == conflict.conflict_id and "resolve track" in gap.reason


def test_an_explained_conflict_is_shown_and_is_no_gap() -> None:
    svaz = evidence(SVAZ, SVAZ_QUOTE, measures=[measure(38, basis=MeasureBasis.ACTUAL)])
    table = TABLE_ITEM.model_copy(
        update={"measures": (measure(41, basis=MeasureBasis.PRELIMINARY),)}
    )
    m = material([accept(table), accept(svaz, "INDUSTRY")], the_review=review([table, svaz]))
    [conflict] = m.conflicts
    assert conflict.status is ConflictStatus.EXPLAINED and conflict.cause.value == "basis"
    assert not [g for g in m.gaps if g.kind is GapKind.CONFLICT]
    assert conflict_gaps(m.conflicts) == ()


def test_a_subject_without_an_accepted_finding_is_an_unanswered_gap_with_its_stops() -> None:
    m = material(
        tracks=(
            facts(Q1),
            facts(
                Q2,
                stop_reason=StopReason.STOP_REFUSALS,
                sub_questions=("Jaké jsou důvody?",),
            ),
        )
    )
    unanswered = {g.subject_key: g for g in m.gaps if g.kind is GapKind.UNANSWERED}
    assert set(unanswered) == {Q2.key, AGE.key}
    assert unanswered[Q2.key].need == f"{Q2_TEXT}; Jaké jsou důvody?"
    assert "repeated_refusals" in unanswered[Q2.key].reason
    assert unanswered[AGE.key].reason.endswith("no track researched it")
    # The subject's own range is a name; a number in an unanswered subject withholds it.
    assert not unanswered[AGE.key].text_withheld


def test_a_finished_track_s_stated_gaps_are_kept_with_why_and_what_was_tried() -> None:
    stated = TurnGap(need="údaj za rok 2024", why="tabulka uvádí jen rok 2025", tried="tabulka")
    sneaky = TurnGap(need="podíl domácností", why="zdroj uvádí jen 45 %", tried="nic")
    m = material(tracks=(facts(Q1, finish_gaps=(stated, sneaky)), facts(Q2)))
    gaps = [g for g in m.gaps if g.kind is GapKind.STATED]
    assert (gaps[0].need, gaps[0].reason, gaps[0].tried) == (
        "údaj za rok 2024",
        "tabulka uvádí jen rok 2025",
        "tabulka",
    )
    # A number the gap cannot cite is withheld from the brief; the transcript keeps it.
    assert gaps[1].text_withheld and gaps[1].reason == WITHHELD
    assert gaps[1].need == "podíl domácností"


def test_a_planned_or_internal_track_s_gap_lines_are_stated_gaps() -> None:
    built = track_facts(
        track_id="DRT-I-x",
        subject_key=Q2.key,
        status=TrackStatus.COMPLETED,
        stop_reason=StopReason.SINGLE_PASS,
        detail="",
        sub_questions=(),
        gap_lines=("Chybí údaje o motivaci.",),
        transcript=None,
    )
    [gap] = research_gaps([Q2], [built], answered=frozenset({Q2.key}))
    assert gap.kind is GapKind.STATED and gap.need == "Chybí údaje o motivaci."


# --------------------------------------------------------------------------- #
# Acquisition gaps (typed for the ladder, chunk 10)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        ("http_402", AcquisitionReason.PAYWALL),
        ("http_401", AcquisitionReason.LOGIN),
        ("http_403", AcquisitionReason.NOT_PUBLIC),
        ("http_404", AcquisitionReason.NOT_FOUND),
        ("http_410", AcquisitionReason.NOT_FOUND),
        ("robots_disallowed", AcquisitionReason.ROBOTS),
        ("robots_unavailable", AcquisitionReason.ROBOTS),
    ],
)
def test_a_refused_open_says_why_the_source_was_unreachable(
    code: str, reason: AcquisitionReason
) -> None:
    attempt = OpenAttempt(
        turn=2, index=1, ref="R2", url=SVAZ, title="Zpráva o trhu 2025", reason=code
    )
    [gap] = acquisition_gaps([facts(Q1, opens=(attempt,))], LeadSource(), register=REGISTER)
    assert gap.reason is reason and gap.title == "Zpráva o trhu 2025"
    assert gap.publisher == "svaz-dr.example" and gap.url == SVAZ
    assert gap.raised_by == "refused_open" and gap.ladder_version is None
    [tried] = gap.rungs_tried
    assert tried.rung is AcquisitionRung.INVESTIGATOR_OPEN and tried.outcome == code
    assert gap.how_to_obtain == how_to_obtain(reason)
    assert only_years(gap.how_to_obtain)


@pytest.mark.parametrize(
    "code", ["class_not_approved", "address_not_public", "content_type", "http_500", "lost"]
)
def test_aia_s_own_boundaries_and_the_network_are_not_acquisition_gaps(code: str) -> None:
    assert acquisition_reason(code) is None


def test_a_lead_nobody_pursued_is_an_acquisition_gap_unless_the_track_reached_it() -> None:
    lead = TurnLead(need="Tabulka spotřeby za rok 2025", publisher="SÚDR", why="zpráva jen opakuje")
    vague = TurnLead(need="Studie trhu", publisher="statistický úřad", why="chybí")
    reached = facts(Q1, leads=((3, lead),), captured_hosts=frozenset({"stat-dr.example"}))
    missed = facts(Q2, leads=((1, lead), (2, vague)))
    gaps = acquisition_gaps([reached, missed], LeadSource(), register=REGISTER)
    assert [(g.track_id, g.title) for g in gaps] == [
        (missed.track_id, "Tabulka spotřeby za rok 2025"),
        (missed.track_id, "Studie trhu"),
    ]
    resolved, unresolved = gaps
    assert resolved.publisher == "Statistický úřad DR"  # by the register
    assert unresolved.publisher == "statistický úřad"  # as named; the register does not know it
    assert all(g.reason is AcquisitionReason.NOT_PURSUED and g.rungs_tried == () for g in gaps)
    assert all(g.raised_by == "investigator_lead" for g in gaps)


def test_the_verify_step_s_leads_are_acquisition_gaps_naming_their_subject() -> None:
    primary = PrimaryLead(
        lead_id="PL-1",
        evidence_id=SVAZ_ITEM.evidence_id,
        publisher="Statistický úřad DR",
        hosts=("stat-dr.example",),
        data_interfaces=("datastat",),
        link="https://stat-dr.example/t",
        need="Primární zdroj údaje u vydavatele Statistický úřad DR.",
    )
    verifier = VerifierLead(
        lead_id="VL-1",
        evidence_id=TABLE_ITEM.evidence_id,
        query="spotřeba rostlinných nápojů 2026",
        publisher_named="SÚDR",
        publisher="Statistický úřad DR",
        why="novější údaj",
    )
    m = material(the_review=review(primary_leads=[primary], verifier_leads=[verifier]))
    by = {g.raised_by: g for g in m.acquisition_gaps}
    assert by["primary_lead"].url == "https://stat-dr.example/t"
    assert by["primary_lead"].subject_key == Q1.key
    assert by["verifier_lead"].title == "spotřeba rostlinných nápojů 2026"
    assert by["verifier_lead"].publisher == "Statistický úřad DR"


def test_a_lead_for_a_quarantined_finding_still_names_its_subject() -> None:
    lost = evidence(SVAZ, SVAZ_QUOTE, subject=Q2, ref="SNP-q")
    primary = PrimaryLead(
        lead_id="PL-2",
        evidence_id=lost.evidence_id,
        publisher="Statistický úřad DR",
        hosts=("stat-dr.example",),
        data_interfaces=(),
        link=None,
        need="Primární zdroj.",
    )
    q = QuarantinedEvidence(
        evidence_id=lost.evidence_id,
        track_id=lost.track_id,
        reason=QuarantineReason.UNVERIFIED,
        detail="",
        claim=lost.claim,
        source_ref=lost.source_ref,
        evidence=lost,
    )
    m = material(the_review=review(primary_leads=[primary]), quarantined=[q])
    [gap] = m.acquisition_gaps
    assert gap.subject_key == Q2.key


def test_a_number_in_an_acquisition_gap_s_title_is_withheld() -> None:
    attempt = OpenAttempt(
        turn=1, index=0, ref="R1", url=SVAZ, title="Trh vzrostl o 7 %", reason="http_402"
    )
    [gap] = acquisition_gaps([facts(Q1, opens=(attempt,))], LeadSource(), register=None)
    assert gap.text_withheld and gap.title == WITHHELD


def test_record_ids_are_citations_not_numbers() -> None:
    text = "Viz EV-1234567890123456, DRT-W-q-123456789012 a KNW-0123456789ab@2 za rok 2025."
    assert only_years(text)
    assert "1234567890123456" not in strip_ids(text) and "2025" in strip_ids(text)


# --------------------------------------------------------------------------- #
# The prose: every number cites an evidence id
# --------------------------------------------------------------------------- #


def test_a_faithful_brief_is_complete_and_every_number_cites_an_evidence_id() -> None:
    m = material()
    check = check_brief(proposal(), material=m, subjects=subjects())
    assert check.problems == ()
    brief = research_brief(m, check, repair=None)
    assert brief.status is SynthesisStatus.COMPLETE
    assert brief.summary is not None and brief.answers[0].evidence_ids == (
        TABLE_ITEM.evidence_id,
        SVAZ_ITEM.evidence_id,
    )
    assert uncited_numbers(brief, SUBJECTS) == ()
    assert brief.version == BRIEF_VERSION and brief.weights == CONFIDENCE_WEIGHTS_V1


@pytest.mark.parametrize(
    ("text", "ids"),
    [
        # A number in no quote or measure the answer cites.
        ("Do roku 2030 trh vzroste o 99 %.", [TABLE_ITEM.evidence_id]),
        # The svaz's 38 without citing the svaz's finding.
        ("Úřad uvádí 41 milionů litrů, svaz 38.", [TABLE_ITEM.evidence_id]),
        # A confidence written as a number.
        ("Úřad uvádí 41 milionů litrů (jistota 0,87).", [TABLE_ITEM.evidence_id]),
    ],
)
def test_an_uncited_number_in_an_answer_is_refused(text: str, ids: list[str]) -> None:
    answer = {"subject_key": Q1.key, "text": text, "evidence_ids": ids}
    check = check_brief(
        proposal(answers=[answer], summary="Bez čísel."), material=material(), subjects=subjects()
    )
    [refused] = check.excluded
    assert refused.where == "answers[0]" and refused.reason == "number_not_in_cited_evidence"
    assert check.answers == ()
    brief = research_brief(material(), check, repair=None)
    assert brief.status is SynthesisStatus.BLOCKED
    assert uncited_numbers(brief, SUBJECTS) == ()


def test_measures_periods_rounding_and_the_subject_s_own_range_back_a_number() -> None:
    age = evidence(
        STAT,
        "Rostlinné nápoje pije 31,4 % lidí ve věku 18-29 let.",
        subject=AGE,
        measures=[measure(31.4, unit="%", scale=1, period="Y2025", measure_name=None)],
        ref="SNP-age",
    )
    m = material(
        [accept(TABLE_ITEM), accept(SVAZ_ITEM, "INDUSTRY"), accept(age)],
        the_review=review([TABLE_ITEM, SVAZ_ITEM, age]),
    )
    answers = [
        # 41 000 000 is the measure times its scale; 2025 is the measure's period.
        {
            "subject_key": Q1.key,
            "text": "V roce 2025 to bylo 41 000 000 litrů.",
            "evidence_ids": [TABLE_ITEM.evidence_id],
        },
        # 31 rounds 31,4 as the prose shows it; 18-29 is the subject's own range.
        {
            "subject_key": AGE.key,
            "text": "Ve věku 18–29 let pije rostlinné nápoje zhruba 31 % lidí.",  # noqa: RUF001
            "evidence_ids": [age.evidence_id],
        },
    ]
    check = check_brief(
        proposal(answers=answers, summary="Spotřeba 41 milionů litrů."),
        material=m,
        subjects=subjects(),
    )
    assert check.problems == ()


def test_unknown_subjects_and_unaccepted_citations_are_refused_with_their_reasons() -> None:
    answers = [
        {
            "subject_key": "q-000000000000",
            "text": "Text.",
            "evidence_ids": [TABLE_ITEM.evidence_id],
        },
        {"subject_key": Q1.key, "text": "Text.", "evidence_ids": ["EV-0000000000000000"]},
    ]
    check = check_brief(proposal(answers=answers), material=material(), subjects=subjects())
    assert [e.reason for e in check.excluded] == ["unknown_subject", "citation_not_accepted"]
    # The summary's 41 is no published answer's: it is withheld, and said why.
    assert check.summary is None and check.summary_withheld is not None


def test_a_conflict_note_may_state_only_its_two_sides_numbers() -> None:
    m = material()
    [conflict] = m.conflicts
    good = {"conflict_id": conflict.conflict_id, "text": "Úřad uvádí 41, svaz 38 milionů litrů."}
    averaged = {"conflict_id": conflict.conflict_id, "text": "V průměru tedy 39,5 milionu litrů."}
    unknown = {"conflict_id": "CNF-0000", "text": "Nic."}
    check = check_brief(
        proposal(conflict_notes=[averaged, good, unknown]), material=m, subjects=subjects()
    )
    assert check.notes == {conflict.conflict_id: good["text"]}
    assert [e.reason for e in check.excluded] == [
        "number_not_in_cited_evidence",
        "unknown_conflict",
    ]
    brief = research_brief(m, check, repair=None)
    [shown] = brief.conflicts
    assert shown.note == good["text"] and shown.note_refused is None
    assert uncited_numbers(brief, SUBJECTS) == ()


def test_a_limitation_cites_nothing_and_so_states_no_number() -> None:
    check = check_brief(
        proposal(limitations=["Jen 2 zdroje.", "Jen veřejné zdroje."]),
        material=material(),
        subjects=subjects(),
    )
    assert check.limitations == ("Jen veřejné zdroje.",)
    assert [e.reason for e in check.excluded] == ["number_without_citation"]


def test_uncited_numbers_finds_a_number_smuggled_past_the_check() -> None:
    m = material()
    brief = research_brief(m, check_brief(proposal(), material=m, subjects=subjects()), repair=None)
    smuggled = brief.model_copy(update={"limitations": ("Trh vzroste o 99 %.",)})
    assert uncited_numbers(smuggled, SUBJECTS) == (("limitations[0]", 99.0),)


def test_the_brief_without_prose_is_blocked_or_empty_and_keeps_code_s_parts() -> None:
    m = material()
    blocked = research_brief(m, None, repair=None, withheld="the brief was not requested: x")
    assert blocked.status is SynthesisStatus.BLOCKED and blocked.findings == m.findings
    assert blocked.summary_withheld == "the brief was not requested: x"
    empty = research_brief(material([], the_review=review([])), None, repair=None)
    assert empty.status is SynthesisStatus.EMPTY


def test_a_repair_is_recorded_beside_the_brief() -> None:
    m = material()
    first = check_brief(proposal(summary="Trh vzroste o 99 %."), material=m, subjects=subjects())
    assert [p.reason for p in first.problems] == ["summary_withheld"]
    second = check_brief(proposal(), material=m, subjects=subjects())
    brief = research_brief(m, second, repair=BriefRepair(problems=first.problems, refused=None))
    assert brief.status is SynthesisStatus.COMPLETE
    assert brief.repair is not None and brief.repair.problems[0].reason == "summary_withheld"


def test_the_payload_shows_confidence_as_a_band_and_no_agent_rating() -> None:
    m = material()
    payload = brief_payload(m, SUBJECTS)
    text = str(payload)
    assert "source_quality" not in text and "agent_recommended" not in text
    findings: Any = payload["findings"]
    assert {f["confidence"] for f in findings} <= {"low", "medium", "high"}
    assert findings[0]["measures"] == ["12,5 % Y2025 CZ", "41 mil. l Y2025 CZ"]


def test_the_brief_reads_as_a_synthesis_check_for_every_other_reader() -> None:
    m = material()
    answers = [
        {
            "subject_key": Q1.key,
            "text": "Trh roste o 99 %.",
            "evidence_ids": [TABLE_ITEM.evidence_id],
        },
        {
            "subject_key": Q1.key,
            "text": "Úřad uvádí 41 milionů litrů.",
            "evidence_ids": [TABLE_ITEM.evidence_id],
        },
    ]
    brief = research_brief(
        m,
        check_brief(proposal(answers=answers), material=m, subjects=subjects()),
        repair=None,
    )
    check = synthesis_check(brief)
    assert check.status is SynthesisStatus.PARTIAL
    assert [f.text for f in check.findings] == ["Úřad uvádí 41 milionů litrů."]
    assert [(e.index, e.reason) for e in check.excluded] == [(0, "number_not_in_cited_evidence")]
    assert len(check.gaps) == len(brief.gaps)


def test_a_planned_synthesis_and_bundle_record_store_exactly_as_before() -> None:
    brief = research_brief(material(), None, repair=None)
    check = synthesis_check(brief)
    artifact = SynthesisArtifact(
        kind="deep_research_synthesis", check=check, call=None, refused=None
    )
    assert set(artifact.model_dump(mode="json")) == {"kind", "check", "call", "refused"}
    assert set(SynthesisRecord(artifact_id=None, check=check).model_dump(mode="json")) == {
        "artifact_id",
        "check",
    }
    stored = artifact.model_copy(update={"brief": brief}).model_dump(mode="json")
    assert stored["brief"]["kind"] == "deep_research_brief" and "repair_call" not in stored
    assert SynthesisArtifact.model_validate(stored).brief == brief
