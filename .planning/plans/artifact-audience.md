---
status: in-progress
chunks:
  - "[x] AUD1. Cílová skupina's contract as data: view operations, pointable ids (definition, filters, filter, subpanel, preview; assumption arrives with AUD4) and V2's interaction contract; the first Lead targets this screen has"
  - "[ ] AUD2. The body as V2 draws it: Definice, Filtry populace as a table of factor, value and count, the LIVE version named, counts only"
  - "[x] AUD3. Each filter's own count: the audience preview answers a per-filter count beside the combined one, still counts only"
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
- Delivered: B6, a numeric factor's range as two bounded steppers (feature/audience-range-steppers);
  the record of each row is input-interactions.md § Chunk 5, as delivered.
- Delivered: B7+B8, factor groups and values as chips (feature/audience-value-chips); the record of
  each row is input-interactions.md § Chunk 5, as delivered.
- Delivered: B9, the built-in subpanels under a search (feature/audience-subpanel-list);
  the record of each row is input-interactions.md § Chunk 5, as delivered.
- Delivered: B11, Discover's product and success criterion edited in place (feature/audience-discover-inline);
  the record of each row is input-interactions.md § Chunk 5, as delivered.

## 7. Chunks

**AUD1. Contract.** `lib/artifacts/audience.ts`, and the target kinds added to `FOCUS_ID`.
- Web: the screen marks exactly `audienceTargets` (its parts, each stored filter on its chip, each
  offered subpanel), and `audienceTarget` refuses a part, a filter or a subpanel it does not name.
