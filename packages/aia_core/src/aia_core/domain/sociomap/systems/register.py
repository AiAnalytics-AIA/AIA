"""Sociomapa systémů, register entries per map input (decision SM18, answers Q-METH).

Each map input (Budoucnosti, Nastavení vah, Experti, Jednotky, Měsíce, Profil ukazatelů,
Konkurence, Vlivy) gets its own entry in the methodologist's register only after its own
planted-answer test passes its declared rates. Until then every map of that input carries
:data:`AWAITING_LABEL`. The 21 Oct approval covers people's ratings only.

Pure: no I/O. The register itself is Metodika (ADR 0023); this module only decides the label.
"""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass

__all__ = ["AWAITING_LABEL", "InputStatus", "input_status"]

AWAITING_LABEL = "metoda čeká na schválení metodikem"


@dataclass(frozen=True)
class InputStatus:
    input_name: str
    registered: bool
    label: str | None


def input_status(
    input_name: str, *, planted_test_passed: bool, registered: Set[str]
) -> InputStatus:
    """Registered only when the input has its own entry and its planted-answer test passed."""
    ok = planted_test_passed and input_name in registered
    return InputStatus(input_name, ok, None if ok else AWAITING_LABEL)
