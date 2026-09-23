"""Canonical conditional-calibration engine for NPC Panel 10.13.

This module promotes the useful part of the v15 research prototype into the
runtime tree: fit P(D|demography) to documented target tables while preserving a
person-specific residual.  It deliberately does NOT claim that the residual
joint structure is valid.  Therefore output from this module is Tier B unless a
separate, measured joint gate promotes a dimension to Tier A.

The twelve v15 profiles are kept reproducible.  Eight are explicit target
profiles; four are re-derived from source files bundled with the complete
release.  The latter are marked as respondent-level evidence in the registry,
not silently relabeled as public aggregate evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parent
MICRO = ROOT / "source_materials" / "microdata" / "acquired_data"
AGE_BANDS = {"18-24": (18,24), "25-34": (25,34), "35-44": (35,44),
             "45-54": (45,54), "55-64": (55,64), "65-74": (65,74), "75+": (75,200)}
EDU = {"zakladni":"základní", "ss_bez":"střední bez maturity",
       "ss_mat":"střední s maturitou", "vs":"VOŠ/VŠ"}

# Explicit targets copied from the audited v15 prototype, enriched with source URLs.
TRUTH: dict[str, dict[str, Any]] = {
 "digitalni_zivot": dict(zdroj="ČSÚ VŠIT 2025 tab. 5.10", source_url="https://csu.gov.cz/produkty/vyuzivani-informacnich-a-komunikacnich-technologii-v-domacnostech-a-mezi-osobami-gnzqheaxdo", evidence_role="AGGREGATE_CONDITIONAL", celkem=63.6,
   pohlavi={"muz":63.8,"zena":63.6}, vek={"18-24":91.6,"25-34":88.1,"35-44":85.4,"45-54":75.5,"55-64":56.8,"65-74":25.5,"75+":10.8}, vzdelani={"zakladni":46.4,"ss_bez":56.2,"ss_mat":85.5,"vs":95.3}),
 "adopce_ai": dict(zdroj="ČSÚ VŠIT 2025 tab. 5.8", source_url="https://csu.gov.cz/produkty/vyuzivani-informacnich-a-komunikacnich-technologii-v-domacnostech-a-mezi-osobami-gnzqheaxdo", evidence_role="AGGREGATE_CONDITIONAL", celkem=31.5,
   pohlavi={"muz":33.7,"zena":29.6}, vek={"18-24":78.5,"25-34":56.4,"35-44":40.4,"45-54":27.0,"55-64":16.2,"65-74":5.9,"75+":1.8}, vzdelani={"zakladni":16.4,"ss_bez":13.2,"ss_mat":37.3,"vs":60.0}),
 "socialni_site": dict(zdroj="ČSÚ VŠIT 2025 tab. 7.1", source_url="https://csu.gov.cz/produkty/vyuzivani-informacnich-a-komunikacnich-technologii-v-domacnostech-a-mezi-osobami-gnzqheaxdo", evidence_role="AGGREGATE_CONDITIONAL", celkem=63.2,
   pohlavi={"muz":59.6,"zena":66.6}, vek={"18-24":97.6,"25-34":95.6,"35-44":85.3,"45-54":70.3,"55-64":50.7,"65-74":25.0,"75+":9.4}, vzdelani={"zakladni":62.7,"ss_bez":70.0,"ss_mat":77.7,"vs":80.1}),
 "internetove_bankovnictvi": dict(zdroj="ČSÚ VŠIT 2025 tab. 12.1", source_url="https://csu.gov.cz/produkty/vyuzivani-informacnich-a-komunikacnich-technologii-v-domacnostech-a-mezi-osobami-gnzqheaxdo", evidence_role="AGGREGATE_CONDITIONAL", celkem=77.9,
   pohlavi={"muz":78.2,"zena":77.7}, vek={"18-24":87.7,"25-34":95.5,"35-44":94.9,"45-54":91.7,"55-64":81.7,"65-74":53.9,"75+":23.8}, vzdelani={"zakladni":62.7,"ss_bez":84.7,"ss_mat":95.8,"vs":98.5}),
 "ecommerce": dict(zdroj="ČSÚ VŠIT 2025 tab. 14.1, nákup za posledních 12 měsíců", source_url="https://csu.gov.cz/produkty/vyuzivani-informacnich-a-komunikacnich-technologii-v-domacnostech-a-mezi-osobami-gnzqheaxdo", evidence_role="AGGREGATE_CONDITIONAL", celkem=76.2,
   pohlavi={"muz":75.8,"zena":76.6}, vek={"18-24":97.3,"25-34":97.1,"35-44":94.5,"45-54":90.4,"55-64":75.1,"65-74":46.3,"75+":18.1}, vzdelani={"zakladni":65.7,"ss_bez":80.5,"ss_mat":95.7,"vs":96.4}),
 "depresivni_symptomy": dict(zdroj="NÚDZ CAPI 2022, PHQ-9 ≥10, target profile from bundled v15 research build", source_url="https://zenodo.org/records/15754049", evidence_role="MEASURED_RESPONDENT_PROFILE", celkem=8.7,
   pohlavi={"muz":7.9,"zena":9.5}, vek={"18-24":13.1,"25-34":10.1,"35-44":8.7,"45-54":6.6,"55-64":7.2,"65-74":7.5,"75+":14.5}, vzdelani={"zakladni":9.8,"ss_bez":9.9,"ss_mat":7.9,"vs":7.5}),
 "uzkostne_symptomy": dict(zdroj="NÚDZ CAPI 2022, GAD-7 ≥10, target profile from bundled v15 research build", source_url="https://zenodo.org/records/15754049", evidence_role="MEASURED_RESPONDENT_PROFILE", celkem=4.2,
   pohlavi={"muz":3.8,"zena":4.6}, vek={"18-24":7.2,"25-34":4.4,"35-44":4.6,"45-54":4.1,"55-64":4.0,"65-74":3.1,"75+":2.9}, vzdelani={"zakladni":5.3,"ss_bez":3.5,"ss_mat":4.8,"vs":3.7}),
 "ucast_volby": dict(zdroj="ČSÚ volby PS 2025 + věkový profil použitý ve v15 research build", source_url="https://www.volby.cz/opendata/ps2025/ps2025_opendata.htm", evidence_role="AGGREGATE_CONDITIONAL", celkem=68.9,
   vek={"18-24":61.0,"25-34":63.0,"35-44":70.0,"45-54":72.0,"55-64":72.0,"65-74":75.0,"75+":62.0},
   kraj={"Praha":71.4,"Středočeský":71.3,"Jihočeský":69.5,"Plzeňský":68.2,"Karlovarský":60.7,"Ústecký":61.9,"Liberecký":68.0,"Královehradecký":70.5,"Pardubický":71.4,"Vysočina":72.5,"Jihomoravský":69.8,"Olomoucký":68.6,"Zlínský":69.7,"Moravskoslezský":66.1}),
}


def _band_value(a: float) -> str | None:
    for lab, (lo, hi) in AGE_BANDS.items():
        if lo <= a <= hi:
            return lab
    return None


def _micro_profile(df: pd.DataFrame, weights, y, age, sex, male_code=1) -> dict[str, Any]:
    d = pd.DataFrame({"y":y, "w":weights, "vek":age, "poh":sex}).dropna(subset=["y","vek"])
    d["band"] = d.vek.map(_band_value)
    out = {"celkem": round(100*float(np.average(d.y, weights=d.w)), 2), "vek":{}, "pohlavi":{}}
    for b,g in d.groupby("band"):
        if len(g) >= 40 and float(g.w.sum()) > 0:
            out["vek"][b] = round(100*float(np.average(g.y, weights=g.w)), 2)
    m=d.poh==male_code
    if int(m.sum()) > 40 and int((~m).sum()) > 40:
        out["pohlavi"]={"muz":round(100*float(np.average(d.y[m],weights=d.w[m])),2),"zena":round(100*float(np.average(d.y[~m],weights=d.w[~m])),2)}
    return out


def load_derived_truth(strict: bool = False) -> dict[str, dict[str, Any]]:
    """Re-derive four v15 profiles from bundled respondent-level source files."""
    out: dict[str, dict[str, Any]] = {}
    try:
        pth=MICRO/"PIAAC_2023_CZ"/"prgczep2.csv"
        p=pd.read_csv(pth,sep=";",low_memory=False,na_values=[".",".v",".n"])
        w=pd.to_numeric(p.SPFWT0,errors="coerce").fillna(0); age=pd.to_numeric(p.AGE_R,errors="coerce"); sex=pd.to_numeric(p.GENDER_R,errors="coerce")
        lit=pd.to_numeric(p.PVLIT1,errors="coerce"); tru=pd.to_numeric(p.I2_Q01b,errors="coerce")
        x=_micro_profile(p,w,(lit<226).where(lit.notna()),age,sex); x.update(zdroj="OECD PIAAC 2023 CZ, PVLIT1<226",source_url="https://www.oecd.org/en/data/datasets/piaac-2nd-cycle-database.html",evidence_role="MEASURED_RESPONDENT_PROFILE"); out["kognitivni_gramotnost"]=x
        x=_micro_profile(p,w,(tru>=6).where(tru.notna()),age,sex); x.update(zdroj="OECD PIAAC 2023 CZ, I2_Q01b≥6",source_url="https://www.oecd.org/en/data/datasets/piaac-2nd-cycle-database.html",evidence_role="MEASURED_RESPONDENT_PROFILE"); out["socialni_duvera"]=x
    except Exception:
        if strict: raise
    try:
        pth=MICRO/"CSDA_Rule_of_Law_2024"/"CZ_database_v2.tab"
        r=pd.read_csv(pth,sep="\t",low_memory=False); w=pd.to_numeric(r.weight_demo,errors="coerce").fillna(1); age=pd.to_numeric(r.age,errors="coerce"); sex=pd.to_numeric(r.sex,errors="coerce")
        for dim,col,label in [("prioritizuje_vetsinovou_vladu","var152O470","vláda dle vůle většiny jako TOP priorita"),("prioritizuje_nezavislost_soudu","var152O472","nezávislé soudy jako TOP priorita")]:
            v=pd.to_numeric(r[col],errors="coerce"); x=_micro_profile(r,w,(v<=1).where(v.notna()),age,sex); x.update(zdroj=f"Rule of Law ČR 2024, {label}",source_url="https://doi.org/10.14473/CSDA/HL0XSA",evidence_role="MEASURED_RESPONDENT_PROFILE"); out[dim]=x
    except Exception:
        if strict: raise
    return out

_derived = load_derived_truth(strict=False)
# Clean runtime releases do not ship the heavy evidence archive by default.
# Preserve the last audited derived profiles from the canonical frozen truth JSON
# when source files are absent; when the evidence archive is present, re-derive.
if len(_derived) < 4:
    frozen = ROOT / "CONDITIONAL_TRUTH_10_13.json"
    if frozen.exists():
        try:
            frozen_truth = json.loads(frozen.read_text(encoding="utf-8"))
            for _dim in ("kognitivni_gramotnost", "socialni_duvera", "prioritizuje_vetsinovou_vladu", "prioritizuje_nezavislost_soudu"):
                if _dim not in _derived and _dim in frozen_truth:
                    _derived[_dim] = frozen_truth[_dim]
        except Exception:
            pass
TRUTH.update(_derived)


def _bands(p: pd.DataFrame) -> np.ndarray:
    age=pd.to_numeric(p["vek"],errors="coerce").to_numpy(float); out=np.empty(len(p),dtype=object); out[:]=None
    for lab,(lo,hi) in AGE_BANDS.items(): out[(age>=lo)&(age<=hi)]=lab
    return out


def _sex(p: pd.DataFrame) -> np.ndarray:
    return np.where(p["pohlavi"].astype(str).str.lower().str.startswith("mu"),"muz","zena")


def _edu(p: pd.DataFrame) -> np.ndarray:
    inv={v:k for k,v in EDU.items()}; return p["vzdelani"].map(inv).to_numpy()


def fit_probs(p: pd.DataFrame, spec: dict[str, Any], *, holdout: tuple[str,str] | None=None, holdout_axis: str | None=None, iters: int=60, solve_iters: int=40) -> np.ndarray:
    w=pd.to_numeric(p.get("w",p.get("vaha_kalibrovana",1.0)),errors="coerce").fillna(1.0).to_numpy(float)
    dims={}
    if "pohlavi" in spec: dims["pohlavi"]=(_sex(p),spec["pohlavi"])
    if "vek" in spec: dims["vek"]=(_bands(p),spec["vek"])
    if "vzdelani" in spec: dims["vzdelani"]=(_edu(p),spec["vzdelani"])
    if "kraj" in spec: dims["kraj"]=(p["kraj"].astype(str).to_numpy(),spec["kraj"])
    eta=np.full(len(p),norm.ppf(np.clip(float(spec["celkem"])/100,1e-4,1-1e-4))); edu_mask=((pd.to_numeric(p["vek"],errors="coerce")>=25)&(pd.to_numeric(p["vek"],errors="coerce")<=64)).to_numpy()
    def solve(mfit,mapply,target):
        lo,hi=-8.0,8.0
        for _ in range(solve_iters):
            mid=(lo+hi)/2; cur=np.average(norm.cdf(eta[mfit]+mid),weights=w[mfit])
            if cur<target: lo=mid
            else: hi=mid
        eta[mapply]+=(lo+hi)/2
    for _ in range(iters):
        before=eta.copy()
        for dname,(vals,targets) in dims.items():
            if holdout_axis==dname: continue
            for cat,tgt in targets.items():
                if holdout==(dname,cat): continue
                m=vals==cat
                if not m.any(): continue
                mf=m&edu_mask if dname=="vzdelani" else m
                if not mf.any(): mf=m
                solve(mf,m,float(tgt)/100)
        solve(np.ones(len(p),bool),np.ones(len(p),bool),float(spec["celkem"])/100)
        if np.max(np.abs(eta-before))<1e-6: break
    return eta


def residual_latent(p: pd.DataFrame, dcol: str) -> np.ndarray:
    y=pd.to_numeric(p[dcol],errors="coerce").fillna(0).to_numpy(float)
    X=pd.get_dummies(pd.DataFrame({"vek":_bands(p),"vzd":p["vzdelani"].astype(str),"poh":_sex(p),"kraj":p["kraj"].astype(str)}),drop_first=True).to_numpy(float)
    X=np.column_stack([np.ones(len(p)),X]); beta,*_=np.linalg.lstsq(X,y,rcond=None); r=y-X@beta; sd=r.std(); return r/(sd if sd else 1.0)


def recalibrate(p: pd.DataFrame, dimensions: list[str] | None=None) -> pd.DataFrame:
    out=p.copy(); out["w"]=pd.to_numeric(out["vaha_kalibrovana"],errors="coerce").fillna(1.0)
    for dim,spec in TRUTH.items():
        if dimensions and dim not in dimensions: continue
        dcol,mcol=f"D_{dim}",f"M_{dim}"
        if dcol not in out: continue
        eta=fit_probs(out,spec); u=residual_latent(out,dcol); d=eta+u
        out[dcol]=np.round((d-d.mean())/(d.std() or 1),4); out[mcol]=(d>0).astype(int)
    return out.drop(columns=["w"],errors="ignore")


def export_truth(path: str | Path = ROOT/"CONDITIONAL_TRUTH_10_13.json") -> Path:
    path=Path(path); path.write_text(json.dumps(TRUTH,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8"); return path

if __name__ == "__main__":
    print(json.dumps({"n_truth":len(TRUTH),"dimensions":sorted(TRUTH)},ensure_ascii=False,indent=2)); export_truth()
