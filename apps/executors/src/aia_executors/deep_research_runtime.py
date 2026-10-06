"""Deep Research's production composition: off by default, optionally public web.

======================================  ============================================
key                                     meaning
======================================  ============================================
AIA_DEEP_RESEARCH_ENABLED               ``true`` builds the runtime; unset or false,
                                        a Deep Research run parks at its plan step
                                        (``deep_research_unconfigured``)
AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED     ``true`` selects the bounded Czech Wikipedia
                                        Class C public route; false has no retrieval
AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS
                                        optional; unset or empty, the agents do not
                                        think. An integer >= 1024 and below
                                        ``AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS`` turns
                                        on extended thinking for the five agents
AIA_DEEP_RESEARCH_AGENT_DIRECTED        ``true`` runs web tracks as the agent-directed
                                        investigator's turns (plan chunk 9); unset or
                                        false, the planner's queries, as before
AIA_DEEP_RESEARCH_LEAD                  ``true`` has a lead researcher plan the
                                        agent-directed web research: subjects sized by
                                        effort, tasks in waves, re-plans (chunk 11);
                                        needs the agent-directed switch; unset or
                                        false, chunk 9's tracks, as before
AIA_DEEP_RESEARCH_FAN_OUT               ``true`` runs every track that makes a call in
                                        a step of its own, on any worker, with every
                                        host paced and model requests bounded across
                                        processes (chunk 21); unset or false, one step
                                        researches every track, as before
AIA_DEEP_RESEARCH_MODEL_CONCURRENCY     required with fan-out, refused without it: the
                                        model requests in flight across every worker
                                        on the route (1-256). Below the account's quota
                                        for the route's model; proposed 4, pending the
                                        quota request (plan chunk 1). No default
======================================  ============================================

Enabled, it needs the AI runtime with research agents (``AIA_AI_RUNTIME_ENABLED``
and ``AIA_AI_RESEARCH_AGENTS_ENABLED``, :mod:`aia_executors.ai_runtime`): its agents
name ``RESEARCH_REASONING`` and ``CRITIC``, the two capabilities bound only then, and
it uses their output limit and their per-request reservation (primary plus one
schema repair, checked there against the model's ceilings). The worker refuses to
start otherwise -- a switch that silently did nothing would be a guess.

Thinking is part of the output limit, as Claude counts it: thinking and answer
together stay within ``AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS``, so the per-request
reservation (checked against two calls at that limit) already covers it. With
thinking on, the output tool cannot be forced; the gateway offers it with
``auto``, tells the agent to answer through it, and repairs an answer in text
like any schema violation. No other agent thinks: the key is Deep Research's.

The lead switch binds ``RESEARCH_LEAD``, the lead's own policy entry, to the
route's model (``AIRuntimeSettings.research_lead_enabled``); off, nothing binds it and
nothing asks for it. Like the agent-directed switch, it changes who decides what to
research, not what may leave.

The fan-out switch changes where a track is researched, never what it finds: no
fingerprint, version or artifact depends on it. On, it needs ``DATABASE_URL`` (the
worker's own): a small engine of its own carries the shared host pacer and the model
slots (``infrastructure/fan_out_coordination.py``), outside any step's transaction. See
``docs/architecture/deep-research-fan-out.md``.

The agent-directed switch changes how a web track is researched, not what may
leave: every action still passes the retrieval gate, and with no retrieval
configured there is no web track to direct. Off (the default), every request,
fingerprint and count is the planned mode's.

Without the public switch, web tracks park without a search call. With it, public
queries may use Czech Wikipedia through a pinned-IP transport. Unknown or client
material stays blocked by the exact-content classification gate; internal Client
Knowledge remains outside this public Class C route. The worker registers all six
kinds, including when disabled, so a run has a visible parked state.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Mapping
from typing import Final

from aia_core.domain.ai_contracts import THINKING_MIN_BUDGET_TOKENS
from aia_core.domain.deep_research.reputation import REPUTATION_REGISTER_V1
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1
from aia_core.domain.providers import Provider
from aia_core.infrastructure.db import create_app_engine, create_session_factory, is_sqlite
from aia_core.infrastructure.fan_out_coordination import ModelSlots, SharedHostPacer
from aia_core.infrastructure.model_adapters import BedrockSigner
from aia_core.infrastructure.model_adapters.transport import HttpTransport
from sqlalchemy.orm import Session, sessionmaker

from .ai_runtime import AIRuntimeConfigError, AIRuntimeSettings, build_gateway
from .deep_research import DeepResearchConfig, DeepResearchRuntime
from .deep_research_live import wikipedia_retrieval

__all__ = [
    "AGENT_DIRECTED_KEY",
    "ENABLED_KEY",
    "FAN_OUT_KEY",
    "LEAD_KEY",
    "MODEL_CONCURRENCY_KEY",
    "THINKING_KEY",
    "agent_directed",
    "deep_research_enabled",
    "deep_research_runtime",
    "fan_out",
    "lead",
    "model_concurrency",
    "thinking_budget",
]

ENABLED_KEY: Final = "AIA_DEEP_RESEARCH_ENABLED"
WIKIPEDIA_KEY: Final = "AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED"
THINKING_KEY: Final = "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS"
AGENT_DIRECTED_KEY: Final = "AIA_DEEP_RESEARCH_AGENT_DIRECTED"
LEAD_KEY: Final = "AIA_DEEP_RESEARCH_LEAD"
FAN_OUT_KEY: Final = "AIA_DEEP_RESEARCH_FAN_OUT"
MODEL_CONCURRENCY_KEY: Final = "AIA_DEEP_RESEARCH_MODEL_CONCURRENCY"

_TRUE: Final = frozenset({"1", "true", "yes", "on"})
_FALSE: Final = frozenset({"0", "false", "no", "off", ""})


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


def _switch(env: Mapping[str, str] | None, key: str) -> bool:
    env = os.environ if env is None else env
    raw = env.get(key)
    if raw is None:
        return False
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise AIRuntimeConfigError(f"{key}={raw!r} is not true or false")


def agent_directed(env: Mapping[str, str] | None = None) -> bool:
    """The agent-directed switch, read strictly: ``true`` or ``false`` (or unset)."""
    return _switch(env, AGENT_DIRECTED_KEY)


def lead(env: Mapping[str, str] | None = None) -> bool:
    """The lead researcher's switch, read strictly: ``true`` or ``false`` (or unset)."""
    return _switch(env, LEAD_KEY)


