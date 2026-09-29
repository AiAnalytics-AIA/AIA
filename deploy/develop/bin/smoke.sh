#!/usr/bin/env bash
# Prove a deployment, from outside and from the host.
#
#   bin/smoke.sh <expected-git-sha>
#
# A deployment is not successful because containers started. Each check below
# is one line of the brief's list, and a failure names the line. Checks that
# need a real browser session (Cognito login) are not here; they are in the
# runbook as a manual acceptance step, because a smoke test holding a user's
# Google credentials would be worse than the gap it closes.
#
# Exit status: 0 only when every check passed. The AI check always reports
# NOT_RUNNABLE: the smoke makes no paid model call, and the AI runtime -- off by
# default -- is checked by its own acceptance (ADR 0010), not on each deploy.
# It is printed as such and never counted as a pass.

# shellcheck source=deploy/develop/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

SHA="${1:-}"
require_sha "$SHA"
require_env_file
cd "$DEPLOY_DIR" || exit 1

BASE="https://${AIA_PUBLIC_HOSTNAME}"
FAILED=0
pass() { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n      %s\n' "$1" "${2:-}"; FAILED=1; }
json() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@"; }

echo "Smoke: $BASE expecting build $SHA"
echo

# --- web: AIA is the product; 18.6.6 is not part of it (ADR 0015, ADR 0018) --
headers() { curl -s -o /dev/null -D - --max-time 10 -H 'Accept: text/html' "$1" || true; }
status_of() { printf '%s' "$1" | awk 'NR==1{print $2}'; }
location_of() { printf '%s' "$1" | tr -d '\r' | awk 'tolower($1)=="location:"{print $2}'; }

# `/` is the front door of AIA: Caddy itself answers 302 /app/clients, so the
# NPC Panel 18.6.6 document is never what the product hostname opens.
root_headers="$(headers "$BASE/")"
root_code="$(status_of "$root_headers")"; root_location="$(location_of "$root_headers")"
if [ "$root_code" = "302" ] && [ "$root_location" = "/app/clients" ]; then
  pass "web: / opens AIA (302 /app/clients), not the 18.6.6 document"
else fail "web: / opens AIA (302 /app/clients)" "got ${root_code} Location '${root_location}'"; fi

# AIA is behind its own gate (ADR 0018): anonymous, a browser is sent to sign-in
# and comes back to /app/clients. A 200 would mean the screens are public; a 404
# from Caddy, that the running Caddy predates the @app route.
app_headers="$(headers "$BASE/app/clients")"
app_code="$(status_of "$app_headers")"; app_location="$(location_of "$app_headers")"
if [ "$app_code" = "302" ] && [ "$app_location" = "/login?next=%2Fapp%2Fclients" ]; then
  pass "web: an anonymous visit to /app/clients is sent to sign-in (302 /login)"
else fail "web: an anonymous visit to /app/clients is sent to sign-in" "got ${app_code} Location '${app_location}'"; fi

# A cookie that is not AIA's session -- the retired 18.6.6 panel's among them --
# is not a way into AIA.
panel_cookie_headers="$(curl -s -o /dev/null -D - --max-time 10 -H 'Accept: text/html' -H 'Cookie: aia_panel=forged' "$BASE/app/clients" || true)"
if [ "$(status_of "$panel_cookie_headers")" = "302" ]; then
  pass "security: a cookie that is not AIA's session does not open AIA (302 /login)"
else fail "security: a cookie that is not AIA's session does not open AIA" "got $(status_of "$panel_cookie_headers")"; fi

# AIA's pages take no writes; the API is /api/v1.
page_write="$(code -X POST -H 'Accept: text/html' "$BASE/app/clients")"
if [ "$page_write" = "403" ]; then pass "security: a write to AIA's pages is refused (403)"
else fail "security: a write to AIA's pages is refused" "POST /app/clients returned ${page_write}, expected 403"; fi

# The 18.6.6 interface is not served: /classic is AIA's own page saying so, to
# anyone, without sign-in. It doubles as the check that the running Caddy is on
# the deployed Caddyfile -- the one before this answered 302 /login there (OI-45).
classic_body="$(curl -s --max-time 10 -H 'Accept: text/html' -w '\n%{http_code}' "$BASE/classic" || true)"
classic_code="$(printf '%s' "$classic_body" | tail -n1)"
if [ "$classic_code" = "200" ] && printf '%s' "$classic_body" | grep -q "už není součástí AIA"; then
  pass "caddy: running the deployed Caddyfile (/classic is AIA's page: 18.6.6 is not served)"
else fail "caddy: running the deployed Caddyfile" "GET /classic returned ${classic_code} without AIA's page; the running Caddy predates this Caddyfile (docker compose up -d --force-recreate caddy)"; fi

# An unknown path is the web client's own 404.
stray_code="$(code -H 'Accept: text/html' "$BASE/no-such-page")"
if [ "$stray_code" = "404" ]; then pass "web: an unknown path is AIA's 404"
else fail "web: an unknown path is AIA's 404" "GET /no-such-page returned ${stray_code}, expected 404"; fi

# Nothing of the 18.6.6 unit is served (ADR 0018 decision 5): the paths it
# answered on this hostname are the web client's 404 like any other unknown
# path -- not a gate's 401 or 403, not a 502 from a proxy with nobody behind it.
unit_paths_ok=1
for path in /api/bootstrap /files/x /health /status; do
  c="$(code -H 'Accept: application/json' "$BASE$path")"
  [ "$c" = "404" ] || { unit_paths_ok=0; fail "web: the 18.6.6 unit's paths are AIA's 404" "GET $path returned $c, expected 404"; }
done
write_code="$(code -X POST -H 'Content-Type: application/json' -d '{}' "$BASE/api/projects")"
[ "$write_code" = "404" ] || { unit_paths_ok=0; fail "web: the 18.6.6 unit's paths are AIA's 404" "POST /api/projects returned $write_code, expected 404"; }
[ "$unit_paths_ok" = 1 ] && pass "web: the 18.6.6 unit's paths are AIA's 404 (/api/bootstrap, /files/*, /health, /status, POST /api/projects)"

# The 18.6.6 document is gone from the web client too.
direct_code="$(code "$BASE/interface-document")"
if [ "$direct_code" = "404" ]; then pass "web: the 18.6.6 document is not served (/interface-document 404)"
else fail "web: the 18.6.6 document is not served" "GET /interface-document returned ${direct_code}, expected 404"; fi

if [ "$(code "$BASE/login")" = "200" ] && curl -fsS --max-time 10 "$BASE/login" | grep -qi '<html'; then
  pass "web: the sign-in page renders"
else fail "web: the sign-in page renders" "GET $BASE/login did not return 200 HTML"; fi

web_sha="$(curl -fsS --max-time 10 "$BASE/version" | json 'd["sha"] or ""' || true)"
if [ "$web_sha" = "$SHA" ]; then pass "web: /version reports $SHA"
else fail "web: /version reports the deployed SHA" "got '${web_sha}'"; fi

redirect="$(code "http://${AIA_PUBLIC_HOSTNAME}/")"
case "$redirect" in 301|308) pass "web: HTTP redirects to HTTPS ($redirect)" ;;
  *) fail "web: HTTP redirects to HTTPS" "got $redirect" ;; esac

