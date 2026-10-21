"""LOCAL AND TEST ONLY: the production registry with the panel path reading the population double.

``AIA_WORKER_EXECUTORS=aia_executors.population_double:build_registry`` composes exactly what
``aia_executors.registry:build_registry`` composes, from the same environment, with one change:
a run that pinned respondents from its population is answered from the fictional population
double (``aia_core.application.population_double``) instead of the Czech v17 bundle under
``AIA_POPULATION_ASSET_ROOT``. The API composes the same double behind ``AIA_POPULATION_DOUBLE``,
so a run started over HTTP records the double's LIVE and this worker loads it through the
canonical loader from the same deterministic bytes (plan ``run-qc-and-checkpoint`` RQC10, for
tier A of the acceptance harness and AC-05).

Nothing else changes: fieldwork still needs the AI runtime and
``AIA_AI_POPULATION_PERSONAS_ENABLED`` (which, as in production, wants
``AIA_POPULATION_ASSET_ROOT`` set; the double replaces what it would read), the gateway's gates
still decide, and a panel request is still Class A. Without the AI runtime a run parks at
fieldwork exactly as it does in production.

It refuses to build unless ``AIA_ENV`` is ``local`` or ``test`` (unset refuses): a deployed
worker pointed at it fails at start, before claiming anything. ``make layer_check`` keeps every
other module from importing it and every deployment from naming it.
"""

from __future__ import annotations

import os

from aia_core.application.population_double import population_double
from aia_core.domain.deployment import parse_environment
from aia_worker.executor import StepExecutor

from .registry import build_registry as production_registry

__all__ = ["build_registry"]


def build_registry() -> dict[str, StepExecutor]:
    """The factory for ``AIA_WORKER_EXECUTORS``; refuses outside local and test."""
    double = population_double(parse_environment(os.environ.get("AIA_ENV")))
    return production_registry(population=double.loader())
