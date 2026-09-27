from __future__ import annotations
import time
from pathlib import Path
import pandas as pd


def execute_legacy(kind:str,payload:dict,jid:str,phase=lambda _x:None):
    """Execute a pre-17.2 async UI task inside the durable Research OS worker.

    This is a compatibility adapter only: HTTP never executes these long tasks and
    no in-memory thread owns their lifetime. The result contract stays compatible
    with the old /api/job poller.
    """
    import ui_server as u
    core=u.core; OUT=u.OUT; ROOT=u.ROOT
    RUN_DEFAULTS=u.RUN_DEFAULTS
    normalize_ai_provider=u.normalize_ai_provider; get_ai_provider=u.get_ai_provider
    resolve_provider_model=u.resolve_provider_model
    has_openai_key=u.has_openai_key; has_anthropic_key=u.has_anthropic_key
    probe_openai=u.probe_openai; probe_anthropic=u.probe_anthropic
    _file_url=u._file_url; _fullsim_spec_from_payload=u._fullsim_spec_from_payload
    _panel_path_for_project=u._panel_path_for_project; _public_project=u._public_project; _public_study=u._public_study
    diagnose_ai=u.diagnose_ai; analyze_research_brief=u.analyze_research_brief
    build_research_questionnaire=u.build_research_questionnaire; verify_result_context=u.verify_result_context
    deep_research_project=u.deep_research_project; optimize_questionnaire=u.optimize_questionnaire; repair_questionnaire_issue=u.repair_questionnaire_issue; suggest_persona_dimensions=u.suggest_persona_dimensions
    design_research_plan=u.design_research_plan; design_questionnaire=u.design_questionnaire; final_ai_review=u.final_ai_review

    if kind=="copilot":
        phase("AI upravuje aktuální výzkumný projekt")
        from research_copilot import chat
        code,obj=200,chat(str(payload.get("message") or ""),project=payload.get("project"),history=payload.get("history") or [],model=payload.get("model") or "sonnet",provider=payload.get("provider") or ((payload.get("project") or {}).get("run_policy") or {}).get("provider"))
    elif kind=="project_assistant":
        phase("AI asistent hledá inspiraci v historii projektů")
        from project_memory import answer
        code,obj=200,answer(str(payload.get("message") or ""),db_path=ROOT/'data'/'project_store.sqlite',current_project_id=str(payload.get("project_id") or "") or None,current_revision=(int(payload.get("project_revision")) if payload.get("project_revision") not in (None,"") else None),current_project=payload.get("project") or {},history=payload.get("history") or [],provider=payload.get("provider") or ((payload.get("project") or {}).get("run_policy") or {}).get("provider"),model=payload.get("model") or "sonnet",limit=int(payload.get("limit") or 12))
    elif kind=="ai_diagnose":
        phase("klíče → autentizace → modely → strukturovaný test")
        code,obj=200,diagnose_ai(payload)
    elif kind=="final_review":
        phase("AI dělá závěrečnou uživatelskou kontrolu projektu")
        code,obj=200,final_ai_review(payload)
    elif kind=="research_analysis":
        phase("AI analyzuje problém → co zkoumat → sledované sady")
        code,obj=200,analyze_research_brief(payload)
    elif kind=="questionnaire_build":
        phase("AI převádí schválenou analýzu do dotazníku")
        code,obj=200,build_research_questionnaire(payload)
    elif kind=="deep_research":
        phase("Hloubkový research: ČR → zahraničí → studie → evidence pack")
        code,obj=200,deep_research_project(payload,progress=phase)
    elif kind=="library_analyze":
        phase("Data Library · analyzuji zdroj a hledám dopad na dimenze")
        from data_library import analyze_entry
        code,obj=200,analyze_entry(str(payload.get("entry_id") or ""),model=str(payload.get("model") or "sonnet"),provider=str(payload.get("provider") or get_ai_provider()))
    elif kind=="library_deep_research":
        phase("Data Library · Deep Research hledá nové zdroje")
        from data_library import deep_research
        code,obj=200,deep_research(str(payload.get("topic") or ""),model=str(payload.get("model") or "sonnet"),provider=str(payload.get("provider") or get_ai_provider()),max_sources=int(payload.get("max_sources") or 8),progress=phase)
    elif kind=="questionnaire_optimize":
        phase("Hloubkový research → metodická optimalizace dotazníku")
        code,obj=200,optimize_questionnaire(payload,progress=phase)
    elif kind=="questionnaire_repair":
        phase("AI opravuje konkrétní otázku podle nálezu")
        code,obj=200,repair_questionnaire_issue(payload)
    elif kind=="persona_suggest":
        phase("AI vybírá dimenze persony podle projektu a dostupného research")
        code,obj=200,suggest_persona_dimensions(payload)
    elif kind=="result_verify":
        phase("externí research → srovnatelnost → porovnání s NPC výsledky")
        code,obj=200,verify_result_context(payload)
    elif kind=="persona_ablation":
        phase("Ablace persony: stejný vzorek + stejný prompt → none / demographics / full")
        from persona_ablation import run_persona_ablation
        mode=str(payload.get("mode") or RUN_DEFAULTS["mode"])
        code,obj=200,run_persona_ablation(payload.get("project") or {},mode=mode,confirm_live=bool(payload.get("confirm_live")),arms=payload.get("arms"))
    elif kind=="persona_benchmark":
        phase("Human benchmark: demographics → core → full")
        if not payload.get("confirm_live"):
            raise ValueError("Human benchmark musí být explicitně potvrzen jako placený LIVE běh.")
        provider=normalize_ai_provider(((payload.get("project") or {}).get("run_policy") or {}).get("provider") or payload.get("provider") or get_ai_provider())
        model=resolve_provider_model(provider,payload.get("model") or "sonnet")
        if provider=='claude_code_subscription':
            from claude_code_provider import health
            pr=health()
            if not pr.get('ok'): raise RuntimeError('SUBSCRIPTION_PROVIDER_UNAVAILABLE: '+str(pr.get('message') or pr))
        else:
            ready=has_openai_key() if provider=="openai" else has_anthropic_key()
            if not ready: raise RuntimeError(f"STRICT_LIVE_PROVIDER_FAILED: human benchmark vyžaduje zvolený provider {provider}; fallback je zakázán.")
            pr=probe_openai(model) if provider=="openai" else probe_anthropic(model)
            if not pr.get("ok"): raise RuntimeError(f"STRICT_LIVE_PROVIDER_FAILED: {provider} probe selhal: "+str(pr.get("message") or pr))
        spec=payload.get("spec") or {};questions=spec.get("questions") or []
        if not questions: raise ValueError("Benchmark spec neobsahuje questions.")
        budget=float(payload.get("budget_max_usd") or 0)
        if budget<=0: raise ValueError("Pro LIVE benchmark nastavte hard budget cap v USD.")
        from benchmark import run_benchmark, summarize_benchmark, summarize_benchmark_by_role, summarize_benchmark_by_segment, write_benchmark_manifest
        from persona_calibration import fit_calibration_profile
        d=OUT/"benchmarks"/(str(int(time.time()))+"_"+jid);d.mkdir(parents=True,exist_ok=True);csv_path=d/"benchmark_results.csv"
        n=int(payload.get("n") or 300);seed=int(payload.get("seed") or 42)
        df=run_benchmark(spec,n=n,panel_path=str(core.PANEL_PATH),model=model,mode="sync",seed=seed,baselines=("demographics","core","full"),budget_max_usd=budget,provider=provider)
        df.to_csv(csv_path,index=False);summary=summarize_benchmark(df);by_role=summarize_benchmark_by_role(df);by_segment=summarize_benchmark_by_segment(df)
        manifest=write_benchmark_manifest(spec=spec,out_csv=csv_path,panel_path=str(core.PANEL_PATH),model=model,mode="sync",n=n,seed=seed,summary=summary)
        profile=None
        if (df.get("benchmark_role",pd.Series(dtype=str)).astype(str).str.upper()=="CALIBRATION").any():
            profile=fit_calibration_profile(df,source={"benchmark_csv":str(csv_path),"benchmark_manifest":str(manifest)},activate=True)
        code,obj=200,{"summary":summary,"by_role":by_role,"by_segment":by_segment,"profile":profile,"csv":_file_url(csv_path),"manifest":_file_url(manifest),"provider":provider,"model":model,"budget_max_usd":budget,"spent_usd":round(float(pd.to_numeric(df.get("benchmark_spent_usd_cumulative"),errors="coerce").max() or 0),6),"n_questions":int(df["question_id"].nunique()),"baselines":["demographics","core","full"]}
    elif kind=="audience_propose":
        phase("AI převádí popis cílovky pouze na skutečné filtry panelu")
        from audience import propose_filters, feasibility
        provider=normalize_ai_provider(payload.get("provider") or ((payload.get("project") or {}).get("run_policy") or {}).get("provider") or get_ai_provider())
        model=str(payload.get("model") or "sonnet")
        obj=propose_filters(core.load_panel_cached(),str(payload.get("popis") or ""),model=model,provider=provider)
        obj["feasibility"]=feasibility(core.load_panel_cached(),obj["filtry"],int(payload.get("n") or 120))
        code=200
    elif kind=="audience_strategy":
        phase("AI vybírá outcome → propensity → 3 cílové strategie")
        run_id=str(payload.get("run_id") or "").strip()
        if not run_id: raise ValueError("Chybí run_id dokončeného výzkumu.")
        detail_path=ROOT/"runs"/run_id/"detail_internal.csv"
        if not detail_path.is_file(): raise FileNotFoundError("Interní respondentní data běhu nejsou dostupná.")
        detail=pd.read_csv(detail_path,low_memory=False)
        from audience_strategist import persist_candidates
        d=OUT/"discovery"/run_id/("smart_"+str(int(time.time())))
        code,obj=200,persist_candidates(core.load_panel_cached(),detail,payload.get("project") or {},d,model=str(payload.get("model") or "sonnet"),seed=int(payload.get("seed") or 42),min_positive=int(payload.get("min_positive") or 20))
        for c in obj.get("candidates") or []:
            if c.get("propensity_file"): c["propensity_file"]=_file_url(c["propensity_file"])
            c["download"]=_file_url(Path(d)/f"audience_{c.get('key')}.csv")
    elif kind=="simulation_context_enrich":
        phase("Simulace · strukturuji zadání → dohledávám trh → syntetizuji kontext")
        from simulation_context import enrich_simulation_context
        code,obj=200,enrich_simulation_context(str(payload.get("brief") or payload.get("simulation_brief") or ""),project=payload.get("project") or {},existing_context=payload.get("context") or None,model=str(payload.get("model") or "sonnet"),provider=str(payload.get("provider") or "claude_code_subscription"),max_sources=int(payload.get("max_sources") or 8),progress=phase,deep_research=bool(payload.get('deep_research',False)))
    elif kind=="simulation_context_deep":
        phase("Simulace · volitelný Deep Research → trh → evidence → syntéza")
        from simulation_context import enrich_simulation_context
        code,obj=200,enrich_simulation_context(str(payload.get("brief") or payload.get("simulation_brief") or ""),project=payload.get("project") or {},existing_context=payload.get("context") or None,model=str(payload.get("model") or "sonnet"),provider=str(payload.get("provider") or "claude_code_subscription"),max_sources=int(payload.get("max_sources") or 8),progress=phase,deep_research=True)
    elif kind=="simulation_uncertainty_resolve":
        phase("Simulace · dohledávám a doplňuji nevyřešené nejistoty")
        from simulation_context import resolve_simulation_uncertainties
        code,obj=200,resolve_simulation_uncertainties(payload.get("context") or {},raw_brief=str(payload.get("brief") or ""),project=payload.get("project") or {},model=str(payload.get("model") or "sonnet"),provider=str(payload.get("provider") or "claude_code_subscription"),max_sources=int(payload.get("max_sources") or 8),progress=phase)
    elif kind=="scenario_compile":
        phase("AI překládá scénář na auditovatelný delta contract")
        from scenario_compiler import compile_scenario
        code,obj=200,compile_scenario(str(payload.get("scenario") or payload.get("topic") or ""),project=payload.get("project") or {},baseline=str(payload.get("baseline") or ""),model=payload.get("model") or None,provider=payload.get("provider") or None)
    elif kind=="scenario_compile_batch":
        phase("AI kompiluje varianty nezávisle · bez lineární interpolace")
        from scenario_compiler import compile_scenario_variants
        code,obj=200,compile_scenario_variants(str(payload.get("scenario") or payload.get("base_change") or ""),payload.get("variants") or [],project=payload.get("project") or {},baseline=str(payload.get("baseline") or ""),model=str(payload.get("model") or "sonnet"),provider=str(payload.get("provider") or "claude_code_subscription"))
    elif kind=="fullsim_pipeline":
        phase("Simulace · 1/7 · ověřuji scénář a provider")
        from full_simulation import prepare_full_simulation,run_full_simulation,validate_full_simulation_result
        req=_fullsim_spec_from_payload(payload)
        if str((req.get("scenario_contract") or {}).get("status") or "")!="APPROVED": raise ValueError("SIMULATION_SCENARIO_NOT_APPROVED: Nejprve potvrďte, jak AI změnu pochopila.")
        if str(req.get("mode") or "dry")!="dry":
            if not payload.get("confirm_live"): raise ValueError("Simulace vyžaduje potvrzení ostrého LIVE běhu.")
            requested=normalize_ai_provider(payload.get("provider") or req.get("provider") or "claude_code_subscription")
            req["provider"]=requested
            if requested=="claude_code_subscription":
                from claude_code_provider import health
                pr=health()
                if not pr.get("ok"): raise RuntimeError("SUBSCRIPTION_PROVIDER_UNAVAILABLE: "+str(pr.get("message") or pr))
            elif requested=="anthropic":
                if not has_anthropic_key(): raise RuntimeError("CLAUDE_API_KEY_MISSING: Nastavte ANTHROPIC_API_KEY v projektu / Nastavení.")
            elif requested=="openai":
                if not has_openai_key(): raise RuntimeError("OPENAI_API_KEY_MISSING: Nastavte OPENAI_API_KEY v projektu / Nastavení.")
            else:
                raise RuntimeError("LIVE_PROVIDER_NOT_ALLOWED: podporován je Claude Code, Claude API nebo OpenAI API.")
        panel=_panel_path_for_project(payload.get("project"));ctx=payload.get("context") or ((payload.get("project") or {}).get("simulation_context") or {})
        phase("Simulace · 2/7 · Evidence Pack a world model")
        prep=prepare_full_simulation(req,panel_path=panel,existing_research=(ctx.get("evidence") or ((payload.get("project") or {}).get("pre_research") or {})),progress=phase)
        phase("Simulace · 3/7 · spouštím světy")
        run=run_full_simulation(req,panel_path=panel,prepared=prep,progress=phase)
        phase("Simulace · 7/7 · ověřuji frozen artefakty a report")
        run=validate_full_simulation_result(run,require_core_baseline=bool(req.get("include_core_baseline",True)),allow_invalid_dry=(str(req.get("mode") or "dry")=="dry"))
        run["pipeline"]={"status":"COMPLETED","single_durable_job":True};run["context_sha256"]=ctx.get("sha256")
        code,obj=200,run
    elif kind=="fullsim_batch_pipeline":
        phase("Batch Simulation · ověřuji varianty a připravuji společný evidence context")
        from simulation_batch import run_simulation_batch
        req=_fullsim_spec_from_payload(payload);req["provider"]=normalize_ai_provider(payload.get("provider") or req.get("provider") or "claude_code_subscription")
        batch=payload.get("batch") or {}; contracts=batch.get("variants") or payload.get("contracts") or []
        code,obj=200,run_simulation_batch(req,contracts,project=payload.get("project") or {},panel_path=_panel_path_for_project(payload.get("project")),context=payload.get("context") or ((payload.get("project") or {}).get("simulation_context") or {}),confirm_live=bool(payload.get("confirm_live")),progress=phase)
    elif kind=="fullsim_prepare":
        phase("Simulace: připravuji evidenci a model změny")
        from full_simulation import prepare_full_simulation
        req=_fullsim_spec_from_payload(payload);code,obj=200,prepare_full_simulation(req,panel_path=_panel_path_for_project(payload.get("project")),existing_research=((payload.get("project") or {}).get("pre_research") or {}),progress=phase)
    elif kind=="fullsim_run":
        phase("Simulace: baseline → změněný stav → výsledek")
        from full_simulation import run_full_simulation
        req=_fullsim_spec_from_payload(payload)
        if str(req.get("mode") or "dry")!="dry":
            if not payload.get("confirm_live"): raise ValueError("Simulace vyžaduje potvrzení ostrého LIVE běhu.")
            requested=normalize_ai_provider(payload.get("provider") or req.get("provider") or "claude_code_subscription")
            req["provider"]=requested
            if requested=="claude_code_subscription":
                from claude_code_provider import health
                pr=health()
                if not pr.get('ok'): raise RuntimeError('SUBSCRIPTION_PROVIDER_UNAVAILABLE: '+str(pr.get('message') or pr))
            elif requested=="anthropic":
                if not has_anthropic_key(): raise RuntimeError("CLAUDE_API_KEY_MISSING: Nastavte ANTHROPIC_API_KEY v projektu / Nastavení.")
            elif requested=="openai":
                if not has_openai_key(): raise RuntimeError("OPENAI_API_KEY_MISSING: Nastavte OPENAI_API_KEY v projektu / Nastavení.")
            else:
                raise RuntimeError("LIVE_PROVIDER_NOT_ALLOWED: podporován je Claude Code, Claude API nebo OpenAI API.")
        _panel=_panel_path_for_project(payload.get("project"));_prepared=payload.get("prepared")
        if _prepared is None:
            from full_simulation import prepare_full_simulation
            _prepared=prepare_full_simulation(req,panel_path=_panel,existing_research=((payload.get("project") or {}).get("pre_research") or {}),progress=phase)
        code,obj=200,run_full_simulation(req,panel_path=_panel,prepared=_prepared,progress=phase)
    elif kind=="project":
        phase("jeden vzorek → celý dotazník → datasety → sledované sady")
        from project_engine import run_project
        mode=str(payload.get("mode") or "dry")
        if mode!="dry" and not payload.get("confirm_live"): raise ValueError("Běh S AI vyžaduje potvrzení.")
        code,obj=200,_public_project(run_project(payload.get("project") or {},mode=mode,confirm_live=bool(payload.get("confirm_live")),map_method=payload.get("map_method") or "auto"))
    elif kind=="research_design":
        phase("AI analyzuje zadání a připravuje výzkumný projekt");code,obj=200,design_research_plan(payload)
    elif kind=="design":
        phase("AI návrh dotazníku");code,obj=200,design_questionnaire(payload)
    elif kind=="study":
        from study_engine import run_study
        phase("sledovaná sada: sběr → validace → mapa")
        spec=payload.get("spec") or {};mode=str(payload.get("mode","dry"))
        if mode!="dry" and not payload.get("confirm_live"): raise ValueError("Běh S AI vyžaduje potvrzení.")
        outdir=OUT/"studies"/jid;outdir.mkdir(parents=True,exist_ok=True)
        provider=normalize_ai_provider(((payload.get("project") or {}).get("run_policy") or {}).get("provider") or payload.get("provider") or get_ai_provider())
        res=run_study(spec,panel_path=str(core.PANEL_PATH),mode=mode,output_dir=outdir,map_method=payload.get("map_method","auto"),tichy=True,
                      provider_policy=("fallback" if mode=="dry" else "strict_"+provider));code,obj=200,_public_study(res)
    else:
        phase("survey gate → persony → odpovědi");code,obj=core.execute_run(payload)
    if code!=200: raise RuntimeError(str(obj))
    return obj
