# ChemVitro: the case

**Fictional.** ChemVitro a.s., its sites, suppliers, people and numbers are invented, and so are the towns, parks, utilities
and authorities in the documents. The regions (kraje, Länder, województwa) are real so that public research is possible.

This file is the whole context a study needs: the company, the decision, the options, the constraints, the rule, the people,
the client's answers, an inventory of every file and what to research. Every study starts from it and from nothing else.
When a study needs a fact this file doesn't give, the fact either comes from the client's files in [`data/`](data/) and
[`documents/`](documents/), or from public sources found in Rešerše, with a citation. Otherwise it is recorded as missing.
A study never invents a fact.

## 1. The company

| | |
|---|---|
| Name | ChemVitro a.s. (fictional), Brno |
| Business | Specialty chemicals; two production plants, in Brno and Pardubice |
| The product in question | VTX-40, a fictional ester intermediate the two plants consume. ChemVitro does not sell it |
| Use | About 34 000 t in 2026 (Brno 62 %, Pardubice 38 %), growing 1–3 % a year |
| Supply today | Bought in full from one supplier, Hanshin Fine Chemicals (fictional), shipped from Asia; contract until 30. 6. 2030 |
| Price today | About 1 470 EUR/t plus about 96 EUR/t freight (`nakup_vtx40_2023-2026.xlsx`) |

## 2. The situation

The supplier has written that it will renew the contract only at a price 12–22 % above the 2029 price, with a minimum
volume (`dopis_dodavatele.pdf`). In February 2026 a supply gap had to be covered at spot price. The board wants to know
whether ChemVitro should make VTX-40 itself in the EU, and where.

Eight sites in Czechia, Germany and Poland passed a first screening by site agencies (`nabidky_lokalit.pdf`). An EPC
contractor has estimated the plant at each of them (`epc_odhad.pdf`). Demand is not the question: the plant only supplies
ChemVitro's own two plants. What the board is unsure about is everything around the plant:
- competition for staff in each region, and the wages;
- the process's wastewater (acidic, with sulfates) and hazardous waste;
- fees on CO₂ emissions and on hazardous waste;
- permitting: how long it takes and what an authority can demand on top;
- transport of raw materials in and of the product to Brno and Pardubice.

## 3. The decision

**Should ChemVitro build its own VTX-40 plant, and at which of the eight sites?**

| | |
|---|---|
| Decided by | The CFO (finanční ředitelka, FR), with the board |
| Deadline | 29. 1. 2027 (board meeting); the study must be finished by 15. 1. 2027 |
| Goal | The lowest total cost of supplying VTX-40 in 2027–2044, with production running before the supply contract ends |

### The client's brief (verbatim, as typed into Zadání)

> ChemVitro dnes kupuje celou spotřebu meziproduktu VTX-40 od jednoho asijského dodavatele a smlouva končí v polovině
> roku 2030. Dodavatel chce při prodloužení výrazně zdražit. Zvažujeme vlastní závod na 40 000 t ročně a máme osm
> lokalit v Česku, Německu a Polsku. Prodávat nechceme, jde jen o naši spotřebu. Nejvíc nejistí jsme v tom, kolik nás
> lokalita bude stát navíc: odpadní vody, emise, odpady, povolení, lidé a doprava. Rozhoduje finanční ředitelka na
> představenstvu koncem ledna 2027.

## 4. The options

| Code | Site | Country, region | Client's source |
|---|---|---|---|
| 0 | Keep buying | — | `dopis_dodavatele.pdf`, `nakup_vtx40_2023-2026.xlsx` (the baseline every site is compared with) |
| CZ1 | Vrbice, Průmyslová zóna Labe-jih | Česko, Ústecký kraj | `nabidky_lokalit.pdf` p. 1 |
| CZ2 | Lipová, Park Lipová | Česko, Olomoucký kraj | p. 2 |
| CZ3 | Kamenec, Průmyslová zóna Kamenec | Česko, Moravskoslezský kraj | p. 3 |
| DE1 | Wendelstedt, Chemiepark | Německo, Sachsen-Anhalt | p. 4 |
| DE2 | Lindenau, Industriegebiet Lindenau-Ost | Německo, Sachsen | p. 5 |
| DE3 | Eschfeld, Gewerbepark | Německo, Bayern | p. 6 |
| PL1 | Odrzyca, Park Przemysłowy | Polsko, Opolskie | p. 7 |
| PL2 | Bory, Strefa Aktywności Gospodarczej | Polsko, Śląskie | p. 8 |

