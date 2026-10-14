"""An aggregate that is no longer 18.6.6's port says so (plan ``methodology-tab.md`` G2c).

Under ``aia-aggregate-1`` with no estimator replaced the aggregate is the unit's port, byte for
byte, and carries no deviation (the parity self-fixture holds that). Any changed value or any
replaced formula adds a ``deviation`` block naming each; a renamed version that changes nothing
computes the unit's numbers and is not a departure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aia_core.domain.evidence.support import AIA_SUPPORT_V1
from aia_core.domain.fieldwork import FieldworkDataset
from aia_core.domain.methodology.aggregation_formulas import AGGREGATION_FORMULAS
from aia_core.domain.methodology.expressions import compile_formula
from aia_core.domain.research_aggregate import (
    AIA_AGGREGATE_V1,
    DEVIATION_NOTE,
    MEAN,
    TOP_BOX,
    AggregationSpec,
    aggregate_dataset,
    aggregation_deviation,
)
from aia_core.domain.research_design import ResearchSpecification

FIXTURES = Path(__file__).parent / "fixtures" / "research_aggregate"
CASE = sorted((FIXTURES / "cases").glob("*.json"))[0]
SLOT = {f.slot.id: f.slot for f in AGGREGATION_FORMULAS}


def _edited(**changes: Any) -> AggregationSpec:
    data = AIA_AGGREGATE_V1.model_dump(mode="json")
    data["methodology_version"] = "aia-aggregate-1+e1"
    for path, value in changes.items():
        node = data
        *parents, leaf = path.split("__")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return AggregationSpec.model_validate(data)


def _aggregate(**kwargs: Any) -> dict[str, Any]:
    case = json.loads(CASE.read_text(encoding="utf-8"))
    spec = ResearchSpecification.model_validate(case["spec"])
    dataset = FieldworkDataset.model_validate(case["dataset"])
    return aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1, **kwargs)


def test_the_units_port_carries_no_deviation() -> None:
    assert aggregation_deviation(AIA_AGGREGATE_V1, {}) is None
    assert "deviation" not in _aggregate()
    assert "deviation" not in _aggregate(method=AIA_AGGREGATE_V1, slots={})


def test_a_renamed_version_that_changes_nothing_is_not_a_departure() -> None:
    assert aggregation_deviation(_edited(), {}) is None
    assert _aggregate(method=_edited()) == _aggregate()


def test_a_changed_value_is_named_and_the_numbers_follow_it() -> None:
    method = _edited(bootstrap__reps=200, top_box=3)
    departure = aggregation_deviation(method, {})
    assert departure == {
        "from": "aia-aggregate-1",
        "methodology_version": "aia-aggregate-1+e1",
        "changed": [
            {"path": "bootstrap.reps", "unit": 400, "used": 200},
            {"path": "top_box", "unit": 2, "used": 3},
        ],
        "replaced_formulas": [],
        "note_cs": DEVIATION_NOTE,
    }
    edited, unit = _aggregate(method=method), _aggregate()
    assert edited["deviation"] == departure
    scale = next(k for k, q in unit["questions"].items() if q["typ"] == "skala")
    assert edited["questions"][scale]["top2box_pct"] >= unit["questions"][scale]["top2box_pct"]


def test_a_replaced_formula_is_named_even_under_the_units_values() -> None:
    slots = {
        TOP_BOX: compile_formula(SLOT[TOP_BOX], "x >= top"),
        MEAN: compile_formula(SLOT[MEAN], "sum(w * x) / sum(w)"),  # its own built-in, still named
    }
    departure = aggregation_deviation(AIA_AGGREGATE_V1, slots)
    assert departure is not None
    assert departure["changed"] == [] and departure["replaced_formulas"] == [MEAN, TOP_BOX]
    assert _aggregate(slots=slots)["deviation"] == departure
