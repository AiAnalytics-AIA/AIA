"""Optional persistent Claude copilot for NPC Panel 10.12.

Claude is a research-design collaborator, not a required control surface. Users can
close the panel and edit everything manually. When used, Claude sees the current
single research project and can refine the problem framing, tracked sets and
questionnaire, but cannot start respondent runs by itself.
"""
from __future__ import annotations

from typing import Any
import json

from runtime_config import resolve_model
from anthropic_compat import create_message
from research_project import empty_project, normalize_project

SYSTEM = r"""Jsi Claude v roli seniorního českého research directora v NPC Panelu.
Uživatel nemusí znát výzkumnou metodiku. Mluv česky, prakticky a vysvětluj důvody.

Pracuješ nad JEDNÍM výzkumným projektem. Neexistuje samostatný produkt „Audience Lab“ ani
„Mapy“: cílovka, sledované sady, mapy a následné hledání ideální skupiny jsou součástí
jednoho výzkumného workflow.

Sekce projektu:
1. questions — běžné outcomes/screening/chování/cena/purchase intent/open-ended/profilování.
2. object_battery — SLEDOVANÁ SADA: srovnatelné položky stejného logického typu; 4-15 je doporučení, ne automatický důvod návrh zahodit,
   hodnocených stejnou otázkou/škálou. Typ může být cokoli smysluplného: značky, média
   (televize, internet, rádio...), emoce, atributy, vztahy k produktu, procesy, touchpointy,
   povolání, alternativy, koncepty, potřeby atd. Jeden výzkum může mít více různých sad a
   každá může mít vlastní mapu. Nikdy nemíchej nesrovnatelné typy uvnitř jedné sady.

VŽDY explicitně rozlišuj, co je sledovaný objekt a co není. Purchase intent, maximální cena,
věk, příjem, NPS, screening a jednorázový outcome typicky nejsou objekty mapy. Pokud uživatel
chce zkoumat více témat, rozděl je do logických bloků a více sledovaných sad — nevyber pouze jedno.

Familiarity není automatická. Použij ji jen když dává význam pro konkrétní položky (např. značky,
produkty, koncepty). Pro emoce, média, atributy nebo vztahové výroky ji obvykle nepotřebuješ.

Workflow uživatele:
- nejprve popis problému/produktu a rozhodnutí;
- volitelná Claude analýza a případné material follow-up otázky;
- návrh toho, co zkoumat, sledovaných sad a komplexnosti;
- dotazník;
- cílovka (celá ČR / vlastní filtr / širší vzorek a po běhu hledat ideální skupinu);
- persona a respondentní AI model;
- spuštění Bez AI (technická zkouška) nebo S AI (skutečná syntetická simulace);
- výsledky, mapy, externí ověření, případná transparentní kontextová kalibrace.

Pokud uživatel chce „najít ideální skupinu“, nejdříve musí být v projektu popsán produkt/téma a
co znamená úspěch. Typicky doporuč širší první vzorek a reverse discovery až z výsledků. Pokud
label pochází ze syntetických odpovědí, jde o explorativní segment C, ne o potvrzený tržní fakt.

Persona:
- produkce používá koherentní v15.2 personu: same-person core fakta + topic-relevantní whole-donor signály s provenance;
- demographics/core/full/none jsou diagnostická benchmarková ramena, ne běžná uživatelská volba;
- P_* overlay, HEXACO a široké full konstrukty nepovažuj za individuálně změřená fakta a nenavrhuj je jako automatické obohacení produkce.

Research Context je volitelný a nesmí silentně přepisovat panel ani výsledky. Externí post-run
ověření je jiná funkce a může porovnávat výsledek s publikovanou evidencí; případná úprava musí
zachovat původní NPC výsledek a auditovat zdroje.

Když uživatel chce změnu, navrhni aktualizovaný project, ale počítej s tím, že UI změny nejdřív
zobrazí jako návrh a uživatel je přijme nebo odmítne. Nikdy sám nespouštěj běh ani netvrď,
že změna už byla aplikována. Když se uživatel jen ptá, projekt může zůstat beze změny."""


