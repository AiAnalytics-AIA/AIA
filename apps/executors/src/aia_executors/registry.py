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

import os
from collections.abc import Mapping
from typing import Final

from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.population_source import FilesystemPopulationSource
from aia_core.infrastructure.population_store import PopulationStoreSettings, S3PopulationStore
from aia_core.infrastructure.report_pdf import PdfConverter, report_pdf_from_env
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.storage_settings import StorageSettings, build_artifact_store
from aia_worker.executor import StepExecutor

from .ai_fieldwork import AIFieldwork
from .ai_runtime import AIRuntimeSettings, build_ai_fieldwork, build_gateway
from .analysis import AnalysisConfig, analysis_registry
from .deep_research import DeepResearchRuntime, deep_research_registry
from .deep_research_runtime import deep_research_runtime
from .materialize import KIND as MATERIALIZE_KIND
from .materialize import MaterializeExecutor
from .report import report_registry
from .research import AIDatasetProducer, research_registry
from .research_agents import ResearchAgentConfig, ResearchAgentExecutor
from .snapshot import KIND as SNAPSHOT_KIND
from .snapshot import SnapshotExecutor
from .sociomapping_report import sociomapping_report_registry
from .validation import validation_registry

__all__ = [
    "POPULATION_ASSET_ROOT_KEY",
    "SOCIOMAP_CONNECTEDNESS_INTERVAL_KEY",
    "build_registry",
    "materialize_executor",
    "population_store",
    "registry_for",
    "sociomap_connectedness_interval",
]

SOCIOMAP_CONNECTEDNESS_INTERVAL_KEY: Final = "AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED"
_TRUE: Final = {"1", "true", "yes", "on"}
_FALSE: Final = {"0", "false", "no", "off", ""}


def sociomap_connectedness_interval(env: Mapping[str, str]) -> bool:
    """Whether the sociomap step runs F9's respondent bootstrap (off when unset).

    It is 500 resamples per battery -- about 90 s for 1,500 respondents x 22 objects --
    so it ships behind a switch (CLAUDE.md § 8). A value that is not true or false
    stops the worker rather than being read as either.
    """
    raw = env.get(SOCIOMAP_CONNECTEDNESS_INTERVAL_KEY)
    value = (raw or "").strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"{SOCIOMAP_CONNECTEDNESS_INTERVAL_KEY}={raw!r} is not true or false")


def registry_for(
    *,
    store: ArtifactStore,
    build: BuildIdentity,
    ai_runtime: AIDatasetProducer | None = None,
    research_agent: StepExecutor | None = None,
    analysis: StepExecutor | None = None,
    deep_research: DeepResearchRuntime | None = None,
    sociomap_connectedness_interval: bool = False,
    materialize: StepExecutor | None = None,
    report_pdf: PdfConverter | None = None,
) -> dict[str, StepExecutor]:
    """Step kind -> executor, over explicit collaborators. Tests use this."""
    return {
        # Without a store and the shared population it parks (population-operations P4d3).
        MATERIALIZE_KIND: materialize or MaterializeExecutor(store=None, shared=None),
        "research_agent": research_agent or ResearchAgentExecutor(store=store, build=build),
        **(
            analysis_registry(store=store, build=build)
            if analysis is None
            else {"research_analysis": analysis}
        ),
        **deep_research_registry(store=store, build=build, runtime=deep_research),
        SNAPSHOT_KIND: SnapshotExecutor(store=store, build=build),
        **report_registry(store=store, build=build, pdf=report_pdf),
        **sociomapping_report_registry(store=store, build=build),
        **research_registry(
            store=store,
            build=build,
            ai_runtime=ai_runtime,
            sociomap_connectedness_interval=sociomap_connectedness_interval,
        ),
        # The validation's sample and arms answer through the same fieldwork; without it (or
        # its panel path) they park (panel-grounded-respondents 7e4).
        **validation_registry(
            store=store,
            build=build,
            ai=ai_runtime if isinstance(ai_runtime, AIFieldwork) else None,
        ),
    }


#: The read-only directory of the shared population's files (deploy/develop: /srv/population/v17).
POPULATION_ASSET_ROOT_KEY: Final = "AIA_POPULATION_ASSET_ROOT"


def population_store(env: Mapping[str, str]) -> S3PopulationStore | None:
    """The population store, when configured; a store configured by halves stops the worker."""
    settings = PopulationStoreSettings.from_env(env)
    return settings.build() if settings is not None else None


def materialize_executor(
    env: Mapping[str, str], *, store: S3PopulationStore | None = None
) -> MaterializeExecutor:
    """The materialize step over the configured store and shared population, if both are set.

    Either missing, the executor parks every materialize run (``RUNTIME_UNAVAILABLE``); a store
    configured by halves stops the worker (``PopulationStoreSettings.from_env``). ``store``
    passes the one the composition already built.
    """
    root = (env.get(POPULATION_ASSET_ROOT_KEY) or "").strip()
    return MaterializeExecutor(
        store=store if store is not None else population_store(env),
        shared=FilesystemPopulationSource(root) if root else None,
    )


def build_registry() -> dict[str, StepExecutor]:
    """The factory named by ``AIA_WORKER_EXECUTORS``; reads the environment."""
    build = BuildIdentity.from_env()
    connectedness_interval = sociomap_connectedness_interval(os.environ)
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
                step_events=settings.step_events,
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
    children = population_store(os.environ)
    return registry_for(
        store=store,
        materialize=materialize_executor(os.environ, store=children),
        research_agent=agent,
        analysis=analysis,
        deep_research=deep_research_runtime(settings),
        build=build,
        ai_runtime=(
            build_ai_fieldwork(settings, build=build, population_store=children)
            if settings is not None
            else None
        ),
        sociomap_connectedness_interval=connectedness_interval,
        report_pdf=report_pdf_from_env(os.environ),
    )
