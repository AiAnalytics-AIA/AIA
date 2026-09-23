"""Deterministic factual-response layer for NPC Panel.

Facts already present in the panel must never be re-invented by an LLM.  This
module classifies common factual survey questions and maps them to authoritative
panel fields.  Unsupported individual facts fail closed in LIVE mode until an
explicit panel field or calibrated prior is supplied.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any
from copy import deepcopy
from types import SimpleNamespace


FACT_LAYER_VERSION = "1.0"

@dataclass(frozen=True)
class FactSpec:
    status: str  # DIRECT | UNSUPPORTED | NOT_FACT
    field: str = ""
    reason: str = ""


def _norm(x: Any) -> str:
    s = str(x or "").strip().lower()
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s)


# Deliberately conservative.  A false positive here is worse than an LLM question.
_DIRECT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("pohlavi", (r"\b(pohlaví|jste muž|jste žena|gender)\b",)),
    ("vek", (r"\b(kolik (je vám|vám je) let|váš věk|věk respondenta)\b",)),
    ("vzdelani", (r"\b(nejvyšší .*vzdělání|jaké máte vzdělání|dosažené vzdělání)\b",)),
    ("kraj", (r"\b(v jakém kraji|který kraj|kraj bydliště|ve kterém kraji)\b",)),
    ("trida_spolecenska", (r"\b(společenská třída|sociální třída)\b",)),
    ("zamestnan", (r"\b(jste zaměstnan|pracujete v současnosti|máte zaměstnání)\b",)),
    ("F_auto", (r"\b(vlastníte .*auto|máte .*automobil|má vaše domácnost .*auto)\b",)),
    ("F_bydleni", (r"\b(jak bydlíte|forma bydlení|typ bydlení|bydlíte v)\b",)),
    ("F_deti", (r"\b(máte děti|máte .*dítě|rodičem)\b",)),
    ("F_rodinny_stav", (r"\b(rodinný stav|jste ženat|jste vdaná|jste svobodn)\b",)),
    ("F_sam", (r"\b(žijete sám|žijete sama|jednočlenná domácnost)\b",)),
    ("F_strana", (r"\b(kterou stranu|koho byste volil|koho byste volila|volební preference)\b",)),
]

# Individual factual states not contained in the current panel.  These MUST NOT be
# fabricated by a persona.  A later calibrated-prior layer may provide them.
_UNSUPPORTED_PATTERNS = (
    r"\b(diabet\w*|cukrovk\w*|celiak\w*|astma\w*|rakovin\w*|onkolog\w*|diagn[oó]z\w*|onemocn\w*|nemoc\w*)\b",
    r"\b(vlastníte|máte)\s+(hypot[eé]ku|úvěr|investic|akcie|krypt|psa|kočku)\b",
    r"\b(používáte|vlastníte|kupujete)\s+(značku|produkt|iphone|android)\b",
)


def classify_question(question: Any, panel_columns: set[str] | None = None) -> FactSpec:
    """Return deterministic factual contract for a question.

    Explicit metadata wins:
      metadata.fact_source_field = exact panel column
      metadata.fact_kind = "attitude" disables auto factual detection
      metadata.fact_kind = "fact" with no available source fails closed
    """
    md = dict(getattr(question, "metadata", {}) or {})
    text = _norm(getattr(question, "text", ""))
    cols = panel_columns or set()
    kind = _norm(md.get("fact_kind"))
    if kind in {"attitude", "postoj", "opinion"}:
        return FactSpec("NOT_FACT")
    explicit = str(md.get("fact_source_field") or "").strip()
    if explicit:
        if not cols or explicit in cols:
            return FactSpec("DIRECT", explicit, "explicit metadata.fact_source_field")
        return FactSpec("UNSUPPORTED", explicit, f"Panel neobsahuje deklarovaný faktický sloupec '{explicit}'.")
    for field, patterns in _DIRECT_PATTERNS:
        if any(re.search(p, text, flags=re.I) for p in patterns):
            if not cols or field in cols:
                return FactSpec("DIRECT", field, "detected authoritative panel fact")
            return FactSpec("UNSUPPORTED", field, f"Panel neobsahuje očekávaný faktický sloupec '{field}'.")
    if kind in {"fact", "factual", "fakt"}:
        return FactSpec("UNSUPPORTED", "", "Otázka je označena jako faktická, ale nemá fact_source_field ani kalibrační prior.")
    if any(re.search(p, text, flags=re.I) for p in _UNSUPPORTED_PATTERNS):
        return FactSpec("UNSUPPORTED", "", "Individuální fakt není v panelu a v tomto kole pro něj není zaveden kalibrační prior.")
    return FactSpec("NOT_FACT")


def _boolish(v: Any) -> bool | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, bool): return v
    s=_norm(v)
    if s in {"1","1.0","ano","yes","true"}: return True
    if s in {"0","0.0","ne","no","false"}: return False
    return None


def _choice_index(categories: list[str], value: Any) -> int | None:
    """Map authoritative value to a 1-based survey choice index."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    cats=[_norm(x) for x in categories]
    raw=_norm(value)
    # Exact first.
    if raw in cats: return cats.index(raw)+1
    b=_boolish(value)
    if b is not None:
        yes={"ano","ano, mám","ano, vlastním","ano, pracuji","yes","1"}
        no={"ne","ne, nemám","ne, nevlastním","nepracuji","no","0"}
        pool=yes if b else no
        for i,c in enumerate(cats):
            if c in pool or (b and c.startswith("ano")) or ((not b) and c.startswith("ne")):
                return i+1
    # Normalize a few stored coding conventions.
    aliases={
        "zenaty_vdana": ("ženatý/vdaná","ženatý / vdaná","ženat/vdaná","v manželství"),
        "svobodny": ("svobodný/svobodná","svobodný","svobodná"),
        "rozvedeny": ("rozvedený/rozvedená","rozvedený","rozvedená"),
        "vdovec_vdova": ("vdovec/vdova","vdovec","vdova"),
    }
    for a in aliases.get(raw, ()):
        an=_norm(a)
        if an in cats: return cats.index(an)+1
    # Age bands such as 18–29 / 30-44.
    try:
        num=float(value)
        for i,c in enumerate(cats):
            m=re.search(r"(\d{1,3})\s*-\s*(\d{1,3})", c)
            if m and float(m.group(1)) <= num <= float(m.group(2)): return i+1
            # Open-ended upper age/value bands. AI-generated Czech questionnaires
            # commonly use forms such as "75+", "75 a více", "75 let a více",
            # "75 a výše" or "75 nebo více". Treat all of them identically; a band
            # that fails to parse here silently falls out of the deterministic path
            # and the question gets paid for on every respondent.
            m=re.search(r"(\d{1,3})\s*\+",c)
            if m and num>=float(m.group(1)): return i+1
            m=re.search(r"(\d{1,3})\s*(?:let\s*)?(?:a|nebo)\s*(?:více|výše)",c)
            if m and num>=float(m.group(1)): return i+1
            m=re.search(r"(?:více než|nad)\s*(\d{1,3})",c)
            if m and num>float(m.group(1)): return i+1
            m=re.search(r"(?:do|méně než)\s*(\d{1,3})",c)
            if m and num<float(m.group(1)): return i+1
    except Exception:
        pass
    # Soft substring only when unique and meaningful.
    hits=[i for i,c in enumerate(cats) if raw and (raw in c or c in raw)]
    return hits[0]+1 if len(hits)==1 else None



