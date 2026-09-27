#!/usr/bin/env bash
# Dump the develop database to S3.
#
#   bin/backup.sh [label]        -> s3://$AIA_OPS_BUCKET/backups/aia-<utc>-<label>.dump
#
# Runs nightly from the systemd timer installed by cloud-init, and before every
# migration from bin/deploy.sh. pg_dump's custom format is compressed and
# restorable table by table. The bucket is EU-resident, encrypted at rest,
# versioned, blocks public access and expires objects under backups/ by a
# lifecycle rule (infra/develop, 30 days). The dump never touches the host disk.
#
# The upload is verified by size: an empty object is a failed backup, and a
# failed backup fails the deploy that asked for it.

# shellcheck source=deploy/develop/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

LABEL="${1:-nightly}"
require_env_file
cd "$DEPLOY_DIR" || exit 1
postgres_running || die "postgres is not running; nothing to back up"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
key="backups/aia-${stamp}-${LABEL}.dump"

log "dumping to s3://$AIA_OPS_BUCKET/$key"
"${COMPOSE[@]}" exec -T postgres pg_dump -U aia -d aia --format=custom --compress=6 \
  | aws s3 cp - "s3://$AIA_OPS_BUCKET/$key" --region "$AWS_REGION" --only-show-errors

size="$(aws s3api head-object --bucket "$AIA_OPS_BUCKET" --key "$key" --region "$AWS_REGION" --query ContentLength --output text)"
[ "${size:-0}" -gt 1024 ] || die "backup object is ${size:-0} bytes; refusing to call that a backup"
log "backup complete: $key ($size bytes)"
# The research editing copy still lives in the legacy SQLite store (OI-58).
# PostgreSQL retains its study binding, not that editing content. Back up the
# live databases before any container replacement; a file copy would miss WAL.
# Export requires separate owner approval; leave it off until explicitly enabled.
if [ "${AIA_LEGACY_STATE_BACKUP_ENABLED:-false}" != "true" ]; then
  log "legacy working database export is disabled; owner approval is required"
elif [ -n "$("${COMPOSE[@]}" ps --status running -q legacy-panel)" ]; then
  state_key="backups/legacy-state-${stamp}-${LABEL}.zip"
  log "backing up legacy working databases to s3://$AIA_OPS_BUCKET/$state_key"
  "${COMPOSE[@]}" exec -T legacy-panel python - < "$DEPLOY_DIR/bin/backup-legacy-state.py" \
    | aws s3 cp - "s3://$AIA_OPS_BUCKET/$state_key" --region "$AWS_REGION" --only-show-errors
  state_size="$(aws s3api head-object --bucket "$AIA_OPS_BUCKET" --key "$state_key" --region "$AWS_REGION" --query ContentLength --output text)"
  [ "${state_size:-0}" -gt 100 ] || die "legacy state backup is too small"
  log "legacy state backup complete: $state_key ($state_size bytes)"
else
  log "legacy-panel is not running; no legacy working database backup available"
fi
