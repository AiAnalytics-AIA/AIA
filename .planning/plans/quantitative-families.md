---
status: planned
chunks:
  - "[ ] ACC1. The chart-of-accounts mapping in a dataset's data contract: each account to a statement line and sign, period and currency per column"
  - "[ ] ACC2. Statements: profit and loss and balance sheet from a trial balance or ledger export through the mapping; balance checks refused by name"
  - "[ ] ACC3. Ratios: a closed, defined list (liquidity, leverage, margins, turnover), each with its formula and a division by zero named"
  - "[ ] ACC4. Budget against actual: variance per line, with price, volume and mix decomposition where the contract declares quantities"
  - "[ ] ACC5. Accounting stages, charts and report blocks"
  - "[ ] FIN1. The cash-flow schedule: flows by year with a stated discount rate and horizon"
  - "[ ] FIN2. IRR (a stated root rule; several or no roots refused by name) over the MVP's NPV and payback, extended to any cash-flow schedule"
  - "[ ] FIN3. Scenarios and one-way sensitivity on NPV and IRR, reusing cost scenarios' machinery"
  - "[ ] FIN4. Pricing break-even: contribution margin, units and revenue to break even"
  - "[ ] FIN5. Price elasticity fitted from the client's price and volume data (ESTIMATED; its method owner's register entry)"
  - "[ ] FIN6. Finance stages, charts and report blocks"
  - "[ ] OR1. EOQ and reorder point (CALCULATED); safety stock from a stated demand deviation (CALCULATED) or one fitted from data (ESTIMATED)"
  - "[ ] OR2. Linear optimisation: variables, constraints and an objective as typed elements; HiGHS pinned through scipy; the optimum, binding constraints and shadow prices in words; infeasible and unbounded as named results"
  - "[ ] OR3. Demand forecasting as a model type of its own, on the MVP's backtested methods (cost-model-study CR5), for any demand series"
  - "[ ] OR4. Monte Carlo, global sensitivity and value of information on any CALCULATED type, generalising the MVP's (cost-model-study CR3, CR4, CR6)"
  - "[ ] OR5. Operations research stages, charts and report blocks"
  - "[ ] MKT1. The research_result provenance: one admitted claim of an approved research run of the same client, carrying its own grade (modelled under ADR 0024), its run, ref and artifact SHA-256"
  - "[ ] MKT2. TAM, SAM and SOM top-down as a chain of inputs, each step its own label, the chain printing the weakest"
  - "[ ] MKT3. Bottom-up from a survey's admitted share × a population count (research_result), its interval carried, labelled modelováno"
  - "[ ] MKT4. A market-sizing Deep Research purpose (an ADR 0021 amendment): queries from a person's Class B focus, never from the model; findings enter only as public_source"
  - "[ ] MKT5. Market-sizing stages, charts and report blocks"
  - "[ ] LINK1. The survey beside a model: a model revision cites one approved research run of the same client, and its report gains the run's approved map snapshot and admitted key numbers as a chapter, never combined into a model number"
---
# Quantitative families: designed now, built after the MVP

Written 2026-10-29 on the product owner's decision of the same day (relayed by the PM coordinator, ~22:06
UTC). All four families are in AIA's scope, and he chose "Design all now, build later". **Every chunk
here is designed and not scheduled: after the MVP.** In `mvp-execution-contracts.md` each is
UNSCHEDULED, "after the MVP by decision". The rules are
[ADR 0044](../../docs/architecture/adr/0044-quantitative-model-studies.md).

The platform (study kind, inputs and provenance, working copy, run, report frame, Lead, chart kinds) is
built for the MVP in [cost-model-study](cost-model-study.md) (CP1-CP10), with the `ESTIMATED` grade, the method register and the robust method of ADR 0044
decision 14 (2026-10-30: Monte Carlo, global sensitivity, backtested forecasts, value of information,
NPV and payback), all for cost scenarios. Every chunk here is a model type
on that contract, or a platform addition named as one. **Order** (Q11, 2026-10-30: "all of thesw", read by the
coordinator as every family after the MVP, side by side, no ranking): four lanes in parallel, below.
**Owner:** a session per lane, named when the lanes start. Anchors are `@ 861e19fc`.

