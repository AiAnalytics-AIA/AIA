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
    MODULES,
    EvidenceKind,
    ValueOrigin,
    describe,
    module,
)
from aia_core.domain.methodology.sociomap import SOCIOMAP
from aia_core.domain.methodology.sociomap_reference import SOCIOMAP_REFERENCE
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V1, AIA_SOCIOMAP_V3

REPO = Path(__file__).resolve().parents[3]
REGISTER = REPO / "docs/migration/sociomapping-evidence-register.json"


def _values(preset: str | None = None) -> dict[str, object]:
    view = describe(SOCIOMAP, preset)
    return {v.reference: v.value for s in view.steps for v in s.values}


def test_the_sociomap_is_registered() -> None:
    assert module("sociomap") is SOCIOMAP
    assert module("sociomap_reference") is SOCIOMAP_REFERENCE


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
    # No floor is left out of the stored form, so an edit from this preset cannot set one:
    # absent, like the part the preset does not have.
    assert values["relation.effect_floor"] is ABSENT


def test_the_object_maps_own_constants_are_absent_before_aia_sociomap_4() -> None:
    before, after = _values("aia-sociomap-3"), _values("aia-sociomap-4")
    for path in ("layout.min_objects", "layout.stress_bands", "connectedness.quantiles"):
        assert before[path] is ABSENT
        assert after[path] is not ABSENT
    assert after["layout.min_objects"] == 3
    assert after["layout.stress_bands"] == (0.05, 0.10, 0.20)
    assert after["connectedness.quantiles"] == (0.025, 0.975)


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
        e.ref
        for m in MODULES
        for s in m.steps
        for e in s.evidence
        if e.kind is EvidenceKind.REGISTER_RULE
    }
    assert cited and cited <= rules, sorted(cited - rules)


def test_every_step_that_computes_cites_a_register_rule() -> None:
    """Plan methodology-tab S1d: no step of a Sociomap module computes without a rule of the
    register behind it -- the register is the Sociomapping engine's, so a module of another
    area (support, aggregation) answers to its own evidence. ``method`` names the method and
    computes nothing."""
    bare = [
        f"{m.id}/{s.id}"
        for m in MODULES
        if m.id.startswith("sociomap")
        for s in m.steps
        if s.id != "method" and not any(e.kind is EvidenceKind.REGISTER_RULE for e in s.evidence)
    ]
    assert bare == []


def test_every_audit_point_the_map_computes_cites_its_rule() -> None:
    cited = {
        e.ref for s in SOCIOMAP.steps for e in s.evidence if e.kind is EvidenceKind.REGISTER_RULE
    }
    computed = {1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13}
    assert {f"AUDIT-F{n}" for n in computed} <= cited


# --------------------------------------------------------------------------- the reference map


def test_the_reference_map_shows_the_values_it_runs_with() -> None:
    view = describe(SOCIOMAP_REFERENCE)
    values = {v.reference: v.value for s in view.steps for v in s.values}
    assert view.preset == "aia-sociomap-1"
    assert values["layout.parameters.max_iterations"] == 2000
    assert values["layout.map_frame.extent"] == AIA_SOCIOMAP_V1.layout.map_frame.extent == 45.0
    assert values["terrain.respondent.sigma"] == 9.5
    assert values["terrain.object.sigma"] == 12.0
    assert values["aia_core.domain.sociomap.relations:_NAN_SENTINEL"] == 5.5


def test_each_reference_step_the_audit_criticises_says_so() -> None:
    criticised = {
        s.id
        for s in SOCIOMAP_REFERENCE.steps
        for e in s.evidence
        if e.kind is EvidenceKind.REGISTER_RULE and e.ref.startswith("AUDIT-") and e.note_cs
    }
    assert {
        "relation_matrix",
        "coercion",
        "frame",
        "relation_classic",
        "tscore",
        "terrain_objects",
    } <= criticised


def test_the_reference_map_is_kept_as_18_6_6_computed_it() -> None:
    kinds = {e.kind for s in SOCIOMAP_REFERENCE.steps for e in s.evidence}
    assert EvidenceKind.FIXTURE in kinds and EvidenceKind.LEGACY_PORT in kinds
    assert "needituje" in SOCIOMAP_REFERENCE.note_cs
