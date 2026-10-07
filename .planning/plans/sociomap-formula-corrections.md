---
status: planned
chunks:
  - "[ ] 0a. The audit's sixteen rules in the evidence register, DOCUMENTED; its checks C1-C16 and P4-P14 as fixtures"
  - "[ ] 0b. Owner decisions: Q5, Q6, Q7 from the audit; F2 against RTS-O1; the kernel width on the fixed ruler; one object-map method; R smacof against pure Python"
  - "[ ] 1a. Stage 1 -- pair status UNKNOWN / RELIABLE / WEAK with N_min and the Fisher interval on the derived relation; the 5.5 stamp gone (F3)"
  - "[ ] 1b. Stage 1 -- alignment and connectedness over PRIMARY objects, UNKNOWN pairs left out; mean rating as the default height (F8)"
  - "[ ] 1c. Stage 1 -- every straight-liner NOT PLACED with a reason, out of the terrain, counted (F11)"
  - "[ ] 2a. Stage 2 -- per-person min-max over all rated items before Pearson (F2); a declared matrix type, no branch detection (F5); signed strength beside |r| (F4)"
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
**Engineering:** sociomapa-deterministic · **Started:** 2026-10-07 (gap analysis; no code yet) ·
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
the two agree and where they collide is in § 4; the owner's first decision (0b) is whether AIA
carries one object-map method or two.

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

## 4. Conflicts and open questions for the owner (chunk 0b)

1. **One object-map method or two.** Path A's successor under this audit places objects by
   metric SMACOF on δ = sqrt(2(1 − r̃)) with Stress-1 (F6, F7). Path B places them by a rank fit
   whose SOMECS objective is unknown (M2). The audit's method is fully specified and testable;
   the H-Model's is not yet. *Proposal:* build the audit's stages as `aia-sociomap-2`, keep B
   experimental until E1/E5 and M2 settle, and let the owner retire one. Both stay
   `INTERNAL_ONLY` / `EXPERIMENTAL_AIA`; the client gate (OI-17) does not move.
2. **F2 against RTS-O1.** The register reproduces RTS's object relation as plain Pearson on
   scale-normalised answers; the audit says per-person min-max first, and chose it on 22-09-2026
   over per-family normalisation (audit § 12 F2), with Q5 still open. The engine plan measured
   that row normalisation changes r and refused the combination as undocumented. One rule must
   win for AIA's object map; the fixture from E3 or the audit's `[C1]` decides nothing by itself.
3. **The kernel width on the fixed ruler.** F6 fixes one map unit (δ ∈ [0, 2]); F12's hill keeps
   σ in map units but the audit's σ = 12 is in the unit's ±62 frame. On the fixed ruler σ must be
   restated (the respondent density kernel's 9.5 likewise), or the terrain is again scaled by the
   frame. Not in the audit; needed before 4b.
4. **Joint fit or two stages.** The audit's F6 + F10 is objects first, people against fixed
   objects. A's unfolding fits both at once from ratings alone and uses the relation matrix only
   for heights (OI-14). If the owner takes F6 + F10, `aia_rowcond_unfolding_v1` becomes the
   comparison alternative and F16's slope/intercept applies only if the joint fit survives.
5. **R smacof or pure Python.** The audit's preferred route for F16 is R `smacof::unfolding`
   with Python as a fallback. `ARCHITECTURE.md` § 2 and the engine's reason for existing
   (bit-identical on every host) say the opposite. *Proposal:* implement in pure Python, pin to
   an R-produced fixture at a stated tolerance after Procrustes (the recipe OI-15 already asks
   for), and record the tolerance on the artifact. That needs a host with CRAN once.
6. **The audit's own Q5, Q6, Q7**, and the F10 misfit threshold, which it does not give.
7. **The SECONDARY rule** (F8: context objects never enter PRIMARY scores or terrain) binds AIA's
   object manager before it exists (engine doc § 12 lists it as not started).

## 5. Approach

The audit enters AIA the way its own § 9 says the MVP takes it (decision D16: today's formulas
stay the baseline until an approved replacement exists), and the way D6's package already allows
(**REPLACE** → a new declared method with a new `methodology_version`,
`sociomapa-methodology-decision.md` § 5):

- **A new preset, not edits to the old one.** `aia-sociomap-2` on spec contract v3. Every
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
- **0b.** The seven items of § 4, answered in writing by the owner and recorded in
  `sociomapa-methodology-decision.md` v2 (docs PR). Until 1 is answered, chunks 1-4 build
  `aia-sociomap-2` beside B; nothing waits on 2-7 except 2a (F2 rule), 2b/4b (σ) and 4c.
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
- **4c.** `layout.py`: `aia_rowcond_unfolding_v2` with slope and intercept per respondent and the
  penalty, **or** v1 retired to a comparison alternative if 0b item 4 picks F6 + F10. Either way:
  the recovery test on planted ideal points the audit asks for, and the R fixture of OI-15 as the
  parity gate at a stated tolerance.
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
- `.planning/overview.md`: D6 reframed to "approve `aia-sociomap-2`"; M4, M6, M8 noted as
  answered for AIA's object map by F12, F7, F14 pending the owner.
- `.planning/open-items.md`: the four findings of § 7 numbered; OI-13's "withheld" corrected;
  OI-15's recipe reused by chunk 4c.
- `AGENTS.md`: nothing yet.

## 10. Review outcome

Not started.
