# Velis Commerce: the case

**Fictional.** Velis Commerce s.r.o. and every company, person and number in this pack are invented. It is the same
case as the business-model canvas ([`../obchodni-model/`](../obchodni-model/)), so the reports can be read beside
that prototype.

This file is the whole context a study needs: the company, the decision, the options, the rule, the people, the client's answers and an inventory of every file. Every study starts from it and from nothing else. When a study needs a fact this file doesn't give, the fact either comes from the client's files in [`data/`](data/) and [`documents/`](documents/), or from public sources found in Rešerše, with a citation. Otherwise it is recorded as missing. A study never invents a fact.

## 1. The company

| | |
|---|---|
| Name | Velis Commerce s.r.o. (fictional), Praha |
| Business | Online shop for clothing and accessories in the Czech Republic, founded 2016 |
| 2025 | 410 000 orders · 128 000 customers · revenue 594,5 mil. Kč without VAT · EBITDA 27,3 mil. Kč · net cash 4 mil. Kč |
| Growth | Orders up about 9 % a year (345 000 in 2023, 376 100 in 2024) |
| Logistics today | Outsourced since 2021 to Delta Fulfillment CZ s.r.o. (fictional), warehouse in Modřice: picking, packing and handover to carriers. Velis's own 800 m² warehouse in Jihlava handles only returns and the outlet |
| Delivery promise | Next working day in Praha, Brno, Ostrava and Plzeň; within two working days elsewhere |
| Customers | 46 % under 35; 38 % live in the four big cities and place 40 % of the orders |

## 2. The situation

Orders keep growing, and Delta Fulfillment CZ raises its prices every year (the contract allows 3–7 %, and 5 % is expected for 2027). Velis has three offers on the table:
- an extension of its own warehouse by 2 000 m², to run fulfilment itself;
- a Polish 3PL that is cheaper but delivers one day later;
- from its current 3PL, a five-year fixed price in exchange for a surcharge.

An express courier has also offered next-day delivery in the big cities from the Polish warehouse.

Management must decide before the 2027 budget is closed.

## 3. The decision

**Where should Velis store and dispatch its orders in 2026–2032?**

| | |
|---|---|
| Decided by | The CFO, with the management team |
| Deadline | 15. 12. 2026 (budget 2027); the study must be finished by 8. 12. 2026 |
| Goal | The highest contribution after logistics over 7 years, without weakening the delivery promise in the big cities |

### The client's brief (verbatim, as typed into Zadání)

> Velisu rostou objednávky asi o 9 % ročně a český 3PL zdražuje. Klient má nabídku na rozšíření vlastního skladu
> o 2 000 m² a nabídku polského 3PL, který je levnější, ale doručí o den později. Chce vědět, co mu na 7 let
> přinese nejvíc, a nechce ztratit zákazníky, kterým dnes slibuje doručení do dvou dnů. Rozhoduje finanční ředitel
> do poloviny prosince, kvůli rozpočtu na 2027.

## 4. The options

The client brought A, B and C. A2, B2, C2 and H are the combinations proposed in Zadání, and the client accepted them.

| | Option | What it means | Client's source |
|---|---|---|---|
| A | Own warehouse +2 000 m² | Velis runs fulfilment itself from 1. 1. 2028; above capacity, the overflow goes to Delta Fulfillment CZ | `nabidka_hala.pdf` |
| A2 | Warehouse in stages | 60 % of the hall from 1. 1. 2028, the rest from 1. 1. 2030 | `nabidka_hala.pdf` |
| B | Stay with the Czech 3PL | Change nothing; the baseline every option is compared with | `smlouva_3PL_CZ.pdf` |
| B2 | Czech 3PL, fixed price | The five-year fixed-price amendment | `dodatek_3PL_CZ_email.pdf` |
| C | Polish 3PL | Cheaper rates; delivery one day longer everywhere | `nabidka_3PL_PL.pdf` |
| C2 | Polish 3PL + express | As C, with next-day express in the four big cities | `nabidka_3PL_PL.pdf`, `nabidka_kuryr_expres.pdf` |
| H | Hybrid | Big cities from the Czech 3PL, the rest from the Polish 3PL | both 3PL documents |

