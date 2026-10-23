"""GlitchTip read for Settings → Stav systému (settings-backends SB4), against a local stub.

The token is sent as a bearer header only; the last seven days' open issues, the alert rules
and the uptime monitors are read; any failure is a code with what was read before it, never
an exception and never the token.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from aia_core.infrastructure.glitchtip_status import dsn_project_id, read_glitchtip

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
TOKEN = "glitchtip-read-token-0123456789abcdef"

ROUTES: dict[str, Any] = {
    "/api/0/projects/": [
        {"id": "2", "slug": "web", "name": "AIA web", "organization": {"slug": "aia"}},
        {"id": "1", "slug": "backend", "name": "AIA backend", "organization": {"slug": "aia"}},
    ],
    "/api/0/projects/aia/backend/issues/?query=is%3Aunresolved": [
        {
            "id": "11",
            "title": "KeyError: 'x'",
            "culprit": "aia_api.routers.x",
            "count": "4",
            "lastSeen": "2026-10-22T10:00:00Z",
        },
        {"id": "12", "title": "Old", "count": 1, "lastSeen": "2026-10-01T10:00:00Z"},
        {"id": "a/b?c", "title": "Odd id", "lastSeen": "2026-10-22T09:00:00Z"},
        {"id": "13", "title": "No date"},
    ],
    "/api/0/projects/aia/backend/alerts/": [
        {"name": "Any error", "quantity": 1, "timespanMinutes": 10, "alertRecipients": [{}]}
    ],
    "/api/0/organizations/aia/monitors/": [
        {"name": "AIA health", "isUp": True, "lastChange": "2026-10-20T08:00:00Z"},
        {"name": "Unknown", "isUp": None},
    ],
}


class _Stub(BaseHTTPRequestHandler):
    seen: list[tuple[str, str | None]] = []  # noqa: RUF012 -- the test reads it
    routes: dict[str, Any] = ROUTES
    status = 200

    def do_GET(self) -> None:
        type(self).seen.append((self.path, self.headers.get("Authorization")))
        body = type(self).routes.get(self.path)
        code = type(self).status if body is not None else 404
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *_: Any) -> None:
        return


@pytest.fixture
def stub() -> Iterator[str]:
    _Stub.seen = []
    _Stub.routes = dict(ROUTES)
    _Stub.status = 200
    server = HTTPServer(("127.0.0.1", 0), _Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _read(url: str, project: str | None = "1") -> Any:
    return read_glitchtip(
        token=TOKEN,
        api_url=url,
        dashboard_url="https://errors.aia-develop.example/",
        project_id=project,
        now=NOW,
    )


def test_the_dsns_project_is_read_with_the_token_as_a_bearer_only(stub: str) -> None:
    status = _read(stub)
    assert status.error is None
    assert status.project == "AIA backend"
    assert status.project_url == "https://errors.aia-develop.example/aia/issues?project=1"
    assert [i.title for i in status.issues_7d] == ["KeyError: 'x'", "Odd id"]  # 7 days, dated
    issue, odd = status.issues_7d
    assert odd.url == "https://errors.aia-develop.example/aia/issues/a%2Fb%3Fc"
    assert issue.count == 4 and issue.url == "https://errors.aia-develop.example/aia/issues/11"
    assert [(a.name, a.quantity, a.timespan_minutes, a.recipients) for a in status.alerts] == [
        ("Any error", 1, 10, 1)
    ]
    assert [(m.name, m.is_up) for m in status.uptime] == [("AIA health", True), ("Unknown", None)]
    assert status.uptime_enabled is True
    assert {auth for _, auth in _Stub.seen} == {f"Bearer {TOKEN}"}
    assert all(TOKEN not in path for path, _ in _Stub.seen)
    assert TOKEN not in repr(status)


def test_a_refused_token_is_said_by_code_never_raised(stub: str) -> None:
    _Stub.status = 401
    status = _read(stub)
    assert status.error == "glitchtip_refused_token" and status.project is None
    assert TOKEN not in repr(status)


def test_what_was_read_before_a_failure_is_kept(stub: str) -> None:
    del _Stub.routes["/api/0/projects/aia/backend/alerts/"]
    status = _read(stub)
    assert status.error == "glitchtip_http_404"
    assert len(status.issues_7d) == 2 and status.alerts == [] and status.uptime_enabled is None


def test_uptime_switched_off_in_glitchtip_is_said_and_is_no_failure(stub: str) -> None:
    del _Stub.routes["/api/0/organizations/aia/monitors/"]
    status = _read(stub)
    assert status.error is None and status.uptime_enabled is False and status.uptime == []
    assert len(status.issues_7d) == 2 and len(status.alerts) == 1


def test_an_unreachable_glitchtip_is_said() -> None:
    assert _read("http://127.0.0.1:9").error == "glitchtip_unreachable"


def test_an_unexpected_answer_is_said(stub: str) -> None:
    _Stub.routes["/api/0/projects/"] = [{"id": "1", "organization": "aia"}]
    assert _read(stub).error == "glitchtip_unexpected_answer"


def test_the_dsn_names_its_project_by_its_path() -> None:
    assert dsn_project_id("http://key@glitchtip:8000/1") == "1"
    assert dsn_project_id("") is None


class _Elsewhere(BaseHTTPRequestHandler):
    seen: list[str] = []  # noqa: RUF012 -- the test reads it

    def do_GET(self) -> None:
        type(self).seen.append(self.headers.get("Authorization") or "")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"[]")

    def log_message(self, *_: Any) -> None:
        return


def test_a_redirect_is_refused_and_the_token_never_follows_it(stub: str) -> None:
    _Elsewhere.seen = []
    elsewhere = HTTPServer(("127.0.0.1", 0), _Elsewhere)
    threading.Thread(target=elsewhere.serve_forever, daemon=True).start()
    try:

        class _Redirect(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{elsewhere.server_port}/steal")
                self.end_headers()

            def log_message(self, *_: Any) -> None:
                return

        redirecting = HTTPServer(("127.0.0.1", 0), _Redirect)
        threading.Thread(target=redirecting.serve_forever, daemon=True).start()
        try:
            status = _read(f"http://127.0.0.1:{redirecting.server_port}")
        finally:
            redirecting.shutdown()
    finally:
        elsewhere.shutdown()
    assert status.error == "glitchtip_redirect"
    assert _Elsewhere.seen == []


def test_only_an_http_address_is_asked() -> None:
    assert _read("file:///etc/passwd").error == "glitchtip_url_invalid"
