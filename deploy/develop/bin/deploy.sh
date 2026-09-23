#!/usr/bin/env bash
# Deploy one git SHA to the develop host.
#
#   bin/deploy.sh <git-sha> [--no-migrate]
#
#   pull images          immutable <sha> tags from ECR, with the instance role
#   backup               pg_dump to S3, labelled pre-deploy-<sha> (skipped only on
#                        the very first deploy, when there is no database yet)
#   migrate              `alembic upgrade head` once, from the api image at <sha>;
#                        a failure stops here and the running services are untouched
#   switch               AIA_IMAGE_TAG=<sha> written to .env, then compose up --wait
#   smoke                bin/smoke.sh against the public hostname
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
"${COMPOSE[@]}" pull --quiet api worker web legacy-panel

# The legacy unit's data (population panels, demo payloads) lives in the EU ops
# bucket, never in an image or in Git (ADR 0011). Sync it before the service
# starts; the container hydrates and hash-verifies every file at start and
# refuses to run on a partial or drifted bundle.
if [ -n "${AIA_LEGACY_DATA_PREFIX:-}" ]; then
  log "syncing the legacy unit's data bundle from s3://$AIA_OPS_BUCKET/$AIA_LEGACY_DATA_PREFIX/"
  mkdir -p "$DEPLOY_DIR/legacy-data"
  aws s3 sync "s3://$AIA_OPS_BUCKET/$AIA_LEGACY_DATA_PREFIX/" "$DEPLOY_DIR/legacy-data" --only-show-errors --delete
else
  log "AIA_LEGACY_DATA_PREFIX is unset; the legacy unit will refuse to start without its data"
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

log "replacing services"
"${COMPOSE[@]}" up -d --remove-orphans --wait --wait-timeout 180

log "pruning images older than the previous deployment"
docker image prune -f --filter "until=168h" >/dev/null || true

log "smoke tests"
"$DEPLOY_DIR/bin/smoke.sh" "$SHA"
log "deployed $SHA"
