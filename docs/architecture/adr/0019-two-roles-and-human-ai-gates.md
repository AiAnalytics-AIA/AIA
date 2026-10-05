# ADR 0019 — Two roles, no approval between people, and gates only between a person and the AI

**Status:** Accepted on merge — the owner's decision, 2026-10-01. **Supersedes** the
supporting decisions of [ADR 0004](0004-client-study-isolation.md) that gave a client its own
access list (admins get no implicit access; a study grant overrides a client grant; a reviewer
cannot edit), decision 6 of [ADR 0015](0015-client-first-product-interface.md) (a client-level
grant is needed to start a study) and decision 7's approval rules (a person other than the
proposer approves; Knowledge management needs a client-level grant). **Stands:** ADR 0004 rules 1
and 2 (every client-derived object carries its client and study; scope is injected, never
supplied), ADR 0008 (residency), ADR 0010 (the Bedrock route and what it is approved for), ADR
0016 decision 5 (the licence gate) and ADR 0018 decision 3 (AIA's own gate: any active member).
**Date:** 2026-10-01
**Implemented** on develop, 2026-10-05 (#105–#123): one Researcher role, membership as the access,
the grants retired, the budget lift, the spend confirmation and the record of every accept of an
AI proposal. Gate 3 (client-facing release) waits for a client-facing report contract. **The
owner, 2026-10-05:** a Researcher also creates clients (#121); a client's status stays the Admin's.
**Plan:** [`.planning/plans/two-roles-human-ai-gates.md`](../../../.planning/plans/two-roles-human-ai-gates.md)

## Context

AIA was designed for a team that reviews one another: four scope roles (`VIEWER`, `REVIEWER`,
`RESEARCHER`, `LEAD`), a `REVIEWER` who can approve but not edit, a default that refuses a
person approving their own work, and access to each client by grant
(`domain/scope.py:124-216`, `:327`, `:433-471 @ 2de4093`). Client Knowledge could be changed only
by an approval from someone other than the proposer (ADR 0015 decision 7).

The owner has decided that this is the wrong shape for the MVP. People in the organization are
trusted colleagues; what needs a gate is the AI. Uploading a source, editing a brief or running a
study should need no one's approval. A person should be asked to accept what the AI produced,
and only where AIA says so.

## Decision

1. **Two roles.**

   | Role | Is | Holds |
   |---|---|---|
   | **Researcher** | `OrganizationRole.MEMBER` | Every permission: view, edit, upload, run, cancel, see costs, create studies, write Knowledge, accept gates, export, set a study's budget |
   | **Admin** | `OrganizationRole.ADMIN` | Everything a Researcher holds, plus the system settings and user administration |

   `OWNER` stays as the first Admin and is treated as one; it is retired later, not in this
   change. `REVIEWER`, `LEAD`, `VIEWER` and the client-level permission split are removed.
   Handlers keep checking permissions, never roles (ADR 0004): an Admin permission is added,
   the rest collapse.

2. **Every active member sees every client and study of the organization.** There are no client
   or study grants. Membership of the organization is the access.

   What is kept, because it is not approval: the organization is the tenant boundary; an inactive
   user, a non-member and an id from another organization all get the same 404; an archived client
   stays invisible; and ADR 0004 rules 1 and 2 stand unchanged. A `StudyContext` or `ClientContext`
   is still issued only by `ScopeResolver` from persisted state, and a tool argument, request body
   or model output still cannot name a client, study, role or policy.

3. **No approval between people.** The default for self-approval becomes *allowed*. The person who
   uploaded, edited, ran or produced something may accept it. The setting stays (organization,
   client, study) so a client that demands independent review can have it back, and the audit
   record keeps `producer_user_id`, `approver_user_id` and `self_approved`
   (`domain/scope.py:401-409`).

4. **Gates exist only between a person and the AI.** A gate is a person accepting something the AI
   produced. The set is closed:

   1. **Apply an AI proposal** — a design or context proposal, a Knowledge change the AI wrote, or
      an action the pilot chatbot proposes. Nothing is written until accepted.
   2. **Spend** — starting a run above a threshold is shown with its cost and confirmed. The
      threshold is a setting; the plan leaves its value open.
   3. **Client-facing release** — exporting a deliverable that contains AI-produced content.

   Not gates: uploading sources, human edits, human-authored Knowledge, and runs under budget.
   Adding a gate later is its own change with its own record.

5. **Client Knowledge.** A person's change writes a new revision directly, with its author as
   provenance. A change the AI authored is a proposal and needs a person's accept (gate 1).
   Revisions stay append-only (ADR 0015 decision 7).

6. **The AI and the worker hold no gate authority.** A worker's context is issued only against a
   held lease and cannot accept a gate (`application/scope.py:317-386`); a model, an agent or the
   chatbot acts under the signed-in person's own context and can only propose.

## What does not change

- EU residency, data class and the egress boundary (ADR 0008).
- The Bedrock route is approved for fictional Class C only (ADR 0010). **Seeing a client is not
  sending it to a model:** widening who may open a client widens nothing about what may be
  transmitted. The licence gate (OI-61) is unchanged.
- Cost reservation and the usage ledger (ADR 0005).
- The evidence rules for a client-facing number (`AdmittedClaim`). That is a separate question
  from approval and is not decided here.

## Consequences

- **No confidentiality between clients inside the organization.** ADR 0004 was written because
  clients may be direct competitors, and its supporting decisions were what made that boundary
  mean something for a team where everyone is effectively an admin. After this change, any
  member can open any client's workspace, Knowledge and results. Confidentiality between two
  clients rests on trust in the people of the organization, not on the application. Reversing
  this means reintroducing grants and deciding who holds which, with several clients' data
  already in one pool.
- **One person can produce and release a deliverable.** The audit record says so; nothing
  prevents it.
- **No role can administer without being able to read client data.** The property documented on
  `OrganizationRole` (`domain/scope.py:108-116`) is retired.
- **The audit loses an event.** `ACCESS_DENIED / no_grant` can no longer occur between members.
  A cross-organization probe still 404s and is not recorded (an unknown id is noise).
- **Tests change, not disappear.** The tests that assert a refusal of self-approval or of a
  missing grant are rewritten to assert the new rule. None is skipped or loosened.
- **The grant tables go in a later change,** after one deploy that no longer reads them, so the
  change can be rolled back until then (plan chunk 6).

## Alternatives considered

**Keep the grants, drop only the roles.** Rejected by the owner: it keeps an access list to
maintain for a team that does not want one. It was the recommended option in the plan's
discussion and remains the smaller step back if client confidentiality becomes a requirement.

**Keep `REVIEWER` as an optional role.** Rejected: independent review is already available per
scope through the self-approval setting; a role whose only purpose is to be the other person is
the shape being removed.

**Leave the self-approval default off and set it on per organization.** Rejected: the product's
default posture is now the opposite, and a default that every deployment overrides is a default
that is wrong.

## Revisit when

- A client or contract requires that other staff cannot see its work.
- A second organization shares a deployment, or a person outside the organization (a client's own
  user) is given access: that needs a boundary this ADR does not provide.
- The gate set proves wrong: a gate nobody reads, or something that should have asked and did
  not.
- Class A/B transmission is approved (ADR 0010): who may trigger it then deserves its own look.
