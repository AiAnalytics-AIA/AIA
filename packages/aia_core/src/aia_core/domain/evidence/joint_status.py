"""The ``CORE_JOINT_STATUS`` certificate: what the population's joint structure supports.

The synthetic population is a same-person core (Census skeleton plus PIAAC /
ISSP respondents) with **donor-matched blocks** attached by constrained
matching. Within the core, fields are one person's answers. Across blocks they
are not: two matched blocks were answered by *different* donors, so a
relationship between them is a property of the matching, not of anybody
(methodology-ledger M03, high-risk R6).

The reference certificate says so explicitly -- ``cross_block_same_person_joint:
false``, ``client_joint_outputs_allowed: false``,
``cross_block_joint_claims_allowed: false`` -- and it is bound to the exact
production panel bytes by SHA-256. ``core_joint.load_joint_status()`` degrades to
a fallback when the file is missing, unparseable, at an unknown status, or when
the panel hash no longer matches. That is the one dataset gate in the reference
that already fails closed, and it is kept.

Production reading of what the reference leaves unstated, each fail closed:

* The fallback's values are not recoverable without the legacy source, so the
  degraded status here permits **nothing** client-facing (every ``*_allowed``
  flag false, no matched block certified). Recorded as an open item for the
  legacy-source parity run.
* A panel whose hash was not measured cannot be matched against the certificate,
  so it degrades too (``PANEL_HASH_UNVERIFIED``), rather than being trusted.
* A certificate flag that is not a JSON boolean is malformed, not truthy.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .field_policy import FieldPolicy, ProvenanceClass
from .gate import GateDecision, ViolationCode, block, combine

__all__ = [
    "CORE_BLOCKS",
    "CORE_UNIT",
    "JointDegradation",
    "JointStatus",
    "JointUnitKind",
    "PredictionValidationStatus",
    "StructureStatus",
    "evaluate_joint_structure",
    "joint_unit",
    "joint_unit_kind",
    "load_joint_status",
]


class StructureStatus(StrEnum):
    """Certificate structure statuses this code knows. Any other status degrades."""

    QC_PASSED = "QC_PASSED"


class PredictionValidationStatus(StrEnum):
    """Certificate predictive-validation statuses this code knows. Any other degrades.

    Only the status the reference actually carries is known. A certificate that
    claims more must arrive with the code that knows what "more" permits.
    """

    EXTERNAL_HOLDOUT_PENDING = "EXTERNAL_HOLDOUT_PENDING"


class JointDegradation(StrEnum):
    """Why a certificate was not honoured."""

    MISSING = "MISSING"
    UNPARSEABLE = "UNPARSEABLE"
    MALFORMED = "MALFORMED"
    UNKNOWN_STATUS = "UNKNOWN_STATUS"
    PANEL_HASH_UNVERIFIED = "PANEL_HASH_UNVERIFIED"
    PANEL_HASH_MISMATCH = "PANEL_HASH_MISMATCH"


# The blocks that make up the same-person core. Everything in them was answered
# by one respondent (or is that respondent's Census anchor), so a relationship
# among them is same-person truth. Every other block is its own joint unit.
CORE_BLOCKS: Final = frozenset({"population_anchor", "core", "piaac_core"})
CORE_UNIT: Final = "core"

_BOOLEAN_KEYS: Final = (
    "core_same_person_joint",
    "cross_block_same_person_joint",
    "client_joint_outputs_allowed",
    "descriptive_core_outputs_allowed",
    "matched_block_outputs_allowed",
    "cross_block_joint_claims_allowed",
)
_SHA256: Final = re.compile(r"[0-9a-f]{64}")

# Proves a status came from load_joint_status. A certificate decoded from a model
# response or a request body can never carry it, so nobody can hand the claim gate
# a permissive certificate they built themselves.
_JOINT_ISSUER: Final = object()


class JointUnitKind(StrEnum):
    CORE = "CORE"
    MATCHED = "MATCHED"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class JointStatus:
    """The certificate in force, or the degraded status that replaced it."""

    degradation: JointDegradation | None
    detail: str
    production_panel: str | None
    panel_sha256: str | None
    structure_status: StructureStatus | None
    prediction_validation_status: PredictionValidationStatus | None
    core_same_person_joint: bool
    cross_block_same_person_joint: bool
    client_joint_outputs_allowed: bool
    descriptive_core_outputs_allowed: bool
    matched_block_outputs_allowed: bool
    cross_block_joint_claims_allowed: bool
    matched_blocks: frozenset[str]
    runtime_identity_contract: str | None
    _issuer: Any

    def __post_init__(self) -> None:
        if self._issuer is not _JOINT_ISSUER:
            raise ValueError("a joint status is issued only by load_joint_status")

    @property
    def certified(self) -> bool:
        return self.degradation is None


def _degraded(reason: JointDegradation, detail: str) -> JointStatus:
    return JointStatus(
        degradation=reason,
        detail=detail,
        production_panel=None,
        panel_sha256=None,
        structure_status=None,
        prediction_validation_status=None,
        core_same_person_joint=False,
        cross_block_same_person_joint=False,
        client_joint_outputs_allowed=False,
        descriptive_core_outputs_allowed=False,
        matched_block_outputs_allowed=False,
        cross_block_joint_claims_allowed=False,
        matched_blocks=frozenset(),
        runtime_identity_contract=None,
        _issuer=_JOINT_ISSUER,
    )


def load_joint_status(
    certificate: bytes | None, *, measured_panel_sha256: str | None
) -> JointStatus:
    """Honour the certificate only if it parses, is known, and binds to the measured panel.

    ``measured_panel_sha256`` is the hash of the panel bytes actually loaded,
    computed by whoever loaded them -- never read from the certificate itself.
    """
    if certificate is None:
        return _degraded(JointDegradation.MISSING, "no CORE_JOINT_STATUS certificate")
    try:
        raw = json.loads(certificate.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _degraded(JointDegradation.UNPARSEABLE, f"certificate is not JSON: {exc}")
    if not isinstance(raw, Mapping):
        return _degraded(JointDegradation.MALFORMED, "certificate is not a JSON object")

    try:
        structure = StructureStatus(str(raw.get("structure_status")))
        prediction = PredictionValidationStatus(str(raw.get("prediction_validation_status")))
    except ValueError:
        return _degraded(
            JointDegradation.UNKNOWN_STATUS,
            f"unknown status {raw.get('structure_status')!r} / "
            f"{raw.get('prediction_validation_status')!r}",
        )

    flags: dict[str, bool] = {}
    for key in _BOOLEAN_KEYS:
        value = raw.get(key)
        if not isinstance(value, bool):
            return _degraded(JointDegradation.MALFORMED, f"{key} is {value!r}, not a boolean")
        flags[key] = value
    panel = raw.get("production_panel")
    sha = raw.get("panel_sha256")
    blocks = raw.get("matched_blocks")
    identity = raw.get("runtime_identity_contract")
    if not isinstance(panel, str) or not panel:
        return _degraded(JointDegradation.MALFORMED, "production_panel is missing")
    if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
        return _degraded(JointDegradation.MALFORMED, "panel_sha256 is not a SHA-256")
    if not isinstance(blocks, list) or not all(isinstance(b, str) and b for b in blocks):
        return _degraded(JointDegradation.MALFORMED, "matched_blocks is not a list of names")
    if identity is not None and not isinstance(identity, str):
        return _degraded(JointDegradation.MALFORMED, "runtime_identity_contract is not text")

    if measured_panel_sha256 is None:
        return _degraded(
            JointDegradation.PANEL_HASH_UNVERIFIED,
            "the loaded panel's SHA-256 was not measured, so the binding cannot be checked",
        )
    if measured_panel_sha256 != sha:
        return _degraded(
            JointDegradation.PANEL_HASH_MISMATCH,
            f"certificate binds {sha[:12]}..., loaded panel is {measured_panel_sha256[:12]}...",
        )

    return JointStatus(
        degradation=None,
        detail=f"certified for {panel}",
        production_panel=panel,
        panel_sha256=sha,
        structure_status=structure,
        prediction_validation_status=prediction,
        matched_blocks=frozenset(blocks),
        runtime_identity_contract=identity,
        _issuer=_JOINT_ISSUER,
        **flags,
    )


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
                f"{status.degradation}: {status.detail}",
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
