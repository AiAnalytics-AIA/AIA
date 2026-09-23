from __future__ import annotations
import argparse,json,tempfile
from pathlib import Path
import pandas as pd
from npc_ingest import IngestManager


def _json_obj(value):
    if not value:return None
    p=Path(value)
    raw=p.read_text(encoding="utf-8") if p.exists() else value
    return json.loads(raw)


def main():
    ap=argparse.ArgumentParser(description="NPC Panel INGEST A/B/C")
    ap.add_argument("file")
    ap.add_argument("--track",choices=["A","B","C"])
    ap.add_argument("--source")
    ap.add_argument("--description",default="")
    ap.add_argument("--registry",default="data/ingest_registry.sqlite")
    ap.add_argument("--panel",default="FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz")
    ap.add_argument("--column-mapping",help="JSON string or path")
    ap.add_argument("--value-dictionary",help="JSON string or path")
    ap.add_argument("--realism-threshold",help="JSON string or path, e.g. {\"pmse_z_max\":3.1}")
    ap.add_argument("--response-mappings",help="JSON list or path for response-bank mappings")
    ap.add_argument("--allow-review",action="store_true",help="explicitly allow Track-A REVIEW (audit only)")
    ap.add_argument("--override-actor")
    ap.add_argument("--override-reason")
    ap.add_argument("--confirmed-pdf-targets",action="store_true",
                    help="input is a reviewed CSV draft from PDF extraction; all confirmed must be true")
    ap.add_argument("--pdf-draft-out",help="for Track-B PDF: write structured draft here; never merges")
    ap.add_argument("--model",help="Anthropic extraction model for Track-B PDF draft")
    a=ap.parse_args()
    src=Path(a.file)

    if src.suffix.lower()==".pdf":
        if a.track not in {None,"B"}: raise SystemExit("PDF extraction is Track B only")
        from pdf_targets import draft_targets
        out=Path(a.pdf_draft_out or (src.stem+"_targets_draft.csv"))
        draft=draft_targets(src,model=a.model); draft.to_csv(out,index=False)
        print(json.dumps({"decision":"REVIEW_CONFIRMATION","track":"B","draft":str(out),
                          "note":"Nothing merged. Review rows and set confirmed=true, then ingest the CSV with --confirmed-pdf-targets."},ensure_ascii=False,indent=2))
        return 0

    temp_path=None
    if a.confirmed_pdf_targets:
        from pdf_targets import confirmed_targets
        draft=pd.read_csv(src)
        target=confirmed_targets(draft)
        tf=tempfile.NamedTemporaryFile(suffix=".csv",delete=False); tf.close(); temp_path=Path(tf.name)
        target.to_csv(temp_path,index=False); src=temp_path
        a.track="B"

    m=IngestManager(registry_path=a.registry,default_panel=a.panel)
    try:
        r=m.ingest(src,track=a.track,source_id=a.source,description=a.description,
                   column_mapping=_json_obj(a.column_mapping),value_dictionary=_json_obj(a.value_dictionary),
                   realism_threshold=_json_obj(a.realism_threshold),override_actor=a.override_actor,
                   override_reason=a.override_reason,response_mappings=_json_obj(a.response_mappings),
                   allow_review=a.allow_review)
        print(json.dumps(r.__dict__,ensure_ascii=False,indent=2,default=str))
        return 0
    finally:
        m.registry.close()
        if temp_path:
            temp_path.unlink(missing_ok=True)

if __name__=="__main__": raise SystemExit(main())
