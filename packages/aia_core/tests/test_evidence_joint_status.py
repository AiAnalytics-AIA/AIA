"""CORE_JOINT_STATUS: hash-bound loading, explicit degradation, joint-unit decisions."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.evidence import (
    CORE_UNIT,
    JointDegradation,
    JointStatus,
    JointUnitKind,
    PredictionValidationStatus,
    StructureStatus,
    ViolationCode,
    evaluate_joint_structure,
    joint_unit,
    joint_unit_kind,
    load_joint_status,
)

PANEL = "b" * 64


def test_certificate_bound_to_the_loaded_panel_is_honoured(certificate_bytes: Any) -> None:
    status = load_joint_status(certificate_bytes(), measured_panel_sha256=PANEL)
    assert status.certified and status.degradation is None
    assert status.structure_status is StructureStatus.QC_PASSED
    assert (
        status.prediction_validation_status is PredictionValidationStatus.EXTERNAL_HOLDOUT_PENDING
    )
    assert not status.cross_block_same_person_joint
    assert not status.client_joint_outputs_allowed
    assert not status.cross_block_joint_claims_allowed
    assert status.descriptive_core_outputs_allowed and status.matched_block_outputs_allowed
    assert "politics" in status.matched_blocks and len(status.matched_blocks) == 6


@pytest.mark.parametrize(
    ("certificate", "measured", "reason"),
    [
        (None, PANEL, JointDegradation.MISSING),
        (b"{not json", PANEL, JointDegradation.UNPARSEABLE),
        (b"\xff\xfe", PANEL, JointDegradation.UNPARSEABLE),
        (b"[1, 2]", PANEL, JointDegradation.MALFORMED),
    ],
)
def test_unreadable_certificates_degrade(
    certificate: bytes | None, measured: str, reason: JointDegradation
) -> None:
    status = load_joint_status(certificate, measured_panel_sha256=measured)
    assert status.degradation is reason and not status.certified


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"structure_status": "QC_PENDING"}, JointDegradation.UNKNOWN_STATUS),
        ({"structure_status": None}, JointDegradation.UNKNOWN_STATUS),
        ({"prediction_validation_status": "HOLDOUT_VALIDATED"}, JointDegradation.UNKNOWN_STATUS),
        ({"client_joint_outputs_allowed": "false"}, JointDegradation.MALFORMED),
        ({"cross_block_same_person_joint": 0}, JointDegradation.MALFORMED),
        ({"descriptive_core_outputs_allowed": None}, JointDegradation.MALFORMED),
        ({"panel_sha256": "abc"}, JointDegradation.MALFORMED),
        ({"production_panel": ""}, JointDegradation.MALFORMED),
        ({"matched_blocks": "politics"}, JointDegradation.MALFORMED),
        ({"matched_blocks": ["politics", ""]}, JointDegradation.MALFORMED),
        ({"runtime_identity_contract": 7}, JointDegradation.MALFORMED),
    ],
)
def test_malformed_or_unknown_certificates_degrade(
    certificate_bytes: Any, overrides: dict[str, Any], reason: JointDegradation
) -> None:
    status = load_joint_status(certificate_bytes(**overrides), measured_panel_sha256=PANEL)
    assert status.degradation is reason


def test_panel_hash_mismatch_degrades(certificate_bytes: Any) -> None:
    status = load_joint_status(certificate_bytes(), measured_panel_sha256="c" * 64)
    assert status.degradation is JointDegradation.PANEL_HASH_MISMATCH


def test_unmeasured_panel_degrades_rather_than_trusting_the_certificate(
    certificate_bytes: Any,
) -> None:
    status = load_joint_status(certificate_bytes(), measured_panel_sha256=None)
    assert status.degradation is JointDegradation.PANEL_HASH_UNVERIFIED


def test_degraded_status_permits_nothing(degraded_joint_status: JointStatus) -> None:
    s = degraded_joint_status
    assert not any(
        (
            s.core_same_person_joint,
            s.cross_block_same_person_joint,
            s.client_joint_outputs_allowed,
            s.descriptive_core_outputs_allowed,
            s.matched_block_outputs_allowed,
            s.cross_block_joint_claims_allowed,
        )
    )
    assert s.matched_blocks == frozenset()
    assert s.prediction_validation_status is None


def test_a_permissive_status_cannot_be_built_by_hand(joint_status: JointStatus) -> None:
    with pytest.raises(ValueError, match="issued only by load_joint_status"):
        JointStatus(
            **{
                name: getattr(joint_status, name)
                for name in JointStatus.__dataclass_fields__
                if name != "_issuer"
            },
            _issuer=object(),
        )


# --- joint units --------------------------------------------------------------------


def test_joint_units(field_book: Any) -> None:
    assert joint_unit(field_book.get("vek")) == CORE_UNIT
    assert joint_unit(field_book.get("numeracy_score")) == CORE_UNIT
    assert joint_unit(field_book.get("vote_2021")) == "politics"
    assert joint_unit_kind(field_book.get("vzdelani")) is JointUnitKind.CORE
    assert joint_unit_kind(field_book.get("trust_courts")) is JointUnitKind.MATCHED
    assert joint_unit_kind(field_book.get("deal_seeking_1_10")) is JointUnitKind.OTHER


def _decide(book: Any, status: JointStatus, *fields: str, **kw: bool) -> Any:
    args = {"joint": True, "measured": True, "client_facing": True, **kw}
    return evaluate_joint_structure([book.get(f) for f in fields], status, **args)


def test_same_person_core_cross_tab_is_allowed(field_book: Any, joint_status: JointStatus) -> None:
    assert _decide(field_book, joint_status, "vek", "vzdelani", "numeracy_score").allowed


def test_matched_block_by_demographics_is_a_labelled_summary(
    field_book: Any, joint_status: JointStatus
) -> None:
    assert _decide(field_book, joint_status, "vote_2021", "vek").allowed


def test_cross_block_measured_client_claim_is_refused_three_ways(
    field_book: Any, joint_status: JointStatus
) -> None:
    decision = _decide(field_book, joint_status, "vote_2021", "wellbeing_index")
    assert decision.codes == {
        ViolationCode.CROSS_BLOCK_JOINT_CLAIM,
        ViolationCode.CROSS_BLOCK_NOT_SAME_PERSON,
        ViolationCode.CLIENT_JOINT_OUTPUT,
    }


def test_cross_block_stays_refused_internally_and_as_modelled(
    field_book: Any, joint_status: JointStatus
) -> None:
    decision = _decide(
        field_book, joint_status, "trust_courts", "deal_seeking_1_10",
        measured=False, client_facing=False,
    )  # fmt: skip
    assert decision.codes == {ViolationCode.CROSS_BLOCK_JOINT_CLAIM}


def test_separate_statements_are_not_joint(field_book: Any, joint_status: JointStatus) -> None:
    assert _decide(field_book, joint_status, "vote_2021", "wellbeing_index", joint=False).allowed


def test_uncertified_matched_block_is_refused_client_facing(
    field_book: Any, joint_status: JointStatus
) -> None:
    # RELIGION is donor-matched but not named in the certificate's matched_blocks.
    decision = _decide(field_book, joint_status, "religious_affiliation", joint=False)
    assert decision.codes == {ViolationCode.MATCHED_BLOCK_NOT_CERTIFIED}
    internal = _decide(
        field_book, joint_status, "religious_affiliation", joint=False, client_facing=False
    )
    assert internal.allowed


def test_degraded_certificate_refuses_every_client_claim(
    field_book: Any, degraded_joint_status: JointStatus
) -> None:
    decision = _decide(field_book, degraded_joint_status, "vek", joint=False)
    assert decision.codes == {ViolationCode.JOINT_CERTIFICATE_DEGRADED}


def test_degraded_certificate_refuses_internal_core_joints(
    field_book: Any, degraded_joint_status: JointStatus
) -> None:
    decision = _decide(field_book, degraded_joint_status, "vek", "vzdelani", client_facing=False)
    assert decision.codes == {ViolationCode.CORE_OUTPUTS_NOT_CERTIFIED}


def test_certificate_flags_are_read_not_assumed(field_book: Any, certificate_bytes: Any) -> None:
    no_core = load_joint_status(
        certificate_bytes(descriptive_core_outputs_allowed=False), measured_panel_sha256=PANEL
    )
    assert _decide(field_book, no_core, "vek", joint=False).codes == {
        ViolationCode.CORE_OUTPUTS_NOT_CERTIFIED
    }
    no_matched = load_joint_status(
        certificate_bytes(matched_block_outputs_allowed=False), measured_panel_sha256=PANEL
    )
    assert _decide(field_book, no_matched, "vote_2021", joint=False).codes == {
        ViolationCode.MATCHED_BLOCK_NOT_CERTIFIED
    }
    open_joint = load_joint_status(
        certificate_bytes(
            cross_block_joint_claims_allowed=True,
            client_joint_outputs_allowed=True,
        ),
        measured_panel_sha256=PANEL,
    )
    # Even a certificate allowing cross-block claims does not make them same-person truth.
    assert _decide(field_book, open_joint, "vote_2021", "wellbeing_index").codes == {
        ViolationCode.CROSS_BLOCK_NOT_SAME_PERSON
    }
    assert _decide(field_book, open_joint, "vote_2021", "wellbeing_index", measured=False).allowed
