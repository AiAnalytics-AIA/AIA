// The one fixture every scenario and artifact reads. It is a FICTIONAL study:
// "Young Customer Perception 2026" for Fio banka, with invented respondents,
// numbers, quotes and sources. Nothing here is a fact about Fio banka.
//
// Corrections against the V1 exports (brief §18) are marked "§18".
import type { StageId } from './types';

export const STUDY = {
  id: 'study-7f2c',
  client: 'Fio banka',
  clientMono: 'FI',
  clientNote: 'Fiktivní klient a studie pro prototyp',
  name: 'Mladí zákazníci 2026',
  nameEn: 'Young Customer Perception 2026',
  kind: 'Výzkum',
  owner: 'Nigel B.',
  created: '2. 10. 2026',
  population: { id: 'LIVE v17_4_0', read: false },
};

// ---------------------------------------------------------------------------
// Element model. Editable artifacts are sections of items; every edit (yours,
// the Lead's request, a worker's proposal) is an Op over this model.
export interface Item { id: string; [k: string]: unknown }
export interface Section { id: string; title: string; note?: string; locked?: string; items: Item[] }
export interface Doc { sections: Section[] }

// Revision at which each stage's base fixture content was accepted.
export const BASE_REV: Record<StageId, number> = {
  brief: 12, design: 13, questionnaire: 14, audience: 14, dimensions: 14, sample: 14,
  fieldwork: 14, results: 14, sociomap: 14, analysis: 14, report: 14,
};

export const BANKS = ['Fio banka', 'Air Bank', 'Česká spořitelna', 'ČSOB', 'Komerční banka', 'Revolut', 'mBank', 'Raiffeisenbank'];

// ---------------------------------------------------------------- Brief
export const BRIEF: Doc = {
  sections: [
    { id: 'obj', title: 'Cíle', items: [
      { id: 'O1', text: 'Pochopit, jak lidé 18–35 let vnímají Fio banku ve srovnání s dalšími sedmi bankami.' },
      { id: 'O2', text: 'Zjistit, kdo zvažuje změnu hlavní banky, ke které bance a proč.' },
      { id: 'O3', text: 'Podpořit rozhodnutí o komunikační prioritě na rok 2027.' },
    ] },
    { id: 'dec', title: 'Rozhodnutí, která má výzkum podpořit', items: [
      { id: 'D1', text: 'Komunikační priorita 2027: cena, nebo digitální zkušenost?' },
      { id: 'D2', text: 'Oslovovat zvlášť 18–24 a 25–35 let?' },
    ] },
    { id: 'ctx', title: 'Kontext', items: [
      { id: 'C1', text: 'Klient vnímá rostoucí konkurenci neobank mezi mladšími lidmi.' },
      { id: 'C2', text: 'Studie je předběžná; výsledky nejdou ke klientovi bez schválení.' },
    ] },
    { id: 'mat', title: 'Podklady', items: [
      { id: 'M1', text: 'Briefing_Fio_2026.pdf', cls: 'A · důvěrné klienta', note: 'fiktivní' },
      { id: 'M2', text: 'Positioning 2025 (prezentace)', cls: 'A · důvěrné klienta', note: 'fiktivní' },
      { id: 'M3', text: 'Data o složení klientů', cls: '—', note: 'nedodáno' },
    ] },
    { id: 'ass', title: 'Předpoklady', items: [
      { id: 'A1', text: 'Mladí vnímají Fio jako banku spíše pro zkušené investory.' },
      { id: 'A2', text: 'Mladí volí hlavní banku hlavně podle mobilní aplikace.' },
      { id: 'A3', text: 'Klienti Fio jsou v průměru starší než trh.' },
    ] },
  ],
};

// ---------------------------------------------------------------- Design
// §8: every research question carries its coverage chain.
export interface RQ {
  id: string; text: string; decision: string; measures: string[]; items: string[];
  method: string; expected: string; complete: string; gaps: string[]; report: string;
  status: 'covered' | 'partial' | 'gap';
}
export const RQS: RQ[] = [
  { id: 'RQ1', text: 'Jak lidé 18–35 let hodnotí Fio ve srovnání s ostatními bankami?', decision: 'D1', measures: ['Hodnocení 1–10 u 8 bank'], items: ['Set 1'],
    method: 'Průměry s 95% intervaly; pořadí jen kde se intervaly rozcházejí', expected: 'Relativní postavení Fio mezi 8 bankami', complete: 'Každá banka Kish n ≥ 30', gaps: [], report: 'Kap. 3 Klíčová zjištění', status: 'covered' },
  { id: 'RQ2', text: 'Kdo zvažuje změnu hlavní banky, ke které a proč?', decision: 'D1', measures: ['Zvažování změny a cílová banka', 'Důvod změny (otevřená odpověď)'], items: ['Q8', 'Q9', 'Q10'],
    method: 'Podíly s intervaly + kvalitativní rozbor důvodů', expected: 'Které banky a jaké důvody', complete: 'Výběr banky i rozbor důvodů', gaps: ['Kódování otevřených odpovědí v AIA zatím není (navrženo)'], report: 'Kap. 3 a 5', status: 'partial' },
  { id: 'RQ3', text: 'Jakou roli hraje mobilní aplikace a liší se 18–24 od 25–35?', decision: 'D2', measures: ['Hodnocení aplikace 1–10', 'Co je při volbě nejdůležitější'], items: ['Q12', 'Q13'],
    method: 'Průměr s intervalem; srovnání segmentů', expected: 'Váha aplikace; rozdíl mezi věkovými skupinami', complete: 'Srovnání dvou věkových skupin', gaps: ['Srovnání segmentů v AIA zatím není (compare_segments)'], report: 'Kap. 4', status: 'gap' },
  { id: 'RQ4', text: 'Znají mladí Fio a její produkty?', decision: 'D1', measures: ['Znalost banky', 'Znalost produktů Fio'], items: ['Q15', 'Q16'],
    method: 'Podíly s intervaly', expected: 'Znalost značky a produktů zvlášť', complete: 'Oba konstrukty změřeny', gaps: [], report: 'Kap. 3', status: 'covered' },
  { id: 'RQ5', text: 'Které banky se v očích mladých pohybují spolu?', decision: 'D1', measures: ['Hodnocení 1–10 u 8 bank (jako u RQ1)'], items: ['Set 1'],
    method: 'Sociomapa aia-sociomap-3', expected: 'Skupiny bank s podobným pohybem relativních preferencí', complete: 'Mapa s dostatečnou podporou dvojic', gaps: [], report: 'Kap. 4 Sociomapa', status: 'covered' },
];

