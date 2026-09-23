#!/usr/bin/env bash
# NPC Panel 18.6.6 -- container supervisor.
#
# Linux replacement for A0_NPC_PANEL_START.bat -> launcher_bootstrap.py.
# The batch launcher did: find Python -> install deps -> run
# launcher_bootstrap.py, which starts a persistent Research OS worker and the
# HTTP UI server as separate processes. Python and dependencies are baked into
# the image, so this script only has to (1) place and verify the tree,
# (2) start the worker, (3) start the server, (4) make it reachable.
#
# Commands:
#   start            verify, start worker + server, forward the port (default)
#   server           start only ui_server.py
#   worker           start only worker_daemon.py
#   verify           verify the tree and exit
#   selftest         python selftest.py  (offline release self-test)
#   doctor           python doctor.py    (environment diagnostics)
#   shell            interactive shell in the tree
#   <anything else>  exec'd inside the tree, e.g. `python -m pytest tests -q`
#
# Environment (defaults set in the Dockerfile):
#   NPC_TREE              working copy of the tree (default /app)
#   NPC_TREE_SOURCE       pristine extracted tree, read-only (default /reference)
#   NPC_DATA_SOURCE       directory holding the data-manifest files (default /data)
#   NPC_DATA_MANIFEST     data-manifest.json from extract_legacy.py; when it
#                         exists the data files are hydrated into the tree
#   NPC_REFERENCE_META    directory with the verification manifests
#   NPC_SUMS_FILE         runtime-asset sums file in it (default SHA256SUMS.txt)
#   NPC_INVENTORY_FILE    file inventory in it (default reference-file-inventory.json)
#   NPC_TREE_SEED         once | always | never   copy source -> working copy
#   NPC_VERIFY            strict | warn | off      tree verification
#   NPC_PUBLIC_PORT       port published on the container interface (8765)
#   NPC_BIND_IP           interface address for the forwarder (auto-detected)
#   NPC_PORT_SCAN         where ui_server.py may have bound (8765-8785)
#   NPC_START_WORKER      1 | 0
#   NPC_STARTUP_TIMEOUT_S seconds to wait for /health before giving up (120)
#   NPC_UI_SERVER_ARGS    extra arguments appended to `python ui_server.py`
#   NPC_WORKER_ARGS       extra arguments appended to `python worker_daemon.py`
#
# Everything the reference itself reads (ANTHROPIC_API_KEY, NPC_COST_MODE,
# NPC_PANEL, ...) is passed through untouched; see runtime-environment.md.
set -euo pipefail

TREE="${NPC_TREE:-/app}"
SRC="${NPC_TREE_SOURCE:-/reference}"
SEED="${NPC_TREE_SEED:-once}"
VERIFY="${NPC_VERIFY:-strict}"
PUBLIC_PORT="${NPC_PUBLIC_PORT:-8765}"
PORT_SCAN="${NPC_PORT_SCAN:-8765-8785}"
START_WORKER="${NPC_START_WORKER:-1}"
STARTUP_TIMEOUT="${NPC_STARTUP_TIMEOUT_S:-120}"
NPC_HOME="${NPC_HOME:-/opt/npc}"
REF_META="${NPC_REFERENCE_META:-/opt/aia-reference}"
SUMS_FILE="${NPC_SUMS_FILE:-SHA256SUMS.txt}"
INVENTORY_FILE="${NPC_INVENTORY_FILE:-reference-file-inventory.json}"
DATA_SOURCE="${NPC_DATA_SOURCE:-/data}"
DATA_MANIFEST="${NPC_DATA_MANIFEST:-/opt/npc/manifests/data-manifest.json}"

LOG_DIR="$TREE/logs"
WORKER_PID=""
SERVER_PID=""
FORWARD_PID=""
SHUTTING_DOWN=0

