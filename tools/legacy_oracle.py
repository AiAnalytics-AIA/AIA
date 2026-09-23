#!/usr/bin/env python3
"""Reach the running NPC Panel 18.6.6 unit (the oracle), record it, compare with it.

ADR 0011 makes the vendored 18.6.6 unit the behavioural baseline. It runs as the
``legacy-panel`` service on the develop host, on its own hostname behind Caddy's
HTTP basic-auth gate (the reference has no identity model, reference R14). This
module is the one way parity code reaches it:

* ``OracleEndpoint.from_environment()`` reads ``AIA_LEGACY_REFERENCE_URL`` plus
  ``AIA_LEGACY_REFERENCE_USER`` / ``AIA_LEGACY_REFERENCE_PASSWORD``. Absent URL
  means *no oracle*, and every oracle test skips -- the same contract as
  ``AIA_LEGACY_REFERENCE`` for the extracted tree. Credentials come from the
  environment only; nothing here writes them to a fixture or a log.
* ``OracleClient`` sends one request and returns an ``Exchange``: status,
  content type, decoded body, elapsed time. It does not retry, follow redirects
  or invent a body: what the oracle answered is what is recorded.
* ``record`` writes request/response pairs as fixtures in the shape of the
  reference's golden fixtures, one per route, into a directory the parity tests
  read back. ``compare`` decides whether a live answer matches a recorded one
  under the route's declared parity type: ``EXACT`` (equal), ``NUMERICAL``
  (numbers within a tolerance, everything else equal) or ``SEMANTIC`` (same
  shape and keys; values compared where they are not declared volatile).
  Volatile fields (timestamps, ids, elapsed times) are named per fixture and
  compared by type only.

Stdlib only, like the rest of ``tools/``.

    python tools/legacy_oracle.py probe
    python tools/legacy_oracle.py record --scenario scenario.json --out fixtures/legacy_http
    python tools/legacy_oracle.py compare fixtures/legacy_http/H_GET_health.json

Exit status: 1 when the oracle is unreachable, a scenario request fails, or a
comparison finds a difference; else 0.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
UNIT = REPO / "legacy" / "npc-panel-18.6.6"
DEFAULT_FIXTURES = REPO / "packages" / "aia_core" / "tests" / "fixtures" / "legacy_http"

ENV_URL = "AIA_LEGACY_REFERENCE_URL"
ENV_USER = "AIA_LEGACY_REFERENCE_USER"
ENV_PASSWORD = "AIA_LEGACY_REFERENCE_PASSWORD"
ENV_REQUIRE = "AIA_REQUIRE_LEGACY_ORACLE"

EXACT = "EXACT"
NUMERICAL = "NUMERICAL"
SEMANTIC = "SEMANTIC"
PARITY_TYPES = (EXACT, NUMERICAL, SEMANTIC)

FIXTURE_SCHEMA = "aia-legacy-http-fixture-1"


class OracleUnavailable(RuntimeError):
    """The oracle did not answer, or answered with a transport error."""


# --------------------------------------------------------------------------- #
# Endpoint and client
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class OracleEndpoint:
    """Where the oracle is and how to pass its gate. Never serialised."""

    url: str
    user: str = ""
    password: str = field(default="", repr=False)

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> OracleEndpoint | None:
        env = os.environ if environ is None else environ
        url = (env.get(ENV_URL) or "").strip()
        if not url:
            return None
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{ENV_URL} must be an http(s) URL with a host, got {url!r}")
        return cls(
            url=url.rstrip("/"),
            user=(env.get(ENV_USER) or "").strip(),
            password=env.get(ENV_PASSWORD) or "",
        )

    @property
    def gated(self) -> bool:
        return bool(self.user)

    def authorization(self) -> str:
        token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode("ascii")
        return f"Basic {token}"


def require_oracle(environ: Mapping[str, str] | None = None) -> bool:
    """Whether a missing oracle is a failure (``AIA_REQUIRE_LEGACY_ORACLE=1``)."""
    env = os.environ if environ is None else environ
    return env.get(ENV_REQUIRE) == "1"


@dataclass(frozen=True)
class Exchange:
    """One request and what the oracle answered. Everything a fixture records."""

    method: str
    path: str
    query: dict[str, str]
    request_body: Any
    status: int
    content_type: str
    body: Any
    elapsed_ms: int

    @property
    def is_json(self) -> bool:
        return self.content_type.split(";", 1)[0].strip().lower() == "application/json"


class OracleClient:
    """Sends requests to the oracle, through its gate, and decodes the answers."""

    def __init__(self, endpoint: OracleEndpoint, *, timeout_s: float = 60.0) -> None:
        self.endpoint = endpoint
        self.timeout_s = timeout_s

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
        body: Any = None,
        authenticated: bool = True,
    ) -> Exchange:
        """One HTTP exchange. Any HTTP status is an answer; only transport errors raise."""
        if not path.startswith("/"):
            raise ValueError(f"path must start with '/', got {path!r}")
        query = dict(query or {})
        url = self.endpoint.url + path
        if query:
            url += "?" + urllib.parse.urlencode(sorted(query.items()))
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        if authenticated and self.endpoint.gated:
            headers["Authorization"] = self.endpoint.authorization()
        req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                status = int(resp.status)
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
            raw = exc.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OracleUnavailable(f"{method.upper()} {url}: {exc}") from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return Exchange(
            method=method.upper(),
            path=path,
            query=query,
            request_body=body,
            status=status,
            content_type=content_type,
            body=_decode_body(raw, content_type),
            elapsed_ms=elapsed_ms,
        )


def _decode_body(raw: bytes, content_type: str) -> Any:
    kind = content_type.split(";", 1)[0].strip().lower()
    if kind == "application/json":
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    if kind.startswith("text/") or kind in {"application/json", ""}:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            pass
    return {"__bytes_sha256__": hashlib.sha256(raw).hexdigest(), "__bytes__": len(raw)}


def probe(client: OracleClient) -> dict[str, Any]:
    """``GET /health``: the oracle's own liveness answer, or ``OracleUnavailable``."""
    health = client.request("GET", "/health")
    if health.status != 200 or not isinstance(health.body, dict):
        raise OracleUnavailable(f"GET /health answered {health.status}: {health.body!r}")
    return dict(health.body)


