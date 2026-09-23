"""The running 18.6.6 unit as the parity oracle: the contract, the harness, the first gates.

Two halves. The harness half runs everywhere: it drives ``tools/legacy_oracle.py``
against a local stub that behaves like Caddy's gate in front of the unit (401
without credentials, JSON behind it), so ``record`` / ``replay`` / ``compare``
are proven without the develop host. The oracle half is marked ``oracle`` and
reaches the real unit through ``AIA_LEGACY_REFERENCE_URL``; it skips when the
URL is unset and fails under ``AIA_REQUIRE_LEGACY_ORACLE=1``, so a missing oracle
is reported by ``tools/parity_status.py`` as ``NOT_EXECUTED``, never as a pass.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest

REPO = Path(__file__).resolve().parents[3]
UNIT = REPO / "legacy" / "npc-panel-18.6.6"
ARCHIVE_SHA256 = "86b70bfb5c1b4a7984b392cc6187c0842edc5cd28d37d2dd72dcf15d58d53216"

STUB_USER = "gatekeeper-user"
STUB_PASSWORD = "gate-secret"  # a stub's credential, never a real one


# --------------------------------------------------------------------------- #
# A stub oracle: the gate and two of the unit's answers
# --------------------------------------------------------------------------- #


class _StubOracle(BaseHTTPRequestHandler):
    """Answers like the gated unit: 401 anonymously, JSON behind basic auth."""

    calls: ClassVar[list[tuple[str, str, Any]]] = []
    health_payload: ClassVar[dict[str, Any]] = {
        "status": "ok",
        "release": "18.6.6",
        "worker_ready": True,
        "workers": [{"worker_id": "w1", "heartbeat_at": "2026-09-23T15:00:00", "status": "READY"}],
    }

    def _authorised(self) -> bool:
        expected = "Basic " + base64.b64encode(f"{STUB_USER}:{STUB_PASSWORD}".encode()).decode()
        return self.headers.get("Authorization") == expected

    def _send(self, status: int, body: Any, content_type: str = "application/json") -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self._handle(None)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"null")
        self._handle(body)

    def _handle(self, body: Any) -> None:
        if not self._authorised():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="restricted"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        path, _, query = self.path.partition("?")
        type(self).calls.append((self.command, self.path, body))
        if path == "/health":
            self._send(200, self.health_payload)
        elif path == "/api/echo":
            self._send(200, {"echo": body, "query": query, "elapsed": 0.0123})
        else:
            self._send(404, {"error": "unknown route"})

    def log_message(self, *_: Any) -> None:  # quiet
        return


@pytest.fixture
def stub_oracle(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A gated stub bound on loopback, exported through the oracle environment variables."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubOracle)
    _StubOracle.calls = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setenv("AIA_LEGACY_REFERENCE_URL", url + "/")
    monkeypatch.setenv("AIA_LEGACY_REFERENCE_USER", STUB_USER)
    monkeypatch.setenv("AIA_LEGACY_REFERENCE_PASSWORD", STUB_PASSWORD)
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()


# --------------------------------------------------------------------------- #
# The endpoint contract
# --------------------------------------------------------------------------- #


def test_no_url_means_no_oracle(legacy_oracle_tool: Any) -> None:
    assert legacy_oracle_tool.OracleEndpoint.from_environment({}) is None
    assert (
        legacy_oracle_tool.OracleEndpoint.from_environment({"AIA_LEGACY_REFERENCE_URL": " "})
        is None
    )


def test_endpoint_reads_the_three_variables_and_strips_the_slash(legacy_oracle_tool: Any) -> None:
    endpoint = legacy_oracle_tool.OracleEndpoint.from_environment(
        {
            "AIA_LEGACY_REFERENCE_URL": "https://legacy.example.test/",
            "AIA_LEGACY_REFERENCE_USER": "aia",
            "AIA_LEGACY_REFERENCE_PASSWORD": "pw",
        }
    )
    assert endpoint.url == "https://legacy.example.test"
    assert endpoint.gated
    assert endpoint.authorization() == "Basic " + base64.b64encode(b"aia:pw").decode()


def test_the_password_never_appears_in_the_endpoint_repr(legacy_oracle_tool: Any) -> None:
    endpoint = legacy_oracle_tool.OracleEndpoint("https://x.test", "aia", "very-secret")
    assert "very-secret" not in repr(endpoint)


def test_a_url_without_a_host_is_refused(legacy_oracle_tool: Any) -> None:
    with pytest.raises(ValueError, match="http\\(s\\) URL"):
        legacy_oracle_tool.OracleEndpoint.from_environment({"AIA_LEGACY_REFERENCE_URL": "legacy"})


def test_require_flag_is_exactly_one(legacy_oracle_tool: Any) -> None:
    assert legacy_oracle_tool.require_oracle({"AIA_REQUIRE_LEGACY_ORACLE": "1"})
    assert not legacy_oracle_tool.require_oracle({"AIA_REQUIRE_LEGACY_ORACLE": "true"})
    assert not legacy_oracle_tool.require_oracle({})


def test_the_fixture_skips_cleanly_without_a_url(tmp_path: Path) -> None:
    """The session fixture's skip and fail behaviour, observed from a child pytest run.

    The real conftest is copied beside a one-test module, so what is exercised is
    the fixture as shipped, not a re-statement of it.
    """
    conftest = (REPO / "packages" / "aia_core" / "tests" / "conftest.py").read_text("utf-8")
    (tmp_path / "conftest.py").write_text(
        conftest.replace(
            "_REPO_ROOT = Path(__file__).resolve().parents[3]", f"_REPO_ROOT = Path({str(REPO)!r})"
        ),
        "utf-8",
    )
    (tmp_path / "test_needs_oracle.py").write_text(
        "def test_needs_oracle(legacy_oracle):\n"
        '    raise AssertionError("must not run without an oracle")\n',
        "utf-8",
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("AIA_")}

    def run(extra_env: dict[str, str]) -> str:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
            cwd=tmp_path,
            env={**env, **extra_env},
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout + completed.stderr

    assert "1 skipped" in run({})
    assert "1 error" in run({"AIA_REQUIRE_LEGACY_ORACLE": "1"})


# --------------------------------------------------------------------------- #
# The harness against the stub
# --------------------------------------------------------------------------- #


def test_the_gate_refuses_an_anonymous_request(stub_oracle: str, legacy_oracle_tool: Any) -> None:
    endpoint = legacy_oracle_tool.OracleEndpoint.from_environment()
    client = legacy_oracle_tool.OracleClient(endpoint)
    anonymous = client.request("GET", "/health", authenticated=False)
    assert anonymous.status == 401
    behind = client.request("GET", "/health")
    assert behind.status == 200
    assert behind.is_json
    assert behind.body["status"] == "ok"


def test_probe_returns_the_health_document(stub_oracle: str, legacy_oracle_tool: Any) -> None:
    client = legacy_oracle_tool.OracleClient(legacy_oracle_tool.OracleEndpoint.from_environment())
    assert legacy_oracle_tool.probe(client)["release"] == "18.6.6"


def test_a_transport_failure_is_oracle_unavailable(legacy_oracle_tool: Any) -> None:
    client = legacy_oracle_tool.OracleClient(
        legacy_oracle_tool.OracleEndpoint("http://127.0.0.1:9"), timeout_s=1.0
    )
    with pytest.raises(legacy_oracle_tool.OracleUnavailable):
        client.request("GET", "/health")


def test_record_writes_one_fixture_per_spec_without_any_credential(
    stub_oracle: str, legacy_oracle_tool: Any, tmp_path: Path
) -> None:
    client = legacy_oracle_tool.OracleClient(legacy_oracle_tool.OracleEndpoint.from_environment())
    specs = [
        legacy_oracle_tool.RequestSpec(
            fixture_id="H_GET_health",
            method="GET",
            path="/health",
            capability="static.health",
            volatile=("body.workers[*].heartbeat_at",),
        ),
        legacy_oracle_tool.RequestSpec(
            fixture_id="H_POST_echo",
            method="POST",
            path="/api/echo",
            capability="api.echo",
            parity_type="NUMERICAL",
            tolerance=1e-9,
            query={"b": "2", "a": "1"},
            body={"x": [1, 2.5], "name": "Značka"},
        ),
    ]
    written = legacy_oracle_tool.record(client, specs, tmp_path)
    assert [p.name for p in written] == ["H_GET_health.json", "H_POST_echo.json"]

    echo = legacy_oracle_tool.load_fixture(tmp_path / "H_POST_echo.json")
    assert echo["schema"] == legacy_oracle_tool.FIXTURE_SCHEMA
    assert echo["reference_zip_sha256"] == ARCHIVE_SHA256
    assert echo["oracle"] == {"release": "18.6.6", "recorded_at": echo["oracle"]["recorded_at"]}
    assert echo["route"] == {"verb": "POST", "path": "/api/echo"}
    assert echo["request"] == {
        "query": {"b": "2", "a": "1"},
        "body": {"x": [1, 2.5], "name": "Značka"},
    }
    assert echo["response"]["status"] == 200
    assert echo["response"]["body"]["echo"] == {"x": [1, 2.5], "name": "Značka"}
    assert echo["response"]["body"]["query"] == "a=1&b=2", (
        "query is sent sorted, so replays are stable"
    )
    assert echo["parity_type"] == "NUMERICAL" and echo["tolerance"] == 1e-9

    text = "\n".join(p.read_text("utf-8") for p in written)
    assert stub_oracle not in text, "the oracle's URL is not recorded"
    assert STUB_PASSWORD not in text and STUB_USER not in text, "credentials are never recorded"


def test_replay_sends_the_recorded_request_and_compare_finds_no_difference(
    stub_oracle: str, legacy_oracle_tool: Any, tmp_path: Path
) -> None:
    client = legacy_oracle_tool.OracleClient(legacy_oracle_tool.OracleEndpoint.from_environment())
    spec = legacy_oracle_tool.RequestSpec(
        fixture_id="H_GET_health",
        method="GET",
        path="/health",
        capability="static.health",
        volatile=("body.workers[*].heartbeat_at",),
    )
    (path,) = legacy_oracle_tool.record(client, [spec], tmp_path)
    fixture = legacy_oracle_tool.load_fixture(path)
    _StubOracle.health_payload = {
        **_StubOracle.health_payload,
        "workers": [{"worker_id": "w1", "heartbeat_at": "2026-09-24T09:00:00", "status": "READY"}],
    }
    try:
        live = legacy_oracle_tool.replay(client, fixture)
        assert legacy_oracle_tool.compare_exchange(fixture, live) == []
        _StubOracle.health_payload = {**_StubOracle.health_payload, "worker_ready": False}
        live = legacy_oracle_tool.replay(client, fixture)
        differences = legacy_oracle_tool.compare_exchange(fixture, live)
        assert [d.path for d in differences] == ["body.worker_ready"]
    finally:
        _StubOracle.health_payload = {
            **_StubOracle.health_payload,
            "worker_ready": True,
            "workers": [
                {"worker_id": "w1", "heartbeat_at": "2026-09-23T15:00:00", "status": "READY"}
            ],
        }


def test_a_scenario_file_round_trips_and_rejects_duplicates(
    legacy_oracle_tool: Any, tmp_path: Path
) -> None:
    scenario = tmp_path / "scenario.json"
    scenario.write_text(
        json.dumps(
            [
                {
                    "fixture_id": "H_GET_health",
                    "method": "get",
                    "path": "/health",
                    "capability": "x",
                },
                {
                    "fixture_id": "H_POST_a",
                    "method": "POST",
                    "path": "/api/a",
                    "capability": "y",
                    "parity_type": "NUMERICAL",
                    "tolerance": 0.01,
                    "body": {"k": 1},
                    "volatile": ["body.t"],
                },
            ]
        ),
        "utf-8",
    )
    specs = legacy_oracle_tool.load_scenario(scenario)
    assert [s.method for s in specs] == ["GET", "POST"]
    assert specs[1].volatile == ("body.t",)
    scenario.write_text(
        json.dumps([{"fixture_id": "H_a", "method": "GET", "path": "/", "capability": "x"}] * 2),
        "utf-8",
    )
    with pytest.raises(ValueError, match="unique"):
        legacy_oracle_tool.load_scenario(scenario)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"fixture_id": "GET_health"}, "H_<name>"),
        ({"parity_type": "FUZZY"}, "unknown parity type"),
        ({"parity_type": "NUMERICAL"}, "needs a tolerance"),
        ({"parity_type": "EXACT", "tolerance": 0.1}, "only NUMERICAL"),
    ],
)
def test_request_specs_are_validated(
    legacy_oracle_tool: Any, kwargs: dict[str, Any], message: str
) -> None:
    base: dict[str, Any] = {
        "fixture_id": "H_GET_x",
        "method": "GET",
        "path": "/x",
        "capability": "c",
    }
    with pytest.raises(ValueError, match=message):
        legacy_oracle_tool.RequestSpec(**{**base, **kwargs})


# --------------------------------------------------------------------------- #
# The comparer, on its own
# --------------------------------------------------------------------------- #


def _paths(differences: list[Any]) -> list[str]:
    return [d.path for d in differences]


def test_exact_comparison_reports_every_difference(legacy_oracle_tool: Any) -> None:
    expected = {"a": 1, "b": [1, 2, 3], "c": {"d": "x"}, "e": None}
    actual = {"a": 1.0, "b": [1, 2], "c": {"d": "y", "extra": 1}, "f": True}
    got = legacy_oracle_tool.compare_values(expected, actual, parity_type="EXACT")
    assert _paths(got) == ["body", "body", "body.b", "body.c", "body.c.d"]
    reasons = {(d.path, d.reason) for d in got}
    assert ("body", "keys missing") in reasons and ("body", "keys added") in reasons
    assert ("body.b", "array length differs") in reasons
    assert ("body.c", "keys added") in reasons
    assert ("body.c.d", "value differs") in reasons


def test_numerical_comparison_uses_the_tolerance_and_nothing_else(
    legacy_oracle_tool: Any,
) -> None:
    expected = {"v": [0.1, 0.2, 0.3], "label": "odchylka \u03c3"}
    close = {"v": [0.1 + 5e-10, 0.2, 0.3 - 5e-10], "label": "odchylka \u03c3"}
    assert (
        legacy_oracle_tool.compare_values(expected, close, parity_type="NUMERICAL", tolerance=1e-9)
        == []
    )
    far = {"v": [0.1 + 2e-9, 0.2, 0.3], "label": "odchylka \u03c3"}
    got = legacy_oracle_tool.compare_values(expected, far, parity_type="NUMERICAL", tolerance=1e-9)
    assert _paths(got) == ["body.v[0]"]
    relabelled = {"v": [0.1, 0.2, 0.3], "label": "sigma"}
    got = legacy_oracle_tool.compare_values(
        expected, relabelled, parity_type="NUMERICAL", tolerance=1e-9
    )
    assert _paths(got) == ["body.label"], "strings are exact even under NUMERICAL parity"
    with pytest.raises(ValueError, match="tolerance"):
        legacy_oracle_tool.compare_values(expected, far, parity_type="NUMERICAL")


def test_a_boolean_is_never_a_number(legacy_oracle_tool: Any) -> None:
    got = legacy_oracle_tool.compare_values(
        {"ready": True}, {"ready": 1}, parity_type="NUMERICAL", tolerance=10.0
    )
    assert [d.reason for d in got] == ["type differs"]


def test_volatile_fields_are_compared_by_type_only(legacy_oracle_tool: Any) -> None:
    expected = {"id": "run-1", "items": [{"t": "2026-01-01", "v": 1}, {"t": "2026-01-02", "v": 2}]}
    actual = {"id": "run-2", "items": [{"t": "2026-09-23", "v": 1}, {"t": "2026-09-24", "v": 2}]}
    volatile = ["body.id", "body.items[*].t"]
    assert (
        legacy_oracle_tool.compare_values(expected, actual, parity_type="EXACT", volatile=volatile)
        == []
    )
    wrong_type = {"id": 7, "items": [{"t": None, "v": 1}, {"t": "2026-09-24", "v": 2}]}
    got = legacy_oracle_tool.compare_values(
        expected, wrong_type, parity_type="EXACT", volatile=volatile
    )
    assert _paths(got) == ["body.id", "body.items[0].t"]
    assert all(d.reason == "volatile field type" for d in got)


def test_a_star_segment_matches_any_key(legacy_oracle_tool: Any) -> None:
    expected = {"workers": {"w1": {"seen": 1}, "w2": {"seen": 2}}}
    actual = {"workers": {"w1": {"seen": 9}, "w2": {"seen": 8}}}
    assert (
        legacy_oracle_tool.compare_values(
            expected, actual, parity_type="EXACT", volatile=["body.workers.*.seen"]
        )
        == []
    )


def test_status_and_content_type_are_part_of_the_comparison(legacy_oracle_tool: Any) -> None:
    fixture = {
        "response": {"status": 200, "content_type": "application/json; charset=utf-8", "body": {}},
        "parity_type": "EXACT",
        "tolerance": None,
        "volatile": [],
    }
    live = legacy_oracle_tool.Exchange(
        method="GET",
        path="/x",
        query={},
        request_body=None,
        status=404,
        content_type="text/html",
        body="<html>",
        elapsed_ms=1,
    )
    got = legacy_oracle_tool.compare_exchange(fixture, live)
    assert _paths(got) == ["status", "content_type", "body"]


def test_the_unit_release_is_read_from_the_vendored_version_file(legacy_oracle_tool: Any) -> None:
    assert legacy_oracle_tool.unit_release() == (UNIT / "app" / "VERSION").read_text().strip()


# --------------------------------------------------------------------------- #
# Against the real oracle (marked; skipped without AIA_LEGACY_REFERENCE_URL)
# --------------------------------------------------------------------------- #

oracle = pytest.mark.oracle


@oracle
def test_health_reports_ok_and_the_vendored_release(
    legacy_oracle: Any, legacy_oracle_tool: Any
) -> None:
    """``ui_server.py`` answers ``/health`` with the release the unit declares.

    ``legacy/npc-panel-18.6.6/app/ui_server.py`` do_GET ``/health`` @ the unit:
    ``{"status":"ok","release":RELEASE,"worker_ready":...,"workers":[...]}``.
    """
    health = legacy_oracle_tool.probe(legacy_oracle)
    assert health["status"] == "ok"
    assert health["release"] == legacy_oracle_tool.unit_release()
    assert isinstance(health["worker_ready"], bool)
    assert isinstance(health["workers"], list)


@oracle
def test_anonymous_request_is_refused(legacy_oracle: Any) -> None:
    """The gate is the check (reference R14): the unit itself has no authentication."""
    if not legacy_oracle.endpoint.gated:
        pytest.fail(
            "AIA_LEGACY_REFERENCE_URL is set without AIA_LEGACY_REFERENCE_USER: an ungated "
            "oracle must not be published (ADR 0011)"
        )
    assert legacy_oracle.request("GET", "/health", authenticated=False).status == 401


@oracle
def test_bootstrap_names_the_release_and_the_panel(
    legacy_oracle: Any, legacy_oracle_tool: Any
) -> None:
    """``GET /api/bootstrap`` is the UI's first call; its top-level shape is the product's."""
    bootstrap = legacy_oracle.request("GET", "/api/bootstrap")
    assert bootstrap.status == 200 and bootstrap.is_json
    body = bootstrap.body
    assert body["release"] == legacy_oracle_tool.unit_release()
    for key in (
        "edition",
        "worker_ready",
        "validation_tier",
        "cost_modes",
        "panel",
        "empty_project",
    ):
        assert key in body, key
    assert body["panel"]["rows"] > 0 and body["panel"]["columns"] > 0
