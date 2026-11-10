# Three studies, one case

Nigel and Aram each write all three studies on the Velis case ([`CASE.md`](CASE.md)), working independently and starting from the same files. That makes six reports. The executive reads them in two ways:

- **across the types**, to see what each kind of study can answer;
- **across the authors**, to see how much depends on the method and how much on the person.

The answers feed the MVP's scope: which steps, analyses and visuals earn their place.

| | 1 · Situační zpráva | 2 · Obchodní model | 3 · Obchodní model + zákazníci |
|---|---|---|---|
| Answers | What do the sources, the market and the client's people say, and which option does the evidence favour? | Which option wins by the client's rule, how sure is that, and what drives it? | As 2, plus what customers want from delivery, and whether they and the model agree |
| Calculation | None ("Potřebuje výpočet? Ne") | The cash-flow model, base case plus 20 000 futures | As 2 |
| Respondents | None | None | 800 customers (`pruzkum_zakazniku_2026.csv`) |
| Sociomapa | Expert map: the five managers' scores | Scenario map: the options across the model's futures | Scenario map **beside** the respondent map of delivery experiences |
| Main grades | veřejný zdroj, z dat klienta, úsudek | výpočet, odhad, z dat klienta | as 2, plus customers' answers labelled as survey data |
| Canvas boards | Z0–Z7, MV2, MV2b, MV6 | Z0–Z7, M1–M6, MV3, MV4 | as 2, plus the survey lane (`../research-stages/`) |

## What every report contains

These parts are the same in every report, so differences come from the method and not the format:

1. **Shrnutí**: one page with the decision, the recommendation (or "nothing passes") and how sure it is.
2. **Zadání**: the decision, the options, the constraints and the rule as written before any result (CASE.md §3–6).
3. **Co jsme použili**: every file and source, with what was taken from each and what was missing.
4. **The study's own chapters**, below.
5. **Doporučení a provedení**: what to do, the pilot, and what to watch after deciding.
6. **Metoda a meze**: what the study can and cannot claim, the grade legend, and each method's approval status.
7. **Příloha**: tables, and every number's source.

Every number carries its grade and source. Every chart says what it is computed from.

## 1 · Situační zpráva: no model

**The question.** Without building a model, what do the evidence and the client's people say about the seven options?

**Inputs.**
- The brief, all five documents, `zakaznici_souhrn_2025.xlsx` and `vysledovka_rozvaha_2023-2025.xlsx` for context.
- `hodnoceni_expertu.csv` for the expert map.
- Public research.
- `objednavky_2023-2025.xlsx` may be quoted, but the study computes nothing from it beyond what a reader can check by eye.

**Chapters.**
- **Trh a prostředí**: PESTEL; Porter's five forces for Czech e-commerce logistics; the market's size and growth, top-down, from cited sources.
- **Možnosti**: the seven options side by side on cost, risk, service, capacity and capital, using the documents' figures. Each figure is a quote with its page. The comparison is the researcher's labelled judgement, not a calculation.
- **Co si myslí vedení**: the expert map from the five managers' scores. Show where they agree and where one manager sees an option differently. A missing score stays missing.
- **SWOT** of the leading two options.
- **Co by rozhodl výpočet**: the questions only a model could answer, such as how much a one-day delay costs or whether the hall pays back. This is the bridge to type 2.

**It never claims** a number it did not read or compute in front of the reader, or a probability.

## 2 · Obchodní model

**The question.** By the CFO's rule (CASE.md §6), which option should Velis choose, and how sure is that?

**Inputs.** Every file in [`data/`](data/) except `pruzkum_zakazniku_2026.csv`, every document, and public research.

**Steps.**
- **Data.** Write a data contract for each file: which columns are used, and how. Keep `email` out. Check the files: totals against invoices, duplicates, missing values, outliers, seasonality.
- **Předpoklady.** Give every input a low, likely and high value, a source and the person who stands behind it (CASE.md §7–8). Estimate from the client's data where the data allows:
  - the order loss after a one-day delay, from `zpozdeni_2024.xlsx`, overall and in the big cities;
  - the shipping-price elasticity, from `objednavky_doprava_2024.xlsx`.

  State which inputs move together, and why.
