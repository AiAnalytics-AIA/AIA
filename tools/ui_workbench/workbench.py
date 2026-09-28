"""The UI workbench: AIA's client-first interface on this machine, the 18.6.6 unit on request.

    python tools/ui_workbench/workbench.py up        # start (or confirm) AIA
    python tools/ui_workbench/workbench.py status    # what is running, and answering
    python tools/ui_workbench/workbench.py down      # stop everything
    python tools/ui_workbench/workbench.py up --fresh  # also reset the API's (and the unit's) state
    python tools/ui_workbench/workbench.py up --with-unit  # and the 18.6.6 unit beside it, as
                                                       # the reference (ADR 0018)

Four processes, all under tmp/ui-workbench/ (git-ignored), and a fifth on request:

    api      the real aia_api on a scratch SQLite file, local identity, the
             develop seed (api_standin.py)                      127.0.0.1:8766
    worker   `python -m aia_worker` over the API's SQLite file and artifact store, with
             the workbench composition (aia_executors.workbench: the fictional
             fieldwork source, ADR 0016), so a research run finishes here
    web      `next dev` for apps/web                            127.0.0.1:13000
    facade   routes like the develop Caddyfile, minus the gates 127.0.0.1:8780
    unit     with --with-unit only: the vendored ui_server.py on a scratch copy of
             app/, fictional panel (unit_standin.py)             127.0.0.1:8767

http://127.0.0.1:8780/workbench/sign-in signs in as the seeded operator and
opens the client directory, as develop does after sign-in (ADR 0015).
AIA needs none of the unit, as on develop (ADR 0018). With --with-unit,
http://127.0.0.1:8767/ is the unit, byte for byte: the reference to compare a
screen with, never part of AIA. The facade routes nothing to it, as the develop
Caddyfile does not: its old paths are the web client's 404.

The unit's own Python dependencies go into tmp/ui-workbench/venv (uv when
present, else venv + pip), keyed by the requirements file's hash. The API runs
on the repository's environment (`make setup`): AIA_API_PYTHON, else .venv.
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

UNIT_PORT, API_PORT, WEB_PORT, FACADE_PORT = 8767, 8766, 13000, 8780
WITH_UNIT = HOME / "with-unit"
NAMES = ("unit", "api", "worker", "web", "facade")
DB = HOME / "aia.sqlite"
ARTIFACTS = HOME / "artifacts"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _python() -> Path:
    return VENV / "bin" / "python"


def _api_python() -> str:
    """The repository's Python, which has aia_api installed; not the unit's venv."""
    configured = os.environ.get("AIA_API_PYTHON")
    if configured:
        return configured
    local = REPO / ".venv" / "bin" / "python"
    return str(local) if local.exists() else sys.executable


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


def up(fresh: bool, with_unit: bool = False) -> int:
    HOME.mkdir(parents=True, exist_ok=True)
    state = {k: v for k, v in _read_state().items() if _alive(v)}
    if with_unit != WITH_UNIT.exists() and state:
        print("workbench: running in the other mode; `down` first", file=sys.stderr)
        return 1
    if fresh:
        for name in ("unit", "api", "worker"):
            if name in state:
                _stop(name, state.pop(name))
    if with_unit:
        WITH_UNIT.write_text("the 18.6.6 unit runs beside AIA here, as the reference\n")
        ensure_venv()
        ensure_unit_copy(fresh)
    else:
        WITH_UNIT.unlink(missing_ok=True)
    ensure_web_modules()

    if "unit" not in state and with_unit:
        state["unit"] = _spawn(
            "unit", [str(_python()), str(HERE / "unit_standin.py"), "--port", str(UNIT_PORT)], UNIT
        )
    if "api" not in state:
        state["api"] = _spawn(
            "api",
            [
                _api_python(),
                str(HERE / "api_standin.py"),
                "--port",
                str(API_PORT),
                "--artifacts",
                str(ARTIFACTS),
                "--fieldwork",
                "synthetic_fixture",
            ]
            + (["--fresh"] if fresh else []),
            REPO,
        )
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
            {"NEXT_TELEMETRY_DISABLED": "1"},
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
                "--api",
                f"127.0.0.1:{API_PORT}",
            ],
            REPO,
        )
    STATE.write_text(json.dumps(state, indent=1) + "\n")

    if with_unit:
        _wait(f"http://127.0.0.1:{UNIT_PORT}/", "the unit", 180)
    _wait(f"http://127.0.0.1:{API_PORT}/api/v1/health", "the AIA API", 120)
    # The API creates the schema on its first start; the worker claims from it.
    if "worker" not in state:
        state["worker"] = _spawn(
            "worker",
            [_api_python(), "-m", "aia_worker"],
            REPO,
            {
                "AIA_ENV": "local",
                "DATABASE_URL": f"sqlite+pysqlite:///{DB}",
                "AIA_WORKER_EXECUTORS": "aia_executors.workbench:build_registry",
                "AIA_WORKER_ID": "workbench-worker",
                "AIA_WORKER_POLL_SECONDS": "1",
                "AIA_STORAGE_BACKEND": "filesystem",
                "AIA_STORAGE_ROOT": str(ARTIFACTS),
            },
        )
        STATE.write_text(json.dumps(state, indent=1) + "\n")
    _wait(f"http://127.0.0.1:{FACADE_PORT}/app/clients", "the facade and web client", 240)
    print(f"workbench: AIA      http://127.0.0.1:{FACADE_PORT}/workbench/sign-in")
    if with_unit:
        print(
            f"workbench: unit     http://127.0.0.1:{UNIT_PORT}/ (reference only; AIA reaches none)"
        )
    print(f"workbench: logs     {LOGS.relative_to(REPO)}/")
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
    WITH_UNIT.unlink(missing_ok=True)
    return 0


def status() -> int:
    state = _read_state()
    with_unit = WITH_UNIT.exists()
    ok = True
    for name in NAMES:
        if name == "unit" and not with_unit:
            print("unit    not started (reference only: up --with-unit)")
            continue
        pid = state.get(name)
        alive = bool(pid) and _alive(pid or 0)
        ok &= alive
        print(f"{name:7} {'running' if alive else 'stopped'} {pid or ''}")
    api, _ = _probe(f"http://127.0.0.1:{FACADE_PORT}/api/v1/health", timeout=30)
    print(f"api     http://127.0.0.1:{FACADE_PORT}/api/v1/health  HTTP {api}")
    app, _ = _probe(f"http://127.0.0.1:{FACADE_PORT}/app/clients", timeout=60)
    print(f"app     http://127.0.0.1:{FACADE_PORT}/app/clients  HTTP {app}")
    return 0 if ok and api == 200 and app == 200 else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_up = sub.add_parser("up")
    p_up.add_argument(
        "--fresh", action="store_true", help="reset the unit's and the API's scratch state"
    )
    p_up.add_argument(
        "--with-unit",
        action="store_true",
        help="also start the 18.6.6 unit on its own port, as the reference (ADR 0018)",
    )
    sub.add_parser("down")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    if args.cmd == "up":
        return up(args.fresh, args.with_unit)
    if args.cmd == "down":
        return down()
    return status()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
