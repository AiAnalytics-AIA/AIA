---
status: in-progress
chunks:
  - "[x] SMP1. Vzorek's contract as data: view operations, pointable ids (size, quota cell, forecast item, readiness check) and V2's interaction contract"
  - "[x] SMP2. Velikost a složení: n, the dimensions and the audience summarized; the panel's quota cells before a run, and for the fictional roster the words that it has none"
  - "[x] SMP3. Odhad podpory před během: the support forecast and the question outlook, labelled a forecast, never a result"
  - "[x] SMP4. Připravenost ke spuštění: every readiness check with its stage link, on the working revision"
  - "[x] SMP5. Kdo bude odpovídat: the persona source offered, its default and why an unoffered one is not, read only here with a link to Spuštění, where it is chosen (SQ1 = Q54 b)"
  - "[x] SMP6. Journey: Vzorek at 1440, 1100, 768 and 390 px, zero paid jobs"
  - "[x] SMP2b. Složení: the composition table renamed and folded after six rows, link cards, the own dimension by name (reopens SMP2; spec vzorek V6; W1)"
  - "[x] SMP3b. §02 'Kolik dat bude za čísly': KPI tiles from the outlook; pair support disabled with its reason, 'ověří se až z dat' (reopens SMP3; spec vzorek V4; W1)"
  - "[ ] SMP4b. §03 readiness in words, one fix per check, the header pill, the budget row as a warning (reopens SMP4; spec vzorek V5; W1)"
  - "[x] SMP5b. §04 one line for the default source; 'Sběr dat' as the stage's one name (reopens SMP5; spec vzorek V7; W1)"
  - "[ ] SMP10. Readiness FAILs while the run's ceiling exceeds what is left of Rozpočet studie, the remedy raising the budget or lowering N (B1 (a), Nigel 2026-10-26; spec vzorek V5, OQ3; W1, on lead-orchestration LO23)"
  - "[ ] SMP6b. The Vzorek journey extended: N stepped and read back, the Lead's focus, zero paid (reopens SMP6; spec vzorek V8; W1)"
  - "[x] SMP7. N set on Vzorek: one stepper bounded by /research/limits, sample.edits true, set_n shown here; one PR with artifact-dimensions DIM3b (spec vzorek V1; Nigel P1, 26 Oct 2026; W1)"
  - "[ ] SMP8. The run's ceiling and the study's remainder beside N (spec vzorek V2; W1)"
  - "[ ] SMP9. The server's reportable_n and 'Zvýšit na N x · strop +Δ USD'; the browser's own recommendation removed (spec vzorek V3; W1)"
---
# Artifact: Vzorek (Sample)

