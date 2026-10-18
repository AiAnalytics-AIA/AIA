"""The infrastructure errors a route catches, re-exported for the HTTP layer.

A router may not import ``aia_core.infrastructure`` (the import contract "routers
reach infrastructure only through the application layer", pyproject.toml). The
repositories it is handed by the composition root (``aia_api.dependencies``) raise
their own errors, and a router that only needs to *catch* one imports it from here.
The class is the same object, so an ``except`` here matches what the repository
raises; nothing is wrapped or translated.
"""

from __future__ import annotations

from ..infrastructure.repositories import ProjectNotFound
from ..infrastructure.workflow_repository import BudgetWaitNotLiftable, RuntimeParkNotResumable

__all__ = ["BudgetWaitNotLiftable", "ProjectNotFound", "RuntimeParkNotResumable"]