## 5. Constraints

Every option must meet these:
- investment at most 90 mil. Kč (the CFO);
- a move to another 3PL no earlier than 1. 7. 2027, because of the six-month notice period (contract p. 8);
- the hall handles 620 000 orders a year and opens on 1. 1. 2028: the permit is already granted, Velis would sign by 4. 1. 2027, and construction takes 12 months (hall offer p. 2–3). Until then A and A2 stay with Delta Fulfillment CZ;
- the delivery promise in the big cities must not get worse (the sales director).

## 6. The rule, fixed before any result

The rule is the CFO's, recorded on 14. 10. 2026:

> Recommend the option with the highest **median** contribution after logistics, as NPV 2026–2032 at 8 % compared with B, **if** it beats B with a probability of at least 0,80 **and** a loss worse than 10 mil. Kč against B happens in at most 10 % of futures. The delivery promise in the big cities must not get worse. If no option passes, recommend nothing, and say which assumption is most worth checking.

Show the NPV before and after tax (21 %); the rule reads the pre-tax figure. Show the verdict at 6 % and 10 % as well.

## 7. The people

All fictional, named by role only. The role codes are the ones used in `data/hodnoceni_expertu.csv`.

| Code | Role | Stands behind |
|---|---|---|
| FR | CFO (finanční ředitel) | the rule, the risk limit, the discount rate, contribution per order, the investment |
| OR | Sales director (obchodní ředitelka) | order growth, the delivery promise, the pilot |
| VL | Head of logistics (vedoucí logistiky) | warehouse costs, capacity, the transition plan |
| VN | Head of purchasing (vedoucí nákupu) | the 3PL and courier prices |
| MK | Head of marketing (vedoucí marketingu) | customers, the survey (study type 3) |

## 8. The client's answers

Every study gets the same answers. If a study needs to ask the client something, the answer is in this table. If it isn't, the answer is "we don't know; take it as an assumption with a range and say so".

| Question | Answer |
|---|---|
| What worst loss against today can management accept? | 10 mil. Kč, in at most 1 future in 10 |
| Investment ceiling? | 90 mil. Kč |
| Can the new set-up be piloted first? | Yes: one region, 3 months, from March 2027 at the earliest (OR) |
| Discount rate? | 8 %, the CFO's; show 6 % and 10 % too |
| Tax? | Show both before and after tax (21 % corporate income tax); depreciation as the law sets it, to be found in Rešerše |
| Horizon? | 7 years, 2026–2032; the hall counts at its residual value in year 7 |
| Order growth? | 9 % a year most likely, 4–14 % possible (OR) |
| Contribution per order before logistics? | 300 Kč in 2025, 260–340 Kč possible (FR) |
| How many orders does a one-day delay cost? | Marketing guesses 0–12 %. The data in `zpozdeni_2024.xlsx` may say more |
| Transition cost to another 3PL? | See `plan_prechodu.xlsx` (VL) |
| Do the two 3PLs' prices move together? | The sales director sees no link. The head of logistics thinks wages drive both |
| When would each option start? | A, A2: the hall from 1. 1. 2028, Delta Fulfillment CZ until then. B2: the fixed price from 1. 1. 2027. C, C2, H: the move on 1. 7. 2027, after notice given in December 2026 |
| Overflow above the hall's capacity? | Goes to Delta Fulfillment CZ at its contract price |
| Competitor delivery times and prices? | Velis has no data; research them if needed |
| Customer survey? | Only for study type 3: `pruzkum_zakazniku_2026.csv`. Otherwise none |
| Anything else? | No other data exists |

## 9. The client's files

### Data, [`data/`](data/)

