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

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

FAILED=0
PASSED=0

MANIFEST=docs/migration/reference-manifest.json

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

# --- 2a. No raw reference assets by shape ----------------------------------
#
# The archive is 52.6 MB, the population panels ~22 MB. Neither may be committed
# here, and neither may arrive by a different extension.

ASSET_HITS=$(git ls-files \
  | grep -Ei '\.(zip|7z|rar|sqlite|sqlite3|db|parquet)$|\.csv\.gz$|(^|/)npc[-_]panel' \
  || true)
if [ -n "$ASSET_HITS" ]; then
  fail "no raw reference assets by file shape" "$ASSET_HITS"
else
  pass "no raw reference assets by file shape"
fi

# --- 2b. No reference file, under ANY name ---------------------------------
#
# The shape rule above only catches assets that arrive as archives or databases.
# Much of the reference is plain .csv and .json -- LIVE_POPULATION_TARGETS_18_5.csv,
# CALIBRATION_REGISTRY.csv, DONOR_BLOCK_REGISTRY.json -- which no extension rule
# can distinguish from a legitimate config file.
#
# So this rule does not guess from names at all. The manifest records the SHA256
# of all 1,324 canonical reference files; a tracked file whose content hashes to
# one of them IS that reference file, whatever it has been renamed to. Exact, no
# false positives by construction, and it needs no maintenance: the hash set
# comes from the manifest, so it widens automatically when the manifest does.
#
# Name matching was considered and rejected. `README.md` and `pyproject.toml`
# exist in both trees, so matching by path would flag this repository's own
# files; matching by content cannot.

if [ -f "$MANIFEST" ]; then
  grep -oE '"[0-9a-f]{64}"' "$MANIFEST" | tr -d '"' | sort -u > "$WORK/ref-hashes"

  REFERENCE_CONTENT=$(git ls-files | grep -Fxv "$MANIFEST" | while read -r f; do
      [ -f "$f" ] || continue
      h=$(sha256sum "$f" 2>/dev/null | cut -d' ' -f1)
      [ -n "$h" ] && grep -qxF "$h" "$WORK/ref-hashes" && echo "$f ($h)"
    done || true)

  if [ -n "$REFERENCE_CONTENT" ]; then
    fail "no file whose contents are a reference file" "$REFERENCE_CONTENT"
  else
    pass "no file whose contents are a reference file"
  fi
else
  printf 'skip  no file whose contents are a reference file\n      (%s absent)\n' "$MANIFEST"
fi

# --- 2c. No uncompressed reference datasets by naming convention -----------
#
# Defence in depth behind 2b, which only catches a byte-identical copy. A
# reference dataset that has been filtered, re-exported or had a column dropped
# hashes differently and would pass, so its naming convention is caught too.
# Deliberately narrow: it requires a reference-data noun, so `package.json` and
# `tsconfig.json` are unaffected.

DATASET_HITS=$(git ls-files \
  | grep -Ei '\.(csv|tsv|json)$' \
  | grep -Ei '(population|panel|calibration|donor|respondent|segment|registry|targets|weights|census|piaac|issp)' \
  | grep -Ev "^($MANIFEST)$" \
  || true)
if [ -n "$DATASET_HITS" ]; then
  fail "no uncompressed reference datasets" "$DATASET_HITS"
else
  pass "no uncompressed reference datasets"
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
# The snapshot's own identity. The reference tag, its version string and the
# archive filename all contain a client token, and every document that points at
# the authoritative reference has to name them -- that is the pointer working, not
# a disclosure.
#
# These are exempted as LITERALS rather than by exempting the files that carry
# them. A per-file exemption is coarse: it would excuse every token in that file,
# and the allowlist would grow by one entry each time another document cited the
# tag, which is how an allowlist becomes the rule. Matching the literal keeps the
# exemption to exactly the string that is safe, in any file.
SNAPSHOT_IDENTITY='reference-18\.6\.6-gemo-2026-09-11-v1|18\.6\.6 \+ GEMO patch 2026-09-11|NPC_PANEL_18\.6\.6_CURRENT_DEMOS_UPDATED_GEMO_REPUTACNI_SCENARE_2026-09-11_FULL'

# Named file exceptions, each with a reason -- a silent exception is how a guard
# stops meaning anything. Only three remain, because the literal exemption above
# now covers every document that merely cites the snapshot:
#   reference-manifest.json        carries the reference path set; being reduced, see §3
#   public-exposure-remediation.md enumerates the tokens, which is its subject
#   tools/exposure_check.sh        holds the token list itself
ALLOWED_PATHS='^(docs/migration/public-exposure-remediation\.md|docs/migration/reference-manifest\.json|tools/exposure_check\.sh)$'

# Case-insensitive throughout. `gemo-notes.txt` discloses exactly what
# `GEMO-notes.txt` does, and a control that a change of capitalisation defeats is
# not a control.
NAME_HITS=$(git ls-files | grep -Ei "$CLIENT_TOKENS" | grep -Ev "$ALLOWED_PATHS" || true)
if [ -n "$NAME_HITS" ]; then
  fail "no client-identifying legacy filenames" "$NAME_HITS"
else
  pass "no client-identifying legacy filenames"
fi

# Content, not just names. A ledger that lists the engagements is the same
# disclosure as a file named after one.
#
# Test trees are scanned like everything else. An earlier revision exempted
# them, which was wrong twice over: parity and characterization fixtures are the
# single most plausible route for legacy material to enter this repository, and
# the exemption bought nothing -- no test file carries one of these tokens, so it
# was attack surface protecting nothing. Exceptions are per file in
# ALLOWED_PATHS, never per directory.
CONTENT_HITS=$(git ls-files \
  | grep -Ev "$ALLOWED_PATHS" \
  | while read -r f; do
      [ -f "$f" ] || continue
      # A line that carries a token ONLY as part of the snapshot identity is the
      # pointer, not a disclosure. Anything else on that line still counts.
      if grep -iE "$CLIENT_TOKENS" "$f" 2>/dev/null \
           | grep -qivE "$SNAPSHOT_IDENTITY"; then echo "$f"; fi
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
