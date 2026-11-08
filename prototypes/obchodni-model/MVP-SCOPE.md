# MVP scope: the report-2 pipeline on today's AIA

8 Nov 2026. Session A of `BRIEF-mvp-r2.md`. The spine is study type 2 of the ChemVitro case
(`prototypes/case-chemvitro/STUDIES.md`), end to end, producing a report with the content and quality of
`exemplar/ChemVitro_2_model-lokality_nigel.pdf` (parts R2-P01 to R2-P18, tables T1 to T9). Code anchors are
`file:line @ b28ce091` (`origin/develop`, the base of this branch; `apps/` and `packages/` are identical there).
Plan ids are `plan#CHUNK`; a chunk named **new** does not exist in any plan file yet and is defined here in one line.
Board codes are the canvas's (`README.md`); the brief's session table says who builds which.

Sections: 1 The decision · 2 The pipeline in eight steps · 3 Perspectives · 4 The weighting-scenario map ·
5 Parked · 6 Acceptance · 7 Waves · 8 Open decisions.

## 3. Perspectives

The owner (8 Nov): "all business perspectives: financial, strategic, operational, marketing, logistics". A
**perspective** is a set of **components** of the decision. A component is one measure per option, with a source
(a model result, a client-data number, a cited finding, or a named expert's score), a grade (the exemplar's seven:
*z dat klienta, výpočet, odhad, úsudek, veřejný zdroj, právní předpis, průzkum*) and a direction (↑ higher is
better, ↓ lower is better). The weighting-scenario map (§4) scores components; the client's rule does not read them.

Rules, from the methodology review of 5 Nov (ADR 0046 § The methodology review):
- **Gates are not components** (R2). The rule's four conditions are pass / fail / unknown per option; an unknown
  gate is "cannot be recommended until evidenced", and no weight compensates a failed one.
- **A missing component keeps a range, never a score** (R2). The cell shows the range it could take; the map is drawn
  at the documented minimum and the range beside it.
- **One mechanism, one component** (R3, "no double counting"). A component whose mechanism the model's saving already
  holds is marked *v modelu*; one the model does not hold is *mimo model*. A scenario may weight the saving or its
  parts, and the overlap check (§4, line 6) refuses a vector that weights both.
- **Judgement is labelled** (A3). A component scored by a person carries that person's name and the grade *úsudek*.
- **An empty perspective stays and says so.** For ChemVitro the marketing perspective is empty; for Velis it is central.

### ChemVitro's components

Sources are the exemplar's tables and parts. *Stejné pro všechny lokality* names a build-versus-buy component that
does not separate the sites; it is shown in the report and not scored on the map.

