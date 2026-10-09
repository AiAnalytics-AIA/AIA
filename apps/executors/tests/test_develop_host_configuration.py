"""The develop host's own configuration passes the API's and the worker's startup checks.

Each process validated its settings in its own tests, but nothing ran those checks
against what ``deploy/develop/docker-compose.yml`` actually hands the containers. PR
#108 made the API refuse ``AIA_AI_FICTIONAL_CLIENT_IDS`` in ``staging`` while the host
ran as ``staging`` with fictional clients set; CI was green and every deploy from
2026-10-02 failed its health check. These tests read the Compose file, fill it with
values shaped like the host's Parameter Store entries (``bin/write-env.sh``), and start
both checks on the result.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
from aia_executors.ai_runtime import AIRuntimeSettings

api_config: Any = pytest.importorskip(
    "aia_api.config", reason="the API's settings live in apps/api"
)

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = (ROOT / "deploy" / "develop" / "docker-compose.yml").read_text(encoding="utf-8")

#: The host's .env, shaped like Parameter Store's /aia/develop/* (illustrative ids and
#: test prices, not Bedrock's): the AI runtime on, and the seed's fictional clients named,
#: as deploy/develop/README.md § the AI runtime configures them.
HOST_ENV = {
    "AWS_REGION": "eu-central-1",
    "POSTGRES_PASSWORD": "generated-secret",
    "AIA_STORAGE_BUCKET": "aia-develop-artifacts-123456789012",
    "AIA_COGNITO_USER_POOL_ID": "eu-central-1_XXXXXXXXX",
    "AIA_COGNITO_CLIENT_ID": "app-client",
    "AIA_AI_RUNTIME_ENABLED": "true",
    "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
    "AIA_BEDROCK_REGION": "eu-central-1",
    "AIA_BEDROCK_MODEL_ID": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "AIA_AI_POLICY_VERSION": "aia-model-policy-test-1",
    "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
    "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
    "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
    "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
    "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
    "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
    "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL",
    "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
    "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
    "AIA_AI_FICTIONAL_CLIENT_IDS": "CLI-fictional-a,CLI-fictional-b",
}

#: Baked into each image by the deploy (deploy/docker/python.Dockerfile), not Compose.
IMAGE_ENV = {"AIA_BUILD_SHA": "056eca2ea9cb12f717ad698a3f95e9d00d916ff8"}

_ENTRY = re.compile(r"^\s+([A-Z][A-Z0-9_]*):\s*(.*?)\s*$")
_VARIABLE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::-([^}]*))?\}")


def _entries(lines: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in lines:
        match = _ENTRY.match(line)
        if match:
            found[match.group(1)] = match.group(2).strip('"')
    return found


def _service_environment(service: str) -> dict[str, str]:
    """The ``environment:`` of one service, with ``<<: *app-env`` merged under it."""
    anchor = COMPOSE.split("x-app-env: &app-env\n", 1)[1].split("\n\n", 1)[0]
    block = re.split(r"\n  [a-z][a-z-]*:\n", COMPOSE.split(f"\n  {service}:\n", 1)[1], maxsplit=1)[
        0
    ]
    own: list[str] = []
    for line in block.split("    environment:\n", 1)[1].splitlines():
        if not line.startswith("      "):  # the mapping ends at the next service key
            break
        own.append(line)
    merged = _entries(anchor.splitlines())
    merged.update(_entries(own))
    return merged


def _interpolate(values: dict[str, str], dotenv: dict[str, str]) -> dict[str, str]:
    """Compose's ``${VAR}`` and ``${VAR:-default}`` (default when unset or empty)."""

    def one(match: re.Match[str]) -> str:
        value = dotenv.get(match.group(1), "")
        return value if value else (match.group(2) or "")

    return {key: _VARIABLE.sub(one, value) for key, value in values.items()}


def _container(service: str, dotenv: dict[str, str]) -> dict[str, str]:
    return {**IMAGE_ENV, **_interpolate(_service_environment(service), dotenv)}


