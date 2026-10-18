// Execution and evidence artifacts: Fieldwork (run, quality, cost, intervention),
// Results (aggregates with units, intervals, bases, suppression) and the
// Sociomap (frozen deterministic map; display filters never touch it).
import { useApp } from '../app/store';
import { RESULTS, SET1, FIO_RANK, MAP, PAIRS, objLabel, findPair, type Share } from '../model/fixture';
import { Sec, SourceChips, Unavailable, StageLink, fmt } from '../components/ui';
import { Glyph } from '../components/Glyph';
import { Icon } from '../components/Icons';
import * as C from '../app/commands';
import { runScript, fieldwork, retryProvider, send } from '../app/scenarios';
import type { Tone } from '../model/types';

function NotYet({ what }: { what: string }) {
  return <div className="page"><div className="empty"><Glyph tone="blocked" size={16} /><div><b>{what} zatím nejsou.</b><div className="muted">Vzniknou z dokončeného běhu. <StageLink stage="fieldwork">Sběr dat</StageLink></div></div></div></div>;
}

const STEPS: { id: string; label: string; at: number; kind: 'compute' | 'worker' }[] = [
  { id: 'compile', label: 'Zmrazení revize a specifikace', at: 0, kind: 'compute' },
  { id: 'preflight', label: 'Kontrola před během', at: 0, kind: 'compute' },
  { id: 'fieldwork', label: 'Sběr odpovědí (AI respondenti)', at: 400, kind: 'worker' },
  { id: 'aggregate', label: 'Agregace', at: 401, kind: 'compute' },
  { id: 'sociomap', label: 'Sociomapa', at: 401, kind: 'compute' },
  { id: 'analysis', label: 'Analýza (8 modulů)', at: 402, kind: 'worker' },
  { id: 'report', label: 'Koncept zprávy', at: 403, kind: 'worker' },
];

