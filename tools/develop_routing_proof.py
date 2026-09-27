#!/usr/bin/env python3
"""Prove what the develop host serves, through the committed Caddyfile (ADR 0015, 0018).

    python3 tools/develop_routing_proof.py [--caddy PATH] [--keep] [--caddyfile PATH]

``tools/caddy_routes.py`` checks the Caddyfile's *adapted configuration*; this
runs it. The real ``deploy/develop/Caddyfile`` -- not a copy, not an edit -- is
started with the develop Compose file's environment names, in front of the two
upstreams it names (``api:8000``, ``web:3000``) and the worker the host runs
beside them, each a local process on this machine:

    api           the real aia_api on a scratch SQLite file, the local
                  environment's development identity and AIA's session gate
                  (tools/ui_workbench/api_standin.py)
    web           ``next dev`` for apps/web
    worker        ``python -m aia_worker`` with the production registry
                  (``aia_executors.registry``), over the API's database and
                  artifact directory: a research run parks at fieldwork (ADR 0016)

No 18.6.6 unit runs, and none is needed (ADR 0018 decision 5): the proof asks
the product hostname what a browser would, and the old oracle hostname whether
anything still answers for it, printing one line per request. It exits 1 if any
answer is not the one the ADRs say. ``--caddyfile`` runs another revision of the
file instead, to see what it served
(``git show <ref>:deploy/develop/Caddyfile > old.Caddyfile``).

Needs root on a disposable machine (Caddy binds 80 and 443, and installs its
local CA for the *.localhost names), the names below in /etc/hosts pointing at
127.0.0.1, ``make setup`` for the API's Python (AIA_API_PYTHON, else this
interpreter), ``apps/web``'s modules, and a Caddy 2 binary (--caddy, else
``caddy`` on PATH). Never a deployment: a local proof. Everything it writes is
under tmp/develop-routing/.
"""

from __future__ import annotations

import argparse
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
# Read, never served: the pinned 18.6.6 document, so an answer can be told apart from it.
DOCUMENT = REPO / "legacy" / "npc-panel-18.6.6" / "app" / "ui_app.html"
WEB = REPO / "apps" / "web"

