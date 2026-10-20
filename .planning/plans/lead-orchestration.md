---
status: planned
chunks:
  - "[ ] LO0. The contract ADR and the money vocabulary: envelope cap, `budget_usd`, `spend_confirm_usd`, the client ceiling, `clients.budget_usd`, OI-64, one precedence"
  - "[ ] LO1. The envelope (M4): `study_envelopes`, `_raises`, `_charges` and `clients.envelope_ceiling_usd`; charges for paid work including Deep Research"
  - "[ ] LO2. A typed `start_run` with no `confirm_cost_usd`, and an import rule that a plan step cannot reach the confirming start"
  - "[ ] LO3. `lead_plans` and `lead_plan_steps` (M5), the plan authority capability issued by `ScopeResolver`, the `lead_plan` workflow type, behind `AIA_LEAD_PLANS_ENABLED`"
  - "[ ] LO4. The plan card: the steps (including "start fieldwork, ceiling X USD"), approved once, stopping at every gate it does not cover"
  - "[ ] LO5. Direct human chat start: the typed command the server matches, ledger `chat_start`, the model not in the path"
  - "[ ] LO6. The continuation turn: a finished step enqueues a Lead turn with typed results; no polling"
  - "[ ] LO7. The Lead's context layers per ADR 0026 decision 2: readiness, question outlook, what changed since its last turn, other people's changes, and the execution state (status, park code, spend, selection receipt, QC)"
  - "[ ] LO8. `ResultsContext`: type, class (`MaterialRule` for results, module text, maps, report text), lineage, bound, an external-evidence slot labelled L; and the decision on a read tool against ADR 0026 decision 3"
  - "[ ] LO9a. The worker contract, early (W0, the first deliverable of `research-lead-workbench` 11): `LeadWorkerSpec` as a type, one row per worker (id, closed task, context layer, data-class rule, capability, reservation, prompt id and pin, switch, card kind, result kind), with its fixture"
  - "[ ] LO9b. The three new workers as rows (W3): a `REPORT_WRITING` binding, result kinds and accept destinations, per-worker price and keys"
  - "[ ] LO10. `approve_request` bound to the revision shown on its card, and a clean error where the 96 KB Lead context meets the 64 KB agent limit"
  - "[ ] LO11. The Lead over time (M7): `researcher_lead_signals`, proposed updates the researcher approves each, a reader and rollback for Lead file revisions, the admin read and handover, a departure trigger"
  - "[ ] LO12. The route-class refusal says who fixes it: a pre-flight read of the AI route and a message with a link"
  - "[ ] LO13. Client-level paid AI (source proposals, `clients.budget_usd`) recorded as an explicit exception to "every AI action goes through the Lead" in AC-02"
  - "[ ] LO14. The Lead's cost per turn measured, and an `AIA_LEAD_*` kill switch and budget line"
  - "[ ] LO15. Server spend enforcement (W0): `ResearchAgentJobs.start` and `rebuild` apply `spend_confirm_usd` as `ResearchRuns.start` does, and record the confirmation in the ledger; tested through direct HTTP start and rebuild and through the Lead's approve path"
---
# Lead orchestration: the envelope, the plan card, the continuation turn and the Lead over time

The orchestration the prototype and the owner describe: a per-study envelope, a plan approved once, a chat start, a continuation turn that returns typed results to the Lead, its context layers, its workers and its lifecycle. Written 2026-10-19 from `.planning/evidence/mvp-master-traces/trace-4-lead-governance.md` and `trace-2-sample-execution.md`.

