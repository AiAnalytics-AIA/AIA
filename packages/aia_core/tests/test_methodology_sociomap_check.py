"""What an edited object map does, shown before it is put in force (ADR 0023 decision 7, S4b).

The check runs the draft and the methodology in force through the real engine on fixed
fictional panels and reports what moved. These tests hold that it is the same every time,
that a methodology compared with itself moves nothing, and that each kind of edit moves what
it should -- and only that.
"""

from __future__ import annotations

import math
from typing import Any

from aia_core.domain.methodology.expressions import compile_formula
from aia_core.domain.methodology.sociomap_check import (
    CHECK_PANELS,
    compare_object_maps,
    compare_with_in_force,
)
from aia_core.domain.methodology.sociomap_formulas import SOCIOMAP_FORMULAS
from aia_core.domain.sociomap import AIA_SOCIOMAP_V3
from aia_core.domain.sociomap.metrics import ObjectRole

SLOTS = {f.slot.id: f.slot for f in SOCIOMAP_FORMULAS}
IN_FORCE = (AIA_SOCIOMAP_V3, {})


def _edited(**parts: dict[str, Any]) -> Any:
    return AIA_SOCIOMAP_V3.model_copy(
        update={k: getattr(AIA_SOCIOMAP_V3, k).model_copy(update=v) for k, v in parts.items()}
    )


def test_the_panels_are_fictional_fixed_and_cover_weights_gaps_and_context() -> None:
    for panel in CHECK_PANELS:
        once, again = panel.inputs(), panel.inputs()
        assert once == again
        assert all(rid.startswith("R") for rid in once.respondent_ids)
        assert all(v is None or 1.0 <= v <= 10.0 for row in once.values for v in row)
    weighted = next(p for p in CHECK_PANELS if p.id == "weighted").inputs()
    assert len(set(weighted.weights)) > 1
    assert any(v is None for row in weighted.values for v in row)
    assert ObjectRole.SECONDARY.value in weighted.roles.values()


def test_a_methodology_beside_itself_moves_nothing() -> None:
    for c in compare_object_maps(IN_FORCE, IN_FORCE):
        assert c.in_force == c.draft
        assert c.status_changes == ()
        assert c.alignment_rmsd is not None and c.alignment_rmsd < 1e-12
        assert max(c.shifts.values()) < 1e-12
        assert all(a == b for a, b in c.heights.values())
        assert all(a == b for a, b in c.k100.values())
        assert c.terrain_max_change == 0.0


def test_a_higher_n_min_changes_statuses_on_the_small_panel() -> None:
    small = {
        c.panel: c for c in compare_object_maps(IN_FORCE, (_edited(relation={"n_min": 34}), {}))
    }
    changes = small["small"].status_changes
    assert changes and all(to == "unknown" for _, _, _, to in changes)
    assert small["balanced"].status_changes == ()  # 120 raters stay above 34


def test_a_wider_hill_moves_the_terrain_and_nothing_else() -> None:
    for c in compare_object_maps(IN_FORCE, (_edited(terrain={"sigma": 0.3}), {})):
        assert c.terrain_max_change is not None and c.terrain_max_change > 0
        assert c.status_changes == () and max(c.shifts.values()) < 1e-12
        assert c.in_force.stress_1 == c.draft.stress_1


def test_a_replaced_distance_moves_the_objects() -> None:
    draft = (AIA_SOCIOMAP_V3, {"f6.distance": compile_formula(SLOTS["f6.distance"], "1 - r")})
    moved = [max(c.shifts.values()) for c in compare_object_maps(IN_FORCE, draft)]
    assert all(m > 1e-3 for m in moved)


def test_a_replaced_k100_is_the_k100_compared() -> None:
    draft = (AIA_SOCIOMAP_V3, {"f9.k100": compile_formula(SLOTS["f9.k100"], "50 * k")})
    for c in compare_object_maps(IN_FORCE, draft):
        for before, after in c.k100.values():
            assert before is not None and after is not None
            assert math.isclose(after, before / 2, rel_tol=1e-12)
        assert any("interval" in note for note in c.notes)


def test_a_draft_payload_is_checked_through_the_runs_own_pin() -> None:
    spec = _edited(terrain={"sigma": 0.3}).model_copy(
        update={"methodology_version": "aia-sociomap-3+e1"}
    )
    payload = {"spec": spec.model_dump(mode="json"), "formulas": {"f9.k100": "50 * k"}}
    panels = compare_with_in_force(None, payload)
    assert [p.panel for p in panels] == [p.id for p in CHECK_PANELS]
    first = panels[0]
    assert first.terrain_max_change is not None and first.terrain_max_change > 0
    before, after = next(iter(first.k100.values()))
    assert before is not None and after is not None and math.isclose(after, before / 2)
