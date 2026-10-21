---
status: in-progress
chunks:
  - "[ ] FLD1. Sběr dat's contract as data: view operations, pointable ids (run, step, cost line, quality flag) and V2's interaction contract"
  - "[x] FLD2. The run head and its steps as V2 draws them: done over target, status in words, each step marked deterministic or worker, from the run's steps"
  - "[ ] FLD3. Progress from the fieldwork event contract and the per-respondent checkpoint: answered respondents, blocks in flight, waits and parks in words"
  - "[ ] FLD4. Náklady: spent, reserved, the run's ceiling and the study's remainder, and who spent it"
  - "[ ] FLD5. Kvalita a zásah: the run's QC warnings and straight-liner flags, keep or flag; replacement shown unavailable until its method is set"
  - "[ ] FLD6. Spuštění: the Start stays with its gates and one spend dialog; the run also a Lead card; retries, resume and budget lift through the Lead's cards or a person's own gate"
  - "[ ] FLD7. Kdo odpovídal: the receipt, source, population recorded and read, dimensions passed, the data's origin"
  - "[ ] FLD8. Journey: Sběr dat at 1440, 1100, 768 and 390 px on fictional fieldwork, zero paid jobs"
---
# Artifact: Sběr dat (Fieldwork: Spuštění and Průběh)

