"""``tools/dr_accuracy.py``: check, pin and score, round trip, and every refusal.

FICTIONAL throughout: the fixture's invented publishers on ``.example`` hosts, 2091.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.deep_research.accuracy import AccuracyReport, TargetStatus
from aia_core.domain.deep_research.bundle import TrackRecord, seal_bundle
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    BriefDigest,
    Channel,
    DeepResearchRequest,
    EvidenceItem,
    EvidenceType,
    FrozenKnowledge,
    RecommendedUse,
    ResearchSubject,
    RetrievalMode,
    SourceKind,
    StopReason,
    SubjectKind,
    TrackStatus,
    subject_key,
)
from aia_core.domain.deep_research.merge import AcceptedEvidence, RespondentUse, ScoreRecord
from aia_core.domain.deep_research.truth_set import load_pins, load_truth_set
from aia_core.domain.residency import DataClass

FIXTURES = Path(__file__).parent / "fixtures" / "deep_research_accuracy"
TRUTH = FIXTURES / "fictional_truth_set.json"
PINS = FIXTURES / "pins.json"
ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "docs" / "evaluation" / "deep-research" / "czech-public-facts.template.json"


@pytest.fixture(scope="module")
def tool(tool_loader: Any) -> Any:
    return tool_loader("dr_accuracy")


def _subject(text: str) -> ResearchSubject:
    return ResearchSubject(
        key=subject_key(SubjectKind.QUESTION, text),
        kind=SubjectKind.QUESTION,
        text=text,
        origin="truth_set",
    )


def _bundle_json(preset: str, claims: dict[str, str]) -> str:
    """A sealed bundle answering the fixture's questions with ``claims`` (fact id -> claim)."""
    truth = load_truth_set(TRUTH.read_text("utf-8"))
    subjects = {f.fact_id: _subject(f.question or "") for f in truth.facts}
    accepted = []
    for n, (fact_id, claim) in enumerate(claims.items(), 1):
        s = subjects[fact_id]
        accepted.append(
            AcceptedEvidence(
                evidence=EvidenceItem(
                    evidence_id=f"EV-{n:016x}",
                    track_id="DRT-W-" + s.key,
                    subject_key=s.key,
                    channel=Channel.WEB,
                    source_kind=SourceKind.WEB_PAGE,
                    source_ref="SNP-" + "2" * 24,
                    source_url="https://statistika-fikce.example/x",
                    source_title="t",
                    claim=claim,
                    quote=claim,
                    quote_span=(0, len(claim)),
                    evidence_type=EvidenceType.OFFICIAL_REPORT,
                    source_date=None,
                    geography="CZ",
                    population="",
                    topics=(),
                    data_class=DataClass.CLASS_C_INTERNAL,
                    agent_outcome_overlap=False,
                    agent_recommended_use=RecommendedUse.CONTEXT_ONLY,
                    agent_source_quality=0.5,
                ),
                score=ScoreRecord(
                    source_class="OFFICIAL_STATISTICS",
                    base=0.95,
                    age="recent",
                    age_adjustment=0.0,
                    score=0.95,
                    geography="CZ",
                    table_version="t",
                ),
                respondent_use=RespondentUse.ELIGIBLE,
                respondent_exclusion=None,
                merged_ids=(),
                confirmations=(),
                confidence=0.7,
                verifier_reason="ok",
            )
        )
    request = DeepResearchRequest(
        harness_version=HARNESS_VERSION,
        design_revision_id="REV-1",
        design_revision=1,
        preset=preset,
        channels=(Channel.WEB,),
        brief=BriefDigest(title="t", goal="g", decision_use="d", briefing=""),
        subjects=tuple(subjects.values()),
        questionnaire=(),
        knowledge=FrozenKnowledge(items=(), omitted_ids=(), retrieval_limit=200),
        client_terms=(),
    )
    tracks = tuple(
        TrackRecord(
            track_id="DRT-W-" + s.key,
            subject_key=s.key,
            channel=Channel.WEB,
            fingerprint="b" * 64,
            status=TrackStatus.COMPLETED,
            stop_reason=StopReason.SATURATED,
            detail="",
            reused=False,
            artifact_id=None,
            retrieval_mode=RetrievalMode.RECORDED,
            queries=(),
            snapshot_ids=(),
            evidence_ids=(),
            quarantined_ids=(),
            model_requests=0,
            search_calls=0,
            fetches=0,
            credits=0,
            model_cost_usd=0.0,
            tool_cost_usd=0.0,
        )
        for s in subjects.values()
    )
    bundle = seal_bundle(
        request=request,
        subjects=tuple(subjects.values()),
        versions={},
        tracks=tracks,
        accepted=accepted,
        quarantined=(),
        snapshots=(),
        synthesis=None,
        fictional_client=True,
        counts={},
        spend_usd={},
    )
    return bundle.model_dump_json()


