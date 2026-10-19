// Shared artifact building blocks: sections, editable items with their inline
// proposal changes, source chips. One grammar for every editable artifact.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useApp, update } from '../app/store';
import * as C from '../app/commands';
import { Icon } from './Icons';
import { Glyph } from './Glyph';
import type { Change, Proposal, StageId } from '../model/types';
import { src } from '../model/fixture';
import { pendingProposals } from '../model/status';
import { STAGES } from '../model/terms';

export function Sec({ n, title, aside, children, id }: { n?: string; title: string; aside?: ReactNode; children: ReactNode; id?: string }) {
  return (
    <section className="sec" data-aia={id} aria-label={title}>
      <div className="sec__h">{n && <span className="sec__n">{n}</span>}<h3 className="sec__t">{title}</h3>{aside && <span className="sec__d">{aside}</span>}</div>
      {children}
    </section>
  );
}

export function SourceChips({ ids }: { ids: string[] }) {
  if (!ids.length) return null;
  return <>{ids.map((id) => <button key={id} className="srcchip" title={src(id)?.title} onClick={() => C.visual.inspect({ type: 'source', id })}>{id}</button>)}</>;
}

export function fmt(n: number | null | undefined, d = 1) { return n == null ? '—' : n.toFixed(d).replace('.', ','); }

// The changes a pending proposal makes to one element.
export function changesFor(props: Proposal[], itemId: string): { p: Proposal; c: Change }[] {
  return props.flatMap((p) => p.changes.filter((c) => c.why && c.target.split('.').slice(1).join('.') === itemId).map((c) => ({ p, c })));
}

const KIND_WORD: Record<Change['kind'], string> = { modify: 'Změna', remove: 'Odebrat', add: 'Přidat', route: 'Větvení', merge: 'Sloučit', keep: 'Ponecháno' };

export function ChangeBlock({ c, p, stale }: { c: Change; p: Proposal; stale: boolean }) {
  if (c.kind === 'keep') return (
    <div className="annot" data-aia={'proposal.' + p.id + '.' + c.id}><div className="annot__h"><Icon name="check" size={13} />Ponecháno · {c.label}</div>{c.why}</div>
  );
  return (
    <div className="chg" data-aia={'proposal.' + p.id + '.' + c.id} style={stale ? { opacity: 0.6, borderLeftStyle: 'dashed' } : undefined}>
      <div className="chg__h"><Glyph tone="you" size={10} />{KIND_WORD[c.kind]} · {c.label}{stale && <span className="muted"> · zastaralé</span>}</div>
      {c.from && <div><span className="del">{c.from}</span></div>}
      {c.to && <div><span className="ins">{c.to}</span></div>}
      <div className="cap">{c.why}</div>
    </div>
  );
}

