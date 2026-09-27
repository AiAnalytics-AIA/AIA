#!/usr/bin/env bash
# Shared helpers for the develop host scripts. Sourced, not executed.
#
# Every script runs on the host as root (SSM Run Command or an operator shell),
# from DEPLOY_DIR, with the configuration in DEPLOY_DIR/.env. Nothing here echoes
# a value from that file: the scripts print names and outcomes, never secrets.

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/aia/develop}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"
COMPOSE=(docker compose --project-directory "$DEPLOY_DIR" --env-file "$ENV_FILE")

# Caddy reads its Caddyfile once, at start, and `compose up` recreates a
# container only when its image or its Compose configuration changes -- never
# because the contents of a bind-mounted file did. The Caddyfile's hash is
# therefore part of the caddy service's configuration (a label in
# docker-compose.yml): a changed Caddyfile recreates Caddy on the next `up`, an
# unchanged one restarts nothing. Deploy run 14 (2026-09-24) shipped a new
# Caddyfile that the running Caddy never read (OI-45). Computed here so every
# script that runs `compose up` sees the same value.
if [ -f "$DEPLOY_DIR/Caddyfile" ]; then
  AIA_CADDYFILE_SHA256="$(sha256sum "$DEPLOY_DIR/Caddyfile" | cut -d' ' -f1)"
  export AIA_CADDYFILE_SHA256
fi

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

require_env_file() {
  [ -f "$ENV_FILE" ] || die "$ENV_FILE is missing; run bin/write-env.sh first"
  # Read the file's *names* into the shell without printing anything.
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
  : "${AIA_IMAGE_REGISTRY:?}" "${AWS_REGION:?}" "${AIA_PUBLIC_HOSTNAME:?}" "${AIA_OPS_BUCKET:?}"
}

# A git object name, full or abbreviated. Anything else is refused: a deploy of
# "develop" or "latest" would not be traceable to a commit.
require_sha() {
  local sha="${1:-}"
  [[ "$sha" =~ ^[0-9a-f]{7,40}$ ]] || die "expected a git SHA, got '${sha}'"
}

# Registry credentials come from the instance role through Amazon's ECR credential
# helper, so no registry token is kept on disk. `docker login` stored the 12-hour
# token unencrypted in ~/.docker/config.json, and Docker said so on every deploy.
# The helper's own token cache (~/.ecr/cache.json, also plain text) is switched
# off for every docker call these scripts make.
#
# The helper is installed here rather than in user-data: cloud-init runs once per
# instance, so a new package there would never reach the running host, and a
# changed user_data stops and starts the host on the next `terraform apply`.
# When it cannot be installed, the deploy falls back to `docker login` and says
# so: a pull that works beats a deploy that fails over credential hygiene.
export AWS_ECR_DISABLE_CACHE=true

# The directory docker reads config.json from. SSM Run Command starts these
# scripts as root with no HOME at all (deploy run 26, 2026-09-27, stopped on
# "HOME: unbound variable"); docker then falls back to the passwd entry's home,
# so this does the same rather than guess.
docker_config_dir() {
  if [ -n "${DOCKER_CONFIG:-}" ]; then
    printf '%s\n' "$DOCKER_CONFIG"
    return
  fi
  local home="${HOME:-}"
  if [ -z "$home" ]; then
    home="$(getent passwd "$(id -u)" | cut -d: -f6)" || home=""
  fi
  [ -n "$home" ] || die "no home directory for uid $(id -u); set HOME or DOCKER_CONFIG so docker and this script read the same config.json"
  printf '%s/.docker\n' "$home"
}

ecr_login() {
  local registry="${AIA_IMAGE_REGISTRY%%/*}"
  local config_dir config next
  config_dir="$(docker_config_dir)" || exit 1
  config="$config_dir/config.json"
  if ! command -v docker-credential-ecr-login >/dev/null 2>&1; then
    log "installing the ECR credential helper"
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y -qq amazon-ecr-credential-helper >/dev/null 2>&1 \
      || { apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq amazon-ecr-credential-helper >/dev/null 2>&1; } \
      || true
  fi
  if ! command -v docker-credential-ecr-login >/dev/null 2>&1; then
    log "WARNING: the ECR credential helper is not installed; docker login stores a 12-hour registry token unencrypted in $config (deploy/develop/README.md § Registry credentials)"
    aws ecr get-login-password --region "$AWS_REGION" \
      | docker login --username AWS --password-stdin "$AIA_IMAGE_REGISTRY" >/dev/null
    return
  fi
  # Name the helper for this registry and drop any token an earlier login stored.
  # Other registries' entries are left as they are.
  mkdir -p "$config_dir"
  chmod 700 "$config_dir"
  [ -s "$config" ] || printf '{}\n' >"$config"
  next="$(mktemp "$config_dir/.config.json.XXXXXX")"
  if ! jq --arg r "$registry" \
    '.credHelpers[$r] = "ecr-login" | if has("auths") then .auths |= del(.[$r]) else . end' \
    "$config" >"$next"; then
    rm -f "$next"
    die "$config is not valid JSON; fix or remove it, then deploy again"
  fi
  chmod 600 "$next"
  mv "$next" "$config"
  log "registry credentials: ECR credential helper (instance role), nothing stored"
}

# The 18.6.6 unit's health once it has finished starting. The unit is recreated on
# every deploy (its image is tagged by SHA) and hydrates its data on start, so its
# healthcheck says "starting" for up to its start period (120 s,
# legacy/npc-panel-18.6.6/Dockerfile). The deploy does not wait for it, by design,
# and a single read raced it: deploy runs 29 and 30 (2026-09-27) failed smoke
# on "starting", about 20 s after the unit was recreated, while every other
# check passed. This waits out "starting" for at most
# LEGACY_START_WAIT_SECONDS (default 150), then prints the state. An unhealthy,
# exited or missing unit is reported at once.
legacy_unit_health() {
  local id="$1" state waited=0
  local limit="${LEGACY_START_WAIT_SECONDS:-150}" step="${LEGACY_POLL_SECONDS:-5}"
  while :; do
    state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null)" || state="missing"
    [ -n "$state" ] || state="missing"
    if [ "$state" != "starting" ] || [ "$waited" -ge "$limit" ]; then break; fi
    sleep "$step"
    waited=$((waited + step))
  done
  printf '%s\n' "$state"
}

# The running API's build, as /health reports it. Empty when it is not answering.
deployed_sha() {
  curl -fsS --max-time 5 "https://${AIA_PUBLIC_HOSTNAME}/api/v1/health" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["build"]["sha"] or "")' 2>/dev/null \
    || true
}

postgres_running() {
  [ "$("${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -c '^postgres$')" = "1" ]
}
