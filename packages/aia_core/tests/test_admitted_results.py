"""Výsledky's admitted rows (evidence-integrity 6): a suppressed row's reasons leave as codes, and
its ref still names its metric.

A suppressed row's reasons are the words its producers write, and the words carry the numbers
withheld: the estimate, its interval, n and effective n. Each producer's words are met here, from
the producers themselves, and each must read as a known code with no number in it; words no
pattern knows read ``other``.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from aia_core.application.admitted_results import reason_codes
from aia_core.domain.analysis.native import native_evidence, ref_metric
from aia_core.domain.evidence.support import AIA_SUPPORT_V1, REFERENCE_THRESHOLDS
from aia_core.domain.research_aggregate import aggregate_dataset
from aia_core.domain.research_design import compile_design
from aia_core.domain.synthetic_fieldwork import synthetic_dataset

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "n": 200,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}


def _evidence(n: int = 200, mutate: Any = None) -> Any:
    spec, problems = compile_design({**DESIGN, "n": n})
    assert spec is not None, problems
    dataset = synthetic_dataset(spec, seed=20260816)
    aggregate = aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1)
    if mutate is not None:
        aggregate = copy.deepcopy(aggregate)
        mutate(aggregate["questions"]["q2"])
    return spec, native_evidence(
        spec,
        aggregate,
        dataset_sha256="d" * 64,
        origin=dataset.origin,
        support=REFERENCE_THRESHOLDS,
    )


def _codes_without_numbers(reasons: tuple[str, ...]) -> tuple[str, ...]:
    codes = reason_codes(reasons)
    assert codes and "other" not in codes, reasons
    assert not any(ch.isdigit() for code in codes for ch in code)
    return codes


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda r: r["intervaly_95"].pop("Kávu"), "no_interval"),
        (lambda r: r["intervaly_95"]["Kávu"].update(low=90.0, high=10.0), "interval_malformed"),
        (lambda r: r["intervaly_95"]["Kávu"].update(low=0.0, high=1.0), "outside_interval"),
        (lambda r: r["celkem_pct"].update({"Kávu": 41.25}), "not_rounded"),
        (lambda r: r["celkem_pct"].pop("Kávu"), "no_estimate"),
        (lambda r: r.update(support_status="SUPPRESS"), "unit_suppressed"),
        (lambda r: r.update(support_status="GREEN"), "support_status_unknown"),
        (lambda r: r.pop("evidence"), "no_fidelity_rating"),
    ],
)
def test_a_removed_numbers_reasons_read_as_codes_and_name_no_number(mutate: Any, code: str) -> None:
    _, evidence = _evidence(mutate=mutate)
    assert code in _codes_without_numbers(evidence.table.suppressed["q2.pct.1"].reasons)


def test_thin_support_reads_as_its_codes() -> None:
    _, evidence = _evidence(n=30)
    codes = {
        c for s in evidence.table.suppressed.values() for c in _codes_without_numbers(s.reasons)
    }
    assert "below_effective_n" in codes


def test_words_no_pattern_knows_read_other_never_their_text() -> None:
    assert reason_codes(("the estimate 41.2 was eaten", "effective n 3 < 25")) == (
        "other",
        "below_effective_n",
    )


def test_every_ref_the_evidence_mints_names_its_metric() -> None:
    spec, evidence = _evidence()
    options = {q.id: q.options for q in spec.questions}
    assert evidence.table.rows
    for ref, row in evidence.table.rows.items():
        assert row.question_id is not None
        suffix = ref.removeprefix(f"{row.question_id}.")
        assert ref_metric(suffix, options.get(row.question_id, ())) == row.metric
    assert ref_metric("pct.9", ("Kávu",)) is None and ref_metric("median", ()) is None