export const DESIGN: Doc = {
  sections: [
    { id: 'rq', title: 'Výzkumné otázky', items: RQS.map((r) => ({ id: r.id, text: r.text })) },
    { id: 'meth', title: 'Metody', items: [
      { id: 'ME1', text: 'Kvantitativní dotazník, n = 400, fiktivní AI respondenti (prototyp).' },
      { id: 'ME2', text: 'Sociomapa nad sadou hodnocení bank (aia-sociomap-3).' },
      { id: 'ME3', text: 'Kvalitativní rozbor otevřené odpovědi o důvodu změny.' },
    ] },
    { id: 'open', title: 'Nevyřešené volby', items: [
      { id: 'U1', text: 'Srovnání 18–24 vs 25–35: AIA ho zatím neumí. Ponechat otázku, nebo ji přeformulovat?' },
      { id: 'U2', text: 'Kódování otevřených odpovědí: navržená schopnost, ne v produktu.' },
    ] },
  ],
};

// ---------------------------------------------------------------- Questionnaire
// q: wording, type, options, route (shown-if), rq (research questions it measures),
// d: seconds, lock: why an item is protected.
export const QUESTIONNAIRE: Doc = {
  sections: [
    { id: 'b1', title: 'Úvod a výběr', items: [
      { id: 'Q1', q: 'Kolik je vám let?', type: 'number', options: '18–35, jinak konec', d: 20, rq: [] },
      { id: 'Q2', q: 'Která banka je vaše hlavní?', type: 'single', options: BANKS.join(' · ') + ' · jiná', d: 25, rq: [] },
    ] },
    { id: 'b2', title: 'Vztah k bance', items: [
      { id: 'Q5', q: 'Jak dlouho, přibližně v letech, jste klientem své současné hlavní banky, včetně doby, kdy jste měli jen studentský účet?', type: 'single', options: 'méně než 1 · 1–3 · 4–6 · více než 6', d: 45, rq: [] },
      { id: 'Q8', q: 'Zvažujete v příštích 12 měsících změnu hlavní banky?', type: 'single', options: 'Ano · Ne · Nevím', d: 20, rq: ['RQ2'] },
      { id: 'Q9', q: 'Proč zvažujete změnu?', type: 'open', route: 'Q8 = Ano', d: 75, rq: ['RQ2'] },
      { id: 'Q10', q: 'Ke které bance byste nejspíš přešli?', type: 'single', options: BANKS.slice(1).join(' · ') + ' · nevím', route: 'Q8 = Ano', d: 25, rq: ['RQ2'] },
    ] },
    { id: 'set1', title: 'Sada 1 · Hodnocení bank', locked: 'Vstup Sociomapy · chráněno', items: [
      { id: 'Set 1', q: 'Jak moc by vám vyhovovala tato banka? (1 = vůbec, 10 = naprosto)', type: 'set', options: BANKS.join(' · '), d: 150, rq: ['RQ1', 'RQ5'], lock: 'Sociomapa čte tuto sadu. Změna znění, škály nebo objektů vyžaduje novou revizi metodiky mapy.' },
    ] },
    { id: 'b4', title: 'Aplikace', items: [
      { id: 'Q12', q: 'Jak hodnotíte mobilní aplikaci své hlavní banky?', type: 'scale', options: '1–10', d: 20, rq: ['RQ3'] },
      { id: 'Q13', q: 'Seřaďte, co je pro vás při volbě banky nejdůležitější.', type: 'rank', options: 'Poplatky · Aplikace · Pobočky · Úroky · Doporučení známých · Investice', d: 70, rq: ['RQ3'] },
    ] },
    { id: 'b5', title: 'Povědomí', items: [
      { id: 'Q15', q: 'Které z těchto bank znáte alespoň podle jména?', type: 'multi', options: BANKS.join(' · '), d: 45, rq: ['RQ4'] },
      { id: 'Q16', q: 'Které z těchto produktů Fio banky znáte?', type: 'multi', options: 'Spořicí účet · Investiční účet · Hypotéka · Žádný', d: 30, rq: ['RQ4'] },
      { id: 'Q19', q: 'Kontrola pozornosti: vyberte prosím možnost „Souhlasím“.', type: 'single', options: 'Nesouhlasím · Souhlasím · Nevím', d: 15, rq: [], lock: 'Kontrola kvality dat. Neodstraňovat.' },
    ] },
    { id: 'b6', title: 'Demografie', items: [
      { id: 'Q20', q: 'Jaké je vaše nejvyšší dosažené vzdělání?', type: 'single', options: 'ZŠ · SŠ bez maturity · SŠ s maturitou · VŠ', d: 20, rq: [] },
      { id: 'Q21', q: 'Ve kterém kraji žijete?', type: 'single', options: '14 krajů', d: 40, rq: [] },
    ] },
  ],
};

