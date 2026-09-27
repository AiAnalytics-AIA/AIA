"""tools/caddy_routes.py: the develop routing rules, checked on adapted Caddy JSON.

CI runs the tool on the real Caddyfile adapted by the Caddy image; these tests
prove the rules themselves: each one fails a configuration that breaks it.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest


@pytest.fixture(scope="module")
def routes(tool_loader: Any) -> Any:
    return tool_loader("caddy_routes")


GATE = {
    "handler": "reverse_proxy",
    "rewrite": {"method": "GET", "uri": "/api/v1/panel/gate"},
    "upstreams": [{"dial": "api:8000"}],
}
APP_GATE = {
    "handler": "reverse_proxy",
    "rewrite": {"method": "GET", "uri": "/api/v1/session/gate"},
    "upstreams": [{"dial": "api:8000"}],
}


def proxy(dial: str) -> dict[str, Any]:
    return {
        "handler": "reverse_proxy",
        "upstreams": [{"dial": dial}],
        "headers": {"request": {"delete": ["Cookie"]}},
    }


def sub(paths: list[str] | None, *handlers: dict[str, Any]) -> dict[str, Any]:
    r: dict[str, Any] = {
        "handle": [{"handler": "subroute", "routes": [{"handle": list(handlers)}]}]
    }
    if paths is not None:
        r["match"] = [{"path": paths}]
    return r


def good() -> dict[str, Any]:
    product = [
        sub(["/api/v1/*"], {"handler": "reverse_proxy", "upstreams": [{"dial": "api:8000"}]}),
        sub(
            ["/"],
            {
                "handler": "static_response",
                "status_code": 302,
                "headers": {"Location": ["/app/clients"]},
            },
        ),
        sub(["/app", "/app/*"], APP_GATE, proxy("web:3000")),
        sub(
            [
                "/api/providers/claude-code/*",
                "/api/settings/api_keys",
                "/api/settings/anthropic_check",
                "/api/settings/ai_check",
                "/api/settings/ai_diagnose",
            ],
            GATE,
            {"handler": "static_response", "status_code": 410},
        ),
        sub(["/api/*", "/files/*", "/health"], GATE, proxy("legacy-panel:8765")),
        sub(None, proxy("web:3000")),
    ]
    legacy = [
        sub(
            None,
            {"handler": "authentication"},
            {"handler": "reverse_proxy", "upstreams": [{"dial": "legacy-panel:8765"}]},
        )
    ]
    return {
        "apps": {
            "http": {
                "servers": {
                    "srv0": {
                        "routes": [
                            {
                                "match": [{"host": ["aia.example.test"]}],
                                "handle": [{"handler": "subroute", "routes": product}],
                            },
                            {
                                "match": [{"host": ["legacy.example.test"]}],
                                "handle": [{"handler": "subroute", "routes": legacy}],
                            },
                        ]
                    }
                }
            }
        }
    }


def product(config: dict[str, Any]) -> list[dict[str, Any]]:
    return config["apps"]["http"]["servers"]["srv0"]["routes"][0]["handle"][0]["routes"]  # type: ignore[no-any-return]


def at(config: dict[str, Any], path: str) -> int:
    """The index of the product route that names ``path``."""
    return next(
        i
        for i, r in enumerate(product(config))
        if path in [p for m in r.get("match", []) for p in m.get("path", [])]
    )


def test_the_routing_adr_0015_describes_passes(routes: Any) -> None:
    assert routes.check(good()) == []


def test_a_catch_all_to_the_unit_is_refused(routes: Any) -> None:
    config = good()
    product(config)[-1] = sub(None, GATE, proxy("legacy-panel:8765"))
    problems = routes.check(config)
    assert any("catch-all to 18.6.6" in p for p in problems)
    assert any("last route must be the web client" in p for p in problems)


def test_serving_the_classic_document_at_root_is_refused(routes: Any) -> None:
    config = good()
    product(config)[at(config, "/")] = sub(
        ["/"], GATE, {"handler": "rewrite", "uri": "/interface-document"}, proxy("web:3000")
    )
    problems = routes.check(config)
    assert any(p.startswith("/ must answer 302 /app/clients") for p in problems)
    assert any("rewrites to the 18.6.6 document" in p for p in problems)


def test_the_classic_hand_off_coming_back_is_refused(routes: Any) -> None:
    # ADR 0018 decision 4: the 18.6.6 interface is not served on the product hostname.
    config = good()
    product(config).insert(
        1,
        sub(
            ["/classic"],
            GATE,
            {"handler": "rewrite", "uri": "/interface-document"},
            proxy("web:3000"),
        ),
    )
    problems = routes.check(config)
    assert any("rewrites to the 18.6.6 document" in p for p in problems)
    assert any(p.startswith("/classic must be the web client's page") for p in problems)
    # /classic named, and sent to AIA's own page, is fine.
    config = good()
    product(config).insert(1, sub(["/classic"], proxy("web:3000")))
    assert routes.check(config) == []


def test_the_unit_on_a_path_it_does_not_serve_or_without_the_gate_is_refused(routes: Any) -> None:
    config = good()
    product(config).insert(-1, sub(["/app/secret"], proxy("legacy-panel:8765")))
    problems = routes.check(config)
    assert any("paths it does not serve" in p for p in problems)
    assert any("without the gate first" in p for p in problems)


def test_a_cookie_reaching_the_unit_or_aias_pages_is_refused(routes: Any) -> None:
    config = good()
    leaky = copy.deepcopy(proxy("legacy-panel:8765"))
    leaky["headers"] = {}
    product(config)[at(config, "/api/*")] = sub(["/api/*"], GATE, leaky)
    app = copy.deepcopy(proxy("web:3000"))
    app["headers"] = {}
    product(config)[at(config, "/app")] = sub(["/app", "/app/*"], APP_GATE, app)
    problems = routes.check(config)
    assert any("cookie reaches the unit" in p for p in problems)
    assert any("/app: the session cookie reaches the web client" in p for p in problems)


def test_an_ungated_app_or_an_open_oracle_is_refused(routes: Any) -> None:
    config = good()
    product(config)[at(config, "/app")] = sub(["/app", "/app/*"], proxy("web:3000"))
    config["apps"]["http"]["servers"]["srv0"]["routes"][1]["handle"][0]["routes"] = [
        sub(None, {"handler": "reverse_proxy", "upstreams": [{"dial": "legacy-panel:8765"}]})
    ]
    problems = routes.check(config)
    assert any(p.startswith("/app must be AIA's own gate") for p in problems)
    assert any("legacy hostname must be basic auth" in p for p in problems)


def test_app_behind_the_18_6_6_panels_gate_is_refused(routes: Any) -> None:
    # Whether AIA can be reached must never be the unit's gate's call (ADR 0018).
    config = good()
    product(config)[at(config, "/app")] = sub(["/app", "/app/*"], GATE, proxy("web:3000"))
    problems = routes.check(config)
    assert any(p.startswith("/app must be AIA's own gate") for p in problems)
    assert any(p.startswith("/app/* must be AIA's own gate") for p in problems)


def test_retired_connection_routes_are_gated_and_cannot_be_shadowed(routes: Any) -> None:
    config = good()
    retired = product(config)[at(config, "/api/settings/ai_check")]
    retired["handle"][0]["routes"][0]["handle"] = [
        {"handler": "static_response", "status_code": 410}
    ]
    assert any("must be the gate, then 410" in problem for problem in routes.check(config))
    config = good()
    retired = product(config).pop(at(config, "/api/settings/ai_check"))
    product(config).insert(at(config, "/api/*") + 1, retired)
    assert any("shadowed by the unit" in problem for problem in routes.check(config))
