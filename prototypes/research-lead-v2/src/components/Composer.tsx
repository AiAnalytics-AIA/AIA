// The composer: Enter sends, Shift+Enter adds a line, IME composition never
// sends, ArrowUp on an empty field recalls your last message, Escape stops the
// Lead. While the Lead works, new messages queue (send now / edit / remove).
// "@" references an element of the current artifact.
import { useMemo, useRef, useState } from 'react';
import { useApp, update } from '../app/store';
import { T, STAGES } from '../model/terms';
import { Icon } from './Icons';
import { send, stop } from '../app/scenarios';
import { workingDoc } from '../model/doc';
import { MAP } from '../model/fixture';

export function Composer() {
  const s = useApp((x) => x);
  const draft = s.composer.draft;
  const ref = s.composer.ref;
  const ta = useRef<HTMLTextAreaElement>(null);
  const [active, setActive] = useState(0);
  const [attach, setAttach] = useState(false);
  const setDraft = (v: string) => update((d) => { d.composer.draft = v; });

  const mention = draft.match(/(?:^|\s)@([^\s@]*)$/);
  const candidates = useMemo(() => {
    if (!mention) return [];
    const q = mention[1].toLowerCase();
    const list: { path: string; label: string; detail: string }[] = [];
    if (s.stage === 'sociomap') MAP.objects.forEach((o) => list.push({ path: o.id, label: o.label, detail: 'objekt mapy' }));
    else workingDoc(s, s.stage).sections.forEach((sec) => sec.items.forEach((it) => list.push({ path: it.id, label: it.id, detail: String(it.q ?? it.text ?? it.name ?? it.factor ?? '').slice(0, 70) })));
    return list.filter((c) => !q || c.label.toLowerCase().includes(q) || c.detail.toLowerCase().includes(q)).slice(0, 8);
  }, [mention?.[1], s.stage, s.accepted, s.working]); // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (i: number) => {
    const c = candidates[i]; if (!c) return;
    update((d) => { d.composer.ref = { stage: d.stage, path: c.path, label: c.label }; d.composer.draft = d.composer.draft.replace(/@([^\s@]*)$/, '').trimEnd(); });
    ta.current?.focus();
  };
  const submit = () => {
    const text = draft.trim();
    if (!text) return;
    send(text, ref);
    setDraft('');
  };

  return (
    <div className="composer-wrap">
      {s.composer.queue.length > 0 && (
        <div className="queue" aria-label={T.conv.queueTitle}>
          <div className="cap" style={{ padding: '2px 4px' }}>{T.conv.queueTitle}</div>
          {s.composer.queue.map((q) => (
            <div className="queue__item" key={q.id}>
              <Icon name="clock" size={13} /><span className="queue__text">{q.text}</span>
              <button className="btn btn--sm btn--quiet" onClick={() => { update((d) => { d.composer.queue = d.composer.queue.filter((x) => x.id !== q.id); d.composer.queue.unshift(q); }); stop(); }}>{T.conv.sendNow}</button>
              <button className="iconbtn" aria-label={T.conv.editQueued} title={T.conv.editQueued} onClick={() => update((d) => { d.composer.queue = d.composer.queue.filter((x) => x.id !== q.id); d.composer.draft = q.text; })}><Icon name="pencil" size={13} /></button>
              <button className="iconbtn" aria-label={T.conv.removeQueued} title={T.conv.removeQueued} onClick={() => update((d) => { d.composer.queue = d.composer.queue.filter((x) => x.id !== q.id); })}><Icon name="close" size={13} /></button>
            </div>
          ))}
        </div>
      )}
      {s.autopilot && <div className="autopilot" role="status"><Icon name="compute" size={13} />{T.conv.autopilot}<button className="btn btn--sm btn--quiet" style={{ marginLeft: 'auto' }} onClick={stop}>Zastavit</button></div>}
      {candidates.length > 0 && (
        <div className="mention" role="listbox" aria-label={'Prvky: ' + STAGES[s.stage].label}>
          {candidates.map((c, i) => <button key={c.path} role="option" aria-selected={i === active} className={'mention__item' + (i === active ? ' is-active' : '')} onMouseDown={(e) => { e.preventDefault(); pick(i); }}><b>{c.label}</b><span className="muted">{c.detail}</span></button>)}
        </div>
      )}
      {attach && (
        <div className="mention" role="menu">
          <button className="mention__item" role="menuitem" onClick={() => { setAttach(false); setDraft(draft + (draft ? ' ' : '') + '[příloha: Položky_banky.xlsx]'); }}><b>Soubor</b><span className="muted">uloží se jako podklad studie (simulováno)</span></button>
          <button className="mention__item" role="menuitem" onClick={() => { setAttach(false); setDraft(draft + (draft ? ' ' : '') + '[odkaz]'); }}><b>Odkaz</b><span className="muted">V AIA zatím není</span></button>
        </div>
      )}
      {ref && <div className="refchip"><Icon name="at" size={12} />{STAGES[ref.stage].label} · <b>{ref.label}</b><button className="iconbtn" style={{ width: 20, height: 20 }} aria-label="Zrušit odkaz" onClick={() => update((d) => { d.composer.ref = null; })}><Icon name="close" size={11} /></button></div>}
      <div className="composer">
        <label className="sr-only" htmlFor="composer">{T.conv.placeholder}</label>
        <textarea id="composer" ref={ta} rows={1} value={draft} placeholder={ref ? T.conv.placeholderRef : T.conv.placeholder}
          onChange={(e) => { setDraft(e.target.value); setActive(0); e.target.style.height = 'auto'; e.target.style.height = Math.min(180, e.target.scrollHeight) + 'px'; }}
          onKeyDown={(e) => {
            if (e.nativeEvent.isComposing) return;
            if (candidates.length) {
              if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => (a + 1) % candidates.length); return; }
              if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => (a - 1 + candidates.length) % candidates.length); return; }
              if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); pick(active); return; }
              if (e.key === 'Escape') { e.preventDefault(); setDraft(draft.replace(/@([^\s@]*)$/, '')); return; }
            }
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); return; }
            if (e.key === 'ArrowUp' && !draft) { const last = [...s.messages].reverse().find((m) => m.kind === 'user'); if (last?.text) { e.preventDefault(); setDraft(last.text); } return; }
            if (e.key === 'Escape' && s.busy) { e.preventDefault(); stop(); }
          }} />
        <div className="composer__bar">
          <button className="iconbtn" aria-label={T.conv.attach} title={T.conv.attach} aria-expanded={attach} onClick={() => setAttach((v) => !v)}><Icon name="attach" size={16} /></button>
          <button className="iconbtn" aria-label={T.conv.reference} title={T.conv.reference} onClick={() => { setDraft(draft + (draft && !draft.endsWith(' ') ? ' @' : '@')); ta.current?.focus(); }}><Icon name="at" size={16} /></button>
          <button className="btn btn--sm btn--quiet" disabled={s.busy} onClick={() => send('Pokračuj, dokud mě nebudeš potřebovat')} title="Vedoucí pracuje v rámci oprávnění a zastaví se u rozhodnutí, které patří vám">Pokračuj sám</button>
          <button className="btn btn--sm btn--quiet" disabled={s.busy} onClick={() => send('Kde jsme?')}>Kde jsme?</button>
          {s.busy && !draft.trim()
            ? <button className="composer__stop" aria-label={T.conv.stop + ' (Esc)'} title={T.conv.stop + ' (Esc)'} onClick={stop}><Icon name="stop" size={14} /></button>
            : <button className="composer__send" aria-label={s.busy ? 'Zařadit do fronty' : T.conv.send} title={s.busy ? 'Zařadit do fronty' : T.conv.send} disabled={!draft.trim()} onClick={submit}><Icon name="send" size={16} /></button>}
        </div>
      </div>
      <div className="composer__hint">{T.conv.hint}</div>
    </div>
  );
}
