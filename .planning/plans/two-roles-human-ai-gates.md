---
status: in-progress
chunks:
  - "[x] 1. ADR 0019: two roles, no cross-approval, the human-with-AI gate catalogue (supersedes ADR 0004's grant rules and ADR 0015 decisions 6-7)"
  - "[x] 2. Domain: one Researcher permission set; self-approval allowed by default; REVIEWER and LEAD gone"
  - "[x] 3. ScopeResolver: every active member sees every client and study of the organization"
  - "[x] 4. Admin: system settings only for ADMIN; MEMBER is the Researcher; settings document and web client"
  - "[x] 5a. Human-authored Knowledge writes directly (client workspace); a study's proposal still waits for a person, who may be its proposer"
  - "[ ] 5b. Gates (design proposed below, awaiting the owner): split into 5b.1 to 5b.4"
  - "[x] 5b.1 A person can lift a budget wait and the run goes on (today it is a dead end)"
  - "[x] 5b.2 Confirm the cost of a run above a threshold, recorded"
  - "[x] 5b.3 One ledger entry for every acceptance of an AI proposal"
  - "[ ] 5b.4 Client-facing release (blocked: the client-facing report contract does not exist)"
  - "[x] 6. Retire the grants (tables, routes, UI) after one deploy without them"
  - "[x] 7. Any Researcher starts a client (the owner, 2026-10-05); its status stays with the Admin"
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

## Chunk 4 (landed 2026-10-02)

What the Settings page said, against what the system does (ADR 0019), found by reading the page's
own strings:

| Said | Was | Now |
|---|---|---|
| Invariant `membership_grants_no_data: true` ("membership alone grants no client data"), in force and not editable | False since chunk 3: membership is the access (`settings.py:185 @ d5f214d`) | Invariant `membership_is_access` citing ADR 0019 |
| "Added member sees no client data until granted" (members note); "grant a client / study" forms with a role picker | A grant is read by nothing | Forms and the web client's `grantClient` / `grantStudy` removed; the routes stay until chunk 6 |
| Self-approval rule "default (forbidden)" | Default is allowed (`DEFAULT_SELF_APPROVAL_ALLOWED = True`) | "default (allowed)" |
| Role labels LEAD, REVIEWER, VIEWER; organization role MEMBER "člen" | Only the Researcher exists | MEMBER reads "výzkumník"; legacy labels removed |

**Tests.** `test_the_settings_say_membership_is_access_and_offer_no_grants` (fails on the old
document); three tests pin that a Researcher cannot add a member, create a client or change
self-approval (they were only implied); one web test asserts no grant control, no stale sentence and
the role picker's labels (fails on the old component).

**Left for the owner (a finding, not a change).** Creating a client needs an Admin
(`scope_repository.py:272`, `workspace.py` "Starting a client needs an organization owner or admin").
ADR 0019 lists "create studies" for a Researcher and says nothing about clients. If a Researcher
should be able to start a client, that is a one-line permission change plus its test; I did not guess.

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

### Chunk 6 plan (2026-10-05; the owner approved starting it on 2026-10-03)

**Condition met.** Chunk 3 (no grant is read) merged in #105 and has been on `develop` through several
green deploys since (the latest dispatched 2026-10-03 21:10 UTC). Nothing has read a grant row since.

**A correction to the chunk line above.** It says to drop "the per-level `allow_self_approval`
columns" too. That contradicts ADR 0019 decision 3: *"The setting stays (organization, client,
study) so a client that demands independent review can have it back"*, and 5a relies on it (a
person's knowledge write files an ordinary proposal where self-approval is explicitly off). Those
columns are kept; only the grants go.

What goes, all of it written to and none of it read since chunk 3:

- `ScopeResolver.grant_client_access`, `grant_study_access`, `revoke_client_access`;
- `POST /clients/{client_id}/grants` and `POST /studies/{study_id}/grants` (the web client stopped
  calling them in chunk 4);
- the self-grant a new client gave its creator (`workspace.py`) and the develop seed's grants;
- the tables `client_grants` and `study_grants` (`ClientGrantRow`, `StudyGrantRow`), in one
  migration. Its downgrade recreates them empty: the rows are not restored, and nothing reads them.
  What they recorded is kept where it always also was, the `access_audit` rows (`CLIENT_GRANT`,
  `STUDY_GRANT`, `CLIENT_SELF_GRANT`, `CLIENT_REVOKE`), which stay readable in Settings → Audit.

