# The 18.6.6 reference unit

NPC Panel 18.6.6, the vendored unit at `legacy/npc-panel-18.6.6/`
([ADR 0011](../../docs/architecture/adr/0011-vendor-legacy-product-unit.md)), run
**beside** the develop host's product when a comparison needs it: the parity oracle
(`tools/legacy_oracle.py`, `make test-oracle`) and the behavioural reference for a
port. It is not part of AIA
([ADR 0018](../../docs/architecture/adr/0018-aia-runs-without-18-6-6.md) decision 5):
the product deployment in [`deploy/develop`](../develop/README.md) has no unit
image, service, volume mount, hostname, credential, data sync or health check, and
starts, deploys and passes its smoke checks whether this is up, down or absent.

| | |
|---|---|
| `docker-compose.yml` | Compose project `aia-reference`: `legacy-panel` (the unit) and `gate` (Caddy, basic auth) on a network of their own |
| `Caddyfile` | the gate: basic auth, then the unit; plain HTTP on the host's loopback |
| `bin/up.sh <sha>` | pull `aia-legacy-panel:<sha>`, sync the data bundle, start both, wait until the unit is healthy |
| `bin/down.sh` | stop both; the volume and the data directory stay |
| `bin/backup-state.sh <sha> [label]` | the unit's working databases, WAL-safe, to `s3://<ops>/backups/legacy-state-<utc>-<label>.zip` |
| `bin/backup-legacy-state.py` | the copier the backup runs inside the unit's image (SQLite's backup API) |

Nothing here runs by itself: no timer, no deploy step, no `restart` policy that
brings it back after a reboot.

## Getting it onto the host

The *Reference unit* workflow (`.github/workflows/reference-unit.yml`, dispatched
by hand) builds `aia-legacy-panel:<sha>` from `legacy/npc-panel-18.6.6` and ships
this directory as `s3://<ops>/deploy/reference-<sha>.tar.gz`. It changes nothing
on the host. GitHub dispatches only workflows on the default branch. Until this one
is there, the images a develop deploy pushed before ADR 0018 are in ECR (the
repository keeps the 30 newest), so any of those SHAs will do for the image, and an
operator with the ops bucket's credentials ships the bundle from a checkout the way
the workflow does:

```bash
tar -czf reference-bundle.tar.gz -C deploy/reference docker-compose.yml Caddyfile README.md bin
aws s3 cp reference-bundle.tar.gz "s3://<ops-bucket>/deploy/reference-<sha>.tar.gz"
```

On the host, as root:

```bash
mkdir -p /opt/aia/reference && cd /opt/aia/reference
aws s3 cp "s3://$AIA_OPS_BUCKET/deploy/reference-<sha>.tar.gz" - | tar -xz
bin/up.sh <sha>
```

It reads the host's env file, `/opt/aia/develop/.env` (written by
`deploy/develop/bin/write-env.sh` from SSM): `AIA_IMAGE_REGISTRY`, `AWS_REGION`,
`AIA_OPS_BUCKET`, `AIA_LEGACY_DATA_PREFIX` (the data bundle), and the gate's
`AIA_LEGACY_BASIC_USER` / `AIA_LEGACY_BASIC_HASH` (SSM `aia_legacy_basic_user`,
`aia_legacy_basic_hash`). Optional: `AIA_REFERENCE_PORT` (8765),
`AIA_REFERENCE_STATE_VOLUME`, `AIA_REFERENCE_DATA_DIR`
(`/opt/aia/develop/legacy-data`), `ENV_FILE`.

## The volume

`aia-develop_legacy_state` is the unit's whole working tree: its SQLite stores
(`/app/data/project_store.sqlite` and the rest), the files people attached, its
runs and logs. It is the volume the product stack mounted before ADR 0018, kept
exactly as it was when the product stopped running the unit. The Compose file
declares it `external`, so:

- `up` refuses to start without it (`bin/up.sh` says so first) instead of starting
  an empty unit that looks healthy and holds nothing;
- `down` cannot remove it, and no script here passes `--volumes`.

**Do not delete it, and do not `docker volume create` it on the develop host**
until the migration of its content into AIA has run, been verified and its report
accepted (`deploy/develop/README.md` § Migrating 18.6.6 content, OI-58). If it is
ever missing there, restore it from the newest `backups/legacy-state-*.zip`
before anything else. On a host that never ran the unit, an empty one is created
explicitly: `docker volume create aia-develop_legacy_state`.

**Restoring its databases** from a `legacy-state-*.zip` is done with the reference
unit stopped (`bin/down.sh`), after copying the current state first
(`bin/backup-state.sh`), and before starting it again the restored project IDs are
checked against the Studies' bindings in PostgreSQL (`study_workspaces`). The unit's
own start installs a `state_seed` only where no working file exists: it hash-verifies
the seed on first installation and its immutable assets on every start, and never
replaces edited state with archive bytes.

## Reaching it

The gate listens on `127.0.0.1:8765` of the host and nowhere else. From another
machine, forward the port through SSM (encrypted, no inbound port):

```bash
aws ssm start-session --target <instance-id> \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8765"],"localPortNumber":["8765"]}'
```

then, in another shell, the oracle suite against it:

```bash
AIA_LEGACY_REFERENCE_URL=http://127.0.0.1:8765 \
AIA_LEGACY_REFERENCE_USER=<the basic-auth user> \
AIA_LEGACY_REFERENCE_PASSWORD=<its password> \
make test-oracle
```

`tools/legacy_oracle.py` refuses an oracle without the gate
(`test_anonymous_request_is_refused`), which is why the gate is part of this stack.
CI's `oracle-parity` job has no `AIA_LEGACY_REFERENCE_*` secrets configured and
reports its gates as `NOT_EXECUTED`; a CI runner cannot reach the host's loopback,
so it stays that way unless a runner inside the VPC is added.

The legacy hostname (`AIA_LEGACY_HOSTNAME`) is no longer served by anything: the
product's Caddy has no site for it. Its DNS record, if one exists outside
Terraform, can be removed by whoever manages the zone.

## Backups

`bin/backup-state.sh <sha> [label]` copies every `*.sqlite` under `/app/data`
through SQLite's backup API, so committed WAL data is included and a running unit
is never raced. With the reference unit running it runs inside it; otherwise in a
one-off container of the unit's image with no network and the unit's entrypoint
replaced, so nothing of the unit starts, hydrates or seeds. It is an export of
working content, so it needs `AIA_LEGACY_STATE_BACKUP_ENABLED=true` (the data
owner's approval) in the env file. The migration reads such a copy, never the
live volume.
