---
status: in-progress
chunks:
  - "[x] 0. This plan; baseline on develop 64cc1380; the methodology's own self-test (60/60) as the reference"
  - "[x] 1. numpy, scipy and numba as aia-core dependencies; the domain numpy rule lifted"
  - "[x] 2. Input ratings and object relations: per-person centring, the unrelated baseline, pair floors, Benjamini–Hochberg with the noise rule, the sparse-design note; preset aia-sociomap-5 created"
  - "[x] 3. Object positions: soft-rank Spearman with Coulomb repulsion (BB1), Interval MDS for large maps by a fixed object-count rule"
  - "[x] 4. Height and terrain: mean rating, relative heights with a floor, ruler and frame scaling, the envelope terrain, node size and label note for large maps"
  - "[x] 5. Map credibility: split-half agreement, the no-reliable-structure statement, one uncertainty radius per map"
  - "[x] 6. Respondent map: vector-model placement, the chance test for placed / faded, the respondent terrain, the indicative note below six objects"
  - "[x] 7. Taste segments: the mixture on slopes, the shuffle guard, the step-down, profiles, colour only for clearly placed respondents, borderline segments"
  - "[x] 8. aia-sociomap-5 the only method of new runs: the code's default pins -5 by its own name, -1 to -4 leave every product path (run pins, Metodika presets and in-force, the web, the report), Metodika's in force is -5 (D-13); as built under the owner's decisions of 2026-10-21 (§ Chunk 8 as built)"
  - "[ ] 9. The report draws -5: object-map figure from heights.relative and the terrain method, objects_not_placed listed, credibility in place of Stress-1, the respondent-map and taste-segment figures (D-13)"
  - "[x] 10. Methodology is edited only by the methodologist: a Metodik member mark an OWNER grants (held by A. Bahbouh) gates storing and activating methodology versions (D-14, Q4) (#823, merged 2026-10-23)"
  - "[ ] 11. Metodika shows -5 in full: the comparison (MapSummary) carries credibility, the respondent map and taste segments, and the -5 steps are what in force describes (Q8)"
---
# aia-sociomap-5 — the signed-off AIA Sociomapa methodology as a method

**Owner:** A. Bahbouh (methodology) · **Started:** 2026-10-19
**Source of truth:** the AIA methodology folder (signed-off code, formulas and its own
self-test), kept outside this repository by the methodology owner.

## Problem

The client-facing Sociomap (`aia-sociomap-3`, `engine_v2.compute_object_map`) computes
the map the pre-review way:

- per-person min–max on 0–1 ratings, weighted Pearson tested against 0, unknown below
  30 raters (`domain/sociomap/pairs.py`, `engine_v2.py` @ 64cc1380);
- SMACOF on √(2(1−r)) as the only layout (`domain/sociomap/layout.py:806-921`);
- Stress-1 bands as the only credibility measure;
- no respondent placement (`specification.py:653-657` refuses `respondent_placement`)
  and no respondent segmentation.

The methodology owner has signed off a different method for every stage: inputs,
relations, positions, height, terrain, credibility, the respondent map and taste
segments. Nastavení → Metodika cannot express it: an edit may change values and the
editable formulas, never add an algorithm or a step.

## Approach

A new preset `aia-sociomap-5` inside specification contract 3: `aia-sociomap-4` copied
with new option values and new optional fields (the pattern of
`specification.py:963-989`), computed by `engine_v2` and stored in the contract-3
artifact. New fields are left out of the stored form when unset, so the `-2`/`-3`/`-4`
fingerprints, `-3`'s register approval (`sociomap_register.py:52-69`) and every run pinned
to them stay byte-identical. Making `-5` the default or client-facing is a separate step
with its own register approval.

**Editable afterwards.** Every parameter of the new method is a specification field shown
by exactly one Metodika step, so an OWNER/ADMIN edits `-5` like `-4`.

**Ported as written.** The computation is the methodology folder's numpy/scipy/numba
code, so it is checked number for number against the owner's code: BB1 is chaotic (a
1e-15 change in the start gives another map) and its starts come from numpy's generator.

Each chunk is one commit with:

