#!/usr/bin/env bash
# Restore a backup, either for real or as a rehearsal.
#
#   bin/restore.sh --test  [key|latest]   restore into a scratch database, report
#                                          table and row counts, drop it. The live
#                                          database is not touched. Run this after
#                                          any change to the backup path, and
#                                          monthly.
#   bin/restore.sh --live  <key|latest>    stop api and worker, replace the live
#                                          database with the dump, start them,
#                                          run smoke. Destructive: the current
#                                          contents are dumped first, labelled
#                                          pre-restore.
#
# Develop holds synthetic data only. The point of the rehearsal is to prove the
# procedure, so that the first real restore is not also the first attempt.

# shellcheck source=deploy/develop/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

MODE="${1:-}"
KEY="${2:-latest}"
case "$MODE" in --test|--live) ;; *) die "usage: restore.sh --test|--live [key|latest]" ;; esac
require_env_file
cd "$DEPLOY_DIR" || exit 1
postgres_running || die "postgres is not running"

if [ "$KEY" = "latest" ]; then
  KEY="$(aws s3api list-objects-v2 --bucket "$AIA_OPS_BUCKET" --prefix backups/ --region "$AWS_REGION" \
          --query 'sort_by(Contents, &LastModified)[-1].Key' --output text)"
  if [ -z "$KEY" ] || [ "$KEY" = "None" ]; then die "no backups under s3://$AIA_OPS_BUCKET/backups/"; fi
fi
log "using s3://$AIA_OPS_BUCKET/$KEY"

# pg_restore reads the custom format from a file, not a pipe; stream it into the
# container's tmpfs so nothing lands on the host disk.
fetch_into_container() {
  aws s3 cp "s3://$AIA_OPS_BUCKET/$KEY" - --region "$AWS_REGION" --only-show-errors \
    | "${COMPOSE[@]}" exec -T postgres sh -c 'cat > /dev/shm/restore.dump'
}

if [ "$MODE" = "--test" ]; then
  scratch="aia_restore_test_$(date -u +%s)"
  log "restoring into scratch database $scratch"
  fetch_into_container
  "${COMPOSE[@]}" exec -T postgres psql -U aia -d postgres -qc "CREATE DATABASE $scratch"
  "${COMPOSE[@]}" exec -T postgres pg_restore -U aia -d "$scratch" --no-owner --no-privileges /dev/shm/restore.dump
  "${COMPOSE[@]}" exec -T postgres psql -U aia -d "$scratch" -tAc "
    select 'tables=' || count(*) from information_schema.tables where table_schema='public';
    select 'alembic_version=' || version_num from alembic_version;
    select 'organizations=' || count(*) from organizations;
    select 'studies=' || count(*) from studies;
    select 'workflow_runs=' || count(*) from workflow_runs;
    select 'project_artifacts=' || count(*) from project_artifacts;"
  "${COMPOSE[@]}" exec -T postgres psql -U aia -d postgres -qc "DROP DATABASE $scratch"
  "${COMPOSE[@]}" exec -T postgres rm -f /dev/shm/restore.dump
  log "restore rehearsal complete; the live database was not touched"
  exit 0
fi

# --live
log "dumping the current contents first"
"$DEPLOY_DIR/bin/backup.sh" "pre-restore"
log "stopping api and worker"
"${COMPOSE[@]}" stop api worker
fetch_into_container
log "replacing the live database"
"${COMPOSE[@]}" exec -T postgres psql -U aia -d postgres -qc "DROP DATABASE aia"
"${COMPOSE[@]}" exec -T postgres psql -U aia -d postgres -qc "CREATE DATABASE aia"
"${COMPOSE[@]}" exec -T postgres pg_restore -U aia -d aia --no-owner --no-privileges /dev/shm/restore.dump
"${COMPOSE[@]}" exec -T postgres rm -f /dev/shm/restore.dump
log "starting api and worker"
"${COMPOSE[@]}" up -d --wait api worker
"$DEPLOY_DIR/bin/smoke.sh" "$(grep '^AIA_IMAGE_TAG=' "$ENV_FILE" | cut -d= -f2)"
log "live restore complete"
