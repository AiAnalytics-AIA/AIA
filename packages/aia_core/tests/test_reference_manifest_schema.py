"""The manifest writer must not be able to downgrade the manifest schema.

This exists because of a specific near-miss. `test_module_inventory.py` told a
developer to repair manifest drift with::

    python tools/reference_manifest.py write

while that writer scanned the **mutable extracted tree** and emitted the old
schema. Following the instruction would have silently discarded the archive
SHA256, the reference-repository identity and the migration module list --
recreating exactly the stale-manifest problem the archive-derived manifest was
introduced to fix, and leaving a manifest that still *looked* authoritative.

The defence is in three layers, and each is asserted here:

1. A tree-derived write is **refused**, not merely discouraged.
2. Every write is gated on ``validate_schema`` before anything is written, so a
   manifest missing a required field cannot reach disk by any path.
3. The committed manifest is itself checked against the schema, so a hand-edit
   that drops a field fails the build rather than waiting to be noticed.

The tests build synthetic archives. The real reference archive is withheld
pending a licence decision (see ``docs/migration/reference-source.md``), and a
guard that needed it would skip in CI and protect nothing -- which is the same
mistake in a different place.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "reference_manifest.py"
COMMITTED_MANIFEST = REPO_ROOT / "docs" / "migration" / "reference-manifest.json"


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    """Import the tool by path -- `tools/` is a script directory, not a package."""
    spec = importlib.util.spec_from_file_location("reference_manifest", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _complete_manifest(tool: ModuleType) -> dict[str, Any]:
    """A minimal manifest that satisfies the current schema."""
    return {
        "schema_version": tool.MANIFEST_SCHEMA_VERSION,
        "description": "test",
        "generated_at": "2026-09-22T00:00:00+00:00",
        "authoritative_source": {
            "kind": "zip_archive",
            "filename": "reference.zip",
            "sha256": "a" * 64,
            "bytes": 1,
            "version": "18.6.6",
            "total_files_in_archive": 1,
        },
        "reference_repository": {
            "repo": "AiAnalytics-AIA/AIA-reference",
            "visibility": "private",
            "tag": "reference-18.6.6-gemo-2026-09-11-v1",
        },
        "reference_note": "test",
        "canonical_file_count": 1,
        "migration_module_count": 1,
        "migration_modules": ["project_pipeline.py"],
        "files": {"project_pipeline.py": "b" * 64},
    }


def _archive(path: Path, members: dict[str, bytes]) -> Path:
    """Write a synthetic reference archive."""
    with zipfile.ZipFile(path, "w") as zf:
        for name, payload in members.items():
            zf.writestr(name, payload)
    return path


# --------------------------------------------------------------------------- #
# Layer 1: a tree-derived write is refused
# --------------------------------------------------------------------------- #


def test_write_without_an_archive_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    """**The P1 regression, asserted directly.**

    The documented repair instruction must not be able to produce a manifest. A
    tree cannot supply the archive hash or the repository identity, so the only
    manifest it could write is a downgraded one.
    """
    before = COMMITTED_MANIFEST.read_bytes()

    result = subprocess.run(
        [sys.executable, str(TOOL_PATH), "write"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )

    assert result.returncode != 0, "a tree-derived write must fail"
    assert COMMITTED_MANIFEST.read_bytes() == before, "the manifest was modified"

    # The refusal has to be actionable, or the next person works around it.
    assert "--archive" in result.stderr
    assert "docs/migration/reference-source.md" in result.stderr


def test_the_refusal_names_the_authoritative_workflow(tool: ModuleType) -> None:
    """A refusal that does not say what to do instead is a dead end."""
    message = tool.TREE_WRITE_REFUSAL
    assert "AiAnalytics-AIA/AIA-reference" in message
    assert "write --archive" in message
    assert "verify" in message


# --------------------------------------------------------------------------- #
# Layer 2: the schema gate
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "dropped",
    [
        "schema_version",
        "authoritative_source",
        "reference_repository",
        "migration_modules",
        "migration_module_count",
        "files",
        "canonical_file_count",
        "generated_at",
    ],
)
def test_validate_schema_rejects_a_manifest_missing_any_required_field(
    tool: ModuleType, dropped: str
) -> None:
    """Each field is individually load-bearing, so each is individually required.

    Parametrised rather than asserted as a set so a failure names the field that
    went missing -- which is the thing a reader needs to know.
    """
    manifest = _complete_manifest(tool)
    del manifest[dropped]

    with pytest.raises(tool.SchemaError) as exc:
        tool.validate_schema(manifest)
    assert dropped in str(exc.value)


def test_validate_schema_rejects_an_older_schema_version(tool: ModuleType) -> None:
    """A v1 manifest is the stale manifest. It must not validate."""
    manifest = _complete_manifest(tool)
    manifest["schema_version"] = 1
    with pytest.raises(tool.SchemaError, match="schema_version"):
        tool.validate_schema(manifest)


def test_validate_schema_rejects_an_incomplete_authoritative_source(
    tool: ModuleType,
) -> None:
    """Present but hollow is the failure a key check alone would miss."""
    manifest = _complete_manifest(tool)
    del manifest["authoritative_source"]["sha256"]
    with pytest.raises(tool.SchemaError, match="sha256"):
        tool.validate_schema(manifest)


def test_validate_schema_rejects_a_malformed_archive_hash(tool: ModuleType) -> None:
    manifest = _complete_manifest(tool)
    manifest["authoritative_source"]["sha256"] = "not-a-digest"
    with pytest.raises(tool.SchemaError, match="SHA256"):
        tool.validate_schema(manifest)


def test_validate_schema_rejects_counts_that_contradict_their_collections(
    tool: ModuleType,
) -> None:
    """A manifest claiming 191 modules while listing none is worse than silence.

    The claim is what a reader acts on, so an inconsistent count is a defect
    rather than cosmetic drift.
    """
    manifest = _complete_manifest(tool)
    manifest["migration_module_count"] = 191
    with pytest.raises(tool.SchemaError, match="migration_module_count"):
        tool.validate_schema(manifest)

    manifest = _complete_manifest(tool)
    manifest["canonical_file_count"] = 1324
    with pytest.raises(tool.SchemaError, match="canonical_file_count"):
        tool.validate_schema(manifest)


def test_validate_schema_rejects_an_empty_module_list(tool: ModuleType) -> None:
    """Zero modules means the coverage guard has nothing to enforce against."""
    manifest = _complete_manifest(tool)
    manifest["migration_modules"] = []
    manifest["migration_module_count"] = 0
    with pytest.raises(tool.SchemaError, match="migration_modules"):
        tool.validate_schema(manifest)


def test_a_complete_manifest_validates(tool: ModuleType) -> None:
    """The gate must admit a correct manifest, or it is just an outage."""
    tool.validate_schema(_complete_manifest(tool))


# --------------------------------------------------------------------------- #
# The archive write path
# --------------------------------------------------------------------------- #


def test_writing_from_an_archive_produces_a_complete_manifest(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The authoritative path carries the provenance a tree write cannot."""
    archive = _archive(
        tmp_path / "reference.zip",
        {
            "project_pipeline.py": b"print('pipeline')\n",
            "tools/helper.py": b"print('helper')\n",
            "tests/test_thing.py": b"assert True\n",
            "demo_library/canonical/demo.py": b"pass\n",
            "PRODUCT_POLICY.json": b"{}\n",
            "data/state.sqlite": b"runtime state",
        },
    )
    target = tmp_path / "manifest.json"
    monkeypatch.setattr(tool, "MANIFEST_PATH", target)

    manifest = tool.write_from_archive(archive)

    tool.validate_schema(manifest)
    assert (
        manifest["authoritative_source"]["sha256"]
        == hashlib.sha256(archive.read_bytes()).hexdigest()
    )

    # Runtime state is excluded; a .sqlite is not a canonical suffix.
    assert "data/state.sqlite" not in manifest["files"]
    # The prototype's own tests and bundled demo payloads are not migration
    # surface, so they are hashed but not listed as modules.
    assert "tests/test_thing.py" in manifest["files"]
    assert manifest["migration_modules"] == ["project_pipeline.py", "tools/helper.py"]
    assert manifest["migration_module_count"] == 2
    assert json.loads(target.read_text())["schema_version"] == 2


