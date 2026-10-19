// The Study's one Research Lead conversation. Patterns after Open WebUI at
// aa8ce52 (see docs/donor-inventory.md): stick to the bottom only while the
// reader is at the bottom, a return-to-latest button otherwise, older messages
// loaded on request, hover/focus message actions, collapsible tool activity,
// grouped consecutive completed activity, queued follow-ups, stop.
import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useApp, update } from '../app/store';
import * as C from '../app/commands';
import { STAGES, T } from '../model/terms';
import type { Activity, Block, Message } from '../model/types';
import { Icon, Mark } from './Icons';
import { Glyph } from './Glyph';
import { Composer } from './Composer';
import { send, onDecision } from '../app/scenarios';
import { src } from '../model/fixture';

const saved = { top: -1, bottom: true, visible: 40, scenario: '' };

export function Conversation() {
  const s = useApp((x) => x);
  const msgs = s.messages;
  const box = useRef<HTMLDivElement>(null);
  const atBottom = useRef(saved.bottom);
  const [away, setAway] = useState(!saved.bottom);
  const [unread, setUnread] = useState(0);
  const [visible, setVisible] = useState(saved.visible);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const prevLen = useRef(msgs.length);

  // Restore the reading position when the conversation is shown again (focus modes).
  useLayoutEffect(() => {
    const el = box.current; if (!el) return;
    el.scrollTop = saved.bottom || saved.top < 0 ? el.scrollHeight : saved.top;
    return () => { saved.top = el.scrollTop; saved.bottom = atBottom.current; };
  }, []);
  useEffect(() => { saved.visible = visible; }, [visible]);

  const last = msgs[msgs.length - 1];
  const sig = msgs.length + ':' + (last?.shown ?? '') + ':' + s.activities.map((a) => a.summary + a.steps.length + a.status).join('|') + s.decisions.map((d) => d.status).join('');
  useLayoutEffect(() => {
    const el = box.current; if (!el) return;
    const added = msgs.length - prevLen.current;
    prevLen.current = msgs.length;
    if (atBottom.current) el.scrollTop = el.scrollHeight;
    else if (added > 0) setUnread((n) => n + added);
  }, [sig]); // eslint-disable-line react-hooks/exhaustive-deps

  // A scenario switch replaces the whole conversation: start at its end.
  useEffect(() => {
    if (saved.scenario === s.scenario) return;
    saved.scenario = s.scenario;
    atBottom.current = true; setAway(false); setUnread(0); setVisible(40);
    requestAnimationFrame(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; });
  }, [s.scenario]);

  // Content that grows without a new message (streaming, follow-ups, an activity
  // card expanding) keeps the view at the bottom only if the reader is there.
  const inner = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current, inn = inner.current; if (!el || !inn) return;
    const ro = new ResizeObserver(() => { if (atBottom.current) el.scrollTop = el.scrollHeight; });
    ro.observe(inn);
    return () => ro.disconnect();
  }, []);

  // A scroll event can arrive after content has grown again; only a move UP by
  // the reader releases the bottom.
  const lastTop = useRef(0);
  const intent = useRef(0);
  const touched = () => { intent.current = Date.now(); };
  const onScroll = () => {
    const el = box.current!;
    const up = el.scrollTop < lastTop.current - 1 && Date.now() - intent.current < 600;
    lastTop.current = el.scrollTop;
    const b = el.scrollHeight - el.scrollTop - el.clientHeight <= 24 || (atBottom.current && !up);
    atBottom.current = b; setAway(!b); if (b) setUnread(0);
  };
  const toLatest = () => { const el = box.current!; el.scrollTo({ top: el.scrollHeight, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); atBottom.current = true; setAway(false); setUnread(0); };

  const start = Math.max(0, msgs.length - visible);
  const shown = msgs.slice(start);
  const groups = useMemo(() => group(shown, s.activities), [shown, s.activities]);
  const lastLead = [...msgs].reverse().find((m) => m.kind === 'lead');

  return (
    <div className="conv">
      <div className="conv__head">
        <div className="conv__avatar"><Mark size={18} onDark /></div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="conv__who">{T.app.lead}</div>
          <div className="conv__sees">{T.conv.sees}: {STAGES[s.stage].label}{s.selection[s.stage] ? ' · ' + s.selection[s.stage] : ''} · {s.stage === 'report' ? 'koncept ' + s.reportState.draft : ['fieldwork', 'results', 'sociomap', 'analysis'].includes(s.stage) && s.run.status !== 'none' && s.run.status !== 'ready' ? 'běh ' + s.run.id + ' (r' + s.run.revision + ')' : 'revize ' + s.revision + ((s.working[s.stage] ?? []).length ? ' + pracovní úpravy' : '')}</div>
        </div>
        <button className="iconbtn" title="Co Vedoucí čte" aria-label="Co Vedoucí čte" onClick={() => C.visual.inspect({ type: 'context' })}><Icon name="why" size={16} /></button>
        <button className={'iconbtn' + (s.mode === 'conversation' ? ' is-on' : '')} aria-pressed={s.mode === 'conversation'} title={s.mode === 'conversation' ? T.layout.backToNormal : T.layout.chatFocus} aria-label={s.mode === 'conversation' ? T.layout.backToNormal : T.layout.chatFocus} onClick={() => C.visual.mode(s.mode === 'conversation' ? 'normal' : 'conversation')}><Icon name={s.mode === 'conversation' ? 'normal' : 'focusChat'} size={16} /></button>
      </div>
      <div className="conv__scroll" ref={box} onScroll={onScroll} onWheel={touched} onPointerDown={touched} onKeyDown={touched} onTouchMove={touched} tabIndex={0} role="log" aria-label="Konverzace s Vedoucím výzkumu" aria-live="polite" aria-relevant="additions">
        <div ref={inner}>
        {start > 0 && <div className="older"><button className="btn btn--sm btn--quiet" onClick={() => setVisible((v) => v + 40)}><Icon name="up" size={13} />Načíst starší zprávy ({start})</button></div>}
        {groups.map((g) => g.kind === 'group' ? (
          <div className="msg" key={g.key}>
            <div className="actgroup">
              <button className="actgroup__toggle" aria-expanded={!!open[g.key]} onClick={() => setOpen((o) => ({ ...o, [g.key]: !o[g.key] }))}><Icon name={open[g.key] ? 'down' : 'next'} size={12} />{T.conv.groupDone(g.items.length)} · <span className="muted">{g.items.map((m) => s.activities.find((a) => a.id === m.activityId)?.title).join(' · ')}</span></button>
              {open[g.key] && g.items.map((m) => <div key={m.id} style={{ marginTop: 6 }}><ActivityCard a={s.activities.find((a) => a.id === m.activityId)!} grouped /></div>)}
            </div>
          </div>
        ) : <MessageView key={g.m.id} m={g.m} isLastLead={g.m.id === lastLead?.id} />)}
        {s.busy && last?.kind !== 'lead' && !s.activities.some((a) => a.status === 'running') && <div className="msg"><div className="lead"><div className="lead__av"><Mark size={14} onDark /></div><div className="typing" aria-label="Vedoucí odpovídá"><i /><i /><i /></div></div></div>}
        <div style={{ height: 8 }} />
        </div>
      </div>
      {away && (
        <div className="conv__latestwrap">
          <button className="btn btn--sm conv__latest" onClick={toLatest}><Icon name="down" size={13} />{unread ? T.conv.newBelow(unread) : T.conv.latest}</button>
        </div>
      )}
      <Composer />
    </div>
  );
}

