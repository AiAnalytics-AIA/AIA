"""The MVP's activation profile (mvp-master-plan MP6, §4): each switch the MVP needs, judged
READY or NOT_READY from the deployed configuration, without a call.

``deploy/develop/bin/smoke.sh`` runs :mod:`aia_executors.smoke` as a one-off container of the
``worker`` service: the same image and the same environment the running worker was given. Each
row reads that environment through the parsers the worker itself starts with
(:meth:`AIRuntimeSettings.from_env`, the Deep Research switches, ``report_pdf_from_env``), so a
row says what the composition is configured to do. Nothing here builds a gateway, a transport or
a session, and nothing calls a model or a route (execution contract E05): a live probe runs only
after the owner's sign-off and a named allocation line, never on a deploy. That the configuration
composes at all is the smoke's "worker: started" check, since the worker refuses to start on a
configuration it cannot compose.

A row whose material the route refuses by class (a design is Class B by rule, approved knowledge
and panel personas Class A) reads NOT_READY, as every such request would park; under develop's
advisory gates it passes as a recorded advisory, and the reason says so.

A NOT_READY row is said, kept for Settings → Stav systému with its reason, and never fails the
deploy: a switch nobody threw is a fact about the product, not about the deployment.

Two rows of §4 are not deployment switches, and the smoke does not judge them: the ADR 0022
approvals (Nastavení → Deep Research, per organization) and ``clients.data_posture`` (Profil →
Pravidla, per client). The research workbench is the web's switch; ``smoke.sh`` reads it from the
deployed ``/config``.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from aia_core.domain.deployment import DataClassGates
from aia_core.domain.licence_determinations import PANEL_APPROVED_ROUTE
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.report_pdf import report_pdf_from_env

from .ai_runtime import AIRuntimeSettings
from .deep_research_runtime import (
    AGENT_DIRECTED_KEY,
    BRAVE_AS_OF_KEY,
    BRAVE_KEY,
    BRAVE_PRICE_KEY,
    COMMON_CRAWL_KEY,
    CONNECTORS_KEY,
    ENABLED_KEY,
    LEAD_KEY,
    WEB_SEARCH_KEY,
    agent_directed,
    brave_price_per_call,
    common_crawl,
    connectors,
    deep_research_enabled,
    lead,
    web_search,
)

__all__ = ["PROFILE", "ActivationRow", "Readiness", "judge"]

_A: Final = DataClass.CLASS_A_CLIENT_CONFIDENTIAL
_B: Final = DataClass.CLASS_B_DERIVED_CLIENT
#: The classes every design job, Lead turn and panel request needs (§4's route row).
MVP_CLASSES: Final = (_A, _B, DataClass.CLASS_C_INTERNAL)


@dataclass(frozen=True, slots=True)
class Readiness:
    ready: bool
    reason: str


@dataclass(frozen=True, slots=True)
class _Composition:
    """The environment, and the AI runtime as the worker reads it from there."""

    env: Mapping[str, str]
    settings: AIRuntimeSettings | None
    refused: str | None


@dataclass(frozen=True, slots=True)
class ActivationRow:
    key: str
    #: What needs it: the gate or acceptance criterion of §4.
    needed_by: str
    #: The environment keys the row reads (each passed to the worker by the Compose file).
    reads: tuple[str, ...]
    judge: Callable[[_Composition], Readiness]


def _off(key: str) -> Readiness:
    return Readiness(False, f"{key} is not true")


def _runtime(c: _Composition) -> AIRuntimeSettings | Readiness:
    if c.refused is not None:
        return Readiness(False, f"the AI runtime refuses its configuration: {c.refused}")
    if c.settings is None:
        return _off("AIA_AI_RUNTIME_ENABLED")
    return c.settings


def _passes(
    s: AIRuntimeSettings, needed: tuple[DataClass, ...], ready: str, parks: str
) -> Readiness:
    """READY when the route takes every class the material needs; under develop's advisory
    gates a class it refuses passes as a recorded advisory, and the reason says so."""
    missing = ", ".join(cls.value for cls in needed if cls not in s.approved_for)
    if not missing:
        return Readiness(True, ready)
    if s.data_class_gates is DataClassGates.ADVISORY:
        return Readiness(True, f"{ready}; {missing} pass only as advisory (develop)")
    return Readiness(False, f"the route refuses {missing}: {parks}")


def _ai_runtime(c: _Composition) -> Readiness:
    s = _runtime(c)
    if isinstance(s, Readiness):
        return s
    return Readiness(True, f"route {s.route_id}, model {s.model_id}")


def _route_classes(c: _Composition) -> Readiness:
    s = _runtime(c)
    if isinstance(s, Readiness):
        return s
    gaps = [f"not approved for {cls.value}" for cls in MVP_CLASSES if cls not in s.approved_for]
    if not s.eu_processing_approved:
        gaps.append("AIA_AI_ROUTE_EU_PROCESSING_APPROVED is not true")
    if not s.excluded_from_training:
        gaps.append("AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING is not true")
    if s.retention_days is None:
        gaps.append("AIA_AI_ROUTE_RETENTION_DAYS is unspecified")
    if gaps:
        return Readiness(False, "; ".join(gaps))
    return Readiness(True, f"A, B and C approved, retention {s.retention_days} days")


def _research_agents(c: _Composition) -> Readiness:
    s = _runtime(c)
    if isinstance(s, Readiness):
        return s
    if not s.research_agents_enabled:
        return _off("AIA_AI_RESEARCH_AGENTS_ENABLED")
    return _passes(s, (_A, _B), "the design workers are composed", "every design job parks")


def _study_lead(c: _Composition) -> Readiness:
    s = _runtime(c)
    if isinstance(s, Readiness):
        return s
    if not s.study_lead_enabled:
        return _off("AIA_AI_RESEARCH_LEAD_ENABLED")
    if not s.study_lead_configured:
        return Readiness(
            False,
            "AIA_AI_RESEARCH_LEAD_MAX_OUTPUT_TOKENS or _RESERVATION_USD unset: every turn parks",
        )
    model = s.study_lead_model.model_id if s.study_lead_model else f"the route's {s.model_id}"
    return _passes(s, (_A, _B), f"turns answer on {model}", "every turn parks")


#: The population the panel path reads: its import contract, which pins each companion's file
#: and each version's panel by size; bin/sync-population.sh lands them under their base names.
POPULATION_CONTRACT: Final = CZ_SYNTHETIC_V17


def _asset_root(env: Mapping[str, str]) -> Readiness:
    """READY only when every file the contract pins is there, readable, at its pinned size: a
    stat each, never a hash (the import judged the bytes)."""
    root = (env.get("AIA_POPULATION_ASSET_ROOT") or "").strip()
    if not root:
        return Readiness(False, "AIA_POPULATION_ASSET_ROOT is not set")
    if not os.path.isdir(root):
        return Readiness(False, f"{root} is not a directory (bin/sync-population.sh)")
    with os.scandir(root) as entries:
        sizes = {
            e.name: e.stat().st_size for e in entries if e.is_file() and os.access(e.path, os.R_OK)
        }
    contract = POPULATION_CONTRACT
    missing = [c.asset_id for c in contract.companions if sizes.get(c.asset_id) != c.byte_size]
    missing += [
        f"the {v.label} panel"
        for v in contract.known_versions
        if not any(
            name.endswith(f"_{v.label}.csv.gz") and size == v.byte_size
            for name, size in sizes.items()
        )
    ]
    if missing:
        return Readiness(
            False,
            f"{root} lacks {len(missing)} file(s) {contract.contract_id} pins, "
            f"among them {', '.join(missing[:3])} (bin/sync-population.sh)",
        )
    return Readiness(True, f"{root} holds every file {contract.contract_id} pins")


def _population_personas(c: _Composition) -> Readiness:
    s = _runtime(c)
    if isinstance(s, Readiness):
        return s
    if not s.population_personas_enabled:
        return _off("AIA_AI_POPULATION_PERSONAS_ENABLED")
    if s.route_id != PANEL_APPROVED_ROUTE:
        return Readiness(
            False, f"AIA_AI_ROUTE_ID is {s.route_id}; panel data may reach {PANEL_APPROVED_ROUTE}"
        )
    assets = _asset_root(c.env)
    if not assets.ready:
        return assets
    return _passes(s, (_A,), "the panel is offered", "every panel run parks")


def _analysis(c: _Composition) -> Readiness:
    s = _runtime(c)
    if isinstance(s, Readiness):
        return s
    if not s.analysis_enabled:
        return _off("AIA_AI_ANALYSIS_ENABLED")
    return _passes(
        s, (_A, _B), "the analysis modules are composed", "a modelled run's analysis parks"
    )


def _client_source_proposals(c: _Composition) -> Readiness:
    s = _runtime(c)
    if isinstance(s, Readiness):
        return s
    if not s.client_source_proposals_enabled:
        return _off("AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED")
    return _passes(
        s, (_A,), "proposals from a client's document are composed", "every proposal run parks"
    )


def _deep_research(c: _Composition) -> Readiness:
    if not deep_research_enabled(c.env):
        return _off(ENABLED_KEY)
    s = _runtime(c)
    if isinstance(s, Readiness):
        return s
    if not s.research_agents_enabled:
        return Readiness(False, f"{ENABLED_KEY} needs AIA_AI_RESEARCH_AGENTS_ENABLED")
    search = web_search(c.env)
    if search != "brave":
        return Readiness(False, f"{WEB_SEARCH_KEY} is {search}, not brave")
    brave_price_per_call(c.env)  # its dated price and its key's reference, refused by name
    return Readiness(True, "search route brave, priced")


def _deep_research_connectors(c: _Composition) -> Readiness:
    if not deep_research_enabled(c.env):
        return _off(ENABLED_KEY)
    listed = connectors(c.env)
    if not listed:
        return Readiness(False, f"{CONNECTORS_KEY} lists none")
    return Readiness(True, f"listed: {', '.join(listed)}")


def _common_crawl(c: _Composition) -> Readiness:
    if not deep_research_enabled(c.env):
        return _off(ENABLED_KEY)
    if not common_crawl(c.env):
        return _off(COMMON_CRAWL_KEY)
    return Readiness(True, "the Athena URL index and the archive are composed")


def _agent_directed(c: _Composition) -> Readiness:
    if not agent_directed(c.env):
        return _off(AGENT_DIRECTED_KEY)
    return Readiness(True, "the ladder asks the connectors, Wayback and Common Crawl")


def _deep_research_lead(c: _Composition) -> Readiness:
    if not lead(c.env):
        return _off(LEAD_KEY)
    return Readiness(True, "the lead plans the tracks and keeps the sources as a dataset")


def _report_pdf(c: _Composition) -> Readiness:
    if report_pdf_from_env(c.env) is None:
        return _off("AIA_REPORT_PDF_ENABLED")
    return Readiness(True, "LibreOffice renders each report's PDF")


def _not_built(chunk: str) -> Callable[[_Composition], Readiness]:
    return lambda _: Readiness(False, f"not built yet ({chunk})")


def _error_tracking(c: _Composition) -> Readiness:
    # Whether a DSN is set, never its value: a DSN carries the project's key.
    if not (c.env.get("AIA_ERROR_TRACKING_DSN") or "").strip():
        return Readiness(False, "AIA_ERROR_TRACKING_DSN is not set")
    return Readiness(True, "a DSN is set")


#: §4's rows a deployment sets, in its order.
PROFILE: Final = (
    ActivationRow(
        "ai_runtime",
        "every AI step (AC-03)",
        ("AIA_AI_RUNTIME_ENABLED", "AIA_AI_ROUTE_ID", "AIA_BEDROCK_MODEL_ID"),
        _ai_runtime,
    ),
    ActivationRow(
        "route_classes",
        "every design job, Lead turn and panel request",
        (
            "AIA_AI_ROUTE_APPROVED_FOR",
            "AIA_AI_ROUTE_RETENTION_DAYS",
            "AIA_AI_ROUTE_EU_PROCESSING_APPROVED",
            "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING",
        ),
        _route_classes,
    ),
    ActivationRow(
        "research_agents",
        "the design workers (AC-03)",
        ("AIA_AI_RESEARCH_AGENTS_ENABLED",),
        _research_agents,
    ),
    ActivationRow(
        "study_lead",
        "the Lead (AC-02)",
        (
            "AIA_AI_RESEARCH_LEAD_ENABLED",
            "AIA_AI_RESEARCH_LEAD_MAX_OUTPUT_TOKENS",
            "AIA_AI_RESEARCH_LEAD_RESERVATION_USD",
            "AIA_AI_RESEARCH_LEAD_MODEL_ID",
        ),
        _study_lead,
    ),
    ActivationRow(
        "population_personas",
        "population-built respondents (AC-05)",
        ("AIA_AI_POPULATION_PERSONAS_ENABLED", "AIA_AI_ROUTE_ID", "AIA_POPULATION_ASSET_ROOT"),
        _population_personas,
    ),
    ActivationRow(
        "analysis",
        "the eight analysis modules (AC-08)",
        ("AIA_AI_ANALYSIS_ENABLED",),
        _analysis,
    ),
    ActivationRow(
        "client_source_proposals",
        "AI proposals from a client document (AC-10)",
        ("AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED",),
        _client_source_proposals,
    ),
    ActivationRow(
        "deep_research",
        "Deep Research reach (AC-11)",
        (ENABLED_KEY, WEB_SEARCH_KEY, BRAVE_PRICE_KEY, BRAVE_AS_OF_KEY, BRAVE_KEY),
        _deep_research,
    ),
    ActivationRow(
        "deep_research_connectors",
        "the connectors (AC-11)",
        (CONNECTORS_KEY,),
        _deep_research_connectors,
    ),
    ActivationRow(
        "deep_research_common_crawl",
        "Common Crawl's index and archive (AC-11)",
        (COMMON_CRAWL_KEY,),
        _common_crawl,
    ),
    ActivationRow(
        "deep_research_agent_directed",
        "the connectors, Wayback and Common Crawl (AC-11)",
        (AGENT_DIRECTED_KEY,),
        _agent_directed,
    ),
    ActivationRow(
        "deep_research_lead",
        "a run's sources kept as a dataset (AC-11, G71)",
        (LEAD_KEY,),
        _deep_research_lead,
    ),
    ActivationRow(
        "report_pdf",
        "the PDF beside the internal DOCX (AC-13)",
        ("AIA_REPORT_PDF_ENABLED",),
        _report_pdf,
    ),
    ActivationRow(
        "lead_plans",
        "the plan card and wallet (AC-04)",
        (),
        _not_built("lead-orchestration#LO3, AIA_LEAD_PLANS_ENABLED"),
    ),
    ActivationRow(
        "run_qc",
        "the run QC node (AC-08)",
        (),
        _not_built("run-qc-and-checkpoint#RQC2, AIA_RUN_QC_ENABLED"),
    ),
    ActivationRow(
        "population_assets",
        "respondents and the audience step",
        ("AIA_POPULATION_ASSET_ROOT",),
        lambda c: _asset_root(c.env),
    ),
    ActivationRow(
        "error_tracking",
        "diagnostics",
        ("AIA_ERROR_TRACKING_DSN",),
        _error_tracking,
    ),
)


def _said(exc: Exception) -> str:
    return str(exc) or type(exc).__name__


def _judged(row: ActivationRow, composition: _Composition) -> Readiness:
    try:
        return row.judge(composition)
    except Exception as exc:  # a value the parsers refuse, or a directory not read: not ready
        return Readiness(False, _said(exc))


def judge(env: Mapping[str, str]) -> list[tuple[ActivationRow, Readiness]]:
    """Every row of :data:`PROFILE` judged over ``env``, in the profile's order. Never raises:
    a row that cannot be judged is NOT_READY with the refusal's own words."""
    try:
        composition = _Composition(env, AIRuntimeSettings.from_env(env), None)
    except Exception as exc:  # the worker refuses to start on it; each AI row says why
        composition = _Composition(env, None, _said(exc))
    return [(row, _judged(row, composition)) for row in PROFILE]
