# shellcheck shell=bash
# Sourced by bin/smoke.sh: the report editor's rows (plan report-editor-hosting, chunk 4a).
#
# Run only when SSM aia_onlyoffice_enabled is true. What AIA itself serves on docs.<hostname>
# fails the smoke like any other row, because it holds whether the Document Server runs or not:
# the docs gate refuses a request without its cookie, the server's own paths are refused at
# Caddy, /__aia/session without a ticket opens nothing, and a forged cache link is not served. The
# Document Server's health only warns: it never fails a deploy (bin/deploy.sh), and without it
# Zpráva stays read-only.
#
# Uses smoke.sh's pass, fail, warn, code and status_of.

# Every probe below reads "000" when nothing answers, so a failure is a row, never an abort of the
# smoke under lib.sh's errexit and pipefail.
docs_container() {
  { docker ps -q --filter label=com.docker.compose.project=aia-docs \
      --filter label=com.docker.compose.service=onlyoffice 2>/dev/null || true; } | head -1
}

# Why the gate or the ticket exchange answered what it did, when it is not what it should.
docs_why() {
  case "$1" in
    000) printf '; nothing answered: is the docs.<hostname> record in place, and has Caddy its certificate?' ;;
    404) printf '; the API answers 404 until it has both AIA_ONLYOFFICE_URL and AIA_ONLYOFFICE_JWT_SECRET (SSM aia_onlyoffice_url, aia_onlyoffice_jwt_secret)' ;;
  esac
}

docs_checks() {
  local base="https://docs.${AIA_PUBLIC_HOSTNAME}" c path refused=1 session cookie health container
  if [ "${AIA_ONLYOFFICE_ENABLED:-false}" != "true" ]; then
    printf 'info  docs: the report editor is off (aia_onlyoffice_enabled)\n'
    # bin/deploy.sh stops it when the switch is off; one still running means that stop failed.
    [ -z "$(docs_container)" ] \
      || warn "docs: the report editor is off and its Document Server is stopped" "it still runs; bin/docs.sh down"
    return 0
  fi

  c="$(code -H 'Accept: text/html' "$base/" || true)"
  if [ "$c" = "401" ]; then pass "docs: a request without the docs cookie is refused by the docs gate (401)"
  else fail "docs: a request without the docs cookie is refused by the docs gate" "GET $base/ returned $c, expected 401$(docs_why "$c")"; fi

  # The server-to-server, AI proxy and info paths, with and without the version prefix the
  # Document Server's nginx strips and with the repeated slash it merges (tools/caddy_routes.py).
  for path in /healthcheck /coauthoring/CommandService.ashx /9.4.0-1/coauthoring/CommandService.ashx //info/info.json /AI-PROXY/x; do
    c="$(code "$base$path" || true)"
    [ "$c" = "404" ] || { refused=0; fail "docs: the Document Server's own paths are refused at Caddy" "GET $path returned $c, expected 404"; }
  done
  [ "$refused" = 1 ] && pass "docs: the Document Server's own paths are refused at Caddy (404)"

  # The one route without the gate: the Document Server's signed links to a saved document. One
  # with a forged signature must be refused by its own nginx (403). Anything served fails, and so
  # does the gate's 401 or a 404: the route is gone and no save can be fetched. With the Document
  # Server down there is nothing behind the route (000, 502-504): said, not failed.
  c="$(code "$base/cache/files/data/smoke/output.docx/output.docx?md5=AAAAAAAAAAAAAAAAAAAAAA&expires=4102444800" || true)"
  case "$c" in
    403) pass "docs: a cache link with a forged signature is refused by the Document Server (403)" ;;
    2*|3*) fail "docs: a cache link with a forged signature is refused by the Document Server" "it returned $c: the route without the gate serves unsigned links" ;;
    000|502|503|504) warn "docs: a cache link with a forged signature is refused by the Document Server" "it returned $c, expected 403; the Document Server may be down" ;;
    *) fail "docs: a cache link with a forged signature is refused by the Document Server" "it returned $c, expected 403: the cache links' route is missing or another route took them, and no save can be fetched" ;;
  esac

  session="$(curl -s -o /dev/null -D - --max-time 10 "$base/__aia/session" || true)"
  c="$(status_of "$session")"
  c="${c:-000}"
  cookie=""
  # Any cookie named for the docs pass, a prefixed one (__Host-) included.
  printf '%s' "$session" | grep -qiE '^set-cookie:[[:space:]]*[^=;]*aia_docs=' && cookie=" and set a docs cookie"
  if [ "$c" = "401" ] && [ -z "$cookie" ]; then pass "docs: /__aia/session without a ticket opens nothing (401, no cookie)"
  else fail "docs: /__aia/session without a ticket opens nothing" "it returned ${c}${cookie}, expected 401 and no cookie$(docs_why "$c")"; fi

  container="$(docs_container)"
  health="$( [ -n "$container" ] && docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || printf 'not running')"
  if [ "$health" = "healthy" ]; then pass "docs: the Document Server is healthy"
  else warn "docs: the Document Server is healthy" "it is ${health}; Zpráva stays read-only (bin/docs.sh status, bin/docs.sh logs)"; fi
}