def _question_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string"}, "text": {"type": "string"},
            "typ": {"type": "string", "enum": ["vyber", "multi", "skala", "otevrena"]},
            "kategorie": {"type": "array", "items": {"type": "string"}},
            "skala": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
            "popisky_skaly": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2},
            "povolit_nevim": {"type": "boolean"}, "max_slov": {"type": "integer"},
            "filtr": {"type": "string"}, "topics": {"type": "array", "items": {"type": "string"}},
            "metadata": {"type": "object"},
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
            "objects": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 40},
            "object_question": {"type": "string"},
            "scale_labels": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2},
            "familiarity_required": {"type": "boolean"},
            "output_type": {"type": "string", "enum": ["pozicni_mapa", "segmentace", "lovebrand", "test_konceptu"]},
            "visualize": {"type": "boolean"}, "metadata": {"type": "object"},
        },
        "required": ["type", "title"], "additionalProperties": False,
    }


def _tool_schema() -> dict[str, Any]:
    project = {
        "type": "object",
        "properties": {
            "schema_version": {"type": "integer"}, "title": {"type": "string"}, "goal": {"type": "string"},
            "decision_use": {"type": "string"},
            "briefing": {"type": "object", "properties": {
                "product_description": {"type": "string"}, "situation": {"type": "string"},
                "what_is_known": {"type": "string"}, "constraints": {"type": "string"},
            }, "additionalProperties": False},
            "research_plan": {"type": "object"},
            "n": {"type": "integer"},
            "persona_mode": {"type": "string", "enum": ["full", "demographics", "core", "none", "calibrated"]},
            "model": {"type": "string"}, "research_context": {"type": "boolean"},
            "audience": {"type": "object", "properties": {
                "strategy": {"type": "string", "enum": ["population", "filters", "discover"]},
                "description": {"type": "string"}, "filters": {"type": "object"}, "segment": {"type": "object"},
                "product_description": {"type": "string"}, "success_definition": {"type": "string"},
                "discovery_note": {"type": "string"},
            }, "additionalProperties": False},
            "sections": {"type": "array", "items": _section_schema()},
            "discovery": {"type": "object", "properties": {
                "enabled": {"type": "boolean"}, "question_id": {"type": "string"},
                "positive_answers": {"type": "array", "items": {"type": "string"}}, "min_positive": {"type": "integer"},
            }, "additionalProperties": False},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "goal", "n", "audience", "sections"], "additionalProperties": False,
    }
    return {
        "name": "submit_research_workspace",
        "description": "Return the current complete research project and a user-facing response.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "changes_summary": {"type": "array", "items": {"type": "string"}},
                "questions_for_user": {"type": "array", "items": {"type": "string"}},
                "project": project,
            },
            "required": ["message", "project"], "additionalProperties": False,
        },
    }



def _diff_paths(a: Any, b: Any, path: str = "") -> list[dict[str, Any]]:
    """Compact audit diff; UI can ask before applying Claude's proposed project."""
    out=[]
    if type(a) is not type(b):
        return [{"path":path or "/","op":"replace","before":a,"after":b}]
    if isinstance(a,dict):
        for k in sorted(set(a)|set(b)):
            q=(path+"/"+str(k)) if path else "/"+str(k)
            if k not in a: out.append({"path":q,"op":"add","after":b[k]})
            elif k not in b: out.append({"path":q,"op":"remove","before":a[k]})
            else: out.extend(_diff_paths(a[k],b[k],q))
        return out
    if isinstance(a,list):
        if a!=b: out.append({"path":path or "/","op":"replace_list","before_count":len(a),"after_count":len(b)})
        return out
    if a!=b: out.append({"path":path or "/","op":"replace","before":a,"after":b})
    return out

def _compact_project_for_ai(project: dict[str, Any]) -> dict[str, Any]:
    """Small design context for the interactive partner.

    Full Evidence Packs and runtime/audit state can be hundreds of KB and are not
    needed for conversational design. Keep only design-relevant fields and a short
    evidence digest.
    """
    p=normalize_project(project)
    research=p.get("pre_research") or {}
    evidence=[{k:x.get(k) for k in ("claim","source_title","topics")} for x in (research.get("accepted") or [])[:8] if isinstance(x,dict)]
    return {
        "title":p.get("title"),"goal":p.get("goal"),"decision_use":p.get("decision_use"),
        "briefing":p.get("briefing"),"research_plan":p.get("research_plan"),"n":p.get("n"),
        "persona_mode":p.get("persona_mode"),"persona_dimensions":p.get("persona_dimensions"),
        "model":p.get("model"),"audience":p.get("audience"),"sections":p.get("sections"),
        "discovery":p.get("discovery"),"research_evidence_digest":evidence,
    }