log()  { printf '[npc %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die()  { log "ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------- tree -----
seed_tree() {
  # The pristine extraction stays read-only; the app runs on a copy because
  # executing the reference rewrites its SQLite state (runtime-environment.md).
  case "$TREE" in /|"") die "refusing to use '$TREE' as the working tree" ;; esac
  mkdir -p "$TREE"

  local have_tree=0
  [[ -f "$TREE/ui_server.py" && -f "$TREE/ui_app.html" ]] && have_tree=1

  case "$SEED" in
    never)
      (( have_tree )) || die "no tree in $TREE and NPC_TREE_SEED=never"
      ;;
    once)
      if (( have_tree )); then
        log "working tree present in $TREE (NPC_TREE_SEED=once, not reseeding)"
        return
      fi
      copy_tree
      ;;
    always)
      if (( have_tree )); then
        log "NPC_TREE_SEED=always: discarding working tree state in $TREE"
        find "$TREE" -mindepth 1 -delete
      fi
      copy_tree
      ;;
    *) die "NPC_TREE_SEED must be once|always|never, got '$SEED'" ;;
  esac
}

copy_tree() {
  [[ -f "$SRC/ui_server.py" ]] || die "no 18.6.6 tree at $SRC (expected ui_server.py). Mount the extracted archive read-only at $SRC."
  log "seeding working tree: $SRC -> $TREE"
  # cp -a keeps timestamps; the Windows venv (.npc_runtime) is useless here.
  cp -a "$SRC/." "$TREE/"
  rm -rf "$TREE/.npc_runtime"
  chmod -R u+w "$TREE" 2>/dev/null || true
  log "seeded $(find "$TREE" -type f | wc -l | tr -d ' ') files"
}

verify_tree() {
  [[ "$VERIFY" == "off" ]] && { log "tree verification disabled (NPC_VERIFY=off)"; return; }
  mkdir -p "$LOG_DIR"
  if python3 "$NPC_HOME/verify_tree.py" "$TREE" \
       --sums "$REF_META/$SUMS_FILE" \
       --inventory "$REF_META/$INVENTORY_FILE"; then
    return
  fi
  if [[ "$VERIFY" == "strict" ]]; then
    die "tree at $TREE is not the audited 18.6.6 snapshot (set NPC_VERIFY=warn to run it anyway)"
  fi
  log "WARNING: tree differs from the audited snapshot; continuing because NPC_VERIFY=warn"
}

hydrate_data() {
  # Extracted-unit mode: app/ is baked into the image and the licence-bound
  # data arrives on a mount. Copy it into the tree, hash-verified. With no
  # manifest (raw-archive mode) the tree already holds everything.
  [[ -f "$DATA_MANIFEST" ]] || return 0
  local -a flags=()
  [[ "$VERIFY" == "strict" ]] || flags+=(--warn)
  if ! python3 "$NPC_HOME/hydrate_data.py" "$TREE" --manifest "$DATA_MANIFEST" --source "$DATA_SOURCE" "${flags[@]}"; then
    die "data hydration failed: mount the data bundle at $DATA_SOURCE (see data-manifest.json) or set NPC_VERIFY=warn to start without it"
  fi
}

ensure_dirs() {
  # Writable subdirs the reference creates on demand (runtime-environment.md).
  mkdir -p "$TREE/prototype_outputs" "$TREE/logs" "$TREE/diagnostics" "$TREE/runs" "$TREE/data"
}

# ------------------------------------------------------------ processes -----
start_worker() {
  [[ "$START_WORKER" == "1" ]] || { log "worker disabled (NPC_START_WORKER=0)"; return; }
  [[ -f "$TREE/worker_daemon.py" ]] || die "worker_daemon.py not found in $TREE"
  local -a extra=()
  [[ -n "${NPC_WORKER_ARGS:-}" ]] && read -r -a extra <<<"$NPC_WORKER_ARGS"
  log "starting Research OS worker (worker_daemon.py ${extra[*]:-}) -> logs/worker.log"
  (
    cd "$TREE"
    # launcher_bootstrap.py keeps the worker persistent; do the same.
    while (( ! SHUTTING_DOWN )); do
      python3 -u worker_daemon.py "${extra[@]}" >>"$LOG_DIR/worker.log" 2>&1 && rc=0 || rc=$?
      log "worker exited with code $rc; restarting in 5s" >>"$LOG_DIR/worker.log"
      sleep 5
    done
  ) &
  WORKER_PID=$!
}

