"""The executor registry the worker loads: ``aia_executors.registry:build_registry``.

Populated in the vertical-slice chunk; until then it registers nothing, which
``aia_worker.registry.load_executors`` refuses at start-up -- a worker with no
executors would claim nothing and report healthy.
"""

from __future__ import annotations

from aia_worker.executor import StepExecutor

__all__ = ["build_registry"]


def build_registry() -> dict[str, StepExecutor]:
    """Step kind -> executor, built from the process environment."""
    return {}
