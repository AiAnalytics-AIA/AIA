"""What a methodology version may be: an editable module's whole specification and formulas.

Plan ``methodology-tab.md`` A3; ADR 0023 decisions 3-4. Validation fails closed and reports
every problem at once; the store names the version, so an edit is never mistaken for the
code's preset; the reference map is never edited.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.methodology.sociomap import SOCIOMAP
from aia_core.domain.methodology.sociomap_reference import SOCIOMAP_REFERENCE
from aia_core.domain.methodology.versions import (
    VERSION_CONTRACT,
    MethodologyVersionInvalid,
    named,
    payload_sha256,
    validate_version,
    version_payload,
)
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V1, AIA_SOCIOMAP_V3


def _spec(**changes: Any) -> dict[str, Any]:
    spec = AIA_SOCIOMAP_V3.model_dump(mode="json")
    for path, value in changes.items():
        node = spec
        *parents, leaf = path.split("__")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return spec


def _validate(spec: dict[str, Any], formulas: dict[str, str] | None = None, **kw: Any) -> Any:
    return validate_version(
        SOCIOMAP,
        base_preset=kw.get("base", "aia-sociomap-3"),
        spec=spec,
        formulas=formulas or {},
        version_name=kw.get("name", named("aia-sociomap-3", 1)),
    )


def test_an_edited_parameter_is_a_version_named_for_its_base() -> None:
    version = _validate(_spec(relation__n_min=40, terrain__sigma=0.3))
    assert version.spec.relation.n_min == 40
    assert version.spec.terrain.sigma == 0.3
    assert version.spec.methodology_version == "aia-sociomap-3+e1"
    assert version.spec.fingerprint() != AIA_SOCIOMAP_V3.fingerprint()


def test_the_author_cannot_name_a_version_the_codes_preset() -> None:
    version = _validate(_spec(methodology_version="aia-sociomap-3"))
    assert version.spec.methodology_version == "aia-sociomap-3+e1"


def test_a_replaced_formula_is_kept_when_it_keeps_its_slots_properties() -> None:
    version = _validate(_spec(), {"f12.kernel": " h * exp(-d2 / (2 * sigma ** 2)) "})
    assert version.formulas == {"f12.kernel": "h * exp(-d2 / (2 * sigma ** 2))"}


def test_every_problem_is_reported_at_once() -> None:
    with pytest.raises(MethodologyVersionInvalid) as refused:
        _validate(
            _spec(relation__n_min=2, terrain__sigma=-1.0, layout__map_frame__extent=3.0),
            {
                "f12.kernel": "h * exp(d2)",  # rises with distance
                "f6.distance": "__import__('os')",
                "f99.nothing": "1",
            },
        )
    problems = refused.value.problems
    assert {"spec.relation.n_min", "spec.terrain.sigma", "spec.layout.map_frame.extent"} <= set(
        problems
    )
    assert "formula.f12.kernel.non_increasing_in:d2" in problems
    assert problems["formula.f6.distance"].startswith("unknown_function")
    assert "no slot" in problems["formula.f99.nothing"]


def test_a_malformed_specification_is_refused_by_field() -> None:
    spec = _spec()
    del spec["relation"]["confidence"]
    with pytest.raises(MethodologyVersionInvalid) as refused:
        _validate(spec)
    assert "spec.relation.confidence" in refused.value.problems


def test_the_reference_map_is_never_edited() -> None:
    with pytest.raises(MethodologyVersionInvalid) as refused:
        validate_version(
            SOCIOMAP_REFERENCE,
            base_preset="aia-sociomap-1",
            spec=AIA_SOCIOMAP_V1.model_dump(mode="json"),
            formulas={},
            version_name="aia-sociomap-1+e1",
        )
    assert "shown, not edited" in refused.value.problems["module"]


def test_a_base_the_module_does_not_have_is_refused() -> None:
    with pytest.raises(MethodologyVersionInvalid) as refused:
        _validate(_spec(), base="aia-sociomap-9")
    assert "no preset" in refused.value.problems["base_preset"]


def test_the_payload_is_plain_json_and_its_digest_is_stable() -> None:
    version = _validate(_spec(relation__n_min=40), {"f6.distance": "sqrt(2 * (1 - r))"})
    payload = version_payload(version)
    assert payload["contract"] == VERSION_CONTRACT
    assert payload["spec"]["relation"]["n_min"] == 40
    assert payload["formulas"] == {"f6.distance": "sqrt(2 * (1 - r))"}
    assert payload_sha256(payload) == payload_sha256(dict(reversed(list(payload.items()))))
    assert len(payload_sha256(payload)) == 64


def test_a_version_number_counts_from_one() -> None:
    assert named("aia-sociomap-3", 12) == "aia-sociomap-3+e12"
    with pytest.raises(ValueError):
        named("aia-sociomap-3", 0)
