---
status: in-progress
chunks:
  - "[x] 1. Split layout: pure width, keyboard and focus-mode rules with the prototype's bounds"
  - "[x] 2. Inspector back stack: pure state and the item drawer, beside InspectorSlot"
  - "[x] 3. Port the prototype's workbench frame: stylesheet, icons, study header, phase navigator over lane.ts, split, rail"
  - "[x] 4. Mount the workbench as the study screen behind AIA_WEB_RESEARCH_WORKBENCH (on for develop): artifact header and state bars over the existing stage screens"
  - "[x] 5. Lead backend: study_lead_turns, StudyLeadRepository, ResearchLead, /lead routes, research_lead template and executor, settings"
  - "[x] 6. Lead pane: conversation, composer, greeting, view tools, edits as change blocks, decision cards"
  - "[x] 6b. Personal Leads: researcher_leads and memories, hatching, the Můj Vedoucí page, per-researcher sessions"
  - "[ ] 7. Agent proposals inline in the artifact, with research-question coverage gained, lost and kept"
  - "[x] 8. design_items, the working revision on every Design Revision writer (web submit, reuse, accepts), the item-level stale rule"
  - "[x] 9. Accept in one transaction: merged Design Revision, working copy, ledger; the web reloads"
  - "[x] 10. Dismiss and rebuild through the ledger and rebuild_of; the pending-proposals projection"
  - "[ ] 11. The command registry: the workers the Lead may call, each with its prompt and price, behind approve_request (ledger and spend limit already built); the route-class refusal says who fixes it (lead-orchestration LO12a, then LO12b); first deliverable: the worker row (lead-orchestration LO9a)"
  - "[ ] 12. Workbench journey: four widths, keyboard, focus modes, a Lead turn on recorded answers, zero unintended paid jobs"
  - "[x] 13. Design V3 in the repository (prototypes/research-lead-v3, its text) and its chunks in this plan"
  - "[ ] 14. The Lead's view vocabulary: a closed, per-artifact set of display operations the Lead may run on the artifact pane"
  - "[ ] 15. The artifact frame: title, state pill, one version line and at most one state bar; inputs, feeds, workers and provenance in the inspector (the canonical V2 prototype's D5, owner confirmed in MVPQ-01 on 2026-10-20), Pracovní kopie / Historie / Původ, the revision stepper"
  - "[ ] 16. Pointing at the artifact: the Vidí chip, the target button and @ over every artifact's elements"
  - "[ ] 17. Questionnaire artifact, its proposal shown in it (where chunk 7 lands)"
  - "[ ] 18. Brief and Research design artifacts"
  - "[ ] 19. Sample and Fieldwork artifacts"
  - "[ ] 20. Results and Sociomap artifacts, drawing aia-sociomap-5 in full: credibility, uncertainty circles, the respondent map, taste segments, unplaced objects, in Results and project memory alike (D-13)"
  - "[ ] 21. Analysis and Report artifacts"
  - "[ ] 22. Audience and Dimensions artifacts"
  - "[ ] 23. Worker and Deep Research cards in the conversation, each opening the artifact it changes"
  - "[ ] 24. A standing 'continue until you need me' beyond an approved plan's steps, over chunk 11's command registry, stopping at every gate (after the MVP: the plan-scoped part is lead-orchestration LO3-LO5)"
  - "[ ] 25. Deep Research reachable from every stage as a capability"
  - "[ ] 26a. The Lead at every width (D20, MVPQ-11), its pure rules: lib/workbench-layout.ts, the breakpoints (split from 1100 px, drawer 768-1099, sheet under 768), the drawer's states and the one Escape order, tested at 1099, 1100, 768, 767 and 390 px"
  - "[ ] 26b. One tree, three layouts: Workbench renders the artifact and LeadPane once at every width, so crossing 1100 px remounts nothing (a mount-counter test); the workbench serves under 1100 px"
  - "[ ] 26c. The launcher and the drawer (D21): the rail or bottom bar opens the same LeadPane as a side drawer (768-1099 px) or a full-screen sheet (under 768 px); keyboard, focus trap and Escape with a return to the targeted artifact; tested at 1099, 768 and 390 px"
  - "[ ] 26d. The compact header and stage navigator at 768-1099 and under 768 px: all eleven stages reachable by keyboard, no page overflow"
  - "[ ] 26e. A stale card refused and a direct request held by the same server gates, in the drawer and in the split"
  - "[ ] 26f. The manual AI starts removed in every layout behind one predicate, except Spuštění's own Start (D15, 2026-10-21); a static guard test; the journeys start work through the Lead's cards or a typed start"
  - "[ ] 27a. Availability, said once and honestly (D20): first an anchored inventory of every path that turns the Lead off or stops it answering, each made hard to trigger by accident (Q43); then lib/lead-availability.ts (ON / WAITING / OFF / UNKNOWN from GET /lead; unknown never on), the launcher's dot and a stage's one line"
  - "[ ] 27b. The kill switch holds on every Lead start: a card approved after a switch-off is 409 research_lead_disabled, stored text edits can still be accepted or dismissed (Q42); with the Lead off the composer takes only LO5's typed start commands, matched by code, through the same cards, wallet and LO15 confirmation (Q43)"
  - "[ ] 27c. Retire the classic study frame and AIA_WEB_RESEARCH_WORKBENCH (Q41, D5 superseded): the workbench serves at every width, so a Lead is always present; the classic-frame journeys move to the workbench at 1440, 1024, 768 and 390 px"
  - "[ ] 27d. The switch matrix as one journey: Lead on, Lead off and worker parked, at 1100 and 390 px; what is shown, no manual AI start, a direct HTTP start meeting the same gates"
  - "[ ] 29. Conversation controls: older-message paging (with its route), copy, edit and resend, ArrowUp to edit the last message, send-now and edit for a queued message (D-38)"
  - "[ ] 30. The conversation's UI for LO18: streamed text, a file from the composer, unprompted comments marked as paid turns (D-39)"
  - "[ ] 31. Results: charts on the result views and a CSV/XLSX export of the per-question tables from admitted claims (report-delivery RD12) (D-41)"
  - "[ ] 32. The Lead pane's web results: inline citations with links and quotes, the result list as it arrives, each search's cost, and Kontext studie (the study's context file) readable with its version (Q5, Q6)"
  - "[ ] 33. Editor spike (Q19): Wordcraft, ONLYOFFICE Docs and Collabora Online compared against Tiptap for the study context file and reports, on Word-like UX, tracked changes and comments, Lead-driven edits, ledger refs through a round trip, DOCX fidelity, licence and EU self-hosting; a go/no-go to the owner"
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
  **Superseded by D22 (Q41, 2026-10-21):** the classic study frame is retired and the switch is removed
  in chunk 27c.
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

