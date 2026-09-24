"""The workbench facade: one local origin, routed the way the develop Caddyfile
routes the product hostname -- minus the gate.

    /                      -> the web client's /interface-document (the skin)
    /interface-document    -> 404, as on develop: reachable only through `/`
    /api/v1/*              -> 502: the workbench runs no AIA API
    the Caddyfile's @web   -> the web client (read from deploy/develop/Caddyfile)
    everything else        -> the 18.6.6 unit, Host/Origin/Referer rewritten to
                              its own origin, as the unit's runtime/relay.py does

The `@web` matcher is parsed from the committed Caddyfile, not copied, so the
one routing fact that decides what the web client serves cannot drift from
develop. There is no identity here: the workbench is a local design tool on a
fictional panel (tools/ui_workbench/README.md), never a deployment.

Stdlib only.
"""

from __future__ import annotations

import argparse
import http.client
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
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


def web_paths(caddyfile: str) -> list[str]:
    """The path patterns of the product hostname's `@web` matcher."""
    m = re.search(r"^\s*@web\s+path\s+(.+)$", caddyfile, re.MULTILINE)
    if not m:
        raise ValueError("the Caddyfile has no `@web path ...` matcher")
    return m.group(1).split()


def _matches(pattern: str, path: str) -> bool:
    # Caddy's path matcher: a trailing * is a prefix match, otherwise exact.
    if pattern.endswith("*"):
        return path.startswith(pattern[:-1])
    return path == pattern


def route(path: str, patterns: list[str]) -> tuple[str, str]:
    """Where a request path goes: ("web" | "unit" | "404" | "no-api", upstream path)."""
    split = urlsplit(path)
    p, query = split.path, ("?" + split.query if split.query else "")
    if p == "/":
        return "web", "/interface-document" + query
    if p == "/interface-document":
        return "404", p
    if p.startswith("/api/v1/"):
        return "no-api", p
    if any(_matches(pat, p) for pat in patterns):
        return "web", path
    return "unit", path


class Facade(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    web: tuple[str, int] = ("127.0.0.1", 13000)
    unit: tuple[str, int] = ("127.0.0.1", 8767)
    patterns: ClassVar[list[str]] = []

    def _client_origin(self) -> str:
        return f"http://{self.headers.get('Host') or 'localhost'}"

    def _headers_for(self, target: str) -> dict[str, str]:
        host, port = self.web if target == "web" else self.unit
        upstream_origin = f"http://{host}:{port}"
        client_origin = self._client_origin()
        out: dict[str, str] = {}
        for name, value in self.headers.items():
            lname = name.lower()
            if lname in HOP_BY_HOP:
                continue
            if lname == "cookie" and target == "unit":
                continue  # Caddy's header_up -Cookie
            if target == "unit":
                if lname == "host":
                    value = f"{host}:{port}"
                elif lname == "origin":
                    value = upstream_origin
                elif lname == "referer" and value.startswith(client_origin):
                    value = upstream_origin + value[len(client_origin) :]
            out[name] = value
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
        target, path = route(self.path, self.patterns)
        if target == "404":
            return self._answer(404, "Not Found")
        if target == "no-api":
            return self._answer(502, "the workbench runs no AIA API")
        host, port = self.web if target == "web" else self.unit
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        conn = http.client.HTTPConnection(host, port, timeout=600)
        try:
            conn.request(self.command, path, body=body, headers=self._headers_for(target))
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
    ap.add_argument("--unit", default="127.0.0.1:8767")
    ap.add_argument("--caddyfile", default=str(CADDYFILE))
    args = ap.parse_args(argv)
    Facade.web, Facade.unit = _hostport(args.web), _hostport(args.unit)
    Facade.patterns = web_paths(Path(args.caddyfile).read_text(encoding="utf-8"))
    listen = _hostport(args.listen)
    srv = ThreadingHTTPServer(listen, Facade)
    print(
        f"[facade] http://{listen[0]}:{listen[1]}/ -> web {args.web}, unit {args.unit}", flush=True
    )
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