Every site gets the same plant: one process design (`proces_emise_odpady.xlsx`), 40 000 t a year, 95 FTE.

## 5. Constraints

Every site must meet these:
- total investment at most 175 mil. EUR, including everything the site requires (FR);
- production running by 1. 7. 2030, when the supply contract ends; after that, any shortfall is bought at spot price;
- the decision on the site is taken on 1. 2. 2027, and permit applications start then (`epc_odhad.pdf` p. 2);
- one plant, at one site.

## 6. The rule, fixed before any result

The rule is the CFO's, recorded on 2. 11. 2026:

> Recommend the site with the highest **median** saving against keeping buying, as the NPV of the total cost of supply
> 2027–2044 at 8 %, **if** it beats keeping buying with a probability of at least 0,75, **and** a loss worse than
> 20 mil. EUR against keeping buying happens in at most 10 % of futures, **and** production runs by 1. 7. 2030 with a
> probability of at least 0,80, **and** the investment stays within 175 mil. EUR. If no site passes, recommend nothing,
> and say which assumption is most worth checking.

Total cost of supply = investment, plus operating costs once the plant runs, plus VTX-40 bought until it runs, minus
the plant's residual value in 2044. Show the NPV before and after tax (each site at its country's corporate income tax rate, found in Rešerše);
the rule reads the pre-tax figure. Show the verdict at 6 % and 10 % as well.

## 7. The people

All fictional, named by role only. The codes are the ones used in `data/hodnoceni_lokalit.csv`.

| Code | Role | Stands behind |
|---|---|---|
| FR | CFO (finanční ředitelka) | the rule, the discount rate, the investment ceiling |
| GR | CEO (generální ředitel) | the decision to make rather than buy |
| VR | Head of production | the process design, the schedule, operations |
| EHS | Head of environment, health and safety | permits, emissions, waste, wastewater |
| HR | HR director | hiring, wages, the worker survey (study type 3) |
| LOG | Head of logistics | raw materials in, product out |
| NAK | Head of purchasing | the supply contract, the energy and waste offers |
| TI1, TI2 | Process engineers | the process design |
| PRA | Lawyer | contracts, permits |
| ZAM | Employee representative | |
| KON | External consultant, LokaPartner (site agency) | part of the site offers |

## 8. The client's answers

Every study gets the same answers. If a study needs to ask the client something, the answer is here. If it isn't, the
answer is "we don't know; take it as an assumption with a range and say so".

| Question | Answer |
|---|---|
| Discount rate? | 8 %, the CFO's; show 6 % and 10 % too |
| Horizon? | 2027–2044; the plant counts at a residual value of 30 % of its investment in 2044 |
| Tax? | Show before and after tax, each site at its country's corporate income tax rate; depreciation and incentives as the law sets them, found in Rešerše |
| How much VTX-40 do we need? | 34 000 t in 2026, growing 1–3 % a year; the plant makes at most 40 000 t |
| What will the renewed contract cost? | The supplier's letter: 12–22 % above the 2029 price, binding offer in mid-2029. Purchasing's best guess is 17 % |
| And if the plant is late? | Any VTX-40 needed after 30. 6. 2030 and before the plant runs is bought at spot price, as in February 2026 |
| How accurate is the EPC estimate? | ±25 % (class 4); its scope is on `epc_odhad.pdf` p. 3. The comparable plants show what happened elsewhere |
| How long do permits and construction take? | The EPC contractor's ranges (`epc_odhad.pdf` p. 2); authorities may take longer (`memo_povolovani_ovzdusi.pdf`) |
| How many people, at what wage? | 95 FTE; wages in `trh_prace_regiony.xlsx` are gross, without employer contributions; find the contributions in Rešerše |
| Will we get the incentives? | Unknown. The agencies' figures need an authority's approval. Take them as uncertain |
| Do the CO₂ and waste fees change? | Unknown; research the EU ETS price outlook and each country's hazardous-waste fees |
| Can we pilot? | No. A chemical plant is built once |
| Worker survey? | Only for study type 3: `pruzkum_pracovniku_2026.csv`. Otherwise none |
| Anything else? | No other data exists |

## 9. The client's files

### Data, [`data/`](data/)

