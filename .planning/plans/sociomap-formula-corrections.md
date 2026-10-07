---
status: in-progress
chunks:
  - "[x] 0a. The audit's sixteen rules in the evidence register, CANONICAL; its checks C1-C16 and P4-P14 as a fixture"
  - "[ ] 0b. The canonical rule recorded in the decision package; the audit's own Q5, Q6, Q7 and the kernel width on the fixed ruler put to its author; the R-smacof seam settled with engineering"
  - "[x] 1a. Stage 1 -- pair status UNKNOWN / RELIABLE / WEAK with N_min and the Fisher interval on the derived relation; the 5.5 stamp gone (F3)"
  - "[x] 1b. Stage 1 -- alignment and connectedness over PRIMARY objects, UNKNOWN pairs left out; mean rating as the default height (F8)"
  - "[x] 1c. Stage 1 -- every straight-liner NOT PLACED with a reason, out of the terrain, counted (F11)"
  - "[x] 2a. Stage 2 -- per-person min-max over all rated items before Pearson (F2); a declared matrix type, no branch detection (F5); signed strength beside |r| (F4)"
  - "[ ] 2b. Stage 2 -- object layout: delta = sqrt(2(1 - r)), SMACOF from a Torgerson start, Stress-1, no rescale to a radius (F6)"
  - "[ ] 2c. Stage 2 -- one layout; Procrustes alignment to a reference map as a view layer; the quality label (F7)"
  - "[ ] 2d. Spec v3 and the preset aia-sociomap-2; aia-sociomap-1 kept as the comparison alternative; artifact v3; the research step adapter"
  - "[ ] 3. Stage 3 -- the common 0-1 scale (F1); ideal-point placement against the object map, per-respondent misfit e_k and its flag (F10)"
  - "[ ] 4a. Stage 4 -- connectedness 0-100 with a respondent-bootstrap interval; rank only where intervals do not overlap (F9)"
  - "[ ] 4b. Stage 4 -- terrain as the max-envelope of hills, one formula for every surface (F12, F13)"
  - "[ ] 4c. Stage 4 -- row-conditional unfolding with per-respondent slope and intercept and the anti-degeneracy penalty, or its retirement behind F6 + F10 (F16)"
  - "[ ] 4d. Stage 4 -- region tests: positioning variables excluded, Holm, Cohen's d and h ranking (F14, F15), with sociomapping-engine chunk 8"
  - "[ ] 5. Results and the report: the Stress-1 label, arrows for RELIABLE pairs only, sign as colour, the not-placed count; the client gate unchanged (OI-17)"
  - "[ ] 6. Ledgers and the decision package: parity-matrix pins, D6 v2 re-scoped to aia-sociomap-2, OI-13 and OI-16 wording"
---
# Sociomap formula corrections -- the audit "NPC Sociomapa: faulty formulas in the code" fitted into AIA

**Owner:** method owner (QED Group; the audit is by Aram Bahbouh, status 6 October 2026) ·
**Engineering:** sociomapa-deterministic · **Started:** 2026-10-07 (chunks 0a, 1a and 1c landed, § 8a and § 10) ·
**Base:** `develop` @ `579b7ab`.

**Source.** `NPC_Sociomapa_Faulty_Formulas.pdf` (EN) and `NPC_Sociomapa_Chybne_Vzorce.pdf` (CS),
30 pages each, the same document in two languages. Received 2026-10-07; not vendored. Cited
below as "audit, F<n>" (Part I, pp. 3-18), "audit, § 12" (the evidence, pp. 21-28), "audit, § 9"
(the roadmap, p. 19). Its numbers in square brackets (`[C1]`...`[C16]`, `[P4]`...`[P14]`) are
printed by `NPC/analysis/code_formula_checks.py`, which we do not have (chunk 0a asks for it).

**Companion plan.** [`sociomapping-engine.md`](sociomapping-engine.md) upgrades AIA's Sociomap
towards the SOMECS / RTS method (the H-Model). This plan is about a different document: an audit
of the **18.6.6 unit's** Sociomapa pipeline -- `visualization_lab.py`, `sociomap.py`,
`ui_app.html` -- which AIA ported as `aia-sociomap-1`. The audit never mentions SOMECS, the
H-Model or the fuzzy matrix; the engine plan never had the formulas the audit now supplies. Where
the two agree and where they collide is in § 4.

**Canonical.** The owner stated on 2026-10-07 that these two PDFs are *the* canonical
methodology document and that **no prior decision overrides them**. So: where this repository
disagrees with the audit -- the four `AIA_SOCIOMAP_V1` declarations (D6 package), the evidence
register's RTS / SOMECS rules, the engine plan's M-questions, the fixtures that pin the ported
formulas -- the audit wins and the other is stale until a docs PR says so. The audit is a
specification of the panel pipeline (F1-F15) and of the research module's preference map (F16);
the SOMECS H-Model path (B below) is not in it and is therefore not canonical. What the audit
leaves open by its own words (Q5, Q6, Q7, the F10 threshold, the untested F16 fit) stays open and
is its author's to answer, not ours to infer.

## 1. What the audit is, and what it is not

Sixteen formulas (F1-F16) the unit computes, each with the exact formula as the code has it, the
proposed replacement, and the measured consequence on the canonical demo (1,500 respondents,
22 objects) and on simulated data with a known truth. A roadmap of four stages (audit, § 9):
1 *stop untrue statements* (F8, F14, F11, F3), 2 *honest relations and distances* (F2, F5, F4,
F6, F7, one chain), 3 *people where they belong* (F1, F10), 4 *consistent scores and pictures*
(F9, F12, F13, F15, F16). It also lists what it checked and found sound (§ 13: Welch, Cohen's d,
the relaxation rule's optimum, the classical-MDS start, weighted Pearson arithmetic, the
normalisers, the contours, GMM/BIC) and where the unit's handoff no longer describes its code
(§ 14).

**Every "where it occurs" line matches the vendored unit** at
`legacy/npc-panel-18.6.6/app/` @ `579b7ab`: `visualization_lab.py:44-57` (F1), `:104-128`
(F2-F4, F6-F7), `:117-118` (F8-F9), `:154-167` (F10-F11), `:244-283` (F14-F15);
`sociomap.py:40-50, 92` (F16), `:411-440` (F2-F5), `:459-506` (F7), `:557-560` (F8-F9, F13);
`ui_app.html:2037, 2043-2049, 2056-2057, 2069, 2208, 2210`. Every claim in the audit is therefore
checkable here with one `sed -n`; the audit's own evidence script is not.

