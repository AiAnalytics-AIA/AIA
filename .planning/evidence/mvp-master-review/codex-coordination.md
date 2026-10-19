# Independent MVP planning review — 2026-10-20

Reviewed by ChatGPT/Codex at the product owner's request, in coordination with the
Claude Code session maintaining PR #501. Baselines: #500 `8671f244`,
#501 `694f247c`. This is a planning review, not runtime acceptance.
No application code, switch, AWS setting or methodology was changed.

## 1. Delivery conclusion

The Research Lead plus eleven artifact stages matches the prototype's direction.
The MVP is achievable as a dependency-ordered delivery, but the current master
register does not yet make it executable: gaps must have actual child-plan
chunks, acceptance criteria must reflect settled decisions, and operational
activation must be proven separately from code existing. End-Q1-2027 is a
target, not a supported delivery forecast until effort/capacity and external
methodology decisions have been assigned.

The canonical path is: client/study → brief and reviewed inputs → design,
questionnaire, audience, dimensions and sample → population-grounded fieldwork →
deterministic aggregates and Sociomap → admitted analysis and external context →
separate report/snapshot approvals → approved exports. The workbench simplifies
control and presentation; it does not change the Sociomap methodology.

## 2. Findings that must be resolved in the plans

| ID | Finding | Required planning change | Owner / gate |
|---|---|---|---|
| CR-01 | Shared edits, operations, presence, per-change accept, envelopes, plan authority, ResultsContext and Lead lifecycle are described in the architecture but have no executable child-plan chunks | Create the six child plans or add exact chunk IDs to current plans; map every G/I row to a chunk, contract and test | S1/S2/S3, before their wave |
| CR-02 | `spend_confirm_usd` is a confirmation threshold; `budget_usd` is the hard budget | Define envelope against budget, not the threshold. Use distinct Czech labels. Preserve server-computed ceilings, holds, settlement and concurrent accounting | S1/S3, W1 |
| CR-03 | Current AC-02 requires per-job cards; later F13/Q25 permits an approved plan and direct human chat starts | Amend acceptance prose and machine statements together. Model authority cannot fabricate a human confirmation. Uncovered gates park | S1/S3, I-1 |
| CR-04 | Current AC-11 and harness still depend on the deferred Class B provider | Carry #500 OPEN posture into both acceptance forms, harness, architecture and roadmap. Pin enqueue posture; retry copies it. Preserve model class and fictional-client identity | S2/S3, I-R |
| CR-05 | Reach is called a side chain that may slip until W5 although I-R blocks W2; chunk 54 is missing from W0's wave row | Make live probes and route provisioning explicit predecessors. Omitting archive from a W0 smoke does not pass an I-R that requires archive | S2/S3, I-R |
| CR-06 | `two-roles-human-ai-gates` 5b.4 still says no client report exists | Retire that stale blocker. Add report-version and map-snapshot approval chunks, exact artifact fingerprints, download checks and self-approval tests | S3/S1, I-2/I-3 |
| CR-07 | Client PDF is absent although AC-13 requires it | Plan its implementation. Do not remove it or weaken evidence/legal gates without an explicit scope override. Separate renderer availability from approved delivery | S3, I-3 |
| CR-08 | `evidence-integrity` calls the new citation rule a 95% tightening, and asks what replacement means despite F18 | Correct to a new all-findings admission rule; replacement already means a new linked run. Decide only the handling of a module with no admissible finding | S2, I-3 |
| CR-09 | System prompt plan conflicts with MVP-32 | Eleven Lead workers and eight analysis modules are editable/pinned; respondent and Deep Research method prompts remain read-only. New workers need binding, price, result type, accept path, MaterialRule and reuse identity | S1/S2, AC-03 |
| CR-10 | Segment maps have no stored per-respondent descriptors; persona topics are not segmentation variables | Specify the producer, lineage, storage, allowed descriptor set, support/suppression and consumer contract; require an actual own-dimension consumer, not just a child file | S2/S3, I-2/AC-10 |
| CR-11 | AC-06 is treated as already proven despite interrupted fieldwork replay | Checkpoint respondent/block progress and paid-call identity; possibly-billed uncertainty must not trigger automatic paid replay. Keep analysis-only retry distinct | S2, before expanded paid execution |
| CR-12 | API tier A cannot prove the eleven artifact layouts or prototype interactions | Add real browser journeys for hand edits, pointing, proposals, keyboard/focus, stale states, all eleven stages and map view-only operations | S1/S3, every artifact/I-5 |
| CR-13 | Production may follow acceptance in one risk row, but the MVP definition requires production release | Distinguish tier-A pass, tier-B pass and release. Restore, rollback, delete, activation and production credentials/config must be evidenced before release | S3, I-5 |
| CR-14 | Deep Research evaluations 25/26/39 have no explicit wave/disposition before final live gate | Early activation 51 is permitted under its existing guards. Specify which evaluations gate final 27, thresholds/owner and budget; do not label an activation a quality evaluation | S2/S3, I-4 |
| CR-15 | Model-only AWS billing is being described as total study reconciliation | Separate model usage, tool/search spend, reservations, uncertain calls, cloud billing lag and non-provider infrastructure charges; preserve the current AC-15 tolerance unless owner changes it | S2/S3, AC-15 |

