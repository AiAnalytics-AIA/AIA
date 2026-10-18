// Scenario scripts and the Lead's request router. The scripts only call the
// application commands in commands.ts and the conversation writers in lead.ts;
// they never write research state directly. Anything that needs a person (accept,
// start, approve, lift a budget) is left as a control for the person.
import { getState, update, sleep, check, token, Stopped, cancelAll, replaceState, setFast, clearTimers, nextId } from './store';
import * as C from './commands';
import { say, p, ul, kv, userSays, notice, startActivity, actStep, actDone, actUpdate, decisionMsg, tick } from './lead';
import { questionnaireOptimisation, audienceEvidence, reportLessTechnical, reportOverstate, reportSociomapEmphasis, reportSwap, codingProposal } from '../model/proposals';
import { seedDesign, seedExecution, seedEvidence, seedReturn } from './seed';
import { STAGES, STAGE_ORDER } from '../model/terms';
import { pendingProposals, stageStatus, nextForYou } from '../model/status';
import { contentRev, workingDoc, findItem } from '../model/doc';
import { ENVELOPE, MAP, findPair, readiness } from '../model/fixture';
import type { StageId, Message } from '../model/types';

const w = async (t: number, ms: number) => { await sleep(ms); check(t); };
// Waiting on a person or a provider is real time even in fast mode.
const idleWait = async (t: number) => { await new Promise((r) => setTimeout(r, 150)); check(t); };

// ------------------------------------------------------------ runner + queue
export async function runScript(fn: (t: number) => Promise<void>) {
  const t = token();
  update((d) => { d.busy = true; });
  try {
    await fn(t);
  } catch (e) {
    if (!(e instanceof Stopped)) throw e;
    update((d) => {
      d.activities.forEach((a) => { if (a.status === 'running') a.status = 'stopped'; });
      const last = [...d.messages].reverse().find((m) => m.kind === 'lead');
      if (last?.streaming) { last.streaming = false; last.stopped = true; last.shown = undefined; }
    });
    notice('Zastaveno vámi. Nic nebylo přijato za vás; rozpracovaná práce se nezapsala.', 'cancelled');
  } finally {
    update((d) => { d.busy = false; d.autopilot = false; });
    const q = getState().composer.queue;
    if (q.length) {
      const [first] = q;
      update((d) => { d.composer.queue.shift(); });
      setTimeout(() => send(first.text), 300);
    }
  }
}

export function stop() { cancelAll(); }

export function send(text: string, ref?: Message['ref'] | null) {
  const s = getState();
  if (s.busy) { update((d) => { d.composer.queue.push({ id: nextId('q'), text }); }); return; }
  userSays(text, ref ?? undefined);
  update((d) => { d.composer.ref = null; });
  void runScript((t) => routeIntent(t, text, ref ?? null));
}

// ------------------------------------------------------------ the router
const has = (x: string, ...keys: string[]) => keys.some((k) => x.includes(k));

async function routeIntent(t: number, raw: string, ref: Message['ref'] | null) {
  const x = raw.toLowerCase();
  if (ref) return elementRequest(t, raw, ref);
  if (has(x, 'kde jsme', 'where are we', 'stav studie')) return whereAreWe(t);
  if (has(x, 'pokračuj', 'continue until', 'pokracuj')) return continueUntil(t);
  if (has(x, 'méně technick', 'less technical', 'srozumiteln')) return reportProposal(t, 'less');
  if (has(x, 'mladší', 'younger')) return youngerFirst(t);
  if (has(x, 'sociomap') && has(x, 'důraz', 'emphasis', 'víc prostoru', 'zdůrazn')) return reportProposal(t, 'emph');
  if (has(x, 'přehán', 'overstate', 'nadsazuje')) return overstate(t);
  if (has(x, 'odkud', 'where did', 'původ čísla')) return numberOrigin(t);
  if (has(x, 'shrnutí') && has(x, 'patří', 'zjištění') || has(x, 'executive summary')) return execSummary(t);
  if (has(x, 'otevřen', 'open answer', 'kóduj', 'q9')) return openAnswers(t);
  if (has(x, 'slab', 'weak')) return removeWeak(t);
  if (has(x, 'kontext', 'context') && has(x, 'map', 'dvojic', 'výklad', 'interpret')) return mapContext(t);
  if (has(x, 'proč') && has(x, 'blízko', 'near', 'vedle')) return pairWhy(t);
  if (has(x, 'předpoklad', 'cílov', 'audience', 'assumption')) return audienceResearch(t);
  if (has(x, 'dotazník', 'questionnaire', 'zkrať', 'optimal')) return questionnaireReview(t);
  if (has(x, 'výsledk', 'results')) return resultsTour(t);
  if (has(x, 'spusť', 'start') && has(x, 'sběr', 'běh', 'run', 'fieldwork')) return authoriseRun(t);
  if (has(x, 'klientsk', 'client report')) return clientReport(t);
  if (has(x, 'nahraď', 'replace')) return replaceRespondents(t);
  return fallback(t);
}

async function fallback(t: number) {
  await w(t, 400);
  const s = getState();
  await say([p('Tomu přesně nerozumím. Mohu číst a vysvětlovat artefakty, připravit návrh změny v artefaktu, vyžádat práci specialisty nebo hloubkový výzkum v rámci schváleného oprávnění. Rozhodnutí, přijetí návrhů a spuštění běhu patří vám.'), p('Pro změnu konkrétního místa ho označte přes @ v poli zprávy.')],
    { links: [{ stage: s.stage, label: 'Otevřít ' + STAGES[s.stage].label }] });
  followUps(['Kde jsme?', 'Pokračuj, dokud mě nebudeš potřebovat']);
}

function followUps(f: string[]) {
  update((d) => { const last = [...d.messages].reverse().find((m) => m.kind === 'lead'); if (last) last.follow = f; });
}

// ------------------------------------------------------------ A · open study
export async function openStudy(t: number) {
  await w(t, 300);
  const s = getState();
  await say([
    p('Studie je v návrhu výzkumu, revize ' + s.revision + '. Zadání, návrh a dotazník jsou přijaté; nic na vás nečeká.'),
    kv(['Hotovo', 'Zadání r12 · Návrh r13 · Dotazník r14'], ['Mezery', 'RQ2 bez kódování důvodů · RQ3 bez srovnání segmentů'], ['Rozpočet', (s.budget.studyLimit - s.budget.studySpent).toFixed(2).replace('.', ',') + ' USD zbývá z ' + s.budget.studyLimit + ' USD']),
    p('Doporučuji dva kroky: nechat specialistu posoudit dotazník (≈ 10 min je pro tuto skupinu dlouho) a ověřit předpoklady A1–A3 hloubkovým výzkumem. Obojí je v rámci vašeho oprávnění; přijetí výsledků bude na vás.'),
  ], { links: [{ stage: 'questionnaire', label: 'Dotazník' }, { stage: 'audience', focus: 'A1', label: 'Cílová skupina · předpoklady' }] });
  followUps(['Posuď dotazník a navrhni zkrácení', 'Ověř předpoklady o cílové skupině', 'Pokračuj, dokud mě nebudeš potřebovat']);
}