def _api_settings(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> Any:
    for key in [k for k in os.environ if k.startswith("AIA_") or k == "DATABASE_URL"]:
        monkeypatch.delenv(key)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return api_config.Settings(_env_file=None)


def test_the_api_and_the_worker_both_run_as_develop() -> None:
    assert _container("api", HOST_ENV)["AIA_ENV"] == "develop"
    assert _container("worker", HOST_ENV)["AIA_ENV"] == "develop"


def test_the_api_starts_with_the_develop_hosts_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _container("api", HOST_ENV)
    assert env["AIA_AI_FICTIONAL_CLIENT_IDS"] == HOST_ENV["AIA_AI_FICTIONAL_CLIENT_IDS"]
    settings = _api_settings(env, monkeypatch)
    assert settings.is_production  # every deployed-environment guard ran
    settings.validate_for_production()


def test_the_worker_starts_its_ai_runtime_with_the_develop_hosts_configuration() -> None:
    settings = AIRuntimeSettings.from_env(_container("worker", HOST_ENV))
    assert settings is not None


def test_the_same_configuration_under_staging_is_refused_by_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sensitive to the fault #108 shipped: fictional clients where they are refused."""
    api = {**_container("api", HOST_ENV), "AIA_ENV": "staging"}
    with pytest.raises(RuntimeError, match="AIA_AI_FICTIONAL_CLIENT_IDS is refused in staging"):
        _api_settings(api, monkeypatch).validate_for_production()
    worker = {**_container("worker", HOST_ENV), "AIA_ENV": "staging"}
    with pytest.raises(RuntimeError, match="AIA_AI_FICTIONAL_CLIENT_IDS is refused in staging"):
        AIRuntimeSettings.from_env(worker)


#: Brave on, as Parameter Store would carry it (chunk 23f): the key a SecureString, the
#: price and its date plain. A fictional key, never a real one.
BRAVE_ENV = {
    **HOST_ENV,
    "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
    "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
    "AIA_AI_RESEARCH_RESERVATION_USD": "1.5",
    "AIA_DEEP_RESEARCH_ENABLED": "true",
    "AIA_DEEP_RESEARCH_WEB_SEARCH": "brave",
    "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": "research@aia.example",
    "AIA_DEEP_RESEARCH_BRAVE_API_KEY": "fictional-brave-key-0000",
    "AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000": "5",
    "AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF": "2026-10-09",
}


def test_brave_composes_from_the_hosts_env_file_and_its_key_reaches_the_worker_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aia_executors.deep_research_runtime import deep_research_runtime

    worker = _container("worker", BRAVE_ENV)
    runtime = deep_research_runtime(AIRuntimeSettings.from_env(worker), env=worker)
    assert runtime is not None and runtime.retrieval is not None
    assert runtime.retrieval.search_route.route_id == "brave-web-search"
    assert runtime.sign_off_routes() == ("brave-web-search",)
    for service in ("api", "web", "caddy", "postgres"):
        assert "AIA_DEEP_RESEARCH_BRAVE_API_KEY" not in _container(service, BRAVE_ENV)
    api = _api_settings(_container("api", BRAVE_ENV), monkeypatch)
    assert (api.deep_research_web_search, api.deep_research_brave_usd_per_1000) == ("brave", 5.0)


def test_with_brave_unset_the_develop_host_composes_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every new key passes through Compose empty, and empty is unset in both processes."""
    from aia_executors.deep_research_runtime import web_search

    worker = _container("worker", HOST_ENV)
    assert worker["AIA_DEEP_RESEARCH_WEB_SEARCH"] == "" and web_search(worker) == "off"
    api = _api_settings(_container("api", HOST_ENV), monkeypatch)
    assert (api.deep_research_web_search, api.deep_research_brave_usd_per_1000) == ("", None)


def test_common_crawl_composes_from_the_hosts_env_file_and_the_api_prices_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chunk 23e: every Common Crawl key reaches the worker; the switch and the four price keys
    reach the API, which prices the index query as the worker reserves it."""
    from aia_executors.deep_research_runtime import deep_research_runtime

    crawl_env = {
        **{k: v for k, v in BRAVE_ENV.items() if "BRAVE" not in k},
        "AIA_DEEP_RESEARCH_WEB_SEARCH": "wikipedia",
        "AIA_DEEP_RESEARCH_AGENT_DIRECTED": "true",
        "AIA_DEEP_RESEARCH_COMMON_CRAWL": "true",
        "AIA_DEEP_RESEARCH_COMMON_CRAWL_WORKGROUP": "aia-ccindex",
        "AIA_DEEP_RESEARCH_COMMON_CRAWL_DATABASE": "ccindex",
        "AIA_DEEP_RESEARCH_COMMON_CRAWL_TABLE": "ccindex",
        "AIA_DEEP_RESEARCH_COMMON_CRAWL_MAX_SCAN_BYTES": "1000000000",
        "AIA_DEEP_RESEARCH_COMMON_CRAWL_USD_PER_TB_SCANNED": "5",
        "AIA_DEEP_RESEARCH_COMMON_CRAWL_MIN_BILLED_BYTES": "10485760",
        "AIA_DEEP_RESEARCH_COMMON_CRAWL_BILLING_INCREMENT_BYTES": "1048576",
        "AIA_DEEP_RESEARCH_COMMON_CRAWL_PRICES_AS_OF": "2026-10-09",
        "AIA_DEEP_RESEARCH_COMMON_CRAWL_CRAWLS": "CC-MAIN-2026-35",
    }
    worker = _container("worker", crawl_env)
    runtime = deep_research_runtime(AIRuntimeSettings.from_env(worker), env=worker)
    assert runtime is not None and runtime.archive is not None
    api = _api_settings(_container("api", crawl_env), monkeypatch)
    assert api.deep_research_common_crawl is True
    assert api.deep_research_common_crawl_max_scan_bytes == 1_000_000_000
    for service in ("api", "web"):
        assert "AIA_DEEP_RESEARCH_COMMON_CRAWL_WORKGROUP" not in _container(service, crawl_env)