PRODUCT, LEGACY = "aia.localhost", "legacy.localhost"
UPSTREAMS = {"api": 8000, "web": 3000}
OPERATOR = "workbench@example.invalid"


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
        self,
        path: str,
        headers: dict[str, str] | None = None,
        method: str = "GET",
        body: object = None,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPSConnection(self.host, 443, context=self.tls, timeout=120)
        sent = {"Accept-Encoding": "identity", **(headers or {})}
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            sent["Content-Type"] = "application/json"
        try:
            conn.request(method, path, body=data, headers=sent)
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
    s, h, _ = product.get("/app/clients", html)
    line(
        s == 302 and h.get("location") == "/login?next=%2Fapp%2Fclients",
        "GET /app/clients (signed out)",
        f"{s} -> {h.get('location')}",
    )
    # The 18.6.6 interface is not served (ADR 0018): /classic is AIA's own page.
    s, h, b = product.get("/classic", html)
    line(
        s == 200 and "už není součástí AIA".encode() in b and not is_unit_document(b),
        "GET /classic (signed out): AIA's page, not 18.6.6",
        f"{s} {len(b)} B",
    )
    # The unit's old paths are the web client's 404: nothing of 18.6.6 answers (ADR 0018).
    for path in ("/api/bootstrap", "/files/x", "/health"):
        s, h, b = product.get(path, {"Accept": "application/json"})
        web = b"/_next/static/" in b
        line(
            s == 404 and web,
            f"GET {path} (signed out): no unit",
            f"{s} from {'the web client' if web else '?'}",
        )

    # Sign in the way /login does after Cognito: the id token to AIA's session (ADR 0018).
    s, h, _ = product.get(
        "/api/v1/session",
        {"Authorization": f"Bearer {OPERATOR}", "Origin": f"https://{PRODUCT}"},
        method="POST",
    )
    aia_cookie = (h.get("set-cookie") or "").split(";", 1)[0]
    line(
        s == 204 and aia_cookie.startswith("aia_session="),
        "POST /api/v1/session",
        f"{s} {aia_cookie[:24]}...",
    )
    signed = {**html, "Cookie": aia_cookie}
    s, h, _ = product.get("/app/clients", signed)
    line(s == 200, "GET /app/clients (AIA's session)", str(s))
    # A cookie that is not AIA's session -- the retired panel's among them -- is no way in.
    s, h, _ = product.get("/app/clients", {**html, "Cookie": "aia_panel=" + OPERATOR})
    line(
        s == 302 and (h.get("location") or "").startswith("/login?next="),
        "GET /app/clients (another cookie only)",
        f"{s} -> {h.get('location')}",
    )

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
    line(
        s == 200 and not is_unit_document(b) and "x-aia-skin" not in h,
        "GET /classic (signed in): still AIA's page, no hand-off",
        f"{s} {len(b)} B",
    )
    s, h, b = product.get("/api/bootstrap", {"Accept": "application/json", "Cookie": aia_cookie})
    line(
        s == 404 and b"/_next/static/" in b,
        "GET /api/bootstrap (signed in): no unit",
        f"{s} from {'the web client' if b'/_next/static/' in b else '?'}",
    )
    s, _, b = product.get("/interface-document", signed)
    line(s == 404 and not is_unit_document(b), "GET /interface-document", str(s))
    # Not in any matcher: the web client's own 404 page (Next.js), never the unit's answer.
    for path in ("/no-such-page", "/studies-archive"):
        s, h, b = product.get(path, signed)
        web = b"/_next/static/" in b
        line(s == 404 and web, f"GET {path}", f"{s} from {'the web client' if web else 'the unit'}")

    research(product, line)

    # The old oracle hostname: the product's Caddy has no site for it any more
    # (ADR 0018 decision 5), so the TLS handshake finds no certificate to offer.
    try:
        s, _, _ = legacy.get("/", html)
        line(False, f"GET https://{LEGACY}/: nothing serves it", f"{s}, something answered")
    except (ssl.SSLError, OSError) as exc:
        line(True, f"GET https://{LEGACY}/: nothing serves it", type(exc).__name__)
    return out


# A design that passes AIA's readiness: two questions, one tracked set, n in range.
DESIGN: dict[str, Any] = {
    "title": "Proof · fiktivní výzkum",
    "n": 300,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často?", "typ": "skala", "skala": [1, 5]},
                {"id": "q2", "text": "Kde?", "typ": "vyber", "kategorie": ["Doma", "Venku"]},
            ],
        },
        {
            "type": "object_battery",
            "object_family": "varianta",
            "objects": ["Varianta A", "Varianta B", "Varianta C", "Varianta D"],
            "scale": [1, 10],
        },
    ],
}