## Estimates

Session-days on the built platform. Each family also needs its method owner's sign-off on its
definitions page from A. Bahbouh, who signs every definition and every `ESTIMATED` method (Q9, "Aram
signs these too"); that is not counted here.

| Family | Chunks | Estimate | Grades | Needs beyond the platform |
|---|---|---|---|---|
| Accounting | ACC1-ACC5 | 13-16 | CALCULATED | `client-data-in-analysis` contract (ACC1 extends it) |
| Business case and finance | FIN1-FIN4, FIN6 | 8.5-9 | CALCULATED | cost scenarios (FIN3 reuses it) |
| — price elasticity | FIN5 | 3-4 | ESTIMATED | the MVP's register; a method owner |
| Operations research | OR1-OR5 | 13-17 | both | the MVP's `ESTIMATED` methods (OR1's fitted variant, OR3, OR4) |
| Market sizing | MKT1-MKT5 | 13-16 | CALCULATED, carried grades | an ADR 0021 amendment (MKT4); ADR 0024's lift |
| The survey link | LINK1 | 2.5-3.5 | carried grades | MKT1; `report-delivery#RD4` |
| **All families** | | **53-65.5** | | |

**For a later choice:** the core plus four or five `CALCULATED` types in the MVP (cost scenarios, budget
vs actual, ratios, NPV/IRR/payback, EOQ), at about 38-48 session-days, against 30-36 for the core plus
cost scenarios before the robust method (`cost-model-study`, now 78.5-100.5 with it and the WIND map).

## Lanes (Q11: all of them, side by side)

Four sessions after the MVP, one family each, all starting once the MVP's platform has merged.
Weeks assume five session-days a week.

| Lane | Chunks | Session-days | Weeks | Waits on |
|---|---|---|---|---|
| L-FIN: business case and finance | FIN1-FIN6 | 11.5-13 | 2.5-3 | nothing beyond the MVP |
| L-ACC: accounting | ACC1-ACC5 | 13-16 | 2.5-3 | ACC1 extends the data contract (`client-data-in-analysis#2`) |
| L-OR: operations research | OR1-OR5 | 13-17 | 2.5-3.5 | nothing beyond the MVP |
| L-MKT: market sizing and the survey link | MKT1-MKT5, LINK1 | 15.5-19.5 | 3-4 | an ADR 0021 amendment before MKT4; `report-delivery#RD4` for LINK1 |
| **All four** | | **53-65.5** | **about 4** | |

- **Four sessions:** the longest lane decides the calendar, about 4 weeks.
- **Two sessions** (L-FIN then L-OR on one, L-ACC then L-MKT on the other): about 5.5-7 weeks.
- **One session:** about 11-13 weeks.

**A. Bahbouh is the shared constraint.** He signs every family's definitions page and every `ESTIMATED`
method (Q9). With four lanes at once, his reviews arrive together. Each lane's CR10-style validation pack
should reach him as soon as it is ready, not at the end, and each lane is done when it is built; the
client-report status of its numbers follows his entries.

## The `ESTIMATED` grade

Built in the MVP (`cost-model-study#CP10`): the grade, the method register and the Metodika module of
defaults. Every family below uses it; none rebuilds it.

## §ACC Accounting (13-16)

The question: *where does the money go, how healthy is the business, and where did we miss the budget?*

- **ACC1** (2-3). The data contract gains a chart-of-accounts mapping. Each account maps to a statement
  line (revenue, cost of sales, operating cost, asset, liability, equity …) with its sign; each amount
  column declares its currency and period. A ledger export with an unmapped account is refused by name,
  never summed into "other".
- **ACC2** (3-4). Profit and loss, and the balance sheet, built from a trial balance or ledger export
  through the mapping. The balance sheet that does not balance is a named result (`does_not_balance`,
  with the difference), never forced. No cash-flow statement: the indirect method needs working-capital
  definitions the method owner states first.
