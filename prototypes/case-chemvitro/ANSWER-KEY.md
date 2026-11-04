# ChemVitro: answer key

**Open this only after your report is finished.** It says what was planted in the pack, where each clue sits, and what
the reference model (`tools/reference.py`, seed `20270201`, 20 000 futures, true parameters including the hidden costs)
finds. The reference model is one reasonable model, not the only right one: judge a report by whether it found the
planted facts and applied the rule honestly, not by whether it hit these numbers.

## 1. The headline

| | Reference (true costs) | A study that misses the three traps |
|---|---|---|
| Winner at 8 % | **CZ3 Kamenec**: median saving +39,8 mil. EUR, P(beats buying) 0,82, P(loss > 20 mil.) 0,09, P(start by 1. 7. 2030) 1,00, investment ≈ 151 mil. EUR | **CZ2 Lipová**: median +49,5 mil. EUR |
| Also passes at 8 % | CZ2 (+37,4; 0,80; 0,09) | CZ1, CZ3, PL1, PL2 |
| Fails at 8 % | PL1 just misses the loss limit (+35,6; P(loss) 0,10, on the edge); CZ1 and PL2 fail the start date; DE1, DE2, DE3 do not beat buying | DE1, DE2, DE3 |
| At 6 % | CZ2, CZ3, PL1 pass; CZ3 wins | |
| At 10 % | **nothing passes**: recommend nothing | |

The two leading sites are close (2,4 mil. EUR apart) and fail differently: CZ3's risk is staff (a large employer hiring
380 people nearby), CZ2's is a known, priceable wastewater cost. The single assumption most worth checking is the
renewal price of the supply contract (12–22 %): it moves every site's saving together and decides whether 10 % passes.

Reference results at 8 % (mil. EUR, saving = NPV of buying − NPV of the site):

| Site | Median | 90 % interval | P(beat) | P(loss > 20) | P(start ok) | Median start | Investment (median) | Brochure (EPC + land) | Hidden capex |
|---|---|---|---|---|---|---|---|---|---|
| CZ1 | 19,3 | −47,8 … 93,5 | 0,68 | 0,17 | **0,03** | 2030,8 | 164 | 132 | 11,5 |
| CZ2 | 37,4 | −32,7 … 113,7 | 0,80 | 0,09 | 1,00 | 2030,1 | 159 | 127 | 12,1 |
| **CZ3** | **39,8** | −31,8 … 117,2 | 0,82 | 0,09 | 1,00 | 2029,8 | 151 | 131 | 0 |
| DE1 | 2,5 | −72,6 … 82,3 | 0,52 | 0,31 | 1,00 | 2029,7 | 170 | 148 | 0 |
| DE2 | 7,9 | −62,5 … 84,4 | 0,57 | 0,26 | 0,85 | 2030,3 | 174 | 138 | 14,3 |
| DE3 | −19,6 | −89,5 … 56,3 | 0,33 | 0,50 | 0,50 | 2030,5 | 174 | 148 | 4,1 |
| PL1 | 35,6 | −35,4 … 113,2 | 0,79 | 0,10 | 1,00 | 2029,8 | 150 | 122 | 9,2 |
| PL2 | 18,9 | −46,0 … 89,8 | 0,68 | 0,17 | **0,00** | 2031,1 | 153 | 120 | 15,0 |

The brochure favourite is PL2 Bory (lowest EPC estimate, cheapest land, lowest wages, the largest tax exemption). It
cannot start before mid-2031.

## 2. The three traps

### 2.1 Wastewater: relying on the municipal treatment plant (CZ2, DE2)

The process effluent after neutralisation has **sulfates 1 800 mg/l and COD 2 400 mg/l**, about **430 m³ a day**
(`proces_emise_odpady.xlsx`: 4,2 m³/t × 34 000 t / 330 days). The site sheet says every site is "connected to sewer: ano".

| Site | What the statement says (`vyjadreni_cov.pdf`) | Consequence (reference) |
|---|---|---|
| CZ2 Lipová (p. 2) | city plant, spare capacity ~600 m³/day, but the sewer bylaw allows **sulfates ≤ 300, COD ≤ 800 mg/l**; above that a surcharge of 340 Kč/m³ (14 EUR) **or** mandatory pre-treatment. "We have not received your effluent composition." | pre-treatment ≈ 11 mil. EUR capex (×0,9–1,3) + 0,7 mil. EUR a year, +2–5 months. The surcharge alone would be ≈ 2 mil. EUR a year |
| DE2 Lindenau (p. 5, German) | spare capacity **only 250 m³/day** (< 430 needed), sulfate ≤ 600, COD ≤ 1 000 | own pre-treatment + a direct-discharge permit: ≈ 13 mil. EUR + 0,8 mil. EUR a year, +4–8 months |