// ------------------------------------------------------------ B · questionnaire
export async function questionnaireReview(t: number) {
  const s0 = getState();
  const base = contentRev(s0, 'questionnaire');
  C.visual.open('questionnaire');
  const look = startActivity('lookup', 'Čtu dotazník a pokrytí', 'Revize ' + base + ' · 14 položek', [['Čtení', 'workspace/content · revize ' + base], ['Pokrytí', 'research_trace (deterministické)']]);
  await w(t, 500); actDone(look, 'Revize ' + base + ' · 14 položek · 5 otázek');
  const a = startActivity('worker', 'Posouzení dotazníku', 'Specialista pracuje…', [
    ['Specialista', 'aia.research.questionnaire_optimize · prompt v3 · harness 3'], ['Výchozí stav', 'Dotazník revize ' + base], ['Vstupy', 'dotazník, výzkumné otázky, chráněné položky (Sada 1, Q19)'],
    ['Běh', 'Bedrock EU (bedrock-eu-primary) přes ModelGateway'], ['Třída dat', 'B · studie'], ['Oprávnění', 'v rámci studie; bez dalšího potvrzení'],
  ], { stage: 'questionnaire', label: 'Dotazník' });
  for (const [txt, ms] of [['Kontext zmrazen: revize ' + base + ', 5 výzkumných otázek', 500], ['Návrh od modelu přijat (1 volání)', 900], ['Kontrola schématu: 1 oprava', 600], ['Kontrola chráněných položek a pokrytí: v pořádku', 500]] as const) {
    actStep(a, txt, 'done'); tick(15); await w(t, ms);
  }
  const pid = C.createProposal(questionnaireOptimisation(base), 'worker');
  actDone(a, '7 změn navrženo', { details: [...getState().activities.find((x) => x.id === a)!.details, ['Volání', '1 + 1 oprava'], ['Náklad', '0,21 USD'], ['Id', 'job-q7d · ' + pid]], link: { stage: 'questionnaire', label: 'Zkontrolovat' } });
  update((d) => { d.budget.studySpent += 0.21; });
  await say([
    p('Návrh je v Dotazníku u dotčených otázek: 7 změn, délka ≈ 10 → 8½ min.'),
    ul('Q9 (otevřený důvod změny) zůstává; po sloučení Q8 a Q10 se zobrazí po Q8 = Ano.', 'Q16 zůstává: znalost produktů je jiný konstrukt než znalost banky.', 'Sada 1 a Q19 jsou chráněné a beze změny.', 'Ztráta: Q13 už nezměří pořadí míst 4–6 (RQ3).'),
    p('Přijetí je na vás; můžete přijmout jen část změn úpravou v artefaktu.'),
  ], { links: [{ stage: 'questionnaire', focus: 'Q8', label: 'Dotazník · Q8 + Q10' }] });
  followUps(['Proč odebrat Q10?', 'Ověř předpoklady o cílové skupině']);
}

// ------------------------------------------------------------ C · audience research
export async function audienceResearch(t: number) {
  const s0 = getState();
  if (s0.research.some((r) => r.targetRef === 'audience.ass' && r.status === 'done')) {
    await say([p('Předpoklady A1–A3 už mají připojenou evidenci z výzkumu DR-41. Nový výzkum by stál peníze a nic nového by k témuž cíli nepřinesl.')], { links: [{ stage: 'audience', focus: 'A1', label: 'Cílová skupina · předpoklady' }] });
    return;
  }
  const rev = getState().revision;
  C.visual.open('audience', 'A1');
  // AIA validates each derived query; the Lead supplies none of the permissions.
  const queries: C.ResearchRequest[] = [
    { purpose: 'DESIGN_RESEARCH', targetRef: 'audience.ass.A1', target: 'A1', inputClass: 'C', route: 'brave', estimate: 0.22 },
    { purpose: 'DESIGN_RESEARCH', targetRef: 'audience.ass.A2', target: 'A2', inputClass: 'C', route: 'wikipedia', estimate: 0 },
    { purpose: 'DESIGN_RESEARCH', targetRef: 'audience.ass.A3', target: 'A3', inputClass: 'A', route: 'brave', estimate: 0.2 },
  ];
  const a = startActivity('research', 'Výzkum předpokladů A1–A3', 'Ověřuji oprávnění…', [
    ['Účel', 'DESIGN_RESEARCH (jen navrhuje)'], ['Cíl', 'Cílová skupina · předpoklady A1–A3 · revize ' + rev], ['Oprávnění', ENVELOPE.policy], ['Trasy', ENVELOPE.routes.join(' · ')], ['Limit běhu', ENVELOPE.perRun + ' USD'],
  ], { stage: 'audience', focus: 'A1', label: 'Cílová skupina' });
  update((d) => { d.research.push({ id: 'DR-41', purpose: 'DESIGN_RESEARCH', target: 'Předpoklady A1–A3 · revize ' + rev, targetRef: 'audience.ass', status: 'running', step: 0, sources: 0, admitted: 0, quarantined: 0, noEvidence: 0, spent: 0, findings: [] }); });
  for (const q of queries) {
    const r = C.requestResearch(q, 'lead');
    actStep(a, (r.ok ? 'Dotaz k ' + q.target + ' povolen (' + (q.route === 'brave' ? 'Brave, třída C' : 'Wikipedie, třída C') + ')' : 'Dotaz k ' + q.target + ' do vyhledávání nepovolen: ' + r.reason + ' Odpověď jen ze znalostí klienta.'), r.ok ? 'done' : 'done-warn');
    await w(t, 350);
  }
  const steps = ['plán', 'zkoumání', 'sloučení', 'ověření', 'syntéza', 'publikace'];
  for (let i = 0; i < steps.length; i++) {
    actUpdate(a, { summary: 'Krok ' + (i + 1) + ' ze 6 · ' + steps[i], progress: { done: i + 1, total: 6, unit: 'kroků' } });
    update((d) => { const r = d.research.find((x) => x.id === 'DR-41'); if (r) { r.step = i + 1; r.sources = Math.min(14, (i + 1) * 3); } });
    tick(30); await w(t, 450);
  }
  actStep(a, '14 zdrojů · 3 zjištění připuštěna · 2 v karanténě · A3: žádný veřejný zdroj o složení klientů', 'done-warn');
  update((d) => {
    const r = d.research.find((x) => x.id === 'DR-41')!; Object.assign(r, { status: 'done', admitted: 3, quarantined: 2, noEvidence: 1, spent: 0.42, findings: ['S1', 'S2', 'S3'] });
    d.budget.studySpent += 0.42; d.budget.studyReserved = Math.max(0, d.budget.studyReserved - 0.42);
    d.evidenceAttached['ass.A1'] = ['S1']; d.evidenceAttached['ass.A2'] = ['S2']; d.evidenceAttached['ass.A3'] = ['S3'];
    d.failures.missingEvidence = true;
  });
  const pid = C.createProposal(audienceEvidence(rev), 'worker');
  actDone(a, '3 zjištění připojena k předpokladům · Zkontrolovat', { progress: undefined, details: [...getState().activities.find((x) => x.id === a)!.details, ['Zdroje', '14 zachyceno · 3 připuštěna · 2 karanténa'], ['Náklad', '0,42 USD z rezervace 0,42 USD'], ['Id', 'DR-41 · ' + pid]] });
  await say([
    p('Zjištění jsou připojena přímo k předpokladům v Cílové skupině jako návrh. Předpoklady ani filtry se samy nezměnily.'),
    ul('A1: částečně podpořeno externím kontextem (S1).', 'A2: podpořeno externím kontextem (S2); studie to změří v Q13.', 'A3: nepodloženo. Jediný zdroj (S3, positioning klienta) říká, komu se značka chce líbit, ne kdo jsou klienti. Data o složení klientů chybí; předpoklad tím není vyvrácen.'),
    p('Jeden dotaz k A3 vycházel z důvěrného podkladu, proto do veřejného vyhledávání nešel.'),
  ], { links: [{ stage: 'audience', focus: 'A3', label: 'Cílová skupina · A3' }], sources: ['S1', 'S2', 'S3'] });
}

// ------------------------------------------------------------ D · manual edit noticed
export async function leadNotices(stage: StageId) {
  const s = getState();
  const ops = s.working[stage] ?? [];
  if (!ops.length || (s.leadSeen[stage] ?? 0) >= ops.length) return;
  update((d) => { d.leadSeen[stage] = ops.length; });
  const props = pendingProposals(s, stage);
  const items = [...new Set(ops.map((o) => C.opItemId(o.op)))];
  const clash = props.flatMap((pp) => pp.changes.filter((c) => c.op && items.includes(C.opItemId(c.op))).map((c) => c.label));
  await say([
    p('Vidím ' + ops.length + (ops.length === 1 ? ' vaši úpravu' : ' vaše úpravy') + ' v ' + STAGES[stage].label.toLowerCase() + ' (' + items.join(', ') + '). Je uložená jako pracovní verze nad revizí ' + (s.workingSince[stage] ?? contentRev(s, stage)) + '; do revize ji převedete přijetím.'),
    ...(clash.length ? [p('Čekající návrh mění ' + clash.join(', ') + ' také. Přijmete-li svou verzi, návrh zastará a sestavím ho znovu nad novou revizí.')] : []),
  ], { links: [{ stage, focus: items[0], label: STAGES[stage].label + ' · ' + items[0] }] });
}

