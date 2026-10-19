---
status: planned
chunks:
  - "[ ] 0. The method owner's decisions: segment clustering algorithm and parameters, the register entry for each new map method"
  - "[ ] 1. Segments defined by the study's selected dimensions: a pure domain rule, with support and suppression"
  - "[ ] 2. A segment map computed through the existing engine, under a pinned method id"
  - "[ ] 3. Segments found by clustering, as an option, deterministic and labelled"
  - "[ ] 4. Each new map method registered INTERNAL_ONLY until the method owner approves it"
  - "[ ] 5. Map filters over respondents by dimension, answering aggregates only"
  - "[ ] 6. The respondent drill-down route: one respondent's profile and answers, internal, never exported"
  - "[ ] 7. The Lead reads filters and the drill-down, labelled modelled, on the approved route only"
  - "[ ] 8. The Sociomap artifact shows filters and drill-down (with research-lead-workbench chunk 20)"
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
1. **Segments by dimension.** Pure `domain/`: a segment is a cell of the selected dimensions
   (`DIMENSION_TOPICS` / `persona_topics.py` name them); below the floor a segment is suppressed
   and said so, never ordered. Test: a small cell is suppressed, a sufficient one is kept.
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
6. **Drill-down.** One route, `EDIT_STUDY`, returns one respondent's profile and answers from the
   stored dataset, every field labelled modelled. Tests: 403 without `EDIT_STUDY`; the route is
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
