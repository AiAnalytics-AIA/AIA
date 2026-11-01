# ADR 0045 — A report is composed per situation from a library of chapter kinds, each declaring its evidence; expert-scored SOMECS models and imported fieldwork are inputs, never shortcuts around the evidence rules

**Status:** Proposed — 2026-10-30.

**The product owner's answers** (10:12 UTC, 2026-10-30, in the PM coordinator's chat, relayed):
- Q16: "All of it, +41.5–58 days": everything here is in the MVP.
- Q17 and Q19: ""Terénní šetření" + experts client-facing".
- Q18: "Yes, legal approves terms". The approver is recorded as "legal counsel (to be named by Nigel)".
- 10:14 UTC: Q20, "Up to 30": expert and model maps take up to 30 objects, about 20 recommended; cost
  scenarios stay at 12. Market sizing (§MKT) is in the MVP: "Yes, add it to the MVP". A sixth build
  session: "Add a sixth session".

**Why:** the product owner shared a real client deliverable as an example of what AIA must generate
(10:03 UTC, 2026-10-30, in the PM coordinator's chat, relayed): "each report is unique to a unique
situation, this was one type". Its data came from "Both", a real field survey of B2B customers and
expert scoring for the SOMECS models; the design was left to this session. The deliverable is real
client material: it is not in the repository, and nothing here names its client, market or figures.

**Builds on:**
- [ADR 0044](0044-quantitative-model-studies.md): quantitative models, the WIND map, the `CALCULATED`
  and `ESTIMATED` grades.
- [ADR 0027](0027-client-data-is-client-reported-evidence.md) and
  [ADR 0037](0037-client-data-evidence-policy.md): client data under its accepted contract.
- [ADR 0024](0024-panel-grounded-respondents-are-modelled-evidence.md): AI respondents are modelled
  evidence.
- [ADR 0021](0021-deep-research-purpose-target-lineage.md): external research is context, never
  respondent evidence.
- [ADR 0026](0026-research-lead-proposes-a-person-decides.md): the Lead proposes, a person decides.
- The report document model (`domain/report/`).

**Changes:**
- the report's composition: from four fixed recipes to an approved outline of chapter kinds;
- the set of input provenances: an expert's rating;
- the set of data origins: imported fieldwork, proposed and awaiting the owner.

**Leaves unchanged:**
- every number is a ledger ref;
- every existing report is composed as it is today, byte for byte;
- respondent Sociomaps and their register.

**Date:** 2026-10-30.
**Plan:** [situation-reports](../../../.planning/plans/situation-reports.md).

## Context

**The example's anatomy** (anonymised; about 60 pages plus an appendix of maps):
- the contract parties and the terms of delivery, at the front and at the end;
- about 30 pages of fixed method text (complex systems, Sociomapping, SOMECS; conscious and
  unconscious information);
- interpretation chapters specific to the situation:
  - the context and goal;
  - the client's assets;
  - an addressable market in three scenarios, anchored on a foreign benchmark and corrected for social
    desirability;
  - segments profiled and prioritised into phases, with a behavioural typology;
  - competitor profiles and the conditions under which each becomes a threat;
  - spillover to a sister business;
- a phased entry strategy;
- risks ordered by their nature, each with its mitigation;
- KPIs in three planes, and the conditions for moving between phases;
- an appendix:
  - two SOMECS models from expert scoring (objects are segments; objects are risks), with SOMECS's
    native output table: per pair From, To, Incons, Cons, Asymm, Card, Card*; per object S(i),
    S(i)_Sd, d(i), Hm(i);
  - cut-out ("výřezové") maps chosen by an algorithm and commented in the chapters;
  - several hundred uncommented WIND-style maps, one per height variable, with coded object labels.

**What AIA has:**
- Four fixed recipes (`client_report`, `final_report`, `internal_report`, `study_documentation`), which
  compose a `ReportDocument` "in a fixed section order"
  (`packages/aia_core/src/aia_core/domain/report/templates.py:1-20, 186-244 @ 61230f5e`).
- `ReportKind` names four kinds (`domain/report/model.py:397-401 @ 61230f5e`).
- A `Section` carries its blocks and its `sources` (`model.py:503-513`), and the section-source manifest
  lists every section's sources (`domain/report/sources.py:39, 56 @ 61230f5e`).
- The internal report is composed by one function, `compose_internal_report`
  (`application/report.py:158 @ 61230f5e`).

**What AIA lacks:**
- **Profile fields.** The client profile holds a short code, industry, market and description, with no
  company registration, seat or representative (`domain/client_profile.py:49-62 @ 61230f5e`).
- **An expert-scoring input.**
- **Imported fieldwork.** The AI panel is the Czech general population 18+, so it cannot stand for B2B
  segments. `client-data-in-analysis` plans a client's own survey and its own Sociomap (chunks 4 and 6,
  ADR 0027 decisions 2 and 8), but not fieldwork AIA commissions and imports.
