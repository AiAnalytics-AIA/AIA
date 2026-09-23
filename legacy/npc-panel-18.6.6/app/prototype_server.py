#!/usr/bin/env python3
"""Local zero-framework web prototype for NPC Panel.

Run:
    python prototype_server.py
Open:
    http://127.0.0.1:8765

The server binds to localhost by default and is intended for prototype use, not
public internet deployment. Live runs require ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import html
from urllib.parse import urlparse, unquote

from diagnostika import diagnostika
from dotaznik import run_dotaznik
from pipeline import PANEL_PATH, Panel
from provenance import audit_dimension_contracts
from holdout_registry import assert_holdout_clean
from legal_gate import audit_legal
from validation_gate import assert_validation_ready, load_validation_evidence
from system_fingerprint import build_system_fingerprint
from domain_readiness import readiness_for_topics
from research_context import ResearchConfig, run_dual_research, bundle_to_kontext, save_bundle, bundle_from_obj
from dispozice import odvod_temata
from qc import kontrola
from report import export_xlsx, export_dataset_csv, export_dataset_csv_complete
from report_html import export_html
from runtime_config import DEFAULT_MODEL, resolve_model, RELEASE, RUN_DEFAULTS
from survey_lint import lint_questions
from segment_orchestration import prepare_segment
from segment import discover_audience_on_panel
from core_joint import load_joint_status
from run_store import RunStore
from audience_registry import load_audience_frame, get_audience
from population_subpanels import load_special_panel_frame

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "prototype_outputs"
OUT.mkdir(exist_ok=True)

DEMO = {
    "nazev": "Demo — rozvoz potravin",
    "n": 120,
    "mode": "dry",
    "model": RUN_DEFAULTS["model"],
    "response_mode": "probability",
    "seed": 42,
    "persona_mode": RUN_DEFAULTS["persona_mode"],
    "allow_own_estimates": False,
    "use_case": "internal",
    "research_context": {"enabled": False, "topic": "rozvoz potravin", "strict_consensus": True},
    "filtry": {},
    "segment": {"mode": "none"},
    "discovery": {"enabled": False, "question_id": "", "positive_answers": []},
    "otazky": [
        {"id": "O1", "text": "Nakupujete někdy potraviny online?", "typ": "vyber",
         "kategorie": ["ano, pravidelně", "ano, občas", "ne"], "topics": ["potraviny", "online", "nakup"]},
        {"id": "O2", "text": "Zvažoval(a) byste předplatné rozvozu potravin za 299 Kč měsíčně?",
         "typ": "vyber", "kategorie": ["určitě ano", "spíše ano", "spíše ne", "určitě ne"],
         "filtr": "O1 != 'ne'", "hypoteticka": True, "topics": ["potraviny", "cena", "sluzby", "predplatne"]},
        {"id": "O3", "text": "Jak důležitá je pro vás při nákupu potravin cena?", "typ": "skala",
         "skala": [1, 10], "popisky_skaly": ["vůbec", "zásadně"], "topics": ["potraviny", "cena", "nakup"]},
        {"id": "O4", "text": "Co by vás na takové službě nejvíc přesvědčilo nebo odradilo?",
         "typ": "otevrena", "max_slov": 25, "topics": ["potraviny", "sluzby", "cena"]},
    ],
}

HTML = r'''<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NPC Panel Prototype</title><style>
body{font-family:system-ui,Arial;max-width:1200px;margin:30px auto;padding:0 18px;background:#f7f8fb;color:#172033}
h1{margin-bottom:4px}.sub{color:#657083;margin-top:0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:900px){.grid{grid-template-columns:1fr}}
.card{background:white;border:1px solid #dfe5ee;border-radius:14px;padding:18px;box-shadow:0 2px 9px #00000008}
textarea{width:100%;min-height:570px;font-family:ui-monospace,monospace;font-size:13px;border:1px solid #cfd8e6;border-radius:10px;padding:12px;box-sizing:border-box}
button{background:#1f3864;color:#fff;border:0;border-radius:9px;padding:11px 18px;font-weight:700;cursor:pointer;margin-right:8px}.secondary{background:#6c7685}
pre{white-space:pre-wrap;word-break:break-word;background:#111827;color:#e5e7eb;padding:14px;border-radius:10px;min-height:280px;max-height:650px;overflow:auto}
.badge{display:inline-block;background:#e7eef9;padding:5px 9px;border-radius:999px;font-size:12px}.links a{display:inline-block;margin:8px 12px 0 0}
.toggle{display:flex;align-items:center;gap:8px;margin:12px 0;padding:10px;background:#f3f6fb;border-radius:10px}.toggle input{width:18px;height:18px}
</style><body>
<h1>NPC Panel Prototype <span class="badge">''' + RELEASE + r'''</span></h1><p class="sub">Lokální prototyp. Research Context je opt-in: OFF = žádný OpenAI/Claude web research; ON = oba nezávislé research agenty.</p>
<div class="grid"><div class="card"><h2>Brief</h2><textarea id="brief"></textarea><label class="toggle"><input id="research" type="checkbox"><span><b>Research Context</b> — spustit OpenAI + Claude rešerši a přidat pouze bezpečný auditovaný kontext</span></label><p><button onclick="run(false)">Spustit Bez AI</button><button onclick="run(true)">Spustit S AI</button><button class="secondary" onclick="loadDemo()">Obnovit demo</button></p></div>
<div class="card"><h2>Výsledek</h2><div id="status" class="sub">Připraven.</div><div id="links" class="links"></div><pre id="out"></pre></div></div>
<script>
const DEMO = __DEMO__;
function loadDemo(){document.getElementById('brief').value=JSON.stringify(DEMO,null,2); document.getElementById('research').checked=Boolean(DEMO.research_context&&DEMO.research_context.enabled)}
async function run(live){
 const research=document.getElementById('research').checked;
 if(live && !confirm(research ? 'LIVE + Research Context použije placené Anthropic i OpenAI API. Opravdu pokračovat?' : 'LIVE běh použije placené Anthropic API. Research Context je OFF. Opravdu pokračovat?')) return;
 const status=document.getElementById('status'), out=document.getElementById('out'), links=document.getElementById('links'); links.innerHTML='';
 let brief; try{brief=JSON.parse(document.getElementById('brief').value)}catch(e){status.textContent='Neplatný JSON: '+e;return}
 brief.mode=live?'sync':'dry';
 brief.research_context = (brief.research_context && typeof brief.research_context==='object') ? brief.research_context : {};
 brief.research_context.enabled = research;
 status.textContent=research ? 'Běží… Research Context ON' : 'Běží… Research Context OFF'; out.textContent='';
 try{const r=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({brief,confirm_live:live})}); const j=await r.json();
 status.textContent=r.ok?'Hotovo':'Chyba'; out.textContent=JSON.stringify(j.summary||j,null,2);
 if(j.xlsx) links.innerHTML += `<a href="${j.xlsx}">XLSX report</a>`; if(j.html) links.innerHTML += `<a href="${j.html}" target="_blank">HTML report</a>`;
 }catch(e){status.textContent='Chyba';out.textContent=String(e)}
}
loadDemo();
</script></body></html>'''.replace('__DEMO__', json.dumps(DEMO, ensure_ascii=False))


def _safe_name(s: str) -> str:
    x = re.sub(r"[^a-zA-Z0-9_-]+", "_", s).strip("_")[:60]
    return x or "survey"


def _public_summary(v: dict) -> dict:
    return {
        "nazev": v.get("nazev"), "run_id": v.get("run_id"), "release": v.get("release"),
        "n": v.get("n_dotazano"), "model": v.get("model"), "mode": v.get("mode"),
        "response_mode": v.get("response_mode"), "naklady_usd": v.get("naklady_usd"),
        "panel_mode": v.get("panel_mode", "standard"), "ai_panel_profile_id": v.get("ai_panel_profile_id", ""),
        "run_status": v.get("run_status"), "budget": v.get("budget"),
        "provider_policy": v.get("provider_policy"), "provider_probe": v.get("provider_probe"),
        "factual_layer": v.get("factual_layer"), "prompt_template_sha256": v.get("prompt_template_sha256"),
        "sample_id_sha256": v.get("sample_id_sha256"),
        "qc": v.get("qc"), "vysledky": v.get("vysledky"),
        "research_context": v.get("research_context"),
        "validation_gate": {"status": (v.get("validation_gate") or {}).get("status", "NOT_VALIDATED")},
        "joint_core": v.get("joint_core") or load_joint_status(),
        "segment_meta": v.get("segment_meta"),
        "audience_source": v.get("audience_source"),
        "audience_discovery": v.get("audience_discovery"),
        "domain_readiness": v.get("domain_readiness"),
        "legal_gate": {"status": (v.get("legal_gate") or {}).get("status"),
                       "use_case": (v.get("legal_gate") or {}).get("use_case")},
    }


def _question_topics(questions: list[dict]) -> list[str]:
    out: list[str] = []
    for q in questions:
        explicit = [str(x).strip() for x in (q.get("topics") or []) if str(x).strip()]
        topics = explicit or odvod_temata(str(q.get("text", "")) + " " + " ".join(q.get("kategorie") or []))
        out.extend(topics)
    return list(dict.fromkeys(out))


_PANEL_CACHE: dict = {}


def refresh_active_panel_path():
    """Refresh module-level panel path after an immutable Track A/B ingest activates a new snapshot."""
    global PANEL_PATH
    import pipeline as _pipeline
    new_path = _pipeline.resolve_panel_path()
    _pipeline.PANEL_PATH = new_path
    PANEL_PATH = new_path
    _PANEL_CACHE.clear()
    return new_path


def load_panel_cached(panel_path=None):
    """Cache a resolved STATIC/LIVE production panel by exact path."""
    import pandas as pd
    resolved=Path(panel_path or PANEL_PATH)
    key = (str(resolved.resolve()), resolved.stat().st_mtime_ns)
    cache=_PANEL_CACHE.setdefault('by_path',{})
    if key not in cache:
        base = pd.read_csv(resolved, low_memory=False, dtype={'occupation_isco08':'string'})
        try:
            from audience_dimensions import enrich_panel
            base = enrich_panel(base)
        except Exception:
            pass
        cache.clear() if len(cache)>3 else None
        cache[key]=base
    return cache[key]


def _r(code: int, obj: dict):
    """Uniform (status, payload) result used by both the HTTP handler and ui_server."""
    return code, obj


def _provider_run_failure(v: dict, mode: str) -> dict | None:
    """Detect a run in which the provider, not the research design, failed.

    Returns an actionable payload when (almost) every respondent call errored and
    the collected error text looks like a provider problem; otherwise ``None`` so
    normal QC handling continues.
    """
    if mode == "dry":
        return None
    try:
        detail = v.get("detail")
        n = int(len(detail))
        if not n:
            return None
        errors = [str(x) for x in detail["_chyba"].dropna().tolist()] if "_chyba" in detail else []
        if len(errors) < max(1, int(0.9 * n)):
            return None
    except Exception:
        return None
    joined = " | ".join(errors[:5])
    try:
        from provider_diagnostics import explain_router_failure
        diag = explain_router_failure(RuntimeError(joined))
    except Exception:
        diag = {"kind": "OTHER", "message": joined[:600], "detail": joined[:900], "next_action": ""}
    return {"error": diag["message"], "provider_error": diag,
            "failed_calls": len(errors), "total_respondents": n,
            "summary": _public_summary(v)}


def execute_run(payload: dict):
    """Extracted from the original do_POST so alternative front ends can reuse it
    without duplicating gate logic. Returns (http_status, json_payload)."""
    try:
        b = payload.get("brief") or payload
        lint = lint_questions(b.get("otazky", []))
        if not lint["ok"]: return _r(400,{"error":"questionnaire lint failed","lint":lint})
        audience_source = dict(b.get("audience_source") or {})
        audience_mode = str(audience_source.get("mode") or "population").strip().lower()
        audience_meta = None
        custom_audience = audience_mode in {"customer", "special_audience"}
        if custom_audience:
            dataset_id = str(audience_source.get("dataset_id") or "").strip()
            if not dataset_id:
                return _r(400,{"error":"CUSTOM_AUDIENCE_REQUIRED","message":"Vyberte nebo nahrajte konkrétní Customer / Special Audience dataset."})
            try:
                if dataset_id.startswith("builtin_special:"):
                    key=dataset_id.split(":",1)[1]
                    panel_df, sp_meta = load_special_panel_frame(key)
                    audience_meta={"audience_id":dataset_id,"name":sp_meta.get("name") or key,"runtime_csv":None,"builtin_special":True,"support":sp_meta.get("support")}
                    custom_panel_path = ROOT / str(sp_meta.get("file") or "")
                else:
                    panel_df, audience_meta = load_audience_frame(dataset_id)
                    custom_panel_path = ROOT / audience_meta["runtime_csv"]
            except (KeyError, FileNotFoundError):
                return _r(404,{"error":"CUSTOM_AUDIENCE_NOT_FOUND","dataset_id":dataset_id})
            d = {"uroven":"OK","status":"BUILTIN_SPECIAL_AUDIENCE" if dataset_id.startswith("builtin_special:") else "CUSTOM_AUDIENCE","n":int(len(panel_df))}
            holdout = {"review":[]}
        else:
            try:
                from population_context import project_population_mode,panel_path_for,project_population_context
                population_mode=project_population_mode(payload.get('project') or {})
                custom_panel_path=panel_path_for(population_mode)
                population_ctx=project_population_context(payload.get('project') or {})
            except Exception:
                population_mode='LIVE';custom_panel_path=Path(PANEL_PATH);population_ctx={}
            panel_df = load_panel_cached(custom_panel_path)
            d = diagnostika(panel_df)
            if d["uroven"] == "KRITICKE": return _r(500,{"error":"panel diagnostics critical","diagnostics":d})
            if audit_dimension_contracts()["fail"]: return _r(500,{"error":"data contract failure"})
            holdout = assert_holdout_clean()
        topics = _question_topics(b.get("otazky", []))
        readiness = ({"domains":[],"status":"CUSTOM_AUDIENCE_MEASURED_BASE","audience_id":audience_meta.get("audience_id") if audience_meta else ""}
                     if custom_audience else readiness_for_topics(topics, panel=panel_df))
        use_case = str(b.get("use_case", "internal")).lower()
        allow_own = bool(b.get("allow_own_estimates", False))
        if use_case == "commercial" and allow_own:
            return _r(400,{"error":"commercial mode never permits OWN_ESTIMATE dimensions"})
        legal = audit_legal(use_case=use_case, topics=topics, allow_own_estimates=allow_own)
        validation = assert_validation_ready(use_case="internal")
        if use_case == "commercial" and (legal.get("fail") or validation.get("status") != "VALIDATED"):
            return _r(403,{"error":"commercial gates not satisfied",
                "legal_unresolved":len(legal.get("fail",[])),
                "validation_status":validation.get("status","NOT_VALIDATED")}); return
        mode = b.get("mode","dry")
        if mode != "dry" and not payload.get("confirm_live"):
            return _r(400,{"error":"live run requires explicit confirm_live=true"})
        provider_probe = None
        project_policy = ((payload.get("project") or {}).get("run_policy") or {}) if isinstance(payload.get("project"),dict) else {}
        from provider_auth import get_ai_provider, normalize_ai_provider, probe_anthropic, probe_openai
        from runtime_config import resolve_provider_model
        provider = normalize_ai_provider(project_policy.get("provider") or str(b.get("provider_policy") or "").replace("strict_","") or get_ai_provider())
        provider_policy = "strict_" + provider
        b["model"] = resolve_provider_model(provider, b.get("model"))
        if mode != "dry":
            # Production contract: fail closed on the provider explicitly selected
            # for this project. Anthropic and OpenAI are equal product engines; the
            # other vendor never silently takes over a sharp survey.
            if provider == "openai": provider_probe=probe_openai(b.get("model"))
            elif provider == "claude_code_subscription":
                from claude_code_provider import health as claude_code_health
                provider_probe=claude_code_health()
            else: provider_probe=probe_anthropic(b.get("model"))
            if not provider_probe.get("ok"):
                return _r(503,{"error":"STRICT_LIVE_PROVIDER_FAILED",
                    "message":f"Ostrý výzkum vyžaduje funkční zvolený provider {provider}. Běh nebyl spuštěn a placený fallback je zakázán.",
                    "provider":provider,"provider_probe":provider_probe})
        if int(b.get("n", 120)) > 2000 and mode != "dry":
            return _r(400,{"error":"prototype live safety cap is n=2000; use CLI/code to raise intentionally"})

        rcfg = ResearchConfig.from_obj(b.get("research_context", False))
        research_bundle = None
        context_events = None
        precomputed_research = payload.get("precomputed_research")
        if precomputed_research and mode != "dry":
            research_bundle = bundle_from_obj(precomputed_research)
            if research_bundle:
                context_events = bundle_to_kontext(research_bundle)
                rcfg.enabled = True
        elif rcfg.enabled and mode != "dry":
            research_bundle = run_dual_research(rcfg, b.get("otazky", []), provider_override=provider)
            context_events = bundle_to_kontext(research_bundle)

        panel_obj = Panel(panel_df.copy(), min_vek=0 if custom_audience else 18)
        segment_spec = b.get("segment")
        if custom_audience and isinstance(segment_spec, dict) and str(segment_spec.get("mode") or "none") != "none":
            return _r(400,{"error":"CUSTOM_AUDIENCE_SEGMENT_DISCOVERY_DISABLED","message":"U nahrané audience použijte již definovaný segment/sloupec nebo nahrajte odpovídající subset; populační segment discovery se na vlastní data nepřenáší."})
        segment_weights, segment_meta = prepare_segment(
            panel_obj, segment_spec, model=resolve_provider_model(provider,b.get("model")), mode=mode,
            seed=b.get("seed",42), context_events=context_events,
            context_sha256=research_bundle.sha256 if research_bundle else None,
            workers=int(b.get("workers",8)))

        # Population invariant retained from the pre-v15 runtime:
        # panel=panel_obj, panel_path=PANEL_PATH
        # v15 substitutes custom_panel_path only when Customer/Special Audience is selected.
        v = run_dotaznik(b["otazky"], n=int(b.get("n",120)), filtry=b.get("filtry") or None,
            nazev=b.get("nazev","survey"), panel=panel_obj, panel_path=custom_panel_path,
            model=b.get("model"), mode=mode,
            seed=b.get("seed",42), workers=int(b.get("workers",8)), persona_mode=b.get("persona_mode",RUN_DEFAULTS["persona_mode"]),
            persona_topic_allowlist=b.get("persona_topic_allowlist") or None,
            panel_mode=b.get("panel_mode","standard"), ai_panel_profile=b.get("ai_panel_profile") or None,
            response_mode=b.get("response_mode",RUN_DEFAULTS["response_mode"]), allow_own_estimates=allow_own,
            kontext_udalosti=context_events, context_sha256=research_bundle.sha256 if research_bundle else None,
            selection_weights=segment_weights, segment_meta=segment_meta, tichy=True,
            provider_policy=provider_policy, budget_max_usd=(b.get("budget") or {}).get("max_usd"),
            run_dir=payload.get("run_dir") or None, resume_dir=payload.get("resume_dir") or None, checkpoint=True,
            progress_callback=payload.get("progress_callback"), cancel_check=payload.get("cancel_check"))
        v["use_case"] = use_case; v["legal_gate"] = legal; v["validation_gate"] = validation; v["domain_readiness"] = readiness
        v["joint_core"] = ({
            "status":"CUSTOM_AUDIENCE_MEASURED_BASE",
            "client_joint_outputs_allowed": True,
            "note":"Nahrané respondent-level covariáty jsou měřené joint údaje; nově generované survey odpovědi zůstávají modelované výstupy."
        } if custom_audience else load_joint_status()); v["segment_meta"] = segment_meta
        v["audience_source"] = {
            "mode": audience_mode,
            "dataset_id": audience_meta.get("audience_id") if audience_meta else "",
            "dataset_name": audience_meta.get("name") if audience_meta else (population_ctx.get('label') if not custom_audience else "ČR 18+"),
            "measured_joint_base": bool(custom_audience),
            "population_mode": (population_mode if not custom_audience else 'CUSTOM'),
        }
        v["population_context"] = (population_ctx if not custom_audience else {"mode":"CUSTOM","label":audience_meta.get('name') if audience_meta else 'Custom audience'})
        v["provider_probe"] = provider_probe
        v["provider_policy"] = provider_policy
        v["workflow_id"] = payload.get("workflow_id")
        v["job_id"] = payload.get("job_id")
        v["provider"] = provider
        v["response_mode"] = b.get("response_mode", RUN_DEFAULTS["response_mode"])
        v["persona_mode"] = b.get("persona_mode", RUN_DEFAULTS["persona_mode"])
        v["panel_mode"] = b.get("panel_mode", "standard")
        v["ai_panel_profile_id"] = ((b.get("ai_panel_profile") or {}).get("profile_id") if b.get("panel_mode")=="ai_panel" else "")
        v["holdout_review_count"] = len(holdout.get("review", []))
        v["research_context"] = {
            "enabled": rcfg.enabled, "executed": bool(research_bundle),
            "sha256": research_bundle.sha256 if research_bundle else "",
            "accepted": len(research_bundle.accepted) if research_bundle else 0,
            "quarantined": len(research_bundle.quarantined) if research_bundle else 0,
            "agents": [a.agent for a in research_bundle.agents] if research_bundle else [],
            "quality_status": research_bundle.quality_status if research_bundle else ("DRY_NO_CALLS" if rcfg.enabled and mode == "dry" else "OFF"),
            "dry_no_external_calls": bool(rcfg.enabled and mode == "dry"),
        }
        if research_bundle and v.get("run_dir"):
            save_bundle(research_bundle, Path(v["run_dir"]) / "research_context.json")
        dcfg = b.get("discovery") or {}
        if dcfg.get("enabled") and not custom_audience:
            _, disc = discover_audience_on_panel(
                panel_obj.df, v["detail"], str(dcfg.get("question_id")), dcfg.get("positive_answers") or [],
                min_positive=int(dcfg.get("min_positive",20)), seed=b.get("seed",42),
                prevalence_target=(float(dcfg["prevalence_target"]) if dcfg.get("prevalence_target") is not None else None),
                prevalence_source=dcfg.get("prevalence_source"))
            v["audience_discovery"] = disc
        v["qc"] = kontrola(v)
        provider_failure = _provider_run_failure(v, mode)
        if provider_failure is not None:
            # A run where every call failed is a provider incident, not a research
            # quality verdict. Reporting it as "QC critical" hides the actual cause
            # (dead key, no credit, blocked network) from the user.
            return _r(502, provider_failure)
        if v["qc"].get("uroven") == "KRITICKE" and mode != "dry":
            return _r(422,{"error":"QC critical; client report blocked", "summary":_public_summary(v)})
        stem = f"{_safe_name(v['nazev'])}_{v['run_id']}"
        # RESULTS-FIRST CONTRACT: once respondent-level data and QC are valid, core
        # result files are persisted independently. A secondary renderer must never
        # erase the completed fieldwork by throwing after the run is already valid.
        result_warnings=[]
        try:
            dp = export_dataset_csv_complete(v, OUT / f"{stem}_dataset.csv")
            dataset_scope='OWNER_AUDIT_COMPLETE'
        except Exception as exc:
            result_warnings.append({'artifact':'dataset_csv_complete','error':str(exc)[:800]})
            dp = export_dataset_csv(v, OUT / f"{stem}_dataset.csv", internal_data=False)
            dataset_scope='CLIENT_SAFE_FALLBACK'
        try:
            xp = export_xlsx(v, OUT / f"{stem}.xlsx")
        except Exception as exc:
            result_warnings.append({'artifact':'xlsx','error':str(exc)[:800]})
            from openpyxl import Workbook
            wb=Workbook();ws=wb.active;ws.title='Data'
            df=pd.read_csv(dp,low_memory=False)
            ws.append(list(df.columns))
            for row in df.itertuples(index=False,name=None): ws.append(list(row))
            sm=wb.create_sheet('Summary');sm['A1']='NPC Panel results fallback';sm['A2']=json.dumps(_public_summary(v),ensure_ascii=False,default=str)
            xp=OUT/f"{stem}.xlsx";wb.save(xp)
        try:
            hp = export_html(v, OUT / f"{stem}.html")
        except Exception as exc:
            result_warnings.append({'artifact':'html','error':str(exc)[:800]})
            import html as _h
            hp=OUT/f"{stem}.html";hp.write_text('<!doctype html><meta charset="utf-8"><main><h1>'+_h.escape(str(v.get('nazev') or 'Výsledky'))+'</h1><pre>'+_h.escape(json.dumps(_public_summary(v),ensure_ascii=False,indent=2,default=str))+'</pre></main>',encoding='utf-8')
        ap=ahp=None
        try:
            ap, ahp = _export_dataset_analysis(v, stem)
        except Exception as exc:
            result_warnings.append({'artifact':'dataset_analysis','error':str(exc)[:800]})
        # Persist a machine-readable core result before any optional bookkeeping.
        result_json=OUT/f"{stem}_RESULTS_CORE.json"
        result_json.write_text(json.dumps({'status':'RESULTS_READY','run_id':v.get('run_id'),'summary':_public_summary(v),'dataset_scope':dataset_scope,'warnings':result_warnings},ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        try:
            rs=RunStore(ROOT / "data" / "run_store.sqlite")
            rs.record(v); rs.close()
        except Exception as store_exc:
            v["run_store_warning"] = str(store_exc)
            result_warnings.append({'artifact':'run_store','error':str(store_exc)[:800]})
        return _r(200,{"status":"RESULTS_READY","summary":_public_summary(v),"xlsx":f"/files/{xp.name}","dataset_csv":f"/files/{dp.name}","html":f"/files/{hp.name}","results_json":f"/files/{result_json.name}","analysis_json":(f"/files/{ap.name}" if ap else None),"analysis_html":(f"/files/{ahp.name}" if ahp else None),"artifact_warnings":result_warnings,"dataset_scope":dataset_scope})
    except Exception as e:
        return _r(500,{"error":str(e),"trace":traceback.format_exc(limit=8)})


def _dataset_analysis(v:dict)->dict:
    detail=v.get("detail")
    out={
        "status":"INVALID_DRY_RUN" if str(v.get("mode") or "").lower()=="dry" else "MODEL_OUTPUT",
        "run_id":v.get("run_id"),"name":v.get("nazev"),
        "n":int(len(detail)) if hasattr(detail,"__len__") else int(v.get("n_dotazano") or 0),
        "persona_mode":v.get("persona_mode"),"panel_mode":v.get("panel_mode","standard"),"ai_panel_profile_id":v.get("ai_panel_profile_id", ""),"provider_policy":v.get("provider_policy"),
        "cost_usd":v.get("naklady_usd"),"warnings":[],"data_quality":{},"key_results":[]
    }
    if detail is not None and hasattr(detail,"columns"):
        try:
            out["data_quality"]["columns"]=int(len(detail.columns))
            miss=detail.isna().mean().sort_values(ascending=False).head(12)
            out["data_quality"]["highest_missingness"]=[{"column":str(k),"missing_pct":round(float(x)*100,1)} for k,x in miss.items() if float(x)>0]
            out["data_quality"]["duplicate_rows"]=int(detail.duplicated().sum())
        except Exception as exc:
            out["warnings"].append("Datova diagnostika: "+str(exc))
    for qid,r in (v.get("vysledky") or {}).items():
        if isinstance(r,dict) and r.get("celkem_pct"):
            a=sorted(((str(k),float(x)) for k,x in r["celkem_pct"].items()),key=lambda x:x[1],reverse=True)
            if a: out["key_results"].append({"question_id":qid,"type":"choice","top_answer":a[0][0],"top_pct":round(a[0][1],1)})
        elif isinstance(r,dict) and r.get("prumer") is not None:
            out["key_results"].append({"question_id":qid,"type":"scale","mean":round(float(r.get("prumer")),2),"top2_pct":r.get("top2box_pct")})
    out["key_results"]=out["key_results"][:20]
    return out

def _export_dataset_analysis(v:dict, stem:str)->tuple[Path,Path]:
    obj=_dataset_analysis(v)
    jp=OUT/f"{stem}_analysis.json"
    jp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    rows=''.join(
        '<tr><td>'+html.escape(str(x.get('question_id','')))+'</td><td>'+html.escape(str(x.get('top_answer',x.get('mean',''))))+'</td><td>'+html.escape(str(x.get('top_pct',x.get('top2_pct',''))))+'</td></tr>'
        for x in obj.get('key_results',[])
    )
    miss=''.join('<li><b>'+html.escape(str(x['column']))+'</b>: '+str(x['missing_pct'])+' %</li>' for x in obj.get('data_quality',{}).get('highest_missingness',[])) or '<li>Bez vyrazne chybejicnosti v exportovanem detailu.</li>'
    hp=OUT/f"{stem}_analysis.html"
    page=(
        '<!doctype html><html lang="cs"><meta charset="utf-8"><title>NPC - analyza datasetu</title>'
        '<style>body{font:15px/1.5 system-ui;max-width:980px;margin:36px auto;padding:0 20px;color:#172033}.box{border:1px solid #dde4ed;border-radius:14px;padding:16px;margin:12px 0}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #dde4ed;padding:8px;text-align:left}.warn{background:#fff5dd}</style>'
        '<h1>Analyza datasetu - '+html.escape(str(obj.get('name') or 'NPC'))+'</h1>'
        '<div class="box warn"><b>Status:</b> '+html.escape(str(obj.get('status')))+'. Tato analyza je deterministicka a nepridava dalsi LLM interpretaci.</div>'
        '<div class="box"><h2>Struktura</h2><p>N='+str(obj.get('n'))+' - sloupcu '+str(obj.get('data_quality',{}).get('columns','-'))+' - duplicitnich radku '+str(obj.get('data_quality',{}).get('duplicate_rows','-'))+'</p><h3>Nejvyssi chybejicnost</h3><ul>'+miss+'</ul></div>'
        '<div class="box"><h2>Hlavni vysledky</h2><table><tr><th>Otazka</th><th>Top / prumer</th><th>% / top2</th></tr>'+rows+'</table></div>'
        '<div class="box"><h2>Runtime</h2><p>Persona: '+html.escape(str(obj.get('persona_mode')))+' - provider policy: '+html.escape(str(obj.get('provider_policy')))+' - cost USD: '+html.escape(str(obj.get('cost_usd')))+'</p></div></html>'
    )
    hp.write_text(page,encoding='utf-8')
    return jp,hp


class Handler(BaseHTTPRequestHandler):
    server_version = "NPCPanelPrototype/15"

    def _json(self, code: int, obj: dict):
        data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            data = HTML.encode("utf-8"); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
        if path == "/health":
            self._json(200, {"status":"ok","release":RELEASE}); return
        if path == "/status":
            val = load_validation_evidence()
            fp = build_system_fingerprint()
            self._json(200, {"release": RELEASE, "validation_status": val.get("status", "NOT_VALIDATED"),
                             "system_sha256": fp["system_sha256"],
                             "research_context_default": "OFF"}); return
        if path.startswith("/files/"):
            name = unquote(path[len("/files/"):])
            p = (OUT / name).resolve()
            if OUT.resolve() not in p.parents or not p.is_file(): self._json(404,{"error":"not found"}); return
            ctype = {".xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".csv":"text/csv; charset=utf-8", ".html":"text/html; charset=utf-8"}.get(p.suffix.lower(), "application/octet-stream")
            data=p.read_bytes(); self.send_response(200); self.send_header("Content-Type",ctype)
            if p.suffix.lower() in {".xlsx", ".csv"}: self.send_header("Content-Disposition", f'attachment; filename="{p.name}"')
            self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
        self._json(404, {"error":"not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/run": self._json(404,{"error":"not found"}); return
        code, obj = execute_run(json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or b"{}"))
        self._json(code, obj)

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} - {fmt % args}")


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--host",default="127.0.0.1"); ap.add_argument("--port",type=int,default=8765); a=ap.parse_args()
    srv=ThreadingHTTPServer((a.host,a.port),Handler)
    print(f"NPC Panel {RELEASE}: http://{a.host}:{a.port}")
    print("Ctrl+C pro ukončení.")
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally: srv.server_close()
    return 0

if __name__ == "__main__": raise SystemExit(main())
