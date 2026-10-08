---
status: in-progress
chunks:
  - "[x] 0a. The audit's sixteen rules in the evidence register, CANONICAL; its checks C1-C16 and P4-P14 as a fixture"
  - "[ ] 0b. The canonical rule recorded in the decision package; Q5, Q6, Q7 decided by the owner from the sheets in § 4a; the kernel width on the fixed ruler and the audit's other open points put to its author; the R-smacof seam settled with engineering"
  - "[x] 1a. Stage 1 -- pair status UNKNOWN / RELIABLE / WEAK with N_min and the Fisher interval on the derived relation; the 5.5 stamp gone (F3)"
  - "[x] 1b. Stage 1 -- alignment and connectedness over PRIMARY objects, UNKNOWN pairs left out; mean rating as the default height (F8)"
  - "[x] 1c. Stage 1 -- every straight-liner NOT PLACED with a reason, out of the terrain, counted (F11)"
  - "[ ] 1d. Stage 1 -- the relationship-evidence policy Q6 decides: evidence sufficiency (UNKNOWN / WEAK / RELIABLE on the approved n basis) and practical materiality (meets_effect_floor at r_min) as two gates, each declared and recorded per pair (F3); after the Q6 decision"
  - "[x] 2a. Stage 2 -- per-person min-max over all rated items before Pearson (F2); a declared matrix type, no branch detection (F5); signed strength beside |r| (F4)"
  - "[x] 2b. Stage 2 -- object layout: delta = sqrt(2(1 - r)), SMACOF from a Torgerson start, Stress-1, no rescale to a radius (F6)"
  - "[x] 2c. Stage 2 -- one layout; Procrustes alignment to a reference map as a view layer; the quality label (F7)"
  - "[ ] 2d. Spec v3 and the preset aia-sociomap-2; aia-sociomap-1 kept as the comparison alternative; artifact v3; the research step adapter"
  - "[ ] 3. Stage 3 -- the common 0-1 scale (F1); ideal-point placement against the object map, per-respondent misfit e_k and its flag (F10)"
  - "[x] 4a. Stage 4 -- connectedness 0-100 with a respondent-bootstrap interval; rank only where intervals do not overlap (F9)"
  - "[ ] 4b. Stage 4 -- terrain as the max-envelope of hills, one formula for every surface (F12, F13)"
  - "[ ] 4c. Stage 4 -- row-conditional unfolding with per-respondent slope and intercept and the anti-degeneracy penalty, or its retirement behind F6 + F10 (F16)"
  - "[ ] 4d. Stage 4 -- region tests: positioning variables excluded, Holm, Cohen's d and h ranking (F14, F15), with sociomapping-engine chunk 8"
  - "[ ] 5. Results and the report: the Stress-1 label, arrows for RELIABLE pairs only, sign as colour, the not-placed count; the client gate unchanged (OI-17)"
  - "[ ] 6. Ledgers and the decision package: parity-matrix pins, D6 v2 re-scoped to aia-sociomap-2, OI-13 and OI-16 wording"
  - "[ ] I0. Freeze the study-input and map-request contracts: dimensions, population, audience, item roles and method selection"
  - "[ ] I1. Resolve selected dimensions and the audience into the fieldwork respondent context; unavailable inputs refused explicitly"
  - "[ ] I2. Build study-wide rating inputs before slicing families; keep F1 and F2 transforms separate; enforce PRIMARY/SECONDARY roles"
  - "[ ] I3. Carry eligible respondent descriptors, positioning-variable lineage and actual support into regions and readiness"
  - "[ ] I4. Preserve historical spec/artifact readers and pin methodology on run creation and retry"
  - "[ ] I5. Prove the complete study-to-map-to-report journey, including dimension/audience changes and frozen replay"
---
# Sociomap formula corrections -- the audit "NPC Sociomapa: faulty formulas in the code" fitted into AIA

**Owner:** method owner (QED Group; the audit is by Aram Bahbouh, status 6 October 2026) ·
**Engineering:** sociomapa-deterministic · **Started:** 2026-10-07 (chunks 0a, 1a, 1b and 1c landed, § 8a and § 10) ·
**Initial audit base:** `develop` @ `579b7ab`; **latest integration review:** `develop @ 08fdb26a`.

**Source.** `NPC_Sociomapa_Faulty_Formulas.pdf` (EN) and `NPC_Sociomapa_Chybne_Vzorce.pdf` (CS),
30 pages each, the same document in two languages. Received 2026-10-07; not vendored. Cited
below as "audit, F<n>" (Part I, pp. 3-18), "audit, § 12" (the evidence, pp. 21-28), "audit, § 9"
(the roadmap, p. 19). Its numbers in square brackets (`[C1]`...`[C16]`, `[P4]`...`[P14]`) are
printed by `NPC/analysis/code_formula_checks.py`, which we do not have (chunk 0a asks for it).

**Source verification, 2026-10-07.** The user supplied both PDFs and explicitly confirmed them
as the canonical decisions during the application integration review. The selected formulas do
not need to be approved again. Identifiers for the evidence register (not machine-local paths):
EN SHA256 `b45444c0d2df9e262b22f3a2dc19df3a794781866ebba6e2c78da89dbba5f9cb`;
CS SHA256 `3e2d679d47aedeb64e1227ac76ced15c1a9313cc125307e1cef366241356c0ac`.
Use F-number and page when citing them; equation numbering differs between languages.

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

## 2. Initial audit baseline: three computations