- **SOMECS's native output table.** The evidence register has no entry for any of its quantities
  (`docs/migration/sociomapping-evidence-register.json`, the SOMECS entries D1-M2 @ 61230f5e).

## Decisions

### 1. A report is an approved outline of chapter kinds

- **The library.** A **chapter kind** is a registered, versioned spec (`domain/report/chapters.py`). It
  declares:
  - what it is for;
  - the artifacts and evidence it reads, each by type;
  - the grades it may print on each surface (client or internal);
  - its deterministic blocks, built by code;
  - optionally, prose a writing worker drafts (`lead-orchestration#LO9b`, `REPORT_WRITING`). That prose
    cites refs and passes the sentence check (RD7), and a person accepts it.
- **The outline.** A `ReportOutline` is an ordered list of chapter instances: a kind, its parameters,
  and the artifacts it reads, pinned by id and SHA-256. The Lead may propose an outline, or a change to
  one, per change (ADR 0026). **A person approves it**, as a ledger row under a new subject,
  `report_outline`. The composer composes exactly the approved outline.
- **The four recipes become preset outlines.** Each existing kind is a library chapter, and
  `client_report` / `final_report` / `internal_report` / `study_documentation` become named presets of
  those kinds. A test holds every preset's DOCX byte-identical to the recipe's today. Nothing existing
  changes; a situation report is a new outline over the same kinds plus new ones.
- **Sources across studies of one client.** A chapter may pin artifacts from several studies of the
  same client: a research run, a model run, an expert model. It pins them by id and SHA-256, never "the
  latest", and the manifest names each. Another client's artifact is refused.
- **Fixed text is versioned data.** The method chapters and the contract terms are texts stored and
  versioned like Metodika's modules:
  - method text is signed by the methodology owner (A. Bahbouh, ADR 0044 Q9);
  - terms text is approved by the product owner's legal counsel (Q18; "legal counsel (to be named by
    Nigel)", not yet named).

  A report pins the versions it printed.

### 2. Every chapter declares its evidence; the rules do not loosen per situation

**AIA stays stricter than the example.** A number in any chapter is a ledger ref, with its grade:
*výpočet*, *odhad*, *modelováno*, *z dat klienta*, *terénní šetření* (decision 5) or *expertní
hodnocení* (decision 3), with external sources cited as context.

In particular, **a market size appears only as a model result**: the market-sizing model type's output
(`quantitative-families` §MKT), with every step of its chain an input with a provenance and a source,
graded.
- A benchmark from another market is a `public_source` input, cited.
- A correction for social desirability is an input. It is stated by a person, or `ESTIMATED` by a method
  A. Bahbouh registers. It is never a factor written into prose.
- A market size typed into a chapter's text is refused by the sentence check and the report validator.

Strategy, risk and KPI chapters are a person's or the writer's reasoning over cited refs. They state no
number of their own.

### 3. Expert scoring is an input with its own provenance and grade

- **What it is.** A SOMECS objects × criteria model is scored by named experts (the example's two
  models: segments, and risks). It is an ADR 0044 model type, `somecs_expert`. Its input is a new, fifth
  provenance, `expert_rating`: one expert's score of one object on one criterion. The rating records:
  - the expert;
  - their role, and whether they are internal or the client's;
  - when, the form version, and the criterion's scale extremes and direction.
- **The form.** Experts score through an input form. A missing score stays missing, never 0: SOMECS's
  0 fill (`SOMECS-D1`) is not adopted.
