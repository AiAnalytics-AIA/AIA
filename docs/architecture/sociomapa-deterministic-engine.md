# Sociomapa deterministic engine — boundary, contracts and port plan

**Status:** contracts implemented; **no Sociomapping mathematics ported**.
**Blocker:** the legacy NPC Panel reference checkout (`sociomap.py` and
siblings) was not available in the environment where this work was done.
**Audit date:** 2026-09-22, against `origin/main`
`df294e27515d225b9d47c15b21e664bbd8051bd8`.

> parity suite not run because the reference checkout is unavailable

This document is the Sociomapa-specific companion to
[ADR 0007 (no LLM for deterministic computation)](adr/0007-deterministic-tools.md),
[domain-map.md](domain-map.md) and the Phase 9 entry in
[../migration/migration-plan.md](../migration/migration-plan.md). It does not
restate the broader architecture and does not decide anything that belongs to
it.

## 1. Why this exists

Phase 9 requires **numerical parity** with the legacy Sociomapa. The product
already states the rules a Sociomapa must obey (`docs/product/README.md`,
`domain-map.md`, the legacy `PRODUCT_POLICY.json` rule
`manual_drag: visual_override_only_never_mutates_raw_results`). What was
missing was a place where those rules are *types and tests* rather than prose,
and an honest account of what can and cannot be built before the reference
code is read.

The end state:

```
deterministic software   establishes numerical research truth
LLM agents               decide what to investigate, pick permitted tools,
                         interpret structured outputs, explain in prose
humans                   approve consequential methodology decisions and
                         sign off externally delivered conclusions
```

The LLM never invents or calculates the Sociomapping mathematics.

## 2. Boundary classification

Every Sociomapping behaviour falls into one of these groups. The engine package
(`packages/aia_core/src/aia_core/domain/sociomap/`) enforces the first two and
the last; it exposes nothing for the third and fourth to compute with.

| Group | Contents | Where it lives |
| --- | --- | --- |
| **A — deterministic research truth** | relation matrix derivation; matrix transforms; normalisation; weighting; missing-data handling; layout (unfolding) mathematics; coordinates; height and colour metric values; request/arrow decisions; segment statistics; comparison deltas; time-window calculations; quality/stress metrics; statistical tests and significance; validation gate outcomes | tested pure functions producing a `SociomapArtifact`. **None ported yet.** |
| **B — versioned methodology / policy** | relation definition; matrix type; transform; normalisation method; missing-data policy; weighting contract; layout algorithm, parameters and seed; eligible height/colour metrics; (later) arrow rules, comparison rules, segment rules, statistical rules, quality thresholds | `SociomapSpec`, fingerprinted, no hidden defaults, refused when not implemented |
| **C — LLM / semantic reasoning** | formulate a hypothesis; propose a segment; choose which approved tool to call and with which spec-permitted parameters; request a comparison; interpret and explain a structured result; propose follow-ups | future agent runtime; consumes artifacts, never produces numbers |
| **D — human / consequentially approved** | methodology exceptions; material changes to a `SociomapSpec` used for a client; acceptance of a non-standard interpretation; approval of externally delivered claims | existing approval/gate machinery (owned elsewhere); artifacts carry `is_approved` / `is_frozen` |
| **Presentation** | rendered map, surfaces/contours *as pixels*, palette, camera, drag positions, animation | `view.py` (drag overrides, what-if layers) and, later, `apps/web`; reads artifacts, never writes them |

Two things deliberately straddle the line and are resolved this way:

- **Map surface / contour values** are group A if the legacy code computes them
  as numbers (a height field), and presentation only in how they are shaded.
  Until the code is read, they are not in the artifact contract.
- **Layout quality scores** are group A; the *threshold* that makes one
  "acceptable" is group B.

## 3. What the production repository knows about the legacy Sociomapa

Everything below is verified from this repository; nothing is from memory.

