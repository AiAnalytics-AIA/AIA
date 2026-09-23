#!/usr/bin/env python3
"""Container health probe: GET /health on the published port.

Tries loopback first (ui_server.py binds there), then the container
interface (where the socat relay listens when the server bound a different
port). The reference's ``/health`` reports worker readiness, so its status
can legitimately be non-200 while the worker is still starting or no provider
is configured. By default any HTTP response counts as healthy (liveness of
the HTTP server). Set ``NPC_HEALTHCHECK_ACCEPT=200`` to require a 200
(readiness).
"""

from __future__ import annotations

import os
import socket
import sys
import urllib.error
import urllib.request

port = os.environ.get("NPC_PUBLIC_PORT", "8765")
accept = os.environ.get("NPC_HEALTHCHECK_ACCEPT", "any").strip().lower()


def interface_ip() -> str | None:
    ip = os.environ.get("NPC_BIND_IP")
    if ip:
        return ip
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return None if ip.startswith("127.") else ip
    except Exception:
        return None


hosts = ["127.0.0.1"]
if (ip := interface_ip()):
    hosts.append(ip)

last_error = "no host answered"
for host in hosts:
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except Exception as exc:  # connection refused, timeout, ...
        last_error = f"{url}: {exc}"
        continue
    if accept == "any" or str(status) == accept:
        print(f"healthy: {url} -> {status}")
        sys.exit(0)
    print(f"unhealthy: {url} -> {status}, expected {accept}")
    sys.exit(1)

print(f"unhealthy: {last_error}")
sys.exit(1)
