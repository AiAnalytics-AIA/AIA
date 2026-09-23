"""The permissible-claim policy and the factual layer."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.evidence import (
    ClaimBasis,
    ClaimLevel,
    ClaimRequest,
    ClaimSurface,
    Disclosure,
    FactualContract,
    FactualContractRefused,
    FactualResolution,
    QuestionFactMetadata,
    ViolationCode,
    evaluate_claim,
    factual_answer,
    resolve_factual_contract,
)

M, D = ClaimBasis.MEASURED, ClaimBasis.MODELED
CLIENT, INTERNAL = ClaimSurface.CLIENT_FACING, ClaimSurface.INTERNAL
ALL_DISCLOSURES = frozenset(Disclosure)


def claim(*fields: str, **kw: Any) -> ClaimRequest:
    args: dict[str, Any] = {
        "basis": M,
        "surface": CLIENT,
        "level": ClaimLevel.AGGREGATE,
        "disclosures": ALL_DISCLOSURES,
    }
    args.update(kw)
    return ClaimRequest(fields=fields, **args)


@pytest.fixture
def decide(field_book: Any, joint_status: Any) -> Any:
    def run(request: ClaimRequest) -> frozenset[ViolationCode]:
        return evaluate_claim(request, field_book, joint_status).codes

    return run


def test_a_claim_must_name_its_fields() -> None:
    with pytest.raises(ValueError):
        ClaimRequest(fields=(), basis=M, surface=CLIENT, level=ClaimLevel.AGGREGATE)


def test_measured_core_claim_with_scope_is_allowed(decide: Any) -> None:
    assert decide(claim("vek")) == frozenset()


def test_undeclared_field_refuses(decide: Any) -> None:
    assert decide(claim("life_stage_derived")) == {ViolationCode.FIELD_UNDECLARED}
    assert decide(claim("_analysis_weight", basis=D, surface=INTERNAL)) == {
        ViolationCode.FIELD_UNDECLARED
    }


@pytest.mark.parametrize(
    "field", ["panel_row_id", "vaha_strukturalni_2025", "donor_id_mental_health"]
)
def test_audit_only_backs_nothing_anywhere(decide: Any, field: str) -> None:
    assert decide(claim(field, basis=D, surface=INTERNAL)) == {ViolationCode.FIELD_AUDIT_ONLY}


def test_never_measured_fact_cannot_back_a_measured_claim(decide: Any) -> None:
    codes = decide(claim("deal_seeking_1_10"))
    assert ViolationCode.NEVER_MEASURED_FACT in codes
    assert ViolationCode.NOT_MEASURED_EVIDENCE in codes
    # ...not even internally
    assert ViolationCode.NEVER_MEASURED_FACT in decide(claim("deal_seeking_1_10", surface=INTERNAL))


def test_never_measured_fact_may_back_a_modelled_claim(decide: Any) -> None:
    assert decide(claim("deal_seeking_1_10", basis=D)) == frozenset()


def test_value_proxy_is_never_a_direct_measurement(decide: Any) -> None:
    codes = decide(claim("value_security"))
    assert codes == {ViolationCode.NEVER_DIRECT_SCHWARTZ, ViolationCode.NOT_MEASURED_EVIDENCE}
    assert decide(claim("value_security", basis=D)) == frozenset()


def test_person_level_claim_on_aggregate_field_refuses(decide: Any) -> None:
    assert decide(claim("has_savings", level=ClaimLevel.INDIVIDUAL)) == {
        ViolationCode.INDIVIDUAL_CLAIM_ON_AGGREGATE_FIELD
    }
    assert decide(claim("has_savings")) == frozenset()


@pytest.mark.parametrize(
    ("field", "missing", "code"),
    [
        ("vek", Disclosure.SCOPE, ViolationCode.SCOPE_DISCLOSURE_MISSING),
        ("tv_daily_minutes", Disclosure.MODELED_VALUE, ViolationCode.MODELED_DISCLOSURE_MISSING),
        ("vote_2021", Disclosure.HISTORICAL, ViolationCode.HISTORICAL_DISCLOSURE_MISSING),
    ],
)
def test_client_facing_disclosures(
    decide: Any, field: str, missing: Disclosure, code: ViolationCode
) -> None:
    assert decide(claim(field, disclosures=ALL_DISCLOSURES - {missing})) == {code}
    assert decide(claim(field, disclosures=ALL_DISCLOSURES - {missing}, surface=INTERNAL)) == set()


def test_modelled_basis_is_itself_the_modelled_value_disclosure(decide: Any) -> None:
    request = claim("tv_daily_minutes", basis=D, disclosures=frozenset({Disclosure.SCOPE}))
    assert decide(request) == frozenset()


def test_mandated_weight_scheme(decide: Any) -> None:
    field = "is_procurement_buyer_current"
    assert decide(claim(field, weight_scheme="vaha_strukturalni_2025")) == frozenset()
    assert decide(claim(field, weight_scheme="vaha_kalibrovana")) == {
        ViolationCode.WEIGHT_SCHEME_MISMATCH
    }
    assert decide(claim(field)) == {ViolationCode.WEIGHT_SCHEME_MISMATCH}


def test_cross_block_segment_is_joint_whatever_the_caller_says(decide: Any) -> None:
    codes = decide(claim("wellbeing_index", "vote_2021", level=ClaimLevel.SEGMENT))
    assert {
        ViolationCode.CROSS_BLOCK_JOINT_CLAIM,
        ViolationCode.CROSS_BLOCK_NOT_SAME_PERSON,
        ViolationCode.CLIENT_JOINT_OUTPUT,
    } <= codes


def test_persona_profile_across_blocks_is_not_same_person_truth(decide: Any) -> None:
    codes = decide(
        claim("trust_courts", "wellbeing_index", level=ClaimLevel.INDIVIDUAL, surface=INTERNAL)
    )
    assert codes == {
        ViolationCode.CROSS_BLOCK_JOINT_CLAIM,
        ViolationCode.CROSS_BLOCK_NOT_SAME_PERSON,
    }


def test_demographic_breakdown_of_a_matched_block_is_allowed(decide: Any) -> None:
    assert decide(claim("trust_courts", "vek", level=ClaimLevel.SEGMENT)) == frozenset()


def test_separate_aggregate_statements_are_not_joint(decide: Any) -> None:
    assert decide(claim("trust_courts", "wellbeing_index")) == frozenset()


def test_every_violation_is_reported(decide: Any) -> None:
    codes = decide(
        claim(
            "deal_seeking_1_10",
            "wellbeing_index",
            "no_such_field",
            level=ClaimLevel.SEGMENT,
            disclosures=frozenset(),
        )
    )
    assert {
        ViolationCode.FIELD_UNDECLARED,
        ViolationCode.NEVER_MEASURED_FACT,
        ViolationCode.SCOPE_DISCLOSURE_MISSING,
        ViolationCode.CROSS_BLOCK_JOINT_CLAIM,
    } <= codes


def test_degraded_certificate_blocks_client_claims(
    field_book: Any, degraded_joint_status: Any
) -> None:
    decision = evaluate_claim(claim("vek"), field_book, degraded_joint_status)
    assert decision.codes == {ViolationCode.JOINT_CERTIFICATE_DEGRADED}


# --- factual layer ----------------------------------------------------------------------


def test_explicit_source_field_wins(field_book: Any) -> None:
    contract = resolve_factual_contract(QuestionFactMetadata(fact_source_field="vek"), field_book)
    assert contract == FactualContract(FactualResolution.FACTUAL, "vek", ClaimBasis.MEASURED)


def test_factual_field_that_is_modelled_reports_a_modelled_basis(field_book: Any) -> None:
    contract = resolve_factual_contract(
        QuestionFactMetadata(fact_source_field="deal_seeking_1_10", fact_kind="fact"), field_book
    )
    assert contract.basis is ClaimBasis.MODELED


def test_attitude_is_never_factual(field_book: Any) -> None:
    contract = resolve_factual_contract(QuestionFactMetadata(fact_kind="attitude"), field_book)
    assert contract.resolution is FactualResolution.NOT_FACTUAL


def test_no_metadata_is_undeclared_not_factual(field_book: Any) -> None:
    contract = resolve_factual_contract(QuestionFactMetadata(), field_book)
    assert contract.resolution is FactualResolution.UNDECLARED
    assert contract.source_field is None


@pytest.mark.parametrize(
    ("metadata", "match"),
    [
        (QuestionFactMetadata(fact_kind="fact"), "fact_source_field"),
        (QuestionFactMetadata(fact_kind="opinion"), "unknown fact_kind"),
        (QuestionFactMetadata(fact_source_field="vek", fact_kind="attitude"), "attitude"),
        (QuestionFactMetadata(fact_source_field="no_such_column"), "not in the field dictionary"),
        (QuestionFactMetadata(fact_source_field="panel_row_id"), "audit-only"),
    ],
)
def test_metadata_that_would_need_an_invented_fact_is_refused(
    field_book: Any, metadata: QuestionFactMetadata, match: str
) -> None:
    with pytest.raises(FactualContractRefused, match=match):
        resolve_factual_contract(metadata, field_book)


def test_factual_answer_is_the_panel_value_and_missing_stays_missing(field_book: Any) -> None:
    contract = resolve_factual_contract(QuestionFactMetadata(fact_source_field="vek"), field_book)
    assert factual_answer(contract, {"vek": 43}) == 43
    assert factual_answer(contract, {"pohlavi": 1}) is None
    with pytest.raises(ValueError, match="not a factual contract"):
        factual_answer(FactualContract(FactualResolution.UNDECLARED), {"vek": 43})
