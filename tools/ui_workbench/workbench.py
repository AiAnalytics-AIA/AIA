"""The UI workbench: the real 18.6.6 interface with the AIA skin, on this machine.

    python tools/ui_workbench/workbench.py up        # start (or confirm) everything
    python tools/ui_workbench/workbench.py status    # what is running, and answering
    python tools/ui_workbench/workbench.py down      # stop everything
    python tools/ui_workbench/workbench.py up --fresh  # also reset the unit's state

Four processes, all under tmp/ui-workbench/ (git-ignored):

    unit     the vendored ui_server.py on a scratch copy of app/, fictional panel
             (unit_standin.py)                                 127.0.0.1:8767
    web      `next dev` for apps/web, AIA_INTERFACE_SKIN_ENABLED=true  127.0.0.1:13000
    skin     `build-skin.mjs --watch`: skin.css rebuilt on every save
    facade   routes like the develop Caddyfile, minus the gate  127.0.0.1:8780

http://127.0.0.1:8780/ is the skinned interface, as develop serves it after
sign-in. http://127.0.0.1:8767/ is the same unit bare, byte for byte. Edit
apps/web/src/skin/components.css (or tokens.json, legacy-variables.json), reload.

Stdlib only; the unit's own Python dependencies go into tmp/ui-workbench/venv
(uv when present, else venv + pip), keyed by the requirements file's hash.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
UNIT_SRC = REPO / "legacy" / "npc-panel-18.6.6"
WEB = REPO / "apps" / "web"
HOME = REPO / "tmp" / "ui-workbench"
VENV = HOME / "venv"
UNIT = HOME / "unit"
LOGS = HOME / "logs"
STATE = HOME / "state.json"

UNIT_PORT, WEB_PORT, FACADE_PORT = 8767, 13000, 8780


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _python() -> Path:
    return VENV / "bin" / "python"


def ensure_venv() -> None:
    req = UNIT_SRC / "runtime" / "requirements-runtime.txt"
    marker = VENV / ".requirements-sha256"
    want = _hash(req)
    if marker.exists() and marker.read_text().strip() == want and _python().exists():
        return
    print("workbench: installing the unit's runtime requirements (once; a few minutes)")
    shutil.rmtree(VENV, ignore_errors=True)
    # pytest is for the unit's own test suite, not for serving its screens.
    reqs = [line for line in req.read_text().splitlines() if not line.startswith("pytest")]
    trimmed = HOME / "requirements-workbench.txt"
    trimmed.write_text("\n".join(reqs) + "\n")
    if shutil.which("uv"):
        subprocess.run(["uv", "venv", "--python", sys.executable, str(VENV)], check=True)
        subprocess.run(
            ["uv", "pip", "install", "--python", str(_python()), "-r", str(trimmed)], check=True
        )
    else:
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
        subprocess.run(
            [str(_python()), "-m", "pip", "install", "-q", "-r", str(trimmed)], check=True
        )
    marker.write_text(want + "\n")


def ensure_unit_copy(fresh: bool) -> None:
    marker = UNIT / ".app-manifest-sha256"
    want = _hash(UNIT_SRC / "app-manifest.json")
    if not fresh and marker.exists() and marker.read_text().strip() == want:
        return
    print("workbench: copying the unit to a scratch tree (the vendored one is frozen)")
    shutil.rmtree(UNIT, ignore_errors=True)
    shutil.copytree(UNIT_SRC / "app", UNIT, ignore=shutil.ignore_patterns("__pycache__"))
    marker.write_text(want + "\n")


def ensure_web_modules() -> None:
    if not (WEB / "node_modules" / ".bin" / "next").exists():
        print("workbench: npm ci in apps/web")
        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=WEB, check=True)


def _read_state() -> dict[str, int]:
    try:
        return {k: int(v) for k, v in json.loads(STATE.read_text()).items()}
    except (OSError, ValueError):
        return {}


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _spawn(name: str, argv: list[str], cwd: Path, env: dict[str, str] | None = None) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    log = (LOGS / f"{name}.log").open("ab")
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # its own process group, so `down` stops its children too
    )
    return proc.pid


def _probe(url: str, timeout: float = 5) -> tuple[int, dict[str, str]]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}
    except (urllib.error.URLError, OSError):
        return 0, {}


def _wait(url: str, what: str, seconds: int) -> tuple[int, dict[str, str]]:
    deadline = time.monotonic() + seconds
    status, headers = 0, {}
    while time.monotonic() < deadline:
        status, headers = _probe(url, timeout=30)
        if 200 <= status < 500:
            return status, headers
        time.sleep(1)
    raise SystemExit(f"workbench: {what} did not answer at {url} within {seconds}s; see {LOGS}")


def up(fresh: bool) -> int:
    HOME.mkdir(parents=True, exist_ok=True)
    state = {k: v for k, v in _read_state().items() if _alive(v)}
    if fresh and "unit" in state:
        _stop("unit", state.pop("unit"))
    ensure_venv()
    ensure_unit_copy(fresh)
    ensure_web_modules()

    if "unit" not in state:
        state["unit"] = _spawn(
            "unit", [str(_python()), str(HERE / "unit_standin.py"), "--port", str(UNIT_PORT)], UNIT
        )
    if "skin" not in state:
        state["skin"] = _spawn("skin", ["node", "scripts/build-skin.mjs", "--watch"], WEB)
    if "web" not in state:
        state["web"] = _spawn(
            "web",
            [
                str(WEB / "node_modules" / ".bin" / "next"),
                "dev",
                "-p",
                str(WEB_PORT),
                "-H",
                "127.0.0.1",
            ],
            WEB,
            {
                "AIA_LEGACY_PANEL_URL": f"http://127.0.0.1:{UNIT_PORT}",
                "AIA_INTERFACE_SKIN_ENABLED": "true",
                "AIA_INTERFACE_REHOME_ENABLED": "true",
                "AIA_BUILD_SHA": "workbench",
                "NEXT_TELEMETRY_DISABLED": "1",
            },
        )
    if "facade" not in state:
        state["facade"] = _spawn(
            "facade",
            [
                sys.executable,
                str(HERE / "facade.py"),
                "--listen",
                f"127.0.0.1:{FACADE_PORT}",
                "--web",
                f"127.0.0.1:{WEB_PORT}",
                "--unit",
                f"127.0.0.1:{UNIT_PORT}",
            ],
            REPO,
        )
    STATE.write_text(json.dumps(state, indent=1) + "\n")

    _wait(f"http://127.0.0.1:{UNIT_PORT}/", "the unit", 180)
    status, headers = _wait(f"http://127.0.0.1:{FACADE_PORT}/", "the facade and web client", 240)
    skin = headers.get("x-aia-skin", "absent")
    print(
        f"workbench: skinned  http://127.0.0.1:{FACADE_PORT}/  (HTTP {status}, X-AIA-Skin: {skin})"
    )
    print(f"workbench: bare     http://127.0.0.1:{UNIT_PORT}/")
    print(f"workbench: logs     {LOGS.relative_to(REPO)}/")
    if skin != "applied":
        print("workbench: the skin is NOT applied; see logs/web.log", file=sys.stderr)
        return 1
    return 0


def _stop(name: str, pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        return
    for _ in range(50):
        if not _alive(pid):
            break
        time.sleep(0.1)
    else:
        with contextlib.suppress(OSError):
            os.killpg(pid, signal.SIGKILL)
    print(f"workbench: stopped {name} ({pid})")


def down() -> int:
    for name, pid in _read_state().items():
        if _alive(pid):
            _stop(name, pid)
    STATE.unlink(missing_ok=True)
    return 0


def status() -> int:
    state = _read_state()
    ok = True
    for name in ("unit", "web", "skin", "facade"):
        pid = state.get(name)
        alive = bool(pid) and _alive(pid or 0)
        ok &= alive
        print(f"{name:7} {'running' if alive else 'stopped'} {pid or ''}")
    code, headers = _probe(f"http://127.0.0.1:{FACADE_PORT}/", timeout=30)
    skin = headers.get("x-aia-skin", "-")
    print(f"skinned http://127.0.0.1:{FACADE_PORT}/  HTTP {code}  X-AIA-Skin: {skin}")
    return 0 if ok and headers.get("x-aia-skin") == "applied" else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_up = sub.add_parser("up")
    p_up.add_argument("--fresh", action="store_true", help="reset the unit's scratch state")
    sub.add_parser("down")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    if args.cmd == "up":
        return up(args.fresh)
    if args.cmd == "down":
        return down()
    return status()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
