"""A research run's experimental Sociomapping, on fictional data (``research_sociomapping``).

Independent checks where arithmetic allows: correlations and average answers are recomputed
here from the raw answers by a separate, plain implementation. The layout is AIA's
experimental candidate; nothing here tests equivalence with SOMECS.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.fieldwork import DataOrigin, FieldworkDataset
from aia_core.domain.research_design import ResearchSpecification, compile_design
from aia_core.domain.research_sociomapping import (
    METHOD_STATUS,
    SOCIOMAPPING_VERSION,
    ExperimentalNotClientFacing,
    battery_sociomapping,
    require_not_client_facing,
    research_sociomappings,
)
from aia_core.domain.sociomap.hmodel_candidate import CandidateParameters
from aia_core.domain.synthetic_fieldwork import synthetic_dataset

FAST = CandidateParameters(random_starts=1)


def _spec(
    objects: list[str], scale: tuple[int, int] = (1, 10), n: int = 120
) -> ResearchSpecification:
    spec, problems = compile_design(
        {
            "n": n,
            "sections": [
                {
                    "type": "object_battery",
                    "object_family": "značky",
                    "objects": objects,
                    "scale": list(scale),
                }
            ],
        }
    )
    assert spec is not None, problems
    return spec


def _dataset(spec: ResearchSpecification, rows: list[list[int | None]]) -> FieldworkDataset:
    battery = spec.batteries[0]
    respondents = []
    for i, row in enumerate(rows):
        answers: dict[str, Any] = {}
        for obj, value in zip(battery.objects, row, strict=True):
            answers[battery.question_id(obj)] = value
        respondents.append(
            {
                "respondent_id": f"FIC-{i:03d}",
                "donor_id": f"FIC-D{i:03d}",
                "weight": 1.0 + i % 3,
                "answers": answers,
            }
        )
    return FieldworkDataset.model_validate(
        {
            "dataset_version": "test",
            "generator": "hand-written fictional answers",
            "origin": DataOrigin.SYNTHETIC_FIXTURE.value,
            "respondents": respondents,
            "seed": 0,
            "source": "synthetic_fixture",
            "spec_fingerprint": spec.fingerprint(),
        }
    )


def _pearson(a: list[float], b: list[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True))
    return num / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


def test_a_representative_study_is_mapped_experimental_and_never_client_facing() -> None:
    spec = _spec(["Altair", "Borealis", "Cirrus", "Delta", "Echo", "Fjord"])
    dataset = synthetic_dataset(spec, seed=20261005)
    result = research_sociomappings(spec, dataset, FAST)
    assert result["sociomapping_version"] == SOCIOMAPPING_VERSION
    assert result["method_status"] == METHOD_STATUS == "EXPERIMENTAL_AIA"
    assert result["client_facing"] is False and result["synthetic_data"] is True
    assert result["data_origin"] == "SYNTHETIC_FIXTURE"
    assert result["method"]["name"] == "aia_hmodel_candidate_v1"
    assert result["method"]["evaluator"] == "aia_hmodel_accuracy_v1"
    (one,) = result["batteries"]
    assert one["status"] == "MAPPED"
    layout = one["layout"]
    assert sorted(layout["element_ids"]) == sorted(o["id"] for o in one["objects"])
    assert layout["accuracy"]["overall"] is not None
    assert layout["accuracy"]["overall"] >= layout["baseline_classical_mds"] - 1e-12
    assert {"RTS-N1", "RTS-O1", "RTS-W3", "AIA-D1", "AIA-D2", "AIA-H9"} <= set(one["rules"])
    codes = {lim["code"] for lim in one["limitations"]}
    assert {"EXPERIMENTAL_METHOD", "NO_RESPONDENT_PLACEMENT", "NO_HEIGHT_SURFACE"} <= codes
    assert one["support"]["weighting"] == "UNWEIGHTED"
    assert research_sociomappings(spec, dataset, FAST) == result  # deterministic
    with pytest.raises(ExperimentalNotClientFacing, match="experimental"):
        require_not_client_facing(result)


def test_relations_and_heights_match_an_independent_computation() -> None:
    spec = _spec(["A", "B", "C", "D"])
    dataset = synthetic_dataset(spec, seed=7)
    one = battery_sociomapping(spec.batteries[0], dataset, FAST)
    battery = spec.batteries[0]
    columns = [
        [float(r.answers[battery.question_id(o)]) for r in dataset.respondents]  # type: ignore[arg-type]
        for o in battery.objects
    ]
    assert one["support"]["respondents_complete"] == len(dataset.respondents)
    matrix = one["relations"]["matrix"]
    for i in range(4):
        for j in range(4):
            if i != j:
                assert matrix[i][j] == pytest.approx(_pearson(columns[i], columns[j]), abs=1e-12)
    for i, column in enumerate(columns):
        assert one["heights"]["on_scale"][i] == pytest.approx(sum(column) / len(column), abs=1e-9)


def test_difficult_answers_are_kept_named_and_explained() -> None:
    # Fictional answers: A and B move together, C moves against them (negative r),
    # D is answered 4 by everyone (constant), and two respondents skip an object.
    spec = _spec(["A", "B", "C", "D"])
    rows: list[list[int | None]] = [
        [2, 3, 9, 4],
        [4, 4, 7, 4],
        [6, 7, 4, 4],
        [8, 8, 2, 4],
        [9, 10, 1, 4],
        [5, 5, 6, 4],
        [3, None, 8, 4],
        [7, 6, None, 4],
    ]
    one = battery_sociomapping(spec.batteries[0], _dataset(spec, rows), FAST)
    support = one["support"]
    assert (support["respondents_complete"], support["respondents_excluded"]) == (6, 2)
    assert support["missing_by_object"] == {"a": 0, "b": 1, "c": 1, "d": 0}
    relations = one["relations"]
    assert relations["support"] == 6
    ids = [o["id"] for o in one["objects"]]
    a, b, c = ids.index("a"), ids.index("b"), ids.index("c")
    assert relations["matrix"][a][c] < 0 < relations["matrix"][a][b]  # kept signed
    assert {tuple(p[:2]) for p in relations["negative_pairs"]} == {("a", "c"), ("b", "c")}
    assert ["a", "d", "every answer equal for d"] in relations["undefined"]
    assert one["fuzzy"]["available"] is False and "no correlation" in one["fuzzy"]["reason"]
    assert one["coherences"]["available"] is False
    layout = one["layout"]
    assert one["status"] == "MAPPED" and layout["element_ids"] == ["a", "b", "c"]
    assert layout["unplaced"] == [
        {"element_id": "d", "reason": "no defined relation: every answer equal for d"}
    ]
    # The constant object still has its height: everyone answered 4.
    assert one["heights"]["on_scale"][ids.index("d")] == pytest.approx(4.0)
    codes = {lim["code"] for lim in one["limitations"]}
    assert {"COMPLETE_RESPONDENTS_ONLY", "NEGATIVE_CORRELATIONS_KEPT", "UNPLACED_OBJECTS"} <= codes


def test_negative_correlations_alone_block_the_0_1_matrix_by_name_not_the_map() -> None:
    spec = _spec(["A", "B", "C"])
    rows: list[list[int | None]] = [[2, 3, 9], [4, 4, 7], [6, 7, 4], [8, 8, 2], [9, 10, 1]]
    one = battery_sociomapping(spec.batteries[0], _dataset(spec, rows), FAST)
    assert one["status"] == "MAPPED"
    assert one["fuzzy"]["available"] is False and "M12" in one["fuzzy"]["reason"]
    assert one["coherences"] == one["fuzzy"]
    assert len(one["relations"]["negative_pairs"]) == 2


def test_insufficient_support_is_not_mapped_and_says_why() -> None:
    spec = _spec(["A", "B", "C"])
    rows: list[list[int | None]] = [[1, 2, 3], [4, None, 6], [None, 5, 5]]
    one = battery_sociomapping(spec.batteries[0], _dataset(spec, rows), FAST)
    assert one["status"] == "NOT_MAPPED" and one["layout"] is None
    assert "insufficient support: 1 respondent(s)" in one["reason"]


def test_every_relation_equal_has_no_order_to_lay_out() -> None:
    spec = _spec(["A", "B", "C"])
    rows: list[list[int | None]] = [[1, 1, 1], [5, 5, 5], [9, 9, 9], [3, 3, 3]]
    one = battery_sociomapping(spec.batteries[0], _dataset(spec, rows), FAST)
    assert one["status"] == "NOT_MAPPED" and "no order" in one["reason"]
    assert one["relations"]["matrix"][0][1] == pytest.approx(1.0)  # still reported


def test_reordering_the_objects_in_the_design_moves_nothing() -> None:
    rows: list[list[int | None]] = [
        [2, 3, 9, 5],
        [4, 4, 7, 6],
        [6, 7, 4, 2],
        [8, 8, 2, 9],
        [9, 10, 1, 3],
        [5, 5, 6, 7],
    ]
    first = _spec(["A", "B", "C", "D"])
    second = _spec(["D", "B", "A", "C"])
    reordered = [[r[3], r[1], r[0], r[2]] for r in rows]
    one = battery_sociomapping(first.batteries[0], _dataset(first, rows), FAST)
    two = battery_sociomapping(second.batteries[0], _dataset(second, reordered), FAST)
    where = lambda b: dict(  # noqa: E731
        zip(b["layout"]["element_ids"], map(tuple, b["layout"]["positions"]), strict=True)
    )
    assert where(one) == where(two)
    assert one["layout"]["accuracy"]["overall"] == two["layout"]["accuracy"]["overall"]


def test_a_design_without_a_tracked_set_has_none_and_says_so() -> None:
    case = json.loads(
        (
            Path(__file__).parent / "fixtures/research_aggregate/cases/A02_indicative_support.json"
        ).read_text(encoding="utf-8")
    )
    spec = ResearchSpecification.model_validate(case["spec"])
    dataset = FieldworkDataset.model_validate(case["dataset"])
    result = research_sociomappings(spec, dataset, FAST)
    assert result["batteries"] == [] and "mapa nevznikla" in result["note"]
    assert result["method_status"] == "EXPERIMENTAL_AIA" and result["client_facing"] is False

