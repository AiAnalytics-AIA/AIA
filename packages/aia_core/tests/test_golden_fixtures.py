"""Golden-fixture parity gates against the reference repository.

The reference repository (``AiAnalytics-AIA/AIA-reference``) commits eleven
golden fixtures, each one self-contained JSON holding the input, the expected
output, the parity type and the tolerance, captured by executing the reference.
**None of them needs the raw archive**, so unlike the legacy-prototype suites
they can run in CI -- given read access to that private repository.

They are fetched, never copied here: the fixtures are reference material, and
``tools/exposure_check.sh`` keeps reference material out of this repository.
What this repository holds instead is a *pin*: the SHA256 of the fixture
manifest, of the parity plan and of every fixture file, in
``docs/migration/parity-matrix.json``. A fixture that does not hash to its pin
is refused, so a moved branch or an edited fixture cannot quietly change what
"parity" means.

Three kinds of test live here:

1. **Integrity** -- the checkout is the pinned one, and the matrix agrees with
   the reference's own parity plan. Needs the reference repository.
2. **Gates** -- one ``test_golden_fixture_gate[<fixture>]`` per fixture whose
   production implementation exists. Needs the reference repository.
3. **The registry guard** -- ``GATES`` below and the ``GATED`` fixtures in the
   matrix are the same set. Runs everywhere; this is the ratchet that makes a
   gate land with its capability.

Absent reference repository: every test in groups 1 and 2 skips, and a skip is
reported by ``tools/parity_status.py`` as ``NOT_EXECUTED``, never as a pass. CI
sets ``AIA_REQUIRE_REFERENCE_REPO=1`` once the deploy key exists, which turns
the skip into a failure.

Adding a gate when a capability lands: write ``_gate_<fixture>`` below, add it
to ``GATES``, flip the fixture to ``GATED`` in the matrix and add a
``golden_fixture`` gate to its capability. ``test_parity_matrix.py`` and the
registry guard fail until all three agree.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.sociomap import (
    LayoutResult,
    MapKind,
    Provenance,
    RelationMatrix,
    SociomapArtifact,
    SociomapSpec,
    ViewOverrides,
    apply_view_overrides,
)

REPO = Path(__file__).resolve().parents[3]
MATRIX = json.loads((REPO / "docs" / "migration" / "parity-matrix.json").read_text("utf-8"))
PIN = MATRIX["reference"]
FIXTURES: dict[str, dict[str, Any]] = MATRIX["fixtures"]
CAPTURED = sorted(fid for fid, fx in FIXTURES.items() if fx["status"] == "CAPTURED")

pytestmark = pytest.mark.golden


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_fixture(reference_repo: Path, fixture_id: str) -> dict[str, Any]:
    """Load a fixture, refusing one that does not hash to its pin."""
    record = FIXTURES[fixture_id]
    path = reference_repo / record["path"]
    actual = _sha256(path)
    assert actual == record["sha256"], (
        f"{fixture_id} hashes to {actual}, pinned {record['sha256']}; the reference "
        "checkout is not the pinned commit, or the fixture was edited"
    )
    body: dict[str, Any] = json.loads(path.read_text("utf-8"))
    assert body["fixture_id"] == fixture_id
    assert body["reference_zip_sha256"] == PIN["archive_sha256"]
    return body


# --------------------------------------------------------------------------- #
# 1. Integrity of the checkout
# --------------------------------------------------------------------------- #


def test_fixture_manifest_is_the_pinned_one(reference_repo: Path) -> None:
    actual = _sha256(reference_repo / "golden-fixtures" / "manifest.json")
    assert actual == PIN["fixture_manifest_sha256"], (
        f"fixture manifest hashes to {actual}; pinned {PIN['fixture_manifest_sha256']} "
        f"at {PIN['commit']}. Check out the pinned commit, or re-pin deliberately."
    )


def test_parity_plan_is_the_pinned_one(reference_repo: Path) -> None:
    assert _sha256(reference_repo / "parity-plan.json") == PIN["parity_plan_sha256"]


def test_manifest_lists_exactly_the_captured_fixtures(reference_repo: Path) -> None:
    manifest = json.loads((reference_repo / "golden-fixtures" / "manifest.json").read_text())
    listed = {f["fixture_id"]: f for f in manifest["fixtures"]}
    assert sorted(listed) == CAPTURED
    for fid in CAPTURED:
        assert listed[fid]["output_sha256"] == FIXTURES[fid]["sha256"], fid
        assert listed[fid]["capability_id"] == FIXTURES[fid]["capability"], fid
        assert listed[fid]["parity_type"] == FIXTURES[fid]["parity_type"], fid
        assert listed[fid]["tolerance"] == FIXTURES[fid]["tolerance"], fid


@pytest.mark.parametrize("fixture_id", CAPTURED)
def test_captured_fixture_matches_its_pin(reference_repo: Path, fixture_id: str) -> None:
    _load_fixture(reference_repo, fixture_id)


def test_matrix_agrees_with_the_reference_parity_plan(reference_repo: Path) -> None:
    """Parity type, tolerance and fixture links are the reference's call.

    Where production deliberately departs from a link, the departure is a
    recorded discrepancy with a reason -- never a silent edit.
    """
    plan = json.loads((reference_repo / "parity-plan.json").read_text())
    reference = {c["capability"]: c for c in plan["capabilities"]}
    ours = MATRIX["capabilities"]
    assert sorted(reference) == sorted(ours)
    rejected = {
        (d["rejected_fixture_link"]["capability"], d["rejected_fixture_link"]["fixture"])
        for d in MATRIX["reference_discrepancies"]
        if d.get("rejected_fixture_link")
    }
    for cid, ref in reference.items():
        cap = ours[cid]
        assert cap["parity_type"] == ref["parity_type"], cid
        assert cap["tolerance"] == ref["tolerance"], cid
        expected = sorted(f for f in ref["fixtures"] if (cid, f) not in rejected)
        captured = sorted(f for f in cap["fixtures"] if FIXTURES[f]["status"] == "CAPTURED")
        assert captured == expected, cid


# --------------------------------------------------------------------------- #
# 2. Gates -- one per fixture whose production implementation exists
# --------------------------------------------------------------------------- #


def _gate_f9_manual_drag_is_view_override(fixture: dict[str, Any]) -> None:
    """F9 (EXACT): a manual drag is a pure view override.

    The reference proves four discrete facts from its frontend: the rendered
    position changes, the underlying respondent point does not, the relation
    matrix does not, and the terrain cache key changes so the view recomputes.
    Production has no terrain cache; its equivalent of "the view recomputes" is
    that the displayed layout is a different value and names the moved entity.
    The cache-key *string* is a frontend implementation detail and is not
    compared -- the four facts are.

    The fixture places only the dragged respondent; the other three entities
    exist to carry the 4x4 relation matrix, and their positions are irrelevant
    to every fact asserted.
    """
    given = fixture["input"]
    expected = fixture["expected_output"]
    dragged = given["respondent_id"]
    matrix = expected["before"]["matrix"]
    entity_ids = (dragged, *(f"entity_{i}" for i in range(1, len(matrix))))
    base = given["base_position"]
    relation = RelationMatrix(
        entity_ids=entity_ids,
        values=tuple(tuple(float(v) for v in row) for row in matrix),
    )
    artifact = SociomapArtifact(
        spec=SociomapSpec(
            methodology_version="golden-fixture-F9",
            map_kind=MapKind.RESPONDENT,
            relation_method="fixture_supplied",
            matrix_transform="identity",
            normalization_method="none",
            missing_data_policy="fail",
            weighting_policy="unweighted",
            layout_algorithm="fixture_supplied",
            layout_parameters={},
            layout_seed=None,
            height_metric="none",
            colour_metric="none",
        ),
        entity_ids=entity_ids,
        relation=relation,
        layout=LayoutResult(
            algorithm="fixture_supplied",
            x=(base["x"], *(float(i) for i in range(1, len(matrix)))),
            y=(base["y"], *(0.0 for _ in range(1, len(matrix)))),
        ),
        provenance=Provenance(input_fingerprints={"relation": relation.fingerprint()}),
    )
    fingerprint_before = artifact.fingerprint()
    payload_before = artifact.model_dump(mode="json")

    no_drag = ViewOverrides(artifact_fingerprint=fingerprint_before)
    override = given["manual_override"]
    drag = no_drag.with_position(dragged, override["x"], override["y"])

    before = apply_view_overrides(artifact, no_drag)
    after = apply_view_overrides(artifact, drag)

    def displayed(layout: Any) -> dict[str, float]:
        i = layout.entity_ids.index(dragged)
        return {"x": layout.x[i], "y": layout.y[i]}

    def canonical() -> dict[str, float]:
        i = artifact.entity_ids.index(dragged)
        return {"x": artifact.layout.x[i], "y": artifact.layout.y[i]}

    # The positions, exactly.
    assert displayed(before) == expected["before"]["pos"]
    assert displayed(after) == expected["after"]["pos"]
    assert canonical() == expected["before"]["base_point"] == expected["after"]["base_point"]

    # The four discrete facts, each decided by production, compared exactly.
    observed = {
        "position_changed": displayed(after) != displayed(before),
        "base_point_unchanged": canonical() == expected["before"]["base_point"]
        and artifact.fingerprint() == fingerprint_before
        and artifact.model_dump(mode="json") == payload_before,
        "cache_key_changed": after != before and after.overridden == (dragged,),
        "relation_matrix_unchanged": [list(r) for r in artifact.relation.values] == matrix,
    }
    assert observed == {key: expected[key] for key in observed}


GATES: dict[str, Callable[[dict[str, Any]], None]] = {
    "F9_manual_drag_is_view_override": _gate_f9_manual_drag_is_view_override,
}


@pytest.mark.parametrize("fixture_id", sorted(GATES))
def test_golden_fixture_gate(reference_repo: Path, fixture_id: str) -> None:
    GATES[fixture_id](_load_fixture(reference_repo, fixture_id))


# --------------------------------------------------------------------------- #
# 3. The registry guard -- runs everywhere
# --------------------------------------------------------------------------- #


def test_gate_registry_matches_the_matrix() -> None:
    """``GATES`` here and ``GATED`` in the matrix are one set, from both sides."""
    gated = {fid for fid, fx in FIXTURES.items() if fx["gate"]["state"] == "GATED"}
    assert set(GATES) == gated, {
        "registered but not GATED in the matrix": sorted(set(GATES) - gated),
        "GATED in the matrix but not registered": sorted(gated - set(GATES)),
    }