## 3. Independent source checks

The following were opened directly at `8671f244`, rather than accepted solely
from the model-made traces:

- `packages/aia_core/src/aia_core/application/research.py:716–745`:
  confirmation compares a cost ceiling with the spend threshold and accepts a
  sufficient human confirmation; it is not the budget cap.
- `apps/executors/src/aia_executors/ai_fieldwork.py:283–326`: respondent answers
  and call receipts are accumulated in memory while iteration begins at the
  first respondent. This substantiates the need to trace partial-fieldwork recovery.
- `packages/aia_core/src/aia_core/application/research.py:865–895`:
  **analysis-only retry explicitly reuses the frozen dataset**. A claim that all
  retries or all later step failures necessarily recollect fieldwork is too broad.
- `packages/aia_core/src/aia_core/domain/fieldwork.py:172–181`:
  `FieldworkRespondent` has id, donor, weight and answers, not descriptors.
- `packages/aia_core/src/aia_core/domain/analysis/draft.py:254–282`:
  the cited gate checks dangling references and uncovered numbers; this code
  does not require a nonempty admitted-claim list for every key finding.
- `packages/aia_core/src/aia_core/application/report_variants.py:77–79`:
  client report is excluded from `RENDERABLE_REPORTS`.
- `infra/develop/versions.tf:34–40`: provider default tags already include
  `Environment=develop`; the statement “no Environment tag” is wrong.
- `apps/executors/src/aia_executors/ai_runtime.py:251–275`: model validators
  expect `eu.` profile identifiers. The tagged application-profile plan must
  account for this. Consider separating semantic pinned-model identity from the
  invocation target, rather than accepting arbitrary ARNs as model identity.

These are source observations. No live AWS configuration or paid provider call
was inspected or executed by this review.

## 4. Minimum acceptance obligations

| AC | Required proof beyond a checkbox |
|---|---|
| 01 | Both researchers authenticate; every scope path denies another organization/client as specified; Lead turns stay private and admin file access is bounded |
| 02 | All eleven artifacts in browser; no orphaned AI action when buttons disappear; hand/Lead edits share server validation; partial acceptance and item conflicts; protected map lock; bounded results context |
| 03 | All eleven worker contracts complete; eight analysis prompt pins; prompt changes affect new jobs only; read-only method prompt slots refuse mutation |
| 04 | Ceiling displayed; budget/envelope holds atomic under concurrent starts; threshold confirmation remains separate; unused hold released and uncertain charges retained |
| 05 | Actual LIVE population/weight binding reaches fieldwork; requested descriptors and own dimensions reach their intended consumers; missing inputs refuse honestly |
| 06 | Kill after a billed respondent/block, restart and show no duplicate paid replay; uncertain in-flight call requires recovery; completed analysis retry reuses fieldwork |
| 07 | Change exactly one questionnaire item after a run; only impacted stages reopen; report wording changes draft only; old approval becomes invalid |
| 08 | Every key finding has admitted support or explicit refusal/no-finding status; Results receives admitted claims; QC is a warning and cannot silently admit excluded data |
| 09 | Object/respondent/segment maps use the pinned method; support and placement failures explicit; view filtering/drag does not mutate numerical artifacts; drill-down never exports |
| 10 | Document/dataset/public source → reviewed knowledge → frozen study context; child dimension actually consumed; accepted client contract, personal-column removal and separate CLIENT_REPORTED claims |
| 11 | OPEN edited design → Brave, probes and captured sources; CLASSIFIED existing whole-run refusal; retry/mid-run posture tests; DESIGN and INTERPRETATION/report-context paths both budgeted; sources dataset and knowledge admission |
| 12 | Same-client reuse keeps lineage and labels; another client's design is absent |
| 13 | Internal/client DOCX and PDF; report/snapshot approvals separate; both self-approval settings; unauthorized or stale-version download refuses; source-use and evidence gate contract tested |
| 14 | Malformed config refuses start; activation profile describes effective worker composition without a paid smoke call |
| 15 | Trace every number and external quote; reconcile model and tool/search cost separately; pin models/prompts/data/contract; record billing delay/tolerance without calling unknown zero |

