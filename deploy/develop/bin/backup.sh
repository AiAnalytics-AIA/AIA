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
# The 18.6.6 unit's working databases are not the product's and are not backed
# up here (ADR 0018): deploy/reference/bin/backup-state.sh copies them, WAL-safe,
# from the unit's volume, which this stack no longer mounts.
