"""Field policy: derivation, the book's fail-closed lookups, and document loading.

Exact parity of the derivation against all 400 real fields lives in
``test_evidence_gate_parity.py``; these tests pin each rule on synthetic rows so
they run everywhere.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

import pytest

from aia_core.domain.evidence import (
    ClaimBasis,
    ClaimLevel,
    ClaimRequest,
    ClaimRule,
    ClaimSurface,
    Disclosure,
    EvidenceStatus,
    FieldPolicyBook,
    FieldPolicyError,
    FieldPolicyInconsistent,
    FieldUse,
    GateBlocked,
    ProductionGrade,
    ProvenanceClass,
    QuestionFactMetadata,
    UndeclaredField,
    Violation,
    ViolationCode,
    allow,
    block,
    claim_rules_for,
    combine,
    derive_eligibility,
    derive_field_policy,
    evaluate_claim,
    mandated_weight_scheme,
    provenance_class_for,
    resolve_factual_contract,
)
from aia_core.domain.population.policy import FieldUse as ContractUse
from aia_core.domain.population.policy import build_field_policy

SHA = "a" * 64


# --- gate primitives ------------------------------------------------------------


def test_allow_is_the_absence_of_violations() -> None:
    assert allow().allowed
    assert not block(ViolationCode.FIELD_UNDECLARED, "x", "y").allowed


def test_combine_keeps_every_violation_once_in_order() -> None:
    a = block(ViolationCode.FIELD_UNDECLARED, "x", "why")
    b = block(ViolationCode.SUPPORT_SUPPRESSED, "cell", "why")
    merged = combine([a, allow(), b, a])
    assert [v.code for v in merged.violations] == [
        ViolationCode.FIELD_UNDECLARED,
        ViolationCode.SUPPORT_SUPPRESSED,
    ]
    assert not merged.allowed


def test_require_raises_with_every_reason() -> None:
    decision = combine(
        [
            block(ViolationCode.FIELD_UNDECLARED, "x", "a"),
            block(ViolationCode.INTERVAL_MISSING, "d", "b"),
        ]
    )
    with pytest.raises(GateBlocked) as caught:
        decision.require()
    assert caught.value.decision is decision
    assert "FIELD_UNDECLARED" in str(caught.value) and "INTERVAL_MISSING" in str(caught.value)
    allow().require()


def test_violation_renders_code_subject_detail() -> None:
    assert str(Violation(ViolationCode.UNIT_MISMATCH, "c1", "pct vs n")) == (
        "UNIT_MISMATCH: c1 -- pct vs n"
    )


# --- derivation -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("MEASURED_CORE_PIAAC", ProvenanceClass.OBSERVED),
        ("CANONICAL_CORE", ProvenanceClass.OBSERVED),
        ("POPULATION_ANCHOR", ProvenanceClass.OBSERVED),
        ("MATCHED_WHOLE_BLOCK", ProvenanceClass.DONOR_MATCHED),
        ("DERIVED_QC", ProvenanceClass.DERIVED),
        ("CALIBRATED_ONLINE_SAMPLE", ProvenanceClass.CALIBRATED),
        ("MODELED_MARKETING_PRIOR", ProvenanceClass.MODELLED),
        ("HYBRID_MEASURED_PIAAC_OR_MODELED", ProvenanceClass.HYBRID),
        ("PROVENANCE_OR_CORE", ProvenanceClass.PROVENANCE),
        ("NEW_WEIGHT", ProvenanceClass.UNCLASSIFIED),
        ("BENCHMARK_WEIGHT", ProvenanceClass.UNCLASSIFIED),
    ],
)
def test_provenance_class_for(status: str, expected: ProvenanceClass) -> None:
    assert provenance_class_for(status) is expected


def test_every_declared_status_has_a_provenance_class() -> None:
    classes = {provenance_class_for(s.value) for s in EvidenceStatus}
    assert ProvenanceClass.OBSERVED in classes and ProvenanceClass.MODELLED in classes


@pytest.mark.parametrize(
    ("use", "rules"),
    [
        ("PERSONA_OR_ANALYSIS_WITH_SCOPE", (ClaimRule.REQUIRES_SCOPE,)),
        (
            "behavioral prior / simulation modifier, never measured fact",
            (ClaimRule.NEVER_MEASURED_FACT,),
        ),
        (
            "simulation prior; never claim direct Schwartz measurement",
            (ClaimRule.NEVER_DIRECT_SCHWARTZ,),
        ),
        (
            "population segmentation / reach; person value is modeled, not measured",
            (ClaimRule.PERSON_VALUE_MODELED, ClaimRule.AGGREGATE_ONLY),
        ),
        (
            "aggregate planning and persona background with modeled-value disclosure",
            (ClaimRule.AGGREGATE_ONLY, ClaimRule.REQUIRES_MODELED_DISCLOSURE),
        ),
        ("AUDIT_ONLY", (ClaimRule.AUDIT_ONLY,)),
        ("technical/provenance only", (ClaimRule.AUDIT_ONLY,)),
        ("AUDIT_AND_PERSONA_CONFIDENCE", ()),
        ("HISTORICAL_OR_EXPLORATORY", (ClaimRule.HISTORICAL_OR_EXPLORATORY,)),
        ("audience selection; use vaha_strukturalni_2025", (ClaimRule.SPECIFIED_WEIGHT_REQUIRED,)),
        ("", ()),
    ],
)
def test_claim_rules_for(use: str, rules: tuple[ClaimRule, ...]) -> None:
    assert claim_rules_for(use) == rules


def test_mandated_weight_scheme() -> None:
    assert mandated_weight_scheme("audience selection; use vaha_strukturalni_2025") == (
        "vaha_strukturalni_2025"
    )
    assert mandated_weight_scheme("PERSONA_OR_ANALYSIS_WITH_SCOPE") is None


def _policy(**overrides: Any) -> Any:
    args: dict[str, Any] = {
        "field": "f",
        "block": "core",
        "source": "s",
        "evidence_status": "CANONICAL_CORE",
        "production_grade": "A",
        "recommended_use": "PERSONA_OR_ANALYSIS_WITH_SCOPE",
        "description": "d",
        "persona_eligible": True,
    }
    args.update(overrides)
    return derive_field_policy(**args)


def test_measured_core_field_is_eligible_for_everything_but_weighting() -> None:
    p = _policy()
    assert p.eligibility.as_dict() == {
        "analysis": True,
        "client_facing_measured_claim": True,
        "filtering": True,
        "simulation": True,
        "persona_construction": True,
        "weighting": False,
    }


def test_never_measured_fact_cannot_back_a_client_measured_claim() -> None:
    p = _policy(
        evidence_status="MODELED_MARKETING_PRIOR",
        recommended_use="behavioral prior / simulation modifier, never measured fact",
    )
    assert not p.eligibility.permits(FieldUse.CLIENT_FACING_MEASURED_CLAIM)
    assert p.eligibility.permits(FieldUse.SIMULATION)
    assert p.eligibility.permits(FieldUse.ANALYSIS)


def test_never_measured_fact_blocks_even_when_provenance_looks_measured() -> None:
    p = _policy(recommended_use="prior, never measured fact")
    assert p.provenance_class is ProvenanceClass.OBSERVED
    assert not p.eligibility.client_facing_measured_claim


def test_modelled_and_unclassified_provenance_cannot_back_measured_claims() -> None:
    assert not _policy(evidence_status="MODELED_METADATA").eligibility.client_facing_measured_claim
    unclassified = _policy(evidence_status="NEW_WEIGHT", recommended_use="weights")
    assert not unclassified.eligibility.client_facing_measured_claim


def test_audit_only_field_is_eligible_for_nothing_but_weighting_by_name() -> None:
    p = _policy(field="vaha_x", evidence_status="NEW_WEIGHT", recommended_use="AUDIT_ONLY")
    assert p.eligibility.as_dict() == {
        "analysis": False,
        "client_facing_measured_claim": False,
        "filtering": False,
        "simulation": False,
        "persona_construction": False,
        "weighting": True,
    }


def test_audit_only_modelled_field_stays_a_simulation_input() -> None:
    # The reference's simulation flag is "modelled-ish OR not audit-only"; ported as is.
    p = _policy(evidence_status="MODELED_METADATA", recommended_use="AUDIT_ONLY")
    assert p.eligibility.simulation and not p.eligibility.analysis


def test_persona_construction_needs_the_dictionary_flag() -> None:
    assert not _policy(persona_eligible=False).eligibility.persona_construction


@pytest.mark.parametrize(
    ("override", "match"),
    [
        ({"evidence_status": "MADE_UP_STATUS"}, "unknown evidence_status"),
        ({"production_grade": "A+"}, "unknown production_grade"),
        ({"field": "   "}, "no field name"),
    ],
)
def test_unknown_vocabulary_is_refused_not_classified(override: dict[str, Any], match: str) -> None:
    with pytest.raises(FieldPolicyError, match=match):
        _policy(**override)


def test_grade_with_slash_parses() -> None:
    assert _policy(production_grade="C_RAW/B_WEIGHTED").production_grade is (
        ProductionGrade.C_RAW_B_WEIGHTED
    )


# --- the book --------------------------------------------------------------------


def test_book_lookup_of_declared_field(field_book: Any) -> None:
    assert field_book.get("vek").evidence_status is EvidenceStatus.POPULATION_ANCHOR
    assert "vek" in field_book
    assert len(field_book) == 16


def test_undeclared_field_raises_instead_of_defaulting(field_book: Any) -> None:
    with pytest.raises(UndeclaredField) as caught:
        field_book.get("no_such_field")
    assert not caught.value.known_runtime_column


def test_runtime_column_without_dictionary_entry_is_still_undeclared(field_book: Any) -> None:
    with pytest.raises(UndeclaredField) as caught:
        field_book.get("_analysis_weight")
    assert caught.value.known_runtime_column
    assert "runtime column" in str(caught.value)


def test_duplicate_row_is_refused(dictionary_rows: list[dict[str, str]]) -> None:
    with pytest.raises(FieldPolicyError, match="declared twice"):
        FieldPolicyBook.from_dictionary_rows(
            [*dictionary_rows, dictionary_rows[0]], source_sha256=SHA, weight_columns=()
        )


def test_book_must_name_its_dictionary_hash(dictionary_rows: list[dict[str, str]]) -> None:
    with pytest.raises(FieldPolicyError, match="SHA-256"):
        FieldPolicyBook.from_dictionary_rows(dictionary_rows, source_sha256="", weight_columns=())


def test_empty_book_is_refused() -> None:
    with pytest.raises(FieldPolicyError, match="no fields"):
        FieldPolicyBook.from_dictionary_rows([], source_sha256=SHA, weight_columns=())


# --- one authority: the population contract (MVP-29, OI-24 (a)) ---------------------

#: Synthetic fields the reference's derivation lets back a measured client claim and the
#: population contract refuses: matched politics read as historical, a matched block's
#: "persona/context with provenance", calibrated values and derived ones.
TIGHTENED = {
    "vote_2021",
    "religious_affiliation",
    "has_savings",
    "tv_daily_minutes",
    "life_stage",
    "is_procurement_buyer_current",
}


def _contract(dictionary_rows: list[dict[str, str]]) -> Any:
    return build_field_policy(
        dictionary_rows, dictionary_sha256=SHA, weight_columns=["vaha_strukturalni_2025"]
    )


def test_a_population_book_is_eligible_for_exactly_what_its_contract_permits(
    field_book: Any, dictionary_rows: list[dict[str, str]]
) -> None:
    contract = _contract(dictionary_rows)
    uses = {
        FieldUse.ANALYSIS: ContractUse.AGGREGATE_ANALYSIS,
        FieldUse.CLIENT_FACING_MEASURED_CLAIM: ContractUse.CLIENT_MEASURED_CLAIM,
        FieldUse.FILTERING: ContractUse.AUDIENCE_FILTERING,
        FieldUse.SIMULATION: ContractUse.SIMULATION,
        FieldUse.PERSONA_CONSTRUCTION: ContractUse.PERSONA_CONSTRUCTION,
        FieldUse.WEIGHTING: ContractUse.WEIGHTING,
    }
    for name, policy in field_book.fields.items():
        for use, contract_use in uses.items():
            assert policy.eligibility.permits(use) is contract.decide(name, contract_use).allowed, (
                name,
                use,
            )


def test_the_reference_reading_stays_wider_than_the_book(field_book: Any) -> None:
    """The reference's derivation is kept, exact, for parity; the book does not follow it."""
    widened = {
        name
        for name, policy in field_book.fields.items()
        if _reference(policy).client_facing_measured_claim
        and not policy.eligibility.client_facing_measured_claim
    }
    assert widened == TIGHTENED