// ---------------------------------------------------------------- Audience
export const AUDIENCE: Doc = {
  sections: [
    { id: 'def', title: 'Definice', items: [
      { id: 'T1', text: 'Obyvatelé ČR ve věku 18–35 let s běžným účtem u banky.' },
    ] },
    { id: 'flt', title: 'Filtry populace', note: 'LIVE v17_4_0 · náhled jen počty', items: [
      { id: 'F1', factor: 'Věk', value: '18–35', count: '2 184 300' },
      { id: 'F2', factor: 'Má běžný účet', value: 'ano', count: '1 962 000' },
    ] },
    { id: 'ass', title: 'Předpoklady o cílové skupině', items: [
      { id: 'A1', text: 'Mladí vnímají Fio jako banku spíše pro zkušené investory.', status: 'k ověření' },
      { id: 'A2', text: 'Mladí volí hlavní banku hlavně podle mobilní aplikace.', status: 'k ověření' },
      { id: 'A3', text: 'Klienti Fio jsou v průměru starší než trh.', status: 'k ověření' },
    ] },
  ],
};

// ---------------------------------------------------------------- Dimensions
export const DIMENSIONS: Doc = {
  sections: [
    { id: 'dim', title: 'Vybrané dimenze', items: [
      { id: 'DM1', name: 'Digitální afinita', def: 'Jak ochotně člověk řeší finance v aplikacích.', source: 'Populace: blok Digitál (pole dig_*)', use: 'RQ3 · persona', topic: 'digital' },
      { id: 'DM2', name: 'Finanční gramotnost', def: 'Sebehodnocení orientace ve financích.', source: 'Populace: blok Finance', use: 'RQ1, RQ4 · persona', topic: 'finance' },
      { id: 'DM3', name: 'Postoj k riziku', def: 'Ochota podstoupit finanční riziko.', source: 'Populace: blok Finance', use: 'RQ4 · persona', topic: 'finance' },
      { id: 'DM4', name: 'Loajalita ke značce', def: 'Sklon zůstávat u jedné značky.', source: '—', use: 'RQ2', topic: null },
    ] },
  ],
};

// ---------------------------------------------------------------- Sample
export const SAMPLE = {
  n: 400,
  quotas: [
    { cell: '18–24 let', share: '40 %', n: 160 },
    { cell: '25–35 let', share: '60 %', n: 240 },
    { cell: 'Žena', share: '49 %', n: 196 },
    { cell: 'Muž', share: '51 %', n: 204 },
    { cell: 'Praha', share: '14 %', n: 56 },
    { cell: 'Ostatní kraje', share: '86 %', n: 344 },
  ],
  constraints: [
    'Kvóty pohlaví × věková skupina × kraj, metoda největších zbytků.',
    'Vzdělání se do kvót přidává až od n 700; zde se nekvótuje.',
    'Kvóty určují složení vzorku, ne podporu dvojic v mapě. Podpora se ověří až z výsledných dat.', // §18
  ],
  forecast: [
    { what: 'Revolut (sada 1): odhad Kish n', value: '≈ 240', verdict: 'ok' },
    { what: 'Raiffeisenbank (sada 1): odhad Kish n', value: '≈ 28', verdict: 'warn' },
    { what: 'Nejmenší postačující n pro všech 8 bank', value: '≈ 430', verdict: 'warn' },
  ],
};

// Readiness: every prerequisite (§18: the summary reflects all of them).
export interface ReadyItem { id: string; text: string; state: 'pass' | 'warn' | 'fail' | 'you'; where: StageId; note?: string }
export function readiness(opts: { questionnaireAccepted: boolean; audienceAccepted: boolean; spendConfirmed: boolean; proposalsPending: number; workingStages: StageId[] }): ReadyItem[] {
  return [
    { id: 'r1', text: 'Návrh výzkumu přijat', state: 'pass', where: 'design' },
    { id: 'r2', text: 'Dotazník přijat bez čekajících návrhů', state: opts.questionnaireAccepted && opts.proposalsPending === 0 ? 'pass' : 'you', where: 'questionnaire', note: opts.proposalsPending ? opts.proposalsPending + ' návrh čeká' : undefined },
    { id: 'r3', text: 'Bez neuložených pracovních úprav', state: opts.workingStages.length ? 'you' : 'pass', where: opts.workingStages[0] ?? 'questionnaire', note: opts.workingStages.length ? 'Pracovní úpravy: ' + opts.workingStages.join(', ') : undefined },
    { id: 'r4', text: 'Cílová skupina a filtry nastaveny', state: opts.audienceAccepted ? 'pass' : 'you', where: 'audience' },
    { id: 'r5', text: 'Populace LIVE zavedena', state: 'pass', where: 'audience', note: 'v17_4_0' },
    { id: 'r6', text: 'Dimenze: 1 nemá téma persony', state: 'warn', where: 'dimensions', note: 'Loajalita ke značce se respondentům nepředá' },
    { id: 'r7', text: 'Odhad podpory: Raiffeisenbank pod n 30', state: 'warn', where: 'sample', note: 'Pokračovat s omezeními je možné' },
    { id: 'r8', text: 'Odpověditelnost: Q13 a Q9 s rizikem', state: 'warn', where: 'sample' },
    { id: 'r9', text: 'Strop běhu 18,40 USD v limitu studie', state: opts.spendConfirmed ? 'pass' : 'pass', where: 'fieldwork', note: 'Potvrzení nutné až od 25 USD' },
  ];
}

