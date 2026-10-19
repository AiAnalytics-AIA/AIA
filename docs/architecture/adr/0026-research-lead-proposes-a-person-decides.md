# ADR 0026 — The Research Lead proposes; a person decides, and an accept updates the working copy on the server

**Status:** Proposed — 2026-10-19, for the product owner's acceptance. Plan
[research-lead-workbench](../../../.planning/plans/research-lead-workbench.md). Nothing in it is
built until it is accepted, except the plan's web chunks that call no model and change no API
(its chunks 1–6). **Builds on** [ADR 0005](0005-llm-gateway.md) (the one model call path),
[ADR 0016](0016-research-execution-and-model-transmission.md) (a run executes an immutable Design
Revision), [ADR 0018](0018-aia-runs-without-18-6-6.md) (a Study's working content lives in AIA),
[ADR 0019](0019-two-roles-and-human-ai-gates.md) (who decides what the AI produced) and
[ADR 0020](0020-runtime-editable-system-prompts.md) (a prompt is pinned at enqueue). **Changes**
one existing route, the accept of an agent job's proposal (decision 6). **Leaves unchanged** every
evidence gate, the Sociomap register, the methodology in force and every run's pins.
**Date:** 2026-10-19

## Context

The research-lead prototype (`prototypes/research-lead-v2`, PR #481 @ 9b50963f) puts a study's
work in one place. The **Research Lead** ("Vedoucí výzkumu"), a conversation on the left (40 %),
stays with the person across every stage. The stage's artifact is on the right (60 %). The Lead
reads the study, explains readiness and results, prepares changes as inline proposals and starts
the specialist jobs. A person accepts or dismisses each proposal where it lands. The product owner
has asked for this as AIA's target state.

AIA today has the parts but not the conversation:

- **Specialist jobs.** Design help is a durable job, never a request-time call. `ResearchAgentJobs`
  (`packages/aia_core/src/aia_core/application/research.py:1287 @ 50547cdc`) enqueues a
  `research_agent` run (`domain/workflow_templates.py:60 @ 50547cdc`). The run carries the Design
  Revision it was asked on, the action, the context hash and the pinned prompt
  (`research.py:1373-1382 @ 50547cdc`).
- **Accepting a proposal.** It needs `EDIT_STUDY` and `APPROVE_GATE` (`research.py:1492-1494 @
  50547cdc`); the worker holds neither approve permission (`domain/scope.py:202-213 @ 50547cdc`).
  The accept writes a Design Revision through `submit_if_current`
  (`infrastructure/study_design_repository.py:167-184 @ 50547cdc`) and the approval-ledger row
  (`infrastructure/workflow_repository.py:2406 @ 50547cdc`), in one transaction.
- **Model calls.** Only the worker calls a model, under a lease, through `StepModelCaller` and
  `GovernedModelGateway` (`ARCHITECTURE.md:133-134 @ 50547cdc`).

Three things the prototype does are not true of AIA today. They are what this ADR decides.

1. **A proposal does not go stale on your own edit.** The web client accepts with the job's own
   baseline (`apps/web/src/components/rehome/research/useResearchAgents.tsx:86 @ 50547cdc`), so the
   check at `research.py:1496-1497 @ 50547cdc` passes. The server refuses only when another Design
   Revision was submitted since the job started (`study_design_repository.py:180-183 @ 50547cdc`).
   Saving the working copy does not move the head Design Revision. The only guard against an edit
   made while the job ran is in the browser: an exact comparison of the whole brief
   (`useResearchAgents.tsx:85 @ 50547cdc`). It refuses any edit at all, even one the proposal does
   not touch. It also refuses nothing that happened in another tab.
2. **The accept is two writes, from two places.**
   - The server writes the Design Revision and the ledger row.
   - The browser then writes the proposal into the working copy and saves it
     (`useResearchAgents.tsx:87-91 @ 50547cdc`).
   - If that save fails, the person is told the revision is stored but the working copy is not
     (`useResearchAgents.tsx:91-94 @ 50547cdc`). The two copies of the design then disagree until
     somebody notices.
3. **There is no conversation, and nothing the AI starts on its own.** Every job is started by a
   person's button. A Lead that starts specialist jobs would spend the study's money on a model's
   judgement.

## Decision

### 1. A Lead turn is a durable worker step; the API never calls a model

A person's message is stored, and a `research_lead` run with a single `research_lead_turn` step is
enqueued under the Study's design project, owned like an agent job (`DESIGN_PROJECT_OWNER`). The
worker answers it through `StepModelCaller` with the reservation, metering, checkpoint and
recovery of every other model step. The web client follows it through the run's event feed, as it
follows an agent job today.

This is a constraint of the architecture, not a choice: the API has no model path
(`ARCHITECTURE.md:133-134 @ 50547cdc`).

The turn names `ModelCapability.RESEARCH_REASONING` (`domain/ai_models.py:67 @ 50547cdc`), as the
design agents do (`domain/research_agents.py:643-646 @ 50547cdc`). It does **not** name
`RESEARCH_LEAD` (`ai_models.py:68-71 @ 50547cdc`): that capability is Deep Research's lead
researcher, with its own policy entry. The two names are close; the code keeps them apart.

### 2. The Lead's context is frozen at enqueue, in a fixed order, and inspectable

At enqueue, the application service assembles the turn's context and stores it as the step's
input, hashed like an agent job's snapshot (`research.py:1376 @ 50547cdc`):

1. **The pinned prompt.** `aia.research.lead`, through `PromptResolver` (ADR 0020), as
   `ResearchAgentJobs._pin` does (`research.py:1386-1405 @ 50547cdc`).
2. **Approved Client Knowledge.** Read through `ClientKnowledgeRepository` under the Study's scope.
   No contacts, no profile, no unapproved source.
3. **The Study's state.**
   - Name and stage.
   - Budget, spent and spend limit.
   - Runs in flight, by state.
4. **The design.**
   - The current working content, with what changed since the Lead last answered (by item,
     decision 5).
   - The head Design Revision.
   - Readiness and the question outlook, as `ResearchRuns.outlook` computes them.
5. **Results, only on the result stages.**
   - Admitted claims and their evidence refs.
   - Measure verdicts.
   - The Sociomap register's status for each map.
   - Report status.
   - No respondent row, ever.
6. **The active stage's contract** (decision 4).
7. **The conversation.**
   - A rolling summary of older turns, stored as an artifact of the Lead's run.
   - The most recent turns verbatim.

Each layer has a byte bound. A context over its bound drops the oldest verbatim turns first, then
fails the turn by name; it is never cut silently.

The **data class** follows the rule the design agents already use (`research_agents.py:629-640 @
50547cdc`). The design text and the message are classified as material. Any approved knowledge
makes the request `CLASS_A_CLIENT_CONFIDENTIAL` (`domain/residency.py:59 @ 50547cdc`). The most
restrictive class wins, and an unknown class refuses dispatch. When the context carries a
`MODELLED_AI_PANEL` result, the request declares panel lineage, so the licence gate keeps it on
`bedrock-eu-primary` (OI-61).

### 3. The Lead's output is closed; it holds no tools

A turn returns one structured object, validated with one schema repair at most, as the agents' are
(`research_agents.py:659 @ 50547cdc`):

- **`reply`.** Czech prose. Any number in it must be one of the context's admitted claims, cited
  by its ref. A reply that writes any other number is refused by the validator, not by the prompt.
- **`view`.** Visual commands only: open a stage, focus an item by its `data-aia` id, open the
  inspector, switch a result view. They change what the person sees and nothing stored.
- **`requests`.** At most one prepared specialist job (action, instruction, the Design Revision
  it is asked on), or one prepared human action from decision 4's registry (start a run, lift a
  budget, approve a report). Each is shown as a decision card and does nothing until a person
  acts on it.

The Lead calls no tool, reads no table, makes no HTTP request and runs no code. Everything it
knows is in its frozen context.

### 4. One command registry, shared by the interface and the Lead, with human-only gates

Every action a stage offers is a typed command in one registry
(`aia_core/application/lead_commands.py`, new). The interface's buttons and the Lead's prepared
requests resolve to the same command. Each command declares:

- its input schema;
- its permission;
- whether it is **human-only**;
- its idempotency rule;
- the ledger row it writes;
- the existing service it calls.

The registry calls the existing services. It adds no new path to the database.

The prototype shows four capabilities as *proposed*: open-answer coding, audience-assumption
evidence, semantic report edits and respondent replacement. AIA has none of them. The registry has
**no command** for any of them, so neither a button nor a Lead request can reach one. Where a
person meets one, the interface says *V AIA zatím není*. Each needs its own ADR and a deterministic
admission rule first: a report is composed from admitted claims and frozen on approval, and
respondents are drawn once per run.

A human-only command is refused (`403 human_gate_required`) unless a person's request invokes it
directly. A Lead turn can only create a *pending request* for it.

| Command | Calls | Human-only |
|---|---|---|
| `workspace.save` | `StudyWorkspaceRepository.save` (`study_workspace_repository.py:209 @ 50547cdc`) | no |
| `design.submit` | `StudyDesignRepository.submit` (`study_design_repository.py:124 @ 50547cdc`) | no |
| `agent.enqueue` | `ResearchAgentJobs.start` (`research.py:1300 @ 50547cdc`) | **yes** (decision 7) |
| `proposal.accept` | `ResearchAgentJobs.accept`, changed by decision 6 | **yes** (gate 1) |
| `proposal.dismiss` | the approval ledger, `decision = "dismiss"` (decision 8) | **yes** |
| `proposal.rebuild` | `ResearchAgentJobs.start` on the current revision, `rebuild_of` in metadata | **yes** |
| `run.readiness` | `ResearchRuns.outlook` (read) | no |
| `run.start`, `run.retry`, `run.retry_analysis` | `ResearchRuns.start` / `retry` / `retry_analysis` | **yes** (gate 2) |
| `run.cancel`, `run.resume` | `ResearchRuns` / `ResearchAgentJobs` / `DeepResearchRuns` | **yes** |
| `budget.lift`, `study.spend_limit` | `lift_study_budget_waits`, `ScopeRepository.set_study_spend_confirm` | **yes** |
| `deep_research.start` | `DeepResearchRuns.start` / `start_interpretation` | **yes** (gate 2) |
| `report.approve` | `approve_report` | **yes** (gate 3) |

Each stage also has an **AI interaction contract**. It names the stage's readable state, its
visual actions, the registry commands valid on it, and the refusals that apply now: readiness
failures, suppressed cells, an `INTERNAL_ONLY` map, a closed study. The server builds the
contract. The Lead receives it in its context, and the interface reads the same contract to decide
which buttons to draw. The client never tells the server what is allowed.

### 5. A pending proposal goes stale when your edit touches an item it changes

*(Product owner, 2026-10-19.)*

An **item** is the unit a person edits and a proposal changes, with a stable key:

- a brief field;
- an objective, research question or hypothesis, keyed by its normalised text, as `diffLists`
  keys them (`apps/web/src/research/proposal-diff.ts:22 @ 50547cdc`);
- a tracked set, by id;
- a questionnaire section, question or battery, by id;
- the audience, as one item;
- the dimension selection and the sample size, as one item each.

A pure domain function, `design_items(before, after) -> frozenset[ItemKey]`, computes which items
differ between two contents. It is the server's counterpart of `proposalDiff` and is tested
against the same cases.

**At enqueue**, the job records `base_workspace_revision` beside `design_revision_id`: the
working-content revision its Design Revision was submitted from. It also records `touched_items`
once the proposal exists. The worker computes those from the proposal against its baseline and
stores them with the proposal artifact.

**At accept**, the proposal is refused (`409 stale_proposal`, details naming the conflicting
items) when either of these holds:

- the head Design Revision has moved (today's `submit_if_current` check, kept); or
- some item in `touched_items` also appears in `design_items(working copy at
  base_workspace_revision, working copy now)`.

An edit to an item the proposal does not touch never makes it stale. A stale proposal is never
accepted. **Rebuild** starts a new job on the current design; it accepts nothing and leaves the
stale one readable.

### 6. Accept updates the working copy on the server, in one transaction

*(Product owner, 2026-10-19: best practice, the server writes both.)*

`POST /studies/{id}/research/agent-jobs/{run_id}/accept` becomes one command and one transaction,
under the Study row lock `submit_if_current` already takes:

1. **Check the stale rule** (decision 5).
2. **Merge.** Apply the proposal to the *current* working content item by item: each touched item
   takes the proposal's value, and every other item keeps the person's.
3. **Write the Design Revision.** `submit_if_current` writes the merged content, so the Design
   Revision and the working copy are the same design.
4. **Write the working copy.** A new working-content revision, `reason = "ai_proposal_accepted"`,
   based on the current working revision.
5. **Write the ledger.** The approval-ledger row, naming both new revisions.

All of it commits or none of it does.

**Request.** `{ expected_revision_id, expected_workspace_revision }`.

**Response.**
`{ design_revision_id, design_revision, created, workspace_revision, workspace_revision_id }`.

**The client** reloads the working copy from the response and no longer writes the proposal back.
The two-step path (`useResearchAgents.tsx:85-94 @ 50547cdc`) and its "stored but not saved" error
are removed.

**One switch.** The web client and the API deploy together, from one merge to `develop`, and no
other client calls this route. So the change ships in one PR that changes both sides; there is no
release that runs both behaviours. A request without `expected_workspace_revision` is refused
(`422`), never served the old way.

### 7. A specialist job the Lead prepares is started only by a person

*(Product owner, 2026-10-19.)*

`agent.enqueue` is human-only. A Lead turn may *prepare* a job: the action, the instruction, the
Design Revision, and its cost ceiling. The interface shows it as a decision card in the
conversation, and the job is enqueued only when a person approves the card, every time.

The approval:

- is written to the approval ledger (`subject_type = "lead_job_request"`) in the transaction that
  starts the job;
- applies the study's spend limit as `ResearchRuns.start` does (`research.py:716-729 @ 50547cdc`).
  - The ceiling is the agent reservation: primary plus one repair, read from a new API setting
    `ai_research_reservation_usd`, which mirrors the worker's `AIA_AI_RESEARCH_RESERVATION_USD`.
  - At or above the limit, the card asks for the confirmation and records it (ADR 0019 gate 2).
  - With a limit set and no reservation configured, the start is refused as unknown
    (`CostCeilingUnknown`); it is never let through as zero.

The Lead's own turns are not jobs it starts. A person starts each turn by sending a message. Each
turn holds its reservation against the study's budget and parks `AWAITING_BUDGET` when it does not
fit, like any step.

### 8. One new table: the conversation. Proposals stay where they are

**`study_lead_turns`**, append-only, one row per turn. It is read and written only through
`StudyLeadRepository` under a `StudyContext`, enforced by `make layer_check`. Its columns:

- `turn_id`, `organization_id`, `client_id` and `study_id`.
- `sequence_no`, unique per Study.
- `actor`: a person or the Lead.
- `stage`.
- `workspace_revision` and `design_revision_id`: what the turn saw.
- `run_id`: the Lead turn's run.
- `text`, bounded: the person's message, or the Lead's reply once its step has finished.
- `created_at`.

The reply is copied once, from the step's artifact, so that listing a conversation reads no
artifact. That is the one deliberate copy. The artifact keeps the full structured output and its
provenance.

There is **no conversation table**: one Study has one conversation, so `study_id` is its key. What
the Lead last saw is the newest Lead turn's `workspace_revision`.

There is **no proposals table**. A proposal's lifecycle is already held elsewhere:

- **The proposal** is a `research_agent` run and its artifact.
- **Its baseline** is in the run's metadata (with decision 5's two additions).
- **Its acceptance** is in the approval ledger.

Two states are new, and neither needs a column:

- **Dismissed.** A person's decision about AI output, so an approval-ledger row with
  `decision = "dismiss"`. The acceptance check reads `decision = "accept"` only.
- **Superseded.** Derived: a newer run whose metadata names it as `rebuild_of`.

The interface's pending-proposals list is a projection over these.

### 9. Off by default, with its cost stated as an estimate

**The switch.** `AIA_AI_RESEARCH_LEAD_ENABLED` is off by default, in the worker and the API. It
needs `AIA_AI_RUNTIME_ENABLED` and a valid provider configuration.

**Its two keys.** `AIA_AI_RESEARCH_LEAD_MAX_OUTPUT_TOKENS` and `AIA_AI_RESEARCH_LEAD_RESERVATION_USD`
have no defaults. Unset, the turn parks `research_lead_unconfigured`. The reservation covers a turn
and one repair at the bounds.

**Switched off,** everything that is not a model turn still works:

- the 40/60 layout;
- the navigator and the inspector;
- the proposals review;
- every button.

A message parks with its reason, and the pane says so. It never answers with something that is not
the Lead.

**Cost** is stated per turn as *reservation × (1 + repairs)*, the bound the gateway enforces. It is
never quoted from a provider's price list. Calls per turn: one, plus at most one repair.
Specialist jobs remain their own runs at their own reservation.

Before the switch is turned on for develop, chunk 10 measures and states, in its commit body:

- the input bytes per layer;
- latency from enqueue to reply;
- the metered cost of 20 turns on a fictional study.

## Consequences

- **Gains.** One conversation per study, stored in AIA and shared by everyone who opens the study.
  A proposal can no longer be applied over an edit it would overwrite, while edits elsewhere do not
  block it. The Design Revision and the working copy cannot disagree after an accept. No AI action
  spends money or changes the design without a person's decision in the ledger.
- **Costs.**
  - A new domain function (`design_items`) must stay in step with the web's `proposalDiff`; a
    shared set of cases holds the two together.
  - The accept route changes shape.
  - One table.
  - A worker step that is a conversation, whose context must be kept bounded by code.
- **Not decided here.** Streaming tokens to the browser: turns arrive whole, through the existing
  event feed. Any Lead tool use. Any model-written number.

## Alternatives considered

- **Answer turns in the API, streaming.** There is no model path in the API
  (`ARCHITECTURE.md:133-134 @ 50547cdc`). A call inside a request has no lease, no
  checkpoint and no recovery when the browser goes away.
- **Let the Lead call tools or services.** A tool call that mutates would sit beside the gates
  instead of behind them. The closed output and the registry give the Lead the same reach as a
  person's buttons, and nothing more.
- **Let the Lead start specialist jobs within a budget.** Rejected by the product owner: every job
  the Lead prepares needs a person's approval.
- **Stale on any edit,** as the browser does today. This refuses proposals that would not
  overwrite anything. Rejected for item-level staleness.
- **Stale only when the Design Revision moves** (today's server rule). An edit made while the job
  ran is silently overwritten by the accept. Rejected.
- **Keep the browser writing the working copy after the accept.** The two writes cannot be atomic,
  and the failure between them is already visible to people (`useResearchAgents.tsx:91-94 @
  50547cdc`). Rejected.
- **A `study_lead_proposals` table.** It would repeat the run, its metadata and the ledger, and
  three sources would have to agree. Rejected for a projection.
- **Keep the conversation in the browser,** as the prototype does. Not shared, not durable, and not
  auditable (ADR 0002). Only the split width stays per browser.
