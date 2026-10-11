"""Every method module the Metodika tab shows, in the order it shows them.

Empty until the first module is catalogued (plan ``methodology-tab.md`` S1: the Sociomap).
Every module listed here is held complete by the test suite: no problem from
:func:`~.resolution.module_problems`, every step's source pin current, every named test
present.
"""

from __future__ import annotations

from .catalogue import MethodModule

__all__ = ["MODULES", "module"]

MODULES: tuple[MethodModule, ...] = ()


def module(module_id: str) -> MethodModule:
    """The registered module ``module_id``; ``KeyError`` for one that is not registered."""
    for candidate in MODULES:
        if candidate.id == module_id:
            return candidate
    raise KeyError(module_id)
