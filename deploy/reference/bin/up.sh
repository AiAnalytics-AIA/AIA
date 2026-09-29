#!/usr/bin/env bash
# Start the 18.6.6 reference unit on the develop host (ADR 0018 decision 5).
#
#   bin/up.sh <git-sha>
#
#   check        the unit's working volume exists (never created here)
#   pull         aia-legacy-panel:<sha>, built by the Reference unit workflow or
#                by a develop deploy from before ADR 0018
#   sync         the licence-bound data bundle from the ops bucket, when
#                AIA_LEGACY_DATA_PREFIX is set; the unit refuses to start on a
#                partial or drifted bundle
#   start        the unit and its gate, and wait until the unit is healthy
#
# The product is not touched: no service of deploy/develop is started, stopped
# or recreated, and the product keeps answering whatever state this is in.

# shellcheck source=deploy/reference/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

SHA="${1:-}"
require_sha "$SHA"
require_env_file
require_state_volume
export AIA_REFERENCE_TAG="$SHA"

registry_login
log "pulling aia-legacy-panel:$SHA"
"${COMPOSE[@]}" pull --quiet

data_dir="${AIA_REFERENCE_DATA_DIR:-/opt/aia/develop/legacy-data}"
if [ -n "${AIA_LEGACY_DATA_PREFIX:-}" ]; then
  log "syncing the unit's data bundle from s3://$AIA_OPS_BUCKET/$AIA_LEGACY_DATA_PREFIX/"
  mkdir -p "$data_dir"
  aws s3 sync "s3://$AIA_OPS_BUCKET/$AIA_LEGACY_DATA_PREFIX/" "$data_dir" --only-show-errors --delete
else
  log "AIA_LEGACY_DATA_PREFIX is unset; using $data_dir as it is"
fi

log "starting the reference unit and its gate"
# The unit hydrates and verifies its data before it reports healthy (its
# healthcheck's start period is 120 s).
"${COMPOSE[@]}" up -d --wait --wait-timeout 300

log "the reference unit is up on 127.0.0.1:${AIA_REFERENCE_PORT:-8765} behind basic auth"
log "from elsewhere: an SSM port forward to that port (deploy/reference/README.md § Reaching it)"