- Server (the integration coordinator's, `domain/research_lead.py`, merged in #624): an `audience:filter:` focus must
  name a filter stored in the working copy the turn froze, or the current copy for a person's message
  focus; an `audience:subpanel:` focus a built-in subpanel; no catalogue read in the domain (#624: `target_refusal`,
  `audience_filter_not_stored`, `audience_subpanel_unknown`). Test: the server refuses an
  `audience:filter:` target naming no stored filter
  (`test_an_audience_target_names_what_the_working_copy_stores`).
- Depends on `research-lead-workbench#14`, `#16`.

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

## Findings

From the browser audit of 2026-10-21 (workbench on develop `bfe6d15b`, the `audience` fixture,
1440/1100/768/390 px, zero paid jobs). Each is fixed on `fix/audience-copy-and-tap-targets`.

- **F1. The copy names the old product and promises what AIA lacks.**
  - Anchor: `apps/web/src/i18n/cs.ts:2276-2300 @ bfe6d15b`. "Vlastní audience" says an uploaded
    dataset will run like the panel, though choosing it shows "V AIA zatím není". "Audience AI
    Analytics" says "databázi NPC Panelu". "COMING SOON", "Special Audience" and "Nejdřív široký run,
    potom outcome-based segment" are untranslated.
  - Reproduce: open Cílová skupina at any width.
  - Fix: the copy states what AIA does, in Czech. The discover advice no longer says "systém najde
    profil lidí, kteří over-indexují". "Audience AI Analytics" stays; renaming it is the owner's call.
  - Test: `apps/web/src/i18n/audience-copy.test.ts`; the journeys select "Speciální skupiny".
- **F2. A filter chip's remove button is a 15 x 16 px target.**
  - Anchor: `apps/web/src/components/rehome/research/AudienceStep.tsx:337 @ bfe6d15b`, under WCAG
    2.5.8's 24 px.
  - Reproduce: the audit at 390 px measures the "×".
  - Fix: `size-6`.
  - Test: `workbench_journey.mjs` asserts every "Odebrat filtr" button is at least 24 x 24 at all four
    widths.
- **F3. A stored filter the population cannot honour looks like any other until a preview or a run.**
  - Anchor: `apps/web/src/research/audience.ts:340 @ bfe6d15b` (filterChips, no check) with
    `packages/aia_core/src/aia_core/domain/population/audience.py:433 @ bfe6d15b` (a value the panel
    lacks is dropped silently when another remains; all lacking refuses the filter).
  - Reproduce: the `audience` fixture stores `kraj: ["Fiktivní kraj A"]`, which the workbench's
    population does not hold; its chip read as valid.
  - Consequence: the preview, or a run that draws respondents from the population, narrows the
    audience or refuses it whole without the screen saying so beforehand.
  - Fix: `filterProblems` gives a reason for each filter it can prove cannot apply:
    - `factor`: the catalogue does not offer the factor;
    - `policy`: the factor's `policy_allowed` is false;
    - `empty`: no value is stored;
    - `range`: a numeric filter `_interval` refuses (a null or non-numeric bound, a list that is not
      a pair, text), held to the server's rule case by case;
    - `values`: text values a complete value list (shorter than its 60 listed values) lacks.
    The chip says "nelze použít", or "některé hodnoty chybí" when the filter still applies with the
    rest, and takes the attention style; a note says what the selection does. A cut list, a number
    and a boolean value say nothing.
  - Test: `audience.live.test.ts` "stored filters the population cannot honour";
    `AudienceStep.test.tsx` "says at once which stored filter…".
- **Note on history (not a defect in the code).** The develop merge `91e06c1f` lacks #694's readiness
  and start-button waits in `ExecutionSteps.test.tsx`. The cause: an unstage, made to split out
  #728's port, took this branch's copy. The next commit, `816fb230`, restores them; from there the
  file differs from develop `db44f5f3` only in `closeWhere`. No head this PR ships loses the test.

- **OI-51, fixed by the product owner's answer (a), 2026-10-25.** A preset change kept the previous
  audience's subpanel and filters, as 18.6.6 did. On the screen: "Vlastní publikum" and ČR připravujeme
  kept both, and Speciální skupiny kept the filters; ČR 18+ already cleared them. `chooseSpecialPreset`
  (the classic's port, not on the screen) kept them too.
  - Anchor: `apps/web/src/research/audience.ts:94` (`setAnalyticsChoice`) and `:161`
    (`chooseSpecialPreset`) @ f7762d72; `setAudienceEntry` above them.
  - Fix: `presetReset`, used by every preset path, clears the subpanel, filters and segment (OI-51's
    smallest fix). A change that cleared something invalidates the run check. The parity tests compare
    the rest with the classic run on the reset audience.
  - Tests: `AudienceStep.test.tsx` "switching preset clears the previous subpanel and filters";
    `audience.live.test.ts` "what a preset change clears"; `audience.parity.test.ts` setAudienceEntry,
    setAnalyticsChoice and the preset-after-preset cases; the audience journey's step 3.
  - The description stays as it is on a preset change (the product owner, 2026-10-25).
  - Follow-up, fix/audience-preset-clears-strategy (the product owner, 2026-10-25, "Clear both"):
    `presetReset` also resets the strategy to "population" and the subpanel's support figures
    (`support_tier`, `subpanel_status`, `support_summary`) to the template's defaults. A special
    panel's keys (`special_panel_key`, `builtin_special_key`) follow the same rule, since they are the
    same kind of stale write. On the classic's port (`chooseSpecialPreset`, which no screen calls) a
    coming-soon preset after a special panel is then no longer "ready". On ČR 18+ the description
    also stays: the classic's `chooseAudience('population')` wrote "ČR 18+" there. Only a change
    of who is sampled invalidates the run check, not the support figures alone. The new preset writes
    its own figures when it has any.
  - A strategy change (not a preset change) keeps a subpanel's support figures as they are (the product
    owner, 2026-10-26: "leave the strategy question as is").
  - A preset's `dataset_name` (shown as "Zdroj audience") stays as it is on ČR připravujeme (the product
    owner, 2026-10-26: "leave the dataset name as is"). No OI-51 question is left open.
  - Tests:
    `AudienceStep.test.tsx` "switching to one's own audience clears the subpanel's strategy and support
    too…"; `audience.live.test.ts` "what a preset change clears"; the audience journey's step 3.

## 8. Owner questions

None.

## Doc follow-up

- Register this plan and its chunks.
- `CLAUDE.md` § 2, `routers/population.py`: the preview's `per_filter` (AUD3).
