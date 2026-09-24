#!/usr/bin/env python3
"""Prove what the develop host serves, through the committed Caddyfile (ADR 0015).

    python3 tools/develop_routing_proof.py [--caddy PATH] [--keep] [--caddyfile PATH]

``tools/caddy_routes.py`` checks the Caddyfile's *adapted configuration*; this
runs it. The real ``deploy/develop/Caddyfile`` -- not a copy, not an edit -- is
started with the develop Compose file's environment names, in front of the same
three upstreams it names (``api:8000``, ``web:3000``, ``legacy-panel:8765``),
each a local process on this machine:

    legacy-panel  the vendored unit on the workbench's scratch copy and fictional
                  panel (tools/ui_workbench/unit_standin.py; no AI provider) on
                  loopback, behind the unit's own runtime/relay.py, as the
                  container's entrypoint runs it
    api           the real aia_api on a scratch SQLite file, the local
                  environment's development identity, the gate switched on
                  (tools/ui_workbench/api_standin.py --panel-origin)
    web           ``next dev`` for apps/web, skin, hand-off and re-home on

and then asks the product and legacy hostnames what a browser would, printing
one line per request. It exits 1 if any answer is not the one ADR 0015 says.
``--caddyfile`` runs another revision of the file instead, to see what it
served (``git show <ref>:deploy/develop/Caddyfile > old.Caddyfile``).

Needs root on a disposable machine (Caddy binds 80 and 443, and installs its
local CA for the *.localhost names), the names below in /etc/hosts pointing at
127.0.0.1, ``make setup`` for the API's Python (AIA_API_PYTHON, else this
interpreter), the workbench's unit venv (``make ui-workbench`` once), and a
Caddy 2 binary (--caddy, else ``caddy`` on PATH). Never a deployment: a local
proof on a fictional panel. Everything it writes is under tmp/develop-routing/.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import http.client
import json
import os
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
HOME = REPO / "tmp" / "develop-routing"
CADDYFILE = REPO / "deploy" / "develop" / "Caddyfile"
UNIT_COPY = REPO / "tmp" / "ui-workbench" / "unit"
UNIT_PYTHON = REPO / "tmp" / "ui-workbench" / "venv" / "bin" / "python"
DOCUMENT = REPO / "legacy" / "npc-panel-18.6.6" / "app" / "ui_app.html"
WEB = REPO / "apps" / "web"

PRODUCT, LEGACY = "aia.localhost", "legacy.localhost"
UPSTREAMS = {"api": 8000, "web": 3000, "legacy-panel": 8765}
OPERATOR = "workbench@example.invalid"
ORACLE_USER, ORACLE_PASSWORD = "oracle", "local-proof-only"


def _resolves_locally(name: str) -> bool:
    try:
        return socket.gethostbyname(name) == "127.0.0.1"
    except OSError:
        return False


def _spawn(name: str, argv: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen[bytes]:
    HOME.mkdir(parents=True, exist_ok=True)
    log = (HOME / f"{name}.log").open("wb")
    return subprocess.Popen(
        argv,
        cwd=cwd,
        env={**os.environ, **env},
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def _wait_port(port: int, what: str, seconds: int) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise SystemExit(f"proof: {what} did not listen on {port} within {seconds}s; see {HOME}")


class Site:
    """HTTPS to one hostname through Caddy, verified against Caddy's local CA."""

    def __init__(self, host: str, ca: Path) -> None:
        self.host = host
        self.tls = ssl.create_default_context(cafile=str(ca))

    def get(
        self, path: str, headers: dict[str, str] | None = None, method: str = "GET"
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPSConnection(self.host, 443, context=self.tls, timeout=120)
        try:
            conn.request(method, path, headers={"Accept-Encoding": "identity", **(headers or {})})
            r = conn.getresponse()
            return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
        finally:
            conn.close()


def prove(caddy: str) -> list[tuple[bool, str]]:
    ca = HOME / "data" / "caddy" / "pki" / "authorities" / "local" / "root.crt"
    deadline = time.monotonic() + 60
    while not ca.exists() and time.monotonic() < deadline:
        time.sleep(0.5)
    product, legacy = Site(PRODUCT, ca), Site(LEGACY, ca)
    pinned = hashlib.sha256(DOCUMENT.read_bytes()).hexdigest()
    html = {"Accept": "text/html"}
    out: list[tuple[bool, str]] = []

    def line(ok: bool, what: str, got: str) -> None:
        out.append((ok, f"{'PASS' if ok else 'FAIL'}  {what:58} {got}"))

    def is_unit_document(body: bytes) -> bool:
        return hashlib.sha256(body).hexdigest() == pinned or b"NPC_BOOT_STAGE" in body

    # Signed out.
    s, h, b = product.get("/", html)
    line(
        s == 302 and h.get("location") == "/app/clients" and not is_unit_document(b),
        f"GET https://{PRODUCT}/ (signed out)",
        f"{s} Location: {h.get('location')} body {len(b)} B",
    )
    for path in ("/app/clients", "/classic"):
        s, h, _ = product.get(path, html)
        want = "/login?next=" + path.replace("/", "%2F")
        line(
            s == 302 and h.get("location") == want,
            f"GET {path} (signed out)",
            f"{s} -> {h.get('location')}",
        )
    s, h, _ = product.get("/api/bootstrap", {"Accept": "application/json"})
    line(s == 401, "GET /api/bootstrap, the unit (signed out)", str(s))

    # Sign in the way /login does after Cognito: the id token to the gate's session.
    s, h, _ = product.get(
        "/api/v1/panel/session",
        {"Authorization": f"Bearer {OPERATOR}", "Origin": f"https://{PRODUCT}"},
        method="POST",
    )
    cookie = (h.get("set-cookie") or "").split(";", 1)[0]
    line(
        s == 204 and cookie.startswith("aia_panel="),
        "POST /api/v1/panel/session",
        f"{s} {cookie[:24]}...",
    )
    signed = {**html, "Cookie": cookie}

    s, h, b = product.get("/", signed)
    served = "the 18.6.6 document" if is_unit_document(b) else "not the 18.6.6 document"
    line(
        s == 302 and h.get("location") == "/app/clients" and not is_unit_document(b),
        f"GET https://{PRODUCT}/ (signed in)",
        f"{s} Location: {h.get('location')} -- {served}",
    )
    s, h, b = product.get("/app/clients", signed)
    line(
        s == 200 and b"/_next/static/" in b and not is_unit_document(b),
        "GET /app/clients (signed in): the React application",
        f"{s} {len(b)} B, Next.js, sha256 {hashlib.sha256(b).hexdigest()[:12]} != pinned",
    )
    s, h, b = product.get("/api/v1/workspace/clients", {"Authorization": f"Bearer {OPERATOR}"})
    names = [c["name"] for c in json.loads(b)] if s == 200 else []
    line(s == 200 and len(names) >= 2, "GET /api/v1/workspace/clients", f"{s} {names}")
    s, h, b = product.get("/classic", signed)
    handoff = b"data-aia-handoff" in b
    line(
        s == 200 and h.get("x-aia-skin") == "applied" and handoff,
        "GET /classic (signed in): the hand-off, skinned",
        f"{s} X-AIA-Skin: {h.get('x-aia-skin')}, hand-off {'present' if handoff else 'absent'}",
    )
    s, h, b = product.get("/api/bootstrap", {"Accept": "application/json", "Cookie": cookie})
    line(
        s == 200 and b.lstrip().startswith(b"{"),
        "GET /api/bootstrap, the unit (signed in)",
        f"{s} JSON",
    )
    s, _, b = product.get("/interface-document", signed)
    line(s == 404 and not is_unit_document(b), "GET /interface-document", str(s))
    # Not in any matcher: the web client's own 404 page (Next.js), never the unit's answer.
    for path in ("/no-such-page", "/studies-archive"):
        s, h, b = product.get(path, signed)
        web = b"/_next/static/" in b
        line(s == 404 and web, f"GET {path}", f"{s} from {'the web client' if web else 'the unit'}")

    # The oracle: the legacy hostname, basic auth, the unit's own bytes.
    s, _, _ = legacy.get("/", html)
    line(s == 401, f"GET https://{LEGACY}/ (no credentials)", str(s))
    auth = base64.b64encode(f"{ORACLE_USER}:{ORACLE_PASSWORD}".encode()).decode()
    s, h, b = legacy.get("/", {**html, "Authorization": f"Basic {auth}"})
    digest = hashlib.sha256(b).hexdigest()
    line(
        s == 200 and digest == pinned and "x-aia-skin" not in h,
        f"GET https://{LEGACY}/ (basic auth): the oracle",
        f"{s} sha256 {digest[:12]} == pinned ui_app.html, unskinned",
    )
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--caddy", default=shutil.which("caddy") or "caddy")
    ap.add_argument("--keep", action="store_true", help="leave everything running afterwards")
    ap.add_argument("--caddyfile", default=str(CADDYFILE), help="another revision of the file")
    args = ap.parse_args(argv)

    missing = [n for n in (PRODUCT, LEGACY, *UPSTREAMS) if not _resolves_locally(n)]
    if missing:
        print("proof: add to /etc/hosts: 127.0.0.1 " + " ".join(missing), file=sys.stderr)
        return 2
    if not UNIT_PYTHON.exists() or not UNIT_COPY.exists():
        print("proof: run `make ui-workbench` once for the unit's venv and copy", file=sys.stderr)
        return 2

    shutil.rmtree(HOME / "data", ignore_errors=True)
    hashed = subprocess.run(
        [args.caddy, "hash-password", "--plaintext", ORACLE_PASSWORD],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    api_python = os.environ.get("AIA_API_PYTHON") or sys.executable
    procs = [
        _spawn(
            "unit",
            [str(UNIT_PYTHON), str(REPO / "tools/ui_workbench/unit_standin.py"), "--port", "18765"],
            UNIT_COPY,
            {},
        ),
        # The unit guards writes by its own loopback origin; the relay rewrites
        # Host/Origin/Referer, as it does in the legacy-panel container.
        _spawn(
            "legacy-panel",
            [
                sys.executable,
                str(REPO / "legacy/npc-panel-18.6.6/runtime/relay.py"),
                "--listen",
                "127.0.0.1:8765",
                "--upstream",
                "127.0.0.1:18765",
            ],
            REPO,
            {},
        ),
        _spawn(
            "api",
            [
                api_python,
                str(REPO / "tools/ui_workbench/api_standin.py"),
                "--port",
                "8000",
                "--fresh",
                "--db",
                str(HOME / "aia.sqlite"),
                "--panel-origin",
                f"https://{PRODUCT}",
            ],
            REPO,
            {},
        ),
        _spawn(
            "web",
            [str(WEB / "node_modules/.bin/next"), "dev", "-p", "3000", "-H", "127.0.0.1"],
            WEB,
            {
                "AIA_LEGACY_PANEL_URL": "http://legacy-panel:8765",
                "AIA_INTERFACE_SKIN_ENABLED": "true",
                "AIA_INTERFACE_REHOME_ENABLED": "true",
                "NEXT_TELEMETRY_DISABLED": "1",
            },
        ),
        _spawn(
            "caddy",
            [args.caddy, "run", "--config", args.caddyfile, "--adapter", "caddyfile"],
            REPO,
            {
                "AIA_PUBLIC_HOSTNAME": PRODUCT,
                "AIA_LEGACY_HOSTNAME": LEGACY,
                "AIA_LEGACY_BASIC_USER": ORACLE_USER,
                "AIA_LEGACY_BASIC_HASH": hashed,
                "AIA_ACME_EMAIL": "proof@example.invalid",
                "XDG_DATA_HOME": str(HOME / "data"),
                "XDG_CONFIG_HOME": str(HOME / "config"),
            },
        ),
    ]
    try:
        for name, port in (("unit", 18765), *UPSTREAMS.items(), ("caddy", 443)):
            _wait_port(port, name, 240)
        # Warm next dev's compile of the pages the proof reads, so no answer times out.
        for path in ("/app/clients", "/interface-document", "/no-such-page"):
            with contextlib.suppress(OSError):
                c = http.client.HTTPConnection("127.0.0.1", 3000, timeout=240)
                c.request("GET", path)
                c.getresponse().read()
        results = prove(args.caddy)
    finally:
        if not args.keep:
            for p in procs:
                with contextlib.suppress(OSError):
                    os.killpg(p.pid, signal.SIGTERM)
    shown = Path(args.caddyfile).resolve()
    where = shown.relative_to(REPO) if shown.is_relative_to(REPO) else shown
    print(f"develop routing proof -- {where}, Caddy {_version(args.caddy)}")
    for _, text in results:
        print(text)
    failed = sum(not ok for ok, _ in results)
    print(f"{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


def _version(caddy: str) -> str:
    out: Any = subprocess.run([caddy, "version"], capture_output=True, text=True).stdout
    return str(out).split()[0] if out else "?"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
