"""The API reports the 500 a person saw, once, scrubbed, with its request id; never a 4xx.

A real ``sentry_sdk`` client over a capturing transport: what is asserted is the event
that would have gone to GlitchTip.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from aia_core.infrastructure import error_tracking
from aia_core.infrastructure.error_tracking import ErrorTrackingSettings
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from aia_api.config import Environment, Settings
from aia_api.main import create_app

pytest.importorskip("sentry_sdk")
from sentry_sdk.transport import Transport

KEY = "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUv"


class Capture(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope: Any) -> None:
        self.events.extend(i.payload.json for i in envelope.items if i.type == "event")


@pytest.fixture
def reported() -> Iterator[list[dict[str, Any]]]:
    transport = Capture()
    error_tracking.init(
        ErrorTrackingSettings(
            dsn="http://0123abcd@glitchtip:8000/1",
            service="api",
            environment="test",
            release="abc123",
        ),
        transport=transport,
    )
    try:
        yield transport.events
    finally:
        error_tracking.close()


@pytest.fixture
def api(reported: list[dict[str, Any]]) -> Iterator[TestClient]:
    app: FastAPI = create_app(
        Settings(
            env=Environment.TEST,
            database_url="sqlite+pysqlite:///:memory:",
            identity_provider="test",
            log_level="WARNING",
            log_format="console",
        )
    )

    @app.post("/api/v1/studies/{study_id}/boom")
    def boom(study_id: str) -> None:
        raise RuntimeError(f"provider refused {KEY} for study {study_id}")

    @app.get("/api/v1/conflict")
    def conflict() -> None:
        raise HTTPException(409, {"code": "stale", "message": "edited meanwhile"})

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_an_unhandled_exception_is_one_scrubbed_event_with_its_request_id(
    api: TestClient, reported: list[dict[str, Any]]
) -> None:
    response = api.post(
        "/api/v1/studies/S-1/boom?token=abcdefghijklmnop",
        headers={"X-Request-ID": "rid-boom", "Authorization": f"Bearer {KEY}"},
        json={"answer": "body-secret"},
    )
    assert response.status_code == 500

    (event,) = reported
    assert event["tags"]["request_id"] == "rid-boom"
    assert event["tags"]["service"] == "api"
    assert event["exception"]["values"][-1]["type"] == "RuntimeError"
    flat = json.dumps(event)
    assert KEY not in flat
    assert "body-secret" not in flat
    assert "abcdefghijklmnop" not in flat
    assert set(event["request"]["headers"]) <= {"user-agent", "x-request-id"}


def test_a_refusal_is_not_an_issue(api: TestClient, reported: list[dict[str, Any]]) -> None:
    assert api.get("/api/v1/conflict").status_code == 409
    assert api.get("/api/v1/no-such-route").status_code == 404
    assert reported == []


def test_off_without_a_dsn() -> None:
    assert Settings(error_tracking_dsn="").error_tracking is None


def test_a_malformed_dsn_stops_the_api_from_booting() -> None:
    with pytest.raises(ValueError, match="AIA_ERROR_TRACKING_DSN"):
        create_app(Settings(env=Environment.TEST, error_tracking_dsn="glitchtip:8000"))
