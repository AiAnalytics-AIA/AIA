// The frame around the work: one compact study header, the phase-grouped stage
// navigator with its lifecycle overview, the rail shown in artifact focus, the
// Client → Study entry view and the demo controls (deliberately unlike product UI).
import { useEffect, useRef, useState } from 'react';
import { useApp, update, setFast } from '../app/store';
import * as C from '../app/commands';
import { PHASES, STAGES, STAGE_ORDER, T } from '../model/terms';
import { overallState, pendingCount, pendingProposals, stageStatus, statusWord, TONE } from '../model/status';
import { ENTRY_STUDIES, STUDY } from '../model/fixture';
import { Icon, Mark } from './Icons';
import { Glyph } from './Glyph';
import { fmt } from './ui';
import { loadScenario, SCENARIOS } from '../app/scenarios';

export function StudyHeader() {
  const s = useApp((x) => x);
  const [menu, setMenu] = useState(false);
  const [pend, setPend] = useState(false);
  const n = pendingCount(s);
  const b = s.budget;
  const spentPct = Math.min(100, (b.studySpent / b.studyLimit) * 100);
  const resPct = Math.min(100 - spentPct, (b.studyReserved / b.studyLimit) * 100);
  const items = [
    ...pendingProposals(s).map((p) => ({ key: p.id, stage: p.stage, text: p.title, kind: C.isStale(s, p) ? 'Zastaralý návrh' : 'Návrh ke kontrole' })),
    ...s.decisions.filter((d) => d.status === 'open').map((d) => ({ key: d.id, stage: d.stage ?? s.stage, text: d.title, kind: 'Rozhodnutí' })),
  ];
  return (
    <header className="shead">
      <span className="shead__band" aria-hidden="true" />
      <button className="shead__home" onClick={() => update((d) => { d.view = 'entry'; })} aria-label={'Klienti › ' + STUDY.client}>
        <span className="shead__mono" aria-hidden="true">{STUDY.clientMono}</span>
        <span className="shead__title"><span className="shead__client">{T.header.clients} › {STUDY.client}</span><span className="shead__study">{STUDY.name}</span></span>
      </button>
      <span className="shead__state" title={overallState(s)}><Glyph tone={s.run.status === 'running' ? 'running' : s.reopened.length ? 'reopened' : 'done'} size={11} />{overallState(s)}</span>
      <span className="shead__spacer" />
      <button className="synth synth--btn" onClick={() => C.visual.inspect({ type: 'synthetic' })} title={T.synthetic.long}><Icon name="flag" size={12} />{T.synthetic.short}</button>
      {n > 0 && (
        <div style={{ position: 'relative' }}>
          <button className="shead__pending" aria-expanded={pend} onClick={() => setPend((v) => !v)}><Glyph tone="you" size={11} />{T.header.pending(n)}</button>
          {pend && <><div className="scrim" onClick={() => setPend(false)} /><div className="pop" style={{ right: 0, top: 34, width: 360 }} role="dialog" aria-label="Čeká na vás">
            {items.map((it) => <button key={it.key} className="listbtn" onClick={() => { C.visual.open(it.stage); setPend(false); }}><span className="grow"><span className="cap">{it.kind} · {STAGES[it.stage].label}</span><br />{it.text}</span><Icon name="next" size={13} /></button>)}
          </div></>}
        </div>
      )}
      <button className="budgetmini" onClick={() => C.visual.inspect({ type: 'budget' })} title="Rozpočet studie: utraceno, rezervováno, limit">
        <Icon name="budget" size={13} /><span className="budgetmini__bar" aria-hidden="true"><i style={{ width: spentPct + '%' }} /><b style={{ left: spentPct + '%', width: resPct + '%' }} /></span>
        <span className="num">{fmt(b.studySpent, 2)} / {b.studyLimit} USD</span>
      </button>
      <button className="iconbtn" onClick={() => C.visual.inspect({ type: 'envelope' })} title="Oprávnění hloubkového výzkumu" aria-label="Oprávnění hloubkového výzkumu"><Icon name="research" size={16} /></button>
      <div style={{ position: 'relative' }}>
        <button className="iconbtn" aria-label={T.header.menu} title={T.header.menu} aria-expanded={menu} onClick={() => setMenu((v) => !v)}><Icon name="menu" size={16} /></button>
        {menu && <><div className="scrim" onClick={() => setMenu(false)} /><div className="pop menu" style={{ right: 0, top: 34, width: 280 }} role="menu">
          <button role="menuitem" className="listbtn" onClick={() => { setMenu(false); C.visual.inspect({ type: 'context' }); }}>Podrobnosti studie a kontext Vedoucího</button>
          <button role="menuitem" className="listbtn" onClick={() => { setMenu(false); C.visual.inspect({ type: 'envelope' }); }}>Oprávnění hloubkového výzkumu</button>
          <button role="menuitem" className="listbtn" onClick={() => { setMenu(false); C.visual.inspect({ type: 'budget' }); }}>Rozpočet a náklady</button>
          <button role="menuitem" className="listbtn" onClick={() => { setMenu(false); C.visual.inspect({ type: 'synthetic' }); }}>Fiktivní data a omezení</button>
          <button role="menuitem" className="listbtn" onClick={() => { setMenu(false); update((d) => { d.view = 'docs'; }); }}>Dokumentace prototypu</button>
          <div className="cap" style={{ padding: '6px 8px' }}>Správa (členové, nastavení, metodika) zůstává v Nastavení AIA.</div>
        </div></>}
      </div>
    </header>
  );
}

