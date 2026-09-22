#!/usr/bin/env python3
"""Build and verify a canonical manifest of the NPC Panel reference.

The problem this solves: running the prototype's *own* test suite writes to its
``data/`` directory and generates output under ``full_simulation_runs/`` and
``full_simulation_benchmarks/``. The file count therefore grows, and a claim like
"the directory has 1,893 files instead of 1,565, but we think we know why" is not
a useful integrity statement six phases into a migration.

This tool replaces it with a precise one:

    canonical reference source files unchanged

**The ZIP archive is the snapshot authority, and the extracted tree is not.**
That distinction is the whole point of this file, and it was learned the
expensive way: an earlier manifest was hashed from the extracted tree, which the
reference rewrites as it runs, so it measured whatever had last been executed
while describing itself as the only integrity record for the reference.

The authoritative write path therefore reads the **verified archive**:

    python tools/reference_manifest.py write --archive <reference>.zip

A tree-derived write is refused outright rather than offered as a convenience.
It cannot produce the archive hash, the reference-repository identity or the
migration module list, so it could only ever write a manifest that is missing
them -- which is exactly the regression that produced the stale manifest. See
:func:`_refuse_tree_write`.

Every write is gated on :func:`validate_schema`, so the writer cannot emit a
manifest that drops a field the current schema requires, however it was invoked.

Usage::

    python tools/reference_manifest.py write --archive <path>.zip
    python tools/reference_manifest.py verify        # tree vs manifest hashes
    python tools/reference_manifest.py check-schema  # committed manifest is v2
    python tools/reference_manifest.py status        # human-readable summary

``verify`` and ``status`` read the extracted tree from ``AIA_LEGACY_REFERENCE``;
that is a *comparison* against the manifest, not a source for it.

Reference identity, the archive hash and the bootstrap workflow are documented in
``docs/migration/reference-source.md``; ``AiAnalytics-AIA/AIA-reference`` is
authoritative for reference interpretation.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
import zipfile
from datetime import UTC, datetime
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


# --------------------------------------------------------------------------- #
# Manifest schema
#
# Version 2 is the archive-derived manifest. Version 1 was derived from the
# mutable extracted tree and carried none of the provenance below -- no archive
# hash, no reference-repository identity, no migration module list.
#
# These are not decoration. A manifest without `authoritative_source` cannot say
# *which* snapshot it describes; without `reference_repository` a reader has no
# route to the authority; without `migration_modules` the module-coverage guard
# in packages/aia_core/tests/test_module_inventory.py has nothing to enforce
# against. Dropping any of them silently re-creates the stale-manifest problem,
# which is why `validate_schema` gates every write rather than being advisory.
# --------------------------------------------------------------------------- #

MANIFEST_SCHEMA_VERSION = 2

REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "description",
        "generated_at",
        "authoritative_source",
        "reference_repository",
        "reference_note",
        "canonical_file_count",
        "migration_module_count",
        "migration_modules",
        "files",
    }
)

REQUIRED_SOURCE_KEYS: frozenset[str] = frozenset(
    {"kind", "filename", "sha256", "bytes", "version", "total_files_in_archive"}
)

REQUIRED_REPOSITORY_KEYS: frozenset[str] = frozenset({"repo", "visibility", "tag"})

# Directories excluded from the *module* list specifically. The prototype's own
# tests are not migration surface, and neither are caches or bundled demo
# payloads, which are data rather than behaviour. Kept in step with
# EXCLUDED_DIRS in packages/aia_core/tests/test_module_inventory.py.
MODULE_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {"tests", "__pycache__", "node_modules", ".venv", "demo_library", ".git"}
)


def is_migration_module(relative: str) -> bool:
    """True when a path is a reference module the migration must dispose of."""
    return relative.endswith(".py") and not MODULE_EXCLUDED_DIRS & set(relative.split("/"))


class SchemaError(Exception):
    """Raised when a manifest does not satisfy the current schema."""


def validate_schema(manifest: dict[str, Any]) -> None:
    """Raise :class:`SchemaError` unless ``manifest`` is a complete v2 manifest.

    Called on the write path *before* anything touches the file, so a writer that
    would drop provenance fails instead of producing a downgraded manifest. It is
    also what ``check-schema`` runs against the committed artifact.

    The counts are checked against the collections they describe rather than
    merely being present: a manifest claiming 191 modules while listing none is
    worse than one that admits it has none, because the claim is what a reader
    would act on.
    """
    missing = sorted(REQUIRED_KEYS - manifest.keys())
    if missing:
        raise SchemaError(
            f"manifest is missing required field(s): {', '.join(missing)}. "
            "Writing it would downgrade the manifest schema and lose reference "
            "provenance -- see docs/migration/reference-source.md."
        )

    version = manifest["schema_version"]
    if version != MANIFEST_SCHEMA_VERSION:
        raise SchemaError(
            f"manifest schema_version is {version!r}, expected {MANIFEST_SCHEMA_VERSION}"
        )

    source = manifest["authoritative_source"]
    if not isinstance(source, dict):
        raise SchemaError("authoritative_source must be an object")
    missing_source = sorted(REQUIRED_SOURCE_KEYS - source.keys())
    if missing_source:
        raise SchemaError(f"authoritative_source is missing: {', '.join(missing_source)}")
    if not isinstance(source["sha256"], str) or len(source["sha256"]) != 64:
        raise SchemaError("authoritative_source.sha256 must be a SHA256 hex digest")

    repository = manifest["reference_repository"]
    if not isinstance(repository, dict):
        raise SchemaError("reference_repository must be an object")
    missing_repo = sorted(REQUIRED_REPOSITORY_KEYS - repository.keys())
    if missing_repo:
        raise SchemaError(f"reference_repository is missing: {', '.join(missing_repo)}")

    files = manifest["files"]
    modules = manifest["migration_modules"]
    if not isinstance(files, dict) or not files:
        raise SchemaError("files must be a non-empty object")
    if not isinstance(modules, list) or not modules:
        raise SchemaError("migration_modules must be a non-empty list")

    if manifest["canonical_file_count"] != len(files):
        raise SchemaError(
            f"canonical_file_count is {manifest['canonical_file_count']} but "
            f"{len(files)} files are listed"
        )
    if manifest["migration_module_count"] != len(modules):
        raise SchemaError(
            f"migration_module_count is {manifest['migration_module_count']} but "
            f"{len(modules)} modules are listed"
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


# --------------------------------------------------------------------------- #
# The authoritative write path: the verified archive
# --------------------------------------------------------------------------- #

TREE_WRITE_REFUSAL = """\
Refusing to write the manifest from the extracted tree.

