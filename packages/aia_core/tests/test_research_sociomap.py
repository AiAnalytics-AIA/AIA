"""A research run's Sociomap: the unit's relations, AIA's engine, internal only (chunk 6).

The relation matrix is ported from ``sociomap.py`` ``derive_relation_matrix`` and
compared EXACT against captures of the unit (``tools/aggregate_capture.py``). The
map is AIA's deterministic engine under the preset ``AIA_SOCIOMAP_V1``. Whatever
is built, PROGRESS D6 is open, so it is ``INTERNAL_ONLY`` and a client-facing
surface is refused.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from aia_core.domain.fieldwork import FieldworkDataset
from aia_core.domain.research_design import ResearchSpecification, compile_design
from aia_core.domain.research_sociomap import (
    D6_OPEN,
    MethodologyStatus,
    SociomapNotApproved,
    battery_sociomap,
    derive_relation_matrix,
    require_client_facing,
    research_sociomaps,
)
from aia_core.domain.sociomap import AIA_SOCIOMAP_V1
from aia_core.domain.synthetic_fieldwork import synthetic_dataset

FIXTURES = Path(__file__).parent / "fixtures" / "research_sociomap"
CASES = Path(__file__).parent / "fixtures" / "research_aggregate" / "cases"
UNIT = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case(case_id: str) -> tuple[ResearchSpecification, FieldworkDataset]:
    case = json.loads((CASES / f"{case_id}.json").read_text(encoding="utf-8"))
    return (
        ResearchSpecification.model_validate(case["spec"]),
        FieldworkDataset.model_validate(case["dataset"]),
    )


def test_every_capture_and_the_unit_it_came_from_are_pinned() -> None:
    for name, digest in INDEX["files"].items():
        assert _sha256(FIXTURES / name) == digest, f"{name} changed; recapture, never edit"
    for name, digest in INDEX["unit_sources"].items():
        assert _sha256(UNIT / name) == digest, f"the unit's {name} changed; recapture"
    for name, digest in INDEX["cases"].items():
        assert _sha256(CASES / name) == digest, f"input case {name} changed; recapture"
    assert INDEX["files"], "at least one relation matrix is captured"


@pytest.mark.parametrize("name", sorted(INDEX["files"]))
def test_the_relation_matrix_is_exact_against_the_unit(name: str) -> None:
    captured = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    spec, dataset = _case(captured["case_id"])
    battery = next(b for b in spec.batteries if b.id == captured["battery_id"])
    ours = battery_sociomap(battery, dataset)
    assert [o["id"] for o in ours["objects"]] == captured["object_ids"]
    for mine, theirs in zip(ours["relation"]["matrix"], captured["matrix"], strict=True):
        for a, b in zip(mine, theirs, strict=True):
            assert math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
    for a, b in zip(ours["relation"]["scores"], captured["scores"], strict=True):
        assert (a is None and b is None) or math.isclose(a, b, rel_tol=0, abs_tol=1e-9)


def test_the_map_is_the_engines_under_the_adopted_preset_and_internal_only() -> None:
    spec, dataset = _case("A01_full_questionnaire")
    result = research_sociomaps(spec, dataset)
    assert D6_OPEN and result["methodology_status"] == MethodologyStatus.INTERNAL_ONLY.value
    assert result["data_origin"] == "SYNTHETIC_FIXTURE"
    (one,) = result["batteries"]
    assert one["methodology_status"] == "INTERNAL_ONLY"
    assert one["preset"] == AIA_SOCIOMAP_V1.methodology_version
    artifact = one["sociomap"]
    assert artifact["kind"] == "sociomap" and artifact["object_ids"] == [
        o["id"] for o in one["objects"]
    ]
    assert artifact["spec"]["layout"] == AIA_SOCIOMAP_V1.layout.model_dump(mode="json")
    assert artifact["layout"]["converged"] is True
    # Deterministic: the same dataset draws the same map.
    assert research_sociomaps(spec, dataset) == result


def test_no_client_facing_surface_may_render_it_while_d6_is_open() -> None:
    spec, dataset = _case("A01_full_questionnaire")
    result = research_sociomaps(spec, dataset)
    for sociomap in (result, *result["batteries"]):
        with pytest.raises(SociomapNotApproved, match="INTERNAL_ONLY"):
            require_client_facing(sociomap)
    with pytest.raises(SociomapNotApproved):
        require_client_facing({})  # fails closed on anything without a status
    require_client_facing({"methodology_status": "CLIENT_FACING"})  # what approval would allow


def test_the_battery_scale_is_the_datas_and_is_recorded() -> None:
    spec, problems = compile_design(
        {
            "n": 80,
            "sections": [
                {
                    "type": "object_battery",
                    "object_family": "značky",
                    "objects": ["A", "B", "C", "D"],
                    "scale": [1, 5],
                }
            ],
        }
    )
    assert spec is not None, problems
    one = battery_sociomap(spec.batteries[0], synthetic_dataset(spec, seed=3))
    assert one["rating_scale"] == [1, 5]
    assert one["sociomap"]["spec"]["ratings"]["rating_scale_max"] == 5.0


def test_too_few_common_ratings_is_the_units_neutral_relation() -> None:
    ratings = [[1.0, None, 3.0], [2.0, None, 4.0], [3.0, 5.0, 5.0], [4.0, 6.0, 6.0]]
    relation, scores = derive_relation_matrix(ratings, [1.0] * 4)
    assert relation[0][1] == relation[1][0] == 5.5
    assert [relation[i][i] for i in range(3)] == [0.0, 0.0, 0.0]
    assert scores[1] == 5.5


def test_a_design_without_a_tracked_set_has_no_sociomap_and_says_so() -> None:
    spec, dataset = _case("A02_indicative_support")
    result = research_sociomaps(spec, dataset)
    assert result["batteries"] == [] and "Sociomapa nevznikla" in result["note"]
    assert result["methodology_status"] == "INTERNAL_ONLY"


def test_perfect_positive_and_negative_co_movement_are_the_scale_ends() -> None:
    rising = [[float(i), float(i), float(10 - i)] for i in range(1, 9)]
    relation, _ = derive_relation_matrix(rising, [1.0] * 8)
    assert relation[0][1] == pytest.approx(10.0) and relation[0][2] == pytest.approx(1.0)


def test_an_unrated_object_has_no_score_rather_than_a_guess() -> None:
    _, scores = derive_relation_matrix([[1.0, None], [2.0, None]], [1.0, 1.0])
    assert scores == [1.5, None]
