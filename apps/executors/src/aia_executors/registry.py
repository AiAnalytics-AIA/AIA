"""The executor registry the worker loads: ``aia_executors.registry:build_registry``.

This is the executors' composition root: the one place the process environment
is read into an artifact store and a build identity, both shared by every
executor in the process. The worker itself never sees either.

It is the **production** composition. The research fieldwork step gets no
deterministic dataset producer, ever; it gets the AI respondent engine only when
``AIA_AI_RUNTIME_ENABLED`` is set and every AI runtime key is valid
(:class:`~aia_executors.ai_runtime.AIRuntimeSettings`, which refuses to start the
worker otherwise). Unconfigured, a research run parks at fieldwork (ADR 0016 D1).
The fictional synthetic source is only in ``aia_executors.workbench``, which
``make layer_check`` keeps this module from importing.
"""

from __future__ import annotations

from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.storage_settings import StorageSettings, build_artifact_store
from aia_worker.executor import StepExecutor

from .ai_runtime import AIRuntimeSettings, build_ai_fieldwork
from .research import AIDatasetProducer, research_registry
from .snapshot import KIND as SNAPSHOT_KIND
from .snapshot import SnapshotExecutor

__all__ = ["build_registry", "registry_for"]


def registry_for(
    *,
    store: ArtifactStore,
    build: BuildIdentity,
    ai_runtime: AIDatasetProducer | None = None,
) -> dict[str, StepExecutor]:
    """Step kind -> executor, over explicit collaborators. Tests use this."""
    return {
        SNAPSHOT_KIND: SnapshotExecutor(store=store, build=build),
        **research_registry(store=store, build=build, ai_runtime=ai_runtime),
    }


def build_registry() -> dict[str, StepExecutor]:
    """The factory named by ``AIA_WORKER_EXECUTORS``; reads the environment."""
    build = BuildIdentity.from_env()
    settings = AIRuntimeSettings.from_env()
    return registry_for(
        store=build_artifact_store(StorageSettings.from_env()),
        build=build,
        ai_runtime=build_ai_fieldwork(settings, build=build) if settings is not None else None,
    )