def unit_release() -> str:
    """The release the vendored unit declares (``app/VERSION``)."""
    return (UNIT / "app" / "VERSION").read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RequestSpec:
    """One recorded request: what to send and how its answer is compared."""

    fixture_id: str
    method: str
    path: str
    capability: str
    parity_type: str = SEMANTIC
    tolerance: float | None = None
    query: dict[str, str] = field(default_factory=dict)
    body: Any = None
    volatile: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        if not re.fullmatch(r"H_[A-Za-z0-9_]+", self.fixture_id):
            raise ValueError(f"fixture_id must match H_<name>, got {self.fixture_id!r}")
        if self.parity_type not in PARITY_TYPES:
            raise ValueError(f"unknown parity type {self.parity_type!r}")
        if self.parity_type == NUMERICAL and (self.tolerance is None or self.tolerance < 0):
            raise ValueError(f"{self.fixture_id}: NUMERICAL parity needs a tolerance >= 0")
        if self.parity_type != NUMERICAL and self.tolerance is not None:
            raise ValueError(f"{self.fixture_id}: only NUMERICAL parity carries a tolerance")


def load_scenario(path: Path) -> list[RequestSpec]:
    """A scenario file is a JSON list of request specs."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    specs = [
        RequestSpec(
            fixture_id=str(item["fixture_id"]),
            method=str(item["method"]).upper(),
            path=str(item["path"]),
            capability=str(item["capability"]),
            parity_type=str(item.get("parity_type", SEMANTIC)),
            tolerance=item.get("tolerance"),
            query={str(k): str(v) for k, v in (item.get("query") or {}).items()},
            body=item.get("body"),
            volatile=tuple(str(v) for v in item.get("volatile", ())),
            notes=str(item.get("notes", "")),
        )
        for item in raw
    ]
    ids = [s.fixture_id for s in specs]
    if len(set(ids)) != len(ids):
        raise ValueError("scenario fixture ids must be unique")
    return specs


def fixture_from_exchange(
    spec: RequestSpec, exchange: Exchange, *, release: str, recorded_at: datetime | None = None
) -> dict[str, Any]:
    """The fixture document for one exchange. Carries no URL and no credential."""
    when = recorded_at or datetime.now(UTC)
    return {
        "schema": FIXTURE_SCHEMA,
        "fixture_id": spec.fixture_id,
        "capability_id": spec.capability,
        "reference_zip_sha256": _unit_archive_sha256(),
        "oracle": {"release": release, "recorded_at": when.replace(microsecond=0).isoformat()},
        "route": {"verb": spec.method, "path": spec.path},
        "request": {"query": exchange.query, "body": exchange.request_body},
        "response": {
            "status": exchange.status,
            "content_type": exchange.content_type,
            "body": exchange.body,
        },
        "parity_type": spec.parity_type,
        "tolerance": spec.tolerance,
        "volatile": list(spec.volatile),
        "notes": spec.notes,
    }


def _unit_archive_sha256() -> str:
    extraction = json.loads((UNIT / "EXTRACTION.json").read_text(encoding="utf-8"))
    sha: str = extraction["source"]["sha256"]
    return sha


def record(client: OracleClient, specs: Iterable[RequestSpec], out_dir: Path) -> list[Path]:
    """Replay every spec against the oracle and write one fixture per spec."""
    release = str(probe(client).get("release", ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for spec in specs:
        exchange = client.request(spec.method, spec.path, query=spec.query, body=spec.body)
        document = fixture_from_exchange(spec, exchange, release=release)
        path = out_dir / f"{spec.fixture_id}.json"
        path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", "utf-8")
        written.append(path)
    return written


def replay(client: OracleClient, fixture: Mapping[str, Any]) -> Exchange:
    """Send a fixture's request again and return the live exchange."""
    route = fixture["route"]
    request = fixture["request"]
    return client.request(
        str(route["verb"]),
        str(route["path"]),
        query={str(k): str(v) for k, v in (request.get("query") or {}).items()},
        body=request.get("body"),
    )


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Difference:
    path: str
    expected: Any
    actual: Any
    reason: str

    def __str__(self) -> str:
        return f"{self.path}: {self.reason} (expected {self.expected!r}, got {self.actual!r})"


