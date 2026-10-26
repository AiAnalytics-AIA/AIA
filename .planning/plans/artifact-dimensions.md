---
status: in-progress
chunks:
  - "[x] DIM1. Dimenze's contract as data: view operations, pointable ids (dimension, sample size, own dimension) and V2's interaction contract"
  - "[ ] DIM2. Selected dimensions as V2 draws them: name, definition, source in the population, use, and the persona topic or 'bez tématu persony', from the server's mapping"
  - "[x] DIM3. The sample size as one bounded stepper with its recommendation, never silently clamped"
  - "[ ] DIM4. Vlastní dimenze klienta: a requested dimension materialized as the client's owned child, its outcome, and the run it feeds"
  - "[ ] DIM5. The Lead on Dimenze: suggest_dimensions as a card, its proposal inline, the stage's AI start removed"
  - "[ ] DIM6. Journey: Dimenze at 1440, 1100, 768 and 390 px, zero paid jobs"
---
# Artifact: Dimenze (Dimensions)

Umbrella: `research-lead-workbench#22` (with Cílová skupina). Chain:
[`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md). Anchors `@ 25f26232`;
prototype `@ 9b50963f`.

## 1. What it is, and its single job

**Its job: which characteristics of a respondent the persona carries, and how many respondents
there are.**

V2: `DimensionsArt` (`SampleStages.tsx:206-230`).
- §1 Vybrané dimenze, with the aside "politika pole rozhoduje o použití (decide)". Each row shows
  name, definition, source and use, and a chip "téma persony: …" or "bez tématu persony". The caption
  says an unmatched dimension is not passed on (`dimensions_unmatched`) and is named in "Kdo
  odpovídal".
- §2 Vlastní dimenze klienta, which is simulated in V2. The settled scope extends it: own dimensions
  materialize and feed a real consumer (current-disposition.md, Dimensions).
- V2's Vzorek says that the sample size is set here (`SampleStages.tsx:245`).
- Contract `CONTRACTS.dimensions` (`fixture.ts:409`).

## 2. What exists today

- `PersonaStep` (`PersonaStep.tsx:89`):
  - `DimensionGroup` (`:350`, `#per-chosen`) and the factors (`#per-factors`, `:327`);
  - the new-dimension request (`#per-new`, `:252`);
  - the sample size: slider and input (`SampleSlider` `:410`, `SampleInput` `:440`, `#per-sample`);
  - the AI start "Navrhnout" (`:219`, `runJob("personaSuggest")` `:126`).
- The topic mapping lives only in the domain (`domain/persona_topics.py`, `DIMENSION_TOPICS`); the
  run's `selection_receipt` names `dimensions_unmatched`.
- Materialization routes: `routers/materialize.py:215, 262, 278`. The run offers a child through
  `PopulationChoice` (`ExecutionSteps.tsx:869`).
- The valid n has one authority (`run-qc-and-checkpoint#RQC9`, done).

## 3. Gaps

| # | Gap | Kind |
|---|---|---|
| M-1 | The persona topic per dimension before a run: the mapping is not served | needs a new API (DIM2) |
| M-2 | Source and use per dimension (population characteristics, `GET /population/versions/{id}/characteristics`) | data exists |
| M-3 | n as one stepper (audit B1: three controls today, a silent clamp) | data exists |
| M-4 | Own dimensions: request, materialize, outcome and the run that uses them; what a descriptor is and its support stay MVPQ-03 (open) | data exists (routes); the web is new |
| M-5 | The Lead's targets on this screen (G11) | needs a new API (the target grammar) |
| M-6 | `dimensions_set` (declared, `working-copy-edit-ops#WCE10`) | needs a new API (owned there) |

## 4. The Lead on this artifact

- **View operations:** `open_stage(dimensions)`, `focus(target)` and `show_changes`.
- **Pointing:** `dimension:<id>`, `sample:n` and `own_dimension:<request id>`. `data-aia` is
  `dimensions.dim.<id>`.
- **Edit operations:** `dimensions_set` and `set_n`, both structure (`set_n` changes the sample).
- **Workers:** `suggest_dimensions` (a proposal card, `workers.json:9`). Materialization is
  deterministic and a person's start, not a worker.
- **Inline proposals:** the suggested dimensions as rows added or removed.

## 5. Inputs and outputs

- **Reads:** the Brief, Návrh and Cílová skupina (LO9d); the population's catalogue and field policy
  (`RuntimePopulation.decide`).
- **Hands on:**
  - `spec.selection.dimensions` (typed), which reaches the persona topic allowlist
    (`persona_allowlist`) and the receipt;
  - `n`, to the sampler and the cost ceiling;
  - a materialized child, by `population_version_id`, pinned on the run.

  The report's method chapter (`ch-method`) prints each dimension applied or not (`report_method.py:398`); the
  chain plan's manifest names it as that chapter's source (`artifact-chain-to-draft-report#CHN1`).

## 6. Input interactions

- B1 (n), B2-B3 (dimensions and search), B4 (own dimension).
- Primitives: `Stepper`, `ChoiceChips` in a searchable list and `InlineCreateRow`.

## 7. Chunks

**DIM1. Contract.** `lib/artifacts/dimensions.ts`. Depends on `research-lead-workbench#14`, `#16`.

**DIM2. Selected dimensions.**
- The readiness response (or the catalogue) answers each selected dimension's persona topic, or
  `null` with `dimension_unmatched`, from `dimension_topic`.
- Tests: an API test for ekologie → eko and an unmatched one; Vitest that the chip reads "bez tématu
  persony" for null.

**DIM3. The sample size.**
- Tests: `PersonaStep.test.tsx`: 5001 is refused at the field and not saved (I2); the recommendation
  is shown.
- Depends on `input-interactions#5`.

**DIM4. Own dimensions.**
- The request, the run's state and the child's outcome (target beside achieved, `lib/population.ts`
  `targetVerdict`), and a link to "Populace běhu" on Sběr dat.
- Test: an unknown target reads as not met.
- Depends on `client-knowledge-lifecycle#K5` for the definition contract, and on MVPQ-03 for
  descriptors.

**DIM5. The Lead on Dimenze.**
- `PersonaStep.tsx:219` is removed under `leadOwnsAiStarts`.
- Test: the 26f guard.
- Depends on #550, `research-lead-workbench#7`, `#26f`, `working-copy-edit-ops#WCE10` and
  `lead-orchestration#LO5`.

**DIM6. Journey** at 1440, 1100, 768 and 390 px: a dimension chosen, n stepped, the Lead focusing
`dimension:<id>`; zero paid jobs. 768 and 390 px depend on `research-lead-workbench#26b`-`#26d`.

## Progress

- DIM2, part 1 (#612, merged): `GET …/research/persona-topics` answers each dimension's persona topic
  from `dimension_topic`; the "Vybrané dimenze" rows carry the chip and `data-aia="dimension:<id>"`.
  Still open in DIM2: each dimension's definition, its source in the population and its use (M-2).
- DIM3: one `Stepper` for n (`PersonaStep.tsx`, `data-aia="sample:n"`), bounded by the server's
  readiness limits in steps of 50, the recommendation stated beside it and one button to apply it; the
  slider and the 400/800/1200 presets are gone (audit B1). A value outside the limits is refused at the
  field and not saved. This is also the n half of `input-interactions#5`, which stays that plan's to tick.
- DIM1 (#729): `lib/artifacts/dimensions.ts` builds Dimenze's ids (`dimensionAia`, `ownDimensionAia`), an id
  outside the grammar left unmarked (the own-dimension rows used to call `aiaId`, which throws). The
  stepper's `sample:n` comes from Vzorek's `sampleAia.n()`. The integration coordinator answered
  (2026-10-22): the row gains `show_diff` (the plan's `show_changes`; Lead edits land on Dimenze), non-live
  until the op is built, in the coordinator's next registry PR, with `tryAiaId` beside `aiaId`; `sample:n`
  stays on the stepper, one value whose kind's stage is Vzorek (focus opens it there), no second target.
  That PR (#739) landed; Dimenze's ids are built with `tryAiaId`.
- DIM4, read half (#667): "Vlastní dimenze klienta" on Dimenze (`OwnDimensions.tsx`,
  `lib/own-dimensions.ts`) lists the study's materializations, each with its state, its reason and the
  target beside what was achieved (unknown never met), pointable as `own_dimension:<run id>`, and links
  to "Populace běhu". The list route answers `kind`. Still open in DIM4: the request, which waits on
  `client-knowledge-lifecycle#K5` (how a person writes a definition) and MVPQ-03 (descriptors).

## Findings

- **DIM-F1 (fixed in the DIM3 PR).** The "Vybrané dimenze" rows were indented twice: the list carried
  `px-4` inside `StepSection`'s body, which already pads by `px-4` (`PersonaStep.tsx:244 @ bfe6d15`,
  `step.tsx:57 @ bfe6d15`). Seen at 390 px in `dimensions_journey.mjs`'s screenshot; fixed by dropping
  the inner padding. No unit test can see padding; the journey's screenshots are the evidence.
- **DIM-F2 (fixed in #647, F11; open at the time of writing).** Under 1100 px the note
  says to ask the Lead "v konverzaci vlevo", but there is no conversation on the left: the Lead opens
  as a drawer or sheet (`AskLead.tsx:28 @ bfe6d15`; seen at 390 px on Dimenze). #647 makes it "v
  konverzaci s ním (na užší obrazovce ji otevře tlačítko Vedoucího)".

- **DIM-F3 (fixed in the DIM3 PR).** The Vzorek card's heading showed "N=300", which is the
  recommendation, beside a stepper holding the stored n (600 in the audit at 1440 px), so it read as
  the current n (`PersonaStep.tsx:323 @ b6ac25c`). The chip is gone, and the recommendation is named
  only on its button. Test: "the heading names no n but the stored one".

- **DIM-F4 (fixed: the frame's part in #668, Dimenze's "Další" → Vzorek in its own PR).** Inside the workbench the dock still speaks the classic flow: its
  back link reads "4. Audience" (`PersonaStep.tsx:379 @ b6ac25c`, `cs.ts:222`) where the navigator says
  "Cílová skupina" (`workbench-stages.ts:25`), and "Další · kontrola" skips Vzorek, the workbench's next
  stage. Seen at 390 px. #668 drops the dock's back link inside the workbench (`FrameNavigation`);
  #686 gives the stage the frame's next stage (`FrameNavigation`'s `next`, focus on its heading), and
  Dimenze's "Další · Vzorek" opens it (test "inside the workbench goes on to the frame's next stage",
  `dimensions_journey.mjs`); the classic layout keeps "Další · kontrola" to Spuštění.

- **DIM-F5 (fixed in its own PR).** In the workbench a chosen dimension could be removed, and a requested
  one seen, only in the inspector drawer ("Připravenost a pomoc"), which is closed unless opened: the main
  "Vybrané dimenze" list had no remove and no waiting rows, and with nothing chosen it drew nothing
  (`PersonaStep.tsx:205-243` vs `:249 @ 9607ee09`). So after "Přidat jako požadavek" the request was gone
  from the screen once its toast closed. The drawer's × was 16 × 19 px, under WCAG 2.5.8's 24. Seen at
  1440 px. The selection now carries its base row, a 24 px remove per dimension (V2's `removable`) and the
  empty state, with the waiting requests as their own list beside it ("Požadované dimenze"); the drawer's
  duplicate is gone. Tests: "removes a chosen dimension where it is listed and shows a waiting request
  beside it…", `dimensions_journey.mjs` (remove targets at four widths, removed and put back),
  `workspace_journey.mjs` (the request waiting after its toast).

- **DIM-F6 (fixed in the same PR).** The society-factor note named the old product and said the run
  "počítá s celou populací" (`cs.ts:2491 @ 9607ee09`), though a panel run draws under the audience and the
  persona source is chosen before the run ("Kdo bude odpovídat"). It now says where respondents are
  chosen, without naming a stage (the classic calls it Kontrola a spuštění, the workbench Sběr dat) or
  promising the panel, which is offered only under `AIA_AI_POPULATION_PERSONAS_ENABLED`. Test: "goes on
  calibrated… say they are not in AIA and where respondents are chosen".

- **Not fixed, for the product owner.** "Cena / value for money" keeps its English half: it is 18.6.6's
  label (`ui_app.html:404`), pinned with the server's `DIMENSION_LABELS` (`project_memory.py:46`).

- **Fixed by the integration session in #807.** Every visit sent `GET …/design/source` three to four times
  and `…/research/impact` once (both 404 by design) and `PUT …/workspace/stage` twice: the classic layout
  mounted before /config answered, then the workbench (`ResearchScreen.tsx @ d4d093fd`; test "mounts a stage
  once on a fresh page, not the classic layout first and then the workbench"). The integration session
  measured a visit at 44 → 36 requests; what remains is `next dev`'s Strict Mode double effects and the
  by-design 404.

- **DIM-F7 (fixed in its own PR).** Removing a chosen dimension by keyboard left focus on the page's body:
  the row took its button with it (`PersonaStep.tsx:226 @ 382b418a`). Focus now goes to the next row's
  remove, else the previous one's, else the list, with a visible focus ring. Tests: "after a remove, focus goes to the next row's
  remove…", `dimensions_journey.mjs` (removed by keyboard, focus kept in the selection).

- **DIM-F8 (fixed in the same PR).** A search that matched nothing said so only visually: the message
  was mounted in place of the catalogue, not in a live region (`PersonaStep.tsx:282 @ 382b418a`). It is now
  an always-mounted `role="status"`. Test: "says a search that matches nothing in a status…".

- **DIM-F9 (fixed in the same PR).** "Přidat jako požadavek" with an empty name read "Požadavek se
  nepodařilo uložit · Napište název dimenze.", a failed save where nothing was sent, not tied to the field;
  and Enter in the field did nothing (`PersonaStep.tsx:351-355 @ 382b418a`). The empty name is now the
  field's own error, apart from a failed request: `aria-invalid`, described by the message, focus on the
  field, announced again on a second try and cleared by typing; the field is a form that Enter sends. Test:
  "requests a dimension the system does not have: refused when empty, proposed, recorded".

- **DIM-F10 (fixed in its own PR).** "Použít doporučené" replaces the chosen dimensions with the
  recommended set (18.6.6's autofillPersonaDims, `persona.ts:154 @ 1fed2969`), so a dimension the person
  chose outside it was dropped without a word and with no way back (`PersonaStep.tsx:296 @ 1fed2969`); a
  remove from the list had no Vrátit either (`:250`), against input-interactions I6. Both now offer Vrátit
  (`undoChosen`): an unchanged selection is put back exactly, order included; one changed since loses only
  what that action added and gets back what it took, at its old place; focus lands on the dimension put
  back. The autofill offers it whenever it changes the selection and names what it dropped. Its replacing
  semantics stay the classic's. The AI suggestion's apply also replaces the selection without Vrátit; it
  leaves this stage with DIM5 (OI-53, the Lead card LO22), so it is not given one here. Tests: "names what \"Použít doporučené\" drops and
  puts it back on Vrátit…", `research/persona-undo.test.ts`, `dimensions_journey.mjs` (removed by keyboard,
  put back by Vrátit, focus on it).

## 8. Owner questions

None new. MVPQ-03 (what a segment or descriptor is) stays open in `mvp-owner-decisions.md`.

## Doc follow-up

- Register this plan and its chunks.
