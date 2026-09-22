"""Field policy as code: every use decision, every category, every refusal.

Pure-domain tests over synthetic dictionary rows. The categories are the real
ones -- each row uses a verbatim ``recommended_use`` phrase and a real
``evidence_status`` code -- so these tests pin the production reading of each.
Parity with the reference's own extraction is in
``test_population_reference_parity.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.population import (
    EVIDENCE_STATUS_CLASS,
    FIELD_POLICY_VERSION,
    RECOMMENDED_USE_POLICY,
    ClaimRule,
    FieldPolicy,
    FieldUse,
    FieldUseRefused,
    Obligation,
    ParsedDictionary,
    ParsedPanel,
    ProvenanceClass,
    build_field_policy,
    content_sha256,
    field_names_fingerprint,
    validate_import,
)

NEVER_FACT = "behavioral prior / simulation modifier, never measured fact"
SCHWARTZ = "simulation prior; never claim direct Schwartz measurement"
AGG_DISCLOSE = "aggregate planning and persona background with modeled-value disclosure"
SCOPE = "PERSONA_OR_ANALYSIS_WITH_SCOPE"

U = FieldUse


def row(
    name: str,
    use: str = SCOPE,
    status: str = "POPULATION_ANCHOR",
    grade: str = "A",
    persona: str = "yes",
    block: str = "core",
) -> dict[str, str | None]:
    return {
        "field": name,
        "block": block,
        "source": "synthetic",
        "evidence_status": status,
        "production_grade": grade,
        "recommended_use": use,
        "description": None,
        "persona_eligible": persona,
    }


def policy_of(*rows: dict[str, str | None], weights: tuple[str, ...] = ()) -> FieldPolicy:
    return build_field_policy(
        rows,
        dictionary_sha256=content_sha256(b"dictionary"),
        weight_columns=weights,
        derived_fields=(("life_stage_derived", False), ("_analysis_weight", True)),
    )


def allowed(policy: FieldPolicy, name: str) -> set[FieldUse]:
    return {u for u in FieldUse if policy.decide(name, u).allowed}


# --------------------------------------------------------------------------- #
# The tables
# --------------------------------------------------------------------------- #


def test_the_tables_cover_the_v17_dictionary_vocabulary() -> None:
    assert len(RECOMMENDED_USE_POLICY) == 16
    assert len(EVIDENCE_STATUS_CLASS) == 22
    assert FIELD_POLICY_VERSION == "field-policy/v1"


def test_only_observed_and_donor_matched_evidence_is_measured() -> None:
    measured = {c for c in ProvenanceClass if c.is_measured}
    assert measured == {ProvenanceClass.OBSERVED, ProvenanceClass.DONOR_MATCHED}


# --------------------------------------------------------------------------- #
# Representative categories
# --------------------------------------------------------------------------- #


def test_never_measured_fact_is_simulation_and_analysis_only() -> None:
    p = policy_of(row("prior", NEVER_FACT, "MODELED_MARKETING_PRIOR", "B"))
    assert allowed(p, "prior") == {
        U.AUDIENCE_FILTERING,
        U.AGGREGATE_ANALYSIS,
        U.SIMULATION,
        U.PERSONA_CONSTRUCTION,
    }
    assert p.decide("prior", U.CLIENT_MEASURED_CLAIM).reason == "phrase_permits_no_client_claim"
    assert Obligation.DISCLOSE_MODELLED in p.decide("prior", U.PERSONA_CONSTRUCTION).obligations


def test_never_direct_schwartz_can_never_reach_a_client() -> None:
    p = policy_of(row("value", SCHWARTZ, "MODELED_VALUE_PROXY", "B"))
    for use in (U.CLIENT_MEASURED_CLAIM, U.CLIENT_MODELLED_CLAIM):
        with pytest.raises(FieldUseRefused):
            p.require("value", use)
    assert p.decide("value", U.SIMULATION).allowed


def test_a_rule_forbidding_measured_claims_wins_over_a_permissive_phrase() -> None:
    # Even if a phrase permitted client claims, the rule is checked first.
    p = policy_of(row("prior", NEVER_FACT, "MODELED_MARKETING_PRIOR", "B"))
    assert not p.decide("prior", U.CLIENT_MEASURED_CLAIM).allowed


def test_scoped_observed_field_may_back_a_measured_claim_with_scope_disclosure() -> None:
    p = policy_of(row("vek"))
    decision = p.decide("vek", U.CLIENT_MEASURED_CLAIM)
    assert decision.allowed
    assert decision.obligations == {Obligation.DISCLOSE_SCOPE}
    modelled = p.decide("vek", U.CLIENT_MODELLED_CLAIM)
    assert modelled.obligations == {Obligation.DISCLOSE_SCOPE, Obligation.DISCLOSE_MODELLED}


def test_donor_matched_evidence_may_back_a_measured_claim() -> None:
    p = policy_of(row("trust", status="MATCHED_WHOLE_BLOCK", grade="B", block="institutions"))
    assert p.decide("trust", U.CLIENT_MEASURED_CLAIM).allowed


@pytest.mark.parametrize(
    "status",
    ["CALIBRATED_MODELED", "DERIVED_TRANSPARENT", "HYBRID_MEASURED_PIAAC_OR_MODELED"],
)
def test_non_measured_evidence_never_backs_a_measured_claim(status: str) -> None:
    p = policy_of(row("f", status=status, grade="B"))
    decision = p.decide("f", U.CLIENT_MEASURED_CLAIM)
    assert not decision.allowed
    assert decision.reason.endswith("_is_not_measured")
    assert p.decide("f", U.CLIENT_MODELLED_CLAIM).allowed


@pytest.mark.parametrize("grade", ["T", "D"])
def test_technical_and_d_grades_never_reach_a_client(grade: str) -> None:
    p = policy_of(row("f", grade=grade))
    for use in (U.CLIENT_MEASURED_CLAIM, U.CLIENT_MODELLED_CLAIM):
        assert p.decide("f", use).reason == f"grade_{grade}_not_client_facing"
    assert p.decide("f", U.AGGREGATE_ANALYSIS).allowed


def test_aggregate_modelled_phrase_permits_only_disclosed_aggregate_modelled_claims() -> None:
    p = policy_of(row("fin", AGG_DISCLOSE, "CALIBRATED_MODELED", "B"))
    assert not p.decide("fin", U.CLIENT_MEASURED_CLAIM).allowed
    decision = p.decide("fin", U.CLIENT_MODELLED_CLAIM)
    assert decision.allowed
    assert decision.obligations == {Obligation.AGGREGATE_ONLY, Obligation.DISCLOSE_MODELLED}


def test_historical_or_exploratory_is_internal_only() -> None:
    p = policy_of(row("isco", "HISTORICAL_OR_EXPLORATORY", "CANONICAL_CORE", "C"))
    assert U.CLIENT_MEASURED_CLAIM not in allowed(p, "isco")
    assert U.CLIENT_MODELLED_CLAIM not in allowed(p, "isco")
    assert p.decide("isco", U.AUDIENCE_FILTERING).allowed


def test_specified_weight_phrase_obliges_its_weight() -> None:
    p = policy_of(
        row("aud", "audience selection; use vaha_strukturalni_2025", "DERIVED_TRANSPARENT")
    )
    assert p.decide("aud", U.AUDIENCE_FILTERING).obligations == {Obligation.USE_SPECIFIED_WEIGHT}
    assert not p.decide("aud", U.CLIENT_MODELLED_CLAIM).allowed


@pytest.mark.parametrize("use", ["AUDIT_ONLY", "technical/provenance only"])
def test_audit_only_is_refused_for_every_use(use: str) -> None:
    p = policy_of(row("pid", use, "PROVENANCE_OR_CORE", "T", "no"))
    assert allowed(p, "pid") == set()
    assert p.decide("pid", U.SIMULATION).reason == "audit_only"


def test_weight_columns_are_weighting_only() -> None:
    p = policy_of(row("w", "AUDIT_ONLY", "NEW_WEIGHT", "T", "no"), weights=("w",))
    assert allowed(p, "w") == {U.WEIGHTING}
    assert not p.decide("vek_absent", U.WEIGHTING).allowed


def test_persona_follows_persona_eligible() -> None:
    p = policy_of(row("f", persona="no"))
    assert p.decide("f", U.PERSONA_CONSTRUCTION).reason == "not_persona_eligible"


# --------------------------------------------------------------------------- #
# Unknown and unmapped fail closed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad",
    [
        {"recommended_use": "never measured fact, mostly"},  # reworded phrase
        {"evidence_status": "MEASURED_SOMETHING_NEW"},  # prefix would say OBSERVED
        {"production_grade": "A+"},
        {"persona_eligible": "maybe"},
        {"recommended_use": None},
    ],
)
def test_an_unmapped_field_is_refused_for_every_use(bad: dict[str, Any]) -> None:
    p = policy_of(row("f") | bad)
    assert allowed(p, "f") == set()
    assert {p.decide("f", u).reason for u in FieldUse} == {"unmapped_policy"}
    assert [e.field for e in p.unmapped] == ["f"]


def test_an_unknown_field_is_refused() -> None:
    p = policy_of(row("vek"))
    assert p.decide("nope", U.AGGREGATE_ANALYSIS).reason == "unknown_field"


def test_unclassified_derived_fields_are_refused_and_the_weight_is_weighting_only() -> None:
    p = policy_of(row("vek"))
    assert allowed(p, "life_stage_derived") == set()
    assert p.decide("life_stage_derived", U.AUDIENCE_FILTERING).reason == (
        "unclassified_derived_field"
    )
    assert allowed(p, "_analysis_weight") == {U.WEIGHTING}


def test_a_derived_field_may_not_shadow_a_dictionary_field() -> None:
    with pytest.raises(ValueError, match="collides"):
        build_field_policy(
            [row("life_stage_derived")],
            dictionary_sha256=content_sha256(b"d"),
            weight_columns=(),
            derived_fields=(("life_stage_derived", False),),
        )


def test_require_returns_obligations_or_raises_with_the_decision() -> None:
    p = policy_of(row("vek"), row("pid", "AUDIT_ONLY", "PROVENANCE_OR_CORE", "T", "no"))
    assert p.require("vek", U.CLIENT_MEASURED_CLAIM) == {Obligation.DISCLOSE_SCOPE}
    with pytest.raises(FieldUseRefused) as caught:
        p.require("pid", U.AGGREGATE_ANALYSIS)
    assert caught.value.decision.reason == "audit_only"
    assert caught.value.reason == "field_use_refused"


def test_permitted_lists_fields_for_a_use() -> None:
    p = policy_of(row("vek"), row("prior", NEVER_FACT, "MODELED_MARKETING_PRIOR", "B"))
    assert p.permitted(U.CLIENT_MEASURED_CLAIM) == ("vek",)
    assert set(p.permitted(U.SIMULATION)) == {"vek", "prior"}
    assert p.permitted(U.SIMULATION, ["prior"]) == ("prior",)


def test_claim_rules_travel_with_the_entry() -> None:
    p = policy_of(row("fin", AGG_DISCLOSE, "CALIBRATED_MODELED", "B"))
    entry = p.entry("fin")
    assert entry is not None
    assert entry.claim_rules == {ClaimRule.AGGREGATE_ONLY, ClaimRule.REQUIRES_MODELED_DISCLOSURE}
    assert entry.provenance_class is ProvenanceClass.CALIBRATED
    assert p.entry("absent") is None


# --------------------------------------------------------------------------- #
# Import refuses a dictionary the policy cannot map
# --------------------------------------------------------------------------- #

FIELDS = ("row_id", "w")
COLUMNS = (
    "field",
    "block",
    "source",
    "evidence_status",
    "production_grade",
    "recommended_use",
    "description",
    "persona_eligible",
)


def validate_with(dictionary: ParsedDictionary) -> set[str]:
    from aia_core.domain.population import KnownVersion, PopulationImportContract, WeightScheme

    contract = PopulationImportContract(
        contract_id="c/v1",
        dataset_id="d",
        field_count=2,
        field_names_sha256=field_names_fingerprint(FIELDS),
        dictionary_sha256=content_sha256(b"d"),
        primary_key="row_id",
        expected_rows=1,
        weight_schemes=(WeightScheme("main", "w"),),
        default_weight_role="main",
        known_versions=(KnownVersion("s", content_sha256(b"s"), 1),),
        static_reference_label="s",
        enrichment_fields=(),
    )
    report = validate_import(
        contract,
        label="x",
        panel_sha256=content_sha256(b"p"),
        panel_byte_size=1,
        dictionary_sha256=content_sha256(b"d"),
        dictionary=dictionary,
        panel=ParsedPanel(header=FIELDS, columns=(("1",), ("1",)), row_count=1),
    )
    return {c.check for c in report.checks if not c.passed}


def test_import_accepts_a_fully_mapped_dictionary() -> None:
    rows = (
        row("row_id", "AUDIT_ONLY", "PROVENANCE_OR_CORE", "T", "no"),
        row("w", "AUDIT_ONLY", "NEW_WEIGHT", "T", "no"),
    )
    assert validate_with(ParsedDictionary(FIELDS, rows=rows, columns=COLUMNS)) == set()


def test_import_rejects_an_unmapped_dictionary_row() -> None:
    rows = (row("row_id", "AUDIT_ONLY", "PROVENANCE_OR_CORE", "T", "no"), row("w", "use freely"))
    assert validate_with(ParsedDictionary(FIELDS, rows=rows, columns=COLUMNS)) == {
        "dictionary.policy_mapped"
    }


def test_import_rejects_a_dictionary_without_policy_columns() -> None:
    assert validate_with(ParsedDictionary(FIELDS, rows=(), columns=("field",))) == {
        "dictionary.policy_mapped"
    }
