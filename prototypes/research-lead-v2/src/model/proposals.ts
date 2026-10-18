// The proposals specialists prepare, as data. Each change carries the exact op
// it would apply; nothing applies until a person accepts the proposal.
import type { Change, Proposal } from './types';
import { BANKS } from './fixture';

type Draft = Omit<Proposal, 'id' | 'status' | 'createdAt'>;

// §18: Q9 (open reason) is kept and re-routed, not dropped; Q16 is kept as a
// separate construct; Set 1 and Q19 are protected and untouched.
export function questionnaireOptimisation(baseRev: number, opts: { q5DoneByYou?: boolean } = {}): Draft {
  const changes: Change[] = [];
  if (!opts.q5DoneByYou) changes.push({ id: 'c1', target: 'b2.Q5', label: 'Q5', kind: 'modify',
    from: 'Jak dlouho, přibližně v letech, jste klientem své současné hlavní banky, včetně doby, kdy jste měli jen studentský účet?',
    to: 'Jak dlouho jste klientem své hlavní banky?', why: 'Kratší znění; „včetně studentského účtu“ přesunuto do nápovědy. Měří totéž.',
    op: { op: 'set', sec: 'b2', item: 'Q5', field: 'q', value: 'Jak dlouho jste klientem své hlavní banky?' } });
  changes.push(
    { id: 'c2', target: 'b2.Q8', label: 'Q8 + Q10', kind: 'merge',
      from: 'Q8 Ano · Ne · Nevím  +  Q10 Ke které bance byste přešli?',
      to: 'Q8 Zvažujete změnu hlavní banky? Ne · Nevím · Ano, k: Air Bank · … · Revolut · jiné · nevím ke které',
      why: 'Jedna otázka místo dvou. Ponechává výběr cílové banky pro RQ2.',
      op: { op: 'set', sec: 'b2', item: 'Q8', field: 'options', value: 'Ne · Nevím · Ano, k: ' + BANKS.slice(1).join(' · ') + ' · jiné · nevím ke které' } },
    { id: 'c3', target: 'b2.Q10', label: 'Q10', kind: 'remove', from: 'Ke které bance byste nejspíš přešli?', why: 'Obsah je nyní v Q8.',
      op: { op: 'remove', sec: 'b2', item: 'Q10' } },
    { id: 'c4', target: 'b2.Q9', label: 'Q9 (otevřený důvod)', kind: 'route', from: 'zobrazit, pokud Q8 = Ano', to: 'zobrazit, pokud Q8 = Ano (kterákoli banka)',
      why: 'Důvod změny zůstává jako samostatná otevřená otázka hned po Q8. RQ2 („proč“) jinak nelze zodpovědět.',
      op: { op: 'set', sec: 'b2', item: 'Q9', field: 'route', value: 'Q8 = Ano (kterákoli banka)' } },
    { id: 'c5', target: 'b4.Q13', label: 'Q13', kind: 'modify', from: 'Seřaďte všech 6 možností', to: 'Vyberte 3 nejdůležitější', why: 'Úplné řazení šesti položek je nejdelší úloha dotazníku.',
      op: { op: 'set', sec: 'b4', item: 'Q13', field: 'q', value: 'Vyberte tři věci, které jsou pro vás při volbě banky nejdůležitější.' } },
    { id: 'c6', target: 'b4.Q12', label: 'Q12', kind: 'modify', from: '1–10', to: '1 = velmi špatná … 10 = vynikající · nemám aplikaci', why: 'Popsané krajní body a únik pro lidi bez aplikace.',
      op: { op: 'set', sec: 'b4', item: 'Q12', field: 'options', value: '1 = velmi špatná … 10 = vynikající · nemám aplikaci' } },
    { id: 'c7', target: 'b6.Q20', label: 'Q20', kind: 'modify', from: 'ZŠ · SŠ bez maturity · SŠ s maturitou · VŠ', to: 'ZŠ · SŠ bez maturity · SŠ s maturitou · VOŠ · VŠ', why: 'Chyběla vyšší odborná škola.',
      op: { op: 'set', sec: 'b6', item: 'Q20', field: 'options', value: 'ZŠ · SŠ bez maturity · SŠ s maturitou · VOŠ · VŠ' } },
    { id: 'k1', target: 'b5.Q16', label: 'Q16', kind: 'keep', why: 'Ponecháno. Znalost produktů Fio je jiný konstrukt než znalost banky (Q15); RQ4 potřebuje obojí.' },
    { id: 'k2', target: 'set1.Set 1', label: 'Sada 1', kind: 'keep', why: 'Chráněno: vstup Sociomapy. Beze změny.' },
    { id: 'k3', target: 'b5.Q19', label: 'Q19', kind: 'keep', why: 'Chráněno: kontrola kvality dat.' },
  );
  // Duration effects are applied with the wording changes.
  const dur: Change[] = [
    { id: 'd1', target: 'b2.Q5', label: 'Q5 délka', kind: 'modify', why: '', op: { op: 'set', sec: 'b2', item: 'Q5', field: 'd', value: 15 } },
    { id: 'd2', target: 'b2.Q8', label: 'Q8 délka', kind: 'modify', why: '', op: { op: 'set', sec: 'b2', item: 'Q8', field: 'd', value: 30 } },
    { id: 'd3', target: 'b4.Q13', label: 'Q13 délka', kind: 'modify', why: '', op: { op: 'set', sec: 'b4', item: 'Q13', field: 'd', value: 25 } },
  ].filter((c) => !(opts.q5DoneByYou && c.id === 'd1')) as Change[];
  return {
    stage: 'questionnaire', kind: 'design',
    title: opts.q5DoneByYou ? 'Optimalizace dotazníku (sestaveno znovu)' : 'Optimalizace dotazníku',
    author: 'Specialista dotazníku · aia.research.questionnaire_optimize',
    baseRev, baseLabel: 'Revize ' + baseRev,
    changes: [...changes, ...dur],
    implications: [
      opts.q5DoneByYou ? 'Délka ≈ 10 → 9 min (Q5 už zkrácena vámi; její odhad času se nemění).' : 'Délka ≈ 10 → 8½ min.',
      'Q13 se mění z úplného pořadí na výběr tří: RQ3 neodpoví na pořadí míst 4–6.',
      'Větvení: Q9 se zobrazí po Q8 = Ano; Q10 zaniká.',
      'Sada 1 beze změny: Sociomapa a její specifikace se nemění.',
    ],
    coverage: {
      gained: ['RQ2: výběr cílové banky přímo v Q8 (méně přerušení mezi Q8 a Q10)'],
      lost: ['RQ3: pořadí míst 4–6 u Q13 se už neměří'],
      kept: ['RQ1, RQ5: Sada 1 beze změny', 'RQ2: důvod změny (Q9) zůstává', 'RQ4: Q16 zůstává vedle Q15'],
    },
    impact: [
      { stage: 'sample', effect: 'Odpověditelnost Q13 se přepočítá při kontrole připravenosti' },
      { stage: 'fieldwork', effect: 'Běh použije novou revizi; žádný běh zatím neproběhl' },
    ],
    recompute: 'Ne. Zatím žádné výsledky; readiness se přepočte sama.',
    cost: '0,21 USD (již utraceno při přípravě návrhu)',
  };
}

