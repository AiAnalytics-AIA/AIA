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
  - "[ ] 11. The command registry: the workers the Lead may call, each with its prompt and price, behind approve_request (ledger and spend limit already built)"
  - "[ ] 12. Workbench journey: four widths, keyboard, focus modes, a Lead turn on recorded answers, zero unintended paid jobs"
  - "[x] 13. Design V3 in the repository (prototypes/research-lead-v3, its text) and its chunks in this plan"
  - "[ ] 14. The Lead's view vocabulary: a closed, per-artifact set of display operations the Lead may run on the artifact pane"
  - "[ ] 15. The artifact frame: header (inputs, feeds, readiness, workers), Pracovní kopie / Historie / Původ, the revision stepper"
  - "[ ] 16. Pointing at the artifact: the Vidí chip, the target button and @ over every artifact's elements"
  - "[ ] 17. Questionnaire artifact, its proposal shown in it (where chunk 7 lands)"
  - "[ ] 18. Brief and Research design artifacts"
  - "[ ] 19. Sample and Fieldwork artifacts"
  - "[ ] 20. Results and Sociomap artifacts"
  - "[ ] 21. Analysis and Report artifacts"
  - "[ ] 22. Audience and Dimensions artifacts"
  - "[ ] 23. Worker and Deep Research cards in the conversation, each opening the artifact it changes"
  - "[ ] 24. 'Continue until you need me' over chunk 11's command registry, stopping at every gate"
  - "[ ] 25. Deep Research reachable from every stage as a capability"
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

## Design V3: an artifact per step, steered by the Lead (chunks 13-25)

The product owner's V3 design ([`prototypes/research-lead-v3`](../../prototypes/research-lead-v3/README.md),
2026-10-19) keeps the split and the Lead and changes the right side: each research step becomes
**its own artifact**, designed for the step, and the Lead **controls that 60 %**. The design's
visible text is under `prototypes/research-lead-v3/text/`, cited here as `artifacts.txt FRAME n`.

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
- **D12. Supersedes D1 for the artifact bodies.** Each step's artifact is rebuilt to V3 inside the
  workbench, one or two per PR, over AIA's own data and routes (never the design's fixtures). The
  classic layout (switch off, or under 1100 px) keeps today's screens.
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
  closes F1: no paid design job starts outside the Lead's path.
- **D16. Release scope** (owner, 2026-10-19; MVP-3). The Lead and all eleven V3 artifacts are
  release-blocking (12, 11, 14-23). The autopilot (24) and Deep Research from every stage (25) come
  after the MVP; 24 needs an ADR for the Lead's own permission scope first.
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

**The artifacts.** What V3 shows, what AIA has behind it, what is missing. "Backed by" names modules
from the CLAUDE.md map; each chunk anchors its claims in its first commit, and until then an entry
is a **hypothesis**.

| Chunk | Artifact (V3) | What it shows | Backed by in AIA | Missing |
|---|---|---|---|---|
| 17 | Questionnaire (`FRAME 3`) | Outline by section, counts and minutes; each item's type, time, objective; a proposal inline: removed with reason, merged, reworded, locked Sociomap inputs | Questionnaire stage, agent jobs, `proposal-diff.ts`, `research_trace`, questionnaire import | Per-item time estimate; "serves no objective" as a reason the proposal carries |
| 18 | Brief (`FRAME 1`) | Goal, problem type, materials with data class, context, readiness with an assumption carried on | Brief stage, attachments, client knowledge, classification (#487) | Assumptions (A1…) tracked across stages |
| 18 | Research design (`FRAME 2`) | Breadth options with N and trade-off; objectives, research questions, hypotheses; comparable sets, locked Sociomap input; follow-up questions | Plan stage, `research_plan`, tracked sets, Sociomap declarations | Breadth as a choice the design records |
| 19 | Sample (`FRAME 6`) | N with reason, quotas by code, method support, run ceiling against the spend limit | `SampleView`, `support_forecast`, `run_cost`, readiness | Quotas before a run |
| 19 | Fieldwork (`FRAME 7`) | Origin banner, run state and heartbeat, counts, respondent grid, quota fill, steps, spend, provenance | Progress, step activity, budget line, `respondentReceipt` | Per-respondent and quota fill from the fieldwork step's events |
| 20 | Results (`FRAME 8`) | Each question with support and intervals, evidence marks, suppression said | Results Data, `result-reading.ts` | — (re-layout) |
| 20 | Sociomap (`FRAME 10`) | Top view / 3D, object and pair detail, ranked list with ties, method and provenance, "Zeptat se Vedoucího na …" | `ObjectMapView`, `object-map-view.ts`, Sociomap register | Asking the Lead about an object or pair (chunk 16) |
| 21 | Analysis (`FRAME 9`) | Three registers apart (deterministic, AI interpretation, external context); modules with state; a gate refusal shown | Analysis view, `needsRepair`, admitted claims, Interpretation Research | A Lead interpretation as an unapproved register entry |
| 21 | Report (`FRAME 11`) | Outline, a proposal on a draft with Clean / Show changes, evidence on the page | `CompleteReport`, `report-status.ts`, report approval | A report wording proposal (a report worker) |
| 22 | Audience (`FRAME 4`) | Source, population, target group with quotas, assumptions with Deep Research evidence, impact before saving | Audience stage, `/population` routes, Design Research | Cost and time of a new run (V3 itself says the backend lacks it); population size; own and special audiences |
| 22 | Dimensions (`FRAME 5`) | Sociodemographics, recommended dimensions with what uses them, catalogue, own dimension proposed to client knowledge | Dimensions stage, `persona_topics`, materialize | "Used by" links to segments and hypotheses |

**Order.** 12 (the journey), then 11 (the command registry: which workers the Lead may call, each
with its prompt and price; most of the paid path is built, `mvp-consolidation.md` §6), then 14-16
(vocabulary, frame, pointing: every artifact needs them), then 17-22 (those AIA backs first, Audience
and Dimensions last; each removes its stage's AI buttons, D15), then 23. 24-25 after the MVP (D16).
The backend each chunk needs is in `.planning/mvp-consolidation.md` §6.

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
- **`CLAUDE.md` § 2**, beside `src/components/workbench/`: `prototypes/research-lead-v3/` is the
  design the workbench's artifacts follow (2026-10-19); the navigator stays on top.
- **ADR 0026**, under *Accepted with*: the Lead steers the artifact pane through a closed set of
  display operations (D10); its gates are unchanged.
