"""What a research run pins from the methodology in force (ADR 0023 decision 6, plan A4).

A run pins its Sociomap methods when it starts (``research_sociomap.SociomapMethod``), each
with its whole specification, and computes exactly those whatever is put in force later. With
nothing stored the pins are the code's (:func:`~aia_core.domain.research_sociomap.default_methods`);
with an edited object map in force, the reference map is pinned as always beside the edited
specification, under the version's own name. That is all the engine needs for an edited
parameter: it already computes whatever specification a run pinned.

A version that replaces a formula is refused here until the engine evaluates that slot's
expression (:data:`COMPUTED_SLOTS`): a run must never quietly compute the built-in formula
while its methodology says another.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from ..research_sociomap import SociomapMethod, default_methods
from ..sociomap.specification import AIA_SOCIOMAP_V1, SociomapSpecV3

__all__ = [
    "COMPUTED_SLOTS",
    "FormulaNotComputed",
    "sociomap_methods_for",
    "uncomputed_formulas",
]

#: The slots whose stored expression the engine evaluates in place of its own function.
#: Empty until the engine is wired to expressions; a version replacing any other slot is
#: stored and shown, but not put in force.
COMPUTED_SLOTS: Final[frozenset[str]] = frozenset()


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
    return (SociomapMethod.of(AIA_SOCIOMAP_V1), SociomapMethod.of(edited))
