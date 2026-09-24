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
# Exit status: 0 only when every check passed. The AI check reports
# NOT_RUNNABLE while no Bedrock adapter and governed EU route are wired into
# the deployed revision; that is printed as such and never counted as a pass.

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

# --- web and the 18.6.6 interface (ADR 0012) --------------------------------
# `/` is the 18.6.6 interface behind AIA sign-in: anonymous, a browser is sent
# to /login and a data request is refused. Both answers come from the API's
# gate, so they also prove Caddy asks it before forwarding to the unit.
root_headers="$(curl -s -o /dev/null -D - --max-time 10 -H 'Accept: text/html' "$BASE/" || true)"
root_code="$(printf '%s' "$root_headers" | awk 'NR==1{print $2}')"
root_location="$(printf '%s' "$root_headers" | tr -d '\r' | awk 'tolower($1)=="location:"{print $2}')"
if [ "$root_code" = "302" ] && [ "$root_location" = "/login?next=%2F" ]; then
  pass "web: an anonymous visit to / is sent to sign-in (302 /login)"
else fail "web: an anonymous visit to / is sent to sign-in" "got ${root_code} Location '${root_location}'"; fi

# The interface document is reached only through the gated rewrite of `/`
# (ADR 0013); asked for directly, Caddy itself answers 404. Anything else means
# the running Caddy is not on the deployed Caddyfile -- how run 14 left the
# skin unseen with every other check green (OI-45).
direct_code="$(code "$BASE/interface-document")"
if [ "$direct_code" = "404" ]; then
  pass "caddy: running the deployed Caddyfile (/interface-document answers 404)"
else fail "caddy: running the deployed Caddyfile" "GET /interface-document returned ${direct_code}, expected 404; the running Caddy predates this Caddyfile (docker compose up -d --force-recreate caddy)"; fi

if [ "$(code "$BASE/login")" = "200" ] && curl -fsS --max-time 10 "$BASE/login" | grep -qi '<html'; then
  pass "web: the sign-in page renders"
else fail "web: the sign-in page renders" "GET $BASE/login did not return 200 HTML"; fi

panel_code="$(code "$BASE/api/bootstrap")"
if [ "$panel_code" = "401" ]; then pass "security: the 18.6.6 interface refuses an anonymous data request (401)"
else fail "security: the 18.6.6 interface refuses an anonymous data request" "GET /api/bootstrap returned ${panel_code}, expected 401"; fi

forged_code="$(code -X POST -H 'Origin: https://evil.example' -H "Cookie: aia_panel=forged" "$BASE/api/projects")"
if [ "$forged_code" = "403" ]; then pass "security: a cross-origin write to the 18.6.6 interface is refused (403)"
else fail "security: a cross-origin write to the 18.6.6 interface is refused" "POST /api/projects returned ${forged_code}, expected 403"; fi

web_sha="$(curl -fsS --max-time 10 "$BASE/version" | json 'd["sha"] or ""' || true)"
if [ "$web_sha" = "$SHA" ]; then pass "web: /version reports $SHA"
else fail "web: /version reports the deployed SHA" "got '${web_sha}'"; fi

redirect="$(code "http://${AIA_PUBLIC_HOSTNAME}/")"
case "$redirect" in 301|308) pass "web: HTTP redirects to HTTPS ($redirect)" ;;
  *) fail "web: HTTP redirects to HTTPS" "got $redirect" ;; esac

# --- legacy unit (ADR 0011, ADR 0012) ----------------------------------------
# Its health is checked here rather than by `compose up --wait`, so an unhealthy
# unit fails the deploy without keeping the product hostname down.
legacy_id="$("${COMPOSE[@]}" ps -q legacy-panel 2>/dev/null || true)"
legacy_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$legacy_id" 2>/dev/null || echo missing)"
if [ "$legacy_health" = "healthy" ]; then pass "legacy: the 18.6.6 unit is healthy"
else fail "legacy: the 18.6.6 unit is healthy" "state '${legacy_health}'; it needs AIA_LEGACY_DATA_PREFIX and its data bundle in the ops bucket (runbook § The 18.6.6 interface)"; fi

# The gate is the check: the reference API is unauthenticated, so an anonymous
# request to the legacy hostname must be refused by Caddy before it reaches it.
if [ -n "${AIA_LEGACY_HOSTNAME:-}" ]; then
  legacy_code="$(code "https://${AIA_LEGACY_HOSTNAME}/health")"
  if [ "$legacy_code" = "401" ]; then pass "legacy: hostname answers and the gate refuses anonymous access (401)"
  else fail "legacy: hostname answers and the gate refuses anonymous access" "GET /health returned ${legacy_code}, expected 401"; fi
fi

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
