"""Guided research design for NPC Panel 17.0.

The workflow intentionally separates *thinking about the research* from *writing the
questionnaire*. Claude is optional: users can skip these functions and edit the
project manually. When used, Claude first analyzes the business/research problem,
identifies tracked-object sets and non-object outcomes, asks only material follow-up
questions, and only then creates a questionnaire.
"""
from __future__ import annotations

from provider_auth import create_anthropic_client

from typing import Any
import json
import os
import html as _html
import re

from anthropic_compat import create_message
from runtime_config import resolve_model
from product_policy import tracked_set_limits, tracked_set_warning
from research_project import empty_project, normalize_project
from project_intake import intake as intake_project
from instrument_library import compile_standard_sections, merge_standard_sections, library_version
from typology_reference import compact_typology_context
from population_subpanels import list_subpanels, get_subpanel, runtime_filters, list_special_panels
from audience_selector import recommend as recommend_audience



def _clean_ai_text(value: Any) -> str:
    s=_html.unescape(str(value or ''))
    # Strip normal, escaped and line-broken XML/HTML-ish tags such as <item>.
    s=re.sub(r'<[^>]{0,240}>','',s,flags=re.S)
    lines=[x.strip() for x in s.replace('\r','').split('\n')]
    nonempty=[x for x in lines if x]
    if len(nonempty)>=4 and sum(len(x)<=2 for x in nonempty)/len(nonempty)>=0.72:
        # Broken structured-output rendering occasionally emits one character per line.
        s=''.join(nonempty)
    else:
        s='\n'.join(lines)
    s=re.sub(r'[ \t]+',' ',s)
    s=re.sub(r'\n{3,}','\n\n',s)
    return s.strip()

def _sanitize_ai_tree(value: Any) -> Any:
    if isinstance(value,str): return _clean_ai_text(value)
    if isinstance(value,list): return [_sanitize_ai_tree(x) for x in value]
    if isinstance(value,dict): return {k:_sanitize_ai_tree(v) for k,v in value.items()}
    return value

ANALYSIS_SYSTEM = r"""Jsi seniorní český research director. Uživatel není povinen znát metodiku.
Nejdřív analyzuješ výzkumný problém, NEPIŠ ještě celý dotazník.

Tvým úkolem je:
1. pochopit produkt/službu/téma a rozhodnutí, které má výzkum podpořit;
2. navrhnout CO zkoumat a PROČ;
3. formulovat 1–5 explicitních VÝZKUMNÝCH OTÁZEK, na které musí finální report přímo odpovědět;
4. rozlišit SLEDOVANÉ OBJEKTOVÉ SADY a ostatní proměnné.

SLEDOVANÁ OBJEKTOVÁ SADA = vzájemně srovnatelné položky stejného logického typu; 4-15 je doporučený rozsah, ne univerzální blokace,
hodnocených stejnou otázkou a stejnou škálou. Typ může být téměř cokoli: značky, média
(televize, internet, rádio...), emoce, atributy, vztahy k produktu, procesy, povolání,
kanály, touchpointy, alternativy, koncepty, potřeby apod. Neomezuj se na „atributy“.
Jeden výzkum může a často má mít VÍCE různých sad, např. zvlášť média, zvlášť emoce a
zvlášť vztahové výroky. Nikdy nemíchej nesrovnatelné typy v jedné sadě.

VŽDY aktivně hledej vhodné sledované sady. Pokud existuje přirozená sada značek, médií, emocí,
atributů, konceptů apod., navrhni ji. Pokud ale výzkum žádnou přirozenou srovnávací sadu nemá
(např. čistý incidence/pricing/outcome research), vrať tracked_sets=[] a výslovně vysvětli, že
mapa není pro tento design nutná. NIKDY nevyráběj univerzální vztahovou baterii jen proto, aby
formálně existovala mapa. U každé skutečné sady vysvětli, co její porovnání přinese.

NĚCO NENÍ OBJEKT, pokud je to jednorázový outcome nebo profilová proměnná: purchase intent,
maximální cena, věk, příjem, jedna NPS otázka, screening, důvod odmítnutí apod. Ty dej do
non_object_measures a vysvětli proč.

Pole study_slots vyplňuj POUZE z informací, které uživatel skutečně uvedl; chybějící seznam stran, cenu nebo koncept si nevymýšlej.

Pokud dostaneš TYPOLOGII 2026, je to pouze hypotézová referenční vrstva. Smíš z ní navrhnout testovatelné hypotézy nebo srovnání skupin, ale NESMÍŠ tvrdit, že konkrétní respondent typ má, přiřazovat typy podle pár atributů ani používat historické podíly jako současné populační váhy.

Pokud je mezi VESTAVĚNÝMI POPULAČNÍMI SUBPANELY přesná a metodicky vhodná cílová skupina, preferuj ji a vrať její builtin_subpanel key. Experimentální/limited panely vždy označ jako omezené a doporuč Special Audience pro robustní ostrý výzkum.

Ptej se jen na chybějící informace, které by zásadně změnily design (např. co je produkt,
jaké rozhodnutí má výzkum podpořit, které koncepty se testují, reálné cenové body). Pokud
lze udělat rozumný editovatelný návrh bez otázky, nedoptávej se.

Navrhni přiměřenou komplexnost: short (~3-5 min), standard (~6-10 min), deep (~10-15 min).
Vrať pouze tool call."""