# --- host: the product stack runs nothing of 18.6.6 (ADR 0018) --------------
product_unit="$(product_unit_containers)"
if [ -z "$product_unit" ]; then pass "host: the product stack runs no 18.6.6 unit"
else fail "host: the product stack runs no 18.6.6 unit" "container(s) $product_unit of service legacy-panel in project aia-develop"; fi
# Its working volume is kept for the reference and the migration (OI-58), and
# nothing the product runs may remove it. Absent on a host that never ran it.
if unit_volume_exists; then
  pass "host: the 18.6.6 unit's working volume $LEGACY_STATE_VOLUME is kept"
else printf 'info  host: no 18.6.6 working volume on this host (%s)\n' "$LEGACY_STATE_VOLUME"; fi

# --- api ---------------------------------------------------------------------
health="$(curl -fsS --max-time 10 "$BASE/api/v1/health" || true)"
if [ "$(printf '%s' "$health" | json 'd["status"]' 2>/dev/null)" = "ok" ]; then pass "api: /health is ok"
else fail "api: /health is ok" "$health"; fi
api_sha="$(printf '%s' "$health" | json 'd["build"]["sha"] or ""' 2>/dev/null || true)"
if [ "$api_sha" = "$SHA" ]; then pass "api: /health reports build $SHA"
else fail "api: /health reports the deployed SHA" "got '${api_sha}'"; fi
if [ "$(printf '%s' "$health" | json 'd["env"]' 2>/dev/null)" = "staging" ]; then pass "api: runs with AIA_ENV=staging (deployed-environment guards active)"
else fail "api: runs with AIA_ENV=staging" "$health"; fi

