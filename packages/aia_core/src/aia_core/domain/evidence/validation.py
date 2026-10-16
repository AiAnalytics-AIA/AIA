"""Validation status bound to system identity.

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

The reference's tier gate (``tier_gate.py``) is not ported: nothing gave a field a tier and
its description of tiers B and C breaks off mid-sentence, so the A/B/C permits AIA once read
into it decided nothing. What a population field may serve is the population's field policy
(``domain/population/policy.py``; plan methodology-tab V1c2, owner 2026-10-15).

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
from .gate import GateDecision, ViolationCode, allow, block

__all__ = [
    "METHOD_STATUS_HOLDOUT_VALIDATED",
    "METHOD_STATUS_PENDING",
    "RESPONDENT_SYSTEM_COMPONENTS",
    "SYSTEM_FINGERPRINT_COMPONENTS",
    "ValidationState",
    "ValidationStatus",
    "effective_validation_status",
    "evaluate_predictive_validity_claim",
    "lifts_internal_only",
    "method_status",
    "respondent_system_fingerprint",
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


#: What a modelled respondent system's fingerprint binds (ADR 0024 §4). A validation earned on
#: one value of any of these says nothing about another: the claim goes back to internal.
RESPONDENT_SYSTEM_COMPONENTS: Final = (
    "respondent_prompt_sha256",
    "persona_builder",
    "persona_mode",
    "sampler_version",
    "population_version",
    "model_binding",
    "response_process_version",
)


def respondent_system_fingerprint(components: Mapping[str, str]) -> str:
    """Fingerprint the respondent system a modelled validation is earned on.

    Every component is required and nothing else is accepted: a missing one would let a
    validation survive a change to it, and an extra one is a name nobody checked. The prompt
    is named by its SHA-256.
    """
    missing = [k for k in RESPONDENT_SYSTEM_COMPONENTS if not str(components.get(k, "")).strip()]
    if missing:
        raise ValueError(f"respondent system fingerprint needs {', '.join(missing)}")
    extra = sorted(set(components) - set(RESPONDENT_SYSTEM_COMPONENTS))
    if extra:
        raise ValueError(f"respondent system fingerprint does not bind {', '.join(extra)}")
    if not _SHA256.fullmatch(components["respondent_prompt_sha256"]):
        raise ValueError("respondent_prompt_sha256 is not a SHA-256")
    return fingerprint(
        {"kind": "respondent_system", **{k: components[k] for k in RESPONDENT_SYSTEM_COMPONENTS}}
    )


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


def lifts_internal_only(state: ValidationState | None, current_fingerprint: str | None) -> bool:
    """May a modelled claim leave the internal surface? Only on a current holdout validation.

    ADR 0024 §4. No current system (``None``), no validation, one earned on another system, and
    a smoke validation all keep it internal: smoke never stands in for the holdout.
    """
    if current_fingerprint is None:
        return False
    return (
        effective_validation_status(state, current_fingerprint)
        is ValidationStatus.HOLDOUT_VALIDATED
    )


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
