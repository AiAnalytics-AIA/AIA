// One contextual inspector over the artifact: sources, findings, claims, map
// objects and pairs, history, details, impact, activity, methodology, the AI
// contract, the Lead's context, the research envelope and the budget. It keeps a
// back stack; Escape and the close button return focus to where it was opened.
import { Fragment, useEffect, useRef } from 'react';
import { useApp } from '../app/store';
import * as C from '../app/commands';
import { Icon } from './Icons';
import { Glyph } from './Glyph';
import { STAGES, STAGE_ORDER, T } from '../model/terms';
import { CONTRACTS, ENVELOPE, FINDINGS, MAP, PAIRS, claim, findPair, objLabel, src, STUDY, SET1, type SourceKind } from '../model/fixture';
import { fmt, SourceChips } from './ui';
import { send } from '../app/scenarios';
import type { InspectorTarget, StageId } from '../model/types';
import { contentRev } from '../model/doc';

const KIND: Record<SourceKind, string> = { client: 'Znalost klienta', study: 'Dokument studie', external: 'Externí výzkum', respondent: 'Data respondentů', computed: 'Deterministický výstup' };
const ADM: Record<string, string> = { admitted: 'připuštěno jako evidence', context: 'kontext (není důkaz od respondentů)', quarantined: 'v karanténě', refused: 'odmítnuto', not_evidence: 'data, ne evidence' };

function title(t: InspectorTarget): [string, string] {
  switch (t.type) {
    case 'source': return [src(t.id).title, 'Zdroj ' + t.id];
    case 'finding': return ['Zjištění ' + t.id, 'Analýza'];
    case 'claim': return ['Nárok ' + t.id, claim(t.id).admission === 'blocked' ? 'Blokováno' : 'Připuštěno'];
    case 'pair': return [objLabel(t.a) + ' – ' + objLabel(t.b), 'Dvojice v Sociomapě'];
    case 'object': return [objLabel(t.id), 'Objekt v Sociomapě'];
    case 'history': return [T.artifact.history, STAGES[t.stage].label];
    case 'details': return ['Vstupy, závislosti a původ', STAGES[t.stage].label];
    case 'impact': return ['Dopad návrhu', ''];
    case 'activity': return ['Podrobnosti činnosti', ''];
    case 'methodology': return ['Jak číst Sociomapu', MAP.method];
    case 'contract': return [T.artifact.contract, STAGES[t.stage].label + ' · průzkum, ne schválená architektura'];
    case 'context': return ['Co Vedoucí čte', 'Hierarchie kontextu'];
    case 'envelope': return ['Oprávnění hloubkového výzkumu', ENVELOPE.policy];
    case 'budget': return ['Rozpočet studie', 'USD'];
    case 'lifecycle': return ['Přehled fází', ''];
    case 'synthetic': return ['Fiktivní data a omezení', ''];
    case 'research': return ['Běh výzkumu ' + t.id, ''];
  }
}