type G = { kind: 'one'; m: Message } | { kind: 'group'; key: string; items: Message[] };
function group(ms: Message[], acts: Activity[]): G[] {
  const out: G[] = [];
  let run: Message[] = [];
  const flush = () => {
    if (run.length >= 2) out.push({ kind: 'group', key: 'g-' + run[0].id, items: run });
    else run.forEach((m) => out.push({ kind: 'one', m }));
    run = [];
  };
  ms.forEach((m, i) => {
    const a = m.kind === 'activity' ? acts.find((x) => x.id === m.activityId) : null;
    const recent = i >= ms.length - 3;
    if (a && a.status === 'done' && !recent) run.push(m);
    else { flush(); out.push({ kind: 'one', m }); }
  });
  flush();
  return out;
}

function MessageView({ m, isLastLead }: { m: Message; isLastLead: boolean }) {
  const s = useApp((x) => x);
  if (m.kind === 'divider') return <div className="divider" role="separator">{m.text}</div>;
  if (m.kind === 'notice') return <div className="msg"><div className="notice"><Glyph tone={m.tone ?? 'inert'} size={11} />{m.text}<span className="msgmeta">· {m.at}</span></div></div>;
  if (m.kind === 'user') return (
    <div className="msg msg--user" data-msg={m.id}>
      {m.ref && <div className="bubble__ref"><Icon name="at" size={12} />{STAGES[m.ref.stage].label} · {m.ref.label}</div>}
      <div className="bubble">{m.text}</div>
      <div className="msgacts" role="group" aria-label="Akce zprávy">
        <button className="iconbtn" aria-label={T.conv.editQueued} title="Upravit a poslat znovu" onClick={() => update((d) => { d.composer.draft = m.text ?? ''; })}><Icon name="pencil" size={13} /></button>
        <button className="iconbtn" aria-label={T.conv.copy} title={T.conv.copy} onClick={() => navigator.clipboard?.writeText(m.text ?? '').catch(() => { /* refused in some frames */ })}><Icon name="copy" size={13} /></button>
        <span className="msgmeta">{m.at}</span>
      </div>
    </div>
  );
  if (m.kind === 'activity') { const a = s.activities.find((x) => x.id === m.activityId); return a ? <div className="msg" data-msg={m.id}><ActivityCard a={a} /></div> : null; }
  if (m.kind === 'decision') { const d = s.decisions.find((x) => x.id === m.decisionId); return d ? <div className="msg" data-msg={m.id}><DecisionCard id={d.id} /></div> : null; }
  if (m.kind === 'return') return <div className="msg" data-msg={m.id}><ReturnSummary m={m} /></div>;
  // lead
  const hist = m.historical && m.rev < s.revision;
  return (
    <div className="msg" data-msg={m.id}>
      <div className="lead">
        <div className="lead__av"><Mark size={14} onDark /></div>
        <div style={{ minWidth: 0 }}>
          <div className="lead__name"><b>{T.app.lead}</b><span>{m.at}</span>{hist && <span className="histnote" title="Odpověď popisuje stav, který se od té doby změnil"><Icon name="history" size={11} />{T.conv.historical(m.rev, s.revision)}</span>}{m.runRev && <span className="histnote">běh r{m.runRev}</span>}</div>
          <div className={'prose' + (hist ? ' is-hist' : '')}><Blocks blocks={m.blocks ?? []} shown={m.shown} />{m.streaming && <span className="caret" />}{m.stopped && <span className="histnote">zastaveno</span>}</div>
          {!m.streaming && m.sources && m.sources.length > 0 && <div className="srcs">Zdroje: {m.sources.map((id) => <button key={id} className="srcchip" title={src(id).title} onClick={() => C.visual.inspect({ type: 'source', id })}>{id} · {src(id).title.split(' (')[0]}</button>)}</div>}
          {!m.streaming && m.links && m.links.length > 0 && <div className="links">{m.links.map((l, i) => <button key={i} className="linkchip" onClick={() => C.visual.open(l.stage, l.focus)}><Icon name="open" size={12} />{l.label}</button>)}</div>}
          {!m.streaming && <div className={'msgacts' + (isLastLead ? ' is-last' : '')} role="group" aria-label="Akce zprávy">
            <button className="iconbtn" aria-label={T.conv.copy} title={T.conv.copy} onClick={() => navigator.clipboard?.writeText(plain(m.blocks ?? [])).catch(() => { /* refused in some frames */ })}><Icon name="copy" size={13} /></button>
            <button className="iconbtn" aria-label={T.conv.why} title={T.conv.why} onClick={() => C.visual.inspect({ type: 'context' })}><Icon name="why" size={13} /></button>
          </div>}
        </div>
      </div>
      {isLastLead && !m.streaming && m.follow && !s.busy && (
        <div className="follow" aria-label="Navázat">
          {m.follow.map((f) => <button key={f} className="follow__btn" onClick={() => send(f)}><Icon name="next" size={13} />{f}</button>)}
        </div>
      )}
    </div>
  );
}

