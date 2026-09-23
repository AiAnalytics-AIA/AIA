#!/usr/bin/env python3
"""NPC Panel Research OS — durable background workflow runtime.

The browser is a friendly orchestration layer only. Authoritative survey, study,
segment, ingest and validation logic remains in the existing runtime modules.
"""
from __future__ import annotations

import argparse, base64, hashlib, json, os, subprocess, sys, threading, time, traceback, uuid, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote, quote

import pandas as pd
import prototype_server as core
from audience import allowed_values, feasibility, propose_filters, sanitize_filters
from population_subpanels import list_subpanels, get_subpanel, list_special_panels, get_special_panel, load_special_panel_frame
from audience_selector import recommend as recommend_audience
from typology_reference import load_typology_reference
from cost_estimator import estimate_range
from core_joint import load_joint_status
from dispozice import odvod_temata
from domain_readiness import readiness_for_topics
from runtime_config import DEFAULT_MODEL, RELEASE, MODELS, resolve_model, resolve_provider_model, DEFAULT_OPENAI_SURVEY_MODEL, RUN_DEFAULTS
from study_validity import scorecard
from survey_lint import lint_questions
from validation_gate import load_validation_evidence
from validation_status import validation_tier
from research_project import normalize_project, compile_project, project_stats, empty_project, classify_items
from provider_auth import has_anthropic_key, has_openai_key, provider_key_ready, save_local_keys, anthropic_key_info, openai_key_info, probe_anthropic, probe_openai, get_ai_provider, normalize_ai_provider
from audience_registry import list_audiences, load_audience_frame, import_audience_file, audience_preflight, delete_audience
from instrument_library import library_version, study_types as instrument_study_types
from edition_config import build_version
from provider_runtime import policy_for_provider

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"prototype_outputs"; OUT.mkdir(exist_ok=True)
UPLOADS=ROOT/"data"/"ui_uploads"; UPLOADS.mkdir(parents=True,exist_ok=True)
PROJECT_ATTACHMENTS=UPLOADS/"project_attachments"; PROJECT_ATTACHMENTS.mkdir(parents=True,exist_ok=True)


def _filters(raw):
    return {k:(tuple(v) if isinstance(v,list) and len(v)==2 and all(isinstance(x,(int,float)) for x in v) else v)
            for k,v in (raw or {}).items()}


def _panel_for_brief(brief:dict):
    src=dict(brief.get("audience_source") or {}); mode=str(src.get("mode") or "population").strip().lower()
    if mode in {"customer","special_audience"}:
        dataset_id=str(src.get("dataset_id") or "").strip()
        if not dataset_id: raise ValueError("Vyberte nebo nahrajte konkrétní Customer / Special Audience dataset.")
        if dataset_id.startswith("builtin_special:"):
            key=dataset_id.split(":",1)[1]; df,meta=load_special_panel_frame(key)
            return df,{"mode":"special_audience","dataset_id":dataset_id,"dataset_name":key,"meta":meta,"builtin_special":True}
        df,meta=load_audience_frame(dataset_id); return df,{"mode":mode,"dataset_id":dataset_id,"dataset_name":meta.get("name"),"meta":meta,"builtin_special":False}
    return core.load_panel_cached(),{"mode":"population","dataset_id":"","dataset_name":"ČR 18+","meta":None,"builtin_special":False}


def preflight(brief:dict)->dict:
    qs=brief.get("otazky") or []; lint=lint_questions(qs); topics=core._question_topics(qs) if qs else []
    panel,src=_panel_for_brief(brief)
    custom=src["mode"] in {"customer","special_audience"}
    readiness={"domains":[]}
    if topics and not custom:
        try: readiness=readiness_for_topics(topics,panel=panel)
        except Exception as exc: readiness={"domains":[],"error":str(exc)}
    doms=readiness.get("domains",[]); by={d["topic"]:d for d in doms}; per=[]
    for q in qs:
        qt=[str(x).strip() for x in (q.get("topics") or []) if str(x).strip()]
        if not qt: qt=odvod_temata(str(q.get("text",""))+" "+" ".join(q.get("kategorie") or []))
        scored=[by[t] for t in qt if t in by]; worst=min(scored,key=lambda d:d.get("score",0)) if scored else None
        per.append({"id":q.get("id"),"topics":qt,"score":worst.get("score") if worst else None,
                    "grade":worst.get("grade") if worst else None,
                    "own_estimate_share":worst.get("own_estimate_share") if worst else None})
    if custom:
        try:
            if src.get("builtin_special"):
                # Built-in special panels are packaged proxy/structural views, not uploaded audiences.
                # They must never be sent through audience_registry, which only knows user-uploaded datasets.
                from uncertainty import donor_support
                sup=donor_support(panel)
                stat_status="ok" if float(sup.get("effective_n_combined") or 0)>=50 else "low"
                meta=src.get("meta") or {}
                val={"claim_level":"MODELED_ON_BUILTIN_SPECIAL_PANEL","axes":{
                    "statistical":{"status":stat_status,"ess":sup.get("effective_n_combined"),"donor_support":sup},
                    "evidence":{"status":"structural_or_proxy_special_panel","support":meta.get("support")},
                    "joint":{"status":"packaged_special_panel_proxy"},
                    "external":{"tier":"MODEL_OUTCOME_UNVALIDATED"}},
                    "note":"Vestavěný special panel je support-aware strukturální/profesní proxy; nejde o nahraný measured-audience dataset."}
            else:
                ap=audience_preflight(src["dataset_id"],n=int(brief.get("n",120)))
                stat_status="ok" if ap.get("ess",0)>=100 else "low"
                val={"claim_level":"MODELED_ON_MEASURED_AUDIENCE","axes":{
                    "statistical":{"status":stat_status,"ess":ap.get("ess")},
                    "evidence":{"status":"measured_audience_base"},
                    "joint":{"status":"measured_row_level_base"},
                    "external":{"tier":"MODEL_OUTCOME_UNVALIDATED"}},
                    "note":"Nahrané covariáty jsou skutečné row-level joint údaje; nové survey odpovědi jsou stále modelové predikce."}
        except Exception as exc:
            val={"claim_level":"BLOCKED","error":str(exc),"axes":{}}
    else:
        try:
            val=scorecard(otazky=qs,lint=lint,per_question=per,panel=panel,
                          filtry=_filters(brief.get("filtry")),n=int(brief.get("n",120)),
                          persona_mode=str(brief.get("persona_mode",RUN_DEFAULTS["persona_mode"])))
        except Exception as exc:
            val={"claim_level":"BLOCKED","error":str(exc),"axes":{}}
    joint=({"status":"CUSTOM_AUDIENCE_MEASURED_BASE","client_joint_outputs_allowed":True}
           if custom else load_joint_status())
    return {"lint":lint,"topics":topics,"readiness":doms,"per_question":per,"validity":val,
            "estimate":estimate_range(brief),"joint_core":joint,"validation_tier":validation_tier(),
            "audience_source":src}


def _check_issue(level:str, code:str, message:str, *, where:str="", fix_step:str="run", fix_label:str="", fix_kind:str="", fix_value=None, scope:str="project")->dict:
    return {
        "level": level, "code": code, "message": message, "where": where,
        "fix_step": fix_step, "fix_label": fix_label or "Opravit",
        "fix_kind": fix_kind, "fix_value": fix_value, "scope": scope,
    }


def _issue_override_id(code:str, where:str, message:str)->str:
    raw=f"{code}|{where}|{message}".encode("utf-8",errors="replace")
    return "OVR-"+hashlib.sha256(raw).hexdigest()[:16]


def _lint_is_overrideable(message:str)->bool:
    """Only methodology-quality findings may be consciously overridden.

    Structural/runtime-invalid questionnaire states stay hard blockers. The explicit
    override is audited in project.ui_state.validation_overrides and never silently
    removes the warning from the project check.
    """
    low=str(message or "").lower()
    hard=(
        "nemá žádnou otázku", "id otázek nejsou unikátní", "chybí text otázky",
        "neznámý typ otázky", "alespoň 2 kategorie", "kategorie obsahují duplicity",
        "kategorie nesmí být prázdná", "neplatná škála", "neplatná syntaxe filtru",
        "filtr odkazuje", "neexistující/budoucí otázku",
    )
    return not any(x in low for x in hard)


def _apply_issue_override(issue:dict, project:dict)->dict:
    x=dict(issue); oid=_issue_override_id(str(x.get("code") or ""),str(x.get("where") or ""),str(x.get("message") or ""))
    x["override_id"]=oid
    overrides=set(str(v) for v in ((project.get("ui_state") or {}).get("validation_overrides") or []))
    if x.get("overrideable") and oid in overrides:
        x["overridden"]=True; x["original_level"]=x.get("level"); x["level"]="WARNING"; x["scope"]="claim"
        x["message"]="Uživatel vědomě pokračuje navzdory metodickému varování. "+str(x.get("message") or "")
    else:
        x["overridden"]=False
    return x


def _compile_failure(project:dict, exc:Exception)->dict:
    msg=str(exc) or exc.__class__.__name__
    issue=_check_issue(
        "BLOCKER", "PROJECT_COMPILE", msg, where="dotaznik",
        fix_step="questionnaire", fix_label="Opravit dotazník", scope="both",
    )
    return {
        "ok": False, "can_run_dry": False, "can_run_live": False,
        "project": project or {}, "stats": {}, "classification": {"tracked_sets": [], "non_objects": []},
        "preflight": {"lint": {"ok": False, "errors": [{"level": "ERROR", "where": "dotaznik", "message": msg}], "warnings": [], "info": [], "n_questions": 0},
                      "validity": {"claim_level": "BLOCKED", "blocking_axes": ["compile"]}},
        "compiled_brief": None, "issues": [issue],
        "summary": {"blockers": 1, "live_blockers": 0, "warnings": 0, "infos": 0},
    }


def _public_issue_view(issue:dict)->dict:
    """Return a user-facing blocker without exposing internal methodology labels."""
    x=dict(issue or {});code=str(x.get("code") or "")
    mapping={
        "QUESTION_LINT":("Dotazník potřebuje před spuštěním jednu úpravu.","Upravit dotazník"),
        "AUDIENCE_SOURCE":("Vyberte nebo nahrajte cílovou populaci.","Vybrat cílovku"),
        "FACTUAL_SOURCE_MISSING":("Jedna faktická otázka vyžaduje údaj, který pro tuto populaci nemáme. Upravte ji nebo ji nechte AI přeformulovat.","Upravit otázku"),
        "CUSTOM_AUDIENCE_SUPPORT":("Pro požadované N není v této cílové populaci dost dostupných lidí. Snižte N nebo rozšiřte populaci.","Upravit cílovku"),
        "CUSTOM_AUDIENCE_LOAD":("Cílovou populaci se nepodařilo načíst. Vyberte ji znovu nebo nahrajte nový soubor.","Vybrat cílovku"),
        "AUDIENCE_FILTER":("Jedno omezení cílové populace nelze použít. Upravte výběr lidí.","Upravit cílovku"),
        "AUDIENCE_SUPPORT":("Zvolená populace je pro požadovaný počet respondentů příliš malá. Upravte N nebo cílovku.","Upravit cílovku"),
        "REPRESENTATIVE_SAMPLE":("Z této populace teď nelze sestavit dostatečně reprezentativní vzorek požadované velikosti. Zvětšete populaci nebo upravte N.","Upravit vzorek"),
        "VALIDITY_CHECK":("Projekt potřebuje před spuštěním dokončit kontrolu návrhu.","Finální AI kontrola"),
        "AI_PROVIDER_NOT_READY":("AI partner není připravený. Ověřte přihlášení Claude Code v Nastavení AI.","Ověřit AI"),
    }
    msg,label=mapping.get(code,("Projekt potřebuje před spuštěním jednu konkrétní úpravu.",str(x.get("fix_label") or "Upravit")))
    x["user_message"]=msg;x["user_fix_label"]=label
    return x


def project_preflight(project:dict)->dict:
    """Actionable, non-paid project check used by the desktop UI.

    Runtime blockers are intentionally separated from methodological warnings.
    A dry technical run may proceed whenever the questionnaire compiles and the
    target sample is actually drawable.  Evidence/joint/validation limitations
    remain visible but do not masquerade as a runtime failure.
    """
    fact_harmonization=[]
    try:
        from factual_layer import harmonize_project_fact_choices
        project,fact_harmonization=harmonize_project_fact_choices(project,core.load_panel_cached())
        c=compile_project(project)
    except Exception as exc:
        return _compile_failure(project, exc)

    pf=preflight(c["brief"])
    issues=[]
    for note in fact_harmonization:
        issues.append(_check_issue("INFO","FACT_OPTIONS_HARMONIZED",f"{note.get('question_id')}: možnosti byly automaticky sjednoceny s autoritativním polem {note.get('field')}.",where="dotaznik",fix_step="questionnaire",fix_label="Zkontrolovat otázku",scope="claim"))
    lint=pf.get("lint") or {}
    for x in lint.get("errors") or []:
        msg=str(x.get("message") or "Chyba dotazníku."); where=str(x.get("where") or "dotaznik")
        qissue=_check_issue("BLOCKER", "QUESTION_LINT", msg, where=where, fix_step="questionnaire", fix_label="Opravit otázku", scope="both")
        qissue["overrideable"]=_lint_is_overrideable(msg)
        issues.append(_apply_issue_override(qissue,c.get("project") or project))
    for x in lint.get("warnings") or []:
        wi=_check_issue("WARNING", "QUESTION_WARNING", str(x.get("message") or "Varování dotazníku."), where=str(x.get("where") or "dotaznik"), fix_step="questionnaire", fix_label="Zkontrolovat otázku", scope="claim")
        wi["overrideable"]=False; issues.append(wi)

    try:
        panel,audience_src=_panel_for_brief(c["brief"])
    except Exception as exc:
        issues.append(_check_issue("BLOCKER","AUDIENCE_SOURCE",str(exc),where="cílovka",fix_step="audience",fix_label="Vybrat / nahrát audience",scope="both"))
        panel=core.load_panel_cached(); audience_src={"mode":"population","dataset_id":"","dataset_name":"ČR 18+","meta":None}
    custom_audience=audience_src.get("mode") in {"customer","special_audience"}
    if audience_src.get("builtin_special"):
        meta=audience_src.get("meta") or {}; sup=str(meta.get("support") or "")
        if sup.startswith("STRUCTURAL_ONLY") or sup=="EXPERIMENTAL_LOW_SUPPORT":
            issues.append(_check_issue("WARNING","SPECIAL_PANEL_STRUCTURAL_ONLY","Vestavěný special panel je strukturální/modelová proxy, nikoli group-specific respondentní measurement. Pro ostré kulturní/behaviorální claimy nahrajte skutečnou Special Audience.",where="cílovka",fix_step="audience",fix_label="Použít klientská data",scope="claim"))
    # Built-in panel row count and donor support are different quantities.
    # Never let thousands of synthetic rows hide a tiny number of real core donors.
    builtin_key=str((c.get("project",{}).get("audience") or {}).get("builtin_subpanel") or (c.get("brief",{}).get("audience_source") or {}).get("builtin_subpanel") or "")
    builtin_spec=get_subpanel(builtin_key) if builtin_key and not custom_audience else None
    if builtin_spec:
        tier=str(builtin_spec.get("support_tier") or "")
        eff=float(builtin_spec.get("effective_core_donors") or 0)
        uniq=int(builtin_spec.get("unique_core_donors") or 0)
        if tier=="EXPERIMENTAL_LOW_SUPPORT":
            issues.append(_check_issue(
                "WARNING","BUILTIN_PANEL_EXPERIMENTAL",
                f"Vestavěný panel {builtin_spec.get('name')} je pouze experimentální proxy: {uniq} unikátních / {eff:.1f} efektivních core donorů. Pro ostrý výzkum této skupiny preferujte uloženou nebo nahranou Special Audience.",
                where="cílovka",fix_step="audience",fix_label="Použít Special Audience",scope="claim"))
        elif tier=="LIMITED":
            issues.append(_check_issue(
                "WARNING","BUILTIN_PANEL_LIMITED",
                f"Vestavěný panel {builtin_spec.get('name')} má omezený donor support ({uniq} unikátních / {eff:.1f} efektivních core donorů). Omezte granularitu claimu nebo použijte Special Audience.",
                where="cílovka",fix_step="audience",fix_label="Zkontrolovat cílovku",scope="claim"))
        elif tier=="MODERATE":
            issues.append(_check_issue(
                "INFO","BUILTIN_PANEL_MODERATE",
                f"Vestavěný panel {builtin_spec.get('name')} má střední donor support ({uniq} unikátních / {eff:.1f} efektivních core donorů).",
                where="cílovka",fix_step="audience",fix_label="Rozumím",scope="claim"))
    from factual_layer import classify_question
    for q in c["brief"].get("otazky") or []:
        from dotaznik import Otazka
        try:
            oq=Otazka(**q); fs=classify_question(oq,set(panel.columns))
        except Exception:
            fs=None
        if fs is not None and fs.status=="UNSUPPORTED":
            issues.append(_check_issue(
                "LIVE_BLOCKER","FACTUAL_SOURCE_MISSING",
                f"{q.get('id')}: faktická otázka nemá autoritativní zdroj v panelu. {fs.reason} LLM ji v ostrém běhu nesmí domýšlet.",
                where="faktická vrstva",fix_step="questionnaire",fix_label="Doplnit zdroj / změnit otázku",scope="live"))
    if custom_audience and audience_src.get("dataset_id") and not audience_src.get("builtin_special"):
        try:
            cap=audience_preflight(audience_src["dataset_id"],n=int(c["brief"].get("n") or 120))
            for msg in cap.get("problems") or []:
                issues.append(_check_issue("BLOCKER","CUSTOM_AUDIENCE_SUPPORT",str(msg),where="cílovka",fix_step="audience",fix_label="Upravit audience / N",scope="both"))
            for msg in cap.get("warnings") or []:
                issues.append(_check_issue("WARNING","CUSTOM_AUDIENCE_WARNING",str(msg),where="cílovka",fix_step="audience",fix_label="Zkontrolovat audience",scope="claim"))
        except Exception as exc:
            issues.append(_check_issue("BLOCKER","CUSTOM_AUDIENCE_LOAD",str(exc),where="cílovka",fix_step="audience",fix_label="Vybrat audience",scope="both"))
    raw_filters=c["brief"].get("filtry") or {}
    clean_filters,dropped=sanitize_filters(panel,raw_filters)
    for d in dropped:
        issues.append(_check_issue(
            "BLOCKER", "AUDIENCE_FILTER", str(d), where="cilovka",
            fix_step="audience", fix_label="Opravit cílovku", scope="both",
        ))
    try:
        aud=feasibility(panel,clean_filters,int(c["brief"].get("n") or 120))
    except Exception as exc:
        aud={"ok":False,"support":0,"ess":0,"problemy":[{"uroven":"ERROR","text":str(exc)}]}
    for x in aud.get("problemy") or []:
        lvl=str(x.get("uroven") or "WARNING").upper()
        is_block=lvl=="ERROR"
        support=int(aud.get("support") or 0)
        requested=int(c["brief"].get("n") or 0)
        fix_kind="set_n" if is_block and support>=20 and requested>support else ""
        issues.append(_check_issue(
            "BLOCKER" if is_block else "WARNING", "AUDIENCE_SUPPORT" if is_block else "AUDIENCE_WARNING",
            str(x.get("text") or "Problém cílovky."), where="cilovka",
            fix_step="audience" if not fix_kind else "persona",
            fix_label=(f"Nastavit N={support}" if fix_kind else "Upravit cílovku"),
            fix_kind=fix_kind, fix_value=support if fix_kind else None,
            scope="both" if is_block else "claim",
        ))

    # Prove representativeness with the exact selector used by respondent runs.
    # The user does not have to diagnose margins manually: if a balanced unique
    # sample cannot be constructed, the project is blocked before fieldwork.
    representative_audit={}
    if aud.get("ok"):
        try:
            from audience import _mask
            from representative_sampling import draw_representative
            sub=panel[_mask(panel,clean_filters)].copy()
            if "_analysis_weight" in sub.columns:
                ww=pd.to_numeric(sub["_analysis_weight"],errors="coerce").fillna(0).to_numpy(float)
            elif "vaha_kalibrovana" in sub.columns:
                ww=pd.to_numeric(sub["vaha_kalibrovana"],errors="coerce").fillna(0).to_numpy(float)
            else:
                import numpy as np
                ww=np.ones(len(sub),dtype=float)
            _,representative_audit=draw_representative(sub,int(c["brief"].get("n") or 120),seed=int((c.get("project") or {}).get("seed") or 42),weights=ww)
            if representative_audit.get("status")=="PASS_WEIGHTED":
                issues.append(_check_issue("WARNING","REPRESENTATIVE_SAMPLE_WEIGHTED",f"Nevážený výběr má max. odchylku {(representative_audit.get('raw') or {}).get('max_abs_pp')} p. b.; po kalibraci {(representative_audit.get('weighted') or {}).get('max_abs_pp')} p. b. Výsledky používají analytické váhy (efektivní N {representative_audit.get('effective_n')}).",where="vzorek",fix_step="persona",fix_label="Zobrazit váhy",scope="claim"))
        except Exception as exc:
            representative_audit={"status":"BLOCKED","statement":"Reprezentativní vzorek zatím nelze sestavit.","technical_error":str(exc)[:500]}
            issues.append(_check_issue(
                "BLOCKER","REPRESENTATIVE_SAMPLE",str(exc),where="vzorek",
                fix_step="persona",fix_label="Upravit N / cílovku",scope="both"))

    validity=pf.get("validity") or {}
    if validity.get("error"):
        issues.append(_check_issue(
            "BLOCKER", "VALIDITY_CHECK", str(validity.get("error")), where="metodika",
            fix_step="run", fix_label="Zobrazit kontrolu", scope="both",
        ))
    axes=validity.get("axes") or {}
    stat=(axes.get("statistical") or {})
    if stat.get("status") in {"insufficient","low"}:
        issues.append(_check_issue(
            "WARNING", "LOW_EFFECTIVE_N",
            f"Efektivní n je pro část otázek nízké ({stat.get('status')}). Technický běh lze spustit, ale populační claim bude slabý.",
            where="vzorek", fix_step="persona", fix_label="Upravit velikost vzorku", scope="claim",
        ))
    evidence=(axes.get("evidence") or {})
    if evidence.get("status") in {"unsupported","weak"}:
        issues.append(_check_issue(
            "WARNING", "WEAK_EVIDENCE",
            "Část dotazníku má slabou nebo nepřiřazenou evidenční oporu. Pro interní test lze běžet; klientský claim musí zůstat omezený.",
            where="evidence", fix_step="questionnaire", fix_label="Zkontrolovat otázky", scope="claim",
        ))
    joint=(axes.get("joint") or {})
    if joint.get("status") not in {None,"not_applicable","joint_validated","validated"}:
        issues.append(_check_issue(
            "INFO", "JOINT_STATUS",
            f"Joint/persona vrstva je {joint.get('status')}. Jde o metodické omezení, ne technickou překážku interního běhu.",
            where="persona", fix_step="persona", fix_label="Zkontrolovat personu", scope="claim",
        ))
    external=(axes.get("external") or {})
    if external.get("tier") not in {None,"HOLDOUT_VALIDATED"}:
        issues.append(_check_issue(
            "INFO", "EXTERNAL_VALIDATION",
            f"Externí validační tier je {external.get('tier') or 'UNVALIDATED'}. Kontrola projektu neověřuje prediktivní přesnost.",
            where="validace", fix_step="run", fix_label="Rozumím", scope="claim",
        ))

    dry_blockers=[x for x in issues if x["level"]=="BLOCKER" and x.get("scope") in {"both","dry"}]
    live_blockers=list(dry_blockers)
    # LIVE is fail-closed on the explicitly selected Claude transport.
    selected_provider=normalize_ai_provider((c.get("project",{}).get("run_policy") or {}).get("provider") or get_ai_provider())
    provider_ready=provider_key_ready(selected_provider)
    if not provider_ready:
        detail=("ověřené přihlášení Claude Pro/Max" if selected_provider=="claude_code_subscription" else "platný Claude API klíč")
        live_blockers.append(_check_issue(
            "LIVE_BLOCKER", "AI_PROVIDER_NOT_READY",
            f"Ostrý běh vyžaduje připravený zvolený provider {selected_provider} ({detail}). Druhý provider ho automaticky nepřevezme; Bez AI je pouze nevalidní technický test.",
            where="AI provider", fix_step="settings", fix_label="Nastavit / ověřit AI provider", scope="live",
        ))
    # Add all live-only blockers produced above (facts/provider) to the visible list.
    for x in [i for i in issues if i.get("level")=="LIVE_BLOCKER"]:
        if x not in live_blockers: live_blockers.append(x)
    for x in live_blockers:
        if x not in issues: issues.append(x)
    max_usd=(c.get("project",{}).get("budget") or {}).get("max_usd")
    est=(pf.get("estimate") or {})
    if max_usd is not None and float(max_usd) < float(est.get("usd_low") or 0):
        issues.append(_check_issue(
            "WARNING","BUDGET_BELOW_LOW_ESTIMATE",
            f"Hard cap ${float(max_usd):.2f} je pod konzervativním dolním odhadem ${float(est.get('usd_low') or 0):.2f}. Běh se bezpečně zastaví jako částečný, než limit překročí.",
            where="rozpočet",fix_step="run",fix_label="Upravit kreditní limit",scope="claim"))

    can_dry=not dry_blockers
    can_live=not live_blockers
    # Public UI sees only concrete blockers that require user action. Internal
    # evidence/joint/validation/support diagnostics remain available in ``issues``
    # for audit and the final AI review, but never interrupt normal project setup.
    user_issues=[_public_issue_view(x) for x in issues if x.get("level") in {"BLOCKER","LIVE_BLOCKER"} and not x.get("overridden")]
    representation={
        "mode":"automatic_balanced",
        "status":"READY" if representative_audit.get("status") in {"PASS","PASS_WEIGHTED"} else "BLOCKED",
        "population":str((c.get("project",{}).get("audience") or {}).get("description") or audience_src.get("dataset_name") or "zvolená populace"),
        "fields":representative_audit.get("fields") or [x for x in ("pohlavi","vek_skupina","kraj","vzdelani","zamestnani_status") if x in panel.columns],
        "statement":representative_audit.get("statement") or "Vzorek se při běhu automaticky vybere reprezentativně v rámci zvolené populace.",
        "raw_max_abs_pp":((representative_audit.get("raw") or {}).get("max_abs_pp")),
        "weighted_max_abs_pp":((representative_audit.get("weighted") or {}).get("max_abs_pp")),
    }
    return {
        "ok": can_dry, "can_run_dry": can_dry, "can_run_live": can_live,
        "project":c["project"],"stats":project_stats(c["project"]),
        "classification":classify_items(c["project"]),"preflight":pf,
        "compiled_brief":c["brief"], "audience":aud, "issues":issues,
        "user_issues":user_issues,"representativeness":representation,"representativeness_audit":representative_audit,
        "summary": {
            "blockers": sum(1 for x in issues if x["level"]=="BLOCKER"),
            "live_blockers": sum(1 for x in issues if x["level"]=="LIVE_BLOCKER"),
            "warnings": sum(1 for x in issues if x["level"]=="WARNING"),
            "infos": sum(1 for x in issues if x["level"]=="INFO"),
        },
    }



