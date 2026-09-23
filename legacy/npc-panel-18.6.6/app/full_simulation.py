"""Full Simulation Lab for NPC Panel 17.0.

This module is intentionally separated from the evidence-safe population core.
It is an experimental forecasting engine that is *allowed to hypothesize* missing
joint structure and topic-specific latent traits, but every such assumption is
persisted and benchmarked against later human truth.

Core design:
- research first (using existing dual-agent web research);
- explicit anti-leakage split between blind forecast and scenario/nowcast;
- stochastic topic-specific inoculation of the Czech population backbone;
- many plausible worlds, not one deterministic synthetic reality;
- immutable prediction freeze before truth can be attached;
- proper scoring + permanent leaderboard + domain reliability profile;
- optional adaptive hybrid that blends Full Simulation with the safer NPC core
  using only *previous* blind benchmark performance.

Nothing here upgrades CORE_JOINT_STATUS or validation_tier.  Full Simulation is
an experimental competitor to be measured, not a new source of evidence truth.
"""
from __future__ import annotations

from copy import deepcopy

import argparse
import hashlib
import json
import math
import os
import re
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from runtime_config import (
    DEFAULT_ANTHROPIC_RESEARCH_MODEL,
    DEFAULT_MODEL,
    DEFAULT_OPENAI_RESEARCH_MODEL,
    RELEASE,
    resolve_model,
    resolve_provider_model,
)
from pipeline import PANEL_PATH, Panel
from research_context import ResearchBundle, ResearchConfig, run_dual_research, save_bundle

ROOT = Path(__file__).resolve().parent
RUN_ROOT = ROOT / "full_simulation_runs"
BENCH_ROOT = ROOT / "full_simulation_benchmarks"
RUN_ROOT.mkdir(exist_ok=True)
BENCH_ROOT.mkdir(exist_ok=True)

BLIND = "blind_forecast"
SCENARIO = "scenario_nowcast"
VALID_OBJECTIVES = {BLIND, SCENARIO}


# ---------------------------------------------------------------------------
# generic helpers


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return _sha_bytes(raw)


def _slug(s: str, n: int = 40) -> str:
    x = re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")
    return (x[:n] or "factor")


def _clip(v: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, v)))


def _logit(p: float) -> float:
    p = _clip(p, 1e-6, 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def _weighted_mean(x: np.ndarray, w: np.ndarray) -> float:
    w = np.asarray(w, dtype=float)
    x = np.asarray(x, dtype=float)
    ok = np.isfinite(x) & np.isfinite(w) & (w > 0)
    if not np.any(ok):
        return float(np.nanmean(x))
    return float(np.average(x[ok], weights=w[ok]))


def _norm_numeric(s: pd.Series) -> np.ndarray:
    x = pd.to_numeric(s, errors="coerce").to_numpy(float)
    med = float(np.nanmedian(x)) if np.isfinite(x).any() else 0.0
    x = np.where(np.isfinite(x), x, med)
    sd = float(np.std(x))
    if sd <= 1e-9:
        return np.zeros(len(x), dtype=float)
    return (x - float(np.mean(x))) / sd


def _stable_category_score(values: pd.Series, target: str | None = None) -> np.ndarray:
    s = values.astype(str).fillna("")
    if target:
        return np.where(s.str.casefold() == str(target).casefold(), 1.0, -0.25).astype(float)
    # Stable pseudo-ordinal coding for categorical context.  It is deliberately
    # weak and only used when a world-model author did not name a target level.
    return np.array([
        ((int(hashlib.sha256(v.encode("utf-8")).hexdigest()[:8], 16) % 2001) / 1000.0 - 1.0)
        for v in s
    ], dtype=float)


def _question_payload(questions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for i, q in enumerate(questions):
        q = dict(q)
        qid = str(q.get("id") or f"q{i+1}")
        text = str(q.get("text") or "").strip()
        cats = [str(x) for x in (q.get("kategorie") or q.get("categories") or [])]
        if not text or len(cats) < 2:
            continue
        qq = {"id": qid, "text": text, "kategorie": cats}
        for k in ("filtr", "topics", "ordered", "domain", "type", "variants"):
            if k in q:
                qq[k] = q[k]
        out.append(qq)
    if not out:
        raise ValueError("Full Simulation potrebuje alespon jednu uzavrenou otazku se 2+ kategoriemi.")
    return out


# ---------------------------------------------------------------------------
# specification and world model


@dataclass
class FullSimulationSpec:
    topic: str
    questions: list[dict[str, Any]]
    objective: str = BLIND
    domain: str = "general"
    n: int = 400
    worlds: int = 12
    seed: int = 20260816
    model: str = DEFAULT_MODEL
    provider: str = "anthropic"  # anthropic | openai; inherited from the project
    mode: str = "dry"  # dry | sync | batch
    persona_mode: str = "calibrated"
    research_enabled: bool = True
    research_max_sources: int = 8
    world_model_provider: str = "selected"  # selected | heuristic (dry only); legacy explicit provider accepted
    include_core_baseline: bool = True
    include_demographics_baseline: bool = True
    use_learning_profile: bool = True
    save_world_overlays: bool = True
    adaptive_worlds: bool = True
    min_worlds: int = 5
    world_convergence_pp: float = 1.25
    diagnostic_mode: str = "smart"  # off | smart | max
    diagnostic_n: int = 120
    auto_wording_stress: bool = True
    anti_stereotype_guard: bool = True
    budget_max_usd: float | None = None
    scenario_contract: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    resume_run_id: str | None = None

    @classmethod
    def from_obj(cls, obj: dict[str, Any]) -> "FullSimulationSpec":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        clean = {k: v for k, v in dict(obj or {}).items() if k in known}
        clean["questions"] = _question_payload(clean.get("questions") or [])
        spec = cls(**clean)
        spec.topic = str(spec.topic or "").strip()
        if not spec.topic:
            spec.topic = " / ".join(q["text"] for q in spec.questions[:3])[:500]
        if spec.objective not in VALID_OBJECTIVES:
            raise ValueError(f"objective musi byt {BLIND} | {SCENARIO}")
        spec.n = int(max(50, min(5000, spec.n)))
        spec.worlds = int(max(2, min(50, spec.worlds)))
        spec.min_worlds = int(max(2, min(spec.worlds, spec.min_worlds)))
        spec.world_convergence_pp = float(max(0.25, min(5.0, spec.world_convergence_pp)))
        spec.diagnostic_n = int(max(50, min(500, spec.diagnostic_n)))
        if spec.diagnostic_mode not in {"off", "smart", "max"}:
            raise ValueError("diagnostic_mode musi byt off | smart | max")
        spec.seed = int(spec.seed)
        if spec.budget_max_usd is not None:
            spec.budget_max_usd = max(0.01, float(spec.budget_max_usd))
        if spec.mode not in {"dry", "sync", "batch"}:
            raise ValueError("mode musi byt dry | sync | batch")
        if spec.persona_mode not in {"core", "full", "demographics", "calibrated"}:
            raise ValueError("persona_mode musi byt calibrated | core | full | demographics")
        from provider_auth import normalize_ai_provider
        from runtime_config import resolve_provider_model
        legacy_provider = spec.world_model_provider if spec.world_model_provider in {"anthropic","openai"} else None
        spec.provider = normalize_ai_provider(spec.provider or legacy_provider)
        if spec.world_model_provider not in {"selected","heuristic","anthropic","openai","auto"}:
            spec.world_model_provider = "selected"
        spec.model = resolve_provider_model(spec.provider, spec.model)
        return spec


DEFAULT_FACTORS = [
    {"id":"category_involvement","label":"osobní relevance kategorie","description":"Jak moc člověk kategorii řeší, vyhledává informace a plánuje rozhodnutí.","target_mean_10":5.2,"target_sd_10":2.0,"confidence":0.42,"drivers":[{"field":"research_orientation_1_10","effect":0.38},{"field":"category_knowledge_general_1_10","effect":0.30},{"field":"purchase_planning_1_10","effect":0.22}]},
    {"id":"adoption_openness","label":"otevřenost vyzkoušet novinku","description":"Ochota přijmout nový produkt, značku nebo způsob chování.","target_mean_10":5.0,"target_sd_10":2.2,"confidence":0.46,"drivers":[{"field":"novelty_orientation_1_10","effect":0.55},{"field":"value_openness_to_change_1_10","effect":0.28},{"field":"risk_aversion_1_10","effect":-0.22},{"field":"vek","effect":-0.12}]},
    {"id":"economic_friction","label":"ekonomická brzda","description":"Nakolik cena a rozpočtové omezení brzdí pozitivní reakci.","target_mean_10":5.5,"target_sd_10":2.0,"confidence":0.50,"drivers":[{"field":"price_sensitivity_1_10","effect":0.58},{"field":"deal_proneness_1_10","effect":0.24},{"field":"premium_willingness_1_10","effect":-0.20},{"field":"prijem_pozice_0_1","effect":-0.24},{"field":"financial_resilience_1_10","effect":-0.18}]},
    {"id":"brand_receptivity","label":"receptivita vůči značce","description":"Obecná receptivita k brand cues; konkrétní znalost značky se NESMÍ vymyslet bez brand state.","target_mean_10":5.2,"target_sd_10":1.9,"confidence":0.34,"drivers":[{"field":"brand_consciousness_1_10","effect":0.32},{"field":"brand_loyalty_general_1_10","effect":0.18},{"field":"advertising_skepticism_1_10","effect":-0.24},{"field":"need_for_affect_1_10","effect":0.16}]},
    {"id":"social_diffusion","label":"sociální šíření","description":"Nakolik reakci ovlivňují druzí a digitální sociální prostředí.","target_mean_10":4.8,"target_sd_10":2.1,"confidence":0.36,"drivers":[{"field":"social_proof_susceptibility_1_10","effect":0.48},{"field":"influencer_receptivity_1_10","effect":0.25},{"field":"social_media_intensity_1_10","effect":0.18},{"field":"BFI_EXTR","effect":0.08}]},
    {"id":"skepticism","label":"skepticismus a potřeba důkazu","description":"Nakolik člověk rozpoznává persuazi, vyžaduje informace a odolává marketingovému sdělení.","target_mean_10":5.2,"target_sd_10":1.9,"confidence":0.44,"drivers":[{"field":"advertising_skepticism_1_10","effect":0.48},{"field":"persuasion_knowledge_1_10","effect":0.26},{"field":"need_for_cognition_1_10","effect":0.20},{"field":"research_orientation_1_10","effect":0.17},{"field":"PIAAC_I2_Q01b","effect":-0.08}]},
]


def _available_driver_columns(panel: pd.DataFrame) -> list[str]:
    explicit=["vek","pohlavi","vzdelani","kraj","zamestnani_status","prijem_pozice_0_1","velikost_domacnosti","pocet_deti_celkem","zdravi_sebehodnoceni"]
    prefixes=("BFI_","PIAAC_","JRC_","QOG_","ROL_")
    suffixes=("_1_10","_minutes_day","_hours_week")
    exclude=("confidence","status","source","_quality","_distance","vaha_","profile_")
    candidates=[]
    for c in panel.columns:
        if c in explicit or c.startswith(prefixes) or c.endswith(suffixes) or c in {"PHQ9_2022","GAD7_2022","financial_budgeting","financial_regular_reserve","financial_goal_set"}:
            if not any(x in c for x in exclude) and c not in candidates:candidates.append(c)
    return candidates[:180]


def _research_items(bundle: ResearchBundle, objective: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted = []
    for i, x in enumerate(bundle.accepted, 1):
        y = dict(x)
        y["ref"] = f"A{i}"
        y["leakage"] = False
        accepted.append(y)
    contaminated = []
    if objective == SCENARIO:
        j = 1
        for x in bundle.quarantined:
            if x.get("reason") in {"target_outcome_overlap", "deterministic_target_overlap"}:
                y = dict(x)
                y["ref"] = f"L{j}"
                y["leakage"] = True
                contaminated.append(y)
                j += 1
    return accepted, contaminated


def _world_model_prompt(spec: FullSimulationSpec, research: ResearchBundle, panel: pd.DataFrame) -> str:
    accepted, contaminated = _research_items(research, spec.objective)
    drivers = _available_driver_columns(panel)
    leakage_text = (
        "BLIND FORECAST: target-overlap evidence is forbidden and is not supplied below."
        if spec.objective == BLIND else
        "SCENARIO/NOWCAST: target-overlap evidence may inform hypotheses, but every use MUST cite L* refs and makes the run contaminated for predictive benchmarking."
    )
    return f"""You are designing the experimental WORLD MODEL for Full Simulation Lab in a Czech synthetic population system.

Goal: create the most plausible *hypothesis* of how Czech people differ on this topic. Be bold where evidence is missing, but never pretend a hypothesis is measured truth. The model will be sampled stochastically across 18k population records and later judged against held-out human truth.

TOPIC: {spec.topic}
DOMAIN: {spec.domain}
OBJECTIVE: {spec.objective}
{leakage_text}

APPROVED SCENARIO DELTA CONTRACT (human-reviewed; honor these mechanisms, do not turn them into target answer shares):
{json.dumps(spec.scenario_contract or {}, ensure_ascii=False, indent=2)}

QUESTIONS:
{json.dumps(spec.questions, ensure_ascii=False, indent=2)}

SAFE RESEARCH EVIDENCE (A refs):
{json.dumps(accepted[:16], ensure_ascii=False, indent=2, default=str)}

SCENARIO-ONLY TARGET-OVERLAP EVIDENCE (L refs):
{json.dumps(contaminated[:12], ensure_ascii=False, indent=2, default=str)}

AVAILABLE POPULATION/PERSONA DRIVER COLUMNS:
{json.dumps(drivers, ensure_ascii=False)}

Return 6-12 topic-specific latent factors. Each factor is a 1-10 trait. Give a plausible population mean and SD, confidence, and 1-6 drivers from AVAILABLE columns. Driver effect is standardized slope -1..1. Categorical drivers may name category. Add plausible correlations between latent factors. Keep |rho| <= .65. Do NOT encode the desired survey answer as a factor and do NOT set category shares directly. This is a causal/behavioral hypothesis layer, not answer post-stratification.

JSON shape exactly:
{{
 "summary":"...",
 "assumptions":["..."],
 "factors":[{{"id":"snake_case","label":"...","description":"...","target_mean_10":5.0,"target_sd_10":2.0,"confidence":0.5,"drivers":[{{"field":"column","effect":0.3,"category":null}}],"evidence_refs":["A1"]}}],
 "factor_correlations":[{{"a":"id","b":"id","rho":0.25}}],
 "scenario_leakage_refs":["L1"]
}}
"""


def _world_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "factors": {"type": "array", "minItems": 4, "maxItems": 12, "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"}, "label": {"type": "string"}, "description": {"type": "string"},
                    "target_mean_10": {"type": "number"}, "target_sd_10": {"type": "number"},
                    "confidence": {"type": "number"},
                    "drivers": {"type": "array", "items": {"type": "object", "properties": {
                        "field": {"type": "string"}, "effect": {"type": "number"},
                        "category": {"type": ["string", "null"]},
                    }, "required": ["field", "effect", "category"], "additionalProperties": False}},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "label", "description", "target_mean_10", "target_sd_10", "confidence", "drivers", "evidence_refs"],
                "additionalProperties": False,
            }},
            "factor_correlations": {"type": "array", "items": {"type": "object", "properties": {
                "a": {"type": "string"}, "b": {"type": "string"}, "rho": {"type": "number"},
            }, "required": ["a", "b", "rho"], "additionalProperties": False}},
            "scenario_leakage_refs": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "assumptions", "factors", "factor_correlations", "scenario_leakage_refs"],
        "additionalProperties": False,
    }


