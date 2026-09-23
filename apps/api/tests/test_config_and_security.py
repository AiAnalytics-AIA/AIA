"""Tests for configuration guards, secret redaction and the auth seam.

These cover the failure modes that are cheap to get wrong and expensive to
discover in production: a service booting with development settings, a provider
key reaching the log stream, or header-based identity being trusted for real.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aia_api.config import Environment, Settings
from aia_api.dependencies import build_identity_provider
from aia_api.identity import DevelopmentIdentityForbidden
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


PRODUCTION_OK: dict[str, Any] = {
    "env": Environment.PRODUCTION,
    "database_url": "postgresql+psycopg://user:pw@host/aia",
    "cors_origins": ["https://app.example.com"],
    "identity_provider": "cognito",
    "cognito_region": "eu-central-1",
    "cognito_user_pool_id": "eu-central-1_Pool",
    "cognito_client_id": "app-client",
    "build_sha": "a15be650937aacaa821db783c7eff6b9ab40cbe9",
    "storage_backend": "s3",
    "storage_bucket": "aia-develop-artifacts",
    "storage_region": "eu-central-1",
}


def test_valid_production_config_passes() -> None:
    """A correct production configuration validates cleanly."""
    Settings(**PRODUCTION_OK).validate_for_production()


def test_staging_applies_the_same_guards_as_production() -> None:
    """The develop host runs with AIA_ENV=staging precisely to exercise these guards."""
    Settings(**{**PRODUCTION_OK, "env": Environment.STAGING}).validate_for_production()
    with pytest.raises(RuntimeError, match="identity_provider must be 'cognito'"):
        Settings(
            **{**PRODUCTION_OK, "env": Environment.STAGING, "identity_provider": "development"}
        ).validate_for_production()


def test_production_requires_the_build_sha() -> None:
    """A deployment that cannot say which revision it is cannot be debugged or rolled back."""
    with pytest.raises(RuntimeError, match="AIA_BUILD_SHA is required"):
        Settings(**{**PRODUCTION_OK, "build_sha": ""}).validate_for_production()


def test_a_malformed_build_sha_is_refused_at_construction() -> None:
    """A branch name in the revision slot is a broken build step, not a revision."""
    with pytest.raises(ValueError, match="AIA_BUILD_SHA"):
        Settings(env=Environment.LOCAL, build_sha="develop")


def test_production_requires_s3_storage_without_an_endpoint_override() -> None:
    """Memory vanishes with the container; a filesystem is unshared with the worker;
    an endpoint override points at something that is not S3."""
    with pytest.raises(RuntimeError, match="AIA_STORAGE_BACKEND must be 's3'"):
        Settings(**{**PRODUCTION_OK, "storage_backend": "memory"}).validate_for_production()
    with pytest.raises(RuntimeError, match="AIA_STORAGE_ENDPOINT must not be set"):
        Settings(
            **{**PRODUCTION_OK, "storage_endpoint": "http://minio:9000"}
        ).validate_for_production()
    with pytest.raises(RuntimeError, match="AIA_STORAGE_BUCKET is required"):
        Settings(**{**PRODUCTION_OK, "storage_bucket": ""}).validate_for_production()


def test_local_config_may_keep_artifacts_in_memory() -> None:
    """Local development needs no bucket."""
    settings = Settings(env=Environment.LOCAL)
    settings.validate_for_production()
    assert settings.storage_settings().backend == "memory"


def test_production_refuses_a_non_cognito_identity_provider() -> None:
    """A deployed environment must authenticate through Cognito.

    Header-trusting identity in a deployment would make every organization,
    client and study boundary meaningless, so it is refused at startup.
    """
    for provider in ("development", "test"):
        with pytest.raises(RuntimeError, match="identity_provider must be 'cognito'"):
            Settings(
                env=Environment.PRODUCTION,
                database_url="postgresql+psycopg://u:p@h/aia",
                identity_provider=provider,
            ).validate_for_production()


def test_production_refuses_incomplete_cognito_configuration() -> None:
    """A half-configured pool would reject every token; fail at startup instead."""
    with pytest.raises(RuntimeError, match="Cognito configuration is incomplete"):
        Settings(
            env=Environment.PRODUCTION,
            database_url="postgresql+psycopg://u:p@h/aia",
            identity_provider="cognito",
            cognito_region="eu-central-1",
        ).validate_for_production()


def test_insecure_local_identity_is_granted_only_locally() -> None:
    """The single switch that permits header-based identity.

    DevelopmentIdentityProvider refuses to construct without it, so this property
    is what stands between header-trust and a deployed environment.
    """
    assert Settings(env=Environment.LOCAL).allow_insecure_local_identity
    assert Settings(env=Environment.TEST).allow_insecure_local_identity
    assert not Settings(env=Environment.STAGING).allow_insecure_local_identity
    assert not Settings(env=Environment.PRODUCTION).allow_insecure_local_identity


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


def test_development_identity_provider_cannot_be_built_for_production() -> None:
    """The header-trusting provider refuses construction outside local/test.

    Two independent barriers exist: this one, and the config guard above. Neither
    relies on the other.
    """
    settings = Settings(
        env=Environment.PRODUCTION,
        database_url="postgresql+psycopg://u:p@h/aia",
        identity_provider="development",
    )
    with pytest.raises(DevelopmentIdentityForbidden):
        build_identity_provider(settings)


def test_local_environment_gets_the_insecure_provider() -> None:
    """Local development works without Cognito, and says so in the provider name."""
    provider = build_identity_provider(
        Settings(env=Environment.LOCAL, identity_provider="development")
    )
    assert provider.name == "development-insecure"


def test_cognito_provider_is_built_from_config() -> None:
    """Production configuration produces a Cognito provider."""
    provider = build_identity_provider(
        Settings(
            env=Environment.PRODUCTION,
            database_url="postgresql+psycopg://u:p@h/aia",
            identity_provider="cognito",
            cognito_region="eu-central-1",
            cognito_user_pool_id="eu-central-1_Pool",
            cognito_client_id="app-client",
        )
    )
    assert provider.name == "cognito"


def test_missing_credentials_are_rejected(client: TestClient, world: Any) -> None:
    """An unauthenticated request is refused with a bearer challenge."""
    path = f"/api/v1/studies/{world.study_id()}/projects"

    response = client.get(path)
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_malformed_authorization_header_is_rejected(client: TestClient, world: Any) -> None:
    """Only the bearer scheme is accepted, and it must carry a value."""
    path = f"/api/v1/studies/{world.study_id()}/projects"

    for header in ("Bearer", "Bearer   ", "Basic dXNlcjpwYXNz", "token abc"):
        response = client.get(path, headers={"Authorization": header})
        assert response.status_code == 401, header


def test_header_identity_is_ignored_when_a_bearer_token_is_present(
    client: TestClient, world: Any
) -> None:
    """A bearer token wins, so a stray dev header cannot override a real session."""
    path = f"/api/v1/studies/{world.study_id()}/projects"
    response = client.get(
        path,
        headers={"Authorization": "Bearer nonexistent", "X-AIA-Subject": "lead@art-chain.io"},
    )
    assert response.status_code == 401


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


def test_error_response_details_are_redacted(researcher: TestClient, world: Any) -> None:
    """Validation errors echo input, so that echo must be scrubbed."""
    response = researcher.post(
        f"/api/v1/studies/{world.study_id()}/projects",
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
