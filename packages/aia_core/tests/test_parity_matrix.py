"""Consistency guard for the production parity matrix.

``docs/migration/parity-matrix.json`` is the tracker for all 78 reference
capabilities: owner, implementation state, parity type, fixtures, gates,
recorded evidence, intentional differences and release-blocker status. A
tracker that nothing checks drifts the first busy week, and a drifted parity
tracker is worse than none because it is believed.

**These checks run with no reference present**, which is the point: the
reference repository and the raw archive are both private, so a guard that
needed either would skip in CI and enforce nothing. Cross-checks against the
reference's own parity plan live in ``test_golden_fixtures.py`` and run where
the reference repository is available.

What is deliberately *not* stored in the matrix, and so not checked here, is
a verdict. Verdicts are computed by ``tools/parity_status.py`` from these
declarations plus the test results of an actual run -- a typed "PASS" is the
failure mode this file exists to prevent.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
MATRIX_PATH = REPO / "docs" / "migration" / "parity-matrix.json"
DISPOSITIONS_PATH = REPO / "docs" / "migration" / "module-dispositions.json"

CAPABILITY_COUNT = 78

PARITY_TYPES = frozenset(
    {"EXACT", "NUMERICAL", "SEMANTIC", "INTENTIONAL_DIFFERENCE", "NO_PARITY_REQUIRED"}
)
IMPLEMENTATION_STATES = frozenset({"NOT_STARTED", "PARTIAL", "IMPLEMENTED", "RETIRED"})
GATE_KINDS = frozenset(
    {
        "reference_comparison",
        "reference_characterization",
        "reference_contract",
        "golden_fixture",
        "production_contract",
    }
)
REQUIREMENTS = frozenset(
    {
        "legacy_tree",
        "reference_repo",
        "postgres",
        "population_panel",
        "r_smacof",
        "provider_credential",
    }
)
FIXTURE_STATUSES = frozenset({"CAPTURED", "SPECIFIED_NOT_CAPTURED"})
FIXTURE_GATE_STATES = frozenset(
    {"GATED", "PARTIALLY_GATED", "AWAITING_IMPLEMENTATION", "AWAITING_CAPTURE"}
)
FIXTURE_SOURCES = frozenset({"vendored", "reference_repo"})
RECORDED_VERDICTS = frozenset({"PASS", "FAIL", "NOT_EXECUTED", "NOT_RUNNABLE"})
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CAPABILITY_ID = re.compile(r"^[a-z_]+(\.[a-z_]+)?$")


@pytest.fixture(scope="module")
def matrix() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def capabilities(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    caps: dict[str, dict[str, Any]] = matrix["capabilities"]
    return caps


@pytest.fixture(scope="module")
def fixtures(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fx: dict[str, dict[str, Any]] = matrix["fixtures"]
    return fx


@pytest.fixture(scope="module")
def dispositions() -> dict[str, dict[str, Any]]:
    data = json.loads(DISPOSITIONS_PATH.read_text(encoding="utf-8"))
    return {str(m["module"]): m for m in data["modules"]}


def _test_exists(nodeid: str) -> bool:
    """A gate's test reference must name a real file and, if given, a real test."""
    path, _, name = nodeid.partition("::")
    file = REPO / path
    if not file.is_file():
        return False
    if not name:
        return True
    function = name.split("[", 1)[0].split("::")[-1]
    return re.search(rf"^\s*def {re.escape(function)}\(", file.read_text(), re.M) is not None


# --------------------------------------------------------------------------- #
# Shape
# --------------------------------------------------------------------------- #


def test_matrix_covers_exactly_the_78_reference_capabilities(
    capabilities: dict[str, dict[str, Any]],
) -> None:
    assert len(capabilities) == CAPABILITY_COUNT, (
        f"{len(capabilities)} capabilities; the reference classifies {CAPABILITY_COUNT}. "
        "A capability with no row is invisible, which is the failure this matrix fixes."
    )
    for cid, cap in capabilities.items():
        assert CAPABILITY_ID.match(cid), cid
        assert cid.split(".")[0] == cap["family"], cid


