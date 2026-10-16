"""Aggregation on the Metodika tab (plan ``methodology-tab.md`` G2a).

What every registered module must be (complete, pinned, its tests present) is held by
``test_methodology.py``; this file pins what is particular to this one: the values 18.6.6
wrote inline are declared in one specification whose preset is the unit's literals, bit for
bit (the exact-parity aggregate tests prove the output); nothing is editable yet; and the
findings D1, D5 and D7 are named on their steps, D7 shown by what the keyword lists miss.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain import research_aggregate
from aia_core.domain.methodology import MODULES, ValueOrigin, describe
from aia_core.domain.methodology.aggregation import AGGREGATION
from aia_core.domain.methodology.versions import (
    MethodologyVersionInvalid,
    named,
    validate_version,
)
from aia_core.domain.research_aggregate import (
    AGGREGATE_SLOTS,
    AIA_AGGREGATE_V1,
    AggregationSpec,
    classify_question,
    evidence_rating,
)


def _values() -> dict[str, object]:
    view = describe(AGGREGATION)
    return {v.reference: v.value for s in view.steps for v in s.values}


def test_it_is_registered_after_support() -> None:
    ids = [m.id for m in MODULES]
    assert ids[ids.index("support") + 1] == "aggregation"


def test_the_preset_is_the_units_literals_bit_for_bit() -> None:
    boot = AIA_AGGREGATE_V1.bootstrap
    assert (boot.reps, boot.reps_multi) == (400, 350)
    assert (boot.seed, boot.seed_top_box) == (20260816, 20260818)
    assert boot.quantiles == (0.025, 0.975)  # declared, not derived from 0.95: no float drift
    assert AIA_AGGREGATE_V1.top_box == 2
    # The literals left the code: the aggregate reads them from the specification only.
    source = inspect.getsource(research_aggregate.aggregate_question)
    source += inspect.getsource(research_aggregate.bootstrap_weighted_mean)
    source += inspect.getsource(research_aggregate.bootstrap_weighted_distribution)
    for literal in ("400", "350", "20260816", "20260818", "0.025", "0.975", "top - 1"):
        assert literal not in source, literal


def test_it_is_declared_in_force_and_editable() -> None:
    assert [p.name for p in AGGREGATION.presets] == ["aia-aggregate-1"]
    assert AGGREGATION.presets[0].spec is AIA_AGGREGATE_V1
    assert AGGREGATION.in_force == "aia-aggregate-1"
    assert AGGREGATION.editable is True  # values and estimator slots alike (G3b)
    assert {f.slot.id for f in AGGREGATION.formulas} == AGGREGATE_SLOTS


def _version(spec: dict[str, Any], formulas: dict[str, str] | None = None) -> Any:
    return validate_version(
        AGGREGATION,
        base_preset="aia-aggregate-1",
        spec=spec,
        formulas=formulas or {},
        version_name=named("aia-aggregate-1", 1),
    )


def test_a_version_may_change_values_and_replace_estimators() -> None:
    version = _version(
        _spec(bootstrap__reps=1000, bootstrap__quantiles=[0.05, 0.95], top_box=3),
        {"agg.top_box": "x >= top - b + 1", "agg.kish": "count(w)"},
    )
    assert version.spec.methodology_version == "aia-aggregate-1+e1"
    assert version.spec.top_box == 3 and version.spec.bootstrap.quantiles == (0.05, 0.95)
    assert set(version.formulas) == {"agg.top_box", "agg.kish"}


def test_a_version_that_breaks_a_slots_properties_or_the_spec_is_refused_by_name() -> None:
    with pytest.raises(MethodologyVersionInvalid) as refused:
        _version(
            _spec(bootstrap__reps=0),
            {"agg.share": "200 * sum(w * hit) / sum(w)", "agg.mean": "open('x')"},
        )
    problems = refused.value.problems
    assert "spec.bootstrap" in problems  # zero replicates
    assert any(k.startswith("formula.agg.share") for k in problems)  # a share above 100 %
    assert "formula.agg.mean" in problems  # not the formula language


def test_every_declared_value_is_shown_from_the_specification() -> None:
    values = _values()
    assert values["bootstrap.reps"] == 400 and values["bootstrap.seed"] == 20260816
    assert values["top_box"] == 2
    origins = {v.origin for s in describe(AGGREGATION).steps for v in s.values}
    # The keyword lists stay code (they are D7's subject, not a parameter).
    assert origins == {ValueOrigin.SPECIFICATION, ValueOrigin.CODE_CONSTANT}


def _spec(**changes: Any) -> dict[str, Any]:
    data = AIA_AGGREGATE_V1.model_dump(mode="json")
    for path, value in changes.items():
        node = data
        *parents, leaf = path.split("__")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return data


@pytest.mark.parametrize(
    "changes",
    [
        {"bootstrap__reps": 0},
        {"bootstrap__reps_multi": True},
        {"bootstrap__seed": -1},
        {"bootstrap__quantiles": [0.975, 0.025]},
        {"bootstrap__quantiles": [0.0, 0.975]},
        {"top_box": 0},
        {"top_box": 2, "extra": 1},
    ],
)
def test_a_specification_that_cannot_be_computed_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AggregationSpec.model_validate(_spec(**changes))


def test_the_findings_are_named_on_their_steps() -> None:
    notes = {s.id: s.note_cs for s in AGGREGATION.steps}
    assert "D1" in notes["weights"]
    assert "D5" in notes["interval"]
    assert "D7" in notes["classify"]
    groups = {g.id for g in AGGREGATION.groups}
    assert groups == {"M", "V", "O", "B", "F", "Z"}


def test_the_keyword_lists_decide_what_is_refused() -> None:
    """D7: the refusal is only as good as the lists. The same question in other words passes."""
    listed = "Kolik byste zaplatili za měsíční předplatné?"
    assert classify_question(listed, "otevrena") == "absolute_value"
    refused = evidence_rating(listed, "otevrena", validation_status="UNVALIDATED")
    assert (refused["rating"], refused["mode"]) == ("RED", "REFUSE")

    reworded = "Jakou částku za měsíční předplatné považujete za přiměřenou?"
    assert classify_question(reworded, "otevrena") != "absolute_value"
    shown = evidence_rating(reworded, "otevrena", validation_status="UNVALIDATED")
    assert shown["mode"] != "REFUSE" and shown["rating"] == "AMBER"
    validated = evidence_rating("Jak hodnotíte kávu?", "skala", validation_status="validated")
    assert validated["rating"] == "GREEN"
