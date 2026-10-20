# ADR 0031 — Production is a second one-host environment with RDS, in the same AWS account, separated by tags, roles and state

**Status:** Proposed — 2026-10-20. Not accepted until the product owner says so. **Supersedes** the
"production compute remains undecided" of [ADR 0009](0009-single-host-develop-environment.md) (its
status line, *What this ADR does not decide* and *Migration path*) and the matching item of the ADR
index's *Not decided anywhere* list. ECS Fargate is **not** chosen for the MVP. **Builds on**
[ADR 0002](0002-postgresql-authoritative-store.md) (PostgreSQL is store and queue),
[ADR 0003](0003-cognito-identity-boundary.md), [ADR 0008](0008-eu-data-residency.md) and
[ADR 0010](0010-bedrock-eu-inference-route.md). **Leaves unchanged** develop, its host and its
deploy, and every application guard of `AIA_ENV=production`.
**Date:** 2026-10-20. **Amended 2026-10-20** with the product owner's recorded answers D-19, D-20
and D-21 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, #523 @ `ee21982`), and Q15 (a) on
the PM status page (20:50-21:04 UTC, relayed by the coordinator): the hostname. Still Proposed.
**Plan:** [production-environment](../../../.planning/plans/production-environment.md) PE0-PE9b

## Context

Gate I-5 reads "production released"; a tier B that passes on develop does not release. The owner
decided on 2026-10-19 (Q24; `mvp-target-architecture.md` §6): about ten users, no permanent
staging (develop is staging and tier B runs there), a separate production environment on the
one-host pattern with RDS PostgreSQL 16, in the **same AWS account** as develop. A separate account
was recommended and declined; the risk is recorded below.

ADR 0009 kept production open and said what would supersede it: "a second environment (production)
is provisioned — then the ECS/RDS ADR is written". Three facts of develop's Terraform make a second
environment in the same account unsafe if copied as it is:

- **The GitHub OIDC provider is one per account.** `infra/develop/github.tf:8-31 @ 854c209` creates
  it or looks it up (`create_github_oidc_provider`); a second root that also creates it collides, and
  a destroy of the root that owns it removes the other's deploy trust.
- **Develop's buckets are disposable.** `force_destroy = true` on `artifacts` and `ops`
  (`infra/develop/main.tf:109-117 @ 854c209`), correct for synthetic data and wrong for a client's.
- **A tagged Bedrock profile is refused.** The worker accepts only an `eu.` system profile id
  (`apps/executors/src/aia_executors/ai_runtime.py:254, 516 @ 854c209`), so an application inference
  profile ARN tagged by environment fails at start.

## Decision

### 1. The shape: develop's, with RDS

