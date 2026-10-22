#!/usr/bin/env python3
"""Check the develop Caddyfile's routing, from `caddy adapt` JSON (ADR 0015, 0018).

    caddy adapt --config deploy/develop/Caddyfile --adapter caddyfile > caddy.json
    python3 tools/caddy_routes.py caddy.json

Run by CI (develop-host-config) with placeholder hostnames: the product hostname
must be ``aia.example.test``, and ``AIA_LEGACY_HOSTNAME`` is set to
``legacy.example.test`` so that a site for it, if one came back, would show up
here rather than as an empty address. Stdlib only. What it asserts, and why each
line must never go missing:

* The product hostname is the only site but two: NPC Panel 18.6.6's oracle hostname
  is not served by the product (ADR 0018 decision 5); the unit runs, when a
  comparison needs it, from ``deploy/reference`` on the host's loopback. One
  other is ``errors.<product hostname>``, GlitchTip (plan error-tracking), and it
  reaches GlitchTip and nothing else -- never the API or the web client, so it
  shares nothing of AIA's origin.
* The other is ``docs.<product hostname>``, ONLYOFFICE Docs (plan
  report-editor-hosting). Every request there passes AIA's docs gate before it
  reaches the Document Server, without the cookie; the API is reached there only
  to exchange a ticket for the docs cookie (``/__aia/session``); the Document
  Server's server-to-server and admin paths answer 404; only AIA's own pages
  may frame it; and its access log never writes the ticket a URI carries. The
  product hostname never reaches the Document Server.
* ``/`` is a redirect to ``/app/clients`` and nothing else: the product's front
  door is AIA, never the 18.6.6 document (ADR 0015).
* The 18.6.6 interface is not served (ADR 0018 decision 4): no route rewrites to
  the old ``/interface-document``, and ``/classic`` -- if it is named at all --
  goes to the web client, whose page says the interface is gone.
* ``/app`` and ``/app/*`` are AIA's own gate (``/api/v1/session/gate``), then the
  web client, without the cookie. No other gate exists: the 18.6.6 panel's
  (``/api/v1/panel/gate``) is gone with the unit.
* Nothing reaches the unit (``legacy-panel:8765``) or any upstream but the API
  and the web client, so the paths the unit served (``/api/bootstrap``,
  ``/files/*``, ``/health``, ...) are the web client's 404 like any other unknown
  path.
* ``/api/v1/*`` is the API, and the last route is the web client for any other path.
* ``/api/v1/*`` bounds a request body before it reaches the API: FastAPI reads a
  whole JSON body before a route's dependencies run, authentication among them, so
  without a bound anyone could make it hold gigabytes before it answers 401. The bound
  sits above the largest upload (a 25 MiB source or attachment, base64 in JSON) and
  well below what one process should hold.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from typing import Any

PRODUCT = "aia.example.test"
ERRORS = f"errors.{PRODUCT}"
GLITCHTIP = "glitchtip:8000"
DOCS = f"docs.{PRODUCT}"
ONLYOFFICE = "onlyoffice:80"
DOCS_GATE = "/api/v1/session/docs-gate"
# The one path of docs.<hostname> the API answers: a one-time ticket spent for the docs cookie.
DOCS_SESSION = "/__aia/session"
DOCS_SESSION_TARGET = "/api/v1/session/docs?{http.request.uri.query}"
# The Document Server's server-to-server, AI proxy, hosting and admin paths: nothing outside
# needs any of them. Each is refused in any
# case, behind the version prefix its nginx strips and with the slashes its nginx merges.
SERVER_ONLY = (
    "/coauthoring/CommandService.ashx",
    "/9.4.0-1/coauthoring/CommandService.ashx",
    "//coauthoring//commandservice.ashx",
    "/ConvertService.ashx",
    "/converter",
    "/command",
    "/docbuilder",
    "/ai-proxy/openai/v1/chat",
    "/9.4.0.1/AI-PROXY",
    "/hosting/discovery",
    "/admin",
    "/info/info.json",
    "/internal/cluster/inactive",
    "/example/",
    "/welcome/",
    "/healthcheck",
)
# What the editor itself loads, which the refusal must leave alone.
EDITOR_PATHS = (
    "/web-apps/apps/api/documents/api.js",
    "/9.4.0-1/web-apps/apps/documenteditor/main/index.html",
    "/9.4.0-1/sdkjs/word/sdk-all.js",
    "/doc/ART-1.abc/c/",
    "/downloadas/ART-1.abc",
    "/cache/files/data/ART-1.abc/output.docx/output.docx",
    "/information",
)
LEGACY = "legacy.example.test"
UNIT = "legacy-panel:8765"
WEB = "web:3000"
API = "api:8000"
APP_GATE = "/api/v1/session/gate"
# The 18.6.6 panel's gate (ADR 0012), retired with the unit (ADR 0018). Named so
# that a route asking it is reported as the gate it is, and refused.
PANEL_GATE = "/api/v1/panel/gate"
GATES = (APP_GATE, PANEL_GATE, DOCS_GATE)
# The largest body a route takes: a 25 MiB file as base64 (4/3) in its JSON envelope.
BODY_MIN = 36 * 1024 * 1024
BODY_MAX = 64 * 1024 * 1024


def walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def dials(node: Any) -> list[str]:
    return [
        u.get("dial", "")
        for n in walk(node)
        if n.get("handler") == "reverse_proxy"
        for u in n.get("upstreams", [])
    ]


def proxied(node: Any) -> list[str]:
    """The upstreams a route serves from: every proxy's but a gate's."""
    return [
        u.get("dial", "")
        for n in walk(node)
        if n.get("handler") == "reverse_proxy" and n.get("rewrite", {}).get("uri") not in GATES
        for u in n.get("upstreams", [])
    ]


def steps(node: Any) -> list[str]:
    """The route's handlers in order: gate, rewrite, proxy, redirect."""
    out = []
    for n in walk(node):
        handler = n.get("handler")
        if handler == "reverse_proxy":
            uri = n.get("rewrite", {}).get("uri")
            out.append(f"gate:{uri}" if uri in GATES else "proxy:" + ",".join(dials(n)))
        elif handler == "rewrite":
            out.append(f"rewrite:{n.get('uri')}")
        elif handler == "static_response":
            location = n.get("headers", {}).get("Location", [""])
            out.append(f"static:{n.get('status_code')}:{','.join(location)}")
        elif handler == "authentication":
            out.append("basic_auth")
    return out


