// Research-design artifacts: Brief, Design (with research-question coverage) and
// Questionnaire (the editor: blocks, routing, answer formats, tracked sets,
// protected inputs, coverage).
import { useApp } from '../app/store';
import { workingDoc, questionnaireMinutes, acceptedDoc } from '../model/doc';
import { RQS, src, type Item as DocItem } from '../model/fixture';
import { Sec, Item, useProposals, AddItem, SourceChips, Unavailable, StageLink } from '../components/ui';
import { Icon } from '../components/Icons';
import { Glyph } from '../components/Glyph';
import * as C from '../app/commands';

export function BriefArt() {
  const doc = useApp((s) => workingDoc(s, 'brief'));
  const { props, stale } = useProposals('brief');
  return (
    <div className="page">
      {doc.sections.map((sec, i) => (
        <Sec key={sec.id} id={'brief.' + sec.id} n={String(i + 1)} title={sec.title} aside={sec.id === 'mat' ? 'třída dat určuje, kam smí' : undefined}>
          {sec.items.map((it) => (
            <Item key={it.id} stage="brief" sec={sec.id} id={it.id} field="text" value={String(it.text)} label={it.id} props={props} stale={stale} removable={sec.id !== 'mat'} movable={sec.id === 'obj'}>
              <div className="row"><span className="tag">{it.id}</span><span className="grow">{String(it.text)}</span>
                {sec.id === 'mat' && <span className="chip">{String(it.cls)}</span>}{it.note ? <span className="chip chip--line">{String(it.note)}</span> : null}</div>
            </Item>
          ))}
          {sec.id !== 'mat' && <AddItem stage="brief" sec={sec.id} label="Přidat položku" make={(text) => ({ id: sec.id[0].toUpperCase() + (sec.items.length + 1) + 'x', text })} />}
          {sec.id === 'mat' && <Unavailable kind="simulated">Nahrání souboru je v prototypu jen ukázkou; v AIA jde přes Přidat podklady klienta.</Unavailable>}
        </Sec>
      ))}
    </div>
  );
}

const RQ_STATE: Record<string, { word: string; tone: 'done' | 'done-warn' | 'blocked' }> = {
  covered: { word: 'pokryto', tone: 'done' }, partial: { word: 'částečně', tone: 'done-warn' }, gap: { word: 'mezera', tone: 'blocked' },
};

export function DesignArt() {
  const doc = useApp((s) => workingDoc(s, 'design'));
  const q = useApp((s) => acceptedDoc(s, 'questionnaire'));
  const sel = useApp((s) => s.selection.design);
  const coding = useApp((s) => s.codingAccepted);
  const { props, stale } = useProposals('design');
  const qItems = new Set(q.sections.flatMap((x) => x.items.map((i) => i.id)));
  const rqSec = doc.sections.find((x) => x.id === 'rq')!;
  return (
    <div className="page">
      <Sec id="design.rq" n="1" title="Výzkumné otázky a jejich pokrytí" aside="pokrytí počítá AIA (research_trace)">
        <p className="cap" style={{ margin: '0 0 8px' }}>Každá otázka vede k rozhodnutí, měření, analýze a místu ve zprávě. Otázka „které a proč“ potřebuje výběr i rozbor důvodů.</p>
        {rqSec.items.map((it) => {
          const rq = RQS.find((r) => r.id === it.id);
          const status = rq ? (rq.id === 'RQ2' && coding ? 'covered' : rq.status) : 'gap';
          const st = RQ_STATE[status];
          const open = sel === it.id;
          return (
            <Item key={it.id} stage="design" sec="rq" id={it.id} field="text" value={String(it.text)} label={it.id} props={props} stale={stale}>
              <div className="row"><span className="tag">{it.id}</span><span className="grow"><b>{String(it.text)}</b></span><span className="chip"><Glyph tone={st.tone} size={10} />{st.word}</span></div>
              {rq && (
                <dl className={'covgrid' + (open ? ' is-open' : '')}>
                  <dt>Rozhodnutí</dt><dd><StageLink stage="brief" focus={rq.decision}>{rq.decision}</StageLink></dd>
                  <dt>Měření</dt><dd>{rq.measures.join(' · ')}</dd>
                  <dt>Položky dotazníku</dt><dd>{rq.items.map((x) => <span key={x} className={'qref' + (qItems.has(x) ? '' : ' is-gone')}><StageLink stage="questionnaire" focus={x}>{x}</StageLink>{!qItems.has(x) && ' (sloučeno do Q8)'}</span>)}</dd>
                  {open && <>
                    <dt>Analýza</dt><dd>{rq.method}</dd>
                    <dt>Očekávaná odpověď</dt><dd>{rq.expected}</dd>
                    <dt>Hotovo, když</dt><dd>{rq.complete}</dd>
                    <dt>Ve zprávě</dt><dd><StageLink stage="report">{rq.report}</StageLink></dd>
                  </>}
                  <dt>Mezery</dt><dd>{rq.id === 'RQ2' && coding ? 'žádné (kódování přijato)' : rq.gaps.length ? rq.gaps.join(' · ') : 'žádné'}</dd>
                </dl>
              )}
              {!open && rq && <button className="linkbtn cap" onClick={(e) => { e.stopPropagation(); C.visual.select('design', it.id); }}>Celý řetěz: analýza, odpověď, kritérium, zpráva</button>}
            </Item>
          );
        })}
        <AddItem stage="design" sec="rq" label="Přidat výzkumnou otázku" make={(text) => ({ id: 'RQ' + (rqSec.items.length + 1), text })} />
      </Sec>
      {doc.sections.filter((x) => x.id !== 'rq').map((sec, i) => (
        <Sec key={sec.id} id={'design.' + sec.id} n={String(i + 2)} title={sec.title}>
          {sec.items.map((it) => (
            <Item key={it.id} stage="design" sec={sec.id} id={it.id} field="text" value={String(it.text)} label={it.id} props={props} stale={stale} removable>
              <div className="row"><span className="tag">{it.id}</span><span className="grow">{String(it.text)}</span>{sec.id === 'open' && <span className="chip chip--you">čeká na metodické rozhodnutí</span>}</div>
            </Item>
          ))}
        </Sec>
      ))}
      <Sec n="4" title="Hloubkový výzkum pro návrh" aside="mimo pořadí kroků">
        <p style={{ margin: 0 }}>Výzkum pro návrh (DESIGN_RESEARCH) může jen navrhnout; novou revizi vytváří člověk. Zjištění se připojují k místu, kterého se týkají, např. <StageLink stage="audience" focus="A1">předpokladům v Cílové skupině</StageLink>.</p>
      </Sec>
    </div>
  );
}

