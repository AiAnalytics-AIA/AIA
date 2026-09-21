"""Application configuration.

All configuration comes from the environment. Nothing here has a production-ready
default that would let the service start up insecurely by accident: secrets have no
defaults at all, and :meth:`Settings.validate_for_production` refuses to run with
development placeholders when ``AIA_ENV=production``.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment."""

    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Runtime settings, read from the environment or a local ``.env`` file."""

    model_config = SettingsConfigDict(
        env_prefix="AIA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = Environment.LOCAL
    debug: bool = False

    # Service identity, used in logs, traces and the OpenAPI document.
    service_name: str = "aia-api"
    version: str = "0.1.0"

    # ``DATABASE_URL`` is read without the AIA_ prefix because every hosting
    # platform and migration tool already uses that name.
    database_url: str = Field(default="", validation_alias="DATABASE_URL")

    # CORS. Empty means same-origin only, which is the correct default for a
    # deployment that serves the web client behind one hostname.
    cors_origins: list[str] = Field(default_factory=list)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # Request body ceiling. Dataset uploads go through a dedicated upload path with
    # its own limit; this guards ordinary JSON endpoints.
    max_request_bytes: int = 2 * 1024 * 1024

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string as well as a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        """True for the environments that must not run with development defaults."""
        return self.env in (Environment.PRODUCTION, Environment.STAGING)

    @property
    def docs_enabled(self) -> bool:
        """Interactive API docs are served outside production only.

        The OpenAPI document itself is still generated and published as a CI
        artifact, so the schema stays available without exposing a live explorer.
        """
        return self.env is not Environment.PRODUCTION

    def validate_for_production(self) -> None:
        """Fail fast when a production deployment is misconfigured.

        Raised at startup rather than on first request, so a bad deploy fails its
        health check instead of serving traffic in an unsafe state.
        """
        if not self.is_production:
            return

        problems: list[str] = []
        if not self.database_url:
            problems.append("DATABASE_URL is required")
        elif self.database_url.startswith("sqlite"):
            problems.append("SQLite is not a supported production store; use PostgreSQL")
        if self.debug:
            problems.append("AIA_DEBUG must be off in production")
        if "*" in self.cors_origins:
            problems.append("wildcard CORS origin is not permitted in production")

        if problems:
            raise RuntimeError("invalid production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