export function StageNav() {
  const s = useApp((x) => x);
  const [life, setLife] = useState(false);
  const nav = useRef<HTMLDivElement>(null);
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End') return;
    const btns = Array.from(nav.current!.querySelectorAll<HTMLButtonElement>('.nav__stage'));
    const i = btns.indexOf(document.activeElement as HTMLButtonElement);
    const j = e.key === 'Home' ? 0 : e.key === 'End' ? btns.length - 1 : Math.max(0, Math.min(btns.length - 1, i + (e.key === 'ArrowRight' ? 1 : -1)));
    btns[j]?.focus(); e.preventDefault();
  };
  return (
    <nav className="nav" aria-label="Kroky studie" ref={nav} onKeyDown={onKey}>
      {PHASES.map((ph) => (
        <div className="nav__phase" key={ph.id} role="group" aria-label={ph.label}>
          <span className="nav__plabel">{ph.label}</span>
          {STAGE_ORDER.filter((st) => STAGES[st].phase === ph.id).map((st) => {
            const k = stageStatus(s, st);
            const cur = s.stage === st;
            const you = k.kind === 'proposal' || k.kind === 'decision' || k.kind === 'working';
            return (
              <button key={st} className={'nav__stage' + (cur ? ' is-current' : '') + (k.kind === 'blocked' || k.kind === 'notstarted' ? ' is-inert' : '') + (you ? ' is-you' : '')}
                aria-current={cur ? 'page' : undefined} title={STAGES[st].label + ': ' + statusWord(k) + ' · ' + k.note} onClick={() => C.visual.open(st)}>
                <Glyph tone={TONE[k.kind]} size={11} />{STAGES[st].short}<span className="sr-only">, {statusWord(k)}</span>
              </button>
            );
          })}
        </div>
      ))}
      <div className="nav__more">
        <button className="btn btn--sm btn--quiet" aria-expanded={life} onClick={() => setLife((v) => !v)}><Icon name="layers" size={14} />{T.header.lifecycle}</button>
      </div>
      {life && <><div className="scrim" onClick={() => setLife(false)} /><Lifecycle onClose={() => setLife(false)} /></>}
    </nav>
  );
}

function Lifecycle({ onClose }: { onClose: () => void }) {
  const s = useApp((x) => x);
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); }; window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k); }, [onClose]);
  return (
    <div className="pop life" role="dialog" aria-label={T.header.lifecycle}>
      <div className="life__grid">
        {PHASES.map((ph) => (
          <div key={ph.id} className="life__col">
            <div className="lbl">{ph.label}</div>
            {STAGE_ORDER.filter((st) => STAGES[st].phase === ph.id).map((st) => {
              const k = stageStatus(s, st);
              return <button key={st} className="life__st" onClick={() => { C.visual.open(st); onClose(); }}><Glyph tone={TONE[k.kind]} size={11} /><span><b>{STAGES[st].label}</b><br /><span className="cap">{statusWord(k)} · {k.note}</span></span></button>;
            })}
          </div>
        ))}
      </div>
      <div className="life__deps">
        <b>Závislosti</b> (pořadí v navigaci je jen pořadí čtení):
        <span>Dotazník, Cílová skupina, Dimenze a Vzorek → Sběr dat (zmrazí revizi)</span>
        <span>Sběr → Výsledky a Sociomapa (deterministicky)</span>
        <span>Analýza čte připuštěné výsledky; výklad mapy závisí na mapě</span>
        <span>Hloubkový výzkum stojí mimo pořadí: k návrhu před zmrazením, k výkladu po něm</span>
      </div>
      <div className="life__legend">{(['done', 'you', 'running', 'world', 'reopened', 'fault', 'blocked'] as const).map((t) => <span key={t}><Glyph tone={t} size={10} />{{ done: 'hotovo / přijato', you: 'čeká na vás', running: 'běží', world: 'čeká na poskytovatele', reopened: 'znovu otevřeno', fault: 'potřebuje opravu', blocked: 'čeká na předchozí krok' }[t]}</span>)}</div>
    </div>
  );
}