export async function demoManualEdit(t: number) {
  C.visual.open('questionnaire', 'Q5');
  await w(t, 600);
  C.edit('questionnaire', { op: 'set', sec: 'b2', item: 'Q5', field: 'q', value: 'Jak dlouho máte účet u své hlavní banky?' }, 'ui', 'ruční úprava');
  await w(t, 900);
  await leadNotices('questionnaire');
}

// ------------------------------------------------------------ E · stale proposal
export async function staleRefusal(t: number) {
  const s = getState();
  const pp = pendingProposals(s, 'questionnaire')[0];
  if (!pp) return;
  const r = C.acceptProposal(pp.id, 'ui');
  if (r.ok) return;
  await w(t, 200);
  await say([p('Návrh nešlo použít: ' + r.reason), p('Sestavení znovu vytvoří nový návrh nad aktuální revizí. Nic tím nepřijímáte.')], { links: [{ stage: 'questionnaire', label: 'Dotazník' }] });
}

export async function rebuild(t: number, id: string) {
  const s = getState();
  const old = s.proposals.find((x) => x.id === id);
  if (!old) return;
  const base = C.currentBase(s, old.stage);
  const a = startActivity('worker', 'Návrh sestavován znovu', 'nad revizí ' + base, [['Specialista', old.author], ['Výchozí stav', 'revize ' + base + ' (dříve ' + old.baseRev + ')'], ['Důvod', 'původní návrh zastaral']], { stage: old.stage, label: STAGES[old.stage].label });
  await w(t, 900);
  const q5 = (getState().accepted.questionnaire ?? []).some((o) => o.op.op === 'set' && o.op.item === 'Q5' && o.actor === 'you');
  update((d) => { const o = d.proposals.find((x) => x.id === id); if (o) o.status = 'superseded'; });
  const { id: _i, status: _s, createdAt: _c, ...rest } = old;
  void _i; void _s; void _c;
  const draft = old.stage === 'questionnaire' && old.kind === 'design' && old.title.startsWith('Optimalizace') ? questionnaireOptimisation(base, { q5DoneByYou: q5 }) : { ...rest, baseRev: base, baseLabel: (old.stage === 'report' ? 'Koncept ' : 'Revize ') + base };
  const pid = C.createProposal({ ...draft, rebuiltFrom: id }, 'worker');
  actDone(a, (old.stage === 'questionnaire' && q5 ? '6 změn · Q5 už upravena vámi' : draft.changes.filter((c) => c.kind !== 'keep' && c.why).length + ' změn') + ' · Zkontrolovat', { link: { stage: old.stage, label: 'Zkontrolovat' }, details: [...getState().activities.find((x) => x.id === a)!.details, ['Id', pid], ['Náklad', '0,19 USD']] });
  update((d) => { d.budget.studySpent += 0.19; });
  await say([p('Nový návrh vychází z ' + (old.stage === 'report' ? 'konceptu ' : 'revize ') + base + '. ' + (old.stage === 'questionnaire' && q5 ? 'Vaši verzi Q5 nemění; ostatních 6 změn zůstalo. ' : '') + 'Starý návrh je označen jako nahrazený; přijetí je dál na vás.')], { links: [{ stage: old.stage, label: STAGES[old.stage].label }] });
}

// ------------------------------------------------------------ F · fieldwork
export async function authoriseRun(t: number) {
  await w(t, 300);
  const s = getState();
  const items = readiness({ questionnaireAccepted: true, audienceAccepted: true, spendConfirmed: true, proposalsPending: pendingProposals(s, 'questionnaire').length, workingStages: STAGE_ORDER.filter((x) => (s.working[x] ?? []).length) });
  const warn = items.filter((i) => i.state === 'warn');
  const you = items.filter((i) => i.state === 'you');
  C.visual.open('fieldwork');
  if (you.length) {
    await say([p('Běh zatím spustit nejde:'), ul(...you.map((i) => i.text + (i.note ? ' · ' + i.note : '')))], { links: [{ stage: you[0].where, label: STAGES[you[0].where].label }] });
    return;
  }
  await say([p('Připravenost: ' + (items.length - warn.length) + ' z ' + items.length + ' bez výhrad, ' + warn.length + ' varování (žádné neblokuje).'), ul(...warn.map((i) => i.text)), p('Strop běhu 18,40 USD je pod limitem potvrzení studie (25 USD), takže další potvrzení útraty nebude. Spuštění je ale vaše rozhodnutí.')]);
  const id = C.openDecision({ title: 'Spustit sběr dat nad revizí ' + s.revision, reason: 'Běh zmrazí revizi ' + s.revision + '. Pozdější úpravy do něj nevstoupí.', alternatives: [
    { id: 'start', label: 'Spustit s omezeními', detail: '400 fiktivních respondentů · strop 18,40 USD · Raiffeisenbank pravděpodobně potlačena', recommended: true },
    { id: 'n430', label: 'Nejdřív zvýšit n na 430', detail: 'Odhad podpory pro všech 8 bank; strop ≈ 19,80 USD' },
  ], impact: ['Výsledky, Sociomapa, Analýza a Zpráva se spočtou z tohoto běhu'], cost: 'strop 18,40 USD · zbývá ' + (s.budget.studyLimit - s.budget.studySpent).toFixed(2).replace('.', ',') + ' USD', kind: 'authorise-run', stage: 'fieldwork' });
  decisionMsg(id);
}

export async function onDecision(decId: string, alt: string) {
  const d = getState().decisions.find((x) => x.id === decId);
  if (!d) return;
  const r = C.choose(decId, alt, 'ui');
  if (!r.ok) return;
  if (d.kind === 'authorise-run' && alt === 'start') return runScript((t) => fieldwork(t));
  if (d.kind === 'authorise-run' && alt === 'n430') return runScript(async (t) => { await w(t, 200); await say([p('Zvýšení n na 430 je změna Vzorku. V prototypu není nastavitelné; v AIA ji provedete v kroku Dimenze → velikost vzorku a pak spustíte běh.')], { links: [{ stage: 'sample', label: 'Vzorek' }] }); });
  // Decisions raised during a run are recorded directly: the run's script keeps going.
  if (d.kind === 'data' && alt === 'keep') { update((x) => { x.run.decisionOnConstant = 'keep'; }); notice('Rozhodli jste: 6 respondentů ponecháno.', 'done'); return; }
  if (d.kind === 'data' && alt === 'flag') { update((x) => { x.run.decisionOnConstant = 'review'; }); notice('Rozhodli jste: 6 respondentů označeno ke kontrole ve Výsledcích. Data se nemění.', 'done'); return; }
  if (d.kind === 'budget' && alt === 'lift') { C.liftBudget('ui', 10); return; }
  if (d.kind === 'budget' && alt === 'stop') { C.cancelRun('ui'); notice('Běh ukončen s ' + getState().run.done + ' respondenty.', 'cancelled'); return; }
  if (d.kind === 'method' && alt === 'filter') return runScript(async (t) => { C.visual.filter('sociomapHideWeak', true, 'ui'); await w(t, 200); await say([p('Slabé vztahy jsou skryté jen v zobrazení. Filtr je vidět nad mapou; výpočet, pozice objektů i Stress-1 jsou beze změny.')], { links: [{ stage: 'sociomap', label: 'Sociomapa' }] }); });
  if (d.kind === 'method' && alt === 'method') return runScript(async (t) => {
    update((x) => { x.log.push({ id: nextId('cmd'), cmd: 'methodology.change (sociomap floor)', by: 'ui', ok: false, reason: 'Metodiku mění správce v Nastavení → Metodika jako novou verzi; platí až pro nový běh.', at: C.clockLabel(x), stage: 'sociomap' }); });
    await w(t, 200);
    await say([p('Tady to provést nejde. Změna toho, co mapa počítá (např. práh vztahu), je nová verze metodiky: připraví ji správce v Nastavení → Metodika, porovná se s platnou verzí a platí až pro nový běh. Tato mapa zůstane, jak byla spočtena.')]);
  });
  if (d.kind === 'research' && alt === 'go') return runScript((t) => mapContext(t, true));
}

