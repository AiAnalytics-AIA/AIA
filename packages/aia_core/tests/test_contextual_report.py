"""A literature chapter consumes checked evidence, never the withheld prose."""

from pathlib import Path

import pytest

from aia_core.application.contextual_report import literature_sections
from aia_core.application.report import ReportCompositionRefused
from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.confidence import CONFIDENCE_WEIGHTS_V1
from aia_core.domain.deep_research.contracts import (
    ClientTerm,
    ResearchSubject,
    SourceKind,
    SubjectKind,
    digest,
    subject_key,
)
from aia_core.domain.deep_research.document_types import DOCUMENT_RULES_VERSION
from aia_core.domain.deep_research.merge import MERGE_RULES_VERSION
from aia_core.domain.deep_research.topicality import (
    TOPICALITY_VERSION,
    TopicScreen,
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
    topics: TopicScreen | None = None,
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
