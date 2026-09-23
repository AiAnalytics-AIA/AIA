"""The route ledger covers the reference HTTP surface exactly and says what AIA does with each.

``docs/migration/legacy-route-ledger.json`` has one row per unique verb + path of
the 162 dispatch arms the reference recovered from ``ui_server.py`` and
``prototype_server.py`` (``AIA-reference/api-ledger.json``). Its statuses are
the strangling's progress: ``LEGACY`` (oracle only), ``PORTING`` (an AIA route
exists), ``PORTED`` (parity ``PASS``, legacy path retired), ``RETIRED`` (by a
recorded decision). These tests keep the ledger honest without the reference
present, and, with a checkout, prove it still covers the reference's ledger byte
for byte at the pinned hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
LEDGER_PATH = REPO / "docs" / "migration" / "legacy-route-ledger.json"
UNIT = REPO / "legacy" / "npc-panel-18.6.6" / "app"
PLAN = REPO / ".planning" / "plans" / "legacy-strangler.md"

STATUSES = frozenset({"LEGACY", "PORTING", "PORTED", "RETIRED"})
SCOPES = frozenset({"public", "organization", "study", "undecided (D8)"})
VERBS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
MATCHES = frozenset({"exact", "prefix", "suffix"})
SOURCES = frozenset({"ui_server.py", "prototype_server.py"})
DECISIONS = frozenset({"D8", "D9", "D-L1"})
AIA_ROUTE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE) /api/v1/\S+$")


@pytest.fixture(scope="module")
def ledger() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def routes(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = ledger["routes"]
    return rows


# --------------------------------------------------------------------------- #
# Shape, without the reference
# --------------------------------------------------------------------------- #


def test_one_row_per_unique_verb_and_path(
    ledger: dict[str, Any], routes: list[dict[str, Any]]
) -> None:
    keys = [(r["verb"], r["path"]) for r in routes]
    assert len(keys) == len(set(keys)), "a verb + path appears twice"
    assert len(routes) == ledger["reference"]["unique_verb_path_count"] == 153
    assert sum(len(r["arms"]) for r in routes) == ledger["reference"]["route_count"] == 162


def test_rows_are_sorted_by_path_then_verb(routes: list[dict[str, Any]]) -> None:
    assert [(r["path"], r["verb"]) for r in routes] == sorted(
        (r["path"], r["verb"]) for r in routes
    )


def test_every_row_is_well_formed(routes: list[dict[str, Any]]) -> None:
    for r in routes:
        assert r["route"] == f"{r['verb']} {r['path']}", r["route"]
        assert r["verb"] in VERBS, r["route"]
        assert r["path"].startswith("/"), r["route"]
        assert r["status"] in STATUSES, r["route"]
        assert r["scope"] in SCOPES, r["route"]
        assert isinstance(r["slice"], int) and 2 <= r["slice"] <= 15, r["route"]
        assert r["family"] and r["api_ledger_capability"], r["route"]
        assert r["reference_capabilities"] == sorted(set(r["reference_capabilities"])), r["route"]
        assert r["arms"], r["route"]
        for arm in r["arms"]:
            assert arm["source"] in SOURCES and arm["match"] in MATCHES, r["route"]
            assert isinstance(arm["line"], int) and arm["line"] > 0, r["route"]
            assert isinstance(arm["origin_guarded"], bool), r["route"]
        assert r["decision"] is None or r["decision"] in DECISIONS, r["route"]


def test_a_ported_or_porting_row_names_a_study_or_public_aia_route(
    routes: list[dict[str, Any]],
) -> None:
    """Scope is decided when a route is ported, and carried in the AIA path (ARCHITECTURE.md §2)."""
    for r in routes:
        if r["status"] in {"PORTING", "PORTED"}:
            assert r["aia_route"] and AIA_ROUTE.match(r["aia_route"]), r["route"]
            assert r["scope"] != "undecided (D8)", (
                f"{r['route']}: a ported route has a decided scope"
            )
            if r["scope"] == "study":
                assert "/api/v1/studies/{study_id}/" in r["aia_route"], r["route"]
            if r["scope"] == "public":
                assert r["aia_route"].split(" ", 1)[1] in {"/api/v1/health", "/api/v1/ready"}, r[
                    "route"
                ]
        else:
            assert r["aia_route"] is None, f"{r['route']}: only a ported route names an AIA route"


def test_a_retired_row_names_its_decision(routes: list[dict[str, Any]]) -> None:
    for r in routes:
        if r["status"] == "RETIRED":
            assert r["decision"], f"{r['route']}: retirement needs a recorded decision"


def test_prototype_server_arms_are_pending_decision_d9(routes: list[dict[str, Any]]) -> None:
    """The second server's four routes are reference decision D9, not an engineering call."""
    second = [r for r in routes if any(a["source"] == "prototype_server.py" for a in r["arms"])]
    assert sorted(r["route"] for r in second) == [
        "GET /",
        "GET /files/",
        "GET /health",
        "GET /status",
    ]
    for r in second:
        assert r["decision"] == "D9", r["route"]
        assert r["status"] != "RETIRED", f"{r['route']}: D9 is open, nothing is retired under it"


