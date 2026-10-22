"""What a run's metadata says it computed under, by name (plan methodology-tab Z1a, R1d)."""

from __future__ import annotations

from aia_core.domain.methodology.pins import (
    RunMethod,
    aggregation_pin_for,
    response_deviates,
    run_methods,
    sociomap_methods_for,
    support_spec_for,
)
from aia_core.domain.respondent_behavior import AIA_RESPONSE_V1


def test_a_run_from_before_any_pin_reads_as_the_code_presets() -> None:
    assert run_methods({}) == {
        "sociomap": RunMethod("aia-sociomap-1", stored=False),
        "support": RunMethod("aia-support-1", stored=False),
        "aggregation": RunMethod("aia-aggregate-1", stored=False),
        "response": RunMethod("aia-response-1", stored=False),
    }


def test_a_run_under_the_code_presets_names_the_pins() -> None:
    meta = {
        "sociomap_methods": [m.model_dump(mode="json") for m in sociomap_methods_for(None)],
        "support": support_spec_for(None).model_dump(mode="json"),
        "aggregation": aggregation_pin_for(None),
        "response": AIA_RESPONSE_V1.model_dump(mode="json"),
    }
    methods = run_methods(meta)
    assert methods["sociomap"] == RunMethod("aia-sociomap-5", stored=False)
    assert methods["support"] == RunMethod("aia-support-1", stored=False)
    assert methods["aggregation"] == RunMethod("aia-aggregate-1", stored=False)
    assert methods["response"] == RunMethod("aia-response-1", stored=False)


def test_a_stored_version_is_named_as_stored() -> None:
    meta = {
        "methodology": {"name": "aia-sociomap-3+e1"},
        "support_methodology": {"name": "aia-support-1+e2"},
        "aggregation_methodology": {"name": "aia-aggregate-1+e1"},
        "response_methodology": {"name": "aia-response-1+e3"},
    }
    assert run_methods(meta) == {
        "sociomap": RunMethod("aia-sociomap-3+e1", stored=True),
        "support": RunMethod("aia-support-1+e2", stored=True),
        "aggregation": RunMethod("aia-aggregate-1+e1", stored=True),
        "response": RunMethod("aia-response-1+e3", stored=True),
    }


def test_a_pin_that_cannot_be_read_is_named_by_nothing_never_by_a_preset() -> None:
    meta = {
        "sociomap_methods": "x",
        "support": 3,
        "aggregation": {"spec": None},
        "response": {"extremity": 0.3},
    }
    assert run_methods(meta) == {
        "sociomap": RunMethod(None, stored=False),
        "support": RunMethod(None, stored=False),
        "aggregation": RunMethod(None, stored=False),
        "response": RunMethod(None, stored=False),
    }
    assert run_methods({"sociomap_methods": [{"method_id": ""}]})["sociomap"].name is None
    assert run_methods({"aggregation": "x"})["aggregation"].name is None


def test_a_response_process_says_whether_it_is_the_units() -> None:
    """Plan methodology-tab R1d: True only for a process that is not 18.6.6's; a run from
    before the pin was answered under it; a pin that cannot be read is None, never a guess."""
    unit = AIA_RESPONSE_V1.model_dump(mode="json")
    edited = {**unit, "methodology_version": "aia-response-1+e1", "dont_know": 0.4}
    assert response_deviates({}) is False
    assert response_deviates({"response": unit}) is False
    assert response_deviates({"response": edited}) is True
    assert response_deviates({"response": {"extremity": 0.3}}) is None
    # A stored version holding 18.6.6's values computes 18.6.6's numbers: not a deviation.
    renamed = {**unit, "methodology_version": "aia-response-1+e2"}
    assert response_deviates({"response": renamed}) is False


def test_the_units_process_is_decided_by_its_coefficients_not_its_name() -> None:
    from aia_core.domain.methodology.pins import is_units_process

    assert is_units_process(AIA_RESPONSE_V1)
    renamed = AIA_RESPONSE_V1.model_copy(update={"methodology_version": "aia-response-1+e2"})
    assert is_units_process(renamed)
    assert not is_units_process(AIA_RESPONSE_V1.model_copy(update={"extremity": 0.5}))