| Source | Fact |
| --- | --- |
| `docs/migration/legacy-system-map.md` | `sociomap.py`, 565 LOC, "relation matrices, unfolding, layout" |
| `docs/migration/parity-matrix.md` | `sociomap.py`, `visualization_lab.py` → Phase 9, parity **numerical**, status ○ not started |
| `docs/migration/migration-plan.md` §Phase 9 | "Relation matrix derivation, unfolding and layout mathematics, the two map types, matrix/comparison/what-if modes, saved segments, AI segment intelligence, object manager, respondent and segment dialogue." `sociomap.py` mathematics "ports directly"; rendering is new; profile before choosing the renderer |
| `docs/architecture/domain-map.md` | owns relation matrices, unfolding/layout maths, map view state, saved segments, A/B area comparison, what-if layers, object manager. Legacy sources: `sociomap.py`, `visualization_lab.py`, `segment_orchestration.py`, `respondent_dialogue.py`. Position is relationship-derived and stable when the displayed metric changes; height and colour independently selectable |
| `docs/product/README.md` | "Respondent and object maps over a shared data contract; matrix, comparison and what-if modes." Dragging saves a view override; what-if is a layer over immutable originals |
| `docs/migration/reference-manifest.json` | SHA256 of every legacy file, including `sociomap.py`, `visualization_lab.py`, `segment_orchestration.py`, `respondent_dialogue.py`, `docs/product/03_SOCIOMAPA.md`, `docs/architecture_18/SOCIOMAP_REFERENCE_SHA256.txt`, legacy tests `test_socio_height_semantics_1880.py`, `test_socio_object_matrix_1881.py`, `test_socio_flow_1878_1879.py`, `test_interactive_socio_1877.py`, `test_sociomap_unified_1863.py`, `test_sociomap_workspace_1865.py`, `test_block_c_visualization_lab_1820.py`, and demo fixtures `OBJECTS_SOCIOMAP_DEMO.json` (×20) and `RESPONDENTS_SOCIOMAP.csv` |

The legacy test names are informative even without their contents: there is a
"height semantics" contract, an "object matrix" contract, a "socio flow", and an
"interactive" generation. The port must read all of them.

**Not available locally:** any of the above files' contents; the historical
methodology material (SOMECS, H-Model, fuzzy matrices, STORM/WIND maps, RTS,
design definitions, computed matrices, request arrows, object mapping, time
series). None of it is in this repository or on this machine.

## 4. The mathematical pipeline — what must be recovered from code

The chain the artifact contract is built to carry:

```
canonical inputs → SociomapSpec → relation matrix → transforms → layout
      → coordinates → height / colour → (presentation)
```

The following questions are **unanswered** and must be answered from
`sociomap.py`, not inferred. They are listed so the port has a checklist and so
nobody fills them in from a PDF or a hunch.

| # | Question | Where the answer lands |
| --- | --- | --- |
| 1 | Canonical input: square relation matrix, rectangular respondent × object matrix, pairwise evaluations, or derived? | `RelationMatrix` may need a rectangular sibling; `SociomapSpec.relation_method` |
| 2 | How is the relation matrix formed from raw data? | `relation_method` + engine function |
| 3 | Are relations directional? How is asymmetry treated (symmetrised, averaged, max, kept)? | `matrix_transform`; `RelationMatrix.max_asymmetry()` exists to *measure*, not decide |
| 4 | Is layout driven by raw relation, transformed relation, inverse distance, ranks, a fuzzy relation, or another derived quantity? | `matrix_transform`, `normalization_method` |
| 5 | Which optimisation / unfolding procedure? Objective function? Stopping rule? | `layout_algorithm`, `layout_parameters`, `LayoutResult.diagnostics` |
| 6 | Initialisation: fixed, data-derived, random? | `layout_seed`; `Provenance.seed` |
| 7 | Any randomness at all? Deterministic without a seed? | `layout_seed: None` is only valid if the code is seed-free |
| 8 | Which constraints fix translation, rotation, reflection, scale? | `LayoutResult.gauge_fixed`; decides the parity comparison in §8 |
| 9 | What exactly determines x, y, height, colour, and which are independent? | `height_metric`, `colour_metric`; `with_metrics()` already asserts independence of position |
| 10 | How are surfaces / contours derived? | possibly a height-field addition to the artifact |
| 11 | How are request arrows derived (thresholds, directionality)? | arrow rules in spec + artifact structure, deferred |
| 12 | How are segments computed or consumed? | `segments.py`, deferred |
| 13 | How are A/B / temporal comparisons computed? Aligned first? | `comparison.py`, deferred |
| 14 | What quality diagnostics exist (stress, correlation of distances, ...)? | `SociomapArtifact.quality` |
| 15 | Time-series behaviour, if present in the *current* implementation | feature matrix, §7 |
| 16 | Hidden defaults, thresholds, tolerances, module-level mutable state, ordering assumptions, serialisation assumptions, hot spots | `tools/sociomap_inventory.py` output |