The extracted tree is MUTABLE -- running the reference rewrites its data/*.sqlite
state files -- and it cannot supply the archive hash, the reference-repository
identity or anything else the current manifest schema requires. A tree-derived
write is how the stale manifest was produced in the first place.

The authoritative regeneration workflow:

  1. Obtain the archive. AiAnalytics-AIA/AIA-reference is authoritative; see
     docs/migration/reference-source.md for its identity, SHA256 and bootstrap.
  2. Regenerate from it:

       python tools/reference_manifest.py write --archive <reference>.zip

     The archive's SHA256 is checked against the one already recorded in the
     manifest. A different archive is refused unless --accept-new-archive is
     given, because silently re-pointing the manifest at another snapshot is
     indistinguishable from corrupting it.

To compare the tree you have against the committed manifest instead, which is
what you usually want:

       python tools/reference_manifest.py verify
"""


def _refuse_tree_write() -> int:
    """Print the authoritative workflow and fail. Never writes anything.

    Option B of the review finding, enforced in the tool rather than left to
    documentation: an instruction not to do something is weaker than the thing
    being impossible.
    """
    print(TREE_WRITE_REFUSAL, file=sys.stderr)
    return 2


def _archive_members(archive: zipfile.ZipFile) -> dict[str, bytes]:
    """Return ``{relative_path: contents}`` for the archive's canonical files.

    A single top-level directory is stripped, because archives of a tree are
    commonly wrapped in one and the manifest's paths are relative to the
    reference root. Stripping is only done when *every* member shares that one
    prefix -- otherwise a legitimate top-level file would be silently relocated.
    """
    names = [n for n in archive.namelist() if not n.endswith("/")]
    roots = {n.split("/")[0] for n in names if "/" in n}
    flat = any("/" not in n for n in names)
    prefix = f"{roots.pop()}/" if len(roots) == 1 and not flat else ""

    members: dict[str, bytes] = {}
    for name in names:
        relative = name[len(prefix) :] if prefix and name.startswith(prefix) else name
        if not relative:
            continue
        if _is_canonical(Path(relative), relative):
            members[relative] = archive.read(name)
    return members


def write_from_archive(archive_path: Path, *, accept_new_archive: bool = False) -> dict[str, Any]:
    """Regenerate the manifest from the authoritative ZIP archive.

    The archive's own SHA256 is recorded, so the manifest says which snapshot it
    describes rather than merely asserting that some files hashed to something.

    Fields that identify the reference *repository* are carried over from the
    existing manifest: they are a deployment fact, not something derivable from
    an archive, and regenerating hashes is not a reason to forget them.
    """
    if not archive_path.is_file():
        raise SchemaError(f"archive not found: {archive_path}")

    archive_sha = _sha256(archive_path)
    existing: dict[str, Any] = {}
    if MANIFEST_PATH.is_file():
        existing = json.loads(MANIFEST_PATH.read_text())

    recorded = (existing.get("authoritative_source") or {}).get("sha256")
    if recorded and recorded != archive_sha and not accept_new_archive:
        raise SchemaError(
            "archive SHA256 does not match the one this manifest records.\n"
            f"  recorded: {recorded}\n"
            f"  supplied: {archive_sha}\n"
            "This is either the wrong archive or a deliberate snapshot change. "
            "Pass --accept-new-archive only if you intend to re-point the "
            "manifest at a different reference snapshot, and record the change "
            "in docs/migration/reference-source.md in the same commit."
        )

    with zipfile.ZipFile(archive_path) as archive:
        members = _archive_members(archive)
        total_in_archive = sum(1 for n in archive.namelist() if not n.endswith("/"))

    entries = {
        relative: hashlib.sha256(payload).hexdigest()
        for relative, payload in sorted(members.items())
    }
    modules = sorted(p for p in entries if is_migration_module(p))

    previous_source = existing.get("authoritative_source") or {}
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "description": (
            "SHA256 of canonical NPC Panel reference files, derived from the "
            "AUTHORITATIVE ZIP archive. Supersedes any manifest hashed from the "
            "mutable extracted tree. Runtime-generated directories are excluded "
            "-- see RUNTIME_EXCLUDES in tools/reference_manifest.py."
        ),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "authoritative_source": {
            "kind": "zip_archive",
            "filename": archive_path.name,
            "sha256": archive_sha,
            "bytes": archive_path.stat().st_size,
            "version": previous_source.get("version", "unknown"),
            "total_files_in_archive": total_in_archive,
        },
        "reference_repository": existing.get("reference_repository")
        or {
            "repo": "AiAnalytics-AIA/AIA-reference",
            "visibility": "private",
            "tag": "unknown",
            "note": (
                "Authoritative for reference interpretation. See "
                "docs/migration/reference-source.md."
            ),
        },
        "reference_note": existing.get("reference_note")
        or (
            "The extracted tree is MUTABLE -- running the reference rewrites its "
            "data/*.sqlite state files, so hash the ZIP and never the tree."
        ),
        "canonical_file_count": len(entries),
        "migration_module_count": len(modules),
        "migration_modules": modules,
        "files": entries,
    }

    # The gate. Nothing is written until the result is a complete v2 manifest.
    validate_schema(manifest)

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def check_schema() -> int:
    """Validate the committed manifest against the current schema."""
    if not MANIFEST_PATH.is_file():
        print(f"no manifest at {MANIFEST_PATH}", file=sys.stderr)
        return 2
    try:
        validate_schema(json.loads(MANIFEST_PATH.read_text()))
    except SchemaError as exc:
        print(f"manifest schema check FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"manifest schema v{MANIFEST_SCHEMA_VERSION} OK: {MANIFEST_PATH}")
    return 0


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
    parser.add_argument("command", choices=["write", "verify", "status", "check-schema"])
    parser.add_argument(
        "--archive",
        type=Path,
        help="path to the authoritative reference ZIP; required by 'write'",
    )
    parser.add_argument(
        "--accept-new-archive",
        action="store_true",
        help=(
            "allow 'write' to re-point the manifest at an archive whose SHA256 "
            "differs from the recorded one"
        ),
    )
    args = parser.parse_args()

    if args.command == "check-schema":
        return check_schema()

    if args.command == "write":
        # No archive means a tree-derived write, which is refused before the
        # reference is even resolved -- there is nothing a tree could contribute.
        if args.archive is None:
            return _refuse_tree_write()
        try:
            manifest = write_from_archive(args.archive, accept_new_archive=args.accept_new_archive)
        except SchemaError as exc:
            print(f"refusing to write the manifest: {exc}", file=sys.stderr)
            return 2
        print(
            f"wrote {MANIFEST_PATH} "
            f"(schema v{manifest['schema_version']}, "
            f"{manifest['canonical_file_count']} canonical files, "
            f"{manifest['migration_module_count']} migration modules, "
            f"archive {manifest['authoritative_source']['sha256'][:12]}…)"
        )
        return 0

    root = reference_root()
    if args.command == "verify":
        return verify(root)
    return status(root)


if __name__ == "__main__":
    raise SystemExit(main())