BUILD_SYSTEM = r"""Jsi seniorní český výzkumný metodik. Z již schválené analýzy vytvoř JEDEN
výzkumný projekt. STANDARDNÍ KONSTRUKTY, které už mají metadata standard_instrument=true, jsou
kanonické instrumenty knihovny: NEMĚŇ jejich wording, škálu ani routing a nemaž je. AI doplňuje
jen klientsky specifické otázky a metodicky zdůvodněné bloky. Projekt může obsahovat několik běžných bloků a několik sledovaných
objektových sad. Všechny sady běží na stejném respondentním vzorku.

Pravidla dotazníku:
- krátký a rozhodovací; žádné návodné dvojotázky;
- screening/znalost před hodnocením a purchase intent;
- výběrové otázky mají konkrétní a vzájemně srozumitelné kategorie;
- škály mají kotvy;
- citlivější a profiling otázky až později;
- cenové body si nikdy nevymýšlej, pokud je uživatel nedal;
- open-ended otázky používej jen tam, kde přidají vysvětlení;
- sledovaná sada má položky jednoho typu a jednu společnou object_question s {object}; typicky 4-15, ale řiď se cílem výzkumu a technickou policy;
- familiarity_required používej pouze když je pro konkrétní typ položek smysluplné (např. značky/produkty),
  ne automaticky pro média, emoce, vztahové výroky nebo atributy;
- každý tracked set má vlastní sekci object_battery; v jednom projektu může být více map;
- běžné outcomes (purchase intent, cena, frekvence, demografie) zůstanou v questions sekcích;
- persona_mode default calibrated; human CALIBRATION benchmark může zvolit demographics/core/full, bez profilu padá na core;
- model default sonnet jako doporučená kvalitní volba; uživatel jej změní až před spuštěním.

Vrať celý projekt v tool callu. Vrať i krátké vysvětlení změn."""


def _tracked_set_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "object_type": {"type": "string"},
            "purpose": {"type": "string"},
            "objects": {"type": "array", "minItems": 1, "maxItems": 40, "items": {"type": "string"}},
            "object_question": {"type": "string"},
            "scale_labels": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string"}},
            "familiarity_required": {"type": "boolean"},
            "why_map": {"type": "string"},
            "objects_are_suggested": {"type": "boolean"},
        },
        "required": ["title", "object_type", "purpose", "objects", "object_question", "scale_labels", "familiarity_required", "why_map"],
        "additionalProperties": False,
    }


def _analysis_tool() -> dict[str, Any]:
    return {
        "name": "submit_research_analysis",
        "description": "Structured analysis before questionnaire construction.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "problem_summary": {"type": "string"},
                "decision_use": {"type": "string"},
                "objectives": {"type": "array", "items": {"type": "string"}},
                "research_questions": {"type": "array", "minItems": 1, "maxItems": 5, "items": {"type": "string"}},
                "hypotheses": {"type": "array", "items": {"type": "string"}},
                "recommended_topics": {"type": "array", "items": {"type": "string"}},
                "tracked_sets": {"type": "array", "items": _tracked_set_schema()},
                "non_object_measures": {"type": "array", "items": {
                    "type": "object", "properties": {
                        "name": {"type": "string"}, "reason": {"type": "string"},
                        "question_type": {"type": "string"},
                    }, "required": ["name", "reason"], "additionalProperties": False,
                }},
                "audience_recommendation": {"type": "object", "properties": {
                    "strategy": {"type": "string", "enum": ["population", "filters", "discover"]},
                    "description": {"type": "string"}, "reason": {"type": "string"},
                    "builtin_subpanel": {"type": "string"},
                    "source_mode": {"type": "string", "enum": ["population", "customer", "special_audience"]},
                    "dataset_id": {"type": "string"},
                    "action": {"type": "string"},
                }, "required": ["strategy", "description", "reason"], "additionalProperties": False},
                "study_slots": {"type": "object", "properties": {
                    "party_list": {"type": "array", "items": {"type": "string"}},
                    "brand_name": {"type": "string"}, "concept_name": {"type": "string"},
                    "concept_description": {"type": "string"}, "subject_name": {"type": "string"},
                    "scenario_baseline": {"type": "string"}, "scenario_event": {"type": "string"}
                }, "additionalProperties": False},
                "complexity": {"type": "string", "enum": ["short", "standard", "deep"]},
                "estimated_minutes": {"type": "number"},
                "method_reason": {"type": "string"},
                "questions_for_user": {"type": "array", "items": {"type": "string"}},
                "ready_for_questionnaire": {"type": "boolean"},
            },
            "required": ["title", "problem_summary", "decision_use", "objectives", "research_questions", "tracked_sets",
                         "non_object_measures", "audience_recommendation", "complexity", "method_reason",
                         "questions_for_user", "ready_for_questionnaire", "hypotheses", "recommended_topics",
                         "study_slots", "estimated_minutes"],
            "additionalProperties": False,
        },
    }


def _fast_analysis_tool() -> dict[str, Any]:
    """Small first-pass contract for the first screen."""
    return {
        "name": "submit_fast_research_analysis",
        "description": "Fast first-pass research brief analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "problem_summary": {"type": "string"},
                "decision_use": {"type": "string"},
                "objectives": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "string"}},
                "research_questions": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "string"}},
                "hypotheses": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
                "tracked_sets": {"type": "array", "maxItems": 5, "items": _tracked_set_schema()},
                "non_object_measures": {"type": "array", "maxItems": 10, "items": {
                    "type": "object", "properties": {
                        "name": {"type": "string"}, "reason": {"type": "string"}, "question_type": {"type": "string"}
                    }, "required": ["name", "reason"], "additionalProperties": False
                }},
                "questions_for_user": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
                "complexity": {"type": "string", "enum": ["short", "standard", "deep"]},
                "method_reason": {"type": "string"},
                "ready_for_questionnaire": {"type": "boolean"}
            },
            "required": ["title", "problem_summary", "decision_use", "objectives", "research_questions",
                         "tracked_sets", "non_object_measures", "questions_for_user", "complexity",
                         "method_reason", "ready_for_questionnaire"],
            "additionalProperties": False
        }
    }