1. the ported functions, typed for `mypy --strict`;
2. a parity test against a small golden fixture produced by the owner's code on seeded
   simulated data (1e-9 for deterministic stages; identical statuses and decisions for
   outputs that depend on BB1, under the pinned library versions);
3. its Metodika steps (re-pinned, register rule, regenerated web fixture), because the
   pin tests fail otherwise;
4. an independent review: a second agent compares the port with the original line by
   line before the commit is proposed.

**Minimal diff.** No new engine, contract, artifact model or helper module beyond what the
computation needs; no generator scripts committed (fixtures are produced outside the
repository from the methodology folder). Names say what a thing is, never a decision or
audit code.

### Decisions taken (methodology owner, 2026-10-19)

| Decision | Chosen | Rejected, and why |
|---|---|---|
| Where numerical code lives | `domain/sociomap/`, numpy/scipy/numba as `aia-core` dependencies (agreed with the codebase owner) | Pure-Python port: BB1 ~100× slower than the compiled 9 s at 40 objects, segment mixture infeasible on large samples, parity only statistical |
| When Interval MDS replaces BB1 | A fixed object count: the methodology's time budget 1.07e-3·M^2.46/10 ≤ 30 s with the core count frozen at 10, i.e. BB1 for M ≤ 163 objects, Interval MDS above; the method used is recorded on every map | The budget as written reads the machine's core count, so for 65 ≤ M ≤ 164 two machines pick different methods; the repo forbids probing (`layout.py:1-14`) |
| Replace `-3` or add `-5` | Add `-5` | Replacing changes results already approved by fingerprint and pinned by past runs |
| An object nobody in the set rated | Not placed: left out of the set before anything is computed, as a context object is, and listed in `objects_not_placed`; the map is the rated objects' own | Laying it out with the rest and hiding it afterwards (the AIA panel today): with no data it gets the unrelated charge to every object (soft-rank Coulomb term, Interval MDS floor) and pushes the others (up to 1.70 ruler units on an 8-object study); standing it at the set's lowest height with a grey node (the methodology's renderer before 2026-10-19). The panel takes the rule at its next sync |
| A set whose objects declare different scales | Not mappable (`MIXED_SCALES`): the methodology and the AIA panel read one scale per set | Rescaling every item to 0-1 first: the relations read raw ratings, so relations and respondent map would read the data differently (on a demo 25 of 200 respondent statuses changed) |
| What the terrain's frame is fitted over | The rated objects with at least one known (RELIABLE or WEAK) pair, as the AIA panel fits its map; nothing fitted when there is none. The panel also fits over the context objects it shows; `-5` maps the PRIMARY objects only, so the frames agree when no context object is shown | Every placed object (the methodology's renderer before 2026-10-19): an object resting on a handful of raters set the zoom |
| Which failures of the split-half check and the uncertainty radius fall back | Only the two errors Interval MDS raises on too little data, `ZeroDivisionError` (no layout pair in a half) and `numpy.linalg.LinAlgError` (the classical start of a near-empty design); any other error propagates | Catching every exception, as the AIA panel does: a defect would silently become "weakly determined" or "no radius" |

### Library versions

numpy 2.5.x, scipy 1.18.x, numba 0.68.x: the versions the methodology's evidence was
produced with (BB1 and borderline segment decisions change between numba 0.64/numpy 2.3
and 0.68/2.5).

### Not in this plan

