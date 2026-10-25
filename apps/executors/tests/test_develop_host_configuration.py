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
from aia_core.domain.residency import DataClass
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
    # The product hostname every host sets (the Caddyfile and the web need it too).
    "AIA_PUBLIC_HOSTNAME": "aia.example.test",
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
    # The Lead's switch is stated, so the deployed guard passes, and it is on (27a, Q43).
    assert settings.ai_research_lead_enabled is True and settings.research_lead_on


def test_the_worker_starts_its_ai_runtime_with_the_develop_hosts_configuration() -> None:
    settings = AIRuntimeSettings.from_env(_container("worker", HOST_ENV))
    assert settings is not None


def test_develop_runs_its_data_class_gates_advisory_in_the_api_and_the_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The product owner, 2026-10-21 (plan develop-class-advisory): fixed in the Compose file,
    whatever Parameter Store holds, and accepted by both processes' startup checks."""
    from aia_core.domain.deployment import DataClassGates
    from aia_worker.settings import WorkerSettings

    for service in ("api", "worker"):
        assert _container(service, HOST_ENV)["AIA_DATA_CLASS_GATES"] == "advisory"
        overridden = {**HOST_ENV, "AIA_DATA_CLASS_GATES": "enforce"}
        assert _container(service, overridden)["AIA_DATA_CLASS_GATES"] == "advisory"
    api = _api_settings(_container("api", HOST_ENV), monkeypatch)
    assert api.data_class_gates is DataClassGates.ADVISORY
    api.validate_for_production()
    worker = _container("worker", HOST_ENV)
    runtime = AIRuntimeSettings.from_env(worker)
    assert runtime is not None and runtime.data_class_gates is DataClassGates.ADVISORY
    process = WorkerSettings.from_env(
        {**worker, "AIA_WORKER_EXECUTORS": "aia_executors.registry:build_registry"}
    )
    assert process.data_class_gates is DataClassGates.ADVISORY


def test_the_develop_deploy_workflow_checks_the_gates_are_advisory() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-develop.yml").read_text(encoding="utf-8")
    assert "grep -qx '  AIA_DATA_CLASS_GATES: advisory' deploy/develop/docker-compose.yml" in (
        workflow
    )


def test_advisory_gates_under_staging_are_refused_by_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Develop's configuration moved to staging or production does not start either process."""
    clean = {k: v for k, v in HOST_ENV.items() if k != "AIA_AI_FICTIONAL_CLIENT_IDS"}
    for env in ("staging", "production"):
        api = {**_container("api", clean), "AIA_ENV": env}
        with pytest.raises(
            RuntimeError, match=f"AIA_DATA_CLASS_GATES=advisory is refused in {env}"
        ):
            _api_settings(api, monkeypatch).validate_for_production()
        worker = {**_container("worker", clean), "AIA_ENV": env}
        with pytest.raises(
            RuntimeError, match=f"AIA_DATA_CLASS_GATES=advisory is refused in {env}"
        ):
            AIRuntimeSettings.from_env(worker)


#: The route widened as deploy/develop/README.md § AI route classes sets it (ADR 0010,
#: amendment 2026-10-19): Classes A, B and C, with the confirmed retention stated.
WIDENED_ENV = {
    **HOST_ENV,
    "AIA_AI_ROUTE_APPROVED_FOR": (
        "CLASS_A_CLIENT_CONFIDENTIAL,CLASS_B_DERIVED_CLIENT,CLASS_C_INTERNAL"
    ),
    "AIA_AI_ROUTE_RETENTION_DAYS": "0",
}


def test_the_route_widened_to_a_b_and_c_starts_both_and_carries_client_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = _container("worker", WIDENED_ENV)
    settings = AIRuntimeSettings.from_env(worker)
    assert settings is not None
    route = settings.route()
    assert route.approved_for == frozenset(DataClass)
    # What ADR 0008 asks of a route before Classes A and B may travel over it.
    assert route.is_eu_processing and route.excluded_from_training
    assert route.has_bounded_retention and route.retention_days == 0
    # Settings shows the classes from the web container's environment (/config).
    web = _container("web", WIDENED_ENV)
    assert web["AIA_AI_ROUTE_APPROVED_FOR"] == WIDENED_ENV["AIA_AI_ROUTE_APPROVED_FOR"]
    _api_settings(_container("api", WIDENED_ENV), monkeypatch).validate_for_production()


