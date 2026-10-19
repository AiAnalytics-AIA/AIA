// The prototype's documentation inside the app (demo view, not product UI).
import { update } from '../app/store';
import { CAPABILITIES, CONFLICTS, DECISIONS, DONORS, GAPS, HIERARCHY, INSPECTED, INTERACTIONS, BOUNDARY } from '../model/inventory';
import { SCENARIOS } from '../app/scenarios';
import { Mark } from './Icons';

const STATE_WORD = { implemented: 'implementováno', simulated: 'simulováno', proposed: 'navrženo', unavailable: 'v AIA zatím není' } as const;

export function DocsView() {
  return (
    <div className="entrywrap">
      <header className="entryhead"><Mark size={22} /><b>AIA</b><span className="muted">Vedoucí výzkumu · dokumentace prototypu V2</span><span className="grow" /><button className="btn btn--sm" onClick={() => update((d) => { d.view = 'study'; })}>Zpět do studie</button></header>
      <main className="entry docs">
        <h1>Prototyp V2 · dokumentace</h1>
        <p className="muted">Prozkoumáno: {INSPECTED.aia.repo} {INSPECTED.aia.branch} @ <span className="mono">{INSPECTED.aia.commit.slice(0, 10)}</span> · {INSPECTED.owu.repo} {INSPECTED.owu.branch} @ <span className="mono">{INSPECTED.owu.commit.slice(0, 10)}</span>. {INSPECTED.exports}</p>
        <h2>Scénáře</h2>
        <table className="tbl"><tbody>{SCENARIOS.map((s) => <tr key={s.id}><td className="mono">{s.id}</td><td>{s.label}</td><td className="muted">{s.detail}</td></tr>)}</tbody></table>
        <h2>Informační hierarchie</h2>
        <table className="tbl"><tbody>{HIERARCHY.map((h) => <tr key={h.level}><td><b>{h.level}</b></td><td>{h.what}</td><td className="muted">{h.why}</td></tr>)}</tbody></table>
        <h2>Schopnosti a kam se přesunuly</h2>
        <table className="tbl"><thead><tr><th>Schopnost</th><th>V produktu</th><th>Ve V2</th><th>Stav</th></tr></thead><tbody>{CAPABILITIES.map((c) => <tr key={c.capability}><td>{c.capability}</td><td className="muted">{c.product}</td><td>{c.v2}</td><td><span className={'chip' + (c.state === 'proposed' ? ' chip--line' : c.state === 'unavailable' ? ' chip--ink' : '')}>{STATE_WORD[c.state]}</span></td></tr>)}</tbody></table>
        <h2>Interakce</h2>
        <table className="tbl"><tbody>{INTERACTIONS.map((c) => <tr key={c.action}><td>{c.action}</td><td><b>{c.path}</b></td><td className="muted">{c.detail}</td></tr>)}</tbody></table>
        <h2>Open WebUI · co a jak převzato</h2>
        <table className="tbl"><tbody>{DONORS.map((c) => <tr key={c.pattern}><td>{c.pattern}</td><td className="mono cap">{c.source}</td><td>{c.adaptation}</td><td className="muted">{c.cls}</td></tr>)}</tbody></table>
        <h2>Hranice Vedoucího výzkumu</h2>
        <table className="tbl"><thead><tr><th>Oblast</th><th>Čte</th><th>Navrhuje</th><th>Ovládá</th><th>Spouští</th><th>Nesmí</th></tr></thead><tbody>{BOUNDARY.map((b) => <tr key={b.capability}><td><b>{b.capability}</b></td><td>{b.read}</td><td>{b.propose}</td><td>{b.operate}</td><td>{b.invoke}</td><td className="muted">{b.prohibited}</td></tr>)}</tbody></table>
        <h2>Rozhodnutí</h2>
        <table className="tbl"><tbody>{DECISIONS.map((d) => <tr key={d.id}><td className="mono">{d.id}</td><td>{d.decision}</td><td className="muted">{d.why}</td></tr>)}</tbody></table>
        <h2>Rozpory v podkladech</h2>
        <table className="tbl"><tbody>{CONFLICTS.map((d) => <tr key={d.topic}><td><b>{d.topic}</b></td><td>{d.finding}</td><td className="muted">{d.used}</td></tr>)}</tbody></table>
        <h2>Mezery do produkce</h2>
        <ul>{GAPS.map((g) => <li key={g}>{g}</li>)}</ul>
      </main>
    </div>
  );
}
