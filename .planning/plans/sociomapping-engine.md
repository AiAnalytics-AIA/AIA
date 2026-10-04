---
status: planned
chunks:
  - "[ ] 0. Methodology decision record v2 and SOMECS golden fixtures (S1-S8)"
  - "[ ] 1. Fuzzy matrix contract: from STORM data, from object properties, aggregation, legacy bridge"
  - "[ ] 2. H-Model layout (h_model_v1): asymmetric distance fit, Spearman accuracy, multi-start, locks, margins"
  - "[ ] 3. STORM placement (storm_placement_v1): respondents against fixed objects, per-row fit, edge rule"
  - "[ ] 4. WIND terrain (inverse-distance heights) beside terrain66; STORM mass; contour levels"
  - "[ ] 5. Fit reporting: Spearman accuracy, per-point fit, H-Model density significance; D6 threshold"
  - "[ ] 6. Coherences (alpha-cuts), zoom groups, HM correction"
  - "[ ] 7. Spec v3, preset sociomapping-somecs-1, engine and research adapter wiring, artifact v3, ledgers"
  - "[ ] 8. Regions and statistics: A vs complement, A vs B, t / chi-square, effect sizes, multiplicity policy, phrases"
  - "[ ] 9. Overlays as view layers: arrows (RTS rules), shortest path, combine maps, coherence contours"
  - "[ ] 10. Time: positions taken from a reference map, wave alignment, time-series frames, animation"
  - "[ ] 11. Results UI: STORM and WIND views from the artifact, top view default, fit badge, regions, arrows"
  - "[ ] 12. Report pages and the client-facing gate (OI-17) once D6 is signed"
---
# Sociomapping engine: upgrade AIA's Sociomap to the published methodology

**Owner of the method:** Radvan Bahbouh (QED Group). This plan is written for a product
built on his behalf, so every open question below is his to answer directly, not ours to
infer. **Oracle:** the SOMECS software (Sociomap-based Models of Economic Systems) and its
documentation, the way the 18.6.6 unit was the oracle for the strangler. **Base:** `develop`
@ `cf08fac`; PR 116 head `7c1e012` reviewed on 2026-10-04.

## Why

AIA has three different Sociomap computations and none is the method as SOMECS defines it:

| Path | What places objects | What places respondents | Fit reported | Height |
| --- | --- | --- | --- | --- |
| `AIA_SOCIOMAP_V1` (`aia_rowcond_unfolding_v1`) | joint rating unfolding with respondents | the same unfolding | stress-1 | object metric, Gaussian kernel mean (terrain66) |
| 18.6.6 `sociomap.py` (`fit_python_unfolding`, `fit_relational_landscape`) | ipsatised rating unfolding; separately an MDS of a 1-10 relation matrix | the same unfolding | stress | HTML bubbles |
| 18.6.6 `visualization_lab.py`, ported by PR 116 | 800-step spring loop on correlation strength | barycentre of fixed anchors, weights max(0, r - 5) | none | respondent density, Gaussian kernel |

SOMECS (help, § O programu, Slovníček, H-Model, Mapy) defines the pipeline as
**DATA → MATICE → H-MODEL → MAPY**:

1. **Data.** STORM data: subjects × objects, optionally over several *aspects* with
   weights 0-1, plus subject characteristics and one text-info column. (STORM = Subjects
   To Objects Relation Mapping.)
2. **Fuzzy matrix.** A square n × n matrix of relations in 0-1 (row element to column
   element; higher is closer; not necessarily symmetric). Built from STORM data by one of
   three normalisations (within a row, within the database, cardinal to ordinal ranks) or
   from an objects × properties table by Euclidean, Manhattan or correlation similarity
   after declared scale extremes (SOMECS Input, fig. 6). Compatible matrices aggregate as a
   weighted mean under a discrepancy threshold.
