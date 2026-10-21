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
  - "[ ] 7b. Review a Design Research proposal inside the artifact (DRL-6, F-DRL-1): its EVIDENCE items with their findings' quotes and sources, ticked and accepted through POST …/design-proposal/accept with both expected revisions, then the working copy reloaded; a GAP item has no checkbox"
  - "[x] 8. design_items, the working revision on every Design Revision writer (web submit, reuse, accepts), the item-level stale rule"
  - "[x] 9. Accept in one transaction: merged Design Revision, working copy, ledger; the web reloads"
  - "[x] 10. Dismiss and rebuild through the ledger and rebuild_of; the pending-proposals projection"
  - "[ ] 11. The command registry: the workers the Lead may call, each with its prompt and price, behind approve_request (ledger and spend limit already built); the route-class refusal says who fixes it (lead-orchestration LO12a, then LO12b); first deliverable: the worker row (lead-orchestration LO9a)"
  - "[ ] 12. Workbench journey: four widths, keyboard, focus modes, a Lead turn on recorded answers, zero unintended paid jobs"
  - "[ ] 12a. The UI workbench runs Deep Research on recorded web with no paid calls (DRL-1, F-DRL-6): the six steps and the track kind over deep_research_recorded with a scripted model transport, one fictional design and one interpretation exchange; local and test only"
  - "[x] 13. Design V3 in the repository (prototypes/research-lead-v3, its text) and its chunks in this plan"
  - "[ ] 14. The Lead's view vocabulary: a closed, per-artifact set of display operations the Lead may run on the artifact pane"
  - "[ ] 15. The artifact frame: title, state pill, one version line and at most one state bar; inputs, feeds, workers and provenance in the inspector (the canonical V2 prototype's D5, owner confirmed in MVPQ-01 on 2026-10-20), Pracovní kopie / Historie / Původ, the revision stepper"
  - "[ ] 16. Pointing at the artifact: the Vidí chip, the target button and @ over every artifact's elements"
  - "[ ] 17. Questionnaire artifact (umbrella): artifact-questionnaire QST1-QST9; chunk 7 lands in QST5"
  - "[ ] 18. Brief and Research design artifacts (umbrella): artifact-brief BRF1-BRF6, artifact-design DSN1-DSN8"
  - "[ ] 19. Sample and Fieldwork artifacts (umbrella): artifact-sample SMP1-SMP6, artifact-fieldwork FLD1-FLD8"
  - "[ ] 20. Results and Sociomap artifacts (umbrella): artifact-results RES1-RES7, artifact-sociomap SOC1-SOC8; the aia-sociomap-5 drawing in full (credibility, uncertainty circles, the respondent map, taste segments, unplaced objects, in Results and project memory alike, D-13) is sociomap-5-web, hosted by SOC2"
  - "[ ] 21. Analysis and Report artifacts (umbrella): artifact-analysis ANL1-ANL8, artifact-report RPT1-RPT7"
  - "[ ] 22. Audience and Dimensions artifacts (umbrella): artifact-audience AUD1-AUD6, artifact-dimensions DIM1-DIM6"
  - "[ ] 23. Worker and Deep Research cards in the conversation, each opening the artifact it changes (partial, feature/lead-worker-cards: design-job and research-run cards built; Deep Research cards not yet)"
  - "[ ] 24. A standing 'continue until you need me' beyond an approved plan's steps, over chunk 11's command registry, stopping at every gate (after the MVP: the plan-scoped part is lead-orchestration LO3-LO5)"
  - "[ ] 23b. Deep Research request and running cards in the conversation (DRL-4, after #550's chunk 23 half): the quote (ceiling by kind, priced routes, missing live settings, threshold), 'Spustit rešerši' through approve_request, the orb, six steps and fan-out tracks, waits with resume and budget lift, Zrušit"
  - "[ ] 23c. The finished Deep Research card (DRL-7): coverage and counts, the first findings with 'Ověřeno, přidat zdroj', 'Zkontrolovat návrh' (7b), 'Použít ve zprávě' and the report with literature prepared and approved on CompleteReport's routes, a failure's cause and 'Zkusit znovu'"
  - "[ ] 26f.1. The Deep Research half of 26f (DRL-5): the Deep Research starts and retries removed from every layout, their panels kept as readers; after 23b and after lead-orchestration LO5a.3 (Q48); with it lead-orchestration LO5a's acceptance"
  - "[ ] 25. Deep Research reachable from every stage as a capability"
  - "[ ] 26a. The Lead at every width (D20, MVPQ-11), its pure rules: lib/workbench-layout.ts, the breakpoints (split from 1100 px, drawer 768-1099, sheet under 768), the drawer's states and the one Escape order, tested at 1099, 1100, 768, 767 and 390 px"
  - "[x] 26b. One tree, three layouts: Workbench renders the artifact and LeadPane once at every width, so crossing 1100 px remounts nothing (a mount-counter test); the workbench serves under 1100 px"
  - "[ ] 26c. The launcher and the drawer (D21): the rail or bottom bar opens the same LeadPane as a side drawer (768-1099 px) or a full-screen sheet (under 768 px); keyboard, focus trap and Escape with a return to the targeted artifact; tested at 1099, 768 and 390 px"
  - "[ ] 26d. The compact header and stage navigator at 768-1099 and under 768 px: all eleven stages reachable by keyboard, no page overflow"
  - "[ ] 26e. A stale card refused and a direct request held by the same server gates, in the drawer and in the split"
  - "[ ] 26f. The manual AI starts removed in every layout behind one predicate, except Spuštění's own Start (D15, 2026-10-21); a static guard test; the journeys start work through the Lead's cards or a typed start"
  - "[ ] 27a. Availability, said once and honestly (D20): first an anchored inventory of every path that turns the Lead off or stops it answering, each made hard to trigger by accident (Q43); then lib/lead-availability.ts (ON / WAITING / OFF / UNKNOWN from GET /lead, which incorporates the worker's readiness from the composition record, lead-orchestration LO12b; ON only with the worker ready, unknown never on), the launcher's dot and a stage's one line"
  - "[ ] 27b. The kill switch holds on every Lead start: a card the Lead model prepared, approved after a switch-off, is 409 research_lead_disabled, stored text edits can still be accepted or dismissed (Q42); with the Lead off the composer takes only LO5's typed start commands, matched by code, and their server-matched chat_start cards stay approvable under the same wallet and LO15 confirmation (Q43); GET /lead reports the worker's readiness (LO12b)"
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
  - **Two kinds of card, one guard (Q42 with Q43).** The refusal is for a card **the Lead model
    prepared** (a model turn's `request`). A card the server matched from a person's typed command
    (`lead-orchestration#LO5`: matched by code, no model in the path, ledger `chat_start`) is not
    Lead-model output and **stays approvable while the Lead is off**, under the same wallet and LO15
    confirmation checks. The guard reads which kind the card is from the stored turn (its origin
    recorded by the server when the card was made), never from the request body.
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

## Chunk 23 brought forward, and D15 in the workbench (owner, 2026-10-21)

The owner on develop with the workbench on: "the individual AI worker buttons are still there, also a
modal appears when the AI workers are running, i want all the aiworker runtimes to pop up as cards in
the lead researcher chat, preserve the orb UI", widened the same day to research runs ("i want this to
appear in the lead researches chat too"). Built on `feature/lead-worker-cards`:

- **Cards.** Every design job (the eight `ResearchAgentAction`s) and every research run of the study,
  however it was started, is a card in the Lead's conversation (`lib/lead-cards.ts`,
  `components/workbench/LeadCards.tsx`): its name, its state (`agentJobState`, `runState`), its cost
  (unreported is said, never 0), and, while the API reports a step RUNNING, the orb and the live feed
  (`StepActivityPanel` at 64 px over `useStepActivity`). A job approved on a turn's card stands with
  that turn (`request_decision.run_id`); everything else at the time it was created. A finished job
  links to the stage its proposal changes and to its review there (`JOB_STAGE`; the review opens when
  that stage mounts, `OPEN_REVIEW_KEY` in the study's page memory); advice opens in the artifact pane.
  A run links to Průběh, and to Výsledky once its aggregate exists.
- **The prepared research run is an approval card** (the owner's widening; amends D7 for
  `research_run` only). "Zkontrolovat spuštění" submits the working design and reads its readiness, as
  Spuštění does on a visit; "Spustit výzkum" starts it through **Spuštění's own route**,
  `POST …/research/runs` (`ResearchRuns.start`: readiness, the spend limit and its confirmation with
  `budget-line.ts`, the default persona source, LIVE). No second start and no `approve_request` path
  were built. What only the person decides on Spuštění is sent there: a failing readiness,
  answerability gaps (their acknowledgement is written in the person's words), a ceiling unknown under
  a limit, another persona source or a materialized population.
- **No modal.** In the workbench the job dialog (`JobPanel` as a dialog) is not rendered; the card
  carries its content.
- **D15 removals (workbench layout only),** behind one predicate, `ResearchContext.leadOwnsAiStarts`
  (`leadOwnsAiStarts("workbench")`), which every stage reads; chunk 26 removes the predicate when the
  classic layout gets the Lead or is retired:
  - AI pomoc (critique_design, design_copilot, answer_memory: the inspector card, its question form,
    its saved list's "Pokračovat"), and Výsledky's "Zeptat se na klientské znalosti";
  - Zadání's "Vytvořit návrh s AI" (analyze_brief): a plain "Pokračovat na Návrh" link instead;
  - Dotazník's "Sestavit první verzi dotazníku" (build_questionnaire) and "Optimalizovat dotazník s AI"
    (optimize_questionnaire);
  - Cílová skupina's "AI: navrhnout cílovou skupinu" from a description (propose_audience);
  - Dimenze's "AI doporučí" (suggest_dimensions);
  - Návrh's "Doplnit a aktualizovat návrh" (follow-up answers) and "Zpracovat komentáře" -- **the
    owner, 2026-10-21: "this should be done through the lead agent too"**. In the workbench each is a
    save-only control, "Uložit odpovědi" / "Uložit komentáře": it writes the answers into
    `briefing.what_is_known` (`answerFollowUps`) or the comments into `briefing.review_comments`
    (`commentsToReview`, and marks the plan changed by comments, `plan_changed26`), exactly as the
    button did before its analysis, with no paid call. The stage then says the Lead updates the design
    from them and offers "Požádat Vedoucího", which sends the Lead a typed message ("Aktualizuj návrh
    podle mých odpovědí." / "…komentářů."); the Lead answers with its usual card for the same worker
    the buttons call, `analyze_brief`. No server change: the job's frozen design is the whole working
    copy (`domain/research_agents.py:536-543 @ 095a3e68`), so the saved answers and comments reach it;
    held by `test_the_design_update_from_saved_answers_and_comments_goes_through_approve_request`
    (through `approve_request` and the ledger).
  Each stage says the Lead prepares it instead (`AskLead`). Every one of those eight actions is an
  `AgentJobRequest` the Lead may prepare, and `approve_request` starts it with the spend gate and the
  ledger row (`application/research_lead.py:683-765 @ 095a3e68`).
- **Kept, and why:**
  - the classic layout's buttons (switch off, or under 1100 px): no Lead there until chunk 26;
  - Spuštění's Start: not a worker start (the owner: "too" means in addition);
  - Deep Research's starts (Návrh's "Spustit veřejný výzkum", Výsledky' "Spustit rešerši výsledků" and
    its retry): the Lead's `design_research` / `interpretation_research` requests only open the stage
    (D7); they go with `lead-orchestration#LO5a` (scope freeze, chunk 26 D-12);
  - the inspector's budget lifts and saved proposals: they continue or review an approved job, they
    start nothing.
- **Tests.** `lib/lead-cards.test.ts` (each action's card and stage, state words, orb only while
  RUNNING, run cards, the conversation's order, the run card's plan, the predicate),
  `LeadPane.test.tsx` (a running job's card with its orb and no dialog, then its links; a run's card;
  the run card starting only on a click), `ResearchScreen.workbench.test.tsx` (no AI start of its own on
  Zadání, Dotazník, Cílová skupina, Dimenze; Spuštění's Start kept) and
  `tools/ui_workbench/lead_cards_journey.mjs`: the scripted Lead (a message with "spusť" now prepares
  the research run, `aia_executors/workbench.py`) and the workbench's fictional fieldwork; zero paid
  jobs, the design job parks without the AI runtime.
- **The cards' hierarchy (owner, 2026-10-21: the run card "needs better visual hierarchy").** Every
  card reads as the prototype's decision card: an eyebrow where the decision is the person's, the
  title with a state pill, the Lead's why, the key facts as label/value rows (`kvgrid`, tabular
  numbers; the run's ceiling the most prominent value, an unknown one said, never 0; the budget
  before and at least after; the respondents with a link to Spuštění), the actions on the right. The
  "Na nejnovější" pill now sits in the flow above the composer, so it never covers a card's actions.
- **Codex on #550.** "Spustit výzkum" checks the working copy again at the click; a design that changed
  since the card's check is checked anew and shown, never started. Only a job that moves on its own
  (queued or running) is polled; one waiting for budget, recovery or the AI runtime is read again on
  the window's focus, a card's action or a budget change (`jobMovesByItself`).
- **Not built here:** Deep Research cards (chunk 23 stays open); a run card does not survive a reload
  beside the turn that prepared it (it then stands at its own time, and the request card reads open
  again, finding the run on the same revision when asked); the compact Lead under 1100 px (chunk 26).

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
- **F3. The Lead's greeting made a new study's first save stale** *(fixed on
  `fix/new-study-first-save-conflict`; the product owner on develop b3984d4, 2026-10-21)*.
  1. Claim: on a study with no working copy, the greeting's `post` saves the bare template as
     working revision 1 behind the browser, which loaded the study EMPTY, so the person's first
     save (base `null`) is refused `stale_revision` and the copy sits in conflict.
  2. Anchor: the greeting is posted on opening (`LeadPane.tsx:178 @ 962652b1`); `post` calls
     `_design_project` (`research_lead.py:427 @ 962652b1`), which for a study with no Design
     Revision calls `submit_as_working_copy` (`research_lead.py:811 @ 962652b1`), a working-copy
     save; the browser saves with `base_revision: s.revision`, `null` (`store.ts:233 @ 962652b1`),
     refused by `study_workspace_repository.py:268 @ 962652b1`. The turn also recorded
     `workspace_revision = None` for a context frozen from revision 1, so an automatic accept of
     its text edits was refused too (`research_lead.py:561 @ 962652b1`, then `stale_turn`).
  3. Reproduction: `pytest apps/api/tests/test_research_lead_api.py -k new_study` (both fail on
     962652b1); in a browser, the workbench with `AIA_WEB_RESEARCH_WORKBENCH=true`, a hatched
     Lead, a new study, two sentences typed into Zadání: "Uloženo jinde · změny zde neuloženy",
     "Pracovní kopie zatím neuložena".
  4. Consequence: the person's first words are not saved, and the only way on is "Načíst znovu",
     which drops them; every new study opened with a hatched Lead hit it.
  5. Fix: the template is nobody's work. `domain/workspace.py` `edited_from_current`: a copy
     naming no revision was edited from the current one when that is still the bare template with
     no analysis; the save and the Lead's accept both ask it. A copy holding anything else (an
     edit, a reused design, an analysis) still makes a save from no revision stale (ADR 0018).
     `post` names the template revision it froze the turn from.
  6. Tests: `test_a_greeting_on_a_new_study_does_not_make_the_persons_first_save_stale`,
     `test_a_greeting_on_a_new_study_has_its_text_edits_accepted_automatically`,
     `test_a_first_save_is_not_stale_over_the_bare_template_a_server_writer_saved`,
     `test_edited_from_current_names_the_current_revision_or_the_bare_template`.
- **F4. A Lead turn parked on the study's budget held the conversation for ever** *(fixed on
  `fix/lead-turn-after-budget`; reported by the product owner on develop, 2026-10-21)*.
  - Claim: a message sent with no study budget parks its turn in `AWAITING_BUDGET`, and that
    turn counted as busy (`_holds`, `research_lead.py:224-232 @ 095a3e68`), so every later post
    was refused `lead_busy` (`research_lead.py:420-423 @ 095a3e68`) and the pane queued every
    message behind it (`LeadPane.tsx:193 @ 095a3e68`).
  - Nothing ever freed it. Setting the budget in Nastavení → Studie only changes a number
    (`workflow_repository.py:2211-2213 @ 095a3e68`); the only lifts are the research run's and the
    agent job's (`routers/research.py:1396, 2932 @ 095a3e68`), and no route lifts a Lead turn's
    wait. The hold (389b54c5) assumed a lift that did not exist.
  - The first "error" was the parked turn's notice: the step's reason is `budget_exceeded`
    (`domain/workflow.py:583 @ 095a3e68`, read at `research_lead.py:219`), which the pane had no
    words for (its `AWAITING_BUDGET` entry, `LeadPane.tsx:48 @ 095a3e68`, never matched), so it
    showed "Vedoucí se zastavil (budget_exceeded)."
  - Owner decision (Q39, the product owner, 2026-10-21 11:41 UTC): no "Pokračovat" button; "once
    the budget is set or raised, it should automatically resend the message the researcher
    attempted to send in the first place".
  - Fix:
    - A parked turn holds nothing, so the chat never stalls behind one.
    - Setting or raising the budget sends it: `PUT /studies/{id}/budget` calls
      `application.research_lead.set_study_budget`, which after the audited change runs
      `release_lead_budget_waits`. Each of the study's Lead turns parked in `AWAITING_BUDGET` whose
      recorded hold (`requested_usd` on the parked attempt) now fits what remains is lifted through
      `WorkflowRepository.resume_budget_waits`: one `budget` / `lift` row in the approval ledger
      naming the person who set the budget, who is the consent. A hold that would still pass the
      budget, or that was not recorded (unknown never fits), stays parked with its words; a budget
      kept or lowered releases nothing.
    - A message written before the budget is set supersedes the parked turn (its run cancelled in
      the post's transaction, never paid: a budget park spends no attempt and holds no
      reservation), and the new turn's frozen history carries the unanswered message. A greeting
      never supersedes: it stores nothing. At most one turn waits, so 389b54c5's guarantee (no
      stack of paid turns behind a lift) holds.
    - The pane says what happens (`leadReasonWords` in `lib/lead.ts`): "Nastavte ho v Nastavení →
      Studie a zpráva se odešle sama."; a superseded turn reads "přečetl ji s vaší další zprávou".
  - Tests: `test_a_message_written_again_before_the_budget_is_set_is_answered_not_held`,
    `test_setting_the_budget_sends_the_parked_message_and_records_the_person`,
    `test_a_budget_still_too_small_leaves_the_turn_parked`,
    `test_a_parked_turn_whose_hold_is_unknown_stays_parked`,
    `test_a_greeting_does_not_supersede_a_message_waiting_for_budget`,
    `test_a_turn_resumed_from_a_budget_wait_holds_the_conversation`
    (`test_research_lead_application.py`);
    `test_setting_the_study_budget_sends_the_message_that_waited_for_it`
    (`apps/api/tests/test_research_lead_api.py`); `leadReasonWords` in `lib/lead.test.ts`.
