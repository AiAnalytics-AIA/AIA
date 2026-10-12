"""Support and suppression on the Metodika tab (plan ``methodology-tab.md`` G1a).

What every registered module must be (complete, pinned, its tests present) is held by
``test_methodology.py``; this file pins what is particular to this one: both rule sets
are declared in one specification whose preset is today (G1b), both are editable both ways
(G1d) but never to a rule that suppresses nothing, it shows both with the values they decide
with, and it says that they disagree.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.evidence.support import AIA_SUPPORT_V1, REFERENCE_THRESHOLDS
from aia_core.domain.methodology import MODULES, ValueOrigin, describe
from aia_core.domain.methodology.support import SUPPORT
from aia_core.domain.methodology.versions import (
    MethodologyVersionInvalid,
    named,
    validate_version,
)


def _values() -> dict[str, object]:
    view = describe(SUPPORT)
    return {v.reference: v.value for s in view.steps for v in s.values}


def test_it_is_registered_after_the_sociomap_modules() -> None:
    assert [m.id for m in MODULES][-1] == "support"


def test_today_is_the_preset_in_force_and_its_lines_are_editable() -> None:
    assert [p.name for p in SUPPORT.presets] == ["aia-support-1"]
    assert SUPPORT.presets[0].spec is AIA_SUPPORT_V1
    assert SUPPORT.in_force == "aia-support-1"
    assert SUPPORT.editable is True and SUPPORT.formulas == ()


def _edited(**lines: Any) -> dict[str, Any]:
    spec = AIA_SUPPORT_V1.model_dump(mode="json")
    for path, value in lines.items():
        rule, line = path.split("__")
        spec[rule][line] = value
    return spec


def _validate(spec: dict[str, Any]) -> Any:
    return validate_version(
        SUPPORT,
        base_preset="aia-support-1",
        spec=spec,
        formulas={},
        version_name=named("aia-support-1", 1),
    )


@pytest.mark.parametrize(
    "lines",
    [
        {"results__min_layer_donors": 10, "results__indicative_layer_donors": 15},  # looser
        {"results__min_cell": 80, "analysis__min_cell": 120},  # stricter
        {"analysis__n_guard": None, "analysis__indicative": None},  # a line no longer checked
        {"results__n_guard": 25.0, "results__indicative": 50.0},  # a line newly checked
        {"results__min_cell": 50, "results__n_guard": 25.0, "results__indicative": 50.0},
    ],
)
def test_every_line_is_edited_both_ways(lines: dict[str, Any]) -> None:
    version = _validate(_edited(**lines))
    for path, value in lines.items():
        rule, line = path.split("__")
        assert getattr(getattr(version.spec, rule), line) == value, path
    assert version.spec.methodology_version == "aia-support-1+e1"


def test_the_two_rules_may_be_made_one() -> None:
    one = REFERENCE_THRESHOLDS.model_dump(mode="json")
    version = _validate({**_edited(), "results": one, "analysis": one})
    assert version.spec.results == version.spec.analysis == REFERENCE_THRESHOLDS


@pytest.mark.parametrize("rule", ["results", "analysis"])
def test_a_rule_that_suppresses_nothing_is_refused(rule: str) -> None:
    lines = {f"{rule}__{line}": None for line in ("min_cell", "n_guard", "min_layer_donors")}
    with pytest.raises(MethodologyVersionInvalid) as refused:
        _validate(_edited(**lines))
    assert set(refused.value.problems) == {f"spec.{rule}"}
    assert "nic nepotlačí" in refused.value.problems[f"spec.{rule}"]


def test_a_line_out_of_order_or_not_a_number_is_refused_by_name() -> None:
    with pytest.raises(MethodologyVersionInvalid) as refused:
        _validate(_edited(results__indicative_layer_donors=10, analysis__min_cell=True))
    assert {"spec.results", "spec.analysis.min_cell"} <= set(refused.value.problems)


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
