// Scoped application commands (§14). The UI's controls and the Research Lead's
// scripts call the SAME functions; nothing else changes authoritative state.
// Each command checks its own rule and logs what was asked, by whom, and the
// outcome, so the inspector can show that a click and a typed request took the
// same path. Visual operations (open, focus, select, filter) are separate and
// never change research content.
import { getState, update, nextId } from './store';
import type { AppState, AppliedOp, CommandLog, InspectorTarget, Mode, Op, Proposal, StageId, Decision } from '../model/types';
import { contentRev, itemsChangedByWorking } from '../model/doc';
import { STAGE_ORDER, STAGES } from '../model/terms';
import { ENVELOPE } from '../model/fixture';

export type By = CommandLog['by'];
export type Result = { ok: true } | { ok: false; reason: string };

export function clockLabel(s: AppState) {
  const m = 9 * 60 + 40 + Math.floor(s.clock / 60);
  return Math.floor(m / 60) + ':' + String(m % 60).padStart(2, '0');
}

function log(d: AppState, cmd: string, by: By, r: Result, stage?: StageId) {
  d.log.push({ id: nextId('cmd'), cmd, by, ok: r.ok, reason: r.ok ? undefined : r.reason, at: clockLabel(d), stage });
  if (d.log.length > 200) d.log.shift();
}

// ------------------------------------------------------------ visual operations
export const visual = {
  open(stage: StageId, focus?: string) {
    update((d) => { d.stage = stage; d.focusPath = focus ?? null; if (focus) d.selection[stage] = focus; d.inspector = d.inspector.filter((t) => t.type !== 'history' && t.type !== 'details' && t.type !== 'contract'); });
    if (focus) setTimeout(() => update((d) => { if (d.focusPath === focus) d.focusPath = null; }), 2400);
  },
  mode(m: Mode) { update((d) => { d.mode = m; }); },
  inspect(t: InspectorTarget) { update((d) => { const last = d.inspector[d.inspector.length - 1]; if (JSON.stringify(last) !== JSON.stringify(t)) d.inspector.push(t); }); },
  back() { update((d) => { d.inspector.pop(); }); },
  closeInspector() { update((d) => { d.inspector = []; }); },
  filter<K extends keyof AppState['viewFilters']>(k: K, v: AppState['viewFilters'][K], by: By = 'ui') {
    update((d) => { d.viewFilters[k] = v; log(d, 'view.filter ' + k + '=' + String(v), by, { ok: true }, 'sociomap'); });
  },
  select(stage: StageId, id: string) { update((d) => { d.selection[stage] = id; }); },
};

// ------------------------------------------------------------ working copy
export function edit(stage: StageId, op: Op, by: By = 'ui', note?: string): Result {
  const s = getState();
  if (STAGES[stage] && ['fieldwork', 'results', 'sociomap', 'analysis'].includes(stage)) {
    const r: Result = { ok: false, reason: 'Zmrazený artefakt běhu nelze upravit.' };
    update((d) => log(d, 'working.edit', by, r, stage));
    return r;
  }
  update((d) => {
    const list = (d.working[stage] ??= []);
    list.push({ id: nextId('op'), actor: by === 'ui' ? 'you' : 'lead', at: clockLabel(d), op, note } as AppliedOp);
    d.workingSince[stage] ??= contentRev(s, stage);
    log(d, 'working.edit ' + describeOp(op), by, { ok: true }, stage);
  });
  return { ok: true };
}

export function acceptWorking(stage: StageId, by: By = 'ui'): Result {
  if (by !== 'ui') {
    const r: Result = { ok: false, reason: 'Přijetí pracovní verze jako revize je rozhodnutí člověka.' };
    update((d) => log(d, 'working.accept', by, r, stage));
    return r;
  }
  update((d) => {
    const ops = d.working[stage] ?? [];
    if (!ops.length) return;
    const tag = advance(d, stage);
    (d.accepted[stage] ??= []).push(...ops.map((o) => ({ ...o, note: tag + ' · ' + (o.note ?? 'ruční úprava') })));
    d.working[stage] = [];
    delete d.workingSince[stage];
    d.leadSeen[stage] = 0;
    reopenDownstream(d, stage);
    log(d, 'working.accept → ' + (stage === 'report' ? 'koncept ' + d.reportState.draft : 'revize ' + d.revision), by, { ok: true }, stage);
  });
  return { ok: true };
}

export function discardWorking(stage: StageId, by: By = 'ui'): Result {
  update((d) => { d.working[stage] = []; delete d.workingSince[stage]; d.leadSeen[stage] = 0; log(d, 'working.discard', by, { ok: true }, stage); });
  return { ok: true };
}

// ------------------------------------------------------------ proposals
// Design stages advance the Study's Design Revision. The report advances its own
// draft number; run-level proposals (analysis coding) advance neither.
export const DESIGN_STAGES: StageId[] = ['brief', 'design', 'questionnaire', 'audience', 'dimensions'];
export function currentBase(s: AppState, stage: StageId) { return stage === 'report' ? s.reportState.draft : DESIGN_STAGES.includes(stage) ? contentRev(s, stage) : s.run.revision; }
export function isStale(s: AppState, p: Proposal) { return p.status === 'pending' && currentBase(s, p.stage) > p.baseRev; }

