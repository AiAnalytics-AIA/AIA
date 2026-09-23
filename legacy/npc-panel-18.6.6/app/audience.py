"""audience.py — kdo je v cílové skupině a jestli jich je dost.

Odpovídá na otázku, kterou dosud nešlo položit před během:
  * kolik person v panelu filtru vyhovuje (support),
  * jaký podíl populace to je po kalibračních vahách,
  * jaký je efektivní vzorek (ESS) a z něj plynoucí přesnost,
  * čím se segment liší od populace — demograficky i dispozičně.

Filtry mají stejnou sémantiku jako `pipeline.sample_representative`:
    {"pohlavi": "žena"}                 rovnost
    {"kraj": ["Praha", "Středočeský"]}  výčet kategorií
    {"vek": (25, 44)}                   interval (tuple délky 2)

LLM zde nic nerozhoduje. `propose_filters` je jen překlad věty na návrh, který se
vždy ověřuje proti skutečným sloupcům a hodnotám panelu; co neprojde, se zahodí.
"""
from __future__ import annotations
from provider_auth import get_ai_provider

from anthropic_compat import create_message

import json
import math
from typing import Any

import numpy as np
import pandas as pd

DEMO_COLS = ["pohlavi", "vek_skupina", "vzdelani", "kraj", "zamestnani_status"]
NUM_COLS = ["vek", "prijem_osobni_mesicni", "prijem_decile", "velikost_domacnosti"]
WEIGHT = "_analysis_weight"


def _mask(df: pd.DataFrame, filtry: dict[str, Any] | None) -> pd.Series:
    """AND across dimensions; OR inside one categorical dimension.

    Numeric filters accept legacy tuples and the JSON-safe {min,max} contract used
    by the 17.9.3 factor selector.
    """
    m = pd.Series(True, index=df.index)
    for k, v in (filtry or {}).items():
        if k not in df.columns:
            raise KeyError(f"Filtr '{k}' není sloupec panelu.")
        col = df[k]
        if isinstance(v, dict) and ('min' in v or 'max' in v):
            x=pd.to_numeric(col,errors='coerce'); lo=v.get('min',x.min()); hi=v.get('max',x.max())
            m &= x.between(float(lo),float(hi))
        elif isinstance(v, tuple) and len(v) == 2:
            m &= pd.to_numeric(col, errors="coerce").between(v[0], v[1])
        elif isinstance(v, (list, set, tuple)):
            m &= col.isin(list(v))
        else:
            m &= col == v
    return m


def effective_n(w: np.ndarray) -> float:
    """Kish ESS. Vážený vzorek nese míň informace než jeho počet řádků."""
    w = np.asarray(w, dtype=float)
    w = w[np.isfinite(w) & (w > 0)]
    if w.size == 0:
        return 0.0
    return float(w.sum() ** 2 / (w ** 2).sum())


def sampling_precision_pp(n: float, p: float = 0.5, conf: float = 1.96) -> float | None:
    """Poloviční šířka intervalu v procentních bodech při dané velikosti vzorku.

    Je to čistě výběrová chyba pro n nezávislých pozorování. U syntetického panelu
    NEVYJADŘUJE shodu se skutečnou populací — pouze horní mez toho, jak přesně lze
    vůbec něco tvrdit, i kdyby persony byly dokonalé.
    """
    if not n or n <= 1:
        return None
    return round(100 * conf * math.sqrt(p * (1 - p) / n), 2)


def moe_pp(n: float, p: float = 0.5, conf: float = 1.96) -> float | None:
    """Deprecated compatibility alias. Use sampling_precision_pp; this is not population MoE."""
    return sampling_precision_pp(n,p,conf)


def _dist(s: pd.Series, w: np.ndarray) -> dict[str, float]:
    d = pd.Series(w, index=s.index).groupby(s.astype(str)).sum()
    tot = float(d.sum())
    return {k: round(100 * v / tot, 1) for k, v in d.items()} if tot > 0 else {}