def test_widened_without_its_retention_the_route_cannot_carry_client_material() -> None:
    """The runbook's order: the retention is confirmed and set with the classes, never after.
    Without it the worker starts, and the egress check refuses A and B on the route."""
    unset = {k: v for k, v in WIDENED_ENV.items() if k != "AIA_AI_ROUTE_RETENTION_DAYS"}
    settings = AIRuntimeSettings.from_env(_container("worker", unset))
    assert settings is not None
    assert not settings.route().has_bounded_retention


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


#: The Research Lead's own model as Parameter Store would carry it (ADR 0026 amendment,
#: 2026-10-19): an obviously fake id and fake prices, dearer than the route's above.
LEAD_MODEL_ENV = {
    **HOST_ENV,
    "AIA_AI_RESEARCH_LEAD_MODEL_ID": "eu.test.lead-model:1",
    "AIA_AI_RESEARCH_LEAD_INPUT_USD_PER_MTOK": "7",
    "AIA_AI_RESEARCH_LEAD_OUTPUT_USD_PER_MTOK": "11",
    "AIA_AI_RESEARCH_LEAD_MODEL_MAX_OUTPUT_TOKENS": "64000",
    "AIA_AI_RESEARCH_LEAD_CONTEXT_WINDOW_TOKENS": "1000000",
    "AIA_AI_RESEARCH_LEAD_STRUCTURED_OUTPUT": "auto_tool",
    "AIA_AI_RESEARCH_LEAD_THINKING": "adaptive",
    "AIA_AI_RESEARCH_LEAD_EFFORT": "medium",
}


def test_with_the_lead_model_unset_the_lead_runs_on_the_route_model_as_before() -> None:
    worker = _container("worker", HOST_ENV)
    assert worker["AIA_AI_RESEARCH_LEAD_MODEL_ID"] == ""
    settings = AIRuntimeSettings.from_env(worker)
    assert settings is not None and settings.study_lead_configured
    assert settings.lead_model is None
    bindings = settings.model_document()["policies"][0]["bindings"]
    assert bindings["STUDY_LEAD"]["model"] == HOST_ENV["AIA_BEDROCK_MODEL_ID"]


def test_the_lead_models_keys_reach_the_worker_alone_and_its_reservation_must_be_resized() -> None:
    worker = _container("worker", LEAD_MODEL_ENV)
    for key, value in LEAD_MODEL_ENV.items():
        if key.startswith("AIA_AI_RESEARCH_LEAD_"):
            assert worker[key] == value
    for service in ("api", "web"):
        assert "AIA_AI_RESEARCH_LEAD_MODEL_ID" not in _container(service, LEAD_MODEL_ENV)
    # Compose's default reservation is sized at the route's prices: at the dearer Lead model
    # the worker refuses to start, names the key and states the minimum.
    with pytest.raises(RuntimeError, match=r"AIA_AI_RESEARCH_LEAD_RESERVATION_USD.*at least"):
        AIRuntimeSettings.from_env(worker)
    resized = _container("worker", {**LEAD_MODEL_ENV, "AIA_AI_RESEARCH_LEAD_RESERVATION_USD": "2"})
    settings = AIRuntimeSettings.from_env(resized)
    assert settings is not None and settings.study_lead_model is not None
    bindings = settings.model_document()["policies"][0]["bindings"]
    assert bindings["STUDY_LEAD"]["model"] == "eu.test.lead-model:1"
    assert bindings["SIMULATION"]["model"] == HOST_ENV["AIA_BEDROCK_MODEL_ID"]


def test_an_invocation_target_reaches_the_worker_alone_and_unset_changes_nothing() -> None:
    """develop-spend-attribution 5a: the application inference profile chunk 1 will create is
    passed as what the calls go through; the model id stays the eu. id (fictional ARNs)."""
    unset = AIRuntimeSettings.from_env(_container("worker", HOST_ENV))
    assert unset is not None and unset.invocation_target is None
    assert {m.target for m in unset.invocations().values()} == {HOST_ENV["AIA_BEDROCK_MODEL_ID"]}

    arn = "arn:aws:bedrock:eu-central-1:123456789012:application-inference-profile/test0route"
    lead_arn = "arn:aws:bedrock:eu-central-1:123456789012:application-inference-profile/test0lead"
    env = {
        **LEAD_MODEL_ENV,
        "AIA_AI_RESEARCH_LEAD_RESERVATION_USD": "2",
        "AIA_BEDROCK_INVOCATION_TARGET": arn,
        "AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET": lead_arn,
    }
    worker = _container("worker", env)
    assert worker["AIA_BEDROCK_INVOCATION_TARGET"] == arn
    assert worker["AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET"] == lead_arn
    for service in ("api", "web"):
        assert "AIA_BEDROCK_INVOCATION_TARGET" not in _container(service, env)
    settings = AIRuntimeSettings.from_env(worker)
    assert settings is not None and settings.model_id == HOST_ENV["AIA_BEDROCK_MODEL_ID"]
    called = settings.invocations()
    assert called[settings.model_id].target == arn
    assert called["eu.test.lead-model:1"].target == lead_arn


