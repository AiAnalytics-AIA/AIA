---
status: done
chunks:
  - "[x] 1. Vendor F1–F9"
  - "[x] 2. Relation transforms"
  - "[x] 3. Normaliser and object metrics"
  - "[x] 4. Terrain"
  - "[x] 5. Layout registry, AIA unfolding"
  - "[x] 6. Spec v2, artifact v2, compute_sociomap, view overrides"
  - "[x] 7. Documents"
---
# Sociomap deterministic engine — versioned spec, artifact, Python numerical path

**Status:** done (all chunks landed; gaps carried as OI-13 – OI-16) · **Owner:** sociomapa-deterministic (+ parity-quality for
`REF-GAP-SOCIO-R-SMACOF`) · **Started:** 2026-09-22

## Problem

The Sociomapping research mathematics lives in two places in the reference, and
neither can be tested here:

- the **backend** (`sociomap.py`) owns scale coercion, the mutual-relation
  projection and the unfolding layout, but picks its layout algorithm by probing
  the host for `Rscript` — the same study yields different coordinates on
  different machines;
- the **browser** (`ui_app.html`, the `*66` family) owns the terrain field, the
  four normalisation modes and the object metrics, including the T-score. These
  have no backend counterpart and so no possible Python test.

`aia_core.domain.sociomap` @ 17c0a6b holds contracts only
(`ENGINE_IMPLEMENTATION_VERSION = "0.0.0-contracts"`, `IMPLEMENTED` empty), and
those contracts model one square entity set. The reference pipeline is
rectangular: respondents × objects in, respondent **and** object coordinates out.

Authority: `AiAnalytics-AIA/AIA-reference` @ `678e298ad9ca0263da53cc8920d153fdfb956c93`
— `sociomapping-reference-contract.md`, `sociomapping-deep-dive.md`,
`golden-fixtures/F1`–`F9`, `ui-capability-ledger.md`.

## What the fixtures can and cannot pin (measured before designing)

Every fixture was reproduced from the contract's formulas *before* any design
was chosen. Results, reproduced in this session with a throwaway script:

| Fixture | Reproducible from the contract alone? |
| --- | --- |
| F1 coercion | **yes**, all five cases. One ordering ambiguity: the contract does not say whether sentinels are substituted before or after the scale branch is decided. The fixture only exercises inputs where both orders agree |
| F2 mutual | **yes** |
| F3 ipsatize | **yes** |
| F4 Python unfolding | **no.** The algorithm's source is inside the withheld archive. ~200 candidate stress definitions evaluated on F4's own coordinates; none reproduces `stress_1 = 0.391394498`. Coordinates cannot be matched by guessing an optimiser |
| F5 normaliser | **yes**, all seven cases, incl. percentile = `bisect_right / n` |
| F6 object metrics | **yes** |
| F7 respondent terrain | **yes** — every sample, `sum_ht`, finite count and normaliser bounds to 1e-9 |
| F8 object terrain | **partly.** The kernel-weighted-mean rule, constants, bounds and normaliser semantics are pinned, but the object *positions* come from `baseObjectLayout66(matrix)`, a 1,235-char frontend function whose source is withheld. A 2,000-start inverse fit found no placement consistent with the samples |
| F9 drag | **yes** — semantics, not arithmetic |

## Approach

1. **Pure Python, in the domain.** `ARCHITECTURE.md §2` allows stdlib + Pydantic
   in `domain/`. numpy was considered and rejected: it would make the domain
   un-importable without it, and a BLAS-backed SVD is not bit-stable across
   hosts and thread counts — the very host-dependence this work removes. Pure
   Python float arithmetic in a fixed order is. Cost: speed at population scale,
   measured and recorded (chunk 6).
2. **Port what the fixtures pin, exactly.** Coercion, mutual projection,
   ipsatization, normaliser, object metrics, both terrain modes — each with its
   fixture as the test.