def test_reference_pin_is_complete(matrix: dict[str, Any]) -> None:
    ref = matrix["reference"]
    assert ref["repository"] == "AiAnalytics-AIA/AIA-reference"
    assert re.fullmatch(r"[0-9a-f]{40}", ref["commit"]), "pin a commit, not a movable ref"
    for key in ("archive_sha256", "parity_plan_sha256", "fixture_manifest_sha256"):
        assert SHA256.match(ref[key]), key


@pytest.mark.parametrize(
    "field",
    [
        "family",
        "bounded_context",
        "owner",
        "parity_owner",
        "implementation_state",
        "implementation",
        "reference_modules",
        "parity_type",
        "tolerance",
        "parity_reason",
        "fixtures",
        "gates",
        "recorded_evidence",
        "intentional_difference",
        "documented_deviations",
        "high_risk",
        "mvp_path",
        "release_blocker",
        "notes",
    ],
)
def test_every_capability_tracks_every_field(
    capabilities: dict[str, dict[str, Any]], field: str
) -> None:
    missing = sorted(cid for cid, cap in capabilities.items() if field not in cap)
    assert not missing, f"{field!r} missing on: {missing}"


def test_enumerations_are_closed(capabilities: dict[str, dict[str, Any]]) -> None:
    for cid, cap in capabilities.items():
        assert cap["parity_type"] in PARITY_TYPES, cid
        assert cap["implementation_state"] in IMPLEMENTATION_STATES, cid
        assert set(cap["owner"]) == {"workstream", "confirmed"}, cid
        assert cap["owner"]["workstream"], f"{cid}: no owner workstream"
        assert cap["parity_owner"] == "parity-quality", cid
        for gate in cap["gates"]:
            assert gate["kind"] in GATE_KINDS, (cid, gate["id"])
            assert set(gate["requires"]) <= REQUIREMENTS, (cid, gate["id"])
            assert gate["id"].startswith(cid + "/"), (cid, gate["id"])
        for ev in cap["recorded_evidence"]:
            assert ev["verdict"] in RECORDED_VERDICTS, cid
            assert ev["anchor"].strip(), f"{cid}: recorded evidence without an anchor"


def test_gate_ids_are_unique(capabilities: dict[str, dict[str, Any]]) -> None:
    ids = [g["id"] for cap in capabilities.values() for g in cap["gates"]]
    assert len(ids) == len(set(ids))


# --------------------------------------------------------------------------- #
# Parity semantics
# --------------------------------------------------------------------------- #


def test_numerical_parity_states_a_tolerance(capabilities: dict[str, dict[str, Any]]) -> None:
    for cid, cap in capabilities.items():
        if cap["parity_type"] == "NUMERICAL":
            assert isinstance(cap["tolerance"], float) and cap["tolerance"] > 0, cid
        else:
            assert cap["tolerance"] is None, f"{cid}: only NUMERICAL parity has a tolerance"


def test_every_intentional_difference_names_its_production_target(
    capabilities: dict[str, dict[str, Any]],
) -> None:
    for cid, cap in capabilities.items():
        diff = cap["intentional_difference"]
        if cap["parity_type"] == "INTENTIONAL_DIFFERENCE":
            assert diff is not None, cid
            assert diff["legacy"].strip() and diff["production_target"].strip(), cid
        else:
            assert diff is None, f"{cid}: intentional_difference on a {cap['parity_type']} row"


def test_no_parity_required_carries_no_gates_and_blocks_nothing(
    capabilities: dict[str, dict[str, Any]],
) -> None:
    for cid, cap in capabilities.items():
        if cap["parity_type"] == "NO_PARITY_REQUIRED":
            assert not cap["gates"], cid
            assert not cap["release_blocker"]["blocking"], cid
            assert not cap["mvp_path"], cid


def test_deviation_gates_exist(capabilities: dict[str, dict[str, Any]]) -> None:
    for cid, cap in capabilities.items():
        gate_ids = {g["id"] for g in cap["gates"]}
        for dev in cap["documented_deviations"]:
            assert dev["anchor"].strip(), (cid, dev["id"])
            if dev["gate"] is not None:
                assert dev["gate"] in gate_ids, (cid, dev["id"])