ready="$(curl -sS --max-time 10 "$BASE/api/v1/ready" || true)"
if [ "$(printf '%s' "$ready" | json 'd["checks"]["database"]' 2>/dev/null)" = "ok" ]; then pass "api: /ready confirms PostgreSQL"
else fail "api: /ready confirms PostgreSQL" "$ready"; fi

# --- security ----------------------------------------------------------------
expect_401() {  # <label> <curl args...>
  local label="$1"; shift
  local c; c="$(code "$@")"
  if [ "$c" = "401" ]; then pass "security: $label (401)"; else fail "security: $label" "got $c"; fi
}
expect_401 "protected endpoint refuses an unauthenticated request" "$BASE/api/v1/studies"
expect_401 "the development header identity is not active" -H 'X-AIA-Subject: smoke@example.invalid' "$BASE/api/v1/studies"
expect_401 "a forged bearer token is refused" -H 'Authorization: Bearer not-a-token' "$BASE/api/v1/studies"

if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE '(^|:)5432$'; then
  fail "security: PostgreSQL is not listening on the host" "something listens on :5432"
else pass "security: PostgreSQL is not listening on the host"; fi
# Compose v2 may report an unpublished container port as ":0". Inspect the
# actual Docker host bindings instead, and fail closed if inspection fails.
postgres_id="$("${COMPOSE[@]}" ps -q postgres 2>/dev/null)"
port_bindings="$(docker inspect --format '{{json .HostConfig.PortBindings}}' "$postgres_id" 2>/dev/null || echo inspect-failed)"
case "$port_bindings" in
  '{}'|'null') pass "security: the postgres service publishes no port" ;;
  *) fail "security: the postgres service publishes no port" "Docker host bindings: $port_bindings" ;;
esac

# --- database ----------------------------------------------------------------
current="$("${COMPOSE[@]}" run --rm --no-deps -T api alembic current 2>/dev/null | tail -1 || true)"
if printf '%s' "$current" | grep -q '(head)'; then pass "database: schema is at alembic head ($current)"
else fail "database: schema is at alembic head" "alembic current: '${current}'"; fi

# --- worker ------------------------------------------------------------------
if [ "$("${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -c '^worker$')" = "1" ]; then
  pass "worker: container is running"
else fail "worker: container is running" "$("${COMPOSE[@]}" ps worker 2>&1 | tail -1)"; fi
if "${COMPOSE[@]}" logs --no-log-prefix worker 2>/dev/null | grep '"worker started"' | tail -1 | grep -q "\"build_sha\": \"$SHA\""; then
  pass "worker: started at build $SHA"
else fail "worker: started at build $SHA" "no 'worker started' line with build_sha $SHA in the worker log"; fi

# --- storage, worker execution, vertical slice -------------------------------
# One command inside the worker image: S3 round trip through ArtifactStore, then
# a real develop_snapshot run created as the seeded operator, executed by the
# running worker, its artifact read back from S3 and hash-verified. It prints
# its own ok/FAIL lines in this format and exits non-zero on any failure.
if "${COMPOSE[@]}" run --rm --no-deps -T -e AIA_SEED_OWNER_EMAIL worker python -m aia_executors.smoke --expect-build "$SHA"; then
  pass "storage + worker + slice: aia_executors.smoke passed"
else fail "storage + worker + slice: aia_executors.smoke" "see the lines above"; fi

echo
if [ "$FAILED" -ne 0 ]; then echo "smoke: FAILED"; exit 1; fi
echo "smoke: all checks passed for $SHA"