- Colours, camera and drawing: the web client.
- The false-close-pair test: a benchmark honesty test, not part of a map.
- Groups without direction on the respondent map: deferred in the methodology.
- Making `-5` the default.
- Context (SECONDARY) objects: `-5` maps a set's PRIMARY objects only, as the AIA panel
  shows a declared set; context objects are left off its map. How they should join it (the
  panel places them afterwards with the PRIMARY map fixed, NPC's F17 rule) is an open
  question for the methodology owner (2026-10-19).
- Survey weights for the relations: the methodology computes them unweighted, so `-5`
  does too (`-3` weights them); its object height is survey-weighted, as the AIA panel
  draws it (methodology owner, 2026-10-19). Weighted relations: open question for the
  methodology owner, to revisit.
- A platform-independent BB1 map. With the same numpy/scipy/numba versions, macOS and
  Linux give the same inputs and Interval MDS maps but can give different BB1 maps from
  12 objects on (last-bit differences in the compiled kernel, amplified by the chaotic
  criterion; both maps fit equally well). A given image is deterministic. The parity tests
  are exact where the method is deterministic and statistical for full BB1 runs; open
  question for the methodology owner.

## Doc follow-up

- `ARCHITECTURE.md:50` "Stdlib + Pydantic only — numerical code included" → the domain may
  use numpy, scipy and numba (agreed 2026-10-19).
- CLAUDE.md §2: the `aia-sociomap-5` preset, its modules and the new Metodika section.
- Where the Python image's environment is described: `NUMBA_CACHE_DIR=/tmp/numba` (the
  develop containers are read-only except `/tmp`; numba raises at import without it).
- Where the object-map artifact is described: under `aia-sociomap-5` the layout records
  `method` (`soft_rank_spearman_coulomb` or `interval_mds`) and no `stress_1`,
  `raw_stress` or `quality`.
- Where the object-map artifact is described: under `aia-sociomap-5` the height metric is
  `mean_rating_0_1` as before (survey-weighted, on the declared 0-1 scale; an object
  nobody rated is not mapped at all, see below); `heights.relative` holds each
  PRIMARY object's hill height (min-max onto [0.15, 1], null for
  SECONDARY); `objects_not_placed` lists the set's objects nobody rated, which are left out of
  `object_ids` and of every computation (left out of the stored form when empty); the terrain method is
  `framed_relative_envelope`, its `parameters` record the `centre` and `half_extent` fitted over
  the rated objects with a known pair (an object without one can stand outside the grid) and no
  `kernel_cutoff`, and every cell has a height. The
  spec's `terrain` declares `frame_fill` (0.70) and `relative_height_floor` (0.15) and no
  `half_extent` or `kernel_cutoff`. Earlier presets store none of the new keys.
- CLAUDE.md §2, `terrain.py`: `fit_frame` (the framed grid) and `EnvelopeParameters.axes()`
  (the grid's x and y coordinates about its centre; `axis()` is the offsets from the centre).
- Web follow-up, standing rule (methodology owner, 2026-10-19): every visual decision about the
  Sociomap visualisation panel, wherever it appears (research view, Metodika comparison, the
  report's map figure, the respondent map), follows the current AIA panel's drawing
  (`ui_app.html`: terrain, colour ramp, frame, x26, nodes, lines, dots, notes, legends), not the
  repository's existing map drawing; the rest of the website (layout, navigation, components
  around the panel) stays as it is.
- Web follow-up (drawing rules the methodology's renderer has, not ported here, owner
  decision 2026-10-19): the 26x height exaggeration of the terrain; node size
  x min(1, sqrt(30 / M)); the "k of M objects labelled" note for large maps; node colour from
  the relative height; the objects in `objects_not_placed` (nobody rated them) listed under the
  map as the panel does ("Neumístěno …"); the methodology's colours and camera. Until then the
  web and the report leave those objects out without saying so, and draw a `-5` map's framed
  terrain in their absolute 0-1 terraces, though its cells are relative heights, and
  the report's top view keeps its axes at the fixed ruler (the framed grid can reach past
  it). `OBJECT_MAP_METHODS` in `object-map-view.ts` does not name `aia-sociomap-5` (it is
  read as an unnamed method).

