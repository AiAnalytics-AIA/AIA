---
status: in-progress
chunks:
  - "[x] 1. ADR 0019: two roles, no cross-approval, the human-with-AI gate catalogue (supersedes ADR 0004's grant rules and ADR 0015 decisions 6-7)"
  - "[x] 2. Domain: one Researcher permission set; self-approval allowed by default; REVIEWER and LEAD gone"
  - "[x] 3. ScopeResolver: every active member sees every client and study of the organization"
  - "[ ] 4. Admin: system settings only for ADMIN; MEMBER is the Researcher; settings document and web client"
  - "[x] 5a. Human-authored Knowledge writes directly (client workspace); a study's proposal still waits for a person, who may be its proposer"
  - "[ ] 5b. Gates: apply-an-AI-proposal, spend confirm, client-facing release"
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