- **Objects.** At most 30 per model, as SOMECS allows, with about 20 recommended. Above 20 the page says
  so; a 31st is refused `too_many_objects` (Q20, 2026-10-30).
- **Aggregation.** The panel's matrices are aggregated as SOMECS does (`SOMECS-A1`, weighted mean),
  under a discrepancy threshold (`SOMECS-A2`, open). The weights, the threshold and the minimum number
  of experts are A. Bahbouh's (sign-off S10).
- **Grade.** The aggregated scores print *expertní hodnocení*, with the number of experts and their
  roles. **They reach the client report** (Q19, decided 2026-10-30), with that label.
- **Shared engine work.** From there it is ADR 0044 decision 12's engine path, reused, not rebuilt: the
  objects × properties fuzzy matrix, layout and fit, and the WIND height. The criteria are the
  properties.
- **SOMECS's native output table** (Incons, Cons, Asymm, Card, Card*, S(i), S(i)_Sd, d(i), Hm(i)) is
  computed only once each quantity has a register entry with its formula. No source AIA holds defines
  them. Until then each is `MethodologyUndetermined`, by name (sign-off S11, export E10).

### 4. Maps in bulk, and the cut-out maps by a registered rule

- **Bulk maps.** Every height variable of a model gives one stored map snapshot (`report-delivery#RD4`'s
  renderer), deterministic, coded labels with their key, placed in an appendix "bez komentáře".
- **Cut-out maps.** The "výřezové" maps (zooms on a region or coherence group, `SOMECS-C2`) are chosen
  by a selection rule that A. Bahbouh registers (sign-off S12). Each is commented in the chapter that
  cites it.
- **Status.** A map's status is its method's register entry. Bulk generation changes no map's status.

### 5. Imported fieldwork: measured respondents beside the modelled panel

- **Why it is needed.** A B2B segment is not in the Czech 18+ population, so its evidence must come
  from real fieldwork: a questionnaire designed in AIA, fielded by a partner, its answers imported.
- **The origin (Q17, decided 2026-10-30).** A new data origin, `FIELDWORK_IMPORTED`, labelled
  *terénní šetření*. It is not *z dat klienta*, because the client did not measure it.
- **The rules it falls under:**
  - imported under a data contract, as ADR 0027/0037 define it;
  - MQ-18's survey rule: n is the row count, or Kish n when weighted, with an interval;
  - its answers mapped to the study's own design items;
  - its own Sociomap through the existing engine (`client-data-in-analysis#6`);
  - never merged with the AI panel's numbers.
- **What reuses what.** It reuses client-data-in-analysis's contract, analysis copy and survey shape,
  and adds only the origin and the mapping to design items.

## Consequences

- **What it costs.** A chapter-kind registry and an outline, with the old recipes as presets; a fifth
  provenance and a form; a proposed origin; bulk maps; a set of new chapter kinds. The plan estimates
  about 41.5-58 session-days in all, **all of it in the MVP** (Q16, 2026-10-30).
- **What it buys.** A deliverable shaped by its situation, under the same evidence rules as everything
  else.
- **What it does not do.**
  - no number typed into prose;
  - no market size outside a model;
  - no SOMECS output quantity without its formula;
  - no merge of imported, client or modelled data into one number.

## Alternatives considered

- **More fixed templates, one per report type.** Rejected: "each report is unique to a unique
  situation".
- **Free documents assembled by the Lead.** Rejected: every chapter would have to be audited by hand;
  declared kinds keep the evidence rule enforceable.
- **Expert scores as `stated` inputs.** Rejected: a panel's aggregation, discrepancy and roles are a
  method, and the reader must know the numbers are expert judgement.

## Not decided here (the decision page)

Answered on 2026-10-30:
- Q16: all of it, in the MVP.
- Q17: `FIELDWORK_IMPORTED`, *terénní šetření*.
- Q18: the party details come from the client profile; the terms library is approved by legal counsel,
  to be named by Nigel.
- Q19: expert scores are client-facing.

- Q20: expert and model maps take up to 30 objects (about 20 recommended); cost scenarios stay at 12.
- Market sizing (§MKT) is in the MVP, so a market-size chapter can be in an MVP report, still only as
  the model's result (decision 2).

Open:
- The name of the legal counsel who approves the terms library (Q18).