def _volatile_matcher(patterns: Sequence[str]) -> Any:
    """Match a JSON path like ``body.workers[*].heartbeat_at`` against a pattern list.

    ``[*]`` matches any index; ``*`` as a whole segment matches any key.
    """
    compiled = []
    for pattern in patterns:
        regex = re.escape(pattern).replace(r"\[\*\]", r"\[\d+\]").replace(r"\*", r"[^.\[\]]+")
        compiled.append(re.compile("^" + regex + "$"))

    def matches(path: str) -> bool:
        return any(rx.match(path) for rx in compiled)

    return matches


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def compare_values(
    expected: Any,
    actual: Any,
    *,
    parity_type: str,
    tolerance: float | None = None,
    volatile: Sequence[str] = (),
    path: str = "body",
) -> list[Difference]:
    """Differences between two decoded bodies under a parity type.

    * ``EXACT``: everything equal, volatile fields aside.
    * ``NUMERICAL``: numbers within ``tolerance`` (absolute), everything else equal.
    * ``SEMANTIC``: same types, same object keys, same array lengths, and equal
      scalars where not volatile -- the reference's product behaviour, with the
      noise of a running system named per fixture rather than waved through.
    """
    if parity_type not in PARITY_TYPES:
        raise ValueError(f"unknown parity type {parity_type!r}")
    if parity_type == NUMERICAL and tolerance is None:
        raise ValueError("NUMERICAL comparison needs a tolerance")
    is_volatile = _volatile_matcher(volatile)
    out: list[Difference] = []
    _walk(expected, actual, path, parity_type, tolerance or 0.0, is_volatile, out)
    return out


