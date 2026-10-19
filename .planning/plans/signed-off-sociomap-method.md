---
status: in-progress
chunks:
  - "[x] 0. This plan; baseline on develop 64cc1380; the methodology's own self-test (60/60) as the reference"
  - "[x] 1. numpy, scipy and numba as aia-core dependencies; the domain numpy rule lifted"
  - "[ ] 2. Input ratings and object relations: per-person centring, the unrelated baseline, pair floors, Benjamini–Hochberg with the noise rule, the sparse-design note; preset aia-sociomap-5 created"
  - "[ ] 3. Object positions: soft-rank Spearman with Coulomb repulsion (BB1), Interval MDS for large maps by a fixed object-count rule"
  - "[ ] 4. Height and terrain: mean rating, relative heights with a floor, ruler and frame scaling, the envelope terrain, node size and label note for large maps"
  - "[ ] 5. Map credibility: split-half agreement, the no-reliable-structure statement, one uncertainty radius per map"
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

### Library versions

numpy 2.5.x, scipy 1.18.x, numba 0.68.x: the versions the methodology's evidence was
produced with (BB1 and borderline segment decisions change between numba 0.64/numpy 2.3
and 0.68/2.5).

### Not in this plan

- Colours, camera and drawing: the web client.
- The false-close-pair test: a benchmark honesty test, not part of a map.
- Groups without direction on the respondent map: deferred in the methodology.
- Making `-5` the default.

## Doc follow-up

- `ARCHITECTURE.md:50` "Stdlib + Pydantic only — numerical code included" → the domain may
  use numpy, scipy and numba (agreed 2026-10-19).
- CLAUDE.md §2: the `aia-sociomap-5` preset, its modules and the new Metodika section.

## Findings

None yet.
