---
status: planned
chunks:
  - "[ ] SYS0. The methodology owner's ten questions (the pivot research's § Questions for the methodology lead) sent to A. Bahbouh as one message with each recommendation, with the SOMECS name and the published method's licence for him to check (ADR 0046 Q4); each answer recorded here as it comes; no replaced statistic built before its answer"
  - "[ ] SYS1. The synthetic validation suite, generators only: null worlds (independent random walks, AR(1) at 0.3, 0.7 and 0.95, seasonal series with no cross-relation), known factors (12 KPIs from 3 factors), a sparse VAR(1), contamination (10 % outliers, one level shift), compositional shares, 40 units × 10 drivers, 800 scenarios × 7 options from a cost model with a known Iman-Conover correlation; 1,000 seeded replicates at T or n 24, 36, 60, 120; fixtures pinned by SHA-256 like F1-F9"
  - "[ ] SYS1b. The suite run over today's -5 statistics, as the baseline the replacements are judged against; the spike's three sets (36 × 12, 40 × 10, 800 × 7) re-run with planted ground truth and its script committed"
  - "[ ] SYS2. Declared preprocessing per variable before results are seen: unit, transformation (log, log-ratio for shares), detrend or difference, deseasonalise only with two cycles, robust standardisation; reported beside every relation (answers 2, 6)"
  - "[ ] SYS3. The relation statistic: Pearson on the transformed series, or a skipped correlation where outliers are flagged, fixed before results are seen (answer 6)"
  - "[ ] SYS4. The baseline: per-variable surrogates (IAAFT by default) after detrending, checked to reproduce each series' autocorrelation; for scenarios, the imposed input correlation (answer 5)"
  - "[ ] SYS5. Pair floors replaced by an autocorrelation-adjusted effective-sample-size floor, the formula and the floor from the synthetic power curves (answer 3)"
  - "[ ] SYS6. Multiple testing: Benjamini-Yekutieli by default, q and the method reported; a resampling-calibrated FDR only on the methodology owner's approval after the suite (answer 1)"
  - "[ ] SYS7. Credibility: a block bootstrap of rows (block length declared) with Procrustes-aligned displacement per object in place of split-half; stability only, no intervals, below the minimum length (answer 4)"
  - "[ ] SYS8. Fit beside the layout: stress-1 and stress per point against a random-data benchmark and a permutation test; the layout, terrain and determinism unchanged"
  - "[ ] SYS9. The scenario mode: rows a model's Monte Carlo scenarios (>= 800, cost-model-study CR3), the imposed correlation as the baseline, grade MODELLED, the claim 'in this model, A and B move together'; consumed by cost-model-study CS1-CS5"
  - "[ ] SYS10. The expert mode: options or competitors scored by named people on criteria, grade MODELLED with the inputs stated; consumed by situation-reports EX1-EX2"
  - "[ ] SYS11. The unit and period modes, only after the suite passes at the methodology owner's thresholds (answer 7): units placed with density above a stated n, periods as a trajectory, failing edges not drawn, regimes only from a declared break; ESTIMATED, INTERNAL_ONLY until registered"
  - "[ ] SYS12. Each mode a Metodika register entry of its own (ADR 0023), INTERNAL_ONLY until approved; the never-claim list as copy on screen and in the report; the name Sociomapa systémů, never SOMECS, and A. Bahbouh's check of the name and the published method's licence recorded before any client reads it (ADR 0046 Q4, A12)"
---
# Sociomapa systémů: the Sociomap on business systems

Written 2026-11-02 under [ADR 0046](../../docs/architecture/adr/0046-business-decisions-pivot.md)
decision 5. The research behind it is
[`../evidence/pivot-research-2026-11-02.md`](../evidence/pivot-research-2026-11-02.md), sections A and
"Sociomapa systémů method recommendation".

**The rule.** Keep the engine's layout, terrain, sparse design and determinism. Replace its statistics
for business rows, because they do not hold on autocorrelated data (A1-A4). The modes ship in this
order:
1. The scenario map and the expert map, in the MVP at the owner's word ("Both maps in the MVP").
2. The unit and period maps, only after the synthetic suite passes.

**Owner:** S2 with the methodology owner, A. Bahbouh, who decides every statistical choice. Proposed;
the session that takes it reviews this plan first.

## Open: what the maps draw (ADR 0046 W24)

The owner, 2 Nov, in the walkthrough: "i think we still have to rethink what the maps draw, lets leave
this open for now". Who scores on the expert map and how many raters wait on it, and so do SYS9 and
SYS10. The validation suite (SYS0-SYS1b) does not wait.

## What the MVP's maps must do

The owner, 2 Nov (ADR 0046 A6, "Show option clusters"): the scenario and expert maps show which options
win in the same futures, and which hedge each other. A map explains a decision; it never makes one.
SYS9 and SYS10 are judged by this: the clusters and the hedges it draws must be the ones the synthetic
suite planted (SYS1), and each reaches the report outline as a point with its method link
(`research-findings-stage#FND10`).

## What is reused

- **The `aia-sociomap-5` engine's layout and terrain.** These are
  `domain/sociomap/signed_off_layout.py` and `signed_off_respondents.py`'s density. Only the input
  matrix and the statistics around it change.
- **The H-Model, WIND and objects × properties work.** That is `sociomapping-engine` 1a, 2a and 2c, 4b
  and 11, which `cost-model-study` CS2-CS5 and `situation-reports` EX2 consume.
- **Metodika (ADR 0023).** Each mode is a method a run pins.

## Never claim (in every mode)

- A map never says a relation is causal.
- A scenario map never says it shows how the market or the firm behaves.
- A structure is never called real unless it beats its surrogate null after FDR and survives
  resampling.
- A distance is never read as an effect size, and a terrain height between observed points is never
  read as an estimate.
- Regimes are never drawn from 24-36 months without a declared break.
- The method's validity is never argued from Sociomapping's team-communication evidence (A5).