`tools/sociomap_inventory.py` generates, from the real source and without
importing it, the per-function table with inputs, outputs, numeric defaults,
inline numeric literals, randomness calls and module globals read/written. Run
it first:

```bash
AIA_LEGACY_REFERENCE=../npc-panel-reference python tools/sociomap_inventory.py \
    --output docs/architecture/sociomapa-legacy-inventory.md
```

The generated table has the columns the audit asked for; *Responsibility*,
*Classification*, *Production destination* and *Parity requirement* are filled
in by the engineer after reading each function.

## 5. `SociomapSpec` — the methodology contract

`aia_core.domain.sociomap.specification.SociomapSpec`, contract version `1`.

| Field | Meaning |
| --- | --- |
| `methodology_version` | which methodology this spec describes (e.g. the legacy build it was recovered from) |
| `map_kind` | `respondent` or `object` — the two map families the product names |
| `relation_method` | how the relation matrix is derived from canonical inputs |
| `matrix_transform` | transform applied before layout (identity, symmetrisation, inverse, rank, fuzzy, ...) |
| `normalization_method` | scaling applied to the matrix |
| `missing_data_policy` | how `None` cells are treated; the data model never imputes |
| `weighting_policy` | which weights, if any, enter the relation |
| `layout_algorithm` | the unfolding / layout procedure |
| `layout_parameters` | its parameters, JSON data, part of the fingerprint |
| `layout_seed` | seed, or `None` as an explicit statement of seed-free determinism |
| `height_metric` | metric driving map height |
| `colour_metric` | metric driving colour |

Design decisions:

- **Every field is required.** There is no default methodology. A spec that
  omits missing-data treatment cannot be constructed.
- **Method values are identifiers, validated at execution time** by
  `require_supported(spec)` against `IMPLEMENTED: ImplementedMethods`. The
  registry is **empty** and stays empty until a method is ported with parity
  evidence. Executing any spec today raises `UnsupportedMethodology` naming
  every missing method. Nothing falls back.
- **`fingerprint()`** is a SHA256 over the contract version and every field
  with sorted keys. Any change to any field changes it. Artifacts record it, so
  reuse and audit can never confuse two methodologies.
- **Deferred fields**, to be added when the legacy behaviour is read (and
  refused until then by `extra="forbid"`): `arrow_rules`, `comparison_rules`,
  `segment_rules`, `statistical_rules`, `quality_thresholds`, and whatever
  `PRODUCT_POLICY.json` / `DATA_CONTRACT_v17.json` already say about Sociomapa.
  If those files carry an equivalent structure, this spec should be aligned to
  or generated from it rather than duplicated.

## 6. `SociomapArtifact` — the research-truth contract

`aia_core.domain.sociomap.models.SociomapArtifact`, contract version `1`. A
rendered map is never the canonical result; this is.