def cookie_dropped(node: Any) -> bool:
    proxies = [
        n
        for n in walk(node)
        if n.get("handler") == "reverse_proxy" and n.get("rewrite", {}).get("uri") not in GATES
    ]
    return bool(proxies) and all(
        "Cookie" in n.get("headers", {}).get("request", {}).get("delete", []) for n in proxies
    )


def hosts(config: dict[str, Any]) -> set[str]:
    """Every hostname a site answers for, across every server."""
    return {
        h
        for server in config["apps"]["http"]["servers"].values()
        for route in server.get("routes", [])
        for m in route.get("match", [])
        for h in m.get("host", [])
    }


def site(config: dict[str, Any], host: str) -> list[dict[str, Any]]:
    for server in config["apps"]["http"]["servers"].values():
        for route in server.get("routes", []):
            if host in [h for m in route.get("match", []) for h in m.get("host", [])]:
                return route["handle"][0]["routes"]  # type: ignore[no-any-return]
    raise SystemExit(f"no route for {host}")


def paths_of(route: dict[str, Any]) -> list[str]:
    return [p for m in route.get("match", []) for p in m.get("path", [])]


def refuses(route: dict[str, Any], path: str) -> bool:
    """Whether the route's path_regexp matches ``path``.

    Caddy's patterns are Go's RE2; the ones checked here read the same in Python's ``re``.
    """
    return any(
        re.search(m["path_regexp"]["pattern"], path) is not None
        for m in route.get("match", [])
        if "path_regexp" in m
    )


def check(config: dict[str, Any]) -> list[str]:
    """Every problem found; empty when the routing is as the ADRs say."""
    problems: list[str] = []
    others = sorted(hosts(config) - {PRODUCT, ERRORS, DOCS})
    if others:
        problems.append(
            f"the product Caddyfile serves another hostname: {others} (the 18.6.6 oracle is "
            "deploy/reference's, on the host's loopback)"
        )
    if ERRORS in hosts(config):
        upstreams = {d for r in site(config, ERRORS) for d in dials(r)}
        if upstreams != {GLITCHTIP}:
            problems.append(
                f"{ERRORS} must reach GlitchTip ({GLITCHTIP}) and nothing else; got "
                f"{sorted(upstreams)}"
            )
    if DOCS in hosts(config):
        problems.extend(check_docs(config))
    routes = site(config, PRODUCT)

    def only(path: str) -> dict[str, Any] | None:
        found = [r for r in routes if path in paths_of(r)]
        if len(found) != 1:
            problems.append(f"{path}: expected exactly one route, found {len(found)}")
            return None
        return found[0]

    if (r := only("/")) is not None and steps(r) != ["static:302:/app/clients"]:
        problems.append(f"/ must answer 302 /app/clients and nothing else; got {steps(r)}")
    for r in routes:
        if any(s.startswith("rewrite:/interface-document") for s in steps(r)):
            problems.append(f"{paths_of(r)} rewrites to the 18.6.6 document: it is not served")
    for r in (r for r in routes if "/classic" in paths_of(r)):
        if steps(r) != [f"proxy:{WEB}"]:
            problems.append(
                f"/classic must be the web client's page and nothing else; got {steps(r)}"
            )
    for path in ("/app", "/app/*"):
        if (r := only(path)) is not None:
            if steps(r) != [f"gate:{APP_GATE}", f"proxy:{WEB}"]:
                problems.append(
                    f"{path} must be AIA's own gate, then the web client; got {steps(r)}"
                )
            if not cookie_dropped(r):
                problems.append(f"{path}: the session cookie reaches the web client")
    if (r := only("/api/v1/*")) is not None:
        if dials(r) != [API]:
            problems.append(f"/api/v1/* must be the API; got {dials(r)}")
        bounds = [n.get("max_size") for n in walk(r) if n.get("handler") == "request_body"]
        if not bounds or not all(bounds):
            problems.append("/api/v1/* takes a body of any size: the API reads it all first")
        elif not all(BODY_MIN <= int(b) <= BODY_MAX for b in bounds):
            problems.append(
                f"/api/v1/* bounds a body at {bounds}: between {BODY_MIN} (the largest "
                f"upload) and {BODY_MAX} bytes"
            )

    for r in routes:
        where = paths_of(r) or ["any path"]
        if UNIT in dials(r):
            problems.append(f"{where} reaches the 18.6.6 unit: the product serves none of it")
        elif stray := sorted(set(dials(r)) - {API, WEB}):
            problems.append(f"{where} reaches {stray}: only the API and the web client are AIA's")
        if f"gate:{PANEL_GATE}" in steps(r):
            problems.append(f"{where} asks the 18.6.6 panel's gate, which is gone with the unit")
        if f"gate:{DOCS_GATE}" in steps(r):
            problems.append(f"{where} asks the docs gate: AIA's pages are behind AIA's own")
    last = routes[-1]
    if paths_of(last) or dials(last) != [WEB]:
        problems.append(
            f"the last route must be the web client for any other path; got {steps(last)}"
        )
    return problems


