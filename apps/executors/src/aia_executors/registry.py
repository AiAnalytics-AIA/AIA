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

from .ai_runtime import AIRuntimeSettings, build_ai_fieldwork, build_gateway
from .analysis import AnalysisConfig, analysis_registry
from .deep_research import DeepResearchRuntime, deep_research_registry
from .deep_research_runtime import deep_research_runtime
from .research import AIDatasetProducer, research_registry
from .research_agents import ResearchAgentConfig, ResearchAgentExecutor
from .snapshot import KIND as SNAPSHOT_KIND
from .snapshot import SnapshotExecutor

__all__ = ["build_registry", "registry_for"]


def registry_for(
    *,
    store: ArtifactStore,
    build: BuildIdentity,
    ai_runtime: AIDatasetProducer | None = None,
    research_agent: StepExecutor | None = None,
    analysis: StepExecutor | None = None,
    deep_research: DeepResearchRuntime | None = None,
) -> dict[str, StepExecutor]:
    """Step kind -> executor, over explicit collaborators. Tests use this."""
    return {
        "research_agent": research_agent or ResearchAgentExecutor(store=store, build=build),
        **(
            analysis_registry(store=store, build=build)
            if analysis is None
            else {"research_analysis": analysis}
        ),
        **deep_research_registry(store=store, build=build, runtime=deep_research),
        SNAPSHOT_KIND: SnapshotExecutor(store=store, build=build),
        **research_registry(store=store, build=build, ai_runtime=ai_runtime),
    }


def build_registry() -> dict[str, StepExecutor]:
    """The factory named by ``AIA_WORKER_EXECUTORS``; reads the environment."""
    build = BuildIdentity.from_env()
    settings = AIRuntimeSettings.from_env()
    store = build_artifact_store(StorageSettings.from_env())
    agent = None
    if settings is not None and settings.research_agents_enabled:
        agent = ResearchAgentExecutor(
            store=store,
            build=build,
            gateway=build_gateway(settings),
            config=ResearchAgentConfig(
                policy_version=settings.policy_version,
                max_output_tokens=settings.research_max_output_tokens,
                context_window_tokens=settings.context_window_tokens,
                reservation_usd=settings.research_reservation_usd,
                fictional_client_ids=settings.fictional_client_ids,
                material_approvals=settings.material_approvals,
            ),
        )
    analysis = None
    if settings is not None and settings.analysis_enabled:
        config = AnalysisConfig.from_settings(
            settings,
            max_output_tokens=settings.analysis_max_output_tokens,
            reservation_usd=settings.analysis_reservation_usd,
        )
        analysis = analysis_registry(
            store=store, build=build, gateway=build_gateway(settings), config=config
        )["research_analysis"]
    return registry_for(
        store=store,
        research_agent=agent,
        analysis=analysis,
        deep_research=deep_research_runtime(settings),
        build=build,
        ai_runtime=build_ai_fieldwork(settings, build=build) if settings is not None else None,
    )