@pytest.mark.parametrize("name", sorted(TIGHTENED))
def test_a_measured_claim_the_contract_refuses_is_refused(
    field_book: Any, joint_status: Any, name: str
) -> None:
    request = ClaimRequest(
        fields=(name,),
        basis=ClaimBasis.MEASURED,
        surface=ClaimSurface.CLIENT_FACING,
        level=ClaimLevel.AGGREGATE,
        disclosures=frozenset(Disclosure),
    )
    decision = evaluate_claim(request, field_book, joint_status)
    assert ViolationCode.NOT_MEASURED_EVIDENCE in decision.codes


def test_a_derived_field_answers_as_modelled_not_measured(field_book: Any) -> None:
    contract = resolve_factual_contract(
        QuestionFactMetadata(fact_source_field="life_stage"), field_book
    )
    assert contract.basis is ClaimBasis.MODELED


def test_a_runtime_field_the_contract_has_not_classified_stays_undeclared(
    dictionary_rows: list[dict[str, str]],
) -> None:
    contract = build_field_policy(
        dictionary_rows,
        dictionary_sha256=SHA,
        weight_columns=["_analysis_weight"],
        derived_fields=[("_analysis_weight", True)],
    )
    book = FieldPolicyBook.from_population_policy(contract)
    assert book.source_sha256 == SHA
    with pytest.raises(UndeclaredField) as caught:
        book.get("_analysis_weight")
    assert caught.value.known_runtime_column


