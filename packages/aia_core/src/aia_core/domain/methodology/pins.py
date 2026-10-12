"""What a research run pins from the methodology in force (ADR 0023 decision 6, plan A4).

A run pins its Sociomap methods when it starts (``research_sociomap.SociomapMethod``), each
with its whole specification, and computes exactly those whatever is put in force later. With
nothing stored the pins are the code's (:func:`~aia_core.domain.research_sociomap.default_methods`);
with an edited object map in force, the reference map is pinned as always beside the edited
specification, under the version's own name. That is all the engine needs for an edited
parameter: it already computes whatever specification a run pinned.

A version's replaced formulas are pinned with its specification
(``SociomapMethod.formulas``), and the engine computes each from its expression where the
code's formula would run (``sociomap.slots``, S4c). A slot the engine does not read is
refused (:data:`COMPUTED_SLOTS`): a run must never quietly compute the built-in formula
while its methodology says another.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from ..evidence.support import AIA_SUPPORT_V1, SupportSpec
from ..research_sociomap import SociomapMethod, default_methods
from ..sociomap.slots import ENGINE_SLOTS
from ..sociomap.specification import AIA_SOCIOMAP_V1, SociomapSpecV3

__all__ = [
    "COMPUTED_SLOTS",
    "FormulaNotComputed",
    "read_support_pin",
    "sociomap_methods_for",
    "support_spec_for",
    "uncomputed_formulas",
]

#: The slots whose stored expression the engine evaluates in place of its own function:
#: every slot the object map's engine reads. A version replacing any other slot is stored
#: and shown, but not put in force.
COMPUTED_SLOTS: Final[frozenset[str]] = ENGINE_SLOTS


class FormulaNotComputed(ValueError):
    """A version replaces a formula the engine does not yet evaluate from its expression."""

    def __init__(self, slots: list[str]) -> None:
        self.slots = slots
        super().__init__(
            "the engine does not yet compute these formulas from a stored expression, so a "
            f"version replacing them cannot be put in force: {', '.join(slots)}"
        )


def uncomputed_formulas(payload: Mapping[str, Any]) -> list[str]:
    """The slots a version payload replaces that the engine does not evaluate yet."""
    return sorted(set(payload.get("formulas", {})) - COMPUTED_SLOTS)


def sociomap_methods_for(payload: Mapping[str, Any] | None) -> tuple[SociomapMethod, ...]:
    """The Sociomap pins of a run started under ``payload`` (``None``: the code's preset)."""
    if payload is None:
        return default_methods()
    missing = uncomputed_formulas(payload)
    if missing:
        raise FormulaNotComputed(missing)
    edited = SociomapSpecV3.model_validate(payload["spec"])
    return (
        SociomapMethod.of(AIA_SOCIOMAP_V1),
        SociomapMethod.of(edited, payload.get("formulas") or {}),
    )


def support_spec_for(payload: Mapping[str, Any] | None) -> SupportSpec:
    """The support rules a run started under ``payload`` pins (plan ``methodology-tab`` G1c).

    ``None`` -- nothing stored -- is the code's preset, ``aia-support-1``: both rules as they
    were before any version (owner, 2026-10-12), the unit's donor rule for Results and AIA's
    gate for analysis."""
    if payload is None:
        return AIA_SUPPORT_V1
    return SupportSpec.model_validate(payload["spec"])


def read_support_pin(value: Any) -> SupportSpec:
    """A run's pinned support rules from their stored form. A run started before support was
    pinned (``None``) was computed under ``aia-support-1``, so that is what it reads."""
    if value is None:
        return AIA_SUPPORT_V1
    return SupportSpec.model_validate(value)