def test_every_dispatch_arm_points_at_a_real_line_of_the_unit(routes: list[dict[str, Any]]) -> None:
    """The ledger's anchors are lines of the vendored unit, byte-identical to the archive."""
    sources = {name: (UNIT / name).read_text(encoding="utf-8").splitlines() for name in SOURCES}
    for r in routes:
        for arm in r["arms"]:
            line = sources[arm["source"]][arm["line"] - 1]
            needle = r["path"]
            assert needle in line, (
                f"{r['route']} arm {arm['source']}:{arm['line']} does not mention {needle!r}"
            )


def test_nothing_is_ported_yet(routes: list[dict[str, Any]]) -> None:
    """PORTED means parity PASS from executed gates. No oracle gate has executed yet.

    When the first route reaches PORTED, replace this with the assertion that its
    capability's oracle gate exists in the parity matrix.
    """
    assert Counter(r["status"] for r in routes)["PORTED"] == 0


def test_every_slice_in_the_ledger_is_in_the_plan(routes: list[dict[str, Any]]) -> None:
    plan = PLAN.read_text(encoding="utf-8")
    slices = {int(m.group(1)) for m in re.finditer(r"^\| (\d+) \|", plan, re.M)}
    for r in routes:
        assert r["slice"] in slices or r["slice"] >= 15, f"{r['route']} names slice {r['slice']}"


# --------------------------------------------------------------------------- #
# Coverage of the reference, with a checkout
# --------------------------------------------------------------------------- #


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_ledger_covers_exactly_the_reference_api_ledger(
    reference_repo: Path, ledger: dict[str, Any], routes: list[dict[str, Any]]
) -> None:
    api_ledger = reference_repo / "api-ledger.json"
    assert _sha256(api_ledger) == ledger["reference"]["api_ledger_sha256"], (
        "the reference api-ledger changed; regenerate the route ledger deliberately"
    )
    reference = json.loads(api_ledger.read_text(encoding="utf-8"))
    expected = Counter((r["verb"], r["path"]) for r in reference["routes"])
    ours = {(r["verb"], r["path"]): r for r in routes}
    assert set(ours) == set(expected)
    for key, count in expected.items():
        assert len(ours[key]["arms"]) == count, key
    for r in reference["routes"]:
        row = ours[(r["verb"], r["path"])]
        assert row["api_ledger_capability"] == r["capability"], r["path"]
        assert {
            "source": r["source"],
            "line": r["line"],
            "match": r["match"],
            "origin_guarded": r["origin_guarded"],
        } in row["arms"], r["path"]


def test_reference_capabilities_and_families_are_the_capability_maps(
    reference_repo: Path, ledger: dict[str, Any], routes: list[dict[str, Any]]
) -> None:
    capability_map = reference_repo / "capability-map.json"
    assert _sha256(capability_map) == ledger["reference"]["capability_map_sha256"]
    document = json.loads(capability_map.read_text(encoding="utf-8"))
    capabilities: dict[tuple[str, str], set[str]] = {}
    families: dict[tuple[str, str], str] = {}
    for capability in document["capabilities"]:
        for route in capability["http_routes"]:
            key = (route["verb"], route["path"])
            capabilities.setdefault(key, set()).add(capability["capability"])
            families[key] = capability["family"]
    for r in routes:
        key = (r["verb"], r["path"])
        assert r["reference_capabilities"] == sorted(capabilities[key]), r["route"]
        assert r["family"] == families[key], r["route"]
