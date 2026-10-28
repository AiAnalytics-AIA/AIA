# ADR 0026 — The Research Lead proposes; a person decides, and an accept updates the working copy on the server

**Status:** Accepted — 2026-10-19, by the product owner, with the decisions under *Accepted with*
below; proposed the same day. Plan
[research-lead-workbench](../../../.planning/plans/research-lead-workbench.md). **Builds on** [ADR 0005](0005-llm-gateway.md) (the one model call path),
[ADR 0016](0016-research-execution-and-model-transmission.md) (a run executes an immutable Design
Revision), [ADR 0018](0018-aia-runs-without-18-6-6.md) (a Study's working content lives in AIA),
[ADR 0019](0019-two-roles-and-human-ai-gates.md) (who decides what the AI produced) and
[ADR 0020](0020-runtime-editable-system-prompts.md) (a prompt is pinned at enqueue). **Changes**
one existing route, the accept of an agent job's proposal (decision 6). **Leaves unchanged** every
evidence gate, the Sociomap register, the methodology in force and every run's pins.
**Status note, 2026-10-25 (decision 4 as built):** the command registry lives at
`packages/aia_core/src/aia_core/domain/lead_commands.py` (#574), not
`aia_core/application/lead_commands.py`: a closed vocabulary of typed start commands matched by
code, pinned in `tests/fixtures/lead_commands/commands.json` (`domain/lead_commands.py:122 @
5d5ed250`, `match_command`), started through `application/lead_chat_start.py`. A human-only command
is not yet refused with `403 human_gate_required`: no code raises it
(`git grep human_gate_required 5d5ed250` finds only this ADR and the evidence trace). That gap is
tracked as an open item. The status is unchanged.
**Amendment 2026-10-28 (Proposed, not accepted; its five questions answered by the product owner):** [read tools inside a turn; paid work stays an
approved job](#amendment-2026-10-28-proposed-the-lead-reads-through-tools-inside-a-turn-paid-work-stays-an-approved-job),
amending decision 3. Until the product owner accepts it, decision 3 stands as written.
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
- **`edits`.** The Lead's tools on a stage's artifact, a closed set of item operations:
  - set a brief field;
  - add, replace or remove an objective, research question or hypothesis;
  - add, edit or remove a questionnaire question;
  - set the sample size.

  Each edit names the item and why. Code grounds each one against the working content, and an
  edit naming an item that does not exist is dropped and said so. An edit is shown in the artifact
  as a change block.

  It changes the working copy only through the server's gate,
  `POST …/lead/turns/{turn_id}/edits`, which needs `APPROVE_GATE`. In one transaction, under the
  lock the working copy's save takes, it:
  - refuses a stale base (`stale_revision`);
  - applies the accepted edits by the same rules the web shows (`domain/research_lead.py
    apply_edit`);
  - saves the working copy (`reason = "lead_edit_accepted"`);
  - writes one approval-ledger row per decided edit (`subject_type = "lead_edit"`, accept or
    dismiss).

  A decision is made once, and the conversation reads it back from the ledger. An AI edit
  therefore never reaches the study without gate 1's record.
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
- the dimension selection and the sample size, as one item each;
- in the working copy's separate `analysis` document, the research plan's fields, as the plan
  stage edits them. A brief-analysis proposal returns its replacement analysis beside the project
  (`domain/research_agents.py:705-709 @ 50547cdc`), and the working copy saves it as its own
  argument (`study_workspace_repository.py:209-216 @ 50547cdc`), so both documents are diffed and
  merged.

A pure domain function, `design_items(before, after) -> frozenset[ItemKey]`, computes which items
differ between two contents. It is the server's counterpart of `proposalDiff` and is tested
against the same cases.

**A Design Revision records the working revision it came from.** A Design Revision stores no
working-copy revision today (`domain/design.py:98-113 @ 50547cdc`). Without one, a job started
later on an older revision cannot know its real baseline. This is exactly the case of a decision
card approved after the person kept editing. Take working copy W1 that produced design D1. The
person then edits an item, making W2, and a job on D1 starts. If that job recorded W2 as its base,
the accept would compare W2 with W2, find nothing, and overwrite the edit.

So the submit names `workspace_revision`. The server checks that the submitted content and
analysis are that working revision's, by canonical hash, refuses a mismatch
(`422 design_not_from_workspace`), and stores the working revision with the Design Revision.

Every writer of a Design Revision records it, not only the web's submit. Each one names the
working revision that holds the same design:
- **The web's submit**, `POST …/design/revisions`, names it, and the server checks it, as above.
- **Reusing a past design** (`application/design_reuse.py:186-187 @ 50547cdc`) saves the working
  copy and then submits the same content, so it records the revision that save wrote.
- **An accepted proposal**, whether an agent job's or a Design Research proposal's
  (`application/design_research.py:118-120 @ 50547cdc`), writes the working copy and the Design
  Revision in one transaction (decision 6), so it records the working revision that transaction
  wrote.

`StudyDesignRepository.submit` and `submit_if_current` take the working revision as a required
argument, so a new writer cannot leave it out.

**At enqueue**, the job copies that stored value as `base_workspace_revision`, never the working
copy's current revision. It also records `touched_items` once the proposal exists. The worker
computes those from the proposal (content and analysis) against its baseline and stores them with
the proposal artifact.

A Design Revision made before this rule has no working revision. A proposal on it cannot be checked
item by item, so its accept is refused as stale (`unknown_baseline`) and the person rebuilds it. An
unknown baseline is never read as "nothing changed".

**At accept**, the proposal is refused (`409 stale_proposal`, details naming the conflicting
items) when either of these holds:

- the head Design Revision has moved (today's `submit_if_current` check, kept); or
- some item in `touched_items` also appears in `design_items(working copy at
  base_workspace_revision, working copy now)`, content and analysis alike; or
- the baseline is unknown (above).

An edit to an item the proposal does not touch never makes it stale. A stale proposal is never
accepted. **Rebuild** starts a new job on the current design; it accepts nothing and leaves the
stale one readable.

### 6. Accept updates the working copy on the server, in one transaction

*(Product owner, 2026-10-19: best practice, the server writes both.)*

`POST /studies/{id}/research/agent-jobs/{run_id}/accept` becomes one command and one transaction,
under the Study row lock `submit_if_current` already takes:

1. **Check the stale rule** (decision 5).
2. **Merge.** Apply the proposal to the *current* working content **and analysis**, item by item:
   each touched item takes the proposal's value, and every other item keeps the person's. An
   analysis the proposal does not change is kept as it is, never cleared. A brief-analysis
   proposal installs its analysis, as the client does today (`useResearchAgents.tsx:87-90 @
   50547cdc`).
3. **Write the Design Revision.** `submit_if_current` writes the merged content, so the Design
   Revision and the working copy are the same design.
4. **Write the working copy.** A new working-content revision of the merged content and analysis,
   `reason = "ai_proposal_accepted"`, based on the current working revision.
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
- `user_id`: the researcher whose session it is. Every read and write of the conversation, and of
  its runs' results, filters by it (*Accepted with* 6).
- `sequence_no`, unique per Study and researcher.
- `actor`: a person or the Lead.
- `stage`.
- `workspace_revision` and `design_revision_id`: what the turn saw.
- `run_id`: the Lead turn's run.
- `kind`: a message, or the greeting the Lead gives on opening a study.
- `text`, bounded: the person's message.
- `created_at`.

The Lead's reply is not copied into the row. It is the output of the turn's single step, which
listing a conversation reads in the same query as the runs (`list_runs(steps=True)`). So the reply
has one source.

There is **no conversation table**: a researcher has one conversation per Study, so `study_id` and
`user_id` are its key (*Accepted with* 6). What the Lead last saw is the newest Lead turn's
`workspace_revision`.

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

**Cost** is bounded per turn by one reservation, which already covers the turn and its one repair.
This follows the gateway's convention of one reservation per logical request. What a turn actually
cost is the metered usage, reported separately. The cost is never quoted from a provider's price
list. Calls per turn: one, plus at most one repair.
Specialist jobs remain their own runs at their own reservation.

The first turns on develop are measured and stated in the plan file:

- the input bytes per layer;
- latency from enqueue to reply;
- the metered cost of 20 turns on a fictional study.

## Accepted with

The product owner's decisions of 2026-10-19 on accepting:

1. **The Lead is part of the workbench, not an option in it.** The chat-centric workbench is the
   study screen on develop. The kill switch stays, because the repository's rules require one for
   paid behaviour (`CLAUDE.md` § 8). On develop it is on. Where it is off, or a turn parks, the pane
   says why, and the rest of the workbench works.
2. **The Lead controls the artifacts through tools**, as a design tool controls its canvas. Its view
   commands drive the artifact pane, and its edits arrive as change blocks in the artifact. An AI
   edit is never applied without a person, because applying it silently is ruled out.
3. **The Lead greets.** Opening a study with no Lead turn in the last eight hours starts one greeting
   turn: where the study stands, what waits on the person, and the next step. It is paid like any
   turn. Every post locks the researcher's own Lead row first, so two tabs opening a study at once
   start one greeting, not two.
4. **The Lead may prepare all four kinds of paid work** as decision cards:
   - a design job;
   - Design Research;
   - a research run;
   - Interpretation Research.

   - **A design job** is approved on the server (`POST …/lead/turns/{turn_id}/request`). In one
     transaction it checks the spend limit as a run's start does (`cost_confirmation_required`,
     `cost_ceiling_unknown`), submits the working copy as a Design Revision, starts the job and
     writes the ledger row (`subject_type = "lead_job_request"`). So F1 (an agent job ignores the
     spend limit) does not apply to Lead-prepared work.
   - **The other three** start nothing from the card. It opens the stage whose own start carries
     that start's gates: readiness, answerability and the spend limit.
   - *Decided 2026-10-21 (the product owner, Q44-Q47; not built yet):* a Lead card starts Design and
     Interpretation Research on the server through `approve_request` (`lead-orchestration#LO5a.2`).
     The Lead may offer every result target kind from a code-built candidate list, the
     `research_questions` module the default (Q44); a Design Research run may focus on named
     research questions, the whole design the default (Q45); QUICK and STANDARD are offered,
     STANDARD the default (Q46); a plan may chain fieldwork, then interpretation, the step parking
     if its module is BLOCKED (Q47). The record is `lead-orchestration.md` § *Deep Research under
     the Lead (2026-10-21)*.
5. **Live calls on develop, at a small cap.** The per-turn reservation is the smallest the gateway
   accepts. The route's approved data classes still decide which studies can be sent.
6. **Each researcher has their own Lead** (the product owner, later the same day). The Lead is
   a personal agent attached to the account, hatched once and shaped by working with it, in the
   manner of personal agents that keep a persona and a memory that evolves.
   - **Sessions.** A study's conversation is per researcher (`study_lead_turns.user_id`). Nobody
     reads another researcher's session.
   - **The Lead itself.** `researcher_leads` holds one Lead per researcher: its name and its persona,
     a closed set of tone, detail and focus choices plus the researcher's own words about how they
     work.
   - **Memory.** `researcher_lead_memories` holds notes. The Lead proposes at most two per turn as
     `remember`. The person can add notes, and can forget any note; forgetting sets
     `forgotten_at`, so nothing is deleted. A memory note is the researcher's own assistant memory,
     not client knowledge and not research truth, so it takes no approval gate. It is shown in the
     conversation the moment it is kept.
   - **Client isolation decides what a note may carry** (ADR 0004).
     - A `personal` note holds working style and preferences only, and goes with the researcher
       into every study.
     - A `client` note names its client and loads only into that client's studies. The query
       enforces this, not the prompt.
     - Memory text is classified like the design's, and a client note is Class A.
     - The residual risk is a client fact written as a personal note. The prompt forbids it, and
       the person sees every note as it is kept and can forget it. That risk is stated here rather
       than hidden.
7. **The visual target is the prototype** (`prototypes/research-lead-v2`, PR #481). Its layout and
   components are ported into the web client and wired to AIA's working content, runs and routes.
   The existing stage screens stay as the artifact bodies wherever they already do the work.

Later decisions of the product owner, 2026-10-21:

8. **A research run the Lead prepares is an approval card that starts the run** through Spuštění's
   own route, `POST …/research/runs`, with that start's gates (#550; amends *Accepted with* 4 for
   that kind). **Návrh's answers and comments go through the Lead**: in the workbench the stages
   show no AI start of their own, and "Požádat Vedoucího" asks the Lead (#550).
9. **A card the Lead's model prepared is refused while the Lead is off** (Q42): `POST
   …/turns/{turn_id}/request` answers 409 `research_lead_disabled`; stored edits stay decidable.
   `AIA_AI_RESEARCH_LEAD_ENABLED` is stated in every deployed environment, unset refused at start,
   and `GET …/lead` says whether a worker can answer (`worker_ready`, null when unknown) (#561).
10. **A typed start command bypasses the model and the Lead's switch** (Q43): a message that is
    exactly a command of `domain/lead_commands.py`'s vocabulary is stored as the person's command,
    Lead on or off, with no model turn, and started through `POST …/turns/{turn_id}/request`
    (ledger `chat_start`, the wallet when on); `GET /lead` lists the commands (#574; ADR 0028
    decision 3).

## Consequences

- **Gains.** One conversation per researcher per study, stored in AIA (*Accepted with* 6; corrected
  2026-10-21: this line said "shared by everyone who opens the study", which neither decision 6 nor
  the code says, OI-152).
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

## Amendment 2026-10-19: the Lead's own model

*(The product owner, 2026-10-19.)* The Lead's turns run on a model of their own, a
current-generation model on Bedrock, while every other capability stays on the route's
existing model. This amends decision 1's capability; nothing else in this ADR changes.

**A capability of its own.** A turn names `ModelCapability.STUDY_LEAD`
(`packages/aia_core/src/aia_core/domain/ai_models.py:94 @ 5d775785`,
`domain/research_lead.py:883 @ 5d775785`), not `RESEARCH_REASONING`. Decision 1 chose
`RESEARCH_REASONING` because the design agents use it; that is exactly why the Lead could not be
bound apart from them. `RESEARCH_LEAD` stays Deep Research's lead researcher.

**Bound on ADR 0010's route.** `STUDY_LEAD` resolves to the Lead's own model when one is
configured: an EU cross-region inference profile pinned to a version, a second policy entry on
the same route (`bedrock-eu-primary`), as the light model is. The worker pins it beside the
route's model through `PinnedModels`, each model behind its own route-bound adapter
(`apps/executors/src/aia_executors/ai_runtime.py:258, 740, 854 @ 5d775785`). It is the same
route, with the same egress, residency, licence and class approvals: a second model is not a
second approval. Unconfigured, `STUDY_LEAD` resolves to the route's model, so a deployment
without the keys runs the Lead exactly as before. The instance role is granted the profile only
when Terraform's `bedrock_lead_model_id` names it (`infra/develop/main.tf @ 9ba6777b`).

**The reservation follows the model.** Decision 9's per-turn reservation is checked at start
against the Lead's own model's prices, output ceiling and window when one is configured, never
the route's (`ai_runtime.py:765 @ 5d775785`). A hold sized at a cheaper model would let a turn
start that its reservation cannot cover.

**The request shape is declared, not guessed.** The model family the Lead runs on refuses, with
a 400, both ways the Bedrock adapter asked for structured output: a forced tool choice, and a
thinking budget beside an offered tool. It also refuses non-default sampling values, and it
thinks adaptively when nothing is said. So each model's catalog entry declares a request profile
(`RequestProfile`, `domain/ai_models.py:225 @ 5d775785`):

- `structured_output`: `forced_tool` (the default) or `auto_tool`;
- `thinking`: `budget` (the default) or `adaptive`;
- whether it accepts sampling;
- an optional effort, for an adaptive model only.

For an `auto_tool`, `adaptive` model the adapter offers the single output tool with
`toolChoice: auto`, and the gateway tells the model to answer through it, as it already did for a
thinking call (`application/model_gateway.py:454 @ 5d775785`). An answer in text takes the
gateway's one schema repair. The adapter sends no thinking budget and no temperature, and puts
only a configured effort in `additionalModelRequestFields`
(`infrastructure/model_adapters/bedrock.py:202-246 @ 5d775785`). A request the profile cannot
carry is refused before it is signed, by name, never quietly changed. The defaults are the shape
every model was sent before, byte for byte (`test_model_thinking.py`'s golden body).

**No model name in code.** The Lead model's id, prices, limits and profile come only from
configuration: `AIA_AI_RESEARCH_LEAD_MODEL_*` in the worker's environment, from Parameter Store on
develop. They have no defaults, and a missing or invalid key stops the worker by name. They are
recorded from the Bedrock console and pricing page by an operator
(`deploy/develop/README.md` § The Research Lead's own model). Tests use fake ids.

**Not changed.** The route, its approved data classes and retention; every evidence gate;
decision 3's closed output; the one repair; and the rule that the API never calls a model.

## Amendment 2026-10-28 (Proposed): the Lead reads through tools inside a turn; paid work stays an approved job

**Status:** Proposed, 2026-10-28, not yet accepted. Drafted at the product owner's request ("yes,
have a session draft the amendment", the PM coordinator's chat, about 20:45 UTC), from his question
"I feel like our current system prompts architecture would work better as tools for the lead agent,
or no?". **His answers to the draft's five questions** (the coordinator's chat, 20:52-20:55 UTC,
relayed by the coordinator): Q1 "Read tools + workers as defs"; Q2 "USD 0.50 or 8 rounds", whichever
comes first; Q3 "Native tool use first"; Q4 "Fold it in" (ADR 0042); Q5 "B, raised to A with client
data". They are written in below. Acceptance of the amendment as a whole is still his.
**Amends** decision 3 ("The Lead's output is closed; it holds no tools"), its last paragraph ("The
Lead calls no tool, reads no table … Everything it knows is in its frozen context") and decision 9's
"Calls per turn: one, plus at most one repair". **Replaces** ADR 0041 Amendment 1 A3's
three-call round (the bound is R4's) and the ADR 0042 that `lead-client-knowledge` LK1 planned:
client-knowledge search and read are two of R2's tools (Q4). **Leaves unchanged** ADR 0040 (a web
lookup stays a paid job answered by a continuation turn), ADR 0028 (every paid start is a card, a
plan step or a person's typed command), ADR 0020 (each worker's system prompt stays data the
methodologist edits), ADR 0005 (the governed gateway is the only model path), ADR 0008 (data classes
and the egress boundary), the edit gate and every evidence gate. Code anchors are at `develop` @
`28406c46` unless stated.

### Context

**What the Lead cannot answer.** On develop, 2026-10-28, in the Sonnet 5.5 probe, the Lead was asked
"Shrň mi, co běh zjistil" and answered that the values were not in its context. That is what the
code gives it: the runs layer carries each run's id, status and Design Revision id and nothing of
its results (`packages/aia_core/src/aia_core/application/research_lead.py:1528-1535`), and
`freeze_context` has no results, readiness detail or execution state layer
(`domain/research_lead.py:1170-1256`). LO8 (`ResultsContext`, execution row E11) is about to add
results as one more frozen layer. ADR 0041 gives that layer 4 KB to 16 KB (decision 2, layer 7). A
frozen layer must therefore either hold every number of a run on every turn, paid for whether or
not anyone asks, or hold a slice and leave the Lead saying "nevím" about the rest.

**What the Lead must not do** is unchanged: spend money, start work, approve anything or change the
study without a person's decision in the ledger. Decision 3 held no tools because "a tool call that
mutates would sit beside the gates instead of behind them" (*Alternatives considered*). A read that
changes nothing and costs nothing outside the turn's own model calls sits beside no gate.

**What the gateway can carry today.** One structured request and its one schema repair, nothing
else:

- a message is text only: `Message.content: str` (`domain/ai_contracts.py:523-527`);
- an adapter request carries one `output_schema` (`ai_contracts.py:664-690`), which the Bedrock
  adapter sends as a single tool, forced or `auto` (`infrastructure/model_adapters/bedrock.py:236-248`);
- the response keeps only that tool's input (`bedrock.py:348-363`). Any other `toolUse` block is
  dropped, and thinking blocks (`reasoningContent`) are skipped, signature included (`bedrock.py:33`,
  `:352`);
- a call's purpose is `PRIMARY`, `SCHEMA_REPAIR` or `FALLBACK` (`ai_contracts.py:789-794`). There is
  no tool round;
- `ToolRegistry` exists, takes scope never from arguments and requires a result class
  (`domain/ai_tools.py:1-21`, `:148-172`), but nothing outside the tests constructs one
  (`git grep "ToolRegistry(" -- packages apps ':!*/tests/*'` finds none at `28406c46`).

What exists to build on: `StepModelCaller.invoke` takes a reservation per request, so one step can
make several metered requests (`apps/executors/src/aia_executors/ai_step.py:195-207`). The analysis
step checkpoints each model turn the moment it returns, keyed by what was sent, so a retry replays it
and never pays twice (`aia_executors/analysis.py:17-20`, `:326-358`).

### Decision

**The rule: free and internal is read inside the turn; paid or external is a job.** A read costs
nothing beyond the turn's own model calls, sends nothing outside AIA and changes nothing, so it is a
*read tool* the Lead calls inside its turn. Anything paid, anything that reaches outside AIA (ADR
0040) and anything that changes the study stays an approved job, card or plan step, as today.

#### R1. Reads are provider-native tool use (Q3: "Native tool use first")

A Lead turn is a multi-round Converse conversation inside its one worker step:

1. The request offers the model the read tools of R2 and the output tool (`LeadOutput`).
2. The model answers with one or more `toolUse` blocks. Code validates each through
   `ToolRegistry.invoke` (strict arguments, scope never from arguments, `ai_tools.py:247-315`), runs
   it under the turn's own study scope and lease, and sends the results back as `toolResult` blocks.
   The model's reasoning blocks are returned unchanged, signature included, as Converse requires of
   a thinking model in a tool loop.
3. The turn ends when the model calls the output tool in a response holding no read call. Its input
   is validated as today's `LeadOutput` is (one schema repair).
4. A response that calls the output tool beside a read call is a read round. Its output is
   discarded, never applied, and the model is told to answer after the reads. So nothing is
   decided on an answer given before the data was seen.

The frozen context stays the first message (R5). There is no `read` field in `LeadOutput`.

**The gateway work this needs** is built first, as its own chunks (*Build* below), behind the same
switch:

- **`ai_contracts`:** `Message.content` becomes text or a closed tuple of content blocks (`text`,
  `tool_use`, `tool_result`, `reasoning`, the last kept as opaque provider bytes with its
  signature). A new `CallPurpose.TOOL_ROUND`. `ModelResult` carries the response's tool calls and
  reasoning blocks. The defaults stay byte for byte what every other caller sends.
- **The Bedrock adapter:** several tools in `toolConfig`, every `toolUse` block kept in order, the
  `reasoningContent` and `redactedReasoningContent` blocks kept and sent back untouched. A request
  that offers a tool loop to a model or adapter that cannot carry one is refused unsent, by name.
- **`GovernedModelGateway`:** a tool round is a call of its own, with its own ledger row,
  reservation, fingerprint of exactly what was sent (blocks included) and `TOOL_ROUND` purpose. The
  egress, class and licence gates run before **every** round on the round's own content, so a read
  that raises the class is judged before it leaves.
- **`StepModelCaller`:** the turn's ceiling and round cap (R4), and every round journaled and
  replayed (R6).
- **The first product `ToolRegistry`,** built in the executors' composition root with R2's tools, and
  an import contract that keeps the read-tool module away from any start, enqueue, reservation or
  ledger-write entry point.

#### R2. The read-tool set, closed and versioned

Each tool is a `ToolDefinition` with `effect = READS_STUDY_DATA`, a version, a required
`result_data_class`, and argument and result models that forbid undeclared fields. Every id an
argument names must be in the turn's frozen context (a run id from the runs layer, a question id
from the design, a ref from the knowledge index). This is checked as `request_refusal` checks a
card's ids today (`domain/research_lead.py:637-658`), and anything else is refused `not_in_context`
by name. The study is the invocation's, never an argument (`ai_tools.py:56-77`). A refused call goes
back to the model as an error `toolResult` with its code and counts as a call.

| Tool | Returns | Reads through | Class by rule | Bound per call |
|---|---|---|---|---|
| `run_results` (`run_id`, optional `question_ids`, at most 10) | Admitted rows only: each `AdmittedClaim`'s ref, metric, value, interval, support and Kish n. A suppressed row's ref and reason codes, **no number**; a refused question's violation codes, no rows | `application/admitted_results.py:104` (`admitted_results`, `VIEW_RESULTS`, held by the worker's scope, `domain/scope.py:202-213`) | B, raised to A when the run's analysis input carries client data (`evidence-integrity#8a`); the run's dataset lineage declared, so panel-derived results stay on `bedrock-eu-primary` (OI-61) (Q5) | 8 KB; questions past it named, never cut mid-question |
| `run_findings` (`run_id`, `module`) | A module's stored outcome: COMPLETED findings with the evidence refs they cite, BLOCKED with its refusal codes, holding; module prose labelled unapproved | `application/analysis_results.py:1152` (`stored_analysis`, as stored, judges nothing) | as `run_results` | 8 KB |
| `readiness` (none) | Readiness checks, the question outlook and the research-question trace **on the frozen working revision** | `ResearchRuns.outlook_working` (`application/research.py:1390`), as `GET …/research/readiness/working` reads it | B (`rule:design`) | 8 KB |
| `run_status` (`run_id`) | Status, steps with park codes, spend (spent, held, uncertain calls; unknown never zero), cost ceiling, selection receipt | `domain/spend_attribution.py:360` (`run_spend`) over the repository; `VIEW_COSTS` | B (`rule:design`, a study's own figures) | 4 KB |
| `changes_since` (none) | The working copy's edit-log rows and the ledger's decisions since the Lead's previous turn in this conversation, by item and person | `infrastructure/workspace_edit_repository.py:89` (`rows(after_revision=)`); `lead_digest`'s ledger read | B; a person named as the API already names them, never by e-mail | 6 KB |
| `knowledge_search` (`query`) | Ranked hits over the study's chosen knowledge: ref, page, the matching segment's first 300 characters | `lead-client-knowledge` §2: the project-memory matcher, word search only (ADR 0041 REV-0041-EMBED) | A; C for an internal document (`domain/material_rules.py:91-93`) | that plan's |
| `knowledge_read` (`ref`, `page`) | One page of a source or item, at most 8,000 bytes of whole segments with their locators; a proposal marked unapproved | that plan's §3: `reading_for_study`, `item_for_study`, pinned to the frozen index | as `knowledge_search` | 8 KB |

The knowledge tools keep LK3's limits inside a turn: at most 2 searches and 3 page reads (Q4).
Maps and report text join as rows when LO8's providers for them exist (E11). None is declared
before it exists, as `lead_workers.py` says of workers. A paid tool cannot be registered:
`ToolEffect` has no metered member (`ai_tools.py:105-117`), and this amendment keeps it so.

#### R3. The number rule, extended to what the turn read

Decision 3 says any number in the reply "must be one of the context's admitted claims". As built,
`lead_contract` allows a number the frozen context holds (`domain/research_lead.py:660-716`). After
this amendment, a number in the reply must come from the frozen context **or from a tool result
this turn recorded** (R6). The output tool's contract is built from both, with identifiers blanked
on both sides as today. A suppressed row carries no number to quote, and a number found only in the
external-context layer stays refused (LO8 DRL-11).

#### R4. The bound: USD 0.50 or 8 rounds, whichever comes first (Q2)

- **A round** is one model request: a tool round, the answer, or a schema repair. A turn makes at
  most **8**.
- **The turn's ceiling** is **USD 0.50**, all its rounds included. It is a deployment key with no
  default, `AIA_AI_RESEARCH_LEAD_TURN_CEILING_USD`, with `AIA_AI_RESEARCH_LEAD_MAX_ROUNDS` (8)
  beside it. Unset, the turn parks `research_lead_unconfigured`, as the Lead's keys do today.
- **The hold comes from the ceiling.** At the turn's start, the turn holds its ceiling against the
  study's budget. A ceiling that does not fit parks the turn `AWAITING_BUDGET`, as today. Each round
  takes its reservation from that hold and settles at its metered cost. The turn's hold replaces
  today's two-call reservation (`AIA_AI_RESEARCH_LEAD_RESERVATION_USD`).
- **Before each round**, code takes the spend settled so far, adds this round's worst case and the
  answer's worst case, and sends a tool-offering round only if the sum fits the ceiling. A worst case
  is the request's counted input (tokens once `lead-conversation#LC4` counts them, bytes until then)
  at the model's dearest input rate, plus the output cap at its output rate. **Unknown is never
  zero:** an unpriced model refuses the turn (`cost_ceiling_unknown`), and a round whose outcome is
  uncertain counts at its whole worst case.
- **At the bound** (the 8th round, or a round that would not leave the answer's worst case inside
  the ceiling), code sends the answer round. It offers the output tool alone, with the gateway's
  instruction to answer through it. The Lead answers with what it has and says what it did not read
  ("Nepřečetl jsem …", the honest "nevím" that ADR 0041 A5 scores). The validator refuses an answer
  at the bound that names no unread item while reads were refused or cut.
- **A repair counts.** A schema repair is a round against both the 8 and the USD 0.50. If the
  answer round has nothing left for its repair, it fails by name (`lead_turn_ceiling_reached`) and
  is never sent over the ceiling.
- **Parallel calls.** A round may carry at most 4 read calls. The knowledge limits (2 searches,
  3 reads a turn) hold inside the 8 rounds.
- **Off by default:** `AIA_AI_RESEARCH_LEAD_READS`, off in test and by default. Off, no read tool is
  offered and the request is byte for byte today's.

#### R5. What stays frozen at enqueue, and what is fetched

These stay frozen, as today, and hashed with the turn: the pinned prompt, the Lead's files and
notes, the stage's contract, the view and the message, the conversation and its digest, the design
at the turn's working revision, the knowledge index, the runs list and the Interpretation
candidates. The detail behind those ids is fetched in the turn.

A read is pinned to what was frozen wherever the thing can move:

- `readiness` computes on the frozen working revision, not a newer copy;
- `knowledge_read` refuses a reading that moved since the turn froze (`changed_since_turn`);
- a completed run's results do not move.

Live state (`run_status`, `changes_since`) is read at call time and recorded with its read time, and
the reply may say "k <time>". The always-in layers keep a one-line summary of each (the newest
run's state, readiness's verdict, the number of changes since the last turn), so the Lead knows what
to read.

#### R6. Every round and every read journaled; a retry replays

- **Rounds.** Each round's response (its blocks, reasoning included) is checkpointed the moment it
  returns. The key is the turn, the round and the SHA-256 of exactly what was sent, as the analysis
  step does (`analysis.py:17-20`). A retry replays every round it finds and never pays twice; a
  checkpoint whose bytes do not match is not replayed.
- **Reads.** Each read is journaled in the same transaction as its round's checkpoint: tool, version,
  arguments, the result as sent, `args_fingerprint` and `result_fingerprint`
  (`ai_tools.py:175-186`), class and read time. A retry **replays the recorded result** and never
  reads again, so the answer is checked against exactly what the model was shown.
- **Reasoning blocks are kept now.** They used to be discarded (`bedrock.py:33`). They are kept in
  the journal under the turn's class, read only to replay the turn, shown to no one, and erased with
  the turn (`study_lead_repository.py` `erase_member_turns`, `erase_client_lead_turns`).
- **The manifest.** The turn's manifest (ADR 0041 decision 3, LC1/LC2) gains a `reads` section: per
  read, its tool, the ids it returned and left out, its bytes and class, and the rounds and spend
  against the ceiling. "Co Vedoucí vidí" shows it, and LK6's "Přečteno: …" line is that section on
  screen.
- **The class.** The turn's class is the most restrictive of the frozen context and every result so
  far, judged again by the gateway before each round. A read that would raise the class past the
  route's approval is refused before the round is sent, never sent under a lower class (ADR 0008).

#### R7. Paid work: the workers as tool definitions, never called in the turn (Q1)

The Lead's `request` stays one of three things: a card (decision 7, *Accepted with* 4 and 8), a plan
step (ADR 0028 decision 4) or a person's typed command (ADR 0028 decision 3). What changes is where
its shape comes from:

- Each `LeadWorkerSpec` row (`domain/lead_workers.py:88-128`) generates one request definition in
  the output tool's schema. Its arguments, description, card kind and the ceiling key it is priced
  from are read from the row, so the Lead picks a worker by schema rather than from a hand-written
  class per kind (`domain/research_lead.py:340-394`).
- A worker added as a row is offered to the Lead without new contract code. A worker switched off
  is not offered.
- These definitions are part of the output, never callable tools. Choosing one prepares a card and
  calls nothing: a person approves the card (or approved the plan), the job runs durably with its
  lease, checkpoints and reservation, and its result returns as a continuation turn (LO6), which may
  then read through R2.
- The workers' system prompts stay what they are (ADR 0020): the inside of each worker, edited by
  the methodologist.

#### R8. Text read is data, never instructions

A `toolResult` is data. Knowledge text keeps the instruction screen that ADR 0040 decision 6 names,
and its hits are named in the result. Whatever a read returns, the Lead's output stays closed: an
edit is a proposal, paid work is a card, and nothing a result says can approve, spend or start.

### Build

The work is ordered, and each chunk ships with a test that failed before it:

1. **G1, contracts:** content blocks, `TOOL_ROUND`, tool calls and reasoning on `ModelResult`; the
   golden request bodies of every existing caller unchanged.
2. **G2, recorded Converse fixtures first:** the tool-use wire as Bedrock answers it for the Lead's
   model (several `toolUse` blocks, reasoning with signature, a redacted reasoning block, an answer
   in text instead of the tool), captured once on develop's Lead route with fictional content, at
   most 10 requests and under USD 1, on the product owner's word for that capture. Then the Bedrock
   adapter against those fixtures.
3. **G3, gateway and caller:** a round per call in the ledger, the gates run before every round,
   the turn's ceiling and round cap, the round checkpoints and the read journal, replay.
4. **G4, the read tools and the product `ToolRegistry`:** R2's seven tools with their providers,
   the import contract, the manifest's `reads` section.
5. **G5, the workers as definitions** (R7), from `WorkerRegistry`.
6. **G6, measured and switched on:** cost and latency per round on recorded turns, then on a
   fictional develop study, stated before the switch goes on (CLAUDE.md § 8).

**What it costs to build** is an estimate, not a measurement. G1-G3 touch the one model call path
that every paid step uses, about 1,500-2,500 lines with tests over three or four PRs. G4-G5 are
about 1,000-1,500 lines over two PRs. Fixtures and the CI suites cost nothing; the one capture in G2
costs under USD 1. The code-run round over today's gateway (the earlier draft's option) would have
skipped G1-G3 and saved roughly half of that work. The owner chose native tool use first (Q3).

### Costs per turn

Measured on develop, 2026-10-28: one Lead turn on Sonnet 5.5 took 23,918 input and 570 output tokens
and cost USD 0.0589. That turn is consistent with USD 2.20 per million input tokens and USD 11.00
per million output tokens, if output costs five times input. The real prices are in Parameter
Store, not the repository, so everything below is an estimate on those inferred prices and is
unmeasured.

Each round resends the whole conversation so far: the frozen context, every earlier call and
result, and the reasoning. If a round adds about 2,500 tokens of results and about 600 tokens of
output and reasoning:

| Rounds (uncached) | Input tokens, all rounds | Cost (est.) |
|---|---|---|
| 1, a turn that reads nothing (today) | 23,918 | USD 0.059 (measured) |
| 2: one read round and the answer | ~50,000 | ~USD 0.12 |
| 4 | ~112,000 | ~USD 0.27 |
| 6 | ~190,000 | ~USD 0.46 |
| 7 | ~232,000 | ~USD 0.56: over the ceiling |
| 8 | ~278,000 | ~USD 0.67: over the ceiling |

- **Without prompt caching, the USD 0.50 binds first,** at about six rounds (five read rounds and the
  answer). The worst-case check of R4 stops earlier still while worst cases are counted in bytes
  rather than tokens, since bytes overstate tokens: about four rounds.
- **With prompt caching** of the restated prefix (ADR 0041 A1, `lead-conversation#LC4`), a round
  pays the cache-read rate on what it repeats, and the 8-round cap binds first. Its saving is
  unmeasured until LC4.
- **The comparison:** a frozen results layer at ADR 0041's 16 KB ceiling, about 5,500 tokens, costs
  about USD 0.012 on every turn, asked or not. A turn that reads once costs about as much as five
  turns carrying that layer. Most turns are about the design and read nothing.
- **Money held:** USD 0.50 a turn while it runs, below today's develop reservation of USD 1.02
  (`deploy/develop/docker-compose.yml:282`; `deploy/develop/README.md:685-693`).
- **Latency:** each round adds one model answer and the reads, which are database reads with no
  network and no queue hop. Measured in G6.

### Alternatives considered

- **Frozen layers only** (today, and LO8 as planned). Deterministic and one call a turn, but every
  turn pays for results nobody asked about, a 16 KB layer still cannot hold a large run, and the
  Lead says "nevím" about the rest. Kept as the always-in summary (R5), not as the only source.
- **A code-run round over today's gateway** (a `read` field in the closed output, code fetching,
  the next request built by code: the earlier draft, and ADR 0041 A3's shape). It costs less to
  build. It was rejected by the owner's Q3 for native tool use: the model interleaves reasoning and
  reads as it was trained to, and parallel calls come without a field AIA invents.
- **Synchronous paid tools** (the Lead starts a design job, a run or Deep Research inside its turn).
  Rejected:
  - a paid start needs a person's approval or an approved plan with its ceiling shown (this ADR's
    decision 7, ADR 0028), a lease, checkpoints and never paying twice;
  - a turn cannot wait minutes for a run;
  - a model's call is not a person's approval.
- **A full agent loop without a bound.** Rejected: the hold and the ceiling need a known maximum.
  Each round resends the growing context, a turn could loop without stopping, and the journal and
  its hold must stay bounded. Hence R4.
- **A read as a continuation turn** (the Lead asks, the turn ends, the next turn answers, as ADR
  0040's lookup does). That is two turns, a queue hop and a re-frozen context for a free database
  read. Kept for what is paid or external, where the job boundary earns its cost.

### Consequences

- The gateway carries a tool conversation for the first time. Its contracts, adapter, ledger and
  fingerprints change for this one caller; every other caller's bytes stay as they are, held by
  their golden tests.
- Reasoning blocks are stored for the first time, under the turn's class, and erased with the turn.
- The first constructed `ToolRegistry` in the product, with seven tools, each with a test file.
- LO8 is built as providers for the read tools plus a small always-in index, not as one large frozen
  layer.
- A Lead answer about results can cite every admitted number of a run, and never a suppressed one.
- A worker added to `WorkerRegistry` reaches the Lead's output schema without new contract code.

### What enforces it

- `ToolEffect` has no paid member, and the read tools are registered only with
  `READS_STUDY_DATA`. An import contract keeps the read-tool module from importing a start, enqueue,
  reservation or ledger-write entry point.
- Tests, each failing before the change:
  - every existing caller's request body is byte-identical (the golden bodies);
  - a recorded Converse tool-use exchange round-trips: every `toolUse` kept in order, reasoning and
    redacted reasoning sent back untouched;
  - an argument naming a run, question or ref not in the frozen context is refused `not_in_context`;
    an argument carrying a study, client or organization is refused `scope_in_model_arguments`;
  - `run_results` returns no number for a suppressed row and no row for a refused question;
  - a reply number found only in a recorded tool result of this turn passes; one in no result and
    not in the context is refused; one only in the external layer is refused;
  - an output call beside a read call is not applied;
  - the 8th round offers the output tool alone; a round that would leave the answer's worst case
    outside USD 0.50 is not sent, the answer is, and it names what it did not read;
  - a repair counts against both bounds; an unpriced model refuses the turn; an uncertain round
    counts at its worst case;
  - a turn whose ceiling does not fit the budget parks before any round;
  - a retry after round 3 replays rounds 1-3 and every read from the journal, sends the rest, and
    reads nothing again;
  - the gates run before every round: a read result that raises the class past the route's approval
    stops the next round unsent; a panel-derived run's results reach no route but
    `bedrock-eu-primary`;
  - erasing a member's turns erases their reasoning blocks and reads;
  - switched off, no tool is offered and the request is byte-identical to today's;
  - every `LeadWorkerSpec` row yields one request definition, and a switched-off worker yields none.

### Open for Nigel

The five questions are answered (Status, above). Left for him:

1. **Acceptance** of the amendment as a whole.
2. **G2's capture:** up to 10 requests on develop's Lead route with fictional content, under USD 1,
   to record the Converse tool-use wire the fixtures are cut from. (a) Yes, when G2 starts —
   *recommended*; (b) build from the provider's documentation alone, recording on the first live
   turn.

### Doc follow-up

For the docs PR after acceptance; no other shared document is edited here.

- **`docs/architecture/adr/README.md`:** ADR 0026's line notes "Amendment 2026-10-28: native read
  tools in a turn, USD 0.50 or 8 rounds; paid work stays a job".
- **ADR 0041:** the *Leaves unchanged* line's "the Lead calls no tool" reads "the Lead calls no paid
  or external tool (ADR 0026 Amendment 2026-10-28)". A3's round is replaced by that amendment's R4
  bound.
- **`docs/architecture/ai-runtime.md` and `ai-step-executor-contract.md`:** content blocks, the
  `TOOL_ROUND` purpose, the turn's ceiling, reasoning blocks kept for replay.
- **`.planning/plans/lead-orchestration.md`** (owned by the E07 session now; text proposed, not
  applied):
  - **LO7** becomes: "The Lead's always-in state summary (one line each: readiness verdict,
    question-outlook counts, each run's state with park code, changes since the last turn) frozen
    per ADR 0026 decision 2; the detail through the read tools `readiness`, `run_status` and
    `changes_since` (ADR 0026 Amendment 2026-10-28 R2). Test: 'Kde jsme?' answered from the summary
    with no read; 'Proč běh stojí?' answered after one `run_status` read, its park code cited."
  - **LO8** becomes: "`ResultsContext` as providers for the read tools `run_results` and
    `run_findings` (admitted rows only, suppressed refs with reason codes and no number), plus a
    frozen index of the newest run (question ids with their status, modules with their state, maps
    with their register status, no number); type, `MaterialRule` for results (B, raised to A when
    the analysis input carries client data, the lineage declared: Q5), bound per read, the L slot
    unchanged. The read-tool decision against ADR 0026 decision 3 is taken by its Amendment
    2026-10-28. Test: 'Shrň mi, co běh zjistil' is answered with admitted numbers cited by ref
    after one read, a suppressed row named without its number."
  - **LO6:** a continuation turn may read through R2 like any turn.
  - **New LO8a-LO8f** = the amendment's G1-G6, behind `AIA_AI_RESEARCH_LEAD_READS` (off by default,
    off in test), G1-G3 before LO8's providers are wired.
- **`.planning/mvp-execution-contracts.md` E11:** append "the bounded ResultsContext is served
  through the Lead's read tools (ADR 0026 Amendment 2026-10-28); a frozen results layer is only its
  index; it depends on G1-G3".
- **`.planning/plans/lead-client-knowledge.md`:** LK1's "ADR 0042 … amends ADR 0026 decision 3"
  becomes "ADR 0026 Amendment 2026-10-28 (R2's knowledge tools; ADR 0042 folded in, Q4)". LK3's
  `LeadOutput.search` / `.read` fields become the `knowledge_search` / `knowledge_read` tools with
  the same limits, and LK4's round runs on G3.
- **`.planning/plans/research-lead-workbench.md` 11:** the command registry's worker rows also yield
  the Lead's request definitions (R7).
- **`CLAUDE.md` § 2**, when built: `aia_executors/research_lead.py`'s "one STUDY_LEAD request and one
  repair" becomes "a native tool conversation of at most 8 rounds and USD 0.50, behind
  `AIA_AI_RESEARCH_LEAD_READS`"; the Bedrock adapter line notes several tools and reasoning kept for
  replay.
