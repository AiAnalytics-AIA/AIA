# `develop` — runbook

The first continuously deployed AIA environment: one EC2 host in `eu-central-1`
running Caddy, the Next.js client, the FastAPI API, the worker and PostgreSQL 16
under Docker Compose, with S3, Cognito, ECR, SSM and IAM used for real.
Decision record: [ADR 0009](../../docs/architecture/adr/0009-single-host-develop-environment.md).
Infrastructure: [`infra/develop/`](../../infra/develop/). Plan and audit:
[`.planning/plans/done/develop-deployment.md`](../../.planning/plans/done/develop-deployment.md).
Live at <https://aia-develop.art-chain.io/> since 2026-09-23.

The application runs with **`AIA_ENV=develop`**. `develop` is a deployed
environment to the code, so every guard is active — Cognito only, S3 only, no
debug, no wildcard CORS, no header identity, a known build SHA, no fixture
fieldwork. It is also the one deployed environment that hosts fictional data:
`aia_ai_fictional_client_ids` is accepted here and refused in `staging` and
`production` (`aia_core.domain.deployment`). Until 2026-10-05 it ran as
`staging`, which refused those clients once the API checked them (PR #108).

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
   Actions run: it builds the three images, pushes them by SHA, ships this
   directory to `s3://<ops-bucket>/deploy/<sha>.tar.gz`, and runs
   `bin/deploy.sh <sha>` on the host through SSM. The first run has no database
   to back up and says so.
8. **Seed.** From the SSM session:

   ```bash
   cd /opt/aia/develop
   docker compose run --rm --no-deps -T -e AIA_SEED_OWNER_EMAIL worker python -m aia_executors.seed
   ```

   Idempotent. It creates two organizations.
   - **The operator's**, `aia-develop`: the operator named in `AIA_SEED_OWNER_EMAIL`
     as its owner, and the fictional showcase clients with their studies and knowledge.
   - **The smoke's own**, `aia-develop-smoke`: a synthetic owner
     (`smoke.seed@aia-develop.invalid`, never signed in as), a synthetic client and
     study with a budget, a project, and one example workflow run. The operator is not
     a member, so none of it appears in their client list or in Settings.

   Re-running changes nothing.
9. **Sign in.** Open the public hostname (`https://aia-develop.art-chain.io/`).
   The gate sends you to `/login`; choose *Sign in* and authenticate with the
   Google Workspace account from step 8. You land on AIA's client directory,
   `/app/clients` (ADR 0015). The 18.6.6 interface is not part of the product
   (ADR 0018): a stage AIA has not rebuilt says so where you meet it.

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
   `aia-api`, `aia-worker` and `aia-web` at the verified SHA, pushes them to ECR
   tagged `<sha>` (and `develop` as a convenience alias), uploads this directory
   as `deploy/<sha>.tar.gz`, and sends one SSM command to the host.
3. On the host, `bin/deploy.sh <sha>`: pull → backup → `alembic upgrade head`
   → write `AIA_IMAGE_TAG` → `compose up --wait` → `bin/smoke.sh`.
4. The workflow waits for the command, prints its output, and fails if any step
   or smoke check failed. It waits 20 minutes (a deploy takes about two). A host
   still running then is reported `InProgress`, and the command's execution timeout
   stops it at 25 minutes, which releases `bin/deploy.sh`'s lock: until it does, a
   rerun is refused with `another deployment holds .deploy.lock`. The stopped
   command's output stays in Systems Manager → Run Command history, and
   `/var/log/aia-deploy.log` on the host has every line (§ Logs).

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

## AIA on the product hostname

Since [ADR 0015](../../docs/architecture/adr/0015-client-first-product-interface.md)
`https://aia-develop.art-chain.io/` is AIA: `/` redirects to the client
directory, `/app/clients`. Nothing of NPC Panel 18.6.6 is served or run by this
stack ([ADR 0018](../../docs/architecture/adr/0018-aia-runs-without-18-6-6.md)
decisions 4 and 5): it has no unit image, service, volume mount, hostname,
credential, data sync or health check, and `/classic` is AIA's page saying the
interface is gone. (The population is AIA's own, not the unit: `bin/sync-population.sh`
fetches its 15 listed files from the same EU bucket, by hand and read-only. It never
fetches the unit's whole bundle or starts anything of the unit; see § The population.)
The Caddyfile routes:

| Path | Goes to |
|---|---|
| `/api/v1/*` | the AIA API |
| `/login`, `/logout`, `/auth/*`, `/config`, `/version`, `/studies*`, `/_next/*`, `/skin/*`, `/favicon.ico`, `/icon.svg`, `/apple-icon.png` | the AIA web client |
| `/` | `302 /app/clients`; nothing is served |
| `/app`, `/app/*` | after `forward_auth` to AIA's own gate, `GET /api/v1/session/gate`, the web client: AIA, Clients → client workspace → study → stages |
| `/classic` | the web client's public page: the 18.6.6 interface is gone, and the way into AIA |
| everything else | the web client, with its own 404 for a path it does not know. The unit's old paths are among them: `/interface-document`, `/api/bootstrap` and every other `/api/*` outside `/api/v1`, `/files/*`, `/artifacts/*`, `/project-attachments/*`, `/brand/*`, `/fullsim-arena`, `/health`, `/status` |

`tools/caddy_routes.py` checks this table against the adapted Caddyfile in CI, and
fails a second hostname, any upstream but the API and the web client, and the
retired panel gate; `tools/develop_routing_proof.py` and
`tools/develop_routing_journey.mjs` run the real file locally, with a browser, when
the routing changes. The proof also runs the worker as this host does
(`aia_executors.registry`, no fieldwork source) and shows a research run parking at
fieldwork, `ai_runtime_unavailable` (ADR 0016).

- **Who gets into AIA.** Any active member of the organization (ADR 0018). Inside,
  each person sees only the clients and studies they hold grants in: the API
  decides that per call. To let someone in, add them to the organization and
  grant them a client or a study. Someone who signs in with Google but is no
  member is told so.
- **How.** `/login` turns the Google sign-in into an HttpOnly session cookie,
  `aia_session`, through `POST /api/v1/session`; AIA's gate re-verifies it on
  every request to `/app`. Caddy strips it before a request reaches the web
  client. Opening a session is recorded in the access audit (`AIA_SESSION`);
  individual requests are not.
- **Signing out.** `/logout` clears the cookie and the Cognito session. An
  `aia_panel` cookie a sign-in opened before ADR 0018 is read by nothing now and
  expires by itself.
- **When a page shows an error.** A 401 or 403 JSON body on a page means AIA's
  gate refused it; the `code` field says why (`unauthenticated`, `not_a_member`,
  `method_not_allowed`).
- **A Caddyfile change** reaches the running Caddy because its hash is part of
  the caddy service's configuration (`bin/lib.sh`, `AIA_CADDYFILE_SHA256`), so
  `compose up` recreates Caddy when the file changed and not otherwise. The
  smoke check *caddy: running the deployed Caddyfile* fails if it did not; the
  remedy is `docker compose up -d --force-recreate caddy` (OI-45).
- **The smoke check proves the unit is gone.** `bin/smoke.sh` fails when one of
  the unit's old paths answers anything but the web client's 404, or when a
  `legacy-panel` container of this Compose project exists, and says whether the
  unit's working volume is still on the host.

### The first deploy without the unit

A host deployed before ADR 0018 runs the unit as this project's service
`legacy-panel`, on the named volume `aia-develop_legacy_state`: its working
databases and the files people attached, which hold the only copy of the content
of every Study still waiting for its migration (OI-58). The first deploy of this
stack stops that container as the service did (`docker stop -t 30`, so its SQLite
stores close), `compose up --remove-orphans` removes the stopped container, and the
deploy fails if the volume is gone afterwards (`bin/deploy.sh`,
`retire_product_unit` in `bin/lib.sh`). Nothing removes the volume, the data
directory `/opt/aia/develop/legacy-data`, the data bundle in the ops bucket or the
unit's images in ECR.

**Before that deploy**, while the old scripts still reach the running unit, copy
its databases: with the data owner's approval (the parameter
`/aia/develop/aia_legacy_state_backup_enabled` set to `true`, then `bin/write-env.sh`),
`bin/backup.sh pre-adr-0018` exports
them to `s3://<ops-bucket>/backups/legacy-state-<utc>-pre-adr-0018.zip` beside the
PostgreSQL dump. After it, `deploy/reference/bin/backup-state.sh` makes the same copy
(§ Backup scope below).

### The 18.6.6 reference unit

The unit still runs when a comparison needs it -- the parity oracle
(`make test-oracle`) and the behavioural reference for a port -- from
[`deploy/reference`](../reference/README.md), beside this stack: a Compose project of
its own on the same volume, behind a basic-auth gate on the host's loopback
(`127.0.0.1:8765`), reached through an SSM port forward, started and stopped by
hand. It shares no network, file or Compose project with the product, and this stack
starts, deploys and passes its smoke checks whether the reference is up, down or
absent. The Parameter Store values it reads (`aia_legacy_data_prefix`,
`aia_legacy_basic_user`, `aia_legacy_basic_hash`) are written into `.env` with the
others and read by nothing of the product. `aia_legacy_hostname` is read by nothing
at all: no Caddy serves the oracle hostname any more, and its DNS record can be
removed by whoever manages the zone (OI-39).

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

## Error tracking

GlitchTip (self-hosted, `errors/docker-compose.yml`) collects what broke, grouped into
issues, with the build, the environment and where it happened. It speaks Sentry's
protocol; the plan is `.planning/plans/error-tracking.md`.

| From | What becomes an issue | Tags to search by |
|---|---|---|
| API | an unhandled exception (the 500 a person saw), any 5xx | `request_id`, `route` |
| Worker | a step left `FAILED` (one issue per step kind, failure class and cause), an unclassified exception, an outcome that could not be recorded, a loop or sweep that raised | `run_id`, `step_id`, `attempt_id`, `step_kind`, `failure_class`, `study_id` |
| Browser | an uncaught error, an unhandled rejection, a page that crashed while rendering | `boundary`, `digest` |

Never an issue: a 4xx, a retry that later succeeds, a park, a gate, a budget stop, a quota
wait, a cancellation. Every event is scrubbed before it leaves (secret shapes by key and
value, no bodies, cookies, query strings, local variables or user); events are kept 30
days. An issue's `request_id` or `run_id` opens its log lines in CloudWatch:

```
fields @timestamp, level, message, step_id
| filter run_id = "RUN-…"      # or request_id = "…"
| sort @timestamp asc
```

### Turning it on (once)

1. **DNS:** an A record for `errors.<public hostname>` to the host's address (Terraform
   output `public_ip`; Terraform makes it when `route53_zone_id` is set). Caddy obtains
   the certificate itself.
