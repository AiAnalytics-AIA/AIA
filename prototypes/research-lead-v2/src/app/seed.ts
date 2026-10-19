// Seeded study states. Every scenario starts from one of these, built from the
// same fixture and the same op/proposal data the live commands use, so a seeded
// state is one the interactive flow could have produced.
import type { Activity, AppState, Message, Block, AppliedOp, Decision } from '../model/types';
import { questionnaireOptimisation, audienceEvidence } from '../model/proposals';
import { loadPrefs, resetIds } from './store';

let n = 0;
const id = (p: string) => p + '_seed' + (++n);

function msg(kind: Message['kind'], day: string, at: string, rev: number, extra: Partial<Message> = {}): Message {
  return { id: id('m'), kind, day, at, rev, ...extra };
}
const P = (x: string): Block => ({ t: 'p', x });

export function baseState(): AppState {
  n = 0;
  resetIds(1000);
  const prefs = loadPrefs();
  return {
    view: 'study', scenario: 'A', clock: 0, day: 'St 14. 10.', revision: 14, stage: 'questionnaire', mode: 'normal',
    split: typeof prefs.split === 'number' ? prefs.split : 40,
    accepted: {}, working: {}, workingSince: {}, leadSeen: {}, reopened: [], proposals: [], activities: [], decisions: [], messages: [],
    run: { id: '—', revision: 0, status: 'none', done: 0, target: 400, inFlight: 0, constantResponders: 0, spent: 0, reserved: 0, ceiling: 18.4, elapsed: 0, waits: 0 },
    research: [], evidenceAttached: {},
    budget: { studyLimit: 60, studySpent: 3.12, studyReserved: 0, researchLimit: 5, researchSpent: 0, spendConfirm: 25 },
    viewFilters: { sociomapHideWeak: false, sociomapLabels: true, sociomapView: 'top' },
    inspector: [], focusPath: null, selection: {}, composer: { draft: '', ref: null, queue: [] }, busy: false, autopilot: false, unreadBelow: 0,
    analysisState: 'none', reportState: { draft: 1, reviewed: false, changes: 'none' },
    failures: { provider: false, budgetLimit: false, missingEvidence: false, analysisValidation: false },
    log: [], codingAccepted: false,
  };
}

function act(s: AppState, a: Omit<Activity, 'id' | 'startedAt'>, day: string, at: string): void {
  const aid = id('act');
  s.activities.push({ ...a, id: aid, startedAt: 0 } as Activity);
  s.messages.push(msg('activity', day, at, s.revision, { activityId: aid }));
}
function decided(s: AppState, d: Omit<Decision, 'id' | 'status'>, chosen: string, day: string, at: string) {
  const did = id('dec');
  s.decisions.push({ ...d, id: did, status: 'decided', chosen });
  s.messages.push(msg('decision', day, at, s.revision, { decisionId: did }));
}

