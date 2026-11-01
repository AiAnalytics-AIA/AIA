---
status: planned
chunks:
  - "[ ] SR0. ADR 0045 accepted; the legal counsel who approves the terms library (Q18) named"
  - "[ ] RC1. Chapter kinds and the outline: a registry of versioned chapter kinds, ReportOutline, the four recipes as preset outlines composed byte for byte as today; generalises cost-model-study CP8's frame"
  - "[ ] EX1. Expert scoring: an expert panel (named experts, role, internal or the client's), a scoring form over objects × criteria with scale extremes and direction, the expert_rating provenance, aggregation by the registered weights and discrepancy threshold; a missing score stays missing"
  - "[ ] EX2. The somecs_expert model type on ADR 0044's platform, reusing cost-model-study CS2-CS5 (fuzzy matrix, layout and fit, WIND, view) with criteria as properties"
  - "[ ] RC2. The outline proposed by the Lead and approved by a person (ledger subject report_outline), per change"
  - "[ ] RC3. Chapters across studies of one client: artifacts pinned by id and SHA-256, another client's refused, every source in the manifest"
  - "[ ] RC4. Fixed method texts as versioned data, signed by the methodology owner; a report pins the versions it printed"
  - "[ ] RC5. Contract parties and terms: the client profile's registration fields (Class A), the organization's own, a terms text library approved as Q18 decides"
  - "[ ] RC6. New chapter kinds: segment profiling and prioritisation, competitor profiles (Deep Research, cited), phased strategy, risks with mitigation, KPI framework; every number a ref, prose through the writer and the sentence check"
  - "[ ] EX3. SOMECS's native output table (Incons, Cons, Asymm, Card, Card*, S(i), S(i)_Sd, d(i), Hm(i)) once each has a register entry with its formula; export E10 as the check"
  - "[ ] MM1. Bulk maps: one stored snapshot per height variable of a model, coded labels with their key, an appendix without comment"
  - "[ ] MM2. Cut-out maps (výřezové): zooms on regions or coherence groups chosen by the registered selection rule, each commented where cited"
  - "[ ] FW1. Imported fieldwork: the origin Q17 decides, a questionnaire's answers imported under a data contract and mapped to the study's design items, MQ-18's survey rule, its own Sociomap, never merged with the AI panel"
---
# Reports composed per situation, expert-scored SOMECS models, imported fieldwork

Written 2026-10-30 on the product owner's input (10:03 UTC, relayed by the PM coordinator). He shared a
real client deliverable as an example of what AIA must generate: "each report is unique to a unique
situation, this was one type". Its data came from "Both", a real B2B field survey and expert scoring for
the SOMECS models. The rules are [ADR 0044](../../docs/architecture/adr/0044-quantitative-model-studies.md)
and [ADR 0045](../../docs/architecture/adr/0045-reports-composed-per-situation.md) (Proposed).

**The example is real client material.** It stays out of the repository, PRs and artifacts; this plan
carries only its anonymised anatomy (ADR 0045, Context).

**Owner:** S4, S5 and S6 (§ Lanes; a sixth session approved 2026-10-30). Anchors are `@ 61230f5e`.

## What already exists, and is reused rather than rebuilt

- **The report model.**
  - The four recipes (`domain/report/templates.py:186-244`) are fixed section orders over
    `ReportDocument`.
  - `Section.sources` and the manifest (`domain/report/sources.py:39, 56`) already record what each
    chapter read.
  - RC1 turns the recipes into preset outlines; it does not replace them.
- **The platform.** `cost-model-study` CP8 builds the model report's frame (the grade, the admission,
  the template frame); RC1 generalises it.
- **The engine.** `cost-model-study` CS2-CS5 builds the objects × properties fuzzy matrix, layout and
  fit, WIND and its view; EX2 reuses all of it, with criteria as properties.
- **`sociomapping-engine`.**
  - It already has the fuzzy matrix contract (1a), the H-Model accuracy (2a) and its significance (2c,
    open).
  - It has coherences and zoom (6a, built; `SOMECS-C2` documented), which MM2's cut-outs use.
  - It has STORM (3) and regions (8), both open.
- **The evidence register.** SOMECS's aggregation (`SOMECS-A1` documented, `SOMECS-A2` threshold open),
  its 0 fill (`SOMECS-D1`, not adopted) and WIND (`SOMECS-M2`, open). Nothing defines Incons, Cons,
  Asymm, Card, Card*, S(i), S(i)_Sd, d(i) or Hm(i).
- **`client-data-in-analysis`.** A client's own survey under a data contract (ADR 0027 decision 2) and
  its own Sociomap (chunk 6); MQ-18's survey rule. FW1 adds only the origin and the mapping of imported
  answers to the study's design items.
- **`quantitative-families` §MKT.** Market sizing as a model type. ADR 0045 decision 2 makes it the
  only way a market size reaches a report.
- **`report-delivery`.** The map snapshot renderer (RD4), the sentence check (RD7), Deep Research
  context in the client report (RD11).