export function Rail() {
  const s = useApp((x) => x);
  const n = pendingCount(s);
  return (
    <div className="rail">
      <button className="iconbtn" style={{ width: 40, height: 40 }} aria-label={T.layout.openConversation} title={T.layout.openConversation} onClick={() => C.visual.mode('normal')}><Mark size={20} /></button>
      {s.busy && <Glyph tone="running" size={12} title="Vedoucí pracuje" />}
      {n > 0 && <span className="rail__badge" title={T.header.pending(n)}>{n}</span>}
      <button className="iconbtn" aria-label={T.layout.backToNormal} title={T.layout.backToNormal} onClick={() => C.visual.mode('normal')}><Icon name="normal" size={16} /></button>
    </div>
  );
}

export function EntryView() {
  const s = useApp((x) => x);
  const open = () => update((d) => { d.view = 'study'; });
  // The open study's row is read from its live state, the others are fixture.
  const n = pendingCount(s);
  const nx = STAGE_ORDER.find((st) => ['proposal', 'decision', 'working', 'failed'].includes(stageStatus(s, st).kind)) ?? s.stage;
  const lastAct = [...s.activities].reverse().find((a) => a.status === 'done');
  const rows = ENTRY_STUDIES.map((x) => x.open ? { ...x, stage: STAGES[nx].label, attention: n ? 'Čeká na vás: ' + n : '—', latest: lastAct ? lastAct.title + ' · ' + lastAct.summary.replace(' · Zkontrolovat', '') : x.latest, when: s.day } : x);
  return (
    <div className="entrywrap">
      <header className="entryhead"><Mark size={22} /><b>AIA</b><span className="muted">Klienti</span><span className="grow" /><span className="synth"><Icon name="flag" size={12} />{T.synthetic.short}</span></header>
      <main className="entry">
        <div className="cap">Klienti › Fio banka</div>
        <h1>Fio banka</h1>
        <p className="muted">{STUDY.clientNote}. Správa klienta (profil, znalosti, data) zůstává v pracovním prostoru klienta.</p>
        <div className="studytable" role="table" aria-label="Studie klienta">
          <div className="studyrow studyrow--head" role="row"><span role="columnheader">Studie</span><span role="columnheader">Krok</span><span role="columnheader">Pozornost</span><span role="columnheader">Poslední činnost</span><span /></div>
          {rows.map((x) => (
            <button key={x.id} className="studyrow" role="row" onClick={x.open ? open : undefined} disabled={!x.open} title={x.open ? undefined : 'V prototypu jen jedna studie'}>
              <span role="cell"><b>{x.name}</b><br /><span className="cap">{x.kind}</span></span>
              <span role="cell">{x.stage}</span>
              <span role="cell">{x.attention !== '—' ? <span className="chip chip--you">{x.attention}</span> : <span className="muted">—</span>}</span>
              <span role="cell">{x.latest}<br /><span className="cap">{x.when}</span></span>
              <span role="cell">{x.open && <Icon name="next" size={16} />}</span>
            </button>
          ))}
        </div>
      </main>
    </div>
  );
}

export function DemoPanel() {
  const [open, setOpen] = useState(false);
  const s = useApp((x) => x);
  const [fast, setF] = useState(false);
  return (
    <div className="demo" aria-label="Ovládání prototypu (není součást produktu)">
      {open && (
        <div className="demo__panel">
          <div className="demo__h">PROTOTYP · scénáře <span className="cap">(není součást produktu)</span></div>
          {(['main', 'exception'] as const).map((g) => (
            <div key={g}>
              <div className="demo__g">{g === 'main' ? 'Scénáře' : 'Výjimky'}</div>
              {SCENARIOS.filter((x) => x.group === g).map((x) => (
                <button key={x.id} className={'demo__item' + (s.scenario === x.id ? ' is-on' : '')} onClick={() => { setFast(fast); loadScenario(x.id); setOpen(false); }}>
                  <b>{x.id}</b><span>{x.label.replace(/^[A-Z]\d? · |^Výjimka · /, '')}<br /><span className="cap">{x.detail}</span></span>
                </button>
              ))}
            </div>
          ))}
          <div className="demo__g">Pohledy</div>
          <button className="demo__item" onClick={() => { update((d) => { d.view = 'entry'; }); setOpen(false); }}><b>⌂</b><span>Klient → studie</span></button>
          <button className="demo__item" onClick={() => { update((d) => { d.view = 'docs'; }); setOpen(false); }}><b>¶</b><span>Dokumentace prototypu</span></button>
          <label className="demo__item"><input type="checkbox" checked={fast} onChange={(e) => { setF(e.target.checked); setFast(e.target.checked); }} /><span>Bez animací (rychlé scénáře)</span></label>
          <button className="demo__item" onClick={() => { try { localStorage.removeItem('aia-research-lead-v2'); } catch { /* blocked */ } update((d) => { d.split = 40; }); }}><b>↺</b><span>Smazat uložený poměr panelů</span></button>
        </div>
      )}
      <button className="demo__btn" aria-expanded={open} onClick={() => setOpen((v) => !v)}>PROTOTYP · scénář {s.scenario}</button>
    </div>
  );
}