// Long, revision-aware history (§12): earlier answers keep the revision they
// were true for and say so when it has since moved.
function history(s: AppState) {
  const d1 = 'Pá 2. 10.', d2 = 'Po 5. 10.', d3 = 'Pá 9. 10.', d4 = 'Út 13. 10.';
  s.revision = 12;
  s.messages.push(msg('divider', d1, '10:02', 12, { text: d1 }));
  s.messages.push(msg('user', d1, '10:02', 12, { text: 'Zakládám studii pro Fio. Zajímají nás lidé do 35 let a proč odcházejí. Briefing přikládám.' }));
  act(s, { type: 'worker', title: 'Zadání rozebráno', summary: '3 cíle · 2 rozhodnutí · 3 předpoklady', status: 'done', steps: [{ text: 'Briefing_Fio_2026.pdf přečten (2 strany)', tone: 'done' }, { text: 'Cíle, rozhodnutí a předpoklady navrženy do Zadání', tone: 'done' }],
    link: { stage: 'brief', label: 'Zadání' }, details: [['Specialista', 'aia.research.brief_analysis · prompt v2'], ['Výchozí stav', 'prázdné zadání'], ['Vstupy', 'Briefing_Fio_2026.pdf (třída A)'], ['Běh', 'Bedrock EU · přes ModelGateway'], ['Volání', '1 + 0 oprav'], ['Náklad', '0,09 USD'], ['Id', 'job-b81 · art-77c']] }, d1, '10:03');
  s.messages.push(msg('lead', d1, '10:04', 12, { blocks: [P('Zadání jsem rozebral do pěti částí; najdete je v artefaktu Zadání. Jeden podklad chybí: data o složení klientů. Bez nich předpoklad A3 nepůjde ověřit z dokumentů.')], links: [{ stage: 'brief', focus: 'M3', label: 'Zadání · Podklady' }], historical: 'Platilo pro revizi 12' }));
  decided(s, { title: 'Věkové vymezení cílové skupiny', reason: 'Briefing říká „do 35 let“, ale nespecifikuje spodní hranici.', alternatives: [{ id: 'a', label: '18–35 let', detail: 'Dospělí; běžný účet bez souhlasu rodiče', recommended: true }, { id: 'b', label: '15–35 let', detail: 'Zahrnuje studentské účty; nutný jiný screening' }], impact: ['Q1 screening', 'Filtry populace'], kind: 'scope', stage: 'audience' }, 'a', d1, '10:06');

  s.messages.push(msg('divider', d2, '9:15', 12, { text: d2 }));
  s.messages.push(msg('user', d2, '9:15', 12, { text: 'Navrhni výzkumné otázky a metody.' }));
  act(s, { type: 'worker', title: 'Návrh výzkumu sestaven', summary: '5 otázek · 2 nevyřešené volby', status: 'done', steps: [{ text: 'Otázky navázány na rozhodnutí D1, D2', tone: 'done' }, { text: 'Srovnání segmentů: v AIA zatím není → nevyřešená volba U1', tone: 'done-warn' }],
    link: { stage: 'design', label: 'Návrh' }, details: [['Specialista', 'aia.research.design_build · prompt v3'], ['Výchozí stav', 'Zadání r12'], ['Volání', '1 + 1 oprava schématu'], ['Náklad', '0,31 USD']] }, d2, '9:17');
  s.revision = 13;
  s.messages.push(msg('notice', d2, '9:40', 13, { text: 'Revize 13 přijata vámi · Návrh výzkumu', tone: 'done' }));

  const qa: [string, string, number][] = [
    ['Proč RQ3 nemá plné pokrytí?', 'Srovnání 18–24 a 25–35 AIA zatím neumí (compare_segments). Otázku lze ponechat jako popisnou, nebo ji přeformulovat.', 13],
    ['Kolik bude stát sběr pro n 400?', 'Strop běhu by byl ≈ 18 USD; to je pod limitem potvrzení studie (25 USD).', 13],
    ['Můžeme mít odpovědi i od lidí z panelu?', 'Panel respondentů je v tomto prostředí vypnutý; běh použije fiktivní AI respondenty a výsledky půjdou jen interně.', 13],
  ];
  qa.forEach(([q, a, rev], i) => {
    s.messages.push(msg('user', d2, '10:' + (10 + i * 7), rev, { text: q }));
    s.messages.push(msg('lead', d2, '10:' + (11 + i * 7), rev, { blocks: [P(a)], historical: 'Platilo pro revizi ' + rev }));
  });

  // Two working days of short exchanges: the long tail a real study accumulates.
  const topics: [string, string][] = [
    ['Q1', 'Věk je screener: mimo 18–35 dotazník končí.'], ['Q2', 'Hlavní banka: jedna možnost, 8 bank + jiná.'], ['Q5', 'Délka vztahu k bance; znění je zatím dlouhé.'],
    ['Q8', 'Zvažování změny: Ano / Ne / Nevím.'], ['Q9', 'Otevřený důvod změny, jen po Q8 = Ano.'], ['Q10', 'Cílová banka, jen po Q8 = Ano.'],
    ['Sada 1', 'Hodnocení 8 bank na 1–10; vstup Sociomapy.'], ['Q12', 'Hodnocení aplikace hlavní banky 1–10.'], ['Q13', 'Pořadí šesti důvodů volby; nejdelší úloha.'],
    ['Q15', 'Znalost bank podle jména.'], ['Q16', 'Znalost produktů Fio; jiný konstrukt než Q15.'], ['Q19', 'Kontrola pozornosti; chráněná.'],
    ['Q20', 'Vzdělání; chybí VOŠ.'], ['Q21', 'Kraj; 14 možností.'], ['RQ1', 'Měří ji Sada 1.'], ['RQ2', 'Měří ji Q8, Q9 a Q10.'],
    ['RQ3', 'Q12 a Q13; srovnání segmentů v AIA zatím není.'], ['RQ4', 'Q15 a Q16.'], ['RQ5', 'Sada 1 přes Sociomapu.'], ['D1', 'Rozhodnutí o komunikační prioritě 2027.'],
  ];
  ['Út 6. 10.', 'St 7. 10.', 'Čt 8. 10.'].forEach((day, di) => {
    s.messages.push(msg('divider', day, '9:00', 13, { text: day }));
    topics.forEach(([k, a], i) => {
      if ((i + di) % 2) return;
      const at = (9 + Math.floor(i / 3)) + ':' + String((i * 7) % 60).padStart(2, '0');
      s.messages.push(msg('user', day, at, 13, { text: 'Co přesně měří ' + k + '?' }));
      s.messages.push(msg('lead', day, at, 13, { blocks: [P(a)], historical: k.startsWith('Q') ? 'Platilo pro revizi 13' : undefined }));
    });
  });

  s.messages.push(msg('divider', d3, '13:20', 13, { text: d3 }));
  s.messages.push(msg('user', d3, '13:20', 13, { text: 'Vygeneruj dotazník podle návrhu.' }));
  act(s, { type: 'worker', title: 'Dotazník vygenerován', summary: '14 položek · ≈ 10 min', status: 'done', steps: [{ text: '6 bloků, 1 sledovaná sada (Sada 1)', tone: 'done' }, { text: 'Každá položka navázána na výzkumnou otázku', tone: 'done' }],
    link: { stage: 'questionnaire', label: 'Dotazník' }, details: [['Specialista', 'aia.research.questionnaire_build · prompt v3'], ['Výchozí stav', 'Návrh r13'], ['Volání', '1 + 0'], ['Náklad', '0,27 USD']] }, d3, '13:22');
  act(s, { type: 'compute', title: 'Pokrytí výzkumných otázek přepočteno', summary: 'RQ1, RQ4, RQ5 pokryty · RQ2 částečně · RQ3 bez srovnání', status: 'done', steps: [], link: { stage: 'design', label: 'Pokrytí' }, details: [['Výpočet', 'research_trace · deterministický'], ['Vstup', 'Dotazník r13 (pracovní)']] }, d3, '13:22');
  s.revision = 14;
  s.messages.push(msg('notice', d3, '14:05', 14, { text: 'Revize 14 přijata vámi · Dotazník', tone: 'done' }));

  s.messages.push(msg('divider', d4, '16:30', 14, { text: d4 }));
  const more: [string, string][] = [
    ['Které otázky měří RQ2?', 'Q8 (zvažování), Q9 (důvod, otevřená) a Q10 (cílová banka).'],
    ['Je Sada 1 dost velká pro mapu?', 'Pro 8 bank ano; podporu dvojic ale ověří až výsledná data. Raiffeisenbank zná málo lidí, odhad Kish n ≈ 28.'],
    ['Ukaž mi kontrolu pozornosti.', 'Q19 v bloku Povědomí; je chráněná.'],
  ];
  more.forEach(([q, a], i) => {
    s.messages.push(msg('user', d4, '16:' + (31 + i * 4), 14, { text: q }));
    s.messages.push(msg('lead', d4, '16:' + (32 + i * 4), 14, { blocks: [P(a)], links: i === 2 ? [{ stage: 'questionnaire', focus: 'Q19', label: 'Dotazník · Q19' }] : undefined }));
  });
}

