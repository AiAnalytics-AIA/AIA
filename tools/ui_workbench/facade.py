"""The workbench facade: one local origin, routed the way the develop Caddyfile
routes the product hostname (ADR 0015, ADR 0018) -- minus the gates.

    /                      -> 302 /app/clients, AIA's front door
    /api/v1/*              -> the workbench's AIA API (api_standin.py), else 502
    everything else        -> the web client: AIA's pages and its own 404, the
                              18.6.6 unit's old paths among them
    /workbench/sign-in     -> the workbench only: sign in as the seeded operator

The product hostname reaches nothing of the 18.6.6 unit (ADR 0018 decision 5),
and neither does this: when the workbench runs the unit as a reference, it is
on its own port, never behind the facade. The web client's matchers are parsed
from the committed Caddyfile, not copied, so a Caddyfile that stopped sending
AIA's pages to the web client fails here too. There is no gate here: the
workbench is a local design tool on a fictional panel
(tools/ui_workbench/README.md), never a deployment. Its sign-in page puts the
local API's development credential (the operator's e-mail, trusted only in the
local environment) into the tab's session, as /login would after Cognito.

Stdlib only.
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import re
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
CADDYFILE = REPO / "deploy" / "develop" / "Caddyfile"
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
CHUNK = 64 * 1024


def _block(text: str, start: int) -> str:
    """The body of the `{ ... }` block whose opening brace is at or after `start`."""
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[i + 1 : j]
    raise ValueError("unbalanced braces in the Caddyfile")


def web_paths(caddyfile: str) -> list[str]:
    """The path patterns of every named matcher whose `handle` goes to the web client.

    `@web` (AIA's own pages and assets) and `@app` (AIA's application, ADR 0015)
    today; any later matcher that proxies to web:3000 is picked up the same way.
    The gates in front of some of them are not reproduced here.
    """
    patterns: list[str] = []
    for m in re.finditer(r"^\s*@(\w+)\s+path\s+(.+)$", caddyfile, re.MULTILINE):
        handle = re.search(rf"^\s*handle\s+@{m.group(1)}\s*\{{", caddyfile, re.MULTILINE)
        if handle and "web:3000" in _block(caddyfile, handle.start()):
            patterns += m.group(2).split()
    if "/_next/*" not in patterns:
        raise ValueError("no `@name path ...` matcher in the Caddyfile sends /_next/* to web:3000")
    return patterns


SIGN_IN = "/workbench/sign-in"


def route(path: str) -> tuple[str, str]:
    """Where a request path goes, and the path to send upstream.

    The target is one of web, api, redirect or sign-in: as on the product
    hostname, anything not the API is the web client's, a named page or its 404.
    """
    p = urlsplit(path).path
    if p == "/":
        return "redirect", "/app/clients"
    if p == SIGN_IN:
        return "sign-in", p
    if p.startswith("/api/v1/"):
        return "api", path
    return "web", path


def sign_in_page(email: str) -> str:
    """The workbench's stand-in for /login: the tab's AIA session, then the client directory."""
    session = json.dumps(
        {
            "idToken": email,
            "refreshToken": "",
            "expiresAt": 4102444800000,
            "email": email,
            "subject": email,
        }
    )
    return (
        "<!doctype html><meta charset=utf-8><title>Workbench sign-in</title>"
        f"<script>sessionStorage.setItem('aia.session', {json.dumps(session)});"
        "location.replace('/app/clients');</script>"
    )


class Facade(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    web: tuple[str, int] = ("127.0.0.1", 13000)
    api: tuple[str, int] | None = None
    email: str = "workbench@example.invalid"

    def _upstream(self, target: str) -> tuple[str, int]:
        if target == "api" and self.api is not None:
            return self.api
        return self.web

    def _headers_for(self) -> dict[str, str]:
        out = {
            name: value for name, value in self.headers.items() if name.lower() not in HOP_BY_HOP
        }
        out["Connection"] = "close"
        return out

    def _answer(self, status: int, text: str) -> None:
        body = (text + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _proxy(self) -> None:
        target, path = route(self.path)
        if target == "redirect":
            self.send_response(302)
            self.send_header("Location", path)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if target == "sign-in":
            body = sign_in_page(self.email).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return None
        if target == "api" and self.api is None:
            return self._answer(502, "the workbench's AIA API is not running")
        host, port = self._upstream(target)
        if (self.headers.get("Upgrade") or "").lower() == "websocket":
            return self._tunnel(host, port, path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        conn = http.client.HTTPConnection(host, port, timeout=600)
        try:
            conn.request(self.command, path, body=body, headers=self._headers_for())
            resp = conn.getresponse()
        except (ConnectionRefusedError, TimeoutError, OSError) as exc:
            conn.close()
            return self._answer(502, f"{target} at {host}:{port} is not answering: {exc}")

        self.send_response(resp.status, resp.reason)
        for name, value in resp.getheaders():
            if name.lower() in HOP_BY_HOP or name.lower() == "content-length":
                continue
            self.send_header(name, value)
        # Stream and close: http.client has already de-chunked the body.
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        if self.command != "HEAD":
            try:
                while data := resp.read(CHUNK):
                    self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
        conn.close()

    def _tunnel(self, host: str, port: int, path: str) -> None:
        """A WebSocket upgrade, passed through byte for byte: `next dev`'s live
        reload, so a save shows in the browser without a manual refresh."""
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError as exc:
            return self._answer(502, f"web at {host}:{port} is not answering: {exc}")
        upstream.settimeout(None)
        lines = [f"{self.command} {path} HTTP/1.1"] + [f"{k}: {v}" for k, v in self.headers.items()]
        head = "\r\n".join(lines) + "\r\n"
        upstream.sendall(head.encode("latin-1") + b"\r\n")
        client = self.connection

        def pipe(src: socket.socket, dst: socket.socket) -> None:
            try:
                while data := src.recv(CHUNK):
                    dst.sendall(data)
            except OSError:
                pass
            finally:
                for s in (src, dst):
                    with contextlib.suppress(OSError):
                        s.shutdown(socket.SHUT_RDWR)

        back = threading.Thread(target=pipe, args=(upstream, client), daemon=True)
        back.start()
        pipe(client, upstream)
        back.join()
        upstream.close()
        self.close_connection = True

    def do_GET(self) -> None:
        self._proxy()

    def do_POST(self) -> None:
        self._proxy()

    def do_PUT(self) -> None:
        self._proxy()

    def do_PATCH(self) -> None:
        self._proxy()

    def do_DELETE(self) -> None:
        self._proxy()

    def do_HEAD(self) -> None:
        self._proxy()

    def do_OPTIONS(self) -> None:
        self._proxy()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        sys.stderr.write("[facade] " + format % args + "\n")


def _hostport(s: str) -> tuple[str, int]:
    host, _, port = s.rpartition(":")
    return host or "127.0.0.1", int(port)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--listen", default="127.0.0.1:8780")
    ap.add_argument("--web", default="127.0.0.1:13000")
    ap.add_argument("--api", default="127.0.0.1:8766", help='the AIA API; "" for none')
    ap.add_argument("--caddyfile", default=str(CADDYFILE))
    args = ap.parse_args(argv)
    Facade.web = _hostport(args.web)
    Facade.api = _hostport(args.api) if args.api else None
    caddyfile = Path(args.caddyfile).read_text(encoding="utf-8")
    # Refuses a Caddyfile that no longer sends AIA's pages to the web client.
    web_paths(caddyfile)
    listen = _hostport(args.listen)
    srv = ThreadingHTTPServer(listen, Facade)
    print(
        f"[facade] http://{listen[0]}:{listen[1]}/ -> web {args.web}, api {args.api or 'none'}",
        flush=True,
    )
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