def _merge_design_proposal(current: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Apply only design fields the copilot schema is allowed to change.

    Provider/budget/Evidence Pack and the authoritative audience source/dataset are
    protected. The old full-project replacement could silently erase these fields.
    """
    from copy import deepcopy
    merged=deepcopy(current)
    for key in ("title","goal","decision_use","briefing","research_plan","n","persona_mode","model","research_context","sections","discovery","notes"):
        if key in proposal:
            merged[key]=deepcopy(proposal[key])
    if isinstance(proposal.get("audience"),dict):
        merged.setdefault("audience",{})
        for key in ("strategy","description","filters","segment","product_description","success_definition","discovery_note"):
            if key in proposal["audience"]:
                merged["audience"][key]=deepcopy(proposal["audience"][key])
    return normalize_project(merged)

def chat(message: str, *, project: dict[str, Any] | None = None,
         history: list[dict[str, str]] | None = None, model: str = "sonnet", provider: str | None = None) -> dict[str, Any]:
    message = str(message or "").strip()
    if not message:
        raise ValueError("Napiš Claudovi, co chceš udělat.")
    current = normalize_project(project or empty_project())
    safe_history = []
    for x in (history or [])[-8:]:
        role = str(x.get("role") or "")
        content = str(x.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            safe_history.append({"role": role, "content": content[:2500]})
    context = "AKTUÁLNÍ VÝZKUMNÝ PROJEKT — KOMPAKTNÍ DESIGN KONTEXT (JSON):\n" + json.dumps(_compact_project_for_ai(current), ensure_ascii=False, separators=(",",":")) + "\n\nNOVÁ ZPRÁVA UŽIVATELE:\n" + message
    tool = _tool_schema()
    # One routing path only. Anthropic is preferred; the router itself handles the
    # tool-use/JSON-contract retry on the globally selected provider, so a schema or model
    # incompatibility no longer looks like an AI outage.
    from ai_router import call_structured
    try:
        from provider_auth import get_ai_provider, normalize_ai_provider
        selected_provider=normalize_ai_provider(provider or (current.get("run_policy") or {}).get("provider") or get_ai_provider())
        rr = call_structured(system=SYSTEM, messages=safe_history + [{"role": "user", "content": context}],
                             schema=tool["input_schema"], schema_name=tool["name"], anthropic_model=model,
                             max_tokens=5000, prefer=selected_provider, openai_model=(model if selected_provider=="openai" else None), allow_fallback=False)
        raw = dict(rr["data"])
        ai_audit = {"provider": rr.get("provider"), "model": rr.get("model"), "mode": rr.get("mode"),
                    "fallback_used": bool(rr.get("fallback_used")), "attempts": rr.get("attempts")}
    except Exception as exc:
        # The copilot must never block editing, but it must also never hide the
        # reason. The diagnosis names the failing provider and the next action.
        from provider_diagnostics import explain_router_failure
        try:
            selected_provider
        except NameError:
            from provider_auth import get_ai_provider, normalize_ai_provider
            selected_provider=normalize_ai_provider(provider or (current.get("run_policy") or {}).get("provider") or get_ai_provider())
        diag = explain_router_failure(exc, provider=selected_provider)
        return {"message": diag["message"],
                "changes_summary": [], "questions_for_user": [], "project": current, "proposed_project": current,
                "patches": [], "has_changes": False,
                "_ai": {"provider": selected_provider, "failed": True, "fallback_used": False, "kind": diag["kind"],
                        "detail": diag["detail"], "next_action": diag["next_action"]}}
    normalized = _merge_design_proposal(current, raw.get("project") or {})
    patches = _diff_paths(current, normalized)
    return {
        "message": str(raw.get("message") or "Připravil jsem návrh změn."),
        "changes_summary": [str(x) for x in (raw.get("changes_summary") or []) if str(x).strip()][:12],
        "questions_for_user": [str(x) for x in (raw.get("questions_for_user") or []) if str(x).strip()][:8],
        # Backward-compatible field plus explicit proposal contract. UI 10.12 does not
        # silently replace current project; it asks the user before applying.
        "project": normalized, "proposed_project": normalized, "patches": patches[:100],
        "has_changes": bool(patches),
        "_ai": ai_audit,
    }