// ---------------------------------------------------------------- Results (run r16)
// All values are fictional. Scale items are means on 1–10, never percentages (§18).
export interface Mean { obj: string; mean: number | null; lo: number | null; hi: number | null; n: number; suppressed?: string }
export const SET1: Mean[] = [
  { obj: 'Air Bank', mean: 7.6, lo: 7.3, hi: 7.9, n: 372 },
  { obj: 'Revolut', mean: 7.3, lo: 6.9, hi: 7.7, n: 241 },
  { obj: 'Česká spořitelna', mean: 7.0, lo: 6.7, hi: 7.3, n: 388 },
  { obj: 'Fio banka', mean: 6.8, lo: 6.5, hi: 7.1, n: 356 },
  { obj: 'ČSOB', mean: 6.4, lo: 6.1, hi: 6.7, n: 379 },
  { obj: 'mBank', mean: 6.1, lo: 5.7, hi: 6.5, n: 203 },
  { obj: 'Komerční banka', mean: 5.9, lo: 5.6, hi: 6.2, n: 381 },
  { obj: 'Raiffeisenbank', mean: null, lo: null, hi: null, n: 27, suppressed: 'Kish n 27 < 30' },
];
// §18: Fio's position is the same everywhere: 4th of 7 reported by mean, in a
// group whose intervals overlap (2nd–5th), surely below Air Bank.
export const FIO_RANK = { place: 4, of: 7, rated: 8, group: 'překrývá se s Revolutem, Českou spořitelnou a ČSOB', below: 'Air Bank' };

export interface Share { label: string; pct: number; lo: number; hi: number; n: number; base: string }
export const RESULTS = {
  runId: 'RUN-16A',
  n: 400,
  origin: 'SYNTHETIC_AI_FICTIONAL',
  q8: { label: 'Zvažuje změnu hlavní banky (Q8)', pct: 24, lo: 20, hi: 28, n: 400, base: 'všichni respondenti' } as Share,
  q10: [
    { label: 'Revolut', pct: 34, lo: 25, hi: 44, n: 96, base: 'zvažující změnu' },
    { label: 'Air Bank', pct: 29, lo: 21, hi: 39, n: 96, base: 'zvažující změnu' },
    { label: 'Česká spořitelna', pct: 11, lo: 6, hi: 19, n: 96, base: 'zvažující změnu' },
    { label: 'Fio banka', pct: 9, lo: 5, hi: 17, n: 96, base: 'zvažující změnu' },
    { label: 'Jiná / nevím', pct: 17, lo: 11, hi: 26, n: 96, base: 'zvažující změnu' },
  ] as Share[],
  q12: { label: 'Hodnocení aplikace hlavní banky (Q12)', mean: 7.1, lo: 6.9, hi: 7.3, n: 400 },
  q15: { label: 'Zná Fio banku (Q15)', pct: 81, lo: 77, hi: 85, n: 400, base: 'všichni respondenti' } as Share,
  q16: [
    { label: 'Spořicí účet Fio', pct: 46, lo: 41, hi: 51, n: 400, base: 'všichni respondenti' },
    { label: 'Investiční účet Fio', pct: 38, lo: 33, hi: 43, n: 400, base: 'všichni respondenti' },
    { label: 'Hypotéka Fio', pct: 12, lo: 9, hi: 16, n: 400, base: 'všichni respondenti' },
  ] as Share[],
  q9: {
    answered: 96,
    examples: [
      { id: 'R-031', text: 'Za výběr z bankomatu platím víc než kamarádi.' },
      { id: 'R-118', text: 'Aplikace Revolutu je rychlejší a hezčí.' },
      { id: 'R-207', text: 'Chci jednodušší investování v mobilu.' },
      { id: 'R-266', text: 'Pobočka mi nevadí, ale nechci za ni platit.' },
      { id: 'R-342', text: 'Kamarádi mají všichni jinou banku, posílání je pak složitější.' },
    ],
    // Proposed coding (a worker's proposal, not stored classifications): counts appear only after acceptance.
    themes: [
      { id: 'T1', label: 'Poplatky a cena', proposed: 39 },
      { id: 'T2', label: 'Aplikace a rychlost', proposed: 31 },
      { id: 'T3', label: 'Investování v mobilu', proposed: 14 },
      { id: 'T4', label: 'Sociální důvody', proposed: 9 },
      { id: 'T5', label: 'Nezařaditelné', proposed: 3 },
    ],
  },
  constantResponders: 6,
};

