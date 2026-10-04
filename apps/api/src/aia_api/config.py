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

from aia_core.domain.fieldwork import FieldworkSource
from aia_core.infrastructure.build_identity import BuildIdentity, parse_build_sha
from aia_core.infrastructure.storage_settings import StorageBackend, StorageSettings
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

    # The git commit this process was built from, baked into the image by the
    # deployment. Reported by /health and written into artifact provenance as the
    # runtime version. Required in a deployed environment: a deployment that
    # cannot say which revision it is cannot be debugged or rolled back.
    build_sha: str = ""
    build_time: str = ""

    # ``DATABASE_URL`` is read without the AIA_ prefix because every hosting
    # platform and migration tool already uses that name.
    database_url: str = Field(default="", validation_alias="DATABASE_URL")

    # CORS. Empty means same-origin only, which is the correct default for a
    # deployment that serves the web client behind one hostname.
    cors_origins: list[str] = Field(default_factory=list)

    # -------------------------------------------------------------- storage --
    # Where artifact bytes live. Metadata is always PostgreSQL; this selects the
    # ArtifactStore for the bytes. A deployed environment must use S3 itself.
    storage_backend: StorageBackend = "memory"
    storage_bucket: str = ""
    storage_region: str = ""
    storage_prefix: str = ""
    storage_kms_key_id: str = ""
    storage_endpoint: str = ""
    storage_root: str = "./data/artifacts"

    # ------------------------------------------------------------- identity --
    # Which identity provider answers authentication. "cognito" is the only
    # production-valid value; "development" trusts a request header and is
    # rejected outside local/test by validate_for_production().
    identity_provider: Literal["cognito", "development", "test"] = "development"

    cognito_region: str = ""
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_token_use: Literal["id", "access"] = "id"

    # -------------------------------------------------- research execution --
    # Who answers a research run's questionnaire (ADR 0016 decision 4). The AI
    # runtime is the only deployed source; until it exists a run parks at
    # fieldwork. ``synthetic_fixture`` is a fictional dataset for tests and the
    # workbench, refused in every deployed environment by validate_for_production().
    research_fieldwork_source: FieldworkSource = FieldworkSource.AI_RUNTIME
    ai_analysis_enabled: bool = False

    # The clients whose studies an administrator may run a *draft* prompt on (ADR 0020). The
    # same variable the worker reads (``AIA_AI_FICTIONAL_CLIENT_IDS``), read here so the API
    # can refuse a draft on any other client before a job exists. Comma-separated client ids;
    # empty (the default) means no draft can be run anywhere. Refused in production, as the
    # worker refuses it.
    ai_fictional_client_ids: str = ""

    # What the worker reserves per model request (``AIA_AI_FIELDWORK_RESERVATION_USD``,
    # ``AIA_AI_ANALYSIS_RESERVATION_USD``), read here so the API can say what a run can cost at
    # most before it starts (plan 5b.2). Unset is not zero: the ceiling is then unknown, and a
    # study with a spend limit does not start a run whose ceiling is unknown.
    ai_fieldwork_reservation_usd: float | None = None
    ai_analysis_reservation_usd: float | None = None

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # Request body ceiling. Dataset uploads go through a dedicated upload path with
    # its own limit; this guards ordinary JSON endpoints.
    max_request_bytes: int = 2 * 1024 * 1024

    @field_validator("build_sha", mode="before")
    @classmethod
    def _check_build_sha(cls, value: object) -> object:
        """Refuse a malformed revision rather than record it (ARCHITECTURE.md A5)."""
        if isinstance(value, str):
            return parse_build_sha(value) or ""
        return value

    @field_validator("ai_fieldwork_reservation_usd", "ai_analysis_reservation_usd", mode="before")
    @classmethod
    def _blank_reservation_is_unset(cls, value: object) -> object:
        """A Compose variable passed through empty means "not set", not a number that fails."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string as well as a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def fictional_client_ids(self) -> frozenset[str]:
        """The clients a draft prompt may be tested on; empty means none."""
        return frozenset(c.strip() for c in self.ai_fictional_client_ids.split(",") if c.strip())

    @property
    def build(self) -> BuildIdentity:
        """The build this process runs, or an identity with ``sha=None``."""
        return BuildIdentity(sha=self.build_sha or None, built_at=self.build_time or None)

    def storage_settings(self) -> StorageSettings:
        """The typed storage configuration, shared with the executors' composition root."""
        return StorageSettings(
            backend=self.storage_backend,
            bucket=self.storage_bucket,
            region=self.storage_region,
            prefix=self.storage_prefix,
            kms_key_id=self.storage_kms_key_id,
            endpoint_url=self.storage_endpoint,
            root=self.storage_root,
        )

    @property
    def is_production(self) -> bool:
        """True for the environments that must not run with development defaults."""
        return self.env in (Environment.PRODUCTION, Environment.STAGING)

    @property
    def allow_insecure_local_identity(self) -> bool:
        """Whether header-based identity may be used.

        Granted only in local and test environments. ``DevelopmentIdentityProvider``
        refuses to construct without it, so this property is the single switch
        standing between header-trust and a deployed environment.
        """
        return self.env in (Environment.LOCAL, Environment.TEST)

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
        if not self.build_sha:
            problems.append("AIA_BUILD_SHA is required so the deployed revision is known")

        # Storage. Memory vanishes with the container and a container filesystem
        # is unshared between the API and the worker, so a deployment that is not
        # on S3 would lose every artifact on the first restart.
        try:
            problems.extend(self.storage_settings().deployment_problems())
        except ValueError as exc:
            problems.append(str(exc))

        # Identity. A deployed environment trusting request headers would make
        # every tenant and client boundary meaningless, so this is refused at
        # startup rather than per request.
        if self.identity_provider != "cognito":
            problems.append(
                f"identity_provider must be 'cognito' in production, not '{self.identity_provider}'"
            )
        else:
            missing = [
                name
                for name in ("cognito_region", "cognito_user_pool_id", "cognito_client_id")
                if not getattr(self, name)
            ]
            if missing:
                problems.append("Cognito configuration is incomplete: " + ", ".join(missing))

        if self.fictional_client_ids:
            problems.append(
                "AIA_AI_FICTIONAL_CLIENT_IDS is refused in production: fictional material "
                "does not belong there"
            )

        # Fictional respondents must never become a deployed study's fieldwork (D1).
        if self.research_fieldwork_source is FieldworkSource.SYNTHETIC_FIXTURE:
            problems.append(
                "AIA_RESEARCH_FIELDWORK_SOURCE=synthetic_fixture is refused outside "
                "local and test (ADR 0016)"
            )

        if problems:
            raise RuntimeError("invalid production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
