# Scope and authorization

How AIA decides who may touch which client's work.

Implementation: `aia_core.domain.scope` (rules), `aia_core.application.scope`
(resolution), `aia_core.infrastructure.scope_repository` (persistence).
Decision record: [adr/0004](adr/0004-client-study-isolation.md), superseded in part by
[adr/0019](adr/0019-two-roles-and-human-ai-gates.md).

> **Status (ADR 0019, chunks 2 and 3).** AIA is for the team's own use, and the organization
> is the only boundary. Membership of the organization is the access: every active member
> holds the one `RESEARCHER` role on every client and study of it, and `ScopeResolver` reads no
> grant to decide that (`study_context`, `client_context`, `accessible_clients` and
> `accessible_studies`). `ACCESS_DENIED / no_grant` can no longer occur between members. What
> still returns 404 is an unknown id, an archived client, an inactive user, and a client or
> study of another organization. The worker's scope is still narrower than a person's
> (`WORKER_PERMISSIONS`). The grant tables, routes and the roles below remain in the database
> and the API until chunk 6 removes them and this document is rewritten; **the sections
> below that describe grants, four roles, precedence and the `no_grant` denial are the model
> that was superseded, kept so the migration is reviewable.**

## The model

```
Organization                the AIA team
├── User (member)           OWNER | ADMIN | MEMBER  -- administrative only
└── Client                  a paying client; a hard confidentiality boundary
    ├── ClientGrant         role over all of this client's studies
    └── Study               one engagement; unit of budget, delivery, access
        ├── StudyGrant      role over this study; overrides the client grant
        └── Project         revisions, stages, artifacts, workflow runs
```

Resolution chain:

```
User -> Organization membership -> Client grant -> Study grant -> Role -> Permissions
```

## Roles

**Organization roles** grant administrative capability only. `OWNER` and `ADMIN`
may create clients and studies and grant access. They do **not** grant the ability
to read client research data.

That separation is the point. On a team of five where everyone is plausibly an
admin, a client boundary that admins bypass is not a boundary. An admin who needs
to work on a study grants themselves access, and that self-grant is recorded under
its own `CLIENT_SELF_GRANT` audit action so break-glass access is visible
afterwards rather than indistinguishable from routine provisioning.

**Scope roles** apply to a client or a study:

| Role | View | Edit / run | Approve / sign off | Manage access & budget |
| --- | --- | --- | --- | --- |
| `VIEWER` | yes | no | no | no |
| `REVIEWER` | yes | **no** | yes | no |
| `RESEARCHER` | yes | yes | **no** | no |
| `LEAD` | yes | yes | yes | yes |

Two deliberate asymmetries:

- A `REVIEWER` cannot edit. Review must be independent of authorship, or the
  methodology's human sign-off gate is theatre.
- A `RESEARCHER` cannot sign off. The person who produced a deliverable cannot be
  the person who clears it for a client.

Handlers check **permissions**, never roles, so adding a role does not mean
finding every call site.

## Self-approval

Independent review is the **default**, not an absolute. A LEAD holds both
`EDIT_STUDY` and `SIGN_OFF_DELIVERABLE`, so a permission check alone would let one
person author a deliverable and clear its own gate by switching hats. The producer
is therefore refused — unless self-approval has been explicitly enabled by policy
for that scope, which small teams sometimes genuinely need.

```
study override  >  client override  >  organization setting  >  false
```

Every level is **nullable**, and null means *ask my parent* rather than *no*. A
copied-down value would mean that enabling self-approval for an organization
silently failed to reach clients created earlier — the kind of divergence nobody
notices until an approval that should have been refused was not. An explicit
`false` is not inheritance: a client whose contract requires independent review
keeps it under a permissive organization.

Three properties hold this together:

**The policy is server state.** It is resolved from the organization, client and
study rows when scope is issued, and travels on the `StudyContext`. A model, an
agent, a tool argument or a request body cannot assert that self-approval is
permitted, because none of them can produce a context. This is the same structural
guarantee as scope itself, applied to a second decision.

**Policy decides independence; permission decides authority.** Enabling
self-approval does not let anyone approve who could not approve anyway. A
RESEARCHER still cannot sign off their own deliverable, because they hold no
sign-off permission at all. Treating the flag as a permission would turn a
convenience setting into privilege escalation.

**Configuring it requires organization administration.** A study LEAD cannot
arrange self-approval for their own study. A control that is self-service is not a
control, and the change itself is written to `access_audit`.

Over HTTP, `PUT /api/v1/self-approval` sets one level (`{"allowed": true | false |
null}`, plus `client_id` or `study_id`; neither means the organization) and answers
with the policy that now resolves there and its source. `GET /api/v1/self-approval`
returns the levels as stored, not as resolved, because an administrator changing
the policy needs to see which level decided it. Both are OWNER / ADMIN only.

### The approval ledger

`approval_decisions` is append-only and records every gate decision and artifact
sign-off:

| | |
| --- | --- |
| Who | producer, approver, whether they were the same person |
| Under what rule | the effective policy and which level set it |
| On what | the exact gate or artifact, with run/step or project/revision |
| What was decided | the option or `APPROVED`, the comment, the timestamp |

The gate row and `is_approved` hold *current* state. Only the ledger can answer
what the rules were when a client deliverable was cleared, after the configuration
has since changed — which is the question an auditor actually asks.

## Grant precedence

A study grant is authoritative over a client grant **in both directions**.