// ---------------------------------------------------------------- Sociomap
// Positions and heights from the frozen contract-3 artifact (fictional values).
// Distance = co-movement of relative preferences; height = mean rating. Height is
// never closeness.
export interface MapObj { id: string; label: string; x: number; y: number; height: number | null; placed: boolean; note?: string }
export const MAP = {
  method: 'aia-sociomap-3',
  spec: 'sha256:9c1e…4f0a',
  artifact: 'art-sm-16a-set1',
  stress: 0.083,
  fit: 'dobrá',
  nPeople: 400,
  notPlaced: 11,
  objects: [
    { id: 'air', label: 'Air Bank', x: 0.30, y: 0.36, height: 7.6, placed: true },
    { id: 'rev', label: 'Revolut', x: 0.18, y: 0.24, height: 7.3, placed: true },
    { id: 'cs', label: 'Česká spořitelna', x: 0.72, y: 0.40, height: 7.0, placed: true },
    { id: 'fio', label: 'Fio banka', x: 0.42, y: 0.54, height: 6.8, placed: true },
    { id: 'csob', label: 'ČSOB', x: 0.78, y: 0.62, height: 6.4, placed: true },
    { id: 'mb', label: 'mBank', x: 0.20, y: 0.66, height: 6.1, placed: true },
    { id: 'kb', label: 'Komerční banka', x: 0.66, y: 0.80, height: 5.9, placed: true },
    { id: 'rb', label: 'Raiffeisenbank', x: 0, y: 0, height: null, placed: false, note: 'Nezmapováno: Kish n 27 < 30' },
  ] as MapObj[],
};
export interface Pair { a: string; b: string; r: number | null; lo: number | null; hi: number | null; n: number; status: 'RELIABLE' | 'WEAK' | 'UNKNOWN'; floor: boolean }
export const PAIRS: Pair[] = [
  { a: 'air', b: 'rev', r: 0.42, lo: 0.31, hi: 0.52, n: 236, status: 'RELIABLE', floor: true },
  { a: 'fio', b: 'air', r: 0.31, lo: 0.21, hi: 0.40, n: 340, status: 'RELIABLE', floor: true },
  { a: 'cs', b: 'kb', r: 0.38, lo: 0.29, hi: 0.47, n: 371, status: 'RELIABLE', floor: true },
  { a: 'cs', b: 'csob', r: 0.29, lo: 0.19, hi: 0.38, n: 366, status: 'RELIABLE', floor: true },
  { a: 'csob', b: 'kb', r: 0.33, lo: 0.24, hi: 0.42, n: 369, status: 'RELIABLE', floor: true },
  { a: 'mb', b: 'rev', r: 0.22, lo: 0.08, hi: 0.35, n: 180, status: 'RELIABLE', floor: true },
  { a: 'fio', b: 'rev', r: 0.12, lo: -0.01, hi: 0.25, n: 224, status: 'WEAK', floor: true },
  { a: 'fio', b: 'cs', r: -0.18, lo: -0.28, hi: -0.08, n: 349, status: 'RELIABLE', floor: true },
  { a: 'fio', b: 'mb', r: 0.08, lo: -0.06, hi: 0.22, n: 190, status: 'WEAK', floor: false },
  { a: 'fio', b: 'csob', r: 0.04, lo: -0.07, hi: 0.15, n: 341, status: 'WEAK', floor: false },
  { a: 'air', b: 'cs', r: -0.09, lo: -0.19, hi: 0.01, n: 362, status: 'WEAK', floor: false },
  { a: 'rb', b: 'fio', r: null, lo: null, hi: null, n: 21, status: 'UNKNOWN', floor: false },
];
export const objLabel = (id: string) => MAP.objects.find((o) => o.id === id)?.label ?? id;
export function findPair(a: string, b: string) { return PAIRS.find((p) => (p.a === a && p.b === b) || (p.a === b && p.b === a)); }

// ---------------------------------------------------------------- Evidence / sources
export type SourceKind = 'client' | 'study' | 'external' | 'respondent' | 'computed';
export interface Source {
  id: string; kind: SourceKind; title: string; where: string; cls: string; grade?: string;
  admission: 'admitted' | 'context' | 'quarantined' | 'refused' | 'not_evidence';
  passage?: string; locator?: string; retrieved?: string; purpose?: string; trigger?: string; provenance: [string, string][];
  fictional: true;
}
export const SOURCES: Source[] = [
  { id: 'S1', kind: 'external', title: 'Banky a mladí 2025 (ilustrativní průzkum)', where: 'fiktivni-zdroj.example/banky-mladi', cls: 'C · veřejné', grade: 'B', admission: 'context',
    passage: '„Mezi lidmi do 30 let je značka Fio spojována s investováním častěji než s běžným účtem.“', locator: 's. 4, odst. 2', retrieved: '14. 10. 2026',
    purpose: 'DESIGN_RESEARCH', trigger: 'Cílová skupina · předpoklad A1 · revize 14', provenance: [['Běh', 'DR-41 · plan→publish'], ['Snímek', 'sha256:51a…e02'], ['Trasa', 'Brave (placená, schválená)'], ['Náklad', '0,42 USD']], fictional: true },
  { id: 'S2', kind: 'external', title: 'Volba banky podle aplikace (ilustrativní článek)', where: 'cs.wikipedia.org (ilustrativní)', cls: 'C · veřejné', grade: 'C', admission: 'context',
    passage: '„Pro uživatele mobilního bankovnictví je kvalita aplikace jedním z hlavních důvodů volby banky.“', locator: 'odd. Uživatelé', retrieved: '14. 10. 2026',
    purpose: 'DESIGN_RESEARCH', trigger: 'Cílová skupina · předpoklad A2 · revize 14', provenance: [['Běh', 'DR-41'], ['Snímek', 'sha256:7d0…19c'], ['Trasa', 'Wikipedie (bez poplatku)'], ['Náklad', '0,00 USD']], fictional: true },
  { id: 'S3', kind: 'client', title: 'Positioning 2025 (prezentace klienta)', where: 'Znalosti klienta · Podklady', cls: 'A · důvěrné klienta', grade: '—', admission: 'context',
    passage: '„Cílíme na sebevědomé uživatele, kteří chtějí mít finance pod kontrolou.“', locator: 'snímek 6', retrieved: 'zmrazeno 14. 10. 2026',
    purpose: 'DESIGN_RESEARCH', trigger: 'Cílová skupina · předpoklad A3 · revize 14', provenance: [['Přístup', 'knowledge_access (jen kód, žádné vyhledávání)'], ['Revize znalosti', 'K-118 r3']], fictional: true },
  { id: 'S4', kind: 'external', title: 'Neobanky a sdílení plateb (ilustrativní)', where: 'fiktivni-zdroj.example/neobanky', cls: 'C · veřejné', grade: 'C', admission: 'context',
    passage: '„Mladí uživatelé často mají účty u dvou bank zároveň: tradiční a digitální.“', locator: 'odst. 5', retrieved: '17. 10. 2026',
    purpose: 'INTERPRETATION_RESEARCH', trigger: 'Sociomapa · dvojice Fio – Air Bank · běh RUN-16A', provenance: [['Běh', 'DR-44'], ['Snímek', 'sha256:a3b…771'], ['Trasa', 'Brave (placená, schválená)'], ['Náklad', '0,38 USD']], fictional: true },
  { id: 'S5', kind: 'respondent', title: 'Otevřené odpovědi Q9 (96)', where: 'Běh RUN-16A · dataset', cls: 'R · data respondentů', admission: 'not_evidence',
    passage: '„Za výběr z bankomatu platím víc než kamarádi.“ (R-031)', locator: 'Q9 · 96 odpovědí', provenance: [['Dataset', 'sha256:e19…c4d'], ['Původ', 'SYNTHETIC_AI_FICTIONAL']], fictional: true },
  { id: 'S6', kind: 'computed', title: 'Agregace sady 1', where: 'Běh RUN-16A · aggregate', cls: 'I · interní', admission: 'admitted',
    passage: 'Fio banka: průměr 6,8 z 10, 95% interval 6,5–7,1, Kish n 356.', locator: 'aggregate · Set 1 · fio', provenance: [['Artefakt', 'art-agg-16a'], ['Specifikace', 'r16 · sha256:2be…0d1'], ['Zaokrouhlení', '1 desetinné místo']], fictional: true },
  { id: 'S7', kind: 'computed', title: 'Sociomapa sady 1', where: 'Běh RUN-16A · sociomap', cls: 'I · interní', admission: 'admitted',
    passage: 'Fio – Air Bank: r 0,31 [0,21; 0,40], n 340, spolehlivá; Stress-1 0,083.', locator: 'art-sm-16a-set1 · pair fio~air', provenance: [['Metoda', 'aia-sociomap-3'], ['Spec', 'sha256:9c1e…4f0a']], fictional: true },
  { id: 'S8', kind: 'study', title: 'Briefing_Fio_2026.pdf', where: 'Studie · podklady zadání', cls: 'A · důvěrné klienta', admission: 'context',
    passage: '„Zajímá nás hlavně skupina do 35 let a jejich důvody odchodu.“', locator: 's. 1', provenance: [['Příloha', 'att-02 · 412 kB']], fictional: true },
];
export const src = (id: string) => SOURCES.find((s) => s.id === id)!;