**Owner: S1.** Takes the gap rows G1, G11, G12, G13, G15, G16, G17, G20, G39 and interfaces I1, I3, I4, I22, I23 of `mvp-master-plan.md` §6.1 and serves AC-02, AC-03, AC-04, AC-15 and gate I-1.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- A per-study envelope for paid work, set by the researcher up to a client or organization ceiling; everything inside it, including the fieldwork run, no expiry until the study closes, priced Deep Research inside it (F13, Q14).
- The researcher approves a plan once and the Lead runs its steps; a plain chat request from a person starts a run inside the envelope without a plan card; a Lead-initiated run needs an approved plan (Q14, Q25).
- Each researcher has their own Lead, private to them; an organization admin can read its files and notes, never its turns, and hand it on as a copy with personal notes removed; the Lead proposes updates to its own files and the researcher approves each (Q18, Q19, Q26).
- Two meters in the header, the rest on click (Q20); two to three parallel jobs (target architecture).
- The spend limit is a **confirmation threshold** (`spend_confirm_usd`, null means never ask) and the cap is `budget_usd`; the envelope is defined against `budget_usd` and never against the threshold (the owner, 2026-10-19, after the traces).

## Chunks

**LO0. The contract ADR and the money vocabulary: envelope cap, `budget_usd`, `spend_confirm_usd`, the client ceiling, `clients.budget_usd`, OI-64, one precedence**  
Supersedes MVP-13 in the ADR text. Corrects the architecture and cohesion statements that call the spend limit a hard stop. Test: a document check that the word "hard stop" is not applied to `spend_confirm_usd`. Interfaces I4.

**LO1. The envelope (M4): `study_envelopes`, `_raises`, `_charges` and `clients.envelope_ceiling_usd`; charges for paid work including Deep Research**  
The data for the two meters: spent against `budget_usd`, and the envelope remaining on click, with Czech labels distinct from the confirmation threshold's. Server-computed ceilings, holds, settlement and concurrent accounting are preserved (a start never exceeds the cap; an unknown cost counts as its ceiling). Test: a raise needs the researcher inside the ceiling and an approver above it; a charge above the envelope parks, never fails.

**LO2. A typed `start_run` with no `confirm_cost_usd`, and an import rule that a plan step cannot reach the confirming start**  
`ResearchRuns.start` takes the confirmation as a function argument (`research.py:724-742`), so "a plan authority holds no `APPROVE_GATE`" does not protect it. The Run stage button, the plan card and the chat start all call the one start with their pins (persona source, child, acknowledgement). Interfaces I3.

**LO3. `lead_plans` and `lead_plan_steps` (M5), the plan authority capability issued by `ScopeResolver`, the `lead_plan` workflow type, behind `AIA_LEAD_PLANS_ENABLED`**  
The riskiest piece: the most tests and a kill switch. A step that reaches a gate the plan does not cover parks.

**LO4. The plan card: the steps (including "start fieldwork, ceiling X USD"), approved once, stopping at every gate it does not cover**  
The prototype's decision card for a run start is this card with one item. The UI is `research-lead-workbench` 23; this chunk is the contract and the ledger rows (`lead_plan`, `plan_step`, M3).

**LO5. Direct human chat start: the typed command the server matches, ledger `chat_start`, the model not in the path**  
The security condition: a start is authorised by a person's own typed command matched by the server, never by a model's interpretation of text. Inside the envelope only.

**LO6. The continuation turn: a finished step enqueues a Lead turn with typed results; no polling**  
Turns are person-started only today (`research_lead.py:763-790`). A result reaches the Lead as an artifact reference plus fields code has validated, never a worker's free text (a summary derived from web text is an injection path). Test: a step finishing wakes one turn with its results; a failed step wakes one with the park reason.

**LO7. The Lead's context layers per ADR 0026 decision 2: readiness, question outlook, what changed since its last turn, other people's changes, and the execution state (status, park code, spend, selection receipt, QC)**  
`freeze_context` has none of these (`domain/research_lead.py:803-819`). The Lead's answer to "Kde jsme?" is built from them.

