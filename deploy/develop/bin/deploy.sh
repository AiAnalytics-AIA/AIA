#!/usr/bin/env bash
# Deploy one git SHA to the develop host.
#
#   bin/deploy.sh <git-sha> [--no-migrate]
#
#   pull images          immutable <sha> tags from ECR, with the instance role
#   check Caddy          the Caddyfile loaded with this host's .env; a failure stops
#                        here and the running services are untouched
#   backup               pg_dump to S3, labelled pre-deploy-<sha> (skipped only on
#                        the very first deploy, when there is no database yet)
#   migrate              `alembic upgrade head` once, from the api image at <sha>;
#                        a failure stops here and the running services are untouched
#   switch               AIA_IMAGE_TAG=<sha> written to .env, then compose up; waits
#                        until every service is healthy
#   smoke                bin/smoke.sh against the public hostname
#
# Nothing of NPC Panel 18.6.6 is pulled, synced, started or waited on (ADR 0018
# decision 5): the unit runs, when a comparison needs it, from deploy/reference.
#
# --no-migrate is for rolling back to a previous SHA whose schema is already
# present (or older). It never runs `alembic downgrade`: schema rollback is a
# separate, documented, human decision (README § Rollback).
#
# Idempotent: deploying the SHA already running pulls, backs up, migrates
# (a no-op) and restarts nothing that has not changed.

# shellcheck source=deploy/develop/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

SHA="${1:-}"
MIGRATE=1
[ "${2:-}" = "--no-migrate" ] && MIGRATE=0
require_sha "$SHA"
require_env_file
cd "$DEPLOY_DIR" || exit 1

export AIA_IMAGE_TAG="$SHA"
previous="$(deployed_sha)"
log "deploying $SHA (currently running: ${previous:-nothing})"

log "logging in to ECR and pulling images"
ecr_login
"${COMPOSE[@]}" pull --quiet api worker web

# The Caddyfile decides whether anyone reaches the site. Load it with this host's
# configuration before anything is touched: run 10 (2026-09-23) replaced every
# service and only then found Caddy could not parse its file, and the site was
# down until the next deploy.
log "validating the Caddyfile against this host's configuration"
if ! caddy_check="$("${COMPOSE[@]}" run --rm --no-deps -T caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1)"; then
  printf '%s\n' "$caddy_check" | grep -v '"level":"info"' | tail -5 >&2
  die "the Caddyfile does not load with this host's configuration; the running services were not replaced"
fi

log "starting postgres"
"${COMPOSE[@]}" up -d --wait postgres

if postgres_running && "${COMPOSE[@]}" exec -T postgres psql -U aia -d aia -tAc "select 1 from information_schema.tables where table_name='alembic_version'" | grep -q 1; then
  log "backing up before migration"
  "$DEPLOY_DIR/bin/backup.sh" "pre-deploy-$SHA"
else
  log "no migrated database yet; skipping the pre-deploy backup"
fi

if [ "$MIGRATE" = 1 ]; then
  log "running alembic upgrade head from the api image at $SHA"
  # One-off container, the service's environment, no dependencies started, and
  # nothing else touched until it succeeds. The API and worker never migrate.
  if ! "${COMPOSE[@]}" run --rm --no-deps -T api alembic upgrade head; then
    die "migration failed; the running services were not replaced"
  fi
else
  log "--no-migrate: leaving the schema as it is"
fi

log "recording AIA_IMAGE_TAG=$SHA"
if grep -q '^AIA_IMAGE_TAG=' "$ENV_FILE"; then
  sed -i "s/^AIA_IMAGE_TAG=.*/AIA_IMAGE_TAG=$SHA/" "$ENV_FILE"
else
  printf 'AIA_IMAGE_TAG=%s\n' "$SHA" >> "$ENV_FILE"
fi

# A host deployed before ADR 0018 still runs the 18.6.6 unit's container, which
# `--remove-orphans` below removes: stop it gracefully first (lib.sh). Its
# working volume stays, and the deploy fails if it were gone afterwards.
had_unit_volume=0
unit_volume_exists && had_unit_volume=1
retire_product_unit

log "replacing services"
"${COMPOSE[@]}" up -d --remove-orphans --wait --wait-timeout 180

if [ "$had_unit_volume" = 1 ] && ! unit_volume_exists; then
  die "the 18.6.6 unit's working volume $LEGACY_STATE_VOLUME is gone; restore it before anything else (deploy/reference/README.md § The volume)"
fi

log "pruning images older than the previous deployment"
docker image prune -f --filter "until=168h" >/dev/null || true

log "smoke tests"
"$DEPLOY_DIR/bin/smoke.sh" "$SHA"
log "deployed $SHA"
