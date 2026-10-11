"""The formulas a methodology version replaces, as the engine evaluates them (ADR 0023, S4c).

ADR 0023 decision 4: each formula of the object map is a *slot*, and a stored methodology
version may replace a slot's expression. The engine computes a replaced slot from the
version's compiled expression; every slot not replaced runs the code exactly as before. With
no slot replaced nothing here changes a single bit of any map.

The engine knows nothing of the expression language: it reads a slot by its id and calls it
with the slot's declared variables, by name. Compiling and checking an expression is
``domain.methodology``'s; this module only names the ids the engine reads, so a slot id is
spelled once.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, Final

__all__ = [
    "ALIGNMENT",
    "CONNECTEDNESS",
    "DISTANCE",
    "EFFECTIVE_N",
    "EFFECT_FLOOR",
    "ENGINE_SLOTS",
    "HEIGHT",
    "INTERVAL_HIGH",
    "INTERVAL_LOW",
    "K100",
    "KERNEL",
    "NO_SLOTS",
    "PERSON",
    "SCALE",
    "STRESS_1",
    "SUPPORT_EFFECTIVE_N",
    "Slots",
]

#: A replaced slot: called with the slot's variables by name, it returns a number.
type Slots = Mapping[str, Callable[..., Any]]

#: Nothing replaced: the code computes every formula.
NO_SLOTS: Final[Slots] = MappingProxyType({})

SCALE: Final = "f1.scale"
PERSON: Final = "f2.person"
EFFECTIVE_N: Final = "f3.effective_n"
INTERVAL_LOW: Final = "f3.interval_low"
INTERVAL_HIGH: Final = "f3.interval_high"
EFFECT_FLOOR: Final = "f3.effect_floor"
DISTANCE: Final = "f6.distance"
STRESS_1: Final = "f7.stress_1"
ALIGNMENT: Final = "f8.alignment"
CONNECTEDNESS: Final = "f8.connectedness"
HEIGHT: Final = "f8.height"
K100: Final = "f9.k100"
KERNEL: Final = "f12.kernel"
SUPPORT_EFFECTIVE_N: Final = "support.effective_n"

#: Every slot the object-map engine reads from a version.
ENGINE_SLOTS: Final = frozenset(
    {
        SCALE,
        PERSON,
        EFFECTIVE_N,
        INTERVAL_LOW,
        INTERVAL_HIGH,
        EFFECT_FLOOR,
        DISTANCE,
        STRESS_1,
        ALIGNMENT,
        CONNECTEDNESS,
        HEIGHT,
        K100,
        KERNEL,
        SUPPORT_EFFECTIVE_N,
    }
)
