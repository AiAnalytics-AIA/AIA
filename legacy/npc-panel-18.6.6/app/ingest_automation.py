"""Filesystem automation adapter for batch ingest (F6).

Designed for cron/Task Scheduler/Systemd. It performs one deterministic scan and
never starts a hidden background daemon. Tabular files can be processed end-to-end;
PDF Track-B sources are converted only to pending drafts requiring human confirmation.
"""
from __future__ import annotations
from pathlib import Path
import json,shutil,time
from npc_ingest.manager import IngestManager

SUPPORTED={".csv",".xlsx",".xls",".parquet",".pdf"}
def process_inbox(inbox="data/inbox",archive="data/inbox_archive",*,manager=None,default_track=None,
                  pending_confirmation="data/pending_confirmation")->list[dict]:
    ib=Path(inbox); ar=Path(archive); pc=Path(pending_confirmation)
    ib.mkdir(parents=True,exist_ok=True); ar.mkdir(parents=True,exist_ok=True); pc.mkdir(parents=True,exist_ok=True)
    own_manager = manager is None
    manager = manager or IngestManager()
    results=[]
    for p in sorted(x for x in ib.iterdir() if x.is_file() and x.suffix.lower() in SUPPORTED):
        try:
            if p.suffix.lower()==".pdf":
                if default_track not in {None,"B"}: raise ValueError("PDF inbox item can only use Track B")
                from pdf_targets import draft_targets
                draft=draft_targets(p); out=pc/f"{p.stem}_targets_draft.csv"; draft.to_csv(out,index=False)
                rec={"file":p.name,"track":"B","decision":"REVIEW_CONFIRMATION","draft":str(out)}
                shutil.move(str(p),ar/(time.strftime("%Y%m%d-%H%M%S_")+p.name))
            else:
                r=manager.ingest(p,track=default_track)
                rec={"file":p.name,"track":r.track,"decision":r.decision,"version":r.version,"report":r.report_path}
                if r.decision=="ACCEPT": shutil.move(str(p),ar/(time.strftime("%Y%m%d-%H%M%S_")+p.name))
        except Exception as e:
            rec={"file":p.name,"decision":"ERROR","error":str(e)[:500]}
        results.append(rec)
    log=Path("data/inbox_last_run.json");log.parent.mkdir(parents=True,exist_ok=True);log.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    if own_manager:
        manager.close()
    return results
