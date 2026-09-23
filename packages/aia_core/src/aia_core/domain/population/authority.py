"""Who may move a population: the population-operator capability.

Establishing a population and promoting LIVE change what every study in every
organization is computed over. That is platform administration, not study work
and not tenant administration:

* a :class:`~aia_core.domain.scope.StudyContext` confers nothing here -- its
  permissions are about one study;
* an organization ``OWNER`` confers nothing here either -- an owner administers
  one tenant, and must not be able to move LIVE for all of them.

So this is a separate capability with exactly two permissions, issued only by
``aia_core.application.population_authority.PopulationAuthority`` from trusted
deployment configuration, through a module-private sentinel -- the construction
that makes ``StudyContext`` unforgeable. A request body, a tool argument or a
model-generated value can name a user id; none of them can produce this object.
The shared ``Permission`` enum and the scope roles are untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .errors import PopulationError

__all__ = [
    "PopulationOperatorContext",
    "PopulationOperatorGrant",
    "PopulationPermission",
    "PopulationPermissionDenied",
    "require_operator",
]

# Proof that an operator context was issued by the population authority.
_OPERATOR_ISSUER: Final = object()


class PopulationPermission(StrEnum):
    """The only two platform-level population capabilities."""

    #: Create the STATIC or LIVE population of a dataset. Happens once per population.
    POPULATION_ESTABLISH = "POPULATION_ESTABLISH"
    #: Move LIVE to another version by explicit compare-and-set promotion.
    POPULATION_PROMOTE = "POPULATION_PROMOTE"


class PopulationPermissionDenied(PopulationError):
    """The caller holds no population-operator capability for this operation."""

    reason = "population_permission_denied"


@dataclass(frozen=True, slots=True)
class PopulationOperatorGrant:
    """Proof the population authority issued a context. Cannot be forged."""

    _issuer: Any

    def __post_init__(self) -> None:
        if self._issuer is not _OPERATOR_ISSUER:
            raise PopulationPermissionDenied(
                "an operator grant may only be issued by the population authority",
                reason="forged_operator_grant",
            )

    @classmethod
    def _issue(cls) -> PopulationOperatorGrant:
        """Issue a grant. Internal to the population authority."""
        return cls(_issuer=_OPERATOR_ISSUER)


@dataclass(frozen=True, slots=True)
class PopulationOperatorContext:
    """An authenticated user acting as a population operator.

    ``actor_id`` is the verified user id; it is what establish and promote record,
    so the actor on a promotion can never be a free-text argument.
    """

    actor_id: str
    permissions: frozenset[PopulationPermission]
    grant: PopulationOperatorGrant
    request_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.grant, PopulationOperatorGrant):
            raise PopulationPermissionDenied(
                "an operator context requires an issued grant", reason="forged_operator_grant"
            )
        if not self.actor_id:
            raise PopulationPermissionDenied(
                "an operator context names its actor", reason="incomplete"
            )

    def require(self, permission: PopulationPermission) -> None:
        """Raise unless this operator holds ``permission``."""
        if permission not in self.permissions:
            raise PopulationPermissionDenied(
                f"{self.actor_id} does not hold {permission.value}",
                reason="insufficient_population_permission",
            )


def require_operator(operator: object, permission: PopulationPermission) -> str:
    """Refuse anything but an issued operator context holding ``permission``.

    Returns the actor id to record. A ``StudyContext``, an ``OrganizationContext``,
    a principal or a plain string is refused by type, before any permission check.
    """
    if not isinstance(operator, PopulationOperatorContext):
        raise PopulationPermissionDenied(
            f"{type(operator).__name__} is not a population-operator context; "
            "study and organization scope confer no population permission",
            reason="not_an_operator_context",
        )
    operator.require(permission)
    return operator.actor_id