- **ACC3** (2). A closed list of ratios, each with its formula, its inputs and its Czech name: current,
  quick, debt to equity, interest cover, gross, operating and net margin, asset and inventory turnover,
  DSO, DPO. A zero denominator is `undefined`, never infinity or 0.
- **ACC4** (3). Budget against actual per line and period, as an absolute and a percentage. Price,
  volume and mix variance only where the contract declares quantities and prices; otherwise the total
  variance alone, with that said.
- **ACC5** (3-4). The Model stage (the mapping's review), Výsledky (statements, ratios, a variance
  waterfall) and the report blocks.

**Grades:** all `CALCULATED`, with inputs `client_dataset`. **Method owner:** A. Bahbouh (Q9).
**Tests:** a fictional trial balance through every chunk; an unmapped account refused; a balance sheet
that does not balance named; each ratio against a published worked example.

## §FIN Business case and finance (8.5-9, plus FIN5 at 3-4)

The question: *is this investment worth it, when does it pay back, and at what price do we break even?*

- **FIN1** (1.5). A cash-flow schedule: flows by year 0…N, each flow an input, a stated discount rate
  (`stated`, or `public_source` for a market rate), and the horizon.
- **FIN2** (1-1.5).
  - NPV, payback and discounted payback come from the MVP (`cost-model-study#CM7`), generalised to any
    cash-flow schedule.
  - **IRR by a stated root rule:** solved over the stated range. Exactly one root is the IRR. Several
    roots (cash flows that change sign more than once) give `multiple_irr` with each root listed; none
    gives `no_irr`. IRR is never reported for one of several roots.
  - The method text says why.
- **FIN3** (1.5). Scenarios and one-way sensitivity on NPV and IRR, through cost scenarios' sensitivity
  machinery (`cost-model-study#CM2`), generalised to any `CALCULATED` output.
- **FIN4** (1.5). Pricing break-even: contribution margin per unit, then the units and revenue needed to
  break even at a stated price, and the price needed for a stated volume.
- **FIN5** (3-4). Price elasticity from the client's price and volume rows: a log-log fit
  with its interval, its method registered. Internal until the register approves it (Q10).
- **FIN6** (3). Stages, charts (cash flows by year, the NPV profile across rates with the IRR marked,
  the tornado) and report blocks.

**Tests:** NPV and IRR against published worked examples; a two-sign-change flow returns `multiple_irr`
with both roots; payback that never comes is `none_within_horizon`.

## §OR Operations research (13-17)

The question: *how much should we order and keep, what is the best plan under our constraints, and what
demand should we plan for?*

- **OR1** (2-3).
  - EOQ, √(2DS/H), and the reorder point.
  - Safety stock as z × σ × √L for a stated service level. σ is `stated` (giving `CALCULATED`) or fitted
    from the client's demand rows (giving `ESTIMATED`).
  - The warehouse case can use it: EOQ against the storage it implies.
- **OR2** (5-6). Linear optimisation.
  - Variables, linear constraints and a linear objective as typed elements, each coefficient an input
    with provenance.
  - Solved by HiGHS through `scipy.optimize.linprog`, with the solver and version pinned in the method
    spec.
  - Results: the optimum, each variable's value, the binding constraints and their shadow prices, in
    words ("každý další m² skladu by ušetřil …").
  - `infeasible` and `unbounded` are named results, each with what the solver reports about why.
  - Integer programming is not designed: it needs a time limit and a gap rule, which makes it
    non-deterministic in practice.
- **OR3** (1-2.5). Demand forecasting as a model type of its own, for any demand series, on the MVP's
  backtested methods (`cost-model-study#CR5`): the same method set, the same rule that a forecast which
  does not beat its baseline is not used.
- **OR4** (1-1.5). Monte Carlo, global sensitivity and value of information on any `CALCULATED` model
  type, generalising the MVP's (`cost-model-study#CR3`, `#CR4`, `#CR6`): each type declares which of its
  outputs are compared.
