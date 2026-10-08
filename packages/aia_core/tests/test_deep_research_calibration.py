"""The verifier's calibration on a gold set (plan ``deep-research-web-search.md`` chunk 48).

The gold set is fictional, pinned by its hash, shaped exactly as the verifier is shown a
candidate, and its ``superseded`` rows are ones code's own rules supersede. The rates
are the ones code's application of a verdict makes: a bad row judged supported is a
miss, a good row set aside (or not judged) a false alarm. Recorded answers prove the
tooling only; every run records ``NOT_CALIBRATED`` whatever a report says.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.deep_research.agents import AGENT_IDS, AgentRole
from aia_core.domain.deep_research.calibration import (
    PROPOSED_THRESHOLDS,
    VERIFIER_CALIBRATION,
    CalibrationRefused,
    CalibrationStatus,
    GoldItem,
    GoldSet,
    ItemOutcome,
    VerifierAnswers,
    calibrate,
    render_calibration,
    wilson_upper,
)
from aia_core.domain.deep_research.contracts import EvidenceItem
from aia_core.domain.deep_research.merge import Candidate
from aia_core.domain.deep_research.tracing import TraceRecord
from aia_core.domain.deep_research.triangulation import ConflictTolerance
from aia_core.domain.deep_research.verification import _newer, verifier_item
from aia_core.domain.deep_research.verifier import (
    VERIFIER_CONTRACT_VERSION,
    VERIFIER_PROMPT_VERSION,
    ClaimJudgement,
    ClaimVerdict,
)

ROOT = Path(__file__).resolve().parents[3]
GOLD_PATH = Path(__file__).parent / "fixtures" / "deep_research_verifier" / "gold.json"
#: The gold set's hash. A changed row is a new set: give it a new set_id, never re-pin this.
GOLD_SHA256 = "4f09c32e99e2be24969888d675c3bb3ea612a12ae65041a5dd93aafc2bf0efa4"

V = ClaimVerdict


@pytest.fixture(scope="module")
def gold() -> GoldSet:
    return GoldSet.model_validate_json(GOLD_PATH.read_text(encoding="utf-8"))


def _answers(
    gold: GoldSet,
    said: dict[str, ClaimVerdict | None],
    *,
    mode: str = "RECORDED",
    **override: Any,
) -> VerifierAnswers:
    """Answers that say ``said[id]`` where given, the expected verdict elsewhere."""
    judgements = []
    for item in gold.items:
        verdict = said.get(item.evidence_id, item.expected)
        if verdict is None:
            continue
        judgements.append(
            ClaimJudgement(
                evidence_id=item.evidence_id,
                verdict=verdict,
                attacks=[],
                superseded_by=item.related[-1].evidence_id if verdict is V.SUPERSEDED else None,
                search=None,
                reason="scripted",
            )
        )
    fields: dict[str, Any] = {
        "kind": "deep_research_verifier_answers",
        "set_id": gold.set_id,
        "set_sha256": gold.sha256(),
        "mode": mode,
        "agent_id": AGENT_IDS[AgentRole.INDEPENDENT_VERIFIER],
        "prompt_version": VERIFIER_PROMPT_VERSION,
        "contract_version": VERIFIER_CONTRACT_VERSION,
        "model": "a-live-model" if mode == "LIVE" else None,
        "recorded_at": date(2026, 10, 8),
        "judgements": judgements,
    }
    return VerifierAnswers.model_validate({**fields, **override})


# --------------------------------------------------------------------------- #
# The gold set
# --------------------------------------------------------------------------- #


def test_the_gold_set_is_pinned_fictional_and_has_every_verdict(gold: GoldSet) -> None:
    assert gold.sha256() == GOLD_SHA256
    assert gold.fictional is True
    counts = gold.by_verdict()
    assert counts == {"supported": 12, "overstated": 6, "unsupported": 6, "superseded": 4}
    # One false alarm must be able to stay under the proposed threshold (< 0.10).
    assert 1 / counts["supported"] < PROPOSED_THRESHOLDS.max_false_alarm_rate
    # Fiction is visible: every period is a year no figure has yet (2089 on).
    for item in gold.items:
        for m in item.measures:
            assert m.period is None or int(m.period.lstrip("Y")[:4]) >= 2089


def test_a_row_is_shown_exactly_as_the_verifier_is_shown_a_candidate(gold: GoldSet) -> None:
    for item in gold.items:
        evidence = EvidenceItem.model_construct(
            evidence_id=item.evidence_id,
            claim=item.claim,
            quote=item.quote,
            measures=item.measures,
            source_title=item.source.title,
            source_date=item.source.date,
        )
        related = [
            Candidate.model_construct(
                evidence=EvidenceItem.model_construct(
                    evidence_id=r.evidence_id,
                    claim=r.claim,
                    measures=r.measures,
                    source_date=r.date,
                )
            )
            for r in item.related
        ]
        trace = TraceRecord.model_construct(
            publisher_name=item.source.publisher,
            status=item.source.primary,
            cited=tuple(item.source.cited),
        )
        shown = verifier_item(
            Candidate.model_construct(evidence=evidence),
            excerpt=item.excerpt,
            trace=trace,
            related=related,
        )
        assert item.shown() == shown


def test_code_supersedes_every_superseded_row_and_no_supported_one(gold: GoldSet) -> None:
    """A gold verdict code would refuse would score the verifier against the wrong answer."""

    def day(text: str | None) -> date | None:
        return date.fromisoformat(text) if text else None

    for item in gold.items:
        superseded = bool(item.measures) and all(
            any(
                _newer(m, n, day(item.source.date), day(r.date), ConflictTolerance()) is not None
                for r in item.related
                for n in r.measures
            )
            for m in item.measures
        )
        assert superseded is (item.expected is V.SUPERSEDED), item.evidence_id


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"quote": "není ve výňatku"}, "the quote is not in its excerpt"),
        ({"expected": "superseded", "related": []}, "superseded needs the newer figure"),
    ],
)
def test_a_malformed_row_is_refused(gold: GoldSet, change: dict[str, Any], message: str) -> None:
    row = gold.items[0].model_dump(mode="json")
    with pytest.raises(ValidationError, match=message):
        GoldItem.model_validate({**row, **change})


def test_a_set_must_be_fictional_and_name_each_row_once(gold: GoldSet) -> None:
    doc = gold.model_dump(mode="json")
    with pytest.raises(ValidationError):
        GoldSet.model_validate({**doc, "fictional": False})
    with pytest.raises(ValidationError, match="twice"):
        GoldSet.model_validate({**doc, "items": [*doc["items"], doc["items"][0]]})


# --------------------------------------------------------------------------- #
# The rates
# --------------------------------------------------------------------------- #


def test_a_perfect_recorded_verifier_proves_the_tooling_only(gold: GoldSet) -> None:
    report = calibrate(gold, _answers(gold, {}))
    assert (report.misses, report.false_alarms, report.agreement) == (0, 0, 1.0)
    assert report.status is CalibrationStatus.TOOLING_ONLY
    assert report.recorded_calibration == VERIFIER_CALIBRATION == "NOT_CALIBRATED"
    assert "proves the tooling, not a verifier" in render_calibration(report)


def test_each_outcome_is_what_code_does_with_the_verdict(gold: GoldSet) -> None:
    report = calibrate(
        gold,
        _answers(
            gold,
            {
                "G-O01": V.SUPPORTED,  # a bad row accepted: a miss
                "G-U01": V.OVERSTATED,  # set aside under another verdict: not a miss
                "G-X01": None,  # not judged: set aside as unverified
                "G-S01": V.UNSUPPORTED,  # a good row set aside: a false alarm
                "G-S02": None,  # a good row not judged: also lost
            },
        ),
    )
    outcome = {r.evidence_id: r.outcome for r in report.rows}
    assert outcome["G-O01"] is ItemOutcome.MISS
    assert outcome["G-U01"] is ItemOutcome.OTHER_REJECTION
    assert outcome["G-X01"] is ItemOutcome.UNJUDGED_REJECTION
    assert outcome["G-S01"] is outcome["G-S02"] is ItemOutcome.FALSE_ALARM
    assert (report.good, report.bad, report.misses, report.false_alarms) == (12, 16, 1, 2)
    assert report.miss_rate == 1 / 16 and report.false_alarm_rate == 2 / 12
    assert report.unjudged == 2 and report.agreement == 23 / 28
    assert report.confusion["overstated"] == {"overstated": 5, "supported": 1}
    assert report.confusion["supported"] == {"none": 1, "supported": 10, "unsupported": 1}


def test_live_answers_meet_or_miss_the_thresholds_and_change_nothing_recorded(
    gold: GoldSet,
) -> None:
    one_each = calibrate(
        gold, _answers(gold, {"G-O02": V.SUPPORTED, "G-S12": V.OVERSTATED}, mode="LIVE")
    )
    # 1/16 = 0.0625 < 0.15 and 1/12 = 0.083 < 0.10.
    assert one_each.status is CalibrationStatus.MEETS_THRESHOLDS
    assert one_each.thresholds.status == "PROPOSED"
    assert one_each.recorded_calibration == "NOT_CALIBRATED"
    two_alarms = calibrate(
        gold, _answers(gold, {"G-S11": V.OVERSTATED, "G-S12": V.OVERSTATED}, mode="LIVE")
    )
    assert two_alarms.status is CalibrationStatus.MISSES_THRESHOLDS
    three_misses = calibrate(
        gold,
        _answers(gold, dict.fromkeys(("G-O01", "G-O02", "G-U03"), V.SUPPORTED), mode="LIVE"),
    )
    assert (
        three_misses.miss_rate == 3 / 16
        and three_misses.status is CalibrationStatus.MISSES_THRESHOLDS
    )


def test_the_upper_bound_shows_how_little_a_small_set_proves() -> None:
    assert wilson_upper(0, 12) == pytest.approx(0.2425, abs=1e-4)
    assert wilson_upper(1, 16) == pytest.approx(0.2833, abs=1e-4)
    assert wilson_upper(0, 1000) < 0.004
    with pytest.raises(ValueError):
        wilson_upper(0, 0)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"set_sha256": "0" * 64}, "another gold set"),
        ({"set_id": "another-set"}, "another gold set"),
        ({"prompt_version": "0"}, "prompt 0"),
        ({"contract_version": "verification-1"}, "contract verification-1"),
        ({"agent_id": "aia.deep_research.verifier"}, "aia.deep_research.verifier"),
    ],
)
def test_answers_for_another_set_or_verifier_are_refused(
    gold: GoldSet, override: dict[str, Any], message: str
) -> None:
    with pytest.raises(CalibrationRefused, match=message):
        calibrate(gold, _answers(gold, {}, **override))


def test_a_judgement_twice_or_of_an_unknown_row_is_refused(gold: GoldSet) -> None:
    answers = _answers(gold, {})
    twice = answers.model_copy(update={"judgements": [*answers.judgements, answers.judgements[0]]})
    with pytest.raises(CalibrationRefused, match="judged twice"):
        calibrate(gold, twice)
    stranger = answers.judgements[0].model_copy(update={"evidence_id": "G-NONE"})
    with pytest.raises(CalibrationRefused, match="does not have"):
        calibrate(gold, answers.model_copy(update={"judgements": [stranger]}))


def test_live_answers_name_their_model_and_recorded_ones_none(gold: GoldSet) -> None:
    with pytest.raises(ValidationError, match="name their model"):
        _answers(gold, {}, mode="LIVE", model=None)
    with pytest.raises(ValidationError, match="name their model"):
        _answers(gold, {}, model="a-model")


# --------------------------------------------------------------------------- #
# The runner
# --------------------------------------------------------------------------- #


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "dr_accuracy.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_runner_writes_the_report_and_says_what_recorded_answers_prove(
    gold: GoldSet, tmp_path: Path
) -> None:
    answers = tmp_path / "answers.json"
    answers.write_text(_answers(gold, {"G-O01": V.SUPPORTED}).model_dump_json(), encoding="utf-8")
    out = tmp_path / "report.json"
    done = _run("calibrate", "--gold", str(GOLD_PATH), "--answers", str(answers), "--out", str(out))
    assert done.returncode == 0, done.stderr
    assert "miss 1/16" in done.stdout and "status TOOLING_ONLY" in done.stdout
    assert "the runs record NOT_CALIBRATED" in done.stdout
    report = json.loads(out.read_text(encoding="utf-8"))
    assert (report["misses"], report["status"]) == (1, "TOOLING_ONLY")


def test_the_runner_refuses_answers_to_another_version_of_the_set(
    gold: GoldSet, tmp_path: Path
) -> None:
    answers = tmp_path / "answers.json"
    answers.write_text(_answers(gold, {}, set_sha256="0" * 64).model_dump_json(), encoding="utf-8")
    done = _run(
        "calibrate", "--gold", str(GOLD_PATH), "--answers", str(answers),
        "--out", str(tmp_path / "r.json"),
    )  # fmt: skip
    assert done.returncode == 2 and "another gold set" in done.stderr
    assert not (tmp_path / "r.json").exists()