let runLoop = 0;
export async function fieldwork(t: number) {
  const s0 = getState();
  if (s0.run.status === 'none' || s0.run.status === 'ready' || s0.run.status === 'cancelled') { const r = C.startRun('ui'); if (!r.ok) { notice(r.reason, 'blocked'); return; } }
  const loop = ++runLoop;
  const a = startActivity('compute', 'Sběr dat · ' + getState().run.id, 'Běží · 0 z 400', [
    ['Běh', getState().run.id + ' · revize ' + getState().run.revision + ' (zmrazena)'], ['Zdroj', 'ai_runtime · fiktivní roster (persona_source)'], ['Trasa', 'bedrock-eu-primary · ModelGateway'], ['Strop', '18,40 USD'], ['Původ dat', 'SYNTHETIC_AI_FICTIONAL'],
  ], { stage: 'fieldwork', label: 'Sběr dat' });
  C.visual.open('fieldwork');
  await say([p('Sběr běží nad revizí ' + getState().run.revision + '. Průběh uvidíte v jedné kartě; ozvu se jen u věcí, které potřebují vás.')]);
  let constantAsked = false;
  while (getState().run.done < 400) {
    if (loop !== runLoop) return;
    await w(t, 220);
    const s = getState();
    if (s.run.status === 'cancelled') { actDone(a, 'Zrušeno · ' + s.run.done + ' z 400', { status: 'stopped' }); return; }
    if (s.run.status === 'awaiting_budget') { actUpdate(a, { summary: 'Zastaveno na limitu rozpočtu · ' + s.run.done + ' z 400', status: 'waiting' }); await idleWait(t); continue; }
    if (s.failures.provider && s.run.done >= 160 && s.run.done < 170 && s.run.status !== 'waiting_provider') {
      update((d) => { d.run.status = 'waiting_provider'; d.run.waits += 1; });
      actStep(a, 'Poskytovatel nedostupný (ai_runtime_unavailable). Krok zaparkován; nic se neplatí dvakrát.', 'fault');
      actUpdate(a, { summary: 'Zaparkováno · poskytovatel nedostupný', status: 'waiting' });
      await say([p('Poskytovatel modelu přestal odpovídat; krok sběru je zaparkovaný. Rozpracované bloky se nezaplatí dvakrát. Zkusit znovu můžete ve Sběru dat, až bude poskytovatel dostupný.')], { links: [{ stage: 'fieldwork', label: 'Sběr dat' }] });
      continue;
    }
    if (s.run.status === 'waiting_provider') { await idleWait(t); continue; }
    if (s.run.done === 120 && s.run.waits === 0) {
      update((d) => { d.run.status = 'waiting_provider'; d.run.waits = 1; });
      actStep(a, 'Poskytovatel omezil provoz · čekám 40 s (automaticky)', 'world');
      actUpdate(a, { summary: 'Čeká na poskytovatele · 120 z 400' });
      await w(t, 1400);
      update((d) => { d.run.status = 'running'; });
      actStep(a, 'Pokračuje', 'done');
      continue;
    }
    if (s.failures.budgetLimit && s.run.done >= 300 && s.run.status === 'running') {
      update((d) => { d.run.status = 'awaiting_budget'; });
      const id = C.openDecision({ title: 'Běh se zastavil na limitu rozpočtu studie', reason: 'Další blok by překročil limit studie. Krok čeká (AWAITING_BUDGET); nic se neztratilo.', alternatives: [
        { id: 'lift', label: 'Navýšit limit o 10 USD', detail: 'Běh pokračuje od 300', recommended: true },
        { id: 'stop', label: 'Ukončit s 300 respondenty', detail: 'Výsledky z neúplného vzorku; kvóty nesplněny' },
      ], impact: ['Navýšení zapíše schválení do knihy schválení'], cost: 'zbývá ≈ 4,60 USD do stropu běhu', kind: 'budget', stage: 'fieldwork' });
      decisionMsg(id);
      continue;
    }
    update((d) => { d.run.done = Math.min(400, d.run.done + 20); d.run.inFlight = d.run.done < 400 ? 20 : 0; const before = d.run.spent; d.run.spent = +(d.run.done * 0.04465).toFixed(2); d.budget.studySpent += d.run.spent - before; d.run.elapsed += 240; d.clock += 60; });
    const done = getState().run.done;
    actUpdate(a, { summary: 'Běží · ' + done + ' z 400 · ' + getState().run.spent.toFixed(2).replace('.', ',') + ' USD', progress: { done, total: 400, unit: 'respondentů' }, status: 'running' });
    if (done >= 260 && !constantAsked) {
      constantAsked = true;
      update((d) => { d.run.constantResponders = 6; });
      actStep(a, '6 respondentů hodnotilo všech 8 bank stejně', 'done-warn');
      const id = C.openDecision({ title: '6 respondentů dalo všem bankám stejné hodnocení', reason: 'Stejné hodnocení může být lhostejnost, nebo skutečný názor. Samo o sobě není důvod respondenty vyřadit. Ve Sociomapě se takoví lidé nezmapují (nemají relativní preference), ale do průměrů se počítají.', alternatives: [
        { id: 'keep', label: 'Ponechat', detail: 'Výchozí chování AIA', recommended: true },
        { id: 'flag', label: 'Označit ke kontrole ve Výsledcích', detail: 'Data se nemění' },
        { id: 'replace', label: 'Nahradit jinými respondenty', detail: 'V AIA zatím není · navržená schopnost; význam náhrady není metodicky určen' },
      ], impact: ['Běh pokračuje bez ohledu na volbu'], kind: 'data', stage: 'fieldwork' });
      decisionMsg(id);
    }
  }
  update((d) => { d.budget.studySpent += 17.86 - d.run.spent; d.run.status = 'completed'; d.run.inFlight = 0; d.run.spent = 17.86; d.run.reserved = 0; });
  actDone(a, '400 z 400 · ' + getState().run.waits + '× čekání · 17,86 USD', { progress: undefined });
  const c = startActivity('compute', 'Agregace a Sociomapa', 'Počítám…', [['Kroky', 'aggregate · sociomap (aia-sociomap-3)'], ['Model', 'žádný: deterministický výpočet']], { stage: 'results', label: 'Výsledky' });
  await w(t, 700);
  actDone(c, 'Hotovo · Stress-1 0,083 · Raiffeisenbank potlačena');
  const an = startActivity('worker', 'Analýza · 8 modulů', 'Běží…', [['Specialista', 'aia.analysis.module'], ['Brána', 'AdmittedClaim']], { stage: 'analysis', label: 'Analýza' });
  update((d) => { d.analysisState = 'running'; });
  for (let i = 1; i <= 8; i++) { actUpdate(an, { summary: i + ' z 8 modulů', progress: { done: i, total: 8, unit: 'modulů' } }); await w(t, 260); }
  update((d) => { d.analysisState = 'blocked_module'; d.budget.studySpent += 1.94; if (d.failures.analysisValidation) d.analysisState = 'blocked_module'; });
  actDone(an, getState().failures.analysisValidation ? '6 z 8 · Hypotézy neprošly kontrolou · Segmenty blokovány' : '7 z 8 · Segmenty blokovány', { progress: undefined });
  update((d) => { d.budget.studySpent += 0.48; });
  await say([p('Sběr, výpočty i analýza doběhly. Výsledky jsou z běhu ' + getState().run.id + ' nad revizí ' + getState().run.revision + ' a jsou fiktivní, takže jen interní.'), ul('Raiffeisenbank je potlačena (Kish n 27 < 30), v mapě nezmapována.', 'Modul Segmenty je blokován: srovnání segmentů v AIA zatím není.', getState().failures.analysisValidation ? 'Modul Hypotézy dvakrát neprošel kontrolou schématu; opakování je na vás.' : 'Koncept zprávy je sestaven, neschválen.')],
    { links: [{ stage: 'results', label: 'Výsledky' }, { stage: 'analysis', label: 'Analýza' }], runRev: getState().run.revision });
}

