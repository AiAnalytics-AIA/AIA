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
   Google Workspace account from step 8. You land on AIA's client directory,
   `/app/clients` (ADR 0015). The classic 18.6.6 interface is at `/classic`,
   and a stage not yet rebuilt links there with a way back.

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

### Registry credentials

`bin/deploy.sh` pulls from ECR through Amazon's credential helper
(`docker-credential-ecr-login`), which asks the instance role on each pull. No
registry token is stored: `ecr_login` in `bin/lib.sh` names the helper for
`AIA_IMAGE_REGISTRY` in root's `~/.docker/config.json`, deletes the token an
earlier `docker login` left there, and exports `AWS_ECR_DISABLE_CACHE=true` so the
helper does not keep its own plain-text copy in `~/.ecr/cache.json`. The first
deploy after this change installs the Ubuntu package `amazon-ecr-credential-helper`
itself; there is nothing to do by hand and no Terraform change.

If the package cannot be installed, the deploy still pulls with `docker login`,
and its log says `WARNING: the ECR credential helper is not installed`. Docker's
"credentials are stored unencrypted" warning then comes back. Install the package
(`sudo apt-get install amazon-ecr-credential-helper`) and deploy again.

An operator pulling by hand outside these scripts should
`export AWS_ECR_DISABLE_CACHE=true` first, or the helper writes its cache.

## AIA and the 18.6.6 unit on the product hostname

Since [ADR 0015](../../docs/architecture/adr/0015-client-first-product-interface.md)
`https://aia-develop.art-chain.io/` is AIA: `/` redirects to the client
directory, `/app/clients`. The NPC Panel 18.6.6 interface, served by the
`legacy-panel` container, is a labelled, temporary hand-off at `/classic`, and
the unit still answers its own paths, which the React stages read (OI-58). The
Caddyfile routes:

| Path | Goes to |
|---|---|
| `/api/v1/*` | the AIA API |
| `/login`, `/logout`, `/auth/*`, `/config`, `/version`, `/studies*`, `/_next/*`, `/skin/*`, `/favicon.ico`, `/icon.svg`, `/apple-icon.png` | the AIA web client |
| `/` | `302 /app/clients`; nothing is served |
| `/app`, `/app/*` | after `forward_auth` to `GET /api/v1/panel/gate`, the web client: AIA, Clients → client workspace → study → stages; 404 while `AIA_INTERFACE_REHOME_ENABLED` is off |
| `/classic` | after the same `forward_auth`, the web client's `/interface-document`, which fetches the unit's `/` and adds the AIA skin ([ADR 0013](../../docs/architecture/adr/0013-interface-skin-at-the-facade.md)) and `/skin/handoff.js` (its "Zpět do AIA" bar) when it applies |
| `/interface-document` (requested directly) | 404 |
| Legacy Claude Code setup/status and `/api/settings/{api_keys,anthropic_check,ai_check,ai_diagnose}` | after the gate, HTTP 410; no direct credentials or provider probes on the product hostname |
| `/api/*`, `/files/*`, `/artifacts/*`, `/project-attachments/*`, `/brand/*`, `/fullsim-arena`, `/health`, `/status` | `legacy-panel`, after the same `forward_auth` |
| everything else | the web client (its own 404 for a path it does not know); never the unit |

`tools/caddy_routes.py` checks this table against the adapted Caddyfile in CI;
`tools/develop_routing_proof.py` and `tools/develop_routing_journey.mjs` run the
real file locally, with a browser, when the routing changes. The proof also runs
the worker as this host does (`aia_executors.registry`, no fieldwork source) and
shows a research run parking at fieldwork, `ai_runtime_unavailable` (ADR 0016).

- **Who gets in.** An active member of the organization whose role is `OWNER`
  or `ADMIN`. Anyone else who signs in is shown a message and can still use
  `/studies`. To let someone in, make them an organization admin; there is no
  separate list. This is a temporary restriction while the stages read the
  single-tenant unit, not the target model (OI-59); inside AIA each person
  still sees only the clients and studies they hold grants in.