2. **Secrets**, from CloudShell (hex only: the database password sits in a URL):

   ```bash
   P=/aia/develop
   aws ssm put-parameter --name $P/glitchtip_secret_key --type SecureString --value "$(openssl rand -hex 32)"
   aws ssm put-parameter --name $P/glitchtip_db_password --type SecureString --value "$(openssl rand -hex 24)"
   aws ssm put-parameter --name $P/aia_errors_enabled --type String --value true
   ```

3. **Start it**, on the host: `bin/write-env.sh && bin/errors.sh up` (the first start
   migrates an empty database: a minute or two). Then `bin/errors.sh admin <your email>`
   makes the first account; sign in at `https://errors.<public hostname>`.
4. **Projects**, in GlitchTip: an organization `AIA`, then a project `aia-backend`
   (Python; the API and the worker, told apart by the `service` tag) and `aia-web`
   (JavaScript). Each shows its DSN under Settings → Client Keys.
5. **DSNs**: the backend's with its host replaced by `glitchtip:8000` over `http` (the API
   and the worker send inside the host); the web's as shown (browsers send to the public
   name):

   ```bash
   aws ssm put-parameter --name $P/aia_error_tracking_dsn --type String --value "http://<key>@glitchtip:8000/<id>"
   aws ssm put-parameter --name $P/aia_web_error_tracking_dsn --type String --value "https://<key>@errors.<public hostname>/<id>"
   ```

   Then `bin/write-env.sh && docker compose up -d api worker web`. A malformed backend
   DSN stops the API and the worker from starting (said in their log); a malformed web
   DSN turns the browser's reporting off and says so in the web's log.
6. **Alerts**: in each project, Alerts → a webhook (Slack, Discord, Google Chat or any
   URL). E-mail needs an SMTP route the host does not have yet.

