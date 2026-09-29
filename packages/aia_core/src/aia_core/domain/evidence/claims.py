"""The permissible-claim policy: may *this* be said, from *these* fields, *this* way?

Every claim the product makes is described as a :class:`ClaimRequest` -- which
fields back it, whether it is stated as a **measurement** or as a **model
estimate**, who will read it, at what level (population, segment, person), and
which disclosures accompany it -- and :func:`evaluate_claim` decides it from
the field policy and the joint-structure certificate. Nothing in the decision
comes from a prompt.

The rules, and where each comes from:

======================================  ===================================================
Rule                                    Source
======================================  ===================================================
undeclared field refuses                "unknown is never good"; runtime columns with no
                                        dictionary entry (field-policy.json)
audit-only field backs nothing          ``AUDIT_ONLY`` claim rule
*never measured fact* backs no          ``NEVER_MEASURED_FACT`` (51 fields), M02/R5
measured claim, on any surface
*never direct Schwartz* backs no        ``NEVER_DIRECT_SCHWARTZ`` (21 fields)
measured claim
a measured claim needs a field          ``eligibility.client_facing_measured_claim``;
eligible for measured claims            "a modelled figure is never presented as a
                                        measurement" (ARCHITECTURE.md §10)
person-level claim on an aggregate      ``PERSON_VALUE_MODELED`` / ``AGGREGATE_ONLY``
field refuses
client-facing disclosures               ``REQUIRES_SCOPE``, ``REQUIRES_MODELED_DISCLOSURE``,
                                        ``HISTORICAL_OR_EXPLORATORY``
mandated weight scheme                  ``SPECIFIED_WEIGHT_REQUIRED``; no weight fallback (R3)
internal-only field backs nothing       ``INTERNAL_ONLY``: AIA's own declaration of a Study
client-facing                           instrument item (``instrument.py``), never prose
joint structure                         ``CORE_JOINT_STATUS`` (M03/R6), see
                                        :func:`.joint_status.evaluate_joint_structure`
======================================  ===================================================

A measured claim needs measured-claim eligibility on the internal surface too.
The reference flag is named for client output, but an internal analysis that
calls a modelled prior a measurement is exactly the error that later reaches a
client; the distinction internal/client decides disclosures, not truth.

A segment breakdown or a person-level profile over more than one field *is* a
joint claim whatever the caller says: the segmenting field and the described
field are related by construction, and a persona that shows two blocks shows
them as one person.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from .field_policy import ClaimRule, FieldPolicy, FieldPolicyBook, UndeclaredField
from .gate import GateDecision, ViolationCode, block, combine
from .joint_status import JointStatus, evaluate_joint_structure

__all__ = [
    "ClaimBasis",
    "ClaimLevel",
    "ClaimRequest",
    "ClaimSurface",
    "Disclosure",
    "evaluate_claim",
]


class ClaimBasis(StrEnum):
    """Is the number stated as observed in the population, or as a model's estimate?"""

    MEASURED = "MEASURED"
    MODELED = "MODELED"


class ClaimSurface(StrEnum):
    CLIENT_FACING = "CLIENT_FACING"
    INTERNAL = "INTERNAL"


class ClaimLevel(StrEnum):
    AGGREGATE = "AGGREGATE"
    SEGMENT = "SEGMENT"
    INDIVIDUAL = "INDIVIDUAL"


class Disclosure(StrEnum):
    """Statements that travel with a claim so the reader knows its limits."""

    SCOPE = "SCOPE"
    MODELED_VALUE = "MODELED_VALUE"
    HISTORICAL = "HISTORICAL"


@dataclass(frozen=True, slots=True)
class ClaimRequest:
    """One claim, described completely enough to decide it."""

    fields: tuple[str, ...]
    basis: ClaimBasis
    surface: ClaimSurface
    level: ClaimLevel
    joint: bool = False
    disclosures: frozenset[Disclosure] = frozenset()
    weight_scheme: str | None = None

    def __post_init__(self) -> None:
        if not self.fields:
            raise ValueError("a claim must name the fields that back it")

    @property
    def relates_fields(self) -> bool:
        many = len(set(self.fields)) > 1
        return self.joint or (many and self.level is not ClaimLevel.AGGREGATE)


