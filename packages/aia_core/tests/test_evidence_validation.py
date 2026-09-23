"""Validation status bound to the system fingerprint, and the tier gate."""

from __future__ import annotations

import pytest

from aia_core.domain.evidence import (
    METHOD_STATUS_HOLDOUT_VALIDATED,
    METHOD_STATUS_PENDING,
    TIER_PERMITS,
    EvidenceTier,
    TierUseCase,
    ValidationState,
    ValidationStatus,
    ViolationCode,
    effective_validation_status,
    evaluate_predictive_validity_claim,
    evaluate_tier,
    method_status,
    system_fingerprint,
)

COMPONENTS = {
    "panel_sha256": "1" * 64,
    "field_dictionary_sha256": "2" * 64,
    "joint_certificate_sha256": "3" * 64,
    "engine_version": "aia-core 0.1.0",
}
NOW = system_fingerprint(COMPONENTS)
OTHER = system_fingerprint({**COMPONENTS, "panel_sha256": "4" * 64})


def test_fingerprint_moves_with_every_component() -> None:
    for key in COMPONENTS:
        changed = {**COMPONENTS, key: "9" * 64 if key != "engine_version" else "aia-core 0.2.0"}
        assert system_fingerprint(changed) != NOW, key
    assert system_fingerprint(dict(reversed(list(COMPONENTS.items())))) == NOW


@pytest.mark.parametrize("missing", list(COMPONENTS))
def test_fingerprint_refuses_a_missing_component(missing: str) -> None:
    with pytest.raises(ValueError, match=missing):
        system_fingerprint({k: v for k, v in COMPONENTS.items() if k != missing})


def test_fingerprint_refuses_a_non_hash() -> None:
    with pytest.raises(ValueError, match="panel_sha256"):
        system_fingerprint({**COMPONENTS, "panel_sha256": "v17_4_0"})


def test_state_must_name_a_fingerprint() -> None:
    with pytest.raises(ValueError):
        ValidationState(ValidationStatus.HOLDOUT_VALIDATED, "")


def test_status_holds_only_on_the_system_it_was_earned_on() -> None:
    state = ValidationState(ValidationStatus.HOLDOUT_VALIDATED, NOW)
    assert effective_validation_status(state, NOW) is ValidationStatus.HOLDOUT_VALIDATED
    assert effective_validation_status(state, OTHER) is ValidationStatus.NOT_VALIDATED
    assert effective_validation_status(None, NOW) is ValidationStatus.NOT_VALIDATED


def test_predictive_validity_needs_a_current_holdout() -> None:
    assert evaluate_predictive_validity_claim(
        ValidationState(ValidationStatus.HOLDOUT_VALIDATED, NOW), NOW
    ).allowed


def test_smoke_never_unlocks_a_validity_claim() -> None:
    decision = evaluate_predictive_validity_claim(
        ValidationState(ValidationStatus.SMOKE_VALIDATED, NOW), NOW
    )
    assert decision.codes == {ViolationCode.PREDICTIVE_VALIDITY_UNPROVEN}
    assert "smoke" in decision.violations[0].detail


def test_no_validation_is_pending_not_passed() -> None:
    decision = evaluate_predictive_validity_claim(None, NOW)
    assert decision.codes == {ViolationCode.PREDICTIVE_VALIDITY_UNPROVEN}
    assert "EXTERNAL_HOLDOUT_PENDING" in decision.violations[0].detail


def test_stale_validation_is_named_as_stale() -> None:
    decision = evaluate_predictive_validity_claim(
        ValidationState(ValidationStatus.HOLDOUT_VALIDATED, OTHER), NOW
    )
    assert decision.codes == {ViolationCode.VALIDATION_NOT_CURRENT}


def test_method_status_stamp() -> None:
    assert method_status(None, NOW) == (
        "synthetic/modelled research; external predictive certification pending"
    )
    assert method_status(ValidationState(ValidationStatus.SMOKE_VALIDATED, NOW), NOW) == (
        METHOD_STATUS_PENDING
    )
    assert method_status(ValidationState(ValidationStatus.HOLDOUT_VALIDATED, NOW), NOW) == (
        METHOD_STATUS_HOLDOUT_VALIDATED
    )
    assert method_status(ValidationState(ValidationStatus.HOLDOUT_VALIDATED, OTHER), NOW) == (
        METHOD_STATUS_PENDING
    )


# --- tier gate -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tier", "use_case", "allowed"),
    [
        (EvidenceTier.A, TierUseCase.INDIVIDUAL, True),
        (EvidenceTier.A, TierUseCase.SEGMENTATION, True),
        (EvidenceTier.B, TierUseCase.AGGREGATE, True),
        (EvidenceTier.B, TierUseCase.DEMOGRAPHIC_BREAKDOWN, True),
        (EvidenceTier.B, TierUseCase.INTERNAL_EXPERIMENTAL, True),
        (EvidenceTier.B, TierUseCase.SEGMENTATION, False),
        (EvidenceTier.B, TierUseCase.PERSONA, False),
        (EvidenceTier.B, TierUseCase.INDIVIDUAL, False),
        (EvidenceTier.C, TierUseCase.INTERNAL_EXPERIMENTAL, True),
        (EvidenceTier.C, TierUseCase.AGGREGATE, False),
    ],
)
def test_tier_permits(tier: EvidenceTier, use_case: TierUseCase, allowed: bool) -> None:
    assert evaluate_tier({"d1": tier.value}, use_case).allowed is allowed


def test_weakest_dimension_decides() -> None:
    decision = evaluate_tier({"d1": "B", "d2": "C"}, "aggregate")
    assert decision.codes == {ViolationCode.TIER_INSUFFICIENT}
    assert decision.violations[0].subject == "d2"


@pytest.mark.parametrize("tier", [None, "", "D", "a", "B+"])
def test_unknown_tier_refuses(tier: str | None) -> None:
    assert evaluate_tier({"d1": tier}, "internal_experimental").codes == {
        ViolationCode.TIER_UNKNOWN
    }


def test_unknown_use_case_and_no_dimensions_refuse() -> None:
    assert evaluate_tier({"d1": "A"}, "everything").codes == {ViolationCode.TIER_UNKNOWN}
    assert evaluate_tier({}, "aggregate").codes == {ViolationCode.TIER_UNKNOWN}


def test_tier_a_permits_every_use_case() -> None:
    assert TIER_PERMITS[EvidenceTier.A] == frozenset(TierUseCase)