3. **Declare, never detect, the layout algorithm.** The legacy
   `python_weighted_unfolding` and `r_smacof_unfolding` are *known* identifiers
   that fail closed with the reason they are unavailable. A new, fully specified
   AIA algorithm — row-conditional metric unfolding by alternating block
   majorisation, deterministic initialisation, no RNG — is implemented under its
   own identifier, with its own golden fixture on F4's input and its measured
   distance from F4 stated. It is **not** claimed to be parity with anything.
4. **Spec v2 / artifact v2.** A structured spec (preprocessing, layout, map
   frame, metrics, terrain) with no defaults, and an artifact that carries
   respondent and object coordinates, stress, provenance, object metrics and
   both terrain fields.
5. **View and scenario stay layers.** Drag overrides and what-if edits produce
   view/scenario results bound to the artifact fingerprint; the artifact is
   never written. Terrain over dragged positions is a *view* computation, as in
   the reference (manual state is in its cache key).

## Trade-off accepted

The production layout is a declared AIA algorithm rather than the legacy one, so
maps are reproducible and auditable today but are **not** numerically comparable
to legacy maps until the legacy source (or an R fixture) is available.

## Chunks

- [x] 1. Vendor F1–F9 under `packages/aia_core/tests/fixtures/sociomap/` with a
      hash index back to the reference repository; test that the vendored bytes
      match the index — lands: fixtures + test
- [x] 2. Relation transforms: `coerce_relation_scale_1_10` (F1), `mutual_relation_for_position`
      (F2), `ipsatize` (F3) — lands: `domain/sociomap/relations.py` + tests
- [x] 3. Normaliser and object metrics, unknown metric ids rejected — F5, F6 —
      lands: `domain/sociomap/metrics.py` + tests
- [x] 4. Terrain: respondent density and object weighted mean, shared kernel,
      parameters explicit — F7 exact, F8 semantics — lands: `domain/sociomap/terrain.py` + tests
- [x] 5. Layout: algorithm registry, fail-closed legacy ids, AIA unfolding,
      gauge fixing, map frame, own golden fixture, measured distance from F4 —
      lands: `domain/sociomap/layout.py` + tests
- [x] 6. Spec v2, artifact v2, `compute_sociomap`, view overrides (F9) and
      scenario layer on v2; performance measured — lands: `specification.py`,
      `models.py`, `engine.py`, `view.py` + tests
- [x] 7. Documents: engine doc, `PROGRESS.md`, `open-items.md`, `CLAUDE.md` map,
      `AGENTS.md` gotchas, `reference-source.md` gap status

## What changed from the plan while executing it

- **Chunk 5, the layout model.** The first version normalised each respondent's
  row to a fixed scale before fitting. The recovery test caught it: on data
  generated from a known geometry it could not get below stress-1 ≈ 0.07,
  because a fixed row normalisation forces every respondent to the same mean
  distance from the objects. Replaced by the standard row-conditional ratio model
  — one free scale per row, one global normalisation — which recovers planted
  geometry to stress-1 < 1e-4 (`test_recovers_the_geometry_that_generated_the_data`).
- **Chunk 5, the dissimilarity target.** `row_max − rating` was dropped for
  `scale_top − rating`: under a ratio model the former puts every respondent
  exactly on their favourite object. Consequence: ipsatization, which is ported
  (F3), cannot feed the implemented target and is refused when requested.
- **Chunk 6, scenarios.** The reference's what-if edits the relation matrix,
  and in the reference that also moves objects (through `baseObjectLayout66`,
  OI-14). Here positions come from the ratings, so a scenario changes heights and
  metrics only — recorded rather than approximated.

## Measured

- Suite: 733 passed / 117 skipped on SQLite, against 546 / 117 on the parent.
- `compute_sociomap`: 0.11 s at 40 × 8, 0.41 s at 200 × 12, 3.3 s at 1,000 × 20.
- On F4's ratings, AIA vs legacy layout: Procrustes RMSD 1.91 against a radius of 2.01.

## Review outcome

Not yet reviewed by a human. Items the reviewer is asked to rule on are D6 /
OI-16 (the four AIA declarations). Not run: the PostgreSQL suite and the
legacy-source parity tier — neither the database nor `AIA_LEGACY_REFERENCE` was
available in the session, and this change touches neither the schema nor any
module the legacy-source tier covers.
