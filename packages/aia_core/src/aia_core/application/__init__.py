"""Application layer: use cases that orchestrate domain rules and infrastructure.

This layer owns authorization. ``scope.ScopeResolver`` is the only code that can
issue a ``StudyContext``, which every repository touching client data requires.
"""

from .scope import AuthenticatedPrincipal, ScopeResolver

__all__ = ["AuthenticatedPrincipal", "ScopeResolver"]
