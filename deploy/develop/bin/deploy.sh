#!/usr/bin/env bash
# Deploy one git SHA to the develop host.
#
#   bin/deploy.sh <git-sha> [--no-migrate]
#
#   disk preflight       retain protected releases, remove old unused AIA images,
#                        then require disk headroom before downloading anything
#   pull images          immutable <sha> tags from ECR, with the instance role
#   check Caddy          the Caddyfile loaded with this host's .env; a failure stops
#                        here and the running services are untouched
#   backup               pg_dump to S3, labelled pre-deploy-<sha> (skipped only on
#                        the very first deploy, when there is no database yet)
#   migrate              `alembic upgrade head` once, from the api image at <sha>;
#                        a failure stops here and the running services are untouched
#   switch               AIA_IMAGE_TAG=<sha> written to .env, then compose up; waits
#                        until every service is healthy
#   errors               GlitchTip (bin/errors.sh up) when AIA_ERRORS_ENABLED is true;
#                        optional, a failure does not stop the deploy
#   docs                 ONLYOFFICE Docs (bin/docs.sh up) when AIA_ONLYOFFICE_ENABLED is
#                        true; optional, a failure does not stop the deploy
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

# The CI workflow serializes its deployments; this also protects against an
# operator deploying simultaneously, including the successful-release history.
exec 9>"$DEPLOY_DIR/.deploy.lock"
flock -n 9 || die "another deployment holds $DEPLOY_DIR/.deploy.lock; retry after it finishes"

export AIA_IMAGE_TAG="$SHA"
previous="$(deployed_sha)"
log "deploying $SHA (currently running: ${previous:-nothing})"

release_history="$DEPLOY_DIR/.deploy-state/successful-releases.json"
protected=(--protect "$SHA")
[ -z "$previous" ] || protected+=(--protect "$previous")
log "protected image retention and disk preflight"
python3 "$DEPLOY_DIR/bin/image_retention.py" preflight \
  --registry "$AIA_IMAGE_REGISTRY" --state-file "$release_history" \
  --deploy-dir "$DEPLOY_DIR" "${protected[@]}" --apply

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

# Each population version's field dictionary, kept with it (population-operations P7a):
# a version imported before dictionaries were kept gets its own, checked against the
# version's hash, so its characteristics can be read without the panel. Acts as no one and
# decides nothing; with no version, or every dictionary kept, it changes nothing. A refusal
# (a file missing from AIA_POPULATION_DIR, a hash that does not match) is said and does not
# undo a deploy that is otherwise healthy: the page then says the dictionary is not kept.
log "keeping each population version's dictionary"
if ! "$DEPLOY_DIR/bin/population.sh" record-dictionary; then
  log "WARNING: a population dictionary could not be kept (above); the deploy goes on"
fi

# Each established population's audience factor catalogue, computed once from its current
# version's ANALYSIS view and kept with it (panel-grounded-respondents 6b), so the audience
# step's factor editor is served without reading a row. Acts as no one and decides nothing;
# with every catalogue kept it changes nothing. A refusal (the population will not load) is
# said and does not undo a deploy that is otherwise healthy: the step then says the
# catalogue is not kept. Bounded: a catalogue is seconds of work (3.6 s to load v17's
# 18,766 rows, measured), so five minutes means the host is stuck, and a stuck optional
# step must not hold the deploy or its lock (2026-10-13: it held both for an hour).
log "keeping each population's audience catalogue"
catalogue_status=0
timeout --kill-after=30 300 "$DEPLOY_DIR/bin/population.sh" record-catalogue || catalogue_status=$?
case "$catalogue_status" in
  0) ;;
  124|137) log "WARNING: record-catalogue did not finish in 5 minutes and was stopped; no catalogue was kept; the deploy goes on" ;;
  *) log "WARNING: an audience catalogue could not be kept (above); the deploy goes on" ;;
esac

# Sealed Research Leads past their 30 days (ADR 0030, settings-backends SB2): a deactivated
# member's Lead, its conversations and what its turns sent and got back, erased. Acts as no
# one; with nothing due it changes nothing. Optional and bounded like the catalogue: a
# failure is said, the deploy goes on, and the next deploy picks up what is left.
log "erasing sealed Leads past their date"
retention_status=0
timeout --kill-after=30 300 "${COMPOSE[@]}" run --rm --no-deps -T worker \
  python -m aia_executors.lead_retention --apply || retention_status=$?
if [ "$retention_status" -ne 0 ]; then
  log "WARNING: the sealed-Lead retention sweep did not finish (status $retention_status); the deploy goes on"
fi

# GlitchTip, the error tracker (errors/docker-compose.yml), when SSM aia_errors_enabled is
# true: started or updated after AIA is healthy, in a project of its own, so a change to
# AIA's network is picked up. Optional: a failure is said and the deploy goes on, since AIA
# runs the same without it. Bounded like the catalogue above.
if [ "${AIA_ERRORS_ENABLED:-false}" = "true" ]; then
  log "starting GlitchTip"
  if ! timeout --kill-after=30 360 "$DEPLOY_DIR/bin/errors.sh" up; then
    log "WARNING: GlitchTip did not start (above); errors are not tracked; the deploy goes on"
  fi
fi

# ONLYOFFICE Docs, Zpráva's report editor (docs/docker-compose.yml), when SSM
# aia_onlyoffice_enabled is true: started or updated after AIA is healthy, in a project of its
# own. Optional like GlitchTip: without it Zpráva keeps its read-only pane. A start runs
# upstream's whole start sequence (fonts, then gzipping its static files) before api.js takes its
# fixed tag and the server reports healthy: 274-330 s measured (4 vCPU), hence the longer bound.
if [ "${AIA_ONLYOFFICE_ENABLED:-false}" = "true" ]; then
  log "starting the Document Server"
  if ! timeout --kill-after=30 660 "$DEPLOY_DIR/bin/docs.sh" up; then
    log "WARNING: the Document Server did not start (above); Zpráva stays read-only; the deploy goes on"
  fi
# Switched off while it runs: stopped here, so turning it off needs no hand on the host. Its
# volumes are kept (bin/docs.sh down).
elif [ -n "$(docker ps -q --filter label=com.docker.compose.project=aia-docs)" ]; then
  log "stopping the Document Server: aia_onlyoffice_enabled is not true"
  if ! timeout --kill-after=30 120 "$DEPLOY_DIR/bin/docs.sh" down; then
    log "WARNING: the Document Server did not stop (above); the deploy goes on"
  fi
fi

log "smoke tests"
"$DEPLOY_DIR/bin/smoke.sh" "$SHA"
python3 "$DEPLOY_DIR/bin/image_retention.py" record \
  --state-file "$release_history" --sha "$SHA" --previous "$previous"
log "deployed $SHA"