export function Inspector() {
  const stack = useApp((s) => s.inspector);
  const top = stack[stack.length - 1];
  const opener = useRef<HTMLElement | null>(null);
  const panel = useRef<HTMLDivElement>(null);
  const open = !!top;

  useEffect(() => {
    if (open) { if (!opener.current) opener.current = document.activeElement as HTMLElement; panel.current?.focus(); }
    else if (opener.current) { opener.current.focus?.(); opener.current = null; }
  }, [open, top]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape' && open && !(e.target as HTMLElement).closest('.composer')) { e.preventDefault(); C.visual.closeInspector(); } };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [open]);
  if (!top) return null;
  const [h, sub] = title(top);
  return (
    <div className="insp" role="complementary" aria-label={'Inspektor: ' + h} ref={panel} tabIndex={-1}>
      <div className="insp__head">
        {stack.length > 1 && <button className="iconbtn" aria-label="Zpět" title="Zpět" onClick={() => C.visual.back()}><Icon name="back" size={16} /></button>}
        <div style={{ minWidth: 0, flex: 1 }}><div className="insp__title">{h}</div>{sub && <div className="insp__sub">{sub}</div>}</div>
        <button className="iconbtn" aria-label="Zavřít inspektor (Esc)" title="Zavřít (Esc)" onClick={() => C.visual.closeInspector()}><Icon name="close" size={16} /></button>
      </div>
      <div className="insp__body"><Body t={top} /></div>
    </div>
  );
}

function Body({ t }: { t: InspectorTarget }) {
  const s = useApp((x) => x);
  switch (t.type) {
    case 'source': {
      const x = src(t.id);
      return <>
        <div className="row"><span className={'kindtag kindtag--' + x.kind}>{KIND[x.kind]}</span><span className="chip">{x.cls}</span>{x.grade && x.grade !== '—' && <span className="chip">stupeň {x.grade}</span>}</div>
        <p className="cap">Fiktivní zdroj pro prototyp.</p>
        <h4>Pasáž</h4><blockquote className="quote">{x.passage}</blockquote><p className="cap">{x.locator}{x.retrieved ? ' · ' + x.retrieved : ''} · {x.where}</p>
        <h4>Přijetí</h4><p>{ADM[x.admission]}</p>
        {x.purpose && <><h4>Účel a spouštěč</h4><p>{x.purpose}<br /><span className="muted">{x.trigger}</span></p></>}
        <h4>Původ</h4><KV rows={x.provenance} />
        {x.kind === 'external' && <p className="cap">Externí zjištění je kontext. Nemění cílovou skupinu, metodiku ani zmrazené výsledky.</p>}
      </>;
    }
    case 'finding': {
      const f = FINDINGS.find((y) => y.id === t.id)!;
      return <>
        <p>{f.text}</p>
        <dl className="kvgrid"><dt>Druh</dt><dd>{f.register === 'finding' ? 'zjištění' : f.register === 'interpretation' ? 'výklad (ne měření)' : 'externí kontext'}</dd><dt>Otázka</dt><dd>{f.rq}</dd><dt>Revize</dt><dd>koncept · nerevidováno</dd>{f.uncertainty && <><dt>Nejistota</dt><dd>{f.uncertainty}</dd></>}</dl>
        {f.claims.length > 0 && <><h4>Nároky</h4>{f.claims.map((c) => <button key={c} className="listbtn" onClick={() => C.visual.inspect({ type: 'claim', id: c })}><span className="tag">{c}</span>{claim(c).text}<Icon name="next" size={13} /></button>)}</>}
        <h4>Zdroje</h4><SourceChips ids={f.sources} />
      </>;
    }
    case 'claim': {
      const c = claim(t.id);
      if (c.admission === 'blocked') return <><p><Glyph tone="blocked" size={12} /> <b>{c.text}</b></p><h4>Proč blokováno</h4><p>{c.reason}</p><p className="cap">Blokovaný nárok se do analýzy ani zprávy nedostane. AI ho nemůže připustit.</p></>;
      return <>
        <div className="claimval"><span className="big">{c.value}</span> <span className="muted">{c.unit}</span></div>
        <dl className="kvgrid"><dt>Báze</dt><dd>{c.denominator}</dd><dt>Interval</dt><dd>{c.interval}</dd>{c.comparison && <><dt>Srovnání</dt><dd>{c.comparison}</dd></>}<dt>Odkaz</dt><dd className="mono">{c.ref}</dd><dt>Přijetí</dt><dd>AdmittedClaim · interní povrch</dd></dl>
        <h4>Odkud číslo je</h4>
        <ol className="chain">
          <li>Věta ve zprávě nebo zjištění v analýze</li>
          <li>Nárok {c.id} připuštěný bránou evidence (politika pole, podpora, interval)</li>
          <li>{src(c.source).title} · <span className="mono">{src(c.source).locator}</span></li>
          <li>Běh {s.run.id} · revize {s.run.revision} · fiktivní respondenti</li>
        </ol>
        <SourceChips ids={[c.source]} />
        <p className="cap">Připuštění čísla ještě neznamená, že věta, která ho cituje, je platná: kontrola zprávy hlídá i jednotku, bázi a srovnání.</p>
      </>;
    }
    case 'pair': {
      const p = findPair(t.a, t.b);
      const ctx = s.evidenceAttached['pair.' + t.a + '~' + t.b] ?? s.evidenceAttached['pair.' + t.b + '~' + t.a] ?? [];
      const ha = MAP.objects.find((o) => o.id === t.a)?.height, hb = MAP.objects.find((o) => o.id === t.b)?.height;
      if (!p) return <p>Dvojice nemá uložený vztah.</p>;
      return <>
        <div className="row"><span className="kindtag kindtag--computed">Deterministický výsledek</span><span className="chip">{p.status === 'RELIABLE' ? 'spolehlivý' : p.status === 'WEAK' ? 'slabý (interval zahrnuje 0)' : 'neznámý (málo dat)'}</span></div>
        <dl className="kvgrid"><dt>r</dt><dd>{p.r == null ? '—' : fmt(p.r, 2) + ' [' + fmt(p.lo, 2) + '; ' + fmt(p.hi, 2) + ']'}</dd><dt>Podpora</dt><dd>n {p.n} hodnotících obě</dd><dt>Práh 0,10</dt><dd>{p.floor ? 'nad prahem' : 'pod prahem'}</dd><dt>Výšky</dt><dd>{fmt(ha)} a {fmt(hb)} z 10</dd><dt>Čára v mapě</dt><dd>{p.status === 'RELIABLE' && p.floor ? 'ano' : 'ne (jen po výběru)'}</dd></dl>
        <h4>Co to znamená</h4>
        <p>{p.status === 'UNKNOWN' ? 'Málo lidí hodnotilo obě banky; vztah neznáme.' : (p.r ?? 0) > 0 ? 'Relativní preference se pohybují spolu: kdo dá jedné bance víc než ostatním, dá víc i druhé.' : 'Relativní preference jdou proti sobě.'} Blízkost neznamená stejné hodnocení; výška je průměr, blízkost je souvislost.</p>
        <h4>Externí kontext</h4>
        {ctx.length ? <><SourceChips ids={ctx} /><p className="cap">{src(ctx[0]).passage}</p><p className="cap">Kontext vysvětluje, mapu nemění.</p></> : <><p className="muted">Žádný.</p><button className="btn btn--sm" disabled={s.busy} onClick={() => send('Dohledej kontext k dvojici ' + objLabel(t.a) + ' – ' + objLabel(t.b) + ' na mapě')}><Icon name="research" size={13} />Dohledat kontext</button></>}
        <h4>Zeptat se</h4><button className="btn btn--sm" disabled={s.busy} onClick={() => send('Proč je ' + objLabel(t.a) + ' blízko ' + objLabel(t.b) + '?')}>Proč jsou blízko?</button>
      </>;
    }
    case 'object': {
      const o = MAP.objects.find((x) => x.id === t.id)!;
      const rel = PAIRS.filter((p) => p.a === t.id || p.b === t.id);
      const m = SET1.find((x) => x.obj === o.label);
      return <>
        <dl className="kvgrid"><dt>Výška</dt><dd>{o.placed ? fmt(o.height) + ' z 10 (průměr)' : '—'}</dd><dt>Interval</dt><dd>{m?.mean != null ? '[' + fmt(m.lo) + '; ' + fmt(m.hi) + ']' : '—'}</dd><dt>Kish n</dt><dd>{m?.n}</dd><dt>Na mapě</dt><dd>{o.placed ? 'ano' : o.note}</dd></dl>
        <h4>Vztahy</h4>
        {rel.map((p) => { const other = p.a === t.id ? p.b : p.a; return <button key={other} className="listbtn" onClick={() => { C.visual.select('sociomap', p.a + '~' + p.b); C.visual.inspect({ type: 'pair', a: p.a, b: p.b }); }}><span className="grow">{objLabel(other)}</span><span className="muted">{p.r == null ? 'neznámý' : 'r ' + fmt(p.r, 2) + ' · ' + (p.status === 'RELIABLE' ? 'spolehlivý' : 'slabý')}</span><Icon name="next" size={13} /></button>; })}
      </>;
    }
    case 'history': {
      const acc = s.accepted[t.stage] ?? [];
      const props = s.proposals.filter((p) => p.stage === t.stage);
      return <>
        <h4>Aktuálně</h4><p>{t.stage === 'report' ? 'Koncept ' + s.reportState.draft : 'Obsah z revize ' + contentRev(s, t.stage) + ' · studie na revizi ' + s.revision}{s.run.status === 'completed' && ' · běh ' + s.run.id + ' použil revizi ' + s.run.revision}</p>
        <h4>Přijaté změny</h4>
        {acc.length ? <ul className="plain">{[...acc].reverse().map((o) => <li key={o.id}><span className="mono">{o.note?.split(' · ')[0]}</span> {C.describeOp(o.op)} <span className="muted">· {o.note?.split(' · ').slice(1).join(' · ')} · {o.actor === 'you' ? 'vy' : 'z návrhu'}</span></li>)}</ul> : <p className="muted">Výchozí obsah fixture.</p>}
        <h4>Pracovní verze</h4>{(s.working[t.stage] ?? []).length ? <ul className="plain">{(s.working[t.stage] ?? []).map((o) => <li key={o.id}>{C.describeOp(o.op)} <span className="muted">· {o.at}</span></li>)}</ul> : <p className="muted">Bez neuložených úprav.</p>}
        <h4>Návrhy</h4>{props.length ? <ul className="plain">{[...props].reverse().map((p) => <li key={p.id}>{p.title} <span className="muted">· {p.baseLabel} · {({ pending: 'čeká', accepted: 'přijato', rejected: 'odmítnuto', stale: 'zastaralé', superseded: 'nahrazeno' } as const)[p.status]}{p.rebuiltFrom ? ' · sestaveno znovu' : ''}</span></li>)}</ul> : <p className="muted">Žádné.</p>}
      </>;
    }
    case 'details': return <Details stage={t.stage} />;
    case 'impact': return <p>Viz „Dopad a pokrytí“ v liště návrhu.</p>;
    case 'activity': {
      const a = s.activities.find((x) => x.id === t.id);
      if (!a) return null;
      return <><p><b>{a.title}</b> · {a.summary}</p><KV rows={a.details} /></>;
    }
    case 'methodology': return <>
      <h4>Vzdálenost</h4><p>Blízkost dvou bank = jak moc se u lidí pohybují jejich relativní preference spolu (Pearsonovo r z hodnocení přeškálovaných na každého člověka). Neznamená stejné hodnocení.</p>
      <h4>Výška</h4><p>Průměrné hodnocení banky 1–10. Výška nikdy není blízkost.</p>
      <h4>Stav dvojice</h4><p>Spolehlivá: Kish n ≥ 30 a interval nezahrnuje 0. Slabá: interval zahrnuje 0. Neznámá: méně než 30. Čára se kreslí jen u spolehlivých s |r| ≥ 0,10.</p>
      <h4>Shoda (Stress-1)</h4><p>&lt; 0,05 výborná · &lt; 0,10 dobrá · &lt; 0,20 přijatelná · ≥ 0,20 slabá.</p>
      <h4>Nezmapovaní lidé</h4><p>Kdo dal všem stejně, nemá relativní preference: nevstupuje do vztahů, ale počítá se do výšek a podpory.</p>
      <h4>Co je otevřené</h4><p className="cap">Prahy a štítky jsou ze specifikace aia-sociomap-3 (σ terénu 0,25 je dočasné). Hodnoty v prototypu jsou ilustrativní. Změna metodiky = nová verze v Nastavení → Metodika, ne úprava mapy.</p>
    </>;
    case 'contract': {
      const c = CONTRACTS[t.stage];
      return <>
        <p className="cap">Průzkum: co by Vedoucí z artefaktu četl a co smí. Vizuální akce mění jen obraz; doménové akce jsou příkazy AIA se stejnými pravidly jako tlačítka.</p>
        <h4>Čitelný stav</h4><ul className="plain">{c.readable.map((x) => <li key={x}>{x}</li>)}</ul>
        <h4>Vizuální akce</h4><ul className="plain mono">{c.visual.map((x) => <li key={x}>{x}</li>)}</ul>
        <h4>Doménové příkazy</h4><ul className="plain mono">{c.domain.map((x) => <li key={x}>{x}</li>)}</ul>
        <h4>Revize a kontext</h4><p>{c.revision}</p>
        <h4>Odmítnutí</h4><ul className="plain">{c.refusals.map((x) => <li key={x}>{x}</li>)}</ul>
        <h4>Stabilní identifikátory</h4><p className="mono cap">data-aia="{t.stage}.&lt;oddíl&gt;.&lt;prvek&gt;"</p>
      </>;
    }
    case 'context': return <>
      <ol className="chain">
        <li><b>Instrukce a metodika AIA</b> · pravidla nelze změnit dokumentem ani zprávou</li>
        <li><b>Klient</b> · {STUDY.client} · znalosti klienta (schválené), třída A</li>
        <li><b>Studie</b> · {STUDY.name} · revize {s.revision}</li>
        <li><b>Revize / běh</b> · {s.run.status === 'completed' ? s.run.id + ' (revize ' + s.run.revision + ')' : 'zatím bez běhu'}</li>
        <li><b>Artefakt a úkol</b> · {STAGES[s.stage].label}{s.selection[s.stage] ? ' · vybráno ' + s.selection[s.stage] : ''}</li>
      </ol>
      <h4>Čte tento tah</h4><p>Aktuální artefakt (pracovní verzi i přijatou revizi), čekající návrhy, stav kroků, posledních 20 zpráv a shrnutí starší konverzace.</p>
      <h4>Nečte</h4><p>Celou databázi, všechny dokumenty klienta ani celou historii konverzace. Dokumenty a pasáže jsou data, ne pokyny.</p>
      <h4>Inference</h4><p>Každé volání modelu jde přes GovernedModelGateway na trasu bedrock-eu-primary; Vedoucí ani specialista poskytovatele nevolí.</p>
    </>;
    case 'envelope': return <>
      <h4>Účely</h4><ul className="plain">{ENVELOPE.purposes.map((x) => <li key={x}>{x}</li>)}</ul>
      <h4>Schválené trasy</h4><ul className="plain">{ENVELOPE.routes.map((x) => <li key={x}>{x}</li>)}</ul>
      <h4>Třídy dat</h4><p>{ENVELOPE.classes}</p>
      <h4>Nepovoleno</h4><ul className="plain">{ENVELOPE.notAllowed.map((x) => <li key={x}>{x}</li>)}</ul>
      <h4>Limity</h4><p>{ENVELOPE.perRun} USD na běh · rozpočet studie {s.budget.studyLimit} USD. Uvnitř těchto mezí běží výzkum bez dalšího potvrzení.</p>
      <h4>Běhy</h4>{s.research.length ? <ul className="plain">{s.research.map((r) => <li key={r.id}><b>{r.id}</b> {r.purpose} · {r.target} · {r.status === 'done' ? 'hotovo' : 'běží'} · {fmt(r.spent, 2)} USD · {r.admitted} připuštěno, {r.quarantined} karanténa{r.noEvidence ? ', ' + r.noEvidence + ' bez evidence' : ''}</li>)}</ul> : <p className="muted">Zatím žádné.</p>}
      <p className="cap">Rozsah, třídu, trasu ani oprávnění neurčují argumenty modelu; ověřuje je AIA (RetrievalGate).</p>
    </>;
    case 'budget': {
      const b = s.budget;
      return <>
        <dl className="kvgrid"><dt>Limit studie</dt><dd>{fmt(b.studyLimit, 2)} USD</dd><dt>Utraceno</dt><dd>{fmt(b.studySpent, 2)} USD</dd><dt>Rezervováno</dt><dd>{fmt(b.studyReserved, 2)} USD</dd><dt>Zbývá</dt><dd>{fmt(b.studyLimit - b.studySpent - b.studyReserved, 2)} USD</dd><dt>Potvrzení útraty</dt><dd>když strop běhu ≥ {b.spendConfirm} USD</dd><dt>Výzkum na běh</dt><dd>≤ {ENVELOPE.perRun} USD</dd></dl>
        <h4>Položky</h4><ul className="plain">{s.activities.filter((a) => a.details.some(([k]) => k === 'Náklad')).map((a) => <li key={a.id}>{a.title} · {a.details.find(([k]) => k === 'Náklad')![1]}</li>)}</ul>
        <p className="cap">Každé placené volání má rezervaci před odesláním a vyrovná se jednou.</p>
      </>;
    }
    case 'synthetic': return <>
      <p>{T.synthetic.long}</p>
      <ul className="plain"><li>Respondenti: fiktivní AI respondenti (SYNTHETIC_AI_FICTIONAL), ne lidé ani modelovaný panel.</li><li>Populace LIVE v17_4_0 je zaznamenána, ale nenačtena: výsledky nepopisují populaci ČR.</li><li>Výsledky, mapy a zpráva jsou jen interní; klientskou zprávu AIA odmítne.</li><li>Upozornění je v záhlaví a zápatí každé zprávy i exportu.</li></ul>
    </>;
    case 'lifecycle': return null;
    case 'research': return null;
  }
}

function Details({ stage }: { stage: StageId }) {
  const s = useApp((x) => x);
  const idx = STAGE_ORDER.indexOf(stage);
  const inputs: Record<StageId, string> = {
    brief: 'Podklady klienta (třída A)', design: 'Zadání', questionnaire: 'Návrh výzkumu', audience: 'Zadání, populace LIVE', dimensions: 'Populace, výzkumné otázky', sample: 'Cílová skupina, dimenze',
    fieldwork: 'Přijatá revize: dotazník, cílová skupina, vzorek', results: 'Dataset běhu', sociomap: 'Sada 1 z datasetu běhu', analysis: 'Agregace, Sociomapa (připuštěné nároky)', report: 'Analýza, kapitoly z běhu',
  };
  const feeds: Record<StageId, string> = {
    brief: 'Návrh', design: 'Dotazník, Analýza (pokrytí)', questionnaire: 'Sběr dat, Výsledky, Sociomapa', audience: 'Vzorek, Sběr dat', dimensions: 'Sběr dat (persony)', sample: 'Sběr dat',
    fieldwork: 'Výsledky, Sociomapa', results: 'Analýza, Zpráva', sociomap: 'Analýza (výklad mapy), Zpráva', analysis: 'Zpráva', report: '—',
  };
  const log = s.log.filter((l) => l.stage === stage).slice(-8).reverse();
  return <>
    <dl className="kvgrid"><dt>Krok</dt><dd>{idx + 1} z 11 · {STAGES[stage].product}</dd><dt>Vstupy</dt><dd>{inputs[stage]}</dd><dt>Napájí</dt><dd>{feeds[stage]}</dd><dt>Revize</dt><dd>{stage === 'report' ? 'koncept ' + s.reportState.draft : 'obsah r' + contentRev(s, stage) + ' · studie r' + s.revision}</dd></dl>
    <p className="cap">Pořadí v navigaci není graf závislostí: Analýza čte připuštěné výsledky, výklad mapy závisí na mapě.</p>
    <h4>Specialisté a činnosti</h4>
    <ul className="plain">{s.activities.filter((a) => a.link?.stage === stage).slice(-6).map((a) => <li key={a.id}><button className="linkbtn" onClick={() => C.visual.inspect({ type: 'activity', id: a.id })}>{a.title}</button> <span className="muted">· {a.summary}</span></li>)}</ul>
    <h4>Příkazy (UI i Vedoucí stejnou cestou)</h4>
    {log.length ? <ul className="plain">{log.map((l) => <li key={l.id}><Glyph tone={l.ok ? 'done' : 'blocked'} size={10} /> <span className="mono">{l.cmd}</span> <span className="muted">· {l.by === 'ui' ? 'vy (UI)' : l.by === 'lead' ? 'Vedoucí' : l.by === 'worker' ? 'specialista' : 'systém'} · {l.at}{l.reason ? ' · ' + l.reason : ''}</span></li>)}</ul> : <p className="muted">Zatím žádné.</p>}
  </>;
}

export function KV({ rows }: { rows: [string, string][] }) {
  return <dl className="kvgrid">{rows.map(([k, v], i) => <Fragment key={i}><dt>{k}</dt><dd>{v}</dd></Fragment>)}</dl>;
}
