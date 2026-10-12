"""Support and suppression on the Metodika tab (plan ``methodology-tab.md`` G1a).

What every registered module must be (complete, pinned, its tests present) is held by
``test_methodology.py``; this file pins what is particular to this one: both rule sets
are declared in one specification whose preset is today (G1b), nothing is editable yet,
it shows both with the values they decide with, and it says that they disagree.
"""

from __future__ import annotations

from aia_core.domain.evidence.support import AIA_SUPPORT_V1, REFERENCE_THRESHOLDS
from aia_core.domain.methodology import MODULES, ValueOrigin, describe
from aia_core.domain.methodology.support import SUPPORT


def _values() -> dict[str, object]:
    view = describe(SUPPORT)
    return {v.reference: v.value for s in view.steps for v in s.values}


def test_it_is_registered_after_the_sociomap_modules() -> None:
    assert [m.id for m in MODULES][-1] == "support"


def test_today_is_the_preset_in_force_and_nothing_is_editable_yet() -> None:
    assert [p.name for p in SUPPORT.presets] == ["aia-support-1"]
    assert SUPPORT.presets[0].spec is AIA_SUPPORT_V1
    assert SUPPORT.in_force == "aia-support-1"
    assert SUPPORT.editable is False and SUPPORT.formulas == ()


def test_the_units_rule_is_shown_with_the_lines_results_reads() -> None:
    values = _values()
    assert values["results.min_layer_donors"] == 25
    assert values["results.indicative_layer_donors"] == 50
    for line in ("min_cell", "n_guard", "indicative"):
        assert values[f"results.{line}"] is None, line  # not checked by the unit's rule


def test_aias_gate_is_shown_with_every_threshold_it_decides_with() -> None:
    values = _values()
    for name in (
        "min_cell",
        "n_guard",
        "indicative",
        "min_layer_donors",
        "indicative_layer_donors",
    ):
        assert values[f"analysis.{name}"] == getattr(REFERENCE_THRESHOLDS, name), name


def test_every_value_is_the_specifications() -> None:
    view = describe(SUPPORT)
    origins = {v.origin for s in view.steps for v in s.values}
    assert origins == {ValueOrigin.SPECIFICATION}


def test_the_two_rule_sets_are_two_groups_and_the_conflict_is_named() -> None:
    groups = {g.id: g.step_ids for g in SUPPORT.groups}
    assert set(groups) == {"M", "U", "A"}
    assert "unit_status" in groups["U"] and "gate_assess" in groups["A"]
    assert "INDIKATIVNÍ" in SUPPORT.note_cs and "potlačená" in SUPPORT.note_cs
    notes = " ".join(s.note_cs for s in SUPPORT.steps)
    for finding in ("D1", "D2", "D3", "D4"):
        assert finding in notes, finding