export function audienceEvidence(baseRev: number): Draft {
  return {
    stage: 'audience', kind: 'annotation',
    title: 'Evidence k předpokladům A1–A3',
    author: 'Hloubkový výzkum · DESIGN_RESEARCH · DR-41',
    baseRev, baseLabel: 'Revize ' + baseRev,
    changes: [
      { id: 'e1', target: 'ass.A1', label: 'A1', kind: 'modify', from: 'k ověření', to: 'částečně podpořeno externím kontextem', why: 'S1: značka spojována s investováním. Nejde o měření u respondentů.',
        op: { op: 'set', sec: 'ass', item: 'A1', field: 'status', value: 'částečně podpořeno externím kontextem' } },
      { id: 'e2', target: 'ass.A2', label: 'A2', kind: 'modify', from: 'k ověření', to: 'podpořeno externím kontextem', why: 'S2: aplikace mezi hlavními důvody volby. Studie to změří v Q13.',
        op: { op: 'set', sec: 'ass', item: 'A2', field: 'status', value: 'podpořeno externím kontextem' } },
      { id: 'e3', target: 'ass.A3', label: 'A3', kind: 'modify', from: 'k ověření', to: 'nepodloženo dostupnými zdroji', why: 'S3 popisuje komu se značka chce líbit (positioning), ne kdo jsou skuteční klienti. Data o složení klientů nebyla dodána. Předpoklad tím není vyvrácen.', // §18
        op: { op: 'set', sec: 'ass', item: 'A3', field: 'status', value: 'nepodloženo dostupnými zdroji' } },
    ],
    implications: ['Mění jen stav předpokladů. Definice cílové skupiny ani filtry se nemění.', 'Externí zdroje jsou kontext pro návrh, ne důkaz od respondentů.'],
    impact: [{ stage: 'design', effect: 'RQ1 a RQ3 mohou předpoklady A1, A2 ověřit měřením' }],
    recompute: 'Ne.',
    cost: '0,42 USD (výzkum DR-41)',
  };
}

