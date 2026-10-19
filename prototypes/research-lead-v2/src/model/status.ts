// Derived status. Nothing here is stored: every stage's status, the header's
// one-line state and the pending list are read from domain state each render.
import type { AppState, StageId, StageStatus, Tone, Proposal } from './types';
import { STAGE_ORDER, STAGES, STATUS_WORD } from './terms';
import { contentRev } from './doc';
import { isStale } from '../app/commands';

export function pendingProposals(s: AppState, stage?: StageId): Proposal[] {
  return s.proposals.filter((p) => p.status === 'pending' && (!stage || p.stage === stage));
}

export function stageStatus(s: AppState, stage: StageId): StageStatus {
  const reopened = s.reopened.includes(stage);
  const props = pendingProposals(s, stage);
  const stale = props.filter((p) => isStale(s, p));
  const decs = s.decisions.filter((d) => d.status === 'open' && d.stage === stage);
  const working = (s.working[stage] ?? []).length;
  const run = s.run;
  const runDone = run.status === 'completed';

  if (decs.length) return { kind: 'decision', note: decs[0].title };
  if (stale.length) return { kind: 'proposal', note: 'Návrh je zastaralý · sestavit znovu' };
  if (props.length) return { kind: 'proposal', note: props[0].title };
  if (working) return { kind: 'working', note: working + ' neuložených úprav' };

  switch (stage) {
    case 'fieldwork':
      if (run.status === 'running') return { kind: 'running', note: run.done + ' z ' + run.target + ' respondentů' };
      if (run.status === 'waiting_provider') return { kind: 'waiting', note: 'Poskytovatel omezil provoz; pokračuje sám' };
      if (run.status === 'awaiting_budget') return { kind: 'decision', note: 'Zastaveno na limitu rozpočtu' };
      if (runDone && reopened) return { kind: 'reopened', note: 'Běh z revize ' + run.revision + '; studie je na revizi ' + s.revision };
      if (runDone) return { kind: 'complete', note: run.id + ' · revize ' + run.revision };
      if (run.status === 'cancelled') return { kind: 'failed', note: 'Běh zrušen' };
      return { kind: 'ready', note: 'Připraveno ke spuštění' };
    case 'results':
    case 'sociomap':
      if (!runDone) return { kind: 'blocked', note: 'Čeká na dokončený běh' };
      if (reopened) return { kind: 'reopened', note: 'Výsledky platí pro revizi ' + run.revision };
      return { kind: 'frozen', note: run.id + ' · revize ' + run.revision };
    case 'analysis':
      if (!runDone) return { kind: 'blocked', note: 'Čeká na výsledky' };
      if (s.analysisState === 'running') return { kind: 'running', note: 'Moduly analýzy běží' };
      if (s.failures.analysisValidation) return { kind: 'failed', note: 'Modul Hypotézy neprošel kontrolou' };
      if (s.analysisState === 'none') return { kind: 'ready', note: 'Lze spustit' };
      if (reopened) return { kind: 'reopened', note: 'Analýza běhu ' + run.id };
      return { kind: 'complete', note: '7 z 8 modulů · Segmenty blokovány' };
    case 'report':
      if (!runDone || s.analysisState === 'none') return { kind: 'blocked', note: 'Čeká na analýzu' };
      if (s.reportState.reviewed) return { kind: 'complete', note: 'Interně schváleno' };
      return { kind: 'ready', note: 'Koncept · neschváleno' };
    case 'sample':
      if (reopened) return { kind: 'reopened', note: 'Znovu otevřeno' };
      return { kind: 'accepted', note: 'n 400 · 2 varování' };
    default:
      if (reopened) return { kind: 'reopened', note: 'Znovu otevřeno' };
      return { kind: 'accepted', note: 'Revize ' + contentRev(s, stage) };
  }
}

export const TONE: Record<StageStatus['kind'], Tone> = {
  accepted: 'done', working: 'working', proposal: 'you', decision: 'you', running: 'running', waiting: 'world',
  reopened: 'reopened', ready: 'ready', blocked: 'blocked', notstarted: 'inert', complete: 'done', failed: 'fault', frozen: 'done',
};

export function statusWord(st: StageStatus) { return STATUS_WORD[st.kind]; }

export function pendingCount(s: AppState) {
  return pendingProposals(s).length + s.decisions.filter((d) => d.status === 'open').length;
}

// The header's one line: where the study is, in words.
export function overallState(s: AppState): string {
  if (s.run.status === 'running') return 'Sběr dat běží · ' + s.run.done + ' z ' + s.run.target;
  if (s.run.status === 'waiting_provider') return 'Sběr dat čeká na poskytovatele';
  if (s.run.status === 'awaiting_budget') return 'Sběr dat zastaven na limitu rozpočtu';
  if (s.run.status === 'completed') {
    if (s.reopened.length) return 'Výsledky běhu z revize ' + s.run.revision + ' · ' + s.reopened.length + ' kroky znovu otevřeny';
    if (s.reportState.reviewed) return 'Zpráva interně schválena';
    if (s.analysisState === 'complete' || s.analysisState === 'blocked_module') return 'Interpretace a zpráva';
    return 'Výsledky připraveny';
  }
  return 'Návrh výzkumu · revize ' + s.revision;
}

// The first stage that needs the person, in order. Used by "Where are we?" and the return summary.
export function nextForYou(s: AppState): { stage: StageId; why: string } | null {
  for (const st of STAGE_ORDER) {
    const k = stageStatus(s, st);
    if (k.kind === 'proposal' || k.kind === 'decision' || k.kind === 'working' || k.kind === 'failed') return { stage: st, why: STAGES[st].label + ': ' + k.note };
  }
  return null;
}
