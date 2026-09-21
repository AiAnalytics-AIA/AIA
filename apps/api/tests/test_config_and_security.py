"""Tests for configuration guards, secret redaction and the auth seam.

These cover the failure modes that are cheap to get wrong and expensive to
discover in production: a service booting with development settings, a provider
key reaching the log stream, or header-based identity being trusted for real.
"""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from aia_api.config import Environment, Settings
from aia_api.main import create_app
from aia_api.observability import JsonFormatter, redact

# --------------------------------------------------------------------------- #
# Production configuration guards
# --------------------------------------------------------------------------- #


def test_production_requires_a_database_url() -> None:
    """A production service must not boot without a configured store."""
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        Settings(env=Environment.PRODUCTION, database_url="").validate_for_production()


def test_production_refuses_sqlite() -> None:
    """SQLite is unsupported in production: no concurrency, no shared state."""
    settings = Settings(env=Environment.PRODUCTION, database_url="sqlite+pysqlite:///./aia.db")
    with pytest.raises(RuntimeError, match="SQLite is not a supported production store"):
        settings.validate_for_production()


def test_production_refuses_debug_mode() -> None:
    """Debug mode in production leaks internals into responses and logs."""
    settings = Settings(
        env=Environment.PRODUCTION,
        database_url="postgresql+psycopg://u:p@db/aia",
        debug=True,
    )
    with pytest.raises(RuntimeError, match="AIA_DEBUG must be off"):
        settings.validate_for_production()


def test_production_refuses_wildcard_cors() -> None:
    """A wildcard origin with credentials enabled would expose the API to any site."""
    settings = Settings(
        env=Environment.PRODUCTION,
        database_url="postgresql+psycopg://u:p@db/aia",
        cors_origins=["*"],
    )
    with pytest.raises(RuntimeError, match="wildcard CORS origin"):
        settings.validate_for_production()


def test_production_config_reports_every_problem_at_once() -> None:
    """A misconfigured deploy sees all its problems, not just the first."""
    settings = Settings(env=Environment.PRODUCTION, database_url="", debug=True)
    with pytest.raises(RuntimeError) as exc:
        settings.validate_for_production()

    message = str(exc.value)
    assert "DATABASE_URL" in message
    assert "AIA_DEBUG" in message


def test_valid_production_config_passes() -> None:
    """A correct production configuration validates cleanly."""
    Settings(
        env=Environment.PRODUCTION,
        database_url="postgresql+psycopg://user:pw@host/aia",
        cors_origins=["https://app.example.com"],
    ).validate_for_production()


def test_local_config_is_permissive() -> None:
    """Local development must not need production-grade configuration."""
    Settings(env=Environment.LOCAL, debug=True).validate_for_production()


def test_interactive_docs_are_disabled_in_production() -> None:
    """The live API explorer is not exposed in production."""
    assert not Settings(env=Environment.PRODUCTION).docs_enabled
    assert Settings(env=Environment.STAGING).docs_enabled
    assert Settings(env=Environment.LOCAL).docs_enabled


def test_cors_origins_accept_comma_separated_string() -> None:
    """Platform environment variables are strings, not lists."""
    settings = Settings(cors_origins="https://a.example.com, https://b.example.com")
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]


# --------------------------------------------------------------------------- #
# The authentication seam
# --------------------------------------------------------------------------- #


def test_production_refuses_header_based_identity() -> None:
    """Production must not accept a client-supplied identity header.

    Trusting X-AIA-Org in production would let any caller read any tenant's data,
    so the development seam fails closed until a real verifier is wired in.
    """
    app = create_app(
        Settings(
            env=Environment.PRODUCTION,
            database_url="postgresql+psycopg://u:p@localhost/aia",
            log_level="WARNING",
            log_format="console",
        )
    )
    # No lifespan: this must be refused before any database access is attempted.
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/api/v1/projects", headers={"X-AIA-User": "attacker", "X-AIA-Org": "ORG-victim"}
    )

    assert response.status_code == 501
    assert response.json()["code"] == "auth_not_configured"


def test_development_requires_both_identity_headers(client: TestClient) -> None:
    """A partial identity is rejected rather than defaulted."""
    assert client.get("/api/v1/projects", headers={"X-AIA-User": "u"}).status_code == 401
    assert client.get("/api/v1/projects", headers={"X-AIA-Org": "o"}).status_code == 401


# --------------------------------------------------------------------------- #
# Secret redaction
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "API_KEY",
        "apiKey",
        "anthropic_api_key",
        "openai_api_key",
        "secret",
        "client_secret",
        "token",
        "access_token",
        "password",
        "credential",
        "authorization",
        "cookie",
    ],
)
def test_secret_keys_are_redacted(key: str) -> None:
    """Any secret-shaped key is redacted regardless of casing or prefix."""
    assert redact({key: "super-secret-value"})[key] == "[redacted]"


def test_secrets_are_redacted_at_depth() -> None:
    """Redaction reaches nested structures, not just the top level."""
    payload = {
        "project": {
            "settings": [{"api_key": "sk-ant-abcdefghijklmnop"}],
            "title": "safe",
        }
    }
    result = redact(payload)
    assert result["project"]["settings"][0]["api_key"] == "[redacted]"
    assert result["project"]["title"] == "safe"


@pytest.mark.parametrize(
    "text",
    [
        "using sk-ant-api03-ABCDEFGHIJKLMNOP now",
        "key=sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX",
        "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6",
    ],
)
def test_secret_values_are_redacted_inside_free_text(text: str) -> None:
    """A key pasted into an error message is scrubbed too."""
    assert "[redacted]" in redact(text)
    assert "sk-ant-api03-ABCDEFGHIJKLMNOP" not in redact(text)


def test_redaction_is_depth_limited() -> None:
    """A pathologically nested payload cannot hang the logger."""
    payload: dict = {}
    node = payload
    for _ in range(50):
        node["next"] = {}
        node = node["next"]

    result = redact(payload)
    flattened = json.dumps(result)
    assert "[truncated]" in flattened


def test_log_formatter_redacts_and_emits_single_line_json() -> None:
    """Log output is machine-parseable and carries no secrets."""
    record = logging.LogRecord(
        name="aia.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="calling provider",
        args=(),
        exc_info=None,
    )
    record.context = {"api_key": "sk-ant-secret-value", "project_id": "PRJ-1"}  # type: ignore[attr-defined]

    line = JsonFormatter().format(record)

    assert "\n" not in line
    parsed = json.loads(line)
    assert parsed["api_key"] == "[redacted]"
    assert parsed["project_id"] == "PRJ-1"
    assert parsed["message"] == "calling provider"


def test_error_response_details_are_redacted(auth: TestClient) -> None:
    """Validation errors echo input, so that echo must be scrubbed."""
    response = auth.post(
        "/api/v1/projects",
        json={"title": "x", "unexpected_field": "sk-ant-abcdefghijklmnopqrs"},
    )
    assert response.status_code == 422
    assert "sk-ant-abcdefghijklmnopqrs" not in response.text


# --------------------------------------------------------------------------- #
# Database URL normalisation
# --------------------------------------------------------------------------- #


def test_legacy_postgres_scheme_is_rewritten() -> None:
    """Hosting providers still hand out postgres://, which SQLAlchemy 2 rejects."""
    from aia_core.infrastructure.db import resolve_database_url

    assert resolve_database_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert resolve_database_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert resolve_database_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
