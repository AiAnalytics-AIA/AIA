#!/bin/bash
# every 4 min for up to 2 h, run the gate on every pin; print a PR's line only when it changes
here=$(dirname "$0"); declare -A last
for i in $(seq 1 30); do
  for p in $(cut -d: -f1 "${PM_STATE:-./pm-state}/pins.txt" | sort -u); do
    r=$(timeout 120 bash "$here/merge_gate.sh" "$p" 2>&1 | tail -1)
    [ "${last[$p]}" != "$r" ] && echo "$(date -u +%H:%M) $r"; last[$p]="$r"
  done
  [ -s "${PM_STATE:-./pm-state}/pins.txt" ] || break
  sleep 240
done