- **F-STORE-1. Two flushes waiting behind one save sent the same base revision** *(recorded in
  #554; fixed on `fix/store-flush-serialise`)*.
  1. Claim: `ResearchStore.flush` let every caller waiting behind an in-flight save resume
     together; each built its body from the same `state.revision`, so the second was refused
     `stale_revision`. And a flush saved only the snapshot it took, so an edit typed during the
     flight stayed pending after it resolved, and callers looped (`submitWorkingDesign`).
  2. Anchor: `apps/web/src/research/store.ts:225-233 @ 054cf007` (`if (this.inflight) await
     this.inflight;` then `base_revision: s.revision`, with no re-check).
  3. Reproduction: a scratch Vitest on 054cf007 sent bases `[3, 4, 4]`; the tests below fail on
     `origin/develop` 722dd75c and pass with the fix.
  4. Consequence: after a fast edit, a false "Uloženo jinde" conflict whose only way on is a
     reload that drops the edit; and a caller that took one flush to mean "saved" (an accept, a
     job start) acted on a revision that did not hold the person's last edit.
  5. Fix: saves are serialised. `flush` waits for whichever save is in flight, looks at the copy
     again and saves only what is still owed (never saved, changed, failed or template-completed),
     from the revision the previous save returned, until nothing is owed; at most
     `MAX_FLUSH_ROUNDS` (4) saves, then `FlushIncomplete` with the change still pending and its
     debounced save armed. The debounced autosave stays one save per debounce. A flush on a copy
     AIA already holds sends nothing (it used to send a deduplicated save). `submitWorkingDesign`
     calls `flush` once instead of looping.
  6. Tests (`apps/web/src/research/store.test.ts`): `serialises the saves of callers waiting
     behind one: each names the revision the one before returned`, `saves an edit made during the
     flight in the same flush, which resolves only once it is saved`, `says when the copy kept
     changing through every round, and keeps the change waiting for its save`.

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
- **`.planning/open-items.md`.** F1 and F2 above; F3 and F-STORE-1, each closed by its fix.
- **`CLAUDE.md` § 2**, `domain/workspace.py` / the working content paragraph: a save naming no
  revision is not stale over a working copy that is still the bare template a server writer
  saved (`edited_from_current`).
- **`CLAUDE.md` § 2**, beside `src/components/workbench/`: `prototypes/research-lead-v2/` is the
  canonical workspace and artifact reference (MVPQ-01, 2026-10-20); V3 is supporting reference.
- **ADR 0026**, under *Accepted with*: the Lead steers the artifact pane through a closed set of
  display operations (D10); its gates are unchanged.

## Artifact plans (2026-10-21)

The product owner, 2026-10-21: "we need to have a plan for each artifact of each research stage",
and "ensure they all work together to produce a draft research document".
- Chunks 17-22 are now umbrellas. Each is ticked when its artifact plans are done, and the work is
  built from those files:

  | Chunk | Artifact plans |
  |---|---|
  | 17 | [`artifact-questionnaire`](artifact-questionnaire.md) (chunk 7's questionnaire half is QST5) |
  | 18 | [`artifact-brief`](artifact-brief.md), [`artifact-design`](artifact-design.md) |
  | 19 | [`artifact-sample`](artifact-sample.md) (Kontrola's readiness), [`artifact-fieldwork`](artifact-fieldwork.md) (Spuštění and Průběh) |
  | 20 | [`artifact-results`](artifact-results.md), [`artifact-sociomap`](artifact-sociomap.md) |
  | 21 | [`artifact-analysis`](artifact-analysis.md), [`artifact-report`](artifact-report.md) |
  | 22 | [`artifact-audience`](artifact-audience.md), [`artifact-dimensions`](artifact-dimensions.md) |

- [`artifact-chain-to-draft-report`](artifact-chain-to-draft-report.md) composes the hand-offs into
  one internal draft and holds the chain's acceptance test (CHN11, CHN12).
- Each artifact plan's first chunk declares its part of chunk 14's view vocabulary and chunk 16's
  targets. 14 and 16 keep the frame and the grammar; the artifacts fill them in.
- The stage list was checked against `apps/web/src/lib/workbench-stages.ts:16-19` and
  `prototypes/research-lead-v2/src/model/terms.ts:6`. There are eleven stages: Kontrola is part of
  Vzorek, and Spuštění with Průběh is Sběr dat.

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
  *Landed (with 26c's launcher, the dialog, Zavřít and Escape):* `useWorkbenchLayout`, `Split`'s
  `layout`, `wb--split|drawer|sheet`; `Workbench.layout.test.tsx` (mount counter, draft kept,
  dialog, Escape to the launcher) and `workbench_journey.mjs` at 1280/1100/1099/768/390.
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
     `available`, `unavailable_reason` and the worker's readiness, the newest turn's park reason and a
     read failure; output `ON | WAITING(reason) | OFF | UNKNOWN`, with words (the `REASON` map moves
     here from `LeadPane.tsx:36-50`). `UNKNOWN` (unreadable `/lead`, an older API's 404,
     `LeadPane.tsx:114`) never reads as on; `research_lead_disabled` reads as off; parks read as
     waiting. Only `GET /lead` decides; `/config`'s copy is never read for it.
     **The API's switch alone is not availability.** With the API's switch on and the worker's switch
     or its model keys off, a fresh study answers `available: true` today (`routers/lead.py:356-359`)
     while every turn parks `research_lead_unconfigured`. So `GET /lead` incorporates the worker's
     readiness from the worker composition record (`lead-orchestration#LO12b`, shared with
     `deep-research-web-search#52`), and the reader reads ON only with an explicit worker-ready signal.
     Until that record exists, and whenever the worker's readiness has not been read, availability is
     `UNKNOWN`, never ON: `available: true` without the signal reads as unknown.
  3. **Where it shows.** `LeadLauncher` (26c) shows it, and each stage that lost a start in 26f shows one
     line from it (D13), a `LeadAvailabilityNote` in `rehome/research`. `lead_journey.mjs` with the API's
     switch off: the launcher says vypnutý, the composer takes only typed commands (27b), old turns are
     readable, a stage shows the line and no AI start.
- **27b. The kill switch holds on every Lead start** (Q42, Q43). `approve_request`
  (`application/research_lead.py:683`) raises `LeadUnavailable` when not enabled and `routers/lead.py`
  answers 409 `research_lead_disabled` for `/request`; `decide_edits` stays allowed. `post` (`:402`) with
  the Lead off accepts only `lead-orchestration#LO5`'s matched command kinds, still refusing free text.
  The refusal distinguishes the two kinds of card (D22): a card the Lead model prepared is refused; a
  server-matched `chat_start` card (LO5) stays approvable while the Lead is off, with the same wallet and
  LO15 checks. `GET /lead` adds the worker's readiness from the composition record
  (`lead-orchestration#LO12b`) beside `available`, so 27a's reader can say ON; without the record it
  answers readiness unknown, never ready.
  Tests: a card the Lead model prepared, approved after a switch-off, is 409 `research_lead_disabled` with
  no workflow row and no reservation; **in the same switched-off state a server-matched `chat_start`
  card is approved, writes `chat_start` and passes the same wallet and LO15 checks**; `decide_edits`
  still works; a typed run start with the Lead off writes `chat_start`, while free text is 409; with the
  API's switch on and the worker's off (or its keys unset), `GET /lead` does not report the worker ready.
  The typed path depends on LO5, the readiness on LO12b.
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

## Deep Research cards and starts: the Lead controls Deep Research end to end (2026-10-21)

The owner, 2026-10-21: "the lead should be able to control the whole process". The decisions (Q44
to Q48, his words and their times) and the Lead's half of the work (LO5a.1 to LO5a.4, with
LO6's and LO8's tightening) are in
[`lead-orchestration.md` § Deep Research under the Lead](lead-orchestration.md#deep-research-under-the-lead-2026-10-21).
The pricing half is `deep-research-web-search` 55 (DRL-0). This section holds the UI and workbench
half: 7b, 12a, 23b, 23c and 26f.1. Anchors are `@ 095a3e68` unless stated; `@ cd7af699` is #550.

**Where the chunk lines sit.** 7b and 12a stand under the chunks they refine. 23b, 23c and 26f.1
stand after 24, not beside 23 and 26. #550 rewrites line 23 and #551 replaces 26 and 27 with 26a-27d,
so a line next to either would conflict with them. 23 itself stays the half #550 builds (worker and
research-run cards); 26f.1 refines #551's 26f by name.

### Amended decisions

- **D7, for the two Deep Research kinds** (`lead-orchestration#LO5a.2`). A `design_research` or
  `interpretation_research` card no longer only opens its stage. "Spustit rešerši" calls
  `POST …/lead/turns/{turn_id}/request`, and `approve_request` starts the run on the server with the
  threshold, the live-settings guard and the `lead_job_request` ledger row. `research_run` keeps
  #550's path, through Spuštění's own route.
- **25, narrowed.** Once LO5a.1 and LO5a.2 land, the Lead may prepare Deep Research from any stage.
  25 then means only subject kinds beyond research questions and questions (Audience or Dimensions
  as subjects). Those need new engine subjects, and the engine is frozen (ADR 0021), so 25 stays
  after the MVP (D16).

### The chunks

**7b (DRL-6). Review a Design Research proposal inside the artifact (F-DRL-1).**
- `apps/web/src/lib/api.ts`: `deepResearch.acceptDesignProposal(studyId, runId, itemIds,
  expectedRevisionId, expectedWorkspaceRevision)` on `POST …/runs/{run_id}/design-proposal/accept`
  (`routers/deep_research.py:768-796`; `DesignResearchProposals.accept`,
  `application/design_research.py:90-157`, `EDIT_STUDY` and `APPROVE_GATE`, the item-level stale
  rule, the `design_research` ledger row).
- New `components/rehome/research/DesignResearchReview.tsx`. It lists each item, EVIDENCE or GAP, by
  subject, with its findings' quotes and sources and the research question it informs, and offers
  checkboxes and "Přijmout vybrané". A `stale_proposal` refusal is said through `proposal-items.ts`,
  and after an accept the store reloads (`reload(read, { since })`).
- It is mounted on Návrh and Dotazník, where the subject lives, and opened from the card's
  "Zkontrolovat návrh" (#550's `OPEN_REVIEW_KEY` pattern).
- The Lead may recommend items by id in its reply. It cannot accept them.
- Tests (Vitest):
  - the request body has exactly the ticked items and both revisions;
  - a stale proposal is said in Czech;
  - a GAP item has no checkbox.

  Journey: accept one EVIDENCE item and reload; the item is in the working copy, with a
  `design_research` ledger row.
- It can land before 23b as a stage control, because the accept is a person's gate, not an AI start.
  No kill switch.

**12a (DRL-1). A UI workbench that runs Deep Research on recorded web, with no paid calls (F-DRL-6).**
- `apps/executors/src/aia_executors/workbench.py` `workbench_registry_for` adds the Deep Research
  executors over `deep_research_recorded`'s runtime, with a scripted model transport replaying
  recorded answers (as `apps/executors/tests/test_deep_research_journey.py` does). Both modules
  already refuse outside local and test (`deep_research_recorded.py:57-58`).
- A small fictional exchange file under `tools/ui_workbench/fixtures/deep_research/`: one design run,
  and one interpretation over the fixture project's run. `tools/ui_workbench/workbench.py` sets the
  keys.
- Tests (`apps/executors/tests/test_research_lead_workbench.py`):
  - the registry holds the six steps and the track kind;
  - a run on the fixture completes with a sealed bundle marked `RECORDED_FIXTURE`;
  - no gateway call is priced.

  `layer_check` still forbids naming either module in a deployment.
- Every journey below runs on it with the scripted Lead and asserts zero paid calls: the usage
  ledger's paid rows are unchanged, and every snapshot is `RECORDED_FIXTURE`. `lead_journey.mjs` runs
  on `workbench.py up --fresh` (OI-133).

**23b (DRL-4). Deep Research request and running cards in the conversation.** Every Deep Research run
of the study is a card, however it was started, as #550 does for jobs and runs (`lib/lead-cards.ts`,
`components/workbench/LeadCards.tsx @ cd7af699`). A run started from a turn's card stands with that
turn (`request_decision.run_id`); any other run stands at its creation time.
- **The request card** shows:
  - the purpose ("Rešerše k návrhu" / "Rešerše k výsledkům");
  - the focus (Q45) or the target (Q44) in words, with its connections, and behind a disclosure the
    run, the artifact id and a SHA prefix;
  - the preset (STANDARD by default, QUICK offered; Q46);
  - the Lead's `why`;
  - DRL-0's quote: the ceiling and its breakdown by kind, grouped as model, search (Brave), index
    (Common Crawl's Athena) and free routes, each priced route with its price date and an unknown
    price read as "cena neznámá", never 0;
  - the threshold and the budget line (`budget-line.ts`), and the wallet's remainder once the wallet
    is on;
  - missing live settings: they list the keys in words and the routes that need them, say who fixes
    them ("správce organizace, Nastavení → Hloubkový výzkum") with a link, and disable the card
    before a click (LO12a's pattern).

  Its buttons are "Teď ne" and "Spustit rešerši". The latter goes through `approveRequest`, with
  #550's ask-again loop.
- **The running card** shows:
  - the 64 px orb while a step is RUNNING (`deepResearchRunningStep`);
  - the six steps, with each fan-out track `investigate/<track>` under investigate, and the live feed
    of the selected step (`StepActivityPanel` over `useStepActivity`);
  - the cost spent so far against the ceiling;
  - waits in words: `AWAITING_BUDGET` with `BudgetLift` (`APPROVE_BUDGET`), a runtime park with
    "Pokračovat v běhu", and the egress codes with LO12a's who-fixes-it line;
  - "Zrušit rešerši" (`CANCEL_WORKFLOW`), which keeps what was captured.
- Files: `lib/lead-cards.ts` (`deepResearchCard(run)` and the quote model), `LeadCards.tsx`
  (`DeepResearchCard`), `LeadPane.tsx` (`REQUEST_WORDS` marks both kinds as paid; "Zkontrolovat
  cenu" calls the quote), `Workbench.tsx` (`onRequest` for both kinds and retry; the study's Deep
  Research runs polled into the cards).
- Tests:
  - `lead-cards.test.ts`: each phase's words; the orb only while RUNNING; the tracks listed under
    investigate; an unknown cost reads "náklady nevykázány"; missing live settings disable the card.
  - `LeadPane.test.tsx`: the card asks once at the threshold.
  - `lead_journey.mjs` on 12a: "připrav rešerši k návrhu" gives a design card with a ceiling;
    "Spustit rešerši" gives a running card with the orb and the tracks; the run completes; zero paid
    calls.
- Depends on #550, 12a and `lead-orchestration#LO5a.2`. Cards are display; the kill switch is as
  LO5a.2's.

**23c (DRL-7). The finished card: findings, sources and the report.**
- Every finished card shows:
  - the coverage verdict and the counts (accepted, snapshots, gaps, rejected), with
    `SearchedNothing` when nothing was searched;
  - the first three accepted findings, rendered from `GET …/bundle`, never from model text, each with
    `VerifiedSourceButton` (a person's click, `application/verified_sources.py:47-67`);
  - links to the stage panel and to the bundle in full.
- For design, the card adds "Zkontrolovat návrh" (7b).
- For interpretation, it adds:
  - "Použít ve zprávě", which sets the results page's review through the study's page memory;
  - the state of the report with literature, read from `GET …/report/context`, with "Připravit
    zprávu" and "Schválit zprávu" on `CompleteReport`'s routes. Approval is bound to the artifact id
    the card shows (`requestStored`'s `X-AIA-Artifact-Id` rule), and the self-approval rule applies.
- For a failure, it shows the cause worded by code (D-10) and "Zkusit znovu". An interpretation
  retry refused as `lineage_changed` says so and offers a new start over the current target.
- It reuses `lib/report-status.ts`, with no new rule.
- Tests (Vitest):
  - a bundle with zero accepted findings says so;
  - "Schválit" sends the artifact id the card shows;
  - a refused approval (self-approval) is said.

  Journey: interpretation over the fixture run → the finished card → "Ověřeno, přidat zdroj" → the
  item appears on Znalosti → "Použít ve zprávě" → the report prepared, and approved by a second
  fictional member where self-approval is off.
- Depends on 23b, and on 7b for the design link. No kill switch, since these are people's own gates.

**26f.1 (DRL-5). The Deep Research half of 26f.**
- Removed in every layout:
  - `DeepResearchPanel.tsx:124` (start) and `:139` (retry);
  - `InterpretationResearch.tsx:145` (start, with its preset select) and `:161` (retry).
- Their panels stay as read-only views of the runs: the state, the bundle, "Ověřeno, přidat zdroj",
  "Použít ve zprávě", "Zrušit", and the waits (resume, budget lift). None of these starts paid work.
  The stage says where to start instead ("Rešerši připraví Vedoucí výzkumu", `AskLead`, #550).
- 26f's static guard adds `deepResearch.start`, `deepResearch.interpret` and `deepResearch.retry`.
  Their only callers are then the Lead's cards and the run card's retry.
- Tests:
  - the guard;
  - `ResearchScreen.workbench.test.tsx`: no Deep Research start on Dotazník or Výsledky;
  - `lead_journey.mjs` at 1440 and 390 px (until 26c's drawer exists, 1440 and 1100): Deep Research
    is startable only through the Lead;
  - a direct HTTP `POST …/deep-research/runs` with the page's token meets the same gates (26e's
    pattern).
- **Depends on 23b and on `lead-orchestration#LO5a.3` (Q48: the buttons go only once typed starts
  work with the Lead off).** While the classic frame exists, it sits behind `leadOwnsAiStarts`, and
  27c deletes the predicate.
- No kill switch, by D-12. `lead-orchestration#LO5a`'s acceptance is ticked with it.

### Findings

- **F-DRL-1. No web path turns a Design Research proposal into a Design Revision.**
  - Anchor: `apps/api/src/aia_api/routers/deep_research.py:768-796` and
    `application/design_research.py:90-157` exist. The only web reference to the proposal is the GET
    at `apps/web/src/lib/api.ts:1412 @ 095a3e68`.
  - Reproduction: `git grep -n 'design-proposal' 095a3e68 -- apps/web/src` lists api.ts:1412 and a
    test's GET stub alone.
  - Consequence: ADR 0021's checkpoint 1 ("human-reviewed proposals → a new Design Revision") cannot
    be completed in the product. A finding can only be read.
  - Smallest fix: 7b.
  - Test: 7b's Vitest that the review posts the ticked `item_ids` with both expected revisions, and
    its journey step.
- **F-DRL-6. The UI workbench cannot run Deep Research at all.**
  - Anchor: `apps/executors/src/aia_executors/workbench.py:158-173 @ 095a3e68` composes no Deep
    Research runtime, so a run parks at plan.
  - Reproduction: `make ui-workbench`, `make ui-fixtures`, then start Design Research on a fixture
    study. The run waits at plan.
  - Consequence: no browser journey can prove D-12's acceptance with zero paid calls.
  - Smallest fix: 12a.
  - Test: 12a's "a run on the fixture completes with a sealed bundle marked `RECORDED_FIXTURE`".

### Doc follow-up (Deep Research cards and starts)

- `open-items.md`: number F-DRL-1 (owner 7b) and F-DRL-6 (owner 12a).
- `CLAUDE.md` map, `src/components/rehome/research/`: `DesignResearchReview.tsx` (7b), once built.
- The register rows for 7b, 12a, 23b, 23c and 26f.1, in this PR's description.