One EC2 host in `eu-central-1` runs Caddy, web, api and one or two workers under Docker Compose, as
develop does. **Amazon RDS PostgreSQL 16 replaces the database container**: single-AZ, private
subnets, a security group open only to the host, KMS encryption, deletion protection, 14 days of
point-in-time recovery and an automated snapshot before every migration. Own S3 buckets
(`artifacts`, `ops`, `population`), Cognito pool and client with Google Workspace callbacks for the
production hostname, ECR repositories, SSM parameters, CloudWatch alarms (develop's three, plus RDS
CPU, free storage and connections, and the oldest `QUEUED` step's age) and an AWS Budget filtered by
the `Environment` tag. The application runs `AIA_ENV=production`: fictional material refused, every
deployed-environment guard on.

### 2. A root of its own: `infra/production/`

A second Terraform root with its own state and lock. Its buckets are `force_destroy = false` with
`prevent_destroy`; the RDS instance has deletion protection and a final snapshot. One root per
environment keeps ADR 0009's "one root, no modules" rule; the difference from develop is
documented beside it.

**The account's GitHub OIDC provider leaves develop's lifecycle.** Production looking it up is not
enough: while develop's root owns it, a destroy of develop deletes it and breaks production's deploy
trust. So the provider moves to a third, account-level root, `infra/account/`, with its own state, that
owns only what is one per account (the OIDC provider, CloudTrail) under `prevent_destroy`. Develop's
resource is moved there by a state move or an `import` and a `removed` block, never by destroy and
recreate; develop and production both look it up (`create_github_oidc_provider = false`). The move
lands before production's first apply.

### 3. Separation inside one account

- an IAM role per environment, its policies conditioned on the `Environment` resource tag, under a
  permission boundary, so a develop role cannot touch a production resource;
- a deploy role per GitHub environment, assumable only from that environment;
- a KMS key, a Cognito pool, a bucket set, an RDS instance and a state per environment; bucket
  policies deny the other environment's roles;
- CloudTrail on for the account, owned by `infra/account/`.

**What this does not fix:** Bedrock quotas are account-wide, so tier B on develop and production
use draw on the same limits (tier B runs outside working hours, develop's concurrency is capped),
and an account-level IAM mistake has no second boundary.

### 4. A manual release from `main`

`deploy-production.yml` runs on a release from `main` through a GitHub environment with required
reviewers. It takes an RDS snapshot, runs migrations once as a step of their own, deploys the same
images develop ran (tagged by SHA), and smokes the deployed configuration. A migration is never
rolled back automatically; the rollback is the previous images against a database restored from the
snapshot, rehearsed before the first release (PE9b). Auto-deploys of develop are frozen during a
tier B run (PE8).

### 5. Deletion and restore

After a person deletes a client or study, its content may remain in backups and object versions for
**at most 30 days** (MVPQ-07; RDS's 14-day window lies inside it), and a durable deletion journal is
replayed after any restore before traffic is served, so a restore never resurrects deleted content
(`study-data-lifecycle` SDL6, PE9a). Content-free usage and audit rows stay so spend reconciles.

### 6. What production may send, and where

The model route's classes in production are approved by the same evidence as develop's amendment
to ADR 0010 (retention confirmed, the route parameters set), recorded for production separately; a
route approved on develop is not approved in production by inheritance. `AIA_AI_ROUTE_ID` equals
`bedrock-eu-primary`, the only route panel lineage may reach
(`domain/licence_determinations.py:40 @ 854c209`). Deep Research's settings are approved per
organization in production (ADR 0022).

**Egress** (the product owner, 2026-10-20, D-19): the worker's outbound traffic goes through a proxy
that blocks private, link-local and cloud metadata ranges only, with no hostname allow-list, so
Deep Research keeps its decided reach (fetch from any public host). The boundary is the
application's: `RetrievalGate` and its fetcher check every hop and every address, as they do on
develop (`infrastructure/web_retrieval.py`). The proxy is defence in depth for a bug in those
checks, not a list of permitted publishers.

### 7. Sizing, hostname and cost attribution

The proposed sizes are accepted (the product owner, 2026-10-20, D-20): `t3a.large` for the host and
`db.t4g.medium` for RDS, confirmed by a measurement on develop under the acceptance run before the
first apply; the Bedrock quota is raised before the first client run. The production hostname is
**`app.ai-analytics.ai`** (the product owner, 2026-10-20, Q15 a; the new domain of D-20). It is a
Terraform variable, set to that value, so the Cognito callbacks, the Google Workspace redirect and
Caddy's hostname follow it; the domain's DNS zone and certificate are part of the first apply.

Production uses **tagged application inference profiles** (the product owner, 2026-10-20, D-21), one
per model in use, tagged `Environment=production`, so its Bedrock spend is attributable from the
first run and reconciles with AIA's ledger (AC-15). The worker accepts a profile ARN where it
accepts an `eu.` id today (`ai_runtime.py:254, 516`, PE7, after `develop-spend-attribution` 5a).

## Alternatives considered

- **A separate AWS account.** The recommendation; declined by the owner. It is the first revisit.
- **ECS Fargate and an ALB** (ADR 0009's expected shape). More moving parts and cost for about ten
  users; nothing in the application depends on the host, so the move stays deployment work.
- **Production as a variable set on develop's root.** One state for two environments: a mistaken
  apply reaches both.
- **The database container on the production host.** RDS gives point-in-time recovery, snapshots
  and deletion protection that a volume and `pg_dump` do not.

## Consequences

- One host is a single point of failure: RDS protects the data, not availability. Accepted for an
  internal tool at about ten users.
- A second Cognito pool means a second set of Google callbacks and a second user list.
- The worker must accept a tagged profile ARN before production's first run (PE7, after
  `develop-spend-attribution` 5a).

## What enforces it

- An egress test on the production host: a fetch to a private, link-local or metadata address is
  refused by the application and again by the proxy; a fetch to an unlisted public host succeeds.
- PE3: `terraform fmt -check`, `validate` and `plan` on every pull request that touches `infra/`
  (a separate PR, since `ci.yml` is outside the docs-only path list).
- A Terraform test or plan check: neither `infra/develop` nor `infra/production` declares an
  `aws_iam_openid_connect_provider` resource (only `infra/account` does, with `prevent_destroy`), and
  `infra/production` declares no bucket with `force_destroy = true`.
- `smoke.sh` against production: `AIA_ENV=production` guards active, header identity rejected, the
  database unreachable from outside, the worker executing, the deployed SHA visible.
- The release checklist (PE9a, PE9b): restore with deletion replay, rollback, alarms, the activation
  profile `READY`.

## Unblocks

`production-environment` PE1-PE9b, the W1 infrastructure apply, and gate I-5.

## Open for Nigel

Answered by the product owner on 2026-10-20 (`answers-2026-10-20.md`, #523 @ `ee21982`), and
written into decisions 6 and 7:

1. ~~Hostname, sizing and quota.~~ The proposed sizes accepted; a new domain (D-20), named by Q15.
2. ~~Egress in production.~~ A proxy that blocks private and metadata ranges only; the application's
   checks are the boundary (D-19, b).
3. ~~Tagged profiles or `eu.` ids.~~ Tagged profiles (D-21, a).

- ~~The production hostname itself.~~ `app.ai-analytics.ai` (Q15, a). Decision 7.

Nothing remains open in this ADR but its acceptance.
