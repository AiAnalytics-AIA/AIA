---
status: in-progress
chunks:
  - "[x] 1. ADR 0019: two roles, no cross-approval, the human-with-AI gate catalogue (supersedes ADR 0004's grant rules and ADR 0015 decisions 6-7)"
  - "[x] 2. Domain: one Researcher permission set; self-approval allowed by default; REVIEWER and LEAD gone"
  - "[x] 3. ScopeResolver: every active member sees every client and study of the organization"
  - "[ ] 4. Admin: system settings only for ADMIN; MEMBER is the Researcher; settings document and web client"
  - "[x] 5a. Human-authored Knowledge writes directly (client workspace); a study's proposal still waits for a person, who may be its proposer"
  - "[ ] 5b. Gates (design proposed below, awaiting the owner): split into 5b.1 to 5b.4"
  - "[ ] 5b.1 A person can lift a budget wait and the run goes on (today it is a dead end)"
  - "[ ] 5b.2 Confirm the cost of a run above a threshold, recorded"
  - "[ ] 5b.3 One ledger entry for every acceptance of an AI proposal"
  - "[ ] 5b.4 Client-facing release (blocked: the client-facing report contract does not exist)"
  - "[ ] 6. Retire the grants (tables, routes, UI) after one deploy without them"
---
# Two roles, human-with-AI gates

**Status:** planned · **Drafted:** 2026-10-01 · **Branch:** `feature/two-roles-human-ai-gates`
from `develop` @ `2de4093` (not created yet)

## Decision (the owner, in conversation, 2026-10-01)

1. **Two roles.** *Researcher* holds every permission. *Admin* holds everything a Researcher
   holds, plus the system settings.
2. **Every Researcher sees every client in the organization.** No client or study grants.
3. **No approval between people.** Uploading sources, editing, running and writing Knowledge need
   no one's approval. The only approval is a person accepting what the AI produced, at the gates
   AIA defines.

## What exists now (anchors, `2de4093`)

- Scope roles `VIEWER / REVIEWER / RESEARCHER / LEAD` and their permissions:
  `packages/aia_core/src/aia_core/domain/scope.py:124-216`; client permissions `scope.py:241-287`.
- Independent review as the default: `DEFAULT_SELF_APPROVAL_ALLOWED = False` (`scope.py:327`),
  `require_approval_independence` (`scope.py:433-471`), resolved per organization / client / study
  in `ScopeResolver.study_context` and `client_context`
  (`application/scope.py:192-316`, `:387-468`).
- Where it bites: gates `infrastructure/workflow_repository.py:1921-1928`; deliverable sign-off
  `infrastructure/artifact_repository.py:528-545`; Knowledge, where the proposer may not decide
  their own proposal `infrastructure/client_knowledge_repository.py:360-364`.
- Access by grant: `ScopeResolver.accessible_clients` / `accessible_studies`
  (`application/scope.py:469-536`); no grant means 404 (`reason="no_grant"`).
- Organization roles `OWNER / ADMIN / MEMBER`; `is_admin` is OWNER or ADMIN
  (`scope.py:644`, `:875`). The settings routes already gate on the admin context
  (`apps/api/src/aia_api/routers/settings.py:467-502`).
- `UPLOAD_DATA` is a plain permission, not an approval; nothing to remove there.

## Target

| Role | Is | Holds |
|---|---|---|
| Researcher | `OrganizationRole.MEMBER` | every permission on every client and study of the organization |
| Admin | `OrganizationRole.ADMIN` (OWNER kept as the first Admin, or retired) | Researcher, plus system settings and user administration |

What does **not** change, because it is not approval:

- The organization is the tenant boundary. A person outside it, or an inactive user, gets the same
  404. Archived clients stay invisible.
- A model, tool argument or request body never sets scope, a role or a policy
  (`domain/ai_tools.py`; ADR 0008). The AI acts under the signed-in person.
- The worker's context stays narrower than a person's: issued only against a held lease, never
  able to accept a gate (`application/scope.py:317-386`).
- Residency, data class, the licence gate (OI-61) and cost reservation.

## The gate catalogue (to be fixed in chunk 1)

A gate is a person accepting something the AI produced. Proposed set, nothing else gates:

1. **Apply an AI proposal** -- design, context and Knowledge proposals; chatbot-proposed actions.
2. **Spend** -- start a run above a threshold, shown with its cost.
3. **Client-facing release** -- export a deliverable containing AI-produced content.

Not gates: uploads, human edits, human-authored Knowledge, runs under budget.

