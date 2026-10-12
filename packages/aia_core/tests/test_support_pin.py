"""A run's support rules are the ones it pinned (plan ``methodology-tab.md`` G1c).

With nothing stored a run pins ``aia-support-1``: both rules as they were before any version
(owner, 2026-10-12) -- 18.6.6's donor rule for every cell's status, AIA's gate for analysis.
The aggregate decides by the pinned ``results`` rule and analysis gates by the pinned
``analysis`` rule; only a rule other than today's moves a fingerprint, so a run under today's
rules keeps the keys and validations it always had.
"""

from __future__ import annotations

from typing import Any

from aia_core.domain.analysis.native import native_evidence
from aia_core.domain.evidence.support import (
    AIA_SUPPORT_V1,
    REFERENCE_THRESHOLDS,
    UNIT_DONOR_THRESHOLDS,
    SupportSpec,
    SupportThresholds,
)
from aia_core.domain.methodology.pins import read_support_pin, support_spec_for
from aia_core.domain.research_aggregate import UNCERTAINTY_NOTE, aggregate_dataset
from aia_core.domain.research_design import compile_design
from aia_core.domain.synthetic_fieldwork import synthetic_dataset

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "n": 60,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak hodnotíte kávu?", "typ": "skala", "skala": [1, 5]},
            ],
        }
    ],
}
SHA = "d" * 64


def _run() -> tuple[Any, Any]:
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    return spec, synthetic_dataset(spec, seed=20261012)


def _status(aggregate: dict[str, Any]) -> str:
    return str(aggregate["questions"]["q1"]["support_status"])


def test_with_nothing_stored_a_run_pins_both_rules_as_today() -> None:
    assert support_spec_for(None) is AIA_SUPPORT_V1
    assert read_support_pin(None) is AIA_SUPPORT_V1  # a run started before the pin
    assert AIA_SUPPORT_V1.results == UNIT_DONOR_THRESHOLDS
    assert AIA_SUPPORT_V1.analysis == REFERENCE_THRESHOLDS
    pinned = AIA_SUPPORT_V1.model_dump(mode="json")
    assert read_support_pin(pinned) == AIA_SUPPORT_V1
    assert support_spec_for({"spec": pinned}) == AIA_SUPPORT_V1


def test_the_aggregate_decides_by_the_pinned_results_rule() -> None:
    spec, dataset = _run()
    today = aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1)
    donors = today["questions"]["q1"]["n_unique_layer_donors"]
    assert _status(today) == "SUPPRESS" and donors < 25  # 60 fictional people, 20 donors
    looser = AIA_SUPPORT_V1.model_copy(
        update={
            "methodology_version": "aia-support-1+e1",
            "results": UNIT_DONOR_THRESHOLDS.model_copy(
                update={"min_layer_donors": 10, "indicative_layer_donors": 15}
            ),
        }
    )
    edited = aggregate_dataset(spec, dataset, support=looser)
    assert _status(edited) == "REPORTABLE"
    assert edited["questions"]["q1"]["n_guard_threshold"] == 10.0
    # The note each cell carries states the lines of the rule that decided it (G1d).
    assert today["questions"]["q1"]["uncertainty_note"] == UNCERTAINTY_NOTE
    assert (
        "<10 se nereportuje; 10\u201314 je INDIKATIVNÍ"
        in (edited["questions"]["q1"]["uncertainty_note"])
    )
    # Nothing else of the cell moves: the rule decides the status, not the estimate.
    for key in ("prumer", "effective_n", "n_unique_layer_donors", "n_platnych"):
        assert edited["questions"]["q1"][key] == today["questions"]["q1"][key], key


def test_analysis_gates_by_the_pinned_analysis_rule_and_only_a_new_one_moves_the_key() -> None:
    spec, dataset = _run()
    loose = SupportThresholds(
        min_cell=10, n_guard=5.0, indicative=6.0, min_layer_donors=10, indicative_layer_donors=15
    )
    support = SupportSpec(
        methodology_version="aia-support-1+e1",
        results=loose,
        analysis=loose,
    )
    aggregate = aggregate_dataset(spec, dataset, support=support)
    today = native_evidence(
        spec, aggregate, dataset_sha256=SHA, origin=dataset.origin, support=REFERENCE_THRESHOLDS
    )
    edited = native_evidence(
        spec, aggregate, dataset_sha256=SHA, origin=dataset.origin, support=loose
    )
    assert "q1.mean" in today.table.suppressed  # n 60 passes min_cell 50; 20 donors fail 25
    assert "q1.mean" in edited.table.rows
    assert edited.system_fingerprint != today.system_fingerprint
    again = native_evidence(
        spec, aggregate, dataset_sha256=SHA, origin=dataset.origin, support=REFERENCE_THRESHOLDS
    )
    assert again.system_fingerprint == today.system_fingerprint