export function reportLessTechnical(baseRev: number): Draft {
  return {
    stage: 'report', kind: 'presentation',
    title: 'Méně technické shrnutí',
    author: 'Skladatel zprávy · aia.report.revise (oddíl 1)',
    baseRev, baseLabel: 'Koncept ' + baseRev,
    changes: [
      { id: 't1', target: 'r1.P1', label: 'Odstavec 1.1', kind: 'modify',
        from: 'Fio banka dosahuje mezi lidmi 18–35 let průměrného hodnocení 6,8 z 10 (95% interval 6,5–7,1) a je čtvrtá ze sedmi vykázaných bank; od Revolutu, České spořitelny a ČSOB ji intervaly statisticky neoddělují.',
        to: 'Lidé ve věku 18–35 let hodnotí Fio banku v průměru 6,8 bodu z 10 (6,5–7,1). Je čtvrtá ze sedmi bank, ale od Revolutu, České spořitelny a ČSOB ji výzkum spolehlivě odlišit nedokáže.',
        why: 'Bez „95% interval“ a „statisticky“; jednotka, báze, interval i srovnání zachovány.',
        op: { op: 'set', sec: 'r1', item: 'P1', field: 'text', value: 'Lidé ve věku 18–35 let hodnotí Fio banku v průměru 6,8 bodu z 10 (6,5–7,1). Je čtvrtá ze sedmi bank, ale od Revolutu, České spořitelny a ČSOB ji výzkum spolehlivě odlišit nedokáže.' } },
      { id: 't2', target: 'r1.P2', label: 'Odstavec 1.2', kind: 'modify',
        from: 'Změnu hlavní banky zvažuje čtvrtina respondentů (24 %, 20–28 %); jako cíl nejčastěji uvádějí Revolut a Air Bank.',
        to: 'Zhruba každý čtvrtý (24 %, 20–28 %) zvažuje přechod k jiné bance, nejčastěji k Revolutu nebo Air Bank.',
        why: 'Kratší věta; podíl, interval a báze (všichni respondenti) zachovány.',
        op: { op: 'set', sec: 'r1', item: 'P2', field: 'text', value: 'Zhruba každý čtvrtý (24 %, 20–28 %) zvažuje přechod k jiné bance, nejčastěji k Revolutu nebo Air Bank.' } },
    ],
    implications: ['Odkazy C1–C4 zůstávají u stejných čísel.', 'Kontrola evidence: jednotky, báze, intervaly a srovnání beze změny.'],
    impact: [{ stage: 'report', effect: 'Koncept znovu čeká na interní schválení' }],
    recompute: 'Ne. Mění se jen text.',
    cost: '0,06 USD',
  };
}

export function reportOverstate(baseRev: number): Draft {
  return {
    stage: 'report', kind: 'presentation',
    title: 'Oprava přehánějící věty 1.3',
    author: 'Kontrola evidence · aia.report.claim_check',
    baseRev, baseLabel: 'Koncept ' + baseRev,
    changes: [
      { id: 'o1', target: 'r1.P3', label: 'Odstavec 1.3', kind: 'modify',
        from: 'Pro rozhodnutí D1 výsledky naznačují, že digitální zkušenost je pro tuto skupinu stejně důležitá jako cena; srovnání věkových skupin (D2) tato studie neumožnila.',
        to: 'K rozhodnutí D1 studie zatím nemá připuštěné srovnání ceny a digitální zkušenosti (výsledky Q13 čekají na analýzu). Srovnání věkových skupin (D2) tato studie neumožnila.',
        why: 'Věta tvrdí srovnání, které žádný připuštěný nárok nepodporuje.',
        op: { op: 'set', sec: 'r1', item: 'P3', field: 'text', value: 'K rozhodnutí D1 studie zatím nemá připuštěné srovnání ceny a digitální zkušenosti (výsledky Q13 čekají na analýzu). Srovnání věkových skupin (D2) tato studie neumožnila.' } },
    ],
    implications: ['Shrnutí přestane tvrdit nepodložené srovnání.'],
    impact: [{ stage: 'analysis', effect: 'Doporučeno doplnit analýzu Q13 (modul Výzkumné otázky)' }],
    recompute: 'Ne.',
  };
}