// ------------------------------------------------------------ phase seeds
export function seedDesign(): AppState {
  const s = baseState();
  history(s);
  s.revision = 14;
  s.day = 'St 14. 10.';
  s.messages.push(msg('divider', s.day, '9:40', 14, { text: s.day }));
  return s;
}

function acceptedOps(rev: number, ops: AppliedOp['op'][], title: string): AppliedOp[] {
  return ops.map((op) => ({ id: id('op'), actor: 'worker', at: '—', op, note: 'r' + rev + ' · ' + title }));
}

export function seedExecution(): AppState {
  const s = seedDesign();
  const q = questionnaireOptimisation(14);
  s.accepted.questionnaire = acceptedOps(15, q.changes.filter((c) => c.op).map((c) => c.op!), q.title);
  s.proposals.push({ ...q, id: id('pr'), status: 'accepted', createdAt: '9:48' });
  const a = audienceEvidence(15);
  s.accepted.audience = acceptedOps(16, a.changes.map((c) => c.op!), a.title);
  s.proposals.push({ ...a, id: id('pr'), status: 'accepted', createdAt: '10:20' });
  s.evidenceAttached['ass.A1'] = ['S1']; s.evidenceAttached['ass.A2'] = ['S2']; s.evidenceAttached['ass.A3'] = ['S3'];
  s.research.push({ id: 'DR-41', purpose: 'DESIGN_RESEARCH', target: 'Předpoklady A1–A3 · revize 15', targetRef: 'audience.ass', status: 'done', step: 6, sources: 14, admitted: 3, quarantined: 2, noEvidence: 1, spent: 0.42, findings: ['S1', 'S2', 'S3'] });
  s.budget.studySpent = 3.12 + 0.21 + 0.42;
  s.messages.push(msg('notice', s.day, '9:52', 15, { text: 'Revize 15 přijata vámi · Optimalizace dotazníku (7 změn)', tone: 'done' }));
  s.messages.push(msg('notice', s.day, '10:22', 16, { text: 'Revize 16 přijata vámi · Evidence k předpokladům A1–A3', tone: 'done' }));
  s.revision = 16;
  s.stage = 'fieldwork';
  s.run = { ...s.run, id: 'RUN-16A', revision: 16, status: 'ready' };
  return s;
}

