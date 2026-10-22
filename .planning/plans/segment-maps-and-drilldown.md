---
status: planned
chunks:
  - "[ ] 0. The method owner's decisions: segment clustering algorithm and parameters, the register entry for each new map method"
  - "[ ] 1. Segments defined by the sampler's stored descriptors (MVPQ-03): a pure domain rule, with support and suppression"
  - "[ ] 2. A segment map computed through the existing engine, under a pinned method id"
  - "[ ] 3. Segments found by clustering, as an option, deterministic and labelled"
  - "[ ] 4. Each new map method registered INTERNAL_ONLY until the method owner approves it"
  - "[ ] 5. Map filters over respondents by dimension, answering aggregates only"
  - "[ ] 6. The respondent drill-down route: one respondent's profile and answers, internal, never exported"
  - "[ ] 7. The Lead reads filters and the drill-down, labelled modelled, on the approved route only"
  - "[ ] 8. The Sociomap artifact shows filters and drill-down (with research-lead-workbench chunk 20)"
  - "[ ] 9. Respondent-map and segment-map figures and report chapters (W2, before report-delivery RD4): drawn beside the object map, keyed by battery, method and kind with the register status"
  - "[ ] 10. Segment evidence (W2, after 1; the owner, 2026-10-20): per-segment aggregates as SEGMENT-level admitted claims, thin segments suppressed, so the Segments module can state a finding"
  - "[ ] 0a. What a segment is, and the respondent attributes stored per respondent: their class and who may read them; before chunk 1"
  - "[ ] 11. Sociomapa matrix and comparison modes: two maps side by side, over aia-sociomap-5's maps (D-42)"
---
# Segment maps, map filters and the respondent drill-down

Track C of the MVP roadmap (`overview.md` § MVP roadmap, #493). Written 2026-10-19 from
`mvp-cohesion.md` F2 and F7 (#496). **Owner: a chat session, named when chunk 1 starts; the method
owner decides chunk 0 in an AIA session.**

## Decisions this plan carries

| Id | Decision (2026-10-19) |
|---|---|
| MVP-16 | Map kinds in the MVP: object, respondent and segment; hybrid after. The Sociomap artifact has filters and drill-down to one respondent's profile and answers |
| MVP-17 | Segments are **both** defined by the study's dimensions (default) and found by clustering (an option; the algorithm is the method owner's) |
| F2 (`mvp-cohesion.md`) | The drill-down is allowed for the researcher, **the Lead may read it**, and it is never in a client export |

## What exists

- AIA computes object maps only. Respondent placement is chunk 3 of `sociomap-formula-corrections`
  ("ideal points against this object map, audit F10",
  `packages/aia_core/src/aia_core/domain/sociomap/engine_v2.py:93 @ 0b4e05e`, per
  `mvp-consolidation.md` §3). **This plan starts after that chunk**; it does not build respondent
  placement.
- A Sociomap's status is the register's for the exact method and spec fingerprint; a method not
  registered is `INTERNAL_ONLY` and `require_client_facing` refuses it
  (`domain/sociomap_register.py`, `ARCHITECTURE.md` §4 "Integrated is not exposed").
- A panel answer is `AGGREGATE_ONLY` and `PERSON_VALUE_MODELED`
  (`domain/evidence/instrument.py:31, 43 @ 085abe0`); respondent rows are never sent to the browser
  and the Sociomap artifact is served only with `EDIT_STUDY` (`ARCHITECTURE.md` §4).

## Chunks

0. **Method owner.** The clustering algorithm and its parameters; whether segment maps need a
   separate register entry per segment definition; the support floor per segment (`n_min` 30 is
   today's WARN for a Sociomap, `domain/research_design.py` `sociomap_support`). Blocks 3 and 4.
1. **Segments by the sampler's descriptors.** Pure `domain/`: a defined segment is a cell of the
   descriptors the sampler stores per respondent with lineage (the product owner, 2026-10-20,
   MVPQ-03), not of the study's selected dimensions (a dimension is a persona-topic allowlist and
   partitions no one, G30). The permitted combinations, how accepted own dimensions take part and
   the support floor are the methodology owner's (chunk 0). Before this is built it is reconciled
   with the methodology owner's PR #504 (`aia-sociomap-5`: a respondent map and clustered taste
   segments). Below the floor a segment is suppressed and said so, never ordered. Test: a small cell is suppressed, a sufficient one is kept.
2. **Segment map.** The existing contract-3 engine per segment, no new geometry; a new method id
   pinned at run start like every method (`SociomapMethod`), fingerprint in the reuse key. Test:
   removing the pin fails the run; the same pin reuses.
3. **Clustering option.** Deterministic (declared seed), result stored, labelled "found by
   clustering" everywhere it shows. Needs chunk 0.
4. **Register.** Each new method is `INTERNAL_ONLY` by absence from the register; the method owner's
   approval is an entry in `sociomap_register.py`. Test: a client report with an unregistered
   segment map refuses it by name. **Without this, AC-13's "approved map snapshots" cannot include
   respondent or segment maps.**
5. **Filters.** An API route returning aggregates for a filter set (counts, the map recomputed or
   read), never rows. Test: no response body contains a respondent id.
