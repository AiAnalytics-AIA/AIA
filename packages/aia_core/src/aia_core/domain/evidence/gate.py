"""The one decision shape every evidence gate returns.

A gate answers *may this be claimed?* and the answer is a :class:`GateDecision`.
Two properties make it fail closed rather than merely strict:

* **ALLOW is the absence of violations, not a flag.** A decision is allowed only
  when it carries no violation at all; there is no way to build an allowed
  decision that also lists a problem, and no ``force`` or ``override`` field.
* **Blocking is the default of every constructor.** :func:`block` needs a
  reason; :func:`allow` takes nothing. Combining decisions with :func:`combine`
  keeps every violation, so a later gate cannot launder an earlier refusal.

Violations carry a stable :class:`ViolationCode` so a repair prompt, an audit
log and a test can all name the same failure without matching prose.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "GateBlocked",
    "GateDecision",
    "Violation",
    "ViolationCode",
    "allow",
    "block",
    "combine",
]


class ViolationCode(StrEnum):
    """Every reason a gate can refuse. One definition, matched everywhere (A6)."""

    # Field policy
    FIELD_UNDECLARED = "FIELD_UNDECLARED"
    FIELD_AUDIT_ONLY = "FIELD_AUDIT_ONLY"
    FIELD_NOT_ANALYSABLE = "FIELD_NOT_ANALYSABLE"
    NOT_MEASURED_EVIDENCE = "NOT_MEASURED_EVIDENCE"
    NEVER_MEASURED_FACT = "NEVER_MEASURED_FACT"
    NEVER_DIRECT_SCHWARTZ = "NEVER_DIRECT_SCHWARTZ"
    INDIVIDUAL_CLAIM_ON_AGGREGATE_FIELD = "INDIVIDUAL_CLAIM_ON_AGGREGATE_FIELD"
    SCOPE_DISCLOSURE_MISSING = "SCOPE_DISCLOSURE_MISSING"
    MODELED_DISCLOSURE_MISSING = "MODELED_DISCLOSURE_MISSING"
    HISTORICAL_DISCLOSURE_MISSING = "HISTORICAL_DISCLOSURE_MISSING"
    WEIGHT_SCHEME_MISMATCH = "WEIGHT_SCHEME_MISMATCH"

    # Joint structure (CORE_JOINT_STATUS)
    JOINT_CERTIFICATE_DEGRADED = "JOINT_CERTIFICATE_DEGRADED"
    CORE_OUTPUTS_NOT_CERTIFIED = "CORE_OUTPUTS_NOT_CERTIFIED"
    MATCHED_BLOCK_NOT_CERTIFIED = "MATCHED_BLOCK_NOT_CERTIFIED"
    CROSS_BLOCK_JOINT_CLAIM = "CROSS_BLOCK_JOINT_CLAIM"
    CROSS_BLOCK_NOT_SAME_PERSON = "CROSS_BLOCK_NOT_SAME_PERSON"
    CLIENT_JOINT_OUTPUT = "CLIENT_JOINT_OUTPUT"

    # Support and suppression
    SUPPORT_SUPPRESSED = "SUPPORT_SUPPRESSED"
    INTERVAL_MISSING = "INTERVAL_MISSING"

    # Validation and tiers
    VALIDATION_NOT_CURRENT = "VALIDATION_NOT_CURRENT"
    PREDICTIVE_VALIDITY_UNPROVEN = "PREDICTIVE_VALIDITY_UNPROVEN"
    TIER_UNKNOWN = "TIER_UNKNOWN"
    TIER_INSUFFICIENT = "TIER_INSUFFICIENT"

    # Analysis evidence discipline
    SCHEMA_INVALID = "SCHEMA_INVALID"
    EVIDENCE_REF_UNKNOWN = "EVIDENCE_REF_UNKNOWN"
    EVIDENCE_SUPPRESSED = "EVIDENCE_SUPPRESSED"
    METRIC_NOT_ALLOWED = "METRIC_NOT_ALLOWED"
    METRIC_MISMATCH = "METRIC_MISMATCH"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    UNCITED_NUMBER = "UNCITED_NUMBER"
    DANGLING_CLAIM_REF = "DANGLING_CLAIM_REF"
    DUPLICATE_CLAIM_ID = "DUPLICATE_CLAIM_ID"
    MODULE_MISMATCH = "MODULE_MISMATCH"


@dataclass(frozen=True, slots=True)
class Violation:
    """One reason a gate refused, attributed to the thing it refused."""

    code: ViolationCode
    subject: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.subject} -- {self.detail}"


@dataclass(frozen=True, slots=True)
class GateDecision:
    """A gate outcome. Allowed exactly when it carries no violation."""

    violations: tuple[Violation, ...] = ()

    @property
    def allowed(self) -> bool:
        return not self.violations

    @property
    def codes(self) -> frozenset[ViolationCode]:
        return frozenset(v.code for v in self.violations)

    def require(self) -> None:
        """Raise :class:`GateBlocked` unless allowed. For callers that must not continue."""
        if self.violations:
            raise GateBlocked(self)


class GateBlocked(Exception):
    """Raised by :meth:`GateDecision.require` when a gate refused."""

    def __init__(self, decision: GateDecision) -> None:
        self.decision = decision
        super().__init__("; ".join(str(v) for v in decision.violations))


def allow() -> GateDecision:
    return GateDecision()


def block(code: ViolationCode, subject: str, detail: str) -> GateDecision:
    return GateDecision((Violation(code, subject, detail),))


def combine(decisions: Iterable[GateDecision]) -> GateDecision:
    """Merge decisions, keeping every violation once and in first-seen order."""
    seen: dict[Violation, None] = {}
    for decision in decisions:
        for violation in decision.violations:
            seen.setdefault(violation, None)
    return GateDecision(tuple(seen))
