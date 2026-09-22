"""Gate-decision parity against the reference contracts.

Two sources of truth, and each section says which it uses:

* **The reference repository** (``AiAnalytics-AIA/AIA-reference``, private,
  via ``AIA_REFERENCE_REPO``) holds the machine-readable exports -- the 400-field
  policy and the methodology ledger. Tests that read it skip cleanly when it is
  absent and are marked ``parity``.
* **The recovered decision tables** below are the reference's documented gate
  decisions (methodology-ledger M03/M10/M16/M17, high-risk R5/R6/R12), written as
  cases. They run everywhere. ``EXACT`` cases must produce the same allow/block
  decision *and* the same refusal code; ``SEMANTIC`` cases must produce the same
  allow/block decision, with the code free to be more specific.

What neither source can supply is the legacy *source* -- it is withheld with the
archive. The decisions of ``tier_gate.py``, ``validation_gate.py`` and
``core_joint._fallback()`` that the docstrings do not state are recorded in
``.planning/open-items.md`` for the run that has the archive.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.evidence import (
    REFERENCE_THRESHOLDS,
    ClaimBasis,
    ClaimLevel,
    ClaimRequest,
    ClaimRule,
    ClaimSurface,
    Disclosure,
    EvidenceTable,
    FieldPolicyBook,
    FieldUse,
    GateDecision,
    JointDegradation,
    NumericClaim,
    ProductionGrade,
    SupportAssessment,
    SupportEvidence,
    SupportStatus,
    ValidationState,
    ValidationStatus,
    ViolationCode,
    admit_numeric_claims,
    allowed_metric_spellings,
    assess_support,
    block,
    evaluate_claim,
    evaluate_predictive_validity_claim,
    evaluate_tier,
    load_joint_status,
    system_fingerprint,
)

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def ledger(reference_repo: Path) -> dict[str, dict[str, Any]]:
    """The reference methodology ledger, by entry id (M01..M17)."""
    raw = json.loads((reference_repo / "methodology-ledger.json").read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in raw["entries"]}


# --- 1. Field policy: EXACT for all 400 fields ---------------------------------------


@pytest.fixture(scope="module")
def reference_policy_document(reference_repo: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (reference_repo / "field-policy.json").read_text(encoding="utf-8")
    )
    return document


@pytest.fixture(scope="module")
def reference_book(reference_policy_document: dict[str, Any]) -> FieldPolicyBook:
    return FieldPolicyBook.from_policy_document(reference_policy_document)


@pytest.mark.parity
def test_every_reference_field_rederives_identically(
    reference_policy_document: dict[str, Any], reference_book: FieldPolicyBook
) -> None:
    """Loading re-derives every field and refuses on any difference, so loading IS the check."""
    assert len(reference_book) == reference_policy_document["declared_field_count"] == 400
    assert reference_book.source_sha256 == reference_policy_document["source_sha256"]


@pytest.mark.parity
def test_reference_counts_match(
    reference_policy_document: dict[str, Any], reference_book: FieldPolicyBook
) -> None:
    counts = reference_policy_document["counts"]
    fields = list(reference_book.fields.values())
    assert dict(Counter(p.provenance_class.value for p in fields)) == counts["by_provenance_class"]
    assert dict(Counter(p.production_grade.value for p in fields)) == counts["by_production_grade"]
    assert dict(Counter(r.value for p in fields for r in p.claim_rules)) == counts["by_claim_rule"]
    assert sum(p.persona_eligible for p in fields) == counts["persona_eligible"]
    assert (
        sum(p.eligibility.client_facing_measured_claim for p in fields)
        == counts["client_facing_measured_claim_allowed"]
    )


@pytest.mark.parity
def test_methodology_ledger_m02_headline_numbers(reference_book: FieldPolicyBook) -> None:
    """M02: 51 never-measured-fact, 21 never-direct-Schwartz, 10 of 400 grade A."""
    fields = list(reference_book.fields.values())
    never_fact = [p for p in fields if p.has(ClaimRule.NEVER_MEASURED_FACT)]
    assert len(never_fact) == 51
    assert sum(p.has(ClaimRule.NEVER_DIRECT_SCHWARTZ) for p in fields) == 21
    assert sum(p.production_grade is ProductionGrade.A for p in fields) == 10
    assert not any(p.eligibility.permits(FieldUse.CLIENT_FACING_MEASURED_CLAIM) for p in never_fact)


@pytest.mark.parity
def test_runtime_columns_without_an_entry_stay_undeclared(
    reference_policy_document: dict[str, Any], reference_book: FieldPolicyBook
) -> None:
    extra = {
        e["field"] for e in reference_policy_document["runtime_columns_without_dictionary_entry"]
    }
    assert len(extra) == 8
    assert reference_book.undeclared_runtime_columns == frozenset(extra)
    assert not extra & reference_book.fields.keys()


# --- 2. CORE_JOINT_STATUS: EXACT on the restrictions and the hash binding (M03) ------


@pytest.mark.parity
def test_certificate_restrictions_are_the_ledgers(
    ledger: dict[str, dict[str, Any]], certificate_bytes: Any
) -> None:
    """A certificate carrying M03's restrictions loads to exactly those restrictions."""
    m03 = ledger["M03"]
    restrictions = m03["claim_restrictions"]
    sha = m03["constants"]["panel_sha256"].split()[0]
    certificate = certificate_bytes(
        production_panel=m03["constants"]["production_panel"],
        panel_sha256=sha,
        matched_blocks=m03["matched_blocks"],
        **restrictions,
    )
    status = load_joint_status(certificate, measured_panel_sha256=sha)
    assert status.certified
    for key, expected in restrictions.items():
        assert getattr(status, key) == expected, key
    assert sorted(status.matched_blocks) == sorted(m03["matched_blocks"])

    moved = load_joint_status(certificate, measured_panel_sha256=hashlib.sha256(b"x").hexdigest())
    assert moved.degradation is JointDegradation.PANEL_HASH_MISMATCH


