"""Post-run external verification and transparent contextual calibration.

This module is intentionally separate from Research Context used *before* respondent
simulation. Post-run verification is opt-in and is allowed to see the NPC result in
order to compare it with published Czech evidence. It never silently rewrites the
panel or the raw result. Any numerical contextual adjustment creates a second,
auditable variant beside the original NPC estimate.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
import hashlib, json, math, os, re, time
from concurrent.futures import ThreadPoolExecutor

from runtime_config import DEFAULT_ANTHROPIC_RESEARCH_MODEL, DEFAULT_OPENAI_RESEARCH_MODEL
from research_project import compile_project


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical_url(url: str) -> str:
    try:
        p = urlsplit(str(url).strip())
        if p.scheme not in {"http", "https"} or not p.netloc:
            return ""
        return urlunsplit((p.scheme.lower(), p.netloc.lower().removeprefix("www."), re.sub(r"/$", "", p.path or ""), p.query, ""))
    except Exception:
        return ""


def extract_targets(project: dict[str, Any], result_summary: dict[str, Any], *, include_mapped: bool = False) -> list[dict[str, Any]]:
    """Create stable numeric target IDs from a completed run and its project."""
    compiled = compile_project(project)
    qby = {q["id"]: q for q in compiled["brief"]["otazky"]}
    results = (result_summary or {}).get("vysledky") or {}
    out: list[dict[str, Any]] = []
    for qid, r in results.items():
        q = qby.get(qid)
        if not q or not isinstance(r, dict):
            continue
        md = q.get("metadata") or {}
        mapped = bool(md.get("mapped_object"))
        if mapped and not include_mapped:
            continue
        base = {"question_id": qid, "question_text": q.get("text", ""), "question_type": q.get("typ"), "mapped_object": mapped}
        if q.get("typ") in {"vyber", "multi"}:
            for opt, val in (r.get("celkem_pct") or {}).items():
                try: v = float(val)
                except Exception: continue
                out.append({**base, "target_id": f"{qid}|pct|{opt}", "metric": "pct", "option": str(opt), "npc_value": v, "unit": "pct", "bounds": [0.0, 100.0]})
        elif q.get("typ") == "skala":
            if r.get("prumer") is not None:
                lo, hi = (q.get("skala") or [1, 10])[:2]
                out.append({**base, "target_id": f"{qid}|mean", "metric": "mean", "option": "", "npc_value": float(r["prumer"]), "unit": "scale_mean", "bounds": [float(lo), float(hi)]})
            if r.get("top2box_pct") is not None:
                out.append({**base, "target_id": f"{qid}|top2box_pct", "metric": "top2box_pct", "option": "", "npc_value": float(r["top2box_pct"]), "unit": "pct", "bounds": [0.0, 100.0]})
    return out


def _schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "findings": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "target_id": {"type": "string"},
                    "benchmark_value": {"type": ["number", "null"]},
                    "benchmark_low": {"type": ["number", "null"]},
                    "benchmark_high": {"type": ["number", "null"]},
                    "claim_summary": {"type": "string"},
                    "source_title": {"type": "string"}, "source_url": {"type": "string"},
                    "source_date": {"type": ["string", "null"]}, "fieldwork_date": {"type": ["string", "null"]},
                    "geography": {"type": "string"}, "population": {"type": "string"}, "method": {"type": "string"},
                    "directness": {"type": "string", "enum": ["direct", "proxy", "hypothesis", "context_only"]},
                    "wording_comparability": {"type": "number", "minimum": 0, "maximum": 1},
                    "population_comparability": {"type": "number", "minimum": 0, "maximum": 1},
                    "source_quality": {"type": "number", "minimum": 0, "maximum": 1},
                    "direction": {"type": "string", "enum": ["supports", "npc_higher", "npc_lower", "not_comparable", "context_only"]},
                    "rationale": {"type": "string"},
                },
                "required": ["target_id", "benchmark_value", "benchmark_low", "benchmark_high", "claim_summary",
                             "source_title", "source_url", "source_date", "fieldwork_date", "geography", "population",
                             "method", "directness", "wording_comparability", "population_comparability", "source_quality",
                             "direction", "rationale"],
                "additionalProperties": False,
            }},
            "summary": {"type": "string"},
        },
        "required": ["findings", "summary"], "additionalProperties": False,
    }


def _prompt(project: dict[str, Any], targets: list[dict[str, Any]], max_sources: int) -> str:
    brief = {
        "title": project.get("title"), "goal": project.get("goal"), "decision_use": project.get("decision_use"),
        "product_description": (project.get("briefing") or {}).get("product_description"),
        "audience": project.get("audience"),
    }
    return f"""You are verifying results from a Czech synthetic survey AFTER the simulation. The user explicitly wants to compare the NPC estimates with real-world research, statistics and plausible hypotheses.

