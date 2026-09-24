# `develop` — runbook

The first continuously deployed AIA environment: one EC2 host in `eu-central-1`
running Caddy, the Next.js client, the FastAPI API, the worker and PostgreSQL 16
under Docker Compose, with S3, Cognito, ECR, SSM and IAM used for real.
Decision record: [ADR 0009](../../docs/architecture/adr/0009-single-host-develop-environment.md).
Infrastructure: [`infra/develop/`](../../infra/develop/). Plan and audit:
[`.planning/plans/done/develop-deployment.md`](../../.planning/plans/done/develop-deployment.md).
Live at <https://aia-develop.art-chain.io/> since 2026-09-23.

The application runs with **`AIA_ENV=staging`**. That is deliberate: `staging`
is a deployed environment to the code, so every guard is active — Cognito only,
S3 only, no debug, no wildcard CORS, no header identity, a known build SHA.

```
feature/* ──PR──▶ develop ──CI green──▶ deploy-develop.yml ──▶ https://aia-develop.art-chain.io/
                                          build ▸ push to ECR ▸ SSM Run Command ▸ bin/deploy.sh
```

What is on the host:

```
/opt/aia/develop/
  docker-compose.yml   this directory's copy, at the deployed SHA
  Caddyfile
  .env                 root-only; written by bin/write-env.sh from SSM Parameter Store
  bin/                 deploy.sh · backup.sh · restore.sh · smoke.sh · write-env.sh · lib.sh
```

## First deployment (bootstrap)

Done once, by a person with AWS access. Everything after this is automatic.