- **How.** `/login` turns the Google sign-in into an HttpOnly session cookie
  (`aia_panel`) through `POST /api/v1/panel/session`; the gate re-verifies it on
  every request and Caddy strips it before the request reaches the unit.
  Opening a session is recorded in the access audit (`LEGACY_PANEL_SESSION`,
  `LEGACY_PANEL_DENIED`); individual requests are not.
- **Signing out.** `/logout` clears the cookie and the Cognito session.
- **Switching it off.** Set `AIA_LEGACY_PANEL_ENABLED: "false"` on the `api`
  service and `docker compose up -d api`. The gate then answers 404 to
  everything, so nothing reaches the unit from the product hostname -- and,
  while `/app` sits behind the same gate (OI-59), AIA's pages answer 404 too:
  `/` still redirects, to a 404. `/login`, `/studies` and the API stay up.
- **The oracle hostname** (`AIA_LEGACY_HOSTNAME`, basic auth) is unchanged and
  reaches the same container, so both share its state.
- **When `/classic` or a research stage shows an error.** `docker compose ps legacy-panel`: the unit needs
  its data bundle synced by `bin/deploy.sh` (OI-39). A 401 or 403 JSON body on a
  page means the gate refused it; the `code` field says why (`unauthenticated`,
  `legacy_panel_denied`, `cross_origin`). A 502 on `/classic` means the gate admitted
  the request and the unit is not answering: `/classic`'s response carries
  `X-AIA-Skin: bypassed-unreachable` when the web client could not reach it, and
  no such header when the web client itself is down.
- **The skin** (ADR 0013). `AIA_INTERFACE_SKIN_ENABLED` on the `web` service,
  `"true"` on develop;
  `"false"` serves the unit's document byte-for-byte. Every response to `/classic`
  says what happened in `X-AIA-Skin`: `applied`, `bypassed-disabled`, or
  `bypassed-hash-mismatch` when the unit's document is not the pinned
  `ui_app.html` (a regenerated unit; the web log has an
  `interface_skin_bypassed` line with the hash it received). Switching it:
  change the value and `docker compose up -d web`.
- **A Caddyfile change** reaches the running Caddy because its hash is part of
  the caddy service's configuration (`bin/lib.sh`, `AIA_CADDYFILE_SHA256`), so
  `compose up` recreates Caddy when the file changed and not otherwise. The
  smoke check *caddy: running the deployed Caddyfile* fails if it did not; the
  remedy is `docker compose up -d --force-recreate caddy` (OI-45).
- **The site does not depend on the unit** (OI-44). Caddy starts without it,
  the deploy waits only on AIA's services, and the unit's health is a smoke
  check: an unhealthy unit fails the deploy but `/login`, `/studies` and the API
  stay up. The check waits out the unit's `starting` state (its 120 s start
  period, while it hydrates) for at most `LEGACY_START_WAIT_SECONDS`, default
  150, then judges; deploy runs 29 and 30 failed on `starting` with every other
  check green. The deploy also loads the Caddyfile with this host's `.env` before it
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

The worker can run AI respondent fieldwork (the research `ai_runtime` source)
through `GovernedModelGateway` over ADR 0010's route `bedrock-eu-primary`. **It is
off** (`AIA_AI_RUNTIME_ENABLED=false`): a research run parks at fieldwork
(`WAITING_PROVIDER` / `ai_runtime_unavailable`) until an operator configures it,
and ADR 0010 is still *Proposed*. No live model call has been made from this
environment. The smoke test's AI check is still `NOT_RUNNABLE`.

What the environment provides:

- the instance role `aia-develop-instance` may call `bedrock:InvokeModel` on the
  pinned EU profile (`bedrock_model_id`) and on its foundation model in the
  profile's destination regions (`bedrock_destination_regions`), and nothing else;
- no static AWS credentials exist anywhere in the stack, and the signer refuses
  any credential that is not an instance or container role.

**To switch it on** (only after ADR 0010's two open rows are recorded -- the
human terms review and the dated `eu-central-1` price): create these parameters
under `/aia/develop/` (lower-case names; `bin/write-env.sh` upper-cases them),
redeploy, and read the worker's start-up log: an incomplete or unsafe value stops
the worker with the key named.