DEEP_CLAIMS = {
    "pop-01": "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel.",
    "price-02": "Inflace v Česku v roce 2091 byla 2,5 %.",
    "cons-01": "V roce 2091 vlastnilo fiktivní přístroj 450 domácností v Česku.",
}


def test_check_reports_the_hash_and_what_blocks_a_pin(tool: Any, capsys: Any) -> None:
    assert tool.main(["check", "--truth", str(TEMPLATE)]) == 0
    out = capsys.readouterr().out
    assert "cz-public-facts-1: 50 facts" in out
    assert "unverified: 50" in out and "unscorable: 50" in out


def test_pin_records_once_and_refuses_a_changed_set(tool: Any, tmp_path: Path, capsys: Any) -> None:
    truth = tmp_path / "set.json"
    shutil.copy(TRUTH, truth)
    pins = tmp_path / "pins.json"
    args = ["pin", "--truth", str(truth), "--pins", str(pins), "--by", "tester"]
    assert tool.main([*args, "--at", "2026-10-06"]) == 0
    manifest = load_pins(pins.read_text("utf-8"))
    (pin,) = manifest.pins
    assert pin.sha256 == load_truth_set(TRUTH.read_text("utf-8")).sha256()
    assert pin.path == truth.resolve().as_posix()
    assert tool.main(args) == 0
    assert "already pinned" in capsys.readouterr().out
    data = json.loads(truth.read_text("utf-8"))
    data["facts"][0]["expected"]["value_text"] = "10 451"
    truth.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert tool.main(args) == 2
    assert "new set_id" in capsys.readouterr().err


def test_pin_refuses_the_unverified_template(tool: Any, tmp_path: Path, capsys: Any) -> None:
    pins = tmp_path / "pins.json"
    argv = ["pin", "--truth", str(TEMPLATE), "--pins", str(pins), "--by", "x"]
    assert tool.main(argv) == 2
    assert "not verified" in capsys.readouterr().err
    assert not pins.exists()


def test_score_round_trip_against_the_committed_fixture_pins(
    tool: Any, tmp_path: Path, capsys: Any
) -> None:
    run = tmp_path / "bundle.json"
    run.write_text(_bundle_json("DEEP", DEEP_CLAIMS), encoding="utf-8")
    out = tmp_path / "report.json"
    argv = ["score", "--truth", str(TRUTH), "--pins", str(PINS), "--run", str(run)]
    assert tool.main([*argv, "--out", str(out), "--preset", "DEEP", "--allow-unverified"]) == 0
    printed = capsys.readouterr().out
    report = AccuracyReport.model_validate_json(out.read_text("utf-8"))
    deep = report.presets["DEEP"]
    assert (deep.exact, deep.false_acceptances, deep.acquisition_gaps) == (2, 1, None)
    status = {(c.target_id, c.preset): c.status for c in report.targets}
    assert status[("zero-false-acceptances", "DEEP")] is TargetStatus.FAIL
    assert status[("exact-accuracy-deep", "DEEP")] is TargetStatus.FAIL
    assert "FALSE ACCEPTANCE" in printed and "cons-01" in printed
    assert "acquisition gaps not reported" in printed


def test_score_refuses_without_the_unverified_allowance(
    tool: Any, tmp_path: Path, capsys: Any
) -> None:
    run = tmp_path / "bundle.json"
    run.write_text(_bundle_json("DEEP", DEEP_CLAIMS), encoding="utf-8")
    argv = ["score", "--truth", str(TRUTH), "--pins", str(PINS), "--run", str(run)]
    assert tool.main([*argv, "--out", str(tmp_path / "r.json")]) == 2
    assert "not verified" in capsys.readouterr().err
    assert not (tmp_path / "r.json").exists()


