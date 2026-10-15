"""Every method module the Metodika tab shows, in the order it shows them.

Every module listed here is held complete by the test suite: no problem from
:func:`~.resolution.module_problems`, every step's source pin current, every named test
present.
"""

from __future__ import annotations

from .aggregation import AGGREGATION
from .catalogue import MethodModule
from .readiness import READINESS
from .response import RESPONSE
from .sociomap import SOCIOMAP
from .sociomap_reference import SOCIOMAP_REFERENCE
from .sociomapping import SOCIOMAPPING
from .support import SUPPORT
from .weighting import WEIGHTING

__all__ = ["MODULES", "module"]

MODULES: tuple[MethodModule, ...] = (
    SOCIOMAP,
    SOCIOMAP_REFERENCE,
    SOCIOMAPPING,
    SUPPORT,
    AGGREGATION,
    WEIGHTING,
    RESPONSE,
    READINESS,
)


def module(module_id: str) -> MethodModule:
    """The registered module ``module_id``; ``KeyError`` for one that is not registered."""
    for candidate in MODULES:
        if candidate.id == module_id:
            return candidate
    raise KeyError(module_id)
