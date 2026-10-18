// Interpretation and delivery: Analysis (coverage, findings in three registers,
// blocked claims, modules, open answers) and Report (the document, tracked
// changes, references, review).
import { useApp } from '../app/store';
import { FINDINGS, CLAIMS, MODULES, RQS, RESULTS, SET1, claim } from '../model/fixture';
import { workingDoc } from '../model/doc';
import { Sec, Item, useProposals, SourceChips, Unavailable, StageLink, ChangeBlock, fmt } from '../components/ui';
import { Glyph } from '../components/Glyph';
import { Icon } from '../components/Icons';
import * as C from '../app/commands';
import { runScript, retryAnalysis, send } from '../app/scenarios';
import { pendingProposals } from '../model/status';
import { T } from '../model/terms';

export function Milestones() {
  const s = useApp((x) => x);
  const exec = s.run.status === 'completed';
  const analysis = exec && s.analysisState !== 'none' && s.analysisState !== 'running';
  const items: [string, boolean, string][] = [
    ['Sběr dokončen', exec, exec ? s.run.id : 'čeká'],
    ['Povinná analýza', analysis && !s.failures.analysisValidation, analysis ? (s.failures.analysisValidation ? 'Hypotézy k opravě' : 'RQ3 jen částečně') : 'čeká'],
    ['Zpráva zrevidována', s.reportState.reviewed, s.reportState.reviewed ? 'interně schváleno' : 'koncept ' + s.reportState.draft],
  ];
  return (
    <div className="milestones" aria-label="Stav dokončení">
      {items.map(([l, ok, note]) => <div key={l} className="ms"><Glyph tone={ok ? 'done' : 'inert'} size={12} /><b>{l}</b><span className="muted">{note}</span></div>)}
    </div>
  );
}

const REG: Record<string, { label: string; cls: string; note: string }> = {
  finding: { label: 'Zjištění', cls: 'computed', note: 'z připuštěných nároků' },
  interpretation: { label: 'Výklad', cls: 'ai', note: 'čtení zjištění; není měření' },
  context: { label: 'Externí kontext', cls: 'external', note: 'mimo studii; není důkaz od respondentů' },
};

