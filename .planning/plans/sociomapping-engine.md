---
status: in-progress
chunks:
  - "[x] 0a. Read the method's documents; record what they settle and what stays open"
  - "[x] 0b. Evidence register: every rule with source, page, formula, implementation, validation, uncertainty"
  - "[ ] 0c. Reference exports E1-E9 from SOMECS / RTS, one per open technical question"
  - "[ ] 0d. Method-owner decisions no export can settle (M6, M7, M8, M13, M14)"
  - "[x] 1a. Fuzzy matrix contract: documented sources and transforms, every gap refused by name"
  - "[x] 1b. Review corrections: products kept apart, every contract validated, signed correlations kept, weighted mean with provenance"
  - "[ ] 1c. Fuzzy gaps as their exports land: SOMECS STORM to matrix and ordinal (E2), negative correlations (E3), discrepancy (E4)"
  - "[x] 2a. H-Model reported accuracy: definition, per-point fit, invariances; SOMECS fig. 22 reproduced"
  - "[x] 2b. Experimental AIA H-Model candidate aia_hmodel_candidate_v1, evaluated per sociomapping-hmodel.md section 4 (not SOMECS equivalence)"
  - "[ ] 2c. H-Model significance: SOMECS and matched nulls, each refitted; p and quantiles (E1 settles the generator)"
  - "[ ] 3. STORM placement of respondents (E6)"
  - "[x] 4a. Height vectors: column, row and object averages (certification Tab. 1 reproduced)"
  - "[ ] 4b. Display rescale none / this / all, and the WIND surface (E7)"
  - "[x] 6a. Coherences and zoom, reproducing the SOMECS help's worked example"
  - "[ ] 6b. HM correction inside the H-Model"
  - "[ ] J1. Reference study R1 end to end: inputs, fuzzy, H-Model, heights/WIND, 3D, report (first three run today)"
  - "[ ] I1. Research step research_sociomapping behind AIA_SOCIOMAPPING_EXPERIMENTAL_ENABLED: declared matrix, candidate layout, heights, coherences, provenance"
  - "[ ] I2. Internal draft DOCX of the experimental map: method, fit, provenance, limitations (research_sociomapping_docx)"
  - "[ ] I3. API: the artifact through the run (researchers only) and the report's status and download"
  - "[ ] I4. Results page: 3D and top view, rotation, zoom, legend, object details, fit diagnostics, method, download"
  - "[ ] I5. Workbench journey on fictional data: run -> map -> report, screenshots, the report opened"
  - "[ ] 7. Spec v3, preset sociomapping-somecs-1, engine and research adapter wiring, artifact v3, ledgers"
  - "[ ] 8. Regions and statistics (E8, M8)"
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

## Sources read (chunk 0a)

The method owner's own material, received 2026-10-04. Cited by name and section; none of it
is vendored into the repository.