- **OR5** (4). Stages, charts (the inventory sawtooth, the forecast with its interval band, the outcome
  histogram, LP's binding constraints) and report blocks.

**Determinism** (ADR 0044 decision 6): every OR result is stored, and its rerun under the same pins gives
the same bytes. A test per type runs on CI's platform.

## §MKT Market sizing (13-16)

The question: *how big is the market we could serve, and how much of it could we win?*

- **MKT1** (2-3). The `research_result` provenance.
  - One admitted claim of an approved research run of the same client: run id, evidence ref, the
    approved artifact's id and SHA-256.
  - It **carries its own grade**: modelled for AI respondents (ADR 0024); client-reported for a
    client's own survey.
  - A claim from an unapproved, superseded or other client's run is refused by name.
- **MKT2** (2). Top-down TAM → SAM → SOM as a chain of inputs (a population or count, then shares).
  Each step is an input with its own label (`public_source`, `stated`). The result prints the weakest
  label in its chain.
- **MKT3** (2-3). Bottom-up: a survey's admitted share (for example purchase intent) × a population count.
  - **Panel answers enter only as `research_result`:** modelled evidence under ADR 0024, labelled
    *modelováno*, the interval of the share carried to the size.
  - They reach a client only within ADR 0024's client-report lift (`MODELLED_CLIENT_REPORT_LIFT`), and
    never as a "measured" market. In the client report the size is labelled "modelováno: AI respondenti
    z populace" with its scope, under the same rule as every other modelled number (Q12, "Yes, labelled
    modelováno").
  - A top-down and a bottom-up size are shown side by side, never averaged.
- **MKT4** (4-5). Deep Research for market sizing.
  - A third Deep Research purpose, `MARKET_CONTEXT`, needs an amendment of ADR 0021.
  - Its queries are written from a person's focus (Class B by rule, `MaterialRule.JOB_INSTRUCTION`'s
    class), **never from the model's content** (Class A).
  - Its findings enter a model only as `public_source`, after a person adds the source ("Ověřeno, přidat
    zdroj"): **external context, never respondent evidence.**
  - Priced and held in the study's wallet, as other Deep Research runs.
- **MKT5** (3). Stages, charts (the TAM/SAM/SOM funnel with each step's label, top-down beside
  bottom-up) and report blocks.

**Tests:**
- a modelled share stays *modelováno* through the chain;
- a top-down and a bottom-up size are never combined;
- a Deep Research finding cannot be an input until its source is added by a person;
- a query built from a model's content is refused as Class A under `enforce`.

## LINK1. The survey beside a model (2.5-3.5)

ADR 0044 decision 12 (Q3, "Two kinds, linked later"). The model's own map is an objects ×
properties WIND map (`cost-model-study` CS1-CS5); a survey's respondent map sits beside it, never
merged.
- A model revision cites one approved research run of the same client.
- The model's report gains a chapter, "Jak možnosti vnímají respondenti": the run's approved map
  snapshot (`application/map_snapshots.py:92, 198`, `report-delivery#RD4`) and its admitted key
  numbers, each with its grade.
- No survey number enters a model output, and a cost never moves a rating.
- AI respondents stand for consumers; staff and suppliers need the client's own survey
  (`client-data-in-analysis#6`).

**Tests:** another client's run is refused; an unapproved artifact is refused; no survey ref appears in a
model output or chart; the chapter's map is the approved snapshot, byte for byte.

## Open questions (the decision page)

Answered 2026-10-30: Q9 (A. Bahbouh signs every definition and `ESTIMATED` method), Q10 (an `ESTIMATED`
number reaches a client only once he registers its method, labelled *odhad*), Q13 (defaults final as
written, in the versioned Metodika module).

Answered by 09:25 UTC: Q8 "Modely", Q11 "all of thesw" (§ Lanes), Q12 "Yes, labelled modelováno" (MKT3).
No question is open.

## Findings

None yet.

## Doc follow-up

In `cost-model-study.md` § Doc follow-up, which covers both plans: §3.3 of the master plan registers
this plan, and every chunk here is UNSCHEDULED in the contracts. Also: ADR 0021 will need an amendment
before MKT4; ADR 0024's lift scope, for MKT3, is checked when MKT3 is scheduled.
