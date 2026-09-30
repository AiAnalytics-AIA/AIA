"""Deep Research's production composition: off by default, optionally public web.

======================================  ============================================
key                                     meaning
======================================  ============================================
AIA_DEEP_RESEARCH_ENABLED               ``true`` builds the runtime; unset or false,
                                        a Deep Research run parks at its plan step
                                        (``deep_research_unconfigured``)
AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED     ``true`` selects the bounded Czech Wikipedia
                                        Class C public route; false has no retrieval
======================================  ============================================

Enabled, it needs the AI runtime with research agents (``AIA_AI_RUNTIME_ENABLED``
and ``AIA_AI_RESEARCH_AGENTS_ENABLED``, :mod:`aia_executors.ai_runtime`): its agents
name ``RESEARCH_REASONING`` and ``CRITIC``, the two capabilities bound only then, and
it uses their output limit and their per-request reservation (primary plus one
schema repair, checked there against the model's ceilings). The worker refuses to
start otherwise -- a switch that silently did nothing would be a guess.

Without the public switch, web tracks park without a search call. With it, public
queries may use Czech Wikipedia through a pinned-IP transport. Unknown or client
material stays blocked by the exact-content classification gate; internal Client
Knowledge remains outside this public Class C route. The worker registers all six
kinds, including when disabled, so a run has a visible parked state.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final

from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1
from aia_core.domain.providers import Provider
from aia_core.infrastructure.model_adapters import BedrockSigner
from aia_core.infrastructure.model_adapters.transport import HttpTransport

from .ai_runtime import AIRuntimeConfigError, AIRuntimeSettings, build_gateway
from .deep_research import DeepResearchConfig, DeepResearchRuntime
from .deep_research_live import wikipedia_retrieval

__all__ = ["ENABLED_KEY", "deep_research_enabled", "deep_research_runtime"]

ENABLED_KEY: Final = "AIA_DEEP_RESEARCH_ENABLED"
WIKIPEDIA_KEY: Final = "AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED"


def deep_research_enabled(env: Mapping[str, str] | None = None) -> bool:
    """The switch, read strictly: ``true`` or ``false`` (or unset), nothing else."""
    env = os.environ if env is None else env
    raw = env.get(ENABLED_KEY)
    if raw is None:
        return False
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    raise AIRuntimeConfigError(f"{ENABLED_KEY}={raw!r} is not true or false")


def deep_research_runtime(
    settings: AIRuntimeSettings | None,
    *,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
    signer: BedrockSigner | None = None,
) -> DeepResearchRuntime | None:
    """``None`` when Deep Research is off; the runtime when on; raise when it cannot be."""
    values = os.environ if env is None else env
    wiki = values.get(WIKIPEDIA_KEY, "false").strip().lower()
    if wiki not in {"1", "true", "yes", "on", "0", "false", "no", "off", ""}:
        raise AIRuntimeConfigError(f"{WIKIPEDIA_KEY}={wiki!r} is not true or false")
    use_wikipedia = wiki in {"1", "true", "yes", "on"}
    if not deep_research_enabled(values):
        if use_wikipedia:
            raise AIRuntimeConfigError(f"{WIKIPEDIA_KEY} needs {ENABLED_KEY}")
        return None
    if settings is None or not settings.research_agents_enabled:
        raise AIRuntimeConfigError(
            f"{ENABLED_KEY} needs AIA_AI_RUNTIME_ENABLED and AIA_AI_RESEARCH_AGENTS_ENABLED: "
            "its agents are RESEARCH_REASONING and CRITIC, bound only with research agents"
        )
    retrieval, table = wikipedia_retrieval() if use_wikipedia else (None, SOURCE_TABLE_V1)
    return DeepResearchRuntime(
        gateway=build_gateway(settings, transport=transport, signer=signer),
        config=DeepResearchConfig(
            policy_version=settings.policy_version,
            max_output_tokens=settings.research_max_output_tokens,
            context_window_tokens=settings.context_window_tokens,
            reservation_usd=settings.research_reservation_usd,
            fictional_client_ids=settings.fictional_client_ids,
            provider=Provider.AWS_BEDROCK,
            material_approvals=settings.material_approvals,
        ),
        retrieval=retrieval,
        source_table=table,
    )