def _weighted_mean(values: pd.Series, weights: np.ndarray) -> float | None:
    x=pd.to_numeric(values,errors="coerce").to_numpy(dtype=float)
    w=np.asarray(weights,dtype=float)
    ok=np.isfinite(x)&np.isfinite(w)&(w>0)
    if not ok.any() or w[ok].sum()<=0:return None
    return float(np.average(x[ok],weights=w[ok]))


def _weighted_sd(values: pd.Series, weights: np.ndarray) -> float | None:
    x=pd.to_numeric(values,errors="coerce").to_numpy(dtype=float)
    w=np.asarray(weights,dtype=float)
    ok=np.isfinite(x)&np.isfinite(w)&(w>0)
    if ok.sum()<2 or w[ok].sum()<=0:return None
    mu=float(np.average(x[ok],weights=w[ok])); var=float(np.average((x[ok]-mu)**2,weights=w[ok]))
    return float(np.sqrt(var))


def profile(df: pd.DataFrame, filtry: dict[str, Any] | None = None, *,
            top_dimensions: int = 8) -> dict[str, Any]:
    """Popis cílové skupiny proti celé populaci panelu."""
    m = _mask(df, filtry)
    seg, pop = df[m], df
    w_all = pd.to_numeric(df[WEIGHT] if WEIGHT in df.columns else df.get("vaha_strukturalni_2025",df.get("vaha_kalibrovana",pd.Series(1.0,index=df.index))), errors="coerce").fillna(1.0).to_numpy()
    w_seg = w_all[m.to_numpy()]

    support = int(m.sum())
    ess = effective_n(w_seg)
    share = float(w_seg.sum() / w_all.sum()) if w_all.sum() > 0 else 0.0

    demo = []
    for c in DEMO_COLS:
        if c not in df.columns:
            continue
        a, b = _dist(seg[c], w_seg), _dist(pop[c], w_all)
        rows = [{"hodnota": k, "segment_pct": a.get(k, 0.0), "populace_pct": b.get(k, 0.0),
                 "rozdil_pb": round(a.get(k, 0.0) - b.get(k, 0.0), 1)} for k in b]
        rows.sort(key=lambda r: -abs(r["rozdil_pb"]))
        demo.append({"promenna": c, "hodnoty": rows})

    nums = {}
    for c in NUM_COLS:
        if c in df.columns:
            sm=_weighted_mean(seg[c],w_seg); pm=_weighted_mean(pop[c],w_all)
            if sm is not None and pm is not None:
                nums[c] = {"segment": round(sm, 1), "populace": round(pm, 1), "weighted": True}

    # v15.2: profil rozdílů používá pouze měřené nebo celé matchované donor bloky.
    # Staré D_* syntetické dimenze se do Audience Strategistu už nevracejí.
    signal_cols = [
        ("BFI_EXTR","extraverze","MEASURED_DERIVED"),("BFI_AGRE","přívětivost","MEASURED_DERIVED"),
        ("BFI_CONS","svědomitost","MEASURED_DERIVED"),("BFI_EMOS","emoční stabilita","MEASURED_DERIVED"),
        ("BFI_OPEM","otevřenost","MEASURED_DERIVED"),("PIAAC_I2_Q01b","sociální důvěra","MEASURED_JOINT"),
        ("PIAAC_I2_Q05","životní spokojenost","MEASURED_JOINT"),("PHQ9_2022","PHQ-9 score","MATCHED_DONOR_BLOCK"),
        ("GAD7_2022","GAD-7 score","MATCHED_DONOR_BLOCK"),("politicky_zajem_2021","politický zájem","MATCHED_DONOR_BLOCK"),
        ("redistribuce_podpora_2021","podpora redistribuce","MATCHED_DONOR_BLOCK"),
        ("JRC_trust","sociální důvěra JRC","MATCHED_DONOR_BLOCK"),
    ]
    dims=[]
    for c,label,status in signal_cols:
        if c not in df.columns: continue
        sm=_weighted_mean(seg[c],w_seg); pm=_weighted_mean(pop[c],w_all); sd=_weighted_sd(pop[c],w_all)
        if sm is None or pm is None or sd is None or sd<=0 or len(seg)<30: continue
        d=(sm-pm)/sd
        if np.isfinite(d): dims.append({"dimenze":label,"column":c,"d":round(float(d),3),"status":status})
    dims.sort(key=lambda x:-abs(x["d"]))

    return {
        "filtry": filtry or {},
        "support": support,
        "podil_populace_pct": round(100 * share, 2),
        "ess": round(ess, 1),
        "sampling_precision_pp_pri_support": sampling_precision_pp(ess),
        "demografie": demo,
        "numericke": nums,
        "dispozicni_odchylky": dims[:top_dimensions],
        "dispozicni_profil_status": "MEASURED_OR_MATCHED_V15_2_1",
        "precision_note": "Sampling-only precision; nezahrnuje chybu NPC modelu, joint struktury ani rozdíl proti lidem.",
    }


