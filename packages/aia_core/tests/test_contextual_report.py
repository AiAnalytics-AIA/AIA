"""A literature chapter consumes checked evidence, never the withheld prose."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from aia_core.application.contextual_report import (
    TopicRulesUnread,
    literature_sections,
    todays_topic_rules,
)
from aia_core.application.deep_research import BundleNotReady
from aia_core.application.report import ReportCompositionRefused
from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.confidence import CONFIDENCE_WEIGHTS_V1
from aia_core.domain.deep_research.contracts import (
    ClientTerm,
    DeepResearchRequest,
    ResearchSubject,
    SourceKind,
    SubjectKind,
    digest,
    subject_key,
)
from aia_core.domain.deep_research.document_types import DOCUMENT_RULES_VERSION
from aia_core.domain.deep_research.integration import ResultBatteryObjectTarget
from aia_core.domain.deep_research.interpretation import interpretation_mission
from aia_core.domain.deep_research.merge import MERGE_RULES_VERSION
from aia_core.domain.deep_research.topicality import (
    TOPICALITY_VERSION,
    TopicRule,
    TopicScreen,
    TopicVerdict,
    topic_screen,
)
from aia_core.domain.fieldwork import OriginKind
from aia_core.domain.report.model import (
    BulletList,
    Callout,
    Heading,
    Link,
    Paragraph,
    Quote,
    Table,
    Text,
    TextCell,
)
from aia_core.domain.research_design import compile_design
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.artifact_repository import ArtifactNotFound
from aia_core.infrastructure.storage import IntegrityError, ObjectNotFound, StorageError


def bundle(**updates: object) -> EvidenceBundle:
    path = Path(__file__).parent / "fixtures/deep_research_pre_step1/bundle.json"
    original = EvidenceBundle.model_validate_json(path.read_bytes())
    data = {**original.model_dump(mode="json"), **updates, "sha256": ""}
    data = EvidenceBundle.model_validate(data).model_dump(mode="json")
    data["sha256"] = digest(data)
    return EvidenceBundle.model_validate(data)


def _words(block: object) -> str:
    """Every word a reader sees in a block: paragraphs, callouts, lists, quotes, tables."""
    if isinstance(block, Callout):
        # Its title too: a reader sees it (review 3: a wrong title passed every test).
        words = "".join(i.text for i in block.content if isinstance(i, (Text, Link)))
        return f"{block.title}\n{words}" if block.title else words
    if isinstance(block, Paragraph):
        return "".join(i.text for i in block.content if isinstance(i, (Text, Link)))
    if isinstance(block, BulletList):
        return "\n".join(
            "".join(i.text for i in item.content if isinstance(i, Text)) for item in block.items
        )
    if isinstance(block, Quote):
        return f"{block.text} {block.attribution}"
    if isinstance(block, Table):
        return (
            "\n".join(
                " | ".join(c.text for c in row.cells if isinstance(c, TextCell))
                for row in block.rows
            )
            + "\n"
            + "\n".join(block.notes)
        )
    return ""


def prose(
    value: EvidenceBundle,
    origin: OriginKind | None = None,
    tiers_approved: bool | None = None,
    topics: TopicScreen | TopicRulesUnread | None = None,
) -> str:
    return "\n".join(
        _words(b)
        for s in literature_sections(
            value,
            research_run_id="RUN-abc",
            origin=origin,
            tiers_approved=tiers_approved,
            topics=topics,
        )
        for b in s.blocks
    )


def test_source_claims_have_separate_citations_limits_and_fixture_disclosure() -> None:
    original = bundle()
    written = prose(original, OriginKind.SIMULATED)
    for finding in original.accepted:
        assert finding.evidence.claim in written
    for excluded in original.synthesis.check.excluded:
        assert excluded.text not in written
    assert "[L1]" in written and "[L2]" in written
    assert "2026-09-01" in written
    assert "nahraných testovacích výměn" in written
    assert "nikoli o systematický přehled" in written
    assert "Odpovědi této studie jsou smyšlené a nejsou odhadem žádné populace." in written
    assert original.sha256 in written
    assert "nikoli schválením věcné platnosti" in written
    assert all(
        not b.refs
        for s in literature_sections(original, research_run_id="RUN-abc")
        for b in s.blocks
        if isinstance(b, Paragraph)
    )


def test_an_empty_bundle_reports_a_gap_instead_of_inventing_a_review() -> None:
    written = prose(bundle(accepted=[], synthesis=None, quality_status="NO_EVIDENCE"))
    assert "žádné přijaté zjištění" in written
    assert "L1" not in written


def test_the_chapter_names_its_review_and_seal_and_never_the_reports_status() -> None:
    # A version states its review status in its footers alone (D2): the chapter ended with
    # "…součástí interního neschváleného návrhu zprávy", and an approved export printed that
    # under a SCHVÁLENO footer (cross-review).
    original = bundle()
    written = prose(original)
    assert written.endswith(f"Deep Research: RUN-abc. Pečeť ověřeného balíčku: {original.sha256}.")
    assert "neschválen" not in written.casefold() and "koncept" not in written.casefold()
    # "návrh" is the study's design in a report, never a model's proposed synthesis.
    assert "Automaticky sestavená syntéza prošla kontrolou citací a čísel" in written
    assert "návrh syntézy" not in written


def test_corrupt_seal_and_foreign_synthesis_citations_refuse() -> None:
    original = bundle()
    with pytest.raises(ReportCompositionRefused, match="seal"):
        prose(original.model_copy(update={"sha256": "a" * 64}))
    synthesis = original.synthesis.model_dump(mode="json")
    synthesis["check"]["findings"][0]["evidence_ids"] = ["EV-0000000000000000"]
    with pytest.raises(ReportCompositionRefused, match="outside"):
        prose(bundle(synthesis=synthesis))


def test_missing_synthesis_keeps_verified_findings_and_does_not_invent_benchmarks() -> None:
    original = bundle(synthesis=None)
    written = prose(original)
    # Each claim is printed beside its verbatim cited passage, so a reader checks the
    # paraphrase against it (research-integrity-report chunk 2).
    for a in original.accepted:
        assert a.evidence.quote in written
    assert "Souvislá syntéza nebyla přijata" in written
    assert "neobsahují strukturovaný číselný benchmark" in written
    for a in original.accepted:
        assert a.evidence.claim in written


def test_unlabelled_historical_years_do_not_become_benchmark_paragraphs() -> None:
    accepted = bundle().model_dump(mode="json")["accepted"]
    for item in accepted:
        item["evidence"]["claim"] = "Sociomapping was developed in 1993."
        item["evidence"]["measures"] = [{"value": 1993}]
    written = prose(bundle(accepted=accepted, synthesis=None))
    assert "Sociomapping was developed in 1993." in written
    assert "\n1993 [L" not in written
    assert "neobsahují strukturovaný číselný benchmark" in written


def test_labelled_numeric_data_keeps_its_indicator_and_unit() -> None:
    accepted = bundle().model_dump(mode="json")["accepted"]
    accepted[0]["evidence"]["measures"] = [
        {"value": 25, "unit": "%", "measure_name": "Podíl odpovědí"}
    ]
    accepted[0]["evidence"]["claim"] = "Podíl odpovědí byl 25 % v hodnocené skupině."
    written = prose(bundle(accepted=accepted, synthesis=None))
    assert "Podíl odpovědí byl 25 % v hodnocené skupině. [L1]" in written
    assert "neobsahují strukturovaný číselný benchmark" not in written


def test_long_research_subject_is_body_text_and_duplicate_gaps_appear_once() -> None:
    original = bundle()
    synthesis = original.synthesis.model_dump(mode="json")
    synthesis["check"]["gaps"] = ["Chybí původní studie -- nebyla získána."]
    synthesis["check"]["limitations"] = ["Chybí původní studie: nebyla získána."]
    synthesis["brief"] = {
        "kind": "deep_research_brief",
        "version": "test",
        "status": "EMPTY",
        "summary": None,
        "summary_withheld": None,
        "answers": [],
        "findings": [],
        "conflicts": [],
        "gaps": [],
        "limitations": [],
        "excluded": [],
        "repair": None,
        "weights": CONFIDENCE_WEIGHTS_V1.model_dump(mode="json"),
    }
    synthesis["brief"]["acquisition_gaps"] = [
        {
            "gap_id": "GAP-example",
            "publisher": None,
            "title": "Původní publikace",
            "reason": "not_pursued",
            "rungs_tried": [],
            "ladder_version": None,
            "how_to_obtain": "Doplnit z knihovny.",
            "raised_by": "investigator_lead",
            "origin": "LIVE_RETRIEVAL",
            "subject_key": None,
            "track_id": None,
            "url": None,
            "text_withheld": False,
        }
    ]
    gap = {
        "gap_id": "GAP-need",
        "kind": "unanswered",
        "subject_key": original.subjects[0].key,
        "track_id": None,
        "need": "Srovnatelná původní studie",
        "reason": "Sociomapping není aplikovatelný na hodnocení služeb.",
        "tried": None,
        "conflict_id": None,
        "text_withheld": False,
    }
    synthesis["brief"]["gaps"] = [gap, {**gap, "gap_id": "GAP-need-duplicate"}]
    synthesis["brief"]["acquisition_gaps"].append(
        {
            **synthesis["brief"]["acquisition_gaps"][0],
            "gap_id": "GAP-withheld-title",
            "title": "[text s číslem bez citace je jen v přepisu stopy]",
            "text_withheld": True,
        }
    )
    updated = bundle(synthesis=synthesis)
    sections = literature_sections(updated, research_run_id="RUN-abc")
    assert not any(
        isinstance(block, Heading) and block.text == updated.subjects[0].text
        for section in sections
        for block in section.blocks
    )
    assert updated.subjects[0].text in prose(updated)
    assert "Chybí původní studie" not in prose(updated)
    assert prose(updated).count("Srovnatelná původní studie") == 1
    assert gap["reason"] not in prose(updated)
    assert "přepisu stopy" not in prose(updated)
    assert "zdroj bez uvedeného názvu" in prose(updated)
    assert "not_pursued" not in prose(updated)
    # One notice per reason, its sources together and said in the plural (review 2: "tohoto
    # zdroje" stood before two titles), how to obtain them said once.
    assert (
        "Získání těchto zdrojů nebylo v tomto běhu dokončeno: Původní publikace; zdroj bez "
        "uvedeného názvu. Doplnit z knihovny."
    ) in prose(updated)
    assert prose(updated).count("Doplnit z knihovny.") == 1


def test_citation_valid_inapplicability_inference_is_not_published() -> None:
    original = bundle()
    synthesis = original.synthesis.model_dump(mode="json")
    unsupported = "Sociomapping není aplikovatelný na hodnocení služeb."
    synthesis["check"]["summary"] = unsupported
    synthesis["check"]["findings"][0]["text"] = unsupported
    synthesis["check"]["gaps"] = [unsupported]
    synthesis["check"]["limitations"] = [unsupported]
    updated = bundle(synthesis=synthesis)
    before = updated.model_dump_json()
    written = prose(updated)
    assert unsupported not in written
    assert "nikoli schválením věcné platnosti" in written
    for finding in updated.accepted:
        assert finding.evidence.claim in written
    assert updated.model_dump_json() == before
    assert updated.verify()


def test_partial_measure_period_does_not_replace_the_source_claims_full_range() -> None:
    accepted = bundle().model_dump(mode="json")["accepted"]
    accepted[0]["evidence"]["claim"] = (
        "Přehled vybral 14 příspěvků ze 149 publikací z let 2018-2022."
    )
    accepted[0]["evidence"]["measures"] = [
        {"value": 14, "period": "Y2018", "measure_name": "vybrané příspěvky"}
    ]
    written = prose(bundle(accepted=accepted, synthesis=None))
    assert "14 příspěvků ze 149 publikací z let 2018-2022. [L1]" in written
    assert "vybrané příspěvky:" not in written


def _single_source() -> EvidenceBundle:
    """The Fio pattern, fictional: every accepted finding from one university thesis, found
    for a research topic it is not about (research-integrity-report chunk 2)."""
    original = bundle()
    data = original.model_dump(mode="json")
    thesis = "https://is.vse.cz/zp/fiktivni-prace-o-volbe-hypotecni-banky.pdf"
    kept = []
    for a in data["accepted"][:3]:
        a["evidence"]["source_url"] = thesis
        a["evidence"]["source_title"] = "Volba poskytovatele hypotéky (fiktivní práce)"
        a["evidence"]["subject_key"] = data["subjects"][0]["key"]
        a["score"]["source_class"] = "ACADEMIC_INSTITUTION"
        kept.append(a)
    return bundle(accepted=kept, synthesis=None)


def test_a_review_resting_on_one_source_says_so_and_shows_what_each_finding_rests_on() -> None:
    weak = _single_source()
    written = prose(weak)
    assert "Všechna přijatá zjištění (3) pocházejí od jediného vydavatele (vse.cz)" in written
    assert "nenabízí nezávislé potvrzení" in written
    # Credibility is the domain's, said as that, never as relevance; the thesis its web
    # findings come from is named beside it, typed at composition (D4).
    assert (
        "is.vse.cz: akademická instituce; studentská kvalifikační práce (určeno při sestavení "
        "zprávy)"
    ) in written
    assert "jen podle domény, nikoli podle obsahu" in written
    assert "Autora, metodu a vzorek zdroje AIA nezaznamenává" in written
    # Every claim stands beside its verbatim passage and the topic it was searched for.
    topic = weak.subjects[0].text
    for a in weak.accepted:
        assert f"{a.evidence.quote} [L1] Volba poskytovatele hypotéky (fiktivní práce); " in written
        assert f"hledáno k tématu: {topic}" in written
    assert "[L2]" not in written
    assert "neobsahují strukturovaný číselný benchmark" in written


def test_two_pages_of_one_publisher_are_still_one_source_of_evidence() -> None:
    weak = _single_source()
    data = weak.model_dump(mode="json")
    data["accepted"][1]["evidence"]["source_url"] = "https://www.vse.cz/fiktivni-anotace"
    two_pages = bundle(accepted=data["accepted"], synthesis=None)
    written = prose(two_pages)
    assert "[L2]" in written  # two citations ...
    assert "pocházejí od jediného vydavatele (vse.cz)" in written  # ... one publisher
    # Its title says the same, never "one source" beside two cited ones (review 2, F36).
    assert "Rešerše stojí na jednom vydavateli" in written
    assert "jednom zdroji" not in written


def test_counts_say_how_much_was_captured_against_how_little_was_cited() -> None:
    written = prose(_single_source())
    # As "label: number", so no count reads as bad Czech ("z 1 citovaných zdrojů" did).
    assert "Přijatá zjištění: 3, citované zdroje: 1." in written
    assert "Důvody odmítnutí:" in written
    assert "hodnocení zdroje (typ domény a stáří stránky) je pod prahem přijetí (1krát)" in written
    assert "PARTIAL" not in written and "GROUNDED" not in written  # status in words


def test_every_rejection_reason_and_source_class_has_words_in_the_report() -> None:
    from aia_core.application.contextual_report import _QUARANTINE, _SOURCE_CLASS
    from aia_core.domain.deep_research.contracts import QuarantineReason
    from aia_core.domain.deep_research.sources import SourceClass

    assert set(_QUARANTINE) == {r.value for r in QuarantineReason}
    assert set(_SOURCE_CLASS) == {c.value for c in SourceClass}


def test_the_origin_sentence_follows_the_studys_respondents_and_unknown_says_nothing() -> None:
    """ARCHITECTURE.md labels: an origin is read through origin_kind, never assumed."""
    assert "modelovali AI respondenti" in prose(bundle(), OriginKind.MODELLED)
    unknown = prose(bundle())
    assert "smyšlené" not in unknown and "modelovali" not in unknown


def test_two_ministries_on_one_government_domain_are_two_publishers() -> None:
    """The publisher is Deep Research's own (triangulation.publisher_identity): the report's
    single-source callout never reads gov.cz, or co.uk, as one publisher."""
    weak = _single_source()
    data = weak.model_dump(mode="json")
    data["accepted"][0]["evidence"]["source_url"] = "https://www.mpo.gov.cz/fiktivni"
    data["accepted"][1]["evidence"]["source_url"] = "https://www.mfcr.gov.cz/fiktivni"
    data["accepted"][2]["evidence"]["source_url"] = "https://www.mfcr.gov.cz/fiktivni"
    written = prose(bundle(accepted=data["accepted"], synthesis=None))
    assert "jediného vydavatele" not in written


def test_a_withheld_gap_need_prints_no_internal_marker() -> None:
    original = bundle()
    synthesis = original.synthesis.model_dump(mode="json")
    marker = "[text s číslem bez citace je jen v přepisu stopy]"
    synthesis["brief"] = {
        "kind": "deep_research_brief",
        "version": "test",
        "status": "EMPTY",
        "summary": None,
        "summary_withheld": None,
        "answers": [],
        "findings": [],
        "conflicts": [],
        "gaps": [
            {
                "gap_id": "GAP-withheld",
                "kind": "unanswered",
                "subject_key": original.subjects[0].key,
                "track_id": None,
                "need": marker,
                "reason": "x",
                "tried": None,
                "conflict_id": None,
                "text_withheld": True,
            }
        ],
        "limitations": [],
        "excluded": [],
        "repair": None,
        "weights": CONFIDENCE_WEIGHTS_V1.model_dump(mode="json"),
        "acquisition_gaps": [],
    }
    written = prose(bundle(synthesis=synthesis))
    assert marker not in written and "podklad bez uvedeného znění" in written
    # Three withheld needs are three, never merged into one (review 2).
    gaps = synthesis["brief"]["gaps"]
    synthesis["brief"]["gaps"] = [{**gaps[0], "gap_id": f"GAP-withheld-{i}"} for i in range(3)]
    three = prose(bundle(synthesis=synthesis))
    assert "podklady bez uvedeného znění (počet: 3)" in three and "znění;" not in three


def test_the_source_table_is_called_approved_only_where_the_review_pinned_its_approval() -> None:
    """Review 3: the note called the table an unapproved proposal on every review, though a
    priced live route runs only once the review's pinned settings sign it off (ADR 0022)."""
    proposed = prose(bundle(), tiers_approved=False)
    assert "navržená tabulka zdrojů" in proposed and "dosud neschválila" in proposed
    approved = prose(bundle(), tiers_approved=True)
    assert "organizace schválila v nastavení Deep Research" in approved
    assert "neschválila" not in approved and "navržená" not in approved
    unpinned = prose(bundle())
    assert "rešerše nezaznamenala" in unpinned
    assert "neschválila" not in unpinned and "schválila v nastavení" not in unpinned


