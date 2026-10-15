#!/usr/bin/env bash
# GlitchTip, AIA's error tracker, on the develop host (errors/docker-compose.yml).
#
#   bin/errors.sh up                  start (or update) GlitchTip and wait until healthy
#   bin/errors.sh down                stop it; its database volume is kept
#   bin/errors.sh status              its services and their health
#   bin/errors.sh admin <email>       create the first operator account (asks for a password)
#
# A Compose project of its own: nothing here starts, stops or recreates a service of
# AIA's stack, and AIA runs the same whether GlitchTip is up or not.

# shellcheck source=deploy/develop/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ERRORS=(docker compose --project-directory "$DEPLOY_DIR/errors" --env-file "$ENV_FILE"
        -f "$DEPLOY_DIR/errors/docker-compose.yml")

require_env_file

case "${1:-}" in
  up)
    docker network inspect aia-develop_internal > /dev/null 2>&1 \
      || die "AIA's network aia-develop_internal does not exist; deploy AIA first"
    log "starting GlitchTip"
    "${ERRORS[@]}" up -d --wait --wait-timeout 300
    log "GlitchTip is up at https://errors.$AIA_PUBLIC_HOSTNAME"
    ;;
  down)
    "${ERRORS[@]}" down
    log "GlitchTip stopped; its database volume is kept"
    ;;
  status)
    "${ERRORS[@]}" ps
    ;;
  admin)
    email="${2:-}"
    [ -n "$email" ] || die "usage: bin/errors.sh admin <email>"
    "${ERRORS[@]}" exec glitchtip ./manage.py createsuperuser --email "$email"
    ;;
  *)
    die "usage: bin/errors.sh up | down | status | admin <email>"
    ;;
esac
