"""CORE_JOINT_STATUS: one hash-bound evaluator, explicit degradation, joint-unit decisions."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain import evidence, population
from aia_core.domain.evidence import (
    CORE_UNIT,
    JointStatus,
    JointUnitKind,
    ViolationCode,
    evaluate_joint_structure,
    joint_unit,
    joint_unit_kind,
)
from aia_core.domain.population import JointState, evaluate_joint_certificate

PANEL = "b" * 64


def test_certificate_bound_to_the_loaded_panel_is_honoured(certificate_bytes: Any) -> None:
    status = evaluate_joint_certificate(certificate_bytes(), panel_sha256=PANEL)
    assert status.certified and status.state is JointState.CERTIFIED
    assert status.structure_status == "QC_PASSED"
    assert status.prediction_validation_status == "EXTERNAL_HOLDOUT_PENDING"
    assert status.production_panel == "synthetic_panel.csv.gz"
    assert not status.cross_block_same_person_joint
    assert not status.client_joint_outputs_allowed
    assert not status.cross_block_joint_claims_allowed
    assert status.descriptive_core_outputs_allowed and status.matched_block_outputs_allowed
    assert "politics" in status.matched_blocks and len(status.matched_blocks) == 6


@pytest.mark.parametrize(
    ("certificate", "reason"),
    [
        (None, JointState.MISSING),
        (b"{not json", JointState.UNPARSEABLE),
        (b"\xff\xfe", JointState.UNPARSEABLE),
        (b"[1, 2]", JointState.UNPARSEABLE),
    ],
)
def test_unreadable_certificates_degrade(certificate: bytes | None, reason: JointState) -> None:
    status = evaluate_joint_certificate(certificate, panel_sha256=PANEL)
    assert status.state is reason and not status.certified


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        # Checked by the claim gate's own loader before the two were one (evidence-integrity 5b).
        ({"structure_status": "QC_PENDING"}, JointState.UNKNOWN_STATUS),
        ({"structure_status": None}, JointState.UNKNOWN_STATUS),
        ({"prediction_validation_status": "HOLDOUT_VALIDATED"}, JointState.UNKNOWN_STATUS),
        ({"prediction_validation_status": None}, JointState.UNKNOWN_STATUS),
        ({"client_joint_outputs_allowed": "false"}, JointState.UNPARSEABLE),
        ({"cross_block_same_person_joint": 0}, JointState.UNPARSEABLE),
        ({"descriptive_core_outputs_allowed": None}, JointState.UNPARSEABLE),
        ({"panel_sha256": "abc"}, JointState.UNPARSEABLE),
        ({"production_panel": ""}, JointState.UNPARSEABLE),
        ({"production_panel": None}, JointState.UNPARSEABLE),
        ({"matched_blocks": "politics"}, JointState.UNPARSEABLE),
        ({"matched_blocks": ["politics", ""]}, JointState.UNPARSEABLE),
        ({"runtime_identity_contract": 7}, JointState.UNPARSEABLE),
        # Checked by the population loader's alone.
        ({"status": "SOMETHING_NEWER"}, JointState.UNKNOWN_STATUS),
        ({"status": None}, JointState.UNKNOWN_STATUS),
    ],
)
def test_malformed_or_unknown_certificates_degrade(
    certificate_bytes: Any, overrides: dict[str, Any], reason: JointState
) -> None:
    status = evaluate_joint_certificate(certificate_bytes(**overrides), panel_sha256=PANEL)
    assert status.state is reason


def test_panel_hash_mismatch_degrades(certificate_bytes: Any) -> None:
    status = evaluate_joint_certificate(certificate_bytes(), panel_sha256="c" * 64)
    assert status.state is JointState.NOT_THIS_PANEL


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
    fields = {
        name: getattr(joint_status, name)
        for name in JointStatus.__dataclass_fields__
        if name != "_issuer"
    }
    with pytest.raises(ValueError, match="issued only by evaluate_joint_certificate"):
        JointStatus(**fields)
    with pytest.raises(ValueError, match="issued only by evaluate_joint_certificate"):
        JointStatus(**fields, _issuer=object())


# --- one evaluator for the loader and the claim gate (OI-24, evidence-integrity 5b) -----


def test_the_loader_and_the_claim_gate_read_one_status() -> None:
    assert evidence.JointStatus is population.JointStatus
    assert not hasattr(evidence, "load_joint_status")


@pytest.mark.parametrize(
    "overrides",
    [
        # Each certified by one side and refused by the other before they were one.
        {"status": "SOMETHING_NEWER"},
        {"prediction_validation_status": "HOLDOUT_VALIDATED"},
        {"production_panel": None},
        {"matched_blocks": ["politics", ""]},
    ],
)
def test_a_certificate_either_side_refused_refuses_a_client_claim(
    certificate_bytes: Any, field_book: Any, overrides: dict[str, Any]
) -> None:
    status = evaluate_joint_certificate(certificate_bytes(**overrides), panel_sha256=PANEL)
    decision = evaluate_joint_structure(
        [field_book.get("vek")], status, joint=False, measured=True, client_facing=True
    )
    assert decision.codes == {ViolationCode.JOINT_CERTIFICATE_DEGRADED}


#: The fingerprints the claim gate's own status had for these two before the two were one.
#: Every stored analysis module's input fingerprint carries one, so they must not move.
MISSING_FINGERPRINT = "f535ed2ecbbd90fc4dfc729f1861e18ab1b1618003f366a05c8edc57f1b7eb2e"
CERTIFIED_FINGERPRINT = "0d874b236e1f5aadb6ec5e584aa81ec73f4fef1a316c3cc81543079ae4787802"


def test_a_stored_module_keeps_its_certificate_identity(certificate_bytes: Any) -> None:
    missing = evaluate_joint_certificate(None, panel_sha256=PANEL)
    assert missing.fingerprint() == MISSING_FINGERPRINT
    certified = evaluate_joint_certificate(certificate_bytes(), panel_sha256=PANEL)
    assert certified.fingerprint() == CERTIFIED_FINGERPRINT


def test_a_certificate_permitting_more_has_another_identity(certificate_bytes: Any) -> None:
    wider = evaluate_joint_certificate(
        certificate_bytes(client_joint_outputs_allowed=True), panel_sha256=PANEL
    )
    assert wider.certified and wider.fingerprint() != CERTIFIED_FINGERPRINT


def test_a_byte_order_mark_is_read_as_the_certificate(certificate_bytes: Any) -> None:
    status = evaluate_joint_certificate(b"\xef\xbb\xbf" + certificate_bytes(), panel_sha256=PANEL)
    assert status.certified


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
    no_core = evaluate_joint_certificate(
        certificate_bytes(descriptive_core_outputs_allowed=False), panel_sha256=PANEL
    )
    assert _decide(field_book, no_core, "vek", joint=False).codes == {
        ViolationCode.CORE_OUTPUTS_NOT_CERTIFIED
    }
    no_matched = evaluate_joint_certificate(
        certificate_bytes(matched_block_outputs_allowed=False), panel_sha256=PANEL
    )
    assert _decide(field_book, no_matched, "vote_2021", joint=False).codes == {
        ViolationCode.MATCHED_BLOCK_NOT_CERTIFIED
    }
    open_joint = evaluate_joint_certificate(
        certificate_bytes(
            cross_block_joint_claims_allowed=True,
            client_joint_outputs_allowed=True,
        ),
        panel_sha256=PANEL,
    )
    # Even a certificate allowing cross-block claims does not make them same-person truth.
    assert _decide(field_book, open_joint, "vote_2021", "wellbeing_index").codes == {
        ViolationCode.CROSS_BLOCK_NOT_SAME_PERSON
    }
    assert _decide(field_book, open_joint, "vote_2021", "wellbeing_index", measured=False).allowed


def test_fingerprint_identifies_everything_the_certificate_permits(certificate_bytes: Any) -> None:
    base = evaluate_joint_certificate(certificate_bytes(), panel_sha256=PANEL)
    again = evaluate_joint_certificate(certificate_bytes(), panel_sha256=PANEL)
    assert base.fingerprint() == again.fingerprint() and len(base.fingerprint()) == 64
    reordered = evaluate_joint_certificate(
        certificate_bytes(matched_blocks=sorted(base.matched_blocks, reverse=True)),
        panel_sha256=PANEL,
    )
    assert reordered.fingerprint() == base.fingerprint()
    for change in (
        {"matched_block_outputs_allowed": False},
        {"descriptive_core_outputs_allowed": False},
        {"matched_blocks": ["politics"]},
        {"runtime_identity_contract": "a different contract"},
    ):
        narrower = evaluate_joint_certificate(certificate_bytes(**change), panel_sha256=PANEL)
        assert narrower.certified_panel_sha256 == base.certified_panel_sha256
        assert narrower.fingerprint() != base.fingerprint(), change


def test_degraded_fingerprints_differ_by_reason(certificate_bytes: Any) -> None:
    missing = evaluate_joint_certificate(None, panel_sha256=PANEL)
    moved = evaluate_joint_certificate(certificate_bytes(), panel_sha256="c" * 64)
    assert missing.fingerprint() != moved.fingerprint()