def _question_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string"}, "text": {"type": "string"},
            "typ": {"type": "string", "enum": ["vyber", "multi", "skala", "otevrena"]},
            "kategorie": {"type": "array", "items": {"type": "string"}},
            "skala": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "integer"}},
            "popisky_skaly": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string"}},
            "povolit_nevim": {"type": "boolean"}, "max_slov": {"type": "integer"},
            "filtr": {"type": "string"}, "topics": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["text", "typ"], "additionalProperties": False,
    }


def _section_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string"}, "type": {"type": "string", "enum": ["questions", "object_battery"]},
            "title": {"type": "string"}, "purpose": {"type": "string"},
            "questions": {"type": "array", "items": _question_schema()},
            "object_family": {"type": "string"}, "object_type": {"type": "string"},
            "objects": {"type": "array", "minItems": 1, "maxItems": 40, "items": {"type": "string"}},
            "object_question": {"type": "string"},
            "scale_labels": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string"}},
            "familiarity_required": {"type": "boolean"},
            "output_type": {"type": "string", "enum": ["pozicni_mapa", "segmentace", "lovebrand", "test_konceptu"]},
            "visualize": {"type": "boolean"}, "metadata": {"type": "object"},
        },
        "required": ["type", "title"], "additionalProperties": False,
    }


def _project_tool() -> dict[str, Any]:
    return {
        "name": "submit_questionnaire_project",
        "description": "Complete questionnaire project based on approved analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "project": {
                    "type": "object",
                    "properties": {
                        "schema_version": {"type": "integer"}, "title": {"type": "string"}, "goal": {"type": "string"},
                        "decision_use": {"type": "string"}, "briefing": {"type": "object"}, "research_plan": {"type": "object"},
                        "audience": {"type": "object"}, "n": {"type": "integer"},
                        "persona_mode": {"type": "string", "enum": ["full", "demographics", "core", "none", "calibrated"]},
                        "model": {"type": "string"}, "research_context": {"type": "boolean"},
                        "sections": {"type": "array", "items": _section_schema()},
                        "notes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "goal", "audience", "n", "sections"],
                    "additionalProperties": False,
                },
            },
            "required": ["message", "project"], "additionalProperties": False,
        },
    }


def _tool_input(response: Any) -> dict[str, Any]:
    blocks = [x for x in getattr(response, "content", []) if getattr(x, "type", None) == "tool_use"]
    if not blocks:
        raise ValueError("Claude nevrátil strukturovaný výstup.")
    return dict(blocks[0].input)

def _structured_with_fallback(*, system: str, prompt: str, tool: dict[str, Any], model: str, max_tokens: int, provider: str | None = None, interactive: bool = False, max_turns: int = 8) -> tuple[dict[str, Any], dict[str, Any]]:
    """Delegate to the AI router: Anthropic first, then OpenAI, with per-provider retry.

    The router owns tool-use → JSON-contract escalation and model repair, so a schema
    or model incompatibility no longer degrades the design step to a local fallback.
    """
    from ai_router import call_structured
    from provider_auth import get_ai_provider
    out = call_structured(system=system, messages=[{"role": "user", "content": prompt}],
                          schema=tool["input_schema"], schema_name=tool["name"],
                          anthropic_model=model, openai_model=(model if str(provider or get_ai_provider()).lower()=="openai" else None), max_tokens=max_tokens, prefer=(provider or get_ai_provider()), allow_fallback=False,
                          timeout=(75 if interactive else None), claude_max_turns=max_turns, claude_interactive=interactive)
    audit = {k: out.get(k) for k in ("provider", "model", "mode", "fallback_used", "attempts")}
    return out["data"], audit


def _fast_claude_text_recovery(*, system: str, prompt: str, tool: dict[str, Any], model: str, first_error: Exception) -> tuple[dict[str, Any], dict[str, Any]]:
    """Second-chance parser for the FIRST brief analysis, using the same Claude Code provider.

    This is not a model/provider/local fallback. It is only used when the structured
    CLI contract failed or Claude returned malformed structured output. The second
    call asks the same Claude subscription for one small JSON object and parses it
    locally. This keeps the first UX step robust across Claude Code CLI variations.
    """
    from claude_code_provider import text_call
    from ai_router import extract_json
    schema=tool.get("input_schema") or {}
    recovery_prompt=(
        prompt+"\n\nPRVNÍ STRUKTUROVANÝ POKUS SE TECHNICKY NEPODAŘIL. "
        "Neřeš chybu a znovu věcně zpracuj PŮVODNÍ zadání. Vrať POUZE jeden validní JSON objekt, "
        "bez markdownu a bez komentáře. Nevymýšlej značky, produkty, cílovky ani fakta, které uživatel neuvedl.\n"
        "JSON SCHÉMA:\n"+json.dumps(schema,ensure_ascii=False,separators=(",",":"))
    )
    rr=text_call(system=system,messages=[{"role":"user","content":recovery_prompt}],model=model,max_tokens=1200,timeout=75,interactive=True,max_turns=2)
    raw=extract_json(str(rr.get("text") or ""))
    if not isinstance(raw,dict): raise ValueError("Claude recovery nevrátil JSON objekt.")
    # Normalize only contract-shape details. Never invent substantive research content.
    raw.setdefault("title","")
    raw.setdefault("problem_summary","")
    raw.setdefault("decision_use","")
    for key in ("objectives","research_questions","hypotheses","tracked_sets","non_object_measures","questions_for_user"):
        if not isinstance(raw.get(key),list): raw[key]=[]
    if not raw["objectives"]: raw["objectives"]=[raw.get("problem_summary") or "Zodpovědět hlavní otázku ze zadání."]
    if not raw["research_questions"]: raw["research_questions"]=[raw.get("problem_summary") or "Jaká je odpověď na hlavní problém ze zadání?"]
    raw["complexity"]=str(raw.get("complexity") or "standard")
    if raw["complexity"] not in {"short","standard","deep"}: raw["complexity"]="standard"
    raw.setdefault("method_reason","Rychlý první návrh podle uživatelského briefu.")
    raw["ready_for_questionnaire"]=bool(raw.get("ready_for_questionnaire",True))
    audit={"provider":"claude_code_subscription","model":rr.get("model") or model,"mode":"prompt_json_recovery","fallback_used":False,
           "attempts":["structured_failed","same_claude_prompt_json_recovery"],"first_error":str(first_error)[:700]}
    return raw,audit


