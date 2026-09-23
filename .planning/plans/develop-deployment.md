# The first continuously deployed `develop` environment

**Status:** in progress · **Owner:** integration-architecture · **Started:** 2026-09-23

Anchors are against `main` @ `a15be65` unless stated.

## Problem

Nothing in this repository runs anywhere but a developer's machine and CI. There
is no container image, no deployment target, no CD, no `develop` branch, and the
web client has never called the real API. A change merged to `main` is verified
by CI and then goes nowhere, so the architecture's deployed-environment guards
(`AIA_ENV=staging`, Cognito-only identity, S3 storage, EU residency) have never
been exercised against real AWS services.

## Audit of `main` @ `a15be65` (step 1 of the brief)

### What already exists

| Area | State | Anchor |
|---|---|---|
| API | FastAPI, `/api/v1/health`, `/api/v1/ready`, clients / studies / grants / members / audit, study-scoped projects. Typed settings; `staging` **counts as production** for every guard | `apps/api/src/aia_api/config.py:93` (`is_production`), `routers/*.py` |
| Identity | Cognito RS256 verifier, JWKS cache, `token_use=id` default, audience check; `development` header provider refused outside `local`/`test` by two guards | `apps/api/src/aia_api/identity/cognito.py`, `config.py:98-105`, `config.py:136-149` |
| Authorization | `Organization → Client → Study → grant → role`, resolved from PostgreSQL per request; 404-not-403 | `packages/aia_core/src/aia_core/application/scope.py` |
| Workflow engine | Runs, steps, attempts, `FOR UPDATE SKIP LOCKED`, leases, reservations, gates, recovery, resume | `infrastructure/workflow_repository.py` |
| Worker | Complete loop (claim, heartbeat, execute, record, reconcile, `SIGTERM` release), JSON logs. **Only executor: `scripted` (tests)** | `apps/worker/src/aia_worker/`, `testing.py:74` |
| Storage | `ArtifactStore` with S3 / filesystem / memory; `ArtifactRepository` with reuse and provenance. **Not wired into any process**: no settings, no route, no executor uses it | `infrastructure/storage.py:379`, `artifact_repository.py:148`; `grep S3ArtifactStore apps/` → none |
| AI | Provider policy, budget check, residency egress boundary, failure taxonomy. **No `ModelGateway`, no adapter, no ledger on `main`** | `domain/providers.py`, `domain/residency.py`, `docs/architecture/ai-runtime.md:3` |
| Migrations | 7 Alembic revisions; URL from `DATABASE_URL`; CI checks upgrade / drift / downgrade | `migrations/versions/` |
| CI | Blocking lint, types, layering, exposure, migrations, tests on PostgreSQL and SQLite, worker processes, API contract, frontend build, startup smoke. Runs on `main` pushes and PRs only | `.github/workflows/ci.yml:7-10` |
| Local dev | `docker-compose.yml` with PostgreSQL 16 and MinIO. No Dockerfiles anywhere | `docker-compose.yml` |
| Infra | None. No Terraform, no `deploy/`, no `infra/` | — |
| Build identity | `Settings.version = "0.1.0"`, static. No git SHA anywhere | `config.py:46` |

### What is missing for deployment

1. Container images for `api`, `worker`, `web` and a way to tag them by SHA.
2. A deployment target (compute, static IP, DNS, TLS) and the Compose file that runs there.
3. Storage settings in the API and worker composition roots; today `.env.example`
   names `AIA_STORAGE_*` keys that **no code reads** (`.env.example:25-28`).