- **`lead-orchestration`.** The writer worker (`LO9b`, `REPORT_WRITING`) and registry-driven proposals
  (`LO21`).

## Chunks, estimates and timing

Session-days, review and CI included.

| Chunk | Estimate | Needs | MVP? |
|---|---|---|---|
| RC1 | 1.5-2 beyond CP8 (3-4 alone) | `cost-model-study#CP8` | MVP |
| EX1 | 4-5 | `cost-model-study#CP1`-`#CP3`, `#CP10` | MVP |
| EX2 | 2-3 | EX1; `cost-model-study#CS2`-`#CS5` | MVP |
| RC2 | 2.5-3.5 | RC1; `lead-orchestration#LO21` | MVP |
| RC3 | 2-3 | RC1 | MVP |
| RC4 | 1.5-2 | RC1; A. Bahbouh's texts | MVP |
| RC5 | 2.5-3.5 | RC1; Q18; one migration | MVP |
| RC6 | 10-15 (five kinds, 2-3 each) | RC1; `lead-orchestration#LO9b`; `report-delivery#RD7`, `#RD11`; `segment-maps-and-drilldown#1`, `#10`; `quantitative-families` MKT | MVP |
| EX3 | 4-6 | EX2; S11; export E10 | MVP |
| MM1 | 3-4 | EX2; `report-delivery#RD4` | MVP |
| MM2 | 3-4 | MM1; S12; `sociomapping-engine#6a` | MVP |
| FW1 | 5-7 | Q17; `client-data-in-analysis#2`, `#3`, `#3a`, `#3b`, `#6`; S14 | MVP |
| **All, in the MVP (Q16)** | **41.5-58** | | |

**Q16, 2026-10-30: "All of it, +41.5–58 days".** Every chunk here is in the MVP. With
`cost-model-study`'s 79.5-102, the quantitative-model and report track totals **121-160 session-days**.

### Lanes

| Lane | Chunks | Session-days |
|---|---|---|
| **S4** (as in `cost-model-study`) | its CP1-CP9, CM1-CM7, CR1, CR8, CR9, CS5; plus RC1 and EX1's form | 48-59.5 |
| **S5** (as in `cost-model-study`) | its CP10, CR2-CR7, CR10, CS1-CS4; plus EX1's domain part, EX2 and EX3 | 43.5-58 |
| **S6** (approved, "Add a sixth session", 2026-10-30) | RC2-RC6, MM1, MM2, FW1, and `quantitative-families` MKT1-MKT5 | 42.5-58 |
| **All** | | **134-176** |

**Calendar** (five session-days a week): the three lanes run side by side, each about 42.5-59.5
session-days, so the track takes about **10-12 weeks**. On S4 and S5 alone it would take about 13.5-17.5.

S6's chunks are the report, fieldwork and market-sizing work, which needs neither S5's statistics nor
S4's platform beyond RC1:
- RC2-RC6, the outline proposal and the chapter kinds;
- MM1 and MM2, the bulk and cut-out maps;
- FW1, imported fieldwork;
- MKT1-MKT5, market sizing (moved into the MVP, "Yes, add it to the MVP", 2026-10-30). That plan keeps
  the chunks; they are built on this lane.

**Starts and waits:**
- S6 starts once RC1 merges (its first chunk, on S4, in W2).
- MM1 also waits for EX2.
- MKT4 waits for its ADR 0021 amendment (a market-sizing Deep Research purpose), which S6 writes first.

**A market-size chapter is now in the MVP.** It joins RC6's kinds, built with MKT5, and prints only the
model's result (decision 2).

### RC1. Chapter kinds and the outline

- `domain/report/chapters.py`: `ChapterKind` declares its id, version, purpose, the artifact types it
  reads, the grades it may print per surface, its deterministic block builder, and optionally a writer
  draft spec.
- `ReportOutline` is an ordered list of chapter instances (kind, parameters, pinned sources).
- Every existing section becomes a kind, and the four recipes become presets.
- The composer composes an outline; the old functions call it with their preset.

**Tests:**
- each preset's DOCX is byte-identical to today's recipe for the stored fixtures;
- a chapter printing a grade its kind does not allow on that surface is refused;
- an outline citing an unpinned artifact is refused.

### EX1. Expert scoring

- The panel: named experts with their role and side (internal, or the client's), recorded on the model.
- The form: objects × criteria with each criterion's scale extremes and direction (lower-is-better
  negated), one expert per form, saved per score.
- Provenance `expert_rating`: the expert, when, the form version.
- Aggregation per S10: the weights, the discrepancy threshold (`SOMECS-A2`) and the minimum number of
  experts. A missing score stays missing; the 0 fill is not adopted.
- Grade *expertní hodnocení*, with the number of experts and their roles.

**Tests:**
- a missing score is not 0;
- two experts disagreeing beyond the threshold are refused by name;
- the aggregate is the weighted mean (`SOMECS-A1`);
- the form's scale extremes reach the fuzzy matrix unchanged.

### EX2. The `somecs_expert` model type