The negative prototype cases for missing evidence and methodology refusal remain
release tests of invariants even if richer conversational flows are post-MVP.
Unknown capabilities must be visibly unavailable, never fixture-backed product data.

## 5. Decisions: settled versus genuinely open

Do not ask the owner to reapprove per-researcher Leads (F12/Q26), OPEN posture
(#500), respondent replacement as a new linked run (F18), report wording worker
(MVP-12), per-stage structural auto-accept (MVP-14/D18), separate approval policy
(F17), or direct human chat start (Q25). A different choice is a **scope override**
and must be presented as such with impact.

The remaining decision packet should distinguish:

| Topic | Concrete question | Recommendation / affected work |
|---|---|---|
| Prototype precedence | Use the attached V2 build for interaction/detail and V3 for the eleven artifact bodies where compatible? | Yes; list explicit deltas, preserve newer recorded decisions, never let old mock copy overwrite methodology |
| New prototype scope | Are tracked assumptions and open-answer coding required for first release? | Assumptions only if a small explicit design-item contract is accepted; coding is a separate methodology feature, not implied by showing open answers |
| Segment meaning | Which approved stored descriptor fields and combinations define default segments? How do approved own dimensions participate? | Start from eligible existing sampler descriptors; method owner defines support, clustering, parameters and register entries |
| Empty analysis module | May a module produce a structured “no supported finding, reason” result that lets the report proceed? | Yes, with no invented finding; never convert it into admitted evidence |
| Client dataset policy | Is the accepted data contract the evidence-policy source? Resolve ADR 0027 benchmark interval, grounding prohibition/permission and label decisions | Owner/methodologist decision before dependent evidence code; current population field list is not a blanket fit for client datasets |
| Deep Research reach/evaluation | Is Common Crawl required for I-R, or explicitly deferred with a revised exit? Which measured quality criteria must pass before final activation? | Keep existing I-R until owner changes it; allow W0 smoke without archive but report gate BLOCKED; separate evaluation allowance from the USD25 study |
| Deletion semantics | What is the operational deletion horizon including backups/versions and how are deleted subjects kept deleted after restore? | Document the approved horizons and a deletion journal/replay mechanism; do not invent 14/30-day approval from existing infrastructure defaults |
| Paid work outside a study | May client-level source extraction remain in Client Knowledge under client budget, while all study-stage AI actions use the Lead? | Make the scope explicit; retain client isolation, approval and budgeting; do not force a fake study or allow an unbounded alternate path |

Operator confirmations (hostname, callbacks, sizing, quota, model tiers, provider
terms and retention evidence) are a separate checklist. They are not methodology
choices and must not be portrayed as already performed.

## 6. Conditions for calling the plan ready for implementation

1. Every approved MVP AC maps to an owning plan, real chunk, predecessor,
   producer/consumer contract, test and evidence location.
2. Every gap/interface row maps to a child chunk; no row is closed merely because
   it has a destination plan name.
3. Master/wave/child-plan references and dispositions are checked mechanically;
   counts come from front matter, including post-MVP/support distinctions.
4. Settled decisions agree in acceptance MD, machine criteria, roadmap, wave
   tables and child plans; historical analyses have a supersession banner.
5. The question packet contains only unresolved choices or explicitly labelled
   scope overrides, with blocked chunks named.
6. ADRs awaiting owner decisions stay Proposed; implementation checkboxes stay
   open. Built, configured and observed live remain distinct states.
7. Q1-2027 is accompanied by capacity/effort and dependency risk, not an invented
   calendar forecast. A deferred decision cannot be treated as approval.
