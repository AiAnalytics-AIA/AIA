---
status: in-progress
chunks:
  - "[ ] SYS0. The methodology owner's ten questions (the pivot research's § Questions for the methodology lead) sent to A. Bahbouh as one message with each recommendation, with the SOMECS name and the published method's licence for him to check (ADR 0046 Q4); each answer recorded here as it comes; no replaced statistic built before its answer"
  - "[ ] SYS1. The synthetic validation suite, generators only: null worlds (independent random walks, AR(1) at 0.3, 0.7 and 0.95, seasonal series with no cross-relation), known factors (12 KPIs from 3 factors), a sparse VAR(1), contamination (10 % outliers, one level shift), compositional shares, 40 units × 10 drivers, 800 scenarios × 7 options from a cost model with a known Iman-Conover correlation; 1,000 seeded replicates at T or n 24, 36, 60, 120; fixtures pinned by SHA-256 like F1-F9"
  - "[ ] SYS1b. The suite run over today's -5 statistics, as the baseline the replacements are judged against; the spike's three sets (36 × 12, 40 × 10, 800 × 7) re-run with planted ground truth and its script committed"
  - "[ ] SYS2. Declared preprocessing per variable before results are seen: unit, transformation (log, log-ratio for shares), detrend or difference, deseasonalise only with two cycles, robust standardisation; reported beside every relation (answers 2, 6)"
  - "[ ] SYS3. The relation statistic: Pearson on the transformed series, or a skipped correlation where outliers are flagged, fixed before results are seen (answer 6)"
  - "[ ] SYS4. The baseline: per-variable surrogates (IAAFT by default) after detrending, checked to reproduce each series' autocorrelation; for scenarios, the imposed input correlation (answer 5)"
  - "[ ] SYS5. Pair floors replaced by an autocorrelation-adjusted effective-sample-size floor, the formula and the floor from the synthetic power curves (answer 3)"
  - "[ ] SYS6. Multiple testing: Benjamini-Yekutieli by default, q and the method reported; a resampling-calibrated FDR only on the methodology owner's approval after the suite (answer 1)"
  - "[ ] SYS7. Credibility: a block bootstrap of rows (block length declared) with Procrustes-aligned displacement per object in place of split-half; stability only, no intervals, below the minimum length (answer 4); for the scenario map no block bootstrap: stability across seeds and assumptions, with and without each future's mean (ADR 0046 decision 5)"
  - "[ ] SYS8. Fit beside the layout: stress-1 and stress per point against a random-data benchmark and a permutation test; the layout, terrain and determinism unchanged"
  - "[ ] SYS9. The scenario mode: rows a model's Monte Carlo scenarios (>= 800, cost-model-study CR3), the imposed correlation as the baseline, grade MODELLED, the claim 'in this model, A and B move together'; consumed by cost-model-study CS1-CS5"
  - "[ ] SYS10. The expert mode: options or competitors scored by named people on criteria, grade MODELLED with the inputs stated; consumed by situation-reports EX1-EX2"
  - "[ ] SYS11. The unit and period modes, only after the suite passes at the methodology owner's thresholds (answer 7): units placed with density above a stated n, periods as a trajectory, failing edges not drawn, regimes only from a declared break; ESTIMATED, INTERNAL_ONLY until registered"
  - "[ ] SYS12. Each mode a Metodika register entry of its own (ADR 0023), INTERNAL_ONLY until approved; the never-claim list as copy on screen and in the report; the name Sociomapa systémů, never SOMECS, and A. Bahbouh's check of the name and the published method's licence recorded before any client reads it (ADR 0046 Q4, A12)"
  - "[x] SYS13. Indicator height (SM10, Q-IMPORT): domain/sociomap/systems/importance.py, permutation_importance (the score drop per indicator on unseen test rows, with an interval, grade doloženo) and declared_importance (grade odhad, author required); test_sociomap_systems"
  - "[x] SYS14. Futures against the real world (SM11, Q-FUTSCALE): systems/future_scale.py, scale_futures (history percentile, else declared range, else own spread flagged; warning outside 0.5-2 times history's 5-95 % width)"
  - "[x] SYS15. The month test (SM12, Q-TIMETEST; answers 1-5): systems/months.py, month_relations (declared trend, Pearson, IAAFT p-values with the autocorrelation check, Benjamini-Yekutieli, Pyper-Peterman effective months, MIN_MONTHS 36 with TooFewMonths, the declared false-pair rate carried to print); the statistics of SYS3-SYS6 as functions, not yet in the engine"
  - "[x] SYS16. Minimum rows (SM13, Q-MINROWS): systems/minimum_rows.py, minimum_rows from planted runs and DeclaredRates, check_rows with the named refusal, STARTING_MINIMUM months 36 and experts 12"
  - "[x] SYS17. Stability (SM14, Q-LINES): systems/stability.py, map_stability (moving-block bootstrap, Procrustes, 90 % radius per object, the median displacement as the printed stability number), SHOW_CIRCLES_BY_DEFAULT False; the block bootstrap of SYS7 as a function"
  - "[x] SYS18. One-sided relations (SM15, Q-ONEWAY): systems/one_sided.py, symmetric_part for the layout and arrows_that_pass (the asymmetry keeps its sign over the redraws)"
  - "[x] SYS19. Konkurence (SM16, Q-KONK): systems/coverage.py, weighted_coverage"
  - "[x] SYS20. Vlivy (SM17, Q-VLIVY): systems/influence.py, influence_map (MIN_RATERS 5 with TooFewRaters, median per cell, ordinal Krippendorff's alpha, disputed cells, DEMATEL total influence on the outcome else driving power, grade odhad); krippendorff_alpha reproduces Krippendorff (2011)'s published 0.743 / 0.849 / 0.815"
  - "[x] SYS21. Register label per input (SM18, Q-METH): systems/register.py, input_status with AWAITING_LABEL"
  - "[ ] SYS22. Wire systems/ into compute_object_map and the artifact for each map input (months, units, futures, experts, profile, Konkurence, Vlivy): only accepted relations as lines, arrows from arrows_that_pass, heights from importance or influence, the minimum and the stability number recorded; behind a kill switch, off in test"
  - "[ ] SYS23. The web: lines and arrows from the artifact, the uncertainty-circle switch in Nastavení mapy (off by default), the minimum, the stability number, the false-pair rate and AWAITING_LABEL printed on every map"
  - "[ ] SYS24. The planted-answer suite (SYS1) run through systems/ per input; each input's DeclaredRates stated first, its minimum_rows recorded here, then its register entry (SYS12)"
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


