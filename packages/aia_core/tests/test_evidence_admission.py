"""Evidence admission: a model's number becomes a claim only through every gate."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.evidence import (
    AdmittedClaim,
    ClaimBasis,
    ClaimLevel,
    ClaimSurface,
    EvidenceTable,
    Interval,
    NumericClaim,
    SupportAssessment,
    SupportEvidence,
    SupportStatus,
    TierUseCase,
    UnsupportedEstimate,
    ViolationCode,
    admit_numeric_claims,
    assess_support,
)

CLIENT = ClaimSurface.CLIENT_FACING


@pytest.fixture
def admit(field_book: Any, joint_status: Any) -> Any:
    def run(
        claims: list[NumericClaim], table: EvidenceTable, surface: ClaimSurface = CLIENT
    ) -> Any:
        return admit_numeric_claims(
            claims, table, book=field_book, joint_status=joint_status, surface=surface
        )

    return run


def nc(claim_id: str = "c1", ref: str = "E1", **kw: Any) -> NumericClaim:
    args: dict[str, Any] = {"metric": "top2box_pct", "value": 42.5, "unit": "%"}
    args.update(kw)
    return NumericClaim(claim_id=claim_id, evidence_ref=ref, **args)


# --- the evidence table -----------------------------------------------------------------


def test_row_unit_is_derived_from_its_metric(evidence_row: Any) -> None:
    assert evidence_row(metric="n", value=600.0, decimals=0, interval=None).unit.value == (
        "respondents"
    )
    assert evidence_row().unit.value == "%"


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"evidence_ref": " "}, "evidence_ref"),
        ({"fields": ()}, "fields"),
        ({"value": float("nan")}, "finite"),
        ({"decimals": 9}, "decimals"),
        ({"value": 42.54}, "not rounded"),
        ({"interval": Interval(1.0, 2.0, 0.95)}, "outside"),
        ({"dimension_tiers": {"d1": "B"}}, "use case"),
    ],
)
def test_malformed_rows_are_refused(
    evidence_row: Any, overrides: dict[str, Any], match: str
) -> None:
    ref = overrides.pop("evidence_ref", "E1")
    with pytest.raises(ValueError, match=match):
        evidence_row(ref, **overrides)


def test_suppressed_rows_are_removed_from_the_table(evidence_row: Any) -> None:
    thin = assess_support(SupportEvidence(n=30, effective_n=20.0))
    table = EvidenceTable.build([evidence_row("E1"), evidence_row("E2", support=thin)])
    assert set(table.rows) == {"E1"}
    assert set(table.suppressed) == {"E2"}


def test_duplicate_evidence_refs_are_refused(evidence_row: Any) -> None:
    with pytest.raises(ValueError, match="twice"):
        EvidenceTable.build([evidence_row("E1"), evidence_row("E1")])


def test_table_fingerprint_moves_with_content(evidence_row: Any) -> None:
    a = EvidenceTable.build([evidence_row("E1")])
    b = EvidenceTable.build([evidence_row("E1", value=42.6)])
    assert a.fingerprint() == EvidenceTable.build([evidence_row("E1")]).fingerprint()
    assert a.fingerprint() != b.fingerprint()


# --- admission ------------------------------------------------------------------------------


def test_exact_copy_of_a_supported_row_is_admitted(admit: Any, evidence_row: Any) -> None:
    table = EvidenceTable.build([evidence_row()])
    result = admit([nc()], table)
    assert result.decision.allowed
    [claim] = result.admitted
    assert isinstance(claim, AdmittedClaim)
    assert claim.value == 42.5 and claim.row.evidence_ref == "E1" and not claim.indicative


def test_admitted_claims_cannot_be_forged(evidence_row: Any) -> None:
    with pytest.raises(ValueError, match="admitted only by"):
        AdmittedClaim("c1", evidence_row(), CLIENT, object())


def test_no_claims_is_a_valid_admission(admit: Any, evidence_row: Any) -> None:
    result = admit([], EvidenceTable.build([evidence_row()]))
    assert result.decision.allowed and result.admitted == ()


@pytest.mark.parametrize(
    ("claim", "code"),
    [
        (nc(ref="EXTERNAL-1"), ViolationCode.EVIDENCE_REF_UNKNOWN),
        (nc(metric="t_score"), ViolationCode.METRIC_NOT_ALLOWED),
        (nc(metric="mean"), ViolationCode.METRIC_MISMATCH),
        (nc(unit="respondents"), ViolationCode.UNIT_MISMATCH),
        (nc(value=42.0), ViolationCode.VALUE_MISMATCH),
        (nc(value=42.51), ViolationCode.VALUE_MISMATCH),
        (nc(value=float("inf")), ViolationCode.VALUE_MISMATCH),
    ],
)
def test_forgery_and_drift_are_refused(
    admit: Any, evidence_row: Any, claim: NumericClaim, code: ViolationCode
) -> None:
    result = admit([claim], EvidenceTable.build([evidence_row()]))
    assert code in result.decision.codes
    assert result.admitted == ()


def test_citing_a_suppressed_row_says_why(admit: Any, evidence_row: Any) -> None:
    thin = assess_support(SupportEvidence(n=30, effective_n=20.0))
    table = EvidenceTable.build([evidence_row("E1", support=thin)])
    result = admit([nc()], table)
    assert result.decision.codes == {ViolationCode.EVIDENCE_SUPPRESSED}
    assert "min_cell" in result.decision.violations[0].detail


def test_one_bad_claim_admits_nothing(admit: Any, evidence_row: Any) -> None:
    table = EvidenceTable.build([evidence_row("E1"), evidence_row("E2")])
    result = admit([nc("c1", "E1"), nc("c2", "E2", value=1.0)], table)
    assert not result.decision.allowed and result.admitted == ()
    assert all(v.subject.startswith("c2") for v in result.decision.violations)


def test_duplicate_claim_ids_are_refused(admit: Any, evidence_row: Any) -> None:
    result = admit([nc("c1"), nc("c1")], EvidenceTable.build([evidence_row()]))
    assert ViolationCode.DUPLICATE_CLAIM_ID in result.decision.codes


def test_client_estimate_without_interval_is_refused(admit: Any, evidence_row: Any) -> None:
    table = EvidenceTable.build([evidence_row(interval=None)])
    assert admit([nc()], table).decision.codes == {ViolationCode.INTERVAL_MISSING}
    assert admit([nc()], table, ClaimSurface.INTERNAL).decision.allowed


def test_counts_need_no_interval(admit: Any, evidence_row: Any) -> None:
    table = EvidenceTable.build([evidence_row(metric="n", value=600.0, decimals=0, interval=None)])
    claim = nc(metric="n", value=600.0, unit="respondents")
    assert admit([claim], table).decision.allowed


def test_field_policy_runs_on_every_claim(admit: Any, evidence_row: Any) -> None:
    table = EvidenceTable.build([evidence_row(fields=("deal_seeking_1_10",))])
    codes = admit([nc()], table).decision.codes
    assert ViolationCode.NEVER_MEASURED_FACT in codes


def test_joint_structure_runs_on_every_claim(admit: Any, evidence_row: Any) -> None:
    row = evidence_row(fields=("trust_courts", "wellbeing_index"), level=ClaimLevel.SEGMENT)
    codes = admit([nc()], EvidenceTable.build([row])).decision.codes
    assert ViolationCode.CROSS_BLOCK_NOT_SAME_PERSON in codes


def test_modelled_row_backs_a_modelled_claim(admit: Any, evidence_row: Any) -> None:
    row = evidence_row(fields=("deal_seeking_1_10",), basis=ClaimBasis.MODELED)
    assert admit([nc()], EvidenceTable.build([row])).decision.allowed


def test_tier_gate_runs_when_the_row_names_dimensions(admit: Any, evidence_row: Any) -> None:
    row = evidence_row(use_case=TierUseCase.SEGMENTATION, dimension_tiers={"d1": "B"})
    assert admit([nc()], EvidenceTable.build([row])).decision.codes == {
        ViolationCode.TIER_INSUFFICIENT
    }


def test_indicative_support_is_admitted_and_flagged(admit: Any, evidence_row: Any) -> None:
    indicative = assess_support(SupportEvidence(n=200, effective_n=40.0))
    assert indicative.status is SupportStatus.INDICATIVE
    result = admit([nc()], EvidenceTable.build([evidence_row(support=indicative)]))
    assert result.admitted[0].indicative


def test_a_hand_written_reportable_status_never_reaches_the_table(evidence_row: Any) -> None:
    """The forged-support route: a REPORTABLE status with no evidence behind it."""
    with pytest.raises(UnsupportedEstimate):
        evidence_row(support=SupportAssessment(SupportStatus.REPORTABLE))


def test_a_row_never_assessed_cannot_be_cited(admit: Any, evidence_row: Any) -> None:
    table = EvidenceTable.build([evidence_row(support=SupportAssessment())])
    assert admit([nc()], table).decision.codes == {ViolationCode.EVIDENCE_SUPPRESSED}
