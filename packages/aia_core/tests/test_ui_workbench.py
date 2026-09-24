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
