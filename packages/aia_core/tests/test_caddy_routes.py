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
        sub(["/interface-document"], {"handler": "static_response", "status_code": 404}),
        sub(
            ["/classic"],
            GATE,
            {"handler": "rewrite", "uri": "/interface-document"},
            proxy("web:3000"),
        ),
        sub(
            ["/"],
            {
                "handler": "static_response",
                "status_code": 302,
                "headers": {"Location": ["/app/clients"]},
            },
        ),
        sub(["/app", "/app/*"], GATE, proxy("web:3000")),
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
    product(config)[3] = sub(
        ["/"], GATE, {"handler": "rewrite", "uri": "/interface-document"}, proxy("web:3000")
    )
    assert any(p.startswith("/ must answer 302 /app/clients") for p in routes.check(config))


def test_the_unit_on_a_path_it_does_not_serve_or_without_the_gate_is_refused(routes: Any) -> None:
    config = good()
    product(config).insert(-1, sub(["/app/secret"], proxy("legacy-panel:8765")))
    problems = routes.check(config)
    assert any("paths it does not serve" in p for p in problems)
    assert any("without the gate first" in p for p in problems)


def test_a_cookie_reaching_the_unit_or_the_classic_page_is_refused(routes: Any) -> None:
    config = good()
    leaky = copy.deepcopy(proxy("legacy-panel:8765"))
    leaky["headers"] = {}
    product(config)[5] = sub(["/api/*"], GATE, leaky)
    classic = copy.deepcopy(proxy("web:3000"))
    classic["headers"] = {}
    product(config)[2] = sub(
        ["/classic"], GATE, {"handler": "rewrite", "uri": "/interface-document"}, classic
    )
    problems = routes.check(config)
    assert any("cookie reaches the unit" in p for p in problems)
    assert any("/classic: the session cookie" in p for p in problems)


def test_an_ungated_app_or_an_open_oracle_is_refused(routes: Any) -> None:
    config = good()
    product(config)[4] = sub(["/app", "/app/*"], proxy("web:3000"))
    config["apps"]["http"]["servers"]["srv0"]["routes"][1]["handle"][0]["routes"] = [
        sub(None, {"handler": "reverse_proxy", "upstreams": [{"dial": "legacy-panel:8765"}]})
    ]
    problems = routes.check(config)
    assert any(p.startswith("/app must be the gate") for p in problems)
    assert any("legacy hostname must be basic auth" in p for p in problems)
