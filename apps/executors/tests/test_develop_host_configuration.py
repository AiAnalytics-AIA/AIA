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
