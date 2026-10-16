"""Loading the executor registry from configuration.

The worker never imports an executor by name. ``AIA_WORKER_EXECUTORS`` names a
factory -- ``package.module:callable`` -- that returns a mapping of step kind to
executor, and that factory is where an AI runtime or research implementation plugs
in. The worker's own code stays free of anything domain-specific, which
``tools/layer_check.sh`` enforces.

The import is by name, so no lint rule sees what it loads. Outside local and test
the factory must come from ``aia_executors``, the package the import contracts and
the egress ban cover; anything else is refused before it is imported.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, cast

from .executor import ExecutorRegistry, StepExecutor

__all__ = ["EXECUTOR_PACKAGE", "load_executors"]

#: The package every deployed worker's executor factory comes from.
EXECUTOR_PACKAGE = "aia_executors"


def load_executors(spec: str, *, any_package: bool = False) -> dict[str, StepExecutor]:
    """Import ``module:factory``, call it, and validate what it returns.

    Fails loudly at startup on anything unusable -- an empty registry, a blank
    kind, an object without ``execute`` -- because a worker that starts with a
    broken registry claims steps it then fails. Unless ``any_package`` (local and
    test only), a module outside :data:`EXECUTOR_PACKAGE` is refused unimported.
    """
    module_name, _, attribute = spec.partition(":")
    if not module_name or not attribute:
        raise ValueError(f"executor factory must be 'package.module:callable', got {spec!r}")
    if not any_package and not module_name.startswith(EXECUTOR_PACKAGE + "."):
        raise ValueError(
            f"executor factory {spec!r} is outside {EXECUTOR_PACKAGE}; "
            "only AIA_ENV=local or test may name another package"
        )

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
