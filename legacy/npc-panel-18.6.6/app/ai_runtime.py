"""Unified metadata and policy for user-facing AI actions.

Provider execution remains centralized in :mod:`ai_router`.  This module is the
single UX/runtime catalogue: every durable AI action has an expected duration,
hard ceiling, user-facing phase name and whether it is a web-research operation.
The estimates are deliberately ranges, not fake progress percentages.
"""
from __future__ import annotations
from typing import Any

AI_ACTIONS: dict[str, dict[str, Any]] = {
    "research_analysis": {"label":"Pochopení zadání", "usual_seconds":[15,75], "hard_seconds":180, "research":False},
    "final_review": {"label":"Finální AI kontrola projektu", "usual_seconds":[15,90], "hard_seconds":180, "research":False},
    "copilot": {"label":"Výzkumný partner", "usual_seconds":[10,75], "hard_seconds":180, "research":False},
    "project_assistant": {"label":"AI asistent · historie projektů", "usual_seconds":[8,70], "hard_seconds":180, "research":False},
    "questionnaire_build": {"label":"Návrh dotazníku", "usual_seconds":[25,120], "hard_seconds":240, "research":False},
    "persona_suggest": {"label":"Návrh persony", "usual_seconds":[15,90], "hard_seconds":180, "research":False},
    "deep_research": {"label":"Hloubkový research", "usual_seconds":[120,600], "hard_seconds":900, "research":True},
    "library_analyze": {"label":"Analýza zdroje Data Library", "usual_seconds":[20,120], "hard_seconds":240, "research":False},
    "library_deep_research": {"label":"Data Library · Deep Research", "usual_seconds":[120,600], "hard_seconds":900, "research":True},
    "questionnaire_optimize": {"label":"Research + optimalizace dotazníku", "usual_seconds":[150,720], "hard_seconds":960, "research":True},
    "questionnaire_repair": {"label":"AI oprava konkrétní otázky", "usual_seconds":[10,90], "hard_seconds":180, "research":False},
    "result_verify": {"label":"Externí ověření výsledků", "usual_seconds":[120,600], "hard_seconds":900, "research":True},
    "scenario_compile": {"label":"AI návrh scénáře", "usual_seconds":[15,90], "hard_seconds":180, "research":False},
    "simulation_context_enrich": {"label":"Simulace · rychlé pochopení kontextu", "usual_seconds":[8,75], "hard_seconds":110, "research":False},
    "simulation_context_deep": {"label":"Simulace · volitelný Deep Research", "usual_seconds":[120,720], "hard_seconds":1200, "research":True},
    "simulation_uncertainty_resolve": {"label":"Simulace · dohledání nejistot", "usual_seconds":[90,600], "hard_seconds":900, "research":True},
    "scenario_compile_batch": {"label":"AI návrh variant scénáře", "usual_seconds":[30,360], "hard_seconds":600, "research":False},
    "fullsim_pipeline": {"label":"Simulace · celý běh", "usual_seconds":[180,2400], "hard_seconds":5400, "research":True},
    "fullsim_batch_pipeline": {"label":"Simulace · porovnání variant", "usual_seconds":[300,5400], "hard_seconds":10800, "research":True},
    "fullsim_prepare": {"label":"Scénářový world model", "usual_seconds":[45,420], "hard_seconds":720, "research":True},
    "fullsim_run": {"label":"Full Simulation", "usual_seconds":[90,1200], "hard_seconds":1800, "research":False},
    "audience_propose": {"label":"AI převod cílovky na filtry", "usual_seconds":[10,60], "hard_seconds":150, "research":False},
    "audience_strategy": {"label":"Hledání ideální skupiny", "usual_seconds":[20,120], "hard_seconds":240, "research":False},
    "ai_diagnose": {"label":"Diagnostika AI", "usual_seconds":[5,45], "hard_seconds":90, "research":False},
    "persona_ablation": {"label":"Ablace persony", "usual_seconds":[120,1200], "hard_seconds":1800, "research":False},
    "persona_benchmark": {"label":"Human benchmark persony", "usual_seconds":[180,1800], "hard_seconds":2400, "research":False},
    "research_design": {"label":"Návrh výzkumu", "usual_seconds":[20,120], "hard_seconds":240, "research":False},
    "design": {"label":"Návrh dotazníku", "usual_seconds":[20,120], "hard_seconds":240, "research":False},
    "project": {"label":"Výzkumný běh", "usual_seconds":[60,1800], "hard_seconds":3600, "research":False},
    "run": {"label":"Výzkumný běh", "usual_seconds":[60,1800], "hard_seconds":3600, "research":False},
    "study": {"label":"Studie", "usual_seconds":[60,1800], "hard_seconds":3600, "research":False},
}

def action_profile(kind: str | None) -> dict[str, Any]:
    k=str(kind or "").strip()
    x=dict(AI_ACTIONS.get(k) or {"label":k or "AI operace","usual_seconds":[20,300],"hard_seconds":600,"research":False})
    x["kind"]=k
    return x

def format_range_seconds(v: list[int] | tuple[int,int] | None) -> str:
    if not v or len(v)<2:return ""
    a,b=max(1,int(v[0])),max(1,int(v[1]))
    def f(x:int)->str:
        if x<60:return f"{x} s"
        m=round(x/60)
        return f"{m} min"
    return f"{f(a)}–{f(b)}"