def test_a_contract_with_an_unmapped_field_refuses_the_book(
    dictionary_rows: list[dict[str, str]],
) -> None:
    rows = [*dictionary_rows, dict(dictionary_rows[0], field="new_f", recommended_use="reworded")]
    contract = build_field_policy(rows, dictionary_sha256=SHA, weight_columns=())
    with pytest.raises(FieldPolicyError, match="new_f"):
        FieldPolicyBook.from_population_policy(contract)


# --- policy documents ----------------------------------------------------------------


def _reference(p: Any) -> Any:
    """A field's eligibility as the reference's export states it: its own derivation."""
    return derive_eligibility(
        p.field, p.provenance_class, p.claim_rules, p.recommended_use_verbatim, p.persona_eligible
    )


def _document(book: Any) -> dict[str, Any]:
    return {
        "source_sha256": book.source_sha256,
        "declared_field_count": len(book),
        "runtime_columns_without_dictionary_entry": [{"field": "_analysis_weight"}],
        "fields": [
            {
                "field": p.field,
                "block": p.block,
                "source": p.source,
                "evidence_status": p.evidence_status.value,
                "provenance_class": p.provenance_class.value,
                "production_grade": p.production_grade.value,
                "recommended_use_verbatim": p.recommended_use_verbatim,
                "description": p.description,
                "persona_eligible": p.persona_eligible,
                "claim_rules": [r.value for r in p.claim_rules],
                "eligibility": _reference(p).as_dict(),
            }
            for p in book.fields.values()
        ],
    }


