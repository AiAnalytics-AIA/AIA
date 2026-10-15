"""The error reporter: off without a DSN, and nothing secret leaves when it is on.

The leak tests drive a real ``sentry_sdk`` client over a capturing transport, so what is
asserted is the envelope that would have gone over the wire, after every hook ran.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import pytest

from aia_core.infrastructure import error_tracking
from aia_core.infrastructure.error_tracking import ErrorTrackingSettings
from aia_core.infrastructure.redaction import REDACTED, redact, redact_text

sentry_sdk = pytest.importorskip("sentry_sdk")
from sentry_sdk.transport import Transport  # noqa: E402

DSN = "https://0123abcd@errors.example.test/1"
KEY = "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUv"


class Capture(Transport):
    """Every envelope the client would have sent, kept in memory."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope: Any) -> None:
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


@pytest.fixture
def sent() -> Iterator[list[dict[str, Any]]]:
    """A reporter that is on, for one test; uninstalled after it."""
    transport = Capture()
    settings = ErrorTrackingSettings(
        dsn=DSN, service="worker", environment="test", release="abc123"
    )
    assert error_tracking.init(settings, transport=transport)
    try:
        yield transport.events
    finally:
        error_tracking.close()


def _flat(event: dict[str, Any]) -> str:
    import json

    return json.dumps(event)


# ------------------------------------------------------------------ settings --


def test_no_dsn_is_off_and_installs_nothing() -> None:
    assert ErrorTrackingSettings.from_env("api", {}) is None
    assert ErrorTrackingSettings.from_env("api", {"AIA_ERROR_TRACKING_DSN": "  "}) is None
    assert error_tracking.init(None) is False
    assert not error_tracking.enabled()
    # Every call is a no-op when off.
    error_tracking.report_failure("x", fingerprint=["x"])
    error_tracking.report_exception(RuntimeError("x"))
    error_tracking.set_tags(a="b")
    with error_tracking.tagged(a="b"):
        pass


def test_settings_carry_environment_release_and_service() -> None:
    settings = ErrorTrackingSettings.from_env(
        "worker",
        {"AIA_ERROR_TRACKING_DSN": DSN, "AIA_ENV": "develop", "AIA_BUILD_SHA": "f6f88cb9"},
    )
    assert settings == ErrorTrackingSettings(DSN, "worker", "develop", "f6f88cb9")
    bare = ErrorTrackingSettings.from_env("api", {"AIA_ERROR_TRACKING_DSN": DSN})
    assert bare is not None and (bare.environment, bare.release) == ("local", None)


@pytest.mark.parametrize(
    "dsn", ["errors.example.test", "https://errors.example.test/1", "https://k@h/x", "ftp://k@h/1"]
)
def test_a_malformed_dsn_is_refused_never_ignored(dsn: str) -> None:
    with pytest.raises(ValueError, match="AIA_ERROR_TRACKING_DSN"):
        ErrorTrackingSettings.from_env("api", {"AIA_ERROR_TRACKING_DSN": dsn})


def test_an_internal_dsn_with_a_port_is_accepted() -> None:
    dsn = "http://0123abcd@glitchtip:8000/2"
    settings = ErrorTrackingSettings.from_env("api", {"AIA_ERROR_TRACKING_DSN": dsn})
    assert settings is not None and settings.dsn == dsn


# ----------------------------------------------------------------- reporting --


def test_a_failure_is_one_grouped_labelled_event(sent: list[dict[str, Any]]) -> None:
    error_tracking.report_failure(
        "research_report failed: UNKNOWN",
        fingerprint=["step-failed", "research_report", "UNKNOWN", "analysis_incomplete"],
        tags={"run_id": "r1", "step_kind": "research_report", "absent": None},
        context={"error": {"code": "analysis_incomplete"}},
    )
    (event,) = sent
    assert event["fingerprint"] == [
        "step-failed",
        "research_report",
        "UNKNOWN",
        "analysis_incomplete",
    ]
    assert event["tags"]["service"] == "worker"
    assert event["tags"]["run_id"] == "r1"
    assert "absent" not in event["tags"]
    assert (event["environment"], event["release"]) == ("test", "abc123")
    assert event["contexts"]["failure"] == {"error": {"code": "analysis_incomplete"}}