Umbrella: `research-lead-workbench#19` (with Vzorek). Chain:
[`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md). Anchors `@ 25f26232`;
prototype `@ 9b50963f`. Sběr dat is "run + progress" (`terms.ts:15`); Kontrola's readiness is
Vzorek's (`artifact-sample.md`).

## 1. What it is, and its single job

**Its job: run the frozen design and show, truthfully, what the run is doing and what it costs.**

V2: `FieldworkArt` (`EvidenceStages.tsx:27-90`).
- §1 Běh, with "zmrazí revizi N": done over target, a bar and the status in words.
- §1's actions: start through the decision card in the conversation; Zrušit běh; Zkusit krok znovu;
  Navýšit limit; Spustit znovu.
- The seven steps, each tagged "deterministické" or worker (`:17-25`).
- §2 Náklady: spent, reserved, the run's ceiling under the confirmation limit, and the study's
  remainder.
- §3 Kvalita a zásah: constant responders and the attention check. Replacement is "proposed" and
  unavailable.
- §4 Kdo odpovídal: source, population recorded and not read, dimensions passed, data origin.
- Contract `CONTRACTS.fieldwork` (`fixture.ts:411`): the run freezes the revision; only a person
  goes above the limit.

## 2. What exists today

- `RunStep` (`ExecutionSteps.tsx:589`), Spuštění: the cards listed in `artifact-sample.md` §2, and
  "Spustit výzkum" (`:858`, `research.start` `:715, :731`). **It stays** (D15, 2026-10-21). Below it
  is `RunList` (`:940`).
- `ProgressStep` (`:1184`), Průběh:
  - `StepActivityPanel` per running step (`:1295`) and `RespondentsReceipt` (`:1228`, `:186`);
  - `ProgressActions` (`:1097`, `#run-actions`) and `AnalysisRepair` (`:1059`, retries `:1077-1089`).
- Routes (`routers/research.py`):
  - `POST /research/runs` (`:1240`), `GET …/{run_id}` (`:1325`) and `…/events` (`:1335`);
  - `…/cancel` (`:1367`), `…/budget` (`:1396`) and `…/steps/{node_key}/budget` (`:1432`);
  - `…/resume` (`:1500`) and `…/retry` (`:1532`).
- `lib/budget-line.ts`, `lib/run-state.ts`, `lib/step-activity.ts`.

## 3. Gaps

| # | Gap | Kind |
|---|---|---|
| F-1 | Steps tagged deterministic or worker (from step kinds; `lib/activity-orb.ts` already knows which hold a model) | data exists |
| F-2 | Done over target, per respondent: the fieldwork event contract (`run-qc-and-checkpoint#RQC7`) and the checkpoint (`#RQC0`) | needs a new API (owned there) |
| F-3 | Per-run spent and reserved beside the ceiling and the study's remainder; the wallet (`lead-orchestration#LO1`, done) and who spent (`develop-spend-attribution#7`, per-researcher spend, Q40) | needs a new API (per-run spend; owned there for the actor) |
| F-4 | QC warnings (`evidence-integrity#2`, `#3`), straight-liner flags and keep / flag (`run-qc-and-checkpoint#RQC1`, `#RQC4`) | needs a new API (owned there) |
| F-5 | Replacement as a new linked run (`run-qc-and-checkpoint#RQC5`); weights and support are MVPQ-10 (open) | needs an owner decision (MVPQ-10, recorded) |
| F-6 | The run as a Lead card beside Start (#550, `research-lead-workbench#23`); typed start (`lead-orchestration#LO5`); plan step (`#LO4`) | needs a new API (owned there) |
| F-7 | One spend dialog for start, retry and lift (audit B16-B20, `input-interactions#6`) | data exists |
| F-8 | Receipt (`respondentReceipt`) | data exists |

## 4. The Lead on this artifact

- **View operations:** `open_stage(fieldwork)`, `focus(target)` and `open_step(node key)`, which
  opens the step's activity panel.
- **Pointing:** `fieldwork:run`, `fieldwork:step:<node key>`, `fieldwork:cost`,
  `fieldwork:quality:<flag id>` and `fieldwork:receipt`. `data-aia` is `fieldwork.step.<id>`
  (`EvidenceStages.tsx:63`).
- **Edit operations:** none. A run is frozen; nothing the Lead says changes it.
- **Workers and cards:**
  - the research-run card: Start's twin, approved on Spuštění's own route (D7);
  - the budget-lift card (a person's `APPROVE_BUDGET`);
  - the straight-liner check (`lead-orchestration#LO9b`): a proposal to keep or flag;
  - the continuation turn (`lead-orchestration#LO6`), which returns a finished step to the Lead.
- **Inline proposals:** keep / flag on the quality section.

## 5. Inputs and outputs

- **Reads:** a Design Revision (frozen), the persona source and population pins, the readiness
  acknowledgement and the study's budget and wallet.
- **Hands on.** In the run's metadata:
  - typed fields: population binding, `persona_source`, the selection receipt, pinned Sociomap
    methods and gaps;
  - the dataset artifact (id + SHA-256);
  - the aggregate and Sociomap artifacts (id + SHA-256);
  - ledger refs (spend confirmation, `chat_start`, `lead_job_request`).

  The report reads the metadata in "Respondenti a výpočet" (`report_method.py:449`) and the dataset
  through the analysis evidence. QC flags and spend reach no report section today; QC warnings
  enter "Metodika a způsob interpretace" in `artifact-chain-to-draft-report#CHN9`.

## 6. Input interactions

- B14 (spend limit), B16 (Spustit výzkum), B17 (retries), B18-B19 (cancels), B20 (budget lift),
  B25 (job panel non-modal).
- Primitives: `SpendDialog`, `InlineConfirm`, `Switch` and a money `Stepper`.

## 7. Chunks

**FLD1. Contract.** `lib/artifacts/fieldwork.ts`. Depends on `research-lead-workbench#14`, `#16`.

**FLD2. Run head and steps.** Test: `ExecutionSteps.test.tsx`: a model step reads "AI", aggregate
reads "deterministické"; an unknown state reads UNKNOWN (`run-state.ts`).

**FLD3. Progress.**
- Test: counts only as reported (`step-activity.ts`), never a percentage guessed.
- Depends on `run-qc-and-checkpoint#RQC7`, `#RQC0`.

**FLD4. Náklady.**
- API: the run answers `spent_usd` and `reserved_usd` from the ledger and holds (unknown never
  zero). The actor comes from `develop-spend-attribution#7`.
- Test: a run with an uncertain call shows it apart.
- Depends on `lead-orchestration#LO1`.

**FLD5. Kvalita a zásah.** Test: a straight-liner flag is a warning, never a gate. Depends on
`evidence-integrity#3`, `run-qc-and-checkpoint#RQC4`, and MVPQ-10 for replacement.

**FLD6. Spuštění.**
- Start stays (`ExecutionSteps.tsx:858`), behind `SpendDialog`. The run also appears as a Lead card.
- `AnalysisRepair`'s and `ProgressActions`' paid retries go to the Lead's cards or a typed start
  (`research-lead-workbench#26f`); resume and lift stay a person's own gates.
- Tests: the 26f guard (Start the only `AiButton`); a direct HTTP start meets the same gates (26e).
- Depends on #550, `lead-orchestration#LO5`, `input-interactions#6`.

**FLD7. Kdo odpovídal.** Test: a mismatch between the pinned source and the data's origin is named,
never resolved.

**FLD8. Journey.**
- Extends `tools/ui_workbench/research_journey.mjs` in the workbench at 1440, 1100, 768 and 390 px:
  - start through the button and see the run card;
  - the steps;
  - Kdo odpovídal.
- Zero paid jobs. 768 and 390 px depend on `research-lead-workbench#26b`-`#26d`.

## 8. Owner questions

None new (replacement is MVPQ-10, already open).

## Doc follow-up

- Register this plan and its chunks.
- `CLAUDE.md` § 2, `routers/research.py`: a run's `spent_usd` / `reserved_usd` (FLD4).