| File | What | Used by study type |
|---|---|---|
| `nakup_vtx40_2023-2026.xlsx` | Monthly VTX-40 purchases: volume, price, freight, supplier, Jan 2023 to Sep 2026 | 1 (context), 2, 3 |
| `srovnatelne_zavody.xlsx` | 36 comparable plants built 2012–2025: investment, schedule, budget overrun, and what each built beyond the plant itself | 2, 3 |
| `lokality_parametry.xlsx` | ChemVitro's summary of the eight site offers | 1, 2, 3 |
| `trh_prace_regiony.xlsx` | Wages, unemployment, chemical workforce and hiring time per site region; workforce per country | 1, 2, 3 |
| `energie_a_poplatky.csv` | Electricity, gas, water and sewer offers per site | 2, 3 |
| `odpady_nabidky.csv` | Hazardous-waste disposal quotes per site | 2, 3 |
| `doprava_nabidky.csv` | Freight quotes per site: raw materials in, product to Brno and to Pardubice | 2, 3 |
| `ovzdusi_stanice.csv` | Annual means at the air-quality station nearest each site, 2021–2025 | 1, 2, 3 |
| `proces_emise_odpady.xlsx` | The process design per tonne: raw materials, energy, CO₂, wastewater and its composition, VOC, NOx, hazardous waste, staff | 1, 2, 3 |
| `hodnoceni_lokalit.csv` | Twelve people score the eight sites 1–10 on six criteria (10 = best for ChemVitro) | 1, 2 (expert map) |
| `pruzkum_pracovniku_2026.csv` | 300 chemical-industry workers rate how attractive working at each site would be (1–10), and answer on relocation, commuting and wage. The questions and codes are in `pruzkum_pracovniku_2026_dotaznik.md` | 3 only |

The files have not been cleaned. Checking them is part of the study, as it would be with a real client.

### Documents, [`documents/`](documents/)

| File | Pages | What |
|---|---|---|
| `zadani_projektu.pdf` | 4 | The board's project brief: the product, the supply, the targets, the worries, the team |
| `dopis_dodavatele.pdf` | 1 | Hanshin's letter on renewing the contract |
| `nabidky_lokalit.pdf` | 8 | The site agencies' offers, one page per site |
| `epc_odhad.pdf` | 3 | The EPC contractor's investment estimate per site, the schedule, and what the estimate includes and excludes |
| `vyjadreni_cov.pdf` | 8 | The wastewater operators' statements, one per site (German and Polish ones in the original, with a note) |
| `vyjadreni_doprava.pdf` | 8 | The rail and road statements, one per site |
| `memo_povolovani_ovzdusi.pdf` | 3 | A consultant's memo on air permitting in Czechia, Germany and Poland |

Each number taken from a document is cited with its page.

## 10. What to research (Rešerše)

Use public sources only, cited with a quote, the source and its date. These values are not in the pack:
- the EU ETS allowance price and its outlook (EEX, European Commission), and whether a 24 MW boiler falls under the EU ETS;
- the air-quality limit values (Directive 2008/50/EC and its revision, Directive (EU) 2024/2881) and the air-permitting rules
  for a new source in each country (Czech zákon č. 201/2012 Sb. o ochraně ovzduší, German TA Luft / BImSchG, Polish Prawo
  ochrony środowiska);
- hazardous-waste fees and landfill/incineration charges in each country (e.g. Czech zákon č. 541/2020 Sb. o odpadech);
- wages and employer contributions for chemical operators (ČSÚ, Destatis, GUS, Eurostat), and unemployment in the eight regions;
- corporate income tax rates and depreciation rules in the three countries; the nature of each incentive (cash grant or tax relief);
- industrial electricity and gas price outlooks in the three countries;
- exchange rates CZK/EUR and PLN/EUR (ČNB, ECB).

Cite provisions; give no legal advice.

## 11. Rules for every study

- Use the same files and these answers, and nothing invented. Anything missing is recorded as missing, never guessed.
- Every number carries its grade (výpočet, odhad, z dat klienta, veřejný zdroj, úsudek, právní předpis) and its source:
  file and row or page, or the quoted public source.
- The survey's respondents are pseudonymous; no respondent is named or quoted by id in a report.
- An estimate from a method that is not approved is labelled "odhad (metoda čeká na schválení metodikem)".
- Write the report in Czech, as a PDF or DOCX.
- Keep [`ANSWER-KEY.md`](ANSWER-KEY.md) closed until your report is finished.