def _extract_json(text: str) -> dict[str, Any]:
    text = str(text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise ValueError("World-model agent nevratil JSON.")
    return json.loads(m.group(1))


def _anthropic_text(r: Any) -> str:
    return "\n".join(getattr(x, "text", "") for x in (getattr(r, "content", []) or []) if getattr(x, "type", None) == "text")


def _generate_world_model_live(prompt: str, provider: str, model: str | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    from provider_auth import provider_key_ready, normalize_ai_provider
    from ai_router import call_structured
    prefer = normalize_ai_provider(provider)
    if not provider_key_ready(prefer):
        raise RuntimeError(f"Full Simulation: zvolený provider {prefer} není připravený.")
    r=call_structured(system="Vytváříš auditovatelný world model Full Simulation. Nevydávej hypotézy za měřená fakta.",
                      messages=[{"role":"user","content":prompt}],schema=_world_schema(),schema_name="npc_fullsim_world_model",
                      anthropic_model=resolve_provider_model("anthropic", model or DEFAULT_ANTHROPIC_RESEARCH_MODEL),openai_model=resolve_provider_model("openai", model or DEFAULT_OPENAI_RESEARCH_MODEL),max_tokens=5000,prefer=prefer,allow_fallback=False)
    return dict(r["data"]), {"provider":str(r.get("provider")),"model":str(r.get("model") or ""),"fallback_used":bool(r.get("fallback_used"))}


def _fallback_world_model(spec: FullSimulationSpec, panel: pd.DataFrame) -> dict[str, Any]:
    available = set(panel.columns)
    factors = []
    for f in DEFAULT_FACTORS:
        x = json.loads(json.dumps(f, ensure_ascii=False))
        x["drivers"] = [d for d in x["drivers"] if d["field"] in available]
        x["evidence_refs"] = []
        factors.append(x)
    topic = (spec.topic + " " + " ".join(q["text"] for q in spec.questions)).lower()
    if any(k in topic for k in ("polit", "volb", "vlád", "vlada", "euro", "instituc")):
        factors.append({
            "id": "institutional_alignment", "label": "institucionální a hodnotové naladění",
            "description": "Topic-specific směs důvěry v instituce, tradice a otevřenosti změně.",
            "target_mean_10": 5.0, "target_sd_10": 2.1, "confidence": 0.25,
            "drivers": [d for d in [
                {"field": "elity_duveryhodne_2021", "effect": 0.55},
                {"field": "value_openness_to_change_1_10", "effect": 0.25},
                {"field": "value_tradition_1_10", "effect": -0.20},
            ] if d["field"] in available], "evidence_refs": [],
        })
    if any(k in topic for k in ("media", "telev", "internet", "tiktok", "instagram", "youtube", "reklam")):
        factors.append({
            "id": "media_reachability", "label": "dosažitelnost v relevantních médiích",
            "description": "Pravděpodobnost, že respondent bude vystaven tématu v relevantních kanálech.",
            "target_mean_10": 5.1, "target_sd_10": 2.2, "confidence": 0.3,
            "drivers": [d for d in [
                {"field": "online_information_intensity_1_10", "effect": 0.30},
                {"field": "youtube_minutes_day", "effect": 0.25},
                {"field": "tv_intensity_1_10", "effect": 0.20},
            ] if d["field"] in available], "evidence_refs": [],
        })
    ids = {f["id"] for f in factors}
    cors = [
        {"a": "adoption_openness", "b": "economic_friction", "rho": -0.22},
        {"a": "brand_receptivity", "b": "social_diffusion", "rho": 0.28},
        {"a": "skepticism", "b": "brand_receptivity", "rho": -0.16},
        {"a": "category_involvement", "b": "skepticism", "rho": 0.18},
    ]
    cors = [x for x in cors if x["a"] in ids and x["b"] in ids]
    return {
        "summary": "Heuristický topic-specific world model; používá existující deep-persona vrstvy a stochastický joint draw.",
        "assumptions": [
            "Chybějící topic-specific joint vztahy jsou hypotézy, ne měření.",
            "Marginály faktorů jsou široké priory, nikoli publikované prevalence.",
        ],
        "factors": factors[:12], "factor_correlations": cors, "scenario_leakage_refs": [],
    }


def _sanitize_world_model(raw: dict[str, Any], spec: FullSimulationSpec, panel: pd.DataFrame,
                          research: ResearchBundle, generator: dict[str, str]) -> dict[str, Any]:
    available = set(panel.columns)
    factors = []
    seen = set()
    for i, f in enumerate(raw.get("factors") or []):
        fid = _slug(f.get("id") or f.get("label") or f"factor_{i+1}")
        if fid in seen:
            continue
        seen.add(fid)
        drivers = []
        for d in f.get("drivers") or []:
            field = str(d.get("field") or "")
            if field not in available:
                continue
            try:
                effect = _clip(float(d.get("effect", 0)), -1.0, 1.0)
            except Exception:
                continue
            if abs(effect) < 0.02:
                continue
            drivers.append({"field": field, "effect": round(effect, 4), "category": d.get("category")})
        factors.append({
            "id": fid,
            "label": str(f.get("label") or fid).strip()[:120],
            "description": str(f.get("description") or "").strip()[:600],
            "target_mean_10": round(_clip(float(f.get("target_mean_10", 5.0)), 1.2, 9.8), 3),
            "target_sd_10": round(_clip(float(f.get("target_sd_10", 2.0)), 0.6, 3.2), 3),
            "confidence": round(_clip(float(f.get("confidence", 0.3)), 0.05, 0.95), 3),
            "drivers": drivers[:6],
            "evidence_refs": [str(x) for x in (f.get("evidence_refs") or [])][:8],
            "epistemic_status": "HYPOTHESIZED_JOINT",
        })
    if len(factors) < 4:
        fb = _fallback_world_model(spec, panel)
        for f in fb["factors"]:
            if f["id"] not in seen:
                factors.append(f)
                seen.add(f["id"])
            if len(factors) >= 6:
                break
    ids = {x["id"] for x in factors}
    cors = []
    for c in raw.get("factor_correlations") or []:
        a, b = _slug(c.get("a", "")), _slug(c.get("b", ""))
        if a not in ids or b not in ids or a == b:
            continue
        try:
            rho = _clip(float(c.get("rho", 0)), -0.65, 0.65)
        except Exception:
            continue
        cors.append({"a": a, "b": b, "rho": round(rho, 4), "epistemic_status": "HYPOTHESIZED_JOINT"})
    requested_leaks = [str(x) for x in (raw.get("scenario_leakage_refs") or []) if str(x).startswith("L")]
    if spec.objective == BLIND:
        requested_leaks = []
    accepted, contaminated = _research_items(research, spec.objective)
    available_leaks = {x["ref"] for x in contaminated}
    used_leaks = [x for x in requested_leaks if x in available_leaks]
    model = {
        "kind": "npc_full_simulation_world_model_v1",
        "created_at": _now(), "release": RELEASE,
        "topic": spec.topic, "domain": spec.domain, "objective": spec.objective,
        "summary": str(raw.get("summary") or "").strip()[:1800],
        "assumptions": [str(x)[:800] for x in (raw.get("assumptions") or [])][:20],
        "factors": factors[:12], "factor_correlations": cors[:30],
        "research_sha256": research.sha256,
        "research_refs_available": [x["ref"] for x in accepted],
        "scenario_leakage_refs_used": used_leaks,
        "contaminated_for_predictive_benchmark": bool(used_leaks or spec.objective == SCENARIO),
        "generator": generator,
        "note": "Topic-specific factors are simulation hypotheses. They do not change evidence tier or CORE_JOINT_STATUS.",
    }
    model["sha256"] = _sha_json(model)
    return model


def build_world_model(spec: FullSimulationSpec, research: ResearchBundle, panel: pd.DataFrame,
                      *, mock_model: dict[str, Any] | None = None) -> dict[str, Any]:
    if mock_model is not None:
        raw, generator = mock_model, {"provider": "mock", "model": "mock"}
    elif spec.world_model_provider == "heuristic":
        if spec.mode != "dry":
            raise RuntimeError("FULLSIM_LIVE_WORLD_MODEL_REQUIRED: heuristic world model je povolen jen v INVALID dry režimu.")
        raw, generator = _fallback_world_model(spec, panel), {"provider": "heuristic", "model": "deterministic-v1"}
    else:
        from provider_auth import provider_key_ready
        ready = provider_key_ready(spec.provider)
        if not ready:
            if spec.mode != "dry":
                raise RuntimeError(f"FULLSIM_LIVE_WORLD_MODEL_REQUIRED: zvolený provider {spec.provider} není dostupný.")
            raw, generator = _fallback_world_model(spec, panel), {"provider": "heuristic_offline_no_key", "model": "deterministic-v1"}
        else:
            raw, generator = _generate_world_model_live(_world_model_prompt(spec, research, panel), spec.provider, spec.model)
    return _sanitize_world_model(raw, spec, panel, research, generator)


# ---------------------------------------------------------------------------
# stochastic population inoculation


def _nearest_psd_corr(m: np.ndarray) -> np.ndarray:
    m = (m + m.T) / 2.0
    np.fill_diagonal(m, 1.0)
    vals, vecs = np.linalg.eigh(m)
    vals = np.maximum(vals, 1e-5)
    x = vecs @ np.diag(vals) @ vecs.T
    d = np.sqrt(np.clip(np.diag(x), 1e-12, None))
    x = x / np.outer(d, d)
    np.fill_diagonal(x, 1.0)
    return x


def _corr_matrix(world_model: dict[str, Any]) -> np.ndarray:
    fs = world_model["factors"]
    ids = [x["id"] for x in fs]
    ix = {x: i for i, x in enumerate(ids)}
    c = np.eye(len(fs), dtype=float)
    for e in world_model.get("factor_correlations") or []:
        if e["a"] in ix and e["b"] in ix:
            i, j = ix[e["a"]], ix[e["b"]]
            c[i, j] = c[j, i] = _clip(float(e["rho"]), -0.65, 0.65)
    return _nearest_psd_corr(c)


def _calibrate_intercept(base: np.ndarray, target_mean_10: float, weights: np.ndarray) -> float:
    target = _clip((target_mean_10 - 1.0) / 9.0, 0.01, 0.99)
    lo, hi = -8.0, 8.0
    for _ in range(48):
        mid = (lo + hi) / 2
        mean = _weighted_mean(_sigmoid(base + mid), weights)
        if mean < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _driver_vector(df: pd.DataFrame, d: dict[str, Any]) -> np.ndarray:
    field = d["field"]
    s = df[field]
    if pd.api.types.is_numeric_dtype(s):
        return _norm_numeric(s)
    return _stable_category_score(s, d.get("category"))


def inoculate_population(base_df: pd.DataFrame, world_model: dict[str, Any], *, world_index: int,
                         seed: int, learning_profile: dict[str, Any] | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Create one stochastic topic-specific population world.

    The base Czech population rows/weights remain unchanged. Only FS_* fields are
    added.  Different worlds perturb uncertain means, driver strengths and shared
    latent noise while preserving plausible dependence via a Gaussian copula.
    """
    df = base_df.copy()
    factors = world_model["factors"]
    k = len(factors)
    world_seed = int(seed + 104729 * (world_index + 1))
    rng = np.random.default_rng(world_seed)
    corr = _corr_matrix(world_model)
    noise = rng.multivariate_normal(np.zeros(k), corr, size=len(df))
    weights = pd.to_numeric(df.get("_analysis_weight",df.get("vaha_strukturalni_2025",df.get("vaha_kalibrovana", 1.0))), errors="coerce").fillna(0).to_numpy(float) if isinstance(df.get("_analysis_weight",df.get("vaha_strukturalni_2025",df.get("vaha_kalibrovana", 1.0))), pd.Series) else np.ones(len(df))
    if not np.any(weights > 0):
        weights = np.ones(len(df), dtype=float)

    reliability = float((learning_profile or {}).get("full_simulation_reliability", 0.5))
    prior_mult = float((learning_profile or {}).get("world_uncertainty_multiplier", 1.0))
    prior_mult = _clip(prior_mult, 0.75, 1.8)

    factor_stats = []
    factor_values: dict[str, np.ndarray] = {}
    for j, f in enumerate(factors):
        conf = float(f.get("confidence", 0.3))
        mean_sd = max(0.12, (1.0 - conf) * 1.15 * prior_mult)
        target_mean = _clip(float(f["target_mean_10"]) + rng.normal(0, mean_sd), 1.3, 9.7)
        target_sd = _clip(float(f.get("target_sd_10", 2.0)) * rng.lognormal(0, 0.10 * prior_mult), 0.7, 3.4)
        lin = np.zeros(len(df), dtype=float)
        sampled_drivers = []
        for d in f.get("drivers") or []:
            try:
                effect0 = float(d["effect"])
                effect = _clip(rng.normal(effect0, max(0.04, abs(effect0) * (1-conf) * 0.28 * prior_mult)), -1.25, 1.25)
                lin += effect * _driver_vector(df, d)
                sampled_drivers.append({**d, "sampled_effect": round(float(effect), 4)})
            except Exception:
                continue
        # Logistic-normal scale. target_sd controls noise amplitude; reliability
        # slightly reduces extreme world perturbation once repeated benchmarks earn it.
        noise_scale = _clip(target_sd / 1.9, 0.45, 1.8) * (1.08 - 0.16 * reliability)
        lin += noise[:, j] * noise_scale
        intercept = _calibrate_intercept(lin, target_mean, weights)
        score = 1.0 + 9.0 * _sigmoid(lin + intercept)
        col = f"FS_{f['id']}_10"
        df[col] = np.round(score, 3)
        factor_values[f["id"]] = score
        factor_stats.append({
            "id": f["id"], "label": f["label"], "target_mean_10_sampled": round(target_mean, 3),
            "realized_weighted_mean_10": round(_weighted_mean(score, weights), 3),
            "realized_sd_10": round(float(np.std(score)), 3), "drivers": sampled_drivers,
        })

    # Human-readable profile line injected into the persona. Use extremes only so
    # LLMs do not average a long list into a generic respondent.
    labels = {f["id"]: f["label"] for f in factors}
    ids = [f["id"] for f in factors]
    mat = np.column_stack([factor_values[x] for x in ids]) if ids else np.empty((len(df), 0))
    profiles = []
    if len(ids):
        for row in mat:
            order = np.argsort(-np.abs(row - 5.5))[: min(5, len(ids))]
            parts = [f"{labels[ids[z]]}: {row[z]:.0f}/10" for z in order]
            profiles.append("; ".join(parts))
    else:
        profiles = [""] * len(df)
    df["FS_SIMULATION_PROFILE"] = profiles
    df["FS_WORLD_ID"] = f"world_{world_index+1:03d}"
    df["FS_WORLD_SEED"] = world_seed
    df["FS_WORLD_MODEL_SHA256"] = world_model["sha256"]
    df["FS_EPISTEMIC_STATUS"] = "EXPERIMENTAL_HYPOTHESIZED_JOINT"

    meta = {
        "world_id": f"world_{world_index+1:03d}", "world_index": world_index,
        "seed": world_seed, "factor_stats": factor_stats, "correlation_matrix": corr.round(5).tolist(),
        "population_rows": int(len(df)), "learning_profile_used": bool(learning_profile),
    }
    meta["sha256"] = _sha_json(meta)
    return df, meta


# ---------------------------------------------------------------------------
# scoring, ensemble and learning


def _extract_dist(answer: dict[str, Any]) -> dict[str, float]:
    d = answer.get("expected_pct") or answer.get("celkem_pct") or {}
    return {str(k): float(v) for k, v in d.items() if v is not None and np.isfinite(float(v))}


def _extract_ci(answer: dict[str, Any]) -> dict[str, dict[str, float]]:
    src = answer.get("expected_intervaly_95") or answer.get("intervaly_95") or {}
    out = {}
    for k, v in src.items():
        try:
            lo = float(v.get("low")); hi = float(v.get("high"))
            if np.isfinite(lo) and np.isfinite(hi):
                out[str(k)] = {"low": lo, "high": hi}
        except Exception:
            pass
    return out


def ensemble_world_results(world_results: list[dict[str, Any]], questions: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "full_simulation_world_ensemble", "worlds": len(world_results), "questions": {}}
    for q in questions:
        qid, cats = q["id"], list(q["kategorie"])
        rows = []
        cis = []
        for wr in world_results:
            ans = (wr.get("vysledky") or {}).get(qid, {})
            rows.append(_extract_dist(ans))
            cis.append(_extract_ci(ans))
        qout = {"text": q["text"], "categories": cats, "estimate_pct": {}, "interval_95": {},
                "between_world_sd_pp": {}, "within_world_sd_pp": {}, "world_estimates": {}}
        for cat in cats:
            vals = np.array([r.get(cat, np.nan) for r in rows], dtype=float)
            vals = vals[np.isfinite(vals)]
            if not len(vals):
                continue
            within_vars = []
            for ci in cis:
                if cat in ci:
                    width = max(0.0, float(ci[cat]["high"]) - float(ci[cat]["low"]))
                    within_vars.append((width / 3.92) ** 2)
            within = float(np.mean(within_vars)) if within_vars else 0.0
            between = float(np.var(vals, ddof=1)) if len(vals) > 1 else 0.0
            total_sd = math.sqrt(max(0.0, within + between))
            est = float(np.mean(vals))
            qout["estimate_pct"][cat] = round(est, 3)
            qout["interval_95"][cat] = {"low": round(max(0.0, est - 1.96*total_sd), 3), "high": round(min(100.0, est + 1.96*total_sd), 3)}
            qout["between_world_sd_pp"][cat] = round(math.sqrt(max(0.0, between)), 3)
            qout["within_world_sd_pp"][cat] = round(math.sqrt(max(0.0, within)), 3)
            qout["world_estimates"][cat] = [round(float(x), 3) for x in vals]
        out["questions"][qid] = qout
    out["uncertainty_note"] = (
        "95% world-ensemble interval combines mean respondent-bootstrap variance within worlds and between-world simulation variance via the law of total variance. It is not Rubin multiple-imputation inference."
    )
    out["sha256"] = _sha_json(out)
    return out


def _single_run_prediction(run: dict[str, Any], questions: list[dict[str, Any]], label: str) -> dict[str, Any]:
    obj = {"kind": label, "questions": {}}
    for q in questions:
        ans = (run.get("vysledky") or {}).get(q["id"], {})
        obj["questions"][q["id"]] = {
            "text": q["text"], "categories": q["kategorie"], "estimate_pct": _extract_dist(ans), "interval_95": _extract_ci(ans)
        }
    obj["sha256"] = _sha_json(obj)
    return obj


def blend_predictions(a: dict[str, Any], b: dict[str, Any], weight_a: float, *, label: str = "adaptive_hybrid") -> dict[str, Any]:
    w = _clip(weight_a, 0.0, 1.0)
    out = {"kind": label, "weight_full_simulation": round(w, 4), "questions": {}}
    for qid in sorted(set(a.get("questions", {})) & set(b.get("questions", {}))):
        qa, qb = a["questions"][qid], b["questions"][qid]
        cats = sorted(set(qa.get("estimate_pct", {})) | set(qb.get("estimate_pct", {})))
        est = {c: w*float(qa.get("estimate_pct", {}).get(c, 0)) + (1-w)*float(qb.get("estimate_pct", {}).get(c, 0)) for c in cats}
        ci = {}
        for c in cats:
            ia = qa.get("interval_95", {}).get(c); ib = qb.get("interval_95", {}).get(c)
            if ia and ib:
                ci[c] = {"low": round(w*float(ia["low"])+(1-w)*float(ib["low"]),3), "high": round(w*float(ia["high"])+(1-w)*float(ib["high"]),3)}
        out["questions"][qid] = {"text": qa.get("text") or qb.get("text"), "categories": cats,
                                  "estimate_pct": {k:round(v,3) for k,v in est.items()}, "interval_95": ci}
    out["sha256"] = _sha_json(out)
    return out


def _normalize_pct(d: dict[str, Any], cats: list[str]) -> np.ndarray:
    x = np.array([max(0.0, float(d.get(c, 0.0))) for c in cats], dtype=float)
    s = x.sum()
    return x / s if s > 0 else np.ones(len(cats), dtype=float) / max(1, len(cats))


def score_distribution(pred_pct: dict[str, float], truth_pct: dict[str, float], *, ordered: bool = False) -> dict[str, Any]:
    cats = list(truth_pct)
    for c in pred_pct:
        if c not in cats:
            cats.append(c)
    p = _normalize_pct(pred_pct, cats)
    t = _normalize_pct(truth_pct, cats)
    err_pp = (p - t) * 100
    eps = 1e-9
    mid=.5*(p+t)
    kl_pm=float(np.sum(p*np.log(np.clip(p,eps,1)/np.clip(mid,eps,1))))
    kl_tm=float(np.sum(t*np.log(np.clip(t,eps,1)/np.clip(mid,eps,1))))
    hp=float(-np.sum(p*np.log(np.clip(p,eps,1)))); ht=float(-np.sum(t*np.log(np.clip(t,eps,1))))
    result = {
        "mae_pp": round(float(np.mean(np.abs(err_pp))), 4),
        "rmse_pp": round(float(np.sqrt(np.mean(err_pp**2))), 4),
        "max_abs_error_pp": round(float(np.max(np.abs(err_pp))), 4),
        "tvd_pp": round(float(50*np.sum(np.abs(p-t))), 4),
        "brier": round(float(np.sum((p-t)**2)), 6),
        "cross_entropy": round(float(-np.sum(t*np.log(np.clip(p, eps, 1)))), 6),
        "jensen_shannon": round(float(.5*(kl_pm+kl_tm)), 6),
        "entropy_gap": round(float(hp-ht), 6),
    }
    if ordered and len(cats) >= 2:
        result["crps_ordinal"] = round(float(np.mean((np.cumsum(p)[:-1]-np.cumsum(t)[:-1])**2)), 6)
    else:
        result["crps_ordinal"] = None
    return result


def score_prediction(prediction: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    tqs = truth.get("questions") or {}
    rows = []
    coverage = []
    for qid, tq in tqs.items():
        pq = (prediction.get("questions") or {}).get(qid)
        if not pq:
            continue
        td = tq.get("truth_pct") if isinstance(tq, dict) else tq
        if not isinstance(td, dict):
            continue
        m = score_distribution(pq.get("estimate_pct") or {}, td, ordered=bool((tq if isinstance(tq,dict) else {}).get("ordered", False)))
        cov = []
        for cat, tv in td.items():
            ci = (pq.get("interval_95") or {}).get(cat)
            if ci:
                cov.append(float(ci["low"]) <= float(tv) <= float(ci["high"]))
        m.update({"question_id": qid, "coverage_95": (round(float(np.mean(cov)),4) if cov else None)})
        rows.append(m)
        if cov:
            coverage.extend(cov)
    if not rows:
        return {"status": "NO_COMPARABLE_QUESTIONS", "questions": []}
    keys = ["mae_pp", "rmse_pp", "max_abs_error_pp", "tvd_pp", "brier", "cross_entropy", "jensen_shannon"]
    overall = {k: round(float(np.mean([r[k] for r in rows])), 6) for k in keys}
    cr = [r["crps_ordinal"] for r in rows if r.get("crps_ordinal") is not None]
    overall["crps_ordinal"] = round(float(np.mean(cr)), 6) if cr else None
    overall["coverage_95"] = round(float(np.mean(coverage)), 4) if coverage else None
    return {"status": "SCORED", "overall": overall, "questions": rows}


def _benchmark_dirs() -> list[Path]:
    return sorted([p for p in BENCH_ROOT.iterdir() if p.is_dir()]) if BENCH_ROOT.exists() else []


def leaderboard() -> dict[str, Any]:
    records = []
    for d in _benchmark_dirs():
        p = d / "scores.json"
        meta = d / "truth.json"
        if not p.exists() or not meta.exists():
            continue
        try:
            scores = json.loads(p.read_text(encoding="utf-8"))
            truth = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        if truth.get("benchmark_eligibility") != "BLIND_ELIGIBLE":
            continue
        for method, s in (scores.get("methods") or {}).items():
            if s.get("status") != "SCORED":
                continue
            records.append({"run_id": d.name, "method": method, "domain": truth.get("domain", "general"), **s["overall"]})
    by: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        by.setdefault(r["method"], []).append(r)
    methods = {}
    for method, rows in by.items():
        methods[method] = {
            "n_benchmarks": len(rows),
            "mean_mae_pp": round(float(np.mean([r["mae_pp"] for r in rows])), 4),
            "mean_tvd_pp": round(float(np.mean([r["tvd_pp"] for r in rows])), 4),
            "mean_brier": round(float(np.mean([r["brier"] for r in rows])), 6),
            "mean_coverage_95": round(float(np.mean([r["coverage_95"] for r in rows if r.get("coverage_95") is not None])),4) if any(r.get("coverage_95") is not None for r in rows) else None,
        }
    # Head-to-head FullSim vs core on same benchmark.
    paired = []
    for rid in sorted({r["run_id"] for r in records}):
        rr = {r["method"]: r for r in records if r["run_id"] == rid}
        if "FULL_SIMULATION" in rr and "NPC_CORE" in rr:
            paired.append(rr["FULL_SIMULATION"]["mae_pp"] < rr["NPC_CORE"]["mae_pp"])
    return {
        "kind": "npc_full_simulation_leaderboard_v1", "created_at": _now(),
        "methods": methods, "n_blind_benchmarks": len({r["run_id"] for r in records}),
        "fullsim_win_rate_vs_core": round(float(np.mean(paired)),4) if paired else None,
        "records": records[-500:],
        "note": "Only predictions frozen before human truth and not contaminated by target-overlap research count here.",
    }


def learning_profile(domain: str = "general", *, exclude_run_id: str | None = None) -> dict[str, Any]:
    rows = []
    for d in _benchmark_dirs():
        if d.name == exclude_run_id:
            continue
        sp, tp = d / "scores.json", d / "truth.json"
        if not sp.exists() or not tp.exists():
            continue
        try:
            s = json.loads(sp.read_text(encoding="utf-8")); t = json.loads(tp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if t.get("benchmark_eligibility") != "BLIND_ELIGIBLE":
            continue
        if str(t.get("domain", "general")) not in {str(domain), "general"}:
            continue
        fs = (s.get("methods") or {}).get("FULL_SIMULATION", {})
        core = (s.get("methods") or {}).get("NPC_CORE", {})
        if fs.get("status") == "SCORED":
            rows.append({"run_id": d.name, "fs": fs["overall"], "core": core.get("overall") if core.get("status")=="SCORED" else None})
    if not rows:
        return {"kind":"fullsim_learning_profile_v1","domain":domain,"n_benchmarks":0,
                "full_simulation_reliability":0.5,"world_uncertainty_multiplier":1.0,
                "adaptive_fullsim_weight":None,"status":"NO_HISTORY"}
    fs_mae = float(np.mean([r["fs"]["mae_pp"] for r in rows]))
    fs_cov = [r["fs"].get("coverage_95") for r in rows if r["fs"].get("coverage_95") is not None]
    reliability = _clip(math.exp(-fs_mae / 12.0) * math.sqrt(len(rows)/(len(rows)+4)), 0.05, 0.95)
    coverage = float(np.mean(fs_cov)) if fs_cov else None
    unc_mult = 1.0
    if coverage is not None:
        # Too-narrow historical intervals -> widen future worlds; conservative cap.
        unc_mult = _clip(1.0 + max(0.0, 0.90-coverage)*1.8, 0.85, 1.6)
    pairs = [r for r in rows if r["core"]]
    weight = None
    if len(pairs) >= 3:
        delta = float(np.mean([r["core"]["mae_pp"] - r["fs"]["mae_pp"] for r in pairs]))
        # Smoothly move from safer core to FullSim; never fully discard either.
        weight = _clip(1/(1+math.exp(-delta/2.5)), 0.20, 0.80)
    return {
        "kind":"fullsim_learning_profile_v1","domain":domain,"created_at":_now(),
        "n_benchmarks":len(rows),"benchmark_run_ids":[r["run_id"] for r in rows],
        "mean_fullsim_mae_pp":round(fs_mae,4),"historical_coverage_95":round(coverage,4) if coverage is not None else None,
        "full_simulation_reliability":round(reliability,4),"world_uncertainty_multiplier":round(unc_mult,4),
        "adaptive_fullsim_weight":round(weight,4) if weight is not None else None,
        "status":"ACTIVE" if len(rows)>=3 else "EARLY_HISTORY",
    }


# ---------------------------------------------------------------------------
# persistence and benchmark registry


def _run_dir(run_id: str) -> Path:
    return RUN_ROOT / _slug(run_id, 90)


def _bench_dir(run_id: str) -> Path:
    return BENCH_ROOT / _slug(run_id, 90)


def list_runs(limit: int = 100) -> list[dict[str, Any]]:
    rows = []
    for d in sorted([p for p in RUN_ROOT.iterdir() if p.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True):
        p = d / "prediction_manifest.json"
        if not p.exists():
            continue
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
            rows.append({
                "run_id": d.name, "created_at": m.get("created_at"), "topic": m.get("topic"),
                "domain": m.get("domain"), "objective": m.get("objective"), "worlds": m.get("worlds"),
                "n": m.get("n"), "benchmark_eligible": m.get("benchmark_eligible"),
                "manifest_sha256": m.get("manifest_sha256"),
            })
        except Exception:
            continue
        if len(rows) >= limit:
            break
    return rows


def load_run(run_id: str) -> dict[str, Any]:
    d = _run_dir(run_id)
    if not d.exists():
        raise FileNotFoundError(f"Full Simulation run nenalezen: {run_id}")
    out = {"run_id": run_id}
    for name in ("prediction_manifest.json", "prediction.json", "world_model.json", "research_snapshot.json", "learning_profile.json"):
        p = d / name
        if p.exists():
            out[name.removesuffix(".json")] = json.loads(p.read_text(encoding="utf-8"))
    return out


def register_external_prediction(run_id: str, method: str, prediction: dict[str, Any], *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    d = _bench_dir(run_id); d.mkdir(parents=True, exist_ok=True)
    truth_exists = (d / "truth.json").exists()
    status = "POST_HOC_EXCLUDED" if truth_exists else "PRE_TRUTH_ELIGIBLE"
    obj = {"kind":"external_prediction_v1","run_id":run_id,"method":str(method).strip()[:120],
           "submitted_at":_now(),"status":status,"prediction":prediction,"metadata":metadata or {}}
    obj["sha256"] = _sha_json(obj)
    sd = d / "submissions"; sd.mkdir(exist_ok=True)
    p = sd / f"{_slug(method,70)}.json"; p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    return obj


def record_truth(run_id: str, truth: dict[str, Any]) -> dict[str, Any]:
    run = load_run(run_id)
    mani = run.get("prediction_manifest") or {}
    bdir = _bench_dir(run_id); bdir.mkdir(parents=True, exist_ok=True)
    tp = bdir / "truth.json"
    if tp.exists():
        raise RuntimeError("Truth už byla k tomuto frozen runu zapsána; benchmark je immutable.")
    questions = truth.get("questions") or {}
    if not isinstance(questions, dict) or not questions:
        raise ValueError("truth.questions musi obsahovat qid -> {truth_pct:{...}}")
    eligible = bool(mani.get("benchmark_eligible"))
    truth_obj = {
        "kind":"npc_full_simulation_truth_v1","run_id":run_id,"revealed_at":_now(),
        "source":truth.get("source", ""),"source_url":truth.get("source_url", ""),
        "fieldwork_start":truth.get("fieldwork_start", ""),"fieldwork_end":truth.get("fieldwork_end", ""),
        "human_n":truth.get("human_n"),"methodology":truth.get("methodology", ""),
        "domain":truth.get("domain") or mani.get("domain") or "general","questions":questions,
        "rows":truth.get("rows") or [],"weight_column":truth.get("weight_column") or "weight",
        "prediction_manifest_sha256":mani.get("manifest_sha256"),
        "benchmark_eligibility":"BLIND_ELIGIBLE" if eligible else "CONTAMINATED_EXCLUDED",
        "note":"Eligibility is inherited from the frozen prediction; truth cannot retroactively make a scenario run blind.",
    }
    truth_obj["sha256"] = _sha_json(truth_obj)
    tp.write_text(json.dumps(truth_obj,ensure_ascii=False,indent=2),encoding="utf-8")

    predictions = run.get("prediction", {}).get("methods", {})
    methods = {}
    from fullsim_learning import counterintuitive_score, joint_structure_score, demographic_inflation_score, residual_learning_profile
    for method, pred in predictions.items():
        methods[method] = score_prediction(pred, truth_obj)
        methods[method]["counterintuitive"] = counterintuitive_score(pred, truth_obj)
    sd = bdir / "submissions"
    if sd.exists():
        for p in sd.glob("*.json"):
            try:
                x = json.loads(p.read_text(encoding="utf-8"))
                if x.get("status") != "PRE_TRUTH_ELIGIBLE":
                    continue
                methods[x["method"]] = score_prediction(x["prediction"], truth_obj)
                methods[x["method"]]["counterintuitive"] = counterintuitive_score(x["prediction"], truth_obj)
            except Exception:
                continue
    joint_diag=None; demo_inflation=None
    if truth_obj.get("rows"):
        try:
            synp=_run_dir(run_id)/"synthetic_response_sample.csv.gz"
            if synp.exists():
                syn=pd.read_csv(synp); hum=pd.DataFrame(truth_obj["rows"])
                qids=sorted(set(questions) & set(syn.columns) & set(hum.columns))
                if len(qids)>=2: joint_diag=joint_structure_score(syn,hum,qids)
                if qids: demo_inflation=demographic_inflation_score(syn,hum,qids)
        except Exception:
            joint_diag=None; demo_inflation=None
    scores = {"kind":"npc_full_simulation_scores_v2","run_id":run_id,"created_at":_now(),"methods":methods,
              "benchmark_eligibility":truth_obj["benchmark_eligibility"],
              "joint_structure_diagnostic":joint_diag,"demographic_inflation":demo_inflation}
    scores["sha256"] = _sha_json(scores)
    (bdir/"scores.json").write_text(json.dumps(scores,ensure_ascii=False,indent=2),encoding="utf-8")
    lb = leaderboard()
    (BENCH_ROOT/"LEADERBOARD.json").write_text(json.dumps(lb,ensure_ascii=False,indent=2),encoding="utf-8")
    report_path=write_benchmark_html(bdir,truth_obj,scores,lb)
    prof = learning_profile(truth_obj["domain"])
    (BENCH_ROOT/"LEARNING_PROFILE.json").write_text(json.dumps(prof,ensure_ascii=False,indent=2),encoding="utf-8")
    residual = residual_learning_profile(run_root=RUN_ROOT,bench_root=BENCH_ROOT,domain=truth_obj["domain"])
    (BENCH_ROOT/f"RESIDUAL_LEARNING_{_slug(truth_obj['domain'],50)}.json").write_text(json.dumps(residual,ensure_ascii=False,indent=2),encoding="utf-8")
    try:
        from research_arena import write_arena_html
        arena_path=write_arena_html(BENCH_ROOT,BENCH_ROOT/"RESEARCH_ARENA.html")
    except Exception:
        arena_path=None
    return {"truth":truth_obj,"scores":scores,"leaderboard":lb,"learning_profile":prof,"residual_learning":residual,
            "research_arena_html":str(arena_path) if arena_path else None,"report_html":str(report_path)}


# ---------------------------------------------------------------------------
# prepare + execute


def prepare_full_simulation(spec_obj: dict[str, Any] | FullSimulationSpec, *, panel_path: str | Path | None = None,
                            mock_research: dict[str, Any] | None = None,
                            mock_world_model: dict[str, Any] | None = None,
                            existing_research: dict[str, Any] | None = None,
                            progress=None) -> dict[str, Any]:
    spec = spec_obj if isinstance(spec_obj, FullSimulationSpec) else FullSimulationSpec.from_obj(spec_obj)
    _progress = progress if callable(progress) else (lambda _x: None)
    _progress("Scénářový model · načítám audience a projekt")
    if spec.objective == SCENARIO and spec.mode != "dry" and str((spec.scenario_contract or {}).get("status") or "") != "APPROVED":
        raise ValueError("LIVE scénář vyžaduje schválený scenario delta contract. Nejprve scénář zkompilujte a schvalte.")
    panel = Panel.load(panel_path or PANEL_PATH, min_vek=0 if panel_path and Path(panel_path).resolve() != Path(PANEL_PATH).resolve() else 18, hlasit=False)
    # Research follows the explicitly selected provider, including Claude Code subscription.
    _pa=__import__("provider_auth")
    _research_provider=_pa.normalize_ai_provider(spec.provider)
    research_ready=bool(_pa.provider_key_ready(_research_provider))
    research_cfg = ResearchConfig(
        enabled=bool(spec.research_enabled and (research_ready or mock_research is not None)),
        topic=spec.topic, max_sources_per_agent=spec.research_max_sources,
        strict_consensus=False, allow_single_agent_primary=True, allow_degraded_single_agent=True,
        max_context_blocks=12,
    )
    existing_research = existing_research or {}
    if spec.research_enabled and (existing_research.get("accepted") or existing_research.get("quarantined")):
        _progress("Scénářový model · používám existující Evidence Pack")
        research = ResearchBundle(
            True, spec.topic, str(existing_research.get("created_at") or _now()), [],
            list(existing_research.get("accepted") or []), list(existing_research.get("quarantined") or []),
            dict(existing_research.get("config") or asdict(research_cfg)),
            quality_status=str(existing_research.get("quality_status") or "REUSED_PROJECT_EVIDENCE_PACK"),
            sha256=str(existing_research.get("sha256") or ""),
        )
        if not research.sha256: research.finalize_hash()
    elif research_cfg.enabled:
        _progress("Scénářový model · Research Context hledá relevantní evidenci")
        research = run_dual_research(research_cfg, spec.questions, mock_agents=mock_research, provider_override=_research_provider, progress=_progress)
    else:
        _progress("Scénářový model · bez nového research (offline / vypnuto)")
        research = ResearchBundle(False, spec.topic, _now(), [], [], [], asdict(research_cfg), quality_status="OFFLINE_NO_KEY_OR_DISABLED").finalize_hash()
    from fullsim_learning import (
        annotate_relationship_provenance, stereotype_adversary, adversarial_world_model,
        residual_learning_profile,
    )
    _progress("Scénářový model · AI staví world model z mechanismů a Evidence Packu")
    wm = build_world_model(spec, research, panel.df, mock_model=mock_world_model)
    _progress("Scénářový model · kontroluji provenance, support a stereotype risk")
    wm = annotate_relationship_provenance(wm)
    stereotype = stereotype_adversary(wm)
    # Internal-use Full Simulation may be bold, but the default model should not
    # amplify unsupported demographic caricatures. Strong unobserved demographic
    # slopes are automatically shrunk while the original risk is preserved in the audit.
    if spec.anti_stereotype_guard and stereotype.get("risk") == "HIGH":
        original_sha = wm.get("sha256")
        wm = adversarial_world_model(wm, "shrink")
        wm["anti_stereotype_adjustment"] = {
            "applied": True, "mode": "shrink", "pre_adjustment_sha256": original_sha,
            "reason": "strong unsupported demographic dependencies",
        }
        wm = annotate_relationship_provenance(wm)
        wm["sha256"] = _sha_json({k:v for k,v in wm.items() if k != "sha256"})
    else:
        wm["anti_stereotype_adjustment"] = {"applied": False, "mode": "audit_only"}
        wm["sha256"] = _sha_json({k:v for k,v in wm.items() if k != "sha256"})
    profile = learning_profile(spec.domain)
    residual_profile = residual_learning_profile(run_root=RUN_ROOT, bench_root=BENCH_ROOT, domain=spec.domain)
    accepted, leaks = _research_items(research, spec.objective)
    return {
        "spec":asdict(spec),"research":asdict(research),"world_model":wm,"learning_profile":profile,
        "residual_learning_profile": residual_profile, "anti_stereotype": stereotype,
        "research_summary":{"quality_status":research.quality_status,"accepted":len(accepted),"target_overlap_available":len(leaks)},
        "benchmark_eligible": bool(spec.objective == BLIND and not wm.get("contaminated_for_predictive_benchmark")),
    }



def _base_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Main forecast always uses the exact base wording; variants are diagnostics."""
    out=[]
    for q in questions:
        x=dict(q); x.pop("variants",None); out.append(x)
    return out


def _auto_paraphrase_sets(spec: FullSimulationSpec, base_questions: list[dict[str, Any]]) -> list[tuple[str,list[dict[str,Any]]]]:
    """Generate two semantics-preserving wording variants with one cheap LLM call.

    Failure is non-fatal. The immutable base wording remains the main forecast and
    reverse-option-order stress is available even offline.
    """
    from provider_auth import provider_key_ready
    if not spec.auto_wording_stress or spec.mode == "dry" or not provider_key_ready(spec.provider):
        return []
    try:
        prompt = """Create TWO neutral Czech paraphrases for each survey question below. Preserve meaning, reference period, response scale and polarity exactly. Do not make a question more positive/negative and do not mention this instruction. Return JSON only: {\"questions\":{\"qid\":[\"variant 1\",\"variant 2\"]}}.\n\n""" + json.dumps([
            {"id":q["id"],"text":q["text"],"categories":q.get("kategorie",[])} for q in base_questions
        ],ensure_ascii=False)
        from ai_router import call_text
        rr=call_text({"messages":[{"role":"user","content":prompt}]},anthropic_model=resolve_model("sonnet"),openai_model=resolve_provider_model("openai", spec.model) if spec.provider=="openai" else None,max_tokens=1800,prefer=spec.provider,allow_fallback=False)
        if rr.get("chyba"): raise RuntimeError(rr["chyba"])
        raw=_extract_json(rr.get("text") or ""); byid=raw.get("questions") or {}
        sets=[]
        for vi in range(2):
            qs=[]; ok=False
            for q in base_questions:
                x=dict(q); vv=byid.get(q["id"]) or []
                if vi < len(vv) and isinstance(vv[vi],str) and len(vv[vi].strip())>=5:
                    x["text"]=vv[vi].strip()[:1000]; ok=True
                qs.append(x)
            if ok: sets.append((f"PARAPHRASE_{vi+1}",qs))
        return sets
    except Exception:
        return []


def _stress_question_sets(spec: FullSimulationSpec, base_questions: list[dict[str, Any]]) -> list[tuple[str,list[dict[str,Any]]]]:
    sets=[("ORIGINAL",base_questions)]
    rev=[]
    for q in base_questions:
        x=dict(q); x["kategorie"]=list(reversed(q.get("kategorie") or [])); rev.append(x)
    sets.append(("REVERSE_OPTIONS",rev))
    # Explicit author-provided variants are stronger than automatically generated ones.
    maxv=max([len(q.get("variants") or []) for q in spec.questions] or [0])
    for vi in range(min(maxv,3)):
        qs=[]; used=False
        for qbase,qsrc in zip(base_questions,spec.questions):
            x=dict(qbase); vs=qsrc.get("variants") or []
            if vi < len(vs) and isinstance(vs[vi],dict) and str(vs[vi].get("text") or "").strip():
                x["text"]=str(vs[vi]["text"]).strip(); used=True
            qs.append(x)
        if used: sets.append((f"AUTHOR_VARIANT_{vi+1}",qs))
    if spec.diagnostic_mode == "max":
        sets.extend(_auto_paraphrase_sets(spec,base_questions))
    # unique labels only
    out=[]; seen=set()
    for name,qs in sets:
        if name not in seen: out.append((name,qs));seen.add(name)
    return out


def _model_alias(model_id: str) -> str:
    from runtime_config import MODELS
    mid=resolve_model(model_id)
    for a,m in MODELS.items():
        if m.model_id==mid:return a.upper()
    return re.sub(r"[^A-Za-z0-9]+","_",mid)[:30].upper()

def _save_overlay(df: pd.DataFrame, factor_cols: list[str], path: Path) -> str:
    cols = [c for c in ["panel_row_id", *factor_cols, "FS_SIMULATION_PROFILE", "FS_WORLD_ID", "FS_WORLD_SEED", "FS_WORLD_MODEL_SHA256", "FS_EPISTEMIC_STATUS"] if c in df.columns]
    small = df[cols]
    try:
        small.to_parquet(path.with_suffix(".parquet"), index=False, compression="zstd")
        return str(path.with_suffix(".parquet"))
    except Exception:
        small.to_csv(path.with_suffix(".csv.gz"), index=False, compression="gzip")
        return str(path.with_suffix(".csv.gz"))


def _load_json(path: Path, default=None):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return default

def _resume_signature(spec: FullSimulationSpec) -> str:
    obj=asdict(spec);obj.pop("budget_max_usd",None);obj.pop("resume_run_id",None);obj.pop("notes",None);return _sha_json(obj)

def _checkpoint_result(rr):
    return {"vysledky":rr.get("vysledky") or {},"budget":rr.get("budget") or {},"naklady_usd":rr.get("naklady_usd") or 0.0,"run_status":rr.get("run_status")}

def run_full_simulation(spec_obj: dict[str, Any] | FullSimulationSpec, *, panel_path: str | Path | None = None,
                        prepared: dict[str, Any] | None = None,
                        mock_research: dict[str, Any] | None = None,
                        mock_world_model: dict[str, Any] | None = None,
                        core_baseline_override: dict[str, Any] | None = None,
                        progress=None) -> dict[str, Any]:
    from dotaznik import run_dotaznik

    spec = spec_obj if isinstance(spec_obj, FullSimulationSpec) else FullSimulationSpec.from_obj(spec_obj)
    _progress = progress if callable(progress) else (lambda _x: None)
    _progress("Full Simulation · načítám zmrazený scénář a vzorek")
    base_panel = Panel.load(panel_path or PANEL_PATH, min_vek=0 if panel_path and Path(panel_path).resolve() != Path(PANEL_PATH).resolve() else 18, hlasit=False)
    source_path = Path(panel_path or PANEL_PATH).resolve();resumed=bool(spec.resume_run_id)
    if resumed:
        run_id=str(spec.resume_run_id);d=_run_dir(run_id)
        if not d.exists():raise FileNotFoundError(f"Resume run neexistuje: {run_id}")
        old=_load_json(d/"spec.json",{}) or {};old_sig=_load_json(d/"resume_state.json",{}).get("spec_signature") or _sha_json({k:v for k,v in old.items() if k not in {"budget_max_usd","resume_run_id","notes"}})
        if old_sig!=_resume_signature(spec):raise RuntimeError("Resume odmítnut: změnil se zmrazený scénář/sample/model/provider.")
        prep=_load_json(d/"prepare_snapshot.json") or {"research":_load_json(d/"research_snapshot.json",{}),"world_model":_load_json(d/"world_model.json",{}),"learning_profile":_load_json(d/"learning_profile.json",{}),"residual_learning_profile":{},"anti_stereotype":{},"research_summary":{},"benchmark_eligible":False}
    else:
        prep=prepared or prepare_full_simulation(spec,panel_path=panel_path,mock_research=mock_research,mock_world_model=mock_world_model,progress=_progress);run_id=time.strftime("%Y%m%d_%H%M%S")+"_fs_"+_sha_json({"topic":spec.topic,"seed":spec.seed,"questions":spec.questions})[:10];d=_run_dir(run_id)
        if d.exists():raise RuntimeError(f"run dir uz existuje: {d}")
        (d/"worlds").mkdir(parents=True);base=asdict(spec);base["resume_run_id"]=None;(d/"spec.json").write_text(json.dumps(base,ensure_ascii=False,indent=2),encoding="utf-8");(d/"prepare_snapshot.json").write_text(json.dumps(prep,ensure_ascii=False,indent=2,default=str),encoding="utf-8");(d/"world_model.json").write_text(json.dumps(prep["world_model"],ensure_ascii=False,indent=2),encoding="utf-8");(d/"research_snapshot.json").write_text(json.dumps(prep["research"],ensure_ascii=False,indent=2,default=str),encoding="utf-8");(d/"learning_profile.json").write_text(json.dumps(prep.get("learning_profile") or {},ensure_ascii=False,indent=2),encoding="utf-8")
    wm=prep["world_model"];profile=prep.get("learning_profile") or learning_profile(spec.domain)

    # Production respondent calls are fail-closed on Anthropic and share one hard
    # budget across worlds, baselines and diagnostics. A batch request with a hard
    # cap is executed as per-call sync inside pipeline so the cap can be enforced
    # before each paid request.
    live = spec.mode != "dry"
    provider_policy = ("strict_" + spec.provider) if live else "dry_local_only"
    resume_state=_load_json(d/"resume_state.json",{}) or {};spent_total_usd=float(resume_state.get("spent_usd") or 0.0) if resumed else 0.0;survey_spend=dict(resume_state.get("survey_spend") or {});budget_exhausted=False

    def _run_survey(qs, **kwargs):
        nonlocal spent_total_usd, budget_exhausted
        remaining = None
        if live and spec.budget_max_usd is not None:
            remaining = max(0.0, float(spec.budget_max_usd) - spent_total_usd)
            if remaining <= 1e-9:
                budget_exhausted = True
                return None
        key=str(kwargs.pop("_checkpoint_key","") or "");sd=d/"survey_checkpoints"/key if key else None
        if sd:
            sd.parent.mkdir(parents=True,exist_ok=True)
            if (sd/"manifest.json").exists() and (sd/"checkpoint.pkl").exists():kwargs["resume_dir"]=sd
            else:kwargs["run_dir"]=sd;kwargs["checkpoint"]=True
        rr=run_dotaznik(qs,provider_policy=provider_policy,budget_max_usd=remaining,**kwargs)
        b = rr.get("budget") or {}
        spent = b.get("spent_usd")
        if spent is None:
            spent = rr.get("naklady_usd") or 0.0
        current=max(0.0,float(spent or 0.0));prior=float(survey_spend.get(key) or 0.0) if key else 0.0;spent_total_usd += max(0.0,current-prior) if key else current
        if key:survey_spend[key]=current
        if rr.get("run_status") == "PARTIAL_BUDGET_CAP":
            budget_exhausted = True
        if live and spec.budget_max_usd is not None and spent_total_usd >= float(spec.budget_max_usd) - 1e-9:
            budget_exhausted = True
        return rr

    base_questions = _base_questions(spec.questions)
    qids = [q["id"] for q in base_questions]
    world_results=[]
    world_meta=[]
    for cp in sorted((d/"worlds").glob("world_*_result.json")):
        z=_load_json(cp)
        if z:world_results.append(z)
    for mp in sorted((d/"worlds").glob("world_[0-9][0-9][0-9].json")):
        z=_load_json(mp)
        if z:world_meta.append(z)
    completed_worlds=len(world_results)
    world_response_frames = []
    convergence = {"converged":False,"worlds":0,"reason":"NOT_CHECKED"}
    factor_cols = [f"FS_{f['id']}_10" for f in wm["factors"]]
    from fullsim_learning import world_convergence, demographic_overdetermination_guard
    pretruth_demo_guard = None
    first_inoculated = None
    for wi in range(completed_worlds,spec.worlds):
        _progress(f"Full Simulation · svět {wi+1}/{spec.worlds} · aplikuji world model a sbírám odpovědi")
        inoculated, meta = inoculate_population(base_panel.df, wm, world_index=wi, seed=spec.seed,
                                                 learning_profile=(profile if spec.use_learning_profile else None))
        if first_inoculated is None:
            first_inoculated = inoculated.copy()
            pretruth_demo_guard = demographic_overdetermination_guard(first_inoculated, factor_cols=factor_cols)
        p = Panel(inoculated, min_vek=base_panel.min_vek)
        p.source_path = source_path
        rr = _run_survey(
            base_questions, n=spec.n, panel=p, panel_path=source_path, model=spec.model, mode=spec.mode,
            seed=spec.seed, ulozit=False, tichy=True, persona_mode=spec.persona_mode,
            response_mode="probability", allow_own_estimates=True, _checkpoint_key=f"world_{wi+1:03d}",
        )
        if rr is None:break
        if rr.get("run_status")=="PARTIAL_BUDGET_CAP":
            (d/"resume_state.json").write_text(json.dumps({"spec_signature":_resume_signature(spec),"completed_worlds":len(world_results),"spent_usd":spent_total_usd,"survey_spend":survey_spend,"status":"WAITING_CREDITS"},ensure_ascii=False,indent=2),encoding="utf-8");break
        world_results.append(rr);(d/"worlds"/f"world_{wi+1:03d}_result.json").write_text(json.dumps(_checkpoint_result(rr),ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        meta["result_summary"] = {qid: _extract_dist((rr.get("vysledky") or {}).get(qid, {})) for qid in qids}
        if spec.save_world_overlays:
            meta["overlay_file"] = _save_overlay(inoculated, factor_cols, d/"worlds"/f"world_{wi+1:03d}_overlay")
        (d/"worlds"/f"world_{wi+1:03d}.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        world_meta=[m for m in world_meta if int(m.get("world_index",-999))!=int(meta.get("world_index",wi))];world_meta.append(meta)
        (d/"resume_state.json").write_text(json.dumps({"spec_signature":_resume_signature(spec),"completed_worlds":len(world_results),"spent_usd":spent_total_usd,"survey_spend":survey_spend,"status":"RUNNING"},ensure_ascii=False,indent=2),encoding="utf-8")
        if budget_exhausted:
            # Keep the paid partial world, but do not start another world/baseline.
            break
        # Small respondent-level audit sample for later joint/human calibration diagnostics.
        det=rr.get("detail")
        if isinstance(det,pd.DataFrame) and len(det):
            keep=[c for c in ["synthetic_case_id","pohlavi","vek","vzdelani","kraj","velikost_obce","_analysis_weight",*qids] if c in det.columns]
            sm=det[keep].head(min(500,len(det))).copy(); sm["_world_id"]=meta["world_id"]
            world_response_frames.append(sm)
        if spec.adaptive_worlds and len(world_results) >= spec.min_worlds:
            convergence = world_convergence(world_results, base_questions, threshold_pp=spec.world_convergence_pp)
            if convergence.get("converged"):
                break

    _progress("Full Simulation · agreguji světy a kontroluji konvergenci")
    if not world_results:
        raise RuntimeError("FULLSIM_NO_WORLD_RESULTS: simulace nevytvořila žádný dokončený svět.")
    ensemble = ensemble_world_results(world_results, base_questions)
    ensemble["adaptive_worlds"]={"planned":spec.worlds,"executed":len(world_results),**convergence}
    if world_response_frames:
        synth=pd.concat(world_response_frames,ignore_index=True)
        synth.to_csv(d/"synthetic_response_sample.csv.gz",index=False,compression="gzip")
    if pretruth_demo_guard is not None:
        (d/"demographic_guard.json").write_text(json.dumps(pretruth_demo_guard,ensure_ascii=False,indent=2),encoding="utf-8")
    methods: dict[str, Any] = {"FULL_SIMULATION": ensemble}

    # Safer baselines use the un-inoculated population, same question wording/model/sample seed.
    core_pred = None
    if spec.include_core_baseline and core_baseline_override:
        # Batch variants share one untouched-population baseline. This is both faster
        # and methodologically cleaner: scenario worlds remain independent, while the
        # counterfactual reference is literally identical across the comparison.
        _progress("Full Simulation · používám společný frozen baseline NPC Core")
        core_pred = deepcopy(core_baseline_override)
        methods["NPC_CORE"] = core_pred
    elif spec.include_core_baseline and not budget_exhausted:
        _progress("Full Simulation · počítám baseline NPC Core")
        r = _run_survey(base_questions, n=spec.n, panel=base_panel, panel_path=source_path, model=spec.model,
                         mode=spec.mode, seed=spec.seed, ulozit=False, tichy=True, persona_mode="core",
                         response_mode="probability", allow_own_estimates=False, _checkpoint_key="baseline_core")
        if r is not None:
            core_pred = _single_run_prediction(r, base_questions, "npc_core")
            methods["NPC_CORE"] = core_pred
    if spec.include_demographics_baseline and not budget_exhausted:
        _progress("Full Simulation · počítám demographics baseline")
        r = _run_survey(base_questions, n=spec.n, panel=base_panel, panel_path=source_path, model=spec.model,
                         mode=spec.mode, seed=spec.seed, ulozit=False, tichy=True, persona_mode="demographics",
                         response_mode="probability", allow_own_estimates=False, _checkpoint_key="baseline_demographics")
        if r is not None:
            methods["NPC_DEMOGRAPHICS"] = _single_run_prediction(r, base_questions, "npc_demographics")
    if spec.use_learning_profile and core_pred and profile.get("adaptive_fullsim_weight") is not None:
        methods["NPC_SIM_HISTORY_BLEND"] = blend_predictions(ensemble, core_pred, float(profile["adaptive_fullsim_weight"]), label="npc_sim_history_blend")

    _progress("Full Simulation · kontroluji robustnost, citlivost a historickou kalibraci")
    from fullsim_learning import (
        apply_residual_correction, compare_prediction_methods, prediction_features,
        meta_error_forecast, decision_router,
    )
    residual_profile = prep.get("residual_learning_profile") or {}
    learned_pred, learned_meta = apply_residual_correction(ensemble, residual_profile)
    if learned_meta.get("n_hits"):
        methods["NPC_SIM_LEARNED"] = learned_pred

    # Diagnostic matrix is intentionally separate from client-facing methods.
    # It may change wording/order/model/noise and therefore must not be scored as
    # if it were the exact frozen survey instrument.
    diag_methods: dict[str,Any] = {}
    if spec.diagnostic_mode != "off" and first_inoculated is not None and world_results and not budget_exhausted:
        alias=_model_alias(spec.model)
        diag_methods[f"FULLSIM_DIAG__{alias}__ORIGINAL__NOISE_1.0"] = _single_run_prediction(world_results[0], base_questions, "diagnostic_original")
        stress_sets=_stress_question_sets(spec,base_questions)
        diag_models=[spec.model]
        if spec.diagnostic_mode == "max":
            diag_models=list(dict.fromkeys([spec.model,resolve_model("haiku"),resolve_model("sonnet")]))
        temps=[1.0] if spec.diagnostic_mode=="smart" else [0.85,1.0,1.15]
        diag_panel=Panel(first_inoculated,min_vek=base_panel.min_vek); diag_panel.source_path=source_path
        for mi,mdl in enumerate(diag_models):
            for si,(sname,qs) in enumerate(stress_sets):
                if mi==0 and sname=="ORIGINAL":
                    # original/current-model/noise=1 already came from world 1
                    continue
                # smart mode only needs reverse order + any explicit author variant;
                # max mode additionally uses generated paraphrases and model/noise matrix.
                for temp in temps:
                    if spec.diagnostic_mode=="smart" and temp!=1.0: continue
                    rr=_run_survey(qs,n=min(spec.diagnostic_n,spec.n),panel=diag_panel,panel_path=source_path,
                                    model=mdl,mode=spec.mode,seed=spec.seed+88000+mi*1000+si*100+int(temp*10),
                                    ulozit=False,tichy=True,persona_mode=spec.persona_mode,response_mode="probability",
                                    allow_own_estimates=True,dispersion_config={"temperature":temp},min_effective_n=25)
                    if rr is None:
                        budget_exhausted=True; break
                    name=f"FULLSIM_DIAG__{_model_alias(mdl)}__{sname}__NOISE_{temp}"
                    diag_methods[name]=_single_run_prediction(rr,qs,"diagnostic")
                    if budget_exhausted: break
        # max mode also isolates response-noise ablation on exact wording/current model.
        if spec.diagnostic_mode=="max":
            for temp in (0.85,1.15):
                if budget_exhausted: break
                rr=_run_survey(base_questions,n=min(spec.diagnostic_n,spec.n),panel=diag_panel,panel_path=source_path,
                                model=spec.model,mode=spec.mode,seed=spec.seed+99000+int(temp*100),ulozit=False,tichy=True,
                                persona_mode=spec.persona_mode,response_mode="probability",allow_own_estimates=True,
                                dispersion_config={"temperature":temp},min_effective_n=25)
                if rr is None: break
                diag_methods[f"FULLSIM_DIAG__{alias}__ORIGINAL__NOISE_{temp}"]=_single_run_prediction(rr,base_questions,"diagnostic_noise")
    robustness = compare_prediction_methods(diag_methods) if diag_methods else {
        "kind":"npc_fullsim_robustness_v1","model_disagreement_pp":{},"prompt_sensitivity_pp":{},
        "response_noise_sensitivity_pp":{},"top_category_rank_flip":{},"fragile_questions":[],"status":"DIAGNOSTICS_OFF"
    }
    feature_map={}
    pre_prediction={"methods":{"FULL_SIMULATION":ensemble}}
    for q in base_questions:
        feature_map[q["id"]]=prediction_features(qid=q["id"],q=q,prediction=pre_prediction,diagnostics=robustness,
                                                  research_summary=prep.get("research_summary"),world_model=wm)
    meta_error=meta_error_forecast(feature_map,run_root=RUN_ROOT,bench_root=BENCH_ROOT,domain=spec.domain)
    router=decision_router(meta_error=meta_error,robustness=robustness,stereotype=prep.get("anti_stereotype"),
                           learning_profile=profile,benchmark_eligible=bool(prep.get("benchmark_eligible")),
                           human_calibration_n=0)
    (d/"diagnostic_methods.json").write_text(json.dumps(diag_methods,ensure_ascii=False,indent=2),encoding="utf-8")
    (d/"robustness.json").write_text(json.dumps(robustness,ensure_ascii=False,indent=2),encoding="utf-8")
    (d/"meta_features.json").write_text(json.dumps({"questions":feature_map},ensure_ascii=False,indent=2),encoding="utf-8")
    (d/"meta_error.json").write_text(json.dumps(meta_error,ensure_ascii=False,indent=2),encoding="utf-8")
    (d/"decision_router.json").write_text(json.dumps(router,ensure_ascii=False,indent=2),encoding="utf-8")
    sim_method = "NPC_SIM_LEARNED" if "NPC_SIM_LEARNED" in methods else ("NPC_SIM_HISTORY_BLEND" if "NPC_SIM_HISTORY_BLEND" in methods else "FULL_SIMULATION")
    prediction = {
        "kind":"npc_full_simulation_prediction_v2","run_id":run_id,"created_at":_now(),
        "topic":spec.topic,"domain":spec.domain,"objective":spec.objective,"methods":methods,
        "primary_method":sim_method,
        "user_modes":{"CORE":"NPC_CORE" if "NPC_CORE" in methods else None,"SIM":sim_method,"HYBRID":"AVAILABLE_AFTER_HUMAN_CALIBRATION"},
        "decision_router":router,"meta_error":meta_error,"robustness":robustness,
        "demographic_guard":pretruth_demo_guard,"anti_stereotype":prep.get("anti_stereotype"),
        "world_model_sha256":wm["sha256"],"research_sha256":prep["research"].get("sha256"),
        "learning_profile_sha256":_sha_json(profile),"residual_learning_sha256":residual_profile.get("sha256"),
        "benchmark_eligible": bool(prep.get("benchmark_eligible")) and not budget_exhausted,
        "run_status":"PARTIAL_BUDGET_CAP" if budget_exhausted else ("INVALID_DRY_RUN" if spec.mode=="dry" else "COMPLETE"),
        "budget":{"max_usd":spec.budget_max_usd,"spent_usd":round(spent_total_usd,6),"exhausted":bool(budget_exhausted)},"resume_available":bool(budget_exhausted),"resume_run_id":run_id if budget_exhausted else None,
        "provider":spec.provider,"provider_policy":provider_policy,
        "epistemic_status":"PARTIAL_BUDGET_CAP" if budget_exhausted else ("EXPERIMENTAL_FORECAST" if prep.get("benchmark_eligible") else "EXPERIMENTAL_SCENARIO_CONTAMINATED"),
        "synthetic_only_recommended": not bool(router.get("abstain_from_synthetic_only")),
    }
    _progress("Full Simulation · zmrazuji predikci před truth a zapisuji audit")
    prediction["sha256"] = _sha_json(prediction)
    (d/"prediction.json").write_text(json.dumps(prediction,ensure_ascii=False,indent=2),encoding="utf-8")

    manifest = {
        "kind":"npc_full_simulation_prediction_manifest_v1","created_at":_now(),"release":RELEASE,
        "run_id":run_id,"topic":spec.topic,"domain":spec.domain,"objective":spec.objective,"n":spec.n,
        "worlds":len(world_results),"worlds_planned":spec.worlds,"worlds_executed":len(world_results),"adaptive_worlds":bool(spec.adaptive_worlds),
        "seed":spec.seed,"model":spec.model,"mode":spec.mode,"persona_mode":spec.persona_mode,
        "provider":spec.provider,"provider_policy":provider_policy,"budget_max_usd":spec.budget_max_usd,"spent_usd":round(spent_total_usd,6),"resumed":resumed,"resume_available":bool(budget_exhausted),
        "run_status":"PARTIAL_BUDGET_CAP" if budget_exhausted else ("INVALID_DRY_RUN" if spec.mode=="dry" else "COMPLETE"),
        "panel_path":str(source_path),"panel_sha256":_sha_bytes(source_path.read_bytes()),
        "world_model_sha256":wm["sha256"],"research_sha256":prep["research"].get("sha256"),
        "prediction_sha256":prediction["sha256"],"benchmark_eligible":bool(prep.get("benchmark_eligible")) and not budget_exhausted,
        "scenario_leakage_refs_used":wm.get("scenario_leakage_refs_used",[]),
        "methods":list(methods),"freeze_policy":"immutable_prediction_before_truth",
        "warning":"Full Simulation hypothesizes missing joint structure. It does not upgrade evidence tier or validation status.",
    }
    manifest["manifest_sha256"] = _sha_json(manifest)
    (d/"prediction_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    if budget_exhausted:
        (d/"PARTIAL.lock").write_text(manifest["manifest_sha256"]+"\n",encoding="utf-8")
        try:(d/"FROZEN.lock").unlink()
        except FileNotFoundError:pass
    else:
        (d/"FROZEN.lock").write_text(manifest["manifest_sha256"]+"\n",encoding="utf-8")
        try:(d/"PARTIAL.lock").unlink()
        except FileNotFoundError:pass
    (d/"resume_state.json").write_text(json.dumps({"spec_signature":_resume_signature(spec),"completed_worlds":len(world_results),"spent_usd":spent_total_usd,"survey_spend":survey_spend,"status":"WAITING_CREDITS" if budget_exhausted else "COMPLETE"},ensure_ascii=False,indent=2),encoding="utf-8")
    (d/"world_summary.json").write_text(json.dumps({"worlds":world_meta},ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    _progress("Full Simulation · generuji scénářový report")
    result_warnings=[]
    try:
        report_path=write_run_html(d,prediction,manifest,wm,prep.get("research_summary"),profile)
    except Exception as exc:
        result_warnings.append({'artifact':'simulation_report_html','error':str(exc)[:800]})
        report_path=_fallback_simulation_html(d/'FULL_SIMULATION_REPORT.html',prediction,manifest,str(exc))
        _progress("Full Simulation · HTML renderer selhal, použit nouzový report z frozen prediction")

    # Prime benchmark directory with pre-truth predictions. This does not reveal truth.
    bd = _bench_dir(run_id); bd.mkdir(parents=True, exist_ok=True)
    (bd/"frozen_prediction_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (bd/"meta_features.json").write_text(json.dumps({"questions":feature_map},ensure_ascii=False,indent=2),encoding="utf-8")
    _progress("Full Simulation · exportuji klientský dataset a delivery ZIP")
    client_outputs=export_simulation_client_outputs(d,prediction,manifest,report_path)
    result_warnings.extend(client_outputs.pop('artifact_warnings',[]) or [])
    _progress("Full Simulation · hotovo · predikce je zmrazená a report připraven")
    return {
        "run_id":run_id,"run_dir":str(d),"prediction":prediction,"manifest":manifest,"world_model":wm,
        "research_summary":prep.get("research_summary"),"learning_profile":profile,
        "robustness":robustness,"meta_error":meta_error,"decision_router":router,"demographic_guard":pretruth_demo_guard,
        "leaderboard":leaderboard(),"report_html":str(report_path),"results_status":"RESULTS_READY_DEGRADED_EXPORT" if result_warnings else "RESULTS_READY","artifact_warnings":result_warnings,**client_outputs,
    }




def _fallback_simulation_html(path: Path, prediction: dict[str,Any], manifest: dict[str,Any], reason: str='') -> Path:
    import html as _html
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);rows=[]
    for method,m in (prediction.get('methods') or {}).items():
        for qid,q in (m.get('questions') or {}).items():
            for cat,val in (q.get('estimate_pct') or {}).items(): rows.append(f'<tr><td>{_html.escape(str(method))}</td><td>{_html.escape(str(q.get("text") or qid))}</td><td>{_html.escape(str(cat))}</td><td>{_html.escape(str(val))}%</td></tr>')
    txt=("<!doctype html><meta charset='utf-8'><style>body{font:15px/1.6 Arial;max-width:1100px;margin:30px auto;padding:20px}.warn{background:#fff4d6;padding:12px}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:7px}</style>"
         +f"<div class='warn'>Nouzový export reportu. Frozen prediction je zachována. {_html.escape(str(reason))}</div><h1>Simulation results</h1><p>Run status: {_html.escape(str(prediction.get('run_status')))}</p><table><tr><th>Method</th><th>Question</th><th>Category</th><th>Estimate</th></tr>{''.join(rows)}</table>")
    p.write_text(txt,encoding='utf-8');return p

def export_simulation_client_outputs(run_dir: Path, prediction: dict[str,Any], manifest: dict[str,Any], report_path: Path) -> dict[str,Any]:
    """Create client-safe flat CSV/XLSX/ZIP. Core results survive renderer failure."""
    d=Path(run_dir); rows=[]; warnings=[]; methods=prediction.get('methods') or {}; core=methods.get('NPC_CORE') or {}; core_q=core.get('questions') or {}
    for method,m in methods.items():
        for qid,q in (m.get('questions') or {}).items():
            cats=sorted(set(q.get('estimate_pct') or {}))
            for cat in cats:
                val=(q.get('estimate_pct') or {}).get(cat); ci=(q.get('interval_95') or {}).get(cat) or {}; bv=((core_q.get(qid) or {}).get('estimate_pct') or {}).get(cat)
                try: delta=float(val)-float(bv) if bv is not None else None
                except Exception: delta=None
                rows.append({'method':method,'question_id':qid,'question':q.get('text') or qid,'category':cat,'estimate_pct':val,'baseline_core_pct':bv,'delta_vs_core_pp':delta,'interval_low':ci.get('low'),'interval_high':ci.get('high'),'run_id':prediction.get('run_id'),'run_status':prediction.get('run_status')})
    df=pd.DataFrame(rows)
    csvp=d/'SIMULATION_RESULTS.csv'; df.to_csv(csvp,index=False,encoding='utf-8-sig')
    xlsx=d/'SIMULATION_RESULTS.xlsx'
    try:
        with pd.ExcelWriter(xlsx,engine='openpyxl') as w:
            df.to_excel(w,index=False,sheet_name='Results')
            pd.DataFrame([{'key':k,'value':json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v} for k,v in manifest.items()]).to_excel(w,index=False,sheet_name='Manifest')
    except Exception as exc:
        warnings.append({'artifact':'simulation_results_xlsx','error':str(exc)[:800]})
        from openpyxl import Workbook
        wb=Workbook();ws=wb.active;ws.title='Results';ws.append(list(df.columns))
        for row in df.itertuples(index=False,name=None):ws.append(list(row))
        ms=wb.create_sheet('Manifest');ms.append(['key','value'])
        for k,v in manifest.items():ms.append([str(k),json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(dict,list)) else str(v)])
        wb.save(xlsx)
    zp=d/'SIMULATION_CLIENT_DELIVERY.zip'; files=[Path(report_path),csvp,xlsx,d/'prediction.json',d/'prediction_manifest.json',d/'FROZEN.lock'];checks=[]
    try:
        with zipfile.ZipFile(zp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for q in files:
                if q.is_file(): z.write(q,q.name);checks.append(f'{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}')
            z.writestr('DELIVERY_SHA256SUMS.txt','\n'.join(checks)+'\n');z.writestr('DELIVERY_NOTE.txt','Modelled scenario output. Frozen prediction is the source of truth for this package.\n')
    except Exception as exc:
        warnings.append({'artifact':'simulation_client_delivery_zip','error':str(exc)[:800]}); raise
    return {'results_csv':str(csvp),'results_xlsx':str(xlsx),'client_delivery_zip':str(zp),'artifact_warnings':warnings}


def validate_full_simulation_result(result: dict[str, Any], *, require_core_baseline: bool = True, allow_invalid_dry: bool = False) -> dict[str, Any]:
    """Fail closed unless a complete frozen client-facing artifact set exists."""
    r=dict(result or {}); pred=dict(r.get("prediction") or {}); manifest=dict(r.get("manifest") or {})
    methods=dict(pred.get("methods") or {}); problems=[]
    status=str(pred.get("run_status") or "")
    if not (status=="COMPLETE" or (allow_invalid_dry and status=="INVALID_DRY_RUN")):
        problems.append(f"run_status={status}")
    if "FULL_SIMULATION" not in methods and not any(k.startswith("NPC_SIM") for k in methods): problems.append("missing simulation prediction")
    if require_core_baseline and "NPC_CORE" not in methods: problems.append("missing NPC_CORE baseline")
    run_dir=Path(str(r.get("run_dir") or ""))
    if not run_dir.is_dir(): problems.append("run_dir missing")
    else:
        for name in ("prediction.json","prediction_manifest.json","FROZEN.lock","FULL_SIMULATION_REPORT.html","SIMULATION_RESULTS.csv","SIMULATION_RESULTS.xlsx","SIMULATION_CLIENT_DELIVERY.zip"):
            if not (run_dir/name).is_file() or (run_dir/name).stat().st_size<=0: problems.append(f"missing/empty {name}")
    report=Path(str(r.get("report_html") or "")) if r.get("report_html") else None
    if report is None or not report.is_file(): problems.append("report_html missing")
    if not manifest.get("manifest_sha256"): problems.append("manifest_sha256 missing")
    if problems: raise RuntimeError("FULLSIM_ARTIFACT_GATE_FAILED: "+"; ".join(problems))
    r["artifact_gate"]={"status":"PASS","frozen":True,"report":str(report),"methods":list(methods),"results_csv":str(run_dir/"SIMULATION_RESULTS.csv"),"results_xlsx":str(run_dir/"SIMULATION_RESULTS.xlsx"),"client_delivery_zip":str(run_dir/"SIMULATION_CLIENT_DELIVERY.zip")}
    return r


def _html_escape(x: Any) -> str:
    import html
    return html.escape(str(x if x is not None else ""))


def write_run_html(run_dir: Path, prediction: dict[str, Any], manifest: dict[str, Any],
                   world_model: dict[str, Any], research_summary: dict[str, Any] | None,
                   learning: dict[str, Any] | None) -> Path:
    primary = prediction.get("primary_method", "FULL_SIMULATION")
    sections=[]
    for method,m in (prediction.get("methods") or {}).items():
        qs=[]
        for qid,q in (m.get("questions") or {}).items():
            rows=[]
            for cat,val in (q.get("estimate_pct") or {}).items():
                ci=(q.get("interval_95") or {}).get(cat)
                cint=f"{float(ci['low']):.1f}–{float(ci['high']):.1f} %" if ci else "interval unavailable"
                rows.append(f"<tr><td>{_html_escape(cat)}</td><td>{float(val):.1f} %</td><td>{_html_escape(cint)}</td></tr>")
            qs.append(f"<h4>{_html_escape(q.get('text') or qid)}</h4><table><thead><tr><th>Odpověď</th><th>Odhad</th><th>95% interval</th></tr></thead><tbody>{''.join(rows)}</tbody></table>")
        sections.append(f"<section><h3>{_html_escape(method)}{' — PRIMARY' if method==primary else ''}</h3>{''.join(qs)}</section>")
    factors=''.join(f"<tr><td>{_html_escape(f['label'])}</td><td>{float(f['target_mean_10']):.1f}/10</td><td>{float(f['confidence']):.2f}</td><td>{_html_escape(', '.join(d['field'] for d in f.get('drivers',[])))}</td></tr>" for f in world_model.get('factors',[]))
    eligible=bool(manifest.get('benchmark_eligible'))
    html=f"""<!doctype html><html lang='cs'><head><meta charset='utf-8'><title>Full Simulation — {_html_escape(manifest.get('topic'))}</title><style>
body{{font:14px/1.5 system-ui,sans-serif;max-width:1080px;margin:28px auto;padding:0 22px;color:#172033}}h1,h2,h3{{line-height:1.15}}.flag{{display:inline-block;padding:4px 8px;border:1px solid #999;border-radius:3px;font-size:11px}}.warn{{background:#fff3d6}}.ok{{background:#eaf7ef}}table{{border-collapse:collapse;width:100%;margin:8px 0 18px}}th,td{{border-bottom:1px solid #d9dee5;padding:7px;text-align:left}}code{{font-size:11px}}section{{margin:25px 0}}.meta{{color:#657080;font-size:12px}}
</style></head><body><div class='flag {'ok' if eligible else 'warn'}'>{'BLIND BENCHMARK ELIGIBLE' if eligible else 'SCENARIO / EXCLUDED FROM BLIND LEADERBOARD'}</div><h1>Full Simulation Lab</h1><h2>{_html_escape(manifest.get('topic'))}</h2><p class='meta'>Run {_html_escape(manifest.get('run_id'))} · {manifest.get('worlds')} světů × n={manifest.get('n')} · {_html_escape(manifest.get('model'))} · objective {_html_escape(manifest.get('objective'))}</p><p><b>Epistemický status:</b> experimentální forecast. Topic-specific scenario vztahy jsou hypotetizované a nemění evidence tier ani externí prediktivní validaci v15.2.</p><h2>World model</h2><p>{_html_escape(world_model.get('summary'))}</p><table><thead><tr><th>Faktor</th><th>Prior</th><th>Confidence</th><th>Drivers</th></tr></thead><tbody>{factors}</tbody></table><p class='meta'>Research: {_html_escape((research_summary or {}).get('quality_status'))} · bezpečné zdroje {(research_summary or {}).get('accepted',0)} · target-overlap {(research_summary or {}).get('target_overlap_available',0)}. Historical domain benchmarks: {(learning or {}).get('n_benchmarks',0)}.</p><h2>Frozen prediction</h2>{''.join(sections)}<h2>Audit</h2><p><code>manifest_sha256={_html_escape(manifest.get('manifest_sha256'))}</code></p><p><code>prediction_sha256={_html_escape(manifest.get('prediction_sha256'))}</code></p><p>{_html_escape(manifest.get('warning'))}</p></body></html>"""
    out=run_dir/"FULL_SIMULATION_REPORT.html"
    out.write_text(html,encoding="utf-8")
    return out


def write_benchmark_html(bench_dir: Path, truth: dict[str, Any], scores: dict[str, Any], lb: dict[str, Any]) -> Path:
    rows=[]
    for method,s in (scores.get('methods') or {}).items():
        if s.get('status')!='SCORED': continue
        o=s['overall']
        rows.append(f"<tr><td>{_html_escape(method)}</td><td>{o['mae_pp']:.2f}</td><td>{o['tvd_pp']:.2f}</td><td>{o['brier']:.4f}</td><td>{'' if o.get('coverage_95') is None else f'{100*o["coverage_95"]:.0f} %'}</td></tr>")
    html=f"""<!doctype html><html lang='cs'><head><meta charset='utf-8'><title>Full Simulation benchmark</title><style>body{{font:14px/1.5 system-ui,sans-serif;max-width:980px;margin:28px auto;padding:0 22px;color:#172033}}table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #d9dee5;padding:8px;text-align:left}}.meta{{color:#657080}}</style></head><body><h1>Full Simulation benchmark</h1><p class='meta'>Run {_html_escape(truth.get('run_id'))} · {_html_escape(truth.get('benchmark_eligibility'))} · truth {_html_escape(truth.get('source'))}</p><table><thead><tr><th>Metoda</th><th>MAE p.b.</th><th>TVD p.b.</th><th>Brier</th><th>95% coverage</th></tr></thead><tbody>{''.join(rows)}</tbody></table><p>Permanentní blind benchmarky: {lb.get('n_blind_benchmarks',0)} · FullSim win-rate vs NPC Core: {_html_escape(lb.get('fullsim_win_rate_vs_core'))}</p><p class='meta'>Nižší MAE/TVD/Brier je lepší. Do permanentního leaderboardu vstupují pouze predikce uzamčené před truth a bez target leakage.</p></body></html>"""
    out=bench_dir/"BENCHMARK_REPORT.html"; out.write_text(html,encoding='utf-8'); return out


# ---------------------------------------------------------------------------
# CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="full_simulation", description="NPC Full Simulation Lab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare"); p.add_argument("spec"); p.add_argument("--panel")
    p = sub.add_parser("run"); p.add_argument("spec"); p.add_argument("--panel")
    p = sub.add_parser("truth"); p.add_argument("run_id"); p.add_argument("truth_json")
    p = sub.add_parser("submit"); p.add_argument("run_id"); p.add_argument("method"); p.add_argument("prediction_json")
    sub.add_parser("leaderboard")
    p = sub.add_parser("show"); p.add_argument("run_id")
    a = ap.parse_args(argv)
    if a.cmd in {"prepare","run"}:
        spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
        out = prepare_full_simulation(spec,panel_path=a.panel) if a.cmd=="prepare" else run_full_simulation(spec,panel_path=a.panel)
    elif a.cmd == "truth":
        out = record_truth(a.run_id, json.loads(Path(a.truth_json).read_text(encoding="utf-8")))
    elif a.cmd == "submit":
        out = register_external_prediction(a.run_id,a.method,json.loads(Path(a.prediction_json).read_text(encoding="utf-8")))
    elif a.cmd == "leaderboard":
        out = leaderboard()
    else:
        out = load_run(a.run_id)
    print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