**LO8. `ResultsContext`: type, class (`MaterialRule` for results, module text, maps, report text), lineage, bound, an external-evidence slot labelled L; and the decision on a read tool against ADR 0026 decision 3**  
Written in **W1**, not W2. S2 and S3 write providers against it. Test: a result with Class A lineage is refused by a Class-C-only route. Interfaces I1.

**LO9a. The worker contract, early (W0, the first deliverable of `research-lead-workbench` 11): `LeadWorkerSpec` as a type, one row per worker, with its fixture**  
One row defines a worker once: id, closed task, context layer, data-class rule, capability, reservation, prompt id and pin, switch, card kind, result kind (`mvp-cohesion.md` F5). Chunk 11's command registry and the W1 artifact chunks depend on this row; the three new workers are rows, not three designs. Test: a worker with a missing field is refused at registration.

**LO9b. The three new workers as rows (W3): a `REPORT_WRITING` binding, result kinds and accept destinations, per-worker price and keys**  
The three workers (map interpreter, report writer, straight-liner check) have no binding, no accept path and no price today. The accept destinations are `report-delivery#RD6` and `run-qc-and-checkpoint#RQC4`. **Prerequisite for the report writer's semantic edits:** ADR 0026 decision 4 requires an ADR and a deterministic admission rule for semantic report edits before any command exists; the feature is settled, the ADR is the work (`report-delivery#RD6`).

**LO15. Server spend enforcement (W0): `ResearchAgentJobs.start` and `rebuild` apply `spend_confirm_usd` as `ResearchRuns.start` does, and record the confirmation in the ledger**  
`ResearchAgentJobs.start` (`application/research.py:1311-1407`) reads no `spend_confirm_usd`, while `ResearchRuns.start` does (`:739`); the only check on a design job today is in the Lead's approve path (`application/research_lead.py:678-760`). Removing the manual buttons (D15) is a UI change and does not enforce a server rule: `mvp-cohesion.md` F5 adopts this check as the first code change, and `research-lead-workbench` F1 is no longer an owner decision. `budget_usd` is the cap; the envelope and the `spend_confirm_usd` confirmation are distinct. Test: a direct HTTP start and a rebuild above the threshold are refused without a covering confirmation and write the ledger row with one; the Lead's approve path still passes; a start under the threshold is unchanged. Interfaces I4.

**LO10. `approve_request` bound to the revision shown on its card, and a clean error where the 96 KB Lead context meets the 64 KB agent limit**  
`approve_request` submits whatever the working copy is at approval time, unlike `decide_edits`, which needs `base_revision`. Test: approving a card whose revision moved is refused with a message, not a 500.

**LO11. The Lead over time (M7): `researcher_lead_signals`, proposed updates the researcher approves each, a reader and rollback for Lead file revisions, the admin read and handover, a departure trigger**  
File revisions have no reader today (`revisions()` has no caller). A second researcher cannot accept the first Lead's edit blocks (turns are private): the rule is stated here and tested.

**LO12. The route-class refusal says who fixes it: a pre-flight read of the AI route and a message with a link**  
The refusal surfaces in the job error, the Lead pane, source proposals and Progress, and none says an operator fixes it. The API cannot evaluate class, so the worker publishes a composition record the API and Settings read (shared with `deep-research-web-search#52`). The Lead pane gains `retention_unspecified`, `residency_violation` and `training_exclusion_missing`. Settings is read-only and stays so. Interfaces I15, I24.

**LO13. Client-level paid AI (source proposals, `clients.budget_usd`) recorded as an explicit exception to "every AI action goes through the Lead" in AC-02**  
A wording change to the criterion, made with the acceptance harness, not a behaviour change. Interfaces I23.

**LO14. The Lead's cost per turn measured, and an `AIA_LEAD_*` kill switch and budget line**  
The prototype's own documentation lists the unmeasured cost per turn as a gap to production.

## Open: owner clarifications

None here. The envelope sits beside `spend_confirm_usd`, which stays a per-start confirmation (settled; `mvp-master-plan.md` §11.2).