def test_every_gate_names_real_tests(capabilities: dict[str, dict[str, Any]]) -> None:
    """A gate that points at a renamed test would report NOT_EXECUTED forever."""
    dangling = [
        (cid, gate["id"], test)
        for cid, cap in capabilities.items()
        for gate in cap["gates"]
        for test in gate["tests"]
        if not _test_exists(test)
    ]
    assert not dangling, f"gates naming tests that do not exist: {dangling}"


def test_reference_backed_gates_declare_what_they_need(
    capabilities: dict[str, dict[str, Any]], fixtures: dict[str, dict[str, Any]]
) -> None:
    """A reference-backed gate must say which environment it needs, or it cannot
    be told apart from one that simply did not run. A golden gate needs what its
    fixture needs: nothing when the fixture is vendored, the reference
    repository when it is read from a checkout."""
    fixture_of = {fx["gate"]["gate_id"]: fx for fx in fixtures.values() if fx["gate"]["gate_id"]}
    for cid, cap in capabilities.items():
        for gate in cap["gates"]:
            if gate["kind"] == "golden_fixture":
                assert gate["id"] in fixture_of, f"{gate['id']} gates no fixture"
                assert gate["requires"] == fixture_of[gate["id"]]["requires"], gate["id"]
            if gate["kind"] == "reference_contract":
                assert "reference_repo" in gate["requires"], (cid, gate["id"])
            if gate["kind"] in {"reference_comparison", "reference_characterization"}:
                assert "legacy_tree" in gate["requires"], (cid, gate["id"])


# --------------------------------------------------------------------------- #
# Fixtures and the gate ratchet
# --------------------------------------------------------------------------- #


def test_fixture_links_are_consistent(
    capabilities: dict[str, dict[str, Any]], fixtures: dict[str, dict[str, Any]]
) -> None:
    for cid, cap in capabilities.items():
        for fid in cap["fixtures"]:
            assert fid in fixtures, f"{cid} names unknown fixture {fid}"
    for fid, fx in fixtures.items():
        assert fid in capabilities[fx["capability"]]["fixtures"], (
            f"{fid}'s primary capability {fx['capability']} does not list it"
        )


def test_fixture_records_are_well_formed(fixtures: dict[str, dict[str, Any]]) -> None:
    for fid, fx in fixtures.items():
        assert fx["status"] in FIXTURE_STATUSES, fid
        assert fx["gate"]["state"] in FIXTURE_GATE_STATES, fid
        assert set(fx["requires"]) <= REQUIREMENTS, fid
        if fx["status"] == "CAPTURED":
            assert SHA256.match(fx["sha256"]), fid
            assert fx["source"] in FIXTURE_SOURCES, fid
            assert fx["reference_path"].startswith("golden-fixtures/"), fid
            assert fx["gate"]["state"] != "AWAITING_CAPTURE", fid
            assert fx["gap"] is None, fid
            if fx["source"] == "vendored":
                assert fx["requires"] == [], f"{fid} is vendored and needs nothing"
            else:
                assert fx["path"] == fx["reference_path"], fid
                assert "reference_repo" in fx["requires"], fid
        else:
            assert fx["sha256"] is None and fx["path"] is None, fid
            assert fx["gate"]["state"] == "AWAITING_CAPTURE", fid
            assert fx["gap"], f"{fid} is not captured but names no reference gap"


def test_every_vendored_fixture_is_the_pinned_bytes(fixtures: dict[str, dict[str, Any]]) -> None:
    """Runs everywhere: a vendored copy that no longer hashes to its pin is a
    fixture someone edited, and a parity test against it tests itself."""
    for fid, fx in fixtures.items():
        if fx["source"] != "vendored":
            continue
        actual = hashlib.sha256((REPO / fx["path"]).read_bytes()).hexdigest()
        assert actual == fx["sha256"], f"{fid}: {fx['path']} does not hash to its pin"