export function FieldworkArt() {
  const s = useApp((x) => x);
  const r = s.run;
  const busy = s.busy;
  if (r.status === 'none') return <NotYet what="Běhy" />;
  const doneN = r.status === 'completed' ? 403 : r.done;
  const stepTone = (at: number, id: string): Tone => {
    if (r.status === 'completed') return id === 'analysis' && s.failures.analysisValidation ? 'fault' : 'done';
    if (r.status === 'ready') return 'inert';
    if (id === 'fieldwork') return r.status === 'waiting_provider' ? (s.failures.provider ? 'fault' : 'world') : r.status === 'awaiting_budget' ? 'you' : r.status === 'cancelled' ? 'cancelled' : 'running';
    return at <= doneN && at === 0 ? 'done' : 'inert';
  };
  const left = s.budget.studyLimit - s.budget.studySpent;
  return (
    <div className="page">
      <Sec id="fieldwork.run" n="1" title={'Běh ' + (r.status === 'ready' ? '(připraven)' : r.id)} aside={'zmrazí revizi ' + (r.status === 'ready' ? s.revision : r.revision)}>
        <div className="runhead">
          <div className="big">{r.done}<span className="muted"> / {r.target}</span></div>
          <div className="grow">
            <div className="bar"><i style={{ width: (r.done / r.target) * 100 + '%' }} /></div>
            <div className="cap">{r.status === 'running' ? 'Běží · ' + r.inFlight + ' bloků rozpracováno' : r.status === 'waiting_provider' ? (s.failures.provider ? 'Zaparkováno: poskytovatel nedostupný' : 'Čeká na poskytovatele (automaticky pokračuje)') : r.status === 'awaiting_budget' ? 'Čeká na navýšení rozpočtu (AWAITING_BUDGET)' : r.status === 'completed' ? 'Dokončeno · ' + Math.round(r.elapsed / 60) + ' min · ' + r.waits + '× čekání' : r.status === 'cancelled' ? 'Zrušeno' : 'Připraveno'}</div>
          </div>
          <div className="actionrow">
            {r.status === 'ready' && (s.decisions.some((d) => d.kind === 'authorise-run' && d.status === 'open')
              ? <button className="btn btn--primary" onClick={() => { const el = document.querySelector<HTMLElement>('.dec:not(.is-decided) .opt.is-chosen'); el?.scrollIntoView({ block: 'center' }); el?.focus(); }}>Rozhodnutí o spuštění čeká v konverzaci</button>
              : <button className="btn btn--primary" disabled={busy} onClick={() => send('Spusť sběr dat')}>Spustit sběr…</button>)}
            {(r.status === 'running' || r.status === 'waiting_provider' || r.status === 'awaiting_budget') && <button className="btn btn--danger" onClick={() => C.cancelRun('ui')}>Zrušit běh</button>}
            {r.status === 'waiting_provider' && s.failures.provider && <button className="btn" onClick={() => void runScript(retryProvider)}>Zkusit krok znovu</button>}
            {r.status === 'awaiting_budget' && <button className="btn btn--primary" onClick={() => C.liftBudget('ui', 10)}>Navýšit limit o 10 USD</button>}
            {r.status === 'cancelled' && <button className="btn" disabled={busy} onClick={() => void runScript(fieldwork)}>Spustit znovu</button>}
          </div>
        </div>
        <ol className="steps">
          {STEPS.map((st) => <li key={st.id} data-aia={'fieldwork.step.' + st.id}><Glyph tone={stepTone(st.at, st.id)} size={12} /><span className="grow">{st.label}</span><span className={'kind kind--' + st.kind}>{st.kind === 'compute' ? 'deterministické' : 'AI · ModelGateway'}</span></li>)}
        </ol>
      </Sec>
      <Sec id="fieldwork.cost" n="2" title="Náklady" aside="USD · Bedrock EU přes ModelGateway">
        <dl className="kvgrid wide">
          <dt>Utraceno během</dt><dd>{fmt(r.spent, 2)} USD</dd>
          <dt>Rezervováno</dt><dd>{fmt(r.reserved, 2)} USD (rozpracované bloky)</dd>
          <dt>Strop běhu</dt><dd>{fmt(r.ceiling, 2)} USD · pod limitem potvrzení {s.budget.spendConfirm} USD</dd>
          <dt>Zbývá ve studii</dt><dd>{fmt(left, 2)} USD z {s.budget.studyLimit} USD</dd>
        </dl>
        <button className="linkbtn cap" onClick={() => C.visual.inspect({ type: 'budget' })}>Rozpis rozpočtu</button>
      </Sec>
      <Sec id="fieldwork.quality" n="3" title="Kvalita a zásah">
        <ul className="ready">
          <li><Glyph tone={r.constantResponders ? 'done-warn' : 'done'} size={12} /><span className="grow">{r.constantResponders ? r.constantResponders + ' respondentů hodnotilo všech 8 bank stejně' : 'Bez nápadných vzorců'}{r.decisionOnConstant && <span className="muted"> · {r.decisionOnConstant === 'keep' ? 'ponecháno (vaše rozhodnutí)' : 'označeno ke kontrole'}</span>}</span></li>
          <li><Glyph tone="done" size={12} /><span className="grow">Kontrola pozornosti Q19: {r.done ? '3 neprošli · vyřazeni pravidlem z návrhu' : 'čeká na data'}</span></li>
        </ul>
        <p className="cap">Stejné hodnocení všech objektů samo o sobě neznamená, že je respondent špatný. V mapě nemá relativní preference, proto se nezmapuje; do průměrů se počítá.</p>
        <Unavailable kind="proposed">Náhrada respondentů: význam náhrady pro vážení a podporu není metodicky určen.</Unavailable>
      </Sec>
      <Sec n="4" title="Kdo odpovídal">
        <dl className="kvgrid wide">
          <dt>Zdroj</dt><dd>Fiktivní AI respondenti (persona_source: fictional_roster)</dd>
          <dt>Populace</dt><dd>LIVE v17_4_0 zaznamenána, <b>nenačtena</b> (read_by_fieldwork: ne)</dd>
          <dt>Dimenze</dt><dd>3 předány · Loajalita ke značce nepředána (bez tématu)</dd>
          <dt>Původ dat</dt><dd className="mono">SYNTHETIC_AI_FICTIONAL</dd>
        </dl>
      </Sec>
    </div>
  );
}