def test_document_round_trips(field_book: Any) -> None:
    loaded = FieldPolicyBook.from_policy_document(_document(field_book))
    # The same fields, read with the reference's eligibility: the parity reading.
    assert loaded.fields == {
        name: replace(p, eligibility=_reference(p)) for name, p in field_book.fields.items()
    }
    assert loaded.undeclared_runtime_columns == frozenset({"_analysis_weight"})


def test_hand_widened_eligibility_is_refused(field_book: Any) -> None:
    doc = _document(field_book)
    tampered = copy.deepcopy(doc)
    for entry in tampered["fields"]:
        if entry["field"] == "deal_seeking_1_10":
            entry["eligibility"]["client_facing_measured_claim"] = True
    with pytest.raises(FieldPolicyInconsistent) as caught:
        FieldPolicyBook.from_policy_document(tampered)
    assert caught.value.mismatches == {"deal_seeking_1_10": ("eligibility",)}


def test_dropped_claim_rule_is_refused(field_book: Any) -> None:
    doc = _document(field_book)
    for entry in doc["fields"]:
        if entry["field"] == "value_security":
            entry["claim_rules"] = []
    with pytest.raises(FieldPolicyInconsistent, match="value_security"):
        FieldPolicyBook.from_policy_document(doc)


def test_miscount_is_refused(field_book: Any) -> None:
    doc = _document(field_book)
    doc["declared_field_count"] = 400
    with pytest.raises(FieldPolicyError, match="declared_field_count"):
        FieldPolicyBook.from_policy_document(doc)


@pytest.mark.parametrize("missing", ["source_sha256", "fields", "declared_field_count"])
def test_document_missing_a_key_is_refused(field_book: Any, missing: str) -> None:
    doc = _document(field_book)
    del doc[missing]
    with pytest.raises(FieldPolicyError, match="not a field policy document"):
        FieldPolicyBook.from_policy_document(doc)


def test_document_persona_flag_must_be_boolean(field_book: Any) -> None:
    doc = _document(field_book)
    doc["fields"][0]["persona_eligible"] = "yes"
    with pytest.raises(FieldPolicyError, match="persona_eligible"):
        FieldPolicyBook.from_policy_document(doc)