| Parameter | Value |
|---|---|
| `aia_ai_runtime_enabled` | `true` |
| `aia_ai_route_id` | `bedrock-eu-primary` |
| `aia_bedrock_region` | `eu-central-1` |
| `aia_bedrock_model_id` | the same id as Terraform's `bedrock_model_id` |
| `aia_ai_policy_version` | a new name per change of model or price, e.g. `aia-bedrock-develop-2026-09` |
| `aia_bedrock_input_usd_per_mtok`, `aia_bedrock_output_usd_per_mtok` | from the Bedrock pricing page, the date recorded in ADR 0010 |
| `aia_bedrock_max_output_tokens`, `aia_bedrock_context_window_tokens` | the model's documented limits |
| `aia_ai_route_eu_processing_approved`, `aia_ai_route_excluded_from_training` | `true` only once ADR 0010's review is recorded |
| `aia_ai_route_approved_for` | `CLASS_C_INTERNAL` (ADR 0010: nothing wider without a reviewed change) |
| `aia_ai_route_retention_days` | **leave unset** -- the account setting is `inherit`, not zero |
| `aia_ai_fieldwork_max_output_tokens` | the respondent agent's cap per call, e.g. `1024` |
| `aia_ai_fieldwork_reservation_usd` | budget held per respondent request (primary + one repair); it must cover two calls' ceilings |
| `aia_ai_fictional_client_ids` | the client ids of the seed's *(fiktivní)* clients: only their studies' designs are Class C |

With the route approved for Class C only, a study of any client **not** in
`aia_ai_fictional_client_ids` parks with `egress_route_not_approved_for_class`,
and anything derived from the population panel parks with `licence_undetermined`
(OI-61), both before any request leaves. Inspect: usage in `ai_usage_events`
(`provider`, `route_id`, `model`, `provider_request_id`, tokens, `cost_usd`,
`cost_basis`, `runtime_version`), the reservation per request in
`budget_reservations`, failure classification on the attempt row
(`step_attempts.error_json`), and the dataset artifact's `provenance` (agent,
prompt hash, class, lineage, every call).

## Seed / reset

```bash
docker compose run --rm --no-deps -T -e AIA_SEED_OWNER_EMAIL worker python -m aia_executors.seed           # idempotent
docker compose run --rm --no-deps -T -e AIA_SEED_OWNER_EMAIL worker python -m aia_executors.seed --reset   # drop the seeded org's data, then seed
```

Synthetic data only. `--reset` removes only what the seed created (its
organization slug), never anything else.

