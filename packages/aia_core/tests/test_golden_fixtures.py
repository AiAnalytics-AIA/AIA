"""Golden fixtures against the pinned reference repository.

The reference repository (``AiAnalytics-AIA/AIA-reference``) commits eleven
golden fixtures, each one self-contained JSON holding the input, the expected
output, the parity type and the tolerance, captured by executing the reference.
**None of them needs the raw archive.** They reach the parity gates two ways:

- **F1-F9 are vendored** under ``tests/fixtures/sociomap/`` and gated by the
  Sociomap engine's own tests, which run everywhere.
- **F10-F11 are read from a reference checkout** by
  ``test_population_reference_parity.py``.

``docs/migration/parity-matrix.json`` pins the commit, the fixture manifest,
the parity plan and every fixture's SHA256. This module checks a checkout
against those pins:

1. the checkout is the pinned one (manifest and parity plan hash to their pins);
2. every captured fixture in the checkout hashes to its pin, and every vendored
   copy is byte-identical to the fixture it copies;
3. the matrix agrees with the reference's own parity plan, except where a
   recorded discrepancy says why not.

Absent reference repository: every test here skips, and a skip is reported by
``tools/parity_status.py`` as ``NOT_EXECUTED``, never as a pass. CI sets
``AIA_REQUIRE_REFERENCE_REPO=1`` once the deploy key exists, which turns the
skip into a failure. The vendored copies are still checked against their pins
without a checkout, by ``test_parity_matrix.py``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
MATRIX = json.loads((REPO / "docs" / "migration" / "parity-matrix.json").read_text("utf-8"))
PIN = MATRIX["reference"]
FIXTURES: dict[str, dict[str, Any]] = MATRIX["fixtures"]
CAPTURED = sorted(fid for fid, fx in FIXTURES.items() if fx["status"] == "CAPTURED")

pytestmark = pytest.mark.golden


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_fixture(reference_repo: Path, fixture_id: str) -> dict[str, Any]:
    """Load a fixture, refusing one that does not hash to its pin."""
    record = FIXTURES[fixture_id]
    path = reference_repo / record["reference_path"]
    actual = _sha256(path)
    assert actual == record["sha256"], (
        f"{fixture_id} hashes to {actual}, pinned {record['sha256']}; the reference "
        "checkout is not the pinned commit, or the fixture was edited"
    )
    body: dict[str, Any] = json.loads(path.read_text("utf-8"))
    assert body["fixture_id"] == fixture_id
    assert body["reference_zip_sha256"] == PIN["archive_sha256"]
    return body


# --------------------------------------------------------------------------- #
# 1. Integrity of the checkout
# --------------------------------------------------------------------------- #


def test_fixture_manifest_is_the_pinned_one(reference_repo: Path) -> None:
    actual = _sha256(reference_repo / "golden-fixtures" / "manifest.json")
    assert actual == PIN["fixture_manifest_sha256"], (
        f"fixture manifest hashes to {actual}; pinned {PIN['fixture_manifest_sha256']} "
        f"at {PIN['commit']}. Check out the pinned commit, or re-pin deliberately."
    )


def test_parity_plan_is_the_pinned_one(reference_repo: Path) -> None:
    assert _sha256(reference_repo / "parity-plan.json") == PIN["parity_plan_sha256"]


def test_manifest_lists_exactly_the_captured_fixtures(reference_repo: Path) -> None:
    manifest = json.loads((reference_repo / "golden-fixtures" / "manifest.json").read_text())
    listed = {f["fixture_id"]: f for f in manifest["fixtures"]}
    assert sorted(listed) == CAPTURED
    for fid in CAPTURED:
        assert listed[fid]["output_sha256"] == FIXTURES[fid]["sha256"], fid
        assert listed[fid]["capability_id"] == FIXTURES[fid]["capability"], fid
        assert listed[fid]["parity_type"] == FIXTURES[fid]["parity_type"], fid
        assert listed[fid]["tolerance"] == FIXTURES[fid]["tolerance"], fid


@pytest.mark.parametrize("fixture_id", CAPTURED)
def test_captured_fixture_matches_its_pin(reference_repo: Path, fixture_id: str) -> None:
    _load_fixture(reference_repo, fixture_id)


VENDORED = sorted(fid for fid in CAPTURED if FIXTURES[fid]["source"] == "vendored")


@pytest.mark.parametrize("fixture_id", VENDORED)
def test_vendored_copy_is_the_reference_fixture(reference_repo: Path, fixture_id: str) -> None:
    """The copy the gates read and the file in the authority are the same bytes."""
    record = FIXTURES[fixture_id]
    vendored = (REPO / record["path"]).read_bytes()
    assert vendored == (reference_repo / record["reference_path"]).read_bytes(), fixture_id


def test_matrix_agrees_with_the_reference_parity_plan(reference_repo: Path) -> None:
    """Parity type, tolerance and fixture links are the reference's call.

    Where production deliberately departs from a link, the departure is a
    recorded discrepancy with a reason -- never a silent edit.
    """
    plan = json.loads((reference_repo / "parity-plan.json").read_text())
    reference = {c["capability"]: c for c in plan["capabilities"]}
    ours = MATRIX["capabilities"]
    assert sorted(reference) == sorted(ours)
    rejected = {
        (d["rejected_fixture_link"]["capability"], d["rejected_fixture_link"]["fixture"])
        for d in MATRIX["reference_discrepancies"]
        if d.get("rejected_fixture_link")
    }
    for cid, ref in reference.items():
        cap = ours[cid]
        assert cap["parity_type"] == ref["parity_type"], cid
        assert cap["tolerance"] == ref["tolerance"], cid
        expected = sorted(f for f in ref["fixtures"] if (cid, f) not in rejected)
        captured = sorted(f for f in cap["fixtures"] if FIXTURES[f]["status"] == "CAPTURED")
        assert captured == expected, cid
