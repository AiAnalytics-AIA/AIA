"""How many decimal places a run stores, editable as an aggregation version (plan V1b).

The preset keeps 18.6.6's places, so the unit's aggregate is byte for byte what it was; a
version that changes them is stored rounded, named as a deviation, read back by analysis at the
same places (never rounded again) and refused outside 0-3 whole places.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.analysis.native import native_evidence
from aia_core.domain.evidence.support import AIA_SUPPORT_V1, REFERENCE_THRESHOLDS
from aia_core.domain.methodology.aggregation import AGGREGATION
from aia_core.domain.methodology.pins import read_aggregation_pin
from aia_core.domain.methodology.versions import (
    MethodologyVersionInvalid,
    named,
    spec_as_computed,
    validate_version,
)
from aia_core.domain.research_aggregate import (
    AIA_AGGREGATE_V1,
    AggregationSpec,
    RoundingSpec,
    aggregate_dataset,
    stored_decimals,
)
from aia_core.domain.research_design import compile_design
from aia_core.domain.synthetic_fieldwork import synthetic_dataset

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj (fiktivní)",
    "n": 200,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
                {
                    "id": "q3",
                    "text": "Co ještě snídáte?",
                    "typ": "multi",
                    "kategorie": ["Pečivo", "Ovoce", "Nic"],
                },
            ],
        }
    ],
}


def _method(share: int, mean: int) -> AggregationSpec:
    return AIA_AGGREGATE_V1.model_copy(
        update={
            "methodology_version": "aia-aggregate-1+e1",
            "rounding": RoundingSpec(share_decimals=share, mean_decimals=mean),
        }
    )


def _aggregate(method: AggregationSpec = AIA_AGGREGATE_V1) -> tuple[Any, Any, dict[str, Any]]:
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    dataset = synthetic_dataset(spec, seed=20260816)
    return spec, dataset, aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1, method=method)


def _places(value: float) -> int:
    text = repr(float(value))
    return 0 if text.endswith(".0") else len(text.split(".")[1])


def test_the_aggregate_stores_its_numbers_at_the_versions_places() -> None:
    _, _, unit = _aggregate()
    assert "rounding" not in unit and "deviation" not in unit
    _, _, edited = _aggregate(_method(0, 3))
    assert edited["rounding"] == {"share_decimals": 0, "mean_decimals": 3}
    changed = {c["path"] for c in edited["deviation"]["changed"]}
    assert changed == {"rounding.share_decimals", "rounding.mean_decimals"}
    for name in ("q2", "q3"):
        q = edited["questions"][name]
        for option, value in q["celkem_pct"].items():
            assert value == round(value), (name, option, value)
            assert q["intervaly_95"][option]["low"] == round(q["intervaly_95"][option]["low"])
    scale = edited["questions"]["q1"]
    assert scale["prumer"] == round(scale["prumer"], 3) and _places(scale["sd"]) <= 3
    assert scale["top2box_pct"] == round(scale["top2box_pct"])
    # The same computation: only the stored places moved.
    unit_mean = unit["questions"]["q1"]["prumer"]
    assert abs(scale["prumer"] - unit_mean) < 0.005


def test_analysis_admits_each_number_at_the_places_the_aggregate_stored() -> None:
    for share, mean in ((0, 3), (2, 1), (1, 2)):
        spec, dataset, aggregate = _aggregate(_method(share, mean))
        evidence = native_evidence(
            spec,
            aggregate,
            dataset_sha256="d" * 64,
            origin=dataset.origin,
            support=REFERENCE_THRESHOLDS,
        )
        rows = evidence.table.rows
        pct = rows["q2.pct.1"]
        assert (
            pct.decimals == share
            and pct.value == aggregate["questions"]["q2"]["celkem_pct"]["Kávu"]
        )
        assert rows["q1.mean"].decimals == mean and rows["q1.top2box"].decimals == share


def test_an_aggregate_without_a_block_reads_as_the_units_places() -> None:
    _, _, unit = _aggregate()
    assert stored_decimals(unit) == RoundingSpec(share_decimals=1, mean_decimals=2)
    with pytest.raises(ValueError):
        stored_decimals({"rounding": {"share_decimals": 9, "mean_decimals": 2}})


def test_a_pin_stored_before_rounding_was_declared_reads_as_the_units() -> None:
    old = AIA_AGGREGATE_V1.model_dump(mode="json")
    del old["rounding"]
    spec, slots = read_aggregation_pin({"spec": old, "formulas": {}})
    assert spec.rounding == AIA_AGGREGATE_V1.rounding and slots == {}


def test_a_stored_spec_without_rounding_reads_as_its_runs_compute_it() -> None:
    old = AIA_AGGREGATE_V1.model_dump(mode="json")
    del old["rounding"]
    old["bootstrap"]["reps"] = 200
    shown = spec_as_computed(AGGREGATION, "aia-aggregate-1", old)
    assert shown["rounding"] == {"share_decimals": 1, "mean_decimals": 2}
    assert shown["bootstrap"]["reps"] == 200 and "rounding" not in old
    # A stored value always wins; what no preset type reads is shown as stored.
    assert spec_as_computed(AGGREGATION, "aia-aggregate-1", {"bootstrap": 1}) == {"bootstrap": 1}
    assert spec_as_computed(AGGREGATION, "no-such-preset", old) == old


def _validate(**rounding: Any) -> Any:
    spec = AIA_AGGREGATE_V1.model_dump(mode="json")
    spec["rounding"].update(rounding)
    return validate_version(
        AGGREGATION,
        base_preset="aia-aggregate-1",
        spec=spec,
        formulas={},
        version_name=named("aia-aggregate-1", 1),
    )


def test_a_version_moves_the_places_from_0_to_3() -> None:
    assert _validate(share_decimals=0, mean_decimals=3).spec.rounding.share_decimals == 0


@pytest.mark.parametrize(
    "rounding",
    [
        {"share_decimals": 4},
        {"share_decimals": -1},
        {"mean_decimals": 1.5},
        {"mean_decimals": True},
        {"share_decimals": "1"},
    ],
)
def test_places_outside_0_to_3_whole_are_refused(rounding: dict[str, Any]) -> None:
    with pytest.raises(MethodologyVersionInvalid) as refused:
        _validate(**rounding)
    assert any(k.startswith("spec.rounding") for k in refused.value.problems), refused.value


def test_the_preview_writes_example_numbers_at_the_drafts_places() -> None:
    assert AGGREGATION.preview is not None
    unit = AGGREGATION.preview(AIA_AGGREGATE_V1)
    assert [line.step_id for line in unit] == ["round_share", "round_share", "round_mean"]
    assert unit[0].message_cs == "Ranní nápoj: Kávu: 38,5 % (34,1\u201342,9 %)"
    assert unit[2].message_cs.endswith("průměr 7,43 (7,21\u20137,65), SD 1,82")
    whole = AGGREGATION.preview(_method(0, 3))
    assert whole[0].message_cs == "Ranní nápoj: Kávu: 38 % (34\u201343 %)"
    assert "průměr 7,432 (7,209\u20137,651), SD 1,818" in whole[2].message_cs