- Where the object-map artifact is described: under `aia-sociomap-5` a MAPPED map records
  `credibility` = {`rule` (`split_half` or `no_reliable_pair`), `split_half` (null without a
  score), `threshold`, `weakly_determined`, `reliable_pairs`, `uncertainty_radius` (in units
  of the map's RMS inter-object distance; null when a bootstrap map cannot be computed)}; a
  NOT_MAPPABLE map and the earlier presets record none. The spec's top-level `credibility`
  section (`split_half_threshold` 0.59, `split_half_splits` 2, `split_half_seed` 0,
  `bootstrap_resamples` 20, `bootstrap_seed` 0, `safety_factor` 1.2) is declared under `-5`
  only and left out of the earlier presets' stored form.
- CLAUDE.md §2: `domain/sociomap/signed_off_credibility.py` (`split_half_agreement`,
  `map_uncertainty`), wired in `engine_v2._credibility`; Metodika steps `split_half_check`,
  `uncertainty_radius`, `map_credibility` (group "Věrohodnost mapy"); register rule
  `AIA-SIGNED-OFF-CREDIBILITY`.
- Web follow-up (map credibility, not drawn yet): the weakly-determined banner over a `-5` map
  with `credibility.weakly_determined` (the panel's texts: "Dvě poloviny vzorku se shodnou jen
  v s % srovnání „co je blíž“ (50 % = náhoda). Pozice na mapě nečtěte jako skupiny ani
  vzdálenosti." and, without a score, "Žádný vztah mezi objekty se neliší od náhody. …"); the
  split-half share in the HUD where Stress-1 stood; one uncertainty circle per object of
  radius `uncertainty_radius` × the drawn map's RMS inter-object distance (ruler units), none
  when null; the methodology comparison (Nastavení → Metodika, `sociomap_check.MapSummary`)
  does not carry the credibility yet, so an edit of a credibility value shows no change there
  until it reports the share, the flag and the radius. Until then the web shows a weakly determined `-5` map like any
  other; the report
  prints the warning and, for internal readers, the share and the radius.

- Where the object-map artifact is described: under `aia-sociomap-5` a MAPPED map records
  `respondents` = {`status` "computed", one entry per respondent in `respondent_ids` order in
  `x`, `y` (ruler units), `placement` (`PLACED`, `FADED` or `NOT_PLACED`), `misfit` (1 − R²)
  and `p_value` (the chance test), each null when NOT_PLACED; `counts` of each placement;
  `informative` and `min_objects`; `density` = {`parameters` (`grid_resolution`,
  `half_extent`, `centre` of the object terrain's grid, and the density's own `sigma`),
  `height` [gy][gx], divided by its maximum, 0 everywhere when nobody is PLACED}}. A respondent
  can stand outside the grid. A NOT_MAPPABLE `-5` map records `respondents` not computed with
  the reason that there is no map; the earlier presets record the chunk-3 statement as before.
  The spec's top-level `respondent_map` section (`chance_level` 0.10, `min_ratings` 3,
  `informative_min_objects` 6, `density_sigma` 0.35) is declared under `-5` only, requires the
  framed terrain, and is left out of the earlier presets' stored form; the legacy
  `respondent_placement` stays null.
- CLAUDE.md §2: `domain/sociomap/signed_off_respondents.py` (`place_respondents`,
  `respondent_density`), wired in `engine_v2._respondents`; Metodika steps
  `vector_model_placement`, `respondent_density`, `respondent_map` (the four values; group
  "Respondenti a podpora mapy", beside the audit's `f10_placement`, which stays the proposal
  for the earlier presets); register rule `AIA-SIGNED-OFF-RESPONDENTS`.
- Web follow-up (respondent map, not drawn yet): a respondent map view for `-5` from
  `respondents` on the object map's frame: PLACED respondents as dots, FADED ones fainter
  (alpha 0.3), NOT_PLACED ones not drawn; the density as terrain at the methodology's 26x height
  exaggeration; below `min_objects` the note „Sada má n objektů: mapa respondentů je jen
  orientační (spolehlivá od 6)“ and, below 3 objects, „Sada má n objektů: respondenty nelze
  umístit (potřeba aspoň 3 hodnocení)“ (the panel's texts, with its objekty / objektů
  agreement; the minimum, 3 in the panel's text, is printed from `spec.respondent_map.min_ratings`
  so the note stays true when the value is edited in Metodika, methodology owner 2026-10-19);
  the panel's option to raise the terrain from a filtered group of respondents
  only (computed in the client from the stored positions, the same kernel and grid). The
  methodology comparison (`sociomap_check.MapSummary`) does not carry the respondent map yet,
  so an edit of a `respondent_map` value shows no change there. Until then the web and the
  report show no respondents for a `-5` map.

- Where the object-map artifact is described: under `aia-sociomap-5` a MAPPED map's respondent
  map records `segments` = {`decision` (`SEGMENTS`, `NONE` or `BORDERLINE`), `reason` (under
  `NONE`: `TOO_FEW_RESPONDENTS`, `NO_CLEAR_SEGMENTS`, `NOT_ABOVE_SHUFFLED` or `NOT_STABLE`), `k`
  (0 unless `SEGMENTS`), `k_fit`, `gain`, `null_gain_max`, `margins` (each map's, two decimals),
  `mean_margin`, `votes`, `maps` (the last four null below `consensus_min_objects`), `shares`,
  `separation`, `distinct`, `profiles` (per segment: `likes`, `dislikes` as object ids,
  `difference`, `standard_error`, `p_value`, `distinctive` per object), per respondent in
  `respondent_ids` order `label` (-1 without a slope), `membership` (five decimals) and
  `coloured` (all three null unless `SEGMENTS`), `hint` (`BORDERLINE` only: `k`, `shares`,
  `profiles`)}. The spec's top-level `segments` section (17 values) is declared under `-5` only
  and left out of the earlier presets' stored form.
- CLAUDE.md §2: `domain/sociomap/signed_off_segments.py` (`respondent_slopes`, `map_decision`,
  `taste_segments`, `consensus_state`, `segment_profiles`, `jittered_ratings`; the compiled EM
  loop; the shuffles fitted four at a time in threads), wired in `engine_v2._segments`; Metodika
  steps `segment_mixture`, `shuffle_guard`, `segment_step_down`, `segment_consensus`,
  `segment_membership`, `segment_profiles`, `taste_segments` (the 17 values) in group S7; register
  rule `AIA-SIGNED-OFF-SEGMENTS`.
- Web follow-up (taste segments, not drawn yet): the respondent dots coloured by `label` where
  `coloured`, grey otherwise; the segment legend with shares and `likes` / `dislikes`, "overlapping"
  when not `distinct`; the decision's note from `decision` and `reason` (the panel's texts); under
  `BORDERLINE` nobody coloured and the likely split named from `hint`. The methodology comparison
  (`sociomap_check.MapSummary`) does not carry the segments yet, so an edit of a `segments` value
  shows no change there. Until then the web and the report show no segments for a `-5` map.

## Findings

None yet.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

Chunk 8 supersedes this plan's § Not in this plan where it puts making `-5` the default out of scope.

**New chunks.**

- **8 (W1).** The product owner's D-13: "make aia 5 the only version … get rid of any functionality
  of the old ones. maps are drawn according to the current 5." A new run pins `aia-sociomap-5` by its
  own name (not `+e<n>`), at its spec fingerprint, alone: `default_methods()` stops returning `-1` and
  `-3` (`domain/research_sociomap.py:323-330 @ 854c209`). Metodika's `in_force` becomes `-5`, its
  presets offer `-5` only, and an edit starts from the version in force (today `presets[0]`, `-4`:
  `MethodologyVersions.tsx:79-86 @ 854c209`; its test `MethodologyVersions.test.tsx:258` changes with
  it). The worker image's `NUMBA_CACHE_DIR` and library versions are recorded with each map (packet
  E-6). Tests: a new run pins exactly `aia-sociomap-5` at `8b0b4864…`; no product path offers `-1` to
  `-4`; `require_client_facing` passes for a `-5` map once the register entry exists and refuses
  `-5+e1`. **Settled by the owner (Q1-Q3).** It merges **when built**: every `-5` map stays
  `INTERNAL_ONLY`, and no map reaches a client, until the methodology owner's register entry exists
  (packet MQ-01, asked first). A stored `-1`/`-3` run keeps its data and numbers; its map panel says
  "Mapa ze starší metody; spusťte běh znovu" and draws nothing. `-1` to `-4` leave every product
  path, while the old engine and its golden fixtures F1-F9 stay in the code as tested reference
  (their deletion is a later decision, once `-5` has golden fixtures of its own).
- **9 (W2, before E15).** The report's map chapter and figures for `-5`: z from `heights.relative`,
  the caption from the terrain method, `objects_not_placed` listed (today dropped:
  `object_map_figure.py:39, 64-104 @ 854c209`), credibility in place of Stress-1
  (`report_maps.py:215-220`), and the respondent-map and taste-segment figures
  (`segment-maps-and-drilldown#9`). How the report re-derives a `-5` map follows MQ-04 (E-7).
- **10 (W1).** D-14 and Q4: a "Metodik" mark on a member, granted and withdrawn by an OWNER
  (audited), held today by A. Bahbouh, gates **both** storing and activating a methodology version
  (today OWNER or ADMIN, ADR 0023). Any member still reads Metodika and runs check and compare.
  Tests: an ADMIN without the mark is refused by name on store and on activate; the mark's grant and
  withdrawal are audited. ADR 0023's role table changes in its PR's Doc follow-up.
- **11 (W2, after 8).** Q8, against the planning session's recommendation: Metodika's comparison
  shows **all** of `-5`'s outputs. `MapSummary` (`domain/methodology/sociomap_check.py:136 @
  854c209`) carries credibility (split-half share, uncertainty radius), the respondent map
  (placed / faded counts) and taste segments, so an edit of any `-5` parameter shows its effect;
  "v platnosti" describes the `-5` steps ("Věrohodnost mapy", "Respondenti a podpora mapy", S7) and
  the `-3`-only steps are not shown as in force. The comparison runs on the API host: its latency on
  the fixed panels is measured in the chunk's PR (BB1 at about 9 s compiled is the methodology
  owner's figure).

**Measurement before MQ-06** (packet E-9): a `-5` map with respondents and segments on the develop
worker image at 1,500, 5,000 and 20,000 respondents, recorded in this plan before the methodology
owner answers MQ-06.

### After the old-method answer (the owner's answers on the PM status page, 2026-10-20 20:50-21:04 UTC, relayed by the coordinator (page ids Q13 to Q18; `.planning/evidence/scope-freeze/answers-2026-10-20.md`, fourth table))

- **8 (page Q17: (a)).** A retry of a run that pinned `-1` or `-3` is **refused**, worded with a link
  that starts a new run on `-5` from the same Design Revision. Approved reports of such runs stay
  downloadable (`report-delivery#RD3`). Test: a retry of a `-3` run returns the refusal and the new
  run link, and starts nothing.

### Implementation lane: the methodology owner's #517 (2026-10-20)

The product owner, 21:33 UTC (relayed by the coordinator): the `-5` drawing is **A. Bahbouh's own
lane**, PR #517 (`feature/aia-sociomap-5-web`) and its plan `.planning/plans/sociomap-5-web.md` on that
branch.
- Built there (chunks 1-5 ticked on the branch at the time of writing): the panel ported pixel for
  pixel, credibility (the weakly-determined banner, the uncertainty circle, objects not placed), the
  respondent map and taste segments.
- Still to come there: detail on click (6), and the Word report's `-5` figure and the web map's PNG
  snapshot (7).

**Chunk 9's figure is built by #517's chunk 7.** Chunk 9 keeps the report chapter's text (credibility
in place of Stress-1, unplaced objects listed) and the respondent-map and taste-segment figures'
place in the chapter, drawn from #517's renderer.

