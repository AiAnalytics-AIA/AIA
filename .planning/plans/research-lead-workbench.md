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
  - "[ ] 26. The Lead stays accessible at every width (D20, MVPQ-11): the workbench serves under 1100 px with the Lead as a compact drawer or a stacked layout, the manual AI starts are removed in every layout, tested at 1099, 1100, 768 and 390 px, by keyboard, focus and Escape with a return to the targeted artifact, with a stale card refused, and by a direct request"
  - "[ ] 27. Switch-off and rollback (D20): actual availability is stated; the compact Lead stays reachable while its backend is enabled, a genuinely disabled backend stays disabled and says so, with no alternate AI start and no bypass of a kill switch; every layout uses the same card, plan, wallet and server-confirmation paths"
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
- **D13. AIA's data only.** Where AIA has nothing behind a part of an artifact, the part says so in
  words ("V AIA zatím není", or the backend's own reason), never a placeholder that reads like data.
- **D14. The journey grows with the artifacts.** Chunk 12 lands first, and each artifact PR adds its
  own steps to `workbench_journey.mjs` / `lead_journey.mjs`.
- **D15. Every AI action goes through the Research Lead** (owner, 2026-10-19; `overview.md` MVP-8).
  The manual AI buttons (AI pomoc, the stage cards' "Navrhnout", the job panel's starts) are removed.
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
- **`.planning/open-items.md`.** F1 and F2 above; F3, closed by its fix.
- **`CLAUDE.md` § 2**, `domain/workspace.py` / the working content paragraph: a save naming no
  revision is not stale over a working copy that is still the bare template a server writer
  saved (`edited_from_current`).
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
