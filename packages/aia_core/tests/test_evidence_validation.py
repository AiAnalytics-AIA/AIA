"""Validation status bound to the system fingerprint."""

from __future__ import annotations

import pytest

from aia_core.domain.evidence import (
    METHOD_STATUS_HOLDOUT_VALIDATED,
    METHOD_STATUS_PENDING,
    ValidationState,
    ValidationStatus,
    ViolationCode,
    effective_validation_status,
    evaluate_predictive_validity_claim,
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


# --- the retired tier gate (methodology-tab V1c2) -----------------------------------------


def test_the_tier_gate_is_retired() -> None:
    """Nothing gave a field a tier, so the A/B/C gate decided nothing; the population's field
    policy decides a field's uses. Neither its names nor its codes remain to be reached for."""
    from aia_core.domain import evidence

    for name in ("TIER_PERMITS", "EvidenceTier", "TierUseCase", "evaluate_tier"):
        assert not hasattr(evidence, name), name
    assert not [code for code in ViolationCode if code.name.startswith("TIER_")]


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