| Field | Meaning |
| --- | --- |
| `spec` | the full `SociomapSpec` (and therefore its fingerprint) |
| `entity_ids` | ordered, unique, non-blank; the canonical order for every vector |
| `relation` | `RelationMatrix` in the same entity order, missing cells preserved |
| `layout` | `LayoutResult`: `algorithm`, `x`, `y`, `gauge_fixed`, `diagnostics` |
| `height`, `colour` | `MetricValues` aligned with `entity_ids`; independent of each other and of `layout` |
| `provenance` | `implementation`, `implementation_version` (`0.0.0-contracts` today), `input_fingerprints`, `source_artifact_ids`, `seed`, `dependencies` |
| `quality` | algorithm-specific quality metrics |
| `warnings` | deterministic warnings raised during computation |

Excluded on purpose: timestamps (the artifact repository row records
`created_at`; a time inside the fingerprinted body would make identical
computations look different), pixel positions, palettes, drag state, PNG/SVG.

Guarantees, each covered by a test in `test_sociomap_contracts.py`:

- immutability (frozen models; no mutating operation exists);
- alignment (matrix order equals artifact order; every vector matches `n`);
- `fingerprint()` reproducible for identical content and sensitive to one
  coordinate, one warning, the seed, or the spec;
- `to_payload()` / `from_payload()` round-trip through JSON and **refuse a
  tampered payload** (body edited, or spec edited with the artifact fingerprint
  recomputed);
- `with_metrics()` swaps height and/or colour and moves no point;
- the artifact type forbids presentation fields.

Storage: `ArtifactRepository.put_json(payload=artifact.to_payload(), ...)` with
`input_fingerprint` set from the spec fingerprint and the input fingerprints,
so the existing reuse mechanism applies unchanged. No new table is needed.

## 7. Presentation and exploration layers

`aia_core.domain.sociomap.view`:

- **`ViewOverrides`** — dragged positions bound to an `artifact_fingerprint`.
  `apply_view_overrides(artifact, overrides)` returns a `DisplayedLayout`
  listing which entities were moved. Overrides bound to a different artifact or
  naming unknown entities are refused. The artifact is never written; tests
  assert its fingerprint and layout are unchanged after a drag.
- **`WhatIfLayer`** — a hypothesis as `RelationEdit`s against a base artifact.
  `derive_what_if_relation(base, layer)` returns a *new* `RelationMatrix`; the
  base is untouched. A derived artifact records the base under
  `provenance.input_fingerprints["what_if_base_artifact"]`. The edit vocabulary
  (cell overrides) is provisional until the legacy what-if mode is read; the
  layering invariant is not.

## 8. Parity plan and tolerances

Numerical parity is the primary Phase 9 deliverable and cannot start without
the reference. When it does:

1. **Pin the source.** `test_sociomap_parity.py` already asserts that each
   legacy Sociomapa module's SHA256 matches `reference-manifest.json`.
2. **Inventory first.** Generate and commit the function table (§4).
3. **Characterise before porting.** For each deterministic function, capture
   its outputs on shared fixtures (the legacy demo `RESPONDENTS_SOCIOMAP.csv` and
   `OBJECTS_SOCIOMAP_DEMO.json` files are the natural ones) into fixtures under
   `packages/aia_core/tests/fixtures/sociomap/`, with the reference SHA recorded
   beside them.
4. **Port the smallest coherent slice** — relation matrix derivation and its
   transforms — and compare cell by cell before touching layout.
5. **Layout comparison depends on `gauge_fixed`.**
   - If the legacy layout fixes translation, rotation, reflection and scale
     (canonical orientation), compare coordinates directly.
   - If it does not, align with an orthogonal Procrustes fit (translation +
     rotation + reflection; scale only if the legacy scale is arbitrary) and
     compare the aligned coordinates *and* the full pairwise distance matrix.
     Comparing distances as well is what stops an over-permissive alignment
     from passing genuinely different geometry.
   - A random initialisation must be reproduced with the legacy seeding path,
     not merely "a seed".
