"""Merge and verification: declared scores decide, a student thesis and a finding off its
topic are set aside, leakage excludes from respondents only."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from aia_core.domain.deep_research.agents import Verdict
from aia_core.domain.deep_research.contracts import (
    Channel,
    EvidenceItem,
    EvidenceType,
    QuarantineReason,
    RecommendedUse,
    ResearchSubject,
    ScreenQuestion,
    SourceKind,
    SubjectKind,
    evidence_id,
    subject_key,
)
from aia_core.domain.deep_research.document_types import (
    DOCUMENT_RULES_VERSION,
    document_rules_of,
)
from aia_core.domain.deep_research.merge import (
    MERGE_RULES_VERSION,
    RespondentUse,
    SourceFacts,
    TrackEvidence,
    apply_verdicts,
    excerpt_window,
    merge_evidence,
    verification_batches,
)
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1
from aia_core.domain.deep_research.topicality import TOPICALITY_VERSION, topic_screen
from aia_core.domain.deep_research.works import (
    WORKS_VERSION,
    WorkNotice,
    WorkStatus,
    resolve_status,
)
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
    result = merge_evidence(
        [_track("T1", blog)], questionnaire=(), table=SOURCE_TABLE_V1, topics=None
    )
    assert result.candidates == ()
    (q,) = result.quarantined
    assert q.reason is QuarantineReason.LOW_SOURCE_QUALITY and "UNKNOWN" in q.detail


def test_approved_knowledge_and_official_sources_become_candidates() -> None:
    official = _item("T1", "https://www.czso.cz/a", "Spotřeba mléka klesá o dvě procenta.")
    internal = _item("T2", None, "Klient prodává v Brně.", ref="KNW-00000000000001@1")
    result = merge_evidence(
        [_track("T1", official), _track("T2", internal)],
        questionnaire=(),
        table=SOURCE_TABLE_V1,
        topics=None,
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
        topics=None,
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
        [_track("T1", a), _track("T2", b)], questionnaire=(), table=SOURCE_TABLE_V1, topics=None
    )
    (only,) = result.candidates
    assert only.evidence.evidence_id == a.evidence_id and only.merged_ids == (b.evidence_id,)


def test_confirmation_from_another_source_raises_confidence_and_is_capped() -> None:
    claim = "Spotřeba ovesných nápojů roste ve městech rychle."
    media = _item("T1", "https://www.idnes.cz/a", claim)
    stats = _item("T2", "https://www.czso.cz/a", claim + " Podle úřadu.", ref="SNP-" + "2" * 24)
    alone = merge_evidence(
        [_track("T1", media)], questionnaire=(), table=SOURCE_TABLE_V1, topics=None
    )
    together = merge_evidence(
        [_track("T1", media), _track("T2", stats)],
        questionnaire=(),
        table=SOURCE_TABLE_V1,
        topics=None,
    )
    confirmed = next(c for c in together.candidates if c.evidence.evidence_id == media.evidence_id)
    assert confirmed.confirmations == (stats.evidence_id,)
    assert confirmed.confidence > alone.candidates[0].confidence
    assert all(c.confidence <= 0.98 for c in together.candidates)


OATS = ResearchSubject(
    key=subject_key(SubjectKind.OBJECT, "Ovesný nápoj"),
    kind=SubjectKind.OBJECT,
    text="Ovesný nápoj",
    origin="t",
)
ALMOND = ResearchSubject(
    key=subject_key(SubjectKind.OBJECT, "Mandlový nápoj"),
    kind=SubjectKind.OBJECT,
    text="Mandlový nápoj",
    origin="t",
)
FACT = "Ovesný nápoj tvořil v roce 2025 polovinu prodejů rostlinných nápojů v síti klienta."


def test_an_off_topic_copy_is_set_aside_before_dedupe_and_never_stands_in_for_its_twin() -> None:
    # One knowledge fact, found first by the almond track and then by the oat track.
    ref = "KNW-00000000000001@1"
    title = {"source_title": "Prodeje v síti klienta"}
    by_almond = _item("T-almond", None, FACT[:-1] + " letos.", ref=ref, subject_key=ALMOND.key)
    by_almond = by_almond.model_copy(update=title)
    by_oats = _item("T-oats", None, FACT, ref=ref, subject_key=OATS.key).model_copy(update=title)
    tracks = [_track("T-almond", by_almond), _track("T-oats", by_oats)]
    unscreened = merge_evidence(tracks, questionnaire=(), table=SOURCE_TABLE_V1, topics=None)
    # Without the screen the almond copy, first in track order, held the oat finding.
    (held,) = unscreened.candidates
    assert (held.evidence.evidence_id, held.merged_ids) == (
        by_almond.evidence_id,
        (by_oats.evidence_id,),
    )
    screen = topic_screen((OATS, ALMOND), client_terms=())
    merged = merge_evidence(tracks, questionnaire=(), table=SOURCE_TABLE_V1, topics=screen)
    (only,) = merged.candidates
    assert (only.evidence.evidence_id, only.merged_ids) == (by_oats.evidence_id, ())
    (q,) = merged.quarantined
    assert (q.evidence_id, q.reason) == (by_almond.evidence_id, QuarantineReason.OFF_TOPIC)
    assert q.evidence == by_almond
    assert q.detail == "objekt: „Mandlový nápoj“; citace ani název zdroje ho nejmenuje"


def test_a_source_is_scored_before_its_topic_and_unknown_topics_are_never_accepted() -> None:
    blog = _item("T1", "https://someones-blog.example/post", FACT, subject_key=ALMOND.key)
    official = _item("T2", "https://www.czso.cz/a", FACT, subject_key="o-ffffffffffff")
    screen = topic_screen((OATS, ALMOND), client_terms=())
    merged = merge_evidence(
        [_track("T1", blog), _track("T2", official)],
        questionnaire=(),
        table=SOURCE_TABLE_V1,
        topics=screen,
    )
    assert merged.candidates == ()
    assert {q.evidence_id: q.reason for q in merged.quarantined} == {
        blog.evidence_id: QuarantineReason.LOW_SOURCE_QUALITY,
        # A topic the run's screen does not hold: unknown, set aside, kept.
        official.evidence_id: QuarantineReason.TOPIC_UNDETERMINED,
    }
    assert all(q.evidence is not None for q in merged.quarantined)


def test_the_merge_rules_carry_the_topic_rules() -> None:
    assert MERGE_RULES_VERSION.startswith("aia-merge-3/")
    assert WORKS_VERSION in MERGE_RULES_VERSION and TOPICALITY_VERSION in MERGE_RULES_VERSION


# --------------------------------------------------------------------------- the document (D4)

#: A fictional bachelor thesis in a university's thesis archive: its host alone scores it
#: well above acceptance (an academic institution, 0.70 undated).
THESIS_URL = "https://is.muni.cz/th/fikt1/fiktivni-prace.pdf"


def test_a_student_thesis_is_quarantined_by_name_and_kept_as_a_lead() -> None:
    thesis = _item("T1", THESIS_URL, "Klienti volí banku podle poplatků.")
    titled = _item(
        "T1",
        "https://www.czso.cz/fiktivni",
        "Spotřeba roste.",
        source_title="Spotřeba v domácnostech | Diplomová práce",
    )
    article = _item("T1", "https://polek.vse.cz/fiktivni-clanek", "Trh roste.")
    result = merge_evidence(
        [_track("T1", thesis, titled, article)],
        questionnaire=(),
        table=SOURCE_TABLE_V1,
        topics=None,
    )
    # The university's journal is its host's class; the thesis and the titled page are not.
    assert [c.evidence.evidence_id for c in result.candidates] == [article.evidence_id]
    assert [c.score.source_class for c in result.candidates] == ["ACADEMIC_INSTITUTION"]
    assert [(q.evidence_id, q.reason, q.detail) for q in result.quarantined] == [
        (
            thesis.evidence_id,
            QuarantineReason.STUDENT_THESIS,
            "adresa vede do archivu kvalifikačních prací is.muni.cz/th/ "
            f"(pravidla {DOCUMENT_RULES_VERSION})",
        ),
        (
            titled.evidence_id,
            QuarantineReason.STUDENT_THESIS,
            f"název zdroje uvádí „diplomová práce“ (pravidla {DOCUMENT_RULES_VERSION})",
        ),
    ]
    # Kept whole, so a researcher still sees it as a lead.
    assert [q.evidence for q in result.quarantined] == [thesis, titled]


def test_a_thesis_is_typed_at_the_address_its_page_was_read_from() -> None:
    # The search hit redirected into a thesis archive: the final address is the source's.
    redirected = _item("T1", "https://example.org/odkaz", "Klienti volí banku podle poplatků.")
    track = TrackEvidence(
        track_id="T1",
        evidence=(redirected,),
        sources={
            redirected.source_ref: SourceFacts(
                ref=redirected.source_ref,
                kind=SourceKind.WEB_PAGE,
                url=THESIS_URL,
                published=None,
                retrieved=RETRIEVED,
            )
        },
    )
    result = merge_evidence([track], questionnaire=(), table=SOURCE_TABLE_V1, topics=None)
    (q,) = result.quarantined
    assert q.reason is QuarantineReason.STUDENT_THESIS


def test_client_knowledge_is_never_typed() -> None:
    # A person approved it as the client's own, whatever document it came from.
    internal = _item(
        "T1",
        None,
        "Klient prodává v Brně.",
        ref="KNW-00000000000001@1",
        source_title="Bakalářská práce: Prodej v Brně",
    )
    result = merge_evidence(
        [_track("T1", internal)], questionnaire=(), table=SOURCE_TABLE_V1, topics=None
    )
    assert [c.score.source_class for c in result.candidates] == ["CLIENT_KNOWLEDGE"]
    assert result.quarantined == ()


def test_a_retraction_is_named_before_a_thesis_and_a_thesis_before_its_score_and_topic() -> None:
    retracted = _item("T1", THESIS_URL, "Klienti volí banku podle poplatků.")
    standing = resolve_status(
        "10.5555/fikt.2025.7",
        {
            "crossref-works-1": (
                WorkNotice(
                    status=WorkStatus.RETRACTED,
                    notice_doi="10.5555/notice.1",
                    source="retraction-watch",
                ),
            )
        },
        checked_at=datetime(2026, 10, 8, 12, 0, tzinfo=UTC),
    )
    facts = SourceFacts(
        ref=retracted.source_ref,
        kind=SourceKind.WEB_PAGE,
        url=THESIS_URL,
        published=None,
        retrieved=RETRIEVED,
        work_status=standing,
    )
    # A thesis register is an unknown host to the source table (it would score 0.15), and the
    # finding names no almond drink: the thesis is what it is set aside as.
    register = _item("T2", "https://theses.cz/id/fikt1/", "Spotřeba roste.", subject_key=ALMOND.key)
    result = merge_evidence(
        [
            TrackEvidence(
                track_id="T1", evidence=(retracted,), sources={retracted.source_ref: facts}
            ),
            _track("T2", register),
        ],
        questionnaire=(),
        table=SOURCE_TABLE_V1,
        topics=topic_screen((OATS, ALMOND), client_terms=()),
    )
    assert result.candidates == ()
    assert [(q.evidence_id, q.reason) for q in result.quarantined] == [
        (retracted.evidence_id, QuarantineReason.RETRACTED_SOURCE),
        (register.evidence_id, QuarantineReason.STUDENT_THESIS),
    ]


def test_the_merge_rules_carry_the_document_rules() -> None:
    carried = f"aia-merge-3/{WORKS_VERSION}/{TOPICALITY_VERSION}/{DOCUMENT_RULES_VERSION}"
    assert carried == MERGE_RULES_VERSION
    assert document_rules_of(MERGE_RULES_VERSION) == DOCUMENT_RULES_VERSION


def test_batches_follow_the_track_that_found_them() -> None:
    items = [
        _item("T1", "https://www.czso.cz/" + str(i), f"Tvrzení číslo {i} o trhu.") for i in range(5)
    ]
    items.append(_item("T2", "https://www.czso.cz/t2", "Jiné tvrzení o regulaci trhu."))
    merged = merge_evidence(
        [_track("T1", *items[:5]), _track("T2", items[5])],
        questionnaire=(),
        table=SOURCE_TABLE_V1,
        topics=None,
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
    merged = merge_evidence(
        [_track("T1", *items)], questionnaire=(), table=SOURCE_TABLE_V1, topics=None
    )
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
