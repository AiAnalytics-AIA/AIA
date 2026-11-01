#!/bin/bash
# The Document Server's entrypoint, then its api.js written once more under a fixed cache tag
# (artifact-report RPT8e; plan report-editor-hosting).
#
# The image ships api.js.tpl, not api.js. Its start script (/app/ds/run-document-server.sh) runs
# documentserver-flush-cache.sh, and again through documentserver-generate-allfonts.sh, which
# writes api.js from the template under a tag made from the start's date and minute
# (md5 of %Y.%m.%d-%H%M). Zpráva loads that script only under its Subresource Integrity
# (AIA_ONLYOFFICE_API_INTEGRITY), so a tag that moves with every start would refuse the editor
# after any restart. Once the start script has run every step that writes api.js (it ends by
# following its logs), this runs upstream's own flush-cache script with its own option, -h, under
# AIA_DS_CACHE_TAG: api.js and nginx's $cache_tag are written by the same script, so they agree.
# Nothing of the program is changed or replaced (NOTICE).
set -u

: "${AIA_DS_CACHE_TAG:?the fixed cache tag (deploy/develop/docs/docker-compose.yml)}"

# This script is PID 1: a stop reaches the start script, whose own trap stops its services.
trap 'kill -TERM "${ds:-}" 2>/dev/null; wait "${ds:-}"; exit $?' TERM INT
/app/ds/run-document-server.sh &
ds=$!

# Upstream's last step follows its logs; a start sequence measured at 274-330 s, bounded at 900.
echo "[aia] waiting for the start script's last step to set the fixed cache tag"
waited=0
until pgrep -f 'xargs tail -F' > /dev/null; do
  kill -0 "$ds" 2>/dev/null || { wait "$ds"; exit $?; }
  if [ "$waited" -ge 900 ]; then
    echo "[aia] the start script never reached its last step in 900 s: api.js keeps upstream's per-start tag and the server stays unhealthy" >&2
    break
  fi
  sleep 2
  waited=$((waited + 2))
done
if [ "$waited" -lt 900 ]; then
  if documentserver-flush-cache.sh -h "$AIA_DS_CACHE_TAG"; then
    echo "[aia] api.js written under the fixed cache tag $AIA_DS_CACHE_TAG"
  else
    echo "[aia] documentserver-flush-cache.sh -h failed ($?): the server stays unhealthy" >&2
  fi
fi

wait "$ds"