## Decisions of 24 Nov 2026 (methodology session; MVP Map SM10-SM18)

Taken with A. Bahbouh in a session on 24 Nov 2026 and recorded on the AIA MVP Map's Decisions tab.
They answer Q-IMPORT, Q-FUTSCALE, Q-TIMETEST (Aram's questions 1-5: Benjamini-Yekutieli; a trend
declared first; Pyper & Peterman, modified; 36 months, describe only below; IAAFT, 1,000 per
series), Q-MINROWS, Q-LINES, Q-ONEWAY, Q-KONK, Q-VLIVY and Q-METH. SYS13-SYS21 build them as pure
functions in `domain/sociomap/systems/`; SYS22-SYS24 wire them in.

- **SM10 Q-IMPORT.** Height on indicator maps = the drop in a tested model's score when the
  indicator is shuffled on unseen years, with an interval; with no tested model, a declared weight
  printed as odhad with its author. Never correlation on the map's own data.
- **SM11 Q-FUTSCALE.** Futures against realised history of the same quantity, else a declared
  range, else their own spread, flagged; a warning when they are much narrower or wider than
  history.
- **SM12 Q-TIMETEST.** The bundle above, plus the false-pair rate on planted no-link data declared
  before use and printed on every month map.
- **SM12 amendment (24 Nov 2026, user's decision).** The surrogate null is pooled over all pairs.
  A pair's own null cannot give p below 1 / (2 x surrogates + 1), and Benjamini-Yekutieli multiplies
  the smallest p by pairs x sum(1/i): with 1,000 surrogates no relation could pass from about 12
  series (66 pairs) on, however strong. Pooled, a planted pair among 12 series passes
  (`test_month_relations_can_pass_a_planted_pair_among_many_series`). AIA_SW applies the same rule
  to its object relations.
- **SM13 Q-MINROWS.** Each input's minimum from its planted-answer test; below it a table, refused
  by name; starting values months 36, experts 12; printed on every map.
- **SM14 Q-LINES.** Lines only for tested relations; an uncertainty circle per point (90 % of its
  aligned displacement) as a switch, off by default; one stability number always printed.
- **SM15 Q-ONEWAY.** Layout from the mean of both directions; arrows only for a tested asymmetry.
- **SM16 Q-KONK.** Weighted coverage: sum w min(a, b) / sum w b, on rows scaled to the real world.
- **SM17 Q-VLIVY.** At least 5 raters, median per cell, Krippendorff's alpha printed, disputed
  cells without lines; height = total influence on the outcome, else driving power; grade odhad.
- **SM18 Q-METH.** One register entry per input, after its own planted-answer test; until then
  "metoda čeká na schválení metodikem".

The 2 Nov wording above (four modes, MODELLED, 800 scenarios) is the subject of Q-PLANWORDS and is
not rewritten here.

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
- A structure is never called real unless it passes its mode's contract (ADR 0046 decision 5): the
  period map's surrogate null after FDR and the block bootstrap; the scenario map's stability across
  seeds and assumptions, with no p-value and no block bootstrap; the expert map's rater resampling; the
  unit map's cluster resampling.
- A distance is never read as an effect size, and a terrain height between observed points is never
  read as an estimate.
- Regimes are never drawn from 24-36 months without a declared break.
- The method's validity is never argued from Sociomapping's team-communication evidence (A5).