It is a specification at formula level, which the SOMECS material is not for the layout (the
H-Model's objective is unknown, `sociomapping-hmodel.md` § 4). It leaves three questions open by
name (Q5: co-movement vs "rated alike"; Q6: the final `N_min`; Q7: the default terrain height),
says F16's full proposal was not tested ("the fitted map still needs a recovery test on data with
known ideal points", § 12 F16), and says nothing about respondent weights, the data class or the
client gate -- AIA's own rules there stand.

## 2. Where AIA stands: three computations

| Path | Objects placed by | Respondents placed by | Fit | Height | Status |
| --- | --- | --- | --- | --- | --- |
| **A** `aia-sociomap-1`: `domain/research_sociomap.py` → `domain/sociomap/` (`AIA_SOCIOMAP_V1`) | the ratings unfolding `aia_rowcond_unfolding_v1`, jointly with respondents (`engine.py:226-238`) | the same unfolding | `stress_1` on the artifact (`engine.py:291`); printed in the DOCX figure (`figures.py:75-78`), not on Results (`ExecutionSteps.tsx:1012-1040`, a table) | `relation_classic_tscore` (`specification.py:415`), kernel-weighted mean terrain (`terrain.py:251-253`) | `INTERNAL_ONLY` while D6 is open |
| **B** `aia-research-sociomapping-1`: `domain/research_sociomapping.py` → `fuzzy.py`, `declared.py`, `hmodel_candidate.py`, `heights.py` | `aia_hmodel_candidate_v1`, a rank fit on signed object correlations | not placed (M3) | Spearman accuracy, overall and per point | mean answer on the set's scale (RTS-W3); no surface | `EXPERIMENTAL_AIA`, behind `AIA_SOCIOMAPPING_EXPERIMENTAL_ENABLED` |
| **C** the unit's respondent map, lens, scenario mode, lasso and area comparison | -- | -- | -- | -- | **not in AIA** (`interface-screens.json` `route-visualization`: `NOT_IN_AIA`); PR 116's Visualization Lab port is unmerged |

The relation matrix path A feeds its engine is the unit's `derive_relation_matrix`, ported line
for line (`research_sociomap.py:80-129`): weighted Pearson on raw ratings, fewer than five common
ratings → 5.5, `1 + 9 (r + 1) / 2`. That is the audit's F2, F3 and F4, present in AIA today and
deliberately so (PR C chunk 6 ported the unit). The engine's own refusals (`refuse` for a missing
cell, `AmbiguousCoercion`, no silent T-score) never see these cells, because the stamp happens
upstream of the spec.

## 3. Gap analysis, F1-F16

Status: **CARRIED** = AIA carries the unit's faulty formula; **PARTIAL** = part of the
replacement exists; **MET** = AIA already does what the replacement asks; **ABSENT** = neither
the defect nor the capability exists in AIA, the rule binds when it is built.