def _local_analysis_fallback(briefing: dict[str, Any], error: Exception) -> dict[str, Any]:
    """Deterministic editable design when cloud AI is unavailable.

    This is deliberately conservative: it keeps the workflow moving but never labels
    itself as an AI analysis. The user can edit it and rerun AI later.
    """
    b={k:str(v or "").strip() for k,v in (briefing or {}).items()}
    goal=b.get("goal") or b.get("situation") or b.get("product_description") or "Nový výzkum"
    try:
        from dispozice import odvod_temata
        topics=odvod_temata(" ".join(b.values()))[:8]
    except Exception:
        topics=[]
    _audrec={"action":"advisory_only","source_mode":"population","dataset_id":"","dataset_name":"ČR 18+","builtin_subpanel":"","reason":"Cílovka se vybírá explicitně uživatelem; lokální DEBUG fallback ji nesmí měnit."}
    return {
        "title": (b.get("product_description") or goal)[:100],
        "problem_summary": goal,
        "decision_use": b.get("decision_use") or "Podpořit rozhodnutí popsané v briefu.",
        "objectives": ["Změřit hlavní outcome relevantní pro rozhodnutí.", "Zjistit důvody a bariéry odpovědi."],
        "research_questions": [f"Jaká je odpověď cílové skupiny na hlavní problém: {goal}?"],
        "hypotheses": [], "recommended_topics": topics, "tracked_sets": [],
        "non_object_measures": [
            {"name":"hlavní outcome","reason":"Přímo odpovídá rozhodnutí; není mapovým objektem.","question_type":"vyber/skala"},
            {"name":"důvod odpovědi","reason":"Vysvětluje mechanismus výsledku.","question_type":"otevrena"},
        ],
        "audience_recommendation": {
            "strategy":"filters" if _audrec.get("builtin_subpanel") else "population",
            "description":_audrec.get("dataset_name") or "ČR 18+",
            "reason":_audrec.get("reason") or "Bezpečný výchozí rámec populace.",
            "builtin_subpanel":_audrec.get("builtin_subpanel") or "",
            "source_mode":_audrec.get("source_mode") or "population",
            "dataset_id":_audrec.get("dataset_id") or "",
            "action":_audrec.get("action") or "population",
            "support":_audrec.get("support"),
        },
        "complexity":"short","estimated_minutes":4,
        "method_reason":"Lokální nouzový návrh bez cloud AI; slouží jen jako editovatelný základ.",
        "questions_for_user": [], "ready_for_questionnaire": True,
        "tracked_set_fallback_used": False, "tracked_set_fallback_reason":"",
        "no_tracked_set_reason":"Lokální fallback nevyrábí objektovou baterii bez věcné opory.",
        "_ai": {"provider":"local_fallback","fallback_used":True,"error":str(error)[:500]},
    }

def _ensure_local_questions(project: dict[str, Any], briefing: dict[str, Any]) -> dict[str, Any]:
    p=normalize_project(project)
    if any(sec.get("type")=="questions" and sec.get("questions") for sec in p.get("sections",[])):
        return p
    product=str((briefing or {}).get("product_description") or (briefing or {}).get("goal") or "toto téma").strip()
    qs=[
        {"id":"q_relevance","text":f"Nakolik je pro vás {product} osobně relevantní?","typ":"skala","skala":[1,7],"popisky_skaly":["vůbec","velmi"],"povolit_nevim":True,"topics":[]},
        {"id":"q_consider","text":f"Jak pravděpodobné je, že byste {product} zvažoval/a?","typ":"vyber","kategorie":["Rozhodně ano","Spíše ano","Spíše ne","Rozhodně ne"],"povolit_nevim":True,"topics":[]},
        {"id":"q_why","text":"Co je hlavní důvod vaší předchozí odpovědi?","typ":"otevrena","max_slov":35,"povolit_nevim":False,"topics":[]},
    ]
    p.setdefault("sections",[]).insert(0,{"id":"local_questions","type":"questions","title":"Základní otázky — upravte podle briefu","purpose":"Lokální fallback při nedostupném AI provideru.","questions":qs,"metadata":{"local_fallback":True}})
    return normalize_project(p)


