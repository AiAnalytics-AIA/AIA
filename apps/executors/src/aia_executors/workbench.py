"""The test and workbench composition: production's executors plus fictional fieldwork.

``AIA_WORKER_EXECUTORS=aia_executors.workbench:build_registry`` gives the research
fieldwork step one dataset producer, the fictional synthetic source (ADR 0016
D1), so the chain after fieldwork -- aggregation, the Sociomap, the results
screens -- can be proven on this machine and in tests. Nothing it produces is
fieldwork; every dataset and every artifact computed from one carries
``data_origin = SYNTHETIC_FIXTURE``.

It refuses to build unless ``AIA_ENV`` is ``local`` or ``test`` (unset refuses): a deployed worker
pointed at it fails at start, before claiming anything. That is the worker's half
of the refusal; the API refuses the setting on staging and production, and the
production registry never provides the source.
"""

from __future__ import annotations

import os
from typing import Final

from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.synthetic_fieldwork import synthetic_dataset
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.storage_settings import StorageSettings, build_artifact_store
from aia_worker.executor import StepExecutor

from .registry import registry_for
from .research import research_registry

__all__ = ["ALLOWED_ENVIRONMENTS", "SYNTHETIC_SEED", "build_registry", "workbench_registry_for"]

#: Where the fictional source may exist. Anything else refuses at start.
ALLOWED_ENVIRONMENTS: Final = frozenset({"local", "test"})

#: One fixed seed: the same design gives the same fictional dataset every time.
SYNTHETIC_SEED: Final = 20260816


def workbench_registry_for(
    *, store: ArtifactStore, build: BuildIdentity
) -> dict[str, StepExecutor]:
    """Production's registry with the fictional fieldwork source added. Tests use this."""
    return {
        **registry_for(store=store, build=build),
        **research_registry(
            store=store,
            build=build,
            producers={
                FieldworkSource.SYNTHETIC_FIXTURE: lambda spec: synthetic_dataset(
                    spec, seed=SYNTHETIC_SEED
                )
            },
        ),
    }


def build_registry() -> dict[str, StepExecutor]:
    """The factory for ``AIA_WORKER_EXECUTORS``; refuses outside local and test."""
    env = os.environ.get("AIA_ENV", "").strip().lower()
    if env not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            f"aia_executors.workbench provides fictional fieldwork and refuses AIA_ENV={env!r}; "
            "a deployed worker uses aia_executors.registry:build_registry (ADR 0016)"
        )
    return workbench_registry_for(
        store=build_artifact_store(StorageSettings.from_env()),
        build=BuildIdentity.from_env(),
    )
