"""The brief: only accepted evidence may be cited, and only its quotes' numbers written."""

from __future__ import annotations

from typing import Any

from aia_core.domain.deep_research.agents import Finding, SynthesisProposal
from aia_core.domain.deep_research.contracts import (
    Channel,
    EvidenceItem,
    EvidenceType,
    RecommendedUse,
    ResearchSubject,
    SourceKind,
    SubjectKind,
    subject_key,
)
from aia_core.domain.deep_research.merge import AcceptedEvidence, RespondentUse, ScoreRecord
from aia_core.domain.deep_research.synthesis import SynthesisStatus, validate_synthesis
from aia_core.domain.residency import DataClass

QUESTION = ResearchSubject(
    key=subject_key(SubjectKind.QUESTION, "Kdo kupuje ve věku 18\u201329 let?"),
    kind=SubjectKind.QUESTION,
    text="Kdo kupuje ve věku 18\u201329 let?",
    origin="research_plan.research_questions[0]",
)
SUBJECTS = {QUESTION.key: QUESTION}


def _accepted(eid: str, quote: str) -> AcceptedEvidence:
    values: dict[str, Any] = {
        "evidence_id": eid,
        "track_id": "DRT-W-" + QUESTION.key,
        "subject_key": QUESTION.key,
        "channel": Channel.WEB,
        "source_kind": SourceKind.WEB_PAGE,
        "source_ref": "SNP-" + "0" * 24,
        "source_url": "https://www.czso.cz/a",
        "source_title": "t",
        "claim": quote,
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
        "agent_source_quality": 0.9,
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
        respondent_use=RespondentUse.ELIGIBLE,
        respondent_exclusion=None,
        merged_ids=(),
        confirmations=(),
        confidence=0.95,
        verifier_reason="ok",
    )


ACCEPTED = {
    "EV-0000000000000001": _accepted(
        "EV-0000000000000001", "Podíl kupujících vzrostl na 23 % v roce 2025."
    ),
    "EV-0000000000000002": _accepted("EV-0000000000000002", "Nejčastěji kupují lidé ve městech."),
}


def _proposal(*findings: Finding, summary: str = "Trh roste.") -> SynthesisProposal:
    return SynthesisProposal(summary=summary, findings=list(findings), gaps=[], limitations=[])


def test_a_cited_finding_with_its_quotes_numbers_is_published() -> None:
    check = validate_synthesis(
        _proposal(
            Finding(
                subject_key=QUESTION.key,
                text="Ve věku 18\u201329 let podíl kupujících vzrostl na 23 % (2025).",
                evidence_ids=["EV-0000000000000001", "EV-0000000000000001"],
            ),
            summary="Podíl kupujících dosáhl 23 %.",
        ),
        accepted=ACCEPTED,
        subjects=SUBJECTS,
    )
    assert check.status is SynthesisStatus.COMPLETE
    assert check.findings[0].evidence_ids == ("EV-0000000000000001",)
    assert check.summary == "Podíl kupujících dosáhl 23 %."


def test_unsupported_findings_are_excluded_with_their_reason() -> None:
    check = validate_synthesis(
        _proposal(
            Finding(
                subject_key="q-ffffffffffff", text="Něco.", evidence_ids=["EV-0000000000000002"]
            ),
            Finding(
                subject_key=QUESTION.key, text="Zdroj říká.", evidence_ids=["EV-quarantined01"]
            ),
            Finding(
                subject_key=QUESTION.key,
                text="Podíl je 40 %.",
                evidence_ids=["EV-0000000000000001"],
            ),
            Finding(
                subject_key=QUESTION.key,
                text="Lidé ve městech kupují nejčastěji.",
                evidence_ids=["EV-0000000000000002"],
            ),
        ),
        accepted=ACCEPTED,
        subjects=SUBJECTS,
    )
    assert check.status is SynthesisStatus.PARTIAL
    assert [(e.index, e.reason) for e in check.excluded] == [
        (0, "unknown_subject"),
        (1, "citation_not_accepted"),
        (2, "number_not_in_cited_evidence"),
    ]
    assert [f.text for f in check.findings] == ["Lidé ve městech kupují nejčastěji."]


def test_a_summary_with_an_unbacked_number_is_withheld() -> None:
    check = validate_synthesis(
        _proposal(
            Finding(
                subject_key=QUESTION.key,
                text="Lidé ve městech kupují nejčastěji.",
                evidence_ids=["EV-0000000000000002"],
            ),
            summary="Trh roste o 12 % ročně.",
        ),
        accepted=ACCEPTED,
        subjects=SUBJECTS,
    )
    assert check.summary is None and check.summary_withheld and "12" in check.summary_withheld
    assert check.status is SynthesisStatus.PARTIAL


def test_accepted_evidence_with_no_surviving_finding_blocks_the_brief() -> None:
    check = validate_synthesis(
        _proposal(
            Finding(subject_key=QUESTION.key, text="99 %.", evidence_ids=["EV-0000000000000002"])
        ),
        accepted=ACCEPTED,
        subjects=SUBJECTS,
    )
    assert check.status is SynthesisStatus.BLOCKED and check.findings == ()