| File | What | Period | Used by study type |
|---|---|---|---|
| `objednavky_2023-2025.xlsx` | Monthly orders, revenue, average order, returns; orders by kraj in 2025 | 2023–2025 | 1 (context), 2, 3 |
| `vysledovka_rozvaha_2023-2025.xlsx` | P&L by year with the 2025 plan; balance sheet | 2023–2025 | 1, 2, 3 |
| `faktury_3PL_CZ_2025.csv` | Delta Fulfillment CZ's monthly invoices | 2025 | 2, 3 |
| `zakaznici_souhrn_2025.xlsx` | CRM summary: age, big city or not, purchase frequency. No personal data | 2025 | 1, 2, 3 |
| `zpozdeni_2024.xlsx` | 6 200 orders delayed by a carrier outage in December 2024, a matched control group of 6 200, and each customer's orders in the next 90 days. **Contains a personal column** (`email`) | Dec 2024 to Mar 2025 | 2, 3 |
| `objednavky_doprava_2024.xlsx` | Weekly orders before and after the shipping price rose from 69 to 79 Kč, against marketing's forecast | Mar–Aug 2024 | 2, 3 |
| `plan_prechodu.xlsx` | Transition cost to another 3PL by item: min, likely, max (VL) | Oct 2026 | 2, 3 |
| `hodnoceni_expertu.csv` | Five managers score the seven options 1–10 on five criteria (10 = best for the company) | Oct 2026 | 1, 2 (expert map) |
| `pruzkum_zakazniku_2026.csv` | 800 customers rate eight delivery experiences 1–10, say whether they would reorder after a one-day delay (1–5), and what they would pay for next-day delivery. The questions as asked and every scale's anchors are in `pruzkum_zakazniku_2026_dotaznik.md` | Oct 2026 | 3 only |

The files have not been cleaned. Checking them is part of the study, as it would be with a real client.

### Documents, [`documents/`](documents/)

| File | Pages | What |
|---|---|---|
| `smlouva_3PL_CZ.pdf` | 9 | The current 3PL contract: fees, storage, price adjustment, notice |
| `dodatek_3PL_CZ_email.pdf` | 1 | Delta Fulfillment CZ's fixed-price offer (B2) |
| `nabidka_hala.pdf` | 6 | The warehouse extension: price, schedule, capacity, residual value, running costs |
| `nabidka_3PL_PL.pdf` | 7 | Wisła Fulfilment's offer (C): fees, transport, delivery times, capacity, indexation, term |
| `nabidka_kuryr_expres.pdf` | 1 | Rychlík Kurýr's next-day express in the big cities (C2) |

Each number taken from a document is cited with its page.

## 10. What to research (Rešerše)

Use public sources only, cited with a quote, the source and its date. These values are not in the pack, so each study finds them itself:
- Czech online clothing and accessories market: size and growth (e.g. ČSÚ, APEK, Eurostat);
- wage growth in transport and storage, in Czechia (ČSÚ, CZ-NACE H) and Poland (GUS);
- Czech inflation forecast (ČNB);
- prices and delivery times of Czech and Polish 3PL fulfilment, and of competitors' delivery offers;
- the law: the corporate income tax rate and the depreciation group of a warehouse hall (zákon č. 586/1992 Sb.), the notice rules for the contract (zákon č. 89/2012 Sb.), and GDPR for the personal column in the delay data. Cite provisions; give no legal advice.

The canvas uses placeholder market figures (41 mld. Kč, +7 %). They are fictional and are not to be copied.

## 11. Rules for every study

- Use the same files and these answers, and nothing invented. Anything missing is recorded as missing, never guessed.
- Every number carries its grade (výpočet, odhad, z dat klienta, veřejný zdroj, úsudek, právní předpis) and its source: file and row or page, or the quoted public source.
- The personal column stays out of every computation and every report.
- An estimate from a method that is not approved is labelled "odhad (metoda čeká na schválení metodikem)".
- Write the report in Czech, as a PDF or DOCX.
- Keep [`ANSWER-KEY.md`](ANSWER-KEY.md) closed until your report is finished.
