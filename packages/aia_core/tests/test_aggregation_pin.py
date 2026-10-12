"""What a run pins for its aggregation (plan ``methodology-tab.md`` G3a).

With nothing stored a run pins 18.6.6's port: ``aia-aggregate-1``, no formula replaced. A
stored version pins its whole specification and the formulas it replaces; a formula the
aggregate does not read is refused, never pinned. Reading a pin back compiles each replaced
formula into the slot the aggregate reads, and a pin that does not read fails loudly.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.methodology.pins import (
    UNIT_AGGREGATION_PIN,
    FormulaNotComputed,
    aggregation_pin_for,
    read_aggregation_pin,
)
from aia_core.domain.research_aggregate import AIA_AGGREGATE_V1, TOP_BOX


def _payload(**formulas: str) -> dict[str, Any]:
    spec = AIA_AGGREGATE_V1.model_dump(mode="json")
    spec["methodology_version"] = "aia-aggregate-1+e1"
    spec["top_box"] = 3
    return {"spec": spec, "formulas": dict(formulas)}


def test_with_nothing_stored_a_run_pins_the_units_port() -> None:
    assert aggregation_pin_for(None) == UNIT_AGGREGATION_PIN
    assert read_aggregation_pin(None) == (AIA_AGGREGATE_V1, {})
    method, slots = read_aggregation_pin(UNIT_AGGREGATION_PIN)
    assert method == AIA_AGGREGATE_V1 and slots == {}


def test_a_version_is_pinned_whole_and_its_formulas_read_back_as_slots() -> None:
    pin = aggregation_pin_for({**_payload(**{TOP_BOX: "x >= top"}), "contract": "x"})
    assert pin == _payload(**{TOP_BOX: "x >= top"})  # only spec and formulas are pinned
    method, slots = read_aggregation_pin(pin)
    assert method.top_box == 3 and set(slots) == {TOP_BOX}
    assert slots[TOP_BOX](x=4.0, top=5.0, b=3.0) == 0.0  # the replaced rule, not the built-in


def test_a_formula_the_aggregate_does_not_read_is_refused() -> None:
    with pytest.raises(FormulaNotComputed):
        aggregation_pin_for(_payload(**{"agg.median": "x"}))
    with pytest.raises(ValueError, match="no formula"):
        read_aggregation_pin(_payload(**{"f6.distance": "1"}))


@pytest.mark.parametrize(
    "stored",
    [
        "aia-aggregate-1",
        {"spec": {"top_box": 2}, "formulas": {}},
        _payload(**{TOP_BOX: "open('x')"}),
    ],
)
def test_a_pin_that_does_not_read_fails_loudly(stored: Any) -> None:
    with pytest.raises(ValueError):
        read_aggregation_pin(stored)