def analyze_research(briefing: dict[str, Any], *, model: str = "sonnet", provider: str | None = None, fast: bool = False) -> dict[str, Any]:
    raw_brief = dict(briefing or {})
    current_slots = dict(raw_brief.get("study_config") or {}) if isinstance(raw_brief.get("study_config"), dict) else {}
    b = {k: str(v or "").strip() for k, v in raw_brief.items() if k != "study_config"}
    goal = b.get("goal") or b.get("situation") or b.get("product_description")
    if not goal:
        raise ValueError("Nejdřív stručně popište, co řešíte a co chcete zjistit.")
    intake = {'study_type':'custom','study_config':{},'questions_for_user':[],'missing_slots':[]}
    # The first brief analysis is intentionally small and fast. Audience selection is
    # a separate explicit user step, so this AI action must never silently switch the
    # project to a built-in/special audience or ship large internal panel catalogues
    # into the prompt. That both slowed Claude Code down and caused stale
    # ``builtin_special:*`` IDs to leak into scenarios.
    _audrec = {
        "action": "advisory_only", "source_mode": "population", "dataset_id": "",
        "dataset_name": "ČR 18+", "builtin_subpanel": "",
        "reason": "Cílovka se vybírá explicitně v kroku Koho se ptát.", "support": None,
    }
    prompt = ("ZADÁNÍ UŽIVATELE — BRIEF JE PRIMÁRNÍ AUTORITA:\n" + json.dumps(b, ensure_ascii=False, indent=2) +
              "\n\nÚKOL: rychle pochop problém a rozhodnutí, navrhni cíle/RQ/hypotézy a případné sledované sady. "
              "Cílovku zde pouze POPIŠ slovně; NEVYBÍREJ dataset, special audience ani interní panel. "
              "Ptej se jen na informace, které materiálně mění design. Deep Research se spouští až později explicitně. "
              "Nevnášej nesouvisející produkty, study routery ani příklady, které uživatel neuvedl.")
    tool = _fast_analysis_tool() if fast else _analysis_tool()
    max_out = 1800 if fast else 3200
    try:
        raw, ai_audit = _structured_with_fallback(system=ANALYSIS_SYSTEM, prompt=prompt, tool=tool, model=model, max_tokens=max_out, provider=provider, interactive=fast, max_turns=(2 if fast else 8))
        raw = _sanitize_ai_tree(raw)
    except Exception as exc:
        from ai_execution_context import is_cancel_exception
        if is_cancel_exception(exc):
            raise
        # The first screen is intentionally resilient to structured-output quirks
        # of different Claude Code builds. Retry ONCE through the SAME Claude Code
        # subscription as plain text + JSON parsing. This is not a local/provider fallback.
        if str(provider or "").strip().lower()=="claude_code_subscription":
            try:
                raw,ai_audit=_fast_claude_text_recovery(system=ANALYSIS_SYSTEM,prompt=prompt,tool=tool,model=model,first_error=exc)
                raw=_sanitize_ai_tree(raw)
            except Exception as recovery_exc:
                from ai_execution_context import is_cancel_exception
                if is_cancel_exception(recovery_exc):
                    raise
                raise RuntimeError(f"RESEARCH_DESIGN_AI_FAILED: structured={exc}; prompt_json_recovery={recovery_exc}") from recovery_exc
        # LIVE/product design is fail-visible. A deterministic local scaffold is
        # available only as an explicit developer/debug opt-in; it must never
        # masquerade as a completed AI research design.
        elif str(os.environ.get("NPC_ALLOW_LOCAL_DESIGN_FALLBACK", "")).strip().lower() not in {"1","true","yes","on"}:
            raise RuntimeError(f"RESEARCH_DESIGN_AI_FAILED: {exc}") from exc
        else:
            fb = _local_analysis_fallback(briefing, exc)
            fb["study_type"] = "custom"
            fb["study_config"] = {}
            fb["instrument_library_version"] = library_version()
            fb["audience_recommendation"] = {
                "strategy":"filters" if _audrec.get("builtin_subpanel") else "population",
                "description":_audrec.get("dataset_name") or "ČR 18+",
                "reason":_audrec.get("reason") or "",
                "builtin_subpanel":_audrec.get("builtin_subpanel") or "",
                "source_mode":_audrec.get("source_mode") or "population",
                "dataset_id":_audrec.get("dataset_id") or "",
                "action":_audrec.get("action") or "population",
                "support":_audrec.get("support"),
            }
            fb["questions_for_user"] = []
            fb["design_slot_questions"] = []
            fb["ready_for_questionnaire"] = False
            fb["local_fallback_requires_ai_rerun"] = True
            return fb
    tracked = []
    for i, s in enumerate(raw.get("tracked_sets") or [], 1):
        if not isinstance(s, dict):
            continue
        objs = list(dict.fromkeys(str(x).strip() for x in (s.get("objects") or []) if str(x).strip()))
        hard_min, hard_max, _recommended = tracked_set_limits("pozicni_mapa")
        if not hard_min <= len(objs) <= hard_max:
            continue
        typ = str(s.get("object_type") or "sledované položky").strip()
        q = str(s.get("object_question") or "Jak hodnotíte {object}?").strip()
        if "{object}" not in q:
            q = q.rstrip(" ?") + " {object}?"
        labs = [str(x).strip() for x in (s.get("scale_labels") or ["vůbec", "velmi"])][:2]
        if len(labs) != 2 or not all(labs):
            labs = ["vůbec", "velmi"]
        tracked.append({
            "id": f"tracked_{i}", "title": str(s.get("title") or typ).strip(), "object_type": typ,
            "purpose": str(s.get("purpose") or "").strip(), "objects": objs,
            "object_question": q, "scale_labels": labs,
            "familiarity_required": bool(s.get("familiarity_required", False)),
            "why_map": str(s.get("why_map") or "").strip(),
            "objects_are_suggested": bool(s.get("objects_are_suggested", True)),
        })
    # 10.12: no synthetic fallback battery. A tracked set is a research design choice,
    # not a schema tax. Empty tracked_sets is valid for studies where no natural
    # comparison battery exists; the questionnaire can still contain ordinary outcomes.
    fallback_used = False
    fallback_reason = ""
    no_tracked_reason = "" if tracked else (
        "Analýza nenašla přirozenou sledovanou sadu srovnatelných položek. "
        "Výzkum může pokračovat bez mapy; sadu lze kdykoli doplnit ručně nebo přes Claude."
    )
    aud = raw.get("audience_recommendation") or {}
    strategy = str(aud.get("strategy") or "population")
    if strategy not in {"population", "filters", "discover"}:
        strategy = "population"
    return {
        "title": str(raw.get("title") or "Nový výzkum").strip(),
        "problem_summary": str(raw.get("problem_summary") or "").strip(),
        "decision_use": str(raw.get("decision_use") or "").strip(),
        "objectives": [str(x).strip() for x in (raw.get("objectives") or []) if str(x).strip()][:12],
        "research_questions": [str(x).strip() for x in (raw.get("research_questions") or []) if str(x).strip()][:5],
        "hypotheses": [str(x).strip() for x in (raw.get("hypotheses") or []) if str(x).strip()][:12],
        "recommended_topics": [str(x).strip() for x in (raw.get("recommended_topics") or []) if str(x).strip()][:16],
        "tracked_sets": tracked,
        "non_object_measures": [x for x in (raw.get("non_object_measures") or []) if isinstance(x, dict) and str(x.get("name") or "").strip()][:20],
        "audience_recommendation": {
            "strategy": "population",
            "description": str(aud.get("description") or "Cílovku vyberte v kroku Koho se ptát").strip(),
            "reason": str(aud.get("reason") or _audrec.get("reason") or "").strip(),
            "builtin_subpanel": "", "source_mode": "population", "dataset_id": "",
            "action": "advisory_only", "support": None,
        },
        "complexity": str(raw.get("complexity") or "standard"),
        "estimated_minutes": raw.get("estimated_minutes"),
        "method_reason": str(raw.get("method_reason") or "").strip(),
        "questions_for_user": list(dict.fromkeys([str(x).strip() for x in (raw.get("questions_for_user") or []) if str(x).strip()]))[:10],
        "design_slot_questions": [],
        "study_type": "custom",
        "study_config": {},
        "instrument_library_version": library_version(),
        "ready_for_questionnaire": bool(raw.get("ready_for_questionnaire", True)),
        "tracked_set_fallback_used": fallback_used,
        "tracked_set_fallback_reason": fallback_reason,
        "no_tracked_set_reason": no_tracked_reason,
        "_ai": ai_audit,
    }


