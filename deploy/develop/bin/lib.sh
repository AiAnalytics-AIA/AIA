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
# The 18.6.6 unit's working volume, which this stack mounted until ADR 0018 and
# deploy/reference mounts now. Named only so the deploy can prove it kept it.
LEGACY_STATE_VOLUME="aia-develop_legacy_state"

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

# Until ADR 0018 this stack ran the 18.6.6 unit as its service `legacy-panel`.
# A host deployed before it still has that container: these find it, stop it the
# way its service did, and say whether its working volume is still there. On a
# host that never ran the unit all three are no-ops. They go once the volume's
# content is migrated and the data owner has accepted the report (OI-58).
product_unit_containers() {
  docker ps -a -q --filter "label=com.docker.compose.project=aia-develop" \
    --filter "label=com.docker.compose.service=legacy-panel"
}

unit_volume_exists() {
  docker volume inspect "$LEGACY_STATE_VOLUME" >/dev/null 2>&1
}

# 30 s, the service's stop_grace_period, so the unit's SQLite stores close
# cleanly; `compose up --remove-orphans` would give an orphan only Compose's 10 s.
# The container is left for `--remove-orphans`; the volume is never touched.
retire_product_unit() {
  local ids
  ids="$(product_unit_containers)"
  [ -n "$ids" ] || return 0
  log "retiring the 18.6.6 unit's container from the product stack (ADR 0018); its volume $LEGACY_STATE_VOLUME stays"
  # shellcheck disable=SC2086 -- one id per word
  docker stop -t 30 $ids >/dev/null
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
