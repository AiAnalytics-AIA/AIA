#!/usr/bin/env bash
# Put 18.6.6's v17 population where the worker reads it (population-operations P6).
#
#   bin/sync-population.sh
#
# By hand, by the data owner, before the population is imported (README § The
# population). Every file population/v17.files lists is fetched into a staging
# directory beside the target -- "bucket" files from AIA_POPULATION_SOURCE_PREFIX in
# the EU ops bucket (today the unit's data bundle, legacy-data/86b70bfb5c1b), "unit"
# files from this deploy bundle -- and its size and SHA256 are checked against the
# list. Only when every file matches is the staging directory swapped in for
# AIA_POPULATION_DIR/v17, read-only; one mismatch or missing object leaves whatever
# was there untouched.
#
# This is AIA's population, not the 18.6.6 unit: nothing of the unit is started or
# read from its settings (ADR 0018 decision 5), and the bucket is read, never
# written. Only the panels, the field dictionary and the companions are copied, not
# the rest of the bundle. The worker mounts the directory read-only; the import
# judges every byte again.
#
# Idempotent: a second run fetches, verifies and swaps in the same bytes.

# shellcheck source=deploy/develop/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_env_file
: "${AIA_POPULATION_SOURCE_PREFIX:?AIA_POPULATION_SOURCE_PREFIX names where the files are in the ops bucket (README § The population)}"

LIST="$DEPLOY_DIR/population/v17.files"
ROOT="${AIA_POPULATION_DIR:-/opt/aia/population}"
TARGET="$ROOT/v17"
[ -f "$LIST" ] || die "$LIST is missing; deploy a SHA whose bundle carries population/"

mkdir -p "$ROOT"
stage="$(mktemp -d "$ROOT/.v17.XXXXXX")"
old=""
# The verified directory is read-only (0555); make it writable again to remove it.
discard() { [ -e "$1" ] && { chmod -R u+w "$1"; rm -rf "$1"; } || true; }
cleanup() { discard "$stage"; [ -z "$old" ] || discard "$old"; }
trap cleanup EXIT

count=0
while read -r sha bytes origin path; do
  case "$sha" in '' | '#'*) continue ;; esac
  [[ "$sha" =~ ^[0-9a-f]{64}$ && "$bytes" =~ ^[0-9]+$ ]] || die "$LIST: a malformed line for '$path'"
  [[ "$path" =~ ^[A-Za-z0-9_.][A-Za-z0-9_./-]*$ && "$path" != *..* ]] || die "$LIST: '$path' is not a plain relative path"
  name="${path##*/}"
  [ ! -e "$stage/$name" ] || die "$LIST: two files are named $name"
  case "$origin" in
    bucket)
      aws s3 cp "s3://$AIA_OPS_BUCKET/$AIA_POPULATION_SOURCE_PREFIX/$path" "$stage/$name" \
        --only-show-errors --region "$AWS_REGION" || die "could not fetch $path from s3://$AIA_OPS_BUCKET/$AIA_POPULATION_SOURCE_PREFIX/"
      ;;
    unit)
      [[ "$path" != */* ]] || die "$LIST: a unit file is named by its base name, not '$path'"
      cp "$DEPLOY_DIR/population/$path" "$stage/$name" || die "$path is not in this deploy bundle"
      ;;
    *) die "$LIST: '$origin' is neither bucket nor unit" ;;
  esac
  actual_bytes="$(wc -c < "$stage/$name" | tr -d ' ')"
  [ "$actual_bytes" = "$bytes" ] || die "$name is $actual_bytes bytes, not $bytes; nothing was replaced"
  actual_sha="$(sha256sum "$stage/$name" | cut -d' ' -f1)"
  [ "$actual_sha" = "$sha" ] || die "$name does not have the listed SHA256; nothing was replaced"
  count=$((count + 1))
done < "$LIST"
[ "$count" -gt 0 ] || die "$LIST lists no files"

chmod 0444 "$stage"/*
chmod 0555 "$stage"
if [ -e "$TARGET" ]; then
  old="$ROOT/.v17.previous.$$"
  mv -T "$TARGET" "$old"
fi
mv -T "$stage" "$TARGET"
log "the population's $count files are in $TARGET, each matching population/v17.files"
