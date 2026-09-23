"""Standalone offline HTML protocol for NPC Panel 10.13.

The protocol is intentionally dependency-free.  Quantitative research outputs are
rendered as point + interval + evidence rating.  Synthetic/derived estimates use a
hatched confidence band.  Cells below the Kish effective-n guard are suppressed.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
import json

from fidelity import evidence_rating, falsification_condition


def _fmt(x: Any, decimals: int=0) -> str:
    try:
        return f"{float(x):.{decimals}f}"
    except Exception:
        return "—"


def _decimals(lo: float, hi: float) -> int:
    try: return 1 if abs(float(hi)-float(lo)) < 2 else 0
    except Exception: return 0


def _rating_dot(rating: str) -> str:
    return f"<span class='evidence {escape(str(rating).lower())}' title='Evidence {escape(str(rating))}'></span>"


def _band(label: str, estimate: Any, interval: dict|None, *, rating: str='AMBER', unit: str='%', synthetic: bool=True) -> str:
    if not interval or interval.get('low') is None or interval.get('high') is None:
        return f"<div class='measure missing'><span>{escape(str(label))}</span><b>interval není k dispozici — hodnota se nezobrazuje</b>{_rating_dot('RED')}</div>"
    lo=float(interval['low']); hi=float(interval['high']); est=float(estimate); d=_decimals(lo,hi)
    # Visual position uses the local interval window rather than a misleading zero baseline.
    span=max(hi-lo, 1e-9); pad=max(span*.35, 1.0 if unit=='%' else span*.2); mn=lo-pad; mx=hi+pad
    left=max(0,min(100,100*(lo-mn)/(mx-mn))); width=max(1,min(100-left,100*(hi-lo)/(mx-mn))); point=max(0,min(100,100*(est-mn)/(mx-mn)))
    cls='hatched' if synthetic else 'solid'
    return (f"<div class='measure'><div class='measure-head'><span>{escape(str(label))}</span>"
            f"<strong>{_fmt(est,d)}{escape(unit)} <small>({_fmt(lo,d)}–{_fmt(hi,d)}{escape(unit)})</small></strong>{_rating_dot(rating)}</div>"
            f"<div class='track'><span class='ci {cls}' style='left:{left:.2f}%;width:{width:.2f}%'></span><span class='point' style='left:{point:.2f}%'></span></div></div>")


def _distribution(title: str, pct: dict, intervals: dict, rating: str, effective_n: float, threshold: float) -> str:
    out=[f"<h3>{escape(title)}</h3>"]
    if float(effective_n or 0) < float(threshold or 50):
        out.append("<div class='suppressed'>málo pozorování — zvětšete vzorek</div>")
        return ''.join(out)
    for k,v in sorted((pct or {}).items(), key=lambda x:-float(x[1])):
        out.append(_band(str(k),v,(intervals or {}).get(k),rating=rating,unit='%',synthetic=True))
    return ''.join(out)


def _segment_tables(a: dict, rating: str) -> str:
    chunks=[]
    for key,tab in a.items():
        if not str(key).startswith('podle_') or not isinstance(tab,dict): continue
        chunks.append(f"<details><summary>Rozpad: {escape(str(key)[6:])}</summary>")
        for label,row in tab.items():
            if row.get('suppressed'):
                chunks.append(f"<div class='segment-row'><b>{escape(str(label))}</b><span class='suppressed'>málo pozorování</span></div>")
                continue
            # 17.1.1: pri donor_layer='core' se drive vypsalo "core donors=N · core donors=N".
            _layer=str(row.get('donor_layer','core'))
            _layer_part=("" if _layer=="core" else f" · {escape(_layer)} donors={escape(str(row.get('n_unique_layer_donors','—')))}")
            chunks.append(f"<div class='segment-card'><h4>{escape(str(label))}</h4><div class='micro'>effective n = {escape(str(row.get('effective_n','—')))} · core donors={escape(str(row.get('n_unique_core_donors','—')))}{_layer_part} · max donor share={escape(str(row.get('max_donor_share','—')))} · support={escape(str(row.get('support_status','—')))}</div>")
            if 'prumer' in row:
                chunks.append(_band('průměr',row.get('prumer'),row.get('interval_95'),rating=rating,unit='',synthetic=True))
            else:
                ints=row.get('intervaly_95',{})
                for k,v in row.items():
                    if k in {'n','effective_n','n_unique_core_donors','donor_layer','n_unique_layer_donors','max_donor_share','support_status','intervaly_95','interval_95','suppressed','reason'} or str(k).startswith('_'): continue
                    if isinstance(v,(int,float)):
                        chunks.append(_band(str(k),v,ints.get(k),rating=rating,unit='%',synthetic=True))
            chunks.append('</div>')
        chunks.append('</details>')
    return ''.join(chunks)


def _manifest(v: dict) -> str:
    rows={
      'release':v.get('release'),'run_id':v.get('run_id'),'panel_version':v.get('panel_version'),
      'panel_sha256':v.get('panel_sha256'),'model':v.get('model'),'mode':v.get('mode'),
      'temperature':v.get('model_request_temperature'),'seed':v.get('seed'),'response_mode':v.get('response_mode'),
      'persona_mode':v.get('persona_mode'),'sampling':v.get('sampling'),'generated_at':v.get('generated_at'),
      'context_sha256':v.get('context_sha256') or '—',
    }
    return '<dl class="manifest">'+''.join(f'<dt>{escape(str(k))}</dt><dd>{escape(str(val))}</dd>' for k,val in rows.items())+'</dl>'


def export_html(v: dict[str, Any], path: str|Path) -> Path:
    css=r'''
:root{--paper:#FAF9F6;--ink:#14181C;--muted:#5C636B;--line:#DCDFE3;--accent:#23356B;--green:#3E9C6A;--amber:#C98A1E;--red:#C0503C}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Georgia,'Times New Roman',serif;line-height:1.45}main{max-width:1040px;margin:0 auto;padding:34px 34px 70px}.mono,.meta,.micro,.manifest,.measure strong{font-family:'IBM Plex Mono','Cascadia Mono','Consolas',monospace;font-variant-numeric:tabular-nums}header{border-bottom:1px solid var(--ink);padding-bottom:18px;margin-bottom:28px}.origin{font-family:Arial,sans-serif;font-size:12px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;margin-bottom:12px}.origin:before{content:'SYNTHETIC';border:1px solid var(--ink);padding:3px 6px;margin-right:9px}h1{font-size:34px;line-height:1.1;margin:0 0 8px}h2{font-size:23px;margin:36px 0 12px;border-top:1px solid var(--line);padding-top:20px}h3{font:700 13px Arial,sans-serif;text-transform:uppercase;letter-spacing:.05em;margin:22px 0 8px}h4{margin:10px 0 2px}.lead{color:var(--muted);max-width:780px}.meta{display:grid;grid-template-columns:160px 1fr;gap:4px 18px;font-size:12px;margin-top:16px}.meta b{font-weight:500;color:var(--muted)}.q{margin:22px 0 42px}.measure{border-top:1px solid var(--line);padding:9px 0 11px}.measure-head{display:grid;grid-template-columns:minmax(180px,1fr) auto 20px;gap:12px;align-items:baseline}.measure strong{font-size:14px}.measure small{font-weight:400;color:var(--muted)}.track{height:12px;position:relative;margin-top:6px;background:linear-gradient(to right,transparent 49.8%,var(--line) 50%,transparent 50.2%)}.ci{position:absolute;top:3px;height:6px;border:1px solid var(--ink)}.ci.hatched{background:repeating-linear-gradient(135deg,rgba(20,24,28,.12) 0 2px,transparent 2px 5px)}.ci.solid{background:var(--ink)}.point{position:absolute;top:0;width:2px;height:12px;background:var(--ink)}.evidence{width:9px;height:9px;border-radius:50%;display:inline-block}.evidence.green{background:var(--green)}.evidence.amber{background:var(--amber)}.evidence.red{background:var(--red)}.policy{border-left:3px solid var(--amber);padding:9px 12px;margin:12px 0;font-family:Arial,sans-serif;font-size:13px}.policy.red{border-color:var(--red)}.falsify{background:#fff;border:1px solid var(--line);padding:12px 14px;margin-top:16px;font-size:13px}.falsify b{font-family:Arial,sans-serif}.suppressed{font-family:Arial,sans-serif;color:var(--muted);border:1px dashed var(--line);padding:10px;margin:7px 0}.micro{font-size:11px;color:var(--muted)}details{border-top:1px solid var(--line);padding:10px 0}summary{cursor:pointer;font-family:Arial,sans-serif;font-weight:700}.segment-card{margin:10px 0 18px;padding-left:14px;border-left:1px solid var(--line)}.segment-row{display:flex;gap:20px;padding:7px 0}.verbatim{padding:8px 0;border-bottom:1px solid var(--line)}.qc{border:1px solid var(--line);padding:12px 14px;margin:15px 0}.qc.critical{text-decoration:line-through;border-color:var(--red)}.legend{display:flex;gap:18px;font:12px Arial,sans-serif;color:var(--muted);margin:12px 0}.sample{display:inline-block;width:34px;height:8px;border:1px solid var(--ink);margin-right:6px}.sample.hatched{background:repeating-linear-gradient(135deg,rgba(20,24,28,.12) 0 2px,transparent 2px 5px)}.sample.solid{background:var(--ink)}.manifest{display:grid;grid-template-columns:190px 1fr;gap:5px 16px;font-size:11px;word-break:break-all}.manifest dt{color:var(--muted)}.manifest dd{margin:0}.dry-banner{position:sticky;top:0;z-index:50;background:#8b0000;color:#fff;font:800 15px Arial,sans-serif;letter-spacing:.08em;text-align:center;padding:10px}.dry-watermark{position:fixed;inset:0;z-index:40;pointer-events:none;overflow:hidden}.dry-watermark:before{content:'INVALID – DRY RUN   INVALID – DRY RUN   INVALID – DRY RUN';position:absolute;left:-18%;top:43%;width:140%;transform:rotate(-25deg);font:900 46px Arial,sans-serif;letter-spacing:.12em;color:rgba(139,0,0,.12);white-space:nowrap}footer{border-top:1px solid var(--ink);margin-top:44px;padding-top:14px;color:var(--muted);font-size:12px}@media print{main{max-width:none;padding:18mm}.q{break-inside:avoid}details{display:block}summary{list-style:none}}
'''
    name=escape(str(v.get('nazev','NPC Panel')))
    dry=str(v.get('mode','')).lower()=='dry'
    dry_mark=("<div class='dry-banner'>INVALID – DRY RUN · TECHNICKÝ TEST · NEPOUŽÍVAT JAKO VÝZKUM</div><div class='dry-watermark'></div>" if dry else "")
    parts=["<!doctype html><html lang='cs'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",f"<title>{'INVALID – DRY RUN · ' if dry else ''}{name}</title><style>{css}</style></head><body>"+dry_mark+"<main>",
           "<header><div class='origin'>Syntetický panel · nejedná se o terénní sběr</div>",f"<h1>{name}</h1>",
           "<p class='lead'>Rozhodovací protokol. Simulované a odvozené veličiny jsou šrafované; každé zobrazené výzkumné číslo má interval a evidence rating. v17.1 používá koherentní same-person core a explicitně matchované donor bloky; cross-block a prediktivní claimy zůstávají validačně oddělené.</p>",
           "<div class='legend'><span><i class='sample solid'></i>měřené na lidech</span><span><i class='sample hatched'></i>simulované / odvozené</span><span>● green / amber / red = evidence</span></div>",
           f"<div class='meta'><b>Run</b><span>{escape(str(v.get('run_id','—')))}</span><b>Release</b><span>{escape(str(v.get('release','—')))}</span><b>Vzorek</b><span>raw n={escape(str(v.get('n_dotazano','—')))}</span><b>Model</b><span>{escape(str(v.get('model','—')))}</span></div></header>"]
    qc=v.get('qc') or {}
    if qc:
        critical=str(qc.get('uroven','')).upper()=='KRITICKE'
        parts.append(f"<div class='qc {'critical' if critical else ''}'><b>QC {escape(str(qc.get('uroven','')))}</b> — {escape(str(qc.get('verdikt','')))}"+(" · klientský export je blokovaný." if critical else "")+"</div>")
    for q in v.get('otazky',[]):
        a=v.get('vysledky',{}).get(q['id'],{}); ev=evidence_rating(q.get('text',''),a.get('typ',q.get('typ','')))
        parts.append(f"<section class='q'><h2>{escape(str(q['id']))} · {escape(str(q.get('text','')))}</h2>")
        parts.append(f"<div class='micro'>raw n={escape(str(a.get('n_platnych','—')))} · Kish n={escape(str(a.get('effective_n_kish','—')))} · donor-aware n={escape(str(a.get('effective_n','—')))} · core donors={escape(str(a.get('n_unique_core_donors','—')))} · layer={escape(str(a.get('donor_layer','core')))} · layer donors={escape(str(a.get('n_unique_layer_donors','—')))} · max donor share={escape(str(a.get('max_donor_share','—')))} · support={escape(str(a.get('support_status','—')))}</div>")
        if str(a.get('support_status','')).upper() == 'INDICATIVE':
            parts.append("<div class='policy'>INDIKATIVNÍ: relevantní vrstva má jen 25–49 unikátních reálných donorů. Čísla zobrazujeme s donor-bootstrap intervalem, ale nejsou vhodná pro přesný klientský claim.</div>")
        elif str(a.get('support_status','')).upper() == 'SUPPRESS':
            parts.append("<div class='policy red'>NEREPORTOVAT: relevantní vrstva má méně než 25 unikátních reálných donorů.</div>")
        parts.append(f"<div class='policy {'red' if ev['rating']=='RED' else ''}'>{_rating_dot(ev['rating'])} <b>{escape(ev['rating'])} · {escape(ev['mode'])}</b> — {escape(ev['reason'])}</div>")
        typ=a.get('typ')
        if ev['mode']=='REFUSE':
            parts.append("<div class='suppressed'>Tato absolutní úloha je pro klientský claim odmítnuta. Použijte relativní variantu nebo lidské měření.</div>")
        elif typ in {'vyber','multi'}:
            parts.append(_distribution('Vylosované syntetické odpovědi',a.get('celkem_pct',{}),a.get('intervaly_95',{}),ev['rating'],a.get('effective_n',0),a.get('n_guard_threshold',50)))
            # Preserve the older report label while enforcing interval-first rendering.
            parts.append(_distribution('Průměr LLM pravděpodobností',a.get('expected_pct',{}),a.get('expected_intervaly_95',{}),ev['rating'],a.get('effective_n',0),a.get('n_guard_threshold',50)))
        elif typ=='skala':
            if float(a.get('effective_n') or 0) < float(a.get('n_guard_threshold',50)):
                parts.append("<div class='suppressed'>málo pozorování — zvětšete vzorek</div>")
            else:
                parts.append(_band('průměr',a.get('prumer'),a.get('prumer_interval_95'),rating=ev['rating'],unit='',synthetic=True))
                parts.append(_band('top-2-box',a.get('top2box_pct'),a.get('top2box_interval_95'),rating=ev['rating'],unit='%',synthetic=True))
        elif typ=='otevrena':
            parts.append("<h3>Ilustrační syntetické verbatimy</h3>")
            for x in a.get('verbatimy',[])[:30]: parts.append(f"<div class='verbatim'>{escape(str(x))}</div>")
        parts.append(_segment_tables(a,ev['rating']))
        for w in a.get('varovani',[]): parts.append(f"<div class='policy'>{escape(str(w))}</div>")
        parts.append(f"<div class='falsify'><b>Co by muselo být pravda, aby závěr neplatil:</b> {escape(falsification_condition(q.get('text',''),typ,ev))}</div></section>")
    parts.append("<h2>Manifest běhu</h2>"+_manifest(v))
    parts.append("<footer>Syntetický původ je vlastnost výstupu, nikoli poznámka pod čarou. Původní data, váhy a auditní export zůstávají oddělené od tohoto klientského protokolu.</footer></main></body></html>")
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(''.join(parts),encoding='utf-8'); return p