- **Model.** One cash-flow model for all seven options. Use the same timing for each (CASE.md §8): every option at the Czech 3PL in 2026; B2's fixed price from 1. 1. 2027; a move to the Polish 3PL on 1. 7. 2027; the hall from 1. 1. 2028, with A and A2 at the Czech 3PL until then. Run the base case plus 20 000 seeded futures with seed `20261030`; the same seed gives the same result.
- **Výsledky.**
  - **Rozhodnutí:** the rule applied as written. For each option: the median and 90 % interval of NPV against B, P(better than B) and P(loss > 10 mil. Kč). Then sensitivity, break-even, and the value of information in Kč.
  - **Finance:** NPV before and after tax, IRR, payback, at 6 / 8 / 10 %.
  - **Účetnictví:** P&L and key ratios for each option in 2028.
  - **Provoz a logistika:** capacity against monthly peaks, and cost to serve.
  - **Trh:** whether growth of 9 % a year is realistic against the market.
- **Sociomapa systémů, scenario map.** The seven options placed by whether they do well in the same futures. Show which options win together and which hedge each other. Draw only links that beat chance after the false-alarm correction. The map is labelled internal until Metodika approves the method. What the maps draw is still open (W24), so say which view you chose and why.

**It never claims** that the map shows causation, or a probability the model did not compute.

## 3 · Obchodní model + zákazníci

**The question.** As in 2, plus: what do customers want from delivery, and do their answers agree with how they actually behaved (the delay data) and with the model?

**Inputs.** Everything from 2, plus `pruzkum_zakazniku_2026.csv` and its questionnaire, `pruzkum_zakazniku_2026_dotaznik.md` (each question's wording and scale anchors). The 800 rows are fictional respondents. They stand in for a real customer survey or for AIA's AI respondents, and both authors use the same file so their reports can be compared.

**Additional chapters.**
- **Co chtějí zákazníci:** how attractive the eight delivery experiences are, overall and by group (big city or not, age, purchase frequency), and what customers would pay for next-day delivery.
- **Respondentní Sociomapa:** customers × the eight delivery experiences, mapped as in the survey lane, with segments where the data shows them.
- **Dvě mapy vedle sebe:** the scenario map of options and the respondent map of experiences, linked through which experience each option gives a customer:

  | Experience | Options that give it |
  |---|---|
  | O1 Doručení druhý den | A, A2, B, B2 and H in the big cities |
  | O2 Do 2 pracovních dnů | A, A2, B, B2 outside the big cities; C in the big cities |
  | O3 Do 3 pracovních dnů | C outside the big cities; C2, H outside the big cities |
  | O4 Expres ve velkých městech | C2 in the big cities |
  | O5 Doprava za 79 Kč | today's shipping price; any option |
  | O6 Doprava za 59 Kč, o den delší | a cheaper, slower delivery; fits C |
  | O7 Výdejní box nebo výdejní místo | a delivery channel; any option |
  | O8 Doprava zdarma nad 1 500 Kč | a pricing lever; any option |

  The maps stay two maps. They are never merged into one.
- **Říkají a dělají:** the customers' stated reaction to a one-day delay (`q_zpozdeni_objednal_znovu_1_5`) against the observed loss in `zpozdeni_2024.xlsx`. Where the two disagree, the report says which it trusts and why.

**The rule for survey numbers.** A survey number never enters the model silently. It may enter only as a labelled alternative scenario ("pokud mají zákazníci pravdu"), shown beside the base result.

## For the executive: one sheet per report

The same questions for each of the six reports. Answers go back into the MVP plan.

1. Which option would you choose after reading this report, and how sure would you be?
2. Which page or chart convinced you most? Which one did you not trust, and why?
3. What did you need that the report didn't have?
4. What could be cut without loss?
5. Is the length right? (shorter / right / longer)
6. Comparing it with the same type by the other author: are the conclusions the same? If not, which one do you believe?
7. Comparing it with the other two types: which would you pay for, and how much would you pay compared with today's research?
8. For type 3: did the customers' map change your view of the model's map?

## Suggested file names

`Velis_1_situacni-zprava_<autor>.pdf`, `Velis_2_obchodni-model_<autor>.pdf`, `Velis_3_model-a-zakaznici_<autor>.pdf`.
