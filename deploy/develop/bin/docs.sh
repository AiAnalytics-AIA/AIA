#!/usr/bin/env bash
# ONLYOFFICE Docs, Zpráva's report editor, on the develop host (docs/docker-compose.yml).
#
#   bin/docs.sh up        start (or update) the Document Server and wait until healthy
#   bin/docs.sh down      stop it; its volumes are kept
#   bin/docs.sh status    its service and its health
#   bin/docs.sh logs      its last 200 log lines
#
# A Compose project of its own: nothing here starts, stops or recreates a service of
# AIA's stack, and AIA runs the same whether the Document Server is up or not.

# shellcheck source=deploy/develop/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

DOCS=(docker compose --project-directory "$DEPLOY_DIR/docs" --env-file "$ENV_FILE"
      -f "$DEPLOY_DIR/docs/docker-compose.yml")
# Compose interpolates the whole file for every command, and the secret is required there (:?),
# so once a rollback deleted it, down, status and logs would refuse too. Only up keeps the guard;
# the others use no secret, and get a placeholder only when there is none.
if [ "${1:-}" != "up" ]; then
  export AIA_ONLYOFFICE_JWT_SECRET="${AIA_ONLYOFFICE_JWT_SECRET:-unused-unless-starting}"
fi

require_env_file

case "${1:-}" in
  up)
    docker network inspect aia-docs > /dev/null 2>&1 \
      || die "the network aia-docs does not exist; deploy AIA first"
    log "starting the Document Server"
    "${DOCS[@]}" up -d --wait --wait-timeout 600
    log "the Document Server is up at https://docs.$AIA_PUBLIC_HOSTNAME"
    ;;
  down)
    "${DOCS[@]}" down
    log "the Document Server stopped; its volumes are kept"
    ;;
  status)
    "${DOCS[@]}" ps
    ;;
  logs)
    "${DOCS[@]}" logs --tail 200 onlyoffice
    ;;
  *)
    die "usage: bin/docs.sh up | down | status | logs"
    ;;
esac