| Perspective | Component (per site) | Source | Grade | Direction | In the saving? |
|---|---|---|---|---|---|
| **Finanční** | Medián úspory proti nákupu, NPV 2027–2044 při 8 % | T1, R2-P06 | odhad | ↑ | the saving itself |
| | P(porazí nákup) ≥ 0,75 | T1 | odhad | gate | |
| | P(ztráta > 20 mil. EUR) ≤ 0,10 | T1 | odhad | gate | |
| | Investice v základním případě ≤ 175 mil. EUR | T5 | výpočet | gate; ↓ | v modelu |
| | P(investice ≤ 175) | T5 | odhad | ↑ | v modelu |
| | IRR; rok návratnosti | T4 | výpočet | ↑; ↓ | v modelu |
| | NPV po zdanění při 8 % | T4 | výpočet | ↑ | v modelu (tax is a fixed parameter, I4) |
| | Forma pobídky: daňová úleva (CZ, PL) nebo dotace (DE), podíl a P(schválení) 0,5 | R2-P10, T9 | z dat klienta; právní předpis; úsudek | informační | v modelu (after-tax view) |
| **Strategická** | Společné selhání s vedoucí lokalitou: podíl budoucností, v nichž je i tato lokalita horší než nákup | T8, R2-P12 | odhad | ↓ | mimo model |
| | Závislost na jednom dodavateli; přirážka při prodloužení 12–22 %; podmínky po roce 2035; zůstatková hodnota 30 % | R2-P03 §2.4, R2-P08 §7.2, T9 | z dat klienta; úsudek | stejné pro všechny lokality | levers of build vs buy |
| | Tržní pozice | — | — | not applicable: the plant supplies Brno (62 %) and Pardubice (38 %) only | |
| **Provozní** | Provozní náklad na tunu 2032, celkem | T6 | výpočet | ↓ | v modelu |
| | z toho energie; údržba a park; odpad a voda | T6 | výpočet | ↓ | v modelu |
| | Najíždění 60–90 % v prvním půlroce | T9 | úsudek | stejné pro všechny lokality | |
| **Marketingová / obchodní** | — | — | — | empty for ChemVitro: captive demand, no customer promise at stake. Velis: customer promise, delivery time, demand growth | |
| **Logistická** | Doprava produktu do Brna a Pardubic, EUR/t | T6 (doprava) | výpočet | ↓ | v modelu |
| | Vlečka k postavení: délka, cena za km, získání pozemků (Odrzyca) | T5, T9 | z dat klienta; odhad; úsudek | ↓ | v modelu (capex, delay) |
| | Silniční přístup: nosnost mostu 16 t proti 40 t, zesílení (Eschfeld) | T5, T9 | z dat klienta; úsudek | ↓ | v modelu (capex, start) |
| | Doprava surovin přes překladiště do stavby vlečky, EUR/t | T9 | úsudek | ↓ | v modelu |
| **Prostředí a povolování** | Stanice nad limitem memoranda (BaP, PM2,5) → šance kompenzace 0,8 / 0,2 / 0 | R2-P05, T9 | z dat klienta; úsudek | ↓ | v modelu (the decisive input) |
| | Prodloužení povolování s kompenzací, měsíce (CZ 9–15, PL 12–18) | T9 | z dat klienta | ↓ | v modelu |
| | P(výroba k 1. 7. 2030) ≥ 0,80 | T1, R2-P07 | odhad | gate | |
| | Předčištění odpadních vod: potřeba a cena (Lipová, Lindenau) | T5, T9 | z dat klienta; odhad | ↓ | v modelu |
| | Poplatek chemického parku (Wendelstedt) | T9 | z dat klienta | ↓ | v modelu |
| | Emise CO₂ a EU ETS, 56 EUR/t | T6 | výpočet | stejné pro všechny lokality | |
| **Lidé** | Náklady na zaměstnance na tunu (mzda operátora × skladba mezd × odvody) | T6 (lidé), T9 | výpočet; právní předpis (prozatímní) | ↓ | v modelu |
| | Doba obsazení místa operátora, dny (Eschfeld 118, jinde 49–71) | R2-P07 §6.2, Trh práce v regionech | z dat klienta | ↓ | mimo model (stress test only) |
| | Velký nábor v okolí (Kamenec: 380 lidí do 2028) | Trh práce v regionech | z dat klienta | ↓ | mimo model |
| | Růst mezd po roce 2031 | T9 | úsudek | stejné pro všechny lokality | |

What the table shows for the map: 22 scored components, of which 18 are *v modelu*. A scenario that weights
"finance 0,5 · provoz 0,3 · logistika 0,2" over these scores operations and logistics twice, because the saving already
holds their cost per tonne. Two honest scenario families exist: (a) **the saving against what the model leaves out**
(shared failure, hiring time, hiring competition), and (b) **the parts of the saving against each other** (people,
maintenance, transport, permitting cost) without the saving itself. The map records which family a scenario belongs to.

## 4. The weighting-scenario map (Mapa scénářů vah, board MV9)

1. **Objects** are the options: the eight sites. The buy baseline is the rule's reference, not an object.
2. **Rows** are named weight vectors over perspectives or components, composed by the researcher or the client's
   people ("FR: finance 0,5 · provoz 0,3 · logistika 0,2"), each with who composed it and when, recorded in the
   approval ledger before results where the composer has not seen them (swing weighting, R3).
3. **The fan** around each row is k perturbed vectors from a declared concentration; it is a sensitivity setting, never
   a probability (R4). The map prints "podíl testovaných nastavení, v nichž je možnost první", never P.
4. **A cell** is the option's weighted score: each component scaled on its declared extremes and direction
   (`cost-model-study#CS1`), gates excluded and shown as pass / fail / unknown beside the map (R2).
5. **A missing component** keeps its range: the cell is an interval, the map is drawn at the documented minimum and
   the row says what the top of the range would change (R2).
6. **The overlap check** marks components with one mechanism (§3, *v modelu*); a vector that weights the saving and
   one of its parts is refused by name and offered the two honest families.
7. **Height** is the weighted score under the scenario the reader chooses; relative (centred per row) and absolute
   readings side by side, as MV3's contract for the scenario mode (R5).
8. **Layout** is the `aia-sociomap-5` engine's over the rows × objects table, as the prototype already runs it
   (`tools/engine_maps.py`, `compute_object_map`, `domain/sociomap/engine_v2.py:887`); its pair statistics are not read,
   because the rows are settings we chose (MV3). Options close together win under the same weightings.
9. **Apart from the futures map.** The futures map's rows are the model's draws; this map's rows are preferences. They
   sit side by side and are never merged.
10. **Where it goes.** The map is preference information. It enters the report under "Co by závěr změnilo", never the
    recommendation; the client's rule decides (R3). Its method is a Metodika register entry of its own
    (`sociomapa-systemu#SYS12`), internal until the methodologist approves it, labelled *metoda čeká na schválení
    metodikem* wherever it appears.

The rest of the scope (sections 1, 2 and 5 to 8) follows in this file.