### Chunk 8 as built: the owner's decisions of 2026-10-21 (relayed by the coordinator)

- **`-5` is registered client-facing.** `SOCIOMAP_REGISTER` holds `aia-sociomap-5` at its spec
  fingerprint (`959a5877…`, with the relation detail's `clear_effect` in the spec; `8b0b4864…`
  before it), decided by the methodology owner on 2026-10-21, beside the `-3` entry
  that old runs still read. A version that changes anything (`-5+e<n>`) stays internal.
- **Metodika keeps `-2`, `-3` and `-4` offered**, with `-5` listed first and in force; an edit starts
  from the version in force, else from the preset in force.
- **An unchanged preset in force pins its own name.** A stored version equal to its base preset (no
  changed value, no replaced formula) is pinned as the preset itself (`sociomap_methods_for`), so it
  keeps the register's approval; any change pins `<preset>+e<n>`.
- **Retries.** A run whose object map is exactly `-3`, or that pinned the reference map alone, is
  refused with the start of a new `-5` run over the same Design Revision, with the refused run's
  respondents, population and research-question decision. A run of an edited version (which also
  pinned `-1` beside it) is retried with its own version, without `-1`.
- **Analysis retry of an old run is allowed when its map is stored**: its Sociomap step reuses the
  map stored under the same inputs (the same input fingerprint) and computes no old method; with no
  stored map it is refused like a retry.
