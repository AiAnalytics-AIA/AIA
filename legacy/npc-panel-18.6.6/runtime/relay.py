#!/usr/bin/env python3
"""Loopback relay for the NPC Panel reference server.

ui_server.py is a localhost desktop application: it binds 127.0.0.1 and its
``_guard_origin()`` rejects mutating requests whose ``Origin`` is not its own
loopback address ("Cross-origin request blocked. NPC backend přijímá změny
pouze ze svého lokálního UI."). Docker publishes ports on the container
interface, and a browser on the host sends ``Origin: http://localhost:8765``,
so a plain TCP relay (socat) makes every POST fail.

This relay listens on the container interface and forwards each request to
the server on loopback with ``Host``, ``Origin`` and ``Referer`` rewritten to
the server's own address. From the server's point of view every request comes
from its local UI, exactly as when the batch launcher opened the browser on
the same machine. ``Location`` headers on the way back are rewritten to the
address the browser used.

Standard library only. Usage:

    relay.py --listen 172.17.0.2:8765 --upstream 127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import http.client
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}
CHUNK = 64 * 1024


class Relay(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    upstream_host = "127.0.0.1"
    upstream_port = 8765

    # -- helpers ------------------------------------------------------------
    @property
    def upstream_origin(self) -> str:
        return f"http://{self.upstream_host}:{self.upstream_port}"

    def _client_origin(self) -> str:
        host = self.headers.get("Host") or f"localhost:{self.server.server_address[1]}"
        return f"http://{host}"

    def _rewrite_request_headers(self) -> dict[str, str]:
        out: dict[str, str] = {}
        client_origin = self._client_origin()
        for name, value in self.headers.items():
            lname = name.lower()
            if lname in HOP_BY_HOP:
                continue
            if lname == "host":
                value = f"{self.upstream_host}:{self.upstream_port}"
            elif lname == "origin":
                value = self.upstream_origin
            elif lname == "referer" and value.startswith(client_origin):
                value = self.upstream_origin + value[len(client_origin):]
            out[name] = value
        out["Connection"] = "close"
        return out

    def _rewrite_response_header(self, name: str, value: str) -> str:
        if name.lower() == "location" and value.startswith(self.upstream_origin):
            return self._client_origin() + value[len(self.upstream_origin):]
        return value

    # -- the relay ----------------------------------------------------------
    def _relay(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        conn = http.client.HTTPConnection(self.upstream_host, self.upstream_port, timeout=600)
        try:
            conn.request(self.command, self.path, body=body, headers=self._rewrite_request_headers())
            resp = conn.getresponse()
        except (ConnectionRefusedError, socket.timeout, OSError) as exc:
            self.send_error(502, f"upstream {self.upstream_origin} unavailable: {exc}")
            conn.close()
            return

        self.send_response(resp.status, resp.reason)
        chunked = False
        for name, value in resp.getheaders():
            lname = name.lower()
            if lname in HOP_BY_HOP:
                chunked = chunked or (lname == "transfer-encoding" and "chunked" in value.lower())
                continue
            self.send_header(name, self._rewrite_response_header(name, value))
        if chunked:
            # http.client de-chunks for us; we stream and close instead.
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()

        if self.command != "HEAD":
            try:
                while True:
                    data = resp.read(CHUNK)
                    if not data:
                        break
                    self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
        conn.close()

    def do_GET(self): self._relay()          # noqa: E704
    def do_POST(self): self._relay()         # noqa: E704
    def do_PUT(self): self._relay()          # noqa: E704
    def do_PATCH(self): self._relay()        # noqa: E704
    def do_DELETE(self): self._relay()       # noqa: E704
    def do_HEAD(self): self._relay()         # noqa: E704
    def do_OPTIONS(self): self._relay()      # noqa: E704

    def log_message(self, fmt, *args):  # quiet: the server logs its own requests
        if args and str(args[1:2]).startswith("('5"):
            sys.stderr.write("[relay] " + fmt % args + "\n")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listen", required=True, help="ip:port to listen on (container interface)")
    ap.add_argument("--upstream", default="127.0.0.1:8765", help="ip:port of ui_server.py")
    args = ap.parse_args(argv)

    lhost, _, lport = args.listen.rpartition(":")
    uhost, _, uport = args.upstream.rpartition(":")
    Relay.upstream_host, Relay.upstream_port = uhost, int(uport)

    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer.daemon_threads = True
    srv = ThreadingHTTPServer((lhost, int(lport)), Relay)
    print(f"[relay] {lhost}:{lport} -> http://{uhost}:{uport} (Host/Origin/Referer rewritten)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