Every accept keeps `approver_user_id` and `self_approved` (`scope.py:401-409`), so "who accepted
this" is still answerable. Self-approval stays a setting, not a hard-wired rule, so one client
that demands independent review can turn it back on.

## Chunks

1. **ADR.** `docs/architecture/adr/0019-two-roles-and-human-ai-gates.md` supersedes the grant
   rules of ADR 0004 (admins get no implicit access; a study grant overrides a client grant; a
   reviewer cannot edit), decisions 6 and 7 of ADR 0015, and the separation-of-duties default.
   ADR 0004 rules 1 and 2 stand. The ADR index is a shared file: its line goes under Doc
   follow-up, not in this PR.
2. **Domain.** One permission set for Researcher. Default of self-approval flips to allowed.
   Remove `REVIEWER` and `LEAD` and the client-level permission split that existed for them. The
   tests that assert refusal are rewritten to assert the new rule; none is skipped or loosened.
3. **Scope resolution.** `study_context`, `client_context`, `accessible_clients`,
   `accessible_studies` drop the grant lookup: membership of the organization is the access.
   The `ACCESS_DENIED / no_grant` audit entry disappears; a cross-organization probe still 404s.
4. **Admin and settings.** MEMBER is Researcher, ADMIN adds the system settings. The settings
   document stops listing four scope roles; the web client stops offering role pickers.
5. **Gates.** Wire the three gates; human-authored Knowledge writes a revision directly with its
   author recorded; AI-authored Knowledge still goes through a proposal and an accept.
   - **5a (landed).** `ClientKnowledgeRepository.add` is the person's write: it records an already-approved
     proposal row (no migration, same lineage) and `POST /clients/{id}/knowledge/proposals` calls it.
     The study route `/studies/{id}/knowledge-proposals` is unchanged and its proposals wait for an
     accept; the Pending tab no longer hides Accept from the proposer. Where self-approval is
     explicitly off, `add` files an ordinary proposal, so a client that asked for independent review
     keeps it. Owner, 2026-10-02: knowledge from deep research stays AI-authored and is accepted by a person.
6. **Retire grants.** After one deploy with chunk 3 live: drop the grant tables, routes, UI and
   the per-level `allow_self_approval` columns in one migration.

## Trade-offs accepted

- **No client isolation inside the organization.** Anyone in the organization can open any client's
  workspace and Knowledge. Reversing this later means reintroducing grants and deciding who holds
  which, with data from several clients already in one pool. The organization stays the boundary.