// An element of an editable artifact: its content, its working-copy marker, the
// pending changes proposed for it, and the edit / reference / move controls.
export function Item({ stage, sec, id, field, value, label, locked, children, multiline = true, movable = false, removable = false, props, stale }: {
  stage: StageId; sec: string; id: string; field?: string; value?: string; label: string; locked?: string;
  children?: ReactNode; multiline?: boolean; movable?: boolean; removable?: boolean; props: Proposal[]; stale: (p: Proposal) => boolean;
}) {
  const focus = useApp((s) => s.focusPath);
  const selected = useApp((s) => s.selection[stage] === id);
  const edited = useApp((s) => (s.working[stage] ?? []).some((o) => C.opItemId(o.op) === id));
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? '');
  const box = useRef<HTMLDivElement>(null);
  const ch = changesFor(props, id);

  useEffect(() => { if (focus === id) box.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }); }, [focus, id]);

  const save = () => {
    if (field && draft.trim() && draft !== value) C.edit(stage, { op: 'set', sec, item: id, field, value: draft.trim() }, 'ui', 'ruční úprava');
    setEditing(false);
  };
  const refer = () => update((d) => { d.composer.ref = { stage, path: id, label }; });

  return (
    <div ref={box} className={'item' + (focus === id ? ' just' : '') + (edited ? ' edited' : '') + (selected ? ' is-sel' : '')} data-aia={stage + '.' + sec + '.' + id}
      onClick={() => C.visual.select(stage, id)}>
      <div className="item__main">
        {editing ? (
          <div className="item__edit">
            {multiline
              ? <textarea className="field" rows={2} value={draft} autoFocus onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Escape') setEditing(false); if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) save(); }} aria-label={'Upravit ' + label} />
              : <input className="field" value={draft} autoFocus onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Escape') setEditing(false); if (e.key === 'Enter') save(); }} aria-label={'Upravit ' + label} />}
            <div className="item__editbar"><button className="btn btn--sm btn--primary" onClick={save}>Uložit do pracovní verze</button><button className="btn btn--sm btn--quiet" onClick={() => setEditing(false)}>Zrušit</button><span className="cap">Ctrl+Enter uloží · Esc zruší</span></div>
          </div>
        ) : children}
        {edited && !editing && <div className="cap"><Icon name="pencil" size={11} /> Vaše úprava v pracovní verzi · zatím ne v revizi</div>}
        {ch.map(({ p, c }) => <ChangeBlock key={p.id + c.id} p={p} c={c} stale={stale(p)} />)}
      </div>
      <div className="item__tools" role="group" aria-label={'Akce pro ' + label}>
        {locked ? <span className="lockline" title={locked}><Icon name="lock" size={11} />chráněno</span> : field && !editing && (
          <button className="iconbtn" title={'Upravit ' + label} aria-label={'Upravit ' + label} onClick={(e) => { e.stopPropagation(); setDraft(value ?? ''); setEditing(true); }}><Icon name="pencil" size={14} /></button>
        )}
        <button className="iconbtn" title="Odkázat v konverzaci (@)" aria-label={'Odkázat na ' + label + ' v konverzaci'} onClick={(e) => { e.stopPropagation(); refer(); }}><Icon name="at" size={14} /></button>
        {!locked && movable && <>
          <button className="iconbtn" aria-label={'Posunout ' + label + ' nahoru'} title="Posunout nahoru" onClick={(e) => { e.stopPropagation(); C.edit(stage, { op: 'move', sec, item: id, dir: -1 }); }}><Icon name="up" size={14} /></button>
          <button className="iconbtn" aria-label={'Posunout ' + label + ' dolů'} title="Posunout dolů" onClick={(e) => { e.stopPropagation(); C.edit(stage, { op: 'move', sec, item: id, dir: 1 }); }}><Icon name="down" size={14} /></button>
        </>}
        {!locked && removable && <button className="iconbtn" aria-label={'Odebrat ' + label} title="Odebrat (do pracovní verze)" onClick={(e) => { e.stopPropagation(); C.edit(stage, { op: 'remove', sec, item: id }); }}><Icon name="close" size={14} /></button>}
      </div>
    </div>
  );
}

export function useProposals(stage: StageId) {
  const props = useApp((s) => pendingProposals(s, stage));
  const s = useApp((x) => x);
  return { props, stale: (p: Proposal) => C.isStale(s, p) };
}

export function AddItem({ stage, sec, make, label }: { stage: StageId; sec: string; make: (text: string) => Record<string, unknown> & { id: string }; label: string }) {
  const [open, setOpen] = useState(false);
  const [t, setT] = useState('');
  if (!open) return <button className="btn btn--sm btn--quiet" onClick={() => setOpen(true)}><Icon name="plus" size={13} />{label}</button>;
  return (
    <div className="item__edit">
      <input className="field" autoFocus value={t} onChange={(e) => setT(e.target.value)} placeholder={label} aria-label={label}
        onKeyDown={(e) => { if (e.key === 'Enter' && t.trim()) { C.edit(stage, { op: 'add', sec, item: make(t.trim()) }); setT(''); setOpen(false); } if (e.key === 'Escape') setOpen(false); }} />
      <div className="item__editbar"><button className="btn btn--sm btn--primary" disabled={!t.trim()} onClick={() => { C.edit(stage, { op: 'add', sec, item: make(t.trim()) }); setT(''); setOpen(false); }}>Přidat do pracovní verze</button><button className="btn btn--sm btn--quiet" onClick={() => setOpen(false)}>Zrušit</button></div>
    </div>
  );
}

export function Unavailable({ children, kind = 'unavailable' }: { children: ReactNode; kind?: 'unavailable' | 'proposed' | 'simulated' }) {
  const word = kind === 'proposed' ? 'Navrženo · v AIA zatím není' : kind === 'simulated' ? 'Simulováno v prototypu' : 'V AIA zatím není';
  return <span className={'capnote capnote--' + kind}><span className="capnote__k">{word}</span><span>{children}</span></span>;
}

export function StageLink({ stage, focus, children }: { stage: StageId; focus?: string; children?: ReactNode }) {
  return <button className="linkbtn" onClick={() => C.visual.open(stage, focus)}>{children ?? STAGES[stage].label}</button>;
}
