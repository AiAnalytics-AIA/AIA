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


# The 18.6.6 panel's gate (ADR 0012): retired with the unit, refused wherever it appears.
PANEL_GATE = {
    "handler": "reverse_proxy",
    "rewrite": {"method": "GET", "uri": "/api/v1/panel/gate"},
    "upstreams": [{"dial": "api:8000"}],
}
APP_GATE = {
    "handler": "reverse_proxy",
    "rewrite": {"method": "GET", "uri": "/api/v1/session/gate"},
    "upstreams": [{"dial": "api:8000"}],
}
UNIT = "legacy-panel:8765"


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


def site(host: str, routes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"match": [{"host": [host]}], "handle": [{"handler": "subroute", "routes": routes}]}


def good() -> dict[str, Any]:
    product = [
        sub(["/api/v1/*"], {"handler": "reverse_proxy", "upstreams": [{"dial": "api:8000"}]}),
        sub(
            ["/login", "/_next/*"],
            {"handler": "reverse_proxy", "upstreams": [{"dial": "web:3000"}]},
        ),
        sub(
            ["/"],
            {
                "handler": "static_response",
                "status_code": 302,
                "headers": {"Location": ["/app/clients"]},
            },
        ),
        sub(["/app", "/app/*"], APP_GATE, proxy("web:3000")),
        sub(None, proxy("web:3000")),
    ]
    return {
        "apps": {"http": {"servers": {"srv0": {"routes": [site("aia.example.test", product)]}}}}
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


def test_the_routing_adr_0018_describes_passes(routes: Any) -> None:
    assert routes.check(good()) == []


def test_the_unit_as_the_catch_all_is_refused(routes: Any) -> None:
    config = good()
    product(config)[-1] = sub(None, PANEL_GATE, proxy(UNIT))
    problems = routes.check(config)
    assert any("reaches the 18.6.6 unit" in p for p in problems)
    assert any("asks the 18.6.6 panel's gate" in p for p in problems)
    assert any("last route must be the web client" in p for p in problems)


def test_the_unit_coming_back_on_its_own_paths_is_refused(routes: Any) -> None:
    # ADR 0018 decision 5: the product deployment serves nothing of 18.6.6,
    # gated or not, on the paths it used to or on any other.
    for handlers in ((PANEL_GATE, proxy(UNIT)), (APP_GATE, proxy(UNIT)), (proxy(UNIT),)):
        config = good()
        product(config).insert(-1, sub(["/api/*", "/files/*", "/health"], *handlers))
        problems = routes.check(config)
        assert any(
            "['/api/*', '/files/*', '/health'] reaches the 18.6.6 unit" in p for p in problems
        )


def test_any_upstream_but_the_api_and_the_web_client_is_refused(routes: Any) -> None:
    config = good()
    product(config).insert(-1, sub(["/elsewhere/*"], proxy("reference:8765")))
    problems = routes.check(config)
    assert any("reaches ['reference:8765']" in p for p in problems)


def test_a_second_hostname_is_refused(routes: Any) -> None:
    # The oracle hostname is not the product's: the unit runs from deploy/reference,
    # on the host's loopback, behind its own gate.
    config = good()
    oracle = site(
        "legacy.example.test",
        [sub(None, {"handler": "authentication"}, proxy(UNIT))],
    )
    config["apps"]["http"]["servers"]["srv0"]["routes"].append(oracle)
    problems = routes.check(config)
    assert any("serves another hostname: ['legacy.example.test']" in p for p in problems)


def test_serving_the_classic_document_at_root_is_refused(routes: Any) -> None:
    config = good()
    product(config)[at(config, "/")] = sub(
        ["/"], PANEL_GATE, {"handler": "rewrite", "uri": "/interface-document"}, proxy("web:3000")
    )
    problems = routes.check(config)
    assert any(p.startswith("/ must answer 302 /app/clients") for p in problems)
    assert any("rewrites to the 18.6.6 document" in p for p in problems)
    assert any("asks the 18.6.6 panel's gate" in p for p in problems)


def test_the_classic_hand_off_coming_back_is_refused(routes: Any) -> None:
    # ADR 0018 decision 4: the 18.6.6 interface is not served on the product hostname.
    config = good()
    product(config).insert(
        1,
        sub(
            ["/classic"],
            PANEL_GATE,
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


def test_a_cookie_reaching_aias_pages_is_refused(routes: Any) -> None:
    config = good()
    app = copy.deepcopy(proxy("web:3000"))
    app["headers"] = {}
    product(config)[at(config, "/app")] = sub(["/app", "/app/*"], APP_GATE, app)
    problems = routes.check(config)
    assert any("/app: the session cookie reaches the web client" in p for p in problems)


def test_an_ungated_app_is_refused(routes: Any) -> None:
    config = good()
    product(config)[at(config, "/app")] = sub(["/app", "/app/*"], proxy("web:3000"))
    problems = routes.check(config)
    assert any(p.startswith("/app must be AIA's own gate") for p in problems)


def test_app_behind_the_18_6_6_panels_gate_is_refused(routes: Any) -> None:
    # Whether AIA can be reached is never the unit's gate's call (ADR 0018).
    config = good()
    product(config)[at(config, "/app")] = sub(["/app", "/app/*"], PANEL_GATE, proxy("web:3000"))
    problems = routes.check(config)
    assert any(p.startswith("/app must be AIA's own gate") for p in problems)
    assert any(p.startswith("/app/* must be AIA's own gate") for p in problems)
    assert any("asks the 18.6.6 panel's gate" in p for p in problems)


def test_the_api_elsewhere_is_refused(routes: Any) -> None:
    config = good()
    product(config)[at(config, "/api/v1/*")] = sub(["/api/v1/*"], proxy("web:3000"))
    problems = routes.check(config)
    assert any(p.startswith("/api/v1/* must be the API") for p in problems)