def test_a_fixture_gate_link_is_one_golden_gate_of_its_capability(
    capabilities: dict[str, dict[str, Any]], fixtures: dict[str, dict[str, Any]]
) -> None:
    """``GATED`` or ``PARTIALLY_GATED`` names exactly one golden gate, and every
    golden gate is named by exactly one fixture -- from both sides."""
    linked: dict[str, str] = {}
    for fid, fx in fixtures.items():
        gid = fx["gate"]["gate_id"]
        if fx["gate"]["state"] in {"GATED", "PARTIALLY_GATED"}:
            assert gid, f"{fid} is {fx['gate']['state']} but names no gate"
            gates = {g["id"]: g for g in capabilities[fx["capability"]]["gates"]}
            assert gid in gates and gates[gid]["kind"] == "golden_fixture", (fid, gid)
            assert gid not in linked, f"{gid} gates both {linked.get(gid)} and {fid}"
            linked[gid] = fid
        else:
            assert gid is None, f"{fid} is {fx['gate']['state']} but names gate {gid}"
    golden = {
        g["id"]
        for cap in capabilities.values()
        for g in cap["gates"]
        if g["kind"] == "golden_fixture"
    }
    assert golden == set(linked), {"unlinked golden gates": sorted(golden - set(linked))}


def test_an_implemented_capability_has_every_fixture_gated(
    capabilities: dict[str, dict[str, Any]], fixtures: dict[str, dict[str, Any]]
) -> None:
    """The ratchet: a capability cannot be called implemented while a captured
    fixture that gates it is still waiting for a gate. Porting the code and
    wiring its parity gate land together, or the port is PARTIAL."""
    for cid, cap in capabilities.items():
        if cap["implementation_state"] != "IMPLEMENTED":
            continue
        ungated = [
            fid
            for fid in cap["fixtures"]
            if fixtures[fid]["status"] == "CAPTURED"
            and fixtures[fid]["gates_capability"]
            and fixtures[fid]["gate"]["state"] != "GATED"
        ]
        assert not ungated, f"{cid} is IMPLEMENTED with ungated fixtures {ungated}"


# --------------------------------------------------------------------------- #
# Implementation state versus the module inventory
# --------------------------------------------------------------------------- #


def test_implementation_anchors_exist(capabilities: dict[str, dict[str, Any]]) -> None:
    for cid, cap in capabilities.items():
        if cap["implementation_state"] in {"PARTIAL", "IMPLEMENTED"}:
            assert cap["implementation"], f"{cid} claims code but names none"
        for path in cap["implementation"]:
            assert (REPO / path).exists(), f"{cid}: {path} does not exist"


def test_reference_modules_are_in_the_inventory(
    capabilities: dict[str, dict[str, Any]], dispositions: dict[str, dict[str, Any]]
) -> None:
    for cid, cap in capabilities.items():
        unknown = [m for m in cap["reference_modules"] if m not in dispositions]
        assert not unknown, f"{cid}: modules absent from module-dispositions.json: {unknown}"


def test_implementation_state_agrees_with_the_module_inventory(
    capabilities: dict[str, dict[str, Any]], dispositions: dict[str, dict[str, Any]]
) -> None:
    """Two trackers describing one fact must not contradict each other."""
    for cid, cap in capabilities.items():
        states = {dispositions[m]["state"] for m in cap["reference_modules"]}
        if cap["implementation_state"] == "IMPLEMENTED":
            assert states <= {"done", "n/a"}, f"{cid} IMPLEMENTED but modules are {states}"
        if cap["implementation_state"] == "NOT_STARTED":
            assert not states & {"done", "partial"}, f"{cid} NOT_STARTED but modules are {states}"


def test_every_ported_module_is_claimed_by_a_started_capability(
    capabilities: dict[str, dict[str, Any]], dispositions: dict[str, dict[str, Any]]
) -> None:
    started = {
        m
        for cap in capabilities.values()
        if cap["implementation_state"] in {"PARTIAL", "IMPLEMENTED"}
        for m in cap["reference_modules"]
    }
    orphans = sorted(
        m for m, d in dispositions.items() if d["state"] in {"done", "partial"} and m not in started
    )
    assert not orphans, f"ported modules with no started capability: {orphans}"


# --------------------------------------------------------------------------- #
# Release blockers and the MVP acceptance path
# --------------------------------------------------------------------------- #