def final_ai_review(req:dict)->dict:
    """One user-friendly end-of-setup review.

    Internal governance states are deliberately input-only. The assistant must
    translate them into ordinary research recommendations and must never expose
    implementation labels such as joint_unvalidated, ESS, anchor registries or
    validation tiers in the normal product UI.
    """
    project=dict(req.get("project") or {})
    checked=project_preflight(project)
    cproj=checked.get("project") or project
    brief=checked.get("compiled_brief") or {}
    # Build a real representative sample preview locally so the review does not
    # merely promise representativeness; it verifies the same selector used by runs.
    sample_audit=dict(checked.get("representativeness_audit") or {})
    if not sample_audit:
        sample_audit={"status":"BLOCKED","statement":"Reprezentativní vzorek zatím nelze sestavit."}
    from data_library import knowledge_context_for_project
    library_context=knowledge_context_for_project(cproj,limit=12)
    sections=[]
    for sec in cproj.get("sections") or []:
        if sec.get("type")=="object_battery":
            sections.append({"type":"tracked_set","title":sec.get("title"),"family":sec.get("object_family") or sec.get("object_type"),"objects":list(sec.get("objects") or [])[:15]})
        else:
            sections.append({"type":"questions","title":sec.get("title"),"questions":[{"id":q.get("id"),"text":q.get("text"),"type":q.get("typ")} for q in (sec.get("questions") or [])[:20]]})
    internal=[{"code":x.get("code"),"level":x.get("level"),"where":x.get("where"),"message":x.get("message")} for x in checked.get("issues") or []]
    schema={"type":"object","properties":{
        "ready":{"type":"boolean"},"summary":{"type":"string"},"sample_statement":{"type":"string"},
        "questionnaire_statement":{"type":"string"},"persona_statement":{"type":"string"},"knowledge_statement":{"type":"string"},
        "recommended_changes":{"type":"array","maxItems":6,"items":{"type":"object","properties":{
            "area":{"type":"string"},"change":{"type":"string"},"why":{"type":"string"},"priority":{"type":"string","enum":["high","medium","low"]}},"required":["area","change","why","priority"],"additionalProperties":False}}
    },"required":["ready","summary","sample_statement","questionnaire_statement","persona_statement","knowledge_statement","recommended_changes"],"additionalProperties":False}
    payload={"project":{"title":cproj.get("title"),"goal":cproj.get("goal"),"decision_use":cproj.get("decision_use"),"n":cproj.get("n"),"audience":cproj.get("audience"),"persona_dimensions":cproj.get("persona_dimensions"),"sections":sections},
             "technical_ready":bool(checked.get("can_run_live")),"actionable_blockers":checked.get("user_issues") or [],
             "internal_diagnostics":internal,"representative_sample_check":sample_audit,"data_library_context":library_context}
    from ai_router import call_structured
    out=call_structured(system=("Jsi senior research director. Proveď poslední uživatelskou kontrolu projektu před spuštěním. "
        "Interní diagnostiku použij jen k rozhodnutí, ale NIKDY uživateli nevypisuj interní názvy, kódy nebo technické termíny "
        "jako joint_unvalidated, validation tier, ESS, donor support, anchor, evidence grade nebo claim level. "
        "Pokud je problém neblokující, převeď jej na obyčejné doporučení nebo jej vůbec nezmiňuj. "
        "Vzorek považuj za reprezentativní pouze pokud representative_sample_check není BLOCKED. "
        "Data Library shrň jako praktickou větu o tom, zda projekt využívá relevantní schválené poznatky; nevydávej knowledge-only dimenzi za naměřený individuální atribut. "
        "Buď stručný, praktický a zaměřený na to, co má uživatel změnit před spuštěním."),
        messages=[{"role":"user","content":json.dumps(payload,ensure_ascii=False)}],schema=schema,schema_name="npc_final_project_review",
        anthropic_model=str(cproj.get("model") or "sonnet"),max_tokens=2200,prefer="claude_code_subscription",allow_fallback=False)
    review=out.get("data") or {}
    # Defense in depth: the model is instructed not to expose internal labels,
    # but normal UI must remain clean even if it ignores that instruction.
    import re
    forbidden=re.compile(r"(?i)joint[_ -]?unvalidated|\bunvalidated\b|validation tier|\bESS\b|donor support|population anchor|populační kotv|evidence grade|claim level|effective[_ -]?n|efektivní n")
    def clean_text(v):
        if isinstance(v,str):
            parts=re.split(r"(?<=[.!?])\s+",v)
            kept=[x for x in parts if not forbidden.search(x)]
            return " ".join(kept).strip()
        if isinstance(v,list):return [clean_text(x) for x in v]
        if isinstance(v,dict):return {k:clean_text(x) for k,x in v.items()}
        return v
    review=clean_text(review)
    review["ready"]=bool(review.get("ready")) and bool(checked.get("can_run_live")) and sample_audit.get("status") in {"PASS","PASS_WEIGHTED"}
    review.setdefault("summary","Projekt byl zkontrolován. Pokračujte podle doporučení níže.")
    review["sample_statement"]=sample_audit.get("statement") or "Vzorek se připraví automaticky v rámci zvolené populace."
    review.setdefault("knowledge_statement","Data Library nemá pro tento projekt žádný schválený doplňující poznatek." if not library_context.get('count') else f"Data Library nabízí {library_context.get('count')} relevantních schválených poznatků pro návrh a interpretaci.")
    return {"review":review,"sample_audit":sample_audit,"library_context":library_context,"technical_ready":bool(checked.get("can_run_live")),"_ai":{"provider":out.get("provider"),"model":out.get("model"),"tok_in":out.get("tok_in",0),"tok_out":out.get("tok_out",0)}}


def design_questionnaire(req:dict)->dict:
    zadani=str(req.get("zadani","")).strip()
    if not zadani: raise ValueError("Chybí zadání.")
    from navrh import navrhni_dotaznik
    brief=navrhni_dotaznik(zadani,pocet_otazek=int(req.get("pocet",6)),cilova_skupina=req.get("cilova_skupina") or None,
                           model=resolve_model(req.get("design_model") or req.get("model") or "sonnet"),n=int(req.get("n",120)),mode="dry",provider=normalize_ai_provider(req.get("provider") or get_ai_provider()))
    brief.pop("vystup",None);brief.setdefault("use_case","internal");brief.setdefault("allow_own_estimates",False)
    brief.setdefault("research_context",{"enabled":True});brief.setdefault("segment",{"mode":"none"})
    return {"brief":brief,"preflight":preflight(brief)}


def design_research_plan(req:dict)->dict:
    """Compatibility endpoint from 10.9; new UI uses persistent Claude copilot."""
    zadani=str(req.get("zadani","")).strip()
    if not zadani: raise ValueError("Popište, co chcete zjistit.")
    from research_designer import design_research
    return design_research(zadani,cilova_skupina=str(req.get("cilova_skupina") or ""),n=int(req.get("n",120)),model=resolve_model(req.get("design_model") or req.get("model") or "sonnet"),provider=normalize_ai_provider(req.get("provider") or get_ai_provider()))




def build_project_variants(analysis:dict, project:dict, requested_n:int=300)->list[dict]:
    """Three editable project designs from one brief analysis; no extra AI call."""
    rqs=[str(x).strip() for x in (analysis.get('research_questions') or []) if str(x).strip()]
    objs=[str(x).strip() for x in (analysis.get('objectives') or []) if str(x).strip()]
    hyps=[str(x).strip() for x in (analysis.get('hypotheses') or []) if str(x).strip()]
    base=max(100,int(requested_n or 300))
    return [
      {'id':'lean','title':'Rychlá orientace','badge':'rychlejší / levnější','summary':'Odpoví na hlavní rozhodovací otázku s menším rozsahem. Vhodné pro rychlý screening nebo první iteraci.','tradeoff':'Méně detailních segmentů a nižší síla pro malé podskupiny.','n':max(150,min(base,250)),'complexity':'short','research_questions':rqs[:3] or [str(project.get('goal') or '')],'objectives':objs[:3] or [str(project.get('goal') or '')],'hypotheses':hyps[:3],'deep_research':False,'recommended_dimension_topics':['demography','digital','hobby','shopping']},
      {'id':'recommended','title':'Doporučený vyvážený','badge':'doporučeno','summary':'Vyvážený design pro hlavní rozhodnutí, segmentaci i interpretaci.','tradeoff':'O něco delší běh než screening, ale výrazně robustnější výstup.','n':max(300,base),'complexity':'standard','research_questions':rqs[:8] or [str(project.get('goal') or '')],'objectives':objs[:8] or [str(project.get('goal') or '')],'hypotheses':hyps[:8],'deep_research':False,'recommended_dimension_topics':['demography','digital','media','hobby','shopping','values']},
      {'id':'deep','title':'Hloubkový diagnostický','badge':'nejvíc detailu','summary':'Rozšířený design pro složitější rozhodnutí, více hypotéz, segmenty a silnější evidenční kontext.','tradeoff':'Vyšší čas i výpočetní náročnost; Deep Research je doporučený, ne automaticky spuštěný.','n':max(500,base),'complexity':'deep','research_questions':rqs[:12] or [str(project.get('goal') or '')],'objectives':objs[:12] or [str(project.get('goal') or '')],'hypotheses':hyps[:12],'deep_research':True,'recommended_dimension_topics':['demography','digital','social','media','hobby','shopping','advertising','values','finance','work']}
    ]


def analyze_research_brief(req:dict)->dict:
    """Fast first-pass brief analysis.

    Deep Research is deliberately NOT run here. The first user action must remain
    responsive and only understand/structure the brief. Research is an explicit
    later step (questionnaire optimization, persona enrichment, or project research).
    """
    from research_designer import analyze_research, analysis_to_project_skeleton
    from provider_auth import get_ai_provider
    briefing=dict(req.get("briefing") or {})
    if req.get("goal") and not briefing.get("goal"): briefing["goal"]=req.get("goal")
    provider=normalize_ai_provider(req.get("provider") or get_ai_provider())
    requested_model=str(req.get("model") or "sonnet")
    # 17.9.1: the intake is an interactive structure pass, not long-form analysis.
    # Keep Sonnet for substantive later steps, but use Haiku on Claude Code here.
    fast_model=str(req.get('fast_model') or ('haiku' if provider=='claude_code_subscription' and requested_model in {'sonnet','claude-sonnet',''} else requested_model))
    try:
        analysis=analyze_research(briefing,model=fast_model,provider=provider,fast=True)
    except TypeError as exc:
        # Compatibility for diagnostic monkeypatches / older extension functions that
        # still expose the legacy signature. Production research_designer supports
        # fast=True; never hide a different TypeError.
        if "unexpected keyword argument 'fast'" not in str(exc): raise
        analysis=analyze_research(briefing,model=fast_model,provider=provider)
    analysis["background_research"]={"quality_status":"NOT_RUN","accepted":[],"quarantined":[],"agents":[],"sha256":None,
                                     "note":"Deep Research se při prvním pochopení briefu nespouští. Je dostupný později jako explicitní krok."}
    project=analysis_to_project_skeleton(analysis,briefing,n=int(req.get("n") or 300))
    project["research_context"]=False
    project["pre_research"]=analysis["background_research"]
    variants=build_project_variants(analysis,project,int(req.get("n") or 300))
    analysis["project_variants"]=variants
    project["design_variants"]=variants
    project["selected_design_variant"]="recommended"
    return {"analysis":analysis,"project":project,"research":analysis["background_research"],"fast_brief_analysis":True,"project_variants":variants}


def build_research_questionnaire(req:dict)->dict:
    from research_designer import build_questionnaire
    return build_questionnaire(req.get("analysis") or {},req.get("briefing") or {},n=int(req.get("n") or 300),
                               current_project=req.get("project"),model=req.get("model") or "sonnet",provider=normalize_ai_provider(req.get("provider") or get_ai_provider()))


def _xlsx_rows(raw: bytes) -> list[list[str]]:
    """Small dependency-free XLSX reader for the questionnaire import sheet."""
    import io, zipfile, xml.etree.ElementTree as ET, re
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall('m:si',ns): shared.append(''.join(t.text or '' for t in si.findall('.//m:t',ns)))
        wb=ET.fromstring(z.read('xl/workbook.xml')); rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relmap={x.attrib['Id']:x.attrib['Target'] for x in rels}
        sheets=wb.find('m:sheets',ns); target=None
        for sh in (list(sheets) if sheets is not None else []):
            rid=sh.attrib.get('{%s}id'%ns['r']); name=str(sh.attrib.get('name') or '')
            if target is None or name.strip().upper()=='DOTAZNIK': target=relmap.get(rid)
            if name.strip().upper()=='DOTAZNIK': break
        if not target: raise ValueError('XLSX neobsahuje list DOTAZNIK ani čitelný první list.')
        target=str(target).replace('\\','/').lstrip('/')
        while target.startswith('../'): target=target[3:]
        if not target.startswith('xl/'): target='xl/'+target
        root=ET.fromstring(z.read(target)); rows=[]
        for row in root.findall('.//m:sheetData/m:row',ns):
            vals={}; maxc=-1
            for c in row.findall('m:c',ns):
                ref=c.attrib.get('r','A1'); letters=re.match(r'[A-Z]+',ref).group(0); ci=0
                for ch in letters: ci=ci*26+(ord(ch)-64)
                ci-=1; maxc=max(maxc,ci); typ=c.attrib.get('t'); val=''
                if typ=='inlineStr': val=''.join(t.text or '' for t in c.findall('.//m:t',ns))
                else:
                    v=c.find('m:v',ns); rawv=v.text if v is not None else ''
                    if typ=='s' and str(rawv).isdigit(): val=shared[int(rawv)] if int(rawv)<len(shared) else ''
                    elif typ=='b': val='TRUE' if rawv=='1' else 'FALSE'
                    else: val=rawv or ''
                vals[ci]=str(val).strip()
            if maxc>=0: rows.append([vals.get(i,'') for i in range(maxc+1)])
        return rows


