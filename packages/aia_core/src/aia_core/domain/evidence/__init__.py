"""Validation & Evidence: what may be claimed, and on what evidence.

Every gate here is deterministic, pure and fail closed. None of them reads a
prompt, and none of them can be satisfied by one: a model proposes, these
functions decide. See ``.planning/plans/evidence-governance-foundation.md`` for
the reference contracts each module ports and where it deliberately differs.
"""

from .field_policy import (
    ClaimRule,
    EvidenceStatus,
    FieldEligibility,
    FieldPolicy,
    FieldPolicyBook,
    FieldPolicyError,
    FieldPolicyInconsistent,
    FieldUse,
    ProductionGrade,
    ProvenanceClass,
    UndeclaredField,
    claim_rules_for,
    derive_eligibility,
    derive_field_policy,
    mandated_weight_scheme,
    provenance_class_for,
)
from .gate import (
    GateBlocked,
    GateDecision,
    Violation,
    ViolationCode,
    allow,
    block,
    combine,
)

__all__ = [
    "ClaimRule",
    "EvidenceStatus",
    "FieldEligibility",
    "FieldPolicy",
    "FieldPolicyBook",
    "FieldPolicyError",
    "FieldPolicyInconsistent",
    "FieldUse",
    "GateBlocked",
    "GateDecision",
    "ProductionGrade",
    "ProvenanceClass",
    "UndeclaredField",
    "Violation",
    "ViolationCode",
    "allow",
    "block",
    "claim_rules_for",
    "combine",
    "derive_eligibility",
    "derive_field_policy",
    "mandated_weight_scheme",
    "provenance_class_for",
]