// ---------------------------------------------------------------- Analysis
export interface Finding {
  id: string; rq: string; register: 'finding' | 'interpretation' | 'context';
  text: string; claims: string[]; sources: string[]; uncertainty?: string; review: 'draft' | 'reviewed';
}
export const FINDINGS: Finding[] = [
  { id: 'F1', rq: 'RQ1', register: 'finding', text: 'Fio banka má průměrné hodnocení 6,8 z 10 [6,5; 7,1], 4. místo ze 7 vykázaných bank. Od Revolutu, České spořitelny a ČSOB ji intervaly neoddělují; pod Air Bank je jistě.', claims: ['C1', 'C2'], sources: ['S6'], uncertainty: 'Pořadí 2.–5. se překrývá.', review: 'draft' },
  { id: 'F2', rq: 'RQ2', register: 'finding', text: 'Změnu hlavní banky zvažuje 24 % [20; 28] respondentů (n 400). Nejčastěji uvádějí Revolut (34 % ze 96) a Air Bank (29 % ze 96).', claims: ['C3', 'C4'], sources: ['S6'], uncertainty: 'Báze 96: široké intervaly.', review: 'draft' },
  { id: 'F3', rq: 'RQ4', register: 'finding', text: 'Fio banku zná 81 % [77; 85]; její investiční účet 38 % [33; 43]. Znalost značky a produktů jsou dva různé konstrukty.', claims: ['C5'], sources: ['S6'], review: 'draft' },
  { id: 'F4', rq: 'RQ5', register: 'interpretation', text: 'Fio leží na mapě blízko Air Bank: kdo si Fio cení relativně víc, cení si relativně víc i Air Bank. Nehodnotí je stejně (6,8 vs 7,6 z 10). Lze to číst jako společný „digitální“ výběr, ale to je výklad, ne měření.', claims: ['C6'], sources: ['S7'], uncertainty: 'Výklad; měřená je jen souvislost relativních preferencí.', review: 'draft' },
  { id: 'F5', rq: 'RQ5', register: 'context', text: 'Externí kontext: mladí mívají dvě banky zároveň, tradiční a digitální (ilustrativní zdroj). Může to vysvětlovat blízkost Fio a Air Bank; mapu to nemění.', claims: [], sources: ['S4'], review: 'draft' },
];
export interface Claim { id: string; text: string; value: string; unit: string; denominator: string; comparison?: string; interval: string; ref: string; source: string; admission: 'admitted' | 'blocked'; reason?: string }
export const CLAIMS: Claim[] = [
  { id: 'C1', text: 'Fio: průměr hodnocení', value: '6,8', unit: 'z 10 (průměr na škále 1–10)', denominator: 'Kish n 356 hodnotících Fio', interval: '95% [6,5; 7,1]', ref: 'aggregate:Set1:fio', source: 'S6', admission: 'admitted' },
  { id: 'C2', text: 'Fio: pořadí', value: '4. ze 7', unit: 'pořadí podle průměru', denominator: '7 vykázaných bank (Raiffeisenbank potlačena)', comparison: 'oddělena jen od Air Bank', interval: 'překryv 2.–5.', ref: 'aggregate:Set1:rank', source: 'S6', admission: 'admitted' },
  { id: 'C3', text: 'Zvažuje změnu', value: '24', unit: '% respondentů', denominator: 'n 400, všichni', interval: '95% [20; 28]', ref: 'aggregate:Q8:ano', source: 'S6', admission: 'admitted' },
  { id: 'C4', text: 'Cílová banka Revolut', value: '34', unit: '% zvažujících', denominator: 'n 96 zvažujících změnu', interval: '95% [25; 44]', ref: 'aggregate:Q10:revolut', source: 'S6', admission: 'admitted' },
  { id: 'C5', text: 'Znalost investičního účtu Fio', value: '38', unit: '% respondentů', denominator: 'n 400', interval: '95% [33; 43]', ref: 'aggregate:Q16:invest', source: 'S6', admission: 'admitted' },
  { id: 'C6', text: 'Vztah Fio – Air Bank', value: '0,31', unit: 'r (min-max přeškálovaná hodnocení)', denominator: 'n 340 hodnotících obě', interval: '95% [0,21; 0,40]', ref: 'sociomap:set1:fio~air', source: 'S7', admission: 'admitted' },
  { id: 'C7', text: 'Mladší (18–24) hodnotí Fio hůř než 25–35', value: '—', unit: '—', denominator: '—', interval: '—', ref: 'segments:age', source: 'S6', admission: 'blocked', reason: 'Srovnání segmentů není v AIA (compare_segments); číslo nebylo připuštěno.' },
  { id: 'C8', text: 'Mladí považují Fio za banku pro investory', value: '—', unit: '—', denominator: '—', interval: '—', ref: '—', source: 'S1', admission: 'blocked', reason: 'Nic ve studii to neměří; externí zdroj je kontext, ne důkaz od respondentů.' },
  { id: 'C9', text: 'Populace je kalibrovaná na ČR 18–35', value: '—', unit: '—', denominator: '—', interval: '—', ref: 'run:population', source: 'S6', admission: 'blocked', reason: 'Běh má fiktivní respondenty; populace nebyla načtena (read_by_fieldwork: ne).' }, // §18
];
export const claim = (id: string) => CLAIMS.find((c) => c.id === id)!;