From then on every deploy starts or updates GlitchTip after AIA is healthy
(`aia_errors_enabled`); a GlitchTip that will not start is said and does not fail the
deploy. Off: delete the two DSN parameters (AIA stops reporting) and
`bin/errors.sh down` (its database volume is kept).

`bin/errors.sh status` shows its two services. GlitchTip's events are not in
`bin/backup.sh`: they are operational, and the next failure rebuilds them.

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
off by default** (`AIA_AI_RUNTIME_ENABLED=false`): a research run parks at
fieldwork (`WAITING_PROVIDER` / `ai_runtime_unavailable`) until an operator
configures it. ADR 0010 is accepted for fictional Class C on develop only
(2026-09-26); the one authorised acceptance run is recorded in
[`bedrock-develop-activation-2026-09-26.md`](../../docs/architecture/bedrock-develop-activation-2026-09-26.md).
The smoke test's AI check is `NOT_RUNNABLE` by design: the smoke makes no paid
model call, so it proves nothing about whether the runtime is on for a given
deploy.

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
| `aia_ai_route_eu_processing_approved`, `aia_ai_route_excluded_from_training` | `true` (ADR 0010's review, 2026-09-26; required for Classes A and B) |
| `aia_ai_route_approved_for` | `CLASS_A_CLIENT_CONFIDENTIAL,CLASS_B_DERIVED_CLIENT,CLASS_C_INTERNAL` (ADR 0010, amendment 2026-10-19), only together with the retention below; until then `CLASS_C_INTERNAL` |
| `aia_ai_route_retention_days` | the Bedrock account's provider-side retention, **once an operator has confirmed it** (§ AI route classes); unset until then, and then only Class C may travel |
| `aia_ai_fieldwork_max_output_tokens` | the respondent agent's cap per call, e.g. `1024` |
| `aia_ai_fieldwork_reservation_usd` | budget held per respondent request (primary + one repair); it must cover two calls' ceilings |
| `aia_ai_fictional_client_ids` | the client ids of the seed's *(fiktivní)* clients; kept for configuration compatibility, it classifies no material ([ai-material-classification.md](../../docs/architecture/ai-material-classification.md)) |

A study's design, its names and a researcher's messages to the Research Lead are Class
B by the product owner's rule of 2026-10-19 (ADR 0008 amendment); approved knowledge, a
client's documents and the Lead's client notes are Class A. With the route approved for
Class C only, each of those parks with `egress_route_not_approved_for_class`, before any
request leaves; anything derived from the population panel needs its licence besides
(OI-61). Inspect: usage in `ai_usage_events`
(`provider`, `route_id`, `model`, `provider_request_id`, tokens, `cost_usd`,
`cost_basis`, `runtime_version`), the reservation per request in
`budget_reservations`, failure classification on the attempt row
(`step_attempts.error_json`), and the dataset artifact's `provenance` (agent,
prompt hash, class, lineage, every call).

### AI route classes

The product owner decided on 2026-10-19 that this route may carry Classes A, B and C
(ADR 0010, amendment of that date). It takes effect only when an operator sets the four
parameters below; the Compose defaults stay empty, so nothing in the repository widens the
route by itself. ADR 0008 requires a specified retention for A and B, and the worker's
egress check refuses either over a route whose retention is unset
(`egress_retention_unspecified`).

1. **Confirm the retention, then record it.** `aia_ai_route_retention_days` is the provider-side
   retention of model inputs and outputs: how long Bedrock and the model provider keep them,
   under the account's data-retention setting and the model's terms. It is **not** read from
   invocation logging. Logging off only means AIA's account does not publish payloads to its
   own CloudWatch or S3; it says nothing about what the provider keeps. Two pieces of evidence,
   both required:

   - the account's Bedrock **data-retention** setting, in the Bedrock console (Settings) for
     `eu-central-1`, and the retention it states (AWS's "Data retention" page in the Bedrock
     user guide describes the modes). ADR 0010 § Retention found it `inherit` on 2026-09-26;
     read what it is now;
   - the model's own terms for the models on the route (the route model and, when one is set,
     the Lead's), from the model's page and end-user licence agreement in the console: whether
     the provider keeps inputs or outputs, and for how long.

   Invocation logging is checked as well, because a configured log is a retention of AIA's own
   that the activation evidence names:

   ```bash
   aws bedrock get-model-invocation-logging-configuration --region eu-central-1
   ```

   Record the setting, the terms reference, the logging state, the number of days that follows
   and the date in the activation evidence (ADR 0010 § Activation evidence) before setting the
   parameter. If either piece cannot be confirmed, or the two disagree, stop here: the route
   stays Class C only.
2. **Set the parameters**, from CloudShell (`<days>` is the number confirmed in step 1):

   ```bash
   P=/aia/develop
   aws ssm put-parameter --name $P/aia_ai_route_eu_processing_approved --type String --value true --overwrite
   aws ssm put-parameter --name $P/aia_ai_route_excluded_from_training --type String --value true --overwrite
   aws ssm put-parameter --name $P/aia_ai_route_retention_days --type String --value <days> --overwrite
   aws ssm put-parameter --name $P/aia_ai_route_approved_for --type String --overwrite \
     --value CLASS_A_CLIENT_CONFIDENTIAL,CLASS_B_DERIVED_CLIENT,CLASS_C_INTERNAL
   ```

   None of the four is a secret: `String`, not `SecureString`.
3. **Write the host's environment and restart**, on the host:

   ```bash
   bin/write-env.sh && docker compose up -d worker web
   ```

   The worker reads the route; the web client shows its classes on Settings. The next deploy
   (`bin/deploy.sh`) does the same. Check:
   `docker compose exec worker printenv AIA_AI_ROUTE_APPROVED_FOR AIA_AI_ROUTE_RETENTION_DAYS`
   prints both; Settings → AI shows the three classes. A value the worker refuses stops it at
   start, with the key named in its log.

To narrow it again, put `CLASS_C_INTERNAL` back into `aia_ai_route_approved_for` and repeat
step 3; requests of Classes A and B then park before anything is sent.

### Model requests in a step's activity

`aia_ai_step_events` (`true`; off when unset) makes each research-agent and analysis model
request write `ai_request_sent` and `ai_request_answered` to its run's feed: counts, cost and
latency, never text. A running step's activity panel shows them. Two database writes per request
(~1.3 ms measured). It changes nothing unless `aia_ai_research_agents_enabled` or
`aia_ai_analysis_enabled` is also on, since only those two callers announce. Only the worker
reads it: after creating or changing the parameter, run `bin/write-env.sh` and
`docker compose up -d worker`, then `docker compose exec worker printenv AIA_AI_STEP_EVENTS`
prints `true`. Requests made before the restart are not in the feed. On develop since
2026-10-13.