1–2 are built in PR #483 (`lib/workbench-split.ts`, `lib/inspector-stack.ts` and
`ItemInspector.tsx`). They are ticked on that branch, so they read done when its code reaches `develop`, not before.
3–4, 6 and 7 are web. 5 and 8–11 are backend; 9 changes the accept route and the web together.
12 is the journey (`tools/ui_workbench/workbench_journey.mjs`).

5, 6 and 6b are built in the Lead backend PR: the routes, the `research_lead_turn` executor, the
researcher's own Lead with its revisions and notes, and `tools/ui_workbench/lead_journey.mjs`. The
journey runs a Lead turn in a browser on the workbench's scripted Lead (`ScriptedLeadExecutor`),
never a model: hatching, the greeting, a message, an edit accepted through the server's gate and
read back after a reload, a prepared job left unapproved, the note on Můj Vedoucí.

## Stage artifacts, steered by the Lead (chunks 13-25; V2 canonical, V3 supporting)

The earlier V3 designs ([`prototypes/research-lead-v3`](../../prototypes/research-lead-v3/README.md)) remain a supporting inventory of stage capabilities; their visible text is under `prototypes/research-lead-v3/text/`, cited as `artifacts.txt FRAME n`. **The owner's later MVPQ-01 decision (2026-10-20) selects the Czech V2 clickable build as the visual and interaction reference for the shell and all eleven artifact bodies.** Each step remains its own purpose-built artifact. A V3 frame reference below names coverage to reconcile, not authority to replace the corresponding V2 layout.

Today the workbench mounts the classic stage screens as the artifact (`Workbench.tsx:473 @
0b4e05e` renders `{children}`, passed in by `ResearchScreen.tsx`), as D1 chose. The Lead steers
the pane through two operations, `open_stage` and `focus` (`domain/research_lead.py:192-202 @
0b4e05e`), at most three a turn (`:416`), a focus naming only `question|section|brief|plan`
items (`:176`); the web applies them (`lib/lead.ts:30, 301 @ 0b4e05e`) and the person can point
at an element (`lib/lead.ts:341`, `Workbench.tsx:185-207 @ 0b4e05e`).

**Decisions (product owner, 2026-10-19).**

- **D9. The navigator stays at the top.** The V3 boards draw a lifecycle rail at the bottom; it is
  not adopted. Phases and stage states stay `lib/workbench-stages.ts:21-41 @ 0b4e05e` over `lane.ts`.
