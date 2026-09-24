"""The UI workbench's facade routes like the develop Caddyfile (tools/ui_workbench).

The workbench is a local design tool, but its one routing fact -- which paths the
web client serves -- is read from the committed Caddyfile, so a wrong parse would
quietly show a screen develop never serves. These tests pin the parse against the
real file and drive the facade against two local stubs.
"""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import ClassVar

import pytest

REPO = Path(__file__).resolve().parents[3]
FACADE_PATH = REPO / "tools" / "ui_workbench" / "facade.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ui_workbench_facade", FACADE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


facade = _load()
PATTERNS: list[str] = facade.web_paths((REPO / "deploy" / "develop" / "Caddyfile").read_text())


def test_the_web_matcher_is_read_from_the_committed_caddyfile() -> None:
    for expected in ("/login", "/_next/*", "/skin/*", "/studies", "/studies/*", "/version"):
        assert expected in PATTERNS
    # The rebuilt interface (ADR 0014), from its own gated matcher.
    assert "/app" in PATTERNS and "/app/*" in PATTERNS


def test_a_caddyfile_without_the_matcher_is_refused() -> None:
    with pytest.raises(ValueError, match="/_next/"):
        facade.web_paths("example.test {\n\treverse_proxy web:3000\n}\n")


@pytest.mark.parametrize(
    ("path", "target", "upstream"),
    [
        ("/", "web", "/interface-document"),
        ("/?lang=cs", "web", "/interface-document?lang=cs"),
        ("/interface-document", "404", "/interface-document"),
        ("/api/v1/panel/gate", "no-api", "/api/v1/panel/gate"),
        ("/api/bootstrap", "unit", "/api/bootstrap"),
        ("/skin/skin.css?v=abc", "web", "/skin/skin.css?v=abc"),
        ("/_next/static/x.js", "web", "/_next/static/x.js"),
        ("/studies", "web", "/studies"),
        ("/studies-archive", "unit", "/studies-archive"),
        ("/brand/logo.svg", "unit", "/brand/logo.svg"),
        ("/app", "web", "/app"),
        ("/app/projects?view=demo", "web", "/app/projects?view=demo"),
        ("/apps", "unit", "/apps"),
    ],
)
def test_routes_like_the_product_hostname(path: str, target: str, upstream: str) -> None:
    assert facade.route(path, PATTERNS) == (target, upstream)


class _Echo(BaseHTTPRequestHandler):
    name: ClassVar[str] = ""

    def do_GET(self) -> None:
        body = json.dumps(
            {"upstream": self.name, "path": self.path, "headers": dict(self.headers)}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def _serve(handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture()
def running() -> Iterator[int]:
    web = _serve(type("Web", (_Echo,), {"name": "web"}))
    unit = _serve(type("Unit", (_Echo,), {"name": "unit"}))
    handler = type(
        "F",
        (facade.Facade,),
        {"web": web.server_address[:2], "unit": unit.server_address[:2], "patterns": PATTERNS},
    )
    front = _serve(handler)
    yield int(front.server_address[1])
    for srv in (front, web, unit):
        srv.shutdown()


def _get(port: int, path: str, headers: dict[str, str] | None = None) -> dict[str, object]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())  # type: ignore[no-any-return]


def test_the_document_reaches_the_web_client_with_the_cookie(running: int) -> None:
    got = _get(running, "/", {"Cookie": "aia_session=x"})
    assert got["upstream"] == "web" and got["path"] == "/interface-document"
    assert got["headers"]["Cookie"] == "aia_session=x"  # type: ignore[index]


def test_the_unit_sees_its_own_origin_and_no_cookie(running: int) -> None:
    port = running
    got = _get(
        port,
        "/api/bootstrap",
        {
            "Cookie": "aia_session=x",
            "Origin": f"http://127.0.0.1:{port}",
            "Referer": f"http://127.0.0.1:{port}/",
        },
    )
    headers = got["headers"]
    assert got["upstream"] == "unit"
    assert "Cookie" not in headers  # type: ignore[operator]
    assert headers["Origin"] == f"http://{headers['Host']}"  # type: ignore[index]
    assert headers["Referer"] == f"http://{headers['Host']}/"  # type: ignore[index]


def test_the_direct_document_path_is_not_an_entry(running: int) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(running, "/interface-document")
    assert err.value.code == 404


def test_a_websocket_upgrade_is_tunnelled_to_the_web_client() -> None:
    # `next dev`'s live reload: the upgrade reaches the web client with its
    # Upgrade header intact, and bytes flow both ways afterwards.
    import socket

    seen: dict[str, str] = {}

    def upstream(srv: socket.socket) -> None:
        conn, _ = srv.accept()
        head = b""
        while b"\r\n\r\n" not in head:
            head += conn.recv(1024)
        seen["head"] = head.decode()
        conn.sendall(
            b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n"
        )
        conn.sendall(conn.recv(1024)[::-1])
        conn.close()

    srv = socket.create_server(("127.0.0.1", 0))
    threading.Thread(target=upstream, args=(srv,), daemon=True).start()
    handler = type(
        "F",
        (facade.Facade,),
        {"web": srv.getsockname()[:2], "unit": ("127.0.0.1", 9), "patterns": PATTERNS},
    )
    front = _serve(handler)
    client = socket.create_connection(("127.0.0.1", int(front.server_address[1])), timeout=10)
    client.sendall(
        b"GET /_next/webpack-hmr?id=1 HTTP/1.1\r\nHost: x\r\n"
        b"Upgrade: websocket\r\nConnection: Upgrade\r\n\r\n"
    )
    reply = b""
    while b"\r\n\r\n" not in reply:
        reply += client.recv(1024)
    client.sendall(b"ping")
    echoed = client.recv(1024)
    client.close()
    front.shutdown()
    srv.close()
    assert reply.startswith(b"HTTP/1.1 101")
    assert seen["head"].startswith("GET /_next/webpack-hmr?id=1 HTTP/1.1")
    assert "Upgrade: websocket" in seen["head"]
    assert echoed == b"gnip"


def _standin() -> ModuleType:
    path = REPO / "tools" / "ui_workbench" / "unit_standin.py"
    spec = importlib.util.spec_from_file_location("ui_workbench_unit_standin", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_workbench_unit_can_reach_no_ai_provider(tmp_path: Path) -> None:
    """A signed-in CLI or an API key on the machine must never be used by the workbench."""
    standin = _standin()
    (tmp_path / "BUILD_EDITION.json").write_text(
        json.dumps({"version": "18.6.6", "claude_code_enabled": True}), encoding="utf-8"
    )
    cli = tmp_path / "bin-with-claude"
    cli.mkdir()
    (cli / "claude").write_text("#!/bin/sh\n")
    other = tmp_path / "bin"
    other.mkdir()
    env = {
        "PATH": f"{cli}:{other}",
        "ANTHROPIC_API_KEY": "sk-test",
        "OPENAI_API_KEY": "sk-test",
        "CLAUDE_CODE_OAUTH_TOKEN": "t",
        "HOME": "/root",
    }
    standin.no_ai(tmp_path, env)

    edition = json.loads((tmp_path / "BUILD_EDITION.json").read_text(encoding="utf-8"))
    assert edition["version"] == "18.6.6"  # the rest of the edition is kept
    assert not edition["claude_code_enabled"]
    assert not edition["claude_api_enabled"]
    assert not edition["openai_api_enabled"]
    # An empty list would mean "all three" to edition_config.allowed_providers.
    assert edition["allowed_live_providers"] == ["workbench_no_ai"]
    assert env == {"PATH": str(other), "HOME": "/root"}