export function seedEvidence(): AppState {
  const s = seedExecution();
  const day = 'Čt 15. 10.';
  s.messages.push(msg('user', s.day, '10:30', 16, { text: 'Spusť sběr.' }));
  act(s, { type: 'compute', title: 'Sběr dat dokončen', summary: '400 z 400 · 2 čekání na poskytovatele · 17,86 USD', status: 'done', steps: [{ text: 'Revize 16 zmrazena do běhu RUN-16A', tone: 'done' }, { text: 'Poskytovatel 2× omezil provoz; běh pokračoval sám', tone: 'world' }, { text: '6 respondentů hodnotilo všechny banky stejně · ponecháno (vaše rozhodnutí)', tone: 'done-warn' }],
    link: { stage: 'fieldwork', label: 'Sběr dat' }, details: [['Běh', 'RUN-16A · revize 16'], ['Zdroj', 'ai_runtime · fiktivní roster'], ['Trasa', 'bedrock-eu-primary · ModelGateway'], ['Volání', '400 bloků × 3 = 1 200'], ['Náklad', '17,86 USD z 18,40 USD stropu'], ['Původ dat', 'SYNTHETIC_AI_FICTIONAL']] }, s.day, '11:48');
  s.messages.push(msg('divider', day, '8:30', 16, { text: day }));
  act(s, { type: 'compute', title: 'Výsledky a Sociomapa spočteny', summary: 'Agregace · mapa Stress-1 0,083 · 1 objekt nezmapován', status: 'done', steps: [], link: { stage: 'results', label: 'Výsledky' }, details: [['Kroky', 'aggregate · sociomap (aia-sociomap-3)'], ['Deterministické', 'ano · bez modelu'], ['Artefakty', 'art-agg-16a · art-sm-16a-set1']] }, day, '8:31');
  act(s, { type: 'worker', title: 'Analýza dokončena', summary: '7 z 8 modulů · Segmenty blokovány', status: 'done', steps: [{ text: 'Segmenty: uloženo BLOCKED, 0 volání (srovnání segmentů není v AIA)', tone: 'done-warn' }],
    link: { stage: 'analysis', label: 'Analýza' }, details: [['Specialista', 'aia.analysis.module · 8 modulů'], ['Brána evidence', 'AdmittedClaim; 3 nároky blokovány'], ['Volání', '17 (2 opravy)'], ['Náklad', '1,94 USD']] }, day, '9:05');
  act(s, { type: 'worker', title: 'Koncept zprávy sestaven', summary: '7 oddílů · interní · neschváleno', status: 'done', steps: [], link: { stage: 'report', label: 'Zpráva' }, details: [['Skladatel', 'research_report · po oddílech'], ['Stav', 'DRAFT_UNAPPROVED'], ['Náklad', '0,48 USD']] }, day, '9:20');
  s.day = day;
  s.revision = 16;
  s.run = { ...s.run, status: 'completed', done: 400, spent: 17.86, reserved: 0, elapsed: 4680, waits: 2, constantResponders: 6, decisionOnConstant: 'keep' };
  s.budget.studySpent = 3.75 + 17.86 + 1.94 + 0.48;
  s.analysisState = 'blocked_module';
  s.stage = 'results';
  return s;
}