export const MODULES = [
  { id: 'executive', label: 'Shrnutí', state: 'done' },
  { id: 'research_questions', label: 'Výzkumné otázky', state: 'done' },
  { id: 'objects', label: 'Objekty (banky)', state: 'done' },
  { id: 'audience', label: 'Cílová skupina', state: 'done' },
  { id: 'segments', label: 'Segmenty', state: 'blocked', note: 'Srovnání segmentů není v AIA; modul uložen BLOCKED s 0 voláními.' },
  { id: 'hypotheses', label: 'Hypotézy', state: 'done' },
  { id: 'implications', label: 'Důsledky', state: 'done' },
  { id: 'limitations', label: 'Omezení', state: 'done' },
] as { id: string; label: string; state: 'done' | 'blocked' | 'failed'; note?: string }[];

// ---------------------------------------------------------------- Report
export const REPORT: Doc = {
  sections: [
    { id: 'r1', title: '1 Shrnutí a rozhodnutí', items: [
      { id: 'P1', text: 'Fio banka dosahuje mezi lidmi 18–35 let průměrného hodnocení 6,8 z 10 (95% interval 6,5–7,1) a je čtvrtá ze sedmi vykázaných bank; od Revolutu, České spořitelny a ČSOB ji intervaly statisticky neoddělují.', refs: ['C1', 'C2'] },
      { id: 'P2', text: 'Změnu hlavní banky zvažuje čtvrtina respondentů (24 %, 20–28 %); jako cíl nejčastěji uvádějí Revolut a Air Bank.', refs: ['C3', 'C4'] },
      { id: 'P3', text: 'Pro rozhodnutí D1 výsledky naznačují, že digitální zkušenost je pro tuto skupinu stejně důležitá jako cena; srovnání věkových skupin (D2) tato studie neumožnila.', refs: [] },
    ] },
    { id: 'r2', title: '2 Cíle a odpovědi na výzkumné otázky', items: [
      { id: 'P4', text: 'RQ1, RQ4 a RQ5 jsou zodpovězeny. RQ2 je zodpovězena výběrem banky; důvody jsou zatím jen jako příklady, ne kódované. RQ3 zodpovězena jen částečně (bez srovnání segmentů).', refs: [] },
    ] },
    { id: 'r3', title: '3 Klíčová zjištění', items: [
      { id: 'P5', text: 'Znalost značky (81 %) je výrazně vyšší než znalost investičního účtu Fio (38 %).', refs: ['C5'] },
      { id: 'P6', text: 'Hodnocení aplikace hlavní banky je v průměru 7,1 z 10 (6,9–7,3).', refs: [] },
    ] },
    { id: 'r4', title: '4 Sociomapa', items: [
      { id: 'P7', text: 'Na mapě (Stress-1 0,083, dobrá shoda) leží Fio blízko Air Bank: relativní preference obou bank se u respondentů pohybují spolu (r 0,31). Neznamená to stejné hodnocení.', refs: ['C6'] },
    ] },
    { id: 'r5', title: '5 Interpretace a doporučení', items: [
      { id: 'P8', text: 'Doporučujeme ověřit, zda Fio a Air Bank sdílejí stejné „digitální“ publikum, kvalitativním navazujícím šetřením.', refs: [] },
    ] },
    { id: 'r6', title: '6 Metodika a omezení', items: [
      { id: 'P9', text: 'Respondenti jsou fiktivní AI respondenti (n 400). Populace nebyla načtena; výsledky nepopisují skutečnou populaci ČR. Raiffeisenbank je potlačena pro nízkou podporu (Kish n 27).', refs: ['C9'] }, // §18
    ] },
    { id: 'r7', title: 'Příloha A · Evidence', items: [
      { id: 'P10', text: 'Tabulky otázek, intervaly, báze a odkazy na artefakty běhu RUN-16A.', refs: [] },
    ] },
  ],
};

