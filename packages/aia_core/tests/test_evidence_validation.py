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


def test_a_recorded_state_names_its_date_truth_and_both_hashes_or_none_of_them() -> None:
    from datetime import UTC, datetime

    from aia_core.domain.evidence.validation import ValidationTruth

    when = datetime(2026, 10, 13, tzinfo=UTC)
    evidence = {
        "validated_at": when,
        "truth": ValidationTruth.PANEL_HELD_OUT,
        "preregistration_sha256": "a" * 64,
        "verdict_sha256": "b" * 64,
    }
    recorded = ValidationState(ValidationStatus.HOLDOUT_VALIDATED, NOW, **evidence)
    assert recorded.validated_at == when
    with pytest.raises(ValueError, match="names its date"):
        ValidationState(ValidationStatus.HOLDOUT_VALIDATED, NOW, validated_at=when)
    with pytest.raises(ValueError, match="verdict_sha256"):
        ValidationState(
            ValidationStatus.HOLDOUT_VALIDATED, NOW, **{**evidence, "verdict_sha256": "x"}
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        ValidationState(
            ValidationStatus.HOLDOUT_VALIDATED,
            NOW,
            **{**evidence, "validated_at": datetime(2026, 10, 13)},
        )


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


# --- the respondent system a modelled validation is earned on (ADR 0024 §4) ---------------

RESPONDENT = {
    "respondent_prompt_sha256": "a" * 64,
    "persona_builder": "aia-panel-persona-source-1/aia-persona-profile-1",
    "persona_mode": "calibrated",
    "sampler_version": "aia-panel-sample-1",
    "population_version": "v17_4_0",
    "model_binding": "bedrock/anthropic.claude/bedrock-eu-primary",
    "response_process_version": "aia-response-process-1",
}


def test_the_respondent_system_fingerprint_moves_with_every_component() -> None:
    from aia_core.domain.evidence import RESPONDENT_SYSTEM_COMPONENTS, respondent_system_fingerprint

    assert set(RESPONDENT) == set(RESPONDENT_SYSTEM_COMPONENTS)
    base = respondent_system_fingerprint(RESPONDENT)
    moved = {
        respondent_system_fingerprint(
            {**RESPONDENT, key: "b" * 64 if key.endswith("sha256") else RESPONDENT[key] + "x"}
        )
        for key in RESPONDENT_SYSTEM_COMPONENTS
    }
    assert base not in moved and len(moved) == len(RESPONDENT_SYSTEM_COMPONENTS)


@pytest.mark.parametrize("key", sorted(RESPONDENT))
def test_the_respondent_system_refuses_a_missing_or_blank_component(key: str) -> None:
    from aia_core.domain.evidence import respondent_system_fingerprint

    with pytest.raises(ValueError, match=key):
        respondent_system_fingerprint({k: v for k, v in RESPONDENT.items() if k != key})
    with pytest.raises(ValueError, match=key):
        respondent_system_fingerprint({**RESPONDENT, key: " "})


def test_the_respondent_system_refuses_a_name_it_does_not_bind_and_a_prompt_not_hashed() -> None:
    from aia_core.domain.evidence import respondent_system_fingerprint

    with pytest.raises(ValueError, match="temperature"):
        respondent_system_fingerprint({**RESPONDENT, "temperature": "0.7"})
    with pytest.raises(ValueError, match="SHA-256"):
        respondent_system_fingerprint({**RESPONDENT, "respondent_prompt_sha256": "v1"})


def test_only_a_current_holdout_lifts_internal_only() -> None:
    from aia_core.domain.evidence import lifts_internal_only, respondent_system_fingerprint

    system = respondent_system_fingerprint(RESPONDENT)
    other = respondent_system_fingerprint({**RESPONDENT, "population_version": "v17_5_0"})
    holdout = ValidationState(ValidationStatus.HOLDOUT_VALIDATED, system)
    assert lifts_internal_only(holdout, system)
    assert not lifts_internal_only(holdout, other)  # stale: the population moved
    assert not lifts_internal_only(holdout, None)  # no current system: nothing to judge
    assert not lifts_internal_only(None, system)
    assert not lifts_internal_only(
        ValidationState(ValidationStatus.SMOKE_VALIDATED, system), system
    )
