"""A research run's Sociomap: the unit's relations, AIA's engine, internal only (chunk 6).

The relation matrix is ported from ``sociomap.py`` ``derive_relation_matrix`` and
compared EXACT against captures of the unit (``tools/aggregate_capture.py``). The
map is AIA's deterministic engine under the preset ``AIA_SOCIOMAP_V1``. Whatever
is built, PROGRESS D6 is open, so it is ``INTERNAL_ONLY`` and a client-facing
surface is refused.

Beside the unit's matrix, each pair carries what the audit "NPC Sociomapa: faulty
formulas in the code" (F3) says it can be: its signed correlation, rater count,
Fisher interval and status (plan sociomap-formula-corrections, chunk 1a).
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
    PAIR_CONFIDENCE,
    MethodologyStatus,
    PairRelations,
    SociomapNotApproved,
    battery_sociomap,
    derive_pair_relations,
    derive_relation_matrix,
    require_client_facing,
    research_sociomaps,
)
from aia_core.domain.sociomap import AIA_SOCIOMAP_V1
from aia_core.domain.sociomap.relations import AUDIT_PROVISIONAL_N_MIN, PairStatus
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


# ------------------------------------------- pair status beside the unit (F3) --


def _pairs(
    ratings: list[list[float | None]], weights: list[float] | None = None, n_min: int = 30
) -> PairRelations:
    return derive_pair_relations(
        ratings,
        weights if weights is not None else [1.0] * len(ratings),
        n_min=n_min,
        confidence=PAIR_CONFIDENCE,
    )


def test_a_pair_rated_by_too_few_is_unknown_where_the_unit_stamps_five_and_a_half() -> None:
    # Finding F-1 of the plan: the unit's matrix keeps its 5.5 (aia-sociomap-1 is
    # the unit's formula); the pair status says that number is not a relation.
    ratings: list[list[float | None]] = [
        [1.0, None, 3.0],
        [2.0, None, 4.0],
        [3.0, 5.0, 5.0],
        [4.0, 6.0, 6.0],
    ]
    relation, _ = derive_relation_matrix(ratings, [1.0] * 4)
    pairs = _pairs(ratings)
    assert relation[0][1] == 5.5
    assert pairs.n[0][1] == 2 and pairs.status[0][1] is PairStatus.UNKNOWN
    assert pairs.interval[0][1] is None  # two raters have no standard error
    assert pairs.n[0][2] == 4 and pairs.r[0][2] == pytest.approx(1.0)
    assert pairs.status[0][2] is PairStatus.UNKNOWN  # perfect, and still only four raters
    assert pairs.counts() == {"unknown": 3, "reliable": 0, "weak": 0}


def test_the_signed_correlation_is_the_one_the_unit_mapped_onto_one_to_ten() -> None:
    spec, dataset = _case("A01_full_questionnaire")
    relation = battery_sociomap(spec.batteries[0], dataset)["relation"]
    m = len(relation["matrix"])
    for i in range(m):
        for j in range(m):
            if i == j:
                assert relation["r"][i][j] is None and relation["status"][i][j] is None
                continue
            # The unit: strength = 1 + 9 (r + 1) / 2, every pair here over 5 raters.
            unit_r = (relation["matrix"][i][j] - 1.0) / 4.5 - 1.0
            assert relation["r"][i][j] == pytest.approx(unit_r, abs=1e-12)
            assert relation["r"][i][j] == relation["r"][j][i]


def test_the_stored_relation_names_its_rule_and_its_provisional_n_min() -> None:
    spec, dataset = _case("A01_full_questionnaire")
    relation = battery_sociomap(spec.batteries[0], dataset)["relation"]
    assert relation["n_min"] == AUDIT_PROVISIONAL_N_MIN == 30
    assert relation["confidence"] == 0.95
    assert "audit F3" in relation["status_rule"] and "Q6" in relation["status_rule"]
    assert "read status before matrix" in relation["matrix_caveat"]
    m = len(relation["matrix"])
    assert sum(relation["status_counts"].values()) == m * (m - 1) // 2
    # Every pair here has 450 raters; one is too weak to tell from zero.
    assert relation["status_counts"] == {"unknown": 0, "reliable": 9, "weak": 1}
    for i in range(m):
        for j in range(m):
            if i != j and relation["status"][i][j] == "reliable":
                low, high = relation["interval"][i][j]
                assert low > 0 or high < 0


def test_a_constant_column_has_no_correlation_rather_than_a_zero_one() -> None:
    # The unit reads a constant column as r = 0 (5.5); here it has no correlation.
    rows: list[list[float | None]] = [[float(k % 7), 4.0, float(k % 5)] for k in range(60)]
    weights = [1.0 + (k % 3) / 7 for k in range(60)]  # unequal: rounding must not invent r
    relation, _ = derive_relation_matrix(rows, weights)
    pairs = _pairs(rows, weights)
    assert relation[0][1] == 5.5
    assert pairs.r[0][1] is None and pairs.r[1][2] is None
    assert pairs.n[0][1] == 60 and pairs.status[0][1] is PairStatus.UNKNOWN
    assert pairs.interval[0][1] is None
    assert pairs.r[0][2] is not None


def test_a_respondent_without_a_positive_finite_weight_rates_no_pair() -> None:
    rows: list[list[float | None]] = [[float(k), float(k), float(-k)] for k in range(40)]
    weights = [1.0] * 40
    weights[0], weights[1], weights[2] = math.nan, 0.0, -1.0
    assert _pairs(rows, weights).n[0][1] == 37


def test_a_planted_strong_pair_is_reliable_and_an_unrelated_one_is_not() -> None:
    rows: list[list[float | None]] = [
        [float(k % 10 + 1), float(k % 10 + 1), float((k * 7) % 10 + 1)] for k in range(200)
    ]
    pairs = _pairs(rows)
    assert pairs.r[0][1] == pytest.approx(1.0)
    assert pairs.status[0][1] is PairStatus.RELIABLE
    assert pairs.status[0][2] is not PairStatus.UNKNOWN


def test_n_min_is_the_callers_and_is_recorded() -> None:
    rows: list[list[float | None]] = [
        [float(k % 10 + 1), float(k % 10 + 1), float((k * 7) % 10 + 1)] for k in range(20)
    ]
    assert _pairs(rows, n_min=30).status[0][1] is PairStatus.UNKNOWN
    loose = _pairs(rows, n_min=10)
    assert loose.status[0][1] is PairStatus.RELIABLE and loose.n_min == 10


def test_pair_relations_refuse_a_ragged_matrix_or_a_diagonal_value() -> None:
    good = _pairs([[1.0, 2.0, 3.0], [2.0, 1.0, 3.0], [3.0, 3.0, 1.0]])
    body = good.model_dump()
    with pytest.raises(ValueError, match="diagonal"):
        PairRelations.model_validate({**body, "n": [[3, 3, 3], [3, None, 3], [3, 3, None]]})
    with pytest.raises(ValueError, match="matrix like r"):
        PairRelations.model_validate({**body, "status": [[None, "weak"], ["weak", None]]})
