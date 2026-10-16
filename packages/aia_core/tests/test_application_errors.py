"""The errors a router catches are the repositories' own classes, not copies.

``aia_core.application.errors`` exists so a router can catch an infrastructure
error without importing infrastructure (the ratchet contract in pyproject.toml).
If it ever wrapped or redefined one, an ``except`` in the router would stop
matching what the repository raises and a 404 would become a 500.
"""

from __future__ import annotations

from aia_core.application import errors
from aia_core.infrastructure import repositories


def test_project_not_found_is_the_repositorys_own_class() -> None:
    assert errors.ProjectNotFound is repositories.ProjectNotFound


def test_every_re_export_is_an_infrastructure_object() -> None:
    for name in errors.__all__:
        assert getattr(errors, name).__module__.startswith("aia_core.infrastructure.")
