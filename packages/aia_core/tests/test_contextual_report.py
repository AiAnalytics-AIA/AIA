"""A literature chapter consumes checked evidence, never the withheld prose."""

from pathlib import Path

import pytest

from aia_core.application.contextual_report import literature_sections
from aia_core.application.report import ReportCompositionRefused
from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.confidence import CONFIDENCE_WEIGHTS_V1
from aia_core.domain.deep_research.contracts import digest
from aia_core.domain.report.model import Heading, Link, Paragraph, Text


def bundle(**updates: object) -> EvidenceBundle:
    path = Path(__file__).parent / "fixtures/deep_research_pre_step1/bundle.json"
    original = EvidenceBundle.model_validate_json(path.read_bytes())
    data = {**original.model_dump(mode="json"), **updates, "sha256": ""}
    data = EvidenceBundle.model_validate(data).model_dump(mode="json")
    data["sha256"] = digest(data)
    return EvidenceBundle.model_validate(data)


def prose(value: EvidenceBundle) -> str:
    return "\n".join(
        "".join(i.text for i in b.content if isinstance(i, (Text, Link)))
        for s in literature_sections(value, research_run_id="RUN-abc")
        for b in s.blocks
        if isinstance(b, Paragraph)
    )


def test_checked_synthesis_has_separate_sources_limits_and_fixture_disclosure() -> None:
    original = bundle()
    written = prose(original)
    for finding in original.synthesis.check.findings:
        assert finding.text in written
    for excluded in original.synthesis.check.excluded:
        assert excluded.text not in written
    assert "[L1]" in written and "[L2]" in written
    assert "2026-09-01" in written
    assert "nahraných testovacích výměn" in written
    assert "nikoli o systematický přehled" in written
    assert "Syntetické odpovědi" in written
    assert original.sha256 in written
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
    written = prose(bundle(accepted=accepted, synthesis=None))
    assert "Podíl odpovědí: 25 % [L1]" in written
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
    updated = bundle(synthesis=synthesis)
    sections = literature_sections(updated, research_run_id="RUN-abc")
    assert not any(
        isinstance(block, Heading) and block.text == updated.subjects[0].text
        for section in sections
        for block in section.blocks
    )
    assert updated.subjects[0].text in prose(updated)
    assert prose(updated).count("Chybí původní studie") == 1
    assert "not_pursued" not in prose(updated)
    assert "Získání tohoto zdroje nebylo v tomto běhu dokončeno. Doplnit z knihovny." in prose(
        updated
    )
