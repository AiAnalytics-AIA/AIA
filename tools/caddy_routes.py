#!/usr/bin/env python3
"""Check the develop Caddyfile's routing, from `caddy adapt` JSON (ADR 0012, 0015, 0018).

    caddy adapt --config deploy/develop/Caddyfile --adapter caddyfile > caddy.json
    python3 tools/caddy_routes.py caddy.json

Run by CI (develop-host-config) with placeholder hostnames: the product hostname
must be ``aia.example.test`` and the legacy one ``legacy.example.test``. Stdlib
only. What it asserts, and why each line must never go missing:

* ``/`` is a redirect to ``/app/clients`` and nothing else: the product's front
  door is AIA, never the 18.6.6 document (ADR 0015).
* The 18.6.6 interface is not served (ADR 0018 decision 4): no route rewrites to
  the old ``/interface-document``, and ``/classic`` -- if it is named at all --
  goes to the web client, whose page says the interface is gone, never to the
  unit or through the panel's gate.
* ``/app`` and ``/app/*`` are AIA's own gate (``/api/v1/session/gate``, ADR 0018),
  then the web client, without the cookie: never the 18.6.6 panel's gate, so
  nothing about the unit decides whether AIA can be reached.
* The unit is reached only on the paths it serves, each behind the gate and
  without the cookie; nothing without a path matcher reaches it, so no unknown
  path falls through to the classic product.
* ``/api/v1/*`` is the API.
* The legacy hostname is the oracle behind basic auth, straight to the unit.
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
GATE = "/api/v1/panel/gate"
APP_GATE = "/api/v1/session/gate"
GATES = (GATE, APP_GATE)
# The paths the unit serves (docs/migration/legacy-route-ledger.json).
UNIT_PATHS = {
    "/api/*",
    "/files/*",
    "/artifacts/*",
    "/project-attachments/*",
    "/brand/*",
    "/fullsim-arena",
    "/health",
    "/status",
}


RETIRED_AI_PATHS = {
    "/api/providers/claude-code/*",
    "/api/settings/api_keys",
    "/api/settings/anthropic_check",
    "/api/settings/ai_check",
    "/api/settings/ai_diagnose",
}


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
            problems.append(f"/classic must be the web client's page and nothing else; got {steps(r)}")
    for path in ("/app", "/app/*"):
        if (r := only(path)) is not None:
            if steps(r) != [f"gate:{APP_GATE}", f"proxy:{WEB}"]:
                problems.append(
                    f"{path} must be AIA's own gate, then the web client; got {steps(r)}"
                )
            if not cookie_dropped(r):
                problems.append(f"{path}: the session cookie reaches the web client")
    if (r := only("/api/v1/*")) is not None and dials(r) != ["api:8000"]:
        problems.append(f"/api/v1/* must be the API; got {dials(r)}")

    for path in RETIRED_AI_PATHS:
        if (r := only(path)) is not None:
            if steps(r) != [f"gate:{GATE}", "static:410:"]:
                problems.append(f"{path} must be the gate, then 410; got {steps(r)}")
            unit_routes = [i for i, route in enumerate(routes) if UNIT in dials(route)]
            if unit_routes and routes.index(r) > min(unit_routes):
                problems.append(f"{path}: retired connection handler is shadowed by the unit")

    to_unit = [r for r in routes if UNIT in dials(r)]
    if not to_unit:
        problems.append(
            "the product hostname no longer reaches the unit (the stages read it, OI-58)"
        )
    for r in to_unit:
        paths = set(paths_of(r))
        if not paths:
            problems.append(
                "a route without a path matcher reaches the unit: a catch-all to 18.6.6"
            )
        elif not paths <= UNIT_PATHS:
            problems.append(
                f"the unit is reached on paths it does not serve: {sorted(paths - UNIT_PATHS)}"
            )
        if steps(r)[:1] != [f"gate:{GATE}"]:
            problems.append(f"the unit is reached on {sorted(paths)} without the gate first")
        if not cookie_dropped(r):
            problems.append(f"the session cookie reaches the unit on {sorted(paths)}")
    last = routes[-1]
    if paths_of(last) or dials(last) != [WEB]:
        problems.append(
            f"the last route must be the web client for any other path; got {steps(last)}"
        )

    legacy = site(config, LEGACY)
    legacy_steps = [s for r in legacy for s in steps(r)]
    if "basic_auth" not in legacy_steps or legacy_steps[-1:] != [f"proxy:{UNIT}"]:
        problems.append(
            f"the legacy hostname must be basic auth, then the unit; got {legacy_steps}"
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
        "caddy routes: / -> /app/clients; /app behind AIA's gate; no 18.6.6 document; "
        "the unit only on its own paths, behind the panel gate"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
