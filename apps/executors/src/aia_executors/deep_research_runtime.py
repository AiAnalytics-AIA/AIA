"""Deep Research's production composition: off by default, optionally public web.

======================================  ============================================
key                                     meaning
======================================  ============================================
AIA_DEEP_RESEARCH_ENABLED               ``true`` builds the runtime; unset or false,
                                        a Deep Research run parks at its plan step
                                        (``deep_research_unconfigured``)
AIA_DEEP_RESEARCH_WEB_SEARCH            ``off``, ``wikipedia`` or ``brave``: the search
                                        route (plan chunk 23d). Unset, the Wikipedia
                                        switch below decides; both set is refused.
                                        ``brave`` needs the public fetch's contact and
                                        the three Brave keys below
AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED     ``true`` selects the bounded Czech Wikipedia
                                        Class C public route; false has no retrieval.
                                        Read when the key above is unset
AIA_DEEP_RESEARCH_BRAVE_API_KEY         Brave's subscription key, put in the
                                        environment by the deployment (SSM
                                        SecureString on develop); read at each call
                                        through its reference, never stored, logged
                                        or named in a route
AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000    Brave's price per 1,000 requests, in USD,
                                        above zero: what every search reserves
                                        (divided by 1,000) and is charged
AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF    the date that price was read (YYYY-MM-DD),
                                        not in the future
AIA_DEEP_RESEARCH_COMMON_CRAWL          ``true`` composes Common Crawl (plan chunk 23e):
                                        the URL index through Athena in us-east-1,
                                        priced at the workgroup's scan cutoff, and
                                        archived pages by byte range; outside the EU,
                                        Class C only, and the index needs its
                                        organization's sign-off. Needs a search route,
                                        the public fetch's contact and every key below
AIA_DEEP_RESEARCH_COMMON_CRAWL_*        WORKGROUP, DATABASE, TABLE, MAX_SCAN_BYTES (the
                                        workgroup's enforced cutoff), USD_PER_TB_SCANNED,
                                        MIN_BILLED_BYTES, BILLING_INCREMENT_BYTES,
                                        PRICES_AS_OF, and CRAWLS (comma-separated
                                        CC-MAIN-YYYY-WW ids the ladder's archive rung
                                        asks). Every one required; none has a default
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
AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT  one e-mail address: pages are then fetched from
                                        any public host, robots.txt obeyed, the address
                                        in every request's user agent (plan chunk 23b);
                                        needs the Wikipedia search. Unset: Wikipedia's
                                        pages only, as before
AIA_DEEP_RESEARCH_CONNECTORS            comma-separated: datastat, nkod, eurostat,
                                        openalex, ares, crossref, wayback -- the public
                                        dataset connectors the ladder may query
                                        (chunks 14-16, 23b); crossref and openalex are
                                        also what the merge asks whether a cited work
                                        was retracted (chunk 46); needs the public
                                        fetch's contact. Unset or empty: none
======================================  ============================================

Enabled, it needs the AI runtime with research agents (``AIA_AI_RUNTIME_ENABLED``
and ``AIA_AI_RESEARCH_AGENTS_ENABLED``, :mod:`aia_executors.ai_runtime`): its agents
name ``RESEARCH_REASONING`` and ``CRITIC``, the two capabilities bound only then, and
it uses their output limit as the most any request may write. The worker refuses to
start otherwise -- a switch that silently did nothing would be a guess.

Each kind of request has its own window, output limit and reservation (primary plus
one schema repair), derived from the route's prices, the model's window and that
output limit (``domain/deep_research/request_limits.py``); nothing about them is
configured, and ``AIA_AI_RESEARCH_RESERVATION_USD`` is the design jobs' alone. The API
prices a run's ceiling by the same rule from the same keys.

Thinking is part of the output limit, as Claude counts it: with thinking on, each
kind's answer limit gains the thinking budget, never beyond
``AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS``, and its reservation is sized on the sum. With
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
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Final

from aia_core.application.acquisition_ladder import LadderConfig
from aia_core.domain.ai_contracts import THINKING_MIN_BUDGET_TOKENS
from aia_core.domain.deep_research.common_crawl import MAX_CRAWLS_PER_QUERY
from aia_core.domain.deep_research.reputation import REPUTATION_REGISTER_V1
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1
from aia_core.domain.providers import Provider
from aia_core.infrastructure.common_crawl import CommonCrawlSettings, common_crawl_settings
from aia_core.infrastructure.db import create_app_engine, create_session_factory, is_sqlite
from aia_core.infrastructure.fan_out_coordination import ModelSlots, SharedHostPacer
from aia_core.infrastructure.model_adapters import BedrockSigner
from aia_core.infrastructure.model_adapters.transport import EnvironmentCredentials, HttpTransport
from aia_core.infrastructure.web_retrieval_brave import BRAVE_CREDENTIAL_REF
from aia_core.infrastructure.web_retrieval_live import public_user_agent
from sqlalchemy.orm import Session, sessionmaker

from .ai_runtime import AIRuntimeConfigError, AIRuntimeSettings, build_gateway
from .deep_research import DeepResearchConfig, DeepResearchRuntime
from .deep_research_live import (
    CONNECTORS,
    UNAVAILABLE_CONNECTORS,
    brave_retrieval,
    common_crawl_archive,
    connector_accesses,
    public_retrieval,
    wikipedia_retrieval,
)

__all__ = [
    "AGENT_DIRECTED_KEY",
    "BRAVE_AS_OF_KEY",
    "BRAVE_KEY",
    "BRAVE_PRICE_KEY",
    "COMMON_CRAWL_CRAWLS_KEY",
    "COMMON_CRAWL_KEY",
    "CONNECTORS_KEY",
    "ENABLED_KEY",
    "FAN_OUT_KEY",
    "LEAD_KEY",
    "MODEL_CONCURRENCY_KEY",
    "PUBLIC_FETCH_CONTACT_KEY",
    "THINKING_KEY",
    "WEB_SEARCH_KEY",
    "agent_directed",
    "brave_price_per_call",
    "common_crawl",
    "common_crawl_crawls",
    "connectors",
    "deep_research_enabled",
    "deep_research_runtime",
    "fan_out",
    "lead",
    "model_concurrency",
    "public_fetch_contact",
    "thinking_budget",
    "web_search",
]

ENABLED_KEY: Final = "AIA_DEEP_RESEARCH_ENABLED"
WIKIPEDIA_KEY: Final = "AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED"
THINKING_KEY: Final = "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS"
AGENT_DIRECTED_KEY: Final = "AIA_DEEP_RESEARCH_AGENT_DIRECTED"
LEAD_KEY: Final = "AIA_DEEP_RESEARCH_LEAD"
FAN_OUT_KEY: Final = "AIA_DEEP_RESEARCH_FAN_OUT"
MODEL_CONCURRENCY_KEY: Final = "AIA_DEEP_RESEARCH_MODEL_CONCURRENCY"
PUBLIC_FETCH_CONTACT_KEY: Final = "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT"
CONNECTORS_KEY: Final = "AIA_DEEP_RESEARCH_CONNECTORS"
WEB_SEARCH_KEY: Final = "AIA_DEEP_RESEARCH_WEB_SEARCH"
BRAVE_KEY: Final = "AIA_DEEP_RESEARCH_BRAVE_API_KEY"
BRAVE_PRICE_KEY: Final = "AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000"
BRAVE_AS_OF_KEY: Final = "AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF"
WEB_SEARCHES: Final = ("off", "wikipedia", "brave")
COMMON_CRAWL_KEY: Final = "AIA_DEEP_RESEARCH_COMMON_CRAWL"
COMMON_CRAWL_CRAWLS_KEY: Final = "AIA_DEEP_RESEARCH_COMMON_CRAWL_CRAWLS"
#: The most a price per 1,000 requests may say: a typo of a decimal point stops the worker.
MAX_BRAVE_USD_PER_1000: Final = 100.0

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


def public_fetch_contact(env: Mapping[str, str] | None = None) -> str | None:
    """The public fetch's contact address, read strictly: unset or empty is none."""
    env = os.environ if env is None else env
    raw = (env.get(PUBLIC_FETCH_CONTACT_KEY) or "").strip()
    if not raw:
        return None
    try:
        public_user_agent(raw)
    except ValueError as exc:
        raise AIRuntimeConfigError(
            f"{PUBLIC_FETCH_CONTACT_KEY} must be one plain e-mail address"
        ) from exc
    return raw


