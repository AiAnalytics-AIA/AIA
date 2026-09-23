"""Permanent blind Research Arena for Full Simulation 10.15."""
from __future__ import annotations
import html,json,time
from pathlib import Path
from typing import Any
import numpy as np

def arena_data(bench_root: Path) -> dict[str,Any]:
    runs=[]
    if bench_root.exists():
        for d in sorted([x for x in bench_root.iterdir() if x.is_dir()],reverse=True):
            try:
                t=json.loads((d/'truth.json').read_text(encoding='utf-8'));s=json.loads((d/'scores.json').read_text(encoding='utf-8'))
            except Exception: continue
            rows=[]
            for m,x in (s.get('methods') or {}).items():
                if x.get('status')=='SCORED': rows.append({'method':m,**x['overall']})
            rows.sort(key=lambda x:x.get('mae_pp',999))
            runs.append({'run_id':d.name,'domain':t.get('domain','general'),'source':t.get('source',''),'eligibility':t.get('benchmark_eligibility'),'methods':rows})
    methods={}
    for r in runs:
        if r['eligibility']!='BLIND_ELIGIBLE': continue
        for x in r['methods']: methods.setdefault(x['method'],[]).append(x)
    summary={m:{'n':len(xs),'mean_mae_pp':round(float(np.mean([x['mae_pp'] for x in xs])),3),'mean_brier':round(float(np.mean([x['brier'] for x in xs])),6)} for m,xs in methods.items()}
    return {'kind':'npc_research_arena_v1','created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'n_runs':len(runs),'methods':summary,'runs':runs}

def write_arena_html(bench_root: Path, out: Path) -> Path:
    a=arena_data(bench_root); rows=''.join(f"<tr><td>{html.escape(m)}</td><td>{x['n']}</td><td>{x['mean_mae_pp']:.2f}</td><td>{x['mean_brier']:.4f}</td></tr>" for m,x in sorted(a['methods'].items(),key=lambda z:z[1]['mean_mae_pp']))
    cards=[]
    for r in a['runs'][:100]:
        rr=''.join(f"<tr><td>{html.escape(x['method'])}</td><td>{x['mae_pp']:.2f}</td><td>{x['tvd_pp']:.2f}</td><td>{x['brier']:.4f}</td></tr>" for x in r['methods'])
        cards.append(f"<section><h3>{html.escape(r['run_id'])} · {html.escape(r['domain'])}</h3><p>{html.escape(r['eligibility'])} · truth: {html.escape(r['source'])}</p><table><tr><th>Metoda</th><th>MAE</th><th>TVD</th><th>Brier</th></tr>{rr}</table></section>")
    doc=f"""<!doctype html><html lang=cs><meta charset=utf-8><title>NPC Research Arena</title><style>body{{font:14px/1.5 system-ui;max-width:1100px;margin:30px auto;padding:0 20px;color:#172033}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:7px;text-align:left}}section{{margin:28px 0}}.note{{padding:10px;border:1px solid #d7dce2}}</style><body><h1>NPC Research Arena</h1><div class=note>Permanentní scoreboard. Blind runy jsou zmrazené před truth; post-hoc metody se do historie nevydávají za predikci.</div><h2>Dlouhodobé pořadí</h2><table><tr><th>Metoda</th><th>Blind benchmarků</th><th>Mean MAE p.b.</th><th>Brier</th></tr>{rows}</table><h2>Jednotlivé arény</h2>{''.join(cards) or '<p>Zatím bez odhalené truth.</p>'}</body></html>"""
    out.write_text(doc,encoding='utf-8');return out