// ---------------------------------------------------------------- AI Interaction Contract (§14)
export interface Contract { readable: string[]; visual: string[]; domain: string[]; revision: string; refusals: string[] }
export const CONTRACTS: Record<StageId, Contract> = {
  brief: { readable: ['cíle, rozhodnutí, kontext, podklady (třída), předpoklady'], visual: ['open(brief)', 'focus(item)'], domain: ['propose(brief, ops)', 'working.save', 'working.accept → revize'], revision: 'pracovní verze nad přijatou revizí', refusals: ['důvěrný podklad nelze poslat do veřejného vyhledávání'] },
  design: { readable: ['výzkumné otázky + řetěz pokrytí', 'metody', 'nevyřešené volby'], visual: ['focus(RQ)', 'open coverage row'], domain: ['propose(design, ops)', 'research.request(DESIGN_RESEARCH, design_revision)'], revision: 'Design Revision (neměnná)', refusals: ['metodickou volbu neuzavírá AI'] },
  questionnaire: { readable: ['bloky, otázky, větvení, sady, pokrytí RQ, délka'], visual: ['focus(Q)', 'show diff'], domain: ['worker.questionnaire_optimize', 'propose(questionnaire, ops)', 'proposal.accept (člověk)'], revision: 'návrh nese baseRev; zastaralý je odmítnut', refusals: ['Sada 1 a Q19 jsou chráněné', 'přijetí návrhu jen člověk (APPROVE_GATE)'] },
  audience: { readable: ['definice, filtry (počty), předpoklady + připojené zdroje'], visual: ['focus(assumption)', 'open source'], domain: ['audience.preview (počty)', 'research.request(DESIGN_RESEARCH, assumption)'], revision: 'revize studie', refusals: ['náhled vrací jen počty, žádné řádky', 'externí zjištění nemění předpoklad samo'] },
  dimensions: { readable: ['dimenze, definice, zdroj v populaci, použití'], visual: ['focus(dimension)'], domain: ['propose(dimensions, ops)'], revision: 'revize studie', refusals: ['pole použije jen to, co dovolí politika pole (decide)'] },
  sample: { readable: ['n, kvóty, omezení, odhad podpory, připravenost'], visual: ['open readiness item'], domain: ['readiness.check', 'outlook'], revision: 'revize studie', refusals: ['kvóta nezaručuje podporu dvojic'] },
  fieldwork: { readable: ['běh, kroky, průběh, náklady, čekání, kvalita'], visual: ['open step'], domain: ['run.start (člověk)', 'run.cancel', 'budget.lift (člověk)'], revision: 'běh zmrazí revizi; pozdější úpravy nepřebírá', refusals: ['náhradu respondentů AIA nemá (navrženo)', 'nad limit potvrzení jen člověk'] },
  results: { readable: ['agregace, intervaly, báze, potlačení, původ'], visual: ['focus(measure)', 'open claim'], domain: ['— (jen čtení)'], revision: 'zmrazený běh', refusals: ['potlačené číslo se neukáže ani AI'] },
  sociomap: { readable: ['objekty, výšky, dvojice (r, n, interval, stav), shoda'], visual: ['select(object)', 'select(pair)', 'view.filter (jen zobrazení)'], domain: ['research.request(INTERPRETATION_RESEARCH, pair)', 'methodology.version (správce)'], revision: 'zmrazený artefakt mapy', refusals: ['filtr zobrazení nemění výpočet', 'externí kontext do výpočtu nevstupuje'] },
  analysis: { readable: ['moduly, zjištění, nároky, blokované nároky, pokrytí RQ'], visual: ['open finding', 'open claim'], domain: ['analysis.retry (člověk)', 'propose(coding) (navrženo)'], revision: 'běh + harness', refusals: ['číslo jen jako AdmittedClaim', 'AI neschvaluje vlastní tvrzení'] },
  report: { readable: ['oddíly, odstavce, odkazy na nároky, stav revize'], visual: ['focus(section)', 'show tracked changes'], domain: ['propose(report, ops)', 'evidence.check(sentence)', 'report.approve (člověk)'], revision: 'koncept DRAFT_UNAPPROVED', refusals: ['klientská zpráva fiktivního běhu odmítnuta', 'schválení jen člověk'] },
};

// ---------------------------------------------------------------- Deep Research envelope
export const ENVELOPE = {
  policy: 'Výzkum studie · schváleno organizací 2. 10. 2026',
  purposes: ['DESIGN_RESEARCH (před zmrazením metodiky; jen navrhuje)', 'INTERPRETATION_RESEARCH (nad zmrazenými výsledky; nic nemění)'],
  routes: ['Wikipedie CZ/EN · bez poplatku · třída C', 'Brave · placená · třída C · schváleno'],
  perRun: 5,
  classes: 'Do veřejného vyhledávání jen dotazy třídy C. Dotaz odvozený z důvěrného materiálu dědí jeho třídu.',
  notAllowed: ['data respondentů do vyhledávání', 'důvěrné podklady klienta do vyhledávání (ani parafrází)', 'Common Crawl (neschváleno)'],
};

export const ENTRY_STUDIES = [
  { id: 'study-7f2c', name: 'Mladí zákazníci 2026', kind: 'Výzkum', stage: 'Dotazník', attention: '1 návrh čeká na vás', latest: 'Dotazník posouzen · 7 změn navrženo', when: 'dnes 9:42', open: true },
  { id: 'study-3a10', name: 'Bankovní aplikace Q3', kind: 'Výzkum', stage: 'Zpráva', attention: 'Zpráva čeká na schválení', latest: 'Koncept zprávy sestaven', when: '12. 10.', open: false },
  { id: 'study-91bd', name: 'Kampaň Spoření 2027', kind: 'Simulace', stage: 'Návrh', attention: '—', latest: 'Varianta B přidána', when: '3. 10.', open: false },
];
