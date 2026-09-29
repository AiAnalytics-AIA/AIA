"""The settings page describes the runtime the worker actually builds.

The settings document (``aia_api.routers.settings``) cannot read the worker's
environment, so it names what the code defines: the native provider, each AI
activity's capabilities and the switches that turn it on. These tests hold that
description to ``aia_executors.ai_runtime`` and to the develop Compose file. A
capability bound without being listed, a switch the worker does not read, or one
Compose does not hand the web's ``/config``, fails here -- not on the page, as a
claim nobody checked.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import aia_executors.ai_runtime as runtime
import pytest
from aia_executors.ai_runtime import AIRuntimeSettings

settings_router: Any = pytest.importorskip(
    "aia_api.routers.settings", reason="the settings document lives in apps/api"
)

ROOT = Path(__file__).resolve().parents[3]

#: A complete, valid worker configuration: test prices and ids, not Bedrock's.
_ENV = {
    "AIA_ENV": "test",
    "AIA_AI_RUNTIME_ENABLED": "true",
    "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
    "AIA_BEDROCK_REGION": "eu-central-1",
    "AIA_BEDROCK_MODEL_ID": "eu.test-settings-v1:0",
    "AIA_AI_POLICY_VERSION": "test-v1",
    "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
    "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
    "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
    "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
    "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
    "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
    "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL",
    "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
    "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
    "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
    "AIA_AI_RESEARCH_RESERVATION_USD": "2",
}


def _described() -> Any:
    return settings_router._native_runtime()


def _bound(env: dict[str, str]) -> tuple[set[str], set[str]]:
    """The providers and capabilities the worker's model policy binds under ``env``."""
    settings = AIRuntimeSettings.from_env(env)
    assert settings is not None
    document = settings.model_document()
    providers = {m["provider"] for m in document["models"]} | {
        p for policy in document["policies"] for p in policy["allowed_providers"]
    }
    capabilities = {c for policy in document["policies"] for c in policy["bindings"]}
    return providers, capabilities


@pytest.mark.parametrize("design", ["false", "true"])
def test_every_capability_the_worker_binds_belongs_to_an_activity_the_page_lists(
    design: str,
) -> None:
    env = {**_ENV, "AIA_AI_RESEARCH_AGENTS_ENABLED": design}
    providers, bound = _bound(env)
    described = _described()
    on = [a for a in described.activities if all(env.get(s) == "true" for s in a.switches)]
    assert bound == {c for a in on for c in a.capabilities}, (
        "aia_executors.ai_runtime binds a capability the settings page does not describe "
        "(or describes one it does not bind): update _native_runtime in "
        "apps/api/src/aia_api/routers/settings.py with the activity that uses it"
    )
    assert providers == {p.id for p in described.providers}
    # What no switch turns on is said to be unused, never implied to be available.
    everything = _bound({**_ENV, "AIA_AI_RESEARCH_AGENTS_ENABLED": "true"})[1]
    assert not everything & set(described.unused_capabilities)


def test_every_switch_the_page_names_is_read_by_the_worker_and_handed_to_the_web() -> None:
    source = Path(runtime.__file__).read_text(encoding="utf-8")
    compose = (ROOT / "deploy" / "develop" / "docker-compose.yml").read_text(encoding="utf-8")
    worker = compose.split("\n  worker:\n", 1)[1].split("\n  legacy-panel:", 1)[0]
    web = compose.split("\n  web:\n", 1)[1].split("\n  api:\n", 1)[0]
    route = (ROOT / "apps" / "web" / "src" / "app" / "config" / "route.ts").read_text(
        encoding="utf-8"
    )
    listed = re.search(r"export const AI_SWITCHES = \[([^\]]*)\]", route)
    assert listed, "route.ts no longer declares AI_SWITCHES"
    shown = set(re.findall(r'"([A-Z_]+)"', listed.group(1)))

    switches = {s for a in _described().activities for s in a.switches}
    assert switches
    for switch in switches:
        assert f'"{switch}"' in source, f"the worker does not read {switch}"
        assert re.search(rf"^\s+{switch}:", worker, flags=re.M), f"Compose withholds {switch}"
        assert re.search(rf"^\s+{switch}:", web, flags=re.M), f"/config cannot see {switch}"
    assert shown == switches


def test_the_master_switch_is_read_first_and_a_refused_switch_stops_the_whole_worker() -> None:
    """The rule the page states (apps/web/src/lib/ai-runtime.ts), as the worker keeps it."""
    described = _described()
    master = described.switch
    others = {s for a in described.activities for s in a.switches} - {master}
    assert master == "AIA_AI_RUNTIME_ENABLED" and others
    # Off: nothing else is read, so nothing else can be wrong, and nothing runs.
    for other in others:
        assert AIRuntimeSettings.from_env({master: "false", other: "maybe"}) is None
    assert AIRuntimeSettings.from_env({}) is None
    # On: a value the worker refuses, in the master or any other switch, is a
    # refusal to start -- fieldwork included, not only the activity it belongs to.
    with pytest.raises(runtime.AIRuntimeConfigError):
        AIRuntimeSettings.from_env({**_ENV, master: "maybe"})
    for other in others:
        with pytest.raises(runtime.AIRuntimeConfigError):
            AIRuntimeSettings.from_env({**_ENV, other: "maybe"})


def test_the_worker_signs_with_the_host_role_and_no_key_exists() -> None:
    """What the page says instead of a login or key field is how the worker works."""
    assert _described().credential.value == "INSTANCE_ROLE"
    source = Path(runtime.__file__).read_text(encoding="utf-8")
    assert "InstanceRoleSigner(region=settings.region)" in source
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "ANTHROPIC_API_KEY"):
        assert key not in source
