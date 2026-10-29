"""Evidence-integrity 2a: a run's QC, EXACT against the unit's own ``qc.kontrola``.

The fixtures are the unit's unmodified ``kontrola`` run on fictional runs
(``tools/run_qc_capture.py``), pinned by SHA-256 in ``fixtures/run_qc/index.json``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.fieldwork import (
    DataOrigin,
    FieldworkDataset,
    FieldworkRespondent,
    FieldworkSource,
    InvalidDataset,
)
from aia_core.domain.research_design import compile_design
from aia_core.domain.run_qc import (
    NOT_APPLICABLE,
    UNIT_THRESHOLDS,
    QcCheck,
    QcLevel,
    QcNotReadable,
    QcQuestion,
    dataset_qc,
    run_qc,
)

FIXTURES = Path(__file__).parent / "fixtures" / "run_qc"
UNIT_QC = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app" / "qc.py"
#: The unit's metric keys whose checks are 2b's (demographics) or not applicable in AIA.
NOT_PORTED_KEYS = {"chybovost", "cramer_v", "rozpeti_prumeru_segmentu"}


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_fixtures_are_the_ones_captured_from_the_units_qc() -> None:
    index = _load("index.json")
    for name, sha in index["fixtures"].items():
        assert _sha(FIXTURES / name) == sha, name
    assert _sha(UNIT_QC) == index["unit_source"]["qc.py"]


CASES = {c["id"]: c for c in _load("cases.json")}
UNIT = {r["id"]: r["result"] for r in _load("kontrola.json")}


def _ours(case: dict[str, Any]) -> Any:
    questions = [QcQuestion(o["id"], o["typ"], tuple(o["volby"])) for o in case["otazky"]]
    return run_qc(questions, case["rows"], dry=case["mode"] == "dry", ablation=case["ablation"])


def _unit_metrics(metrics: Any) -> Any:
    """The unit's metrics without what 2a does not port; its NaN (``"NaN"``) read as ``None``."""
    if isinstance(metrics, dict):
        return {k: _unit_metrics(v) for k, v in metrics.items() if k not in NOT_PORTED_KEYS}
    return None if metrics == "NaN" else metrics


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_a_runs_qc_is_the_units_finding_for_finding(case_id: str) -> None:
    unit, ours = UNIT[case_id], _ours(CASES[case_id])
    # Each finding is the unit's: its level, place and value, and the check the unit's own
    # sentence names (CHECK_OF_TEXT), in the unit's order.
    assert [(f.level.value, f.where, f.check, f.value) for f in ours.findings] == [
        (f["uroven"], f["kde"], CHECK_OF_TEXT[f["nalez"]], f["hodnota"]) for f in unit["nalezy"]
    ]
    assert ours.level.value == unit["uroven"]
    assert ours.verdict == unit["verdikt"]


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_a_runs_qc_metrics_are_the_units_key_for_key(case_id: str) -> None:
    assert dict(_ours(CASES[case_id]).metrics) == _unit_metrics(UNIT[case_id]["metriky"])


#: The unit's sentence for each ported check (``qc.py``), to which each finding's id is pinned.
#: The domain carries the id alone; its words are the screen's.
CHECK_OF_TEXT = {
    "vic nez 20 % respondentu neodpovedelo": QcCheck.MISSING_ANSWERS,
    "temer nikdo neodpovedel 'nevim' — nerealne rozhodne": QcCheck.DONT_KNOW_RARE,
    "prilis mnoho 'nevim' — otazka je nejasna": QcCheck.DONT_KNOW_FREQUENT,
    "jedna kategorie pohltila skoro vse": QcCheck.CONCENTRATED,
    "temer nulovy rozptyl na skale": QcCheck.FLAT_SCALE,
    "synteticke verbatimy se opakuji — model recykluje formulace": (QcCheck.REPEATED_OPEN_ANSWERS),
    "cast respondentu odpovida na vsechny skaly stejne": QcCheck.STRAIGHT_LINING,
    "hodne respondentu ma uplne stejnou sadu odpovedi i pres velky prostor odpovedi": (
        QcCheck.IDENTICAL_VECTORS
    ),
    "efekt plne persony nebyl v tomto behu overen ablation testem": (
        QcCheck.PERSONA_EFFECT_UNVERIFIED
    ),
}


def test_the_fixtures_reach_every_ported_check() -> None:
    reached = {f.check for c in CASES.values() for f in _ours(c).findings}
    assert reached == set(QcCheck) - set(NOT_APPLICABLE)
    assert {_ours(c).level for c in CASES.values()} == {QcLevel.VAROVANI, QcLevel.KRITICKE}


def test_what_has_no_input_in_aia_is_named_never_passed() -> None:
    qc = _ours(CASES["clean"])
    assert set(qc.not_applicable) == set(NOT_APPLICABLE)
    assert all(qc.not_applicable.values())
    assert not {f.check for f in qc.findings} & set(NOT_APPLICABLE)


def test_a_run_with_no_respondent_is_refused() -> None:
    with pytest.raises(QcNotReadable, match="no respondent"):
        run_qc([QcQuestion("q", "skala")], [], dry=False, ablation=False)


