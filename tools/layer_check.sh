#!/usr/bin/env bash
#
# Lightweight layering enforcement for AIA.
#
# One rule here per rule stated in ARCHITECTURE.md. Deliberately grep-level: no
# AST, no dependency-graph tool, nothing to install. A checker that needs its own
# toolchain gets disabled the first time that toolchain breaks, and then the
# layering rots silently -- which is the failure this file exists to prevent.
#
# Exit 0 = every rule passes. Run it before every commit; CI runs it blocking.
#
# Adding a rule: state it in ARCHITECTURE.md first, then add one `forbid` line
# here. Rules are a ratchet -- each one is added only once it already passes, so
# this script is green from the day it lands and a red run always means a
# regression rather than a backlog.
#
# Exemptions are named, never silent. Every `--exclude` below carries a comment
# saying why the file is allowed the thing the rule forbids. Pretending an
# exception does not exist is what kills these scripts.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

FAILED=0
PASSED=0

# forbid <rule-name> <pattern> <path> [excluded-basename ...]
forbid() {
  local rule="$1" pattern="$2" path="$3"; shift 3
  local excludes=()
  while [ $# -gt 0 ]; do excludes+=(--exclude="$1"); shift; done

  if [ ! -e "$path" ]; then
    printf 'skip  %s\n      (path %s does not exist yet)\n' "$rule" "$path"
    return 0
  fi

  local hits
  hits=$(grep -rn "${excludes[@]}" \
           --exclude-dir=node_modules --exclude-dir=.next \
           --exclude-dir=__pycache__ --exclude-dir=.venv \
           -E "$pattern" "$path" 2>/dev/null || true)

  if [ -n "$hits" ]; then
    printf 'FAIL  %s\n' "$rule"
    printf '%s\n' "$hits" | sed 's/^/      /'
    FAILED=1
  else
    printf 'ok    %s\n' "$rule"
    PASSED=$((PASSED + 1))
  fi
}

CORE=packages/aia_core/src/aia_core
API=apps/api/src/aia_api

echo "Layer rules (ARCHITECTURE.md §3)"
echo

# --- Layer 1: the domain is pure -------------------------------------------
#
# The domain layer is importable with nothing installed but Pydantic. That is
# what makes its tests total and instant, and it is the property that decays
# first if it is not checked: one convenient `from sqlalchemy import ...` and
# the rules can no longer be tested without a database.

forbid "domain imports no framework, driver or SDK" \
  '^\s*(from|import)\s+(sqlalchemy|fastapi|starlette|boto3|botocore|httpx|requests|redis|alembic|psycopg)\b' \
  "$CORE/domain/"

forbid "domain does not import outward (application, infrastructure)" \
  '^\s*from\s+(\.\.|aia_core\.)(application|infrastructure)\b' \
  "$CORE/domain/"

# --- Layer 2: application orchestrates, it does not serve HTTP --------------

forbid "application layer knows nothing about HTTP" \
  '^\s*(from|import)\s+(fastapi|starlette)\b' \
  "$CORE/application/"

# --- Layer 3: infrastructure is driven, never driving -----------------------

forbid "infrastructure knows nothing about HTTP" \
  '^\s*(from|import)\s+(fastapi|starlette)\b' \
  "$CORE/infrastructure/"

# The AWS SDK is an optional dependency imported lazily inside S3ArtifactStore,
# so that nothing else in the codebase loads an AWS SDK and the package installs
# without one. A second import site would silently make boto3 mandatory.
forbid "AWS SDK stays behind the storage adapter" \
  '^\s*(from|import)\s+(boto3|botocore)\b' \
  "$CORE" \
  storage.py

# --- Layer 6: transport validates, delegates, serialises --------------------
#
# A route handler that opens a Session is a route handler that can make a
# decision the domain never saw. dependencies.py and main.py are the composition
# root -- they are where the engine, the session factory and the readiness probe
# legitimately live -- and are exempt by name.
forbid "no database access in the HTTP layer" \
  '^\s*(from|import)\s+sqlalchemy\b' \
  "$API" \
  dependencies.py main.py

# Tables are the infrastructure's private shape. The API talks to repositories,
# which return domain objects; reaching for a table means a query is about to be
# written in a place where it cannot be tested without the whole stack.
forbid "no ORM tables in the HTTP layer" \
  '(from|import)\s+.*infrastructure\.tables\b' \
  "$API"

# --- Authorization: scope is issued, never constructed ----------------------
#
# ScopeResolver is the only issuer of a scope context, via a module-private
# sentinel. If any other module can build one, then a request body, a tool
# payload or a model-generated argument can widen its own scope -- which is the
# whole isolation boundary gone. See docs/architecture/scope-and-authorization.md.
forbid "scope contexts are issued only by ScopeResolver" \
  '^[^#]*\b(Organization|Client|Study)Context\(' \
  "$CORE" \
  scope.py

forbid "the API never builds its own scope context" \
  '^[^#]*\b(Organization|Client|Study)Context\(' \
  "$API"

# --- Population: one resolver, one loader ----------------------------------
#
# The reference answered "which population is in use" in four places and loaded
# it through two loaders that returned different populations from the same bytes
# (AIA-reference R4, fixture F10). A RuntimePopulation is issued only by
# PopulationRuntime in application/population.py, through a module-private
# sentinel; runtime.py defines it. Parsing a panel anywhere else is the first step
# of a second loader, so that is refused too; population_parser.py is the parser.
forbid "runtime populations are issued only by the canonical loader" \
  '^[^#]*RuntimePopulation\._issue\(' \
  "$CORE" \
  population.py runtime.py

forbid "the API never issues a runtime population" \
  '^[^#]*RuntimePopulation\._issue\(' \
  "$API"

forbid "population panels are parsed only by the canonical loader" \
  '^[^#]*\bparse_panel\(' \
  "$CORE" \
  population.py population_parser.py

forbid "the API never parses a population panel" \
  '^[^#]*\bparse_panel\(' \
  "$API"

# Establishing and promoting a population is platform administration. The
# operator grant is issued only by PopulationAuthority from trusted configuration
# (application/population_authority.py); authority.py defines it. Neither a study
# nor an organization context implies it, and the API never mints one.
forbid "population-operator grants are issued only by the population authority" \
  '^[^#]*PopulationOperatorGrant\._issue\(' \
  "$CORE" \
  population_authority.py authority.py

forbid "the API never issues a population-operator grant" \
  '^[^#]*PopulationOperatorGrant\._issue\(' \
  "$API"

# --- Tests: the signal is never deleted ------------------------------------
#
# A failing test is a finding (ARCHITECTURE.md §7). Runtime `pytest.skip(...)`
# is allowed and used deliberately -- a missing PostgreSQL or a missing legacy
# reference checkout is a real environment fact. A *static* skip or xfail is
# different: it removes the signal permanently and silently.
forbid "no statically skipped or xfailed tests" \
  '@pytest\.mark\.(skip|xfail)' \
  packages/aia_core/tests
forbid "no statically skipped or xfailed API tests" \
  '@pytest\.mark\.(skip|xfail)' \
  apps/api/tests

# --- Presentation: the client renders, it does not decide -------------------
#
# GET /projects/{id}/impact exists precisely so the browser never reasons about
# which stages an edit invalidates. A database client in the web app would mean
# that boundary has been crossed in the most expensive possible way.
forbid "the web client does not talk to a database" \
  '^\s*(import|export).*(from\s+)?['\''"](pg|better-sqlite3|@prisma/client|mysql2|mongodb)['\''"]' \
  apps/web/src

echo
if [ "$FAILED" -ne 0 ]; then
  echo "layer_check: FAILED -- see the rules above and ARCHITECTURE.md §3."
  exit 1
fi
echo "layer_check: $PASSED rules pass."