### The Research Lead's own model

The study's Research Lead (ADR 0026) can run on a model of its own while every other
capability stays on `aia_bedrock_model_id` (the product owner, 2026-10-19; ADR 0026 §
Amendment 2026-10-19). Its turns ask for `STUDY_LEAD`. With `aia_ai_research_lead_model_id`
unset, `STUDY_LEAD` is bound to the route's model and the Lead runs exactly as before. Set, it
is a second policy entry on the same route, `bedrock-eu-primary`: same egress, same approved
classes, same retention. Nothing in the repository names the model or its price. Every value
below is recorded by an operator from the Bedrock console and pricing page.

**Before anything is set**, in the Bedrock console for `eu-central-1`:

- model access is enabled for the model;
- its EU cross-region inference profile id is written in full as Bedrock lists it (`eu.anthropic.…`,
  with a `:N` suffix only if the id has one; the current model family's ids have none), never a
  `latest` alias;
- `aws bedrock get-inference-profile --inference-profile-identifier <id>` lists the same
  destination regions as Terraform's `bedrock_destination_regions`. If they differ, stop: the
  grant below covers those regions only, and changing them is a reviewed IAM change;
- its input and output prices (and cache prices, if any) are read from the Bedrock pricing page
  for the region, and the date is noted.

**1. Grant it (Terraform).** In `infra/develop/terraform.tfvars` set
`bedrock_lead_model_id = "<the profile id>"`, then `terraform plan` from `infra/develop`. The plan
changes only `aws_iam_role_policy.instance`: the profile's ARN and its foundation model's ARN in
each destination region are added to the `InvokeTheOneApprovedModel` statement. Then run
`terraform apply`. `terraform output bedrock_model_arns_granted` lists everything the role may
now invoke. Empty (the default), the policy is unchanged.

**2. Configure it (Parameter Store).** Create these under `/aia/develop/`. Names are lower-case;
`bin/write-env.sh` upper-cases them. Once the id is set, every row not marked optional is
required. A missing or invalid one stops the worker with its key named.

| Parameter | Value |
|---|---|
| `aia_ai_research_lead_model_id` | the profile id, the same as `bedrock_lead_model_id`; it must differ from `aia_bedrock_model_id` |
| `aia_ai_research_lead_input_usd_per_mtok`, `aia_ai_research_lead_output_usd_per_mtok` | USD per million tokens, from the pricing page, dated |
| `aia_ai_research_lead_cache_read_usd_per_mtok`, `aia_ai_research_lead_cache_write_usd_per_mtok` | optional; unset charges cache tokens at the input rate |
| `aia_ai_research_lead_model_max_output_tokens` | the model's documented output ceiling |
| `aia_ai_research_lead_context_window_tokens` | the model's documented context window |
| `aia_ai_research_lead_structured_output` | `auto_tool` for a model that refuses a forced tool choice, else `forced_tool` |
| `aia_ai_research_lead_thinking` | `adaptive` for a model that refuses a thinking budget, else `budget` |
| `aia_ai_research_lead_effort` | optional, `adaptive` only: `low`, `medium`, `high`, `xhigh` or `max`; unset takes the model's default |
| `aia_ai_research_lead_max_output_tokens` | **raise it** for a model with `adaptive` thinking: its thinking and its answer share this cap, and Compose's `1500` ends such a turn truncated before it answers (two calls paid, no answer). Pick it with the effort below; the reservation grows with it |
| `aia_ai_research_lead_reservation_usd` | **re-size it** for the new prices (below) |
| `aia_ai_policy_version` | a new name: a new binding is a policy change, recorded on every call |

The Lead model's catalog entry declares no sampling setting. The Lead's turns send none, and one
that ever did would be refused before it left.

**3. Re-size the reservation.** `aia_ai_research_lead_reservation_usd` (Compose default `1.02`)
was sized at the route model's prices. The worker checks it against the model the Lead runs on:
two calls (a turn and its one repair), each at the Lead's whole window
(`lead_request_window_tokens`: 117,630 tokens at Compose's output cap of 1,500, measured
@ 5d775785) and its output
cap, priced at the Lead model's dearest input rate and its output rate. A reservation below that
stops the worker, and the refusal states the minimum:
`AIA_AI_RESEARCH_LEAD_RESERVATION_USD: the Research Lead's reservation must cover two calls at
the Lead model's prices, window and the Lead's output limit (at least N)`. Set the parameter to
at least N. With adaptive thinking, the output cap (`aia_ai_research_lead_max_output_tokens`)
covers the thinking and the answer together. A cap too small ends a turn truncated. Raising it
raises N, and the worker states the new one.

**4. Restart the worker.**

```bash
cd /opt/aia/develop && bin/write-env.sh && docker compose up -d worker
```

Only the worker reads these keys. The API and the web are not restarted.

**5. Read its start-up.** `docker compose ps worker` shows it `Up`. A worker that refused its
configuration is `Restarting`, and `docker compose logs --tail=50 worker` ends in
`AIRuntimeConfigError:` with the key named (for the reservation, the minimum too). Fix the
parameter and repeat steps 4 and 5. `docker compose exec worker printenv
AIA_AI_RESEARCH_LEAD_MODEL_ID` prints the id the worker received.

**6. Check one turn.** Send the Lead a message on a fictional study, then:

```bash
docker compose exec -T postgres psql -U aia -d aia -tAc \
  "select capability, model, outcome, cost_usd from ai_usage_events
   where capability = 'STUDY_LEAD' order by occurred_at desc limit 2"
```

The model is the Lead's profile, and the cost is priced at its rates.

**Switching it off.** Delete `aia_ai_research_lead_model_id` (the other `aia_ai_research_lead_*`
model keys are then not read), give `aia_ai_policy_version` a new name, and repeat step 4. The
Lead returns to the route's model. To remove the grant, empty `bedrock_lead_model_id` and
`terraform apply`.

### Deep Research on Brave search

Brave's search is a priced, live route outside the EU, Class C only
(`aia_executors.deep_research_live.brave_retrieval`). Each search reserves its price
against the study before it leaves and is charged once, and a start is refused (409
`live_settings_unapproved`) until the organization has approved every setting live needs
on **Nastavení → Deep Research** (ADR 0022 decision 6; the Wikipedia route needs no
sign-off). To switch it on, beside the AI runtime and research agents above, create
these parameters under `/aia/develop/`, run `bin/write-env.sh` (or deploy), and read the
worker's start-up log: a missing or invalid key stops the worker with the key named.

| Parameter | Value |
|---|---|
| `aia_deep_research_enabled` | `true` |
| `aia_deep_research_web_search` | `brave` (replaces `aia_deep_research_wikipedia_enabled`: leave that `false` or unset) |
| `aia_deep_research_public_fetch_contact` | one e-mail address: Brave's results are pages on any public host |
| `aia_deep_research_brave_api_key` | **SecureString**: the subscription key. Only the worker receives it; it is read at each call and never logged |
| `aia_deep_research_brave_usd_per_1000` | the plan's price per 1,000 requests, in USD |
| `aia_deep_research_brave_prices_as_of` | the date that price was read, `YYYY-MM-DD` |

To switch it off, set `aia_deep_research_web_search` to `wikipedia` or `off` and
redeploy; a run already planned on Brave then stops with `composition_changed` rather
than continuing on another route.

### Deep Research on Common Crawl

Common Crawl's URL index runs through Amazon Athena in **`us-east-1`**, outside the EU, and its
archived pages come from `data.commoncrawl.org`; both carry Class C only, and the index query is
priced (its scan cutoff, reserved against the study) and so needs the organization's approvals on
**Nastavení → Deep Research**. The `us-east-1` exception is the owner's residency decision, and the
AWS side is an operator's: the results bucket, the workgroup with an enforced
`BytesScannedCutoffPerQuery`, the `ccindex` table and the instance role's grants
([`docs/architecture/deep-research-common-crawl.md`](../../docs/architecture/deep-research-common-crawl.md)
§ Human actions). Then create, under `/aia/develop/`, beside a search route and
`aia_deep_research_public_fetch_contact`:

| Parameter | Value |
|---|---|
| `aia_deep_research_common_crawl` | `true` |
| `aia_deep_research_common_crawl_workgroup`, `_database`, `_table` | the workgroup and the `ccindex` table |
| `aia_deep_research_common_crawl_max_scan_bytes` | the workgroup's enforced cutoff, at least `10000000` |
| `aia_deep_research_common_crawl_usd_per_tb_scanned`, `_min_billed_bytes`, `_billing_increment_bytes`, `_prices_as_of` | Athena's dated price |
| `aia_deep_research_common_crawl_crawls` | 1 to 6 crawl ids, `CC-MAIN-YYYY-WW`, comma-separated |

## Seed / reset

```bash
docker compose run --rm --no-deps -T -e AIA_SEED_OWNER_EMAIL worker python -m aia_executors.seed           # idempotent
docker compose run --rm --no-deps -T -e AIA_SEED_OWNER_EMAIL worker python -m aia_executors.seed --reset   # drop the two seeded orgs' data, then seed
```

Synthetic data only. `--reset` removes only what the seed created (its two
organization slugs, `aia-develop` and `aia-develop-smoke`), never anything else.

The deployment smoke (`aia_executors.smoke`) acts only in `aia-develop-smoke`, as its
synthetic owner, so nothing a person archives or changes in their own workspace can
stop it. Before 2026-09-28 the smoke's client, `synthetic-client`, sat in the
operator's organization. Archiving it to keep it out of the client list failed deploy
runs 36–41 (OI-80). If that client is still there, archived, the seed leaves it as it
is.

To start completely fresh: `docker compose down -v` (destroys the PostgreSQL
volume and Caddy's certificates), then `bin/deploy.sh <sha>` and the seed.

## The population

AIA's population is 18.6.6's v17 synthetic model of the Czech adult population: three
versions of the panel (18,766 rows × 400 fields each), the 400-field dictionary and 15
companions, every one pinned by SHA256 in the Czech import contract
(`packages/aia_core/src/aia_core/domain/population/czech.py`). Once it is imported, with
STATIC on `v17_1_2` and LIVE on `v17_4_0`, every new research run records the LIVE version
it would be computed over (owner's decision of 2026-10-10, `.planning/plans/population-operations.md`
P3, P6). Fieldwork answers from it only for a run that pinned the panel persona source at start,
which needs `AIA_AI_POPULATION_PERSONAS_ENABLED=true` (off by default; see below). Panel-derived
material may reach `bedrock-eu-primary` and no other route (OI-61, the data owner's determination
of 2026-10-12).

### Respondents drawn from the population

`AIA_AI_POPULATION_PERSONAS_ENABLED` is read by both the API (a new `ai_runtime` run pins
`persona_source = panel`) and the worker (it serves such a run from `AIA_POPULATION_ASSET_ROOT`,
which Compose sets to the read-only `/srv/population/v17`). Before turning it on:

1. LIVE is established (`bin/population.sh status`); without it a start is refused, 409
   `population_not_established`, and nothing is created.
2. The AI runtime is on and its route is approved for `CLASS_A_CLIENT_CONFIDENTIAL`: a panel
   persona is Class A, never internal.
3. The study's design asks for an `n` the sampler can represent; a small one is refused as
   `sampling_unrepresentative` until OI-99 is decided.

Turning it off again does not change a run that already pinned the panel: a worker without the
path parks it (`panel_personas_unavailable`) rather than answering with fictional respondents.

### Materialized children (the population store)

A client's materialized dimension is written once, as an owned child version, to its own bucket,
`aia-develop-population-<account>` (Terraform `aws_s3_bucket.population`; no `force_destroy`), under
`materialized/`. Its name and region are the SSM parameters `/aia/develop/aia_population_store_bucket`
and `/aia/develop/aia_population_store_region`, which the deploy hands the worker as
`AIA_POPULATION_STORE_BUCKET` / `AIA_POPULATION_STORE_REGION` (both or neither: neither means no
store, nothing written or read). The instance role may get and put objects under `materialized/`
and list the bucket, nothing else.

The worker builds one store and gives it to both the `population_materialize` step, which writes a
child, and the panel loader, which reads a selected child back. Without a store, a materialize run
parks (`population_store_unconfigured`), and a panel run over a child parks at fieldwork; neither
writes or substitutes anything.

### The audience preview

The audience step's feasibility preview is counted by the API, which mounts the same
directory read-only and loads LIVE once per process and version (measured on fictional rows
of v17's shape: ~97 MB held, 360 MB peak while parsing, 3.6 s; the real panel holds more).
The first preview after a deploy or a promotion pays the load; later ones only the count. The
API never receives `AIA_POPULATION_OPERATORS`. Set `AIA_API_POPULATION_ASSET_ROOT=` (empty) in
`.env` to turn the preview off; the step then says it is not available here.

The panels are licence-bound (PIAAC 2023 CZ / ISSP 2022 CZ, open decision D3). They stay
in the EU ops bucket and on this host's disk, never in Git or an image. Fifteen of the
files come from the unit's data bundle (`legacy-data/86b70bfb5c1b`). The other four are the
frozen unit's own configuration files (`legacy/npc-panel-18.6.6/app/*.json`), which the
deploy bundle carries. `population/v17.files` lists all 19.

This is the data owner's act, once, as a named operator. Every step is safe to repeat, and
each refusal writes nothing.

Run these steps as an identity limited to this host, never as the AWS account's root user (the
first import did, OI-96). It needs only: `ssm:SendCommand` and `ssm:GetCommandInvocation` on the
develop instance, and `ssm:PutParameter` / `ssm:GetParameter` under `/aia/develop/`.

1. **Name the operator and the source.** Find your AIA user id (you must have signed in once):

   ```bash
   docker compose exec -T postgres psql -U aia -d aia -tAc \
     "select user_id from users where email = 'you@art-chain.io'"
   ```

   Then create two parameters under `/aia/develop/` and rewrite the env file:

   | Parameter | Value |
   |---|---|
   | `aia_population_source_prefix` | `legacy-data/86b70bfb5c1b` |
   | `aia_population_operators` | `{"<user id>":["POPULATION_ESTABLISH","POPULATION_PROMOTE"]}` |

   ```bash
   bin/write-env.sh
   ```

   Unset or empty, `aia_population_operators` names nobody, and every command but
   `status` and `record-dictionary` (which act as no one) is refused. A value that does not read stops the command and names the key.

2. **Back up**, so the import can be undone by a restore (§ Database). Nothing un-imports
   a version:

   ```bash
   bin/backup.sh pre-population
   ```

3. **Put the files on the host.** This fetches the 15 bucket files and copies the 4
   bundled ones into a staging directory. It checks each one's size and SHA256 against
   `population/v17.files`, and only then swaps the directory in, read-only, as
   `/opt/aia/population/v17` (`AIA_POPULATION_DIR`). One mismatch or missing object stops
   it, and the files already there stay as they were.

   ```bash
   bin/sync-population.sh
   ```

4. **Import the three versions, oldest first.** A version's parent is the contract's,
   so the import finds it. `v17_0_BASE` is the lineage root, build input only, and never
   becomes a population, so it is imported without companions. The other two are
   imported with every companion the contract declares. Each prints its `version_id`.

   ```bash
   P="18.6.6 data bundle legacy-data/86b70bfb5c1b (source zip 86b70bfb5c1b4a79…)"
   bin/population.sh import --as you@art-chain.io --label v17_0_BASE \
     --panel FINALNI_KOMPLETNI_PANEL_v17_0_BASE.csv.gz --dictionary FIELD_DICTIONARY_v17_1.csv \
     --provenance "$P"
   bin/population.sh import --as you@art-chain.io --label v17_1_2 \
     --panel FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz --dictionary FIELD_DICTIONARY_v17_1.csv \
     --provenance "$P" --all-companions
   bin/population.sh import --as you@art-chain.io --label v17_4_0 \
     --panel FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz --dictionary FIELD_DICTIONARY_v17_1.csv \
     --provenance "$P" --all-companions
   ```

5. **Establish STATIC, then LIVE**, with the ids step 4 printed (or read them from
   `bin/population.sh status`):

   ```bash
   bin/population.sh establish --as you@art-chain.io --population CZ_STATIC_REFERENCE \
     --kind STATIC --version <v17_1_2 id> --reason "the 18.6.6 reproducibility anchor"
   bin/population.sh establish --as you@art-chain.io --population CZ_LIVE \
     --kind LIVE --version <v17_4_0 id> --reason "the 18.6.6 default runtime population"
   ```

6. **Check.** `bin/population.sh status` lists the three versions, both populations and
   two history entries naming your user id. **Společenská inteligence** shows the same
   registry. A research run started from now on says on its page that `v17_4_0` was
   recorded and that its respondents did not come from it. Runs started before keep
   what they recorded, which is nothing.

   Each deploy then runs `bin/population.sh record-dictionary`, which keeps every
   version's verified field dictionary in the database for the characteristics section
   on Společenská inteligence. It acts as no one and needs no sign-in. A refusal is logged
   as a warning and does not fail the deploy.

   It then runs `bin/population.sh record-catalogue`, which keeps the audience factor
   catalogue of each population's current version, computed once from its ANALYSIS view,
   for the audience step's factor editor and subpanels. `establish` and `promote` keep the
   catalogue of the version they move to as well, so a promotion between deploys does not
   leave the step without one; a version no population has stood on has none. Either is
   said in the command's answer, and a refusal does not undo the change or fail the deploy.
   The deploy gives the command five minutes (a catalogue is seconds of work: 3.6 s to load
   v17's 18,766 rows, measured) and stops it after that, logging `record-catalogue did not
   finish in 5 minutes`; no catalogue is kept then, the step says so, and the deploy goes on.
   On 2026-10-13 the unbounded command held the deploy, and its lock, for the hour SSM
   allows a command by default.

**Exit codes.** `2` means refused before anything was written: a person the
configuration does not name, a malformed argument. `3` means the population itself
refused, with every failure listed. A `3` on the real files is a **finding**: record it
in the plan and do not loosen the contract. The reference measured the weight totals
on `v17_4_0` only (the `czech.py` docstring); if `v17_1_2` fails them, that is exactly
such a finding.

**Cost.** Parsing one panel took 3.1 s and peaked at about 430 MB of process memory,
measured on a fictional panel of the same shape (18,766 × 400, 5.4 MB gzip). The import
runs as a one-off worker container beside the running services on this 4 GB host. The
files add about 23 MB to the host's disk and nothing to S3.

## Migrating 18.6.6 content

Studies bound to an 18.6.6 project before ADR 0018 read *Čeká na migraci z 18.6.6* and
cannot be edited until their content is migrated into AIA
([ADR 0018](../../docs/architecture/adr/0018-aia-runs-without-18-6-6.md) decision 2).
The migration is an operator's act, run once on the host, from **copies**: it never
opens the unit's live files and never writes or deletes anything of the unit. Keep the
unit's volume `aia-develop_legacy_state` and its data bundle exactly as they are until
the report has been accepted.

The copies come from the volume itself, in throwaway containers of the unit's image
that start nothing of the unit: the product stack no longer runs it, and the unit need
not run at all. If the reference unit is up, stop it first
(`/opt/aia/reference/bin/down.sh`), so nothing changes the store between the copy and
the migration. Take the copies only once writes have stopped (§ The cutover, below).
A Study bound, or a project saved, after the copy is not in it: it waits as *not in this
copy*, and `--recover-missing` would then decide it wrongly. The copier,
`backup-legacy-state.py`, comes with the reference bundle
([`deploy/reference`](../reference/README.md) § Getting it onto the host); the image is
any `aia-legacy-panel` SHA in ECR (`aws ecr list-images --repository-name
aia-legacy-panel`); it runs as the user who owns the unit's stores, which a read-only
copy of a WAL database needs (AGENTS.md § Docker and Compose).

From an SSM session, in `/opt/aia/develop`:

```bash
mkdir -p /opt/aia/migration && cd /opt/aia/develop
docker volume inspect aia-develop_legacy_state >/dev/null   # stop here if it is missing: never create it
IMAGE="$(sed -n 's/^AIA_IMAGE_REGISTRY=//p' .env)/aia-legacy-panel:<sha>"
# 1. Copies: the databases through SQLite's backup API (WAL-safe), and the files.
docker run --rm -i --network none --entrypoint python3 -v aia-develop_legacy_state:/app "$IMAGE" - \
  < /opt/aia/reference/bin/backup-legacy-state.py > /opt/aia/migration/legacy-state.zip
cid="$(docker create --network none -v aia-develop_legacy_state:/app "$IMAGE")"
docker cp "$cid:/app/data/ui_uploads/project_attachments" /opt/aia/migration/project_attachments
docker rm "$cid"

# 2. A dry run: no content is written; the report says what would happen to each Study.
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
the unit's volume. A Study the person may not open also leaves one access-audit record
of that refusal, as every refused access does. That record is the only thing a dry run
writes.

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

**A Study that is delivered, archived or cancelled** stays waiting, with a reason such as
*the Study is DELIVERED: reopen it to migrate*
(`application/workspace_migration.py:306-307`). Reopening it (`ACTIVE`), migrating it
with `--study <id>` and closing it again all work. But delivering it again sets a new
`delivered_at` (`infrastructure/scope_repository.py:576-577`), so the original delivery
time is then kept only in `access_audit` (`STUDY_STATUS_CHANGED`, `created_at`). Decide
each such Study with its owner before the cutover (OI-81).

**Undo.** `bin/restore.sh --live <the pre-migration dump>` puts PostgreSQL back as it
was before the apply, with the schema still at the release's. The files already copied
into the artifact bucket are then unreferenced objects. The unit's volume was never
changed, so nothing there needs undoing. Undoing the release itself is § Rolling back
the content cutover.

## The cutover

The release that takes the unit out of the product (ADR 0018) is deployed once, in a
maintenance window. Its first deploy makes every Study bound to 18.6.6 read *Čeká na
migraci z 18.6.6* until the migration above has run, and `bin/deploy.sh` upgrades the
schema and switches the services but migrates no content. The order, from the
2026-09-28 consolidation plan:

1. **Hold the deploy.** Every green `develop` head deploys itself (§ Normal deployment),
   so a person puts a hold in place before the release is merged. One way is a required
   reviewer on the `develop` GitHub environment, which the deploy job runs in.
2. **Stop writes** and close public access, by the means the operator chooses; nothing
   here builds one. Stop the workers.
3. **Copy, before the release deploys.**
   - Take `bin/backup.sh pre-adr-0018`. With the data owner's approval it also exports
     the unit's databases (§ The first deploy without the unit).
   - For the migration, take the WAL-safe copy of the unit's store and
     `project_attachments` (§ Migrating 18.6.6 content, step 1).
   - Record each copy's SHA256, and check that the dump restores with
     `bin/restore.sh --test`.
4. **Rehearse on the copies,** in an isolated PostgreSQL: the release's migration, the
   dry run, the apply, every Study's disposition, and § Rolling back the content
   cutover. Keep the reports.
5. **Merge the release once**, as a merge commit, and release the hold.
   `bin/deploy.sh` takes `pre-deploy-<sha>`, migrates to `5b1d0f3e9a21` and switches the
   services. Public access stays closed.
6. **Migrate** (§ Migrating 18.6.6 content, steps 2 and 3), and give every Study left
   waiting its disposition.
7. **Accept.** Run the smoke and the browser checks on the deployed head:
   - sign-in and an active researcher's access;
   - refusal across studies;
   - open, save, reload, import and download;
   - stale-save and Run protection;
   - Settings that tell the truth;
   - the native workspace, with the unit stopped.
8. **Reopen** only when steps 6 and 7 pass. Otherwise roll back while access is still
   closed.

A dress rehearsal of steps 3, 4 and 6, and of the database rollback, ran on 2026-09-28.
It used fictional data on a scratch PostgreSQL 16 (`.planning/overview.md`). It is not
step 4: it had none of the host's data and ran no Docker.

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

### Rolling back the content cutover

Migration `5b1d0f3e9a21` is the exception to the paragraph above. The dress rehearsal
on 2026-09-28 (§ The cutover) found three things.

- **A code-only rollback is not safe.** On the release's schema, `develop`'s code
  (`8017b54`) did three things wrong:
  - It failed every new binding with `NotNullViolation` on `content_state`. The
    migration drops that column's default (`20260927_5b1d0f3e9a21_…py:69`), and the old
    row does not know the column (`infrastructure/tables.py:643 @ 8017b54`).
  - It could not read a Study started in AIA: its `unit_project_id` is null, which the
    old model refuses (`domain/workspace.py:59 @ 8017b54`).
  - It opened a migrated Study's 18.6.6 project, without anything saved in AIA since.
- **`alembic downgrade` refuses** once any Study holds content in AIA or has no 18.6.6
  project (`…py:88-100`). It is possible only before the apply, while nothing has been
  saved.
- **The rollback moves the database and the code together.** While writes are still
  stopped:
  1. Run `bin/restore.sh --live <key>`, where the key is that of the
     `pre-deploy-<release sha>` dump `bin/deploy.sh` took before it migrated. It first
     dumps what is there (`pre-restore`). Its closing smoke runs the release's code on
     the older schema, so it is not the verdict; step 3 is.
  2. Deploy the previous SHA with `migrate` unchecked, through the workflow, which
     unpacks that SHA's bundle. Its Compose file still has `legacy-panel`, which starts
     on the volume the release left untouched. From the host instead, unpack
     `s3://<ops-bucket>/deploy/<previous-sha>.tar.gz` into `/opt/aia/develop` and run
     `bin/write-env.sh` before `bin/deploy.sh <previous-sha> --no-migrate`: the release's
     bundle has no unit service.
  3. That deploy's smoke must pass. The files the migration copied into the artifact
     bucket stay there, unreferenced.

After reopening, a rollback discards everything saved in AIA since that dump, so it
needs its own decision and an export first. The rehearsal covered the database, the
migration and both code revisions; it did not cover the Compose or SSM steps.

## Disk retention

Every deployment acquires the host's `.deploy.lock`, then runs image retention
and checks disk headroom **before ECR login, downloads, backup, migration or
service replacement**. This includes manual `bin/deploy.sh` calls. The
CloudWatch `aia-develop-disk-85-percent` alarm and its existing notifications
remain unchanged; cleanup runs with deployments, not with every alarm.

Only local `aia-api`, `aia-worker` and `aia-web` images in this deployment's
registry, tagged by a full git SHA and older than 48 hours, can be removed.
Retention keeps:

- Every image used by any running **or stopped** container.
- The incoming SHA, the currently responding release, and all images less than
  48 hours old.
- The latest four distinct successful releases: current plus three rollback
  releases, even when older than 48 hours.
- Untagged, shared/floating-tag, other-registry and reference-unit images.

The successful list is written atomically to
`.deploy-state/successful-releases.json` **after smoke passes**, never after a
failed pull, migration or smoke test. On the first deployment with this policy,
the list is initialized from the incoming successful release and the previously
running SHA; the 48-hour window and container references also protect recent
images. Until four distinct releases are recorded, automatic retention keeps
**all** images: older pre-policy rollback images cannot be inferred from image
creation dates. An operator may seed the ledger from four verified successful
deployment receipts (oldest first, using the `record --sha` command); do not
substitute arbitrary local image tags. Corrupt history or an unreadable Docker
inventory stops the deployment.
Do not delete the history file to work around that refusal: repair it from
successful deploy receipts. Abbreviated operator SHAs protect all matching
full-SHA tags conservatively.

No force removal, broad Docker prune, container deletion or volume deletion is
used. Backups, PostgreSQL, research files and ECR images are untouched. A
concurrent container referencing an eligible image makes Docker refuse removal;
the deploy then stops before downloads.

After retention, root, Docker storage, containerd storage and deployment
filesystems must each have at least **8 GiB available** and be at or below
**85% used**. Each distinct filesystem is checked once; reserved filesystem
blocks do not count as available. A refusal prints available space and the
thresholds, while the running services remain in place. Cleanup cannot solve
growth in retained images, logs, volumes or backups: investigate those, or use
the Resize procedure below. It never broadens its deletion rules to clear a gate.

To inspect without deleting anything, on the host:

```bash
python3 bin/image_retention.py preflight \
  --registry "$AIA_IMAGE_REGISTRY" \
  --state-file /opt/aia/develop/.deploy-state/successful-releases.json \
  --protect <current-full-sha> --protect <incoming-full-sha>
```

Use the registry from the host's deployment configuration, without printing the
rest of `.env`. Standalone preflight is a dry run by default; `--apply` opts into
the same authorized policy as deploy. Full deployment provides the host lock;
do not run standalone `--apply` concurrently with a deployment.

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


### Backup scope

`bin/backup.sh` (nightly through `aia-backup.timer`, and before every deploy) dumps
PostgreSQL, where every Study's identity, bindings, Design Revisions and, since ADR
0018, working content live; the files a brief carries are artifacts in the artifact
bucket. It no longer touches the 18.6.6 unit: until the migration above has run and
its report has been accepted (OI-58), the content of Studies still waiting for it is
only in the unit's volume `aia-develop_legacy_state`, which this stack neither mounts
nor backs up.

Nothing writes to that volume except the reference unit while it runs. Copy it with
`deploy/reference/bin/backup-state.sh <sha> <label>` (the data owner's approval,
`AIA_LEGACY_STATE_BACKUP_ENABLED=true`, as above) once after the first deploy without
the unit if no `pre-adr-0018` copy was taken (nothing has changed the volume since the
unit stopped), after any session that used the reference unit, and before the
migration. It writes
`s3://<ops-bucket>/backups/legacy-state-<utc>-<label>.zip`: every `*.sqlite` under
`/app/data`, consistent one database at a time (not one atomic snapshot across them).
The files people attached (`/app/data/ui_uploads`) are not in the ZIP; they stay in
the volume, and the migration copies the ones its Studies name into AIA's storage.
`bin/restore.sh` restores PostgreSQL only; restoring the unit's databases is a
reference-side act, with the reference unit stopped (`deploy/reference/README.md`
§ The volume).

### AI settings

`/app/settings` has one AI section. What powers AIA comes from code, in the
settings document's `ai_runtime`: Bedrock, the instance-role credential, and each
native activity with its capabilities, versions and switches. The switches, region,
model and approved data classes come from the web container's nonsecret runtime
environment through `/config`. It has no provider login, direct API-key field,
selector or paid test button, and no 18.6.6 settings page is reachable from the
product. On develop the enabled capability is internal respondent fieldwork using
synthetic provenance; this is not real respondent evidence. Native design proposals
are implemented and off
(`AIA_AI_RESEARCH_AGENTS_ENABLED`). Each switch is read with the worker's vocabulary
(`1`/`true`/`yes`/`on`); a value the worker refuses is shown as invalid, not as off,
and with the runtime on it stops the whole worker. This display is not a live health
probe and never says connected or verified. Historical provider labels in archived
projects remain historical metadata, listed under a collapsed history, not
connection controls. Production-study material must be classified by its actual
content and provenance before design jobs are enabled (OI-63, OI-79).