export function AnalysisArt() {
  const s = useApp((x) => x);
  if (s.run.status !== 'completed') return <div className="page"><div className="empty"><Glyph tone="blocked" size={16} /><div><b>Analýza zatím není.</b><div className="muted">Čte připuštěné výsledky dokončeného běhu.</div></div></div></div>;
  const coding = pendingProposals(s, 'analysis')[0];
  const ctxOk = (s.evidenceAttached['pair.fio~air'] ?? []).length > 0;
  const findings = FINDINGS.filter((f) => f.register !== 'context' || ctxOk);
  const mods = MODULES.map((m) => (m.id === 'hypotheses' && s.failures.analysisValidation ? { ...m, state: 'failed' as const, note: 'Dvakrát neprošlo kontrolou schématu (pole hypotheses[2].evidence_ref). Uloženo BLOCKED.' } : m));
  return (
    <div className="page">
      <Milestones />
      <Sec id="analysis.coverage" n="1" title="Pokrytí výzkumných otázek">
        <table className="tbl">
          <thead><tr><th>Otázka</th><th>Odpověď</th><th>Zjištění</th><th>Co chybí</th></tr></thead>
          <tbody>{RQS.map((r) => {
            const fs = findings.filter((f) => f.rq === r.id);
            const st = r.id === 'RQ2' ? (s.codingAccepted ? 'ano' : 'výběr ano, důvody bez kódování') : r.id === 'RQ3' ? 'jen částečně' : 'ano';
            return <tr key={r.id}><td><b>{r.id}</b> <span className="muted">{r.text}</span></td><td>{st}</td><td>{fs.map((f) => <button key={f.id} className="srcchip" onClick={() => C.visual.inspect({ type: 'finding', id: f.id })}>{f.id}</button>)}</td><td className="muted">{r.id === 'RQ2' && s.codingAccepted ? '—' : r.gaps.join(' · ') || '—'}</td></tr>;
          })}</tbody>
        </table>
      </Sec>
      <Sec id="analysis.findings" n="2" title="Zjištění, výklad a kontext" aside="koncept · nerevidováno">
        {findings.map((f) => (
          <div key={f.id} className={'finding' + (s.focusPath === f.id ? ' just' : '')} data-aia={'analysis.finding.' + f.id}>
            <div className="finding__h"><span className={'kindtag kindtag--' + REG[f.register].cls}>{REG[f.register].label}</span><span className="tag">{f.id}</span><span className="cap">{f.rq} · {REG[f.register].note}</span>
              <button className="iconbtn" style={{ marginLeft: 'auto' }} aria-label={'Otevřít ' + f.id + ' v inspektoru'} onClick={() => C.visual.inspect({ type: 'finding', id: f.id })}><Icon name="inspector" size={14} /></button></div>
            <p>{f.text}</p>
            <div className="finding__f">{f.claims.map((c) => <button key={c} className="srcchip" onClick={() => C.visual.inspect({ type: 'claim', id: c })}>{c}</button>)}<SourceChips ids={f.sources} />{f.uncertainty && <span className="cap">Nejistota: {f.uncertainty}</span>}</div>
          </div>
        ))}
        {!ctxOk && <p className="cap">Externí kontext k mapě zatím nebyl dohledán.</p>}
        <div className="actionrow"><button className="btn btn--sm" disabled={s.busy} onClick={() => send('Která zjištění patří do shrnutí?')}>Která zjištění do shrnutí?</button></div>
      </Sec>
      <Sec id="analysis.blocked" n="3" title="Blokované nároky" aside="brána evidence">
        {CLAIMS.filter((c) => c.admission === 'blocked').map((c) => (
          <div key={c.id} className={'blocked' + (s.focusPath === c.id ? ' just' : '')} data-aia={'analysis.claim.' + c.id}><Glyph tone="blocked" size={12} /><div className="grow"><b>{c.text}</b><div className="muted">{c.reason}</div></div><button className="srcchip" onClick={() => C.visual.inspect({ type: 'claim', id: c.id })}>{c.id}</button></div>
        ))}
      </Sec>
      <Sec id="analysis.q9" n="4" title="Otevřené odpovědi Q9: proč zvažují změnu" aside={RESULTS.q9.answered + ' odpovědí'}>
        {s.codingAccepted ? (
          <>
            <table className="tbl"><thead><tr><th>Téma</th><th className="n">Odpovědi</th><th>Příklad</th></tr></thead>
              <tbody>{RESULTS.q9.themes.map((t, i) => <tr key={t.id}><td>{t.label}</td><td className="n">{t.proposed} <span className="muted">z 96</span></td><td className="serif">„{RESULTS.q9.examples[i]?.text ?? '—'}“</td></tr>)}</tbody></table>
            <p className="cap">Počty z uložené klasifikace každé odpovědi (prototyp). Kódování je výklad; každé téma má dohledatelné příklady.</p>
          </>
        ) : coding ? (
          <>{coding.changes.map((c) => <ChangeBlock key={c.id} c={c} p={coding} stale={false} />)}</>
        ) : (
          <>
            <p style={{ margin: '0 0 6px' }}>RQ2 se ptá „proč“; výběr banky bez rozboru důvodů otázku nezodpoví.</p>
            <Unavailable kind="proposed">Kvalitativní kódování otevřených odpovědí. Počty by vznikly z uložené klasifikace, ne z textu modelu.</Unavailable>
            <div className="actionrow"><button className="btn btn--sm" disabled={s.busy} onClick={() => send('Rozeber otevřené odpovědi Q9')}>Navrhnout témata</button></div>
          </>
        )}
      </Sec>
      <Sec id="analysis.modules" n="5" title="Moduly analýzy" aside="aia.analysis.module · interní">
        <ul className="ready">
          {mods.map((m) => (
            <li key={m.id}><Glyph tone={m.state === 'done' ? 'done' : m.state === 'failed' ? 'fault' : 'blocked'} size={12} /><span className="grow">{m.label}{m.note && <span className="muted"> · {m.note}</span>}</span>
              {m.state === 'failed' && <button className="btn btn--sm" disabled={s.busy} onClick={() => void runScript(retryAnalysis)}>Nové kolo nad stejnými daty</button>}</li>
          ))}
        </ul>
      </Sec>
    </div>
  );
}

