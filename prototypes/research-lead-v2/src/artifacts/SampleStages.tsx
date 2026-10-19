// Sample-definition artifacts: Audience (definition, filters, assumptions with
// attached evidence), Dimensions (definitions, sources, usage) and Sample
// (composition, constraints, support forecast, readiness).
import { useApp, update } from '../app/store';
import { workingDoc } from '../model/doc';
import { readiness, SAMPLE, src } from '../model/fixture';
import { Sec, Item, useProposals, SourceChips, Unavailable, StageLink, AddItem } from '../components/ui';
import { Glyph } from '../components/Glyph';
import { Icon } from '../components/Icons';
import { STAGE_ORDER, STAGES } from '../model/terms';
import { pendingProposals } from '../model/status';
import { send } from '../app/scenarios';
import * as C from '../app/commands';

export function AudienceArt() {
  const doc = useApp((s) => workingDoc(s, 'audience'));
  const attached = useApp((s) => s.evidenceAttached);
  const research = useApp((s) => s.research.find((r) => r.targetRef === 'audience.ass'));
  const busy = useApp((s) => s.busy);
  const { props, stale } = useProposals('audience');
  const def = doc.sections.find((x) => x.id === 'def')!;
  const flt = doc.sections.find((x) => x.id === 'flt')!;
  const ass = doc.sections.find((x) => x.id === 'ass')!;
  return (
    <div className="page">
      <Sec id="audience.def" n="1" title="Definice cílové skupiny">
        {def.items.map((it) => <Item key={it.id} stage="audience" sec="def" id={it.id} field="text" value={String(it.text)} label="Definice" props={props} stale={stale}><div>{String(it.text)}</div></Item>)}
      </Sec>
      <Sec id="audience.flt" n="2" title="Filtry populace" aside={flt.note}>
        <table className="tbl">
          <thead><tr><th>Faktor</th><th>Hodnota</th><th className="n">Odpovídá v populaci</th></tr></thead>
          <tbody>{flt.items.map((it) => <tr key={it.id} data-aia={'audience.flt.' + it.id}><td>{String(it.factor)}</td><td>{String(it.value)}</td><td className="n">{String(it.count)}</td></tr>)}</tbody>
        </table>
        <p className="cap">Náhled vrací jen počty, žádné řádky. Vzorek lze z LIVE vylosovat (n 400). <Unavailable>Vlastní a speciální panely.</Unavailable></p>
      </Sec>
      <Sec id="audience.ass" n="3" title="Předpoklady o cílové skupině" aside={research ? research.id + ' · ' + (research.status === 'done' ? 'dokončeno' : 'běží') : 'bez evidence'}>
        <p className="cap" style={{ margin: '0 0 6px' }}>Externí evidence je kontext pro návrh, ne měření u respondentů. Stav předpokladu se mění jen přijetím návrhu.</p>
        {ass.items.map((it) => {
          const ev = attached['ass.' + it.id] ?? [];
          return (
            <Item key={it.id} stage="audience" sec="ass" id={it.id} field="text" value={String(it.text)} label={it.id} props={props} stale={stale} removable>
              <div className="row"><span className="tag">{it.id}</span><span className="grow">{String(it.text)}</span><span className={'chip' + (String(it.status).startsWith('nepodlo') ? ' chip--line' : '')}>{String(it.status)}</span></div>
              {ev.map((id) => {
                const s = src(id);
                return (
                  <div key={id} className="evline" data-aia={'audience.ass.' + it.id + '.evidence.' + id}>
                    <span className={'kindtag kindtag--' + s.kind}>{s.kind === 'external' ? 'Externí výzkum' : 'Znalost klienta'}</span>
                    <span className="grow"><span className="serif">{s.passage}</span> <span className="cap">{s.title} · {s.locator}</span></span>
                    <SourceChips ids={[id]} />
                  </div>
                );
              })}
              {it.id === 'A3' && ev.length > 0 && <div className="cap">Žádný zdroj nepopisuje skutečné složení klientů. Chybí: data o složení klientů (nedodáno).</div>}
            </Item>
          );
        })}
        <AddItem stage="audience" sec="ass" label="Přidat předpoklad" make={(text) => ({ id: 'A' + (ass.items.length + 1), text, status: 'k ověření' })} />
        {!research && <div className="actionrow"><button className="btn btn--sm" disabled={busy} onClick={() => send('Ověř předpoklady o cílové skupině')}><Icon name="research" size={14} />Požádat Vedoucího o ověření</button><span className="cap">V rámci schváleného oprávnění · odhad ≤ 0,50 USD</span></div>}
      </Sec>
    </div>
  );
}

