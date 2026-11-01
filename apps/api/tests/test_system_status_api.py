"""Settings → Stav systému over HTTP (settings-backends SB4).

The latest smoke run, not ready first; GlitchTip read with a read-only token, not configured
without one, an unreadable GlitchTip said by code; OWNER and ADMIN only; the token never in an
answer.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from aia_core.domain.deploy_smoke import SmokeCheck, SmokeStatus
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.deploy_smoke_repository import record_smoke_run
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from aia_api.config import Settings

API = "/api/v1/settings"
TOKEN = "glitchtip-read-token-0123456789abcdef"


def test_no_smoke_run_kept_reads_null(owner: TestClient) -> None:
    response = owner.get(f"{API}/system-status")
    assert response.status_code == 200 and response.json() == {"latest": None}


def test_the_latest_run_reads_not_ready_first(app: FastAPI, owner: TestClient) -> None:
    now = datetime.now(UTC)
    with create_session_factory(app.state.engine)() as session:
        record_smoke_run(
            session,
            run_id="SMK-1",
            build_sha="aaaaaaa",
            checks=[SmokeCheck("old", SmokeStatus.OK)],
            ran_at=now - timedelta(hours=2),
        )
        record_smoke_run(
            session,
            run_id="SMK-2",
            build_sha="bbbbbbb",
            checks=[
                SmokeCheck("web: / opens AIA", SmokeStatus.OK),
                SmokeCheck("ai: a paid model call", SmokeStatus.NOT_RUNNABLE),
                SmokeCheck("api: /health is ok", SmokeStatus.FAIL),
            ],
            ran_at=now,
        )
        session.commit()
    latest = owner.get(f"{API}/system-status").json()["latest"]
    assert (latest["run_id"], latest["build_sha"]) == ("SMK-2", "bbbbbbb")
    assert (latest["all_ok"], latest["failed"], latest["not_runnable"]) == (False, 1, 1)
    assert [(c["check"], c["status"]) for c in latest["checks"]] == [
        ("api: /health is ok", "FAIL"),
        ("ai: a paid model call", "NOT_RUNNABLE"),
        ("web: / opens AIA", "ok"),
    ]


def test_a_not_ready_activation_row_is_no_pass(app: FastAPI, owner: TestClient) -> None:
    """MP6: a deploy whose checks all passed but whose MVP switches are not all on is not
    all_ok, and the row says which and why, after a failure and before an unrun check."""
    with create_session_factory(app.state.engine)() as session:
        record_smoke_run(
            session,
            run_id="SMK-3",
            build_sha="ccccccc",
            checks=[
                SmokeCheck("web: / opens AIA", SmokeStatus.OK),
                SmokeCheck("ai: a paid model call", SmokeStatus.NOT_RUNNABLE),
                SmokeCheck("activation: analysis -- off", SmokeStatus.NOT_READY),
            ],
            ran_at=datetime.now(UTC),
        )
        session.commit()
    latest = owner.get(f"{API}/system-status").json()["latest"]
    assert (latest["all_ok"], latest["failed"], latest["not_ready"]) == (False, 0, 1)
    assert [c["status"] for c in latest["checks"]] == ["NOT_READY", "NOT_RUNNABLE", "ok"]


def test_a_researcher_reads_neither(researcher: TestClient) -> None:
    for path in ("system-status", "error-tracking"):
        refused = researcher.get(f"{API}/{path}")
        assert refused.status_code == 403 and refused.json()["code"] == "insufficient_role"


def test_without_a_token_error_tracking_is_not_configured(owner: TestClient) -> None:
    body = owner.get(f"{API}/error-tracking").json()
    assert body["configured"] is False and body["error"] is None
    assert body["issues_7d"] == [] and body["alerts"] == [] and body["uptime"] == []
    assert body["uptime_enabled"] is None


def test_with_a_second_organization_both_are_refused_as_the_deployments(
    app: FastAPI, owner: TestClient
) -> None:
    """Smoke results and GlitchTip's issues are every tenant's: an organization's admin reads
    them only while the deployment holds that organization alone."""
    from aia_core.application.develop_seed import SMOKE_ORGANIZATION_SLUG
    from aia_core.infrastructure.scope_repository import ScopeRepository

    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).create_organization(
            slug=SMOKE_ORGANIZATION_SLUG, name="Smoke", owner_email="s@example.invalid"
        )
        session.commit()
    # Outside develop an organization of the seed's name is a tenant like any other.
    assert owner.get(f"{API}/system-status").status_code == 409
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).create_organization(
            slug="tenant-two", name="Tenant two", owner_email="t@example.org"
        )
        session.commit()
    for path in ("system-status", "error-tracking"):
        refused = owner.get(f"{API}/{path}")
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "deployment_shared"
        assert "provozovatel" in refused.json()["message"]


class _Stub(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        recent = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        routes: dict[str, Any] = {
            "/api/0/projects/": [
                {
                    "id": "1",
                    "slug": "backend",
                    "name": "AIA backend",
                    "organization": {"slug": "aia"},
                }
            ],
            "/api/0/projects/aia/backend/issues/?query=is%3Aunresolved": [
                {"id": "7", "title": "Boom", "count": "2", "lastSeen": recent}
            ],
            "/api/0/projects/aia/backend/alerts/": [],
            "/api/0/organizations/aia/monitors/": [{"name": "API", "isUp": False}],
        }
        ok = self.headers.get("Authorization") == f"Bearer {TOKEN}"
        body = routes.get(self.path)
        self.send_response(200 if ok and body is not None else (401 if not ok else 404))
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *_: Any) -> None:
        return


@pytest.fixture
def glitchtip() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


class TestWithAToken:
    """A read-only token configured; the DSN left unset, so no reporter starts in the test."""

    @pytest.fixture
    def settings(self, settings: Settings, glitchtip: str) -> Settings:
        return settings.model_copy(
            update={
                "glitchtip_api_token": SecretStr(TOKEN),
                "glitchtip_api_url": glitchtip,
                "glitchtip_dashboard_url": "https://errors.aia-develop.example",
            }
        )

    def test_glitchtip_is_read_and_the_token_never_answered(self, owner: TestClient) -> None:
        response = owner.get(f"{API}/error-tracking")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["configured"] is True and body["error"] is None
        assert body["dashboard_url"] == "https://errors.aia-develop.example"
        assert body["project"] == "AIA backend"
        assert [(i["title"], i["count"]) for i in body["issues_7d"]] == [("Boom", 2)]
        assert body["uptime"] == [{"name": "API", "is_up": False, "last_change": None}]
        assert body["uptime_enabled"] is True
        assert TOKEN not in response.text