6. **Tolerances are recorded, not assumed.** Proposed starting points, to be
   confirmed against the legacy arithmetic:
   - matrix and metric values: absolute `1e-9` (pure arithmetic reorderings;
     anything looser indicates a real difference);
   - coordinates after alignment: to be derived from the legacy stopping
     tolerance (an iterative procedure cannot be reproduced tighter than it
     converged); record the value and its justification here when known;
   - decisions (arrows, gate outcomes): exact.
7. Compare, in order: relation matrix, transformed matrix, normalised values,
   coordinates, heights, colours, arrows, segment metrics, comparison outputs,
   quality outputs. Never screenshots.

## 9. Feature matrix

"Legacy" means the current NPC Panel implementation, which has **not** been
read; entries are what the production repository's documents say exists.

| Feature | Historical docs | Legacy implementation | Current AIA scope | Classification | Port now / later / exclude |
| --- | --- | --- | --- | --- | --- |
| Relation matrix derivation | yes | yes (`sociomap.py`) | Phase 9 | A + B | **first slice**, when reference available |
| Matrix transforms / normalisation | yes (fuzzy, computed matrices) | unknown which | Phase 9 | A + B | with first slice |
| Unfolding / layout | yes (H-model, SOMECS) | yes | Phase 9 | A + B | second slice |
| Respondent map | — | yes | yes | A | with layout |
| Object map (`test_socio_object_matrix_1881`) | object mapping | yes | yes | A | with layout |
| Height semantics (`test_socio_height_semantics_1880`) | — | yes | yes | A + B | with metrics |
| Colour metric | — | presumed | yes | A + B | with metrics |
| Matrix mode | — | yes | yes | presentation over A | after core |
| Comparison mode (A/B area) | map comparisons, overlaps | yes | yes | A (deltas) + presentation | later |
| What-if mode | — | yes | yes | layer over A | contract now; semantics later |
| Manual drag | — | yes (policy rule) | yes | presentation | **contract now** |
| Saved segments | subteam maps | yes (`segment_orchestration.py`) | yes | B (definition) + A (statistics) | later |
| AI segment intelligence | — | yes | yes | C | later; consumes A |
| Object manager | — | yes | yes | data management | later |
| Respondent / segment dialogue | — | yes (`respondent_dialogue.py`) | yes | C | later |
| Request arrows | yes | unknown | not named | A + B | verify in legacy; else exclude |
| Surfaces / contours (3-D) | STORM/WIND, 3-D | unknown | not named | A (values) + presentation | verify in legacy |
| Time series / temporal windows / animation | yes | unknown | not named | A + presentation | verify in legacy; else exclude |
| Communication / knowledge / cooperation designs | yes | unknown | not named | B (relation definitions) | exclude unless in legacy |
| Fuzzy matrices, H-model as such | yes | unknown | — | A | only if the legacy code is that |

## 10. Agent tool boundary

Nothing agent-facing is implemented; the shapes are fixed so the future
`ToolRegistry` entries are mechanical. Every tool takes typed inputs plus a
`SociomapSpec`, calls `require_supported`, and returns structured data with
provenance — never prose.

```
derive_relation_matrix(inputs, spec)            -> RelationMatrix + provenance
calculate_layout(relation, spec)                -> LayoutResult + diagnostics
calculate_metric(artifact, metric_id, spec)     -> MetricValues
compare_maps(artifact_a, artifact_b, rules)     -> structured deltas
calculate_segment_statistics(artifact, segment) -> structured statistics
evaluate_map_quality(artifact, thresholds)      -> metrics + pass/fail per rule
test_hypothesis(artifact, hypothesis_spec)      -> statistic, p, effect size, n
```

The agent may choose among these, choose parameters the spec permits, and
interpret results. It may not supply a number that appears in an artifact.
Scope (organisation, client, study) comes from the trusted `StudyContext`,
never from a tool argument.

## 11. Contradiction scan

Found while auditing; **not edited** because the surfaces belong to the
architecture reconciliation or the frontend.

