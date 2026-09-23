from __future__ import annotations
import re,unicodedata
from typing import Any
from population_subpanels import list_subpanels,list_special_panels,project_patch as builtin_patch,special_project_patch

def _norm(s):
 s=str(s or "").lower().replace("–","-");return " ".join("".join(c for c in unicodedata.normalize("NFKD",s) if not unicodedata.combining(c)).split())
def _text(b):
 if isinstance(b,str):return _norm(b)
 return _norm(" ".join(str(v) for v in (b or {}).values() if isinstance(v,(str,int,float))))
BUILTIN={
"medical_doctors":["lekar","doctor","physician"],"health_professionals":["zdravotnik","sestra","health professional"],"teachers":["ucitel","pedagog"],"ict_specialists":["ict specialist","it specialist","programator","developer"],"managers":["manazer","vedouci pracovnik","executive"],"students":["student"],"young_18_29":["mladi","gen z","18-29"],"seniors_80_plus":["80+","nad 80"],"seniors_66_79":["senior","duchodce"],"parents":["rodic","rodice"],"employed":["pracujici","zamestnani"],"unemployed":["nezamestnany"],"service_sales":["prodejce","retail","sluzby a prodej"],"science_engineering":["inzenyr","vedec","engineer"],"business_admin_specialists":["business specialist","administrativni specialista"]}
SPECIAL={
"construction_ecosystem":["stavebnictvi","stavebni material","stavari","stavebni firmy"],"real_estate_professionals":["realitni makler","reality","real estate","nemovitostni profesional"],"healthcare_material_ecosystem":["zdravotnicky material","medical devices","zdravotnicke pomucky","zdrav material"],"healthcare_clinical_professionals":["klinicti zdravotnici","clinical healthcare"],"procurement_buyers":["nakupci","procurement","tendr","verejne zakazky"],"foreign_ukrainian":["ukrajinci","ukrajinsti obcane","ukrajinsky"],"foreign_slovak":["slovaci","slovensti obcane"],"foreign_vietnamese":["vietnamci","vietnamsti obcane"],"foreign_russian":["rusove","rusti obcane"],"foreigners_overall_top4_proxy":["cizinci","zahranicni obcane"],"minority_moravian":["moravska narodnost","moravane"],"minority_silesian":["slezska narodnost","slezane"],"minority_roma_selfdeclared":["romska narodnost","romove"],"minority_polish":["polska mensina","polaci"],"minority_german":["nemecka mensina"],"minority_slovak_declared":["slovenska narodnost"],"minority_ukrainian_declared":["ukrajinska narodnost"],"minority_vietnamese_declared":["vietnamska narodnost"]}
def _registered(text,audiences):
 out=[];words={w for w in re.findall(r"[a-z0-9]{4,}",text) if w not in {"vyzkum","panel","ceske","respondent"}}
 for a in audiences or []:
  hay=_norm(" ".join(str(a.get(k) or "") for k in ("name","description","population_definition","type")));score=sum(w in hay for w in words)
  if score:out.append({"audience_id":a.get("audience_id"),"name":a.get("name"),"type":a.get("type"),"rows":a.get("rows"),"score":score})
 return sorted(out,key=lambda x:(-x["score"],-int(x.get("rows") or 0)))
def recommend(briefing:dict[str,Any]|str,*,audiences=None,requested_n=300):
 text=_text(briefing);reg=_registered(text,audiences)
 if reg and reg[0]["score"]>=2:
  a=reg[0];return {"action":"use_registered_audience","source_mode":a.get("type") or "special_audience","dataset_id":a.get("audience_id") or "","dataset_name":a.get("name") or "","confidence":.95,"reason":"Uložený respondent-level dataset je přesnější než vestavěná proxy.","support":a}
 bys={x.get("key"):x for x in list_special_panels()}
 for key,kws in SPECIAL.items():
  hits=[k for k in kws if _norm(k) in text]
  if hits and key in bys:
   sp=bys[key];support=str(sp.get("support") or "");rows=int(sp.get("rows") or 0);base={"source_mode":"special_audience","dataset_id":"builtin_special:"+key,"dataset_name":sp.get("name") or key,"special_panel_key":key,"confidence":.94,"matched_keywords":hits,"support":sp}
   if support in {"STRUCTURAL_ONLY","STRUCTURAL_ONLY_TOP4","EXPERIMENTAL_LOW_SUPPORT"} or rows<30:
    return {**base,"action":"builtin_special_with_warning","reason":"Existuje pouze strukturální/nízkosupportová proxy. Pro ostrý claim preferujte skutečný Special Audience dataset."}
   return {**base,"action":"use_builtin_special_panel","reason":"Brief odpovídá interně dostupné special audience proxy; metodická omezení se kontrolují v preflightu."}
 by={x.get("key"):x for x in list_subpanels()}
 for key,kws in BUILTIN.items():
  hits=[k for k in kws if _norm(k) in text]
  if hits and key in by:
   sp=by[key];tier=str(sp.get("support_tier") or "");base={"source_mode":"population","dataset_id":"","dataset_name":sp.get("name"),"builtin_subpanel":key,"confidence":.9,"matched_keywords":hits,"support":sp}
   if tier=="EXPERIMENTAL_LOW_SUPPORT":return {**base,"action":"recommend_special_audience","reason":"Vestavěná proxy má experimentální donor support; pro ostrý research použijte Special Audience."}
   if tier=="LIMITED" and requested_n>min(int(sp.get("rows") or 0),max(80,int(float(sp.get("effective_core_donors") or 0)*3))):return {**base,"action":"builtin_with_warning","reason":"Vestavěný panel má omezený donor support; snižte N nebo použijte Special Audience."}
   return {**base,"action":"use_builtin_subpanel","reason":"Brief odpovídá vestavěnému populačnímu subpanelu."}
 return {"action":"population","source_mode":"population","dataset_id":"","dataset_name":"ČR 18+","builtin_subpanel":"","confidence":.55,"reason":"Není bezpečně rozpoznána užší cílová skupina.","support":None,"alternatives":reg[:3]}
def project_patch(rec):
 a=rec.get("action")
 if a=="use_registered_audience":return {"source_mode":rec.get("source_mode") or "special_audience","dataset_id":rec.get("dataset_id") or "","dataset_name":rec.get("dataset_name") or "","builtin_subpanel":"","strategy":"population","description":rec.get("dataset_name") or "Uložená audience","filters":{},"audience_recommendation":rec}
 if rec.get("special_panel_key"):
  p=special_project_patch(rec["special_panel_key"]);p["audience_recommendation"]=rec;return p
 if rec.get("builtin_subpanel"):
  p=builtin_patch(rec["builtin_subpanel"]);p["audience_recommendation"]=rec;return p
 return {"source_mode":"population","dataset_id":"","dataset_name":"ČR 18+","builtin_subpanel":"","strategy":"population","description":"ČR 18+","filters":{},"audience_recommendation":rec}