def test_three_withheld_sources_of_one_reason_are_three_in_the_plural() -> None:
    """Review 3: the plural reason and the count of withheld sources had no test that could fail."""
    original = bundle()
    synthesis = original.model_dump(mode="json")["synthesis"]
    synthesis["brief"] = {
        "kind": "deep_research_brief",
        "version": "test",
        "status": "EMPTY",
        "summary": None,
        "summary_withheld": None,
        "answers": [],
        "findings": [],
        "conflicts": [],
        "gaps": [],
        "limitations": [],
        "excluded": [],
        "repair": None,
        "weights": CONFIDENCE_WEIGHTS_V1.model_dump(mode="json"),
        "acquisition_gaps": [
            {
                "gap_id": f"GAP-withheld-{i}",
                "publisher": None,
                "title": "[skryto]",
                "reason": "not_pursued",
                "rungs_tried": [],
                "ladder_version": None,
                "how_to_obtain": "",
                "raised_by": "investigator_lead",
                "origin": "LIVE_RETRIEVAL",
                "subject_key": None,
                "track_id": None,
                "url": None,
                "text_withheld": True,
            }
            for i in range(3)
        ],
    }
    written = prose(bundle(synthesis=synthesis))
    assert "zdroje bez uvedeného názvu (počet: 3)" in written
    assert "[skryto]" not in written
    assert (
        "Získání těchto zdrojů nebylo v tomto běhu dokončeno: zdroje bez uvedeného názvu "
        "(počet: 3)." in written
    )


