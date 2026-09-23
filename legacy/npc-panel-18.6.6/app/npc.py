#!/usr/bin/env python3
"""Canonical CLI entrypoint for NPC Panel 17.1.2."""
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path

def _forward(script,args):
    args=list(args);args=args[1:] if args and args[0]=='--' else args
    return subprocess.call([sys.executable,str(Path(__file__).with_name(script)),*args])

def main(argv=None):
    ap=argparse.ArgumentParser(prog='npc',description='NPC Panel — UI, survey, VÝZKUM, segmenty, ingest a validace')
    sub=ap.add_subparsers(dest='cmd',required=True)
    for name,helptext in [('survey','run standard survey'),('study','run VÝZKUM'),('ingest','ingest A/B/C')]:
        s=sub.add_parser(name,help=helptext);s.add_argument('file');s.add_argument('args',nargs=argparse.REMAINDER)
    s=sub.add_parser('ui',help='start product web UI');s.add_argument('args',nargs=argparse.REMAINDER)
    s=sub.add_parser('fullsim',help='Full Simulation Lab: prepare/run/freeze/benchmark');s.add_argument('args',nargs=argparse.REMAINDER)
    s=sub.add_parser('arena',help='build/open permanent Research Arena');s.add_argument('--bench-root',default='full_simulation_benchmarks');s.add_argument('--out',default='full_simulation_benchmarks/RESEARCH_ARENA.html')
    s=sub.add_parser('cross-survey',help='hidden-item cross-survey benchmark');s.add_argument('csv');s.add_argument('--known',required=True);s.add_argument('--targets',required=True);s.add_argument('--mode',default='dry');s.add_argument('--model',default='haiku');s.add_argument('-o','--out',default='cross_survey_result.json')
    s=sub.add_parser('doctor');s.add_argument('args',nargs=argparse.REMAINDER)
    s=sub.add_parser('evidence');s.add_argument('--panel',default='FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz');s.add_argument('--out',default='EFFECTIVE_EVIDENCE_AUDIT_v17.csv')
    s=sub.add_parser('joint',help='run v17.1.2 coherence audit and show structural joint contract');s.add_argument('--panel',default='FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz');s.add_argument('--out',default='COHERENCE_AUDIT_v17_1.csv')
    s=sub.add_parser('questions');s.add_argument('--store',default='data/run_store.sqlite');s.add_argument('--limit',type=int,default=100)
    s=sub.add_parser('history');s.add_argument('question_id',nargs='?');s.add_argument('--store',default='data/run_store.sqlite');s.add_argument('--limit',type=int,default=100)
    s=sub.add_parser('audience');s.add_argument('brief');s.add_argument('--panel',default='FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz')
    s=sub.add_parser('validita');s.add_argument('brief');s.add_argument('--panel',default='FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz')
    a=ap.parse_args(argv)
    if a.cmd=='survey':return _forward('run.py',[a.file,*a.args])
    if a.cmd=='study':return _forward('study_cli.py',[a.file,*a.args])
    if a.cmd=='ingest':return _forward('ingest_cli.py',[a.file,*a.args])
    if a.cmd=='ui':return _forward('ui_server.py',a.args)
    if a.cmd=='fullsim':return _forward('full_simulation.py',a.args)
    if a.cmd=='cross-survey':return _forward('cross_survey.py',[a.csv,'--known',a.known,'--targets',a.targets,'--mode',a.mode,'--model',a.model,'--out',a.out])
    if a.cmd=='arena':
        from research_arena import write_arena_html
        out=write_arena_html(Path(a.bench_root),Path(a.out));print(out);return 0
    if a.cmd=='doctor':return _forward('doctor.py',a.args)
    if a.cmd=='joint':
        rc=_forward('coherence_audit_v17.py',['--panel',a.panel,'--out',a.out])
        if rc==0:
            from core_joint import load_joint_status
            print(json.dumps(load_joint_status(),ensure_ascii=False,indent=2))
        return rc
    if a.cmd=='evidence':
        import pandas as pd
        from effective_evidence_audit import audit
        d=audit(pd.read_csv(a.panel,low_memory=False));d.to_csv(a.out,index=False);print(a.out);return 0
    if a.cmd in {'questions','history'}:
        from run_store import RunStore
        rs=RunStore(a.store)
        try:
            obj=rs.list_questions(a.limit) if a.cmd=='questions' else (rs.question_history(a.question_id,a.limit) if a.question_id else rs.list_runs(a.limit))
            print(json.dumps(obj,ensure_ascii=False,indent=2,default=str));return 0
        finally:rs.close()
    if a.cmd in {'audience','validita'}:
        import pandas as pd
        b=json.loads(Path(a.brief).read_text(encoding='utf-8'));df=pd.read_csv(a.panel,low_memory=False)
        filtry={k:(tuple(v) if isinstance(v,list) and len(v)==2 and all(isinstance(x,(int,float)) for x in v) else v) for k,v in (b.get('filtry') or {}).items()}
        if a.cmd=='audience':
            from audience import feasibility
            print(json.dumps(feasibility(df,filtry,int(b.get('n',120))),ensure_ascii=False,indent=2));return 0
        import ui_server
        print(json.dumps(ui_server.preflight(b)['validity'],ensure_ascii=False,indent=2,default=str));return 0
    return 2
if __name__=='__main__':raise SystemExit(main())