def _walk(
    expected: Any,
    actual: Any,
    path: str,
    parity_type: str,
    tolerance: float,
    is_volatile: Any,
    out: list[Difference],
) -> None:
    if is_volatile(path):
        if _type_name(expected) != _type_name(actual):
            out.append(
                Difference(path, _type_name(expected), _type_name(actual), "volatile field type")
            )
        return
    if _type_name(expected) != _type_name(actual):
        out.append(Difference(path, expected, actual, "type differs"))
        return
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        if missing:
            out.append(Difference(path, missing, None, "keys missing"))
        if extra:
            out.append(Difference(path, None, extra, "keys added"))
        for key in sorted(set(expected) & set(actual)):
            _walk(
                expected[key],
                actual[key],
                f"{path}.{key}",
                parity_type,
                tolerance,
                is_volatile,
                out,
            )
        return
    if isinstance(expected, list):
        assert isinstance(actual, list)
        if len(expected) != len(actual):
            out.append(Difference(path, len(expected), len(actual), "array length differs"))
        for i, (e, a) in enumerate(zip(expected, actual, strict=False)):
            _walk(e, a, f"{path}[{i}]", parity_type, tolerance, is_volatile, out)
        return
    if isinstance(expected, int | float) and not isinstance(expected, bool):
        assert isinstance(actual, int | float)
        if parity_type == NUMERICAL:
            if math.isnan(expected) and math.isnan(actual):
                return
            if abs(float(expected) - float(actual)) > tolerance:
                out.append(
                    Difference(path, expected, actual, f"differs by more than {tolerance:g}")
                )
            return
        if expected != actual:
            out.append(Difference(path, expected, actual, "value differs"))
        return
    if expected != actual:
        out.append(Difference(path, expected, actual, "value differs"))


def compare_exchange(fixture: Mapping[str, Any], live: Exchange) -> list[Difference]:
    """Differences between a recorded fixture and a live exchange of the same request."""
    recorded = fixture["response"]
    out: list[Difference] = []
    if int(recorded["status"]) != live.status:
        out.append(Difference("status", recorded["status"], live.status, "status differs"))
    recorded_kind = str(recorded["content_type"]).split(";", 1)[0].strip().lower()
    live_kind = live.content_type.split(";", 1)[0].strip().lower()
    if recorded_kind != live_kind:
        out.append(Difference("content_type", recorded_kind, live_kind, "content type differs"))
    out.extend(
        compare_values(
            recorded["body"],
            live.body,
            parity_type=str(fixture["parity_type"]),
            tolerance=fixture.get("tolerance"),
            volatile=[str(v) for v in fixture.get("volatile", [])],
        )
    )
    return out


def load_fixture(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != FIXTURE_SCHEMA:
        raise ValueError(f"{path}: not a {FIXTURE_SCHEMA} document")
    for key in ("fixture_id", "route", "request", "response", "parity_type"):
        if key not in document:
            raise ValueError(f"{path}: missing {key!r}")
    return document


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _client_or_exit() -> OracleClient:
    endpoint = OracleEndpoint.from_environment()
    if endpoint is None:
        print(f"{ENV_URL} is not set; there is no oracle to reach.", file=sys.stderr)
        raise SystemExit(1)
    return OracleClient(endpoint)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe", help="GET /health through the gate and print the answer")
    rec = sub.add_parser("record", help="replay a scenario against the oracle into fixtures")
    rec.add_argument("--scenario", type=Path, required=True)
    rec.add_argument("--out", type=Path, default=DEFAULT_FIXTURES)
    cmp_ = sub.add_parser("compare", help="replay recorded fixtures and report differences")
    cmp_.add_argument("fixtures", type=Path, nargs="+")
    args = parser.parse_args(argv)

    client = _client_or_exit()
    try:
        if args.command == "probe":
            answer = probe(client)
            print(json.dumps(answer, ensure_ascii=False, indent=1))
            return 0
        if args.command == "record":
            written = record(client, load_scenario(args.scenario), args.out)
            for path in written:
                print(f"recorded {path}")
            return 0
        failed = 0
        for path in args.fixtures:
            fixture = load_fixture(path)
            differences = compare_exchange(fixture, replay(client, fixture))
            if differences:
                failed += 1
                print(f"DIFF  {fixture['fixture_id']}")
                for d in differences:
                    print(f"      {d}")
            else:
                print(f"ok    {fixture['fixture_id']}")
        return 1 if failed else 0
    except OracleUnavailable as exc:
        print(f"oracle unavailable: {exc}", file=sys.stderr)
        return 1


def as_dict(exchange: Exchange) -> dict[str, Any]:
    return asdict(exchange)


if __name__ == "__main__":
    sys.exit(main())
