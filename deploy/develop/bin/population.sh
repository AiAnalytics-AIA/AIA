#!/usr/bin/env bash
# Run the population's operator command in the deployed worker image.
#
#   bin/population.sh status
#   bin/population.sh import --as <email> --label v17_4_0 --panel ... (README § The population)
#
# A one-off container of the worker at AIA_IMAGE_TAG, with the worker's environment:
# the database, AIA_POPULATION_OPERATORS (who may operate the population; unset, nobody)
# and AIA_POPULATION_ASSET_ROOT over the read-only directory bin/sync-population.sh
# filled. It prints ids and outcomes as JSON, never a row of the panel, and exits as
# the command does: 0 done, 2 refused with nothing written, 3 the population refused it.

# shellcheck source=deploy/develop/bin/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_env_file
cd "$DEPLOY_DIR" || exit 1
[ "$#" -gt 0 ] || die "name a command: status, import, attach, establish or promote"
exec "${COMPOSE[@]}" run --rm --no-deps -T worker python -m aia_executors.population_ops "$@"