- **Provenance.** Each `-5` map records the worker's numpy, scipy, numba and llvmlite versions; the
  numba cache path, a deployment detail, is not recorded.
- **Client reports show the `-5` respondent map** beside its two object-map views.
- **"Klienti"** is the team's own client handling.

### The terrain under inverse-distance weighting (the methodology owner, 2026-10-26)

- **The `-5` object terrain is the objects' relative heights weighted by inverse distance, as the
  Sociomapy app interpolates them** (`framed_relative_idw`): z(q) = Σ_j w_j t_j / Σ_j w_j,
  w_j = d_j^(−p), p = `terrain.idw_power` = 3, on the same framed grid, Relativní and Absolutní
  alike. The terrain at an object is its own height, beside a taller one too; every other point is
  a weighted mean of the objects, far from them as well.
- **Selectable:** the same under the hills' falloff (`framed_relative_idw_falloff`, × max_j
  exp(−d_j² / 2σ²), σ = 0.25: far from every object, ground; a replaced kernel shapes the falloff)
  and the envelope (`framed_relative_envelope`, no power). The hill width and the kernel do not
  enter the plain weighted mean.
- **Both inverse-distance terrains are stored** (Nigel, 2026-10-27): a run under either stores the
  other beside it, and the map switches between them, opened on plain IDW. Plain IDW fills empty
  space with the nearest objects' height (the 8-object `complete` study's bottom-left corner reads
  about 0.9); the falloff keeps each object at its own height and lets empty space fall to ground.