export async function retryProvider(t: number) {
  update((d) => { d.failures.provider = false; d.run.status = 'running'; d.log.push({ id: nextId('cmd'), cmd: 'run.retry_step fieldwork', by: 'ui', ok: true, at: C.clockLabel(d), stage: 'fieldwork' }); });
  await w(t, 100);
}

// ------------------------------------------------------------ G · results
export async function resultsTour(t: number) {
  const s = getState();
  if (s.run.status !== 'completed') { await w(t, 300); await say([p('Výsledky zatím nejsou: běh ' + (s.run.status === 'none' || s.run.status === 'ready' ? 'neproběhl' : 'ještě běží') + '.')]); return; }
  C.visual.open('results', 'set1');
  await w(t, 300);
  await say([
    p('Výsledky běhu ' + s.run.id + ' (revize ' + s.run.revision + ', fiktivní respondenti, n 400):'),
    ul('Sada 1 jsou průměry na škále 1–10, ne procenta. Fio 6,8 z 10 [6,5; 7,1], 4. ze 7 vykázaných; od Revolutu, České spořitelny a ČSOB ji intervaly neoddělují.', 'Raiffeisenbank je potlačena (Kish n 27 < 30): číslo neukazuji ani já.', 'Q8: změnu zvažuje 24 % [20; 28] ze všech 400. Cílové banky jsou podíly ze 96 zvažujících.', 'Otevřené odpovědi Q9 jsou data, ne připuštěná evidence; nejsou kódované.'),
  ], { links: [{ stage: 'results', focus: 'set1', label: 'Výsledky · Sada 1' }, { stage: 'results', focus: 'q8', label: 'Výsledky · Q8' }], sources: ['S6'], runRev: s.run.revision });
  followUps(['Proč je Fio blízko Air Bank?', 'Rozeber otevřené odpovědi Q9']);
}

// ------------------------------------------------------------ H · sociomap
export async function pairWhy(t: number) {
  C.visual.open('sociomap', 'fio~air');
  C.visual.select('sociomap', 'fio~air');
  const l = startActivity('lookup', 'Čtu dvojici Fio – Air Bank', 'art-sm-16a-set1', [['Artefakt', MAP.artifact + ' · ' + MAP.spec], ['Metoda', MAP.method]]);
  await w(t, 400); actDone(l, 'r 0,31 · n 340 · spolehlivá');
  C.visual.inspect({ type: 'pair', a: 'fio', b: 'air' });
  const pr = findPair('fio', 'air')!;
  await say([
    p('Blízkost na mapě znamená, že relativní preference se u respondentů pohybují spolu: kdo dá Fio víc bodů než ostatním bankám, dá obvykle víc i Air Bank. Neznamená, že je hodnotí stejně: Fio má 6,8, Air Bank 7,6 z 10 (výška na mapě).'),
    kv(['Vztah', 'r ' + pr.r!.toFixed(2).replace('.', ',') + ' [' + pr.lo!.toFixed(2).replace('.', ',') + '; ' + pr.hi!.toFixed(2).replace('.', ',') + ']'], ['Podpora', 'n ' + pr.n + ' lidí hodnotících obě · spolehlivá'], ['Shoda mapy', 'Stress-1 0,083 · dobrá']),
    p('Proč se pohybují spolu, mapa neříká. Může to být společný „digitální“ výběr; to je výklad, ne měření. Externí kontext mohu dohledat v rámci oprávnění.'),
  ], { sources: ['S7'], runRev: getState().run.revision });
  followUps(['Odeber slabé vztahy', 'Dohledej kontext k této dvojici']);
}

export async function removeWeak(t: number) {
  await w(t, 300);
  C.visual.open('sociomap');
  await say([p('Záleží, co tím myslíte. Skrýt slabé vztahy v zobrazení lze hned a výpočet se nezmění. Vyřadit je z výpočtu by změnilo metodiku mapy: to je nová verze v Metodice a nový běh.')]);
  const id = C.openDecision({ title: 'Slabé vztahy: zobrazení, nebo výpočet?', reason: 'V mapě jsou 4 slabé dvojice (interval zahrnuje 0) a 1 neznámá. Odkazy se kreslí jen u spolehlivých nad prahem 0,10; slabé jsou vidět po výběru objektu.', alternatives: [
    { id: 'filter', label: 'Skrýt v zobrazení', detail: 'Filtr zobrazení; mapa, pozice a Stress-1 beze změny', recommended: true },
    { id: 'method', label: 'Vyřadit z výpočtu', detail: 'Nová verze metodiky (správce) a nový běh' },
  ], impact: ['Zmrazený artefakt mapy se v žádném případě nemění'], kind: 'method', stage: 'sociomap' });
  decisionMsg(id);
}

// ------------------------------------------------------------ I · map-context research
export async function mapContext(t: number, approved = false) {
  const s = getState();
  if (s.research.some((r) => r.targetRef === 'sociomap.pair.fio~air')) {
    await w(t, 200);
    C.visual.open('sociomap', 'fio~air');
    await say([p('Kontext k této dvojici už je připojen (DR-44). Mapa se tím nezměnila.')], { sources: ['S4'] });
    return;
  }
  void approved;
  const q: C.ResearchRequest = { purpose: 'INTERPRETATION_RESEARCH', targetRef: 'sociomap.pair.fio~air', target: 'Fio – Air Bank', inputClass: 'C', route: 'brave', estimate: 0.38 };
  const r = C.requestResearch(q, 'lead');
  if (!r.ok) { await say([p('AIA výzkum nepovolilo: ' + r.reason)]); return; }
  C.visual.open('sociomap', 'fio~air');
  const a = startActivity('research', 'Kontext k dvojici Fio – Air Bank', 'Krok 1 ze 6', [['Účel', 'INTERPRETATION_RESEARCH (nic nemění)'], ['Cíl', 'pair fio~air · ' + MAP.artifact + ' (zmrazen, sha256)'], ['Dotaz', 'odvozen jen z názvů bank (třída C)'], ['Trasa', 'Brave · placená · schválená'], ['Rezervace', '0,38 USD']], { stage: 'sociomap', focus: 'fio~air', label: 'Sociomapa' });
  update((d) => { d.research.push({ id: 'DR-44', purpose: 'INTERPRETATION_RESEARCH', target: 'Sociomapa · Fio – Air Bank · ' + d.run.id, targetRef: 'sociomap.pair.fio~air', status: 'running', step: 0, sources: 0, admitted: 0, quarantined: 0, noEvidence: 0, spent: 0, findings: [] }); });
  for (let i = 1; i <= 6; i++) { actUpdate(a, { summary: 'Krok ' + i + ' ze 6', progress: { done: i, total: 6, unit: 'kroků' } }); await w(t, 380); }
  update((d) => { const x = d.research.find((y) => y.id === 'DR-44')!; Object.assign(x, { status: 'done', step: 6, sources: 9, admitted: 1, quarantined: 1, spent: 0.38, findings: ['S4'] }); d.evidenceAttached['pair.fio~air'] = ['S4']; d.budget.studySpent += 0.38; d.budget.studyReserved = Math.max(0, d.budget.studyReserved - 0.38); });
  actDone(a, '1 zjištění připojeno k dvojici · mapa beze změny', { progress: undefined });
  await say([p('Kontext je u dvojice Fio – Air Bank v mapě, označený jako externí. Ilustrativní zdroj uvádí, že mladí často mají dvě banky, tradiční a digitální. To může blízkost vysvětlovat, ale nedokazuje ji. Mapa, její výpočet ani výsledky se nezměnily.')], { sources: ['S4'], links: [{ stage: 'sociomap', focus: 'fio~air', label: 'Sociomapa · Fio – Air Bank' }] });
}