| Source | What it settles for the engine |
| --- | --- |
| SOMECS Software Help (CZ, 80 pp.) | The DATA → MATRIX → H-MODEL → MAPS pipeline; fuzzy matrix definition; STORM transforms (row, database, ordinal) and the 0 fill; aggregation as a weighted mean; coherences as alpha-cuts with a worked example; H-Model accuracy as a Spearman correlation, per-point fit, locks, margins, "iterate again" finds another layout; STORM and WIND maps; heights from column sums, STORM sums, a characteristic or custom values; region tests (t for continuous, chi-square for discrete); animation and time windows |
| SOMECS Input tutorial (EN, 21 pp.) | Objects × properties input; scale extremes per property, lower-is-better entered negative; Euclidean / Manhattan / correlation similarity ("correlation for more than 15 properties"); a five-star data-quality indicator; anonymisation |
| SOMECS Time Series tutorial (EN, 9 pp.) | Window and step framing; overlap, frames, average and minimum records per frame, residual; export refused on errors |
| Certification material for internal facilitators (CZ, 75 pp.) | The data matrix (row gave, column received, diagonal empty, asymmetric) with a worked 7 × 7 example; heights from column averages, row averages or a weighted characteristic; **the layout criterion: from each person, the order of distances to the others follows the order of that person's ratings, and of the possible layouts the one closest to the data is chosen** (§ 1.2.1, § 1.3.2); the order of distances, not their size, is what a reader takes; effectiveness = quality weighted by importance, with a value table and "the real formula is a rather complex equation" (§ 1.5); arrows and subteams |
| RTS designs doc (EN, 40 pp.) | People questions give a square matrix, object questions a respondents × objects matrix; **object relations are the correlation of the answer columns** (its example reproduces as plain Pearson: 0.96, 0.44, 0.23); answers normalised to 0-1 by their scale points, never by the data's range; heights as `.column.average`, `.row.average`, `.storm.average`; height normalisation none / each / range; arrows as boolean expressions over matrices |
| Design description (EN, 15 pp.) | Map limits: 30 people or objects, about 20 recommended; arrow rules (desired − current ≥ 2; quality 1-2 of 5; significant negative correlation among objects); subteam maps from 4 members |
| Cloud RTS specification (CZ, 54 pp., licence annex) | Views 3D rotate, 3D, 2D top; arrows and teams drawn only from the top; height rescale modes No Rescale (questionnaire scale), Rescale This (this map's range), Rescale All (range across the displayed maps); minimums: 2 completed questionnaires to show a map, 3 people or 3 objects to start |
| Sociomapping step by step (CZ, 34 pp.) and Research on Sociomapping (EN, 2010) | Facilitation, not computation; "the order of distances is key, not the actual distance"; layout fidelity measured by Spearman rank correlation |

**What this changes.** The H-Model is a *row-conditional rank* fit; object maps are built from
the Pearson correlation of respondents' answers, as 18.6.6's object map also does, so PR 116's
*input* to its object map matches RTS while its spring layout does not; and the map is a
people-or-objects map: RTS never places respondents, only SOMECS's STORM map does.

## Open questions, each with its exact dependency

The register (`docs/migration/sociomapping-evidence-register.json`) is the source of truth for
every rule; this table is what is still missing. **E** = a reference export or experiment (a
technical fact the software can show); **O** = a decision only the method owner can make.

| # | Question | Status after 0a/0b | Depends on | Blocks |
| --- | --- | --- | --- | --- |
| M1 | SOMECS: transformed STORM data to the n x n fuzzy matrix; the ordinal transform; a database of equal values; aspects | Object relations for **RTS** settled (RTS-O1, reproduced). SOMECS's own path open | E2 | 1c (SOMECS path only) |
| M2 | H-Model objective; accuracy details; per-point fit | Accuracy definition inferred and implemented (SOMECS-H3, fig. 22: 0.786 vs listed 0.785). SOMECS's fitting objective unknown; an experimental AIA candidate is specified (sociomapping-hmodel.md § 4) | E1 (accuracy), E5 (per-point; a second SOMECS layout); O for the objective itself | Any claim that AIA's layout is SOMECS's; not the candidate's build or evaluation |
| M3 | STORM placement of respondents | Open; SOMECS only | E6 | 3 |
| M4 | WIND interpolation | Open; heights themselves settled (4a) | E7 | 4b |
| M5 | Unanswered cells | RTS requires every answer; SOMECS fills 0. AIA keeps them empty and refuses where a complete matrix is needed | O (accept "refuse" for client work, or name a policy) | nothing today: refusal is safe |
| M6 | Fit level below which a map is not delivered | Open | O, informed by 2c's nulls | 12 |
| M7 | Respondent (population) weights | Open; no source weights a Sociomap | O | 7 |
| M8 | Region tests: which t-test, chi-square construction, multiplicity | SOMECS: t for continuous, chi-square for discrete (SOMECS-T1) | E8 + O (multiplicity) | 8 |
| M9 | Visualization Lab (PR 116) | Its object input matches RTS-O1 (Pearson, though rescaled to 1-10); its layouts match nothing documented | O | 11 |
| M10 | Extrapolation in animation | Open | E9 | 10 |
| M11 | Discrepancy measure gating aggregation | Weighted mean built; gate not applied and recorded as not performed | E4 | 1c |
| M12 | Negative correlations between objects on a 0-1 relation scale | Kept signed; refused by name at the 0-1 step | E3 | object maps on real data (R1 is all-positive) |
| M13 | Effectiveness formula (EFFECT) | Value table in certification p. 17; formula withheld | O (QED supplies it) | effectiveness designs |
| M14 | Statistical adequacy: when a correlation, map or region difference means something | Support recorded everywhere; product minimums (RTS-L1) are not adequacy | O | 12, and any client-facing use |
| M15 | The significance null's generator | SOMECS refits random symmetric matrices (fig. 22); distribution unstated | E1 | 2c acceptance only |

## Evidence still needed (chunk 0c) -- the smallest export for each

Each export can rule candidate rules in or out. One example need not identify an algorithm
uniquely, so each row also says what could stay open after it.

| Id | Export or experiment | Could distinguish | Might remain unresolved |
| --- | --- | --- | --- |
| E1 | SOMECS "Matrix Model Estimation", n = 10, run to completion, CSV saved (SOMECS Input p. 21) | M2: overall-pairs vs mean-per-row vs Pearson accuracy, sign or absolute value, over hundreds of matrix / coordinate / accuracy triples. M15: the random generator's distribution | Ties (continuous random values rarely tie); asymmetric input (the run ticks "symmetrical"); the optimiser, since coordinates are its output, not its process; whether the module fits the way the main H-Model does |
| E2 | SOMECS project from a STORM table of at least 5 subjects x 4 objects with varied values, once per transform (row, database, ordinal with a tie), each exported with its fuzzy matrix | M1: each transform's formula and tie rule; whether transformed STORM becomes the fuzzy matrix by correlation, a distance or something else | Formulas that agree on the chosen values (a small table can fit several); aspects; empty cells; a database of equal values unless included on purpose |
| E3 | RTS object question where two objects are rated in opposite directions, exported with its relation matrix | M12: whether RTS clips a negative r to 0, shifts it ((r + 1) / 2), takes `abs(r)` or refuses | Whether that is a deliberate rule or incidental; SOMECS's handling of the same case |
| E4 | Two 3 x 3 matrices differing in one cell by 0.3; aggregate in SOMECS at thresholds 0.2 and 0.4; repeat with the difference spread over three cells | M11: maximum cell difference vs a mean or sum; whether the threshold is inclusive | What SOMECS does on failure beyond what the screen shows; more than two matrices; unequal weights unless tried |
| E5 | SOMECS H-Model of the help's drinks example: positions ("Info o pozicích"), accuracy, per-point bars | M2: a second accuracy check on a real matrix; per-point candidates to the colour bar's resolution; a SOMECS layout to compare the AIA candidate with | The optimiser (one layout from one search); per-point candidates the bar's resolution cannot separate |
| E6 | SOMECS STORM map of the drinks data with subject positions | M3: a subject at the weighted mean of object positions vs fitted (unfolding) vs projected; which weights | The optimiser if placement is fitted; ties and empty answers |
| E7 | SOMECS WIND map of a 3-element matrix with heights 0, 0.5, 1 at known positions, as an image | M4: inverse-distance power vs a kernel; behaviour at and between points and at the edge | Exact parameters (an image gives heights only to its colour resolution); smoothing with many points |
| E8 | A SOMECS region test (A vs complement) on the drinks data with its p-values | M8: Student vs Welch t; the chi-square table's construction; p's rounding | Multiplicity across regions (O); how regions are drawn in other cases |
| E9 | A SOMECS animation with extrapolation, frame by frame | M10: linear vs curved extrapolation; frames per interval | Elements entering or leaving between waves; how waves are aligned when the frames do not show it |

E1 and E5 narrow the most: they test the accuracy definition on many more examples. Neither
identifies SOMECS's fitting objective; that needs the method owner (M2, O).

## Chunks

Detailed chunk notes. Everything listed under a chunk as "needs" is a row above.

### Integration I1-I5: one usable journey with the experimental method (2026-10-05)

Goal, set by the user for one night: research run -> declared relationship matrix -> H-Model
layout -> map exploration on the existing Results page -> downloadable AIA report with method,
fit, provenance and limitations. A small integration that works, not the roadmap.

Shape (checked against develop @ `70ff89d` and PR 116 @ `7c1e012`, unmerged):

- **Beside the existing Sociomap, not instead of it.** The `sociomap` step (legacy relations,
  `aia-sociomap-1`, INTERNAL_ONLY) is untouched, and so is every stored artifact. A new step
  `sociomapping` (kind `research_sociomapping`, stage ANALYSIS, after `run`) and a report step
  `sociomapping_report` (kind `research_sociomapping_report`, stage REPORT) are added to the
  research graph only when the API's `AIA_SOCIOMAPPING_EXPERIMENTAL_ENABLED` is on when the run
  starts; the flag is stored on the run (as `analysis_enabled` is), so a retry keeps the graph
  and old runs never change shape. Off by default; on in the workbench.
- **Declared relationship matrix** per tracked battery: RTS object correlations (RTS-N1,
  RTS-O1), signed, undefined pairs named (AIA-D1). Respondents with any unanswered object of
  the battery are excluded and counted (RTS collects complete data; the exclusion is AIA's,
  labelled, M5). Unweighted: no source weights a Sociomap (M7); the population weights the
  old step uses are recorded as not applied.
- **Layout**: `aia_hmodel_candidate_v1` (AIA-H9), EXPERIMENTAL_AIA. Constant objects are listed
  unplaced. **Heights**: each object's average answer on the battery's scale (RTS-W3). No STORM
  placement of respondents (M3) and no WIND surface (M4): the view shows points at their
  heights, not an interpolated terrain. **Coherences** only when every correlation is defined
  and non-negative (RTS-O2); otherwise the M12 reason, with the negative pairs.
- **Status never upgrades itself.** `method_status = EXPERIMENTAL_AIA`, `client_facing = false`
  on the artifact and the report; nothing in code can set them otherwise.
- **Report**: rendered by the report step in the worker (the API never executes steps), an
  INTERNAL draft through the existing `DocxRenderer`; fit diagnostics printed as properties of
  the computation (as `SociomapFigure` prints stress), never as admitted survey evidence.
- **UI**: renders the stored artifact only. PR 116's SVG renderer is coupled to its own
  `aia-native-workspace-1` payload and unmerged, so this view is its own small SVG component;
  converging the two is a follow-up once PR 116 lands.

- **0c / 0d.** Collect E1-E9 and the owner decisions; each lands as a fixture under
  `packages/aia_core/tests/fixtures/sociomapping_sources/` with a register entry upgraded from
  INFERRED or OPEN.
- **1c.** Only the SOMECS path and the 0-1 step for negative correlations remain; both refuse
  today by name.
- **2b. Experimental AIA H-Model candidate.** `h_model_candidate_v1`: objective, starts,
  selection, gauge and acceptance exactly as `docs/architecture/sociomapping-hmodel.md` § 4,
  labelled experimental in code and on every artifact. Buildable now. Its acceptance is on
  AIA's own terms -- a provisional comparison with fig. 22's 0.786 (rounding band recorded),
  MDS baselines, perfect fit only on planted data constructed to admit it, an evaluation set
  of independent matrices (asymmetric and tied included) fixed before scoring, repeatability
  tested apart from cross-host reproducibility. No result of 2b is presented as SOMECS
  equivalence; E1/E5 compare it with SOMECS afterwards, they do not confirm it.
- **2c. Significance.** § 5 of the same document; both nulls, refitted; worker step.
- **3. STORM placement.** Needs E6. RTS has no respondent map, so an AIA object study gets an
  object map first; respondents wait for SOMECS's rule.
- **4b.** Rescale modes are documented (RTS-V1) and can be built with 2b; the WIND surface
  waits for E7, and until then the existing terrain66 surface stays labelled as AIA's own.
- **6b.** HM correction, after 2b.
- **J1. The acceptance journey.** `tools/sociomapping_journey.py` runs R1 through every built
  stage and lists the rest as pending with what blocks them; each new stage joins it and its
  test. Done when R1 reaches a rendered 3-D map and a report page with every intermediate
  and fit diagnostic shown.
- **7-12.** As before: wiring and artifact v3, regions, overlays, time, the Results UI from the
  artifact, the report and the client gate.

## Progress

On `feature/sociomapping-engine`; `make verify` green before each commit.

**0a, 0b.** Sources read and cited by page; evidence register with 35 rules, each labelled
DOCUMENTED, REPRODUCED_FROM_EXAMPLE, INFERRED, PROPOSED or OPEN, and a test
(`test_sociomapping_evidence_register.py`) that fails if an implementation or a validating test
goes missing, if a rule called reproduced has no source example behind it, or if an output
records a rule id the register lacks.

**1a, 1b -- `domain/sociomap/fuzzy.py`.** Review corrections to the first draft, each a defect
the draft had:

1. *Products mixed.* One `normalise_storm_ratings` served RTS and SOMECS rules alike, and the
   correlation accepted any of its outputs. Now RTS (`rts_people_matrix`, `rts_scale_answers`,
   `rts_object_correlations`, `rts_fuzzy_from_correlations`), SOMECS
   (`somecs_transform_storm`) and legacy AIA (`legacy_fuzzy_from_relation_1_10`) are separate
   functions, every output records its product and rule ids, and the correlation accepts only
   RTS-scaled answers.
2. *`NormalisedStorm` unvalidated.* Now checks ids, shape, finiteness, range, booleans, that
   empty cells exist only under `KEEP_EMPTY`, that a scale is recorded with and only with the
   RTS transform, and that product and transform agree (`test_normalised_storm_contract`).
3. *Normalisation order unexamined.* Column scaling keeps Pearson's r; row normalisation
   changes it (-0.620 to -0.426 on the test data). The undocumented combination is refused
   (`test_scaling_columns_keeps_r_but_row_normalisation_changes_it`).
4. *Negative correlations discarded.* The draft refused the whole computation. Now
   `ObjectCorrelations` keeps the signed matrix, every pair's support and every undefined pair
   with its reason; only the step to `[0, 1]` refuses, naming each negative pair (M12).
5. *Aggregation overstated.* `aggregate_fuzzy` returned a bare matrix labelled aggregated.
   Now `weighted_mean_fuzzy` returns the mean with input fingerprints, sources, raw and
   normalised weights, and `discrepancy_check = NOT_PERFORMED` with the reason (M11).
6. *Undocumented cases extrapolated.* The within-row transform gave 0.5 to a row with one
   answered cell and transformed partial rows. SOMECS transforms are documented for complete
   data, so a row with an empty cell is now refused under `KEEP_EMPTY` (M5).
7. *Computable taken for adequate.* Support is now recorded on correlations; adequacy is
   M14, and the product minimums are registered as display rules (RTS-L1), not adequacy.

**2a -- `domain/sociomap/hmodel.py`.** The reported accuracy, separate from any objective:
Spearman over all ordered pairs of `(M_rs, -d_rs)`, average ranks, undefined when a side is
constant; per-point fit per row; `mean_per_point` reported apart from the overall figure.
Gives 0.786 on SOMECS's fig. 22 coordinates (0.783-0.793 across the screenshot's rounding;
listed: 0.785). Invariances tested. `tools/somecs_estimation_experiment.py`: SOMECS 0.786 vs
classical MDS 0.661 vs best of 20 nonmetric MDS 0.743 on the same matrix, under AIA's
evaluator.

