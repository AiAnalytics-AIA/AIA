#!/usr/bin/env bash
#
# Public-exposure guard for AiAnalytics-AIA/AIA.
#
# The legacy reference is client work: its filenames alone name real companies and
# engagements, and a filename is disclosure even when the file it names is absent.
# AiAnalytics-AIA/AIA-reference is private and authoritative for anything detailed.
#
# This repository is being made PRIVATE (decision D5, 2026-09-22). That does not
# retire this guard, for two reasons. Private is a setting somebody can change
# back, and a guard that was removed when it looked unnecessary is not there when
# it becomes necessary again. And private is not need-to-know: every collaborator,
# every CI log and every future fork still sees whatever is committed, so detailed
# reference material still does not belong here.
#
# This script fails the build when reference material that belongs in the private
# repository appears here. Grep-level on purpose, matching tools/layer_check.sh:
# a checker that needs its own toolchain gets disabled the first time that
# toolchain breaks, and then the guard rots exactly when it is load-bearing.
#
# It checks the WORKING TREE, which is what a PR adds. It does not and cannot
# scrub history -- see docs/migration/public-exposure-remediation.md.
#
# Exit 0 = clean. Run it before every commit; CI runs it blocking.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

FAILED=0
PASSED=0

fail() {
  printf 'FAIL  %s\n' "$1"
  shift
  printf '%s\n' "$@" | sed 's/^/      /'
  FAILED=1
}

pass() {
  printf 'ok    %s\n' "$1"
  PASSED=$((PASSED + 1))
}

echo "Public-exposure rules (docs/migration/public-exposure-remediation.md)"
echo

# --- 1. No detailed reference inventories ----------------------------------
#
# A per-file inventory of the reference is a map of client engagements. The
# summary manifest that CI needs is explicitly allowed by name below; anything
# broader belongs in the private repository.

INVENTORY_HITS=$(git ls-files \
  | grep -Ei '(reference[-_]file[-_]inventory|reference[-_]rebuild[-_]package/|reference[-_]snapshot)' \
  || true)
if [ -n "$INVENTORY_HITS" ]; then
  fail "no detailed reference inventories in the public repo" "$INVENTORY_HITS"
else
  pass "no detailed reference inventories in the public repo"
fi

# --- 2. No raw reference assets --------------------------------------------
#
# The archive is 52.6 MB, the population panels ~22 MB. Neither may be committed
# here, and neither may arrive by a different extension.

ASSET_HITS=$(git ls-files \
  | grep -Ei '\.(zip|7z|rar|sqlite|sqlite3|db|parquet)$|\.csv\.gz$|(^|/)npc[-_]panel' \
  || true)
if [ -n "$ASSET_HITS" ]; then
  fail "no raw reference assets in the public repo" "$ASSET_HITS"
else
  pass "no raw reference assets in the public repo"
fi

# --- 3. No client-identifying legacy filenames -----------------------------
#
# Tokens taken from the reference inventory. This list is maintained by the data
# owner -- it is a statement about which names identify real clients, which is
# not a judgement a build script can make. ALLOWED_PATHS carries the exceptions
# by name, because a silent exception is how a guard stops meaning anything.
#
# The reference tag and archive filename legitimately contain one of these
# tokens: they are the snapshot's identity and are recorded in the manifest and
# in reference-source.md.

CLIENT_TOKENS='GEMO|MMC_GEMO|STREAMIO|AURORA|NEXORA|RAILMOVE'
# Named exceptions, each with a reason -- a silent exception is how a guard stops
# meaning anything:
#   reference-source.md            records the snapshot identity: tag and archive name
#   public-exposure-remediation.md enumerates the tokens, which is its subject
#   reference-manifest.json        carries the reference path set; being reduced, see §3
#   .planning/PROGRESS.md          cites the reference tag as the authoritative pointer
#   tools/exposure_check.sh        holds the token list itself
ALLOWED_PATHS='^(docs/migration/(reference-source|public-exposure-remediation)\.md|docs/migration/reference-manifest\.json|\.planning/PROGRESS\.md|tools/exposure_check\.sh)$'

NAME_HITS=$(git ls-files | grep -E "$CLIENT_TOKENS" | grep -Ev "$ALLOWED_PATHS" || true)
if [ -n "$NAME_HITS" ]; then
  fail "no client-identifying legacy filenames" "$NAME_HITS"
else
  pass "no client-identifying legacy filenames"
fi

# Content, not just names. A ledger that lists the engagements is the same
# disclosure as a file named after one.
CONTENT_HITS=$(git ls-files \
  | grep -Ev "$ALLOWED_PATHS" \
  | grep -Ev '^(packages|apps)/.*/tests?/' \
  | while read -r f; do
      [ -f "$f" ] || continue
      if grep -qE "$CLIENT_TOKENS" "$f" 2>/dev/null; then echo "$f"; fi
    done || true)
if [ -n "$CONTENT_HITS" ]; then
  fail "no client-identifying legacy names in file contents" "$CONTENT_HITS"
else
  pass "no client-identifying legacy names in file contents"
fi

# --- 4. No agent coordination state in product history ---------------------
#
# .agent-status is a disposable bus between concurrent agents, and its own
# README says the branch carrying it is never merged. It reached main anyway,
# which is the case this rule exists to stop repeating.

STATUS_HITS=$(git ls-files | grep -E '^\.agent-status/' || true)
if [ -n "$STATUS_HITS" ]; then
  fail ".agent-status must not be in product history" "$STATUS_HITS"
else
  pass ".agent-status must not be in product history"
fi

echo
if [ "$FAILED" -ne 0 ]; then
  echo "exposure_check: FAILED."
  echo "Detailed reference material belongs in AiAnalytics-AIA/AIA-reference,"
  echo "which is private and authoritative -- regardless of this repo's visibility."
  exit 1
fi
echo "exposure_check: $PASSED rules pass."