3. **H-Model.** The horizontal model: elements placed in the plane so that Euclidean
   distances correspond to the fuzzy-matrix distances *while preserving asymmetry* (C is
   nearest to B while B is nearest to A). **Accuracy is the Spearman correlation between
   the Euclidean distance matrix and the fuzzy matrix**, shown as a percentage; each point
   carries its own fit and an importance weight; points can be locked; iterating again
   finds another local optimum; "HM correction" trades fit for coherence proximity;
   positions live in 0-1 with small/bigger/huge margins; positions can be taken over from
   another matrix of the same type. The H-Model density module gives the distribution of
   the Spearman coefficient, i.e. how significant a fit is.
4. **Maps.** A **STORM map** shows the concentration of subjects, each placed where its
   attitude to the objects is best captured: fans next to their favourite, the undecided
   between objects, those preferring none at the edges or corners. A **WIND map**
   (Weighted INverse Distance) keeps the same horizontal positions and interpolates one
   object variable as height (column sums of the matrix, sums of STORM ratings, a
   characteristic, a custom value, or the inverse). Regions A and B are tested (t-test for
   continuous, chi-square for discrete characteristics, p-value), significant regions are
   searched, phrases are compared, maps of the same type animate (linear interpolation or
   a dynamic H-Model) and can be combined, extrapolated and framed over time windows.

The sociomap.com design description adds the team-diagnostics layer: a map's positions
come from mutual ratings and its heights from received averages; arrows mark a wish for
more communication (desired − current ≥ 2) or low quality (1-2 on 1-5); object maps carry
arrows for significant negative correlations; 30 elements at most, about 20 recommended;
subteam maps from 4 members.

**Consequence.** The redevelopment is not a new layout algorithm. It is a new *contract*
(fuzzy matrix in, H-Model out, STORM placement against it, WIND height on it, a Spearman
fit with significance) with SOMECS fixtures as the gate, and the existing engine kept
as a named alternative for comparison. The 18.6.6 unit stops being the oracle for this
capability; its two layouts stay refused (OI-13, OI-15) unless the owner wants them.

## Boundaries that do not move

- Pure Python domain under `packages/aia_core/src/aia_core/domain/sociomap/`; stdlib +
  Pydantic; bit-identical on every host; every algorithm declared in the spec, never
  detected (ARCHITECTURE § boundary, `require_supported`).
- A number reaches a client only as an `AdmittedClaim`; the map stays `INTERNAL_ONLY`
  until D6 is signed and OI-17's gate exists.
- Unknown is never neutral (A4). SOMECS substitutes 0 for a missing rating (help, Data
  § Úvod); that is a declared policy the owner must accept or replace, never a default.
- Presentation reads the artifact and never writes it (`view.py`). Overlays, regions,
  arrows and animation are layers over an immutable base.
- Shared docs change in a docs PR; this plan and the PR description carry the follow-ups.

## Open methodology decisions (chunk 0 collects the answers)

Each one blocks the chunk named; the owner answers, the answer lands in
`docs/architecture/sociomapa-methodology-decision.md` v2 through the docs PR.

