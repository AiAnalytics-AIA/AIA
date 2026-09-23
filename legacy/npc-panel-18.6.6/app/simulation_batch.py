"""Multi-variant Full Simulation orchestration and client-facing comparison outputs."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from provider_runtime import normalize_live_provider
import hashlib, html, json, math, time, zipfile
import pandas as pd

ROOT=Path(__file__).resolve().parent
BATCH_ROOT=ROOT/'full_simulation_batches'
BATCH_ROOT.mkdir(parents=True,exist_ok=True)


def _now()->str:return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def _id()->str:return 'SIMB-'+time.strftime('%Y%m%d-%H%M%S')+'-'+hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:8]
def _sha(obj:Any)->str:return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def _primary_method(pred:dict[str,Any])->str:
    m=str(pred.get('primary_method') or '')
    if m and m in (pred.get('methods') or {}):return m
    methods=pred.get('methods') or {}
    for k in methods:
        if k.startswith('NPC_SIM') or k=='FULL_SIMULATION':return k
    return next(iter(methods),'')


def _rows_for_variant(variant:dict[str,Any],run:dict[str,Any])->list[dict[str,Any]]:
    pred=run.get('prediction') or {}; methods=pred.get('methods') or {}; pm=_primary_method(pred)
    sim=methods.get(pm) or {}; base=methods.get('NPC_CORE') or {}
    rows=[]
    qids=sorted(set((sim.get('questions') or {}))|set((base.get('questions') or {})))
    meta=variant.get('variant') or {}
    for qid in qids:
        sq=(sim.get('questions') or {}).get(qid) or {}; bq=(base.get('questions') or {}).get(qid) or {}
        cats=sorted(set(sq.get('estimate_pct') or {})|set(bq.get('estimate_pct') or {}))
        for cat in cats:
            sv=float((sq.get('estimate_pct') or {}).get(cat,0) or 0); bv=float((bq.get('estimate_pct') or {}).get(cat,0) or 0)
            ci=(sq.get('interval_95') or {}).get(cat) or {}
            rows.append({'variant_id':meta.get('id'),'variant_label':meta.get('label'),'variable':meta.get('variable'),'value':meta.get('value'),'unit':meta.get('unit'),
                         'question_id':qid,'question':sq.get('text') or bq.get('text') or qid,'category':cat,
                         'simulation_pct':round(sv,4),'baseline_core_pct':round(bv,4),'delta_pp':round(sv-bv,4),
                         'interval_low':ci.get('low'),'interval_high':ci.get('high'),'primary_method':pm,
                         'run_id':run.get('run_id'),'run_status':pred.get('run_status')})
    return rows


def response_curve_diagnostics(df:pd.DataFrame)->list[dict[str,Any]]:
    out=[]
    if df.empty:return out
    for (qid,cat),g in df.groupby(['question_id','category'],dropna=False):
        gg=g.copy(); gg['_num']=pd.to_numeric(gg['value'],errors='coerce'); gg=gg.dropna(subset=['_num']).sort_values('_num')
        if len(gg)<2:continue
        x=gg['_num'].to_numpy(float); y=gg['delta_pp'].to_numpy(float)
        slopes=[]
        for i in range(1,len(x)):
            dx=x[i]-x[i-1]
            if abs(dx)>1e-12:slopes.append(float((y[i]-y[i-1])/dx))
        curvature=None
        if len(slopes)>=2:curvature=max(slopes)-min(slopes)
        signs=[0 if abs(v)<1e-9 else (1 if v>0 else -1) for v in slopes]
        nonlin=bool(curvature is not None and abs(curvature)>0.05) or len(set(s for s in signs if s))>1
        out.append({'question_id':qid,'question':str(gg.iloc[0]['question']),'category':cat,'points':len(gg),
                    'min_value':float(x.min()),'max_value':float(x.max()),'slopes_pp_per_unit':[round(v,5) for v in slopes],
                    'curvature_score':None if curvature is None else round(float(curvature),5),
                    'monotonic':len(set(s for s in signs if s))<=1,'nonlinear_signal':nonlin})
    return out


def _comparison_schema()->dict[str,Any]:
    return {'type':'object','properties':{
        'executive_summary':{'type':'string'},'decision_answer':{'type':'string'},'best_option':{'type':'string'},
        'tradeoffs':{'type':'array','items':{'type':'string'}},'nonlinear_effects':{'type':'array','items':{'type':'string'}},
        'brand_risks':{'type':'array','items':{'type':'string'}},'segment_implications':{'type':'array','items':{'type':'string'}},
        'uncertainties':{'type':'array','items':{'type':'string'}},'recommendations':{'type':'array','items':{'type':'string'}},
        'do_not_overclaim':{'type':'array','items':{'type':'string'}},
    },'required':['executive_summary','decision_answer','best_option','tradeoffs','nonlinear_effects','brand_risks','segment_implications','uncertainties','recommendations','do_not_overclaim'],'additionalProperties':False}


def _deterministic_interpretation(rows:list[dict[str,Any]],diagnostics:list[dict[str,Any]],context:dict[str,Any])->dict[str,Any]:
    return {'executive_summary':'Technický dry-run porovnání variant. Klientská interpretace vyžaduje LIVE Claude běh.',
            'decision_answer':'Dry-run neposkytuje klientské rozhodovací doporučení.','best_option':'Nehodnoceno v dry-run.',
            'tradeoffs':[],'nonlinear_effects':[f"{x['question']} / {x['category']}: nelineární signál" for x in diagnostics if x.get('nonlinear_signal')][:8],
            'brand_risks':[],'segment_implications':[],'uncertainties':[u.get('question') for u in context.get('uncertainties',[]) if u.get('status')!='RESOLVED'][:10],
            'recommendations':[],'do_not_overclaim':['Dry-run je technický test, nikoli klientská predikce.']}


def _ai_interpret(rows:list[dict[str,Any]],diagnostics:list[dict[str,Any]],context:dict[str,Any],contracts:list[dict[str,Any]],*,model='sonnet',provider='claude_code_subscription')->dict[str,Any]:
    from ai_router import call_structured
    payload={'context':{k:v for k,v in context.items() if k not in {'evidence','data_library'}},'evidence':((context.get('evidence') or {}).get('accepted') or [])[:24],'variants':[{'variant':c.get('variant'),'assumptions':c.get('assumptions'),'unknowns':c.get('unknowns'),'shifts':c.get('shifts')} for c in contracts],
             'results':rows,'response_curve_diagnostics':diagnostics}
    system="""Jsi seniorní strategy consultant. Interpretuješ už HOTOVÉ výsledky několika nezávisle simulovaných variant.