# --------------------------------------------------------------------------- the topic (D4)

TRUST = "Do jaké míry klienti důvěřují založení běžného účtu online?"
CHECKED = "AIA také ověřila, že se zjištění týká tématu, pro které bylo hledáno"
UNCHECKED = "Neověřila však, zda se zdroj týká stejného jevu, populace, území a období"
#: Each topic check as the chapter says it, of the topic the reader sees in its list.
OBJECT_CHECK = (
    "U tématu, které je názvem objektu, ověřila, že citace nebo název zdroje obsahuje ta slova "
    "jeho názvu, kterými se liší od ostatních objektů této rešerše (je-li objekt v rešerši "
    "jediný, celý název)."
)
QUESTION_CHECK = (
    "U tématu, které je otázkou nebo popisem hledaného kontextu (k výsledku otázky, výzkumné "
    "otázce, cíli studie, kategorii nebo dvojici objektů), ověřila, že tvrzení, citace a název "
    "zdroje dohromady sdílejí aspoň dvě jeho slova (zbývá-li jediné, to jedno); nepočítají se "
    "přitom slova, kterými AIA téma uvozuje, jména klienta, tázací slova a slova s číslicí."
)
CROSS_CHECK = (
    "U tématu, které za pomlčkou připojuje název objektu, ověřila obojí: u objektu za pomlčkou "
    "slova jeho názvu, u části před pomlčkou její slova jako u otázky."
)
#: R4 reads the quote and the source's title, never the rest of the source, so the sentence
#: names those two: "zdroj nejmenuje" claimed the whole source was read (cross-review).
CONCEPT_CHECK = (
    "U každého tématu, které jmenuje pojem z pevně dané skupiny (druh bankovního produktu; "
    "objekt této rešerše, je-li jich v ní víc), ověřila také, že citace ani název zdroje "
    "nejmenují místo něj jiný pojem téže skupiny."
)


