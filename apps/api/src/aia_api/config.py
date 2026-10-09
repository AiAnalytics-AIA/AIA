"""Application configuration.

All configuration comes from the environment. Nothing here has a production-ready
default that would let the service start up insecurely by accident: secrets have no
defaults at all, and :meth:`Settings.validate_for_production` refuses to run with
development placeholders in a deployed environment (``AIA_ENV`` develop, staging or
production; :mod:`aia_core.domain.deployment` says what each allows).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from aia_core.domain.deployment import DeploymentEnvironment, fictional_material_problem
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.infrastructure.build_identity import BuildIdentity, parse_build_sha
from aia_core.infrastructure.storage_settings import StorageBackend, StorageSettings
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The deployment environment is the domain's, so the API and the worker read one list.
Environment = DeploymentEnvironment


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
    # The experimental Sociomapping (AIA's H-Model candidate) and its internal draft report,
    # added to a research run's graph when the run starts (AIA_SOCIOMAPPING_EXPERIMENTAL_ENABLED).
    # Deterministic, no model call; recorded on the run, so a retry keeps it. Off by default.
    sociomapping_experimental_enabled: bool = False

    # The clients whose studies an administrator may run a *draft* prompt on (ADR 0020). The
    # same variable the worker reads (``AIA_AI_FICTIONAL_CLIENT_IDS``), read here so the API
    # can refuse a draft on any other client before a job exists. Comma-separated client ids;
    # empty (the default) means no draft can be run anywhere. Refused outside local, test and
    # develop, by the same rule the worker applies (aia_core.domain.deployment).
    ai_fictional_client_ids: str = ""

    # What the worker reserves per model request (``AIA_AI_FIELDWORK_RESERVATION_USD``,
    # ``AIA_AI_ANALYSIS_RESERVATION_USD``), read here so the API can say what a run can cost at
    # most before it starts (plan 5b.2). Unset is not zero: the ceiling is then unknown, and a
    # study with a spend limit does not start a run whose ceiling is unknown.
    ai_fieldwork_reservation_usd: float | None = None
    ai_analysis_reservation_usd: float | None = None

    # What a Deep Research run can cost at most (plan deep-research-web-search.md chunk 22),
    # from the same keys the worker composes it from. Each kind of model request reserves
    # what its own window and output limit can cost (domain/deep_research/request_limits.py),
    # derived from the route's prices (``AIA_BEDROCK_*_USD_PER_MTOK``), the model's window
    # (``AIA_BEDROCK_CONTEXT_WINDOW_TOKENS``), the research output limit
    # (``AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS``) and the thinking budget
    # (``AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS``, empty: none). Then whether the public
    # Wikipedia route is on (its search and fetch are free), and the mode switches
    # (``AIA_DEEP_RESEARCH_AGENT_DIRECTED``, ``AIA_DEEP_RESEARCH_LEAD``). A missing price,
    # window or limit is not zero: a study with a spend limit then does not start a Deep
    # Research run. The cache prices are optional, as for the worker: unset, the input rate.
    bedrock_input_usd_per_mtok: float | None = None
    bedrock_output_usd_per_mtok: float | None = None
    bedrock_cache_read_usd_per_mtok: float | None = None
    bedrock_cache_write_usd_per_mtok: float | None = None
    bedrock_context_window_tokens: int | None = None
    ai_research_max_output_tokens: int | None = None
    deep_research_thinking_budget_tokens: int | None = None
    deep_research_wikipedia_enabled: bool = False
    # The search route by name (``AIA_DEEP_RESEARCH_WEB_SEARCH``, chunk 23d): off, wikipedia or
    # brave; empty, the Wikipedia switch decides, as the worker reads it. Brave is priced per
    # request from ``AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000`` (unset: unknown, never free).
    deep_research_web_search: Literal["", "off", "wikipedia", "brave"] = ""
    deep_research_brave_usd_per_1000: float | None = None
    # Common Crawl (``AIA_DEEP_RESEARCH_COMMON_CRAWL``, chunk 23e): each URL index query reserves
    # the workgroup's scan cutoff, billed at the dated Athena price, as the worker composes it.
    # Any key missing: the index's price is unknown, never free. Archived pages are fee-free.
    deep_research_common_crawl: bool = False
    deep_research_common_crawl_max_scan_bytes: int | None = None
    deep_research_common_crawl_usd_per_tb_scanned: float | None = None
    deep_research_common_crawl_min_billed_bytes: int | None = None
    deep_research_common_crawl_billing_increment_bytes: int | None = None
    # The public dataset connectors the worker composes (``AIA_DEEP_RESEARCH_CONNECTORS``,
    # chunk 23b): fee-free, so stated free when listed rather than off. The worker checks
    # the names; here only whether any is listed matters to the ceiling.
    deep_research_connectors: str = ""
    deep_research_agent_directed: bool = False
    deep_research_lead: bool = False

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

    @field_validator(
        "ai_fieldwork_reservation_usd",
        "ai_analysis_reservation_usd",
        "bedrock_input_usd_per_mtok",
        "bedrock_output_usd_per_mtok",
        "bedrock_cache_read_usd_per_mtok",
        "bedrock_cache_write_usd_per_mtok",
        "bedrock_context_window_tokens",
        "ai_research_max_output_tokens",
        "deep_research_thinking_budget_tokens",
        "deep_research_brave_usd_per_1000",
        "deep_research_common_crawl_max_scan_bytes",
        "deep_research_common_crawl_usd_per_tb_scanned",
        "deep_research_common_crawl_min_billed_bytes",
        "deep_research_common_crawl_billing_increment_bytes",
        mode="before",
    )
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
        """True for the deployed environments, which must not run with development defaults."""
        return self.env.is_deployed

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

        # The worker applies the same rule from the same module, so the two cannot disagree.
        fictional = fictional_material_problem(self.env, self.fictional_client_ids)
        if fictional:
            problems.append(fictional)

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
