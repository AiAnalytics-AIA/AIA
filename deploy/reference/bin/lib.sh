#!/usr/bin/env bash
# Shared helpers for the 18.6.6 reference unit's scripts. Sourced, not executed.
#
# The reference runs beside the product on the develop host, as root (an SSM
# session or Run Command), and reads the host's env file for the registry, the
# ops bucket and the gate's credentials. It sources nothing of the product's
# scripts, so a change to deploy/develop can never break it, and the product
# reads nothing of this directory. Nothing here echoes a value from the env
# file: names and outcomes only.

set -euo pipefail

REFERENCE_DIR="${REFERENCE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_FILE="${ENV_FILE:-/opt/aia/develop/.env}"
COMPOSE=(docker compose --project-directory "$REFERENCE_DIR" --env-file "$ENV_FILE" -f "$REFERENCE_DIR/docker-compose.yml")
# The unit's working volume: the product stack's until ADR 0018, kept as it was.
STATE_VOLUME="${AIA_REFERENCE_STATE_VOLUME:-aia-develop_legacy_state}"

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

require_env_file() {
  [ -f "$ENV_FILE" ] || die "$ENV_FILE is missing; the develop host writes it with deploy/develop/bin/write-env.sh"
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
  : "${AIA_IMAGE_REGISTRY:?}" "${AWS_REGION:?}" "${AIA_OPS_BUCKET:?}"
}

require_sha() {
  local sha="${1:-}"
  [[ "$sha" =~ ^[0-9a-f]{7,40}$ ]] || die "expected the git SHA of an aia-legacy-panel image, got '${sha}'"
}

# The volume holds the unit's working databases and files (OI-58). It is never
# created here: on a host that lost it, an empty one would start a unit that
# looks healthy and holds nothing. Restore it first (README.md § The volume).
require_state_volume() {
  docker volume inspect "$STATE_VOLUME" >/dev/null 2>&1 \
    || die "the unit's working volume $STATE_VOLUME does not exist; see deploy/reference/README.md § The volume before creating one"
}

# The registry credentials come from the instance role. The product's deploy
# installs Amazon's ECR credential helper and names it in docker's config.json;
# when it is there, a pull needs nothing else. Otherwise a docker login stores a
# 12-hour token on disk, which is said rather than done quietly.
registry_login() {
  if command -v docker-credential-ecr-login >/dev/null 2>&1; then
    export AWS_ECR_DISABLE_CACHE=true
    return
  fi
  log "WARNING: no ECR credential helper; docker login stores a 12-hour registry token unencrypted"
  aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$AIA_IMAGE_REGISTRY" >/dev/null
}