4. Cognito user pool, Google federation, and a browser login flow (the web client has none).
5. A `develop` branch, CI on it, and a CD workflow with OIDC → AWS.
6. Backups, restore, smoke tests, runbook, cost estimate.
7. A real step executor and workflow routes: nothing on `main` lets a browser start a run or a worker do anything but a scripted test step.
8. A seed command for synthetic develop data (the only provisioning code is inline in CI's smoke job, `ci.yml:344-380`).

### Frontend: real vs mock (truth table)

Measured by reading every page under `apps/web/src/app` @ `a15be65`. There is no
`fetch`, no API client, no `NEXT_PUBLIC_*` variable and no auth code in `apps/web`.

| Surface | State | Evidence |
|---|---|---|
| Dashboard | **mock** | `app/org/[orgSlug]/dashboard/page.tsx:2` imports `mockAlerts, mockCases` |
| Studies ("cases") | **mock** | `app/org/[orgSlug]/cases/page.tsx:2` imports `mockCases` |
| Project / case workspace | **mock** | `components/aia/CaseWorkspaceLayout.tsx`, gates 1–5 from `lib/mock.ts:83` |
| Workflow | **mock** | `mockGates`; approval buttons have no handler |
| Sociomapping | **mock, and the superseded manual SOP** | `cases/[caseId]/sociomapping/page.tsx:7` "Manual Sociomapping SOP" |
| Reports / document editor | **mock, browser-local** | `lib/doc.ts` + `lib/storage.ts` (localStorage) |
| Authentication | **absent** | no auth code; root page links straight to `/org/aia-demo/dashboard` |

The vocabulary (cases, five gates, import pack) is the archived MVP's, not the
production domain (`Organization → Client → Study → Project → WorkflowRun`).
The design-system plan (`plans/design-system.md`) already schedules the rewire;
this deployment does not redesign the client. It adds the smallest real slice
beside the demo and labels the demo as such.

### AI runtime: real vs planned

| Piece | `main` | PR #28 (`claude/eager-mendel-3bom5p`, unmerged, **conflicts with `main`**, no CI run recorded) |
|---|---|---|
| Provider policy, budget, residency | real, tested | unchanged |
| `ModelGateway` contract (ADR 0005 A) | **absent** | `domain/ai_execution.py`, `application/model_gateway.py` |
| Model registry / policy | absent | `domain/ai_models.py`, fails closed |
| Adapters | absent | Anthropic HTTP, OpenAI HTTP, Claude Code CLI — over recorded transports only; **no live transport, no Bedrock adapter** |
| Usage ledger | absent | `ai_usage_events` migration `1cd2a5acd29f` |
| Step executor calling the gateway | absent | absent (named as platform-runtime's, `docs/architecture/ai-step-executor-contract.md`) |
| Approved egress route declared | none (`EgressPolicy()` empty = refuse all) | none — "D6 approved route, D7 transport, D8 credentials" deferred |

**Nothing on `main` can call a model, governed or otherwise.** That is the
correct fail-closed state and it is what this deployment inherits.

### Contradictions between the deployment brief and the repository

| # | Brief | Repository | Resolution taken here |
|---|---|---|---|
| C1 | "At least one governed Bedrock call works through `ModelGateway`" (done-criteria 11–13) | `ModelGateway` does not exist on `main`; PR #28 builds it and is unmerged, conflicting, and adds no Bedrock adapter | **Reported, not faked.** The deployment provisions everything the route needs (instance role scoped to one pinned EU model, region, no static keys) and records the route as ADR 0010 *Proposed*. The Bedrock `ProviderAdapter` is built **after** PR #28 merges, against its `ProviderAdapter`/`HttpTransport` protocols, as a separate PR. Building a second gateway here would fork ADR 0005 A; merging #28 into `develop` is a decision the brief reserves to a human ("do not merge arbitrary open PR branches") **Update 2026-09-23:** #28 merged into `main` at `676bc1f`; the follow-up change merges `main` into `develop`, so the gateway is on both branches and the adapter PR can start (D12 resolved) |
| C2 | Single AWS host running Compose | ADR index and four documents say the compute service is *undecided* between ECS Fargate and App Runner | ADR 0009 records the single host as the **develop** compute decision only, with the ECS/RDS migration path; production compute stays undecided |
| C3 | Bedrock as the initial provider | ADR 0008 selects no vendor; ADR index: "model provider … not selected" | ADR 0010 is the vendor record ADR 0008 asks for, *Proposed* until a human confirms terms and model availability |
| C4 | `Provider` for Bedrock | `Provider` enum has `claude_code_subscription`, `anthropic`, `openai` only; parity tests pin these | A new `aws_bedrock` provider id lands with the adapter PR, not here |
| C5 | Brief's `develop` protection: "deployment only after CI" | CI's `startup-smoke` job runs with `AIA_ENV=local` and the header identity provider; useful, but not the deployed configuration | The develop smoke tests (`deploy/develop/bin/smoke.sh`) assert the staging guards from outside: header identity rejected, unauthenticated 401, PostgreSQL unreachable |
| C6 | `CLAUDE.md` target lists "Amplify … SQS" | ADR 0002 forbids SQS; the brief forbids Amplify-style split hosting for develop | `CLAUDE.md` target line corrected in this change set |
| C7 | Frontend must implement Cognito login | `plans/design-system.md` owns the client rewire and sequences the "first real vertical slice" after chunks 0–3 | Login and one real page are added **beside** the demo, under `/studies`, without touching the demo pages' design; the design-system plan keeps ownership of the rewire |

## Approach

**One host, real managed services, no new application coupling.** Caddy, Next.js,
FastAPI, the worker and PostgreSQL 16 run under Docker Compose on one EC2
instance in `eu-central-1`. S3, Cognito, ECR, SSM, IAM and Bedrock are the real
AWS services. Every process reads its configuration from the environment
exactly as it would on ECS (`DATABASE_URL`, `AIA_STORAGE_*`, `AIA_COGNITO_*`), so
moving to ECS/RDS later is deployment work.

**EC2 over Lightsail.** Compared on the brief's eight axes:

| Axis | Lightsail (2 vCPU / 4 GB / 80 GB) | EC2 `t3a.medium` + 80 GB gp3 + EIP |
|---|---|---|
| Monthly cost | ~$24 bundle | ~$32 instance + ~$8 disk + ~$4 EIP ≈ $44 |
| IAM integration | **No instance role.** Bedrock, S3 and ECR would need static keys on the host — the brief forbids exactly that | Instance profile: role credentials, rotated by AWS, never on disk |
| SSM | Only via hybrid activation (a registration secret to manage) | Native; Run Command from GitHub Actions with no SSH |
| Deployment automation | SSH keys in GitHub, or the activation above | `aws ssm send-command` under the OIDC role |
| Disk snapshots | Manual or Lightsail's own schedule | Data Lifecycle Manager policy in Terraform |
| Static IP | Included | Elastic IP (~$3.65) |
| Monitoring | Lightsail metrics only | CloudWatch agent, alarms on disk / CPU / instance status |
| Operational complexity | Lower on paper, higher in practice once IAM is worked around | One Terraform root, ~250 lines |

The $20/month Lightsail saving buys static AWS credentials on the host. Not
taken. Sizing: `t3a.medium` (2 vCPU, 4 GB) and 80 GB gp3; resizing is
`instance_type` in `terraform.tfvars` plus one reboot (runbook § Resize).

**ECR over GHCR.** The host pulls with its instance role and no registry secret;
GHCR would need a PAT on the instance. Images are tagged `<git-sha>` (immutable)
and `develop` (convenience only). One registry.

**Secrets: one protected env file on the host, written once by an operator from
SSM Parameter Store.** Secrets Manager adds rotation machinery nothing here
consumes yet; Parameter Store `SecureString` costs nothing and is readable by the
instance role. Terraform creates the parameter *names*; a human writes the values
(§ Human actions). Bedrock and S3 use the instance role, so the only secrets are
the PostgreSQL password and the Google OAuth client secret (held by Cognito, not by
AIA).

**Migrations run once, as a deploy step**, in a one-off `api` container
(`alembic upgrade head`) after a `pg_dump`, before the application containers are
replaced. Neither the API nor the worker migrates on start. Rollback redeploys a
previous SHA; schema rollback is a separate, documented, human decision.

**The vertical slice is deterministic.** With no gateway on `main`, the smallest
honest browser → API → PostgreSQL → worker → S3 → browser flow is a
`develop_snapshot` workflow: one step that reads the project's current revision
under the lease-issued scope, writes a JSON artifact through `ArtifactRepository`
(so S3, reuse and provenance are all real), and completes. The brief allows "AI
call or deterministic stage" for this milestone. The AI step is the next slice;
C1 resolved when #28 reached `main` (D12).

**Executors get their own package.** `layer_check` forbids `apps/worker`
importing repositories, storage or `domain.project` (`tools/layer_check.sh:85-88`);
that is the seam working. Step implementations therefore live in
`apps/executors/src/aia_executors/`, a layer 4b that depends on
`aia_worker.executor` and `aia_core`, and is named by
`AIA_WORKER_EXECUTORS=aia_executors.registry:build_registry`.

## Trade-off accepted

The develop environment proves the deployed architecture end to end **except the
model call**, which waits on the gateway PR; in exchange nothing here forks ADR
0005 or merges unreviewed work into `develop`.

## Chunks

- [x] 1. This plan, ADR 0009 (single-host develop), ADR 0010 (Bedrock EU route, Proposed) — lands: docs
- [x] 2. Build identity and storage settings — `AIA_BUILD_SHA` in `/health`, worker start log and the web client; typed `AIA_STORAGE_*` settings in both composition roots, S3 required under `staging`/`production` — lands: code + tests + `.env.example`
- [x] 3. Containers — `apps/api/Dockerfile`, `apps/worker/Dockerfile`, `apps/web/Dockerfile` (standalone output), non-root, SHA baked in — lands: images built locally
- [x] 4. Single host — `deploy/develop/`: Compose, Caddyfile, `env.example`, `bin/deploy.sh`, `bin/backup.sh`, `bin/restore.sh`, `bin/smoke.sh`, runbook — lands: files + runbook
- [x] 5. Terraform — `infra/develop/`: instance + role + EIP + DLM snapshots, S3 artifacts + backups, ECR ×3, GitHub OIDC role, SSM parameters, Cognito pool + Google IdP + client + domain, budget, optional Route53 — lands: files + tfvars example
- [x] 6. Vertical slice, backend — `apps/executors` with `develop_snapshot`; run routes under `/studies/{id}/projects/{pid}/runs`; artifact read route; `application/develop_seed.py` + `tools/seed_develop.py` — lands: code + tests + layer rules
- [x] 7. Vertical slice, frontend — Cognito PKCE login, `lib/api.ts`, `/studies` pages, version footer, demo pages labelled — lands: code, lint/tsc/build green
- [x] 8. CI/CD — CI on `develop`; `deploy-develop.yml`: `workflow_run` → build → ECR → SSM → smoke — lands: workflows
- [x] 9. Docs sync, `make verify`, `develop` branch from `main`, PR, cost table, human actions — lands: docs + branch + PR

## What was verified, and what was not

Verified in the session that wrote this (Python 3.12, PostgreSQL 16.13, Node 22):
the whole Python suite on PostgreSQL and SQLite, `mypy --strict`, `layer_check`,
`exposure_check`, `alembic check`, web lint / `tsc` / production build, the
standalone web server, `shellcheck` on the host scripts, `docker compose config`,
`terraform fmt`, and both workflow files parsing.

**Not verified** — the sandbox's egress policy refused Docker Hub, Amazon ECR
Public's anonymous quota and the Terraform provider registry: `docker build` of
the three images, `terraform validate`/`plan`, Caddy configuration validation,
and the deploy workflow itself. Each is exercised for the first time by the
human actions in `infra/develop/README.md`; the workflow fails loudly on any of
them rather than reporting a deployment that did not happen.

## Findings filed along the way

OI-33 (a repository `ScopeDenied` is a 500 in the projects and scope routers),
OI-34 (no web test runner), OI-35 (browser session in `sessionStorage`, accepted
for develop). OI-3 closed: `develop` is the second branch it asked for.

## Not done here, deliberately

- The Bedrock `ProviderAdapter` and the `aws_bedrock` provider id (C1, C4).
- The `apps/web` rewire and design system (owned by `plans/design-system.md`).
- Production compute, RDS, ALB: ADR 0009 § Migration path only.
- Repository rules and environment protection (a human, § Human actions).

## Review outcome

Filled in when the plan is archived.