- **One person can produce and release a deliverable.** The audit trail records it; nothing stops it.
- **Admin is only more settings.** Nothing stops an Admin from also being a Researcher, which is
  the point, but there is then no role that can administer without being able to read client data
  (the property `OrganizationRole`'s docstring claims, `scope.py:108-116`). That claim is retired.

## Open

- Human-authored Knowledge writes a revision directly; only AI-authored changes go through a
  proposal and an accept (**confirmed by the owner, 2026-10-01**).
- The spend threshold for gate 2 is a number someone must choose.
- Class A/B transmission is unchanged and still unapproved (ADR 0010). Widening who can see a
  client does not widen what may be sent to a model.

## Chunk 3 (landed)

`ScopeResolver` stops reading grants. `study_context` and `client_context` issue the one Researcher
role to any active member of the organization; `accessible_clients` lists every unarchived client of
it and `accessible_studies` every study of it (optionally one client's). The organization is still
the boundary: a study or client of another organization, an unknown id, an archived client and an
inactive user all return 404, as before. The `ACCESS_DENIED / no_grant` audit entry is gone. The
grant tables, routes and `grant_*` repository methods are untouched and now inert, so the change can
be rolled back by reverting the resolver; chunk 6 removes them.

**Archived clients stay invisible in listings (review finding, fixed in this chunk).**
`accessible_studies` did not exclude the studies of an archived client, before this chunk or after
it (`application/scope.py` @ 599fe95: the old queries joined only the grant tables). With grants that
reached only the people granted; with membership as the access it reached every member through
`GET /studies`, while `study_context` and `client_context` refused the same client. It now joins
`ClientRow` and drops archived clients. Tests that would have caught it:
`test_an_archived_clients_studies_drop_out_of_every_listing` and
`test_an_archived_clients_studies_are_not_in_the_portfolio_listing`.

**Tests rewritten, none skipped.** 69 tests asserted the grant rule (core 33, API 34, executors 2).
Each was rewritten to assert the new rule, or to keep testing a boundary that still exists: a run,
project, attachment, design or artifact is found only through the study the path names; knowledge is
read under the client whose context it was issued for; a `ClientContext` of another client's path
returns that client's rows only; respondent rows are still never inlined. Counts after: core 3,105
passed / 203 skipped (unchanged), API 267 (unchanged), worker 50, executors 137 (+1: the migration
CLI now has both a "left waiting" case, a closed study, and an "owner migrates" case).

**Trade-off, stated once.** Any member can read and change any client's data, and the only
isolation left is the organization. That is the owner's decision (ADR 0019 decision 2), reconfirmed
on 2026-10-02: the software is only for AIA's internal use. No second-organization test was added for
that reason; the existing `test_principal_from_another_organization_is_denied` and the
organization filters in every query stay.

**Not done here.** `docs/architecture/scope-and-authorization.md` carries a status note and is
rewritten in chunk 6; the web client still shows `your_role` and a role picker (chunk 4).

## Chunk 5b design (proposed 2026-10-02, awaiting the owner)

Status of what ADR 0019 decision 4 calls the three gates, read against `develop` @ 78c5b9e. The ADR
fixes **what** the gates are; this section is **how**, using what the engine already has, and
asks for three decisions. Nothing here is built.

### What exists

| Gate | Already there | Missing |
|---|---|---|
| 1. Apply an AI proposal | A design proposal is a job; **nothing is written until a person accepts it**: `ResearchAgentJobs.accept` needs `EDIT_STUDY`, an open study and an unchanged baseline revision, then writes a new Design Revision (`application/research.py:358`). A study's Knowledge finding is a proposal that a person decides (`ClientKnowledgeRepository.decide`). | The accepts are recorded in different places. The append-only `approval_decisions` ledger is written by `decide_gate` and by `ArtifactRepository.approve` (`artifact_repository.py:555`) only; a design accept and a Knowledge decision do not write it, so "who accepted what the AI produced" has no single answer. |
| 2. Spend | A **hard cap**: `reserve_budget` refuses a call that would pass the study budget and the step parks as `AWAITING_BUDGET` (`infrastructure/workflow_repository.py:995`, `domain/workflow.py:570`). `APPROVE_BUDGET` and `MANAGE_STUDY_BUDGET` exist and a Researcher holds both. | (a) **A budget wait cannot be lifted** (finding below). (b) There is no cost shown or confirmed before a run starts: cost exists only per call (`estimated_cost_usd` on an attempt, the gateway's ceiling). |
| 3. Client-facing release | `ArtifactRepository.approve` (`SIGN_OFF_DELIVERABLE`) and `download_url` (`EXPORT_DELIVERABLE`); a report carries `review_state` `DRAFT_UNAPPROVED` / `APPROVED_INTERNAL` (`routers/research.py:765`). | There is **no client-facing report**. PR #97 states that one needs its own admission and approval contract, and none is written. |

The engine's own gate (`open_gate`, `decide_gate`, the `approval_decisions` ledger, `AWAITING_GATE`)
is complete, but **no research step opens one**: no executor returns a gated outcome, so it is
unused, and there is no route or screen to decide one.

### Finding: a budget wait is a dead end

1. **Claim.** A step parked as `AWAITING_BUDGET` never resumes, even after the budget is raised.
2. **Anchor.** `resume_waiting_steps` considers only `WAITING_PROVIDER` and `WAITING_CAPACITY` and
   states that it never touches `AWAITING_*` (`workflow_repository.py:1636-1650 @ 78c5b9e`);
   `set_study_budget` only changes the number (`scope_repository.py:594`); no other method moves
   `AWAITING_BUDGET` to `RUNNABLE` except the operator's `force_step_status` (`:2197`).
3. **Reproduction.** On 2026-10-02 a throwaway test (not committed) parked a step with
   `FailureClass.BUDGET_EXCEEDED`, raised the budget with `set_study_budget(scope, 100000.0)`, and
   ran `resume_waiting_steps()` and `claim_next()`: `RESUMED []`, `CLAIMED None`, status still
   `AWAITING_BUDGET`. The existing test `test_budget_exhaustion_parks_in_its_own_state` covers the
   park only, not the exit.
4. **Consequence.** A run that hits its cap stays "waiting for budget" for good. The person can
   raise the budget and nothing happens; since #103 the Progress page says why it waits but offers
   no action.
5. **Smallest fix.** `WorkflowRepository.lift_budget_wait(step_id, new_budget_usd, note)`: needs
   `APPROVE_BUDGET` and `MANAGE_STUDY_BUDGET`, raises the study budget (never lowers it), moves the
   step to `RUNNABLE` without consuming an attempt, and writes an `approval_decisions` row.
6. **Test that would have caught it.** Park, lift, claim: the step is claimable and the ledger
   has one row.

### Proposed design

**5b.1: lift a budget wait.** The method above, a route
`POST /studies/{id}/research/runs/{run_id}/steps/{node_key}/budget` taking the new total and a
note, and an action on the Progress page next to the wait it explains ("Zvýšit rozpočet na ... a
pokračovat"). The decision is a Researcher's, as ADR 0019 already says ("set a study's budget").
The worker keeps no such authority (`WORKER_PERMISSIONS`). Nothing else changes: the cap stays hard.

**5b.2: confirm what a run will cost, above a threshold.**
- A pure function in the domain gives an **upper-bound cost** for a research run from what readiness
  already knows (respondents, questions, batteries, objects) and the configured reservation per
  request, for fieldwork and for the eight analysis modules. It is a ceiling, not a forecast, and
  is labelled that way.
- The Run stage always shows that ceiling beside the study's remaining budget.
- When the ceiling is at or above the threshold (a setting, `AIA_SPEND_CONFIRM_USD`, **off when
  unset**) the start request must carry `confirm_cost_usd` at least equal to the ceiling, else the
  API answers 409 `cost_confirmation_required` with the ceiling. The page asks, the person confirms.
- The confirmation is one `approval_decisions` row (`subject_type = "spend"`, the ceiling, the
  threshold, who and whether self-approved), written in the same transaction as the run. The
  request body cannot lower the ceiling: the server recomputes it.
- Why not a step in the graph: a gate step would put `AWAITING_GATE` in front of every run and
  needs the gate-deciding route and screen anyway, to ask a question the person has already
  answered by pressing Start. A confirm on the start request reuses the ledger and adds no state.

**5b.3: one ledger.** The design accept (`ResearchAgentJobs.accept`) and the Knowledge decision
(`ClientKnowledgeRepository.decide`) also write an `approval_decisions` row
(`subject_type = "ai_proposal"`), so "who accepted what the AI produced" has one answer. Their
behaviour is unchanged; only the record is added. The pilot chatbot's proposed actions are in the
ADR's gate 1; I found no chatbot in the code and have not designed for one.

**5b.4: client-facing release.** Not designed here. It cannot be built before a client-facing report
exists, and that needs its own admission contract (which claims may reach a client, the licence
gate OI-61, and synthetic or internal-only claims refused, as `compose_internal_report` already
refuses them). The mechanism it will use is the one that exists: `approve` then `download_url`,
recorded in the same ledger. Until then no route serves a client-facing report, so there is nothing
to gate.

### 5b.1 progress (2026-10-02)

**Backend landed** (`feature/lift-budget-wait`): `WorkflowRepository.resume_budget_wait` (needs
`APPROVE_BUDGET`; refuses a step that is not `AWAITING_BUDGET` and a run being cancelled; writes the
approval ledger and a `STEP_RESUMED` event), `ResearchRuns.lift_budget_wait` (raises the study budget
through `ScopeRepository.set_study_budget`, so the change is audited, then resumes; checks everything
before writing so a refused lift changes nothing), and
`POST /studies/{id}/research/runs/{run_id}/steps/{node_key}/budget`. **The Progress page action is the
remaining part of 5b.1**, so the chunk is not ticked.

**A correction to the design above.** It said the existing ledger could be reused as it stands. It
cannot: `approval_decisions.subject_type` has a CHECK that admitted only `'gate'` and `'artifact'`
(`tables.py` `approval_subject_type_known`), so a `'budget'` row failed with an integrity error.
Migration `8c2f4a6d1b3e` widens it to `'budget'` only; 5b.2 and 5b.3 will each need to add their own
subject type (`'spend'`, `'ai_proposal'`) the same way. Verified on PostgreSQL 16: upgrade,
`alembic check` (no drift), downgrade to base and back, and a downgrade that is refused while a
`'budget'` row exists (the ledger is append-only).

**Gotcha for `AGENTS.md`** (Doc follow-up): the metadata's naming convention (`ck_%(table_name)s_...`)
is applied to the name given to `op.drop_constraint` as well as to `create_check_constraint`. A
constraint already created as `ck_approval_decisions_approval_subject_type_known` must be passed as
`op.f('ck_approval_decisions_approval_subject_type_known')` to both. Wrong: `op.drop_constraint(
'ck_approval_decisions_approval_subject_type_known', ...)` fails with `constraint
"ck_approval_decisions_ck_approval_decisions_approval_su_956c" ... does not exist` (double prefix,
truncated). Right: wrap the full name in `op.f(...)` on both calls.

### Decisions needed from the owner

1. **The threshold (5b.2).** The value is yours to set. I will not guess a dollar figure: the ceiling
   function can print it for the fictional acceptance run, and a threshold of about twice that is a
   reasonable start. Is a confirm-above-threshold on the start request the right shape, or do you
   want it on every run?
2. **5b.4 deferred** until a client-facing report is designed: agreed?
3. **Order:** 5b.1 first, because it fixes a dead end that exists today; then 5b.2; 5b.3 any time.

### Trade-offs accepted

- The ceiling can be far above what a run really costs; it protects against surprise, not
  against waste. Its precision improves when the reservation settings do.
- A confirmation on the start request is a click, not a second person. Per ADR 0019 that is the
  point; the ledger records it.
- The hard cap stays hard: a run past its budget still stops until a person lifts it.

## Findings

- **A source a person added still waited for approval, and could not be approved.** The client
  workspace's add went through `ClientKnowledgeRepository.propose`, so every source sat `PROPOSED` and
  stayed out of `for_study` until decided (`infrastructure/client_knowledge_repository.py`, `propose`/`_approved`
  @ 3c2ddda); the page hid Accept on the person's own proposals (`KnowledgeArea.tsx:126 @ 3c2ddda`) while
  the API, since chunk 2, allowed it, so a lone Researcher could not clear their own Pending tab.
  Reproduction: `POST /clients/{id}/knowledge/proposals` as the only member, then `GET .../knowledge`
  returned `[]`. Tests that guard it:
  `test_what_a_person_adds_takes_effect_at_once_with_nobody_to_approve_it`,
  `test_by_default_what_a_person_adds_to_a_client_takes_effect_at_once`, and the web test
  "lists a source a person adds at once, with nothing left to approve".

- **The worker borrowed the Researcher's permission set.** `ScopeResolver.execution_context` built the
  worker's scope from `permissions_for(EXECUTION_ROLE)` with `EXECUTION_ROLE = RESEARCHER`, so it was
  the old Researcher set that withheld approval (`application/scope.py:63-67 @ 2de4093`). Giving the
  Researcher every permission would have given the worker `APPROVE_GATE`, the exact thing ADR 0019
  decision 6 forbids. Chunk 2 adds an explicit `WORKER_PERMISSIONS` (`domain/scope.py`) and the
  worker's scope uses it. Reproduction before the fix: with `ROLE_PERMISSIONS[RESEARCHER]` widened,
  `test_the_execution_role_does_the_work_and_never_approves_it` fails. Tests that now guard it:
  that test, plus `test_worker_permissions_are_a_strict_subset_that_withholds_approval` and
  `test_a_worker_scope_cannot_accept_a_gate_or_change_the_budget` in `test_scope_isolation.py`.
- **A CI-only script still named a removed role.** The `Application starts` job provisions its world
  with `ScopeRole.LEAD` inline in `.github/workflows/ci.yml:622 @ 413f72d`, and `create_study`
  answered `role="LEAD"` (`routers/scope.py:471 @ 413f72d`). Neither is reached by `make test`, so
  the local run was green and the job went red on the PR (run 36869120448). Reproduction: the
  workflow's own provisioning snippet against PostgreSQL raises `AttributeError: LEAD`. Fix: both
  use `RESEARCHER`; `test_a_study_created_by_an_administrator_reports_the_one_role` fails on the old
  response. Reproduced and passed locally (migrate, boot, provision, project lifecycle over HTTP,
  worker start and stop) before the fix was pushed.
- **Stored roles.** The grant tables' CHECK constraints still allow `VIEWER/REVIEWER/LEAD`
  (`tables.py:565, :588`). Rows are read with `ScopeRole.from_stored`, which maps the retired values
  to `RESEARCHER`; the grant API accepts the old names. No migration in this chunk; chunk 6 drops
  the tables.

- The first draft of this plan cited only ADR 0015 decision 7. The grants and the "no implicit
  admin access" rule are ADR 0004's, written because clients may be direct competitors
  (`0004-client-study-isolation.md:8-9, 46-55`). Chunk 1 now supersedes those too, and the ADR
  states plainly that confidentiality between clients no longer rests on the application.
  Anchored to the ADR text, not a defect in the code.

## Doc follow-up

For the docs PR after merge:

- `CLAUDE.md` §2 map: `domain/scope.py` line (roles), the Client Knowledge paragraph ("a person
  other than the proposer approves"), the `ScopeResolver` description (grants).
- `ARCHITECTURE.md`: the scope and approval sections.
- `docs/architecture/adr/README.md`: the row for ADR 0019; ADR 0004 and ADR 0015 marked partly
  superseded (the "Superseded in part by" lines go in those two ADRs' headers, in the docs PR,
  because they are shared index material).
- `AGENTS.md`: nothing expected.