#: Claude Sonnet 5.5 on the route as the SSM writes of sonnet-5-5-switch would carry it: the
#: id, prices and limits the infra session read from develop's Bedrock account on 2026-10-25
#: (eu-central-1, Standard geo, USD per Mtok), and the profile the model family needs.
SONNET_5_5_ENV = {
    **HOST_ENV,
    "AIA_BEDROCK_MODEL_ID": "eu.anthropic.claude-sonnet-5-5",
    "AIA_BEDROCK_INPUT_USD_PER_MTOK": "2.20",
    "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "11.00",
    "AIA_BEDROCK_CACHE_READ_USD_PER_MTOK": "0.11",
    "AIA_BEDROCK_CACHE_WRITE_USD_PER_MTOK": "2.75",
    "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "128000",
    "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "1000000",
    "AIA_BEDROCK_STRUCTURED_OUTPUT": "auto_tool",
    "AIA_BEDROCK_THINKING": "adaptive",
    "AIA_BEDROCK_ACCEPTS_SAMPLING": "false",
    "AIA_AI_FIELDWORK_EFFORT": "low",
}


def test_the_route_models_profile_reaches_the_worker_and_unset_changes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aia_core.domain.ai_models import DEFAULT_REQUEST_PROFILE, Effort, ThinkingMode

    unset = AIRuntimeSettings.from_env(_container("worker", HOST_ENV))
    assert unset is not None and unset.request_profile == DEFAULT_REQUEST_PROFILE

    worker = _container("worker", SONNET_5_5_ENV)
    for key in (
        "AIA_BEDROCK_STRUCTURED_OUTPUT",
        "AIA_BEDROCK_THINKING",
        "AIA_BEDROCK_ACCEPTS_SAMPLING",
        "AIA_AI_FIELDWORK_EFFORT",
    ):
        assert worker[key] == SONNET_5_5_ENV[key]
    settings = AIRuntimeSettings.from_env(worker)
    assert settings is not None and settings.model_id == "eu.anthropic.claude-sonnet-5-5"
    assert settings.request_profile.thinking is ThinkingMode.ADAPTIVE
    assert not settings.request_profile.accepts_sampling
    policy = settings.model_document()["policies"][0]
    assert policy["efforts"] == {"SIMULATION": Effort.LOW.value}
    assert settings.cache_write_usd_per_mtok == 2.75

    # The API prices a Deep Research ceiling as the worker sends it: no budget to this model.
    api = _api_settings(
        _container("api", {**SONNET_5_5_ENV, "AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS": "2048"}),
        monkeypatch,
    )
    assert api.bedrock_thinking == "adaptive"
    assert api.deep_research_pricing().thinking_budget_tokens is None
    assert api.deep_research_pricing().cache_write_usd_per_mtok == 2.75


def test_the_report_editor_reaches_the_api_on_its_public_origin_and_stays_off_until_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Document Server is not on AIA's network: it reaches the API on the public hostname
    (report-editor-hosting decision 4). The develop host hands the API that origin, and the
    editor's routes are still off until the editor's URL and secret are set from SSM."""
    dotenv = HOST_ENV
    off = _api_settings(_container("api", dotenv), monkeypatch)
    assert off.onlyoffice_callback_base == "https://aia.example.test"
    assert not off.report_editor_on
    on = _api_settings(
        _container(
            "api",
            {
                **dotenv,
                "AIA_ONLYOFFICE_URL": "https://docs.example.test",
                "AIA_ONLYOFFICE_JWT_SECRET": "s" * 48,
            },
        ),
        monkeypatch,
    )
    assert on.report_editor_on
    assert "AIA_ONLYOFFICE_CALLBACK_BASE" not in _container("worker", dotenv)
