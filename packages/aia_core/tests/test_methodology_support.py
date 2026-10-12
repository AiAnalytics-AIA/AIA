"""Support and suppression on the Metodika tab (plan ``methodology-tab.md`` G1a).

What every registered module must be (complete, pinned, its tests present) is held by
``test_methodology.py``; this file pins what is particular to this one: it only documents
(nothing is declared yet, so nothing is in force or editable), it shows both rule sets that
decide today with the values the code decides with, and it says that they disagree.
"""

from __future__ import annotations

from aia_core.domain import research_aggregate
from aia_core.domain.evidence.support import REFERENCE_THRESHOLDS
from aia_core.domain.methodology import MODULES, ValueOrigin, describe
from aia_core.domain.methodology.support import SUPPORT


def _values() -> dict[str, object]:
    view = describe(SUPPORT)
    return {v.reference: v.value for s in view.steps for v in s.values}


def test_it_is_registered_after_the_sociomap_modules() -> None:
    assert [m.id for m in MODULES][-1] == "support"


def test_it_documents_and_declares_nothing_yet() -> None:
    assert SUPPORT.presets == () and SUPPORT.in_force is None
    assert SUPPORT.editable is False and SUPPORT.formulas == ()
    view = describe(SUPPORT)
    origins = {v.origin for s in view.steps for v in s.values}
    assert origins == {ValueOrigin.CODE_CONSTANT}


def test_the_units_rule_is_shown_with_the_thresholds_results_reads() -> None:
    values = _values()
    assert (
        values["aia_core.domain.research_aggregate:_SUPPRESS_BELOW"]
        == (research_aggregate._SUPPRESS_BELOW)
        == 25
    )
    assert (
        values["aia_core.domain.research_aggregate:_REPORTABLE_FROM"]
        == (research_aggregate._REPORTABLE_FROM)
        == 50
    )


def test_aias_gate_is_shown_with_every_threshold_it_decides_with() -> None:
    values = _values()
    prefix = "aia_core.domain.evidence.support:REFERENCE_THRESHOLDS."
    for name in (
        "min_cell",
        "n_guard",
        "indicative",
        "min_layer_donors",
        "indicative_layer_donors",
    ):
        assert values[prefix + name] == getattr(REFERENCE_THRESHOLDS, name), name


def test_the_two_rule_sets_are_two_groups_and_the_conflict_is_named() -> None:
    groups = {g.id: g.step_ids for g in SUPPORT.groups}
    assert set(groups) == {"U", "A"}
    assert "unit_status" in groups["U"] and "gate_assess" in groups["A"]
    assert "INDIKATIVNÍ" in SUPPORT.note_cs and "potlačená" in SUPPORT.note_cs
    notes = " ".join(s.note_cs for s in SUPPORT.steps)
    for finding in ("D1", "D2", "D3", "D4"):
        assert finding in notes, finding