def connectors(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """The listed connectors, read strictly: names the composition knows, each once."""
    env = os.environ if env is None else env
    raw = (env.get(CONNECTORS_KEY) or "").split(",")
    names = tuple(n.strip().lower() for n in raw if n.strip())
    if len(names) != len(set(names)):
        raise AIRuntimeConfigError(f"{CONNECTORS_KEY} lists a connector twice")
    for name in names:
        if name in UNAVAILABLE_CONNECTORS:
            raise AIRuntimeConfigError(f"{CONNECTORS_KEY}: {name}: {UNAVAILABLE_CONNECTORS[name]}")
        if name not in CONNECTORS:
            raise AIRuntimeConfigError(
                f"{CONNECTORS_KEY}: {name!r} is not a connector ({', '.join(CONNECTORS)})"
            )
    return names


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


def web_search(env: Mapping[str, str] | None = None) -> str:
    """The search route the deployment names: ``off``, ``wikipedia`` or ``brave``."""
    env = os.environ if env is None else env
    named = (env.get(WEB_SEARCH_KEY) or "").strip().lower()
    wiki = (env.get(WIKIPEDIA_KEY) or "").strip().lower()
    if wiki not in _TRUE | _FALSE:
        raise AIRuntimeConfigError(f"{WIKIPEDIA_KEY}={wiki!r} is not true or false")
    if named:
        if named not in WEB_SEARCHES:
            raise AIRuntimeConfigError(
                f"{WEB_SEARCH_KEY}={named!r} is not one of {', '.join(WEB_SEARCHES)}"
            )
        if wiki in _TRUE:
            # ``false`` beside it is what a Compose file's default writes, and harmless.
            raise AIRuntimeConfigError(
                f"{WEB_SEARCH_KEY} replaces {WIKIPEDIA_KEY}: turn one of them on, not both"
            )
        return named
    return "wikipedia" if wiki in _TRUE else "off"


def brave_price_per_call(env: Mapping[str, str] | None = None) -> float:
    """Brave's dated price, per request: ``AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000`` / 1,000.

    Both price keys are required and checked; there is no default price. The key's
    presence is checked through its reference, and its value is not kept.
    """
    env = os.environ if env is None else env
    raw = (env.get(BRAVE_PRICE_KEY) or "").strip()
    try:
        per_1000 = float(raw)
    except ValueError:
        raise AIRuntimeConfigError(f"{BRAVE_PRICE_KEY}={raw!r} is not a price in USD") from None
    if not (0 < per_1000 <= MAX_BRAVE_USD_PER_1000) or per_1000 != per_1000:
        raise AIRuntimeConfigError(
            f"{BRAVE_PRICE_KEY}={raw!r} must be above 0 and at most {MAX_BRAVE_USD_PER_1000:g}"
        )
    as_of = (env.get(BRAVE_AS_OF_KEY) or "").strip()
    try:
        read_on = date.fromisoformat(as_of)
    except ValueError:
        raise AIRuntimeConfigError(
            f"{BRAVE_AS_OF_KEY}={as_of!r} is not a date (YYYY-MM-DD)"
        ) from None
    if read_on > datetime.now(UTC).date():
        raise AIRuntimeConfigError(f"{BRAVE_AS_OF_KEY}={as_of} is in the future")
    try:
        present = bool(EnvironmentCredentials(environ=env).secret(BRAVE_CREDENTIAL_REF).strip())
    except KeyError:
        present = False
    if not present:
        raise AIRuntimeConfigError(f"{WEB_SEARCH_KEY}=brave needs {BRAVE_KEY}")
    return per_1000 / 1000


def common_crawl(env: Mapping[str, str] | None = None) -> bool:
    """Whether the deployment composes Common Crawl (``AIA_DEEP_RESEARCH_COMMON_CRAWL``)."""
    return _switch(env, COMMON_CRAWL_KEY)


def common_crawl_crawls(env: Mapping[str, str]) -> tuple[str, ...]:
    """The crawls the ladder's archive rung asks: required, each a CC-MAIN-YYYY-WW id,
    none twice, at most as many as one index query may name."""
    raw = [c.strip() for c in (env.get(COMMON_CRAWL_CRAWLS_KEY) or "").split(",") if c.strip()]
    if not raw:
        raise AIRuntimeConfigError(f"{COMMON_CRAWL_CRAWLS_KEY} is required")
    bad = [c for c in raw if not re.fullmatch(r"CC-MAIN-\d{4}-\d{2}", c)]
    if bad:
        raise AIRuntimeConfigError(f"{COMMON_CRAWL_CRAWLS_KEY}: {bad[0]!r} is not CC-MAIN-YYYY-WW")
    if len(set(raw)) != len(raw):
        raise AIRuntimeConfigError(f"{COMMON_CRAWL_CRAWLS_KEY} names a crawl twice")
    if len(raw) > MAX_CRAWLS_PER_QUERY:
        raise AIRuntimeConfigError(
            f"{COMMON_CRAWL_CRAWLS_KEY} names at most {MAX_CRAWLS_PER_QUERY} crawls"
        )
    return tuple(raw)


def _common_crawl_settings(env: Mapping[str, str]) -> CommonCrawlSettings:
    try:
        settings = common_crawl_settings(env)
    except ValueError as exc:
        raise AIRuntimeConfigError(str(exc)) from None
    if settings.prices_as_of > datetime.now(UTC).date():
        raise AIRuntimeConfigError(
            f"AIA_DEEP_RESEARCH_COMMON_CRAWL_PRICES_AS_OF={settings.prices_as_of} is in the future"
        )
    return settings


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
    search = web_search(values)
    has_search = search != "off"  # a search route the public fetch rides beside
    thinking = thinking_budget(values)
    directed = agent_directed(values)
    planned_by_lead = lead(values)
    fanned_out = fan_out(values)
    slots_limit = model_concurrency(values)
    contact = public_fetch_contact(values)
    listed = connectors(values)
    if contact is not None and not has_search:
        raise AIRuntimeConfigError(
            f"{PUBLIC_FETCH_CONTACT_KEY} needs {WIKIPEDIA_KEY} or {WEB_SEARCH_KEY}: pages "
            "are fetched beside a search route"
        )
    if listed and contact is None:
        raise AIRuntimeConfigError(
            f"{CONNECTORS_KEY} needs {PUBLIC_FETCH_CONTACT_KEY}: a connector rides beside the "
            "public fetch, and OpenAlex's polite pool is asked with the same contact"
        )
    if planned_by_lead and not directed:
        raise AIRuntimeConfigError(
            f"{LEAD_KEY} needs {AGENT_DIRECTED_KEY}: the lead plans agent-directed tracks"
        )
    crawl = common_crawl(values)
    if crawl and (not has_search or contact is None):
        raise AIRuntimeConfigError(
            f"{COMMON_CRAWL_KEY} needs a search route and {PUBLIC_FETCH_CONTACT_KEY}: the "
            "archive answers a page the public fetch found dead or moved"
        )
    if search == "brave" and contact is None:
        raise AIRuntimeConfigError(
            f"{WEB_SEARCH_KEY}=brave needs {PUBLIC_FETCH_CONTACT_KEY}: Brave's results are "
            "pages on any public host, fetched by the public fetch"
        )
    if not deep_research_enabled(values):
        if has_search:
            raise AIRuntimeConfigError(
                f"{WEB_SEARCH_KEY if values.get(WEB_SEARCH_KEY) else WIKIPEDIA_KEY} "
                f"needs {ENABLED_KEY}"
            )
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
    if not has_search:
        retrieval, table = None, SOURCE_TABLE_V1
    elif search == "brave":
        assert contact is not None
        retrieval, table = brave_retrieval(
            contact,
            price_usd_per_call=brave_price_per_call(values),
            credentials=EnvironmentCredentials(environ=values),
            pacer=pacer,
        )
    elif contact is not None:
        retrieval, table = public_retrieval(contact, pacer=pacer)
    else:
        retrieval, table = wikipedia_retrieval(pacer=pacer)
    datasets, archives = (
        connector_accesses(listed, contact=contact, pacer=pacer)
        if listed and contact is not None
        else ((), ())
    )
    archive = crawls = None
    if crawl:
        assert contact is not None
        crawls = common_crawl_crawls(values)
        archive = common_crawl_archive(_common_crawl_settings(values), contact=contact)
    if planned_by_lead:
        settings = dataclasses.replace(settings, research_lead_enabled=True)
    return DeepResearchRuntime(
        gateway=build_gateway(settings, transport=transport, signer=signer),
        config=DeepResearchConfig(
            policy_version=settings.policy_version,
            max_output_tokens=settings.research_max_output_tokens,
            context_window_tokens=settings.context_window_tokens,
            prices=settings.model_prices(),
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
        datasets=datasets,
        archives=archives,
        # The ladder resolves publishers by the register only where it can then reach
        # them (chunk 23b); without the public fetch it keeps its defaults, and every
        # fingerprint is the one it had before.
        ladder=(
            LadderConfig(register=REPUTATION_REGISTER_V1, crawls=crawls or ())
            if contact is not None
            else None
        ),
        archive=archive,
    )
