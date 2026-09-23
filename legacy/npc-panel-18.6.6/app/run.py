#!/usr/bin/env python3
"""One-command NPC Panel orchestrator.

The path is deliberately fail-closed:
brief -> lint -> panel/data/holdout/legal/domain preflight -> optional dual-agent
Research Context -> sequential synthetic interview -> QC -> reports.

Research Context is opt-in. If it is OFF, neither OpenAI nor Claude web research is
called. If it is ON, BOTH independent research agents must complete successfully.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from runtime_config import RUN_DEFAULTS as _RD

SABLONA = {
    "nazev": "Nazev pruzkumu",
    "n": 500,
    "mode": _RD["mode"],
    "model": _RD["model"],
    "response_mode": _RD["response_mode"],
    "seed": 42,
    "persona_mode": _RD["persona_mode"],
    "allow_own_estimates": _RD["allow_own_estimates"],
    "use_case": _RD["use_case"],
    "research_context": {
        "enabled": False,
        "topic": "",
        "strict_consensus": True,
        "max_sources_per_agent": 8,
    },
    "filtry": {},
    "segment": {"mode": "none"},
    "discovery": {"enabled": False, "question_id": "", "positive_answers": []},
    "vystup": "vystupy/pruzkum.xlsx",
    "otazky": [
        {"id": "O1", "text": "Prvni otazka?", "typ": "vyber",
         "kategorie": ["moznost A", "moznost B", "moznost C"], "topics": []},
        {"id": "O2", "text": "Na skale 1-10?", "typ": "skala",
         "skala": [1, 10], "popisky_skaly": ["vubec", "zcela"], "topics": []},
    ],
}


def _question_topics(questions: list[dict]) -> list[str]:
    from dispozice import odvod_temata
    out = []
    for q in questions:
        explicit = [str(x).strip() for x in (q.get("topics") or []) if str(x).strip()]
        ts = explicit or odvod_temata(str(q.get("text", "")) + " " + " ".join(q.get("kategorie") or []))
        out.extend(ts)
    return list(dict.fromkeys(out))


def main() -> int:
    ap = argparse.ArgumentParser(description="NPC Panel — plně automatický běh z briefu")
    ap.add_argument("brief", nargs="?", help="cesta k JSON briefu")
    ap.add_argument("--dry", action="store_true", help="žádná placená API volání, včetně research agentů")
    ap.add_argument("--n", type=int, help="přebije n z briefu")
    ap.add_argument("--panel", help="cesta k panelu")
    ap.add_argument("--mode", choices=["sync", "batch", "dry"], help="přebije mode z briefu")
    ap.add_argument("--response-mode", choices=["probability", "choice"])
    ap.add_argument("--resume", metavar="RUN_DIR")
    ap.add_argument("--preflight-only", action="store_true", help="jen gatey; žádné modelové/API volání")
    ap.add_argument("--internal-data", action="store_true")
    ap.add_argument("--use-case", choices=["internal", "research", "commercial"])
    ap.add_argument("--research-context", choices=["on", "off"], help="přebije přepínač v briefu")
    ap.add_argument("--sablona", action="store_true")
    ap.add_argument("--navrh", metavar="ZADANI")
    ap.add_argument("--import", dest="import_soubor", metavar="SOUBOR")
    a = ap.parse_args()

    if a.sablona:
        print(json.dumps(SABLONA, ensure_ascii=False, indent=2)); return 0
    if a.import_soubor:
        from import_dotaznik import importuj_dotaznik
        b = importuj_dotaznik(a.import_soubor, n=a.n or 500)
        b.setdefault("research_context", {"enabled": False, "topic": "", "strict_consensus": True})
        b.setdefault("use_case", "internal"); b.setdefault("allow_own_estimates", False)
        cil = Path(a.brief or "brief.json")
        cil.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[import] {len(b['otazky'])} otázek -> {cil}"); return 0
    if a.navrh:
        from navrh import navrhni_dotaznik
        b = navrhni_dotaznik(a.navrh, n=a.n or 500)
        b.setdefault("research_context", {"enabled": False, "topic": a.navrh, "strict_consensus": True})
        b.setdefault("use_case", "internal"); b.setdefault("allow_own_estimates", False)
        cil = Path(a.brief or "brief.json")
        cil.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[navrh] {len(b['otazky'])} otázek -> {cil}"); return 0
    if not a.brief:
        ap.error("chybí brief")

    b = json.loads(Path(a.brief).read_text(encoding="utf-8"))
    for o in b.get("otazky", []):
        for k in ("skala", "popisky_skaly"):
            if k in o: o[k] = tuple(o[k])

    from diagnostika import diagnostika, tabulka_diagnostiky
    from dotaznik import run_dotaznik, tabulka_dotaznik
    from qc import kontrola, tabulka_qc
    from report import export_xlsx
    from report_html import export_html
    from survey_lint import lint_questions, format_lint
    from runtime_config import resolve_model
    from provenance import audit_dimension_contracts
    from holdout_registry import assert_holdout_clean
    from legal_gate import audit_legal
    from validation_gate import assert_validation_ready
    from domain_readiness import readiness_for_topics
    from research_context import ResearchConfig, run_dual_research, bundle_to_kontext, save_bundle
    import pandas as pd
    from pipeline import PANEL_PATH, Panel, resolve_panel_path
    from segment_orchestration import prepare_segment
    from segment import discover_audience_on_panel

    # 1) deterministic preflight before any paid call
    lint = lint_questions(b.get("otazky", [])); print(format_lint(lint))
    if not lint["ok"]:
        print("!! BLOCKED: questionnaire lint"); return 5

    panel_file = Path(a.panel or os.environ.get("NPC_PANEL", resolve_panel_path()))
    panel_df = pd.read_csv(panel_file, low_memory=False, dtype={'occupation_isco08':'string'})
    d = diagnostika(panel_df)
    if d["uroven"] != "OK": print(tabulka_diagnostiky(d))
    if d["uroven"] == "KRITICKE":
        print("!! BLOCKED: panel integrity diagnostics"); return 3

    pa = audit_dimension_contracts()
    if pa["fail"]:
        print("!! BLOCKED: incomplete data contracts"); return 4
    holdout = assert_holdout_clean()
    # Institution overlap (e.g. different CVVM waves) is informational, not a
    # permanent runtime warning. Exact holdout-item overlap remains a hard gate.

    topics = _question_topics(b.get("otazky", []))
    readiness = readiness_for_topics(topics, panel=panel_df)
    print(f"[domain readiness] {readiness['overall']} min={readiness['minimum_score']}")

    use_case = a.use_case or b.get("use_case", _RD["use_case"])
    allow_own = bool(b.get("allow_own_estimates", _RD["allow_own_estimates"]))
    if use_case == "commercial" and allow_own:
        print("!! BLOCKED: commercial mode never permits OWN_ESTIMATE dimensions"); return 8
    legal = audit_legal(use_case=use_case, topics=topics, allow_own_estimates=allow_own)
    validation = assert_validation_ready(use_case="internal")
    print(f"[validation] {validation.get('status', 'NOT_VALIDATED')}")
    if use_case == "commercial":
        blockers = []
        if legal.get("fail"):
            blockers.append(f"legal approvals unresolved: {len(legal['fail'])}")
        if validation.get("status") != "VALIDATED":
            blockers.append("blind predictive validation not unlocked")
        if blockers:
            print("!! COMMERCIAL BLOCKED: " + "; ".join(blockers))
            print("   Systém dovolí interní/research běh, ale nevydá komerční claim ani klientský report.")
            return 9
    elif legal.get("warnings"):
        print(f"[legal] {len(legal['warnings'])} source approvals unresolved; allowed only because use_case={use_case}")

    resolved_mode = "dry" if a.dry else (a.mode or b.get("mode", _RD["mode"]))
    resolved_model = resolve_model(b.get("model"))
    if resolved_mode != "dry":
        from provider_auth import provider_key_ready, get_ai_provider
        if not provider_key_ready(get_ai_provider()):
            print("!! S AI vyžaduje připravený zvolený provider (Anthropic API / OpenAI API / Claude Code subscription)"); return 6

    rcfg_obj = dict(b.get("research_context") or {}) if isinstance(b.get("research_context"), dict) else b.get("research_context", False)
    if a.research_context:
        if isinstance(rcfg_obj, dict): rcfg_obj["enabled"] = a.research_context == "on"
        else: rcfg_obj = {"enabled": a.research_context == "on"}
    rcfg = ResearchConfig.from_obj(rcfg_obj)
    if rcfg.enabled and resolved_mode != "dry":
        from provider_auth import get_ai_provider
        if get_ai_provider()=="claude_code_subscription":
            print("!! Research Context ON používá web-search lane a v této verzi vyžaduje explicitně Anthropic/OpenAI API provider; žádný silent fallback."); return 7
        from provider_auth import provider_key_ready
        if not provider_key_ready(get_ai_provider()):
            print("!! Research Context ON vyžaduje připravený zvolený API provider"); return 7

    if a.preflight_only:
        print("[preflight] PASS — žádné API volání provedeno.")
        print(json.dumps({"topics": topics, "domain_readiness": readiness, "legal": legal,
                          "validation": validation, "research_context_planned": rcfg.enabled}, ensure_ascii=False, indent=2))
        return 0

    # 2) optional independent dual research. --dry intentionally never calls it.
    research_bundle = None
    context_events = None
    if rcfg.enabled and resolved_mode != "dry":
        print("[research] ON — spouštím nezávisle OpenAI + Claude web research")
        research_bundle = run_dual_research(rcfg, b.get("otazky", []))
        context_events = bundle_to_kontext(research_bundle)
        print(f"[research] accepted={len(research_bundle.accepted)}, quarantined={len(research_bundle.quarantined)}, sha={research_bundle.sha256[:12]}")
    elif rcfg.enabled:
        print("[research] DRY — plán ověřen, ale žádný robot ani web search nebyl spuštěn")
    else:
        print("[research] OFF — žádné dohledávání externích informací")

    # 3) optional data-driven audience segment. No new people are invented: the
    # engine learns/receives propensity over the existing panel and changes PPS only.
    panel_obj = Panel(panel_df.copy())
    segment_weights, segment_meta = prepare_segment(
        panel_obj, b.get("segment"), model=resolved_model, mode=resolved_mode,
        seed=b.get("seed"), context_events=context_events,
        context_sha256=research_bundle.sha256 if research_bundle else None,
        workers=b.get("workers", 8))
    if segment_meta.get("mode") != "none":
        print(f"[segment] {segment_meta.get('name')} class={segment_meta.get('confidence_class')} "
              f"prev={100*float(segment_meta.get('prevalence_calibrated',0)):.2f}% "
              f"ESS={segment_meta.get('ess_population')}")

    v = run_dotaznik(
        b["otazky"], n=a.n or b.get("n", 500), filtry=b.get("filtry") or None,
        nazev=b.get("nazev", Path(a.brief).stem), panel=panel_obj, panel_path=panel_file,
        model=resolved_model, mode=resolved_mode, seed=b.get("seed"),
        workers=b.get("workers", 8), persona_mode=b.get("persona_mode", _RD["persona_mode"]),
        response_mode=a.response_mode or b.get("response_mode", "probability"),
        allow_own_estimates=allow_own, kontext_udalosti=context_events,
        context_sha256=research_bundle.sha256 if research_bundle else None,
        resume_dir=a.resume, selection_weights=segment_weights, segment_meta=segment_meta,
        anchor_config=(b.get("anchors") or {"enabled": False}),
        dispersion_config=(b.get("dispersion") or {}),
    )
    # Optional client-facing simulation ensemble. The first production run is kept
    # as the detailed audit run; additional runs vary only seed and calibrated
    # probability temperature and are summarized as a simulation interval.
    ecfg=b.get("ensemble") or {}
    if ecfg.get("enabled"):
        from ensemble import summarize_runs
        eruns=[v]
        nr=max(2,int(ecfg.get("runs",5)))
        temps=list(ecfg.get("temperatures") or [0.9,1.0,1.1,1.0,0.95])
        base_seed=int(b.get("seed") or 20260814)
        for ei in range(1,nr):
            dc=dict(b.get("dispersion") or {}); dc["temperature"]=float(temps[ei%len(temps)])
            eruns.append(run_dotaznik(
                b["otazky"], n=a.n or b.get("n",500), filtry=b.get("filtry") or None,
                nazev=b.get("nazev",Path(a.brief).stem)+f"_ens{ei+1}", panel=panel_obj, panel_path=panel_file,
                model=resolved_model, mode=resolved_mode, seed=base_seed+ei*1009, workers=b.get("workers",8),
                persona_mode=b.get("persona_mode",_RD["persona_mode"]), response_mode=a.response_mode or b.get("response_mode",_RD["response_mode"]),
                allow_own_estimates=allow_own, kontext_udalosti=context_events,
                context_sha256=research_bundle.sha256 if research_bundle else None,
                selection_weights=segment_weights, segment_meta=segment_meta,
                anchor_config=(b.get("anchors") or {"enabled":False}), dispersion_config=dc,
                ulozit=False, tichy=True))
        v["ensemble"]=summarize_runs(eruns,qlo=float(ecfg.get("qlo",.10)),qhi=float(ecfg.get("qhi",.90)))
        v["naklady_usd_ensemble_total"]=v["ensemble"]["total_cost_usd"]
        print(f"[ensemble] {nr} runs; interval={v['ensemble']['interval_quantiles']}; cost=${v['ensemble']['total_cost_usd']}")

    v["use_case"] = use_case; v["legal_gate"] = legal; v["validation_gate"] = validation; v["domain_readiness"] = readiness
    store_cfg = b.get("run_store") or {}
    if store_cfg.get("enabled"):
        from run_store import RunStore
        rs = RunStore(store_cfg.get("path", "data/run_store.sqlite"))
        try:
            rs.record(v, study_id=store_cfg.get("study_id"), client=store_cfg.get("client", ""))
        finally:
            rs.close()
    v["research_context"] = {
        "enabled": rcfg.enabled,
        "executed": bool(research_bundle),
        "sha256": research_bundle.sha256 if research_bundle else "",
        "accepted": len(research_bundle.accepted) if research_bundle else 0,
        "quarantined": len(research_bundle.quarantined) if research_bundle else 0,
        "agents": [a.agent for a in research_bundle.agents] if research_bundle else [],
    }
    if research_bundle and v.get("run_dir"):
        save_bundle(research_bundle, Path(v["run_dir"]) / "research_context.json")
    if segment_weights is not None and v.get("run_dir"):
        rd = Path(v["run_dir"])
        pd.DataFrame({"panel_index": segment_weights.index, "propensity": segment_weights.values}).to_csv(
            rd / "segment_propensity.csv", index=False)
        (rd / "segment_model.json").write_text(json.dumps(segment_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    dcfg = b.get("discovery") or {}
    if dcfg.get("enabled"):
        dprop, disc = discover_audience_on_panel(
            panel_obj.df, v["detail"], str(dcfg.get("question_id")),
            dcfg.get("positive_answers") or [], min_positive=int(dcfg.get("min_positive", 20)),
            seed=b.get("seed") or 0,
            prevalence_target=(float(dcfg["prevalence_target"]) if dcfg.get("prevalence_target") is not None else None),
            prevalence_source=dcfg.get("prevalence_source"))
        v["audience_discovery"] = disc
        outdir = Path(v.get("run_dir") or "runs")
        outdir.mkdir(parents=True, exist_ok=True)
        pprop = outdir / "audience_discovery_propensity.csv"
        pd.DataFrame({"panel_index": dprop.index, "propensity": dprop.values}).to_csv(pprop, index=False)
        (outdir / "audience_discovery.json").write_text(
            json.dumps(disc, ensure_ascii=False, indent=2), encoding="utf-8")
        disc["propensity_file"] = str(pprop)
        print(f"[discovery] {disc['target_question']} -> full panel scored; class={disc.get('confidence_class')} "
              f"ESS={disc.get('ess_population')}")

    print(tabulka_dotaznik(v))
    q = kontrola(v); v["qc"] = q; print(tabulka_qc(q))
    if q["uroven"] == "KRITICKE" and resolved_mode != "dry":
        print("!! Client report blocked: QC CRITICAL"); return 2

    cesta = export_xlsx(v, b.get("vystup", f"vystupy/{b.get('nazev', 'pruzkum')}.xlsx"),
                        internal_data=a.internal_data)
    html = export_html(v, Path(cesta).with_suffix(".html"))
    print(f"[report] {cesta}\n[html]   {html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
