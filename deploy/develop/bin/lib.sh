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

ecr_login() {
  aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$AIA_IMAGE_REGISTRY" >/dev/null
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