def _merged_under(value: EvidenceBundle, merge: str) -> EvidenceBundle:
    return bundle(
        **{
            k: v
            for k, v in value.model_dump(mode="json").items()
            if k not in {"versions", "sha256"}
        },
        versions={**value.versions, "merge": merge},
    )


def test_a_review_merged_under_the_topic_rules_says_what_they_check_and_what_they_leave() -> None:
    for merge in (MERGE_RULES_VERSION, "aia-merge-9/aia-works-3/aia-dr-topicality-4/x"):
        written = prose(_merged_under(bundle(), merge))
        assert CHECKED in written and UNCHECKED not in written
        assert "ani zda shoda slov znamená shodu významu" in written
        assert "stejné populace, území a období" in written
    # A review merged before them keeps the sentence that nobody checked the topic.
    assert bundle().versions["merge"] == "aia-merge-1"
    written = prose(bundle())
    assert UNCHECKED in written and CHECKED not in written


def test_each_topic_check_the_chapter_names_is_said_of_the_topics_it_runs_for() -> None:
    """The paragraph says each rule of the topics it runs for, and the rules do run so: a
    tracked object needs only the words that tell it from the others (R1), a research question
    two of its words (R3), a question about an object both (cross-review: the chapter claimed
    the two-word check for every finding, and an object's never had it). Extending R3 to
    objects fails the first judgement here until the sentence says so."""
    objects = [
        ResearchSubject(
            key=subject_key(SubjectKind.OBJECT, name),
            kind=SubjectKind.OBJECT,
            text=name,
            origin="tracked_objects",
        )
        for name in ("Ovesný nápoj", "Mandlový nápoj", "Sójový nápoj")
    ]
    asked = "Proč lidé kupují rostlinné nápoje?"
    question = ResearchSubject(
        key=subject_key(SubjectKind.QUESTION, asked),
        kind=SubjectKind.QUESTION,
        text=asked,
        origin="research_plan.research_questions[0]",
    )
    cross = ResearchSubject(
        key="x-" + "0" * 12,
        kind=SubjectKind.CROSS,
        text=f"{asked} \u2014 {objects[0].text}",
        origin=f"cross:{question.key}|{objects[0].key}",
        question_key=question.key,
        object_key=objects[0].key,
    )
    screen = topic_screen([*objects, question, cross], client_terms=())
    flakes = "Ovesné vločky zdražily o 12 %."
    one_word = {"claim": flakes, "quote": flakes, "source_title": "Ceny obilovin 2025"}
    # A tracked object: its one distinguishing word is enough, no second word asked for.
    assert screen.judge_text(objects[0].key, **one_word).verdict is TopicVerdict.ON_TOPIC
    # A question about it: the object named, and still two of the question's words.
    about = screen.judge_text(cross.key, **one_word)
    assert (about.verdict, about.rule) == (TopicVerdict.OFF_TOPIC, TopicRule.TOPIC_WORDS)
    # A research question: one shared word ("rostlinné") is not two.
    oils = "Rostlinné oleje zdražily."
    one = screen.judge_text(question.key, claim=oils, quote=oils, source_title="")
    assert (one.verdict, one.rule) == (TopicVerdict.OFF_TOPIC, TopicRule.TOPIC_WORDS)
    assert screen.profiles[objects[0].key].topic_terms == ()  # an object has no topic words
    # The concept swap reads the quote and the source's title, never the claim or the rest of
    # the source: a mortgage in the title sets a current-account finding aside, a mortgage in
    # the claim alone is not what R4 decides on.
    current = "Proč lidé zakládají běžný účet u banky?"
    account = ResearchSubject(
        key=subject_key(SubjectKind.QUESTION, current),
        kind=SubjectKind.QUESTION,
        text=current,
        origin="research_plan.research_questions[1]",
    )
    banks = topic_screen([account], client_terms=())
    said = "Lidé u banky zakládají účet podle poplatků."
    titled = banks.judge_text(account.key, claim=said, quote=said, source_title="Ceny hypoték")
    assert (titled.verdict, titled.rule) == (TopicVerdict.OFF_TOPIC, TopicRule.CONCEPT_SWAP)
    claimed = banks.judge_text(
        account.key, claim=f"{said} Hypotéky také.", quote=said, source_title="Poplatky bank"
    )
    assert claimed.rule is not TopicRule.CONCEPT_SWAP

    # The fixture's review holds questions and objects, no cross: each said once, the cross's
    # double check not at all, and the two-word check of no object.
    written = prose(_merged_under(bundle(), MERGE_RULES_VERSION))
    assert OBJECT_CHECK in written and QUESTION_CHECK in written and CONCEPT_CHECK in written
    assert CROSS_CHECK not in written
    assert written.count("aspoň dvě") == 1  # said of questions, nothing else


