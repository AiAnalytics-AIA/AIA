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
# NOT_RUNNABLE while no ModelGateway exists on the deployed revision; that is
# printed as such and is never counted as a pass.

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

# --- web ---------------------------------------------------------------------
if [ "$(code "$BASE/")" = "200" ] && curl -fsS --max-time 10 "$BASE/" | grep -qi '<html'; then
  pass "web: HTTPS loads and the page renders"
else fail "web: HTTPS loads and the page renders" "GET $BASE/ did not return 200 HTML"; fi

web_sha="$(curl -fsS --max-time 10 "$BASE/version" | json 'd["sha"] or ""' || true)"
if [ "$web_sha" = "$SHA" ]; then pass "web: /version reports $SHA"
else fail "web: /version reports the deployed SHA" "got '${web_sha}'"; fi

redirect="$(code "http://${AIA_PUBLIC_HOSTNAME}/")"
case "$redirect" in 301|308) pass "web: HTTP redirects to HTTPS ($redirect)" ;;
  *) fail "web: HTTP redirects to HTTPS" "got $redirect" ;; esac

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
if [ -n "$("${COMPOSE[@]}" port postgres 5432 2>/dev/null)" ]; then
  fail "security: the postgres service publishes no port" "$("${COMPOSE[@]}" port postgres 5432)"
else pass "security: the postgres service publishes no port"; fi

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