- **D10. The Lead controls the artifact pane** through a **closed vocabulary of display operations**
  each artifact declares: artifact, tab, revision, the element in focus, the view, object or section
  shown, whether changes are shown. They change what the person sees, never what is stored (the
  design's "browser operator": it works the same page the person sees). An operation naming a target
  the artifact does not have is refused, never guessed. Anything that changes data stays a typed
  command behind its existing gate (D6, D7).
- **D11. The interface is Czech.** The design's English gives structure and meaning: "Workspace /
  History / Provenance" are **Pracovní kopie / Historie / Původ**, the "Sees" chip is **Vidí**.
- **D12. Supersedes D1 for the artifact bodies; amended by MVPQ-01, 2026-10-20.** Each step's artifact follows the canonical V2 build inside the workbench, one or two per PR, over AIA's own data and routes (never the design's fixtures). V3 contributes a supporting coverage checklist only. The
  classic layout (switch off) keeps today's screens; under 1100 px the workbench still serves, with the Lead as a compact drawer or a stacked layout (D20, MVPQ-11); on switch-off the compact Lead stays reachable while its backend is enabled.
  *2026-10-21:* the classic layout is retired (D22, Q41) and the compact Lead is a drawer (D21).
- **D13. AIA's data only.** Where AIA has nothing behind a part of an artifact, the part says so in
  words ("V AIA zatím není", or the backend's own reason), never a placeholder that reads like data.
- **D14. The journey grows with the artifacts.** Chunk 12 lands first, and each artifact PR adds its
  own steps to `workbench_journey.mjs` / `lead_journey.mjs`.
- **D15. Every AI action goes through the Research Lead** (owner, 2026-10-19; `overview.md` MVP-8).
  The manual AI buttons (AI pomoc, the stage cards' "Navrhnout", the job panel's starts) are removed.
  **Except Spuštění's own Start (owner, 2026-10-21):** the Run stage keeps its "Spustit výzkum" button,
  with its own gates, and a research run also appears as a card in the Lead's chat. The owner's words:
  "i want this to appear in the lead researches chat too". Chunk 26f leaves that one button in place.
  The Lead calls smaller workers, each with its own system prompt (ADR 0020), as it prepares a design
  job today (`AgentJobRequest`); a paid one starts only on a person's approval through
  `approve_request`, which already holds the study's spend limit (`application/research_lead.py:678-760
  @ 0b4e05e`). Removal goes **artifact by artifact**: each of 17-22 lands without its stage's buttons
  and with the Lead able to call that stage's worker, so no AI action is ever without a way in. This
  removes the way in from the interface only; it does not enforce the spend limit, which is a server
  rule (`lead-orchestration#LO15`).
- **D20. The Lead stays accessible at every width (owner, MVPQ-11, 2026-10-20; reconciles D12 and D15).**
  Under 1100 px the workbench still serves, with the Lead as a compact drawer or a stacked layout beside the
  artifact, consistent with the canonical V2 workspace; the exact composition is an engineering and design
  choice. The manual AI starts are removed in every layout (the stage components are shared), so no alternate
  start exists, and every layout uses the same revision-bound card, approved-plan, wallet and
  `lead-orchestration#LO15` server-confirmation paths: the container adds no authority and weakens no
  privacy. **On switch-off or rollback** the actual availability is stated: the compact Lead stays reachable
  while its backend is enabled, a genuinely disabled backend stays disabled and says so, and a kill switch is
  never bypassed. A direct request is held by the same server gates. Client Knowledge extraction is the
  separately recorded client-level exception (`lead-orchestration#LO13`, MVPQ-08). Tests (chunks 26, 27):
  1099, 1100, 768 and 390 px, keyboard, focus and Escape with a return to the targeted artifact, a stale card,
  the switch off, the kill switch off, and a direct HTTP start.
  **Composition settled by D21 (2026-10-21):** a compact drawer, not a stacked layout.
- **D21. The compact Lead is a drawer, over one tree** (engineering and design choice under D20,
  2026-10-21; the reasons are in *Chunks 26-27* below).
  - At 1100 px and wider the split serves, as today (the prototype's rule).
  - At 768-1099 px the artifact takes the width; V2's rail (artifact focus, D3) stays at the left and
    opens the conversation as a **side drawer** over the artifact, `min(440px, 80vw)`.
  - Under 768 px the rail becomes a bottom bar, and the conversation opens as a **full-screen sheet**
    (`100dvh`, safe-area insets).
  - The drawer and the sheet are `role="dialog"`, `aria-modal`, named by the Lead, with a focus trap;
    Escape or Zavřít closes it and returns focus to the launcher, or to the artifact a Lead view op
    targeted.
  - **One tree, no remount.** `Workbench` renders the artifact (`children`) and `LeadPane` once, at one
    position in its element tree, at every width; a layout changes only classes and where the
    conversation's container is placed. A hidden conversation stays mounted, so its poll, its greeting
    and its once-only view ops keep their state. `useStageWide` goes with the classic frame (27c).
  - A stacked layout was rejected: at 1099 x 800 it leaves about 380 px for the artifact, it nests two
    scroll regions in one column, and a Lead `focus` op can land off screen behind the conversation.
- **D22. The owner's answers on the Lead's switches** (Nigel, the product owner, 2026-10-21).
  - **Q41 (11:54 UTC): retire the classic study layout.** The workbench serves at every width and
    `AIA_WEB_RESEARCH_WORKBENCH` is removed (D5 superseded; chunk 27c). His note: "this means a lead is
    always present". Rollback of the frame is a redeploy of the previous release; the Lead's own
    rollback stays `AIA_AI_RESEARCH_LEAD_ENABLED`. With one frame, there is no Lead controller to lift
    into a shared host: the Lead stays inside `Workbench`.
  - **Q42 (11:43 UTC): refuse it.** A Lead card prepared before the Lead was switched off is refused on
    approval with 409 `research_lead_disabled`; the card waits until the Lead is on again. Accepting or
    dismissing stored text edits stays allowed: it calls no model and spends nothing. His note: "this is
    an edge case". Chunk 27b.
  - **Q43 (11:44 UTC): typed start commands work without the model.** With the Lead off, the composer
    still takes `lead-orchestration#LO5`'s typed start commands, matched by code with no model in the
    path, through the same approval cards, ledger row, wallet and LO15 confirmation; free text is
    refused with the disabled notice. His note: "we should analyze what all turns off a lead, the lead
    should not be turned off very easily". So chunk 27 begins with an inventory of every path that
    disables the Lead or stops it answering, each anchored and each made hard to trigger by accident
    (27a).
- **D16. Release scope** (owner, 2026-10-19; MVP-3). The Lead and all eleven stage artifacts following V2 are
  release-blocking (12, 11, 14-23). **The plan-scoped part of the autopilot is in the MVP** (an approved
  plan the Lead runs, and a person's chat start: `lead-orchestration` LO3-LO5; MVP-3 amended and MVP-13
  superseded by the per-study wallet, 2026-10-19). Chunk 24, a standing "continue" beyond a plan's
  steps, and chunk 25, Deep Research from every stage, come after the MVP; 24 needs an ADR for the Lead's
  own permission scope first.
- **D17. The workers** (owner, 2026-10-19; MVP-12, MVP-13). Chunk 11's registry holds the eight
  existing `ResearchAgentAction`s (`domain/research_agents.py:37-44 @ 0b4e05e`) and three new contracts,
  each closed and proposal-only with its own prompt (ADR 0020): a map interpreter (reads a frozen map,
  writes an unapproved interpretation, never an input to the map), a report writer (wording and order
  of a draft; numbers stay references re-admitted by the evidence gate), a straight-liner check (flags
  respondents with identical battery answers, proposes keep or replace; replacing needs a new step).
  Every paid job is one approval card.
- **D18. Structural edits may auto-apply per stage** (owner, 2026-10-19; MVP-14). The researcher's
  `auto_accept_text_edits` (`domain/research_lead.py`, `ResearcherLead`) gains a per-stage choice for
  structural edits; off by default; every applied edit is still a working revision and a ledger row
  marked auto, as the text edits are.
- **D19. The Lead sees everything stored about results** (owner, 2026-10-19; MVP-15). Today its runs
  layer is id, status and design revision (`application/research_lead.py:882-889 @ 0b4e05e`) within a
  96 KB context (`domain/research_lead.py:116`). The design: a results layer that summarizes each
  stored artifact (aggregates, maps, module texts, report drafts) by id, classified by
  `context_classification` like every other layer, and a read tool the Lead names an artifact with to
  have it in the next turn, so the bound holds. `lead_contract`'s rule (a number only from the
  context) stays.

**The artifacts.** The canonical V2 build governs all eleven bodies (MVPQ-01,
settled 2026-10-20). The complete stage-by-stage producer/consumer and required-delta
matrix is [the current conformance disposition](../evidence/mvp-prototype-v2/current-disposition.md).
The older V3 frame inventory is supporting reference.

| Chunk | Canonical V2 artifacts | Production contract |
|---|---|---|
| 17 | Questionnaire | Sections, routing, time/coverage, inline proposals and protected map inputs; WCE writer/merge/lock contracts |
| 18 | Brief; Research design | Stable classified materials and question/decision/measurement/analysis/report links; unsupported coverage remains a gap |
| 19 | Sample; Fieldwork | Actual quota/support/readiness, typed progress/receipt/QC and cost; pinned population/method and checkpoint events |
| 20 | Results; Sociomap | Admitted results, stored map output and exact register status; object/pair controls, filters and internal drill-down |
| 21 | Analysis; Report | Finding/claim/source chain, blocked reasons and same-data retry; draft changes and exact-version approvals |
| 22 | Audience; Dimensions | LIVE counts and source pins; own dimensions materialize and feed a real consumer despite the prototype's simulated panel |

Chunks 15/20/21 explicitly retain the four-way distinction: deterministic frozen result,
display-only operation, labelled AI interpretation and external context. Display and
context never mutate numeric outputs or acquire admitted-result status.

Chunk 15 also owns the V2 message-origin/context inspector and return summary UI;
chunk 12 verifies copy, older-message paging, queue, stop/edit keyboard controls and
return to the last read position. Origin means permitted captured context/prompt/
worker references, not hidden reasoning or another researcher's turns. The last-read
cursor is researcher-scoped; LO7 provides the real event/context summary and LO11
its personal lifecycle. Agree the minimal context/origin/cursor contract in W1 before
the W4 UI, alongside LO7/LO8 and the privacy tests. No new shared-chat store is implied.

**Order.** 12 (the journey), then 11 (the command registry: which workers the Lead may call, each
with its prompt and price; most of the paid path is built, `mvp-consolidation.md` §6), then 14-16
(vocabulary, frame, pointing: every artifact needs them), then 17-22 (those AIA backs first, Audience
and Dimensions last; each removes its stage's AI buttons, D15), then 23. 24-25 after the MVP (D16).
The backend each chunk needs is in `.planning/mvp-consolidation.md` §6.

## Findings

- **F1. An agent job ignores the study's spend limit** *(a defect to fix now, `lead-orchestration#LO15`)*.
  - `ResearchAgentJobs.start` (`research.py:1300-1384 @ 50547cdc`) holds a reservation but never
    reads `spend_confirm_usd`, which `ResearchRuns.start` applies (`research.py:716-729 @
    50547cdc`).
  - ADR 0026 decision 7 applies the limit to Lead-prepared jobs. `mvp-cohesion.md` F5 adopts the
    check inside `ResearchAgentJobs.start` as the first code change (`lead-orchestration#LO15`), so no
    path is held to a different rule.
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
- **`CLAUDE.md` § 2**, beside `src/components/workbench/`: `prototypes/research-lead-v2/` is the
  canonical workspace and artifact reference (MVPQ-01, 2026-10-20); V3 is supporting reference.
- **ADR 0026**, under *Accepted with*: the Lead steers the artifact pane through a closed set of
  display operations (D10); its gates are unchanged.

## Child plans (added by the master plan, 2026-10-19)

The orchestration and edit work this plan's artifacts stand on is in six plans, each chunk in exactly one
place: `working-copy-edit-ops` (the shared vocabulary, merge, per-change accept, presence, the Sociomap
lock), `lead-orchestration` (the wallet, the plan card, the chat start, the continuation turn,
`ResultsContext`, the Lead over time), `run-qc-and-checkpoint`, `report-delivery`, `study-data-lifecycle`
and `production-environment`. Chunks 14-22 here build the screens over them. Chunk 15
follows the owner-selected V2: inputs, feeds, workers and provenance live in the inspector,
and a state bar appears only when it applies. MVPQ-01 settles this decision.

## Owner decision MVPQ-01 (2026-10-20)

After the side-by-side review, the owner selected the prototype open in the browser:
the Czech AIA Vedoucí výzkumu / Research Lead V2 build. This settles prototype precedence
for the full workspace and all eleven artifact bodies. It supersedes the recommendation
to take V3 bodies by default. Implement the selected compact layout; expose complexity
through its contextual controls. Preserve existing domain/methodology, scope, budget,
approval and privacy decisions. MP12 (the master plan's chunk) records necessary conformance deltas; implementation
chunks remain open. See `../mvp-owner-decisions.md` MVPQ-01; do not re-ask this question.

## Assumption panel (2026-10-20, MVPQ-02)

Tracked assumptions are shown and edited in the Design artifact (18) and in Audience (22, where the canonical V2 places the assumption and evidence panel), both from the one item contract of `assumptions-and-open-answer-coding#AOC1`; there is no second store and no panel-local state.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunks.** 29 (W2), 30 (W3, with `lead-orchestration#LO18`), 31 (W3, with
`report-delivery#RD12`). D-38, D-39 and D-41 were answered **in** whole.

**Existing chunks, changed by the owner's answers.**

- **20 (D-13).** The map views draw `aia-sociomap-5` only: the method named, relative-height terraces,
  the credibility banner, split-half share and uncertainty circles, "Neumístěno", the respondent map
  and taste segments, following `ui_app.html`'s drawing (packet E-3, the owner's standing rule). Today `ObjectMapView` reads only `support` (`ObjectMapView.tsx:296, 568 @ 7975ff6`, #514), so a weakly
  determined `-5` map looks as confident as any other. Project memory's past runs draw through the same
  `RunResults`, so they get the same layers. Test: a `-5` map with a low split-half share shows its
  credibility banner and uncertainty circles in Results and in project memory. The
  `-1`/`-3` drawing leaves the product; a stored older run keeps its data and its map panel says "Mapa ze
  starší metody; spusťte běh znovu" (Q2).
- **15.** Mount `ItemInspector` (imported only by its own test) and fix provider waits reading as
  inert (`research/lane.ts:134 @ 854c209`).
- **26 (D-12).** No Deep Research button survives as an exception; Deep Research starts through the
  Lead (`lead-orchestration#LO5a`).
- **Map node drag** (D-40) is **out**: camera-only view operations satisfy AC-09.

### After the baseline's questions (the owner's answers to the baseline's Q1-Q8, 2026-10-20 19:37-19:46 UTC (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, second table))

- **32 (W3, with `lead-orchestration#LO19` and `#LO20`).** The UI half: a search's results appear in
  the turn as they come (no click to open them), each claim with its inline citation, a captured page
  one click from "Ověřeno, přidat zdroj"; the study's context file is readable from the pane.

### Implementation lane: the methodology owner's #517 (2026-10-20)

The product owner, 21:33 UTC (relayed by the coordinator): the `-5` drawing is **A. Bahbouh's own
lane**, PR #517 (`feature/aia-sociomap-5-web`) and its plan `.planning/plans/sociomap-5-web.md` on that
branch.
- Built there (chunks 1-5 ticked on the branch at the time of writing): the panel ported pixel for
  pixel, credibility (the weakly-determined banner, the uncertainty circle, objects not placed), the
  respondent map and taste segments.
- Still to come there: detail on click (6), and the Word report's `-5` figure and the web map's PNG
  snapshot (7).

**Chunk 20 does not build the `-5` layers again.** It hosts #517's panel in the Results and Sociomap
artifacts and in project memory, and its credibility test is met by #517's work. Chunk 20 keeps the
artifact frame, routing and the old-method panel text (Q2).

### After the editor answer (the owner's answers on the PM status page, 2026-10-20, relayed by the coordinator at 21:41 UTC (page ids Q19 to Q21; `.planning/evidence/scope-freeze/answers-2026-10-20.md`, fifth table))

- **33 (W1, page Q19: (a)).** Evaluate before adopting. A time-boxed spike compares editors for the
  study context file (`lead-orchestration#LO19`) and the report documents (`report-delivery#RD6`),
  each researcher's tracked-change or direct mode (page Q13) included. Its outcome is a written
  go/no-go to the owner; nothing is adopted in this chunk.
  - **Candidates:** Wordcraft (`github.com/storytold/wordcraft`; MIT/Apache, Rust/WASM, an MCP
    server, alpha); ONLYOFFICE Docs (AGPL, Word-like, track changes, a JS API); Collabora Online
    (LibreOffice-based, MPL, WOPI). Tiptap is the baseline: the owner finds its UX poor ("I want as
    close to Microsoft Word or LibreOffice as possible") and asks for alternatives.
  - **Criteria:** a Word-like UX; tracked changes and comments; the Lead driving edits (suggestion
    and direct modes); every report number staying a ledger ref through an edit and a DOCX round trip
    (`report-delivery#RD6`); DOCX fidelity against `infrastructure/report_docx`; the licence (AGPL's
    obligations named for a hosted product); EU self-hosting with no outside service.
  - **Evidence:** each candidate run locally on one fictional study context file and one sample
    report, the round trip's ledger refs counted before and after, a screenshot set, the licence
    reading. Zero paid jobs.
  - LO19 and RD6 build against the editor the owner chooses; until then they keep a plain editor
    behind the same edit operations, so the choice changes the surface, not the rules.
  - **Spike written up (2026-10-20):**
    [`editor-spike-2026-10-21.md`](../evidence/editor-spike-2026-10-21.md).
    - It is a desk comparison of five editors with cited sources. The local run on fictional files
      is not done yet: this session's egress refused the vendors' hosts.
    - Its recommendation: a conditional go for ONLYOFFICE Docs Community, self-hosted. AIA writes
      the Lead's suggestions as OOXML revisions, and every number is a locked, tagged content
      control that AIA checks on each save. Collabora Online is the fallback.
    - It records finding F-ED1: no path that writes digits into a report tags them with their
      source. The evidence file lists sixteen paths, P1-P16, plus the ones it rules out:
      - the ledger's values in prose, tables, KPI tiles, captions, charts and the appendix;
      - the map's pair table, support prose and fit caption;
      - the design, method and literature chapters' facts.

      Anchors include `report_docx/blocks.py:116-123`, `tables.py:182-198`, `blocks.py:280-299`,
      `application/report_maps.py:186-223` and `report_docx/figures.py:79 @ e09a6c99`. R3 cannot be
      checked through a round trip until RD6 emits every one as a locked, tagged content control.
    - It records finding F-ED3: no report keeps its document model
      (`apps/executors/src/aia_executors/report.py:121-167 @ e09a6c99`). `report-delivery#RD5a` is
      therefore a prerequisite of both edit modes.
    - Open question OQ-ED1, for the owner and A. Bahbouh: map result values (P7-P9) are not
      admitted ledger refs, which RD6 requires. Either admit them as ledger claims, or approve an
      exemption that tags them by artifact id. Until then, their tagging is provisional.
    - The save check compares whole numeric tokens per paragraph, so `Q19` → `Q91` is refused.
    - The one-day proof covers comments as well as numbers. It reads replies and resolved state by
      parsing `commentsExtended.xml`, `commentsIds.xml` and `commentsExtensible.xml` directly,
      because python-docx reads `comments.xml` only.
    - The go/no-go is the owner's, so the chunk stays open.

## Chunks 26-27: the Lead at every width, and with its switches off (2026-10-21)

Written from a read of `origin/develop @ 095a3e68`; every anchor below is `file:line @ 095a3e68`
unless it says otherwise. The decisions are D20, D21 and D22 above; cohesion F13.3
(`.planning/mvp-cohesion.md:435-454`) and master-plan gap G40 (`mvp-master-plan.md:427`) are the
register rows these chunks answer. Each sub-chunk is one draft PR (D8).

**What exists.**

- The layout is chosen in `Ready` (`ResearchScreen.tsx:336-337, 349, 378`): the deployment switch
  (`app/config/route.ts:31`, read once per page and off while unknown, `ResearchScreen.tsx:232-252`),
  then the width (`useWideEnough`, `matchMedia("(min-width: 1100px)")`, `Workbench.tsx:61-77`), kept per
  stage by `useStageWide` (`Workbench.tsx:79-90`) because crossing 1100 px remounts the stage screen in the
  other tree and drops what its editors hold. Under 1100 px AIA serves the classic layout
  (`workbench.css:504`); V2 shows only a note there (`prototypes/research-lead-v2/src/app/App.tsx:45`),
  so V2 has no narrow design.
- Both frames render the same stage screens (`ResearchScreen.tsx:371-373, 390-392`). What the Lead does
  beyond the conversation (edit decisions, automatic accepts, view ops, pointing, the cards' approval)
  is `Workbench` state (`Workbench.tsx:159-436`), not `LeadPane`'s.
- `LeadPane` needs a bounded height (`.conv`, `workbench.css:103`) and must stay mounted while hidden: it
  polls while a turn is busy (`LeadPane.tsx:134-139`), applies a finished turn's view ops once
  (`:140-147`) and greets once (`:174-179`). The split already hides rather than unmounts it
  (`Split.tsx:33-34`).
- Availability: `GET /lead` answers `available` and `unavailable_reason` from the API's
  `ai_research_lead_enabled` alone (`routers/lead.py:350-362`; `config.py:137`, off by default). A post is
  refused when off (`application/research_lead.py:402-403`); `approve_request` (`:683`) and
  `decide_edits` (`:504`) do not read the switch, which is Q42's case.
- The manual AI starts, all in components both frames share: AI pomoc (`ResearchScreen.tsx:44-55`,
  `ResearchAssistance.tsx:119, 121, 130, 144`), `BriefStep.tsx:135`, `PlanStep.tsx:756`,
  `QuestionnaireStep.tsx:238, 252`, `AudienceStep.tsx:302`, `PersonaStep.tsx:219`, Results' "Zeptat se na
  klientské znalosti" (`ExecutionSteps.tsx:1415, 1442`), Spuštění's "Spustit výzkum"
  (`ExecutionSteps.tsx:858`, **stays**, D15 2026-10-21), run and analysis retries (`ExecutionSteps.tsx:1077-1089,
  1114, 1121`), Design Research (`DeepResearchPanel.tsx:124, 139`), Interpretation Research
  (`InterpretationResearch.tsx:145, 161`) and `ProposalReview`'s "Navrhnout znovu" (`ProposalReview.tsx:151`,
  a paid rebuild). Not starts: `JobPanel`'s Cancel (`JobPanel.tsx:72`) and `AgentBudgetWaits`, a person's
  budget lift on the same job (`ResearchScreen.tsx:358, 402`). The client-level `SourceProposals.tsx` is
  the recorded exception (`lead-orchestration#LO13`, MVPQ-08).
- Tests that assume the classic frame: `workbench_journey.mjs:143-161` (classic at 1024 px);
  `ux_journey.mjs:66, 104` and `proposal_prompt_journey.mjs:44-152` at 1440/1024/768/390 with the switch
  off; `research_journey.mjs:45, 100` clicks "Spustit výzkum".

**The sub-chunks.** Journeys run on `make ui-workbench` + `make ui-fixtures` with the scripted Lead
(`ScriptedLeadExecutor`) and assert zero paid jobs; `lead_journey.mjs` passes once per workbench (OI-133),
so it is rerun on `workbench.py up --fresh`.

- **26a. The compact layout as pure rules.** New `apps/web/src/lib/workbench-layout.ts` and its Vitest:
  `layoutFor(width)` → `split` (≥ 1100) | `drawer` (768-1099) | `sheet` (< 768), with the breakpoints as
  named constants beside `workbench-split.ts`'s; the drawer's states `closed | open | peek(target) |
  picking`; `onEscape(state, context)` → the next state and where focus goes, in one fixed order: an open
  `AskDialog`, then picking, then the item inspector or `.insp`, then the drawer (a busy-turn stop,
  chunk 29, is the composer's own key while it has focus). Tests: the boundaries at 1099, 1100, 768, 767
  and 390; every transition; the Escape order for each combination; `peek` returns focus to the target,
  closing to the launcher. No dependency on `feature/lead-worker-cards`.
- **26b. One tree, three layouts** (D21). `Workbench.tsx`'s return tree (`:444-491`) renders the
  artifact and `LeadPane` once; `useWideEnough` becomes `useWorkbenchLayout()` over `layoutFor`;
  `Split.tsx` takes `layout`, drawing no handle and placing `split__left` as the overlay in `drawer` and
  `sheet`; `workbench.css` drops the 360/420 px minimums under 1100 (`:93, 96`) and adds `wb--drawer` /
  `wb--sheet` with `100dvh` and safe-area insets; `ResearchScreen.tsx:337, 349` serves the workbench at
  every width. Tests: `Workbench.test.tsx` with a `matchMedia` stub: crossing 1100 px both ways does not
  remount the stage child (a mount counter) and keeps `LeadPane`'s draft; in `drawer` the conversation is
  hidden but mounted and its poll continues; `workbench_journey.mjs`'s "classic at 1024" (`:153-161`)
  becomes "the workbench at 1440/1280/1100/1099/768/390, no page overflow". Lands after
  `feature/lead-worker-cards` merges, or rebased on it: both change `Workbench.tsx` and `LeadPane.tsx`.
- **26c. The launcher and the drawer.** `Rail` (`Workbench.tsx:642-649`) becomes `LeadLauncher`, a
  vertical rail in `drawer` and a bottom bar in `sheet`, with the pending badge and 27a's availability
  dot; the drawer shell is `role="dialog"`, `aria-modal`, focus-trapped, with Escape and Zavřít;
  `LeadPane.tsx:230-232`'s focus-mode toggle becomes Zavřít in a compact layout (a `container` prop);
  `onView` (`Workbench.tsx:238-255`) closes the drawer to `peek`, then highlights and focuses the target
  (`tabindex=-1`); picking (`:183-207`) hides the drawer while armed and reopens it at the composer.
  Tests (Vitest, RTL): open by Enter on the launcher, focus in the composer, Tab kept inside, Escape back
  to the launcher; a turn's `focus` op closes the drawer and focuses `#qedit_…`; "@" then a tap sets the
  chip and reopens; the pending badge is announced through the launcher's `aria-label`, since the hidden
  log's `aria-live` is silent. `lead_journey.mjs` at 1099, 768 and 390: hatch, greet, send, a change block
  accepted through the gate, Escape returning to the targeted artifact. Depends on 26b.
- **26d. The compact header and stage navigator.** `StudyHeader` (`Workbench.tsx:566-608`): under 768 px
  the budget meter and pending count move into the menu and the title truncates; `StageNav`
  (`:612-640`): a horizontally scrolled navigator at 768-1099 with the current stage in view, and under
  768 a stage button opening a phase-grouped list (`lib/workbench-stages.ts:16-42`), keeping the arrow,
  Home and End keys (`:613-620`); `.insp` full-width under 768 (`workbench.css:258`). Tests: the
  navigator's list and keys in Vitest; `workbench_journey.mjs` at 768 and 390: all eleven stages reachable
  by keyboard, no overflow, Výsledky's views by hash.
- **26e. The stale card and the direct request, in every layout.** Journey steps in `lead_journey.mjs`,
  in the drawer at 768 and in the split at 1100: a card from an older working revision is refused by the
  server and said so in words; a direct HTTP `POST …/research-agents/…` start or rebuild with the page's
  token meets the same LO15 confirmation and ledger; a direct `POST …/lead/turns/{id}/request` for a stale
  or used turn is refused. A server test only if a gap is found (LO15's tests exist,
  `lead-orchestration.md:23`). Depends on `feature/lead-worker-cards`, whose cards are what go stale.
- **26f. Remove the manual AI starts from every layout**, every row of *What exists* above except
  Spuštění's "Spustit výzkum", which stays and whose run also shows as a Lead chat card (D15,
  2026-10-21). Also `AI_HELP` and `ResearchAssistance` (the inspector keeps readiness and blockers),
  `askAssistance` (`context.tsx:41`) and the dead start paths of `useAnalysis` / `useAiStep` (their
  follow-and-continue parts stay while a stored job can wait for a lift). The cards branch gates its
  workbench-only removals with **one** predicate in `ResearchContext` (`leadOwnsAiStarts`); with the
  classic frame retired (27c) this chunk deletes the predicate and the removed controls together. Tests:
  a static Vitest guard listing every importer of `AiButton` (Spuštění's Start and `SourceProposals.tsx`
  only) and asserting no other stage control calls `runJob`, `research.start`, `deepResearch.start` or
  `retryAnalysis`; `ux_journey.mjs` starts its retries through the Lead's card or a typed start (LO5);
  `research_journey.mjs` keeps the Start button, now in the workbench. Depends on
  `feature/lead-worker-cards` merged (every removed start has its card), `lead-orchestration#LO5` and
  `#LO5a`, and 27c.
- **27a. Availability, said once and honestly.**
  1. **The inventory first (Q43).** Every path that turns the Lead off or stops it answering, anchored,
     each with how it is set, who can set it, and what keeps it from being set by accident. The seed,
     to be verified and completed in this chunk:

     | Path | Anchor | Effect | Accident today |
     |---|---|---|---|
     | API `AIA_AI_RESEARCH_LEAD_ENABLED` unset or false | `apps/api/src/aia_api/config.py:137` (default `False`); `routers/lead.py:356-359` | `GET /lead` off; a post refused (`application/research_lead.py:402-403`) | **Off by default**: a deployment that omits the key has no Lead |
     | Worker `AIA_AI_RESEARCH_LEAD_ENABLED` unset or false | `apps/executors/src/aia_executors/ai_runtime.py:696`; `registry.py:106` | a turn parks `research_lead_unconfigured` (`research_lead.py:79`) | The API and the worker read separate copies (`deploy/develop/docker-compose.yml:156, 237`) and can disagree |
     | Worker on, its keys unset | `ai_runtime.py:851` | every turn parks `research_lead_unconfigured` | Silent until a turn is asked |
     | A wrong Lead key | `ai_runtime.py:691-695` (the Lead's model equal to the route's) and `_with_study_lead` (`:848`) | the **worker stops at start**, every step with it | One typo stops all AI work |
     | `AIA_AI_RUNTIME_ENABLED` unset | `ai_runtime.py:571` | no runtime; the turn parks `ai_runtime_unavailable` | Off by default |
     | Egress and licence refusals | `LeadPane.tsx:39-45` (`egress_*`, `licence_undetermined`) | a turn parks or refuses for one study | A route or classification change elsewhere |
     | Budget | `LeadPane.tsx:48` (`AWAITING_BUDGET`) | the turn waits for a lift | A spent study budget |
     | Not hatched, busy, context too large | `infrastructure/researcher_lead_repository.py:67`; `application/research_lead.py:125`; `domain/research_lead.py:599` | a post refused for one researcher | By design, per researcher |
     | The web's own copy | `deploy/develop/docker-compose.yml:100`; `lib/public-config.ts:8` | display only, never availability | Can differ from the API's |

     The output is the table, completed and anchored, with each accidental path closed or named: for
     instance a start-time warning when the API and the worker disagree, and the default reconsidered
     in a separate owner-visible change. Nothing here loosens a kill switch.
  2. **The pure reader.** New `apps/web/src/lib/lead-availability.ts` and its Vitest: input `GET /lead`'s
     `available` and `unavailable_reason`, the newest turn's park reason and a read failure; output `ON |
     WAITING(reason) | OFF | UNKNOWN`, with words (the `REASON` map moves here from `LeadPane.tsx:36-50`).
     `UNKNOWN` (unreadable `/lead`, an older API's 404, `LeadPane.tsx:114`) never reads as on;
     `research_lead_disabled` reads as off; parks read as waiting. Only `GET /lead` decides; `/config`'s
     copy is never read for it.
  3. **Where it shows.** `LeadLauncher` (26c) shows it, and each stage that lost a start in 26f shows one
     line from it (D13), a `LeadAvailabilityNote` in `rehome/research`. `lead_journey.mjs` with the API's
     switch off: the launcher says vypnutý, the composer takes only typed commands (27b), old turns are
     readable, a stage shows the line and no AI start.
- **27b. The kill switch holds on every Lead start** (Q42, Q43). `approve_request`
  (`application/research_lead.py:683`) raises `LeadUnavailable` when not enabled and `routers/lead.py`
  answers 409 `research_lead_disabled` for `/request`; `decide_edits` stays allowed. `post` (`:402`) with
  the Lead off accepts only `lead-orchestration#LO5`'s matched command kinds, still refusing free text.
  Tests: a card approved after a switch-off is 409 with no workflow row and no reservation;
  `decide_edits` still works; a typed run start with the Lead off writes `chat_start` and passes the same
  wallet and LO15 checks, while free text is 409. The typed path depends on LO5.
- **27c. Retire the classic study frame** (Q41). `ResearchScreen.tsx`: delete `useWorkbenchSwitch`
  (`:232-252`), the classic branch (`:378-409`) and `useStageWide`; the pre-ready states (`:199-227`) take
  the workbench's header so the frame does not jump on load. `app/config/route.ts:31` and
  `lib/public-config.ts:34-36` drop `workbench`, with its test (`route.test.ts:118-124`);
  `deploy/develop/docker-compose.yml:116` drops the key. There is no `LeadHost`: the Lead stays inside
  `Workbench`, the one frame. Tests: `ux_journey.mjs`, `proposal_prompt_journey.mjs`,
  `workspace_journey.mjs` and `audience_journey.mjs` pass in the workbench at 1440, 1024, 768 and 390.
  Lands after 26b-26d (the workbench must serve every width first) and before 26f.
- **27d. The switch matrix as one journey.** New `tools/ui_workbench/lead_availability_journey.mjs`, or
  steps in `lead_journey.mjs`: Lead on, Lead off and worker parked, at 1100 and 390: what is shown, that
  no manual AI start exists (a DOM query for the removed labels and `[data-ai-start]`, Spuštění's Start
  excepted), and that a direct HTTP start meets the same gates. Then 26 and 27 are done.

**Order.** 26a and 27a's pure reader now; 27a's inventory beside them; 26b, 26c, 26d after
`feature/lead-worker-cards` merges; 26e; 27b (with LO5 for the typed path); 27c; 26f; 27d.

**Risks.**

- **A remount at the breakpoint loses unsaved editor state.** Today's guard is `useStageWide`
  (`Workbench.tsx:79-90`); 26b's one-tree rule replaces it and its mount-counter test proves it. A
  regression would drop Návrh's narrative without the leave guard.
- **Escape collisions.** Escape already disarms picking (`Workbench.tsx:198-200`), closes `ItemInspector`
  (`ItemInspector.tsx:42`) and `ResearchAssistance` (`ResearchAssistance.tsx:95`, gone after 26f), and in
  V2 stops a busy turn (`prototypes/research-lead-v2/src/components/Composer.tsx:86`, chunk 29). 26a fixes
  one order; every handler respects `defaultPrevented`.
- **A hidden live region announces nothing.** The conversation's `aria-live` (`LeadPane.tsx:287`) is
  silent while the drawer is closed; the launcher carries a new reply and a pending card.
- **The soft keyboard and `100dvh` on phones.** The sheet's composer must stay above the keyboard
  (`visualViewport`, safe-area insets). `.wb` is `height: 100dvh; overflow: hidden` (`workbench.css:8-9`),
  so stage screens that relied on page scroll in classic scroll inside `.artbody`; the journeys at 390
  have measured only classic.
- **"@" pointing has no hover on touch.** The outline is `:hover`-only (`workbench.css:518`); on touch the
  first tap must both show and choose the target.
- **Merge overlap with `feature/lead-worker-cards`.** Both change `Workbench.tsx` and `LeadPane.tsx`. Its
  workbench-only gate must be one predicate, or 26f becomes a hunt through every stage component. That
  branch was unpushed and empty at `095a3e68`, so every `Workbench.tsx` and `LeadPane.tsx` anchor here
  is likely to move when it lands.
- **The order of removal.** Removing the starts before 27c would leave the classic frame, still served
  under 1100 px, with neither the Lead nor any AI start: D20 broken. Restoring buttons to hide a
  disabled Lead breaks MVPQ-11.
- **The Lead's kill switch becomes a research-wide stop** once every start but Spuštění's goes through
  the Lead. Q43's typed commands keep runs, retries and Deep Research reachable with the Lead off;
  operators must still know what the switch stops before they use it in an incident (27a's inventory).
- **Availability from the wrong source.** `/config`'s copy (`docker-compose.yml:100`) can differ from the
  API's (`:156`); only `GET /lead` decides what the study screen says.
- **Production changes frame at once** (Q41). The switch is off by default (D5), so the release carrying
  27c moves production from classic to the workbench in one step; rollback is the previous image.
- **The journeys' cost and flakiness.** Six widths × three Lead states multiply the run time, and
  `lead_journey` passes once per workbench (OI-133): 27d stays at 1100 and 390, the full width sweep at
  the Lead-on state.

### Doc follow-up (chunks 26-27, 2026-10-21)

- **`mvp-master-plan.md` and `mvp-execution-contracts.md`.** `research-lead-workbench#26` and `#27` are
  now `#26a`-`#26f` and `#27a`-`#27d`. The references at `mvp-master-plan.md:315` (AC-02), `:427` (G40),
  `:511` (G69, now `#26f` with LO5a), `:698` (MVPQ-11's row) and the execution contracts' E26
  (`mvp-execution-contracts.md:49`) and LO5a's row (`:210`) name the sub-chunks; each sub-chunk takes
  E26's wave (W1). `tools/master_check.py` fails until they do.
- **`mvp-owner-decisions.md`.** Q41-Q43 as answered (D22), and the 2026-10-21 run-start decision (D15).
- **`mvp-cohesion.md` F13.3.** Its "no stage start of its own" no longer holds for the research run:
  Spuštění keeps its Start beside the Lead's card (owner, 2026-10-21).
- **`CLAUDE.md` § 2**, when 27c lands: `src/components/workbench/` no longer sits behind
  `AIA_WEB_RESEARCH_WORKBENCH`; there is no classic layout; the Lead is a drawer under 1100 px.
  When 26a and 27a land: `lib/workbench-layout.ts` and `lib/lead-availability.ts`.