def _with_subjects(*subjects: ResearchSubject) -> str:
    """The chapter of a review merged under the topic rules over ``subjects``."""
    held = bundle(subjects=[s.model_dump(mode="json") for s in subjects])
    return prose(_merged_under(held, MERGE_RULES_VERSION))


def test_an_interpretation_reviews_topics_are_each_said_with_the_checks_that_ran() -> None:
    """Every report with literature is Interpretation Research (``_compose`` refuses any other
    purpose), and its questions are framings: the result of one tracked object is the object
    and a framed question about it, a QUESTION that R1 never reads. The chapter said that a
    question about an object was checked for the object's name (cross-review): a finding filed
    under the framed question and quoting another plant drink passes. Each sentence now says
    its check of the topic the reader sees, and each is held to what the screen does."""
    design = {
        "title": "Rostlinné nápoje",
        "sections": [
            {
                "type": "object_battery",
                "id": "napoje",
                "title": "Nápoje",
                "object_family": "rostlinné nápoje",
                "objects": ["Ovesný nápoj", "Mandlový nápoj", "Sójový nápoj"],
                "object_question": "Jak hodnotíte {object}?",
            }
        ],
    }
    spec, problems = compile_design(design)
    assert spec is not None, problems
    (battery,) = spec.batteries
    target = ResultBatteryObjectTarget(
        kind="RESULT_BATTERY_OBJECT",
        research_run_id="RUN-00000000000000a1",
        aggregate_artifact_id="ART-00000000000000a3",
        battery_id=battery.id,
        object_id=battery.objects[0].id,
    )
    obj, framed = interpretation_mission(
        target, specification=spec.model_dump(mode="json"), design=design
    )
    assert (obj.kind, obj.text) == (SubjectKind.OBJECT, "Ovesný nápoj")
    assert framed.kind is SubjectKind.QUESTION and framed.text.startswith("Kontext a srovnání")
    almond = "Spotřebitelé začali hodnotit mandlový nápoj výše než kravské mléko."
    finding = {"claim": almond, "quote": almond, "source_title": ""}
    screen = topic_screen([obj, framed], client_terms=())
    # The object: its name is checked, and the quote does not name it.
    judged = screen.judge_text(obj.key, **finding)
    assert (judged.verdict, judged.rule) == (TopicVerdict.OFF_TOPIC, TopicRule.OBJECT_NAMED)
    # The framed question about it: two of its words, not the object's name.
    assert screen.judge_text(framed.key, **finding).verdict is TopicVerdict.ON_TOPIC
    written = _with_subjects(obj, framed)
    assert OBJECT_CHECK in written and QUESTION_CHECK in written
    assert CROSS_CHECK not in written and "v otázce na něj" not in written
    # A deeper preset opens the cross: there the object's name is checked too, and said so.
    cross = ResearchSubject(
        key="x-" + "1" * 12,
        kind=SubjectKind.CROSS,
        text=f"{framed.text} \u2014 {obj.text}",
        origin=f"cross:{framed.key}|{obj.key}",
        question_key=framed.key,
        object_key=obj.key,
    )
    judged = topic_screen([obj, framed, cross], client_terms=()).judge_text(cross.key, **finding)
    assert (judged.verdict, judged.rule) == (TopicVerdict.OFF_TOPIC, TopicRule.OBJECT_NAMED)
    assert CROSS_CHECK in _with_subjects(obj, framed, cross)
    # A review of one Sociomap object holds no question: no two-word check is claimed.
    alone = _with_subjects(obj)
    assert OBJECT_CHECK in alone and CONCEPT_CHECK in alone
    assert QUESTION_CHECK not in alone and "aspoň dvě" not in alone


