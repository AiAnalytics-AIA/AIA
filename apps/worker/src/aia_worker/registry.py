"""Loading the executor registry from configuration.

The worker never imports an executor by name. ``AIA_WORKER_EXECUTORS`` names a
factory -- ``package.module:callable`` -- that returns a mapping of step kind to
executor, and that factory is where an AI runtime or research implementation plugs
in. The worker's own code stays free of anything domain-specific, which
``tools/layer_check.sh`` enforces.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, cast

from .executor import ExecutorRegistry, StepExecutor

__all__ = ["load_executors"]


def load_executors(spec: str) -> dict[str, StepExecutor]:
    """Import ``module:factory``, call it, and validate what it returns.

    Fails loudly at startup on anything unusable -- an empty registry, a blank
    kind, an object without ``execute`` -- because a worker that starts with a
    broken registry claims steps it then fails.
    """
    module_name, _, attribute = spec.partition(":")
    if not module_name or not attribute:
        raise ValueError(f"executor factory must be 'package.module:callable', got {spec!r}")

    module = importlib.import_module(module_name)
    factory = getattr(module, attribute, None)
    if not callable(factory):
        raise ValueError(f"{spec!r} is not callable")

    registry = cast(Callable[[], Any], factory)()
    if not isinstance(registry, dict) or not registry:
        raise ValueError(f"{spec!r} must return a non-empty dict of kind -> executor")

    checked: dict[str, StepExecutor] = {}
    for kind, executor in cast(ExecutorRegistry, registry).items():
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError(f"{spec!r} returned a blank or non-string step kind")
        if not isinstance(executor, StepExecutor):
            raise ValueError(f"executor for {kind!r} has no execute(step, context) method")
        checked[kind] = executor
    return checked