Sections 2, 3 and 7 retain the anchored initial audit at `579b7ab`; they are not a current
completion ledger. Chunks 0a, 1a, 1b and 1c have since landed (PRs #172, #173 and #179).
Pair status and PRIMARY scores now accompany the legacy map, all straight-liners are excluded
from its layout, and cache identity includes the engine implementation version. The legacy
relation matrix, classic height and layout still remain. Current progress is in § 8a and § 10;
the application integration review is in § 8.1.

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
| F16 unfolding targets stretched per respondent, one global scale | (9,9,9,10) and (1,1,1,10) get identical targets; (5,5,5,5) → "very close" to all | The unit's `fit_python_unfolding` is refused (OI-13; the plan found it present at `sociomap.py:53`). A's `aia_rowcond_unfolding_v1`: δ = scale_top − rating (`layout.py:237`, a constant multiple of the audit's δ_kj, equivalent under the free row scale) ✓; per-respondent slope b_k ✓; **no intercept c_k**; collapse prevented by a global normalisation, not smacof's penalty; straight-liners partly excluded (F11). R smacof refused in the existing path (OI-15; `domain/` is pure Python by rule) | **PARTIAL** | b_k and c_k per respondent, straight-liners out, λ·pen(U, V) as in `smacof::unfolding`; the canonical audit prefers R and calls Python "a test fallback". Resolve the R runtime behind an adapter, corrected fixtures and recovery tolerances in § 4 and chunk 4c; the pure-domain boundary does not authorize replacing the chosen method |

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

## 4a. Q5, Q6, Q7 as methodology decisions (the owner's), with options and consequences

The three questions the audit leaves open are not equations to approve; each is a statement
about what the map claims, and the statistician's part is to say which formula makes that
statement true. Rewritten on 2026-10-07 from the owner's assessment, with where AIA's code
stands today on each. The register's `AUDIT-F2`, `AUDIT-F3` and `AUDIT-F8` carry the ids.

### Q5 -- what proximity between two objects claims

**Decision.** Should two objects be close because respondents' *relative* preferences for them
move together, because respondents give them *similar absolute ratings*, or should these be two
distinct analytical concepts shown apart?

**Where AIA stands.** Chunk 2a (not yet built) follows the audit's F2: per-person min-max over
every item the respondent rated, then Pearson. That *is* a choice of relative co-movement: the
rescaling removes each person's level, and two objects everyone rates 9 and 9 have constant
columns, which AIA already reports as UNKNOWN (no correlation; chunk 1a, PR #172), not as
"close". So the canonical path answers "co-movement" by construction, and the open question is
whether that is the intended claim and whether "rated alike" needs a concept of its own.

| Option | What proximity means | Consequence down the chain (F2 -> F4 -> F6 -> F7 -> F8/F9) |
| --- | --- | --- |
| (a) Relative co-movement (the audit's F2 as written) | people who prefer one more than their usual also prefer the other more | a correlation-based distance (F2's Pearson after per-person min-max, then F6's δ); the map shows preference structure, not popularity; level is removed, so a universally loved and a universally disliked object can sit together if the residual preferences agree; arrows, distances and the F8/F9 scores all inherit the "co-movement" meaning |
| (b) Absolute rating similarity | the two objects receive similar ratings | a level-sensitive paired-rating distance, never a correlation. Pearson removes each object's mean, so it cannot say "rated alike": `[1, 2, 3]` and `[8, 9, 10]` correlate perfectly at very different levels, and two identical flat profiles have no correlation at all. The candidate is the mean absolute rating difference over the respondents who rated both, normalised by the declared scale range: `d_ij = mean_k abs(x_ki - x_kj) / (max - min)`, on a 1-10 scale `/ 9`; 0 for identical ratings, 1 for maximally different, defined for flat profiles. Proximity then carries level, not ties; F8/F9 would score level; a new declared method (a distance, not F2's correlation), not a parameter |
| (c) Two concepts, kept apart | positions from (a); level shown by a separate encoding | the audit's own shape: distance = co-movement (F6), height = mean rating (F8's default, Q7), so level is visible without entering the geometry; costs one more legend line and the discipline of never reading height as closeness |

Pearson belongs to (a) only. In short: (a) co-movement -> a correlation-based distance; (b)
absolute rating similarity -> a level-sensitive paired-rating distance; (c) both, kept apart.

AIA's reading until decided: (c) -- positions represent co-movement; absolute level is shown
separately (for example as height, Q7). It is what the audit's F2 + F8 already compose to, and it
keeps the geometry free of the inflation the audit measured (+0.39 of spurious relation from
rating habits). Chunk 2a builds (a) for the positions either way; (b) would be a new declared
method, not a parameter.

### Q6 -- the minimum evidence for a relationship

**Decision.** What minimum pairwise sample size does AIA require before it interprets a
relationship at all, and what uncertainty criterion must a relationship satisfy before it is
shown as reliable? "Is 30 the number" is the wrong question: 30 is a floor, not a proof.

**Where AIA stands.** Built (chunk 1a, PR #172) and already the three-state rule the assessment
asks for: `N_ij < n_min` -> UNKNOWN; `N_ij >= n_min` and the Fisher 95 % interval includes 0 ->
WEAK; excludes 0 -> RELIABLE. `n_min` has no default: the caller passes it (30, the audit's
working value) and every result records it, so changing the floor is a declared parameter, not a
code change. What is *not* decided: the floor's value, which `n` under weights, and whether a
statistically reliable but tiny relation should be drawn at all. Those last two are **not**
parameters the code takes today: `pair_status(r, n, n_min, confidence)` has no effect threshold,
and `derive_pair_relations` passes `len(ok)` to both the interval and the status. Choosing either
is new work, chunk 1d (chunk 1a is complete and is not the vehicle).

**Two gates, not one.** Effect size and statistical reliability are different concepts and the
policy keeps them apart:

- *Evidence sufficiency*: enough observations (or effective observations) and the uncertainty
  around `r`. This is the state `UNKNOWN / WEAK / RELIABLE`, unchanged in meaning.
- *Practical materiality*: optionally, `abs(r) >= r_min`. Recorded per pair as a separate
  `meets_effect_floor`, never folded into the state, so a tiny but precisely estimated
  correlation is RELIABLE and is not described as substantively strong.

| Option | Rule | Consequence |
| --- | --- | --- |
| (a) Floor + interval (as built) | UNKNOWN below n_min; WEAK if CI includes 0; RELIABLE otherwise | defensible and already in place; with N = 500 a relation of r = 0.10 is RELIABLE, so large studies show many faint arrows |
| (b) Floor + interval + practical floor | the state as (a); beside it `meets_effect_floor = abs(r) >= r_min` (e.g. 0.10 or 0.20) | separates "distinguishable from zero" from "worth drawing" without redefining RELIABLE; one more declared number, recorded like n_min; arrows and descriptions read both gates; F4's opacity already fades faint relations, so this mostly affects arrow counts and the F8/F9 sums. New code (chunk 1d): an explicit threshold in the policy, not a reading of `pair_status` |
| (c) Which n | the respondent count (as built, the audit's N) or Kish's effective n under weights | with weights, the count overstates the evidence and the interval is too narrow. If chosen, `derive_pair_relations` computes the pair's own Kish n from its valid respondents' weights, `n_eff = (sum w)^2 / sum w^2`, and uses the approved basis for both the floor and the interval instead of `len(ok)` (chunk 1d; `domain/evidence/support.py` has the formula). Kish's n inside the Fisher interval is itself a methodological approximation, so it is signed off explicitly, never assumed; the audit does not say (B9) |

AIA's reading until decided: (a) with n_min = 30 and the respondent count, both recorded on every
result. (b) and (c) each need chunk 1d, which lands after the Q6 decision.

**The ask, as one evidence policy.** The floor, the interval criterion, the practical floor and
the weighting question are one decision, not three: *how does survey weighting propagate through
the point estimate (the weighted Pearson of F2, B7) and its uncertainty (which n, B9), and what
states does a pair pass through?* The author is asked for an explicit model to accept or
replace, as the two gates above: the evidence state UNKNOWN (insufficient evidence on the
approved n basis) / WEAK (the interval crosses 0) / RELIABLE (it excludes 0), and beside it
whether the pair meets the effect floor. Statistically detectable is not practically
meaningful, and the methodology should say which one an arrow means.

### Q7 -- what terrain height claims

**Decision.** What statement does the default vertical dimension make: absolute evaluation
(popularity), relational connectedness, or another metric? The hills are the most visible
encoding on the map, and "high" must mean one thing.

**Where AIA stands.** `aia-sociomap-1` defaults to the unit's T-score of the classic relation sum
(carried, F8/F9); the audit's F8 says mean rating, pending Q7. Under F12's envelope (chunk 4b)
height equals the metric exactly, so whatever is chosen is what the hill says. Mean rating is a
directly observed quantity on the item's declared scale; connectedness K_i is derived from the
geometry's own input and depends on Q5 (what a relation means) and Q6 (which pairs count).

| Option | "High" means | Consequence |
| --- | --- | --- |
| (a) Mean rating (the audit's default) | people rated this object highly | observed, not manufactured; readable without the map; needs a rescale mode across sets with different scales (RTS-V1 none / this / all); an object loved by all but tied to nothing stands tall and isolated, which is honest |
| (b) Connectedness K_i | this object is strongly tied to the others | height and distance then say related things, which risks reading height as closeness; depends on Q5 and Q6, so it changes when they do; undefined for an object with no known pair (B8), which must then have no hill |
| (c) Alignment A_i | this object moves with (+) or against (-) the family | signed, so a terrain needs a zero plane; best as a colour, not a height |
| (d) Selectable, with (a) as the default | the legend says which | what the engine already supports (`object_height_metric` is a spec field); the decision is only which is the default in reports |

AIA's reading until decided: (d) with (a) as the default, which is the audit's tentative choice
and keeps the vertical dimension observed; (b) and (c) stay selectable analytical layers.

**Order.** Q5 first: it fixes the meaning of F2, and F4, F6, F7, F8 and F9 inherit it. Q6 and Q7
can be answered after, and both are declared parameters in AIA, so the code built so far does
not move when they are.

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

**F-5 (hypothesis: one occurrence, not reproduced). A research screen test waits its full 15 s
for the proposal dialog under the full suite's load, on a head whose web tree did not change.**
Anchor: `apps/web/src/components/rehome/research/test-native-agents.ts:62-68 @ 387a417`
(`NATIVE_JOB_WAIT` 15 s, `approveProposal`), failing test
`QuestionnaireStep.test.tsx:250-260` › *reviews the native brief analysis and questionnaire
before opening the editor*. Observed once: PR #176's Frontend job on `387a417` (run
37632214819, 2026-10-07 13:56 UTC): `Unable to find role="button" and name "Použít návrh"`
after 15 067 ms, 614 of 615 tests passed; the same job passed on the PR's previous head
`8cbb322`, and `git diff 8cbb322 387a417 -- apps/web` is empty. Reproduction attempted: the
full `npm test` on the same tree in a 4-core container passed 615 of 615 (45.9 s). Consequence:
a red Frontend job on a PR that touched no web file. The config-cache cause of this class was
fixed in PR #83 (OI-76); this residual has no confirmed cause and no fix is proposed, because a
wider wait only makes the failure slower (OI-76's own conclusion). Test that would catch it:
the repeated-run harness OI-76 used (`repeats: 60` on the file, and full suites under doubled
load), applied to this test, to measure a rate before anything is changed.

## 8. Chunks

- **0a.** Register F1-F16 in `docs/migration/sociomapping-evidence-register.json` with product
  `NPC-AUDIT`, page, formula, replacement and label CANONICAL; the register test keeps every
  implemented rule pointing at code and a test. Ask the owner for `code_formula_checks.py` and
  its printed `[C*]` / `[P*]` outputs; vendor them under
  `packages/aia_core/tests/fixtures/sociomapping_sources/` as the audit's fixtures.
- **0b.** Record the canonical rule and the five settled answers of § 4 in
  `sociomapa-methodology-decision.md` v2 (docs PR). Put the open items to the audit's author
  in one note: Q5, Q6, Q7, the F10 misfit threshold, σ on the fixed ruler. Settle the R seam
  with engineering (tolerance, host). The unanswered widths gate terrain integration in 4b;
  the F10 threshold gates chunk 3's misfit classification; the R contract gates 4c.
  Q6 and Q7 run on the audit's provisional values until answered. F2's chosen rule and
  2b's object geometry do not wait on another methodology decision.
- **1a.** `relations.py`: `pair_status(r, n, n_min)` → UNKNOWN / RELIABLE / WEAK with the Fisher-z
  interval; `research_sociomap.derive_relation_matrix` gains a variant that returns signed r,
  N_ij and status per pair (the 1-10 mapping and the 5.5 stamp stay only in the legacy variant).
  Artifact carries `relation.status`, `relation.n`, `relation.interval`.
- **1b.** `metrics.py`: `alignment` and `connectedness` over the PRIMARY set (today: every
  object of the battery) with UNKNOWN excluded; `mean_rating` as the v3 default height.
- **1c.** `engine.py` placeability: any constant row is NOT PLACED with the reason; count on the
  artifact; the density terrain over placed respondents only (already so).
- **1d.** After the Q6 decision (§ 4a). `relations.py`: an explicit evidence policy -- `n_min`,
  the confidence, the n basis (respondent count or pairwise Kish `n_eff = (sum w)^2 / sum w^2`
  over the pair's valid respondents) and an optional `r_min` -- declared and recorded on every
  result. `pair_status` keeps `UNKNOWN / WEAK / RELIABLE` as the evidence state on the chosen n
  basis; `meets_effect_floor` is recorded beside it, never folded in. `derive_pair_relations`
  stops passing `len(ok)` when the basis is Kish. Tests: a weighted pair whose count passes the
  floor and whose effective n does not is UNKNOWN; a precisely estimated r = 0.05 is RELIABLE
  and does not meet a 0.10 floor; with no `r_min` declared, nothing is computed for the floor.
- **2a.** `relations.py`: `person_minmax(ratings)` over all rated items of the respondent,
  constant rows excluded; Pearson on the result; `RelationScaleCoercion.DECLARED_CORRELATION |
  DECLARED_SIMILARITY_0_1 | DECLARED_STRENGTH_1_10` with no detection; the artifact stores
  signed r̃ and |r̃| side by side. F5 is `SPECIFICATION_REQUIRED`: the audit does not write out
  the transform from a declared 1-10 strength matrix into F6's correlation distance, so 2a
  refuses that type (named, not guessed) until the author supplies it.
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
  `INTERNAL_ONLY`); `layer_check` extended to the new preset name. Integration acceptance
  requires I0, I2 and I4 below; a new enum alone does not preserve historical fingerprints
  or freeze a run's requested method.
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
0a. F2's rule is settled by the canonical source; object geometry in 2b does not wait on a
terrain width. The unanswered fixed-ruler kernel widths gate 4b and respondent-density
integration, the F10 threshold gates chunk 3's misfit classification (a diagnostic-only
result must explicitly say it has no classification), and the R runtime/fixture/tolerance
contract gates 4c. I0-I5 are the application integration track in § 8.1, with their own
dependencies; they are not six tasks to postpone until after chunk 6.

## 8.1 Application integration: inputs, dimensions and the whole study (I0-I5)

**User direction, 2026-10-07:** make this fit the rest of the application, including its inputs
and dimensions, and record the work here for Claude Code. Formula implementation alone is not
completion of the application journey. These chunks implement the canonical decisions; they
do not reopen them. Existing client-delivery and evidence gates remain separate from accepting
the source methodology.

**Review baseline:** PR 171 head `d0017457`; initial integration review `develop @ 4dce18fc`,
refreshed against `develop @ 08fdb26a` on 2026-10-07. The compiler, fieldwork producer,
dimension UI, fieldwork contract and run-start/retry code cited below are unchanged. The
Sociomap adapter now adds pair statuses and PRIMARY scores but still reads a single battery
and selects the legacy preset at execution. The disconnects remain pre-existing.

### Evidence: where the current journey stops carrying the user's choices

| Input | Current implementation and consequence |
| --- | --- |
| Questionnaire and tracked objects | `domain/research_design.py:76-140 @ 4dce18fc` declares question types/scales and batteries with object ids, family and scale. `domain/fieldwork.py:75-128` carries answers, missing values, respondent/donor ids, weights and a spec fingerprint. These are the right foundations. |
| Selected study dimensions | `apps/web/src/research/persona.ts:120-150` saves `persona_dimensions.approved`; client additions come from knowledge item ids/titles (`:45-74`). `ResearchSpecification` has no dimension field (`domain/research_design.py:123-140`), and `compile_design` never copies the selection (`:375-389`). The UI choice does not reach the executed respondent contract. |
| Population and audience | The compiler retains source mode, strategy and only `has_filters` (`research_design.py:383-386`); readiness warns filters/custom audiences are not applied (`:462-469`). `apps/executors/src/aia_executors/ai_fieldwork.py:118-123` makes a fictional roster from sample size and a spec-derived seed, not the selected population and audience. |
| Full rating context | `domain/research_sociomap.py:292-320 @ 08fdb26a` still extracts one battery's answers. Putting `person_minmax` there without a study-wide input would violate F2: pp. 4 and 22 explicitly require all rated items and reject active-family-only normalization. Open PR #183 starts the cross-battery adapter; its remaining integration work is recorded below. |
| Map roles and comparison descriptors | `ObjectRole` and `primary_scores` now exist, but the adapter explicitly declares every tracked object PRIMARY (`research_sociomap.py:312-316 @ 08fdb26a`). `SpecObject`/`SpecBattery` still have no role or map lens (`research_design.py:97-119`), and `FieldworkRespondent` has no general descriptor snapshot (`fieldwork.py:80-87`). A selected dimension's label is not a measured or materialized respondent value. |
| Readiness and invalidation | Structural readiness passes an existing battery as Sociomap input (`research_design.py:453-457`), while the allowed study sample starts at 20 (`:62`) and F3's working pair minimum is about 30. The impact model already includes dimensions, audience and population snapshot as fieldwork inputs (`domain/pipeline.py:275-295`), but the execution compiler drops some of them. |

**Reproduction (2026-10-07, repeated at `08fdb26a`, no model calls):** compile otherwise identical valid studies with
`persona_dimensions.approved = ["finance"]` versus `["ekologie"]`. Both compile without errors
and their specifications and fingerprints are equal. Repeat with audience filters 18-29 versus
60-80: both compile to the same audience, `{source_mode: population, strategy: population,
has_filters: true}`. Saved Design Revisions can differ; the defect is the missing semantics in
the executed specification. Reading the full design for material classification does not pass
its chosen dimensions to respondent generation.

### Contract and boundaries

The complete chain is:

```text
Frozen Design Revision + selected dimensions + population revision + audience
  -> resolved respondent context and declared questionnaire
  -> frozen answers + eligible respondent descriptors
  -> canonical Sociomap inputs and frozen method
  -> immutable map artifact
  -> views / region analysis / report / interpretation sidecar
```

Keep four concepts separate in typed contracts:

1. **Study/persona dimensions:** selected attributes or constructs that resolve to versioned
   definitions and authorized respondent values. Choosing a label does not invent values.
2. **Measured rating items and object families:** declared observations, scales, item ids and
   object identities that can enter the canonical formulas.
3. **Descriptive variables:** attributes or answers used to describe groups, with provenance
   and an explicit eligibility decision for comparisons.
4. **Map coordinates:** computed output. A selected dimension is not automatically an axis or
   an object on a map.

Knowledge approval, dimension materialization and population promotion remain different acts:
`source -> evidence proposal -> human approval -> materialization -> validation/calibration ->
explicit new LIVE revision`. This feature must not implement another population loader or
promote LIVE when someone chooses a dimension. Application services resolve inputs through the
existing scope and `PopulationRuntime` capabilities; the pure domain receives immutable typed
values; executors orchestrate; API and UI do not derive research rules.

### Chunks and acceptance

**I0. Freeze the study-input and map-request contracts.** Before integrating v2, specify the
selected dimension ids/definition versions, their intended roles, the population binding and
weight scheme, actual audience selection, questionnaire item/scale identities, the complete
rating universe and its identity, primary/context object sets, positioning-variable lineage,
and the selected methodology/spec fingerprint. Store immutable bindings on the run rather than
reading whichever definition or LIVE population is current when a worker runs. Define legacy
reading without back-filling historical inputs. Resolve whether a run selects one method or a
named comparison set. A changed input changes the appropriate execution/reuse identity;
presentation-only changes do not trigger fieldwork.

**I1. Resolve dimension and audience choices before fieldwork.** Extend the compiler and
application/producer boundary so selected dimensions reach persona construction or their other
declared role, and the actual audience selects the roster. Resolve materialized values using
the approved population binding; retain lineage, missingness, donor ids and weights. If a
dimension or source cannot be executed, return an explicit unsupported/not-ready result rather
than claiming that the selection was applied. Keep the fictional source explicitly fictional;
do not quietly substitute it for a missing population. This is a dependency on the population
and dimension-materialization work, not permission to reconstruct it inside Sociomap.
**Tests:** changing a fixture dimension changes the resolved context and identity; an age
filter changes eligible respondents; missing materialization is named; another client's values
are unreachable. Do not require a stochastic model's final answer to differ as proof of wiring.

**I2. Build the canonical rating adapter across the study.** Resolve all declared rating items
and scales from the frozen questionnaire and answers before slicing an active object family.
Record which items determine each person's normalization bounds. Keep F1's scale-normalized
ratings for F10 distinct from F2's person-normalized ratings for object relations. Do not infer
rating objects from numeric columns or include demographic descriptors as ratings. PRIMARY
membership governs scores and object terrain; SECONDARY objects cannot silently alter those
results. Expose the item-selection and transformation lineage on the artifact. Where ordering
across mixed scales is not specified by the sources, record the exact unresolved parameter
instead of borrowing an old RTS rule.
**Tests:** with two batteries, active-family switching leaves the global normalization context
unchanged; changing a rated item outside the active family affects F2 when it changes a bound;
F10 still uses declared scale ends; numeric descriptors are not ingested as rating objects;
adding context objects alone does not change PRIMARY scores or terrain.

**I3. Descriptors, exclusions and actual support.** Carry eligible dimension values and other
descriptors beside answers, with their definition/source versions and missingness. Freeze the
positioning-variable set so F14 can exclude it; unplaced respondents are excluded from terrain,
lasso and comparisons, with their count retained. Distinguish structural readiness to collect
answers from sufficient support to produce a map or pair: apply N_min after missingness and
constant-row handling; define explicit outcomes for all-UNKNOWN and disconnected inputs.
Preserve weights and donor provenance, and document their treatment in correlation, support
and bootstrap without silently changing the canonical formula. Retain Welch, which audit
pp. 27-28 declares sound; apply Holm and d/h as specified. A categorical significance procedure
not given by the audit remains separately declared, not an implied answer to all of M8.
**Tests:** insufficient pair support remains UNKNOWN even when total study N is large;
positioning variables cannot be tested inferentially; a descriptive dimension is only used
when its value/provenance and evidence eligibility exist; unplaced people never enter a region.

**I4. Historical reading and frozen method execution.** `SociomapSpec.fingerprint()` currently
includes a global contract version (`domain/sociomap/specification.py:259-261 @ 4dce18fc`);
the artifact reader recomputes it (`models.py:492-505`). In-memory changing that global from
2 to 3 makes an unchanged old payload fail with `ArtifactIntegrityError`. Add version-aware
hashing/reading rather than replacing the old contract. `application/research.py:225-267,
299-305` currently freezes no Sociomap method at start/retry; the executor chooses the preset
when it executes (`apps/executors/src/aia_executors/research.py:429-476 @ 08fdb26a`). Pin the selected spec
or comparison set at enqueue and preserve it on retry. Explicitly treat historical runs with no
selection as legacy v1. Preserve the canonical artifact/battery/object identifiers used by
ADR 0021, or version every affected consumer.
**Tests:** pre-change artifacts retain their hashes and view references; v1 and v2 for one
design have distinct run identities; enqueue before a default change and execute/retry after it
still uses the originally frozen method and source bindings; tampering remains refused.

**I5. Whole-application acceptance.** Run a recorded, fictional study with two object families,
different declared scales, selected fixture-materialized dimensions, an actual audience filter,
a frozen fixture population binding, missing answers, a constant respondent and context objects.
Prove I1-I4 through the real application/executor path, then Results and the report. Both render
the same stored geometry, scores, support, exclusions, method and provenance; neither recomputes
the map. Change a dimension, audience and rating input in separate new revisions and verify the
correct invalidation and fresh bindings. Replay the original run unchanged. Interpretation
Research may read the pinned artifact; its Lens remains a sidecar and external research cannot
change canonical coordinates or deterministic findings (ADR 0021). A fixture success does not
claim live population/materialization availability or client-delivery approval.

**Dependencies and ownership.** I0 first; I1, I2 and I4 can be developed as separate slices
after it. I2 integrates 1a-2b and 3; I3 supplies the input/exclusion contracts needed by 4d.
I4 gates the integration part of 2d. Chunk 5 and I5 require those contracts and the applicable
mathematical chunks; unavailable upstream services must be named, not silently bypassed.
Formula unit tests may proceed using explicit frozen fixtures while I1 is incomplete. Keep
the experimental H-Model as a named comparison path and coordinate shared Results/report and
region files with `sociomapping-engine.md`; synchronize its competing v3 claim through its own
plan/docs follow-up. The implementer reports engine progress and application integration
progress separately. Do not mark the full journey complete because only the formulas pass.

### Current changes and open-PR coordination (2026-10-07)

**Merged through `develop @ 08fdb26a`.** PR #172 supplies pair status and complete straight-line
exclusion; PR #173 registers the canonical audit; PR #179 adds `ObjectRole` and PRIMARY
alignment/connectedness. Reuse their public contracts in I2/I3; do not implement them again.
No I0-I5 chunk is complete: the study compiler still has no role/dimension contract, the
producer still has no applied audience, and the complete corrected map has not reached Results.
`SOCIOMAP_VERSION = aia-research-sociomap-3` is the research body version, not spec/artifact v3
or the future `aia-sociomap-2` preset (`domain/research_sociomap.py:72-77 @ 08fdb26a`).

**I4 is partly supported, not finished.** `_sociomap_fingerprint` now includes the engine
implementation version and the research body version (`executors/research.py:429-445 @
08fdb26a`; `test_a_changed_engine_is_not_handed_the_previous_engines_map`). This
prevents cross-engine cache reuse. It does not freeze the chosen method at enqueue: the preset
and engine are still resolved by executing code, and version-aware historical spec readers
remain pending. Retain those I4 tests after reusing the new fingerprint helper.

**Deep Research changes.** PR #178 accepts selected Design Research evidence into a new Design
Revision through `DesignResearchProposals.accept` (`application/design_research.py:87-135 @
08fdb26a`); `apply_to_design` writes only `design_research`, leaving questionnaire, dimensions
and audience unchanged (`domain/deep_research/design_proposals.py:227-277`). Accepting evidence
does not materialize a dimension or inject it into ratings. PRs #175/#177/#180/#181 add ADR
0022's approved policy settings and Settings surface; those settings do not select Sociomap
methodology. I5 must preserve the accepted evidence lineage and the Interpretation Research
sidecar boundary. Extend its recorded acceptance with an evidence-only Design Research accept:
the dimension/audience/rating contracts stay unchanged until a person explicitly edits them.

**Open PR #183, `feature/sociomap-person-minmax @ 0dae6ff6`, not merged.** Its
`rescaled_battery_ratings` resolves declared scales across `spec.batteries` before slicing a
family, stores `relation_rescaled`, and moves the research body to `aia-research-sociomap-4`
(`domain/research_sociomap.py:313-349, 430-462` at that head). This addresses part of I2; reuse
it after merge. The adapter enumerates batteries only, so I0/I2 must explicitly decide which
standalone scale questions are rating items; a numeric descriptor must never enter by dtype.
Test a standalone item explicitly declared as a rating alongside two batteries, and record
the full item/scale universe, not only battery ids. PRIMARY/SECONDARY selection, frozen method
bindings, region descriptors and the full acceptance remain I0-I5 work. Do not tick 2a or I2
here before that PR lands. Its F1-before-F2 mixed-scale ordering is a declared implementation
reading to reconcile with I2's source questions, not an additional owner-approved formula.

**Open PR #176, `chore/sociomap-decision-sheets @ 6d1c069d`, not merged.** It records the owner's
Q5/Q6/Q7 decision sheets and the author's parameter/semantics questions. Preserve that section
and its evidence-register states when reconciling the plan after merge; retain I0-I5 and the
canonical PDF identifiers too. The sheets cover the questions the source leaves open; they
do not require reapproval of settled formulas. Neither open PR is part of the merged baseline.

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

**Request to the audit's author (chunk 0a and 0b, to be sent by the owner).** Revised on
2026-10-07 after the owner's second assessment; the annotated PDF mirrors this list. Three
groups: A, what the audit itself leaves open; B, readings AIA has taken, to confirm or correct;
C, the evidence to reproduce the audit.

- **A1 (Q5, F2).** What does proximity between two objects claim: relative preferences moving
  together, similar absolute ratings, or two concepts kept apart? AIA's *provisional*
  implementation follows the first (positions from co-movement, level as height) pending
  methodology confirmation; it is not the answer. F4, F6, F7, F8 and F9 inherit the decision.
- **A2 (Q6, F3, with B7 and B9).** One evidence policy: the pairwise floor before a pair is
  interpreted at all; the uncertainty criterion before it is shown reliable; whether reliability
  also needs a practical floor on |r|; and how survey weighting propagates through the point
  estimate (weighted Pearson after per-person rescaling) and its uncertainty (the respondent
  count or Kish's effective n). An explicit state model is asked for (§ 4a Q6).
- **A3 (Q7, F8).** What does terrain height claim: absolute evaluation (mean rating, observed),
  relational connectedness (derived, depends on Q5 and Q6), or a selectable default? AIA's
  provisional reading: mean rating as the default, the others as layers.
- **A4 (F10).** How should the respondent-misfit threshold for "poorly represented" be
  calibrated and validated: absolute on the fixed ruler, calibrated on planted preference
  structures, percentile-based, or derived from another criterion? The recommended value *and*
  the acceptance evidence behind it, not a number alone.
- **A5 (F6 with F11, F12).** On the fixed ruler (one map unit means the same everywhere; delta in
  0..2) the kernel widths from the unit's +-62 frame have no meaning. Two separate kernels, each
  with a semantic definition relative to the ruler: the object-terrain kernel (how broad each
  object's hill is) and the respondent-density kernel (how much smoothing where people cluster).
  They need not share a width. Blocks chunk 4b.
- **A6 (F16).** The audit's checks covered the target defect only. If AIA's planted-ideal-point
  recovery is to stand as the acceptance, what properties and tolerances constitute successful
  recovery: correct relative object geometry; respondent ideal-point ordering recovered;
  invariance to a respondent's scoring generosity; known straight-liners excluded; no degenerate
  collapse; a deterministic result within tolerance?
- **B8 (F8).** With the denominator fixed at m_P - 1, leaving an UNKNOWN pair out equals counting
  it as a zero relation. AIA's reading: divide by the object's known PRIMARY pairs, an object with
  no known pair has no score, and *the count of known pairs is stored and shown beside each
  score* (0.75 from 2 pairs is not 0.75 from 20).
- **B10 (F16).** R `smacof::unfolding` as the reference, the pure-Python fit as the test
  fallback: agreement on one R fixture within a tolerance does not by itself establish the same
  method. AIA proposes three layers for "methodologically equivalent within stated tolerance":
  fixture parity on known examples; property tests (rotation and reflection invariance,
  straight-liner behaviour, no collapse); recovery tests on planted ideal points. Acceptable?
- **B11 (F8).** The SECONDARY rule as AIA has written it: context objects never enter PRIMARY
  scores or terrain. Is that the whole boundary? May SECONDARY objects affect the PRIMARY
  layout, respondent placement, Procrustes alignment, Stress-1 or any other derived quantity?
  If they move PRIMARY coordinates they affect conclusions without entering a score formula.
- **C12-C15.** `NPC/analysis/code_formula_checks.py` as run for the 6 October 2026 status; its
  printed output (every `[C*]` and `[P*]` number); the simulated inputs behind C1, C2, C4/P4,
  C10/P10, C11, C12/P12, C13, C14/P14 and C16, or the seeds and generators; if the demo dataset
  cannot leave, the per-check summaries as they stand (C1's mean r and share positive, C5's
  stresses, C6's disparities, C8's rankings, C9's scores, C10's radii). The chain a canonical
  rule should have: methodology claim -> executable validation -> frozen fixture -> CI test ->
  implementation. Today the fixture is a transcription of the PDF, marked as such.

**Governance of the register while these are open.** Authority and completeness are two
things. Every audit rule is `CANONICAL` in authority (its label: it overrides every other
source); that does not make every formula implementation-complete. The register's
`canonical.completeness` says which, per rule: `SPECIFIED` (formula and meaning fully
specified), `PENDING_PARAMETER` (the formula is fixed; a number is open: F3's floor and
practical floor, F10's threshold, F11's and F12's kernel widths, F16's tolerance),
`PENDING_SEMANTICS` (what the rule claims is open: F2 under Q5 and the weighting, F8 under Q7,
the denominator and the SECONDARY boundary) or `SPECIFICATION_REQUIRED` (part of the formula is
not written out, so an implementer would have to invent methodology: F5's 1-10 strength
transform). The test refuses anything but `SPECIFIED` without a named question, so a
provisional AIA reading cannot pass for a finished methodological decision.

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
- `CLAUDE.md` § 7 Known flakes: an entry for F-5 above in the required shape, once a second
  occurrence or a measured rate confirms it; `.planning/open-items.md` OI-76: the 2026-10-07
  occurrence on PR #176 as a residual of the class after PR #83.
- `AGENTS.md`: nothing yet.
- `docs/architecture/research-journey.md`, `population.md` and `data-model.md`: after I0-I5
  land, document the frozen dimension/audience/population/map bindings, input roles, actual
  support checks and their implemented producer/consumer boundaries.
- `CLAUDE.md` / `ARCHITECTURE.md`: record the new typed contracts and version-aware readers,
  composition ownership and enforcement only once implemented; preserve pure-domain and
  population-loader boundaries. This plan is the record until the dedicated docs PR lands.
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
  gains "; `RelationScaleCoercion.DECLARED_*` (a declared strength 1-10 refused by name until
  F5's transform is written out)"; `research_sociomap.py` gains "; each pair after the
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
- From chunk 2b: `CLAUDE.md` map, `domain/sociomap/layout.py` "declared layout registry;
  aia_rowcond_unfolding_v1" gains "; `fit_smacof_objects` (audit F6: objects alone on the fixed
  ruler sqrt(2 (1 - r~)), weighted SMACOF from a Torgerson start, UNKNOWN pairs weight 0, Stress-1,
  never rescaled)". `sociomapa-deterministic-engine.md` § 8 a row -- reference: targets
  `14 + 46 (1 - m / m_max)` and the map stretched to radius 38 or 44 (four copies, F7); production:
  `aia-sociomap-1` keeps its unfolding, `fit_smacof_objects` beside it on the fixed ruler, read by
  no preset until 2d; tests `test_the_map_is_never_stretched_to_a_radius`,
  `test_a_family_without_structure_keeps_its_size_and_says_so`.
- From chunk 2c: `CLAUDE.md` map, `domain/sociomap/view.py` "drag overrides, view terrain,
  scenarios (never write) F9" gains "; `align_to_reference` (audit F7: a map turned onto the
  previous one by rotation/reflection only, a view) and `stress_quality` (the audit's Stress-1
  label)". `sociomapa-deterministic-engine.md` § 8 a row -- reference: four layout copies that
  disagree (the scenario view turns the map a quarter and enlarges it 16 %), no fit shown;
  production: one layout (2b), aligned as a view, labelled; tests
  `test_a_turned_map_is_turned_back_without_scaling`, `test_every_stress_carries_the_audits_label`.
- From chunk 4a: `CLAUDE.md` map, the `metrics.py` line gains "; `connectedness_100`: K100 =
  100 K with a respondent-bootstrap interval (B and seed declared, OI-62's generator, pair status
  fixed from the full sample), `rank_with_ties`: an order only where intervals do not overlap,
  as a relation per pair and a rank range per object (audit F9)"; `research_sociomap.py` gains
  "; `connectedness_100` with its ranking, over `CONNECTEDNESS_RESAMPLES = 500` and
  `CONNECTEDNESS_SEED`". `sociomapa-deterministic-engine.md` § 2: beside the F8 scores, "K100 and
  its interval (audit F9), stored by the research step, read by no surface yet"; § 8 a row --
  reference: the normative score `50 + 10 z` (panel ÷n, report ÷(n−1)), always winners and
  losers; production: `tscore` kept for `aia-sociomap-1`, `connectedness_100` and `rank_with_ties`
  beside it; tests `test_intervals_that_overlap_or_touch_are_tied`,
  `test_overlap_is_not_transitive_so_there_are_no_tie_groups`. `.planning/open-items.md`: finding
  F-4a-1 (§ 10, chunk 4a) numbered, and put to the audit's author with group B of § 8a (a
  percentile interval for a mean of |r| sits above its point near zero); the bootstrap's cost
  (89 s for one 1,500 x 22 battery) as an open engineering item.

## 10. Progress and review outcome

2026-10-07: application integration reviewed against `develop @ 4dce18fc`; I0-I5 added at the
user's request. The canonical formulas fit the intended architecture, but the current
dimension/audience selections do not reach the executed fieldwork contract. The two compiler
probes in § 8.1 reproduce the gap. Existing baseline verification: 193 focused Sociomap tests,
91 layering rules and 7 exposure rules passed; all 41 plans were well-formed before this edit.
These checks do not certify the unbuilt corrected method or complete application integration.
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

At the 1a landing no score, layout or terrain read the status. Since then 1b reads it for
PRIMARY scores; layout and terrain still do not (2b, 4b); the engine
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

### Application integration refresh, 2026-10-07

Reconciled PR #182 with `develop @ 08fdb26a`, preserving the completed 0a/1a/1b/1c chunks
and their measured progress. Re-ran both compiler probes: different dimensions and age
filters still produce equal execution specifications and fingerprints. Added coordination
for open PRs #176 and #183, and separated cache invalidation already implemented from
method pinning still pending. I0-I5 remain open. The initial audit tables retain their dated
baseline; the current integration evidence above identifies changed code explicitly.

### Chunk 2a -- each person on their own scale (F2), a declared matrix type (F5), 2026-10-07

**Why now, with Q5 open.** The audit names this variant as chosen ("This is the variant we chose
(per-person normalisation within the active family only was rejected)", § 12 F2, p. 22) and
leaves only Q5 (co-movement vs "rated alike") open; § 4a's sheet (#176) records AIA's reading
until the owner decides, (c): positions represent co-movement, absolute level is shown apart, and
"chunk 2a builds (a) for the positions either way". `relation_rescaled` is that (a); if the
decision changes the rule, it changes under a new `SOCIOMAP_VERSION`.

What landed, on `feature/sociomap-person-minmax`:

- `domain/sociomap/relations.py`: `person_minmax` (eq. 5: `(a - min_l) / (max_l - min_l)` over
  every item the respondent rated; a row with no spread -- one value, one item or none -- is
  excluded, never 0/0; non-finite refused) and `PersonScaled`. `DeclaredRelationType` and
  `coerce_declared_1_10` (eq. 11: correlation `1 + 9 (x + 1) / 2`, similarity `1 + 9 x`, chosen
  by the declaration; a cell outside the type's range or non-finite refused, never clipped or
  5.5). A declared strength 1-10 is **named and refused** (`DeclaredTypeUnspecified`, and
  `require_supported` refuses the spec): register `AUDIT-F5` is `SPECIFICATION_REQUIRED` (#176),
  the audit names the type without writing out its transform into F6's distance. `mutual_relation_for_position` now projects through `mutual_from_1_10`, the same
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

Two readings this chunk declares, both to be reconciled in I2 (see the coordination note on this
PR above): **(a)** putting each item on its declared 0-1 scale (F1 eq. 3) *before* the per-person
min-max (F2 eq. 5) when sets have different scale ends is AIA's implementation reading, not an
owner-approved formula -- the audit writes the two transforms separately; on one shared scale the
order changes nothing. **(b)** the "all items rated" of F2 is enumerated from the specification's
tracked sets only: a standalone scale question is not a rating item here until I0/I2 decide which
ones are, and no numeric descriptor enters by its type. `relation_rescaled.rated_with` records the
sets read.

What it does not do: no layout reads r~ (2b: SMACOF on `sqrt(2 (1 - r~))`), `aia-sociomap-1` lays
out over the unit's matrix as before; Results and the DOCX show nothing new (chunk 5); arrows by
`abs_r` and sign are chunk 5's.

Checks run: `ruff check`, `ruff format --check` (543 files), `mypy --strict` (300 files, clean),
`make layer_check` (100 rules), `make exposure_check` (7 rules), the evidence-register suite (24
passed), every `sociomap` test and the new `test_sociomap_person_minmax.py` (24 tests).

### Chunk 2b -- objects on a fixed ruler by SMACOF (F6), 2026-10-07

What landed, on `feature/sociomap-smacof-objects` (stacked on #183, chunk 2a):

- `domain/sociomap/layout.py`: `correlation_distance(r) = sqrt(2 (1 - r))` (eq. 13; refuses r
  outside [-1, 1]), `correlation_distances(r, known)` (targets from signed r~, `None` where the
  pair is not known), and `fit_smacof_objects(delta, *, max_iterations, tolerance)` -> `ObjectLayout`
  (points, Stress-1 by eq. 14 over the known pairs, raw stress, known pairs, iterations, converged,
  `start_fill`). Weighted SMACOF: Torgerson start (double-centred squared targets, top two
  eigenvectors by the module's Jacobi), Guttman transforms `X <- V^+ B(X) X` with
  `V^+ = (V + 11^T/m)^-1 - 11^T/m` (Gauss-Jordan), stop on a relative raw-stress improvement below
  `tolerance`; then the unfolding's gauge (centroid, principal axes, third-moment reflection) --
  translation, rotation, reflection only, **never a rescale**. `max_iterations` and `tolerance`
  have no defaults. Refused: fewer than three objects, an asymmetric, negative or non-finite target,
  a known-pair graph that does not connect every object.
- One choice the audit leaves open, recorded on every layout: an UNKNOWN pair's squared target
  in the Torgerson *start* is the mean of the known ones (`start_fill`; `None` when every pair is
  known). It shapes only where the iteration begins; the stress weights the pair 0.

Measured (`test_sociomap_smacof_objects.py`): a planted 8-point configuration recovered to
Stress-1 ~ 1e-16 in 3 iterations, and with two UNKNOWN pairs in 26; twelve objects whose
correlations are cos(a - b) land on radius 1.000000 (the unit would have stretched them to 38);
twelve near-independent objects (r in [-0.09, 0.08], every target 1.35-1.47) Stress-1 0.335 --
"2D picture unreliable", the audit's own run reports 0.307 on its data -- within radius 1.03,
where a strong family of the same size spans 1.26. The audit's demo optimum (0.296, [C5]) and
the families of [C4]/[P4] are not reproducible without its data.

What it does not do: the plan's `DissimilarityTarget.CORRELATION_DISTANCE` and
`MapFrameMethod.FIXED_RULER` spec members move to 2d with spec v3, where the engine and the research
step read them; adding them now would let a v2 spec name a layout the v2 engine cannot run. No
research body stores an object layout yet (2d), so `SOCIOMAP_VERSION` does not move. Results and
the report show nothing new (chunk 5).

### Chunk 2c -- one layout, aligned as a view, labelled (F7), 2026-10-07

What landed, on `feature/sociomap-smacof-objects` (with 2b):

- `domain/sociomap/view.py`: `stress_quality(stress_1)` -> `StressQuality` (GOOD < 0.05 <= FAIR
  < 0.10 <= WEAK < 0.20 <= UNRELIABLE; each bound belongs to the band above it; a negative or
  non-finite stress is refused, not labelled), with `STRESS_QUALITY_TEXT` holding the reader's words
  ("2D picture unreliable"). `align_to_reference(points, reference)` -> `AlignedObjects`: eq. 16's
  `argmin_Q ||P* Q - P_previous||` over rotations and reflections about the origin, fitted on the
  objects both maps hold; no translation and no scaling (both maps come centred from the layout's
  gauge, and Q is rotation/reflection as the audit writes it), so every distance and the Stress-1
  are the layout's own. An object in one map only is turned with the rest; fewer than two common
  objects are refused. `base` and `reference` fingerprint the two inputs: a view names what it
  turned and never replaces it.
- The existing `layout.procrustes_align` (parity comparisons) is unchanged: it centres both inputs
  and may scale, which a reader's view must not.

What it does not do: nothing prints the label yet. The plan's 2c line has it printed by the DOCX
figure and Results, but the only map they draw is `aia-sociomap-1`'s unfolding, whose stress is
over respondent x object cells -- a different measure from eq. 14's -- so labelling it with the
audit's bands would be a reading the audit does not make. The label reaches the reader with the
v2 map in chunk 5. No stored map is aligned to a previous wave until 2d stores object layouts
and chunk 10 (engine plan) brings waves.

### Chunk 4a -- connectedness 0-100 with a respondent-bootstrap interval (F9), 2026-10-07

What landed, on `feature/sociomap-connectedness-interval` (stacked on #183, chunk 2a):

- `domain/sociomap/metrics.py`: `connectedness_100(object_ids, roles, correlate, *, respondents,
  resamples, seed)` -> `Connectedness100` (per PRIMARY object `k100 = 100 K_i`, `low`, `high`,
  `resamples_scored`, `known_pairs`; plus `resamples`, `seed`, `generator`, `quantiles`,
  `respondents` and the rule id `audit-f9-connectedness-100-respondent-bootstrap-v1`).
  `resamples` and `seed` have no default; a bool, zero or negative is refused. `K_i` is
  `primary_scores`' connectedness (1b), so F8's PRIMARY set and UNKNOWN rule hold inside every
  resample. `rank_with_ties(intervals)` -> `TiedRanking` (rule
  `audit-f9-rank-where-intervals-do-not-overlap-v1`). `linear_quantile`, `PairCorrelator`,
  `RankRelation`, `RankedObject`, `ConnectednessInterval`.
- `domain/research_sociomap.py`: each set's body gains `connectedness_100` (the payload plus its
  `ranking`), over `CONNECTEDNESS_RESAMPLES = 500` and `CONNECTEDNESS_SEED = 20261007`, module
  constants declared by name and recorded on the body. The correlator it passes is
  `derive_pair_relations` over the rows `rescaled_battery_ratings` already put on each person's
  own scale, with weight x multiplicity (the weighted Pearson of duplicated rows): rescaling is
  per person, so a drawn row is rescaled once, not per resample. `SOCIOMAP_VERSION` `-4` -> `-5`,
  because the executor fingerprints its input with it and a body stored under `-4` (without the
  intervals) must not be reused as if it had them.
- Register `AUDIT-F9`: `implementation` and eleven `validation` entries; completeness stays
  `SPECIFIED` (the formula is the audit's; the readings below sit in `uncertainty`, and K inherits
  F8's open semantics there).

**Readings chosen where the audit is silent** (recorded in the rule text and the register):

1. *Pair status is fixed from the full sample.* The bootstrap measures the variability of one
   statistic, K_i over the full sample's known PRIMARY pairs, so every resample averages that same
   set; a resample's own statuses are not read (a full-sample UNKNOWN pair stays out even where a
   resample could compute it). The alternative, recomputing status per resample, would let the
   denominator move between resamples and make the interval a mixture of different statistics.
2. *A resample that cannot compute one of an object's known pairs does not score that object*
   (constant column there, or nobody drawn who rated both). Not 0, not K over fewer pairs; it is
   left out of that object's quantiles and `resamples_scored` says how many remained. An object
   unscored in the full sample has no K100, no interval and no resamples.
3. *Generator and quantile are aggregation's* (OI-62): `random.Random(seed).random()`, index
   `min(floor(u n), n - 1)`, and `research_aggregate._quantile`'s linear rule (`np.quantile`'s
   default, type 7), reimplemented as `linear_quantile` because the Sociomap package imports
   nothing outside itself, and pinned value for value to `_quantile` and to the generator's name
   (`test_the_quantile_and_the_generator_are_aggregations`). Every respondent of the sample is a
   cluster, including one who rated nothing in the family (the sample's size and composition).
4. *Ranking shape.* Overlap is not transitive (a ~ b, b ~ c, c above a), so there are no tie
   groups and no single rank: `TiedRanking` gives, per object, `outranks` / `outranked_by` /
   `tied_with` and a rank range `rank_best = 1 + |outranked_by|`, `rank_worst = ranked -
   |outranks|`, plus `relation(a, b)` -> ABOVE / BELOW / TIED. Closed intervals: touching
   (`low_i == high_j`) is overlap, so tied. Objects keep the input's order; objects without an
   interval are `unranked`, never last.

**Measured cost** (this container, Python 3.12, pure Python):

- Captured case `A01_full_questionnaire` (450 respondents, 5 objects, 1 battery), B = 500: the
  bootstrap alone 1.22-1.30 s (three runs); `battery_sociomap` as a whole 3.9 s.
- Synthetic 1,500 respondents x 22 objects (independent tastes, a generosity habit, integer 1-10,
  per-person min-max), B = 500: **89.3 s and 92.8 s** (two runs), 0.18 s per correlation pass
  (`derive_pair_relations` over 231 pairs; 0.25 s for one pass alone on uniform data). That is
  per battery: a specification with four such batteries adds about six minutes to the research
  step. **B stays declared at 500**; nothing shrinks it. The trade-off, for engineering with the
  owner: (a) a bootstrap-specific correlation pass -- each pair's common-rater index and the five
  weighted sums computed over the drawn respondents only, the full sample still through
  `derive_pair_relations` -- estimated 3-5x faster, not bit-identical to `derive_pair_relations`
  (summation order), so it would be pinned to it within 1e-12 by a test and named on the body;
  (b) the bootstrap as its own research step (or one per battery) so it runs in parallel and
  retries on its own; (c) a smaller B is the owner's call, not engineering's, and would record its
  Monte Carlo error. (a) and (b) compose; neither changes a number the audit specifies.
- Test suites: `test_research_sociomap.py` takes about 42 s (each `battery_sociomap` call on A01
  pays the 1.3 s bootstrap on top of about 2.6 s for the rest).

**Finding F-4a-1 (methodological, for the audit's author with group B of § 8a).**
1. Claim: where an object's pairs are near zero, the audit's percentile interval for K100 lies
   above the full sample's K100, often excluding it. 2. Anchor: the rule, `metrics.py`
   `connectedness_100` (this chunk); the cause is K being a mean of |r|: a resample's duplicated
   rows add noise that |.| folds upward. 3. Reproduction:
   `test_sociomap_connectedness_100.py::test_near_zero_the_percentile_interval_sits_above_its_point`
   (200 respondents, 20 independent objects, B = 100: 10 of 20 intervals wholly above their point,
   none below). On the 1,500 x 22 synthetic at B = 500: 3 of 22 exclude the point, all from above,
   and the point sits on average at 14 % of its interval's width from the low end. In typical data
   with real relations (A01; the planted two-taste family) every interval contains its point.
   4. Consequence: a weakly connected object is shown with a margin that does not contain its own
   score; rankings among weak objects are still read from overlap, but the interval misdescribes
   the estimate. 5. Smallest fix: not ours to choose -- a bias-corrected (BCa) or basic bootstrap
   interval, or a debiased K, is a methodology change to F9; AIA keeps the audit's percentile
   interval and records this. 6. The test above is the one that catches it.

What it does not do: no height, terrain, Results or DOCX surface reads K100 or the ranking (chunk
5); `tscore` and `relation_classic` stay `aia-sociomap-1`'s, unchanged; the seed is a module
constant, not a spec field, until spec v3 (2d) has a place for it (§ 8's 4a line says "a spec
field"; the constant is recorded on every body meanwhile). Pair status in the resamples does not
use Kish's n (1d).

Checks run: `ruff check`, `ruff format --check` (490 files), `mypy --strict` over the four source
trees (300 files, clean; `tsc --noEmit` fails on missing `apps/web` packages in the container, not
on this change), `make layer_check` (100 rules), `make exposure_check` (7 rules), `tools/progress.py
--check` (44 plans), the new `test_sociomap_connectedness_100.py` (13 passed), every `sociomap` /
register test (544 passed, 5 skipped: archive-backed parity), and on Python 3.12 the core suite
(5,090 passed, 205 skipped), API + worker (400 passed, 8 skipped), executors (308 passed, 2
skipped); 0 failed. `make web_design` and `make test-web` not run: no web file changed.
