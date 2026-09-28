"""Instrument items: a Study's own questions as evidence fields, internal only, never measured."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.evidence import (
    INSTRUMENT_BLOCK,
    INSTRUMENT_POLICY_VERSION,
    INSTRUMENT_RECOMMENDED_USE,
    ClaimBasis,
    ClaimLevel,
    ClaimRequest,
    ClaimRule,
    ClaimSurface,
    EvidenceTable,
    FieldPolicyBook,
    FieldPolicyError,
    InstrumentItem,
    InstrumentPolicyRefused,
    InstrumentStatus,
    NumericClaim,
    ProvenanceClass,
    ViolationCode,
    admit_numeric_claims,
    claim_rules_for,
    derive_field_policy,
    evaluate_claim,
    instrument_declaration_sha256,
    instrument_field,
    instrument_policy,
    instrument_policy_book,
    load_joint_status,
)
from aia_core.domain.fieldwork import NON_EVIDENCE_ORIGINS, DataOrigin

ITEMS = (
    InstrumentItem("q1", "Jak často pijete kávu?"),
    InstrumentItem("q2", "Co si ráno koupíte?"),
)
SOURCE = "fieldwork aia-synthetic-fixture-1"
MISSING = load_joint_status(None, measured_panel_sha256=None)


def book(origin: DataOrigin | None = DataOrigin.SYNTHETIC_AI_FICTIONAL) -> FieldPolicyBook:
    return instrument_policy_book(ITEMS, origin=origin, source=SOURCE)


def row(evidence_row: Any, **overrides: Any) -> Any:
    args: dict[str, Any] = {
        "fields": (instrument_field("q1"),),
        "basis": ClaimBasis.MODELED,
        "disclosures": frozenset(),
        "data_origin": DataOrigin.SYNTHETIC_AI_FICTIONAL,
    }
    args.update(overrides)
    return evidence_row("q1.top2box", **args)


def claim() -> NumericClaim:
    return NumericClaim("c1", "q1.top2box", "top2box_pct", 42.5, "%")


# --- the declaration ----------------------------------------------------------------------


def test_the_stated_use_and_the_enforced_rules_cannot_drift_apart() -> None:
    policy = book().get("instrument:q1")
    assert policy.claim_rules == (
        *claim_rules_for(INSTRUMENT_RECOMMENDED_USE),
        ClaimRule.INTERNAL_ONLY,
    )
    assert set(policy.claim_rules) == {
        ClaimRule.NEVER_MEASURED_FACT,
        ClaimRule.PERSON_VALUE_MODELED,
        ClaimRule.AGGREGATE_ONLY,
        ClaimRule.INTERNAL_ONLY,
    }


def test_an_item_is_modelled_ungraded_and_eligible_for_internal_analysis_only() -> None:
    policy = book().get("instrument:q1")
    assert policy.evidence_status is InstrumentStatus.SIMULATED_RESPONSE
    assert policy.provenance_class is ProvenanceClass.MODELLED
    assert policy.production_grade is None
    assert policy.block == INSTRUMENT_BLOCK
    assert policy.description == "Jak často pijete kávu?"
    assert policy.eligibility.as_dict() == {
        "analysis": True,
        "client_facing_measured_claim": False,
        "filtering": False,
        "simulation": False,
        "persona_construction": False,
        "weighting": False,
    }


@pytest.mark.parametrize("origin", sorted(NON_EVIDENCE_ORIGINS))
def test_every_simulated_origin_is_declared(origin: DataOrigin) -> None:
    assert len(book(origin)) == 2


def test_answers_of_unknown_origin_have_no_policy() -> None:
    with pytest.raises(InstrumentPolicyRefused, match="unknown"):
        book(None)
    with pytest.raises(InstrumentPolicyRefused):
        instrument_declaration_sha256(ITEMS, origin=None, source=SOURCE)


def test_no_dictionary_can_declare_an_instrument_status() -> None:
    with pytest.raises(FieldPolicyError, match="evidence_status"):
        derive_field_policy(
            field="q1",
            block="survey",
            source="donor",
            evidence_status=InstrumentStatus.SIMULATED_RESPONSE.value,
            production_grade="B",
            recommended_use=INSTRUMENT_RECOMMENDED_USE,
            description="",
            persona_eligible=False,
        )


def test_internal_only_is_never_extracted_from_dictionary_prose(
    dictionary_rows: list[dict[str, str]],
) -> None:
    phrases = [r["recommended_use"] for r in dictionary_rows] + [
        INSTRUMENT_RECOMMENDED_USE,
        "internal analysis only",
        "INTERNAL_ONLY",
    ]
    assert all(ClaimRule.INTERNAL_ONLY not in claim_rules_for(p) for p in phrases)


def test_the_declaration_is_namespaced_complete_and_refuses_duplicates() -> None:
    declared = book()
    assert set(declared.fields) == {"instrument:q1", "instrument:q2"}
    assert "q1" not in declared
    with pytest.raises(FieldPolicyError, match="twice"):
        instrument_policy_book(
            (*ITEMS, ITEMS[0]), origin=DataOrigin.SYNTHETIC_FIXTURE, source=SOURCE
        )
    with pytest.raises(InstrumentPolicyRefused, match="no item"):
        instrument_policy_book((), origin=DataOrigin.SYNTHETIC_FIXTURE, source=SOURCE)


@pytest.mark.parametrize("bad", ["", " q1", "q1 "])
def test_an_item_needs_a_clean_id_and_a_text(bad: str) -> None:
    with pytest.raises(ValueError):
        instrument_field(bad)
    with pytest.raises(ValueError):
        InstrumentItem(bad, "text")
    with pytest.raises(ValueError, match="no question text"):
        InstrumentItem("q1", "  ")
    with pytest.raises(ValueError, match="source"):
        instrument_policy(ITEMS[0], origin=DataOrigin.SYNTHETIC_FIXTURE, source=" ")


def test_the_declaration_identity_moves_with_everything_it_declares() -> None:
    base = instrument_declaration_sha256(ITEMS, origin=DataOrigin.SYNTHETIC_FIXTURE, source=SOURCE)
    assert book(DataOrigin.SYNTHETIC_FIXTURE).source_sha256 == base
    variants = {
        instrument_declaration_sha256(
            ITEMS, origin=DataOrigin.SYNTHETIC_AI_FICTIONAL, source=SOURCE
        ),
        instrument_declaration_sha256(
            ITEMS[:1], origin=DataOrigin.SYNTHETIC_FIXTURE, source=SOURCE
        ),
        instrument_declaration_sha256(ITEMS, origin=DataOrigin.SYNTHETIC_FIXTURE, source="other"),
        instrument_declaration_sha256(
            (InstrumentItem("q1", "Jak často pijete čaj?"), ITEMS[1]),
            origin=DataOrigin.SYNTHETIC_FIXTURE,
            source=SOURCE,
        ),
    }
    assert base not in variants and len(variants) == 4
    assert INSTRUMENT_POLICY_VERSION == "aia-instrument-evidence-1"


# --- what the claim gate admits on it ----------------------------------------------------


def test_an_internal_modelled_aggregate_claim_is_admitted_without_a_certificate(
    evidence_row: Any,
) -> None:
    table = EvidenceTable.build([row(evidence_row)])
    admission = admit_numeric_claims(
        [claim()], table, book=book(), joint_status=MISSING, surface=ClaimSurface.INTERNAL
    )
    assert admission.decision.allowed
    assert [c.claim_id for c in admission.admitted] == ["c1"]


def test_client_facing_is_refused_by_three_independent_gates(evidence_row: Any) -> None:
    table = EvidenceTable.build([row(evidence_row)])
    admission = admit_numeric_claims(
        [claim()], table, book=book(), joint_status=MISSING, surface=ClaimSurface.CLIENT_FACING
    )
    assert not admission.admitted
    assert {
        ViolationCode.FIELD_INTERNAL_ONLY,
        ViolationCode.SYNTHETIC_DATA_ORIGIN,
        ViolationCode.JOINT_CERTIFICATE_DEGRADED,
    } <= admission.decision.codes


def test_internal_only_holds_on_its_own_with_a_certificate_and_no_origin(
    evidence_row: Any, joint_status: Any
) -> None:
    """The row that slipped the other two gates is still refused client-facing."""
    table = EvidenceTable.build([row(evidence_row, data_origin=None)])
    admission = admit_numeric_claims(
        [claim()], table, book=book(), joint_status=joint_status, surface=ClaimSurface.CLIENT_FACING
    )
    assert admission.decision.codes == {ViolationCode.FIELD_INTERNAL_ONLY}


def test_an_instrument_item_never_backs_a_measured_claim_even_internally() -> None:
    request = ClaimRequest(
        fields=(instrument_field("q1"),),
        basis=ClaimBasis.MEASURED,
        surface=ClaimSurface.INTERNAL,
        level=ClaimLevel.AGGREGATE,
    )
    codes = evaluate_claim(request, book(), MISSING).codes
    assert {ViolationCode.NEVER_MEASURED_FACT, ViolationCode.NOT_MEASURED_EVIDENCE} <= codes


def test_an_instrument_item_never_describes_one_person() -> None:
    request = ClaimRequest(
        fields=(instrument_field("q1"),),
        basis=ClaimBasis.MODELED,
        surface=ClaimSurface.INTERNAL,
        level=ClaimLevel.INDIVIDUAL,
    )
    assert evaluate_claim(request, book(), MISSING).codes == {
        ViolationCode.INDIVIDUAL_CLAIM_ON_AGGREGATE_FIELD
    }


def test_two_items_of_one_instrument_are_one_joint_unit() -> None:
    request = ClaimRequest(
        fields=(instrument_field("q1"), instrument_field("q2")),
        basis=ClaimBasis.MODELED,
        surface=ClaimSurface.INTERNAL,
        level=ClaimLevel.SEGMENT,
    )
    assert evaluate_claim(request, book(), MISSING).allowed


def test_a_population_field_is_still_undeclared_in_an_instrument_book() -> None:
    request = ClaimRequest(
        fields=("vek",),
        basis=ClaimBasis.MODELED,
        surface=ClaimSurface.INTERNAL,
        level=ClaimLevel.AGGREGATE,
    )
    assert evaluate_claim(request, book(), MISSING).codes == {ViolationCode.FIELD_UNDECLARED}