_FACT_AUTO_HARMONIZE_FIELDS={"pohlavi","vzdelani","kraj","trida_spolecenska"}
_FACT_VALUE_ORDER={"pohlavi":["muž","žena"],"vzdelani":["základní","střední","postsekundární","vysokoškolské"]}

def _ordered_fact_values(field:str,values:list[str])->list[str]:
    vals=[str(x).strip() for x in values if str(x).strip()]; wanted=[_norm(x) for x in _FACT_VALUE_ORDER.get(field,[])]
    by={_norm(x):x for x in vals}; return [by[x] for x in wanted if x in by]+sorted([x for x in vals if _norm(x) not in wanted],key=_norm)

def harmonize_project_fact_choices(project:dict[str,Any],panel:Any)->tuple[dict[str,Any],list[dict[str,Any]]]:
    out=deepcopy(project or {});notes=[];cols=set(list(getattr(panel,'columns',[])))
    for sec in out.get('sections') or []:
        if not isinstance(sec,dict) or sec.get('type')!='questions':continue
        for q in sec.get('questions') or []:
            if not isinstance(q,dict) or str(q.get('typ') or '')!='vyber':continue
            probe=SimpleNamespace(text=str(q.get('text') or ''),metadata=dict(q.get('metadata') or {}),typ='vyber')
            spec=classify_question(probe,cols);field=str(spec.field or '')
            if spec.status!='DIRECT' or field not in _FACT_AUTO_HARMONIZE_FIELDS or field not in cols:continue
            vals=[x for x in panel[field].dropna().astype(str).map(str.strip).unique().tolist() if x]
            cats=list(q.get('kategorie') or q.get('volby') or []);unmapped=[v for v in vals if _choice_index(cats,v) is None]
            md=dict(q.get('metadata') or {});md.setdefault('fact_source_field',field)
            if unmapped:
                md.setdefault('fact_original_categories',list(cats));md['fact_options_harmonized']=True;md['fact_harmonization_reason']='AI taxonomy was not fully mappable to authoritative panel values.'
                q['kategorie']=_ordered_fact_values(field,vals);q.pop('volby',None);notes.append({'question_id':str(q.get('id') or ''),'field':field,'unmapped_values':unmapped[:12],'new_categories':q['kategorie']})
            q['metadata']=md
    return out,notes


def deterministic_answer(question: Any, row: Any, spec: FactSpec) -> tuple[Any, dict[str, Any]]:
    """Answer a DIRECT question from one panel row, or raise on ambiguous mapping."""
    if spec.status != "DIRECT":
        raise ValueError("deterministic_answer requires DIRECT FactSpec")
    value=row.get(spec.field) if hasattr(row, "get") else row[spec.field]
    typ=str(getattr(question,"typ",""))
    if typ == "skala" and spec.field == "vek":
        ans=int(round(float(value)))
        lo,hi=getattr(question,"skala",(1,100))
        if not (int(lo)<=ans<=int(hi)):
            raise ValueError(f"Faktická hodnota věku {ans} neleží ve škále {lo}-{hi}.")
    elif typ == "vyber":
        cats=list(getattr(question,"volby",[]) or getattr(question,"kategorie",[]))
        idx=_choice_index(cats,value)
        if idx is None:
            raise ValueError(f"Faktický sloupec '{spec.field}' s hodnotou {value!r} nelze jednoznačně mapovat na možnosti otázky.")
        ans=cats[idx-1]
    elif typ == "multi":
        raise ValueError("Faktická multi-select otázka vyžaduje explicitní transformaci; LLM fallback je zakázán.")
    elif typ == "otevrena":
        ans=str(value)
    else:
        raise ValueError(f"Nepodporovaný typ faktické otázky: {typ}")
    return ans,{"fact_source_field":spec.field,"fact_layer_version":FACT_LAYER_VERSION,"fact_match":True,"provider":"deterministic_fact"}