start_server() {
  [[ -f "$TREE/ui_server.py" ]] || die "ui_server.py not found in $TREE"
  local -a extra=()
  [[ -n "${NPC_UI_SERVER_ARGS:-}" ]] && read -r -a extra <<<"$NPC_UI_SERVER_ARGS"
  log "starting HTTP UI server (ui_server.py ${extra[*]:-}) -> logs/startup.log"
  (
    cd "$TREE"
    exec python3 -u ui_server.py "${extra[@]}"
  ) > >(tee -a "$LOG_DIR/startup.log") 2>&1 &
  SERVER_PID=$!
}

# Scan 127.0.0.1:$PORT_SCAN for an HTTP answer on /health and print the port.
find_server_port() {
  python3 - "$PORT_SCAN" <<'PY'
import sys, urllib.request, urllib.error
lo, _, hi = sys.argv[1].partition("-")
lo, hi = int(lo), int(hi or lo)
for port in range(lo, hi + 1):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
    except urllib.error.HTTPError:
        pass                      # any HTTP status means the server is up
    except Exception:
        continue
    print(port)
    sys.exit(0)
sys.exit(1)
PY
}

wait_for_server() {
  local deadline=$(( SECONDS + STARTUP_TIMEOUT )) port
  while (( SECONDS < deadline )); do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      die "ui_server.py exited during startup; see $LOG_DIR/startup.log"
    fi
    if port="$(find_server_port)"; then
      echo "$port"
      return 0
    fi
    sleep 1
  done
  die "ui_server.py did not answer on 127.0.0.1:$PORT_SCAN within ${STARTUP_TIMEOUT}s; see $LOG_DIR/startup.log"
}

container_ip() {
  # NPC_BIND_IP overrides detection (e.g. host networking). Otherwise take the
  # address of the interface that carries the default route -- in Docker that
  # is the container's bridge IP, which port publishing targets.
  if [[ -n "${NPC_BIND_IP:-}" ]]; then echo "$NPC_BIND_IP"; return; fi
  python3 - <<'PY'
import socket
ip = None
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("10.255.255.255", 1))   # no packet is sent for UDP connect
    ip = s.getsockname()[0]
    s.close()
except Exception:
    pass
if not ip or ip.startswith("127."):
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "0.0.0.0"
print(ip)
PY
}

# Does an HTTP server answer on $1:$2? (any status counts)
http_answers() {
  python3 - "$1" "$2" <<'PY'
import sys, urllib.request, urllib.error
try:
    urllib.request.urlopen(f"http://{sys.argv[1]}:{sys.argv[2]}/health", timeout=2)
except urllib.error.HTTPError:
    pass
except Exception:
    sys.exit(1)
sys.exit(0)
PY
}

start_forwarder() {
  # The reference binds loopback (it is a localhost desktop app). Docker port
  # publishing targets the container interface, so relay it unless the server
  # is already reachable there on the public port.
  local actual_port="$1" ip
  ip="$(container_ip)"
  if [[ "$ip" == "0.0.0.0" || "$ip" == 127.* ]]; then
    log "WARNING: no non-loopback interface found; skipping port forwarder"
    return
  fi
  if [[ "$actual_port" == "$PUBLIC_PORT" ]] && http_answers "$ip" "$PUBLIC_PORT"; then
    log "server already reachable on $ip:$PUBLIC_PORT; no forwarder needed"
    return
  fi
  # An HTTP relay, not a TCP one: ui_server.py's _guard_origin() only accepts
  # mutating requests whose Origin is its own loopback address, so Host,
  # Origin and Referer are rewritten on the way in (see relay.py).
  log "publishing $ip:$PUBLIC_PORT -> 127.0.0.1:$actual_port (relay.py, origin rewritten)"
  python3 -u "$NPC_HOME/relay.py" --listen "$ip:$PUBLIC_PORT" --upstream "127.0.0.1:$actual_port" \
    > >(tee -a "$LOG_DIR/relay.log") 2>&1 &
  FORWARD_PID=$!
  sleep 1
  if ! kill -0 "$FORWARD_PID" 2>/dev/null; then
    FORWARD_PID=""
    log "WARNING: could not bind $ip:$PUBLIC_PORT; the UI may be unreachable from outside the container"
  elif ! http_answers "$ip" "$PUBLIC_PORT"; then
    log "WARNING: relay is up but $ip:$PUBLIC_PORT does not answer yet"
  fi
}