To start completely fresh: `docker compose down -v` (destroys the PostgreSQL
volume and Caddy's certificates), then `bin/deploy.sh <sha>` and the seed.

## Migrating 18.6.6 content

Studies bound to an 18.6.6 project before ADR 0018 read *Čeká na migraci z 18.6.6* and
cannot be edited until their content is migrated into AIA
([ADR 0018](../../docs/architecture/adr/0018-aia-runs-without-18-6-6.md) decision 2).
The migration is an operator's act, run once on the host, from **copies**: it never
opens the unit's live files and never writes or deletes anything of the unit. Keep the
unit's `legacy_state` volume and its data bundle exactly as they are until the report
has been accepted.

From an SSM session, in `/opt/aia/develop`, with the unit running:

```bash
mkdir -p /opt/aia/migration && cd /opt/aia/develop
# 1. Copies: the databases through SQLite's backup API (WAL-safe), and the files.
docker compose exec -T legacy-panel python - < bin/backup-legacy-state.py > /opt/aia/migration/legacy-state.zip
docker compose cp legacy-panel:/app/data/ui_uploads/project_attachments /opt/aia/migration/project_attachments

# 2. A dry run: nothing is written; the report says what would happen to each Study.
docker compose run --rm --no-deps -T -v /opt/aia/migration:/migration:ro worker \
  python -m aia_executors.legacy_workspace \
    --store /migration/legacy-state.zip --attachments /migration/project_attachments \
    --as <your AIA sign-in email> > /opt/aia/migration/dry-run.json
```

Read the summary (standard error) and `dry-run.json`. `--as` names the AIA person the
migration acts as: each Study is opened with the grants that person holds on it, so a
Study they may not edit is reported and left waiting. An organization owner has no
implicit access to a client's studies: grant the person `LEAD` or `RESEARCHER` on each
client whose studies are waiting first. Each Study's `outcome` is `MIGRATED`,
`RECOVERED`, `UNRECOVERABLE` or `NOT_MIGRATED` with its `reason`; `files_missing` and
`files_mismatched` name brief files the copy lacks or whose bytes no longer match;
`unit_projects_not_bound` lists every unit project no Study refers to, which stays in
the unit's volume.

```bash
# 3. Back up PostgreSQL, then apply. Each Study is its own transaction, validated
#    against the copy before it commits; one that does not validate is rolled back.
bin/backup.sh pre-migration
docker compose run --rm --no-deps -T -v /opt/aia/migration:/migration:ro worker \
  python -m aia_executors.legacy_workspace \
    --store /migration/legacy-state.zip --attachments /migration/project_attachments \
    --as <your AIA sign-in email> --apply > /opt/aia/migration/applied.json
aws s3 cp /opt/aia/migration/applied.json "s3://<ops-bucket>/backups/legacy-migration-$(date -u +%Y%m%dT%H%M%SZ).json"
```

Exit status: 0 when every Study looked at is migrated, recovered or marked
unrecoverable; 3 when some stay waiting (each with its reason: fix it, run again);
2 when it could not start (no such active AIA user, an unreadable copy, or a database
the unit still has open). Running it again is safe: a Study that no longer waits is
listed under `done_before` and never written again.

**A Study whose unit project is not in the copy** stays waiting, because a partial or
wrong copy must not decide its fate. When you know the copy is complete (the dry run's
`unit_projects_not_bound` and the unit's own project list agree), run step 3 once more
with `--recover-missing`: such a Study becomes `RECOVERED` from its newest Design
Revision, whose stages say so, or `UNRECOVERABLE`, where a person who may edit starts
again (OI-66).

**Undo.** `bin/restore.sh --live <the pre-migration dump>` puts PostgreSQL back as it
was; the files already copied into the artifact bucket are then unreferenced objects.
The unit's volume was never changed, so nothing there needs undoing.

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


### Working Research content and backup scope (2026-09-26)

Until OI-58 is retired, AIA keeps Study identities/bindings in PostgreSQL while
Research editing content is in the legacy volume's SQLite project store. A
PostgreSQL dump alone cannot restore that editing copy. After owner approval,
set `AIA_LEGACY_STATE_BACKUP_ENABLED=true` in the host environment. The default
is disabled and logs that no working database export was made. When enabled,
`bin/backup.sh` streams consistent copies of `/app/data/*.sqlite` to the same private,
encrypted EU ops bucket under `backups/legacy-state-<utc>-<label>.zip`, using
`bin/backup-legacy-state.py` and SQLite's backup API. Existing retention applies.
Database snapshots are consistent individually, not an atomic cross-database
transaction. Uploaded attachments and generated file artifacts are outside this
ZIP. If the unit is not running the script explicitly reports no state backup.

The backup source is fed from the deployment bundle into the old running image,
so the first deployment of this repair can protect the databases too. Restore
working databases only with the unit stopped, keep a backup of current state,
and check both project IDs and PostgreSQL bindings before restarting. The
PostgreSQL `restore.sh` does not restore the separate SQLite ZIP.

Runtime hydration installs a `state_seed` only if no working file exists. It
still hash-verifies the seed on first installation and immutable assets on every
start. Replacing edited state with archive bytes is prohibited.


### AI settings

`/app/settings` has one AI section. What powers AIA comes from code, in the
settings document's `ai_runtime`: Bedrock, the instance-role credential, and each
native activity with its capabilities, versions and switches. The switches, region,
model and approved data classes come from the web container's nonsecret runtime
environment through `/config`. It has no provider login, direct API-key field,
selector or paid test button. Classic settings navigation is redirected there by
the product wrapper. On develop the enabled capability is fictional, internal-only
respondent fieldwork; native design proposals are implemented and off
(`AIA_AI_RESEARCH_AGENTS_ENABLED`). Each switch is read with the worker's vocabulary
(`1`/`true`/`yes`/`on`); a value the worker refuses is shown as invalid, not as off,
and with the runtime on it stops the whole worker. This display is not a live health
probe and never says connected or verified. Historical provider labels in archived
projects remain historical metadata, listed under a collapsed history, not
connection controls.