def _field_rules(policy: FieldPolicy, request: ClaimRequest) -> Iterable[GateDecision]:
    f = policy.field
    if ClaimRule.AUDIT_ONLY in policy.claim_rules or not policy.eligibility.analysis:
        yield block(ViolationCode.FIELD_AUDIT_ONLY, f, "audit and provenance only")
        return

    measured = request.basis is ClaimBasis.MEASURED
    if measured and policy.has(ClaimRule.NEVER_MEASURED_FACT):
        yield block(
            ViolationCode.NEVER_MEASURED_FACT,
            f,
            f"{policy.evidence_status}: behavioural prior, never measured fact",
        )
    if measured and policy.has(ClaimRule.NEVER_DIRECT_SCHWARTZ):
        yield block(
            ViolationCode.NEVER_DIRECT_SCHWARTZ,
            f,
            "value proxy; never a direct Schwartz measurement",
        )
    if measured and not policy.eligibility.client_facing_measured_claim:
        yield block(
            ViolationCode.NOT_MEASURED_EVIDENCE,
            f,
            f"{policy.provenance_class} evidence cannot back a measured claim",
        )

    if request.level is ClaimLevel.INDIVIDUAL and (
        policy.has(ClaimRule.PERSON_VALUE_MODELED) or policy.has(ClaimRule.AGGREGATE_ONLY)
    ):
        yield block(
            ViolationCode.INDIVIDUAL_CLAIM_ON_AGGREGATE_FIELD,
            f,
            "the person-level value is modelled; only aggregate use is defensible",
        )

    if request.surface is ClaimSurface.CLIENT_FACING:
        if policy.has(ClaimRule.INTERNAL_ONLY):
            yield block(ViolationCode.FIELD_INTERNAL_ONLY, f, "declared for internal analysis only")
        if policy.has(ClaimRule.REQUIRES_SCOPE) and Disclosure.SCOPE not in request.disclosures:
            yield block(ViolationCode.SCOPE_DISCLOSURE_MISSING, f, "needs a scope disclosure")
        if (
            policy.has(ClaimRule.REQUIRES_MODELED_DISCLOSURE)
            and measured
            and Disclosure.MODELED_VALUE not in request.disclosures
        ):
            yield block(
                ViolationCode.MODELED_DISCLOSURE_MISSING, f, "needs a modelled-value disclosure"
            )
        if (
            policy.has(ClaimRule.HISTORICAL_OR_EXPLORATORY)
            and Disclosure.HISTORICAL not in request.disclosures
        ):
            yield block(
                ViolationCode.HISTORICAL_DISCLOSURE_MISSING,
                f,
                "historical or exploratory; not a current measurement",
            )

    mandated = policy.mandated_weight_scheme
    if policy.has(ClaimRule.SPECIFIED_WEIGHT_REQUIRED) and request.weight_scheme != mandated:
        yield block(
            ViolationCode.WEIGHT_SCHEME_MISMATCH,
            f,
            f"must be weighted by {mandated}, not {request.weight_scheme or 'nothing'}",
        )


def evaluate_claim(
    request: ClaimRequest, book: FieldPolicyBook, joint_status: JointStatus
) -> GateDecision:
    """Decide one claim. Every violation is reported, not only the first."""
    decisions: list[GateDecision] = []
    policies: list[FieldPolicy] = []
    for field in dict.fromkeys(request.fields):
        try:
            policy = book.get(field)
        except UndeclaredField as exc:
            decisions.append(block(ViolationCode.FIELD_UNDECLARED, field, str(exc)))
            continue
        policies.append(policy)
        decisions.extend(_field_rules(policy, request))

    if policies:
        decisions.append(
            evaluate_joint_structure(
                policies,
                joint_status,
                joint=request.relates_fields,
                measured=request.basis is ClaimBasis.MEASURED,
                client_facing=request.surface is ClaimSurface.CLIENT_FACING,
            )
        )
    return combine(decisions)