export function DimensionsArt() {
  const doc = useApp((s) => workingDoc(s, 'dimensions'));
  const { props, stale } = useProposals('dimensions');
  const sec = doc.sections[0];
  return (
    <div className="page">
      <Sec id="dimensions.dim" n="1" title="Vybrané dimenze" aside="politika pole rozhoduje o použití (decide)">
        {sec.items.map((it) => (
          <Item key={it.id} stage="dimensions" sec="dim" id={it.id} field="def" value={String(it.def)} label={String(it.name)} props={props} stale={stale} removable>
            <div className="dimrow">
              <div><b>{String(it.name)}</b><div className="muted">{String(it.def)}</div></div>
              <div className="cap">{String(it.source)}</div>
              <div className="cap">{String(it.use)}</div>
              <div>{it.topic ? <span className="chip"><Glyph tone="done" size={10} />téma persony: {String(it.topic)}</span> : <span className="chip chip--line"><Glyph tone="done-warn" size={10} />bez tématu persony</span>}</div>
            </div>
          </Item>
        ))}
        <p className="cap">Dimenze bez tématu persony se respondentům nepředá (dimensions_unmatched); běh ji pojmenuje v „Kdo odpovídal“.</p>
      </Sec>
      <Sec n="2" title="Vlastní dimenze klienta">
        <p style={{ margin: 0 }}>Materializace dimenze klienta do vlastní populace probíhá jako samostatný běh. <Unavailable kind="simulated">V prototypu jen popsáno.</Unavailable></p>
      </Sec>
    </div>
  );
}

export function SampleArt() {
  const s = useApp((x) => x);
  const items = readiness({ questionnaireAccepted: true, audienceAccepted: true, spendConfirmed: true, proposalsPending: pendingProposals(s, 'questionnaire').length, workingStages: STAGE_ORDER.filter((x) => (s.working[x] ?? []).length) });
  const blocking = items.filter((i) => i.state === 'you' || i.state === 'fail');
  const warns = items.filter((i) => i.state === 'warn');
  return (
    <div className="page">
      <Sec id="sample.size" n="1" title="Velikost a složení" aside={'n ' + SAMPLE.n}>
        <div className="cols">
          <table className="tbl grow"><thead><tr><th>Kvótní buňka</th><th className="n">Podíl</th><th className="n">n</th></tr></thead>
            <tbody>{SAMPLE.quotas.map((q) => <tr key={q.cell}><td>{q.cell}</td><td className="n">{q.share}</td><td className="n">{q.n}</td></tr>)}</tbody></table>
          <ul className="plain side">{SAMPLE.constraints.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
        <p className="cap">Velikost vzorku se v AIA nastavuje v kroku Dimenze; zde je přehled.</p>
      </Sec>
      <Sec id="sample.forecast" n="2" title="Odhad podpory před během" aside="odhad, ne výsledek">
        <table className="tbl"><tbody>{SAMPLE.forecast.map((f) => <tr key={f.what}><td><Glyph tone={f.verdict === 'ok' ? 'done' : 'done-warn'} size={10} /> {f.what}</td><td className="n">{f.value}</td></tr>)}</tbody></table>
        <p className="cap">Skutečná podpora dvojic se ověří až z výsledných dat (<StageLink stage="sociomap">Sociomapa</StageLink>). Kvóta ji nezaručuje.</p>
      </Sec>
      <Sec id="sample.ready" n="3" title="Připravenost ke spuštění" aside={blocking.length ? blocking.length + ' brání spuštění' : warns.length + ' varování, nic nebrání'}>
        <ul className="ready">
          {items.map((i) => (
            <li key={i.id} data-aia={'sample.ready.' + i.id}>
              <Glyph tone={i.state === 'pass' ? 'done' : i.state === 'warn' ? 'done-warn' : i.state === 'you' ? 'you' : 'fault'} size={12} title={i.state} />
              <span className="grow">{i.text}{i.note && <span className="muted"> · {i.note}</span>}</span>
              <button className="linkbtn cap" onClick={() => C.visual.open(i.where)}>{STAGES[i.where].label}</button>
            </li>
          ))}
        </ul>
        <div className="actionrow">
          <button className="btn btn--sm" onClick={() => C.visual.open('fieldwork')}>Pokračovat na Sběr dat<Icon name="next" size={13} /></button>
          {warns.length > 0 && <span className="cap">Lze pokračovat s omezeními (ADR 0025).</span>}
        </div>
      </Sec>
      <Sec n="4" title="Kdo bude odpovídat">
        <label className="radio"><input type="radio" name="ps" defaultChecked /> Fiktivní AI respondenti <span className="cap">výchozí · výsledky jen interní</span></label>
        <label className="radio is-off"><input type="radio" name="ps" disabled /> Panel z populace <span className="cap">nenabízeno: AIA_AI_POPULATION_PERSONAS_ENABLED je vypnuto</span></label>
        <button className="linkbtn cap" onClick={() => update((d) => { d.inspector.push({ type: 'synthetic' }); })}>Co znamenají fiktivní respondenti</button>
      </Sec>
    </div>
  );
}