def test_release_blocker_is_exactly_the_mvp_path(capabilities: dict[str, dict[str, Any]]) -> None:
    for cid, cap in capabilities.items():
        blocker = cap["release_blocker"]
        assert blocker["reason"].strip(), cid
        assert blocker["blocking"] == cap["mvp_path"], (
            f"{cid}: release_blocker must follow the MVP acceptance path, so a blocker "
            "is something the acceptance test cannot pass without"
        )


def test_off_path_high_risk_capabilities_say_why(capabilities: dict[str, dict[str, Any]]) -> None:
    """A high-risk behaviour off the MVP path is a decision, and must read as one."""
    for cid, cap in capabilities.items():
        if cap["high_risk"] and not cap["mvp_path"]:
            assert cap["release_blocker"]["reason"].startswith("Off the MVP path"), cid
        for rid in cap["high_risk"]:
            assert re.fullmatch(r"R([1-9]|1[0-7])", rid), (cid, rid)


def test_mvp_criteria_define_the_mvp_path(
    matrix: dict[str, Any], capabilities: dict[str, dict[str, Any]]
) -> None:
    acceptance = matrix["mvp_acceptance"]
    assert (REPO / acceptance["definition"]).is_file()
    ids = [c["id"] for c in acceptance["criteria"]]
    assert len(ids) == len(set(ids))
    named = {cid for crit in acceptance["criteria"] for cid in crit["capabilities"]}
    assert named <= capabilities.keys(), named - capabilities.keys()
    on_path = {cid for cid, cap in capabilities.items() if cap["mvp_path"]}
    assert named == on_path, {"criteria only": named - on_path, "flag only": on_path - named}


def test_every_high_risk_behaviour_is_owned_by_a_capability(
    capabilities: dict[str, dict[str, Any]],
) -> None:
    owned = {rid for cap in capabilities.values() for rid in cap["high_risk"]}
    assert owned == {f"R{i}" for i in range(1, 18)}, sorted(owned)


# --------------------------------------------------------------------------- #
# CI wiring -- read as text: the workflow is the contract, and PyYAML is not a
# declared dependency of this package
# --------------------------------------------------------------------------- #

CI_WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def test_ci_fetches_the_pinned_reference_commit(matrix: dict[str, Any]) -> None:
    """The commit CI checks out and the commit the hashes were pinned at are one."""
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    block = text.split("repository: AiAnalytics-AIA/AIA-reference", 1)[1].split("\n\n", 1)[0]
    refs = re.findall(r"^\s*ref:\s*(\S+)", block, re.M)
    assert refs == [matrix["reference"]["commit"]], refs


def test_every_ci_pytest_step_writes_junit() -> None:
    """A pytest step without JUnit output is invisible to parity_status.py, so
    every gate it runs would read as NOT_EXECUTED -- or, with --available, FAIL."""
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    steps = re.split(r"\n\s+- (?=name:|uses:|run:)", text)
    silent = [
        step.splitlines()[0]
        for step in steps
        if re.search(r"^\s*(run:.*)?\bpytest (packages|apps)", step, re.M)
        and "--junit-xml" not in step
    ]
    assert not silent, f"pytest steps without --junit-xml: {silent}"


def test_every_reference_gap_is_owned_and_bound_to_its_fixture(
    matrix: dict[str, Any], fixtures: dict[str, dict[str, Any]]
) -> None:
    gaps: dict[str, dict[str, Any]] = matrix["reference_gaps"]
    named = {fx["gap"] for fx in fixtures.values() if fx["gap"]}
    assert named == set(gaps), {"fixtures only": named - set(gaps), "gaps only": set(gaps) - named}
    for gid, gap in gaps.items():
        assert fixtures[gap["fixture"]]["gap"] == gid
        assert "parity-quality" in gap["owners"] and len(gap["owners"]) >= 2, gid
        assert set(gap["blocked_on"]) <= REQUIREMENTS, gid
        assert set(gap["blocked_on"]) <= set(fixtures[gap["fixture"]]["requires"]), gid
        assert gap["blockers"] and gap["definition_of_done"].strip(), gid
        assert gap["register"].startswith(".planning/open-items.md "), gid