- **`terrain.idw_power` lies in (0, 10]**: above that, 1 / d^p underflows or overflows on a map's
  grid (200 fails with a division by zero, 1e6 with an overflow), in the spec and Metodika alike.
- **Report figures** print the version's own terrain (under `-5`, plain IDW) and say which terrain
  they show. Letting the study's lead researcher choose the terrain of a report's map figures
  (internal and client) is a later chunk.
- **Why** (evidence in the methodology folder's project, `NPC_Panel/analysis/idw_terrain/`, five
  maps): the envelope lifted 0–4 objects per real map by up to 0.33 of the scale next to a taller
  neighbour; none is lifted under inverse-distance weighting. Chosen knowingly over the falloff
  variant (first signed off the same day): plain weighting brings back plateaus (56–80 % of cells
  within 0.10 of the nearest object; the envelope 18–28 %) and raises ground far from every object
  to 0.51–0.72, on 0.1–3.7 % of the cells.
- **The register approves the new `-5` fingerprint** (`b2992c12…`) client-facing beside the
  `959a5877…` entry, which runs stored before the change keep. `-2`, `-3` and `-4` are unchanged.
- **Metodika** shows the weighted mean and its falloff variant as steps after the envelope's, with
  `terrain.idw_power` (in (0, 10]) among the terrain's parameters; the terrain parity fixture
  (`signed_off_terrain.json`) was produced again by the methodology's own code. The web's `-5`
  fixture stays a stored map of the envelope: a run stored before the change.

## Chunk 10 ticked (2026-10-26, docs PR)

Shipped by #823 (merged into develop 2026-10-23, `58a272b4`), the Settings backends' SB1: the Metodik mark (`PUT /members/{user_id}/methodologist`, `apps/api/src/aia_api/routers/scope.py:806-821 @ 40b16d58`), and `MethodologyRepository` requiring it before any methodology change (`packages/aia_core/src/aia_core/infrastructure/methodology_repository.py:233-237 @ 40b16d58`, `require_methodologist`). The Settings gap map recorded the drift (SOSM#10 open although SB1 shipped).