1. **Human actions first.** Complete every item in
   [`infra/develop/README.md` § Human actions](../../infra/develop/README.md#human-actions)
   that precedes `terraform apply`: AWS account and region confirmed, hostname
   chosen, Google OAuth client created, budget approved, Bedrock model access
   enabled.
2. **Provision.** In `infra/develop/`: copy `terraform.tfvars.example` to
   `terraform.tfvars`, fill it in, then `terraform init && terraform apply`.
   Note the outputs: `public_ip`, `ecr_registry`, `cognito_*`, `github_deploy_role_arn`.
3. **DNS.** Point `dev.<domain>` (an `A` record) at `public_ip`. If the zone is
   in Route 53 and `route53_zone_id` was set, Terraform did this.
4. **GitHub.** Create the `develop` environment and set its variables from the
   Terraform outputs, per `infra/develop/README.md` § GitHub. Create the
   `develop` branch from `main` if it does not exist.
5. **Host bootstrap** — the instance's cloud-init installed Docker, Compose, the
   AWS CLI, the CloudWatch agent, the nightly backup timer and `/opt/aia/develop/`.
   Verify from your machine, with no SSH:

   ```bash
   aws ssm start-session --target <instance-id>          # an interactive shell, audited
   sudo -i
   cloud-init status --wait && docker --version && docker compose version
   ```

6. **Configuration.** Still in that session:

   ```bash
   cd /opt/aia/develop && bin/write-env.sh                # SSM parameters -> .env (root, 0600)
   ```

7. **First deploy.** Merge anything into `develop`, or run the
   *Deploy develop* workflow by hand with the SHA of `develop`'s head. Watch the
   Actions run: it builds the four images, pushes them by SHA, ships this
   directory to `s3://<ops-bucket>/deploy/<sha>.tar.gz`, and runs
   `bin/deploy.sh <sha>` on the host through SSM. The first run has no database
   to back up and says so.
8. **Seed.** From the SSM session:

   ```bash
   cd /opt/aia/develop
   docker compose run --rm --no-deps -T -e AIA_SEED_OWNER_EMAIL worker python -m aia_executors.seed
   ```

   Idempotent. Creates the organization, the operator named in
   `AIA_SEED_OWNER_EMAIL` as its owner, a synthetic client and study with a
   budget, a project, and one example workflow run. Re-running changes nothing.
9. **Sign in.** Open the public hostname (`https://aia-develop.art-chain.io/`).
   The gate sends you to `/login`; choose *Sign in* and authenticate with the
   Google Workspace account from step 8. You land on the NPC Panel 18.6.6
   interface (ADR 0012). `/studies` is AIA's own live view of the same API.

## Normal deployment

Merge a pull request into `develop`. Then:

1. CI runs (`.github/workflows/ci.yml`) with every existing check. Its final
   job dispatches only when they all succeed on a push to `develop`.
2. The dispatch runs `deploy-develop.yml` on the `develop` ref. GitHub requires
   the dispatchable workflow file to exist on the default branch (`main`) too,
   so register a compatible copy there before relying on it (done: PR #32,
   `7f8cb2a`; a later edit to the file is inert until released). Keeping the run
   on `develop` lets the environment's develop-only branch rule apply. It
   runs in the `develop` GitHub environment,
   assumes the deploy role through OIDC (no stored AWS keys), builds
   `aia-api`, `aia-worker`, `aia-legacy-panel` and `aia-web` at the verified SHA, pushes them to ECR
   tagged `<sha>` (and `develop` as a convenience alias), uploads this directory
   as `deploy/<sha>.tar.gz`, and sends one SSM command to the host.
3. On the host, `bin/deploy.sh <sha>`: pull → backup → `alembic upgrade head`
   → write `AIA_IMAGE_TAG` → `compose up --wait` → `bin/smoke.sh`.
4. The workflow waits for the command, prints its output, and fails if any step
   or smoke check failed.

Refresh `https://aia-develop.art-chain.io/` — the footer and `/version` show the SHA;
`/api/v1/health` shows the same SHA under `build.sha`.

## The 18.6.6 interface on the product hostname

Since [ADR 0012](../../docs/architecture/adr/0012-legacy-interface-as-product-facade.md)
`https://aia-develop.art-chain.io/` is the NPC Panel 18.6.6 interface, served by
the `legacy-panel` container, with AIA in front of it. The Caddyfile routes:

| Path | Goes to |
|---|---|
| `/api/v1/*` | the AIA API |
| `/login`, `/logout`, `/auth/*`, `/config`, `/version`, `/studies*`, `/_next/*`, `/skin/*`, `/favicon.ico`, `/icon.svg`, `/apple-icon.png` | the AIA web client |
| `/` | after `forward_auth` to `GET /api/v1/panel/gate`, the web client's `/interface-document`, which fetches the unit's `/` and adds the AIA skin when it applies ([ADR 0013](../../docs/architecture/adr/0013-interface-skin-at-the-facade.md)) |
| `/interface-document` (requested directly) | 404 |
| everything else | `legacy-panel`, after `forward_auth` to `GET /api/v1/panel/gate` |

- **Who gets in.** An active member of the organization whose role is `OWNER`
  or `ADMIN`. Anyone else who signs in is shown a message and can still use
  `/studies`. To let someone in, make them an organization admin; there is no
  separate list.
- **How.** `/login` turns the Google sign-in into an HttpOnly session cookie
  (`aia_panel`) through `POST /api/v1/panel/session`; the gate re-verifies it on
  every request and Caddy strips it before the request reaches the unit.
  Opening a session is recorded in the access audit (`LEGACY_PANEL_SESSION`,
  `LEGACY_PANEL_DENIED`); individual requests are not.
- **Signing out.** `/logout` clears the cookie and the Cognito session.
- **Switching it off.** Set `AIA_LEGACY_PANEL_ENABLED: "false"` on the `api`
  service and `docker compose up -d api`. The gate then answers 404 to
  everything, so nothing reaches the unit from the product hostname; `/` shows
  a 404 until the Caddyfile routes it elsewhere.
- **The oracle hostname** (`AIA_LEGACY_HOSTNAME`, basic auth) is unchanged and
  reaches the same container, so both share its state.
- **When `/` shows an error.** `docker compose ps legacy-panel`: the unit needs
  its data bundle synced by `bin/deploy.sh` (OI-39). A 401 or 403 JSON body on a
  page means the gate refused it; the `code` field says why (`unauthenticated`,
  `legacy_panel_denied`, `cross_origin`). A 502 on `/` means the gate admitted
  the request and the unit is not answering: the response carries
  `X-AIA-Skin: bypassed-unreachable` when the web client could not reach it, and
  no such header when the web client itself is down.
- **The skin** (ADR 0013). `AIA_INTERFACE_SKIN_ENABLED` on the `web` service;
  `"false"` serves the unit's document byte-for-byte. Every response to `/`
  says what happened in `X-AIA-Skin`: `applied`, `bypassed-disabled`, or
  `bypassed-hash-mismatch` when the unit's document is not the pinned
  `ui_app.html` (a regenerated unit; the web log has an
  `interface_skin_bypassed` line with the hash it received). Switching it:
  change the value and `docker compose up -d web`.
- **The site does not depend on the unit** (OI-44). Caddy starts without it,
  the deploy waits only on AIA's services, and the unit's health is a smoke
  check: an unhealthy unit fails the deploy but `/login`, `/studies` and the API
  stay up. The deploy also loads the Caddyfile with this host's `.env` before it
  touches anything, and stops if it does not load.

### Switching the unit on

The 18.6.6 interface needs one value under `/aia/develop/` in Parameter Store
and its data bundle in the ops bucket. The oracle hostname for the parity harness
needs three more, and is optional. Terraform does not create any of them yet
(OI-44). From a shell with the operator's AWS credentials, `eu-central-1`:

```bash
# Required. Where the data bundle lives in the ops bucket, as uploaded once with
#   aws s3 sync <extract_legacy.py --data-out dir> s3://<ops-bucket>/<prefix>/
# (develop: legacy-data/86b70bfb5c1b, set 2026-09-23)
aws ssm put-parameter --name /aia/develop/aia_legacy_data_prefix --type String --value legacy-data/<bundle-id>

# Optional: the oracle hostname (an A record at the host's public IP) and its
# basic-auth gate, for the parity harness (OI-39). Not needed for the interface.
aws ssm put-parameter --name /aia/develop/aia_legacy_hostname --type String --value legacy.aia-develop.art-chain.io
aws ssm put-parameter --name /aia/develop/aia_legacy_basic_user --type String --value oracle
aws ssm put-parameter --name /aia/develop/aia_legacy_basic_hash --type SecureString \
  --value "$(docker run --rm caddy:2-alpine caddy hash-password --plaintext '<password>')"
```

Then re-run *Deploy develop*. Every deploy rewrites `.env` from Parameter Store
(`bin/write-env.sh`) before `bin/deploy.sh`, so nothing is run on the host by
hand. The smoke test reports `legacy: the 18.6.6 unit is healthy` when it worked
(first on 2026-09-23, run 12). Without the hostname values the oracle block binds
`legacy-unconfigured.localhost` with a gate nobody can pass, so the product
hostname is unaffected.

## Logs

From an SSM session, in `/opt/aia/develop`:

```bash
docker compose ps                              # state and health of every service
docker compose logs -f --tail=200 api          # api | worker | web | caddy | postgres
docker compose logs --since=1h worker | grep '"level": "ERROR"'
docker compose logs worker | grep '"run_id": "RUN-…"'   # one run's story, every step and attempt
```

The API and worker log one JSON object per line: `request_id` on every API line,
`worker_id`, `run_id`, `step_id`, `attempt_id` on the worker's. Caddy logs JSON
access lines. Container logs rotate at 5 × 20 MB per service; the CloudWatch
agent ships them to the log group `/aia/develop` (`infra/develop`).

Host: `journalctl -u docker`, `journalctl -u aia-backup.service`, `df -h /`.

## Database

**Connect** (debugging only; the port is not published anywhere):

```bash
docker compose exec postgres psql -U aia -d aia
```

**Migrate.** Only `bin/deploy.sh` migrates, as one step, from the api image at
the SHA being deployed. To run it by hand: `docker compose run --rm --no-deps -T api alembic upgrade head`.
`alembic current` from the same image shows the applied revision.

**Back up.** Nightly at 02:30 UTC (`aia-backup.timer`) and before every
migration: `bin/backup.sh [label]` → `s3://<ops-bucket>/backups/aia-<utc>-<label>.dump`.
The bucket is EU-resident, encrypted, versioned, private; objects expire after
30 days (Terraform). A daily EBS snapshot of the data volume (Data Lifecycle
Manager, 7 kept) is the second copy.

**Restore — rehearsal** (does not touch the live database; run monthly and after
any change to the backup path):

```bash
bin/restore.sh --test latest       # or a specific backups/… key
```

Restores into a scratch database inside the running container, prints table
count, alembic revision and row counts for organizations, studies, runs and
artifacts, then drops it.

**Restore — for real:**

```bash
bin/restore.sh --live <key|latest>
```

Dumps the current contents first (`pre-restore`), stops `api` and `worker`,
replaces the `aia` database, starts them, runs the smoke test.

## AI

There is **no live model call on this revision**. The `ModelGateway` contract
and provider adapter interfaces exist, but no Bedrock adapter, live transport
or governed EU route is wired into the API or worker. The smoke test reports
the AI check as `NOT_RUNNABLE`, never as a pass. What the environment already
provides for it:

- the instance role may call `bedrock:InvokeModel` on the one pinned EU model
  in `infra/develop/terraform.tfvars` (`bedrock_model_id`), and nothing else;
- no static AWS credentials exist anywhere in the stack;
- [ADR 0010](../../docs/architecture/adr/0010-bedrock-eu-inference-route.md)
  records the proposed route `bedrock-eu-primary` and the checks a human performs.

When the Bedrock adapter and its governed route land, inspect: the model policy and
route in the api/worker environment (`AIA_MODEL_POLICY_*`, `AIA_EGRESS_ROUTES_*`
as that change defines them), usage in the `ai_usage_events` table (`provider`,
`route_id`, `model`, `provider_request_id`, tokens, `cost_usd`, `input_fingerprint`,
`runtime_version`), and failure classification on the attempt row
(`step_attempts.error_json.failure`). This section is updated by that change.

## Seed / reset

```bash
docker compose run --rm --no-deps -T -e AIA_SEED_OWNER_EMAIL worker python -m aia_executors.seed           # idempotent
docker compose run --rm --no-deps -T -e AIA_SEED_OWNER_EMAIL worker python -m aia_executors.seed --reset   # drop the seeded org's data, then seed
```

Synthetic data only. `--reset` removes only what the seed created (its
organization slug), never anything else.

To start completely fresh: `docker compose down -v` (destroys the PostgreSQL
volume and Caddy's certificates), then `bin/deploy.sh <sha>` and the seed.

## Rollback

Deploy the previous SHA. The workflow accepts a SHA by hand (*Run workflow* →
`sha`; the button exists only once the workflow is on `main`), or from the host:

```bash
bin/deploy.sh <previous-sha> --no-migrate
```

`--no-migrate` leaves the schema at its current head, which the previous
application revision must tolerate: AIA migrations are additive between
neighbouring revisions, and CI proves every migration reversible, but
**`alembic downgrade` is never run automatically**. If a rollback genuinely needs
the schema moved back, a person decides it, takes a backup, runs
`docker compose run --rm --no-deps -T api alembic downgrade <rev>` from the
*newer* image (the one that knows the migration), and then deploys the older SHA.

Previous SHAs are in ECR (`aws ecr list-images --repository-name aia-api`) and in
the *Deploy develop* run history.

## Resize

Change `instance_type` in `infra/develop/terraform.tfvars` and `terraform apply`
(the instance stops, resizes and starts; ~2 minutes of downtime; the volume and
its data are untouched). Disk: raise `root_volume_gb`, apply, then on the host
`sudo growpart /dev/nvme0n1 1 && sudo resize2fs /dev/nvme0n1p1`. Compute for the
worker alone can also grow later by moving it to a second Compose host with the
same `DATABASE_URL`; nothing in the application assumes one host.

## Destroy

1. `bin/backup.sh final` if anything is worth keeping (synthetic data; normally not).
2. `terraform destroy` in `infra/develop/`. The artifacts and ops buckets have
   `force_destroy = true` because they hold synthetic data only; the Cognito
   user pool has deletion protection **off** for the same reason. Route 53
   records created by Terraform go with it; an externally managed `A` record
   must be removed by hand.
3. Delete the `develop` GitHub environment's variables if the account is going
   away, and revoke the Google OAuth client in Google Cloud.

## Monthly cost

Estimated for `eu-central-1`, on-demand, September 2026 list prices; verify
against the AWS calculator before approving the budget.

| Item | USD / month |
|---|---:|
| EC2 `t3a.medium` (2 vCPU, 4 GB), on-demand, 730 h | ~32 |
| EBS gp3 80 GB root volume | ~8 |
| Elastic IP (in use) | ~4 |
| EBS snapshots, 7 daily × ~10 GB changed | ~4 |
| S3 artifacts + ops (< 20 GB, few requests) | ~1 |
| ECR (4 repositories, ~10 tags kept, ~3 GB) | ~1 |
| CloudWatch (agent metrics, 2 GB logs, 3 alarms) | ~4 |
| Route 53 hosted zone (only if DNS is in AWS) | 0.5 |
| Cognito (≤ 10,000 MAU, Essentials tier) | 0 |
| SSM Parameter Store standard, Run Command | 0 |
| **Fixed total** | **~55** |
| Bedrock (variable; Class C smoke only until the adapter lands) | metered |

The AWS Budget in `infra/develop` alerts at 80 % and 100 % of `monthly_budget_usd`
(default 100). Bedrock spend is governed in the application by study budgets and
reservations, never by choosing a cheaper model automatically.

## What this environment is not

Not production. One host, one availability zone, a database on a local volume
with nightly dumps. Synthetic data only. The path to ECS and RDS is in ADR 0009
and is deployment work, not application work.