def _older_current_account_review() -> tuple[EvidenceBundle, TopicScreen]:
    """F1, fictional, as a review merged before the topic rules stored it: three findings from
    a mortgage thesis accepted for a current-account topic, one on that topic, the rest the
    fixture's own; Banka Lípa is no bank."""
    original = bundle()
    data = original.model_dump(mode="json")
    trust = ResearchSubject(
        key=subject_key(SubjectKind.QUESTION, TRUST),
        kind=SubjectKind.QUESTION,
        text=TRUST,
        origin="research_plan.research_questions[0]",
    ).model_dump(mode="json")
    thesis = "https://is.vse.cz/zp/fiktivni-prace-o-volbe-hypotecni-banky.pdf"
    for a in data["accepted"][:3]:
        a["evidence"]["source_url"] = thesis
        a["evidence"]["source_title"] = "Faktory výběru poskytovatele hypotečního úvěru"
        a["evidence"]["subject_key"] = trust["key"]
    on = data["accepted"][3]["evidence"]
    on["subject_key"] = trust["key"]
    on["source_title"] = "Digitální bankovnictví v Česku (fiktivní)"
    on["quote"] = on["claim"] = "Podíl klientů, kteří si běžný účet založili online, vzrostl."
    on["measures"] = []
    older = bundle(subjects=[trust, *data["subjects"]], accepted=data["accepted"], synthesis=None)
    screen = topic_screen(
        older.subjects, client_terms=(ClientTerm(term="Banka Lípa", source="client.name"),)
    )
    return older, screen


