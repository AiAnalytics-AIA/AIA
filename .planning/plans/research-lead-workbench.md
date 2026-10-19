---
status: in-progress
chunks:
  - "[ ] 1. Split layout: pure width, keyboard and focus-mode rules with the prototype's bounds"
  - "[ ] 2. Inspector back stack: pure state and the item drawer, beside InspectorSlot"
  - "[ ] 3. Port the prototype's workbench frame: stylesheet, icons, study header, phase navigator over lane.ts, split, rail"
  - "[ ] 4. Mount the workbench as the study screen behind AIA_WEB_RESEARCH_WORKBENCH (on for develop): artifact header and state bars over the existing stage screens"
  - "[ ] 5. Lead backend: study_lead_turns, StudyLeadRepository, ResearchLead, /lead routes, research_lead template and executor, settings"
  - "[ ] 6. Lead pane: conversation, composer, greeting, view tools, edits as change blocks, decision cards"
  - "[ ] 6b. Personal Leads: researcher_leads and memories, hatching, the Můj Vedoucí page, per-researcher sessions"
  - "[ ] 7. Agent proposals inline in the artifact, with research-question coverage gained, lost and kept"
  - "[ ] 8. design_items, the working revision on each Design Revision and every web submit naming it, the item-level stale rule"
  - "[ ] 9. Accept in one transaction: merged Design Revision, working copy, ledger; the web reloads"
  - "[ ] 10. Dismiss and rebuild through the ledger and rebuild_of; the pending-proposals projection"
  - "[ ] 11. Lead-prepared paid work recorded in the ledger, with the spend limit, from the server's command registry"
  - "[ ] 12. Workbench journey: four widths, keyboard, focus modes, a Lead turn on recorded answers, zero unintended paid jobs"
---
# Research Lead workbench

The study screen becomes the research-lead prototype (`prototypes/research-lead-v2`, PR #481 @
9b50963f). On the left is the conversation with the Research Lead (Vedoucí výzkumu); on the right is
the stage's artifact. The Lead reads the study, explains it, steers the artifact pane, proposes edits
as change blocks the person accepts, and prepares paid work as decision cards the person approves.

The design is [ADR 0026](../../docs/architecture/adr/0026-research-lead-proposes-a-person-decides.md),
**Accepted** on 2026-10-19 with the product owner's decisions in its *Accepted with* section.

## Decisions taken in this plan

- **D1. The prototype is the visual target, and AIA's code does the work.**
  - The prototype's frame is ported into `apps/web`: header, navigator, split, conversation,
    composer, artifact header, state bars and inspector. Its stylesheet already reads AIA's
    `src/app/tokens.css`.
  - The prototype's fixture-driven artifacts are **not** ported. The artifact bodies are AIA's
    stage screens (`STEP_SCREENS`), which already load, edit and save the real working content.
- **D2. The navigator shows the prototype's eleven stages in six phases, over today's routes.**
  - Brief → `brief`, Design → `plan`, Questionnaire → `questionnaire`, Audience → `audience`,
    Dimensions → `persona` (slug `dimensions`).
  - Sample is a read-only projection over Dimenze and Kontrola.
  - Fieldwork → `run` and `progress`.
  - Results, Sociomap, Analysis and Report → `results`, with `ResultsWorkspace`'s view.
  - Each stage's state comes from `designLane` / `runLane` (`apps/web/src/research/lane.ts @
    50547cdc`). Nothing new decides a tone.
- **D3. The split uses the prototype's bounds** (`Split.tsx:10-11, 21, 48-52 @ 9b50963f`).
  - The left pane is 28–62 %, adjusted in steps of 2 %.
  - Home, Enter or a double-click resets it to 40 %.
  - Artifact focus collapses the conversation to a rail; conversation focus is a temporary 68 %.
  - The width is kept per browser.
- **D4. Two inspectors.** `InspectorSlot` keeps the stage's readiness. The item drawer, with its
  back stack, shows one item's detail.
- **D5. The workbench switch, `AIA_WEB_RESEARCH_WORKBENCH`,** is read by `/config`. It is on for
  develop and off by default, so a deployment that has not chosen it keeps today's layout.
- **D6. Lead edits pass the server's gate.** Accepting or dismissing a change block is
  `POST …/lead/turns/{turn_id}/edits`, with the working revision it was shown on. The server applies
  the edits, saves the working copy and writes the ledger rows in one transaction; the web then
  reloads the working copy.
- **D7. Lead decision cards start paid work only on the server's gate.** A design job is approved by
  `POST …/lead/turns/{turn_id}/request`, which carries the spend limit, the ledger row and the start
  in one transaction. A research run, Design Research and Interpretation Research open their stage,
  whose own start carries its gates. Cards and their gates land in the same chunk (6).
- **D8. PRs.** Each piece opens as a draft PR. It is marked ready so Codex reviews it, its findings
  are handled, and it merges once green (the product owner, 2026-10-19).

## Chunks

1–2 landed in PR #483: `lib/workbench-split.ts`, `lib/inspector-stack.ts` and `ItemInspector.tsx`.
3–4, 6 and 7 are web. 5 and 8–11 are backend; 9 changes the accept route and the web together.
12 is the journey (`tools/ui_workbench/workbench_journey.mjs`).

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
