"""A person's confirmation of a start's cost ceiling: the confirming entry point (ADR 0028
decision 3; lead-orchestration LO2).

A start whose cost ceiling reaches the study's confirmation threshold (``spend_confirm_usd``)
needs a person's yes for at least that ceiling (``money.threshold_verdict``). That yes was a bare
``confirm_cost_usd`` argument, so any caller able to reach the start could supply it, the plan
step included, and the only check (``APPROVE_BUDGET`` in ``record_spend_confirmation``) ran
after the run was created. It is now a :class:`SpendConfirmation`, which only
:func:`confirm_spend` issues, and only to a scope holding ``APPROVE_BUDGET`` (which
``WORKER_PERMISSIONS`` withholds and the plan authority will not hold), before anything is
created. It names the person and the Study it was issued in; a start elsewhere refuses it.

Enforced three ways: the module-private issuer below, an init-only argument, so a confirmation
built anywhere else, or copied with ``dataclasses.replace``, raises; ``tools/layer_check.sh``,
which forbids building one, naming the issuer, or calling :func:`confirm_spend` in the worker or
an executor; and the import contract "nothing the worker runs reaches the confirming start" in the
root ``pyproject.toml``.
"""

from __future__ import annotations

import math
from dataclasses import InitVar, dataclass
from typing import Final

from ..domain.scope import Permission, StudyContext

__all__ = ["SpendConfirmation", "confirm_spend"]

_CONFIRMATION_ISSUER: Final = object()


@dataclass(frozen=True, slots=True)
class SpendConfirmation:
    """A person's yes to spending up to ``usd`` on one start in one Study, issued by
    :func:`confirm_spend`."""

    usd: float
    #: The person who confirmed, and the Study they confirmed it in.
    confirmed_by: str
    study_id: str
    issuer: InitVar[object]

    def __post_init__(self, issuer: object) -> None:
        if issuer is not _CONFIRMATION_ISSUER:
            raise TypeError("a spend confirmation is issued only by confirm_spend")


def confirm_spend(scope: StudyContext, usd: float | None) -> SpendConfirmation | None:
    """The person's confirmed amount as a :class:`SpendConfirmation`, or ``None`` when they
    confirmed nothing. Needs ``APPROVE_BUDGET``; a figure that is not a finite, non-negative
    number of USD is refused, never read as a confirmation."""
    if usd is None:
        return None
    scope.require(Permission.APPROVE_BUDGET)
    if isinstance(usd, bool) or not math.isfinite(usd) or usd < 0:
        raise ValueError("a confirmed amount is a finite, non-negative number of USD")
    return SpendConfirmation(float(usd), scope.actor_id, scope.study_id, _CONFIRMATION_ISSUER)
