# ADR 0009 — One EC2 host runs the `develop` environment under Docker Compose

**Status:** Accepted for the `develop` integration environment only. **Production
compute remains undecided** (ADR 0002 § Compute, ADR index).
**Date:** 2026-09-23

## Context

The application has a layered architecture, a durable PostgreSQL-backed workflow
engine and fail-closed guards for deployed environments, and none of it has ever
run outside a laptop or a CI runner. A first continuously deployed environment is
needed so that a merge to `develop` can be exercised at a stable HTTPS URL, with
real identity, real object storage and real IAM.

The brief for that environment is explicit: simple to operate, inexpensive,
representative where it matters, and free of infrastructure adopted because it is
conventional — no Kubernetes, Redis, SQS, service mesh, autoscaling, multiple load
balancers, App Runner or module hierarchies. PostgreSQL stays both store and queue
(ADR 0002).

## Decision

**`develop` runs on one EC2 instance in `eu-central-1` under Docker Compose:**

```
caddy      TLS, HTTP→HTTPS, one hostname, /api/* → api, everything else → web
web        Next.js standalone, :3000, internal network only
api        FastAPI under uvicorn, :8000, internal network only
worker     aia-worker, no inbound port, AIA_WORKER_EXECUTORS=aia_executors.registry:build_registry
postgres   PostgreSQL 16 on a persistent volume, internal network only, nightly pg_dump to S3
```

with these AWS services used for real: **S3** (artifacts, backups), **Cognito**
federated to Google Workspace, **ECR**, **SSM** (Run Command, Parameter Store),
**IAM** (instance profile, GitHub OIDC role), **CloudWatch** (agent metrics, alarms),
**Bedrock** (instance-role access scoped to one pinned EU model; the adapter is a
separate change, ADR 0010).

The application runs with **`AIA_ENV=staging`**, which `Settings.is_production`
treats as production: SQLite refused, debug refused, wildcard CORS refused,
Cognito required with complete configuration, header identity unconstructible.
The environment is operationally called `develop`; the application's environment
value is what selects the guards, and the guards are the point.

### Why EC2 and not Lightsail

Lightsail is cheaper by roughly $20 a month and loses on the one axis that
matters: a Lightsail instance has no IAM instance role. S3, ECR and Bedrock access
would need static AWS keys on the host, which is the credential shape this
environment exists to avoid. EC2 gives role credentials, native SSM Run Command
(so CI deploys without SSH), Data Lifecycle Manager snapshots and CloudWatch
alarms from the same Terraform root. Sizing starts at `t3a.medium` (2 vCPU,
4 GB) and 80 GB gp3; growth is a variable change and a reboot.

### Why ECR and not GHCR

The host pulls images with its instance role. GHCR would need a personal access
token on the instance. One registry, images tagged by immutable git SHA with a
mutable `develop` alias for convenience only.

### Why an env file and not Secrets Manager

There are two application secrets: the PostgreSQL password and the Cognito
client's Google secret, and Cognito holds the second. Secrets Manager's rotation
machinery has nothing to rotate into yet. Values live in SSM Parameter Store as
`SecureString`, are written once by an operator into a root-only env file on the
host, and are never in an image, a log or the repository. Moving them to Secrets
Manager later is a change to one script.

## What this ADR does not decide

- **Production compute.** ECS Fargate remains the expected shape and App Runner
  remains open; neither is chosen here. Nothing in the application may depend on
  the single host: the database comes from `DATABASE_URL`, storage stays behind
  `ArtifactStore`, identity behind `IdentityProvider`, models behind
  `ModelGateway`, configuration from the environment.
- **A model vendor.** ADR 0010 records the proposed Bedrock route against ADR 0008.
- **High availability.** One host is one host. The develop database is synthetic
  data, backed up nightly, and the restore is rehearsed, not assumed.

## Migration path

```
TODAY (develop)                        LATER (production)
one EC2 host                           ALB
├ caddy                                ├ ECS web
├ web                                  └ ECS api
├ api                                  ECS worker
├ worker                                  │
└ postgres (volume, pg_dump → S3)         ▼
                                       RDS PostgreSQL
S3 · Cognito · ECR · SSM · Bedrock     S3 · Cognito · ECR · Secrets Manager · CloudWatch · Bedrock
```

Every arrow is deployment work: the same images, the same environment variables,
`DATABASE_URL` pointing at RDS, the env file replaced by task-definition secrets.

## Consequences

- One Terraform root (`infra/develop/`), one Compose file (`deploy/develop/`),
  one CD workflow. Readable in a sitting.
- Compose restarts containers; nothing restarts the host. A CloudWatch instance
  status check alarm and the EC2 auto-recovery action cover the host.
- Backups are `pg_dump` to an EU S3 bucket with lifecycle expiry, plus daily EBS
  snapshots. The restore procedure is in the runbook and is exercised on demand.
- CI's `startup-smoke` proves the processes boot; the deploy's `smoke.sh` proves
  the **deployed configuration**: staging guards active, header identity rejected,
  PostgreSQL unreachable from outside, worker executing, S3 round trip, deployed
  SHA visible.

## Revisit when

- More than one host is needed for load, or a second environment (production)
  is provisioned — then the ECS/RDS ADR is written and this one is superseded for
  that environment.
- Anything requires a secret the env-file scheme cannot hold safely.