The EPC estimate excludes "pre-treatment beyond neutralisation" (`epc_odhad.pdf` p. 3). `srovnatelne_zavody.xlsx` shows 8
of 36 plants built pre-treatment, median ≈ 10 mil. EUR, never in a chemical park.

### 2.2 Air: siting in an area that exceeds the limits (CZ1, PL2)

`ovzdusi_stanice.csv`, 2025: **CZ1 Vrbice** benzo[a]pyrene 1,76 ng/m³ (target 1); **PL2 Bory** PM2,5 25,8 µg/m³ (limit 25),
B[a]P 3,68 ng/m³, NO₂ 30. Every other site is within today's limits. The memo (`memo_povolovani_ovzdusi.pdf` p. 2–3)
explains that in such areas the authority can require **compensation measures** (offsets paid by the investor) and
emission levels at the strict end of BAT, and that permits take 9–15 months longer in Czechia and 12–18 months in Poland.
It does not name the sites: the analyst has to combine the station data with the memo.

Reference: CZ1 offsets 5–9 mil. EUR + abatement 4,5 mil. EUR capex + 0,4 mil. EUR a year, +9–15 months; PL2 offsets 7–13
+ 5,0 + 0,45, +12–18 months. Both then start after 1. 7. 2030 in almost every future (CZ1 3 %, PL2 0 %) and buy at spot
price meanwhile. `srovnatelne_zavody.xlsx`: 9 plants paid compensation measures, median 5 mil. EUR.

Red herring: CZ3 Kamenec had B[a]P 1,3 ng/m³ in 2021 only; 2022–2025 it is 0,88–0,97, within the target.
Caveat worth a note: under the revised directive (EU) 2024/2881 the 2030 limits are much lower (PM2,5 10 µg/m³), so
several sites may exceed them by 2030; a report that spots this deserves credit, but it is not planted.

### 2.3 Logistics: the last mile (PL1, DE3)

| Site | Brochure | Statement (`vyjadreni_doprava.pdf`) | Reference |
|---|---|---|---|
| PL1 Odrzyca | "bocznica kolejowa w odległości 3,4 km" (a rail siding 3,4 km away) | p. 7, Polish: the investor pays for building the 3,4 km spur and buying the land; 14–24 months from land rights; until then trucks via a transhipment terminal | spur 3,4 km × 1,9–2,8 mil. EUR/km + 1,2 mil. EUR land; trucking +16 EUR per tonne of raw material until the spur runs. Does not delay the start (trucks possible) |
| DE3 Eschfeld | "Anbindung über die Kreisstraße an die A93" | p. 6, German: the bridge over the Eschbach carries **16 t**; tankers weigh 40 t; reinforcement at the investor's cost (3,2–5,0 mil. EUR); heavy-traffic access is approved only after it is done | +3,2–5,0 mil. EUR and +6–10 months: P(start by 1. 7. 2030) falls to 0,50 |

`srovnatelne_zavody.xlsx`: 4 plants built a spur, median ≈ 2,0 mil. EUR per km.

## 3. Other things planted

**Documents**
- `epc_odhad.pdf` p. 3 lists what the estimate excludes: off-site infrastructure, pre-treatment, compensation measures, park
  fees, site-risk reserve. A study that adds nothing to the EPC figure has missed all three traps.
- `epc_odhad.pdf` is ±25 %, but the comparable plants overran by a median of **17,0 %** (90th percentile 31,2 %; 36 plants after removing the duplicate);
  brownfield sites worst. The reference uses a median overrun of +16 %.
- `zadani_projektu.pdf` p. 4: the consultant KON works for LokaPartner, the agency that brokered part of the offers.
- Incentives: the Czech investment incentive and the Polish CIT exemption are **tax reliefs**: they do not change the
  pre-tax figure the rule reads. Only the German GRW is a cash grant (the reference counts it with a 60 % approval
  chance). A report that subtracts PL2's "CIT exemption up to 50 %" from the investment has misread it.
