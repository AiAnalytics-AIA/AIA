---
status: in-progress
chunks:
  - "[x] LO0. The contract ADR and the money vocabulary: wallet cap, `budget_usd`, `spend_confirm_usd`, the client ceiling, `clients.budget_usd`, OI-64, one precedence"
  - "[x] LO1. The wallet (M4): `study_wallets`, `_raises`, `_charges` and `clients.wallet_ceiling_usd`; charges for paid work including Deep Research"
  - "[ ] LO2. A typed `start_run` with no `confirm_cost_usd`, and an import rule that a plan step cannot reach the confirming start"
  - "[ ] LO3. `lead_plans` and `lead_plan_steps` (M5), the plan authority capability issued by `ScopeResolver`, the `lead_plan` workflow type, behind `AIA_LEAD_PLANS_ENABLED`"
  - "[ ] LO4. The plan card: the steps (including "start fieldwork, ceiling X USD"), approved once, stopping at every gate it does not cover"
  - "[x] LO5. Direct human chat start: the typed command the server matches, ledger `chat_start`, the model not in the path"
  - "[ ] LO6. The continuation turn: a finished step enqueues a Lead turn with typed results; no polling"
  - "[ ] LO7. The Lead's context layers per ADR 0026 decision 2: readiness, question outlook, what changed since its last turn, other people's changes, and the execution state (status, park code, spend, selection receipt, QC)"
  - "[ ] LO8. `ResultsContext`: type, class (`MaterialRule` for results, module text, maps, report text), lineage, bound, an external-evidence slot labelled L; and the decision on a read tool against ADR 0026 decision 3"
  - "[x] LO9a. The worker contract, early (W0, the first deliverable of `research-lead-workbench` 11): `LeadWorkerSpec` as a type, one row per worker (id, closed task, context layer, data-class rule, capability, reservation, prompt id and pin, switch, card kind, result kind), with its fixture"
  - "[ ] LO9c. A results-worker job shape (W2, before LO9b): a workflow type and step kind keyed on (run_id, target), frozen inputs by artifact id and SHA-256, its own context builder and executor behind its own switch, sharing the worker row, prompt pin and usage ledger"
  - "[ ] LO9b. The three new workers as rows (W3): a `REPORT_WRITING` binding, result kinds and accept destinations, per-worker price and keys"
  - "[x] LO10. `approve_request` bound to the revision shown on its card, and a clean error where the 96 KB Lead context meets the 64 KB agent limit"
  - "[ ] LO11. The Lead over time (M7): `researcher_lead_signals`, proposed updates the researcher approves each, a reader and rollback for Lead file revisions; no handover or admin read (D-32 to D-34); a departed member's Lead sealed, then deleted at the retention end (Q14)"
  - "[x] LO12a. The route-class refusal says who fixes it (W0): on the job error, the Lead pane, source proposals and Progress, from the refusal codes that exist today, with a link to the runbook; static copy, no read of the route"
  - "[ ] LO12b. A pre-flight read of the AI route (W1): the worker publishes a composition record the API, Settings and the Lead pane read (shared with `deep-research-web-search#52`), and the new refusal reasons"
  - "[ ] LO13. Client-level paid AI (source proposals, `clients.budget_usd`) recorded as an explicit exception to "every AI action goes through the Lead" in AC-02"
  - "[ ] LO14. The Lead's cost per turn measured, and an `AIA_LEAD_*` kill switch and budget line"
  - "[x] LO16. The approval ledger's subject types (lane migration M3, W0, the first migration): `approval_decisions.subject_type` extended with `wallet`, `lead_plan`, `plan_step`, `chat_start`, `data_contract`, `map_snapshot` and `sociomap_unlock`; S3 writes it"
  - "[x] LO15. Server spend enforcement (W0): `ResearchAgentJobs.start` and `rebuild` apply `spend_confirm_usd` as `ResearchRuns.start` does, and record the confirmation in the ledger; tested through direct HTTP start and rebuild and through the Lead's approve path"
  - "[ ] LO5a. Deep Research from the Lead: a plan-step kind and a typed chat start, priced by deep-research-web-search 55's ceiling (D-12); split into LO5a.1-LO5a.4 (2026-10-21), this line holds the acceptance and is ticked when they and research-lead-workbench 26f.1 have landed"
  - "[ ] LO5a.1. The Lead's Deep Research requests and context (DRL-2): a preset (QUICK or STANDARD, STANDARD by default), a design focus on named research questions, an Interpretation target from a code-built candidate list over every result kind of ADR 0021, Q44 (the research-questions module by default), a retry request; the deep_research and targets layers"
  - "[ ] LO5a.2. A Lead card starts Deep Research on the server (DRL-3): approve_request starts Design and Interpretation Research and their retry, priced by deep-research-web-search 55, with the threshold, live settings and ledger row; amends research-lead-workbench D7 for the two kinds"
  - "[ ] LO5a.3. Typed Deep Research starts (DRL-8, on LO5): start, retry and stop matched by code with no model in the path, ledger chat_start, a wallet charge at the ceiling; works with the Lead off"
  - "[ ] LO5a.4. Deep Research as plan-step kinds (DRL-9, on LO3/LO4): design_research and interpretation_research steps, a target fixed or relative to an earlier step resolved when the step starts, parked when its module ended BLOCKED"
  - "[ ] LO12c. The composition digest stored on each run and served over HTTP (D-09; the record #513 called MP6b)"
  - "[ ] LO17. Stopping the Lead: cancel a running turn, withdraw an approved plan (the current step finishes or is cancelled, nothing after it starts), with the workbench build line (D-18)"
  - "[ ] LO18. The Lead's turns stream, take a file from the composer, and comment unprompted after the researcher pauses editing, each such comment a paid turn inside the wallet (D-39)"
  - "[ ] LO19. A study's context file: a Markdown file per study, built by code from the study's shared state and refreshed on every change, read by every researcher's Lead in that study as its study layer (Q5)"
  - "[ ] LO20. Hledat na webu: the Lead's governed web search through RetrievalGate, several results with inline citations in the turn, OPEN clients without a card and CLASSIFIED clients behind a plan card, each search charged to the wallet (Q6, Q24)"
  - "[ ] LO21. Registry-driven actions (CARD-1, Nigel 2026-10-22): the Lead proposes actions: [{worker_id, args}], several per turn, from one registry; split into LO21a-LO21e, this line holds the acceptance"
  - "[ ] LO21a. The action registry: each action an args schema, a Czech description and an example; LeadOutput's allowed action union generated from it at startup"
  - "[ ] LO21b. The prompt's action section generated from the registry and filtered per turn: off, over budget or not permitted for the study left out"
  - "[ ] LO21c. One generic card renderer keyed on card_kind with per-kind slots; each action its own ledger decision and approval route"
  - "[ ] LO21d. The four request types (agent_job, research_run, design_research, interpretation_research) migrated to actions; a stored request still reads"
  - "[ ] LO21e. The plan kind: one action whose steps reference registered actions, LO4's card (steps shown, one approval, live state per step)"
  - "[ ] LO9d. Every stage worker gets its declared inputs: the upstream accepted items, readiness, question outlook, research trace, earlier proposals' reasons and dismissals, and the newest sealed Deep Research bundle's findings by reference, labelled external context (Q12)"
---
# Lead orchestration: the wallet, the plan card, the continuation turn and the Lead over time

The orchestration the prototype and the owner describe: a per-study wallet, a plan approved once, a chat start, a continuation turn that returns typed results to the Lead, its context layers, its workers and its lifecycle. Written 2026-10-19 from `.planning/evidence/mvp-master-traces/trace-4-lead-governance.md` and `trace-2-sample-execution.md`.

**Owner: S1.** Takes the gap rows G1, G11, G12, G13, G15, G16, G17, G20, G39, G43 and interfaces I1, I3, I4, I22, I23 of `mvp-master-plan.md` §6.1 and serves AC-02, AC-03, AC-04, AC-15 and gate I-1.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- A per-study wallet for paid work, set by the researcher up to a client or organization ceiling; everything inside it, including the fieldwork run, no expiry until the study closes, priced Deep Research inside it (F13, Q14).
- The researcher approves a plan once and the Lead runs its steps; a plain chat request from a person starts a run inside the wallet without a plan card; a Lead-initiated run needs an approved plan (Q14, Q25).
- Each researcher has their own Lead, private to them; an organization admin can read its files and notes, never its turns, and hand it on as a copy with personal notes removed; the Lead proposes updates to its own files and the researcher approves each (Q18, Q19, Q26).
- Two meters in the header, the rest on click (Q20); two to three parallel jobs (target architecture).
- The spend limit is a **confirmation threshold** (`spend_confirm_usd`, null means never ask) and the cap is `budget_usd`; the wallet is defined against `budget_usd` and never against the threshold (the owner, 2026-10-19, after the traces).

## Chunks

**LO0. The contract ADR and the money vocabulary: wallet cap, `budget_usd`, `spend_confirm_usd`, the client ceiling, `clients.budget_usd`, OI-64, one precedence**  
Supersedes MVP-13 in the ADR text. **The name (the product owner, 2026-10-20):** the study's spending cap that an approved plan runs inside is the **wallet** in code and plans (`study_wallets`, `study_wallet_raises`, `study_wallet_charges`, `clients.wallet_ceiling_usd`, "wallet cap") and **Peněženka** in the Czech UI; it was called the envelope until then. `budget_usd` and `spend_confirm_usd` keep their names. The other envelopes (the Sociomap terrain envelope, Deep Research's orchestration envelope, the error-tracking envelope, the investigator's output envelope) are different things and keep theirs. Corrects the architecture and cohesion statements that call the spend limit a hard stop. Test: a document check that the word "hard stop" is not applied to `spend_confirm_usd`. Interfaces I4.

**LO1. The wallet (M4): `study_wallets`, `_raises`, `_charges` and `clients.wallet_ceiling_usd`; charges for paid work including Deep Research**  
The data for the two meters: spent against `budget_usd`, and the wallet remaining on click, with Czech labels distinct from the confirmation threshold's. Server-computed ceilings, holds, settlement and concurrent accounting are preserved (a start never exceeds the cap; an unknown cost counts as its ceiling). Test: a raise inside the client's wallet ceiling is the researcher's; one above it is refused, naming who can raise the ceiling (an organization OWNER or ADMIN; D-03, no approver queue); a charge above the wallet parks, never fails.

**LO2. A typed `start_run` with no `confirm_cost_usd`, and an import rule that a plan step cannot reach the confirming start**  
`ResearchRuns.start` takes the confirmation as a function argument (`research.py:724-742`), so "a plan authority holds no `APPROVE_GATE`" does not protect it. The Run stage button, the plan card and the chat start all call the one start with their pins (persona source, child, acknowledgement). Interfaces I3.

**LO3. `lead_plans` and `lead_plan_steps` (M5), the plan authority capability issued by `ScopeResolver`, the `lead_plan` workflow type, behind `AIA_LEAD_PLANS_ENABLED`**  
The riskiest piece: the most tests and a kill switch. A step that reaches a gate the plan does not cover parks.

**LO4. The plan card: the steps (including "start fieldwork, ceiling X USD"), approved once, stopping at every gate it does not cover**  
The prototype's decision card for a run start is this card with one item. The minimum usable plan card lands with LO4 in W1 inside the current Lead pane; it is part of I-1. `research-lead-workbench` 23 adds the richer worker/Deep Research cards in W4 and is not the first UI for plan approval. This chunk owns the contract and ledger rows (`lead_plan`, `plan_step`, M3).

**LO5. Direct human chat start: the typed command the server matches, ledger `chat_start`, the model not in the path**  
The security condition: a start is authorised by a person's own typed command matched by the server, never by a model's interpretation of text. Inside the wallet only.

