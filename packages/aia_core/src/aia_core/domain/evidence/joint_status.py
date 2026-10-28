"""The joint structure of a population: what a claim may relate, under its certificate.

The synthetic population is a same-person core (Census skeleton plus PIAAC /
ISSP respondents) with **donor-matched blocks** attached by constrained
matching. Within the core, fields are one person's answers. Across blocks they
are not: two matched blocks were answered by *different* donors, so a
relationship between them is a property of the matching, not of anybody
(methodology-ledger M03, high-risk R6).

The certificate itself, ``CORE_JOINT_STATUS``, is evaluated once, by
:func:`aia_core.domain.population.evaluate_joint_certificate`, for the population loader and
for this gate alike (MVP-29, evidence-integrity 5b): its :class:`JointStatus` is the only
status, bound to the exact panel bytes by SHA-256, and a missing, unparseable, unknown or
unbound certificate falls back to one that permits nothing. What stays here is the claim
gate's reading of it: which unit a field belongs to and whether a claim's fields may be
related.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Final

from ..population.companions import JointStatus
from .field_policy import FieldPolicy, ProvenanceClass
from .gate import GateDecision, ViolationCode, block, combine

__all__ = [
    "CORE_BLOCKS",
    "CORE_UNIT",
    "JointStatus",
    "JointUnitKind",
    "evaluate_joint_structure",
    "joint_unit",
    "joint_unit_kind",
]


# The blocks that make up the same-person core. Everything in them was answered
# by one respondent (or is that respondent's Census anchor), so a relationship
# among them is same-person truth. Every other block is its own joint unit.
CORE_BLOCKS: Final = frozenset({"population_anchor", "core", "piaac_core"})
CORE_UNIT: Final = "core"


class JointUnitKind(StrEnum):
    CORE = "CORE"
    MATCHED = "MATCHED"
    OTHER = "OTHER"


def joint_unit(policy: FieldPolicy) -> str:
    """The joint unit a field belongs to: the same-person core, or its own block."""
    return CORE_UNIT if policy.block in CORE_BLOCKS else policy.block


def joint_unit_kind(policy: FieldPolicy) -> JointUnitKind:
    if policy.block in CORE_BLOCKS:
        return JointUnitKind.CORE
    if policy.provenance_class is ProvenanceClass.DONOR_MATCHED:
        return JointUnitKind.MATCHED
    return JointUnitKind.OTHER


def evaluate_joint_structure(
    policies: Iterable[FieldPolicy],
    status: JointStatus,
    *,
    joint: bool,
    measured: bool,
    client_facing: bool,
) -> GateDecision:
    """Decide whether the joint structure of the population supports a claim.

    ``joint`` is true when the claim relates the fields to each other (a
    cross-tab, a correlation, a cluster, a segment defined on one and described
    by another), rather than stating each separately.

    * A client-facing claim needs a certificate in force, and every unit it
      touches certified: the core by ``descriptive_core_outputs_allowed``, a
      matched block by ``matched_block_outputs_allowed`` *and* by being named in
      ``matched_blocks``.
    * A joint claim within the core, or between the core and one other block (a
      labelled donor-block summary by demographics), is not a cross-block claim.
    * A joint claim spanning two or more non-core units is cross-block: refused
      unless the certificate allows cross-block claims, refused as measured
      truth unless cross-block joints are same-person, and refused client-facing
      unless client joint outputs are allowed. At the current certificate all
      three are false, so all three refuse.
    """
    fields = list(policies)
    subject = ",".join(p.field for p in fields)
    decisions: list[GateDecision] = []

    if client_facing and not status.certified:
        decisions.append(
            block(
                ViolationCode.JOINT_CERTIFICATE_DEGRADED,
                subject,
                f"{status.state.value}: {status.detail}",
            )
        )

    kinds = {joint_unit(p): joint_unit_kind(p) for p in fields}
    if client_facing and status.certified:
        for unit, kind in sorted(kinds.items()):
            if kind is JointUnitKind.CORE and not status.descriptive_core_outputs_allowed:
                decisions.append(
                    block(
                        ViolationCode.CORE_OUTPUTS_NOT_CERTIFIED, unit, "core outputs not allowed"
                    )
                )
            if kind is JointUnitKind.MATCHED and not (
                status.matched_block_outputs_allowed and unit in status.matched_blocks
            ):
                decisions.append(
                    block(
                        ViolationCode.MATCHED_BLOCK_NOT_CERTIFIED,
                        unit,
                        "donor-matched block is not certified for client outputs",
                    )
                )

    if joint:
        non_core = sorted(u for u in kinds if u != CORE_UNIT)
        if len(non_core) >= 2:
            units = "+".join(non_core)
            if not status.cross_block_joint_claims_allowed:
                decisions.append(
                    block(ViolationCode.CROSS_BLOCK_JOINT_CLAIM, units, "cross-block joint claim")
                )
            if measured and not status.cross_block_same_person_joint:
                decisions.append(
                    block(
                        ViolationCode.CROSS_BLOCK_NOT_SAME_PERSON,
                        units,
                        "a cross-block relationship is not same-person measured truth",
                    )
                )
            if client_facing and not status.client_joint_outputs_allowed:
                decisions.append(
                    block(
                        ViolationCode.CLIENT_JOINT_OUTPUT, units, "client joint outputs forbidden"
                    )
                )
        elif non_core == [] and len(fields) > 1 and not status.core_same_person_joint:
            decisions.append(
                block(
                    ViolationCode.CORE_OUTPUTS_NOT_CERTIFIED,
                    CORE_UNIT,
                    "the core is not certified as a same-person joint",
                )
            )

    return combine(decisions)
