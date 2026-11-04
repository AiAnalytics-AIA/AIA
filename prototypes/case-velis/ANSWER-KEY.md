# Answer key: what was planted in the data

**Don't open this until your report is finished.** It's for comparing the six reports afterwards: did a study find what is really in the data, and did it say so honestly?

All the values come from `tools/generate.py` (seed `20261104`). The "measured" column is what the files themselves give, as a careful study would compute it.

## Effects

| What | Planted | Measured in the file | Where |
|---|---|---|---|
| Order loss after a one-day delay (90-day orders, delayed against control) | 3,9 % | ≈ 3,6 %; at n = 6 200 per group the 95 % interval is roughly ±3 pp | `zpozdeni_2024.xlsx`, delay sub-seed 80 |
| Share of that loss in the big cities | 55 % | ≈ 52 % (big cities ≈ 5,7 %, elsewhere ≈ 2,6 % relative loss) | the same file |
| Orders after the shipping price rose 69 → 79 Kč | −5,1 % | ≈ −5,6 % against the forecast | `objednavky_doprava_2024.xlsx` |
| Seasonality | November–December peak | November 2025 is an outlier (Black Friday), about 1,6 × an average month | `objednavky_2023-2025.xlsx` |
| Expert disagreement | The head of logistics distrusts the Polish supplier | VL scores "Riziko dodavatele" for C2 at 1 (others 4–7) and for C at 3 | `hodnoceni_expertu.csv` |
| Customer segments (survey) | 4 latent groups: fast (30 %), price-led (35 %), convenience and boxes (20 %), indifferent (15 %) | Not a column. A study that reports segments should find roughly these | `pruzkum_zakazniku_2026.csv` |
| Stated against observed | The fast-delivery segment says it would reorder less after a delay (mean ≈ 3,1 of 5) than the price-led one (≈ 4,3). Its stated willingness to pay for next day is ≈ 39 Kč, against ≈ 6 Kč for the price-led | survey means; the observed loss is in the delay file |

## Data-quality traps

| Trap | Size | Where |
|---|---|---|
| Duplicated rows | 124 (1 %) | `zpozdeni_2024.xlsx`; the same `id_zakaznika` appears twice |
| Missing kraj | 56 rows | `zpozdeni_2024.xlsx` |
| Personal column | `email`, fictional addresses | `zpozdeni_2024.xlsx`; must stay out of every computation and report |
| Orders against invoices | invoiced orders are 0,4 % fewer (cancellations before dispatch) | `objednavky_2023-2025.xlsx` against `faktury_3PL_CZ_2025.csv` |
| Logistics in the P&L against the invoices | 23,6 mil. Kč against 23,58 mil. Kč (rounding) | P&L against invoices |
| Missing expert score | OR, option A, "Služba zákazníkům" | `hodnoceni_expertu.csv` |
| Survey non-response | 11 empty ratings | `pruzkum_zakazniku_2026.csv` |

## Reconciliations that hold

- Orders: 345 000 / 376 100 / 410 000; revenue equals the P&L: 479,6 / 534,1 / 594,5 mil. Kč.
- Contribution before logistics = 300 Kč × 410 000 = 123,0 mil. Kč (P&L row 14 shows the 300 Kč).
- EBITDA 2025 = 123,0 − 23,6 − 34,0 − 26,5 − 11,6 = 27,3 mil. Kč. The balance sheet balances (120,5), and net debt is 27,0 − 31,0 = −4,0.
- Document pages: the 3PL fee is on contract p. 4, the price adjustment on p. 6 and the notice on p. 8. The hall's price is on p. 1, its schedule on p. 2, its capacity on p. 3 and its residual value on p. 4. The Polish fee is on p. 2, transport and delivery time on p. 3, capacity on p. 4 and indexation on p. 5.

## The prototype's results

The canvas ([`../obchodni-model/`](../obchodni-model/)) shows a fictional result: C2 recommended, with B2 as the hedge, and C2 best in 42 % of futures. It was drawn by hand, not computed from these files. The timing also differs: the canvas opens the hall in 2027, while this pack opens it on 1. 1. 2028, because the offer's 12 months start at signing in January 2027. A study that reaches a different answer from the data is not wrong. Say where and why the two differ.