const plain = (b: Block[]) => b.map((x) => x.x ?? (x.items ?? []).join('\n') ?? (x.rows ?? []).map((r) => r.join(': ')).join('\n')).join('\n\n');

function Blocks({ blocks, shown }: { blocks: Block[]; shown?: number }) {
  let budget = shown ?? Infinity;
  const take = (t: string) => { if (budget <= 0) return ''; const out = t.slice(0, budget); budget -= t.length; return out; };
  return <>{blocks.map((b, i) => {
    if (budget <= 0) return null;
    if (b.t === 'p') return <p key={i}>{take(b.x ?? '')}</p>;
    if (b.t === 'h') return <h4 key={i}>{take(b.x ?? '')}</h4>;
    if (b.t === 'ul') return <ul key={i}>{(b.items ?? []).map((x, j) => { const t = take(x); return t ? <li key={j}>{t}</li> : null; })}</ul>;
    return <dl key={i}>{(b.rows ?? []).map(([k, v], j) => { const t = take(v); return t ? <Fragment key={j}><dt>{k}</dt><dd>{t}</dd></Fragment> : null; })}</dl>;
  })}</>;
}

const TYPE_LABEL: Record<Activity['type'], string> = { lead: T.activity.lead, worker: T.activity.worker, research: T.activity.research, compute: T.activity.compute, decision: T.activity.decision, lookup: T.activity.lookup };
const TYPE_ICON: Record<Activity['type'], string> = { lead: 'compute', worker: 'worker', research: 'research', compute: 'compute', decision: 'decision', lookup: 'lookup' };

