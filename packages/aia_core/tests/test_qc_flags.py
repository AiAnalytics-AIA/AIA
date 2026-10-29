"""RQC4a: a run's deterministic QC flags, their ids and lineage, and the accept target."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.fieldwork import (
    DataOrigin,
    FieldworkDataset,
    FieldworkRespondent,
    FieldworkSource,
)
from aia_core.domain.qc_flags import (
    ACCEPT_FIELD,
    QC_FLAGS_VERSION,
    DecisionRefused,
    FlagDecision,
    FlagDecisionRecord,
    FlagKind,
    check_decision,
    dataset_flags,
    flag_id,
    flags_payload,
    read_flags,
    record_flags,
    straight_liner_flags,
)
from aia_core.domain.research_design import compile_design
from aia_core.domain.run_qc import QcNotReadable, QcQuestion, run_qc
from aia_core.domain.straight_lining import AnswerSpread

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "run_qc" / "cases.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_the_flags_are_exactly_the_respondents_the_run_qc_counts(case: dict[str, Any]) -> None:
    """One rule (RQC1): the flags' count is the run QC's straight-lining share, on every captured
    run; with too few scales the QC reads no share and nobody is flagged."""
    questions = [QcQuestion(o["id"], o["typ"], tuple(o["volby"])) for o in case["otazky"]]
    rows = case["rows"]
    flags = straight_liner_flags(
        [q.id for q in questions if q.typ == "skala"],
        [(f"r{k}", row) for k, row in enumerate(rows)],
    )
    share = run_qc(questions, rows, dry=False, ablation=False).metrics.get("straightlining")
    if share is None:
        assert flags == ()
    else:
        assert round(len(flags) / len(rows), 3) == share


def test_a_flag_names_its_respondent_its_reading_and_the_items_read() -> None:
    items = ("s1", "s2", "s3")
    flags = straight_liner_flags(
        items,
        [
            ("a", {"s1": 4, "s2": 4, "s3": 4}),
            ("b", {"s1": 1, "s2": 4, "s3": 5}),
            ("c", {"s1": 2, "s2": None, "s3": None}),
            ("d", {}),
        ],
    )
    assert [(f.flag_id, f.spread, f.items) for f in flags] == [
        ("straight_liner:a", AnswerSpread.NO_SPREAD, items),
        ("straight_liner:c", AnswerSpread.ONE, items),
    ]


def test_a_flag_id_names_a_respondent() -> None:
    assert flag_id(FlagKind.STRAIGHT_LINER, "r7") == "straight_liner:r7"
    with pytest.raises(ValueError, match="names a respondent"):
        flag_id(FlagKind.STRAIGHT_LINER, "")


def test_stored_flags_read_back_and_a_forged_or_other_version_is_refused() -> None:
    flags = straight_liner_flags(("a", "b", "c"), [("r1", {"a": 2, "b": 2, "c": 2})])
    payload = json.loads(json.dumps(flags_payload(flags)))
    assert payload["version"] == QC_FLAGS_VERSION
    assert read_flags(payload) == flags
    with pytest.raises(ValueError, match="not readable"):
        read_flags({**payload, "version": "aia-qc-flags-0"})
    entry = payload["flags"][0]
    with pytest.raises(ValueError, match="does not name"):
        read_flags({**payload, "flags": [{**entry, "id": "straight_liner:r2"}]})
    for broken in ({k: v for k, v in entry.items() if k != "spread"}, {**entry, "items": "abc"}):
        with pytest.raises(ValueError, match="stored shape"):
            read_flags({**payload, "flags": [broken]})
    with pytest.raises(ValueError, match="stored shape"):
        read_flags({"version": QC_FLAGS_VERSION})


def _spec(**condition: Any) -> Any:
    spec, problems = compile_design(
        {
            "title": "Ranní nápoj",
            "n": 20,
            "sections": [
                {
                    "type": "questions",
                    "questions": [
                        {
                            "id": "q0",
                            "text": "Pijete kávu?",
                            "typ": "vyber",
                            "kategorie": ["Ano", "Ne"],
                        }
                    ]
                    + [
                        {
                            "id": f"q{k}",
                            "text": f"Otázka {k}?",
                            "typ": "skala",
                            "skala": [1, 5],
                            **(condition if k == 3 else {}),
                        }
                        for k in (1, 2, 3)
                    ],
                }
            ],
        }
    )
    assert spec is not None, problems
    return spec


def _dataset(spec: Any, rows: list[dict[str, Any]]) -> FieldworkDataset:
    return FieldworkDataset(
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


def test_a_datasets_flags_read_its_scale_questions_by_respondent_id() -> None:
    spec = _spec()
    rows = [{"q0": "Ano", "q1": 3, "q2": 3, "q3": 3}, {"q0": "Ano", "q1": 1, "q2": 2, "q3": 3}]
    (flag,) = dataset_flags(spec, _dataset(spec, rows))
    assert flag.flag_id == "straight_liner:r0" and flag.items == ("q1", "q2", "q3")


def test_a_conditional_question_is_refused_as_the_run_qc_refuses_it() -> None:
    spec = _spec(filtr={"question_id": "q0", "options": ["Ano"]})
    with pytest.raises(QcNotReadable, match="q3: a conditional question's base"):
        dataset_flags(spec, _dataset(spec, [{"q0": "Ne", "q1": 2, "q2": 2, "q3": None}]))


FLAGS = straight_liner_flags(("a", "b", "c"), [("r1", {"a": 2, "b": 2, "c": 2})])
QC = {"inputs": {"dataset_sha256": "sha-1"}, "flags": flags_payload(FLAGS)}


def _record(**change: Any) -> FlagDecisionRecord:
    base: dict[str, Any] = {
        "flag_id": "straight_liner:r1",
        "decision": "keep",
        "qc_artifact_id": "qc-1",
        "dataset_sha256": "sha-1",
        "decided_by": "user-1",
    }
    return FlagDecisionRecord(**{**base, **change})


def _check(record: FlagDecisionRecord, qc: dict[str, Any] = QC) -> FlagDecision:
    return check_decision(record, qc_artifact_id="qc-1", qc=qc)


def test_a_decision_on_a_stored_flag_is_taken() -> None:
    assert ACCEPT_FIELD == "flag_decisions"
    assert _check(_record()) is FlagDecision.KEEP
    assert _check(_record(decision="flag", proposal="job-9")) is FlagDecision.FLAG


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"decision": "replace"}, "replace_not_available"),
        ({"decision": "drop"}, "decision_unknown"),
        ({"decided_by": ""}, "no_author"),
        ({"qc_artifact_id": "qc-2"}, "other_record"),
        ({"dataset_sha256": "sha-2"}, "stale_dataset"),
        ({"flag_id": "straight_liner:r2"}, "unknown_flag"),
    ],
)
def test_a_decision_the_record_does_not_take_is_refused_by_name(
    change: dict[str, Any], reason: str
) -> None:
    with pytest.raises(DecisionRefused) as refused:
        _check(_record(**change))
    assert refused.value.reason == reason


def test_a_record_without_flags_is_unrecorded_never_no_flags() -> None:
    """A QC that could not be read, or one stored before the flags, holds no ``flags``."""
    unrecorded = {"inputs": QC["inputs"], "status": "not_computed"}
    assert record_flags(unrecorded) is None
    assert record_flags({"flags": flags_payload(())}) == ()
    with pytest.raises(DecisionRefused) as refused:
        _check(_record(), unrecorded)
    assert refused.value.reason == "flags_unrecorded"