def analysis_to_project_skeleton(analysis: dict[str, Any], briefing: dict[str, Any], *, n: int = 300) -> dict[str, Any]:
    p = empty_project(title=str(analysis.get("title") or "Nový výzkum"), goal=str(analysis.get("problem_summary") or ""), n=n)
    p["decision_use"] = str(analysis.get("decision_use") or "")
    p["study_type"] = str(analysis.get("study_type") or "custom")
    p["study_config"] = dict(analysis.get("study_config") or {})
    p["instrument_library"] = {"version": analysis.get("instrument_library_version") or library_version(),
                               "missing_slots": [x.get("slot") for x in (analysis.get("design_slot_questions") or []) if x.get("slot")],
                               "skipped_instruments": []}
    p["briefing"].update({
        "product_description": str((briefing or {}).get("product_description") or ""),
        "situation": str((briefing or {}).get("situation") or ""),
        "what_is_known": str((briefing or {}).get("what_is_known") or ""),
        "constraints": str((briefing or {}).get("constraints") or ""),
    })
    p["research_plan"] = {
        "status": "analyzed",
        "problem_summary": str(analysis.get("problem_summary") or ""),
        "objectives": analysis.get("objectives") or [],
        "research_questions": analysis.get("research_questions") or analysis.get("objectives") or [],
        "hypotheses": analysis.get("hypotheses") or [],
        "recommended_topics": analysis.get("recommended_topics") or [],
        "non_object_measures": analysis.get("non_object_measures") or [],
        "questions_for_user": analysis.get("questions_for_user") or [],
        "complexity": analysis.get("complexity") or "standard", "estimated_minutes": analysis.get("estimated_minutes"),
        "method_reason": analysis.get("method_reason") or "",
    }
    aud = analysis.get("audience_recommendation") or {}
    p["audience"].update({"strategy": aud.get("strategy") or "population", "description": aud.get("description") or "ČR 18+",
                          "product_description": p["briefing"]["product_description"]})
    _src=str(aud.get("source_mode") or "population").strip().lower()
    _dsid=str(aud.get("dataset_id") or "").strip()
    if _src in {"customer","special_audience"} and _dsid:
        p["audience"].update({"source_mode":_src,"dataset_id":_dsid,"dataset_name":aud.get("description") or "Uložená audience",
                              "builtin_subpanel":"","strategy":"population","filters":{},"audience_recommendation":aud})
    _action=str(aud.get("action") or "population")
    _sp=get_subpanel(str(aud.get("builtin_subpanel") or "").strip()) if _src=="population" and _action in {"use_builtin_subpanel","builtin_with_warning"} else None
    if _sp:
        p["audience"].update({"source_mode":"population","strategy":"filters","builtin_subpanel":_sp["key"],
                              "dataset_name":_sp.get("name") or p["audience"].get("dataset_name"),
                              "description":_sp.get("description") or _sp.get("name") or p["audience"].get("description"),
                              "filters":runtime_filters(_sp),"subpanel_status":_sp.get("status","ready"),
                              "support_tier":_sp.get("support_tier",""),"support_summary":dict(aud.get("support") or {}),"audience_recommendation":aud})
    elif aud:
        p["audience"]["audience_recommendation"]=dict(aud)
    standard = {"sections": [], "library_version": library_version(), "missing_slots": [], "skipped": []}
    p["instrument_library"].update({"version": standard["library_version"], "missing_slots": [], "skipped_instruments": []})
    tracked_sections = [{
        "id": s["id"], "type": "object_battery", "title": s["title"], "purpose": s["purpose"],
        "object_family": s["object_type"], "object_type": s["object_type"], "objects": s["objects"],
        "object_question": s["object_question"], "scale_labels": s["scale_labels"],
        "familiarity_required": s["familiarity_required"], "output_type": "pozicni_mapa", "visualize": True,
        "metadata": {"designer_generated": True, "why_map": s.get("why_map", ""), "objects_are_suggested": s.get("objects_are_suggested", True),
                     "fallback_generated": bool(s.get("fallback_generated", False))},
    } for s in analysis.get("tracked_sets") or []]
    p["sections"] = standard["sections"] + tracked_sections
    return normalize_project(p)



