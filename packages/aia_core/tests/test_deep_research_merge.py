"""Merge and verification: declared scores decide, leakage excludes from respondents only."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from aia_core.domain.deep_research.agents import Verdict
from aia_core.domain.deep_research.contracts import (
    Channel,
    EvidenceItem,
    EvidenceType,
    QuarantineReason,
    RecommendedUse,
    ScreenQuestion,
    SourceKind,
    evidence_id,
)
from aia_core.domain.deep_research.merge import (
    RespondentUse,
    SourceFacts,
    TrackEvidence,
    apply_verdicts,
    excerpt_window,
    merge_evidence,
    verification_batches,
)
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1
from aia_core.domain.residency import DataClass

RETRIEVED = date(2026, 9, 27)


def _item(track: str, url: str | None, claim: str, **fields: Any) -> EvidenceItem:
    ref = fields.pop("ref", "SNP-" + str(abs(hash(url)) % 10**24).zfill(24))
    values: dict[str, Any] = {
        "evidence_id": evidence_id("f" * 64, ref, claim, claim),
        "track_id": track,
        "subject_key": "q-000000000001",
        "channel": Channel.WEB if url else Channel.INTERNAL,
        "source_kind": SourceKind.WEB_PAGE if url else SourceKind.CLIENT_KNOWLEDGE,
        "source_ref": ref,
        "source_url": url,
        "source_title": "t",
        "claim": claim,
        "quote": claim,
        "quote_span": (0, len(claim)),
        "evidence_type": EvidenceType.OTHER,
        "source_date": None,
        "geography": "",
        "population": "",
        "topics": (),
        "data_class": DataClass.CLASS_C_INTERNAL,
        "agent_outcome_overlap": False,
        "agent_recommended_use": RecommendedUse.CONTEXT_ONLY,
        "agent_source_quality": 1.0,
        **fields,
    }
    return EvidenceItem.model_validate(values)


def _track(track: str, *items: EvidenceItem) -> TrackEvidence:
    return TrackEvidence(
        track_id=track,
        evidence=items,
        sources={
            i.source_ref: SourceFacts(
                ref=i.source_ref,
                kind=i.source_kind,
                url=i.source_url,
                published=date(2025, 6, 1),
                retrieved=RETRIEVED,
            )
            for i in items
        },
    )


QUESTIONNAIRE = (
    ScreenQuestion(
        id="q1", text="Jak často kupujete rostlinné nápoje?", kategorie=("Týdně", "Nikdy")
    ),
)


def test_an_unknown_host_is_quarantined_whatever_the_agent_thought_of_it() -> None:
    blog = _item("T1", "https://someones-blog.example/post", "Trh roste.", agent_source_quality=1.0)
    result = merge_evidence([_track("T1", blog)], questionnaire=(), table=SOURCE_TABLE_V1)
    assert result.candidates == ()
    (q,) = result.quarantined
    assert q.reason is QuarantineReason.LOW_SOURCE_QUALITY and "UNKNOWN" in q.detail


def test_approved_knowledge_and_official_sources_become_candidates() -> None:
    official = _item("T1", "https://www.czso.cz/a", "Spotřeba mléka klesá o dvě procenta.")
    internal = _item("T2", None, "Klient prodává v Brně.", ref="KNW-00000000000001@1")
    result = merge_evidence(
        [_track("T1", official), _track("T2", internal)], questionnaire=(), table=SOURCE_TABLE_V1
    )
    assert {c.score.source_class for c in result.candidates} == {
        "OFFICIAL_STATISTICS",
        "CLIENT_KNOWLEDGE",
    }


def test_the_leakage_rule_excludes_from_respondents_without_discarding_the_finding() -> None:
    labelled = _item(
        "T1",
        "https://www.czso.cz/b",
        "Třetina lidí má ráda čaj.",
        agent_outcome_overlap=True,
        agent_recommended_use=RecommendedUse.EXCLUDE_TARGET_LEAKAGE,
    )
    screened = _item(
        "T1", "https://www.czso.cz/c", "38 % respondentů kupuje rostlinné nápoje týdně."
    )
    clean = _item("T1", "https://www.czso.cz/d", "Regulace obalů se mění od roku 2026.")
    result = merge_evidence(
        [_track("T1", labelled, screened, clean)],
        questionnaire=QUESTIONNAIRE,
        table=SOURCE_TABLE_V1,
    )
    uses = {c.evidence.claim: (c.respondent_use, c.respondent_exclusion) for c in result.candidates}
    assert uses[labelled.claim] == (RespondentUse.EXCLUDED, QuarantineReason.TARGET_OUTCOME_OVERLAP)
    assert uses[screened.claim] == (
        RespondentUse.EXCLUDED,
        QuarantineReason.DETERMINISTIC_TARGET_OVERLAP,
    )
    assert uses[clean.claim] == (RespondentUse.ELIGIBLE, None)
    assert result.quarantined == ()


def test_the_same_source_saying_the_same_thing_is_one_candidate() -> None:
    a = _item("T1", "https://www.czso.cz/x", "Spotřeba ovesných nápojů roste ve městech rychle.")
    b = _item(
        "T2",
        "https://czso.cz/x/",
        "Spotřeba ovesných nápojů roste ve městech rychle a stabilně.",
        ref="SNP-" + "1" * 24,
    )
    result = merge_evidence(
        [_track("T1", a), _track("T2", b)], questionnaire=(), table=SOURCE_TABLE_V1
    )
    (only,) = result.candidates
    assert only.evidence.evidence_id == a.evidence_id and only.merged_ids == (b.evidence_id,)


def test_confirmation_from_another_source_raises_confidence_and_is_capped() -> None:
    claim = "Spotřeba ovesných nápojů roste ve městech rychle."
    media = _item("T1", "https://www.idnes.cz/a", claim)
    stats = _item("T2", "https://www.czso.cz/a", claim + " Podle úřadu.", ref="SNP-" + "2" * 24)
    alone = merge_evidence([_track("T1", media)], questionnaire=(), table=SOURCE_TABLE_V1)
    together = merge_evidence(
        [_track("T1", media), _track("T2", stats)], questionnaire=(), table=SOURCE_TABLE_V1
    )
    confirmed = next(c for c in together.candidates if c.evidence.evidence_id == media.evidence_id)
    assert confirmed.confirmations == (stats.evidence_id,)
    assert confirmed.confidence > alone.candidates[0].confidence
    assert all(c.confidence <= 0.98 for c in together.candidates)


def test_batches_follow_the_track_that_found_them() -> None:
    items = [
        _item("T1", "https://www.czso.cz/" + str(i), f"Tvrzení číslo {i} o trhu.") for i in range(5)
    ]
    items.append(_item("T2", "https://www.czso.cz/t2", "Jiné tvrzení o regulaci trhu."))
    merged = merge_evidence(
        [_track("T1", *items[:5]), _track("T2", items[5])], questionnaire=(), table=SOURCE_TABLE_V1
    )
    batches = verification_batches(merged.candidates, size=2)
    assert [[c.evidence.track_id for c in b] for b in batches] == [
        ["T1", "T1"],
        ["T1", "T1"],
        ["T1"],
        ["T2"],
    ]
    with pytest.raises(ValueError):
        verification_batches(merged.candidates, size=0)


def test_only_supported_candidates_are_accepted() -> None:
    items = [
        _item("T1", "https://www.czso.cz/v" + str(i), f"Tvrzení {i} o spotřebě.") for i in range(4)
    ]
    merged = merge_evidence([_track("T1", *items)], questionnaire=(), table=SOURCE_TABLE_V1)
    verdicts = {
        items[0].evidence_id: (Verdict.SUPPORTED, "citace to říká"),
        items[1].evidence_id: (Verdict.OVERSTATED, "citace říká méně"),
        items[2].evidence_id: (Verdict.UNSUPPORTED, "citace mluví o něčem jiném"),
    }
    accepted, quarantined = apply_verdicts(merged.candidates, verdicts)
    assert [a.evidence.evidence_id for a in accepted] == [items[0].evidence_id]
    assert accepted[0].verifier_reason == "citace to říká"
    assert {q.evidence_id: q.reason for q in quarantined} == {
        items[1].evidence_id: QuarantineReason.OVERSTATED_BY_VERIFIER,
        items[2].evidence_id: QuarantineReason.UNSUPPORTED_BY_VERIFIER,
        items[3].evidence_id: QuarantineReason.UNVERIFIED,
    }


def test_the_verifier_reads_the_quote_and_its_surroundings() -> None:
    text = "a" * 500 + "QUOTE" + "b" * 500
    window = excerpt_window(text, (500, 505), chars=10)
    assert window == "a" * 10 + "QUOTE" + "b" * 10
    assert excerpt_window("QUOTE", (0, 5)) == "QUOTE"
    with pytest.raises(ValueError):
        excerpt_window("abc", (2, 9))
