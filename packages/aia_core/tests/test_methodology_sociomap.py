"""The Metodika tab's Sociomap shows the audit's sixteen points as AIA computes them.

Plan ``methodology-tab.md`` S1. The catalogue's completeness, source pins and named tests
are held by ``test_methodology.py`` for every registered module; this file pins what the
methodologist relies on in this one: the audit's order, the values the map in force reads,
and the points AIA does not compute yet saying so.
"""

from __future__ import annotations

import json
from pathlib import Path

from aia_core.domain.methodology import (
    ABSENT,
    EvidenceKind,
    ValueOrigin,
    describe,
    module,
)
from aia_core.domain.methodology.sociomap import SOCIOMAP
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V3

REPO = Path(__file__).resolve().parents[3]
REGISTER = REPO / "docs/migration/sociomapping-evidence-register.json"


def _values(preset: str | None = None) -> dict[str, object]:
    view = describe(SOCIOMAP, preset)
    return {v.reference: v.value for s in view.steps for v in s.values}


def test_the_sociomap_is_registered() -> None:
    assert module("sociomap") is SOCIOMAP


def test_the_groups_follow_the_audit_from_f1_to_f16() -> None:
    ids = [g.id for g in SOCIOMAP.groups]
    assert ids == ["M", *[f"F{n}" for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16)]]
    assert next(g for g in SOCIOMAP.groups if g.id == "F12").title_cs.startswith("F12-F13")


def test_the_points_aia_does_not_compute_say_so() -> None:
    by_id = {g.id: g for g in SOCIOMAP.groups}
    for unbuilt in ("F14", "F15"):
        assert by_id[unbuilt].step_ids == ()
        assert "V AIA zatím není" in by_id[unbuilt].note_cs
    assert by_id["F16"].step_ids == () and "Otevřené" in by_id["F16"].note_cs
    placement = next(s for s in SOCIOMAP.steps if s.id == "f10_placement")
    assert "V AIA zatím není" in placement.note_cs


def test_the_map_in_force_shows_the_values_it_runs_with() -> None:
    values = _values()
    assert values["relation.n_min"] == AIA_SOCIOMAP_V3.relation.n_min == 30
    assert values["relation.confidence"] == 0.95
    assert values["relation.effect_floor"] == 0.1
    assert values["terrain.sigma"] == 0.25
    assert values["layout.tolerance"] == 1e-12
    assert values["respondent_placement"] is None


def test_the_predecessor_shows_the_terrain_it_does_not_have_as_absent() -> None:
    values = _values("aia-sociomap-2")
    assert values["terrain.sigma"] is ABSENT
    assert values["relation.effect_floor"] is None  # declared: no floor, not absent


def test_constants_outside_the_specification_are_labelled_code() -> None:
    view = describe(SOCIOMAP)
    origins = {v.reference: v.origin for s in view.steps for v in s.values}
    assert origins["aia_core.domain.sociomap.view:STRESS_QUALITY_BANDS"] is (
        ValueOrigin.CODE_CONSTANT
    )
    assert origins["aia_core.domain.sociomap.metrics:CONNECTEDNESS_QUANTILES"] is (
        ValueOrigin.CODE_CONSTANT
    )
    assert origins["relation.n_min"] is ValueOrigin.SPECIFICATION


def test_every_register_rule_cited_is_in_the_register() -> None:
    rules = {r["id"] for r in json.loads(REGISTER.read_text(encoding="utf-8"))["rules"]}
    cited = {
        e.ref for s in SOCIOMAP.steps for e in s.evidence if e.kind is EvidenceKind.REGISTER_RULE
    }
    assert cited and cited <= rules, sorted(cited - rules)


def test_every_audit_point_the_map_computes_cites_its_rule() -> None:
    cited = {
        e.ref for s in SOCIOMAP.steps for e in s.evidence if e.kind is EvidenceKind.REGISTER_RULE
    }
    computed = {1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13}
    assert {f"AUDIT-F{n}" for n in computed} <= cited
