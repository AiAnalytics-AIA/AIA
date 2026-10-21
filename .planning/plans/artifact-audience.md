---
status: planned
chunks:
  - "[ ] AUD1. Cílová skupina's contract as data: view operations, pointable ids (definition, filter, subpanel, assumption) and V2's interaction contract; the first Lead targets this screen has"
  - "[ ] AUD2. The body as V2 draws it: Definice, Filtry populace as a table of factor, value and count, the LIVE version named, counts only"
  - "[ ] AUD3. Each filter's own count: the audience preview answers a per-filter count beside the combined one, still counts only"
  - "[ ] AUD4. Předpoklady o cílové skupině: the assumption list with attached evidence, external and client knowledge labelled apart"
  - "[ ] AUD5. The Lead on Cílová skupina: propose_audience as a card, its proposal inline, the stage's AI start removed"
  - "[ ] AUD6. Journey: Cílová skupina at 1440, 1100, 768 and 390 px, zero paid jobs"
---
# Artifact: Cílová skupina (Audience)

Umbrella: `research-lead-workbench#22` (with Dimenze). Chain:
[`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md). Anchors `@ 25f26232`;
prototype `@ 9b50963f`.

## 1. What it is, and its single job

**Its job: who the respondents must be, as filters on the population, and what the study assumes
about them.**

V2: `AudienceArt` (`prototypes/research-lead-v2/src/artifacts/SampleStages.tsx:157-204`).
- §1 Definice.
- §2 Filtry populace: a table of factor, value and "Odpovídá v populaci", with the note "LIVE v17_4_0
  · náhled jen počty". "Vlastní a speciální panely" is marked Unavailable (`:171-177`).
- §3 Předpoklady o cílové skupině. Each assumption has a status chip and evidence lines labelled
  "Externí výzkum" or "Znalost klienta", with passage and locator (`:178-201`). The caption reads
  "Externí evidence je kontext pro návrh, ne měření u respondentů".
- Contract `CONTRACTS.audience` (`fixture.ts:408`): the preview returns counts only; an external
  finding never changes an assumption by itself.

## 2. What exists today

- `AudienceStep` (`AudienceStep.tsx:116`):
  - `FilterEditor` (`:265`, `#aud-filters`) with the AI start "Navrhnout" (`:302`, `runJob("audiencePropose")`
    `:278`);
  - `LiveFilters` (`:331`), `FactorEditor` (`:370`), `Preview` (`:419`) and `Subpanels` (`:455`);
  - `DiscoverEditor` (`:481`) and `Summary` (`:504`).
- Routes: `GET /population/audience-catalogue` (`routers/population.py:480`) and
  `POST /population/audience-preview` (`:604`). The preview answers the combined selection only:
  `selected_rows`, `selected_donors` and the sample verdict (`domain/population/audience_preview.py:40-80`).
- No Lead target: no `data-aia` id on the research screens (G11 of the chain plan); `FOCUS_ID` takes
  only `question|section|brief|plan` (`domain/research_lead.py:205`).

## 3. Gaps

| # | Gap | Kind |
|---|---|---|
| A-1 | Definice: the audience description as an item | data exists |
| A-2 | Filter table with factor, value and source version | data exists (catalogue) |
| A-3 | "Odpovídá v populaci" per filter: the preview gives only the combined count | needs a new API (AUD3) |
| A-4 | Assumptions with attached evidence (`assumptions-and-open-answer-coding#AOC1`, `#AOC2`, with its ADR) | needs a new API (owned there) |
| A-5 | Own and special panels: "V AIA zatím není", as today (`NotInAia`, `:78`) | data exists (refusal text) |
| A-6 | The Lead's targets on this screen (G11, chunk 16) | needs a new API (the target grammar) |
| A-7 | The audience edit operation (`audience_set`, declared, `working-copy-edit-ops#WCE10`) | needs a new API (owned there) |
| A-8 | The report receives only `source_mode`, `strategy` and `has_filters` (`research_design.py:910-914`, G4 of the chain plan) | needs a new API (`artifact-chain-to-draft-report#CHN5`) |

## 4. The Lead on this artifact

- **View operations:** `open_stage(audience)`, `focus(target)`, `show_changes`, and
  `open_source(evidence id)` (V2's "open source").
- **Pointing:** `audience:definition`, `audience:filter:<factor>`, `audience:subpanel:<id>` and
  `assumption:<id>`. `data-aia` is `audience.flt.<id>` and `audience.ass.<id>.evidence.<src>`, as in V2
  (`SampleStages.tsx:174, 188`).
- **Edit operations:** none is text. `audience_set` (description and filters) and `assumption_*` are
  structure; a filter change changes who is drawn.
- **Workers:** `propose_audience` (a proposal card, `workers.json:8`). Evidence for an assumption
  comes from Design Research findings on its linked RQ (AOC2, `lead-orchestration#LO5a.1`), never from
  a new engine subject (`research-lead-workbench#25` stays after the MVP).
- **Inline proposals:** an audience proposal's filters as change rows in the table; an assumption's
  attached evidence as a proposal a person accepts.

## 5. Inputs and outputs

- **Reads:** the Brief and Návrh (LO9d); LIVE's kept catalogue; the study's client's materialized
  children.
- **Hands on:** `audience` (description, filters, source mode) as typed design fields.
  - The run's selection (`SpecSelection`, `selection_receipt`) receives the filters and fieldwork
    applies them (panel path).
  - The report receives three flags only (A-8); its method chapter (`ch-method`) prints the filters applied as the
    run recorded them (`report_method.py:398`).
  - Assumptions go to the report's assumptions chapter (`report-delivery#RD9`).

## 6. Input interactions

- B5-B11: where from and which population, numeric factor ranges, categorical values, categories and
  search, the subpanel, the description to AI, discover.
- Primitives: `RadioCard`, `Stepper` (bounded ranges), `ChoiceChips` with counts, a combobox and
  `InlineText`.

## 7. Chunks

**AUD1. Contract.** `lib/artifacts/audience.ts`, and the target kinds added to `FOCUS_ID`. Test: the
server refuses an `audience:filter:` target naming no catalogue factor. Depends on
`research-lead-workbench#14`, `#16`.

**AUD2. Body.** Tests: `AudienceStep.test.tsx`: the table lists the saved filters with the catalogue
version; a missing preview says why. Depends on `input-interactions#5`.

**AUD3. Per-filter counts.**
- `audience_preview` adds `per_filter: {factor: selected_rows}`: each filter alone over the same
  population, counts only.
- Tests: domain test against `select_audience` on the fictional population; the API stays 503 without
  `AIA_POPULATION_ASSET_ROOT`.

**AUD4. Assumptions.** Test: external evidence is labelled and never changes a status without a
person's accept. Depends on `assumptions-and-open-answer-coding#AOC1`, `#AOC2`.

**AUD5. The Lead on Cílová skupina.**
- `AudienceStep.tsx:302` is removed under `leadOwnsAiStarts`; the proposal shows inline.
- Test: the 26f guard.
- Depends on #550, `research-lead-workbench#7`, `#26f`, `working-copy-edit-ops#WCE10` and
  `lead-orchestration#LO5`.

**AUD6. Journey.**
- Steps in `tools/ui_workbench/audience_journey.mjs` at 1440, 1100, 768 and 390 px: a filter saved,
  its own count shown, the Lead focusing it.
- Zero paid jobs. 768 and 390 px depend on `research-lead-workbench#26b`-`#26d`.

## 8. Owner questions

None.

## Doc follow-up

- Register this plan and its chunks.
- `CLAUDE.md` § 2, `routers/population.py`: the preview's `per_filter` (AUD3).