| # | Question | Blocks | Our default if unanswered |
| --- | --- | --- | --- |
| M1 | How does SOMECS derive the n × n fuzzy matrix from STORM data (subjects × objects)? Row/database/ordinal normalisation is documented; the subject-to-relation step is not. | 1, 2 | refuse: no fuzzy matrix from ratings without the rule |
| M2 | The exact H-Model objective: Spearman over all off-diagonal cells, or row-conditional (within each row), and how asymmetry enters (two directed targets per pair?). | 2 | row-conditional ordinal fit, Spearman reported over all cells, both directions as separate targets |
| M3 | The STORM placement rule for a subject given fixed object positions, and the rule for "prefers none" subjects at the edge. | 3 | external row-conditional unfolding with objects fixed; a row whose fit is undefined goes to the rim and is counted |
| M4 | WIND interpolation: inverse-distance exponent and search radius; is 18.6.6's Gaussian terrain66 an accepted re-implementation or a departure? | 4 | implement IDW with exponent as a spec parameter; keep terrain66 as a second declared method |
| M5 | Missing STORM cell: 0 (SOMECS), exclude the cell (AIA), or exclude the row? | 1, 3 | exclude the cell; refuse a row with fewer than two observed cells |
| M6 | The fit level below which a map may not be delivered, and whether the H-Model density p-value is the gate. | 5, 12 | none chosen; D6 stays open |
| M7 | Respondent (population) weights: do they enter the fuzzy matrix, the STORM mass, the WIND heights, or nothing? | 1, 4 | nothing; unweighted, labelled |
| M8 | Multiple-testing policy for region tests over many characteristics. | 8 | Holm; every p-value stored raw and adjusted |
| M9 | Is the 18.6.6 Visualization Lab (PR 116) his intended simplification for market research or a prototype shortcut? | 11 | keep it as "Visualization Lab", internal, off by default; never call it a Sociomap |
| M10 | Extrapolation (the next frame of an animation): which model? | 10 | not implemented; the control is absent |

## Chunks

### 0. Methodology decision record v2 and SOMECS golden fixtures
- Collect M1-M10 with the owner; write the answers as declarations with formulas.
- Obtain from SOMECS, on a small fictional dataset (the Drinks example from the help or a
  purpose-built one), every intermediate: the STORM data, the fuzzy matrix under each
  normalisation, the H-Model positions with its Spearman accuracy and per-point fit, the
  STORM map mass grid, the WIND map heights for two height choices, a region test result,
  and two frames of an animation. Vendor them as **S1-S8** under
  `packages/aia_core/tests/fixtures/sociomap/`, pinned by SHA256 in
  `docs/migration/parity-matrix.json`, each with the tolerance the owner accepts (positions
  are compared after Procrustes alignment, because the H-Model has local optima).
- Record the SOMECS version and the export format (.smp, .smx, CSV from the HMODEL module).
- **Done when:** the decision document carries M1-M10 with an answer or an explicit
  "deferred", and the eight fixtures load with their pins verified.

### 1. Fuzzy matrix contract
- `domain/sociomap/fuzzy.py`: `FuzzyMatrix` (n × n, values 0-1, diagonal undefined,
  asymmetry allowed, element ids, provenance), `from_storm_data(ratings, aspects,
  normalisation, missing_policy)` with the three normalisations and aspect weights 0-1,
  `from_properties(table, extremes, method)` with Euclidean / Manhattan / correlation and
  the sign convention for lower-is-better, `aggregate(matrices, weights, discrepancy)`.
- Bridge: `coerce_relation_scale_1_10` already accepts a 0-1 similarity (F1); add the
  inverse so a stored 1-10 relation becomes a `FuzzyMatrix` with its origin recorded.
- SOMECS Input's data-quality indicator (five stars, OK/GOOD/FAIR/POOR) as a computed
  quality record with reasons; it never blocks, it is shown.
- **Tests:** S2 (each normalisation), S1 (properties → similarity), aggregation with a
  discrepancy refusal, missing policy per M5. Gate on `sociomapping.core`.

### 2. H-Model layout `h_model_v1`
- `layout.py` gains `h_model_v1`: input `FuzzyMatrix`; output positions in the 0-1 frame
  with the chosen margin, Spearman accuracy, per-point fit, iterations, seed, the
  objective per M2. Multi-start from a declared seed list, the best kept, all accuracies
  recorded. Locked points and per-point importance weights as parameters. Procrustes
  alignment to a reference configuration when one is given (reuses `procrustes_align`).
- Refuses more than 30 elements; warns above 20 (design description § Limits).
- **Tests:** S3 positions within tolerance after alignment, accuracy within 0.01, per-point
  fit ordering; planted-geometry recovery; order-permutation invariance of the distance
  matrix (the current spring loop fails this by 18.9 of 76 units, see the PR 116 review).