Umbrella: `research-lead-workbench#19` (with Sběr dat). Chain:
[`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md). Anchors `@ 25f26232`;
prototype `@ 9b50963f`.

**The stage list.** The navigator has eleven stages (`apps/web/src/lib/workbench-stages.ts:16-19`,
equal to `prototypes/research-lead-v2/src/model/terms.ts:6`). "Kontrola" is not a stage of its own.
- V2's Sample is "persona (vzorek) + run (kontrola)" (`terms.ts:14`): Kontrola's readiness lives
  here.
- Sběr dat is "run + progress" (`terms.ts:15`): Spuštění's start and Průběh live in
  [`artifact-fieldwork.md`](artifact-fieldwork.md).

## 1. What it is, and its single job

**Its job: what will be drawn, how well it is expected to support the analysis, and whether the
study is ready to run.** It writes nothing of its own except n (`set_n`).

V2: `SampleArt` (`SampleStages.tsx:232-273`).
- §1 Velikost a složení: the quota cells table, the constraints, and "Velikost vzorku se v AIA
  nastavuje v kroku Dimenze".
- §2 Odhad podpory před během, with the aside "odhad, ne výsledek" and the caption "Kvóta ji
  nezaručuje".
- §3 Připravenost ke spuštění: each check with its glyph and a link to its stage, and "Pokračovat na
  Sběr dat". Warnings may continue (ADR 0025).
- §4 Kdo bude odpovídat: the persona source radios, the panel shown as not offered with its reason.
- Contract `CONTRACTS.sample` (`fixture.ts:410`): quota does not guarantee pair support.

## 2. What exists today

- `SampleView` (`apps/web/src/components/workbench/SampleView.tsx:13`, 41 lines): n, the chosen
  dimensions and the recommendation, read only, with links. It is mounted by the workbench
  (`Workbench.tsx:475`).
- Kontrola's content is on Spuštění (`RunStep`, `ExecutionSteps.tsx:589`):
  - `AnswerabilityGate` (`:798`), `ResearchTraceCard` (`:809`) and `QuestionOutlookCard` (`:816`);
  - `CostCard` (`:818`), `RespondentChoice` (`:820`, `:911`) and `PopulationChoice` (`:827`, `:869`);
  - `fixStep` maps a check to its stage (`:373`).
- Route: `GET /research/readiness` (`routers/research.py:1131`): checks, `support_forecast`,
  `question_outlook`, `research_trace`, `persona_sources` and the cost ceiling. `/research/limits`
  (`:1115`).

## 3. Gaps

| # | Gap | Kind |
|---|---|---|
| S-1 | Quota cells before a run for the panel path (`domain/population/sampling.py`, not served) | needs a new API (`run-qc-and-checkpoint#RQC6`) |
| S-2 | The fictional roster has no quotas: said in words | data exists |
| S-3 | Forecast and outlook (`support_forecast`, `question_outlook`) | data exists |
| S-4 | Readiness on the working revision, not only on a submitted Design Revision (`working-copy-edit-ops#WCE7`) | needs a new API (owned there) |
| S-5 | Persona source: offered, its default and reasons (`persona_sources`) | data exists; placed on Spuštění, read only here (SQ1 = Q54 b) |
| S-6 | The Lead's targets on this screen (G11) | needs a new API (the target grammar) |

## 4. The Lead on this artifact

- **View operations:** `open_stage(sample)`, `focus(target)` and `open_check(check id)`, which opens
  the stage a check names (V2's "open readiness item").
- **Pointing:** `sample:n`, `sample:quota:<cell>`, `sample:forecast:<item>` and `sample:ready:<check
  id>` (V2's `data-aia` `sample.ready.<id>`, `SampleStages.tsx:254`).
- **Edit operations:** `set_n` (structure). Nothing else is written here.
- **Workers:** none. Readiness and the forecast are deterministic: the Lead reads them (a lookup,
  no cost) and cannot override a FAIL (`docs/boundary-matrix.md`).
- **Inline proposals:** none; a proposal from another stage shows its effect on readiness after
  WCE7.

## 5. Inputs and outputs

- **Reads:** Dimenze (n, dimensions), Cílová skupina (filters), Dotazník (items for the outlook) and
  Návrh (the trace).
- **Hands on:**
  - the readiness the start reads;
  - the persona source chosen, a start argument (`research.start`, `ExecutionSteps.tsx:715`);
  - at start, the run's metadata records the gaps, answerability and the forecast. The report prints
    them in "Respondenti a výpočet" (`report_method.py:176`, `:449`). The research trace is recorded
    at start for the research-questions chapter (`ch-2`; `artifact-chain-to-draft-report#CHN3`).

## 6. Input interactions

- B12 (persona source), B13 (the run's population) and B15 (continue with limits).
- Primitives: `RadioCard` and `InlineText` for the reason (B15).

## 7. Chunks

**SMP1. Contract.** `lib/artifacts/sample.ts`. Depends on `research-lead-workbench#14`, `#16`.

**SMP2. Size and composition.**
- Tests: `SampleView.test.tsx`: the roster reads "fiktivní soupis nemá kvóty"; a panel run's cells
  come from the API.
- Depends on `run-qc-and-checkpoint#RQC6` for panel cells.
- Delivered with RQC6c: `lib/sample-view.ts` `compositionOf` (roster, drawn, refused, unknown);
  §1's "Složení podle kvót" lists the cells with respondents, largest first, each `sample:quota:<key>`,
  ten shown and the rest under a `details` element; the roster reads "Fiktivní respondenti se
  nevybírají podle kvót."; a refusal in the audience step's words (`PREVIEW_REASONS`). SMP3's
  forecast now reads a panel run known when the server drew its sample. Tests
  `sample-view.test.ts` (`compositionOf`, the panel forecast) and `SampleView.test.tsx`
  ("Složení podle kvót").

**SMP3. Forecast.** Test: an unknown forecast for a panel run reads "neznámé", never good.

**SMP4. Readiness.**
- Each check with its stage link; this moves Kontrola's read-only cards here from Spuštění, which
  keeps the start (`artifact-fieldwork#FLD6`).
- Test: a FAIL names its stage.
- Depends on `working-copy-edit-ops#WCE7`.

**SMP5. Kdo bude odpovídat.** SQ1 = Q54 (b): the choice stays on Spuštění, beside the start that pins
it (`artifact-fieldwork`); Vzorek shows the offered sources, the default and why an unoffered one is
not, read only, with a link to Spuštění. No new stored field. Test: Vzorek has no control that sets
the source, names an unoffered one with its reason, and its link opens Spuštění.

**SMP6. Journey** at 1440, 1100, 768 and 390 px: the readiness list, a check opening its stage;
zero paid jobs. 768 and 390 px depend on `research-lead-workbench#26b`-`#26d`.

## 8. Owner questions

**SQ1. Where is the persona source chosen?** **Settled 2026-10-21 via /pmstatus Q54: (b).**
V2 draws the choice in Vzorek §4. The plan's D2 makes Vzorek a read-only projection, and today the
choice is a start argument on Spuštění (`ExecutionSteps.tsx:820`).
- (a) In Vzorek, as V2 draws it. The choice is stored in the working copy as a design field (Class
  B), so the Lead can propose it and Spuštění reads it. It needs a new field and an edit operation.
- (b) On Spuštění, beside the start that pins it. Vzorek shows the default and the offer read only,
  with a link.

**Recommendation: (b).** The source is pinned by the start and belongs beside it; no new stored
field. (a) if the owner wants V2's layout exactly.

## Decisions taken while building

- **WCE7b (2026-10-22): readiness is read on the working revision.** The decision below held until
  `GET …/research/readiness/working` (#616); Vzorek now reads that and submits nothing.
- **SMP3 (2026-10-21): readiness is read on a Design Revision until WCE7.** Vzorek reads
  `GET /research/readiness` as Spuštění does (`ExecutionSteps.tsx:650-669 @ 871c62c5`): an editor's
  working copy is saved and submitted (source stage `persona`; an unchanged copy answers its existing
  revision, `study_design_repository.py` `submit`), a reader's is the latest revision. When
  `working-copy-edit-ops#WCE7` serves readiness on a working revision, `useSampleReadiness.ts`
  reads that and submits nothing. Test: `SampleView.test.tsx` "loadSampleReadiness".
- **SMP3: a panel run's forecast is unknown by the domain's rule**, not by the web's reading of
  words: `forecast_support` cannot count a population draw's donors (`support_forecast.py:170-181
  @ 871c62c5`), so `supportForecastOf` reads `persona_source: "panel"` (or no `support_forecast`
  check) as "neznámé". A structured forecast on the readiness response would remove the rule's
  copy; not needed for SMP3.

- **SMP6, first part (2026-10-21):** `workbench_journey.mjs` opens Vzorek at 1440, 1100, 768 and
  390 px: the size and the server's forecast, read only, every `sample:` id present, no overflow,
  Spuštění one click away, nothing paid. The readiness list and a check opening its stage join it
  with SMP4; the chunk stays open until then.

- **SMP6, done (2026-10-22, with RQC6d):** `sample_panel_journey.mjs`, on
  `workbench.py up --fresh --population-double`: at 1440, 1100, 768 and 390 px "Složení podle kvót"
  shows every cell readiness drew as its `sample:quota:<key>` with the server's n (largest ten, the
  rest folded), the forecast known, nothing editable, no overflow; then a readiness check opens its
  stage; zero paid jobs.

- **SMP4 (2026-10-22).** Vzorek §3 lists every check the server ran on the working copy, worst
  first (an unknown status first, never counted as passed), each with the stage that fixes it
  (`sample-view.ts` `checkStage`, by id or, for `compile:<code>:<where>` and `battery_size:<set>`, by
  prefix; a check this client does not know names none) and its own target
  `sample:ready:<id>`; the aside follows the server's `ready` (false stops the run whatever the
  counts) and counts what blocks and what warns; "Pokračovat na Sběr dat" goes on,
  "Lze pokračovat s omezeními" when only warnings. The support forecast is shown in §2 alone, counted
  here and named when it warns. Kontrola's cards stay on Spuštění until `artifact-fieldwork#FLD6`
  decides; "Kdo bude odpovídat" is now §4, as V2 numbers it.

## Findings

- **F-SMP-1. Spuštění sends a failing `dimensions` or `sociomap_support` check to Dotazník.**
  - Anchor: `apps/web/src/components/rehome/research/ExecutionSteps.tsx:381-385 @ bfe6d15b` (`fixStep`:
    `/sample|^n$|^support_forecast$/` → persona, `/audience/` → audience, the rest → questionnaire).
  - Reproduction: `fixStep("dimensions")` and `fixStep("sociomap_support")` return `"questionnaire"`;
    the checks are `research_design.py:1250-1276 @ bfe6d15b` (n below the pair minimum; the selected
    dimensions).
  - Consequence: "Opravit →" on those checks opens the questionnaire, where neither is fixed.
  - Smallest fix: map both to `persona`, as Vzorek's `checkStage` does.
  - Test: `fixStep` for each check id the domain emits. Reported to the Sběr dat session (its file).
- **F-SMP-2. The readiness messages Vzorek shows disagree with their numbers in Czech** (found by the
  Vzorek browser audit, 2026-10-22, at 1440/1100/768/390 px on every workbench fixture).
  - Anchor: `packages/aia_core/src/aia_core/domain/research_design.py:1205 and :1242 @ fe85aa54`.
  - Reproduction: a design with 1 question and 1 tracked set reads "1 otázek, 1 sledovaných sad (6
    položek k zodpovězení)." and "1 sad pro Sociomapu.".
  - Consequence: every Vzorek, Spuštění and Kontrola readiness list shows broken Czech.
  - Fix: `report.numbers.counted` for each count, on this PR.
  - Test: `test_research_design.py::test_readiness_counts_agree_with_their_number_in_czech`.

## Doc follow-up

- Register this plan and its chunks.
- CLAUDE.md §2, `SampleView`: "Vzorek, read only: §1 size and composition with links to where they
  are set, §2 the server's forecast and question outlook, §3 every readiness check on the working
  copy with the stage that fixes it (`lib/sample-view.ts` `checkStage`), §4 who will answer; read
  through useSampleReadiness on the working revision".
- open-items: F-SMP-1 (Spuštění's `fixStep` misroutes `dimensions` and `sociomap_support`; the Sběr
  dat session is fixing it in artifact-fieldwork).

## From the research build spec (2026-10-26)

Source: the research build spec (https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy), checked chunk by chunk against this plan's front-matter at
develop `bd0d1ad6` in the research chunk register (26 Oct 2026); waves recorded in
`.planning/mvp-execution-contracts.md`. Lane and order: [`prototype-build.md`](prototype-build.md).
A spec id carries its section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`), because the
ids repeat across sections. A ticked chunk the spec reopens is never unticked: its rework is a
follow-up chunk below.

**SMP2b. Composition** (spec `vzorek/V6`; reopens SMP2; W1, lane E).

**SMP3b. Kolik dat bude za čísly** (spec `vzorek/V4`; reopens SMP3; W1, lane E). Decided by default (planning, open to Nigel's override): the brand pair is disabled with its reason (R9), no pair forecast (OQ4).

**SMP4b. Readiness in words** (spec `vzorek/V5`; reopens SMP4; W1, lane E). On `research-lead-workbench#36`. B1 decided (a) (Nigel, 26 Oct 2026 01:21-01:24 UTC on the plan page, relayed by the PM coordinator): the study budget stops a run before it starts, "as drawn"; the budget row reads as the FAIL check SMP10 serves, its remedy raising the budget or lowering N.

**SMP5b. Kdo bude odpovídat, one line** (spec `vzorek/V7`; reopens SMP5; W1, lane E).

**SMP10. The budget stops a run** (spec `vzorek/V5`, OQ3; W1, lane E). B1 (a), Nigel, 26 Oct 2026 01:21-01:24 UTC on the plan page, relayed by the PM coordinator: the study budget stops a run before it starts, "as drawn". A readiness check FAILs while the run's ceiling exceeds what is left of Rozpočet studie; its remedy is raising the budget or lowering N. Today the start never consults the budget (register OQ3). Needs the ceiling before a start, `lead-orchestration#LO23` (W1). An unknown ceiling is not a pass. Test: a design whose ceiling exceeds the remainder is not ready, and raising the budget makes it ready.

**SMP6b. Journey** (spec `vzorek/V8`; reopens SMP6; W1, lane E). After SMP7-SMP9.

**SMP7. N on Vzorek** (spec `vzorek/V1`; W1, lane E). Nigel, 26 Oct 2026 (P1): N is set on Vzorek, "this stage has to do with setting up the AI respondents". One PR with `artifact-dimensions#DIM3b`, so N is never on neither stage. The contract's `sample.edits` becomes true and `set_n` is shown here. Bounds from `/research/limits` (server 20-10 000; register contradiction 14 with `input-interactions#5`'s 50-5000), never clamped. Test: a refused n saves nothing; Dimenze has no n control. Done with DIM3b: §01's "Velikost vzorku" is the stepper (`SampleSize.tsx`,
the one Dimenze used, bounded by `/research/limits`, a refused n saved nothing), "Upravit v Dimenzích" gone;
`ARTIFACTS.sample.edits` true (`domain/lead_artifacts.py`, `lib/workbench-artifacts.ts`, the contract
fixture) and the Lead's `set_n` shown on Vzorek (`lib/lead.ts` editStage); `ARTIFACTS.dimensions.edits`
stays true (WCE10's `dimensions_set`). The browser's recommendation stays beside N until SMP9. Tests:
"sets n on Vzorek…" (ResearchScreen.workbench), `lead.test.ts` (set_n → sample), `workbench_journey.mjs`
and `dimensions_journey.mjs` (n stepped on Vzorek, 44 px at 390).

**SMP8. Ceiling beside N** (spec `vzorek/V2`; W1, lane E). Unknown never zero.

**SMP9. Reportable n** (spec `vzorek/V3`; partly no backend; W1, lane E). A readiness `?n=` ceiling query is new. Replaces DIM3's browser recommendation (contradiction 16).

**Notes.**
- The plan was `done`; it is `in-progress` again because the spec adds open chunks (26 Oct 2026).