PROJECT CONTEXT:\n{json.dumps(brief, ensure_ascii=False, indent=2)}

NUMERIC TARGETS TO VERIFY:\n{json.dumps(targets, ensure_ascii=False, indent=2)}

Search for up to {max_sources} high-quality Czech or directly relevant sources. Prefer official statistics, primary research reports, peer-reviewed work and reputable survey organizations. For every useful finding, map it to EXACTLY ONE target_id from the list.

Rules:
- A benchmark_value may be returned ONLY when the source reports a genuinely comparable numerical measure in the SAME UNIT as the target. Never convert a vague statement into a number.
- direct = essentially the same construct/outcome and population; proxy = related but not identical; hypothesis = mechanism or directional expectation without a comparable numeric benchmark; context_only = useful background.
- Score wording_comparability, population_comparability and source_quality honestly from 0 to 1.
- If wording, population, time period or method differ materially, lower comparability and explain it.
- Do not force consensus. Contradictory sources are useful and should both be returned.
- Do not claim the NPC result is correct merely because one source is nearby.
- Return source URLs and dates. Paraphrase; do not quote long passages.
- The user may later request a transparent contextual adjustment. Only direct numeric evidence with strong comparability is eligible for numerical adjustment; hypotheses/proxies remain annotations.
Return only the JSON object requested by the tool/schema."""


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    try: return json.loads(text)
    except Exception: pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I) or re.search(r"(\{.*\})", text, re.S)
    if not m: raise ValueError("research agent nevrátil JSON")
    return json.loads(m.group(1))


def _anthropic_text(response: Any) -> str:
    return "\n".join(getattr(b, "text", "") for b in (getattr(response, "content", []) or []) if getattr(b, "type", None) == "text")


def _openai_agent(prompt: str, model: str) -> dict[str, Any]:
    from provider_auth import create_openai_client
    r = create_openai_client(max_retries=2).responses.create(model=model, input=prompt,
        tools=[{"type": "web_search", "search_context_size": "high"}],
        text={"format": {"type": "json_schema", "name": "npc_result_verification", "schema": _schema(), "strict": True}},
        store=False)
    return _extract_json(getattr(r, "output_text", ""))


def _anthropic_agent(prompt: str, model: str, max_sources: int) -> dict[str, Any]:
    from provider_auth import create_anthropic_client, resolve_available_anthropic_model
    client = create_anthropic_client(max_retries=3)
    model = resolve_available_anthropic_model(model)
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max(1, max_sources)}]
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    response = None
    for _ in range(3):
        response = client.messages.create(model=model, max_tokens=6500, messages=messages, tools=tools)
        if getattr(response, "stop_reason", None) != "pause_turn": break
        messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": response.content}]
    return _extract_json(_anthropic_text(response))



def _claude_code_agent(prompt: str, model: str, max_sources: int, agent_name: str) -> dict[str, Any]:
    from claude_code_provider import research_structured_call
    rr=research_structured_call(
        system=("Jsi validační research agent NPC Panelu. Porovnávej hotové syntetické výsledky s reálnými zdroji. "
                "Nepřepisuj NPC výsledek, nevymýšlej benchmarky a přísně rozlišuj direct/proxy/hypothesis/context_only."),
        messages=[{"role":"user","content":prompt}], schema=_schema(), schema_name='npc_result_verification',
        model=model or 'sonnet', timeout=480, max_turns=8)
    return rr.get('data') or {}

def _normalize_finding(x: dict[str, Any], *, agent: str, allowed_targets: set[str]) -> dict[str, Any] | None:
    tid = str(x.get("target_id") or "").strip()
    if tid not in allowed_targets: return None
    url = _canonical_url(x.get("source_url") or "")
    if not url: return None
    def num(k):
        v = x.get(k)
        try: return float(v) if v is not None and math.isfinite(float(v)) else None
        except Exception: return None
    direct = str(x.get("directness") or "context_only")
    if direct not in {"direct", "proxy", "hypothesis", "context_only"}: direct = "context_only"
    return {
        "target_id": tid, "benchmark_value": num("benchmark_value"), "benchmark_low": num("benchmark_low"), "benchmark_high": num("benchmark_high"),
        "claim_summary": str(x.get("claim_summary") or "").strip()[:1200], "source_title": str(x.get("source_title") or "").strip()[:300],
        "source_url": url, "source_date": x.get("source_date"), "fieldwork_date": x.get("fieldwork_date"),
        "geography": str(x.get("geography") or "").strip()[:120], "population": str(x.get("population") or "").strip()[:220],
        "method": str(x.get("method") or "").strip()[:300], "directness": direct,
        "wording_comparability": max(0.0, min(1.0, float(x.get("wording_comparability", 0)))),
        "population_comparability": max(0.0, min(1.0, float(x.get("population_comparability", 0)))),
        "source_quality": max(0.0, min(1.0, float(x.get("source_quality", 0.5)))),
        "direction": str(x.get("direction") or "not_comparable"), "rationale": str(x.get("rationale") or "").strip()[:900],
        "agent": agent,
    }


def verify_results(project: dict[str, Any], result_summary: dict[str, Any], *, target_ids: list[str] | None = None,
                   include_mapped: bool = False, max_sources_per_agent: int = 8,
                   mock_agents: dict[str, Any] | None = None, provider_override: str | None = None) -> dict[str, Any]:
    project = compile_project(project)["project"]
    targets = extract_targets(project, result_summary, include_mapped=include_mapped)
    if target_ids:
        wanted = set(map(str, target_ids)); targets = [t for t in targets if t["target_id"] in wanted]
    if not targets:
        raise ValueError("Není vybraný žádný číselný výsledek vhodný k externímu ověření.")
    # Keep a local research call bounded. The UI can verify more in a second pass.
    targets = targets[:24]
    prompt = _prompt(project, targets, max_sources_per_agent)
    agents: list[dict[str, Any]] = []
    if mock_agents is not None:
        for name, obj in mock_agents.items():
            if obj is not None: agents.append({"agent": name, "model": f"mock-{name}", "output": obj, "error": None})
    else:
        from provider_auth import get_ai_provider, normalize_ai_provider, provider_key_ready
        provider=normalize_ai_provider(provider_override or (project.get("run_policy") or {}).get("provider") or get_ai_provider())
        if not provider_key_ready(provider):
            raise RuntimeError(f"Externí ověření potřebuje připravený zvolený provider: {provider}.")
        if provider=="claude_code_subscription":
            # Two independent validation passes reduce single-agent anchoring.
            for name in ('claude_code_A','claude_code_B'):
                try:
                    agents.append({"agent":name,"model":"sonnet","output":_claude_code_agent(prompt,'sonnet',max_sources_per_agent,name),"error":None})
                except Exception as exc:
                    agents.append({"agent":name,"model":"sonnet","output":{},"error":str(exc)[:700]})
        else:
            try:
                if provider=="openai":
                    agents.append({"agent":"openai","model":DEFAULT_OPENAI_RESEARCH_MODEL,"output":_openai_agent(prompt,DEFAULT_OPENAI_RESEARCH_MODEL),"error":None})
                else:
                    agents.append({"agent":"anthropic","model":DEFAULT_ANTHROPIC_RESEARCH_MODEL,"output":_anthropic_agent(prompt,DEFAULT_ANTHROPIC_RESEARCH_MODEL,max_sources_per_agent),"error":None})
            except Exception as exc:
                agents.append({"agent":provider,"model":DEFAULT_OPENAI_RESEARCH_MODEL if provider=="openai" else DEFAULT_ANTHROPIC_RESEARCH_MODEL,"output":{},"error":str(exc)[:600]})
    successful = [a for a in agents if not a.get("error")]
    if not successful:
        errors = "; ".join(f"{a.get('agent')}: {a.get('error')}" for a in agents if a.get('error'))
        raise RuntimeError("Externí ověření selhalo u všech dostupných research agentů. " + errors)
    allowed = {t["target_id"] for t in targets}
    findings = []
    summaries = []
    for a in successful:
        obj = a.get("output") or {}
        summaries.append({"agent": a["agent"], "summary": str(obj.get("summary") or "")[:1500]})
        for x in obj.get("findings") or []:
            if isinstance(x, dict):
                y = _normalize_finding(x, agent=a["agent"], allowed_targets=allowed)
                if y: findings.append(y)
    # De-duplicate exact same URL+target, keep the stronger rating.
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for x in findings:
        key = (x["target_id"], x["source_url"])
        score = x["source_quality"] * x["wording_comparability"] * x["population_comparability"]
        old = dedup.get(key)
        old_score = -1 if old is None else old["source_quality"] * old["wording_comparability"] * old["population_comparability"]
        if score > old_score: dedup[key] = x
    findings = list(dedup.values())
    by_target = {}
    for t in targets:
        fs = [x for x in findings if x["target_id"] == t["target_id"]]
        direct = [x for x in fs if x["directness"] == "direct" and x["benchmark_value"] is not None]
        best = max(direct, key=lambda x: x["source_quality"]*x["wording_comparability"]*x["population_comparability"], default=None)
        status = "NO_COMPARABLE_SOURCE"
        if direct: status = "DIRECT_EVIDENCE"
        elif fs: status = "CONTEXT_ONLY"
        by_target[t["target_id"]] = {"target": t, "status": status, "findings": fs, "best_direct": best}
    bundle = {
        "created_at": _now(), "project_title": project.get("title"), "targets": targets,
        "agents": [{"agent": a["agent"], "model": a["model"], "error": a.get("error")} for a in agents],
        "agent_summaries": summaries, "findings": findings, "by_target": by_target,
        "quality_status": "DUAL_RESEARCH" if len(successful) >= 2 else "SINGLE_AGENT_RESEARCH",
        "note": "Externí evidence porovnává výsledek; sama o sobě nedokazuje prediktivní validitu NPC panelu.",
    }
    raw = json.dumps(bundle, ensure_ascii=False, sort_keys=True, default=str)
    bundle["sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return bundle


_STRENGTH = {"mild": 0.25, "medium": 0.45, "strong": 0.65}


def contextual_calibration(verification: dict[str, Any], *, strength: str = "medium") -> dict[str, Any]:
    """Create a transparent *scenario*, not a statistical calibration.

    The weights are heuristic comparability judgements produced during evidence review.
    Therefore the result must never be labelled as a newly calibrated population estimate.
    Raw NPC values are always preserved.
    """
    if strength not in _STRENGTH:
        raise ValueError("strength musí být mild, medium nebo strong")
    base_alpha = _STRENGTH[strength]
    adjusted = []
    for tid, item in (verification.get("by_target") or {}).items():
        target = item.get("target") or {}
        raw = target.get("npc_value")
        if raw is None: continue
        eligible = []
        for f in item.get("findings") or []:
            if f.get("directness") != "direct" or f.get("benchmark_value") is None: continue
            w = float(f.get("source_quality",0))*float(f.get("wording_comparability",0))*float(f.get("population_comparability",0))
            if w < 0.32 or float(f.get("wording_comparability",0)) < 0.65 or float(f.get("population_comparability",0)) < 0.65:
                continue
            eligible.append((w, float(f["benchmark_value"]), f))
        if not eligible:
            adjusted.append({"target_id": tid, "raw_npc": raw, "adjusted": raw, "applied": False, "reason": "Není dostatečně srovnatelná přímá číselná evidence."})
            continue
        sw = sum(w for w,_,_ in eligible)
        center = sum(w*v for w,v,_ in eligible)/sw
        evidence_conf = min(1.0, sw/1.6)
        alpha = min(0.70, base_alpha * evidence_conf)
        val = (1-alpha)*float(raw) + alpha*center
        bounds = target.get("bounds") or []
        if len(bounds)==2: val=max(float(bounds[0]),min(float(bounds[1]),val))
        adjusted.append({
            "target_id": tid, "raw_npc": round(float(raw),3), "evidence_center": round(center,3),
            "adjusted": round(val,3), "delta": round(val-float(raw),3), "alpha": round(alpha,3),
            "applied": True, "strength": strength,
            "sources": [{"title": f["source_title"], "url": f["source_url"], "benchmark": v, "weight": round(w,3)} for w,v,f in eligible],
            "warning": "Kontextový scénář není statistická kalibrace ani nový human výsledek; jde o transparentní heuristický post-processing NPC odhadu vůči externí evidenci."
        })
    return {"created_at": _now(), "strength": strength, "adjustments": adjusted,
            "raw_preserved": True, "method_status": "HEURISTIC_CONTEXT_SCENARIO_NOT_CALIBRATION",
            "label": "Kontextově upravený scénář",
            "verification_sha256": verification.get("sha256", "")}


def save_verification(bundle: dict[str, Any], root: str | Path, stem: str) -> Path:
    d = Path(root); d.mkdir(parents=True, exist_ok=True)
    p = d / f"{stem}_external_verification.json"
    p.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return p


def save_calibration(bundle: dict[str, Any], root: str | Path, stem: str) -> Path:
    d = Path(root); d.mkdir(parents=True, exist_ok=True)
    p = d / f"{stem}_context_adjusted.json"
    p.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return p
