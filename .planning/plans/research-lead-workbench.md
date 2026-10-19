---
status: planned
chunks:
  - "[ ] 1. Split layout: pure width, keyboard and focus-mode rules with the prototype's bounds"
  - "[ ] 2. Inspector back stack: pure state and the item drawer, beside InspectorSlot"
  - "[ ] 3. Phase navigator: StageTrack's groups as a vertical navigator over the same lane"
  - "[ ] 4. Mount the workbench behind AIA_WEB_RESEARCH_WORKBENCH (off): the inspector column becomes the left pane"
  - "[ ] 5. Inline proposal review: change blocks in the artifact, research-question coverage gained, lost and kept"
  - "[ ] 6. Workbench journey: four widths, keyboard, focus modes, both switch states, zero paid jobs"
  - "[ ] 7. (ADR 0026) design_items and the item-level stale rule, with cases shared with proposalDiff"
  - "[ ] 8. (ADR 0026) Accept in one transaction: merged Design Revision, working copy, ledger; the web reloads"
  - "[ ] 9. (ADR 0026) Dismiss and rebuild through the ledger and rebuild_of; the pending-proposals projection"
  - "[ ] 10. (ADR 0026) study_lead_turns, StudyLeadRepository and the conversation routes, no model"
  - "[ ] 11. (ADR 0026) The research_lead_turn executor behind AIA_AI_RESEARCH_LEAD_ENABLED, measured"
  - "[ ] 12. (ADR 0026) Command registry, stage contracts, human-only refusal and Lead-prepared job approval"
  - "[ ] 13. (ADR 0026) The conversation in the left pane: turns, decision cards, the event feed"
---
# Research Lead workbench