Nevymýšlej čísla ani kauzalitu mimo payload. Nepředpokládej lineární cenu/poptávku: explicitně zvaž prahy, reference price, quality/premium signal, brand equity, promo habituation, competitor response, channel economics a segmentovou heterogenitu, ale tvrď je jen pokud jsou podpořené context/contract/result daty.
Odděl modelovaný výsledek, mechanismus, nejistotu a doporučení. Pokud nejlepší varianta není jednoznačná, řekni to. Výstup má být použitelný v klientském reportu."""
    r=call_structured(system=system,messages=[{'role':'user','content':json.dumps(payload,ensure_ascii=False,default=str)}],schema=_comparison_schema(),schema_name='npc_simulation_batch_interpretation',anthropic_model=model,max_tokens=5000,prefer=provider,allow_fallback=False,timeout=420)
    return r.get('data') or {}


def _write_html(path:Path,batch:dict[str,Any],df:pd.DataFrame)->Path:
    interp=batch.get('interpretation') or {}; variants=batch.get('variants') or []
    def esc(x):return html.escape(str(x if x is not None else ''))
    cards=''.join(f"<div class='card'><h3>{esc(v.get('label'))}</h3><p>{esc(v.get('change'))}</p><small>run {esc(v.get('run_id'))}</small></div>" for v in variants)
    rows=''.join(f"<tr><td>{esc(r.variant_label)}</td><td>{esc(r.question)}</td><td>{esc(r.category)}</td><td>{r.simulation_pct:.1f}%</td><td>{r.baseline_core_pct:.1f}%</td><td>{r.delta_pp:+.1f} p.b.</td></tr>" for r in df.itertuples())
    bullet=lambda xs:''.join(f'<li>{esc(x)}</li>' for x in (xs or [])) or '<li>—</li>'
    h=f"""<!doctype html><html lang='cs'><head><meta charset='utf-8'><title>Simulation comparison</title><style>body{{font:15px/1.5 system-ui;max-width:1180px;margin:30px auto;padding:0 24px;color:#172033}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.card{{border:1px solid #dce1e8;border-radius:14px;padding:14px}}table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #ddd;padding:7px;text-align:left}}.mut{{color:#687284}}.flag{{padding:5px 9px;border-radius:6px;background:#fff3d6;display:inline-block}}</style></head><body><div class='flag'>MODELLED SCENARIO COMPARISON · NOT CERTAIN FORECAST</div><h1>{esc(batch.get('title') or 'Porovnání simulací')}</h1><p>{esc(interp.get('executive_summary'))}</p><h2>Rozhodovací odpověď</h2><p><b>{esc(interp.get('decision_answer'))}</b></p><p>Nejlepší varianta: <b>{esc(interp.get('best_option'))}</b></p><div class='grid'>{cards}</div><h2>Co není lineární / na co pozor</h2><ul>{bullet(interp.get('nonlinear_effects'))}</ul><h2>Trade-offs</h2><ul>{bullet(interp.get('tradeoffs'))}</ul><h2>Brand risks</h2><ul>{bullet(interp.get('brand_risks'))}</ul><h2>Segmenty</h2><ul>{bullet(interp.get('segment_implications'))}</ul><h2>Nejistoty</h2><ul>{bullet(interp.get('uncertainties'))}</ul><h2>Doporučení</h2><ul>{bullet(interp.get('recommendations'))}</ul><h2>Použitá evidence</h2><ul>{''.join(f'<li><b>{esc(x.get("source_title") or "Zdroj")}</b> — {esc(x.get("claim") or "")}' + (f' · <a href="{esc(x.get("source_url"))}">zdroj</a>' if x.get('source_url') else '') + '</li>' for x in (((batch.get('context') or {}).get('evidence') or {}).get('accepted') or [])[:20]) or '<li>Bez externí evidence v tomto běhu.</li>'}</ul><h2>Výsledkový dataset</h2><table><thead><tr><th>Varianta</th><th>Otázka</th><th>Odpověď</th><th>Simulace</th><th>Baseline Core</th><th>Δ</th></tr></thead><tbody>{rows}</tbody></table><p class='mut'>Varianty byly simulovány nezávisle nad společným evidence/context packem. Křivka není lineárně interpolována. Frozen run artefakty jednotlivých variant zůstávají auditovatelné.</p></body></html>"""
    path.write_text(h,encoding='utf-8');return path



def _fallback_batch_html(path:Path,batch:dict[str,Any],df:pd.DataFrame,reason:str='')->Path:
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);e=lambda x:html.escape(str(x or ''))
    rows=''.join(f'<tr><td>{e(r.get("variant_label"))}</td><td>{e(r.get("question"))}</td><td>{e(r.get("category"))}</td><td>{e(r.get("simulation_pct"))}</td><td>{e(r.get("delta_pp"))}</td></tr>' for r in df.to_dict('records'))
    txt=f'''<!doctype html><meta charset="utf-8"><style>body{{font:15px/1.6 Arial;max-width:1100px;margin:30px auto;padding:20px}}.warn{{background:#fff4d6;padding:12px}}table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px solid #ddd;padding:7px}}</style><div class="warn">Nouzový srovnávací report. Frozen varianty a výsledkový dataset jsou zachované. {e(reason)}</div><h1>{e(batch.get('title') or 'Porovnání simulací')}</h1><table><tr><th>Varianta</th><th>Otázka</th><th>Kategorie</th><th>Simulace %</th><th>Δ p.b.</th></tr>{rows}</table>'''
    p.write_text(txt,encoding='utf-8');return p

def run_simulation_batch(spec:dict[str,Any],contracts:list[dict[str,Any]],*,project:dict[str,Any]|None=None,panel_path:str|Path|None=None,
                         context:dict[str,Any]|None=None,confirm_live:bool=False,progress=None)->dict[str,Any]:
    from full_simulation import prepare_full_simulation,run_full_simulation,validate_full_simulation_result
    _progress=progress if callable(progress) else (lambda _x:None)
    if len(contracts)<2: raise ValueError('Batch simulace vyžaduje alespoň dvě varianty.')
    if any(str(c.get('status') or '')!='APPROVED' for c in contracts): raise ValueError('Všechny varianty musí být schválené.')
    mode=str(spec.get('mode') or 'sync')
    if mode!='dry' and not confirm_live: raise ValueError('Batch simulace vyžaduje potvrzení LIVE běhu.')
    if mode!='dry':
        spec['provider']=normalize_live_provider(spec.get('provider') or 'claude_code_subscription')
    batch_id=_id(); d=BATCH_ROOT/batch_id; d.mkdir(parents=True,exist_ok=False)
    ctx=context or (project or {}).get('simulation_context') or {}
    evidence=(ctx.get('evidence') or {}) if isinstance(ctx,dict) else {}
    artifact_warnings=[]
    runs=[]; all_rows=[]; shared_core_baseline=None
    total=len(contracts)
    for i,c in enumerate(contracts,1):
        v=c.get('variant') or {}; label=str(v.get('label') or f'Varianta {i}')
        _progress(f'Batch Simulation · varianta {i}/{total} · world model · {label}')
        vs=deepcopy(spec); vs['scenario_contract']=c; vs['topic']=f"{spec.get('topic') or 'Simulace'} · {label}"
        # Variant-specific seeds guarantee independent worlds while preserving deterministic reruns.
        vs['seed']=int(spec.get('seed') or 42)+i*100003
        prep=prepare_full_simulation(vs,panel_path=panel_path,existing_research=evidence,progress=_progress)
        _progress(f'Batch Simulation · varianta {i}/{total} · světy · {label}')
        rr=run_full_simulation(vs,panel_path=panel_path,prepared=prep,core_baseline_override=shared_core_baseline,progress=_progress)
        rr=validate_full_simulation_result(rr,require_core_baseline=bool(vs.get('include_core_baseline',True)),allow_invalid_dry=(mode=='dry'))
        if bool(vs.get('include_core_baseline',True)) and shared_core_baseline is None:
            shared_core_baseline=deepcopy(((rr.get('prediction') or {}).get('methods') or {}).get('NPC_CORE') or None)
            if not shared_core_baseline:
                raise RuntimeError('FULLSIM_BATCH_SHARED_BASELINE_MISSING')
        all_rows.extend(_rows_for_variant(c,rr))
        runs.append({'variant':v,'contract_sha256':_sha(c),'run_id':rr.get('run_id'),'run_dir':rr.get('run_dir'),'report_html':rr.get('report_html'),'prediction':rr.get('prediction'),'manifest':rr.get('manifest'),'artifact_gate':rr.get('artifact_gate')})
    df=pd.DataFrame(all_rows); diagnostics=response_curve_diagnostics(df)
    _progress('Batch Simulation · porovnávám varianty a hledám nelinearity')
    if mode=='dry' or not bool(spec.get('comparison_ai',True)):
        interp=_deterministic_interpretation(all_rows,diagnostics,ctx)
    else:
        try: interp=_ai_interpret(all_rows,diagnostics,ctx,contracts,model=str(spec.get('model') or 'sonnet'),provider=str(spec.get('provider') or 'claude_code_subscription'))
        except Exception as exc:
            artifact_warnings.append({'artifact':'comparison_ai_interpretation','error':str(exc)[:800]})
            interp=_deterministic_interpretation(all_rows,diagnostics,ctx)
            interp['executive_summary']='AI interpretace porovnání nebyla dostupná; klientský balík byl dokončen z frozen výsledků a deterministické diagnostiky.'
    title=str((ctx or {}).get('title') or (project or {}).get('title') or spec.get('topic') or 'Porovnání simulací')
    batch={'kind':'npc_fullsim_batch_v1','batch_id':batch_id,'created_at':_now(),'title':title,'context_sha256':(ctx or {}).get('sha256'),'variants':[],
           'curve_diagnostics':diagnostics,'interpretation':interp,'nonlinearity_policy':'Independent variant simulations; no linear interpolation.','baseline_policy':'One shared frozen NPC_CORE reference; independent scenario world models and worlds.','mode':mode,'context':{'summary':ctx.get('summary'),'uncertainties':ctx.get('uncertainties') or [],'evidence':{'accepted':(evidence.get('accepted') or [])[:30],'quality_status':evidence.get('quality_status')}}}
    for c,r in zip(contracts,runs):
        batch['variants'].append({**(c.get('variant') or {}),'run_id':r.get('run_id'),'report_html':r.get('report_html'),'artifact_gate':r.get('artifact_gate')})
    csv=d/'simulation_comparison.csv'; df.to_csv(csv,index=False,encoding='utf-8-sig')
    xlsx=d/'SIMULATION_COMPARISON.xlsx'
    try:
        with pd.ExcelWriter(xlsx,engine='openpyxl') as w:
            df.to_excel(w,index=False,sheet_name='Results')
            pd.DataFrame(diagnostics).to_excel(w,index=False,sheet_name='Response curves')
            pd.DataFrame(batch['variants']).to_excel(w,index=False,sheet_name='Variants')
            pd.DataFrame([{'section':k,'value':json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v} for k,v in interp.items()]).to_excel(w,index=False,sheet_name='Interpretation')
            pd.DataFrame((evidence.get('accepted') or [])[:100]).to_excel(w,index=False,sheet_name='Evidence')
            pd.DataFrame(ctx.get('uncertainties') or []).to_excel(w,index=False,sheet_name='Uncertainties')
    except Exception as exc:
        artifact_warnings.append({'artifact':'batch_xlsx','error':str(exc)[:800]})
        from openpyxl import Workbook
        wb=Workbook();ws=wb.active;ws.title='Results';ws.append(list(df.columns))
        for row in df.itertuples(index=False,name=None):ws.append(list(row))
        wb.save(xlsx)
    try: report=_write_html(d/'SIMULATION_COMPARISON_REPORT.html',batch,df)
    except Exception as exc:
        artifact_warnings.append({'artifact':'batch_report_html','error':str(exc)[:800]})
        report=_fallback_batch_html(d/'SIMULATION_COMPARISON_REPORT.html',batch,df,str(exc))
    js=d/'simulation_batch.json'; manifest_path=d/'batch_manifest.json'; delivery=d/'SIMULATION_BATCH_CLIENT_DELIVERY.zip'
    batch['artifacts']={'csv':str(csv),'xlsx':str(xlsx),'report_html':str(report),'batch_json':str(js),'audit_json':str(js),'manifest_json':str(manifest_path),'client_delivery_zip':str(delivery),'directory':str(d)}
    batch['runs']=runs
    batch['artifact_warnings']=artifact_warnings
    batch['results_status']='RESULTS_READY_DEGRADED_EXPORT' if artifact_warnings else 'RESULTS_READY'
    batch['sha256']=_sha({k:v for k,v in batch.items() if k not in {'runs','sha256'}})
    manifest={'kind':'npc_simulation_batch_manifest_v1','batch_id':batch_id,'created_at':_now(),'batch_sha256':batch['sha256'],'variant_count':len(runs),
              'variant_run_ids':[r.get('run_id') for r in runs],'context_sha256':batch.get('context_sha256'),'artifacts':{k:str(v) for k,v in batch['artifacts'].items()},
              'policy':'client-ready comparison only after every variant passes frozen artifact gate'}
    manifest['manifest_sha256']=_sha(manifest)
    batch['manifest']=manifest
    batch['artifact_gate']={'status':'PASS','variant_count':len(runs),'frozen_variants':all((r.get('artifact_gate') or {}).get('status')=='PASS' for r in runs),'client_outputs':[str(csv),str(xlsx),str(report),str(js),str(manifest_path),str(delivery)]}
    # Write the canonical final metadata BEFORE creating the delivery ZIP so the ZIP
    # never contains a pre-gate draft of simulation_batch.json / batch_manifest.json.
    js.write_text(json.dumps(batch,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    _progress('Batch Simulation · balím klientský delivery ZIP')
    checks=[]
    with zipfile.ZipFile(delivery,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for q in (csv,xlsx,report,js,manifest_path):
            z.write(q,q.name); checks.append(f'{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}')
        for c,r in zip(contracts,runs):
            label=str((c.get('variant') or {}).get('id') or r.get('run_id') or 'variant')
            rd=Path(str(r.get('run_dir') or ''))
            for name in ('FULL_SIMULATION_REPORT.html','SIMULATION_RESULTS.csv','SIMULATION_RESULTS.xlsx','prediction.json','prediction_manifest.json','FROZEN.lock'):
                q=rd/name
                if q.is_file():
                    arc=f'variants/{label}/{name}'; z.write(q,arc); checks.append(f'{hashlib.sha256(q.read_bytes()).hexdigest()}  {arc}')
        z.writestr('DELIVERY_SHA256SUMS.txt','\n'.join(checks)+'\n')
        z.writestr('DELIVERY_NOTE.txt','Independent scenario variants over one shared frozen NPC Core baseline. Each scenario is modelled independently; this is not linear interpolation and not a certain forecast.\n')
    required=[csv,xlsx,report,js,manifest_path,delivery]
    if any((not q.is_file()) or q.stat().st_size<=0 for q in required) or not batch['artifact_gate']['frozen_variants']:
        raise RuntimeError('FULLSIM_BATCH_ARTIFACT_GATE_FAILED')
    _progress('Batch Simulation · hotovo · dataset, Excel, delivery ZIP a klientský report připraveny')
    return batch
