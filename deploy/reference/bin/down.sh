#!/usr/bin/env bash
# Stop the 18.6.6 reference unit and its gate.
#
#   bin/down.sh
#
# The containers go; the unit's working volume and its data directory stay, and
# nothing here removes either (no `--volumes`; the volume is external, so
# Compose would refuse to remove it anyway). The product is not touched.

# shellcheck source=deploy/reference/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_env_file
# `down` resolves the image name too, so any tag will do for stopping.
export AIA_REFERENCE_TAG="${AIA_REFERENCE_TAG:-stopped}"
log "stopping the reference unit and its gate"
"${COMPOSE[@]}" down
log "stopped; the unit's working volume $STATE_VOLUME is kept"