Make the research-lead prototype (`prototypes/research-lead-v2`, PR #481 @ 9b50963f) AIA's study
workspace. On the left (40 %) is the conversation with the Research Lead; on the right (60 %) is
the stage's artifact. Proposals land inline, and every decision is a person's.

The design is [ADR 0026](../../docs/architecture/adr/0026-research-lead-proposes-a-person-decides.md),
**Proposed**. The plan has two parts:

- **Chunks 1–6** call no model and change no API. They can land before the ADR is accepted, and
  each leaves `develop` green and deployable.
- **Chunks 7–13** carry out the ADR and start only after the product owner accepts it.

## Decisions taken in this plan

- **D1. Today's stages and slugs stay.**
  - The navigator groups the existing `STEP_KEYS` (`apps/web/src/research/steps.ts:16 @ 50547cdc`).
    These are ten keys, eight of them on the track. It does not invent a second list.
  - Phases are `StageTrack`'s groups (`StageTrack.tsx:21-25 @ 50547cdc`): design, sample, run.
  - Each stage's state is `designLane` / `runLane` (`apps/web/src/research/lane.ts @ 50547cdc`).
    Nothing new decides a stage's tone.
  - The prototype's Sample stage is a read-only view over Dimenze (`persona`, slug `dimensions`)
    and Kontrola (`run`). It is not a new stage.
  - The prototype's result sub-stages (data, maps, analysis, report) are `ResultsWorkspace`'s
    views on `results`.
- **D2. The split uses the prototype's bounds** (`prototypes/research-lead-v2/src/components/Split.tsx:10-11,
  21, 48-52 @ 9b50963f`).
  - The left pane is 28–62 %, adjusted in steps of 2 %.
  - Home, Enter or a double-click resets it to 40 %.
  - Artifact focus collapses the conversation to a rail; conversation focus is a temporary 68 %.
  - Focus modes never overwrite the saved width, which is kept per browser (`localStorage`,
    wrapped in try/catch, the default without it).
- **D3. Two inspectors, not one.**
  - `InspectorProvider` / `InspectorSlot` (`Inspector.tsx:65-90 @ 50547cdc`) stay: the stage's
    readiness, portalled beside it. In the workbench, that column becomes the left pane's lower
    part.
  - The new item inspector is a drawer in the artifact pane, opened on an item's `data-aia` id,
    with a back stack. Escape closes it and returns focus to the opener.
  - Neither replaces the other: one is the stage's state, the other is an item's detail.
- **D4. The layout ships behind a web switch**, `AIA_WEB_RESEARCH_WORKBENCH`, read by `/config`
  (`apps/web/src/lib/public-config.ts @ 50547cdc`). It is off by default, so `develop` keeps
  today's layout until the product owner turns it on. Both states are journey-tested.
- **D5. Strings go into `apps/web/src/i18n/cs.ts`**, in the sections the research stages already
  use (`aia.study.*`, `research.*`). The file is never rewritten.
- **D6. The Lead's backend waits for ADR 0026.** Chunks 7–13 change an API route, add a table,
  add a worker step and spend money. None of them starts before acceptance.

## Chunks

### 1. Split layout (web, pure)

- **Files.** `apps/web/src/lib/workbench-split.ts` and its tests. The tests cover clamp, step,
  reset, pointer to percentage, focus-mode width, and the stored value read and refused.
- **Verify.** `make test-web`, `npx tsc --noEmit`.

### 2. Inspector back stack (web)

- **Files.**
  - `apps/web/src/lib/inspector-stack.ts`: open, back, close, and reset on a stage change. Pure,
    with tests.
  - `components/rehome/research/ItemInspector.tsx`: the drawer, Escape, focus return. Tested.
- **Verify.** `make test-web`.

### 3. Phase navigator (web)

- **Scope.** `StageTrack.tsx` gains a vertical variant for the workbench, fed by the same `GROUPS`,
  `designLane` and `runLane`, with roving arrow-key focus.
- **Tests.** `StageTrack.test.tsx` gains cases showing that both variants read the same tones.
- **Verify.** `make test-web`.

### 4. Mount the workbench (web)

- **Scope.**
  - With `AIA_WEB_RESEARCH_WORKBENCH` on, `ResearchScreen.tsx`'s workspace grid
    (`ResearchScreen.tsx:279 @ 50547cdc`) becomes the split.
  - The left pane holds what the inspector column holds today: the stage's readiness slot, AI help
    (`ResearchAssistance`), the job panel, budget waits, saved proposals, and *Do spuštění zbývá*.
  - The navigator moves into the left pane's head, and the artifact fills the right.
  - Off, nothing changes.
- **Verify.** `make test-web`, `make web_design`, `npx tsc --noEmit`, and the existing journeys
  with the switch off.

### 5. Inline proposal review (web)

- **Scope.** `ProposalReview` is drawn as change blocks at the items they change, with a sticky
  bar (accept, dismiss). It shows research-question coverage gained, lost and kept, from
  `proposedTrace` / `trace.ts` and `proposalDiff`. A stale refusal says which items conflict and
  offers rebuild.
- **API.** Today's accept route, unchanged. The item-level rule arrives in chunk 7.
- **Verify.** `ProposalReview.test.tsx`, `make test-web`.

### 6. Workbench journey (web)

- **Scope.** `tools/ui_workbench/workbench_journey.mjs`, run with the switch on and off:
  - 1440, 1280, 1024 and 768 wide, with no horizontal page scroll;
  - the separator, by keyboard and by pointer;
  - the focus modes;
  - the item drawer's back stack and focus return;
  - zero paid jobs.
- **Verify.** The journey after `make ui-workbench` + `make ui-fixtures`.

### 7. Item-level stale rule (ADR 0026 decision 5)

- **Scope.**
  - `aia_core/domain/design_items.py`: `design_items(before, after)`.
  - A shared case file used by both its pytest and `proposal-diff.test.ts`.
  - `ResearchAgentJobs.start` records `base_workspace_revision`; the worker records
    `touched_items` with the proposal.
- **Verify.** `make test`, `make typecheck`.

### 8. Atomic accept (ADR 0026 decision 6)

- **Scope.**
  - `ResearchAgentJobs.accept` performs the stale check, merge, `submit_if_current`, working-copy
    save and ledger row in one transaction, under the Study lock.
  - The route takes `expected_workspace_revision` and returns both revisions.
  - `useResearchAgents.apply` reloads instead of writing back.
  - Web and API change in this one PR.
- **Tests.**
  - Every refusal: design moved, an overlapping edit, a request without the field.
  - A non-overlapping edit survives.
  - A failure at each step leaves nothing written.
- **Verify.** `make verify`.

### 9. Dismiss, rebuild, pending proposals (ADR 0026 decision 8)

- **Scope.**
  - Dismiss writes `decision = "dismiss"`.
  - The acceptance check reads `"accept"` only.
  - Rebuild starts a job with `rebuild_of`.
  - A projection lists pending proposals.

### 10. The conversation table (ADR 0026 decision 8)

- **Scope.**
  - The `study_lead_turns` migration.
  - `StudyLeadRepository` (StudyContext only, a `layer_check` rule).
  - `GET /studies/{id}/lead` and `POST /studies/{id}/lead/turns`. With the switch off, a turn is
    stored and parks; it never fakes a reply.
- **Verify.** `alembic upgrade head`, downgrade then upgrade, `make test`, `make layer_check`,
  `make openapi`.

### 11. The Lead turn executor (ADR 0026 decisions 1–3, 9)

- **Scope.**
  - The `research_lead` template and the `aia.research.lead` prompt.
  - Context assembly with byte bounds.
  - The closed output contract with the number validator.
  - `aia_executors/research_lead.py` over `StepModelCaller`.
  - The switch and its two keys.
- **Measured before develop turns it on:** input bytes per layer, latency, and the metered cost of
  20 turns on a fictional study.

### 12. Command registry and Lead-prepared jobs (ADR 0026 decisions 4, 7)

- **Scope.**
  - `aia_core/application/lead_commands.py`, with the stage contracts.
  - `403 human_gate_required`.
  - Approval of a prepared job: the ledger row, the spend limit, and the API setting
    `ai_research_reservation_usd`.

### 13. The conversation in the left pane

- **Scope.**
  - Turns, the Lead's reply, decision cards for prepared requests, and the activity feed.
  - Visual commands applied, every one revertible.
  - Switched off: the left pane is chunk 4's.

## Findings

- **F1. An agent job ignores the study's spend limit** *(observation, not yet a defect)*.
  - `ResearchAgentJobs.start` (`research.py:1300-1384 @ 50547cdc`) holds a reservation but never
    reads `spend_confirm_usd`, which `ResearchRuns.start` applies (`research.py:716-729 @
    50547cdc`).
  - ADR 0026 decision 7 applies the limit to Lead-prepared jobs. Whether a person's own button
    should be held to it too is the product owner's call.
  - Reproduction: set a spend limit below `AIA_AI_RESEARCH_RESERVATION_USD`, then start any design
    job; no confirmation is asked.
- **F2. Today's accept can silently overwrite an edit made in another tab.**
  - The browser's guard (`useResearchAgents.tsx:85 @ 50547cdc`) compares only its own store.
  - The server compares only Design Revisions (`study_design_repository.py:180-183 @ 50547cdc`).
  - Closed by chunk 8.
  - The test that would have caught it: accepting after a working-copy save from a second session
    on an item the proposal changes must be refused.

## Doc follow-up (for the docs PR, not this branch)

- **`docs/architecture/adr/README.md`.** Add 0026, *The Research Lead proposes; a person decides,
  and an accept updates the working copy on the server*, Proposed.
- **`CLAUDE.md` § 2**, once chunks land:
  - `lib/workbench-split.ts`, `lib/inspector-stack.ts`, `ItemInspector.tsx` and
    `AIA_WEB_RESEARCH_WORKBENCH`;
  - then (chunks 7–13) `domain/design_items.py`, `application/lead_commands.py`,
    `study_lead_turns`, `aia_executors/research_lead.py` and `AIA_AI_RESEARCH_LEAD_*`.
- **`ARCHITECTURE.md`.** The accept route's new shape, and one more human-only gate source (a
  Lead-prepared job).
- **`.planning/open-items.md`.** F1 and F2 above.