// ------------------------------------------------------------ J · analysis
export async function execSummary(t: number) {
  C.visual.open('analysis');
  await w(t, 400);
  await say([
    p('Do shrnutí podle mě patří tři zjištění; všechna mají připuštěné nároky, ale jsou zatím koncept (nikdo je nerevidoval):'),
    ul('F2 zvažování změny 24 % [20; 28], cíle Revolut a Air Bank (báze 96, široké intervaly).', 'F1 postavení Fio 6,8 z 10, 4. ze 7, odlišitelná jen od Air Bank.', 'F3 znalost značky 81 % vs. investičního účtu 38 %.'),
    p('F4 (blízkost Fio a Air Bank) jen jako výklad, ne zjištění. Nepatří sem C7 (mladší vs. starší) ani C8 (Fio jako banka pro investory): oba nároky jsou blokované.'),
  ], { links: [{ stage: 'analysis', focus: 'F2', label: 'Analýza · F2' }], sources: ['S6', 'S7'], runRev: getState().run.revision });
}

export async function openAnswers(t: number) {
  C.visual.open('analysis', 'q9');
  const a = startActivity('worker', 'Rozbor otevřených odpovědí Q9', 'Navržená schopnost', [['Specialista', 'kvalitativní kódování · v AIA zatím není'], ['Vstup', '96 odpovědí Q9 · RUN-16A'], ['Výstup', 'návrh témat; počty až z uložené klasifikace']], { stage: 'analysis', focus: 'q9', label: 'Analýza · Q9' });
  await w(t, 900);
  const pid = C.createProposal(codingProposal(), 'worker');
  actDone(a, '5 témat navrženo · Zkontrolovat', { details: [...getState().activities.find((x) => x.id === a)!.details, ['Id', pid]] });
  await say([p('Navrhl jsem 5 témat s příklady u každého. Je to navržená schopnost: počty se po přijetí odvodí z uložené klasifikace každé odpovědi, ne z textu modelu.')], { links: [{ stage: 'analysis', focus: 'q9', label: 'Analýza · Q9' }] });
}

export async function retryAnalysis(t: number) {
  update((d) => { d.log.push({ id: nextId('cmd'), cmd: 'analysis.retry (Hypotézy)', by: 'ui', ok: true, at: C.clockLabel(d), stage: 'analysis' }); });
  const a = startActivity('worker', 'Analýza · nové kolo (Hypotézy)', 'Běží…', [['Kolo', 'analysis_round 2 · nad stejnými zmrazenými daty'], ['Bez sběru', 'ano']], { stage: 'analysis', label: 'Analýza' });
  await w(t, 1100);
  update((d) => { d.failures.analysisValidation = false; d.budget.studySpent += 0.22; });
  actDone(a, 'Hypotézy hotovo · 7 z 8');
}

// ------------------------------------------------------------ K · report
export async function reportProposal(t: number, which: 'less' | 'emph') {
  C.visual.open('report', 'r1');
  const s = getState();
  const a = startActivity('worker', which === 'less' ? 'Úprava shrnutí: méně technicky' : 'Úprava shrnutí: Sociomapa', 'Oddíl 1', [['Skladatel', 'aia.report.revise · jen oddíl 1'], ['Vstupy', 'oddíl 1 + nároky C1–C6 (ne celá studie)'], ['Kontrola', 'jednotky, báze, intervaly, srovnání']], { stage: 'report', focus: 'r1', label: 'Zpráva' });
  await w(t, 800); actStep(a, 'Kontrola evidence: jednotky, báze a intervaly zachovány', 'done');
  await w(t, 300);
  C.createProposal(which === 'less' ? reportLessTechnical(s.reportState.draft) : reportSociomapEmphasis(s.reportState.draft), 'worker');
  actDone(a, (which === 'less' ? '2 změny' : '1 nový odstavec') + ' · Zkontrolovat');
  await say([p(which === 'less' ? 'Navrhl jsem dvě sledované změny v oddílu 1. Odkazy na čísla zůstaly u stejných vět; intervaly a báze nezmizely, jen jsou psané běžnou řečí.' : 'Navrhl jsem do shrnutí odstavec, který odkáže na mapu. Skupiny bank v něm jsou čtení mapy, ne nový výpočet; vztah popisuji jako pohyb relativních preferencí.')], { links: [{ stage: 'report', focus: 'r1', label: 'Zpráva · oddíl 1' }] });
}

export async function youngerFirst(t: number) {
  C.visual.open('report', 'r1');
  await w(t, 400);
  await say([p('Zjištění o mladších zákaznících (18–24 vs. 25–35) ve zprávě není a být nemůže: srovnání segmentů AIA zatím neumí a nárok C7 je blokovaný.'), p('Na začátek mohu dát zjištění o zvažování změny (24 %), které se týká celé skupiny 18–35. Připravím to jako návrh?')], { links: [{ stage: 'analysis', focus: 'C7', label: 'Analýza · blokované nároky' }] });
  C.createProposal(reportSwap(getState().reportState.draft), 'worker');
}

export async function overstate(t: number) {
  C.visual.open('report', 'P3');
  const a = startActivity('worker', 'Kontrola věty 1.3', 'Kontrola evidence', [['Kontrola', 'aia.report.claim_check'], ['Věta', '1.3'], ['Nároky', 'žádný připuštěný nárok']], { stage: 'report', focus: 'P3', label: 'Zpráva · 1.3' });
  await w(t, 700);
  actDone(a, 'Přehání · 1 změna navržena');
  C.createProposal(reportOverstate(getState().reportState.draft), 'worker');
  await say([p('Ano. Věta 1.3 tvrdí, že digitální zkušenost je stejně důležitá jako cena. Žádný připuštěný nárok takové srovnání nepodporuje: Q13 zatím nemá analýzu. Navrhl jsem opravu přímo ve Zprávě.')], { links: [{ stage: 'report', focus: 'P3', label: 'Zpráva · věta 1.3' }] });
}

export async function numberOrigin(t: number) {
  C.visual.open('report', 'P1');
  await w(t, 300);
  C.visual.inspect({ type: 'claim', id: 'C1' });
  await say([p('6,8 je průměr ze škály 1–10 u 356 respondentů, kteří Fio hodnotili (Kish n), z agregace běhu RUN-16A nad revizí 16. Řetěz od věty po artefakt je v inspektoru.')], { sources: ['S6'], runRev: 16 });
}

export async function clientReport(t: number) {
  await w(t, 300);
  update((d) => { d.log.push({ id: nextId('cmd'), cmd: 'report.client', by: 'lead', ok: false, reason: 'client_report_refused: běh není modelovaný z populace (SYNTHETIC_AI_FICTIONAL).', at: C.clockLabel(d), stage: 'report' }); });
  await say([p('Klientskou zprávu AIA pro tento běh odmítá (client_report_refused): respondenti jsou fiktivní, ne modelovaní z populace. Interní zprávu lze schválit; ke klientovi nesmí.')]);
}

export async function replaceRespondents(t: number) {
  await w(t, 300);
  await say([p('Náhrada respondentů v AIA není. Je to navržená schopnost a její metodický význam (co náhrada znamená pro vážení a pro podporu) zatím nikdo neurčil. Stejné hodnocení všech bank samo o sobě důvod k vyřazení není.')]);
}

