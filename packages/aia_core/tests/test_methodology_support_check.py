"""The support draft check (plan ``methodology-tab.md`` G1d, ADR 0023 decision 10).

An edited support rule is decided beside the rules in force on fixed fictional cells, through
the functions a run decides with, and every cell it newly reports or newly suppresses is
named, on each surface.
"""

from __future__ import annotations

from aia_core.domain.analysis.native import reassess_support
from aia_core.domain.evidence.support import (
    AIA_SUPPORT_V1,
    REFERENCE_THRESHOLDS,
    UNIT_DONOR_THRESHOLDS,
    SupportSpec,
    SupportThresholds,
)
from aia_core.domain.methodology.support_check import (
    SUPPORT_CHECK_CELLS,
    compare_support,
    compare_support_with_in_force,
)
from aia_core.domain.research_aggregate import donor_support, uncertainty_note


def _version(results: SupportThresholds, analysis: SupportThresholds) -> SupportSpec:
    return SupportSpec(methodology_version="aia-support-1+e1", results=results, analysis=analysis)


def _payload(spec: SupportSpec) -> dict[str, object]:
    return {"spec": spec.model_dump(mode="json")}


def test_the_cells_are_fixed_and_span_every_status() -> None:
    first = compare_support(AIA_SUPPORT_V1, AIA_SUPPORT_V1)
    again = compare_support(AIA_SUPPORT_V1, AIA_SUPPORT_V1)
    assert first == again and len(first.cells) == len(SUPPORT_CHECK_CELLS) == 16
    assert all("fiktivní" in c.label_cs for c in first.cells)
    today = {c.results[0] for c in first.cells} | {c.analysis[0] for c in first.cells}
    assert today == {"SUPPRESS", "INDICATIVE", "REPORTABLE"}
    # Finding D2 is on the list: Results shows what analysis reads as only indicative.
    assert any(c.results[0] != c.analysis[0] for c in first.cells)


def test_an_unchanged_draft_moves_nothing() -> None:
    same = compare_support(AIA_SUPPORT_V1, AIA_SUPPORT_V1)
    assert all(c.changes() == {} for c in same.cells)
    assert same.moved("reported") == same.moved("suppressed") == same.moved("changed") == ()


def test_each_cell_is_decided_by_the_functions_a_run_decides_with() -> None:
    looser = _version(
        UNIT_DONOR_THRESHOLDS.model_copy(update={"min_layer_donors": 10}), REFERENCE_THRESHOLDS
    )
    compared = compare_support(AIA_SUPPORT_V1, looser)
    for cell, row in zip(SUPPORT_CHECK_CELLS, compared.cells, strict=True):
        donors, weights = cell.sample()
        for i, spec in enumerate((AIA_SUPPORT_V1, looser)):
            unit = donor_support(donors, weights, rule=spec.results)
            assert row.results[i] == unit["support_status"], cell.id
            again = reassess_support(
                {
                    "support_status": unit["support_status"],
                    "n_platnych": unit["n"],
                    "effective_n": unit["effective_n_combined"],
                    "n_unique_layer_donors": unit["n_unique_layer_donors"],
                },
                spec.analysis,
            )
            assert row.analysis[i] == again.status.value, cell.id
        assert (row.n, row.donors) == (len(donors), len(set(donors)))


def test_a_looser_rule_lists_every_cell_it_newly_reports_and_suppresses_none() -> None:
    looser = _version(
        UNIT_DONOR_THRESHOLDS.model_copy(
            update={"min_layer_donors": 10, "indicative_layer_donors": 20}
        ),
        REFERENCE_THRESHOLDS,
    )
    compared = compare_support(AIA_SUPPORT_V1, looser)
    reported = compared.moved("reported")
    assert reported and all(surface == "results" for _, surface in reported)
    expected = {c.cell for c in compared.cells if c.results[0] == "SUPPRESS" and c.donors >= 10}
    assert {cell for cell, _ in reported} == expected
    assert compared.moved("suppressed") == ()


def test_a_stricter_rule_lists_every_cell_it_newly_suppresses_and_reports_none() -> None:
    stricter = _version(
        UNIT_DONOR_THRESHOLDS,
        REFERENCE_THRESHOLDS.model_copy(update={"min_cell": 200}),
    )
    compared = compare_support(AIA_SUPPORT_V1, stricter)
    suppressed = {cell for cell, surface in compared.moved("suppressed")}
    assert suppressed == {
        c.cell for c in compared.cells if c.analysis[0] != "SUPPRESS" and c.n < 200
    }
    assert compared.moved("reported") == ()


def test_the_stricter_of_the_two_rules_still_wins_in_analysis() -> None:
    """An analysis rule looser than the results rule cannot show what Results suppresses."""
    loose = SupportThresholds(
        min_cell=1, n_guard=None, indicative=None, min_layer_donors=1, indicative_layer_donors=2
    )
    compared = compare_support(AIA_SUPPORT_V1, _version(UNIT_DONOR_THRESHOLDS, loose))
    for c in compared.cells:
        if c.results[1] == "SUPPRESS":
            assert c.analysis[1] == "SUPPRESS", c.cell


def test_the_draft_is_compared_with_the_stored_version_in_force() -> None:
    stored = _version(REFERENCE_THRESHOLDS, REFERENCE_THRESHOLDS)
    compared = compare_support_with_in_force(_payload(stored), _payload(AIA_SUPPORT_V1))
    assert (compared.in_force, compared.draft) == ("aia-support-1+e1", "aia-support-1")
    assert compare_support_with_in_force(None, _payload(AIA_SUPPORT_V1)).in_force == (
        "aia-support-1"
    )


def test_the_uncertainty_note_states_the_lines_of_the_rule_in_force() -> None:
    assert "<25 se nereportuje; 25\u201349 je INDIKATIVNÍ" in uncertainty_note(
        UNIT_DONOR_THRESHOLDS
    )
    edited = uncertainty_note(
        UNIT_DONOR_THRESHOLDS.model_copy(update={"min_layer_donors": 10, "min_cell": 30})
    )
    assert "n_platnych <30 se nereportuje" in edited
    assert "n_unique_layer_donors <10 se nereportuje; 10\u201349 je INDIKATIVNÍ" in edited
    assert "25" not in edited
    no_band = uncertainty_note(
        UNIT_DONOR_THRESHOLDS.model_copy(update={"indicative_layer_donors": 25})
    )
    assert "INDIKATIVNÍ" not in no_band
