"""Validation status bound to system identity, and the evidence tier gate.

Two reference rules (methodology-ledger M10, high-risk R12):

* **A validation state that outlives the artifact it validated is a false claim
  of verification.** ``validation_status.py`` is "a canonical validation state
  machine bound to the current system fingerprint". Here a
  :class:`ValidationState` names the fingerprint it was earned on, and
  :func:`effective_validation_status` returns ``NOT_VALIDATED`` the moment the
  current fingerprint differs.
* **Smoke is not holdout.** ``smoke_validation.py``: ``SMOKE_VALIDATED`` "never
  unlocks or replaces the one-shot human HOLDOUT_VALIDATED certificate", and
  ``validation_gate.py``: "a dry/smoke benchmark can never unlock a validity
  claim". Only a current ``HOLDOUT_VALIDATED`` permits a predictive-validity
  claim, and none exists today: external validity is
  ``EXTERNAL_HOLDOUT_PENDING``.

The tier gate (``tier_gate.py``): "Tier A: conditional + independently
validated joint evidence (currently none). Tier B: documented
marginal/conditional evidence; aggregate and demographic breakdowns ma[...]",
with use cases ``aggregate, demographic_breakdown, segmentation, persona,
individual, internal_experimental``. The recovered excerpt stops mid-sentence,
so two readings here are this port's, both fail closed and both listed for the
legacy-source parity run: Tier B permits aggregate, demographic-breakdown and
internal-experimental use and nothing else; Tier C permits internal-experimental
use only.

What the holdout certificate itself requires (preregistration, locked truth,
the five ablation baselines, the fourteen thresholds in
``validation_gate.DEFAULT_THRESHOLDS``) belongs to ``governance.holdout`` and is
not ported here; this module only refuses to let anything *else* stand in for it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from ..pipeline import fingerprint
from .gate import GateDecision, ViolationCode, allow, block, combine

__all__ = [
    "METHOD_STATUS_HOLDOUT_VALIDATED",
    "METHOD_STATUS_PENDING",
    "SYSTEM_FINGERPRINT_COMPONENTS",
    "TIER_PERMITS",
    "EvidenceTier",
    "TierUseCase",
    "ValidationState",
    "ValidationStatus",
    "effective_validation_status",
    "evaluate_predictive_validity_claim",
    "evaluate_tier",
    "method_status",
    "system_fingerprint",
]


class ValidationStatus(StrEnum):
    NOT_VALIDATED = "NOT_VALIDATED"
    SMOKE_VALIDATED = "SMOKE_VALIDATED"
    HOLDOUT_VALIDATED = "HOLDOUT_VALIDATED"


# Stamped on every analysis payload by code, never by a model (M17).
METHOD_STATUS_PENDING: Final = (
    "synthetic/modelled research; external predictive certification pending"
)
# Production copy: the reference never reached this state, so it has no wording for it.
METHOD_STATUS_HOLDOUT_VALIDATED: Final = (
    "synthetic/modelled research; externally validated against a blind human holdout"
)

# What a system fingerprint must bind. Each is the SHA-256 of the thing itself.
SYSTEM_FINGERPRINT_COMPONENTS: Final = (
    "panel_sha256",
    "field_dictionary_sha256",
    "joint_certificate_sha256",
    "engine_version",
)
_SHA256: Final = re.compile(r"[0-9a-f]{64}")


def system_fingerprint(components: Mapping[str, str]) -> str:
    """Fingerprint the system a validation was earned on. Every component is required.

    A missing component is refused rather than fingerprinted as absent: a
    fingerprint that ignores the panel would survive a panel change, which is the
    exact failure R12 describes.
    """
    missing = [k for k in SYSTEM_FINGERPRINT_COMPONENTS if not components.get(k)]
    if missing:
        raise ValueError(f"system fingerprint needs {', '.join(missing)}")
    for key in SYSTEM_FINGERPRINT_COMPONENTS[:3]:
        if not _SHA256.fullmatch(components[key]):
            raise ValueError(f"{key} is not a SHA-256")
    return fingerprint({k: components[k] for k in sorted(components)})


@dataclass(frozen=True, slots=True)
class ValidationState:
    """A validation status and the system fingerprint it was earned on."""

    status: ValidationStatus
    system_fingerprint: str

    def __post_init__(self) -> None:
        if not _SHA256.fullmatch(self.system_fingerprint):
            raise ValueError("a validation state must name the system fingerprint it was earned on")


def effective_validation_status(
    state: ValidationState | None, current_fingerprint: str
) -> ValidationStatus:
    """The status that holds *now*: none if never validated or earned on another system."""
    if state is None or state.system_fingerprint != current_fingerprint:
        return ValidationStatus.NOT_VALIDATED
    return state.status


def evaluate_predictive_validity_claim(
    state: ValidationState | None, current_fingerprint: str
) -> GateDecision:
    """May a result claim predictive validity? Only on a current holdout validation."""
    if state is not None and state.system_fingerprint != current_fingerprint:
        return block(
            ViolationCode.VALIDATION_NOT_CURRENT,
            "system",
            f"{state.status} was earned on {state.system_fingerprint[:12]}..., "
            f"current system is {current_fingerprint[:12]}...",
        )
    status = effective_validation_status(state, current_fingerprint)
    if status is ValidationStatus.HOLDOUT_VALIDATED:
        return allow()
    why = (
        "smoke validation never unlocks a validity claim"
        if status is ValidationStatus.SMOKE_VALIDATED
        else "no blind human holdout validation (EXTERNAL_HOLDOUT_PENDING)"
    )
    return block(ViolationCode.PREDICTIVE_VALIDITY_UNPROVEN, "system", why)


def method_status(state: ValidationState | None, current_fingerprint: str) -> str:
    """The method-status stamp for a payload, from the validation that holds now."""
    if (
        effective_validation_status(state, current_fingerprint)
        is ValidationStatus.HOLDOUT_VALIDATED
    ):
        return METHOD_STATUS_HOLDOUT_VALIDATED
    return METHOD_STATUS_PENDING


# --- tier gate ----------------------------------------------------------------------------


class EvidenceTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class TierUseCase(StrEnum):
    AGGREGATE = "aggregate"
    DEMOGRAPHIC_BREAKDOWN = "demographic_breakdown"
    SEGMENTATION = "segmentation"
    PERSONA = "persona"
    INDIVIDUAL = "individual"
    INTERNAL_EXPERIMENTAL = "internal_experimental"


TIER_PERMITS: Final[Mapping[EvidenceTier, frozenset[TierUseCase]]] = {
    EvidenceTier.A: frozenset(TierUseCase),
    EvidenceTier.B: frozenset(
        {
            TierUseCase.AGGREGATE,
            TierUseCase.DEMOGRAPHIC_BREAKDOWN,
            TierUseCase.INTERNAL_EXPERIMENTAL,
        }
    ),
    EvidenceTier.C: frozenset({TierUseCase.INTERNAL_EXPERIMENTAL}),
}


def evaluate_tier(
    dimension_tiers: Mapping[str, str | None], use_case: str | TierUseCase
) -> GateDecision:
    """May these dimensions support a claim of this use case? Every dimension must permit it.

    An unknown use case, a dimension with no tier or an unrecognised tier, and
    an empty set of dimensions all refuse.
    """
    try:
        wanted = TierUseCase(use_case)
    except ValueError:
        return block(ViolationCode.TIER_UNKNOWN, str(use_case), "unknown use case")
    if not dimension_tiers:
        return block(ViolationCode.TIER_UNKNOWN, wanted.value, "no dimensions to evaluate")

    decisions: list[GateDecision] = []
    for dimension, raw in sorted(dimension_tiers.items()):
        try:
            tier = EvidenceTier(raw) if raw is not None else None
        except ValueError:
            tier = None
        if tier is None:
            decisions.append(block(ViolationCode.TIER_UNKNOWN, dimension, f"tier {raw!r}"))
        elif wanted not in TIER_PERMITS[tier]:
            decisions.append(
                block(
                    ViolationCode.TIER_INSUFFICIENT,
                    dimension,
                    f"tier {tier} does not support {wanted} claims",
                )
            )
    return combine(decisions)