### 3. STORM placement `storm_placement_v1`
- `storm.py`: each subject placed against the fixed H-Model objects per M3; per-row fit;
  the rim rule for rows with no preference; a counted, reasoned exclusion list.
- The STORM mass (concentration) as a declared terrain source, separate from WIND.
- **Tests:** S4 mass grid and subject positions; the three narrative cases from the help
  (fan near favourite, undecided between, none at the rim); a 2,000 × 30 timing budget.

### 4. WIND terrain and STORM mass
- `terrain.py` gains `TerrainMethod = {wind_idw, terrain66}`: WIND as inverse-distance
  weighting of object heights with exponent and radius per M4; height sources: matrix
  column sums, STORM rating sums, a characteristic, custom, inverse column sums (mapped to
  the existing `ObjectMetric` ids where they coincide). Contour levels stored, not drawn.
- **Tests:** S5 and S6 heights within tolerance; F7/F8 keep passing for terrain66.

### 5. Fit reporting and H-Model density
- `fit.py`: Spearman accuracy, per-point fit, and the permutation distribution of the
  Spearman coefficient under row-shuffled fuzzy matrices (the "H-Model density function");
  a p-value and the chosen significance level stored on the artifact.
- The artifact says, in words, what the fit means (methodology_status, the D6 state).
- **Tests:** known distribution for n = 5 against a brute-force enumeration; S3 accuracy.

### 6. Coherences, zoom, HM correction
- `coherence.py`: alpha-cuts as single-linkage over the pairwise minimum of mutual
  relations, the nested grouping string the help shows `(C, (D, (A, B)0.5)0.4)0.1`,
  zoom levels (merge groups above a cut, the merged relation as the minimum), and the HM
  correction as a declared penalty term in `h_model_v1`.
- **Tests:** the help's 4 × 4 worked example reproduces its grouping exactly.

### 7. Spec v3, preset, wiring, ledgers
- `SociomapSpec` v3: `fuzzy` (source, normalisation, aspects, missing policy),
  `layout.algorithm = h_model_v1` with its parameters, `respondents.algorithm =
  storm_placement_v1`, `terrain.method`, `fit` (seeds, permutations, level). Preset
  `SOCIOMAPPING_SOMECS_1`, `methodology_version = "sociomapping-somecs-1"`. `AIA_SOCIOMAP_V1`
  stays as a second preset for comparison; nothing auto-selects.
- `research_sociomap.py`: a battery's ratings become STORM data; the relation matrix
  becomes a `FuzzyMatrix`; the artifact carries both maps, fit, exclusions, provenance.