export function reportSociomapEmphasis(baseRev: number): Draft {
  return {
    stage: 'report', kind: 'presentation',
    title: 'Více prostoru pro Sociomapu',
    author: 'Skladatel zprávy · aia.report.revise (oddíl 1)',
    baseRev, baseLabel: 'Koncept ' + baseRev,
    changes: [
      { id: 's1', target: 'r1.P1b', label: 'Nový odstavec 1.2', kind: 'add',
        to: 'Mapa vztahů ukazuje dvě skupiny: digitální banky (Air Bank, Revolut, mBank) a tradiční banky (Česká spořitelna, ČSOB, Komerční banka). Fio leží blíž digitální skupině, nejblíže Air Bank (viz kap. 4, obr. 4.1).',
        why: 'Shrnutí odkáže na mapu. Vztah zůstává „pohyb relativních preferencí“, ne stejné hodnocení.',
        op: { op: 'add', sec: 'r1', after: 'P1', item: { id: 'P1b', text: 'Mapa vztahů ukazuje dvě skupiny: digitální banky (Air Bank, Revolut, mBank) a tradiční banky (Česká spořitelna, ČSOB, Komerční banka). Fio leží blíž digitální skupině, nejblíže Air Bank (viz kap. 4, obr. 4.1).', refs: ['C6'] } } },
    ],
    implications: ['Skupiny jsou čtení mapy (interpretace), ne nový výpočet.', 'Mapa je interní: fiktivní běh.'],
    impact: [],
    recompute: 'Ne.',
  };
}

export function reportSwap(baseRev: number): Draft {
  return {
    stage: 'report', kind: 'presentation', title: 'Zvažování změny jako první zjištění',
    author: 'Skladatel zprávy · aia.report.revise', baseRev, baseLabel: 'Koncept ' + baseRev,
    changes: [{ id: 'w1', target: 'r1.P2', label: 'Odstavec 1.2 → 1.1', kind: 'modify', from: 'pořadí 2', to: 'pořadí 1', why: 'Zjištění o zvažování změny se týká celé skupiny 18–35.', op: { op: 'move', sec: 'r1', item: 'P2', dir: -1 } }],
    implications: ['Mění se jen pořadí odstavců.'], impact: [], recompute: 'Ne.',
  };
}

export function codingProposal(): Draft {
  return {
    stage: 'analysis', kind: 'annotation', title: 'Návrh kódování otevřených odpovědí Q9',
    author: 'Specialista kvalitativní analýzy · navržená schopnost (v AIA zatím není)',
    baseRev: 16, baseLabel: 'Běh RUN-16A',
    changes: [
      { id: 'q1', target: 'Q9.T1', label: 'Poplatky a cena', kind: 'add', to: '39 odpovědí', why: 'Např. R-031, R-266' },
      { id: 'q2', target: 'Q9.T2', label: 'Aplikace a rychlost', kind: 'add', to: '31 odpovědí', why: 'Např. R-118' },
      { id: 'q3', target: 'Q9.T3', label: 'Investování v mobilu', kind: 'add', to: '14 odpovědí', why: 'Např. R-207' },
      { id: 'q4', target: 'Q9.T4', label: 'Sociální důvody', kind: 'add', to: '9 odpovědí', why: 'Např. R-342' },
      { id: 'q5', target: 'Q9.T5', label: 'Nezařaditelné', kind: 'add', to: '3 odpovědi', why: 'Ponecháno bez tématu' },
    ],
    implications: ['Počty vzniknou z uložené klasifikace každé odpovědi, ne z textu modelu.', 'Kódování je interpretace; každé téma má dohledatelné příklady.'],
    impact: [{ stage: 'report', effect: 'RQ2 („proč“) lze doplnit do kap. 3' }],
    recompute: 'Ano: modul Výzkumné otázky se přepočte nad uloženou klasifikací.',
    cost: 'odhad 0,35 USD',
  };
}
