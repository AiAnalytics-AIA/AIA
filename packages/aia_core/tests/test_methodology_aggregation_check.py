"""The aggregation draft check (plan ``methodology-tab.md`` G3b, ADR 0023 decision 7).

An edited aggregation is computed beside the one in force on fixed fictional panels, through
``aggregate_dataset`` itself, and every estimate, interval and status it moves is named.
"""

from __future__ import annotations

import copy
from typing import Any

from aia_core.domain.evidence.support import AIA_SUPPORT_V1, SupportThresholds
from aia_core.domain.methodology.aggregation_check import (
    AGGREGATION_CHECK_PANELS,
    compare_aggregation,
    compare_aggregation_with_in_force,
)
from aia_core.domain.methodology.pins import UNIT_AGGREGATION_PIN

UNIT = UNIT_AGGREGATION_PIN


def _draft(formulas: dict[str, str] | None = None, **values: Any) -> dict[str, Any]:
    pin = copy.deepcopy(dict(UNIT))
    pin["spec"]["methodology_version"] = "aia-aggregate-1+e1"
    for path, value in values.items():
        node = pin["spec"]
        *parents, leaf = path.split("__")
        for p in parents:
            node = node[p]
        node[leaf] = value
    pin["formulas"] = formulas or {}
    return pin


def test_the_panels_are_fixed_fictional_and_span_every_status() -> None:
    first = compare_aggregation(UNIT, UNIT, support=AIA_SUPPORT_V1)
    assert first == compare_aggregation(UNIT, UNIT, support=AIA_SUPPORT_V1)
    assert all("fiktivní" in p.label_cs for p in first.panels)
    assert {p.panel for p in first.panels} == {p.id for p in AGGREGATION_CHECK_PANELS}
    statuses = {s for p in first.panels for _, s, _ in p.statuses}
    assert statuses == {"SUPPRESS", "INDICATIVE", "REPORTABLE"}
    # Every reported estimate is there: two scales x (mean, top box), 3 + 4 shares.
    assert all(len(p.rows) == 11 for p in first.panels)


def test_an_unchanged_draft_moves_nothing() -> None:
    same = compare_aggregation(UNIT, _draft(), support=AIA_SUPPORT_V1)
    assert (same.in_force, same.draft) == ("aia-aggregate-1", "aia-aggregate-1+e1")
    for panel in same.panels:
        assert panel.moved == () and panel.status_changes == ()


def test_a_narrower_top_box_moves_every_top_box_and_nothing_else() -> None:
    narrow = compare_aggregation(UNIT, _draft(top_box=1), support=AIA_SUPPORT_V1)
    for panel in narrow.panels:
        moved = {(r.question, r.measure) for r in panel.moved}
        assert moved == {("spokojenost", "top2box"), ("doporuceni", "top2box")}
        for r in panel.moved:
            assert r.draft[0] is not None and r.in_force[0] is not None
            assert r.draft[0] < r.in_force[0]  # one top point holds fewer than two


def test_a_replaced_kish_formula_moves_the_effective_n_and_with_it_a_status() -> None:
    """Under a rule that checks effective n, an edited Kish formula moves statuses, and the
    check says which. Ignoring the weights lifts the weighted panel's effective n from about
    31 to its 40 donors (the combined n is capped by them), across a line at 35."""
    gate = AIA_SUPPORT_V1.model_copy(
        update={
            "results": SupportThresholds(
                min_cell=None,
                n_guard=35.0,
                indicative=None,
                min_layer_donors=None,
                indicative_layer_donors=None,
            )
        }
    )
    unweighted = compare_aggregation(UNIT, _draft({"agg.kish": "count(w)"}), support=gate)
    weighted = next(p for p in unweighted.panels if p.panel == "vazeny")
    assert all(before < 35.0 <= after for _, before, after in weighted.effective_n)
    assert {(q, x, y) for q, x, y in weighted.status_changes} == {
        (q, "SUPPRESS", "REPORTABLE") for q in ("spokojenost", "doporuceni", "volba", "kanaly")
    }
    # The panel without weights has nothing a Kish edit could move.
    small = next(p for p in unweighted.panels if p.panel == "maly")
    assert small.status_changes == () and all(b == a for _, b, a in small.effective_n)


def test_fewer_replicates_move_intervals_not_estimates() -> None:
    fewer = compare_aggregation(UNIT, _draft(bootstrap__reps=50), support=AIA_SUPPORT_V1)
    rows = [r for p in fewer.panels for r in p.moved]
    assert rows
    assert all(r.in_force[0] == r.draft[0] for r in rows)  # the estimate itself stands


def test_the_draft_is_compared_with_the_stored_version_in_force() -> None:
    stored = {**_draft(top_box=1), "contract": "aia-methodology-version-1"}
    compared = compare_aggregation_with_in_force(stored, UNIT, support=AIA_SUPPORT_V1)
    assert (compared.in_force, compared.draft) == ("aia-aggregate-1+e1", "aia-aggregate-1")
    assert compare_aggregation_with_in_force(None, UNIT, support=AIA_SUPPORT_V1).in_force == (
        "aia-aggregate-1"
    )