8. *Objective overclaimed.* The first draft of the H-Model note read that gap as showing
   SOMECS optimises rank agreement and set ">= 0.786 on fig. 22" as 2b's acceptance. The gap
   is equally consistent with more starts, another optimiser, manual adjustment or a different
   evaluator; one layout of one matrix cannot identify an algorithm. Now: SOMECS's objective is
   recorded as unknown (AIA-H8, OPEN), 0.786 is a provisional comparison score, the MDS
   figures are baselines of the configurations tested, and 2b builds an experimental AIA
   candidate with acceptance criteria that do not depend on one screenshot.

**4a -- `domain/sociomap/heights.py`.** Column, row and object averages; certification Tab. 1
reproduced (2.66 printed for 16/6 is a truncation).

**6a -- `domain/sociomap/coherence.py`.** As before, plus the consequence of the help's tie
rule, now tested: with ties the grouping depends on element order
(`(C, (A, (B, D)0.5)0.4)0.1` after reordering); without ties it does not.

**J1 so far.** `tools/sociomapping_journey.py` on the fictional study R1 (a six-person team with
two questions; twelve respondents rating five fictional brands): fuzzy matrices, heights,
coherences and object correlations, with every intermediate printed; six stages pending,
each naming its blocker.

**Findings.**

- `apps/web/src/i18n/cs.ts:919 @ 7c1e012` (`mapToolNotInAia`) unused after PR 116.
- OI-13 says `fit_python_unfolding` is withheld; it is at
  `legacy/npc-panel-18.6.6/app/sociomap.py:53 @ cf08fac`.