export function ActivityCard({ a, grouped }: { a: Activity; grouped?: boolean }) {
  const [open, setOpen] = useState(false);
  const tone = a.status === 'running' ? 'running' : a.status === 'waiting' ? 'world' : a.status === 'failed' ? 'fault' : a.status === 'stopped' ? 'cancelled' : a.status === 'refused' ? 'blocked' : a.steps.some((x) => x.tone === 'done-warn') ? 'done-warn' : 'done';
  const review = a.status === 'done' && a.link && /Zkontrolovat/.test(a.summary + a.link.label);
  return (
    <div className={'act act--' + a.type + (grouped ? ' act--grouped' : '')} data-aia={'activity.' + a.id}>
      <div className="act__row">
        <button className="act__toggle" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          <span className="act__type" title={TYPE_LABEL[a.type]}><Icon name={TYPE_ICON[a.type]} size={13} /></span>
          <span className="sr-only">{TYPE_LABEL[a.type]}: </span>
          <span className="act__title">{a.title}</span>
          <span className="act__sum">· {a.summary.replace(' · Zkontrolovat', '')}</span>
        </button>
        <span className="act__right">
          <Glyph tone={tone} size={12} title={a.status} />
          {a.link && <button className={'btn btn--sm' + (review ? '' : ' btn--quiet')} onClick={() => C.visual.open(a.link!.stage, a.link!.focus)}>{review ? T.activity.review : a.link.label === 'Zkontrolovat' ? T.activity.review : T.activity.open}</button>}
        </span>
      </div>
      {a.type === 'research' && <div className="act__env"><Icon name="lock" size={11} /><span className="grow">{a.details.find(([k]) => k === 'Účel')?.[1].split(' ')[0]} · v rámci schváleného oprávnění · {a.details.find(([k]) => k === 'Náklad' || k === 'Rezervace')?.[1] ?? 'rezervace ≤ 5 USD'} · třída C</span><button className="linkbtn" onClick={() => C.visual.inspect({ type: 'envelope' })}>Oprávnění</button></div>}
      {a.progress && a.status !== 'done' && <div className="progressline" role="progressbar" aria-valuemin={0} aria-valuemax={a.progress.total} aria-valuenow={a.progress.done} aria-label={a.title}><i style={{ width: (a.progress.done / a.progress.total) * 100 + '%' }} /></div>}
      {open && (
        <div className="act__body">
          <div className="cap" style={{ marginBottom: 6 }}>{TYPE_LABEL[a.type]}</div>
          {a.steps.length > 0 && <ul className="act__steps">{a.steps.map((st, i) => <li key={i}><Glyph tone={st.tone} size={10} /><span>{st.text}</span></li>)}</ul>}
          {a.details.length > 0 && <dl className="kvgrid">{a.details.map(([k, v], i) => <Fragment key={i}><dt>{k}</dt><dd>{v}</dd></Fragment>)}</dl>}
        </div>
      )}
    </div>
  );
}