def _restore_approved_tracked_sets(project: dict[str, Any], approved: dict[str, Any]) -> dict[str, Any]:
    """Fail-safe: questionnaire drafting may refine a set, but must not silently delete it."""
    p = normalize_project(project)
    existing = [x for x in p.get("sections", []) if x.get("type") == "object_battery"]
    def _set_key(x):
        return (str(x.get("id") or "").strip().lower(),
                str(x.get("title") or "").strip().lower(),
                str(x.get("object_family") or x.get("object_type") or "").strip().lower())
    keys = {_set_key(x) for x in existing}
    ids = {str(x.get("id") or "").strip().lower() for x in existing}
    for sec in normalize_project(approved).get("sections", []):
        if sec.get("type") != "object_battery":
            continue
        key = _set_key(sec)
        sid = str(sec.get("id") or "").strip().lower()
        same_title_type = any((k[1], k[2]) == (key[1], key[2]) for k in keys)
        if sid not in ids and not same_title_type:
            p["sections"].append(sec)
            keys.add(key); ids.add(sid)
    # No battery is a valid outcome when the approved design has none.
    return normalize_project(p)

def build_questionnaire(analysis: dict[str, Any], briefing: dict[str, Any], *, n: int = 300,
                        current_project: dict[str, Any] | None = None, model: str = "sonnet", provider: str | None = None) -> dict[str, Any]:
    base = normalize_project(current_project or analysis_to_project_skeleton(analysis, briefing, n=n))
    prompt = (
        "SCHVÁLENÁ ANALÝZA:\n" + json.dumps(analysis, ensure_ascii=False, indent=2) +
        "\n\nZADÁNÍ:\n" + json.dumps(briefing or {}, ensure_ascii=False, indent=2) +
        "\n\nVÝCHOZÍ PROJEKT (sledované sady mohou být prázdné):\n" + json.dumps(base, ensure_ascii=False, indent=2) +
        "\n\nDoplň jen klientsky specifické otázkové bloky a vrať kompletní použitelný projekt. Sekce s metadata.standard_instrument=true jsou zamčené kanonické instrumenty: nemaž je ani nepřepisuj. Zachovej všechny schválené sledované sady; pokud schválená analýza žádnou nemá, žádnou uměle nevyráběj."
    )
    tool = _project_tool()
    try:
        raw, ai_audit = _structured_with_fallback(system=BUILD_SYSTEM, prompt=prompt, tool=tool, model=model, max_tokens=8500, provider=provider)
        raw = _sanitize_ai_tree(raw)
        p = normalize_project(raw.get("project") or base)
    except Exception as exc:
        if str(os.environ.get("NPC_ALLOW_LOCAL_DESIGN_FALLBACK", "")).strip().lower() not in {"1","true","yes","on"}:
            raise RuntimeError(f"QUESTIONNAIRE_DESIGN_AI_FAILED: {exc}") from exc
        p = _ensure_local_questions(base, briefing)
        raw = {"message":"Lokální DEBUG základ dotazníku. Před LIVE během je nutné znovu spustit AI návrh."}
        ai_audit = {"provider":"local_fallback","fallback_used":True,"error":str(exc)[:500],"invalid_for_live":True}

    # The approved analysis is authoritative for tracked sets. Claude may refine wording,
    # but it must not silently drop an entire measurement set while drafting the questionnaire.
    # Match first by stable id, then by normalized title/object type. Missing sets are restored
    # from the deterministic skeleton. This guarantees that a research plan with e.g. media +
    # emotions remains one project with both independent maps.
    approved = analysis_to_project_skeleton(analysis, briefing, n=n)
    p = _restore_approved_tracked_sets(p, approved)
    # Standard instrument library is authoritative as well. AI may add custom blocks
    # but cannot silently mutate/delete canonical measurement instruments.
    p["study_type"] = str(analysis.get("study_type") or p.get("study_type") or "custom")
    p["study_config"] = dict(analysis.get("study_config") or p.get("study_config") or {})
    p = normalize_project(merge_standard_sections(p))

    # The analysis is authoritative for the research-plan explanation even if Claude omits it from the tool payload.
    p["research_plan"].update({
        "status": "questionnaire_ready",
        "problem_summary": analysis.get("problem_summary") or p["research_plan"]["problem_summary"],
        "objectives": analysis.get("objectives") or p["research_plan"]["objectives"],
        "research_questions": analysis.get("research_questions") or p["research_plan"].get("research_questions") or analysis.get("objectives") or [],
        "hypotheses": analysis.get("hypotheses") or p["research_plan"]["hypotheses"],
        "recommended_topics": analysis.get("recommended_topics") or p["research_plan"]["recommended_topics"],
        "non_object_measures": analysis.get("non_object_measures") or p["research_plan"]["non_object_measures"],
        "complexity": analysis.get("complexity") or p["research_plan"]["complexity"],
        "estimated_minutes": analysis.get("estimated_minutes"),
        "method_reason": analysis.get("method_reason") or p["research_plan"]["method_reason"],
    })
    return {"message": str(raw.get("message") or "Dotazník je připraven k úpravám."), "project": normalize_project(p), "_ai": ai_audit}


def design_research(zadani: str, *, cilova_skupina: str = "", n: int = 500, model: str = "sonnet", provider: str | None = None) -> dict[str, Any]:
    """Compatibility helper: analyze first and build only if no material follow-up is required."""
    briefing = {"goal": str(zadani or "").strip(), "situation": str(zadani or "").strip(), "product_description": "", "what_is_known": "", "constraints": ""}
    analysis = analyze_research(briefing, model=model, provider=provider)
    if cilova_skupina:
        analysis["audience_recommendation"] = {"strategy": "filters", "description": cilova_skupina, "reason": "Cílová skupina byla zadána uživatelem."}
    out = {"analysis": analysis, "ready_to_run": False, "questions_for_user": analysis.get("questions_for_user") or []}
    if analysis.get("ready_for_questionnaire"):
        built = build_questionnaire(analysis, briefing, n=n, model=model, provider=provider)
        out.update(built)
    return out

