"""v17 evidence-aware persona retrieval over the coherent population data core.

The production persona is intentionally narrow:
- coherent core facts come from the single PIAAC/ISSP core donor and Census skeleton,
- PIAAC BFI-2 scores are measured-derived traits on the same core respondent,
- specialist survey blocks are whole-block statistical matches and are *always* labelled
  as matched donor evidence, never as facts measured on the core person,
- plausible-value skill estimates and transparent QC classes are not persona facts.

This replaces the old D_*/P_* synthetic persona path for the v17.1.2 population panel.

17.1 certification gate: MODELED_BEHAVIOR_PRIOR signals stay available in the dataset
for segmentation/planning but are excluded from respondent prompts until the preregistered
A/B/C/D LLM ablation demonstrates incremental predictive value.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
import math

import pandas as pd

from product_policy import persona_signal_budget

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "PERSONA_SIGNAL_CATALOG_v17.csv"
VALUE_LABELS = ROOT / "PERSONA_VALUE_LABELS_v17.json"

BFI_LABELS = {
    "BFI_EXTR":"extraverze", "BFI_AGRE":"přívětivost", "BFI_CONS":"svědomitost",
    "BFI_EMOS":"emoční stabilita", "BFI_OPEM":"otevřenost zkušenosti",
    "BFI_EXTR_ASSE":"sociální sebejistota", "BFI_EXTR_ENER":"energie/aktivita", "BFI_EXTR_SOCI":"sociabilita",
    "BFI_AGRE_COMP":"soucitnost", "BFI_AGRE_RESP":"respekt k druhým", "BFI_AGRE_TRUS":"důvěřivost",
    "BFI_CONS_ORGA":"organizovanost", "BFI_CONS_PROD":"produktivita", "BFI_CONS_RESP":"zodpovědnost",
    "BFI_EMOS_ANXI":"odolnost vůči úzkosti", "BFI_EMOS_DEPR":"odolnost vůči skleslosti", "BFI_EMOS_VOLA":"emoční stabilita/volatilita",
    "BFI_OPEM_AEST":"estetická otevřenost", "BFI_OPEM_CURI":"intelektuální zvídavost", "BFI_OPEM_IMAG":"představivost",
}


def _safe_num(v: Any) -> float | None:
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


@lru_cache(maxsize=1)
def _value_labels() -> dict[str, dict[str, Any]]:
    if not VALUE_LABELS.exists():
        return {}
    import json
    try:
        return dict(json.loads(VALUE_LABELS.read_text(encoding="utf-8")).get("variables") or {})
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _catalog() -> list[dict[str, Any]]:
    if not CATALOG.exists():
        return []
    df=pd.read_csv(CATALOG,low_memory=False)
    out=[]
    for _,r in df.iterrows():
        col=str(r.get("column") or "").strip()
        if not col: continue
        out.append({
            "column":col,
            "label":str(r.get("label") or col).strip(),
            "topics":{x.strip().lower() for x in str(r.get("topics") or "").split("|") if x.strip() and x.strip().lower()!="nan"},
            "source":str(r.get("source") or "").strip(),
            "wave":str(r.get("wave") or "").strip(),
            "evidence_role":str(r.get("evidence_role") or "").strip(),
            "block":str(r.get("block") or "").strip(),
            "kind":str(r.get("kind") or "raw").strip(),
            "priority":float(r.get("priority") or 1.0),
            "min_abs_z":float(r.get("min_abs_z") or 0.0),
            "concept":"" if pd.isna(r.get("concept")) else str(r.get("concept") or "").strip(),
        })
    return out


def _role_suffix(m: dict[str,Any], row: pd.Series) -> str:
    role=m["evidence_role"]
    if role=="MEASURED_DERIVED":
        return f"měřeno v core donorovi; {m['source']} {m['wave']}"
    if role=="MEASURED_JOINT":
        return f"měřeno ve stejném core donorovi; {m['source']} {m['wave']}"
    if role in {"MATCHED_DONOR_BLOCK","MATCHED_WHOLE_BLOCK_CANONICAL"}:
        block=m.get("block") or "blok"; q=row.get(f"_donor_{block}_quality"); qs=f", match {q}" if pd.notna(q) and str(q).strip() else ""
        return f"statisticky přiřazený celý donor blok; {m['source']} {m['wave']}{qs}"
    if role=="CALIBRATED_BEHAVIOR_MODEL": return "kalibrovaný behaviorální model"
    if role=="MODELED_BEHAVIOR_PRIOR": return "modelový behaviorální prior"
    if role=="MODELED_VALUE_PROXY": return "modelový hodnotový proxy"
    if role=="CALIBRATED_MODELED_COMPOSITE": return "kalibrovaný modelový kompozit"
    if role=="CALIBRATED_MODELED_BINARY": return "kalibrovaná modelová položka"
    return role.lower().replace("_"," ")


_ANCHOR_MAX_WORDS = 12


def _compact_anchor(label: str, low: str, high: str, direction: str) -> str:
    """Strip anchor prose down to what the label does not already say.

    Rationale: the anchor text is byte-identical across all respondents, so every
    word of it is paid N times in the prompt while carrying zero per-respondent
    information. Words already present in the label are removed, a direction that
    merely restates the high anchor is dropped, and the remainder is capped.
    """
    lab_words={w for w in re.findall(r"\w+", label.lower()) if len(w)>3}

    def _clean(t: str) -> str:
        """Cut the anchor at the first content word the label already contains.

        Truncating at that boundary keeps the polarity marker ("zcela neochotný/á")
        and drops the restatement of the dimension name, without leaving dangling
        prepositions the way word-by-word filtering does.
        """
        t=re.sub(r"^\s*\d+\s*=\s*", "", str(t or "").strip())
        out=[]
        for w in t.split():
            if re.sub(r"\W","",w).lower() in lab_words: break
            out.append(w)
        if not out: out=t.split()[:3]
        return " ".join(out).strip(" ,;—-")

    lo,hi=_clean(low),_clean(high)
    if lo and hi and lo.lower()==hi.lower(): hi=""
    parts=[]
    if lo or hi: parts.append(f"0={lo or '—'}, 10={hi or '—'}")
    d=str(direction or "").strip()
    # "vyšší hodnota = více uvedeného" is the default semantics of any 1–10 scale;
    # spelling it out per respondent adds tokens, not information.
    if d and not re.match(r"^(vyšší|nižší|více|méně)\b", d, re.I) and len(d.split())<=6:
        parts.append(d)
    return " ".join("; ".join(parts).split()[:_ANCHOR_MAX_WORDS])


def _render(m: dict[str,Any], row: pd.Series) -> tuple[str,float] | None:
    c=m["column"]
    if c not in row.index or pd.isna(row.get(c)):
        return None
    v=row.get(c); kind=m["kind"]; label=m["label"]
    score=m["priority"]

    # v17.0.0: source-specific value semantics always outrank a generic scale.
    # This prevents the LLM from assuming that a larger number always means
    # "more" of the label (several CSES/JRC scales run in the opposite direction).
    spec=_value_labels().get(c)
    if spec:
        x=_safe_num(v)
        if x is None: return None
        values=spec.get("values") or {}
        key=str(int(round(x))) if abs(x-round(x))<1e-9 else f"{x:g}"
        if key in values:
            direction=str(spec.get("direction") or "").strip()
            suffix=f"; {direction}" if direction else ""
            return f"{label}: {values[key]}{suffix}",score*(1.15 if direction else 1.05)
        anchors=spec.get("anchors") or {}
        if anchors:
            low=str(anchors.get("low") or "").strip(); high=str(anchors.get("high") or "").strip()
            direction=str(spec.get("direction") or "").strip()
            # Generic 1–10 semantics need no repeated anchor prose. Only reversed or
            # otherwise special scales carry anchors into the prompt.
            generic=("nízká intenzita" in low and "vysoká intenzita" in high and "více uvedeného" in direction)
            if generic:return f"{label}: {x:g}/10",score*(1+abs(x-5)/10)
            # FIX 17.1.1: anchor prose is identical for every respondent and was the
            # single largest consumer of the persona word budget (~40 words/signal),
            # which pushed ~11 % of calibrated personas over the cap. Keep only the
            # information the label does not already carry.
            anch=_compact_anchor(label, low, high, direction)
            txt=f"{label}: {x:g}/10" + (f" ({anch})" if anch else "")
            return txt,score*(1+abs(x-5)/10)

    if kind=="bfi_z":
        x=_safe_num(v)
        if x is None or abs(x)<max(.35,m["min_abs_z"]): return None
        strength="výrazně" if abs(x)>=1.15 else "spíše"
        direction="vyšší" if x>0 else "nižší"
        score*=1.2+abs(x)
        return f"{strength} {direction} {label} než populační průměr",score
    if kind=="scale10":
        x=_safe_num(v)
        if x is None: return None
        # middle values are low-information; extremes rank first.
        score*=1+abs(x-5)/5
        return f"{label}: {x:g}/10",score
    if kind=="scale5":
        x=_safe_num(v)
        if x is None: return None
        score*=1+abs(x-3)/2
        return f"{label}: {x:g}/5",score
    if kind=="frequency5":
        x=_safe_num(v)
        if x is None: return None
        names={1:"nikdy",2:"méně než měsíčně",3:"alespoň měsíčně, ne týdně",4:"alespoň týdně, ne denně",5:"denně"}
        score*=1+abs(x-3)/2
        return f"{label}: {names.get(int(round(x)),str(x))}",score
    if kind=="health5":
        x=_safe_num(v)
        if x is None: return None
        names={1:"výborné",2:"velmi dobré",3:"dobré",4:"uspokojivé",5:"špatné"}
        score*=1+abs(x-3)/2
        return f"{label}: {names.get(int(round(x)),str(x))}",score
    if kind=="scale4":
        x=_safe_num(v)
        if x is None: return None
        score*=1+abs(x-2.5)/1.5
        return f"{label}: {x:g}/4",score
    if kind=="scale6":
        x=_safe_num(v)
        if x is None: return None
        score*=1+abs(x-3.5)/2.5
        return f"{label}: {x:g}/6",score
    if kind=="yesno":
        x=_safe_num(v)
        if x is None: return None
        return f"{label}: {'ano' if int(round(x))==1 else 'ne'}",score*1.2
    if kind=="minutes_day":
        x=_safe_num(v)
        if x is None:return None
        score*=1+min(abs(x),180)/360
        return f"{label}: ~{x:g} min/den",score
    if kind=="hours_week":
        x=_safe_num(v)
        if x is None:return None
        return f"{label}: ~{x:g} h/týden",score
    if kind=="scale01":
        x=_safe_num(v)
        if x is None:return None
        return f"{label}: {x:.2f} (0–1)",score
    if kind=="categorical":
        txt=str(v).strip()
        if not txt or txt.lower() in {"nan","none","<na>","unknown"}:return None
        return f"{label}: {txt}",score
    if kind=="phq9":
        x=_safe_num(v)
        if x is None: return None
        score*=1+min(x,20)/20
        return f"PHQ-9 symptom score: {x:g}/27 (nikoli diagnóza)",score
    if kind=="gad7":
        x=_safe_num(v)
        if x is None: return None
        score*=1+min(x,18)/18
        return f"GAD-7 symptom score: {x:g}/21 (nikoli diagnóza)",score
    if kind=="text":
        txt=str(v).strip()
        if not txt or txt.lower() in {"nan","none","<na>","neví/odmítl","nevi/odmitl","don't know","dont know","refused"}: return None
        # Several JRC labelled exports are English. Keep the source value but render
        # common response categories in Czech so persona prompts stay user-friendly.
        tr={
            "None of the time":"nikdy", "A little of the time":"malou část času",
            "Some of the time":"část času", "Most of the time":"většinu času", "All of the time":"stále",
            "Never":"nikdy", "Daily":"denně", "Every week":"jednou týdně",
            "More than once a week":"vícekrát týdně", "Every two weeks":"jednou za dva týdny",
            "Once a month":"jednou měsíčně", "Every two months or less frequently":"jednou za dva měsíce nebo méně často",
            "On specific holidays only":"jen o vybraných svátcích", "Once a week":"jednou týdně",
            "More than once a week":"více než jednou týdně",
        }
        txt=tr.get(txt,txt)
        return f"{label}: {txt}",score*1.15
    return None


def grounded_profile_text(row: pd.Series, topics: Iterable[str] | None) -> str:
    """Return a compact topic-specific, provenance-qualified profile.

    On v15.2 rows, lack of topic-specific evidence returns an empty string instead
    of falling back to old synthetic D_/P_* scores.
    """
    topic_set={str(x).strip().lower() for x in (topics or []) if str(x).strip()}
    if not topic_set:
        return ""

    candidates=[]
    for m in _catalog():
        if not (topic_set & m["topics"]): continue
        # 17.1 external-validation gate: purely modeled marketing/behavior priors
        # must not influence respondent answers before the A/B/C/D LLM ablation is run.
        if m.get("evidence_role") == "MODELED_BEHAVIOR_PRIOR":
            continue
        rr=_render(m,row)
        if rr is None: continue
        txt,score=rr
        # Exact/specific topic matches outrank generic domain matches. This prevents
        # e.g. three generic device-frequency facts from hiding the bank/e-commerce
        # fact in a banking question merely because all of them also match "digital".
        _generic={"digital","online","politika","verejne","zdravi","vztahy","finance","spolecnost","prace"}
        _matched=topic_set & m["topics"]
        _specific=_matched-_generic
        score*=1.0+0.80*len(_specific)
        candidates.append((score,m,txt))
    if not candidates:
        return ""

    candidates.sort(key=lambda x:(-x[0],x[1]["column"]))
    budget=max(3,min(9,persona_signal_budget(topic_set)))
    selected=[]; per_block={}; used_concepts=set()
    for score,m,txt in candidates:
        block=m["block"] or "other"
        concept=m.get("concept") or ""
        # Prefer diversity. A whole matched block should not swamp the prompt and
        # independent survey waves must not look like a longitudinal history.
        if per_block.get(block,0)>=3: continue
        if concept and concept in used_concepts: continue
        selected.append((m,txt)); per_block[block]=per_block.get(block,0)+1
        if concept: used_concepts.add(concept)
        if len(selected)>=budget: break

    groups=[]
    for m,txt in selected:
        groups.append(f"{txt} [{_role_suffix(m,row)}]")
    return "Relevantní datové signály: " + "; ".join(groups)