def test_a_single_top_level_directory_is_stripped(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Archives of a tree are usually wrapped in one folder; paths are not."""
    archive = _archive(
        tmp_path / "wrapped.zip",
        {
            "npc-panel-18.6.6/project_pipeline.py": b"pass\n",
            "npc-panel-18.6.6/sub/mod.py": b"pass\n",
        },
    )
    monkeypatch.setattr(tool, "MANIFEST_PATH", tmp_path / "m.json")

    manifest = tool.write_from_archive(archive)
    assert sorted(manifest["files"]) == ["project_pipeline.py", "sub/mod.py"]


def test_a_root_level_file_prevents_prefix_stripping(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stripping when only *some* members share a prefix would relocate files.

    The reference archive has root-level launchers next to directories, so this
    is the real shape rather than a hypothetical one.
    """
    archive = _archive(
        tmp_path / "flat.zip",
        {"START.bat": b"echo\n", "pkg/mod.py": b"pass\n"},
    )
    monkeypatch.setattr(tool, "MANIFEST_PATH", tmp_path / "m.json")

    manifest = tool.write_from_archive(archive)
    assert sorted(manifest["files"]) == ["START.bat", "pkg/mod.py"]


def test_a_different_archive_is_refused_unless_explicitly_accepted(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-pointing the manifest at another snapshot must be deliberate.

    Silently accepting a different archive is indistinguishable from corrupting
    the manifest, and the corruption would carry a valid-looking hash.
    """
    target = tmp_path / "manifest.json"
    monkeypatch.setattr(tool, "MANIFEST_PATH", target)

    first = _archive(tmp_path / "a.zip", {"project_pipeline.py": b"v1\n"})
    tool.write_from_archive(first)
    recorded = json.loads(target.read_text())["authoritative_source"]["sha256"]

    second = _archive(tmp_path / "b.zip", {"project_pipeline.py": b"v2\n"})
    with pytest.raises(tool.SchemaError, match="does not match"):
        tool.write_from_archive(second)

    assert json.loads(target.read_text())["authoritative_source"]["sha256"] == recorded

    tool.write_from_archive(second, accept_new_archive=True)
    assert json.loads(target.read_text())["authoritative_source"]["sha256"] != recorded


def test_repository_identity_survives_regeneration(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where the reference lives is a deployment fact an archive cannot supply.

    Regenerating hashes is not a reason to forget it -- losing it on every
    rewrite is half of the original defect.
    """
    target = tmp_path / "manifest.json"
    target.write_text(
        json.dumps(
            {
                "reference_repository": {
                    "repo": "AiAnalytics-AIA/AIA-reference",
                    "visibility": "private",
                    "tag": "reference-18.6.6-gemo-2026-09-11-v1",
                },
                "authoritative_source": {"version": "18.6.6 + GEMO patch 2026-09-11"},
            }
        )
    )
    monkeypatch.setattr(tool, "MANIFEST_PATH", target)

    archive = _archive(tmp_path / "r.zip", {"project_pipeline.py": b"pass\n"})
    manifest = tool.write_from_archive(archive, accept_new_archive=True)

    assert manifest["reference_repository"]["tag"] == "reference-18.6.6-gemo-2026-09-11-v1"
    assert manifest["authoritative_source"]["version"] == "18.6.6 + GEMO patch 2026-09-11"


# --------------------------------------------------------------------------- #
# Layer 3: the committed artifact
# --------------------------------------------------------------------------- #


def test_the_committed_manifest_satisfies_the_current_schema(tool: ModuleType) -> None:
    """A hand-edit that drops a field fails here rather than in six months."""
    tool.validate_schema(json.loads(COMMITTED_MANIFEST.read_text(encoding="utf-8")))


def test_check_schema_command_passes_on_the_committed_manifest() -> None:
    """The same guarantee through the CLI, which is what a human would run."""
    result = subprocess.run(
        [sys.executable, str(TOOL_PATH), "check-schema"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "schema v2 OK" in result.stdout