def test_tagged_scopes_label_what_happens_inside_only(sent: list[dict[str, Any]]) -> None:
    with error_tracking.tagged(step_id="s1"):
        error_tracking.report_failure("inside", fingerprint=["a"])
    error_tracking.report_failure("outside", fingerprint=["b"])
    inside, outside = sent
    assert inside["tags"]["step_id"] == "s1"
    assert "step_id" not in outside["tags"]


def test_an_error_log_line_is_an_event_and_an_info_line_a_breadcrumb(
    sent: list[dict[str, Any]],
) -> None:
    log = logging.getLogger("aia.test.error_tracking")
    log.setLevel(logging.INFO)  # the processes' root level; pytest's is WARNING
    log.info("claimed the step")
    try:
        raise RuntimeError("database went away")
    except RuntimeError:
        log.exception("worker iteration failed")
    (event,) = sent
    assert event["exception"]["values"][-1]["value"] == "database went away"
    messages = [c.get("message") for c in event["breadcrumbs"]["values"]]
    assert "claimed the step" in messages


# ---------------------------------------------------------- nothing leaks --


def test_no_secret_local_body_or_cookie_leaves(sent: list[dict[str, Any]]) -> None:
    def failing(api_key: str, answers: list[str]) -> None:
        respondent_answer = answers[0]  # noqa: F841 -- a local that must never leave
        raise RuntimeError(f"provider refused key {api_key}; Authorization: Bearer {KEY}")

    import sentry_sdk as sdk

    sdk.add_breadcrumb(
        category="httplib",
        data={"url": "https://api.search.brave.com/res/v1/web/search?q=client+secret+plan"},
    )
    with sdk.new_scope() as scope:
        scope.add_event_processor(_with_request)
        try:
            # Built at run time, so the answer is in no source line the event carries.
            failing(KEY, ["".join(["Vol", "il bych stranu X"])])
        except RuntimeError as error:
            error_tracking.report_exception(error, tags={"request_id": "rid-1"})

    (event,) = sent
    flat = _flat(event)
    assert KEY not in flat
    assert "Volil bych" not in flat
    assert "session=abc" not in flat
    assert "body-secret" not in flat
    assert "client+secret+plan" not in flat
    assert "q=" not in flat
    assert REDACTED in event["exception"]["values"][-1]["value"]
    frames = event["exception"]["values"][-1]["stacktrace"]["frames"]
    assert all("vars" not in f for f in frames)
    assert event["request"] == {
        "method": "POST",
        "url": "https://aia.example.test/api/v1/studies/s/runs",
        "headers": {"User-Agent": "test", "X-Request-ID": "rid-1"},
    }
    (crumb,) = [c for c in event["breadcrumbs"]["values"] if c.get("category") == "httplib"]
    assert crumb["data"]["url"] == "https://api.search.brave.com/res/v1/web/search"
    assert event["tags"]["request_id"] == "rid-1"


def _with_request(event: dict[str, Any], _hint: Any) -> dict[str, Any]:
    # What the Starlette integration attaches to a request's event.
    event["request"] = {
        "method": "POST",
        "url": "https://aia.example.test/api/v1/studies/s/runs?token=abcdefghijklmnop",
        "query_string": "token=abcdefghijklmnop",
        "headers": {
            "User-Agent": "test",
            "X-Request-ID": "rid-1",
            "Authorization": f"Bearer {KEY}",
            "Cookie": "session=abc",
        },
        "cookies": {"session": "abc"},
        "data": {"note": "body-secret"},
        "env": {"REMOTE_ADDR": "10.0.0.1"},
    }
    return event


def test_scrub_event_is_safe_on_a_bare_event() -> None:
    assert error_tracking.scrub_event({"message": f"key {KEY}"}) == {"message": f"key {REDACTED}"}
    assert error_tracking.scrub_breadcrumb({"data": {"url": None}}) == {"data": {"url": None}}


# ----------------------------------------------------------------- redaction --


def test_redaction_by_key_and_by_value_shape() -> None:
    assert redact({"nested": {"api_key": "x"}, "note": f"use {KEY}"}) == {
        "nested": {"api_key": REDACTED},
        "note": f"use {REDACTED}",
    }
    assert redact_text("token=abcdefghijklmnop") == f"token={REDACTED}"
    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEifQ.c2lnbmF0dXJlLWJ5dGVz"
    assert redact_text(f"refresh failed for {jwt}") == f"refresh failed for {REDACTED}"
    assert redact_text("x" * 600).endswith("…") and len(redact_text("x" * 600)) == 500
