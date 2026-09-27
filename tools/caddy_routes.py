#!/usr/bin/env python3
"""Check the develop Caddyfile's routing, from `caddy adapt` JSON (ADR 0015, 0018).

    caddy adapt --config deploy/develop/Caddyfile --adapter caddyfile > caddy.json
    python3 tools/caddy_routes.py caddy.json

Run by CI (develop-host-config) with placeholder hostnames: the product hostname
must be ``aia.example.test``, and ``AIA_LEGACY_HOSTNAME`` is set to
``legacy.example.test`` so that a site for it, if one came back, would show up
here rather than as an empty address. Stdlib only. What it asserts, and why each
line must never go missing:

* The product hostname is the only site: NPC Panel 18.6.6's oracle hostname is not
  served by the product (ADR 0018 decision 5); the unit runs, when a comparison
  needs it, from ``deploy/reference`` on the host's loopback.
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
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from typing import Any

PRODUCT = "aia.example.test"
LEGACY = "legacy.example.test"
UNIT = "legacy-panel:8765"
WEB = "web:3000"
API = "api:8000"
APP_GATE = "/api/v1/session/gate"
# The 18.6.6 panel's gate (ADR 0012), retired with the unit (ADR 0018). Named so
# that a route asking it is reported as the gate it is, and refused.
PANEL_GATE = "/api/v1/panel/gate"
GATES = (APP_GATE, PANEL_GATE)


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


def check(config: dict[str, Any]) -> list[str]:
    """Every problem found; empty when the routing is as the ADRs say."""
    problems: list[str] = []
    others = sorted(hosts(config) - {PRODUCT})
    if others:
        problems.append(
            f"the product Caddyfile serves another hostname: {others} (the 18.6.6 oracle is "
            "deploy/reference's, on the host's loopback)"
        )
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
    if (r := only("/api/v1/*")) is not None and dials(r) != [API]:
        problems.append(f"/api/v1/* must be the API; got {dials(r)}")

    for r in routes:
        where = paths_of(r) or ["any path"]
        if UNIT in dials(r):
            problems.append(f"{where} reaches the 18.6.6 unit: the product serves none of it")
        elif stray := sorted(set(dials(r)) - {API, WEB}):
            problems.append(f"{where} reaches {stray}: only the API and the web client are AIA's")
        if f"gate:{PANEL_GATE}" in steps(r):
            problems.append(f"{where} asks the 18.6.6 panel's gate, which is gone with the unit")
    last = routes[-1]
    if paths_of(last) or dials(last) != [WEB]:
        problems.append(
            f"the last route must be the web client for any other path; got {steps(last)}"
        )
    return problems


def main(argv: list[str]) -> int:
    config = json.load(open(argv[1]))  # noqa: SIM115 -- a one-shot CLI read
    problems = check(config)
    for p in problems:
        print(f"FAIL  {p}")
    if problems:
        return 1
    print(
        "caddy routes: one hostname, AIA's; / -> /app/clients; /app behind AIA's gate; "
        "the API and the web client only, nothing of 18.6.6"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