function advance(d: AppState, stage: StageId): string {
  if (stage === 'report') { d.reportState.draft += 1; d.reportState.reviewed = false; return 'k' + d.reportState.draft; }
  if (DESIGN_STAGES.includes(stage)) { d.revision += 1; return 'r' + d.revision; }
  return 'b' + d.run.revision;
}

export function createProposal(p: Omit<Proposal, 'id' | 'status' | 'createdAt'>, by: By = 'worker'): string {
  const id = nextId('pr');
  update((d) => {
    d.proposals.forEach((x) => { if (x.stage === p.stage && x.status === 'pending' && x.kind === p.kind) x.status = 'superseded'; });
    d.proposals.push({ ...p, id, status: 'pending', createdAt: clockLabel(d) });
    log(d, 'proposal.create (' + p.changes.length + ' změn)', by, { ok: true }, p.stage);
  });
  return id;
}

export function acceptProposal(id: string, by: By = 'ui'): Result {
  const s = getState();
  const p = s.proposals.find((x) => x.id === id);
  let r: Result;
  if (!p || p.status !== 'pending') r = { ok: false, reason: 'Návrh už nečeká na rozhodnutí.' };
  else if (by !== 'ui') r = { ok: false, reason: 'Návrh přijímá člověk (APPROVE_GATE). Vedoucí ani specialista ho přijmout nemohou.' };
  else if (isStale(s, p)) r = { ok: false, reason: 'Návrh vychází z ' + (p.stage === 'report' ? 'konceptu ' : 'revize ') + p.baseRev + ', obsah je nyní z ' + (p.stage === 'report' ? 'konceptu ' : 'revize ') + currentBase(s, p.stage) + '. Sestavte ho znovu.' };
  else {
    const touched = itemsChangedByWorking(s, p.stage);
    const clash = p.changes.filter((c) => c.op && touched.has(opItemId(c.op)));
    r = clash.length ? { ok: false, reason: 'Vaše pracovní úpravy mění ' + clash.map((c) => c.label).join(', ') + ' stejně jako návrh. Nejprve je přijměte nebo zahoďte.' } : { ok: true };
  }
  update((d) => {
    log(d, 'proposal.accept', by, r, p?.stage);
    if (!r.ok || !p) return;
    const dp = d.proposals.find((x) => x.id === id)!;
    const tag = advance(d, dp.stage);
    const ops = dp.changes.filter((c) => c.op).map((c) => ({ id: nextId('op'), actor: 'worker' as const, at: clockLabel(d), op: c.op!, note: tag + ' · ' + dp.title }));
    if (dp.stage === 'analysis') d.codingAccepted = true;
    (d.accepted[dp.stage] ??= []).push(...ops);
    dp.status = 'accepted';
    if (dp.kind === 'annotation') (d.evidenceAttached['accepted:' + dp.stage] ??= []).push(dp.id);
    reopenDownstream(d, dp.stage);
  });
  return r;
}

export function rejectProposal(id: string, by: By = 'ui'): Result {
  update((d) => { const p = d.proposals.find((x) => x.id === id); if (p) p.status = 'rejected'; log(d, 'proposal.reject', by, { ok: true }, p?.stage); });
  return { ok: true };
}

// ------------------------------------------------------------ decisions
export function openDecision(dec: Omit<Decision, 'id' | 'status'>): string {
  const id = nextId('dec');
  update((d) => { d.decisions.push({ ...dec, id, status: 'open' }); });
  return id;
}
export function choose(decId: string, alt: string, by: By = 'ui'): Result {
  const r: Result = by === 'ui' ? { ok: true } : { ok: false, reason: 'Toto rozhodnutí patří člověku.' };
  update((d) => { const x = d.decisions.find((y) => y.id === decId); if (r.ok && x) { x.status = 'decided'; x.chosen = alt; } log(d, 'decision.choose ' + alt, by, r, x?.stage); });
  return r;
}

