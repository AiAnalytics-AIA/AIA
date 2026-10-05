# ADR 0004 — Client and Study as hard isolation boundaries; scope is injected

**Status:** Accepted. Implemented. **Superseded in part** by
[ADR 0019](0019-two-roles-and-human-ai-gates.md) (2026-10-01): the client's own access list
(client and study grants, no implicit admin access, a study grant overriding a client grant, a
reviewer who cannot edit) is gone, and every active member sees every client and study of the
organization. Rules 1 and 2 stand: every client-derived object carries its client and study, and
scope is injected, never supplied. The grant tables were dropped on 2026-10-05 (#120); the
`access_audit` rows of past grants remain.
**Date:** 2026-09-21

## Context

AIA holds confidential research for clients who may be direct competitors. Client
and Study are product-level isolation boundaries, not labels.

The system is also heading towards agentic execution, where an LLM chooses tool
calls and supplies their arguments.

## Decision

Two rules, enforced structurally rather than by convention.

### 1. Every client-derived object resolves to a client and a study

`projects` carries `organization_id`, `client_id` and `study_id`. The repository's
isolation predicate asserts all three in the same statement that finds the row.

`study_id` alone would suffice given the foreign keys. All three are checked
anyway, because a missed join is exactly how cross-tenant leaks happen, and a
corrupted or mis-migrated row must not be readable under the wrong authorisation.

### 2. Scope is injected, never supplied

`StudyContext` can only be issued by `ScopeResolver`, which requires a verified
principal and reads their grants from PostgreSQL. Construction is guarded by a
module-private sentinel, so a dict decoded from a model response, a tool argument
or an HTTP body cannot forge one. `ProjectRepository` and `ArtifactRepository`
refuse anything that is not an issued `StudyContext`, by type.

**This is what makes the agentic rule enforceable:** an AI tool may pass whatever
`client_id` it likes, and it will not resolve unless the authenticated human
behind the request holds a grant on it. The worst a confused or compromised agent
can do is fail.

## Supporting decisions

**Denial is 404, never 403.** A 403 confirms the resource exists, which discloses
another client's engagement. Every denial reason is recorded in the access audit
instead.

**Organization admins get no implicit client data access.** They may create
clients and studies and grant access; reading research still needs a grant. On a
team where everyone is effectively an admin, this is the only thing that makes the
client boundary mean anything. An admin granting themselves access is legitimate —
someone must start work on a new client — and is recorded under a distinct
`CLIENT_SELF_GRANT` action so break-glass access is reviewable.

**A study grant overrides a client grant in both directions.** It can bring
someone in for a single study, or restrict a client lead on a sensitive one. Taking
the maximum of the two would make the second impossible.

**A reviewer cannot edit.** `REVIEWER` holds `APPROVE_GATE` and
`SIGN_OFF_DELIVERABLE` but not `EDIT_STUDY`. The methodology's human sign-off gate
is meaningless if the author can clear it.

**Handlers check permissions, never roles.** Adding a role does not require
finding every call site.

## Alternatives considered

**Row-level security only.** Rejected as the primary mechanism: it would not stop
an application-layer bug from querying with the wrong scope, and it cannot express
"a study grant narrows a client grant". Still wanted as a **second** layer.

**A single `tenant_id` column.** Rejected: it cannot express that two studies for
the same client are also isolated from each other.

**Passing `client_id` as a parameter.** Rejected: that is precisely the hole the
sentinel closes. Scope derived from a parameter is scope an agent can choose.

## Consequences

- Every repository touching client data needs a `StudyContext`, which makes test
  setup heavier. The shared fixture provisions a real two-client world so tests
  exercise the production authorisation path rather than a permissive stub.
- Background jobs must carry enough information to re-resolve scope, since a
  `StudyContext` is not serialisable by design.
- PostgreSQL row-level security is still owed as defence in depth.