# ---------------------------------------------------------------------------
# Backward-compatible 10.9/10.10 plan normalizer. Kept so saved plans and older
# automation/tests continue to work; the 10.11 UI no longer exposes this binary
# standard_survey vs object_study product split.
def normalize_plan(raw: dict[str, Any], *, n: int = 500, zadani: str = "") -> dict[str, Any]:
    from navrh import _validuj as validate_standard_brief
    from study_contract import StudySpec
    if not isinstance(raw, dict):
        raise ValueError("Výzkumný asistent nevrátil strukturovaný plán.")
    kind = str(raw.get("plan_kind", "")).strip()
    if kind not in {"standard_survey", "object_study"}:
        raise ValueError("Výzkumný asistent neurčil platný typ výzkumu.")
    out = {
        "plan_kind": kind,
        "title": str(raw.get("title") or "Nový výzkum").strip(),
        "research_question": str(raw.get("research_question") or zadani).strip(),
        "decision_use": str(raw.get("decision_use") or "").strip(),
        "method_reason": str(raw.get("method_reason") or "").strip(),
        "audience_description": str(raw.get("audience_description") or "ČR 18+").strip(),
        "ready_to_run": bool(raw.get("ready_to_run", True)),
        "missing_inputs": [str(x).strip() for x in (raw.get("missing_inputs") or []) if str(x).strip()],
        "user_checks": [str(x).strip() for x in (raw.get("user_checks") or []) if str(x).strip()],
        "n": int(n), "source_request": zadani,
    }
    if kind == "standard_survey":
        brief = validate_standard_brief({"nazev": out["title"], "otazky": list(raw.get("standard_questions") or [])})
        qs = brief["otazky"]
        if not qs: raise ValueError("Pro standardní průzkum nevznikla žádná použitelná otázka.")
        out["brief"] = {
            "nazev": out["title"], "n": int(n), "mode": "dry", "seed": 42,
            "model": resolve_model("sonnet"), "response_mode": "probability", "persona_mode": "calibrated",
            "filtry": {}, "otazky": qs, "research_context": {"enabled": False},
            "segment": {"mode": "none"}, "use_case": "internal", "allow_own_estimates": False,
            "_zadani_klienta": zadani,
        }
        out["questionnaire_preview"] = qs
        return out
    s = raw.get("study") or {}
    family = str(s.get("object_family") or "").strip()
    objects = list(dict.fromkeys(str(x).strip() for x in (s.get("objects") or []) if str(x).strip()))
    if not family: raise ValueError("Objektová studie nemá object_family.")
    output_type = str(s.get("output_type") or "pozicni_mapa")
    hard_min, hard_max, _recommended = tracked_set_limits(output_type)
    if not hard_min <= len(objects) <= hard_max:
        raise ValueError(f"Objektová studie pro {output_type} potřebuje {hard_min}–{hard_max} navržených položek stejného typu.")
    metadata = {"designer_generated": True, "objects_are_suggested": bool(s.get("objects_are_suggested", False))}
    _warning = tracked_set_warning(len(objects), output_type)
    if _warning: metadata["design_warning"] = _warning
    if s.get("price_bands"): metadata["price_bands"] = [str(x).strip() for x in s.get("price_bands") if str(x).strip()]
    if s.get("focal_object"): metadata["focal_object"] = str(s["focal_object"]).strip()
    if s.get("test_object"): metadata["test_object"] = str(s["test_object"]).strip()
    chars=[]
    for x in s.get("characteristics") or []:
        if not isinstance(x,dict): continue
        kind2=str(x.get("kind") or "").strip()
        if kind2 not in {"attitude","frequency","binary","ordinal","nps"}: continue
        row={"name":str(x.get("name") or "").strip(),"kind":kind2,"text":str(x.get("text") or "").strip(),
             "values":[str(v).strip() for v in (x.get("values") or []) if str(v).strip()],
             "topics":[str(v).strip() for v in (x.get("topics") or []) if str(v).strip()][:4],
             "scale":[int(v) for v in (x.get("scale") or [])][:2]}
        if row["name"] and row["text"]: chars.append(row)
    spec_dict = {
        "name": out["title"], "research_question": out["research_question"],
        "output_type": output_type,
        "objects": [{"label": x, "family": family} for x in objects], "object_family": family,
        "object_question": str(s.get("object_question") or "Jaký je Váš vztah k položce {object}?").strip(),
        "object_scale_labels": tuple((s.get("scale_labels") or ["velmi negativní", "velmi pozitivní"])[:2]),
        "familiarity_required": bool(s.get("familiarity_required", False)), "characteristics": chars,
        "n": int(n), "metadata": metadata,
    }
    try: spec=StudySpec(**spec_dict)
    except ValueError as exc:
        if spec_dict["output_type"]=="test_konceptu" and "price_bands" in str(exc):
            out["ready_to_run"]=False
            if not any("cen" in x.lower() for x in out["missing_inputs"]): out["missing_inputs"].append("Doplňte konkrétní cenová pásma pro test konceptu.")
            tmp=dict(spec_dict);tmp["output_type"]="pozicni_mapa";spec=StudySpec(**tmp)
        else: raise
    out["study_spec"]=spec_dict;out["questionnaire_preview"]=spec.questionnaire();out["objects"]=objects;out["object_family"]=family;out["objects_are_suggested"]=bool(s.get("objects_are_suggested",False))
    return out
