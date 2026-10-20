# ADR 0028 — The Lead orchestrates inside a wallet: a plan approved once, a typed start a person asks for, and every uncovered gate parks

**Status:** Proposed — 2026-10-20. Not accepted until the product owner says so. **Supersedes**
MVP-13 ("a paid worker job is approved one card at a time", `overview.md`). **Amends**
[ADR 0026](0026-research-lead-proposes-a-person-decides.md) decision 7 and *Accepted with* 4 (a
job the Lead prepares inside an approved plan starts without its own card; a run, Design Research
and Interpretation Research may be plan steps). **Builds on** [ADR 0019](0019-two-roles-and-human-ai-gates.md)
(gates only between a person and the AI; the worker holds no gate authority) and ADR 0002 (the
ledger and the queue are PostgreSQL). **Leaves unchanged** `budget_usd` as the cap that stops
spending, `spend_confirm_usd` as a per-start confirmation threshold, every evidence gate and every
run's pins.
**Date:** 2026-10-20. **Amended 2026-10-20** with the product owner's recorded answers D-01 to D-05
and D-08 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, #523 @ `ee21982`); still Proposed.
**Plan:** [lead-orchestration](../../../.planning/plans/lead-orchestration.md) LO0-LO5, LO10, LO15, LO16

**Terminology** (the product owner, 2026-10-20). The per-study spending allowance is the **wallet**
in code and plans (`study_wallets`, `study_wallet_raises`, `study_wallet_charges`,
`clients.wallet_ceiling_usd`, "wallet cap") and **Peněženka** on screen. Earlier documents call it
the *envelope*; the two words mean the same thing. `budget_usd` (the hard budget) and
`spend_confirm_usd` (the confirmation threshold) keep their names. The four money numbers' Czech
names (the product owner, 2026-10-20, D-01): *Rozpočet klienta* (`clients.budget_usd`), *Rozpočet
studie* (`budget_usd`, renaming today's "Strop rozpočtu"), *Peněženka* (the wallet) and *Práh
potvrzení* (`spend_confirm_usd`).

## Context

The owner decided on 2026-10-19 (F13, Q14, Q25; `mvp-cohesion.md`) that a researcher sets a
per-study wallet for paid work, approves a Lead's plan once and lets its steps run, and that a
person's own request in the conversation starts a run inside the wallet without a plan card. A
Lead-initiated start still needs an approved plan. Three facts of the code make this an
architectural change, not a screen:

- **Every paid start is a person's call today.** `WORKER_PERMISSIONS` withholds `APPROVE_GATE`
  (`packages/aia_core/src/aia_core/domain/scope.py:202-213 @ 854c209`), and a worker's context is
  issued only against a held lease (`application/scope.py:289-343 @ 854c209`). Nothing can start a
  job on a person's standing authority.
- **The spend confirmation is a function argument.** `ResearchRuns.start` takes
  `confirm_cost_usd` (`application/research.py:479-488 @ 854c209`) and accepts the start when it
  covers the ceiling (`:739`). Any caller that can reach `start` can pass it, so "the plan holds no
  `APPROVE_GATE`" would not, on its own, stop a plan step from confirming its own spend.
- **The agent job path ignores the threshold.** `ResearchAgentJobs.start` and `rebuild`
  (`research.py:1311, 1514 @ 854c209`) read no `spend_confirm_usd`; the only check on a design job
  is in the Lead's approve path (`application/research_lead.py:678-700 @ 854c209`). The cap
  itself is enforced at reservation (`infrastructure/workflow_repository.py:1240-1244 @ 854c209`).

## Decision

### 1. Three amounts, one precedence

| Amount | Is | Set by | On screen |
|---|---|---|---|
| `studies.budget_usd` | The hard cap: a reservation that does not fit parks `AWAITING_BUDGET` (unchanged) | a member (ADR 0019) | *Rozpočet studie* |
| `study_wallets.cap_usd` | What paid work may be started **without a further card**, a slice of `budget_usd` | the researcher, up to the ceiling | *Peněženka* |
| `studies.spend_confirm_usd` | A per-start confirmation threshold; null never asks (unchanged) | a member | *Práh potvrzení* |

`clients.wallet_ceiling_usd` (nullable, set only by an organization OWNER or ADMIN) bounds every
open wallet of the client's studies; null means a wallet may not exceed the study's `budget_usd`.
**Precedence:** the budget stops spending; the wallet decides what may start without a card; the
threshold decides what asks again. A wallet never raises the budget, and the threshold is never
called a hard stop. A client's own paid work (source proposals, `clients.budget_usd`) is outside
every wallet: the exception the owner settled (MVPQ-08, LO13).

### 2. The wallet's ledger: charges by ceiling, under the study lock

- `study_wallets`: one open wallet per study (a partial unique index `WHERE closed_at IS NULL`), no
  expiry; it closes with the study.
- `study_wallet_raises`: insert-once, `from_cap_usd`, `to_cap_usd`, `raised_by`. A raise inside the
  ceiling is the researcher's act and writes a ledger row (`subject_type = "wallet"`). **A raise
  above the client's ceiling is refused**; only an OWNER or ADMIN raising the ceiling itself lets a
  wallet grow past it (the product owner, 2026-10-20, D-03). The refusal names who can raise the
  ceiling.
- `study_wallet_charges`: insert-once, one per started run, `ceiling_usd`, the `plan_id` or none,
  and the `approval_decisions` row that authorised it.

Remaining is `cap_usd` minus the sum of the charges' `ceiling_usd`, computed under the study row
lock in the transaction that starts the run. **An unknown ceiling is a refusal**
(`CostCeilingUnknown`, as `research.py:735-737 @ 854c209`), never a zero charge. Settled spend is
read from the usage ledger for display only. `StudyWalletRepository` is the only reader and writer
of the three tables.

### 3. One typed start, and nothing reaches the confirming path from a model or a plan

`start_run` becomes a typed command (ADR 0026 decision 4's registry) with **no `confirm_cost_usd`
field**: its input is the Design Revision id, the persona source, the population child and the
answerability acknowledgement, each explicit, never "the latest". It has three callers:

| Caller | Authority | Ledger | Threshold reached |
|---|---|---|---|
| the Run stage's button | the person's `APPROVE_GATE` | `spend` when confirmed (today's) | asks, as today |
| a person's typed request in the composer (`chat_start`) | the person's `APPROVE_GATE`, matched by the server | `chat_start` | asks the person in the same exchange |
| a plan step | the plan authority (decision 4) | `plan_step` | covered by the plan's approval for the ceiling the card showed; **parks** if the ceiling grew (D-02) |

**The security condition.** A by-request start is authorised by a typed command the web sends
from the composer's quick action, naming the revision it starts. The server executes it directly.
Free text is never a start: it goes to the Lead, which can only prepare a card. A model's reading
of a message ("the person asked") is not authority, because anything the Lead read (a client
document, a captured source, a pasted brief) can carry instructions. The confirmation of a
threshold comes only from a person's act: their own request, or their approval of a plan card that
showed the ceiling (decision 4). A plan step reads the confirmation that approval recorded; it can
never create one, and a model output or a worker never supplies one; an import contract forbids `aia_executors` and the plan step from importing the confirming
service entry point.

### 4. The plan authority: issued by `ScopeResolver`, can start what a frozen step names, cannot approve

A Lead turn may return a plan: at most twelve typed steps (`agent_job`, `research_run`,
`deep_research`, `interpretation_research`), each with its own ceiling, frozen at proposal with the
Design Revision and working revision it was prepared on (`lead_plans`, `lead_plan_steps`). A
person approves it once (`APPROVE_GATE`, one ledger row `lead_plan`). Approval needs the whole
plan's ceiling to fit the wallet's remaining; it does not reserve it. **The approval records a
confirmation for each step's ceiling the card showed** (the product owner, 2026-10-20, D-02): a step
whose run reaches `spend_confirm_usd` at that ceiling or below starts without asking again, because
the person saw it on the card; the card shows each ceiling against the threshold.

An approved plan runs as a workflow of a new closed type, `lead_plan`, one `lead_plan_step` per
step, each depending on the previous. The step's executor asks `ScopeResolver` for a **plan
authority**: issued only against a held lease **and** an `APPROVED` plan row of the same study,
naming exactly one frozen step. It holds `RUN_WORKFLOW` and the right to call `start_run` (or the
step's own start) with that step's frozen inputs, and nothing else: no `APPROVE_GATE`, no
`APPROVE_BUDGET`, no threshold confirmation, no other study.

**A step parks** (`AWAITING_GATE`, the existing state for "a person owes us a decision", `domain/workflow.py:110, 184 @ 854c209`, its reason named) and shows a card when it meets anything its
approval did not cover:

- its ceiling does not fit the wallet's remaining, or the ceiling is unknown;
- the run's ceiling **grew** since the card was shown and reaches `spend_confirm_usd` (D-02);
- a budget lift, a report approval, a Sociomap unlock, a readiness or answerability failure;
- the step would start from the working copy, and the working copy or head Design Revision moved
  since the plan was prepared (decision 5).

A parked step is never skipped and never retried around the gate; the person's act resumes or stops
it (`…/stop`, `STOPPED` with the reason).

### 5. A plan is bound to the revision on its card

`approve_request` today submits whatever the working copy is at approval time (LO10). Approving a
plan names the plan's `design_revision_id` and `workspace_revision`; a mismatch is refused
`409 stale_plan`, never approved on content the person did not see.

**When the design moves while a plan runs** (the product owner, 2026-10-20, D-04): the steps already
tied to the plan's immutable Design Revision finish on it. A run executes one immutable revision
(ADR 0016), so finishing it is safe, and stopping it would waste paid fieldwork. Only a step that
would start from the working copy stops, `STOPPED` with the reason; a new plan uses the new design.
A step never starts on a revision other than the one frozen in it.

### 6. Off by default

`AIA_LEAD_PLANS_ENABLED` (off by default, off in test) gates plan approval and the `lead_plan_step`
executor. Off, the wallet still exists and every paid job is a card again (MVP-13's behaviour, the
fallback). `chat_start` needs only the wallet.

## Alternatives considered

- **Keep MVP-13, one card per job.** The owner superseded it; it is the fallback when the switch is
  off.
- **Give the worker `APPROVE_GATE` while a plan runs.** It would let any executor in the process
  approve anything; the capability must be narrower than a person's.
- **Let the Lead's reading of a message count as the person's request.** Rejected: prompt injection
  from any text the Lead has read becomes a spend.
- **Charge the wallet by settled spend.** A start would be judged by what earlier runs happened to
  cost, so concurrent starts could exceed the cap; by ceiling, a start never can.
- **Park every step whose run reaches the threshold, even one the card showed** (this ADR's draft).
  Rejected by the owner (D-02): it asks twice for a number already on the card.
- **Stop the whole plan when the design moves** (this ADR's draft). Rejected by the owner (D-04):
  it wastes paid fieldwork on a run that executes an immutable revision anyway.
- **An approver for a wallet raise above the client's ceiling** (LO1's test). Rejected by the owner
  (D-03): with about ten users, a queue nobody watches is worse than a refusal naming who can raise
  the ceiling.
- **Reserve the plan's whole ceiling at approval.** Simpler accounting, but it would lock the
  wallet for steps that may never run; each step charges when it starts.

## Consequences

- **New:** four tables (M4, M5), one workflow type, one step kind, one capability, three ledger
  subjects (`wallet`, `lead_plan`, `plan_step`, `chat_start` in M3, the lane's first migration), a
  typed command, and the LO15 fix in `ResearchAgentJobs.start` and `rebuild`.
- **Risk:** the plan authority is a new kind of capability and the riskiest piece of the MVP. It
  gets a kill switch and the most negative tests.
- **Cost:** a wallet is one more number on screen; the header shows two meters (budget spent, wallet
  remaining) and the threshold on click (Q20).

## What enforces it

- `ScopeResolver` is the only issuer of the plan authority; `make layer_check` forbids constructing
  it elsewhere and the authority's permission set is asserted to exclude `APPROVE_GATE`.
- An import contract (`[tool.importlinter]`): `aia_executors` and the `lead_plan_step` executor do
  not import the confirming start entry point; the API never starts a plan step.
- `StudyWalletRepository` is the only writer of the wallet tables (`layer_check`).
- Tests: concurrent starts never exceed the cap; an unknown ceiling is refused; a step whose
  ceiling the card showed starts above the threshold without asking again, and one whose ceiling
  grew parks; a raise above the client's ceiling is refused by name; a design move lets a step tied
  to the frozen revision finish and stops a step that would start from the working copy; a stale plan is refused at approval; a direct HTTP start and rebuild above the
  threshold without a confirmation are refused (LO15); a `chat_start` built from free text is
  refused; the plan authority cannot reach another study.

## Unblocks

`lead-orchestration` LO1-LO5, LO10 (W1 plan code), LO15 and LO16 (W0), M3, M4 and M5; gate I-1.

## Open for Nigel

Answered by the product owner on 2026-10-20 (`answers-2026-10-20.md`, #523 @ `ee21982`), and
written into the decisions above:

1. ~~Does a plan's approval cover the threshold?~~ Yes, for each step's ceiling the card showed; a
   grown ceiling parks (D-02, b). Decision 4.
2. ~~A raise above the client's ceiling.~~ Refused; only raising the ceiling lets a wallet grow
   (D-03, a). Decision 2.
3. ~~A plan stops on any revision move.~~ No: steps tied to the immutable revision finish; only a
   step that would start from the working copy stops (D-04, b). Decision 5.
4. ~~Deep Research inside the wallet.~~ Charge its ceiling, reconcile its tool spend after M11
   (D-05, a), as decision 2 and this item already said.
5. ~~Amending ADR 0026, which is Accepted.~~ Yes, to each amendment as its ADR is accepted (D-08, a).

Nothing remains open in this ADR but its acceptance.
