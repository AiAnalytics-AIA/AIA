#!/usr/bin/env bash
# Copy the 18.6.6 unit's working databases to the ops bucket, WAL-safe.
#
#   bin/backup-state.sh <git-sha> [label]
#       -> s3://$AIA_OPS_BUCKET/backups/legacy-state-<utc>-<label>.zip
#
# The copy the migration of 18.6.6 content reads (deploy/develop/README.md §
# Migrating 18.6.6 content): every *.sqlite under /app/data, copied through
# SQLite's backup API, so committed WAL data is in it and a live writer is never
# raced (a file copy of a WAL database can miss both). backup-legacy-state.py
# does the copying, inside the unit's own image:
#
#   the reference unit is running    in it, as it runs
#   it is not                        in a one-off container of the image at
#                                    <sha>, with no network and the unit's
#                                    entrypoint replaced, so nothing of the unit
#                                    starts and nothing hydrates or seeds
#
# Each database is opened read-only (SQLite may add its own -shm index beside
# it) and nothing is deleted. An export of the unit's working content leaves the
# host, so it needs the data owner's approval: AIA_LEGACY_STATE_BACKUP_ENABLED=true
# in the env file says it was given.

# shellcheck source=deploy/reference/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

SHA="${1:-}"
LABEL="${2:-manual}"
require_sha "$SHA"
require_env_file
require_state_volume
export AIA_REFERENCE_TAG="$SHA"
[ "${AIA_LEGACY_STATE_BACKUP_ENABLED:-false}" = "true" ] \
  || die "exporting the unit's working databases needs the data owner's approval (AIA_LEGACY_STATE_BACKUP_ENABLED=true)"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
key="backups/legacy-state-${stamp}-${LABEL}.zip"
script="$REFERENCE_DIR/bin/backup-legacy-state.py"

log "backing up the unit's working databases to s3://$AIA_OPS_BUCKET/$key"
if [ -n "$("${COMPOSE[@]}" ps --status running -q legacy-panel 2>/dev/null)" ]; then
  "${COMPOSE[@]}" exec -T legacy-panel python3 - < "$script" \
    | aws s3 cp - "s3://$AIA_OPS_BUCKET/$key" --region "$AWS_REGION" --only-show-errors
else
  registry_login
  image="$AIA_IMAGE_REGISTRY/aia-legacy-panel:$SHA"
  docker pull --quiet "$image" >/dev/null
  docker run --rm -i --network none --entrypoint python3 -v "$STATE_VOLUME:/app" "$image" - < "$script" \
    | aws s3 cp - "s3://$AIA_OPS_BUCKET/$key" --region "$AWS_REGION" --only-show-errors
fi

size="$(aws s3api head-object --bucket "$AIA_OPS_BUCKET" --key "$key" --region "$AWS_REGION" --query ContentLength --output text)"
[ "${size:-0}" -gt 100 ] || die "the backup object is ${size:-0} bytes; refusing to call that a backup"
log "backup complete: $key ($size bytes)"
