---
status: in-progress
chunks:
  - "[x] 0. This plan; baseline on develop 64cc1380; the methodology's own self-test (60/60) as the reference"
  - "[x] 1. numpy, scipy and numba as aia-core dependencies; the domain numpy rule lifted"
  - "[x] 2. Input ratings and object relations: per-person centring, the unrelated baseline, pair floors, Benjamini–Hochberg with the noise rule, the sparse-design note; preset aia-sociomap-5 created"
  - "[x] 3. Object positions: soft-rank Spearman with Coulomb repulsion (BB1), Interval MDS for large maps by a fixed object-count rule"
  - "[x] 4. Height and terrain: mean rating, relative heights with a floor, ruler and frame scaling, the envelope terrain, node size and label note for large maps"
  - "[x] 5. Map credibility: split-half agreement, the no-reliable-structure statement, one uncertainty radius per map"
  - "[ ] 6. Respondent map: vector-model placement, the chance test for placed / faded, the respondent terrain, the indicative note below six objects"
  - "[ ] 7. Taste segments: the mixture on slopes, the shuffle guard, the step-down, profiles, colour only for clearly placed respondents, borderline segments"
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

## Findings

None yet.
