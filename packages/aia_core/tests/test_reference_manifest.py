"""Tests for the canonical reference manifest tool.

The manifest is the only integrity record for the NPC Panel reference, which is a
snapshot with no git history. A manifest tool that silently fails to detect a
change would be worse than none, because it would license a false claim.

These tests run against synthetic directories, so they need no reference
checkout and never touch the real one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

TOOLS = Path(__file__).resolve().parents[3] / "tools"


@pytest.fixture(scope="module")
def manifest_tool() -> Any:
    """Import the manifest tool."""
    sys.path.insert(0, str(TOOLS))
    try:
        import reference_manifest

        return reference_manifest
    finally:
        sys.path.remove(str(TOOLS))


@pytest.fixture
def fake_reference(tmp_path: Path) -> Path:
    """A miniature reference tree with both canonical and runtime files."""
    root = tmp_path / "npc-panel-reference"

    # Canonical: behaviour-defining.
    (root).mkdir()
    (root / "project_pipeline.py").write_text("STAGES = ['BRIEF']\n")
    (root / "PRODUCT_POLICY.json").write_text('{"version": "18.6.6"}\n')
    (root / "requirements.txt").write_text("pandas>=2.1\n")
    (root / "README.md").write_text("# Reference\n")
    (root / "PANEL.csv").write_text("a,b\n1,2\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_core.py").write_text("def test_x(): pass\n")

    # Runtime-generated: written by the prototype's own tests and application.
    for directory, name in (
        ("data", "project_store.sqlite"),
        ("logs", "run.log"),
        ("full_simulation_runs", "spec.json"),
        ("full_simulation_benchmarks", "meta.json"),
        ("prototype_outputs", "out.json"),
        ("vystupy", "report.json"),
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)
        (root / directory / name).write_text("runtime state\n")

    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "mod.pyc").write_bytes(b"\x00compiled")

    return root


def test_scan_includes_only_canonical_files(manifest_tool: Any, fake_reference: Path) -> None:
    """Source, config, tests, data and docs are canonical; runtime output is not."""
    entries = manifest_tool.scan(fake_reference)

    assert set(entries) == {
        "PANEL.csv",
        "PRODUCT_POLICY.json",
        "README.md",
        "project_pipeline.py",
        "requirements.txt",
        "tests/test_core.py",
    }
    assert all(len(digest) == 64 for digest in entries.values())


@pytest.mark.parametrize(
    "path",
    [
        "data/project_store.sqlite",
        "logs/run.log",
        "full_simulation_runs/spec.json",
        "full_simulation_benchmarks/meta.json",
        "prototype_outputs/out.json",
        "vystupy/report.json",
        "__pycache__/mod.pyc",
    ],
)
def test_runtime_paths_are_excluded(manifest_tool: Any, fake_reference: Path, path: str) -> None:
    """Changes under these paths carry no behavioural meaning.

    The prototype writes to them when its own suite runs, which is why the raw
    file count is not an integrity signal.
    """
    assert path not in manifest_tool.scan(fake_reference)


def test_runtime_churn_does_not_change_the_canonical_set(
    manifest_tool: Any, fake_reference: Path
) -> None:
    """The exact property the manifest exists to assert.

    Simulates what running the prototype's own test suite does: new and modified
    runtime files, growing the tree. The canonical set must be identical.
    """
    before = manifest_tool.scan(fake_reference)

    (fake_reference / "data" / "project_store.sqlite").write_text("mutated by tests\n")
    (fake_reference / "full_simulation_runs" / "new_run").mkdir()
    (fake_reference / "full_simulation_runs" / "new_run" / "spec.json").write_text("{}\n")
    (fake_reference / "logs" / "another.log").write_text("noise\n")

    assert manifest_tool.scan(fake_reference) == before


def test_verify_detects_a_modified_canonical_file(
    manifest_tool: Any, fake_reference: Path, monkeypatch: Any, tmp_path: Path
) -> None:
    """A one-character change to source must fail verification.

    Without this the manifest would license the claim it is supposed to prove.
    """
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setattr(manifest_tool, "MANIFEST_PATH", manifest_path)
    monkeypatch.setenv("AIA_LEGACY_REFERENCE", str(fake_reference))

    assert manifest_tool.write(fake_reference)["canonical_file_count"] == 6
    assert manifest_tool.verify(fake_reference) == 0

    (fake_reference / "project_pipeline.py").write_text("STAGES = ['BRIEF', 'SNEAKY']\n")
    assert manifest_tool.verify(fake_reference) == 1


def test_verify_detects_a_deleted_canonical_file(
    manifest_tool: Any, fake_reference: Path, monkeypatch: Any, tmp_path: Path
) -> None:
    """A removed source file is drift too, not merely a smaller tree."""
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setattr(manifest_tool, "MANIFEST_PATH", manifest_path)

    manifest_tool.write(fake_reference)
    (fake_reference / "PRODUCT_POLICY.json").unlink()

    assert manifest_tool.verify(fake_reference) == 1


def test_verify_detects_an_added_canonical_file(
    manifest_tool: Any, fake_reference: Path, monkeypatch: Any, tmp_path: Path
) -> None:
    """A new source file is drift: someone edited the reference."""
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setattr(manifest_tool, "MANIFEST_PATH", manifest_path)

    manifest_tool.write(fake_reference)
    (fake_reference / "extra_module.py").write_text("def surprise(): pass\n")

    assert manifest_tool.verify(fake_reference) == 1


def test_verify_without_a_manifest_is_an_error_not_a_pass(
    manifest_tool: Any, fake_reference: Path, monkeypatch: Any, tmp_path: Path
) -> None:
    """A missing manifest must not be reported as "unchanged"."""
    monkeypatch.setattr(manifest_tool, "MANIFEST_PATH", tmp_path / "absent.json")
    assert manifest_tool.verify(fake_reference) == 2


def test_manifest_records_why_it_exists(
    manifest_tool: Any, fake_reference: Path, monkeypatch: Any, tmp_path: Path
) -> None:
    """The file explains itself, because it will be read without this test."""
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setattr(manifest_tool, "MANIFEST_PATH", manifest_path)
    manifest_tool.write(fake_reference)

    manifest = json.loads(manifest_path.read_text())
    assert "runtime" in manifest["description"].lower()
    assert "reference-weaknesses" in manifest["reference_note"]
    assert manifest["canonical_file_count"] == len(manifest["files"])


def test_committed_manifest_matches_the_real_reference(
    manifest_tool: Any, legacy_root: Path
) -> None:
    """The committed manifest must verify against the actual reference.

    Marked parity: it skips without a reference checkout, and fails loudly if the
    reference has drifted from what the repository claims.
    """
    assert manifest_tool.verify(legacy_root) == 0


test_committed_manifest_matches_the_real_reference = pytest.mark.parity(
    test_committed_manifest_matches_the_real_reference
)