6. **Drill-down.** One route, `EDIT_STUDY`, returns one respondent's stored attributes and answers
   from the stored dataset, every field labelled modelled; **never the generated persona profile
   prose** (the product owner, 2026-10-20, MVPQ-03). Tests: 403 without `EDIT_STUDY`; the route is
   not reachable from the report or snapshot path; never an `AdmittedClaim`. `ARCHITECTURE.md` §4's
   "rows never sent" gains the one named exception (docs PR).
7. **The Lead reads it.** Filters and the drill-down enter the Lead's results context
   (`mvp-cohesion.md` F4) classified before any model reads them. One respondent's modelled answers
   derive from the panel, so the Lead's configured route must be the one the licence determination
   approves (`bedrock-eu-primary`, OI-61) or the gateway refuses. Test: the route refuses the
   lineage unless it is the approved one; the Lead says "modelled" when it quotes one respondent.
8. **Artifact.** The filters and drill-down inside the Sociomap artifact, with
   `research-lead-workbench` chunk 20 and its pointing (chunk 16).

## Depends on / feeds

Needs `sociomap-formula-corrections` 3 (respondent map), `0b` (method owner) and the Lead's results
context. Feeds AC-09 and AC-13. The clustering and the register entries are the only parts that
wait on a person outside engineering.

## Open

- Whether a segment map's method needs one register entry or one per segment definition.
- Whether the drill-down shows the persona's generated profile text or only its attributes and
  answers (a model-written text about an invented person is still modelled).

## Doc follow-up

`ARCHITECTURE.md` §4: the drill-down exception and that it is internal and never exported.

## Added by the master plan (2026-10-19)

**0a.** Chunk 1 defines a segment as a cell of the study's selected dimensions (`DIMENSION_TOPICS`), but a
dimension in AIA is a persona-topic allowlist (`persona_topics.py:313-320`) and a stored respondent holds
only id, donor, weight and answers (`fieldwork.py:172-181`; the persona profile and each draw's record are
not stored). Segment maps, filters and the drill-down have nothing to read until one record per respondent
holds the segmentation variables. The owner and the method owner state the variable (the proposed default
is the quota-cell fields sampling already uses: age group, sex, region, education from n 700); this chunk
then stores it, classes it and says who may read it: the producer, the lineage, the storage, the allowed descriptor set, the support and suppression rules and the consumer contract. An approved own dimension needs an actual consumer (a segmentation or filter), not only a child file (gap G28, `client-knowledge-lifecycle` K5). Gap G30; interface I5.

## Cross-check additions (2026-10-20)

From the independent cross-check of the master plan against the code (`mvp-master-plan.md` §6.1, G47-G57). Anchors are `@ 085abe0`.

**9. Respondent-map and segment-map figures and report chapters (G54, X9).** `object_map_snapshots` and `compose_map_sections` read only contract-3 object maps through `read_object_maps`, `report-delivery#RD4` says S2 supplies the figure function, and the run graph has no segment-map node or report `depends_on` edge. This chunk draws `draw_respondent_map_snapshot` and `draw_segment_map_snapshot` beside `draw_object_map_snapshot`, keys `object_map_snapshots` and `compose_map_sections` by (battery, method, kind) with the register status and any suppressed or not-mappable segment named, and puts the segment-map artifact in the report's `depends_on`. It states whether a client snapshot prints respondent points or only the aggregate terrain. Reconcile with the methodology owner's `aia-sociomap-5` (#504) first. Tests: deterministic bytes; `client=True` refuses an unregistered kind.

**10. Segment evidence (G48, X1; the owner, 2026-10-20: build segment evidence).** MVPQ-04 blocks the report while any of the eight modules has no supported finding, and chunk 5 says segment filters are never an `AdmittedClaim`; nothing produces SEGMENT-level admitted evidence (`ClaimLevel.SEGMENT` is defined at `domain/evidence/claims.py:81` and has no producer; `domain/analysis/modules.py:91-96` tells the module to say segmentation cannot be assessed). So the Segments module could never state a finding and no report could be composed. This chunk computes per-segment aggregates over chunk 1's descriptors (Kish effective n, support, suppression) and admits them as SEGMENT-level claims through `admit_numeric_claims`, so the module states a finding from them. Filters (chunk 5) stay aggregates only. Tests: a thin segment is suppressed and named; `RELIGION` is refused client-facing; the Segments module of the library study states a finding that cites a SEGMENT claim, and the report composes.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunk.** 11 (W3), D-42 in.

**Existing chunks, changed.** Segments stay **defined by the sampler's stored descriptors** (MVPQ-03,
§ Decisions; `mvp-cohesion.md`); `-5` does not replace them. D-13 changes only the engine: 2 computes
each descriptor-defined segment's map with `-5`, the only method, instead of the contract-3 engine
(G59). 3 stays the optional clustering, and `-5`'s taste segments are one candidate for it; whether
they are, and how they relate to descriptor segments, is the methodology owner's (MQ-02, MQ-05), so
3 waits on it. 10 does not wait: without SEGMENT-level evidence the Segments module has no supported
finding, and MVPQ-04 then blocks **every** report, not only a study with segments. 9 names `-5`'s
fields; its figures are `signed-off-sociomap-method#9`'s.

### Ordering (the coordinator's census, 2026-10-21, OI-192)

`segment-maps-and-drilldown#10` (segment evidence) lands before `evidence-integrity#9b` (the
refusal while a module has no supported finding) and `artifact-chain-to-draft-report#CHN10`. Once
9b lands, the Segments chapter (ch-5) has no admitted producer without 10, so no run could reach a
draft report.
