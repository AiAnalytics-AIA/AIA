from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json, shutil, time
import pandas as pd
from .registry import Registry,sha256_file
from .router import classify
from .harmonization import harmonize_columns,apply_value_dictionary
from .leakage import assert_no_holdout
from .realism import assess
from .versioning import merge_track_a,merge_track_b
from .response_bank import ResponseBank

@dataclass
class IngestDecision:
    track:str; decision:str; version:str|None; report_path:str; metrics:dict[str,Any]


def _read(path:Path)->pd.DataFrame:
    if path.suffix.lower()==".csv":return pd.read_csv(path,low_memory=False)
    if path.suffix.lower() in {".xlsx",".xls"}:return pd.read_excel(path)
    if path.suffix.lower()==".parquet":return pd.read_parquet(path)
    raise ValueError(f"Unsupported ingest format: {path.suffix}")

class IngestManager:
    def __init__(self,*,registry_path="data/ingest_registry.sqlite",default_panel="FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz",
                 quarantine_dir="data/quarantine",versions_dir="data/panel_versions"):
        self.registry=Registry(registry_path); self.default_panel=Path(default_panel); self.quarantine=Path(quarantine_dir); self.versions_dir=Path(versions_dir)
        self.quarantine.mkdir(parents=True,exist_ok=True); self.versions_dir.mkdir(parents=True,exist_ok=True)
        if self.registry.active_version() is None and self.default_panel.exists():
            self.registry.register_version("v15.2",self.default_panel,n_radku=len(pd.read_csv(self.default_panel,usecols=[0])),activate=True,changelog="bootstrap active version")

    def close(self) -> None:
        self.registry.close()

    def __enter__(self) -> "IngestManager":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def active_panel_path(self)->Path:
        a=self.registry.active_version(); return Path(a["cesta"]) if a else self.default_panel

    def ingest(self,path:str|Path,*,track:str|None=None,source_id:str|None=None,description="",
               column_mapping:dict[str,str]|None=None,value_dictionary:dict[str,dict[str,str]]|None=None,
               realism_threshold:dict[str,float]|None=None,override_actor:str|None=None,override_reason:str|None=None,
               response_mappings:list[dict[str,Any]]|None=None,seed=20260814,
               allow_review:bool=False)->IngestDecision:
        p=Path(path); h=sha256_file(p); df=harmonize_columns(_read(p),column_mapping); df,unknown=apply_value_dictionary(df,value_dictionary)
        route=classify(df,p.name,track); src=source_id or p.stem
        report={"file":str(p),"sha256":h,"route":route.__dict__,"unknown_values":unknown,"source_id":src}
        # Track C is always quarantined, never merged and never written to anchor bank.
        if route.track=="C":
            q=self.quarantine/f"{h[:12]}_{p.name}"; shutil.copy2(p,q)
            report.update({"decision":"QUARANTINE","reason":"explicit validation/ground-truth track C"})
            rp=self.quarantine/f"{h[:12]}_report.json"; rp.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
            self.registry.record_upload(hash=h,soubor=str(p),trat="C",popis=description,n_radku=len(df),n_sloupcu=len(df.columns),rozhodnuti="QUARANTINE",duvod=report["reason"],report=str(rp))
            return IngestDecision("C","QUARANTINE",None,str(rp),report)

        assert_no_holdout(df,self.registry,source_id=src)
        active=self.active_panel_path(); ref=pd.read_csv(active,low_memory=False)
        # v15.2 population rows are a Census-calibrated same-person core plus whole donor blocks.
        # Appending arbitrary Track-A rows and copying missing columns from nearest neighbours would
        # destroy that contract. Row-level population sources must be added to the donor/source
        # build and the population rebuilt. Customer/Special Audience data belong in audience_registry.
        if route.track=="A" and {"core_source","core_donor_id"}.issubset(ref.columns):
            report.update({
                "decision":"REBUILD_REQUIRED",
                "reason":"v15.2 population core is immutable under generic Track-A row append; add this source to the donor build or upload it as a Customer/Special Audience dataset.",
                "active_panel":str(active),
            })
            q=self.quarantine/f"{h[:12]}_{p.name}"
            if not q.exists(): shutil.copy2(p,q)
            rp=self.quarantine/f"{h[:12]}_report.json"; rp.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
            self.registry.record_upload(hash=h,soubor=str(p),trat="A",popis=description,n_radku=len(df),n_sloupcu=len(df.columns),rozhodnuti="REBUILD_REQUIRED",duvod=report["reason"],report=str(rp))
            return IngestDecision("A","REBUILD_REQUIRED",None,str(rp),report)
        real=assess(ref,df,threshold=realism_threshold,seed=seed) if route.track=="A" else {"decision":"N/A","statistic":{},"findings":[]}
        report["realism"]=real
        if route.track=="A" and real["decision"] in {"REJECT","REVIEW"} and not (override_actor or (real["decision"]=="REVIEW" and allow_review)):
            # Fail closed. REVIEW means that the realism threshold is not yet calibrated
            # (or evidence is otherwise insufficient); it must never silently create a
            # production panel version. An explicit, audited override is required.
            decision=real["decision"]
            q=self.quarantine/f"{h[:12]}_{p.name}"
            if not q.exists(): shutil.copy2(p,q)
            report.update({"decision":decision,"reason":"realism/domain gate requires calibrated threshold or explicit override"})
            rp=self.quarantine/f"{h[:12]}_report.json"; rp.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
            self.registry.record_upload(hash=h,soubor=str(p),trat="A",popis=description,n_radku=len(df),n_sloupcu=len(df.columns),skore_pravosti=real.get("statistic",{}).get("z"),rozhodnuti=decision,duvod=report["reason"],report=str(rp))
            return IngestDecision("A",decision,None,str(rp),report)
        if override_actor:self.registry.override(h,override_actor,override_reason or "explicit override")
        upload_id=self.registry.record_upload(hash=h,soubor=str(p),trat=route.track,popis=description,n_radku=len(df),n_sloupcu=len(df.columns),skore_pravosti=real.get("statistic",{}).get("z"),rozhodnuti="PROCESSING",duvod="",report="")
        if route.track=="A":
            merged=merge_track_a(df,active,self.registry,upload_id=upload_id,seed=seed,versions_dir=self.versions_dir)
            # Response bank is populated only from explicit mappings; no question semantics are guessed.
            nresp=0
            if response_mappings:
                bank=ResponseBank(self.registry.path)
                try:
                    for m in response_mappings:
                        nresp+=bank.add_responses(df,source_id=src,**m)
                finally:bank.close()
            report.update({"decision":"ACCEPT","merge":merged,"responses_added":nresp})
            version=merged["version"]
        else:
            merged=merge_track_b(df,active,self.registry,upload_id=upload_id,versions_dir=self.versions_dir)
            report.update({"decision":"ACCEPT","merge":merged}); version=merged["version"]
        rp=self.versions_dir/f"ingest_{h[:12]}_report.json"; rp.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        self.registry.record_upload(hash=h,soubor=str(p),trat=route.track,popis=description,n_radku=len(df),n_sloupcu=len(df.columns),skore_pravosti=real.get("statistic",{}).get("z"),rozhodnuti="ACCEPT",duvod="",verze_panelu=version,report=str(rp))
        return IngestDecision(route.track,"ACCEPT",version,str(rp),report)