def research(product: Site, line: Any) -> None:
    """ADR 0016 on the production composition: a run parks at fieldwork, nothing invented."""
    bearer = {
        "Authorization": f"Bearer {OPERATOR}",
        "Accept": "application/json",
        "Origin": f"https://{PRODUCT}",
    }

    def call(method: str, path: str, body: object = None) -> tuple[int, Any]:
        s, _, b = product.get(path, bearer, method=method, body=body)
        try:
            return s, json.loads(b)
        except ValueError:
            return s, None

    _, clients = call("GET", "/api/v1/workspace/clients")
    client = (clients or [{}])[0].get("client_id", "")
    s, study = call(
        "POST", f"/api/v1/clients/{client}/studies", {"name": "Proof run", "kind": "RESEARCH"}
    )
    sid = (study or {}).get("study_id", "")
    line(s == 201 and bool(sid), "POST /api/v1/clients/<client>/studies (RESEARCH)", f"{s} {sid}")
    base = f"/api/v1/studies/{sid}"
    s, rev = call("POST", f"{base}/design/revisions", {"content": DESIGN, "source_stage": "run"})
    rid = (rev or {}).get("revision_id", "")
    line(s in (200, 201) and bool(rid), "POST …/design/revisions", f"{s} {rid}")
    s, ready = call("GET", f"{base}/research/readiness?design_revision_id={rid}")
    ready = ready or {}
    line(
        s == 200 and ready.get("ready") is True and ready.get("fieldwork_source") == "ai_runtime",
        "GET …/research/readiness",
        f"{s} ready={ready.get('ready')} fieldwork={ready.get('fieldwork_source')}",
    )
    s, run = call("POST", f"{base}/research/runs", {"design_revision_id": rid})
    run_id = (run or {}).get("run_id", "")
    line(s in (200, 201) and bool(run_id), "POST …/research/runs", f"{s} {run_id}")
    deadline = time.monotonic() + 90
    steps: dict[str, dict[str, Any]] = {}
    while time.monotonic() < deadline:
        _, run = call("GET", f"{base}/research/runs/{run_id}")
        steps = {x["node_key"]: x for x in (run or {}).get("steps", [])}
        if steps.get("run", {}).get("waiting_reason") or (run or {}).get("is_terminal"):
            break
        time.sleep(1)
    fieldwork = steps.get("run", {})
    run = run or {}
    line(
        fieldwork.get("status") == "WAITING_PROVIDER"
        and fieldwork.get("waiting_reason") == "ai_runtime_unavailable"
        and run.get("phase") == "WAITING",
        "the run parks at fieldwork (no AI runtime)",
        f"{run.get('phase')} run={fieldwork.get('status')}/{fieldwork.get('waiting_reason')}",
    )
    done = [k for k in ("compile", "preflight") if steps.get(k, {}).get("status") == "SUCCEEDED"]
    after = {k: steps.get(k, {}).get("status") for k in ("aggregate", "sociomap")}
    line(
        len(done) == 2 and set(after.values()) == {"BLOCKED"},
        "compile + preflight done; aggregate, sociomap blocked",
        f"{done} {after}",
    )
    origins = {x.get("data_origin") for x in steps.values()}
    artifacts = len(run.get("artifact_ids", []))
    line(
        origins == {None} and artifacts == 2,
        "nothing fictional, nothing computed past fieldwork",
        f"data_origin {sorted(map(str, origins))}, {artifacts} artifacts",
    )


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

    shutil.rmtree(HOME / "data", ignore_errors=True)
    api_python = os.environ.get("AIA_API_PYTHON") or sys.executable
    procs = [
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
                "--artifacts",
                str(HOME / "artifacts"),
            ],
            REPO,
            {},
        ),
        _spawn(
            "web",
            [str(WEB / "node_modules/.bin/next"), "dev", "-p", "3000", "-H", "127.0.0.1"],
            WEB,
            {"NEXT_TELEMETRY_DISABLED": "1"},
        ),
        _spawn(
            "caddy",
            [args.caddy, "run", "--config", args.caddyfile, "--adapter", "caddyfile"],
            REPO,
            {
                "AIA_PUBLIC_HOSTNAME": PRODUCT,
                # Set, as on the host, so a site for it, if one came back, would be served.
                "AIA_LEGACY_HOSTNAME": LEGACY,
                "AIA_ACME_EMAIL": "proof@example.invalid",
                "XDG_DATA_HOME": str(HOME / "data"),
                "XDG_CONFIG_HOME": str(HOME / "config"),
            },
        ),
    ]
    try:
        for name, port in (*UPSTREAMS.items(), ("caddy", 443)):
            _wait_port(port, name, 240)
        # The worker the develop host runs: the production registry, which has no
        # fieldwork source (ADR 0016), over the API's schema, created at its start.
        procs.append(
            _spawn(
                "worker",
                [api_python, "-m", "aia_worker"],
                REPO,
                {
                    "DATABASE_URL": f"sqlite+pysqlite:///{HOME / 'aia.sqlite'}",
                    "AIA_WORKER_EXECUTORS": "aia_executors.registry:build_registry",
                    "AIA_WORKER_ID": "proof-worker",
                    "AIA_WORKER_POLL_SECONDS": "1",
                    "AIA_STORAGE_BACKEND": "filesystem",
                    "AIA_STORAGE_ROOT": str(HOME / "artifacts"),
                },
            )
        )
        # Warm next dev's compile of the pages the proof reads, so no answer times out.
        for path in ("/app/clients", "/interface-document", "/no-such-page", "/api/bootstrap"):
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