@pytest.mark.parity
def test_the_real_certificate_is_honoured_against_the_real_panel(legacy_root: Path) -> None:
    """With the archive: the shipped certificate parses and binds to the shipped panel.

    If this fails on a key name, the certificate's real shape differs from the
    one documented in population-subsystem.md -- a finding, not a flake.
    """
    manifest = json.loads((REPO / "docs/migration/reference-manifest.json").read_text())
    raw = (legacy_root / "CORE_JOINT_STATUS.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["files"]["CORE_JOINT_STATUS.json"]
    declared = json.loads(raw)
    panel = next(legacy_root.rglob(str(declared["production_panel"])))
    status = load_joint_status(
        raw, measured_panel_sha256=hashlib.sha256(panel.read_bytes()).hexdigest()
    )
    assert status.certified, status.detail
    assert not status.cross_block_same_person_joint
    assert not status.client_joint_outputs_allowed
    assert not status.cross_block_joint_claims_allowed


# --- 3. Support and metrics: EXACT on the constants the gates decide with (M16, M17) --


@pytest.mark.parity
def test_suppression_constants_are_the_ledgers(ledger: dict[str, dict[str, Any]]) -> None:
    constants = ledger["M16"]["constants"]
    assert REFERENCE_THRESHOLDS.min_cell == constants["min_cell"]
    assert REFERENCE_THRESHOLDS.n_guard == constants["n_guard_threshold"]
    assert REFERENCE_THRESHOLDS.indicative == constants["indicative_threshold"]
    assert SupportAssessment().status.value == constants["support_status default"]


@pytest.mark.parity
def test_allowed_metric_set_is_the_ledgers(ledger: dict[str, dict[str, Any]]) -> None:
    stated = ledger["M17"]["constants"]["allowed metrics"]
    assert " | ".join(allowed_metric_spellings()) == stated


# --- 4. Recovered decision tables: run everywhere ----------------------------------------
#
# Each case is one documented reference decision. `parity` says how it compares:
#   EXACT                   same allow/block and exactly these refusal codes
#   SEMANTIC                same allow/block; the code may be more specific
#   INTENTIONAL_DIFFERENCE  production blocks where the reference passed or degraded
#                           silently; the case proves the new behaviour


@dataclass(frozen=True)
class GateCase:
    case_id: str
    source: str
    parity: str
    run: Callable[[Any], GateDecision]
    allowed: bool
    codes: frozenset[ViolationCode] = frozenset()


def _claim(*fields: str, **kw: Any) -> ClaimRequest:
    args: dict[str, Any] = {
        "basis": ClaimBasis.MEASURED,
        "surface": ClaimSurface.CLIENT_FACING,
        "level": ClaimLevel.AGGREGATE,
        "disclosures": frozenset(Disclosure),
    }
    args.update(kw)
    return ClaimRequest(fields=fields, **args)


def _decide(request: ClaimRequest) -> Callable[[Any], GateDecision]:
    return lambda w: evaluate_claim(request, w.book, w.joint)


def _admit(claim: NumericClaim, **row: Any) -> Callable[[Any], GateDecision]:
    def run(w: Any) -> GateDecision:
        table = EvidenceTable.build([w.row(**row)])
        return admit_numeric_claims(
            [claim], table, book=w.book, joint_status=w.joint, surface=ClaimSurface.CLIENT_FACING
        ).decision

    return run


def _support(n: int | None, eff: float | None) -> Callable[[Any], GateDecision]:
    def run(_: Any) -> GateDecision:
        status = assess_support(SupportEvidence(n=n, effective_n=eff)).status
        if status is SupportStatus.SUPPRESS:
            return block(ViolationCode.SUPPORT_SUPPRESSED, "cell", "suppressed")
        return GateDecision()

    return run


_MISSING = object()


def _certificate(
    measured: str | None, raw: object = None, **overrides: Any
) -> Callable[[Any], GateDecision]:
    """Load a certificate: the synthetic one with overrides, or ``raw`` bytes, or none."""

    def run(w: Any) -> GateDecision:
        data = None if raw is _MISSING else raw if isinstance(raw, bytes) else w.cert(**overrides)
        status = load_joint_status(data, measured_panel_sha256=measured)
        if status.certified:
            return GateDecision()
        return block(
            ViolationCode.JOINT_CERTIFICATE_DEGRADED, "certificate", str(status.degradation)
        )

    return run


_FP = system_fingerprint(
    {
        "panel_sha256": "1" * 64,
        "field_dictionary_sha256": "2" * 64,
        "joint_certificate_sha256": "3" * 64,
        "engine_version": "e",
    }
)
_OLD_FP = "f" * 64
_PANEL = "b" * 64  # the synthetic certificate's panel hash (conftest)
_NC = NumericClaim("c1", "E1", "top2box_pct", 42.5, "%")
DEGRADED = frozenset({ViolationCode.JOINT_CERTIFICATE_DEGRADED})

GATE_CASES: tuple[GateCase, ...] = (
    # M02 / R5 -- the field dictionary, enforced
    GateCase(
        "never-measured-fact-measured-claim", "M02, R5", "EXACT",
        _decide(_claim("deal_seeking_1_10")), False,
        frozenset({ViolationCode.NEVER_MEASURED_FACT, ViolationCode.NOT_MEASURED_EVIDENCE}),
    ),
    GateCase(
        "never-measured-fact-as-simulation-prior", "M02", "EXACT",
        _decide(_claim("deal_seeking_1_10", basis=ClaimBasis.MODELED)), True,
    ),
    GateCase(
        "never-direct-schwartz", "M02", "EXACT",
        _decide(_claim("value_security")), False,
        frozenset({ViolationCode.NEVER_DIRECT_SCHWARTZ, ViolationCode.NOT_MEASURED_EVIDENCE}),
    ),
    GateCase(
        "person-value-modeled-individual", "M02", "EXACT",
        _decide(_claim("has_savings", level=ClaimLevel.INDIVIDUAL)), False,
        frozenset({ViolationCode.INDIVIDUAL_CLAIM_ON_AGGREGATE_FIELD}),
    ),
    GateCase(
        "audit-only", "M02", "EXACT",
        _decide(_claim("panel_row_id", basis=ClaimBasis.MODELED)), False,
        frozenset({ViolationCode.FIELD_AUDIT_ONLY}),
    ),
    GateCase(
        "mandated-weight", "M02, R3", "EXACT",
        _decide(_claim("is_procurement_buyer_current", weight_scheme="vaha_kalibrovana")), False,
        frozenset({ViolationCode.WEIGHT_SCHEME_MISMATCH}),
    ),
    GateCase(
        "undeclared-runtime-column", "field-policy.json runtime_columns_without_dictionary_entry",
        "INTENTIONAL_DIFFERENCE",
        _decide(_claim("life_stage_derived")), False,
        frozenset({ViolationCode.FIELD_UNDECLARED}),
    ),
    # M03 / R6 -- the joint certificate
    GateCase(
        "descriptive-core-output", "M03 descriptive_core_outputs_allowed", "EXACT",
        _decide(_claim("vek", "vzdelani", level=ClaimLevel.SEGMENT)), True,
    ),
    GateCase(
        "matched-block-labelled-summary", "M03 matched_block_outputs_allowed", "EXACT",
        _decide(_claim("trust_courts", "vek", level=ClaimLevel.SEGMENT)), True,
    ),
    GateCase(
        "cross-block-same-person", "M03, R6", "EXACT",
        _decide(_claim("trust_courts", "wellbeing_index", level=ClaimLevel.SEGMENT)), False,
        frozenset(
            {
                ViolationCode.CROSS_BLOCK_JOINT_CLAIM,
                ViolationCode.CROSS_BLOCK_NOT_SAME_PERSON,
                ViolationCode.CLIENT_JOINT_OUTPUT,
            }
        ),
    ),
    GateCase(
        "cross-block-modelled-internal", "M03 cross_block_joint_claims_allowed", "EXACT",
        _decide(
            _claim(
                "trust_courts", "wellbeing_index", level=ClaimLevel.SEGMENT,
                basis=ClaimBasis.MODELED, surface=ClaimSurface.INTERNAL,
            )
        ),
        False, frozenset({ViolationCode.CROSS_BLOCK_JOINT_CLAIM}),
    ),
    GateCase("certificate-missing", "M03", "EXACT", _certificate(_PANEL, _MISSING), False,
             DEGRADED),
    GateCase("certificate-unparseable", "M03", "EXACT", _certificate(_PANEL, b"{"), False,
             DEGRADED),
    GateCase("certificate-unknown-status", "M03", "EXACT",
             _certificate(_PANEL, structure_status="X"), False, DEGRADED),
    GateCase("certificate-hash-moved", "M03", "EXACT", _certificate("c" * 64), False, DEGRADED),
    GateCase("certificate-bound", "M03", "EXACT", _certificate(_PANEL), True),
    GateCase("certificate-hash-unmeasured", "M03", "INTENTIONAL_DIFFERENCE", _certificate(None),
             False, DEGRADED),
    # M16 -- effective-n suppression
    GateCase("support-default", "M16 support_status default", "EXACT", _support(None, None), False,
             frozenset({ViolationCode.SUPPORT_SUPPRESSED})),
    GateCase("support-below-n-guard", "M16 n_guard_threshold", "EXACT", _support(500, 24.9), False,
             frozenset({ViolationCode.SUPPORT_SUPPRESSED})),
    GateCase("support-below-min-cell", "M16 min_cell", "EXACT", _support(49, 49.0), False,
             frozenset({ViolationCode.SUPPORT_SUPPRESSED})),
    GateCase("support-indicative", "M16 indicative_threshold", "SEMANTIC", _support(500, 30.0),
             True),
    GateCase("support-reportable", "M16", "EXACT", _support(500, 400.0), True),
    GateCase(
        "interval-required", "M16 stated rule 10.13", "EXACT",
        _admit(_NC, interval=None), False, frozenset({ViolationCode.INTERVAL_MISSING}),
    ),
    # M17 -- analysis evidence discipline
    GateCase("evidence-copied-exactly", "M17", "EXACT", _admit(_NC), True),
    GateCase(
        "evidence-rejects-forgery",
        "M17; reference test_release_core::test_evidence_rejects_forgery", "SEMANTIC",
        _admit(NumericClaim("c1", "FORGED", "top2box_pct", 42.5, "%")), False,
        frozenset({ViolationCode.EVIDENCE_REF_UNKNOWN}),
    ),
    GateCase(
        "numeric-gate", "M17; reference test_release_core::test_numeric_gate", "SEMANTIC",
        _admit(NumericClaim("c1", "E1", "top2box_pct", 45.0, "%")), False,
        frozenset({ViolationCode.VALUE_MISMATCH}),
    ),
    GateCase(
        "metric-outside-allowed-set", "M17 allowed metrics", "EXACT",
        _admit(NumericClaim("c1", "E1", "t_score", 42.5, "%")), False,
        frozenset({ViolationCode.METRIC_NOT_ALLOWED}),
    ),
    # M10 / R12 -- validation and tiers
    GateCase(
        "smoke-never-unlocks", "M10 smoke_validation.py", "EXACT",
        lambda _: evaluate_predictive_validity_claim(
            ValidationState(ValidationStatus.SMOKE_VALIDATED, _FP), _FP
        ),
        False, frozenset({ViolationCode.PREDICTIVE_VALIDITY_UNPROVEN}),
    ),
    GateCase(
        "holdout-pending", "M10 EXTERNAL_HOLDOUT_PENDING", "EXACT",
        lambda _: evaluate_predictive_validity_claim(None, _FP), False,
        frozenset({ViolationCode.PREDICTIVE_VALIDITY_UNPROVEN}),
    ),
    GateCase(
        "validation-outlived-its-system", "R12", "EXACT",
        lambda _: evaluate_predictive_validity_claim(
            ValidationState(ValidationStatus.HOLDOUT_VALIDATED, _OLD_FP), _FP
        ),
        False, frozenset({ViolationCode.VALIDATION_NOT_CURRENT}),
    ),
    GateCase(
        "tier-b-aggregate", "M10 tier_gate.py Tier B", "EXACT",
        lambda _: evaluate_tier({"d": "B"}, "aggregate"), True,
    ),
    GateCase(
        "tier-b-persona", "M10 tier_gate.py Tier A currently none", "SEMANTIC",
        lambda _: evaluate_tier({"d": "B"}, "persona"), False,
        frozenset({ViolationCode.TIER_INSUFFICIENT}),
    ),
)  # fmt: skip


@dataclass(frozen=True)
class _World:
    book: Any
    joint: Any
    row: Any
    cert: Any


@pytest.mark.parametrize("case", GATE_CASES, ids=[c.case_id for c in GATE_CASES])
def test_recovered_gate_decision(
    case: GateCase, field_book: Any, joint_status: Any, evidence_row: Any, certificate_bytes: Any
) -> None:
    decision = case.run(_World(field_book, joint_status, evidence_row, certificate_bytes))
    assert decision.allowed is case.allowed, f"{case.source}: {decision.violations}"
    if case.parity in {"EXACT", "INTENTIONAL_DIFFERENCE"}:
        assert decision.codes == case.codes, case.source
    else:
        assert case.codes <= decision.codes or not case.codes, case.source


def test_every_case_names_its_source_and_parity() -> None:
    assert len({c.case_id for c in GATE_CASES}) == len(GATE_CASES)
    for case in GATE_CASES:
        assert case.source and case.parity in {"EXACT", "SEMANTIC", "INTENTIONAL_DIFFERENCE"}
        assert case.allowed == (not case.codes), case.case_id


def test_degraded_certificate_blocks_every_client_claim(
    field_book: Any, degraded_joint_status: Any
) -> None:
    """M03: whatever the field, a claim made on an uncertified panel does not reach a client."""
    for policy in field_book.fields.values():
        decision = evaluate_claim(
            _claim(policy.field, basis=ClaimBasis.MODELED), field_book, degraded_joint_status
        )
        assert not decision.allowed, policy.field


# --- 5. The claim gate over the real dictionary: never wider than the reference ----------


@pytest.mark.parity
def test_claim_gate_never_permits_what_the_reference_policy_forbids(
    reference_book: FieldPolicyBook, ledger: dict[str, dict[str, Any]], certificate_bytes: Any
) -> None:
    """Over all 400 real fields, with every disclosure and the mandated weight supplied.

    A measured client claim on one field is allowed only where the reference
    marks it client-eligible (no widening), and the only eligible fields refused
    are those in a donor-matched block the certificate does not name (the one
    deliberate narrowing, pinned here so a change to it is a visible diff).
    """
    m03 = ledger["M03"]
    sha = m03["constants"]["panel_sha256"].split()[0]
    status = load_joint_status(
        certificate_bytes(panel_sha256=sha, matched_blocks=m03["matched_blocks"]),
        measured_panel_sha256=sha,
    )
    narrowed: set[str] = set()
    for policy in reference_book.fields.values():
        decision = evaluate_claim(
            _claim(policy.field, weight_scheme=policy.mandated_weight_scheme),
            reference_book,
            status,
        )
        eligible = policy.eligibility.client_facing_measured_claim
        assert not (decision.allowed and not eligible), policy.field
        if eligible and not decision.allowed:
            assert decision.codes == {ViolationCode.MATCHED_BLOCK_NOT_CERTIFIED}, policy.field
            narrowed.add(policy.block)
    assert narrowed == {"RELIGION"}