def feasibility(df: pd.DataFrame, filtry: dict[str, Any] | None, n: int) -> dict[str, Any]:
    """Projde požadované n proti dostupnému supportu.

    Výběr je PPS BEZ náhrady, takže n > support není 'méně přesné' — spadne to.
    """
    p = profile(df, filtry)
    support, problems = p["support"], []
    if support == 0:
        problems.append({"uroven": "ERROR", "text": "Filtr nevybral žádnou personu; běh selže."})
    elif n > support:
        problems.append({"uroven": "ERROR",
                         "text": f"Požadované n={n} přesahuje dostupný support {support}. "
                                 f"Výběr je bez náhrady, běh selže. Sniž n nebo rozšiř filtr."})
    elif n > 0.5 * support:
        problems.append({"uroven": "WARNING",
                         "text": f"n={n} je přes polovinu supportu ({support}). Vzorek vyčerpává "
                                 f"segment, opakované běhy budou skoro identické."})
    achieved = min(n, support) if support else 0
    ess_ratio = (p["ess"] / support) if support else 0
    if support and ess_ratio < 0.6:
        problems.append({"uroven": "WARNING",
                         "text": f"Váhy jsou v segmentu nerovnoměrné (ESS {p['ess']:.0f} "
                                 f"z {support}). Efektivní přesnost je horší, než n napovídá."})
    p["pozadovane_n"] = n
    p["dosazitelne_n"] = achieved
    p["sampling_precision_pp_pri_n"] = sampling_precision_pp(min(achieved, p["ess"]) if p["ess"] else achieved)
    p["problemy"] = problems
    p["ok"] = not any(x["uroven"] == "ERROR" for x in problems)
    return p


# --------------------------------------------------------------------------- #
# volitelný překlad věty na filtr; model navrhuje, kód rozhoduje
# --------------------------------------------------------------------------- #
def allowed_values(df: pd.DataFrame, *, text: str = '', limit: int = 120) -> dict[str, Any]:
    """JSON-safe catalogue for AI translation and backwards-compatible UI fields."""
    from audience_dimensions import catalog, search_catalog
    items=search_catalog(df,text,limit=limit) if str(text or '').strip() else [x for x in catalog(df,include_research_only=False)['factors'] if x.get('filterable')][:limit]
    out={}
    for x in items:
        if x['kind']=='numeric':out[x['id']]={'type':'range','min':x.get('min'),'max':x.get('max'),'label':x['label'],'category':x['category_label']}
        else:out[x['id']]={'type':x['kind'],'values':[v['value'] for v in (x.get('values') or [])[:30]],'label':x['label'],'category':x['category_label']}
    # Historical clients expect these keys to exist even when lexical search is used.
    for c in DEMO_COLS:
        if c in df.columns and c not in out: out[c]=sorted(map(str,df[c].dropna().unique()))[:40]
    return out


