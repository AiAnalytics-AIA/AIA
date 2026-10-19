# Trace 4: the Research Lead, orchestration and governance

Cohesion audit, read-only. Repository `/home/user/AIA`, branch `chore/mvp-master-plan`, SHA `f7e80bb9`
(every anchor is `file:line @ f7e80bb9`). Group: capabilities 1-9 of the brief.

**Path prefixes.** `C` = `packages/aia_core/src/aia_core`, `API` = `apps/api/src/aia_api`,
`EX` = `apps/executors/src/aia_executors`, `WEB` = `apps/web/src`.

**Status words.** EXISTS (I opened the lines), PARTIAL, MISSING (with the plan and chunk that should build it,
or NONE), CONTRADICTION (both sides quoted). **◇** = hypothesis (I did not open it, or it is operator state I
cannot see from the repository).

**What I could not verify.** (a) What develop's SSM parameters are today: the repository only says the route is
Class C until an operator acts (`deploy/develop/README.md:412-420`), so "develop refuses every AI call right now"
is ◇ for the live host and EXISTS for the code path. (b) I did not run any test or reproduction; every claim is
from reading. (c) I read `LeadPane.tsx` only at the reason map and the web store only at its save call.

**Plan-side facts that frame everything.** `grep` for `researcher_lead_signals`, `study_envelopes`, `lead_plans`,
`workspace_edit_ops`, `proposal_change_decisions`, `LeadWorkerSpec`, `ResultsContext` over `.planning/plans/` and
`docs/architecture/` returns nothing. They exist only in `.planning/mvp-target-architecture.md`,
`mvp-development-plan.md` and `mvp-cohesion.md`. `.planning/plans/research-lead-workbench.md` (25 chunks, 15 open)
has no chunk for any of them. The development plan says so itself (`mvp-development-plan.md:119-121`: "**New** means
the chunk is added to that plan before the wave starts"; `:252-254`: "does not change a plan file"). So every row below
marked "MISSING (dev plan W1 New)" has a wave and an owner in the dev plan and **no chunk in any plan file**, which
`CLAUDE.md` §4 treats as a hypothesis, not a plan.

---

## 1. A Lead turn: context freeze, closed output, repair, grounded edits, the 96 KB bound

**Verdict.** The turn itself is built, tested and well-guarded (closed output, number guard, grounding, stale rule,
ledger). What is thin is *what the Lead is shown*: the frozen context holds 8 layers and none of the layers ADR 0026
decision 2 promised for results, readiness, change-since or a stage contract; the accept path never writes a Design
Revision; and an approval card is not bound to the revision it was prepared on.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Web posts a turn (greeting or message, stage, focus) | EXISTS | `API/routers/lead.py:372-399`; the pane is `WEB/components/workbench/LeadPane.tsx` ◇ (only the reason map at `:36-48` opened) |
| Application `post`: needs EDIT_STUDY + RUN_WORKFLOW + open study, locks the researcher's Lead row, busy check, 8 h greeting window | EXISTS | `C/application/research_lead.py:385-500` |
| Context frozen at enqueue: fixed order, canonical JSON, hashed, stored as step input | EXISTS | `C/domain/research_lead.py:782-827`; `C/application/research_lead.py:442-487` |
| The layers (prompt, lead, knowledge, study, design, runs, view, conversation) | PARTIAL | `C/domain/research_lead.py:803-818`. ADR 0026 decision 2 also promises readiness and question outlook, results ("only on the result stages"), the stage contract, a rolling summary and "what changed since the Lead last answered" (`docs/architecture/adr/0026-research-lead-proposes-a-person-decides.md` decision 2). None is in `freeze_context`. |
| `runs` layer | PARTIAL | `C/application/research_lead.py:851-889`: id, status, design revision id of the newest 5 `research` runs only. Agent jobs, Deep Research, Interpretation, materialization are not shown. |
| 96 KB bound, oldest turns dropped first, then refused by name | EXISTS | `C/domain/research_lead.py:116, 800-827` (`LeadContextTooLarge`); API 422 `API/routers/lead.py:337-338` |
| The bound protects other layers | PARTIAL | Only the conversation is droppable. Knowledge is capped at 20 KB (`C/domain/research_agents.py:545-562`), notes at 16 KB (`research_lead.py:129`); the design is not capped, so a big design is refused whole, and any new layer (results, ops feed, signals) has no drop priority. Plan: results layer is the dev plan's "New" chunk before `research-lead-workbench` 20 (no chunk in the file). |
| Mismatch between the Lead's bound and the agents' | CONTRADICTION | The Lead accepts a context to 96 KB (`research_lead.py:116`); the design jobs it prepares refuse over 64 KB: `C/domain/research_agents.py:582` "Research agent context exceeds 64 KB". The Lead's approve route has no `ValueError` arm (`API/routers/lead.py:284-345`, only `LeadRejected`, `DesignRejected`, `WorkspaceRejected`), while the manual route maps it to 422 (`API/routers/research.py:2727-2730`), so a 64-96 KB design that the Lead can discuss gives a 500 on approval ◇ (code-read, not executed). |
| Closed `LeadOutput` | EXISTS | `C/domain/research_lead.py:412-422`: reply, view ≤3, edits ≤12, one request, follow ≤3, self_update; `extra="forbid"` |
| Number guard (reply may write only numbers in the context or prompt; exponents refused) | EXISTS | `C/domain/research_lead.py:435-498` |
| One schema repair | EXISTS | `C/domain/research_lead.py:996` (`schema_repair_attempts=1`); a failed repair parks as a permanent failure and the pane says only "Vedoucí se zastavil (code)" (`LeadPane.tsx:46`) |
| Worker step, preflight before any spend, scripted fallback for the workbench | EXISTS | `EX/research_lead.py:150-226, 230-349` |
| Edits grounded against the working content (unknown question, section, item dropped and named) | EXISTS | `C/domain/research_lead.py:548-592`; called at `EX/research_lead.py:281-284` |
| Edit vocabulary (8 ops: set_text, list_add/replace/remove, question_add/edit/remove, set_n) | EXISTS | `C/domain/research_lead.py:299-309` |
| Planned shared vocabulary (move, merge, section, set, route, scale, comparison) and `domain/edit_ops.py` | MISSING | file does not exist (`Glob`); NONE in plan files; dev plan W0 "contract" and W1 "New" (`mvp-development-plan.md:136, 210`) |
| Edits accepted on the server: EDIT_STUDY + APPROVE_GATE, stale base refused whole, one transaction, ledger row per edit | EXISTS | `C/application/research_lead.py:504-618`; ledger `C/infrastructure/workflow_repository.py:2556` |
| Accept also writes a Design Revision | CONTRADICTION | `decide_edits` saves the working copy only (`research_lead.py:592-601`: `workspace.save(... reason="lead_edit_accepted")`, no `designs.submit`). The agent-job accept does both (`C/application/proposal_accept.py:142-156`). The target architecture's test "after any accept the head's content equals the working copy's" (`mvp-target-architecture.md:179-183`) would fail for today's Lead accept. |
| Automatic accept of text edits only; refused whole if the turn is stale | EXISTS | `C/domain/research_lead.py:314-346`; `C/application/research_lead.py:541-566` |
| Per-stage automatic accept of structural edits (workbench plan D18, overview MVP-14) | CONTRADICTION | `research-lead-workbench.md:141-144` D18 and `overview.md:585` MVP-14 allow it; `mvp-cohesion.md:359-360` ("The automatic accept stays the Lead's, text edits only (MVP-14, ADR 0026)") and `mvp-target-architecture.md:98-101` ("text-only operations are the only ones an automatic accept may take") forbid it. |
| Lead edits visible to and acceptable by a second researcher | MISSING | `decide_edits` takes only the caller's own turn (`research_lead.py:550`, `StudyLeadRepository` filters by `actor_id`, `C/infrastructure/study_lead_repository.py:3-6`). Cohesion F12.5 "any member with APPROVE_GATE may accept" is built only for agent-job proposals. NONE. |
| Approval card bound to what was shown | CONTRADICTION | ADR 0026 decision 3 "the Design Revision it is asked on"; code: `AgentJobRequest` has only `action` and `why` (`research_lead.py:352-357`), `RequestApproval` only `confirm_cost_usd` (`API/routers/lead.py:100-105`), and `approve_request` submits whatever the working copy is *at approval time* and starts the job on it (`C/application/research_lead.py:736-746`). `decide_edits` by contrast requires `base_revision` (`lead.py:86-97`). Plan `lead_plan` would bind revisions (`mvp-target-architecture.md:144-146`) but the existing single card is not covered. |
| Result returns to the screen and the next turn | PARTIAL | The conversation reads the step output (`research_lead.py:295-311`); web reload after accept ◇ not opened. The Lead's next turn sees the new working copy but not what changed or who changed it (no ops feed). |
| Hard lock on Set 1 and the Sociomap rating question | MISSING | `apply_edit` has no lock; a Lead `question_remove` can remove a declared rating question (`research_lead.py:1294-1316`). Dev plan: part of `edit_ops` (S1, W0 contract, W1). |

---

## 2. Personal Leads: hatching, SOUL and USER, notes, proposed updates, signals, admin read, handover

**Verdict.** Hatching, files, notes, revisions, client isolation of notes and "waits for the researcher's yes" are
built. Everything that makes the Lead *develop* or be *administered* (signals, review, admin read, handover, rollback)
is design-only and none of it is in a plan file. One stored feature (revisions) has no reader.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Hatch once, defaults, no body | EXISTS | `API/routers/lead.py:476-486`; `C/infrastructure/researcher_lead_repository.py:214` |
| SOUL, USER ≤ 2000 chars, name ≤ 40, DB checks | EXISTS | `C/infrastructure/tables.py:821-858`; `C/domain/research_lead.py:123-126` |
| Notes ≤ 300 chars, personal or client, forgotten by flag, client note loaded only into that client's study by the query | EXISTS | `C/infrastructure/tables.py:897-940`; `researcher_lead_repository.py:152-176` |
| Lead changes its own files only through `self_update`; what reaches every client waits for a yes, what stays in the client applies | EXISTS | `C/domain/research_lead.py:617-646`; `EX/research_lead.py:285-306`; `C/application/research_lead.py:620-676` |
| Class of the files (C personal, A client notes) | EXISTS | `C/domain/research_lead.py:853-873`; `C/domain/material_rules.py:85-86` |
| "No client name or number in a personal file" as a rule with a test | PARTIAL | enforced by prompt (`research_lead.py:724-725`) and by the researcher's yes (`split_self_update`), not by code; the planned test (`mvp-target-architecture.md:197-199`) is MISSING, NONE in plan files |
| Proposed updates ("Remember this" after a correction, periodic review) | PARTIAL | The prompt already lets the Lead change files "when their lasting preference is obvious" (`research_lead.py:718-719`) while the domain docstring says "only ... when the researcher asks" (`:18-21`): CONTRADICTION between docstring and prompt. The card (`self_update_pending`) exists; the *trigger* (signals, review due) does not. |
| `researcher_lead_signals` table, kinds, synchronous writes, "due" rule | MISSING | no table (grep); dev plan M7, W2, S1 (`mvp-development-plan.md:198`); ADR "The Lead over time and its files" is a to-do (`:223`); NONE in plan files |
| Signal producers | MISSING | "undid_lead_edit" needs an undo that needs the ops log (M1); "rejected_lead_proposal" could be written from `decide_edits dismiss` today but no code does. `repeated_instruction` has no detector and no owner. |
| Lead sees unconsumed signals | MISSING | no layer in `freeze_context`; adding one is a context change that must bump `LEAD_HARNESS_VERSION` (`research_lead.py:111`, checked at `EX/research_lead.py:236`); not stated anywhere |
| Revisions of each file change kept | EXISTS | `C/infrastructure/tables.py:861-894`; written in `apply_self_update` (`researcher_lead_repository.py:283`) |
| Revisions readable or revertible | MISSING | `ResearcherLeadRepository.revisions()` has **no caller** (`grep "\.revisions()"` finds none outside tests); no route exposes it; the Lead is not shown revisions (its `lead` layer is name, soul, user, notes). F14 says "every change is a revision that can be rolled back" (`mvp-cohesion.md:471-472`); NONE. |
| Turns private per researcher | EXISTS | `C/infrastructure/study_lead_repository.py:3-6`; `C/infrastructure/tables.py:808` unique (study, user, sequence) |
| Admin read of files and notes | MISSING | The repository states the opposite invariant: "always works on the calling researcher's Lead ... never an argument" (`researcher_lead_repository.py:3-6`) and `layer_check` guards the tables (`tools/layer_check.sh:458-462`). Needs a deliberate second access path, `LEAD_FILES_READ` in `access_audit` (free-text `action`, `tables.py:607`, so no migration), an ADR amending decision 8. Dev plan W2 M7; NONE in plan files. |
| Handover: copy with personal notes removed, original archived | MISSING | no `archived_at`, no `derived_from_lead_id`. Not decided: the **USER file** (what the Lead knows of how *this person* works, `research_lead.py:19-20`) and SOUL are also personal to the departed researcher; the rule only says "personal notes removed" (`mvp-target-architecture.md:200-203`). And what triggers it (user deactivation exists in `ScopeResolver._active_user`, `C/application/scope.py:107`, but nothing links it to Leads) ◇. |
| Routes `GET /admin/leads/{user_id}`, `POST .../handover` | MISSING | would be the first routes in `routers/lead.py` that name a user id, against its docstring "No route takes a client, organization or user id" (`API/routers/lead.py:15`) |
| Preference `auto_accept_text_edits` | EXISTS | `API/routers/lead.py:489-505`; `C/infrastructure/tables.py:841-843` |

---

## 3. Command registry and the workers the Lead may call (prompt pin, price, `approve_request`)

**Verdict.** Eight design workers exist, each with a pinned prompt; one path (agent job) is approvable through the
Lead. The *registry*, the *price per worker*, the *three new workers* and the "human-only" enforcement are not built.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Typed request in the Lead's output (agent_job, research_run, design_research, interpretation_research) | EXISTS | `C/domain/research_lead.py:352-378` |
| Only `agent_job` starts anything; the other three "only open a stage" | EXISTS | `C/application/research_lead.py:705-707` (`NotAPaidRequest`) |
| Command registry `application/lead_commands.py` | MISSING | file absent; ADR 0026 decision 4; `research-lead-workbench` chunk 11 (open) |
| `403 human_gate_required` for human-only commands | MISSING | string appears only in the ADR (`0026...md:177`); no code |
| Eight existing workers | EXISTS | `C/domain/research_agents.py:37-44` |
| Each worker's prompt pinned at enqueue, editable | EXISTS | `C/application/research.py:1311+` (`_pin`); slots `C/domain/prompt_slots.py:95-110` |
| Price per worker | MISSING | one worker reservation for all actions: `AIA_AI_RESEARCH_RESERVATION_USD` (`EX/ai_runtime.py` settings; API mirror `API/config.py:123-126`, used by `API/routers/lead.py:461`). Chunk 11 text says "each with its prompt and price" (`research-lead-workbench.md:15`); no per-action key or API mirror is designed. The API mirrors each key by hand, so N workers means N keys in two processes. Dev plan: "worker row" W0 (`mvp-development-plan.md:127`, `mvp-cohesion.md:216-221`), no chunk text. |
| One worker row (`LeadWorkerSpec`) read by Settings | MISSING | Settings still lists activities by hand (`API/routers/settings.py:459-529`); the spec is first deliverable of chunk 11 per `mvp-cohesion.md:223-225`, not in the chunk text |
| Three new workers (`interpret_map`, `polish_report`, `flag_straightliners`) | MISSING | dev plan W3 S1; MVP-12. They do not fit the agent-job shape: the job input is a Design Revision snapshot (`research.py:1338-1343`), the outputs are design items merged by `accept_into_working_copy`; `ResearchAction` is a closed enum of 8 used in 25 places; capability `REPORT_WRITING` has **no consumer or binding** (`C/domain/ai_models.py:78`; worker binds only SIMULATION, RESEARCH_LEAD, RESEARCH_REASONING, STUDY_LEAD, CRITIC, FAST_EXTRACTION at `EX/ai_runtime.py:718-731`). Result kinds (unapproved interpretation, report wording, keep/replace flags) have no accept destination and no ledger subject. NONE in plan files. |
| `approve_request` holds the spend limit, writes the ledger, starts once | EXISTS | `C/application/research_lead.py:678-759`; ledger `workflow_repository.py:2627` |
| Manual route starts the same job with no spend-limit check | EXISTS (a defect) | `C/application/research.py:1311-1408` reads no `spend_confirm_usd`; `API/routers/research.py:2735-2754`. Cohesion F5 "a fix, not a decision" (`mvp-cohesion.md:212-225`), dev plan W0; but `.planning/open-items.md` OI-127 says "Open: ... the product owner's call" and plan F1 says "observation, not yet a defect" (`research-lead-workbench.md:179-186`). CONTRADICTION across three documents; no plan chunk. |
| "Every AI action through the Lead" (AC-02, MVP-8) | CONTRADICTION | AC-02 (`docs/migration/mvp-acceptance.md:77`) vs ADR 0026 decision 4 and code: a research run, Design Research, Interpretation, fieldwork, analysis retry, materialization and the *client-level* "Navrhnout znalosti" (`client_source_proposals`, no study to scope a Lead to) keep their own starts. Only the envelope/plan/`chat_start` design (not built) could cover runs; client-level AI has no Lead at all. |

---

## 4. The approval ledger and its subject types

**Verdict.** Ten subject types exist; seven are planned in one migration (M3). The list is complete for the new
human acts but three acts are recorded in other stores without saying so, and the map snapshot has two writers.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Table and the allowed subject types: gate, artifact, budget, spend, ai_proposal, design_research, answerability, lead_edit, lead_job_request, lead_self_update | EXISTS | `C/infrastructure/tables.py:1708-1713` |
| Migrations that extended it | EXISTS | `migrations/versions/20261019_7b3c32892aa9_research_lead.py` and five earlier |
| Planned seven new types in one migration (envelope, lead_plan, plan_step, chat_start, data_contract, map_snapshot, sociomap_unlock) | MISSING | dev plan M3, S3, W0 first (`mvp-development-plan.md:192`); no plan chunk; the chunk must also add repository writers and `layer_check` rules |
| `subject_id` size fits the new subjects | EXISTS | `String(64)` (`tables.py:1664`) |
| Who writes ledger rows | PARTIAL | all in `workflow_repository.py` (`:2318, 2414, 2492, 2556, 2627, 2685`) plus `artifact_repository.py:568`; the dev plan's surface table (`:107-111`) names no owner for `workflow_repository.py`, which S1 (plans, chat_start), S2 (runs) and S3 (data_contract, report) would all edit |
| Map snapshot approval | CONTRADICTION | `mvp-target-architecture.md:230-232` "approved through the existing artifact approval" (that writes `subject_type="artifact"`, `artifact_repository.py:568`) **and** `:224` adds ledger subject `map_snapshot`. Two ledger shapes for one act. |
| Client posture change (`data_posture`) | MISSING | M10 says "audited by who and when" (`mvp-development-plan.md:201`) but names neither a ledger subject nor an `access_audit` action; not in M3 |
| Client envelope ceiling set by admin | MISSING | subject `envelope` is the study's; the client ceiling's audit is unnamed |
| Plan step ledger rows record the right person | PARTIAL | `execution_context` attributes work to `run.triggered_by` (`C/application/scope.py:355`); a `plan_step` row would name the person who approved the plan as actor, which is intended (`mvp-target-architecture.md:153-155`), but producer/approver independence for a row nobody clicked has no stated rule |

---

## 5. Spend limit, client budget, per-study envelope, plan card, plan authority

**Verdict.** The designs conflate three different money concepts, and the "plan authority" is described as safe
because it holds no `APPROVE_GATE`, which does not protect the thing it needs protecting.

What exists (all anchored): the study **budget** `budget_usd` is the cumulative cap, held by reservations under a
study-row lock and parking `AWAITING_BUDGET` (`C/infrastructure/workflow_repository.py:1217-1260`); the study
**spend limit** `spend_confirm_usd` is only "the limit above which starting a run asks for confirmation"
(`C/application/research.py:452-454`; `C/domain/scope.py:562-566`); the **client budget** pays the client's *own*
AI work and "never ... its studies" (`C/domain/scope.py:563-572`).

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Spend limit applied at run start (ceiling ≥ limit needs confirmation, unknown ceiling refused, recorded) | EXISTS | `C/application/research.py:724-742` |
| Applied at Lead-prepared job approval | EXISTS | `C/application/research_lead.py:720-734` |
| Applied at manual agent-job start | MISSING | see §3 (dev plan W0 "fix"; OI-127 still open) |
| Applied to Deep Research start | ◇ | `C/application/deep_research.py` not opened; ADR 0019 gate 2 claims it |
| Spend limit is "the hard stop for everything" | CONTRADICTION | `mvp-target-architecture.md:134` ("stays the hard stop for everything") and header meter "spent of spend limit" (`mvp-cohesion.md:497-498`) vs `research.py:452-454` (a per-start confirmation threshold; null means never asks) and the real cap `budget_usd` (`workflow_repository.py:1240`). An envelope "capped at the study's spend limit when no client ceiling is set" (`mvp-target-architecture.md:132-133`) therefore has no defined meaning when the limit is null (the default). |
| Meter semantics | CONTRADICTION | F16's "client's budget ... in a details drawer" (`mvp-cohesion.md:500-501`) would show `clients.budget_usd`, which pays only client-level work (`scope.py:563-572`), beside a study's spend: unrelated numbers under one heading. |
| Client budget (CB1-CB4) | EXISTS | `client-budget.md` front-matter; CB5 (end-to-end proof) open, plan `client-budget` CB5 |
| Envelope tables (`study_envelopes`, `_raises`, `_charges`), `clients.envelope_ceiling_usd` | MISSING | dev plan M4, S1 (ceiling column S3), W1; no plan chunk; no `layer_check` rule yet |
| Envelope accounting "under the study row lock like a spend confirmation" | CONTRADICTION | `ResearchRuns.start` takes **no** study lock (`research.py:479-760`; the only `lock()` in that file is `dismiss`, `:1498`). The existing confirmation is a stateless per-start comparison; a cumulative envelope needs a new serialisation (the reservation path's lock, `workflow_repository.py:1217-1230`, is the model). |
| What counts against the envelope | PARTIAL | `study_envelope_charges` keys on `run_id` of `workflow_runs` and a ceiling; Lead turns (also `workflow_runs`, type `research_lead`) and priced Deep Research tool holds are not charged, yet cohesion F16 says "Lead turns and workers all count toward the study's spend". Stated for `spent`, not for envelope. |
| Plan card tables and workflow type `lead_plan` | MISSING | dev plan M5, S1, W1; `WORKFLOW_TYPES` is a closed set (`C/domain/workflow_templates.py:88`) so a new type also edits S2's template file; no chunk |
| Plan steps run sequentially over one frozen revision | CONTRADICTION | `mvp-target-architecture.md:139-146`: steps are `agent_job`, `research_run`, ..., "frozen at proposal", and "if the working copy or head revision moves, the plan is STOPPED". An `agent_job` step's proposal, once accepted by a person, moves both (`C/application/proposal_accept.py:130-156`), which stops the plan before the next step. Either a plan may not contain an accept between steps (then "Brief to Sample worked through the Lead" cannot be one card) or the stale rule needs an exception. Not addressed. |
| Plan authority "holds no APPROVE_GATE" as the safety property | CONTRADICTION | A worker context already lacks `APPROVE_GATE` but holds EDIT_STUDY and RUN_WORKFLOW (`C/domain/scope.py:202-213`), and `ResearchRuns.start` needs only RUN_WORKFLOW (`research.py` start preamble), `ResearchAgentJobs.start` only EDIT_STUDY + RUN_WORKFLOW (`:1311-1330`). Gate 2 (spend confirmation) is **a function argument** `confirm_cost_usd` (`research.py:724-742`), not a permission: any caller with RUN_WORKFLOW can pass any value. The ADR/plan promise "a spend confirmation ... parks" (`mvp-target-architecture.md:154-157`) is therefore enforced by nothing but the executor's own code. Needs a typed start API for the plan executor with no `confirm_cost_usd`, plus a `layer_check`/import rule that the executor cannot reach the full `start`. NONE. |
| Plan authority issued only by `ScopeResolver` against a lease and an APPROVED plan | MISSING | pattern exists (`C/application/scope.py:289-371`: lease-held issue, actor = `triggered_by`); a second issuer for plans is new code, S1 "with S3's ledger" (`mvp-development-plan.md:213`); no chunk |
| Typed `start_run` command (by-request start) | MISSING | `mvp-target-architecture.md:159-169`, route `POST lead/commands` marked ◇; also needs the web composer's quick action (S1) |
| Kill switch `AIA_LEAD_PLANS_ENABLED` | MISSING | named in plan; not in `config.py`, compose or README |

---

## 6. The continuation turn: a finished step returning typed results to the Lead

**Verdict.** Not designed anywhere. This is the biggest *absent* link in the group.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| A turn is always started by a person | EXISTS (a constraint) | `post` takes `kind in ('message','greeting')` and requires a person for a message (`C/application/research_lead.py:763-790`); table checks `actor in ('person','lead')`, `kind in ('message','greeting')` (`tables.py:801-802`); the Lead's turn is paid by a person's message (ADR 0026 decision 7 last paragraph) |
| A system-initiated turn ("step finished, here is what happened") | MISSING | no kind, no trigger, no plan. `mvp-target-architecture.md:389-392` ends the plan sequence at "the plan is DONE" without a turn. NONE. |
| A finished step's typed result visible to the Lead | MISSING | the Lead sees run id and status only (`research_lead.py:882-889`); `ResultsContext` is "a contract before W2" (`mvp-development-plan.md:158-159, 214`), no chunk, no owner file |
| The Lead reading more than its context (D19 "a read tool the Lead names an artifact with") | CONTRADICTION | `research-lead-workbench.md:145-151` vs ADR 0026 decision 3 "The Lead calls no tool, reads no table" and "Not decided here: ... Any Lead tool use". `LeadOutput` has no field for it (`research_lead.py:412-422`). |
| How a plan's step outcome reaches the card | MISSING | `lead_plan_steps.status` is planned (`mvp-target-architecture.md:140-142`); the web's follow of it and the Lead's awareness are unstated |
| A parked step gets resumed and the Lead told | PARTIAL | `resume_runtime_parks` lets a person resume a park for a worker-class refusal (`C/application/research.py:293-314`); Lead turns parked this way have no resume (the person re-sends, creating another turn; `_holds` deliberately ignores such parks, `research_lead.py:224-232`) |

---

## 7. Model gateway, policy, tiers, and the AI route classes

### 7.1 The chain

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Only path to a model is `GovernedModelGateway`; preflight runs the same checks as invoke and stops | EXISTS | `C/application/model_gateway.py:214-242, 340-374` |
| Egress order: scope issued, class not None, route exists, **class in route.approved_for**, EU confirmed for A and B, training exclusion, **bounded retention** | EXISTS | `C/domain/residency.py:177-262` (class refusal at `:228-232`; retention at `:251-255`) |
| Gateway names refusals `egress_<reason>` and `licence_<reason>` | EXISTS | `model_gateway.py:347-349, 374` |
| Route configured from env: `AIA_AI_ROUTE_APPROVED_FOR`, `_RETENTION_DAYS`, `_EU_PROCESSING_APPROVED`, `_EXCLUDED_FROM_TRAINING` | EXISTS | `EX/ai_runtime.py:505-600`, route built at `:769-779`; compose passes them to the worker only (`deploy/develop/docker-compose.yml:224-227`) and **`APPROVED_FOR` alone** to the web (`:106`) |
| Model policy binds capabilities to the one route model, plus the light and Lead models as second entries on the same route | EXISTS | `EX/ai_runtime.py:690-767` |
| Licence gate for panel-derived lineage: route id must be `bedrock-eu-primary` | EXISTS | `C/domain/licence_determinations.py:44, 55-82` |
| Production route id and class approval | MISSING | ADR 0010's amendment is "develop's EU route" only (`docs/architecture/adr/0010...md:158-166`); `mvp-development-plan.md:138` (production applied in W1) names neither the production route class decision, its retention evidence, nor that its `AIA_AI_ROUTE_ID` must equal `bedrock-eu-primary` or every panel-derived call is refused by the licence gate ◇ (the production env is unbuilt). NONE. |
| Models tiered by role, pinned, "shown in Settings" | MISSING | Settings and `/config` carry only the route model (`WEB/app/config/route.ts:25-26`); the Lead's and light model ids, prices and tiers appear nowhere in the settings document (`API/routers/settings.py:449-540`); `develop-spend-attribution` and `mvp-target-architecture.md:337-352` give no Settings producer. NONE. |

### 7.2 Which material gets which class, per worker kind

All classes are minimums; an operator's exact-bytes classification can only raise them
(`C/domain/material_rules.py:79-91, 124-141`). Any approved Client Knowledge item makes the whole request **A**
(`rule:knowledge`, `material_rules.py:87`; `research_agents.py:660-669`; `research_lead.py:939-947`).

| Worker kind (step kind) | Parts and their class | Minimum route approval | Anchor |
|---|---|---|---|
| Lead turn (`research_lead_turn`), including the greeting | design B, study and client names B, message and focus label B, earlier messages B, Lead name/SOUL/USER/personal notes C, client notes A, approved knowledge A, prompt C (baseline) or declared/operator, earlier replies carry their turn's class | **B** with no knowledge and no client note, otherwise **A** | `C/domain/research_lead.py:876-948` |
| Design jobs (`research_agent`, 8 actions) | design B, non-empty instruction B, prompt as above, knowledge A | **B**; **A** with any approved knowledge | `C/domain/research_agents.py:640-690` |
| Fieldwork (`research_fieldwork`, ai_runtime) | design B; roster personas C; **panel personas A** (not fictional) + panel lineage, so also the licence gate | roster run **B**; panel run **A** | `EX/ai_fieldwork.py:418-432`; `C/domain/ai_respondent.py:311-327` |
| Analysis modules (`research_analysis`) | design B; dataset C only if origin is simulated and respondents fictional, else A | roster run **B**; modelled/panel run **A** | `EX/analysis.py:581-590`; `C/domain/analysis/harness.py:192-203` |
| Client source proposals (`client_source_proposals`) | client source A, or C if marked "Interní dokument"; raised by operator | **A** (C if marked) | `EX/client_source_proposals.py:208-262` |
| Deep Research (six kinds) | design: **operator's exact-bytes record only** (rule not applied); none = park `egress_unclassified_material`; search routes are Class C only, so a B/A design's queries are refused by every composed route | model route B/A as the operator classified; search C only | `EX/deep_research/plan.py:159-174`; OI-129 |
| Report, QC, population materialize, PDF | no model call (report composed from admitted modules) | none | `CLAUDE.md` map; `REPORT_WRITING` has no consumer |

**Consequence.** On the MVP's own path (population-built respondents, analysis of their modelled results, the Lead)
**every worker needs Class A except a roster-only run**; there is no study-material worker that works on a Class-C-only
route. `docs/migration/mvp-acceptance.md:52` and the dev plan are right that the operator step is first, but
`mvp-development-plan.md:77-79` ("any design job whose study has approved knowledge (Class A by rule) parks") understates
it: with the route at C, *every* design job, Lead turn and run parks, with or without knowledge (it is Class B then;
`deploy/develop/README.md:401-404` says so). The message the user sees names A or B depending on the study.

### 7.3 Every place the refusal can surface, and whether anyone is told how to fix it

The API never evaluates egress: its settings carry no route classes (`grep approved_for apps/api` finds none), so every
AI start is "enqueue, then park". Nothing before the click warns.

| Surface | What the person sees | Names who fixes it, or links? | Anchor |
|---|---|---|---|
| Design stage AI buttons (analyze, build, optimize, audience, dimensions, critique, copilot, memory) | Czech frame around the raw English exception: "AI návrh čeká na povolenou trasu nebo licenci: route bedrock-eu-primary is not approved for CLASS_A_CLIENT_CONFIDENTIAL"; shown as a thrown job error / notice | **No** | `EX/research_agents.py:239-248`; `WEB/lib/research-agent-jobs.ts:45-49`; `WEB/components/rehome/research/useResearchAgents.tsx:150-200` |
| Lead pane (greeting and every message) | `egress_route_not_approved_for_class` → "Tuto studii nelze poslat modelu: trasa AI není schválena pro třídu jejích dat." | **No.** Only the unclassified-material line says "Rozhoduje o tom správce AIA" (`LeadPane.tsx:39`), and that text is outdated: the owner's rule of 2026-10-19 closed that cause (OI-126). Retention, residency and training-exclusion refusals have **no** entry and fall to "Vedoucí se zastavil (egress_retention_unspecified)" | `WEB/components/workbench/LeadPane.tsx:36-48`; `EX/research_lead.py:187-196` |
| Client "Navrhnout znalosti" | reason list: "trasa k modelu není schválená pro důvěrné podklady klienta"; "u trasy k modelu není uvedena doba uchování dat" | No (and says "důvěrné podklady klienta" for the Lead-context B case it is not) | `WEB/i18n/cs.ts:466-467`; `EX/client_source_proposals.py:239-262` |
| Fieldwork and analysis steps (Progress, Results) | "Krok čeká: AI model pro něj není dostupný nebo povolený." and "Důvod je uvedený u kroku."; the code is shown through the generic coded-words fallback (no `egress_*` entry in `reason-words.ts` or `cs.ts` outside the two above) | No | `WEB/i18n/cs.ts:2717-2728`; `EX/analysis.py:383-405` |
| Deep Research | gap `POLICY_REFUSED`, coverage counts; `egress_unclassified_material` park | No | `EX/deep_research/plan.py:166-174`; coverage ledger |
| Draft prompt test dialog | "Úloha čeká na povolenou trasu, licenci nebo na zařazení textu promptu operátorem" | Names "operátor" only | `WEB/i18n/cs.ts:894` |
| Settings → AI | lists the approved classes, read-only, with "never verified" | It is where the fix is *shown*, not *made*; and it can say all three classes while the worker refuses `egress_retention_unspecified`, because `/config` carries `AIA_AI_ROUTE_APPROVED_FOR` alone, not retention, EU or training flags | `WEB/components/aia/settings/ControlPanel.tsx:612-621`; `WEB/app/config/route.ts:27-28`; `docker-compose.yml:106` |
| API | nothing (it never refuses on class) | n/a | `API/routers/lead.py`, `routers/research.py` |

**Does any message tell anyone how to fix it? No surface does.** The fix is operator work (confirm the Bedrock retention,
set four SSM parameters, `bin/write-env.sh`, restart: `deploy/develop/README.md:412-470`), not something an administrator
does on Nastavení. The dev plan promises a stage error that "says ... an administrator widens it on Nastavení → AI, and
link there (a small chunk in `research-lead-workbench`, with the Lead's command registry, chunk 11)"
(`mvp-development-plan.md:79-82`); chunk 11's text has no such item (`research-lead-workbench.md:15`), and **Settings → AI
cannot widen anything** (`API/routers/settings.py:572-583` is a read-only document; `CLAUDE.md` map "the read-only
settings document"): CONTRADICTION between the promised remedy and the product.

---

## 8. Settings as the administrator's place (AI runtime, Deep Research, methodology)

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Read-only `ai_runtime`: provider, credential, activities with capabilities, versions, switches | EXISTS | `API/routers/settings.py:449-540, 565-583` |
| Activities match the worker | CONTRADICTION | the list is six activities (`settings.py:529`) and derives `unused_capabilities` from it; the worker also binds `FAST_EXTRACTION` for client source proposals (`EX/ai_runtime.py:729-730`), so Settings reports that capability as *unused* while a deployed step uses it. A test holds the list to itself (`apps/api/tests/test_settings_api.py:418-423`), not to the worker's bindings. |
| Prompt slots for analysis, Deep Research, respondent listed read-only as "not run by any composition" | CONTRADICTION | `C/domain/prompt_slots.py:121-140` (`NOT_RUN_BY_ANY_COMPOSITION`) vs `EX/registry.py:100-109` which registers `research_analysis` and the Deep Research kinds by default; plan `system-prompts-settings` chunk 7's rationale "registered by no composition" is stale (`system-prompts-settings.md:211-216`). MVP-32 says respondent and Deep Research prompts "stay read-only (method)" (`overview.md:603`) while chunk 7 would wire respondent, analysis and Deep Research: scope disagrees. |
| Effective route (retention, EU, training flags), per-tier models, per-worker price in Settings | MISSING | see §7.1; NONE |
| Settings writes the route classes | MISSING by design | operator, not product (§7.3) |
| Deep Research settings (ADR 0022): values, approval, live readiness | EXISTS | `API/routers/deep_research_settings.py`; plan chunks 40-44 done |
| "Reach" panel (each route and connector built/approved/active/refused with reason) | MISSING | `deep-research-web-search` 52 (open), W1 S2 |
| Open posture per client, who sets it, where it is shown | MISSING | plan 53 names "organization OWNER or ADMIN" and "client's profile"; there is no route in `mvp-target-architecture.md` §5 (it lists envelope-ceiling and admin leads, not data-posture), no UI chunk, no audit store (§4). M10 only adds the column. |
| What class an OPEN client's Deep Research **model** requests carry | MISSING | plan 53: "the design is treated as Class C" (`deep-research-web-search.md:1660-1662`), which lowers the owner's rule B for these requests (`material_rules.py:25-29` "can only make it stricter, never looser"; `deep_research/plan.py:163` is the only classifier). The dev plan claims "model gateway and material_rules ... not touched" (`mvp-development-plan.md:72-76`) which holds only if the lowering is limited to queries; the model requests are not mentioned. |
| Methodology (ADR 0023): catalogue, versions, check/compare (any member), publish and activate (OWNER/ADMIN) | EXISTS | `API/routers/methodology.py` (CLAUDE.md map; not opened) ◇ |
| System prompts tab (ADR 0020) incl. the Lead's prompt | EXISTS | `prompt_slots.py:104-110` |

---

## 9. Scope and identity for every new route the plans add

Existing pattern: every study route resolves a `StudyContext` through `StudyScopeDep` (404 for a study outside scope,
403 for permission); the researcher's own Lead resolves `OrganizationContext` and the repository filters by `actor_id`
(`API/routers/lead.py:469-505`; `C/infrastructure/researcher_lead_repository.py:95-101`). Membership is access (ADR 0019).

| New route (from `mvp-target-architecture.md` §5) | Scope design | Status |
|---|---|---|
| `POST workspace/ops`, `GET workspace/ops`, `PUT/GET presence` | study path, member | MISSING (M1, M2); the existing whole-copy `PUT workspace/content` (`API/routers/workspace.py:2064`) stays, and there are **six** current writers of the working copy (`workspace.py:2064`, `research_lead.py:594`, `proposal_accept.py:142`, `design_reuse.py:186`, `study_design_repository.py:226`, `study_workspace_repository.py:323/444`) against the planned rule "the working copy is written only by `apply_edit_ops`" (`mvp-target-architecture.md:411-413`); the web's autosave sends whole content with a base revision (`WEB/research/store.ts:209-215`). Converting that is not in any chunk. |
| `GET/PUT envelope`, `POST envelope/raise`, `lead/plans*`, `lead/commands`, per-change `accept` | study path | MISSING; new permission use is stated (`APPROVE_GATE`, `EDIT_STUDY`) |
| `GET/PUT /organization/clients/{id}/envelope-ceiling` | org role OWNER/ADMIN, client in path | MISSING; the prefix `/organization/` is new: today's admin client routes sit at `/clients/{client_id}/status` and `/self-approval` (`API/routers/scope.py:343, 527`), and `OrganizationContext` "carries no client or study id" (`C/domain/scope.py:888-896`), so the route needs a client lookup under an org context, a pattern with no precedent here |
| `PUT /clients/{id}/datasets/{source_id}/contract` | client path, `PROPOSE_CLIENT_KNOWLEDGE` ◇ | MISSING (S3) |
| data posture set/read | none specified | MISSING (§8) |
| `GET /admin/leads/{user_id}`, `POST .../handover` | org OWNER/ADMIN, target user in path; isolation test for another organization's user | MISSING (§2) |
| CI route list | `ci.yml` `api-contract` `required` (`.github/workflows/ci.yml:520-590`) says all routes are listed (`mvp-target-architecture.md:277`) but contains **none** of the seven existing Lead routes (`/lead`, `/studies/{id}/lead`, `.../turns`, `.../edits`, `.../self-update`, `.../request`, `/lead/preferences`): `grep -n lead ci.yml` is empty. The scope assertion's keyword test (`/projects`, `/runs`, `/artifacts`, `/agent-jobs`, `ci.yml:607-614`) would not cover `/lead*`, `/envelope`, `/presence` either. Gap in the contract the plan relies on. |
| Stale comments about scope | CONTRADICTION (minor) | `C/domain/scope.py:3-9` still documents "Client grant -> Study grant -> Role" and `OrganizationRole`'s docstring says admins "do not grant the ability to read client research data" (`:110-118`), and the self-approval comments say "default of False" (`:533`, `:612`); all superseded by ADR 0019 (`DEFAULT_SELF_APPROVAL_ALLOWED = True`, `:313`). |

---

# Lists

## (A) GAPS: a link MISSING with no plan

1. **The continuation turn** (a finished step returns typed results to the Lead) has no kind, trigger, table or plan; turns are person-started only (`C/application/research_lead.py:763-790`, `tables.py:801-802`). Owner: S1.
2. **Pre-flight and remedy for the route-class refusal.** No surface says who fixes it or links (§7.3), the API cannot evaluate class, `/config` omits retention/EU/training, and the dev plan's "small chunk in chunk 11" is not in the chunk text (`research-lead-workbench.md:15`). Owner: S1 (messages, Settings) with S3 (deploy).
3. **Production route classes and route id.** ADR 0010's amendment is develop-only; production's retention evidence, class approval and the requirement `AIA_AI_ROUTE_ID == bedrock-eu-primary` (`licence_determinations.py:44`) are in no plan or `infra/production` chunk. Owner: S3.
4. **Typed start API for the plan executor without `confirm_cost_usd`**, and a rule it cannot reach the full start (`research.py:724-742` takes the confirmation as an argument). Owner: S1 with S3's ledger.
5. **Three new workers**: no binding for `REPORT_WRITING`, no result kind or accept path for interpretation, report wording and straight-liner flags, no job input for a result artifact, no per-worker price/key (single reservation, `API/config.py:123-126`). Owner: S1 (S2 supplies the straight-liner flags).
6. **Lead file revisions have no reader or rollback** (`revisions()` unused); F14's "rolled back" has no path. Owner: S1.
7. **Admin read and handover** (repository invariant amendment, `access_audit` actions, routes, ADR) and the **USER file's handover rule**; departure trigger. Owner: S1.
8. **Data posture**: no route, UI, permission wording, audit store (M10 column only), and no stated class for an OPEN client's Deep Research *model* requests. Owner: S2 (rule), S3 (column, route).
9. **Working-copy writers**: six writers to be migrated onto `apply_edit_ops`, including the web's whole-content autosave. No chunk. Owner: S1.
10. **`approve_request` not bound to the card's revision**, and the 64 KB vs 96 KB mismatch yields a 500 on approval ◇. Owner: S1.
11. **Settings does not show the effective route, the models per tier, or FAST_EXTRACTION** (`settings.py:529`), and `/config` reads `APPROVED_FOR` without retention. Owner: S1.
12. **A second researcher cannot accept the first Lead's edit blocks** (turn-scoped), against F12.5. Owner: S1.
13. **A `read` capability for D19** has no field in `LeadOutput` and conflicts with ADR 0026 decision 3. Owner: S1 (ADR first).
14. **CI route contract omits all Lead routes**; the scope assertion's keyword list will not cover new ones. Owner: S3.

## (B) CONTRADICTIONS

1. **Spend limit is called the hard stop.** `mvp-target-architecture.md:134` vs `C/application/research.py:452-454` and `C/domain/scope.py:562-566` (a confirmation threshold; the cap is `budget_usd`, `workflow_repository.py:1240`). The envelope is defined against the wrong quantity.
2. **Structural auto-accept.** `overview.md:585` and `research-lead-workbench.md:141-144` (allowed per stage) vs `mvp-cohesion.md:359-360` and `mvp-target-architecture.md:98-101` (text only).
3. **Autopilot timing.** `research-lead-workbench.md:28, 131-133` D16 and `overview.md:574, 584` (MVP-3, MVP-13 "one card at a time, no standing budget") vs `mvp-development-plan.md:136` (envelope and plan card in W1) and `mvp-cohesion.md:432-445` (supersedes MVP-13). The dev plan says the plan wins on conflict (`:7-8`), so the dev plan is the stale one until the chunks exist.
4. **Spend limit on the manual job:** OI-127 (open, owner's call) and plan F1 (observation) vs cohesion F5 (adopted, a fix) and dev plan W0.
5. **ADR 0026 vs code.** Decision 2's layers vs `freeze_context`; "Accepted with" 6 "a memory note ... takes no approval gate" vs `decide_self_update` (`research_lead.py:620-676`); decision 3 "the Design Revision it is asked on" vs `approve_request`; domain docstring "only when the researcher asks" (`:18-21`) vs prompt `:718-719`.
6. **Accept invariant.** "After any accept head == working copy" (`mvp-target-architecture.md:179-183`) vs the Lead edit accept that submits no Design Revision (`research_lead.py:592-601`).
7. **Plan stale rule vs sequential steps** (`mvp-target-architecture.md:144-146` vs `proposal_accept.py:130-156`).
8. **AC-02 "every AI action through the Lead"** vs ADR 0026 decision 4, `research_lead.py:705-707`, and client-level AI with no study.
9. **Dev plan's remedy vs product:** "an administrator widens it on Nastavení → AI" (`mvp-development-plan.md:81`) vs a read-only Settings and an operator-only SSM procedure (`deploy/develop/README.md:412-470`); and the dev plan understates which requests park (A only; B too, `:77-79` vs `README:401-404`).
10. **Map snapshot approval** has two ledger shapes (`artifact_repository.py:568` vs `mvp-target-architecture.md:224`).
11. **Settings vs worker:** FAST_EXTRACTION shown unused (`settings.py:529` vs `ai_runtime.py:729-730`); prompt slots "not run by any composition" (`prompt_slots.py:121-140` vs `registry.py:100-109`); `system-prompts-settings` 7 vs MVP-32 scope.
12. **OPEN posture lowers the design to Class C** for Deep Research (`deep-research-web-search.md:1660-1662`) against "an operator ... can only make it stricter" (`material_rules.py:25-29`) while the dev plan says `material_rules` is not touched (`:72-76`). Known doc follow-ups: AC-11 "approved for Class B" (`mvp-acceptance.md:86`) and AC-13 "a reviewer other than the producer" (`:88`) vs the owner's later decisions.
13. **Lead 96 KB vs agent 64 KB** (`research_lead.py:116` vs `research_agents.py:582`).
14. **Stale scope comments** (`scope.py:3-9`, `:117-122`) vs ADR 0019.
15. **"Client budget"** in the header drawer (F16) vs `clients.budget_usd` that pays only client-level work (`scope.py:563-572`); and the client *ceiling* reuses the word.

## (C) INTERFACES crossing plans or sessions with no owner

1. **`workflow_repository.py` ledger writers** are edited by S1 (plans, `chat_start`), S2 (runs, QC) and S3 (data_contract, reports); no surface owner (`mvp-development-plan.md:107-111`). Proposed owner: S3 (the migration-lane owner), with S1 reviewing Lead rows.
2. **`material_rules.py` and `residency.py`** (class rules) are touched by S1 (results context classification), S2 (OPEN posture, client-reported data) and S3 (data contract); unlisted. Proposed owner: S1, S2/S3 open small PRs.
3. **`apps/web/src/components/aia/settings/` and `routers/settings.py`**: S1 owns the router, S2 adds the Reach panel, S3 would show posture and ceiling. Proposed owner: S1; Reach and posture as small PRs.
4. **`domain/workflow_templates.py` and `executors/registry.py`** gain `lead_plan` (S1) while S2 and S3 add step kinds; closed set, no owner. Proposed owner: S1 for registration, each session for its own kind.
5. **`prompt_slots.py` (S1) vs `analysis.py` (S2)**: wiring analysis prompts needs the analysis executor to take a pin; the chunk sits under S1 in W3 (`mvp-development-plan.md:167`). Proposed owner: S2 for the executor half.
6. **`ResultsContext` provider contract**: S1 owns the type, S2 and S3 supply providers; "contract before W2" has no file, chunk or reviewer (`mvp-development-plan.md:158-159`). Proposed owner: S1, written as an ADR addendum.
7. **Licence route id vs `infra/production`** (S2's `licence_determinations.py` vs S3's Terraform and SSM). Proposed owner: S3 with a test that the production env's route id is in `PANEL_APPROVED_ROUTE`.
8. **`WEB/lib/api.ts` and `WEB/i18n/cs.ts`** (one 2,700-line file) are edited by every session and are the carrier of every refusal message in §7.3; unlisted. Proposed owner: S1 for refusal wording, the rest by area.
9. **The working copy's writers** (`study_workspace_repository.py`, `study_design_repository.py`, `design_reuse.py`, `proposal_accept.py`, `workspace.py` router) are split across S1 (`apply_edit_ops`), S3 (`client_*`, reuse) and the web store; `apply_edit_ops` as sole writer needs all of them. Proposed owner: S1.
10. **Client-level paid AI** (`client_source_proposals`, `clients.budget_usd`) belongs to S3 but is outside the Lead's reach, while AC-02 says every AI action is through the Lead. Proposed owner: S3, with an explicit exception recorded in AC-02.
