"""The acceptance harness's worker: ``aia_executors.acceptance_recorded:build_registry``.

Tier A of ``MVP-ACCEPT-2`` (``docs/migration/mvp-acceptance.md`` §2) runs the production stack
over HTTP with recorded, deterministic providers **behind** the gateway and the retrieval gate.
This is that worker's composition: the production one (:func:`registry.compose_registry`, the
same settings, executors, gateway, reservations, ledger and gates), with one change -- the model
wire is :class:`~aia_executors.recorded_models.RecordedModels` and its signer, so every model
request is answered by a recording and nothing leaves the process or is paid.

It refuses to build unless ``AIA_ENV`` is ``local`` or ``test`` (unset refuses), and no
deployment may name it (``make layer_check``): a recorded answer can never stand in for a model.
Deep Research is refused here until its recorded composition joins it (plan
``mvp-acceptance-harness`` chunk 4): its search and fetch would otherwise be the live routes.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final

from aia_worker.executor import StepExecutor

from .deep_research_runtime import ENABLED_KEY as DEEP_RESEARCH_KEY
from .recorded_models import RecordedModels, RecordedSigner
from .registry import compose_registry

__all__ = ["ALLOWED_ENVIRONMENTS", "build_registry", "refuse_outside_tests"]

#: Where recorded models may answer. Anything else refuses at start.
ALLOWED_ENVIRONMENTS: Final = frozenset({"local", "test"})
_TRUE: Final = {"1", "true", "yes", "on"}


def refuse_outside_tests(env: Mapping[str, str]) -> None:
    """Raise unless this process is a local or test one, and Deep Research is off."""
    environment = (env.get("AIA_ENV") or "").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            "aia_executors.acceptance_recorded answers model requests from recordings and "
            f"refuses AIA_ENV={environment!r}; no deployment composes it"
        )
    if (env.get(DEEP_RESEARCH_KEY) or "").strip().lower() in _TRUE:
        raise RuntimeError(
            "aia_executors.acceptance_recorded has no recorded web retrieval yet; "
            f"{DEEP_RESEARCH_KEY} would compose the live search routes beside recorded models"
        )


def build_registry() -> dict[str, StepExecutor]:
    """The factory ``AIA_WORKER_EXECUTORS`` names; reads the environment like production's."""
    refuse_outside_tests(os.environ)
    return compose_registry(transport=RecordedModels(), signer=RecordedSigner())