def test_the_thresholds_are_a_parameter_and_recorded() -> None:
    case = CASES["straight_liners_below"]
    stricter = replace(UNIT_THRESHOLDS, straight_lining_max=0.0)
    questions = [QcQuestion(o["id"], o["typ"], tuple(o["volby"])) for o in case["otazky"]]
    qc = run_qc(questions, case["rows"], dry=False, ablation=False, thresholds=stricter)
    assert QcCheck.STRAIGHT_LINING in {f.check for f in qc.findings}
    assert qc.thresholds is stricter
    assert QcCheck.STRAIGHT_LINING not in {f.check for f in _ours(case).findings}


def test_the_missing_answers_check_reads_the_threshold_in_force() -> None:
    rows: list[dict[str, Any]] = [{"q": None}] + [{"q": "Ano"}] * 6  # 14.3 % not answered
    question = [QcQuestion("q", "vyber", ("Ano", "Ne"))]
    lower = replace(UNIT_THRESHOLDS, missing_max=0.10)
    (finding,) = [
        f
        for f in run_qc(question, rows, dry=True, ablation=False, thresholds=lower).findings
        if f.check is QcCheck.MISSING_ANSWERS
    ]
    assert finding.value == 0.143
    assert not [
        f
        for f in run_qc(question, rows, dry=True, ablation=False).findings
        if f.check is QcCheck.MISSING_ANSWERS
    ]


@pytest.mark.parametrize("bad", ["4", True])
def test_a_scale_answer_that_is_not_a_number_is_refused_by_name(bad: object) -> None:
    rows: list[dict[str, Any]] = [{"s": 3}, {"s": bad}]
    with pytest.raises(TypeError, match="s: a scale answer must be a number"):
        run_qc([QcQuestion("s", "skala")], rows, dry=True, ablation=False)


def test_a_stored_dataset_is_checked_through_its_specification() -> None:
    """Straight-lining reads the scale questions alone, the unit's scope (F-RQC1-1): a tracked
    set rated with one value is not a straight-liner here."""
    spec, problems = compile_design(
        {
            "title": "Ranní nápoj",
            "n": 20,
            "sections": [
                {
                    "type": "questions",
                    "questions": [
                        {"id": f"q{k}", "text": f"Otázka {k}?", "typ": "skala", "skala": [1, 5]}
                        for k in (1, 2, 3)
                    ],
                },
                {
                    "type": "object_battery",
                    "title": "Nápoje",
                    "object_family": "nápoje",
                    "objects": ["Káva", "Čaj", "Kakao"],
                    "object_question": "Jak hodnotíte {object}?",
                    "scale": [1, 10],
                },
            ],
        }
    )
    assert spec is not None, problems
    ratings = {b.question_id(o): 7 for b in spec.batteries for o in b.objects}
    rows = [{"q1": 3, "q2": 3, "q3": 3, **ratings}, {"q1": 1, "q2": 4, "q3": 5, **ratings}]
    dataset = FieldworkDataset(
        dataset_version="1",
        source=FieldworkSource.AI_RUNTIME,
        origin=DataOrigin.SYNTHETIC_AI_FICTIONAL,
        spec_fingerprint=spec.fingerprint(),
        seed=1,
        generator="test",
        respondents=tuple(
            FieldworkRespondent(respondent_id=f"r{k}", donor_id=f"d{k}", weight=1.0, answers=a)
            for k, a in enumerate(rows)
        ),
    )
    qc = dataset_qc(spec, dataset, dry=True)
    assert qc.metrics["straightlining"] == 0.5
    assert QcCheck.STRAIGHT_LINING in {f.check for f in qc.findings}
    per_question = qc.metrics["per_otazku"]
    assert isinstance(per_question, dict)
    assert set(per_question) == {"q1", "q2", "q3"}


def _questions_design(**question: Any) -> dict[str, Any]:
    return {
        "title": "Ranní nápoj",
        "n": 20,
        "sections": [
            {
                "type": "questions",
                "questions": [
                    {
                        "id": "q1",
                        "text": "Pijete kávu?",
                        "typ": "vyber",
                        "kategorie": ["Ano", "Ne"],
                    },
                    {"id": "q2", "text": "Jak často?", "typ": "skala", "skala": [1, 5], **question},
                ],
            }
        ],
    }


def _dataset(fingerprint: str, rows: list[dict[str, Any]]) -> FieldworkDataset:
    return FieldworkDataset(
        dataset_version="1",
        source=FieldworkSource.AI_RUNTIME,
        origin=DataOrigin.SYNTHETIC_AI_FICTIONAL,
        spec_fingerprint=fingerprint,
        seed=1,
        generator="test",
        respondents=tuple(
            FieldworkRespondent(respondent_id=f"r{k}", donor_id=f"d{k}", weight=1.0, answers=a)
            for k, a in enumerate(rows)
        ),
    )


def test_a_dataset_of_another_specification_is_refused_never_read_as_unanswered() -> None:
    spec, problems = compile_design(_questions_design())
    assert spec is not None, problems
    with pytest.raises(InvalidDataset, match="different specification"):
        dataset_qc(spec, _dataset("another", [{"q1": "Ano", "q2": 3}]), dry=True)


def test_a_conditional_question_is_refused_until_the_dataset_records_who_was_asked() -> None:
    spec, problems = compile_design(
        _questions_design(filtr={"question_id": "q1", "options": ["Ano"]})
    )
    assert spec is not None, problems
    assert spec.questions[1].condition is not None
    dataset = _dataset(spec.fingerprint(), [{"q1": "Ano", "q2": 3}, {"q1": "Ne", "q2": None}])
    with pytest.raises(QcNotReadable, match="q2: a conditional question's base"):
        dataset_qc(spec, dataset, dry=True)
