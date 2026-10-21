---
status: in-progress
chunks:
  - "[x] SMP1. Vzorek's contract as data: view operations, pointable ids (size, quota cell, forecast item, readiness check) and V2's interaction contract"
  - "[ ] SMP2. Velikost a složení: n, the dimensions and the audience summarized; the panel's quota cells before a run, and for the fictional roster the words that it has none"
  - "[x] SMP3. Odhad podpory před během: the support forecast and the question outlook, labelled a forecast, never a result"
  - "[ ] SMP4. Připravenost ke spuštění: every readiness check with its stage link, on the working revision"
  - "[x] SMP5. Kdo bude odpovídat: the persona source offered, its default and why an unoffered one is not, read only here with a link to Spuštění, where it is chosen (SQ1 = Q54 b)"
  - "[ ] SMP6. Journey: Vzorek at 1440, 1100, 768 and 390 px, zero paid jobs"
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

## Doc follow-up

- Register this plan and its chunks.
