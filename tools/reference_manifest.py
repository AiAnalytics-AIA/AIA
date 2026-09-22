#!/usr/bin/env python3
"""Build and verify a canonical manifest of the NPC Panel reference.

The problem this solves: running the prototype's *own* test suite writes to its
``data/`` directory and generates output under ``full_simulation_runs/`` and
``full_simulation_benchmarks/``. The file count therefore grows, and a claim like
"the directory has 1,893 files instead of 1,565, but we think we know why" is not
a useful integrity statement six phases into a migration.

This tool replaces it with a precise one:

    canonical reference source files unchanged

It hashes only the inputs that define behaviour -- source, configuration, tests,
packaged reference data, documentation -- and explicitly excludes directories the
prototype writes to at runtime.

Usage::

    python tools/reference_manifest.py write    # create the manifest
    python tools/reference_manifest.py verify   # fail if canonical files changed
    python tools/reference_manifest.py status   # human-readable summary

The reference path comes from ``AIA_LEGACY_REFERENCE``, defaulting to
``../npc-panel-reference``.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "docs/migration/reference-manifest.json"

# Directories and patterns the prototype writes to when its own tests or its
# application run. Excluded from the canonical set: changes here are expected and
# carry no information about whether behaviour was modified.
RUNTIME_EXCLUDES: tuple[str, ...] = (
    # Application and test runtime state
    "data/*",
    "logs/*",
    "runs/*",
    "prototype_outputs/*",
    "vystupy/*",
    "diagnostics/*",
    "remediation/*",
    # Generated simulation output
    "full_simulation_runs/*",
    "full_simulation_benchmarks/*",
    "full_simulation_batches/*",
    # Caches and editor noise
    "**/__pycache__/*",
    "**/.pytest_cache/*",
    "**/*.pyc",
    "**/.DS_Store",
    ".git/*",
)

# Everything that defines behaviour. A change to any of these is a change to the
# reference and must be deliberate and tracked.
CANONICAL_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py",  # source and tests
        ".json",  # policies, contracts, registries
        ".csv",  # packaged reference data
        ".md",  # documentation and release notes
        ".html",  # the reference UI
        ".toml",
        ".txt",  # requirements
        ".sql",
        ".gz",  # the population panel
        ".sh",
        ".bat",
        ".ps1",
    }
)


def _excluded(relative: str) -> bool:
    """True when a path is runtime-generated rather than canonical."""
    return any(
        fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(f"**/{relative}", pattern)
        for pattern in RUNTIME_EXCLUDES
    )


def _is_canonical(path: Path, relative: str) -> bool:
    """True when a file defines reference behaviour."""
    if _excluded(relative):
        return False
    return path.suffix.lower() in CANONICAL_SUFFIXES


def _sha256(path: Path) -> str:
    """Hash a file in chunks, so a 7 MB panel does not need to fit in memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reference_root() -> Path:
    """Resolve the reference directory, or exit with an explanation."""
    configured = os.environ.get("AIA_LEGACY_REFERENCE")
    candidates = (
        [Path(configured)]
        if configured
        else [
            Path(__file__).resolve().parents[2] / "npc-panel-reference",
            Path.home() / "Downloads" / "AIA" / "npc-panel-reference",
        ]
    )
    for candidate in candidates:
        if (candidate / "project_pipeline.py").is_file():
            return candidate.resolve()

    sys.exit(
        "NPC Panel reference not found. Set AIA_LEGACY_REFERENCE to the "
        "npc-panel-reference checkout."
    )


def scan(root: Path) -> dict[str, str]:
    """Return ``{relative_path: sha256}`` for every canonical file."""
    entries: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if _is_canonical(path, relative):
            entries[relative] = _sha256(path)
    return entries


def write(root: Path) -> dict[str, Any]:
    """Write the canonical manifest."""
    entries = scan(root)
    manifest: dict[str, Any] = {
        "description": (
            "SHA256 of canonical NPC Panel reference files: source, configuration, "
            "tests, packaged data and documentation. Runtime-generated directories "
            "are excluded -- see RUNTIME_EXCLUDES in tools/reference_manifest.py. "
            "Verify with: python tools/reference_manifest.py verify"
        ),
        "reference_note": (
            "The reference is a snapshot with no git history. This manifest is the "
            "only integrity record for it. Any intentional edit must be recorded in "
            "docs/migration/reference-weaknesses.md and the manifest regenerated in "
            "the same commit."
        ),
        "canonical_file_count": len(entries),
        "files": entries,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def verify(root: Path) -> int:
    """Compare the reference against the manifest. Returns a process exit code."""
    if not MANIFEST_PATH.is_file():
        print(f"no manifest at {MANIFEST_PATH}; run 'write' first", file=sys.stderr)
        return 2

    expected: dict[str, str] = json.loads(MANIFEST_PATH.read_text())["files"]
    actual = scan(root)

    changed = sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k])
    missing = sorted(expected.keys() - actual.keys())
    added = sorted(actual.keys() - expected.keys())

    if not (changed or missing or added):
        print(f"canonical reference source files unchanged ({len(actual)} files verified)")
        return 0

    print("CANONICAL REFERENCE FILES DIFFER FROM THE MANIFEST", file=sys.stderr)
    for label, paths in (("modified", changed), ("missing", missing), ("added", added)):
        for path in paths[:40]:
            print(f"  {label}: {path}", file=sys.stderr)
        if len(paths) > 40:
            print(f"  … and {len(paths) - 40} more {label}", file=sys.stderr)
    print(
        "\nIf this was intentional, record it in "
        "docs/migration/reference-weaknesses.md and regenerate the manifest in the "
        "same commit. If not, the reference has drifted and parity results are "
        "no longer trustworthy.",
        file=sys.stderr,
    )
    return 1


def status(root: Path) -> int:
    """Print a summary of canonical versus runtime-generated files."""
    canonical = scan(root)
    total = sum(1 for p in root.rglob("*") if p.is_file() and ".git/" not in p.as_posix())

    print(f"reference root:   {root}")
    print(f"canonical files:  {len(canonical)}")
    print(f"total files:      {total}")
    print(f"runtime/excluded: {total - len(canonical)}")
    print()
    print("Runtime-generated paths are excluded because the prototype's own test")
    print("suite and application write to them. Only canonical files carry")
    print("behavioural meaning.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["write", "verify", "status"])
    args = parser.parse_args()

    root = reference_root()
    if args.command == "write":
        manifest = write(root)
        print(f"wrote {MANIFEST_PATH} ({manifest['canonical_file_count']} canonical files)")
        return 0
    if args.command == "verify":
        return verify(root)
    return status(root)


if __name__ == "__main__":
    raise SystemExit(main())
