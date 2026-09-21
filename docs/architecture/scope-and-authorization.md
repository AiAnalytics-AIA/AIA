# Scope and authorization

How AIA decides who may touch which client's work.

Implementation: `aia_core.domain.scope` (rules), `aia_core.application.scope`
(resolution), `aia_core.infrastructure.scope_repository` (persistence).
Decision record: [adr/0004](adr/0004-client-study-isolation.md).

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
