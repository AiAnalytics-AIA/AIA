"""The population authority: the only issuer of a population-operator context.

Operators come from **trusted deployment configuration** -- a mapping of verified
user id to population permissions, read at the composition root -- never from a
request, a token claim or the database a tenant can write to. The authority
checks that the caller is an authenticated principal and that configuration names
them, and issues a :class:`PopulationOperatorContext` carrying exactly the
permissions configured. Nothing else can construct one
(``make layer_check`` refuses an issuance anywhere else).

Deliberately separate from ``ScopeResolver``: population operation is platform
administration, and neither a study grant nor an organization role implies it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from ..domain.population.authority import (
    PopulationOperatorContext,
    PopulationOperatorGrant,
    PopulationPermission,
    PopulationPermissionDenied,
)
from .scope import AuthenticatedPrincipal

__all__ = ["PopulationAuthority", "PopulationOperatorConfig"]


@dataclass(frozen=True, slots=True)
class PopulationOperatorConfig:
    """Who may operate the population: verified user id -> permissions.

    Built from typed configuration by the composition root. Empty -- the default
    -- means nobody may establish or promote, which is the correct state for any
    deployment that has not deliberately named an operator.
    """

    operators: Mapping[str, frozenset[PopulationPermission]] = field(default_factory=dict)

    @classmethod
    def from_names(cls, operators: Mapping[str, Iterable[str]]) -> PopulationOperatorConfig:
        """Parse ``{user_id: ["POPULATION_PROMOTE", ...]}``. An unknown name is an error."""
        parsed: dict[str, frozenset[PopulationPermission]] = {}
        for user_id, names in operators.items():
            if not user_id:
                raise ValueError("an operator needs a user id")
            parsed[user_id] = frozenset(PopulationPermission(n) for n in names)
        return cls(operators=parsed)


class PopulationAuthority:
    """Issues population-operator contexts to configured, authenticated users."""

    def __init__(self, config: PopulationOperatorConfig) -> None:
        self._config = config

    def operator_context(self, principal: AuthenticatedPrincipal) -> PopulationOperatorContext:
        """Issue a context for ``principal``, or refuse.

        Refused by type for anything that is not an authenticated principal -- a
        study or organization context included -- and refused for a principal the
        configuration does not name.
        """
        if not isinstance(principal, AuthenticatedPrincipal):
            raise PopulationPermissionDenied(
                f"{type(principal).__name__} is not an authenticated principal",
                reason="not_a_principal",
            )
        permissions = self._config.operators.get(principal.user_id)
        if not permissions:
            raise PopulationPermissionDenied(
                f"{principal.user_id} is not a configured population operator",
                reason="not_an_operator",
            )
        return PopulationOperatorContext(
            actor_id=principal.user_id,
            permissions=permissions,
            grant=PopulationOperatorGrant._issue(),
            request_id=principal.request_id,
        )