def test_an_older_review_labels_what_todays_topic_rules_would_not_accept() -> None:
    older, screen = _older_current_account_review()
    stored = older.model_dump(mode="json")
    written = prose(older, topics=screen)
    # One callout names the sources; each finding says why, with the rules' version. The
    # thesis's two web findings are named as the merge would set them aside first (D4); the
    # approved fact carrying its address is Client Knowledge, never typed, so its topic decides.
    assert "Zjištění, která by dnešní pravidla nepřijala" in written
    assert "Přijatá zjištění, která by podle nich neprošla: 3." in written
    assert f"podle pravidel {DOCUMENT_RULES_VERSION}: 2, ze zdroje L1." in written
    assert f"podle kontroly tématu {TOPICALITY_VERSION}: 1, ze zdroje L1." in written
    labelled = (
        f"Dnešní kontrola tématu ({TOPICALITY_VERSION}) by toto zjištění nepřijala: netýká se "
        "tématu, pro které bylo hledáno (téma: „běžný účet“; zdroj jmenuje: „hypotéka“)."
    )
    assert written.count(labelled) == 1
    assert written.count(f"Dnešní pravidla typů dokumentů ({DOCUMENT_RULES_VERSION})") == 2
    for a in older.accepted[:3]:
        assert f"{a.evidence.quote} [L1] Faktory výběru" in written
    # Labelled, never removed, re-scored or recounted: counts, citations and the seal as stored.
    unlabelled = prose(older)
    assert "Dnešní kontrola tématu" not in unlabelled
    for line in (
        "Přijatá zjištění: 7, citované zdroje:",
        f"Pečeť ověřeného balíčku: {older.sha256}",
    ):
        assert line in written and line in unlabelled
    assert written.count("[L1]") == unlabelled.count("[L1]")
    assert older.verify() and older.model_dump(mode="json") == stored
    # The chapter still says nobody checked the topic when the review was made.
    assert UNCHECKED in written


def test_a_review_merged_under_the_topic_rules_is_never_labelled_again() -> None:
    older, screen = _older_current_account_review()
    judged = _merged_under(older, MERGE_RULES_VERSION)
    written = prose(judged, topics=screen)
    assert "Dnešní kontrola tématu" not in written and "nepřijala" not in written


def _refusing(error: BaseException) -> Callable[[], DeepResearchRequest]:
    def read() -> DeepResearchRequest:
        raise error

    return read


def _invalid_request() -> BaseException:
    try:
        DeepResearchRequest.model_validate({})
    except ValidationError as exc:
        return exc
    raise AssertionError("an empty request validated")