- The registration form received with the sources contains an RTS administrator login; it was
  not used and is not recorded anywhere in the repository. Rotate it.
- A fictional fixture can still fail `make exposure_check`: its content rule matches the 18.6.6
  demo brand names case-insensitively anywhere in a tracked file. R1's first object was named
  after one and failed `no client-identifying legacy names in file contents`
  (`tools/exposure_check.sh:169`); it is now Altair. Check invented names against
  `FICTIONAL_DEMO_TOKENS` before writing a fixture.

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

- CLAUDE.md map, `sociomap/`: `fuzzy.py` (RTS / SOMECS / legacy paths to a fuzzy matrix, signed
  object correlations, weighted mean with provenance), `coherence.py` (alpha-cut coherences, zoom),
  `hmodel.py` (reported H-Model accuracy), `heights.py` (column / row / object averages).
- CLAUDE.md map, `docs/`: `docs/migration/sociomapping-evidence-register.json` (every rule with
  source, page, label, validation; tested) and `docs/architecture/sociomapping-hmodel.md`.
- AGENTS.md (pytest/fixtures): invented names in a fixture must avoid `FICTIONAL_DEMO_TOKENS` in
  `tools/exposure_check.sh`; the content rule is case-insensitive and covers test trees.
- CLAUDE.md map, `tools/`: `sociomapping_journey.py` (reference study R1 through every built
  stage), `somecs_estimation_experiment.py` (SOMECS fig. 22 versus MDS; NumPy, scikit-learn).

- `docs/architecture/sociomapa-methodology-decision.md` v2: M1-M10 with answers.
- `docs/architecture/sociomapa-deterministic-engine.md`: the DATA → MATICE → H-MODEL →
  MAPY pipeline, the two presets, SOMECS as oracle, fixtures S1-S8.
- CLAUDE.md map: `sociomap/{fuzzy,storm,fit,coherence,regions}.py`, `TerrainMethod`,
  the preset names; the Visualization Lab's name where it survives.
- `.planning/overview.md`: D6 reframed as "approve `sociomapping-somecs-1`"; OI-13 status.