function DecisionCard({ id }: { id: string }) {
  const d = useApp((s) => s.decisions.find((x) => x.id === id))!;
  const busy = useApp((s) => s.busy);
  const [pick, setPick] = useState(d.alternatives.find((a) => a.recommended)?.id ?? d.alternatives[0].id);
  const decided = d.status === 'decided';
  const unavailable = (aid: string) => aid === 'replace';
  return (
    <div className={'dec' + (decided ? ' is-decided' : '')} data-aia={'decision.' + d.id}>
      <div className="dec__head"><Glyph tone={decided ? 'done' : 'you'} size={11} />{decided ? T.decision.decided(d.alternatives.find((a) => a.id === d.chosen)?.label ?? '') : d.kind === 'authorise-run' || d.kind === 'budget' ? T.decision.authorise : T.decision.head}</div>
      <div className="dec__body">
        <p className="dec__title">{d.title}</p>
        <p className="dec__reason">{d.reason}</p>
        <div role="radiogroup" aria-label={d.title}>
          {d.alternatives.map((a) => (
            <button key={a.id} role="radio" aria-checked={(decided ? d.chosen : pick) === a.id} disabled={decided || unavailable(a.id)} className={'opt' + ((decided ? d.chosen : pick) === a.id ? ' is-chosen' : '')} onClick={() => setPick(a.id)}>
              <span className="opt__radio" />
              <span><span className="opt__label">{a.label}{a.recommended && <span className="chip chip--ai">{T.decision.recommended}</span>}{unavailable(a.id) && <span className="chip chip--line">navrženo · v AIA zatím není</span>}</span><span className="opt__detail">{a.detail}</span></span>
            </button>
          ))}
        </div>
        {d.impact.length > 0 && <ul className="dec__impact">{d.impact.map((x) => <li key={x}>{x}</li>)}</ul>}
        {!decided && <div className="dec__foot">{d.cost && <span className="cap">{T.decision.cost}: {d.cost}</span>}<span className="grow" /><button className="btn btn--primary btn--sm" disabled={busy && d.kind !== 'data' && d.kind !== 'budget'} onClick={() => void onDecision(d.id, pick)}>Rozhodnout</button></div>}
      </div>
    </div>
  );
}

function ReturnSummary({ m }: { m: Message }) {
  const r = m.returnSummary!;
  const lastSeen = useApp((s) => s.lastSeenMsg);
  const goBack = () => { const el = document.querySelector('[data-msg="' + lastSeen + '"]'); el?.scrollIntoView({ block: 'center' }); (el as HTMLElement | null)?.classList.add('just'); };
  return (
    <div className="ret" aria-label="Shrnutí po návratu">
      <h3>Od vaší poslední návštěvy</h3>
      <div className="ret__grid">
        <div><h4>Co se změnilo</h4><ul>{r.changed.map((x) => <li key={x}>{x}</li>)}</ul></div>
        <div><h4>Co doběhlo</h4><ul>{r.finished.map((x) => <li key={x}>{x}</li>)}</ul></div>
        <div style={{ gridColumn: '1 / -1' }}><h4>Co potřebuje pozornost</h4><ul>{r.attention.map((x) => <li key={x}>{x}</li>)}</ul></div>
      </div>
      <div className="ret__next"><Glyph tone="you" size={11} /><b>Doporučený další krok:</b> {r.next}</div>
      <div className="actionrow"><button className="btn btn--sm btn--primary" onClick={() => C.visual.open('report', 'P3')}>Otevřít větu 1.3</button>{lastSeen && <button className="btn btn--sm btn--quiet" onClick={goBack}><Icon name="history" size={13} />Na poslední přečtené místo</button>}</div>
    </div>
  );
}