def check_docs(config: dict[str, Any]) -> list[str]:
    """What docs.<hostname> must be: the Document Server behind the docs gate, and no more."""
    problems: list[str] = []
    routes = site(config, DOCS)
    served = [r for r in routes if dials(r) or steps(r)]
    session = [r for r in served if DOCS_SESSION in paths_of(r)]
    if len(session) != 1 or steps(session[0]) != [
        f"rewrite:{DOCS_SESSION_TARGET}",
        f"proxy:{API}",
    ]:
        problems.append(
            f"{DOCS}{DOCS_SESSION} must be the API's ticket exchange and nothing else; got "
            f"{[steps(r) for r in session]}"
        )
    refusal = [r for r in served if steps(r) == ["static:404:"]]
    for path in SERVER_ONLY:
        if not any(refuses(r, path) for r in refusal):
            problems.append(f"{DOCS}{path} must answer 404: it is the Document Server's own")
    for path in EDITOR_PATHS:
        if any(refuses(r, path) for r in served):
            problems.append(f"{DOCS}{path} is refused, and the editor needs it")
    for r in served:
        where = paths_of(r) or ["any path"]
        if r in session:
            continue
        if API in proxied(r):
            problems.append(f"{DOCS} {where} reaches the API beyond the ticket exchange")
        if stray := sorted(set(proxied(r)) - {ONLYOFFICE}):
            problems.append(f"{DOCS} {where} reaches {stray}: only the Document Server is served")
        if ONLYOFFICE in proxied(r):
            if steps(r) != [f"gate:{DOCS_GATE}", f"proxy:{ONLYOFFICE}"]:
                problems.append(
                    f"{DOCS} {where} must be the docs gate, then the Document Server; "
                    f"got {steps(r)}"
                )
            if not cookie_dropped(r):
                problems.append(f"{DOCS} {where}: a cookie reaches the Document Server")
    last = served[-1] if served else {}
    if paths_of(last) or proxied(last) != [ONLYOFFICE]:
        problems.append(f"{DOCS}: the last route must be the Document Server for any other path")
    framers = {
        value
        for n in walk(routes)
        if n.get("handler") == "headers"
        for value in n.get("response", {}).get("set", {}).get("Content-Security-Policy", [])
    }
    if framers != {f"frame-ancestors https://{PRODUCT}"}:
        problems.append(f"{DOCS} must be framed by https://{PRODUCT} alone; got {sorted(framers)}")
    if not logs_drop_ticket(config):
        problems.append(f"{DOCS}'s access log writes the ticket in a URI's query")
    return problems


def logs_drop_ticket(config: dict[str, Any]) -> bool:
    """Whether every access log of docs.<hostname> deletes ``ticket`` from the logged URI."""
    names = [
        name
        for server in config["apps"]["http"]["servers"].values()
        for name in server.get("logs", {}).get("logger_names", {}).get(DOCS, [])
    ]
    logs = config.get("logging", {}).get("logs", {})

    def drops(name: str) -> bool:
        encoder = logs.get(name, {}).get("encoder", {})
        uri = encoder.get("fields", {}).get("request>uri", {})
        return (
            encoder.get("format") == "filter"
            and uri.get("filter") == "query"
            and any(
                a.get("type") == "delete" and a.get("parameter") == "ticket"
                for a in uri.get("actions", [])
            )
        )

    return bool(names) and all(drops(n) for n in names)


def main(argv: list[str]) -> int:
    config = json.load(open(argv[1]))  # noqa: SIM115 -- a one-shot CLI read
    problems = check(config)
    for p in problems:
        print(f"FAIL  {p}")
    if problems:
        return 1
    print(
        "caddy routes: AIA's hostname, errors.<it> to GlitchTip alone and docs.<it> to the "
        "Document Server behind the docs gate; / -> /app/clients; /app behind AIA's gate; the "
        "API and the web client only, nothing of 18.6.6"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