1. **`docs/architecture/artifacts.md`** lists "computed map layouts" as an
   *ephemeral cache* in Redis with a TTL. A layout is canonical research truth
   under this document (fingerprinted, reproducible, auditable) and belongs in
   `project_artifacts`; a *rendering* cache may be ephemeral. The same row names
   Redis, which [ADR 0002](adr/0002-postgresql-authoritative-store.md) says is
   not being introduced; `docker-compose.yml` already omits it, while
   `docs/architecture/README.md` and the `Makefile` `services` target still
   mention it.
2. **`apps/web`** still implements the superseded MVP concept: a "Manual
   Sociomapping SOP" page with Import Pack download, Sociomap upload and "Gate 5",
   a `sociomap` artifact type that is an *uploaded file*, and a Stats page that
   exports a "Sociomapping Import Pack". The product docs describe a native
   Sociomapa workspace. This is the known "still mock-backed" state; it should be
   rewired against `SociomapArtifact`, not extended.
3. **`docs/migration/status.md`** reports the parity job as "94 skipped"; this
   change adds 5 more reference-gated tests (4 hash pins, 1 inventory run), so
   the number becomes 99. The status ledger is owned by the architecture
   agent and is not updated here.

## 12. Performance observations

Measured on the contracts only (no algorithm exists to profile), CPython 3.12,
dense synthetic matrices, one core:

| Entities | Matrix validation | Matrix fingerprint | Artifact + JSON serialise | JSON round-trip + integrity check | Wire size |
| --- | --- | --- | --- | --- | --- |
| 40 | 1 ms | 1 ms | 2 ms | 2 ms | < 0.1 MB |
| 400 | 91 ms | 76 ms | 153 ms | 209 ms | 3.2 MB |
| 2,000 | 2.7 s | 2.6 s | 4.3 s | 7.0 s | 81 MB |

Reading: a team-scale or 400-entity map costs nothing measurable at the
contract layer. At population scale the dense `n × n` relation matrix is itself
the cost -- O(n²) cells in Python tuples and 81 MB of JSON at 2,000 entities --
before any layout mathematics runs. The decision that follows is **not** taken
here: whether population-scale maps are computed over segments, stored with an
array-backed or sparse relation representation, or bounded by policy depends on
the legacy algorithm's own complexity, which is unknown until it is read. No GPU,
approximation or distribution is warranted on this evidence.

## 13. Verification of this change

Run from the repository root with the project virtualenv:

```bash
pytest packages/aia_core/tests/test_sociomap_contracts.py \
       packages/aia_core/tests/test_sociomap_inventory_tool.py \
       packages/aia_core/tests/test_sociomap_parity.py -q
ruff check packages/aia_core tools/sociomap_inventory.py
mypy packages/aia_core/src tools/sociomap_inventory.py --strict
```

The parity module skips its reference-gated tests without
`AIA_LEGACY_REFERENCE` and says so; a skip is not a pass.

## 14. Decisions needed from the product owner / methodology owner

1. **Reference access.** The port cannot proceed in an environment without
   `../npc-panel-reference`. Either provision it (the manifest verifies it) or
   accept that Phase 9 work is limited to contracts.
2. **Historical vs. current methodology.** When the code is read, any
   discrepancy between `sociomap.py` and the SOMECS / H-model literature is to be
   documented and the *current* behaviour preserved unless an explicit decision
   changes it. Who makes that decision, and where is it recorded?
3. **Spec governance.** Changing a `SociomapSpec` used for a client study
   changes every fingerprint downstream. Is that a gate-approved action (group
   D) in all cases, or only when a deliverable is frozen?
4. **What-if vocabulary.** Cell-level relation edits are the provisional
   mechanism; confirm against the legacy mode before exposing it to agents.
5. **Operating scale.** Team Sociomaps have tens of entities; a synthetic
   population map may have hundreds or thousands. Layout complexity is unknown
   until the algorithm is read; the contract layer handles 400 entities in
   under a quarter of a second and 2,000 in seconds (§12), and the engine's
   complexity decides the renderer and any need for segmentation before layout.