def test_score_refuses_uncommitted_pins_unless_fictional_and_allowed(
    tool: Any, tmp_path: Path, capsys: Any
) -> None:
    pins = tmp_path / "pins.json"
    shutil.copy(PINS, pins)
    run = tmp_path / "bundle.json"
    run.write_text(_bundle_json("DEEP", DEEP_CLAIMS), encoding="utf-8")
    argv = ["score", "--truth", str(TRUTH), "--pins", str(pins), "--run", str(run)]
    argv += ["--out", str(tmp_path / "r.json"), "--allow-unverified"]
    assert tool.main(argv) == 2
    assert "not committed" in capsys.readouterr().err
    assert tool.main([*argv, "--allow-uncommitted-pins"]) == 0
    real = ["score", "--truth", str(TEMPLATE), "--pins", str(pins), "--run", str(run)]
    assert tool.main([*real, "--out", str(tmp_path / "x.json"), "--allow-uncommitted-pins"]) == 2
    assert "fictional sets only" in capsys.readouterr().err


def test_score_refuses_a_run_of_another_preset(tool: Any, tmp_path: Path, capsys: Any) -> None:
    run = tmp_path / "bundle.json"
    run.write_text(_bundle_json("STANDARD", DEEP_CLAIMS), encoding="utf-8")
    argv = ["score", "--truth", str(TRUTH), "--pins", str(PINS), "--run", str(run)]
    argv += ["--out", str(tmp_path / "r.json"), "--allow-unverified", "--preset", "DEEP"]
    assert tool.main(argv) == 2
    assert "not of preset DEEP" in capsys.readouterr().err


def test_score_refuses_a_tampered_bundle_and_an_unknown_file(
    tool: Any, tmp_path: Path, capsys: Any
) -> None:
    data = json.loads(_bundle_json("DEEP", DEEP_CLAIMS))
    data["preset"] = "QUICK"
    run = tmp_path / "bundle.json"
    run.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    argv = ["score", "--truth", str(TRUTH), "--pins", str(PINS), "--out", str(tmp_path / "r")]
    assert tool.main([*argv, "--run", str(run), "--allow-unverified"]) == 2
    assert "seal" in capsys.readouterr().err
    other = tmp_path / "other.json"
    other.write_text('{"kind": "something_else"}', encoding="utf-8")
    assert tool.main([*argv, "--run", str(other), "--allow-unverified"]) == 2
    assert "neither a bundle nor a run record" in capsys.readouterr().err


def test_score_reads_a_run_record_too(tool: Any, tmp_path: Path) -> None:
    truth = load_truth_set(TRUTH.read_text("utf-8"))
    fact = truth.facts[0]
    subject = _subject(fact.question or "")
    record = {
        "kind": "deep_research_accuracy_run",
        "version": "aia-dr-accuracy-run-1",
        "run_id": "live-1",
        "preset": "STANDARD",
        "origins": ["LIVE_RETRIEVAL"],
        "fictional_client": True,
        "subjects": {subject.key: subject.text},
        "findings": [
            {
                "evidence_id": "EV-0000000000000001",
                "subject_key": subject.key,
                "claim": "Česko mělo 10 450 tis. obyvatel.",
                "quote": "[OBY01!CZ/2091] Česko | 2091 = 10 450",
                "source_ref": "SNP-" + "3" * 24,
                "source_url": "https://statistika-fikce.example/data/OBY01",
                "measures": [
                    {
                        "value": 10450,
                        "scale": 1000,
                        "population": "PERSONS",
                        "geography": "CZ",
                        "period": "2091",
                    }
                ],
                "measures_from": "stated",
                "grounding": "dataset_cell",
                "cell_locator": "OBY01!CZ/2091",
                "provenance": "primary",
            }
        ],
        "reports_provenance": True,
        "reports_acquisition_gaps": True,
        "acquisition_gaps": [],
    }
    run = tmp_path / "run.json"
    run.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "report.json"
    argv = ["score", "--truth", str(TRUTH), "--pins", str(PINS), "--run", str(run)]
    assert tool.main([*argv, "--out", str(out), "--allow-unverified"]) == 0
    m = AccuracyReport.model_validate_json(out.read_text("utf-8")).presets["STANDARD"]
    assert (m.exact, m.primary_answered, m.cell_grounded_answered, m.acquisition_gaps) == (
        1,
        1,
        1,
        0,
    )