- `SociomapExecutor` unchanged in shape; `AIA_SOCIOMAP_WORKSPACE_ENABLED` is retired once
  chunk 11 renders from the artifact (PR 116's field stays readable).
- Ledgers that change with the code: `parity-matrix.json` (fixtures S1-S8, gates,
  `sociomapping.core` state), `legacy-route-ledger.json` (the eight `/api/visualization*`
  routes to PORTING with the research artifact route), `interface-screens.json`
  (`route-visualization` to REBUILDING).
- **Tests:** `test_parity_matrix.py` green with the new pins; end-to-end run on the
  synthetic fixture through the real worker.

### 8. Regions and statistics
- `regions.py`: region A vs complement and A vs B over subject characteristics: Welch t
  for continuous, chi-square for discrete (the help's own rule), Cohen d, intervals,
  raw and adjusted p-values per M8, minimum support per side with SUPPRESS below it;
  significant-region search as a scan over the grid with the same tests; phrase frequency
  in a region vs the rest (the text-info column).
- Every reported number is an `AdmittedClaim` through `evidence/`; p-values below support
  are suppressed, not rounded.
- **Tests:** S7; degenerate cases (one side empty, constant characteristic, tiny n).

### 9. Overlays as view layers
- `view.py` gains arrows (RTS rules: desired − current ≥ 2 single, both ways double;
  quality ≤ 2 of 5; object maps: significant negative correlation at the chosen level),
  shortest path (mediators whose chained relation beats the direct one), combine maps
  (add or subtract normalised heights, revert), coherence contours. All read the base
  artifact; a scenario stays a layer with its own fingerprint.
- **Tests:** each rule on a hand-built matrix; the layer never mutates the base.

### 10. Time
- Positions taken from a reference map (Procrustes to the earlier H-Model, locked where
  the owner says), wave sequences as a list of aligned artifacts, time-series framing with
  window and step and the frame-quality record from the SOMECS Time Series tool (overlap,
  frames, average and minimum records per frame, residual; export refused below the
  minimum), linear interpolation between frames. Dynamic H-Model motion and extrapolation
  only per M10.
- **Tests:** S8 two frames; frame arithmetic on the tool's worked example (10-day window,
  7-day step, 20 days → 2 frames, 4 residual records).

### 11. Results UI
- `SociomapWorkspace.tsx` renders from the v3 artifact: STORM and WIND toggle, top view
  with contours as the default, 3D as an option, the fit badge (accuracy, p, D6 state),
  regions A/B with the test table, arrows, animation between aligned waves. The renderer
  parts of PR 116 (SVG surface, camera, drilldown) are reused; the barycentre and spring
  geometry are not rendered as a Sociomap. Per M9 the Visualization Lab either stays as
  its own named view or goes.
- **Tests:** component tests on a fixture artifact; the workbench journey through Run →
  Results with both maps; `make ui-capture`.

### 12. Report and the client gate
- Report blocks for the map (method, fit, exclusions, regions) through `report/`;
  OI-17's gate: a Sociomap reaches a client document only when the spec's methodology
  version carries an approval in the decision document and the fit passes M6.

## What this costs

- Chunks 0-5 are the engine; without SOMECS fixtures (chunk 0) every later chunk is a
  hypothesis about the method. Getting the fixtures is the owner's and the team's first
  job, before any code.
- Two presets coexist for a while. Every artifact names its methodology version, so no
  map is ever ambiguous; the cost is two code paths until the owner retires one.
- The H-Model has local optima, as SOMECS itself says ("iterate again finds another
  position"). Multi-start with recorded seeds makes AIA deterministic, not unique; the fit
  and its p-value are what a reader judges, and the plan stores both.

## Disposition of PR 116

Mergeable as engineering behind its switch, but under M9 and with three changes before
merge: name the view "Visualization Lab" in the UI and plan, keep it visually apart from
the Sociomap card, and update the three ledgers it leaves stale (route ledger,
`interface-screens.json`, `parity-matrix.json` pin). Its renderer is reused in chunk 11;
its geometry is replaced by chunks 2-4.

## Findings carried from the review of PR 116 (for the docs PR)

- The 18.6.6 unit's `fit_python_unfolding` is present at
  `legacy/npc-panel-18.6.6/app/sociomap.py:53 @ cf08fac`; OI-13 still says it is withheld.
  Reopen or close OI-13 per the owner's choice of layout (this plan does not port it).
- `apps/web/src/i18n/cs.ts:919 @ 7c1e012` (`mapToolNotInAia`) is unused after PR 116.

## Doc follow-up

- `docs/architecture/sociomapa-methodology-decision.md` v2: M1-M10 with answers.
- `docs/architecture/sociomapa-deterministic-engine.md`: the DATA → MATICE → H-MODEL →
  MAPY pipeline, the two presets, SOMECS as oracle, fixtures S1-S8.
- CLAUDE.md map: `sociomap/{fuzzy,storm,fit,coherence,regions}.py`, `TerrainMethod`,
  the preset names; the Visualization Lab's name where it survives.
- `.planning/overview.md`: D6 reframed as "approve `sociomapping-somecs-1`"; OI-13 status.
