"""What a run's metadata says it computed under, by name (plan methodology-tab Z1a)."""

from __future__ import annotations

from aia_core.domain.methodology.pins import (
    RunMethod,
    aggregation_pin_for,
    run_methods,
    sociomap_methods_for,
    support_spec_for,
)


def test_a_run_from_before_any_pin_reads_as_the_code_presets() -> None:
    assert run_methods({}) == {
        "sociomap": RunMethod("aia-sociomap-1", stored=False),
        "support": RunMethod("aia-support-1", stored=False),
        "aggregation": RunMethod("aia-aggregate-1", stored=False),
    }


def test_a_run_under_the_code_presets_names_the_pins() -> None:
    meta = {
        "sociomap_methods": [m.model_dump(mode="json") for m in sociomap_methods_for(None)],
        "support": support_spec_for(None).model_dump(mode="json"),
        "aggregation": aggregation_pin_for(None),
    }
    methods = run_methods(meta)
    assert methods["sociomap"] == RunMethod("aia-sociomap-3", stored=False)
    assert methods["support"] == RunMethod("aia-support-1", stored=False)
    assert methods["aggregation"] == RunMethod("aia-aggregate-1", stored=False)


def test_a_stored_version_is_named_as_stored() -> None:
    meta = {
        "methodology": {"name": "aia-sociomap-3+e1"},
        "support_methodology": {"name": "aia-support-1+e2"},
        "aggregation_methodology": {"name": "aia-aggregate-1+e1"},
    }
    assert run_methods(meta) == {
        "sociomap": RunMethod("aia-sociomap-3+e1", stored=True),
        "support": RunMethod("aia-support-1+e2", stored=True),
        "aggregation": RunMethod("aia-aggregate-1+e1", stored=True),
    }


def test_a_pin_that_cannot_be_read_is_named_by_nothing_never_by_a_preset() -> None:
    meta = {"sociomap_methods": "x", "support": 3, "aggregation": {"spec": None}}
    assert run_methods(meta) == {
        "sociomap": RunMethod(None, stored=False),
        "support": RunMethod(None, stored=False),
        "aggregation": RunMethod(None, stored=False),
    }
    assert run_methods({"sociomap_methods": [{"method_id": ""}]})["sociomap"].name is None
    assert run_methods({"aggregation": "x"})["aggregation"].name is None
