---
status: in-progress
chunks:
  - "[x] LO0. The contract ADR and the money vocabulary: wallet cap, `budget_usd`, `spend_confirm_usd`, the client ceiling, `clients.budget_usd`, OI-64, one precedence"
  - "[ ] LO1. The wallet (M4): `study_wallets`, `_raises`, `_charges` and `clients.wallet_ceiling_usd`; charges for paid work including Deep Research"
  - "[ ] LO2. A typed `start_run` with no `confirm_cost_usd`, and an import rule that a plan step cannot reach the confirming start"
  - "[ ] LO3. `lead_plans` and `lead_plan_steps` (M5), the plan authority capability issued by `ScopeResolver`, the `lead_plan` workflow type, behind `AIA_LEAD_PLANS_ENABLED`"
  - "[ ] LO4. The plan card: the steps (including "start fieldwork, ceiling X USD"), approved once, stopping at every gate it does not cover"
  - "[ ] LO5. Direct human chat start: the typed command the server matches, ledger `chat_start`, the model not in the path"
  - "[ ] LO6. The continuation turn: a finished step enqueues a Lead turn with typed results; no polling"
  - "[ ] LO7. The Lead's context layers per ADR 0026 decision 2: readiness, question outlook, what changed since its last turn, other people's changes, and the execution state (status, park code, spend, selection receipt, QC)"
  - "[ ] LO8. `ResultsContext`: type, class (`MaterialRule` for results, module text, maps, report text), lineage, bound, an external-evidence slot labelled L; and the decision on a read tool against ADR 0026 decision 3"
  - "[x] LO9a. The worker contract, early (W0, the first deliverable of `research-lead-workbench` 11): `LeadWorkerSpec` as a type, one row per worker (id, closed task, context layer, data-class rule, capability, reservation, prompt id and pin, switch, card kind, result kind), with its fixture"
  - "[ ] LO9c. A results-worker job shape (W2, before LO9b): a workflow type and step kind keyed on (run_id, target), frozen inputs by artifact id and SHA-256, its own context builder and executor behind its own switch, sharing the worker row, prompt pin and usage ledger"
  - "[ ] LO9b. The three new workers as rows (W3): a `REPORT_WRITING` binding, result kinds and accept destinations, per-worker price and keys"
  - "[ ] LO10. `approve_request` bound to the revision shown on its card, and a clean error where the 96 KB Lead context meets the 64 KB agent limit"
  - "[ ] LO11. The Lead over time (M7): `researcher_lead_signals`, proposed updates the researcher approves each, a reader and rollback for Lead file revisions; no handover or admin read (D-32 to D-34); a departed member's Lead sealed, then deleted at the retention end (Q14)"
  - "[ ] LO12a. The route-class refusal says who fixes it (W0): on the job error, the Lead pane, source proposals and Progress, from the refusal codes that exist today, with a link to the runbook; static copy, no read of the route"
  - "[ ] LO12b. A pre-flight read of the AI route (W1): the worker publishes a composition record the API, Settings and the Lead pane read (shared with `deep-research-web-search#52`), and the new refusal reasons"
  - "[ ] LO13. Client-level paid AI (source proposals, `clients.budget_usd`) recorded as an explicit exception to "every AI action goes through the Lead" in AC-02"
  - "[ ] LO14. The Lead's cost per turn measured, and an `AIA_LEAD_*` kill switch and budget line"
  - "[x] LO16. The approval ledger's subject types (lane migration M3, W0, the first migration): `approval_decisions.subject_type` extended with `wallet`, `lead_plan`, `plan_step`, `chat_start`, `data_contract`, `map_snapshot` and `sociomap_unlock`; S3 writes it"
  - "[x] LO15. Server spend enforcement (W0): `ResearchAgentJobs.start` and `rebuild` apply `spend_confirm_usd` as `ResearchRuns.start` does, and record the confirmation in the ledger; tested through direct HTTP start and rebuild and through the Lead's approve path"
  - "[ ] LO5a. Deep Research from the Lead: a plan-step kind and a typed chat start, priced by deep-research-web-search 55's ceiling (D-12)"
  - "[ ] LO12c. The composition digest stored on each run and served over HTTP (D-09; the record #513 called MP6b)"
  - "[ ] LO17. Stopping the Lead: cancel a running turn, withdraw an approved plan (the current step finishes or is cancelled, nothing after it starts), with the workbench build line (D-18)"
  - "[ ] LO18. The Lead's turns stream, take a file from the composer, and comment unprompted after the researcher pauses editing, each such comment a paid turn inside the wallet (D-39)"
  - "[ ] LO19. A study's context file: a Markdown file per study, built by code from the study's shared state and refreshed on every change, read by every researcher's Lead in that study as its study layer (Q5)"
  - "[ ] LO20. Hledat na webu: the Lead's governed web search through RetrievalGate, several results with inline citations in the turn, OPEN clients without a card and CLASSIFIED clients behind a plan card, each search charged to the wallet (Q6, Q24)"
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
The data for the two meters: spent against `budget_usd`, and the wallet remaining on click, with Czech labels distinct from the confirmation threshold's. Server-computed ceilings, holds, settlement and concurrent accounting are preserved (a start never exceeds the cap; an unknown cost counts as its ceiling). Test: a raise needs the researcher inside the ceiling and an approver above it; a charge above the wallet parks, never fails.

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

**LO7. The Lead's context layers per ADR 0026 decision 2: readiness, question outlook, what changed since its last turn, other people's changes, and the execution state (status, park code, spend, selection receipt, QC)**  
`freeze_context` has none of these (`domain/research_lead.py:803-819`). The Lead's answer to "Kde jsme?" is built from them.

**LO8. `ResultsContext`: type, class (`MaterialRule` for results, module text, maps, report text), lineage, bound, an external-evidence slot labelled L; and the decision on a read tool against ADR 0026 decision 3**  
Written in **W1**, not W2. S2 and S3 write providers against it. Test: a result with Class A lineage is refused by a Class-C-only route. Interfaces I1.

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

**LO11. The Lead over time (M7): `researcher_lead_signals`, proposed updates the researcher approves each, a reader and rollback for Lead file revisions; no handover or admin read (D-32 to D-34); a departed member's Lead sealed, then deleted at the retention end (Q14)**  
File revisions have no reader today (`revisions()` has no caller). Turns stay private (Q26). A Lead is never handed over and no admin reads another researcher's Lead files (the owner, 2026-10-20, D-32 to D-34; the earlier "admin read and handover" is withdrawn). Another member's ability to accept a proposal is **not** a Lead-lifecycle matter and is not decided here: Q16 makes proposals shared, and `working-copy-edit-ops#WCE6` builds it (gap G42).

**LO12a. The route-class refusal says who fixes it (W0): static copy on the four surfaces**  
The refusal surfaces in the job error, the Lead pane, source proposals and Progress, and none says an operator fixes it (the AI route's classes are set in SSM, not on Settings, which is read-only). The copy is keyed by the refusal codes that exist today (`egress_route_not_approved_for_class` and its siblings) and names the operator step and the runbook; it reads nothing and needs no composition record. Test: each code on each surface renders its who-fixes-it line. Interfaces I24.

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
  reservation settles; a withdrawn plan starts no further step.
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
