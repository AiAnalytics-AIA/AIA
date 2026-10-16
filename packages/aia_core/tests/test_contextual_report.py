"""A literature chapter consumes checked evidence, never the withheld prose."""

from pathlib import Path

import pytest

from aia_core.application.contextual_report import literature_sections
from aia_core.application.report import ReportCompositionRefused
from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.confidence import CONFIDENCE_WEIGHTS_V1
from aia_core.domain.deep_research.contracts import digest
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
    if isinstance(block, (Paragraph, Callout)):
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


def prose(value: EvidenceBundle, origin: OriginKind | None = None) -> str:
    return "\n".join(
        _words(b)
        for s in literature_sections(value, research_run_id="RUN-abc", origin=origin)
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
    assert "Další nedostupný zdroj" in prose(updated)
    assert "not_pursued" not in prose(updated)
    # One notice per reason, its sources together, how to obtain them said once.
    assert (
        "Získání tohoto zdroje nebylo v tomto běhu dokončeno. Původní publikace; Další "
        "nedostupný zdroj. Doplnit z knihovny."
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
    # Credibility is the domain's, said as that, never as relevance.
    assert "akademická instituce (může jít i o studentskou práci)" in written
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


def test_counts_say_how_much_was_captured_against_how_little_was_cited() -> None:
    written = prose(_single_source())
    # As "label: number", so no count reads as bad Czech ("z 1 citovaných zdrojů" did).
    assert "Přijatá zjištění: 3, citované zdroje: 1." in written
    assert "Důvody odmítnutí:" in written
    assert "doména zdroje má nízké nebo neurčené hodnocení (1krát)" in written
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
    assert marker not in written and "další nedoložený podklad" in written