const TYPE_WORD: Record<string, string> = { number: 'číslo', single: 'jedna možnost', multi: 'více možností', open: 'otevřená', scale: 'škála', rank: 'pořadí', set: 'sledovaná sada · škála 1–10' };

export function QuestionnaireArt() {
  const doc = useApp((s) => workingDoc(s, 'questionnaire'));
  const before = useApp((s) => acceptedDoc(s, 'questionnaire'));
  const { props, stale } = useProposals('questionnaire');
  const mins = questionnaireMinutes(doc);
  const rqCount = (id: string) => doc.sections.flatMap((s) => s.items).filter((i) => (i.rq as string[] | undefined)?.includes(id)).length;
  return (
    <div className="page">
      <div className="strip">
        <span><b>{doc.sections.reduce((n, s) => n + s.items.length, 0)}</b> položek</span>
        <span>≈ <b>{String(mins).replace('.', ',')}</b> min{questionnaireMinutes(before) !== mins && <span className="muted"> (přijato {String(questionnaireMinutes(before)).replace('.', ',')})</span>}</span>
        <span className="strip__rq">Pokrytí: {RQS.map((r) => <span key={r.id} className={'rqpill' + (rqCount(r.id) ? '' : ' is-gap')} title={rqCount(r.id) + ' položek měří ' + r.id}>{r.id} {rqCount(r.id)}</span>)}</span>
      </div>
      {doc.sections.map((sec, i) => (
        <Sec key={sec.id} id={'questionnaire.' + sec.id} n={'B' + (i + 1)} title={sec.title} aside={sec.locked ? <span className="lockline"><Icon name="lock" size={11} />{sec.locked}</span> : undefined}>
          {sec.items.map((it: DocItem) => (
            <Item key={it.id} stage="questionnaire" sec={sec.id} id={it.id} field="q" value={String(it.q)} label={it.id} locked={(it.lock as string) || sec.locked} props={props} stale={stale} movable={!sec.locked} removable={!sec.locked && !it.lock}>
              <div className="qrow">
                <span className="tag">{it.id}</span>
                <div className="grow">
                  <div className="qtext">{String(it.q)}</div>
                  <div className="qmeta">
                    <span>{TYPE_WORD[String(it.type)] ?? String(it.type)}</span>
                    {it.options ? <span className="muted">{String(it.options)}</span> : null}
                  </div>
                  {it.route ? <div className="qroute"><Icon name="next" size={12} />zobrazit, pokud {String(it.route)}</div> : null}
                  {it.lock ? <div className="cap">{String(it.lock)}</div> : null}
                </div>
                <div className="qside">
                  {((it.rq as string[] | undefined) ?? []).map((r) => <span key={r} className="rqpill">{r}</span>)}
                  <span className="cap">{Math.round(Number(it.d))} s</span>
                </div>
              </div>
            </Item>
          ))}
        </Sec>
      ))}
      <Sec title="Závislosti" n="—">
        <ul className="plain">
          <li>Sada 1 → <StageLink stage="sociomap">Sociomapa</StageLink> (vstup výpočtu) a <StageLink stage="results" focus="set1">Výsledky</StageLink>.</li>
          <li>Q8 → Q9 (větvení). Q9 je otevřená odpověď: data, ne připuštěná evidence; rozbor viz <StageLink stage="analysis" focus="q9">Analýza</StageLink>.</li>
          <li>Q15 a Q16 měří dva konstrukty (znalost banky, znalost produktů) pro RQ4.</li>
        </ul>
        <p className="cap">Zdroj pro pokrytí: {src('S8').title} <SourceChips ids={['S8']} /></p>
      </Sec>
    </div>
  );
}