shutdown() {
  (( SHUTTING_DOWN )) && return
  SHUTTING_DOWN=1
  [[ -n "$FORWARD_PID$SERVER_PID$WORKER_PID" ]] || return 0
  log "shutting down"
  for pid in "$FORWARD_PID" "$SERVER_PID"; do
    if [[ -n "$pid" ]]; then kill -TERM "$pid" 2>/dev/null || true; fi
  done
  if [[ -n "$WORKER_PID" ]]; then
    # worker_daemon.py is a child of the restart-loop subshell: stop it first
    # so the loop cannot respawn it, then the loop itself.
    pkill -TERM -P "$WORKER_PID" 2>/dev/null || true
    kill -TERM "$WORKER_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}

banner() {
  log "NPC Panel 18.6.6 reference runtime"
  log "python $(python3 --version 2>&1 | cut -d' ' -f2) · tree $TREE · source $SRC"
  if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then log "ANTHROPIC_API_KEY present"; else log "ANTHROPIC_API_KEY absent (offline baseline)"; fi
  if [[ -n "${NPC_PANEL:-}" ]]; then log "WARNING: NPC_PANEL overrides the population version (see configuration-contract.md)"; fi
  return 0
}

# ----------------------------------------------------------------- main -----
cmd="${1:-start}"; shift || true
trap shutdown EXIT TERM INT

case "$cmd" in
  start)
    banner
    seed_tree
    hydrate_data
    verify_tree
    ensure_dirs
    start_worker
    start_server
    port="$(wait_for_server)"
    log "ui_server.py is answering on 127.0.0.1:$port"
    start_forwarder "$port"
    log "READY -> http://localhost:$PUBLIC_PORT/  (this is the 18.6.6 UI; GET /health for status)"
    # Supervise: exit when the server exits, with its code.
    wait "$SERVER_PID" && rc=0 || rc=$?
    (( SHUTTING_DOWN )) || log "ui_server.py exited with code $rc"
    shutdown
    exit "$rc"
    ;;
  server)
    banner; seed_tree; hydrate_data; verify_tree; ensure_dirs
    start_server
    port="$(wait_for_server)"
    start_forwarder "$port"
    wait "$SERVER_PID" && rc=0 || rc=$?
    shutdown; exit "$rc"
    ;;
  worker)
    banner; seed_tree; hydrate_data; verify_tree; ensure_dirs
    START_WORKER=1 start_worker
    wait "$WORKER_PID" && exit 0 || exit $?
    ;;
  verify)
    seed_tree
    hydrate_data
    VERIFY=strict verify_tree
    ;;
  selftest)
    seed_tree; hydrate_data; verify_tree; ensure_dirs
    cd "$TREE" && exec python3 -u selftest.py "$@"
    ;;
  doctor)
    seed_tree; hydrate_data; ensure_dirs
    cd "$TREE" && exec python3 -u doctor.py "$@"
    ;;
  shell)
    seed_tree; hydrate_data; ensure_dirs
    cd "$TREE" && exec bash "$@"
    ;;
  *)
    seed_tree; hydrate_data; ensure_dirs
    cd "$TREE" && exec "$cmd" "$@"
    ;;
esac