def fan_out(env: Mapping[str, str] | None = None) -> bool:
    """The fan-out switch, read strictly: ``true`` or ``false`` (or unset)."""
    return _switch(env, FAN_OUT_KEY)


def model_concurrency(env: Mapping[str, str] | None = None) -> int | None:
    """Model requests in flight across the route, read strictly: unset is None; else 1-256.

    There is no default: the limit must sit below the account's quota, which only the
    operator knows (proposed 4, pending the quota request).
    """
    env = os.environ if env is None else env
    raw = (env.get(MODEL_CONCURRENCY_KEY) or "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise AIRuntimeConfigError(f"{MODEL_CONCURRENCY_KEY}={raw!r} is not a whole number")
    value = int(raw)
    if not 1 <= value <= 256:
        raise AIRuntimeConfigError(f"{MODEL_CONCURRENCY_KEY}={value} is not between 1 and 256")
    return value


def _coordination_sessions(env: Mapping[str, str]) -> sessionmaker[Session]:
    """The fan-out coordination's own engine, on the worker's database."""
    url = (env.get("DATABASE_URL") or "").strip()
    if not url:
        raise AIRuntimeConfigError(
            f"{FAN_OUT_KEY} needs DATABASE_URL: the host pacer and the model slots are "
            "shared through the worker's database"
        )
    if is_sqlite(url) and ":memory:" in url:
        raise AIRuntimeConfigError(
            f"{FAN_OUT_KEY} cannot share an in-memory database between processes"
        )
    return create_session_factory(create_app_engine(url, pool_size=2, max_overflow=4))


def thinking_budget(env: Mapping[str, str] | None = None) -> int | None:
    """The thinking budget, read strictly: unset or empty is none; else an integer >= 1024.

    Whether it fits the output limit is checked against the research agents' limit
    when the runtime is built.
    """
    env = os.environ if env is None else env
    raw = (env.get(THINKING_KEY) or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise AIRuntimeConfigError(f"{THINKING_KEY}={raw!r} is not an integer") from exc
    if value < THINKING_MIN_BUDGET_TOKENS:
        raise AIRuntimeConfigError(
            f"{THINKING_KEY}={value} is below the smallest budget, {THINKING_MIN_BUDGET_TOKENS}"
        )
    return value


def deep_research_runtime(
    settings: AIRuntimeSettings | None,
    *,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
    signer: BedrockSigner | None = None,
    coordination: sessionmaker[Session] | None = None,
) -> DeepResearchRuntime | None:
    """``None`` when Deep Research is off; the runtime when on; raise when it cannot be.

    ``coordination`` is the fan-out's session factory (a test's database); ``None``
    builds one from ``DATABASE_URL`` when the switch is on.
    """
    values = os.environ if env is None else env
    wiki = values.get(WIKIPEDIA_KEY, "false").strip().lower()
    if wiki not in {"1", "true", "yes", "on", "0", "false", "no", "off", ""}:
        raise AIRuntimeConfigError(f"{WIKIPEDIA_KEY}={wiki!r} is not true or false")
    use_wikipedia = wiki in {"1", "true", "yes", "on"}
    thinking = thinking_budget(values)
    directed = agent_directed(values)
    planned_by_lead = lead(values)
    fanned_out = fan_out(values)
    slots_limit = model_concurrency(values)
    if planned_by_lead and not directed:
        raise AIRuntimeConfigError(
            f"{LEAD_KEY} needs {AGENT_DIRECTED_KEY}: the lead plans agent-directed tracks"
        )
    if not deep_research_enabled(values):
        if use_wikipedia:
            raise AIRuntimeConfigError(f"{WIKIPEDIA_KEY} needs {ENABLED_KEY}")
        if thinking is not None:
            raise AIRuntimeConfigError(f"{THINKING_KEY} needs {ENABLED_KEY}")
        if planned_by_lead:
            raise AIRuntimeConfigError(f"{LEAD_KEY} needs {ENABLED_KEY}")
        if directed:
            raise AIRuntimeConfigError(f"{AGENT_DIRECTED_KEY} needs {ENABLED_KEY}")
        if fanned_out:
            raise AIRuntimeConfigError(f"{FAN_OUT_KEY} needs {ENABLED_KEY}")
        if slots_limit is not None:
            raise AIRuntimeConfigError(f"{MODEL_CONCURRENCY_KEY} needs {FAN_OUT_KEY}")
        return None
    if fanned_out and slots_limit is None:
        raise AIRuntimeConfigError(
            f"{FAN_OUT_KEY} needs {MODEL_CONCURRENCY_KEY}: the model requests in flight "
            "across every worker, below the account's quota (proposed 4); there is no default"
        )
    if slots_limit is not None and not fanned_out:
        raise AIRuntimeConfigError(f"{MODEL_CONCURRENCY_KEY} needs {FAN_OUT_KEY}")
    if settings is None or not settings.research_agents_enabled:
        raise AIRuntimeConfigError(
            f"{ENABLED_KEY} needs AIA_AI_RUNTIME_ENABLED and AIA_AI_RESEARCH_AGENTS_ENABLED: "
            "its agents are RESEARCH_REASONING and CRITIC, bound only with research agents"
        )
    if thinking is not None and thinking >= settings.research_max_output_tokens:
        raise AIRuntimeConfigError(
            f"{THINKING_KEY}={thinking} must be below AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS="
            f"{settings.research_max_output_tokens}: thinking is part of the output limit"
        )
    slots: ModelSlots | None = None
    pacer: SharedHostPacer | None = None
    if fanned_out:
        assert slots_limit is not None
        sessions = coordination or _coordination_sessions(values)
        slots = ModelSlots(sessions, pool=f"bedrock:{settings.route_id}", limit=slots_limit)
        pacer = SharedHostPacer(sessions)
    retrieval, table = (
        wikipedia_retrieval(pacer=pacer) if use_wikipedia else (None, SOURCE_TABLE_V1)
    )
    if planned_by_lead:
        settings = dataclasses.replace(settings, research_lead_enabled=True)
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
            thinking_budget_tokens=thinking,
            agent_directed=directed,
            lead=planned_by_lead,
            fan_out=fanned_out,
        ),
        retrieval=retrieval,
        source_table=table,
        # The proposed register names publishers for the agent-directed review only
        # (chunk 12); the planned mode never reads it.
        register=REPUTATION_REGISTER_V1 if directed else None,
        model_slots=slots,
    )