export function ReportArt() {
  const s = useApp((x) => x);
  const doc = useApp((x) => workingDoc(x, 'report'));
  const { props, stale } = useProposals('report');
  if (s.run.status !== 'completed') return <div className="page"><div className="empty"><Glyph tone="blocked" size={16} /><div><b>Zpráva zatím není.</b><div className="muted">Skládá se z analýzy dokončeného běhu.</div></div></div></div>;
  return (
    <div className="page page--doc">
      <Milestones />
      <div className="docbar">
        <span className="synth"><Icon name="flag" size={12} />{T.synthetic.short}</span>
        <span className="cap">Interní zpráva · koncept {s.reportState.draft} · {s.reportState.reviewed ? 'interně schváleno' : 'neschváleno'}</span>
        <span className="grow" />
        <button className="btn btn--sm btn--quiet" onClick={() => C.visual.inspect({ type: 'synthetic' })}>Omezení</button>
        <button className="btn btn--sm" onClick={() => C.approveReport('ui')} disabled={s.reportState.reviewed || props.length > 0} title={props.length ? 'Nejprve rozhodněte o čekajících změnách' : undefined}>{s.reportState.reviewed ? 'Schváleno' : 'Schválit interně'}</button>
        <button className="btn btn--sm btn--quiet" onClick={() => send('Připrav klientskou zprávu')} disabled={s.busy}>Klientská zpráva…</button>
      </div>
      <article className="doc" aria-label="Koncept zprávy">
        <header className="doc__head">
          <div className="doc__kicker">Fio banka · interní</div>
          <h1>Mladí zákazníci 2026</h1>
          <p className="doc__disc"><b>Fiktivní data.</b> Respondenti, čísla, citace a zdroje jsou smyšlené pro prototyp; nejde o fakta o Fio bance. Výsledky nepopisují populaci ČR.</p>
        </header>
        {doc.sections.map((sec) => (
          <section key={sec.id} className="doc__sec" data-aia={'report.' + sec.id}>
            <h2 className={s.focusPath === sec.id ? 'just' : ''}>{sec.title}</h2>
            {sec.items.map((it) => (
              <Item key={it.id} stage="report" sec={sec.id} id={it.id} field="text" value={String(it.text)} label={'Odstavec ' + it.id} props={props} stale={stale} movable>
                <p className="doc__p">{String(it.text)} {((it.refs as string[] | undefined) ?? []).map((r) => <button key={r} className="srcchip" title={claim(r).text} onClick={(e) => { e.stopPropagation(); C.visual.inspect({ type: 'claim', id: r }); }}>{r}</button>)}</p>
              </Item>
            ))}
            {sec.id === 'r3' && (
              <figure className="doc__fig" data-aia="report.fig.set1">
                <figcaption>Obr. 3.1 Hodnocení bank, průměr na škále 1–10 s 95% intervalem (n podle banky)</figcaption>
                <div className="minichart">{SET1.filter((m) => m.mean != null).map((m) => <div key={m.obj} className="mc"><span className="mc__l">{m.obj}</span><span className="mc__bar"><i style={{ left: ((m.lo! - 1) / 9) * 100 + '%', width: ((m.hi! - m.lo!) / 9) * 100 + '%' }} /><b style={{ left: ((m.mean! - 1) / 9) * 100 + '%' }} /></span><span className="mc__v">{fmt(m.mean)}</span></div>)}</div>
                <div className="cap">Raiffeisenbank potlačena (Kish n 27). Hodnoty nejsou procenta.</div>
              </figure>
            )}
            {sec.id === 'r4' && <figure className="doc__fig"><figcaption>Obr. 4.1 Sociomapa sady 1 (aia-sociomap-3, Stress-1 0,083) · <StageLink stage="sociomap">otevřít mapu</StageLink></figcaption></figure>}
          </section>
        ))}
        <footer className="doc__foot">Koncept {s.reportState.draft} · {s.reportState.reviewed ? 'APPROVED_INTERNAL' : 'DRAFT_UNAPPROVED'} · Fiktivní data · {s.run.id} · revize {s.run.revision}</footer>
      </article>
      <Sec n="—" title="Záznam pokrytí (mimo text zprávy)">
        <ul className="plain">
          <li>Segmenty (srovnání 18–24 a 25–35): neprovedeno, v AIA zatím není. Kapitola ve zprávě není; záznam zůstává zde.</li>
          <li>Kódování Q9: {s.codingAccepted ? 'přijato; lze doplnit do kap. 3' : 'navržená schopnost, nepřijato'}.</li>
        </ul>
        <div className="actionrow">
          <button className="btn btn--sm btn--quiet" disabled={s.busy} onClick={() => send('Udělej shrnutí méně technické')}>Méně technicky</button>
          <button className="btn btn--sm btn--quiet" disabled={s.busy} onClick={() => send('Dej zjištění o mladších zákaznících na začátek')}>Mladší zákazníci jako první</button>
          <button className="btn btn--sm btn--quiet" disabled={s.busy} onClick={() => send('Dej Sociomapě větší důraz')}>Víc Sociomapy</button>
          <button className="btn btn--sm btn--quiet" disabled={s.busy} onClick={() => send('Nepřehání věta 1.3 evidenci?')}>Přehání věta 1.3?</button>
          <button className="btn btn--sm btn--quiet" disabled={s.busy} onClick={() => send('Odkud je číslo 6,8?')}>Odkud je 6,8?</button>
        </div>
        <Unavailable>Klientská zpráva: pro fiktivní běh AIA odmítá (client_report_refused).</Unavailable>
        <p className="cap">Export DOCX/PDF nese stejné upozornění o fiktivních datech v záhlaví i zápatí (simulováno).</p>
      </Sec>
    </div>
  );
}
