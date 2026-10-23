"""tools/caddy_routes.py: the develop routing rules, checked on adapted Caddy JSON.

CI runs the tool on the real Caddyfile adapted by the Caddy image; these tests
prove the rules themselves: each one fails a configuration that breaks it.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
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
CADDYFILE = Path(__file__).resolve().parents[3] / "deploy" / "develop" / "Caddyfile"


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
        sub(
            ["/api/v1/*"],
            {"handler": "request_body", "max_size": 40 * 1024 * 1024},
            {"handler": "reverse_proxy", "upstreams": [{"dial": "api:8000"}]},
        ),
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


def _with_errors_site(config: dict[str, Any], *dials: str) -> dict[str, Any]:
    errors = site("errors.aia.example.test", [sub(None, *(proxy(d) for d in dials))])
    config["apps"]["http"]["servers"]["srv0"]["routes"].append(errors)
    return config


def test_glitchtip_on_its_own_name_passes(routes: Any) -> None:
    # Plan error-tracking: errors.<product hostname> is the one other site, GlitchTip's.
    assert routes.check(_with_errors_site(good(), "glitchtip:8000")) == []


@pytest.mark.parametrize("dials", [("api:8000",), ("web:3000",), ("glitchtip:8000", UNIT)])
def test_the_errors_name_reaching_anything_but_glitchtip_is_refused(
    routes: Any, dials: tuple[str, ...]
) -> None:
    problems = routes.check(_with_errors_site(good(), *dials))
    assert any("must reach GlitchTip (glitchtip:8000) and nothing else" in p for p in problems)


def test_glitchtip_on_another_name_is_refused(routes: Any) -> None:
    config = good()
    other = site("glitchtip.example.test", [sub(None, proxy("glitchtip:8000"))])
    config["apps"]["http"]["servers"]["srv0"]["routes"].append(other)
    problems = routes.check(config)
    assert any("serves another hostname: ['glitchtip.example.test']" in p for p in problems)


def test_an_api_that_takes_a_body_of_any_size_is_refused(routes: Any) -> None:
    # FastAPI reads a whole JSON body before a route's dependencies run, the
    # authentication among them: without a bound here, anyone can make the API hold
    # gigabytes before it answers 401.
    config = good()
    product(config)[at(config, "/api/v1/*")] = sub(
        ["/api/v1/*"], {"handler": "reverse_proxy", "upstreams": [{"dial": "api:8000"}]}
    )
    problems = routes.check(config)
    assert any("/api/v1/* takes a body of any size" in p for p in problems)


@pytest.mark.parametrize("size", [8 * 1024 * 1024, 1024 * 1024 * 1024])
def test_a_body_bound_below_an_upload_or_far_above_one_is_refused(routes: Any, size: int) -> None:
    config = good()
    api = product(config)[at(config, "/api/v1/*")]
    api["handle"][0]["routes"][0]["handle"][0]["max_size"] = size
    problems = routes.check(config)
    assert any("/api/v1/* bounds a body at" in p for p in problems)


def test_the_real_caddyfile_adapts_to_routing_that_passes(routes: Any) -> None:
    caddy = shutil.which("caddy")
    if caddy is None:
        pytest.skip("caddy is not installed; CI's develop-host-config job runs the real one")
    env = {
        **os.environ,
        "AIA_PUBLIC_HOSTNAME": "aia.example.test",
        "AIA_LEGACY_HOSTNAME": "legacy.example.test",
        "AIA_ACME_EMAIL": "ops@example.test",
    }
    adapted = subprocess.run(
        [caddy, "adapt", "--config", str(CADDYFILE), "--adapter", "caddyfile"],
        capture_output=True,
        check=True,
        env=env,
        text=True,
    )
    assert routes.check(json.loads(adapted.stdout)) == []


# Plan report-editor-hosting: docs.<product hostname> is ONLYOFFICE Docs behind AIA's docs gate.
DOCS_GATE = {
    "handler": "reverse_proxy",
    "rewrite": {"method": "GET", "uri": "/api/v1/session/docs-gate"},
    "upstreams": [{"dial": "api:8000"}],
}
SERVER_ONLY = (
    "(?i)^/+(?:[0-9]+\\.[0-9]+\\.[0-9]+[.|-]\\w+/+)?(?:coauthoring/+commandservice\\.ashx|"
    "convertservice\\.ashx|command|converter|docbuilder|ai-proxy|hosting|admin|info|internal|"
    "example|welcome|healthcheck)(?:[/?].*)?$"
)


CACHE_FILE = "^/cache/files/(?:[A-Za-z0-9_=-][A-Za-z0-9_.=-]*/)*[A-Za-z0-9_=-][A-Za-z0-9_.=-]*$"
CACHE_MATCH = {
    "method": ["GET", "HEAD"],
    "path_regexp": {"name": "cache_file", "pattern": CACHE_FILE},
    "query": {"expires": ["*"], "md5": ["*"]},
}


def cache_route(match: dict[str, Any] | None = None, *handlers: dict[str, Any]) -> dict[str, Any]:
    r = sub(None, *(handlers or (proxy("onlyoffice:80"),)))
    r["match"] = [match or CACHE_MATCH]
    return r


def docs_routes(
    *,
    refusal: str = SERVER_ONLY,
    gate: dict[str, Any] = DOCS_GATE,
    upstream: dict[str, Any] | None = None,
    framed_by: str = "https://aia.example.test",
    cache: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    headers = {
        "handle": [
            {
                "handler": "headers",
                "response": {"set": {"Content-Security-Policy": [f"frame-ancestors {framed_by}"]}},
            }
        ]
    }
    exchange = sub(
        ["/__aia/session"],
        {"handler": "rewrite", "uri": "/api/v1/session/docs?{http.request.uri.query}"},
        {"handler": "reverse_proxy", "upstreams": [{"dial": "api:8000"}]},
    )
    refused = {
        "handle": [
            {
                "handler": "subroute",
                "routes": [{"handle": [{"handler": "static_response", "status_code": 404}]}],
            }
        ],
        "match": [{"path_regexp": {"name": "server_only", "pattern": refusal}}],
    }
    links = cache if cache is not None else cache_route()
    return [
        headers,
        exchange,
        refused,
        *([links] if links else []),
        sub(None, gate, upstream or proxy("onlyoffice:80")),
    ]


DROPS_TICKET = {
    "format": "filter",
    "wrap": {"format": "json"},
    "fields": {
        "request>uri": {
            "filter": "query",
            "actions": [
                {"type": "delete", "parameter": name}
                for name in ("ticket", "md5", "expires", "token")
            ],
        }
    },
}


def _with_docs_site(
    config: dict[str, Any],
    docs: list[dict[str, Any]],
    *,
    encoder: dict[str, Any] | None = None,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    server = config["apps"]["http"]["servers"]["srv0"]
    server["routes"].append(site("docs.aia.example.test", docs))
    server["logs"] = {"logger_names": {"docs.aia.example.test": ["log2"]}}
    config["logging"] = {
        "logs": {
            "log2": {"encoder": encoder or DROPS_TICKET},
            "default": {"encoder": default or DROPS_TICKET},
        }
    }
    return config


@pytest.mark.parametrize(
    "encoder",
    [
        {"format": "json"},
        {**DROPS_TICKET, "fields": {"request>uri": {"filter": "query", "actions": []}}},
        {
            **DROPS_TICKET,
            "fields": {
                "request>uri": {
                    "filter": "query",
                    "actions": [{"type": "delete", "parameter": "next"}],
                }
            },
        },
    ],
)
def test_a_docs_access_log_that_writes_the_ticket_is_refused(
    routes: Any, encoder: dict[str, Any]
) -> None:
    problems = routes.check(_with_docs_site(good(), docs_routes(), encoder=encoder))
    assert any("access log writes the ticket" in p for p in problems)


def test_the_document_server_behind_the_docs_gate_passes(routes: Any) -> None:
    assert routes.check(_with_docs_site(good(), docs_routes())) == []


def test_the_document_server_without_the_docs_gate_is_refused(routes: Any) -> None:
    for gate in (APP_GATE, {"handler": "vars"}):
        problems = routes.check(_with_docs_site(good(), docs_routes(gate=gate)))
        assert any("must be the docs gate, then the Document Server" in p for p in problems)


def test_a_cookie_reaching_the_document_server_is_refused(routes: Any) -> None:
    keeps = {"handler": "reverse_proxy", "upstreams": [{"dial": "onlyoffice:80"}]}
    problems = routes.check(_with_docs_site(good(), docs_routes(upstream=keeps)))
    assert any("a cookie reaches the Document Server" in p for p in problems)


@pytest.mark.parametrize("dial", ["api:8000", "web:3000", "glitchtip:8000"])
def test_the_docs_name_reaching_anything_else_is_refused(routes: Any, dial: str) -> None:
    problems = routes.check(_with_docs_site(good(), docs_routes(upstream=proxy(dial))))
    assert any("docs.aia.example.test" in p and dial in p for p in problems)


@pytest.mark.parametrize(
    "refusal",
    [
        # The plain paths only: the version prefix and repeated slashes reach the same service.
        "^/(coauthoring/CommandService\\.ashx|ConvertService\\.ashx|converter|info|healthcheck)$",
        # Without the AI proxy.
        SERVER_ONLY.replace("ai-proxy|", ""),
    ],
)
def test_a_server_path_left_open_is_refused(routes: Any, refusal: str) -> None:
    problems = routes.check(_with_docs_site(good(), docs_routes(refusal=refusal)))
    assert any("must answer 404: it is the Document Server's own" in p for p in problems)


def test_a_refusal_that_takes_the_editor_s_own_paths_is_refused(routes: Any) -> None:
    problems = routes.check(_with_docs_site(good(), docs_routes(refusal="(?i)^/+(?:info|.*)")))
    assert any("is refused, and the editor needs it" in p for p in problems)


@pytest.mark.parametrize("framed_by", ["*", "https://evil.example.test", "'self'"])
def test_the_editor_framed_by_anything_but_aia_is_refused(routes: Any, framed_by: str) -> None:
    problems = routes.check(_with_docs_site(good(), docs_routes(framed_by=framed_by)))
    assert any("must be framed by https://aia.example.test alone" in p for p in problems)


def test_the_product_reaching_the_document_server_is_refused(routes: Any) -> None:
    config = good()
    product(config).insert(-1, sub(["/docs/*"], APP_GATE, proxy("onlyoffice:80")))
    problems = routes.check(config)
    assert any("reaches ['onlyoffice:80']" in p for p in problems)


def test_aias_pages_behind_the_docs_gate_are_refused(routes: Any) -> None:
    config = good()
    product(config)[-1] = sub(None, DOCS_GATE, proxy("web:3000"))
    problems = routes.check(config)
    assert any("asks the docs gate" in p for p in problems)


def test_an_error_log_that_writes_the_ticket_is_refused(routes: Any) -> None:
    # An upstream error (the API down) is logged by the default logger with its request's URI,
    # and the ticket in it was never spent.
    config = _with_docs_site(good(), docs_routes(), default={"format": "json"})
    problems = routes.check(config)
    assert any("access log writes the ticket" in p for p in problems)


# The save callback names the Document Server's signed links to the saved document; AIA's API
# fetches them server to server, without the docs cookie, so they alone go by without the gate.
@pytest.mark.parametrize(
    "path",
    [
        "/cache/files/data/ART-1.abc_17/output.docx/output.docx",
        "/cache/files/data/ART-1.abc_17/changes.zip/changes.zip",
        # A document key may carry `=` (base64-like) anywhere.
        "/cache/files/data/=abc=_3/output.docx/output.docx",
    ],
)
def test_the_callbacks_cache_links_match(routes: Any, path: str) -> None:
    assert routes.CACHE_FILE == CACHE_FILE
    assert re.search(CACHE_FILE, path)


@pytest.mark.parametrize(
    "path",
    [
        # Anything its nginx would resolve to another location must stay behind the gate.
        "/cache/files/../web-apps/apps/api/documents/api.js",
        "/cache/files/data/../../coauthoring/CommandService.ashx",
        "/cache/files/./data/x",
        "/cache/files/data/.x",
        "//cache/files/data/x",
        "/cache/files//data/x",
        "/cache/files/",
        "/cache/files",
        "/9.4.0-1/cache/files/data/x",
        "/web-apps/apps/api/documents/api.js",
    ],
)
def test_no_other_path_matches_the_cache_links(path: str) -> None:
    assert re.search(CACHE_FILE, path) is None


def test_saves_that_cannot_be_fetched_are_refused(routes: Any) -> None:
    problems = routes.check(_with_docs_site(good(), docs_routes(cache={})))
    assert any("signed cache links must be one route" in p for p in problems)


@pytest.mark.parametrize(
    "match",
    [
        {**CACHE_MATCH, "path_regexp": {"name": "cache_file", "pattern": "^/cache/files/.*$"}},
        {k: v for k, v in CACHE_MATCH.items() if k != "query"},
        {**CACHE_MATCH, "query": {"md5": ["*"]}},
        {k: v for k, v in CACHE_MATCH.items() if k != "method"},
        {**CACHE_MATCH, "method": ["GET", "HEAD", "POST"]},
    ],
)
def test_a_wider_ungated_route_is_refused(routes: Any, match: dict[str, Any]) -> None:
    problems = routes.check(_with_docs_site(good(), docs_routes(cache=cache_route(match))))
    assert any("must be the docs gate, then the Document Server" in p for p in problems)


def test_cache_links_that_keep_the_cookie_are_refused(routes: Any) -> None:
    keeps = {"handler": "reverse_proxy", "upstreams": [{"dial": "onlyoffice:80"}]}
    problems = routes.check(_with_docs_site(good(), docs_routes(cache=cache_route(None, keeps))))
    assert any("cache links: a cookie reaches the Document Server" in p for p in problems)


def test_cache_links_reaching_anything_else_are_refused(routes: Any) -> None:
    elsewhere = cache_route(None, proxy("api:8000"))
    problems = routes.check(_with_docs_site(good(), docs_routes(cache=elsewhere)))
    assert any("signed cache links must be one route" in p for p in problems)


def test_the_adapters_method_order_does_not_matter(routes: Any) -> None:
    reordered = {**CACHE_MATCH, "method": ["HEAD", "GET"]}
    assert routes.check(_with_docs_site(good(), docs_routes(cache=cache_route(reordered)))) == []


def test_cache_links_rewritten_elsewhere_are_refused(routes: Any) -> None:
    rewritten = cache_route(
        None,
        {"handler": "rewrite", "uri": "/coauthoring/CommandService.ashx"},
        proxy("onlyoffice:80"),
    )
    problems = routes.check(_with_docs_site(good(), docs_routes(cache=rewritten)))
    assert any("a rewrite would send them to another path" in p for p in problems)


@pytest.mark.parametrize("kept", ["md5", "expires"])
def test_a_log_that_writes_a_cache_links_signature_is_refused(routes: Any, kept: str) -> None:
    # A signed link in the log opens the saved document without the gate until it expires.
    encoder = copy.deepcopy(DROPS_TICKET)
    actions = encoder["fields"]["request>uri"]["actions"]
    encoder["fields"]["request>uri"]["actions"] = [a for a in actions if a["parameter"] != kept]
    for which in ("encoder", "default"):
        config = _with_docs_site(good(), docs_routes(), **{which: encoder})
        assert any("a cache link's signature" in p for p in routes.check(config)), which


def test_a_non_404_refusal_of_the_editors_paths_is_refused(routes: Any) -> None:
    blocks = {
        "handle": [
            {
                "handler": "subroute",
                "routes": [{"handle": [{"handler": "static_response", "status_code": 403}]}],
            }
        ],
        "match": [{"path_regexp": {"name": "x", "pattern": "^/web-apps/"}}],
    }
    docs = docs_routes()
    docs.insert(-1, blocks)
    problems = routes.check(_with_docs_site(good(), docs))
    assert any("is refused, and the editor needs it" in p for p in problems)


def _product_log(config: dict[str, Any], encoder: dict[str, Any]) -> dict[str, Any]:
    config["apps"]["http"]["servers"]["srv0"]["logs"] = {
        "logger_names": {"aia.example.test": ["log0"]}
    }
    config["logging"] = {"logs": {"log0": {"encoder": encoder}}}
    return config


DROPS_TOKEN = {
    "format": "filter",
    "fields": {
        "request>uri": {"filter": "query", "actions": [{"type": "delete", "parameter": "token"}]}
    },
    "wrap": {"format": "json"},
}


def test_a_product_log_that_drops_the_editors_token_passes(routes: Any) -> None:
    assert routes.check(_product_log(good(), DROPS_TOKEN)) == []


@pytest.mark.parametrize(
    "encoder",
    [{"format": "json"}, {**DROPS_TOKEN, "fields": {"request>uri": {"filter": "query"}}}],
)
def test_a_product_log_that_writes_the_editors_token_is_refused(
    routes: Any, encoder: dict[str, Any]
) -> None:
    """The report editor's document and callback URLs carry a bearer token in their query
    (artifact-report RPT8c): the product's access log must never write it."""
    problems = routes.check(_product_log(good(), encoder))
    assert any("writes the report editor's token" in p for p in problems)


def test_an_error_log_that_writes_the_editors_token_is_refused(routes: Any) -> None:
    config = good()
    config["logging"] = {"logs": {"default": {"encoder": {"format": "json"}}}}
    problems = routes.check(config)
    assert any("writes the report editor's token" in p for p in problems)