@pytest.mark.parametrize(
    "error",
    [
        BundleNotReady("the stored plan is not this run's request"),
        BundleNotReady("the run has planned nothing"),
        IntegrityError("hash mismatch"),
        ObjectNotFound("gone"),
        ArtifactNotFound("ART-1"),
        _invalid_request(),
        json.JSONDecodeError("Expecting value", "", 0),
        KeyError("request"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_an_older_review_whose_plan_cannot_be_read_is_composed_without_labels_and_says_so(
    error: BaseException,
) -> None:
    """Today's topic rules read the client's names from the review's stored plan. A plan that
    is gone, corrupt or not the run's request refused the whole report with literature
    (cross-review); the labels are what need it, so the chapter is composed without them and
    says, once, that the check could not be applied -- an unlabelled finding is unknown, never
    one that passes."""
    older, screen = _older_current_account_review()
    rules = todays_topic_rules(older, _refusing(error))
    assert rules is TopicRulesUnread.PLAN_UNVERIFIED
    written = prose(older, topics=rules)
    title = "Dnešní kontrolu tématu nebylo možné použít"
    assert written.count(title) == 1
    assert (
        f"Rešerše vznikla před dnešní kontrolou tématu ({TOPICALITY_VERSION}) a tu na ni nebylo "
        "možné použít: uložený plán rešerše, z něhož kontrola čte jména klienta, se nepodařilo "
        "ověřit. Zda by některé z přijatých zjištění dnes kontrolou tématu neprošlo, proto není "
        "známo; že u zjištění není uveden důvod, neznamená, že by jí prošlo."
    ) in written
    # No finding labelled by a check that did not run; the document rules, which need no plan,
    # still name the thesis; counts and seal as stored.
    assert "Dnešní kontrola tématu" not in written
    assert written.count(THESIS_LABEL) == 2
    # The thesis's two findings are a lower bound of what today's rules would not accept,
    # never their total: the chapter said "neprošla: 2" here and "3" when the plan was read
    # (cross-review). Otherwise the unlabelled chapter and the callout.
    bound = "neprošla: nejméně 2 (dnešní kontrolu tématu nebylo možné použít)."
    assert bound in written and "neprošla: 2." not in written
    assert "neprošla: 3." in prose(older, topics=screen)
    unlabelled = prose(older)
    assert written.replace(_words_of_callout(written, title), "") == unlabelled.replace(
        "neprošla: 2.", bound
    )
    assert UNCHECKED in written


def _words_of_callout(written: str, title: str) -> str:
    start = written.index(title)
    return written[start : written.index("\n", written.index("\n", start) + 1) + 1]


def test_a_review_merged_under_the_topic_rules_never_reads_its_plan() -> None:
    older, _screen = _older_current_account_review()
    judged = _merged_under(older, MERGE_RULES_VERSION)
    assert todays_topic_rules(judged, _refusing(AssertionError("read"))) is None
    assert "Dnešní kontrolu tématu nebylo možné použít" not in prose(judged, topics=None)


def test_a_readable_plan_gives_todays_rules_and_a_refused_access_still_refuses() -> None:
    older, _screen = _older_current_account_review()
    request = DeepResearchRequest.model_validate_json(
        (Path(__file__).parent / "fixtures/deep_research_pre_step1/request.json").read_bytes()
    )
    assert todays_topic_rules(older, lambda: request) == topic_screen(
        older.subjects, client_terms=request.client_terms
    )
    # A person without access is not a plan that cannot be read: the report is refused.
    with pytest.raises(ScopeDenied):
        todays_topic_rules(older, _refusing(ScopeDenied()))


def test_a_store_that_failed_to_answer_is_not_a_plan_that_cannot_be_read() -> None:
    """S3's get raises the base StorageError for any failure but a missing object (a timeout,
    throttling). Read as an unverified plan, it stored a newest draft without today's labels,
    servable and approvable, that a retry seconds later would have labelled (cross-review): it
    fails the request instead, and only the store's verdicts on the object leave the labels
    out."""
    older, _screen = _older_current_account_review()
    with pytest.raises(StorageError, match="could not read"):
        todays_topic_rules(older, _refusing(StorageError("could not read k")))
    for verdict in (ObjectNotFound("k"), IntegrityError("hash mismatch")):
        assert todays_topic_rules(older, _refusing(verdict)) is TopicRulesUnread.PLAN_UNVERIFIED


# --------------------------------------------------------------------------- the document (D4)

THESIS_LABEL = (
    f"Dnešní pravidla typů dokumentů ({DOCUMENT_RULES_VERSION}) by toto zjištění nepřijala"
)


def test_an_older_review_names_a_student_thesis_at_composition_among_its_web_sources_only() -> None:
    """A review merged before the document rules is never typed again by the engine; the
    composition types its accepted web sources at USD 0 and changes no acceptance."""
    weak = _single_source()
    stored = weak.model_dump(mode="json")
    written = prose(weak)
    assert "Zjištění, která by dnešní pravidla nepřijala" in written
    assert (
        "Přijatá zjištění, která by podle nich neprošla: 2. Studentská kvalifikační práce podle "
        f"pravidel {DOCUMENT_RULES_VERSION}: 2, ze zdroje L1."
    ) in written
    assert "kontroly tématu" not in written  # no topic screen given: nothing said of the topic
    # After each web finding's quote, the reason in words; never after the approved fact's.
    topic = weak.subjects[0].text
    for a in weak.accepted:
        quoted = f"{a.evidence.quote} [L1] Volba poskytovatele hypotéky (fiktivní práce); "
        quoted += f"hledáno k tématu: {topic}\n"
        if a.evidence.source_kind is SourceKind.WEB_PAGE:
            assert (
                quoted + f"{THESIS_LABEL}: studentská kvalifikační práce (adresa vede do archivu "
                "kvalifikačních prací vse.cz/zp/). Rešerše vznikla před nimi a zjištění přijala; "
                "uvedeno je beze změny."
            ) in written
        else:
            assert quoted in written and quoted + THESIS_LABEL not in written
    assert written.count(THESIS_LABEL) == 2
    assert (
        "Rešerše vznikla před pravidly typů dokumentů; studentské kvalifikační práce mezi jejími "
        f"zdroji rozpoznávají až při sestavení zprávy pravidla {DOCUMENT_RULES_VERSION}"
    ) in written
    # Labelled, never removed, re-scored or recounted, and the bundle as stored.
    typed = prose(_merged_under(weak, MERGE_RULES_VERSION))
    for line in ("Přijatá zjištění: 3, citované zdroje: 1.", "Odmítnutá zjištění: 6."):
        assert line in written and line in typed
    assert written.count("[L1]") == typed.count("[L1]")
    assert weak.verify() and weak.model_dump(mode="json") == stored


def test_a_review_merged_under_the_document_rules_is_never_typed_again() -> None:
    weak = _single_source()
    for merge, rules in (
        (MERGE_RULES_VERSION, DOCUMENT_RULES_VERSION),
        ("aia-merge-9/aia-works-3/aia-document-types-4", "aia-document-types-4"),
    ):
        written = prose(_merged_under(weak, merge))
        assert "Dnešní pravidla" not in written and "nepřijala" not in written
        assert "určeno při sestavení zprávy" not in written
        # The note names the rules the review's own merge applied, and what they leave.
        assert (
            f"Studentské kvalifikační práce rešerše odmítla podle pravidel {rules}, a to jen "
            "podle adresy a názvu zdroje; práci, kterou tato pravidla nepoznají, nevylučuje."
        ) in written
        # An academic host the rules left undetermined may still hold a thesis.
        assert "is.vse.cz: akademická instituce (může jít i o studentskou práci)" in written


def test_an_academic_host_the_rules_leave_undetermined_keeps_its_caveat() -> None:
    data = _single_source().model_dump(mode="json")
    for a in data["accepted"]:
        a["evidence"]["source_url"] = "https://www.vse.cz/fiktivni-anotace"
        a["evidence"]["source_title"] = "Fiktivní anotace"
    written = prose(bundle(accepted=data["accepted"], synthesis=None))
    assert "vse.cz: akademická instituce (může jít i o studentskou práci)" in written
    assert "studentská kvalifikační práce" not in written and "nepřijala" not in written
