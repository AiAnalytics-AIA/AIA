"""Instrument items: a Study's own questions as evidence fields, internal only, never measured."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.evidence import (
    INSTRUMENT_BLOCK,
    INSTRUMENT_POLICY_VERSION,
    INSTRUMENT_RECOMMENDED_USE,
    MODELLED_INSTRUMENT_POLICY_VERSION,
    MODELLED_INSTRUMENT_RECOMMENDED_USE,
    ClaimBasis,
    ClaimLevel,
    ClaimRequest,
    ClaimRule,
    ClaimSurface,
    Disclosure,
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
    instrument_policy_version,
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
        MODELLED_INSTRUMENT_RECOMMENDED_USE,
        "internal analysis only",
        "INTERNAL_ONLY",
        "MODELED_DISCLOSURE_ALWAYS",
    ]
    for aia_only in (ClaimRule.INTERNAL_ONLY, ClaimRule.MODELED_DISCLOSURE_ALWAYS):
        assert all(aia_only not in claim_rules_for(p) for p in phrases)


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


def test_internal_only_holds_on_its_own_with_a_certificate_and_an_admissible_origin(
    evidence_row: Any, joint_status: Any
) -> None:
    """The row that slips the other two gates (a certificate, the one admissible origin) is
    still refused client-facing by the policy alone."""
    from aia_core.domain.fieldwork import DataOrigin

    table = EvidenceTable.build([row(evidence_row, data_origin=DataOrigin.MODELLED_AI_PANEL)])
    admission = admit_numeric_claims(
        [claim()], table, book=book(), joint_status=joint_status, surface=ClaimSurface.CLIENT_FACING
    )
    assert admission.decision.codes == {ViolationCode.FIELD_INTERNAL_ONLY}


def test_a_row_with_no_origin_no_longer_slips_the_origin_gate(
    evidence_row: Any, joint_status: Any
) -> None:
    """ADR 0024 §2: the gate is an allowlist, so a missing origin is refused too."""
    table = EvidenceTable.build([row(evidence_row, data_origin=None)])
    admission = admit_numeric_claims(
        [claim()], table, book=book(), joint_status=joint_status, surface=ClaimSurface.CLIENT_FACING
    )
    assert admission.decision.codes == {
        ViolationCode.ORIGIN_NOT_ADMISSIBLE,
        ViolationCode.FIELD_INTERNAL_ONLY,
    }


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


# --- aia-instrument-evidence-2: answers from AI respondents built from the population --------

MODELLED = DataOrigin.MODELLED_AI_PANEL


def modelled_book() -> FieldPolicyBook:
    return instrument_policy_book(ITEMS, origin=MODELLED, source=SOURCE)


def modelled_claim(**overrides: Any) -> ClaimRequest:
    args: dict[str, Any] = {
        "fields": (instrument_field("q1"),),
        "basis": ClaimBasis.MODELED,
        "surface": ClaimSurface.CLIENT_FACING,
        "level": ClaimLevel.AGGREGATE,
        "disclosures": frozenset({Disclosure.SCOPE, Disclosure.MODELED_VALUE}),
    }
    args.update(overrides)
    return ClaimRequest(**args)


def test_a_modelled_origin_is_declared_under_its_own_policy_chosen_by_the_origin() -> None:
    """ADR 0024 §3: -2 for MODELLED_AI_PANEL, -1 unchanged for the simulated origins."""
    policy = modelled_book().get("instrument:q1")
    assert instrument_policy_version(MODELLED) == MODELLED_INSTRUMENT_POLICY_VERSION
    assert MODELLED_INSTRUMENT_POLICY_VERSION == "aia-instrument-evidence-2"
    assert instrument_policy_version(DataOrigin.SYNTHETIC_FIXTURE) == INSTRUMENT_POLICY_VERSION
    assert policy.evidence_status is InstrumentStatus.MODELLED_PANEL_RESPONSE
    assert policy.provenance_class is ProvenanceClass.MODELLED
    assert policy.recommended_use_verbatim == MODELLED_INSTRUMENT_RECOMMENDED_USE
    assert policy.claim_rules == (
        *claim_rules_for(MODELLED_INSTRUMENT_RECOMMENDED_USE),
        ClaimRule.MODELED_DISCLOSURE_ALWAYS,
        ClaimRule.INTERNAL_ONLY,
    )
    assert set(policy.claim_rules) == {
        ClaimRule.NEVER_MEASURED_FACT,
        ClaimRule.PERSON_VALUE_MODELED,
        ClaimRule.AGGREGATE_ONLY,
        ClaimRule.REQUIRES_SCOPE,
        ClaimRule.REQUIRES_MODELED_DISCLOSURE,
        ClaimRule.MODELED_DISCLOSURE_ALWAYS,
        ClaimRule.INTERNAL_ONLY,
    }
    assert not policy.eligibility.client_facing_measured_claim
    assert book().get("instrument:q1").evidence_status is InstrumentStatus.SIMULATED_RESPONSE


def test_the_two_policies_never_share_a_declaration_identity() -> None:
    simulated = instrument_declaration_sha256(
        ITEMS, origin=DataOrigin.SYNTHETIC_AI_FICTIONAL, source=SOURCE
    )
    modelled = instrument_declaration_sha256(ITEMS, origin=MODELLED, source=SOURCE)
    assert simulated != modelled == modelled_book().source_sha256


def test_without_a_validation_a_modelled_claim_is_internal_even_fully_disclosed(
    evidence_row: Any, joint_status: Any
) -> None:
    """ADR 0024 §4: nothing earns a validation yet, so -2 carries INTERNAL_ONLY."""
    assert evaluate_claim(modelled_claim(), modelled_book(), joint_status).codes == {
        ViolationCode.FIELD_INTERNAL_ONLY
    }
    internal = modelled_claim(surface=ClaimSurface.INTERNAL, disclosures=frozenset())
    assert evaluate_claim(internal, modelled_book(), MISSING).allowed
    table = EvidenceTable.build([row(evidence_row, data_origin=MODELLED)])
    admission = admit_numeric_claims(
        [claim()],
        table,
        book=modelled_book(),
        joint_status=joint_status,
        surface=ClaimSurface.CLIENT_FACING,
    )
    assert ViolationCode.FIELD_INTERNAL_ONLY in admission.decision.codes
    assert not admission.admitted


def test_a_client_facing_modelled_claim_needs_both_disclosures_whatever_its_basis(
    joint_status: Any,
) -> None:
    """The dictionary's rule asks the modelled disclosure of a measured claim only; -2 asks it
    of every client-facing claim."""
    codes = evaluate_claim(modelled_claim(disclosures=frozenset()), modelled_book(), joint_status)
    assert {
        ViolationCode.SCOPE_DISCLOSURE_MISSING,
        ViolationCode.MODELED_DISCLOSURE_MISSING,
    } <= codes.codes


@pytest.mark.parametrize("surface", list(ClaimSurface))
def test_a_modelled_answer_is_never_a_measured_fact_nor_one_persons(
    surface: ClaimSurface,
) -> None:
    measured = modelled_claim(basis=ClaimBasis.MEASURED, surface=surface)
    assert {
        ViolationCode.NEVER_MEASURED_FACT,
        ViolationCode.NOT_MEASURED_EVIDENCE,
    } <= evaluate_claim(measured, modelled_book(), MISSING).codes
    person = modelled_claim(level=ClaimLevel.INDIVIDUAL, surface=surface)
    assert (
        ViolationCode.INDIVIDUAL_CLAIM_ON_AGGREGATE_FIELD
        in evaluate_claim(person, modelled_book(), MISSING).codes
    )


def test_a_segment_claim_on_modelled_answers_is_allowed_internally() -> None:
    segment = modelled_claim(surface=ClaimSurface.INTERNAL, level=ClaimLevel.SEGMENT)
    assert evaluate_claim(segment, modelled_book(), MISSING).allowed


def test_no_dictionary_can_declare_the_modelled_status() -> None:
    with pytest.raises(FieldPolicyError, match="evidence_status"):
        derive_field_policy(
            field="q1",
            block="survey",
            source="donor",
            evidence_status=InstrumentStatus.MODELLED_PANEL_RESPONSE.value,
            production_grade="B",
            recommended_use=MODELLED_INSTRUMENT_RECOMMENDED_USE,
            description="",
            persona_eligible=False,
        )


# --- what a validation does to -2 (ADR 0024 §4) --------------------------------------------

SYSTEM = "c" * 64
OTHER_SYSTEM = "d" * 64


def validated_book(state: Any, system: str | None = SYSTEM) -> FieldPolicyBook:
    return instrument_policy_book(
        ITEMS, origin=MODELLED, source=SOURCE, respondent_system=system, validation=state
    )


def holdout(on: str = SYSTEM) -> Any:
    from aia_core.domain.evidence import ValidationState, ValidationStatus

    return ValidationState(ValidationStatus.HOLDOUT_VALIDATED, on)


def test_a_current_holdout_takes_a_fully_disclosed_modelled_claim_to_a_client(
    joint_status: Any,
) -> None:
    """The one route out of INTERNAL_ONLY; every other -2 rule still holds."""
    book_ = validated_book(holdout())
    policy = book_.get("instrument:q1")
    assert ClaimRule.INTERNAL_ONLY not in policy.claim_rules
    assert ClaimRule.MODELED_DISCLOSURE_ALWAYS in policy.claim_rules
    assert evaluate_claim(modelled_claim(), book_, joint_status).allowed
    assert {
        ViolationCode.SCOPE_DISCLOSURE_MISSING,
        ViolationCode.MODELED_DISCLOSURE_MISSING,
    } <= evaluate_claim(modelled_claim(disclosures=frozenset()), book_, joint_status).codes
    measured = modelled_claim(basis=ClaimBasis.MEASURED)
    assert ViolationCode.NEVER_MEASURED_FACT in evaluate_claim(measured, book_, joint_status).codes
    person = modelled_claim(level=ClaimLevel.INDIVIDUAL)
    assert (
        ViolationCode.INDIVIDUAL_CLAIM_ON_AGGREGATE_FIELD
        in evaluate_claim(person, book_, joint_status).codes
    )
    # The joint certificate is still required client-facing (ADR 0024 §6).
    assert (
        ViolationCode.JOINT_CERTIFICATE_DEGRADED
        in evaluate_claim(modelled_claim(), book_, MISSING).codes
    )


@pytest.mark.parametrize(
    "state",
    [
        None,
        "stale",
        "smoke",
    ],
)
def test_no_validation_a_stale_one_or_smoke_keeps_a_modelled_claim_internal(
    state: str | None, joint_status: Any
) -> None:
    from aia_core.domain.evidence import ValidationState, ValidationStatus

    given = {
        None: None,
        "stale": holdout(on=OTHER_SYSTEM),
        "smoke": ValidationState(ValidationStatus.SMOKE_VALIDATED, SYSTEM),
    }[state]
    book_ = validated_book(given)
    assert ClaimRule.INTERNAL_ONLY in book_.get("instrument:q1").claim_rules
    assert (
        ViolationCode.FIELD_INTERNAL_ONLY
        in evaluate_claim(modelled_claim(), book_, joint_status).codes
    )


def test_the_declaration_identity_moves_with_the_system_and_the_validation() -> None:
    ids = {
        validated_book(None, system=None).source_sha256,
        validated_book(None).source_sha256,
        validated_book(None, system=OTHER_SYSTEM).source_sha256,
        validated_book(holdout()).source_sha256,
    }
    assert len(ids) == 4
    # A stale validation judges as no validation on the same system: the same declaration.
    assert (
        validated_book(holdout(on=OTHER_SYSTEM)).source_sha256 == validated_book(None).source_sha256
    )


def test_simulated_answers_are_never_validated_and_their_identity_never_moves() -> None:
    before = instrument_declaration_sha256(
        ITEMS, origin=DataOrigin.SYNTHETIC_FIXTURE, source=SOURCE
    )
    assert before == book(DataOrigin.SYNTHETIC_FIXTURE).source_sha256
    for kwargs in ({"respondent_system": SYSTEM}, {"validation": holdout()}):
        with pytest.raises(InstrumentPolicyRefused, match="never validated"):
            instrument_policy_book(
                ITEMS, origin=DataOrigin.SYNTHETIC_FIXTURE, source=SOURCE, **kwargs
            )


def test_a_validation_needs_the_current_system_and_a_system_is_a_fingerprint() -> None:
    with pytest.raises(ValueError, match="current respondent system"):
        validated_book(holdout(), system=None)
    with pytest.raises(ValueError, match="SHA-256"):
        validated_book(None, system="v1")