def import_questionnaire_payload(req: dict) -> dict:
    import csv, io
    raw=base64.b64decode(req.get('data_b64') or '')
    if not raw: raise ValueError('Nahrajte XLSX nebo CSV dotazník.')
    filename=Path(str(req.get('filename') or 'dotaznik.xlsx')).name
    if filename.lower().endswith('.csv'):
        text=raw.decode('utf-8-sig'); rows=list(csv.reader(io.StringIO(text)))
    elif filename.lower().endswith('.xlsx'):
        rows=_xlsx_rows(raw)
    else: raise ValueError('Podporovaný formát je .xlsx nebo .csv.')
    if not rows: raise ValueError('Soubor je prázdný.')
    headers=[str(x).strip().lower() for x in rows[0]]
    required={'id','otazka','typ'}
    if not required.issubset(headers): raise ValueError('Chybí povinné sloupce: '+', '.join(sorted(required-set(headers))))
    idx={h:i for i,h in enumerate(headers)}
    def get(row,key):
        i=idx.get(key); return str(row[i]).strip() if i is not None and i<len(row) else ''
    def split(x): return [v.strip() for v in str(x or '').replace('\n','|').split('|') if v.strip()]
    project=normalize_project(req.get('project') or empty_project())
    sections=[]; qblocks={}; object_count=0; question_count=0
    for row in rows[1:]:
        if not any(str(x).strip() for x in row): continue
        qid=get(row,'id') or f'Q{question_count+1}'; text=get(row,'otazka'); typ=get(row,'typ').lower(); block=get(row,'blok') or 'Dotazník'
        if not text: raise ValueError(f'{qid}: chybí znění otázky.')
        if typ=='objektova_sada':
            objects=split(get(row,'moznosti'))
            if not 4<=len(objects)<=15: raise ValueError(f'{qid}: sledovaná sada potřebuje 4–15 srovnatelných položek.')
            try: lo=int(float(get(row,'skala_min') or 1)); hi=int(float(get(row,'skala_max') or 10))
            except Exception: lo,hi=1,10
            sections.append({'id':qid,'type':'object_battery','title':get(row,'sledovana_sada') or block or qid,'purpose':get(row,'poznamka'),
                             'object_family':get(row,'sledovana_sada') or block or 'objekty','object_type':get(row,'sledovana_sada') or block or 'objekty',
                             'objects':objects,'object_question':text if '{object}' in text else text.rstrip('?')+' — {object}?','scale':[lo,hi],
                             'scale_labels':['minimum','maximum'],'familiarity_required':False,'output_type':'pozicni_mapa','visualize':True,'metadata':{'tracked_set':True,'imported':True}})
            object_count+=1; continue
        if typ not in {'vyber','multi','skala','otevrena'}: raise ValueError(f'{qid}: neznámý typ {typ}.')
        if block not in qblocks:
            qblocks[block]={'id':'sec_import_'+str(len(qblocks)+1),'type':'questions','title':block,'purpose':'','questions':[]};sections.append(qblocks[block])
        q={'id':qid,'text':text,'typ':typ,'povolit_nevim':get(row,'povolit_nevim').lower() in {'1','true','ano','yes'}}
        if typ in {'vyber','multi'}:
            cats=split(get(row,'moznosti'))
            if len(cats)<2: raise ValueError(f'{qid}: výběrová otázka potřebuje alespoň 2 možnosti.')
            q['kategorie']=cats
        elif typ=='skala':
            try:q['skala']=[int(float(get(row,'skala_min') or 1)),int(float(get(row,'skala_max') or 10))]
            except Exception:q['skala']=[1,10]
            q['popisky_skaly']=['minimum','maximum']
        else:q['max_slov']=35
        qblocks[block]['questions'].append(q);question_count+=1
    project['sections']=sections
    project['research_plan']['status']='questionnaire_ready'
    return {'project':normalize_project(project),'summary':{'question_count':question_count,'tracked_sets':object_count,'sections':len(sections)},'filename':filename}


def deep_research_project(req: dict, progress=None) -> dict:
    from research_context import ResearchConfig, run_dual_research
    from dataclasses import asdict
    project=normalize_project(req.get('project') or empty_project())
    provider=normalize_ai_provider(req.get('provider') or (project.get('run_policy') or {}).get('provider') or get_ai_provider())
    topic=' | '.join(x for x in [project.get('goal'),project.get('decision_use'),(project.get('briefing') or {}).get('product_description'),(project.get('briefing') or {}).get('situation')] if str(x or '').strip())
    try: questions=compile_project(project).get('brief',{}).get('otazky') or []
    except Exception: questions=[]
    if not questions: questions=[{'id':'research_goal','text':topic or project.get('title') or 'Výzkumné téma'}]
    cm=str((project.get('run_policy') or {}).get('cost_mode') or 'REFERENCE').upper()
    preset={'ECONOMY':(6,10),'STANDARD':(10,18),'REFERENCE':(16,28)}.get(cm,(16,28))
    selected_model=str(req.get('model') or project.get('model') or ('gpt-5' if provider=='openai' else 'sonnet'))
    cfg=ResearchConfig(enabled=True,topic=topic,max_sources_per_agent=int(req.get('max_sources_per_agent') or preset[0]),strict_consensus=True,allow_single_agent_primary=True,allow_degraded_single_agent=True,max_context_blocks=int(req.get('max_context_blocks') or preset[1]),anthropic_model=selected_model,openai_model=selected_model)
    rb=run_dual_research(cfg,questions,provider_override=provider,progress=progress);obj=asdict(rb)
    return {'research':obj,'quality_status':rb.quality_status,'accepted_count':len(rb.accepted),'quarantined_count':len(rb.quarantined),'provider':provider,'sha256':rb.sha256}


def optimize_questionnaire(req: dict, progress=None) -> dict:
    from research_designer import analyze_research, build_questionnaire
    project=normalize_project(req.get('project') or empty_project()); research=(req.get('research') or {}).get('research') or req.get('research')
    if not research:
        research=deep_research_project(req,progress=progress).get('research') or {}
    briefing={**(project.get('briefing') or {}),'goal':project.get('goal'),'decision_use':project.get('decision_use')}
    safe=[]
    for x in (research.get('accepted') or [])[:18]: safe.append(f"- {x.get('claim')} [zdroj: {x.get('source_title')}; {x.get('source_url')}]")
    if safe: briefing['what_is_known']=(str(briefing.get('what_is_known') or '')+'\n\nDEEP RESEARCH — bezpečný background context:\n'+'\n'.join(safe)).strip()
    model=str(req.get('model') or ('gpt-5' if normalize_ai_provider(req.get('provider') or (project.get('run_policy') or {}).get('provider'))=='openai' else 'sonnet'))
    analysis=analyze_research(briefing,model=model,provider=normalize_ai_provider(req.get("provider") or (project.get("run_policy") or {}).get("provider") or get_ai_provider()));analysis['background_research']=research
    built=build_questionnaire(analysis,briefing,n=int(project.get('n') or 300),current_project=project,model=model,provider=normalize_ai_provider(req.get("provider") or (project.get("run_policy") or {}).get("provider") or get_ai_provider()))
    built['project']['pre_research']=research;built['project']['research_context']=True;built['analysis']=analysis;built['research']=research
    return built


