from __future__ import annotations
import argparse
from runtime_config import RUN_DEFAULTS, json
from pathlib import Path
from study_contract import StudySpec
from study_engine import run_study

def main():
    ap=argparse.ArgumentParser(description="NPC Panel modul VÝZKUM")
    ap.add_argument("spec"); ap.add_argument("--panel"); ap.add_argument("--out",default="study_outputs")
    ap.add_argument("--mode",choices=["sync","batch","dry"],default=RUN_DEFAULTS["mode"])
    ap.add_argument("--map-method",choices=["auto","r_smacof","python"],default="auto")
    a=ap.parse_args(); spec=json.loads(Path(a.spec).read_text(encoding="utf-8"))
    r=run_study(spec,panel_path=a.panel,mode=a.mode,output_dir=a.out,map_method=a.map_method)
    print(json.dumps({"validation":r["validation"],"files":r["files"]},ensure_ascii=False,indent=2,default=str))
if __name__=="__main__": main()