| F | The unit's defect (audit) | AIA today, anchored @ `579b7ab` | Status | What the replacement means in AIA |
| --- | --- | --- | --- | --- |
| F1 columns guessed as ratings | quantile rule, household size becomes an object | No detection: the objects are the design's tracked set and its declared scale (`research_sociomap.py:150-156`; `research_sociomapping.py` via `rts_scale_answers`, `fuzzy.py:449`). B normalises to 0-1 by the declared scale (RTS-N1); A uses raw ratings | **MET** (B), **PARTIAL** (A: declared, not 0-1) | A takes the 0-1 scale in chunk 3; nothing to remove |
| F2 Pearson on raw ratings | rating habits inflate r (+0.39 with σ_g = 1.2, σ_t = 1.5) | A: raw weighted Pearson (`research_sociomap.py:119-127`). B: Pearson on column-scaled answers (`fuzzy.py:476`), **and the engine plan refused row normalisation as an undocumented combination** after measuring that it changes r (−0.620 → −0.426; `test_scaling_columns_keeps_r_but_row_normalisation_changes_it`) | **CARRIED** (A and B) | per-person min-max over *all* rated items, straight-liners excluded, then Pearson. **Collides with register RTS-O1** (reproduced from the RTS example as plain Pearson) -- owner question, § 4 |
| F3 too little data = "no relation" | N < 5 → r = 0 → strength 5.5, drawn as a measurement; chance band ±0.88 at N = 5 | A: `if len(ok) < 5: rel = 5.5` (`research_sociomap.py:116-117`), then summed into the classic score and the T-score height. B: one `support` per matrix (complete cases only, `fuzzy.py:531`), undefined pairs named, no N_min, no interval | **CARRIED** (A), **PARTIAL** (B) | a pair status (UNKNOWN below N_min ≈ 30; RELIABLE when the Fisher-z 95 % interval excludes 0; WEAK otherwise), weight 0 in the layout, no arrow, out of the scores. A4 and A5 of `ARCHITECTURE.md` already forbid the stamp; this is the finding in § 7 |
| F4 1-10 strength, arrows by it | r = 0 is a medium arrow, r = −0.9 the faintest; `v <= 0` never filters | A stores `1 + 9 (r + 1) / 2` (`research_sociomap.py:127`) and positions on `(mutual − 1) / 9` (`relations.py:181-182`); B keeps signed r. AIA draws no arrows (Results is a table; B lists relations sorted by r) | **CARRIED** (A data), **MET** (B data), display **ABSENT** | strength = \|r̃\|, direction = sign, arrows only for RELIABLE pairs (chunk 5; engine plan chunk 9 overlays) |
| F5 a supplied matrix's scale guessed | the same r = 0.30 is 3.7 or 6.85 | A: `_branch` picks similarity / correlation / clip from the values (`relations.py:95-100`, `:128-160`), kept for fixture F1 parity; the mixed-NaN case alone is refused. B: `declared.py` takes values as measured (AIA-D1). No upload route exists | **CARRIED** (A), **MET** (B) | `RelationSpec.scale_coercion` becomes a declared type (correlation / similarity 0-1 / strength 1-10); detection stays only as the named legacy option of `aia-sociomap-1` |
| F6 target distance scaled to the strongest pair, map stretched to a radius | a barely related family looks as structured as a strong one; maps not comparable across families or waves | A does not place objects from the relation matrix at all (OI-14), so the strongest-pair target is absent; but every map is rescaled so the furthest point sits at 45 (`engine.py:232-238`, `map_frame max_abs_to_extent`, D6 package § 3) -- the second half of F6. B scales into [0.05, 0.95] (`hmodel_candidate.py:84`), harmless to a rank fit, still erases scale across waves | **CARRIED** (the frame), replacement **ABSENT** | δ = sqrt(2 (1 − r̃)) ∈ [0, 2], SMACOF weighted by pair status, Stress-1, **no rescale**: one map unit means the same everywhere. The terrain's σ is then in these units (§ 4) |
| F7 four layouts that disagree; the fit never shown | scenario mode rotates and enlarges; HTML vs PNG disparity 0.86; Stress-1 0.30 never displayed | A: one implementation, deterministic, bit-identical (`layout.py` docstring; `test_identical_input_gives_identical_bits`); `stress_1` on every artifact; `procrustes_align` exists (`layout.py:597`) but only tests call it; no label; Results does not show the stress. B shows accuracy and per-point fit | **PARTIAL** | alignment to the previous map as a view layer over the immutable artifact (engine plan chunk 10); the label thresholds (< 0.05 good, < 0.10 fair, < 0.20 weak, ≥ 0.20 "2D picture unreliable") -- **this answers M6** |
| F8 classic score Σ(s_ij + s_ji) | mostly a constant, signs cancel, SECONDARY objects reshuffle the ranking | A: `relation_classic` over the coerced 1-10 matrix (`metrics.py:213-224`), the default height (`specification.py:415`), pinned by fixture F6 as reference behaviour; `mean_rating` is available with declared bounds. No object manager, so no SECONDARY contamination. B: mean answer as height (RTS-W3) | **CARRIED** (A), **MET** (B height) | `alignment A_i` ∈ [−1, 1] and `connectedness K_i` ∈ [0, 1] over PRIMARY objects, UNKNOWN pairs left out; default height mean rating (audit Q7 pending) |
| F9 normative score 50 + 10 z, panel ÷n vs report ÷(n−1) | always winners and losers; two numbers for one object | A: `tscore` with the population divisor (`metrics.py:226-231`), one function, so the panel/report mismatch does not exist here | **CARRIED** (the curve), **MET** (one formula) | `K_i × 100` with a 2.5/97.5 % respondent-bootstrap interval (B ≈ 500; AIA's own generator per OI-62); rank i above j only when intervals do not overlap |
| F10 respondent = barycentre of objects rated > 5 | 1-5 items never count; (10,10,10,10), (10,1,10,1) and (6,6,6,6) all map to (0,0); everyone in the inner 19 % | A places respondents jointly in the unfolding, no barycentre, no fixed midpoint; **no per-respondent misfit** (diagnostics are `row_scales`, `principal_axis_gap`, `engine.py:295-298`). B places no respondents (M3) | **PARTIAL** (A) | ideal point against the **fixed** object map: x_k = argmin Σ_j (‖x − y_j‖ − δ_kj)², δ_kj = D (1 − ã_kj), misfit e_k, "poorly represented" above a threshold. This is a two-stage model (objects from F6, people against them); A's joint fit is a different model -- § 4 |
| F11 unplaceable respondents invented | a ring that adds a fake ridge (18 % of peak density); a stale 22-object position labelled POSITIONED | A: `excluded_respondents` with a reason (`engine.py:72-83`), out of the density terrain (placed ids only, `engine.py:302-304`), counted in `warnings`. **But only "every object at the top" is excluded**: a respondent giving every object the same score below the top is placed (`engine.py:78`), equidistant from everything, carrying no preference | **PARTIAL** | every straight-liner NOT PLACED with the reason; the legend count (Results has no respondent view today) |
| F12 object terrain = kernel-weighted mean | plateaus to 46 units then a cliff; a high object next to a low one pulled to 0.66 | A: exactly this -- `hsum / den` where `den > 0` else `None` (`terrain.py:251-253`), `None` → 0 (`terrain.py:264`), σ = 12, cutoff 0.0005 (`TERRAIN66_OBJECT`, `terrain.py:110`); pinned by fixtures F7/F8. B: no surface (M4) | **CARRIED** | z(q) = max_j h_j exp(−‖q − y_j‖² / 2σ²): each object a hill of exactly its height. **This answers M4 for AIA's object map** unless E7 says WIND differs |
| F13 report terrain = sum of hills | a cluster of three equal objects peaks 2.7× an isolated one | Nothing outside `compute_terrain` computes a surface (`report_docx/`, `application/sociomapping_report.py`, `apps/web` all read the artifact); no AIA surface is rendered anywhere today | **MET** by construction | one formula in domain; chunk 4b adds the test that no renderer sums anything |
| F14 area tests on the positioning variables, 24 uncorrected tests | 5 of 6 "significant" on pure noise; 44 % false alarms on random splits | No lasso, no regions, no `compare_area` (`route-visualization` `NOT_IN_AIA`); engine plan chunk 8 (M8: which t, chi-square, multiplicity) is where regions land; `domain/evidence/` gates every client-facing number | **ABSENT** -- binds chunk 8 | test V \ V_position only, label the positioning variables "differs by construction", Holm at α = 0.05, Cohen's d with its interval first. **This answers M8's multiplicity question** |
| F15 "main differences" in raw units | a six-year age gap outranks a complete gender split | absent, as F14 | **ABSENT** -- binds chunk 8 | \|d\| for numbers, \|h\| = \|2 arcsin √π_A − 2 arcsin √π_B\| for categories, max over categories |
| F16 unfolding targets stretched per respondent, one global scale | (9,9,9,10) and (1,1,1,10) get identical targets; (5,5,5,5) → "very close" to all | The unit's `fit_python_unfolding` is refused (OI-13; the plan found it present at `sociomap.py:53`). A's `aia_rowcond_unfolding_v1`: δ = scale_top − rating (`layout.py:237`, a constant multiple of the audit's δ_kj, equivalent under the free row scale) ✓; per-respondent slope b_k ✓; **no intercept c_k**; collapse prevented by a global normalisation, not smacof's penalty; straight-liners partly excluded (F11). R smacof refused (OI-15; `domain/` is pure Python by rule) | **PARTIAL** | b_k and c_k per respondent, straight-liners out, λ·pen(U, V) as in `smacof::unfolding`; the audit prefers R and calls Python "a test fallback" -- AIA's answer is a pure-Python fit validated against an R fixture, not an R runtime (§ 4) |

**Count.** CARRIED 8 (F2, F3, F4, F5, the F6 frame, F8, F9, F12), PARTIAL 5 (F1, F7, F10, F11,
F16), MET 1 (F13), ABSENT 2 (F14, F15). Path B already meets F1, F5, the data side of F4 and
the height of F8. Every CARRIED item is a formula AIA
ported *on purpose* for parity with the unit and pinned by a golden fixture (F1, F2, F5, F6, F7,
F8 under `fixtures/sociomap/`). The audit does not make those fixtures wrong: they prove the port
is exact. It makes the ported method unapproved, which it already is (D6).

## 4. What the canonical rule settles, and what stays open (chunk 0b)

Before the owner's statement these were seven questions. The rule answers five of them; the
plan records the answers so nobody re-litigates them.

| # | Question as first raised | Settled by the canonical rule | Still open |
| --- | --- | --- | --- |
| 1 | One object-map method or two | **The audit's method is AIA's object map**: SMACOF on δ = sqrt(2 (1 − r̃)) with Stress-1 (F6, F7). Path B's H-Model is not in the audit; it stays `EXPERIMENTAL_AIA`, for comparison only, until retired. The engine plan's M2 is moot for the object map | -- |
| 2 | F2 against register rule RTS-O1 | **F2 wins**: per-person min-max over all rated items, straight-liners excluded, then Pearson. RTS-O1 (plain Pearson on column-scaled answers) and the engine plan's refusal of row normalisation are stale for AIA's object map; the measured change in r (−0.620 → −0.426) is the habit being removed, not a reason to refuse | Q5 (co-movement vs "rated alike"), the audit's own open question |
| 3 | The kernel width on the fixed ruler | Not in the audit: F12 keeps σ = 12 of the unit's ±62 frame, F6 fixes one map unit (δ ∈ [0, 2]) | **Open, to the audit's author**: σ for the object envelope and 9.5 for the respondent density, restated in the fixed ruler's units; until then 4b cannot land |
| 4 | Joint fit or two stages | **Two stages** (F6 then F10): objects from the relation map, respondents as ideal points against the fixed objects, with misfit e_k. `aia_rowcond_unfolding_v1` is retired to a comparison alternative for the panel map. F16 is a separate product in the audit (the research module's preference map, `sociomap.py`); its replacement applies there, chunk 4c | the F10 misfit threshold (not given) |
| 5 | R smacof or pure Python | The audit's route for F16 is R `smacof::unfolding`, Python "a test fallback only". That is the canonical preference. `domain/` staying pure Python is an engineering constraint, not a methodology decision, and the two are compatible: an R adapter in `infrastructure/` (failing closed when R is absent, OI-15's recipe) with the pure-Python fit as the test fallback the audit allows | the tolerance at which the Python fallback must agree with R, and whether the develop host carries R -- engineering, 0b |
| 6 | The audit's Q5, Q6 (final N_min), Q7 (default terrain height) | -- | **Open, to the audit's author.** Until answered: N_min = 30 as the audit's working value (F3 says "≈ 30"), mean rating as the default height (F8 says "pending Q7") -- both recorded as the audit's provisional values, not AIA's |
| 7 | The SECONDARY rule (F8) | **Binds**: context objects never enter PRIMARY scores or terrain. AIA's object manager does not exist yet; the rule is written into chunk 1b's contract now so it is there when it does | -- |

**What becomes stale by this rule, and where it is said.** The D6 package's four
declarations: § 1 target (the audit's δ is equivalent, so it survives as F16's), § 2 layout
(replaced for the panel map by F6 + F10), § 3 frame (rejected by F6), § 4 missing policy
(replaced by F3's pair status; `refuse` survives as the behaviour for a cell below N_min that
no spec declares otherwise). The register's RTS-O1 for AIA's object map. The engine plan's M2,
M4, M6, M8 for the object map (answered by F7, F12, F7, F14). All of it goes through the docs
PR (§ 9); this plan edits none of those files.

## 5. Approach

The audit enters AIA the way its own § 9 says the MVP takes it (decision D16: today's formulas
stay the baseline until an approved replacement exists), and the way D6's package already allows
(**REPLACE** → a new declared method with a new `methodology_version`,
`sociomapa-methodology-decision.md` § 5):

- **A new preset, not edits to the old one.** `aia-sociomap-2` on spec contract v3, the
  canonical method; `aia-sociomap-1` and path B stay only as named comparison alternatives. Every
  replacement is a new enum member beside the legacy one (`PairStatusRule`,
  `RelationScaleCoercion.DECLARED_*`, `DissimilarityTarget.CORRELATION_DISTANCE`,
  `LayoutAlgorithm.AIA_SMACOF_OBJECTS_V1`, `MapFrameMethod.FIXED_RULER`,
  `TerrainMode.OBJECT_ENVELOPE`, the new `ObjectMetric`s). `aia-sociomap-1` keeps computing
  exactly what fixtures F1-F9 pin, so nothing stored changes and every artifact names its method.
- **Stage by stage, in the audit's order**, because stage 2 is one chain (relation → strength →
  distance → layout) and stage 3 needs stage 2's ruler. Each chunk lands code + tests, behind the
  preset, with no route or UI change until chunk 5.
- **The audit's measurements become AIA's tests** on synthetic data, so no archive is needed:
  F2's inflation (six independent objects, σ_g = 1.2, σ_t = 1.5: raw mean r ≈ +0.39, after
  min-max ≈ −0.09, centring −1/(m − 1)); F3's chance band (±0.88 at N = 5, ±0.36 at 30); F6's
  weak family (targets 1.36-1.48, Stress-1 0.307 vs a strong family's 0.067); F7's convergence
  (SMACOF optimum 0.296 where 500 relaxation steps stop at 0.348); F10's four profiles; F12's
  profile 1.0 → 0.84 → 0.04 → 0.001 at 0 / 7 / 30 / 46 units; F14's 0 of 9 on noise and 44 % → 6 %
  on random splits; F15's h = π for a complete split.
- **Unknown stays unknown** (A4): a pair below N_min has weight 0 and no arrow, never 5.5; a
  respondent with no preference is NOT PLACED, never ringed; a map without structure shows its
  Stress-1 and the label, never a stretched picture.
- **Shared docs change in the docs PR**; this plan and the PR descriptions carry the follow-ups.

## 6. Trade-off accepted

Three Sociomap computations coexist until the owner retires one, at the cost of two more code
paths and a second decision package; in exchange nothing already stored changes meaning, and the
audit's formulas can be built and measured now instead of waiting for SOMECS fixtures.

## 7. Findings (live defects in AIA's own code, six parts each)

**F-1. A pair rated by fewer than five people is stamped 5.5 and summed into the height.**
Anchor `packages/aia_core/src/aia_core/domain/research_sociomap.py:116-117 @ 579b7ab`, then
`relation_classic` (`metrics.py:213-224`) and the preset height (`specification.py:415`).
Reproduce: `packages/aia_core/tests/test_research_sociomap.py:127-129 @ 579b7ab` asserts the
5.5 cell today (the port's own parity test); through `battery_sociomap` the T-score height
moves with it. Consequence: an unknown is drawn as a medium relation on the internal map (A4, A5).
Smallest fix: chunk 1a (pair status; weight 0; the sentinel only under `aia-sociomap-1` by name).
Test: a four-rater pair is UNKNOWN, enters no score, and the artifact's `relation.status` says so.

**F-2. A straight-liner below the top of the scale is placed.** Anchor
`packages/aia_core/src/aia_core/domain/sociomap/engine.py:72-83 @ 579b7ab` (only `== scale_top`
excludes). Reproduce: a respondent rating every object 6 on 1-10 gets coordinates and a density
contribution. Consequence: a crowd of equal-raters raises the density terrain where nobody has a
preference (audit F11). Smallest fix: chunk 1c (`max_l a_kl == min_l a_kl` → NOT PLACED). Test:
`(6, 6, 6, 6)` is in `excluded_respondents` with the reason and absent from `respondent_terrain`.

**F-3. The object terrain is a weighted mean with a cliff.** Anchor
`packages/aia_core/src/aia_core/domain/sociomap/terrain.py:251-253, 264 @ 579b7ab`. Reproduce:
one object at height 1 → `height_normalised` is 1.0 out to the cutoff radius and 0 beyond
(`test_one_object_gives_its_own_value_wherever_it_has_support` asserts exactly this). Consequence:
height means crowding, not score (audit F12). Smallest fix: chunk 4b, a new `TerrainMode`; the
old mode stays for `aia-sociomap-1`. Test: the audit's profile at 0 / 7 / 30 / 46 units.

**F-4. Every map is stretched to extent 45.** Anchor
`packages/aia_core/src/aia_core/domain/sociomap/engine.py:232-238 @ 579b7ab`. Reproduce: scale
all ratings' spread down → identical map. Consequence: maps are not comparable across families or
waves (audit F6, D6 package § 3 names the same consequence). Smallest fix: chunk 2b
(`MapFrameMethod.FIXED_RULER`). Test: a weak and a strong family keep different radii.

(All four are reproduced by existing tests that assert the current behaviour; the v1 tests
stay as they are, because v1 stays what it is.)

## 8. Chunks

- **0a.** Register F1-F16 in `docs/migration/sociomapping-evidence-register.json` with product
  `NPC-AUDIT`, page, formula, replacement and label DOCUMENTED; the register test keeps every
  implemented rule pointing at code and a test. Ask the owner for `code_formula_checks.py` and
  its printed `[C*]` / `[P*]` outputs; vendor them under
  `packages/aia_core/tests/fixtures/sociomapping_sources/` as the audit's fixtures.
- **0b.** Record the canonical rule and the five settled answers of § 4 in
  `sociomapa-methodology-decision.md` v2 (docs PR). Put the open items to the audit's author
  in one note: Q5, Q6, Q7, the F10 misfit threshold, σ on the fixed ruler. Settle the R seam
  with engineering (tolerance, host). Nothing waits on 0b except 4b (σ) and 4c's tolerance;
  Q6 and Q7 run on the audit's provisional values until answered.
- **1a.** `relations.py`: `pair_status(r, n, n_min)` → UNKNOWN / RELIABLE / WEAK with the Fisher-z
  interval; `research_sociomap.derive_relation_matrix` gains a variant that returns signed r,
  N_ij and status per pair (the 1-10 mapping and the 5.5 stamp stay only in the legacy variant).
  Artifact carries `relation.status`, `relation.n`, `relation.interval`.
- **1b.** `metrics.py`: `alignment` and `connectedness` over the PRIMARY set (today: every
  object of the battery) with UNKNOWN excluded; `mean_rating` as the v3 default height.
- **1c.** `engine.py` placeability: any constant row is NOT PLACED with the reason; count on the
  artifact; the density terrain over placed respondents only (already so).
- **2a.** `relations.py`: `person_minmax(ratings)` over all rated items of the respondent,
  constant rows excluded; Pearson on the result; `RelationScaleCoercion.DECLARED_CORRELATION |
  DECLARED_SIMILARITY_0_1 | DECLARED_STRENGTH_1_10` with no detection; the artifact stores
  signed r̃ and |r̃| side by side.
- **2b.** `layout.py`: `fit_smacof_objects(delta, weights)` -- Torgerson start, Guttman transform,
  Stress-1, weights 0 for UNKNOWN; `DissimilarityTarget.CORRELATION_DISTANCE`;
  `MapFrameMethod.FIXED_RULER` (no rescale; the extent recorded as 2.0). Pure Python, bit-identical;
  the audit's optimum 0.296 on its demo cannot be reproduced without the demo, so the test is the
  weak/strong synthetic family and a planted configuration recovered to Stress-1 < 1e-4.
- **2c.** `view.py`: `align_to(reference_artifact)` -- orthogonal Procrustes (rotation,
  reflection, no scale) as a view layer with its own key; `quality_label(stress_1)` with the
  audit's thresholds, printed by the DOCX figure and Results.
- **2d.** `SociomapSpec` contract v3, `AIA_SOCIOMAP_V2` (`methodology_version = "aia-sociomap-2"`),
  `require_supported` for every new member, artifact v3 (`to_payload` round-trip, tamper refused),
  `research_sociomap` building v2 beside v1 under one research step (`methodology_status` stays
  `INTERNAL_ONLY`); `layer_check` extended to the new preset name.
- **3.** Ratings to the common 0-1 scale by the declared ends (F1); `place_respondents(objects,
  ratings)` -- ideal points against the fixed object map, δ_kj = D (1 − ã_kj) with D = 2, misfit
  e_k, flag above the owner's threshold; NOT PLACED from 1c. Lands as
  `LayoutAlgorithm.AIA_IDEAL_POINT_V1` for respondents under v2; the joint unfolding stays v1's.
- **4a.** `metrics.py`: `connectedness_100` with a respondent bootstrap (clusters = respondents,
  B = 500, `random.Random(seed)` with `random()` only, as OI-62 decided for aggregation), 2.5/97.5
  quantiles; `rank_with_ties` from non-overlapping intervals. The seed is a spec field.
- **4b.** `terrain.py`: `TerrainMode.OBJECT_ENVELOPE`, z(q) = max_j h_j exp(−d² / 2σ²) with σ in
  the v2 ruler's units (0b item 3); a test that no module outside the engine sums or averages
  hills (grep-level, like `layer_check`).
- **4c.** The research module's preference map (F16, the audit's separate product): targets
  δ_kj = (s_max − a_kj) / (s_max − s_min), per-respondent slope b_k and intercept c_k, straight-
  liners out, the anti-degeneracy penalty as in `smacof::unfolding`; R `smacof` through an
  adapter in `infrastructure/` (fails closed without R), the pure-Python
  `aia_rowcond_unfolding_v2` as the test fallback, pinned to the R fixture of OI-15 at the
  tolerance 0b sets; the recovery test on planted ideal points the audit asks for. For the panel
  map, v1 is retired to a comparison alternative (§ 4 item 4).
- **4d.** With sociomapping-engine chunk 8: `regions.py` tests only variables outside the
  positioning set, labels the rest "differs by construction", Holm at 0.05, d with its interval
  first, h for categories; the "main differences" ranking by |d| and |h|. Every p-value and
  effect reaches a client only as an `AdmittedClaim`.
- **5.** Results: the v2 map with the Stress-1 label, arrows for RELIABLE pairs only
  (|r̃| opacity, sign colour), the not-placed count in the legend; the DOCX figure prints the
  label; `require_client_facing` unchanged -- `aia-sociomap-2` is `INTERNAL_ONLY` until D6 v2.
- **6.** `parity-matrix.json` (the v1 pins stay; v2 gates added), `interface-screens.json`
  notes, OI-13 (the function is present, not withheld -- the engine plan's finding), OI-16 and D6
  v2 re-scoped to `aia-sociomap-2`, the register's labels upgraded as fixtures land.

Order: 0a → 1a → 1b → 1c → 2a → 2b → 2c → 2d → 3 → 4a → 4b → 4c → 4d → 5 → 6. 0b runs beside
0a and gates 2a's rule, 2b/4b's σ and 4c.

## 8a. Progress

**0a (2026-10-07, `feature/sociomap-audit-register`).** `docs/migration/sociomapping-evidence-register.json`
gains a `CANONICAL` label, the two audit documents (`NPC_AUDIT_EN`, `NPC_AUDIT_CS`, 30 pages,
one pagination), sixteen rules `AUDIT-F1`..`AUDIT-F16` (each: the replacement as the formula,
the Part I page and the § 12 page, what it applies to in AIA with the anchor it replaces, the
chunk that implements it as `resolve_by`, the open question if the audit leaves one), and a
`canonical` block: the owner's rule, the scope, `supersedes` (F2 → RTS-O1; F3 → AIA-D2;
F4 → RTS-A1; F6 → AIA-H8, AIA-H9; F7 → SOMECS-H3; F10 → SOMECS-M1; F12 → SOMECS-M2;
F14 → SOMECS-T1; each superseded rule's `uncertainty` now says so) and `checks`, the printed
evidence each rule rests on. The audit's twenty checks (C1-C16, P4, P10, P12, P14) and its
"checked and found sound" list are transcribed, number by number, into
`packages/aia_core/tests/fixtures/sociomapping_sources/npc_audit_checks.json`; nothing was
recomputed. `test_sociomapping_evidence_register.py` keeps it true: a CANONICAL rule cites a
canonical document and a page, everything superseded says by what, the register and the
fixture name the same checks and each check names the rules that claim it. Measured: the
register suite 24 passed; every `sociomap` test 421 passed, 5 skipped (the archive-backed
parity tests, as always); `mypy` over the four source trees clean; `ruff format --check` 478
files; `layer_check` 94 rules; `exposure_check` 7 rules. Not done, and not doable from here:
the audit's `code_formula_checks.py` and its outputs are still with the audit's author; the
request below is what to send.

**Request to the audit's author (chunk 0a, to be sent by the owner).** For
`.planning/plans/sociomap-formula-corrections.md` chunk 0a we need, as files: (1)
`NPC/analysis/code_formula_checks.py` as run for the 6 October 2026 status; (2) its printed
output, so every `[C*]` and `[P*]` number in the audit is reproducible here; (3) the simulated
inputs behind C1, C2, C4/P4, C10/P10, C11, C12/P12, C13, C14/P14 and C16, or the seeds and
generators that made them; (4) if the demo dataset cannot leave, the per-check summaries it
produced (C1's mean r and share positive, C5's stresses, C6's disparities, C8's rankings,
C9's scores, C10's radii) as they stand. With them the fixture becomes the audit's own output
instead of a transcription, and each of the plan's synthetic acceptance tests can be checked
against the audit's number before it is trusted.

Two readings to settle with the same note (raised by the Codex review of PR #173, recorded in
the register's `AUDIT-F2` and `AUDIT-F8`): (5) F2 is silent on respondent weights; AIA keeps the
Pearson step weighted after the per-person rescaling, as the unit's path is today, unless the
author says otherwise. (6) F8 writes the denominator as m_P − 1 while leaving UNKNOWN pairs out
of the sums; a fixed denominator scores an unknown pair as 0, so AIA divides by the known
PRIMARY pairs and leaves an object with none unscored, unless the author says otherwise.

**1a and 1c went before 0a** (2026-10-07, PR #172, another session). 0a was thought blocked on the
PDFs' pages; they were in hand, so 0a landed next (PR #173), and its merge with #172 registers
F3 as implemented by `relations:pair_status` with the chance-band test as its source example,
and F11 by `engine:_placeability`. Both rules keep what is still owed: F11's count in a legend
that does not exist yet (chunk 5), F3's final N_min (Q6).

## 9. Doc follow-up

- `CLAUDE.md` map, `domain/sociomap/`: the v2 members once they exist (`pair_status`,
  `person_minmax`, `fit_smacof_objects`, `place_respondents`, `connectedness_100`,
  `OBJECT_ENVELOPE`, `align_to`); `AIA_SOCIOMAP_V2` beside `AIA_SOCIOMAP_V1`.
- `docs/architecture/sociomapa-deterministic-engine.md`: § 2 pipeline with the v2 chain, § 5 the
  v2 preset table, § 8 the differences table extended (S8: no 5.5 stamp; S9: no frame rescale;
  S10: envelope terrain), § 12 the audit as a source.
- `docs/architecture/sociomapa-methodology-decision.md` v2: the four v1 declarations re-read
  against the audit (§ 3 frame: the audit rejects it; § 1 target: the audit's δ is equivalent),
  the § 4 questions with the owner's answers, `aia-sociomap-2` as the decision's subject.
- `.planning/overview.md`: the canonical rule as a decision row (the audit overrides every prior
  Sociomap decision); D6 reframed to "approve `aia-sociomap-2`"; M2, M4, M6, M8 marked answered
  for AIA's object map by the audit (F6/F7, F12, F7, F14).
- `.planning/plans/sociomapping-engine.md` (its own PR, never this one): path B demoted to a
  comparison alternative; M2, M4, M6, M8 closed for the object map; chunk 8 to take F14/F15.
- `docs/migration/sociomapping-evidence-register.json`: RTS-O1 and the RTS / SOMECS rules marked
  as not canonical for AIA's object map; the audit's F-rules (chunk 0a) labelled CANONICAL.
- `.planning/open-items.md`: the four findings of § 7 numbered; OI-13's "withheld" corrected;
  OI-15's recipe reused by chunk 4c.
- `AGENTS.md`: nothing yet.
- From chunk 1a: `CLAUDE.md` map, `domain/sociomap/relations.py`: "pair status (audit F3):
  UNKNOWN / RELIABLE / WEAK from the rater count and the Fisher-z interval"; `research_sociomap.py`:
  "each pair's signed r, rater count, interval and status beside the unit's 1-10 matrix".
  `sociomapa-deterministic-engine.md` § 8: a row S8 -- reference: a pair under five raters is 5.5,
  drawn as a medium relation; production: the unit's matrix kept for `aia-sociomap-1`, every pair
  carrying its status, UNKNOWN below `n_min`; tests
  `test_a_pair_rated_by_too_few_is_unknown_where_the_unit_stamps_five_and_a_half`,
  `test_below_n_min_a_pair_is_unknown_whatever_its_number_says`.
- From chunk 1c: `sociomapa-deterministic-engine.md` § 2, the pipeline line "placeable rows
  (≥ 2 ratings, not all at the top)" becomes "placeable rows (≥ 2 ratings, not a straight-liner
  at any score)"; § 6, `excluded_respondents` "with no recoverable position, straight-liners
  included"; § 8, a row S9 -- reference: an unplaceable respondent is put on an invented ring
  (audit F11); production: every straight-liner excluded with its reason, out of the density
  terrain, still counted in `support_n`; tests `test_a_straight_liner_below_the_top_is_not_placed`,
  `test_straight_liners_do_not_move_anyone_else`. `CLAUDE.md` map, `executors/research.py`: "a
  stored Sociomap is reused only under the same engine implementation version".
- From chunk 1b: `CLAUDE.md` map, a line under `domain/sociomap/` for `metrics.py` (it has none
  today): "metrics.py  object metrics and the normaliser (F5, F6); `primary_scores`: alignment and
  connectedness over the PRIMARY objects, UNKNOWN pairs out of the sums and the denominator, an
  object with none unscored (audit F8)"; `research_sociomap.py`: "... and each object's alignment
  and connectedness (`object_scores`)". `sociomapa-deterministic-engine.md`: § 2 pipeline, beside
  the object metrics, "alignment / connectedness over PRIMARY (audit F8), stored by the research
  step, read by no height yet"; § 5 a note that `aia-sociomap-1`'s default height stays the
  classic T-score and the audit's provisional default (mean rating, Q7) arrives with spec v3; § 8 a
  row S10 -- reference: the classic score `sum_j (s_ij + s_ji)`, mostly the constant `11 (m - 1)`,
  a 5.5-stamped pair counted as medium, context objects in the sum; production: `relation_classic`
  kept for `aia-sociomap-1`, and `primary_scores` beside it over PRIMARY objects with UNKNOWN
  pairs left out; tests `test_the_scores_are_the_audits_formula_on_a_hand_computed_example`,
  `test_a_secondary_object_never_moves_a_primary_score_where_it_reshuffles_classic`. (The
  envelope-terrain row this plan's § 9 first called S10 takes the next free number.)
  `.planning/overview.md` / D6 v2 note: AIA's reading of F8's denominator (known PRIMARY pairs,
  unscored with none) is put to the audit's author with Q7.
- From chunk 2a: `CLAUDE.md` map, `domain/sociomap/relations.py` "scale coercion, mutual
  projection, ipsatization F1-F3" gains "; `person_minmax` (audit F2: each respondent's own 0-1
  scale over every item they rated, straight-liners out); `coerce_declared_1_10` (audit F5: a
  matrix's declared type, never detected)"; `specification.py` "SociomapSpec v2 (no defaults)"
  gains "; `RelationScaleCoercion.DECLARED_*`"; `research_sociomap.py` gains "; each pair after the
  rating habit is removed (`relation_rescaled`, signed r~ and |r~|), which the object scores read".
  `sociomapa-deterministic-engine.md` § 2: the relation step's choice of coercion (reference
  detection or a declared type); § 8 a row -- reference: a supplied matrix's scale guessed from
  its values (r = 0.30 is 3.70 or 6.85); production: `aia-sociomap-1` keeps the guess for fixture
  F1, `DECLARED_*` converts by the declaration and refuses what the type cannot hold; tests
  `test_the_same_correlation_means_the_same_strength_whatever_the_other_cells`,
  `test_the_engine_converts_by_the_declared_type_and_records_it`. A row for F2 -- reference:
  weighted Pearson on raw ratings (the habit inflates r, +0.394 for six independent objects);
  production: the unit's matrix kept for `aia-sociomap-1`'s layout, `relation_rescaled` beside it;
  test `test_the_rating_habit_inflates_raw_r_and_the_rescaling_removes_it`.

## 10. Progress and review outcome

### Chunk 1a -- pair status (F3), 2026-10-07

What landed, on `feature/sociomap-pair-status`:

- `domain/sociomap/relations.py`: `PairStatus` (UNKNOWN / RELIABLE / WEAK), `pair_status(r, n,
  n_min, confidence)`, `fisher_interval`, `null_band` (the audit's chance band) and
  `AUDIT_PROVISIONAL_N_MIN = 30`. `n_min` and the confidence have no defaults: the caller passes
  them and the result records them.
- `domain/research_sociomap.py`: `derive_pair_relations` -- the unit's weighted Pearson, signed,
  with `n`, `interval` and `status` per pair; nothing stamped (fewer than two raters or a constant
  column → `r = None`, UNKNOWN). `derive_relation_matrix` is unchanged in behaviour and still EXACT
  against the unit's capture (it now shares the weighted moments with the new function, same
  operation order). The stored body's `relation` block gains `r`, `n`, `interval`, `status`,
  `n_min`, `confidence`, `status_counts`, `status_rule` and a `matrix_caveat` on the 1-10 matrix.
- `SOCIOMAP_VERSION` `aia-research-sociomap-1` → `-2`: the executor fingerprints its input with
  it, so a run stored under `-1` (without the statuses) is not reused as if it had them.

What it does not do yet: no score, layout or terrain reads the status (1b, 2b, 4b); the engine
artifact (`compute_sociomap`) is unchanged, so `aia-sociomap-1` still lays out over the unit's
matrix. The status is visible in the stored body only; Results shows nothing new (chunk 5).

Measured on the captured case `A01_full_questionnaire` (450 respondents, 5 objects): 10 pairs, 9
RELIABLE, 1 WEAK, 0 UNKNOWN; every signed `r` equals the unit's `(strength − 1) / 4.5 − 1` to 1e-12.

**Open point for the audit's author (with Q5-Q7).** `n` counts respondents, not weight. Under a
weighted design the Fisher interval read at that `n` is narrower than the weighted correlation
warrants (Kish's effective n, which `domain/evidence/support.py` already computes for
aggregation, would widen it). The audit's F3 does not say which `n`; chunk 1a uses the count, as
the audit's N does, and records the choice in `status_rule`. Unanswered, this is a hypothesis
about over-confidence, not a finding.

Checks run: `ruff check`, `ruff format --check`, `mypy --strict` (all three trees), `make
layer_check`, `make exposure_check`, `make test` on Python 3.12 as CI (4,969 + 331 + 54 + 295
passed, 0 failed). `make web_design` and `make test-web` were not
run: no web file changed, and `apps/web` has no installed packages in the session's container.

### Chunk 1c -- straight-liners not placed (F11), 2026-10-07

Finding F-2 is fixed. `domain/sociomap/engine.py` `_placeability` excludes every respondent whose
rated objects all share one score, at the top of the scale or anywhere else (`max == min` over
the rated cells, so missing cells do not hide one). Each gets its reason in
`excluded_respondents`, stays out of the layout and the density terrain, is counted in the
warning, and still counts in `mean_rating` and `support_n`. A battery of nothing but
straight-liners has no map (`UnfoldingDesignError`, fail closed).

**Why this changes `aia-sociomap-1` and does not break the rule that v1 stays what it is.** The
placeability rule belongs to `aia_rowcond_unfolding_v1`, AIA's own layout, not to the unit:
the engine document says the layout is not a port, and the reference's layout fixture (F4) is
refused. No reference fixture F1-F9 goes through it, so v1 still computes exactly what F1-F9
pin. The old rule excluded only the top-of-scale case; this is the same rule without the
special case.

`ENGINE_IMPLEMENTATION_VERSION` 1.1.0 → 1.2.0, since the output changes for any input with a
straight-liner below the top. The layout golden (`AIA1_rowcond_unfolding_on_f4_ratings.json`) was
regenerated with `tools/sociomap_golden.py`: only its version field changed, because F4's 24
respondents include no straight-liner. Neither does the captured research case A01 (450
respondents), so no stored research map's numbers move.

The research step's reuse fingerprint now includes the engine version
(`apps/executors/src/aia_executors/research.py` `_sociomap_fingerprint`). Before, a newer build
could be handed a map the previous engine drew for the same dataset and spec, because the
artifact repository reuses by input fingerprint.

Measured: twenty identical straight-liners and one with a missing cell, added to an eight-person
design, leave every other respondent's coordinates, the object coordinates and the density
terrain bit-identical (`test_straight_liners_do_not_move_anyone_else`).


Checks run: `ruff check`, `ruff format --check`, `mypy --strict`, `make layer_check`, `make
exposure_check`, `tools/sociomap_golden.py --check`, `make test` on Python 3.12 (4,973 + 331 + 54 +
296 passed, 0 failed).

### Chunk 1b -- alignment and connectedness over PRIMARY objects (F8), 2026-10-07

What landed, on `feature/sociomap-alignment-connectedness`:

- `domain/sociomap/metrics.py`: `primary_scores(object_ids, r, status, roles)` → `PrimaryScores`
  (per PRIMARY object: `alignment`, `connectedness`, `known_pairs` -- the denominator -- and
  `unknown_partners`; plus `primary`, `secondary`, `excluded_pairs` and the rule id
  `audit-f8-known-primary-pairs-v1`); `alignment(...)` and `connectedness(...)` as by-id views;
  `ObjectRole` (PRIMARY / SECONDARY); `AUDIT_PROVISIONAL_DEFAULT_HEIGHT = MEAN_RATING` (the
  audit's provisional answer to Q7). `roles` must declare every object: nothing defaults to
  PRIMARY, and an undeclared or unknown id is refused. Only PRIMARY x PRIMARY cells are read; an
  UNKNOWN pair's number never is; a RELIABLE or WEAK pair must carry r in [-1, 1] and both halves
  of a pair must agree. UNKNOWN pairs are out of the sums and the denominator; an object with no
  known pair is `None`, never 0 (the reading put to the author in § 8a item 6).
- `domain/research_sociomap.py`: each set's stored body gains `object_scores` (every object of a
  tracked set declared PRIMARY, since there is no object manager). `SOCIOMAP_VERSION` `-2` → `-3`:
  the executor fingerprints its input with it, so a body stored under `-2` (without the scores)
  is not reused as if it had them.
- Register `AUDIT-F8`: `implementation` and eight `validation` entries.

What it does not do: no height, terrain or Results surface reads the scores. `relation_classic`
and the T-score height stay `aia-sociomap-1`'s, unchanged; mean rating becomes a declared
default only with spec v3 (2d), and the new scores become `ObjectMetric` members there too, so
no v1 spec can select a metric v1 does not compute. The audit's C8 numbers come from its demo,
which we do not have; the SECONDARY test is synthetic (a context object moves the classic
score's top object to the bottom and leaves every PRIMARY score bit-identical).

Measured on the captured case `A01_full_questionnaire` (450 respondents, 5 objects): every pair
known, each object's scores the mean of its four signed / absolute r to 1e-12. With the first
object's ratings kept for 20 respondents only, its four pairs are UNKNOWN, it is unscored, and
the other four are scored over three pairs.

Checks run: `ruff check`, `ruff format --check` (547 files), `mypy --strict` over the four source
trees (295 files, clean), `make layer_check` (94 rules), `make exposure_check` (7 rules), the
evidence-register suite (24 passed), every `sociomap` test (473 passed, 5 skipped: the
archive-backed parity tests), `make test` on Python 3.12 (4,992 + 331 + 54 + 296 passed, 0
failed). `tsc --noEmit`, `make web_design` and `make test-web` were not run: no web file
changed, and `apps/web` has no installed packages in the session's container.

### Chunk 2a -- each person on their own scale (F2), a declared matrix type (F5), 2026-10-07

**Why now, with Q5 open.** The audit names this variant as chosen ("This is the variant we chose
(per-person normalisation within the active family only was rejected)", § 12 F2, p. 22) and
leaves only Q5 (co-movement vs "rated alike") open; § 8 above already says nothing waits on 0b
but 4b and 4c. Q5 stays with the audit's author; if it changes the rule, `relation_rescaled`
changes with it under a new `SOCIOMAP_VERSION`.

What landed, on `feature/sociomap-person-minmax`:

- `domain/sociomap/relations.py`: `person_minmax` (eq. 5: `(a - min_l) / (max_l - min_l)` over
  every item the respondent rated; a row with no spread -- one value, one item or none -- is
  excluded, never 0/0; non-finite refused) and `PersonScaled`. `DeclaredRelationType` and
  `coerce_declared_1_10` (eq. 11: correlation `1 + 9 (x + 1) / 2`, similarity `1 + 9 x`, strength
  as is, chosen by the declaration; a cell outside the type's range or non-finite refused, never
  clipped or 5.5). `mutual_relation_for_position` now projects through `mutual_from_1_10`, the same
  arithmetic, so the declared path projects alike (fixtures F1-F2 unchanged).
- `domain/sociomap/specification.py`: `RelationScaleCoercion.DECLARED_CORRELATION |
  DECLARED_SIMILARITY_0_1 | DECLARED_STRENGTH_1_10` beside `REFERENCE_COERCE_1_10`;
  `require_supported` refuses a declared type with the 5.5 midpoint sentinel (F5: a missing cell is
  unknown). `engine.py` dispatches on the declared coercion and records the branch as
  `declared_<type>`. No preset names a declared type: `aia-sociomap-1` keeps the reference's
  detection for fixture F1, and no upload route exists to declare one.
- `domain/research_sociomap.py`: `rescaled_battery_ratings` puts every rating of every tracked set
  of the specification on its item's declared 0-1 scale first (F1 eq. 3, so items with different
  ends compare), then each respondent's own min-max over all of them (F2: all items rated, not only
  the family mapped), and returns the mapped set's columns and the excluded respondents. Each
  battery's body gains `relation_rescaled`: the rule, the sets read, the excluded respondents, every
  pair's signed `r`, `abs_r` (F4's strength, beside the sign), `n`, interval, status and counts.
  `object_scores` (1b) now read `relation_rescaled`, as F8 writes them over r~.
  `battery_sociomap` takes `rated_with` by keyword, no default. `SOCIOMAP_VERSION` `-3` -> `-4`.
- The Pearson step stays weighted after the rescaling, AIA's reading where the audit is silent
  (register `AUDIT-F2`, § 8a item 5).

Measured (`test_the_rating_habit_inflates_raw_r_and_the_rescaling_removes_it`): six independent
objects, generosity sd 1.2, taste sd 1.5, integer 1-10, 3,000 respondents, seed 1: raw mean r
**+0.394** (the audit's [C1]: +0.394; theory 0.39), after min-max **-0.090** (the audit's -0.09).
With continuous (unrounded) ratings the same panel gives +0.40 and -0.11: the audit's baseline is
reproduced on the integer scale a panel collects. [C7]: r = 0.30 is 3.70 or 6.85 under detection
and 6.85 both times when declared a correlation.

What it does not do: no layout reads r~ (2b: SMACOF on `sqrt(2 (1 - r~))`), `aia-sociomap-1` lays
out over the unit's matrix as before; Results and the DOCX show nothing new (chunk 5); arrows by
`abs_r` and sign are chunk 5's.

Checks run: `ruff check`, `ruff format --check` (543 files), `mypy --strict` (300 files, clean),
`make layer_check` (100 rules), `make exposure_check` (7 rules), the evidence-register suite (24
passed), every `sociomap` test and the new `test_sociomap_person_minmax.py` (24 tests).

