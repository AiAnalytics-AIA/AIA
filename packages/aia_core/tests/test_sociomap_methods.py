"""Sociomap specs stored with their contract, and the methods a run pins.

Plan ``sociomap-formula-corrections`` § 8.2, slice S1 (I0, I4). A stored spec names its
contract and is read under that one; a run's pinned method carries its whole spec and is
verified against its fingerprint before anything is computed.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.research_sociomap import (
    LEGACY_METHODS,
    SociomapMethod,
    SociomapMethodsInvalid,
    default_methods,
    methods_fingerprint,
    read_methods,
)
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V1,
    SPEC_CONTRACT_VERSION,
    UnknownSpecContract,
    UnsupportedMethodology,
    read_spec,
    spec_payload,
)
from aia_core.domain.sociomap.layout import LayoutAlgorithm

#: The v1 preset's fingerprint, as every stored ``aia-sociomap-1`` map records it. A
#: contract added beside this one must never move it (I4).
V1_FINGERPRINT = "9d4dffeac5531f3fc0e18c2db6a2a9c8d823d5fd299fbec30870c9aa2f31c211"


def test_the_v1_preset_fingerprint_has_not_moved() -> None:
    assert SPEC_CONTRACT_VERSION == "2"
    assert AIA_SOCIOMAP_V1.fingerprint() == V1_FINGERPRINT


def test_a_stored_spec_reads_back_under_its_contract_with_its_fingerprint() -> None:
    payload = spec_payload(AIA_SOCIOMAP_V1)
    assert payload["contract_version"] == "2"
    spec = read_spec(payload)
    assert spec == AIA_SOCIOMAP_V1 and spec.fingerprint() == V1_FINGERPRINT


@pytest.mark.parametrize("contract", [None, "1", "4", 2])
def test_a_spec_under_a_contract_this_engine_does_not_read_is_refused(contract: Any) -> None:
    payload = {**spec_payload(AIA_SOCIOMAP_V1), "contract_version": contract}
    if contract is None:
        del payload["contract_version"]
    with pytest.raises(UnknownSpecContract):
        read_spec(payload)


def test_a_pin_resolves_to_exactly_the_spec_it_was_made_from() -> None:
    method = SociomapMethod.of(AIA_SOCIOMAP_V1)
    assert method.method_id == "aia-sociomap-1"
    assert method.spec_fingerprint == V1_FINGERPRINT
    assert method.resolve() == AIA_SOCIOMAP_V1
    # Stored and read back, as a run's metadata holds it.
    assert SociomapMethod.model_validate(method.model_dump(mode="json")).resolve() == (
        AIA_SOCIOMAP_V1
    )


def test_an_edited_pin_is_refused_not_computed() -> None:
    method = SociomapMethod.of(AIA_SOCIOMAP_V1).model_dump(mode="json")
    method["spec"]["spec"]["layout"]["map_frame"]["extent"] = 30.0
    with pytest.raises(SociomapMethodsInvalid, match="fingerprint"):
        SociomapMethod.model_validate(method).resolve()


def test_a_pin_whose_id_is_not_its_specs_method_is_refused() -> None:
    method = SociomapMethod.of(AIA_SOCIOMAP_V1).model_copy(update={"method_id": "aia-sociomap-2"})
    with pytest.raises(SociomapMethodsInvalid, match="holds 'aia-sociomap-1'"):
        method.resolve()


def test_a_pin_the_engine_cannot_compute_is_refused_by_name() -> None:
    unavailable = AIA_SOCIOMAP_V1.model_copy(
        update={
            "layout": AIA_SOCIOMAP_V1.layout.model_copy(
                update={"algorithm": LayoutAlgorithm.LEGACY_R_SMACOF_UNFOLDING}
            )
        }
    )
    with pytest.raises(UnsupportedMethodology) as caught:
        SociomapMethod.of(unavailable).resolve()
    assert "layout.algorithm" in caught.value.unsupported


def test_a_run_without_a_pin_reads_as_aia_sociomap_1() -> None:
    assert read_methods(None) == LEGACY_METHODS
    (legacy,) = LEGACY_METHODS
    assert legacy.resolve() == AIA_SOCIOMAP_V1


def test_a_new_run_pins_aia_sociomap_1_and_the_audits_object_map_beside_it() -> None:
    from aia_core.domain.sociomap import AIA_SOCIOMAP_V2

    assert default_methods() == (*LEGACY_METHODS, SociomapMethod.of(AIA_SOCIOMAP_V2))
    assert read_methods([m.model_dump(mode="json") for m in default_methods()]) == (
        default_methods()
    )


@pytest.mark.parametrize(
    ("value", "match"),
    [
        ([], "at least one"),
        ("aia-sociomap-1", "at least one"),
        ([{"method_id": "aia-sociomap-1"}], "does not read"),
        (
            [SociomapMethod.of(AIA_SOCIOMAP_V1).model_dump(mode="json")] * 2,
            "pinned twice",
        ),
    ],
)
def test_a_pinned_set_this_module_does_not_compute_is_refused(value: Any, match: str) -> None:
    with pytest.raises(SociomapMethodsInvalid, match=match):
        read_methods(value)


def test_a_set_with_no_contract_2_map_is_refused() -> None:
    method = SociomapMethod.of(AIA_SOCIOMAP_V1).model_dump(mode="json")
    method["spec"]["contract_version"] = "3"
    with pytest.raises(SociomapMethodsInvalid, match="exactly one contract-2"):
        read_methods([method])


def test_the_set_fingerprint_follows_every_pinned_spec() -> None:
    other = AIA_SOCIOMAP_V1.model_copy(update={"methodology_version": "aia-sociomap-1b"})
    assert methods_fingerprint(LEGACY_METHODS) == methods_fingerprint(LEGACY_METHODS)
    assert methods_fingerprint(LEGACY_METHODS) != methods_fingerprint((SociomapMethod.of(other),))