// ------------------------------------------------------------ L · PM
export async function whereAreWe(t: number) {
  await w(t, 300);
  const s = getState();
  const done = STAGE_ORDER.filter((x) => ['accepted', 'complete', 'frozen'].includes(stageStatus(s, x).kind)).map((x) => STAGES[x].label);
  const pend = pendingProposals(s).map((x) => STAGES[x.stage].label + ': ' + x.title);
  const decs = s.decisions.filter((d) => d.status === 'open').map((d) => d.title);
  const blocked = STAGE_ORDER.filter((x) => ['blocked', 'failed', 'reopened'].includes(stageStatus(s, x).kind)).map((x) => STAGES[x].label + ' (' + stageStatus(s, x).note + ')');
  const nx = nextForYou(s);
  await say([
    kv(['Hotovo', done.join(', ') || '—'], ['Teď', STAGES[s.stage].label + ' · ' + stageStatus(s, s.stage).note], ['Čeká na vás', [...pend, ...decs].join('; ') || 'nic'], ['Blokuje', blocked.join('; ') || 'nic'],
      ['Rozpočet', s.budget.studySpent.toFixed(2).replace('.', ',') + ' z ' + s.budget.studyLimit + ' USD' + (s.budget.studyReserved ? ' · rezervováno ' + s.budget.studyReserved.toFixed(2).replace('.', ',') : '')]),
    p('Další krok: ' + (nx ? nx.why : s.run.status === 'completed' ? 'zkontrolovat a interně schválit zprávu.' : 'spustit sběr dat (vaše rozhodnutí).')),
  ], { links: nx ? [{ stage: nx.stage, label: STAGES[nx.stage].label }] : [] });
}

export async function continueUntil(t: number) {
  update((d) => { d.autopilot = true; d.pmPaused = undefined; });
  const s = getState();
  if (s.run.status === 'completed') {
    await say([p('Pokračuji: zkontroluji zprávu proti evidenci a připravím úpravy. Zastavím se u schválení, které patří vám.')]);
    await overstate(t);
    await w(t, 300);
    update((d) => { d.pmPaused = 'Schválení zprávy je vaše rozhodnutí.'; });
    await say([p('Tady potřebuji vás: oprava věty 1.3 čeká na přijetí a zprávu interně schvalujete vy. Klientskou zprávu AIA pro fiktivní běh neumožní.')], { links: [{ stage: 'report', focus: 'P3', label: 'Zpráva · 1.3' }] });
    return;
  }
  await say([p('Pokračuji v rámci vašich oprávnění: posoudím dotazník, ověřím předpoklady a zkontroluji připravenost. Zastavím se u prvního rozhodnutí, které patří vám.')]);
  if (!pendingProposals(getState(), 'questionnaire').length && contentRev(getState(), 'questionnaire') < 15) await questionnaireReview(t);
  await w(t, 300);
  if (!getState().research.some((r) => r.targetRef === 'audience.ass')) await audienceResearch(t);
  await w(t, 300);
  const c = startActivity('compute', 'Kontrola připravenosti', 'readiness + outlook', [['Výpočet', 'readiness (deterministické)'], ['Revize', String(getState().revision)]], { stage: 'sample', label: 'Vzorek' });
  await w(t, 500);
  const pend = pendingProposals(getState());
  actDone(c, pend.length + ' návrhy čekají · 3 varování');
  update((d) => { d.pmPaused = 'Přijetí návrhů a spuštění běhu patří vám.'; });
  await say([p('Tady se zastavuji. Potřebuji vás:'), ul(...pend.map((x) => STAGES[x.stage].label + ': ' + x.title + ' (přijmout, nebo odmítnout)'), 'Potom spuštění sběru dat (vaše rozhodnutí; strop je pod limitem potvrzení).')], { links: pend.map((x) => ({ stage: x.stage, label: STAGES[x.stage].label })) });
}

// ------------------------------------------------------------ element requests (@)
const FIELD: Partial<Record<StageId, string>> = { brief: 'text', design: 'text', questionnaire: 'q', audience: 'text', dimensions: 'def', report: 'text' };
const SHORTER: Record<string, string> = {
  Q5: 'Jak dlouho jste klientem své hlavní banky?',
  Q13: 'Vyberte tři věci, které jsou pro vás při volbě banky nejdůležitější.',
  P1: 'Fio banka: 6,8 z 10 (6,5–7,1), čtvrtá ze sedmi bank; od Revolutu, České spořitelny a ČSOB neodlišitelná.',
};