```
client=VIEWER,     study=LEAD    -> LEAD      (brought in for one study)
client=LEAD,       study=VIEWER  -> VIEWER    (restricted on a sensitive study)
client=RESEARCHER, study=none    -> RESEARCHER
client=none,       study=none    -> no access; the study is invisible
```

Taking the maximum of the two would make the second case impossible, and that is
the case a confidentiality boundary exists for.

## StudyContext: scope that cannot be supplied

Every repository touching client data requires a `StudyContext`, and only
`ScopeResolver` can issue one:

```python
scope = resolver.study_context(principal, study_id=study_id)
repo = ProjectRepository(session, scope)
```

Construction is guarded by a module-private sentinel. A dict decoded from a model
response, a tool argument, an HTTP body or a job payload cannot forge one, and
`ProjectRepository` rejects anything that is not an issued context **by type**.

This is the structural half of the product rule:

> No AI- or model-generated argument may determine client or study scope.

An agent may pass any `client_id` it likes. It will not resolve unless the
authenticated human behind the request holds a grant on it. The worst a confused
or compromised agent can do is fail.

The client id is always derived from the **study row**, never from the caller, so a
mismatched client/study pair cannot be used to read one client's study under
another client's authorisation.

`OrganizationContext` is the administrative counterpart and deliberately carries
no client or study id, so it cannot be used to read research data at all.

## ClientContext: one client's workspace

A client workspace (ADR 0015) reads above the study -- the client's list of
studies, its overview, its knowledge -- so it needs scope for the client itself.
`ScopeResolver.client_context(principal, client_id, require=...)` issues a
`ClientContext`, with the same sentinel, after the same checks in the same
order: an active user, a member of the organization, a client of **that**
organization that is not archived, and then either a client-level grant or at
least one study grant on a study of the client. The studies the caller may open
are resolved there and travel on the context (`study_ids`); a list of the
client's studies is filtered by them in the query, never in the page.

What it allows is `ClientPermission`, from the client-level role:

| Client role | `VIEW_CLIENT` | `VIEW_CLIENT_KNOWLEDGE` | `PROPOSE_CLIENT_KNOWLEDGE` | `APPROVE_CLIENT_KNOWLEDGE` | `CREATE_STUDY` |
|---|---|---|---|---|---|
| none (study grants only) | yes | | | | |
| `VIEWER` | yes | yes | | | |
| `REVIEWER` | yes | yes | | yes | |
| `RESEARCHER` | yes | yes | yes | | yes |
| `LEAD` | yes | yes | yes | yes | yes |

Denial follows the rule below: no grant, an unknown or archived client, another
organization's client -- all 404, the reason in the audit. A caller who can see
the client but lacks the permission gets 403 `insufficient_role`.

**Client Knowledge** is read only through `ClientKnowledgeRepository`, which takes
an issued `ClientContext` or `StudyContext` and puts `client_id ==
scope.client_id` in the statement that finds the rows. There is no method that
reads knowledge by id alone, and no global pool filtered afterwards. A proposal
is approved by someone other than its proposer unless the client's self-approval
policy (above) allows it, and approval writes a new revision with its provenance.
ADR 0015 narrowly amends ADR 0004 rule 1 for this: a study may *propose*
knowledge to its own client, and only a human decision moves it there.

**A study's unit project** (OI-58) is found only from the study:
`StudyWorkspaceRepository.get(scope)` with an issued `StudyContext`. There is no
lookup by unit project id; an id a browser sends authorizes nothing.

## The isolation predicate

```python
ProjectRow.organization_id == scope.organization_id,
ProjectRow.client_id      == scope.client_id,
ProjectRow.study_id       == scope.study_id,
```

Applied in the same statement that finds the row, on every read and every write.
`study_id` alone would suffice given the foreign keys; all three are asserted
because a missed join is how cross-tenant leaks actually happen, and a corrupted
or mis-migrated row must not be readable under the wrong authorisation.

There is no method that fetches a project or artifact by id alone.

## Denial is 404, never 403

Every failure raises `ScopeDenied` and the API renders **404**.

A 403 would confirm the resource exists, disclosing that a competitor is a client
or that a particular engagement is underway. The distinguishing reason
(`no_grant`, `client_archived`, `user_deactivated`, `unknown_study`,
`insufficient_role`, `study_closed`) goes to the access audit, not the response.

The one exception: a caller who demonstrably has access to a study but lacks the
*role* for an action gets **403 `insufficient_role`**. Acknowledging a resource
they can already see leaks nothing, and telling them they need a different role is
actionable.

## Immediate revocation

Deactivation and grant revocation take effect on the **next request**, not at token
expiry, because authorization is a database read rather than a token claim. Both
are covered by tests.

## Audit

`access_audit` is append-only and records grants, revocations, self-grants,
membership changes, status and budget changes, and **denials**.

Denials of existing studies are recorded; requests for ids that do not exist in
the organization are not, so a prober cannot fill the audit log with noise.

## Closed studies

A `DELIVERED` or `ARCHIVED` study accepts no new work: `require_open_study()`
refuses it. Starting a run against a delivered study would change work a client
has already been shown.

## Still owed

- **PostgreSQL row-level security** as a second layer, so a future raw query
  cannot bypass the repository.
- **Rate limiting.** An authenticated member can currently exhaust the API.
- **An API surface for self-approval configuration.** The trusted write path is
  `ScopeRepository.set_self_approval`, which requires organization administration
  and is audited; it is not yet exposed over HTTP, so today it is set from a
  provisioning command.
