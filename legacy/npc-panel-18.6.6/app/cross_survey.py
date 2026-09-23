"""Cross-survey hidden-item benchmark for NPC 10.15.

The target columns are withheld from the prompt. Known answers and basic
respondent descriptors may be supplied.  This is a stricter generalization test
than reproducing survey marginals.  Live mode uses the existing Anthropic
respondent runner; dry mode exists only for plumbing tests.
"""
from __future__ import annotations
import argparse,json,hashlib,time
from pathlib import Path
from typing import Any
import numpy as np, pandas as pd
from pipeline import _call_llm
from dotaznik import Otazka, build_dotaznik_kw, _parse_response
from runtime_config import DEFAULT_MODEL,resolve_model


def run_cross_survey(data: pd.DataFrame, *, known: list[str], targets: list[str], model: str=DEFAULT_MODEL, mode: str="dry", seed: int=1, max_rows: int=500) -> dict[str,Any]:
    df=data.head(max_rows).copy(); rng=np.random.default_rng(seed); results={}
    for qi,target in enumerate(targets):
        if target not in df: continue
        cats=[str(x) for x in pd.Series(df[target]).dropna().astype(str).value_counts().index]
        if len(cats)<2: continue
        o=Otazka(id=target,text=f"Jak byste odpověděl/a na položku {target}?",typ="vyber",kategorie=cats,povolit_nevim=False)
        kws=[]; valid=[]
        for i,row in df.iterrows():
            if pd.isna(row[target]): continue
            bio=[]
            for c in ("pohlavi","vek","vzdelani","kraj"):
                if c in row and pd.notna(row[c]): bio.append(f"{c}: {row[c]}")
            hist="\n".join(f"{c}: {row[c]}" for c in known if c in row and pd.notna(row[c])) or "(žádné známé odpovědi)"
            kws.append(build_dotaznik_kw("\n".join(bio) or "Dospělý člověk z ČR.",[o],historie=hist,response_mode="probability")); valid.append(i)
        raw=_call_llm(kws,resolve_model(model),mode,max_tokens=80,mock=lambda kw,j: json.dumps({"probabilities":(rng.dirichlet(np.ones(len(cats)))).tolist()}))
        correct=[]; brier=[]
        for j,r in enumerate(raw):
            if r.get("chyba"): continue
            rrng=np.random.default_rng(seed+qi*10007+j)
            val,meta=_parse_response(r["text"],o,"probability",rrng)
            truth=str(df.loc[valid[j],target]); correct.append(str(val)==truth)
            probs=np.array(meta.get("probabilities") or [1/len(cats)]*len(cats),float); one=np.array([1. if c==truth else 0. for c in cats]); brier.append(float(np.sum((probs-one)**2)))
        results[target]={"n":len(correct),"accuracy":round(float(np.mean(correct)),4) if correct else None,"mean_brier":round(float(np.mean(brier)),6) if brier else None,"categories":cats}
    out={"kind":"npc_cross_survey_benchmark_v1","created_at":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),"mode":mode,"model":resolve_model(model),"known":known,"targets":targets,"results":results}
    out["sha256"]=hashlib.sha256(json.dumps(out,sort_keys=True,ensure_ascii=False).encode()).hexdigest(); return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument('csv');ap.add_argument('--known',required=True);ap.add_argument('--targets',required=True);ap.add_argument('--mode',default='dry');ap.add_argument('--model',default=DEFAULT_MODEL);ap.add_argument('-o','--out',default='cross_survey_result.json');a=ap.parse_args()
    out=run_cross_survey(pd.read_csv(a.csv),known=[x for x in a.known.split(',') if x],targets=[x for x in a.targets.split(',') if x],mode=a.mode,model=a.model);Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