function Interval({ lo, hi, mean, min, max }: { lo: number; hi: number; mean: number; min: number; max: number }) {
  const x = (v: number) => ((v - min) / (max - min)) * 100;
  return (
    <div className="ivl" aria-hidden="true">
      <span className="ivl__band" style={{ left: x(lo) + '%', width: x(hi) - x(lo) + '%' }} />
      <span className="ivl__dot" style={{ left: x(mean) + '%' }} />
    </div>
  );
}

function ShareRow({ s }: { s: Share }) {
  return (
    <tr>
      <td>{s.label}</td>
      <td className="n"><b>{s.pct} %</b></td>
      <td className="n muted">[{s.lo}; {s.hi}]</td>
      <td style={{ width: '32%' }}><Interval lo={s.lo} hi={s.hi} mean={s.pct} min={0} max={100} /></td>
      <td className="n muted">n {s.n}</td>
    </tr>
  );
}

export function ResultsArt() {
  const run = useApp((s) => s.run);
  const reopened = useApp((s) => s.reopened.includes('results'));
  const rev = useApp((s) => s.revision);
  const coding = useApp((s) => s.codingAccepted);
  const flagged = useApp((s) => s.run.decisionOnConstant === 'review');
  if (run.status !== 'completed') return <NotYet what="Výsledky" />;
  return (
    <div className="page">
      {reopened && <div className="annot"><div className="annot__h"><Glyph tone="reopened" size={11} />Výsledky běhu z revize {run.revision}; studie je na revizi {rev}</div>Čísla platí pro revizi {run.revision}. Nový běh je potřeba, má-li změna vstoupit do výsledků.</div>}
      <Sec id="results.set1" n="1" title="Sada 1 · Jak moc by vám vyhovovala tato banka?" aside="průměr na škále 1–10 · 95% interval · Kish n">
        <div data-aia="results.set1">
          <table className="tbl">
            <thead><tr><th>Banka</th><th className="n">Průměr</th><th className="n">Interval</th><th>1 · · · · 10</th><th className="n">Kish n</th></tr></thead>
            <tbody>
              {SET1.map((m) => (
                <tr key={m.obj} className={m.obj === 'Fio banka' ? 'is-sel' : ''}>
                  <td>{m.obj}</td>
                  {m.mean == null ? <td colSpan={3} className="muted">Potlačeno · {m.suppressed}</td> : <>
                    <td className="n"><b>{fmt(m.mean)}</b> <span className="muted">z 10</span></td>
                    <td className="n muted">[{fmt(m.lo)}; {fmt(m.hi)}]</td>
                    <td style={{ width: '30%' }}><Interval lo={m.lo!} hi={m.hi!} mean={m.mean} min={1} max={10} /></td>
                  </>}
                  <td className="n muted">{m.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="readline">Fio banka je {FIO_RANK.place}. ze {FIO_RANK.of} vykázaných bank ({FIO_RANK.rated} hodnocených). Pořadí platí jen tam, kde se intervaly rozcházejí: Fio {FIO_RANK.group}; jistě je pod {FIO_RANK.below}. <SourceChips ids={['S6']} /></p>
        </div>
      </Sec>
      <Sec id="results.q8" n="2" title="Změna hlavní banky" aside="podíl · 95% interval · báze">
        <table className="tbl"><tbody>
          <ShareRow s={RESULTS.q8} />
        </tbody></table>
        <h4 className="subh">Ke které bance (Q8, jen zvažující změnu, n 96)</h4>
        <table className="tbl"><tbody>{RESULTS.q10.map((x) => <ShareRow key={x.label} s={x} />)}</tbody></table>
        <p className="cap">Báze 96: intervaly jsou široké; Revolut a Air Bank se od sebe neliší.</p>
      </Sec>
      <Sec id="results.q9" n="3" title="Proč zvažují změnu (Q9, otevřená odpověď)" aside={RESULTS.q9.answered + ' odpovědí'}>
        <ul className="quotes">{RESULTS.q9.examples.map((e) => <li key={e.id}><span className="serif">„{e.text}“</span> <span className="cap mono">{e.id}</span></li>)}</ul>
        {coding
          ? <p className="cap">Témata z uložené klasifikace: viz <StageLink stage="analysis" focus="q9">Analýza · Q9</StageLink>.</p>
          : <p className="cap">Otevřené odpovědi jsou data, ne připuštěná evidence; nejsou kódované. <StageLink stage="analysis" focus="q9">Rozbor v Analýze</StageLink></p>}
      </Sec>
      <Sec id="results.other" n="4" title="Aplikace a povědomí">
        <table className="tbl"><tbody>
          <tr><td>{RESULTS.q12.label}</td><td className="n"><b>{fmt(RESULTS.q12.mean)}</b> <span className="muted">z 10</span></td><td className="n muted">[{fmt(RESULTS.q12.lo)}; {fmt(RESULTS.q12.hi)}]</td><td style={{ width: '32%' }}><Interval lo={RESULTS.q12.lo} hi={RESULTS.q12.hi} mean={RESULTS.q12.mean} min={1} max={10} /></td><td className="n muted">n {RESULTS.q12.n}</td></tr>
          <ShareRow s={RESULTS.q15} />
          {RESULTS.q16.map((x) => <ShareRow key={x.label} s={x} />)}
        </tbody></table>
        <p className="cap">Q13 (co je při volbě nejdůležitější): uloženo, zatím bez analýzy. Srovnání 18–24 a 25–35: <Unavailable>srovnání segmentů</Unavailable></p>
      </Sec>
      <Sec n="5" title="Původ a kvalita">
        <dl className="kvgrid wide">
          <dt>Běh</dt><dd>{run.id} · revize {run.revision} · n 400</dd>
          <dt>Původ</dt><dd>Fiktivní AI respondenti · <span className="mono">SYNTHETIC_AI_FICTIONAL</span> · jen interně</dd>
          <dt>Potlačení</dt><dd>Kish n &lt; 30 se nevykazuje (Raiffeisenbank)</dd>
          <dt>Stejné hodnocení</dt><dd>6 respondentů{flagged ? ' · označeno ke kontrole' : ' · ponecháno'}</dd>
        </dl>
      </Sec>
    </div>
  );
}

// ---------------------------------------------------------------- Sociomap
const W = 640, H = 440, PAD = 40;
const px = (x: number) => PAD + x * (W - 2 * PAD);
const py = (y: number) => PAD + y * (H - 2 * PAD);

export function SociomapArt() {
  const s = useApp((x) => x);
  const run = s.run;
  if (run.status !== 'completed') return <NotYet what="Mapy" />;
  const f = s.viewFilters;
  const sel = s.selection.sociomap;
  const selPair = sel && sel.includes('~') ? sel.split('~') : null;
  const selObj = sel && !sel.includes('~') ? sel : null;
  const placed = MAP.objects.filter((o) => o.placed);
  const ranked = [...MAP.objects].sort((a, b) => (b.height ?? -1) - (a.height ?? -1));
  const context = s.evidenceAttached['pair.fio~air'] ?? [];
  const visiblePairs = PAIRS.filter((p) => {
    if (p.status === 'UNKNOWN') return false;
    const isLink = p.status === 'RELIABLE' && p.floor;
    if (isLink) return true;
    if (f.sociomapHideWeak) return false;
    return selObj ? p.a === selObj || p.b === selObj : selPair ? findPair(selPair[0], selPair[1]) === p : false;
  });
  const terrace = (h: number) => 'var(--viz-terrace-' + Math.max(1, Math.min(10, Math.round((h - 5) * 3.2))) + ')';
  return (
    <div className="page page--wide">
      <div className="maptools" role="toolbar" aria-label="Zobrazení mapy">
        <span className="lbl">Zobrazení</span>
        <div className="seg" role="group" aria-label="Pohled">
          <button className={f.sociomapView === 'top' ? 'is-on' : ''} aria-pressed={f.sociomapView === 'top'} onClick={() => C.visual.filter('sociomapView', 'top')}>Shora</button>
          <button className={f.sociomapView === 'relief' ? 'is-on' : ''} aria-pressed={f.sociomapView === 'relief'} onClick={() => C.visual.filter('sociomapView', 'relief')}>Reliéf</button>
        </div>
        <label className="check"><input type="checkbox" checked={f.sociomapLabels} onChange={(e) => C.visual.filter('sociomapLabels', e.target.checked)} /> Popisky</label>
        <label className="check"><input type="checkbox" checked={f.sociomapHideWeak} onChange={(e) => C.visual.filter('sociomapHideWeak', e.target.checked)} /> Skrýt slabé vztahy</label>
        <span className="grow" />
        <button className="btn btn--sm btn--quiet" onClick={() => C.visual.inspect({ type: 'methodology' })}><Icon name="why" size={14} />Jak číst mapu</button>
      </div>
      {f.sociomapHideWeak && <div className="filterbar" data-aia="sociomap.filter.hideWeak"><Icon name="filter" size={13} /><b>Filtr zobrazení:</b> slabé vztahy skryté. Výpočet, pozice objektů a Stress-1 beze změny. <button className="linkbtn" onClick={() => C.visual.filter('sociomapHideWeak', false)}>Zrušit filtr</button></div>}
      <div className="mapwrap">
        <div className="mapcanvas">
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Sociomapa sady 1: 7 bank na mapě, Raiffeisenbank nezmapována" className={'map map--' + f.sociomapView}>
            <rect x={0} y={0} width={W} height={H} fill="var(--viz-stage)" />
            {placed.map((o) => (
              <g key={'t' + o.id}>
                {[1, 0.7, 0.42].map((k, i) => <circle key={i} cx={px(o.x)} cy={py(o.y)} r={(26 + (o.height! - 5) * 20) * k} fill={terrace(5 + (o.height! - 5) * (0.45 + i * 0.28))} opacity={f.sociomapView === 'relief' ? 0.42 : 0.2} />)}
              </g>
            ))}
            {visiblePairs.map((p) => {
              const a = MAP.objects.find((o) => o.id === p.a)!, b = MAP.objects.find((o) => o.id === p.b)!;
              const isSel = selPair && findPair(selPair[0], selPair[1]) === p;
              const weak = p.status !== 'RELIABLE' || !p.floor;
              return <line key={p.a + p.b} x1={px(a.x)} y1={py(a.y)} x2={px(b.x)} y2={py(b.y)} stroke={(p.r ?? 0) < 0 ? 'var(--viz-link-negative)' : 'var(--viz-link-positive)'} strokeWidth={isSel ? 3.5 : weak ? 1 : 1.5 + Math.abs(p.r ?? 0) * 4} strokeDasharray={weak ? '3 4' : (p.r ?? 0) < 0 ? '7 4' : undefined} opacity={isSel ? 1 : 0.8}
                onClick={() => { C.visual.select('sociomap', p.a + '~' + p.b); C.visual.inspect({ type: 'pair', a: p.a, b: p.b }); }} style={{ cursor: 'pointer' }} data-aia={'sociomap.pair.' + p.a + '~' + p.b} />;
            })}
            {context.length > 0 && (() => { const a = MAP.objects.find((o) => o.id === 'fio')!, b = MAP.objects.find((o) => o.id === 'air')!; return <g transform={`translate(${(px(a.x) + px(b.x)) / 2 + 6},${(py(a.y) + py(b.y)) / 2 - 18})`} onClick={() => C.visual.inspect({ type: 'source', id: 'S4' })} style={{ cursor: 'pointer' }} data-aia="sociomap.context.S4"><rect x={-2} y={-11} width={86} height={16} rx={2} fill="var(--surface-raised)" stroke="var(--border-strong)" strokeDasharray="2 2" /><text x={4} y={1} fontSize={10} fill="var(--viz-stage-ink)">externí kontext S4</text></g>; })()}
            {placed.map((o) => {
              const on = selObj === o.id || (selPair && selPair.includes(o.id));
              return (
                <g key={o.id} transform={`translate(${px(o.x)},${py(o.y)})`} onClick={() => { C.visual.select('sociomap', o.id); C.visual.inspect({ type: 'object', id: o.id }); }} style={{ cursor: 'pointer' }} data-aia={'sociomap.object.' + o.id} role="button" aria-label={o.label + ', výška ' + fmt(o.height)}>
                  <circle r={on ? 8 : 6} fill={on ? 'var(--viz-map-select)' : 'var(--viz-stage-ink)'} stroke="var(--viz-stage)" strokeWidth={2} />
                  {f.sociomapLabels && <text x={10} y={4} fontSize={13} fontWeight={o.id === 'fio' ? 700 : 500} fill="var(--viz-stage-ink)">{o.label} <tspan fill="var(--viz-stage-muted)" fontWeight={400}>{fmt(o.height)}</tspan></text>}
                </g>
              );
            })}
          </svg>
          <div className="maplegend">
            <span><i className="lg lg--pos" />spolehlivý kladný vztah</span><span><i className="lg lg--neg" />spolehlivý záporný</span><span><i className="lg lg--weak" />slabý (jen po výběru)</span><span>Výška = průměrné hodnocení 1–10</span>
          </div>
        </div>
        <aside className="mapside">
          <div className="fourway" aria-label="Co je co">
            <div><span className="kindtag kindtag--computed">Deterministický výsledek</span> pozice, výšky, vztahy, Stress-1 · zmrazeno</div>
            <div><span className="kindtag">Zobrazení</span> pohled, popisky, filtry · mění jen obraz</div>
            <div><span className="kindtag kindtag--ai">Výklad</span> co blízkost může znamenat · od Vedoucího, označeno</div>
            <div><span className="kindtag kindtag--external">Externí kontext</span> zdroje mimo studii · do výpočtu nevstupují</div>
          </div>
          <h4 className="subh">Objekty podle výšky (průměr)</h4>
          <ol className="objlist">
            {ranked.map((o) => (
              <li key={o.id}><button className={'objbtn' + (selObj === o.id ? ' is-on' : '')} onClick={() => { C.visual.select('sociomap', o.id); C.visual.inspect({ type: 'object', id: o.id }); }}>
                <span className="grow">{o.label}</span><span className="num">{o.placed ? fmt(o.height) : '—'}</span></button>{!o.placed && <div className="cap">{o.note}</div>}</li>
            ))}
          </ol>
          <dl className="kvgrid">
            <dt>Shoda</dt><dd>Stress-1 {fmt(MAP.stress, 3)} · {MAP.fit}</dd>
            <dt>Lidé</dt><dd>{MAP.nPeople} · {MAP.notPlaced} nezmapováno (bez relativních preferencí)</dd>
            <dt>Metoda</dt><dd className="mono">{MAP.method}</dd>
            <dt>Stav metody</dt><dd>schváleno pro klienty · tento běh fiktivní → jen interně</dd>
          </dl>
          <p className="cap">Hodnoty v prototypu jsou ilustrativní. Prahy a štítky shody jsou ze specifikace aia-sociomap-3.</p>
          <div className="actionrow"><button className="btn btn--sm" onClick={() => send('Proč je Fio blízko Air Bank?')}>Zeptat se na Fio – Air Bank</button></div>
        </aside>
      </div>
    </div>
  );
}

export { objLabel };