def repair_questionnaire_issue(req:dict)->dict:
    """Repair one concrete questionnaire question without regenerating the instrument."""
    from ai_router import call_structured
    project=json.loads(json.dumps(req.get("project") or {}))
    issue=dict(req.get("issue") or {})
    qid=str(req.get("question_id") or issue.get("where") or "").strip()
    if not qid or qid in {"dotaznik","metodika"}: raise ValueError("Nález není přiřazen ke konkrétní otázce.")
    target=None
    for sec in project.get("sections") or []:
        if sec.get("type")!="questions": continue
        for q in sec.get("questions") or []:
            if str(q.get("id") or "")==qid: target=q; break
        if target is not None: break
    if target is None: raise ValueError(f"Otázku {qid} se nepodařilo najít v projektu.")
    provider=normalize_ai_provider(req.get("provider") or (project.get("run_policy") or {}).get("provider") or get_ai_provider())
    model=str(req.get("model") or project.get("model") or "sonnet")
    schema={"type":"object","properties":{"text":{"type":"string"},"typ":{"type":"string","enum":["vyber","multi","skala","otevrena"]},"kategorie":{"type":"array","items":{"type":"string"},"maxItems":24},"skala":{"type":"array","items":{"type":"integer"},"minItems":2,"maxItems":2},"popisky_skaly":{"type":"array","items":{"type":"string"},"minItems":2,"maxItems":2},"povolit_nevim":{"type":"boolean"},"filtr":{"type":["string","null"]},"repair_note":{"type":"string"}},"required":["text","typ","kategorie","skala","popisky_skaly","povolit_nevim","filtr","repair_note"],"additionalProperties":False}
    payload={"project_goal":project.get("goal"),"decision_use":project.get("decision_use"),"issue":issue,"question":target}
    rr=call_structured(system=("Jsi senior survey metodik. Oprav POUZE jednu konkrétní otázku podle nálezu. Zachovej její výzkumný význam a pokud nejsou možnosti příčinou chyby, zachovej je. Neodstraňuj cenové body, chutě, značky ani jiné legitimní odpovědi jen proto, že jsou metodicky neobvyklé. Strukturální chybu oprav minimální změnou. Vrať kompletní opravenou otázku."),messages=[{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],schema=schema,schema_name="npc_question_repair",anthropic_model=model,openai_model=model if provider=="openai" else None,max_tokens=2200,prefer=provider,allow_fallback=False)
    data=dict(rr.get("data") or {})
    repaired=dict(target); repaired["text"]=str(data.get("text") or target.get("text") or "").strip(); repaired["typ"]=str(data.get("typ") or target.get("typ") or "vyber")
    if repaired["typ"] in {"vyber","multi"}:
        repaired["kategorie"]=[str(x).strip() for x in (data.get("kategorie") or target.get("kategorie") or []) if str(x).strip()]
    else: repaired.pop("kategorie",None)
    if repaired["typ"]=="skala":
        repaired["skala"]=list(data.get("skala") or target.get("skala") or [1,10])[:2]; repaired["popisky_skaly"]=list(data.get("popisky_skaly") or target.get("popisky_skaly") or ["minimum","maximum"])[:2]
    repaired["povolit_nevim"]=bool(data.get("povolit_nevim",target.get("povolit_nevim",False)))
    f=data.get("filtr"); repaired.pop("filtr",None) if f in (None,"") else repaired.__setitem__("filtr",str(f))
    repaired["id"]=qid; repaired["metadata"]=dict(target.get("metadata") or {})
    target.clear(); target.update(repaired)
    # Normalize as an immediate safety check; this must never repair the rest of the questionnaire silently.
    normalized=normalize_project(project)
    return {"project":normalized,"question_id":qid,"question":repaired,"repair_note":str(data.get("repair_note") or "Otázka upravena podle nálezu."),"provider":rr.get("provider") or provider,"model":rr.get("model") or model}


def suggest_persona_dimensions(req: dict) -> dict:
    from ai_router import call_structured
    project=normalize_project(req.get('project') or empty_project());provider=normalize_ai_provider(req.get('provider') or (project.get('run_policy') or {}).get('provider') or get_ai_provider())
    model=str(req.get('model') or ('gpt-5' if provider=='openai' else 'sonnet'))
    labels=dict(req.get('dimension_labels') or {})
    from data_library import active_dimensions
    library_dims=active_dimensions()
    for did,d in library_dims.items(): labels.setdefault(did,str(d.get('label') or did))
    from audience_dimensions import catalog as factor_catalog
    factors=factor_catalog(core.load_panel_cached(),include_research_only=False)
    factor_rows=[{'id':x['id'],'label':x['label'],'category':x['category_label'],'status':x['status']} for x in factors.get('factors',[]) if x.get('filterable')][:160]
    research=req.get('research') or project.get('pre_research') or {}
    schema={'type':'object','properties':{'dimensions':{'type':'array','items':{'type':'string'}},'reasoning':{'type':'array','items':{'type':'object','properties':{'dimension':{'type':'string'},'why':{'type':'string'}},'required':['dimension','why'],'additionalProperties':False}},'new_dimensions':{'type':'array','maxItems':6,'items':{'type':'object','properties':{'label':{'type':'string'},'dimension_id':{'type':'string'},'why':{'type':'string'},'evidence_needed':{'type':'string'},'source_strategy':{'type':'string','enum':['document','deep_research','either']},'suggested_predictors':{'type':'array','items':{'type':'string'}}},'required':['label','dimension_id','why','evidence_needed','source_strategy','suggested_predictors'],'additionalProperties':False}},'research_used':{'type':'boolean'}},'required':['dimensions','reasoning','new_dimensions','research_used'],'additionalProperties':False}
    payload={'goal':project.get('goal'),'decision_use':project.get('decision_use'),'briefing':project.get('briefing'),'questionnaire':project.get('sections'),'available_dimensions':labels,'existing_dimensions':(project.get('persona_dimensions') or {}).get('approved') or [],'research_context':(research.get('accepted') or [])[:20],'library_dimensions':library_dims,'society_factor_catalog':factor_rows}
    system='Jsi senior research metodik. Vyber 3–8 existujících dimenzí persony, které mohou materiálně zlepšit odpovědi pro tento výzkum. Aktivní dimenze vybírej VÝHRADNĚ z available_dimensions. Navíc můžeš navrhnout max. 6 NOVÝCH dimenzí, pokud v katalogu chybí důležitý konstrukt. Novou dimenzi nikdy nevydávej za existující data: musí projít Data Library, mít externí evidenci a pro dosimulování i kvantitativní populační kotvu (prevalence/průměr) a vztah k existujícím predictorům. suggested_predictors vybírej pouze z society_factor_catalog. Citlivé charakteristiky nenavrhuj jako běžný targeting.'
    rr=call_structured(system=system,messages=[{'role':'user','content':json.dumps(payload,ensure_ascii=False,default=str)}],schema=schema,schema_name='npc_persona_dimensions',anthropic_model=model,openai_model=model if provider=='openai' else None,max_tokens=3200,prefer=provider,allow_fallback=False)
    data=rr.get('data',{}) or {};allowed={str(k).strip():str(v).strip() for k,v in labels.items() if str(k).strip()};label_to_id={str(v).strip().casefold():k for k,v in allowed.items() if str(v).strip()}
    chosen=[];unsupported=[]
    for raw in data.get('dimensions') or []:
        x=str(raw or '').strip();did=x if x in allowed else label_to_id.get(x.casefold())
        if did and did not in chosen:chosen.append(did)
        elif x and x not in unsupported:unsupported.append(x)
    reasoning=[]
    for row in data.get('reasoning') or []:
        if not isinstance(row,dict):continue
        dim=str(row.get('dimension') or '').strip();did=dim if dim in allowed else label_to_id.get(dim.casefold());reasoning.append({'dimension':did or dim,'why':str(row.get('why') or '').strip(),'supported':bool(did)})
    factor_ids={x['id'] for x in factor_rows};newdims=[]
    for row in data.get('new_dimensions') or []:
        if not isinstance(row,dict):continue
        label=str(row.get('label') or '').strip();did=re.sub(r'[^a-z0-9_]+','_',str(row.get('dimension_id') or label).lower()).strip('_')[:100]
        if len(label)<2 or not did:continue
        newdims.append({'label':label,'dimension_id':did,'why':str(row.get('why') or '').strip(),'evidence_needed':str(row.get('evidence_needed') or '').strip(),'source_strategy':str(row.get('source_strategy') or 'either'),'suggested_predictors':[x for x in (row.get('suggested_predictors') or []) if x in factor_ids][:8]})
    return {'dimensions':chosen[:8],'unsupported_dimensions':unsupported[:8],'reasoning':reasoning[:12],'new_dimension_suggestions':newdims[:6],'research_used':bool(data.get('research_used')),'provider':rr.get('provider') or provider,'model':rr.get('model') or model,'factor_catalog_count':factors.get('filterable_count',0)}


def verify_result_context(req:dict)->dict:
    from result_context import verify_results, save_verification
    project=req.get("project") or {}
    summary=req.get("result_summary") or {}
    bundle=verify_results(project,summary,target_ids=req.get("target_ids") or None,
                          include_mapped=bool(req.get("include_mapped",False)),
                          max_sources_per_agent=int(req.get("max_sources_per_agent") or 8))
    run_id=str(summary.get("run_id") or int(time.time()))
    path=save_verification(bundle,OUT/"external_verification"/run_id,run_id)
    return {"verification":bundle,"file":_file_url(path)}


def calibrate_result_context(req:dict)->dict:
    from result_context import contextual_calibration, save_calibration
    verification=req.get("verification") or {}
    result=contextual_calibration(verification,strength=str(req.get("strength") or "medium"))
    run_id=str(req.get("run_id") or int(time.time()))
    path=save_calibration(result,OUT/"external_verification"/run_id,run_id)
    return {"calibration":result,"file":_file_url(path)}


def create_final_client_report(req:dict)->dict:
    from final_client_report import export_final_client_report
    project=req.get("project") or {}
    summary=req.get("result_summary") or {}
    verification=req.get("verification") or {}
    if not verification:
        raise ValueError("Nejdřív spusťte externí ověření; Final Client Report vzniká až po triangulaci.")
    support=req.get("support") or ((summary.get("donor_support") or {}) if isinstance(summary,dict) else {})
    run_id=str(summary.get("run_id") or int(time.time()))
    out=OUT/"final_reports"/run_id/f"FINAL_CLIENT_REPORT_{run_id}.docx"
    path=export_final_client_report(out,project=project,result_summary=summary,verification=verification,support=support or None)
    return {"file":_file_url(path),"run_id":run_id,"verification_sha256":verification.get("sha256")}


def _file_url(value:str|Path|None)->str|None:
    if not value:return None
    p=Path(value).resolve()
    try:
        rel=p.relative_to(OUT.resolve())
        return "/files/"+quote(str(rel).replace("\\","/"), safe="/")
    except Exception:
        pass
    # FullSim and batch artifacts intentionally live outside prototype_outputs.
    # Expose only explicitly whitelisted generated subtrees, never arbitrary disk paths.
    try:
        rel=p.relative_to(ROOT.resolve())
        top=rel.parts[0] if rel.parts else ''
        if top in {'full_simulation_runs','full_simulation_batches','full_simulation_benchmarks','demo_library'}:
            return "/artifacts/"+quote(str(rel).replace("\\","/"),safe="/")
    except Exception:
        pass
    return str(p)


def _public_study(result:dict)->dict:
    files={k:_file_url(v) for k,v in (result.get("files") or {}).items()}
    seg=result.get("segments")
    public_seg=({k:v for k,v in seg.items() if k not in {"labels","model"}} if isinstance(seg,dict) else None)
    return {"validation":result.get("validation"),"meta":result.get("meta"),"files":files,"spec":result.get("spec"),"segments":public_seg}


def _public_project(result:dict)->dict:
    out={"project":result.get("project"),"compiled_question_count":result.get("compiled_question_count"),"main":result.get("main"),"batteries":[]}
    for b in result.get("batteries") or []:
        bb=dict(b); bb["files"]={k:_file_url(v) for k,v in (b.get("files") or {}).items()}; out["batteries"].append(bb)
    return out


def run_discovery(req:dict)->dict:
    run_id=str(req.get("run_id") or "").strip(); qid=str(req.get("question_id") or "").strip()
    positives=[str(x) for x in (req.get("positive_answers") or []) if str(x).strip()]
    if not run_id or not qid or not positives: raise ValueError("Vyber dokončený běh, otázku a pozitivní odpovědi.")
    detail_path=ROOT/"runs"/run_id/"detail_internal.csv"
    if not detail_path.is_file(): raise FileNotFoundError("Interní respondentní data běhu nejsou dostupná.")
    detail=pd.read_csv(detail_path,low_memory=False)
    from segment import discover_audience_on_panel
    prop,meta=discover_audience_on_panel(core.load_panel_cached(),detail,qid,positives,
        min_positive=int(req.get("min_positive") or 20),seed=int(req.get("seed") or 42),
        prevalence_target=(float(req["prevalence_target"]) if req.get("prevalence_target") is not None else None),
        prevalence_source=req.get("prevalence_source"))
    d=OUT/"discovery"/run_id/f"{qid}_{int(time.time())}"; d.mkdir(parents=True,exist_ok=True)
    panel=core.load_panel_cached()
    df=pd.DataFrame({"propensity":prop.to_numpy()})
    if "panel_row_id" in panel.columns: df.insert(0,"panel_row_id",panel["panel_row_id"].astype(str).to_numpy())
    else: df.insert(0,"panel_index",panel.index.to_numpy())
    pp=d/"segment_propensity.csv"; df.to_csv(pp,index=False)
    mp=d/"segment_model.json"; mp.write_text(json.dumps(meta,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    conf=meta.get("confidence_class") or ("B" if req.get("prevalence_target") is not None else "C")
    return {"run_id":run_id,"question_id":qid,"positive_answers":positives,"confidence_class":conf,
            "epistemic_status":meta.get("epistemic_status","synthetic_outcome_discovery"),"ess_population":meta.get("ess_population"),
            "prevalence":meta.get("prevalence"),"profile":meta.get("profile") or [],
            "segment_config":{"mode":"propensity_file","name":f"Ideální skupina: {qid}","propensity_file":str(pp),"metadata_file":str(mp)},
            "files":{"propensity":_file_url(pp),"model":_file_url(mp)},
            "note":"Skupina je odvozena z odpovědí tohoto NPC běhu. Bez externí human kotvy je explorativní (C)."}


def save_api_keys(req:dict)->dict:
    """Store normalized local API keys and report the actual credential source."""
    return save_local_keys(
        anthropic_key=req.get("anthropic_key") if "anthropic_key" in req else None,
        openai_key=req.get("openai_key") if "openai_key" in req else None,
        ai_provider=req.get("ai_provider") if "ai_provider" in req else None,
        clear_empty=bool(req.get("clear_empty",False)),
    )

def check_anthropic_provider(req:dict)->dict:
    """Explicit live provider check requested from Settings."""
    return probe_anthropic(req.get("model") or "sonnet")

def check_ai_providers(req:dict)->dict:
    """Probe the selected Claude transport. No non-Claude LIVE fallback exists."""
    selected=normalize_ai_provider(req.get("provider") or get_ai_provider())
    skipped={"ok":False,"kind":"SKIPPED","message":"Nezvolená cesta nebyla při tomto testu volána."}
    a=dict(skipped); cc=dict(skipped)
    if selected=="anthropic":
        a=probe_anthropic(req.get("anthropic_model") or "sonnet") if has_anthropic_key() else {"ok":False,"kind":"MISSING","message":"Claude API klíč není nastaven."}
    if selected=="claude_code_subscription":
        from claude_code_provider import health
        cc=health()
        if cc.get("ok") and bool(req.get("roundtrip",False)):
            from ai_router import roundtrip_test
            cc={**cc,"roundtrip":roundtrip_test(prefer="claude_code_subscription")};cc["ok"]=bool(cc["roundtrip"].get("ok"))
    selected_status=cc if selected=="claude_code_subscription" else a
    from provider_auth import detected_env_overrides
    overrides=detected_env_overrides()
    label="Claude Code" if selected=="claude_code_subscription" else "Claude API"
    msg=(label+" je připravený.") if selected_status.get("ok") else (label+" neprošel live testem.")
    return {"ok":bool(selected_status.get("ok")),"preferred":selected if selected_status.get("ok") else None,"selected":selected,
            "claude_api":a,"anthropic":a,"claude_code":cc,"openai":{"ok":False,"kind":"DISABLED","message":"OpenAI není LIVE provider v této edici."},
            "env_overrides":overrides,"message":msg}

def diagnose_ai(req:dict)->dict:
    """Full chain diagnosis: storage → key type → auth → models → structured call."""
    from provider_diagnostics import full_report
    return full_report(live=bool(req.get("live",True)))


def _fullsim_spec_from_payload(payload:dict)->dict:
    spec=dict(payload.get("spec") or {})
    if not spec.get("questions") and payload.get("project"):
        raw_project=payload.get("project") or {}
        compile_warning=""
        try:
            c=compile_project(raw_project)
        except Exception as exc:
            # Scenario/FullSim is allowed to derive its own transparent outcome
            # instrument from the brief. A partially structured AI project must not
            # kill the whole simulation just because an unrelated questionnaire
            # section is incomplete. The normal survey/preflight path remains strict.
            compile_warning=f"PROJECT_NORMALIZATION_FOR_SCENARIO: {type(exc).__name__}: {exc}"[:1200]
            try:
                np=normalize_project(raw_project)
            except Exception:
                np=dict(raw_project)
            c={"brief":{"otazky":[]},"project":np}
        qs=[]
        for q in c.get("brief",{}).get("otazky") or []:
            # Full Simulation v1 benchmarks closed outcomes; open verbatims can be
            # added later without contaminating the scoring contract.
            if len(q.get("kategorie") or [])>=2:
                qs.append(q)
        if not qs:
            outcome=str(spec.get("outcome") or spec.get("topic") or (payload.get("project") or {}).get("goal") or "Celkový dopad scénáře na zkoumanou věc").strip()
            qs=[{"id":"SCENARIO_OUTCOME","text":outcome,"typ":"vyber","kategorie":["Výrazně negativní","Spíše negativní","Beze změny","Spíše pozitivní","Výrazně pozitivní"]}]
            spec["auto_outcome_question"]=True
        if compile_warning:
            spec["project_compile_warning"]=compile_warning
        spec["questions"]=qs
        p=c.get("project") or {}
        spec.setdefault("topic",p.get("goal") or p.get("title") or "")
        spec.setdefault("domain",(p.get("research_plan") or {}).get("recommended_topics",["general"])[0] if (p.get("research_plan") or {}).get("recommended_topics") else "general")
        spec.setdefault("n",int(p.get("n") or 300))
        provider=normalize_ai_provider((p.get("run_policy") or {}).get("provider") or get_ai_provider())
        spec.setdefault("provider",provider)
        spec["world_model_provider"]="selected"
        spec["model"]=resolve_provider_model(provider,spec.get("model") or p.get("model") or "sonnet")
        budget=(p.get("budget") or {}).get("max_usd")
        if budget not in (None, ""):
            spec.setdefault("budget_max_usd",float(budget))
    return spec



def _panel_path_for_project(project:dict|None) -> str:
    """Resolve the exact panel backing the project for scenario/FullSim.

    User-uploaded audiences live in ``audience_registry``. Packaged special views
    (``builtin_special:<key>``) live in ``SPECIAL_PANELS`` and must never be sent
    through that registry. Older AI-generated projects may also carry only
    ``special_panel_key``; accept that canonical key for backwards compatibility.
    """
    p=project or {}
    aud=(p.get("audience") or {})
    mode=str(aud.get("source_mode") or "population").strip().lower()
    if mode in {"customer","special_audience"}:
        dataset_id=str(aud.get("dataset_id") or "").strip()
        special_key=str(aud.get("special_panel_key") or "").strip()
        if dataset_id.startswith("builtin_special:"):
            special_key=dataset_id.split(":",1)[1].strip()
        if special_key:
            spec=get_special_panel(special_key)
            if not spec:
                raise ValueError(f"Neznámý vestavěný special panel: {special_key}")
            path=(ROOT/str(spec.get("file") or "")).resolve()
            if not path.is_file():
                raise FileNotFoundError(f"Chybí soubor special panelu: {path}")
            return str(path)
        if not dataset_id:
            raise ValueError("Full Simulation vyžaduje vybraný dataset pro Customer / Special Audience.")
        _,meta=load_audience_frame(dataset_id)
        runtime_csv=str(meta.get("runtime_csv") or "").strip()
        if not runtime_csv:
            raise RuntimeError(f"Audience {dataset_id} nemá runtime_csv.")
        return str((ROOT/runtime_csv).resolve())
    try:
        from population_context import panel_path_for, project_population_mode
        return str(panel_path_for(project_population_mode(p)))
    except Exception:
        return str(core.PANEL_PATH)

def _start_job(payload:dict,kind="run")->str:
    """Enqueue one durable atomic UI action inside a persistent project."""
    from project_store import ProjectStore
    from project_pipeline import LEGACY_STAGE_MAP, resolve_stage, fingerprint
    st=_ros_store(); client_request_id=str(payload.get("client_request_id") or "").strip(); idem=(f"client:{kind}:{client_request_id}" if client_request_id else None)
    if idem:
        with st.cx() as c:
            old=c.execute('SELECT job_id FROM jobs WHERE idempotency_key=?',(idem,)).fetchone()
        if old:return str(old['job_id'])
    project=payload.get("project") or {}; pid=str(payload.get("project_id") or project.get("project_id") or "").strip(); rev=int(payload.get("project_revision") or 0)
    sim_kind=kind.startswith(('sim','fullsim','scenario')) or 'simulation' in kind
    utility_kind=kind in {'copilot','project_assistant','ai_diagnose'}
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
    stored_ptype=''
    try:
        snap=ps.get(pid) if pid else None
        if snap: stored_ptype=str(snap.get('project_type') or '').strip().lower()
        if (not pid or not snap) and not utility_kind:
            if sim_kind:
                created=ps.create_project(project_type='simulation',title=str((payload.get('spec') or {}).get('name') or project.get('title') or 'Nová simulace'),project={'schema_version':'simulation-project-v1','title':str((payload.get('spec') or {}).get('name') or project.get('title') or 'Nová simulace'),'simulation':payload.get('spec') or {},'research_project':project or {}},runtime_version=build_version())
            else:
                created=ps.create_project(project_type='research',title=str(project.get('title') or 'Nový výzkum'),project=project or empty_project(),runtime_version=build_version())
            pid=created['project_id'];rev=int(created['revision']);payload['project_id']=pid;payload['project_revision']=rev
        elif snap and rev<=0:
            rev=int(snap.get('revision') or 1);payload['project_revision']=rev
    finally: ps.close()
    rp=(project.get("run_policy") or {}) if isinstance(project,dict) else {}
    provider=normalize_ai_provider(payload.get("provider") or rp.get("provider") or (payload.get("spec") or {}).get("provider") or get_ai_provider())
    payload['provider']=provider
    if isinstance(project,dict):project.setdefault('run_policy',{})['provider']=provider;project['run_policy']['allow_provider_fallback']=False
    budget=payload.get("budget_max_usd")
    if budget in (None,"") and isinstance(project,dict): budget=(project.get("budget") or {}).get("max_usd")
    _foreground_priorities={"research_analysis":100,"questionnaire_build":98,"questionnaire_optimize":98,"questionnaire_repair":99,"final_review":96,"scenario_compile":96,"scenario_compile_batch":96,"simulation_context_enrich":96,"simulation_context_deep":95,"simulation_uncertainty_resolve":96,"fullsim_pipeline":95,"fullsim_batch_pipeline":95,"audience_propose":94,"audience_strategy":94,"persona_suggest":92,"fullsim_prepare":90,"fullsim_run":90,"ai_diagnose":88}
    _priority=int(payload.get("priority") or _foreground_priorities.get(kind,85))
    # The stored project decides the pipeline. Deriving it from the action name made a
    # research-flavoured action on a simulation project target a non-existent stage.
    ptype=stored_ptype if stored_ptype in {'simulation','research'} else ('simulation' if sim_kind else 'research')
    stage_id='' if utility_kind else resolve_stage(ptype,LEGACY_STAGE_MAP.get(kind),default=('WORLDS' if ptype=='simulation' else 'RESEARCH_DESIGN'))
    artifact_target='' if utility_kind else (('SIMULATION_' if ptype=='simulation' else 'RESEARCH_')+kind.upper());fp=fingerprint({'kind':kind,'payload':{k:v for k,v in payload.items() if k not in {'client_request_id','history'}}})
    wid=st.create_workflow(project_id=pid,project_revision=rev,workflow_type="project_atomic_action",priority=_priority,budget_usd=(float(budget) if budget not in (None,"") else None),cost_mode=str(rp.get("cost_mode") or "REFERENCE").upper(),metadata={"legacy_kind":kind,"research_os":build_version(),"durable_project_action":True,"project_type":ptype,"stage_id":stage_id})
    jid=st.add_job(wid,kind,"legacy_task",priority=_priority,provider_policy=provider,input_data={"legacy_kind":kind,"payload":payload,"project":project,"project_id":pid,"project_revision":rev,"stage_id":stage_id,"artifact_target":artifact_target,"input_fingerprint":fp,"phase_policy":{"provider":provider}},max_attempts=3,idempotency_key=idem,project_id=pid,project_revision=rev,stage_id=stage_id,artifact_target=artifact_target,input_fingerprint=fp)
    st.queue_ready_jobs(wid);return jid

def save_project_attachment(req:dict)->dict:
    raw=base64.b64decode(req.get('data_b64') or '')
    if not raw: raise ValueError('Příloha je prázdná.')
    if len(raw)>25*1024*1024: raise ValueError('Jedna příloha může mít maximálně 25 MB.')
    name=Path(str(req.get('filename') or 'attachment')).name
    import re
    safe=re.sub(r'[^A-Za-z0-9._ -]+','_',name)[:160] or 'attachment'
    aid='ATT-'+hashlib.sha256(raw+str(time.time_ns()).encode()).hexdigest()[:14]
    stored=f'{aid}_{safe}'; path=PROJECT_ATTACHMENTS/stored; path.write_bytes(raw)
    try:
        from data_library import _extract_text
        text=_extract_text(raw,safe)
        if text.startswith('[TEXT_EXTRACTION_FAILED:'): text=''
    except Exception:
        text=''
    ext=Path(safe).suffix.lower(); digest=hashlib.sha256(raw).hexdigest(); pid=str(req.get('project_id') or '').strip()
    if pid:
        from project_store import ProjectStore
        ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
        try:
            snap=ps.get(pid); rev=int(req.get('project_revision') or ((snap or {}).get('revision') or 0)) or None
            ps.bind_attachment(project_id=pid,revision=rev,attachment_id=aid,filename=safe,stored_path=str(path),sha256=digest,size_bytes=len(raw),metadata={'extension':ext,'text_extracted':bool(text)})
        finally:ps.close()
    return {'attachment_id':aid,'filename':safe,'stored_name':stored,'size_bytes':len(raw),'sha256':digest,
            'kind':'file','extension':ext,'text_extracted':bool(text),'context_excerpt':text[:6000],
            'project_id':pid or None,'download_url':'/project-attachments/'+quote(stored)}


def save_project_state(req:dict)->dict:
    from project_store import ProjectStore
    ps=ProjectStore(ROOT/"data"/"project_store.sqlite")
    try:
        pid=req.get("project_id") or None;snap=ps.get(str(pid)) if pid else None
        panel_version=str(req.get('panel_version') or '').strip()
        if not panel_version:
            from pipeline import resolve_panel_metadata
            panel_version=str(resolve_panel_metadata(core.PANEL_PATH).get('panel_version') or '')
        ptype=str(req.get('project_type') or ((snap or {}).get('project_type') or 'research')).lower()
        fn=ps.save_raw if ptype=='simulation' else ps.save
        return fn(req.get("project") or {}, project_id=pid,parent_project_id=req.get("parent_project_id") or None,analysis=req.get("analysis") or {},panel_version=panel_version,reason=str(req.get("reason") or "autosave"),project_type=ptype,runtime_version=build_version())
    finally: ps.close()

def project_history(limit=100):
    from project_store import ProjectStore
    from demo_showcase import project_catalog, load as load_demo
    ps=ProjectStore(ROOT/"data"/"project_store.sqlite")
    try:
        rows=ps.list(limit,include_archived=True)
        enriched=[]
        for row in rows:
            x=dict(row)
            try:
                snap=ps.get(str(x.get('project_id') or '')) or {}
                project=snap.get('project') or {}
                analysis=snap.get('analysis') or {}
                if x.get('project_type')=='simulation':
                    sim=project.get('simulation') or project
                    aud=sim.get('audience') or project.get('audience') or {}
                    x['goal']=str(sim.get('brief') or sim.get('context') or project.get('goal') or '')
                    x['research_question']=str(sim.get('decision') or project.get('decision_use') or x['goal'] or 'Jak se změní chování populace v navrženém scénáři?')
                    x['population']=str(aud.get('description') or aud.get('population') or 'ČR 18+ / dle projektu')
                    x['client']=str(sim.get('client') or project.get('client') or '')
                    run=project.get('fullsim_run') or {}
                    x['study_result']=str(run.get('headline') or run.get('recommendation') or ('Simulace dokončena.' if x.get('status')=='COMPLETED' else 'Simulace je '+str(x.get('status') or 'rozpracovaná').lower()+'.'))
                else:
                    aud=project.get('audience') or {}
                    rp=project.get('research_plan') or {}
                    qs=rp.get('research_questions') or []
                    briefing=project.get('briefing') or {}
                    x['goal']=str(project.get('goal') or '')
                    x['research_question']=str((qs[0] if qs else None) or project.get('goal') or 'Výzkumná otázka zatím není vyplněná.')
                    x['population']=str(aud.get('description') or aud.get('population') or 'ČR 18+ / dle projektu')
                    x['client']=str(briefing.get('client') or briefing.get('organization') or project.get('client') or '')
                    x['study_result']=str(analysis.get('executive_answer') or analysis.get('recommendation') or ('Výzkum dokončen.' if x.get('status')=='COMPLETED' else 'Výzkum je '+str(x.get('status') or 'rozpracovaný').lower()+'.'))
            except Exception:
                pass
            enriched.append(x)
        try:
            js=_ros_store(); jobs=js.list_jobs(limit=2000); by={}
            for j in jobs:
                pid=str(j.get('project_id') or '')
                if not pid:continue
                b=by.setdefault(pid,{'running':0,'waiting_user':0,'waiting_ai':0,'failed':0,'queued':0,'latest_job_status':None,'latest_job_kind':None})
                st=str(j.get('status') or '')
                if st=='RUNNING':b['running']+=1
                elif st=='WAITING_USER':b['waiting_user']+=1
                elif st in {'WAITING_CREDITS','WAITING_CAPACITY','RECOVERY_REQUIRED'}:b['waiting_ai']+=1
                elif st=='FAILED':b['failed']+=1
                elif st in {'READY','QUEUED','RETRYING','WAITING_DEPENDENCY'}:b['queued']+=1
                if b['latest_job_status'] is None:b['latest_job_status']=st;b['latest_job_kind']=j.get('kind')
            for x in enriched:x['job_summary']=by.get(str(x.get('project_id') or ''),{'running':0,'waiting_user':0,'waiting_ai':0,'failed':0,'queued':0})
        except Exception:
            for x in enriched:x['job_summary']={'running':0,'waiting_user':0,'waiting_ai':0,'failed':0,'queued':0}
    finally:ps.close()
    # DEMO metadata is already human-readable in demo_showcase; do not load all
    # heavy seed/output files just to render the Project Management list.
    demos=[dict(x) for x in project_catalog()]
    return demos+enriched

def load_project_state(req:dict)->dict:
    from project_store import ProjectStore
    from demo_showcase import find as find_demo, load as load_demo
    pid=str(req.get("project_id") or "").strip()
    if not pid: raise ValueError("Chybí project_id")
    if find_demo(pid):
        d=load_demo(pid)
        for f in d.get('files') or []:f['download_url']=_file_url(f.get('path'))
        for _k,v in (d.get('primary_files') or {}).items():
            if v:v['download_url']=_file_url(v.get('path'))
        return d
    ps=ProjectStore(ROOT/"data"/"project_store.sqlite")
    try:
        x=ps.get(pid, int(req["revision"]) if req.get("revision") not in (None,"") else None)
        if not x: raise FileNotFoundError("Projekt/revize nenalezena")
        return x
    finally:ps.close()

def create_project_state(req:dict)->dict:
    from project_store import ProjectStore
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
    try:return ps.create_project(project_type=str(req.get('project_type') or 'research'),title=req.get('title'),project=req.get('project'),parent_project_id=req.get('parent_project_id'),preferred_provider=req.get('preferred_provider') or get_ai_provider(),provider_policy=req.get('provider_policy') or policy_for_provider(req.get('preferred_provider') or get_ai_provider()),max_api_cost_usd=float(req.get('max_api_cost_usd') or 10.0),runtime_version=build_version())
    finally:ps.close()

def _project_dashboard_read_model(x:dict)->dict:
    project=x.get('project') or {}; analysis=x.get('analysis') or {}; ptype=str(x.get('project_type') or 'research')
    stages=x.get('stages') or []; artifacts=x.get('artifacts') or []
    common={'project_type':ptype,'status':x.get('status'),'current_stage':x.get('current_stage'),'last_completed_stage':x.get('last_completed_stage'),'last_checkpoint':x.get('last_checkpoint'),'progress_done':sum(1 for st in stages if st.get('status') in {'DONE','DONE_WITH_WARNINGS'}),'progress_total':len(stages),'artifact_count':len(artifacts),'waiting':[{'stage':st.get('stage_type'),'status':st.get('status'),'reason':st.get('waiting_reason')} for st in stages if str(st.get('status') or '').startswith('WAITING')],'failed':[{'stage':st.get('stage_type'),'reason':st.get('waiting_reason')} for st in stages if st.get('status')=='FAILED']}
    if ptype!='simulation':
        rp=project.get('research_plan') or {};aud=project.get('audience') or {};qs=rp.get('research_questions') or []
        common.update({'research_question':str((qs[0] if qs else None) or project.get('goal') or ''),'population':aud.get('description') or aud.get('population') or '','executive_answer':analysis.get('executive_answer') or analysis.get('decision_answer') or analysis.get('recommendation') or '','finding_count':len(analysis.get('key_findings') or []),'segment_count':len(analysis.get('segment_story') or [])})
        return common
    sim=project.get('simulation') or project;contract=project.get('scenario_contract') or sim.get('scenario_contract') or {};run=project.get('fullsim_run') or sim.get('fullsim_run') or {}
    worlds=run.get('worlds_executed') or run.get('worlds') or run.get('completed_worlds') or 0
    if isinstance(worlds,(list,dict)):worlds=len(worlds)
    variants=contract.get('variants') or sim.get('variants') or project.get('variants') or []
    comparison=run.get('comparison') or project.get('comparison') or sim.get('comparison') or {}
    common.update({'brief':sim.get('brief') or project.get('goal') or '','decision':sim.get('decision') or project.get('decision_use') or '','baseline':sim.get('baseline') or contract.get('baseline') or '','worlds_executed':int(worlds or 0),'worlds_planned':int(run.get('worlds_planned') or run.get('planned_worlds') or worlds or 0),'variant_count':len(variants) if isinstance(variants,list) else 0,'variants':variants[:12] if isinstance(variants,list) else [],'winner':run.get('winner') or comparison.get('winner') or project.get('winner') or '','recommendation':run.get('recommendation') or comparison.get('recommendation') or analysis.get('recommendation') or '','headline':run.get('headline') or comparison.get('headline') or '','breakpoints':run.get('breakpoints') or comparison.get('breakpoints') or [],'risks':run.get('risks') or comparison.get('risks') or [],'opportunities':run.get('opportunities') or comparison.get('opportunities') or [],'segment_differences':run.get('segment_differences') or comparison.get('segment_differences') or []})
    return common

def project_portfolio_dashboard()->dict:
    rows=project_history(500);real=[x for x in rows if not x.get('is_demo')];demos=[x for x in rows if x.get('is_demo')]
    def cnt(fn):return sum(1 for x in real if fn(x))
    waiting_user=[x for x in real if x.get('status')=='WAITING_USER' or (x.get('job_summary') or {}).get('waiting_user')]
    waiting_ai=[x for x in real if x.get('status') in {'WAITING_CREDITS','WAITING_CAPACITY'} or (x.get('job_summary') or {}).get('waiting_ai')]
    failed=[x for x in real if (x.get('job_summary') or {}).get('failed')];running=[x for x in real if x.get('status')=='IN_PROGRESS' or (x.get('job_summary') or {}).get('running')];ready=[x for x in real if x.get('status') in {'DRAFT','READY_TO_CONTINUE'}];completed=[x for x in real if str(x.get('status') or '').startswith('COMPLETED')];pinned=[x for x in real if x.get('pinned')];recent=sorted(real,key=lambda x:str(x.get('modified_at') or ''),reverse=True)[:8]
    return {'counts':{'all':len(real),'research':cnt(lambda x:x.get('project_type')!='simulation'),'simulation':cnt(lambda x:x.get('project_type')=='simulation'),'running':len(running),'waiting_user':len(waiting_user),'waiting_ai':len(waiting_ai),'failed':len(failed),'ready':len(ready),'completed':len(completed),'archived':cnt(lambda x:bool(x.get('archived'))),'pinned':len(pinned),'demo':len(demos)},'attention':{'waiting_user':waiting_user[:8],'waiting_ai':waiting_ai[:8],'failed':failed[:8],'running':running[:8]},'pinned':pinned[:8],'recent':recent,'demos':demos[:8]}

def project_overview(req:dict)->dict:
    from project_store import ProjectStore
    from demo_showcase import find as find_demo, load as load_demo
    pid=str(req.get('project_id') or '').strip();
    if not pid:raise ValueError('Chybí project_id')
    if find_demo(pid):
        d=load_demo(pid)
        for f in d.get('files') or []:f['download_url']=_file_url(f.get('path'))
        return d
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
    try:
        x=ps.overview(pid)
        if not x:raise FileNotFoundError('Projekt nenalezen')
        for a in x.get('artifacts') or []:
            try:a['download_url']=_file_url(a.get('path')) if a.get('path') else None
            except Exception:a['download_url']=None
        for a in x.get('attachments') or []:
            try:a['download_url']='/project-attachments/'+quote(Path(a.get('stored_path') or '').name)
            except Exception:a['download_url']=None
        try:
            jobs=[j for j in _ros_store().list_jobs(limit=2000) if str(j.get('project_id') or '')==pid]
            x['jobs']=jobs[:80]
            x['job_summary']={'running':sum(j.get('status')=='RUNNING' for j in jobs),'waiting_user':sum(j.get('status')=='WAITING_USER' for j in jobs),'waiting_ai':sum(j.get('status') in {'WAITING_CREDITS','WAITING_CAPACITY','RECOVERY_REQUIRED'} for j in jobs),'failed':sum(j.get('status')=='FAILED' for j in jobs),'queued':sum(j.get('status') in {'READY','QUEUED','RETRYING','WAITING_DEPENDENCY'} for j in jobs)}
        except Exception:x['jobs']=[];x['job_summary']={'running':0,'waiting_user':0,'waiting_ai':0,'failed':0,'queued':0}
        x['dashboard']=_project_dashboard_read_model(x)
        return x
    finally:ps.close()

def _visualization_candidate_paths(project_id:str='',run_id:str='')->list[tuple[Path,str]]:
    """Return only generated/attached respondent files already owned by this app."""
    out=[]
    if run_id:
        p=(ROOT/'runs'/str(run_id)/'detail_internal.csv').resolve()
        if p.is_file():out.append((p,'RUN_DETAIL_INTERNAL'))
    if project_id:
        from demo_showcase import find as find_demo, load as load_demo
        if find_demo(project_id):
            try:
                d=load_demo(project_id)
                for f in d.get('files') or []:
                    raw=f.get('path') or f.get('stored_path')
                    if not raw:continue
                    pp=Path(raw); pp=(pp if pp.is_absolute() else ROOT/pp).resolve()
                    nm=(pp.name+' '+str(f.get('name') or '')).lower()
                    if pp.is_file() and pp.suffix.lower() in {'.csv','.xlsx','.json'} and any(k in nm for k in ('respond','dataset','detail','microdata','sample')):
                        out.append((pp,'DEMO_DATASET'))
            except Exception:pass
        else:
            from project_store import ProjectStore
            ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
            try:
                ov=ps.overview(project_id) or {}
                rows=(ov.get('artifacts') or [])+(ov.get('attachments') or [])
                for a in rows:
                    raw=a.get('path') or a.get('stored_path') or a.get('storage_uri')
                    if not raw:continue
                    pp=Path(str(raw)); pp=(pp if pp.is_absolute() else ROOT/pp).resolve()
                    nm=(pp.name+' '+str(a.get('artifact_type') or '')+' '+str(a.get('filename') or '')).lower()
                    if pp.is_file() and pp.suffix.lower() in {'.csv','.xlsx','.json'} and any(k in nm for k in ('respond','dataset','detail','microdata','sample','fieldwork')):
                        out.append((pp,'PROJECT_ARTIFACT'))
                # Legacy project payloads sometimes carry the generated dataset path directly.
                def walk(x):
                    if isinstance(x,dict):
                        for v in x.values():yield from walk(v)
                    elif isinstance(x,list):
                        for v in x:yield from walk(v)
                    elif isinstance(x,str) and x.lower().endswith(('.csv','.xlsx','.json')):yield x
                for raw in walk(ov.get('project') or {}):
                    pp=Path(raw);pp=(pp if pp.is_absolute() else ROOT/pp).resolve();nm=pp.name.lower()
                    if pp.is_file() and any(k in nm for k in ('respond','dataset','detail','microdata','sample')):out.append((pp,'PROJECT_PAYLOAD'))
            finally:ps.close()
    # unique, deterministic priority
    seen=set();uniq=[]
    for pp,src in out:
        key=str(pp)
        if key not in seen:seen.add(key);uniq.append((pp,src))
    return uniq


def visualization_respondents(req:dict)->dict:
    from visualization_lab import load_respondent_file, respondent_map_payload
    pid=str(req.get('project_id') or '').strip();run_id=str(req.get('run_id') or '').strip()
    candidates=_visualization_candidate_paths(pid,run_id)
    preferred=Path(str(req.get('source_file') or '')).name.strip()
    if preferred:
        candidates=sorted(candidates,key=lambda item:(0 if item[0].name==preferred else 1, str(item[0])))
    if not candidates:
        return {'available':False,'project_id':pid,'run_id':run_id,'reason':'NO_RESPONDENT_DATA',
                'message':'Pro tento projekt není k dispozici respondentní dataset. Visualization Lab nevytváří náhradní syntetické lidi. U LIVE projektu je potřeba dokončený fieldwork/dataset; DEMO dataset bude dodán jako samostatný datový seed.'}
    errors=[]
    for pp,src in candidates:
        try:
            df=load_respondent_file(pp)
            payload=respondent_map_payload(df,rating_columns=req.get('rating_columns') or None,profile_columns=req.get('profile_columns') or None)
            if pid:
                try:
                    from project_store import ProjectStore
                    ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
                    try:payload['saved_layouts']={'respondents':ps.visualization_layout(pid,'respondents'),'objects':ps.visualization_layout(pid,'objects')}
                    finally:ps.close()
                except Exception:payload['saved_layouts']={'respondents':{'positions':{},'view':{}},'objects':{'positions':{},'view':{}}}
            return {'available':True,'project_id':pid,'run_id':run_id,'source':src,'source_file':pp.name,'payload':payload}
        except Exception as exc:errors.append(f'{pp.name}: {exc}')
    return {'available':False,'project_id':pid,'run_id':run_id,'reason':'RESPONDENT_DATA_NOT_MAPPABLE','message':'Respondentní soubor existuje, ale nemá dost společně hodnocených položek pro mapu.','errors':errors[:8]}



def visualization_dialogue(req:dict)->dict:
    """Ask one selected respondent or a selected segment.

    Grounded mode is deterministic and local over the exact respondent rows.
    Simulated mode is explicit/fail-closed and sends only minimized evidence to
    the selected provider, never the raw respondent file.
    """
    from respondent_dialogue import dialogue
    pid=str(req.get('project_id') or '').strip();run_id=str(req.get('run_id') or '').strip()
    if not pid and not run_id:raise ValueError('Chybí project_id nebo run_id')
    candidates=_visualization_candidate_paths(pid,run_id)
    preferred=Path(str(req.get('source_file') or '')).name.strip()
    if preferred:
        candidates=sorted(candidates,key=lambda item:(0 if item[0].name==preferred else 1, str(item[0])))
    if not candidates:raise ValueError('Pro tento projekt není dostupný respondentní dataset.')
    return dialogue(candidate_paths=candidates,question=str(req.get('question') or ''),target_type=str(req.get('target_type') or 'respondent'),
                    respondent_id=str(req.get('respondent_id') or '') or None,respondent_ids=[str(x) for x in (req.get('respondent_ids') or [])],
                    segment_label=str(req.get('segment_label') or 'Vybraný segment'),mode=str(req.get('mode') or 'grounded'),
                    provider=str(req.get('provider') or 'claude_code_subscription'),model=str(req.get('model') or 'sonnet'))


def visualization_object_map(req:dict)->dict:
    """Object mode of the unified Sociomapa.

    LIVE/research projects derive it from respondent ratings.  DEMO projects may
    supply the explicit audited relation matrix in OBJECTS_SOCIOMAP_DEMO.json.
    """
    pid=str(req.get('project_id') or '').strip();run_id=str(req.get('run_id') or '').strip()
    if not pid and not run_id:raise ValueError('Chybí project_id nebo run_id')
    respondent=visualization_respondents({'project_id':pid,'run_id':run_id,'source_file':req.get('source_file') or ''})
    if respondent.get('available') and (respondent.get('payload') or {}).get('object_map',{}).get('names'):
        return {'available':True,'project_id':pid,'source':respondent.get('source'),'source_file':respondent.get('source_file'),
                'object_map':respondent['payload']['object_map'],'saved_layout':(respondent['payload'].get('saved_layouts') or {}).get('objects') or {}}
    if pid:
        try:
            from demo_showcase import find as find_demo
            meta=find_demo(pid)
            if meta:
                base=(ROOT/str(meta.get('relative_path') or '')).resolve()
                fp=base/'OBJECTS_SOCIOMAP_DEMO.json'
                if fp.is_file():
                    raw=json.loads(fp.read_text(encoding='utf-8'))
                    nodes=raw.get('nodes') or [];matrix=raw.get('relation_matrix_1_10') or []
                    if nodes and matrix:
                        names=[str(x.get('name') or f'Objekt {i+1}') for i,x in enumerate(nodes)]
                        classic=[]
                        for i in range(len(names)):
                            row=sum(float(x or 0) for x in matrix[i]) if i<len(matrix) else 0.0
                            col=sum(float(matrix[j][i] or 0) for j in range(len(matrix)) if i<len(matrix[j]))
                            classic.append(row+col)
                        import statistics
                        mu=statistics.fmean(classic) if classic else 50.0;sd=statistics.pstdev(classic) if len(classic)>1 else 0.0
                        norm=[50.0 if sd<1e-9 else 50.0+10.0*(x-mu)/sd for x in classic]
                        om={'names':names,'matrix':matrix,'positions':[], 'scores_classic':classic,'scores_normative':norm,
                            'mean_rating':[float(x.get('score')) if x.get('score') is not None else None for x in nodes],
                            'support_n':[None for _ in nodes], 'pair_p':[], 'pair_n':[], 'pair_r':[],
                            'types':['dot' if str(x.get('type') or '').lower() in {'anchor','secondary','dot'} else 'hill' for x in nodes],
                            'relation_source':raw.get('matrix_source') or 'DEMO_EXPLICIT_RELATION_MATRIX',
                            'matrix_contract':raw.get('matrix_contract') or 'row sends; column receives; diagonal=0; 1..10',
                            'statistics_contract':'Explicit DEMO relation matrix: inferential p-values are not available.'}
                        from project_store import ProjectStore
                        ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
                        try:lay=ps.visualization_layout(pid,'objects')
                        finally:ps.close()
                        return {'available':True,'project_id':pid,'source':'DEMO_RELATION_MATRIX','source_file':fp.name,'object_map':om,'saved_layout':lay}
        except Exception as exc:
            return {'available':False,'project_id':pid,'reason':'OBJECT_MAP_ERROR','message':str(exc)}
    return {'available':False,'project_id':pid,'reason':'NO_OBJECT_MAP','message':'Pro tento projekt není k dispozici relační matice objektů.'}


def visualization_layout_action(req:dict)->dict:
    from project_store import ProjectStore
    pid=str(req.get('project_id') or '').strip();mode=str(req.get('mode') or 'respondents').strip().lower();action=str(req.get('action') or 'save').strip().lower()
    if not pid:raise ValueError('Chybí project_id')
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
    try:
        if action=='get':return {'ok':True,'layout':ps.visualization_layout(pid,mode)}
        if action=='reset':return ps.reset_visualization_layout(pid,mode)
        return {'ok':True,'layout':ps.save_visualization_layout(pid,mode,positions=req.get('positions') or {},view=req.get('view') or {},metadata={'source':'SOCIOMAP_WORKSPACE_18_6_6','manual_visual_override':True})}
    finally:ps.close()

def visualization_segments(req:dict)->dict:
    from project_store import ProjectStore
    pid=str(req.get('project_id') or '').strip()
    if not pid:raise ValueError('Chybí project_id')
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
    try:return {'project_id':pid,'segments':ps.visualization_segments(pid)}
    finally:ps.close()


def visualization_segment_action(req:dict)->dict:
    from project_store import ProjectStore
    pid=str(req.get('project_id') or '').strip();action=str(req.get('action') or 'save').strip().lower()
    if not pid:raise ValueError('Chybí project_id')
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
    try:
        if action=='delete':return ps.delete_visualization_segment(pid,str(req.get('segment_id') or ''))
        return ps.save_visualization_segment(pid,str(req.get('name') or 'Uložený segment'),filter_spec=req.get('filter') or {},respondent_ids=req.get('respondent_ids') or [],color=str(req.get('color') or ''),metadata={'source':'VISUALIZATION_LAB','selection_mode':req.get('selection_mode') or 'filter'})
    finally:ps.close()


def visualization_compare(req:dict)->dict:
    from visualization_lab import compare_area
    payload=visualization_respondents(req)
    if not payload.get('available'):return payload
    return {'available':True,'project_id':payload.get('project_id'),'comparison':compare_area(payload['payload']['points'],[str(x) for x in req.get('area_a') or []],[str(x) for x in req.get('area_b') or []])}

def _demo_segment_intelligence(project_id:str)->dict|None:
    from demo_showcase import find as find_demo
    meta=find_demo(project_id)
    if not meta:return None
    rel=str(meta.get('relative_path') or '')
    base=(ROOT/rel).resolve() if rel else None
    p=(base/'SEGMENT_INTELLIGENCE_DEMO.json') if base else None
    if p and p.is_file():
        try:return json.loads(p.read_text(encoding='utf-8'))
        except Exception:return None
    return None


def visualization_intelligence(req:dict)->dict:
    """Discover interesting groups and optionally interpret aggregates through AI.

    Discovery is immediate and deterministic.  Runtime AI is explicit and cached;
    opening Visualization Lab never creates a paid provider call on its own.
    """
    from visualization_lab import load_respondent_file
    from segment_intelligence import discover_segments, interpret_with_ai, merge_ai
    from demo_showcase import find as find_demo
    pid=str(req.get('project_id') or '').strip(); run_id=str(req.get('run_id') or '').strip()
    if not pid and not run_id:raise ValueError('Chybí project_id nebo run_id')
    candidates=_visualization_candidate_paths(pid,run_id)
    if not candidates:return {'available':False,'reason':'NO_RESPONDENT_DATA','message':'Segment Intelligence potřebuje respondentní dataset.'}
    last=[]; df=None; source_file=''; source=''
    for pp,src in candidates:
        try:
            x=load_respondent_file(pp)
            if len(x) and len(x.columns)>=3:df=x;source_file=pp.name;source=src;break
        except Exception as exc:last.append(f'{pp.name}: {exc}')
    if df is None:return {'available':False,'reason':'RESPONDENT_DATA_NOT_MAPPABLE','errors':last[:6]}
    payload=discover_segments(df,max_candidates=int(req.get('max_candidates') or 12))
    demo_ai=_demo_segment_intelligence(pid) if pid and find_demo(pid) else None
    if demo_ai:
        return {'available':True,'project_id':pid,'source':source,'source_file':source_file,'intelligence':merge_ai(payload,demo_ai),'ai_state':'DEMO_PRECOMPUTED','cached':True}
    cached=None; snap=None
    if pid:
        from project_store import ProjectStore
        ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
        try:
            cached=ps.segment_intelligence(pid);snap=ps.get(pid)
        finally:ps.close()
    if cached and str(cached.get('dataset_fingerprint'))==str(payload.get('dataset_fingerprint')) and not bool(req.get('refresh_ai')):
        ai=cached.get('payload') or {}
        return {'available':True,'project_id':pid,'source':source,'source_file':source_file,'intelligence':merge_ai(payload,ai),'ai_state':'CACHED','cached':True}
    use_ai=bool(req.get('use_ai') or req.get('refresh_ai'))
    if not use_ai:
        return {'available':True,'project_id':pid,'source':source,'source_file':source_file,'intelligence':payload,'ai_state':'NOT_RUN','cached':False,
                'ai_message':'Datové skupiny jsou připravené. AI interpretaci lze spustit explicitně; otevření mapy samo o sobě nevolá placené API.'}
    provider=str(req.get('provider') or (snap or {}).get('preferred_provider') or get_ai_provider())
    model=req.get('model') or ((snap or {}).get('project') or {}).get('model')
    ai=interpret_with_ai(payload,provider=provider,model=model)
    if pid:
        from project_store import ProjectStore
        ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
        try:ps.save_segment_intelligence(pid,payload['dataset_fingerprint'],ai,provider=str(ai.get('provider') or provider),model=str(ai.get('model') or model or ''),status='AI_READY',metadata={'privacy':'AGGREGATES_ONLY','source_file':source_file})
        finally:ps.close()
    return {'available':True,'project_id':pid,'source':source,'source_file':source_file,'intelligence':merge_ai(payload,ai),'ai_state':'AI_READY','cached':False}


def project_impact(req:dict)->dict:
    from project_store import ProjectStore
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
    try:return ps.impact_preview(str(req.get('project_id') or ''),list(req.get('changed_fields') or []),req.get('stage_type'))
    finally:ps.close()

def project_continue_claude_api(req:dict)->dict:
    """Explicit paid continuation. Completed artifacts are never requeued."""
    from project_store import ProjectStore
    pid=str(req.get('project_id') or '').strip();
    if not pid:raise ValueError('Chybí project_id')
    if not provider_key_ready('anthropic'):raise ValueError('Claude API není připravené. Vložte ANTHROPIC_API_KEY a otestujte připojení.')
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite'); st=_ros_store()
    try:
        snap=ps.get(pid);
        if not snap:raise FileNotFoundError('Projekt nenalezen')
        ps.set_provider_policy(pid,preferred_provider='anthropic',provider_policy='CLAUDE_CODE_THEN_API',max_api_cost_usd=float(req.get('max_api_cost_usd') or snap.get('max_api_cost_usd') or 10.0),explicit=True,reason='explicit_continue_with_claude_api')
        rev=int(snap['revision']);stage=str(req.get('stage_type') or snap.get('current_stage') or '')
        changed=[]
        with st.cx() as c:
            rows=c.execute("SELECT job_id,input_json,status FROM jobs WHERE project_id=? AND project_revision=? AND status IN ('WAITING_CREDITS','WAITING_CAPACITY','PAUSED','READY','QUEUED') ORDER BY created_at",(pid,rev)).fetchall()
            for r in rows:
                inp=json.loads(r['input_json'] or '{}'); inp.setdefault('phase_policy',{})['provider']='anthropic';inp.setdefault('approval_decisions',[]).append({'option':'continue_with_claude_api','provider':'anthropic','explicit_user_action':True})
                c.execute("UPDATE jobs SET provider_policy='anthropic',input_json=?,status=CASE WHEN status IN ('WAITING_CREDITS','WAITING_CAPACITY','PAUSED') THEN 'QUEUED' ELSE status END,attempt=0,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE job_id=?",(json.dumps(inp,ensure_ascii=False,default=str),time.strftime('%Y-%m-%dT%H:%M:%S'),r['job_id']));changed.append(r['job_id'])
        ps.record_provider_event(pid,revision=rev,stage_type=stage,from_provider='claude_code_subscription',to_provider='anthropic',reason='explicit_continue_with_claude_api',explicit_user_action=True,metadata={'requeued_jobs':changed})
        for jid in changed:
            j=st.get_job(jid);st.event(jid,'PROVIDER_CHANGED','User explicitly continued missing work with Claude API.',{'provider':'anthropic','project_id':pid},'WARN');st.refresh_workflow(j['workflow_id'])
        st.queue_ready_jobs();return {'ok':True,'project_id':pid,'revision':rev,'provider':'anthropic','provider_label':'Claude API','requeued_jobs':changed,'reused_completed_artifacts':True}
    finally:ps.close()

def project_settings_update(req:dict)->dict:
    from project_store import ProjectStore
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
    try:return ps.set_provider_policy(str(req.get('project_id') or ''),preferred_provider=req.get('preferred_provider'),provider_policy=req.get('provider_policy'),max_api_cost_usd=req.get('max_api_cost_usd'),explicit=True,reason='project_settings')
    finally:ps.close()

def project_memory_search(req:dict)->dict:
    from project_memory import search
    return search(str(req.get('query') or ''),db_path=ROOT/'data'/'project_store.sqlite',current_project_id=str(req.get('project_id') or '') or None,current_revision=(int(req.get('project_revision')) if req.get('project_revision') not in (None,'') else None),current_project=req.get('project') or {},limit=int(req.get('limit') or 14),kinds=req.get('kinds'))

def demo_copy_project(req:dict)->dict:
    from demo_showcase import editable_project, find as find_demo, load as load_demo
    from project_store import ProjectStore
    pid=str(req.get('project_id') or '')
    meta=find_demo(pid)
    if not meta:raise FileNotFoundError('DEMO projekt nenalezen')
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
    try:
        if str(meta.get('project_type') or 'research')=='simulation':
            d=load_demo(pid); a=d.get('assignment') or {}; aud=d.get('audience') or {}
            title=str(d.get('title') or 'DEMO simulace').replace(' — navazující simulace','')+' — kopie simulace'
            project={'schema_version':'simulation-project-v1','title':title,'simulation':{
                'title':title,'brief':str(a.get('client_need') or d.get('title') or ''),
                'baseline':str((d.get('project') or {}).get('baseline') or a.get('client_need') or ''),
                'decision':str(a.get('primary_decision') or ''),'audience':aud,
                'source_research_project_id':meta.get('source_research_project_id'),'demo_source':pid}}
            return ps.create_project(project_type='simulation',title=title,project=project,preferred_provider=req.get('preferred_provider') or get_ai_provider(),provider_policy=policy_for_provider(req.get('preferred_provider') or get_ai_provider()),max_api_cost_usd=10.0,runtime_version=build_version())
        project=editable_project(pid)
        return ps.create_project(project_type='research',title=project.get('title'),project=project,preferred_provider=req.get('preferred_provider') or get_ai_provider(),provider_policy=policy_for_provider(req.get('preferred_provider') or get_ai_provider()),max_api_cost_usd=10.0,runtime_version=build_version())
    finally:ps.close()

def demo_catalog_public()->list[dict]:
    from demo_showcase import project_catalog
    return project_catalog()

def project_history_action(req:dict)->dict:
    from project_store import ProjectStore
    from demo_showcase import find as find_demo
    ps=ProjectStore(ROOT/'data'/'project_store.sqlite');pid=str(req.get('project_id') or '')
    try:
        if find_demo(pid):raise ValueError('DEMO seed je read-only. Nejprve vytvořte editovatelnou kopii.')
        action=str(req.get('action') or '')
        if action=='branch':return ps.branch(pid,int(req.get('revision')),str(req.get('name') or 'Větev'))
        if action=='restore':return ps.restore_as_new_revision(pid,int(req.get('revision')))
        if action=='archive':ps.archive(pid,True);return {'ok':True,'archived':True}
        if action=='unarchive':ps.archive(pid,False);return {'ok':True,'archived':False}
        if action=='pin':return {'ok':True,**ps.set_pinned(pid,True)}
        if action=='unpin':return {'ok':True,**ps.set_pinned(pid,False)}
        if action=='tags':return {'ok':True,**ps.set_tags(pid,list(req.get('tags') or []))}
        if action=='duplicate':return {'ok':True,**ps.duplicate(pid,req.get('name'))}
        if action=='trash':return {'ok':True,**ps.move_to_trash(pid)}
        if action=='restore-trash':return {'ok':True,**ps.restore_from_trash(pid)}
        raise ValueError('Neznámá project history action')
    finally:ps.close()

def project_export(req:dict)->dict:
    from project_store import ProjectStore
    pid=str(req.get('project_id') or '');ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
    try:
        path=ps.export_zip(pid,OUT/'project_exports'/f'{pid}_PROJECT_EXPORT.zip');return {'ok':True,'path':str(path),'download_url':_file_url(path)}
    finally:ps.close()

def history(limit=100):
    from run_store import RunStore
    rs=RunStore(ROOT/"data"/"run_store.sqlite")
    try:return rs.list_runs(limit)
    finally:rs.close()


def bootstrap()->dict:
    panel=core.load_panel_cached(); val=load_validation_evidence(); joint=load_joint_status()
    from pipeline import resolve_panel_metadata
    pm=resolve_panel_metadata(core.PANEL_PATH)
    model_cards=[]
    model_help={
        "haiku":{"role":"Rychlý","pros":"Nejnižší náklady a rychlé iterace.","cons":"Méně nuance u složitých otevřených a kontextových otázek.","recommended_for":"technické a časné iterace"},
        "sonnet":{"role":"Doporučený","pros":"Nejlepší praktický poměr kvality, stability a ceny.","cons":"Dražší než Haiku.","recommended_for":"většinu finálních výzkumů"},
        "opus":{"role":"Nejvyšší kvalita","pros":"Největší kapacita pro složité kontexty a otevřené odpovědi.","cons":"Nejdražší a pomalejší; neřeší chyby datového jádra.","recommended_for":"náročné finální projekty"},
    }
    for alias,m in MODELS.items(): model_cards.append({"alias":alias,"id":m.model_id,"label":m.label,**model_help.get(alias,{})})
    from persona_calibration import calibration_status
    cal_status=calibration_status()
    persona_cards=[
        {"id":"calibrated","name":"Benchmarkově kalibrovaná persona","status":"DOPORUČENÝ DEFAULT","summary":"Human CALIBRATION benchmark před každou otázkou vybere recept demographics/core/full podle domény; bez aktivního profilu bezpečně padá na core.","pros":["benchmark přímo mění konstrukci persony","doménově adaptivní","blind holdout se do učení nesmí dostat"],"cons":["vyžaduje dost CALIBRATION otázek","bez benchmarku je efektivně core"],"recommended_for":"ostrý výzkum po nahrání lidských kalibračních benchmarků"},
        {"id":"demographics","name":"Jednoduchý profil","status":"BASELINE","summary":"Jen pevné sociodemografické údaje.","pros":["nejtransparentnější","nejméně syntetických předpokladů","dobrá validační baseline"],"cons":["málo behaviorální hloubky","lidé stejné demografie jsou si podobnější"],"recommended_for":"konzervativní odhad, sanity check a ablace"},
        {"id":"core","name":"Integrovaná datová persona v17","status":"DATOVÉ JÁDRO / ABLACE","summary":"Koherentní core s jedním skutečným PIAAC/ISSP donorem; whole-donor bloky politiky, zdraví, vztahů a institucí; navíc topic-relevant marketing/media/life, hodnotové proxy, náboženství a finanční capability s explicitní provenance a confidence.","pros":["soudržná socioekonomika","měřená BFI-2 osobnost pro working-age","žádné nezávislé losování 75 dimenzí","každý matched blok je označen"],"cons":["cross-survey vazba mezi bloky je statistický matching, ne totéž jako jeden člověk v jednom omnibusu","u malých profesních subpanelů je omezený donor support"],"recommended_for":"většinu produktových, společenských a populačních výzkumů"},
        {"id":"full","name":"Rozšířená diagnostická persona","status":"EXPERIMENTÁLNÍ","summary":"Koherentní v17 core plus legacy experimentální vrstvy, pokud jsou v panelu přítomné.","pros":["vhodné pro sensitivity analysis a ablace"],"cons":["legacy latentní vrstvy nejsou součástí v17 produkčního datového jádra","není automaticky pravdivější než core"],"recommended_for":"diagnostiku a ablace"},
        {"id":"none","name":"Generic AI baseline","status":"VALIDAČNÍ BASELINE","summary":"Model bez persony.","pros":["ukáže, kolik přidává samotný panel","nejjednodušší benchmark"],"cons":["nereprezentuje heterogenitu populace"],"recommended_for":"ablace a metodickou kontrolu"},
    ]
    selected_provider=get_ai_provider()
    from edition_config import build_version, load_edition
    edition=load_edition()
    return {"release":RELEASE,"edition":edition,"worker_ready":_worker_ready()[0],"validation_tier":validation_tier(),"validation":val,"joint_core":joint,
            "ai_provider":selected_provider,"ai_provider_label":({"anthropic":"Claude API","openai":"OpenAI API","claude_code_subscription":"Claude Code"}.get(selected_provider,selected_provider)),"live_providers":[{"id":"claude_code_subscription","label":"Claude Code"},{"id":"anthropic","label":"Claude API"},{"id":"openai","label":"OpenAI API"}],"default_model":resolve_provider_model(selected_provider,DEFAULT_MODEL),"models":model_cards,"persona_modes":persona_cards,
            "cost_modes":{"ECONOMY":{"label":"Rychle a levně","default_budget_usd":1.0},"STANDARD":{"label":"Střední cesta","default_budget_usd":3.0},"REFERENCE":{"label":"Excelent","default_budget_usd":10.0}},
            "has_anthropic_key":has_anthropic_key(),"has_openai_key":has_openai_key(),"has_ai_key":bool(has_anthropic_key() or has_openai_key() or provider_key_ready('claude_code_subscription')),"ai_provider_ready":provider_key_ready(selected_provider),"anthropic_key_info":anthropic_key_info(),"openai_key_info":openai_key_info(),
            "panel":{"rows":len(panel),"columns":len(panel.columns),"version":pm.get("panel_version"),"path":str(core.PANEL_PATH),"target_hash":pm.get("target_hash","")},
            "persona_profile":{"version":"v17-coherent-core+matched-blocks+calibrated-background","strategy":"coherent core facts + topic-relevant measured/matched signals","registry":"PERSONA_SIGNAL_CATALOG_v17.csv","provenance_registry":"DATA_PROVENANCE_REGISTRY_v17.csv","legacy_overlay_registry":"PERSONA_PROFILE_REGISTRY_v1.json","population_core_changed":True,"calibration":cal_status},
            "full_simulation":{"version":"full-simulation-lab-v17-scenario-contract","status":"EXPERIMENTAL_FORECASTING_WITH_HUMAN_RECTIFICATION","max_worlds":50,"default_worlds":12,"user_modes":["CORE","SIM","HYBRID"],"blind_objective":"blind_forecast","scenario_objective":"scenario_nowcast"},
            "audiences":list_audiences(),
            "population_subpanels":list_subpanels(),
            "special_panels":list_special_panels(),
            "audience_source_modes":["population","customer","special_audience"],
            "instrument_library":{"version":library_version(),"study_types":instrument_study_types()},
            "typology_reference":load_typology_reference(),
            "data_library":__import__("data_library").summary(),
            "population_registry":__import__("population_context").summary(),
            "empty_project":empty_project(),"panel_values":allowed_values(panel)}



def _ros_store():
    from job_store import JobStore
    return JobStore(ROOT/"data"/"research_os.sqlite")

def _worker_ready(max_age_s:float=35.0)->tuple[bool,list[dict]]:
    from job_store import now
    s=_ros_store();workers=s.workers();fresh=[]
    for w in workers:
        try:
            ts=time.mktime(time.strptime(str(w.get("heartbeat_at") or "")[:19],"%Y-%m-%dT%H:%M:%S"))
            if time.time()-ts<=max_age_s and w.get("status") in {"READY","BUSY"}:fresh.append(w)
        except Exception: pass
    return bool(fresh),fresh

def create_research_workflow(req:dict)->dict:
    from project_store import ProjectStore
    from workflow_engine import create_standard
    project=req.get("project") or None;pid=str(req.get("project_id") or "").strip();rev=req.get("project_revision")
    ps=ProjectStore(ROOT/"data"/"project_store.sqlite")
    try:
        if project is not None:
            saved=ps.save(project,project_id=pid or None,analysis=req.get("analysis") or {},panel_version="v"+build_version(),reason="workflow_enqueue")
            pid=saved["project_id"];rev=saved["revision"];project=ps.get(pid,rev)["project"]
        else:
            if not pid: raise ValueError("Chybí project_id nebo project.")
            snap=ps.get(pid,int(rev) if rev not in (None,"") else None)
            if not snap: raise FileNotFoundError("Projekt/revize nenalezena.")
            rev=snap["revision"];project=snap["project"]
    finally: ps.close()
    mode=str(req.get("mode") or "dry");confirm=bool(req.get("confirm_live"))
    cost_mode=str(req.get("cost_mode") or (project.get("run_policy") or {}).get("cost_mode") or "REFERENCE").upper()
    budget=req.get("budget_usd")
    if budget in (None,""): budget=(project.get("budget") or {}).get("max_usd")
    out=create_standard(_ros_store(),project_id=pid,project_revision=int(rev),project=project,mode=mode,confirm_live=confirm,cost_mode=cost_mode,budget_usd=(float(budget) if budget not in (None,"") else None),priority=int(req.get("priority") or 50),verification=bool(req.get("verification")),after_workflow=req.get("after_workflow") or None,idempotency_key=req.get("idempotency_key") or None)
    return out

def _publicize_workflow_paths(value):
    """Convert generated artifact paths inside workflow JSON to browser-safe /files URLs."""
    if isinstance(value,dict):
        return {k:_publicize_workflow_paths(v) for k,v in value.items()}
    if isinstance(value,list):
        return [_publicize_workflow_paths(v) for v in value]
    if isinstance(value,str):
        raw=value.strip()
        if raw.startswith(("/files/","http://","https://")):
            return value
        try:
            pp=Path(raw)
            suffix=pp.suffix.lower()
            if pp.is_absolute() and suffix in {".csv",".xlsx",".xls",".json",".html",".docx",".pptx",".zip",".pdf",".png",".jpg",".jpeg",".txt"}:
                return _file_url(pp)
        except Exception:
            pass
    return value

def _workflow_public(wid:str)->dict:
    s=_ros_store();w=s.get_workflow(wid)
    if not w: raise FileNotFoundError("Workflow nenalezen.")
    # Enrich workflow with truthful runtime state. Jobs are stored alphabetically,
    # so choosing the first READY item can mislabel a RUNNING research job as a
    # later phase (historically 1/10 was shown as "Statistické výsledky").
    jobs=w.get('jobs') or []
    def _age(ts):
        if not ts:return None
        try:return max(0,int(time.time()-time.mktime(time.strptime(str(ts)[:19],'%Y-%m-%dT%H:%M:%S'))))
        except Exception:return None
    with s.cx() as c:
        for j in jobs:
            ev=c.execute("SELECT message,payload_json,ts FROM job_events WHERE job_id=? AND event_type='PROGRESS' ORDER BY event_id DESC LIMIT 1",(j.get('job_id'),)).fetchone()
            if ev:
                try:payload=json.loads(ev['payload_json'] or '{}')
                except Exception:payload={}
                j['latest_progress']={**payload,'message':ev['message'],'ts':ev['ts']}
            j['heartbeat_age_seconds']=_age(j.get('heartbeat_at'))
            j['elapsed_seconds']=None
            if j.get('started_at'):
                try:j['elapsed_seconds']=max(0,int(time.time()-time.mktime(time.strptime(str(j['started_at'])[:19],'%Y-%m-%dT%H:%M:%S'))))
                except Exception:pass
    rank={'RUNNING':0,'WAITING_USER':1,'WAITING_CAPACITY':2,'WAITING_CREDITS':3,'RECOVERY_REQUIRED':4,'RETRYING':5,'QUEUED':6,'READY':7,'WAITING_DEPENDENCY':8,'PAUSED':9}
    active=sorted((j for j in jobs if j.get('status') in rank),key=lambda j:(rank.get(j.get('status'),99),str(j.get('started_at') or '9999'),str(j.get('created_at') or '')))
    current=active[0] if active else None
    done=sum(1 for j in jobs if j.get('status')=='COMPLETED');total=len(jobs) or 1
    w['current_job']=current
    w['current_step']=current.get('node_key') if current else None
    w['completed_jobs']=done;w['total_jobs']=len(jobs);w['progress_pct']=round(100*done/total)
    return _publicize_workflow_paths(w)

PAGE=(ROOT/"ui_app.html").read_text(encoding="utf-8")

class Handler(BaseHTTPRequestHandler):
    server_version="NPCPanelResearchOS/"+build_version()
    def _allowed_origin(self):
        origin=(self.headers.get("Origin") or "").strip()
        if not origin:return None
        try:
            u=urlparse(origin);host=(u.hostname or "").lower();port=u.port or (443 if u.scheme=="https" else 80)
            actual=int(self.server.server_address[1])
            if u.scheme=="http" and host in {"127.0.0.1","localhost"} and port==actual:return origin
        except Exception:pass
        return False
    def _guard_origin(self):
        allowed=self._allowed_origin()
        if allowed is False:
            self._json(403,{"error":"Cross-origin request blocked. NPC backend přijímá změny pouze ze svého lokálního UI."},cors=False)
            return False
        return True
    def _json(self,code,obj,cors=True):
        data=json.dumps(obj,ensure_ascii=False,default=str).encode();self.send_response(code);self.send_header("Content-Type","application/json; charset=utf-8")
        if cors:
            allowed=self._allowed_origin()
            if isinstance(allowed,str):self.send_header("Access-Control-Allow-Origin",allowed);self.send_header("Vary","Origin")
        self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
    def _body(self):
        n=int(self.headers.get("Content-Length","0"));return json.loads(self.rfile.read(n) or b"{}")
    def do_OPTIONS(self):
        if not self._guard_origin():return
        allowed=self._allowed_origin();self.send_response(204)
        if isinstance(allowed,str):self.send_header("Access-Control-Allow-Origin",allowed);self.send_header("Vary","Origin")
        self.send_header("Access-Control-Allow-Methods","GET,POST,PATCH,DELETE,OPTIONS");self.send_header("Access-Control-Allow-Headers","Content-Type");self.send_header("Access-Control-Max-Age","600");self.end_headers()
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/":
            data=PAGE.encode();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0");self.send_header("Pragma","no-cache");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
        if path.startswith("/brand/"):
            name=Path(unquote(path[len("/brand/"):])).name;p=(ROOT/"brand"/name).resolve();base=(ROOT/"brand").resolve()
            if (base!=p and base not in p.parents) or not p.is_file():self._json(404,{"error":"brand asset not found"});return
            ext=p.suffix.lower();ct={".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".svg":"image/svg+xml",".webp":"image/webp"}.get(ext,"application/octet-stream")
            data=p.read_bytes();self.send_response(200);self.send_header("Content-Type",ct);self.send_header("Cache-Control","public, max-age=86400");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
        if path.startswith("/project-attachments/"):
            name=Path(unquote(path[len("/project-attachments/"):])).name;p=(PROJECT_ATTACHMENTS/name).resolve();base=PROJECT_ATTACHMENTS.resolve()
            if (base!=p and base not in p.parents) or not p.is_file():self._json(404,{"error":"attachment not found"});return
            data=p.read_bytes();self.send_response(200);self.send_header("Content-Type","application/octet-stream");self.send_header("Content-Length",str(len(data)));self.send_header("Content-Disposition",f'attachment; filename="{name.split("_",1)[-1]}"');self.end_headers();self.wfile.write(data);return
        if path=="/health":
            ready,workers=_worker_ready();self._json(200,{"status":"ok","release":RELEASE,"worker_ready":ready,"workers":workers});return
        if path=="/api/bootstrap":
            try:self._json(200,bootstrap())
            except Exception as exc:
                (ROOT/"logs").mkdir(exist_ok=True)
                with (ROOT/"logs"/"backend_errors.log").open("a",encoding="utf-8") as f:f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] /api/bootstrap\n{traceback.format_exc()}\n")
                self._json(500,{"error":"Backend bootstrap selhal.","detail":str(exc),"log":"logs/backend_errors.log"})
            return
        if path=="/api/support/download":
            q=parse_qs(urlparse(self.path).query);name=Path((q.get("name") or [""])[0]).name
            base=(ROOT/"diagnostics").resolve();p=(base/name).resolve()
            if (base!=p and base not in p.parents) or not p.is_file() or p.suffix.lower()!=".zip":self._json(404,{"error":"diagnostický ZIP nebyl nalezen"});return
            data=p.read_bytes();self.send_response(200);self.send_header("Content-Type","application/zip");self.send_header("Content-Length",str(len(data)));self.send_header("Content-Disposition",f'attachment; filename="{p.name}"');self.end_headers();self.wfile.write(data);return
        if path=="/api/command-center":
            from workflow_engine import command_center
            self._json(200,command_center(_ros_store()));return
        if path.startswith("/api/workflows/"):
            wid=path.split("/",3)[3];self._json(200,_workflow_public(wid));return
        if path=="/api/jobs":
            q=parse_qs(urlparse(self.path).query);sts=[x for x in ",".join(q.get("status",[])).split(",") if x]
            self._json(200,_ros_store().list_jobs(sts or None));return
        if path.startswith("/api/jobs/") and path.count("/")==3:
            jid=path.rsplit("/",1)[1];j=_ros_store().get_job(jid);self._json(200,j) if j else self._json(404,{"error":"unknown job"});return
        if path=="/api/jobs/updates":
            q=parse_qs(urlparse(self.path).query);self._json(200,{"events":_ros_store().updates(int((q.get("since_event_id") or [0])[0]))});return
        if path=="/api/approvals/pending":self._json(200,_ros_store().pending_approvals());return
        if path=="/api/schedules":
            from scheduler import Scheduler
            self._json(200,Scheduler(_ros_store(),ROOT/"data"/"project_store.sqlite").list());return
        if path=="/api/providers/claude-code/status":
            from edition_config import claude_code_enabled
            if not claude_code_enabled(): self._json(200,{"ok":False,"provider":"claude_code_subscription","kind":"DISABLED_IN_EDITION","message":"Claude Code není v této edici povolen."});return
            from claude_code_provider import health
            self._json(200,health());return
        if path=="/api/providers/parity/status":
            from provider_parity import load_status
            self._json(200,load_status());return
        if path=="/api/panel_values":self._json(200,allowed_values(core.load_panel_cached()));return
        if path=="/api/audience/dimensions":
            from audience_dimensions import catalog
            self._json(200,catalog(core.load_panel_cached(),include_research_only=True));return
        if path=="/api/history":self._json(200,history());return
        if path=="/api/library":
            from data_library import list_entries,list_proposals,summary
            self._json(200,{"summary":summary(),"entries":list_entries(),"proposals":list_proposals()});return
        if path=="/api/library/dimensions":
            from data_library import active_dimensions
            self._json(200,active_dimensions());return
        if path=="/api/library/system-catalog":
            from library_system_catalog import catalog
            self._json(200,catalog());return
        if path=="/api/populations":
            from population_context import summary
            self._json(200,summary());return
        if path=="/api/results-registry":
            from results_registry import list_results,summary
            q=parse_qs(urlparse(self.path).query);sync=str((q.get('sync') or ['0'])[0]).lower() in {'1','true','yes'}
            self._json(200,{"summary":summary(sync=sync),"results":list_results()});return
        if path=="/api/library/project-sources":
            from data_library import project_sources
            q=parse_qs(urlparse(self.path).query);pid=(q.get('project_id') or [''])[0]
            self._json(200,{"project_id":pid,"sources":project_sources(pid)});return
        if path=="/api/audiences":self._json(200,list_audiences());return
        if path=="/api/audiences/template":
            p=ROOT/"NPC_OWN_AUDIENCE_TEMPLATE_v17_6_0.xlsx"
            if not p.is_file(): self._json(404,{"error":"template missing"});return
            data=p.read_bytes();self.send_response(200);self.send_header("Content-Type","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");self.send_header("Content-Length",str(len(data)));self.send_header("Content-Disposition",'attachment; filename="NPC_OWN_AUDIENCE_TEMPLATE_v17_6_0.xlsx"');self.end_headers();self.wfile.write(data);return
        if path=="/api/questionnaire/template":
            p=ROOT/"NPC_QUESTIONNAIRE_TEMPLATE_v17_6_0.xlsx"
            if not p.is_file(): self._json(404,{"error":"questionnaire template missing"});return
            data=p.read_bytes();self.send_response(200);self.send_header("Content-Type","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");self.send_header("Content-Length",str(len(data)));self.send_header("Content-Disposition",'attachment; filename="NPC_QUESTIONNAIRE_TEMPLATE_v17_6_0.xlsx"');self.end_headers();self.wfile.write(data);return
        if path=="/api/instruments":
            from instrument_library import load_library
            self._json(200,load_library());return
        if path=="/api/scenario/truth":
            from scenario_truth_log import list_entries
            self._json(200,list_entries());return
        if path=="/api/projects":self._json(200,project_history());return
        if path=="/api/projects/trash":
            from project_store import ProjectStore
            ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
            try:self._json(200,ps.trash())
            finally:ps.close()
            return
        if path=="/api/library/society/brief":
            from society_insights import generate_brief
            query=parse_qs(urlparse(self.path).query)
            mode=(query.get('population_mode') or ['LIVE'])[0]
            force=str((query.get('force') or ['0'])[0]).lower() in {'1','true','yes'}
            self._json(200,{'brief':generate_brief(mode,force)});return
        if path=="/api/projects/dashboard":self._json(200,project_portfolio_dashboard());return
        if path.startswith("/api/visualization/segments/"):
            pid=unquote(path.split("/",4)[4]);self._json(200,visualization_segments({"project_id":pid}));return
        if path=="/api/demos":self._json(200,demo_catalog_public());return
        if path.startswith("/api/projects/") and path.endswith("/overview"):
            pid=path.split("/")[3];self._json(200,project_overview({'project_id':pid}));return
        if path=="/api/validation":self._json(200,{"validation_tier":validation_tier(),"validation":load_validation_evidence(),"joint_core":load_joint_status()});return
        if path=="/api/persona/calibration/status":
            from persona_calibration import calibration_status
            self._json(200,calibration_status());return
        if path=="/api/fullsim/runs":
            from full_simulation import list_runs
            self._json(200,list_runs());return
        if path=="/api/fullsim/leaderboard":
            from full_simulation import leaderboard
            self._json(200,leaderboard());return
        if path=="/api/fullsim/arena":
            from research_arena import arena_data
            from full_simulation import BENCH_ROOT
            self._json(200,arena_data(BENCH_ROOT));return
        if path=="/fullsim-arena":
            from research_arena import write_arena_html
            from full_simulation import BENCH_ROOT
            out=write_arena_html(BENCH_ROOT,BENCH_ROOT/"RESEARCH_ARENA.html")
            data=out.read_bytes();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
        if path=="/api/job":
            jid=(parse_qs(urlparse(self.path).query).get("id") or [""])[0]
            if jid.startswith("WF-"):
                w=_ros_store().get_workflow(jid)
                if not w:self._json(404,{"error":"unknown workflow"});return
                run=next((x for x in w["jobs"] if x["node_key"]=="run"),None);state={"QUEUED":"running","READY":"running","RUNNING":"running","WAITING_DEPENDENCY":"running","WAITING_USER":"waiting_user","WAITING_CAPACITY":"paused","WAITING_CREDITS":"paused","PAUSED":"paused","RETRYING":"running","RECOVERY_REQUIRED":"error","COMPLETED":"done","FAILED":"error","CANCELLED":"cancelled"}.get(w["status"],"running")
                obj={"state":state,"workflow_id":jid,"phase":next((x["node_key"] for x in w["jobs"] if x["status"] in {"RUNNING","QUEUED","WAITING_USER","WAITING_CAPACITY","WAITING_CREDITS","PAUSED","RETRYING"}),w["status"]),"result":(run or {}).get("output",{}).get("result") if state=="done" else None}
                self._json(200,obj);return
            # 17.2 durable compatibility jobs return the old poll contract.
            pj=_ros_store().get_job(jid) if jid.startswith("JOB-") else None
            if pj:
                state={"READY":"running","QUEUED":"running","RUNNING":"running","WAITING_DEPENDENCY":"running","RETRYING":"running","WAITING_USER":"waiting_user","WAITING_CAPACITY":"paused","WAITING_CREDITS":"paused","PAUSED":"paused","RECOVERY_REQUIRED":"error","COMPLETED":"done","FAILED":"error","CANCELLED":"cancelled"}.get(pj["status"],"running")
                phase=pj.get("node_key") or pj["status"]
                try:
                    evs=_ros_store().updates(0,5000)
                    last=next((e for e in reversed(evs) if e.get("job_id")==jid and e.get("event_type")=="PROGRESS"),None)
                    _last_progress_payload={}
                    if last:
                        _last_progress_payload=(last.get("payload") or {})
                        phase=_last_progress_payload.get("phase") or last.get("message") or phase
                except Exception:
                    _last_progress_payload={}
                result=(pj.get("output") or {}).get("result") if state=="done" else ((pj.get("error") or {}) if state=="error" else None)
                if state=="done": result=_publicize_workflow_paths(result)
                # Unified AI telemetry: show honest elapsed/heartbeat/ETA-range instead
                # of an endless spinner or invented token counts. Claude subscription
                # does not expose token usage here, so the UI explicitly says so.
                try:
                    from ai_runtime import action_profile
                    _inp=pj.get("input") or {}
                    _legacy=str(_inp.get("legacy_kind") or pj.get("kind") or "")
                    _prof=action_profile(_legacy)
                    def _age(ts):
                        if not ts:return None
                        try:return max(0,int(time.time()-time.mktime(time.strptime(str(ts)[:19],"%Y-%m-%dT%H:%M:%S"))))
                        except Exception:return None
                    _elapsed=None
                    if pj.get("started_at"):
                        try:_elapsed=max(0,int(time.time()-time.mktime(time.strptime(str(pj.get("started_at"))[:19],"%Y-%m-%dT%H:%M:%S"))))
                        except Exception:pass
                    _provider=str((_inp.get("payload") or {}).get("provider") or (((_inp.get("payload") or {}).get("project") or {}).get("run_policy") or {}).get("provider") or pj.get("provider_policy") or "")
                    _model=str((_inp.get("payload") or {}).get("model") or ((_inp.get("payload") or {}).get("spec") or {}).get("model") or pj.get("model") or "")
                    telemetry={"action":_prof.get("label"),"usual_seconds":_prof.get("usual_seconds"),"hard_seconds":_prof.get("hard_seconds"),
                               "research":bool(_prof.get("research")),"elapsed_seconds":_elapsed,"heartbeat_age_seconds":_age(pj.get("heartbeat_at")),
                               "provider":_provider,"model":_model,"estimated_cost_usd":pj.get("estimated_cost_usd"),"actual_cost_usd":pj.get("actual_cost_usd")}
                    for _k in ("provider_stage","provider_wait_seconds","provider_silence_seconds","provider_elapsed_seconds","retry_delay_ms","provider_error","tok_in","tok_out"):
                        if _last_progress_payload.get(_k) is not None: telemetry[_k]=_last_progress_payload.get(_k)
                except Exception:
                    telemetry={}
                self._json(200,{"state":state,"job_id":jid,"workflow_id":pj.get("workflow_id"),"phase":phase,"result":result,"telemetry":telemetry});return
            self._json(404,{"error":"unknown job"});return
        if path.startswith("/files/"):
            rel=unquote(path[len("/files/"):]);p=(OUT/rel).resolve()
            if (OUT.resolve()!=p and OUT.resolve() not in p.parents) or not p.is_file():self._json(404,{"error":"not found"});return
            ext=p.suffix.lower();ct={".xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",".csv":"text/csv; charset=utf-8",".docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",".pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation",".zip":"application/zip",".html":"text/html; charset=utf-8",".json":"application/json; charset=utf-8"}.get(ext,"application/octet-stream")
            data=p.read_bytes();self.send_response(200);self.send_header("Content-Type",ct);self.send_header("Content-Length",str(len(data)));self.send_header("Content-Disposition",("inline" if ext==".html" else "attachment")+f'; filename="{p.name}"');self.end_headers();self.wfile.write(data);return
        if path.startswith("/artifacts/"):
            rel=unquote(path[len("/artifacts/"):]);p=(ROOT/rel).resolve()
            try:_rel=p.relative_to(ROOT.resolve());_top=_rel.parts[0] if _rel.parts else ''
            except Exception:self._json(404,{"error":"not found"});return
            if _top not in {"full_simulation_runs","full_simulation_batches","full_simulation_benchmarks","demo_library"} or not p.is_file():self._json(404,{"error":"not found"});return
            ext=p.suffix.lower();ct={".xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",".csv":"text/csv; charset=utf-8",".docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",".pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation",".zip":"application/zip",".html":"text/html; charset=utf-8",".json":"application/json; charset=utf-8",".gz":"application/gzip",".txt":"text/plain; charset=utf-8",".sqlite":"application/vnd.sqlite3",".svg":"image/svg+xml",".png":"image/png",".md":"text/markdown; charset=utf-8"}.get(ext,"application/octet-stream")
            data=p.read_bytes();self.send_response(200);self.send_header("Content-Type",ct);self.send_header("Content-Length",str(len(data)));self.send_header("Content-Disposition",("inline" if ext==".html" else "attachment")+f'; filename="{p.name}"');self.end_headers();self.wfile.write(data);return
        self._json(404,{"error":"not found"})
    def do_POST(self):
        if not self._guard_origin():return
        path=urlparse(self.path).path
        try:
            if path=="/api/workflows/create":self._json(200,create_research_workflow(self._body()));return
            if path.startswith("/api/workflows/") and path.endswith("/pause"):
                wid=path.split("/")[3];st=_ros_store();
                with st.cx() as c:c.execute("UPDATE workflows SET status='PAUSED',updated_at=? WHERE workflow_id=?",(time.strftime('%Y-%m-%dT%H:%M:%S'),wid));c.execute("UPDATE jobs SET status='PAUSED',updated_at=? WHERE workflow_id=? AND status='QUEUED'",(time.strftime('%Y-%m-%dT%H:%M:%S'),wid))
                self._json(200,st.get_workflow(wid));return
            if path.startswith("/api/workflows/") and path.endswith("/resume"):
                wid=path.split("/")[3];st=_ros_store();
                with st.cx() as c:c.execute("UPDATE workflows SET status='READY',updated_at=? WHERE workflow_id=?",(time.strftime('%Y-%m-%dT%H:%M:%S'),wid));c.execute("UPDATE jobs SET status='READY',updated_at=? WHERE workflow_id=? AND status='PAUSED'",(time.strftime('%Y-%m-%dT%H:%M:%S'),wid))
                st.queue_ready_jobs(wid);self._json(200,st.get_workflow(wid));return
            if path.startswith("/api/workflows/") and path.endswith("/cancel"):
                wid=path.split("/")[3];b=self._body();st=_ros_store();[st.request_cancel(j['job_id'],source=b.get('source') or 'workflow_api',reason=b.get('reason') or '') for j in st.get_workflow(wid)['jobs']];self._json(200,st.get_workflow(wid));return
            if path.startswith("/api/workflows/") and path.endswith("/schedule"):
                wid=path.split("/")[3];b=self._body();st=_ros_store();wf=st.get_workflow(wid)
                if not wf: raise FileNotFoundError(wid)
                start_at=str(b.get('start_at') or '').strip()
                if not start_at: raise ValueError('Zadejte datum a čas pokračování.')
                if len(start_at)==16: start_at += ':00'
                from scheduler import Scheduler
                spec={'project_id':wf['project_id'],'project_revision':wf['project_revision'],'use_latest_revision':False,'schedule_type':'one_time','schedule_expr':start_at,'next_run_at':start_at,'misfire_policy':'run_once','workflow_template':{'resume_workflow_id':wid}}
                self._json(200,Scheduler(st,ROOT/'data'/'project_store.sqlite').create(spec));return
            if path.startswith("/api/jobs/") and path.endswith("/retry"):
                jid=path.split("/")[3];st=_ros_store();j=st.get_job(jid)
                if not j:raise FileNotFoundError(jid)
                st.transition(jid,'RETRYING',force=True);st.queue_ready_jobs(j['workflow_id']);self._json(200,st.get_job(jid));return
            if path.startswith("/api/jobs/") and path.endswith("/configure"):
                jid=path.split("/")[3];b=self._body();st=_ros_store();self._json(200,st.configure_job(jid,provider=b.get('provider'),model=b.get('model'),estimated_cost_usd=b.get('estimated_cost_usd'),phase_policy=b.get('phase_policy')));return
            if path.startswith("/api/jobs/") and path.endswith("/cancel"):
                jid=path.split("/")[3];b=self._body();st=_ros_store();st.request_cancel(jid,source=b.get('source') or 'job_api',reason=b.get('reason') or '');self._json(200,st.get_job(jid));return
            if path.startswith("/api/approvals/") and path.endswith("/decide"):
                aid=path.split("/")[3];self._json(200,_ros_store().decide_approval(aid,self._body()));return
            if path=="/api/schedules":
                from scheduler import Scheduler
                self._json(200,Scheduler(_ros_store(),ROOT/"data"/"project_store.sqlite").create(self._body()));return
            if path=="/api/project/run":self._json(200,create_research_workflow(self._body()));return
            if path=="/api/fullsim/prepare":self._json(200,{"job_id":_start_job(self._body(),"fullsim_prepare")});return
            if path=="/api/fullsim/run":self._json(200,{"job_id":_start_job(self._body(),"fullsim_run")});return
            if path=="/api/fullsim/pipeline":self._json(200,{"job_id":_start_job(self._body(),"fullsim_pipeline")});return
            if path=="/api/fullsim/batch-pipeline":self._json(200,{"job_id":_start_job(self._body(),"fullsim_batch_pipeline")});return
            if path=="/api/simulation/context/enrich":self._json(200,{"job_id":_start_job(self._body(),"simulation_context_enrich")});return
            if path=="/api/simulation/context/deep":self._json(200,{"job_id":_start_job(self._body(),"simulation_context_deep")});return
            if path=="/api/simulation/context/resolve":self._json(200,{"job_id":_start_job(self._body(),"simulation_uncertainty_resolve")});return
            if path=="/api/fullsim/truth":
                b=self._body();from full_simulation import record_truth
                self._json(200,record_truth(str(b.get("run_id") or ""),b.get("truth") or {}));return
            if path=="/api/fullsim/submit":
                b=self._body();from full_simulation import register_external_prediction
                self._json(200,register_external_prediction(str(b.get("run_id") or ""),str(b.get("method") or "external"),b.get("prediction") or {},metadata=b.get("metadata") or {}));return
            if path=="/api/fullsim/calibration":
                b=self._body();from fullsim_learning import register_human_calibration
                from full_simulation import RUN_ROOT,BENCH_ROOT
                self._json(200,register_human_calibration(str(b.get("run_id") or ""),b.get("calibration") or {},run_root=RUN_ROOT,bench_root=BENCH_ROOT,
                                                          sizes=tuple(b.get("sizes") or [25,50,100,250]),seed=int(b.get("seed") or 20260817),prior_ess=b.get("prior_ess")));return
            if path=="/api/library/upload":
                b=self._body();raw=base64.b64decode(b.get("data_b64") or "")
                from data_library import add_source
                self._json(200,add_source(raw=raw,filename=str(b.get("filename") or "source"),source_type=str(b.get("source_type") or "other"),title=str(b.get("title") or ""),year=str(b.get("year") or ""),author=str(b.get("author") or ""),source_url=str(b.get("source_url") or ""),notes=str(b.get("notes") or "")));return
            if path=="/api/library/batch-upload":
                b=self._body(); items=[]
                for x in (b.get('files') or []):
                    items.append({**x,'raw':base64.b64decode(x.get('data_b64') or '')})
                from library_batch_import import batch_add_sources
                self._json(200,batch_add_sources(items,defaults=b.get('defaults') or {}));return
            if path=="/api/library/project-link":
                b=self._body();from data_library import link_source_to_project
                self._json(200,link_source_to_project(str(b.get('project_id') or ''),str(b.get('source_ref') or ''),source_kind=str(b.get('source_kind') or 'system_catalog'),usage_role=str(b.get('usage_role') or 'context')));return
            if path=="/api/results-registry/sync":
                from results_registry import sync_project_store,sync_showcase_demos,summary
                self._json(200,{"project_store":sync_project_store(),"demos":sync_showcase_demos(),"summary":summary()});return
            if path=="/api/population/calibration/propose":
                b=self._body();from population_context import propose_calibration
                self._json(200,propose_calibration(source_ref=str(b.get('source_ref') or ''),proposal_id=str(b.get('proposal_id') or ''),dimension_id=str(b.get('dimension_id') or ''),change_type=str(b.get('change_type') or 'overlay'),spec=b.get('spec') or {},note=str(b.get('note') or '')));return
            if path=="/api/population/calibration/decide":
                b=self._body();from population_context import decide_calibration
                self._json(200,decide_calibration(str(b.get('event_id') or ''),str(b.get('decision') or '')));return
            if path=="/api/population/calibration/apply-overlay":
                b=self._body();from population_context import register_applied_overlay
                self._json(200,register_applied_overlay(event_id=str(b.get('event_id') or '')));return
            if path=="/api/library/society/schedule":
                from society_insights import set_schedule
                b=self._body();self._json(200,set_schedule(bool(b.get('enabled',True)),str(b.get('cadence') or 'weekly'),str(b.get('population_mode') or 'LIVE')));return
            if path=="/api/library/society/ask":
                from society_insights import ask_society
                b=self._body();self._json(200,ask_society(str(b.get('question') or ''),str(b.get('population_mode') or 'LIVE'),bool(b.get('use_ai',False))));return
            if path=="/api/library/society/segment/run":
                from society_insights import run_segmentation
                b=self._body();self._json(200,run_segmentation(int(b.get('k') or 4),str(b.get('population_mode') or 'LIVE'),b.get('dimensions'),str(b.get('name') or 'Segment Lab')));return
            if path=="/api/library/society/segment/ask":
                from society_insights import ask_segment
                b=self._body();self._json(200,ask_segment(str(b.get('segment_id') or ''),str(b.get('question') or ''),bool(b.get('use_ai',False))));return
            if path=="/api/library/analyze":self._json(200,{"job_id":_start_job(self._body(),"library_analyze")});return
            if path=="/api/library/deep-research":self._json(200,{"job_id":_start_job(self._body(),"library_deep_research")});return
            if path=="/api/library/proposal/decide":
                b=self._body();from data_library import decide_proposal
                self._json(200,decide_proposal(str(b.get("proposal_id") or ""),str(b.get("decision") or "")));return
            if path=="/api/library/dimension/request":
                b=self._body();from data_library import create_dimension_request
                self._json(200,create_dimension_request(label=str(b.get('label') or ''),dimension_id=str(b.get('dimension_id') or ''),rationale=str(b.get('rationale') or ''),source_strategy=str(b.get('source_strategy') or 'document_or_research'),spec=b.get('spec') or {},origin=str(b.get('origin') or 'user')));return
            if path=="/api/library/dimension/spec":
                b=self._body();from data_library import update_dimension_spec
                self._json(200,update_dimension_spec(str(b.get('proposal_id') or ''),b.get('spec') or {}));return
            if path=="/api/library/dimension/materialize":
                b=self._body();from data_library import materialize_dimension
                out=materialize_dimension(str(b.get('proposal_id') or ''))
                try:core._PANEL_CACHE.clear()
                except Exception:pass
                self._json(200,out);return
            if path=="/api/audiences/upload":
                b=self._body(); raw=base64.b64decode(b.get("data_b64") or "")
                if not raw: raise ValueError("Nahrajte .xlsx nebo .csv audience.")
                name=Path(str(b.get("filename") or "audience.xlsx")).name
                p=UPLOADS/f"{int(time.time())}_{name}"; p.write_bytes(raw)
                meta=import_audience_file(p,filename=name,audience_name=b.get("audience_name") or None,audience_type=b.get("audience_type") or "special_audience",description=b.get("description") or "")
                self._json(200,{"audience":meta,"preflight":audience_preflight(meta["audience_id"],n=int(b.get("n") or 120))});return
            if path=="/api/audiences/preflight":
                b=self._body();self._json(200,audience_preflight(str(b.get("dataset_id") or ""),required_roles=b.get("required_roles") or None,required_columns=b.get("required_columns") or None,n=int(b.get("n") or 120)));return
            if path=="/api/audiences/delete":
                b=self._body();delete_audience(str(b.get("dataset_id") or ""));self._json(200,{"ok":True});return
            if path=="/api/research/intake":
                from project_intake import intake
                b=self._body(); payload=b.get("briefing") or b
                self._json(200,intake(payload,study_type=b.get("study_type") or None,current_slots=b.get("current_slots") or None));return
            if path=="/api/research/compile_instruments":
                from instrument_library import merge_standard_sections, compile_standard_sections
                b=self._body(); p=normalize_project(b.get("project") or {})
                if b.get("study_type"): p["study_type"]=str(b.get("study_type"))
                if isinstance(b.get("study_config"),dict): p["study_config"]=dict(b.get("study_config") or {})
                compiled=compile_standard_sections(p.get("study_type") or "custom",p.get("study_config") or {},include_optional=bool((p.get("study_config") or {}).get("include_optional_instruments",False)))
                if compiled.get("missing_slots"): raise ValueError("Chybí povinné designové vstupy: " + ", ".join(compiled["missing_slots"]))
                p=merge_standard_sections(p,replace_existing_standard=True)
                self._json(200,{"project":p,"instrument_library":{"version":compiled["library_version"],"skipped":compiled["skipped"],"missing_slots":compiled["missing_slots"]}});return
            if path=="/api/scenario/compile":
                self._json(200,{"job_id":_start_job(self._body(),"scenario_compile")});return
            if path=="/api/scenario/compile-batch":
                self._json(200,{"job_id":_start_job(self._body(),"scenario_compile_batch")});return
            if path=="/api/scenario/approve":
                b=self._body();from scenario_compiler import approve_scenario
                self._json(200,approve_scenario(b.get("contract") or {}));return
            if path=="/api/scenario/approve-batch":
                b=self._body();from scenario_compiler import approve_scenario_batch
                self._json(200,approve_scenario_batch(b.get("batch") or {}));return
            if path=="/api/scenario/truth":
                b=self._body();from scenario_truth_log import record
                self._json(200,record(b));return
            if path=="/api/providers/claude-code/setup":
                from edition_config import claude_code_enabled
                if not claude_code_enabled(): self._json(400,{"ok":False,"error":"Claude Code není v této edici povolen."});return
                kwargs={"cwd":str(ROOT),"env":{**os.environ,"PYTHONUTF8":"1","PYTHONIOENCODING":"utf-8"}}
                if os.name=="nt":
                    wrapper=ROOT/"INSTALOVAT_CLAUDE_CODE.bat"
                    comspec=os.environ.get("COMSPEC") or "cmd.exe"
                    cmd=[comspec,"/d","/k",str(wrapper)]
                    kwargs["creationflags"]=getattr(subprocess,"CREATE_NEW_CONSOLE",0)
                else:
                    # On non-Windows there is no safe portable way for an HTTP server to open an interactive terminal.
                    self._json(400,{"ok":False,"error":"Integrované interaktivní přihlášení je v tomto balíku určeno pro Windows."});return
                subprocess.Popen(cmd,**kwargs)
                self._json(202,{"ok":True,"started":True,"message":"Otevřelo se samostatné persistentní okno pro instalaci/přihlášení Claude Code. Zůstane otevřené a ukáže READY nebo konkrétní chybu. Potom klikněte na Znovu ověřit."});return
            if path=="/api/settings/api_keys":self._json(200,save_api_keys(self._body()));return
            if path=="/api/settings/anthropic_check":self._json(200,check_anthropic_provider(self._body()));return
            if path=="/api/settings/ai_check":self._json(200,check_ai_providers(self._body()));return
            if path=="/api/support/bundle":
                b=self._body();from support_bundle import create_bundle
                p=create_bundle(str(b.get("job_id") or "").strip() or None)
                self._json(200,{"ok":True,"name":p.name,"download_url":"/api/support/download?name="+quote(p.name),"privacy":"bez promptů, obsahu projektu a přihlašovacích údajů"});return
            if path=="/api/settings/ai_diagnose":self._json(200,{"job_id":_start_job(self._body(),"ai_diagnose")});return
            if path=="/api/assistant/search":self._json(200,project_memory_search(self._body()));return
            if path=="/api/assistant/chat":self._json(200,{"job_id":_start_job(self._body(),"project_assistant")});return
            if path=="/api/demos/copy":self._json(200,demo_copy_project(self._body()));return
            if path=="/api/projects/create":self._json(200,create_project_state(self._body()));return
            if path=="/api/projects/overview":self._json(200,project_overview(self._body()));return
            if path=="/api/projects/impact":self._json(200,project_impact(self._body()));return
            if path=="/api/projects/continue-claude-api":self._json(200,project_continue_claude_api(self._body()));return
            if path=="/api/projects/settings":self._json(200,project_settings_update(self._body()));return
            if path=="/api/projects/history-action":self._json(200,project_history_action(self._body()));return
            if path=="/api/projects/export":self._json(200,project_export(self._body()));return
            if path=="/api/projects/save":self._json(200,save_project_state(self._body()));return
            if path=="/api/projects/load":self._json(200,load_project_state(self._body()));return
            if path=="/api/visualization/respondents":self._json(200,visualization_respondents(self._body()));return
            if path=="/api/visualization/dialogue":self._json(200,visualization_dialogue(self._body()));return
            if path=="/api/visualization/object-map":self._json(200,visualization_object_map(self._body()));return
            if path=="/api/visualization/layout":self._json(200,visualization_layout_action(self._body()));return
            if path=="/api/visualization/segment":self._json(200,visualization_segment_action(self._body()));return
            if path=="/api/visualization/compare":self._json(200,visualization_compare(self._body()));return
            if path=="/api/visualization/intelligence":self._json(200,visualization_intelligence(self._body()));return
            if path=="/api/project/attachment":self._json(200,save_project_attachment(self._body()));return
            if path=="/api/project/check":self._json(200,project_preflight(self._body().get("project") or {}));return
            if path=="/api/project/final-review":self._json(200,{"job_id":_start_job(self._body(),"final_review")});return
            if path=="/api/persona/ablation":self._json(200,{"job_id":_start_job(self._body(),"persona_ablation")});return
            if path=="/api/persona/benchmark/run":self._json(200,{"job_id":_start_job(self._body(),"persona_benchmark")});return
            if path=="/api/persona/calibration/fit":
                b=self._body(); raw=base64.b64decode(b.get("data_b64") or "")
                if not raw: raise ValueError("Nahrajte benchmark CSV.")
                p=UPLOADS/(f"{int(time.time())}_persona_benchmark.csv"); p.write_bytes(raw)
                from persona_calibration import fit_calibration_csv
                self._json(200,fit_calibration_csv(p,activate=True));return
            if path=="/api/discovery/strategy":self._json(200,{"job_id":_start_job(self._body(),"audience_strategy")});return
            if path=="/api/copilot/chat":self._json(200,{"job_id":_start_job(self._body(),"copilot")});return
            if path=="/api/research/analyze":self._json(200,{"job_id":_start_job(self._body(),"research_analysis")});return
            if path=="/api/research/build_questionnaire":self._json(200,{"job_id":_start_job(self._body(),"questionnaire_build")});return
            if path=="/api/questionnaire/upload":self._json(200,import_questionnaire_payload(self._body()));return
            if path=="/api/research/deep":self._json(200,{"job_id":_start_job(self._body(),"deep_research")});return
            if path=="/api/questionnaire/optimize":self._json(200,{"job_id":_start_job(self._body(),"questionnaire_optimize")});return
            if path=="/api/questionnaire/repair":self._json(200,{"job_id":_start_job(self._body(),"questionnaire_repair")});return
            if path=="/api/persona/suggest":self._json(200,{"job_id":_start_job(self._body(),"persona_suggest")});return
            if path=="/api/results/targets":
                b=self._body();from result_context import extract_targets
                self._json(200,{"targets":extract_targets(b.get("project") or {},b.get("result_summary") or {},include_mapped=bool(b.get("include_mapped",False)))});return
            if path=="/api/results/verify":self._json(200,{"job_id":_start_job(self._body(),"result_verify")});return
            if path in {"/api/results/contextual_calibration","/api/results/contextual_scenario"}:self._json(200,calibrate_result_context(self._body()));return
            if path=="/api/results/final_report":self._json(200,create_final_client_report(self._body()));return
            if path=="/api/discovery/from_run":self._json(200,run_discovery(self._body()));return
            if path=="/api/preflight":self._json(200,preflight(self._body()));return
            if path=="/api/run":self._json(200,{"job_id":_start_job(self._body(),"run")});return
            if path=="/api/research/design":self._json(200,{"job_id":_start_job(self._body(),"research_design")});return
            if path=="/api/navrh":self._json(200,{"job_id":_start_job(self._body(),"design")});return
            if path=="/api/audience/recommend":
                b=self._body(); payload=b.get("briefing") or b.get("text") or b
                self._json(200,recommend_audience(payload,audiences=list_audiences(),requested_n=int(b.get("n") or 300)));return
            if path=="/api/audience":
                b=self._body();clean,dropped=sanitize_filters(core.load_panel_cached(),b.get("filtry") or {});out=feasibility(core.load_panel_cached(),clean,int(b.get("n",120)));out["dropped"]=dropped;self._json(200,out);return
            if path in {"/api/audience/navrh","/api/audience/propose"}:
                self._json(200,{"job_id":_start_job(self._body(),"audience_propose")});return
            if path=="/api/segment/preview":
                b=self._body();from pipeline import Panel;from segment_orchestration import prepare_segment
                panel=Panel(core.load_panel_cached().copy());_,meta=prepare_segment(panel,b.get("segment"),model=DEFAULT_MODEL,mode="dry",seed=42,workers=4);self._json(200,meta);return
            if path=="/api/study/check":
                from study_contract import StudySpec
                spec=StudySpec(**(self._body().get("spec") or {}));self._json(200,{"ok":True,"object_family":spec.object_family,"n_objects":len(spec.objects),"familiarity_required":spec.familiarity_required,"n_questions":len(spec.questionnaire())});return
            if path=="/api/study/run":self._json(200,{"job_id":_start_job(self._body(),"study")});return
            if path=="/api/ingest":
                b=self._body();name=Path(str(b.get("filename") or "upload.csv")).name;raw=base64.b64decode(b.get("data_b64") or "");p=UPLOADS/f"{int(time.time())}_{name}";p.write_bytes(raw)
                from npc_ingest import IngestManager
                m=IngestManager(registry_path=ROOT/"data"/"ingest_registry.sqlite",default_panel=core.PANEL_PATH)
                try:r=m.ingest(p,track=b.get("track"),source_id=b.get("source") or None,description="UI ingest")
                finally:m.close()
                if r.decision=="ACCEPT" and r.track in {"A","B"}:r.metrics["active_panel_path"]=str(core.refresh_active_panel_path())
                self._json(200,r.__dict__);return
        except Exception as exc:
            (ROOT/"logs").mkdir(exist_ok=True)
            with (ROOT/"logs"/"backend_errors.log").open("a",encoding="utf-8") as f:f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {path}\n{traceback.format_exc()}\n")
            self._json(400,{"error":str(exc),"log":"logs/backend_errors.log"});return
        self._json(404,{"error":"not found"})
    def do_DELETE(self):
        if not self._guard_origin():return
        path=urlparse(self.path).path
        if path.startswith("/api/schedules/"):
            from scheduler import Scheduler
            sid=path.rsplit("/",1)[1];Scheduler(_ros_store(),ROOT/"data"/"project_store.sqlite").delete(sid);self._json(200,{"ok":True});return
        self._json(404,{"error":"not found"})
    def do_PATCH(self):
        if not self._guard_origin():return
        path=urlparse(self.path).path
        if path.startswith("/api/schedules/"):
            from scheduler import Scheduler
            sid=path.rsplit("/",1)[1];self._json(200,Scheduler(_ros_store(),ROOT/"data"/"project_store.sqlite").patch(sid,self._body()));return
        self._json(404,{"error":"not found"})
    def log_message(self,fmt,*args):return


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--host",default="127.0.0.1");ap.add_argument("--port",type=int,default=8766);ap.add_argument("--no-open",action="store_true");a=ap.parse_args()
    # Friendly desktop behaviour: if the preferred local port is already occupied,
    # try a few neighbouring ports instead of failing with an opaque socket error.
    ports=[a.port] if a.port==0 else list(range(a.port,a.port+10))
    srv=None;last_exc=None
    for port in ports:
        try:
            srv=ThreadingHTTPServer((a.host,port),Handler);break
        except OSError as exc:
            last_exc=exc
    if srv is None:
        raise SystemExit(f"NPC Panel nelze spustit: žádný port {a.port}–{a.port+9} není volný. ({last_exc})")
    actual_port=int(srv.server_address[1]);url=f"http://{a.host}:{actual_port}";print(f"NPC Panel {RELEASE}: {url}")
    state_path=ROOT/"data"/"server_state.json";state_path.parent.mkdir(parents=True,exist_ok=True)
    state_path.write_text(json.dumps({"pid":os.getpid(),"url":url,"host":a.host,"port":actual_port,"release":RELEASE,"root":str(ROOT),"started_at":time.strftime('%Y-%m-%dT%H:%M:%S')},ensure_ascii=False,indent=2),encoding="utf-8")
    if actual_port!=a.port:
        print(f"[NPC] Port {a.port} byl obsazený, používám {actual_port}.")
    if not a.no_open:threading.Timer(1,lambda:webbrowser.open(url)).start()
    try:srv.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        srv.server_close()
        try:state_path.unlink(missing_ok=True)
        except Exception:pass
    return 0
if __name__=="__main__":raise SystemExit(main())