def sanitize_filters(df: pd.DataFrame, raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Keep only data-backed, product-filterable dimensions and valid values."""
    from audience_dimensions import factor_map
    fmap=factor_map(df); clean={}; dropped=[]
    for k,v in (raw or {}).items():
        spec=fmap.get(k)
        if not spec or not spec.get('filterable'):
            dropped.append(f"{k}: není podporovaná filtrační dimenze"); continue
        if k not in df.columns:
            dropped.append(f"{k}: není runtime sloupec panelu"); continue
        if spec.get('kind')=='numeric':
            if isinstance(v,dict) and ('min' in v or 'max' in v):
                lo=v.get('min',spec.get('min'));hi=v.get('max',spec.get('max'))
            elif isinstance(v,(list,tuple)) and len(v)==2:
                lo,hi=v
            elif isinstance(v,(int,float,np.integer,np.floating)):
                lo=hi=v
            else:
                dropped.append(f"{k}: očekáván interval min/max");continue
            try:lo=float(lo);hi=float(hi)
            except Exception:dropped.append(f"{k}: neplatný číselný interval");continue
            if hi<lo:lo,hi=hi,lo
            clean[k]=(lo,hi);continue
        actual=list(df[k].dropna().unique()); lookup={str(x):x for x in actual}
        numeric_binary=set(lookup).issubset({'0','1','0.0','1.0','True','False'}) and bool(lookup)
        vals=list(v) if isinstance(v,(list,tuple,set)) else [v]
        keys=[]
        for x in vals:
            if isinstance(x,(bool,np.bool_)) and numeric_binary:
                keys.extend([str(int(x)),str(bool(x))])
            else:keys.append(str(x))
        keep=[]
        for key in keys:
            if key in lookup and lookup[key] not in keep:keep.append(lookup[key])
        if not keep:dropped.append(f"{k}: žádná zadaná hodnota v panelu neexistuje")
        else:clean[k]=keep[0] if len(keep)==1 else keep
    return clean,dropped


def propose_filters(df: pd.DataFrame, popis: str, *, model: str = "sonnet", provider: str | None = None) -> dict[str, Any]:
    """Natural-language audience -> safe data-backed filter proposal."""
    from runtime_config import resolve_model
    candidates=allowed_values(df,text=popis,limit=55)
    schema={"type":"object","properties":{"filtry":{"type":"object"},"zduvodneni":{"type":"string"},"nepokryto":{"type":"string"}},"required":["filtry","zduvodneni","nepokryto"],"additionalProperties":False}
    sys_p=("Překládáš popis cílové populace na skutečné filtry českého panelu. "
           "Používej výhradně nabídnuté faktory. Mezi různými dimenzemi platí AND; více hodnot stejné kategorické dimenze znamená OR. "
           "Číselný interval vrať jako {\"min\": číslo, \"max\": číslo}. Co panel neumí, napiš do nepokryto; nikdy nevymýšlej sloupec ani citlivý targeting.\n\n"+json.dumps(candidates,ensure_ascii=False,indent=1))
    from ai_router import call_structured
    rr=call_structured(system=sys_p,messages=[{"role":"user","content":popis}],schema=schema,schema_name='submit_filters',anthropic_model=model,max_tokens=1500,prefer=(provider or get_ai_provider()),allow_fallback=False)
    out=dict(rr.get('data') or {}); clean,dropped=sanitize_filters(df,out.get('filtry') or {})
    return {'filtry':clean,'zahozeno':dropped,'zduvodneni':out.get('zduvodneni',''),'nepokryto':out.get('nepokryto',''),'candidate_count':len(candidates),'_ai':{'provider':rr.get('provider'),'model':rr.get('model'),'fallback_used':rr.get('fallback_used',False)}}