export function seedReturn(): AppState {
  const s = seedEvidence();
  // While you were away (four days): interpretation research finished, a provider
  // wait recovered, the Lead noticed one stale item.
  s.research.push({ id: 'DR-44', purpose: 'INTERPRETATION_RESEARCH', target: 'Sociomapa · dvojice Fio – Air Bank · RUN-16A', targetRef: 'sociomap.pair.fio~air', status: 'done', step: 6, sources: 9, admitted: 1, quarantined: 1, noEvidence: 0, spent: 0.38, findings: ['S4'] });
  s.evidenceAttached['pair.fio~air'] = ['S4'];
  s.budget.studySpent += 0.38;
  const day = 'Po 19. 10.';
  s.messages.push(msg('divider', 'Čt 15. 10.', '17:10', 16, { text: 'Čt 15. 10. · později' }));
  s.messages.push(msg('activity', 'Čt 15. 10.', '17:10', 16, { activityId: (() => { const aid = id('act'); s.activities.push({ id: aid, type: 'research', title: 'Kontext k dvojici Fio – Air Bank', summary: '1 zjištění připojeno k mapě · mapa beze změny', status: 'done', startedAt: 0, steps: [{ text: 'Poskytovatel vyhledávání 1× nedostupný; krok obnoven bez opakované platby', tone: 'recovery' }], link: { stage: 'sociomap', focus: 'fio~air', label: 'Sociomapa · Fio – Air Bank' }, details: [['Účel', 'INTERPRETATION_RESEARCH'], ['Cíl', 'pair fio~air · art-sm-16a-set1 (sha256 zmrazen)'], ['Trasa', 'Brave · třída C'], ['Náklad', '0,38 USD']] }); return aid; })() }));
  s.day = day;
  s.returnFrom = 'Čt 15. 10.';
  s.lastSeenMsg = s.messages[s.messages.length - 2]?.id;
  s.messages.push(msg('divider', day, '8:55', 16, { text: 'Vítejte zpět · ' + day }));
  s.messages.push(msg('return', day, '8:55', 16, { returnSummary: {
    changed: ['Ke Sociomapě připojen externí kontext k dvojici Fio – Air Bank (DR-44). Mapa se nezměnila.'],
    finished: ['Výzkum DR-44 dokončen (0,38 USD)', 'Koncept zprávy čeká na interní schválení od Čt 15. 10.'],
    attention: ['Zpráva: věta 1.3 tvrdí srovnání, které nemá připuštěný nárok', 'Analýza: Segmenty blokovány; RQ3 zodpovězena jen částečně', 'Otevřené odpovědi Q9 nejsou kódované (navržená schopnost)'],
    next: 'Zkontrolovat větu 1.3 ve Zprávě a pak koncept interně schválit.',
  } }));
  s.stage = 'report';
  return s;
}
