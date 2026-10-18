// The workbench: header, navigator, the conversation / artifact split, demo controls.
import { useEffect } from 'react';
import { useApp, update, savePrefs, getState } from './store';
import { Split } from '../components/Split';
import { Conversation } from '../components/Conversation';
import { ArtifactPane } from '../components/ArtifactPane';
import { StudyHeader, StageNav, Rail, EntryView, DemoPanel } from '../components/Shell';
import { DocsView } from '../components/DocsView';
import { leadNotices, runScript } from './scenarios';
import { STAGE_ORDER } from '../model/terms';

export function App() {
  const view = useApp((s) => s.view);
  const mode = useApp((s) => s.mode);
  const split = useApp((s) => s.split);
  const workSig = useApp((s) => STAGE_ORDER.map((st) => (s.working[st] ?? []).length).join(','));
  const busy = useApp((s) => s.busy);

  // The Lead notices a person's edits once they pause (§13), never mid-task.
  useEffect(() => {
    if (busy) return;
    const t = setTimeout(() => {
      const s = getState();
      const st = STAGE_ORDER.find((x) => (s.working[x] ?? []).length > (s.leadSeen[x] ?? 0));
      if (st && !s.busy) void runScript(() => leadNotices(st));
    }, 1600);
    return () => clearTimeout(t);
  }, [workSig, busy]);

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (!(e.altKey && e.shiftKey)) return;
      if (e.key === 'A' || e.code === 'KeyA') { e.preventDefault(); update((d) => { d.mode = d.mode === 'artifact' ? 'normal' : 'artifact'; }); }
      if (e.key === 'C' || e.code === 'KeyC') { e.preventDefault(); update((d) => { d.mode = d.mode === 'conversation' ? 'normal' : 'conversation'; }); }
      if (e.key === 'N' || e.code === 'KeyN') { e.preventDefault(); update((d) => { d.mode = 'normal'; }); }
    };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, []);

  if (view === 'entry') return <div className="app app--entry"><EntryView /><DemoPanel /></div>;
  if (view === 'docs') return <div className="app app--entry"><DocsView /><DemoPanel /></div>;
  return (
    <div className="app">
      <div className="narrow" role="note"><b>Pracovní plocha je navržena pro desktop.</b><span>Otevřete ji na obrazovce široké alespoň 1100 px. Na užší obrazovce je k dispozici přehled studií a dokumentace prototypu.</span><span><button className="btn btn--sm" onClick={() => update((d) => { d.view = 'entry'; })}>Přehled studií</button> <button className="btn btn--sm btn--quiet" onClick={() => update((d) => { d.view = 'docs'; })}>Dokumentace</button></span></div>
      <a href="#composer" className="skip">Přeskočit na zprávu</a>
      <StudyHeader />
      <StageNav />
      <main className="workspace">
        <Split split={split} mode={mode}
          onSplit={(v) => update((d) => { d.split = v; })}
          onCommit={(v) => { update((d) => { d.split = v; }); savePrefs({ split: v }); }}
          left={<Conversation />} right={<ArtifactPane />} rail={<Rail />} />
      </main>
      <DemoPanel />
    </div>
  );
}