Registered on ADR 0044's platform. Objects and criteria come from the form, and from there it is
`cost-model-study` CS2-CS5 unchanged: the fuzzy matrix, the layout and fit, the WIND height on a chosen
criterion, the view.

**Tests:** 30 objects accepted, a note above 20, a 31st refused `too_many_objects` (Q20); the type passes
CP2's registration and determinism harness; a segments model of 7 objects and
a risks model of 6 build their maps; the respondent map's terrain is unchanged.

### RC2-RC6, EX3, MM1, MM2, FW1

- **RC2.** The Lead proposes an outline from the library and the situation (the brief, the studies, the
  models). A person accepts each change, and the approval is a `report_outline` ledger row.
  **Test:** an outline the person has not approved does not compose.
- **RC3.** A chapter pins a research run's, a model run's or an expert model's artifacts by id and
  SHA-256, within one client. The manifest names each.
  **Test:** another client's artifact is refused; a superseded artifact is named as such.
- **RC4.** Method texts as versioned data, signed by A. Bahbouh (S13); a report pins each version.
  **Test:** an unsigned text is printed internally only.
- **RC5.** The client profile gains its registration (IČ/DIČ), seat and representative (Class A); the
  organization's own details; a terms library approved by legal counsel (Q18; "to be named by Nigel").
  **Test:** no contract-party block in a report whose outline has no such chapter; values only from the
  profile.
- **RC6.** Five chapter kinds, each declaring its evidence:
  - segment profiling and prioritisation (segments as `segment-maps-and-drilldown` defines them);
  - competitor profiles (a Deep Research run per competitor, findings cited as external);
  - a phased strategy;
  - risks with their mitigation (optionally an expert risk model, EX2);
  - KPIs in planes, with the conditions for moving between phases.

  Prose goes through the writer and the sentence check, and every number is a ref.
  **Test:** a market size in a chapter's prose is refused; a risk chapter's order by nature is the
  person's, recorded.
- **EX3.** Each native SOMECS quantity is computed only with its register entry and formula (S11), and
  checked against export E10: a SOMECS objects × criteria project and its output table.
  **Test:** an unregistered quantity is `MethodologyUndetermined`, by name.
- **MM1.** For each height variable, a stored snapshot (RD4), deterministic, with coded labels and their
  key.
  **Test:** the same model gives the same bytes; the count equals the variables.
- **MM2.** Cut-outs by the selection rule of S12 over coherence groups and zoom (`SOMECS-C2`), each
  cited and commented where used.
  **Test:** the rule's choice is reproducible; an uncited cut-out is not in a chapter.
- **FW1.** The origin as Q17 decides. Answers are imported under a data contract and mapped to the
  study's design items, under MQ-18's survey rule (n or Kish n, intervals) and S14's weighting. The
  survey gets its own Sociomap (`client-data-in-analysis#6`) and is never merged with the AI panel.
  **Test:** a B2B segment's number carries the fieldwork label and its support; an AI-panel number for
  the same item sits beside it, never averaged.

## A. Bahbouh's sign-off sheet: the additions

These continue `cost-model-study` § The methodology owner's sign-off sheet.

| # | Item | What he signs |
|---|---|---|
| S10 | Expert aggregation (`aia-expert-agg-1`) | the experts' weights; the discrepancy threshold (`SOMECS-A2`) and its measure; the minimum number of experts; that a missing score stays missing; the object cap of 30, about 20 recommended (Q20, decided) |
| S11 | SOMECS's native output table | the formula of each of Incons, Cons, Asymm, Card, Card*, S(i), S(i)_Sd, d(i), Hm(i), checked against export E10 |
| S12 | Bulk and cut-out maps (`aia-map-select-1`) | which variables get maps; the cut-out selection criteria (fit, height contrast, coherence or region significance); the zoom rule (`SOMECS-C2`) |
| S13 | Fixed method texts | each text and its version (the frame, Sociomapping, SOMECS, conscious and unconscious information) |
| S14 | Imported fieldwork | weighting and support for a B2B frame under MQ-18; how its map is labelled |
| S15 | Social desirability correction (with `quantitative-families` §MKT) | a stated factor, or an estimated one and its method |

## Findings

None yet.

## Doc follow-up

- **`mvp-master-plan.md`:**
  - §3.1: this plan, core (Q16 (b));
  - §11.1: Q16-Q20, the sixth session and market sizing in the MVP, answered 2026-10-30; §11.4: the name
    of the legal counsel (Q18).
- **`mvp-execution-contracts.md`:** every chunk here in W3-W4 (Q16 (b)), in the lanes of § Lanes.
- **`mvp-development-plan.md` §2:** the sixth build session, S6 (approved 2026-10-30), and its lane.
- **`docs/architecture/adr/README.md`:** row 0045, Proposed.
- **`sociomapping-engine.md`:** E10 (a SOMECS objects × criteria project with its output table) and the
  open questions for S11.
- **`mvp-methodology-packet.md`:** S10-S15.
- **`client-data-in-analysis.md`:** FW1's origin beside chunk 6's client survey, once Q17 is answered.