export async function elementRequest(t: number, raw: string, ref: NonNullable<Message['ref']>) {
  const s = getState();
  const stage = ref.stage;
  const field = FIELD[stage];
  const doc = workingDoc(s, stage);
  const hit = findItem(doc, ref.path);
  await w(t, 300);
  if (!field || !hit) { await say([p('Tento prvek je součástí zmrazeného výsledku; měnit ho nelze. Mohu ho vysvětlit nebo dohledat jeho původ.')]); return; }
  const sec = doc.sections.find((x) => x.id === hit.sec)!;
  const locked = (hit.item.lock as string | undefined) ?? sec.locked;
  const x = raw.toLowerCase();
  const current = String(hit.item[field] ?? '');
  let change: { kind: 'modify' | 'remove' | 'add'; to?: string; op: import('../model/types').Op; why: string } | null = null;
  const quoted = raw.match(/[„"“](.+?)[“"”]/)?.[1] ?? raw.match(/(?:na|to)[: ]+(.+)$/i)?.[1];
  if (has(x, 'odeber', 'smaž', 'remove', 'delete', 'odstraň')) change = { kind: 'remove', op: { op: 'remove', sec: hit.sec, item: ref.path }, why: 'Na vaši žádost.' };
  else if (has(x, 'nahoru', 'up')) change = { kind: 'modify', to: 'o pozici výš', op: { op: 'move', sec: hit.sec, item: ref.path, dir: -1 }, why: 'Přesun na vaši žádost.' };
  else if (has(x, 'dolů', 'down')) change = { kind: 'modify', to: 'o pozici níž', op: { op: 'move', sec: hit.sec, item: ref.path, dir: 1 }, why: 'Přesun na vaši žádost.' };
  else if (has(x, 'krat', 'zkrať', 'short')) { const to = SHORTER[ref.path] ?? current.split(/[,;(]/)[0].trim() + (current.endsWith('?') && !current.split(/[,;(]/)[0].trim().endsWith('?') ? '?' : ''); change = { kind: 'modify', to, op: { op: 'set', sec: hit.sec, item: ref.path, field, value: to }, why: 'Kratší znění; význam zachován.' }; }
  else if (quoted) change = { kind: 'modify', to: quoted.trim(), op: { op: 'set', sec: hit.sec, item: ref.path, field, value: quoted.trim() }, why: 'Znění podle vás.' };
  if (locked && change) {
    update((d) => { d.log.push({ id: nextId('cmd'), cmd: 'propose ' + C.describeOp(change!.op), by: 'lead', ok: false, reason: 'Chráněný prvek: ' + locked, at: C.clockLabel(d), stage }); });
    await say([p(ref.label + ' je chráněný: ' + locked), p('Návrh nepřipravím. Pokud ho opravdu chcete změnit, je to metodické rozhodnutí: nová revize metodiky a nový běh.')]);
    return;
  }
  if (!change) { await say([p('Co se má s „' + ref.label + '“ stát? Např. „kratší“, „odebrat“, „nahoru“ nebo nové znění v uvozovkách.')]); return; }
  C.createProposal({ stage, kind: stage === 'report' ? 'presentation' : 'design', title: 'Úprava ' + ref.label, author: 'Vedoucí výzkumu · na vaši žádost', baseRev: C.currentBase(s, stage), baseLabel: (stage === 'report' ? 'Koncept ' : 'Revize ') + C.currentBase(s, stage),
    changes: [{ id: 'x1', target: hit.sec + '.' + ref.path, label: ref.label, kind: change.kind, from: change.kind === 'remove' || change.op.op === 'set' ? current : undefined, to: change.to, why: change.why, op: change.op }],
    implications: stage === 'questionnaire' ? ['Pokrytí: ' + ((hit.item.rq as string[] | undefined)?.join(', ') || 'žádná výzkumná otázka') + (change.kind === 'remove' && (hit.item.rq as string[] | undefined)?.length ? ' ztratí měření' : ' zachováno')] : ['Mění jen tento prvek.'],
    impact: [], recompute: 'Ne.' }, 'lead');
  C.visual.open(stage, ref.path);
  await say([p('Návrh je v artefaktu u „' + ref.label + '“. Použít ho můžete vy.')], { links: [{ stage, focus: ref.path, label: STAGES[stage].label + ' · ' + ref.label }] });
}

// ------------------------------------------------------------ scenario catalogue
export interface Scenario { id: string; label: string; detail: string; group: 'main' | 'exception'; seed: () => import('../model/types').AppState; run?: (t: number) => Promise<void>; prompt?: string; stage?: StageId }

export const SCENARIOS: Scenario[] = [
  { id: 'A', label: 'A · Otevřít studii', detail: 'Stav a další doporučení', group: 'main', seed: seedDesign, run: openStudy, stage: 'questionnaire' },
  { id: 'B', label: 'B · Dotazník', detail: 'Změny u otázek, pokrytí, chráněné položky', group: 'main', seed: seedDesign, prompt: 'Posuď dotazník a navrhni zkrácení', stage: 'questionnaire' },
  { id: 'C', label: 'C · Výzkum cílové skupiny', detail: 'Oprávnění, evidence u předpokladu', group: 'main', seed: seedDesign, prompt: 'Ověř předpoklady o cílové skupině', stage: 'audience' },
  { id: 'D', label: 'D · Ruční úprava', detail: 'Pracovní verze a Vedoucí ji vidí', group: 'main', seed: () => withProposal(seedDesign()), run: demoManualEdit, stage: 'questionnaire' },
  { id: 'E', label: 'E · Zastaralý návrh', detail: 'Revize postoupí, odmítnutí, nové sestavení', group: 'main', seed: () => withWorkingQ5(withProposal(seedDesign())), stage: 'questionnaire' },
  { id: 'F', label: 'F · Sběr dat', detail: 'Průběh, čekání, náklady, zásah', group: 'main', seed: seedExecution, prompt: 'Spusť sběr dat', stage: 'fieldwork' },
  { id: 'G', label: 'G · Výsledky', detail: 'Jednotky, podpora, potlačení, nejistota', group: 'main', seed: seedEvidence, prompt: 'Projdi se mnou výsledky', stage: 'results' },
  { id: 'H', label: 'H · Sociomapa', detail: 'Dvojice, výklad, zobrazení vs. výpočet', group: 'main', seed: seedEvidence, prompt: 'Proč je Fio blízko Air Bank?', stage: 'sociomap' },
  { id: 'I', label: 'I · Kontext k mapě', detail: 'Evidence vysvětluje, mapu nemění', group: 'main', seed: seedEvidence, prompt: 'Dohledej kontext k dvojici Fio – Air Bank na mapě', stage: 'sociomap' },
  { id: 'J', label: 'J · Analýza', detail: 'Podložená zjištění, mezery, blokované nároky', group: 'main', seed: seedEvidence, prompt: 'Která zjištění patří do shrnutí?', stage: 'analysis' },
  { id: 'K', label: 'K · Zpráva', detail: 'Sémantické úpravy, sledované změny, odkazy', group: 'main', seed: seedEvidence, prompt: 'Udělej shrnutí méně technické', stage: 'report' },
  { id: 'L', label: 'L · Pokračuj, dokud mě nebudeš potřebovat', detail: 'Pracuje v oprávnění, zastaví se u rozhodnutí', group: 'main', seed: seedDesign, prompt: 'Pokračuj, dokud mě nebudeš potřebovat', stage: 'questionnaire' },
  { id: 'M', label: 'M · Návrat po dnech', detail: 'Co se změnilo, co čeká, další krok', group: 'main', seed: seedReturn, stage: 'report' },
  { id: 'X1', label: 'Výjimka · Limit rozpočtu', detail: 'Běh čeká na navýšení', group: 'exception', seed: () => { const s = seedExecution(); s.failures.budgetLimit = true; return s; }, prompt: 'Spusť sběr dat', stage: 'fieldwork' },
  { id: 'X2', label: 'Výjimka · Chybějící evidence', detail: 'A3 bez zdroje o složení klientů', group: 'exception', seed: seedDesign, prompt: 'Ověř předpoklady o cílové skupině', stage: 'audience' },
  { id: 'X3', label: 'Výjimka · Selhání poskytovatele', detail: 'Krok zaparkován, opakování na vás', group: 'exception', seed: () => { const s = seedExecution(); s.failures.provider = true; return s; }, prompt: 'Spusť sběr dat', stage: 'fieldwork' },
  { id: 'X4', label: 'Výjimka · Analýza neprošla kontrolou', detail: 'Modul Hypotézy, nové kolo', group: 'exception', seed: () => { const s = seedEvidence(); s.failures.analysisValidation = true; return s; }, stage: 'analysis' },
  { id: 'X5', label: 'Výjimka · Znovu otevřená práce', detail: 'Úprava dotazníku po běhu', group: 'exception', seed: () => { const s = seedEvidence(); s.working.questionnaire = [{ id: 'op-x5', actor: 'you', at: '9:10', op: { op: 'set', sec: 'b4', item: 'Q12', field: 'q', value: 'Jak hodnotíte mobilní aplikaci své hlavní banky (1–10)?' }, note: 'ruční úprava' }]; s.workingSince.questionnaire = 15; s.stage = 'questionnaire'; return s; }, stage: 'questionnaire' },
  { id: 'X6', label: 'Výjimka · Metodické omezení', detail: 'Vyřadit slabé vztahy z výpočtu', group: 'exception', seed: seedEvidence, prompt: 'Odeber slabé vztahy z mapy', stage: 'sociomap' },
  { id: 'X7', label: 'Výjimka · Nedostupná schopnost', detail: 'Klientská zpráva fiktivního běhu', group: 'exception', seed: seedEvidence, prompt: 'Připrav klientskou zprávu', stage: 'report' },
];

function withProposal(s: import('../model/types').AppState) {
  s.proposals.push({ ...questionnaireOptimisation(14), id: 'pr-seed', status: 'pending', createdAt: '9:44' });
  s.activities.push({ id: 'act-seed', type: 'worker', title: 'Posouzení dotazníku', summary: '7 změn navrženo', status: 'done', startedAt: 0, steps: [], link: { stage: 'questionnaire', label: 'Zkontrolovat' }, details: [['Specialista', 'aia.research.questionnaire_optimize'], ['Výchozí stav', 'Dotazník revize 14'], ['Náklad', '0,21 USD']] });
  s.messages.push({ id: 'm-seed-a', kind: 'activity', day: s.day, at: '9:44', rev: 14, activityId: 'act-seed' });
  return s;
}
function withWorkingQ5(s: import('../model/types').AppState) {
  s.working.questionnaire = [{ id: 'op-q5', actor: 'you', at: '9:50', op: { op: 'set', sec: 'b2', item: 'Q5', field: 'q', value: 'Jak dlouho máte účet u své hlavní banky?' }, note: 'ruční úprava' }];
  s.workingSince.questionnaire = 14;
  s.leadSeen.questionnaire = 1;
  s.messages.push({ id: 'm-seed-e', kind: 'lead', day: s.day, at: '9:51', rev: 14, blocks: [{ t: 'p', x: 'Vidím vaši úpravu Q5 v pracovní verzi nad revizí 14. Čekající návrh mění Q5 také. Přijmete-li svou verzi, návrh zastará.' }], links: [{ stage: 'questionnaire', focus: 'Q5', label: 'Dotazník · Q5' }] });
  return s;
}

export function loadScenario(id: string, opts: { autorun?: boolean } = {}) {
  const sc = SCENARIOS.find((x) => x.id === id);
  if (!sc) return;
  cancelAll(); clearTimers(); setFast(false);
  const st = sc.seed();
  st.scenario = id;
  if (sc.stage) st.stage = sc.stage;
  replaceState(st);
  if (opts.autorun === false) return;
  if (sc.run) void runScript(sc.run);
  else if (sc.prompt) setTimeout(() => send(sc.prompt!), 250);
}