**LO6. The continuation turn: a finished step enqueues a Lead turn with typed results; no polling**  
Turns are person-started only today (`research_lead.py:763-790`). A result reaches the Lead as an artifact reference plus fields code has validated, never a worker's free text (a summary derived from web text is an injection path). Test: a step finishing wakes one turn with its results; a failed step wakes one with the park reason.
**Deep Research (DRL-10, 2026-10-21):** a Deep Research run that finishes, fails or parks wakes one
turn with typed fields only (run id, purpose, status and park code, counts, `quality_status`, actual
cost, the bundle's SHA-256 and its finding ids; no web text by this path), and a research run whose
analysis completes wakes one whose context offers its Interpretation candidates (LO5a.1), so the
scripted Lead can prepare an interpretation card. Tests: a completed Deep Research run's turn holds
its counts and ids and no quote text; a park wakes one with the code; a completed analysis lets the
scripted Lead prepare an interpretation card. Detail in *Deep Research under the Lead* below.

**LO7. The Lead's context layers per ADR 0026 decision 2: readiness, question outlook, what changed since its last turn, other people's changes, and the execution state (status, park code, spend, selection receipt, QC)**  
`freeze_context` has none of these (`domain/research_lead.py:803-819`). The Lead's answer to "Kde jsme?" is built from them.

- **Delivered beside LO7: external context, never evidence** (evidence-integrity 7, the Lead's half;
  `feature/lead-external-context`, after #669).
  - **The switch:** `AIA_AI_ANALYSIS_EXTERNAL_CONTEXT`, the analysis's own, off by default. With it
    on, `POST …/lead/turns` gives the turn the artifact store (`ResearchLead.external_store`).
  - **The layer:** `_freeze` reads the Study's newest finished Design Research bundle through the
    analysis's reader (`ResearchRuns.design_research_pin`, then
    `analysis_results._external_context`: pinned, seal-verified, Class C findings only). It
    freezes them as the layer `external_context_not_evidence` after the runs, with its note and
    pin.
  - **When it cannot be read:** a bundle that does not read is said in the layer (`unavailable`),
    never read as no context and never stopping the turn.
  - **Numbers:** `citable_context` leaves the layer out, so `lead_contract` refuses a figure taken
    from it like any number the study's context does not hold.
  - **Classification:** `context_classification` counts it as Class C (`bundle:public_findings`).
  - **Off:** the context is byte-identical to before.
  - **Tests:**
    - `test_research_lead.py` "external context …" (the layer, the refused figure, the class);
    - `test_research_lead_application.py`
      `test_external_context_is_frozen_only_when_switched_on_and_pinned`;
    - `test_research_lead_api.py`
      `test_a_turn_reads_external_context_only_with_the_analysis_switch_on`.

**LO8. `ResultsContext`: type, class (`MaterialRule` for results, module text, maps, report text), lineage, bound, an external-evidence slot labelled L; and the decision on a read tool against ADR 0026 decision 3**  
Written in **W1**, not W2. S2 and S3 write providers against it. Test: a result with Class A lineage is refused by a Class-C-only route. Interfaces I1.
**Deep Research's provider and the one door for external numbers (DRL-11, 2026-10-21):** the L slot's
Deep Research provider carries the study's newest sealed bundle(s) by reference (each accepted
finding's claim, quote, source title and URL, source class, verifier verdict and injection flag;
gaps; rejected findings by reason code), bounded with omissions named, classed by `MaterialRule`;
LO9d's stage workers read the same provider. `ground_edits` refuses an edit whose number appears in
the context only in L: an external number enters a design only through
`DesignResearchProposals.accept` (ADR 0021). The web renders an `evidence:<id>` citation's quote and
source from the bundle, never from the model's text. Tests: a reply citing a finding renders the
bundle's quote; an edit carrying a number found only in a finding is refused; a hostile page's text
(`deep-research-web-search` chunk 45's set) in L changes no request or edit.

**LO9a. The worker contract, early (W0, the first deliverable of `research-lead-workbench` 11): `LeadWorkerSpec` as a type, one row per worker, with its fixture**  
One row defines a worker once: id, closed task, context layer, data-class rule, capability, reservation, prompt id and pin, switch, card kind, result kind (`mvp-cohesion.md` F5). Chunk 11's command registry and the W1 artifact chunks depend on this row; the three new workers are rows, not three designs. Test: a worker with a missing field is refused at registration.

**LO9b. The three new workers as rows (W3): a `REPORT_WRITING` binding, result kinds and accept destinations, per-worker price and keys**  
The three workers (map interpreter, report writer, straight-liner check) have no binding, no accept path and no price today. The accept destinations are `report-delivery#RD6` and `run-qc-and-checkpoint#RQC4`. **One more worker may follow (`assumptions-and-open-answer-coding#AOC7`):** if the coding method lets a model propose codes, a twelfth row joins here; the eleven are the baseline of AC-03 and nothing is claimed present because a slot could do it. **Prerequisite for the report writer's semantic edits:** ADR 0026 decision 4 requires an ADR and a deterministic admission rule for semantic report edits before any command exists; the feature is settled, the ADR is the work (`report-delivery#RD6`).

**LO16. The approval ledger's subject types (lane migration M3, W0, the first migration)**  
`approval_decisions.subject_type` is a check constraint; every later migration and consumer (`LO1`, `LO3`, `LO5`, `working-copy-edit-ops#WCE8`, `report-delivery#RD4`, `client-data-in-analysis#2`) writes one of these subjects, so one migration extends it once and no later migration edits the same constraint. S3 owns the lane and writes it; the consumers write only their rows. It lands with its repository change, a round-trip test, an isolation test and its `layer_check` rule. Gap G43.

**LO15. Server spend enforcement (W0): `ResearchAgentJobs.start` and `rebuild` apply `spend_confirm_usd` as `ResearchRuns.start` does, and record the confirmation in the ledger**  
`ResearchAgentJobs.start` (`application/research.py:1311-1407`) reads no `spend_confirm_usd`, while `ResearchRuns.start` does (`:739`); the only check on a design job today is in the Lead's approve path (`application/research_lead.py:678-760`). Removing the manual buttons (D15) is a UI change and does not enforce a server rule: `mvp-cohesion.md` F5 adopts this check as the first code change, and `research-lead-workbench` F1 is no longer an owner decision. `budget_usd` is the cap; the wallet and the `spend_confirm_usd` confirmation are distinct. Test: a direct HTTP start and a rebuild above the threshold are refused without a covering confirmation and write the ledger row with one; the Lead's approve path still passes; a start under the threshold is unchanged. Interfaces I4.

**LO10. `approve_request` bound to the revision shown on its card, and a clean error where the 96 KB Lead context meets the 64 KB agent limit**  
`approve_request` submits whatever the working copy is at approval time, unlike `decide_edits`, which needs `base_revision`. Test: approving a card whose revision moved is refused with a message, not a 500.

- **Landed** (`feature/lead-card-revision`).
  - **The card's revision.** `ResearchLead.approve_request` reads the working revision before it
    submits anything. The card is stale (`LeadCardStale`, 409 `stale_card`, details
    `current_revision` and `turn_revision`) when the working copy was saved past the revision the
    turn was written from. Saves that are only accepts of this turn's own edits do not count
    (`_only_own_accepts`, from the `lead_edit` ledger rows' `workspace_revision`).
  - Accepting what the card came with is part of the card. A person's save, or another turn's
    accept, is not.
  - A stale card starts only when the request names the current revision (`workspace_revision`),
    the person's yes. The web asks once (`STALE_CARD_QUESTION`) and approves again naming it.
    This is the knowledge approval's rule (F-K1: a stale edit applies only when the reviewer
    names the current revision).
  - Refusing outright was the other choice. It was rejected because re-asking the Lead is a paid
    turn, and the person's own small edit would cost one.
  - The working copy is read once, before the check, and that revision is the one submitted
    (review of LO10). A save landing between the check and the submit makes the submit refuse
    (409 `stale_revision`, nothing started); the job never runs on a revision nobody checked.
  - **The 64 KB bound.** `context_snapshot` raises `AgentContextTooLarge` (a `ValueError`, so
    the agent-jobs route's `invalid_agent_input` 422 still holds). The card's route answers 422
    `agent_context_too_large` instead of a 500, and the pane says it in words.
  - Tests:
    - `apps/api/tests/test_research_lead_api.py`:
      `test_a_card_whose_design_moved_waits_for_the_persons_yes_on_the_current_one`,
      `test_accepting_the_cards_own_edits_leaves_it_approvable`,
      `test_a_save_landing_after_the_check_does_not_change_what_the_job_runs_on`,
      `test_a_study_too_large_for_a_design_job_is_refused_by_name_not_a_500`.
    - `tools/ui_workbench/lead_stale_journey.mjs`: "a card whose design moved asks before it
      starts, and on a yes starts on the current revision".

**LO11. The Lead over time (M7): `researcher_lead_signals`, proposed updates the researcher approves each, a reader and rollback for Lead file revisions; no handover or admin read (D-32 to D-34); a departed member's Lead sealed, then deleted at the retention end (Q14)**  
File revisions have no reader today (`revisions()` has no caller). Turns stay private (Q26). A Lead is never handed over and no admin reads another researcher's Lead files (the owner, 2026-10-20, D-32 to D-34; the earlier "admin read and handover" is withdrawn). Another member's ability to accept a proposal is **not** a Lead-lifecycle matter and is not decided here: Q16 makes proposals shared, and `working-copy-edit-ops#WCE6` builds it (gap G42).

**LO12a. The route-class refusal says who fixes it (W0): static copy on the four surfaces**  
The refusal surfaces in the job error, the Lead pane, source proposals and Progress, and none says an operator fixes it (the AI route's classes are set in SSM, not on Settings, which is read-only). The copy is keyed by the refusal codes that exist today (`egress_route_not_approved_for_class` and its siblings) and names the operator step and the runbook; it reads nothing and needs no composition record. Test: each code on each surface renders its who-fixes-it line. Interfaces I24.

- **Landed** (`feature/route-refusal-who-fixes`). `apps/web/src/lib/route-refusal.ts` maps the six
  refusals the route's settings decide (`egress_` + `route_not_approved_for_class`,
  `retention_unspecified`, `residency_violation`, `training_exclusion_missing`, `no_approved_route`,
  `route_provider_mismatch`) to one line: the operator fixes it, by which SSM parameter, under
  `deploy/develop/README.md`, and Settings cannot change it.
  - Not on the list: `egress_unclassified_material` (an operator's classification, not the route),
    `licence_undetermined` (the data owner) and the budget codes (the researcher).
  - The four surfaces append it: the Lead pane (`leadReasonWords`), the job panel
    (`agentJobUpdate`, `followAgentJob`), source proposals (`proposalsLine`) and Progress
    (`waitingDetail`, and `stepProblem` for Deep Research).
  - A run step had no code to key on: its message is free text, and the gate's code stayed in the
    attempt's error. `ResearchStepResponse.error_reason` and Deep Research's `DeepResearchStep`
    now carry that code, or null when it is not a code (`_code`).
  - `lead-availability.ts` now re-exports the pane's `leadReasonWords` instead of keeping a copy,
    closing its TODO(#547).
  - Tests: `route-refusal.test.ts`; on each surface, `lead.test.ts`, `research-agent-jobs.test.ts`,
    `source-proposals.test.ts`, `research-execution.test.ts`; the API test
    `test_fieldwork_without_the_ai_runtime_waits_visibly_and_nothing_downstream_runs` and
    `test_a_step_passes_on_a_stored_code_never_free_text`, and Deep Research's
    `test_a_run_parked_for_the_runtime_goes_on_when_a_person_resumes_it`, with `reason-words.test.ts`.
  - Not a browser journey: the workbench has no route to refuse (its fieldwork is fictional code),
    and making one refuse would mean building a refusing gateway into the workbench for one line of
    static copy.

**LO12b. A pre-flight read of the AI route (W1)**  
The API cannot evaluate class, so the worker publishes a composition record the API, Settings and the Lead pane read (shared with `deep-research-web-search#52`, whose Reach panel is the other consumer, and with `run-qc-and-checkpoint#RQC8`). It lands in the same row as 52 (E12). The Lead pane gains `retention_unspecified`, `residency_violation` and `training_exclusion_missing`. Settings is read-only and stays so. Interfaces I15.

**LO13. Client-level paid AI (source proposals, `clients.budget_usd`) recorded as an explicit exception to "every AI action goes through the Lead" in AC-02**  
A wording change to the criterion, made with the acceptance harness, not a behaviour change. Interfaces I23.

**LO14. The Lead's cost per turn measured, and an `AIA_LEAD_*` kill switch and budget line**  
The prototype's own documentation lists the unmeasured cost per turn as a gap to production.

## Open: owner clarifications

None here. The wallet sits beside `spend_confirm_usd`, which stays a per-start confirmation (settled; `mvp-master-plan.md` §11.2).


## Execution predecessors (2026-10-20)

LO0, LO9a, LO12a, LO15 and LO16 are W0; LO1-LO8, LO10, LO12b, LO13 and LO14 are W1; LO11 is W2;
LO9b is W3. LO10's card-revision check precedes the first actionable card, not the final workers.
LO7 uses WCE4's change feed and RQC7's events; unavailable result providers are typed unavailable,
never guessed. LO11's persistent personal lifecycle is later work; basic per-researcher turn privacy
must already pass AC-01 in W1. LO14's measured turn cost requires approved live activation; the
zero-cost composition/limit tests can precede it. LO13 records only the exception the owner accepts.
See `../mvp-execution-contracts.md`; no implementation checkbox changes here.

## Cross-check additions (2026-10-20)

From the independent cross-check of the master plan against the code (`mvp-master-plan.md` §6.1, G47-G57). Anchors are `@ 085abe0`.

**LO9c. A results-worker job shape (G47, X2).** The map interpreter, the report writer and the straight-liner check cannot be `research_agent` actions: a `research_agent` job is keyed on a Design Revision and carries a design snapshot (`application/research.py:1311-1356`), and `ResearchAction` is a closed eight-member enum (`domain/research_agents.py:35-43`). This chunk builds the second shape: a workflow type and step kind keyed on (run_id, target), a frozen-input payload (artifact ids and SHA-256, as `FrozenLineage` does), its own context builder, a service found only through the Study, and an executor behind its own `AIA_AI_RESEARCH_WORKERS_*` switch. It shares `LeadWorkerSpec`, the prompt pin and the usage ledger; LO9b then adds only rows. Test: a job for run R and a map target is refused for another Study's run, and the executor verifies the payload hash.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunks.**

- **LO5a (W1, in E26 with E12).** D-12: Deep Research starts as a plan-step kind and as a typed chat
  start, with `deep-research-web-search#55`'s ceiling; `research-lead-workbench#26` keeps no Deep
  Research button as an exception. I22 names it. Test: after #26, at 1440 and 390 px, Deep Research is
  startable through the Lead only.
- **LO12c (W1, after LO12b).** D-09: AC-14 is reworded to typed settings plus a composition digest
  (AI runtime, model binding, switches) stored on each run and returned by
  `GET …/research/runs/{id}`. Test: the digest is present over HTTP; a worker on malformed settings
  exits non-zero by name.
- **LO17 (W1).** D-18: Esc during a turn stops it ("Zastaveno vámi. Nic nebylo přijato za vás.");
  "Zastavit plán" on a running plan's card. Tests: a cancelled turn applies nothing and its
  reservation settles; a withdrawn plan starts no further step. *Tightened 2026-10-21 (LO5a.4):* a
  withdrawn plan whose current step is a Deep Research run cancels it, keeps what it captured, and
  starts nothing after it.
- **LO18 (W3).** D-39, IN: streaming text (ADR 0026 left streaming "not decided"; this answer decides
  it), a file from the composer kept as the client's source or the brief's attachment by the existing
  paths, and unprompted comments after a pause, **each a paid turn charged to the wallet, shown as
  such**. Needs an ADR 0026 amendment in its PR. Test: an unprompted comment never fires when the
  wallet cannot cover a turn.

**Existing chunks, changed by the owner's answers.**

- **LO0 (D-01).** The money names: Rozpočet klienta (`clients.budget_usd`), Rozpočet studie
  (`budget_usd`; Settings' "Strop rozpočtu" is renamed), Peněženka (the wallet), Práh potvrzení
  (`spend_confirm_usd`), written once in the copy module.
- **LO1 (D-03, D-05).** A raise above the client's wallet ceiling is refused, naming who can raise
  the ceiling (OWNER or ADMIN on Profil → Pravidla, `client-knowledge-lifecycle#K11`); there is no
  approver queue. A Deep Research run is charged at its ceiling until migration M11 reconciles tool
  spend.
- **LO3 / LO10 (D-04).** On a Design Revision move a plan finishes the steps tied to its immutable
  revision and stops only the steps that would start from the working copy.
- **LO4 / LO9a (D-02).** The card shows each step's ceiling against the threshold; the plan's approval
  records a confirmation for each shown ceiling; a step whose ceiling grew since parks. AC-04 follows.
- **LO11 (D-32, D-33, D-34).** Each researcher has their own Lead, built and named by them (free
  text), never transferred: the handover, a handover-starting departure trigger and an admin's reading of another
  researcher's Lead files are **out**. LO11 keeps the Lead's file history (readable, restorable
  revisions) and F14's learning rules. No study is assigned to one researcher's Lead (Q5, below). ADR 0030 is narrowed in its
  own PR accordingly.
- **LO12a (D-10).** Every API error in Czech with a no-leak test and a native copy review; the words
  for a refused Deep Research run (terminal, by cause).

### After the baseline's questions (the owner's answers to the baseline's Q1-Q8, 2026-10-20 19:37-19:46 UTC (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, second table))

- **LO11 (Q5): no study assignment.** Every researcher's own Lead works in every study they open; an
  admin assigns nothing. The owner: "opening a study, just shows their own agent within that studies
  artifacts, and now their ai agent can interact with the artifacts of that study and control the
  functions and valves in them … he carries his own files, but also the context of each study
  session." The open study-assignment question is closed.
- **LO19 (W2, after LO8 and `working-copy-edit-ops#WCE4`).** The owner: "maybe we need to have an md
  file attached to each study session so the researchers ai can get the context of the study, this
  should be updated regularly within each study." Proposed shape, pending the one question sent to
  the owner (who may write its prose part):
  - **What it holds.** The study's shared state, never any researcher's private turns: the brief and
    research questions, each stage's state, the Design Revision head and what changed since the
    last one (from the operation log), runs and their states, approved results and report state, the
    decisions in the approval ledger (accepted and refused changes, approvals, spend confirmations),
    and open items. Each line names its source (revision, run, ledger row).
  - **Who writes it.** Code, as a deterministic projection of that state (no model call, no cost);
    rebuilt on every working-copy revision, run event and ledger decision, so it is always current.
  - **Its class.** The highest class of what it holds by `material_rules.py`: Class B for a design,
    Class A when it carries approved client knowledge; it is sent only to a route approved for that
    class.
  - **How it fits ADR 0026.** It becomes the content of `freeze_context`'s existing `study` layer
    (`domain/research_lead.py:782-829 @ 47e5536`) with a byte budget of its own inside the 96 KB;
    when over budget the oldest history lines go first, and the omission is named. It feeds the
    frozen context, never replaces it: each turn freezes the file's version it read, so a turn stays
    reproducible.
  - **Where it shows.** Readable in the study (the Lead pane's "Kontext studie"), with its version.
  - Tests: two researchers' Leads read the same file; no private turn text appears in it; a run event
    rebuilds it; a turn records the file version it read.
- **LO20 (W3, after `deep-research-web-search#56`).** Q6, with the owner's note: "i really want to
  preserve a good UX here, and not have limited results." The Lead calls Hledat na webu as a tool:
  code sends the query through `RetrievalGate` (posture, class, egress, metering, journal) as a
  single-track lookup (`deep-research-web-search#56`): several search results at once (a list of
  titles, snippets and links), the top pages fetched and captured in parallel, and the Lead's answer
  cites each claim inline with its link and quote, labelled "externí zdroj", never respondent
  evidence. No extra click: the results stream into the turn. OPEN clients only; for a CLASSIFIED
  client the Lead says it may not search and why. Each search and fetch is charged to the wallet and
  shown with its cost. A captured page can be added to Client Knowledge by the existing "Ověřeno,
  přidat zdroj". **Needs an ADR first** (a new ADR after 0038 for the Lead's lookup tool, and ADR
  0017's scope widened to it); the chunk's PR carries it Proposed.

### After the stage-handoff and context-file answers (the owner's answers on the PM status page, 2026-10-20 about 20:35 UTC, relayed by the coordinator (page ids Q10, Q11, Q12; `.planning/evidence/scope-freeze/answers-2026-10-20.md`, third table))

The owner, on Q12: "we need the highest degree of integration, this needs to be cohesive to produce a
high quality report." All five gaps of the coordinator's stage-handoff audit are closed here and in
the chunks named below.

- **LO9d (W2, after LO9a and `working-copy-edit-ops#WCE7`).** A stage worker today sees the design
  and approved knowledge titles only (`context_snapshot`, `domain/research_agents.py:565-583 @
  7878bad`), so each stage works in a silo and the previous stage's output is not its input. Each
  worker's `LeadWorkerSpec` row declares the inputs it reads, and its context carries them:
  - the upstream stages' accepted items, from WCE7's map of what each stage reads;
  - readiness, the question outlook and the research trace;
  - earlier proposals' reasons and dismissals for the same stage;
  - the newest sealed Deep Research bundle's findings, by reference and labelled external context
    (ADR 0021: never respondent evidence).
  The context stays bounded (the worker's own byte limit), with omissions named. Test: a
  questionnaire worker started after an accepted brief and a Design Research run reads both, and a
  dismissed proposal's reason, by id.
- **LO7.** The Lead's context gains a pending-proposals layer: every proposal still waiting on the
  study, with its stage, proposer and base revision (`application/research_lead.py:858-889 @
  7878bad` builds the layers today without it).
- **LO6's test** also covers a job started through `approve_request`, so a job the Lead's card started
  returns its typed result to the Lead like any other.
- **LO19, the prose part (page Q10: (b)).** Besides the code-built state, the study context file has
  "Poznámky ke studii": any researcher's Lead proposes a note and a person accepts it through the
  existing accept path, with the auto-accept text toggle applying. A note is study material, classed
  by `material_rules.py` like the design. The owner also wrote: "i do want to kinda integrate wordcraft
  and have the lead research be able to live edit the document, once the user is editing the document
  will depend if they revize the text as a comment or rewrite it directly, that will be up to each
  researcher." That live-editing part is **not planned yet**: the coordinator is asking which
  document and what "wordcraft" means.

### After the editing, departure and lookup answers (the owner's answers on the PM status page, 2026-10-20 20:50-21:04 UTC, relayed by the coordinator (page ids Q13 to Q18; `.planning/evidence/scope-freeze/answers-2026-10-20.md`, fourth table))

- **LO19 and the reports (page Q13: (a)).** How a Lead's edit reaches a document is each
  researcher's own setting: **tracked-change suggestions** the researcher accepts or rejects (the
  default), or **direct rewrites** that stay undoable. It applies to the study context file's notes
  (LO19) and to report documents (`report-delivery#RD6`), on top of their existing rules (every
  number a ledger ref in a report). The editor itself is open: the owner names Wordcraft
  (`github.com/storytold/wordcraft`, an open-source Rust/WASM Word reimplementation with an MCP
  server, alpha), and whether AIA adopts it is being asked; nothing here depends on that choice.
- **LO11 (page Q14: (a)).** A departed member's Lead is **sealed** when the member is deactivated
  (`two-roles-human-ai-gates#8`): no turn runs, nothing is read by anyone, its files and notes stay
  as they were. It is deleted at the end of MVPQ-07's retention (30 days), through
  `study-data-lifecycle`'s delete path, with the content-free usage and audit rows kept. Still no
  handover and no admin read (D-32 to D-34). Test: a deactivated member's Lead refuses a turn and an
  admin read, and is gone after the retention end.
- **LO20 (page Q18: (a)).** A Lead web lookup needs **no plan card or approval**: it runs inside the
  turn, bounded to **3 queries, 5 fetched pages and 2 lookups per turn**, with a hold on the wallet
  before it leaves (the hold refuses it when the wallet cannot cover it). OPEN clients only. Tests:
  a fourth query in one turn is refused by name; a lookup with too little wallet is refused before
  anything is sent.

### After the lookup-for-CLASSIFIED answer (the owner's answers on the PM status page, 2026-10-20 21:55-21:57 UTC, relayed by the coordinator (page ids Q22 to Q24; `.planning/evidence/scope-freeze/answers-2026-10-20.md`, sixth table))

- **LO20 (page Q24: (c)).** The lookup works for **CLASSIFIED** clients too, **behind a plan card**:
  the Lead prepares the lookup (its queries as they will be sent, the route, the bound and the wallet
  hold) and the person approves it, through the same card path as LO4's minimum plan card. An OPEN
  client's lookup still needs no card (page Q18's bounds: 3 queries, 5 pages, 2 lookups per turn).
  A CLASSIFIED lookup's queries are Class B by rule or `deep-research-web-search#57a`'s
  code-extracted fields, to Brave alone; search operators as `deep-research-web-search#58`. The
  owner asked how cards are made systematically; the card inventory goes to him as an explainer
  through the coordinator. Tests: a CLASSIFIED client's lookup sends nothing before its card is
  approved, and runs within the same bounds after; a stale card is refused.

## Findings (the coordinator's card review, 2026-10-20)

Found on the UI workbench at develop `237fd0a` (screenshots by the coordinator), anchored at
`242523e`. For the docs PR to number in `open-items.md`. Reproduction: `make ui-workbench` with
in-process scripted model answers and `AIA_AI_ANALYSIS_ENABLED=true`, then `make ui-fixtures`,
unless stated.

- **CR-1. The Lead's request card shows no cost and starts the job on one click.**
  Anchor: `apps/web/src/components/workbench/LeadPane.tsx:471-488`, `Workbench.tsx:258-279`,
  `apps/api/src/aia_api/routers/lead.py:458-462`, `application/research_lead.py:720-734 @ 242523e`.
  The only ceiling is the flat `AIA_AI_RESEARCH_RESERVATION_USD`, raised only as a 409 when it reaches
  the study's limit; the turn returns no cost. Reproduce: a Lead turn proposing an agent job, then
  "Spustit úlohu". Consequence: a person approves paid work without seeing its price. Smallest fix:
  the card path's price step (LO4, LO10): the turn returns `ceiling_usd`, the card shows "až X USD"
  and sends `confirm_cost_usd`. Test: a request card renders its ceiling, and approving it without
  `confirm_cost_usd` at or above the limit is refused.

### The card system's design reference (2026-10-20, relayed by the coordinator)

- The card path (LO4, LO10, LO16) and the fixes of CR-1, CR-2, CR-3 (`two-roles-human-ai-gates`) and
  CR-5 (`report-delivery`) take the published card-system design as their visual reference: the
  workbench design artifact, version 5, screen 14 (the design session's artifact
  `JrWZXosJtKVLckHhArngeV`). Behaviour stays this plan's and ADR 0026's / ADR 0019's.
- **Open, not adopted:** the design names ledger subject types beyond LO16's list: `qc_decision`,
  `study_note`, `report_edit`, `knowledge_revision` and `budget_lift`. They are proposals only.
  Whether LO16's migration M3 takes them (and which of them are new approval subjects rather than
  rows an existing writer already records, e.g. `knowledge_revision` in the knowledge repository's
  revisions, `budget_lift` in `resume_budget_wait`'s ledger row) is decided in LO16's PR, by S3 and
  the owner; until then LO16's list is unchanged.

## LO16 delivered (2026-10-21)

Migration M3, `5054d4d610c2` (down revision `57eaa96a5538`), admits the seven subjects; the
closed set is `domain/approval_ledger.py` `ApprovalSubject`, from which `tables.py` builds the
CHECK; every writer names its subject through the enum; `WorkflowRepository.ledger` reads a
study's rows under all three scope columns. Tests: `packages/aia_core/tests/test_approval_ledger.py`
(round trip of every subject, isolation across study, client and a forged organization column,
the upgrade and the refusing downgrade on PostgreSQL). Two `layer_check` rules: the ledger table
is touched only by its two repositories, and a subject is never a string of its own. The design's
proposed extra subjects (`qc_decision`, `study_note`, `report_edit`, `knowledge_revision`,
`budget_lift`) are **not** admitted: LO16's list is unchanged until the owner and S3 decide, and
admitting any of them later is a new migration on the same constraint, which M3 exists to avoid
(`budget_lift` is already `budget`; `knowledge_revision` is the knowledge repository's revisions).

## LO0 delivered (2026-10-21)

The contract ADR is ADR 0028, accepted and merged with #512. The vocabulary is typed in
`domain/money.py`: the five amounts (`MONEY`: column, Czech name, role, who sets it, what null
means), `PRECEDENCE` (budget, then wallet, then threshold), and the rules LO1, LO3/LO4, LO5 and
LO15 implement: `threshold_verdict` (today's rule; `ResearchRuns.start` now calls it),
`wallet_remaining` and `wallet_verdict` (by ceiling, an unknown ceiling refused),
`wallet_raise_verdict` (D-03: above the client ceiling refused, never above the budget) and
`start_verdict` for the three paths (D-02: a plan step starts on the ceiling its card showed and
parks when it grew; it never supplies a confirmation). OI-64 is written into the contract: a retry
is judged by its own full ceiling, because until RQC0 it may pay its respondents again. The four
names (D-01) are written once in the web copy module (`cs.money`); Settings' "Strop rozpočtu" is
"Rozpočet studie", and the run's cost panel calls the threshold "Práh potvrzení" throughout. Both
are held to `tests/fixtures/money/vocabulary.json` (`test_money.py`, `apps/web/src/i18n/money.test.ts`),
and `test_nothing_calls_the_confirmation_threshold_a_hard_stop` reads the code and the governing
documents. The wallet ceiling has no Czech label: the owner named none, so none is invented.

## Findings (LO0, review of #534)

- **F-LO0-1. The confirmation threshold's rule has three inline copies beside `money.threshold_verdict`.**
  Anchor: `application/deep_research.py:648-651`, `application/research_lead.py:724-729`,
  `application/validation.py:200-203 @ fd523a81`; `ResearchRuns.start` calls `threshold_verdict`
  since #534. Reproduction: `grep -n "confirm_cost_usd <" packages/aia_core/src/aia_core/application/*.py`
  lists the three. Consequence: none today (all four agree: `>=` asks, a confirmation covers at least
  the ceiling); a change to the rule made in one place would leave the Deep Research start, the Lead's
  approve path and a validation start on the old one. Smallest fix: each calls `threshold_verdict`,
  with its own refusal for an unknown ceiling kept; LO15 (E03) touches two of them and is the natural
  place. Test: each start's threshold tests, unchanged, plus one asserting it imports the domain rule.
  Deliberately not adopted in #534 (the reviewer's call).

### Doc follow-up (LO0)

- `open-items.md`: number F-LO0-1, owner LO15.


## LO15 delivered (2026-10-21, E03)

Before (`@ b5b369ae`): `ResearchAgentJobs.start` (`application/research.py:1343-1439`) and
`rebuild` (`:1546-1570`) read no `spend_confirm_usd`; the only check on a design job was the Lead's
approve path (`application/research_lead.py:720-734`). The worker's scope holds `EDIT_STUDY` and
`RUN_WORKFLOW` (`domain/scope.py:202-213`), so a step could have created a job past any threshold.

Now:

- `ResearchAgentJobs.spend_gate` is the job's one rule: `money.threshold_verdict` over the job's
  ceiling (`reservation_usd`, the design job's reservation `AIA_AI_RESEARCH_RESERVATION_USD`, a
  primary and one repair) and the study's threshold. Using a confirmation needs `APPROVE_BUDGET`,
  which `WORKER_PERMISSIONS` withholds, so a step can neither evade the threshold nor supply the yes.
  `start` applies it only when the job would be created (a found job asks nothing, as a run's start)
  and writes the `spend` ledger row with the new job (`record_spend_confirmation`); `rebuild` passes
  its `confirm_cost_usd` through to `start`.
- The API's `POST …/research/agent-jobs` and `POST …/agent-jobs/{id}/rebuild` take
  `confirm_cost_usd` and pass the deployment's reservation; refusals are the run start's 409
  `cost_confirmation_required` (ceiling and threshold in `details`) and `cost_ceiling_unknown`
  (`research_reservation_missing`). The request never names the ceiling.
- The Lead's approve path asks through the same `spend_gate` before submitting the design, then the
  job's own start applies it again and writes the job's `spend` row; the turn's `lead_job_request`
  row keeps its `spend` figures as before. The browser's direct start and rebuild
  (`useResearchAgents`) ask once with the server's ceiling (`withJobCostConfirmation`,
  `lib/research-agent-jobs.ts`) and confirm exactly that figure.
- **F-LO0-1 closed:** `deep_research.py` and `validation.py` call `threshold_verdict` in place of their
  inline comparisons, each keeping its own refusal for an unknown ceiling; `research_lead.py` calls
  `spend_gate`. Held by `test_every_start_path_applies_the_one_domain_rule`.

No switch: with no threshold set (the default) nothing changes, and a switch off would reopen the
path E03 closes. Tests: `packages/aia_core/tests/test_research_agent_spend.py` (below, at and above
the threshold, an unknown reservation, a rebuild, the worker's scope asked and refused its
confirmation, the four start paths on the one rule), `test_the_spend_limit_holds_a_prepared_job`
(the Lead path writes the job's spend row), `apps/api/tests/test_research_agent_spend_api.py`
(direct HTTP start and rebuild), `apps/web/src/lib/research-agent-jobs.test.ts`.

### Doc follow-up (LO15)

- `open-items.md`: F-LO0-1 closed by LO15 (E03).
- `CLAUDE.md` map, `routers/research.py` line on agent jobs: "`POST …/agent-jobs` and
  `…/rebuild` take `confirm_cost_usd`; a new job whose reservation reaches the study's threshold is
  409 `cost_confirmation_required` (LO15)".
- `docs/architecture/research-agents.md`: a job is held to `spend_confirm_usd` at start and
  rebuild, its ceiling the design job's reservation.

## LO9a delivered (2026-10-21, E03)

`domain/lead_workers.py`: `LeadWorkerSpec`, one frozen row per worker with the ten fields of F5
(`worker_id`, `task` with its closed `output_contract`, `context_layer`, `material_rules`,
`capability`, `reservation_key` with `schema_repairs`, `prompt_id` with `prompt_version`, `switch`,
`card_kind`, `result_kind`); no field has a default. `WorkerRegistry` refuses at registration a row
with a field missing (named in `WorkerRefused.fields`), of the wrong shape (an unknown material
rule or capability, a switch not `AIA_…_ENABLED`, a reservation key not `AIA_…_RESERVATION_USD`, an
open contract, an advice card on a proposal result, an extra field), or reusing an id or a prompt.
The eight design workers are rows (`domain/research_agents.py` `WORKERS`, `worker_for`) and
`agent_request` takes its capability, prompt id and repair count from the row, so the row is the
definition the job runs, not a description beside it. The fixture is
`packages/aia_core/tests/fixtures/lead_workers/workers.json`; `test_lead_workers.py` holds the rows
to it, to `CONTRACTS`, `prompt_version_for`, `DESIGN_ACTIONS` and the executor's keys.

**Choices recorded.** (1) The type is its own module, not `research_agents.py` as F5 first wrote:
LO9c's results workers share the row and are not `research_agent` actions (keyed on a run, not a
Design Revision), so the type must not live in the design harness; the design harness holds its
rows. (2) A row names the reservation's deployment key, never an amount: the amount is the
deployment's (ADR 0028: unknown is not zero), and LO15 reads it there. (3) `ContextLayer` has one
member, the design snapshot; LO8's results context adds its own when it exists, so nothing claims a
layer no builder makes. (4) `data_class` is derived from the rules (their worst case, Class A here
because a snapshot may carry approved knowledge); the request's own class stays `agent_request`'s.
(5) The registry is not yet read by the API or Settings: `research-lead-workbench` 11 (the command
registry) and Settings' `ai_runtime` document read it in E26; nothing here changes a runtime path but
`agent_request`'s three values, which are byte-identical to before.

### Doc follow-up (LO9a)

- `CLAUDE.md` map, `packages/aia_core/src/aia_core/domain/`: "`lead_workers.py` The worker contract
  (LO9a): `LeadWorkerSpec`, one row per worker the Lead may call, every field required and checked
  at registration (`WorkerRegistry`); the eight design workers are `research_agents.WORKERS`, held to
  `tests/fixtures/lead_workers/workers.json`".

### Review of #541 (2026-10-21), applied

The prompt-test panel's start asks at the threshold too (`SystemPromptsPanel` TestRun, through
`withJobCostConfirmation`); a "no" is `JobCostDeclined`, in Czech; a sub-cent ceiling prints its
digits, never "0 USD" (`jobCostUsd`); an approval whose job already existed records `spend: null` on
its `lead_job_request` row; `RequestApproval.confirm_cost_usd` takes the run's bound (0 to
1,000,000) and no non-finite number; `test_the_request_s_class_comes_from_exactly_the_row_s_rules`
holds `agent_request`'s rules to the worker row; an invocation-target refusal masks the account id.

**Finding F-E03-1.** A non-finite number in any request body (`Infinity`, `NaN`, which Python's JSON
parser accepts) was refused by validation, and then the 422 itself failed to serialise its echo of
the input: a 500. Anchor: `apps/api/src/aia_api/observability.py:206-213 @ 8e3f55dd`. Reproduction:
`test_a_confirmation_outside_its_bound_or_not_finite_is_refused[Infinity]` against that line.
Consequence: a malformed client got a 500 and an error report instead of a 422. Fix (here): the echo
keeps non-finite constants as text (`parse_constant=str`). Doc follow-up: number it in
`open-items.md`, closed by #541.

## LO1 delivered (2026-10-21, E07, stacked on #541)

Migration M4, `60ccc9ff42cf` (down revision `5054d4d610c2`, one head): `study_wallets` (one open
wallet per study, `uq_study_wallets_open` partial on `closed_at IS NULL`), `study_wallet_raises`
and `study_wallet_charges` (insert-once; a charge unique per `run_id`, its kind one of
`domain/wallet.py` `ChargeKind`: research run, agent job, Deep Research, Interpretation Research),
and `clients.wallet_ceiling_usd` (nullable, non-negative). The downgrade drops all four and refuses
while a raise or a charge is stored. `infrastructure/study_wallet_repository.py`
(`StudyWalletRepository`) is their only reader and writer (`make layer_check`, four rules: core,
API, worker, executors). `application/wallet.py` (`StudyWallets`) is the switch: with
`AIA_STUDY_WALLET_ENABLED` off (the default, off in test, absent from the develop Compose file)
every call raises `WalletDisabled` before the repository is built. HTTP:
`GET /studies/{id}/wallet` (off: `available: false`, no row read) and `PUT …/wallet {cap_usd}`
(`APPROVE_BUDGET`; off: 409 `wallet_disabled`; 409 `above_client_ceiling` with
`who_can_raise: ["OWNER","ADMIN"]` (D-03) or `above_study_budget`). A cap change writes one
`wallet` ledger row (`WorkflowRepository.record_wallet_raise`, `APPROVE_BUDGET`, which
`WORKER_PERMISSIONS` withholds) and one raise naming it.

**Choices recorded.**

1. **The lock is the study row, `SELECT … FOR UPDATE`, under READ COMMITTED**, taken first by every
   write that compares an amount (`set_cap`, `quote`, `charge`, `close`). Rejected: a conditional
   `UPDATE … SET charged = charged + x WHERE charged + x <= cap` on the wallet row (it needs a
   denormalised running total beside the insert-once charges, two sources of one number, and the
   cap's bounds live on two other rows), and `SERIALIZABLE` (aborts on conflict and needs a retry
   loop at every caller; the blocking lock waits and re-reads instead). The study row is the lock
   `workflow_repository._reserve` already takes for the budget. **Lock order: the run, then the
   study that pays**, the existing invariant (`workflow_repository.py:773-779`,
   `application/research.py:290-295`, `application/client_work.py:127-131 @ 30e078cc`). Nothing
   here locks a run or a client row; a caller holding a run's lock may call `quote` or `charge`,
   and must never lock an existing run after them in the same transaction (a run it just created
   is invisible to others and takes no contested lock). The wallet row is not the lock because the
   first raise creates it, and a lock on a row not yet there protects nothing. (The first version
   of this PR said "the study row first, then the run"; that was the reverse of the invariant,
   review P2-c.) Money is compared as decimals (`money._exact`, `repr`'s shortest round trip;
   the charges summed in Python), so USD 0.30 less 0.10 fits a 0.20 start exactly (review P3-a);
   the columns stay `Float`, as every budget column is.
2. **A charge is a hold at its run's ceiling, never released or re-priced** (ADR 0028 decision 2):
   remaining is the effective cap minus the charges' ceilings (`money.wallet_remaining`); settled
   spend stays in the usage ledger, read for display. No `settled_usd` column: a second copy of
   what the usage ledger holds would be a second source of one number. "Settled once" here means
   the hold is written once (unique `run_id`) and a start that finds its run charged charges
   nothing again.
3. **The effective cap** is the smallest of the wallet's cap, the client's wallet ceiling and the
   study's budget (`domain/wallet.py` `effective_cap`), computed at every read, so a ceiling
   lowered or a budget cut after a raise bounds the wallet at once.
4. **A charge needs this run's start decision** (review P2-b): a `chat_start` or `plan_step`
   ledger row of the same study (`CHARGE_AUTHORITIES`) whose `run_id` is the charged run, whose
   decision is `start` (`CHARGE_DECISION`), used by no other charge (`wallet_charge_decision_once`);
   a `plan_step` row's subject is its step, which the charge names with its plan (`plan_step_id`,
   `plan_id`, both or neither by CHECK); a `chat_start` charge names neither. Each refusal has its
   reason (`not_a_start_decision`, `decision_names_another_run`, `decision_not_a_start`,
   `plan_step_mismatch`, `chat_start_names_a_plan`, `decision_already_used`). LO3 adds the check
   that the step belongs to an approved plan, once `lead_plans` exists. The charge needs
   `RUN_WORKFLOW`, not an approval: the plan authority (LO3) holds none
   and charges under the decision a person already made. A person's own start on the Run stage
   does not consult the wallet (`money.start_verdict`, `StartPath.PERSON`) and writes no charge,
   so no existing start path calls the repository: with the switch on or off, today's spend paths
   are byte-for-byte unchanged. LO5 (the typed chat start) and LO3/LO4 (the plan step) are its
   callers: `quote` under the study lock, create the run, `charge` it, one transaction.
5. **A refusal is typed, never decided here**: `WalletChargeRefused` (`no_wallet`,
   `ceiling_unknown`, `outside_wallet`); the plan step parks on it and the typed start refuses
   (`money.start_verdict`). "A charge above the wallet parks, never fails" is LO3's test, on its
   step; LO1 proves the refusal writes nothing.
6. **A closed study refuses and closes its wallet** (review P2-a): `set_cap`, `quote` and `charge`
   read the status from the locked study row and refuse `study_closed`; the API's status change
   goes through `application/wallet.py` `set_study_status`, which closes the wallet in the same
   transaction when the study becomes DELIVERED, ARCHIVED or CANCELLED and the switch is on (off:
   the status alone, no wallet row read). A first cap of USD 0 writes its raise and ledger row like
   any other (review P3-b); an unknown study is 404 (P3-e).
7. **The switch is the wallet's own** (`AIA_STUDY_WALLET_ENABLED`), apart from ADR 0028 decision
   6's `AIA_LEAD_PLANS_ENABLED`, so the wallet ships off before any caller exists.

Tests: `packages/aia_core/tests/test_study_wallet.py` (the cap's two refusals, the ledger row once,
a no-op cap, bounds that move, the worker refused, a charge once by ceiling, unknown refused, no
wallet, the authority's subject and study, another study's run, close and reopen, the table's
uniques and kind CHECK, the switch off reading nothing; on PostgreSQL: eight concurrent USD 3
charges on a USD 10 wallet, exactly three charged; a charge waiting on a held cap change and
refused against the new cap; the migration's downgrade and upgrade, and its refusal with a raise
stored). Both concurrency tests fail when `charge` reads the study row without the lock (measured:
mutation run, 2 failed). `apps/api/tests/test_wallet_api.py` (off by default, on: set and read,
both refusals with their details, 422, 404).

Further tests (the review of #544): an exact decimal fit, this run's decision (six refusals), one
`chat_start` row refused for a second run, the decision's unique key, a plan step naming its step
and plan, a closed study refusing all three writes, the status change closing the wallet (three
statuses) and keeping it open (IN_REVIEW), off reading nothing, a first cap of 0 recorded;
`test_migration_heads.py`: exactly one Alembic head (review P1-a: #542 adds `a3c5e7f9b1d4` on the
same parent; whichever merges second re-points its `down_revision`).

### Findings (review of #544, recorded, not fixed here)

- **F-LO1-1 (P3-c). A retry drains the wallet.** A retry is a new run (`run_id`), so it takes its
  own charge at its full ceiling while the original's hold is never released. Anchor:
  `infrastructure/study_wallet_repository.py` `charge` (unique `run_id`, no release) @ this PR's
  head. Reproduction: charge run A at USD 5, retry it as run B and charge B: USD 10 held for one
  run's work. Consequence: a few retries exhaust the wallet. Smallest fix: LO3's step-retry rule
  says whether a retry's charge replaces the original's (released when the original ended without
  paying), decided with the release question below. Test: a retried plan step's wallet holds one
  ceiling, not two.
  *Linked (2026-10-22):* the stage's analysis retry (`POST …/analysis/retry`) and the typed
  "Zopakuj analýzu" (below) charge the wallet nothing today, by the product manager's decision
  (b). When F-LO1-1 is decided, both change together, in one PR.
- **F-LO1-2 (P3-d). The wallet is not bounded by what the budget has left.** `effective_cap` takes
  `budget_usd`, not its remainder (`spent_usd` and open reservations). Anchor: `domain/wallet.py`
  `effective_cap` @ this PR's head. Reproduction: budget USD 10, wallet USD 10, a person-started run
  spends USD 9; the wallet still shows USD 10 remaining. Consequence: display only, since the
  budget's reservation still stops the spend; a plan step would start and then park
  `AWAITING_BUDGET` rather than be stopped at start. Smallest fix: bound remaining by the budget's
  remainder when LO4 shows the meters. Test: the wallet's remaining never exceeds the budget's.
- **F-LO1-3 (P3-f). The downgrade drops `clients.wallet_ceiling_usd`.** It refuses while a raise
  or a charge is stored, but drops a ceiling an OWNER or ADMIN set. Anchor:
  `migrations/versions/20261021_60ccc9ff42cf_…py` `downgrade` @ this PR's head. Nothing sets the
  column until K11. Smallest fix: refuse the downgrade too while any ceiling is non-null, when K11
  ships its setter. Test: the downgrade refuses with a ceiling set.

**Open for the owner (not a finding).** With charges never released, a wallet is drawn down by
upper bounds: a run whose ceiling was USD 5 and that cost USD 0.40 keeps USD 5 of the wallet held
until the researcher raises the cap. ADR 0028 rejects charging by settled spend for concurrency; a
release of the unspent part *after* a run ends (the hold settled to its usage) keeps concurrency
safe and is a different rule. Whether to adopt it is the owner's, in an ADR 0028 amendment; LO1
builds the ADR as written.

### Doc follow-up (LO1)

- `CLAUDE.md` map, `infrastructure/`: "`study_wallet_repository.py` The ONLY reader/writer of
  `study_wallets`, `study_wallet_raises`, `study_wallet_charges` (M4, LO1): every amount compared
  under the study row's `FOR UPDATE`; a charge is a run's ceiling, once, authorised by a
  `chat_start` or `plan_step` ledger row; `set_cap` writes the `wallet` ledger row"; `application/`:
  "`wallet.py` StudyWallets behind `AIA_STUDY_WALLET_ENABLED` (off by default)"; `domain/`:
  "`wallet.py` the wallet's values: `ChargeKind`, `CHARGE_AUTHORITIES`, `effective_cap`, the two
  refusals"; `routers/`: "wallet (GET/PUT /studies/{id}/wallet, Peněženka; off: available false,
  409 wallet_disabled; 409 above_client_ceiling naming OWNER/ADMIN, above_study_budget)".
- `ARCHITECTURE.md` enforcement list: the four `layer_check` wallet rules.
- `docs/architecture/adr/0028-…` What enforces it: "the wallet is behind
  `AIA_STUDY_WALLET_ENABLED`, apart from `AIA_LEAD_PLANS_ENABLED`"; and the release question above.
- `open-items.md`: number F-LO1-1 (owner LO3), F-LO1-2 (owner LO4), F-LO1-3 (owner K11).
- `CLAUDE.md` map, `application/`: "`wallet.py` … `set_study_status`: a study's status change, which
  closes its wallet when it closes"; the scope router's status route goes through it.
- `deploy/develop/README.md` (the switches): `AIA_STUDY_WALLET_ENABLED`, off, not in Compose.


## Deep Research under the Lead (2026-10-21)

The owner, 2026-10-21, on #550's note that the Deep Research start buttons stay because the Lead
cannot start Deep Research end to end: **"we need to plan this, the lead should be able to control
the whole process".** This section is that plan's Lead half. Its UI half is
`research-lead-workbench` § *Deep Research cards and starts*, and its pricing half is
`deep-research-web-search` 55 (DRL-0). The ids DRL-0 to DRL-11 name the pieces across the three
files. Anchors are `@ 095a3e68` (`origin/develop` when written) unless stated; `@ cd7af699` is #550.

### Decisions (the product owner, Nigel, 2026-10-21; not re-asked)

- **Earlier the same day:** "the lead should be able to control the whole process".
- **Q44 (12:28 UTC). The Lead may offer all seven Interpretation target kinds** of ADR 0021
  (`domain/deep_research/integration.py:172-260`), **from the code-built candidate list, with the
  `research_questions` analysis module as the default** it proposes. The seven are `TargetKind`
  (`integration.py:172-179`). Six are results (`RESULT_QUESTION`, `RESULT_BATTERY_OBJECT`,
  `ANALYSIS_MODULE`, `SOCIOMAP`, `SOCIOMAP_OBJECT`, `SOCIOMAP_RELATIONSHIP`) and are offered as
  Interpretation candidates. The seventh, `DESIGN_REVISION`, is Design Research's own target: the
  Lead reaches it through a design request, and the interpretation freeze refuses it (422), as it
  does today. His note: "the research lead
  needs to be able to control the end to end process and ensure it has all the context and
  connections to be informed". So each candidate carries its connections in words built by code:
  the research run and its date, the module, question or map entity, and the research questions it
  traces to (`domain/research_trace.py`). The model never writes an id of its own.
- **Q45 (12:29 UTC). A Design Research run may focus on named research questions;** the whole design
  stays the default. His note: "cool idea, needs to be well planned and properly connected". So the
  focus is ids of the revision's research questions taken from the turn's context, filtered by code
  into the engine's subjects before the request is frozen. The engine is unchanged: it receives fewer
  subjects, and per-subject fingerprints keep reuse. The card names each focused question and the
  questionnaire items that measure it (`research_trace`), so the person sees what is researched and
  what is not.
- **Q46 (12:31 UTC). The Lead offers QUICK and STANDARD, and STANDARD is the default.** His note,
  which overrides the option's own default of QUICK: "standard by default". The request contract
  refuses DEEP and EXHAUSTIVE. The card shows each preset's own ceiling (DRL-0's quote), because even
  these are large: `deep-research-reports.md` records worst cases of USD 31.03 for QUICK and
  USD 170.59 for STANDARD over a fresh executive target.
- **Q47 (12:31 UTC). An approved plan may chain fieldwork, then Interpretation Research on its
  results.** Code resolves the target when that step starts, and the plan card shows it as
  "výsledek kroku N · <modul>", with its ceiling confirmed at plan approval (D-02). **The step parks
  if its module ended BLOCKED** (or is stored BLOCKED, as `needsRepair` reads it). It never
  substitutes another target.
- **Q48 (12:32 UTC). DRL-5 (removing the Deep Research buttons) waits for DRL-8** (typed starts that
  work without the model, LO5a.3). Q43's guarantee therefore holds before the buttons go: with the
  Lead off, Deep Research stays startable by a typed command.

Decided as engineering in the same plan, not asked:
- No new kill switch for the Lead's Deep Research card. It holds the same server gates as the stage
  start it replaces, and a switch turned off would bring back D-12's gap once the buttons are gone.
  Rollback is `AIA_AI_RESEARCH_LEAD_ENABLED`, which leaves typed starts working (Q43).
- The Lead never cancels, accepts a proposal, approves a report or a setting, or adds a source by
  itself (ADR 0026, ADR 0019, ADR 0022, CLAUDE.md).
- The run card's retry, resume and budget lift use the stage routes, as #550's run card does.

### Settled before and carried here

- D-12: Deep Research starts only through the Lead (LO5a).
- D15 and AC-02: Deep Research is not an exception; source proposals are (LO13).
- D7 as #550 amends it, amended again by LO5a.2 for the two Deep Research kinds.
- LO4: a card is a one-item plan once LO3 and LO4 land.
- D-05: a Deep Research run is charged at its ceiling until M11 (`ChargeKind.DEEP_RESEARCH` and
  `INTERPRETATION_RESEARCH`, `domain/wallet.py:58-66`).
- Q42 and Q43: `research-lead-workbench` 27b, on #551.
- ADR 0021: Design Research only proposes. The engine is frozen, so nothing below changes
  `domain/deep_research/*` or `aia_executors/deep_research/*` except as a caller.
- ADR 0022: a priced live route is refused until every live setting is approved
  (`application/deep_research.py:625-632`), and the Lead never approves one.

### The chunks

**Standing rule CARD-1: one card, one action** (Nigel, 2026-10-22 ~22:50 UTC, relayed by the
coordinator). "One card in the Lead researcher chat is for one action: one run (běh) of AI
respondents, one run of Deep Research", and so on for every kind.
- A card never bundles two actions, two runs or two jobs.
- A turn that proposes several gets several cards, each with its own approve and decline, cost,
  state and result.

Checked against today's cards (develop `b6cd4d9e`):
- **Conforms:**
  - the prepared agent job (one job, `approve_request`, `application/research_lead.py:934`);
  - the research-run card (one run, started on Spuštění);
  - a typed start (LO5, one start);
  - the analysis-retry card (one run over the failed modules);
  - LO5a.1/.2's `design_research` and `interpretation_research` (one run each, as planned);
  - the budget lift (one parked step);
  - LC5a's queue: one Lead turn answers several messages, and that is one paid action, not a card.
- **Breaks it, or cannot yet keep it:**
  1. **A turn can propose at most one request.** `LeadOutput.request: JobRequest | None`
     (`domain/research_lead.py:348`), and the prompt says "nejvýše jednu" (`:823`). A turn that
     would propose two can show only one. The fix is `requests: list[…]` with one card per item,
     each with its own decision in the ledger, and a prompt version bump.
  2. **"Pamatovat si" decides a whole `self_update` at once**: notes to remember and to forget,
     SOUL, USER and the name, in one accept (`decide_self_update`, `:876`). Under CARD-1 each
     change is its own card.
  3. **The edits block's "Přijmout vše"** (`apps/web/src/components/workbench/Workbench.tsx:833`)
     accepts up to 12 edits with one click. Each edit already has its own decision in the ledger
     (`decide_edits`, `:753`), so the batch button is a convenience over per-item cards. It
     conforms if edits count as one action each and the batch is only a shortcut; otherwise
     drop it. Nigel's call.
  4. **LO4's plan card**, as planned, approves several steps at once ("approved once"). Under
     CARD-1, LO4 needs one card per step, or Nigel's explicit exception for plans.

Nigel's answers (2026-10-22 ~22:55 UTC):
- (1) Breaks the rule: chunked as **LO21** (LO20 is the Lead's web lookup, ADR 0040). Nigel then
  asked for it to be shaped for scale, still systematic and approval-gated. See **LO21,
  registry-driven actions** below.
- (2) "Pamatovat si" stays one decision.
- (3) "Přijmout vše" stays.
- (4) **A plan is one action**, so one card approves a whole plan. LO4's card must show every
  step visually and directly inside the card:
  - each step is its own row with its kind's icon, what it does in plain words, its cost ceiling
    and its order or dependency;
  - the card shows the plan's total ceiling and has one approve and decline for the plan;
  - after approval, each row carries its own live state (queued, running, done, failed, waiting
    on you);
  - a step that needs a person surfaces in its row without breaking the card.

  A plan's rows are its registered actions (LO21e). A `research_run` action is one row; under
  it the card shows that run's own steps, read from its workflow template
  (`domain/workflow_templates.py`) and, once started, from the run's steps. Those steps are
  never actions of their own: the Lead cannot propose an aggregation or a report outside a run.

  Example plans:
  - "Návrh dotazníku": Design Research → questionnaire job; the card then shows the readiness
    check, read once both finish, which is a read and not a step;
  - "Pilotní běh": one `research_run` row at n = 50, showing its steps (fieldwork, aggregation,
    report draft);
  - "Plný běh": one `research_run` row at n, showing its steps (fieldwork, aggregation,
    Sociomapa, the 8 analysis modules, report);
  - "Interpretace výsledků": Interpretation Research on the strongest relations → report with
    literature;
  - "Oprava modulů": retry the failed analysis modules.

**LO21. Registry-driven actions** (Nigel, 2026-10-22 ~23:00 UTC, relayed by the coordinator).

What it is:
- `LeadOutput.request` today is one of four fixed types (`domain/research_lead.py:282-348 @
  b6cd4d9e`). It becomes `actions: [{worker_id, args}]`, several per turn.
- The registry is the single source of truth for what the Lead may propose. Adding a card kind
  is one registry entry, its args schema and its card slot, with no change to the Lead's core
  schema or prompt.
- ADR 0026's shape stays: structured output without tools, a frozen context, one schema repair,
  a predictable cost per turn.
- Each change of the generated union or prompt section bumps `LEAD_HARNESS_VERSION` and the
  Lead prompt version (ADR 0020 pin).
- A bump alone does not keep old turns readable: `ResearchLead._completed` parses every stored
  output with today's `LeadOutput` (`application/research_lead.py:564-572 @ 689a2d24`). So the
  registry is append-only by version (Codex review on #818):
  - an action's `args` schema never changes in place; a change is a new version of the action
    (`ActionSpec.version`), and every version stays registered for decoding;
  - removing an action stops *offering* it (LO21b), never decoding it;
  - a stored action is decoded by its turn's recorded harness version and its own
    `worker_id`@`version`, never by today's union;
  - a decoded action whose version is no longer offered can still be declined; approving it
    re-checks it against today's guards, and one that no longer passes says why, by name.

The registry's shape:
- `domain/lead_workers.py`'s `LeadWorkerSpec` (`:88-105`) describes a *model* worker today:
  `output_contract`, `capability`, `prompt_id` and `schema_repairs` are required.
- A research run or a Deep Research run is an action that calls no model of its own. So
  LO21a adds an `ActionSpec` beside it:
  - `worker_id`, `card_kind`, `result_kind` and `switch`;
  - the cost source (`reservation_key` or a ceiling function);
  - `material_rules`;
  - `args` (a Pydantic model), `description_cs` and `example`;
  - an optional reference to the `LeadWorkerSpec` it runs.

  A model worker's action names its spec, so nothing is said twice.

The chunks, each with its test:
- **LO21a.** The `ActionSpec` registry and the generated `LeadOutput.actions` union.
  - Tests: an unknown `worker_id` is refused; each action's args are validated by its schema;
    the union equals the registry; a duplicate `worker_id`@`version` fails at import; a turn
    stored under an earlier version decodes, and can be declined, after the action's `args`
    gain a new version.
- **LO21b.** The prompt's action section is generated from the registry and filtered per turn,
  from the frozen context: a switch off, or not permitted (scope, study status). The model sees
  only what it can propose. `lead_contract` refuses an action the turn was not offered.
  - Cost depends on the arguments (a focused Deep Research quote is cheaper than a whole
    design's, a QUICK preset than a STANDARD one, a run by its n), so the budget cannot be
    judged on the registry entry alone (Codex review on #818):
    - the amounts are `domain/money.py`'s, in its one precedence (`money.py:31-34 @ c42a73e7`):
      Rozpočet studie stops spending, Peněženka decides what may start without a card, Práh
      potvrzení decides what asks again and is never a cap. A Lead action always has a card, so
      what it is compared with is Rozpočet studie's remainder (`above_study_budget`, `:269`);
    - an action is left out only when its *cheapest* arguments' ceiling (`domain/run_cost.py`)
      is known and exceeds that remainder;
    - otherwise it is offered with that remainder, and each spec's ceiling function prices the
      arguments the model chose when the turn is grounded;
    - an action whose ceiling exceeds the remainder keeps its card, but the card shows the
      refusal, never a way to start it: its cost beside the remainder, and the way to raise
      Rozpočet studie, named, with who may raise it. Práh potvrzení's confirmation
      (`threshold_verdict`, `:195`, ADR 0019 gate 2) applies only to a card within the budget;
    - an unknown ceiling (`total_usd: None`, `CeilingUnknown`: a panel run, an unpriced route)
      is never compared as 0. Its action is offered and its card says the cost is unknown;
      approving it is refused wherever a rule needs the ceiling
      (`ThresholdVerdict.CEILING_UNKNOWN`, `money.py:183`);
    - card copy uses the names in `money.py` (`MONEY`), never "what is left".
  - Tests: the section lists exactly the offered actions; an action that was not offered is
    refused; the section's bytes stay bounded; with Rozpočet studie's remainder covering QUICK
    or focused work but not STANDARD or whole-design work, the action is offered, a QUICK card
    is approvable (asking at Práh potvrzení when its ceiling reaches it), and a STANDARD card
    shows the refusal and the way to raise the budget, with no approve; an action whose
    cheapest ceiling is unknown is offered, its card says so, and its approval is refused with
    `ceiling_unknown`.
- **LO21c.** One generic card renderer (web) keyed on `card_kind`, with small per-kind slots.
  Each action is its own approve and decline and its own ledger decision (CARD-1); the route
  becomes `…/turns/{turn_id}/actions/{index}`.
  - Tests: two actions in one turn give two cards and two ledger rows; deciding one leaves the
    other waiting; the spend limit, `LiveNotApproved` and classification parking apply per
    action.
- **LO21d.** The four request types are migrated: `agent_job`, `research_run`,
  `design_research` and `interpretation_research`, the last two LO5a.2's.
  - Tests: a stored single `request` still reads and decides; each type's card behaves as
    before.
- **LO21e.** The `plan` kind: one action whose steps reference registered actions. It is LO4's
  card, with every step shown, one approval, live state per step, and a person's gate in its row.
  - Tests: a plan naming an unregistered or not-offered action is refused, and so is one naming
    a workflow step (aggregation, report) as a row; a `research_run` row shows its template's
    steps before it starts and its run's steps after; the per-step state follows each step's
    run.

Order: after LO5a.1 and LO5a.2. LO21d migrates their cards; LO21e needs LO3 and LO4.

Later option, not now: native "propose" tools that only create pending cards. Revisit when the
Lead gains read-only tools (LO20's web lookup), because tools change the cost and repair model
ADR 0026 fixes.

**First after the feature freeze (Nigel, 2026-10-22, relayed by the coordinator, /pmstatus
Q80).**
- Deep Research is started by the Lead: a card in the chat that the person approves. It is never
  started automatically, and the guards stay those of Deep Research's own start:
  - `confirm_cost_usd` at the spend threshold;
  - `LiveNotApproved`;
  - a ledger row;
  - classification parking (OI-129).
- LO5a.1 and LO5a.2 come first after the freeze, after `lead-conversation` LC5a.
- LO5a.2 covers **both** `design_research` and `interpretation_research`.
- In the same release:
  - #808 (Dotazník) hides Dotazník's own workbench start (QF-13). It is held as a draft and
    merges with LO5a.
  - Výsledky hides its own workbench Interpretation Research start and retry.

  Until LO5a.2 lands, those stage buttons are the workbench's only way to start either.

**LO5a.1 (DRL-2). The Lead's Deep Research requests and context.**
- `domain/research_lead.py`. Today both requests carry only `why` (`domain/research_lead.py:250-258`).
  - `DesignResearchRequest` gains `preset: Literal["QUICK","STANDARD"] = "STANDARD"` (Q46) and
    `focus: list[<research-question id>]`, empty for the whole design (Q45).
  - `InterpretationResearchRequest` gains `target: <candidate id>` (by default the run's
    `research_questions` module candidate, Q44) and `preset`.
  - A new `DeepResearchRetryRequest` (`kind: "deep_research_retry"`, a `run_id` from the layer).
  - `lead_contract` grounds every id against the layers and refuses one that is not there, as it
    refuses an unknown focus target today.
  - The prompt (`_TASK`, `:545-580`) describes the two purposes, the presets and what a target is,
    and says that a rešerše is external context, never respondent evidence. The prompt version is
    bumped (ADR 0020 pin).
- New `domain/lead_research_targets.py`, `interpretation_candidates` (pure). It lists the study's
  targetable entities from its finished research runs, newest first and bounded. Each candidate has
  a short id `t1…tn` that is stable within the turn, its `TargetKind`, its words and connections
  (Q44), and the `ResearchTargetRef` behind it. A module stored BLOCKED is left out (the `needsRepair`
  rule).
- `application/research_lead.py` `_freeze` gains two layers, each in its own byte budget inside the
  96 KB, with omissions named and classed by `material_rules`. This closes F-DRL-4.
  - `deep_research`: the study's newest Deep Research runs (id, purpose, target in words, preset,
    phase and park code, counts, actual cost, ceiling).
  - `targets`: the candidates.
- The scripted Lead (`aia_executors/workbench.py`): "rešerš" prepares `design_research`; "výklad" or
  "výsledk" prepares `interpretation_research` over the default candidate.
- Tests (`test_research_lead.py`):
  - an unknown target, focus or run id is refused;
  - DEEP is refused, and STANDARD is the default;
  - the layers fit inside 96 KB;
  - a Deep Research run appears in the context;
  - the layers' class follows `material_rules`;
  - a BLOCKED module is omitted;
  - a candidate's connections name its research questions.

  Fixture: the candidate list for the workbench's fixture run.
- **The scoped freeze (Q45; Codex on #553).** Today `DeepResearchRuns.freeze_design` and `start`
  take no focus and rebuild every subject from the whole revision (`extract_subjects`,
  `application/deep_research.py:293, 319 @ 095a3e68`). A focused card would therefore quote and run
  the whole design. The contract:
  - `freeze_design(…, focus=<research-question ids>)` validates each id against the revision's
    research questions (an unknown id is refused by name, `focus_unknown`, 422) and carries only the
    selected research-question subjects into the frozen `DeepResearchRequest`. An empty focus is the
    whole design.
  - That one frozen spec is used for both the quote and the enqueue: LO5a.2 freezes once and passes
    the same spec to `DeepResearchRuns.quote` (DRL-0's `_admit`) for the card's price and to the
    start for the run. The start gains an entry that enqueues a given frozen spec (or `start` takes
    `focus` and freezes identically), so the run never re-freezes the whole design.
  - The focused subjects are in the engine request, so a focused run has its own request and spec
    fingerprint and never reuses the whole design's run by idempotency; its per-subject track
    fingerprints still reuse what was researched before.
  - **Dependency on DRL-0 (#555):** `_admit` and `quote` take the frozen spec, so the focus reaches
    them through it. The quote route's body gains `focus` here, and `_admit` gains a focus parameter
    only if a caller cannot hand it the focused spec. #555 is not changed for this.
- Tests (focus): a focused quote equals the focused start's ceiling, and both are smaller than the
  whole design's; an unknown focus id is refused before anything is priced; the focused run's
  request holds only the selected subjects.
- Kill switch: the Lead's own (`AIA_AI_RESEARCH_LEAD_ENABLED`). The fields only prepare.

**LO5a.2 (DRL-3). A Lead card starts Deep Research on the server; this amends D7 for the two kinds.**
Today `approve_request` raises `NotAPaidRequest` for any request that is not an `AgentJobRequest`
(`application/research_lead.py:711-712`), and the router answers 422 `not_a_paid_request`
(`routers/lead.py:335-336`; `test_a_request_that_only_opens_a_stage_is_not_a_paid_request`). The
web card only navigates (`Workbench.tsx:258-262`).
- Design: the design must be the revision the card was quoted on (LO10's rule: the turn's working
  revision, else `LeadTurnStale`, else submit it). The design is frozen once with the card's
  focus (LO5a.1's scoped freeze), and that spec is the one priced and enqueued.
- Interpretation: the target is resolved from the turn's frozen candidates, then
  `start_interpretation` is called. Its freeze verifies every pin (`ResearchTargetNotFound` and
  `ResearchTargetInvalid`, answered 404 and 422).
- `deep_research_retry` calls `retry`.
- Each is priced by DRL-0 and confirmed with `confirm_cost_usd` equal to the ceiling the card showed
  (D-02). A ceiling that grew asks again with the server's figure (#550's pattern,
  `Workbench.tsx:476-493 @ cd7af699`).
- The `lead_job_request` ledger row carries the run id, purpose, target, preset, focus, ceiling and
  `spend`.
- **The wallet (Codex on #553).** `lead_job_request` is not a wallet authority: a charge accepts only a
  `chat_start` or `plan_step` row naming the charged run with decision `start`
  (`domain/wallet.py:72-78`, `infrastructure/study_wallet_repository.py` `charge` and its decision
  check). Without more, a card-approved run would bypass the wallet cap with the wallet on. So, when
  `AIA_STUDY_WALLET_ENABLED` is on, the approval writes a wallet-authorising decision and charges the
  wallet in the same transaction as the start, in LO1's order: quote under the study lock, create
  the run, write the `lead_card` row naming that run (decision `start`), charge it as
  `DEEP_RESEARCH` or `INTERPRETATION_RESEARCH` at its ceiling. A refused charge (`outside_wallet`,
  `ceiling_unknown`, `no_wallet`) rolls the whole transaction back: no run, no ledger row. A person
  approving a card on the spot is judged by `start_verdict`'s `CHAT_START` rule (inside the wallet,
  refused outside); whether `StartPath` gets its own member is decided in the PR, with no rule of
  its own. With the wallet off, nothing is charged, as for every start today.
- **The authority: a new subject `lead_card`, not a single-step plan.** It is the smaller of the two.
  A single-step plan needs `lead_plans`, `lead_plan_steps`, the plan authority and the `lead_plan`
  workflow type (LO3, "the riskiest piece") and the plan card (LO4) before any Deep Research card
  could charge. A new subject is one value in `ApprovalSubject`, one in `CHARGE_AUTHORITIES`, and one
  migration (named here **M3b**, `lead_card` added to `approval_decisions.subject_type`'s CHECK, with
  its round-trip test in `test_approval_ledger.py`). The cost is the one LO16 wanted to avoid: a
  second migration on the same constraint. It also serves agent-job cards, which are not charged
  today either (`StartPath.PERSON`). Reusing `lead_job_request` as the authority was rejected: its
  `run_id` names the Lead turn's run and its decision is `approve` (`workflow_repository.py:2681-2715
  @ 095a3e68`), so it cannot name the charged run without changing what existing rows mean.
- Approved once: a second approval returns the same run. `NotAPaidRequest` stays for `research_run`
  only.
- `routers/lead.py` maps `LiveNotApproved` to 409 `live_settings_unapproved` with `missing` and
  `routes`, and maps the cost 409s. It answers `research_lead_disabled` (Q42) if 27b has not landed;
  whichever of the two lands second keeps one check.
- Tests:
  - an approval creates one run with its ledger row, and a second approval returns it;
  - a stale working revision is refused;
  - another study's target is 404;
  - a moved pin is refused;
  - the threshold asks, and once confirmed the row records `spend`;
  - on a priced composition without approved live settings: 409 with the keys, and nothing written;
  - with the Lead off: 409, with no workflow row and no reservation;
  - the run's spec and fingerprint equal those of a stage start with the same inputs;
  - with the wallet on, an approved card's run is charged once under its `lead_card` row, and a card
    whose ceiling is over the wallet's remainder is refused with no run, no ledger row and no charge;
  - with the wallet off, nothing is charged and nothing changes.
- Depends on DRL-0, LO5a.1, LO1 (done), the M3b migration (in this chunk, after LO16) and LO10 (or
  this chunk's own revision check for its kinds); ideally 27b.

**LO5a.3 (DRL-8, on LO5). Typed Deep Research starts.**
- LO5's matcher gains:
  - "Spusť rešerši k návrhu [rychlou|standardní]", STANDARD when neither is said;
  - "Spusť rešerši výsledků", with the target picked from the composer's code-built list (LO5a.1's
    candidates), never parsed from free text;
  - "Zopakuj rešerši";
  - "Zastav rešerši".
- Each runs in one transaction, in LO1's order (choice 4): quote under the study lock
  (`start_verdict(CHAT_START)`), create the run, write the `chat_start` row naming it, then charge
  the wallet as `DEEP_RESEARCH` or `INTERPRETATION_RESEARCH` at the ceiling.
  `StudyWalletRepository.charge` needs the run to exist (`unknown_run`, `study_wallet_repository.py`
  `charge`), so the charge comes after the create, never before; a refused charge rolls back the run
  and the row.
- It works with the Lead off (Q43).
- Tests:
  - with the Lead off, a typed design start writes `chat_start`, a charge and one run, while free
    text is 409;
  - outside the wallet, it is refused and nothing is written;
  - the order holds: the charge names the run created in the same transaction, and a charge refused
    after the create leaves no run, no `chat_start` row and no charge;
  - a typed stop cancels the run;
  - a journey on recorded web.
- Kill switch: `AIA_STUDY_WALLET_ENABLED`.
- Depends on LO5, LO1, DRL-0, LO5a.1 and 27b. **DRL-5 waits for it (Q48).**

**LO5a.4 (DRL-9, on LO3/LO4). Deep Research as plan-step kinds.**
- `lead_plan_steps.kind` takes `design_research` and `interpretation_research`.
  - A design step runs over the plan's immutable revision (D-04).
  - An interpretation step names a fixed target or one relative to an earlier step (Q47). Code
    resolves it when the step starts.
- The worker-side step calls `DeepResearchRuns.start` or `start_interpretation` under the plan
  authority, priced by DRL-0 from the worker's settings. It parks on any of:
  - a ceiling that grew (D-02);
  - the wallet;
  - `LiveNotApproved`;
  - a BLOCKED module (Q47).
- LO4's card shows one line per step: "Rešerše k návrhu · strop X USD".
- Tests:
  - an approved plan "fieldwork, then interpretation of step 1's `research_questions` module" runs
    both steps and charges two `plan_step` rows;
  - a grown ceiling parks;
  - a BLOCKED module parks the step and starts nothing;
  - a withdrawn plan (LO17) cancels the running Deep Research step;
  - the worker's ceiling equals the API's quote for the same spec.
- Kill switch: `AIA_LEAD_PLANS_ENABLED`.
- Depends on LO3, LO4, LO17 and DRL-0.

**LO5a (the acceptance).**
- At 1440 and 390 px, Deep Research can be started only through the Lead: an approved card, a typed
  command or a plan step.
- A direct `POST …/deep-research/runs` with the page's token meets the same gates.
- It is ticked together with `research-lead-workbench` 26f.1 (DRL-5).

**LO6 (DRL-10) and LO8 (DRL-11)** are tightened in their own paragraphs above, and **LO17**'s test in
the scope freeze section.

**Order.**
1. DRL-0 and DRL-1, in parallel.
2. LO5a.1.
3. LO5a.2, after LO10 (ideally after 27b).
4. DRL-6, which can go early.
5. DRL-4, after #550.
6. DRL-7.
7. LO5a.3 (on LO5), **then DRL-5 (Q48)**.
8. LO6's, LO5a.4's and LO8's parts, as their parents land.

### Findings

- **F-DRL-4. The Lead cannot see a Deep Research run.**
  - Anchor: `application/research_lead.py:858-866 @ 095a3e68` lists runs with
    `workflow_type=RESEARCH`, at most five.
  - Reproduction: start a Design Research run, post a Lead turn, and read the turn's frozen context.
    No Deep Research run is in it.
  - Consequence: "Kde jsme?" omits a running or finished rešerše, and the Lead may prepare a
    duplicate.
  - Smallest fix: LO5a.1's `deep_research` layer.
  - Test: LO5a.1's "a Deep Research run appears in the context".
- **F-DRL-5. The Interpretation target is fixed in the browser.**
  - Anchor: `apps/web/src/lib/api.ts:1380-1385 @ 095a3e68` always sends `ANALYSIS_MODULE`
    `research_questions`.
  - Reproduction: `git show 095a3e68:apps/web/src/lib/api.ts | sed -n 1380,1385p`.
  - Consequence: six of ADR 0021's seven target kinds have no way in from the product, although
    `POST …/runs/interpretation` accepts them.
  - Smallest fix: LO5a.1's candidates, all seven kinds (Q44).
  - Test: an LO5a.2 approval over a battery-object candidate starts a run whose target is that object.
- F-DRL-1 and F-DRL-6 belong to `research-lead-workbench`. F-DRL-2, F-DRL-3 and F-DRL-7 belong to
  `deep-research-web-search` (chunk 55).

### Doc follow-up (Deep Research under the Lead)

- `open-items.md`: number F-DRL-4 (owner LO5a.1) and F-DRL-5 (owner LO5a.1).
- `mvp-master-plan.md` and `mvp-execution-contracts.md`: the register rows listed in this PR's
  description.
- ADR 0026 *Accepted with*: a Lead card starts Design and Interpretation Research on the server
  through `approve_request` (LO5a.2), with the Q44-Q47 answers.
- ADR 0028 (the wallet): a person's approval of a Lead card is a charge authority, `lead_card`
  (migration M3b on the subject CHECK, LO5a.2); LO16's delivered note gains the same line.

## LO5 delivered (2026-10-21, Sprint 5 part 3, stacked on research-lead-workbench 27b's #561)

**The vocabulary** (`domain/lead_commands.py`, pinned in
`packages/aia_core/tests/fixtures/lead_commands/commands.json`, served on `GET /lead` as
`commands`). One Czech imperative per start, named as the card registry names it:

| Typed | Start |
|---|---|
| Analyzuj zadání | `agent_job:analyze_brief` |
| Navrhni dotazník | `agent_job:build_questionnaire` |
| Uprav dotazník | `agent_job:optimize_questionnaire` |
| Navrhni audienci | `agent_job:propose_audience` |
| Navrhni dimenze | `agent_job:suggest_dimensions` |
| Zkontroluj návrh | `agent_job:critique_design` |
| Pomoz s návrhem | `agent_job:design_copilot` |
| Zeptej se na klientské znalosti | `agent_job:answer_memory` |
| Spusť výzkum | `research_run` |

The whole message must be the command after a fixed normalisation (NFC, case folded, whitespace
collapsed, an optional leading `/`, one trailing `.` or `!`); diacritics are kept exactly, so
"spust vyzkum" is a message, and so is "Prosím spusť výzkum". A design job may carry the person's
instruction after a colon ("Navrhni dotazník: krátce"); the run takes none. Nothing near a
command is read as one: a guess at a start is the thing LO5 exists to prevent.

**The path.** `ResearchLead.post` matches before anything else: a command is stored on the
person's own turn (`study_lead_turns.command`, migration `c663617cf79b`, CHECK
`command IS NULL OR actor = 'person'`), with no Lead turn and no run, Lead on or off, hatched or
not (Q43). Free text with the Lead off is still 409 `research_lead_unavailable`.
`approve_request` reads the stored turn: a person's turn naming a command goes to
`application/lead_chat_start.py` `approve_chat_start`, never through the Lead switch (D22); a
Lead turn keeps 27b's guard. The approval runs in LO1's order, in the request's one transaction:

1. with `AIA_STUDY_WALLET_ENABLED`: `StudyWallets.quote` under the study lock and
   `money.start_verdict(CHAT_START)`: outside the wallet or an unknown ceiling is 409
   `outside_wallet` / `ceiling_unknown` (nothing written), the threshold asks
   (`cost_confirmation_required`); with the wallet off, nothing is quoted or charged;
2. the work's own start: `ResearchAgentJobs.start` (the job's reservation is its ceiling, LO15's
   threshold and `spend` row) or `ResearchRuns.start` on the deployment's run settings
   (`routers/research.py` `run_start_settings`, the same values `POST …/research/runs` passes;
   its refusals through the shared `run_start_errors`);
3. `WorkflowRepository.record_chat_start`: subject the run, decision `start`, the turn, the start,
   the ceiling and the Design Revision; `APPROVE_GATE`, which the worker's scope withholds;
4. `StudyWallets.charge` (`AGENT_JOB` or `RESEARCH_RUN`) under that row; a refusal rolls the run
   and the row back with it.

Approved once: a second approval returns the run its `chat_start` row names. A start that finds
its work already there (the same job on the same design, the revision's run) returns it and
writes nothing: that work was authorised when it was created.

**Choices recorded.** (1) A typed research run starts on the deployment's defaults: the default
persona source, LIVE, no answerability acknowledgement (a gap with the gate on is refused by the
run's own rule and the person goes to Spuštění). (2) The command is a column, not a new turn
kind: `kind` stays `message`, so every reader of the conversation is unchanged. (3) The matcher
runs before the Lead's switch, its lock and its busy check: a typed start is the person's, not a
conversation turn.

**Not here.** Deep Research typed starts (LO5a.3) need DRL-0 (#555) and LO5a.1, neither on
develop; `design_research` and `interpretation_research` are not matched yet. The composer's
recognition and card in the web are the next PR, after #550 (Lead chat cards) merges.

**The web's card (`feature/lead-typed-start-card`, 2026-10-22).**
- A person's turn naming a `command` is followed by their own card in the conversation:
  `RequestCard` with `typed`, the eyebrow "Váš příkaz", and the request built by `commandRequest`
  (`lib/lead.ts`). The card reads the server's `command`, never the text; the instruction after a
  colon is the card's why.
- The card starts the work through `…/request`, the run too (`Workbench.tsx` `onRequest`: a typed
  start is approved whatever its kind), with the threshold's confirmation as for every card. The
  job or run it started follows under it.
- Found because `lead_cards_journey.mjs` failed on develop (b6ac25c5). "Spusť výzkum." became a
  command, and the journey waited for a Lead answer that no longer comes. The journey now:
  - starts a job by typed "Zkontroluj návrh";
  - asks the Lead with "Prosím, spusť výzkum." (a message, not a command) for its run card.
- Tests: `LeadPane.test.tsx` "follows a person's typed start with their own card…", `lead.test.ts`
  `commandRequest`, and `lead_cards_journey.mjs` "a typed start shows the person's own card, and
  its approval starts the job through …/request".
- Not built: the composer recognising a command before it is sent (a hint as the person types),
  and the commands list (`GET /lead` `commands`) shown as suggestions.

Tests: `packages/aia_core/tests/test_lead_commands.py` (the fixture, every worker and the run
once, matches and near-misses), `test_lead_chat_start.py` (the row authorises its charge; the
worker cannot write one), `apps/api/tests/test_lead_chat_start_api.py` (Lead off: a command taken,
free text 409; Lead on: no model turn; in one switched-off state the model's card 409 and the typed
card started; once only; the threshold; a typed run; a design not ready writes nothing; another
researcher's card 404; with the wallet on: charged under its row, outside or unknown writes
nothing, a charge refused after the create rolls back; the CHECK). Migration: `alembic upgrade
head`, `alembic check`, `downgrade base`, `upgrade head` on PostgreSQL 16.

### Doc follow-up (LO5)

- `CLAUDE.md` map, `routers/lead.py`: "a message that is exactly a typed start command
  (`domain/lead_commands.py`) is stored as the person's command, Lead on or off, with no model
  turn; `POST …/turns/{turn_id}/request` starts it (ledger `chat_start`, the wallet when on);
  `GET /lead` lists `commands`".
- `CLAUDE.md` map, `domain/`: "`lead_commands.py` the composer's typed start commands, matched
  by code (LO5), pinned in `tests/fixtures/lead_commands/commands.json`"; `application/`:
  "`lead_chat_start.py` approve_chat_start: quote, create, `chat_start`, charge (LO1's order)";
  `infrastructure/`: "`workflow_repository.record_chat_start`".
- ADR 0028 *What enforces it*: the `chat_start` writer and its order.
- ADR 0026 *Accepted with*: typed start commands bypass the model and the Lead's switch (Q43).

### Finding: a typed start approved again on the same design was never decided (2026-10-22, `fix/typed-start-reuse`)

1. **Claim.** A typed start approved on a job that an earlier approval had already started for the
   same design writes nothing for its own turn. Its card stays undecided, no job card follows it,
   and after a reload it asks again.
2. **Anchor.** `application/lead_chat_start.py:219 @ fe85aa54` writes the `chat_start` row only
   when `started.created`. `chat_start_decisions` reads a card's decision from that row alone.
3. **Reproduction.**
   - `apps/api/tests/test_lead_chat_start_api.py::test_a_typed_start_approved_on_a_job_already_started_decides_its_card_and_starts_nothing`
   - In a browser: type "Zkontroluj návrh" twice on the UI workbench and approve both. The second
     answers 200 with the first job, and `GET /lead` gives that turn `request_decision: null`.
4. **Consequence.** The person clicks "Spustit úlohu" and nothing appears. The card read
   "Rozhodnuto" beside "Spustí se až vaším potvrzením."; after a reload it is open again, and
   every click returns the same job. `lead_cards_journey` failed on a second run on one workbench
   (:145) for this reason.
5. **Fix.** The found job decides the card with a `chat_start` row of decision `reuse`, which names
   the run in its comment only and leaves `run_id` null.
   - `run_id` is null because spend attribution counts every `chat_start` row whose `run_id` names
     the run as a start approval (`workflow_repository.py:194 @ fe85aa54`). The second approver
     started nothing and paid for nothing.
   - It is no charge authority, which needs decision `start`.
   - `request_decision.reused` tells the web, and the card reads "Už proběhlo / Tato úloha pro
     tento návrh už proběhla". The job is shown once, where it started.
   - A decided card no longer says "Spustí se až vaším potvrzením.".
6. **Test.** The API test above, plus the typed research run's second approval in
   `test_a_typed_research_run_starts_on_the_deployments_run_settings` and `LeadPane.test.tsx`
   "says a typed start approved again found the job already done, and shows that job once".
   `lead_cards_journey` accepts either outcome at its typed start, so it runs again on one
   workbench.

   - Review of #682: a found job is also not held to the wallet or the threshold again.
     `existing_start` asks the start itself for the key it would use (`_probe`, raised before
     any gate or write, so the key code is never copied), and `quote` runs only when a run will be
     created. On the agent path the Design Revision is now submitted before the quote, as the
     run path already did; a refusal rolls the whole request back. A reused turn's run is not
     "linked" in `conversationTimeline`, so a job or run that no card started (a run started on
     Spuštění) stays in the conversation. Tests: the wallet case with a cap of exactly one
     reservation, `test_a_typed_start_found_already_started_asks_no_confirmation` (both fail at
     ab1e892d), and `lead-cards.test.ts` "leaves a run a typed start found already started where
     it is".

### Doc follow-up (typed start reuse)

- ADR 0028 *What enforces it*: "a typed start approved on a run another approval already started
  writes a `chat_start` row of decision `reuse` naming the run in its comment only, never in
  `run_id`: neither a start approval for attribution nor a charge authority".

## The typed analysis retry (2026-10-22, `feature/lead-analysis-retry`; LO5, for artifact-analysis ANL6)

The registry already named `analysis_retry` among Analýza's starts, but nothing started it from
the conversation. A person types **"Zopakuj analýzu"** (no instruction), matched by code
(`domain/lead_commands.py` `ANALYSIS_RETRY`, pinned in `commands.json`), and approves its card.
- **One path with the stage.** `approve_chat_start` takes the study's newest research run that ran
  analysis (`_newest_analysed_run`; one still running is refused, never passed over for an older
  one) and calls the stage route's own `retry_failed_modules`: the same threshold (LO15), frozen
  dataset, idempotency and refusals by name (`analysis_not_retryable` with `run_not_finished`,
  `analysis_not_in_run`, `dataset_missing`, `specification_missing`, `nothing_to_retry`, and
  `no_analysed_run` when the study has no run that ran analysis at all), mapped
  once in `run_start_errors` for both routes. It writes `chat_start` naming the retry run (`reuse`
  when the retry was already there).
- **No wallet charge** (the product manager's decision (b), 2026-10-22): the stage route charges
  none, so neither does the typed start; the card says so in words ("Opakování analýzy se
  nestrhává z Peněženky."). Linked to F-LO1-1 above. With the wallet off (everywhere today)
  nothing changes.
- **The store.** `RunStartSettings.store` carries the artifact store the retry reads the run's
  stored outcomes from; the Lead's approve route passes it.
- **The card** (`LeadPane` `RequestCard`, kind `analysis_retry`): what it does, that no new data is
  collected, and the payment line; approved through the same `onRequest` as every typed start.
- **Tests.** `test_lead_chat_start_api.py` "a typed analysis retry with no analysed run is refused by
  name", "… of a run still going is refused as the stage route is" (the stage route answers the
  same), "… starts the stage retry on the newest analysed run" (the stage's start, the confirmation
  passed on, `chat_start` with no ceiling, no charge with the wallet on); `test_lead_commands.py`;
  `lead.test.ts` `commandRequest`; `LeadPane.test.tsx` "shows a typed analysis retry as the stage's
  retry…".
- **Not here:** removing the stage's own retry buttons is ANL6's (Analýza, behind 26f).
- **Follow-up (the PM's optional points on #744, `feature/lead-analysis-retry-pin`).**
  - *The card names its run.* GET /lead answers `analysis_retry_run` (the newest analysed run, by
    `newest_analysed_run`'s rule) and the card shows "Který běh"; approval sends `retry_run_id`, and a
    newer analysed run since is 409 `analysis_retry_target_moved` (`current_run_id`), nothing written,
    asked as LO10 asks a moved design (`ANALYSIS_RETRY_MOVED_QUESTION`), then retried on the newer
    run only on the person's yes. No migration: the run is bound at approval, as the revision is.
  - *The Peněženka only with the wallet on.* GET /lead answers `wallet_enabled`; the retry's "nestrhává
    se z Peněženky" and the typed run's "… a Peněženka se kontrolují" show only when it is on.
  - Tests: `test_lead_chat_start_api.py` "a typed analysis retry names its run and never retries a newer
    one unasked", "the conversation says whether the wallet is on"; `LeadPane.test.tsx` "… names the run
    it retries and starts it on that run", "says a typed start is not charged to the Peněženka only with
    the wallet on"; `Workbench.layout.test.tsx` "is approved on the run its card named, and on a newer one
    only after the person's yes". The web tests fail without the change.

### Doc follow-up (typed analysis retry)

- `CLAUDE.md` map, `application/lead_chat_start.py` (and the commands list): "Zopakuj analýzu"
  starts `retry_failed_modules` on the newest analysed run, `chat_start`, no wallet charge.

