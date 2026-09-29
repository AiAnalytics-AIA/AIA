"""The UI workbench's facade routes like the develop Caddyfile (tools/ui_workbench).

The workbench is a local design tool, but it must route the way the product
hostname does: the API on /api/v1, the web client for everything else -- the
18.6.6 unit's old paths among them, which reach nothing of the unit (ADR 0018).
The web client's matchers are read from the committed Caddyfile, so a Caddyfile
that stopped sending AIA's pages to the web client fails here. These tests pin
the parse against the real file and drive the facade against local stubs.
"""

from __future__ import annotations

import http.client
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
CADDYFILE = (REPO / "deploy" / "develop" / "Caddyfile").read_text()
PATTERNS: list[str] = facade.web_paths(CADDYFILE)
# The paths the unit answered on the product hostname before ADR 0018.
UNIT_PATHS = (
    "/api/bootstrap",
    "/files/x",
    "/artifacts/x",
    "/project-attachments/x",
    "/brand/logo.svg",
    "/fullsim-arena",
    "/health",
    "/status",
)


def test_the_web_matcher_is_read_from_the_committed_caddyfile() -> None:
    for expected in ("/login", "/_next/*", "/skin/*", "/studies", "/studies/*", "/version"):
        assert expected in PATTERNS
    # The rebuilt interface (ADR 0014), from its own gated matcher.
    assert "/app" in PATTERNS and "/app/*" in PATTERNS


def test_a_caddyfile_without_the_matcher_is_refused() -> None:
    with pytest.raises(ValueError, match="/_next/"):
        facade.web_paths("example.test {\n\treverse_proxy web:3000\n}\n")


def test_the_facade_knows_no_unit() -> None:
    # The Caddyfile routes nothing to the unit, so neither may the facade.
    source = FACADE_PATH.read_text(encoding="utf-8")
    assert "legacy-panel" not in source and "8767" not in source


@pytest.mark.parametrize(
    ("path", "target", "upstream"),
    [
        # AIA is the front door (ADR 0015); the 18.6.6 interface is not served
        # (ADR 0018): /classic is the web client's own page, the old document its 404.
        ("/", "redirect", "/app/clients"),
        ("/?lang=cs", "redirect", "/app/clients"),
        ("/classic", "web", "/classic"),
        ("/interface-document", "web", "/interface-document"),
        ("/api/v1/workspace/clients", "api", "/api/v1/workspace/clients"),
        # The unit's old paths are the web client's, like any other (ADR 0018).
        ("/api/bootstrap", "web", "/api/bootstrap"),
        ("/brand/logo.svg", "web", "/brand/logo.svg"),
        ("/skin/fonts/IBMPlexSans-Regular.woff2", "web", "/skin/fonts/IBMPlexSans-Regular.woff2"),
        ("/_next/static/x.js", "web", "/_next/static/x.js"),
        ("/studies", "web", "/studies"),
        ("/app", "web", "/app"),
        (
            "/app/clients/CLI-1/research/STU-1/brief",
            "web",
            "/app/clients/CLI-1/research/STU-1/brief",
        ),
        # Anything else is the web client's (its 404).
        ("/studies-archive", "web", "/studies-archive"),
        ("/apps", "web", "/apps"),
        ("/workbench/sign-in", "sign-in", "/workbench/sign-in"),
    ],
)
def test_routes_like_the_product_hostname(path: str, target: str, upstream: str) -> None:
    assert facade.route(path) == (target, upstream)


def test_sign_in_puts_the_operators_session_in_the_tab_and_opens_the_directory() -> None:
    page = facade.sign_in_page("workbench@example.invalid")
    stored = page.split("sessionStorage.setItem('aia.session', ", 1)[1].split(");", 1)[0]
    session = json.loads(json.loads(stored))
    assert session["idToken"] == "workbench@example.invalid"
    assert set(session) == {"idToken", "refreshToken", "expiresAt", "email", "subject"}
    assert "location.replace('/app/clients')" in page


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
    api = _serve(type("Api", (_Echo,), {"name": "api"}))
    handler = type(
        "F",
        (facade.Facade,),
        {"web": web.server_address[:2], "api": api.server_address[:2]},
    )
    front = _serve(handler)
    yield int(front.server_address[1])
    for srv in (front, web, api):
        srv.shutdown()


def _get(port: int, path: str, headers: dict[str, str] | None = None) -> dict[str, object]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())  # type: ignore[no-any-return]


def test_the_root_is_a_redirect_to_the_client_directory(running: int) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", running, timeout=10)
    conn.request("GET", "/")
    resp = conn.getresponse()
    assert (resp.status, resp.getheader("Location")) == (302, "/app/clients")
    conn.close()


def test_classic_is_the_web_clients_own_page(running: int) -> None:
    got = _get(running, "/classic", {"Cookie": "aia_session=x"})
    assert got["upstream"] == "web" and got["path"] == "/classic"


def test_the_aia_api_gets_the_callers_credential(running: int) -> None:
    got = _get(running, "/api/v1/workspace/clients", {"Authorization": "Bearer a@example.invalid"})
    assert got["upstream"] == "api" and got["path"] == "/api/v1/workspace/clients"
    assert got["headers"]["Authorization"] == "Bearer a@example.invalid"  # type: ignore[index]


def test_an_unknown_path_is_the_web_clients(running: int) -> None:
    assert _get(running, "/studies-archive")["upstream"] == "web"


@pytest.mark.parametrize("path", UNIT_PATHS)
def test_the_units_old_paths_are_the_web_clients(running: int, path: str) -> None:
    assert _get(running, path)["upstream"] == "web"


def test_without_an_api_its_paths_answer_502() -> None:
    handler = type("F", (facade.Facade,), {"web": ("127.0.0.1", 9), "api": None})
    front = _serve(handler)
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(int(front.server_address[1]), "/api/v1/health")
    front.shutdown()
    assert err.value.code == 502


def test_the_old_document_path_goes_to_the_web_client(running: int) -> None:
    # The web client has no such page any more: its 404, never the unit's document.
    assert _get(running, "/interface-document")["upstream"] == "web"


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
    handler = type("F", (facade.Facade,), {"web": srv.getsockname()[:2]})
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


@pytest.mark.parametrize(
    "path",
    [
        "/api/providers/claude-code/setup",
        "/api/providers/claude-code/status",
        "/api/settings/api_keys",
        "/api/settings/ai_check",
        "/api/settings/ai_diagnose",
        "/api/settings/anthropic_check",
    ],
)
def test_legacy_connection_requests_reach_no_unit(running: int, path: str) -> None:
    # The retired connection controls (a key saved, a CLI logged in) went with the
    # unit: the paths are the web client's, which has no such page.
    assert facade.route(path + "?x=1") == ("web", path + "?x=1")
    assert _get(running, path)["upstream"] == "web"
