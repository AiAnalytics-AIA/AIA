"""Optional legacy/template study hints. Not used as authority in the production brief-first workflow."""
from __future__ import annotations
from typing import Any
import re
from instrument_library import study_types, missing_slots

STUDY_LABELS={k:v.get("label",k) for k,v in study_types().items()}

KEYWORDS = {}  # Production is brief-first; no deterministic study router.

def classify_study(briefing: dict[str,Any] | str) -> dict[str,Any]:
    """Compatibility shim. Production never infers a study type from keywords.

    Explicit templates may still call ``intake(..., study_type=...)``. When no
    template is explicitly selected, the only safe classification is ``custom``.
    """
    return {"study_type":"custom","label":STUDY_LABELS.get("custom","Vlastní výzkum"),
            "scores":{},"confidence":"brief_first_no_router"}


def _first_label(text: str, limit: int=120) -> str:
    t=str(text or "").strip().split("\n")[0].strip()
    return t.split(".")[0][:limit].strip()


def infer_slots(study_type: str, briefing: dict[str,Any], current: dict[str,Any] | None=None) -> dict[str,Any]:
    slots=dict(current or {})
    product=str(briefing.get("product_description") or "").strip()
    goal=str(briefing.get("goal") or "").strip()
    situation=str(briefing.get("situation") or briefing.get("context") or "").strip()
    label=_first_label(product)
    if study_type=="brand" and label: slots.setdefault("brand_name",label)
    if study_type=="concept_test" and product:
        slots.setdefault("concept_description",product); slots.setdefault("concept_name",label or "Testovaný koncept")
    if study_type in {"product_test","pricing"} and label: slots.setdefault("product_name",label)
    if study_type in {"satisfaction","customer_experience"} and label: slots.setdefault("subject_name",label)
    if study_type=="communications_test" and label: slots.setdefault("stimulus_name",label)
    if study_type=="policy_test" and (product or goal): slots.setdefault("policy_statement",product or goal)
    if study_type=="employee" and label: slots.setdefault("organization_name",label)
    if study_type=="b2b_decision" and label: slots.setdefault("category_name",label)
    if study_type=="segmentation" and goal: slots.setdefault("segmentation_goal",goal)
    if study_type=="scenario":
        if goal: slots.setdefault("scenario_event",goal)
        elif situation: slots.setdefault("scenario_event",situation)
    return slots


def followup_questions(study_type: str, slots: dict[str,Any]) -> list[dict[str,Any]]:
    labels={
        "policy_statement":("Jaké přesné opatření nebo návrh mají respondenti hodnotit?","long_text"),
        "brand_name":("Jak se přesně jmenuje značka, kterou zkoumáme?","text"),
        "brand_list":("Které značky mají být ve srovnání?","list"),
        "brand_attribute_list":("Které atributy značky mají respondenti hodnotit?","list"),
        "category_name":("Jak se jmenuje produktová / nákupní kategorie?","text"),
        "concept_name":("Jak se má testovaný koncept pracovně jmenovat?","text"),
        "concept_description":("Jaký přesný popis konceptu má respondent vidět?","long_text"),
        "product_name":("Jak se jmenuje produkt nebo služba, kterou testujeme?","text"),
        "price_point":("Jakou konkrétní cenu chcete otestovat? Uveďte částku i měnu.","text"),
        "stimulus_name":("Jak se má testovaný reklamní / komunikační materiál označovat?","text"),
        "subject_name":("S čím přesně mají respondenti hodnotit svoji spokojenost nebo zkušenost?","text"),
        "organization_name":("Jak se jmenuje organizace / zaměstnavatel, kterého se interní výzkum týká?","text"),
        "supplier_name":("Kterého dodavatele mají B2B respondenti hodnotit?","text"),
        "channel_list":("Které mediální / informační kanály chcete měřit?","list"),
        "experience_attribute_list":("Které atributy zákaznické zkušenosti mají být v baterii?","list"),
        "decision_criteria_list":("Která kritéria výběru dodavatele mají být v baterii?","list"),
        "need_list":("Které potřeby chcete v segmentaci porovnávat?","list"),
        "barrier_list":("Které bariéry chcete v segmentaci porovnávat?","list"),
        "segmentation_goal":("Podle jakého rozhodnutí nebo cíle má být segmentace užitečná?","long_text"),
        "scenario_baseline":("Jaký je výchozí stav, proti kterému máme scénář porovnat?","long_text"),
        "scenario_event":("Jaká přesná událost nebo změna se má ve scénáři stát?","long_text"),
    }
    return [{"slot":k,"question":labels.get(k,(f"Doplňte {k}","text"))[0],"input_type":labels.get(k,("","text"))[1]} for k in missing_slots(study_type,slots)][:5]


def intake(briefing: dict[str,Any], *, study_type: str|None=None, current_slots: dict[str,Any]|None=None) -> dict[str,Any]:
    cls=classify_study(briefing) if not study_type else {"study_type":study_type,"label":STUDY_LABELS.get(study_type,study_type),"scores":{},"confidence":"explicit"}
    st=cls["study_type"]
    slots=infer_slots(st,briefing,current_slots)
    qs=followup_questions(st,slots)
    return {**cls,"study_config":slots,"missing_slots":[q["slot"] for q in qs],"questions_for_user":qs,"ready_for_standard_instruments":not qs}