// ------------------------------------------------------------ Deep Research (§10)
export interface ResearchRequest { purpose: 'DESIGN_RESEARCH' | 'INTERPRETATION_RESEARCH'; targetRef: string; target: string; inputClass: 'A' | 'C' | 'R'; route: 'wikipedia' | 'brave' | 'common_crawl'; estimate: number }
export function validateResearch(s: AppState, q: ResearchRequest): Result {
  // AIA decides from the study, the envelope and the input data; never from model arguments.
  if (q.purpose === 'DESIGN_RESEARCH' && s.run.status === 'completed' && q.targetRef.startsWith('design')) return { ok: false, reason: 'Metodika je zmrazená během; výzkum pro návrh už jen navrhne novou revizi.' };
  if (q.purpose === 'INTERPRETATION_RESEARCH' && s.run.status !== 'completed') return { ok: false, reason: 'Interpretační výzkum potřebuje dokončený běh studie.' };
  if (q.inputClass === 'R') return { ok: false, reason: 'Data respondentů nesmí do vyhledávání.' };
  if (q.inputClass === 'A') return { ok: false, reason: 'Dotaz je odvozen z důvěrného podkladu (třída A) a dědí jeho třídu; do veřejného vyhledávání nesmí ani parafrází.' };
  if (q.route === 'common_crawl') return { ok: false, reason: 'Trasa Common Crawl není organizací schválená.' };
  const left = s.budget.studyLimit - s.budget.studySpent - s.budget.studyReserved;
  if (q.estimate > ENVELOPE.perRun) return { ok: false, reason: 'Odhad ' + q.estimate.toFixed(2) + ' USD je nad limitem běhu ' + ENVELOPE.perRun + ' USD; potřeba rozšířit oprávnění.' };
  if (q.estimate > left) return { ok: false, reason: 'Zbývá ' + left.toFixed(2) + ' USD rozpočtu studie; odhad je ' + q.estimate.toFixed(2) + ' USD.' };
  return { ok: true };
}
export function requestResearch(q: ResearchRequest, by: By = 'lead'): Result {
  const r = validateResearch(getState(), q);
  update((d) => { log(d, 'research.request ' + q.purpose + ' → ' + q.targetRef, by, r); if (r.ok) d.budget.studyReserved += q.estimate; });
  return r;
}

// ------------------------------------------------------------ runs and budget
export function startRun(by: By = 'ui'): Result {
  const s = getState();
  let r: Result = { ok: true };
  if (by !== 'ui') r = { ok: false, reason: 'Spuštění běhu potvrzuje člověk.' };
  else if (Object.values(s.working).some((w) => w && w.length)) r = { ok: false, reason: 'Nejprve přijměte nebo zahoďte pracovní úpravy; běh zmrazí přijatou revizi.' };
  else if (s.proposals.some((p) => p.status === 'pending' && p.kind === 'design')) r = { ok: false, reason: 'Čeká návrh změny návrhu výzkumu.' };
  update((d) => {
    log(d, 'run.start revize ' + d.revision, by, r, 'fieldwork');
    if (!r.ok) return;
    d.run = { ...d.run, id: 'RUN-' + d.revision + 'A', revision: d.revision, status: 'running', done: 0, inFlight: 0, spent: 0, reserved: 0.92, elapsed: 0, waits: 0, constantResponders: 0 };
    d.reopened = d.reopened.filter((x) => x !== 'fieldwork');
  });
  return r;
}
export function cancelRun(by: By = 'ui'): Result {
  update((d) => { log(d, 'run.cancel', by, { ok: true }, 'fieldwork'); if (d.run.status !== 'completed') d.run.status = 'cancelled'; d.run.inFlight = 0; d.run.reserved = 0; });
  return { ok: true };
}
export function liftBudget(by: By = 'ui', amount = 10): Result {
  const r: Result = by === 'ui' ? { ok: true } : { ok: false, reason: 'Navýšení rozpočtu je rozhodnutí člověka.' };
  update((d) => { log(d, 'budget.lift +' + amount + ' USD', by, r, 'fieldwork'); if (r.ok) { d.budget.studyLimit += amount; d.failures.budgetLimit = false; if (d.run.status === 'awaiting_budget') d.run.status = 'running'; } });
  return r;
}
export function approveReport(by: By = 'ui'): Result {
  const r: Result = by === 'ui' ? { ok: true } : { ok: false, reason: 'Zprávu schvaluje člověk; AI neschvaluje vlastní text.' };
  update((d) => { log(d, 'report.approve', by, r, 'report'); if (r.ok) d.reportState.reviewed = true; });
  return r;
}

// ------------------------------------------------------------ revision impact
const DOWNSTREAM_OF: Partial<Record<StageId, StageId[]>> = {
  brief: ['design'],
  design: ['questionnaire', 'fieldwork'],
  questionnaire: ['fieldwork', 'results', 'sociomap', 'analysis', 'report'],
  audience: ['sample', 'fieldwork'],
  dimensions: ['fieldwork'],
  sample: ['fieldwork'],
};
function reopenDownstream(d: AppState, stage: StageId) {
  if (d.run.status !== 'completed') return;
  for (const x of DOWNSTREAM_OF[stage] ?? []) if (!d.reopened.includes(x)) d.reopened.push(x);
  d.reopened.sort((a, b) => STAGE_ORDER.indexOf(a) - STAGE_ORDER.indexOf(b));
}
export function downstreamOf(stage: StageId) { return DOWNSTREAM_OF[stage] ?? []; }

export function opItemId(op: Op): string {
  if (op.op === 'add') return op.item.id;
  if (op.op === 'set') return op.item ?? op.sec;
  return op.item;
}

export function describeOp(op: Op): string {
  if (op.op === 'set') return 'set ' + (op.item ? op.item + '.' : '') + op.field;
  if (op.op === 'add') return 'add ' + op.item.id;
  if (op.op === 'remove') return 'remove ' + op.item;
  return 'move ' + op.item + (op.dir < 0 ? ' ↑' : ' ↓');
}