- The 24 MW boiler is above the 20 MW threshold, so the plant is in the EU ETS (memo p. 1); carbon is a cost at every site.
- DE1's brochure mentions a park service fee "by agreement"; its wastewater statement (`vyjadreni_cov.pdf` p. 4) names it:
  about 1,1 mil. EUR a year, outside the EPC scope.
- Decoys that look like traps but cost little or nothing: DE3's treatment plant charges a surcharge from COD 2 500 mg/l
  (the effluent has 2 400); CZ3's from COD 3 000; CZ2 needs a turning lane at about 2 mil. Kč (`vyjadreni_doprava.pdf` p. 2);
  PL2's municipal treatment plant does accept the effluent (limits 2 000 / 3 000 mg/l), unlike CZ2's.
- `doprava_nabidky.csv`: PL1's rail rate assumes a spur to the site ("předpoklad dopravce: vlečka k areálu"), which does not
  exist yet.

**Data files**
- `srovnatelne_zavody.xlsx`: P-17 appears twice (the second time with a rounded investment); P-23's capacity (91) is in
  t/day, not kt/year; P-31 has no price year; investments are in EUR, CZK and PLN (5 CZK, 7 PLN rows) and in each
  plant's own price year.
- `nakup_vtx40_2023-2026.xlsx`: 2025-07 volume in kg; 2024-03 price in USD (labelled in the currency column); an extra
  2026-02 row is a spot purchase from another supplier at 2 180 EUR/t: the spot price for a late start.
- `trh_prace_regiony.xlsx`: wages are gross in **local currency** (CZK, EUR, PLN), without employer contributions; CZ3 has
  "Kamenec Steel hiring 380 people by 2028"; DE3 has 2,4 % unemployment and 118 days to fill an operator post.
- `odpady_nabidky.csv`: a second, cheaper PL2 quote (95 EUR/t, landfill) covers only non-hazardous waste: not comparable.
- `ovzdusi_stanice.csv`: see 2.2.
- `hodnoceni_lokalit.csv`:
  - **TI2 scored with the scale reversed** (1 = best); a note on one row says so ("hodnoceno 1 = nejlepší"), and TI2's
    scores run against everyone else's;
  - **KON adds about 2,5 points to CZ2 and PL2**, the two sites its agency brokered;
  - EHS marks CZ1 and PL2 down on permitting: the only person who saw the air problem;
  - two cells are missing.
- `pruzkum_pracovniku_2026.csv`:
  - 306 rows: **6 duplicated respondents** (W009, W040, W055, W112, W139, W249);
  - **9 straight-liners** (all eight sites the same score: W069, W071, W075, W086, W143, W191, W253, W254, W284);
  - the sample is **58 % Czech** (179 / 66 / 61 after duplicates), while the chemical workforce in the relevant regions is
    31 000 CZ / 46 000 DE / 24 000 PL (`trh_prace_regiony.xlsx`, sheet Země): unweighted averages favour the Czech sites;
  - **home bias**: every worker rates sites in their own country about 2 points higher;
  - **a mobile segment** (younger technicians and maintenance staff, relocation 4–5) rates DE1 and DE3 about 1,8 higher and
    their own country lower: the respondent map should show it;
  - expected wages are in the local currency (column `mena`).
  - Says vs does: mean willingness to relocate 2,54, only 19 % say 4–5; the labour data (hiring time, big hiring projects)
    is the better guide to staffing. A report that staffs DE3 from the survey's relocation answers ignores 118 days to fill
    a post.

## 4. What each study type should find

| Type | Should find |
|---|---|
| 1 · Situační zpráva | CZ2's and DE2's wastewater limits against the process effluent (a by-eye comparison of two numbers); CZ1's and PL2's station values against the limits, with the memo; PL1's spur and DE3's bridge; the EPC exclusions; KON's interest and TI2's reversed scale on the expert map; that PL2 looks best only on paper. No ranking by cost |
| 2 · Model nákladů | the three traps priced; overrun from the comparable plants; spot price for a late start; tax reliefs out of the pre-tax rule; the rule applied: **CZ3** at 8 % (CZ2 close behind), nothing at 10 %; the renewal price as the assumption most worth checking |
| 3 · Model + pracovníci | as 2, plus: the survey cleaned (duplicates, straight-liners) and weighted by country; home bias and the mobile segment on the respondent map; the survey's stated mobility not trusted over the labour data; CZ3's staffing risk discussed as the main risk of the winner |
