# Three studies, one case

Each author writes all three studies on the ChemVitro case ([`CASE.md`](CASE.md)), working independently and starting
from the same files. The executive reads the reports across the types (what each kind of study can answer) and across the
authors (how much depends on the method and how much on the person).

| | 1 · Situační zpráva | 2 · Model nákladů lokality | 3 · Model + pracovníci |
|---|---|---|---|
| Answers | What do the documents, the public sources and the client's people say about the eight sites, and which does the evidence favour? | Which site wins by the CFO's rule, how sure is that, and what drives it? | As 2, plus where the workers would want to work, and whether that agrees with the labour-market data and the model |
| Calculation | None ("Potřebuje výpočet? Ne") | The cost-of-supply model, base case plus 20 000 futures | As 2 |
| Respondents | None | None | 300 workers (`pruzkum_pracovniku_2026.csv`) |
| Sociomapa | Expert map: the twelve people's scores | Scenario map: the sites across the model's futures | Scenario map **beside** the respondent map of the sites |
| Main grades | veřejný zdroj, z dat klienta, úsudek, právní předpis | výpočet, odhad, z dat klienta | as 2, plus the workers' answers labelled as survey data |

## What every report contains

1. **Shrnutí**: one page with the decision, the recommendation (or "nothing passes") and how sure it is.
2. **Zadání**: the decision, the options, the constraints and the rule as written before any result (CASE.md §3–6).
3. **Co jsme použili**: every file and source, with what was taken from each and what was missing.
4. **The study's own chapters**, below.
5. **Doporučení a provedení**: what to do, what to clarify with which authority or operator, and what to watch.
6. **Metoda a meze**: what the study can and cannot claim, the grade legend, and each method's approval status.
7. **Příloha**: tables, and every number's source.

Every number carries its grade and source. Every chart says what it is computed from.

## 1 · Situační zpráva: no model

**The question.** Without building a model, what do the documents, the public sources and the client's people say about
the eight sites?

**Inputs.** Every document; `lokality_parametry.xlsx`, `trh_prace_regiony.xlsx`, `ovzdusi_stanice.csv`,
`proces_emise_odpady.xlsx` and `nakup_vtx40_2023-2026.xlsx` for reading; `hodnoceni_lokalit.csv` for the expert map;
public research. The study may compare two numbers a reader can check by eye (a limit against a measured value, a capacity
against a need), but computes no cost.

**Chapters.**
- **Prostředí**: PESTEL for a chemical plant in the three countries; carbon and waste fees; permitting regimes;
  the labour markets of the eight regions, from cited sources.
- **Lokality**: the eight sites side by side on cost, permitting and environment, staff, logistics and site risk, using the
  documents' figures. Each figure is a quote with its page. What each site's documents leave out is shown as clearly as
  what they say.
- **Co si myslí lidé ChemVitro**: the expert map from the twelve people's scores. Where they agree, where one person sees a
  site differently, and whether any score should not be taken at face value. A missing score stays missing.
- **SWOT** of the leading two sites.
- **Co by rozhodl výpočet**: the questions only a model could answer. This is the bridge to type 2.

**It never claims** a cost it did not read or compute in front of the reader, or a probability.

## 2 · Model nákladů lokality

**The question.** By the CFO's rule (CASE.md §6), should ChemVitro build, where, and how sure is that?

**Inputs.** Every file in [`data/`](data/) except `pruzkum_pracovniku_2026.csv`, every document, and public research.

**Steps.**
- **Data.** Write a data contract for each file: which columns are used, and how. Check the files: units, currencies,
  price years, duplicates, missing values, outliers, and quotes that do not cover the same thing.
- **Předpoklady.** Give every input a low, likely and high value, a source and the person who stands behind it
  (CASE.md §7–8). Estimate from the client's data where the data allows:
  - how far the EPC estimate is likely to be exceeded, from `srovnatelne_zavody.xlsx`;
  - what the comparable plants spent beyond their EPC estimates, from the same file.

  For every site, check what the EPC estimate covers against what the site's documents require, and price any difference.
  State which inputs move together, and why.
- **Model.** One cost-of-supply model for the eight sites and the buy baseline, on the same timeline: decision on
  1. 2. 2027, permits, construction, start; VTX-40 bought until the plant runs, at spot price after 30. 6. 2030. Run the base
  case plus 20 000 seeded futures with seed `20270201`; the same seed gives the same result.
- **Výsledky.**
  - **Rozhodnutí:** the rule applied as written. For each site: the median and 90 % interval of the saving against keeping
    buying, P(beats buying), P(loss > 20 mil. EUR), P(production by 1. 7. 2030) and the investment. Then sensitivity,
    break-even, and the value of information in EUR.
  - **Finance:** NPV before and after tax, IRR, payback, at 6 / 8 / 10 %.
  - **Provoz:** staff, energy, carbon, waste and wastewater cost per tonne at each site in 2032.
  - **Harmonogram:** the start date's distribution per site against 1. 7. 2030.
- **Sociomapa systémů, scenario map.** The eight sites (and keeping buying) placed by whether they do well in the same
  futures. Draw only links that beat chance after the false-alarm correction. The map is labelled internal until Metodika
  approves the method; say which view you chose and why.

**It never claims** that the map shows causation, or a probability the model did not compute.

## 3 · Model + pracovníci

**The question.** As in 2, plus: where would the workers ChemVitro needs want to work, and does that agree with the
labour-market data and with the model's staffing assumptions?

**Inputs.** Everything from 2, plus `pruzkum_pracovniku_2026.csv` and `pruzkum_pracovniku_2026_dotaznik.md`. The 300 rows
are fictional respondents; both authors use the same file so their reports can be compared.

**Additional chapters.**
- **Koho oslovíme:** how attractive working at each site is, overall and by group (country, profession, age, willingness to
  relocate), and what wage the workers expect, in one currency. Say who the sample represents and who it does not.
- **Respondentní Sociomapa:** workers × the eight sites, with segments where the data shows them.
- **Dvě mapy vedle sebe:** the scenario map of the sites and the respondent map of the workers. The maps stay two maps.
  They are never merged into one.
- **Říkají a dělají:** the workers' stated willingness to relocate and commute against the labour-market data (hiring time,
  unemployment, big hiring projects nearby). Where the two disagree, the report says which it trusts and why.

**The rule for survey numbers.** A survey number never enters the model silently. It may enter only as a labelled
alternative scenario ("pokud mají pracovníci pravdu"), shown beside the base result.

## For the executive: one sheet per report

1. Which site would you choose after reading this report, and how sure would you be?
2. Which page or chart convinced you most? Which one did you not trust, and why?
3. What did you need that the report didn't have?
4. What could be cut without loss?
5. Is the length right? (shorter / right / longer)
6. Comparing it with the same type by the other author: are the conclusions the same? If not, which one do you believe?
7. Comparing it with the other two types: which would you pay for, and how much compared with today's research?
8. For type 3: did the workers' map change your view of the model's map?

## Suggested file names

`ChemVitro_1_situacni-zprava_<autor>.pdf`, `ChemVitro_2_model-lokality_<autor>.pdf`, `ChemVitro_3_model-a-pracovnici_<autor>.pdf`.