Tests that exercised granting are removed with it; tests that used grants to set up a world drop
those calls (membership already gives the access). No test of a rule that still holds is removed.

### Chunk 6 landed (2026-10-05, branch `feature/retire-grants` from `develop` @ `70ff89d`)

- Code: the three grant methods are gone from `application/scope.py`; `ClientGrant`, `StudyGrant`
  and `effective_role` from `domain/scope.py` (`effective_role` was kept by chunk 3 only "until
  the grants are retired"); `ClientGrantRow`, `StudyGrantRow` from `infrastructure/tables.py`; the
  two `/grants` routes and `GrantRequest` from `routers/scope.py`; the creator's self-grant from
  `workspace.py` `start_client`; the seed's grants from `application/develop_seed.py`.
- Migration `20261005_d8e2f4a6b1c3` (down `c5d7e9f1a2b4`). PostgreSQL 16: one head; upgrade from
  base to head; `alembic check` clean; downgrade to `c5d7e9f1a2b4` recreates both tables, and their
  `pg_dump -s` is identical to the same tables built by the original migrations (columns, CHECK,
  PK, FKs, indexes); downgrade to base and upgrade again clean.
- Tests removed because their subject was the granting itself: in `test_scope_isolation.py`
  `test_admin_self_grant_works_and_is_audited`, `test_study_grant_is_authoritative_when_present`
  (`effective_role`), `test_study_grant_cannot_narrow_a_researcher`,
  `test_a_study_grant_adds_nothing_because_membership_is_the_access`,
  `test_a_researcher_can_staff_their_own_study`, `test_a_plain_researcher_can_staff_a_study`,
  `test_regression_a_study_grant_never_removes_access_a_client_grant_gives`,
  `test_self_grant_records_previous_and_new_access`,
  `test_granting_someone_else_is_not_recorded_as_a_self_grant`; and the worker test's one line
  that a worker could not grant (the rest of that test stays).
- Tests rewritten to say the same rule without a grant:
  `test_a_new_member_reads_the_clients_knowledge_like_any_member` (was "…with only a study
  grant…"), `test_a_new_member_may_do_everything_for_the_client` (`test_client_scope.py`),
  `test_any_member_sees_the_whole_client_and_its_knowledge` (`test_client_api.py`),
  `test_the_access_audit_lists_entries_with_their_payload` (now audits a study started in a
  client, which writes a payload, instead of a grant).
- Setup-only grant calls dropped from the four `conftest.py` files, `test_seed_and_smoke.py` and
  `test_deep_research_journey.py`; every isolation test (cross-organization 404, archived client,
  the worker's permissions, forged scope) stays.

### Chunk 7: any Researcher starts a client (2026-10-05, branch `feature/researchers-create-clients` from `develop` @ `056eca2`)

**The owner's decision, in conversation, 2026-10-05:** "yes researchers are able to create clients".
It answers the question this plan carried since chunk 4 (creating a client was Admin-only).
ADR 0019 already allows it: Admin is "everything a Researcher holds, plus the system settings and
user administration" (`docs/architecture/adr/0019-two-roles-and-human-ai-gates.md:35`), and a
client is neither. The Admin-only rule was a reading recorded in a test comment ("ADR 0019 keeps
it with the Admin", `apps/api/tests/test_client_api.py:70 @ 056eca2`), not the ADR; the ADR
needs no edit.

- `ScopeRepository.create_client` no longer calls `require_administer`; the context it takes
  exists only for an active member, and `CLIENT_CREATED` names the actor.
- `POST /clients` and `POST /workspace/clients` lose their 403 branch.
- The client directory offers "Nový klient" to every member; its empty state no longer says
  "budete jeho vedoucím" (a retired role) or "ask an admin to give you access" (ADR 0019).
- Unchanged, still the Admin's: a client's status (`set_client_status`, archive included), and
  the organization-level `create_study` (`POST /studies`). A member starts a study in a client
  workspace, as before.
- Stale access sentences fixed on the way: the settings account note, the roles intro, the
  `/studies` empty state and the API-control help ("Mění správce" — budgets are a Researcher's).
- Tests: `test_only_admins_can_create_clients_and_studies` is replaced by
  `test_a_researcher_creates_a_client_every_member_opens_it_and_the_creation_is_audited` and
  `test_a_clients_status_and_the_organization_level_study_route_stay_with_administration`; the
  API test now has the researcher start the client; new
  `test_a_researcher_creates_a_client_by_the_api_but_its_status_stays_with_administration`; the
  settings case asserting 403 on `POST /clients` is removed (it asserted the retired rule); the
  web test offers the new client to a member.

### 5b.3 plan (2026-10-05; the owner said "yes" to starting it)

**Two corrections to the 5b.3 line in the design above, found reading `develop` @ `0c42547`:**

1. **No AI writes a Knowledge proposal today.** `propose_from_study` has one caller, the route
   `POST /studies/{study_id}/knowledge-proposals` (`apps/api/src/aia_api/routers/workspace.py:1225`),
   which a person calls; `propose` (`client_knowledge_repository.py:327`) is a person's in the
   client workspace, and the only other caller is the develop seed. No executor proposes Knowledge
   (`grep -rn "propose_from_study\|\.propose(" --include=*.py packages apps`). Writing an
   `ai_proposal` row on every `ClientKnowledgeRepository.decide` would label people's proposals as
   the AI's (CLAUDE.md §8, never stamp a guess). So the Knowledge decision is left as it is; the
   day an AI authors Knowledge, that path writes the row (recorded under Findings).
2. **A worker's scope could accept an AI proposal.** `ResearchAgentJobs.accept` checks only
   `EDIT_STUDY` (`application/research.py:576 @ 0c42547`), which `WORKER_PERMISSIONS` holds
   (`domain/scope.py:202`). ADR 0019 decision 6: "The AI and the worker hold no gate authority",
   and accepting an AI proposal is gate 1. Nothing calls `accept` with a worker's scope today; the
   check is what keeps it so.

**What this chunk does:**

- `approval_decisions.subject_type` admits `'ai_proposal'` (one migration; the downgrade refuses
  while such a row exists, as `c5d7e9f1a2b4` does for `'spend'`).
- `WorkflowRepository.record_ai_proposal_acceptance(run_id, ...)`: one row per agent job —
  `subject_id` = the job's run id, `gate_type` = the action, `producer_user_id` = who asked the AI,
  the approver and `self_approved` from the same `observe_approval_independence`, and in `comment`
  the Design Revision the accept wrote, whether it was new, and the proposal artifact. Needs
  `APPROVE_GATE`. A second accept of the same job writes no second row (an identical proposal can
  be accepted twice; the check runs under the Study row lock `submit_if_current` already holds).
- `ResearchAgentJobs.accept` requires `APPROVE_GATE` as well and calls it in the same transaction
  as the revision. A Researcher holds both permissions, so no person's behaviour changes.

**Tests:** the accept writes one row naming the job, the revision and the people; a second accept
of an unchanged proposal writes none; a worker's scope is refused with no revision and no row; the
migration's downgrade refuses while an `ai_proposal` row exists (PostgreSQL).

### 5b.3 landed (2026-10-05, branch `feature/ai-proposal-ledger` from `develop` @ `0c42547`)

- Migration `20261005_e4b7c2d9f6a1` (down `d8e2f4a6b1c3`): the ledger CHECK admits `'ai_proposal'`.
  PostgreSQL 16: one head; upgrade; `alembic check` clean; the downgrade refused with one seeded
  `ai_proposal` row ("1 AI proposal accept(s) are in the approval ledger"), then ran once it was
  gone; upgrade again clean.
- `WorkflowRepository.record_ai_proposal_acceptance` and `ResearchAgentJobs.accept` as planned.
- Tests (`apps/executors/tests/test_research_agent_executor.py`, through the real worker):
  `test_worker_stores_proposal_and_review_creates_a_new_revision` now asserts the one row (job,
  action, artifact type, producer = approver = the lead, `self_approved`, the revision and the
  artifact in `comment`); `test_a_workers_scope_cannot_accept_an_ai_proposal`;
  `test_the_same_jobs_accept_is_recorded_once`. Both new tests fail with the `APPROVE_GATE` check
  and the once-only guard removed, and pass with them. The CHECK test in `test_scope_isolation.py`
  admits `ai_proposal`.

### 5b.2 plan (2026-10-03, owner's decision: the threshold is per study, set before the run)

The owner's answer to "what is the threshold and where is it set": **per study, at the beginning of
the run**, not a deployment setting. So `AIA_SPEND_CONFIRM_USD` from the proposal above is dropped.

- Each study has an optional **confirm limit** (`studies.spend_confirm_usd`, NULL = none). A
  Researcher sets it on the Run stage before pressing Start. Audited like the budget.
- The Run stage always shows the run's **cost ceiling** beside the study's remaining budget.
- When a limit is set and the ceiling is at or above it, `POST .../research/runs` must carry
  `confirm_cost_usd >= ceiling`, else 409 `cost_confirmation_required` with the ceiling. The server
  recomputes the ceiling; the body cannot lower it. The confirmation is one `approval_decisions`
  row (`subject_type = "spend"`), written in the run's transaction.
- **The ceiling** is an upper bound, labelled as one: fieldwork requests x the fieldwork
  reservation, plus analysis modules x calls per module x the analysis reservation. Fieldwork
  requests are respondents x the most blocks a questionnaire can split into (every item asked of
  every respondent, none answered by code), because which items code answers depends on each
  persona. The reservations are the worker's settings (`AIA_AI_FIELDWORK_RESERVATION_USD`,
  `AIA_AI_ANALYSIS_RESERVATION_USD`); the API reads the same variables, as it already does for
  `AIA_AI_FICTIONAL_CLIENT_IDS`, and `deploy/develop/docker-compose.yml` passes them to the API.
- **Unknown is not zero.** If a reservation the run needs is not set for the API, the ceiling is
  unknown (null, with the reason). With a limit set, an unknown ceiling refuses the start
  (409 `cost_ceiling_unknown`) rather than letting it through.

Chunks (each builds and passes on its own; one PR):

1. Domain: the pure ceiling function and the block-splitting helper it shares with
   `plan_respondent`; tests that pin the arithmetic.
2. Persistence: migration (`studies.spend_confirm_usd`; ledger `subject_type` admits `'spend'`),
   `ScopeRepository.set_study_spend_confirm` (audited), the study's response.
3. Application and API: the ceiling in the readiness answer, the confirmation on start, the ledger
   row, `PUT /studies/{id}/spend-confirm`, the API settings and the Compose passthrough.
4. Web: the Run stage shows the ceiling, the limit control and the confirm step; Czech strings.
5. Tick 5b.2; Doc follow-up (CLAUDE.md map, AGENTS.md if a gotcha appears, the Compose variables).

### 5b.2 landed (2026-10-04, PR #117)

All five chunks of the plan above, as planned, with these specifics:

- **Ceiling** `domain/run_cost.py`: `run_cost_ceiling` (tests `test_run_cost.py`, incl. every persona of a
  roster under the bound). Analysis counts `1 + MAX_REPAIRS` calls per module.
- **Limit** `studies.spend_confirm_usd`, `ScopeRepository.set_study_spend_confirm` (audited
  `STUDY_SPEND_CONFIRM_CHANGED`); ledger `subject_type='spend'`; migration `c5d7e9f1a2b4`.
- **Start/retry** `ResearchRuns.start` / `retry` take `reservations` and `confirm_cost_usd`;
  `WorkflowRepository.record_spend_confirmation` writes the row (needs `APPROVE_BUDGET`; the worker
  cannot). Errors over HTTP: 409 `cost_confirmation_required` (details: ceiling, limit), 409
  `cost_ceiling_unknown` (details: reason, limit).
- **Run stage**: a "Náklady běhu" card (ceiling, its basis, "horní mez, ne odhad", what is left of the
  budget, the limit and whether Start will ask; a limit form for an editor). Start asks with the
  server's ceiling; Start is disabled when a limit is set and the ceiling is unknown; a retry that the
  server answers with `cost_confirmation_required` asks and retries with the yes.

**Found on the way.** The Run stage crashed on a readiness answer without the new fields (an older
API during a rollout): it now reads a missing figure as absent, not zero, and not as a crash.

### 5b.1 progress (2026-10-02)

**Backend landed** (`feature/lift-budget-wait`): `WorkflowRepository.resume_budget_wait` (needs
`APPROVE_BUDGET`; refuses a step that is not `AWAITING_BUDGET` and a run being cancelled; writes the
approval ledger and a `STEP_RESUMED` event), `ResearchRuns.lift_budget_wait` (raises the study budget
through `ScopeRepository.set_study_budget`, so the change is audited, then resumes; checks everything
before writing so a refused lift changes nothing), and
`POST /studies/{id}/research/runs/{run_id}/steps/{node_key}/budget`. **The Progress page action is the
remaining part of 5b.1** and has landed too (below), so the chunk is ticked.

**Progress page landed.** A step in `AWAITING_BUDGET`, seen by someone who can edit the study, shows a
form under it (`BudgetLift` in `ExecutionSteps.tsx`): the study's budget and what is spent (read from
`GET /studies/{id}`), a new total that cannot be below the budget now (the button is disabled, and the
API refuses it with 422 `budget_not_raised` regardless), an optional note, and "Zvýšit rozpočet a
pokračovat" (`research.liftBudget`). The cap stays hard and the page says so: if the new total still
does not cover the step it stops again. A 409 (`not_waiting_for_budget`) is printed and the form stays.
Four Vitest tests in `ExecutionSteps.test.tsx` (post body and path, lower total disabled, API refusal
shown, nothing for a reader or for a non-budget wait); three fail with the form switched off.

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

- **A Knowledge change an AI writes will need its own ledger row; none exists yet.** ADR 0019
  decision 5 makes an AI-authored Knowledge change a proposal that a person accepts (gate 1), but no
  code path lets an AI author one: `propose_from_study` is called only by a person's route
  (`apps/api/src/aia_api/routers/workspace.py:1225 @ 0c42547`) and the develop seed. So
  `ClientKnowledgeRepository.decide` writes no `ai_proposal` row, on purpose (5b.3 plan). The
  executor that first proposes Knowledge must mark the proposal as AI-authored and make `decide`
  write the row; the test is the one 5b.3 added for design accepts, for Knowledge. Not a defect
  today: there is nothing to record.

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

For the docs PR after merge. **Applied** by `chore/docs-follow-up-two-roles` (2026-10-05), with
the follow-ups of #112, #113, #114, #117 and #122; findings filed as OI-82 to OI-84.

- `CLAUDE.md` §2 map: `domain/scope.py` line (roles), the Client Knowledge paragraph ("a person
  other than the proposer approves"), the `ScopeResolver` description (grants).
- `ARCHITECTURE.md`: the scope and approval sections.
- `docs/architecture/adr/README.md`: the row for ADR 0019; ADR 0004 and ADR 0015 marked partly
  superseded (the "Superseded in part by" lines go in those two ADRs' headers, in the docs PR,
  because they are shared index material).
- `AGENTS.md`: nothing expected.
- 5b.3: `CLAUDE.md` §2 map, the `workflow_repository.py` line, after "resume_budget_wait: a person
  lifts an AWAITING_BUDGET step, in the approval ledger (the worker's scope cannot)": add
  "record_ai_proposal_acceptance: a person's accept of an agent job's proposal, once per job, in the
  same ledger (ADR 0019 gate 1)". The plan's own 5b design line about Knowledge decisions is
  corrected in the 5b.3 plan above.
- Chunk 7: none. No shared document says who creates a client (`grep -i "creat.*client"` over
  `CLAUDE.md`, `ARCHITECTURE.md`, `AGENTS.md` @ `056eca2`). It also restores ADR 0015's rule
  "Nothing in the client shell may depend on the caller being an owner or admin"
  (`docs/architecture/adr/0015-client-first-product-interface.md:167`), which the Admin-only
  "Nový klient" button broke.
- Chunk 6: `CLAUDE.md` §2 map, `scope_repository.py` line: "(grant tables remain, unread, until
  ADR 0019 chunk 6 retires them)" becomes "(the grant tables are dropped, ADR 0019 chunk 6)";
  `docs/architecture/adr/0004-client-study-isolation.md` and the ADR index: grants no longer exist
  in the schema, the audit rows of past grants remain.
